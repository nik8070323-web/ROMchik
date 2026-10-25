from pathlib import Path
from aiogram.exceptions import TelegramAPIError
from services.materials import repository, FOLDERS, SECTIONS
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.subject import (
    get_subjects_keyboard,
    get_additional_keyboard
)

router = Router()

BASE_DIR = Path(__file__).resolve().parent.parent

EXTRA_FILES = {
    "Титульный лист для реферата": "титульный лист.docx",
    "Регламент для реферата": "регламент реферата.docx"
}


def get_lecture_files(subject):
    if subject not in FOLDERS:
        return []
    return [material.path for material in repository.list(subject, "lecture")]


@router.callback_query(F.data == "materials")
async def open_materials(callback: CallbackQuery, state: FSMContext = None):
    if state is not None:
        await state.clear()
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📚 Выбери предмет:",
            reply_markup=get_subjects_keyboard()
        )


@router.callback_query(F.data == "additional")
async def open_additional(callback: CallbackQuery, state: FSMContext = None):
    if state is not None:
        await state.clear()
    await open_subject(callback)


@router.callback_query(F.data.startswith("catalog:"))
@router.callback_query(F.data.startswith("subject:"))
async def open_subject(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    category = None
    if parts[0] == "catalog":
        if len(parts) != 4 or parts[2] not in ("lecture", "practice"):
            await callback.answer("Некорректная кнопка", show_alert=True)
            return
        category = parts[2]
        parts = ["subject", parts[1], parts[3]]
    if callback.data != "additional" and (len(parts) not in (2, 3) or (len(parts) == 3 and (not parts[2].isascii() or not parts[2].isdigit() or len(parts[2]) > 6))):
        await callback.answer("Некорректная кнопка", show_alert=True)
        return
    await callback.answer()
    subject = "Дополнительно" if callback.data == "additional" else parts[1]
    if not isinstance(callback.message, Message):
        return
    if subject in FOLDERS and category is None:
        builder = InlineKeyboardBuilder()
        builder.button(text="📖 Лекции", callback_data=f"catalog:{subject}:lecture:0")
        builder.button(text="📝 Практики", callback_data=f"catalog:{subject}:practice:0")
        builder.button(text="← Предметы", callback_data="materials")
        builder.adjust(1)
        await callback.message.edit_text(f"📚 {subject}: выбери тип материалов:", reply_markup=builder.as_markup())
        return
    prefix = f"catalog:{subject}:{category}" if category else f"subject:{subject}"
    back = f"subject:{subject}" if category else "back"
    try:
        materials = repository.list(subject, category) if subject in SECTIONS else []
    except (OSError, ValueError):
        await callback.message.answer("Не удалось прочитать каталог. Попробуйте позже.")
        return
    if not materials:
        await callback.message.edit_text(
            f"В этом разделе предмета «{subject}» файлов пока нет.",
            reply_markup=InlineKeyboardBuilder().button(text="← Назад", callback_data=back).as_markup())
        return
    size = 15
    page = min(int(parts[2]) if len(parts) == 3 else 0, (len(materials) - 1) // size)
    builder = InlineKeyboardBuilder()
    for material in materials[page * size:(page + 1) * size]:
        builder.button(text=f"{material.title} ({material.path.suffix[1:].upper()})", callback_data=f"material:{material.uid}")
    if page:
        builder.button(text="← Предыдущие", callback_data=f"{prefix}:{page - 1}")
    if (page + 1) * size < len(materials):
        builder.button(text="Следующие →", callback_data=f"{prefix}:{page + 1}")
    builder.button(text="← Назад", callback_data=back)
    builder.adjust(1)
    label = {"lecture": "Лекции", "practice": "Практики"}.get(category, "Материалы")
    await callback.message.edit_text(f"📚 {label} по предмету «{subject}»:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("material:"))
async def send_material(callback: CallbackQuery):
    try:
        material = repository.get(callback.data.split(":", 1)[1])
        if material is None:
            await callback.answer("Файл удалён. Откройте каталог заново.", show_alert=True)
            return
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.answer_document(FSInputFile(material.path), caption=material.title)
    except (OSError, ValueError, TelegramAPIError):
        if isinstance(callback.message, Message):
            await callback.message.answer("Не удалось отправить файл. Откройте каталог заново или попробуйте позже.")


@router.callback_query(F.data.startswith("file:"))
async def send_lecture(callback: CallbackQuery):
    parts = (callback.data or "").split(":", 2)

    if len(parts) != 3:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return

    _, subject, index = parts
    try:
        files = get_lecture_files(subject)
    except (OSError, ValueError):
        await callback.answer("Не удалось прочитать каталог", show_alert=True)
        return

    if not index.isascii() or not index.isdecimal() or len(index) > 10:
        await callback.answer("Некорректный номер файла", show_alert=True)
        return

    if int(index) >= len(files):
        await callback.answer("Файл не найден", show_alert=True)
        return

    file = files[int(index)]

    if not file.is_file():
        await callback.answer("Файл не найден", show_alert=True)
        return

    await callback.answer()

    if isinstance(callback.message, Message):
        try:
            await callback.message.answer_document(document=FSInputFile(file), caption=f"📄 {file.stem}")
        except (OSError, TelegramAPIError):
            await callback.message.answer("Не удалось отправить файл. Попробуйте позже.")

@router.callback_query(F.data.startswith("additional:"))
async def send_additional(callback: CallbackQuery):
    name = callback.data.split(":", 1)[1]
    filename = EXTRA_FILES.get(name)

    if filename is None:
        await callback.answer("Файл не найден", show_alert=True)
        return

    path = BASE_DIR / "лекции" / "дополнительно" / filename

    if not path.is_file():
        await callback.answer(
            "Файл не найден",
            show_alert=True
        )
        return

    await callback.answer()

    if isinstance(callback.message, Message):
        try:
            await callback.message.answer_document(document=FSInputFile(path), caption=name)
        except (OSError, TelegramAPIError):
            await callback.message.answer("Не удалось отправить файл. Попробуйте позже.")