from aiogram import Router, F
from aiogram.types import Message

router = Router()

# Обработка конкретного текста
@router.message(F.text.lower() == "привет")
async def hello_call(message: Message):
    await message.answer("Привет! Как дела?")


@router.message(F.text.lower() == "как тебя зовут?")
async def call_name(message: Message):
    await message.answer("Привет, я Ромчик!")


# Обработка любого другого текста
@router.message(F.text)
async def random_text(message: Message):
    await message.answer("Я пока не знаю, что ответить.")

