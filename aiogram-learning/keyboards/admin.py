from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.materials import KINDS, SECTIONS


def buttons(*rows):
    builder = InlineKeyboardBuilder()
    for text, data in rows:
        builder.button(text=text, callback_data=data)
    builder.adjust(1)
    return builder.as_markup()


keyboard_admin = buttons(
    ("➕ Добавить материал", "admin:add"),
    ("📁 Управление материалами", "admin:manage"),
    ("📊 Статистика", "admin:stats"),
    ("↩️ Назад", "admin:exit"),
)


def get_admin_subjects_keyboard(manage=False):
    prefix = "admin:list" if manage else "admin:subject"
    return buttons(*[(sub, f"{prefix}:{sub}") for sub in SECTIONS], ("↩️ Назад", "admin:back"))


def kinds_keyboard():
    return buttons(*[(label, f"admin:kind:{key}") for key, label in KINDS.items()],
                   ("↩️ Назад", "admin:add"), ("Отмена", "admin:back"))


def cancel_keyboard(back="admin:back"):
    return buttons(("↩️ Назад", back), ("Отмена", "admin:back"))


def material_list_keyboard(materials, subject, page=0):
    size = 15
    pages = max(1, (len(materials) + size - 1) // size)
    page = min(max(page, 0), pages - 1)
    rows = [(f"{m.title} ({m.path.suffix[1:].upper()})", f"admin:view:{m.uid}") for m in materials[page * size:(page + 1) * size]]
    if page:
        rows.append(("← Предыдущие", f"admin:list:{subject}:{page - 1}"))
    if page + 1 < pages:
        rows.append(("Следующие →", f"admin:list:{subject}:{page + 1}"))
    rows.append(("↩️ Предметы", "admin:manage"))
    return buttons(*rows)
