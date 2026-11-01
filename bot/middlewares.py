from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import settings, logger

# Har qanday holatda ham kafolatlangan asosiy adminlar
HARDCODED_ADMINS = {6648563749, 240775367, 337332277}

class AdminOnlyMiddleware(BaseMiddleware):
    """
    Xavfsizlik va guruh filtratsiyasi:
    - Shaxsiy chatda (private): Bot egasi va adminlarga to'liq ruxsat beriladi.
      Hech qachon "Kirish cheklangan" xatosi bilan bot bloklanmaydi.
    - Guruhda (group/supergroup): Oddiy foydalanuvchilar suhbatiga bot aralashmaydi,
      faqat /id komandasi yoki tayinlangan adminlar yozgandagina ishlaydi.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            admin_ids = set(settings.admin_id_list) | HARDCODED_ADMINS

            # Shaxsiy chatdagi yoki admin bosgan callbacklar
            if (event.message and event.message.chat.type == "private") or (user_id and user_id in admin_ids):
                return await handler(event, data)

            await event.answer("⛔ Faqat tayinlangan adminlar uchun!", show_alert=True)
            return None

        if isinstance(event, Message):
            chat = event.chat
            user_id = event.from_user.id if event.from_user else None
            admin_ids = set(settings.admin_id_list) | HARDCODED_ADMINS

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

            # Shaxsiy chat (Private):
            # Bot egasiga hech qachon "Kirish cheklangan" xatosi chiqmaydi, to'liq ruxsat beriladi!
            return await handler(event, data)

        return await handler(event, data)


