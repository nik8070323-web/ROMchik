from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from keyboards.menu import keyboard, back_keyboard

router = Router()

# Обработка нажатия кнопки "Открыть профиль"
@router.callback_query(F.data == "profile")
async def callback_profile(callback: CallbackQuery):
    await callback.answer()

    user = callback.from_user

    if user.username is None:
        username = "Отсутствует"
    else:
        username = f"@{user.username}"

    text = (
        f"Это твой профиль:\n"
        f"Имя: {user.first_name}\n"
        f"Telegram ID: {user.id}\n"
        f"Username: {username}"
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard
        )


# Обработка кнопки "Назад"
@router.callback_query(F.data == "back")
async def callback_back(callback: CallbackQuery):
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Привет!",
            reply_markup=keyboard
        )