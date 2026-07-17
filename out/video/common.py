# -*- coding: utf-8 -*-
"""Сборка финального ДЕМО-видео Ouroboros (команда Атанор) из реальных артефактов.

Пайплайн:
  1. Рендер кадров (PIL, 1920x1080) для каждой сцены из реальных артефактов прогона.
  2. Синтез русской озвучки (edge-tts, Microsoft Edge neural TTS ru-RU-SvetlanaNeural;
     fallback SAPI Irina) пофрагментно -> MP3 -> WAV.
  3. Сведение кадров + озвучки в MP4 (ffmpeg, H.264/AAC) + версия с субтитрами.

Все показанные данные — обезличенная синтетика из examples/demo_case_alpha
и results/demo/<run_id>/ (реальный прогон rule-движка).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------- paths
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent / "athanor-release-sync"
BUILD = HERE / "build"
FRAMES = BUILD / "frames"
AUDIO = BUILD / "audio"
FINAL = HERE / "final"
for d in (FRAMES, AUDIO, FINAL):
    d.mkdir(parents=True, exist_ok=True)

FFMPEG = _ff = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    for cand in (shutil.which("ffmpeg"), r"C:\ffmpeg\bin\ffmpeg.exe"):
        if cand and Path(cand).is_file():
            FFMPEG = cand
if not FFMPEG:
    sys.exit("ffmpeg не найден: pip install imageio-ffmpeg")

# --------------------------------------------------------------------- fonts
F_DIR = Path(r"C:\Windows\Fonts")
def font(name, size):
    return ImageFont.truetype(str(F_DIR / name), size)
F_TITLE = lambda s=44: font("arialbd.ttf", s)
F_H     = lambda s=30: font("arialbd.ttf", s)
F_BODY  = lambda s=24: font("arial.ttf", s)
F_SMALL = lambda s=20: font("arial.ttf", s)
F_TINY  = lambda s=17: font("arial.ttf", s)
F_CODE  = lambda s=22: font("consola.ttf", s)
F_CODEB = lambda s=22: font("consola.ttf", s)
F_MONO  = lambda s=18: font("consola.ttf", s)

# --------------------------------------------------------------------- palette (Sber)
BG       = (15, 23, 42)        # #0F172A тёмный слейт (рабочий стол)
PANEL    = (248, 250, 252)     # светлая карточка
PANEL_D  = (30, 41, 59)        # тёмная карточка
INK      = (26, 26, 46)        # #1A1A2E основной текст
INK2     = (71, 85, 105)       # приглушённый
BLUE     = (26, 86, 255)       # #1A56FF
TEAL     = (18, 178, 166)      # #12B2A6
AMBER    = (217, 119, 6)       # гейт/внимание
RED      = (220, 38, 38)       # блокер
GREEN    = (22, 163, 74)       # OK
GREY     = (148, 163, 184)
LINE     = (226, 232, 240)
CHIPBG   = (241, 245, 249)

W, H = 1920, 1080

# --------------------------------------------------------------------- canvas
def new_canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def topbar(d, step, total, tag):
    # левый акцент
    d.rectangle([0, 0, 8, H], fill=TEAL)
    # верхняя плашка
    d.rectangle([0, 0, W, 70], fill=(2, 6, 23))
    d.text((34, 18), "Ouroboros — мозг команды", font=F_H(26), fill=TEAL)
    # шаг
    txt = f"Шаг {step}/{total}  ·  {tag}"
    bbox = d.textbbox((0, 0), txt, font=F_BODY(22))
    w = bbox[2] - bbox[0]
    d.text((W - w - 34, 22), txt, font=F_BODY(22), fill=GREY)

def caption(d, text, color=BLUE):
    # нижняя плашка-подпись (одна мысль)
    h = 84
    y = H - h
    d.rectangle([0, y, W, H], fill=(2, 6, 23))
    d.rectangle([0, y, 8, H], fill=color)
    d.text((34, y + 24), text, font=F_H(28), fill=(248, 250, 252))

def panel(d, box, fill=PANEL, radius=18, border=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                        outline=border, width=2 if border else 0)

def chip(d, x, y, text, fill=CHIPBG, fg=INK, pad=(14, 8), font_=F_SMALL(20), border=None):
    bbox = d.textbbox((0, 0), text, font=font_)
    w = bbox[2] - bbox[0] + pad[0] * 2
    h = bbox[3] - bbox[1] + pad[1] * 2
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=fill, outline=border,
                        width=2 if border else 0)
    d.text((x + pad[0], y + pad[1] - 2), text, font=font_, fill=fg)
    return w, h

def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def text_block(d, x, y, lines, fnt, fill, leading=34):
    for ln in lines:
        d.text((x, y), ln, font=fnt, fill=fill)
        y += leading
    return y

def code_block(d, box, lines, header=None):
    x0, y0, x1, y1 = box
    panel(d, box, fill=(13, 17, 28), radius=14, border=(51, 65, 85))
    y = y0 + 18
    if header:
        d.text((x0 + 20, y), header, font=F_CODE(18), fill=GREY)
        y += 30
        d.line([x0 + 20, y, x1 - 20, y], fill=(51, 65, 85), width=1)
        y += 12
    for ln in lines:
        d.text((x0 + 24, y), ln, font=F_CODE(22), fill=(226, 232, 240))
        y += 30
    return y

def badge(d, x, y, text, color):
    f = F_TINY(17)
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0] + 22
    h = 26
    d.rounded_rectangle([x, y, x + w, y + h], radius=13, fill=color)
    d.text((x + 11, y + 4), text, font=f, fill=(255, 255, 255))
    return w, h

def confidence_pill(d, x, y, val):
    return badge(d, x, y, f"увер. {val:.1f}", BLUE)

# --------------------------------------------------------------------- artifact loaders
# Live-артефакты: Jira — реальная Cloud (KAN-1/KAN-2), остальное — demo_case_alpha_live.
# Прогон: MCP_BACKEND=atlassian python -m athanor.cli run --case examples/demo_case_alpha_live --via-mcp
_LIVE = REPO / "results" / "scratch" / "demo_alpha_live"
_CASE_LIVE = REPO / "examples" / "demo_case_alpha_live"

def load_demo_output(fmt="v1"):
    return (_LIVE / "output.md").read_text(encoding="utf-8")

def load_memory_before():
    return (_CASE_LIVE / "input" / "memory_seed.md").read_text(encoding="utf-8")

def load_memory_after():
    return (_LIVE / "memory_after" / "knowledge" / "release_alfa.md").read_text(encoding="utf-8")

def load_journal():
    return (_LIVE / "memory_after" / "journal.log").read_text(encoding="utf-8")

def load_draft(did):
    return json.loads((_LIVE / "outbox" / f"{did}.json").read_text(encoding="utf-8"))

def load_metrics():
    return json.loads((REPO / "results" / "metrics.json").read_text(encoding="utf-8"))

def load_registry():
    return json.loads((REPO / "skills" / "release_sync" / "versions" / "registry.json").read_text(encoding="utf-8"))

def load_skill_md():
    return (REPO / "skills" / "release_sync" / "SKILL.md").read_text(encoding="utf-8")

def load_identity():
    return (REPO / "memory" / "identity.md").read_text(encoding="utf-8")

def load_case_input(name):
    d = REPO / "examples" / "demo_case_alpha_live" / "input"
    return {
        "calendar": json.loads((d / "calendar.json").read_text(encoding="utf-8")),
        "tracker": json.loads((d / "tracker.json").read_text(encoding="utf-8")),
        "mail": json.loads((d / "mail.json").read_text(encoding="utf-8")),
        "transcript": (d / "transcript.txt").read_text(encoding="utf-8"),
        "confluence": json.loads((d / "confluence.json").read_text(encoding="utf-8")),
    }
