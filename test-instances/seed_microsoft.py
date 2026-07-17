"""Сидинг синтетики «Альфа» в реальный Outlook.com (Microsoft Graph).

Создаёт в календаре (MS_ACCOUNT из .env, по умолчанию athanor-demo@outlook.com) событие «Релиз-синк · Альфа» (03.07 14:00)
и отправляет себе письмо-блокер «Блокер по KAN-1: payment-adapter не в prod»
(попадает в Inbox). Идемпотентно: при повторном запуске переиспользует существующее
событие/письмо по теме.

Запуск: python test-instances/seed_microsoft.py
Требует .env: MS_CLIENT_ID, MS_REFRESH_TOKEN (после ms_auth.py), MS_ACCOUNT.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "mcp"))
import _backends as B  # noqa: E402


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.strip().startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().split(" #")[0].strip())


_load_env(REPO / ".env")
ACCOUNT = os.environ.get("MS_ACCOUNT", "athanor-demo@outlook.com")
EVENT_SUBJECT = "Релиз-синк · Альфа"
MAIL_SUBJECT = "Блокер по KAN-1: payment-adapter не в prod"


def _graph_post(path: str, body: dict) -> dict:
    token = B._ms_access_token()
    req = urllib.request.Request(f"https://graph.microsoft.com/v1.0{path}",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:500]}


def _graph_get(path: str) -> dict:
    return B._ms_graph_get(path)


def _find_event() -> str | None:
    try:
        data = _graph_get("/me/events?$select=id,subject&$top=50")
    except Exception as e:
        print(f"[find event] {e}")
        return None
    for e in data.get("value", []):
        if EVENT_SUBJECT in (e.get("subject") or ""):
            return e["id"]
    return None


def _mail_exists() -> bool:
    try:
        from urllib.parse import quote
        data = _graph_get(f"/me/messages?$select=subject&$top=50&$filter="
                          f"{quote('startswith(subject, ') + quote(chr(39) + MAIL_SUBJECT.split(':')[0] + chr(39))}")
    except Exception:
        # $filter на messages может быть ограничен; запасной путь — листаем инбокс
        try:
            data = _graph_get("/me/messages?$select=subject&$top=50")
        except Exception as e:
            print(f"[find mail] {e}")
            return False
    for m in data.get("value", []):
        if "payment-adapter" in (m.get("subject") or ""):
            return True
    return False


def main() -> int:
    if not os.environ.get("MS_CLIENT_ID") or not os.environ.get("MS_REFRESH_TOKEN"):
        sys.exit("MS_CLIENT_ID/MS_REFRESH_TOKEN не заданы. Сначала python test-instances/ms_auth.py")
    print(f"=== Сидинг Outlook.com: {ACCOUNT} ===\n")

    # 1) событие календаря
    eid = _find_event()
    if eid:
        print(f"[reuse event] {EVENT_SUBJECT!r} уже в календаре (id={eid[:12]}…)")
    else:
        body = {
            "subject": EVENT_SUBJECT,
            "body": {"contentType": "Text", "content":
                     "Релиз-синк проекта Альфа, релиз ALPHA-2026.07. "
                     "Участники: Тимлид, SRE, Владелец продукта, Разработчик backend, Разработчик frontend. "
                     "Синтетическое демо-событие Ouroboros."},
            "start": {"dateTime": "2026-07-03T14:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2026-07-03T15:00:00", "timeZone": "UTC"},
            "location": {"displayName": "Альфа · релизная комната"},
        }
        s, resp = _graph_post("/me/events", body)
        if s in (200, 201):
            print(f"[create event] {EVENT_SUBJECT!r} → id={resp.get('id','?')[:12]}…")
        else:
            print(f"[create event FAILED] HTTP {s} {resp}")
            sys.exit(1)

    # 2) письмо-блокер (отправляем себе → попадает в Inbox)
    if _mail_exists():
        print(f"[reuse mail] {MAIL_SUBJECT!r} уже в ящике")
    else:
        mail = {
            "message": {
                "subject": MAIL_SUBJECT,
                "body": {"contentType": "Text", "content":
                         f"KAN-1: смежный сервис payment-adapter не задеплоен в production, "
                         f"релизное окно под риском, деплой заблокирован. "
                         f"(Синтетическое демо-письмо Ouroboros, from SRE.)"},
                "toRecipients": [{"emailAddress": {"address": ACCOUNT}}],
                "from": {"emailAddress": {"name": "SRE", "address": ACCOUNT}},
            },
            "saveToSentItems": True,
        }
        s, resp = _graph_post("/me/sendMail", mail)
        if s in (202, 200, 201):
            print(f"[send mail] {MAIL_SUBJECT!r} → {ACCOUNT} (в Inbox + Sent)")
        else:
            print(f"[send mail FAILED] HTTP {s} {resp}")
            sys.exit(1)

    # 3) проверка
    print("\n=== Итог (из реального Graph) ===")
    evs = B.graph_events_ms()
    print(f"  calendar: {len(evs)} событие «Альфа»")
    for e in evs:
        print(f"    {e['title']} @ {e['datetime']}  participants={len(e['participants'])}")
    mails = B.graph_mail_ms()
    print(f"  mail: {len(mails)} письмо «Альфа»")
    for m in mails:
        print(f"    [{m['id'][:8]}…] {m['subject']}  from={m['from_role']}  {m['date']}")
    print(f"\nТеперь: MCP_BACKEND=live python mcp/serve_all.py  (Jira + Outlook через MCP)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
