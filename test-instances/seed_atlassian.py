"""Сидинг реальной Jira: создаёт синтетику «Альфа» в проекте KAN.

Создаёт 2 задачи (label "alpha-demo"), переводит первую в Done для воспроизведения
конфликта Jira «готово» ↔ письмо «блокер». Идемпотентно: при повторном запуске
переиспользует существующие alpha-demo задачи.

Запуск: python test-instances/seed_atlassian.py
Требует .env: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT.
Выход: печатает ключи созданных задач (нужны для генерации live-кейса).
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

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
    url = os.environ.get("JIRA_URL", "https://<your-tenant>.atlassian.net").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    project = os.environ.get("JIRA_PROJECT", "KAN")
    label = os.environ.get("JIRA_LABEL", "alpha-demo")
    if not email or not token:
        sys.exit("JIRA_EMAIL/JIRA_API_TOKEN не заданы в .env")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json",
               "Content-Type": "application/json"}
    return url, headers, project, label


def _req(method, url, headers, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:500]}
    except Exception as e:
        return -1, {"error": str(e)}


def _find_done_transition(url, headers, key):
    """Найти transition, ведущий в 'done'-статус (готово/done/выполнено/closed)."""
    s, body = _req("GET", f"{url}/rest/api/2/issue/{key}/transitions", headers)
    if s != 200:
        return None
    done_names = {"готово", "done", "выполнено", "closed", "закрыто", "resolved", "решено",
                  "complete", "completed"}
    for tr in body.get("transitions", []):
        tgt = (tr.get("to") or {}).get("name", "").strip().lower()
        if tgt in done_names:
            return tr.get("id"), tr.get("to", {}).get("name")
    # запасной: transition с id "31" (обычно Done в Software) или имя содержит "Done"
    for tr in body.get("transitions", []):
        if "done" in (tr.get("name", "") + " " + (tr.get("to") or {}).get("name", "")).lower():
            return tr.get("id"), tr.get("to", {}).get("name")
    return None


def _find_existing(url, headers, project, label):
    """Поиск alpha-demo задач через /rest/api/3/search/jql (api/2/search удалён)."""
    jql = f'project={project} AND labels="{label}" ORDER BY created ASC'
    s, body = _req("POST", f"{url}/rest/api/3/search/jql", headers,
                   {"jql": jql, "fields": ["summary", "status", "assignee", "labels"]})
    if s not in (200, 201):
        print(f"[search] HTTP {s} {body}")
        return []
    issues = body.get("issues") or body.get("values") or []
    return issues


def _pick_issuetype(url, headers, project):
    s, body = _req("GET", f"{url}/rest/api/2/issue/createmeta?projectKeys={project}", headers)
    if s == 200 and isinstance(body, dict):
        projects = body.get("projects", [])
        if projects:
            names = {it.get("name", "") for it in projects[0].get("issuetypes", [])}
            for pref in ("Задание", "Задача", "Task", "История", "Story", "Функция"):
                if pref in names:
                    return pref
            for it in projects[0].get("issuetypes", []):
                if not it.get("subtask"):
                    return it["name"]
    return "Task"


def main():
    url, headers, project, label = _cfg()
    print(f"=== Сидинг Jira: {url} · project={project} · label={label} ===\n")

    existing = _find_existing(url, headers, project, label)
    summaries = {"Миграция на ППРБ": None, "Интеграция с партнёром": None}

    if existing:
        print(f"[reuse] найдено {len(existing)} alpha-demo задач:")
        for i in existing:
            print(f"  {i['key']}: {i['fields']['summary']!r} [{i['fields']['status']['name']}]")
            if i["fields"]["summary"] in summaries:
                summaries[i["fields"]["summary"]] = i["key"]
        # если не все найдены — создадим недостающие
        need_create = {s: k for s, k in summaries.items() if k is None}
    else:
        need_create = dict(summaries)

    if need_create:
        issuetype = _pick_issuetype(url, headers, project)
        print(f"[createmeta] issue type: {issuetype!r}")
        for summary in need_create:
            body = {
                "fields": {
                    "project": {"key": project},
                    "summary": summary,
                    "issuetype": {"name": issuetype},
                    "labels": [label],
                    "description": "Синтетическая задача проекта «Альфа» (демо-контур Ouroboros). "
                                   "Не рабочая задача.",
                }
            }
            s, resp = _req("POST", f"{url}/rest/api/2/issue", headers, body)
            if s in (200, 201):
                key = resp["key"]
                summaries[summary] = key
                print(f"[create] {summary!r} → {key}")
            else:
                print(f"[create FAILED] {summary!r}: HTTP {s} {resp}")
                sys.exit(1)
        print()

    # переводим «Миграция на ППРБ» в Done (для конфликта Jira «готово» ↔ письмо «блокер»)
    key_done = summaries["Миграция на ППРБ"]
    key_progress = summaries["Интеграция с партнёром"]
    if key_done:
        tr = _find_done_transition(url, headers, key_done)
        if tr:
            tid, tname = tr
            s, resp = _req("POST", f"{url}/rest/api/2/issue/{key_done}/transitions", headers,
                           {"transition": {"id": tid}})
            print(f"[transition] {key_done} → {tname!r} (id={tid}): HTTP {s}")
        else:
            print(f"[transition] {key_done}: не найден done-transition (статус оставлен как есть)")

    # финальная проверка
    print("\n=== Итог (alpha-demo задачи в KAN) ===")
    final = _find_existing(url, headers, project, label)
    for i in final:
        print(f"  {i['key']}\t{i['fields']['summary']}\t[{i['fields']['status']['name']}]")
    print(f"\nKEYS: done={key_done} in_progress={key_progress}")
    # сохраним ключи в файл для генератора live-кейса
    out = HERE.parent / "results" / "atlassian_seeded_keys.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"done": key_done, "in_progress": key_progress,
                               "project": project, "url": url}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
