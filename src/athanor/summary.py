"""Детерминированная сборка сводки перед релиз-синком.

Сводка НЕ генерируется LLM: статусы, блокеры, конфликты и обязательства
агрегируются кодом из структурированных источников, у каждого пункта —
источник и уверенность. LLM применяется только к расшифровке (extract.py).
Это осознанное разделение: язык — модели, факты — детерминированному коду.
"""

from __future__ import annotations

import re

from .models import CONFIDENCE, CaseInput, SummaryItem

# Статусы задач, означающие «сделано» (для поиска конфликтов с письмами)
_DONE_STATUSES = {"готово", "готово к релизу", "закрыто", "done", "released"}

# Ключевые слова блокера в письмах
_BLOCKER_RX = re.compile(
    r"блокер|заблокирован|не\s+задеплоен|недоступен|падает|срываем|критично", re.IGNORECASE
)
_QUESTION_RX = re.compile(r"вопрос|уточнить|подтвердите\s+пожалуйста|\?", re.IGNORECASE)
_ISSUE_KEY_RX = re.compile(r"\b([A-Z]{2,5}-\d{1,5})\b(?!\.\d)")


def build_summary(case: CaseInput, memory_commitments: list[dict] | None = None) -> list[SummaryItem]:
    items: list[SummaryItem] = []
    memory_commitments = memory_commitments or []

    # 1) Статусы задач и PR (Jira/Git · 0.9)
    for issue in case.issues:
        items.append(
            SummaryItem(
                text=f"{issue.key} «{issue.title}» — {issue.status} (исп.: {issue.assignee_role})",
                source=f"Jira {issue.key}",
                confidence=CONFIDENCE["jira"],
                kind="status",
            )
        )
    for pr in case.prs:
        linked = f" по {pr.issue_key}" if pr.issue_key else ""
        days = f", на ревью {pr.review_days} дн." if pr.review_days else ""
        items.append(
            SummaryItem(
                text=f"PR #{pr.number} «{pr.title}»{linked} — {pr.status}{days}",
                source=f"Git PR#{pr.number}",
                confidence=CONFIDENCE["git"],
                kind="status",
            )
        )

    # 2) Блокеры из писем (письмо · 0.7)
    blocker_mails = [m for m in case.mails if _BLOCKER_RX.search(m.subject + " " + m.body)]
    for m in blocker_mails:
        items.append(
            SummaryItem(
                text=f"Блокер из письма ({m.from_role}, {m.date}): {m.subject}",
                source=f"письмо {m.id} от {m.date}",
                confidence=CONFIDENCE["mail"],
                kind="blocker",
            )
        )

    # 3) Конфликты источников: задача «готова», а письмо сообщает о блокере
    done_keys = {i.key for i in case.issues if i.status.strip().lower() in _DONE_STATUSES}
    for m in blocker_mails:
        seen_keys: set[str] = set()
        for key in _ISSUE_KEY_RX.findall(m.subject + " " + m.body):
            if key in seen_keys:
                continue  # не плодить дубль-конфликт на повторном вхождении ключа
            seen_keys.add(key)
            if key in done_keys:
                items.append(
                    SummaryItem(
                        text=(
                            f"⚠ КОНФЛИКТ по {key}: Jira — «готово» ↔ письмо {m.date} — «блокер». "
                            f"Приоритет источников: Git/Jira > переписка; требуется решение человека"
                        ),
                        source=f"Jira {key} ↔ письмо {m.id}",
                        confidence=CONFIDENCE["transcript"],  # 0.6 — конфликт снижает уверенность
                        kind="conflict",
                    )
                )

    # 4) Открытые вопросы из писем
    for m in case.mails:
        if m in blocker_mails:
            continue
        if _QUESTION_RX.search(m.subject + " " + m.body):
            items.append(
                SummaryItem(
                    text=f"Открытый вопрос ({m.from_role}, {m.date}): {m.subject}",
                    source=f"письмо {m.id} от {m.date}",
                    confidence=CONFIDENCE["mail"],
                    kind="question",
                )
            )

    # 5) Обязательства с прошлого синка (память · 0.8); отменённые не напоминаем
    for c in memory_commitments:
        status = c.get("status", "open")
        if status == "cancelled":
            continue
        mark = "✔ выполнено: " if status == "done" else ""
        items.append(
            SummaryItem(
                text=f"{mark}{c['owner']}: {c['action']} · срок {c['due']}",
                source=f"память релиза · {c.get('source', 'синк')}",
                confidence=CONFIDENCE["memory"],
                kind="commitment",
            )
        )

    # 6) Деградация без падения: источник недоступен / данных нет
    for src in case.sources_down:
        items.append(
            SummaryItem(
                text=f"Источник «{src}» недоступен — данные неполны; повторю запрос при следующем прогоне",
                source="самодиагностика",
                confidence=1.0,
                kind="warning",
            )
        )
    if not case.issues and "tracker_repo" not in case.sources_down:
        items.append(
            SummaryItem(
                text="Трекер вернул пустой список задач — сводка может быть неполной",
                source="самодиагностика",
                confidence=1.0,
                kind="warning",
            )
        )
    return items
