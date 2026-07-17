"""MCP-сервер «трекер + репозиторий». Порт 9902.

Коннектор к задачам (Jira) и pull request-ам (Bitbucket). Источник — MCP_BACKEND:
  - live (по умолчанию) → Jira Cloud (atlassian) + Bitbucket Cloud (bitbucket);
  - test → локальные инстансы Jira (:9911) + Bitbucket (:9913);
  - file → обезличенная выгрузка из MCP_CASE_DIR.
Конвертация «контракт → схема агента» — в mcp/_backends.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpServer, serve  # noqa: E402
import _backends  # noqa: E402

TOOLS = {
    "get_issues": (
        {"description": "Задачи трекера по релизу (live→Jira Cloud; test→Jira-инстанс; file→выгрузка)"},
        _backends.get_issues,
    ),
    "get_prs": (
        {"description": "Pull Request-ы по релизу (live→Bitbucket Cloud; test→Bitbucket-инстанс; file→выгрузка)"},
        _backends.get_prs,
    ),
}

server = McpServer("tracker_repo", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_TRACKER_REPO_PORT", "9902"))
    print(f"[tracker_repo] MCP server on http://127.0.0.1:{port}/mcp")
    serve(server, port).serve_forever()
