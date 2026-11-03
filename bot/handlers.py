"""
Metro Monitoring Bot - Kengaytirilgan Admin Boshqaruv Paneli va Handlerlar.
aiogram 3.x asosida to'liq asinxron ishlaydi.
Barcha boshqaruv qat'iy ravishda Reply Keyboard (rangli tugmalar) orqali amalga oshiriladi.
Faqatgina alohida yangilik postlarida '🔗 Asl manbani ochish' inline tugmasi qoldirilgan.
Matnlarda separator chiziqlar o'rniga toza paragraflar (bo'sh qatorlar) qo'llangan.
"""

import html
import time
import asyncio
import datetime
from typing import Optional, List, Dict

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import settings, format_uz_time, logger, get_recent_logs
from core.storage import storage
from core.deduplicator import deduplicator
from core.filter import (
    is_metro_related,
    explain_filter,
    add_custom_keyword,
    remove_custom_keyword,
    get_custom_keywords
)
from parsers.base import NewsItem
from parsers.manager import source_manager
from bot.notifier import send_metro_alert, download_photo_file
from bot.states import AdminStates
from core.ai_analyzer import ai_analyzer, safe_truncate_words
from bot.keyboards import (
    get_main_keyboard,
    get_collapsed_keyboard,
    get_settings_reply_keyboard,
    get_sources_reply_keyboard,
    get_ai_reply_keyboard,
    get_logs_reply_keyboard,
    get_cache_reply_keyboard,
    get_keywords_reply_keyboard,
    get_cancel_keyboard,
    post_source_url_kb
)

router = Router()

# =========================================================================
# MATN VA XABAR GENERATORLARI (SEPARATOR CHIZIQLARSIZ, TOZA INTERFEYS)
# =========================================================================

def build_dashboard_text() -> str:
    """Admin Dashboard asosiy ekrani uchun ixcham va to'liq ma'lumot."""
    status_icon = "⏸️ To'xtatilgan" if source_manager.is_paused else "🟢 24/7 Faol"
    ai_icon = "🟢 Faol" if settings.AI_ENABLED else "⏸️ O'chirilgan"
    last_time = "Hali yo'q"
    if source_manager.last_check_time > 0:
        last_time = format_uz_time(source_manager.last_check_time, "%H:%M:%S")

    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_sources = tg_count + web_count

    return (
        "🚇 <b>TOSHKENT METROPOLITENI MONITORING TIZIMI</b>\n\n"
        f"• <b>Monitoring holati:</b> {status_icon}\n"
        f"• <b>AI Tahlilchi (Dual AI):</b> {ai_icon}\n"
        f"• <b>Kuzatilayotgan manbalar:</b> <b>{total_sources} ta</b> (📱 {tg_count} kanal, 💻 {web_count} sayt)\n"
        f"• <b>Avtomatik tekshiruv:</b> har {settings.CHECK_INTERVAL_SECONDS} soniyada\n"
        f"• <b>Oxirgi skaner:</b> {last_time} ({source_manager.last_check_duration:.1f}s)\n"
        f"• <b>Keshdagi postlar:</b> {storage.count} ta | <b>Dublikat xotirasi:</b> {len(deduplicator._history)} ta\n\n"
        "<i>Pastdagi boshqaruv menyusidan kerakli bo'limni tanlang:</i>"
    )


def build_status_text() -> str:
    """Tizim holati va to'liq statistika."""
    last_time = "Hali tekshirilmadi"
    if source_manager.last_check_time > 0:
        last_time = format_uz_time(source_manager.last_check_time, "%H:%M:%S | %d.%m.%Y")

    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_sources = tg_count + web_count
    
    group_count = len(settings.group_id_list)
    group_info = f"\n📢 <b>Ulangan guruhlar:</b> {group_count} ta" if group_count > 0 else "\n📢 <b>Ulangan guruh:</b> Hali ulanmagan"
    state_str = "⏸️ Vaqtincha to'xtatilgan" if source_manager.is_paused else "🟢 24/7 Faol"

    return (
        "📊 <b>TIZIMNING TO'LIQ STATISTIKASI:</b>\n\n"
        f"<b>Holat:</b> {state_str}\n"
        f"🌐 <b>Kuzatilayotgan manbalar:</b> {total_sources} ta\n"
        f"  ├ 📱 Telegram kanallar: {tg_count} ta\n"
        f"  └ 💻 Yangilik saytlari va RSS: {web_count} ta\n\n"
        f"⏱️ <b>Avtomatik tekshirish oralig'i:</b> har {settings.CHECK_INTERVAL_SECONDS} soniyada\n"
        f"⚡ <b>Oxirgi tekshiruv vaqti:</b> {last_time}\n"
        f"⏳ <b>Oxirgi skaner davomiyligi:</b> {source_manager.last_check_duration:.2f} soniya\n"
        f"🧠 <b>Antidublikat chegarasi:</b> {settings.SIMILARITY_THRESHOLD * 100:.0f}%\n"
        f"🗂️ <b>Keshdagi ko'rilgan postlar:</b> {storage.count} ta\n"
        f"🧠 <b>Antidublikat xotirasi (oxirgi 24 soat):</b> {len(deduplicator._history)} ta voqea\n"
        f"👥 <b>Ruxsat etilgan adminlar:</b> {len(settings.admin_id_list)} ta"
        f"{group_info}\n\n"
        f"<i>Tizim barcha {total_sources} ta nufuzli manbani parallel ravishda barqaror kuzatib bormoqda.</i>"
    )


def build_recent_news_text() -> str:
    """Tizim tomonidan topilgan eng so'nggi metro xabarlari ro'yxati."""
    events = deduplicator.get_recent_events(limit=8)
    if not events:
        return (
            "📰 <b>SO'NGGI METRO XABARLARI</b>\n\n"
            "<i>Hozircha tizim xotirasida topilgan yangi metro voqealari yo'q.\n"
            "Manbalardan yangilik chiqqan zahoti bu yerda avtomatik aks etadi.</i>"
        )

    lines = ["📰 <b>SO'NGGI ANIQLANGAN METRO XABARLARI:</b>\n"]
    for i, ev in enumerate(events, 1):
        t_str = format_uz_time(ev.get("timestamp", 0), "%H:%M | %d.%m")
        title = html.escape(ev.get("ai_title") or ev.get("title", "Sarlavhasiz"), quote=False)
        source = html.escape(ev.get("source", "Noma'lum"), quote=False)
        badge = ev.get("ai_badge") or "🚇 METRO"
        url = ev.get("url", "")
        url_link = f' <a href="{url}">[Asl manba]</a>' if url else ""
        lines.append(f"<b>{i}. {badge}</b> [{t_str}] <b>{source}</b>:\n{title}{url_link}\n")

    return "\n".join(lines)


def build_ai_status_text() -> str:
    """AI Tahlilchi holati haqida to'liq professional ma'lumot (hech qanday test yoki dummy matnsiz)."""
    st = ai_analyzer.get_status_info()
    status_icon = "🟢 Faol" if st["ai_enabled"] else "⏸️ O'chirilgan"

    gemini_key_str = "✅ Ulangan" if st["gemini_configured"] else "❌ Kalit kiritilmagan"
    openrouter_key_str = "✅ Ulangan" if st["openrouter_configured"] else "❌ Kalit kiritilmagan"

    total_sources = len(source_manager.telegram_channels) + len(source_manager.web_sources)

    return (
        "🤖 <b>AI TAHLILCHI VA DUBLIKAT NAZORATI TIZIMI</b>\n\n"
        f"• <b>Umumiy holat:</b> {status_icon}\n\n"
        f"1️⃣ <b>Asosiy provayder (Google Gemini):</b>\n"
        f"   ├ Holati: <b>{gemini_key_str}</b>\n"
        f"   └ Model: <code>{st['gemini_model']}</code>\n\n"
        f"2️⃣ <b>Zaxira provayder (OpenRouter Fallback):</b>\n"
        f"   ├ Holati: <b>{openrouter_key_str}</b>\n"
        f"   └ Model: <code>{st['openrouter_model']}</code>\n\n"
        "⚡ <b>Qanday ishlaydi?</b>\n"
        f"Kuzatilayotgan <b>{total_sources} ta</b> nufuzli OAV va Telegram kanallardan kelayotgan har bir metro yangiligi avtomatik tarzda sun'iy intellekt orqali tahlil qilinadi: reklama, chaqiriq va ortiqcha matnlardan tozalanadi, voqea joyi va sababi aniqlanadi hamda rasmi bilan birga guruh va kanalga yetkaziladi. Asosiy provayderda limit tugasa, tizim avtomatik zaxira provayderiga ulanadi."
    )


def build_settings_text() -> str:
    """Sozlamalar matni."""
    status_str = "⏸️ Vaqtincha to'xtatilgan" if source_manager.is_paused else "🟢 Faol"
    return (
        "⚙️ <b>TIZIM VA MONITORING SOZLAMALARI:</b>\n\n"
        f"• <b>Monitoring holati:</b> {status_str}\n"
        f"• <b>Tekshirish intervali:</b> har <b>{settings.CHECK_INTERVAL_SECONDS} soniyada</b>\n"
        f"• <b>Antidublikat chegarasi:</b> <b>{settings.SIMILARITY_THRESHOLD * 100:.0f}%</b>\n"
        f"• <b>Parallel so'rovlar limiti:</b> <b>{settings.MAX_CONCURRENT_REQUESTS} ta</b>\n\n"
        "<i>Kerakli sozlamani quyidagi tugmalar orqali boshqaring:</i>"
    )


def build_keywords_text() -> str:
    """Filtr kalit so'zlari matni."""
    custom_kws = get_custom_keywords()
    custom_str = ", ".join(custom_kws) if custom_kws else "Hozircha qo'shilmagan"
    return (
        "🏷️ <b>METRO FILTR KALIT SO'ZLARI:</b>\n\n"
        "🚇 <b>Asosiy o'zaklar:</b> metro, metrosi, metropoliten, toshmetro, tashmetro, yerosti, yerusti metrosi\n\n"
        "🚉 <b>Metro liniyalari va bekatlar:</b> Chilonzor, O'zbekiston, Yunusobod, Sergeli, Halqa yo'li va barcha 50+ bekat nomlari (ham lotin, ham kirill, ham yangi alifbo variantlari bilan).\n\n"
        "⚠️ <b>Hodisa belgilari:</b> to'xtab qoldi, nosozlik, kechikish, vagon, poyezd, rels, mashinist, tutun, tirbandlik, interval, chipta, turniket, tarif.\n\n"
        f"✨ <b>Qo'shimcha maxsus so'zlar ({len(custom_kws)} ta):</b>\n"
        f"<code>{custom_str}</code>"
    )


def build_cache_text() -> str:
    """Kesh holati matni."""
    return (
        "🧹 <b>KESH VA XOTIRANI BOSHQARISH:</b>\n\n"
        f"• <b>Keshdagi xabarlar (seen_posts):</b> <b>{storage.count} ta</b>\n"
        f"• <b>Antidublikat izlari (seen_fingerprints):</b> <b>{len(deduplicator._history)} ta</b> voqea\n\n"
        "💡 <i>Keshni tozalash avval ko'rilgan xabarlarning qayta tekshirilishiga imkon yaratadi.</i>"
    )


# =========================================================================
# ASOSIY MENU HANDLERLARI (REPLY KEYBOARD)
# =========================================================================

@router.message(StateFilter("*"), Command("close", "hide"))
@router.message(StateFilter("*"), F.text.in_(["❌ Panelni yopish", "Panelni yopish", "❌ Yopish", "Yopish"]) | F.text.lower().contains("yopish"))
async def cmd_close_panel(message: Message, state: FSMContext) -> None:
    """Boshqaruv panelini yig'ish (bitta ixcham tugma holatiga keltirish)."""
    await state.clear()
    await message.answer(
        "<i>Boshqaruv paneli yig'ildi. Qayta ochish uchun pastdagi tugmani bosing:</i>",
        parse_mode="HTML",
        reply_markup=get_collapsed_keyboard()
    )


@router.message(StateFilter("*"), Command("start", "menu", "panel", "dashboard", "cancel"))
@router.message(StateFilter("*"), F.text.in_(["◀️ Asosiy menyu", "❌ Bekor qilish", "Bekor qilish", "Asosiy menyu"]))
@router.message(StateFilter("*"), F.text.in_(["🎛 Panel", "🎛 Boshqaruv paneli", "Panel", "Boshqaruv", "🎛 Panelni ochish", "Panelni ochish"]) | F.text.lower().contains("ochish"))
async def cmd_main_menu(message: Message, state: FSMContext) -> None:
    """Asosiy menyuga qaytish va FSM holatini bekor qilish."""
    await state.clear()
    await message.answer(
        build_dashboard_text(),
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter("*"), Command("check"))
@router.message(StateFilter("*"), F.text.in_(["🔍 Tekshirish", "🔍 Hozir tekshirish"]))
async def cmd_check_now(message: Message, state: FSMContext) -> None:
    """Barcha kuzatilayotgan manbalarni parallel tekshirish va yangi xabarlarni jo'natish."""
    await state.clear()
    if getattr(source_manager, "is_scanning", False):
        await message.answer(
            "⏳ <b>Hozirda manbalar tekshirilmoqda...</b>\n"
            "Monitoring jarayoni orqa fonda ketmoqda, iltimos natija tayyor bo'lishini kuting.",
            parse_mode="HTML"
        )
        return

    status_msg = await message.answer(
        "⏳ <b>Barcha manbalar parallel tekshirilmoqda...</b>\n"
        "Iltimos, kuting (bu bir necha soniya vaqt oladi)...",
        parse_mode="HTML"
    )
    try:
        new_alerts, stats = await source_manager.scan_all_sources()
        for idx, item in enumerate(new_alerts, 1):
            await send_metro_alert(message.bot, item)
            if idx < len(new_alerts):
                await asyncio.sleep(0.5)

        result_text = (
            "✅ <b>Tekshiruv muvaffaqiyatli yakunlandi!</b>\n\n"
            f"⏱️ <b>Sarflangan vaqt:</b> {stats['elapsed_seconds']} soniya\n"
            f"🌐 <b>Tekshirilgan manbalar:</b> {stats['total_sources']} ta ({stats['channels_count']} kanal, {stats['web_count']} sayt)\n"
            f"📥 <b>Yig'ilgan so'nggi postlar:</b> {stats['raw_posts_fetched']} ta\n"
            f"🚨 <b>Topilgan yangi metro xabarlari:</b> {stats['metro_alerts_found']} ta"
        )
        await status_msg.edit_text(result_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Hozir tekshirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Tekshirishda xatolik yuz berdi: {e}", parse_mode="HTML")


@router.message(StateFilter("*"), Command("today"))
@router.message(StateFilter("*"), F.text.in_(["📅 Bugungi xabarlar", "📅 Bugungi yangiliklar"]))
async def cmd_today_news(message: Message, state: FSMContext) -> None:
    """Bugungi kun bo'yicha metro yangiliklarini AI tahlillari va rasmlari bilan ketma-ket chiqarish."""
    await state.clear()
    events = deduplicator.get_today_events()
    now_str = format_uz_time(fmt="%d.%m.%Y")

    if not events:
        total_src = len(source_manager.telegram_channels) + len(source_manager.web_sources)
        await message.answer(
            f"📅 <b>BUGUNGI METRO YANGILIKLARI ({now_str})</b>\n\n"
            "<i>Bugun hozircha monitoring orqali yangi metro yangiligi aniqlanmadi.\n"
            f"Tizim {total_src} ta rasmiy va ommabop manbani 24/7 rejimida uzluksiz kuzatmoqda.</i>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        f"📅 <b>BUGUNGI METRO YANGILIKLARI ({now_str})</b>\n\n"
        f"Bugun jami <b>{len(events)} ta</b> metro yangiligi aniqlangan.\n"
        "AI tahliliy xulosalari va fotosuratlari bilan taqdim etilmoqda:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

    for idx, ev in enumerate(events, 1):
        title = html.escape(ev.get("ai_title") or ev.get("title", "Sarlavhasiz"), quote=False)
        badge = html.escape(ev.get("ai_badge") or "🚇 METRO XABARI", quote=False)
        raw_summary = ev.get("ai_summary") or ev.get("content", "")
        summary = html.escape(safe_truncate_words(raw_summary, 220), quote=False)
        source = html.escape(ev.get("source", "Noma'lum manba"), quote=False)
        t_str = format_uz_time(ev.get("timestamp", 0), "%H:%M")
        url = ev.get("url", "")
        image_url = ev.get("image_url", "")
        station = ev.get("ai_station", "")
        status = ev.get("ai_status", "")
        advice = ev.get("ai_advice", "")

        # Toza, ixcham va to'liq matn ko'rinishi
        lines = [
            f"🚇 <b>TOSHKENT METROSI | {badge}</b>\n",
            f"📌 <b>{title}</b>\n",
            f"📋 <b>Tahlil:</b> {summary}\n"
        ]
        details = []
        if station:
            st_l = station.lower()
            if not any(ign in st_l for ign in ["noma'lum", "umumiy tarmoq", "none", "butun", "tutash"]):
                details.append(f"📍 <b>Hudud:</b> {html.escape(station.strip(), quote=False)}")
        if status:
            st_clean = safe_truncate_words(status.strip(), 70)
            details.append(f"🚦 <b>Holat:</b> {html.escape(st_clean, quote=False)}")
        if details:
            lines.append("\n".join(details) + "\n")
        if advice:
            lines.append(f"💡 <b>Tavsiya:</b> <i>{html.escape(advice.strip(), quote=False)}</i>\n")

        lines.append(f"🕒 <b>Vaqt:</b> {t_str} | 🏛️ <b>Manba:</b> {source}")
        card_text = "\n".join(lines)

        item_kb = post_source_url_kb(url) if url else None

        # Rasmni yuklab olib BufferedInputFile orqali yuborish
        sent_photo = False
        if image_url:
            photo_file = await download_photo_file(image_url)
            if photo_file:
                try:
                    await message.answer_photo(
                        photo=photo_file,
                        caption=card_text,
                        parse_mode="HTML",
                        reply_markup=item_kb
                    )
                    sent_photo = True
                except Exception as pe:
                    logger.warning(f"Rasm bilan yuborishda xatolik ({pe}), matn ko'rinishida yuboriladi")

        if not sent_photo:
            await message.answer(
                text=card_text,
                parse_mode="HTML",
                reply_markup=item_kb,
                disable_web_page_preview=False
            )

        if idx < len(events):
            await asyncio.sleep(1.2)


@router.message(StateFilter("*"), Command("ai"))
@router.message(StateFilter("*"), F.text == "🤖 AI Tahlilchi")
async def cmd_ai_menu(message: Message, state: FSMContext) -> None:
    """AI Tahlilchi bo'limini ochish va Reply klaviaturani ko'rsatish."""
    await state.clear()
    await message.answer(
        build_ai_status_text(),
        parse_mode="HTML",
        reply_markup=get_ai_reply_keyboard(settings.AI_ENABLED)
    )


@router.message(StateFilter("*"), F.text.in_(["🔄 Aloqani tekshirish", "🔄 Tekshirish", "🔄 Provayderlarni tekshirish"]))
async def cmd_ai_check_providers(message: Message) -> None:
    """AI provayderlarining aloqasini real tekshirish."""
    status_msg = await message.answer(
        "⏳ <b>Gemini va OpenRouter provayderlari bilan aloqa tekshirilmoqda...</b>",
        parse_mode="HTML"
    )
    start_time = time.time()
    st = ai_analyzer.get_status_info()

    g_ok = False
    o_ok = False
    try:
        if st["gemini_configured"]:
            res_g = await ai_analyzer._call_gemini_api("Toshkent metrosi")
            g_ok = bool(res_g)
    except Exception as ge:
        logger.debug(f"Gemini test xatosi: {ge}")

    try:
        if st["openrouter_configured"]:
            res_o = await ai_analyzer._call_openrouter_api("Toshkent metrosi")
            o_ok = bool(res_o)
    except Exception as oe:
        logger.debug(f"OpenRouter test xatosi: {oe}")

    elapsed = time.time() - start_time
    g_status = "🟢 Aloqa a'lo (200 OK)" if g_ok else "🔴 Ulanmadi"
    o_status = "🟢 Aloqa a'lo (200 OK)" if o_ok else "🔴 Ulanmadi"

    msg = (
        "🤖 <b>AI PROVAYDERLARI ALOQA NATIJASI:</b>\n\n"
        f"1️⃣ <b>Google Gemini ({st['gemini_model']}):</b> {g_status}\n"
        f"2️⃣ <b>OpenRouter ({st['openrouter_model']}):</b> {o_status}\n\n"
        f"⏱️ <b>Javob vaqti:</b> {elapsed:.2f} soniya\n\n"
        "⚡ <i>Barcha monitoring yangiliklari ushbu sun'iy intellekt tizimi orqali real vaqtda qayta ishlanadi.</i>"
    )
    await status_msg.edit_text(msg, parse_mode="HTML")


@router.message(StateFilter("*"), F.text.in_(["▶️ AI ni yoqish", "⏸️ AI ni o'chirish", "▶️ Yoqish", "⏸️ O'chirish"]))
async def cmd_ai_toggle(message: Message) -> None:
    """AI tahlilchini yoqish / o'chirish."""
    settings.AI_ENABLED = not settings.AI_ENABLED
    action_text = "yoqildi va faol" if settings.AI_ENABLED else "vaqtincha o'chirildi"
    await message.answer(
        f"🤖 <b>AI Tahlilchi {action_text}!</b>",
        parse_mode="HTML",
        reply_markup=get_ai_reply_keyboard(settings.AI_ENABLED)
    )


@router.message(StateFilter("*"), Command("history", "news"))
@router.message(StateFilter("*"), F.text == "📰 So'nggi xabarlar")
async def cmd_recent_news(message: Message, state: FSMContext) -> None:
    """Oxirgi aniqlangan metro xabarlarini ko'rsatish."""
    await state.clear()
    await message.answer(
        build_recent_news_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )


@router.message(StateFilter("*"), Command("status"))
@router.message(StateFilter("*"), F.text == "📊 Tizim holati")
async def cmd_status(message: Message, state: FSMContext) -> None:
    """Tizim holatini ko'rsatish."""
    await state.clear()
    await message.answer(
        build_status_text(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@router.message(StateFilter("*"), Command("sources"))
@router.message(StateFilter("*"), F.text == "🌐 Manbalar")
async def cmd_sources_menu(message: Message, state: FSMContext) -> None:
    """Manbalar bo'limi Reply klaviaturasini ochish."""
    await state.clear()
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_count = tg_count + web_count
    await message.answer(
        "🌐 <b>KUZATILAYOTGAN MANBALAR BOSHQARUVI:</b>\n\n"
        f"• 📱 Telegram kanallar: <b>{tg_count} ta</b>\n"
        f"• 💻 Veb-saytlar va OAV: <b>{web_count} ta</b>\n"
        f"• Jami manbalar: <b>{total_count} ta</b>\n\n"
        "<i>Kerakli ro'yxatni ko'rish yoki yangi manba kiritish uchun quyidagi tugmalardan foydalaning:</i>",
        reply_markup=get_sources_reply_keyboard(tg_count, web_count),
        parse_mode="HTML"
    )


@router.message(StateFilter("*"), F.text.startswith("📱 Telegram"))
async def cmd_list_tg_channels(message: Message, state: FSMContext) -> None:
    """Barcha kuzatilayotgan Telegram kanallari ro'yxatini matn ko'rinishida chiqarish."""
    await state.clear()
    channels = source_manager.telegram_channels
    tg_count = len(channels)
    web_count = len(source_manager.web_sources)

    chunk_size = 40
    chunks = [channels[i:i + chunk_size] for i in range(0, len(channels), chunk_size)]

    for idx, chunk in enumerate(chunks, 1):
        lines = [f"📱 <b>TELEGRAM KANALLAR RO'YXATI ({idx}/{len(chunks)}):</b>\n"]
        for c_idx, ch in enumerate(chunk, (idx - 1) * chunk_size + 1):
            name = html.escape(ch.get("name", "Kanal"), quote=False)
            user = ch.get("username", "")
            lines.append(f"<b>{c_idx}.</b> {name} — <a href=\"https://t.me/{user}\">@{user}</a>")
        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_sources_reply_keyboard(tg_count, web_count)
        )


@router.message(StateFilter("*"), F.text.startswith("💻 Saytlar") | F.text.startswith("💻 Veb-saytlar"))
async def cmd_list_web_sources(message: Message, state: FSMContext) -> None:
    """Barcha kuzatilayotgan Veb-saytlar ro'yxatini matn ko'rinishida chiqarish."""
    await state.clear()
    websites = source_manager.web_sources
    tg_count = len(source_manager.telegram_channels)
    web_count = len(websites)

    lines = [f"💻 <b>VEB-SAYTLAR VA RSS RO'YXATI ({web_count} ta):</b>\n"]
    for idx, site in enumerate(websites, 1):
        name = html.escape(site.get("name", "Sayt"), quote=False)
        url = site.get("url", "")
        src_type = site.get("type", "rss").upper()
        lines.append(f"<b>{idx}.</b> <b>{name}</b> ({src_type}) — <a href=\"{url}\">{url}</a>")

    lines.append(
        "\n⚡ <i>Veb-saytlardan chiqqan barcha maqolalarning asosiy rasmlari Open Graph (og:image) orqali avtomatik yuklab olinadi.</i>"
    )

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_sources_reply_keyboard(tg_count, web_count)
    )


@router.message(StateFilter("*"), F.text.in_(["➕ Kanal", "➕ Kanal qo'shish"]))
async def cmd_add_tg_start(message: Message, state: FSMContext) -> None:
    """Telegram kanal qo'shish so'rovini boshlash."""
    await state.set_state(AdminStates.waiting_for_tg_username)
    await message.answer(
        "➕ <b>YANGI TELEGRAM KANAL QO'SHISH:</b>\n\n"
        "Kanalning <b>@username</b>ini yoki havolasini yuboring (masalan: <code>@tashkent_news</code>):\n\n"
        "<i>Bekor qilish uchun '❌ Bekor qilish' tugmasini bosing.</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_tg_username))
async def process_add_tg_username(message: Message, state: FSMContext) -> None:
    """Telegram kanal username kiritilganda tekshirish va saqlash."""
    username = message.text.strip().replace("https://t.me/", "").replace("t.me/", "")
    status_msg = await message.answer(f"⏳ <b>@{username} tekshirilmoqda...</b>", parse_mode="HTML")
    
    test_res = await source_manager.test_single_source(username)
    if not test_res.get("success"):
        await status_msg.edit_text(
            f"❌ <b>Kanalni qo'shib bo'lmadi!</b>\n"
            f"Sabab: Kanal ochiq (public) emas yoki xatolik: {test_res.get('error')}",
            parse_mode="HTML"
        )
        return

    success, msg = source_manager.add_telegram_channel(
        username=username,
        name=test_res.get("source_name", username)
    )
    await state.clear()
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)

    if success:
        await status_msg.edit_text(
            f"✅ <b>Muvaffaqiyatli!</b>\n\n"
            f"{msg}\n"
            f"Oxirgi olingan postlar soni: <b>{test_res.get('total_fetched')} ta</b>\n"
            f"Endi ushbu kanal 24/7 monitoring ro'yxatiga kiritildi.",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(f"⚠️ {msg}", parse_mode="HTML")
    await message.answer("Boshqaruv menyusi:", reply_markup=get_sources_reply_keyboard(tg_count, web_count))


@router.message(StateFilter("*"), F.text.in_(["➕ Sayt", "➕ Sayt qo'shish"]))
async def cmd_add_web_start(message: Message, state: FSMContext) -> None:
    """Veb-sayt qo'shish so'rovini boshlash."""
    await state.set_state(AdminStates.waiting_for_web_name)
    await message.answer(
        "➕ <b>YANGI VEB-SAYT QO'SHISH (1/3 QADAM):</b>\n\n"
        "Sayt nomini kiriting (masalan: <code>Gazeta.uz Maxsus</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_web_name))
async def process_add_web_name(message: Message, state: FSMContext) -> None:
    """Sayt nomi qabul qilinganda."""
    await state.update_data(web_name=message.text.strip())
    await state.set_state(AdminStates.waiting_for_web_url)
    await message.answer(
        "🌐 <b>2/3 QADAM:</b>\n\n"
        "Saytning bosh sahifa URL manzilini kiriting (masalan: <code>https://gazeta.uz</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_web_url))
async def process_add_web_url(message: Message, state: FSMContext) -> None:
    """Sayt URL manzili qabul qilinganda."""
    await state.update_data(web_url=message.text.strip())
    await state.set_state(AdminStates.waiting_for_web_feed)
    await message.answer(
        "📡 <b>3/3 QADAM:</b>\n\n"
        "Saytning RSS / Atom Feed manzilini kiriting (masalan: <code>https://gazeta.uz/uz/rss/</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_web_feed))
async def process_add_web_feed(message: Message, state: FSMContext) -> None:
    """Sayt Feed manzili qabul qilinganda saqlash."""
    data = await state.get_data()
    feed_url = message.text.strip()
    name = data.get("web_name", "Yangi Sayt")
    url = data.get("web_url", "")
    await state.clear()

    status_msg = await message.answer("⏳ RSS manba tekshirilmoqda...", parse_mode="HTML")
    success, msg = source_manager.add_web_source(name=name, url=url, feed_url=feed_url)
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)

    if success:
        await status_msg.edit_text(
            f"✅ <b>Muvaffaqiyatli qo'shildi!</b>\n\n"
            f"Sayt: <b>{name}</b>\n"
            f"URL: {url}\n"
            f"RSS: {feed_url}",
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(f"⚠️ {msg}", parse_mode="HTML")
    await message.answer("Boshqaruv menyusi:", reply_markup=get_sources_reply_keyboard(tg_count, web_count))


@router.message(StateFilter("*"), F.text.in_(["🔍 Manbani tekshirish", "🔍 Manba tekshirish"]))
async def cmd_test_source_prompt(message: Message, state: FSMContext) -> None:
    """Manbani testlash uchun nom so'rash."""
    await state.set_state(AdminStates.waiting_for_test_source)
    await message.answer(
        "🔍 <b>MANBANI TEKSHIRIB KO'RISH:</b>\n\n"
        "Tekshirmoqchi bo'lgan Telegram kanal @username yoki sayt ID sini yuboring (masalan: <code>@kunuzofficial</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_test_source))
async def process_test_source(message: Message, state: FSMContext) -> None:
    """Manbani testlash natijasini ko'rsatish."""
    ident = message.text.strip()
    await state.clear()
    status_msg = await message.answer(f"⏳ <b>'{ident}' tekshirilmoqda...</b>", parse_mode="HTML")
    res = await source_manager.test_single_source(ident)
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)

    if not res.get("success"):
        await status_msg.edit_text(
            f"❌ Xatolik yuz berdi: {res.get('error')}",
            parse_mode="HTML"
        )
        await message.answer("Boshqaruv menyusi:", reply_markup=get_sources_reply_keyboard(tg_count, web_count))
        return

    text = (
        f"✅ <b>Tekshiruv natijasi:</b> {res.get('source_name')}\n"
        f"• Turi: <b>{res.get('source_type')}</b>\n"
        f"• Olingan so'nggi postlar: <b>{res.get('total_fetched')} ta</b>\n"
        f"• Metroga oid yangiliklar: <b>{res.get('metro_found')} ta</b>\n\n"
    )
    samples = res.get("sample_items", [])
    if samples:
        text += "<b>Oxirgi postlardan namunalar:</b>\n"
        for s in samples[:3]:
            text += f"• <i>{html.escape(s.title[:80])}</i>\n"

    await status_msg.edit_text(text, parse_mode="HTML")
    await message.answer("Boshqaruv menyusi:", reply_markup=get_sources_reply_keyboard(tg_count, web_count))


@router.message(StateFilter("*"), Command("settings"))
@router.message(StateFilter("*"), F.text == "⚙️ Sozlamalar")
async def cmd_settings_menu(message: Message, state: FSMContext) -> None:
    """Sozlamalar bo'limi Reply klaviaturasini ochish."""
    await state.clear()
    await message.answer(
        build_settings_text(),
        parse_mode="HTML",
        reply_markup=get_settings_reply_keyboard(source_manager.is_paused)
    )


@router.message(StateFilter("*"), F.text.in_(["▶️ Kuzatuvni yoqish", "⏸️ Kuzatuvni to'xtatish", "▶️ Monitoringni yoqish", "⏸️ Monitoringni to'xtatish"]))
async def cmd_toggle_monitoring(message: Message, state: FSMContext) -> None:
    """Monitoringni to'xtatish yoki qayta yoqish."""
    await state.clear()
    is_paused = source_manager.toggle_pause()
    state_word = "vaqtincha to'xtatildi (Pause)" if is_paused else "qayta ishga tushirildi (24/7 Faol)"
    await message.answer(
        f"⚡ <b>Monitoring {state_word}!</b>",
        parse_mode="HTML",
        reply_markup=get_settings_reply_keyboard(is_paused)
    )


@router.message(StateFilter("*"), Command("ping", "diag"))
@router.message(StateFilter("*"), F.text == "🩺 Diagnostika")
async def cmd_diagnostics(message: Message, state: FSMContext) -> None:
    """Tizim diagnostikasi va Telegram API ping kechikishini o'lchash."""
    await state.clear()
    t_start = time.time()
    ping_msg = await message.answer("📡 Server va Telegram API bilan aloqa tekshirilmoqda...")
    latency_ms = (time.time() - t_start) * 1000

    now_uz = format_uz_time(fmt="%H:%M:%S | %d.%m.%Y (UTC+5)")
    admin_count = len(settings.admin_id_list)
    group_count = len(settings.group_id_list)
    total_sources = len(source_manager.telegram_channels) + len(source_manager.web_sources)

    text = (
        "🩺 <b>TIZIM DIAGNOSTIKASI VA PING:</b>\n\n"
        f"⚡ <b>Telegram API kechikishi:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"🕒 <b>O'zbekiston joriy vaqti:</b> <code>{now_uz}</code>\n"
        f"🟢 <b>Monitoring holati:</b> {'⏸️ Toxtatilgan' if source_manager.is_paused else '24/7 Faol'}\n"
        f"🌐 <b>Kuzatilayotgan manbalar:</b> {total_sources} ta\n"
        f"👥 <b>Ulangan adminlar:</b> {admin_count} ta\n"
        f"📢 <b>Ulangan guruhlar:</b> {group_count} ta\n"
        f"🗂️ <b>Xotiradagi kesh:</b> {storage.count} ta xabar\n"
        f"🧠 <b>Antidublikat xotirasi:</b> {len(deduplicator._history)} ta voqea\n\n"
        "<i>Barcha asinxron jarayonlar to'liq barqaror ishlamoqda.</i>"
    )
    await ping_msg.edit_text(text, parse_mode="HTML")


@router.message(StateFilter("*"), F.text.startswith("⏱️ Interval:") | F.text.in_(["⏱️ 30s", "⏱️ 60s", "⏱️ 120s"]))
async def cmd_set_interval(message: Message, state: FSMContext) -> None:
    """Tekshirish intervalini o'zgartirish."""
    await state.clear()
    raw = message.text.replace("⏱️ Interval:", "").replace("⏱️", "").replace("s", "").strip()
    try:
        new_int = int(raw)
        settings.CHECK_INTERVAL_SECONDS = new_int
        await message.answer(
            f"✅ <b>Avtomatik tekshiruv oralig'i har {new_int} soniyaga sozlandi!</b>",
            parse_mode="HTML",
            reply_markup=get_settings_reply_keyboard(source_manager.is_paused)
        )
    except ValueError:
        await message.answer("⚠️ Noto'g'ri interval qiymati.", reply_markup=get_settings_reply_keyboard(source_manager.is_paused))


@router.message(StateFilter("*"), Command("keywords"))
@router.message(StateFilter("*"), F.text == "🏷️ Kalit so'zlar")
async def cmd_keywords_menu(message: Message, state: FSMContext) -> None:
    """Kalit so'zlar menyusi."""
    await state.clear()
    await message.answer(
        build_keywords_text(),
        parse_mode="HTML",
        reply_markup=get_keywords_reply_keyboard()
    )


@router.message(StateFilter("*"), F.text.in_(["➕ So'z qo'shish", "➕ Yangi kalit so'z qo'shish"]))
async def cmd_add_keyword_start(message: Message, state: FSMContext) -> None:
    """Yangi kalit so'z kiritish so'rovi."""
    await state.set_state(AdminStates.waiting_for_new_keyword)
    await message.answer(
        "➕ <b>YANGI KALIT SO'Z QO'SHISH:</b>\n\n"
        "Metroga oid yangi so'z yoki bekat nomini kiriting (masalan: <code>Yangi Toshkent bekati</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_new_keyword))
async def process_add_keyword(message: Message, state: FSMContext) -> None:
    """Kalit so'zni saqlash."""
    kw = message.text.strip()
    await state.clear()
    success = add_custom_keyword(kw)
    if success:
        await message.answer(
            f"✅ <b>'{kw}'</b> kalit so'zi muvaffaqiyatli qo'shildi va filtrga kiritildi!",
            parse_mode="HTML",
            reply_markup=get_keywords_reply_keyboard()
        )
    else:
        await message.answer(
            "⚠️ Kalit so'z juda qisqa yoki xatolik yuz berdi.",
            reply_markup=get_keywords_reply_keyboard()
        )


@router.message(StateFilter("*"), F.text.in_(["🔍 Matnni tekshirish", "🔍 Matn tekshirish"]))
async def cmd_test_text_start(message: Message, state: FSMContext) -> None:
    """Matnni filtrdan tekshirish so'rovi."""
    await state.set_state(AdminStates.waiting_for_test_text)
    await message.answer(
        "🔍 <b>MATNNI FILTRDAN TEKSHIRISH:</b>\n\n"
        "Ixtiyoriy xabar matnini yuboring. Tizim uning metroga aloqadorligi va dublikat tahlilini ko'rsatib beradi:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(StateFilter(AdminStates.waiting_for_test_text))
async def process_test_text(message: Message, state: FSMContext) -> None:
    """Yuborilgan matnni filtr va dublikat tahlilidan o'tkazish."""
    text = message.text.strip()
    await state.clear()

    analysis = explain_filter(text, text)
    is_metro = analysis.get("is_metro", False)
    tags = analysis.get("tags", [])
    reason = analysis.get("reason", "")
    matched = analysis.get("matched", [])

    is_dup, dup_source, sim = deduplicator.is_duplicate(text, text, "Manual")

    verdict_icon = "🟢 QABUL QILINADI (METROGA OID)" if is_metro else "🔴 RAD ETILADI (METROGA ALOQADOR EMAS)"
    tags_str = " ".join(tags) if tags else "Mavjud emas"
    matched_str = ", ".join(matched) if matched else "Mos keluvchi belgilar yo'q"
    dup_str = f"⚠️ Ha! (Asl manba: {dup_source}, o'xshashlik: {sim*100:.1f}%)" if is_dup else f"✅ Yo'q (Maksimal o'xshashlik: {sim*100:.1f}%)"

    result_text = (
        "🔍 <b>FILTR TAHLILI NATIJASI:</b>\n\n"
        f"<b>Qaror:</b> {verdict_icon}\n"
        f"🏷️ <b>Berilgan teglar:</b> <code>{tags_str}</code>\n"
        f"🔍 <b>Tahlil sababi:</b> {reason}\n"
        f"📌 <b>Aniqlangan belgilar:</b> <code>{matched_str}</code>\n\n"
        f"🧠 <b>Kross-dublikat tekshiruvi:</b>\n{dup_str}"
    )
    await message.answer(result_text, parse_mode="HTML", reply_markup=get_keywords_reply_keyboard())


@router.message(StateFilter("*"), Command("cache"))
@router.message(StateFilter("*"), F.text.in_(["🧹 Kesh", "🧹 Keshni tozalash"]))
async def cmd_cache_menu(message: Message, state: FSMContext) -> None:
    """Kesh bo'limi Reply klaviaturasini ochish."""
    await state.clear()
    await message.answer(
        build_cache_text(),
        parse_mode="HTML",
        reply_markup=get_cache_reply_keyboard()
    )


@router.message(StateFilter("*"), F.text.in_(["🗑️ Postlar keshi", "🗑️ Ko'rilgan postlar keshini tozalash"]))
async def cmd_clear_seen_cache(message: Message, state: FSMContext) -> None:
    """Seen posts keshini tozalash."""
    await state.clear()
    c = storage.clear()
    await message.answer(
        f"✅ <b>Ko'rilgan xabarlar keshi tozalandi ({c} ta element o'chirildi)!</b>",
        parse_mode="HTML",
        reply_markup=get_cache_reply_keyboard()
    )


@router.message(StateFilter("*"), F.text.in_(["🧠 Dublikat izlari", "🧠 Antidublikat xotirasini tozalash"]))
async def cmd_clear_dedup_cache(message: Message, state: FSMContext) -> None:
    """Antidublikat izlarini tozalash."""
    await state.clear()
    c = deduplicator.clear_history()
    await message.answer(
        f"✅ <b>Antidublikat xotirasi tozalandi ({c} ta voqea o'chirildi)!</b>",
        parse_mode="HTML",
        reply_markup=get_cache_reply_keyboard()
    )


@router.message(StateFilter("*"), F.text.in_(["🧹 Barcha kesh", "🧹 BARCHA keshni tozalash"]))
async def cmd_clear_all_cache(message: Message, state: FSMContext) -> None:
    """Barcha keshni tozalash."""
    await state.clear()
    c1 = storage.clear()
    c2 = deduplicator.clear_history()
    await message.answer(
        f"✅ <b>Barcha kesh to'liq tozalandi!</b>\n({c1} ta xabar ID, {c2} ta dublikat izi o'chirildi)",
        parse_mode="HTML",
        reply_markup=get_cache_reply_keyboard()
    )


@router.message(StateFilter("*"), Command("logs"))
@router.message(StateFilter("*"), F.text.in_(["📋 Loglar", "📋 Tizim loglari"]))
@router.message(StateFilter("*"), F.text.in_(["🔄 Yangilash", "🔄 Loglarni yangilash"]))
async def cmd_system_logs(message: Message, state: FSMContext) -> None:
    """Tizim loglarini ko'rsatish va yangilash."""
    await state.clear()
    logs_text = html.escape(get_recent_logs(lines=25))
    text = (
        "📋 <b>TIZIMNING SO'NGGI LOGLARI (OXIRGI 25 TA):</b>\n\n"
        f"<pre><code>{logs_text}</code></pre>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_logs_reply_keyboard())


@router.message(Command("id", "group_id", "getid"))
async def cmd_get_id(message: Message) -> None:
    """Joriy chat yoki guruh identifikatorini aniqlash."""
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
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


# =========================================================================
# OLDIN YUBORILGAN INLINE TUGMALAR UCHUN XAVFSIZ CALLBACK HANDLER
# =========================================================================

@router.callback_query()
async def safe_fallback_callback(call: CallbackQuery) -> None:
    """Oldingi inline tugmalar bosilganda xato bermasdan xabar berish."""
    await call.answer("Iltimos, pastdagi asosiy klaviatura menyusidan foydalaning.")
