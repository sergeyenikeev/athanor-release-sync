"""MCP-сервер «расшифровки встреч». Порт 9903.

Расшифровки — локальные файлы кейса (MCP_CASE_DIR/input/transcript.txt):
это исходный источник, внешнего API расшифровок нет. Для кейса TB-11
(недоступный источник) сервер запускается с MCP_TRANSCRIPTS_DOWN=1 и
отвечает ошибкой — клиент обязан деградировать без падения («данные
неполны»), это проверяется корзиной.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import McpServer, case_dir, serve  # noqa: E402


def get_transcript(case_id: str = "") -> str:
    if os.environ.get("MCP_TRANSCRIPTS_DOWN", "0") == "1":
        raise RuntimeError("transcripts source is down (simulated outage)")
    path = case_dir() / "input" / "transcript.txt"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


TOOLS = {
    "get_transcript": (
        {
            "description": "Расшифровка релиз-синка (обезличенная, из файлов кейса)",
            "inputSchema": {
                "type": "object",
                "properties": {"case_id": {"type": "string", "description": "ID кейса (опц.)"}},
            },
        },
        get_transcript,
    ),
}

server = McpServer("transcripts", TOOLS)

if __name__ == "__main__":
    port = int(os.environ.get("MCP_TRANSCRIPTS_PORT", "9903"))
    print(f"[transcripts] MCP server on http://127.0.0.1:{port}/mcp")
    serve(server, port).serve_forever()
