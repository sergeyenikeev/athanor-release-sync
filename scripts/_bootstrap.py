"""Общий bootstrap: кладёт src/ на sys.path, чтобы скрипты запускались
без `pip install -e .` и без ручного PYTHONPATH. Импортируется первой
строкой любого скрипта в scripts/ и tests/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
