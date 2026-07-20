# Боевой прогон Ouroboros: Human-in-the-loop end-to-end

Дата: 2026-07-20. Ouroboros v6.64.3, workspace `D:\d\ouroboros\athanor-release-sync`,
провайдер `openai-compatible::jetnight-pro` (jet-night router). Бюджет $100000.

## Что доказано

Человек подтверждает/отклоняет черновики писем **через чат Ouroboros** — Ouroboros
вызывает навык `release_sync`, навык выполняет HITL-команды (`approve`/`reject`),
статусы черновиков меняются в `outbox/*.json`. Без команды человека Ouroboros
**сам не подтверждает** — черновики остаются в `awaiting_approval`.

## Прогоны

| Run | Task ID | Что | Результат |
|---|---|---|---|
| 1 | `0a635a42` | `run` (навык сам) | 3 черновика `awaiting_approval`, F1=1.00, objective=pass, tier=solved |
| 4 | `fa059b87` | HITL approve D01 + reject D02 | D01=`executed`, D02=`rejected`(duplicate), D03=`awaiting_approval` |
| 5 | `f2afd64d` | Полный e2e в одной задаче | 22 rounds, D01=`executed`, D02=`rejected`(owner-resolvable), D03=`awaiting_approval`, tier=solved |

## Финальные статусы черновиков (артефакт)

```
TB-04-D01.json: status=executed  executed_at=2026-07-20T00:08:41
TB-04-D02.json: status=rejected  rejected_at=2026-07-20T00:08:49  reason=owner-resolvable
TB-04-D03.json: status=awaiting_approval  (человек не трогал — ждёт решения)
```

## Файлы

- `outbox/TB-04-D01.json`, `D02.json`, `D03.json` — черновики с финальными статусами
- `output.md` — сводка агента (print из run)
- `run.json` — структурированный результат прогона навыка
- `run1_ouroboros_run_result.json` — полный JSON результата задачи Ouroboros `0a635a42` (run)
- `run4_ouroboros_hitl_result.json` — JSON результата `fa059b87` (HITL approve+reject)
- `run5_ouroboros_e2e_stability_result.json` — JSON результата `f2afd64d` (полный e2e)

## Как воспроизвести

```bash
# 1. Поднять MCP-серверы (опционально, для --via-mcp)
MCP_CASE_DIR=test-basket/TB-04 MCP_BACKEND=file python mcp/serve_all.py

# 2. Запуск Ouroboros (headless CLI)
ouroboros run --workspace D:\d\ouroboros\athanor-release-sync --jsonl \
  --result-json-out results/scratch/runN_result.json --timeout 600 \
  "<промпт одной строкой без переносов>"
```

Промпт должен быть **одной строкой** — PowerShell/.cmd shim обрезает многострочные
аргументы до первого параграфа (зафиксировано в прогонах 2/3, task `c5d7ab6f`/`f464c226`).

## Честные ограничения

- **Стоимость**: `cost_usd=0.0` в JSON — jet-night router не репортит cost в
  openai-compatible-провайдере; токены реальные (prompt≈93k, completion≈3.7k на прогон).
- **Длительность**: 8–22 rounds на задачу, ~1–3 мин wall-clock. **Не для демо-видео <3 мин**
  (там `cli demo` с автопаproved-митацией). Это боевой артефакт для критерия
  «Применение ГигаАгента».
- **Safety**: Ouroboros в run 1 честно остановился на HITL — не подтвёрдил черновики
  сам. `[CAPABILITY_OMISSION_MANIFEST]` системный блок — норма (missing_credential
  для MCP live-режима; для file/rule не помеха).
- **CLI `edit`/`comment`** добавлены, но в боевом прогоне не проверялись (только
  `approve`/`reject`). Юнит-тесты `tests/unit/test_cli_hitl.py` покрывают все 4.
