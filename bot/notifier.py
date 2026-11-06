import html
import datetime
import logging
import httpx
from typing import Optional, List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
from config import settings, format_uz_time
from parsers.base import NewsItem
from core.ai_analyzer import ai_analyzer, AIAnalysisResult

logger = logging.getLogger("MetroMonitor.Notifier")

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
}

# Xotiradagi tezkor fotosuratlar keshi (LRU, qayta yuklab olishni 100% yo'qotadi)
_IMAGE_CACHE: dict = {}
_IMAGE_CACHE_MAX = 50

async def download_photo_file(image_url: str) -> Optional[BufferedInputFile]:
    """
    Rasm URL manzilidan baytlarni asinxron yuklab olib, BufferedInputFile yaratadi.
    Kesh (cache) orqali takroriy so'rovlarni yo'qotadi va Telegram serverlarining
    'failed to get HTTP URL content' xatosini 100% oldini oladi.
    """
    if not image_url or not image_url.startswith("http"):
        return None

    if image_url in _IMAGE_CACHE:
        content, ext = _IMAGE_CACHE[image_url]
        return BufferedInputFile(content, filename=f"metro_image.{ext}")

    try:
        async with httpx.AsyncClient(timeout=8.0, headers=COMMON_HEADERS, follow_redirects=True) as client:
            resp = await client.get(image_url)
            if resp.status_code == 200 and len(resp.content) > 500:
                ext = "jpg"
                ct = resp.headers.get("content-type", "").lower()
                if "png" in ct or ".png" in image_url.lower():
                    ext = "png"
                elif "webp" in ct or ".webp" in image_url.lower():
                    ext = "webp"

                if len(_IMAGE_CACHE) >= _IMAGE_CACHE_MAX:
                    # Eng eski rasm keshdan chiqariladi
                    _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)))
                _IMAGE_CACHE[image_url] = (resp.content, ext)

                return BufferedInputFile(resp.content, filename=f"metro_image.{ext}")
    except Exception as exc:
        logger.debug(f"Rasmni yuklab olishda xatolik ({image_url[:60]}): {exc}")
    return None


def format_alert_message(item: NewsItem) -> str:
    """Xabarni standart HTML ko'rinishida formatlash (AI o'chirilgandagi fallback, chiziqsiz)."""
    now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
    if item.published_at:
        try:
            pub_str = item.published_at.replace("Z", "+00:00")
            pub_dt = datetime.datetime.fromisoformat(pub_str)
            now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
        except Exception:
            pass

    title_safe = html.escape(item.title.strip(), quote=False)
    content_safe = html.escape(item.content.strip(), quote=False)
    source_safe = html.escape(item.source_name, quote=False)

    if len(content_safe) > 700:
        content_safe = content_safe[:700] + "..."

    tags_str = " ".join(item.tags) if item.tags else "#metro #toshkent"

    msg = (
        "🚇 <b>METRO MONITORING XABARI</b>\n\n"
        f"📌 <b>Manba:</b> {source_safe}\n"
        f"🕒 <b>Vaqt:</b> {now_str}\n"
        f"🔍 <b>Belgilar:</b> <code>{html.escape(tags_str)}</code>\n\n"
        f"📰 <b>Sarlavha:</b>\n<b>{title_safe}</b>\n\n"
    )

    if content_safe and content_safe != title_safe:
        msg += f"📝 <b>Tafsilot:</b>\n{content_safe}\n\n"

    msg += "<i>⚡ Xabar avtomatik aniqlanib, kross-dublikat tekshiruvidan o'tkazildi.</i>"
    return msg


async def send_metro_alert(
    bot: Bot,
    item: NewsItem,
    chat_ids: Optional[List[int]] = None,
    pre_analyzed_result: Optional[AIAnalysisResult] = None
) -> int:
    """
    Aniqlangan metro xabarini asl sarlavhasi va asl matni bilan (AI o'zgartirishlarisiz),
    fotosurat va '🔗 Asl manbani ochish' tugmasi bilan yuboradi.
    AI faqat xabarning haqiqiyligini tekshirish uchun ishlatiladi.
    """
    # 1. AI orqali haqiqiylikni tekshirish (Verifikatsiya)
    ai_result = pre_analyzed_result
    if ai_result is None:
        try:
            ai_result = await ai_analyzer.verify_metro_news(item)
        except Exception as exc:
            logger.error(f"AI verifikatsiya jarayonida xatolik: {exc}")
            ai_result = ai_analyzer._build_local_result(item)

    # Agar AI postni Toshkent metrosiga aloqasiz (reklama/sport/chet el) deb topsa, yuborilmaydi
    if ai_result and not ai_result.is_metro:
        logger.info(f"Post rad etildi (AI: Metroga tegishli emas): '{item.title[:60]}' | Sabab: {ai_result.reason}")
        return 0

    # 2. Xabar matnini tayyorlash (Asl manba sarlavhasi va matni)
    try:
        text = ai_result.to_telegram_html(item)
        caption_text = ai_result.to_telegram_caption_html(item)
    except Exception as exc:
        logger.warning(f"Xabarni formatlashda ogohlantirish: {exc}")
        text = format_alert_message(item)
        caption_text = text

    # Antidublikat xotirasida asl ma'lumotlarni saqlash
    try:
        from core.deduplicator import deduplicator
        deduplicator.update_event_ai(
            url=item.url,
            ai_title=item.title.strip(),
            ai_summary=item.content.strip()[:350],
            ai_badge=ai_result.badge if ai_result else "🚇 METRO XABARI",
            image_url=item.image_url or "",
            station="",
            status="",
            advice="",
            full_html=text,
            caption_html=caption_text
        )
    except Exception as exc:
        logger.debug(f"Antidublikat xotirasini yangilashda xatolik: {exc}")

    # 3. Yagona inline tugma (Asl manba)
    item_url = item.url.strip() if item.url else "https://tashmetro.uz"
    if not item_url.startswith("http"):
        item_url = f"https://{item_url}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Asl manbani ochish",
                    url=item_url
                )
            ]
        ]
    )

    targets = chat_ids if chat_ids is not None else settings.target_chat_ids
    successful_deliveries = 0

    # 4. Fotosurat faylini oldindan yuklab olish (xatolik bo'lmasligi uchun)
    photo_file = None
    if item.image_url:
        photo_file = await download_photo_file(item.image_url)

    uploaded_photo_id: Optional[str] = None

    for chat_id in targets:
        # Fotosurat bilan yuborish (Photo Card)
        if photo_file or uploaded_photo_id:
            try:
                caption_text = ai_result.to_telegram_caption_html(item) if hasattr(ai_result, "to_telegram_caption_html") else text
                # 1-marta baytlar yuklanadi, keyingi adminlarga Telegram file_id ishlatiladi (tarmoq trafigi va CPU 3x tejaladi)
                photo_payload = uploaded_photo_id if uploaded_photo_id else photo_file
                sent_msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_payload,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                if not uploaded_photo_id and sent_msg and sent_msg.photo:
                    uploaded_photo_id = sent_msg.photo[-1].file_id

                successful_deliveries += 1
                logger.info(f"Metro xabarnomasi (RASM BILAN) muvaffaqiyatli yetkazildi: Chat ID {chat_id}")
                continue
            except Exception as pe:
                logger.warning(f"Rasm bilan jo'natishda xatolik ({pe}), matn sifatida qayta jo'natilmoqda...")

        # Rasm bo'lmaganda matn ko'rinishida yuborish
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            successful_deliveries += 1
            logger.info(f"Metro xabarnomasi muvaffaqiyatli yetkazildi: Chat ID {chat_id}")
        except TelegramBadRequest as exc:
            logger.warning(f"HTML formatlash xatosi (Chat ID {chat_id}): {exc}. Standart formatda qayta urinilmoqda...")
            try:
                fallback_text = format_alert_message(item)
                await bot.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=False
                )
                successful_deliveries += 1
            except Exception as e2:
                logger.error(f"Xabarni qayta jo'natishda ham xatolik: {e2}")
        except Exception as e:
            logger.error(f"Chatga ({chat_id}) xabar yetkazishda xatolik: {e}")

    return successful_deliveries
