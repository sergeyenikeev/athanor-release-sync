# Тестовые инстансы и реальные облачные интеграции (Jira/Bitbucket/Confluence Cloud)

Три уровня интеграций MCP-адаптеров:

1. **Локальные тестовые инстансы** (этот каталог, `MCP_BACKEND=test`) — серверы с
   **реальными контрактами** корпоративных систем и обезличенной синтетикой «Альфа».
2. **Реальная Jira** (`MCP_BACKEND=atlassian`) — MCP-адаптер `get_issues` ходит к
   боевой Jira (Atlassian) и читает синтетику с лейблом `alpha-demo`.
3. **Реальный Bitbucket Cloud** (`MCP_BACKEND_PR=bitbucket`) — `get_prs` читает открытые PR
   из выделенного демо-репо. **Реальная Confluence Cloud** (`MCP_BACKEND_CONFLUENCE=atlassian`)
   — `get_confluence_pages` читает страницы (release plan / decision log) с лейблом `alpha-demo`.

> Это **не боевые интеграции** в смысле прод-данных. Уровень 1 — локальные серверы с
> реальными контрактами. Уровни 2–3 — реальные облачные системы, но с синтетическими данными.
> Смена URL/env → боевые системы (после пилота и ИБ-согласования).

## Состав

| Инстанс | Порт | Контракт | Эндпоинты |
|---|---|---|---|
| `jira_server.py` | 9911 | Atlassian Jira REST v2 | `/rest/api/2/search?jql=`, `/rest/api/2/issue/{key}`, `/rest/api/2/serverInfo` |
| `bitbucket_server.py` | 9913 | Bitbucket Cloud REST 2.0 | `/repositories/{workspace}/{repo_slug}/pullrequests` |
| `confluence_server.py` | 9914 | Atlassian Confluence REST API v1 | `/wiki/rest/api/content/search?cql=`, `/wiki/rest/api/content/{id}`, `/wiki/rest/api/space` |

Calendar/mail в test-режиме читаются из файла (graph-инстанс не используется);
реальные mail/Calendar — Google через `MCP_BACKEND=live` (IMAP + iCal, `seed_google.py`).

Данные — обезличенная синтетика «Альфа» (роли, APP-/OPS-***, `payment-adapter`, страницы
`Release Plan · Альфа` / `Decision Log · Альфа`). ПДн и секретов нет.

## Запуск

```bash
# все три инстанса в одном процессе
python test-instances/serve_all.py

# или по отдельности
python test-instances/jira_server.py
python test-instances/bitbucket_server.py
python test-instances/confluence_server.py
```

## Связь с MCP-адаптерами

`mcp/_backends.py` при `MCP_BACKEND=test` ходит к этим инстансам и конвертирует
ответы реальных контрактов в схему агента (`Issue`/`PullRequest`/`ConfluencePage`).
Calendar/mail в test-режиме — из файла; в live — Google (IMAP/iCal):

| MCP-инструмент | Тестовый инстанс | Конвертация |
|---|---|---|
| `calendar_mail.get_events` | (файл в test; live: Google iCal) | iCal VEVENT → `CalendarEvent` |
| `calendar_mail.get_mail` | (файл в test; live: Google IMAP) | IMAP message → `Mail` |
| `tracker_repo.get_issues` | Jira `/rest/api/2/search` | Jira issue → `Issue` |
| `tracker_repo.get_prs` | Bitbucket `/repositories/.../pullrequests` | Bitbucket PR → `PullRequest` |
| `confluence.get_confluence_pages` | Confluence `/wiki/rest/api/content/search` (CQL) | Confluence page → `ConfluencePage` (HTML→excerpt, version, url) |

## Полный прогон через тестовые инстансы

```bash
# терминал 1
python test-instances/serve_all.py
# терминал 2
MCP_BACKEND=test python mcp/serve_all.py
# терминал 3
MCP_BACKEND=test python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
```

Результат идентичен файловому демо-контуру: конфликт Jira↔письмо, блокер
payment-adapter, решение + 2 поручения, черновики HITL, обновление памяти, плюс секция
«Контекст из Confluence» (release plan / decision log).

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `MCP_BACKEND` | (не задан) | `test` — локальные инстансы; `atlassian` — реальная Jira; иначе — файлы кейса |
| `TEST_JIRA_URL` | `http://127.0.0.1:9911` | URL тестовой Jira (`MCP_BACKEND=test`) |
| `TEST_BITBUCKET_URL` | `http://127.0.0.1:9913` | URL тестового Bitbucket |
| `TEST_CONFLUENCE_URL` | `http://127.0.0.1:9914` | URL тестового Confluence (`MCP_BACKEND=test`) |
| `TEST_JIRA_PROJECT` | `ALPHA` | JQL-проект для поиска (test) |
| `TEST_CONFLUENCE_SPACE` | `ALPHA` | пространство Confluence для CQL (test) |
| `TEST_BB_WORKSPACE`/`TEST_BB_REPO_SLUG` | `athanor`/`alpha` | workspace и slug репо для pullrequests |
| `JIRA_URL` | `https://<your-tenant>.atlassian.net` | URL реальной Jira (`atlassian`) |
| `JIRA_EMAIL`/`JIRA_API_TOKEN` | (пусто) | Basic auth Jira; токен — в `.env` |
| `JIRA_PROJECT` | `KAN` | проект Jira |
| `JIRA_LABEL` | `alpha-demo` | лейбл фильтра синтетики |
| `CONFLUENCE_URL` | `https://<your-tenant>.atlassian.net` | URL реальной Confluence Cloud (`MCP_BACKEND_CONFLUENCE=atlassian`) |
| `CONFLUENCE_EMAIL`/`CONFLUENCE_API_TOKEN` | (пусто) | Basic auth Confluence Cloud; можно переиспользовать `JIRA_*` (тот же Atlassian API-токен) |
| `CONFLUENCE_SPACE` | `ALPHA` | пространство Confluence Cloud |
| `CONFLUENCE_LABEL` | `alpha-demo` | лейбл фильтра синтетики |

## Реальная Jira (`MCP_BACKEND=atlassian`)

`mcp/_backends.py::jira_issues_atlassian` ходит к Jira (`/rest/api/3/search/jql`,
Basic auth) и читает задачи с лейблом `JIRA_LABEL`, нормализуя статусы. Остальные
источники — файлы live-кейса.

```bash
# 1) .env: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT=KAN
# 2) сидинг синтетики в реальную Jira (идемпотентно)
python test-instances/discover_atlassian.py   # диагностика статусов/типов
python test-instances/seed_atlassian.py       # создать alpha-demo задачи (ключи по проекту KAN: KAN-1/KAN-2), KAN-1 → Done
python test-instances/gen_live_case.py        # examples/demo_case_alpha_live (канонические ключи APP-412/APP-521)
# 3) прогон через реальную Jira
MCP_BACKEND=atlassian python mcp/serve_all.py
MCP_BACKEND=atlassian python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

API-токен: https://id.atlassian.com/manage-profile/security/api-tokens. Креды — только
в `.env` (в `.gitignore`); в репозитории плейсхолдеры. Финальное демо-видео собрано на
этом уровне (сидинг в проект KAN: KAN-1/KAN-2; канонический live-снимок в репо — APP-412/APP-521). URL/email в кадрах видео замаскированы.

## Реальный Bitbucket Cloud (`MCP_BACKEND_PR=bitbucket`)

`mcp/_backends.py::bitbucket_prs_cloud` ходит к Bitbucket Cloud
(`/repositories/{workspace}/{repo_slug}/pullrequests?state=OPEN`) и читает открытые PR
из **выделенного демо-репо** (синтетика «Альфа»). Конвертация Bitbucket PR → `PullRequest`
та же, что у тестового инстанса. Остальные источники — файлы кейса (или Jira через
`MCP_BACKEND_JIRA=atlassian`).

> **App Passwords удаляются** (brownout с 09.06.2026, permanent removal 28.07.2026).
> Два механизма авторизации API tokens (приоритет — workspace token):

**A) Personal API token** (любой план, Basic auth `email:token`):
- https://bitbucket.org/account/settings/api-tokens/ (avatar → Personal settings → API tokens)
- Username для Basic auth = **email аккаунта Atlassian** (не Bitbucket username)
- Scopes (не наследуют — нужны и read, и write): `read:repository` · `write:repository` ·
  `read:pullrequest` · `write:pullrequest`. Срок обязателен (макс 1 год), показывается один раз.
- **НЕ может создавать репо** (`POST /repositories` — workspace-admin операция, 403).
  Создайте демо-репо вручную в UI — seeder сделает ветку + PR.

**B) Workspace access token** (Premium, Bearer auth):
- bitbucket.org → workspace → **Settings** → **Access tokens** → Create access token
- Scopes: `repository` (read+write+admin), `pullrequest` (read+write).
- **Может создавать репо**. Приоритет над (A), если заданы оба.

```bash
# 1) .env: BITBUCKET_WORKSPACE, BITBUCKET_REPO_SLUG +
#          (A) BITBUCKET_EMAIL + BITBUCKET_API_TOKEN  — либо —
#          (B) BITBUCKET_WORKSPACE_TOKEN
#    Опц.: BITBUCKET_PR_ISSUE_KEY (по умолч. APP-412; для связки с Jira — KAN-ключ)
# 2) сидинг: репо (только B) + ветка + PR «Схема оплат»
python test-instances/seed_bitbucket.py
# 3) прогон через реальный Bitbucket (PR из Cloud, остальное — файлы кейса)
MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
# 4) combined live: Jira + Bitbucket Cloud
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

`seed_bitbucket.py` создаёт репо (только с workspace access token) → начальный коммит на
`main` → ветку `feature/payment-schema` с отличающимся коммитом → открытый PR «Схема оплат»
(`summary`: «PR по `<issue_key>`: миграция схемы оплат»). При повторном запуске переиспользует
существующие репо/ветку/PR. С personal API token (вариант A) репо нужно создать вручную,
остальное seeder сделает сам. Результат — `results/bitbucket_seeded.json`. Токены — только
в `.env` (в `.gitignore`).

## Реальная Confluence Cloud (`MCP_BACKEND_CONFLUENCE=atlassian`)

`mcp/_backends.py::confluence_pages_atlassian` ходит к Confluence Cloud
(`/wiki/rest/api/content/search?cql=space=KEY AND label="alpha-demo"`, Basic auth: email +
API-токен) и читает страницы с лейблом `CONFLUENCE_LABEL` (синтетика «Альфа») — release plan /
decision log / RFC. Конвертация Confluence page → `ConfluencePage` та же, что у тестового
инстанса (HTML body → excerpt, `version.number`, `_links` → url, `version.when` → дата).
Страницы попадают в сводку секцией «Контекст из Confluence» (kind=`doc`, уверенность 0.8).

> Тот же Atlassian API-токен работает для Jira и Confluence — можно переиспользовать
> `JIRA_EMAIL`/`JIRA_API_TOKEN` (если `CONFLUENCE_EMAIL`/`CONFLUENCE_API_TOKEN` не заданы).

```bash
# 1) .env: CONFLUENCE_URL, CONFLUENCE_SPACE=ALPHA, CONFLUENCE_LABEL=alpha-demo +
#          CONFLUENCE_EMAIL + CONFLUENCE_API_TOKEN  (или переиспользовать JIRA_*)
#    API-токен: https://id.atlassian.com/manage-profile/security/api-tokens
# 2) сидинг синтетики в реальной Confluence (идемпотентно: пространство + 2 страницы с лейблом)
python test-instances/seed_confluence.py    # «Release Plan · Альфа», «Decision Log · Альфа»
# 3) прогон через реальную Confluence Cloud (остальное — файлы кейса)
MCP_BACKEND_CONFLUENCE=atlassian python mcp/serve_all.py
MCP_BACKEND_CONFLUENCE=atlassian python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
# 4) combined live: Jira + mail + Calendar + Confluence Cloud
MCP_BACKEND=live python mcp/serve_all.py
MCP_BACKEND=live python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

`seed_confluence.py` создаёт пространство `ALPHA` (если нет) → 2 страницы с лейблом
`alpha-demo` (storage-format body) → вешает лейбл через `/content/{id}/label`. Идемпотентно:
при повторном запуске переиспользует существующие alpha-demo страницы. Результат —
`results/confluence_seeded.json`. Креды — только в `.env` (в `.gitignore`); адаптер читает
только страницы с лейблом `alpha-demo`, не рабочую документацию.

> **Личные пространства** (`CONFLUENCE_SPACE` начинается с `~` или пусто): создать глобальное
> пространство нельзя, и CQL `space="~…"` парсер не принимает — seeder переиспользует
> существующее личное пространство (проверка через `GET /space?type=personal`, т.к.
> `GET /space/~…` таймаутит на `~` в пути) и ищет/создаёт страницы только по лейблу
> `alpha-demo`. При пустом `CONFLUENCE_SPACE` личное пространство определяется автоматически.

## Что доказывает

1. MCP-адаптеры работают с **реальными API-контрактами** (Jira REST,
   Bitbucket Cloud REST 2.0, Confluence Cloud REST API v1, Google IMAP/iCal),
   а не только с файловой выгрузкой.
2. Конвертация «контракт системы → схема агента» реализована и воспроизводима.
3. **Уровень 3: реальная Jira** — боевой контракт Atlassian, live-данные из Cloud.
3b. **Реальный Bitbucket Cloud** — боевой контракт Atlassian, live-PR из Cloud (`MCP_BACKEND_PR=bitbucket`).
3c. **Реальная Confluence Cloud** — боевой контракт Atlassian, live-страницы из Cloud (`MCP_BACKEND_CONFLUENCE=atlassian`).
4. **Смена URL/env = переход на боевые системы** без изменения адаптеров.
5. Демонстрационный контур уровня 1 остаётся офлайн и детерминированным.
