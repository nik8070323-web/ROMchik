from config import load_environment

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.messages import router as messages_router
from handlers.Subjects import router as subjects_router
from handlers.admin import router as admin_router, denied_router

TOKEN = os.getenv("BOT_TOKEN")


def create_dispatcher():
    dp = Dispatcher(events_isolation=SimpleEventIsolation())

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(admin_router)
    dp.include_router(denied_router)
    dp.include_router(subjects_router)
    dp.include_router(messages_router)

    return dp


# Запуск бота
async def main():
    if not TOKEN or not TOKEN.strip():
        raise ValueError("Укажите BOT_TOKEN в окружении или /home/container/.env")

    bot = Bot(token=TOKEN)
    dp = create_dispatcher()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
