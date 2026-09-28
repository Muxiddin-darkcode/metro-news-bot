import os
import logging
from pathlib import Path
from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    ADMIN_IDS: str = "123456789,987654321"
    CHECK_INTERVAL_SECONDS: int = 60
    MAX_CONCURRENT_REQUESTS: int = 15
    SIMILARITY_THRESHOLD: float = 0.65
    
    # Path settings
    SOURCES_FILE: Path = DATA_DIR / "sources.json"
    SEEN_POSTS_FILE: Path = DATA_DIR / "seen_posts.json"
    SEEN_FINGERPRINTS_FILE: Path = DATA_DIR / "seen_fingerprints.json"
    
    # Parsing limits
    MAX_SEEN_CACHE_SIZE: int = 2500
    REQUEST_TIMEOUT: float = 10.0

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def admin_id_list(self) -> List[int]:
        ids = []
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

settings = Settings()

from datetime import datetime, timezone, timedelta

# O'zbekiston vaqti (Toshkent: UTC+5)
# Har qanday server (Render, Railway, Docker, VPS) da aniq O'zbekiston vaqtini ta'minlaydi
UZ_TZ = timezone(timedelta(hours=5))

def uz_now() -> datetime:
    """O'zbekiston (Toshkent: UTC+5) bo'yicha joriy vaqt."""
    return datetime.now(UZ_TZ)

def format_uz_time(dt_or_timestamp=None, fmt: str = "%H:%M:%S | %d.%m.%Y") -> str:
    """
    O'zbekiston vaqti (UTC+5) bo'yicha chiroyli formatda vaqt matnini qaytaradi.
    dt_or_timestamp: float (timestamp), datetime ob'ekti yoki None (joriy vaqt).
    """
    if dt_or_timestamp is None:
        dt = uz_now()
    elif isinstance(dt_or_timestamp, (int, float)):
        dt = datetime.fromtimestamp(dt_or_timestamp, tz=UZ_TZ)
    elif isinstance(dt_or_timestamp, datetime):
        if dt_or_timestamp.tzinfo is None:
            dt = dt_or_timestamp.replace(tzinfo=timezone.utc).astimezone(UZ_TZ)
        else:
            dt = dt_or_timestamp.astimezone(UZ_TZ)
    else:
        return "Noma'lum"
    return dt.strftime(fmt)

class UzFormatter(logging.Formatter):
    """Loglarda har doim O'zbekiston vaqtini (UTC+5) ko'rsatuvchi formatlovchi."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=UZ_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

# Configure standardized logging with Uzbekistan Time
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(UzFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_log_handler]
)
logger = logging.getLogger("MetroMonitor")

