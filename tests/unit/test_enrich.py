"""Unit-тесты enrich: блокеры из решений синка (в дополнение к письмам/конфликтам)."""
import unittest

from athanor.enrich import extract_blockers
from athanor.models import OWNER_NOT_SET, CalendarEvent, CaseInput, Decision, SummaryItem

EVENT = CalendarEvent("TB", "Релиз-синк", "Альфа", "2026-07-03T14:00")


def _case() -> CaseInput:
    return CaseInput(EVENT, [], [], [], None)


class TestBlockersFromDecisions(unittest.TestCase):
    def test_decision_blocker_extracted(self):
        decisions = [
            Decision("блокер по OPS-77 фиксируем, ответственный SRE", source="OPS-77", confidence=0.9)
        ]
        blockers = extract_blockers(_case(), [], decisions)
        self.assertEqual(len(blockers), 1)
        b = blockers[0]
        self.assertEqual(b.owner, "SRE")
        self.assertEqual(b.source_evidence, "OPS-77")
        self.assertEqual(b.severity, "high")
        self.assertEqual(b.resolution_status, "confirmed")
        self.assertEqual(b.confidence, 0.9)

    def test_plain_decision_is_not_blocker(self):
        decisions = [Decision("выкатываем релиз 03.07 в окно 18:00–20:00", source="расшифровка синка 03.07")]
        self.assertEqual(extract_blockers(_case(), [], decisions), [])

    def test_blocker_without_owner_gets_owner_not_set(self):
        decisions = [Decision("деплой заблокирован до миграции", source="расшифровка синка 03.07")]
        blockers = extract_blockers(_case(), [], decisions)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0].owner, OWNER_NOT_SET)

    def test_summary_blockers_still_extracted(self):
        items = [SummaryItem("Блокер из письма (SRE, 2026-07-02): ППРБ", source="письмо M1", confidence=0.7, kind="blocker")]
        blockers = extract_blockers(_case(), items, [])
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0].resolution_status, "open")

    def test_none_decisions_backward_compatible(self):
        self.assertEqual(extract_blockers(_case(), []), [])


if __name__ == "__main__":
    unittest.main()
