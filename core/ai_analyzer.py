"""
Toshkent Metropoliteni Xabarlarini Tahlil Qilish Moduli (100% Mahalliy, AI'siz).
Eski importlar buzilmasligi uchun core.formatter ga asoslangan holda 0ms da ishlaydi.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from parsers.base import NewsItem
from core.formatter import (
    clean_raw_news_text,
    safe_truncate_words,
    format_metro_alert,
    format_original_news_html,
    format_original_news_caption,
    FormattedAlert
)
from core.filter import (
    detect_line_and_station,
    detect_metro_topic,
    is_resolution_text,
    is_disruption_text
)

# Krill harflari va transliteratsiya
CYRILLIC_TO_LATIN_MAP = {
    'А': 'A', 'а': 'a', 'Б': 'B', 'б': 'b', 'В': 'V', 'в': 'v',
    'Г': 'G', 'г': 'g', 'Д': 'D', 'д': 'd', 'Ё': 'Yo', 'ё': 'yo',
    'Ж': 'J', 'ж': 'j', 'З': 'Z', 'з': 'z', 'И': 'I', 'и': 'i',
    'Й': 'Y', 'й': 'y', 'К': 'K', 'к': 'k', 'Л': 'L', 'л': 'l',
    'М': 'M', 'м': 'm', 'Н': 'N', 'н': 'n', 'О': 'O', 'о': 'o',
    'П': 'P', 'п': 'p', 'Р': 'R', 'р': 'r', 'С': 'S', 'с': 's',
    'Т': 'T', 'т': 't', 'У': 'U', 'у': 'u', 'Ф': 'F', 'ф': 'f',
    'Х': 'X', 'х': 'x', 'Ц': 'Ts', 'ц': 'ts', 'Ч': 'Ch', 'ч': 'ch',
    'Ш': 'Sh', 'ш': 'sh', 'Щ': 'Sh', 'щ': 'sh', 'Ъ': "'", 'ъ': "'",
    'Ы': 'I', 'ы': 'i', 'Ь': '', 'ь': '', 'Э': 'E', 'э': 'e', 'Е': 'E', 'е': 'e',
    'Ю': 'Yu', 'ю': 'yu', 'Я': 'Ya', 'я': 'ya',
    'Ў': "O'", 'ў': "o'", 'Ғ': "G'", 'ғ': "g'", 'Қ': "Q", 'қ': "q", 'Ҳ': "H", 'ҳ': "h"
}


def contains_cyrillic(text: str) -> bool:
    import re
    return bool(re.search(r'[а-яА-ЯёЁўЎқҚғҒҳҲ]', text))


def cyrillic_to_latin(text: str) -> str:
    if not text:
        return ""
    res = [CYRILLIC_TO_LATIN_MAP.get(char, char) for char in text]
    return "".join(res)


def normalize_model_name(model: str, default_model: str) -> str:
    m = model.strip() if model else ""
    if not m:
        return default_model
    if "llama-3.3-70b" in m.lower():
        if "meta-llama/" not in m.lower():
            return "meta-llama/llama-3.3-70b-instruct"
    if "gemini" in m.lower() and ("3.5" in m.lower() or "2.0-flash-exp" in m.lower()):
        return "gemini-1.5-flash"
    return m


@dataclass
class AIAnalysisResult:
    """Moslashuvchan natija modeli (100% mahalliy tahlil)."""
    success: bool = True
    is_metro: bool = True
    confidence: float = 1.0
    category: str = "NEWS"
    badge: str = "🚇 METRO XABARI"
    line: str = ""
    station: str = ""
    topic: str = ""
    is_resolution: bool = False
    title: str = ""
    summary: str = ""
    station_and_line: str = ""
    incident_status: str = ""
    key_points: List[str] = field(default_factory=list)
    advice: str = ""
    reason: str = "Mahalliy deterministik filtr tasdiqladi"
    provider_used: str = "Mahalliy tezyurar filtr"
    model_name: str = "local-engine"
    error_message: Optional[str] = None

    def to_telegram_html(self, item: NewsItem) -> str:
        return format_metro_alert(item).html_text

    def to_telegram_caption_html(self, item: NewsItem) -> str:
        return format_metro_alert(item).caption_text


class LocalMetroAnalyzer:
    """100% mahalliy tezkor tahlilchi (AI o'rnida ishlaydi)."""
    def __init__(self):
        self.gemini_api_key = ""
        self.openrouter_api_key = ""

    def get_status_info(self) -> Dict[str, Any]:
        return {
            "ai_enabled": False,
            "engine": "100% Mahalliy Deterministik Dvigatel",
            "latency_ms": 0.001
        }

    async def verify_metro_news(self, item: NewsItem) -> AIAnalysisResult:
        return self._build_local_result(item)

    async def analyze_news(self, item: NewsItem) -> AIAnalysisResult:
        return self._build_local_result(item)

    def _build_local_result(self, item: NewsItem) -> AIAnalysisResult:
        alert = format_metro_alert(item)
        return AIAnalysisResult(
            success=True,
            is_metro=True,
            confidence=1.0,
            category="RESOLUTION" if alert.is_resolution else "NEWS",
            badge=alert.badge,
            line=alert.line,
            station=alert.station,
            topic=alert.topic,
            is_resolution=alert.is_resolution,
            title=item.title.strip(),
            summary=clean_raw_news_text(item.content.strip())[:350],
            reason="Mahalliy tezyurar filtr orqali tasdiqlandi",
            provider_used="Mahalliy filtr"
        )

    def _build_fallback_result(self, item: NewsItem, reason: str = "") -> AIAnalysisResult:
        res = self._build_local_result(item)
        if contains_cyrillic(res.title):
            res.title = cyrillic_to_latin(res.title)
        if contains_cyrillic(res.summary):
            res.summary = cyrillic_to_latin(res.summary)
        if reason:
            res.reason = reason
        return res


ai_analyzer = LocalMetroAnalyzer()
