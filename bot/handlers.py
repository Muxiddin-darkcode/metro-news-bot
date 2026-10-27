"""
Metro Monitoring Bot - Kengaytirilgan Admin Boshqaruv Paneli va Handlerlar.
aiogram 3.x asosida to'liq asinxron ishlaydi.
"""

import html
import time
import datetime
from typing import Optional, List, Dict

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
from bot.notifier import send_metro_alert
from bot.states import AdminStates
from bot.keyboards import (
    get_main_keyboard,
    admin_main_dashboard_kb,
    sources_menu_kb,
    tg_sources_page_kb,
    web_sources_page_kb,
    monitoring_menu_kb,
    filter_menu_kb,
    custom_keywords_kb,
    cache_menu_kb,
    cancel_kb,
    back_to_main_kb
)

router = Router()

# =========================================================================
# YORDAMCHI VA XAVFSIZ TAHRIRLASH FUNKSIYALARI
# =========================================================================

async def safe_edit_message(
    call: CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    disable_web_page_preview: bool = True
) -> None:
    """
    Inline xabarni xavfsiz tahrirlash yordamchisi.
    Agar Telegram 'message is not modified' xatosi qaytarsa, dastur to'xtab qolmaydi.
    """
    try:
        if call.message:
            await call.message.edit_text(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            # Ma'lumot allaqachon eng oxirgi holatda
            pass
        else:
            logger.warning(f"Xabarni tahrirlashda TelegramBadRequest: {exc}")
    except Exception as exc:
        logger.debug(f"Xabarni tahrirlashda istisno: {exc}")
        try:
            if call.message:
                await call.message.answer(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview
                )
        except Exception:
            pass


def build_dashboard_text() -> str:
    """Admin Dashboard asosiy ekrani uchun ixcham va mobilga mos matn."""
    status_icon = "⏸️ To'xtatilgan" if source_manager.is_paused else "🟢 Faol"
    last_time = "Hali yo'q"
    if source_manager.last_check_time > 0:
        last_time = format_uz_time(source_manager.last_check_time, "%H:%M:%S")

    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_sources = tg_count + web_count

    return (
        "🎛️ <b>ADMIN BOSHQARUV PANELI</b>\n\n"
        f"• <b>Holat:</b> {status_icon}\n"
        f"• <b>Tekshiruv:</b> har {settings.CHECK_INTERVAL_SECONDS}s | <b>Dublikat:</b> {settings.SIMILARITY_THRESHOLD * 100:.0f}%\n"
        f"• <b>Manbalar:</b> {total_sources} ta (📱 {tg_count} kanal, 💻 {web_count} sayt)\n"
        f"• <b>Oxirgi skan:</b> {last_time} ({source_manager.last_check_duration:.1f}s)\n"
        f"• <b>Kesh:</b> {storage.count} ta | <b>Izlar:</b> {len(deduplicator._history)} ta\n\n"
        "<i>Kerakli amalni tanlang:</i>"
    )



def build_status_text() -> str:
    """Tizim holati va umumiy statistikasini ko'rsatish."""
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
        f"  └ 💻 Yangilik saytlari: {web_count} ta\n\n"
        f"⏱️ <b>Avtomatik tekshirish oralig'i:</b> har {settings.CHECK_INTERVAL_SECONDS} soniyada\n"
        f"⚡ <b>Oxirgi tekshiruv vaqti:</b> {last_time}\n"
        f"⏳ <b>Oxirgi skaner davomiyligi:</b> {source_manager.last_check_duration:.2f} soniya\n"
        f"🧠 <b>Antidublikat chegarasi:</b> {settings.SIMILARITY_THRESHOLD * 100:.0f}%\n"
        f"🗂️ <b>Keshdagi ko'rilgan postlar:</b> {storage.count} ta\n"
        f"🧠 <b>Antidublikat xotirasi (oxirgi 24 soat):</b> {len(deduplicator._history)} ta voqea\n"
        f"👥 <b>Ruxsat etilgan adminlar:</b> {len(settings.admin_id_list)} ta"
        f"{group_info}"
    )


def build_recent_news_text() -> str:
    """Tizim tomonidan topilgan eng so'nggi metro xabarlari ro'yxati."""
    events = deduplicator.get_recent_events(limit=8)
    if not events:
        return (
            "📰 <b>SO'NGGI METRO XABARLARI</b>\n\n"
            "<i>Hozircha tizim xotirasida topilgan yangi metro voqealari yo'q.</i>"
        )

    lines = ["📰 <b>SO'NGGI ANIQLANGAN METRO XABARLARI (OXIRGI 24 SOAT):</b>\n"]
    for i, ev in enumerate(events, 1):
        t_str = format_uz_time(ev.get("timestamp", 0), "%H:%M | %d.%m")
        title = html.escape(ev.get("title", "Sarlavhasiz"))
        source = html.escape(ev.get("source", "Noma'lum"))
        url = ev.get("url", "")
        url_link = f' <a href="{url}">[Havolani ochish]</a>' if url else ""
        lines.append(f"<b>{i}.</b> [{t_str}] <b>{source}</b>:\n{title}{url_link}\n")

    return "\n".join(lines)


# =========================================================================
# ASOSIY ADMIN BUYRUQLARI (COMMANDS VA REPLY TUGMALAR)
# =========================================================================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Botni boshlash va xush kelibsiz xabari."""
    await state.clear()
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_count = tg_count + web_count

    await message.answer(
        "👋 <b>Assalomu alaykum, Hurmatli Administrator!</b>\n\n"
        "🚇 <b>Toshkent Metropoliteni Tezkor Monitoring Tizimi</b> faol holatda ishlamoqda.\n\n"
        f"Tizim 24/7 rejimida <b>{total_count} ta manba</b>ni ({tg_count} ta TG kanal va {web_count} ta sayt) "
        "asinxron parallel kuzatib boradi.\n\n"
        "Boshqaruv uchun pastdagi tezkor klaviatura yoki inline paneldan foydalanishingiz mumkin:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    # Inline Dashboardni ham ko'rsatish
    await message.answer(
        build_dashboard_text(),
        reply_markup=admin_main_dashboard_kb(source_manager.is_paused),
        parse_mode="HTML"
    )


@router.message(Command("panel", "admin", "dashboard"))
@router.message(F.text.contains("Boshqaruv paneli") | F.text.contains("BOSHQARUV PANELI"))
async def cmd_panel(message: Message, state: FSMContext) -> None:
    """Interaktiv Admin Dashboardni chiqarish."""
    await state.clear()
    await message.answer(
        build_dashboard_text(),
        reply_markup=admin_main_dashboard_kb(source_manager.is_paused),
        parse_mode="HTML"
    )


@router.message(Command("status"))
@router.message(F.text.contains("Tizim holati") | F.text.contains("TIZIM HOLATI"))
async def cmd_status(message: Message) -> None:
    """Tizim holatini ko'rsatish."""
    await message.answer(
        build_status_text(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("history", "news"))
@router.message(F.text.contains("So'nggi xabarlar") | F.text.contains("SO'NGGI XABARLAR"))
async def cmd_recent_news(message: Message) -> None:
    """Oxirgi metro xabarlarini ko'rsatish."""
    await message.answer(
        build_recent_news_text(),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )


@router.message(Command("logs"))
@router.message(F.text.contains("So'nggi loglar") | F.text.contains("SO'NGGI LOGLAR"))
async def cmd_logs(message: Message) -> None:
    """Tizim loglarini ko'rsatish."""
    logs_text = html.escape(get_recent_logs(lines=25))
    text = (
        "📋 <b>TIZIMNING SO'NGGI LOGLARI (OXIRGI 25 TA):</b>\n\n"
        f"<pre><code>{logs_text}</code></pre>"
    )
    refresh_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Loglarni yangilash", callback_data="admin:logs")],
            [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")]
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=refresh_kb)


@router.message(Command("settings"))
@router.message(F.text.contains("Sozlamalar") | F.text.contains("SOZLAMALAR"))
async def cmd_settings(message: Message) -> None:
    """Sozlamalar menyusini ochish."""
    kb = monitoring_menu_kb(
        source_manager.is_paused,
        settings.CHECK_INTERVAL_SECONDS,
        settings.SIMILARITY_THRESHOLD
    )
    text = (
        "⚙️ <b>TIZIM VA MONITORING PARAMETRLARI:</b>\n\n"
        f"• <b>Holat:</b> {'⏸️ Vaqtincha toxtatilgan' if source_manager.is_paused else '🟢 Faol'}\n"
        f"• <b>Tekshirish intervali:</b> har {settings.CHECK_INTERVAL_SECONDS} soniyada\n"
        f"• <b>Antidublikat chegarasi:</b> {settings.SIMILARITY_THRESHOLD * 100:.0f}%\n"
        f"• <b>Parallel so'rovlar limiti:</b> {settings.MAX_CONCURRENT_REQUESTS} ta\n\n"
        "<i>Kerakli parametr ustiga bosib uni o'zgartirishingiz mumkin:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


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
        parse_mode="HTML"
    )


@router.message(Command("sources"))
async def cmd_sources(message: Message) -> None:
    """Manbalarni boshqarish bo'limi."""
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    await message.answer(
        f"🌐 <b>KUZATILAYOTGAN MANBALAR BOSHQARUVI:</b>\n\n"
        f"• 📱 Telegram kanallar: <b>{tg_count} ta</b>\n"
        f"• 💻 Veb-saytlar va RSS: <b>{web_count} ta</b>\n"
        f"• Jami: <b>{tg_count + web_count} ta</b>\n\n"
        "Quyidagi tugmalar orqali ro'yxatni ko'rish, yangi manba qo'shish yoki o'chirish mumkin:",
        reply_markup=sources_menu_kb(tg_count, web_count),
        parse_mode="HTML"
    )


@router.message(Command("keywords"))
async def cmd_keywords(message: Message) -> None:
    """Filtr kalit so'zlari bo'limi."""
    custom_kws = get_custom_keywords()
    custom_str = ", ".join(custom_kws) if custom_kws else "Hozircha yo'q"
    text = (
        "🏷️ <b>METRO FILTR KALIT SO'ZLARI:</b>\n\n"
        "🚇 <b>Asosiy so'zlar:</b> metro, metrosi, metropoliten, тошметро, tashmetro\n\n"
        "🚉 <b>Bekatlar:</b> Paxtakor bekati, Chilonzor bekati, Amir Temur bekati, "
        "Yunusobod bekati, Alisher Navoiy bekati, Turkiston bekati, va barcha bekatlar.\n\n"
        "⚠️ <b>Hodisalar:</b> to'xtab qoldi, nosozlik, kechikish, vagon, poyezd, rels, mashinist, "
        "tutun, tirbandlik, interval, chipta, turniket, tarif.\n\n"
        f"✨ <b>Admin qo'shgan maxsus kalit so'zlar ({len(custom_kws)} ta):</b>\n"
        f"<code>{custom_str}</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=filter_menu_kb())


@router.message(Command("ping", "diag"))
async def cmd_ping(message: Message) -> None:
    """Tizim diagnostikasi va Telegram ping kechikishini o'lchash."""
    t_start = time.time()
    ping_msg = await message.answer("📡 Server va Telegram API bilan aloqa tekshirilmoqda...")
    latency_ms = (time.time() - t_start) * 1000

    now_uz = format_uz_time(fmt="%H:%M:%S | %d.%m.%Y (UTC+5)")
    admin_count = len(settings.admin_id_list)
    group_count = len(settings.group_id_list)
    
    text = (
        "🩺 <b>TIZIM DIAGNOSTIKASI VA PING:</b>\n\n"
        f"⚡ <b>Telegram API javob vaqti:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"🕒 <b>O'zbekiston joriy vaqti:</b> <code>{now_uz}</code>\n"
        f"🟢 <b>Monitoring holati:</b> {'⏸️ Toxtatilgan' if source_manager.is_paused else '24/7 Faol'}\n"
        f"👥 <b>Ulangan adminlar:</b> {admin_count} ta\n"
        f"📢 <b>Ulangan guruhlar:</b> {group_count} ta\n"
        f"🗂️ <b>Xotiradagi kesh:</b> {storage.count} ta xabar ID si\n"
        f"🧠 <b>Antidublikat xotirasi:</b> {len(deduplicator._history)} ta voqea\n\n"
        "<i>Barcha tizim jarayonlari to'liq barqaror ishlamoqda.</i>"
    )
    await ping_msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.message(Command("test_alert"))
async def cmd_test_alert(message: Message) -> None:
    """Test metro ogohlantirishini hozirgi chatga yuborish."""
    test_item = NewsItem(
        raw_id="admin_test_post_001",
        url="https://tashmetro.uz",
        title="Toshkent metrosida oraliq intervallar qisqartirildi (TEST OGOHLANTIRISH)",
        content="Metropoliten harakat xavfsizligi va qulaylikni oshirish maqsadida qo'shimcha poyezdlar harakatini yo'lga qo'ydi. Ushbu xabar admin boshqaruv paneli orqali tizimni sinovdan o'tkazish uchun yuborildi.",
        source_name="Metro Monitoring Test Markazi",
        published_at=datetime.datetime.now().isoformat(),
        tags=["#metro", "#chilonzor", "#poyezd", "#test"]
    )
    await send_metro_alert(message.bot, test_item, chat_ids=[message.chat.id])
    await message.answer("✅ <b>Test ogohlantirish xabari muvaffaqiyatli yuborildi!</b>", parse_mode="HTML")


@router.message(Command("check"))
@router.message(F.text.contains("Hozir tekshirish") | F.text.contains("HOZIR TEKSHIRISH"))
async def cmd_check(message: Message) -> None:
    """Barcha 80+ manbani parallel tekshirish va yangi yangiliklarni jo'natish."""
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


# =========================================================================
# ASOSIY DASHBOARD CALLBACK QUERY LAR
# =========================================================================

@router.callback_query(F.data == "noop")
async def callback_noop(call: CallbackQuery) -> None:
    """Bo'sh tugma bosilganda bildirishnoma ko'rsatmaslik."""
    await call.answer()


@router.callback_query(F.data == "admin:cancel")
async def callback_cancel(call: CallbackQuery, state: FSMContext) -> None:
    """Joriy FSM holatini bekor qilib asosiy menyuga qaytish."""
    await state.clear()
    await call.answer("Amal bekor qilindi.")
    await safe_edit_message(
        call,
        build_dashboard_text(),
        reply_markup=admin_main_dashboard_kb(source_manager.is_paused)
    )


@router.callback_query(F.data == "admin:main")
async def callback_main(call: CallbackQuery, state: FSMContext) -> None:
    """Asosiy dashboardga qaytish."""
    await state.clear()
    await call.answer()
    await safe_edit_message(
        call,
        build_dashboard_text(),
        reply_markup=admin_main_dashboard_kb(source_manager.is_paused)
    )


@router.callback_query(F.data == "admin:logs")
async def callback_logs(call: CallbackQuery) -> None:
    """Loglarni ko'rish va yangilash."""
    await call.answer()
    logs_text = html.escape(get_recent_logs(lines=25))
    text = (
        "📋 <b>TIZIMNING SO'NGGI LOGLARI (OXIRGI 25 TA):</b>\n\n"
        f"<pre><code>{logs_text}</code></pre>"
    )
    refresh_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Loglarni yangilash", callback_data="admin:logs")],
            [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")]
        ]
    )
    await safe_edit_message(call, text, reply_markup=refresh_kb)


@router.callback_query(F.data == "admin:diag")
async def callback_diag(call: CallbackQuery) -> None:
    """Diagnostika hisoboti."""
    t_start = time.time()
    await call.answer()
    latency_ms = (time.time() - t_start) * 1000
    now_uz = format_uz_time(fmt="%H:%M:%S | %d.%m.%Y (UTC+5)")
    admin_count = len(settings.admin_id_list)
    group_count = len(settings.group_id_list)

    text = (
        "🩺 <b>TIZIM DIAGNOSTIKASI VA PING:</b>\n\n"
        f"⚡ <b>Telegram API kechikishi:</b> <code>{latency_ms:.1f} ms</code>\n"
        f"🕒 <b>O'zbekiston vaqti:</b> <code>{now_uz}</code>\n"
        f"🟢 <b>Monitoring holati:</b> {'⏸️ Toxtatilgan' if source_manager.is_paused else '24/7 Faol'}\n"
        f"👥 <b>Ulangan adminlar:</b> {admin_count} ta\n"
        f"📢 <b>Ulangan guruhlar:</b> {group_count} ta\n"
        f"🗂️ <b>Keshdagi xabarlar:</b> {storage.count} ta\n"
        f"🧠 <b>Antidublikat xotirasi:</b> {len(deduplicator._history)} ta voqea\n\n"
        "<i>Tizim uzluksiz 24/7 rejimida xatosiz ishlamoqda.</i>"
    )
    await safe_edit_message(call, text, reply_markup=back_to_main_kb())


@router.callback_query(F.data == "admin:news")
async def callback_news(call: CallbackQuery) -> None:
    """So'nggi yangiliklar ro'yxati."""
    await call.answer()
    await safe_edit_message(
        call,
        build_recent_news_text(),
        reply_markup=back_to_main_kb(),
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "btn_status")
async def callback_status(call: CallbackQuery) -> None:
    """Holat tugmasi bosilganda."""
    await call.answer()
    await call.message.answer(build_status_text(), parse_mode="HTML", reply_markup=get_main_keyboard())


@router.callback_query(F.data == "btn_check_now")
async def callback_check_now(call: CallbackQuery) -> None:
    """Hozir tekshirish tugmasi bosilganda."""
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
            "✅ <b>Tekshiruv yakunlandi!</b>\n\n"
            f"⏱️ Sarflangan vaqt: <b>{stats['elapsed_seconds']} soniya</b>\n"
            f"🌐 Tekshirilgan manbalar: <b>{stats['total_sources']} ta</b>\n"
            f"📥 Yig'ilgan so'nggi postlar: <b>{stats['raw_posts_fetched']} ta</b>\n"
            f"🚨 Topilgan yangi metro xabarlari: <b>{stats['metro_alerts_found']} ta</b>"
        )
        await status_msg.edit_text(result_text, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {e}")


# =========================================================================
# MONITORING SOZLAMALARI VA NAZORATI
# =========================================================================

@router.callback_query(F.data.in_(["admin:monitor", "admin:settings"]))
async def callback_monitor_menu(call: CallbackQuery) -> None:
    """Monitoring boshqaruvi va sozlamalari menyusi."""
    await call.answer()
    kb = monitoring_menu_kb(
        source_manager.is_paused,
        settings.CHECK_INTERVAL_SECONDS,
        settings.SIMILARITY_THRESHOLD
    )
    text = (
        "⚡ <b>MONITORING VA PARAMETRLAR NAZORATI:</b>\n\n"
        f"• <b>Monitoring holati:</b> {'⏸️ Vaqtincha toxtatilgan' if source_manager.is_paused else '🟢 24/7 Faol'}\n"
        f"• <b>Tekshirish intervali:</b> har <b>{settings.CHECK_INTERVAL_SECONDS} soniyada</b>\n"
        f"• <b>Dublikat chegarasi:</b> <b>{settings.SIMILARITY_THRESHOLD * 100:.0f}%</b>\n\n"
        "💡 <i>Quyidagi tugmalar orqali interval yoki sezgirlikni bitta bosish bilan o'zgartirishingiz mumkin:</i>"
    )
    await safe_edit_message(call, text, reply_markup=kb)


@router.callback_query(F.data == "admin:mon:toggle")
async def callback_monitor_toggle(call: CallbackQuery) -> None:
    """Monitoringni to'xtatish yoki qayta yoqish."""
    is_paused = source_manager.toggle_pause()
    state_word = "to'xtatildi (Pause)" if is_paused else "ishga tushirildi (Faol)"
    await call.answer(f"Monitoring {state_word}!", show_alert=True)
    await callback_monitor_menu(call)


@router.callback_query(F.data.startswith("admin:mon:int:"))
async def callback_monitor_set_interval(call: CallbackQuery) -> None:
    """Tekshirish intervalini o'zgartirish."""
    new_int = int(call.data.split(":")[-1])
    settings.CHECK_INTERVAL_SECONDS = new_int
    await call.answer(f"Interval har {new_int} soniyaga o'zgartirildi!", show_alert=True)
    await callback_monitor_menu(call)


@router.callback_query(F.data.startswith("admin:mon:th:"))
async def callback_monitor_set_threshold(call: CallbackQuery) -> None:
    """Antidublikat o'xshashlik chegarasini sozlash."""
    new_th = float(call.data.split(":")[-1])
    settings.SIMILARITY_THRESHOLD = new_th
    deduplicator.set_threshold(new_th)
    await call.answer(f"Dublikat chegarasi {new_th * 100:.0f}% ga sozlandi!", show_alert=True)
    await callback_monitor_menu(call)


# =========================================================================
# MANBALARNI BOSHQARISH (TELEGRAM KANALLAR VA VEB-SAYTLAR)
# =========================================================================

@router.callback_query(F.data == "admin:sources")
async def callback_sources_menu(call: CallbackQuery) -> None:
    """Manbalar boshqaruv menyusi."""
    await call.answer()
    tg_count = len(source_manager.telegram_channels)
    web_count = len(source_manager.web_sources)
    total_count = tg_count + web_count
    text = (
        "🌐 <b>MANBALARNI BOSHQARISH BO'LIMI:</b>\n\n"
        f"Hozirda jami <b>{total_count} ta</b> manba asinxron kuzatilmoqda:\n"
        f"• 📱 Telegram kanallar: <b>{tg_count} ta</b>\n"
        f"• 💻 Yangilik veb-saytlari: <b>{web_count} ta</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await safe_edit_message(call, text, reply_markup=sources_menu_kb(tg_count, web_count))


@router.callback_query(F.data.startswith("admin:src:tg:"))
async def callback_sources_tg_list(call: CallbackQuery) -> None:
    """Telegram kanallari sahifalangan ro'yxati."""
    await call.answer()
    page = int(call.data.split(":")[-1])
    channels = source_manager.telegram_channels
    text = (
        f"📱 <b>TELEGRAM KANALLAR RO'YXATI ({len(channels)} ta):</b>\n\n"
        "<i>Kanal tafsilotlarini ko'rish yoki uni o'chirish (🗑️) uchun tegishli tugmani bosing:</i>"
    )
    kb = tg_sources_page_kb(channels, page=page, per_page=6)
    await safe_edit_message(call, text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:src:web:"))
async def callback_sources_web_list(call: CallbackQuery) -> None:
    """Veb-saytlar sahifalangan ro'yxati."""
    await call.answer()
    page = int(call.data.split(":")[-1])
    websites = source_manager.web_sources
    text = (
        f"💻 <b>VEB-SAYTLAR RO'YXATI ({len(websites)} ta):</b>\n\n"
        "<i>Sayt tafsilotlarini ko'rish yoki o'chirish (🗑️) uchun tegishli tugmani bosing:</i>"
    )
    kb = web_sources_page_kb(websites, page=page, per_page=6)
    await safe_edit_message(call, text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:src:view_tg:"))
async def callback_sources_view_tg(call: CallbackQuery) -> None:
    """Bitta Telegram kanalning to'liq ma'lumotlarini ko'rish."""
    await call.answer()
    user = call.data.split(":")[-1]
    ch = next((c for c in source_manager.telegram_channels if c.get("username", "").lower() == user.lower()), None)
    if not ch:
        await call.answer("Kanal topilmadi!", show_alert=True)
        return

    text = (
        f"📱 <b>TELEGRAM KANAL MA'LUMOTI:</b>\n\n"
        f"🏷️ <b>Nomi:</b> {ch.get('name', user)}\n"
        f"🔗 <b>Username:</b> @{ch.get('username')}\n"
        f"🌐 <b>Tili:</b> {ch.get('lang', 'uz')}\n"
        f"⚡ <b>Ustuvorlik:</b> {ch.get('priority', 'normal')}\n"
        f"🔗 <b>Havola:</b> https://t.me/{ch.get('username')}\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧪 Darhol tekshirib ko'rish", callback_data=f"admin:src:test_tg:{user}"),
                InlineKeyboardButton(text="🗑️ Kanalni o'chirish", callback_data=f"admin:src:del_tg:{user}")
            ],
            [InlineKeyboardButton(text="◀️ Kanallar ro'yxatiga qaytish", callback_data="admin:src:tg:0")]
        ]
    )
    await safe_edit_message(call, text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:src:view_web:"))
async def callback_sources_view_web(call: CallbackQuery) -> None:
    """Bitta veb-saytning to'liq ma'lumotlarini ko'rish."""
    await call.answer()
    sid = call.data.split(":")[-1]
    site = next((w for w in source_manager.web_sources if w.get("id", "").lower() == sid.lower() or w.get("name", "").lower() == sid.lower()), None)
    if not site:
        await call.answer("Veb-sayt topilmadi!", show_alert=True)
        return

    text = (
        f"💻 <b>VEB-SAYT MA'LUMOTI:</b>\n\n"
        f"🏷️ <b>Nomi:</b> {site.get('name')}\n"
        f"🆔 <b>ID:</b> <code>{site.get('id')}</code>\n"
        f"🌐 <b>Sayt URL:</b> {site.get('url')}\n"
        f"📡 <b>Feed/RSS URL:</b> <code>{site.get('feed_url')}</code>\n"
        f"📁 <b>Turi:</b> {site.get('type', 'rss').upper()}\n"
        f"🌐 <b>Tili:</b> {site.get('lang', 'uz')}\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧪 Darhol tekshirib ko'rish", callback_data=f"admin:src:test_web:{sid}"),
                InlineKeyboardButton(text="🗑️ Saytni o'chirish", callback_data=f"admin:src:del_web:{sid}")
            ],
            [InlineKeyboardButton(text="◀️ Saytlar ro'yxatiga qaytish", callback_data="admin:src:web:0")]
        ]
    )
    await safe_edit_message(call, text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:src:del_tg:"))
async def callback_sources_del_tg(call: CallbackQuery) -> None:
    """Telegram kanalni o'chirish."""
    user = call.data.split(":")[-1]
    success, msg = source_manager.remove_telegram_channel(user)
    await call.answer(msg, show_alert=True)
    await callback_sources_tg_list(call)


@router.callback_query(F.data.startswith("admin:src:del_web:"))
async def callback_sources_del_web(call: CallbackQuery) -> None:
    """Veb-saytni o'chirish."""
    sid = call.data.split(":")[-1]
    success, msg = source_manager.remove_web_source(sid)
    await call.answer(msg, show_alert=True)
    await callback_sources_web_list(call)


@router.callback_query(F.data.startswith("admin:src:test_tg:"))
async def callback_sources_test_tg(call: CallbackQuery) -> None:
    """Telegram kanalni bir martalik skanerlab testlash."""
    user = call.data.split(":")[-1]
    await call.answer(f"@{user} skanerlanmoqda...", show_alert=False)
    load_msg = await call.message.answer(f"⏳ <b>@{user} kanali tekshirilmoqda...</b>", parse_mode="HTML")
    res = await source_manager.test_single_source(user)
    if not res.get("success"):
        await load_msg.edit_text(f"❌ Xatolik yuz berdi: {res.get('error')}", parse_mode="HTML")
        return

    text = (
        f"✅ <b>Kanal tekshiruvi natijasi:</b> @{user}\n\n"
        f"📥 Olingan so'nggi postlar: <b>{res.get('total_fetched')} ta</b>\n"
        f"🚨 Metroga oid xabarlar: <b>{res.get('metro_found')} ta</b>\n\n"
    )
    samples = res.get("sample_items", [])
    if samples:
        text += "<b>Oxirgi postlar namunalari:</b>\n"
        for s in samples[:3]:
            text += f"• <i>{html.escape(s.title[:80])}</i>\n"

    await load_msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(F.data.startswith("admin:src:test_web:"))
async def callback_sources_test_web(call: CallbackQuery) -> None:
    """Veb-saytni bir martalik testlash."""
    sid = call.data.split(":")[-1]
    await call.answer(f"'{sid}' tekshirilmoqda...", show_alert=False)
    load_msg = await call.message.answer(f"⏳ <b>'{sid}' sayti tekshirilmoqda...</b>", parse_mode="HTML")
    res = await source_manager.test_single_source(sid)
    if not res.get("success"):
        await load_msg.edit_text(f"❌ Xatolik yuz berdi: {res.get('error')}", parse_mode="HTML")
        return

    text = (
        f"✅ <b>Veb-sayt tekshiruvi natijasi:</b> {res.get('source_name')}\n\n"
        f"📥 Olingan so'nggi postlar: <b>{res.get('total_fetched')} ta</b>\n"
        f"🚨 Metroga oid xabarlar: <b>{res.get('metro_found')} ta</b>\n\n"
    )
    samples = res.get("sample_items", [])
    if samples:
        text += "<b>Oxirgi postlar namunalari:</b>\n"
        for s in samples[:3]:
            text += f"• <i>{html.escape(s.title[:80])}</i>\n"

    await load_msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(F.data == "admin:src:add_tg")
async def callback_sources_add_tg_start(call: CallbackQuery, state: FSMContext) -> None:
    """Telegram kanal qo'shish so'rovini boshlash."""
    await call.answer()
    await state.set_state(AdminStates.waiting_for_tg_username)
    await call.message.answer(
        "➕ <b>YANGI TELEGRAM KANAL QO'SHISH:</b>\n\n"
        "Kanalning <b>@username</b>ini yoki havolasini yuboring (masalan: <code>@tashkent_news</code>):\n\n"
        "<i>Bekor qilish uchun pastdagi tugmani bosing.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(StateFilter(AdminStates.waiting_for_tg_username))
async def process_add_tg_username(message: Message, state: FSMContext) -> None:
    """Telegram kanal username kiritilganda tekshirish va saqlash."""
    username = message.text.strip()
    status_msg = await message.answer(f"⏳ <b>@{username} tekshirilmoqda...</b>", parse_mode="HTML")
    
    test_res = await source_manager.test_single_source(username)
    if not test_res.get("success"):
        await status_msg.edit_text(
            f"❌ <b>Kanalni qo'shib bo'lmadi!</b>\n"
            f"Sabab: Kanal ochiq (public) emas yoki xatolik: {test_res.get('error')}",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    success, msg = source_manager.add_telegram_channel(
        username=username,
        name=test_res.get("source_name", username)
    )
    await state.clear()
    if success:
        await status_msg.edit_text(
            f"✅ <b>Muvaffaqiyatli!</b>\n\n"
            f"{msg}\n"
            f"Oxirgi olingan postlar soni: <b>{test_res.get('total_fetched')} ta</b>\n"
            f"Endi ushbu kanal 24/7 monitoring ro'yxatiga kiritildi.",
            parse_mode="HTML",
            reply_markup=back_to_main_kb()
        )
    else:
        await status_msg.edit_text(f"⚠️ {msg}", parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(F.data == "admin:src:add_web")
async def callback_sources_add_web_start(call: CallbackQuery, state: FSMContext) -> None:
    """Veb-sayt qo'shish so'rovini boshlash."""
    await call.answer()
    await state.set_state(AdminStates.waiting_for_web_name)
    await call.message.answer(
        "➕ <b>YANGI VEB-SAYT / RSS MANBA QO'SHISH (1/3 QADAM):</b>\n\n"
        "Sayt nomini kiriting (masalan: <code>Gazeta.uz Maxsus</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb()
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
        reply_markup=cancel_kb()
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
        reply_markup=cancel_kb()
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
    if success:
        await status_msg.edit_text(
            f"✅ <b>Muvaffaqiyatli qo'shildi!</b>\n\n"
            f"Sayt: <b>{name}</b>\n"
            f"URL: {url}\n"
            f"RSS: {feed_url}",
            parse_mode="HTML",
            reply_markup=back_to_main_kb()
        )
    else:
        await status_msg.edit_text(f"⚠️ {msg}", parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(F.data == "admin:src:test")
async def callback_sources_test_prompt(call: CallbackQuery, state: FSMContext) -> None:
    """Manbani testlash uchun nom so'rash."""
    await call.answer()
    await state.set_state(AdminStates.waiting_for_test_source)
    await call.message.answer(
        "🔍 <b>MANBANI TEKSHIRIB KO'RISH:</b>\n\n"
        "Tekshirmoqchi bo'lgan Telegram kanal username yoki sayt nomini yuboring (masalan: <code>@kunuzofficial</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(StateFilter(AdminStates.waiting_for_test_source))
async def process_test_source(message: Message, state: FSMContext) -> None:
    """Manbani testlash natijasini ko'rsatish."""
    ident = message.text.strip()
    await state.clear()
    status_msg = await message.answer(f"⏳ <b>'{ident}' tekshirilmoqda...</b>", parse_mode="HTML")
    res = await source_manager.test_single_source(ident)
    if not res.get("success"):
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {res.get('error')}", parse_mode="HTML", reply_markup=back_to_main_kb())
        return

    text = (
        f"✅ <b>Natija:</b> {res.get('source_name')}\n"
        f"Turi: <b>{res.get('source_type')}</b>\n"
        f"Olingan postlar: <b>{res.get('total_fetched')} ta</b>\n"
        f"Metroga oid yangiliklar: <b>{res.get('metro_found')} ta</b>\n\n"
    )
    samples = res.get("sample_items", [])
    if samples:
        text += "<b>Oxirgi postlar namunalari:</b>\n"
        for s in samples[:3]:
            text += f"• <i>{html.escape(s.title[:80])}</i>\n"

    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())


# =========================================================================
# FILTR VA TEST VOSITALARI
# =========================================================================

@router.callback_query(F.data == "admin:filter")
async def callback_filter_menu(call: CallbackQuery) -> None:
    """Filtr menyusi."""
    await call.answer()
    text = (
        "🧪 <b>FILTR VA TEST VOSITALARI BO'LIMI:</b>\n\n"
        "Ushbu bo'lim orqali quyidagilarni amalga oshirishingiz mumkin:\n"
        "1. <b>Matnni filtrdan testlash:</b> Ixtiyoriy xabarni botga yuborib, uning qanday teglanishi va qabul qilinishini tekshirish;\n"
        "2. <b>Maxsus kalit so'zlar:</b> Yangi metro atamalari yoki bekatlarini dinamik qo'shish;\n"
        "3. <b>Test Alert:</b> Adminga haqiqiy ko'rinishdagi xabarnoma jo'natish."
    )
    await safe_edit_message(call, text, reply_markup=filter_menu_kb())


@router.callback_query(F.data == "admin:flt:test_text")
async def callback_filter_test_start(call: CallbackQuery, state: FSMContext) -> None:
    """Matn yuborish so'rovi."""
    await call.answer()
    await state.set_state(AdminStates.waiting_for_test_text)
    await call.message.answer(
        "🧪 <b>MATNNI FILTRDAN TEKSHIRISH:</b>\n\n"
        "Istalgan yangilik matni yoki sarlavhasini yuboring. Tizim uni tahlil qilib, to'liq hisobot beradi:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(StateFilter(AdminStates.waiting_for_test_text))
async def process_filter_test_text(message: Message, state: FSMContext) -> None:
    """Yuborilgan matnni filtr va dublikat tahlilidan o'tkazish."""
    text = message.text.strip()
    await state.clear()

    analysis = explain_filter(text, text)
    is_metro = analysis.get("is_metro", False)
    tags = analysis.get("tags", [])
    reason = analysis.get("reason", "")
    matched = analysis.get("matched", [])

    is_dup, dup_source, sim = deduplicator.is_duplicate(text, text, "Test")

    verdict_icon = "🟢 QABUL QILINADI (METROGA OID)" if is_metro else "🔴 RAD ETILADI (METROGA ALOQADOR EMAS)"
    tags_str = " ".join(tags) if tags else "Mavjud emas"
    matched_str = ", ".join(matched) if matched else "Mos keluvchi belgilar yo'q"
    dup_str = f"⚠️ Ha! (Asl manba: {dup_source}, o'xshashlik: {sim*100:.1f}%)" if is_dup else f"✅ Yo'q (Maksimal o'xshashlik: {sim*100:.1f}%)"

    result_text = (
        "🔬 <b>FILTR DIAGNOSTIKASI NATIJASI:</b>\n\n"
        f"<b>Qaror:</b> {verdict_icon}\n"
        f"🏷️ <b>Berilgan teglar:</b> <code>{tags_str}</code>\n"
        f"🔍 <b>Tahlil sababi:</b> {reason}\n"
        f"📌 <b>Aniqlangan belgilar:</b> <code>{matched_str}</code>\n\n"
        f"🧠 <b>Kross-dublikat tekshiruvi:</b>\n{dup_str}"
    )
    await message.answer(result_text, parse_mode="HTML", reply_markup=back_to_main_kb())


@router.callback_query(F.data == "admin:flt:keywords")
async def callback_filter_keywords(call: CallbackQuery) -> None:
    """Maxsus kalit so'zlar ro'yxati."""
    await call.answer()
    keywords = get_custom_keywords()
    text = (
        f"🏷️ <b>ADMIN QO'SHGAN MAXSUS KALIT SO'ZLAR ({len(keywords)} ta):</b>\n\n"
        "<i>Ushbu so'zlar Toshkent metrosiga oid yangi xabarlarni tutishda asosiy filtrga qo'shimcha sifatida ishlaydi:</i>"
    )
    await safe_edit_message(call, text, reply_markup=custom_keywords_kb(keywords))


@router.callback_query(F.data == "admin:flt:add_kw")
async def callback_filter_add_kw_start(call: CallbackQuery, state: FSMContext) -> None:
    """Yangi kalit so'z kiritish so'rovi."""
    await call.answer()
    await state.set_state(AdminStates.waiting_for_new_keyword)
    await call.message.answer(
        "➕ <b>YANGI KALIT SO'Z QO'SHISH:</b>\n\n"
        "Metroga oid yangi so'z yoki bekat nomini kiriting (masalan: <code>Yangi Toshkent bekati</code>):",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(StateFilter(AdminStates.waiting_for_new_keyword))
async def process_filter_add_kw(message: Message, state: FSMContext) -> None:
    """Kalit so'zni saqlash."""
    kw = message.text.strip()
    await state.clear()
    success = add_custom_keyword(kw)
    if success:
        await message.answer(
            f"✅ <b>'{kw}'</b> kalit so'zi muvaffaqiyatli qo'shildi va filtr xotirasiga saqlandi!",
            parse_mode="HTML",
            reply_markup=back_to_main_kb()
        )
    else:
        await message.answer("⚠️ Kalit so'z juda qisqa yoki xatolik yuz berdi.", reply_markup=back_to_main_kb())


@router.callback_query(F.data.startswith("admin:flt:del_kw:"))
async def callback_filter_del_kw(call: CallbackQuery) -> None:
    """Kalit so'zni o'chirish."""
    kw = call.data.split(":")[-1]
    success = remove_custom_keyword(kw)
    if success:
        await call.answer(f"'{kw}' kalit so'zi o'chirildi!", show_alert=True)
    else:
        await call.answer("O'chirishda xatolik!", show_alert=True)
    await callback_filter_keywords(call)


@router.callback_query(F.data == "admin:flt:test_alert")
async def callback_filter_test_alert(call: CallbackQuery) -> None:
    """Test xabarnomasini chaqirish."""
    await call.answer("Test xabarnoma jo'natilmoqda...", show_alert=False)
    test_item = NewsItem(
        raw_id="admin_test_post_002",
        url="https://tashmetro.uz",
        title="Toshkent metrosida yangi poyezdlar sinovi yakunlandi (TEST OGOHLANTIRISH)",
        content="Yangi tarkiblar Chilonzor yo'nalishida yo'lovchilarga xizmat ko'rsatishni boshladi. Ushbu xabar admin boshqaruv panelidan test sifatida yuborildi.",
        source_name="Metro Monitoring Test Markazi",
        published_at=datetime.datetime.now().isoformat(),
        tags=["#metro", "#chilonzor", "#poyezd", "#test"]
    )
    await send_metro_alert(call.bot, test_item, chat_ids=[call.message.chat.id])
    await call.message.answer("✅ <b>Test ogohlantirish xabari muvaffaqiyatli yetkazildi!</b>", parse_mode="HTML")


# =========================================================================
# KESH VA XOTIRANI BOSHQARISH (CACHE MANAGEMENT)
# =========================================================================

@router.callback_query(F.data == "admin:cache")
async def callback_cache_menu(call: CallbackQuery) -> None:
    """Kesh boshqaruv menyusi."""
    await call.answer()
    text = (
        "🧹 <b>KESH VA XOTIRANI TOZALASH BO'LIMI:</b>\n\n"
        f"• <b>Keshdagi xabarlar (seen_posts.json):</b> {storage.count} ta\n"
        f"• <b>Antidublikat xotirasi (seen_fingerprints.json):</b> {len(deduplicator._history)} ta voqea\n\n"
        "⚠️ <i>Diqqat: Keshni tozalash avval ko'rilgan xabarlarning qayta tekshirilishiga sabab bo'lishi mumkin.</i>"
    )
    await safe_edit_message(call, text, reply_markup=cache_menu_kb())


@router.callback_query(F.data == "admin:cache:seen")
async def callback_cache_clear_seen(call: CallbackQuery) -> None:
    """Ko'rilgan xabarlar keshini tozalash."""
    c = storage.clear()
    await call.answer(f"Seen posts keshi tozalandi ({c} ta element o'chirildi)!", show_alert=True)
    await callback_cache_menu(call)


@router.callback_query(F.data == "admin:cache:fingerprints")
async def callback_cache_clear_fingerprints(call: CallbackQuery) -> None:
    """Antidublikat izlari xotirasini tozalash."""
    c = deduplicator.clear_history()
    await call.answer(f"Antidublikat xotirasi tozalandi ({c} ta voqea o'chirildi)!", show_alert=True)
    await callback_cache_menu(call)


@router.callback_query(F.data == "admin:cache:all")
async def callback_cache_clear_all(call: CallbackQuery) -> None:
    """Barcha keshni tozalash."""
    c1 = storage.clear()
    c2 = deduplicator.clear_history()
    await call.answer(f"Barcha kesh tozalandi! ({c1} xabar, {c2} voqea o'chirildi)", show_alert=True)
    await callback_cache_menu(call)
