# ДЕМО-сценарий: релиз-синк проекта «Альфа» (demo_case_alpha)

**Кейс:** `examples/demo_case_alpha/` — сквозной обезличенный сценарий релиз-синка
проекта «Альфа», релиз `ALPHA-2026.07`, 03.07 14:00. Содержит: событие календаря,
2 Jira-задачи, открытый PR, письмо-блокер, обязательства с прошлого синка (память),
короткую расшифровку (решение + 2 поручения). Конфликт Jira↔письмо и блокер
`payment-adapter` выявляются автоматически.

**Выбор (task4 §25):** понятен без объяснений; данные из нескольких источников
(календарь, Jira, Git, почта, расшифровка, память); заметный блокер/конфликт;
сводка; решения и поручения; Human-in-the-loop; обновление памяти; < 3 мин;
не самый сложный; детерминированный (rule-движок, 100% воспроизводимость).

## Запуск (три режима)

```bash
# 1) файловый демо-контур (офлайн, по умолчанию)
python -m athanor.cli demo --case examples/demo_case_alpha --engine rule
# эквивалент: python scripts/run_demo.py --case examples/demo_case_alpha

# 2) через MCP-серверы (файловый бэкенд)
python mcp/serve_all.py                                            # терминал 1
python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print

# 3) через реальную Jira (боевой контракт Atlassian, MCP_BACKEND=atlassian)
python test-instances/seed_atlassian.py                                 # создать KAN-1/KAN-2 в реальной Jira
python test-instances/gen_live_case.py                                  # live-кейс examples/demo_case_alpha_live
MCP_BACKEND=atlassian python mcp/serve_all.py                           # терминал 1 (MCP → Jira)
MCP_BACKEND=atlassian python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

Все три режима дают идентичный результат (сводка, конфликт, блокер, решения,
поручения, черновики HITL, обновление памяти). Режим 3 (реальная Jira) —
основа финального демо-видео: задачи KAN-1/KAN-2 читаются из боевой Jira, конфликт
KAN-1 (Jira «Готово» ↔ письмо «блокер») выявляется на live-данных.

## Шаги ДЕМО
1. Запуск (одна из команд выше) — сводка с конфликтом Jira↔письмо и блокером.
2. В `output.md`: ⚠ КОНФЛИКТ по APP-412 (Jira «готово» ↔ письмо «блокер»),
   приоритет источников, HITL-эскалация; блокер `payment-adapter не в prod`.
3. Решения/поручения из расшифровки с источником и уверенностью (2 поручения:
   Разработчик backend — release-notes, SRE — деплой payment-adapter; срок 2026-07-03).
4. `python -m athanor.cli approve --draft <outbox>/<id>.json --execute` — HITL.
5. `memory_after/` — обновлённая память релиза (новое решение + 2 обязательства,
   журнал `journal.log`).

## Артефакты
- Прогон: `results/demo/<run_id>/` (`output.md`, `run.json`, `memory_after/`, `outbox/`)
- Метрики: `results/metrics.json` (17 сценариев, F1 100%)
- Демо-видео: `video/Athanor_Ouroboros_Project_Results_Demo.mp4` (2:20.76)

Длительность прогона < 3 мин (детерминированный rule-движок, ~1 с на цикл).
Длительность демо-видео — 2:20.76 (< 3 мин, критерий «ДЕМО-видео» 30%).