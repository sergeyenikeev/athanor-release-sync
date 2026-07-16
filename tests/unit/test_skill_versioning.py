"""Unit-тесты версионирования навыка: реестр, promote с gate, rollback, feedback→proposal."""
import json
import tempfile
import unittest
from pathlib import Path

from athanor.feedback import feedback_to_proposal, load_feedback, save_feedback
from athanor.models import Feedback
from athanor.skill_versioning import (
    get_active_version, list_versions, load_registry, promote, rollback,
    save_registry,
)


def _baseline_runner(profile: str) -> dict:
    # детерминированный «контрольный тест»: не деградирует (F1=1.0 для любого профиля)
    return {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def _degrading_runner(profile: str) -> dict:
    return {"precision": 1.0, "recall": 1.0, "f1": 0.9 if profile == "v2" else 1.0}


class TestSkillVersioning(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sv-"))
        self.reg_path = self.tmp / "registry.json"
        reg = {"active": "v1", "versions": {
            "v1": {"version": "v1", "status": "stable", "reason": "baseline", "format_profile": "v1", "test_results": {}, "created_at": "t", "promoted_at": "t"},
            "v2": {"version": "v2", "status": "candidate", "reason": "короче", "format_profile": "v2", "test_results": {}, "created_at": "t", "promoted_at": ""},
        }, "history": []}
        save_registry(reg, self.reg_path)

    def test_list_and_active(self):
        self.assertEqual(get_active_version(self.reg_path), "v1")
        self.assertEqual(len(list_versions(self.reg_path)), 2)

    def test_promote_no_degradation(self):
        r = promote("v2", reason="фидбек", control_runner=_baseline_runner, path=self.reg_path)
        self.assertTrue(r["applied"])
        self.assertEqual(get_active_version(self.reg_path), "v2")
        v = load_registry(self.reg_path)["versions"]["v2"]
        self.assertEqual(v["status"], "stable")

    def test_promote_degradation_rejected(self):
        r = promote("v2", reason="фидбек", control_runner=_degrading_runner, path=self.reg_path)
        self.assertFalse(r["applied"])
        self.assertEqual(get_active_version(self.reg_path), "v1")
        v = load_registry(self.reg_path)["versions"]["v2"]
        self.assertEqual(v["status"], "rejected")

    def test_rollback(self):
        promote("v2", reason="фидбек", control_runner=_baseline_runner, path=self.reg_path)
        r = rollback("v1", path=self.reg_path)
        self.assertTrue(r["applied"])
        self.assertEqual(get_active_version(self.reg_path), "v1")

    def test_rollback_unknown(self):
        r = rollback("v9", path=self.reg_path)
        self.assertFalse(r["applied"])


class TestFeedback(unittest.TestCase):
    def test_proposal_format_change(self):
        fb = Feedback("run-1", usefulness=3, format_change="короче, блокеры сверху")
        p = feedback_to_proposal(fb)
        self.assertEqual(p["format_profile"], "v2")
        self.assertIn("обратная связь", p["reason"])

    def test_proposal_low_usefulness(self):
        fb = Feedback("run-1", usefulness=2)
        p = feedback_to_proposal(fb)
        self.assertEqual(p["format_profile"], "")
        self.assertIn("полезности", p["reason"])

    def test_save_load_feedback(self):
        tmp = Path(tempfile.mkdtemp(prefix="fb-"))
        fb = Feedback("run-1", usefulness=4, format_change="короче")
        save_feedback(tmp, fb)
        loaded = load_feedback(tmp)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["usefulness"], 4)


if __name__ == "__main__":
    unittest.main()
