# -*- coding: utf-8 -*-
"""Сидинг реального Bitbucket Cloud: создаёт синтетику «Альфа» в демо-репо.

Идемпотентно: создаёт репо (если нет), начальный коммит на main, ветку
feature/payment-schema с отличающимся коммитом и открытый PR «Миграция на ППРБ»
(summary «PR по <issue_key>: миграция на ППРБ»). При повторном запуске
переиспользует существующие репо/ветку/PR.

Запуск: python test-instances/seed_bitbucket.py
Требует .env (один из двух механизмов авторизации):
  A) Personal API token (любой план): BITBUCKET_EMAIL + BITBUCKET_API_TOKEN
     (Basic auth email:token; scopes: read+write:repository, read+write:pullrequest).
     НЕ может создавать репо — создайте репо вручную в UI, seeder сделает ветку + PR.
  B) Workspace access token (Premium): BITBUCKET_WORKSPACE_TOKEN
     (Bearer auth; scopes: repository admin + pullrequest write). Может создавать репо.
Плюс: BITBUCKET_WORKSPACE, BITBUCKET_REPO_SLUG.
Опц.: BITBUCKET_PR_ISSUE_KEY (по умолч. APP-412) — ключ задачи в summary PR;
       для связки с реальной Jira укажите KAN-ключ (см. gen_live_case.py).
Выход: печатает id PR + results/bitbucket_seeded.json (нужно для live-кейса).

App Passwords удаляются (brownout 09.06.2026, removal 28.07.2026) — миграция на API tokens.

Контракты Bitbucket Cloud REST 2.0:
  GET  /repositories/{ws}/{slug}                              — проверить репо
  POST /repositories/{ws}                                     — создать репо
  GET  /repositories/{ws}/{slug}/refs/branches/{name}         — проверить ветку
  POST /repositories/{ws}/{slug}/src                          — коммит/ветка (multipart)
  GET  /repositories/{ws}/{slug}/pullrequests?state=OPEN      — список PR
  POST /repositories/{ws}/{slug}/pullrequests                 — открыть PR
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
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

BASE = "https://api.bitbucket.org/2.0"


def _cfg():
    ws = os.environ.get("BITBUCKET_WORKSPACE", "")
    slug = os.environ.get("BITBUCKET_REPO_SLUG", "")
    if not (ws and slug):
        sys.exit("BITBUCKET_WORKSPACE/BITBUCKET_REPO_SLUG не заданы в .env")
    # B) workspace access token (Premium, Bearer) — приоритет
    ws_token = os.environ.get("BITBUCKET_WORKSPACE_TOKEN", "")
    if ws_token:
        headers = {"Authorization": f"Bearer {ws_token}", "Accept": "application/json"}
        return ws, slug, headers, "workspace-token"
    # A) personal API token (Basic auth: email:token)
    email = os.environ.get("BITBUCKET_EMAIL", "")
    token = os.environ.get("BITBUCKET_API_TOKEN", "")
    if not (email and token):
        sys.exit("Нужен BITBUCKET_WORKSPACE_TOKEN (Bearer, Premium) либо "
                 "BITBUCKET_EMAIL+BITBUCKET_API_TOKEN (Basic, любой план) в .env")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    return ws, slug, headers, "personal-token"


def _req(method, url, headers, body=None, content_type="application/json"):
    data = None
    h = dict(headers)
    if body is not None:
        if content_type == "application/json":
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        else:
            data = body  # bytes (multipart)
            h["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:800]}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


def _multipart(fields, files):
    """fields: [(name, value)] · files: [(fieldname, filename, ctype, content_bytes)]."""
    boundary = "----athanor" + uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())
    for fieldname, filename, ctype, content in files:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{fieldname}"; filename="{filename}"\r\n'
            .encode())
        parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
        parts.append(content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _branch_sha(ws, slug, headers, name):
    s, body = _req("GET", f"{BASE}/repositories/{ws}/{slug}/refs/branches/{name}", headers)
    if s == 200:
        return body.get("target", {}).get("hash")
    return None


def main():
    ws, slug, headers, auth_kind = _cfg()
    issue_key = os.environ.get("BITBUCKET_PR_ISSUE_KEY", "APP-412")
    print(f"=== Сидинг Bitbucket Cloud: {ws}/{slug} · PR issue_key={issue_key} · auth={auth_kind} ===\n")

    # 1) репо
    s, body = _req("GET", f"{BASE}/repositories/{ws}/{slug}", headers)
    if s == 404:
        s2, body2 = _req("POST", f"{BASE}/repositories/{ws}", headers, {
            "scm": "git", "name": slug, "is_private": True,
            "description": "Синтетика «Альфа» (демо Ouroboros). Не рабочий репо.",
        })
        if s2 in (200, 201):
            print(f"[create repo] {ws}/{slug}")
        elif s2 == 403:
            sys.exit(
                f"[create repo] HTTP 403 — personal API token не может создавать репо "
                f"(workspace-admin операция).\n"
                f"  Создайте репо вручную: bitbucket.org → {ws} → Create repository → "
                f"name='{slug}' → Create (private, без README/.gitignore).\n"
                f"  Затем запустите seeder снова — он создаст ветку + PR.\n"
                f"  Альтернатива (Premium): workspace access token (BITBUCKET_WORKSPACE_TOKEN, "
                f"Bearer) — может создавать репо."
            )
        else:
            sys.exit(f"[create repo FAILED] HTTP {s2} {body2}")
    elif s != 200:
        sys.exit(f"[get repo FAILED] HTTP {s} {body}")
    else:
        print(f"[reuse repo] {ws}/{slug}")

    # 2) main + начальный коммит
    main_sha = _branch_sha(ws, slug, headers, "main")
    if main_sha:
        print(f"[reuse main] {main_sha[:12]}")
    else:
        mbody, ct = _multipart(
            [("branch", "main"), ("message", "init: Альфа demo repo")],
            [("README.md", "README.md", "text/plain", b"# Alpha (demo)\nSynthetic Ouroboros data.\n")],
        )
        s2, body2 = _req("POST", f"{BASE}/repositories/{ws}/{slug}/src", headers, mbody, ct)
        if s2 not in (200, 201):
            sys.exit(f"[init main FAILED] HTTP {s2} {body2}")
        main_sha = _branch_sha(ws, slug, headers, "main")
        print(f"[init main] {main_sha[:12] if main_sha else '?'}")

    # 3) ветка feature/payment-schema (с отличающимся коммитом)
    feat = "feature/payment-schema"
    if _branch_sha(ws, slug, headers, feat):
        print(f"[reuse branch] {feat}")
    else:
        mbody, ct = _multipart(
            [("branch", feat), ("parents", main_sha or ""), ("message", "payment schema migration (demo)")],
            [("demo/change.txt", "change.txt", "text/plain", b"payment-schema v2 (demo)\n")],
        )
        s2, body2 = _req("POST", f"{BASE}/repositories/{ws}/{slug}/src", headers, mbody, ct)
        if s2 in (200, 201):
            print(f"[create branch] {feat} <- main {main_sha[:12] if main_sha else '?'}")
        else:
            sys.exit(f"[create branch FAILED] HTTP {s2} {body2}")

    # 4) PR «Миграция на ППРБ»
    title = "Миграция на ППРБ"
    summary = f"PR по {issue_key}: миграция на ППРБ"
    s, body = _req("GET", f"{BASE}/repositories/{ws}/{slug}/pullrequests?state=OPEN&pagelen=50", headers)
    existing = None
    if s == 200:
        for pr in body.get("values", []):
            if pr.get("title") == title:
                existing = pr
                break
    if existing:
        pr_id = existing["id"]
        print(f"[reuse PR] #{pr_id} «{title}»")
    else:
        s2, body2 = _req("POST", f"{BASE}/repositories/{ws}/{slug}/pullrequests", headers, {
            "title": title,
            "source": {"branch": {"name": feat}},
            "destination": {"branch": {"name": "main"}},
            "summary": {"raw": summary},
            "close_source_branch": False,
        })
        if s2 in (200, 201):
            pr_id = body2["id"]
            print(f"[create PR] #{pr_id} «{title}»")
        else:
            sys.exit(f"[create PR FAILED] HTTP {s2} {body2}")

    # 5) сохраняем
    out = HERE.parent / "results" / "bitbucket_seeded.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "workspace": ws, "repo": slug, "pr_id": pr_id, "title": title,
        "issue_key": issue_key,
        "url": f"https://bitbucket.org/{ws}/{slug}/pull-requests/{pr_id}",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out}")
    print(f"PR: https://bitbucket.org/{ws}/{slug}/pull-requests/{pr_id}")
    print(f"\nПрогон через реальный Bitbucket Cloud:")
    print(f"  MCP_BACKEND_PR=bitbucket python mcp/serve_all.py   # терминал 1")
    print(f"  MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print")


if __name__ == "__main__":
    main()
