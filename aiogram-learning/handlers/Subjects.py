from pathlib import Path
from aiogram.types import InlineKeyboardButton
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.subject import (
    get_subjects_keyboard,
    get_additional_keyboard
)

router = Router()

BASE_DIR = Path(__file__).resolve().parent.parent

FOLDERS = {
    "МДК": "мдк",
    "ОИТ": "оит",
    "ИНО": "ИНО"
}

EXTRA_FILES = {
    "Титульный лист для реферата": "титульный лист.docx",
    "Регламент для реферата": "регламент реферата.docx"
}


def get_lecture_files(subject):
    folder = FOLDERS.get(subject)

    if folder is None:
        return []

    path = BASE_DIR / "лекции" / folder
    return sorted(path.glob("*.pdf"))


@router.callback_query(F.data == "materials")
async def open_materials(callback: CallbackQuery):
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📚 Выбери предмет:",
            reply_markup=get_subjects_keyboard()
        )


@router.callback_query(F.data == "additional")
async def open_additional(callback: CallbackQuery):
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Дополнительные материалы:",
            reply_markup=get_additional_keyboard()
        )


@router.callback_query(F.data.startswith("subject:"))
async def open_subject(callback: CallbackQuery):
    await callback.answer()

    subject = callback.data.split(":", 1)[1]
    files = get_lecture_files(subject)

    if not isinstance(callback.message, Message):
        return

    if not files:
        await callback.message.edit_text(
            f"Для предмета «{subject}» файлов пока нет."
        )
        return

    builder = InlineKeyboardBuilder()

    for index, file in enumerate(files):
        builder.button(
            text=file.stem,
            callback_data=f"file:{subject}:{index}"
        )

    builder.row(
    InlineKeyboardButton(
        text="← Назад",
        callback_data="materials"
        )
    )
    builder.adjust(1)

    await callback.message.edit_text(
        f"📚 Лекции по предмету «{subject}»:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("file:"))
async def send_lecture(callback: CallbackQuery):
    await callback.answer()

    _, subject, index = callback.data.split(":", 2)
    files = get_lecture_files(subject)

    if not index.isdigit() or int(index) >= len(files):
        return

    if not isinstance(callback.message, Message):
        return

    file = files[int(index)]

    await callback.message.answer_document(
        document=FSInputFile(file),
        caption=f"📄 {file.stem}"
    )


@router.callback_query(F.data.startswith("additional:"))
async def send_additional(callback: CallbackQuery):
    await callback.answer()

    name = callback.data.split(":", 1)[1]
    filename = EXTRA_FILES.get(name)

    if filename is None:
        return

    path = BASE_DIR / "лекции" / "дополнительно" / filename

    if not path.is_file():
        await callback.answer(
            "Файл не найден",
            show_alert=True
        )
        return

    if isinstance(callback.message, Message):
        await callback.message.answer_document(
            document=FSInputFile(path),
            caption=name
        )