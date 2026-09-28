import logging
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from parsers.base import NewsItem

logger = logging.getLogger("MetroMonitor.TelegramParser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz,ru,en;q=0.9",
}

async def fetch_telegram_channel(
    client: httpx.AsyncClient,
    username: str,
    channel_name: str,
    limit: int = 8
) -> List[NewsItem]:
    """
    Telegram ochiq kanalidan eng so'nggi postlarni oladi (https://t.me/s/{username}).
    Hech qanday bot tokeni, API sessiyasi yoki telefon raqamsiz ishlaydi.
    """
    clean_username = username.strip().lstrip("@")
    url = f"https://t.me/s/{clean_username}"
    items: List[NewsItem] = []

    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"Telegram kanal ochilmadi: @{clean_username} (status: {response.status_code})")
            return items

        soup = BeautifulSoup(response.text, "lxml")
        posts = soup.find_all("div", class_="tgme_widget_message")
        
        # Eng so'nggi postlardan limit miqdorda olish
        for post in posts[-limit:]:
            post_id = post.get("data-post", "")
            
            # Matnni qidirish
            text_el = post.find("div", class_="tgme_widget_message_text")
            text = text_el.get_text(separator="\n", strip=True) if text_el else ""
            
            # Agar matn bo'lmasa (faqat rasm/stiker), davom etish
            if not text:
                continue

            # Havola va vaqt
            date_el = post.find("a", class_="tgme_widget_message_date")
            post_url = date_el.get("href", f"https://t.me/{post_id}") if date_el else f"https://t.me/{post_id}"
            time_el = post.find("time")
            published_at = time_el.get("datetime") if time_el else None

            # Sarlavha uchun matnning birinchi qatorini olamiz
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0][:150] if lines else f"Telegram xabari (@{clean_username})"
            content = "\n".join(lines[1:]) if len(lines) > 1 else text

            item = NewsItem(
                title=title,
                content=content,
                url=post_url,
                source_name=f"Telegram / @{clean_username} ({channel_name})",
                source_type="telegram",
                raw_id=post_id or post_url,
                published_at=published_at
            )
            items.append(item)

    except httpx.TimeoutException:
        logger.debug(f"Telegram kanal so'rov vaqti tugadi (timeout): @{clean_username}")
    except Exception as e:
        logger.warning(f"Telegram kanalni o'qishda xatolik (@{clean_username}): {e}")

    return items
