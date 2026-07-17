"""Дискавери реальной Jira: статусы проекта, типы задач, существующие alpha-demo.

Запуск: python test-instances/discover_atlassian.py
Требует .env: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT.
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
    """Загрузить KEY=VALUE из .env в os.environ (секреты не логируются)."""
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
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    return url, headers, project, label


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return e.code, {"error": body}
    except Exception as e:
        return -1, {"error": str(e)}


def main():
    url, headers, project, label = _cfg()
    print(f"=== Jira: {url} · project={project} · label={label} ===\n")

    # 1) serverInfo
    s, body = _get(f"{url}/rest/api/2/serverInfo", headers)
    print(f"[serverInfo] {s} · {body.get('serverTitle','?')} v{body.get('version','?')} (Cloud={body.get('cloud', '?')})\n")

    # 2) статусы проекта
    s, body = _get(f"{url}/rest/api/2/project/{project}/statuses", headers)
    print(f"[project statuses] HTTP {s}")
    if isinstance(body, list):
        for st in body:
            print(f"  - {st.get('name')!r} (id={st.get('id')})  categories={[c.get('name') for c in st.get('statuses', [])][:0] or st.get('categories', [])}")
    else:
        print(f"  {body}")
    print()

    # 3) типы задач проекта (createmeta)
    s, body = _get(f"{url}/rest/api/2/issue/createmeta?projectKeys={project}", headers)
    print(f"[createmeta] HTTP {s}")
    if isinstance(body, dict):
        projects = body.get("projects", [])
        if projects:
            for it in projects[0].get("issuetypes", []):
                print(f"  - {it.get('name')!r} (id={it.get('id')}) subtask={it.get('subtask')}")
        else:
            print("  (нет проектов в createmeta — возможно, нужен新版 API /rest/api/3)")
    else:
        print(f"  {body}")
    print()

    # 4) существующие alpha-demo задачи (api/3 search/jql — api/2/search удалён)
    jql = f'project={project} AND labels="{label}" ORDER BY created ASC'
    import urllib.request as _ur
    _body = json.dumps({"jql": jql, "fields": ["summary", "status", "assignee", "labels"]}).encode("utf-8")
    _req2 = _ur.Request(f"{url}/rest/api/3/search/jql", data=_body, headers=headers, method="POST")
    try:
        with _ur.urlopen(_req2, timeout=15) as r:
            s, body = r.status, json.loads(r.read().decode("utf-8"))
    except _ur.HTTPError as e:
        s, body = e.code, {"error": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:
        s, body = -1, {"error": str(e)}
    issues = body.get("issues") or body.get("values") or [] if isinstance(body, dict) else []
    print(f"[alpha-demo issues] HTTP {s} · total={body.get('total') if isinstance(body, dict) else '?'}")
    for i in issues:
        f = i.get("fields", {})
        print(f"  {i['key']}: {f.get('summary')!r} [{(f.get('status') or {}).get('name')}] assignee={(f.get('assignee') or {}).get('displayName','—')} labels={f.get('labels', [])}")
    print()

    # 5) transitions для первой alpha-demo задачи (если есть)
    if isinstance(body, dict) and body.get("issues"):
        key = body["issues"][0]["key"]
        s2, tb = _get(f"{url}/rest/api/2/issue/{key}/transitions", headers)
        print(f"[transitions for {key}] HTTP {s2}")
        if isinstance(tb, dict):
            for tr in tb.get("transitions", []):
                tgt = tr.get("to", {})
                print(f"  - {tr.get('name')!r} (id={tr.get('id')}) → {tgt.get('name')!r}")
        print()


if __name__ == "__main__":
    main()
