from dataclasses import dataclass
from typing import Optional, List

@dataclass
class NewsItem:
    """Yig'ilgan yangilik yoki Telegram postining universal modeli."""
    title: str
    content: str
    url: str
    source_name: str
    source_type: str  # 'telegram' yoki 'web'
    raw_id: str
    published_at: Optional[str] = None
    tags: Optional[List[str]] = None

    @property
    def full_text(self) -> str:
        return f"{self.title}\n\n{self.content}".strip()
