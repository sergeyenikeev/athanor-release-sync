"""Загрузка входных данных: напрямую из файлов кейса или через MCP-заглушки.

Оба пути дают одинаковый CaseInput. Файловый путь используется тестовым
харнессом (офлайн, детерминированно); MCP-путь доказывает, что заглушки
отвечают по тому же интерфейсу, что и боевые коннекторы (streamable_http).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from .models import CalendarEvent, CaseInput, Issue, Mail, PullRequest


# ---------------------------------------------------------------- file mode
def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Битый/нечитаемый JSON — не падаем; возвращаем пусто, источник считается неполным
        return {}


def _safe_build(ctor, item: dict, kind: str, sink: list[str]) -> Any:
    """Собрать объект схемы, пропуская записи с некорректными полями (graceful)."""
    try:
        return ctor(**item)
    except TypeError:
        sink.append(f"пропущена некорректная запись {kind}: {item!r}")
        return None


def load_case_from_files(case_dir: Path, transcripts_down: bool = False) -> CaseInput:
    inp = case_dir / "input"
    cal = _read_json(inp / "calendar.json")
    trk = _read_json(inp / "tracker.json")
    mail = _read_json(inp / "mail.json")
    schema_warnings: list[str] = []

    events = [e for e in (_safe_build(CalendarEvent, e, "event", schema_warnings) for e in cal.get("events", [])) if e]
    release_windows = [str(w) for w in cal.get("release_windows", []) if w]
    issues = [i for i in (_safe_build(Issue, i, "issue", schema_warnings) for i in trk.get("issues", [])) if i]
    prs = [p for p in (_safe_build(PullRequest, p, "pr", schema_warnings) for p in trk.get("prs", [])) if p]
    mails = [m for m in (_safe_build(Mail, m, "mail", schema_warnings) for m in mail.get("messages", [])) if m]

    transcript: str | None = None
    sources_down: list[str] = []
    tpath = inp / "transcript.txt"
    if transcripts_down:
        sources_down.append("transcripts")
    elif tpath.is_file():
        try:
            transcript = tpath.read_text(encoding="utf-8")
        except OSError:
            transcript = None
            sources_down.append("transcripts")

    if not trk and not (inp / "tracker.json").is_file():
        sources_down.append("tracker_repo")

    case = CaseInput(
        event=events[0] if events else None,
        issues=issues,
        prs=prs,
        mails=mails,
        transcript=transcript,
        sources_down=sources_down,
        release_windows=release_windows,
    )
    case.schema_warnings = schema_warnings  # type: ignore[attr-defined]
    return case


# ----------------------------------------------------------------- MCP mode
class McpClient:
    """Минимальный клиент MCP поверх streamable_http (JSON-RPC 2.0 POST)."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._id = 0

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(f"MCP error from {self.base_url}: {data['error']}")
        return data.get("result", {})

    def initialize(self) -> dict[str, Any]:
        return self._call(
            "initialize",
            {"protocolVersion": "2025-03-26", "clientInfo": {"name": "athanor", "version": "1.0"}},
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return self._call("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        # содержимое кладём как text-блок с JSON внутри (см. mcp/_base.py)
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                return content[0]["text"]
        return result


def load_case_via_mcp(cfg: dict[str, str], case_id: str) -> CaseInput:
    """Собрать CaseInput вызовами трёх MCP-заглушек (данные кейса задаются
    заглушкам через переменную окружения MCP_CASE_DIR при их запуске)."""
    host = cfg["MCP_HOST"]
    cal_mail = McpClient(f"http://{host}:{cfg['MCP_CALENDAR_MAIL_PORT']}/mcp")
    tracker = McpClient(f"http://{host}:{cfg['MCP_TRACKER_REPO_PORT']}/mcp")
    transcripts = McpClient(f"http://{host}:{cfg['MCP_TRANSCRIPTS_PORT']}/mcp")

    sources_down: list[str] = []
    events: list[CalendarEvent] = []
    mails: list[Mail] = []
    issues: list[Issue] = []
    prs: list[PullRequest] = []
    transcript: str | None = None

    try:
        cal_mail.initialize()
        events = [CalendarEvent(**e) for e in cal_mail.call_tool("get_events") or []]
        mails = [Mail(**m) for m in cal_mail.call_tool("get_mail") or []]
    except Exception:
        sources_down.append("calendar_mail")

    try:
        tracker.initialize()
        issues = [Issue(**i) for i in tracker.call_tool("get_issues") or []]
        prs = [PullRequest(**p) for p in tracker.call_tool("get_prs") or []]
    except Exception:
        sources_down.append("tracker_repo")

    try:
        transcripts.initialize()
        got = transcripts.call_tool("get_transcript", {"case_id": case_id})
        transcript = got if isinstance(got, str) and got.strip() else None
    except Exception:
        sources_down.append("transcripts")

    return CaseInput(
        event=events[0] if events else None,
        issues=issues,
        prs=prs,
        mails=mails,
        transcript=transcript,
        sources_down=sources_down,
    )
