from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import settings, logger

class AdminOnlyMiddleware(BaseMiddleware):
    """
    Ochiq kirish tizimi (Barcha foydalanuvchilar uchun ochiq):
    - Shaxsiy chatda (private): Istalgan foydalanuvchi botdan to'liq foydalana oladi.
      Hech kimga 'Kirish cheklangan' degan xatolik chiqmaydi.
    - Guruhda (group/supergroup): Bot faqat unga yo'naltirilgan buyruqlar (/start, /check, /today, /id va h.k.)
      yoki tugmalar bosilganda javob beradi, oddiy suhbatlarga xalaqit bermaydi.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, CallbackQuery):
            # Barcha callback tugmalar hamma uchun ochiq
            return await handler(event, data)

        if isinstance(event, Message):
            chat = event.chat

            # Guruh yoki superguruhda faqat buyruqlarga yoki botga qaratilgan xabarlarga javob beradi
            if chat and chat.type in ("group", "supergroup"):
                if event.text and event.text.startswith("/"):
                    return await handler(event, data)
                # Guruhdagi boshqa oddiy foydalanuvchilar o'zaro suhbatiga bot aralashmaydi
                return None

            # Shaxsiy chat (Private): Hamma uchun to'liq ochiq!
            return await handler(event, data)

        return await handler(event, data)


