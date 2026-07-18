"""Unit-тест Bitbucket Cloud-адаптера (MCP_BACKEND_PR=bitbucket).

Без сети и кредов: патчит urllib.request.urlopen фейковым ответом Bitbucket
Cloud REST 2.0 и проверяет конвертацию «контракт → схема агента» (PullRequest),
построение Basic-авторизации (email аккаунта + API token) и правильный эндпоинт.
"""
import base64
import json
import os
import sys
import unittest
import urllib.request
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp"))
import _backends  # noqa: E402


class _FakeResp:
    def __init__(self, body_bytes, status=200):
        self._buf = BytesIO(body_bytes)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._buf.read()


class TestBitbucketCloud(unittest.TestCase):
    """bitbucket_prs_cloud(): контракт Bitbucket REST 2.0 → PullRequest + auth (Basic или Bearer)."""

    def setUp(self):
        os.environ["MCP_BACKEND_PR"] = "bitbucket"
        os.environ["BITBUCKET_WORKSPACE"] = "athanor"
        os.environ["BITBUCKET_REPO_SLUG"] = "alpha"
        os.environ["BITBUCKET_EMAIL"] = "demo@example.test"
        os.environ["BITBUCKET_API_TOKEN"] = "secret"

    def tearDown(self):
        for k in ("MCP_BACKEND_PR", "BITBUCKET_WORKSPACE", "BITBUCKET_REPO_SLUG",
                  "BITBUCKET_EMAIL", "BITBUCKET_API_TOKEN", "BITBUCKET_WORKSPACE_TOKEN",
                  "BITBUCKET_URL"):
            os.environ.pop(k, None)

    def _patch_urlopen(self, payload):
        captured = {}

        def fake(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            return _FakeResp(json.dumps(payload).encode("utf-8"))

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake
        return captured, orig

    def test_cloud_pr_conversion_and_auth(self):
        payload = {"pagelen": 50, "size": 1, "page": 1, "values": [{
            "id": 128, "title": "Миграция на ППРБ", "state": "OPEN",
            "created_on": "2026-06-30T10:00:00Z", "updated_on": "2026-07-02T09:00:00Z",
            "summary": {"raw": "PR по APP-412: миграция на ППРБ"},
            "author": {"nickname": "Разработчик backend"},
            "source": {"branch": {"name": "feature/pprb-migration"}},
            "destination": {"branch": {"name": "main"}},
        }]}
        captured, orig = self._patch_urlopen(payload)
        try:
            prs = _backends.get_prs()
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(len(prs), 1)
        pr = prs[0]
        self.assertEqual(pr["number"], 128)
        self.assertEqual(pr["title"], "Миграция на ППРБ")
        self.assertEqual(pr["status"], "на ревью")
        self.assertEqual(pr["issue_key"], "APP-412")
        self.assertEqual(pr["review_days"], 2)
        # эндпоинт и query контракта Bitbucket Cloud
        self.assertIn("/repositories/athanor/alpha/pullrequests", captured["url"])
        self.assertIn("state=OPEN", captured["url"])
        self.assertIn("pagelen=50", captured["url"])
        # Basic-авторизация: email:api_token
        hdrs = captured["headers"]
        auth = next((v for k, v in hdrs.items() if k.lower() == "authorization"), "")
        self.assertTrue(auth.startswith("Basic "), f"expected Basic auth, got {auth!r}")
        self.assertEqual(base64.b64decode(auth.split(" ", 1)[1]).decode(), "demo@example.test:secret")

    def test_cloud_state_mapping_merged(self):
        payload = {"values": [{
            "id": 7, "title": "Готовый PR", "state": "MERGED",
            "created_on": "2026-06-01T00:00:00Z", "updated_on": "2026-06-01T00:00:00Z",
            "summary": {"raw": "no key here"},
        }]}
        captured, orig = self._patch_urlopen(payload)
        try:
            prs = _backends.get_prs()
        finally:
            urllib.request.urlopen = orig
        # state=OPEN в query, но ответ фейковый — маппинг MERGED → «смержен»
        self.assertEqual(prs[0]["status"], "смержен")
        self.assertEqual(prs[0]["issue_key"], "")
        self.assertEqual(prs[0]["review_days"], 1)

    def test_cloud_missing_creds_raises(self):
        os.environ.pop("BITBUCKET_API_TOKEN", None)
        os.environ.pop("BITBUCKET_WORKSPACE_TOKEN", None)
        with self.assertRaises(RuntimeError) as cm:
            _backends.get_prs()
        self.assertIn("BITBUCKET_API_TOKEN", str(cm.exception))

    def test_cloud_workspace_token_bearer_auth(self):
        """Workspace access token (Premium) → Bearer auth, email не нужен."""
        os.environ.pop("BITBUCKET_EMAIL", None)
        os.environ.pop("BITBUCKET_API_TOKEN", None)
        os.environ["BITBUCKET_WORKSPACE_TOKEN"] = "ws-secret"
        payload = {"values": [{
            "id": 1, "title": "x", "state": "OPEN",
            "created_on": "2026-06-01T00:00:00Z", "updated_on": "2026-06-01T00:00:00Z",
            "summary": {"raw": ""},
        }]}
        captured, orig = self._patch_urlopen(payload)
        try:
            _backends.get_prs()
        finally:
            urllib.request.urlopen = orig
        hdrs = captured["headers"]
        auth = next((v for k, v in hdrs.items() if k.lower() == "authorization"), "")
        self.assertEqual(auth, "Bearer ws-secret")

    def test_cloud_missing_repo_raises(self):
        os.environ.pop("BITBUCKET_REPO_SLUG", None)
        with self.assertRaises(RuntimeError) as cm:
            _backends.get_prs()
        self.assertIn("BITBUCKET_REPO_SLUG", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
