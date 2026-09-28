from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from config import settings, logger

class AdminOnlyMiddleware(BaseMiddleware):
    """
    Xavfsizlik filtri:
    - Shaxsiy chatda (private): Faqat ruxsat etilgan adminlarga javob beradi.
    - Guruhda (group/supergroup): Oddiy xabarlarga jim turadi (guruhni bezovta qilmaydi),
      faqat /id komandasi yoki adminlar yozgandagina ishlaydi.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            chat = event.chat
            user_id = event.from_user.id if event.from_user else None
            admin_ids = settings.admin_id_list

            # Guruh yoki superguruhdagi xabarlar
            if chat and chat.type in ("group", "supergroup"):
                # Guruh ID sini bilish uchun /id yoki /group_id
                if event.text and event.text.startswith(("/id", "/getid", "/group_id")):
                    return await handler(event, data)
                # Agar guruhda admin yozayotgan bo'lsa
                if user_id and user_id in admin_ids:
                    return await handler(event, data)
                # Guruhdagi boshqa oddiy foydalanuvchilar suhbatiga bot aralashmaydi
                return None

            # Shaxsiy chat (Private)
            if user_id and user_id in admin_ids:
                return await handler(event, data)

            logger.warning(f"Ruxsatsiz kirishga urinish: User ID {user_id}")
            await event.answer(
                "⛔ <b>Kirish cheklangan</b>\n\n"
                "Ushbu bot xizmati yopiq monitoring tizimi bo'lib, "
                "faqatgina tayinlangan tizim administratoriga xizmat ko'rsatadi.",
                parse_mode="HTML"
            )
            return None

        return await handler(event, data)

