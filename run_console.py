"""Отладка бота в консоли, без Telegram и без токенов.

Запуск:  python run_console.py
"""
import asyncio

from bot.core import ChatBot
from config import GREETING


async def main() -> None:
    chatbot = ChatBot()
    user_id = 1
    print(GREETING)
    while True:
        try:
            replica = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not replica:
            continue
        reply = await chatbot.respond(user_id, replica)
        print(f"Бот: {reply.text}")
        if reply.images:
            print(f"      [фото: {', '.join(p.name for p in reply.images)}]")
        print()
        if reply.finished:
            break
    print("Статистика:", chatbot.stats)


if __name__ == "__main__":
    asyncio.run(main())
