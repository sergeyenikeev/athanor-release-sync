# Демо-видео Project Results (критерий «ДЕМО-видео», 30%)

Финальное демо-видео сборки Project Results команды «Атанор» (Sber AI Hack).
Длительность **2:20.76** (< 3 мин), 1920×1080, H.264/AAC, **русская голосовая озвучка**
(edge-tts `ru-RU-DmitryNeural`), субтитры `.srt`. Полный end-to-end сценарий:
запуск Ouroboros → сбор 5 источников через MCP → сводка с конфликтом и блокером →
анализ расшифровки (решения ≠ идеи, поручения) → HITL-черновик → память релиза →
эволюция навыка v1→v2 + откат → метрики 17 сценариев.

## Файлы
- `final/Athanor_Ouroboros_Project_Results_Demo.mp4` — финальное видео ( основной артефакт).
- `final/Athanor_Ouroboros_Project_Results_Demo.srt` — субтитры (текст озвучки).
- `final/Athanor_Ouroboros_Project_Results_Demo_subtitles.mp4` — версия с вшитыми субтитрами.
- `final/Athanor_Ouroboros_Project_Results_Demo_cover.png` — обложка.
- `final/voiceover.txt` — текст озвучки.
- `build/mcp_session.txt`, `build/live_session.txt`, `build/atlassian_session.txt` —
  **реальные** захваченные сессии (JSON-RPC over HTTP для MCP, live- и Atlassian-контуров),
  из которых `scenes.py` рендерит кадры.
- `make_video.py`, `scenes.py`, `common.py`, `timings.py` — сборщик (PIL-рендер кадров
  из реальных артефактов + edge-tts + сведение ffmpeg).

## Что показано в кадре
Видео показывает **фактически работающий прототип**, а не статичную презентацию:
- F2 — реальный агентный прогон **Ouroboros v6.64** (Claude Opus 4.8, task `dec66d75`,
  lifecycle=completed, 16 rounds, 8 MCP-вызовов / 5 инструментов) — tool trace и сводка.
- F3 — реальная MCP-сессия (JSON-RPC over HTTP), захваченная через `mcp/serve_all.py`
  + `athanor.cli --via-mcp` (лог `build/mcp_session.txt`).
- F4–F8 — briefing, конфликт, поручения, HITL-черновик, память — из фактических
  артефактов прогона `results/runs/eval_20260716T232149/`.

## Пересборка (опционально)
```bash
cd out/video
python make_video.py     # нужен ffmpeg в PATH + edge-tts (или fallback SAPI Irina)
```
Промежуточные артефакты (`build/frames/`, `build/audio/`) регенерируются автоматически
и в репозиторий не входят.
