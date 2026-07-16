"""Генератор эталонной разметки test-basket/TB-XX/expected/ (заморозка до прогонов).

Запускается ОДИН раз после проверки входов (scripts/gen_basket.py) и ручной
сверки вывода rule-движка. Эталон = результат корректного извлечения на
замороженных обезличенных входах; после генерации не подгоняется под прогон.

Запуск: python scripts/gen_expected.py
Пишет: expected/decisions.json, expected/actions.json, expected/blockers.json,
       expected/summary.json, expected/flags.json
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from athanor.agent import run_case  # noqa: E402
from athanor.config import load_config  # noqa: E402
from athanor.memory import _slug  # noqa: E402
from athanor.sources import load_case_from_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASKET = ROOT / "test-basket"


def _seed_memory(case_dir: Path) -> Path:
    mem = Path(tempfile.mkdtemp(prefix="exp-mem-"))
    (mem / "knowledge").mkdir(parents=True, exist_ok=True)
    seed = case_dir / "input" / "memory_seed.md"
    if seed.is_file():
        first = seed.read_text(encoding="utf-8").splitlines()[0]
        if "«" in first and "»" in first:
            name = f"release_{_slug(first.split('«')[1].split('»')[0])}.md"
            shutil.copy(seed, mem / "knowledge" / name)
    return mem


def main() -> int:
    cfg = dict(load_config())
    cfg["ATHANOR_ENGINE"] = "rule"
    cfg["ATHANOR_LLM_MOCK"] = "0"
    for case_dir in sorted(BASKET.iterdir()):
        if not case_dir.is_dir():
            continue
        meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
        if meta.get("manual_expected"):
            # Эталон зафиксирован вручную (task4 §20) — не перезаписывать выводом агента
            print(f"{case_dir.name}: пропуск (manual_expected=True)")
            continue
        case = load_case_from_files(case_dir, transcripts_down=meta.get("transcripts_down", False))
        mem = _seed_memory(case_dir)
        out = Path(tempfile.mkdtemp(prefix="exp-out-"))
        res = run_case(
            case, case_dir.name, cfg, mem, out / "outbox",
            engine="rule", format_profile=meta.get("format", "v1"), make_hitl_drafts=False,
        )
        exp = case_dir / "expected"
        exp.mkdir(parents=True, exist_ok=True)
        (exp / "decisions.json").write_text(
            json.dumps(
                [{"text": d.text, "reason": d.reason, "source": d.source} for d in res.decisions],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        (exp / "actions.json").write_text(
            json.dumps(
                [{"action": a.action, "owner": a.owner, "due": a.due, "source": a.source} for a in res.actions],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        (exp / "blockers.json").write_text(
            json.dumps(
                [{"id": b.id, "description": b.description, "severity": b.severity,
                  "source_evidence": b.source_evidence, "confidence": b.confidence,
                  "resolution_status": b.resolution_status} for b in res.blockers],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        (exp / "summary.json").write_text(
            json.dumps(
                [{"text": it.text, "source": it.source, "confidence": it.confidence, "kind": it.kind}
                 for it in res.summary_items],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        (exp / "flags.json").write_text(
            json.dumps(
                {"security_flags": res.security_flags, "warnings": res.warnings,
                 "memory_updates": res.memory_updates},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        print(f"{case_dir.name}: D={len(res.decisions)} A={len(res.actions)} B={len(res.blockers)} "
              f"sec={len(res.security_flags)} warn={len(res.warnings)}")
        shutil.rmtree(mem, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
