# Архитектура

«Ouroboros — мозг команды»: ИИ-агент подготовки к релиз-синкам и разборам
инцидентов. Демонстрационный контур — обезличенные синтетические выгрузки;
боевые коннекторы (Outlook/Jira/Git/Confluence) — тот же интерфейс через MCP,
после пилота.

## Слои

```
sources (calendar/tracker/mail/transcript) → MCP stubs (JSON-RPC/HTTP)
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
| MCP-инструменты (get_*) | демо-адаптеры (тот же интерфейс) | mcp/ |
| Версионирование навыка + rollback | реализовано | src/athanor/skill_versioning.py |
| Коннекторы Outlook/Jira/Git/Confluence | подготовлен интерфейс, боевые — после пилота | mcp/ + src/athanor/sources.py |

## Схема (Mermaid)
```mermaid
flowchart LR
  C[Календарь] --> M[MCP stubs]
  J[Jira/Tracker] --> M
  G[Git/PR] --> M
  ML[Почта] --> M
  T[Расшифровка] --> M
  M -->|load_case| A[agent.run_case]
  A -->|scan| S[Safety Layer]
  A --> MEM[(memory/knowledge)]
  A --> SUM[summary: конфликты/блокеры]
  A --> EXT[extract: решения/поручения]
  EXT -->|LLM\|rule| A
  A --> H[HITL outbox]
  A --> R[output.md + run.json + metrics]
  H -->|approve| EXEC[executed (демо)]
  FB[feedback] --> SV[skill_versioning: v1↔v2 + rollback]
```
