import os
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

router = Router()

ADMIN_IDS = {
    int(user_id.strip())
    for user_id in os.getenv('ADMIN_IDS', '').split(',')
    if user_id.strip().isascii() and user_id.strip().isdecimal()
}


@router.message(Command("admin"))
async def admin_panel(message: Message):
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        await message.answer('Твои данные летят в пекло)))')
        return
    await message.answer(
        "⚙️ Админ-панель Ромчика\n\n"
        f"Добро пожаловать, {user.first_name}!"
    )