"""Минимальный MCP-сервер (streamable_http, JSON-RPC 2.0 poverh HTTP POST).

Реализовано подмножество протокола, достаточное для обнаружения и вызова
инструментов клиентом Ouroboros: initialize, tools/list, tools/call.
Каждая заглушка объявляет свои инструменты и читает обезличенные данные
из папки кейса (env MCP_CASE_DIR, по умолчанию examples/demo_case).
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]


def case_dir() -> Path:
    return Path(os.environ.get("MCP_CASE_DIR", REPO_ROOT / "examples" / "demo_case"))


def read_case_json(name: str, key: str) -> list[dict[str, Any]]:
    path = case_dir() / "input" / name
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get(key, [])


class McpStub:
    def __init__(self, name: str, tools: dict[str, tuple[dict[str, Any], Callable[..., Any]]]):
        self.name = name
        self.tools = tools  # tool_name -> (schema, handler)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        rid = request.get("id")
        try:
            if method == "initialize":
                result: Any = {
                    "protocolVersion": "2025-03-26",
                    "serverInfo": {"name": self.name, "version": "1.0.0-mvp"},
                    "capabilities": {"tools": {}},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": tname,
                            "description": schema.get("description", ""),
                            "inputSchema": schema.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        }
                        for tname, (schema, _) in self.tools.items()
                    ]
                }
            elif method == "tools/call":
                params = request.get("params", {})
                tname = params.get("name")
                if tname not in self.tools:
                    raise KeyError(f"unknown tool {tname!r}")
                _, handler = self.tools[tname]
                data = handler(**(params.get("arguments") or {}))
                result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
            elif method == "notifications/initialized":
                return {}  # уведомление — без ответа
            else:
                raise KeyError(f"unsupported method {method!r}")
            return {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:  # noqa: BLE001 — заглушка отвечает ошибкой протокола
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(e)}}


def make_handler(stub: McpStub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            reply = stub.handle(body)
            payload = json.dumps(reply, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 — health-check
            payload = json.dumps({"server": stub.name, "status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args: Any) -> None:  # тихий режим
            pass

    return Handler


def serve(stub: McpStub, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(stub))
    return server
