"""Unit-тесты rule-экстрактора: решения vs идеи, поручения, срок, владелец, отмена."""
import unittest

from athanor.extract import extract_rule

EVENT = "2026-07-03"


class TestExtract(unittest.TestCase):
    def test_decision_with_reason(self):
        d, a, c = extract_rule("Тимлид: Решение: окно релиза 03.07, потому что регламент", EVENT)
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0].text, "окно релиза 03.07")
        self.assertEqual(d[0].reason, "регламент")

    def test_idea_is_not_decision(self):
        d, a, c = extract_rule("Владелец продукта: идея — может быть стоит перенести на вечер", EVENT)
        self.assertEqual(d, [])
        self.assertEqual(a, [])

    def test_self_commitment(self):
        d, a, c = extract_rule("Разработчик A: я подготовлю release-notes по APP-412 до 03.07", EVENT)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].owner, "Разработчик A")
        self.assertEqual(a[0].due, "2026-07-03")
        self.assertEqual(a[0].source, "APP-412")

    def test_addressed_action(self):
        d, a, c = extract_rule("Тимлид: SRE, подтверди деплой до 03.07", EVENT)
        self.assertEqual(a[0].owner, "SRE")
        self.assertEqual(a[0].due, "2026-07-03")

    def test_ownerless_action(self):
        d, a, c = extract_rule("Тимлид: надо бы обновить runbook по инциденту", EVENT)
        self.assertEqual(a[0].owner, "не определён")
        self.assertEqual(a[0].due, "не указан")

    def test_no_due(self):
        d, a, c = extract_rule("Тимлид: SRE, подготовь отчёт по инциденту OPS-78", EVENT)
        self.assertEqual(a[0].due, "не указан")
        self.assertEqual(a[0].source, "OPS-78")

    def test_cancellation(self):
        d, a, c = extract_rule("Тимлид: OPS-77 больше не нужен", EVENT)
        self.assertIn("OPS-77", c)

    def test_today_tomorrow(self):
        d, a, c = extract_rule("Тимлид: SRE, подтверди деплой сегодня", EVENT)
        self.assertEqual(a[0].due, "2026-07-03")
        d, a, c = extract_rule("Тимлид: SRE, подтверди деплой завтра", EVENT)
        self.assertEqual(a[0].due, "2026-07-04")

    def test_distractor_on_then_not_action(self):
        # «на потом» — дистрактор, не поручение
        d, a, c = extract_rule("Разработчик B: предлагаю подумать про автотесты на потом", EVENT)
        self.assertEqual(a, [])

    def test_dogovorili_prefix_stripped(self):
        d, a, c = extract_rule("Тимлид: Договорились: блокер по OPS-77 фиксируем, ответственный SRE", EVENT)
        self.assertEqual(d[0].text, "блокер по OPS-77 фиксируем, ответственный SRE")
        self.assertEqual(d[0].source, "OPS-77")


if __name__ == "__main__":
    unittest.main()
