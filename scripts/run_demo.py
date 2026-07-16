"""Детерминированный демо-прогон (одна команда, < 3 мин, без сети/ключей).

Запуск: python scripts/run_demo.py
Эквивалент: python -m athanor.cli demo --case examples/demo_case --engine rule
"""
import _bootstrap  # noqa: F401  — кладёт src/ на sys.path
import sys

from athanor.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:] or ["--case", "examples/demo_case", "--engine", "rule"]
    if argv[0] not in {"demo", "run", "approve"}:
        argv = ["demo", *argv]
    raise SystemExit(main(argv))
