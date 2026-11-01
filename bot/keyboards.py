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
    Asosiy Reply klaviatura menyusi (ekranning pastida doimiy turuvchi).
    Qisqa, ixcham va rangli tugmalar (style: primary/success/danger).
    """
    kb = [
        [
            KeyboardButton(text="🎛 Panel", style="primary"),
            KeyboardButton(text="🔍 Tekshirish", style="success")
        ],
        [
            KeyboardButton(text="📅 Bugungi xabarlar", style="primary"),
            KeyboardButton(text="📰 So'nggi xabarlar", style="primary")
        ],
        [
            KeyboardButton(text="🤖 AI Tahlilchi", style="primary"),
            KeyboardButton(text="📊 Tizim holati", style="primary")
        ],
        [
            KeyboardButton(text="🌐 Manbalar", style="primary"),
            KeyboardButton(text="⚙️ Sozlamalar", style="primary")
        ],
        [
            KeyboardButton(text="📋 Loglar", style="primary"),
            KeyboardButton(text="🧹 Kesh", style="danger")
        ],
        [
            KeyboardButton(text="❌ Panelni yopish", style="danger")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_collapsed_keyboard() -> ReplyKeyboardMarkup:
    """
    Yopilgan (yig'ilgan) holatdagi bittagina ixcham tugma.
    Foydalanuvchi klaviaturani butunlay yo'qotmasdan, bitta bosish bilan qayta ochishi mumkin.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎛 Panelni ochish", style="success")]
        ],
        resize_keyboard=True,
        is_persistent=False
    )


def get_settings_reply_keyboard(is_paused: bool = False) -> ReplyKeyboardMarkup:
    """Sozlamalar Reply klaviaturasi (qisqa nomlar bilan)."""
    if is_paused:
        toggle_btn = KeyboardButton(text="▶️ Yoqish", style="success")
    else:
        toggle_btn = KeyboardButton(text="⏸️ To'xtatish", style="danger")

    kb = [
        [
            toggle_btn,
            KeyboardButton(text="🩺 Diagnostika", style="primary")
        ],
        [
            KeyboardButton(text="⏱️ 30s", style="primary"),
            KeyboardButton(text="⏱️ 60s", style="primary"),
            KeyboardButton(text="⏱️ 120s", style="primary")
        ],
        [
            KeyboardButton(text="🏷️ Kalit so'zlar", style="primary"),
            KeyboardButton(text="🧹 Kesh", style="danger")
        ],
        [
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_sources_reply_keyboard(tg_count: int = 0, web_count: int = 0) -> ReplyKeyboardMarkup:
    """Manbalar Reply klaviaturasi (qisqa nomlar bilan)."""
    tg_label = f"📱 Telegram ({tg_count})" if tg_count else "📱 Telegram"
    web_label = f"💻 Saytlar ({web_count})" if web_count else "💻 Saytlar"
    kb = [
        [
            KeyboardButton(text=tg_label, style="primary"),
            KeyboardButton(text=web_label, style="primary")
        ],
        [
            KeyboardButton(text="➕ Kanal", style="success"),
            KeyboardButton(text="➕ Sayt", style="success")
        ],
        [
            KeyboardButton(text="🔍 Tekshirish", style="primary"),
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_ai_reply_keyboard(ai_enabled: bool = True) -> ReplyKeyboardMarkup:
    """AI Tahlilchi Reply klaviaturasi (qisqa nomlar bilan)."""
    if ai_enabled:
        toggle_btn = KeyboardButton(text="⏸️ O'chirish", style="danger")
    else:
        toggle_btn = KeyboardButton(text="▶️ Yoqish", style="success")

    kb = [
        [
            KeyboardButton(text="🔄 Tekshirish", style="success"),
            toggle_btn
        ],
        [
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_logs_reply_keyboard() -> ReplyKeyboardMarkup:
    """Loglar Reply klaviaturasi (qisqa nomlar bilan)."""
    kb = [
        [
            KeyboardButton(text="🔄 Yangilash", style="success"),
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_cache_reply_keyboard() -> ReplyKeyboardMarkup:
    """Kesh Reply klaviaturasi (bir qatorga sig'adigan ixcham nomlar bilan)."""
    kb = [
        [
            KeyboardButton(text="🗑️ Postlar keshi", style="danger"),
            KeyboardButton(text="🧠 Dublikat izlari", style="danger")
        ],
        [
            KeyboardButton(text="🧹 Barcha kesh", style="danger"),
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_keywords_reply_keyboard() -> ReplyKeyboardMarkup:
    """Kalit so'zlar Reply klaviaturasi (qisqa nomlar bilan)."""
    kb = [
        [
            KeyboardButton(text="➕ So'z qo'shish", style="success"),
            KeyboardButton(text="🔍 Tekshirish", style="primary")
        ],
        [
            KeyboardButton(text="◀️ Asosiy menyu", style="primary")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bekor qilish Reply klaviaturasi."""
    kb = [
        [
            KeyboardButton(text="❌ Bekor qilish", style="danger")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, is_persistent=False)


def post_source_url_kb(url: str) -> InlineKeyboardMarkup:
    """
    Xabar ostidagi yagona inline tugma: faqatgina asl manbani ochish uchun.
    Barcha boshqa boshqaruv tugmalari pastki Reply Keyboard menyusida joylashgan.
    """
    clean_url = url.strip() if url else "https://tashmetro.uz"
    if not clean_url.startswith("http"):
        clean_url = f"https://{clean_url}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔗 Asl manbani ochish", url=clean_url)
            ]
        ]
    )
