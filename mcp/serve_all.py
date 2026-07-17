"""Запуск всех четырёх MCP-серверов в одном процессе (потоки).

  python mcp/serve_all.py                      # MCP_BACKEND=live → реальные сервисы
  MCP_CASE_DIR=test-basket/TB-03 python mcp/serve_all.py
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _base import case_dir, serve  # noqa: E402
import calendar_mail  # noqa: E402
import tracker_repo  # noqa: E402
import transcripts  # noqa: E402
import confluence  # noqa: E402

SERVERS = [
    (calendar_mail.server, int(os.environ.get("MCP_CALENDAR_MAIL_PORT", "9901"))),
    (tracker_repo.server, int(os.environ.get("MCP_TRACKER_REPO_PORT", "9902"))),
    (transcripts.server, int(os.environ.get("MCP_TRANSCRIPTS_PORT", "9903"))),
    (confluence.server, int(os.environ.get("MCP_CONFLUENCE_PORT", "9904"))),
]


def main() -> None:
    print(f"Папка кейса (transcripts/file-fallback): {case_dir()}")
    servers = []
    for server, port in SERVERS:
        srv = serve(server, port)
        servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"  {server.name:<14} http://127.0.0.1:{port}/mcp")
    print("MCP-серверы подняты. Ctrl+C — остановка.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for srv in servers:
            srv.shutdown()
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
