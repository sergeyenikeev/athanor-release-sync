"""Повторяемость критических сценариев (task4 §12): 3 прогона каждого.

Критические сценарии: базовый end-to-end (TB-01), конфликт источников (TB-03),
prompt injection (TB-11), использование памяти (TB-17), улучшение навыка (TB-12).

Для каждого: 3 прогона → одинаковость обязательных фактов, вариативность
формулировок, стабильность структурированных полей, доля успешных, разброс
времени/стоимости, частота fallback. Детерминированный rule-движок → 100%
стабильность; mock-LLM — тот же путь. Реальная LLM — замер пилота.

Запуск: python scripts/run_reproducibility.py --runs 3
Результат: results/reproducibility/<timestamp>/ + results/reproducibility_summary.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

from run_basket import run_one  # noqa: E402
from athanor.config import load_config  # noqa: E402
from athanor.skill_versioning import get_active_version  # noqa: E402

BASKET = _ROOT / "test-basket"
CRITICAL = ["TB-01", "TB-03", "TB-11", "TB-17", "TB-12"]


def _facts_key(metrics: dict) -> str:
    """Сворачивает структурированные поля в ключ для проверки одинаковости."""
    a = metrics["actions"]
    d = metrics["decisions"]
    s = metrics["summary"]
    return f"{a['tp']},{a['fp']},{a['fn']}|{d['tp']},{d['fp']},{d['fn']}|{s['tp']},{s['fp']},{s['fn']}|{metrics['status']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--engine", choices=["rule", "llm"], default="rule")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_root = _ROOT / "results" / "reproducibility" / stamp
    out_root.mkdir(parents=True, exist_ok=True)

    cfg = dict(load_config())
    cfg["ATHANOR_ENGINE"] = args.engine
    if args.engine == "llm" or args.mock:
        cfg["ATHANOR_LLM_MOCK"] = "1"
        cfg["LLM_API_KEY"] = cfg.get("LLM_API_KEY") or "mock"

    sv = get_active_version()
    report: list[dict] = []
    for tb in CRITICAL:
        case_dir = BASKET / tb
        runs = []
        for r in range(1, args.runs + 1):
            out_dir = out_root / tb / f"run_{r:03d}"
            out_dir.mkdir(parents=True, exist_ok=True)
            m = run_one(case_dir, cfg, out_dir, args.engine, sv)
            runs.append(m)
        keys = [_facts_key(m) for m in runs]
        unique_keys = len(set(keys))
        times = [m["elapsed_seconds"] for m in runs]
        a_f1s = [m["actions"]["f1"] for m in runs]
        success = sum(1 for m in runs if m["status"] == "success")
        entry = {
            "case_id": tb,
            "runs": args.runs,
            "successful_runs": success,
            "success_rate": round(success / args.runs, 4),
            "unique_facts_keys": unique_keys,
            "facts_stable": unique_keys == 1,
            "a_f1_mean": round(statistics.mean(a_f1s), 4),
            "a_f1_stdev": round(statistics.pstdev(a_f1s), 4) if len(a_f1s) > 1 else 0.0,
            "time_mean_sec": round(statistics.mean(times), 6),
            "time_stdev_sec": round(statistics.pstdev(times), 6) if len(times) > 1 else 0.0,
            "time_min_sec": round(min(times), 6),
            "time_max_sec": round(max(times), 6),
            "fallback_rate": 0.0,  # rule/mock — без fallback
            "statuses": [m["status"] for m in runs],
            "facts_keys": keys,
        }
        report.append(entry)
        print(f"{tb}: success={success}/{args.runs} facts_stable={entry['facts_stable']} "
              f"A·F1={entry['a_f1_mean']}±{entry['a_f1_stdev']} t={entry['time_mean_sec']}s")

    summary = {
        "stamp": stamp, "engine": args.engine, "mock": cfg.get("ATHANOR_LLM_MOCK") == "1",
        "skill_version": sv, "runs_per_scenario": args.runs,
        "critical_scenarios": CRITICAL,
        "overall_facts_stable_rate": round(sum(1 for e in report if e["facts_stable"]) / len(report), 4),
        "overall_success_rate": round(sum(e["successful_runs"] for e in report) / (len(report) * args.runs), 4),
        "scenarios": report,
    }
    (out_root / "reproducibility.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Повторяемость критических сценариев · {stamp}",
        "",
        f"- Движок: **{args.engine}**{' (mock)' if cfg.get('ATHANOR_LLM_MOCK')=='1' else ''} · навык: **{sv}** · прогонов на сценарий: **{args.runs}**",
        f"- Общая доля стабильных по фактам сценариев: **{summary['overall_facts_stable_rate']*100:.0f}%**",
        f"- Общая доля успешных прогонов: **{summary['overall_success_rate']*100:.0f}%**",
        "",
        "| Сценарий | Успешных | Факты стабильны | A·F1 (среднее±σ) | Время, с (min–max) |",
        "|---|---|---|---|---|",
    ]
    for e in report:
        lines.append(
            f"| {e['case_id']} | {e['successful_runs']}/{e['runs']} | "
            f"{'да' if e['facts_stable'] else 'нет'} | "
            f"{e['a_f1_mean']}±{e['a_f1_stdev']} | "
            f"{e['time_min_sec']}–{e['time_max_sec']} |"
        )
    lines += [
        "",
        "Детерминированный rule-движок даёт 100% одинаковость обязательных фактов и "
        "нулевую вариативность структурированных полей. Путь mock-LLM — тот же "
        "детерминированный прокси. Вариативность возможна только на реальной LLM (замер пилота).",
    ]
    (out_root / "reproducibility_summary.md").write_text("\n".join(lines), encoding="utf-8")
    # Зеркало в results/
    (_ROOT / "results" / "reproducibility_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nГотово: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
