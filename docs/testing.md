# Тестирование

Одна команда, без внешних зависимостей (unittest из stdlib):
```bash
python scripts/run_tests.py          # все 117 тестов
python -m unittest discover -s tests -t .   # эквивалент
```

## Структура
- `tests/unit/` — модели, парсеры, нормализаторы, conflict detector, memory storage,
  approval gate, prompt-injection detector, metrics calculator, skill versioning.
- `tests/integration/` — MCP-серверы, полный workflow агента,
  **тестовые инстансы** (`test_test_instances.py`: реальные контракты Jira REST v2,
  Bitbucket Cloud REST 2.0, Confluence + конвертация через `mcp/_backends.py` при `MCP_BACKEND=test`).
- `tests/e2e/` — вся корзина TB-01..TB-17; эволюция навыка (promote v2 + rollback); HITL-обход (TB-16).
- `tests/negative/` — отсутствующий файл, битый JSON, timeout/ошибка LLM, пустой
  ответ, некорректная схема, недоступный MCP, превышение бюджета, внешнее действие
  без подтверждения, prompt injection, пустая расшифровка.

## Тестовая корзина (`test-basket/TB-01..TB-17`)
17 обезличенных сценариев (15 обязательных task4 §5 + 2 доп.): обычный синк, блокер,
конфликт Jira↔письмо, расшифровка (решения vs идеи), поручение без срока, без владельца,
изменение решения, отмена обязательства, похожие задачи, неполные данные, недоступный
источник + prompt injection, повторный прогон после обратной связи (v2), неявный срок
через релизное окно, недоступный трекер (Jira), повреждённая расшифровка, внешнее
действие без подтверждения (HITL), повторный прогон с памятью (2 цикла).

Каждый сценарий: `input/{calendar,tracker,mail,transcript,memory_seed}` +
`expected/{decisions,actions,blockers,summary,flags}.json` + `meta.json` +
`metadata.yaml` + `README.md` (task4 §7). TB-13..TB-17 — эталон зафиксирован вручную
(`manual_expected=True`, task4 §20); TB-17 имеет отдельный `cycle1/` (первый цикл).

Генерация: `python scripts/gen_basket.py` (входы TB-01..TB-12) →
`python scripts/gen_scenarios_extra.py` (TB-13..TB-17 + metadata.yaml/README для всех) →
`python scripts/gen_expected.py` (эталоны TB-01..TB-12; TB-13..TB-17 пропускаются).

## Метрики
```bash
python tests/run_basket.py --engine rule --run-id my_rule
python tests/score.py --run results/runs/eval_20260716T232149 --mirror
# → metrics.json, metrics.csv, results_summary.md, evaluation_report.html
```
См. `docs/evaluation.md`.
