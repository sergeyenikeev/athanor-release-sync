"""MCP-заглушка «трекер + репозиторий» (имитация Jira/Git-выгрузки). Порт 9902."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpStub, read_case_json, serve  # noqa: E402

TOOLS = {
    "get_issues": (
        {"description": "Задачи трекера по релизу (обезличенная выгрузка Jira)"},
        lambda: read_case_json("tracker.json", "issues"),
    ),
    "get_prs": (
        {"description": "Pull Request-ы по релизу (обезличенная выгрузка Git)"},
        lambda: read_case_json("tracker.json", "prs"),
    ),
}

stub = McpStub("tracker_repo", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_TRACKER_REPO_PORT", "9902"))
    print(f"[tracker_repo] MCP stub on http://127.0.0.1:{port}/mcp")
    serve(stub, port).serve_forever()
