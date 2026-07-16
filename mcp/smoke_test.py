"""Smoke-тест MCP-заглушек: initialize + tools/list + tools/call на каждом сервере.

Запуск: сначала `python mcp/serve_all.py` в соседнем терминале, затем
`python mcp/smoke_test.py` (или `make mcp-smoke`). Код выхода 0 = все три отвечают.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from athanor.config import load_config  # noqa: E402
from athanor.sources import McpClient  # noqa: E402


def main() -> int:
    cfg = load_config()
    host = cfg["MCP_HOST"]
    checks = [
        ("calendar_mail", cfg["MCP_CALENDAR_MAIL_PORT"], "get_events", {}),
        ("tracker_repo", cfg["MCP_TRACKER_REPO_PORT"], "get_issues", {}),
        ("transcripts", cfg["MCP_TRANSCRIPTS_PORT"], "get_transcript", {"case_id": "smoke"}),
    ]
    failed = 0
    for name, port, tool, args in checks:
        client = McpClient(f"http://{host}:{port}/mcp")
        try:
            info = client.initialize()
            tools = [t["name"] for t in client.list_tools()]
            data = client.call_tool(tool, args)
            size = len(data) if isinstance(data, (list, str)) else 1
            print(f"OK   {name:<14} server={info['serverInfo']['name']} tools={tools} {tool}→{size} записей")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {name:<14} {e}")
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
