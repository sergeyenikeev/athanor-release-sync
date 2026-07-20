from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def _state_dir(api) -> str:
    """Return the state directory for this skill, creating it if needed."""
    base = os.path.join(str(api.skills_dir or "."), "vk-bridge", "state")
    os.makedirs(base, exist_ok=True)
    return base


def _state_file(api, filename: str) -> str:
    return os.path.join(_state_dir(api), filename)


def _load_settings(api) -> Dict[str, Any]:
    path = _state_file(api, "settings.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings_dict(api, settings: Dict[str, Any]) -> None:
    path = _state_file(api, "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _load_offset(api) -> int:
    path = _state_file(api, "poll_offset.json")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r") as f:
            return json.load(f).get("offset", 0)
    except (json.JSONDecodeError, OSError):
        return 0


def _save_offset(api, offset: int) -> None:
    path = _state_file(api, "poll_offset.json")
    with open(path, "w") as f:
        json.dump({"offset": offset}, f)


_VALID_COMMAND_MODES = frozenset({"strict", "safe_commands", "full_access"})

_VK_COMMAND_MODE_STRICT = "strict"
_VK_COMMAND_MODE_SAFE = "safe_commands"
_VK_COMMAND_MODE_FULL = "full_access"

_VK_SAFE_TRANSLATIONS: dict[str, str] = {
    "/status": "/status",
    "/bg status": "/bg status",
    "/bg": "/bg",
}


def _translate_command(text: str, command_mode: str) -> Optional[str]:
    if not text or not text.strip().startswith("/"):
        return text
    normalized = text.strip().lower()
    if command_mode == _VK_COMMAND_MODE_STRICT:
        return None
    if command_mode == _VK_COMMAND_MODE_FULL:
        return text.strip()
    for cmd_key in sorted(_VK_SAFE_TRANSLATIONS, key=len, reverse=True):
        if normalized == cmd_key or normalized.startswith(cmd_key + " "):
            return _VK_SAFE_TRANSLATIONS[cmd_key]
    return None


def _host_headers(api) -> Dict[str, str]:
    return {"X-Skill-Token": api.get_skill_token().use_in_request()}
