"""Запуск всех тестовых инстансов в одном процессе (потоки).

  python test-instances/serve_all.py

Порты: Jira 9911 · Bitbucket 9913 · Confluence 9914. Локально, офлайн, без auth.
Контракты реальные (Atlassian Jira REST v2, Bitbucket Cloud REST 2.0,
Confluence Cloud REST API v1), данные — обезличенная синтетика «Альфа». Смена URL -> боевые системы.
Calendar/mail в test-режиме читаются из файла (test-instances/graph больше не используется).
"""
from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

import jira_server
import bitbucket_server
import confluence_server

SERVERS = [
    (jira_server.Handler, 9911, "test-jira"),
    (bitbucket_server.Handler, 9913, "test-bitbucket"),
    (confluence_server.Handler, 9914, "test-confluence"),
]


def main() -> None:
    srvs = []
    for handler, port, name in SERVERS:
        srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
        srvs.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"  {name:<12} http://127.0.0.1:{port}")
    print("Тестовые инстансы подняты (реальные контракты, синтетика Альфа). Ctrl+C — остановка.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for s in srvs:
            s.shutdown()
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
