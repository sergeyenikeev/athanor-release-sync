"""Оркестрация сквозного цикла: контекст → сводка → извлечение → память → HITL.

В боевом контуре этим циклом управляет навык Ouroboros (skills/release_sync);
здесь — та же последовательность как переиспользуемая функция, чтобы её могли
вызывать и навык, и офлайн-харнесс tests/run_basket.py.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from .engine import run_extraction
from .enrich import enrich_actions, enrich_decisions, extract_blockers
from .memory import ReleaseMemory
from .models import CaseInput, RunResult
from .security import scan_untrusted
from .summary import build_summary
from . import hitl

# Валидная реплика расшифровки: «Роль: текст» (используется для диагностики повреждения)
_LINE_RX = re.compile(r"^\s*(?P<role>[^:]{2,40}?)\s*:\s*(?P<text>.+)$", re.MULTILINE)


def run_case(
    case: CaseInput,
    case_id: str,
    cfg: dict[str, str],
    memory_dir: Path,
    outbox_dir: Path,
    engine: str = "rule",
    format_profile: str = "v1",
    make_hitl_drafts: bool = True,
    skill_version: str = "v1",
) -> RunResult:
    started = time.monotonic()
    warnings: list[str] = []
    security_flags: list[str] = []

    project = case.event.project if case.event else "Неизвестный проект"
    event_date = case.event.date if case.event else None
    if case.event is None:
        warnings.append("Событие синка не найдено в календаре — сводка без привязки к встрече")

    # 0) Скан недоверенных источников (письма) до любой обработки
    for m in case.mails:
        security_flags += scan_untrusted(m.subject + "\n" + m.body, f"письме {m.id} от {m.from_role}")

    # 1) Память релиза (перенос обязательств между синками)
    mem = ReleaseMemory(memory_dir, project)

    # 2) Детерминированная сводка
    summary_items = build_summary(case, memory_commitments=mem.commitments)

    # 3) Расшифровка → решения/поручения (LLM или rule-baseline)
    decisions, actions, cancellations, llm_calls = [], [], [], 0
    if case.transcript:
        security_flags += scan_untrusted(case.transcript, "расшифровке синка")
        if not case.transcript.strip():
            warnings.append(
                "Расшифровка пуста или повреждена — ожидаемый формат «Роль: текст»; "
                "извлечение пропущено, повторите загрузку"
            )
        elif not _LINE_RX.search(case.transcript):
            warnings.append(
                "Расшифровка пуста или повреждена — ожидаемый формат «Роль: текст»; "
                "извлечение пропущено, повторите загрузку"
            )
        else:
            decisions, actions, cancellations, llm_calls = run_extraction(
                engine, cfg, case.transcript, event_date
            )
    elif "transcripts" in case.sources_down:
        warnings.append("Расшифровка недоступна (источник transcripts) — этап «после встречи» пропущен")

    # 3a) Evidence linking + уверенность + структурированные блокеры
    decisions = enrich_decisions(decisions, case)
    actions = enrich_actions(actions, case, event_date or "2026-01-01")
    blockers = extract_blockers(case, summary_items, decisions)

    # 4) Обновление аудируемой памяти
    memory_updates = mem.apply_cycle(event_date or "2026-01-01", decisions, actions, cancellations)

    # 5) Черновики внешних действий — только через HITL
    drafts = []
    if make_hitl_drafts and actions:
        drafts = hitl.make_drafts(actions, outbox_dir, case_id)

    return RunResult(
        case_id=case_id,
        engine=engine,
        format_profile=format_profile,
        summary_items=summary_items,
        decisions=decisions,
        actions=actions,
        drafts=drafts,
        memory_updates=memory_updates,
        security_flags=security_flags,
        warnings=warnings,
        elapsed_seconds=time.monotonic() - started,
        blockers=blockers,
        llm_calls=llm_calls,
        skill_version=skill_version,
        # модель фиксируется только при реальных LLM-вызовах; rule-движок — пусто
        model=cfg.get("LLM_MODEL", "") if llm_calls else "",
    )
