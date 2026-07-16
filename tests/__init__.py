"""Тестовый пакет. При импорте кладёт src/ на sys.path — тесты запускаются
через `python -m unittest discover -s tests -t .` без установки пакета."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
