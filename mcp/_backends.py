"""MCP-адаптеры к реальным и тестовым источникам (контракт → схема агента).

Режимы MCP_BACKEND:
  - live (по умолчанию) — реальные Jira/Bitbucket/Confluence/Google
    (mail через IMAP + calendar через публичный iCal URL), stdlib-only.
  - test — локальные тестовые инстансы (Jira REST v2, Bitbucket Cloud REST 2.0,
    Confluence REST API v1) по реальным HTTP-контрактам; calendar/mail в test-режиме
    читаются из файла (read_case_json). Конвертация ответов → схема агента.
  - file — файловый демо-контур (обезличенные выгрузки из MCP_CASE_DIR).

Контракты:
  Jira:       GET /rest/api/2/search?jql=project=KEY  → {issues:[{key,fields:{summary,status,assignee}}]}
  Bitbucket: GET /repositories/{workspace}/{repo_slug}/pullrequests → {values:[{id,title,state,created_on,updated_on,summary:{raw}}]}
  Confluence: GET /wiki/rest/api/content/search?cql=space=KEY AND label="alpha-demo"
              &expand=body.view,version,space → {results:[{id,title,space,version,body, _links}]}
  Google mail: IMAP (imaplib) → message; Google calendar: публичный iCal (.ics) → VEVENT.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# Загрузить .env в os.environ при импорте (секреты Jira). .env в .gitignore.
_ENV = Path(__file__).resolve().parent.parent / ".env"
if _ENV.is_file():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _v = _v.split("#", 1)[0].strip() if " #" in _v else _v.strip()
            os.environ.setdefault(_k.strip(), _v)

# URL тестовых инстансов — читаются лениво (внутри функций), чтобы env,
# заданный после импорта (напр. в тестах), учитывался.


def _backend() -> str:
    return os.environ.get("MCP_BACKEND", "").lower()


def _backend_for(source: str) -> str:
    """Per-source backend selection. Приоритет: MCP_BACKEND_<SOURCE> > MCP_BACKEND.
    Source ∈ {CALENDAR, MAIL, JIRA, PR, TRANSCRIPT, CONFLUENCE}. 'live' preset разворачивается
    в Jira=atlassian, calendar/mail=google, confluence=atlassian, pr/transcript=file."""
    override = os.environ.get(f"MCP_BACKEND_{source}", "").lower()
    if override:
        return override
    b = _backend()
    if b == "live":
        return {"JIRA": "atlassian", "CALENDAR": "google",
                "MAIL": "google", "PR": "file", "TRANSCRIPT": "file",
                "CONFLUENCE": "atlassian"}.get(source, "file")
    return b


def _jira_url() -> str:
    return os.environ.get("TEST_JIRA_URL", "http://127.0.0.1:9911")


def _bitbucket_url() -> str:
    return os.environ.get("TEST_BITBUCKET_URL", "http://127.0.0.1:9913")


def _confluence_url() -> str:
    return os.environ.get("TEST_CONFLUENCE_URL", "http://127.0.0.1:9914")


def _jira_project() -> str:
    return os.environ.get("TEST_JIRA_PROJECT", "ALPHA")


def _confluence_space() -> str:
    return os.environ.get("TEST_CONFLUENCE_SPACE", "ALPHA")


def _bb_workspace() -> str:
    return os.environ.get("TEST_BB_WORKSPACE", "athanor")


def _bb_repo_slug() -> str:
    return os.environ.get("TEST_BB_REPO_SLUG", "alpha")


# --- Bitbucket Cloud (боевой контракт, MCP_BACKEND_PR=bitbucket) ----------
def _bitbucket_cloud_url() -> str:
    return os.environ.get("BITBUCKET_URL", "https://api.bitbucket.org/2.0").rstrip("/")


def _bitbucket_cloud_workspace() -> str:
    return os.environ.get("BITBUCKET_WORKSPACE", "")


def _bitbucket_cloud_repo() -> str:
    return os.environ.get("BITBUCKET_REPO_SLUG", "")


def _bitbucket_cloud_auth() -> dict:
    """Авторизация Bitbucket Cloud. Два механизма (приоритет — workspace token):

    1. **Workspace access token** (Premium): `BITBUCKET_WORKSPACE_TOKEN` →
       `Authorization: Bearer <token>`. Привязан к workspace, может создавать репо.
    2. **Personal API token** (любой план): `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` →
       Basic auth `email:token`. Не может создавать репо (POST /repositories —
       workspace-admin операция), но читает/создаёт ветки, коммиты, PR.

    App Passwords удаляются (brownout 09.06.2026, removal 28.07.2026) — миграция на
    API tokens. См. test-instances/README.md."""
    ws_token = os.environ.get("BITBUCKET_WORKSPACE_TOKEN", "")
    if ws_token:
        return {"Authorization": f"Bearer {ws_token}", "Accept": "application/json"}
    import base64

    email = os.environ.get("BITBUCKET_EMAIL", "")
    token = os.environ.get("BITBUCKET_API_TOKEN", "")
    if not email or not token:
        raise RuntimeError("MCP_BACKEND_PR=bitbucket требует либо BITBUCKET_WORKSPACE_TOKEN "
                           "(workspace access token, Bearer, Premium), либо BITBUCKET_EMAIL + "
                           "BITBUCKET_API_TOKEN (personal API token, Basic) в .env "
                           "(см. test-instances/README.md)")
    creds = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


# --- Atlassian Jira (боевой контракт, MCP_BACKEND=atlassian) ----------
def _jira_cloud_url() -> str:
    return os.environ.get("JIRA_URL", "https://<your-tenant>.atlassian.net").rstrip("/")


def _jira_cloud_project() -> str:
    return os.environ.get("JIRA_PROJECT", "KAN")


def _jira_cloud_label() -> str:
    return os.environ.get("JIRA_LABEL", "alpha-demo")


def _jira_auth_header() -> dict:
    """Basic-авторизация Jira: email + API-токен. Токен — только в .env."""
    import base64

    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not email or not token:
        raise RuntimeError("MCP_BACKEND=atlassian требует JIRA_EMAIL и JIRA_API_TOKEN в .env")
    creds = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {creds}", "Accept": "application/json",
            "Content-Type": "application/json"}


def _jira_search(jql: str, fields: list[str] | None = None) -> list[dict]:
    """Поиск задач в Jira через /rest/api/3/search/jql (POST, JSON).

    /rest/api/2/search удалён в новых Cloud-инстансах (410); createmeta и issue
    эндпоинты api/2 работают. Возвращаем issues в том же формате, что и api/2.
    """
    url = f"{_jira_cloud_url()}/rest/api/3/search/jql"
    body = {"jql": jql, "fields": fields or ["summary", "status", "assignee"]}
    last = None
    for _ in range(3):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=_jira_auth_header(), method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            issues = data.get("issues") or data.get("values") or []
            return issues
        except urllib.error.HTTPError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            import time as _t; _t.sleep(1.0)
    raise last  # type: ignore[misc]


# Нормализация статусов Jira (EN/RU) → каноничные русские для схемы агента.
_STATUS_MAP = {
    "done": "готово", "выполнено": "готово", "closed": "закрыто", "закрыто": "закрыто",
    "resolved": "решено", "решено": "решено",
    "in progress": "в работе", "в работе": "в работе",
    "to do": "к выполнению", "к выполнению": "к выполнению", "backlog": "бэклог",
    "open": "открыто", "открыто": "открыто",
}


def _normalize_status(name: str) -> str:
    return _STATUS_MAP.get(name.strip().lower(), name)


def _get(url: str, headers: dict | None = None, timeout: int = 20, retries: int = 3) -> dict | list:
    """HTTP GET с retry на network timeout (live-облака нестабильны)."""
    last = None
    for _ in range(retries):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # HTTP-ошибка — не сетевая, поднимаем сразу (как было)
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            import time as _t; _t.sleep(1.0)
    raise last  # type: ignore[misc]


def _project_from_subject(subject: str) -> str:
    # «Релиз-синк · Альфа» → «Альфа»
    if "·" in subject:
        return subject.split("·", 1)[1].strip()
    return "Альфа"


def _dt_short(iso: str) -> str:
    # 2026-07-03T14:00:00 → 2026-07-03T14:00
    return iso.replace("Z", "").split("+")[0][:16]


def _date_short(iso: str) -> str:
    return iso.replace("Z", "").split("+")[0][:10]


# ----------------------------------------------------------------- tracker/repo
def jira_issues() -> list[dict]:
    """Тестовый инстанс Jira (локальный сервер с реальным контрактом REST v2)."""
    data = _get(f"{_jira_url()}/rest/api/2/search?jql=project={_jira_project()}")
    out = []
    for i in data.get("issues", []):
        f = i["fields"]
        out.append({
            "key": i["key"],
            "title": f["summary"],
            "status": f["status"]["name"],
            "assignee_role": (f.get("assignee") or {}).get("displayName", "не определён"),
        })
    return out


def jira_issues_atlassian() -> list[dict]:
    """Реальная Jira (MCP_BACKEND=atlassian). Контракт тот же, что у тестового
    инстанса; добавлены Basic-авторизация, нормализация статусов и фильтр по лейблу,
    чтобы читать только синтетику «Альфа», а не рабочие задачи проекта."""
    label = _jira_cloud_label()
    jql = f'project={_jira_cloud_project()} AND labels="{label}" ORDER BY created ASC'
    out = []
    for i in _jira_search(jql):
        f = i.get("fields", {})
        assignee = (f.get("assignee") or {}).get("displayName", "не определён")
        out.append({
            "key": i["key"],
            "title": f["summary"],
            "status": _normalize_status(f["status"]["name"]),
            "assignee_role": assignee,
        })
    return out


def bitbucket_prs() -> list[dict]:
    data = _get(f"{_bitbucket_url()}/repositories/{_bb_workspace()}/{_bb_repo_slug()}/pullrequests?state=OPEN")
    out = []
    state_map = {"open": "на ревью", "merged": "смержен", "declined": "отклонён", "superseded": "заменён"}
    for p in data.get("values", []):
        created = datetime.fromisoformat(p["created_on"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(p["updated_on"].replace("Z", "+00:00"))
        review_days = max(1, round((updated - created).total_seconds() / 86400))
        m = re.search(r"([A-Z]{2,5}-\d{1,5})", (p.get("summary") or {}).get("raw", "") or "")
        out.append({
            "number": p["id"],
            "title": p["title"],
            "status": state_map.get(p["state"].lower(), p["state"]),
            "review_days": review_days,
            "issue_key": m.group(0) if m else "",
        })
    return out


def bitbucket_prs_cloud() -> list[dict]:
    """Реальный Bitbucket Cloud (MCP_BACKEND_PR=bitbucket). Контракт тот же, что у
    тестового инстанса (/repositories/{workspace}/{repo_slug}/pullrequests → {values}),
    добавлена Basic-авторизация (email аккаунта + API token with scopes). Демо-репо
    должно быть выделенным (синтетика «Альфа»), чтобы не читать рабочие PR."""
    ws = _bitbucket_cloud_workspace()
    repo = _bitbucket_cloud_repo()
    if not ws or not repo:
        raise RuntimeError("MCP_BACKEND_PR=bitbucket требует BITBUCKET_WORKSPACE и "
                           "BITBUCKET_REPO_SLUG в .env (см. test-instances/README.md)")
    url = (f"{_bitbucket_cloud_url()}/repositories/{ws}/{repo}/pullrequests"
           f"?state=OPEN&pagelen=50")
    data = _get(url, _bitbucket_cloud_auth())
    out = []
    state_map = {"open": "на ревью", "merged": "смержен", "declined": "отклонён", "superseded": "заменён"}
    for p in data.get("values", []):
        created = datetime.fromisoformat(p["created_on"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(p["updated_on"].replace("Z", "+00:00"))
        review_days = max(1, round((updated - created).total_seconds() / 86400))
        summary = (p.get("summary") or {}).get("raw", "") or ""
        m = re.search(r"([A-Z]{2,5}-\d{1,5})", summary)
        out.append({
            "number": p["id"],
            "title": p["title"],
            "status": state_map.get(p["state"].lower(), p["state"]),
            "review_days": review_days,
            "issue_key": m.group(0) if m else "",
        })
    return out


# --- Реальный mail (IMAP) + Calendar (iCal) — MCP_BACKEND_CALENDAR/MAIL=google ---
# Без Azure/OAuth: IMAP + пароль приложения (mail), публичный iCal URL (Calendar).
# stdlib-only (imaplib, email, urllib). Реальный внешний ящик, промышленный протокол IMAP.

def _gmail_cfg() -> tuple[str, str]:
    acct = os.environ.get("GOOGLE_ACCOUNT", "")
    pwd = os.environ.get("GOOGLE_APP_PASSWORD", "")
    if not acct or not pwd:
        raise RuntimeError("MCP_BACKEND=google для почты требует GOOGLE_ACCOUNT и "
                           "GOOGLE_APP_PASSWORD в .env (см. test-instances/README.md)")
    return acct, pwd


def _decode_hdr(raw: str | None) -> str:
    import email.header as _h
    if not raw:
        return ""
    out = []
    for enc, charset in _h.decode_header(raw):
        if isinstance(enc, bytes):
            out.append(enc.decode(charset or "utf-8", "replace"))
        else:
            out.append(enc)
    return "".join(out)


def _msg_body(msg) -> str:
    import email as _email
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    cs = part.get_content_charset() or "utf-8"
                    return payload.decode(cs, "replace")
        # запасно — text/html
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return msg.get_payload() or ""


def _imap_date(raw: str | None) -> str:
    import email.utils as _u
    if not raw:
        return ""
    dt = _u.parsedate_tz(raw)
    if not dt:
        return ""
    ts = _u.mktime_tz(dt)
    import time as _t
    return _t.strftime("%Y-%m-%d", _t.gmtime(ts))


def gmail_mail() -> list[dict]:
    """Письма из реального mail через IMAP (пароль приложения). Фильтр — синтетика «Альфа»."""
    import imaplib, email as _email
    acct, pwd = _gmail_cfg()
    box = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        box.login(acct, pwd)
        box.select("INBOX")
        typ, data = box.search(None, "ALL")
        ids = (data[0] or b"").split()[-25:]
        out = []
        for mid in ids:
            typ, msgdata = box.fetch(mid, "(RFC822)")
            if typ != "OK" or not msgdata or not msgdata[0]:
                continue
            msg = _email.message_from_bytes(msgdata[0][1])
            subj = _decode_hdr(msg["Subject"])
            role_hdr = _decode_hdr(msg.get("X-Athanor-Role"))
            # только синтетика демо-контура (не личная почта пользователя):
            # маркер — заголовок X-Athanor-Role (все сид-письма его имеют) ИЛИ ключевые
            # слова в теме (для писем без заголовка, напр. импортированных вручную).
            if not role_hdr and not any(k in subj for k in ("payment-adapter", "KAN-", "Альфа", "Релиз-синк")):
                continue
            role = role_hdr or "SRE"
            out.append({
                "id": mid.decode(),
                "from_role": role,
                "date": _imap_date(msg["Date"]),
                "subject": subj,
                "body": _msg_body(msg),
            })
        return out
    finally:
        try:
            box.logout()
        except Exception:
            pass


def _ical_unfold(text: str) -> str:
    # iCal line folding: продолжение строки начинается с пробела/таба
    return re.sub(r"\r?\n[ \t]", "", text)


def _ical_dt(raw: str) -> str:
    # DTSTART:20260703T140000Z | 20260703T140000 | TZID=...:20260703T140000
    raw = raw.split(":", 1)[-1] if ":" in raw else raw
    raw = raw.rstrip("Z")
    if "T" in raw and len(raw) >= 13:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T{raw[9:11]}:{raw[11:13]}"
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


# Участники — роли (обезличивание), не реальные люди.
_ALPHA_PARTICIPANTS = ["Тимлид", "SRE", "Владелец продукта", "Разработчик backend", "Разработчик frontend"]


def google_calendar_events() -> list[dict]:
    """События из Calendar через публичный iCal URL (.ics, без авторизации)."""
    url = os.environ.get("GOOGLE_ICAL_URL", "")
    if not url:
        raise RuntimeError("MCP_BACKEND=google для календаря требует GOOGLE_ICAL_URL в .env "
                           "(публичный iCal URL календаря — см. test-instances/README.md)")
    text = None
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                text = _ical_unfold(r.read().decode("utf-8", "replace"))
            break
        except Exception as e:  # noqa: BLE001 — сеть до calendar.google.com нестабильна
            last_err = e
            import time as _t; _t.sleep(1.0)
    if text is None:
        raise RuntimeError(f"iCal fetch failed after 3 retries: {last_err}")
    out = []
    for block in text.split("BEGIN:VEVENT"):
        if "END:VEVENT" not in block:
            continue
        ev = block.split("END:VEVENT", 1)[0]
        fields = {}
        for ln in ev.splitlines():
            if ":" in ln and ";" not in ln.split(":")[0]:
                k, _, v = ln.partition(":")
                fields[k.strip().upper()] = v.strip()
            elif ":" in ln:
                k, _, v = ln.partition(":")
                fields[k.strip().split(";", 1)[0].upper()] = v.strip()
        subj = fields.get("SUMMARY", "")
        if "Релиз-синк" not in subj and "Альфа" not in subj:
            continue
        out.append({
            "id": fields.get("UID", subj),
            "title": subj,
            "project": _project_from_subject(subj) if "·" in subj else "Альфа",
            "datetime": _ical_dt(fields.get("DTSTART", "")),
            "participants": _ALPHA_PARTICIPANTS,
        })
    return out


# --- Atlassian Confluence Cloud (боевой контракт, MCP_BACKEND_CONFLUENCE=atlassian) ---
def _confluence_cloud_url() -> str:
    return os.environ.get("CONFLUENCE_URL", "https://<your-tenant>.atlassian.net").rstrip("/")


def _confluence_cloud_space() -> str:
    return os.environ.get("CONFLUENCE_SPACE", "ALPHA")


def _confluence_cloud_label() -> str:
    return os.environ.get("CONFLUENCE_LABEL", "alpha-demo")


def _confluence_auth_header() -> dict:
    """Basic-авторизация Confluence Cloud: email + API-токен (тот же, что для Jira).
    Токен — только в .env. Используется REST API v1 (/wiki/rest/api/content/search, CQL)."""
    import base64

    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("JIRA_API_TOKEN", "")
    if not email or not token:
        raise RuntimeError("MCP_BACKEND_CONFLUENCE=atlassian требует CONFLUENCE_EMAIL и "
                           "CONFLUENCE_API_TOKEN в .env (можно переиспользовать JIRA_EMAIL/"
                           "JIRA_API_TOKEN — тот же Atlassian API-токен)")
    creds = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


def _strip_html(s: str) -> str:
    """Грубо очистить HTML из body.view.value Confluence — для excerpt."""
    import re as _re
    out = _re.sub(r"<[^>]+>", " ", s or "")
    out = _re.sub(r"\s+", " ", out).strip()
    return out


def _excerpt(body_view: str, limit: int = 200) -> str:
    text = _strip_html(body_view)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _confluence_cql(space: str, label: str) -> str:
    """CQL-фильтр: пространство (опц.) + лейбл (читаем только синтетику «Альфа»).

    Space-фильтр опускается, если ключ пуст или начинается с '~' (личное
    пространство — CQL-парсер Confluence не принимает `space="~…"`). В этом
    случае фильтром остаётся только лейбл `alpha-demo`, чего достаточно для
    изоляции синтетики демо-контура от рабочей документации."""
    parts: list[str] = []
    if space and not space.startswith("~"):
        parts.append(f'space="{space}"')
    if label:
        parts.append(f'label="{label}"')
    if not parts:
        # без фильтров — ищем все страницы (только для дискавери; в боевых
        # настройках всегда задан лейбл)
        return "type=page"
    return " AND ".join(parts)


def confluence_pages_test() -> list[dict]:
    """Тестовый инстанс Confluence (локальный сервер с реальным контрактом REST API v1):
    GET /wiki/rest/api/content/search?cql=space=KEY AND label="alpha-demo"&expand=body.view,version,space
    """
    from urllib.parse import quote
    space = _confluence_space()
    label = os.environ.get("TEST_CONFLUENCE_LABEL", "alpha-demo")
    cql = _confluence_cql(space, label)
    url = (f"{_confluence_url()}/wiki/rest/api/content/search"
           f"?cql={quote(cql)}&expand=body.view,version,space&limit=25")
    data = _get(url)
    return _confluence_results_to_schema(data, base_url=_confluence_url())


def confluence_pages_atlassian() -> list[dict]:
    """Реальная Confluence Cloud (MCP_BACKEND_CONFLUENCE=atlassian). Контракт тот же, что у
    тестового инстанса (REST API v1 /wiki/rest/api/content/search, CQL, Basic auth); читаем
    только страницы с лейблом CONFLUENCE_LABEL (синтетика «Альфа»), не рабочую документацию."""
    from urllib.parse import quote
    space = _confluence_cloud_space()
    label = _confluence_cloud_label()
    cql = _confluence_cql(space, label)
    url = (f"{_confluence_cloud_url()}/wiki/rest/api/content/search"
           f"?cql={quote(cql)}&expand=body.view,version,space&limit=25")
    req = urllib.request.Request(url, headers=_confluence_auth_header(), method="GET")
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            return _confluence_results_to_schema(data, base_url=_confluence_cloud_url())
        except urllib.error.HTTPError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            import time as _t; _t.sleep(1.0)
    raise last  # type: ignore[misc]


def _confluence_results_to_schema(data: dict, base_url: str) -> list[dict]:
    """Конвертация ответа Confluence REST API v1 → список ConfluencePage-словарей.

    Ответ: {results: [{id, title, space:{key,name}, version:{number,when},
            body:{view:{value}}, _links:{webui, base}}], ...}
    """
    out = []
    base = (data.get("_links") or {}).get("base") or base_url
    for p in data.get("results", []):
        if (p.get("type") or "page") != "page":
            continue
        space = (p.get("space") or {}).get("key", "")
        version = (p.get("version") or {})
        body_view = ((p.get("body") or {}).get("view") or {}).get("value", "")
        links = p.get("_links") or {}
        webui = links.get("webui", "")
        url = (base.rstrip("/") + webui) if webui else ""
        title = p.get("title", "")
        excerpt = _excerpt(body_view)
        # body.view содержит H1 с заголовком → excerpt начинается с title; отбрасываем
        # префикс, чтобы в сводке не было «Title: Title …»
        if title and excerpt.lower().startswith(title.lower()):
            excerpt = excerpt[len(title):].lstrip(" :—-–")
        if not excerpt:
            excerpt = title  # не оставлять пустой excerpt
        out.append({
            "id": str(p.get("id", "")),
            "title": title,
            "space": space,
            "excerpt": excerpt,
            "url": url,
            "version": int(version.get("number", 1) or 1),
            "updated_at": _date_short(version.get("when", "")),
        })
    return out


# ----------------------------------------------------------------- dispatch
def get_events() -> list[dict]:
    b = _backend_for("CALENDAR")
    if b == "google":
        return google_calendar_events()
    # test/file → файловая выгрузка (read_case_json)
    from _base import read_case_json  # noqa: PLC0415
    return read_case_json("calendar.json", "events")


def get_mail() -> list[dict]:
    b = _backend_for("MAIL")
    if b == "google":
        return gmail_mail()
    # test/file → файловая выгрузка (read_case_json)
    from _base import read_case_json  # noqa: PLC0415
    return read_case_json("mail.json", "messages")


def get_issues() -> list[dict]:
    b = _backend_for("JIRA")
    if b == "atlassian":
        return jira_issues_atlassian()
    if b in ("test", "test-instances", "instances"):
        return jira_issues()
    from _base import read_case_json  # noqa: PLC0415
    return read_case_json("tracker.json", "issues")


def get_prs() -> list[dict]:
    b = _backend_for("PR")
    if b == "bitbucket":
        return bitbucket_prs_cloud()
    if b in ("test", "test-instances", "instances"):
        return bitbucket_prs()
    # atlassian/file: PR из локального кейса (боевой Bitbucket — через MCP_BACKEND_PR=bitbucket)
    from _base import read_case_json  # noqa: PLC0415
    return read_case_json("tracker.json", "prs")


def get_confluence_pages(space: str = "", label: str = "") -> list[dict]:
    """Страницы Confluence (release plan / decision log / RFC) по проекту.

    Файловый демо-контур (по умолчанию) — read_case_json('confluence.json').
    MCP_BACKEND=test — локальный тестовый инстанс (реальный контракт REST API v1).
    MCP_BACKEND_CONFLUENCE=atlassian — реальная Confluence Cloud (CQL по space+label).
    """
    b = _backend_for("CONFLUENCE")
    if b == "atlassian":
        return confluence_pages_atlassian()
    if b in ("test", "test-instances", "instances"):
        return confluence_pages_test()
    from _base import read_case_json  # noqa: PLC0415
    return read_case_json("confluence.json", "pages")
