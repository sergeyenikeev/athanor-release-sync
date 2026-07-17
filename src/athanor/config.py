"""Загрузка конфигурации: .env (KEY=VALUE) + переменные окружения.

Переменные окружения имеют приоритет над .env. Секреты в репозиторий
не попадают: .env в .gitignore, значения по умолчанию не содержат ключей.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULTS = {
    "LLM_API_BASE": "https://openrouter.ai/api/v1",
    "LLM_API_KEY": "",
    "LLM_MODEL": "openai/gpt-4o-mini",
    "LLM_TEMPERATURE": "0",
    "LLM_TIMEOUT_SECONDS": "60",
    "LLM_MAX_RETRIES": "3",
    "LLM_BUDGET_USD": "0",  # 0 = без лимита; бюджет прогона корзины
    "LLM_PRICE_PER_1K": "0",  # оценка стоимости для логирования
    "LOCAL_LLM_BASE_URL": "",  # локальная OpenAI-compatible модель (vLLM, llama.cpp…)
    "ATHANOR_LLM_MOCK": "0",  # 1 = детерминированный mock без сети (для тестов)
    "MCP_HOST": "127.0.0.1",
    "MCP_CALENDAR_MAIL_PORT": "9901",
    "MCP_TRACKER_REPO_PORT": "9902",
    "MCP_TRANSCRIPTS_PORT": "9903",
    "MCP_CONFLUENCE_PORT": "9904",
    "MCP_TRANSCRIPTS_DOWN": "0",
    "ATHANOR_ENGINE": "llm",
    "ATHANOR_HITL": "1",
}


def _find_env_file(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        p = candidate / ".env"
        if p.is_file():
            return p
    return None


def load_config(env_file: Path | None = None) -> dict[str, str]:
    cfg = dict(_DEFAULTS)
    path = env_file or _find_env_file()
    if path and path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.split("#", 1)[0].strip() if " #" in value else value.strip()
            cfg[key.strip()] = value
    for key in cfg:
        if key in os.environ:
            cfg[key] = os.environ[key]
    return cfg
