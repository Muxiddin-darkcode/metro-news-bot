import json
import logging
from pathlib import Path
from typing import Set
from config import settings

logger = logging.getLogger("MetroMonitor.Storage")

class StorageManager:
    """
    Yengil, ma'lumotlar bazasisiz (No-DB) saqlovchi.
    seen_posts.json fayli orqali xabarlarning unikal havolalari/ID larini saqlaydi.
    Xotirada (In-memory Set) orqali O(1) tezlikda tekshiradi.
    """
    def __init__(self, filepath: Path = settings.SEEN_POSTS_FILE, max_size: int = settings.MAX_SEEN_CACHE_SIZE):
        self.filepath = filepath
        self.max_size = max_size
        self._seen_urls: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._seen_urls = set(data[-self.max_size:])
                        logger.info(f"Keshdan {len(self._seen_urls)} ta avvalgi xabar yuklandi.")
            except Exception as e:
                logger.error(f"seen_posts.json faylini o'qishda xatolik: {e}")
                self._seen_urls = set()
        else:
            self._save()

    def _save(self) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            # Oxirgi max_size tasi saqlanadi
            items_to_save = list(self._seen_urls)[-self.max_size:]
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(items_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"seen_posts.json fayliga yozishda xatolik: {e}")

    def is_seen(self, url_or_id: str) -> bool:
        """Xabar avval tekshirilganmi yoki yo'qligini aniqlaydi."""
        return url_or_id in self._seen_urls

    def mark_seen(self, url_or_id: str) -> None:
        """Xabarni ko'rilgan deb belgilaydi va faylga yozadi."""
        if url_or_id not in self._seen_urls:
            self._seen_urls.add(url_or_id)
            if len(self._seen_urls) > self.max_size * 1.2:
                # Hajm oshib ketsa, qisqartirish
                self._seen_urls = set(list(self._seen_urls)[-self.max_size:])
            self._save()

    @property
    def count(self) -> int:
        return len(self._seen_urls)

storage = StorageManager()
