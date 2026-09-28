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
        self.load_sources()

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
