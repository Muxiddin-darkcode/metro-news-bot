"""
Metro Yangiliklarini AI Verifikatsiya Moduli (Dual-Provider: Gemini + OpenRouter Fallback).
AI matnni tahrirlamaydi, balki post HAQIQATDAN HAM Toshkent metrosiga tegishli ekanligini
100% aniqlikda tekshiruvchi (Classifier / Verifier) aqlli filtr sifatida ishlaydi.
Xabarlar manbaning o'z asl sarlavhasi va asl matni bilan yetkaziladi.
"""

import os
import re
import json
import html
import datetime
import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import httpx

from config import settings, format_uz_time
from parsers.base import NewsItem
from core.filter import detect_line_and_station, detect_metro_topic, is_resolution_text, is_disruption_text

logger = logging.getLogger("MetroMonitor.AIAnalyzer")


def clean_raw_news_text(text: str) -> str:
    """
    Xom matndan reklama, bot/kanal havolalari va ortiqcha shovqinlarni tozalash.
    Asl yangilik matnining o'zini toza holatda saqlab qoladi.
    """
    if not text:
        return ""

    t = text

    # 1. URL va Telegram havolalarni tozalash (http, https, t.me)
    t = re.sub(r'https?://[^\s]+', '', t)
    t = re.sub(r'(?:t\.me|telegram\.me)/[^\s]+', '', t)

    # 2. @username havolalarni tozalash
    t = re.sub(r'@[a-zA-Z0-9_]{4,}', '', t)

    # 3. Keng tarqalgan reklama, chaqiriq va ortiqcha jumlalar
    noise_patterns = [
        r'(?i)bizga\s+obuna\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)kanalga\s+a[\'’`]?zo\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)kanalimizga\s+obuna\s+b[oóõö][\'’`]?ling[:!]?',
        r'(?i)rasmiy\s+kanalimizga\s+ulan[:!]?',
        r'(?i)batafsil\s+(?:bu\s+yerda|havola\s+orqali|quyidagi|saytimizda)[:!]?',
        r'(?i)k[oóõö][\'’`]?proq\s+yangiliklar[:!]?',
        r'(?i)подписывайтесь\s+на\s+(?:наш\s+)?канал[:!]?',
        r'(?i)читайте\s+(?:также|подробнее)[:!]?',
        r'(?i)barcha\s+huquqlar\s+himoyalangan',
        r'(?i)все\s+права\s+защищены',
        r'(?i)foto\s*:\s*[^\n]+',
        r'(?i)video\s*:\s*[^\n]+',
        r'(?i)manba\s*:\s*[^\n]+',
        r'(?i)reklama\s*:\s*[^\n]+',
        r'(?i)реклама\s*:\s*[^\n]+'
    ]
    for pat in noise_patterns:
        t = re.sub(pat, '', t)

    # 4. Ortiqcha bo'shliqlar va bo'sh qatorlarni normallashtirish
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n\n', t)
    return t.strip()


def safe_truncate_words(text: str, max_len: int) -> str:
    """Matnni so'zlarni chala qoldirmasdan, butun so'z bo'yicha toza qisqartirish."""
    if not text or len(text) <= max_len:
        return text.strip()
    truncated = text[:max_len]
    last_space = max(truncated.rfind(" "), truncated.rfind("\n"))
    if last_space > int(max_len * 0.6):
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,;:-—") + "..."


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
    """Matnda krill harflari bor-yo'qligini tekshirish."""
    return bool(re.search(r'[а-яА-ЯёЁўЎқҚғҒҳҲ]', text))

def cyrillic_to_latin(text: str) -> str:
    """Krillcha matnni O'zbek lotin alifbosiga o'tkazish."""
    if not text:
        return ""
    res = []
    for char in text:
        res.append(CYRILLIC_TO_LATIN_MAP.get(char, char))
    return "".join(res)

def normalize_model_name(model: str, default_model: str) -> str:
    """Model nomlarini OpenRouter va Gemini talablariga moslashtirish."""
    m = model.strip() if model else ""
    if not m:
        return default_model
    if "llama-3.3-70b" in m.lower():
        if "meta-llama/" not in m.lower():
            return "meta-llama/llama-3.3-70b-instruct"
    if "gemini" in m.lower() and ("3.5" in m.lower() or "2.0-flash-exp" in m.lower()):
        return "gemini-1.5-flash"
    return m


METRO_AI_VERIFIER_PROMPT = """Sen Toshkent Metropoliteni yangiliklari bo'yicha aqlli verifikatorisan.
Sening asosiy vazifalaring:
1. Berilgan post HAQIQATDAN HAM Toshkent metrosiga tegishli ekanligini 100% ishonch bilan tekshirish (is_metro: true/false).
2. Qaysi yo'nalish (liniya) va bekatga tegishli ekanligini aniqlash.
3. Yangilik mavzusini aniqlash.
4. Agar post nosozlik yoki to'xtashdan so'ng harakat qayta tiklangani haqida bo'lsa, is_resolution: true deb belgilash.

RAD ETILADIGAN SOXTA POSTLAR (is_metro: false):
1. Ko'chmas mulk va ijara reklamalari: "metro yaqinida kvartira sotiladi", "metroga 5 daqiqalik masofa", "ijara", "narxi $...".
2. Chet el metrosi: Moskva, Sankt-Peterburg, Parij, Pekin, Nyu-York metrosi (agar Toshkentga aloqasi bo'lmasa).
3. Sport va yengil atletika: "100 metr masofaga yugurish", "200 metr suzish", medallar, marafon.
4. Boshqa ma'nolar: "Metro" savdo markazi, metrologiya, santimetr.
5. Shunchaki shahar xabarlarida "metro" so'zi joylashuv mo'ljali sifatida tasodifan tilga olingan bo'lsa (masalan "Minor bekati yaqinidagi kafeda yong'in").

HAQIQIY METRO POSTLARI (is_metro: true):
Toshkent metrosining o'zi, poyezdlari, yo'lovchilari, bekatlardagi holatlar, harakat to'xtashi, intervallar, ta'mirlash, yangi vagonlar va rasmiy axborotlar.

LINIYALAR:
- 🔴 Chilonzor yo'li
- 🔵 O'zbekiston yo'li
- 🟢 Yunusobod yo'li
- 🟣 Yerusti halqa yo'li

FAQAT QUYIDAGI IXCHAM JSON FORMATIDA JAVOB BER:
{
  "is_metro": true | false,
  "confidence": 0.95,
  "line": "🔴 Chilonzor yo'li | 🔵 O'zbekiston yo'li | 🟢 Yunusobod yo'li | 🟣 Yerusti halqa yo'li | null",
  "station": "Bekat nomi | null",
  "topic": "Harakat va oraliq intervallar | To'lov va tariflar | Yangi poyezdlar | Rasmiy bayonot | Umumiy yangilik",
  "is_resolution": true | false,
  "reason": "Qisqa sabab (1 jumla)"
}
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": (
            "Sarlavha: Chilonzor yo'lida poyezdlar harakati vaqtincha to'xtatildi\n"
            "Matn: Novza bekatida poyezdda yuzaga kelgan texnik nosozlik sababli harakat 15 daqiqaga to'xtab qoldi."
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "is_metro": True,
            "confidence": 0.99,
            "line": "🔴 Chilonzor yo'li",
            "station": "📌 Novza bekati",
            "topic": "Harakat va oraliq intervallar",
            "is_resolution": False,
            "reason": "Toshkent metrosi Novza bekatida poyezd to'xtab qolganligi haqida haqiqiy voqea."
        }, ensure_ascii=False)
    },
    {
        "role": "user",
        "content": (
            "Sarlavha: Chilonzor yo'lida poyezdlar harakati to'liq tiklandi\n"
            "Matn: Novza bekatidagi nosozlik bartaraf etildi, poyezdlar amaldagi jadval bo'yicha harakatlanmoqda."
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "is_metro": True,
            "confidence": 0.99,
            "line": "🔴 Chilonzor yo'li",
            "station": "📌 Novza bekati",
            "topic": "Harakat qayta tiklandi",
            "is_resolution": True,
            "reason": "Nosozlik bartaraf etilib, harakat qayta tiklangani haqidagi rasmiy xabar."
        }, ensure_ascii=False)
    },
    {
        "role": "user",
        "content": (
            "Sarlavha: Chilonzor metrosiga 3 daqiqalik masofada 3 xonali kvartira ijaraga beriladi\n"
            "Matn: Remonti yevro, barcha sharoitlari bor. Narxi 500 dollar. Murojaat uchun: +998901234567"
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "is_metro": False,
            "confidence": 0.99,
            "line": None,
            "station": None,
            "topic": None,
            "is_resolution": False,
            "reason": "Ko'chmas mulk va ijara reklamasi."
        }, ensure_ascii=False)
    },
    {
        "role": "user",
        "content": (
            "Sarlavha: Toshkent metrosiga yangi 5 vagonli zamonaviy poyezdlar olib kelinadi\n"
            "Matn: Metropoliten rahbariyati xabar berishicha, 2027-yilgacha tarkiblarning 80 foizi 5 vagonli tizimga o'tkaziladi."
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "is_metro": True,
            "confidence": 0.98,
            "line": None,
            "station": None,
            "topic": "Yangi poyezdlar va modernizatsiya",
            "is_resolution": False,
            "reason": "Toshkent metropoliteni poyezdlari yangilanishi haqidagi yangilik."
        }, ensure_ascii=False)
    }
]


def format_original_news_html(
    item: NewsItem,
    badge: str = "🚇 METRO XABARI",
    result: Optional['AIAnalysisResult'] = None
) -> str:
    """Asl manba sarlavhasi va matnini liniya, bekat va mavzu bilan toza HTML formatida tayyorlash."""
    now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
    if item.published_at:
        try:
            pub_str = item.published_at.replace("Z", "+00:00")
            pub_dt = datetime.datetime.fromisoformat(pub_str)
            now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
        except Exception:
            pass

    clean_title = html.escape(item.title.strip(), quote=False)
    clean_source = html.escape(item.source_name.strip(), quote=False)

    raw_content = clean_raw_news_text(item.content.strip())
    content_safe = html.escape(raw_content, quote=False)

    if len(content_safe) > 850:
        content_safe = safe_truncate_words(content_safe, 850)

    tags_str = " ".join(item.tags) if item.tags else "#metro #toshkent"

    # Liniya, bekat va mavzu sarlavhasini shakllantirish
    line_val = getattr(result, "line", "") if result else ""
    station_val = getattr(result, "station", "") if result else ""
    topic_val = getattr(result, "topic", "") if result else ""
    is_res = getattr(result, "is_resolution", False) if result else False

    if not line_val and not station_val:
        full_text = f"{item.title} {item.content}"
        line_val, station_val = detect_line_and_station(full_text)
        if not topic_val:
            topic_val = detect_metro_topic(full_text)
        if not is_res:
            is_res = is_resolution_text(full_text)

    header_lines = ["🚇 <b>TOSHKENT METROSI XABARI</b>"]
    loc_parts = []
    if line_val:
        loc_parts.append(f"<b>{line_val}</b>")
    if station_val:
        loc_parts.append(f"<b>{station_val}</b>")

    if loc_parts:
        header_lines.append(" | ".join(loc_parts))

    if is_res:
        header_lines.append("🟢 <b>HARAKAT QAYTA TIKLANDI</b>")
    elif topic_val:
        header_lines.append(f"📂 <b>Mavzu:</b> {topic_val}")

    header_block = "\n".join(header_lines)

    msg = f"{header_block}\n\n📌 <b>{clean_title}</b>\n\n"
    if content_safe and content_safe.lower() != clean_title.lower():
        msg += f"{content_safe}\n\n"

    msg += (
        f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}\n"
        f"🔍 <b>Teglar:</b> <code>{html.escape(tags_str)}</code>"
    )
    return msg


def format_original_news_caption(
    item: NewsItem,
    badge: str = "🚇 METRO XABARI",
    result: Optional['AIAnalysisResult'] = None
) -> str:
    """Fotosuratlar tagiga qo'yiladigan asl manba matni (1024 belgi chegarasi bilan)."""
    now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
    if item.published_at:
        try:
            pub_str = item.published_at.replace("Z", "+00:00")
            pub_dt = datetime.datetime.fromisoformat(pub_str)
            now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
        except Exception:
            pass

    clean_title = html.escape(item.title.strip(), quote=False)
    clean_source = html.escape(item.source_name.strip(), quote=False)

    raw_content = clean_raw_news_text(item.content.strip())
    content_safe = html.escape(raw_content, quote=False)

    if len(content_safe) > 550:
        content_safe = safe_truncate_words(content_safe, 550)

    line_val = getattr(result, "line", "") if result else ""
    station_val = getattr(result, "station", "") if result else ""
    topic_val = getattr(result, "topic", "") if result else ""
    is_res = getattr(result, "is_resolution", False) if result else False

    if not line_val and not station_val:
        full_text = f"{item.title} {item.content}"
        line_val, station_val = detect_line_and_station(full_text)
        if not topic_val:
            topic_val = detect_metro_topic(full_text)
        if not is_res:
            is_res = is_resolution_text(full_text)

    header_lines = ["🚇 <b>TOSHKENT METROSI XABARI</b>"]
    loc_parts = []
    if line_val:
        loc_parts.append(f"<b>{line_val}</b>")
    if station_val:
        loc_parts.append(f"<b>{station_val}</b>")

    if loc_parts:
        header_lines.append(" | ".join(loc_parts))

    if is_res:
        header_lines.append("🟢 <b>HARAKAT QAYTA TIKLANDI</b>")
    elif topic_val:
        header_lines.append(f"📂 <b>Mavzu:</b> {topic_val}")

    header_block = "\n".join(header_lines)

    msg = f"{header_block}\n\n📌 <b>{clean_title}</b>\n\n"
    if content_safe and content_safe.lower() != clean_title.lower():
        msg += f"{content_safe}\n\n"

    msg += f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}"
    return msg


@dataclass
class AIAnalysisResult:
    """AI verifikatsiyasining natijasi."""
    success: bool
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
    reason: str = ""
    provider_used: str = "Mahalliy filtr"
    model_name: str = ""
    error_message: Optional[str] = None

    def to_telegram_html(self, item: NewsItem) -> str:
        """Asl sarlavha va matn bilan toza xabar matni."""
        return format_original_news_html(item, badge=self.badge, result=self)

    def to_telegram_caption_html(self, item: NewsItem) -> str:
        """Fotosurat ostiga asl matn bilan tayyorlangan caption."""
        return format_original_news_caption(item, badge=self.badge, result=self)


class AIAnalyzer:
    """
    Toshkent Metropoliteni yangiliklarini tekshiruvchi AI xizmati.
    Asosiy vazifasi: Post haqiqatan ham metroga tegishlimi yoki yo'qligini aniqlash.
    Matnni o'zgartirmaydi, original faktlarni aslicha saqlaydi.
    """

    def __init__(self):
        self.gemini_api_key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")).strip()
        gem_m = (settings.GEMINI_MODEL or os.environ.get("GEMINI_MODEL", "")).strip()
        self.gemini_model = normalize_model_name(gem_m, "gemini-1.5-flash")

        self.openrouter_api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
        open_m = (settings.OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "")).strip()
        self.openrouter_model = normalize_model_name(open_m, "meta-llama/llama-3.3-70b-instruct")

        self.timeout = getattr(settings, "AI_TIMEOUT", 15.0)

    def reload_keys(self) -> None:
        """Sozlamalardan kalitlarni qayta yuklash."""
        self.gemini_api_key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")).strip()
        gem_m = (settings.GEMINI_MODEL or os.environ.get("GEMINI_MODEL", "")).strip()
        self.gemini_model = normalize_model_name(gem_m, "gemini-1.5-flash")

        self.openrouter_api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
        open_m = (settings.OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "")).strip()
        self.openrouter_model = normalize_model_name(open_m, "meta-llama/llama-3.3-70b-instruct")

    def get_status_info(self) -> Dict[str, Any]:
        """AI provayderlarining joriy holati."""
        self.reload_keys()
        return {
            "ai_enabled": settings.AI_ENABLED,
            "gemini_configured": bool(self.gemini_api_key),
            "gemini_model": self.gemini_model,
            "openrouter_configured": bool(self.openrouter_api_key),
            "openrouter_model": self.openrouter_model,
        }

    async def verify_metro_news(self, item: NewsItem) -> AIAnalysisResult:
        """Postning Toshkent metrosiga haqiqatan tegishli ekanligini AI orqali tekshirish."""
        return await self.analyze_news(item)

    async def analyze_news(self, item: NewsItem) -> AIAnalysisResult:
        """
        Yangilikni tekshirish:
        1. Agar AI o'chirilgan yoki kalitlar kiritilmagan bo'lsa -> Mahalliy filtrga tayanadi (is_metro: True).
        2. Gemini API orqali tezkor tekshiruv (is_metro: True/False).
        3. Agar Gemini xato bersa -> OpenRouter zaxirasiga o'tadi.
        """
        self.reload_keys()

        if not settings.AI_ENABLED or (not self.gemini_api_key and not self.openrouter_api_key):
            logger.debug("AI tekshiruv o'chiq yoki kalitlar yo'q, mahalliy filtr natijasi qabul qilinmoqda.")
            return self._build_local_result(item)

        cleaned_title = clean_raw_news_text(item.title)
        cleaned_content = clean_raw_news_text(item.content)

        user_prompt = (
            f"Sarlavha: {cleaned_title}\n"
            f"Matn:\n{cleaned_content[:1500]}"
        )

        # 1-urinish: Google Gemini API
        if self.gemini_api_key:
            try:
                res = await self._call_gemini_api(user_prompt, item)
                if res:
                    res.provider_used = "Google Gemini AI"
                    res.model_name = self.gemini_model
                    logger.info(f"Gemini verifikatsiyasi: is_metro={res.is_metro}, sabab: {res.reason}")
                    return res
            except Exception as e:
                logger.warning(f"Gemini API xatoligi: {e}. OpenRouter zaxirasiga o'tilmoqda...")

        # 2-urinish: OpenRouter API Fallback
        if self.openrouter_api_key:
            try:
                res = await self._call_openrouter_api(user_prompt, item)
                if res:
                    res.provider_used = "OpenRouter AI"
                    res.model_name = self.openrouter_model
                    logger.info(f"OpenRouter verifikatsiyasi: is_metro={res.is_metro}, sabab: {res.reason}")
                    return res
            except Exception as e:
                logger.warning(f"OpenRouter API xatoligi: {e}.")

        # 3-urinish: Mahalliy tasdiq
        return self._build_local_result(item)

    async def _call_gemini_api(self, user_prompt: str, item: NewsItem) -> Optional[AIAnalysisResult]:
        """Google Gemini REST API ga murojaat."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        )

        contents = []
        for example in FEW_SHOT_EXAMPLES:
            role = "user" if example["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": example["content"]}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": user_prompt}]
        })

        payload = {
            "system_instruction": {
                "parts": [{"text": METRO_AI_VERIFIER_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 120,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 429:
                raise RuntimeError("Gemini API Rate limit (429)")
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API HTTP {resp.status_code}: {resp.text[:120]}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini javob bermadi.")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini javob matni topilmadi.")

            raw_text = parts[0].get("text", "")
            return self._parse_json_response(raw_text, item)

    async def _call_openrouter_api(self, user_prompt: str, item: NewsItem) -> Optional[AIAnalysisResult]:
        """OpenRouter REST API ga murojaat."""
        url = "https://openrouter.ai/api/v1/chat/completions"

        messages = [{"role": "system", "content": METRO_AI_VERIFIER_PROMPT}]
        for example in FEW_SHOT_EXAMPLES:
            messages.append({"role": example["role"], "content": example["content"]})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.openrouter_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 120
        }

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": "https://tashmetro-bot.local",
            "X-Title": "Tashkent Metro Monitor",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                raise RuntimeError("OpenRouter Rate limit (429)")
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:120]}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenRouter bo'sh javob qaytardi.")

            content = choices[0].get("message", {}).get("content", "")
            return self._parse_json_response(content, item)

    def _parse_json_response(self, text: str, item: NewsItem) -> AIAnalysisResult:
        """AI JSON javobini xavfsiz o'qish."""
        clean_text = text.strip()
        if "```json" in clean_text:
            m = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
            if m:
                clean_text = m.group(1).strip()
        elif "```" in clean_text:
            m = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
            if m:
                clean_text = m.group(1).strip()

        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_text = clean_text[first_brace:last_brace + 1]

        data = {}
        try:
            data = json.loads(clean_text)
        except Exception:
            is_metro = "true" in clean_text.lower() and "false" not in clean_text.lower()
            data = {"is_metro": is_metro, "confidence": 0.8, "reason": "Matnli parsing"}

        is_metro = bool(data.get("is_metro", True))
        confidence = float(data.get("confidence", 0.9))
        ai_line = str(data.get("line") or "").strip()
        ai_station = str(data.get("station") or "").strip()
        ai_topic = str(data.get("topic") or "").strip()
        ai_is_res = bool(data.get("is_resolution", False))
        reason = str(data.get("reason", "")).strip()

        # Mahalliy tahlil bilan boyitish (agar AI bo'sh qoldirgan bo'lsa)
        full_text = f"{item.title} {item.content}"
        loc_line, loc_station = detect_line_and_station(full_text)
        loc_topic = detect_metro_topic(full_text)
        loc_res = is_resolution_text(full_text)

        final_line = ai_line or loc_line or ""
        final_station = ai_station or loc_station or ""
        final_topic = ai_topic or loc_topic or "Toshkent Metropoliteni yangiligi"
        final_res = ai_is_res or loc_res

        badge = "🟢 HARAKAT QAYTA TIKLANDI" if final_res else (final_line or "🚇 METRO XABARI")

        return AIAnalysisResult(
            success=True,
            is_metro=is_metro,
            confidence=confidence,
            category="RESOLUTION" if final_res else "NEWS",
            badge=badge,
            line=final_line,
            station=final_station,
            topic=final_topic,
            is_resolution=final_res,
            title=item.title.strip(),
            summary=clean_raw_news_text(item.content.strip())[:350],
            reason=reason or "AI orqali tasdiqlandi"
        )

    def _build_local_result(self, item: NewsItem) -> AIAnalysisResult:
        """Mahalliy aqlli qoidalar asosidagi tezkor tasdiq (liniya, bekat va mavzuni aniqlash)."""
        full_text = f"{item.title} {item.content}"
        line, station = detect_line_and_station(full_text)
        topic = detect_metro_topic(full_text)
        is_res = is_resolution_text(full_text)

        badge = "🟢 HARAKAT QAYTA TIKLANDI" if is_res else (line or "🚇 METRO XABARI")

        return AIAnalysisResult(
            success=True,
            is_metro=True,
            confidence=1.0,
            category="RESOLUTION" if is_res else "NEWS",
            badge=badge,
            line=line or "",
            station=station or "",
            topic=topic,
            is_resolution=is_res,
            title=item.title.strip(),
            summary=clean_raw_news_text(item.content.strip())[:350],
            reason="Mahalliy qat'iy qoidalar orqali tasdiqlandi",
            provider_used="Mahalliy filtr"
        )

    def _build_fallback_result(self, item: NewsItem, reason: str = "") -> AIAnalysisResult:
        """Moslashuvchan fallback natija (lotin alifbosiga o'tkazilgan)."""
        res = self._build_local_result(item)
        if contains_cyrillic(res.title):
            res.title = cyrillic_to_latin(res.title)
        if contains_cyrillic(res.summary):
            res.summary = cyrillic_to_latin(res.summary)
        if reason:
            res.reason = reason
        return res


ai_analyzer = AIAnalyzer()
