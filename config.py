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

# Configure standardized logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MetroMonitor")
