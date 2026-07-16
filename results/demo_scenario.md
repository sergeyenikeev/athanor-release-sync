# ДЕМО-сценарий: TB-03 «Конфликт Jira и письма»

**Выбор (task4 §25):** понятен без объяснений; данные из нескольких источников (календарь, Jira, Git, почта, расшифровка); заметный блокер/конфликт; сводка; решения и поручения; Human-in-the-loop; обновление памяти; < 3 мин; не самый сложный.

## Шаги ДЕМО
1. `python -m athanor.cli run --case test-basket/TB-03 --engine rule --print` — сводка с конфликтом
2. Показать в output.md: ⚠ КОНФЛИКТ по APP-412 (Jira «готово» ↔ письмо «блокер»), приоритет источников, HITL-эскалация
3. Показать решения/поручения из расшифровки с источником и уверенностью
4. `python -m athanor.cli approve --draft results/scratch/TB-03/outbox/<id>.json` — HITL-подтверждение
5. Показать memory_after/ — обновлённая память релиза (аудит)

## Артефакты
- Прогон: `results/runs/after_fix/TB-03/output.md`, `run.json`
- Эталон: `test-basket/TB-03/expected/`
- Метрики: `results/runs/after_fix/TB-03/metrics.json`

Длительность < 3 мин (детерминированный rule-движок, ~1 с на цикл).