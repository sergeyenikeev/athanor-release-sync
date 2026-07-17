"""Unit-тесты Confluence-коннектора: модель, уверенность, секция сводки,
файловая загрузка, dispatch бэкендов, конвертация REST API v1 → схема агента.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp"))
sys.path.insert(0, str(ROOT / "src"))

from athanor.models import CONFIDENCE, CaseInput, CalendarEvent, ConfluencePage
from athanor.sources import load_case_from_files
from athanor.summary import build_summary

import _backends  # noqa: E402


EVENT = CalendarEvent("TB", "Релиз-синк", "Альфа", "2026-07-03T14:00")


class TestConfluenceModel(unittest.TestCase):
    def test_page_defaults(self):
        p = ConfluencePage("196612", "Release Plan · Альфа")
        self.assertEqual(p.space, "")
        self.assertEqual(p.excerpt, "")
        self.assertEqual(p.url, "")
        self.assertEqual(p.version, 1)
        self.assertEqual(p.updated_at, "")

    def test_page_full(self):
        p = ConfluencePage("196612", "Release Plan", space="ALPHA",
                           excerpt="окно 03.07", url="http://x/196612", version=3,
                           updated_at="2026-07-01")
        self.assertEqual(p.space, "ALPHA")
        self.assertEqual(p.version, 3)

    def test_confidence_confluence(self):
        self.assertIn("confluence", CONFIDENCE)
        self.assertEqual(CONFIDENCE["confluence"], 0.8)


class TestConfluenceSummary(unittest.TestCase):
    def test_doc_section_present(self):
        pages = [ConfluencePage("196612", "Release Plan · Альфа", space="ALPHA",
                                excerpt="Целевое окно 03.07 18:00–20:00")]
        case = CaseInput(EVENT, [], [], [], None, confluence_pages=pages)
        items = build_summary(case)
        docs = [i for i in items if i.kind == "doc"]
        self.assertEqual(len(docs), 1)
        self.assertIn("Release Plan", docs[0].text)
        self.assertIn("Confluence 196612", docs[0].source)
        self.assertIn("ALPHA", docs[0].source)
        self.assertEqual(docs[0].confidence, CONFIDENCE["confluence"])

    def test_no_doc_section_when_empty(self):
        case = CaseInput(EVENT, [], [], [], None)
        items = build_summary(case)
        self.assertFalse([i for i in items if i.kind == "doc"])


class TestConfluenceFileLoading(unittest.TestCase):
    def test_load_case_reads_confluence_json(self):
        case = load_case_from_files(ROOT / "examples" / "demo_case_alpha")
        self.assertEqual(len(case.confluence_pages), 2)
        titles = {p.title for p in case.confluence_pages}
        self.assertIn("Release Plan · Альфа", titles)
        self.assertIn("Decision Log · Альфа", titles)
        self.assertEqual(case.confluence_pages[0].space, "ALPHA")

    def test_missing_confluence_json_no_crash(self):
        d = Path(tempfile.mkdtemp(prefix="conf-missing-"))
        case = load_case_from_files(d)
        self.assertEqual(case.confluence_pages, [])

    def test_malformed_confluence_page_skipped(self):
        d = Path(tempfile.mkdtemp(prefix="conf-bad-"))
        (d / "input").mkdir()
        (d / "input" / "confluence.json").write_text(
            json.dumps({"pages": [{"title": "без id"}]}),  # нет id → TypeError
            encoding="utf-8")
        case = load_case_from_files(d)
        self.assertEqual(case.confluence_pages, [])
        self.assertTrue(getattr(case, "schema_warnings", []))


class TestConfluenceBackends(unittest.TestCase):
    def setUp(self):
        # изолируем от env процесса
        self._saved = {k: os.environ.get(k) for k in
                       ("MCP_BACKEND", "MCP_BACKEND_CONFLUENCE", "MCP_CASE_DIR")}
        for k in ("MCP_BACKEND", "MCP_BACKEND_CONFLUENCE"):
            os.environ.pop(k, None)
        os.environ["MCP_CASE_DIR"] = str(ROOT / "examples" / "demo_case_alpha")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_file_backend_returns_pages(self):
        pages = _backends.get_confluence_pages()
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["id"], "196612")
        self.assertEqual(pages[0]["space"], "ALPHA")

    def test_atlassian_backend_missing_creds_raises(self):
        os.environ["MCP_BACKEND_CONFLUENCE"] = "atlassian"
        os.environ.pop("CONFLUENCE_EMAIL", None)
        os.environ.pop("CONFLUENCE_API_TOKEN", None)
        os.environ.pop("JIRA_EMAIL", None)
        os.environ.pop("JIRA_API_TOKEN", None)
        with self.assertRaises(RuntimeError):
            _backends.get_confluence_pages()

    def test_results_to_schema_conversion(self):
        data = {
            "_links": {"base": "https://x.atlassian.net/wiki"},
            "results": [
                {"id": "1", "type": "page", "title": "P1",
                 "space": {"key": "ALPHA"},
                 "version": {"number": 2, "when": "2026-07-01T09:30:00.000Z"},
                 "body": {"view": {"value": "<p>Hello <b>world</b></p>"}},
                 "_links": {"webui": "/spaces/ALPHA/pages/1"}},
                {"id": "2", "type": "attachment", "title": "skip attachment"},
            ],
        }
        out = _backends._confluence_results_to_schema(data, base_url="https://x.atlassian.net/wiki")
        self.assertEqual(len(out), 1)  # attachment отфильтрован
        p = out[0]
        self.assertEqual(p["id"], "1")
        self.assertEqual(p["title"], "P1")
        self.assertEqual(p["space"], "ALPHA")
        self.assertEqual(p["version"], 2)
        self.assertEqual(p["updated_at"], "2026-07-01")
        self.assertEqual(p["excerpt"], "Hello world")
        self.assertEqual(p["url"], "https://x.atlassian.net/wiki/spaces/ALPHA/pages/1")

    def test_excerpt_truncation(self):
        long_html = "<p>" + " ".join(["слово"] * 200) + "</p>"
        self.assertLessEqual(len(_backends._excerpt(long_html, limit=50)), 52)
        self.assertTrue(_backends._excerpt(long_html, limit=50).endswith("…"))

    def test_cql_space_filter_for_personal_space(self):
        # личное пространство (~…): space-фильтр опускается, CQL — только по лейблу
        self.assertEqual(_backends._confluence_cql("~701215abc", "alpha-demo"),
                         'label="alpha-demo"')
        # глобальное пространство: space + label
        self.assertEqual(_backends._confluence_cql("ALPHA", "alpha-demo"),
                         'space="ALPHA" AND label="alpha-demo"')
        # пустой space: только лейбл
        self.assertEqual(_backends._confluence_cql("", "alpha-demo"),
                         'label="alpha-demo"')
        # всё пусто → широкий поиск type=page (только для дискавери)
        self.assertEqual(_backends._confluence_cql("", ""), "type=page")

    def test_results_to_schema_strips_leading_title(self):
        data = {
            "_links": {"base": "https://x.atlassian.net/wiki"},
            "results": [{
                "id": "1", "type": "page", "title": "Release Plan",
                "space": {"key": "ALPHA"},
                "version": {"number": 1, "when": "2026-07-01T09:30:00.000Z"},
                "body": {"view": {"value": "<h1>Release Plan</h1><p>окно 03.07</p>"}},
                "_links": {"webui": "/spaces/ALPHA/pages/1"},
            }],
        }
        out = _backends._confluence_results_to_schema(data, base_url="https://x.atlassian.net/wiki")
        self.assertEqual(len(out), 1)
        # excerpt не должен начинаться с заголовка (H1 из body.view отброшен)
        self.assertEqual(out[0]["excerpt"], "окно 03.07")


if __name__ == "__main__":
    unittest.main()
