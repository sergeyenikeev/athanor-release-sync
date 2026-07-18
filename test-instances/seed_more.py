# -*- coding: utf-8 -*-
"""Расширение сидинга до 10+ сущностей в каждой системе (масштаб демо-контура).

Дополняет seed_basket.py (5 Jira-задач + PR #2 + 5 писем) и базовые сидеры
(seed_atlassian/confluence/bitbucket/google). Создаёт:

  - Jira: +7 задач (APP-410/413/422/430, OPS-70/79/80) → 12 basket-задач + KAN-1/2 = 14
  - Bitbucket: +8 PR (разные фичи/доки) → 10 PR всего
  - Confluence: +8 страниц (RFC/Postmortem/Runbook/Changelog/On-call/Retrospective/
    Architecture/Test Plan) → 10 страниц всего
  - Gmail: +6 писем (уникальные темы, X-Athanor-Role) → 11+ писем всего
  - Calendar: генерирует examples/calendar_alpha_10.ics с 10 событиями для импорта
    в Google Calendar (Settings → Import & export → Import). Calendar API требует
    OAuth2 — app password даёт только IMAP/SMTP, поэтому .ics + ручной импорт.

Идемпотентно: переиспользует существующие задачи/PR/страницы/письма.
Запуск: python test-instances/seed_more.py
Выход: results/more_seeded.json + examples/calendar_alpha_10.ics.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

from seed_basket import (  # noqa: E402
    _jira_cfg, _myself, _ensure_project, _pick_issuetype,
    _find_issue_by_label_summary, _find_transition, _STATUS_TARGET,
    _bb_cfg, _bb_multipart, _bb_branch_sha, BB_BASE,
    LABEL_DEMO, LABEL_BASKET, PROJECTS,
)
import seed_basket as _sb  # noqa: E402


def _req_retry(method, url, headers, body=None, content_type="application/json",
               timeout=12, retries=6, backoff=3.0):
    """_req с retry на network timeout (Atlassian/Bitbucket нестабильны)."""
    data = None
    h = dict(headers)
    if body is not None:
        if content_type == "application/json":
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        else:
            data = body
            h["Content-Type"] = content_type
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
                err_body = e.read().decode("utf-8", "replace")[:600]
            except Exception:
                err_body = f"<HTTP {e.code} {e.reason}, body unreadable>"
            return e.code, {"error": err_body}
        except Exception as e:  # noqa: BLE001 — network timeout/ssl/reset
            last = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    return -1, {"error": f"{type(last).__name__}: {last} (after {retries} retries)"}


# Monkey-patch: seed_basket-хелперы (_ensure_project, _pick_issuetype, ...) используют
# _req без retry — заменим на retry-версию, чтобы Atlassian-таймауты не валили весь прогон.
_sb._req = _req_retry
_req = _req_retry  # для прямых вызовов ниже

# ============================================================ Jira: +7 задач
# basket_key — канон корзины/«Альфа»; jira_key назначает Cloud (APP-4.., OPS-3..).
JIRA_MORE = [
    {"proj": "APP", "basket_key": "APP-410", "summary": "Кэш ППРБ",
     "status": "готово", "role": "Разработчик backend"},
    {"proj": "APP", "basket_key": "APP-413", "summary": "Вебхуки ППРБ",
     "status": "в работе", "role": "Разработчик backend"},
    {"proj": "APP", "basket_key": "APP-422", "summary": "Реестр ППРБ",
     "status": "открыто", "role": "Разработчик frontend"},
    {"proj": "APP", "basket_key": "APP-430", "summary": "Метрики бизнес-операций",
     "status": "открыто", "role": "Владелец продукта"},
    {"proj": "OPS", "basket_key": "OPS-70", "summary": "Стенд предпрода",
     "status": "готово", "role": "SRE"},
    {"proj": "OPS", "basket_key": "OPS-79", "summary": "Мониторинг ППРБ-адаптера",
     "status": "в работе", "role": "SRE"},
    {"proj": "OPS", "basket_key": "OPS-80", "summary": "Runbook релизов",
     "status": "открыто", "role": "SRE"},
]


def seed_jira_more():
    print("\n=== Jira: +7 задач (до 12 basket + KAN-1/2 = 14) ===")
    url, headers = _jira_cfg()
    lead = _myself(url, headers)
    ok = {}
    for proj in PROJECTS:
        if _ensure_project(url, headers, proj, lead):
            ok[proj["key"]] = proj
    out = []
    for t in JIRA_MORE:
        if t["proj"] not in ok:
            print(f"  [skip] {t['basket_key']} — проект {t['proj']} недоступен")
            continue
        existing = _find_issue_by_label_summary(url, headers, t["proj"], t["summary"])
        if existing:
            key = existing["key"]
            print(f"  [reuse] {t['basket_key']} -> {key} «{t['summary']}»")
            out.append({**t, "jira_key": key})
            continue
        issuetype = _pick_issuetype(url, headers, t["proj"])
        s, body = _req("POST", f"{url}/rest/api/2/issue", headers, {"fields": {
            "project": {"key": t["proj"]}, "summary": t["summary"],
            "issuetype": {"name": issuetype}, "labels": [LABEL_DEMO, LABEL_BASKET],
            "description": (f"Синтетическая задача демо-контура Ouroboros (канон {t['basket_key']}). "
                            f"Роль-владелец: {t['role']}. Не рабочая задача."),
        }})
        if s not in (200, 201):
            print(f"  [create FAILED] {t['basket_key']} «{t['summary']}»: HTTP {s} {body}")
            continue
        key = body["key"]
        print(f"  [create] {t['basket_key']} -> {key} «{t['summary']}»")
        targets = _STATUS_TARGET.get(t["status"])
        if targets:
            tr = _find_transition(url, headers, key, targets)
            if tr:
                tid, tname = tr
                s2, _ = _req("POST", f"{url}/rest/api/2/issue/{key}/transitions", headers,
                             {"transition": {"id": tid}})
                print(f"    [transition] -> {tname!r}: HTTP {s2}")
        out.append({**t, "jira_key": key})
    return out


# ============================================================ Bitbucket: +8 PR
# branch + PR на diff-коммите; issue_key — реальный jira_key если есть, иначе basket_key.
def _bb_pr_exists(ws, slug, headers, title):
    s, body = _req("GET", f"{BB_BASE}/repositories/{ws}/{slug}/pullrequests?state=OPEN&pagelen=50", headers)
    if s != 200:
        return None
    for pr in body.get("values", []):
        if pr.get("title") == title:
            return pr
    return None


def seed_bitbucket_more(jira_map):
    """jira_map: {basket_key: jira_key} — для связи PR с Jira-задачами."""
    print("\n=== Bitbucket: +8 PR (до 10) ===")
    ws, slug, headers = _bb_cfg()
    if not ws:
        print("  [skip] BITBUCKET creds не заданы")
        return []
    main_sha = _bb_branch_sha(ws, slug, headers, "main")
    if not main_sha:
        print("  [skip] ветка main не найдена — запустите seed_bitbucket.py сначала")
        return []
    print(f"  repo: {ws}/{slug} · main={main_sha[:12]}")
    prs_spec = [
        {"title": "Кэш ППРБ", "branch": "feature/payment-cache",
         "issue": "APP-410", "file": "cache.txt", "content": b"pprb-cache v1 (demo)\n",
         "summary": "Кэш ППРБ: in-memory cache для ППРБ-сервис (демо Ouroboros)"},
        {"title": "Вебхуки ППРБ", "branch": "feature/payment-webhooks",
         "issue": "APP-413", "file": "webhooks.txt", "content": b"pprb-webhooks v1 (demo)\n",
         "summary": "Вебхуки ППРБ: обработка callback от партнёра (демо Ouroboros)"},
        {"title": "Реестр ППРБ", "branch": "feature/refund-registry",
         "issue": "APP-422", "file": "registry.txt", "content": b"pprb-registry v1 (demo)\n",
         "summary": "Реестр ППРБ: реестр + сверка (демо Ouroboros)"},
        {"title": "Метрики бизнес-операций", "branch": "feature/bizops-metrics",
         "issue": "APP-430", "file": "metrics.txt", "content": b"bizops-metrics v1 (demo)\n",
         "summary": "Метрики бизнес-операций: дашборд (демо Ouroboros)"},
        {"title": "Мониторинг ППРБ-адаптера", "branch": "feature/payment-monitoring",
         "issue": "OPS-79", "file": "monitoring.txt", "content": b"pprb-monitoring v1 (demo)\n",
         "summary": "Мониторинг ППРБ-адаптера: health-checks + алерты (демо Ouroboros)"},
        {"title": "Runbook релизов", "branch": "docs/release-runbook",
         "issue": "OPS-80", "file": "runbook.md", "content": "# Runbook релизов Альфа (demo)\n".encode("utf-8"),
         "summary": "Runbook релизов Альфа: пошаговый runbook для SRE (демо Ouroboros)"},
        {"title": "Postmortem 2026-06-30", "branch": "docs/postmortem-0630",
         "issue": "OPS-78", "file": "postmortem.md",
         "content": "# Postmortem инцидента 2026-06-30 (demo)\n".encode("utf-8"),
         "summary": "Postmortem инцидента 2026-06-30: разбор + action items (демо Ouroboros)"},
        {"title": "Архитектура ППРБ v2", "branch": "docs/payment-arch-v2",
         "issue": "APP-412", "file": "arch-v2.md",
         "content": "# Архитектура ППРБ v2 (demo)\n".encode("utf-8"),
         "summary": "Архитектура ППРБ v2: RFC + диаграммы (демо Ouroboros)"},
    ]
    out = []
    for spec in prs_spec:
        issue_key = jira_map.get(spec["issue"]) or spec["issue"]
        # ветка
        if _bb_branch_sha(ws, slug, headers, spec["branch"]):
            print(f"  [reuse branch] {spec['branch']}")
        else:
            mbody, ct = _bb_multipart(
                [("branch", spec["branch"]), ("parents", main_sha),
                 ("message", f"{spec['title']} (demo basket)")],
                [(f"demo/{spec['file']}", spec["file"], "text/plain", spec["content"])],
            )
            s, body = _req("POST", f"{BB_BASE}/repositories/{ws}/{slug}/src", headers, mbody, ct)
            if s not in (200, 201):
                err = json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else str(body)
                # ветка уже существует (из прерванного прогона) — переиспользуем, идём к PR
                if "not the head" in err or "already exists" in err.lower():
                    print(f"  [reuse branch] {spec['branch']} (exists, parent mismatch ignored)")
                else:
                    print(f"  [branch FAILED] {spec['branch']}: HTTP {s} {body}")
                    continue
        # PR
        existing = _bb_pr_exists(ws, slug, headers, spec["title"])
        if existing:
            pr_id = existing["id"]
            print(f"  [reuse PR] #{pr_id} «{spec['title']}»")
        else:
            s2, body2 = _req("POST", f"{BB_BASE}/repositories/{ws}/{slug}/pullrequests", headers, {
                "title": spec["title"], "source": {"branch": {"name": spec["branch"]}},
                "destination": {"branch": {"name": "main"}},
                "summary": {"raw": f"PR по {issue_key}: {spec['summary']}"},
                "close_source_branch": False,
            })
            if s2 not in (200, 201):
                print(f"  [PR FAILED] «{spec['title']}»: HTTP {s2} {body2}")
                continue
            pr_id = body2["id"]
            print(f"  [create PR] #{pr_id} «{spec['title']}» (issue={issue_key})")
        out.append({"title": spec["title"], "pr_id": pr_id, "branch": spec["branch"],
                    "issue_key": issue_key,
                    "url": f"https://bitbucket.org/{ws}/{slug}/pull-requests/{pr_id}"})
    return out


# ============================================================ Confluence: +8 страниц
def _conf_cfg():
    url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("CONFLUENCE_API_TOKEN") or os.environ.get("JIRA_API_TOKEN", "")
    if not (url and email and token):
        return None, None, None, None
    creds = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    return url, {"Authorization": f"Basic {creds}", "Accept": "application/json",
                 "Content-Type": "application/json"}, os.environ.get("CONFLUENCE_SPACE", ""), LABEL_DEMO


CONF_PAGES = [
    {"title": "RFC · ППРБ v2",
     "storage": "<h1>RFC · ППРБ v2</h1><p>Миграция на ППРБ на v2: разбиение на ППРБ-ядро + ППРБ-адаптер.</p><p>Owner: Разработчик backend. Срок: 03.07.</p>"},
    {"title": "Postmortem · Инцидент 2026-06-30",
     "storage": "<h1>Postmortem · Инцидент 2026-06-30</h1><p>Симптом: деградация ППРБ-адаптера 30.06 14:00–15:30.</p><p>Причина: исчерпание connection pool. Action items: OPS-79, APP-413.</p>"},
    {"title": "Runbook · Релизы Альфа",
     "storage": "<h1>Runbook · Релизы Альфа</h1><p>Окно: 18:00–20:00 (пятница исключена). Code freeze за 1 день.</p><p>Шаги: деплой → smoke → мониторинг → release-notes.</p>"},
    {"title": "Changelog · Альфа 2026.07",
     "storage": "<h1>Changelog · Альфа 2026.07</h1><ul><li>APP-412 миграция на ППРБ</li><li>APP-521 интеграция с партнёром</li><li>APP-421 репликация ППРБ</li></ul>"},
    {"title": "On-call · Альфа",
     "storage": "<h1>On-call · Альфа</h1><p>График: SRE (нечётные недели), SRE-2 (чётные).</p><p>Каналы: #alpha-oncall. Эскалация: Тимлид → Владелец продукта.</p>"},
    {"title": "Retrospective · Спринт 12",
     "storage": "<h1>Retrospective · Спринт 12</h1><p>Что хорошо: релиз 03.07 в срок. Что улучшить: связь с SRE по ППРБ-адаптеру раньше.</p>"},
    {"title": "Architecture · ППРБ",
     "storage": "<h1>Architecture · ППРБ</h1><p>Компоненты: ППРБ-ядро, ППРБ-адаптер, partner-api. Зависимости: partner-api (внешний).</p>"},
    {"title": "Test Plan · Альфа 2026.07",
     "storage": "<h1>Test Plan · Альфа 2026.07</h1><p>Smoke: ППРБ-ядро e2e. Регресс: реплики, вебхуки. Нагрузка: 100 RPS.</p>"},
]


def _conf_find_personal_space(url, headers):
    s, body = _req("GET", f"{url}/wiki/rest/api/space?limit=25&type=personal", headers)
    if s == 200:
        for sp in body.get("results", []):
            if sp.get("type") == "personal":
                return sp["key"]
    return None


def _conf_find_page(url, headers, cql):
    s, body = _req("GET", f"{url}/wiki/rest/api/content/search?cql={urllib.parse.quote(cql)}&expand=version", headers)
    if s != 200:
        return {}
    found = {}
    for p in body.get("results", []):
        found[p["title"]] = p
    return found


def _conf_find_by_title(url, headers, space, title):
    """Fallback: поиск страницы по title в пространстве. CQL с title="..." ломается
    на кириллице/спецсимволах (·, —), поэтому берём все страницы space и фильтруем в Python."""
    cql = f'space="{space}" AND type=page' if space else "type=page"
    s, body = _req("GET", f"{url}/wiki/rest/api/content/search?cql={urllib.parse.quote(cql)}"
                   "&limit=50&expand=version", headers)
    if s != 200:
        return None
    for p in body.get("results", []):
        if p.get("title") == title:
            return p
    return None


def seed_confluence_more():
    print("\n=== Confluence: +8 страниц (до 10) ===")
    url, headers, space, label = _conf_cfg()
    if not url:
        print("  [skip] CONFLUENCE creds не заданы")
        return []
    personal = space.startswith("~") if space else False
    if not space:
        space = _conf_find_personal_space(url, headers)
        print(f"  [discover] личное пространство: {space}")
    cql = (f'space="{space}" AND label="{label}"') if (space and not personal) else f'label="{label}"'
    existing = _conf_find_page(url, headers, cql)
    print(f"  [search] найдено {len(existing)} alpha-demo страниц")
    seeded = {}
    for p in CONF_PAGES:
        if p["title"] in existing:
            pid = str(existing[p["title"]]["id"])
            print(f"  [reuse page] {pid} «{p['title']}»")
            seeded[p["title"]] = pid
            continue
        s2, body2 = _req("POST", f"{url}/wiki/rest/api/content", headers, {
            "type": "page", "title": p["title"], "space": {"key": space},
            "body": {"storage": {"value": p["storage"], "representation": "storage"}},
        })
        if s2 not in (200, 201):
            err = json.dumps(body2, ensure_ascii=False) if isinstance(body2, dict) else str(body2)
            # страница уже существует, но CQL по label её не нашёл — ищем по title
            if "already exists" in err.lower():
                found = _conf_find_by_title(url, headers, space, p["title"])
                if found:
                    pid = str(found["id"])
                    # повесим label (если ещё нет)
                    _req("POST", f"{url}/wiki/rest/api/content/{pid}/label", headers,
                         [{"prefix": "global", "name": label}])
                    print(f"  [reuse page] {pid} «{p['title']}» (found by title, label added)")
                    seeded[p["title"]] = pid
                    continue
            print(f"  [page FAILED] «{p['title']}»: HTTP {s2} {body2}")
            continue
        pid = str(body2["id"])
        _req("POST", f"{url}/wiki/rest/api/content/{pid}/label", headers, [{"prefix": "global", "name": label}])
        print(f"  [create page] {pid} «{p['title']}»")
        seeded[p["title"]] = pid
    return {"space": space, "pages": seeded}


# ============================================================ Gmail: +6 писем
MAIL_MORE = [
    {"basket_id": "more-1", "role": "Разработчик backend", "subject": "Release-notes APP-412 готовы",
     "body": "Release-notes по APP-412 (Миграция на ППРБ) готовы, залил в Confluence. (Синтетика Ouroboros, from backend.)"},
    {"basket_id": "more-2", "role": "Разработчик frontend", "subject": "Деплой partner-api завершён",
     "body": "Partner-api задеплоен в prod, интеграция APP-521 проверена. (Синтетика Ouroboros, from frontend.)"},
    {"basket_id": "more-3", "role": "SRE", "subject": "Postmortem 2026-06-30 готов",
     "body": "Postmortem инцидента 2026-06-30 готов, action items: OPS-79, APP-413. (Синтетика Ouroboros, from SRE.)"},
    {"basket_id": "more-4", "role": "SRE", "subject": "Runbook релизов обновлён",
     "body": "Runbook релизов Альфа обновлён, добавлен шаг smoke-теста ППРБ-ядро. (Синтетика Ouroboros, from SRE.)"},
    {"basket_id": "more-5", "role": "Разработчик backend", "subject": "Запрос на ревью PR Кэш ППРБ",
     "body": "PR «Кэш ППРБ» готов к ревью, нужен аппрув до 03.07. (Синтетика Ouroboros, from backend.)"},
    {"basket_id": "more-6", "role": "Владелец продукта", "subject": "Согласование окна релиза 10.07",
     "body": "Согласуем окно релиза 10.07 18:00–20:00, пятница исключена по регламенту. (Синтетика Ouroboros, from PM.)"},
]


def _imap_has_subject(acct, pwd, subject):
    import imaplib, email as _email, email.header as _h
    try:
        box = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        try:
            box.login(acct, pwd)
            box.select("INBOX")
            typ, data = box.search(None, "ALL")
            ids = (data[0] or b"").split()[-60:]
            for mid in ids:
                typ, md = box.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
                if typ == "OK" and md and md[0]:
                    raw = md[0][1] if isinstance(md[0], tuple) else md[0]
                    msg = _email.message_from_bytes(raw)
                    dec = ""
                    for enc, cs in _h.decode_header(msg.get("Subject", "")):
                        dec += enc.decode(cs or "utf-8", "replace") if isinstance(enc, bytes) else enc
                    if subject.lower() in dec.lower():
                        return True
            return False
        finally:
            try:
                box.logout()
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001
        print(f"  [imap check] {e}")
        return False


def seed_gmail_more():
    print("\n=== Gmail: +6 писем (до 11+) ===")
    acct = os.environ.get("GOOGLE_ACCOUNT", "")
    pwd = os.environ.get("GOOGLE_APP_PASSWORD", "")
    if not (acct and pwd):
        print("  [skip] GOOGLE creds не заданы")
        return []
    sent = []
    for m in MAIL_MORE:
        if _imap_has_subject(acct, pwd, m["subject"]):
            print(f"  [reuse] «{m['subject']}» уже в Inbox")
            sent.append({**m, "status": "reused"})
            continue
        msg = EmailMessage()
        msg["From"] = acct
        msg["To"] = acct
        msg["Subject"] = m["subject"]
        msg["X-Athanor-Role"] = m["role"]
        msg["X-Athanor-Basket"] = m["basket_id"]
        msg.set_content(m["body"])
        try:
            import smtplib
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
                s.starttls()
                s.login(acct, pwd)
                s.send_message(msg)
            print(f"  [send] «{m['subject']}» (role={m['role']})")
            sent.append({**m, "status": "sent"})
        except Exception as e:  # noqa: BLE001
            print(f"  [send FAILED] «{m['subject']}»: {e}")
            sent.append({**m, "status": f"failed: {e}"})
    return sent


# ============================================================ Calendar: .ics (10 событий)
CAL_EVENTS = [
    # — Июнь: разбор инцидента + postmortem + code freeze перед релизом 03.07 —
    {"uid": "alpha-incident-3006@athanor", "summary": "Разбор инцидента · Альфа",
     "dtstart": "20260630T110000", "dtend": "20260630T120000",
     "desc": "Разбор инцидента 30.06: деградация ППРБ-адаптера 14:00–15:30."},
    {"uid": "alpha-postmortem-0107@athanor", "summary": "Postmortem-митинг · Альфа",
     "dtstart": "20260701T110000", "dtend": "20260701T120000",
     "desc": "Postmortem-митинг по инциденту 30.06."},
    {"uid": "alpha-freeze-0207@athanor", "summary": "Code freeze · Альфа",
     "dtstart": "20260702T120000", "dtend": "20260702T180000",
     "desc": "Code freeze перед релизом ALPHA-2026.07."},
    # — Неделя 03.07 (много встреч: Релиз-синк + 6 рабочих встреч 06–09.07) —
    {"uid": "alpha-rs-0307@athanor", "summary": "Релиз-синк · Альфа",
     "dtstart": "20260703T140000", "dtend": "20260703T150000",
     "desc": "Релиз-синк проекта Альфа (ALPHA-2026.07). 5 участников: Тимлид, SRE, Владелец продукта, Разработчик backend, Разработчик frontend."},
    {"uid": "alpha-retro-0607@athanor", "summary": "Ретроспектива · Альфа",
     "dtstart": "20260706T110000", "dtend": "20260706T120000",
     "desc": "Ретроспектива спринта 12 по проекту Альфа. (Перенесена с 05.07 — воскресенье, выходной.)"},
    {"uid": "alpha-daily-0607@athanor", "summary": "Daily стендап · Альфа",
     "dtstart": "20260706T160000", "dtend": "20260706T161500",
     "desc": "Daily стендап команды Альфа: статус по ППРБ-миграции, блокеры."},
    {"uid": "alpha-sprint-0707@athanor", "summary": "Планирование спринта · Альфа",
     "dtstart": "20260707T120000", "dtend": "20260707T130000",
     "desc": "Планирование спринта 13 по проекту Альфа."},
    {"uid": "alpha-sre-sync-0707@athanor", "summary": "Синхронизация с SRE · Альфа",
     "dtstart": "20260707T160000", "dtend": "20260707T163000",
     "desc": "Синхронизация с SRE по деплою ППРБ-адаптера в production."},
    {"uid": "alpha-blockers-0807@athanor", "summary": "Разбор блокеров · Альфа",
     "dtstart": "20260708T110000", "dtend": "20260708T113000",
     "desc": "Разбор блокеров релиза ALPHA-2026.07: ППРБ-адаптер, partner-api."},
    {"uid": "alpha-demo-0807@athanor", "summary": "Демо для заказчика · Альфа",
     "dtstart": "20260708T150000", "dtend": "20260708T160000",
     "desc": "Демо релиза ALPHA-2026.07 (Миграция на ППРБ) для заказчика. (Перенесено с 12.07 — воскресенье, выходной.)"},
    {"uid": "alpha-review-0907@athanor", "summary": "Код-ревью синк · Альфа",
     "dtstart": "20260709T100000", "dtend": "20260709T103000",
     "desc": "Синк по код-ревью PR: Миграция на ППРБ, Репликация ППРБ, Вебхуки ППРБ."},
    # — Следующие недели: релиз-синки по пятницам + демо —
    {"uid": "alpha-rs-1007@athanor", "summary": "Релиз-синк · Альфа",
     "dtstart": "20260710T140000", "dtend": "20260710T150000",
     "desc": "Релиз-синк проекта Альфа (ALPHA-2026.10)."},
    {"uid": "alpha-rs-1707@athanor", "summary": "Релиз-синк · Альфа",
     "dtstart": "20260717T140000", "dtend": "20260717T150000",
     "desc": "Релиз-синк проекта Альфа (ALPHA-2026.12)."},
    {"uid": "alpha-rs-2407@athanor", "summary": "Релиз-синк · Альфа",
     "dtstart": "20260724T140000", "dtend": "20260724T150000",
     "desc": "Релиз-синк проекта Альфа (ALPHA-2026.14)."},
]


def _ics_escape(text: str) -> str:
    r"""Экранирование TEXT по RFC 5545: \ , ; и переводы строк."""
    return (text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
            .replace("\n", "\\n"))


def _dt_to_csv(dt: str) -> tuple[str, str]:
    """20260703T140000 → ('07/03/2026', '02:00 PM') — формат Google Calendar CSV."""
    y, m, d, hh, mm = dt[:4], dt[4:6], dt[6:8], dt[9:11], dt[11:13]
    date = f"{m}/{d}/{y}"
    h = int(hh)
    suffix = "AM" if h < 12 else "PM"
    h12 = h if h <= 12 else h - 12
    if h12 == 0:
        h12 = 12
    time = f"{h12}:{mm} {suffix}"
    return date, time


def gen_calendar_csv():
    """CSV для импорта в Google Calendar — надёжнее .ics для кириллицы.

    Google Calendar .ics-импорт иногда читает UTF-8 как Latin-1 → mojibake в
    русских названиях. CSV с UTF-8 BOM импортируется корректно. Формат:
    Subject, Start Date, Start Time, End Date, End Time, All Day Event,
    Description, Location, Private
    """
    print(f"\n=== Calendar: .csv с {len(CAL_EVENTS)} событиями (UTF-8 BOM, для Google Calendar) ===")
    out_dir = REPO / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv = out_dir / "calendar_alpha.csv"
    import csv as _csv
    rows = [["Subject", "Start Date", "Start Time", "End Date", "End Time",
             "All Day Event", "Description", "Location", "Private"]]
    for ev in CAL_EVENTS:
        sd, st = _dt_to_csv(ev["dtstart"])
        ed, et = _dt_to_csv(ev["dtend"])
        rows.append([ev["summary"], sd, st, ed, et, "False", ev["desc"], "", "True"])
    with csv.open("w", encoding="utf-8-sig", newline="") as f:
        _csv.writer(f).writerows(rows)
    print(f"  [saved] {csv} ({len(CAL_EVENTS)} событий, UTF-8 BOM)")
    print("  ИМПОРТ В GOOGLE CALENDAR (рекомендуемый путь для кириллицы):")
    print("  Settings → Import & export → Import → выберите examples/calendar_alpha.csv →")
    print("  выберите календарь (athanorproject2026) → Import. CSV с UTF-8 BOM импортирует")
    print("  кириллицу корректно (в отличие от .ics, где Google Calendar иногда даёт mojibake).")
    return {"csv": str(csv.relative_to(REPO)), "events": len(CAL_EVENTS)}


def gen_calendar_ics():
    print(f"\n=== Calendar: .ics с {len(CAL_EVENTS)} событиями (все на рабочих днях) ===")
    out_dir = REPO / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    ics = out_dir / "calendar_alpha_10.ics"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Athanor//Ouroboros demo//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Альфа (демо Ouroboros)",
        "X-WR-TIMEZONE:UTC",
    ]
    for ev in CAL_EVENTS:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}",
            "DTSTAMP:20260701T000000Z",
            f"DTSTART:{ev['dtstart']}",
            f"DTEND:{ev['dtend']}",
            f"SUMMARY:{_ics_escape(ev['summary'])}",
            f"DESCRIPTION:{_ics_escape(ev['desc'])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # UTF-8 with BOM — иначе Google Calendar может читать кириллицу как Latin-1 (абракадабра).
    # CRLF — стандарт RFC 5545 для .ics.
    with ics.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    print(f"  [saved] {ics} ({len(CAL_EVENTS)} событий, UTF-8 BOM, CRLF, TEXT escaped)")
    print("  Импорт в Google Calendar: Settings → Import & export → Import calendar →")
    print("  выберите examples/calendar_alpha_10.ics → выберите календарь (athanorproject2026) → Import.")
    print("  ВАЖНО: UTF-8 BOM обязателен для кириллицы (без BOM Google Calendar читает Latin-1 → абракадабра).")
    print("  Если ранее импортировали старый .ics (без BOM) — удалите события с абракадаброй перед переимпортом.")
    print("  После импорта события станут live — iCal URL (GOOGLE_ICAL_URL) начнёт их отдавать.")
    return {"ics": str(ics.relative_to(REPO)), "events": len(CAL_EVENTS)}


# ============================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*",
                    default=None,
                    help="подмножество: jira bitbucket confluence gmail calendar (по умолчанию все)")
    args = ap.parse_args()
    only = set(args.only) if args.only else {"jira", "bitbucket", "confluence", "gmail", "calendar"}
    print("=== Расширение сидинга до 10+ сущностей в каждой системе ===")
    print(f"--only: {sorted(only)}")

    jira_more, jira_map, bb, conf, mail, cal = [], {}, [], {}, [], {}
    if "jira" in only:
        jira_more = seed_jira_more()
        jira_map = {t["basket_key"]: t["jira_key"] for t in jira_more if t.get("jira_key")}
    # маппинг из basket_seeded.json (если есть) — нужен для Bitbucket даже без Jira
    bs = REPO / "results" / "basket_seeded.json"
    if bs.is_file():
        data = json.loads(bs.read_text(encoding="utf-8"))
        for t in data.get("jira", {}).get("tasks", []):
            jira_map.setdefault(t["basket_key"], t["jira_key"])
    if "bitbucket" in only:
        bb = seed_bitbucket_more(jira_map)
    if "confluence" in only:
        conf = seed_confluence_more()
    if "gmail" in only:
        mail = seed_gmail_more()
    if "calendar" in only:
        cal_ics = gen_calendar_ics()
        cal_csv = gen_calendar_csv()
        cal = {"ics": cal_ics, "csv": cal_csv}

    out = {"jira_more": jira_more, "jira_map": jira_map, "bitbucket_more": bb,
           "confluence_more": conf, "gmail_more": mail, "calendar": cal if isinstance(cal, dict) else cal}
    outpath = REPO / "results" / "more_seeded.json"
    outpath.parent.mkdir(parents=True, exist_ok=True)
    # merge с предыдущим прогоном (если --only запускали частями)
    if outpath.is_file():
        try:
            prev = json.loads(outpath.read_text(encoding="utf-8"))
            for k, v in out.items():
                if v:
                    prev[k] = v
            out = prev
        except Exception:
            pass
    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Итог ===")
    print(f"  Jira: +{len(jira_more)} задач (всего basket: {5 + len(jira_more)} + KAN-1/2 = {7 + len(jira_more)})")
    print(f"  Bitbucket: +{len(bb)} PR (всего {2 + len(bb)})")
    print(f"  Confluence: +{len(conf.get('pages', {})) if isinstance(conf, dict) else 0} страниц")
    print(f"  Gmail: +{sum(1 for m in mail if isinstance(m, dict) and m.get('status') in ('sent', 'reused'))} писем")
    if isinstance(cal, dict) and cal.get("ics", {}).get("events"):
        print(f"  Calendar: .ics + .csv с {cal['ics']['events']} событиями (CSV — рекомендуемый импорт для кириллицы)")
    print(f"\n[saved] {outpath}")


if __name__ == "__main__":
    main()
