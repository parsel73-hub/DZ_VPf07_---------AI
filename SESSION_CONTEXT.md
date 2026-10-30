# Контекст сессии: локальный AI-агент (ProxyAI + LangChain)

Дата: 30.10.2026

## Задача
Создать терминального AI-агента на базе ProxyAI (OpenAI-совместимый API) и LangChain, умеющего:
- искать в интернете (DuckDuckGo);
- получать погоду для любого города;
- узнавать курс криптовалют (CoinGecko);
- работать с файлами (чтение/запись);
- выполнять ограниченные команды терминала;
- сохранять историю диалога в memory.json.

## Состояние: ГОТОВО ✅
Проект создан, все инструменты протестированы живыми вызовами. Единственное, что осталось пользователю — вставить реальный ключ ProxyAI в `agent/.env`.

## Структура проекта
```
DZ_VPf07_локальныйAI/
├── README.md            # полная документация и инструкции
├── agent/
│   ├── agent.py         # ReAct-цикл поверх ChatOpenAI (ProxyAI)
│   ├── tools.py         # 6 инструментов + память
│   ├── run.py           # CLI (/memory, /exit)
│   ├── memory.json      # история диалога агента (пусто, ждёт запуска)
│   ├── .env             # OPENAI_API_KEY=sk-CHANGE_ME ← ЗАМЕНИТЬ НА РЕАЛЬНЫЙ КЛЮЧ
│   ├── .env.example
│   └── requirements.txt
└── venv/                # виртуальное окружение, Python 3.12.9
```

## Ключевые технические решения
1. **venv обязателен** — всё разворачивалось в `venv\` (пользователь просил «делай все в venv»).
2. **Python 3.12.9 подходит** под LangChain; проблема из замечания задания актуальна только для 3.13+. В системе также есть Python 3.14 (`python3`) — его использовать нельзя.
3. **Установленные версии**: langchain 0.3.30, langchain-openai 0.3.35, openai 2.54.0, ddgs 9.16.1, requests 2.34.2, python-dotenv 1.2.4.
4. **DuckDuckGo**: пакет `duckduckgo-search` переименован в `ddgs` — в tools.py импорт с fallback.
5. **Погода**: `api.open-meteo.com/v1/forecast` НЕдоступен из сети пользователя (SSL read timeout). Решение: геокодинг через Open-Meteo работает, forecast — основной запрос с таймаутом 8с + автоматический fallback на `api.met.no/weatherapi/locationforecast/2.0/compact` (обязательно заголовок `User-Agent: local-ai-agent-test/1.0`, иначе 403).
6. **ProxyAI**: base_url `https://api.proxyapi.ru/v1`, формат модели `вендор/имя` (по умолчанию `openai/gpt-4o-mini`). Документация: proxyapi.ru/docs.
7. **Формат решений LLM**: текстовый JSON `{thought, action{tool,args} | null, answer | null}`, парсер `_parse_json`. Обработаны 401 (просьба проверить ключ) и 402 (баланс).
8. **Безопасность терминала**: белый список dir, ls, echo, type, cat, whoami, date, time, ver.

## Результаты тестов
- get_weather('Москва') → met.no fallback: 10.1°C ✅
- get_crypto_price(bitcoin, rub) → 6 243 179 RUB ✅
- web_search('LangChain framework') → релевантные результаты ✅
- write_file/read_file ✅; rm запрещён ✅
- Полный цикл ask() дошёл до ProxyAI: 401 Invalid API Key (ключ тестовый — ожидаемо) ✅

## Как продолжить работу
```powershell
# 1. Вписать реальный ключ ProxyAI в agent\.env (вместо sk-CHANGE_ME)
notepad agent\.env
# 2. Запустить агента
venv\Scripts\python.exe agent\run.py
```

## Возможные следующие шаги (не начаты)
- Интеграция с реальным ключом и сквозной тест всех сценариев через CLI.
- Добавление strict json_schema режима вместо текстового JSON (константа TOOL_CALL_SCHEMA уже заготовлена в agent.py).
- Автоматическое резюме истории в поле "summary" memory.json.
