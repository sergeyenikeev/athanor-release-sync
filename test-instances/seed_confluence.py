# -*- coding: utf-8 -*-
"""Сидинг реальной Confluence Cloud: создаёт синтетику «Альфа» в пространстве.

Идемпотентно: создаёт пространство (если нет) и 2 страницы с лейблом alpha-demo —
«Release Plan · Альфа» и «Decision Log · Альфа». При повторном запуске
переиспользует существующие alpha-demo страницы.

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


PAGES = [
    {
        "title": "Release Plan · Альфа",
        "storage": (
            "<h1>Release Plan · Альфа</h1>"
            "<p>Целевое окно релиза 03.07 18:00–20:00. Code freeze с 02.07 12:00.</p>"
            "<p>Зависимости: payment-adapter (владелец SRE), partner-api.</p>"
            "<p>Release-notes по APP-412 готовит Разработчик backend.</p>"
        ),
    },
    {
        "title": "Decision Log · Альфа",
        "storage": (
            "<h1>Decision Log · Альфа</h1>"
            "<ul>"
            "<li>26.06: согласовано окно 18:00–20:00 (исключить пятницу по регламенту).</li>"
            "<li>30.06: APP-412 «Миграция схемы оплат» — принято в релиз 03.07.</li>"
            "<li>30.06: APP-521 «Интеграция с партнёром» — готово к релизу, отслеживать partner-api.</li>"
            "</ul>"
        ),
    },
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
            print(f"[reuse page] {page['id']} «{p['title']}»")
            seeded[p["title"]] = page["id"]
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
