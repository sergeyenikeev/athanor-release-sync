# -*- coding: utf-8 -*-
"""Оркестратор: озвучка (edge-tts SvetlanaNeural, fallback SAPI Irina) + сведение MP4 + субтитры + обложка.

Запуск:  python make_video.py
Выход:   final/Athanor_Ouroboros_Project_Results_Demo.mp4 (+ subs, .srt, cover)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image

import common as C
from common import W, H, FFMPEG, FINAL, FRAMES, AUDIO, HERE
import scenes as S

# ----------------------------------------------------------------- fragments
# Каждый фрагмент: tag, caption, color, voiceover, scenes=[(weight, render_fn)]
FRAGMENTS = [
    dict(tag="Проблема", cap="Контекст размазан по 6 системам — подготовка вручную",
         color=C.RED,
         voice="Перед каждым релиз-синком тимлид вручную собирает контекст из календаря, Jira, Git, почты и Confluence. Устные договорённости и блокеры часто обнаруживаются слишком поздно. Покажем, как агент на Ouroboros собирает этот контекст сам.",
         scenes=[(2, S.f1_title), (5, S.f1_sources)]),
    dict(tag="Запуск сценария", cap="1. Реальный Ouroboros v6.64 · навык release_sync · MCP",
         color=C.BLUE,
         voice="Ouroboros видит релиз-синк проекта Альфа. Одна команда — и навык release_sync автоматически начинает подготовку к встрече: определяет проект, участников и связанный релиз.",
         scenes=[(2, S.f2_launch), (3, S.f2_ouroboros_anim, 8)]),
    dict(tag="Сбор контекста", cap="2. 5 источников через MCP: Jira · mail · Calendar · Bitbucket · Confluence",
         color=C.BLUE,
         voice="Через MCP-инструменты агент опрашивает календарь, почту, трекер, репозиторий и Confluence — страницу релиза, чтобы понять, что включено в релиз. В демо это обезличенные выгрузки с теми же контрактами, что и корпоративные коннекторы.",
         scenes=[(1, S.f3_collect_1), (2, S.f3_collect_3), (2, S.f3_collect_5)]),
    dict(tag="Сводка и блокер", cap="3. Найден конфликт данных · критичный блокер",
         color=C.RED,
         voice="Агент не прячет противоречие. Jira сообщает «готово», pull request ещё на ревью, а в письме — блокер: смежный сервис payment-adapter не развёрнут. Три источника, оба значения, уровень уверенности и ссылка на каждый вывод.",
         scenes=[(2, S.f4_summary_full), (3, S.f4_summary_zoom)]),
    dict(tag="Анализ расшифровки", cap="4. Решение отделено от идей · 2 поручения",
         color=C.TEAL,
         voice="После встречи Ouroboros разбирает расшифровку. Отделяет решение от идей и извлекает два поручения: для каждого — владелец, срок и фрагмент, на котором основан вывод.",
         scenes=[(2, S.f5_transcript), (3, S.f5_extract)]),
    dict(tag="Human-in-the-loop", cap="5. Черновик — требуется подтверждение человека",
         color=C.AMBER,
         voice="Внешние действия агент не выполняет сам. Письмо исполнителю — только черновик со статусом «ожидает подтверждения». Человек проверяет владельца, срок и текст, подтверждает — и только тогда действие исполняется.",
         scenes=[(2, S.f6_awaiting), (3, S.f6_approved)]),
    dict(tag="Обновление памяти", cap="6. Память релиза обновлена · журнал записан",
         color=C.TEAL,
         voice="После подтверждения решение и обязательства сохраняются в памяти релиза. На следующем синке агент использует их как проверяемый контекст, а не начинает работу с нуля.",
         scenes=[(1, S.f7_before), (2, S.f7_after)]),
    dict(tag="Обратная связь и навык", cap="7. Новая версия навыка прошла тесты · откат",
         color=C.BLUE,
         voice="Обратная связь не меняет поведение бесконтрольно. Ouroboros создаёт новую версию навыка, прогоняет контрольные тесты и применяет её только при отсутствии деградации. Откат — в одну команду.",
         scenes=[(2, S.f8_feedback), (3, S.f8_evolution)]),
    dict(tag="Фактические результаты", cap="17 тестовых сценариев · F1 100%",
         color=C.GREEN,
         voice="На семнадцати обезличенных сценариях прототип достиг precision, recall и F1 равных единице по поручениям. Все прогоны успешны, каждое утверждение — с источником.",
         scenes=[(1, S.f9_metrics)]),
    dict(tag="Финал", cap="Следующий шаг — пилот с корпоративными коннекторами",
         color=C.TEAL,
         voice="Ouroboros уже готовит тимлида к релиз-синку, фиксирует договорённости и сохраняет причины решений. Следующий шаг — пилот с корпоративными коннекторами.",
         scenes=[(1, S.f10_final)]),
]
TOTAL = len(FRAGMENTS)

# ----------------------------------------------------------------- TTS (edge-tts neural, fallback SAPI Irina)
EDGE_VOICE = os.environ.get("ATHANOR_EDGE_VOICE", "ru-RU-DmitryNeural")  # нейт-голос Microsoft Edge (мужской)


def _tts_normalize(text: str) -> str:
    """Нормализация текста для TTS: исправить ударения и чтение технических терминов.
    На экране/в SRT остаётся исходное написание (Ouroboros, release_sync); правится
    только произношение аудио.

    - «Ouroboros» → «Уро́борос» (ударение на вторую «о»; от греч. οὐροβόρος).
      Latin-написание edge-tts читает ненадёжно (побуквенно / с неверным ударением).
    - «release_sync» → «релиз-синк» (иначе подчёркивание читается как «нижнее
      подчёркивание»).
    """
    import re

    def _ouro(m: "re.Match[str]") -> str:
        w = "уро\u0301борос"  # combining acute accent U+0301 на вторую 'о' (после 'р')
        return w[0].upper() + w[1:] if m.group(0)[0].isupper() else w

    text = re.sub(r"[Oo]uroboros(?!\w)", _ouro, text)
    text = text.replace("release_sync", "релиз-синк")
    # Аббревиатуры/короткие обозначения — edge-tts читает их непредсказуемо (побуквенно/как слово):
    text = re.sub(r"\bMCP\b(?!\w)", "эм-си-пи", text)          # Model Context Protocol
    text = re.sub(r"\bF1\b(?!\w)", "эф один", text)            # F1-метрика
    # Заимствования — фиксим ударение (U+0301) и чтение под русскую фонетику:
    text = re.sub(r"\bJira\b(?!\w)", "джи\u0301ра", text)      # ДжИра
    text = re.sub(r"\bConfluence\b(?!\w)", "конфлю\u0301енс", text)  # конфлЮенс
    return text


def synth_edge_mp3(text, mp3_path, retries=4):
    """Синтез через edge-tts (Microsoft Edge neural TTS, ru-RU-SvetlanaNeural).
    Высококачественный нейт-голос; нужен интернет. Возвращает длительность в сек."""
    import asyncio, edge_tts
    async def _run():
        comm = edge_tts.Communicate(text, EDGE_VOICE, rate="+0%", pitch="+0Hz")
        await comm.save(str(mp3_path))
    last = None
    for attempt in range(retries):
        try:
            asyncio.run(_run())
            if mp3_path.stat().st_size > 1000:
                return True
            last = "empty output"
        except Exception as e:  # noqa: BLE001 — сеть до speech.platform.bing.com нестабильна
            last = f"{type(e).__name__}: {e}"
            print(f"      [edge-tts] попытка {attempt+1}/{retries} не удалась: {last[:80]}")
            import time as _t; _t.sleep(2.0)
    print(f"      [edge-tts] сдаюсь после {retries} попыток: {last}")
    return False

def _mp3_duration_seconds(mp3_path):
    """Длительность MP3 через ffprobe/ffmpeg (нет stdlib-способа)."""
    import subprocess as _sp
    r = _sp.run([FFMPEG, "-i", str(mp3_path)], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if "Duration" in ln:
            h, m, s = ln.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return -1

def _mp3_to_wav(mp3_path, wav_path):
    """Конвертация MP3 → WAV (44.1kHz 16bit mono) для совместимости с concat/audio pipeline."""
    import subprocess as _sp
    _sp.run([FFMPEG, "-y", "-i", str(mp3_path), "-ar", "44100", "-ac", "1",
             "-sample_fmt", "s16", str(wav_path)], capture_output=True, check=True)

def synth_wav(text, out_path, rate=-1):
    """Синтез русской озвучки. Приоритет — edge-tts (нейт SvetlanaNeural); fallback — SAPI Irina.
    out_path — .wav; edge-tts сначала в .mp3 рядом, потом конвертируется в .wav."""
    mp3_path = out_path.with_suffix(".mp3")
    if synth_edge_mp3(text, mp3_path):
        dur = _mp3_duration_seconds(mp3_path)
        if dur > 0:
            _mp3_to_wav(mp3_path, out_path)
            return dur
        print("      [edge-tts] длительность не определилась — fallback на SAPI")
    # fallback: SAPI Irina (офлайн, роботизированный, но всегда работает)
    print("      [fallback] SAPI Microsoft Irina")
    import win32com.client
    sp = win32com.client.Dispatch("SAPI.SpVoice")
    for v in sp.GetVoices():
        if "Irina" in v.GetDescription():
            sp.Voice = v
            break
    sp.Rate = rate
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Format.Type = 6  # SA44100Hz16BitMono
    stream.Open(str(out_path), 3, False)  # SSFMCreateForWrite = 3
    sp.AudioOutputStream = stream
    sp.Speak(text, 0)
    stream.Close()
    return -1  # длительность определит вызывающий через wav_duration

def wav_duration(path):
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / float(f.getframerate())

# ----------------------------------------------------------------- build frames + audio
def build():
    # 1) озвучка пофрагментно (edge-tts нейт-голос SvetlanaNeural; fallback SAPI Irina)
    frag_audio = []
    voice_text = []
    for i, fr in enumerate(FRAGMENTS, 1):
        wp = AUDIO / f"frag{i:02d}.wav"
        mp3p = AUDIO / f"frag{i:02d}.mp3"
        print(f"[tts] фрагмент {i}/{TOTAL}: {fr['tag']}")
        # пересинтезировать, если есть только SAPI-wav без mp3 (edge-tts не запускался)
        need_resynth = (not wp.exists()) or wp.stat().st_size <= 1000 or (not mp3p.exists())
        if not need_resynth and mp3p.exists() and mp3p.stat().st_size > 1000:
            dur = wav_duration(wp) if wp.exists() else _mp3_duration_seconds(mp3p)
        else:
            dur = synth_wav(_tts_normalize(fr["voice"]), wp, rate=0)
            if dur <= 0:
                dur = wav_duration(wp)
        frag_audio.append((wp, dur))
        voice_text.append(fr["voice"])
        print(f"      длительность {dur:.2f} с")

    total_audio = sum(d for _, d in frag_audio)
    print(f"[tts] общая длительность озвучки: {total_audio:.2f} с")

    # 1b) субтитры .srt + текст озвучки
    write_srt(frag_audio, FRAGMENTS)
    write_voiceover(FRAGMENTS)

    # 2) рендер сцен с распределением длительности по весам
    scenes_meta = []  # (png_path, dur, frag_idx, scene_idx)
    seg_concat = []   # список (png, dur) для видео-конката
    for i, fr in enumerate(FRAGMENTS, 1):
        dur = frag_audio[i - 1][1]
        weights = [s[0] for s in fr["scenes"]]
        wsum = sum(weights)
        t = 0.0
        for j, scene in enumerate(fr["scenes"], 1):
            w = scene[0]
            fn = scene[1]
            nframes = scene[2] if len(scene) > 2 else 1  # анимация: > 1 кадра
            sdur = dur * w / wsum
            # мини-пауза между сценами внутри фрагмента (кроме последней) — 0.25 c
            if j < len(fr["scenes"]):
                sdur = max(sdur - 0.25, 0.4)
            fdur = sdur / nframes
            last_png = None
            for k in range(nframes):
                png = FRAMES / (f"f{i:02d}_s{j:02d}.png" if nframes == 1
                                else f"f{i:02d}_s{j:02d}_f{k:02d}.png")
                if not png.exists():
                    if nframes == 1:
                        img = S._scene(fn, i, TOTAL, fr["tag"], fr["cap"], fr["color"])
                    else:
                        img = S._anim_scene(fn, i, TOTAL, fr["tag"], fr["cap"], fr["color"], k, nframes)
                    img.save(png)
                    print(f"[frame] {png.name}")
                scenes_meta.append((png, fdur, i, j, t))
                seg_concat.append((png, fdur))
                last_png = png
                t += fdur
            # вставим паузу-кадр (повтор последнего) длительностью 0.25 c
            if j < len(fr["scenes"]) and last_png is not None:
                seg_concat.append((last_png, 0.25))

    total_video = sum(d for _, d in seg_concat)
    print(f"[frame] общая длительность видео-дорожки: {total_video:.2f} с")

    # 3) concat-файлы для ffmpeg
    vlist = BUILD_LIST = HERE / "build" / "video_concat.txt"
    alist = HERE / "build" / "audio_concat.txt"
    with vlist.open("w", encoding="utf-8") as f:
        for png, dur in seg_concat:
            f.write(f"file '{png.as_posix()}'\nduration {dur:.3f}\n")
        # ffmpeg concat demuxer: последний file без duration не показывается — дублируем
        f.write(f"file '{seg_concat[-1][0].as_posix()}'\n")
    with alist.open("w", encoding="utf-8") as f:
        for wp, _ in frag_audio:
            f.write(f"file '{wp.as_posix()}'\n")

    # 4) финальный MP4 (без субтитров)
    out_base = FINAL / "Athanor_Ouroboros_Project_Results_Demo.mp4"
    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(vlist),
        "-f", "concat", "-safe", "0", "-i", str(alist),
        "-vf", "fps=30,format=yuv420p,scale=1920:1080:flags=lanczos",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-shortest", "-t", f"{total_audio + 0.2:.2f}", "-movflags", "+faststart",
        str(out_base),
    ]
    print("[ffmpeg] сборка базового MP4 …")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:]); sys.exit("ffmpeg базовый сбой")
    print(f"[ffmpeg] OK -> {out_base}")

    # 5) версия со встроенными субтитрами (hardcoded)
    srt = FINAL / "Athanor_Ouroboros_Project_Results_Demo.srt"
    out_subs = FINAL / "Athanor_Ouroboros_Project_Results_Demo_subtitles.mp4"
    if srt.exists():
        cmd2 = [
            FFMPEG, "-y", "-i", str(out_base),
            "-vf", f"subtitles='{srt.as_posix().replace(':', '\\:')}':force_style='FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=52',scale=1920:1080:flags=lanczos",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out_subs),
        ]
        print("[ffmpeg] сборка версии с субтитрами …")
        r2 = subprocess.run(cmd2, capture_output=True, text=True)
        if r2.returncode != 0:
            print(r2.stderr[-3000:]); print("WARN: версия с субтитрами не собрана")
        else:
            print(f"[ffmpeg] OK -> {out_subs}")

    # 6) обложка (первый кадр / титул)
    cover = FINAL / "Athanor_Ouroboros_Project_Results_Demo_cover.png"
    S._scene(S.f1_title, 1, TOTAL, "Проблема",
             "Команда «Атанор» · Ouroboros — мозг команды", C.TEAL).save(cover)
    print(f"[cover] {cover}")

    # 7) сводка по длительности
    dur = probe_duration(out_base)
    print(f"\n[ГОТОВО] длительность {dur:.2f} с ({int(dur//60)}:{int(dur%60):02d})")
    return total_audio, total_video, dur

def probe_duration(path):
    cmd = [FFMPEG, "-i", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if "Duration" in ln:
            h, m, s = ln.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return -1

# ----------------------------------------------------------------- SRT + voiceover text
def _srt_ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _chunk_voice(text, max_chars=78):
    """Разбить озвучку на куски <= max_chars, сохраняя пунктуацию."""
    import re
    # сначала по границам предложений
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= max_chars:
            chunks.append(sent)
            continue
        # длинное предложение — режем по запятым, сохраняя их
        parts = re.split(r"(?<=,)\s+", sent)
        cur = ""
        for p in parts:
            cand = (cur + " " + p).strip()
            if len(cand) <= max_chars:
                cur = cand
            else:
                if cur:
                    chunks.append(cur)
                if len(p) <= max_chars:
                    cur = p
                else:
                    words, w = p.split(), ""
                    for x in words:
                        if len((w + " " + x).strip()) <= max_chars:
                            w = (w + " " + x).strip()
                        else:
                            if w:
                                chunks.append(w)
                            w = x
                    cur = w
        if cur:
            chunks.append(cur)
    return chunks

def write_srt(frag_audio, fragments):
    cues = []
    t = 0.0
    idx = 1
    for (wp, dur), fr in zip(frag_audio, fragments):
        chunks = _chunk_voice(fr["voice"])
        # распределить время по числу символов
        weights = [len(c) for c in chunks]
        wsum = sum(weights) or 1
        start = t
        for c, w in zip(chunks, weights):
            end = start + dur * w / wsum
            # не допускаем наложений: end чуть-чуть отступает от старта следующего
            end = min(end, t + dur - 0.001)
            cues.append((idx, start, end, c))
            idx += 1
            start = end + 0.001
        t += dur
    srt = FINAL / "Athanor_Ouroboros_Project_Results_Demo.srt"
    with srt.open("w", encoding="utf-8") as f:
        for idx, s, e, line in cues:
            f.write(f"{idx}\n{_srt_ts(s)} --> {_srt_ts(e)}\n{line}\n\n")
    print(f"[srt] {srt} · {len(cues)} cues")

def write_voiceover(fragments):
    out = FINAL / "voiceover.txt"
    with out.open("w", encoding="utf-8") as f:
        f.write("Текст голосовой озвучки демо-видео\n")
        f.write("Ouroboros — мозг команды · команда «Атанор» · Sber AI Hack\n\n")
        for i, fr in enumerate(fragments, 1):
            f.write(f"--- Фрагмент {i}. {fr['tag']} ---\n{fr['voice']}\n\n")
    print(f"[voice] {out}")

if __name__ == "__main__":
    build()
