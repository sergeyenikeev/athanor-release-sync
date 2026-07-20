"""Unit-тесты CLI-команд HITL: approve/reject/edit/comment.

Проверяет, что subparsers корректно вызывают hitl.* и меняют статус черновика,
а также что approve --execute переводит в executed, а попытка исполнить
неподтверждённый черновик через approve (без --execute) не исполняет."""
import json
import tempfile
import unittest
from pathlib import Path

from athanor.cli import main as cli_main
from athanor.hitl import APPROVED, AWAITING, EXECUTED, REJECTED, make_drafts
from athanor.models import ActionItem


class TestCliHitl(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="cli-hitl-")) / "outbox"
        a = ActionItem("деплой ППРБ-адаптера", "SRE", "2026-07-18", "OPS-104")
        d = make_drafts([a], self.out, "CLI")[0]
        self.draft_path = self.out / f"{d['id']}.json"

    def _read(self) -> dict:
        return json.loads(self.draft_path.read_text(encoding="utf-8"))

    def test_approve(self):
        rc = cli_main(["approve", "--draft", str(self.draft_path)])
        self.assertEqual(rc, 0)
        self.assertEqual(self._read()["status"], APPROVED)

    def test_approve_execute(self):
        rc = cli_main(["approve", "--draft", str(self.draft_path), "--execute"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._read()["status"], EXECUTED)

    def test_reject(self):
        rc = cli_main(["reject", "--draft", str(self.draft_path), "--reason", "неактуально"])
        self.assertEqual(rc, 0)
        d = self._read()
        self.assertEqual(d["status"], REJECTED)
        self.assertEqual(d["reject_reason"], "неактуально")

    def test_reject_no_reason(self):
        rc = cli_main(["reject", "--draft", str(self.draft_path)])
        self.assertEqual(rc, 0)
        self.assertEqual(self._read()["status"], REJECTED)
        self.assertNotIn("reject_reason", self._read())

    def test_edit_subject_body(self):
        rc = cli_main(["edit", "--draft", str(self.draft_path),
                       "--subject", "новая тема", "--body", "новой текст"])
        self.assertEqual(rc, 0)
        d = self._read()
        self.assertEqual(d["subject"], "новая тема")
        self.assertEqual(d["body"], "новой текст")
        self.assertEqual(d["status"], AWAITING)  # правка не меняет статус

    def test_edit_to_role_due(self):
        rc = cli_main(["edit", "--draft", str(self.draft_path),
                       "--to-role", "QA", "--due", "2026-07-25"])
        self.assertEqual(rc, 0)
        d = self._read()
        self.assertEqual(d["to_role"], "QA")
        self.assertEqual(d["due"], "2026-07-25")

    def test_edit_no_fields_returns_2(self):
        rc = cli_main(["edit", "--draft", str(self.draft_path)])
        self.assertEqual(rc, 2)
        self.assertEqual(self._read()["status"], AWAITING)  # ничего не сломал

    def test_comment(self):
        rc = cli_main(["comment", "--draft", str(self.draft_path), "--text", "проверить срок"])
        self.assertEqual(rc, 0)
        d = self._read()
        self.assertEqual(len(d["comments"]), 1)
        self.assertEqual(d["comments"][0]["text"], "проверить срок")

    def test_double_approve_fails(self):
        cli_main(["approve", "--draft", str(self.draft_path)])
        with self.assertRaises(ValueError):
            cli_main(["approve", "--draft", str(self.draft_path)])


if __name__ == "__main__":
    unittest.main()
