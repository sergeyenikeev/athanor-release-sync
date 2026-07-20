# MCP-инструменты

Четыре MCP-сервера (streamable_http, JSON-RPC 2.0) — `mcp/`. Три режима данных:

- **Live-интеграции** (`MCP_BACKEND=live`, по умолчанию) — реальные Jira/Bitbucket/
  Confluence/Google (mail+calendar) через `mcp/_backends.py`; сидинг синтетики «Альфа» —
  `test-instances/seed_*.py`. Расшифровки — файлы кейса (внешнего API нет).
- **Тестовые инстансы** (`MCP_BACKEND=test`) — MCP-адаптеры `mcp/_backends.py`
  ходят к локальным тестовым инстансам `test-instances/` по **реальным контрактам**
  Jira REST v2, Bitbucket Cloud REST 2.0, Confluence REST API v1 и конвертируют
  ответы в схему агента. Calendar/mail в test-режиме — файлы. Офлайн, детерминированно.
- **Файловый демо-контур** (`MCP_BACKEND=file`) — обезличенные выгрузки из папки
  кейса (`MCP_CASE_DIR`, по умолчанию `examples/demo_case`). Офлайн-демо.

mail/Calendar — Google (IMAP + публичный iCal URL), без Azure/OAuth.

## Серверы и инструменты
| Сервер | Порт | Инструменты | Файл (по умолч.) | `MCP_BACKEND=test` |
|---|---|---|---|---|
| calendar_mail | 9901 | `get_events`, `get_mail` | `calendar.json`, `mail.json` | (calendar/mail → файл; live: Google iCal/IMAP) |
| tracker_repo | 9902 | `get_issues`, `get_prs` | `tracker.json` | Jira `/rest/api/2/search` + Bitbucket `/repositories/.../pullrequests` |
| transcripts | 9903 | `get_transcript(case_id)` (при `MCP_TRANSCRIPTS_DOWN=1` — ошибка → деградация) | `transcript.txt` | (без изменений) |
| confluence | 9904 | `get_confluence_pages(space?, label?)` | `confluence.json` | Confluence `/wiki/rest/api/content/search` (CQL) |

## Запуск
```bash
# файловый демо-контур (по умолчанию)
python mcp/serve_all.py                                   # все четыре, данные examples/demo_case
MCP_CASE_DIR=test-basket/TB-03 python mcp/serve_all.py    # данные конкретного кейса

# тестовые инстансы (реальные контракты Jira/Bitbucket/Confluence; mail/Calendar — Google)
python test-instances/serve_all.py                        # порты 9911-9914 (терминал 1)
MCP_BACKEND=test python mcp/serve_all.py                  # MCP-адаптеры → тестовые инстансы (терминал 2)

python mcp/smoke_test.py                                  # initialize + tools/list + tools/call
```

## Прогон через MCP
```bash
python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
MCP_BACKEND=test python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
```
Без `--via-mcp` данные читаются из файлов кейса напрямую (офлайн). С `--via-mcp` —
через MCP-серверы. С `MCP_BACKEND=test` MCP-серверы ходят к тестовым инстансам.

## Конфиг для Ouroboros
`mcp/mcp_config.json` — объявление серверов для Settings → MCP:
```json
{"mcpServers": {"calendar_mail": {"transport":"streamable_http","url":"http://127.0.0.1:9901/mcp"}, …},
 "backends": {"file": "по умолчанию — read_case_json", "test": "MCP_BACKEND=test — mcp/_backends.py → test-instances/"}}
```

## Клиент
`src/athanor/sources.py::McpClient` — минимальный JSON-RPC 2.0 POST-клиент
(`initialize`/`tools/list`/`tools/call`). `load_case_via_mcp` собирает `CaseInput`
из четырёх серверов с per-source обработкой ошибок → `sources_down` (graceful).

## Адаптеры к тестовым инстансам (`mcp/_backends.py`)
При `MCP_BACKEND=test` инструменты ходят к `test-instances/` и конвертируют
ответы реальных контрактов в схему агента:

| MCP-инструмент | Тестовый инстанс | Конвертация |
|---|---|---|
| `get_events` | (calendar/mail → файл в test-режиме; live: Google iCal) | iCal VEVENT → `CalendarEvent` |
| `get_mail` | (calendar/mail → файл в test-режиме; live: Google IMAP) | IMAP message → `Mail` |
| `get_issues` | Jira `/rest/api/2/search` | Jira issue → `Issue` |
| `get_prs` | Bitbucket `/repositories/{workspace}/{repo_slug}/pullrequests` | Bitbucket PR → `PullRequest` |
| `get_confluence_pages` | Confluence `/wiki/rest/api/content/search` (CQL) | Confluence page → `ConfluencePage` (HTML→excerpt, version, url) |

URL тестовых инстансов переопределяются env: `TEST_JIRA_URL`,
`TEST_BITBUCKET_URL`, `TEST_CONFLUENCE_URL`, `TEST_JIRA_PROJECT`,
`TEST_CONFLUENCE_SPACE`, `TEST_BB_WORKSPACE`, `TEST_BB_REPO_SLUG`.
Подробнее — `test-instances/README.md`.

## Live-интеграции (`MCP_BACKEND=live`)
Per-source backend через `MCP_BACKEND_<SOURCE>` (приоритет над `MCP_BACKEND`). Preset `live`:
Jira=atlassian, calendar/mail=google, confluence=atlassian, pr/transcript=file. **4 боевые системы
через MCP, stdlib-only.** Боевой Bitbucket — через `MCP_BACKEND_PR=bitbucket` (можно поверх `live`).

| Источник | Бэкенд | Реальная система | Контракт |
|---|---|---|---|
| calendar | google | Calendar | публичный iCal `.ics` URL (urllib, без авторизации) |
| mail | google | mail | IMAP + пароль приложения (imaplib, 2FA) |
| jira | atlassian | Jira (Atlassian) | `/rest/api/3/search/jql` (Basic auth) |
| pr | bitbucket | Bitbucket Cloud (Atlassian) | `/repositories/{ws}/{slug}/pullrequests` (Basic `email:token` или Bearer workspace token) |
| confluence | atlassian | Confluence Cloud (Atlassian) | `/wiki/rest/api/content/search` (CQL `space=KEY AND label="alpha-demo"`, Basic auth) |
| transcript | file | локальный кейс | файлы |

```bash
# .env: JIRA_*, GOOGLE_ACCOUNT, GOOGLE_APP_PASSWORD, GOOGLE_ICAL_URL
python test-instances/seed_google.py    # письмо-блокер в mail + проверка iCal
MCP_BACKEND=live python mcp/serve_all.py
MCP_BACKEND=live python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print

# добавить боевой Bitbucket Cloud к live:
python test-instances/seed_bitbucket.py                                  # репо + ветка + PR «Миграция на ППРБ»
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

**mail (Google):** IMAP + пароль приложения (https://myaccount.google.com/apppasswords,
нужна 2FA). **Calendar:** публичный iCal URL (Settings → Integrate calendar).
Креды — только в `.env` (в `.gitignore`). Без Azure/OAuth.

## Реальный Bitbucket Cloud (`MCP_BACKEND_PR=bitbucket`)
При `MCP_BACKEND_PR=bitbucket` инструмент `get_prs` ходит к боевому Bitbucket Cloud
(`/repositories/{workspace}/{repo_slug}/pullrequests?state=OPEN`) и читает открытые PR из
**выделенного демо-репо** (синтетика «Альфа»). Конвертация Bitbucket PR → `PullRequest` та
же, что у тестового инстанса.

> App Passwords удаляются (removal 28.07.2026). Два механизма API tokens (приоритет —
> workspace token): **A) personal API token** (любой план, Basic `email:token`, не может
> создавать репо) · **B) workspace access token** (Premium, Bearer, может создавать репо).

```bash
# .env: BITBUCKET_WORKSPACE, BITBUCKET_REPO_SLUG, BITBUCKET_PR_ISSUE_KEY (опц.) +
#        (A) BITBUCKET_EMAIL + BITBUCKET_API_TOKEN  — либо —  (B) BITBUCKET_WORKSPACE_TOKEN
python test-instances/seed_bitbucket.py    # репо (B only) + ветка + PR «Миграция на ППРБ»
MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
```

Personal API token: https://bitbucket.org/account/settings/api-tokens/ (Basic auth,
username = email аккаунта; scopes `read+write:repository`, `read+write:pullrequest`; срок
макс 1 год; не может создавать репо — создайте демо-репо вручную). Workspace access token
(Premium): workspace → Settings → Access tokens (Bearer; scopes `repository` read+write+
admin, `pullrequest` read+write; может создавать репо). Креды — только в `.env`
(в `.gitignore`).

## Реальная Confluence Cloud (`MCP_BACKEND_CONFLUENCE=atlassian`)
При `MCP_BACKEND_CONFLUENCE=atlassian` инструмент `get_confluence_pages` ходит к боевой
Confluence Cloud (`/wiki/rest/api/content/search?cql=…`, Basic auth: email + API-токен) и
читает страницы с лейблом `CONFLUENCE_LABEL` (синтетика «Альфа») — release plan / decision log
/ RFC. Конвертация Confluence page → `ConfluencePage` та же, что у тестового инстанса
(HTML body → excerpt с отбросом заголовка-префикса, version, `_links` → url). Страницы
попадают в сводку секцией «Контекст из Confluence» (kind=`doc`, уверенность 0.8).

> Тот же Atlassian API-токен работает для Jira и Confluence — можно переиспользовать
> `JIRA_EMAIL`/`JIRA_API_TOKEN` (если `CONFLUENCE_EMAIL`/`CONFLUENCE_API_TOKEN` не заданы).
>
> **Личные пространства** (ключ `~…`): CQL-парсер Confluence не принимает `space="~…"`,
> поэтому адаптер опускает space-фильтр для `~`-ключей и ищет только по лейблу
> `alpha-demo` (`mcp/_backends.py::_confluence_cql`). Лейбл — достаточный фильтр синтетики.
> `GET /wiki/rest/api/space/~…` таймаутит на `~` в пути — `seed_confluence.py` проверяет
> личное пространство через `GET /space?type=personal`.

```bash
# 1) .env: CONFLUENCE_URL, CONFLUENCE_SPACE (глобальный ключ, или ~… для личного, или пусто),
#          CONFLUENCE_LABEL=alpha-demo +
#          CONFLUENCE_EMAIL + CONFLUENCE_API_TOKEN  (или переиспользовать JIRA_*)
# 2) сидинг синтетики в реальной Confluence (идемпотентно: пространство + 2 страницы)
python test-instances/seed_confluence.py        # «Release Plan · Альфа», «Decision Log · Альфа»
# 3) прогон через реальную Confluence Cloud
MCP_BACKEND_CONFLUENCE=atlassian python mcp/serve_all.py
MCP_BACKEND_CONFLUENCE=atlassian python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
# 4) combined live: Jira + mail + Calendar + Confluence Cloud
MCP_BACKEND=live python mcp/serve_all.py
MCP_BACKEND=live python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

API-токен: https://id.atlassian.com/manage-profile/security/api-tokens. Креды — только
в `.env` (в `.gitignore`); в репозитории плейсхолдеры. Адаптер читает только страницы с
лейблом `alpha-demo`, не рабочую документацию пространства.

## Подготовленные, но не подключённые в MVP
`create_jira_draft`, `create_email_draft`, `create_reminder`, `save_feedback`,
`load_release_memory`, `update_release_memory` —
объявлены в allowlist (`security.ALLOWED_HITL_TOOLS`); в демо-контуре реализованы
в процессе (hitl.py, memory.py, feedback.py) с тем же контрактом. Боевые MCP-обёртки —
после пилота. `get_confluence_pages` — реализован (`mcp/confluence.py` + `_backends.py`).
