# -*- coding: utf-8 -*-
"""Прямое переименование сущностей по явным ключам (Jira/BB/Conf) — без search.

Jira: PUT /rest/api/2/issue/{key} с fields.summary.
Bitbucket: PUT /pullrequests/{id} с title+summary.
Confluence: PUT /content/{id} с title+body.storage (version+1).

Сеть Atlassian/Bitbucket нестабильна — каждую сущность пробиваем с retry.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())


def _req(method, url, headers, body=None, timeout=20, retries=6, backoff=2.0):
    data = None
    h = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                try:
                    raw = r.read().decode("utf-8")
                except Exception:
                    raw = ""
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            try:
                err = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                err = f"<HTTP {e.code} {e.reason}>"
            return e.code, {"error": err}
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    return -1, {"error": f"{type(last).__name__}: {last}"}


# ============================================================ Jira
def jira_put_summary(key, new_summary):
    url = os.environ["JIRA_URL"].rstrip("/")
    creds = base64.b64encode(f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()).decode()
    H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    s, body = _req("PUT", f"{url}/rest/api/2/issue/{key}", H, {"fields": {"summary": new_summary}})
    return s, body


def rename_jira_direct():
    print("\n=== Jira: прямое переименование summary ===")
    renames = [
        ("KAN-1", "Миграция на ППРБ"),
        ("APP-1", "Миграция на ППРБ"),
        ("APP-3", "Репликация ППРБ"),
        ("APP-4", "Кэш ППРБ"),
        ("APP-5", "Вебхуки ППРБ"),
        ("APP-6", "Реестр ППРБ"),
        ("OPS-1", "Деплой ППРБ-адаптера"),
        ("OPS-4", "Мониторинг ППРБ-адаптера"),
        ("OPS-6", "Мониторинг ППРБ-адаптера"),
    ]
    for key, new_sum in renames:
        s, body = jira_put_summary(key, new_sum)
        ok = s in (200, 204)
        print(f"  [{'OK' if ok else 'FAIL'}] {key} → «{new_sum}» (HTTP {s})")
        if not ok:
            print(f"       {body}")


# ============================================================ Bitbucket
def bb_put_pr(pid, title, summary_raw):
    ws = os.environ["BITBUCKET_WORKSPACE"]
    slug = os.environ["BITBUCKET_REPO_SLUG"]
    ws_token = os.environ.get("BITBUCKET_WORKSPACE_TOKEN", "")
    if ws_token:
        H = {"Authorization": f"Bearer {ws_token}", "Accept": "application/json"}
    else:
        creds = base64.b64encode(f"{os.environ['BITBUCKET_EMAIL']}:{os.environ['BITBUCKET_API_TOKEN']}".encode()).decode()
        H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    payload = {"title": title, "summary": {"raw": summary_raw}}
    return _req("PUT", f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/pullrequests/{pid}", H, payload)


def rename_bitbucket_direct():
    print("\n=== Bitbucket: прямое переименование PR ===")
    # PR #1..#10: title + summary (issue_key — реальный jira_key из basket_seeded)
    renames = [
        (1, "Миграция на ППРБ", "PR по APP-412: миграция на ППРБ (демо Ouroboros)"),
        (2, "Репликация ППРБ", "PR по APP-3: репликация ППРБ (демо корзина Ouroboros, TB-09). Связан с Jira-задачей APP-3 «Репликация ППРБ» (проект APP, Cloud)."),
        (3, "Вебхуки ППРБ", "PR по APP-413: вебхуки ППРБ (демо Ouroboros)"),
        (4, "Кэш ППРБ", "PR по APP-410: кэш ППРБ (демо Ouroboros)"),
        (5, "Метрики бизнес-операций", "PR по APP-430: метрики бизнес-операций (демо Ouroboros)"),
        (6, "Реестр ППРБ", "PR по APP-422: реестр ППРБ (демо Ouroboros)"),
        (7, "Мониторинг ППРБ-адаптера", "PR по OPS-79: мониторинг ППРБ-адаптера (демо Ouroboros)"),
        (8, "Runbook релизов", "PR по OPS-80: runbook релизов Альфа (демо Ouroboros)"),
        (9, "Postmortem 2026-06-30", "PR по OPS-2: postmortem инцидента 2026-06-30 (демо Ouroboros)"),
        (10, "Архитектура ППРБ v2", "PR по APP-1: архитектура ППРБ v2 (демо Ouroboros)"),
    ]
    for pid, title, summary in renames:
        s, body = bb_put_pr(pid, title, summary)
        ok = s in (200, 201)
        print(f"  [{'OK' if ok else 'FAIL'}] PR #{pid}: «{title}» (HTTP {s})")
        if not ok:
            print(f"       {body}")


# ============================================================ Confluence
def conf_put_page(pid, new_title, new_storage, version_num):
    url = os.environ["CONFLUENCE_URL"].rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ["JIRA_EMAIL"]
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ["JIRA_API_TOKEN"]
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    space = os.environ.get("CONFLUENCE_SPACE", "")
    payload = {
        "id": pid, "type": "page", "title": new_title,
        "space": {"key": space},
        "body": {"storage": {"value": new_storage, "representation": "storage"}},
        "version": {"number": int(version_num) + 1},
    }
    return _req("PUT", f"{url}/wiki/rest/api/content/{pid}", H, payload)


def conf_get_page(pid):
    url = os.environ["CONFLUENCE_URL"].rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ["JIRA_EMAIL"]
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ["JIRA_API_TOKEN"]
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    s, body = _req("GET", f"{url}/wiki/rest/api/content/{pid}?expand=version,body.storage,space", H)
    return s, body


# Новые storage-тела для страниц с платежами
CONF_NEW = {
    "425985": ("Release Plan · Альфа",
        "<h1>Release Plan · Альфа</h1>"
        "<p>Целевое окно релиза 03.07 18:00–20:00. Code freeze с 02.07 12:00.</p>"
        "<p>Зависимости: ППРБ-адаптер (владелец SRE), partner-api.</p>"
        "<p>Release-notes по APP-412 готовит Разработчик backend.</p>"),
    "458753": ("Decision Log · Альфа",
        "<h1>Decision Log · Альфа</h1>"
        "<ul>"
        "<li>26.06: согласовано окно 18:00–20:00 (исключить пятницу по регламенту).</li>"
        "<li>30.06: APP-412 «Миграция на ППРБ» — принято в релиз 03.07.</li>"
        "<li>30.06: APP-521 «Интеграция с партнёром» — готово к релизу, отслеживать partner-api.</li>"
        "</ul>"),
    "1245185": ("RFC · ППРБ v2",
        "<h1>RFC · ППРБ v2</h1><p>Миграция на ППРБ v2: разбиение на ППРБ-ядро + ППРБ-адаптер.</p>"
        "<p>Owner: Разработчик backend. Срок: 03.07.</p>"),
    "1212418": ("Architecture · ППРБ",
        "<h1>Architecture · ППРБ</h1><p>Компоненты: ППРБ-ядро, ППРБ-адаптер, partner-api. "
        "Зависимости: partner-api (внешний).</p>"),
    "1081346": ("Postmortem · Инцидент 2026-06-30",
        "<h1>Postmortem · Инцидент 2026-06-30</h1><p>Симптом: деградация ППРБ-адаптера 30.06 14:00–15:30.</p>"
        "<p>Причина: исчерпание connection pool. Action items: OPS-79, APP-413.</p>"),
    "1179650": ("Changelog · Альфа 2026.07",
        "<h1>Changelog · Альфа 2026.07</h1><ul><li>APP-412 миграция на ППРБ</li>"
        "<li>APP-521 интеграция с партнёром</li><li>APP-421 репликация ППРБ</li></ul>"),
    "1179666": ("Retrospective · Спринт 12",
        "<h1>Retrospective · Спринт 12</h1><p>Что хорошо: релиз 03.07 в срок. "
        "Что улучшить: связь с SRE по ППРБ-адаптеру раньше.</p>"),
    "1081363": ("Test Plan · Альфа 2026.07",
        "<h1>Test Plan · Альфа 2026.07</h1><p>Smoke: ППРБ-ядро e2e. Регресс: реплики, вебхуки. "
        "Нагрузка: 100 RPS.</p>"),
}


def rename_confluence_direct():
    print("\n=== Confluence: прямое переименование страниц ===")
    for pid, (new_title, new_storage) in CONF_NEW.items():
        s, body = conf_get_page(pid)
        if s != 200:
            print(f"  [FAIL get] {pid}: HTTP {s} {body}")
            continue
        version = (body.get("version") or {}).get("number", 1)
        s2, body2 = conf_put_page(pid, new_title, new_storage, version)
        ok = s2 in (200, 201)
        print(f"  [{'OK' if ok else 'FAIL'}] {pid}: «{new_title}» (HTTP {s2})")
        if not ok:
            print(f"       {body2}")


def main():
    print("=== Прямое переименование сущностей: платежи → ППРБ ===")
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else {"jira", "bb", "conf"}
    if "jira" in only:
        rename_jira_direct()
    if "bb" in only:
        rename_bitbucket_direct()
    if "conf" in only:
        rename_confluence_direct()
    print("\nГотово.")


if __name__ == "__main__":
    main()
