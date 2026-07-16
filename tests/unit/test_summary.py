"""Unit-тесты сборщика сводки: статусы, блокеры, конфликты, обязательства, деградация."""
import unittest

from athanor.models import CalendarEvent, CaseInput, Issue, Mail, PullRequest, SummaryItem
from athanor.summary import build_summary

EVENT = CalendarEvent("TB", "Релиз-синк", "Альфа", "2026-07-03T14:00")


class TestSummary(unittest.TestCase):
    def test_status_items(self):
        case = CaseInput(EVENT, [Issue("APP-412", "Миграция", "в работе", "Разработчик A")], [], [], None)
        items = build_summary(case)
        self.assertTrue(any(i.kind == "status" and "APP-412" in i.text for i in items))
        self.assertEqual(items[0].confidence, 0.9)

    def test_blocker_from_mail(self):
        case = CaseInput(EVENT, [], [], [Mail("M1", "SRE", "2026-07-02", "Блокер", "APP-412 заблокирован")], None)
        items = build_summary(case)
        self.assertTrue(any(i.kind == "blocker" for i in items))

    def test_conflict_jira_vs_mail(self):
        case = CaseInput(
            EVENT,
            [Issue("APP-412", "Миграция", "готово", "Разработчик A")],
            [],
            [Mail("M1", "SRE", "2026-07-02", "Блокер по APP-412", "APP-412 не задеплоен, заблокирован")],
            None,
        )
        items = build_summary(case)
        conflicts = [i for i in items if i.kind == "conflict"]
        self.assertEqual(len(conflicts), 1)
        self.assertIn("КОНФЛИКТ", conflicts[0].text)

    def test_no_duplicate_conflict(self):
        case = CaseInput(
            EVENT,
            [Issue("APP-412", "Миграция", "готово", "Разработчик A")],
            [],
            [Mail("M1", "SRE", "2026-07-02", "Блокер по APP-412", "APP-412 не задеплоен, APP-412 заблокирован")],
            None,
        )
        items = build_summary(case)
        self.assertEqual(len([i for i in items if i.kind == "conflict"]), 1)

    def test_memory_commitment_not_cancelled(self):
        mem = [{"owner": "SRE", "action": "поднять стенд", "due": "2026-07-01", "source": "OPS-70", "status": "open"},
               {"owner": "SRE", "action": "отменённое", "due": "не указан", "source": "OPS-77", "status": "cancelled"}]
        case = CaseInput(EVENT, [], [], [], None)
        items = build_summary(case, memory_commitments=mem)
        commits = [i for i in items if i.kind == "commitment"]
        self.assertEqual(len(commits), 1)
        self.assertIn("поднять стенд", commits[0].text)

    def test_source_down_warning(self):
        case = CaseInput(EVENT, [], [], [], None, sources_down=["transcripts"])
        items = build_summary(case)
        self.assertTrue(any(i.kind == "warning" and "transcripts" in i.text for i in items))

    def test_empty_tracker_warning(self):
        case = CaseInput(EVENT, [], [], [], None)
        items = build_summary(case)
        self.assertTrue(any("пустой список" in i.text for i in items))


if __name__ == "__main__":
    unittest.main()
