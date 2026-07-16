"""Обратная связь пользователя и управляемая эволюция навыка (task2 §6.6, §4 шаг 9).

Формат feedback (models.Feedback) поддерживает:
  — оценку полезности (usefulness 1..5);
  — исправление факта / ответственного / срока;
  — изменение формата (format_change);
  — подтверждение или отклонение черновика (draft_decisions).

Хранилище: memory/feedback.jsonl (append-only, аудит). На основе обратной связи
формируется предложение по изменению навыка (format_profile) — применяет
skill_versioning.promote только после контрольных тестов без деградации.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .models import Feedback


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def save_feedback(memory_dir: Path, fb: Feedback) -> dict[str, Any]:
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / "feedback.jsonl"
    if not fb.created_at:
        fb.created_at = _now()
    record = fb.__dict__
    path.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_feedback(memory_dir: Path) -> list[dict[str, Any]]:
    path = memory_dir / "feedback.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def feedback_to_proposal(fb: Feedback) -> dict[str, Any]:
    """Преобразовать обратную связь в предложение по изменению навыка."""
    proposal: dict[str, Any] = {
        "run_id": fb.run_id,
        "usefulness": fb.usefulness,
        "reason": "",
        "format_profile": "",
    }
    if fb.format_change:
        low = fb.format_change.lower()
        if "короче" in low or "блокер" in low or "сверху" in low:
            proposal["format_profile"] = "v2"
            proposal["reason"] = f"обратная связь: {fb.format_change}"
    if fb.usefulness and fb.usefulness < 4 and not proposal["format_profile"]:
        proposal["reason"] = "низкая оценка полезности — пересмотреть формат сводки"
    return proposal


def apply_feedback_proposal(
    memory_dir: Path, proposal: dict[str, Any], control_runner
) -> dict[str, Any]:
    """Применить предложение через skill_versioning с контрольными тестами.

    control_runner(format_profile) -> dict метрик контрольных примеров {f1, ...}.
    Возвращает результат promote (см. skill_versioning.promote).
    """
    if not proposal.get("format_profile"):
        return {"applied": False, "reason": "предложение не требует новой версии навыка"}
    from .skill_versioning import promote  # локальный импорт — разрыв цикла

    return promote(
        proposal["format_profile"],
        reason=proposal["reason"],
        control_runner=control_runner,
        memory_dir=memory_dir,
    )
