"""OAuth2 device code flow для личного Microsoft-аккаунта (Outlook.com).

Личные Outlook.com-ящики не поддерживают Basic-auth/IMAP-пароль — только OAuth2.
Скрипт выполняет device code flow ОДИН раз (интерактивно), получает refresh_token
и сохраняет его в .env. Дальше mcp/_backends.py (MCP_BACKEND=microsoft) обновляет
access-токены по refresh-токену без повторного входа.

Запуск: python test-instances/ms_auth.py
Требует в .env: MS_CLIENT_ID (из регистрации приложения в Azure, см. README).
Область (scope): Mail.ReadWrite, Mail.Send, Calendars.ReadWrite, offline_access.
Tenant: consumers (личные Microsoft-аккаунты).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCOPE = ("https://graph.microsoft.com/Mail.ReadWrite "
         "https://graph.microsoft.com/Mail.Send "
         "https://graph.microsoft.com/Calendars.ReadWrite "
         "offline_access")


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().split(" #")[0].strip())


def _save_to_env(path: Path, key: str, value: str) -> None:
    """Записать key=value в .env (обновить существующее или дописать)."""
    lines = []
    found = False
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line.rstrip("\n"))
    if not found:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"# {key} — added by ms_auth.py (device code flow)")
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    _load_env(REPO / ".env")
    client_id = os.environ.get("MS_CLIENT_ID", "").strip()
    if not client_id:
        sys.exit("MS_CLIENT_ID не задан в .env. Зарегистрируйте приложение в Azure "
                 "(см. test-instances/README.md) и впишите Client ID в .env как MS_CLIENT_ID.")
    tenant = os.environ.get("MS_TENANT", "consumers")
    account = os.environ.get("MS_ACCOUNT", "athanor-demo@outlook.com")
    env_path = REPO / ".env"

    print(f"=== Microsoft Graph device code flow ===")
    print(f"  tenant={tenant} · account={account} · client_id={client_id[:8]}…")
    print(f"  scope: {SCOPE}\n")

    # 1) запрашиваем device code
    dc = _post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
               {"client_id": client_id, "scope": SCOPE})
    user_code = dc["user_code"]
    device_code = dc["device_code"]
    verify_url = dc.get("verification_uri", "https://microsoft.com/devicelogin")
    expires_in = dc.get("expires_in", 900)
    interval = dc.get("interval", 5)
    print(f"➡  Откройте в браузере:  {verify_url}")
    print(f"➡  Введите код:          {user_code}")
    print(f"➡  Войдите как           {account}")
    print(f"   и согласитесь с разрешениями (Mail/Calendars/Send).\n")
    print(f"   (код действителен {expires_in // 60} мин; ожидаем вход…)\n")

    # 2) опрашиваем /token
    deadline = time.time() + expires_in
    last_err = ""
    while time.time() < deadline:
        time.sleep(interval)
        try:
            tok = _post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                        {"client_id": client_id, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                         "device_code": device_code, "scope": SCOPE})
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode("utf-8", "replace"))
            err = body.get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            if err in ("authorization_declined", "expired_token", "bad_verification_code"):
                sys.exit(f"OAuth2 не удалось: {err} — {body.get('error_description','')}")
            last_err = f"{err}: {body.get('error_description','')}"
            continue
        access = tok["access_token"]
        refresh = tok.get("refresh_token", "")
        _save_to_env(env_path, "MS_REFRESH_TOKEN", refresh)
        if "MS_ACCOUNT" not in (env_path.read_text(encoding="utf-8") if env_path.is_file() else ""):
            _save_to_env(env_path, "MS_ACCOUNT", account)
        print("✅ Готово! Получен access + refresh токен.")
        print(f"   MS_REFRESH_TOKEN сохранён в .env (длина {len(refresh)} симв.).")
        print(f"   access_token действует {tok.get('expires_in',3600)} c; обновится автоматически.")
        print(f"\nТеперь:")
        print(f"  python test-instances/seed_microsoft.py    # создать событие + письмо-блокер")
        print(f"  MCP_BACKEND=live python mcp/serve_all.py   # Jira + Outlook через MCP")
        # быстрый sanity-запрос к Graph
        try:
            req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
                                         headers={"Authorization": f"Bearer {access}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                me = json.loads(r.read().decode("utf-8"))
            print(f"\n[sanity] Graph /me → {me.get('userPrincipalName') or me.get('mail') or me.get('displayName')}")
        except Exception as e:
            print(f"[sanity] Graph /me: {e}")
        return 0
    sys.exit(f"Время ожидания истекло. {last_err}")


if __name__ == "__main__":
    raise SystemExit(main())
