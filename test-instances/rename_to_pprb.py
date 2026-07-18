# -*- coding: utf-8 -*-
"""Переименование сущностей в реальных облаках: «платежи → Миграция на ППРБ».

Идемпотентно переименовывает через API:
  - Jira: summary basket-задач (label=basket) и KAN-1 (label=alpha-demo)
  - Bitbucket: title+summary открытых PR
  - Confluence: title+body.storage alpha-demo страниц (version.number+1)

Использует те же RULES, что и migrate_pprb.py. Креды — из .env.
Gmail отдельно: IMAP-удаление старых писем с «payment-adapter» + seed_google/basket/more.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(r"C:\Users\senik\AppData\Local\Temp\opencode")))
from migrate_pprb import RULES  # noqa: E402


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env(REPO / ".env")


def _apply_rules(text: str) -> tuple[str, int]:
    orig = text
    total = 0
    for old, new in RULES:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total += n
    return text, total


def _req(method, url, headers, body=None, timeout=20, retries=4, backoff=2.0):
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
                err = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                err = f"<HTTP {e.code} {e.reason}>"
            return e.code, {"error": err}
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    return -1, {"error": f"{type(last).__name__}: {last}"}


# ============================================================ Jira
def rename_jira():
    print("\n=== Jira: переименование summary ===")
    url = os.environ.get("JIRA_URL", "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not (url and email and token):
        print("  [skip] JIRA creds не заданы")
        return
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    # поиск basket + alpha-demo задач
    for label in ("basket", "alpha-demo"):
        s, body = _req("POST", f"{url}/rest/api/3/search/jql", H,
                       {"jql": f'labels="{label}" ORDER BY created ASC',
                        "fields": ["summary", "status", "labels"]})
        if s not in (200, 201):
            print(f"  [search label={label}] HTTP {s} {body}")
            continue
        issues = body.get("issues") or body.get("values") or []
        for i in issues:
            key = i["key"]
            summary = i["fields"]["summary"]
            new_summary, n = _apply_rules(summary)
            if n and new_summary != summary:
                s2, body2 = _req("PUT", f"{url}/rest/api/2/issue/{key}", H,
                                 {"fields": {"summary": new_summary}})
                ok = s2 in (200, 204)
                print(f"  [{'OK' if ok else 'FAIL'}] {key}: «{summary}» → «{new_summary}» (HTTP {s2})")
                if not ok:
                    print(f"       {body2}")
            else:
                print(f"  [skip] {key}: «{summary}» (без платежей)")


# ============================================================ Bitbucket
def rename_bitbucket():
    print("\n=== Bitbucket: переименование PR title+summary ===")
    ws = os.environ.get("BITBUCKET_WORKSPACE", "")
    slug = os.environ.get("BITBUCKET_REPO_SLUG", "")
    if not (ws and slug):
        print("  [skip] BITBUCKET creds не заданы")
        return
    ws_token = os.environ.get("BITBUCKET_WORKSPACE_TOKEN", "")
    if ws_token:
        H = {"Authorization": f"Bearer {ws_token}", "Accept": "application/json"}
    else:
        email = os.environ.get("BITBUCKET_EMAIL", "")
        token = os.environ.get("BITBUCKET_API_TOKEN", "")
        creds = base64.b64encode(f"{email}:{token}".encode()).decode()
        H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    BB = "https://api.bitbucket.org/2.0"
    s, body = _req("GET", f"{BB}/repositories/{ws}/{slug}/pullrequests?state=OPEN&pagelen=50", H)
    if s != 200:
        print(f"  [list PR] HTTP {s} {body}")
        return
    for pr in body.get("values", []):
        pid = pr["id"]
        title = pr.get("title", "")
        summary_raw = (pr.get("summary") or {}).get("raw", "") or ""
        new_title, n1 = _apply_rules(title)
        new_summary, n2 = _apply_rules(summary_raw)
        if (n1 or n2) and (new_title != title or new_summary != summary_raw):
            payload = {}
            if new_title != title:
                payload["title"] = new_title
            if new_summary != summary_raw:
                payload["summary"] = {"raw": new_summary}
            s2, body2 = _req("PUT", f"{BB}/repositories/{ws}/{slug}/pullrequests/{pid}", H, payload)
            ok = s2 in (200, 201)
            print(f"  [{'OK' if ok else 'FAIL'}] PR #{pid}: «{title}» → «{new_title}» (HTTP {s2})")
            if not ok:
                print(f"       {body2}")
        else:
            print(f"  [skip] PR #{pid}: «{title}» (без платежей)")


# ============================================================ Confluence
def rename_confluence():
    print("\n=== Confluence: переименование title+body страниц ===")
    url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("JIRA_API_TOKEN", "")
    if not (url and email and token):
        print("  [skip] CONFLUENCE creds не заданы")
        return
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    H = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    label = os.environ.get("CONFLUENCE_LABEL", "alpha-demo")
    space = os.environ.get("CONFLUENCE_SPACE", "")
    personal = space.startswith("~") if space else False
    cql = (f'space="{space}" AND label="{label}"') if (space and not personal) else f'label="{label}"'
    s, body = _req("GET", f"{url}/wiki/rest/api/content/search?cql={urllib.parse.quote(cql)}"
                   "&expand=version,body.storage,space&limit=50", H)
    if s != 200:
        print(f"  [search] HTTP {s} {body}")
        return
    for p in body.get("results", []):
        if (p.get("type") or "page") != "page":
            continue
        pid = str(p["id"])
        title = p.get("title", "")
        storage = ((p.get("body") or {}).get("storage") or {}).get("value", "")
        version = (p.get("version") or {}).get("number", 1)
        new_title, n1 = _apply_rules(title)
        new_storage, n2 = _apply_rules(storage)
        if (n1 or n2) and (new_title != title or new_storage != storage):
            payload = {
                "id": pid, "type": "page", "title": new_title,
                "space": {"key": (p.get("space") or {}).get("key", space)},
                "body": {"storage": {"value": new_storage, "representation": "storage"}},
                "version": {"number": int(version) + 1},
            }
            s2, body2 = _req("PUT", f"{url}/wiki/rest/api/content/{pid}", H, payload)
            ok = s2 in (200, 201)
            print(f"  [{'OK' if ok else 'FAIL'}] {pid}: «{title}» → «{new_title}» (HTTP {s2})")
            if not ok:
                print(f"       {body2}")
        else:
            print(f"  [skip] {pid}: «{title}» (без платежей)")


def main():
    print("=== Переименование сущностей в облаках: платежи → ППРБ ===")
    rename_jira()
    rename_bitbucket()
    rename_confluence()
    print("\nГотово. Gmail отдельно: IMAP-удаление + повторный seed.")


if __name__ == "__main__":
    main()
