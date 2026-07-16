"""Rule-baseline: извлечение решений и поручений из расшифровки без LLM.

Назначение: (а) офлайн-запуск харнесса и CI без ключей; (б) нижняя граница
качества для сравнения с LLM-движком. Метрики Project Results снимаются
с LLM-движка; rule-baseline в отчёте помечается отдельно.
"""

from __future__ import annotations

import datetime as dt
import re

from .models import DUE_NOT_SET, OWNER_NOT_SET, ActionItem, Decision

_LINE_RX = re.compile(r"^\s*(?P<role>[^:]{2,40}?)\s*:\s*(?P<text>.+)$")
# Ключ задачи (APP-412). Негативный lookahead «не за цифрой через точку» отбраковывает
# идентификаторы релизов вида ALPHA-2026.07, которые формально похожи на ключ (task4 СЦ-09/10).
_ISSUE_KEY_RX = re.compile(r"\b([A-Z]{2,5}-\d{1,5})\b(?!\.\d)")

# Маркеры решения (утверждённого), НЕ идеи
_DECISION_RX = re.compile(
    r"^(решение\s*[—:-]|решили|договорились|фиксируем|утверждаем|переносим|откладываем|отменяем)",
    re.IGNORECASE,
)
# Дистракторы-«идеи» — не решения и не поручения
_IDEA_RX = re.compile(
    r"идея|может\s+быть,?\s+стоит|предлагаю\s+подумать|на\s+потом|как\s+вариант|когда-нибудь",
    re.IGNORECASE,
)
# Первое лицо: говорящий берёт обязательство на себя
_SELF_COMMIT_RX = re.compile(
    r"^(я\s+)?(подготовлю|сделаю|проверю|подтвержу|задеплою|соберу|опишу|обновлю|созвонюсь|напишу|беру\s+на\s+себя)"
    r"|(\bна\s+мне\b)",
    re.IGNORECASE,
)
# Обращение: «SRE, подтверди деплой …» / «Разработчик A, за тобой …»
_ADDRESSED_RX = re.compile(
    r"^(?P<addressee>[А-ЯA-Z][^,]{1,30}?),\s*(?P<rest>(за\s+тобой\b|подтверди|подготовь|проверь|задеплой|собери|обнови|опиши|напиши).*)$",
    re.IGNORECASE,
)
# Безадресное долженствование → владелец «не определён»
_OWNERLESS_RX = re.compile(
    r"^(надо\s+бы|нужно\s+бы|надо|нужно|необходимо|стоит)\s+(?P<rest>.+)$", re.IGNORECASE
)
_DUE_RX = re.compile(r"\b(?:до|к)\s+(\d{1,2})\.(\d{2})\b")
_CANCEL_RX = re.compile(r"(?P<key>[A-Z]{2,5}-\d{1,5})\s+больше\s+не\s+нужен|отменяем\s+(?P<key2>[A-Z]{2,5}-\d{1,5})", re.IGNORECASE)


def _parse_due(text: str, event_date: str | None) -> str:
    m = _DUE_RX.search(text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(event_date.split("-")[0]) if event_date else 2026
        return f"{year:04d}-{month:02d}-{day:02d}"
    low = text.lower()
    if event_date:
        base = dt.date.fromisoformat(event_date)
        if "сегодня" in low:
            return base.isoformat()
        if "завтра" in low:
            return (base + dt.timedelta(days=1)).isoformat()
    return DUE_NOT_SET


def _source_of(text: str, event_date: str | None) -> str:
    keys = _ISSUE_KEY_RX.findall(text)
    if keys:
        return keys[0]
    if event_date:
        d = dt.date.fromisoformat(event_date)
        return f"расшифровка синка {d.day:02d}.{d.month:02d}"
    return "расшифровка синка"


def _strip_due_tail(text: str) -> str:
    """Убрать хвост со сроком из текста действия («… до 03.07» → «…»)."""
    return _DUE_RX.sub("", text).rstrip(" ,.;—-")


def extract_rule(transcript: str, event_date: str | None) -> tuple[list[Decision], list[ActionItem], list[str]]:
    """Вернуть (решения, поручения, отмены OPS/APP-ключей)."""
    decisions: list[Decision] = []
    actions: list[ActionItem] = []
    cancellations: list[str] = []

    for raw in transcript.splitlines():
        m = _LINE_RX.match(raw)
        if not m:
            continue
        role, text = m.group("role").strip(), m.group("text").strip()

        cm = _CANCEL_RX.search(text)
        if cm:
            cancellations.append(cm.group("key") or cm.group("key2"))

        if _IDEA_RX.search(text):
            continue  # идеи-дистракторы: не решение и не поручение

        if _DECISION_RX.search(text):
            reason = ""
            rm = re.search(r"(?:из-за|потому\s+что|причина\s*[:—-])\s*(.+)$", text, re.IGNORECASE)
            if rm:
                reason = rm.group(1).strip().rstrip(".")
            body = re.sub(r"^решение\s*[—:-]\s*", "", text, flags=re.IGNORECASE).strip()
            # убрать рамочные префиксы решения (смысл глагола «откладываем/переносим» оставляем)
            body = re.sub(r"^(договорились|фиксируем|утверждаем|решили)\s*[—:-]?\s*", "", body, flags=re.IGNORECASE).strip()
            # убрать хвост причины из текста решения (причина живёт в отдельном поле)
            body = re.sub(r"\s*(?:из-за|потому\s+что|причина\s*[:—-])\s*.+$", "", body, flags=re.IGNORECASE).strip().rstrip(",.;—-")
            decisions.append(Decision(text=body, reason=reason, source=_source_of(text, event_date)))
            continue

        am = _ADDRESSED_RX.match(text)
        if am:
            rest = am.group("rest")
            rest = re.sub(r"^за\s+тобой\s+", "", rest, flags=re.IGNORECASE)
            actions.append(
                ActionItem(
                    action=_strip_due_tail(rest).strip().rstrip("."),
                    owner=am.group("addressee").strip(),
                    due=_parse_due(text, event_date),
                    source=_source_of(text, event_date),
                )
            )
            continue

        if _SELF_COMMIT_RX.search(text):
            body = re.sub(r"^я\s+", "", text, flags=re.IGNORECASE)
            body = re.sub(r"\s*\bна\s+мне\b\s*", " ", body, flags=re.IGNORECASE)
            actions.append(
                ActionItem(
                    action=_strip_due_tail(body).strip().rstrip("."),
                    owner=role,
                    due=_parse_due(text, event_date),
                    source=_source_of(text, event_date),
                )
            )
            continue

        om = _OWNERLESS_RX.match(text)
        if om and not _IDEA_RX.search(text):
            actions.append(
                ActionItem(
                    action=_strip_due_tail(om.group("rest")).strip().rstrip("."),
                    owner=OWNER_NOT_SET,
                    due=_parse_due(text, event_date),
                    source=_source_of(text, event_date),
                )
            )

    return decisions, actions, cancellations
