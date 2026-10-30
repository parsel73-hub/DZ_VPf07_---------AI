"""Логика агента: LLM (ProxyAI/OpenAI) + инструменты LangChain."""

import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools import ALL_TOOLS, load_memory, save_message

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SYSTEM_PROMPT = """Ты — локальный AI-агент с доступом к инструментам.

Доступные инструменты:
- web_search: поиск информации в интернете (DuckDuckGo).
- get_weather: погода для любого города.
- get_crypto_price: курс криптовалют через CoinGecko.
- read_file / write_file: чтение и запись файлов.
- run_terminal_command: безопасное выполнение ограниченного набора команд терминала.

Правила:
1) Анализируй задачу пользователя и выбирай подходящий инструмент.
2) Если данных недостаточно — задай уточняющий вопрос вместо догадок.
3) Отвечай понятно и структурированно, кратко резюмируя результат инструмента.
4) Не выдумывай данные, которых нет; если инструмент не сработал — честно сообщи об этом.
"""


def build_llm() -> ChatOpenAI:
    """Создает чат-модель через ProxyAI (OpenAI-совместимый API)."""
    api_key = os.getenv("OPENAI_API_KEY") or ""
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/v1")
    model = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
    if not api_key or api_key.startswith("sk-ваш"):
        raise RuntimeError(
            "OPENAI_API_KEY не настроен. Скопируйте agent/.env.example в agent/.env "
            "и вставьте реальный ключ ProxyAI."
        )
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )


def _history_messages():
    """Преобразует сохраненную историю диалога в сообщения LangChain."""
    msgs = []
    for item in load_memory().get("history", [])[-10:]:
        role = item.get("role")
        content = item.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content))
        elif role == "assistant":
            msgs.append(AIMessage(content))
    return msgs


def _run_tool(name: str, args: dict) -> str:
    """Вызывает инструмент по имени."""
    for t in ALL_TOOLS:
        if t.name == name:
            try:
                result = t.invoke(args)
                return str(result)
            except Exception as e:
                return f"Инструмент {name} завершился с ошибкой: {e}"
    return f"Неизвестный инструмент: {name}"


# Примечание: схема TOOL_CALL_SCHEMA ниже оставлена как пример для strict-json
# режима; в текущем цикле ask() используется текстовый JSON-промпт с парсером.
TOOL_CALL_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_decision",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Краткая reasoning-заметка"},
                "action": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "tool": {
                            "type": "string",
                            "enum": [t.name for t in ALL_TOOLS],
                        },
                        "args": {"type": "object"},
                    },
                    "required": ["tool", "args"],
                },
                "answer": {
                    "type": "string",
                    "nullable": True,
                    "description": "Финальный ответ пользователю (если инструмент не нужен)",
                },
            },
            "required": ["thought", "action", "answer"],
        },
    },
}


def ask(user_input: str, max_steps: int = 5) -> str:
    """Основной цикл: пользовательский запрос -> решения агента -> ответ."""
    llm = build_llm()
    save_message("user", user_input)

    messages = [SystemMessage(SYSTEM_PROMPT)] + _history_messages()

    for _ in range(max_steps):
        try:
            resp = llm.invoke(
                messages + [HumanMessage(
                    "Ответь строго JSON по схеме: "
                    '{"thought": str, "action": {"tool": str, "args": object} | null, '
                    '"answer": str | null}. '
                    "Если нужен инструмент — заполни action, answer=null. "
                    "Иначе — answer с готовым ответом."
                )]
            )
        except Exception as e:
            err_text = str(e)
            if "401" in err_text or "Authentication" in type(e).__name__:
                final = (
                    "Ошибка авторизации в ProxyAI/OpenAI: проверьте OPENAI_API_KEY "
                    "в файле agent/.env."
                )
            elif "402" in err_text:
                final = "Недостаточно средств на балансе ProxyAI (HTTP 402)."
            else:
                final = f"LLM недоступна: {err_text[:200]}"
            save_message("assistant", final)
            return final
        raw = resp.content.strip()
        decision = _parse_json(raw)
        if decision is None:
            final = raw
            break

        thought = decision.get("thought", "")
        action = decision.get("action")
        answer = decision.get("answer")

        if action:
            tool_name = action.get("tool")
            tool_args = action.get("args") or {}
            obs = _run_tool(tool_name, tool_args)
            messages.append(AIMessage(f"REASONING: {thought}\nACTION: {tool_name} {tool_args}"))
            messages.append(HumanMessage(f"РЕЗУЛЬТАТ ИНСТРУМЕНТА {tool_name}:\n{obs}"))
            continue

        final = answer or "Агент не смог сформулировать ответ."
        break
    else:
        final = "Превышено максимальное число шагов агентного цикла."

    save_message("assistant", final)
    return final


def _parse_json(text: str):
    """Пытается извлечь JSON-объект из ответа модели."""
    import json
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
        if isinstance(obj, dict) and ("action" in obj or "answer" in obj):
            return obj
    except Exception:
        pass
    return None
