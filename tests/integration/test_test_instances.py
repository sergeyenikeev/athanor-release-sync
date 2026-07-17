"""Integration-тесты тестовых инстансов (уровень интеграций, task6).

Поднимает локальные тестовые инстансы (Jira REST v2, Bitbucket Cloud REST 2.0,
Confluence REST API v1) и MCP-адаптеры в режиме MCP_BACKEND=test, проверяет
реальные HTTP-контракты и конвертацию «контракт системы → схема агента».
Calendar/mail в test-режиме читаются из файла (graph-инстанс не используется).
"""
import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp"))
sys.path.insert(0, str(ROOT / "test-instances"))
sys.path.insert(0, str(ROOT / "src"))

import _base  # noqa: E402
import tracker_repo  # noqa: E402
import confluence  # noqa: E402
import jira_server  # noqa: E402
import bitbucket_server  # noqa: E402
import confluence_server  # noqa: E402
from athanor.sources import McpClient  # noqa: E402

_PER_SOURCE = ("MCP_BACKEND_CALENDAR", "MCP_BACKEND_MAIL", "MCP_BACKEND_JIRA",
               "MCP_BACKEND_PR", "MCP_BACKEND_TRANSCRIPT", "MCP_BACKEND_CONFLUENCE")


def _serve(handler, port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class TestTestInstances(unittest.TestCase):
    """Тестовые инстансы отвечают по реальным контрактам."""

    @classmethod
    def setUpClass(cls):
        cls.ti_ports = [9931, 9933]
        cls.ti_srvs = [
            _serve(jira_server.Handler, cls.ti_ports[0]),
            _serve(bitbucket_server.Handler, cls.ti_ports[1]),
        ]
        # направим _backends на тестовые порты
        os.environ["TEST_JIRA_URL"] = f"http://127.0.0.1:{cls.ti_ports[0]}"
        os.environ["TEST_BITBUCKET_URL"] = f"http://127.0.0.1:{cls.ti_ports[1]}"
        os.environ["MCP_BACKEND"] = "test"
        # изолируем от .env per-source override'ов (напр. MCP_BACKEND_PR=bitbucket)
        cls._saved_ps = {k: os.environ.pop(k, None) for k in _PER_SOURCE}
        cls.mcp_port_tracker = 9942
        cls.mcp_srvs = [
            _base.serve(tracker_repo.server, cls.mcp_port_tracker),
        ]
        for s in cls.mcp_srvs:
            threading.Thread(target=s.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for s in cls.ti_srvs + cls.mcp_srvs:
            s.shutdown()
        os.environ.pop("MCP_BACKEND", None)
        for k, v in cls._saved_ps.items():
            if v is not None:
                os.environ[k] = v

    def test_jira_rest_contract(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.ti_ports[0]}/rest/api/2/search?jql=project=ALPHA", timeout=5
        ) as r:
            self.assertEqual(r.status, 200)
            body = json.loads(r.read().decode())
        self.assertEqual(body["total"], 2)
        keys = {i["key"] for i in body["issues"]}
        self.assertEqual(keys, {"APP-412", "APP-521"})

    def test_bitbucket_pulls_contract(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.ti_ports[1]}/repositories/athanor/alpha/pullrequests?state=OPEN", timeout=5
        ) as r:
            body = json.loads(r.read().decode())
        self.assertEqual(len(body["values"]), 1)
        self.assertEqual(body["values"][0]["id"], 128)

    def test_mcp_adapter_get_issues_from_jira(self):
        c = McpClient(f"http://127.0.0.1:{self.mcp_port_tracker}/mcp")
        c.initialize()
        issues = c.call_tool("get_issues")
        self.assertEqual(len(issues), 2)
        by_key = {i["key"]: i for i in issues}
        self.assertEqual(by_key["APP-412"]["status"], "готово")
        self.assertEqual(by_key["APP-412"]["assignee_role"], "Разработчик backend")

    def test_mcp_adapter_get_prs_from_bitbucket(self):
        c = McpClient(f"http://127.0.0.1:{self.mcp_port_tracker}/mcp")
        c.initialize()
        prs = c.call_tool("get_prs")
        self.assertEqual(len(prs), 1)
        pr = prs[0]
        self.assertEqual(pr["number"], 128)
        self.assertEqual(pr["status"], "на ревью")
        self.assertEqual(pr["issue_key"], "APP-412")
        self.assertEqual(pr["review_days"], 2)


class TestConfluenceInstance(unittest.TestCase):
    """Тестовый инстанс Confluence отвечает по реальному контракту REST API v1;
    MCP-адаптер конвертирует ответ в схему агента (ConfluencePage)."""

    @classmethod
    def setUpClass(cls):
        cls.ti_port = 9964
        cls.ti_srv = _serve(confluence_server.Handler, cls.ti_port)
        os.environ["TEST_CONFLUENCE_URL"] = f"http://127.0.0.1:{cls.ti_port}"
        os.environ["TEST_CONFLUENCE_SPACE"] = "ALPHA"
        os.environ["MCP_BACKEND"] = "test"
        cls._saved_ps = {k: os.environ.pop(k, None) for k in _PER_SOURCE}
        cls.mcp_port = 9974
        cls.mcp_srv = _base.serve(confluence.server, cls.mcp_port)
        threading.Thread(target=cls.mcp_srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.ti_srv.shutdown()
        cls.mcp_srv.shutdown()
        os.environ.pop("MCP_BACKEND", None)
        for k, v in cls._saved_ps.items():
            if v is not None:
                os.environ[k] = v

    def test_confluence_cql_search_contract(self):
        from urllib.parse import quote
        cql = quote('space="ALPHA" AND label="alpha-demo"')
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.ti_port}/wiki/rest/api/content/search?cql={cql}"
            "&expand=body.view,version,space&limit=25", timeout=5
        ) as r:
            self.assertEqual(r.status, 200)
            body = json.loads(r.read().decode())
        self.assertEqual(body["size"], 2)
        titles = {p["title"] for p in body["results"]}
        self.assertIn("Release Plan · Альфа", titles)
        self.assertIn("Decision Log · Альфа", titles)
        # контракт: каждая страница имеет space/version/body.view
        p0 = body["results"][0]
        self.assertEqual(p0["space"]["key"], "ALPHA")
        self.assertIn("version", p0)
        self.assertIn("view", p0["body"])

    def test_confluence_content_by_id_contract(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.ti_port}/wiki/rest/api/content/196612", timeout=5
        ) as r:
            body = json.loads(r.read().decode())
        self.assertEqual(body["id"], "196612")
        self.assertEqual(body["title"], "Release Plan · Альфа")

    def test_mcp_adapter_get_confluence_pages(self):
        c = McpClient(f"http://127.0.0.1:{self.mcp_port}/mcp")
        info = c.initialize()
        self.assertEqual(info["serverInfo"]["name"], "confluence")
        tools = [t["name"] for t in c.list_tools()]
        self.assertEqual(tools, ["get_confluence_pages"])
        pages = c.call_tool("get_confluence_pages")
        self.assertEqual(len(pages), 2)
        by_id = {p["id"]: p for p in pages}
        rp = by_id["196612"]
        self.assertEqual(rp["title"], "Release Plan · Альфа")
        self.assertEqual(rp["space"], "ALPHA")
        self.assertEqual(rp["version"], 3)
        self.assertEqual(rp["updated_at"], "2026-07-01")
        self.assertIn("196612", rp["url"])
        # HTML body преобразован в чистый текст-excerpt
        self.assertIn("окно", rp["excerpt"])
        self.assertNotIn("<", rp["excerpt"])


if __name__ == "__main__":
    unittest.main()
