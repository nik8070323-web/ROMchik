
import asyncio
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from dotenv import load_dotenv
from handlers.start import router as start_router
from handlers.profile import router as profile_router
from handlers.messages import router as messages_router
from handlers.Subjects import router as subjects_router

# Загрузка токена
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

router = Router()


# Запуск бота
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(messages_router)
    dp.include_router(subjects_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
