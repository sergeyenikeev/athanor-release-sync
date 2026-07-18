"""Локальный тестовый инстанс Bitbucket Cloud (REST API 2.0, контракт Bitbucket).

Реальный контракт /repositories/{workspace}/{repo_slug}/pullrequests.
Данные — обезличенная синтетика проекта «Альфа». Порт 9913.

Запуск: python test-instances/bitbucket_server.py
Это тестовый инстанс, не боевой Bitbucket. Смена URL -> реальный Bitbucket Cloud.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# синтетика «Альфа» в формате Bitbucket Cloud REST 2.0 (pull request)
PRS = [
    {
        "id": 128,
        "title": "Миграция на ППРБ",
        "state": "OPEN",
        "created_on": "2026-06-30T10:00:00Z",
        "updated_on": "2026-07-02T09:00:00Z",
        "author": {"nickname": "Разработчик backend", "display_name": "Разработчик backend"},
        "source": {"branch": {"name": "feature/pprb-migration"},
                   "repository": {"name": "alpha", "full_name": "athanor/alpha"}},
        "destination": {"branch": {"name": "main"},
                        "repository": {"name": "alpha", "full_name": "athanor/alpha"}},
        "summary": {"raw": "PR по APP-412: миграция на ППРБ", "markup": "markdown"},
        "comment_count": 2,
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
        if path.endswith("/pullrequests"):
            # /repositories/{workspace}/{repo_slug}/pullrequests
            self._json(200, {"pagelen": 10, "size": len(PRS), "page": 1, "values": PRS})
            return
        self._json(404, {"type": "error", "error": {"message": "Not Found"}})

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    import os
    port = int(os.environ.get("TEST_BITBUCKET_PORT", "9913"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[test-bitbucket] REST API 2.0 on http://127.0.0.1:{port}/repositories/athanor/alpha  (контракт Bitbucket Cloud)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
