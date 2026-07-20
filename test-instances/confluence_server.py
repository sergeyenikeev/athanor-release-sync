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

# синтетика «Альфа» в формате Confluence REST API v1 (content/search).
# HTML-тело страниц синхронизировано с test-instances/seed_confluence.py (storage),
# чтобы файловый, тестовый (:9914) и боевой (atlassian) контуры отдавали
# одинаковый контент страниц. Обновлять тело — в обоих файлах одновременно.
RELEASE_PLAN_HTML = (
    "<h1>Release Plan · Альфа</h1>"
    "<p>Релиз ALPHA-2026.07, окно 03.07 18:00–20:00 МСК, code freeze с "
    "02.07 12:00. В скоуп: APP-412 «Миграция на ППРБ», APP-521 «Интеграция с "
    "партнёром». Зависимости: ППРБ-адаптер (владелец SRE), partner-api. "
    "Release-notes по APP-412 готовит Разработчик backend.</p>"
    "<h2>Параметры релиза</h2>"
    "<p>Release-менеджер — Тимлид (backend). Окно согласовано на релиз-синке "
    "26.06 (см. Decision Log · Альфа): пятница исключена по регламенту заморозки "
    "банка. Точка невозврата — 03.07 19:30.</p>"
    "<h2>Скоуп релиза</h2>"
    "<table><tbody>"
    "<tr><th>Задача</th><th>Название</th><th>Исполнитель</th>"
    "<th>Release-notes</th><th>Источник</th></tr>"
    "<tr><td>APP-412</td><td>Миграция на ППРБ</td><td>Разработчик backend</td>"
    "<td>да, готовит backend</td><td>Jira · Decision Log 30.06</td></tr>"
    "<tr><td>APP-521</td><td>Интеграция с партнёром</td><td>Разработчик frontend</td>"
    "<td>да</td><td>Jira · Decision Log 30.06</td></tr>"
    "</tbody></table>"
    "<h2>Зависимости</h2>"
    "<ul>"
    "<li><strong>ППРБ-адаптер (payment-adapter)</strong> — владелец SRE; должен быть "
    "развёрнут в предпроде до 02.07 18:00. Без адаптера релиз не проходит дымные "
    "тесты платёжной схемы.</li>"
    "<li><strong>partner-api</strong> — смежная команда «Партнёры»; отслеживать "
    "доступность стенда и контракт v2 до 03.07 12:00.</li>"
    "</ul>"
    "<h2>План релиза</h2>"
    "<ol>"
    "<li>02.07 12:00 — code freeze, открыт hotfix-branch.</li>"
    "<li>02.07 18:00 — развёртывание ППРБ-адаптера в предпрод (SRE).</li>"
    "<li>03.07 11:00 — релиз-синк: подтверждение готовности, сверка зависимостей "
    "и статусов Jira/PR.</li>"
    "<li>03.07 18:00 — выкатка в прод.</li>"
    "<li>03.07 19:00 — дымные тесты и мониторинг метрик.</li>"
    "<li>03.07 20:00 — закрытие окна или откат по решению Release-менеджера.</li>"
    "</ol>"
    "<h2>Критерии готовности</h2>"
    "<ul>"
    "<li>Все задачи скоупа в статусе «Готово» в Jira; PR слиты и закрыты в Bitbucket.</li>"
    "<li>ППРБ-адаптер развёрнут в предпроде, дымные тесты платёжной схемы зелёные.</li>"
    "<li>Release-notes опубликованы в Confluence, ссылка есть в релиз-синке.</li>"
    "<li>Дежурный SRE подтверждает готовность к выкатке в чате «Альфа · релизы».</li>"
    "</ul>"
    "<h2>Откат</h2>"
    "<p>При критической ошибке в течение 30 минут после выкатки — rollback на "
    "предыдущую версию через hotfix-branch. Решение принимает Release-менеджер по "
    "согласованию с SRE и Владельцем продукта. Точка невозврата — 03.07 19:30; "
    "после неё откат только по согласованию с Владельцем продукта.</p>"
    "<h2>Риски</h2>"
    "<ul>"
    "<li>ППРБ-адаптер не развёрнут к началу окна → сдвиг выкатки на 24 часа.</li>"
    "<li>Конфликт статусов Jira/PR/почты (задача «готово», но письмо сообщает о "
    "блокере) → сверка на релиз-синке 03.07; приоритет Git/Jira выше переписки.</li>"
    "<li>Попадание релиза в окно заморозки платежей — открытый вопрос к SRE "
    "(см. Decision Log · Альфа).</li>"
    "</ul>"
    "<h2>Каналы связи</h2>"
    "<p>Координация — корпоративный чат «Альфа · релизы». Эскалация — Тимлид → "
    "Владелец продукта. Статусы задач — Jira, проект APP. Pull-запросы — "
    "Bitbucket, репозиторий alpha-backend. Расшифровки синков — в папке релиза.</p>"
)

DECISION_LOG_HTML = (
    "<h1>Decision Log · Альфа</h1>"
    "<p>26.06: согласовано окно 18:00–20:00 (пятница исключена по регламенту). "
    "30.06: APP-412 «Миграция на ППРБ» — принято в релиз 03.07. 30.06: APP-521 "
    "«Интеграция с партнёром» — готово к релизу, отслеживать partner-api. 01.07: "
    "release-notes по APP-412 готовит Разработчик backend.</p>"
    "<h2>Назначение журнала</h2>"
    "<p>Журнал решений проекта «Альфа». Каждое решение фиксируется с датой, "
    "владельцем и обоснованием, чтобы на релиз-синках не возвращаться к уже "
    "принятым вопросам и сохранять причины (а не только итог). Страница "
    "дополняет Release Plan · Альфа.</p>"
    "<h2>Принятые решения</h2>"
    "<table><tbody>"
    "<tr><th>Дата</th><th>Решение</th><th>Владелец</th>"
    "<th>Обоснование</th><th>Статус</th></tr>"
    "<tr><td>26.06</td><td>Окно релиза 03.07 18:00–20:00; пятница исключена по "
    "регламенту заморозки</td><td>Тимлид</td><td>Регламент банка: пятница — день "
    "заморозки, выкатка в прод запрещена</td><td>действует</td></tr>"
    "<tr><td>30.06</td><td>APP-412 «Миграция на ППРБ» — принято в релиз 03.07</td>"
    "<td>Владелец продукта</td><td>Блокер миграции платёжной схемы; перенос на "
    "следующий спринт недопустим</td><td>действует</td></tr>"
    "<tr><td>30.06</td><td>APP-521 «Интеграция с партнёром» — готово к релизу, "
    "отслеживать partner-api</td><td>Владелец продукта</td><td>Контракт v2 "
    "согласован; остаточный риск — готовность смежного стенда</td>"
    "<td>действует, под контролем</td></tr>"
    "<tr><td>01.07</td><td>Release-notes по APP-412 готовит Разработчик backend</td>"
    "<td>Тимлид</td><td>Автор миграции — лучший кандидат описать изменения и откат</td>"
    "<td>действует</td></tr>"
    "</tbody></table>"
    "<h2>Открытые вопросы</h2>"
    "<ul>"
    "<li>Попадает ли релиз 03.07 в окно заморозки платежей? — уточнить у SRE до "
    "релиз-синка 03.07.</li>"
    "<li>Готовность partner-api на стенде предпрода — подтвердить смежной команде "
    "«Партнёры» до 03.07 12:00.</li>"
    "<li>Нужен ли откат partner-api вместе с основным релизом — определить на "
    "релиз-синке.</li>"
    "</ul>"
    "<h2>История изменений страницы</h2>"
    "<ul>"
    "<li>v5 (30.06): добавлены решения 30.06 по APP-412 и APP-521.</li>"
    "<li>v4 (28.06): зафиксировано окно релиза 03.07 18:00–20:00.</li>"
    "<li>v3 (26.06): создана страница, записан регламент пятницы.</li>"
    "</ul>"
)

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
                "value": RELEASE_PLAN_HTML,
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
                "value": DECISION_LOG_HTML,
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
