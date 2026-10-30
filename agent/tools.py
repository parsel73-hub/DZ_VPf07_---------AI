"""Инструменты агента: поиск, погода, криптовалюта, файлы, терминал."""

import json
import os
import subprocess

import requests
from langchain_core.tools import tool

# Белые списки для безопасного выполнения команд
ALLOWED_COMMANDS = {
    "dir", "ls", "echo", "type", "cat", "whoami", "date", "time", "ver",
}

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")


@tool
def web_search(query: str) -> str:
    """Поиск информации в интернете через DuckDuckGo. Используйте для вопросов о фактах, новостях, определениях."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return "Ошибка: пакет ddgs (duckduckgo-search) не установлен."
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, region="ru-ru"))
        if not results:
            return f"По запросу «{query}» ничего не найдено."
        lines = [f"Результаты поиска по запросу «{query}»:\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Без названия")
            url = r.get("href", "")
            body = r.get("body", "")
            lines.append(f"{i}. {title}\n   {url}\n   {body}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Ошибка при поиске: {e}"


def _geocode(city: str):
    """Преобразует название города в координаты через Open-Meteo Geocoding API."""
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "ru"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or []
    if not results:
        return None
    item = results[0]
    return item["latitude"], item["longitude"], item.get("name", city)


def _weather_symbol(code: str) -> str:
    """Условие погоды по коду symbol Met.no."""
    mapping = {
        "clearsky": "Ясно", "fair": "Переменная облачность",
        "fog": "Туман", "cloudy": "Пасмурно",
        "partlycloudy": "Переменная облачность",
        "lightrain": "Слабый дождь", "rain": "Дождь", "heavyrain": "Сильный дождь",
        "rainshowers": "Кратковременный дождь",
        "sleet": "Мокрый снег", "snow": "Снег", "snowshowers": "Кратковременный снег",
        "thundercloudy": "Гроза",
    }
    base = (code or "").split("_")[0]
    return mapping.get(base, code or "Неизвестно")


@tool
def get_weather(city: str) -> str:
    """Погода в городе. Параметр: название города (например «Москва»). Возвращает температуру, ветер и условия погоды."""
    try:
        geo = _geocode(city)
        if not geo:
            return f"Город «{city}» не найден."
        lat, lon, name = geo
        # Основной источник — Open-Meteo
        try:
            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                },
                timeout=8,
            )
            resp.raise_for_status()
            cw = resp.json().get("current_weather", {})
            weather_codes = {
                0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность",
                3: "Пасмурно", 45: "Туман", 48: "Изморозь", 51: "Морось",
                53: "Морось", 55: "Морось", 61: "Дождь", 63: "Дождь",
                65: "Сильный дождь", 71: "Снег", 73: "Снег", 75: "Снегопад",
                80: "Ливень", 81: "Ливень", 82: "Сильный ливень",
                95: "Гроза", 96: "Гроза с градом", 99: "Гроза с градом",
            }
            desc = weather_codes.get(cw.get("weathercode"), f"Код {cw.get('weathercode')}")
            return (
                f"Погода в городе {name} (текущая):\n"
                f"  Температура: {cw.get('temperature')} °C\n"
                f"  Ветер: {cw.get('windspeed')} км/ч\n"
                f"  Условия: {desc}\n"
                f"  Время наблюдения: {cw.get('time')}"
            )
        except Exception:
            pass
        # Запасной источник — Norcecast Met.no (без ключей)
        resp = requests.get(
            "https://api.met.no/weatherapi/locationforecast/2.0/compact",
            params={"lat": lat, "lon": lon},
            headers={"User-Agent": "local-ai-agent-test/1.0"},
            timeout=20,
        )
        resp.raise_for_status()
        ts = resp.json()["properties"]["timeseries"]
        now = ts[0]["data"]["instant"]["details"]
        symbol = ""
        for key in ("next_1_hours", "next_6_hours"):
            if key in ts[0]["data"]:
                symbol = ts[0]["data"][key]["summary"].get("symbol_code", "")
                break
        wind = now.get("wind_speed", "?")
        return (
            f"Погода в городе {name} (прогноз на сейчас, источник met.no):\n"
            f"  Температура: {now.get('air_temperature')} °C\n"
            f"  Ветер: {wind} м/с\n"
            f"  Влажность: {now.get('relative_humidity')}%\n"
            f"  Условия: {_weather_symbol(symbol)}\n"
            f"  Время: {ts[0]['time']}"
        )
    except Exception as e:
        return f"Ошибка при получении погоды: {e}"


@tool
def get_crypto_price(coin: str, currency: str = "usd") -> str:
    """Курс криптовалюты через CoinGecko. Параметры: coin — id монеты (bitcoin, ethereum, solana...), currency — валюта (usd, rub, eur)."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin.lower(), "vs_currencies": currency.lower()},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        coin_data = data.get(coin.lower())
        if not coin_data:
            return f"Монета «{coin}» не найдена. Примеры id: bitcoin, ethereum, solana."
        cur = currency.lower()
        price = coin_data.get(cur)
        if price is None:
            return f"Валюта «{currency}» не поддерживается для {coin}."
        return f"Курс {coin.upper()} ({cur.upper()}): {price:,} {cur.upper()}"
    except Exception as e:
        return f"Ошибка при получении курса: {e}"


@tool
def read_file(path: str) -> str:
    """Читает содержимое текстового файла по указанному пути."""
    try:
        full = path if os.path.isabs(path) else os.path.abspath(path)
        if not os.path.isfile(full):
            return f"Файл не найден: {full}"
        with open(full, "r", encoding="utf-8") as f:
            content = f.read()
        return f"Содержимое файла {full}:\n{content[:4000]}"
    except Exception as e:
        return f"Ошибка чтения файла: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Записывает текст в файл по указанному пути (создает директории при необходимости)."""
    try:
        full = path if os.path.isabs(path) else os.path.abspath(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Записано {len(content)} символов в файл {full}"
    except Exception as e:
        return f"Ошибка записи файла: {e}"


@tool
def run_terminal_command(command: str) -> str:
    """Выполняет разрешенную терминальную команду (безопасные утилиты: dir, ls, echo, type, cat, whoami, date, time, ver)."""
    parts = command.strip().split()
    if not parts:
        return "Пустая команда."
    base = parts[0].lower()
    if base not in ALLOWED_COMMANDS:
        return (
            f"Команда «{base}» запрещена политикой безопасности. "
            f"Разрешены только: {', '.join(sorted(ALLOWED_COMMANDS))}."
        )
    try:
        result = subprocess.run(
            command.strip(),
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        return (
            f"Команда: {command}\n"
            f"Код возврата: {result.returncode}\n"
            f"Вывод:\n{out[:3000] if out else '(пусто)'}\n"
            f"Ошибки:\n{err[:1000] if err else '(нет)'}"
        )
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"


def load_memory():
    """Загружает историю диалога из memory.json."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"history": [], "summary": ""}
    return {"history": [], "summary": ""}


def save_message(role: str, content: str):
    """Добавляет сообщение в историю и сохраняет её в memory.json."""
    mem = load_memory()
    mem["history"].append({"role": role, "content": content})
    # Ограничиваем историю последними 40 сообщениями
    mem["history"] = mem["history"][-40:]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


ALL_TOOLS = [
    web_search,
    get_weather,
    get_crypto_price,
    read_file,
    write_file,
    run_terminal_command,
]
