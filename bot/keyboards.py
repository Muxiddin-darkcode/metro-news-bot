from typing import List, Dict
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import settings

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Admin uchun mobilga mos, qulay boshqaruv klaviaturasi.
    """
    kb = [
        [
            KeyboardButton(text="🎛️ Boshqaruv paneli", style="primary"),
            KeyboardButton(text="🔍 Hozir tekshirish", style="success")
        ],
        [
            KeyboardButton(text="📊 Tizim holati", style="primary"),
            KeyboardButton(text="📰 So'nggi xabarlar", style="primary")
        ],
        [
            KeyboardButton(text="📋 Tizim loglari", style="primary"),
            KeyboardButton(text="⚙️ Sozlamalar", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=True)


def admin_main_dashboard_kb(is_paused: bool = False) -> InlineKeyboardMarkup:
    """
    Boshqaruv paneli asosiy Dashboard menyusi.
    Har bir tugma telefonda 100% to'liq ko'rinadi va kesilib ketmaydi.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 Manbalar", callback_data="admin:sources"),
            InlineKeyboardButton(text="⚡ Monitoring", callback_data="admin:monitor")
        ],
        [
            InlineKeyboardButton(text="🧪 Filtr & Test", callback_data="admin:filter"),
            InlineKeyboardButton(text="📰 Yangiliklar", callback_data="admin:news")
        ],
        [
            InlineKeyboardButton(text="📋 Loglar", callback_data="admin:logs"),
            InlineKeyboardButton(text="🩺 Diagnostika", callback_data="admin:diag")
        ],
        [
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings"),
            InlineKeyboardButton(text="🧹 Kesh", callback_data="admin:cache")
        ],
        [
            InlineKeyboardButton(text="🔍 Hozir tekshirish", callback_data="btn_check_now", style="success")
        ],
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def sources_menu_kb(tg_count: int, web_count: int) -> InlineKeyboardMarkup:
    """Manbalarni boshqarish bo'limi tugmalari (mobilga mos)."""
    keyboard = [
        [
            InlineKeyboardButton(text=f"📱 Kanallar ({tg_count})", callback_data="admin:src:tg:0"),
            InlineKeyboardButton(text=f"💻 Saytlar ({web_count})", callback_data="admin:src:web:0")
        ],
        [
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin:src:add_tg"),
            InlineKeyboardButton(text="➕ Sayt qo'shish", callback_data="admin:src:add_web")
        ],
        [
            InlineKeyboardButton(text="🔍 Manbani testlash", callback_data="admin:src:test"),
            InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def tg_sources_page_kb(channels: List[Dict], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Telegram kanallari sahifalangan ro'yxati (mobilga mos)."""
    total_pages = max(1, (len(channels) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_channels = channels[start_idx:end_idx]

    rows = []
    for ch in current_channels:
        u = ch.get("username", "")
        rows.append([
            InlineKeyboardButton(text=f"📱 @{u[:16]}", callback_data=f"admin:src:view_tg:{u}"),
            InlineKeyboardButton(text="🗑️", callback_data=f"admin:src:del_tg:{u}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:src:tg:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:src:tg:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin:src:add_tg"),
        InlineKeyboardButton(text="◀️ Manbalar", callback_data="admin:sources")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def web_sources_page_kb(websites: List[Dict], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Veb-saytlar sahifalangan ro'yxati (mobilga mos)."""
    total_pages = max(1, (len(websites) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_sites = websites[start_idx:end_idx]

    rows = []
    for site in current_sites:
        sid = site.get("id", site.get("name", ""))[:20]
        name = site.get("name", "Sayt")[:16]
        rows.append([
            InlineKeyboardButton(text=f"💻 {name}", callback_data=f"admin:src:view_web:{sid}"),
            InlineKeyboardButton(text="🗑️", callback_data=f"admin:src:del_web:{sid}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:src:web:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:src:web:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(text="➕ Sayt qo'shish", callback_data="admin:src:add_web"),
        InlineKeyboardButton(text="◀️ Manbalar", callback_data="admin:sources")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def monitoring_menu_kb(is_paused: bool, interval: int, threshold: float) -> InlineKeyboardMarkup:
    """Monitoring va sozlamalar menyusi (mobilga mos)."""
    toggle_text = "▶️ Monitoringni YOQISH" if is_paused else "⏸️ Monitoringni TO'XTATISH"

    keyboard = [
        [InlineKeyboardButton(text=toggle_text, callback_data="admin:mon:toggle")],
        [InlineKeyboardButton(text="🔍 Hozir tekshirish", callback_data="btn_check_now", style="success")],
        [
            InlineKeyboardButton(text=f"{'✅ ' if interval == 30 else ''}30s", callback_data="admin:mon:int:30"),
            InlineKeyboardButton(text=f"{'✅ ' if interval == 60 else ''}60s", callback_data="admin:mon:int:60"),
            InlineKeyboardButton(text=f"{'✅ ' if interval == 120 else ''}120s", callback_data="admin:mon:int:120"),
            InlineKeyboardButton(text=f"{'✅ ' if interval == 300 else ''}300s", callback_data="admin:mon:int:300")
        ],
        [
            InlineKeyboardButton(text=f"{'✅ ' if abs(threshold - 0.50) < 0.01 else ''}0.50", callback_data="admin:mon:th:0.50"),
            InlineKeyboardButton(text=f"{'✅ ' if abs(threshold - 0.65) < 0.01 else ''}0.65", callback_data="admin:mon:th:0.65"),
            InlineKeyboardButton(text=f"{'✅ ' if abs(threshold - 0.75) < 0.01 else ''}0.75", callback_data="admin:mon:th:0.75"),
            InlineKeyboardButton(text=f"{'✅ ' if abs(threshold - 0.85) < 0.01 else ''}0.85", callback_data="admin:mon:th:0.85")
        ],
        [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def filter_menu_kb() -> InlineKeyboardMarkup:
    """Filtr va test vositalari menyusi (mobilga mos)."""
    keyboard = [
        [InlineKeyboardButton(text="🧪 Matnni testlash", callback_data="admin:flt:test_text")],
        [
            InlineKeyboardButton(text="🏷️ Kalit so'zlar", callback_data="admin:flt:keywords"),
            InlineKeyboardButton(text="➕ So'z qo'shish", callback_data="admin:flt:add_kw")
        ],
        [
            InlineKeyboardButton(text="🚨 Test Alert", callback_data="admin:flt:test_alert"),
            InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def custom_keywords_kb(keywords: List[str]) -> InlineKeyboardMarkup:
    """Maxsus kalit so'zlar ro'yxati menyusi."""
    rows = []
    for kw in keywords[:12]:
        rows.append([
            InlineKeyboardButton(text=f"🏷️ {kw[:16]}", callback_data="noop"),
            InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"admin:flt:del_kw:{kw}")
        ])
    rows.append([
        InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="admin:flt:add_kw"),
        InlineKeyboardButton(text="◀️ Filtr menyusi", callback_data="admin:filter")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cache_menu_kb() -> InlineKeyboardMarkup:
    """Kesh va xotirani tozalash menyusi."""
    keyboard = [
        [InlineKeyboardButton(text="🗑️ Ko'rilgan postlar keshini tozalash", callback_data="admin:cache:seen")],
        [InlineKeyboardButton(text="🧠 Antidublikat xotirasini tozalash", callback_data="admin:cache:fingerprints")],
        [InlineKeyboardButton(text="🧹 BARCHA keshni tozalash", callback_data="admin:cache:all")],
        [InlineKeyboardButton(text="◀️ Asosiy menyu", callback_data="admin:main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def cancel_kb() -> InlineKeyboardMarkup:
    """Bekor qilish tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:cancel")]]
    )


def back_to_main_kb() -> InlineKeyboardMarkup:
    """Asosiy menyuga qaytish tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Asosiy menyuga qaytish", callback_data="admin:main")]]
    )
