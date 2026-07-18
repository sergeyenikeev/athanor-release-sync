# Ouroboros — мозг команды (команда «Атанор», Sber AI Hack)

ИИ-агент подготовки к **релиз-синкам и разборам инцидентов**: восстановление
контекста из нескольких систем, формирование briefing перед встречей, извлечение
решений/поручений/ответственных/сроков из расшифровки, контроль договорённостей,
раннее выявление блокеров, аудируемая память релизов и управляемое улучшение
навыка по обратной связи. На базе технологии **Ouroboros** (навык + память + MCP +
Safety Layer + Human-in-the-loop).

> Контур MVP — реальные Jira/Bitbucket/Confluence/Google (mail+calendar) через MCP
> (`MCP_BACKEND=live`); расшифровки — файлы кейса.
>
> Агент работает на настольном приложении **Ouroboros** (навык + MCP + память +
> Safety Layer + Human-in-the-loop) — оркестрация нескольких систем, HITL и
> аудируемая память достижимы только в его контуре. Инструкция с нуля — в разделе
> [«Установка и настройка Ouroboros»](#установка-и-настройка-ouroboros).

## Реализованные функции

| Функция | Статус | Доказательство |
|---|---|---|
| Сводка перед релиз-синком (детерминированная) | реализовано | `src/athanor/summary.py`, `results/runs/after_fix/TB-01/output.md` |
| Источники: календарь, трекер, PR, почта, расшифровки | реальные (live) + расшифровки (файлы) | `mcp/`, `examples/demo_case_alpha_live`, `test-instances/seed_*.py` |
| Извлечение решений и поручений (rule + LLM) | реализовано | `src/athanor/extract.py`, `src/athanor/llm.py` |
| Решение ≠ идея; владелец/срок/источник | реализовано | `tests/unit/test_extract.py` |
| Конфликт Jira↔письмо (оба значения + приоритет) | реализовано | `src/athanor/summary.py`, TB-03 |
| Блокеры (структурированные) | реализовано | `src/athanor/enrich.py` (Blocker) |
| Черновики действий (HITL) | реализовано | `src/athanor/hitl.py`, `outbox/` |
| Аудируемая память релиза + журнал | реализовано | `src/athanor/memory.py`, `memory/knowledge/release_alfa.md` |
| Safety Layer (prompt injection, allowlist, маскирование) | реализовано | `src/athanor/security.py`, TB-11 |
| Версионирование навыка + эволюция по обратной связи + откат | реализовано | `src/athanor/skill_versioning.py`, `skills/release_sync/versions/registry.json` |
| Метрики (P/R/F1, время, evidence coverage) | реализовано | `tests/score.py`, `results/metrics.json` |
| Тестовая корзина 17 сценариев (15 обязательных task4 + 2 доп.) | реализовано | `test-basket/TB-01..TB-17` |
| Боевые коннекторы Jira/Bitbucket/Confluence/mail/Calendar | реализовано (`MCP_BACKEND=live`) | `mcp/_backends.py`, `test-instances/seed_*.py` |
| Боевой коннектор Confluence Cloud | реализовано | `mcp/confluence.py`, `mcp/_backends.py` (`MCP_BACKEND_CONFLUENCE=atlassian`), `test-instances/seed_confluence.py` |
| Источник Confluence в сводке (release plan / decision log) | реализовано | `src/athanor/summary.py` (kind=`doc`), `examples/demo_case_alpha/input/confluence.json` |
| Замер AS IS/TO BE на реальных данных | не входит в MVP | пилот |

## Архитектура
Слои: domain (`models`) → connectors (`sources`, MCP) → orchestration (`agent`,
`engine`, `enrich`) → memory (`memory`) → safety (`security`, `hitl`) → LLM (`llm`)
→ presentation (`format`, `cli`) → evaluation (`run_basket`, `score`).
Подробнее — `docs/architecture.md`.

## Системные требования
Python 3.10+ (проверено на 3.13). Внешние runtime-зависимости — нет (только stdlib).
`pip install -e .` опционален (для `python -m athanor.cli`); скрипты в `scripts/` и
`tests/` работают без установки (сами кладут `src/` на `sys.path`).

## Переменные окружения
См. `.env.example`. Ключевые: `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`,
`LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_BUDGET_USD`, `LOCAL_LLM_BASE_URL`,
`ATHANOR_LLM_MOCK` (1 — детерминированный mock без сети), `ATHANOR_ENGINE`
(`llm`/`rule`), `MCP_*` (порты MCP-серверов), `MCP_TRANSCRIPTS_DOWN` (TB-11).
Без `LLM_API_KEY` CLI `--engine llm` автоматически использует mock.

## Структура входных данных (кейс)
```
test-basket/TB-XX/input/
  calendar.json   {"events":[{id,title,project,datetime,participants}]}
  tracker.json    {"issues":[{key,title,status,assignee_role}], "prs":[{number,title,status,review_days,issue_key}]}
  mail.json       {"messages":[{id,from_role,date,subject,body}]}
  transcript.txt  role: текст (построчные реплики)
  memory_seed.md  (опц.) посев памяти релиза
meta.json          {id,type,checks,format,transcripts_down,seed}
expected/*.json    эталон (decisions,actions,blockers,summary,flags)
```

## Структура выходных данных (прогон)
```
results/runs/<run_id>/TB-XX/
  output.md        briefing + решения + поручения + блокеры + черновики + память + тайминги
  run.json         полный сериализованный RunResult
  metrics.json     метрики сценария (TP/FP/FN, P/R/F1, coverage, статус)
  memory_after/    память релиза после прогона (аудит)
  outbox/*.json    черновики (HITL, awaiting_approval)
results/runs/<run_id>/manifest.json   сводка прогона
results/{metrics.json,metrics.csv,results_summary.md,evaluation_report.html}  (со --mirror)
```

## Ouroboros-компоненты
- **SKILL.md** — `skills/release_sync/SKILL.md` (v1) + `versions/SKILL_v2.md` (v2);
  entry — `skills/release_sync/main.py`.
- **identity.md** — `memory/identity.md` (роль, границы автономии, запреты).
- **knowledge/** — `memory/knowledge/` (память релиза, модель команды, организация,
  проекты, релизы, решения, терминология, предпочтения, политики).
- **MCP** — `mcp/` (4 MCP-сервера: calendar_mail, tracker_repo, transcripts, confluence; `mcp_config.json`; `MCP_BACKEND=live` → реальные Jira/Bitbucket/Confluence/Google).
- **Память** — постоянная (`identity.md`, `knowledge/`), релиза
  (`release_<slug>.md`), журнал (`journal.log`), рабочая (`results/runs/<id>/`).
- **Safety Layer** — `src/athanor/security.py` + HITL.
- **Версионирование** — `skills/release_sync/versions/registry.json` + CLI.
- **Human-in-the-loop** — `src/athanor/hitl.py` + `outbox/`.

## Human-in-the-loop
Любое внешнее действие (письмо, задача, срок, ответственный, закрытие обязательства,
изменение памяти навыка, применение новой версии навыка) — только черновик до
подтверждения человека. Статусы: `proposed → awaiting_approval → approved → executed`
(или `→ rejected/failed`). Демо: `python -m athanor.cli approve --draft outbox/<id>.json`.

## Безопасность
См. `docs/security.md`. Секреты — только в `.env` (в `.gitignore`); ПДн нет
(обезличенная синтетика); prompt injection детектор + allowlist + маскирование +
валидация памяти; HITL на все внешние действия.

## Тесты и метрики
```bash
python scripts/run_tests.py                                   # 117 тестов, одна команда
python scripts/run_evaluation.py --engine rule                # корзина + метрики + эволюция
```

### Цели Project Proposal vs факт MVP (rule-baseline)
| Цель | План | Факт | Статус |
|---|---|---|---|
| Поручения precision | ≥ 85% | 100% | ✅ |
| Поручения recall | ≥ 80% | 100% | ✅ |
| Поручения F1 | ≥ 82% | 100% | ✅ |
| Полезность сводки | ≥ 4/5 | не замерено в MVP (пилот, независимый оценщик) | 📅 пилот |
| Принятые черновики | ≥ 60% | 100% (11/11) | ✅ |
| Время подготовки TO BE | ≤ 3 мин | <1 с end-to-end (5 мс cycle) | ✅ |

5 из 6 целей измерены и достигнуты; полезность сводки — замер пилота (независимый оценщик).
Подробнее — `docs/testing.md`, `docs/evaluation.md`. Результаты — `results/` (`metrics.json`,
`results_summary.md`).

## Замер AS IS/TO BE на реальных данных

| Параметр | AS IS (вручную) | TO BE (с агентом) | Статус |
|---|---|---|---|
| Время подготовки к релиз-синку | не замерено (нет доступа к тайм-трекингу команды) | <1 с end-to-end (rule-baseline, 5 мс cycle); реальный прогон Ouroboros — $0.4337, 16 rounds | AS IS — `[ТРЕБУЕТСЯ ФАКТИЧЕСКИЙ ЗАМЕР AS IS]`; TO BE — замерено ✅ |
| Поручения precision / recall / F1 | не замерено | 100% / 100% / 100% (цели ≥85/80/82), корзина TB-01..TB-17 | TO BE — замерено ✅ |
| Принятые черновики (HITL) | не замерено | 100% (11/11), цель ≥60% | TO BE — замерено ✅ |
| Полезность сводки (≥4/5) | не замерено | не замерено | 📅 пилот (независимый оценщик) |
| Recall на реальных расшифровках | — | не замерено (корзина синтетическая) | 📅 пилот с реальной LLM |

**Честно:** AS IS-хронометраж не измерялся — нет доступа к тайм-трекингу команды
(целевая оценка из Project Proposal помечена как оценочная). TO BE-метрики сняты на
rule-baseline / mock-LLM по синтетической корзине проекта «Альфа» (TB-01..TB-17);
реальный прогон Ouroboros v6.64 + Claude Opus 4.8 делал **только сводку**
(MCP-оркестрация): task `dec66d75`, $0.4337, 16 rounds, 8 MCP-вызовов. Источники:
`results/metrics.json`, `results/results_summary.md`, `results/scratch/ouroboros_demo/`.
Замер AS IS и полезности сводки на реальных данных — план пилота.

## Известные ограничения
- Jira/Bitbucket/Confluence/mail/Calendar — реализованы и подключены через
  `MCP_BACKEND=live` (`mcp/_backends.py`, сидинг — `test-instances/seed_*.py`).
- Метрики сняты на rule-baseline / mock-LLM (синтетическая корзина). Recall на
  реальных расшифровках — замер пилота с реальной LLM.
- Хронометраж AS IS (ручная подготовка) — не измерялся (нет доступа к тайм-трекингу);
  целевая оценка из Project Proposal помечена как оценочная.
- `create_jira_draft`/`create_email_draft`/`update_release_memory` реализованы в
  процессе (hitl.py/memory.py) с контрактом MCP-инструментов; боевые MCP-обёртки —
  после пилота.

## Структура репозитория
```
README.md  LICENSE  CHANGELOG.md  .env.example  .gitignore  pyproject.toml  Makefile
docs/        architecture, demo, testing, security, mcp, evaluation
config/      demo.yaml, local.yaml, test.yaml (пресеты env)
skills/release_sync/   SKILL.md, main.py, prompts/, versions/ (registry.json, SKILL_v1/v2)
memory/      identity.md, knowledge/ (release_alfa, team_model, organization/, projects/, …), feedback.jsonl
src/athanor/ models, config, security, summary, extract, llm, engine, enrich, memory,
              hitl, feedback, skill_versioning, control, sources, format, agent, cli
mcp/         _base, _backends, calendar_mail, tracker_repo, transcripts, confluence, serve_all, smoke_test, mcp_config.json
test-basket/ TB-01..TB-17 (input + expected + meta + metadata.yaml + README); TB-13..TB-17 — эталон зафиксирован вручную (task4 §20)
tests/       unit, integration, e2e, negative, run_basket.py, score.py
scripts/     _bootstrap, run_demo, run_tests, run_evaluation, export_results, gen_basket, gen_expected
examples/    demo_case, demo_case_alpha (данные по умолчанию для MCP, incl. confluence.json)
test-instances/ jira_server (REST v2), bitbucket_server (Cloud REST 2.0), confluence_server (REST API v1), serve_all, discover_atlassian, seed_atlassian, seed_bitbucket, seed_confluence, seed_google, gen_live_case
results/     runs/, demo/, metrics.json, metrics.csv, results_summary.md, evaluation_report.html
```

## Установка и настройка Ouroboros

Проект работает на настольном приложении **Ouroboros** (навык + память + MCP +
Safety Layer + Human-in-the-loop). Ниже — инструкция с нуля до первого прогона.
Проверено на Ouroboros **v6.64** (Windows x64); шаги те же для macOS/Linux.
Актуальная версия — на странице релизов.

### 1. Установить Ouroboros

- Скачать сборку со страницы релизов: <https://github.com/razzant/ouroboros/releases>
  - **Windows x64**: `Ouroboros-<ver>-windows-x64.zip` → распаковать →
    `Ouroboros\Ouroboros.exe`. (Установка проекта использовала папку
    `D:\d\Ouroboros-6.61.4-windows-x64\`, приложение обновлено до 6.64.)
  - **macOS**: `Ouroboros-<ver>-macos.dmg`; при блокировке Gatekeeper —
    `xattr -cr /Applications/Ouroboros.app`.
  - **Linux**: AppImage (`chmod +x && ./Ouroboros-*.AppImage`).
- Первый запуск → Onboarding Wizard → выбрать провайдера модели (шаг 2).
- Рабочее пространство по умолчанию: `C:\Users\<user>\Ouroboros` (Windows),
  `~/.local/share/Ouroboros` (Linux/macOS). Все настройки — `data/settings.json`.

### 2. Настроить провайдера модели

Settings → Models (или Onboarding Wizard). Ouroboros принимает любой
OpenAI-совместимый шлюз: OpenRouter / GigaChat / Cloud.ru Foundation Models /
локальный сервер (Ollama, LM Studio, vLLM). Вписать ключ в соответствующее поле.

Ключевые поля `data/settings.json` (канонические для этого MVP):

| Поле | Значение MVP | Назначение |
|---|---|---|
| `OUROBOROS_MODEL` | `anthropic/claude-opus-4.8` (OpenRouter) | основная модель агента |
| `OUROBOROS_REVIEW_MODELS` | `openai/gpt-4o-mini` | ревью/safety-модель (лёгкая, дешёвая) |
| `OUROBOROS_REVIEW_ENFORCEMENT` | `advisory` | ревью рекомендательное, не блокирующее |
| `OUROBOROS_RUNTIME_MODE` | `advanced` | полный цикл с ревью и HITL |
| `OUROBOROS_MAX_WORKERS` | `2` | параллелизм модели |

Любая модель класса agentic reasoning (Claude Opus 4.x / GPT-5.x / GigaChat Max)
работает. Команды для тестов и метрик (`--engine rule`) работают без ключа
провайдера — они используют детерминированный rule-движок (см. раздел «Команды»).

### 3. Поднять MCP-серверы проекта

Из корня репозитория (Python 3.10+, внешних зависимостей нет):

```bash
python mcp/serve_all.py          # 4 сервера: 9901-9904 (MCP_BACKEND=file по умолчанию)
python mcp/smoke_test.py         # проверка: initialize + tools/list + tools/call
```

Режимы данных (`MCP_BACKEND` в `.env` или в среде запуска):
- `file` (по умолчанию) — обезличенные выгрузки из `examples/demo_case` (офлайн-демо).
- `test` — локальные тестовые инстансы `test-instances/` с **реальными контрактами**
  Jira REST v2 / Bitbucket 2.0 / Confluence REST API v1 (офлайн, детерминированно).
- `live` — реальные Jira/Bitbucket/Confluence/Google mail+Calendar (нужны креды в `.env`).

### 4. Подключить MCP-серверы в Ouroboros

Settings → MCP → Add server (или импорт `mcp/mcp_config.json`). Четыре сервера:

| id | transport | url |
|---|---|---|
| `calendar_mail` | streamable_http | `http://127.0.0.1:9901/mcp` |
| `tracker_repo` | streamable_http | `http://127.0.0.1:9902/mcp` |
| `transcripts` | streamable_http | `http://127.0.0.1:9903/mcp` |
| `confluence` | streamable_http | `http://127.0.0.1:9904/mcp` |

После добавления — **Refresh**; у каждого сервера `enabled: true` и `tool_count > 0`
(в сумме 5 инструментов: `get_events`, `get_mail`, `get_issues`, `get_prs`,
`get_confluence_pages`). Это соответствует блоку `MCP_SERVERS` в `data/settings.json`.

### 5. Подключить навык `release_sync`

Ouroboros подгружает внешние навыки из каталога, заданного переменной
`OUROBOROS_SKILLS_REPO_PATH`. В `data/settings.json` (или Settings → Advanced → Skills):

```json
"OUROBOROS_SKILLS_REPO_PATH": "D:\\d\\ouroboros\\athanor-release-sync\\skills"
```

Путь указывает на папку `skills/` этого репозитория (навык лежит в
`skills/release_sync/`: `SKILL.md` + `main.py` + `versions/` + `prompts/`).
Навык не копируется в workspace — Ouroboros читает его прямо из чекаута репо.

Проверка: `ouroboros skills list` — навык `release_sync` виден.
**Перезапустить Ouroboros** после изменения настройки.

### 6. Память и рабочее пространство

Память навыка — файлы в репозитории (`memory/`), открывать в Ouroboros проект
`athanor-release-sync` (New task → Workspace = `athanor-release-sync`):

- `memory/identity.md` — роль агента, границы автономии, запреты.
- `memory/knowledge/` — память релиза, модель команды, организация, проекты,
  решения, терминология, предпочтения, политики.
- `memory/journal.log` — журнал решений (аудит).
- `memory/feedback.jsonl` — обратная связь для эволюции навыка.

Навык `main.py` сам резолвит `src/athanor` и `memory/` через
`OUROBOROS_SKILLS_REPO_PATH`/parents — отдельная загрузка в workspace не требуется.

### 7. Первый прогон в Ouroboros

```bash
# терминал 1: MCP-серверы (шаг 3)
python mcp/serve_all.py
```

В Ouroboros: New task → Workspace = `athanor-release-sync` → запрос:

> Подготовь сводку к релиз-синку проекта Альфа 03.07

Агент вызовет MCP-инструменты (`get_events` → `get_issues` → `get_prs` →
`get_mail` → `get_confluence_pages`) и вернёт сводку с источником и уверенностью
у каждого пункта. После встречи — приложите расшифровку и попросите извлечь
решения и поручения. Эквивалент в CLI (если установлен `ouroboros`):

```bash
ouroboros run --workspace athanor-release-sync "Подготовь сводку к релиз-синку проекта Альфа 03.07"
```

### 8. Устранение типовых ошибок

| Симптом | Решение |
|---|---|
| Агент не видит MCP-инструменты | проверьте `python mcp/serve_all.py` и адреса в Settings → MCP; `python mcp/smoke_test.py` |
| `skills list` не показывает `release_sync` | проверьте `OUROBOROS_SKILLS_REPO_PATH` (папка `skills/` репо) и перезапустите Ouroboros |
| 401/403 от провайдера | проверьте ключ и баланс; для OpenRouter из РФ — VPN |
| Skill review quorum failure | добавьте второй провайдер для ревью либо `OUROBOROS_REVIEW_ENFORCEMENT=advisory` |
| MCP-серверы не стартуют (порт занят) | измените `MCP_*_PORT` в `.env` и в `mcp/mcp_config.json` синхронно |
| Пустой экран / зависание | перезапустить Ouroboros; проверить `ouroboros.pid` в workspace |

### 9. Эталонный реальный прогон (что должно получиться)

Реальный прогон Ouroboros v6.64 + Claude Opus 4.8 на этом проекте:

- task `dec66d75`, **lifecycle=completed** (review=best_effort, auto-acceptance без кворума),
  $0.4337, 16 rounds, 8 MCP-вызовов (5 инструментов:
  `get_events`/`get_mail`/`get_issues`/`get_prs`/`get_confluence_pages`;
  3 safety-таймаута восстановлены автоматическим retry) → сводка (Confluence:
  что в релизе; APP-412 Готово, APP-521 к выполнению, PR #128, конфликт
  Jira↔mail↔Bitbucket, блокер payment-adapter; роли backend/frontend).
- Артефакт: `results/scratch/ouroboros_demo/` (`run.log`, `result.json`).
- Кадр с реальным выводом Ouroboros — фрагмент 2 демо-видео.

> Важно: реальный прогон Ouroboros делал **только сводку** (MCP-оркестрация).
> Память, HITL, Safety, версионирование — это **код навыка / rule-движок**,
> не реальный прогон Ouroboros.

## Тестовые инстансы и live-интеграции (Jira/Bitbucket/Confluence Cloud + mail + Calendar)

Четыре уровня MCP-адаптеров (`mcp/_backends.py`, per-source через `MCP_BACKEND_<SOURCE>`):

1. **Файловый демо-контур** (`MCP_BACKEND=file`) — обезличенные выгрузки из `MCP_CASE_DIR` (офлайн-демо).
2. **Локальные тестовые инстансы** (`MCP_BACKEND=test`, `test-instances/`) — серверы с
   реальными контрактами Jira REST v2, Bitbucket Cloud REST 2.0, Confluence
   Cloud REST API v1 (calendar/mail в test-режиме — файлы). Офлайн, детерминированно.
3. **Реальная Jira** (`MCP_BACKEND_JIRA=atlassian`) — `get_issues` ходит к боевой Jira
   Cloud (Atlassian, `/rest/api/3/search/jql`, Basic auth), читает синтетику с лейблом `alpha-demo`.
3b. **Реальный Bitbucket Cloud** (`MCP_BACKEND_PR=bitbucket`) — `get_prs` ходит к боевому
   Bitbucket Cloud (Atlassian, `/repositories/{ws}/{slug}/pullrequests`), читает открытые PR
   из выделенного демо-репо. Auth: personal API token (Basic `email:token`, любой план) либо
   workspace access token (Bearer, Premium). (App Passwords удалены 28.07.2026.)
3c. **Реальная Confluence Cloud** (`MCP_BACKEND_CONFLUENCE=atlassian`) — `get_confluence_pages`
   ходит к боевой Confluence Cloud (Atlassian, `/wiki/rest/api/content/search`, CQL
   `space=KEY AND label="alpha-demo"`, Basic auth), читает страницы (release plan / decision log)
   с лейблом `alpha-demo`. Тот же Atlassian API-токен, что для Jira. Страницы попадают в сводку
   секцией «Контекст из Confluence» (kind=`doc`, уверенность 0.8).
4. **Live-интеграции** (`MCP_BACKEND=live`, по умолчанию) — Jira (atlassian) + mail (IMAP, пароль
   приложения) + Calendar (публичный iCal URL) + Confluence Cloud (atlassian). **4 боевые
   системы через MCP, stdlib-only, без Azure/OAuth.** Календарь/почта — `MCP_BACKEND_CALENDAR/MAIL=google`,
   Jira/Confluence — `atlassian`, PR/расшифровка — файлы кейса. Боевой Bitbucket —
   `MCP_BACKEND_PR=bitbucket` (поверх `live`).

```bash
# уровень 2 — тестовые инстансы (порты 9911-9914)
MCP_BACKEND=test python mcp/serve_all.py
MCP_BACKEND=test python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print

# уровень 3 — реальная Jira (.env: JIRA_URL/JIRA_EMAIL/JIRA_API_TOKEN)
python test-instances/seed_atlassian.py         # создать alpha-demo задачи в реальной Jira (ключи — по проекту JIRA_PROJECT, по умолчанию KAN-1/KAN-2)
MCP_BACKEND=atlassian python mcp/serve_all.py

# уровень 3b — реальный Bitbucket Cloud (.env: BITBUCKET_WORKSPACE/REPO_SLUG + personal API token или workspace token)
python test-instances/seed_bitbucket.py         # репо (workspace token) + ветка + PR; с personal token репо создать вручную
MCP_BACKEND_PR=bitbucket python mcp/serve_all.py
MCP_BACKEND_PR=bitbucket python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print

# уровень 3c — реальная Confluence Cloud (.env: CONFLUENCE_URL/SPACE/EMAIL/API_TOKEN или переиспользовать JIRA_*)
python test-instances/seed_confluence.py        # пространство + 2 страницы (label alpha-demo)
MCP_BACKEND_CONFLUENCE=atlassian python mcp/serve_all.py
MCP_BACKEND_CONFLUENCE=atlassian python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print

# уровень 4 — live: Jira + mail + Calendar + Confluence Cloud (+ опц. Bitbucket Cloud)
#   .env: JIRA_*, GOOGLE_ACCOUNT, GOOGLE_APP_PASSWORD (пароль приложения), GOOGLE_ICAL_URL,
#         CONFLUENCE_URL/SPACE/EMAIL/API_TOKEN
python test-instances/seed_google.py            # письмо-блокер в mail (или вручную) + проверка iCal
MCP_BACKEND=live python mcp/serve_all.py
MCP_BACKEND=live python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
#   с боевым Bitbucket: добавить MCP_BACKEND_PR=bitbucket
```

**mail/Calendar (Google):** mail — IMAP + пароль приложения (2FA → myaccount.google.com/apppasswords),
календарь — публичный iCal URL (`calendar.google.com → Settings → Integrate calendar`). Без Azure/OAuth.
Креды — только в `.env` (в `.gitignore`), в репозитории плейсхолдеры. Финальное демо-видео
собрано на уровне 4: данные реально сняты с Jira (APP-412/APP-521 в каноническом live-снимке) + mail (письмо-блокер) +
Calendar (событие «Релиз-синк · Альфа»); для детерминизма прогона live-снимок сохранён
в `examples/demo_case_alpha_live/` и прогнан через MCP (файловый бэкенд на live-данных).

## Демо-видео
`video/Athanor_Ouroboros_Project_Results_Demo.mp4` (2:20.62, 1920×1080,
H.264/AAC) — финальное демо-видео (< 3 мин, критерий «ДЕМО-видео» 30%).
Единственный файл в `video/`; QR-код презентации ведёт на
`/blob/main/video/Athanor_Ouroboros_Project_Results_Demo.mp4` (живой — HTTP 200).
Сборщик (PIL-рендер кадров + edge-tts DmitryNeural + сведение ffmpeg) — во внешнем
репозитории (`out/video/make_video.py`), в этот репозиторий выкладывается только
готовый MP4. Сценарий: `results/demo_scenario.md`, `docs/demo.md`.

## Проблема и решение

**AS IS.** Тимлид по релизам проводит 4–7 координационных встреч в день. Контекст
размазан по почте/календарю, Jira, Git, Confluence, чатам и расшифровкам. Подготовка вручную,
устные обязательства и причины решений теряются, блокеры всплывают поздно.

**TO BE.** До синка — сводка (статусы, PR, блокеры, зависимости, обязательства, у
каждого пункта источник и уверенность). После — решения, поручения (действие ·
ответственный · срок · источник), черновики (отправка после подтверждения человека).
Между — контроль обязательств, ранние блокеры, аудируемая память релиза.

## Команды

```bash
python scripts/run_demo.py                 # демо-прогон (examples/demo_case)
python scripts/run_tests.py                # все тесты (unittest, 90+)
python scripts/run_evaluation.py --engine rule   # корзина + метрики + эволюция навыка
python tests/run_basket.py --engine rule --run-id my_rule   # только корзина (TB-01..TB-17); my_rule — ваша метка
python tests/score.py --run results/runs/eval_20260716T232149 --mirror   # метрики каноничного прогона + артефакты
python -m athanor.cli run --case test-basket/TB-04 --engine rule --print   # один кейс
python -m athanor.cli demo                                    # демо через CLI
python -m athanor.cli versions                                # реестр версий навыка
python -m athanor.cli feedback --usefulness 3 --format-change "короче, блокеры сверху"
python -m athanor.cli promote --version v2                    # применить с контрольным тестом
python -m athanor.cli rollback --to v1                        # откат навыка
python -m evaluation run-all                                  # вся корзина + метрики (task4 §21)
python -m evaluation run --scenario scenario_01               # один сценарий (scenario_NN → TB-NN)
python -m evaluation compare-skills --baseline v1 --candidate v2  # сравнение версий навыка
python -m evaluation reproducibility                          # 3× прогона критических сценариев
python -m evaluation export-report --mirror                   # сводный отчёт
python mcp/serve_all.py                       # MCP-серверы (9901–9904; MCP_BACKEND=live → реальные сервисы)
python mcp/smoke_test.py                      # проверка MCP-серверов
```

## Лицензия
MIT (`LICENSE`). Проприетарные технологии не используются; зависимости — лицензионно
безопасны (stdlib Python — PSF; опционально pytest — MIT).
