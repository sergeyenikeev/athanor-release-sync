"""MCP-сервер «календарь + почта». Порт 9901.

Коннектор к календарю и почте (Google). Источник данных — через MCP_BACKEND:
  - live (по умолчанию) → Google: Calendar (публичный iCal URL) + mail (IMAP, пароль приложения);
  - test/file → обезличенная выгрузка из MCP_CASE_DIR.
Конвертация «контракт → схема агента» — в mcp/_backends.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpServer, serve  # noqa: E402
import _backends  # noqa: E402

TOOLS = {
    "get_events": (
        {"description": "События календаря по проекту (live→Google iCal; test/file→выгрузка)"},
        _backends.get_events,
    ),
    "get_mail": (
        {"description": "Письма по проекту (live→Google IMAP; test/file→выгрузка)"},
        _backends.get_mail,
    ),
}

server = McpServer("calendar_mail", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_CALENDAR_MAIL_PORT", "9901"))
    print(f"[calendar_mail] MCP server on http://127.0.0.1:{port}/mcp")
    serve(server, port).serve_forever()
