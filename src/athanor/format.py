"""Рендеринг результата в markdown. Два формата сводки:

- v1 — исходный (полный порядок секций);
- v2 — после обратной связи пользователя «короче, блокеры и решения сверху»
  (демонстрация версионирования навыка, кейс TB-12; см. skills/release_sync/versions/).
"""

from __future__ import annotations

from .models import RunResult, SummaryItem

_KIND_TITLES = [
    ("conflict", "Конфликты источников"),
    ("blocker", "Блокеры"),
    ("status", "Статусы задач и PR"),
    ("commitment", "Обязательства с прошлого синка"),
    ("question", "Открытые вопросы"),
    ("warning", "Полнота данных"),
]

# v2: блокеры/конфликты сверху, вопросы и статусы свёрнуты до ключевого
_KIND_ORDER_V2 = ["conflict", "blocker", "commitment", "status", "warning"]


def _fmt_item(it: SummaryItem) -> str:
    return f"- {it.text} ({it.source} · {it.confidence:.1f})"


def render_summary(items: list[SummaryItem], profile: str = "v1") -> str:
    lines: list[str] = []
    if profile == "v2":
        lines.append("## Сводка (формат v2 — по обратной связи: блокеры и решения сверху)")
        for kind in _KIND_ORDER_V2:
            got = [it for it in items if it.kind == kind]
            if kind == "status":
                got = got[:3]  # v2: не более трёх статусов, остальное по запросу
            for it in got:
                lines.append(_fmt_item(it))
        return "\n".join(lines)

    lines.append("## Сводка перед релиз-синком")
    for kind, title in _KIND_TITLES:
        got = [it for it in items if it.kind == kind]
        if not got:
            continue
        lines.append(f"\n### {title}")
        lines.extend(_fmt_item(it) for it in got)
    return "\n".join(lines)


def render_result(res: RunResult) -> str:
    parts: list[str] = [f"# Прогон {res.case_id} · движок {res.engine} · формат {res.format_profile}", ""]
    parts.append(render_summary(res.summary_items, res.format_profile))

    if res.decisions:
        parts += ["", "## Решения (из расшифровки)"]
        for d in res.decisions:
            reason = f" · причина: {d.reason}" if d.reason else ""
            parts.append(f"- {d.text}{reason} · источник: {d.source}")

    if res.actions:
        parts += ["", "## Поручения"]
        parts += [a.as_line() for a in res.actions]

    if res.blockers:
        parts += ["", "## Блокеры (структурированно)"]
        for b in res.blockers:
            parts.append(
                f"- {b.id} [{b.severity}] {b.description} "
                f"· источник: {b.source_evidence} · уверенность {b.confidence:.1f} · {b.resolution_status}"
            )

    if res.drafts:
        parts += ["", "## Черновики (ожидают подтверждения человека — HITL)"]
        parts += [f"- {d['id']}: {d['subject']} → {d['to_role']} · статус {d['status']}" for d in res.drafts]

    if res.memory_updates:
        parts += ["", "## Обновления памяти релиза"]
        parts += [f"- {u}" for u in res.memory_updates]

    if res.security_flags:
        parts += ["", "## Безопасность"]
        parts += [f"- ⚠ {f}" for f in res.security_flags]

    if res.warnings:
        parts += ["", "## Предупреждения"]
        parts += [f"- {w}" for w in res.warnings]

    parts += [
        "",
        f"_Время цикла: {res.elapsed_seconds:.1f} с · LLM-вызовов: {res.llm_calls} "
        f"· навык: {res.skill_version} · движок: {res.engine}_",
        "",
    ]
    return "\n".join(parts)
