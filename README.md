# Локальный AI-агент (ProxyAI + LangChain)

Терминальный AI-агент, который понимает задачи на естественном языке и сам выбирает инструменты.

## Возможности (инструменты)

| Инструмент | Назначение |
|---|---|
| `web_search` | Поиск в интернете через DuckDuckGo (`ddgs`) |
| `get_weather` | Погода для любого города (геокодинг Open-Meteo + forecast, fallback на met.no) |
| `get_crypto_price` | Курс криптовалют через CoinGecko (без ключей) |
| `read_file` / `write_file` | Чтение и запись файлов |
| `run_terminal_command` | Безопасное выполнение команд (белый список: dir, ls, echo, type, cat, whoami, date, time, ver) |
| Память | История диалога сохраняется в `agent/memory.json` |

## Структура проекта

```
agent/
├── agent.py          # логика агента (ReAct-цикл поверх LLM)
├── tools.py          # инструменты (погода, крипта, поиск, файлы, терминал, память)
├── memory.json       # долговременная память агента
├── run.py            # CLI-интерфейс запуска агента
├── .env              # хранит OPENAI_API_KEY (создается из .env.example)
└── requirements.txt  # зависимости
venv/                 # виртуальное окружение (Python 3.12)
```

## Требования к версии Python

⚠️ **Важно:** для работы LangChain нужен **Python ниже 3.13** (проверено на 3.12.9).
Если у вас установлен Python 3.13 или выше:

```powershell
winget install Python.Python.3.11
python3.11 -m venv venv
```

## Установка и запуск

Из корня проекта (где лежит эта папка):

```powershell
# 1. Виртуальное окружение (если ещё не создано)
python -m venv venv

# 2. Зависимости
venv\Scripts\python.exe -m pip install -r agent\requirements.txt

# 3. Настройка ключа
copy agent\.env.example agent\.env
notepad agent\.env   # вставьте реальный ключ ProxyAI вместо sk-CHANGE_ME

# 4. Запуск агента
venv\Scripts\python.exe agent\run.py
```

Внутри `.env`:

```
OPENAI_API_KEY=sk-ваш_ключ_proxyapi
OPENAI_BASE_URL=https://api.proxyapi.ru/v1
OPENAI_MODEL=openai/gpt-4o-mini
```

Получить ключ: [proxyapi.ru](https://proxyapi.ru) → консоль → API-ключ → пополнить баланс.
Модель можно менять на любую доступную (`anthropic/claude-...`, `google/gemini-...`, `openai/gpt-4o` и т.д.).

## Примеры запросов

```
Вы: Какая погода в Москве?
Агент: Погода в городе Москва: температура 10.1°C, ветер 2.5 м/с, переменная облачность...

Вы: Сколько стоит Bitcoin в рублях?
Агент: Курс BITCOIN (RUB): 6 243 179 RUB

Вы: Найди информацию про LangChain
Агент: <резюме результатов поиска DuckDuckGo>

Вы: Сохрани заметку "купить молоко" в файл notes.txt
Агент: Записал ... в C:\...\notes.txt
```

Команды CLI: `/memory` — показать последние сообщения из памяти, `/exit` — выход.

## Как это работает

1. Запрос пользователя вместе с историей из `memory.json` передается в LLM (через ProxyAI).
2. Модель возвращает JSON-решение: `{thought, action{tool,args}, answer}`.
3. Если есть `action` — агент вызывает инструмент, добавляет результат в контекст и просит модель продолжить (до 5 шагов).
4. Если есть `answer` — ответ возвращается пользователю.
5. Обмен (вопрос + финальный ответ) сохраняется в `agent/memory.json`.
