"""LLM-движок: разбор расшифровки через OpenAI-совместимый API (urllib).

Используется ТОЛЬКО для языковой части — извлечения решений/поручений из
недоверенного текста. Текст оборачивается маркерами изоляции (security.py),
ответ принимается строго как JSON. Ретраи с экспоненциальной паузой.

Возможности (task2 §8):
  — провайдер: OpenRouter / OpenAI-compatible / локальная модель (LOCAL_LLM_BASE_URL);
  — mock-режим (LLM_API_KEY=mock) для офлайн-тестов без сети и ключей;
  — промпт хранится отдельно (skills/release_sync/prompts/extract.md);
  — таймаут, retries с backoff, бюджет (LLM_BUDGET_USD), логирование стоимости;
  — fallback: при ошибке LLM — детерминированный rule-baseline (graceful degradation).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .models import DUE_NOT_SET, OWNER_NOT_SET, ActionItem, Decision
from .security import wrap_untrusted

_PROMPT_FILE = Path(__file__).resolve().parents[2] / "skills" / "release_sync" / "prompts" / "extract.md"
_COST_LOG = None  # задаётся через set_cost_log_path при запуске харнесса
_COST_TOTAL: dict[str, float] = {"usd": 0.0, "calls": 0}

_FALLBACK_PROMPT = """Ты — компонент извлечения фактов агента релиз-координации (команда «Атанор»).
Твоя единственная задача: из расшифровки рабочей встречи выделить УТВЕРЖДЁННЫЕ решения
и поручения. Ответ — СТРОГО один JSON-объект:
{"decisions":[{"text":"...","reason":"...","source":"..."}],
 "actions":[{"action":"...","owner":"...","due":"...","source":"..."}]}"""


def set_cost_log_path(path: Path) -> None:
    global _COST_LOG
    _COST_LOG = path


def _load_system_prompt() -> str:
    try:
        text = _PROMPT_FILE.read_text(encoding="utf-8")
        marker = "## Системный промпт"
        if marker in text:
            body = text.split(marker, 1)[1].strip()
            return body
    except OSError:
        pass
    return _FALLBACK_PROMPT


class LlmError(RuntimeError):
    pass


def _is_mock(cfg: dict[str, str]) -> bool:
    return cfg.get("LLM_API_KEY", "").lower() == "mock" or cfg.get("ATHANOR_LLM_MOCK") == "1"


def _mock_extract(cfg: dict[str, str], transcript: str, event_date: str | None):
    """Детерминированный mock: имитирует корректный LLM-ответ через rule-baseline.
    Позволяет прогонять путь LLM-движка (JSON-валидация, пломбирование) без сети/ключа."""
    from . import extract  # локальный импорт — разрыв цикла

    decisions, actions, _cancellations = extract.extract_rule(transcript, event_date)
    data = {
        "decisions": [{"text": d.text, "reason": d.reason, "source": d.source} for d in decisions],
        "actions": [{"action": a.action, "owner": a.owner, "due": a.due, "source": a.source} for a in actions],
    }
    _log_cost(cfg, calls=1, usd=0.0, mock=True)
    return data


def _log_cost(cfg: dict[str, str], *, calls: int, usd: float, mock: bool = False) -> None:
    _COST_TOTAL["usd"] += usd
    _COST_TOTAL["calls"] += calls
    if _COST_LOG is None:
        return
    _COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _COST_LOG.open("a", encoding="utf-8") as f:
        f.write(
            f"{time.strftime('%Y-%m-%dT%H:%M:%S')} · model={cfg.get('LLM_MODEL','?')} "
            f"· calls={calls} · usd={usd:.6f} · mock={mock} · total_usd={_COST_TOTAL['usd']:.6f}\n"
        )


def _check_budget(cfg: dict[str, str]) -> None:
    budget = float(cfg.get("LLM_BUDGET_USD", "0") or 0)
    if budget > 0 and _COST_TOTAL["usd"] > budget:
        raise LlmError(f"Превышен бюджет LLM: {_COST_TOTAL['usd']:.4f} > {budget}")


def _chat(cfg: dict[str, str], messages: list[dict[str, str]]) -> dict:
    url = cfg["LLM_API_BASE"].rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": cfg["LLM_MODEL"],
            "temperature": float(cfg["LLM_TEMPERATURE"]),
            "stream": False,
            "messages": messages,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['LLM_API_KEY']}",
        },
        method="POST",
    )
    retries = int(cfg["LLM_MAX_RETRIES"])
    timeout = float(cfg["LLM_TIMEOUT_SECONDS"])
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage", {})
            usd = _estimate_cost(cfg, usage)
            _log_cost(cfg, calls=1, usd=usd)
            _check_budget(cfg)
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2**attempt)
    raise LlmError(f"LLM недоступна после {retries} попыток: {last}")


def _estimate_cost(cfg: dict[str, str], usage: dict) -> float:
    p = int(usage.get("prompt_tokens", 0) or 0)
    c = int(usage.get("completion_tokens", 0) or 0)
    rate = float(cfg.get("LLM_PRICE_PER_1K", "0") or 0)
    return (p + c) / 1000.0 * rate


def _parse_json_reply(reply: str) -> dict:
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0] if "```" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LlmError(f"LLM вернула не-JSON: {reply[:200]!r}")
    return json.loads(text[start : end + 1])


def extract_llm(
    cfg: dict[str, str], transcript: str, event_date: str | None
) -> tuple[list[Decision], list[ActionItem]]:
    if _is_mock(cfg):
        data = _mock_extract(cfg, transcript, event_date)
    elif cfg.get("LOCAL_LLM_BASE_URL"):
        cfg = {**cfg, "LLM_API_BASE": cfg["LOCAL_LLM_BASE_URL"], "LLM_API_KEY": cfg.get("LLM_API_KEY") or "local"}
        data = _call_real(cfg, transcript, event_date)
    elif cfg.get("LLM_API_KEY"):
        data = _call_real(cfg, transcript, event_date)
    else:
        raise LlmError(
            "Не задан LLM_API_KEY (или LOCAL_LLM_BASE_URL, или mock) — используйте --engine rule"
        )

    decisions = [
        Decision(
            text=str(d.get("text", "")).strip(),
            reason=str(d.get("reason", "")).strip(),
            source=str(d.get("source", "")).strip(),
        )
        for d in data.get("decisions", [])
        if str(d.get("text", "")).strip()
    ]
    actions = [
        ActionItem(
            action=str(a.get("action", "")).strip(),
            owner=str(a.get("owner") or OWNER_NOT_SET).strip(),
            due=str(a.get("due") or DUE_NOT_SET).strip(),
            source=str(a.get("source", "")).strip(),
        )
        for a in data.get("actions", [])
        if str(a.get("action", "")).strip()
    ]
    return decisions, actions


def _call_real(cfg: dict[str, str], transcript: str, event_date: str | None) -> dict:
    user = (
        f"Дата встречи: {event_date or 'неизвестна'}.\n"
        f"Расшифровка релиз-синка:\n{wrap_untrusted(transcript)}\n"
        "Верни JSON."
    )
    reply = _chat(cfg, [{"role": "system", "content": _load_system_prompt()}, {"role": "user", "content": user}])
    return _parse_json_reply(reply["choices"][0]["message"]["content"])


def cost_total() -> dict[str, float]:
    return dict(_COST_TOTAL)
