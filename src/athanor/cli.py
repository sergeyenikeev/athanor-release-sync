"""CLI прототипа.

Примеры:
  python -m athanor.cli run --case test-basket/TB-01 --engine rule --print
  python -m athanor.cli run --case test-basket/TB-03 --engine llm --out results/scratch/TB-03
  python -m athanor.cli run --case test-basket/TB-01 --via-mcp   # через MCP-серверы
  python -m athanor.cli approve --draft outbox/TB-04-D01.json
  python -m athanor.cli reject  --draft outbox/TB-04-D01.json --reason "неактуально"
  python -m athanor.cli edit    --draft outbox/TB-04-D01.json --subject "новая тема"
  python -m athanor.cli comment --draft outbox/TB-04-D01.json --text "проверить срок"
  python -m athanor.cli demo                          # демо-прогон < 3 мин
  python -m athanor.cli basket --engine rule          # вся корзина
  python -m athanor.cli score                         # метрики последнего прогона
  python -m athanor.cli feedback --usefulness 3 --format-change "короче, блокеры сверху"
  python -m athanor.cli versions                      # реестр версий навыка
  python -m athanor.cli promote --version v2          # применить с контрольным тестом
  python -m athanor.cli rollback --to v1              # откат
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .agent import run_case
from .config import load_config
from .format import render_result
from .hitl import approve_draft, comment_draft, edit_draft, execute_draft, reject_draft
from .models import Feedback
from .sources import load_case_from_files, load_case_via_mcp

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_meta(case_dir: Path) -> dict:
    meta = case_dir / "meta.json"
    return json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}


def _prepare_memory(case_dir: Path, memory_arg: str | None) -> Path:
    """Память прогона: --memory DIR, иначе временная копия с посевом кейса."""
    if memory_arg:
        return Path(memory_arg)
    tmp = Path(tempfile.mkdtemp(prefix="athanor-mem-"))
    (tmp / "knowledge").mkdir(parents=True, exist_ok=True)
    identity = REPO_ROOT / "memory" / "identity.md"
    if identity.is_file():
        shutil.copy(identity, tmp / "identity.md")
    seed = case_dir / "input" / "memory_seed.md"
    if seed.is_file():
        first = seed.read_text(encoding="utf-8").splitlines()[0]
        name = "release_alfa.md"
        if "«" in first and "»" in first:
            from .memory import _slug  # noqa: PLC0415

            name = f"release_{_slug(first.split('«')[1].split('»')[0])}.md"
        shutil.copy(seed, tmp / "knowledge" / name)
    return tmp


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    case_dir = Path(args.case)
    if not case_dir.is_dir():
        print(f"Кейс не найден: {case_dir}", file=sys.stderr)
        return 2
    meta = _load_meta(case_dir)
    engine = args.engine or cfg["ATHANOR_ENGINE"]
    if engine == "llm" and not cfg.get("LLM_API_KEY") and cfg.get("ATHANOR_LLM_MOCK") != "1":
        cfg["ATHANOR_LLM_MOCK"] = "1"
        cfg["LLM_API_KEY"] = "mock"
    fmt = args.format or meta.get("format", "v1")
    transcripts_down = bool(meta.get("transcripts_down", False))

    if args.via_mcp:
        case = load_case_via_mcp(cfg, case_dir.name)
    else:
        case = load_case_from_files(case_dir, transcripts_down=transcripts_down)

    memory_dir = _prepare_memory(case_dir, args.memory)
    out_dir = Path(args.out) if args.out else Path("results/scratch") / case_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    from .skill_versioning import get_active_version  # noqa: PLC0415

    res = run_case(
        case,
        case_id=case_dir.name,
        cfg=cfg,
        memory_dir=memory_dir,
        outbox_dir=out_dir / "outbox",
        engine=engine,
        format_profile=fmt,
        skill_version=get_active_version(),
    )

    md = render_result(res)
    (out_dir / "output.md").write_text(md, encoding="utf-8")
    (out_dir / "run.json").write_text(
        json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mem_after = out_dir / "memory_after"
    shutil.rmtree(mem_after, ignore_errors=True)
    shutil.copytree(memory_dir, mem_after)

    if args.print:
        print(md)
    else:
        print(f"OK: {out_dir / 'output.md'} · движок {engine} · формат {fmt}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    draft = approve_draft(Path(args.draft))
    print(f"Подтверждено человеком: {draft['id']} → статус {draft['status']}")
    if args.execute:
        execute_draft(Path(args.draft))
        print(f"Исполнено (демо-имитация): {draft['id']}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    draft = reject_draft(Path(args.draft), reason=args.reason or "")
    print(f"Отклонено человеком: {draft['id']} → статус {draft['status']}"
          + (f" (причина: {draft.get('reject_reason')})" if draft.get('reject_reason') else ""))
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    patch: dict[str, Any] = {}
    if args.subject:
        patch["subject"] = args.subject
    if args.body:
        patch["body"] = args.body
    if args.to_role:
        patch["to_role"] = args.to_role
    if args.due:
        patch["due"] = args.due
    if not patch:
        print("Не указано ни одного поля для правки (--subject/--body/--to-role/--due)", file=sys.stderr)
        return 2
    draft = edit_draft(Path(args.draft), patch)
    print(f"Отредактировано человеком: {draft['id']} · поля: {', '.join(patch)}")
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    draft = comment_draft(Path(args.draft), args.text)
    print(f"Комментарий добавлен: {draft['id']} · всего комментариев: {len(draft.get('comments', []))}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Один детерминированный end-to-end прогон (< 3 мин): сводка → извлечение →
    черновики → подтверждение HITL → обновление памяти."""
    case_dir = Path(args.case)
    cfg = load_config()
    engine = args.engine
    if engine == "llm" and not cfg.get("LLM_API_KEY") and cfg.get("ATHANOR_LLM_MOCK") != "1":
        cfg["ATHANOR_LLM_MOCK"] = "1"
        cfg["LLM_API_KEY"] = "mock"
    meta = _load_meta(case_dir)
    fmt = args.format or meta.get("format", "v1")
    case = load_case_from_files(case_dir, transcripts_down=bool(meta.get("transcripts_down", False)))
    memory_dir = _prepare_memory(case_dir, None)
    run_id = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = REPO_ROOT / "results" / "demo" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    from .skill_versioning import get_active_version  # noqa: PLC0415

    res = run_case(case, case_id=case_dir.name, cfg=cfg, memory_dir=memory_dir,
                   outbox_dir=out_dir / "outbox", engine=engine, format_profile=fmt,
                   skill_version=get_active_version())
    md = render_result(res)
    (out_dir / "output.md").write_text(md, encoding="utf-8")
    (out_dir / "run.json").write_text(json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(out_dir / "memory_after", ignore_errors=True)
    shutil.copytree(memory_dir, out_dir / "memory_after")

    # HITL: подтверждаем и исполняем все черновики (демо-имитация отправки)
    approved = 0
    for d in res.drafts:
        p = out_dir / "outbox" / f"{d['id']}.json"
        if p.is_file():
            approve_draft(p)
            execute_draft(p)
            approved += 1

    print(md)
    print(f"\n— HITL: подтверждено и исполнено (демо) черновиков: {approved}/{len(res.drafts)}")
    print(f"— Память релиза обновлена: {len(res.memory_updates)} записей (см. {out_dir / 'memory_after'})")
    print(f"— Артефакты: {out_dir}")
    return 0


def _run_script(script: str, extra: list[str]) -> int:
    py = sys.executable or "python"
    cmd = [py, str(REPO_ROOT / script), *extra]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


def cmd_basket(args: argparse.Namespace) -> int:
    extra = ["--engine", args.engine]
    if args.mock:
        extra.append("--mock")
    if args.run_id:
        extra += ["--run-id", args.run_id]
    return _run_script("tests/run_basket.py", extra)


def cmd_score(args: argparse.Namespace) -> int:
    extra = ["--run", args.run] if args.run else []
    if args.mirror:
        extra.append("--mirror")
    return _run_script("tests/score.py", extra)


def cmd_feedback(args: argparse.Namespace) -> int:
    from . import feedback as fb_mod  # noqa: PLC0415
    from .control import control_runner  # noqa: PLC0415
    from .skill_versioning import get_active_version  # noqa: PLC0415

    memory_dir = REPO_ROOT / "memory"
    fb = Feedback(
        run_id=args.run_id or "manual",
        usefulness=args.usefulness,
        format_change=args.format_change or "",
        comment=args.comment or "",
    )
    rec = fb_mod.save_feedback(memory_dir, fb)
    print(f"Обратная связь сохранена: memory/feedback.jsonl (usefulness={fb.usefulness})")
    proposal = fb_mod.feedback_to_proposal(fb)
    if proposal.get("format_profile"):
        print(f"Предложение: применить {proposal['format_profile']} ({proposal['reason']})")
        result = fb_mod.apply_feedback_proposal(memory_dir, proposal, control_runner)
        print(f"Результат promote: {result}")
    else:
        print("Предложение по изменению навыка не сформировано (низкий приоритет).")
    return 0


def cmd_versions(args: argparse.Namespace) -> int:
    from .skill_versioning import list_versions, get_active_version  # noqa: PLC0415

    active = get_active_version()
    print(f"Активная версия: {active}\n")
    for v in list_versions():
        print(f"  {v['version']:<4} статус={v['status']:<10} формат={v['format_profile']}"
              f"  причина: {v['reason']}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    from .control import control_runner  # noqa: PLC0415
    from .skill_versioning import promote  # noqa: PLC0415

    result = promote(args.version, reason=f"CLI promote by user", control_runner=control_runner,
                     memory_dir=REPO_ROOT / "memory")
    print(f"promote {args.version}: {result}")
    return 0 if result.get("applied") else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    from .skill_versioning import rollback  # noqa: PLC0415

    result = rollback(args.to)
    print(f"rollback → {args.to}: {result}")
    return 0 if result.get("applied") else 1


def main(argv: list[str] | None = None) -> int:
    # Windows: консоль по умолчанию cp1251 — русские и спецсимволы (→, ✅, ⚠) ломают вывод.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(prog="athanor", description="Athanor release_sync CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="сквозной прогон одного кейса")
    pr.add_argument("--case", required=True, help="папка кейса, напр. test-basket/TB-01")
    pr.add_argument("--engine", choices=["llm", "rule"], help="движок извлечения")
    pr.add_argument("--format", choices=["v1", "v2"], help="формат сводки (версия навыка)")
    pr.add_argument("--memory", help="папка памяти (по умолчанию — временная с посевом кейса)")
    pr.add_argument("--out", help="папка результатов (по умолчанию results/scratch/<кейс>)")
    pr.add_argument("--via-mcp", action="store_true", help="читать данные через MCP-серверы (live→реальные Jira/Bitbucket/Confluence/Google; file→выгрузка)")
    pr.add_argument("--print", action="store_true", help="вывести результат в консоль")
    pr.set_defaults(func=cmd_run)

    pa = sub.add_parser("approve", help="подтвердить черновик (HITL)")
    pa.add_argument("--draft", required=True, help="путь к outbox/<id>.json")
    pa.add_argument("--execute", action="store_true", help="также исполнить (демо-имитация)")
    pa.set_defaults(func=cmd_approve)

    pr = sub.add_parser("reject", help="отклонить черновик (HITL)")
    pr.add_argument("--draft", required=True, help="путь к outbox/<id>.json")
    pr.add_argument("--reason", default="", help="причина отклонения")
    pr.set_defaults(func=cmd_reject)

    pe = sub.add_parser("edit", help="отредактировать черновик (HITL)")
    pe.add_argument("--draft", required=True, help="путь к outbox/<id>.json")
    pe.add_argument("--subject", default="", help="новая тема письма")
    pe.add_argument("--body", default="", help="новый текст письма")
    pe.add_argument("--to-role", default="", help="новый получатель (роль)")
    pe.add_argument("--due", default="", help="новый срок")
    pe.set_defaults(func=cmd_edit)

    pc = sub.add_parser("comment", help="добавить комментарий к черновику (HITL)")
    pc.add_argument("--draft", required=True, help="путь к outbox/<id>.json")
    pc.add_argument("--text", required=True, help="текст комментария")
    pc.set_defaults(func=cmd_comment)

    pd = sub.add_parser("demo", help="детерминированный end-to-end демо-прогон")
    pd.add_argument("--case", default="examples/demo_case", help="папка кейса (по умолчанию examples/demo_case)")
    pd.add_argument("--engine", choices=["llm", "rule"], default="rule", help="движок")
    pd.add_argument("--format", choices=["v1", "v2"], help="формат сводки")
    pd.set_defaults(func=cmd_demo)

    pb = sub.add_parser("basket", help="прогон тестовой корзины TB-01..TB-17")
    pb.add_argument("--engine", choices=["llm", "rule"], default="rule")
    pb.add_argument("--mock", action="store_true", help="mock-LLM")
    pb.add_argument("--run-id", default=None)
    pb.set_defaults(func=cmd_basket)

    ps = sub.add_parser("score", help="расчёт метрик и артефакты оценки")
    ps.add_argument("--run", default=None, help="папка прогона (по умолчанию — последний)")
    ps.add_argument("--mirror", action="store_true", help="скопировать артефакты в results/")
    ps.set_defaults(func=cmd_score)

    pf = sub.add_parser("feedback", help="сохранить обратную связь и предложить изменение навыка")
    pf.add_argument("--usefulness", type=int, default=0, help="оценка полезности 1..5")
    pf.add_argument("--format-change", default="", help='напр. "короче, блокеры сверху"')
    pf.add_argument("--run-id", default="manual")
    pf.add_argument("--comment", default="")
    pf.set_defaults(func=cmd_feedback)

    pv = sub.add_parser("versions", help="реестр версий навыка")
    pv.set_defaults(func=cmd_versions)

    pp = sub.add_parser("promote", help="применить версию навыка после контрольных тестов")
    pp.add_argument("--version", required=True)
    pp.set_defaults(func=cmd_promote)

    prb = sub.add_parser("rollback", help="откат к стабильной версии навыка")
    prb.add_argument("--to", required=True)
    prb.set_defaults(func=cmd_rollback)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
