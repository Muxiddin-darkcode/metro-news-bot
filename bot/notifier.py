import html
import datetime
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from parsers.base import NewsItem

logger = logging.getLogger("MetroMonitor.Notifier")

def format_alert_message(item: NewsItem) -> str:
    """Xabarni chiroyli va qulay HTML ko'rinishida formatlash."""
    now_str = datetime.datetime.now().strftime("%H:%M | %d.%m.%Y")
    
    # HTML maxsus belgilarini tozalash
    title_safe = html.escape(item.title.strip())
    content_safe = html.escape(item.content.strip())
    source_safe = html.escape(item.source_name)
    
    # Qisqacha matn uzunligini nazorat qilish
    if len(content_safe) > 700:
        content_safe = content_safe[:700] + "..."

    # Teglar
    tags_str = " ".join(item.tags) if item.tags else "#metro"

    msg = (
        "🚇 <b>METRO YANGILIK / MONITORING XABARI</b>\n\n"
        f"📌 <b>Manba:</b> {source_safe}\n"
        f"🕒 <b>Vaqt:</b> {now_str}\n"
        f"🔍 <b>Belgilar:</b> <code>{tags_str}</code>\n\n"
        f"📰 <b>Sarlavha:</b>\n<b>{title_safe}</b>\n\n"
    )

    if content_safe and content_safe != title_safe:
        msg += f"📝 <b>Tafsilot:</b>\n{content_safe}\n\n"

    msg += "────────────────────────\n<i>⚡ Xabar avtomatik ravishda aniqlanib, kross-dublikat tekshiruvidan o'tkazildi.</i>"

    return msg

async def send_metro_alert(bot: Bot, item: NewsItem) -> int:
    """
    Aniqlangan metro xabarini faqat belgilangan 2 ta adminga jo'natadi.
    Muvaffaqiyatli yetkazilgan adminlar sonini qaytaradi.
    """
    text = format_alert_message(item)
    
    # Asl manbaga o'tish va tezkor inline tugmalar (orqa foni rangli)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Asl manbani ochish",
                    url=item.url if item.url.startswith("http") else f"https://{item.url}",
                    style="primary"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Qayta tekshirish",
                    callback_data="btn_check_now",
                    style="success"
                ),
                InlineKeyboardButton(
                    text="📊 Tizim holati",
                    callback_data="btn_status",
                    style="primary"
                )
            ]
        ]
    )

    admin_ids = settings.admin_id_list
    successful_deliveries = 0

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            successful_deliveries += 1
            logger.info(f"Xabar adminga yetkazildi: User ID {admin_id}")
        except Exception as e:
            logger.error(f"Adminga ({admin_id}) xabar yetkazishda xatolik: {e}")

    return successful_deliveries
