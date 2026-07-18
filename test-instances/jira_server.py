"""Локальный тестовый инстанс Jira (REST API v2, контракт Atlassian).

Реальный контракт /rest/api/2/search и /rest/api/2/issue/{key}.
Данные — обезличенная синтетика проекта «Альфа». Порт 9911.

Запуск: python test-instances/jira_server.py
Это тестовый инстанс, не боевая Jira. Смена URL -> реальная Jira/DC.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# синтетика «Альфа» в формате Jira REST v2
ISSUES = [
    {
        "key": "APP-412",
        "fields": {
            "summary": "Миграция на ППРБ",
            "status": {"name": "готово"},
            "assignee": {"displayName": "Разработчик backend"},
            "project": {"key": "ALPHA", "name": "Альфа"},
        },
    },
    {
        "key": "APP-521",
        "fields": {
            "summary": "Интеграция с партнёром",
            "status": {"name": "в работе"},
            "assignee": {"displayName": "Разработчик frontend"},
            "project": {"key": "ALPHA", "name": "Альфа"},
        },
    },
]


def _search(jql: str) -> dict:
    # упрощённый JQL-парсер: поддерживает project=KEY
    proj = None
    if "project=" in jql:
        proj = jql.split("project=")[1].split()[0].strip().strip('"')
    issues = [i for i in ISSUES if not proj or i["fields"]["project"]["key"] == proj.upper()]
    return {
        "expand": "names,schema",
        "startAt": 0,
        "maxResults": 50,
        "total": len(issues),
        "issues": issues,
    }


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
        from urllib.parse import parse_qs
        params = parse_qs(qs)
        if path.startswith("/rest/api/2/issue/"):
            key = path.rstrip("/").split("/")[-1]
            issue = next((i for i in ISSUES if i["key"] == key), None)
            if issue:
                self._json(200, issue)
            else:
                self._json(404, {"errorMessages": [f"Issue {key} does not exist"], "errors": {}})
            return
        if path == "/rest/api/2/search":
            jql = params.get("jql", [""])[0]
            self._json(200, _search(jql))
            return
        if path == "/rest/api/2/serverInfo":
            self._json(200, {"serverTitle": "Athanor Test Jira", "version": "9001.0.0-test",
                             "buildDate": "2026-07-01", "baseUrl": "http://127.0.0.1:9911"})
            return
        self._json(404, {"errorMessages": [f"unknown path {path}"], "errors": {}})

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    import os
    port = int(os.environ.get("TEST_JIRA_PORT", "9911"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[test-jira] REST API v2 on http://127.0.0.1:{port}/rest/api/2  (контракт Atlassian)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
