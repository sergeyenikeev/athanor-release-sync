# -*- coding: utf-8 -*-
"""Сидинг реальной Confluence Cloud: создаёт синтетику «Альфа» в пространстве.

Идемпотентно: создаёт пространство (если нет) и 2 страницы с лейблом alpha-demo —
«Release Plan · Альфа» и «Decision Log · Альфа». При повторном запуске обновляет
тело существующих alpha-demo страниц (PUT + инкремент версии), переиспользуя
пространство и id страниц — поэтому повторный сид пушит новый контент в Cloud.

Запуск: python test-instances/seed_confluence.py
Требует .env: CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN
              (можно переиспользовать JIRA_EMAIL/JIRA_API_TOKEN — тот же Atlassian API-токен),
              CONFLUENCE_SPACE (по умолч. ALPHA), CONFLUENCE_LABEL (по умолч. alpha-demo).
Выход: печатает id страниц + results/confluence_seeded.json (нужно для live-кейса).

Контракты Confluence Cloud REST API v1:
  GET  /wiki/rest/api/space/{key}                       — проверить пространство
  POST /wiki/rest/api/space                             — создать пространство
  GET  /wiki/rest/api/content/search?cql=space=KEY AND label="alpha-demo"
  POST /wiki/rest/api/content                           — создать страницу
  PUT  /wiki/rest/api/content/{id}                      — обновить тело (version+1)
  POST /wiki/rest/api/content/{id}/label                — добавить лейбл
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip() if " #" in v else v.strip()
        os.environ.setdefault(k.strip(), v)


_load_env(REPO / ".env")


def _cfg():
    url = os.environ.get("CONFLUENCE_URL", "https://<your-tenant>.atlassian.net").rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("JIRA_API_TOKEN", "")
    space = os.environ.get("CONFLUENCE_SPACE", "ALPHA")
    label = os.environ.get("CONFLUENCE_LABEL", "alpha-demo")
    if not email or not token:
        sys.exit("CONFLUENCE_EMAIL/CONFLUENCE_API_TOKEN не заданы в .env "
                 "(можно переиспользовать JIRA_EMAIL/JIRA_API_TOKEN — тот же Atlassian API-токен)")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json",
               "Content-Type": "application/json"}
    return url, headers, space, label


def _req(method, url, headers, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:600]}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


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
    {"title": "Release Plan · Альфа", "storage": RELEASE_PLAN_HTML},
    {"title": "Decision Log · Альфа", "storage": DECISION_LOG_HTML},
]


def main():
    url, headers, space, label = _cfg()
    personal = space.startswith("~") if space else False
    print(f"=== Сидинг Confluence Cloud: {url} · space={space or '<личное/label-only>'} "
          f"· label={label} ===\n")

    # 1) пространство (личные '~…' через API не создаются — они уже есть; при пустом
    #    space страницы разместятся в личном пространстве пользователя по умолчанию)
    if not space:
        print("[space] не задан — страницы будут созданы в личном пространстве пользователя")
    elif personal:
        # GET /space/~… таймаутит на ~… в пути (CDN/SSL) — проверяем через список
        # личных пространств (GET /space?type=personal), который работает.
        s, body = _req("GET", f"{url}/wiki/rest/api/space?limit=25&type=personal", headers)
        found = None
        if s == 200:
            for sp in body.get("results", []):
                if sp.get("key") == space:
                    found = sp
                    break
        if found:
            print(f"[reuse personal space] {space} ({found.get('name','')})")
        else:
            sys.exit(f"[get personal space FAILED] HTTP {s} {body}\n"
                     "  Личное пространство создаётся пользователем в UI (Profile → Personal space).")
    else:
        s, body = _req("GET", f"{url}/wiki/rest/api/space/{urllib.parse.quote(space, safe='')}",
                       headers)
        if s == 404:
            s2, body2 = _req("POST", f"{url}/wiki/rest/api/space", headers, {
                "key": space, "name": "Альфа (демо Ouroboros)",
                "description": {"plain": {"value": "Синтетика «Альфа» (демо-контур Ouroboros). Не рабочее пространство."}},
            })
            if s2 in (200, 201):
                print(f"[create space] {space}")
            else:
                sys.exit(f"[create space FAILED] HTTP {s2} {body2}\n"
                         "  Создайте пространство вручную в UI (Space key должен быть уникальным на сайте) "
                         "и запустите seeder снова.")
        elif s != 200:
            sys.exit(f"[get space FAILED] HTTP {s} {body}")
        else:
            print(f"[reuse space] {space}")

    # 2) существующие alpha-demo страницы (для личного/пустого space — только по лейблу:
    #    CQL-парсер Confluence не принимает space="~…")
    if space and not personal:
        cql = f'space="{space}" AND label="{label}"'
    else:
        cql = f'label="{label}"'
    s, body = _req("GET", f"{url}/wiki/rest/api/content/search?cql={urllib.parse.quote(cql)}"
                   "&expand=version", headers)
    existing = {}
    if s == 200:
        for p in body.get("results", []):
            existing[p["title"]] = p
        print(f"[search] найдено {len(existing)} alpha-demo страниц")
    else:
        print(f"[search] HTTP {s} {body} — продолжим, попробуем создать")

    # 3) создаём недостающие страницы + вешаем лейбл
    # при пустом space — определим личное пространство пользователя (type=personal)
    page_space = space
    if not page_space:
        s, body = _req("GET", f"{url}/wiki/rest/api/space?limit=25&type=personal", headers)
        if s == 200:
            for sp in body.get("results", []):
                if sp.get("type") == "personal":
                    page_space = sp["key"]
                    print(f"[discover] личное пространство: {page_space} ({sp.get('name','')})")
                    break
        if not page_space:
            sys.exit("Не задан CONFLUENCE_SPACE и личное пространство не найдено. "
                     "Создайте его в UI (Profile → Personal space) или укажите CONFLUENCE_SPACE.")
    seeded = {}
    for p in PAGES:
        if p["title"] in existing:
            page = existing[p["title"]]
            pid = str(page["id"])
            cur_ver = int((page.get("version") or {}).get("number", 1) or 1)
            # Обновляем тело существующей страницы (PUT + инкремент версии), чтобы
            # повторный сид пусшил новый контент в реальную Cloud (иначе страница
            # переиспользуется как есть, со старым коротким телом).
            s2, body2 = _req("PUT", f"{url}/wiki/rest/api/content/{pid}", headers, {
                "id": pid,
                "type": "page",
                "title": p["title"],
                "body": {"storage": {"value": p["storage"], "representation": "storage"}},
                "version": {"number": cur_ver + 1},
            })
            if s2 in (200, 201):
                print(f"[update page] {pid} «{p['title']}» v{cur_ver}→{cur_ver + 1}")
            else:
                print(f"[update page FAILED] {pid} «{p['title']}»: HTTP {s2} {body2}")
            seeded[p["title"]] = pid
            continue
        s2, body2 = _req("POST", f"{url}/wiki/rest/api/content", headers, {
            "type": "page",
            "title": p["title"],
            "space": {"key": page_space},
            "body": {"storage": {"value": p["storage"], "representation": "storage"}},
        })
        if s2 in (200, 201):
            pid = str(body2["id"])
            print(f"[create page] {pid} «{p['title']}»")
            # лейбл
            s3, body3 = _req("POST", f"{url}/wiki/rest/api/content/{pid}/label", headers,
                             [{"prefix": "global", "name": label}])
            if s3 in (200, 201):
                print(f"[label] {pid} ← {label}")
            else:
                print(f"[label FAILED] {pid}: HTTP {s3} {body3}")
            seeded[p["title"]] = pid
        else:
            print(f"[create page FAILED] «{p['title']}»: HTTP {s2} {body2}")

    # 4) финальная проверка
    print(f"\n=== Итог (alpha-demo страницы, space={space or page_space}) ===")
    s, body = _req("GET", f"{url}/wiki/rest/api/content/search?cql={urllib.parse.quote(cql)}"
                   "&expand=version,space", headers)
    if s == 200:
        for p in body.get("results", []):
            spk = (p.get("space") or {}).get("key", "")
            print(f"  {p['id']}\t{p['title']}\t[space={spk}]")
    out = HERE.parent / "results" / "confluence_seeded.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "space": space, "label": label, "url": url, "pages": seeded,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out}")
    print(f"\nПрогон через реальную Confluence Cloud:")
    print(f"  MCP_BACKEND_CONFLUENCE=atlassian python mcp/serve_all.py   # терминал 1")
    print(f"  MCP_BACKEND_CONFLUENCE=atlassian python -m athanor.cli run "
          f"--case examples/demo_case_alpha --via-mcp --engine rule --print")


if __name__ == "__main__":
    main()
