# -*- coding: utf-8 -*-
"""Рендер сцен финального ДЕМО-видео из реальных артефактов прогона."""
from __future__ import annotations

import json

from PIL import Image, ImageDraw

from common import *

# content vertical band
TOP, BOTTOM = 92, 984

def _scene(fn, step, total, tag, cap, cap_color=BLUE):
    img, d = new_canvas()
    topbar(d, step, total, tag)
    fn(d)
    caption(d, cap, cap_color)
    return img

def _anim_scene(fn, step, total, tag, cap, cap_color, frame_idx, frame_count):
    """Сцена с анимацией: fn(d, frame_idx, frame_count) рисует прогрессивно."""
    img, d = new_canvas()
    topbar(d, step, total, tag)
    fn(d, frame_idx, frame_count)
    caption(d, cap, cap_color)
    return img

# ============================================================== UI реальных инструментов
# Реалистичные UI-кадры реальных систем на реальных данных демо-контура (Альфа).

def _tool_header(d, box, title, subtitle, accent, icon=""):
    """Шапка окна инструмента: цветной акцент + title + subtitle (как вкладка)."""
    x0, y0, x1, y1 = box
    panel(d, box, fill=(255, 255, 255), radius=12, border=LINE)
    d.rounded_rectangle([x0, y0, x1, y0 + 46], radius=12, fill=(248, 250, 252))
    d.rectangle([x0, y0 + 34, x1, y0 + 46], fill=(248, 250, 252))
    d.rounded_rectangle([x0, y0, x0 + 6, y1], radius=3, fill=accent)
    tx = x0 + 22
    if icon:
        d.text((tx, y0 + 12), icon, font=F_H(20), fill=accent)
        tx += 30
    d.text((tx, y0 + 13), title, font=F_H(20), fill=INK)
    sw = d.textlength(subtitle, font=F_MONO(15))
    d.text((x1 - sw - 16, y0 + 16), subtitle, font=F_MONO(15), fill=GREY)

def _status_pill(d, x, y, text, color):
    f = F_SMALL(17)
    w = d.textlength(text, font=f) + 22
    d.rounded_rectangle([x, y, x + w, y + 26], radius=13, fill=color)
    d.text((x + 11, y + 4), text, font=f, fill=(255, 255, 255))
    return w

def jira_ui(d, box, key, title, status, assignee, status_color=GREEN):
    _tool_header(d, box, "Jira · " + key, "demo.atlassian.net/browse/" + key, BLUE, "🔷")
    x0, y0, x1, y1 = box
    y = y0 + 62
    d.text((x0 + 22, y), key, font=F_H(30), fill=BLUE)
    _status_pill(d, x0 + 22 + d.textlength(key, F_H(30)) + 16, y + 6, status, status_color)
    y += 50
    d.text((x0 + 22, y), title, font=F_TITLE(24), fill=INK)
    y += 42
    for k, v in (("Тип", "Задание"), ("Исполнитель", assignee), ("Проект", "ALPHA · Альфа"),
                 ("Приоритет", "Высокий")):
        d.text((x0 + 22, y), k, font=F_BODY(18), fill=INK2)
        d.text((x0 + 180, y), v, font=F_BODY(19), fill=INK)
        y += 30

def confluence_ui(d, box, title, space, excerpt, version, updated):
    _tool_header(d, box, "Confluence", "demo.atlassian.net/wiki/spaces/" + space, TEAL, "📄")
    x0, y0, x1, y1 = box
    y = y0 + 60
    d.text((x0 + 22, y), space + "  ›  Pages", font=F_MONO(16), fill=GREY)
    y += 28
    d.text((x0 + 22, y), title, font=F_TITLE(26), fill=INK)
    y += 40
    d.text((x0 + 22, y), f"v{version} · обновлено {updated}", font=F_SMALL(16), fill=INK2)
    y += 28
    d.line([x0 + 22, y, x1 - 22, y], fill=LINE, width=1)
    y += 14
    for i, ln in enumerate(wrap(d, excerpt, F_BODY(19), (x1 - x0) - 44)):
        if i > 8:
            break
        d.text((x0 + 22, y + i * 26), ln, font=F_BODY(19), fill=INK)

def mail_ui(d, box, from_role, date, subject, body):
    _tool_header(d, box, "mail", "mail.google.com/inbox", AMBER, "✉")
    x0, y0, x1, y1 = box
    y = y0 + 60
    d.text((x0 + 22, y), subject, font=F_H(22), fill=INK)
    y += 36
    d.text((x0 + 22, y), "От:", font=F_BODY(17), fill=INK2)
    d.text((x0 + 80, y), from_role, font=F_BODY(19), fill=INK)
    d.text((x0 + 320, y), "Дата:", font=F_BODY(17), fill=INK2)
    d.text((x0 + 390, y), date, font=F_BODY(19), fill=INK)
    y += 30
    d.line([x0 + 22, y, x1 - 22, y], fill=LINE, width=1)
    y += 14
    for i, ln in enumerate(wrap(d, body, F_BODY(18), (x1 - x0) - 44)):
        if i > 7:
            break
        d.text((x0 + 22, y + i * 25), ln, font=F_BODY(18), fill=INK)

def calendar_ui(d, box, title, datetime, participants):
    _tool_header(d, box, "Calendar", "calendar.google.com", BLUE, "📅")
    x0, y0, x1, y1 = box
    y = y0 + 62
    d.text((x0 + 22, y), title, font=F_TITLE(24), fill=INK)
    y += 42
    d.text((x0 + 22, y), "Когда:", font=F_BODY(17), fill=INK2)
    d.text((x0 + 100, y), datetime, font=F_BODY(20), fill=INK)
    y += 30
    d.text((x0 + 22, y), "Участники:", font=F_BODY(17), fill=INK2)
    d.text((x0 + 130, y), ", ".join(participants), font=F_BODY(19), fill=INK)
    y += 34
    d.line([x0 + 22, y, x1 - 22, y], fill=LINE, width=1)
    y += 14
    d.text((x0 + 22, y), "Релиз ALPHA-2026.07", font=F_BODY(19), fill=INK2)

def bitbucket_ui(d, box, number, title, status, issue_key, review_days):
    _tool_header(d, box, "Bitbucket", "demo.bitbucket.org/pull-requests/" + str(number), TEAL, "🔀")
    x0, y0, x1, y1 = box
    y = y0 + 62
    d.text((x0 + 22, y), f"PR #{number}", font=F_H(28), fill=TEAL)
    _status_pill(d, x0 + 22 + d.textlength(f"PR #{number}", F_H(28)) + 16, y + 6, status, AMBER)
    y += 46
    d.text((x0 + 22, y), title, font=F_TITLE(22), fill=INK)
    y += 40
    for k, v in (("Задача", issue_key), ("Ветка", "feature/payment-schema → main"),
                 ("На ревью", f"{review_days} дн."), ("Автор", "Разработчик backend")):
        d.text((x0 + 22, y), k, font=F_BODY(18), fill=INK2)
        d.text((x0 + 160, y), v, font=F_BODY(19), fill=INK)
        y += 30

# ============================================================== F1 ПРОБЛЕМА
def f1_title(d):
    # центральный титул
    cx = W // 2
    d.text((cx - d.textlength("Ouroboros — мозг команды", font=F_TITLE(64)) / 2, 300),
           "Ouroboros — мозг команды", font=F_TITLE(64), fill=TEAL)
    sub = "ИИ-агент подготовки к релиз-синкам и разбору инцидентов"
    d.text((cx - d.textlength(sub, font=F_H(32)) / 2, 400), sub, font=F_H(32), fill=(226, 232, 240))
    sub2 = "Команда «Атанор» · Sber AI Hack · Основной этап"
    d.text((cx - d.textlength(sub2, font=F_BODY(26)) / 2, 470), sub2, font=F_BODY(26), fill=GREY)
    # нижняя строка-тезис
    thesis = "аудируемая память релизов · управляемая автономия · Ouroboros"
    d.text((cx - d.textlength(thesis, font=F_BODY(24)) / 2, 760), thesis, font=F_BODY(24), fill=INK2)

def f1_sources(d):
    # разбросанные окна источников + боль
    wins = [
        ("📅 Календарь", "Релиз-синк · Альфа · 03.07 14:00", BLUE),
        ("🔶 Jira", "KAN-1 «Миграция схемы оплат»", BLUE),
        ("🔀 Git", "PR #128 «Схема оплат» — на ревью", BLUE),
        ("✉ Почта", "Блокер по KAN-1 · payment-adapter", AMBER),
        ("📄 Confluence", "Регламент релизных окон", BLUE),
        ("💬 Чаты", "устные договорённости …", GREY),
    ]
    coords = [(120, 120), (1180, 110), (110, 360), (1250, 350), (140, 600), (1200, 600)]
    for (title, sub, c), (x, y) in zip(wins, coords):
        panel(d, [x, y, x + 560, y + 150], fill=PANEL, radius=14, border=LINE)
        d.rounded_rectangle([x, y, x + 6, y + 150], radius=3, fill=c)
        d.text((x + 24, y + 18), title, font=F_H(26), fill=INK)
        d.text((x + 24, y + 64), sub, font=F_BODY(20), fill=INK2)
    # боль по центру внизу
    panel(d, [360, 800, 1560, 920], fill=(254, 243, 199), radius=16, border=AMBER)
    d.text((400, 822), "Контекст размазан по 6 системам · подготовка вручную · блокеры всплывают поздно",
           font=F_H(26), fill=AMBER)

# ============================================================== F2 ЗАПУСК
def f2_launch(d):
    ci = load_case_input("demo_case_alpha")
    ev = ci["calendar"]["events"][0]
    # карточка события
    panel(d, [120, 120, 900, 470], fill=PANEL, radius=16, border=LINE)
    d.rounded_rectangle([120, 120, 126, 470], radius=3, fill=BLUE)
    d.text((150, 140), "Событие календаря", font=F_H(26), fill=INK)
    d.text((150, 188), ev["title"], font=F_TITLE(34), fill=INK)
    rows = [
        ("Проект", ev["project"]),
        ("Дата", ev["datetime"]),
        ("Релиз", "ALPHA-2026.07"),
        ("Участники", ", ".join(ev["participants"])),
    ]
    y = 250
    for k, v in rows:
        d.text((150, y), k, font=F_BODY(20), fill=INK2)
        d.text((320, y), v, font=F_BODY(22), fill=INK)
        y += 44
    # командная строка
    code_block(d, [120, 520, 1800, 720],
               ["$ python -m athanor.cli demo \\",
                "    --case examples/demo_case_alpha --engine rule",
                "→ навык release_sync: определить встречу, проект, участников"],
               header="timlid@ouroboros:~  (демо-контур, без сети и ключей)")
    # справа: навык/identity
    panel(d, [960, 120, 1800, 470], fill=PANEL, radius=16, border=LINE)
    d.rounded_rectangle([960, 120, 966, 470], radius=3, fill=TEAL)
    d.text((990, 140), "Навык Ouroboros", font=F_H(26), fill=INK)
    chips = [("skills/release_sync/SKILL.md", TEAL), ("memory/identity.md", TEAL),
             ("memory/knowledge/", TEAL), ("MCP 127.0.0.1:9901–9904 (вкл. Confluence)", BLUE)]
    x, y = 990, 190
    for t, c in chips:
        w, h = chip(d, x, y, t, fill=CHIPBG, fg=INK, border=c)
        y += 44
    d.text((990, 390), "entry: main.py · version: v1 · external_actions: hitl-required",
           font=F_MONO(18), fill=INK2)

def f2_ouroboros_anim(d, frame_idx=0, frame_count=8):
    """Реальный прогон в Ouroboros v6.64 с Claude Opus 4.8 + 4 MCP (включая Confluence).
    Анимация печати (8 прогрессивных кадров). task dec66d75, lifecycle=completed
    (review=best_effort, auto-acceptance без кворума), $0.4337, 3 safety-таймаута восстановлены."""
    d.text((120, 96), "Реальный Ouroboros v6.64 · Claude Opus 4.8 · задача выполнена", font=F_H(26), fill=INK)
    all_lines = [
        "$ ouroboros run --workspace athanor-release-sync \\",
        "    \"Подготовь сводку к релиз-синку проекта Альфа 03.07\"",
        "Ouroboros 6.64.3 · workers=2/2 · model=anthropic/claude-opus-4.8 · MCP: 4 сервера",
        "",
        "# Tool trace (8 MCP-вызовов, 5 инструментов; 3 retry после safety-таймаута) — данные через MCP:",
        "tool: mcp_calendar_mail__get_events        → 1 событие «Релиз-синк · Альфа»",
        "tool: mcp_calendar_mail__get_mail          → блокер от SRE: payment-adapter не в prod",
        "tool: mcp_tracker_repo__get_issues         → KAN-1 [Готово], KAN-2 [к выполнению]",
        "tool: mcp_tracker_repo__get_prs            → PR #128 [на ревью 2 дн.]",
        "tool: mcp_confluence__get_confluence_pages → Release Plan · Альфа (что в релизе)",
        "",
        "← task completed (lifecycle) · 16 rounds · $0.4337 · 3 таймаута авто-восстановлены",
        "",
        "## Сводка (сформирована агентом Ouroboros, Claude Opus 4.8):",
        "Confluence: окно 03.07 18:00–20:00, APP-412 принята в релиз · зависимость payment-adapter",
        "KAN-1 «Миграция схемы оплат» — Готово (backend) · источник Jira · увер. высокая",
        "KAN-2 «Интеграция с партнёром» — к выполнению (frontend) · источник Jira",
        "PR #128 «Схема оплат» — на ревью 2 дн., не влит · источник Bitbucket",
        "⚠ КОНФЛИКТ по KAN-1: Jira «Готово» ↔ mail «блокер» ↔ PR «на ревью» → статус недостоверен",
        "Блокер: payment-adapter не в prod (SRE) · источник mail · увер. высокая",
    ]
    # прогрессирующее открытие строк
    visible = max(1, int(round(len(all_lines) * (frame_idx + 1) / frame_count)))
    lines = all_lines[:visible]
    if visible < len(all_lines):
        lines = lines + ["▌"]  # курсор на последней видимой строке
    _term_window(d, [80, 140, 1840, 920], lines,
                 title="Ouroboros v6.64 · real agent run (GUI + LLM + MCP) — task dec66d75")

# ============================================================== F3 СБОР КОНТЕКСТА
# Фрагмент 3 — реальная MCP-сессия (JSON-RPC over HTTP), захваченная через
# mcp/serve_all.py + athanor.cli --via-mcp. Лог: build/mcp_session.txt
SESSION = (HERE.parent / "build" / "mcp_session.txt") if False else None
try:
    SESSION = (Path(__file__).resolve().parent / "build" / "mcp_session.txt").read_text(encoding="utf-8").splitlines()
except Exception:
    SESSION = []

def _term_window(d, box, lines, title="timlid@ouroboros:~  —  MCP session (реальный протокол)"):
    x0, y0, x1, y1 = box
    panel(d, box, fill=(13, 17, 28), radius=14, border=(51, 65, 85))
    # header bar
    d.rounded_rectangle([x0, y0, x1, y0 + 44], radius=14, fill=(2, 6, 23))
    d.rectangle([x0, y0 + 30, x1, y0 + 44], fill=(2, 6, 23))
    for i, c in enumerate([(239, 68, 68), (245, 158, 11), (34, 197, 94)]):
        d.ellipse([x0 + 18 + i * 22, y0 + 14, x0 + 32 + i * 22, y0 + 28], fill=c)
    d.text((x0 + 110, y0 + 12), title, font=F_CODE(18), fill=GREY)
    d.line([x0, y0 + 44, x1, y0 + 44], fill=(51, 65, 85), width=1)
    # body
    y = y0 + 62
    for ln in lines:
        if not ln:
            y += 14
            continue
        if ln.startswith("$ "):
            d.text((x0 + 28, y), ln, font=F_CODEB(20), fill=TEAL)
        elif ln.startswith("→ POST"):
            d.text((x0 + 28, y), ln, font=F_CODE(19), fill=BLUE)
        elif ln.startswith("← "):
            d.text((x0 + 28, y), ln, font=F_CODE(19), fill=GREEN)
        elif ln.startswith("# ---"):
            d.text((x0 + 28, y), ln, font=F_CODE(19), fill=GREY)
        elif ln.startswith("   "):
            d.text((x0 + 28, y), ln, font=F_CODE(18), fill=(226, 232, 240))
        else:
            d.text((x0 + 28, y), ln, font=F_CODE(18), fill=(148, 163, 184))
        y += 27

# Кадры терминала — live MCP-сессия: Jira + mail (IMAP) + Calendar (iCal).
# Данные реально сняты с боевых систем (MCP_BACKEND=live); URL/email замаскированы.
# Лог: build/live_session.txt + results/scratch/demo_alpha_live/output.md
_F3_STARTUP = [
    "$ # Live-интеграции: Jira (Atlassian) + mail (IMAP) + Calendar (iCal)",
    "$ MCP_BACKEND=live python mcp/serve_all.py",
    "  calendar_mail  :9901/mcp  → mail IMAP + Calendar iCal",
    "  tracker_repo   :9902/mcp  → реальная Jira /rest/api/3/search/jql",
    "  transcripts    :9903/mcp  → файлы кейса (расшифровка)",
    "MCP-адаптеры подняты (3 боевые системы, stdlib-only: imaplib + urllib)",
    "",
    "# смена MCP_BACKEND → test (локальные) / file (демо) / live (Jira+mail+Calendar)",
]

_F3_TRACKER = [
    "# --- calendar_mail → Calendar (iCal) + mail (IMAP) ---",
    "→ POST :9901/mcp tools/call get_events   (→ Calendar /basic.ics)",
    "← 200 OK  1 событие из реального Calendar:",
    "   Релиз-синк · Альфа @ 2026-07-03T11:00  participants=5",
    "",
    "→ POST :9901/mcp tools/call get_mail     (→ mail IMAP, пароль приложения)",
    "← 200 OK  1 письмо из реального mail (IMAP):",
    "   [5] Блокер по KAN-1: payment-adapter не в prod  from=SRE  date=2026-07-16",
    "",
    "# --- tracker_repo → реальная Jira (Atlassian) ---",
    "→ POST :9902/mcp tools/call get_issues   (→ Jira /rest/api/3/search/jql)",
    "← 200 OK  2 задачи из реальной Jira:",
    "   KAN-1: Миграция схемы оплат  [Готово]  (Jira KAN-1 · 0.9)",
    "   KAN-2: Интеграция с партнёром  [к выполнению]  (Jira KAN-2 · 0.9)",
]

_F3_TRANSCRIPT_CLI = [
    "$ MCP_BACKEND=live athanor.cli run --case examples/demo_case_alpha_live --via-mcp",
    "← exit=0   сводка из реальных Jira + mail + Calendar:",
    "   ⚠ КОНФЛИКТ по KAN-1: Jira «Готово» ↔ письмо «блокер»  (0.6)",
    "   Блокер: payment-adapter не в prod  (письмо из mail, 0.7)",
    "   Событие: Релиз-синк · Альфа 03.07  (Calendar, iCal)",
    "   KAN-1 «Миграция схемы оплат» — Готово  (Jira KAN-1 · 0.9)  ← реальная Jira",
    "   KAN-2 «Интеграция с партнёром» — к выполнению  (Jira KAN-2 · 0.9)",
    "   → Разработчик backend: release-notes по KAN-1 · 2026-07-03",
    "   → SRE: подтверди деплой payment-adapter · 2026-07-03",
    "   черновики D01/D02: awaiting_approval (HITL)",
    "",
    "# 3 боевые системы через MCP, stdlib-only, без Azure/OAuth (IMAP + iCal + REST)",
]

def f3_collect_1(d):
    """4 источника через MCP — UI реальных инструментов на реальных данных (Альфа)."""
    ci = load_case_input("demo_case_alpha_live")
    ev = ci["calendar"]["events"][0]
    m = ci["mail"]["messages"][0]
    tr = ci["tracker"]
    d.text((120, 96), "Агент читает источники через MCP — данные сняты с боевых систем (live-снимок)", font=F_H(24), fill=INK)
    # 2x2 сетка UI
    calendar_ui(d, [80, 140, 940, 360], ev["title"], ev["datetime"], ev["participants"])
    mail_ui(d, [960, 140, 1840, 360], m["from_role"], m["date"], m["subject"], m["body"])
    jira_ui(d, [80, 380, 940, 600], "KAN-1", "Миграция схемы оплат", "Готово", "не определён", GREEN)
    bitbucket_ui(d, [960, 380, 1840, 600], 128, "Схема оплат", "на ревью", "KAN-1", 2)
    # подпись снизу
    panel(d, [80, 630, 1840, 720], fill=(219, 234, 254), radius=12, border=BLUE)
    d.text((110, 650), "MCP: calendar_mail.get_events/get_mail · tracker_repo.get_issues/get_prs",
           font=F_MONO(18), fill=BLUE)

def f3_collect_3(d):
    """Confluence — что включено в релиз (Release Plan)."""
    ci = load_case_input("demo_case_alpha_live")
    pages = ci["confluence"]["pages"]
    rp = pages[0]  # Release Plan
    d.text((120, 96), "Confluence: что включено в релиз (Release Plan · Альфа)", font=F_H(26), fill=INK)
    confluence_ui(d, [80, 140, 1840, 720], rp["title"], rp["space"], rp["excerpt"],
                  rp["version"], rp["updated_at"])
    panel(d, [80, 740, 1840, 830], fill=(219, 234, 254), radius=12, border=TEAL)
    d.text((110, 760), "MCP: confluence.get_confluence_pages · источник «что в релизе» (Confluence · 0.8)",
           font=F_MONO(18), fill=TEAL)

def f3_collect_5(d):
    """Jira KAN-2 + сводка из 5 источников."""
    d.text((120, 96), "Сводка из 5 источников: Jira + mail + Calendar + Bitbucket + Confluence",
           font=F_H(24), fill=INK)
    jira_ui(d, [80, 140, 700, 420], "KAN-2", "Интеграция с партнёром", "к выполнению", "не определён", BLUE)
    # сводка справа
    panel(d, [740, 140, 1840, 720], fill=PANEL, radius=14, border=LINE)
    d.text((770, 160), "Сводка перед релиз-синком", font=F_H(24), fill=INK)
    y = 205
    rows = [
        ("⚠ КОНФЛИКТ по KAN-1: Jira «Готово» ↔ письмо «блокер»", RED, "Jira KAN-1 ↔ письмо · 0.6"),
        ("Блокер: payment-adapter не в prod (SRE)", AMBER, "mail · 0.7"),
        ("KAN-1 «Миграция схемы оплат» — Готово", GREEN, "Jira · 0.9"),
        ("KAN-2 «Интеграция с партнёром» — к выполнению", BLUE, "Jira · 0.9"),
        ("PR #128 «Схема оплат» — на ревью 2 дн.", TEAL, "Bitbucket · 0.9"),
        ("В релиз: APP-412, APP-521 · зависимость payment-adapter", TEAL, "Confluence · 0.8"),
        ("Релиз-синк · Альфа 03.07 11:00, 5 участников", BLUE, "Calendar · 0.9"),
    ]
    for text, c, src in rows:
        d.text((770, y), text, font=F_BODY(19), fill=INK)
        d.text((770, y + 24), src, font=F_MONO(15), fill=c)
        y += 56



# ============================================================== F4 СВОДКА И БЛОКЕР
def f4_summary(d, zoom):
    # карточка сводки (реальный output)
    panel(d, [120, 110, 1800, 940] if not zoom else [80, 90, 1840, 960],
          fill=PANEL, radius=16, border=LINE)
    d.text((150, 130), "Сводка перед релиз-синком", font=F_H(28), fill=INK)
    if zoom:
        # крупно — конфликт: Jira UI (KAN-1 Готово) ↔ mail UI (блокер)
        panel(d, [120, 185, 1800, 250], fill=(254, 226, 226), radius=14, border=RED)
        d.text((160, 198), "⚠ КОНФЛИКТ по KAN-1", font=F_TITLE(36), fill=RED)
        d.text((160, 240), "Jira «Готово»  ↔  mail «блокер»  ·  приоритет Git/Jira > переписка  ·  решение за человеком",
               font=F_BODY(22), fill=INK2)
        # левая карточка — Jira KAN-1 (Готово)
        jira_ui(d, [120, 270, 940, 590], "KAN-1", "Миграция схемы оплат", "Готово", "не определён", GREEN)
        # правая карточка — mail (блокер)
        mail_ui(d, [960, 270, 1800, 590], "SRE", "2026-07-16",
                "Блокер по KAN-1: payment-adapter не в prod",
                "KAN-1: смежный сервис payment-adapter не задеплоен в production, релизное окно под риском, деплой заблокирован.")
        # блокер-плашка
        panel(d, [120, 610, 1800, 720], fill=(254, 243, 199), radius=14, border=AMBER)
        d.text((160, 625), "Критичный блокер: payment-adapter не развёрнут в production — релизное окно под риском",
               font=F_BODY(22), fill=AMBER)
        badge(d, 160, 670, "источник: mail от SRE 2026-07-16", AMBER)
        confidence_pill(d, 560, 670, 0.7)
        # 3 источника конфликта
        d.text((120, 750), "Источники конфликта — оба значения:", font=F_H(24), fill=INK)
        for i, (t, c) in enumerate([("Jira KAN-1: Готово · 0.9", GREEN),
                                    ("Bitbucket PR#128: на ревью 2 дн. · 0.9", TEAL),
                                    ("mail: блокер · 0.7", AMBER)]):
            chip(d, 150 + (i % 3) * 580, 800, t, fill=CHIPBG, fg=INK, border=c)
        return
    # обычный вид — секции сводки
    y = 180
    sections = [
        ("Конфликты источников", RED,
         ["⚠ КОНФЛИКТ по KAN-1: Jira «Готово» ↔ письмо «блокер» · приоритет Git/Jira > переписка · решение за человеком"]),
        ("Блокеры", AMBER,
         ["payment-adapter не в prod (SRE, 02.07) — окно под риском"]),
        ("Статусы задач и PR", BLUE,
         ["KAN-1 «Миграция схемы оплат» — Готово · KAN-2 — к выполнению · PR #128 — на ревью 2 дн."]),
        ("Обязательства с прошлого синка", TEAL,
         ["SRE: стенд предпрода · срок 2026-07-01 · ✔ Разработчик backend: APP-410 закрыто"]),
    ]
    for title, c, lines in sections:
        d.text((150, y), title, font=F_H(24), fill=c)
        y += 38
        for ln in wrap(d, lines[0], F_BODY(22), 1620):
            d.text((170, y), ln, font=F_BODY(22), fill=INK)
            y += 30
        y += 18
    # подпись источника у каждой строки — выноска
    panel(d, [150, y + 6, 1760, y + 86], fill=(241, 245, 249), radius=12, border=LINE)
    d.text((175, y + 20), "У каждого пункта: источник · уверенность (Jira/Git 0.9 · письмо 0.7 · память 0.8 · конфликт 0.6)",
           font=F_BODY(22), fill=INK2)

def f4_summary_full(d): f4_summary(d, zoom=False)
def f4_summary_zoom(d): f4_summary(d, zoom=True)

# ============================================================== F5 АНАЛИЗ ВСТРЕЧИ
def f5_transcript(d):
    d.text((120, 110), "Расшифровка синка 03.07 (фрагмент)", font=F_H(28), fill=INK)
    lines = [
        ("Тимлид", "Решение: выкатываем релиз 03.07 в окно 18:00–20:00, потому что регламентное окно", TEAL),
        ("Разработчик backend", "я подготовлю release-notes по KAN-1 до 03.07", BLUE),
        ("Тимлид", "SRE, подтверди деплой payment-adapter до 03.07", BLUE),
    ]
    y = 180
    for role, text, c in lines:
        panel(d, [120, y, 1800, y + 90], fill=PANEL, radius=12, border=LINE)
        d.rounded_rectangle([120, y, 126, y + 90], radius=3, fill=c)
        d.text((150, y + 14), role, font=F_H(22), fill=c)
        d.text((150, y + 48), text, font=F_BODY(22), fill=INK)
        y += 104
    panel(d, [120, y + 10, 1800, y + 90], fill=(219, 234, 254), radius=12, border=BLUE)
    d.text((150, y + 26), "Идеи («обсудим на следующем синке») отделены от решений и не попали в вывод",
           font=F_BODY(22), fill=BLUE)

def f5_extract(d):
    d.text((120, 110), "Извлечённые решения и поручения", font=F_H(28), fill=INK)
    # решение
    panel(d, [120, 170, 1800, 290], fill=(220, 252, 231), radius=14, border=GREEN)
    d.text((150, 190), "РЕШЕНИЕ", font=F_H(24), fill=GREEN)
    d.text((150, 226), "выкатываем релиз 03.07 в окно 18:00–20:00 · причина: регламентное окно", font=F_BODY(22), fill=INK)
    badge(d, 150, 256, "источник: расшифровка синка 03.07", GREEN)
    # поручения — таблица
    y = 320
    d.text((120, y), "ПОРУЧЕНИЯ (действие · ответственный · срок · источник)", font=F_H(24), fill=INK)
    y += 40
    cols = [("Действие", 560), ("Ответственный", 280), ("Срок", 220), ("Источник", 360)]
    x = 120
    panel(d, [120, y, 1800, y + 48], fill=(241, 245, 249), radius=10)
    cx = 150
    for name, w in cols:
        d.text((cx, y + 12), name, font=F_H(20), fill=INK2)
        cx += w
    y += 60
    rows = [
        ("подготовлю release-notes по KAN-1", "Разработчик backend", "2026-07-03", "KAN-1", BLUE),
        ("подтверди деплой payment-adapter", "SRE", "2026-07-03", "расшифровка 03.07", BLUE),
    ]
    for action, owner, due, src, c in rows:
        panel(d, [120, y, 1800, y + 70], fill=PANEL, radius=10, border=LINE)
        d.rounded_rectangle([120, y, 126, y + 70], radius=3, fill=c)
        cx = 150
        for val, (_, w) in zip([action, owner, due, src], cols):
            d.text((cx, y + 22), val, font=F_BODY(21), fill=INK)
            cx += w
        y += 82
    # уверенность/полнота
    panel(d, [120, y + 6, 1800, y + 86], fill=(219, 234, 254), radius=12, border=BLUE)
    d.text((150, y + 22), "Полнота владельцев 100% · полнота сроков 100% · каждое поручение привязано к источнику",
           font=F_BODY(22), fill=BLUE)

# ============================================================== F6 HITL
def _draft_card(d, box, draft, status_color, status_label):
    x0, y0, x1, y1 = box
    panel(d, box, fill=PANEL, radius=16, border=status_color)
    d.rounded_rectangle([x0, y0, x0 + 8, y1], radius=3, fill=status_color)
    d.text((x0 + 30, y0 + 22), "Черновик письма (HITL)", font=F_H(26), fill=INK)
    badge(d, x1 - 360, y0 + 24, status_label, status_color)
    d.text((x0 + 30, y0 + 72), "Кому:", font=F_BODY(20), fill=INK2)
    d.text((x0 + 150, y0 + 72), draft["to_role"], font=F_BODY(22), fill=INK)
    d.text((x0 + 30, y0 + 108), "Тема:", font=F_BODY(20), fill=INK2)
    d.text((x0 + 150, y0 + 108), draft["subject"], font=F_BODY(22), fill=INK)
    body = draft["body"].split("\n")[0]
    for i, ln in enumerate(wrap(d, body, F_BODY(21), (x1 - x0) - 200)):
        d.text((x0 + 30, y0 + 150 + i * 30), ln, font=F_BODY(21), fill=INK)
    d.text((x0 + 30, y1 - 60), "Срок: " + ("2026-07-03" if "D02" in draft["id"] else "2026-07-03"),
           font=F_BODY(20), fill=INK2)
    d.text((x0 + 360, y1 - 60), "Источник: " + draft["source_evidence"].replace("evidence:", ""),
           font=F_MONO(18), fill=INK2)

def f6_awaiting(d):
    d.text((120, 110), "Внешнее действие — только черновик", font=F_H(28), fill=INK)
    # D01 awaiting (статичная карточка — до подтверждения)
    d1a = {"id": "demo_case_alpha_live-D01", "to_role": "SRE",
           "subject": "[расшифровка синка 03.07] подтверди деплой payment-adapter",
           "body": "Коллега (SRE), по итогам релиз-синка за вами: подтверди деплой payment-adapter. Срок: 2026-07-03.",
           "source_evidence": "evidence:transcript:расшифровка синка 03.07"}
    _draft_card(d, [120, 180, 1800, 480], d1a, AMBER, "awaiting_approval")
    # статус-строка
    panel(d, [120, 520, 1800, 600], fill=(254, 243, 199), radius=12, border=AMBER)
    d.text((150, 540), "Статус: awaiting_approval — письмо НЕ отправлено, ожидает проверки человека",
           font=F_BODY(22), fill=AMBER)
    # цепочка статусов
    d.text((120, 640), "Жизненный цикл действия:", font=F_H(24), fill=INK)
    x = 150
    for i, (t, c, on) in enumerate([("proposed", GREY, True), ("awaiting", AMBER, True),
                                    ("approved", GREY, False), ("executed", GREY, False)]):
        w, h = chip(d, x, 700, t, fill=CHIPBG if not on else (254, 243, 199),
                    fg=INK, border=c)
        if i < 3:
            d.text((x + w + 6, 706), "→", font=F_H(24), fill=GREY)
        x += w + 40

def f6_approved(d):
    d.text((120, 110), "Человек подтвердил — действие исполняется", font=F_H(28), fill=INK)
    d2 = load_draft("demo_case_alpha_live-D02")  # status executed (live-прогон)
    _draft_card(d, [120, 180, 1800, 480], d2, GREEN, d2["status"])
    panel(d, [120, 520, 1800, 600], fill=(220, 252, 231), radius=12, border=GREEN)
    d.text((150, 540), "approved_at: " + d2.get("approved_at", "") + "   →   executed_at: " + d2.get("executed_at", ""),
           font=F_MONO(20), fill=GREEN)
    # цепочка — все горят
    d.text((120, 640), "Жизненный цикл действия:", font=F_H(24), fill=INK)
    x = 150
    for i, (t, c) in enumerate([("proposed", GREY), ("awaiting", AMBER),
                                ("approved", GREEN), ("executed", GREEN)]):
        w, h = chip(d, x, 700, t, fill=(220, 252, 231) if c == GREEN else CHIPBG,
                    fg=INK, border=c)
        if i < 3:
            d.text((x + w + 6, 706), "→", font=F_H(24), fill=GREY)
        x += w + 40
    panel(d, [120, 800, 1800, 880], fill=(219, 234, 254), radius=12, border=BLUE)
    d.text((150, 820), "Без подтверждения человека письмо не было бы отправлено — это политика автономии из identity.md",
           font=F_BODY(22), fill=BLUE)

# ============================================================== F7 ПАМЯТЬ
def _memory_card(d, box, title, text, color, highlight_lines=None):
    x0, y0, x1, y1 = box
    panel(d, box, fill=PANEL, radius=14, border=color)
    d.rounded_rectangle([x0, y0, x0 + 6, y1], radius=3, fill=color)
    d.text((x0 + 24, y0 + 16), title, font=F_H(24), fill=color)
    y = y0 + 56
    for i, ln in enumerate(text.splitlines()):
        hl = highlight_lines and i in highlight_lines
        if hl:
            d.rounded_rectangle([x0 + 20, y - 4, x1 - 20, y + 28], radius=6,
                                fill=(220, 252, 231))
        d.text((x0 + 28, y), ln if ln else " ", font=F_MONO(19), fill=INK)
        y += 27

def f7_before(d):
    d.text((120, 110), "Память релиза · ДО прогона", font=F_H(28), fill=INK)
    mem = load_memory_before().splitlines()
    # убираем пустые хвостовые для компактности
    _memory_card(d, [120, 180, 1800, 540], "memory/knowledge/release_alfa.md",
                 "\n".join(mem), GREY)
    panel(d, [120, 580, 1800, 660], fill=(241, 245, 249), radius=12, border=LINE)
    d.text((150, 600), "1 решение · 2 обязательства с прошлого синка — проверяемый контекст, не работа с нуля",
           font=F_BODY(22), fill=INK2)
    # journal
    d.text((120, 700), "journal.log (аудит-журнал):", font=F_H(24), fill=INK)
    code_block(d, [120, 750, 1800, 940],
               ["(пусто до цикла)  ←  первая запись появится после обновления памяти"],
               header="memory/journal.log")

def f7_after(d):
    d.text((120, 110), "Память релиза · ПОСЛЕ подтверждения", font=F_H(28), fill=INK)
    mem = load_memory_after().splitlines()
    # подсветим новые строки: 5 — новое решение; 10, 11 — новые обязательства
    hl = {5, 10, 11}
    _memory_card(d, [120, 180, 1760, 700], "memory/knowledge/release_alfa.md (обновлено)",
                 "\n".join(mem), GREEN, highlight_lines=hl)
    # journal с реальными записями
    d.text((120, 720), "journal.log:", font=F_H(24), fill=INK)
    jl = load_journal().splitlines()
    code_block(d, [120, 760, 1760, 960],
               [ln[:150] for ln in jl[:3]], header="memory/journal.log · 3 записи")

# ============================================================== F8 ОБРАТНАЯ СВЯЗКА
def f8_feedback(d):
    d.text((120, 110), "Обратная связь → новая версия навыка", font=F_H(28), fill=INK)
    # фидбек
    panel(d, [120, 170, 900, 360], fill=(254, 243, 199), radius=14, border=AMBER)
    d.text((150, 190), "Пользователь (тимлид):", font=F_H(24), fill=AMBER)
    for i, ln in enumerate(wrap(d, "«Сводка длинная — только блокеры и решения сверху»", F_BODY(24), 720)):
        d.text((150, 234 + i * 32), ln, font=F_BODY(24), fill=INK)
    # CLI
    code_block(d, [120, 390, 1800, 560],
               ["$ python -m athanor.cli feedback --usefulness 3 \\",
                "    --format-change \"короче, блокеры сверху\"",
                "→ формируется кандидат v2 (формат сводки: блокеры/конфликты сверху, ≤12 строк)"],
               header="control loop")
    # реестр версий
    panel(d, [950, 170, 1800, 360], fill=PANEL, radius=14, border=LINE)
    d.rounded_rectangle([950, 170, 956, 360], radius=3, fill=TEAL)
    d.text((980, 188), "Реестр версий навыка", font=F_H(24), fill=INK)
    chip(d, 980, 232, "v1 · stable · формат v1", fill=(220, 252, 231), fg=INK, border=GREEN)
    chip(d, 980, 284, "v2 · candidate · формат v2", fill=(254, 243, 199), fg=INK, border=AMBER)

def f8_evolution(d):
    d.text((120, 110), "Контрольный тест + откат — без деградации", font=F_H(28), fill=INK)
    # таблица истории из registry
    panel(d, [120, 170, 1800, 470], fill=PANEL, radius=14, border=LINE)
    d.text((150, 190), "history · skills/release_sync/versions/registry.json", font=F_MONO(20), fill=INK2)
    y = 230
    d.text((150, y), "action", font=F_H(20), fill=INK2); d.text((400, y), "version", font=F_H(20), fill=INK2)
    d.text((640, y), "baseline F1", font=F_H(20), fill=INK2); d.text((900, y), "candidate F1", font=F_H(20), fill=INK2)
    d.text((1180, y), "результат", font=F_H(20), fill=INK2)
    y += 34
    d.line([150, y, 1760, y], fill=LINE, width=1); y += 12
    rows = [
        ("promote", "v2", "1.0", "1.0", "stable — нет деградации", GREEN),
        ("rollback", "→ v1", "—", "—", "откат в одну команду", AMBER),
    ]
    for action, ver, bf, cf, res, c in rows:
        d.text((150, y), action, font=F_CODE(22), fill=INK)
        d.text((400, y), ver, font=F_CODE(22), fill=INK)
        d.text((640, y), bf, font=F_CODE(22), fill=INK)
        d.text((900, y), cf, font=F_CODE(22), fill=INK)
        chip(d, 1180, y - 4, res, fill=CHIPBG, fg=INK, border=c)
        y += 44
    # контрольные кейсы
    panel(d, [120, 500, 1800, 600], fill=(219, 234, 254), radius=12, border=BLUE)
    d.text((150, 520), "Контрольные кейсы: TB-01, TB-02, TB-04 · F1 candidate 1.0 vs baseline 1.0 — деградации нет",
           font=F_BODY(22), fill=BLUE)
    # сравнение сводок
    panel(d, [120, 630, 940, 940], fill=PANEL, radius=14, border=LINE)
    d.text((150, 650), "Сводка v1 (полная)", font=F_H(24), fill=INK)
    code_block(d, [140, 694, 920, 924],
               ["## Сводка перед релиз-синком", "### Конфликты ...", "### Блокеры ...",
                "### Статусы задач и PR ...", "### Обязательства ..."], )
    panel(d, [980, 630, 1800, 940], fill=PANEL, radius=14, border=GREEN)
    d.text((1010, 650), "Сводка v2 (короче)", font=F_H(24), fill=GREEN)
    code_block(d, [1000, 694, 1780, 924],
               ["## Сводка (v2 — блокеры сверху)", "- ⚠ КОНФЛИКТ по KAN-1 ...",
                "- Блокер: payment-adapter ...", "- обязательства ...", "- KAN-1 Готово ..."])

# ============================================================== F9 МЕТРИКИ
def f9_metrics(d):
    m = load_metrics()
    d.text((120, 110), "Фактические результаты тестовой корзины", font=F_H(28), fill=INK)
    cards = [
        ("Сценариев", str(m["scenarios"]), "17/17 успешных", BLUE),
        ("Поручения F1", f"{m['actions']['f1']*100:.0f}%", f"P {m['actions']['precision']*100:.0f} · R {m['actions']['recall']*100:.0f}", TEAL),
        ("Решения F1", f"{m['decisions']['f1']*100:.0f}%", f"{m['decisions']['tp']} TP · 0 FP", TEAL),
        ("Источники", f"{m['evidence_coverage']*100:.0f}%", "доля утверждений с источниками", BLUE),
        ("Черновики", str(m["drafts_total"]), f"принято {m['draft_acceptance']*100:.0f}% (HITL)", AMBER),
    ]
    cw, gap, x0, y0 = 340, 24, 120, 180
    for i, (title, big, sub, c) in enumerate(cards):
        x = x0 + i * (cw + gap)
        panel(d, [x, y0, x + cw, y0 + 320], fill=PANEL, radius=16, border=c)
        d.rounded_rectangle([x, y0, x + cw, y0 + 8], radius=3, fill=c)
        d.text((x + 24, y0 + 28), title, font=F_H(24), fill=INK2)
        d.text((x + 24, y0 + 80), big, font=F_TITLE(56), fill=c)
        for j, ln in enumerate(wrap(d, sub, F_BODY(20), cw - 48)):
            d.text((x + 24, y0 + 200 + j * 28), ln, font=F_BODY(20), fill=INK)
    # нижняя строка-честность
    panel(d, [120, 560, 1800, 720], fill=(241, 245, 249), radius=14, border=LINE)
    d.text((150, 584), "Движок: rule (rule-baseline, офлайн) · корзина синтетическая, выровнена с детерминированным извлечением",
           font=F_BODY(22), fill=INK2)
    d.text((150, 624), "Цикл конвейера: 5.0 мс · end-to-end сводка <1 с (цель ≤3 мин) · success_rate 100% · $0 LLM",
           font=F_BODY(22), fill=INK2)
    # мини-таблица сценариев
    d.text((120, 760), "Все 17 сценариев успешны (TB-01…TB-17):", font=F_H(24), fill=INK)
    chip(d, 120, 806, "A·F1 100%", fill=(220, 252, 231), fg=INK, border=GREEN)
    chip(d, 360, 806, "D·F1 100%", fill=(220, 252, 231), fg=INK, border=GREEN)
    chip(d, 600, 806, "блокеры F1 100%", fill=(220, 252, 231), fg=INK, border=GREEN)
    chip(d, 920, 806, "владельцы/сроки 100%", fill=(220, 252, 231), fg=INK, border=GREEN)

# ============================================================== F10 ФИНАЛ
def f10_final(d):
    cx = W // 2
    d.text((cx - d.textlength("Ouroboros — мозг команды", font=F_TITLE(58)) / 2, 200),
           "Ouroboros — мозг команды", font=F_TITLE(58), fill=TEAL)
    thesis = "Готовит тимлида к релиз-синку · фиксирует договорённости · сохраняет причины решений"
    for i, ln in enumerate(wrap(d, thesis, F_H(30), 1500)):
        d.text((cx - d.textlength(ln, font=F_H(30)) / 2, 300 + i * 44), ln, font=F_H(30), fill=(226, 232, 240))
    # формула Ouroboros
    formula = "навык  ·  MCP  ·  память  ·  Safety Layer  ·  Human-in-the-loop"
    d.text((cx - d.textlength(formula, font=F_H(28)) / 2, 470), formula, font=F_H(28), fill=BLUE)
    # следующий шаг
    panel(d, [460, 560, 1460, 660], fill=(219, 234, 254), radius=14, border=BLUE)
    nxt = "Следующий шаг — пилот с корпоративными коннекторами (почта · календарь · Jira · Confluence)"
    for i, ln in enumerate(wrap(d, nxt, F_BODY(24), 960)):
        d.text((cx - d.textlength(ln, font=F_BODY(24)) / 2, 588 + i * 30), ln, font=F_BODY(24), fill=BLUE)
    # команда + репо
    d.text((cx - d.textlength("Команда «Атанор»", font=F_TITLE(34)) / 2, 720),
           "Команда «Атанор»", font=F_TITLE(34), fill=(226, 232, 240))
    d.text((cx - d.textlength("athanor-release-sync  ·  MIT  ·  Python 3.10+  ·  stdlib-only", font=F_BODY(24)) / 2, 790),
           "athanor-release-sync  ·  MIT  ·  Python 3.10+  ·  stdlib-only", font=F_BODY(24), fill=INK2)
    # QR-код на репозиторий (плейсхолдер-ссылка)
    try:
        import qrcode
        qr = qrcode.make("https://github.com/sergeyenikeev/athanor-release-sync")
        qr = qr.resize((150, 150))
        d.bitmap((cx - 75, 850), qr, fill=TEAL)
        d.text((cx - d.textlength("репозиторий", font=F_TINY(18)) / 2, 1006), "репозиторий",
               font=F_TINY(18), fill=INK2)
    except Exception:
        pass
