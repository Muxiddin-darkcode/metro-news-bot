"""
Toshkent Metropoliteni Yangiliklarini Formatlash Moduli (100% Mahalliy, AI'siz).
OAV va kanallardagi xabarlarni buzmasdan, 100% asl sarlavha va asl matnni saqlagan holda
4 ta liniya, 50+ bekatlar va qayta tiklanish holatlarini avtomatik ulaydi.
"""

import re
import html
import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass

from config import format_uz_time
from parsers.base import NewsItem
from core.filter import (
    detect_line_and_station,
    detect_metro_topic,
    is_resolution_text,
    is_disruption_text
)


def clean_raw_news_text(text: str) -> str:
    """
    Xom matndan reklama, bot/kanal havolalari va ortiqcha shovqinlarni tozalash.
    Asl yangilik matnining o'zini toza holatda saqlab qoladi.
    """
    if not text:
        return ""

    t = text

    # 1. URL va Telegram havolalarni tozalash (http, https, t.me)
    t = re.sub(r'https?://[^\s]+', '', t)
    t = re.sub(r'(?:t\.me|telegram\.me)/[^\s]+', '', t)

    # 2. @username havolalarni tozalash
    t = re.sub(r'@[a-zA-Z0-9_]{4,}', '', t)

    # 3. Keng tarqalgan reklama, chaqiriq va ortiqcha jumlalar
    noise_patterns = [
        r'(?i)bizga\s+obuna\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)kanalga\s+a[\'’`]?zo\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)kanalimizga\s+obuna\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)rasmiy\s+kanalimizga\s+ulan[:!]?',
        r'(?i)batafsil\s+(?:bu\s+yerda|havola\s+orqali|quyidagi|saytimizda)[:!]?',
        r'(?i)k[oóõö][\'’`]?proq\s+yangiliklar[:!]?',
        r'(?i)подписывайтесь\s+на\s+(?:наш\s+)?канал[:!]?',
        r'(?i)читайте\s+(?:также|подробнее)[:!]?',
        r'(?i)barcha\s+huquqlar\s+himoyalangan',
        r'(?i)все\s+права\s+защищены',
        r'(?i)foto\s*:\s*[^\n]+',
        r'(?i)video\s*:\s*[^\n]+',
        r'(?i)manba\s*:\s*[^\n]+',
        r'(?i)reklama\s*:\s*[^\n]+',
        r'(?i)реклама\s*:\s*[^\n]+'
    ]
    for pat in noise_patterns:
        t = re.sub(pat, '', t)

    # 4. Ortiqcha bo'shliqlar va bo'sh qatorlarni normallashtirish
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n\n', t)
    return t.strip()


def safe_truncate_words(text: str, max_len: int) -> str:
    """Matnni so'zlarni chala qoldirmasdan, butun so'z bo'yicha toza qisqartirish."""
    if not text or len(text) <= max_len:
        return text.strip()
    truncated = text[:max_len]
    last_space = max(truncated.rfind(" "), truncated.rfind("\n"))
    if last_space > int(max_len * 0.6):
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,;:-—") + "..."


@dataclass
class FormattedAlert:
    """Formatlangan metro xabari obyekti."""
    html_text: str
    caption_text: str
    line: str = ""
    station: str = ""
    topic: str = ""
    is_resolution: bool = False
    badge: str = "🚇 METRO XABARI"


def format_metro_alert(item: NewsItem) -> FormattedAlert:
    """
    Yangilikni to'liq mahalliy tahlil qilib, chiroyli HTML va Caption formatiga keltirish.
    0 millisekundlik kechikish bilan 100% asl matn saqlanadi.
    """
    full_text = f"{item.title} {item.content}"
    line, station = detect_line_and_station(full_text)
    topic = detect_metro_topic(full_text)
    is_res = is_resolution_text(full_text)

    line_val = line or ""
    station_val = station or ""
    badge = "🟢 HARAKAT QAYTA TIKLANDI" if is_res else (line_val or "🚇 METRO XABARI")

    now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
    if item.published_at:
        try:
            pub_str = item.published_at.replace("Z", "+00:00")
            pub_dt = datetime.datetime.fromisoformat(pub_str)
            now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
        except Exception:
            pass

    clean_title = html.escape(item.title.strip(), quote=False)
    clean_source = html.escape(item.source_name.strip(), quote=False)

    raw_content = clean_raw_news_text(item.content.strip())
    content_safe_full = html.escape(raw_content, quote=False)
    if len(content_safe_full) > 850:
        content_safe_full = safe_truncate_words(content_safe_full, 850)

    content_safe_caption = html.escape(raw_content, quote=False)
    if len(content_safe_caption) > 550:
        content_safe_caption = safe_truncate_words(content_safe_caption, 550)

    tags_str = " ".join(item.tags) if item.tags else "#metro #toshkent"

    # Sarlavha blokini shakllantirish
    header_lines = ["🚇 <b>TOSHKENT METROSI XABARI</b>"]
    loc_parts = []
    if line_val:
        loc_parts.append(f"<b>{line_val}</b>")
    if station_val:
        loc_parts.append(f"<b>{station_val}</b>")

    if loc_parts:
        header_lines.append(" | ".join(loc_parts))

    if is_res:
        header_lines.append("🟢 <b>HARAKAT QAYTA TIKLANDI</b>")
    elif topic:
        header_lines.append(f"📂 <b>Mavzu:</b> {topic}")

    header_block = "\n".join(header_lines)

    # To'liq HTML xabar
    html_text = f"{header_block}\n\n📌 <b>{clean_title}</b>\n\n"
    if content_safe_full and content_safe_full.lower() != clean_title.lower():
        html_text += f"{content_safe_full}\n\n"
    html_text += (
        f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}\n"
        f"🔍 <b>Teglar:</b> <code>{html.escape(tags_str)}</code>"
    )

    # Fotosurat osti caption matni
    caption_text = f"{header_block}\n\n📌 <b>{clean_title}</b>\n\n"
    if content_safe_caption and content_safe_caption.lower() != clean_title.lower():
        caption_text += f"{content_safe_caption}\n\n"
    caption_text += f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}"

    return FormattedAlert(
        html_text=html_text,
        caption_text=caption_text,
        line=line_val,
        station=station_val,
        topic=topic,
        is_resolution=is_res,
        badge=badge
    )


# Orqaga moslik (Backwards compatibility)
def format_original_news_html(item: NewsItem, badge: str = "🚇 METRO XABARI", result=None) -> str:
    return format_metro_alert(item).html_text


def format_original_news_caption(item: NewsItem, badge: str = "🚇 METRO XABARI", result=None) -> str:
    return format_metro_alert(item).caption_text
