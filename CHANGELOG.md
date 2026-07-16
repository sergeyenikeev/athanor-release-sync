# Changelog

## [1.0.0-mvp] — 2026-07-16

### Добавлено (evident-слой поверх существующего ядра)
- `pyproject.toml` (метаданные + опциональная установка); `scripts/_bootstrap.py` —
  пути `src/` без `PYTHONPATH`/установки (работает в чистом окружении).
- Тестовая корзина `test-basket/TB-01..TB-12` (обезличенные синтетические сценарии):
  `input/` + `expected/{decisions,actions,blockers,summary,flags}.json` + `meta.json`.
  Генераторы: `scripts/gen_basket.py`, `scripts/gen_expected.py`.
- `examples/demo_case` — данные по умолчанию для MCP-заглушек.
- Харнесс `tests/run_basket.py` + скорер `tests/score.py`: метрики (micro P/R/F1,
  coverage, p50/p95, успех, fallback, стоимость), артефакты `metrics.json/csv`,
  `results_summary.md`, `evaluation_report.html`.
- Тесты: `tests/{unit,integration,e2e,negative}` (90+ unittest, одна команда).
- `src/athanor/feedback.py` — сохранение обратной связи (JSONL) + предложение
  по изменению навыка.
- `src/athanor/skill_versioning.py` — реестр версий, promote с контрольным тестом
  (gate «нет деградации F1»), rollback. `skills/release_sync/versions/registry.json`.
- `src/athanor/control.py` — контрольные тесты для эволюции (TB-01/TB-02/TB-04).
- `src/athanor/enrich.py` — Evidence linking, уверенность по источнику,
  структурированные `Blocker`.
- Расширение моделей: `Evidence`, `Blocker`, `Feedback`, `SkillVersion`,
  `DraftAction`, `Project`, `Release`, `Meeting`; опц. поля `ActionItem`/`Decision`
  (id, confidence, source_evidence, timestamps).
- `security.py`: allowlist инструментов, `mask_secrets`, `validate_memory_file`.
- `hitl.py`: полный набор статусов (proposed/awaiting_approval/approved/rejected/
  executed/failed) + reject/edit/comment/execute.
- `llm.py`: промпт вынесен в `skills/release_sync/prompts/extract.md`; mock-LLM
  (`ATHANOR_LLM_MOCK=1`); budget-лимит (`LLM_BUDGET_USD`); логирование стоимости.
- CLI: `demo`, `basket`, `score`, `feedback`, `versions`, `promote`, `rollback`.
- `scripts/run_demo.py`, `run_tests.py`, `run_evaluation.py`, `export_results.py`.
- `config/{demo,local,test}.yaml`; `docs/{architecture,demo,testing,security,mcp,
  evaluation}.md`; `README.md`; `CHANGELOG.md`.
- `memory/knowledge/` расширены поддиректориями (organization, projects, releases,
  decisions, terminology, user_preferences, policies).

### Исправлено
- `_slug`: мягкий/твёрдый знаки убираются (раньше `_`); «Альфа» → `alfa` (был
  `al_fa`, из-за чего `memory/knowledge/release_alfa.md` не находился).
- `summary.py`: дедуп ключей в конфликте Jira↔письмо (раньше дубль при повторном
  вхождении ключа в письме — TB-03).
- `extract.py`: очистка рамочных префиксов решения («Договорились:» и т.п.); хвост
  причины убирается из текста решения.
- `enrich._confidence_for_source`: регистронезависимый поиск ключа (раньше
  lower-case ломал regex, confidence был 0.0 для APP-412).
- `sources.py`: устойчивость к битому JSON и некорректным схемам (skip + warning);
  убран ternary-as-statement.
- `config.py`: добавлены `LOCAL_LLM_BASE_URL`, `LLM_BUDGET_USD`, `LLM_PRICE_PER_1K`,
  `ATHANOR_LLM_MOCK` в дефолты.
- Makefile: команды ссылаются на существующие скрипты.

### Результаты прогона (rule-baseline, committed)
12/12 сценариев success; A·P/R/F1 = 100%/100%/100%; среднее время < 0.01 с;
mock-LLM путь — те же метрики. Эволюция: promote v2 (F1 1.0 vs 1.0) + rollback v1.
