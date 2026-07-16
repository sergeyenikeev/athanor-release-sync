# Demo-режим

Одна команда, детерминированно, < 3 минут, без сети и API-ключей.

## Запуск
```bash
python scripts/run_demo.py
# эквивалент: python -m athanor.cli demo --case examples/demo_case --engine rule
```

## Что происходит (end-to-end)
1. Агент читает событие релиз-синка «Альфа» 03.07 (calendar.json).
2. Через файлы (или MCP-заглушки) — задачи APP-412/APP-521, PR #128, письмо SRE,
   обязательства с прошлого синка (память релиза).
3. Детерминированная сводка: статусы, PR, обязательства, конфликты, блокеры —
   у каждого пункта `(источник · уверенность)`.
4. Расшифровка → 1 решение + 1 поручение (действие · ответственный · срок · источник).
5. Поручение → черновик письма в outbox (`awaiting_approval`).
6. Память релиза обновлена (решение с заменой старого + новое обязательство, журнал).
7. HITL: черновик подтверждён и исполнен (демо-имитация отправки).
8. Артефакты: `results/demo/<run_id>/` (output.md, run.json, memory_after/, outbox/).

## Через MCP-заглушки
```bash
python mcp/serve_all.py                # терминал 1 (MCP_CASE_DIR=examples/demo_case по умолчанию)
python -m athanor.cli run --case examples/demo_case --via-mcp --print   # терминал 2
```

## Полная оценка (с эволюцией навыка)
```bash
python scripts/run_evaluation.py --engine rule
# корзина TB-01..TB-12 → метрики → promote v2 (контрольный тест) → rollback v1
```

## Повторный запуск
Demo идемпотентен: каждый прогон создаёт новую папку `results/demo/<run_id>`;
исходное состояние (examples/demo_case, memory/knowledge) не меняется.
