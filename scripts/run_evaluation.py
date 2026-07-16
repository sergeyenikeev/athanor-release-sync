"""Полная оценка: прогон корзины + метрики + демонстрация эволюции навыка (v1→v2→rollback).

Запуск:
  python scripts/run_evaluation.py                # rule-baseline
  python scripts/run_evaluation.py --engine llm   # mock-LLM (без сети) или реальная LLM (с ключом)
"""
import _bootstrap  # noqa: F401
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

from athanor.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *extra: str) -> int:
    cmd = [sys.executable, str(ROOT / script), *extra]
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["rule", "llm"], default="rule")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    run_id = args.run_id or f"eval_{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}"

    # 1) Прогон корзины
    extra = ["--engine", args.engine, "--run-id", run_id]
    if args.mock or args.engine == "llm":
        extra.append("--mock")
    rc = _run("tests/run_basket.py", *extra)
    if rc != 0:
        return rc

    # 2) Метрики + артефакты (с зеркалированием в results/)
    rc = _run("tests/score.py", "--run", str(ROOT / "results" / "runs" / run_id), "--mirror")
    if rc != 0:
        return rc

    # 3) Демонстрация эволюции навыка: promote v2 (контрольный тест без деградации) + rollback
    print("\n--- Эволюция навыка: promote v2 (контрольный тест) ---")
    cli_main(["versions"])
    cli_main(["promote", "--version", "v2"])
    print("\n--- Откат к v1 ---")
    cli_main(["rollback", "--to", "v1"])
    cli_main(["versions"])
    print(f"\nГотово. Артефакты: results/runs/{run_id}/ и results/{{metrics.json,metrics.csv,results_summary.md,evaluation_report.html}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
