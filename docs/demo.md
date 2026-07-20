# Demo-режим

Одна команда, детерминированно, < 3 минут, без сети и API-ключей.

## Запуск
```bash
python scripts/run_demo.py
# эквивалент: python -m athanor.cli demo --case examples/demo_case --engine rule
```

## Что происходит (end-to-end)
1. Агент читает событие релиз-синка «Альфа» 03.07 (calendar.json).
2. Через файлы (или MCP-серверы) — задачи APP-412/APP-521, PR #128, письмо SRE,
   обязательства с прошлого синка (память релиза).
3. Детерминированная сводка: статусы, PR, обязательства, конфликты, блокеры —
   у каждого пункта `(источник · уверенность)`.
4. Расшифровка → 1 решение + 1 поручение (действие · ответственный · срок · источник).
5. Поручение → черновик письма в outbox (`awaiting_approval`).
6. Память релиза обновлена (решение с заменой старого + новое обязательство, журнал).
7. HITL: черновик подтверждён и исполнен (демо-имитация отправки).
8. Артефакты: `results/demo/<run_id>/` (output.md, run.json, memory_after/, outbox/).

## Боевой e2e через Ouroboros (HITL в чате)

Помимо детерминированного `cli demo` (авто-подтверждение), есть боевой прогон через
Ouroboros v6.64.3, где человек подтверждает/отклоняет черновики **в чате Ouroboros**:
```bash
ouroboros run --workspace . --jsonl --timeout 600 "<промпт одной строкой>"
```
Навык `release_sync` (skills/release_sync/main.py) принимает команды:
`run`, `approve`, `reject`, `edit`, `comment`, `feedback`, `versions`, `promote`,
`rollback`. Артефакты: `results/scratch/ouroboros_{hitl_e2e,evolution,edit_comment,
mcp_hitl}/` + `OUROBOROS_RUNS_SUMMARY.md`. Демо-видео 2:30 включает клипы боевого
e2e (F2=e2e_launch, F6=e2e_hitl) + 5 cloud_capture клипов (F3).

## Через MCP-серверы (file-режим)
```bash
python mcp/serve_all.py                # терминал 1 (MCP_CASE_DIR=examples/demo_case по умолчанию)
python -m athanor.cli run --case examples/demo_case --via-mcp --print   # терминал 2
```

## Через тестовые инстансы (уровень интеграций)
Локальные серверы с реальными контрактами Jira REST v2, Bitbucket Cloud REST 2.0,
Confluence Cloud REST API v1 и синтетикой «Альфа»
(см. `test-instances/README.md`).
```bash
python test-instances/serve_all.py                    # терминал 1 (порты 9911-9914)
MCP_BACKEND=test python mcp/serve_all.py              # терминал 2 (MCP-адаптеры → тестовые инстансы)
MCP_BACKEND=test python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print  # терминал 3
```
MCP-адаптеры (`mcp/_backends.py`) ходят к тестовым инстансам по реальным
HTTP-контрактам и конвертируют ответы в схему агента. Смена URL → боевые
Jira/Bitbucket/Confluence. Результат идентичен файловому демо-контуру
(плюс секция «Контекст из Confluence» — release plan / decision log).

## Полная оценка (с эволюцией навыка)
```bash
python scripts/run_evaluation.py --engine rule
# корзина TB-01..TB-17 → метрики → promote v2 (контрольный тест) → rollback v1
```

## Повторный запуск
Demo идемпотентен: каждый прогон создаёт новую папку `results/demo/<run_id>`;
исходное состояние (examples/demo_case, memory/knowledge) не меняется.
