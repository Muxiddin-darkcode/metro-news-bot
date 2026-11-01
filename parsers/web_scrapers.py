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

            if not image_url and summary:
                try:
                    img_soup = BeautifulSoup(summary, "lxml")
                    img_el = img_soup.find("img")
                    if img_el and img_el.get("src"):
                        image_url = img_el.get("src")
                except Exception:
                    pass

            item = NewsItem(
                title=title,
                content=content,
                url=link or f"{source_info.get('url')}#{title[:30]}",
                source_name=f"Veb / {name}",
                source_type="web",
                raw_id=link or title,
                published_at=published,
                image_url=image_url
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


async def extract_og_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """
    Maqola veb-sahifasidan Open Graph (og:image) orqali haqiqiy fotosuratni ajratib olish.
    Kun.uz, Daryo.uz, Gazeta.uz, UzNews, Anhor va boshqa OAVlar uchun 100% ishlaydi.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        response = await client.get(url, headers=HEADERS, timeout=7.0, follow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
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
                        img_url = "https:" + img_url
                    elif img_url.startswith("/") and not img_url.startswith("//"):
                        from urllib.parse import urlparse
                        p = urlparse(url)
                        img_url = f"{p.scheme}://{p.netloc}{img_url}"
                    if img_url.startswith("http"):
                        return img_url
    except Exception as e:
        logger.debug(f"og:image ajratib olishda xatolik ({url}): {e}")
    return None
