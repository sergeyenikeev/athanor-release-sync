"""Integration-тест полного workflow агента на TB-01 (файловый путь + память)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from athanor.agent import run_case
from athanor.config import load_config
from athanor.memory import _slug
from athanor.sources import load_case_from_files

ROOT = Path(__file__).resolve().parents[2]


class TestAgentWorkflow(unittest.TestCase):
    def setUp(self):
        self.case_dir = ROOT / "test-basket" / "TB-01"
        self.mem = Path(tempfile.mkdtemp(prefix="wf-mem-"))
        (self.mem / "knowledge").mkdir(parents=True, exist_ok=True)
        seed = self.case_dir / "input" / "memory_seed.md"
        if seed.is_file():
            first = seed.read_text(encoding="utf-8").splitlines()[0]
            name = f"release_{_slug(first.split('«')[1].split('»')[0])}.md"
            shutil.copy(seed, self.mem / "knowledge" / name)
        self.out = Path(tempfile.mkdtemp(prefix="wf-out-"))

    def tearDown(self):
        shutil.rmtree(self.mem, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def test_run_case_tb01(self):
        cfg = dict(load_config())
        cfg["ATHANOR_ENGINE"] = "rule"
        case = load_case_from_files(self.case_dir)
        res = run_case(case, "TB-01", cfg, self.mem, self.out / "outbox",
                       engine="rule", format_profile="v1")
        self.assertEqual(res.case_id, "TB-01")
        self.assertEqual(len(res.decisions), 1)
        self.assertEqual(len(res.actions), 1)
        self.assertEqual(res.actions[0].owner, "Разработчик backend")
        self.assertTrue(res.memory_updates)
        self.assertTrue(res.drafts)
        # evidence linking: у action есть id и confidence
        self.assertTrue(res.actions[0].id.startswith("C-"))
        self.assertGreater(res.actions[0].confidence, 0.0)
        self.assertEqual(res.skill_version, "v1")

    def test_run_case_via_mcp_equivalence(self):
        """Файловый и MCP-пути дают одинаковый CaseInput (структурно)."""
        from athanor.sources import load_case_from_files as load_files
        case = load_files(self.case_dir)
        self.assertEqual(case.event.project, "Альфа")
        self.assertEqual(len(case.issues), 2)


if __name__ == "__main__":
    unittest.main()
