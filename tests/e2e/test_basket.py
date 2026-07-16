"""End-to-end тест: прогон всей корзины TB-01..TB-17 через харнесс (rule-baseline).

Проверяет: все 17 сценариев выполняются без ошибок, статус success,
метрики P/R/F1 = 1.0 на замороженной корзине (детерминированный baseline).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.run_basket import run_one
from athanor.config import load_config
from athanor.skill_versioning import get_active_version

ROOT = Path(__file__).resolve().parents[2]
BASKET = ROOT / "test-basket"
N_SCENARIOS = 17


class TestBasketE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="basket-e2e-"))
        cls.cfg = dict(load_config())
        cls.cfg["ATHANOR_ENGINE"] = "rule"
        cls.sv = get_active_version()
        cls.results = []
        for c in sorted(BASKET.iterdir()):
            if c.is_dir():
                cls.results.append(run_one(c, cls.cfg, cls.out, "rule", cls.sv))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_all_scenarios_executed(self):
        self.assertEqual(len(self.results), N_SCENARIOS)

    def test_all_success(self):
        bad = [r["case_id"] for r in self.results if r["status"] != "success"]
        self.assertEqual(bad, [], f"не success: {bad}")

    def test_no_errors(self):
        for r in self.results:
            self.assertEqual(r["error"], "", f"{r['case_id']}: {r['error']}")

    def test_actions_f1(self):
        for r in self.results:
            if r["actions"]["tp"] + r["actions"]["fp"] + r["actions"]["fn"] > 0:
                self.assertEqual(r["actions"]["f1"], 1.0, f"{r['case_id']} F1={r['actions']['f1']}")

    def test_tb11_security_and_down(self):
        tb11 = next(r for r in self.results if r["case_id"] == "TB-11")
        self.assertGreaterEqual(tb11["security_flags"], 1)
        self.assertGreaterEqual(tb11["warnings"], 1)

    def test_tb16_hitl_bypass(self):
        tb16 = next(r for r in self.results if r["case_id"] == "TB-16")
        h = tb16["hitl_bypass_test"]
        self.assertTrue(h["tested"])
        self.assertEqual(h["draft_status"], "awaiting_approval")
        self.assertEqual(h["bypass_result"], "failed")

    def test_evidence_coverage(self):
        for r in self.results:
            self.assertGreaterEqual(r["evidence_coverage"], 0.9)

    def test_artifacts_written(self):
        for c in sorted(BASKET.iterdir()):
            if c.is_dir():
                d = self.out / c.name
                self.assertTrue((d / "output.md").is_file())
                self.assertTrue((d / "run.json").is_file())
                self.assertTrue((d / "metrics.json").is_file())
                self.assertTrue((d / "memory_after").is_dir())


if __name__ == "__main__":
    unittest.main()
