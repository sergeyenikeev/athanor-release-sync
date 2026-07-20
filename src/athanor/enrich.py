"""Связывание с доказательствами (Evidence), уверенность и структурированные блокеры.

Этапы оркестрации из task2 §4: entity resolution → evidence linking → conflict detection.
Здесь: каждому решению/поручению присваивается id, уверенность (по типу источника) и
ссылка на Evidence; из сводки собираются структурированные Blocker-объекты.
"""
from __future__ import annotations

import datetime as dt
import re

from .models import (
    CONFIDENCE,
    DUE_NOT_SET,
    OWNER_NOT_SET,
    ActionItem,
    Blocker,
    CalendarEvent,
    CaseInput,
    Decision,
    Evidence,
    SummaryItem,
)

_ISSUE_KEY_RX = re.compile(r"\b([A-Z]{2,5}-\d{1,5})\b(?!\.\d)")

# Блокер, зафиксированный в решении синка («блокер по OPS-77 фиксируем, ответственный SRE»).
# Уже словами «блокер/заблокирован»: решения — очищенные формулировки, широкий почтовый
# регэксп (падает/критично/…) дал бы ложные блокеры на решениях о переносах.
_DECISION_BLOCKER_RX = re.compile(r"блокер|заблокирован", re.IGNORECASE)
_BLOCKER_OWNER_RX = re.compile(
    r"ответственн(?:ый|ая|ые)?\s*[—:-]?\s*(?P<owner>[А-ЯA-Z][\w /-]{1,30})", re.IGNORECASE
)

# Относительный срок вида «до следующего релизного окна» / «до следующего окна» —
# разрешается по календарю release_windows (task4 СЦ-06: неявный срок).
_REL_WINDOW_RX = re.compile(r"\s*до\s+следующ(?:его|ая|ему|ем)?\s+(?:релизн\w+\s+)?окн\w+", re.IGNORECASE)


def _confidence_for_source(source: str) -> float:
    s = source or ""
    if _ISSUE_KEY_RX.search(s):  # оригинальный регистр: APP-412 → 0.9
        return CONFIDENCE["jira"]
    low = s.lower()
    if low.startswith("pr") or "git" in low:
        return CONFIDENCE["git"]
    if "письмо" in low or "mail" in low:
        return CONFIDENCE["mail"]
    if "память" in low:
        return CONFIDENCE["memory"]
    if "расшифровка" in low or "синк" in low:
        return CONFIDENCE["transcript"]
    return 0.0


def _evidence_for_source(source: str, case: CaseInput) -> Evidence:
    s = source or ""
    key = _ISSUE_KEY_RX.search(s)
    if key:
        k = key.group(1)
        title = next((i.title for i in case.issues if i.key == k), k)
        return Evidence("jira", k, title, confidence=CONFIDENCE["jira"])
    if "расшифровка" in s.lower() or "синк" in s.lower():
        return Evidence("transcript", s or "расшифровка", "Расшифровка релиз-синка", confidence=CONFIDENCE["transcript"])
    if "письмо" in s.lower():
        return Evidence("mail", s, "Письмо по проекту", confidence=CONFIDENCE["mail"])
    return Evidence("unknown", s or "—", s or "Источник", confidence=0.0)


def enrich_decisions(decisions: list[Decision], case: CaseInput) -> list[Decision]:
    for i, d in enumerate(decisions, 1):
        if not d.confidence:
            d.confidence = _confidence_for_source(d.source)
        if not d.source_evidence:
            d.source_evidence = _evidence_for_source(d.source, case).as_ref()
    return decisions


def _resolve_relative_window(a: ActionItem, case: CaseInput) -> None:
    """Разрешить относительный срок «до следующего релизного окна» по календарю.

    Если в тексте действия есть фраза «до следующего … окна», а в календаре
    (case.release_windows) есть дата окна позже даты события — подставить её в
    due и убрать фразу из текста действия. Основание фиксируется в source_evidence.
    """
    if not _REL_WINDOW_RX.search(a.action):
        return
    event_date = case.event.date if case.event else ""
    windows = sorted(w for w in case.release_windows if w and (not event_date or w >= event_date))
    if not windows:
        return
    a.due = windows[0]
    a.action = _REL_WINDOW_RX.sub("", a.action).rstrip(" ,.;—-").strip()
    basis = f"основание: относительный срок «до следующего окна» → {windows[0]} (release_windows)"
    a.source_evidence = (a.source_evidence + " · " + basis) if a.source_evidence else basis


def enrich_actions(actions: list[ActionItem], case: CaseInput, run_date: str) -> list[ActionItem]:
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    for i, a in enumerate(actions, 1):
        _resolve_relative_window(a, case)
        if not a.id:
            a.id = f"C-{i:03d}"
        if not a.confidence:
            a.confidence = _confidence_for_source(a.source)
        if not a.source_evidence:
            a.source_evidence = _evidence_for_source(a.source, case).as_ref()
        if not a.created_at:
            a.created_at = stamp
        a.updated_at = stamp
    return actions


def extract_blockers(
    case: CaseInput,
    summary_items: list[SummaryItem],
    decisions: list[Decision] | None = None,
) -> list[Blocker]:
    """Структурированные блокеры: из сводки (письма/конфликты) и из решений синка.

    Блокер, зафиксированный голосом на встрече, приходит как решение
    («блокер по OPS-77 фиксируем, ответственный SRE») — он тоже попадает в
    blockers со статусом confirmed и владельцем из «ответственный X».
    """
    blockers: list[Blocker] = []
    event_date = case.event.date if case.event else ""
    for idx, it in enumerate(summary_items, 1):
        if it.kind == "blocker":
            blockers.append(
                Blocker(
                    id=f"B-{idx:03d}",
                    description=it.text,
                    severity="high",
                    affected_release=event_date,
                    source_evidence=it.source,
                    confidence=it.confidence,
                    detected_at=event_date,
                    resolution_status="open",
                )
            )
        elif it.kind == "conflict":
            blockers.append(
                Blocker(
                    id=f"B-{idx:03d}",
                    description=it.text,
                    severity="high",
                    affected_release=event_date,
                    source_evidence=it.source,
                    confidence=it.confidence,
                    detected_at=event_date,
                    resolution_status="confirmed",
                )
            )
    for d in decisions or []:
        if not _DECISION_BLOCKER_RX.search(d.text):
            continue
        om = _BLOCKER_OWNER_RX.search(d.text)
        blockers.append(
            Blocker(
                id=f"B-{len(summary_items) + len(blockers) + 1:03d}",
                description=d.text,
                severity="high",
                owner=om.group("owner").strip().rstrip(" ,.;—-") if om else OWNER_NOT_SET,
                affected_release=event_date,
                source_evidence=d.source,
                confidence=d.confidence or CONFIDENCE["transcript"],
                detected_at=event_date,
                resolution_status="confirmed",  # зафиксирован решением на синке
            )
        )
    return blockers
