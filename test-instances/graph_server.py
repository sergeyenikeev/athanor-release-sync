"""Локальный тестовый инстанс Microsoft Graph (Outlook: календарь + почта).

Реальный контракт /v1.0/me/events и /v1.0/me/messages.
Данные — обезличенная синтетика проекта «Альфа». Порт 9912.

Запуск: python test-instances/graph_server.py
Это тестовый инстанс, не боевой Microsoft 365. Смена URL -> реальный Graph.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# синтетика «Альфа» в формате Microsoft Graph
EVENTS = [
    {
        "id": "EVT-DEMO-ALPHA",
        "subject": "Релиз-синк · Альфа",
        "start": {"dateTime": "2026-07-03T14:00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-07-03T15:00:00", "timeZone": "UTC"},
        "location": {"displayName": "Альфа · релизная комната"},
        "attendees": [
            {"emailAddress": {"name": "Тимлид", "address": "timlid@alpha.test"}, "type": "required"},
            {"emailAddress": {"name": "SRE", "address": "sre@alpha.test"}, "type": "required"},
            {"emailAddress": {"name": "Владелец продукта", "address": "po@alpha.test"}, "type": "required"},
            {"emailAddress": {"name": "Разработчик backend", "address": "dev-a@alpha.test"}, "type": "required"},
            {"emailAddress": {"name": "Разработчик frontend", "address": "dev-b@alpha.test"}, "type": "required"},
        ],
        "body": {"contentType": "text", "content": "Релиз-синк проекта Альфа, релиз ALPHA-2026.07"},
    }
]

MESSAGES = [
    {
        "id": "M1",
        "subject": "Блокер по APP-412: payment-adapter не в prod",
        "from": {"emailAddress": {"name": "SRE", "address": "sre@alpha.test"}},
        "receivedDateTime": "2026-07-02T10:00:00Z",
        "body": {"contentType": "text",
                 "content": "APP-412: смежный сервис payment-adapter не задеплоен в production, "
                            "релизное окно под риском, деплой заблокирован."},
    }
]


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict | list) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/v1.0/me/events":
            self._json(200, {"value": EVENTS})
            return
        if path == "/v1.0/me/messages":
            self._json(200, {"value": MESSAGES})
            return
        if path == "/v1.0/$metadata":
            self._json(200, {"name": "Athanor Test Graph", "version": "1.0-test"})
            return
        self._json(404, {"error": {"code": "NotFound", "message": f"unknown path {path}"}})

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    import os
    port = int(os.environ.get("TEST_GRAPH_PORT", "9912"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[test-graph] Microsoft Graph on http://127.0.0.1:{port}/v1.0  (Outlook: календарь + почта)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
