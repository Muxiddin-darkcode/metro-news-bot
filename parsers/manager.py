import json
import time
import asyncio
import logging
from typing import List, Dict, Tuple
import httpx

from config import settings, logger
from parsers.base import NewsItem
from parsers.telegram_channels import fetch_telegram_channel
from parsers.web_scrapers import fetch_rss_source, fetch_html_source
from core.storage import storage
from core.filter import is_metro_related
from core.deduplicator import deduplicator

class SourceManager:
    """
    80 ta manbani (40 ta kanal va 40 ta sayt) parallel ravishda
    Semaphore oqimlari orqali boshqaruvchi markaziy menejer.
    """
    def __init__(self, sources_file=settings.SOURCES_FILE):
        self.sources_file = sources_file
        self.telegram_channels: List[Dict] = []
        self.web_sources: List[Dict] = []
        self.last_check_time: float = 0
        self.last_check_duration: float = 0
        self.is_paused: bool = False
        self.load_sources()

    def pause(self) -> None:
        """Monitoringni vaqtincha to'xtatish."""
        self.is_paused = True
        logger.info("Monitoring vaqtincha to'xtatildi (Paused).")

    def resume(self) -> None:
        """Monitoringni davom ettirish."""
        self.is_paused = False
        logger.info("Monitoring davom ettirildi (Resumed).")

    def toggle_pause(self) -> bool:
        """Monitoring holatini almashtirish (yoqish / to'xtatish)."""
        self.is_paused = not self.is_paused
        return self.is_paused

    def save_sources(self) -> bool:
        """Joriy manbalar ro'yxatini sources.json ga saqlash."""
        try:
            self.sources_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "telegram_channels": self.telegram_channels,
                "web_sources": self.web_sources
            }
            with open(self.sources_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"sources.json fayliga yozishda xatolik: {e}")
            return False

    def add_telegram_channel(
        self, username: str, name: str = "", lang: str = "uz", priority: str = "normal"
    ) -> Tuple[bool, str]:
        """Yangi Telegram kanalini ro'yxatga qo'shish."""
        cleaned = username.strip().lstrip("@")
        if cleaned.startswith("t.me/s/"):
            cleaned = cleaned.replace("t.me/s/", "")
        elif cleaned.startswith("t.me/"):
            cleaned = cleaned.replace("t.me/", "")
        elif cleaned.startswith("https://t.me/"):
            cleaned = cleaned.replace("https://t.me/", "")
        cleaned = cleaned.strip("/").strip()

        if not cleaned:
            return False, "Kanal username noto'g'ri ko'rsatildi."

        # Dublikat tekshiruvi
        for ch in self.telegram_channels:
            if ch.get("username", "").lower() == cleaned.lower():
                return False, f"@{cleaned} kanali ro'yxatda allaqachon mavjud."

        channel_obj = {
            "username": cleaned,
            "name": name.strip() if name.strip() else cleaned,
            "lang": lang,
            "priority": priority
        }
        self.telegram_channels.append(channel_obj)
        self.save_sources()
        logger.info(f"Yangi Telegram kanal qo'shildi: @{cleaned}")
        return True, f"@{cleaned} kanali muvaffaqiyatli qo'shildi."

    def remove_telegram_channel(self, username: str) -> Tuple[bool, str]:
        """Telegram kanalni ro'yxatdan o'chirish."""
        cleaned = username.strip().lstrip("@").lower()
        initial_len = len(self.telegram_channels)
        self.telegram_channels = [
            ch for ch in self.telegram_channels
            if ch.get("username", "").lower() != cleaned
        ]
        if len(self.telegram_channels) < initial_len:
            self.save_sources()
            logger.info(f"Telegram kanal o'chirildi: @{cleaned}")
            return True, f"@{cleaned} kanali ro'yxatdan o'chirildi."
        return False, f"@{cleaned} kanali topilmadi."

    def add_web_source(
        self, name: str, url: str, feed_url: str, src_type: str = "rss", lang: str = "uz"
    ) -> Tuple[bool, str]:
        """Yangi Veb-sayt / RSS manba qo'shish."""
        name = name.strip()
        url = url.strip()
        feed_url = feed_url.strip()
        if not name or not url or not feed_url:
            return False, "Sayt nomi, bosh sahifa URL va RSS/Feed havolasi to'liq bo'lishi shart."

        source_id = "".join(c if c.isalnum() else "_" for c in name.lower())[:30].strip("_")
        for src in self.web_sources:
            if src.get("id") == source_id or src.get("feed_url") == feed_url:
                return False, f"'{name}' sayti yoki RSS havolasi ro'yxatda allaqachon mavjud."

        web_obj = {
            "id": source_id,
            "name": name,
            "url": url,
            "feed_url": feed_url,
            "lang": lang,
            "type": src_type
        }
        self.web_sources.append(web_obj)
        self.save_sources()
        logger.info(f"Yangi sayt qo'shildi: {name} ({feed_url})")
        return True, f"'{name}' sayti muvaffaqiyatli qo'shildi."

    def remove_web_source(self, identifier: str) -> Tuple[bool, str]:
        """Veb-saytni ro'yxatdan o'chirish (ID yoki nomi bo'yicha)."""
        ident = identifier.strip().lower()
        initial_len = len(self.web_sources)
        self.web_sources = [
            src for src in self.web_sources
            if src.get("id", "").lower() != ident and src.get("name", "").lower() != ident
        ]
        if len(self.web_sources) < initial_len:
            self.save_sources()
            logger.info(f"Sayt o'chirildi: {identifier}")
            return True, f"'{identifier}' manbasi muvaffaqiyatli o'chirildi."
        return False, f"'{identifier}' manbasi topilmadi."

    async def test_single_source(self, identifier: str) -> Dict:
        """Bitta manbani (Telegram yoki Sayt) testlash va oxirgi postlarini ko'rsatish."""
        ident = identifier.strip().lstrip("@").lower()
        target_ch = next((ch for ch in self.telegram_channels if ch.get("username", "").lower() == ident), None)
        target_web = next((w for w in self.web_sources if w.get("id", "").lower() == ident or w.get("name", "").lower() == ident), None)

        if not target_ch and not target_web:
            # Agar ro'yxatda bo'lmasa ham, to'g'ridan-to'g'ri telegram kanalini sinab ko'rish imkoni
            target_ch = {"username": ident, "name": f"@{ident}"}

        items: List[NewsItem] = []
        source_name = ""
        source_type = ""
        err_msg = ""

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                if target_ch:
                    source_name = target_ch.get("name", f"@{target_ch['username']}")
                    source_type = "Telegram Kanal"
                    items = await fetch_telegram_channel(client, target_ch["username"], source_name)
                elif target_web:
                    source_name = target_web.get("name", "Veb-sayt")
                    source_type = target_web.get("type", "rss").upper()
                    if target_web.get("type") == "rss":
                        items = await fetch_rss_source(client, target_web)
                    else:
                        items = await fetch_html_source(client, target_web)
        except Exception as e:
            err_msg = str(e)

        metro_items = []
        for it in items:
            is_rel, tags = is_metro_related(it.title, it.content)
            if is_rel:
                it.tags = tags
                metro_items.append(it)

        return {
            "success": len(err_msg) == 0,
            "error": err_msg,
            "source_name": source_name or identifier,
            "source_type": source_type,
            "total_fetched": len(items),
            "metro_found": len(metro_items),
            "sample_items": items[:5],
            "metro_items": metro_items
        }

    def load_sources(self) -> None:
        """sources.json faylidan 40 ta kanal va 40 ta saytni yuklash."""
        if not self.sources_file.exists():
            logger.error(f"Manbalar fayli topilmadi: {self.sources_file}")
            return

        try:
            with open(self.sources_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.telegram_channels = data.get("telegram_channels", [])
                self.web_sources = data.get("web_sources", [])
                logger.info(
                    f"Manbalar muvaffaqiyatli yuklandi: {len(self.telegram_channels)} ta Telegram kanal, "
                    f"{len(self.web_sources)} ta Veb-sayt (Jami: {len(self.telegram_channels) + len(self.web_sources)} ta manba)."
                )
        except Exception as e:
            logger.error(f"sources.json o'qishda xatolik: {e}")


    async def scan_all_sources(self) -> Tuple[List[NewsItem], Dict]:
        """
        Barcha 80 ta manbani asinxron parallel tekshirish va
        faqat yangi, dublikatsiz metro xabarlarini ajratib olish.
        """
        start_time = time.time()
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
        
        all_collected_items: List[NewsItem] = []

        limits = httpx.Limits(max_keepalive_connections=25, max_connections=50)
        async with httpx.AsyncClient(limits=limits, timeout=12.0) as client:
            tasks = []

            # 1. Telegram kanallar uchun vazifalar
            for ch in self.telegram_channels:
                username = ch.get("username", "")
                name = ch.get("name", username)
                tasks.append(self._bounded_fetch_telegram(semaphore, client, username, name))

            # 2. Veb-saytlar uchun vazifalar
            for src in self.web_sources:
                src_type = src.get("type", "rss")
                if src_type == "rss":
                    tasks.append(self._bounded_fetch_rss(semaphore, client, src))
                else:
                    tasks.append(self._bounded_fetch_html(semaphore, client, src))

            # Barcha 80 ta manbani parallel yurgizish
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, list):
                    all_collected_items.extend(res)

        elapsed = time.time() - start_time
        self.last_check_time = time.time()
        self.last_check_duration = elapsed

        logger.info(
            f"Barcha manbalar tekshirildi ({elapsed:.2f} soniyada). "
            f"Jami yangi olingan postlar: {len(all_collected_items)} ta."
        )

        # 3. Filtrlash va Kross-dublikat tekshiruvi
        new_metro_alerts: List[NewsItem] = []

        for item in all_collected_items:
            # 1-qadam: Avval ko'rilganmi (aniq havola bo'yicha)?
            if storage.is_seen(item.raw_id):
                continue
            
            # Kelgusi safar qayta tekshirmaslik uchun saqlab qo'yamiz
            storage.mark_seen(item.raw_id)

            # 2-qadam: Metroga tegishlimi?
            is_metro, tags = is_metro_related(item.title, item.content)
            if not is_metro:
                continue

            item.tags = tags

            # 3-qadam: Kross-manbali dublikatmi? (boshqa kanal bu voqeani yozib bo'lganmi?)
            is_dup, orig_source, sim = deduplicator.is_duplicate(
                item.title, item.content, item.source_name
            )
            if is_dup:
                logger.info(
                    f"Takroriy xabar bloklandi: '{item.title[:60]}...' "
                    f"(Asl manba: {orig_source}, o'xshashlik: {sim:.2f})"
                )
                continue

            # Yangi noyob metro hodisasi deb ro'yxatga olamiz
            deduplicator.register_event(item.title, item.content, item.source_name, item.url)
            new_metro_alerts.append(item)
            logger.info(f"🚨 YANGI METRO XABARI TOPILDI: {item.source_name} -> {item.title[:70]}")

        stats = {
            "elapsed_seconds": round(elapsed, 2),
            "total_sources": len(self.telegram_channels) + len(self.web_sources),
            "channels_count": len(self.telegram_channels),
            "web_count": len(self.web_sources),
            "raw_posts_fetched": len(all_collected_items),
            "metro_alerts_found": len(new_metro_alerts)
        }

        return new_metro_alerts, stats

    async def _bounded_fetch_telegram(self, sem, client, username, name):
        async with sem:
            return await fetch_telegram_channel(client, username, name)

    async def _bounded_fetch_rss(self, sem, client, src):
        async with sem:
            return await fetch_rss_source(client, src)

    async def _bounded_fetch_html(self, sem, client, src):
        async with sem:
            return await fetch_html_source(client, src)

source_manager = SourceManager()
