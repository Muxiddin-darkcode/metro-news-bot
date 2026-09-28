import time
import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from config import settings, format_uz_time
from core.storage import storage
from core.deduplicator import deduplicator
from parsers.manager import source_manager
from bot.notifier import send_metro_alert

router = Router()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin uchun orqa foni rangli (style='success' - yashil, style='primary' - ko'k)
    va bittadan toza ikonkali tugmalar.
    """
    kb = [
        [
            KeyboardButton(text="🔍 Hozir tekshirish", style="success"),
            KeyboardButton(text="📊 Tizim holati", style="primary")
        ],
        [
            KeyboardButton(text="🌐 Manbalar (80 ta)", style="primary"),
            KeyboardButton(text="🏷️ Kalit so'zlar", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=True)

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Assalomu alaykum, Administrator!</b>\n\n"
        "🚇 <b>Toshkent Metropoliteni Monitoring Tizimi</b> faol holatda ishlamoqda.\n\n"
        "Tizim 24/7 rejimida:\n"
        "• <b>40 ta eng yirik O'zbekiston Telegram kanallari</b>\n"
        "• <b>OAV va rasmiy transport veb-saytlari</b>\n"
        "oqimini doimiy tahlil qiladi.\n\n"
        "Metroga oid yangilik, nosozlik yoki kechikish chiqishi bilanoq "
        "sizga birinchilardan bo'lib yetkaziladi.\n\n"
        "Boshqaruv uchun quyidagi rangli tugmalardan foydalanishingiz mumkin:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

def build_status_text() -> str:
    """Tizim holati matnini formatlash (O'zbekiston vaqti bilan)."""
    last_time = "Hali tekshirilmadi"
    if source_manager.last_check_time > 0:
        last_time = format_uz_time(source_manager.last_check_time, "%H:%M:%S | %d.%m.%Y")

    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_sources = tg_count + web_count
    
    group_count = len(settings.group_id_list)
    group_info = f"\n📢 <b>Ulangan guruhlar:</b> {group_count} ta" if group_count > 0 else "\n📢 <b>Ulangan guruh:</b> Hali ulanmagan"

    return (
        "📊 <b>TIZIM HOLATI VA STATISTIKASI:</b>\n\n"
        "🟢 <b>Status:</b> 24/7 Faol (Monitoring ishlamoqda)\n"
        f"🌐 <b>Kuzatilayotgan manbalar:</b> {total_sources} ta\n"
        f"  ├ 📱 Telegram kanallar: {tg_count} ta\n"
        f"  └ 💻 Yangilik saytlari: {web_count} ta\n\n"
        f"⏱️ <b>Avtomatik tekshirish:</b> har {settings.CHECK_INTERVAL_SECONDS} soniyada\n"
        f"⚡ <b>Oxirgi tekshiruv vaqti:</b> {last_time}\n"
        f"⏳ <b>Skaner davomiyligi:</b> {source_manager.last_check_duration:.2f} soniya\n"
        f"🗂️ <b>Keshdagi xabarlar (No-DB):</b> {storage.count} ta\n"
        f"🧠 <b>Antidublikat xotirasi (24 soat):</b> {len(deduplicator._history)} ta voqea\n"
        f"👥 <b>Ruxsat etilgan adminlar:</b> {len(settings.admin_id_list)} ta"
        f"{group_info}"
    )

@router.message(Command("id", "group_id", "getid"))
async def cmd_get_id(message: Message):
    chat = message.chat
    chat_type = chat.type
    chat_id = chat.id
    chat_title = chat.title or chat.full_name or "Chat"
    
    await message.answer(
        f"📋 <b>CHAT MA'LUMOTLARI:</b>\n\n"
        f"🏷️ <b>Nomi:</b> {chat_title}\n"
        f"📁 <b>Turi:</b> <code>{chat_type}</code>\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
        f"💡 <i>Guruhga xabarlar borishi uchun ushbu ID ni .env faylidagi <code>GROUP_ID={chat_id}</code> qatoriga qo'ying.</i>",
        parse_mode="HTML"
    )

@router.message(Command("status"))
@router.message(F.text.contains("Tizim holati") | F.text.contains("TIZIM HOLATI"))
async def cmd_status(message: Message):
    await message.answer(build_status_text(), parse_mode="HTML", reply_markup=get_main_keyboard())

@router.callback_query(F.data == "btn_status")
async def callback_status(call: CallbackQuery):
    if call.from_user.id not in settings.admin_id_list:
        await call.answer("Faqat adminlar uchun!", show_alert=True)
        return
    await call.answer()
    await call.message.answer(build_status_text(), parse_mode="HTML", reply_markup=get_main_keyboard())


@router.message(Command("check"))
@router.message(F.text.contains("Hozir tekshirish") | F.text.contains("HOZIR TEKSHIRISH"))
async def cmd_check(message: Message):
    status_msg = await message.answer(
        "⏳ <b>Barcha manbalar parallel ravishda tekshirilmoqda...</b>\n"
        "Iltimos, kuting (bu 5–10 soniya vaqt oladi).",
        parse_mode="HTML"
    )

    try:
        new_alerts, stats = await source_manager.scan_all_sources()
        
        for item in new_alerts:
            await send_metro_alert(message.bot, item)

        result_text = (
            "✅ <b>Tekshiruv yakunlandi!</b>\n\n"
            f"⏱️ Sarflangan vaqt: <b>{stats['elapsed_seconds']} soniya</b>\n"
            f"🌐 Tekshirilgan manbalar: <b>{stats['total_sources']} ta</b>\n"
            f"📥 Yig'ilgan so'nggi postlar: <b>{stats['raw_posts_fetched']} ta</b>\n"
            f"🚨 Topilgan yangi metro xabarlari: <b>{stats['metro_alerts_found']} ta</b>"
        )
        await status_msg.edit_text(result_text, parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(f"❌ Tekshirishda xatolik yuz berdi: {e}")

@router.callback_query(F.data == "btn_check_now")
async def callback_check_now(call: CallbackQuery):
    if call.from_user.id not in settings.admin_id_list:
        await call.answer("Faqat adminlar uchun!", show_alert=True)
        return
    await call.answer("Tekshiruv boshlandi...", show_alert=False)
    status_msg = await call.message.answer(
        "⏳ <b>Barcha manbalar qayta tekshirilmoqda...</b>",
        parse_mode="HTML"
    )
    try:
        new_alerts, stats = await source_manager.scan_all_sources()
        for item in new_alerts:
            await send_metro_alert(call.bot, item)

        result_text = (
            "✅ <b>Tekshiruv yakunlandi!</b>\n"
            f"⏱️ Vaqt: <b>{stats['elapsed_seconds']}s</b> | "
            f"🚨 Yangi xabarlar: <b>{stats['metro_alerts_found']} ta</b>"
        )
        await status_msg.edit_text(result_text, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {e}")

@router.message(Command("sources"))
@router.message(F.text.contains("Manbalar") | F.text.contains("MANBALAR"))
async def cmd_sources(message: Message):
    tg_samples = [f"@{ch['username']}" for ch in source_manager.telegram_channels[:15]]
    web_samples = [src['name'] for src in source_manager.web_sources[:12]]

    text = (
        "🌐 <b>KUZATILAYOTGAN 80 TA ASOSIY MANBA:</b>\n\n"
        f"📱 <b>Telegram Kanallar (40 ta):</b>\n"
        f"{', '.join(tg_samples)} va yana 25 ta...\n\n"
        f"💻 <b>Yangilik Veb-Saytlari (25+ ta):</b>\n"
        f"{', '.join(web_samples)} va yana boshqalar...\n\n"
        "<i>Barcha manbalar data/sources.json faylida jamlangan.</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@router.message(Command("keywords"))
@router.message(F.text.contains("Kalit so'zlar") | F.text.contains("KALIT SO'ZLAR"))
async def cmd_keywords(message: Message):
    text = (
        "🏷️ <b>METRO FILTR KALIT SO'ZLARI:</b>\n\n"
        "🚇 <b>Asosiy:</b> metro, metrosi, metropoliten, тошметро, tashmetro\n\n"
        "🚉 <b>Bekatlar:</b> Paxtakor bekati, Chilonzor bekati, Amir Temur bekati, "
        "Yunusobod bekati, Alisher Navoiy bekati, Turkiston bekati, va h.k.\n\n"
        "⚠️ <b>Hodisalar:</b> to'xtab qoldi, nosozlik, kechikish, vagon, poyezd, rels, mashinist, "
        "tutun, tirbandlik, interval, chipta, turniket, tarif.\n\n"
        "<i>Filtr O'zbekcha (Lotin va Kirill) xabarlarni to'liq qamrab oladi.</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())
