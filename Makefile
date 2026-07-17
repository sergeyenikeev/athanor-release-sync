# Athanor release_sync — команды разработчика.
# Windows: используйте `make` из Git Bash либо копируйте команды вручную.
# Все команды самодостаточны (sys.path на src выставляют скрипты сами).

PY ?= python

.PHONY: serve run-basket run-basket-llm score mcp-smoke demo test evaluation clean

## Поднять четыре MCP-сервера (Ctrl+C для остановки)
serve:
	$(PY) mcp/serve_all.py

## Прогнать корзину TB-01..TB-12 офлайн (rule-baseline, без ключей)
run-basket:
	$(PY) tests/run_basket.py --engine rule

## Прогнать корзину через LLM (реальная — нужен .env с ключом; иначе mock)
run-basket-llm:
	$(PY) tests/run_basket.py --engine llm --mock

## Посчитать метрики по последнему прогону и сгенерировать артефакты
score:
	$(PY) tests/score.py --mirror

## Проверить, что MCP-серверы отвечают (initialize + tools/list + tools/call)
mcp-smoke:
	$(PY) mcp/serve_all.py & sleep 1; $(PY) mcp/smoke_test.py; kill %1 2>/dev/null || true

## Одиночный детерминированный демо-прогон (examples/demo_case, < 3 мин)
demo:
	$(PY) scripts/run_demo.py

## Все тесты одной командой (unittest, без зависимостей)
test:
	$(PY) scripts/run_tests.py

## Полная оценка: корзина + метрики + эволюция навыка (promote v2 + rollback)
evaluation:
	$(PY) scripts/run_evaluation.py --engine rule

clean:
	$(PY) -c "import shutil,glob; [shutil.rmtree(p, ignore_errors=True) for p in ['results/scratch'] + glob.glob('**/__pycache__', recursive=True)]"
