"""Сводный экспорт результатов оценки в один markdown-файл (для презентации/отчёта).

Запуск: python scripts/export_results.py [--run results/runs/<id>]
Создаёт results/exported_report.md — объединяет results_summary.md + таблицу
сценариев + блок эволюции навыка (registry history).
"""
import _bootstrap  # noqa: F401
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    args = ap.parse_args()
    run_dir = Path(args.run) if args.run else (ROOT / "results" / "runs")
    if run_dir.is_dir() and not (run_dir / "manifest.json").is_file():
        dirs = sorted(d for d in run_dir.iterdir() if d.is_dir() and (d / "manifest.json").is_file())
        run_dir = dirs[-1] if dirs else run_dir
    if not (run_dir / "manifest.json").is_file():
        print(f"Прогон не найден: {run_dir}")
        return 2
    summary = (run_dir / "results_summary.md").read_text(encoding="utf-8") if (run_dir / "results_summary.md").is_file() else ""
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    reg_path = ROOT / "skills" / "release_sync" / "versions" / "registry.json"
    registry = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.is_file() else {}

    parts = [f"# Экспортированный отчёт · прогон {manifest['run_id']}", "", summary, "",
             "## Реестр версий навыка", ""]
    for v in registry.get("versions", {}).values():
        parts.append(f"- **{v['version']}** — статус: {v['status']}, формат: {v['format_profile']}, причина: {v['reason']}")
    parts += ["", "## История изменений навыка", ""]
    for h in registry.get("history", []):
        parts.append(f"- {h.get('at')}: {h.get('action')} {h.get('version','')} — {h.get('reason','')}")
    out = ROOT / "results" / "exported_report.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Экспортировано: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
