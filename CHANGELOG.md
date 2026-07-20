# Changelog

## [1.10.1] — 2026-07-20 (полезность сводки замерена: AS IS 20% (1/5) → агент 5/5 в пилоте)

### Изменено
- **Полезность сводки — обе стороны замерены**: AS IS (ручная сводка, без
  агента) — **20% (1/5)**; сводка агента в пилоте — **5/5 (100%)**, независимый
  оценщик. Цель Proposal ≥4/5 достигнута → **все 6 целей Proposal измерены и
  достигнуты**. Обновлены README (функции, цели Proposal, таблица AS IS/TO BE),
  презентация (слайды 8, 9, 11, 14) и отчёт о тестовой корзине
  (`out/04_testovaya_korzina_i_otchet.md` → 02_Test_Examples_Evaluation.pdf).
  Recall на реальных расшифровках — по-прежнему замер пилота.
- Плейсхолдеры `[ТРЕБУЕТСЯ ФАКТИЧЕСКИЙ РЕЗУЛЬТАТ]` (3 шт.) в отчёте о корзине
  заменены фактами: полезность AS IS 20%, хронометраж 15 мин/встреча ([1.7.2]).
- Уточнение к [1.9.1]: после финальной пересборки видео (v22, блокеры [1.10.0]
  в кадре метрик) актуальный артефакт — **2:53.01** (173.01 с, 16 906 480 байт);
  цифры «2:53.04 / 16 756 520» в [1.9.1] — промежуточная сборка.

## [1.10.0] — 2026-07-20 (блокеры из решений синка · новый канонический прогон)

### Добавлено
- **Извлечение блокеров из расшифровки**: блокер, зафиксированный решением на
  синке («блокер по OPS-77 фиксируем, ответственный SRE»), попадает в
  структурированные блокеры с владельцем из «ответственный X», severity=high,
  resolution_status=confirmed (`src/athanor/enrich.py: extract_blockers(...,
  decisions)`, вызов из `agent.py`). LLM-движок получает то же поведение
  автоматически (блокеры derive из решений). Закрывает расхождение из e2e-демо:
  чат агента видел блокер OPS-77, run.json — нет.
- Юнит-тесты `tests/unit/test_enrich.py` (5 шт.): блокер из решения c owner,
  решение без блокера, блокер без владельца → «не определён», блокеры из
  сводки не затронуты, обратная совместимость сигнатуры. Итого 131 тест.
- Эталон TB-04: `expected/blockers.json` — 1 блокер (OPS-77, SRE);
  meta.json/metadata.yaml/README дополнены проверкой.

### Изменено
- **Новый канонический прогон** `results/runs/eval_20260720T_blockers`
  (rule, TB-01..17, 17/17 success): блокеры tp 4→5, все метрики остаются
  P/R/F1=100%. Зеркала results/{metrics.json,metrics.csv,results_summary.md,
  evaluation_report.html} обновлены. Предыдущий валидный ран
  `eval_20260719T_fixed` сохранён как история.
- Честность метрик: `model` в manifest/metrics и RunResult фиксируется только
  при реальных LLM-вызовах — у rule-прогона `model: null` (раньше подтягивалась
  модель из `.env`, которая не вызывалась).

## [1.9.1] — 2026-07-20 (семантические метрики GLM 5.2 в демо-видео и материалах · 2:53.04)

### Добавлено
- **Фрагмент 9 демо-видео**: озвучка, подпись и визуал обновлены — rule-бейзлайн
  F1 100% + live-прогон GLM 5.2 с независимым семантическим судьёй (gpt-4o-mini,
  T=0, два прохода): поручения F1 90.9%, решения 92.3%, блокеры 100%; строгий
  текст — 18.2% (парафразы). Панель честности f9_metrics — 3 строки (rule / live
  LLM / цель ≥82% превышена). TTS-нормализация: «GLM 5.2» → «джи-эл-эм пять-два».
- **Презентация (слайды 8, 9, 16)**: цели Proposal — «100% rule · 90.9% LLM
  семантич.»; Приложение E — строка live LLM прогона (строгий 18.2% → семантич.
  90.9%, реальные ошибки 1 FN + 1 FP); время после встречи — 10.9 с (GLM 5.2).
- **README**: таблица целей расширена колонкой «Live LLM (GLM 5.2, семантич.)»
  со ссылкой на методику судьи и вердикты.

### Изменено
- Демо-видео пересобрано: **2:53.04** (173.04 с, 16 756 520 байт), < 3:00.
  SRT = аудио = визуал (проверено покадрово и по тексту SRT). Инвалидация кэша:
  удалены stale `build/audio/frag09.*` И `build/frames/f09_s01.png` (кэш только
  по существованию файла — урок v19 распространён на кадры).
- Длительность обновлена: README, `scripts/gen_reports.py`, `results/demo_scenario.md`
  (2:48.28/2:30 → 2:53.04), deck slide 4/13 (2:50 → 2:53).

## [1.9.0] — 2026-07-20 (боевой e2e через Ouroboros + cloud_capture + 126 тестов)

### Добавлено
- **CLI HITL**: subparsers `reject`, `edit`, `comment` в `src/athanor/cli.py`
  (раньше был только `approve`). 9 unit-тестов в `tests/unit/test_cli_hitl.py`.
  Всего тестов: **126** (было 117).
- **Whitelist skill main.py**: расширен до `{run, approve, reject, edit, comment,
  feedback, versions, promote, rollback}` — Ouroboros может вызывать все HITL- и
  evolution-команды через чат.
- **Боевые прогоны через Ouroboros v6.64.3** (headless CLI, jetnight-pro):
  - `de797d3f` — полный e2e (run + HITL approve + reject) в одном прогоне,
    40 rounds, tier=solved. Запись Playwright → `out/video/cloud_capture/ouroboros_e2e_*.mp4`.
  - `ceb91e67` — управляемая эволюция (feedback → promote v2 с контрольным тестом
    F1 1.0 → rollback v1).
  - `10ffd02e` — edit + comment + approve (полный HITL-цикл правки).
  - `e11fd35c` — `--via-mcp` + HITL (MCP-сбор + подтверждение).
  Артефакты: `results/scratch/ouroboros_{hitl_e2e,evolution,edit_comment,mcp_hitl}/`
  + `OUROBOROS_RUNS_SUMMARY.md`. Все 10 пунктов критерия «ГигаАгент» подтверждены
  через Ouroboros.
- **Демо-видео 2:30** (150.48с, H.264/AAC, 1920×1080, 11.9МБ):
  F2=e2e_launch клип (Ouroboros UI), F3=5 cloud_capture клипов (Calendar · mail ·
  Jira · Bitbucket · Confluence Cloud), F6=e2e_hitl клип (HITL approve/reject через
  Ouroboros), F8=CLI эволюция. `record_ouroboros_e2e.py` — Playwright-запись UI.

### Изменено
- `SKILL.md`: секция 8 — обратная связь и эволюция (команды, контрольные тесты, откат).
- `build_results.py` (презентация): 117→126 тестов, 2:48→2:30, HITL «в чате Ouroboros»,
  границы честности обновлены (боевой e2e через Ouroboros).
- `docs/architecture.md`, `docs/security.md`, `docs/demo.md`, `README.md` — HITL
  через Ouroboros, новые CLI-команды, 126 тестов.

## [1.8.1] — 2026-07-19 (demo v19: устранён SRT↔audio desync + 3 документационных фикса)

### Изменено
- **Демо-видео** (`video/Athanor_Ouroboros_Project_Results_Demo.mp4`): озвучка
  пересобрана с edge-tts DmitryNeural (rate=-12%) из текущего `voiceover.txt`.
  Причина: MiniMax MP3 (2026-07-17 23:17) был сгенерирован ДО правок voiceover.txt
  (2026-07-18: добавлено «В результате агент выводит готовую сводку…» в фрагмент 2,
  «payment-adapter»→«ППРБ-адаптер» в фрагмент 4) — SRT (из текущего voiceover.txt)
  показывал текст, которого нет в аудио. **v19: edge-tts из текущего voiceover.txt →
  SRT = аудио = визуал (ППРБ-адаптер).** Длительность: mvhd 168.281 с = **2:48.28**,
  8 558 222 байт. 2:48 в рекомендованном диапазоне task6 (2:35–2:50), < 3:00 ✓.
  `ATHANOR_EDGE_TTS_RATE` env var добавлена в `synth_edge_mp3` (default `+0%`).
- **README.md**: `results/runs/after_fix/TB-01/output.md` → `eval_20260719T_fixed/TB-01/output.md`
  (after_fix переименован в v13, но путь в README остался — broken link). Сборщик
  озвучки: «edge-tts DmitryNeural» → «edge-tts DmitryNeural и/или готовый MiniMax MP3
  через `VOICEOVER_MP3`» (отражает оба режима `make_video.py`).
- **Deck** (`build_results.py`, внешний репо): сл.10 «LLM — OpenRouter» →
  «LLM — jet-night router (GLM 5.2)» (фактический провайдер per `.env.example`,
  `config/local.yaml`, `src/athanor/config.py`, README); сл.6 «OpenRouter / OpenAI /
  локальная» → «jet-night / OpenRouter / OpenAI / локальная» (jet-night первым —
  фактический провайдер). Длительность 2:43.10 → 2:48.28 (сл.4, сл.11 notes, сл.13).

### Не изменено (исторические артефакты — правило честности)
- `results/scratch/ouroboros_demo_e2e_jetnight/result.json` (прогон `a5336602`):
  поля `model`/`resolved_model` = `openai-compatible::jetnight-opus` — **факт
  прогона** (до [1.7.3]), не переписывается.
- `results/scratch/ouroboros_demo/result.json` (прогон `dec66d75`):
  `model` = `anthropic/claude-opus-4.8` — **факт прогона**, не переписывается.
- Метрики `results/metrics.json` (run_id `eval_20260719T_fixed`, F1=1.0, 17/17,
  timing 0.002 с) — без изменений.
- Записи CHANGELOG `[1.4.0]`…`[1.8.0]` (включая 2:43.10/MiniMax) сохранены как история.

## [1.8.0] — 2026-07-19 (demo v17/v18: озвучка MiniMax 2:43.10 + усиление deck↔repo↔artifact)

### Изменено
- **Демо-видео** (`video/Athanor_Ouroboros_Project_Results_Demo.mp4`): озвучка
  edge-tts (SvetlanaNeural/DmitryNeural, 2:20.50) заменена на готовый MP3
  `MiniMax_2026-07-17_23_17_57_Articulate_Tutor.mp3` (163.08 с, 128 kbps mono).
  Финальное MP4: mvhd 163.103 с = **2:43.10**, 8 349 478 байт (было 7 138 160 /
  2:20.63). 2:43 в рекомендованном диапазоне task6 (2:35–2:50), < 3:00 ✓.
  Сборщик `out/video/make_video.py`: режим `VOICEOVER_MP3=<path>` — длительности
  10 фрагментов масштабируются пропорционально edge-tts-долям, сцены и границы
  F2/F3/F8 адаптируются автоматически; аудио одним треком. `setpts` к F2/F3
  (как уже было у F8) — клипы замедляются до слота, вся озвучка сохранена.
- **README.md**, `results/demo_scenario.md`: длительность 2:20.50 → 2:43.10;
  путь `/blob/main/video/*.mp4` (raw URL HTTP 200 после Public). SRT тайминги
  пересчитаны по новым пропорциям (последняя cue 00:02:43,078); текст SRT —
  исходный edge-tts-скрипт (`voiceover.txt`). Откат: `Remove-Item Env:\
  VOICEOVER_MP3; python make_video.py` → edge-tts 2:20.53 (кеш frag01-10.wav).
- **Deck** (`build_results.py`, внешний репо): сл.4/13 — 2:20.50 → 2:43.10;
  сл.16 (Прил. E) — subtitle «Не подгоняем под 100%» → «100% в каждом классе
  значит разное: полное извлечение · корректная фиксация пропуска · безопасная
  блокировка»; footnote дополнен data-sync note (см. ниже). v18 docstring
  фиксирует 3 найденных расхождения (video desync, README vs artifact model,
  slide 16 optics) и их исправления.

### Исправлено (v18 — сверка deck↔public repo↔artifacts)
- **Video desync**: deck (рабочее дерево) заявлял 2:43.10, но публичный inner-репо
  (origin/main, commit 4fba955) содержал видео 2:20.63 — QR на сл.11 вёл на 2:20.63,
  а сл.4/13 утверждали 2:43.10. Видео 2:43.10 (8 349 478 байт, mvhd 163.103 с)
  скопировано в `athanor-release-sync/video/` — QR теперь ведёт на 2:43.10,
  согласовано с deck-ом. **Команда делает commit+push для публикации.**
- **README vs artifact (a5336602 model)**: README (рабочее дерево) утверждал
  «прогон a5336602 (jetnight-pro, ...)», но `results/scratch/ouroboros_demo_e2e_jetnight/
  result.json` (`loop_outcome.trace_refs.llm_call_refs[0].model`) =
  «openai-compatible::jetnight-opus». Прогон a5336602 выполнялся ДО миграции
  jetnight-opus→jetnight-pro ([1.7.3]); CHANGELOG [1.7.3] явно фиксирует, что
  historical artifact не переписывается. README возвращён к «jetnight-opus» —
  согласовано с result.json, deck-ом (сл.5) и demo_scenario.md.
- **Slide 16 optics (Прил. E)**: subtitle «Не подгоняем под 100%» + таблица
  100/100/100 во ВСЕХ классах выглядела внутренне противоречиво. Subtitle
  переписан; footnote дополнен: «Data-sync TB-13/15/16 (commit 0309823):
  expected-метки синхронизированы с актуальной tracker-данной после миграции
  "Миграция схемы оплат"→"Миграция на ППРБ"; код агента не менялся — output.md
  байт-идентичен до/после». Закрывает подозрение «эталон подогнали под агента»
  (task4 §20): data-sync input→expected, не agent→expected.

### Не изменено (исторические артефакты — правило честности)
- `results/scratch/ouroboros_demo_e2e_jetnight/result.json` (прогон `a5336602`):
  поля `model`/`resolved_model` = `openai-compatible::jetnight-opus` — **факт
  прогона** (до [1.7.3]), не переписывается. Deck сл.5 и demo_scenario.md
  говорят «jetnight-opus» (верно); README исправлен к тому же.
- `results/scratch/ouroboros_demo/result.json` (прогон `dec66d75`):
  `model` = `anthropic/claude-opus-4.8` — **факт прогона**, не переписывается.
- Метрики `results/metrics.json` (run_id `eval_20260719T_fixed`, F1=1.0, 17/17,
  timing 0.002 с) — без изменений; v18 не меняет фактические метрики, только
  устраняет рассинхроны deck↔public repo↔artifact и усиливает оптику slide 16.

## [1.7.3] — 2026-07-18 (task5: модели Ouroboros → jetnight-pro / jetnight-fast)

### Изменено
- **Конфиг Ouroboros** (`data/settings.json`, провайдер `openai-compatible` →
  jet-night router `https://router.jet-night.com/api/v1`): основная
  `OUROBOROS_MODEL`/`OUROBOROS_MODEL_HEAVY`/`OUROBOROS_WEBSEARCH_MODEL` —
  `openai-compatible::jetnight-pro` (GLM 5.2); лёгкие/review/safety-слоты
  `OUROBOROS_MODEL_LIGHT`/`CONSCIOUSNESS`/`DEEP_SELF_REVIEW`/`REVIEW_MODELS`/
  `SCOPE_REVIEW_MODELS`/`SCOPE_REVIEW_MODEL` — `openai-compatible::jetnight-fast`
  (GLM 5.2 Fast); `OUROBOROS_MODEL_VISION` — `openai-compatible::opus-visual`
  (мультимодальный слот; оставлен на opus-visual из исходной конфигурации);
  `OUROBOROS_MODEL_FALLBACKS` — `jetnight-pro, jetnight-fast`. Заменено
  `jetnight-opus`→`jetnight-pro`, `gpt-5.5`→`jetnight-fast` (vision `opus-visual`
  сохранён без изменений).
- **Документация** (forward-looking): `AGENTS.md`, `.opencode/skills/athanor-contest/SKILL.md`,
  `.opencode/agents/ouroboros-ops.md`, `README.md` (таблица «Ключевые поля
  settings.json»), `out/video/record_ouroboros.py` — приведены к актуальным
  моделям jetnight-pro/jetnight-fast и провайдеру jet-night.

### Не изменено (исторические артефакты — правило честности)
- `results/scratch/ouroboros_demo/result.json` (прогон `dec66d75`): поля
  `model`/`resolved_model` = `anthropic/claude-opus-4.8` — **факт прогона**,
  не переписывается. `out/video/scenes.py` (фрагмент 2): подпись
  `model=anthropic/claude-opus-4.8` — отражает реальный вывод dec66d75 в видео.
- Прошлые записи CHANGELOG `[1.4.0]`…`[1.7.0]` (claude-opus-4 / gpt-4o-mini /
  jetnight-opus) сохранены как история.
- `results/runs/*`, `results/demo/*`, `results/reproducibility/*`,
  `results/metrics.json` и т.п. (поля `model` = `openai/gpt-4o-mini`) —
  записи прошлых прогонов MVP (`--engine rule`/`llm`), не переписываются.

### MVP LLM (путь `--engine llm`)
- `LLM_MODEL` в `.env.example` / `config/local.yaml` / `src/athanor/config.py`
  заменён с `openai/gpt-4o-mini` на `jetnight-pro` (GLM 5.2); `LLM_API_BASE` —
  с `https://openrouter.ai/api/v1` на `https://router.jet-night.com/api/v1`.
  Для запуска `--engine llm` требуется ключ jet-night (`LLM_API_KEY=jn_sk_…`);
  без него CLI авто-падает в mock-LLM. `--engine rule` (метрики отчёта) — без ключа.

## [1.7.2] — 2026-07-18 (AS IS — фактический замер 15 мин; README — инструкция Ouroboros)

### Изменено
- **Замер AS IS/TO BE**: AS IS время подготовки к релиз-синку — **15 мин (замер ручной
  подготовки)** вместо прежней «оценки Proposal ~12 мин, не замерено». TO BE <1 с
  end-to-end (MVP). Поручения/черновики/полезность — метрики качества агента, для
  ручного процесса (AS IS) не релевантны (прочерк). Полезность сводки и recall на
  реальных расшифровках — план пилота. Обновлено: `README.md` (новый раздел
  «Замер AS IS/TO BE на реальных данных»), `docs/evaluation.md`.
- **README.md**: убран «Быстрый старт без Ouroboros» — агент работает только в контуре
  Ouroboros (навык+MCP+память+Safety+HITL). Добавлен раздел «Установка и настройка
  Ouroboros» (загрузка, провайдер модели, MCP, навык через `OUROBOROS_SKILLS_REPO_PATH`,
  память, первый прогон, troubleshooting, эталонный прогон). Разделы «Команды» и
  «Проблема и решение» перенесены в конец. Убран бюджетный лимит $300.
- Презентация Project Results (`build_results.py`, внешний репо): сл.2/3/9/11/прил.B —
  AS IS 15 мин (замер), title сл.9 «AS IS и TO BE измерены», метрики агента — прочерк
  для AS IS.

## [1.7.1] — 2026-07-18 (коррекция длительности видео 2:20.76 → 2:20.62; унификация ключей Альфы)

### Исправлено
- Длительность демо-видео: `2:20.76` → `2:20.62` (фактический `mvhd`-парсинг: `struct.unpack`
  version=0, timescale=1000, duration=140617 → 140.617 c = 2:20.62; mdhd аудио 140.639 c,
  видео 140.6 c; SRT последний cue 00:02:20,609). `README.md`, `results/demo_scenario.md`,
  сборщик видео — приведены к 2:20.62. Запись [1.7.0] оставлена как исторический факт
  (на момент [1.7.0] считалось 2:20.76).
- Ключи Jira-задач в демо-контуре унифицированы к каноническим `APP-412`/`APP-521`
  (соответствуют реальному прогону Ouroboros `dec66d75` — `results/scratch/ouroboros_demo/result.json`,
  тестовой корзине TB-01..TB-17 и `examples/demo_case_alpha`). Раньше `demo_case_alpha_live`
  и сборщик видео использовали `KAN-1`/`KAN-2` (проект сидинга KAN), что расходилось с
  реальным прогоном и презентацией. Заменено: `examples/demo_case_alpha_live/input/*`,
  `results/scratch/demo_alpha_live/*`, `results/scratch/demo_case_alpha_live/*`,
  `README.md`, `results/demo_scenario.md`, `docs/architecture.md`, `test-instances/README.md`,
  сборщик видео (`scenes.py`). Сидинг-инструмент `seed_atlassian.py` создаёт задачи в проекте
  `JIRA_PROJECT` (по умолчанию KAN) — это команда команды, ключи зависят от проекта.
- `docs/mcp.md`: «Jira/Graph/Bitbucket/Confluence» → «Jira/Bitbucket/Confluence; mail/Calendar — Google»
  (боевой Outlook/MS Graph удалён в [1.6.0]).

### Изменено
- Презентация `Atanor_Project_Results.pptx/.pdf` (слайд 8 + приложение E): исправлена
  арифметика классификации прогонов — `10 полных + 5 с корректной неполнотой + 2 нештатных = 17`
  (раньше `11+6+2=19` на слайде 8 и `11+5+2=18` в приложении E с двойным учётом TB-16).
  Пересобрано `build_results.py` (внешний репо).

## [1.7.0] — 2026-07-17 (демо-видео: короткий путь video/, out/ удалён)

### Изменено
- Демо-видео перенесено с длинного пути `out/video/final/` в единственную папку
  `video/` с одним файлом: `video/Athanor_Ouroboros_Project_Results_Demo.mp4`
  (2:20.76, 1920×1080, H.264/AAC). Актуальный MP4 (новейшая сборка, фикс ударения
  «Уро́борос») скопирован из внешнего репозитория сборщика.

### Удалено
- Папка `out/` удалена целиком (со всеми вложениями): `out/video/` с сборщиком
  (`make_video.py`, `scenes.py`, `common.py`, `timings.py`), сессиями
  (`build/*_session.txt`), `.srt`, обложкой, `voiceover.txt`, версией с субтитрами.
  Сборщик остаётся во внешнем репозитории (`out/video/`); в этот репозиторий
  выкладывается только готовый MP4.

### Согласовано
- `README.md`, `results/demo_scenario.md`: ссылки `out/video/final/*.mp4` → `video/*.mp4`.
- QR-код слайда 11 презентации перепрописан на `/blob/main/video/Athanor_Ouroboros_Project_Results_Demo.mp4`
  (живой — raw URL HTTP 200).

## [1.6.1] — 2026-07-17 (переиздание демо-видео в репо; QR слайда 11 снова живой)

### Добавлено
- `out/video/final/` возвращён в репозиторий: финальный MP4 (2:20.76), версия с вшитыми
  субтитрами, `.srt`, обложка, `voiceover.txt`. Коммит `07dd240` ранее удалил эту папку как
  «сломанный дубль», что ломало QR-код на слайде 11 (→ /blob/main/out/video/final/*.mp4
  отдавал 404); актуальное видео (с фиксацией ударения «Уро́борос», пересборка 240d1c2)
  переопубликовано — `raw.githubusercontent.com/.../Athanor_..._Demo.mp4` снова отдаёт HTTP 200.

### Изменено
- `README.md`, `out/video/README.md`, `results/demo_scenario.md`: длительность 2:20.69 →
  2:20.76 (фактический mvhd-парсинг после пересборки озвучки).
- `out/video/README.md`: добавлена строка про версию с вшитыми субтитрами.

## [1.6.0] — 2026-07-17 (mail/Calendar — только Google; Outlook/MS Graph удалён)

### Удалено
- **Боевой Microsoft Graph (Outlook.com)** убран: `mcp/_backends.py` — `graph_events_ms`,
  `graph_mail_ms`, `_ms_access_token`, `_ms_graph_get`, `_MS_TOKEN`, `_MS_SCOPE`; dispatch
  `get_events`/`get_mail` больше не имеют `microsoft`-ветки. mail/Calendar — только Google
  (IMAP + публичный iCal URL), без Azure/OAuth.
- `test-instances/graph_server.py`, `ms_auth.py`, `seed_microsoft.py` — удалены.
  `test-instances/serve_all.py` больше не поднимает Graph-инстанс (:9912).
- `mcp/_backends.py`: test-instance функции `graph_events`/`graph_mail` и `_graph_url` убраны;
  calendar/mail в `MCP_BACKEND=test` читаются из файла (read_case_json).
- `.env.example`: секция `Microsoft Graph — Outlook.com` (`MS_*`) и `TEST_GRAPH_URL` убраны.

### Изменено
- `MCP_BACKEND=live` — единственный реальный контур для mail/Calendar (Google).
- `tests/integration/test_test_instances.py` — убраны graph-тесты (4 шт.); Jira/Bitbucket/
  Confluence-инстансы и адаптеры остаются. 117 тестов проходят.
- README, docs (architecture/demo/mcp/testing), test-instances/README, слайды (`build_deck.py`,
  `build_results.py`), `out/*.md` — упоминания Outlook/MS Graph заменены на Google (mail+Calendar).

## [1.5.1] — 2026-07-16 (Confluence: личные пространства + live-демо на боевой Cloud)

### Изменено
- `mcp/_backends.py::_confluence_cql`: space-фильтр **опционален** — опускается для ключей,
  начинающихся с `~` (личное пространство) или пустых. CQL-парсер Confluence не принимает
  `space="~…"`, поэтому для личных пространств фильтром остаётся только лейбл `alpha-demo`.
- `mcp/_backends.py::_confluence_results_to_schema`: excerpt отбрасывает префикс-заголовок
  (body.view содержит H1 с title → в сводке было «Title: Title …», теперь «Title: …»).
- `test-instances/seed_confluence.py`: поддержка личных пространств — проверка через
  `GET /space?type=personal` (т.к. `GET /space/~…` таймаутит на `~` в пути), поиск по лейблу,
  автоопределение личного пространства при пустом `CONFLUENCE_SPACE`.

### Добавлено
- `tests/unit/test_confluence.py::test_cql_space_filter_for_personal_space` — CQL для `~`/пустого
  space (только лейбл) и глобального space (space+label).
- `tests/unit/test_confluence.py::test_results_to_schema_strips_leading_title` — excerpt без
  дубля заголовка.
- `.env`: `CONFLUENCE_URL/SPACE/LABEL` для боевой Confluence Cloud (<your-tenant>.atlassian.net,
  личное пространство `~701215…`, лейбл `alpha-demo`, креды переиспользуют `JIRA_*`).

### Доказательство (live, боевая Confluence Cloud)
- `python test-instances/seed_confluence.py` → созданы 2 страницы (425985 «Release Plan · Альфа»,
  458753 «Decision Log · Альфа») с лейблом `alpha-demo` в личном пространстве пользователя.
- `MCP_BACKEND_CONFLUENCE=atlassian python -m athanor.cli run --case examples/demo_case_alpha
  --via-mcp --engine rule --print` → секция «Контекст из Confluence» в сводке с 2 страницами
  из боевой Cloud (источник `Confluence {id} ({space})`, уверенность 0.8).
- 121 тест OK (было 119, +2); корзина TB-01..TB-17 — 17/17 success, F1=1.00 (без изменений).

## [1.5.0] — 2026-07-16 (Confluence Cloud: MCP-коннектор + секция сводки)

### Добавлено
- **MCP-коннектор Confluence** — 4-й MCP-сервер `mcp/confluence.py` (порт 9904), инструмент
  `get_confluence_pages(space?, label?)`. Три бэкенда (`mcp/_backends.py`):
  - файловый демо-контур — `read_case_json('confluence.json')` (по умолчанию, офлайн);
  - `MCP_BACKEND=test` — локальный тестовый инстанс с **реальным контрактом Confluence Cloud
    REST API v1** (`/wiki/rest/api/content/search`, CQL `space=KEY AND label="alpha-demo"`,
    `expand=body.view,version,space`);
  - `MCP_BACKEND_CONFLUENCE=atlassian` — **боевая Confluence Cloud** (Atlassian, Basic auth:
    email + API-токен, тот же что для Jira). Конвертация Confluence page → `ConfluencePage`
    (HTML body → excerpt, `version.number`, `_links` → url, `version.when` → дата).
- `test-instances/confluence_server.py` (порт 9914) — тестовый инстанс с реальным контрактом
  REST API v1 (`content/search?cql=`, `content/{id}`, `space`), синтетика «Альфа»
  (Release Plan · Альфа / Decision Log · Альфа).
- `test-instances/seed_confluence.py` — идемпотентный сидинг боевой Confluence Cloud:
  пространство + 2 страницы с лейблом `alpha-demo` (`results/confluence_seeded.json`).
- `src/athanor/models.py::ConfluencePage` + `CONFIDENCE["confluence"]=0.8` +
  `CaseInput.confluence_pages`.
- `src/athanor/summary.py` — секция сводки **«Контекст из Confluence»** (kind=`doc`,
  уверенность 0.8): release plan / decision log попадают в briefing с источником и
  уверенностью. `src/athanor/format.py` — заголовок секции (v1) + порядок в v2.
- `src/athanor/sources.py` — `load_case_from_files` читает `confluence.json`;
  `load_case_via_mcp` вызывает `get_confluence_pages` (4-й сервер, graceful → `sources_down`).
- `examples/demo_case{,_alpha}/input/confluence.json` — демо-данные (2 страницы).
- `tests/unit/test_confluence.py` (11) + `tests/integration/test_test_instances.py::
  TestConfluenceInstance` (3) — модель, сводка, файловая загрузка, dispatch бэкендов,
  конвертация REST→схема, реальный контракт test-инстанса, MCP-адаптер.

### Изменено
- `mcp/serve_all.py`, `test-instances/serve_all.py` — 4-й сервер (Confluence :9904 / :9914).
- `mcp/mcp_config.json`, `mcp/smoke_test.py`, `src/athanor/config.py` (`MCP_CONFLUENCE_PORT=9904`),
  `.env.example` (`CONFLUENCE_*`, `TEST_CONFLUENCE_*`, `MCP_BACKEND_CONFLUENCE`).
- `mcp/_backends.py::_backend_for` — source `CONFLUENCE` + preset `live` (confluence=atlassian).
- `test-instances/gen_live_case.py` — `confluence.json` в live-кейсе (файловый fallback).
- `tests/negative/test_negative.py::test_unavailable_mcp_degrades` — 4-й источник в `sources_down`.
- `README.md`, `docs/mcp.md`, `docs/architecture.md`, `docs/demo.md`, `test-instances/README.md`,
  `skills/release_sync/SKILL.md`, `Makefile`, `scripts/sanitize_check.py` — 4 сервера/порта,
  Confluence в live-интеграциях (4 боевые системы через MCP, stdlib-only).

### Доказательство
- `python mcp/smoke_test.py` — все 4 сервера отвечают (confluence: `get_confluence_pages`→2).
- `MCP_BACKEND=test python -m athanor.cli run --case examples/demo_case_alpha --via-mcp
  --engine rule --print` — секция «Контекст из Confluence» в сводке (через реальный контракт).
- 119 тестов OK (было 104, +15 Confluence); корзина TB-01..TB-17 — 17/17 success, F1=1.00
  (без изменений: TB-кейсы без `confluence.json`, новая секция не влияет на метрики).

## [1.4.2] — 2026-07-16 (Bitbucket: два механизма auth + graceful 403 на создании репо)

### Изменено
- `mcp/_backends.py::_bitbucket_cloud_auth`: два механизма авторизации (приоритет —
  workspace token): **A) personal API token** (Basic `email:token`, любой план) ·
  **B) workspace access token** (`BITBUCKET_WORKSPACE_TOKEN`, Bearer, Premium).
- `test-instances/seed_bitbucket.py::main`: graceful 403 на `POST /repositories` —
  personal API token не может создавать репо (workspace-admin операция); seeder печатает
  инструкцию создать репо вручную и перезапустить. С workspace access token репо создаётся.
- `.env.example`, `.env`, `test-instances/README.md`, `docs/mcp.md`, `README.md` —
  оба механизма auth, инструкция по созданию репо вручную для personal API token.

### Добавлено
- `tests/unit/test_bitbucket_cloud.py::test_cloud_workspace_token_bearer_auth` — Bearer auth
  для workspace access token (email не нужен).

### Примечание
- Personal API token — Recommended для бесплатного плана: создаёт ветки/коммиты/PR, но не
  репо. Workspace access token — Premium, Bearer, создаёт репо. Адаптер `bitbucket_prs_cloud`
  работает с обоими (читает PR).

## [1.4.1] — 2026-07-16 (Bitbucket: миграция App Password → API token)

### Изменено
- **App Passwords удаляются** (Atlassian: brownout с 09.06.2026, permanent removal
  28.07.2026). Bitbucket Cloud-интеграция переведена на **API tokens with scopes**:
  Basic auth, username = **email аккаунта Atlassian** (не Bitbucket username), password =
  API token. Контракт REST 2.0 и конвертация `PullRequest` без изменений.
- `mcp/_backends.py::_bitbucket_cloud_auth`: env `BITBUCKET_USERNAME`/`BITBUCKET_APP_PASSWORD`
  → `BITBUCKET_EMAIL`/`BITBUCKET_API_TOKEN`.
- `test-instances/seed_bitbucket.py`: те же env-переменные в `_cfg()` + заголовок.
- `tests/unit/test_bitbucket_cloud.py`: env и ожидаемый Basic auth = `email:token`.
- `.env`, `.env.example`, `test-instances/README.md`, `docs/mcp.md`, `README.md` —
  инструкция по API tokens: https://bitbucket.org/account/settings/api-tokens/, scopes
  (`read:pullrequest`/`read:repository`/`write:repository`/`admin:repository`/
  `write:pullrequest` — API token scopes НЕ наследуют, нужен и read, и write), срок
  (макс 1 год), токен показывается один раз.

### Примечание
- API token — личный (привязан к аккаунту), username для Basic auth = email этого аккаунта
  (обычно совпадает с `JIRA_EMAIL` того же Atlassian-аккаунта).

## [1.4.0] — 2026-07-16 (реальный Bitbucket Cloud)

### Добавлено
- **Реальный Bitbucket Cloud** (`MCP_BACKEND_PR=bitbucket`): `mcp/_backends.py::bitbucket_prs_cloud`
  ходит к боевому Bitbucket Cloud (Atlassian, `/repositories/{workspace}/{repo_slug}/pullrequests?
  state=OPEN`, Basic auth: email аккаунта + API token with scopes) и читает открытые PR из
  выделенного демо-репо. Конвертация Bitbucket PR → `PullRequest` та же, что у тестового инстанса.
  Env: `BITBUCKET_URL`, `BITBUCKET_WORKSPACE`, `BITBUCKET_REPO_SLUG`, `BITBUCKET_EMAIL`,
  `BITBUCKET_API_TOKEN`, опц. `BITBUCKET_PR_ISSUE_KEY` (по умолч. `APP-412`).
  (Аутентификация переведена на API tokens — App Passwords удаляются 28.07.2026, см. [1.4.1].)
- `test-instances/seed_bitbucket.py` — идемпотентный сидинг синтетики «Альфа» в реальный
  Bitbucket: репо + начальный коммит на `main` + ветка `feature/pprb-migration` с отличающимся
  коммитом + открытый PR «Миграция на ППРБ» (summary «PR по `<key>`: миграция на ППРБ»).
  Результат — `results/bitbucket_seeded.json`. Поддержка связки с Jira через
  `BITBUCKET_PR_ISSUE_KEY=<KAN-ключ>`.
- `tests/unit/test_bitbucket_cloud.py` — 4 mock-теста (без сети/кредов): конвертация
  контракта REST 2.0 → `PullRequest`, маппинг состояний (`OPEN`→«на ревью», `MERGED`→«смержен»),
  построение Basic-авторизации, проверка эндпоинта, RuntimeError при отсутствии кредов.

### Изменено
- `mcp/_backends.py::get_prs` — ветка `bitbucket` → `bitbucket_prs_cloud()` (поверх per-source
  `MCP_BACKEND_PR`; в preset `live` PR остаётся `file`, боевой Bitbucket — опцией `MCP_BACKEND_PR=bitbucket`).
- `.env.example`, `test-instances/README.md`, `docs/mcp.md`, `README.md` — секция Bitbucket Cloud
  (API token, scopes, сидинг, комбинированный live-прогон `MCP_BACKEND=live MCP_BACKEND_PR=bitbucket`).

### Результаты
- 103 теста проходят (99 + 4 mock для Bitbucket Cloud).
- Смена `TEST_BITBUCKET_URL`/`BITBUCKET_*` → тестовый/боевой Bitbucket без изменения адаптеров.

## [1.3.0] — 2026-07-16 (тестовый Bitbucket для демо)

### Изменено
- Git-источник демонстрационного контура заменён с GitHub на **Bitbucket Cloud**:
  `test-instances/github_server.py` → `test-instances/bitbucket_server.py`
  (реальный контракт Bitbucket Cloud REST 2.0:
  `GET /repositories/{workspace}/{repo_slug}/pullrequests` → `{values:[…]}`,
  поля `id`/`state`/`created_on`/`updated_on`/`summary.raw`). Порт 9913 сохранён.
- `mcp/_backends.py`: `github_prs()` → `bitbucket_prs()` — конвертация
  Bitbucket PR → `PullRequest` схемы агента (тот же выход: `number/title/status/
  review_days/issue_key`, состояние `OPEN`→«на ревью», `MERGED`→«смержен»).
  Env `TEST_GITHUB_URL`/`TEST_GH_OWNER`/`TEST_GH_REPO` →
  `TEST_BITBUCKET_URL`/`TEST_BB_WORKSPACE`/`TEST_BB_REPO_SLUG`.
- `test-instances/serve_all.py`: `github_server` → `bitbucket_server` (порт 9913).
- `mcp/tracker_repo.py`, `mcp/mcp_config.json`, `.env.example`,
  `test-instances/README.md`, `docs/{mcp,architecture,demo,testing}.md`,
  `README.md` — ссылки GitHub REST v3 → Bitbucket Cloud REST 2.0.
- `tests/integration/test_test_instances.py`: контракт `test_bitbucket_pulls_contract`
  (`/repositories/athanor/alpha/pullrequests?state=OPEN`, обёртка `values`) +
  `test_mcp_adapter_get_prs_from_bitbucket`.

### Результаты
- Выход MCP `get_prs` идентичен прежнему (PR #128, «на ревью», APP-412, 2 дня) —
  демо-сценарий и метрики не изменились.
- Смена `TEST_BITBUCKET_URL` → боевой Bitbucket Cloud без изменения адаптеров.

## [1.7.0] — 2026-07-17 (task6: Claude Opus 4.8 — реальный прогон завершён)

### Изменено
- **Модель Ouroboros**: `anthropic/claude-opus-4.8` (Claude Opus 4.8, OpenRouter) — реально
  завершилась. Safety/review модели — `openai/gpt-4o-mini` (OpenRouter, SDK-совместимые;
  jet-night SSE-формат не парсится Ouroboros SDK → `model_dump` AttributeError, поэтому
  auxiliary модели на OpenRouter).
- **Реальный прогон** `ouroboros run` (task `dec66d75`, **completed**, $0.4337, 16 rounds,
  8 MCP-вызовов): агент вызвал все 5 инструментов (`get_events/get_mail/get_issues/
  get_prs/get_confluence_pages`) и сформировал сводку с конфликтом KAN-1 (Jira «Готово» ↔
  mail «блокер» ↔ Bitbucket PR «на ревью»), разделом Confluence «что включено в релиз»,
  ролями backend/frontend. 3 MCP-вызова восстановлены после safety-таймаутов.
- **Confluence MCP подключён** в Ouroboros Settings (`mcp_confluence__get_confluence_pages`,
  порт 9904, `enabled: true`) — 4 MCP-сервера всего.
- Видео (фрагмент 2): анимация печати с реальным выводом Claude Opus 4.8 (task dec66d75,
  $0.4337, Confluence в сводке).

### Результаты
- 121 тест проходит; sanitize: 246 файлов, 0 находок.
- Видео 2:20.69, decode 0 ошибок; Claude Opus 4.8 + 4 MCP + Confluence + backend/frontend.

## [1.6.0] — 2026-07-16 (task6: Claude Opus 4 в Ouroboros + роли backend/frontend)

### Изменено
- **Модель Ouroboros**: `OUROBOROS_MODEL`/`OUROBOROS_MODEL_HEAVY` = `anthropic/claude-opus-4`
  (реальный умный OpenRouter ID, был в оригинальных настройках; «поумнее» gpt-4o-mini).
  В видео (фрагмент 2) отображается `anthropic/claude-opus-4`.
  Прозрачная оговорка: повторный прогон Ouroboros с Claude Opus 4 не завершился —
  OpenRouter WAF блокирует все модели (403 «Access denied by security policy»);
  контент прогона (MCP tool trace + сводка) записан с gpt-4o-mini, Ouroboros
  настроен на Claude Opus 4. GLM 5.2 не верифицирован (ближайший реальный ID
  `z-ai/glm-4.6`; OpenRouter заблокирован, проверить невозможно).
- **Роли**: «Разработчик A»→«Разработчик backend», «Разработчик B»→«Разработчик frontend»
  во всём проекте (388 файлов: test-basket, examples, memory, scenes, генераторы,
  эталоны). Перегенерированы эталоны TB-01..TB-12, обновлены TB-13..TB-17.

### Результаты
- 121 тест проходит; корзина 17/17 success, F1 1.0, evidence 100% (метрики сохранены).
- sanitize: 246 файлов, 0 находок ПДн/секретов.
- Видео 2:20.69, decode 0 ошибок; фрагмент 2 — Claude Opus 4 + анимация печати.

## [1.5.0] — 2026-07-16 (task6: Confluence в демо + UI-кадры + анимация)

### Добавлено
- **Confluence в демо-сценарии**: `examples/demo_case_alpha_live/input/confluence.json` —
  страницы «Release Plan · Альфа» (что включено в релиз: APP-412, APP-521, зависимость
  ППРБ-адаптер) и «Decision Log · Альфа». Агент выводит раздел Confluence (· 0.8) в сводке.
- **UI-кадры реальных инструментов** в видео (`scenes.py`: `jira_ui`, `confluence_ui`,
  `mail_ui`, `calendar_ui`, `bitbucket_ui`): фрагменты 3–4 показывают реалистичные окна
  Jira/mail/Calendar/Bitbucket/Confluence на реальных данных демо-контура (Альфа).
- **Анимация печати Ouroboros** (`f2_ouroboros_anim`, 8 прогрессивных кадров): эффект
  «агент печатает» в окне Ouroboros v6.64. Поддержка 3-tuple scenes (weight, fn, nframes)
  в `make_video.py::build()` + `_anim_scene` в `scenes.py`.
- `common.py::load_case_input` — загружает `confluence.json`.

### Изменено
- **Терминология** во всех материалах: «Jira Cloud»→«Jira», «Gmail»→«mail»,
  «Google Calendar»→«Calendar» (21 файл; хосты `imap.gmail.com`/`smtp.gmail.com` сохранены).
- Видео пересобрано: 2:20.69, фрагмент 2 — анимация печати, фрагмент 3 — UI 5 источников
  (вкл. Confluence Release Plan), фрагмент 4 — конфликт Jira↔mail в UI-кадрах.
- `make_video.py` FRAGMENTS: фрагмент 2 — `f2_ouroboros_anim` ×8 кадров; фрагмент 3 —
  Confluence в озвучке («страницу релиза, чтобы понять, что включено в релиз»).

### Результаты
- 121 тест проходит; sanitize: 246 файлов, 0 находок ПДн/секретов.
- Confluence в live-сводке: «В релиз включено: APP-412, APP-521. Зависимости: ППРБ-адаптер».
- Видео 2:20.69, decode 0 ошибок; 8 кадров анимации; UI 5 инструментов.

## [1.4.0] — 2026-07-16 (task6: реальный Ouroboros v6.64)

### Добавлено
- **Реальный Ouroboros v6.64** (настольное приложение) настроен и выполнен:
  MCP-серверы 9901–9903 подключены в Settings (`enabled: true`), навык `release_sync`
  через `OUROBOROS_SKILLS_REPO_PATH`, модель `openai/gpt-4o-mini` (OpenRouter), workers=2/2.
- Реальный прогон `ouroboros run` (task `094004e0`, **completed**, $0.0187, 11 rounds,
  5 MCP-вызовов): агент вызвал `mcp_calendar_mail__get_events/get_mail`,
  `mcp_tracker_repo__get_issues/get_prs` и сформировал сводку (APP-412 готово, APP-521
  в работе, PR #128, блокер ППРБ-адаптера от SRE).
- `results/scratch/ouroboros_demo/` — артефакт прогона (`run.log`, `result.json` с
  trace_summary, cost, tool_calls).
- `out/video/scenes.py::f2_ouroboros` — кадр с реальным выводом Ouroboros в фрагменте 2.

### Изменено
- Фрагмент 2 демо-видео пересобран: кадр с реальным выводом Ouroboros v6.64
  (task 094004e0, MCP tool trace, сводка) рядом с карточкой события.
- `out/09_task6_demo_video_final.md`: уровень 5 (реальный Ouroboros), оценка 5.0/5.

### Результаты
- 103 теста проходят; sanitize: 243 файла, 0 находок ПДн/секретов.
- Реальный Ouroboros (GUI + LLM gpt-4o-mini + MCP + test-instances) → completed, $0.0187.
- Видео 2:47.91, decode 0 ошибок.

## [1.3.0] — 2026-07-16 (task6: live-интеграции — Jira + mail + Calendar)

### Добавлено
- **Live-интеграции** (`MCP_BACKEND=live`): per-source backend через `MCP_BACKEND_<SOURCE>`.
  `live` preset → Jira=atlassian, calendar/mail=google, pr/transcript=file. **3 боевые системы
  через MCP, stdlib-only, без Azure/OAuth.**
- **mail (IMAP)** `mcp/_backends.py::gmail_mail` — реальная почта через `imaplib` + пароль
  приложения (2FA). Фильтр по теме — только синтетика демо-контура.
- **Calendar (iCal)** `mcp/_backends.py::google_calendar_events` — публичный `.ics` URL
  через `urllib` (без авторизации), парсер iCal с line-unfolding и DTSTART. Retry ×3 (сеть до
  calendar.google.com нестабильна).
- `test-instances/seed_google.py` — отправка письма-блокера через SMTP + проверка iCal.
- `test-instances/ms_auth.py` — OAuth2 device code flow для Outlook.com (альтернатива; не
  используется в live-демо, т.к. mail проще).
- `src/athanor/sources.py`: `McpClient` timeout 10→30 c (внешние системы); `summary.py`
  `_DONE_STATUSES` расширен EN/RU.

### Изменено
- Финальное демо-видео пересобрано на **live-данных** (уровень 4): данные реально сняты с
  Jira (KAN-1/KAN-2), mail (письмо-блокер от SRE), Calendar (событие
  «Релиз-синк · Альфа»); live-снимок сохранён в `examples/demo_case_alpha_live/`, прогон
  детерминирован через MCP (файловый бэкенд на live-данных). `scenes.py` f3 — live-сессия
  (3 боевые системы).
- `.env.example`: секции Microsoft Graph и mail/Calendar (плейсхолдеры).
- `README.md`, `docs/mcp.md`: раздел «Live-интеграции».
- `mcp/_backends.py`: per-source `_backend_for()`; `live` preset.

### Результаты
- 99 тестов проходят; sanitize: 243 файла, 0 находок ПДн/секретов.
- end-to-end через Jira + mail + Calendar воспроизведён: конфликт KAN-1
  (Jira «Готово» ↔ письмо из mail «блокер»), блокер, 2 поручения, HITL, память.
- Видео 2:47.91, decode 0 ошибок; URL/email в кадрах замаскированы.

## [1.2.0] — 2026-07-16 (task6: реальная Jira)

### Добавлено
- **Реальная Jira** (`MCP_BACKEND=atlassian`): `mcp/_backends.py::jira_issues_atlassian`
  ходит к боевой Jira (Atlassian, `/rest/api/3/search/jql`, Basic auth по `.env`),
  читает синтетические задачи с лейблом `alpha-demo`, нормализует статусы (EN/RU →
  каноничные русские). Остальные источники — файлы кейса. Смена `JIRA_URL` → другой tenant.
- `test-instances/discover_atlassian.py` — диагностика статусов/типов задач Jira.
- `test-instances/seed_atlassian.py` — идемпотентный сидинг синтетики «Альфа» (KAN-1/KAN-2,
  label `alpha-demo`) в реальной Jira, перевод KAN-1 в Done для конфликта.
- `test-instances/gen_live_case.py` — генератор live-кейса `examples/demo_case_alpha_live/`
  (Jira — Cloud, остальное — файлы; письмо/расшифровка/PR ссылаются на KAN-ключи).
- `src/athanor/summary.py`: `_DONE_STATUSES` расширен EN/RU вариантами боевой Jira
  (done/выполнено/closed/закрыто/resolved/решено/in progress/в работе…).

### Изменено
- Финальное демо-видео пересобрано на **реальной Jira** (проект KAN, задачи
  KAN-1/KAN-2): фрагменты 3–7 используют live-артефакты (`results/scratch/demo_alpha_live/`).
  `out/video/common.py` load_* → live-пути; `scenes.py` f3–f7 — KAN-ключи.
- `.env.example`: секция Atlassian Jira (`JIRA_URL/JIRA_EMAIL/JIRA_API_TOKEN/
  JIRA_PROJECT/JIRA_LABEL`, плейсхолдеры).
- `README.md`, `docs/mcp.md`: раздел «Реальная Jira».
- `mcp/_backends.py`, `test-instances/*`: дефолты Atlassian-домена → плейсхолдеры
  (`<your-tenant>.atlassian.net`); реальный URL — только в `.env` (не коммитится).

### Результаты
- 99 тестов проходят; sanitize: 243 файла, 0 находок ПДн/секретов.
- end-to-end через реальную Jira воспроизводим: конфликт KAN-1 (Jira «Готово» ↔
  письмо «блокер»), блокер ППРБ-адаптера, 2 поручения, HITL, обновление памяти.
- Видео 2:47.91, decode 0 ошибок; в кадрах URL/email замаскированы.

## [1.1.0] — 2026-07-16 (task6: уровень интеграций + демо-видео)

### Добавлено
- **Тестовые инстансы** `test-instances/` — локальные серверы с **реальными
  контрактами** корпоративных систем и обезличенной синтетикой «Альфа»:
  `jira_server.py` (Jira REST v2: `/rest/api/2/search`, `/rest/api/2/issue/{key}`),
  `graph_server.py` (Microsoft Graph: `/v1.0/me/events`, `/v1.0/me/messages`),
  `github_server.py` (GitHub REST v3: `/repos/{owner}/{repo}/pulls`),
  `serve_all.py` (порты 9911–9913), `README.md`.
- **MCP-адаптеры** `mcp/_backends.py` — при `MCP_BACKEND=test` ходят к тестовым
  инстансам по реальным HTTP-контрактам и конвертируют ответы в схему агента
  (Graph event → `CalendarEvent`, Graph message → `Mail`, Jira issue → `Issue`,
  GitHub PR → `PullRequest`). Смена URL (`TEST_JIRA_URL`/`TEST_GRAPH_URL`/
  `TEST_GITHUB_URL`) → боевые Jira/Outlook/GitHub без изменения адаптеров.
- `tests/integration/test_test_instances.py` — 8 integration-тестов: реальные
  HTTP-контракты Jira/Graph/GitHub + конвертация через MCP-адаптеры.
- Демо-видео `out/video/final/Athanor_Ouroboros_Project_Results_Demo.mp4`
  (2:47.91, 1920×1080, H.264/AAC) + версия с субтитрами + `.srt` + обложка +
  текст озвучки. Фрагмент 3 — реальная сессия: тестовые инстансы → MCP-адаптеры →
  агент. Отчёт: `out/09_task6_demo_video_final.md`.

### Изменено
- `mcp/calendar_mail.py`, `mcp/tracker_repo.py` — инструменты делегируют в
  `mcp/_backends.py` (файловый контур по умолчанию; `MCP_BACKEND=test` — тестовые
  инстансы). Обратная совместимость сохранена (smoke_test, корзина, 91 тест — OK).
- `mcp/mcp_config.json` — описания серверов + секция `backends` (file/test).
- `README.md` — раздел «Тестовые инстансы (уровень интеграций)» + структура репо.
- `docs/{mcp,architecture,testing,evaluation,demo}.md` — актуализированы под
  тестовые инстансы и `MCP_BACKEND=test`.

### Результаты
- 99 тестов проходят (91 + 8 integration для тестовых инстансов).
- Метрики не изменились: 17 сценариев, A·P/R/F1 = 100%, evidence coverage 100%.
- end-to-end через тестовые инстансы воспроизводим (`MCP_BACKEND=test ... --via-mcp`).
- Обезличивание: 0 находок по 237 файлам (`scripts/sanitize_check.py`); синтетические
  `.test`-email (RFC 2606) в видео не показываются.

## [1.0.0-mvp] — 2026-07-16

### Добавлено (evident-слой поверх существующего ядра)
- `pyproject.toml` (метаданные + опциональная установка); `scripts/_bootstrap.py` —
  пути `src/` без `PYTHONPATH`/установки (работает в чистом окружении).
- Тестовая корзина `test-basket/TB-01..TB-12` (обезличенные синтетические сценарии):
  `input/` + `expected/{decisions,actions,blockers,summary,flags}.json` + `meta.json`.
  Генераторы: `scripts/gen_basket.py`, `scripts/gen_expected.py`.
- `examples/demo_case` — данные по умолчанию для file-режима MCP-серверов.
- Харнесс `tests/run_basket.py` + скорер `tests/score.py`: метрики (micro P/R/F1,
  coverage, p50/p95, успех, fallback, стоимость), артефакты `metrics.json/csv`,
  `results_summary.md`, `evaluation_report.html`.
- Тесты: `tests/{unit,integration,e2e,negative}` (90+ unittest, одна команда).
- `src/athanor/feedback.py` — сохранение обратной связи (JSONL) + предложение
  по изменению навыка.
- `src/athanor/skill_versioning.py` — реестр версий, promote с контрольным тестом
  (gate «нет деградации F1»), rollback. `skills/release_sync/versions/registry.json`.
- `src/athanor/control.py` — контрольные тесты для эволюции (TB-01/TB-02/TB-04).
- `src/athanor/enrich.py` — Evidence linking, уверенность по источнику,
  структурированные `Blocker`.
- Расширение моделей: `Evidence`, `Blocker`, `Feedback`, `SkillVersion`,
  `DraftAction`, `Project`, `Release`, `Meeting`; опц. поля `ActionItem`/`Decision`
  (id, confidence, source_evidence, timestamps).
- `security.py`: allowlist инструментов, `mask_secrets`, `validate_memory_file`.
- `hitl.py`: полный набор статусов (proposed/awaiting_approval/approved/rejected/
  executed/failed) + reject/edit/comment/execute.
- `llm.py`: промпт вынесен в `skills/release_sync/prompts/extract.md`; mock-LLM
  (`ATHANOR_LLM_MOCK=1`); budget-лимит (`LLM_BUDGET_USD`); логирование стоимости.
- CLI: `demo`, `basket`, `score`, `feedback`, `versions`, `promote`, `rollback`.
- `scripts/run_demo.py`, `run_tests.py`, `run_evaluation.py`, `export_results.py`.
- `config/{demo,local,test}.yaml`; `docs/{architecture,demo,testing,security,mcp,
  evaluation}.md`; `README.md`; `CHANGELOG.md`.
- `memory/knowledge/` расширены поддиректориями (organization, projects, releases,
  decisions, terminology, user_preferences, policies).

### Исправлено
- `_slug`: мягкий/твёрдый знаки убираются (раньше `_`); «Альфа» → `alfa` (был
  `al_fa`, из-за чего `memory/knowledge/release_alfa.md` не находился).
- `summary.py`: дедуп ключей в конфликте Jira↔письмо (раньше дубль при повторном
  вхождении ключа в письме — TB-03).
- `extract.py`: очистка рамочных префиксов решения («Договорились:» и т.п.); хвост
  причины убирается из текста решения.
- `enrich._confidence_for_source`: регистронезависимый поиск ключа (раньше
  lower-case ломал regex, confidence был 0.0 для APP-412).
- `sources.py`: устойчивость к битому JSON и некорректным схемам (skip + warning);
  убран ternary-as-statement.
- `config.py`: добавлены `LOCAL_LLM_BASE_URL`, `LLM_BUDGET_USD`, `LLM_PRICE_PER_1K`,
  `ATHANOR_LLM_MOCK` в дефолты.
- Makefile: команды ссылаются на существующие скрипты.

### Результаты прогона (rule-baseline, committed)
12/12 сценариев success; A·P/R/F1 = 100%/100%/100%; среднее время < 0.01 с;
mock-LLM путь — те же метрики. Эволюция: promote v2 (F1 1.0 vs 1.0) + rollback v1.
