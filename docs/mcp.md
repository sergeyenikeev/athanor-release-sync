# MCP-инструменты

Три MCP-заглушки (streamable_http, JSON-RPC 2.0) — `mcp/`. Демо-адаптеры читают
обезличенные выгрузки из папки кейса (`MCP_CASE_DIR`, по умолчанию `examples/demo_case`).
Боевые коннекторы (Outlook/Jira/Git/Confluence) — тот же интерфейс, после пилота.

## Серверы и инструменты
| Сервер | Порт | Инструменты |
|---|---|---|
| calendar_mail | 9901 | `get_events`, `get_mail` |
| tracker_repo | 9902 | `get_issues`, `get_prs` |
| transcripts | 9903 | `get_transcript(case_id)` (при `MCP_TRANSCRIPTS_DOWN=1` — ошибка → деградация) |

## Запуск
```bash
python mcp/serve_all.py                                   # все три, данные examples/demo_case
MCP_CASE_DIR=test-basket/TB-03 python mcp/serve_all.py    # данные конкретного кейса
python mcp/smoke_test.py                                  # initialize + tools/list + tools/call
```

## Конфиг для Ouroboros
`mcp/mcp_config.json` — объявление серверов для Settings → MCP:
```json
{"mcpServers": {"calendar_mail": {"transport":"streamable_http","url":"http://127.0.0.1:9901/mcp"}, …}}
```

## Клиент
`src/athanor/sources.py::McpClient` — минимальный JSON-RPC 2.0 POST-клиент
(`initialize`/`tools/list`/`tools/call`). `load_case_via_mcp` собирает `CaseInput`
из трёх заглушек с per-source обработкой ошибок → `sources_down` (graceful).

## Подготовленные, но не подключённые в MVP
`create_jira_draft`, `create_email_draft`, `create_reminder`, `save_feedback`,
`load_release_memory`, `update_release_memory`, `get_confluence_pages` —
объявлены в allowlist (`security.ALLOWED_HITL_TOOLS`); в демо-контуре реализованы
в процессе (hitl.py, memory.py, feedback.py) с тем же контрактом. Боевые MCP-обёртки —
после пилота.
