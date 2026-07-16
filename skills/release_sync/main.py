"""Entry-скрипт навыка release_sync для Ouroboros (type: script).

Ouroboros вызывает его в рабочем пространстве; аргументы:
  main.py --case <папка кейса> [--engine llm|rule] [--format v1|v2]
Скрипт печатает markdown-результат в stdout — Ouroboros показывает его в чате.
Вся логика — в пакете athanor (src/), навык лишь управляет циклом.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from athanor.cli import main  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] not in {"run", "approve"}:
        argv = ["run", *argv, "--print"]
    raise SystemExit(main(argv))
