
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from keyboards.menu import keyboard
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
router = Router()
BASE_DIR = Path(__file__).resolve().parent.parent

@router.message(Command("start"))
async def start_handler(message: Message):
    photo = FSInputFile(BASE_DIR.parent / "images" / "welcome.png")

    await message.answer_photo(photo=photo)
    await message.answer(
        text=(
            "👋 Приветствую, я Ромчик!\n\n"
            "📚 Репозиторий Образовательных Материалов\n\n"
        ),
        reply_markup=keyboard
    )

@router.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "/start — начать работу\n/help — список команд"
    )
