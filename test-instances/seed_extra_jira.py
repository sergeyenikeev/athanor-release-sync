# -*- coding: utf-8 -*-
"""Добавить 3+ новых Jira-задач в проект APP для достижения 17+ общего счёта.

Создаёт через Jira REST API v2 (POST /rest/api/2/issue) с label alpha-demo.
Идемпотентно: если задача с тем же summary уже существует — пропускает.
"""
from __future__ import annotations

import base64
import json
import os
import sys
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
                raw = r.read().decode("utf-8")
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            try:
                err = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                err = f"<HTTP {e.code} {e.reason}>"
            return e.code, {"error": err}
        except Exception as e:
            last = e
            if attempt < retries - 1:
                import time
                time.sleep(backoff * (attempt + 1))
    return -1, {"error": f"{type(last).__name__}: {last}"}


def _jira_search(headers, jql):
    """Поиск задач по JQL — для проверки дублей."""
    import urllib.parse
    url = os.environ["JIRA_URL"].rstrip("/") + "/rest/api/2/search"
    url += "?" + urllib.parse.urlencode({"jql": jql, "maxResults": 50})
    return _req("GET", url, headers)


def _jira_create(headers, project_key, summary, description, issue_type="Task"):
    url = os.environ["JIRA_URL"].rstrip("/") + "/rest/api/2/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "labels": ["alpha-demo"],
        }
    }
    return _req("POST", url, headers, payload)


def main():
    url = os.environ["JIRA_URL"].rstrip("/")
    creds = base64.b64encode(
        f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}

    new_tasks = [
        {
            "project": "APP",
            "summary": "Автотесты ППРБ",
            "description": (
                "Написать e2e-автотесты для ППРБ-ядра и ППРБ-адаптера. "
                "Покрытие: миграция данных, репликация, вебхуки, кэш. "
                "Связано: APP-412 (Миграция на ППРБ), APP-421 (Репликация ППРБ). "
                "(Синтетика Ouroboros, demo.)"
            ),
            "basket_key": "APP-440",
            "role": "QA",
        },
        {
            "project": "APP",
            "summary": "Панель мониторинга ППРБ",
            "description": (
                "Дашборд для мониторинга ППРБ в реальном времени: "
                "latency, throughput, error rate, health check. "
                "Связано: OPS-79 (Мониторинг ППРБ-адаптера). "
                "(Синтетика Ouroboros, demo.)"
            ),
            "basket_key": "APP-431",
            "role": "Разработчик frontend",
        },
        {
            "project": "OPS",
            "summary": "Проверка ППРБ-адаптера в staging",
            "description": (
                "Smoke-тест ППРБ-адаптера на предпроде после деплоя. "
                "Валидация: health check, 10 RPS, нулевые 5xx. "
                "Связано: OPS-77 (Деплой ППРБ-адаптера), OPS-79 (Мониторинг). "
                "(Синтетика Ouroboros, demo.)"
            ),
            "basket_key": "OPS-81",
            "role": "SRE",
        },
    ]

    created = []
    for task in new_tasks:
        proj = task["project"]
        summary = task["summary"]

        # Проверяем дубль
        jql = f'project={proj} AND summary="{summary}" AND labels="alpha-demo"'
        s, body = _jira_search(headers, jql)
        if s == 200:
            issues = body.get("issues", [])
            if issues:
                key = issues[0]["key"]
                print(f"  [SKIP] {key} «{summary}» — уже существует")
                created.append({"jira_key": key, "summary": summary,
                                "basket_key": task["basket_key"],
                                "role": task["role"], "status": "existing"})
                continue

        s, body = _jira_create(headers, proj, summary, task["description"])
        if s in (200, 201):
            key = body.get("key", "?")
            print(f"  [OK]   {key} «{summary}» (проект {proj})")
            created.append({"jira_key": key, "summary": summary,
                            "basket_key": task["basket_key"],
                            "role": task["role"], "status": "created"})
        else:
            print(f"  [FAIL] «{summary}» HTTP {s}: {body}")

    # Сохраняем результат
    out = REPO / "results" / "jira_extra_seeded.json"
    out.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nСохранено: {out}")
    print(f"Создано/найдено: {len(created)} задач")


if __name__ == "__main__":
    main()
