# -*- coding: utf-8 -*-
"""Сидинг KAN для записи видео: +18 осмысленных задач (label "alpha-demo").

Дополняет seed_atlassian.py (KAN-1 «Миграция схемы оплат», KAN-2 «Интеграция
с партнёром») до 20 задач в проекте KAN — доска выглядит «живой» в кадре.
Статусы разложены по колонкам: К выполнению / В работе / Готово.

Идемпотентно: задачи ищутся по summary среди alpha-demo, существующие
переиспользуются (создаются только недостающие).

Запуск: python test-instances/seed_kan_video.py
Требует .env: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip() if " #" in v else v.strip()
        os.environ.setdefault(k.strip(), v)


_load_env(REPO / ".env")


def _cfg():
    url = os.environ.get("JIRA_URL", "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    project = os.environ.get("JIRA_PROJECT", "KAN")
    label = os.environ.get("JIRA_LABEL", "alpha-demo")
    if not (url and email and token):
        sys.exit("JIRA_URL/JIRA_EMAIL/JIRA_API_TOKEN не заданы в .env")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json",
               "Content-Type": "application/json"}
    return url, headers, project, label


def _req(method, url, headers, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:500]}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


def _find_existing(url, headers, project, label):
    jql = f'project={project} AND labels="{label}" ORDER BY created ASC'
    s, body = _req("POST", f"{url}/rest/api/3/search/jql", headers,
                   {"jql": jql, "fields": ["summary", "status"], "maxResults": 100})
    if s not in (200, 201):
        sys.exit(f"[search] HTTP {s} {body}")
    return body.get("issues") or []


def _pick_issuetype(url, headers, project):
    s, body = _req("GET", f"{url}/rest/api/2/issue/createmeta?projectKeys={project}", headers)
    if s == 200 and isinstance(body, dict):
        projects = body.get("projects", [])
        if projects:
            names = {it.get("name", "") for it in projects[0].get("issuetypes", [])}
            for pref in ("Задание", "Задача", "Task", "История", "Story"):
                if pref in names:
                    return pref
            for it in projects[0].get("issuetypes", []):
                if not it.get("subtask"):
                    return it["name"]
    return "Task"


def _find_transition(url, headers, key, target_names):
    """Найти transition, ведущий в один из target_names (lowercase)."""
    s, body = _req("GET", f"{url}/rest/api/2/issue/{key}/transitions", headers)
    if s != 200:
        return None
    for tr in body.get("transitions", []):
        tgt = (tr.get("to") or {}).get("name", "").strip().lower()
        if tgt in target_names:
            return tr.get("id"), tr.get("to", {}).get("name")
    return None


_STATUS_TARGETS = {
    "в работе": {"в работе", "in progress", "выполняется"},
    "готово": {"готово", "done", "выполнено", "closed", "закрыто", "resolved", "решено"},
}

# 18 задач недели релиза ALPHA-2026.07 (миграция на ППРБ): backend / frontend /
# SRE / QA / документация. Статус "" = оставить в «К выполнению».
TASKS = [
    ("Репликация БД ППРБ в резервный ЦОД",
     "Настроить асинхронную репликацию базы ППРБ-ядра в резервный ЦОД. "
     "Целевой RPO — 5 минут, RTO — 30 минут. Проверить failover на стенде предпрода.",
     "в работе"),
    ("Вебхуки статусов оплат от партнёра",
     "Реализовать приём вебхуков partner-api об изменении статуса оплаты. "
     "Идемпотентность по event_id, ретраи с экспоненциальной задержкой, DLQ для битых событий.",
     "в работе"),
    ("Кэширование справочника тарифов",
     "Вынести справочник тарифов в in-memory кэш с TTL 10 минут и инвалидацией по событию. "
     "Снижает нагрузку на ППРБ-ядро на ~40% по данным профилирования.",
     "готово"),
    ("Реестр платежей и сверка с партнёром",
     "Ежедневный реестр платежей за сутки и автоматическая сверка с реестром партнёра. "
     "Расхождения — в отчёт для бухгалтерии, алерт при расхождении > 0,1%.",
     ""),
    ("Дашборд метрик бизнес-операций",
     "Собрать дашборд: успешность оплат, p95 времени проведения, конверсия по шагам. "
     "Источник — метрики ППРБ-адаптера, витрина для Владельца продукта.",
     ""),
    ("Мониторинг и алерты ППРБ-адаптера",
     "Health-check'и ППРБ-адаптера, алерты на error rate > 1% и p95 > 2 с. "
     "Маршрутизация в канал #alpha-oncall, эскалация на дежурного SRE.",
     "в работе"),
    ("Стенд предпрода для нагрузочного тестирования",
     "Развернуть стенд предпрода, идентичный prod по конфигурации ППРБ-ядра. "
     "Синтетические данные, изолированный контур partner-api (заглушка).",
     "готово"),
    ("Runbook релиза ALPHA-2026.07",
     "Пошаговый runbook релиза: code freeze, деплой, smoke, мониторинг, rollback-план. "
     "Окно релиза 18:00–20:00, пятница исключена по регламенту.",
     ""),
    ("Нагрузочное тестирование 100 RPS",
     "Прогнать нагрузочный сценарий 100 RPS на стенде предпрода: оплата, отмена, сверка. "
     "Критерий: p95 < 2 с, ошибки < 0,5%, без деградации connection pool.",
     ""),
    ("Ретраи и таймауты в ППРБ-адаптере",
     "Единая политика таймаутов (connect 2 с, read 5 с) и ретраев (3 попытки, jitter) "
     "для всех вызовов partner-api. Circuit breaker при недоступности партнёра.",
     "в работе"),
    ("Экран истории платежей в личном кабинете",
     "Экран истории платежей: фильтр по периоду и статусу, пагинация, выгрузка в CSV. "
     "Данные — из реестра ППРБ через новый read-API.",
     ""),
    ("Валидация форм ввода реквизитов",
     "Клиентская и серверная валидация реквизитов: контрольный ключ счёта, БИК по справочнику, "
     "маски ввода. Единые тексты ошибок из UI-kit.",
     "готово"),
    ("Миграция логов в централизованное хранилище",
     "Перевести логи ППРБ-ядра и адаптера в централизованное хранилище: структурированный JSON, "
     "trace_id сквозь все сервисы, retention 90 дней.",
     ""),
    ("Ротация секретов и API-ключей партнёра",
     "Перевести ключи partner-api в секрет-хранилище с автоматической ротацией раз в 30 дней. "
     "Убрать секреты из конфигов и переменных окружения в CI.",
     ""),
    ("Smoke-тесты ППРБ-ядра в CI",
     "Набор smoke-тестов ППРБ-ядра (оплата, отмена, статус) в пайплайне CI. "
     "Запуск на каждый merge в main, порог — 100% прохождение, время < 5 минут.",
     "в работе"),
    ("Release-notes и changelog ALPHA-2026.07",
     "Собрать release-notes по задачам релиза (миграция на ППРБ, интеграция с партнёром, "
     "репликация). Выложить changelog в Confluence, разослать команде.",
     ""),
    ("Фикс connection pool после инцидента 30.06",
     "Устранить исчерпание connection pool ППРБ-адаптера (инцидент 30.06, деградация 14:00–15:30): "
     "лимиты пула, keep-alive, метрика занятости пула на дашборд.",
     "готово"),
    ("Согласование окна релиза с SRE",
     "Согласовать окно релиза ALPHA-2026.07 с дежурным SRE: дата, состав дежурных, "
     "план отката. Зафиксировать решение в Confluence (Runbook · Релизы Альфа).",
     ""),
]


def main():
    url, headers, project, label = _cfg()
    print(f"=== Сидинг KAN для видео: {url} · project={project} · label={label} ===\n")

    existing = {i["fields"]["summary"]: i for i in _find_existing(url, headers, project, label)}
    print(f"[search] найдено {len(existing)} alpha-demo задач")

    issuetype = _pick_issuetype(url, headers, project)
    print(f"[createmeta] issue type: {issuetype!r}\n")

    created, reused = [], []
    for summary, description, status in TASKS:
        if summary in existing:
            key = existing[summary]["key"]
            print(f"[reuse]  {key}  «{summary}» [{existing[summary]['fields']['status']['name']}]")
            reused.append(key)
            continue
        s, resp = _req("POST", f"{url}/rest/api/2/issue", headers, {"fields": {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issuetype},
            "labels": [label],
            "description": description + "\n\n(Синтетическая задача проекта «Альфа», демо-контур Ouroboros.)",
        }})
        if s not in (200, 201):
            print(f"[create FAILED] «{summary}»: HTTP {s} {resp}")
            continue
        key = resp["key"]
        created.append(key)
        line = f"[create] {key}  «{summary}»"
        targets = _STATUS_TARGETS.get(status)
        if targets:
            tr = _find_transition(url, headers, key, targets)
            if tr:
                tid, tname = tr
                s2, _ = _req("POST", f"{url}/rest/api/2/issue/{key}/transitions", headers,
                             {"transition": {"id": tid}})
                line += f" → {tname!r} (HTTP {s2})"
            else:
                line += f" → transition в {status!r} не найден"
        print(line)

    print("\n=== Итог (alpha-demo задачи в KAN) ===")
    final = _find_existing(url, headers, project, label)
    by_status: dict[str, int] = {}
    for i in final:
        st = i["fields"]["status"]["name"]
        by_status[st] = by_status.get(st, 0) + 1
        print(f"  {i['key']}\t[{st}]\t{i['fields']['summary']}")
    print(f"\nВсего: {len(final)} · создано сейчас: {len(created)} · переиспользовано: {len(reused)}")
    print("По статусам: " + ", ".join(f"{k}: {v}" for k, v in by_status.items()))

    out = REPO / "results" / "kan_video_seeded.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"project": project, "url": url, "total": len(final),
         "created": created, "reused": reused,
         "issues": [{"key": i["key"], "summary": i["fields"]["summary"],
                     "status": i["fields"]["status"]["name"]} for i in final]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
