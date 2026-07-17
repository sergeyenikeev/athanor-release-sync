# -*- coding: utf-8 -*-
"""Генератор live-кейса: Jira — реальная Cloud (KAN-ключи), остальное — файлы.

Создаёт examples/demo_case_alpha_live/ с ключами из results/atlassian_seeded_keys.json:
календарь, письмо-блокер (ссылка на KAN-done), расшифровка, память, PR (issue_key=KAN-done).
Jira-задачи НЕ в файле — их отдаёт реальная Jira через MCP (MCP_BACKEND=atlassian).

Запуск: python test-instances/gen_live_case.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
keys = json.loads((REPO / "results" / "atlassian_seeded_keys.json").read_text(encoding="utf-8"))
DONE_KEY = keys["done"]       # KAN-1 (Готово)
PROG_KEY = keys["in_progress"]  # KAN-2 (К выполнению)

OUT = REPO / "examples" / "demo_case_alpha_live"
(OUT / "input").mkdir(parents=True, exist_ok=True)

# meta — формат v2 (по обратной связи: блокеры сверху), transcripts_down=false, seed=true
(OUT / "meta.json").write_text(json.dumps({
    "id": "DEMO-ALPHA-LIVE",
    "type": "Сквозной демо-сценарий: Jira — реальная Cloud (KAN), остальное — обезличенные выгрузки",
    "checks": ["сводка из нескольких источников", "конфликт Jira ↔ письмо",
               "блокер payment-adapter", "решение и два поручения", "черновики HITL",
               "обновление памяти релиза"],
    "format": "v2", "transcripts_down": False, "seed": True,
}, ensure_ascii=False, indent=2), encoding="utf-8")

# calendar — релиз-синк Альфа 03.07
(OUT / "input" / "calendar.json").write_text(json.dumps({
    "events": [{
        "id": "DEMO-ALPHA-LIVE", "title": "Релиз-синк · Альфа", "project": "Альфа",
        "datetime": "2026-07-03T14:00",
        "participants": ["Тимлид", "SRE", "Владелец продукта", "Разработчик backend", "Разработчик frontend"],
    }],
}, ensure_ascii=False, indent=2), encoding="utf-8")

# mail — блокер по KAN-done (смежный сервис не в prod) → конфликт с Jira «Готово»
(OUT / "input" / "mail.json").write_text(json.dumps({
    "messages": [{
        "id": "M1", "from_role": "SRE", "date": "2026-07-02",
        "subject": f"Блокер по {DONE_KEY}: payment-adapter не в prod",
        "body": f"{DONE_KEY}: смежный сервис payment-adapter не задеплоен в production, "
                f"релизное окно под риском, деплой заблокирован.",
    }],
}, ensure_ascii=False, indent=2), encoding="utf-8")

# tracker — только PR (issue_key=KAN-done); задачи придут из реальной Jira
(OUT / "input" / "tracker.json").write_text(json.dumps({
    "issues": [],  # MCP_BACKEND=atlassian отдаёт реальные KAN-1/KAN-2
    "prs": [{
        "number": 128, "title": "Схема оплат", "status": "на ревью",
        "review_days": 2, "issue_key": DONE_KEY,
    }],
}, ensure_ascii=False, indent=2), encoding="utf-8")

# confluence — release plan / decision log (файловый fallback; при MCP_BACKEND=live
# боевые страницы придут из реальной Confluence Cloud через MCP_BACKEND_CONFLUENCE=atlassian)
(OUT / "input" / "confluence.json").write_text(json.dumps({
    "pages": [
        {
            "id": "196612", "title": "Release Plan · Альфа", "space": "ALPHA",
            "excerpt": f"Целевое окно 03.07 18:00–20:00. Code freeze с 02.07 12:00. "
            f"Зависимость: payment-adapter (владелец SRE), partner-api. Release-notes по {DONE_KEY}.",
            "url": f"http://demo.atlassian.net/wiki/spaces/ALPHA/pages/196612",
            "version": 3, "updated_at": "2026-07-01",
        },
        {
            "id": "196613", "title": "Decision Log · Альфа", "space": "ALPHA",
            "excerpt": f"26.06: согласовано окно 18:00–20:00 (пятница исключена по регламенту). "
            f"30.06: {DONE_KEY} «Миграция схемы оплат» — принято в релиз 03.07.",
            "url": f"http://demo.atlassian.net/wiki/spaces/ALPHA/pages/196613",
            "version": 5, "updated_at": "2026-06-30",
        },
    ],
}, ensure_ascii=False, indent=2), encoding="utf-8")

# transcript — решение + 2 поручения (ссылки на KAN-done)
(OUT / "input" / "transcript.txt").write_text(
    "Тимлид: Решение: выкатываем релиз 03.07 в окно 18:00–20:00, потому что регламентное окно\n"
    f"Разработчик backend: я подготовлю release-notes по {DONE_KEY} до 03.07\n"
    "Тимлид: SRE, подтверди деплой payment-adapter до 03.07\n",
    encoding="utf-8")

# memory_seed — предыдущее обязательство
(OUT / "input" / "memory_seed.md").write_text(
    "# Память релиза · проект «Альфа»\n\n"
    "## Решения\n"
    "- [2026-06-26] Релиз 03.07 в стандартное окно 18:00–20:00 · причина: пятница исключена по регламенту · источник: синк 26.06 · статус: действует\n\n"
    "## Обязательства\n"
    "- [ ] SRE: подтвердить готовность стенда предпрода · срок 2026-07-01 · источник OPS-70\n"
    "- [x] Разработчик backend: закрыть APP-410 (миграция схемы) · срок 2026-06-27 · источник APP-410\n",
    encoding="utf-8")

print(f"live-кейс создан: {OUT}")
print(f"  Jira (live Cloud): {DONE_KEY} [Готово], {PROG_KEY} [К выполнению] — через MCP_BACKEND=live")
print(f"  письмо-блокер ссылается на {DONE_KEY} → конфликт Jira «Готово» ↔ письмо «блокер»")
print(f"  PR #128 → issue_key={DONE_KEY}")
print(f"\nС live-бэкендом календарь+почта — из реального Outlook.com (MCP_BACKEND_CALENDAR/MAIL=microsoft),")
print(f"Jira — из Cloud (atlassian), PR/расшифровка — файлы кейса.")
print(f"\nПрогон:")
print(f"  MCP_BACKEND=live python mcp/serve_all.py   # терминал 1 (Jira + Outlook через MCP)")
print(f"  MCP_BACKEND=live python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp --engine rule --print")
