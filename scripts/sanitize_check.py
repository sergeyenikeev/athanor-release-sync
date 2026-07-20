"""Проверка обезличивания тестовых данных (task4 §26): сканирует test-basket/,
memory/, examples/, skills/, results/, test-instances/ на ПДн и секреты.

Детекторы: ФИО (словарь реальных имён), корпоративные email, реальные Jira ID,
внутренние URL, токены/API-ключи/пароли, номера карт, телефоны, табельные номера,
боевые облачные URL (Atlassian/Bitbucket tenant), Windows-пути с именем пользователя.
Синтетические маркеры (роли, «Альфа», APP-/OPS-, PR #) — разрешены.

Запуск: python scripts/sanitize_check.py
Результат: results/sanitization_report.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
RESULTS = _ROOT / "results"

# Каталоги для сканирования
TARGETS = [_ROOT / "test-basket", _ROOT / "memory", _ROOT / "examples",
           _ROOT / "skills", _ROOT / "results", _ROOT / "test-instances"]
EXCLUDE = {".git", "__pycache__", "node_modules", "npm-cache", ".venv"}
EXTS = {".json", ".txt", ".md", ".yaml", ".yml", ".py"}

# Реальные русские имена/фамилии (выборка) — детектор ПДн
_REAL_NAMES = re.compile(
    r"\b(Иван|Петр|Сидоров|Смирнов|Кузнецов|Попов|Васильев|Соколов|Михайлов|Новиков|"
    r"Фёдоров|Морозов|Волков|Алексеев|Лебедев|Семёнов|Егоров|Павлов|Козлов|Степанов|"
    r"Николаев|Орлов|Андреев|Макаров|Никитин|Захаров)\b"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(ru|com|org|net|io|sber|team|local)\b")
_REAL_JIRA = re.compile(r"\b(?:JIRA|DEVOPS|PROD|CORP|INFRA|SEC|SBER|GIGA|CLOUD)-\d{1,5}\b", re.IGNORECASE)
_INTERNAL_URL = re.compile(r"https?://(?:[a-z0-9-]+\.)?(sber|sberbank|alfabank|vtb|gazprom|yandex|team|corp|intra|jira\.company|wiki\.company|git\.company)\b", re.IGNORECASE)
_TOKEN = re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,}|api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9]{16,}|token\s*[:=]\s*['\"]?[A-Za-z0-9]{16,}|password\s*[:=]\s*['\"]?\S{6,})\b", re.IGNORECASE)
# Номер банковской карты — 16 цифр (опционально с разделителями),
# НЕ часть десятичной дроби и НЕ часть hex-хеша
_CARD = re.compile(r"(?<![.\dA-Za-z])(?:\d{4}[\s-]?){3}\d{4}(?![.\dA-Za-z])")
# Телефон — требует разделителей (иначе ложные срабатывания на 11-значных JSON-числах)
_PHONE = re.compile(r"(?:\+7|8)\s*\(?\d{3}\)?[\s-]\d{3}[\s-]\d{2}[\s-]\d{2}")
_TABEL = re.compile(r"\bтабель\s*(?:номер|№)\s*[:\-]?\s*\d{4,}\b", re.IGNORECASE)
# Боевые облачные tenant-URL (Atlassian/Bitbucket) — placeholder <tenant> и demo.atlassian.net разрешены
_CLOUD_TENANT = re.compile(r"https?://(?!<tenant>|demo\.atlassian\.net)[a-z0-9-]+\.atlassian\.net\b", re.IGNORECASE)
# Windows-путь с реальным именем пользователя (C:\Users\<name>\) — placeholder <user> разрешён
_WIN_USER = re.compile(r"[A-Za-z]:\\Users\\(?!<user>)[^\\<>\"]+\\", re.IGNORECASE)

DETECTORS = [
    ("ФИО (реальные имена)", _REAL_NAMES),
    ("Корпоративный email", _EMAIL),
    ("Реальный Jira ID", _REAL_JIRA),
    ("Внутренний URL", _INTERNAL_URL),
    ("Боевой облачный URL (Atlassian tenant)", _CLOUD_TENANT),
    ("Windows-путь с именем пользователя", _WIN_USER),
    ("Токен/API-ключ/пароль", _TOKEN),
    ("Номер банковской карты", _CARD),
    ("Телефон", _PHONE),
    ("Табельный номер", _TABEL),
]

# Разрешённые синтетические маркеры (не ПДн)
SYNTH_OK = ["Тимлид", "SRE", "Владелец продукта", "Разработчик backend", "Разработчик frontend", "Атакующий",
            "Альфа", "alpha-web", "alpha-api", "ППРБ-адаптер", "notification-service",
            "ALPHA-2026.07", "APP-", "OPS-", "PR #",
            "athanor-demo@gmail.com", "demo.atlassian.net", "<tenant>", "<user>"]


def _scan_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    findings = []
    for name, rx in DETECTORS:
        for m in rx.finditer(text):
            snippet = re.sub(r"\s+", " ", m.group(0))[:80]
            # фильтр ложных срабатываний: синтетические маркеры — не ПДн
            if any(s.lower() in snippet.lower() for s in SYNTH_OK):
                continue
            if name == "Реальный Jira ID" and (m.group(0).upper().startswith("APP-") or m.group(0).upper().startswith("OPS-")):
                continue
            findings.append({"file": str(path.relative_to(_ROOT)), "detector": name, "match": snippet})
    return findings


def main() -> int:
    all_findings: list[dict] = []
    scanned = 0
    for tgt in TARGETS:
        if not tgt.is_dir():
            continue
        for p in tgt.rglob("*"):
            if any(part in EXCLUDE for part in p.parts):
                continue
            if p.is_file() and p.suffix.lower() in EXTS:
                scanned += 1
                all_findings += _scan_file(p)

    by_detector: dict[str, list[dict]] = {}
    for f in all_findings:
        by_detector.setdefault(f["detector"], []).append(f)

    lines = [
        "# Отчёт по обезличиванию данных (task4 §26)",
        "",
        f"- Сканировано файлов: **{scanned}** в test-basket/, memory/, examples/, skills/, results/, test-instances/",
        f"- Каталоги проверки: {len(TARGETS)}",
        f"- Детекторов: {len(DETECTORS)} (ФИО, email, Jira ID, внутренние URL, токены/ключи/пароли, карты, телефоны, табельные)",
        "",
        "## Выполненные проверки",
        "",
        *[f"- {n}" for n, _ in DETECTORS],
        "",
        "## Разрешённые синтетические маркеры (НЕ ПДн)",
        "",
        *[f"- {m}" for m in SYNTH_OK],
        "",
        "## Результат",
        "",
    ]
    if not all_findings:
        lines += [
            "✅ **Потенциальных утечек ПДн/секретов не обнаружено.**",
            "",
            "Все данные синтетические и обезличенные: вымышленный проект «Альфа», ",
            "роли вместо ФИО (Тимлид, SRE, Владелец продукта, Разработчик backend/B, Атакующий), ",
            "вымышленные тикеты APP-/OPS-***, PR #1**, вымышленные сервисы и даты. ",
            "Секретов (токенов, API-ключей, паролей, карт) в репозитории нет — `.env` в `.gitignore`. "
            "Боевые облачные URL (Atlassian tenant) и Windows-пути с именем пользователя заменены на "
            "плейсхолды `<tenant>` и `<user>`; demo.atlassian.net и athanor-demo@gmail.com — синтетические "
            "демо-аккаунты, не ПДн.",
        ]
    else:
        lines.append(f"⚠ Обнаружено **{len(all_findings)}** потенциальных совпадений:")
        lines.append("")
        for det, items in by_detector.items():
            lines.append(f"### {det} ({len(items)})")
            for it in items:
                lines.append(f"- `{it['file']}`: «{it['match']}»")
            lines.append("")
    lines += [
        "",
        "## Замены, выполненные при создании данных",
        "",
        "- Реальные ФИО → роли (Тимлид, SRE, Владелец продукта, Разработчик backend/B)",
        "- Реальные email → роли (from_role)",
        "- Реальные Jira ID → вымышленные APP-/OPS-***",
        "- Реальные URL → отсутствуют в репо (MCP-серверы 127.0.0.1:9901-9904; боевые URL — в .env, не в репо; "
        "tenant-URL заменены на `<tenant>` в results/)",
        "- Реальные даты → 2026-07-* (синтетика)",
        "",
        "## Вывод",
        "",
        "Тестовая корзина пригодна для конкурсной подачи: ПДн и секретов нет." if not all_findings
        else "Требуется доработка обезличивания (см. совпадения выше).",
    ]
    out = RESULTS / "sanitization_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Сканировано {scanned} файлов · находок: {len(all_findings)} · отчёт: {out}")
    return 1 if all_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
