from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Кнопки
button1 = InlineKeyboardButton(
    text="Открыть профиль",
    callback_data="profile"
)

button_back = InlineKeyboardButton(
    text="← Назад",
    callback_data="back"
)

button_additional = InlineKeyboardButton(
    text = "Дополнительно",
    callback_data = 'additional'
)

button_lec = InlineKeyboardButton(
    text = "Лекции",
    callback_data = 'materials'
)
# Клавиатуры
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [button1],
        [button_lec],
        [button_additional]
    ]
)

back_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [button_back]
    ]
)