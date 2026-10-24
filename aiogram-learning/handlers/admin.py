import asyncio
import secrets

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from filters.admin import AdminFilter
from keyboards.admin import (buttons, cancel_keyboard, get_admin_subjects_keyboard,
                             keyboard_admin, kinds_keyboard, material_list_keyboard)
from keyboards.menu import keyboard as main_keyboard
from services.materials import (ConflictError, FOLDERS, SECTIONS, KINDS, LimitedBuffer,
                               repository, parse_number, validate_document, validate_title)
from states.material import AddMaterial

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())
# Serialize mutations across admins; downloads never overwrite the visible file.
mutation_lock = asyncio.Lock()


async def screen(callback, text, markup):
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            await callback.message.answer(text, reply_markup=markup)


@router.message(Command("admin", "cancel"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Админ-панель Ромчика\nДобро пожаловать!", reply_markup=keyboard_admin)


@router.callback_query(F.data.in_({"admin:back", "admin:exit", "admin:add", "admin:manage", "admin:stats"}))
async def menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    action = callback.data
    if action == "admin:exit":
        await screen(callback, "Главное меню", main_keyboard)
    elif action == "admin:add":
        await state.set_state(AddMaterial.subject)
        await screen(callback, "📤 Выберите предмет", get_admin_subjects_keyboard())
    elif action == "admin:manage":
        await screen(callback, "📁 Выберите предмет", get_admin_subjects_keyboard(manage=True))
    elif action == "admin:stats":
        try:
            materials, extra = repository.statistics()
            lectures = sum(m.kind == "lecture" for m in materials)
            practices = sum(m.kind == "practice" for m in materials)
            lines = [f"Предметов: {len(FOLDERS)}", f"Лекций: {lectures}",
                     f"Практик: {practices}", f"Всего файлов: {len(materials) + extra}",
                     f"Дополнительных файлов: {extra}", ""]
            for subject in FOLDERS:
                items = [m for m in materials if m.subject == subject]
                lines.append(f"{subject}: {len(items)} (лекций: {sum(m.kind == 'lecture' for m in items)}, практик: {sum(m.kind == 'practice' for m in items)})")
            await screen(callback, "📊 Статистика\n" + "\n".join(lines), cancel_keyboard())
        except (OSError, ValueError):
            await screen(callback, "Не удалось прочитать папки материалов. Проверьте доступ к диску.", keyboard_admin)
    else:
        await screen(callback, "⚙️ Админ-панель Ромчика", keyboard_admin)


@router.callback_query(AddMaterial.subject, F.data.startswith("admin:subject:"))
async def select_subject(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":", 2)[2]
    if subject not in SECTIONS:
        await callback.answer("Неизвестный предмет", show_alert=True)
        return
    await callback.answer()
    await state.update_data(subject=subject)
    await state.set_state(AddMaterial.kind)
    await screen(callback, f"📚 {subject}: выберите тип материала", kinds_keyboard())


@router.callback_query(AddMaterial.kind, F.data.startswith("admin:kind:"))
async def select_kind(callback: CallbackQuery, state: FSMContext):
    kind = callback.data.split(":", 2)[2]
    if kind not in KINDS:
        await callback.answer("Неизвестный тип", show_alert=True)
        return
    await callback.answer()
    await state.update_data(kind=kind)
    await state.set_state(AddMaterial.number)
    await screen(callback, "Введите номер материала от 1 до 999999.", cancel_keyboard("admin:to_kind"))


@router.callback_query(StateFilter(AddMaterial.number, AddMaterial.title, AddMaterial.file, AddMaterial.confirm), F.data.in_({"admin:to_kind", "admin:to_number", "admin:to_file"}))
async def step_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    if callback.data == "admin:to_kind" and not data.get("target_uid"):
        await state.set_state(AddMaterial.kind)
        await screen(callback, "Выберите тип материала", kinds_keyboard())
    elif callback.data == "admin:to_number" and not data.get("target_uid"):
        await state.set_state(AddMaterial.number)
        await screen(callback, "Введите номер материала", cancel_keyboard("admin:to_kind"))
    else:
        await state.set_state(AddMaterial.file)
        await screen(callback, "Отправьте PDF или DOCX до 20 МБ.", cancel_keyboard())


@router.message(AddMaterial.number)
async def get_lecture_number(message: Message, state: FSMContext):
    try:
        number = parse_number(message.text)
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=cancel_keyboard("admin:to_kind"))
        return
    await state.update_data(number=number, target_uid=None, title=None)
    await state.set_state(AddMaterial.title)
    await message.answer("Введите название материала или нажмите «Пропустить».", reply_markup=buttons(
        ("Пропустить", "admin:skip_title"), ("↩️ Назад", "admin:to_number"), ("Отмена", "admin:back")))


@router.callback_query(AddMaterial.title, F.data == "admin:skip_title")
async def skip_title(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(title=None)
    await state.set_state(AddMaterial.file)
    await screen(callback, "📎 Отправьте PDF или DOCX до 20 МБ.", cancel_keyboard("admin:to_number"))


@router.message(AddMaterial.title)
async def get_material_title(message: Message, state: FSMContext):
    try:
        title = validate_title(message.text)
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=buttons(
            ("Пропустить", "admin:skip_title"), ("↩️ Назад", "admin:to_number"), ("Отмена", "admin:back")))
        return
    await state.update_data(title=title)
    await state.set_state(AddMaterial.file)
    await message.answer("📎 Отправьте PDF или DOCX до 20 МБ.", reply_markup=cancel_keyboard("admin:to_number"))


@router.message(AddMaterial.file)
async def get_lecture_file(message: Message, state: FSMContext):
    document = message.document
    if document is None:
        await message.answer("Отправьте файл как документ PDF или DOCX.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    try:
        extension = validate_document(document.file_name, document.file_size)
        if data.get("target_uid"):
            target = repository.get(data["target_uid"])
            if target is None:
                raise ValueError("Материал удалён. Откройте /admin заново.")
            existing = [target]
            title = target.title
        else:
            existing = repository.numbered(data["subject"], data["kind"], data["number"])
            title = f"{KINDS[data['kind']]} № {data['number']}"
            if data.get("title"):
                title += " — " + data["title"]
        if len(existing) > 1:
            raise ValueError("Несколько файлов имеют этот номер. Выберите конкретный файл через управление материалами.")
    except (ValueError, OSError) as exc:
        text = str(exc) if isinstance(exc, ValueError) else "Не удалось прочитать каталог материалов."
        await message.answer(text, reply_markup=cancel_keyboard())
        return
    nonce = secrets.token_hex(8)
    await state.update_data(file_id=document.file_id, extension=extension,
                            expected=repository.snapshot(existing), nonce=nonce)
    await state.set_state(AddMaterial.confirm)
    warning = "\n⚠️ Материал существует. Подтверждение заменит его файл." if existing else ""
    await message.answer(
        f"{data['subject']} — {title}\nФайл: {(document.file_name or '')[:180]}\n"
        f"Формат: {extension[1:].upper()}\nРазмер: {document.file_size / 1024:.1f} КБ{warning}\nСохранить?",
        reply_markup=buttons(("Подтвердить замену" if existing else "Сохранить", f"admin:save:{nonce}"),
                             ("↩️ Другой файл", "admin:to_file"), ("Отмена", "admin:back")))


@router.callback_query(AddMaterial.confirm, F.data.startswith("admin:save:"))
async def save_material(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if callback.data != f"admin:save:{data.get('nonce')}":
        await callback.answer("Это устаревшее подтверждение", show_alert=True)
        return
    await callback.answer("Сохраняю…")
    try:
        async with mutation_lock:
            with LimitedBuffer() as buffer:
                await callback.bot.download(data["file_id"], destination=buffer)
                repository.save(data["subject"], data["kind"], data.get("number"),
                                data["extension"], buffer.getvalue(), data["expected"], data.get("target_uid"), title=data.get("title"))
    except ConflictError as exc:
        await state.clear()
        await screen(callback, str(exc), keyboard_admin)
        return
    except (OSError, ValueError, TelegramAPIError, asyncio.TimeoutError):
        await state.set_state(AddMaterial.file)
        await screen(callback, "Не удалось скачать или сохранить файл. Проверьте формат, размер и доступ к диску, затем отправьте файл повторно.", cancel_keyboard())
        return
    await state.clear()
    await screen(callback, "✅ Материал сохранён и доступен в каталоге.", keyboard_admin)


@router.callback_query(F.data.startswith("admin:list:"))
async def list_materials(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) not in (3, 4) or parts[2] not in SECTIONS or (len(parts) == 4 and (not parts[3].isascii() or not parts[3].isdigit() or len(parts[3]) > 6)):
        await callback.answer("Некорректная кнопка", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    try:
        materials = repository.list(parts[2])
        await screen(callback, f"📁 {parts[2]}: лекции и практики" if materials else "Материалов пока нет.",
                     material_list_keyboard(materials, parts[2], int(parts[3]) if len(parts) == 4 else 0))
    except (OSError, ValueError):
        await screen(callback, "Не удалось прочитать каталог.", keyboard_admin)


@router.callback_query(F.data.startswith("admin:view:") | F.data.startswith("admin:replace:") | F.data.startswith("admin:delete:"))
async def material_action(callback: CallbackQuery, state: FSMContext):
    _, action, uid = callback.data.split(":", 2)
    try:
        material = repository.get(uid)
    except (OSError, ValueError):
        await callback.answer("Не удалось прочитать каталог", show_alert=True)
        return
    if material is None:
        await callback.answer("Файл уже удалён. Откройте список заново.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    back = f"admin:list:{material.subject}"
    info = f"{material.subject} — {material.title}\nФайл: {material.path.name}\nРазмер: {material.size / 1024:.1f} КБ"
    if action == "view":
        await screen(callback, info, buttons(("🔄 Заменить файл", f"admin:replace:{uid}"),
                     ("🗑 Удалить", f"admin:delete:{uid}"), ("↩️ Назад", back)))
    elif action == "replace":
        await state.update_data(subject=material.subject, kind=material.kind, number=material.number, target_uid=uid)
        await state.set_state(AddMaterial.file)
        await screen(callback, info + "\nОтправьте новый PDF или DOCX до 20 МБ.", cancel_keyboard(f"admin:view:{uid}"))
    else:
        nonce = secrets.token_hex(8)
        await state.update_data(uid=uid, revision=material.revision, nonce=nonce)
        await state.set_state(AddMaterial.delete)
        await screen(callback, info + "\nУдалить этот материал?", buttons(
            ("Да, удалить", f"admin:remove:{nonce}"), ("Отмена", f"admin:view:{uid}")))


@router.callback_query(AddMaterial.delete, F.data.startswith("admin:remove:"))
async def delete_material(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if callback.data != f"admin:remove:{data.get('nonce')}":
        await callback.answer("Это устаревшее подтверждение", show_alert=True)
        return
    await callback.answer()
    try:
        async with mutation_lock:
            repository.delete(data["uid"], data["revision"])
        text = "✅ Материал удалён."
    except ConflictError as exc:
        text = str(exc)
    except (OSError, ValueError):
        text = "Не удалось удалить файл. Проверьте доступ к диску."
    await state.clear()
    await screen(callback, text, keyboard_admin)


@router.callback_query(F.data.startswith("admin:"))
async def stale_button(callback: CallbackQuery):
    await callback.answer("Кнопка устарела. Откройте /admin заново.", show_alert=True)


@router.message(StateFilter(AddMaterial))
async def pending_step(message: Message):
    await message.answer("Используйте кнопки текущего шага или /cancel для отмены.")


# Explicit replies for denied requests; authorization still lives on the admin router.
denied_router = Router()
denied_router.message.filter(~AdminFilter())
denied_router.callback_query.filter(~AdminFilter())


@denied_router.message(Command("admin", "cancel"))
@denied_router.message(StateFilter(AddMaterial))
async def denied_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Доступ к админ-панели запрещён.")


@denied_router.callback_query(F.data.startswith("admin:"))
async def denied_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Доступ к админ-панели запрещён.", show_alert=True)
