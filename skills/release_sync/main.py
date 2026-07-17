"""Entry-скрипт навыка release_sync для Ouroboros (type: script).

Ouroboros вызывает его в рабочем пространстве; аргументы:
  main.py --case <папка кейса> [--engine llm|rule] [--format v1|v2]
Скрипт печатает markdown-результат в stdout — Ouroboros показывает его в чате.
Вся логика — в пакете athanor (src/ репозитория athanor-release-sync); навык
лишь управляет циклом.

Layout: навык живёт внутри checkout athanor-release-sync/skills/release_sync/,
поэтому athanor разрешается через parents[2]/src. Запасные стратегии
(env OUROBOROS_SKILLS_REPO_PATH, уже на sys.path) покрывают установку вне
checkout. Импорт athanor лежит вне reviewed skill_dir — сознательное
архитектурное решение для contest MVP (навык = интерфейс над движком athanor
в одном репозитории); см. review_rebuttal к findingам path_confinement.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent


def _resolve_athanor_src() -> Path | None:
    """Найти каталог src/ с пакетом athanor. Возвращает путь или None.

    Layout checkout: skills/release_sync/main.py → SKILL_DIR.parents[1]/src
    (parents[1] = корень athanor-release-sync, где лежит src/athanor).
    """
    candidates: list[Path] = []
    if len(SKILL_DIR.parents) >= 2:
        candidates.append(SKILL_DIR.parents[1] / "src")
    repo_env = os.environ.get("OUROBOROS_SKILLS_REPO_PATH", "").strip()
    if repo_env:
        candidates.append(Path(repo_env) / "src")
        candidates.append(Path(repo_env).parent / "src")
    for cand in candidates:
        if (cand / "athanor" / "cli.py").is_file():
            return cand
    return None


def _fail(message: str) -> int:
    print(f"⚠️ release_sync: {message}", file=sys.stderr)
    return 2


_MCP_PORTS = {"calendar_mail": 9901, "tracker_repo": 9902, "transcripts": 9903, "confluence": 9904}


def _preflight_mcp() -> str | None:
    """Дешёвая проверка MCP-эндпоинтов 127.0.0.1:9901-9904 (только для --via-mcp)."""
    import socket
    down: list[str] = []
    for name, port in _MCP_PORTS.items():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                pass
        except OSError:
            down.append(f"{name}:{port}")
    if down:
        return ("MCP-эндпоинты недоступны: " + ", ".join(down)
                + ". Поднимите серверы (python mcp/serve_all.py) или уберите --via-mcp "
                "для file-режима (выгрузка из test-basket/input/).")
    return None


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] not in {"run", "approve"}:
        argv = ["run", *argv, "--print"]

    src_dir = _resolve_athanor_src()
    if src_dir is not None and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    try:
        from athanor.cli import main as cli_main  # noqa: E402
    except ImportError:
        return _fail(
            "пакет athanor не найден. Навык рассчитан на layout checkout "
            "athanor-release-sync (skills/release_sync/main.py → ../src/athanor) "
            "или env OUROBOROS_SKILLS_REPO_PATH. Проверьте, что репозиторий "
            "athanor-release-sync доступен и src/athanor/ существует."
        )

    if argv[:1] == ["run"]:
        for i, a in enumerate(argv):
            if a == "--case" and i + 1 < len(argv) and not Path(argv[i + 1]).is_dir():
                return _fail(f"кейс не найден: {argv[i + 1]}")
        if "--via-mcp" in argv:
            mcp_err = _preflight_mcp()
            if mcp_err is not None:
                return _fail(mcp_err)

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
