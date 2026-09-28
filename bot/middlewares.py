from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from config import settings, logger

class AdminOnlyMiddleware(BaseMiddleware):
    """
    Faqat 2 ta ruxsat etilgan Adminga ruxsat beruvchi xavfsizlik filtri.
    Begona foydalanuvchilar botga yozsa, ularga hech qanday ma'lumot ko'rinmaydi.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id

        admin_ids = settings.admin_id_list

        if user_id and user_id in admin_ids:
            return await handler(event, data)

        logger.warning(f"Ruxsatsiz kirishga urinish: User ID {user_id}")
        if isinstance(event, Message):
            await event.answer(
                "⛔ <b>Kirish cheklangan</b>\n\n"
                "Ushbu bot xizmati yopiq monitoring tizimi bo'lib, "
                "faqatgina tayinlangan 2 ta tizim administratoriga xizmat ko'rsatadi.",
                parse_mode="HTML"
            )
        return None
