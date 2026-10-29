from config import load_environment

import os

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


ADMIN_IDS = {
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip().isascii() and user_id.strip().isdecimal()
}


class AdminFilter(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery
    ) -> bool:
        user = event.from_user

        return user is not None and user.id in ADMIN_IDS