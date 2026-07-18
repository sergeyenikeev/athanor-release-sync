"""Локальный тестовый инстанс Confluence Cloud (REST API v1, контракт Atlassian).

Реальный контракт /wiki/rest/api/content/search (CQL) + /wiki/rest/api/content/{id}.
Данные — обезличенная синтетика проекта «Альфа». Порт 9914.

Запуск: python test-instances/confluence_server.py
Это тестовый инстанс, не боевой Confluence. Смена URL -> реальная Confluence Cloud.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote

# синтетика «Альфа» в формате Confluence REST API v1 (content/search)
PAGES = [
    {
        "id": "196612",
        "type": "page",
        "status": "current",
        "title": "Release Plan · Альфа",
        "space": {"key": "ALPHA", "name": "Альфа", "type": "global"},
        "version": {
            "number": 3,
            "when": "2026-07-01T09:30:00.000Z",
            "friendlyWhen": "вчера",
        },
        "body": {
            "view": {
                "value": (
                    "<h1>Release Plan · Альфа</h1>"
                    "<p>Целевое окно релиза 03.07 18:00–20:00. Code freeze с 02.07 12:00.</p>"
                    "<p>Зависимости: ППРБ-адаптер (владелец SRE), partner-api.</p>"
                    "<p>Release-notes по APP-412 готовит Разработчик backend.</p>"
                ),
                "representation": "view",
            }
        },
        "_links": {
            "webui": "/spaces/ALPHA/pages/196612/Release+Plan+·+Альфа",
            "base": "http://127.0.0.1:9914/wiki",
        },
    },
    {
        "id": "196613",
        "type": "page",
        "status": "current",
        "title": "Decision Log · Альфа",
        "space": {"key": "ALPHA", "name": "Альфа", "type": "global"},
        "version": {
            "number": 5,
            "when": "2026-06-30T15:00:00.000Z",
            "friendlyWhen": "позавчера",
        },
        "body": {
            "view": {
                "value": (
                    "<h1>Decision Log · Альфа</h1>"
                    "<ul>"
                    "<li>26.06: согласовано окно 18:00–20:00 (исключить пятницу по регламенту).</li>"
                    "<li>30.06: APP-412 «Миграция на ППРБ» — принято в релиз 03.07.</li>"
                    "<li>30.06: APP-521 «Интеграция с партнёром» — готово к релизу, отслеживать partner-api.</li>"
                    "</ul>"
                ),
                "representation": "view",
            }
        },
        "_links": {
            "webui": "/spaces/ALPHA/pages/196613/Decision+Log+·+Альфа",
            "base": "http://127.0.0.1:9914/wiki",
        },
    },
]


def _cql_match(cql: str) -> list[dict]:
    """Упрощённый CQL-парсер: поддерживает space="KEY" AND label="alpha-demo"."""
    cql = unquote(cql or "")
    space = None
    label = None
    # space="ALPHA" или space=ALPHA
    import re
    m = re.search(r'space\s*=\s*"?([A-Za-z0-9_-]+)"?', cql, re.IGNORECASE)
    if m:
        space = m.group(1)
    m = re.search(r'label\s*=\s*"?([A-Za-z0-9_-]+)"?', cql, re.IGNORECASE)
    if m:
        label = m.group(1)
    out = []
    for p in PAGES:
        if space and p["space"]["key"].upper() != space.upper():
            continue
        # лейбл в тестовом инстансе не хранится явно — считаем, что все Alpha-страницы
        # несут лейбл alpha-demo (синтетика демо-контура)
        if label and label.lower() != "alpha-demo":
            continue
        out.append(p)
    return out


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict | list) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Atlassian-Token", "no-check")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        params = parse_qs(qs)
        # /wiki/rest/api/content/search?cql=...
        if path == "/wiki/rest/api/content/search":
            cql = params.get("cql", [""])[0]
            results = _cql_match(cql)
            self._json(200, {
                "results": results,
                "start": 0, "limit": 25, "size": len(results),
                "_links": {"base": "http://127.0.0.1:9914/wiki", "context": "/wiki"},
            })
            return
        # /wiki/rest/api/content/{id}?expand=...
        if path.startswith("/wiki/rest/api/content/"):
            cid = path.rstrip("/").split("/")[-1]
            page = next((p for p in PAGES if str(p["id"]) == str(cid)), None)
            if page:
                self._json(200, page)
            else:
                self._json(404, {"statusCode": 404, "message": f"No content with id {cid}"})
            return
        # /wiki/rest/api/space — список пространств
        if path == "/wiki/rest/api/space":
            spaces = [{"key": p["space"]["key"], "name": p["space"]["name"],
                       "type": p["space"]["type"]} for p in PAGES]
            uniq = {s["key"]: s for s in spaces}.values()
            self._json(200, {"results": list(uniq), "size": len(list(uniq)),
                             "_links": {"base": "http://127.0.0.1:9914/wiki"}})
            return
        self._json(404, {"statusCode": 404, "message": f"unknown path {path}"})

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    import os
    port = int(os.environ.get("TEST_CONFLUENCE_PORT", "9914"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[test-confluence] REST API v1 on http://127.0.0.1:{port}/wiki/rest/api  (контракт Atlassian)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
