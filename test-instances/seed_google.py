"""Сидинг синтетики «Альфа» в реальный mail (SMTP + пароль приложения).

Отправляет в mail (GOOGLE_ACCOUNT из .env, по умолчанию athanor-demo@gmail.com) письмо-блокер «Блокер по KAN-1: ППРБ-адаптер
не в prod» (from SRE, заголовок X-Athanor-Role: SRE) — попадает в Inbox. Идемпотентно:
при повторном запуске переотправляет (mail не даёт искать перед отправкой; дубли
фильтруются на чтении по теме). Событие календаря создаётся вручную в Calendar
(см. README) — скрипт только проверяет, что iCal URL отдаёт событие «Альфа».

Запуск: python test-instances/seed_google.py
Требует .env: GOOGLE_ACCOUNT, GOOGLE_APP_PASSWORD, (опц.) GOOGLE_ICAL_URL.
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.strip().startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().split(" #")[0].strip())


_load_env(REPO / ".env")
ACCOUNT = os.environ.get("GOOGLE_ACCOUNT", "")
PWD = os.environ.get("GOOGLE_APP_PASSWORD", "")
MAIL_SUBJECT = "Блокер по KAN-1: ППРБ-адаптер не в prod"


def main() -> int:
    if not ACCOUNT or not PWD:
        sys.exit("GOOGLE_ACCOUNT/GOOGLE_APP_PASSWORD не заданы в .env")
    print(f"=== Сидинг mail: {ACCOUNT} ===\n")

    # 1) письмо-блокер (SMTP → себе в Inbox)
    msg = EmailMessage()
    msg["From"] = ACCOUNT
    msg["To"] = ACCOUNT
    msg["Subject"] = MAIL_SUBJECT
    msg["X-Athanor-Role"] = "SRE"
    msg.set_content(
        "KAN-1: смежный сервис ППРБ-адаптер не задеплоен в production, "
        "релизное окно под риском, деплой заблокирован. "
        "(Синтетическое демо-письмо Ouroboros, from SRE.)")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.starttls()
        s.login(ACCOUNT, PWD)
        s.send_message(msg)
    print(f"[send mail] {MAIL_SUBJECT!r} → {ACCOUNT} (в Inbox + Sent)")

    # 2) проверка календаря (если задан iCal URL)
    ical = os.environ.get("GOOGLE_ICAL_URL", "")
    if ical:
        sys.path.insert(0, str(REPO / "mcp"))
        import _backends as B  # noqa: E402
        try:
            evs = B.google_calendar_events()
            print(f"\n[calendar] {len(evs)} событие «Альфа» из iCal URL:")
            for e in evs:
                print(f"    {e['title']} @ {e['datetime']}  participants={len(e['participants'])}")
        except Exception as e:
            print(f"\n[calendar] не удалось прочитать iCal: {e}")
            print("  Создайте событие вручную в Calendar и сделайте календарь публичным.")
    else:
        print("\n[calendar] GOOGLE_ICAL_URL не задан — создайте событие вручную (см. README).")

    print(f"\nТеперь: MCP_BACKEND=live python mcp/serve_all.py  (Jira + mail + Calendar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
