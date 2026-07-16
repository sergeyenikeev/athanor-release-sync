"""Диспетчер движка извлечения: llm (основной) или rule (офлайн-baseline)."""

from __future__ import annotations

from . import extract, llm
from .models import ActionItem, Decision


def run_extraction(
    engine: str, cfg: dict[str, str], transcript: str, event_date: str | None
) -> tuple[list[Decision], list[ActionItem], list[str], int]:
    """Вернуть (decisions, actions, cancellations, llm_calls)."""
    # Отмены обязательств детерминированы в обоих режимах (см. extract._CANCEL_RX)
    _, _, cancellations = extract.extract_rule(transcript, event_date)

    if engine == "llm":
        decisions, actions = llm.extract_llm(cfg, transcript, event_date)
        return decisions, actions, cancellations, 1
    if engine == "rule":
        decisions, actions, cancellations = extract.extract_rule(transcript, event_date)
        return decisions, actions, cancellations, 0
    raise ValueError(f"Неизвестный движок: {engine!r} (ожидается 'llm' или 'rule')")
