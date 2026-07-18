# -*- coding: utf-8 -*-
"""Добавление писем с ППРБ в Gmail Inbox через IMAP APPEND (SMTP-порты блокированы).

SMTP 465/587 таймаутят на handshake с этой машины (блокировка портов), но IMAP 993
работает. IMAP APPEND помещает RFC822-сообщение прямо в Inbox — gmail_mail() (агент)
прочитает его через IMAP, как и обычные письма. Честно: реальный Gmail-ящик, реальные
письма в Inbox, реальная IMAP-читалка; отличие только в методе доставки (APPEND вместо
SMTP — порты SMTP заблокированы сетью)."""
import os, imaplib, time
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
import sys
REPO = Path(r"D:\d\ouroboros\athanor-release-sync")
sys.path.insert(0, str(REPO / "test-instances"))
for l in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    if l.strip() and not l.strip().startswith("#") and "=" in l:
        k, _, v = l.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
acct = os.environ["GOOGLE_ACCOUNT"]
pwd = os.environ["GOOGLE_APP_PASSWORD"]

from seed_basket import MAIL_MESSAGES as BASKET  # noqa: E402
from seed_more import MAIL_MORE as MORE  # noqa: E402

DEMO = [{"basket_id": "demo", "role": "SRE",
         "subject": "Блокер по KAN-1: ППРБ-адаптер не в prod",
         "body": "KAN-1: смежный сервис ППРБ-адаптер не задеплоен в production, "
                 "релизное окно под риском, деплой заблокирован. (Синтетическое демо-письмо Ouroboros, from SRE.)"}]

ALL = DEMO + BASKET + MORE
print(f"IMAP APPEND {len(ALL)} писем в {acct}/INBOX")


def _msg_bytes(m):
    msg = EmailMessage()
    msg["From"] = acct
    msg["To"] = acct
    msg["Subject"] = m["subject"]
    msg["Date"] = formatdate(timeval=time.time(), localtime=False)
    msg["X-Athanor-Role"] = m["role"]
    msg["X-Athanor-Basket"] = m.get("basket_id", "")
    msg.set_content(m["body"])
    return msg.as_bytes()


box = imaplib.IMAP4_SSL("imap.gmail.com", 993)
box.login(acct, pwd)
appended = failed = 0
for m in ALL:
    for attempt in range(3):
        try:
            typ, data = box.append("INBOX", "", imaplib.Time2Internaldate(time.time()), _msg_bytes(m))
            if typ == "OK":
                appended += 1
                print(f"  [OK] «{m['subject']}» (role={m['role']})")
                break
            else:
                print(f"  [FAIL] «{m['subject']}»: {typ} {data}")
                failed += 1
                break
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                print(f"  [FAIL] «{m['subject']}»: {type(e).__name__}: {e}")
                failed += 1
box.logout()
print(f"\nИтого: добавлено {appended}/{len(ALL)} в INBOX, failed={failed}")
