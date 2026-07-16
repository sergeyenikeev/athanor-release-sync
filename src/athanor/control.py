"""Контрольные тесты для управляемой эволюции навыка (task2 §4 шаг 9, §6.5).

Перед promote новой версии навыка (format_profile) прогоняет контрольные сценарии
(TB-01, TB-02, TB-04) и считает F1 по поручениям —gate «нет деградации».
Используется skill_versioning.promote и CLI feedback/promote.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .agent import run_case
from .config import load_config
from .memory import _slug
from .sources import load_case_from_files

ROOT = Path(__file__).resolve().parents[2]
BASKET = ROOT / "test-basket"
CONTROL_CASES = ["TB-01", "TB-02", "TB-04"]


def _seed(case_dir: Path) -> Path:
    mem = Path(tempfile.mkdtemp(prefix="ctrl-mem-"))
    (mem / "knowledge").mkdir(parents=True, exist_ok=True)
    seed = case_dir / "input" / "memory_seed.md"
    if seed.is_file():
        first = seed.read_text(encoding="utf-8").splitlines()[0]
        if "«" in first and "»" in first:
            name = f"release_{_slug(first.split('«')[1].split('»')[0])}.md"
            shutil.copy(seed, mem / "knowledge" / name)
    return mem


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split()).strip()


def control_runner(format_profile: str, engine: str = "rule") -> dict[str, float]:
    """Прогнать контрольные сценарии с заданным format_profile; вернуть {precision,recall,f1}."""
    cfg = dict(load_config())
    cfg["ATHANOR_ENGINE"] = engine
    if engine == "llm":
        cfg["ATHANOR_LLM_MOCK"] = "1"
        cfg["LLM_API_KEY"] = cfg.get("LLM_API_KEY") or "mock"
    tp = fp = fn = 0
    for tb in CONTROL_CASES:
        case_dir = BASKET / tb
        if not case_dir.is_dir():
            continue
        meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
        case = load_case_from_files(case_dir, transcripts_down=meta.get("transcripts_down", False))
        mem = _seed(case_dir)
        out = Path(tempfile.mkdtemp(prefix="ctrl-out-"))
        res = run_case(case, tb, cfg, mem, out / "outbox", engine=engine,
                       format_profile=format_profile, make_hitl_drafts=False)
        exp = json.loads((case_dir / "expected" / "actions.json").read_text(encoding="utf-8"))
        pool = [{"action": a.action, "owner": a.owner, "due": a.due, "source": a.source} for a in res.actions]
        for e in exp:
            ev = tuple(_norm(e.get(k, "")) for k in ["action", "owner", "due", "source"])
            hit = None
            for i, a in enumerate(pool):
                if tuple(_norm(a.get(k, "")) for k in ["action", "owner", "due", "source"]) == ev:
                    hit = i
                    break
            if hit is not None:
                tp += 1
                pool.pop(hit)
            else:
                fn += 1
        fp += len(pool)
        shutil.rmtree(mem, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
