"""Версионирование навыка release_sync (task2 §6.5, §4 шаг 9).

Реестр: skills/release_sync/versions/registry.json.
  { "active": "v1",
    "versions": { "v1": {…SkillVersion…}, "v2": {…} } }

promote(candidate): запускает контрольные тесты (control_runner) для candidate и
текущей активной версии; применяет кандидат к stable только при отсутствии
деградации F1. rollback(to): откат к стабильной версии. Каждое изменение
записывается в history (причина, метрики до/после).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable

from .models import SkillVersion

REGISTRY = Path(__file__).resolve().parents[2] / "skills" / "release_sync" / "versions" / "registry.json"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def load_registry(path: Path | None = None) -> dict[str, Any]:
    path = path or REGISTRY
    if not path.is_file():
        return {"active": "v1", "versions": {}, "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(reg: dict[str, Any], path: Path | None = None) -> None:
    path = path or REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def list_versions(path: Path | None = None) -> list[dict[str, Any]]:
    reg = load_registry(path)
    return list(reg.get("versions", {}).values())


def get_active_version(path: Path | None = None) -> str:
    return load_registry(path).get("active", "v1")


def _record(reg: dict[str, Any], entry: dict[str, Any]) -> None:
    reg.setdefault("history", []).append({**entry, "at": _now()})


def record_candidate(
    version: str,
    reason: str,
    format_profile: str,
    test_results: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    reg = load_registry(path)
    sv = SkillVersion(
        version=version,
        status="candidate",
        reason=reason,
        format_profile=format_profile,
        test_results=test_results or {},
        created_at=_now(),
    )
    reg.setdefault("versions", {})[version] = sv.__dict__
    _record(reg, {"action": "candidate", "version": version, "reason": reason})
    save_registry(reg, path)
    return sv.__dict__


def promote(
    version: str,
    reason: str = "",
    control_runner: Callable[[str], dict[str, float]] | None = None,
    memory_dir: Path | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Применить версию к stable после контрольных тестов без деградации.

    control_runner(format_profile) -> {"f1": float, …}. Если None — тест-гейт
    пропускается (только для начального засева; в реальном цикле передаётся харнесс).
    """
    reg = load_registry(path)
    versions = reg.setdefault("versions", {})
    if version not in versions:
        return {"applied": False, "reason": f"версия {version!r} не найдена в реестре"}
    candidate = versions[version]
    active = reg.get("active", "v1")
    active_profile = versions.get(active, {}).get("format_profile", "v1")

    if control_runner is None:
        candidate["status"] = "stable"
        candidate["promoted_at"] = _now()
        candidate["reason"] = reason or candidate.get("reason", "")
        reg["active"] = version
        _record(reg, {"action": "promote", "version": version, "reason": reason, "tests": "skipped"})
        save_registry(reg, path)
        return {"applied": True, "active": version, "tests": "skipped"}

    base_metrics = control_runner(active_profile)
    cand_metrics = control_runner(candidate.get("format_profile", version))
    candidate["test_results"] = {"baseline": base_metrics, "candidate": cand_metrics}
    no_degradation = cand_metrics.get("f1", 0.0) >= base_metrics.get("f1", 0.0)

    if no_degradation:
        candidate["status"] = "stable"
        candidate["promoted_at"] = _now()
        candidate["reason"] = reason or candidate.get("reason", "")
        if active in versions and versions[active].get("status") == "stable":
            versions[active]["status"] = "superseded"
        reg["active"] = version
        _record(
            reg,
            {"action": "promote", "version": version, "reason": reason,
             "baseline_f1": base_metrics.get("f1"), "candidate_f1": cand_metrics.get("f1")},
        )
        save_registry(reg, path)
        return {"applied": True, "active": version, "baseline_f1": base_metrics.get("f1"),
                "candidate_f1": cand_metrics.get("f1")}
    candidate["status"] = "rejected"
    _record(
        reg,
        {"action": "reject", "version": version, "reason": "деградация F1",
         "baseline_f1": base_metrics.get("f1"), "candidate_f1": cand_metrics.get("f1")},
    )
    save_registry(reg, path)
    return {"applied": False, "reason": "деградация F1",
            "baseline_f1": base_metrics.get("f1"), "candidate_f1": cand_metrics.get("f1")}


def rollback(to_version: str, path: Path | None = None) -> dict[str, Any]:
    """Откат к стабильной версии. Откатываемая (бывшая активная) → candidate."""
    reg = load_registry(path)
    versions = reg.get("versions", {})
    if to_version not in versions:
        return {"applied": False, "reason": f"версия {to_version!r} не найдена"}
    if versions[to_version].get("status") not in {"stable", "superseded"}:
        return {"applied": False, "reason": "откат возможен только к stable-версии"}
    prev = reg.get("active", "v1")
    versions[to_version]["status"] = "stable"
    reg["active"] = to_version
    if prev in versions and prev != to_version and versions[prev].get("status") == "stable":
        versions[prev]["status"] = "candidate"  # откатываемая версия теряет stable
    _record(reg, {"action": "rollback", "from": prev, "to": to_version})
    save_registry(reg, path)
    return {"applied": True, "active": to_version, "rolled_back_from": prev}
