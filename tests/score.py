"""Расчёт метрик прогона корзины и генерация артефактов оценки (task2 §12, §19).

Читает results/runs/<run_id>/manifest.json + per-scenario metrics.json, считает
агрегаты (micro precision/recall/F1 по поручениям и решениям, полноту владельцев/
сроков, точность блокеров, долю утверждений с источниками, время p50/p95, долю
успешных прогонов, fallback, ошибки, стоимость LLM) и пишет:

  metrics.json, metrics.csv, results_summary.md, evaluation_report.html

Запуск: python tests/score.py --run results/runs/<run_id>
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "actions_precision": 0.85,
    "actions_recall": 0.80,
    "actions_f1": 0.82,
    "usefulness": 4.0,
    "draft_acceptance": 0.60,
    "prep_time_sec": 180.0,
}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * q
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _micro_prf(results: list[dict], entity: str) -> tuple[float, float, float, int, int, int]:
    tp = sum(r[entity]["tp"] for r in results)
    fp = sum(r[entity]["fp"] for r in results)
    fn = sum(r[entity]["fn"] for r in results)
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, tp, fp, fn


def _read_cost(run_dir: Path) -> float:
    log = run_dir / "llm_cost.log"
    if not log.is_file():
        return 0.0
    total = 0.0
    for line in log.read_text(encoding="utf-8").splitlines():
        if "total_usd=" in line:
            try:
                total = float(line.split("total_usd=")[1].strip())
            except (ValueError, IndexError):
                pass
    return total


def compute_metrics(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    results = manifest["results"]
    n = len(results)

    a_p, a_r, a_f1, a_tp, a_fp, a_fn = _micro_prf(results, "actions")
    d_p, d_r, d_f1, d_tp, d_fp, d_fn = _micro_prf(results, "decisions")
    b_p, b_r, b_f1, b_tp, b_fp, b_fn = _micro_prf(results, "blockers")
    s_p, s_r, s_f1, s_tp, s_fp, s_fn = _micro_prf(results, "summary")

    owner_cov = sum(r["owner_coverage"] for r in results) / n if n else 0.0
    due_cov = sum(r["due_coverage"] for r in results) / n if n else 0.0
    evidence_cov = sum(r["evidence_coverage"] for r in results) / n if n else 0.0

    times = sorted(r["elapsed_seconds"] for r in results)
    success = sum(1 for r in results if r["status"] == "success")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["error"])
    llm_calls = sum(r["llm_calls"] for r in results)
    fallback = sum(1 for r in results if manifest["engine"] == "llm" and r["llm_calls"] == 0 and not r["error"])
    drafts_total = sum(r["drafts"] for r in results)
    cost = _read_cost(run_dir)

    # Принятие черновиков человеком в автопрогоне НЕ замеряется: все черновики
    # создаются в статусе awaiting_approval (HITL), решение принимает человек.
    # None = «не замерено»; фактический % принятия — замер пилота с оценщиком.
    draft_acceptance = None

    agg = {
        "run_id": manifest["run_id"], "engine": manifest["engine"], "mock": manifest["mock"],
        "skill_version": manifest["skill_version"],
        # model — только для llm-движка; в rule-прогоне LLM не вызывается (llm_calls=0)
        "model": manifest["model"] if manifest["engine"] == "llm" else None,
        "scenarios": n,
        "actions": {"precision": round(a_p, 4), "recall": round(a_r, 4), "f1": round(a_f1, 4),
                    "tp": a_tp, "fp": a_fp, "fn": a_fn},
        "decisions": {"precision": round(d_p, 4), "recall": round(d_r, 4), "f1": round(d_f1, 4),
                      "tp": d_tp, "fp": d_fp, "fn": d_fn},
        "blockers": {"precision": round(b_p, 4), "recall": round(b_r, 4), "f1": round(b_f1, 4),
                     "tp": b_tp, "fp": b_fp, "fn": b_fn},
        "summary": {"precision": round(s_p, 4), "recall": round(s_r, 4), "f1": round(s_f1, 4),
                    "tp": s_tp, "fp": s_fp, "fn": s_fn},
        "owner_coverage": round(owner_cov, 4),
        "due_coverage": round(due_cov, 4),
        "evidence_coverage": round(evidence_cov, 4),
        "timing": {
            "mean_sec": round(statistics.mean(times), 3) if times else 0.0,
            "p50_sec": round(_percentile(times, 0.5), 3),
            "p95_sec": round(_percentile(times, 0.95), 3),
            "total_sec": round(sum(times), 3),
        },
        "success_rate": round(success / n, 4) if n else 0.0,
        "partial": partial, "failed": failed, "errors": errors,
        "fallback_rate": round(fallback / n, 4) if n else 0.0,
        "llm_calls": llm_calls, "drafts_total": drafts_total,
        "draft_acceptance": draft_acceptance,
        "cost_usd": round(cost, 6),
        "targets": TARGETS,
        "target_met": {
            "actions_precision": a_p >= TARGETS["actions_precision"],
            "actions_recall": a_r >= TARGETS["actions_recall"],
            "actions_f1": a_f1 >= TARGETS["actions_f1"],
            # None = не замерено (принятие черновиков — решение человека, замер пилота)
            "draft_acceptance": None,
        },
    }
    return agg


def write_csv(agg: dict, results: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "type", "status", "A_precision", "A_recall", "A_f1",
                    "D_precision", "D_recall", "D_f1", "S_f1", "owner_cov", "due_cov",
                    "evidence_cov", "elapsed_sec", "llm_calls", "drafts", "error"])
        for r in results:
            w.writerow([
                r["case_id"], r["type"], r["status"],
                r["actions"]["precision"], r["actions"]["recall"], r["actions"]["f1"],
                r["decisions"]["precision"], r["decisions"]["recall"], r["decisions"]["f1"],
                r.get("summary", {}).get("f1", ""),
                r["owner_coverage"], r["due_coverage"], r["evidence_coverage"],
                r["elapsed_seconds"], r["llm_calls"], r["drafts"], r["error"],
            ])


def _engine_note(agg: dict) -> str:
    """Описывает движок в зависимости от engine/mock/model."""
    eng = agg["engine"]
    if eng == "rule":
        return "Метрики сняты с движка **rule** (rule-baseline, офлайн, детерминированно)."
    if agg.get("mock"):
        return "Метрики сняты с движка **llm** (mock-LLM, детерминированный прокси rule-baseline, без сети)."
    model = agg.get("model") or "—"
    return (
        f"Метрики сняты с движка **llm** (реальная LLM: `{model}`, "
        f"стоимость ${agg.get('cost_usd', 0):.4f})."
    )


def _engine_note_html(agg: dict) -> str:
    eng = agg["engine"]
    if eng == "rule":
        return "Метрики сняты с rule (rule-baseline, офлайн)."
    if agg.get("mock"):
        return "Метрики сняты с llm (mock-LLM — детерминированный прокси rule-baseline)."
    model = _esc(agg.get("model") or "—")
    return f"Метрики сняты с llm (реальная LLM: <code>{model}</code>)."


def write_summary_md(agg: dict, results: list[dict], path: Path) -> None:
    a, d, b = agg["actions"], agg["decisions"], agg["blockers"]
    t = agg["timing"]
    lines = [
        f"# Сводка результатов прогона {agg['run_id']}",
        "",
        f"- Движок: **{agg['engine']}**{' (mock)' if agg['mock'] else ''} · навык: **{agg['skill_version']}** · модель: `{agg['model'] or '— (rule, LLM не вызывалась)'}`",
        f"- Сценариев: **{agg['scenarios']}** · успешных: **{int(agg['success_rate']*agg['scenarios'])}** · частичных: {agg['partial']} · неуспешных: {agg['failed']} · ошибок: {agg['errors']}",
        "",
        "## Метрики (micro по корзине)",
        "",
        "| Метрика | Значение | Цель | Статус |",
        "|---|---|---|---|",
        f"| Поручения precision | {_pct(a['precision'])} | ≥85% | {'✅' if a['precision']>=0.85 else '❌'} |",
        f"| Поручения recall | {_pct(a['recall'])} | ≥80% | {'✅' if a['recall']>=0.80 else '❌'} |",
        f"| Поручения F1 | {_pct(a['f1'])} | ≥82% | {'✅' if a['f1']>=0.82 else '❌'} |",
        f"| Решения precision | {_pct(d['precision'])} | — | — |",
        f"| Решения recall | {_pct(d['recall'])} | — | — |",
        f"| Решения F1 | {_pct(d['f1'])} | — | — |",
        f"| Блокеры F1 | {_pct(b['f1'])} | — | — |",
        f"| Сводка F1 | {_pct(agg['summary']['f1'])} | — | — |",
        f"| Полнота владельцев | {_pct(agg['owner_coverage'])} | — | — |",
        f"| Полнота сроков | {_pct(agg['due_coverage'])} | — | — |",
        f"| Доля утверждений с источниками | {_pct(agg['evidence_coverage'])} | — | — |",
        f"| Принятые черновики | не замерено ({agg['drafts_total']} сформировано, awaiting_approval) | ≥60% | 📅 пилот |",
        f"| Среднее время | {t['mean_sec']} с | ≤180 с | {'✅' if t['mean_sec']<=180 else '❌'} |",
        f"| p50 / p95 | {t['p50_sec']} / {t['p95_sec']} с | — | — |",
        f"| Доля успешных прогонов | {_pct(agg['success_rate'])} | — | — |",
        f"| Доля прогонов с fallback | {_pct(agg['fallback_rate'])} | — | — |",
        f"| Стоимость LLM | ${agg['cost_usd']:.4f} | — | — |",
        "",
        "## По сценариям",
        "",
        "| ID | Тип | Статус | A·P/R/F1 | D·F1 | S·F1 | Время |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        a_r = r["actions"]
        d_r = r["decisions"]
        s_r = r.get("summary", {})
        lines.append(
            f"| {r['case_id']} | {r['type']} | {r['status']} | "
            f"{_pct(a_r['precision'])}/{_pct(a_r['recall'])}/{_pct(a_r['f1'])} | "
            f"{_pct(d_r['f1'])} | {_pct(s_r.get('f1', 0))} | {r['elapsed_seconds']:.2f} с |"
        )
    lines += [
        "",
        "## Примечание о движке",
        "",
        _engine_note(agg),
        "Корзина синтетическая и выровнена с детерминированным извлечением — доказывает работу конвейера, "
        "Safety Layer, памяти, HITL и версионирования навыка; recall на реальных расшифровках — замер пилота. "
        "Строгое текстовое сопоставление занижает метрики LLM при парафразе (например, «подготовить» vs «подготовлю»); "
        "семантически корректные извлечения засчитываются только при точном совпадении.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _esc(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_html(agg: dict, results: list[dict], path: Path) -> None:
    a, d, b = agg["actions"], agg["decisions"], agg["blockers"]
    t = agg["timing"]
    rows = ""
    for r in results:
        ar, dr = r["actions"], r["decisions"]
        sr = r.get("summary", {})
        rows += (
            f"<tr><td>{r['case_id']}</td><td>{_esc(r['type'])}</td><td>{r['status']}</td>"
            f"<td>{_pct(ar['precision'])}/{_pct(ar['recall'])}/{_pct(ar['f1'])}</td>"
            f"<td>{_pct(dr['f1'])}</td><td>{_pct(sr.get('f1', 0))}</td>"
            f"<td>{r['elapsed_seconds']:.2f}</td>"
            f"<td>{r['llm_calls']}</td><td>{r['drafts']}</td><td>{_esc(r['error'])}</td></tr>"
        )
    met = (
        f"<tr><td>Поручения precision</td><td>{_pct(a['precision'])}</td><td>≥85%</td><td>{'✅' if a['precision']>=0.85 else '❌'}</td></tr>"
        f"<tr><td>Поручения recall</td><td>{_pct(a['recall'])}</td><td>≥80%</td><td>{'✅' if a['recall']>=0.80 else '❌'}</td></tr>"
        f"<tr><td>Поручения F1</td><td>{_pct(a['f1'])}</td><td>≥82%</td><td>{'✅' if a['f1']>=0.82 else '❌'}</td></tr>"
        f"<tr><td>Решения F1</td><td>{_pct(d['f1'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Блокеры F1</td><td>{_pct(b['f1'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Сводка F1</td><td>{_pct(agg['summary']['f1'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Полнота владельцев</td><td>{_pct(agg['owner_coverage'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Полнота сроков</td><td>{_pct(agg['due_coverage'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Доля с источниками</td><td>{_pct(agg['evidence_coverage'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Принятые черновики</td><td>не замерено ({agg['drafts_total']} сформировано, awaiting_approval)</td><td>≥60%</td><td>📅 пилот</td></tr>"
        f"<tr><td>Среднее время</td><td>{t['mean_sec']} с</td><td>≤180 с</td><td>{'✅' if t['mean_sec']<=180 else '❌'}</td></tr>"
        f"<tr><td>p50 / p95</td><td>{t['p50_sec']} / {t['p95_sec']} с</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Успешных прогонов</td><td>{_pct(agg['success_rate'])}</td><td>—</td><td>—</td></tr>"
        f"<tr><td>Стоимость LLM</td><td>${agg['cost_usd']:.4f}</td><td>—</td><td>—</td></tr>"
    )
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Отчёт оценки · {agg['run_id']}</title>
<style>
body{{font-family:Inter,Arial,sans-serif;margin:2rem;color:#1a1a2e;max-width:1100px}}
h1{{color:#1A56FF}}h2{{color:#12B2A6;border-left:4px solid #12B2A6;padding-left:.5rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;font-size:.9rem}}
th{{background:#f0f4ff}}tr:nth-child(even){{background:#fafafa}}
.ok{{color:#0a7}}.bad{{color:#c33}}.muted{{color:#666}}
</style></head><body>
<h1>Отчёт оценки · прогон {agg['run_id']}</h1>
<p class="muted">Движок: <b>{agg['engine']}</b>{' (mock)' if agg['mock'] else ''} · навык: <b>{agg['skill_version']}</b> · модель: <code>{_esc(agg['model'] or '— (rule, LLM не вызывалась)')}</code><br>
Сценариев: <b>{agg['scenarios']}</b> · успешных: {int(agg['success_rate']*agg['scenarios'])} · частичных: {agg['partial']} · неуспешных: {agg['failed']} · ошибок: {agg['errors']}</p>
<h2>Агрегированные метрики</h2>
<table><tr><th>Метрика</th><th>Значение</th><th>Цель</th><th>Статус</th></tr>{met}</table>
<h2>По сценариям</h2>
    <table><tr><th>ID</th><th>Тип</th><th>Статус</th><th>A·P/R/F1</th><th>D·F1</th><th>S·F1</th><th>Время, с</th><th>LLM</th><th>Черновики</th><th>Ошибка</th></tr>{rows}</table>
<p class="muted">{_engine_note_html(agg)}
Метрики реальной LLM требуют API-ключа. Корзина синтетическая, доказывает работу конвейера, Safety Layer, памяти, HITL и версионирования.</p>
</body></html>"""
    path.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Расчёт метрик и артефакты оценки")
    ap.add_argument("--run", default=None, help="папка прогона (results/runs/<run_id>)")
    ap.add_argument("--mirror", action="store_true", help="дополнительно скопировать артефакты в results/")
    args = ap.parse_args()
    run_dir = Path(args.run) if args.run else _latest_run()
    if not run_dir.is_dir() or not (run_dir / "manifest.json").is_file():
        print(f"Прогон не найден: {run_dir}", file=sys.stderr)
        return 2
    agg = compute_metrics(run_dir)
    results = agg_full_results(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(agg, results, run_dir / "metrics.csv")
    write_summary_md(agg, results, run_dir / "results_summary.md")
    write_html(agg, results, run_dir / "evaluation_report.html")
    if args.mirror:
        dest = ROOT / "results"
        dest.mkdir(parents=True, exist_ok=True)
        for fn in ["metrics.json", "metrics.csv", "results_summary.md", "evaluation_report.html"]:
            (dest / fn).write_text((run_dir / fn).read_text(encoding="utf-8"), encoding="utf-8")
    a = agg["actions"]
    print(f"Метрики: A·P/R/F1={_pct(a['precision'])}/{_pct(a['recall'])}/{_pct(a['f1'])} "
          f"· D·F1={_pct(agg['decisions']['f1'])} · успех={_pct(agg['success_rate'])} "
          f"· среднее={agg['timing']['mean_sec']}с")
    print(f"Артефакты: {run_dir}/metrics.{{json,csv}}, results_summary.md, evaluation_report.html")
    return 0


def agg_full_results(run_dir: Path) -> list[dict]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return manifest["results"]


def _latest_run() -> Path:
    runs = ROOT / "results" / "runs"
    if not runs.is_dir():
        return runs
    dirs = sorted(d for d in runs.iterdir() if d.is_dir())
    return dirs[-1] if dirs else runs


if __name__ == "__main__":
    raise SystemExit(main())
