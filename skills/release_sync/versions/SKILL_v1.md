---
name: release_sync
description: >
  Подготовка к релиз-синку и обработка его итогов: сводка из календаря, трекера,
  почты и памяти релиза; извлечение решений и поручений из расшифровки; черновики
  внешних действий через Human-in-the-loop; обновление аудируемой памяти релиза.
type: script
runtime: python
entry: main.py
version: 1
timeout_sec: 300
permissions: [net, fs]
scripts:
  - name: ./main.py
---

# Навык release_sync (v1) — baseline

Это каноническая копия v1 (активная stable-версия; реестр — versions/registry.json).
Полный текст процесса и правил безопасности — в ../SKILL.md (v1 = текущий SKILL.md).

## Процесс (7 шагов)
1. Контекст: calendar_mail.get_events → встреча, проект, участники.
2. Сбор: tracker_repo.get_issues/get_prs, calendar_mail.get_mail, обязательства прошлых синков — memory/knowledge/release_<проект>.md.
3. Сводка: конфликты → блокеры → статусы → обязательства → вопросы → полнота данных. У каждого пункта (источник · уверенность).
4. Конфликты: Jira «готово» ↔ письмо «блокер» — показать оба значения, приоритет Git/Jira > переписка, эскалация в HITL.
5. После встречи: transcripts.get_transcript → решения (≠ идеи) и поручения (действие · ответственный · срок · источник).
6. HITL: черновики в outbox со статусом awaiting_approval; отправка только после подтверждения человека.
7. Память: решения (с причиной) и обязательства в memory/knowledge/release_<проект>.md; журнал — memory/journal.log.

## Откат
rollback к v1: `python -m athanor.cli rollback --to v1` (см. skill_versioning.rollback).
