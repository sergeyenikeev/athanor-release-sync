# Ouroboros — мозг команды (команда «Атанор», Sber AI Hack)

ИИ-агент подготовки к **релиз-синкам и разборам инцидентов**: восстановление
контекста из нескольких систем, формирование briefing перед встречей, извлечение
решений/поручений/ответственных/сроков из расшифровки, контроль договорённостей,
раннее выявление блокеров, аудируемая память релизов и управляемое улучшение
навыка по обратной связи. На базе технологии **Ouroboros** (навык + память + MCP +
Safety Layer + Human-in-the-loop).

> Демонстрационный контур — обезличенные синтетические выгрузки. Боевые коннекторы
> (Outlook/Jira/Git/Confluence) — тот же интерфейс через MCP, после пилота.

## Быстрый старт (5 шагов)

```bash
# 1. Клонировать репозиторий
git clone <repo-url> athanor-release-sync && cd athanor-release-sync

# 2. Установить зависимости (нет внешних runtime-зависимостей — только Python 3.10+)
python -m pip install -e .            # опционально; скрипты работают и без установки

# 3. Скопировать .env.example (для демо не обязательно — работает без ключей)
cp .env.example .env                  # заполнить LLM_API_KEY только для реальной LLM

# 4. Запустить demo (одна команда, < 3 мин, без сети/ключей)
python scripts/run_demo.py

# 5. Открыть результат
#    results/demo/<run_id>/output.md  — briefing, решения, поручения, черновики, память
#    results/demo/<run_id>/memory_after/  — обновлённая память релиза
```

## Команды

```bash
python scripts/run_demo.py                 # демо-прогон (examples/demo_case)
python scripts/run_tests.py                # все тесты (unittest, 90+)
python scripts/run_evaluation.py --engine rule   # корзина + метрики + эволюция навыка
python tests/run_basket.py --engine rule --run-id rule_v1   # только корзина (TB-01..TB-17)
python tests/score.py --run results/runs/rule_v1 --mirror   # только метрики + артефакты
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
python mcp/serve_all.py                       # MCP-заглушки (9901–9903)
python mcp/smoke_test.py                      # проверка MCP-заглушек
```

## Проблема и решение

**AS IS.** Тимлид по релизам проводит 4–7 координационных встреч в день. Контекст
размазан по Outlook/Jira/Git/Confluence/чатам/расшифровкам. Подготовка вручную,
устные обязательства и причины решений теряются, блокеры всплывают поздно.

**TO BE.** До синка — сводка (статусы, PR, блокеры, зависимости, обязательства, у
каждого пункта источник и уверенность). После — решения, поручения (действие ·
ответственный · срок · источник), черновики (отправка после подтверждения человека).
Между — контроль обязательств, ранние блокеры, аудируемая память релиза.

## Реализованные функции

| Функция | Статус | Доказательство |
|---|---|---|
| Сводка перед релиз-синком (детерминированная) | реализовано | `src/athanor/summary.py`, `results/runs/after_fix/TB-01/output.md` |
| Источники: календарь, трекер, PR, почта, расшифровки | демо-выгрузки (MCP) | `mcp/`, `examples/demo_case` |
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
| Боевые коннекторы Outlook/Jira/Git/Confluence | подготовлен интерфейс | `mcp/` (после пилота) |
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
(`llm`/`rule`), `MCP_*` (порты заглушек), `MCP_TRANSCRIPTS_DOWN` (TB-11).
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
- **MCP** — `mcp/` (3 заглушки, `mcp_config.json`).
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
python scripts/run_tests.py                                   # 90+ тестов, одна команда
python scripts/run_evaluation.py --engine rule                # корзина + метрики + эволюция
```
Подробнее — `docs/testing.md`, `docs/evaluation.md`. Результаты — `results/`.

## Известные ограничения
- Боевые коннекторы Outlook/Jira/Git/Confluence не подключены (демо-адаптеры с тем
  же интерфейсом); нужен доступ к системам и ИБ-согласование для пилота.
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
mcp/         _base, calendar_mail, tracker_repo, transcripts, serve_all, smoke_test, mcp_config.json
test-basket/ TB-01..TB-17 (input + expected + meta + metadata.yaml + README); TB-13..TB-17 — эталон зафиксирован вручную (task4 §20)
tests/       unit, integration, e2e, negative, run_basket.py, score.py
scripts/     _bootstrap, run_demo, run_tests, run_evaluation, export_results, gen_basket, gen_expected
examples/    demo_case (данные по умолчанию для MCP)
results/     runs/, demo/, metrics.json, metrics.csv, results_summary.md, evaluation_report.html
```

## Демо-видео
[ВСТАВИТЬ ССЫЛКУ на демо-видео] — сценарий в `docs/demo.md` и `out/03_scenariy_demo.md`.

## Лицензия
MIT (`LICENSE`). Проприетарные технологии не используются; зависимости — лицензионно
безопасны (stdlib Python — PSF; опционально pytest — MIT).
