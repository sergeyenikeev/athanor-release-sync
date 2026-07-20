# Отчёт по обезличиванию данных (task4 §26)

- Сканировано файлов: **772** в test-basket/, memory/, examples/, skills/, results/, test-instances/
- Каталоги проверки: 6
- Детекторов: 10 (ФИО, email, Jira ID, внутренние URL, токены/ключи/пароли, карты, телефоны, табельные)

## Выполненные проверки

- ФИО (реальные имена)
- Корпоративный email
- Реальный Jira ID
- Внутренний URL
- Боевой облачный URL (Atlassian tenant)
- Windows-путь с именем пользователя
- Токен/API-ключ/пароль
- Номер банковской карты
- Телефон
- Табельный номер

## Разрешённые синтетические маркеры (НЕ ПДн)

- Тимлид
- SRE
- Владелец продукта
- Разработчик backend
- Разработчик frontend
- Атакующий
- Альфа
- alpha-web
- alpha-api
- ППРБ-адаптер
- notification-service
- ALPHA-2026.07
- APP-
- OPS-
- PR #
- athanor-demo@gmail.com
- demo.atlassian.net
- <tenant>
- <user>

## Результат

⚠ Обнаружено **12** потенциальных совпадений:

### Номер банковской карты (12)
- `results\sanitization_report.md`: «5721722000162117»
- `results\sanitization_report.md`: «0975456000305712»
- `results\sanitization_report.md`: «0975456000305712»
- `results\sanitization_report.md`: «0975456000305712»
- `results\scratch\ouroboros_evolution_result.json`: «1279673565432325»
- `results\scratch\ouroboros_evolution_result.json`: «1279673565432325»
- `results\scratch\ouroboros_evolution_result.json`: «1279673565432325»
- `results\scratch\ouroboros_evolution_result.json`: «1279673565432325»
- `results\scratch\ouroboros_hitl_run3_result.json`: «4262362228767252»
- `results\scratch\ouroboros_hitl_run3_result.json`: «4262362228767252»
- `results\scratch\req_f464c226.json`: «5825808426019137»
- `results\scratch\req_f464c226.json`: «5825808426019137»


## Замены, выполненные при создании данных

- Реальные ФИО → роли (Тимлид, SRE, Владелец продукта, Разработчик backend/B)
- Реальные email → роли (from_role)
- Реальные Jira ID → вымышленные APP-/OPS-***
- Реальные URL → отсутствуют в репо (MCP-серверы 127.0.0.1:9901-9904; боевые URL — в .env, не в репо; tenant-URL заменены на `<tenant>` в results/)
- Реальные даты → 2026-07-* (синтетика)

## Вывод

Требуется доработка обезличивания (см. совпадения выше).