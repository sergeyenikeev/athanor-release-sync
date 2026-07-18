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

Данные — обезличенная синтетика «Альфа» (роли, APP-/OPS-***, `ППРБ-адаптер`, страницы
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
ППРБ-адаптер, решение + 2 поручения, черновики HITL, обновление памяти, плюс секция
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
# 2) сидинг: репо (только B) + ветка + PR «Миграция на ППРБ»
python test-instances/seed_bitbucket.py
# 3) прогон через реальный Bitbucket (PR из Cloud, остальное — файлы кейса)
MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print
# 4) combined live: Jira + Bitbucket Cloud
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND=live MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

`seed_bitbucket.py` создаёт репо (только с workspace access token) → начальный коммит на
`main` → ветку `feature/payment-schema` с отличающимся коммитом → открытый PR «Миграция на ППРБ»
(`summary`: «PR по `<issue_key>`: миграция на ППРБ»). При повторном запуске переиспользует
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

## Тестовая корзина в реальных облаках (`seed_basket.py`)

Корзина TB-01..TB-17 — это **17 изолированных сценариев** с конфликтующими состояниями
(одна задача APP-412 в TB-01 «в работе», в TB-03 «готово»; один PR #128 «на ревью» и
«слито»). Удержать их одновременно в одной реальной Jira/Bitbucket физически нельзя.
Per-сценарное состояние воспроизводится через **файловый контур** (`MCP_CASE_DIR`),
как задумано архитектурой; в реальные облака грузится **библиотека уникальных
сущностей** корзины — по одному экземпляру каждой задачи/PR/письма.

```bash
python test-instances/seed_basket.py   # идемпотентно
```

Создаёт (всё с лейблом `alpha-demo` + `basket`):

| Система | Что создаёт | Источник в корзине |
|---|---|---|
| **Jira** | проекты `APP` + `OPS`, 5 задач (APP-1 «Миграция на ППРБ», APP-2 «Интеграция с партнёром», APP-3 «Репликация ППРБ» [Готово], OPS-1 «Деплой ППРБ-адаптера», OPS-2 «Разбор инцидента предпрода») | `tracker.json` всех сценариев |
| **Bitbucket** | PR #2 «Репликация ППРБ» (`feature/refund-schema`→`main`, issue_key=APP-3) | TB-09 `tracker.prs` |
| **Gmail** | 5 уникальных писем с `X-Athanor-Role` (TB-01 «Готовость стенда», TB-02/12 «ППРБ-адаптер не задеплоен», TB-03 «Блокер по APP-412», TB-10/14 «Уточнить окно заморозки», TB-11 «Срочно» — prompt injection) | `mail.json` всех сценариев |
| **Confluence** | пропущено — в `test-basket/` нет `confluence.json` (только у демо-кейса) | — |
| **Calendar** | пропущено — все 17 сценариев используют одно событие «Релиз-синк · Альфа» (уже создано вручную, см. `seed_google.py`) | — |

Канонические ключи `APP-412/521/421`, `OPS-77/78` нельзя задать в Cloud (номера назначает
Jira) → реально `APP-1/2/3`, `OPS-1/2`. Маппинг `basket_key → jira_key` сохранён в
`results/basket_seeded.json` и в `description` каждой задачи. Идемпотентно: повторный
запуск переиспользует проекты/задачи/PR и пропускает письма (IMAP-дедуп по теме).
Результат — `results/basket_seeded.json`.

> **Честно**: это **библиотека сущностей**, не per-сценарное состояние. Сценарии TB-11
> (prompt injection), TB-14 (недоступный трекер), TB-15 (битая расшифровка), TB-16 (HITL-
> bypass) и TB-17 (повторный прогон с памятью) проверяют поведение агента и в live-облака
> не транслируются — они прогоняются на файловом контуре в каноническом eval
> (`results/runs/eval_20260718T164508`).

## Расширение до 10+ сущностей (`seed_more.py`)

Дополняет `seed_basket.py` до 10+ в каждой системе (демо-контур масштаба):

```bash
python test-instances/seed_more.py              # все 5 систем
python test-instances/seed_more.py --only jira bitbucket confluence gmail calendar
```

| Система | Что добавляет | Всего в облаке |
|---|---|---|
| **Jira** | +7 задач (APP-4..7, OPS-3..5) | 14 (KAN-1/2 + APP-1..7 + OPS-1..5) |
| **Bitbucket** | +8 PR (#3..#10: Вебхуки, Кэш, Метрики, Реестр, Мониторинг, Runbook, Postmortem, Архитектура) | 10 PR |
| **Confluence** | +8 страниц (RFC, Postmortem, Runbook, Changelog, On-call, Retrospective, Architecture, Test Plan) | 10 страниц |
| **Gmail** | +6 писем (Release-notes, Деплой partner-api, Postmortem готов, Runbook обновлён, Запрос на ревью, Согласование окна) | 14 писем (все с `X-Athanor-Role`) |
| **Calendar** | `examples/calendar_alpha_10.ics` + `examples/calendar_alpha.csv` (14 событий, все на рабочих днях, UTF-8 BOM) | 14 встреч — ручной импорт в Google Calendar. **CSV рекомендуется** (Settings → Import & export → Import → выберите `calendar_alpha.csv`). .ics-импорт Google Calendar иногда даёт mojibake для кириллицы; CSV с UTF-8 BOM импортирует корректно. Неделя 03.07 — 8 встреч; выходные (05.07, 12.07) перенесены на 06.07, 08.07 |

Calendar нельзя автоматизировать (API требует OAuth2; app password даёт только
IMAP/SMTP). Скрипт генерирует `.ics` для ручного импорта. Идемпотентно, с retry
на сетевые таймауты (`_req_retry`: 6 попыток × 12с + backoff). Артефакт —
`results/more_seeded.json`. Поддерживает `--only` для частичного перезапуска.

> **Сетевая нестабильность Atlassian/Bitbucket** (18.07.2026): API плавают (таймауты,
> ConnectionReset). `seed_more.py` с retry пробивает окна доступности; если часть
> вызовов упала — повторный запуск (`--only <система>`) доделает. Live-прогон на
> расширенных данных — `results/runs/live_real_20260718T153435/` (10 PR, 10 Confluence,
> 3 письма — до правки фильтра писем; перегон на 14 письмах требует стабильной сети).

## Что доказывает

1. MCP-адаптеры работают с **реальными API-контрактами** (Jira REST,
   Bitbucket Cloud REST 2.0, Confluence Cloud REST API v1, Google IMAP/iCal),
   а не только с файловой выгрузкой.
2. Конвертация «контракт системы → схема агента» реализована и воспроизводима.
3. **Уровень 3: реальная Jira** — боевой контракт Atlassian, live-данные из Cloud.
3b. **Реальный Bitbucket Cloud** — боевой контракт Atlassian, live-PR из Cloud (`MCP_BACKEND_PR=bitbucket`).
3c. **Реальная Confluence Cloud** — боевой контракт Atlassian, live-страницы из Cloud (`MCP_BACKEND_CONFLUENCE=atlassian`).
3d. **Библиотека сущностей тестовой корзины** в реальных облаках (`seed_basket.py`): 5 Jira-задач
    (проекты APP/OPS), доп-PR Bitbucket, 5 писем Gmail — все 17 сценариев представлены своими
    уникальными сущностями. Per-сценарное состояние — на файловом контуре (по архитектуре).
4. **Смена URL/env = переход на боевые системы** без изменения адаптеров.
5. Демонстрационный контур уровня 1 остаётся офлайн и детерминированным.
