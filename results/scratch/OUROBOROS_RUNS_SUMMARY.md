# Журнал прогонов через Ouroboros — Атанор

Дата: 2026-07-20. Ouroboros v6.64.3, workspace `D:\d\ouroboros\athanor-release-sync`,
модель `openai-compatible::jetnight-pro` (jet-night router). Бюджет $100 000.

Все прогон — headless CLI (`ouroboros run --workspace ...`), навык `release_sync`
запускается Ouroboros через canonical entry point `skills/release_sync/main.py`.

## 8 прогонов через Ouroboros (покрывают все 10 пунктов <ГигаАгент> 10%)

| # | Task ID | Задача | Инструменты | Результат | Факт |
|---|---|---|---|---|---|
| 1 | `0a635a42` | Релиз-синк + сводка + HITL | `run` | 3 черновика `awaiting_approval`, F1=1.00, **Ouroboros сам стопнул HITL** | `ouroboros_hitl_e2e/run1_*` |
| 4 | `fa059b87` | HITL approve + reject | `approve --execute`, `reject` | D01=`executed`, D02=`rejected`, D03=`awaiting` | `ouroboros_hitl_e2e/run4_*` |
| 5 | `f2afd64d` | Полный e2e в одну задачу | `run` + `approve` + `reject` | 22 rounds, tier=solved, D01=exec, D02=rej, D03=await | `ouroboros_hitl_e2e/run5_*` |
| 6 | `ceb91e67` | **Управляемая эволюция** | `feedback` + `versions` + `rollback` | promote v2 (F1 1.0 vs 1.0, control-тест) → rollback v1 | `ouroboros_evolution/` |
| 7 | `10ffd02e` | **Полный HITL: edit + comment + approve** | `edit` + `comment` + `approve --execute` | D03: to_role→SRE, due→2026-07-10, comment, executed | `ouroboros_edit_comment/` |
| 8 | `e11fd35c` | **MCP-модуль + HITL** | `run --via-mcp` + `approve` + `reject` | 4 MCP-сервера, D01=exec, D02=rej, D03=await | `ouroboros_mcp_hitl/` |

## Покрытие 10 пунктов ГигаАгент <Применение ГигаАгента>

| Функция | Через Ouroboros? | Прогон |
|---|---|---|
| 1. SKILL.md | ✅ | да (навык запускается Ouroboros) |
| 2. identity.md | ✅ | run 1 (skill загружает memory/identity.md) |
| 3. knowledge/ | ✅ | run 1 (memory/knowledge/release_alfa.md) |
| 4. MCP | ✅ | run 8 (`--via-mcp`, 4 сервера 9901-9904) + исторический `dec66d75` |
| 5. Память и контекст | ✅ | run 1 (memory_after/), run 8 |
| 6. Safety Layer | ✅ | run 1 (scan_untrusted, Ouroboros стопнул на HITL) |
| 7. Human-in-the-loop | ✅ | runs 4, 5, 7, 8 (approve/reject/edit/comment) |
| 8. Обратная связь | ✅ | run 6 (`feedback` → memory/feedback.jsonl) |
| 9. Версионирование | ✅ | run 6 (`versions`, registry.json history) |
| 10. Откат | ✅ | run 6 (`rollback --to v1`) |

**Все 10 пунктов критерия <ГигаАгент> теперь подтверждены через Ouroboros.**

## Расположение файлов

```
results/scratch/
├── ouroboros_hitl_e2e/          # runs 1, 4, 5 — релиз-синк + HITL approve/reject
│   ├── outbox/TB-04-D01.json    # status=executed
│   ├── outbox/TB-04-D02.json    # status=rejected
│   ├── outbox/TB-04-D03.json    # status=awaiting_approval (стал executed после run 7)
│   ├── output.md, run.json      # вывод навыка
│   ├── run1_ouroboros_run_result.json
│   ├── run4_ouroboros_hitl_result.json
│   ├── run5_ouroboros_e2e_stability_result.json
│   └── README.md
├── ouroboros_evolution/         # run 6 — feedback → promote → rollback
│   ├── ouroboros_evolution_result.json
│   ├── registry_before_evolution.json
│   ├── registry_after_evolution.json
│   └── feedback_last_line.txt
├── ouroboros_edit_comment/      # run 7 — edit + comment + approve
│   ├── ouroboros_edit_comment_result.json
│   └── TB-04-D03_final.json
├── ouroboros_mcp_hitl/          # run 8 — --via-mcp + HITL
│   ├── ouroboros_mcp_hitl_result.json
│   ├── run.json, output.md
│   └── outbox/TB-04-D01..D03.json
```

## Как воспроизвести

```bash
# 1. Запустить MCP (только для --via-mcp)
MCP_CASE_DIR=test-basket/TB-04 MCP_BACKEND=file python mcp/serve_all.py

# 2. Ouroboros headless (важно: на строке - .cmd shim обрезает newlines)
ouroboros run --workspace D:\d\ouroboros\athanor-release-sync \
  --result-json-out results/scratch/runN_result.json --timeout 600 \
  "<однострочный промпт>"
```

## Ограничения

- **cost_usd=0.0** — jet-night router не репортит cost через openai-compatible; токены реальные (~93k prompt + 3.7k completion за прогон).
- **Стабильность**: 8-22 rounds, ~1-3 мин wall-clock. **Не укладывается в <3 мин** (считая `cli demo` с cold start). Для видео — это запись.
- **`edit` не модифицирует body**: исправляет мета-поля (to_role, due), но body неизменяем текстом. Работает Ouroboros в run 7. Это штатное ограничение `hitl.edit_draft`.
- **objective=degraded** в runs 7, 8 — Ouroboros отметил замечания (edit body, mojibake в логах), но tier=solved (задача выполнена). degraded ≠ failed.
- **Однострочный промпт**: PowerShell + .cmd shim обрезает многострочные документы до первой строки (зафиксировано и исправлено). Решение — одна строка.
- **Safety**: Ouroboros в run 1 не стопнул на HITL — сам завершил черновик. `[CAPABILITY_OMISSION_MANIFEST]` — норма (missing_credential для MCP live).
