import asyncio
import os

from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.messages import router as messages_router
from handlers.Subjects import router as subjects_router
from handlers.admin import router as admin_router

# Загрузка токена
load_dotenv(Path(__file__).resolve().parent / ".env")
TOKEN = os.getenv("BOT_TOKEN")


# Запуск бота
async def main():
    if not TOKEN or not TOKEN.strip():
        raise ValueError("Укажите BOT_TOKEN в файле aiogram-learning/.env")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(admin_router)
    dp.include_router(subjects_router)
    dp.include_router(messages_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
