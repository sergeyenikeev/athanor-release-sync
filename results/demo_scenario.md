# ДЕМО-сценарий: релиз-синк проекта «Альфа» (demo_case_alpha)

**Кейс:** `examples/demo_case_alpha/` — сквозной обезличенный сценарий релиз-синка
проекта «Альфа», релиз `ALPHA-2026.07`, 03.07 14:00. Содержит: событие календаря,
2 Jira-задачи, открытый PR, письмо-блокер, обязательства с прошлого синка (память),
короткую расшифровку (решение + 2 поручения). Конфликт Jira↔письмо и блокер
`ППРБ-адаптер` выявляются автоматически.

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
python mcp/serve_all.py
python -m athanor.cli run --case examples/demo_case_alpha --via-mcp --engine rule --print

# 3) через реальную Jira (боевой контракт Atlassian, MCP_BACKEND=atlassian)
python test-instances/seed_atlassian.py
python test-instances/gen_live_case.py
MCP_BACKEND=atlassian python mcp/serve_all.py
MCP_BACKEND=atlassian python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print
```

Все три режима дают идентичный результат (сводка, конфликт, блокер, решения,
поручения, черновики HITL, обновление памяти). Режим 3 (реальная Jira) — основа
финального демо-видео: задачи APP-412/APP-521 (канонический live-снимок) — в сводке,
конфликт APP-412 (Jira «Готово» ↔ письмо «блокер») выявляется на live-данных.

## Шаги ДЕМО
1. Запуск (одна из команд выше) — сводка с конфликтом Jira↔письмо и блокером.
2. В `output.md`: ⚠ КОНФЛИКТ по APP-412 (Jira «готово» ↔ письмо «блокер»),
   приоритет источников, HITL-эскалация; блокер `ППРБ-адаптер не в prod`.
3. Решения/поручения из расшифровки с источником и уверенностью (2 поручения:
   Разработчик backend — release-notes, SRE — деплой ППРБ-адаптера; срок 2026-07-03).
4. `python -m athanor.cli approve --draft <outbox>/<id>.json --execute` — HITL.
5. `memory_after/` — обновлённая память релиза (новое решение + 2 обязательства,
   журнал `journal.log`).

## Артефакты
- Прогон: `results/runs/eval_20260719T_fixed/` (`output.md`, `run.json`, `memory_after/`, `outbox/`)
- Метрики: `results/metrics.json` (17 сценариев, F1 100%)
- Боевой e2e через Ouroboros: `results/scratch/ouroboros_hitl_e2e/`
  (task `de797d3f`, 40 rounds, HITL approve/reject в чате Ouroboros)
- Демо-видео: `video/Athanor_Ouroboros_Project_Results_Demo.mp4` (2:30;
  F2 — e2e_launch клип Ouroboros UI; F3 — 5 cloud_capture клипов
  Calendar/mail/Jira/Bitbucket/Confluence Cloud; F6 — e2e_hitl клип
  HITL approve/reject через Ouroboros; F8 — CLI эволюция)

Длительность прогона < 3 мин (детерминированный rule-движок, ~1 с на цикл).
Длительность демо-видео — 2:30 (< 3 мин, критерий «ДЕМО-видео» 30%).

## Монтажный лист (10 фрагментов, 2:30)

| # | Таймкод | Фрагмент | Источник клипа |
|---|---|---|---|
| 1 | 00:00–00:17 | Проблема: контекст по 6 системам | PIL |
| 2 | 00:17–00:34 | Запуск: Ouroboros UI + task sent | `ouroboros_e2e_launch.mp4` (Playwright) |
| 3 | 00:34–00:53 | Сбор контекста: 5 источников через MCP | 5× `cloud_*.mp4` (Calendar/mail/Jira/Bitbucket/Confluence) |
| 4 | 00:53–01:11 | Сводка и блокер: конфликт Jira↔PR↔письмо | PIL |
| 5 | 01:11–01:23 | Анализ расшифровки: 2 поручения | PIL |
| 6 | 01:23–01:41 | HITL: approve/reject в чате Ouroboros | `ouroboros_e2e_hitl.mp4` (Playwright) |
| 7 | 01:41–01:52 | Память релиза обновлена | PIL |
| 8 | 01:52–02:07 | Обратная связь: promote v2 + rollback | F8_real_clip (CLI) |
| 9 | 02:07–02:19 | Метрики: 17 сценариев, F1 100% | PIL |
| 10 | 02:19–02:30 | Финал: следующий шаг — пилот | PIL |