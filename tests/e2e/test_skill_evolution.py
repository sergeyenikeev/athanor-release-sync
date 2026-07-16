"""End-to-end тест эволюции навыка: promote v2 (контрольные тесты без деградации) + rollback.

Использует реальный control_runner (athanor.control) на замороженной корзине, но
реестр копируется во временную папку — реальный registry.json не мутирует.
"""
import json
import shutil
import unittest
from pathlib import Path

from athanor.control import control_runner
from athanor.skill_versioning import (
    get_active_version, load_registry, promote, rollback, save_registry,
)

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "skills" / "release_sync" / "versions" / "registry.json"


class TestSkillEvolution(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_registry"
        self.tmp.mkdir(exist_ok=True)
        self.reg_path = self.tmp / "registry.json"
        save_registry(load_registry(REG), self.reg_path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_control_runner_f1(self):
        m = control_runner("v1")
        self.assertEqual(m["f1"], 1.0)

    def test_promote_v2_no_degradation(self):
        r = promote("v2", reason="обратная связь: короче", control_runner=control_runner, path=self.reg_path)
        self.assertTrue(r["applied"], r)
        self.assertEqual(get_active_version(self.reg_path), "v2")
        v2 = load_registry(self.reg_path)["versions"]["v2"]
        self.assertEqual(v2["status"], "stable")

    def test_rollback_after_promote(self):
        promote("v2", reason="фидбек", control_runner=control_runner, path=self.reg_path)
        r = rollback("v1", path=self.reg_path)
        self.assertTrue(r["applied"])
        self.assertEqual(get_active_version(self.reg_path), "v1")
        hist = load_registry(self.reg_path)["history"]
        self.assertTrue(any(h["action"] == "rollback" for h in hist))

    def test_v2_format_does_not_degrade(self):
        """F1 на v2 не ниже F1 на v1 — gate проходит."""
        f1_v1 = control_runner("v1")["f1"]
        f1_v2 = control_runner("v2")["f1"]
        self.assertGreaterEqual(f1_v2, f1_v1)


if __name__ == "__main__":
    unittest.main()
