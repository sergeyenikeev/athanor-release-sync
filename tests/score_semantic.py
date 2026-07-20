"""Семантический скоринг live LLM-прогона поверх сохранённых выходов (без повторного прогона).

Строгое посимвольное сопоставление в run_basket.py::_match занижает метрики LLM:
парафразы («подготовить» vs «подготовлю») и эквивалентные источники («расшифровка
синка» vs ID задачи, где факт обсуждался) считаются ошибками. Этот скрипт считает
semantic P/R/F1 через LLM-judge: для каждой пары (extracted, expected) поручения/
решения/блокера judge отвечает строго JSON {"match": true/false, "reason": "..."}.

Judge-модель — НЕ та же, что оценивалась (по умолчанию openai/gpt-4o-mini через
тот же шлюз, temperature=0). Каждый вердикт сохраняется в
<run>/semantic_judge/<pass_id>/ — аудируемость. Матчинг: жадное паросочетание по
матрице вердиктов (expected по порядку → первый свободный extracted с match=true).

Запуск (два прохода для проверки стабильности, затем сравнение):
  python tests/score_semantic.py --run results/runs/eval_glm52_20260720 --pass-id pass1
  python tests/score_semantic.py --run results/runs/eval_glm52_20260720 --pass-id pass2
  python tests/score_semantic.py --run results/runs/eval_glm52_20260720 --compare pass1 pass2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from athanor.config import load_config  # noqa: E402
from athanor.llm import LlmError, _chat, _parse_json_reply, set_cost_log_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASKET = ROOT / "test-basket"

# Цены OpenRouter для judge-модели, USD за 1M токенов (для оценки стоимости).
DEFAULT_PRICE_IN_PER_1M = 0.15   # openai/gpt-4o-mini prompt
DEFAULT_PRICE_OUT_PER_1M = 0.60  # openai/gpt-4o-mini completion

_SENTINELS = {"не определён", "не указан", "", "-", "—"}

JUDGE_SYSTEM = """Ты — строгий и беспристрастный судья качества извлечения фактов из расшифровок
рабочих встреч (релиз-синков). Тебе дают ДВА объекта одного типа: A — извлечённый агентом,
B — эталонный. Реши, описывают ли они ОДИН И ТОТ ЖЕ факт.

Рубрика (все применимые условия должны выполняться):
1. Действие/решение/блокер совпадает ПО СМЫСЛУ: парафраза, смена лица или вида глагола
   («подготовить» vs «подготовлю»), перестановка слов — это ОДНО И ТО ЖЕ. Другая задача,
   другой объект или другой смысл — РАЗНОЕ.
2. Владелец (owner) совпадает по роли (регистр/форма не важны). «не определён» с обеих
   сторон — совпадение; «не определён» только с одной стороны — расхождение.
3. Срок (due) совпадает по дате. «не указан» с обеих сторон — совпадение; дата только
   с одной стороны — расхождение.
4. Источник (source) совпадает, если оба указывают на один и тот же факт: ID задачи
   (например «APP-412») и расшифровка встречи, где эта задача обсуждалась, — ОДИН
   источник. Разные задачи/документы — разные источники.
Поля, отсутствующие у обоих объектов, не учитывай.

Ответ — СТРОГО один JSON-объект без пояснений вокруг:
{"match": true/false, "reason": "краткое обоснование на русском"}"""


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def _entity_fields(entity: str, obj: dict) -> dict:
    """Обрезает объект до полей, участвующих в сопоставлении (как в strict-матчинге)."""
    if entity == "actions":
        keys = ["action", "owner", "due", "source"]
    elif entity == "decisions":
        keys = ["text", "source"]
    else:  # blockers
        keys = ["description"]
    return {k: str(obj.get(k, "") or "") for k in keys}


def _judge_pair(cfg: dict[str, str], entity: str, extracted: dict, expected: dict) -> tuple[dict, dict]:
    """Один вызов judge. Возвращает (вердикт {"match","reason"}, usage)."""
    label = {"actions": "поручение", "decisions": "решение", "blockers": "блокер"}[entity]
    user = (
        f"Тип объекта: {label}.\n"
        f"A (извлечено агентом): {json.dumps(extracted, ensure_ascii=False)}\n"
        f"B (эталон): {json.dumps(expected, ensure_ascii=False)}\n"
        "Это один и тот же факт? Верни JSON."
    )
    messages = [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]
    last_err: Exception | None = None
    for _ in range(2):  # сетевые ретраи внутри _chat; здесь — ретрай парсинга ответа
        data = _chat(cfg, messages)
        usage = data.get("usage", {}) or {}
        try:
            verdict = _parse_json_reply(data["choices"][0]["message"]["content"])
            if not isinstance(verdict.get("match"), bool):
                raise LlmError(f"судья вернул не-bool match: {verdict!r}")
            return {"match": verdict["match"], "reason": str(verdict.get("reason", "")).strip()}, usage
        except (LlmError, KeyError, json.JSONDecodeError) as e:
            last_err = e
    raise LlmError(f"Не удалось получить валидный вердикт judge: {last_err}")


def _call_cost(usage: dict, price_in: float, price_out: float) -> float:
    if usage.get("cost") is not None:  # точная стоимость от шлюза (OpenRouter)
        return float(usage["cost"])
    p = int(usage.get("prompt_tokens", 0) or 0)
    c = int(usage.get("completion_tokens", 0) or 0)
    return p / 1e6 * price_in + c / 1e6 * price_out


def run_pass(run_dir: Path, pass_id: str, judge_model: str, budget_usd: float,
             price_in: float, price_out: float) -> dict[str, Any]:
    cfg = dict(load_config())
    if not cfg.get("LLM_API_KEY") or cfg["LLM_API_KEY"].lower() == "mock":
        raise LlmError("Нужен реальный LLM_API_KEY в .env — семантический judge не работает в mock-режиме")
    eval_model = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")).get("model", "")
    cfg["LLM_MODEL"] = judge_model
    cfg["LLM_TEMPERATURE"] = "0"
    self_grading = judge_model.split("/")[-1] == str(eval_model).split("/")[-1]

    out_dir = run_dir / "semantic_judge" / pass_id
    out_dir.mkdir(parents=True, exist_ok=True)
    set_cost_log_path(out_dir / "judge_cost.log")

    totals = {e: {"tp": 0, "fp": 0, "fn": 0} for e in ("actions", "decisions", "blockers")}
    per_case: list[dict] = []
    cost_total = 0.0
    calls = 0

    for tb_dir in sorted(d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("TB-")):
        tb = tb_dir.name
        run_json = tb_dir / "run.json"
        if not run_json.is_file():
            continue
        rj = json.loads(run_json.read_text(encoding="utf-8"))
        case_row = {"case_id": tb}
        for entity in ("actions", "decisions", "blockers"):
            extracted = [_entity_fields(entity, o) for o in rj.get(entity, [])]
            exp_file = BASKET / tb / "expected" / f"{entity}.json"
            expected = (
                [_entity_fields(entity, o) for o in json.loads(exp_file.read_text(encoding="utf-8"))]
                if exp_file.is_file() else []
            )
            # Матрица вердиктов: judge по каждой паре (extracted × expected)
            matrix: dict[tuple[int, int], bool] = {}
            for ei, exp_obj in enumerate(expected):
                for xi, ext_obj in enumerate(extracted):
                    verdict, usage = _judge_pair(cfg, entity, ext_obj, exp_obj)
                    calls += 1
                    cost = _call_cost(usage, price_in, price_out)
                    cost_total += cost
                    if cost_total > budget_usd:
                        raise LlmError(f"Превышен бюджет judge: ${cost_total:.4f} > ${budget_usd}")
                    matrix[(ei, xi)] = verdict["match"]
                    record = {
                        "case_id": tb, "entity": entity,
                        "expected_index": ei, "extracted_index": xi,
                        "extracted": ext_obj, "expected": exp_obj,
                        "match": verdict["match"], "reason": verdict["reason"],
                        "judge_model": judge_model, "temperature": 0,
                        "usage": {"prompt_tokens": usage.get("prompt_tokens"),
                                  "completion_tokens": usage.get("completion_tokens")},
                        "cost_usd": round(cost, 6),
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    (out_dir / f"{tb}_{entity}_e{ei}_x{xi}.json").write_text(
                        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
            # Жадное паросочетание: expected по порядку → первый свободный extracted с match
            used: set[int] = set()
            tp = 0
            for ei in range(len(expected)):
                for xi in range(len(extracted)):
                    if xi not in used and matrix.get((ei, xi)):
                        used.add(xi)
                        tp += 1
                        break
            fp, fn = len(extracted) - tp, len(expected) - tp
            totals[entity]["tp"] += tp
            totals[entity]["fp"] += fp
            totals[entity]["fn"] += fn
            case_row[entity] = {"tp": tp, "fp": fp, "fn": fn}
        per_case.append(case_row)
        print(f"{tb}: " + " ".join(
            f"{e[0].upper()}[{case_row[e]['tp']}/{case_row[e]['fp']}/{case_row[e]['fn']}]"
            for e in ("actions", "decisions", "blockers") if e in case_row
        ))

    strict = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    summary: dict[str, Any] = {
        "run_id": run_dir.name, "pass_id": pass_id,
        "judge_model": judge_model, "temperature": 0,
        "evaluated_model": eval_model,
        "self_grading_risk": self_grading,
        "judge_calls": calls, "cost_usd": round(cost_total, 6),
        "matching": "semantic (LLM-judge, попарные вердикты + жадное паросочетание)",
        "entities": {},
        "strict_reference": {e: strict[e] for e in ("actions", "decisions", "blockers")},
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    for entity, t in totals.items():
        p, r, f1 = _prf(t["tp"], t["fp"], t["fn"])
        summary["entities"][entity] = {
            **t, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)
        }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nСемантические метрики ({pass_id}, judge={judge_model}, {calls} вызовов, ${cost_total:.4f}):")
    for entity in ("actions", "decisions", "blockers"):
        s = summary["entities"][entity]
        st = strict[entity]
        print(f"  {entity:9s}: semantic P/R/F1 = {_pct(s['precision'])}/{_pct(s['recall'])}/{_pct(s['f1'])}"
              f"  (strict F1 = {_pct(st['f1'])})")
    if self_grading:
        print("  ВНИМАНИЕ: judge-модель совпадает с оцениваемой — риск self-grading, пометить в отчёте.")
    print(f"Вердикты: {out_dir}")
    return summary


def compare_passes(run_dir: Path, pass_a: str, pass_b: str) -> dict[str, Any]:
    """Стабильность: сравнивает вердикты двух проходов по ключу (case, entity, ei, xi)."""
    def _load(pass_id: str) -> dict[str, dict]:
        d = run_dir / "semantic_judge" / pass_id
        out = {}
        for f in sorted(d.glob("TB-*_e*_x*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            key = f"{rec['case_id']}/{rec['entity']}/e{rec['expected_index']}x{rec['extracted_index']}"
            out[key] = rec
        return out

    a, b = _load(pass_a), _load(pass_b)
    keys = sorted(set(a) | set(b))
    diffs = []
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None or va["match"] != vb["match"]:
            diffs.append({
                "pair": k,
                pass_a: None if va is None else va["match"],
                pass_b: None if vb is None else vb["match"],
                f"reason_{pass_a}": None if va is None else va["reason"],
                f"reason_{pass_b}": None if vb is None else vb["reason"],
            })
    report = {
        "run_id": run_dir.name, "passes": [pass_a, pass_b],
        "pairs_total": len(keys), "verdicts_agree": len(keys) - len(diffs),
        "verdicts_differ": len(diffs), "diffs": diffs,
        "stable": not diffs,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out = run_dir / "semantic_judge" / "stability.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Стабильность: {report['verdicts_agree']}/{report['pairs_total']} вердиктов совпали"
          f" ({'стабильно' if report['stable'] else 'ЕСТЬ РАСХОЖДЕНИЯ — см. stability.json'})")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Семантический скоринг прогона через LLM-judge")
    ap.add_argument("--run", required=True, help="папка прогона (results/runs/<run_id>)")
    ap.add_argument("--pass-id", default="pass1", help="идентификатор прохода (pass1/pass2)")
    ap.add_argument("--judge-model", default="openai/gpt-4o-mini",
                    help="judge-модель (НЕ та же, что оценивалась)")
    ap.add_argument("--budget-usd", type=float, default=1.0, help="жёсткий бюджет judge, USD")
    ap.add_argument("--price-in", type=float, default=DEFAULT_PRICE_IN_PER_1M,
                    help="цена prompt-токенов judge, USD за 1M")
    ap.add_argument("--price-out", type=float, default=DEFAULT_PRICE_OUT_PER_1M,
                    help="цена completion-токенов judge, USD за 1M")
    ap.add_argument("--compare", nargs=2, metavar=("PASS_A", "PASS_B"),
                    help="не гонять judge, а сравнить вердикты двух проходов")
    args = ap.parse_args()

    run_dir = Path(args.run)
    if not (run_dir / "manifest.json").is_file():
        print(f"Прогон не найден: {run_dir}", file=sys.stderr)
        return 2
    if args.compare:
        compare_passes(run_dir, *args.compare)
        return 0
    run_pass(run_dir, args.pass_id, args.judge_model, args.budget_usd, args.price_in, args.price_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
