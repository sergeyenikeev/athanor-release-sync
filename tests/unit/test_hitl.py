"""Unit-тесты approval gate (HITL): статусы, отказ, правка, комментарий, исполнение без подтверждения."""
import json
import tempfile
import unittest
from pathlib import Path

from athanor.hitl import (
    approve_draft, comment_draft, edit_draft, execute_draft, make_drafts,
    reject_draft, APPROVED, AWAITING, EXECUTED, FAILED, REJECTED,
)
from athanor.models import ActionItem


class TestHitl(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="hitl-")) / "outbox"

    def _make(self):
        a = ActionItem("деплой", "SRE", "2026-07-03", "OPS-77")
        d = make_drafts([a], self.out, "TB-01")
        return self.out / f"{d[0]['id']}.json"

    def test_make_drafts_awaiting(self):
        p = self._make()
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(d["status"], AWAITING)

    def test_approve(self):
        p = self._make()
        d = approve_draft(p)
        self.assertEqual(d["status"], APPROVED)

    def test_reject(self):
        p = self._make()
        d = reject_draft(p, reason="неактуально")
        self.assertEqual(d["status"], REJECTED)
        self.assertEqual(d["reject_reason"], "неактуально")

    def test_edit(self):
        p = self._make()
        d = edit_draft(p, {"subject": "новая тема"})
        self.assertEqual(d["subject"], "новая тема")

    def test_comment(self):
        p = self._make()
        d = comment_draft(p, "проверить срок")
        self.assertEqual(len(d["comments"]), 1)

    def test_execute_requires_approval(self):
        p = self._make()
        d = execute_draft(p)  # без approve → failed
        self.assertEqual(d["status"], FAILED)

    def test_execute_after_approval(self):
        p = self._make()
        approve_draft(p)
        d = execute_draft(p)
        self.assertEqual(d["status"], EXECUTED)

    def test_double_approve_rejected(self):
        p = self._make()
        approve_draft(p)
        with self.assertRaises(ValueError):
            approve_draft(p)


if __name__ == "__main__":
    unittest.main()
