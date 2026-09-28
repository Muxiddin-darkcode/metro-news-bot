import logging
import feedparser
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from parsers.base import NewsItem

logger = logging.getLogger("MetroMonitor.WebParser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.9,*/*;q=0.8",
}

def clean_html(html_text: str) -> str:
    """HTML teglaridan tozalangan toza matn qaytaradi."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "lxml")
    return soup.get_text(separator=" ", strip=True)

async def fetch_rss_source(
    client: httpx.AsyncClient,
    source_info: Dict,
    limit: int = 10
) -> List[NewsItem]:
    """RSS lentasi orqali veb-saytdan so'nggi yangiliklarni yuklaydi."""
    feed_url = source_info.get("feed_url") or source_info.get("url")
    name = source_info.get("name", "Veb-sayt")
    items: List[NewsItem] = []

    try:
        response = await client.get(feed_url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            logger.debug(f"RSS manba ochilmadi: {name} (status {response.status_code})")
            return items

        feed = feedparser.parse(response.content)
        
        for entry in feed.entries[:limit]:
            title = clean_html(entry.get("title", ""))
            link = entry.get("link", "")
            
            # Matn (summary yoki description)
            summary = entry.get("summary") or entry.get("description", "")
            content = clean_html(summary)
            published = entry.get("published", "")

            if not title and not content:
                continue

            item = NewsItem(
                title=title,
                content=content,
                url=link or f"{source_info.get('url')}#{title[:30]}",
                source_name=f"Veb / {name}",
                source_type="web",
                raw_id=link or title,
                published_at=published
            )
            items.append(item)

    except httpx.TimeoutException:
        logger.debug(f"RSS manba vaqti tugadi (timeout): {name}")
    except Exception as e:
        logger.debug(f"RSS o'qishda xatolik ({name}): {e}")

    return items

async def fetch_html_source(
    client: httpx.AsyncClient,
    source_info: Dict,
    limit: int = 8
) -> List[NewsItem]:
    """Oddiy HTML veb-sahifadan yangiliklarni qidiruvchi zaxira parser."""
    url = source_info.get("url")
    name = source_info.get("name", "Veb-sayt")
    items: List[NewsItem] = []

    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            return items

        soup = BeautifulSoup(response.text, "lxml")
        # Ko'p tarqalgan yangilik sarlavhalari (h1, h2, h3, a)
        articles = soup.find_all(["article", "div"], class_=lambda c: c and any(k in str(c).lower() for k in ["news", "post", "item", "article"]))

        count = 0
        for art in articles:
            if count >= limit:
                break
            link_tag = art.find("a")
            if not link_tag:
                continue
            
            href = link_tag.get("href", "")
            if href.startswith("/"):
                href = f"{url.rstrip('/')}{href}"
            
            title = clean_html(link_tag.get_text())
            if not title or len(title) < 15:
                continue

            desc_tag = art.find(["p", "span"])
            desc = clean_html(desc_tag.get_text()) if desc_tag else ""

            item = NewsItem(
                title=title,
                content=desc,
                url=href,
                source_name=f"Veb / {name}",
                source_type="web",
                raw_id=href or title
            )
            items.append(item)
            count += 1

    except Exception as e:
        logger.debug(f"HTML o'qishda xatolik ({name}): {e}")

    return items
