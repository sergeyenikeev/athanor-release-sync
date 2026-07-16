"""Human-in-the-loop: внешние действия существуют только как черновики.

Агент никогда не отправляет письма и не создаёт задачи сам. Каждый черновик
кладётся в outbox/ со статусом awaiting_approval; человек подтверждает командой
`python -m athanor.cli approve --draft outbox/<file>.json`
(в демо-контуре «отправка» = смена статуса; боевой коннектор — после пилота).

Статусы действия (task2 §9):
  proposed → awaiting_approval → approved → executed
                           └→ rejected
                           └→ failed
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .models import ActionItem

# Канонические статусы
PROPOSED = "proposed"
AWAITING = "awaiting_approval"
APPROVED = "approved"
REJECTED = "rejected"
EXECUTED = "executed"
FAILED = "failed"

# Совместимость со старым именем статуса (ранние прогоны)
_LEGACY_AWAITING = "awaiting_confirmation"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _draft_from_action(a: ActionItem, draft_id: str) -> dict[str, Any]:
    return {
        "id": draft_id,
        "type": "mail_draft",
        "to_role": a.owner,
        "subject": f"[{a.source}] {a.action}",
        "body": (
            f"Коллега ({a.owner}), по итогам релиз-синка за вами: {a.action}. "
            f"Срок: {a.due}. Источник: {a.source}.\n"
            "— черновик подготовлен агентом, отправка только после подтверждения человека"
        ),
        "status": AWAITING,
        "source_evidence": a.source_evidence or a.source,
        "created_at": _now(),
    }


def make_drafts(actions: list[ActionItem], outbox: Path, case_id: str) -> list[dict[str, Any]]:
    outbox.mkdir(parents=True, exist_ok=True)
    drafts: list[dict[str, Any]] = []
    for i, a in enumerate(actions, 1):
        draft = _draft_from_action(a, f"{case_id}-D{i:02d}")
        path = outbox / f"{draft['id']}.json"
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        drafts.append(draft)
    return drafts


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, draft: dict[str, Any]) -> None:
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")


def _assert_awaiting(draft: dict[str, Any], name: str) -> None:
    status = draft.get("status")
    if status not in {AWAITING, _LEGACY_AWAITING}:
        raise ValueError(f"Черновик {name} в статусе {status!r} — действие уже обработано")


def approve_draft(path: Path) -> dict[str, Any]:
    draft = _load(path)
    _assert_awaiting(draft, path.name)
    draft["status"] = APPROVED
    draft["approved_at"] = _now()
    _save(path, draft)
    return draft


def reject_draft(path: Path, reason: str = "") -> dict[str, Any]:
    draft = _load(path)
    _assert_awaiting(draft, path.name)
    draft["status"] = REJECTED
    draft["rejected_at"] = _now()
    if reason:
        draft["reject_reason"] = reason
    _save(path, draft)
    return draft


def edit_draft(path: Path, patch: dict[str, Any]) -> dict[str, Any]:
    draft = _load(path)
    _assert_awaiting(draft, path.name)
    for k, v in patch.items():
        if k in {"subject", "body", "to_role", "due"}:
            draft[k] = v
    draft["edited_at"] = _now()
    _save(path, draft)
    return draft


def comment_draft(path: Path, comment: str) -> dict[str, Any]:
    draft = _load(path)
    draft.setdefault("comments", []).append({"at": _now(), "text": comment})
    _save(path, draft)
    return draft


def execute_draft(path: Path) -> dict[str, Any]:
    """Имитация отправки в демо-контуре: approved → executed. Без approved — отказ."""
    draft = _load(path)
    if draft.get("status") != APPROVED:
        draft["status"] = FAILED
        draft["fail_reason"] = f"попытка исполнения без подтверждения (статус {draft.get('status')!r})"
        _save(path, draft)
        return draft
    draft["status"] = EXECUTED
    draft["executed_at"] = _now()
    _save(path, draft)
    return draft
