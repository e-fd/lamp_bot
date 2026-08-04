"""Точка входа: запуск чат-бота Ламп.ру (aiogram 3 + asyncio)."""
import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from bot.handlers import router
from config import TELEGRAM_PROXY, TELEGRAM_TOKEN, log


async def main() -> None:
    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN не задан. Скопируйте .env.example в .env "
                  "и впишите токен от @BotFather.")
        sys.exit(1)

    session = AiohttpSession(proxy=TELEGRAM_PROXY) if TELEGRAM_PROXY else None
    if TELEGRAM_PROXY:
        log.info("Telegram работает через прокси")

    bot = Bot(token=TELEGRAM_TOKEN,
              session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    log.info("Бот запущен")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Выход по Ctrl+C")
