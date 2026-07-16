"""Запуск всех тестов одной командой (unittest, без внешних зависимостей).

Запуск:
  python scripts/run_tests.py            # все тесты
  python scripts/run_tests.py -v         # детально
Эквивалент: python -m unittest discover -s tests -t .
"""
import _bootstrap  # noqa: F401
import sys
import unittest

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py", top_level_dir=".")
    runner = unittest.TextTestRunner(verbosity=2 if "-v" in sys.argv else 1)
    result = runner.run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
