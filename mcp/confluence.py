"""MCP-сервер «Confluence» (release plan / decision log / RFC). Порт 9904.

Коннектор к страницам Confluence. Источник — MCP_BACKEND:
  - live (по умолчанию) → Confluence Cloud (atlassian, CQL по space+label);
  - test → локальный инстанс (:9914, реальный контракт REST API v1);
  - file → обезличенная выгрузка из MCP_CASE_DIR.
Конвертация «контракт Confluence → ConfluencePage» — в mcp/_backends.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpServer, serve  # noqa: E402
import _backends  # noqa: E402

TOOLS = {
    "get_confluence_pages": (
        {
            "description": "Страницы Confluence по релизу (release plan / decision log / RFC). "
            "live→Confluence Cloud (CQL); test→инстанс :9914; file→выгрузка.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "space": {"type": "string", "description": "Ключ пространства (опц., по умолч. из env)"},
                    "label": {"type": "string", "description": "Лейбл фильтра синтетики (опц., по умолч. из env)"},
                },
            },
        },
        _backends.get_confluence_pages,
    ),
}

server = McpServer("confluence", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_CONFLUENCE_PORT", "9904"))
    print(f"[confluence] MCP server on http://127.0.0.1:{port}/mcp")
    serve(server, port).serve_forever()
