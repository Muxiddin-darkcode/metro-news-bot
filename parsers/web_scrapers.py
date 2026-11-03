import logging
import asyncio
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
    if "<" not in html_text and ">" not in html_text:
        return html_text.strip()
    soup = BeautifulSoup(html_text, "lxml")
    return soup.get_text(separator=" ", strip=True)

def _parse_rss_entries(content: bytes, source_info: Dict, limit: int) -> List[NewsItem]:
    """Sinxron RSS XML parse jarayoni (worker threadda bajariladi)."""
    feed = feedparser.parse(content)
    items: List[NewsItem] = []
    name = source_info.get("name", "Veb-sayt")
    
    for entry in feed.entries[:limit]:
        title = clean_html(entry.get("title", ""))
        link = entry.get("link", "")
        
        # Matn (summary yoki description)
        summary = entry.get("summary") or entry.get("description", "")
        content_txt = clean_html(summary)
        published = entry.get("published", "")

        if not title and not content_txt:
            continue

        # Rasmni ajratib olish (enclosure, media_content, links yoki img tegidan)
        image_url = None
        enclosures = entry.get("enclosures", [])
        for enc in enclosures:
            if str(enc.get("type", "")).startswith("image/"):
                image_url = enc.get("href")
                break

        if not image_url and "media_content" in entry:
            for mc in entry.get("media_content", []):
                if mc.get("medium") == "image" or "image" in str(mc.get("type", "")):
                    image_url = mc.get("url")
                    break

        if not image_url and "links" in entry:
            for lk in entry.get("links", []):
                if str(lk.get("type", "")).startswith("image/"):
                    image_url = lk.get("href")
                    break

        if not image_url and summary and "<img" in summary:
            try:
                img_soup = BeautifulSoup(summary, "lxml")
                img_el = img_soup.find("img")
                if img_el and img_el.get("src"):
                    image_url = img_el.get("src")
            except Exception:
                pass

        item = NewsItem(
            title=title,
            content=content_txt,
            url=link or f"{source_info.get('url')}#{title[:30]}",
            source_name=f"Veb / {name}",
            source_type="web",
            raw_id=link or title,
            published_at=published,
            image_url=image_url
        )
        items.append(item)

    return items

async def fetch_rss_source(
    client: httpx.AsyncClient,
    source_info: Dict,
    limit: int = 10
) -> List[NewsItem]:
    """RSS lentasi orqali veb-saytdan so'nggi yangiliklarni yuklaydi."""
    feed_url = source_info.get("feed_url") or source_info.get("url")
    name = source_info.get("name", "Veb-sayt")

    try:
        response = await client.get(feed_url, headers=HEADERS, timeout=8.0, follow_redirects=True)
        if response.status_code != 200:
            logger.debug(f"RSS manba ochilmadi: {name} (status {response.status_code})")
            return []

        # CPU-talab RSS parsingni worker threadga o'tkazamiz
        return await asyncio.to_thread(_parse_rss_entries, response.content, source_info, limit)

    except httpx.TimeoutException:
        logger.debug(f"RSS manba vaqti tugadi (timeout): {name}")
    except Exception as e:
        logger.debug(f"RSS o'qishda xatolik ({name}): {e}")

    return []

def _parse_html_entries(html_text: str, source_info: Dict, limit: int) -> List[NewsItem]:
    """Sinxron HTML sahifa parse jarayoni (worker threadda bajariladi)."""
    items: List[NewsItem] = []
    url = source_info.get("url", "")
    name = source_info.get("name", "Veb-sayt")
    soup = BeautifulSoup(html_text, "lxml")
    
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

    return items

async def fetch_html_source(
    client: httpx.AsyncClient,
    source_info: Dict,
    limit: int = 8
) -> List[NewsItem]:
    """Oddiy HTML veb-sahifadan yangiliklarni qidiruvchi zaxira parser."""
    url = source_info.get("url")
    name = source_info.get("name", "Veb-sayt")

    try:
        response = await client.get(url, headers=HEADERS, timeout=8.0, follow_redirects=True)
        if response.status_code != 200:
            return []

        return await asyncio.to_thread(_parse_html_entries, response.text, source_info, limit)
    except httpx.TimeoutException:
        logger.debug(f"HTML manba so'rov vaqti tugadi: {name}")
    except Exception as e:
        logger.debug(f"HTML o'qishda xatolik ({name}): {e}")

    return []

def _extract_og_image_from_html(html_text: str, base_url: str) -> Optional[str]:
    """HTML dan og:image ni worker threadda xavfsiz ajratib olish."""
    try:
        soup = BeautifulSoup(html_text, "lxml")
        og_img = (
            soup.find("meta", property="og:image") or
            soup.find("meta", attrs={"name": "og:image"}) or
            soup.find("meta", attrs={"name": "twitter:image"}) or
            soup.find("meta", attrs={"name": "thumbnail"}) or
            soup.find("link", rel="image_src")
        )
        if og_img:
            img_url = og_img.get("content") or og_img.get("href")
            if img_url:
                img_url = img_url.strip()
                if img_url.startswith("//"):
                    return "https:" + img_url
                elif img_url.startswith("/") and not img_url.startswith("//"):
                    from urllib.parse import urlparse
                    p = urlparse(base_url)
                    return f"{p.scheme}://{p.netloc}{img_url}"
                if img_url.startswith("http"):
                    return img_url
    except Exception:
        pass
    return None

async def extract_og_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Maqola veb-sahifasidan Open Graph (og:image) orqali rasmni tezkor ajratib olish."""
    if not url or not url.startswith("http"):
        return None
    try:
        response = await client.get(url, headers=HEADERS, timeout=6.0, follow_redirects=True)
        if response.status_code == 200:
            return await asyncio.to_thread(_extract_og_image_from_html, response.text, url)
    except Exception as e:
        logger.debug(f"og:image ajratib olishda xatolik ({url}): {e}")
    return None
