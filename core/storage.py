import json
import logging
import asyncio
from pathlib import Path
from typing import Iterable
from collections import OrderedDict
from config import settings

logger = logging.getLogger("MetroMonitor.Storage")

class StorageManager:
    """
    Yengil, ultra-yuqori unumdor No-DB kesh boshqaruvchisi.
    Xotirada (OrderedDict) orqali O(1) tezlikda tekshiradi va O(1) FIFO evakuatsiyani ta'minlaydi.
    Faylga yozish disk I/O ni bloklamasligi uchun batch (to'plam) va async usulida amalga oshiriladi.
    """
    def __init__(self, filepath: Path = settings.SEEN_POSTS_FILE, max_size: int = settings.MAX_SEEN_CACHE_SIZE):
        self.filepath = filepath
        self.max_size = max_size
        self._seen_urls: OrderedDict[str, None] = OrderedDict()
        self._dirty: bool = False
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._seen_urls = OrderedDict((k, None) for k in data[-self.max_size:])
                        logger.info(f"Keshdan {len(self._seen_urls)} ta avvalgi xabar yuklandi.")
            except Exception as e:
                logger.error(f"seen_posts.json faylini o'qishda xatolik: {e}")
                self._seen_urls = OrderedDict()
        else:
            self._save()

    def _save(self) -> None:
        """Sinxron saqlash (zarur bo'lganda chaqiriladi)."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            items_to_save = list(self._seen_urls.keys())[-self.max_size:]
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(items_to_save, f, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            logger.error(f"seen_posts.json fayliga yozishda xatolik: {e}")

    def save(self) -> None:
        """Agar kesh o'zgargan bo'lsa diskka yozish."""
        if self._dirty:
            self._save()

    async def save_async(self) -> None:
        """Asinxron oqimda diskka yozish (event loopni zarracha qotirmaydi)."""
        if self._dirty:
            await asyncio.to_thread(self._save)

    def is_seen(self, url_or_id: str) -> bool:
        """Xabar avval tekshirilganmi yoki yo'qligini O(1) tezlikda aniqlaydi."""
        return url_or_id in self._seen_urls

    def mark_seen(self, url_or_id: str, auto_save: bool = False) -> None:
        """
        Xabarni ko'rilgan deb belgilaydi.
        O(1) True FIFO evakuatsiya: eng eski xabarlar doimiy navbat bilan tozalanadi.
        """
        if url_or_id not in self._seen_urls:
            self._seen_urls[url_or_id] = None
            self._dirty = True
            if len(self._seen_urls) > self.max_size:
                self._seen_urls.popitem(last=False)
            if auto_save:
                self._save()

    def mark_seen_batch(self, urls: Iterable[str]) -> None:
        """Ko'plab havolalarni birdaniga xotiraga kiritish (O(1) FIFO evakuatsiya)."""
        new_items = False
        for u in urls:
            if u not in self._seen_urls:
                self._seen_urls[u] = None
                new_items = True
                if len(self._seen_urls) > self.max_size:
                    self._seen_urls.popitem(last=False)
        if new_items:
            self._dirty = True

    @property
    def count(self) -> int:
        return len(self._seen_urls)

    def clear(self) -> int:
        """Keshdagi barcha ko'rilgan xabarlar tarixini tozalash."""
        cleared_count = len(self._seen_urls)
        self._seen_urls.clear()
        self._dirty = True
        self._save()
        logger.info(f"Storage keshi tozalandi ({cleared_count} ta element o'chirildi).")
        return cleared_count

storage = StorageManager()

