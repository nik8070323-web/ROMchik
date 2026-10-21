from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile

from keyboards.menu import keyboard

router = Router()
BASE_DIR = Path(__file__).resolve().parent.parent


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext = None):
    if state is not None:
        await state.clear()
    path = BASE_DIR.parent / "images" / "welcome.png"

    if path.is_file():
        await message.answer_photo(photo=FSInputFile(path))
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
