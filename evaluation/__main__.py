"""CLI оценки тестовой корзины (task4 §21).

Единая точка входа для запуска сценариев, метрик, сравнения версий навыка и
экспорта отчёта. Делегирует к существующему харнессу (tests/run_basket.py,
tests/score.py, athanor.control) — использует фактический стек проекта.

Примеры (task4 §21):
  python -m evaluation run --scenario scenario_01
  python -m evaluation run --scenario TB-01 --engine rule
  python -m evaluation run-all
  python -m evaluation run-all --engine llm --mock
  python -m evaluation compare-skills --baseline v1 --candidate v2
  python -m evaluation export-report
  python -m evaluation reproducibility
  python -m evaluation evolution
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

BASKET = _ROOT / "test-basket"
RUNS = _ROOT / "results" / "runs"


def _norm_scenario(sid: str) -> str:
    """scenario_01 / scenario-01 / 01 → TB-01; TB-01 → TB-01."""
    s = sid.strip()
    if s.upper().startswith("TB-"):
        return s.upper()
    if s.lower().startswith("scenario"):
        num = s.lower().replace("scenario", "").strip("-_")
        return f"TB-{int(num):02d}"
    if s.isdigit():
        return f"TB-{int(s):02d}"
    return s


def _run_py(script: str, *extra: str) -> int:
    return subprocess.call([sys.executable, str(_ROOT / script), *extra], cwd=str(_ROOT))


def cmd_run(args: argparse.Namespace) -> int:
    tb = _norm_scenario(args.scenario)
    case_dir = BASKET / tb
    if not case_dir.is_dir():
        print(f"Сценарий не найден: {tb} (иском: {args.scenario})", file=sys.stderr)
        return 2
    run_id = args.run_id or f"one_{tb}_{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    out_root = RUNS / run_id
    out_root.mkdir(parents=True, exist_ok=True)
    extra = ["--engine", args.engine, "--run-id", run_id]
    if args.mock:
        extra.append("--mock")
    # Прогон всей корзины с фильтром не поддерживается — запустим один сценарий напрямую
    sys.path.insert(0, str(_ROOT / "tests"))
    from run_basket import run_one  # noqa: E402
    from athanor.config import load_config  # noqa: E402
    from athanor.llm import set_cost_log_path  # noqa: E402
    from athanor.skill_versioning import get_active_version  # noqa: E402

    cfg = dict(load_config())
    engine = args.engine or cfg.get("ATHANOR_ENGINE", "rule")
    if engine == "llm" and (args.mock or not cfg.get("LLM_API_KEY")):
        cfg["ATHANOR_LLM_MOCK"] = "1"
        cfg["LLM_API_KEY"] = cfg.get("LLM_API_KEY") or "mock"
    set_cost_log_path(out_root / "llm_cost.log")
    m = run_one(case_dir, cfg, out_root, engine, get_active_version())
    manifest = {"run_id": run_id, "engine": engine, "scenarios": 1, "results": [m]}
    (out_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{tb}: status={m['status']} A·F1={m['actions']['f1']:.2f} D·F1={m['decisions']['f1']:.2f} "
          f"S·F1={m['summary']['f1']:.2f} t={m['elapsed_seconds']:.2f}s · {out_root}")
    return 0 if m["status"] != "failed" else 1


def cmd_run_all(args: argparse.Namespace) -> int:
    run_id = args.run_id or f"eval_{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    extra = ["--engine", args.engine, "--run-id", run_id]
    if args.mock or args.engine == "llm":
        extra.append("--mock")
    rc = _run_py("tests/run_basket.py", *extra)
    if rc:
        return rc
    return _run_py("tests/score.py", "--run", str(RUNS / run_id), "--mirror")


def cmd_compare_skills(args: argparse.Namespace) -> int:
    from athanor.control import control_runner

    b = control_runner(args.baseline)
    c = control_runner(args.candidate)
    print(f"baseline {args.baseline}: P/R/F1 = {b['precision']}/{b['recall']}/{b['f1']}")
    print(f"candidate {args.candidate}: P/R/F1 = {c['precision']}/{c['recall']}/{c['f1']}")
    no_degradation = c["f1"] >= b["f1"]
    verdict = "ПРИМЕНИТЬ (нет деградации)" if no_degradation else "ОТКЛОНИТЬ (деградация F1)"
    print(f"verdict: {verdict}")
    result = {"baseline": args.baseline, "candidate": args.candidate,
              "baseline_metrics": b, "candidate_metrics": c,
              "no_degradation": no_degradation, "verdict": verdict}
    out = _ROOT / "results" / f"compare_{args.baseline}_{args.candidate}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if no_degradation else 1


def cmd_export_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run) if args.run else _latest_run()
    extra = ["--run", str(run_dir)]
    if args.mirror:
        extra.append("--mirror")
    return _run_py("tests/score.py", *extra)


def cmd_reproducibility(args: argparse.Namespace) -> int:
    return _run_py("scripts/run_reproducibility.py", *(["--runs", str(args.runs)] if args.runs != 3 else []))


def cmd_evolution(args: argparse.Namespace) -> int:
    return _run_py("scripts/run_evaluation.py", "--engine", "rule")


def _latest_run() -> Path:
    if not RUNS.is_dir():
        return RUNS
    dirs = sorted(d for d in RUNS.iterdir() if d.is_dir() and (d / "manifest.json").is_file())
    return dirs[-1] if dirs else RUNS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evaluation", description="Оценка тестовой корзины Ouroboros (task4 §21)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="запуск одного сценария")
    pr.add_argument("--scenario", required=True, help="scenario_01 / TB-01 / 1")
    pr.add_argument("--engine", choices=["rule", "llm"], default="rule")
    pr.add_argument("--mock", action="store_true", help="mock-LLM (без сети/ключа)")
    pr.add_argument("--run-id", default=None)
    pr.set_defaults(func=cmd_run)

    pa = sub.add_parser("run-all", help="запуск всей тестовой корзины + метрики")
    pa.add_argument("--engine", choices=["rule", "llm"], default="rule")
    pa.add_argument("--mock", action="store_true")
    pa.add_argument("--run-id", default=None)
    pa.set_defaults(func=cmd_run_all)

    pc = sub.add_parser("compare-skills", help="сравнение версий навыка (контрольные тесты)")
    pc.add_argument("--baseline", default="v1")
    pc.add_argument("--candidate", default="v2")
    pc.set_defaults(func=cmd_compare_skills)

    pe = sub.add_parser("export-report", help="сформировать отчёт по прогону")
    pe.add_argument("--run", default=None, help="папка прогона (по умолчанию — последний)")
    pe.add_argument("--mirror", action="store_true", help="скопировать артефакты в results/")
    pe.set_defaults(func=cmd_export_report)

    prp = sub.add_parser("reproducibility", help="повторные прогоны критических сценариев")
    prp.add_argument("--runs", type=int, default=3)
    prp.set_defaults(func=cmd_reproducibility)

    pev = sub.add_parser("evolution", help="демонстрация эволюции навыка (promote/rollback)")
    pev.set_defaults(func=cmd_evolution)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
