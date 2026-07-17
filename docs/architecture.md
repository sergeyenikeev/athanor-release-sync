# Архитектура

«Ouroboros — мозг команды»: ИИ-агент подготовки к релиз-синкам и разборам
инцидентов. Контур MVP — реальные Jira/Bitbucket/Confluence/Google (mail+calendar)
через MCP (`MCP_BACKEND=live`); расшифровки — файлы кейса.

## Слои

```
sources (calendar/tracker/mail/transcript) → MCP-серверы (JSON-RPC/HTTP)
        ↓ load_case_from_files | load_case_via_mcp
agent.run_case (orchestration):
  0. security.scan_untrusted (письма)         ← Safety Layer
  1. memory.ReleaseMemory (load)              ← Memory layer
  2. summary.build_summary (детерминированно)  ← конфликты/блокеры/статусы
  3. engine.run_extraction (rule | llm)        ← расшифровка → решения/поручения
  3a. enrich (evidence linking + уверенность + Blocker)
  4. memory.apply_cycle (аудируемая запись + журнал)
  5. hitl.make_drafts (outbox, awaiting_approval)
        ↓ format.render_result
output.md + run.json + memory_after/ + outbox/ + metrics.json
```

## Разделение ответственности (критерий «Применение ГигаАгента»)
- **Ouroboros**: навык (SKILL.md), память (identity.md, knowledge/), MCP, Safety
  Layer, HITL, версионирование навыка, управляемая эволюция по обратной связи.
- **LLM**: только языковая часть — извлечение решений/поручений из расшифровки
  (недоверенный текст в маркерах изоляции, ответ строго JSON). Факты — коду.
- **Пакет athanor**: детерминированная сборка сводки, парсеры, MCP-клиент,
  нормализаторы, scoring, CLI. Без LLM-вызовов в сводке.

## Реальное vs демо
| Компонент | Статус | Где |
|---|---|---|
| Сводка (детерминированная) | реализовано | src/athanor/summary.py |
| Извлечение (rule-baseline) | реализовано | src/athanor/extract.py |
| Извлечение (LLM) | реализовано (OpenAI-compatible) | src/athanor/llm.py |
| Память релиза + журнал | реализовано | src/athanor/memory.py |
| HITL outbox | реализовано | src/athanor/hitl.py |
| Safety Layer (injection/allowlist/mask) | реализовано | src/athanor/security.py |
| MCP-инструменты (get_*) | live (Jira/Bitbucket/Confluence/Google) + адаптеры к тестовым инстансам | mcp/ (mcp/_backends.py) |
| Тестовые инстансы (реальные контракты Jira REST v2, Bitbucket Cloud REST 2.0, Confluence Cloud REST API v1) | реализовано (локально, `MCP_BACKEND=test`) | test-instances/ |
| Реальная Jira (Atlassian, `/rest/api/3/search/jql`) | реализовано (`MCP_BACKEND=atlassian`, live) | mcp/_backends.py, test-instances/seed_atlassian.py |
| Реальная Confluence Cloud (Atlassian, `/wiki/rest/api/content/search`, CQL) | реализовано (`MCP_BACKEND_CONFLUENCE=atlassian`, live) | mcp/_backends.py, test-instances/seed_confluence.py |
| Реальный mail + Calendar (Google, IMAP + iCal) | реализовано (`MCP_BACKEND=live`) | mcp/_backends.py, test-instances/seed_google.py |
| Версионирование навыка + rollback | реализовано | src/athanor/skill_versioning.py |
| Коннектор Confluence Cloud | реализовано (Basic auth + CQL, страницы в сводке kind=`doc`) | mcp/confluence.py + mcp/_backends.py |

## Схема (Mermaid)
```mermaid
flowchart LR
  C[Календарь] --> M[MCP-серверы]
  J[Jira/Tracker] --> M
  G[Git/PR] --> M
  ML[Почта] --> M
  T[Расшифровка] --> M
  CF[Confluence] --> M
  M -->|load_case| A[agent.run_case]
  A -->|scan| S[Safety Layer]
  A --> MEM[(memory/knowledge)]
  A --> SUM[summary: конфликты/блокеры + контекст Confluence]
  A --> EXT[extract: решения/поручения]
  EXT -->|LLM\|rule| A
  A --> H[HITL outbox]
  A --> R[output.md + run.json + metrics]
  H -->|approve| EXEC[executed (демо)]
  FB[feedback] --> SV[skill_versioning: v1↔v2 + rollback]
  TI[test-instances: Jira REST / Bitbucket / Confluence] -. MCP_BACKEND=test .-> M
  JC[Реальная Jira: APP-412/APP-521] -. MCP_BACKEND=atlassian .-> M
```
