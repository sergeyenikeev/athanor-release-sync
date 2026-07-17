"""Integration-тесты MCP-серверов: поднимаем серверы в процессе, вызываем через McpClient."""
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp"))
sys.path.insert(0, str(ROOT / "src"))

import _base  # noqa: E402
import calendar_mail  # noqa: E402
import tracker_repo  # noqa: E402
import transcripts  # noqa: E402
from athanor.sources import McpClient  # noqa: E402

DEMO = ROOT / "examples" / "demo_case"

_BACKEND_KEYS = ("MCP_BACKEND", "MCP_BACKEND_CALENDAR", "MCP_BACKEND_MAIL",
                 "MCP_BACKEND_JIRA", "MCP_BACKEND_PR", "MCP_BACKEND_TRANSCRIPT",
                 "MCP_BACKEND_CONFLUENCE")


class TestMcpServers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # изолируем от .env (MCP_BACKEND=live): тестовый контур — file-режим
        cls._saved = {k: os.environ.get(k) for k in _BACKEND_KEYS}
        os.environ["MCP_BACKEND"] = "file"
        for k in _BACKEND_KEYS[1:]:
            os.environ.pop(k, None)
        os.environ["MCP_CASE_DIR"] = str(DEMO)
        os.environ["MCP_TRANSCRIPTS_DOWN"] = "0"
        cls.servers = []
        cls.ports = [9921, 9922, 9923]
        for server, port in [(calendar_mail.server, cls.ports[0]),
                             (tracker_repo.server, cls.ports[1]),
                             (transcripts.server, cls.ports[2])]:
            srv = _base.serve(server, port)
            cls.servers.append(srv)
            threading.Thread(target=srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for s in cls.servers:
            s.shutdown()
        for k, v in cls._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_calendar_mail_tools(self):
        c = McpClient(f"http://127.0.0.1:{self.ports[0]}/mcp")
        info = c.initialize()
        self.assertEqual(info["serverInfo"]["name"], "calendar_mail")
        tools = [t["name"] for t in c.list_tools()]
        self.assertIn("get_events", tools)
        self.assertIn("get_mail", tools)
        events = c.call_tool("get_events")
        self.assertIsInstance(events, list)
        self.assertTrue(events)  # demo_case непустой

    def test_tracker_repo_tools(self):
        c = McpClient(f"http://127.0.0.1:{self.ports[1]}/mcp")
        c.initialize()
        issues = c.call_tool("get_issues")
        prs = c.call_tool("get_prs")
        self.assertIsInstance(issues, list)
        self.assertIsInstance(prs, list)

    def test_transcripts_tool(self):
        c = McpClient(f"http://127.0.0.1:{self.ports[2]}/mcp")
        c.initialize()
        t = c.call_tool("get_transcript", {"case_id": "demo"})
        self.assertIsInstance(t, str)

    def test_health_check(self):
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{self.ports[0]}/mcp", timeout=5) as r:
            self.assertEqual(r.status, 200)

    def test_unknown_tool_returns_error(self):
        c = McpClient(f"http://127.0.0.1:{self.ports[0]}/mcp")
        c.initialize()
        with self.assertRaises(RuntimeError):
            c.call_tool("nonexistent_tool")


if __name__ == "__main__":
    unittest.main()
