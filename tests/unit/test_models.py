"""Unit-тесты моделей данных и схем."""
import unittest

from athanor.models import (
    ActionItem, Blocker, CalendarEvent, Decision, DraftAction, Evidence,
    Feedback, SkillVersion, DUE_NOT_SET, OWNER_NOT_SET, CONFIDENCE,
)


class TestModels(unittest.TestCase):
    def test_calendar_event_date(self):
        e = CalendarEvent("TB-01", "Релиз-синк", "Альфа", "2026-07-03T14:00")
        self.assertEqual(e.date, "2026-07-03")

    def test_action_item_defaults(self):
        a = ActionItem(action="подготовить отчёт")
        self.assertEqual(a.owner, OWNER_NOT_SET)
        self.assertEqual(a.due, DUE_NOT_SET)
        self.assertEqual(a.confidence, 0.0)
        self.assertEqual(a.id, "")

    def test_action_item_as_line(self):
        a = ActionItem("деплой", "SRE", "2026-07-03", "OPS-77")
        self.assertIn("SRE", a.as_line())
        self.assertIn("2026-07-03", a.as_line())
        self.assertIn("OPS-77", a.as_line())

    def test_decision_optional_fields(self):
        d = Decision("релиз 05.07", reason="перенос", source="APP-412")
        self.assertEqual(d.confidence, 0.0)
        self.assertEqual(d.source_evidence, "")

    def test_evidence_ref(self):
        e = Evidence("jira", "APP-412", "Миграция", confidence=CONFIDENCE["jira"])
        self.assertEqual(e.as_ref(), "evidence:jira:APP-412")
        self.assertEqual(e.confidence, 0.9)

    def test_blocker_defaults(self):
        b = Blocker("B-001", "смежный сервис не задеплоен")
        self.assertEqual(b.severity, "medium")
        self.assertEqual(b.resolution_status, "open")
        self.assertEqual(b.owner, OWNER_NOT_SET)

    def test_draft_action_statuses(self):
        d = DraftAction("D1", "mail_draft", "SRE", "тема", "тело")
        self.assertEqual(d.status, "proposed")

    def test_feedback_defaults(self):
        f = Feedback("run-1", usefulness=4)
        self.assertEqual(f.usefulness, 4)
        self.assertEqual(f.fact_corrections, [])

    def test_skill_version_defaults(self):
        v = SkillVersion("v2")
        self.assertEqual(v.status, "candidate")
        self.assertEqual(v.format_profile, "v1")


if __name__ == "__main__":
    unittest.main()
