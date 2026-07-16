"""Модели данных прототипа. Обезличенная синтетика: роли вместо имён."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Единые константы формулировок (одинаковы во всех материалах комплекта)
DUE_NOT_SET = "не указан"
OWNER_NOT_SET = "не определён"

# Детерминированная карта уверенности по типу источника
CONFIDENCE = {
    "jira": 0.9,
    "git": 0.9,
    "mail": 0.7,
    "transcript": 0.6,
    "memory": 0.8,
}


@dataclass
class CalendarEvent:
    id: str
    title: str
    project: str
    datetime: str  # ISO, напр. 2026-07-03T14:00
    participants: list[str] = field(default_factory=list)

    @property
    def date(self) -> str:
        return self.datetime.split("T", 1)[0]


@dataclass
class Issue:
    key: str
    title: str
    status: str
    assignee_role: str = OWNER_NOT_SET


@dataclass
class PullRequest:
    number: int
    title: str
    status: str
    review_days: int = 0
    issue_key: str = ""


@dataclass
class Mail:
    id: str
    from_role: str
    date: str
    subject: str
    body: str


@dataclass
class SummaryItem:
    """Пункт сводки: текст + источник + уверенность (требование Proposal)."""

    text: str
    source: str
    confidence: float
    kind: str = "status"  # status | blocker | conflict | question | commitment | warning


@dataclass
class Decision:
    text: str
    reason: str = ""
    source: str = ""
    confidence: float = 0.0  # 0.0 — не оценена; enrich.py выставляет по источнику
    source_evidence: str = ""  # ссылка на Evidence.id (опц.)

    def as_line(self) -> str:
        return f"- {self.text} · причина: {self.reason or '—'} · источник: {self.source or DUE_NOT_SET}"


@dataclass
class ActionItem:
    action: str
    owner: str = OWNER_NOT_SET
    due: str = DUE_NOT_SET
    source: str = ""
    id: str = ""  # C-001… (присваивается enrich.py)
    confidence: float = 0.0
    source_evidence: str = ""  # ссылка на Evidence.id (опц.)
    created_at: str = ""
    updated_at: str = ""

    def as_line(self) -> str:
        return f"→ {self.owner}: {self.action} · срок {self.due} · источник {self.source or DUE_NOT_SET}"


@dataclass
class Evidence:
    """Доказательство утверждения: откуда взят факт (требование Proposal §7)."""
    source_type: str  # jira | git | mail | transcript | memory | confluence | calendar
    source_id: str
    source_title: str
    timestamp: str = ""
    excerpt: str = ""
    confidence: float = 0.0
    url: str = ""
    local_path: str = ""

    def as_ref(self) -> str:
        return f"evidence:{self.source_type}:{self.source_id}"


@dataclass
class Blocker:
    """Структурированный блокер (из summary.py / писем / расшифровок)."""
    id: str
    description: str
    severity: str = "medium"  # low | medium | high
    owner: str = OWNER_NOT_SET
    affected_release: str = ""
    source_evidence: str = ""
    confidence: float = 0.0
    detected_at: str = ""
    resolution_status: str = "open"  # open | confirmed | resolved


@dataclass
class DraftAction:
    """Черновик внешнего действия (HITL). Преобразуется в outbox/*.json."""
    id: str
    kind: str  # mail_draft | jira_draft | reminder | memory_update
    to_role: str
    subject: str
    body: str
    status: str = "proposed"  # proposed|awaiting_approval|approved|rejected|executed|failed
    source_evidence: str = ""
    created_at: str = ""


@dataclass
class Feedback:
    """Обратная связь пользователя по итогам прогона (для управляемой эволюции)."""
    run_id: str
    usefulness: int = 0  # 1..5
    fact_corrections: list[str] = field(default_factory=list)  # исправление факта
    owner_corrections: list[str] = field(default_factory=list)
    due_corrections: list[str] = field(default_factory=list)
    format_change: str = ""  # напр. «короче, блокеры сверху»
    draft_decisions: list[str] = field(default_factory=list)  # draft_id -> approved|rejected|edited
    comment: str = ""
    created_at: str = ""


@dataclass
class SkillVersion:
    """Версия навыка (реестр skills/release_sync/versions/registry.json)."""
    version: str  # v1, v2…
    status: str = "candidate"  # candidate | stable | rejected
    reason: str = ""  # причина изменения
    format_profile: str = "v1"
    test_results: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    promoted_at: str = ""


@dataclass
class CaseInput:
    """Входные данные одного прогона (выгрузки демо-контура)."""

    event: CalendarEvent | None
    issues: list[Issue]
    prs: list[PullRequest]
    mails: list[Mail]
    transcript: str | None
    sources_down: list[str] = field(default_factory=list)  # напр. ["transcripts"]
    release_windows: list[str] = field(default_factory=list)  # даты релизных окон (ISO) — для разрешения относительных сроков


@dataclass
class Project:
    """Проект (обезличенный): ключ и команда ролей."""
    key: str
    name: str
    release_window: str = ""
    team_roles: list[str] = field(default_factory=list)


@dataclass
class Meeting:
    """Встреча (релиз-синк / разбор инцидента)."""
    id: str
    title: str
    project: str
    datetime: str
    participants: list[str] = field(default_factory=list)
    kind: str = "release_sync"  # release_sync | incident_review


@dataclass
class Release:
    """Релиз проекта."""
    project: str
    target_date: str
    window: str = ""
    status: str = "planned"  # planned | at_risk | released | postponed


@dataclass
class RunResult:
    """Результат сквозного прогона — сериализуется в results/runs/TB-XX/run.json."""

    case_id: str
    engine: str
    format_profile: str
    summary_items: list[SummaryItem]
    decisions: list[Decision]
    actions: list[ActionItem]
    drafts: list[dict[str, Any]]
    memory_updates: list[str]
    security_flags: list[str]
    warnings: list[str]
    elapsed_seconds: float
    blockers: list[Blocker] = field(default_factory=list)
    llm_calls: int = 0
    skill_version: str = "v1"
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
