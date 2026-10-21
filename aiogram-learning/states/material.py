from aiogram.fsm.state import State, StatesGroup


class AddMaterial(StatesGroup):
    subject = State()
    kind = State()
    number = State()
    file = State()
    confirm = State()
    delete = State()
