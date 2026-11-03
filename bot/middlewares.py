from typing import Callable, Dict, Any, Awaitable, Optional, Set
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import settings, logger

# Har qanday holatda ham kafolatlangan asosiy adminlar
HARDCODED_ADMINS: Set[int] = {6648563749, 240775367, 337332277}

def is_admin_user(user_id: Optional[int]) -> bool:
    """Foydalanuvchi tizim ma'muri ekanligini 100% ishonch bilan tekshirish."""
    if not user_id:
        return False
    return user_id in HARDCODED_ADMINS or user_id in settings.admin_id_list

class AdminOnlyMiddleware(BaseMiddleware):
    """
    Xavfsizlik va ruxsat nazorati:
    - Adminlarga (shaxsiy chatda ham, guruhda ham) to'liq ruxsat beriladi.
    - Begona shaxslar shaxsiy chatda yozsa, ularning o'z Telegram ID raqami bilan xushmuomala ma'lumot beriladi.
    - Guruhda begona foydalanuvchilar suhbatiga bot aralashmaydi (/id bundan mustasno).
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            if is_admin_user(user_id):
                return await handler(event, data)

            await event.answer("⛔ Ushbu boshqaruv faqat tizim ma'murlari uchun!", show_alert=True)
            return None

        if isinstance(event, Message):
            chat = event.chat
            user_id = event.from_user.id if event.from_user else None

            # Guruh yoki superguruhdagi xabarlar
            if chat and chat.type in ("group", "supergroup"):
                # Guruh ID sini bilish uchun /id yoki /group_id
                if event.text and event.text.startswith(("/id", "/getid", "/group_id")):
                    return await handler(event, data)
                # Agar guruhda admin yozayotgan bo'lsa
                if is_admin_user(user_id):
                    return await handler(event, data)
                # Guruhdagi boshqa oddiy foydalanuvchilar suhbatiga bot aralashmaydi
                return None

            # Shaxsiy chat (Private):
            # 1. Agar admin bo'lsa - to'liq va cheklovlarsiz ruxsat
            if is_admin_user(user_id):
                return await handler(event, data)

            # 2. Begona foydalanuvchi bo'lsa - unga ID sini ko'rsatamiz
            logger.warning(f"Ruxsatsiz shaxsiy kirishga urinish: User ID {user_id}")
            await event.answer(
                f"⛔ <b>Kirish cheklangan</b>\n\n"
                f"Sizning Telegram ID raqamingiz: <code>{user_id}</code>\n\n"
                "Ushbu bot Toshkent metropoliteni yopiq monitoring tizimi bo'lib, "
                "faqatgina tayinlangan tizim administratorlariga xizmat ko'rsatadi.\n\n"
                f"💡 <i>Agar siz tizim ma'muri bo'lsangiz, yuqoridagi <code>{user_id}</code> raqamini "
                "server sozlamalaridagi (ADMIN_IDS) qatoriga qo'shing.</i>",
                parse_mode="HTML"
            )
            return None

        return await handler(event, data)


