"""Аудируемая память релизов: memory/knowledge/release_<project>.md + журнал.

Формат файла — структурированный markdown, который читают и человек, и код:

    # Память релиза · проект «Альфа»

    ## Решения
    - [2026-06-26] Релиз 03.07 в стандартное окно · причина: — · источник: синк 26.06 · статус: действует

    ## Обязательства
    - [ ] SRE: подтвердить деплой · срок 2026-07-03 · источник OPS-77
    - [x] Разработчик backend: закрыть APP-410 · срок 2026-06-27 · источник APP-410
    - [отменено] SRE: поднять стенд · срок не указан · источник OPS-77

Каждое изменение дописывается в memory/journal.log (аудит: кто/что/когда/почему).
Изменения видны в git-диффах — это и есть «аудируемая память» из Proposal.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .models import ActionItem, Decision

_COMMIT_RX = re.compile(
    r"^- \[(?P<mark>[ x]|отменено)\]\s*(?P<owner>[^:]+):\s*(?P<action>.+?)"
    r"\s*·\s*срок\s+(?P<due>[^·]+?)\s*·\s*источник\s+(?P<source>.+?)\s*$"
)
_DECISION_RX = re.compile(
    r"^- \[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?P<text>.+?)\s*·\s*причина:\s*(?P<reason>[^·]*?)"
    r"\s*·\s*источник:\s*(?P<source>[^·]+?)\s*·\s*статус:\s*(?P<status>.+?)\s*$"
)

_MARK_TO_STATUS = {" ": "open", "x": "done", "отменено": "cancelled"}
_STATUS_TO_MARK = {v: k for k, v in _MARK_TO_STATUS.items()}


def _slug(project: str) -> str:
    table = str.maketrans("абвгдежзийклмнопрстуфхцчшщъыьэюя", "abvgdejzijklmnoprstufhccss_y_eua")
    s = project.lower().translate(table)
    s = s.replace("_", "")  # убираем мягкий/твёрдый знаки (были _), напр. «Альфа» → alfa
    return re.sub(r"[^a-z0-9]+", "", s) or "project"


class ReleaseMemory:
    """Память одного проекта. memory_dir — корень memory/ рабочего пространства."""

    def __init__(self, memory_dir: Path, project: str):
        self.memory_dir = Path(memory_dir)
        self.project = project
        self.path = self.memory_dir / "knowledge" / f"release_{_slug(project)}.md"
        self.journal = self.memory_dir / "journal.log"
        self.decisions: list[dict] = []
        self.commitments: list[dict] = []
        self._load()

    # ------------------------------------------------------------- parsing
    def _load(self) -> None:
        if not self.path.is_file():
            return
        section = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip().lower()
                continue
            if section.startswith("решения"):
                m = _DECISION_RX.match(line)
                if m:
                    self.decisions.append(
                        {
                            "date": m.group("date"),
                            "text": m.group("text").strip(),
                            "reason": m.group("reason").strip() or "—",
                            "source": m.group("source").strip(),
                            "status": m.group("status").strip(),
                        }
                    )
            elif section.startswith("обязательства"):
                m = _COMMIT_RX.match(line)
                if m:
                    self.commitments.append(
                        {
                            "owner": m.group("owner").strip(),
                            "action": m.group("action").strip(),
                            "due": m.group("due").strip(),
                            "source": m.group("source").strip(),
                            "status": _MARK_TO_STATUS[m.group("mark")],
                        }
                    )

    # ------------------------------------------------------------ mutation
    def apply_cycle(
        self,
        run_date: str,
        decisions: list[Decision],
        actions: list[ActionItem],
        cancellations: list[str],
    ) -> list[str]:
        """Применить результаты цикла; вернуть список строк для журнала/отчёта."""
        updates: list[str] = []

        for d in decisions:
            superseded = None
            for old in self.decisions:
                if old["status"] == "действует" and _same_topic(old["text"], d.text):
                    old["status"] = f"заменено {run_date}"
                    superseded = old
            self.decisions.append(
                {
                    "date": run_date,
                    "text": d.text,
                    "reason": d.reason or "—",
                    "source": d.source or f"синк {run_date}",
                    "status": "действует",
                }
            )
            note = f"решение: «{d.text}»" + (f" (заменяет: «{superseded['text']}»)" if superseded else "")
            updates.append(note)

        for a in actions:
            if not any(
                c["action"] == a.action and c["owner"] == a.owner for c in self.commitments
            ):
                self.commitments.append(
                    {
                        "owner": a.owner,
                        "action": a.action,
                        "due": a.due,
                        "source": a.source or f"синк {run_date}",
                        "status": "open",
                    }
                )
                updates.append(f"обязательство: {a.owner} — «{a.action}» · срок {a.due}")

        for key in cancellations:
            for c in self.commitments:
                if c["status"] == "open" and key.lower() in c["source"].lower():
                    c["status"] = "cancelled"
                    updates.append(f"отменено обязательство по {key}: «{c['action']}» ({c['owner']})")

        self._save()
        self._journal(run_date, updates)
        return updates

    # ------------------------------------------------------------- output
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Память релиза · проект «{self.project}»", ""]
        lines.append("## Решения")
        for d in self.decisions:
            lines.append(
                f"- [{d['date']}] {d['text']} · причина: {d['reason']} "
                f"· источник: {d['source']} · статус: {d['status']}"
            )
        lines += ["", "## Обязательства"]
        for c in self.commitments:
            mark = _STATUS_TO_MARK[c["status"]]
            lines.append(
                f"- [{mark}] {c['owner']}: {c['action']} · срок {c['due']} · источник {c['source']}"
            )
        lines.append("")
        self.path.write_text("\n".join(lines), encoding="utf-8")

    def _journal(self, run_date: str, updates: list[str]) -> None:
        if not updates:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().isoformat(timespec="seconds")
        with self.journal.open("a", encoding="utf-8") as f:
            for u in updates:
                f.write(f"{stamp} · {self.project} · {run_date} · {u}\n")


def _same_topic(old: str, new: str) -> bool:
    """Грубая проверка «то же решение, новая версия»: пересечение значимых слов ≥ 50%."""
    tok = lambda s: {w[:5] for w in re.findall(r"[а-яa-z0-9]{4,}", s.lower())}
    a, b = tok(old), tok(new)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.5
