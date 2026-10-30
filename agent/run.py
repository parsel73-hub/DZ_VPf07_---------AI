"""CLI-интерфейс для запуска локального AI-агента."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import ask, build_llm
from tools import load_memory


def banner():
    print("=" * 60)
    print("  Локальный AI-агент (ProxyAI + LangChain)")
    print("  Команды: /exit — выход, /memory — показать память")
    print("=" * 60)


def main():
    banner()
    try:
        build_llm()
        print("[OK] Ключ и модель настроены.\n")
    except RuntimeError as e:
        print(f"[ОШИБКА] {e}\n")
        return

    while True:
        try:
            user_input = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nПока!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit"):
            print("Пока!")
            break
        if user_input == "/memory":
            mem = load_memory()
            print(f"Сообщений в памяти: {len(mem.get('history', []))}")
            for item in mem.get("history", [])[-5:]:
                print(f"  [{item['role']}] {item['content'][:120]}")
            print()
            continue

        try:
            answer = ask(user_input)
        except Exception as e:
            answer = f"Сбой агента: {e}"

        print(f"\nАгент: {answer}\n")


if __name__ == "__main__":
    main()
