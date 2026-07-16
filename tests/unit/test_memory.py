"""Unit-тесты аудируемой памяти: парсинг, supersession, отмена, журнал."""
import tempfile
import unittest
from pathlib import Path

from athanor.memory import ReleaseMemory, _same_topic
from athanor.models import ActionItem, Decision


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="memtest-"))
        (self.tmp / "knowledge").mkdir(parents=True, exist_ok=True)
        seed = """# Память релиза · проект «Альфа»

## Решения
- [2026-06-26] Релиз 03.07 в стандартное окно 18:00–20:00 · причина: — · источник: синк 26.06 · статус: действует

## Обязательства
- [ ] SRE: поднять стенд предпрода для OPS-77 · срок 2026-07-02 · источник OPS-77
"""
        (self.tmp / "knowledge" / "release_alfa.md").write_text(seed, encoding="utf-8")

    def test_parse(self):
        mem = ReleaseMemory(self.tmp, "Альфа")
        self.assertEqual(len(mem.decisions), 1)
        self.assertEqual(len(mem.commitments), 1)
        self.assertEqual(mem.commitments[0]["status"], "open")

    def test_supersede_decision(self):
        mem = ReleaseMemory(self.tmp, "Альфа")
        new = [Decision("Откладываем релиз с 03.07 на 05.07", reason="не успеваем", source="APP-412")]
        mem.apply_cycle("2026-07-03", new, [], [])
        self.assertEqual(mem.decisions[0]["status"], "заменено 2026-07-03")
        self.assertEqual(mem.decisions[1]["status"], "действует")
        self.assertIn("заменяет", mem.journal.read_text(encoding="utf-8"))

    def test_cancel_commitment(self):
        mem = ReleaseMemory(self.tmp, "Альфа")
        mem.apply_cycle("2026-07-03", [], [], ["OPS-77"])
        self.assertEqual(mem.commitments[0]["status"], "cancelled")

    def test_dedup_commitment(self):
        mem = ReleaseMemory(self.tmp, "Альфа")
        a = ActionItem("поднять стенд предпрода для OPS-77", "SRE", "2026-07-02", "OPS-77")
        updates = mem.apply_cycle("2026-07-03", [], [a], [])
        self.assertEqual(len(mem.commitments), 1)  # дубль не добавился
        self.assertEqual(updates, [])

    def test_same_topic(self):
        self.assertTrue(_same_topic("Релиз 03.07 в стандартное окно", "Откладываем релиз с 03.07 на 05.07"))
        self.assertFalse(_same_topic("Релиз 03.07", "Автотесты для платёжного шлюза"))


if __name__ == "__main__":
    unittest.main()
