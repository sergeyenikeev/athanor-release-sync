"""MCP-сервер «календарь + почта». Порт 9901.

Коннектор к календарю и почте. Источник данных — через MCP_BACKEND:
  - live (по умолчанию) → Google: Calendar (iCal) + mail (IMAP);
  - microsoft → Outlook.com (Microsoft Graph);
  - test → локальный Graph-инстанс (:9912, реальный контракт);
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
    "get_events": (
        {"description": "События календаря по проекту (live→Google iCal / MS Graph; test→Graph-инстанс; file→выгрузка)"},
        _backends.get_events,
    ),
    "get_mail": (
        {"description": "Письма по проекту (live→Google IMAP / MS Graph; test→Graph-инстанс; file→выгрузка)"},
        _backends.get_mail,
    ),
}

server = McpServer("calendar_mail", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_CALENDAR_MAIL_PORT", "9901"))
    print(f"[calendar_mail] MCP server on http://127.0.0.1:{port}/mcp")
    serve(server, port).serve_forever()
