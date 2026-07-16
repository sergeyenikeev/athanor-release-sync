"""MCP-заглушка «календарь + почта» (имитация Outlook-выгрузки). Порт 9901."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpStub, read_case_json, serve  # noqa: E402

TOOLS = {
    "get_events": (
        {"description": "События календаря (обезличенная выгрузка): релиз-синки, разборы инцидентов"},
        lambda: read_case_json("calendar.json", "events"),
    ),
    "get_mail": (
        {"description": "Письма по проекту (обезличенная выгрузка): статусы, блокеры, вопросы"},
        lambda: read_case_json("mail.json", "messages"),
    ),
}

stub = McpStub("calendar_mail", TOOLS)

if __name__ == "__main__":
    import os

    port = int(os.environ.get("MCP_CALENDAR_MAIL_PORT", "9901"))
    print(f"[calendar_mail] MCP stub on http://127.0.0.1:{port}/mcp")
    serve(stub, port).serve_forever()
