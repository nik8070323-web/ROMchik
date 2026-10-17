from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
subjects = [
        "ОИТ",
        "МДК",
        "ИНО"
    ]
additional = [
    'Титульный лист для реферата',
    'Регламент для реферата'
]

def get_subjects_keyboard():
    builder = InlineKeyboardBuilder()
    for sub in subjects:
        builder.button(
            text=sub,
            callback_data = f"subject:{sub}"
        )
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="← Назад",
            callback_data="back"
        )
    )
    return builder.as_markup()


def get_additional_keyboard():
    builder = InlineKeyboardBuilder()
    for add in additional:
        builder.button(
            text = add,
            callback_data = f"additional:{add}"
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="← Назад",
            callback_data="back"
        )
    )
    return builder.as_markup()