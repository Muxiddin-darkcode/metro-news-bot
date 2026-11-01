"""
Metro Yangiliklarini AI Tahlil Qilish Moduli (Dual-Provider: Gemini + OpenRouter Fallback).
Toshkent Metropoliteni yangiliklarini professional transport tahlilchisi sifatida
o'rganib, yo'lovchilar uchun eng aniq, xolis, lo'nda va chiroyli matn tayyorlaydi.
"""

import os
import re
import json
import html
import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import httpx

from config import settings, format_uz_time
from parsers.base import NewsItem

logger = logging.getLogger("MetroMonitor.AIAnalyzer")


def clean_raw_news_text(text: str) -> str:
    """
    Xom matndan reklama, bot/kanal havolalari va ortiqcha shovqinlarni tozalash.
    AI faqat asl faktlarga diqqat qaratishi uchun zamin yaratadi.
    """
    if not text:
        return ""

    t = text

    # 1. URL va Telegram havolalarni tozalash (http, https, t.me)
    t = re.sub(r'https?://[^\s]+', '', t)
    t = re.sub(r'(?:t\.me|telegram\.me)/[^\s]+', '', t)

    # 2. @username havolalarni tozalash
    t = re.sub(r'@[a-zA-Z0-9_]{4,}', '', t)

    # 3. Keng tarqalgan reklama, chaqiriq va ortiqcha jumlalar (O'zbek va Rus tillarida)
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
    """Matnni so'zlarni chala qoldirmasdan, butun so'z va tugallangan jumla bo'yicha toza qisqartirish."""
    if not text or len(text) <= max_len:
        return text.strip()
    truncated = text[:max_len]
    last_space = max(truncated.rfind(" "), truncated.rfind("\n"))
    if last_space > int(max_len * 0.6):
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,;:-—") + "."


CYRILLIC_TO_LATIN_MAP = {
    'А': 'A', 'а': 'a',
    'Б': 'B', 'б': 'b',
    'В': 'V', 'в': 'v',
    'Г': 'G', 'г': 'g',
    'Д': 'D', 'д': 'd',
    'Ё': 'Yo', 'ё': 'yo',
    'Ж': 'J', 'ж': 'j',
    'З': 'Z', 'з': 'z',
    'И': 'I', 'и': 'i',
    'Й': 'Y', 'й': 'y',
    'К': 'K', 'к': 'k',
    'Л': 'L', 'л': 'l',
    'М': 'M', 'м': 'm',
    'Н': 'N', 'н': 'n',
    'О': 'O', 'о': 'o',
    'П': 'P', 'п': 'p',
    'Р': 'R', 'р': 'r',
    'С': 'S', 'с': 's',
    'Т': 'T', 'т': 't',
    'У': 'U', 'у': 'u',
    'Ф': 'F', 'ф': 'f',
    'Х': 'X', 'х': 'x',
    'Ц': 'Ts', 'ц': 'ts',
    'Ч': 'Ch', 'ч': 'ch',
    'Ш': 'Sh', 'ш': 'sh',
    'Щ': 'Sh', 'щ': 'sh',
    'Ъ': "'", 'ъ': "'",
    'Ы': 'I', 'ы': 'i',
    'Ь': '', 'ь': '',
    'Э': 'E', 'э': 'e',
    'Ю': 'Yu', 'ю': 'yu',
    'Я': 'Ya', 'я': 'ya',
    'Ў': "O'", 'ў': "o'",
    'Ғ': "G'", 'ғ': "g'",
    'Қ': 'Q', 'қ': 'q',
    'Ҳ': 'H', 'ҳ': 'h',
}


def contains_cyrillic(text: str) -> bool:
    """Matnda krill harflari bor-yo'qligini tekshirish."""
    return bool(re.search(r'[а-яА-ЯёЁўЎқҚғҒҳҲ]', text))


def cyrillic_to_latin(text: str) -> str:
    """Krill yozuvidagi matnni O'zbek lotin alifbosiga o'girish."""
    if not text:
        return ""
    vowels = "АЕЁИОУЭЮЯаеёиоуэюяЎўAEIOUaeiou"
    res = []
    prev_char = ' '
    for ch in text:
        if ch == 'Е':
            if prev_char in vowels or not prev_char.isalnum():
                res.append('Ye')
            else:
                res.append('E')
        elif ch == 'е':
            if prev_char in vowels or not prev_char.isalnum():
                res.append('ye')
            else:
                res.append('e')
        elif ch in CYRILLIC_TO_LATIN_MAP:
            res.append(CYRILLIC_TO_LATIN_MAP[ch])
        else:
            res.append(ch)
        prev_char = ch
    return "".join(res)


def normalize_model_name(model: str, default_model: str) -> str:
    """Model nomlarini OpenRouter va Gemini talablariga moslashtirish."""
    m = model.strip() if model else ""
    if not m:
        return default_model
    # Llama 3.3 70B variantlari (llama-3.3-70b-versatile, llama-3.3-70b va h.k.)
    if "llama-3.3-70b" in m.lower():
        if "meta-llama/" not in m.lower():
            return "meta-llama/llama-3.3-70b-instruct"
    # Eskirgan yoki mavjud bo'lmagan Gemini modellari
    if "gemini" in m.lower() and ("3.5" in m.lower() or "2.0-flash-exp" in m.lower()):
        return "gemini-1.5-flash"
    return m


METRO_AI_SYSTEM_PROMPT = """Sen Toshkent Metropoliteni bo'yicha Yetakchi Transport Analitikisisan.
Sening vazifang - har qanday manbadan (Telegram kanallar, OAV, rasmiy xabarlar) olingan metro yangiliklarini tahlil qilib, yo'lovchilar uchun operativ, professional, ixcham va faqat faktlarga asoslangan qisqa xulosa tayyorlash.

ENG MUHIM QAT'IY TALABLAR (PRO LEVEL):
1. TIL VA ALIFBO (100% O'ZBEK LOTIN):
   - Kiruvchi xabar qaysi tilda (Ruscha, Krillcha, Inglizcha) bo'lishidan qat'i nazar, barcha chiqariladigan matnlar (sarlavha, tahlil, holat, tavsiya) FAQAT VA FAQAT O'ZBEK LOTIN ALIFBOSIDA bo'lishi SHART!
   - Biron bir ruscha yoki krillcha so'zni aslicha qoldirma. Barchasini toza, adabiy o'zbek lotin tiliga tarjima qil.
2. TEJAMKORLIK VA LO'NDALIK (COIN TEJASH):
   - Keraksiz kirish so'zlarni ("Ma'lum qilinishicha", "Ushbu xabarda aytilishicha") aslo ishlatma. Faqat fakt va mohiyat!
   - clean_title: Qisqa, jarangdor faktik sarlavha (maksimal 50 belgi, O'zbek lotincha).
   - quick_summary: 1-2 ta ixcham jumla, maksimal 180 belgi. Asosiy mohiyat va sabab (O'zbek lotincha).
   - incident_status: Qisqa harakat holati (maksimal 45 belgi, O'zbek lotincha).
   - passenger_impact: Yo'lovchiga daxldor 1 ta qisqa fakt (O'zbek lotincha).
   - practical_advice: 1 ta qisqa va to'liq amaliy tavsiya (maksimal 65 belgi, O'zbek lotincha).
3. FAKTIK ANIKLIK:
   - Faqat keltirilgan matnga tayan, yangi fakt to'qima. Reklama va kanal havolalarini 100% tozalab tashla.
4. TOIFALAR VA BADGELAR:
   - EMERGENCY: "🔴 SHOSHILINCH: HARAKAT TO'XTATILDI" (to'xtash, avariya, nosozlik)
   - WARNING: "🟡 DIQQAT: HARAKAT GRAFIGI O'ZGARISHI" (kechikish, oraliq cho'zilishi, ta'mirlash)
   - NEWS: "🟢 YANGILIK VA RIVOJLANISH" (yangi poyezdlar, yangi bekatlar, qulayliklar)
   - INFO: "ℹ️ RASMIY AXBOROT" (raddiya, rasmiy bayonot, to'lov tartibi)

FAQAT QUYIDAGI JSON FORMATIDA JAVOB BER (boshqa hech narsa yozma):
{
  "category": "EMERGENCY | WARNING | NEWS | INFO",
  "badge": "Yuqoridagi badgelardan biri",
  "clean_title": "O'zbek lotincha qisqa sarlavha",
  "quick_summary": "1-2 jumlali o'zbek lotincha qisqa tahlil",
  "station_and_line": "Bekat/liniya nomi yoki bo'sh",
  "incident_status": "O'zbek lotincha qisqa holat",
  "passenger_impact": [
    "Qisqa ta'sir"
  ],
  "practical_advice": "Qisqa amaliy tavsiya"
}
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": (
            "Manba: Spot.uz\n"
            "Sarlavha: Метро Ташкента планирует расширить 80% поездов до пяти вагонов\n"
            "Matn: Пресс-служба столичной подземки прокомментировала информацию о добавлении вагонов в составы. В компании опровергли слухи из соцсетей о якобы планируемом запуске пятивагонных составов с 20 ноября. Модернизация 54 составов пройдет поэтапно до осени 2027 года."
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "category": "INFO",
            "badge": "ℹ️ RASMIY AXBOROT",
            "clean_title": "5 vagonli poyezdlar haqidagi xabarlar rad etildi",
            "quick_summary": "Metropoliten 20-noyabrdan 5 vagonli poyezdlar yurishi haqidagi mish-mishlarni rad etdi. 54 ta tarkibni 5 vagonli tizimga o'tkazish 2027-yil kuzigacha bosqichma-bosqich yakunlanadi.",
            "station_and_line": "Toshkent metropoliteni",
            "incident_status": "ℹ️ Rasmiy raddiya berildi, harakat odatiy rejimda",
            "passenger_impact": [
                "Harakat tarkiblarini kengaytirish 2027-yilgacha yakunlanadi"
            ],
            "practical_advice": "Poyezdlar amaldagi tasdiqlangan jadval asosida harakatlanmoqda."
        }, ensure_ascii=False)
    },
    {
        "role": "user",
        "content": (
            "Manba: Toshkent Metropoliteni Rasmiy\n"
            "Sarlavha: Чилонзор йўлида ҳаракат вақтинча тўхтатилди\n"
            "Matn: Новза бекатида техник носозлик сабабли поездлар 15 дақиқа тўхтаб қолди. Мутахассислар носозликни тезкор бартараф этиб, ҳаракатни тўлиқ тиклади."
        )
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "category": "WARNING",
            "badge": "🟡 DIQQAT: HARAKAT GRAFIGI O'ZGARISHI",
            "clean_title": "Chilonzor yo'lida poyezdlar harakati tiklandi",
            "quick_summary": "'Novza' bekatida poyezddagi texnik nosozlik tufayli harakat 15 daqiqaga to'xtab qoldi. Mutaxassislar muammoni bartaraf etib, qatnovni odatiy rejimda tikladi.",
            "station_and_line": "Chilonzor yo'li ('Novza' bekati)",
            "incident_status": "✅ Nosozlik bartaraf etildi, qatnov tiklandi",
            "passenger_impact": [
                "Harakat 15 daqiqa to'xtab, so'ng to'liq qayta tiklandi"
            ],
            "practical_advice": "Intervallar to'liq barqarorlashguncha qisqa kechikishlarni inobatga oling."
        }, ensure_ascii=False)
    }
]


@dataclass
class AIAnalysisResult:
    """AI tahlilining mukammal strukturadagi natijasi."""
    success: bool
    category: str = "INFO"
    badge: str = "ℹ️ RASMIY AXBOROT"
    title: str = ""
    summary: str = ""
    station_and_line: str = ""
    incident_status: str = ""
    key_points: List[str] = field(default_factory=list)
    advice: str = ""
    provider_used: str = "Mahalliy tahlil"
    model_name: str = ""
    error_message: Optional[str] = None

    def to_telegram_html(self, item: NewsItem) -> str:
        """Natijani Telegram uchun toza, ixcham va so'zlari to'liq HTML formatida tayyorlash."""
        now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
        if item.published_at:
            try:
                import datetime
                pub_str = item.published_at.replace("Z", "+00:00")
                pub_dt = datetime.datetime.fromisoformat(pub_str)
                now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
            except Exception:
                pass

        clean_title = html.escape(self.title.strip() if self.title else item.title.strip(), quote=False)
        clean_badge = html.escape(self.badge.strip(), quote=False)
        raw_summary = self.summary.strip() if self.summary else item.content.strip()
        clean_summary = html.escape(safe_truncate_words(raw_summary, 240), quote=False)
        clean_source = html.escape(item.source_name, quote=False)

        parts = [
            f"🚇 <b>TOSHKENT METROSI | {clean_badge}</b>\n",
            f"📌 <b>{clean_title}</b>\n",
            f"📋 <b>Tahliliy xulosa:</b>\n{clean_summary}\n"
        ]

        details = []
        if self.station_and_line:
            st_l = self.station_and_line.lower()
            if not any(ign in st_l for ign in ["noma'lum", "umumiy tarmoq", "none", "butun", "tutash"]):
                details.append(f"📍 <b>Hudud:</b> {html.escape(self.station_and_line.strip(), quote=False)}")
        if self.incident_status:
            st_clean = safe_truncate_words(self.incident_status.strip(), 70)
            details.append(f"🚦 <b>Holat:</b> {html.escape(st_clean, quote=False)}")

        if details:
            parts.append("\n".join(details) + "\n")

        if self.advice:
            parts.append(f"💡 <b>Tavsiya:</b> <i>{html.escape(self.advice.strip(), quote=False)}</i>\n")

        parts.append(
            f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}"
        )
        return "\n".join(parts)

    def to_telegram_caption_html(self, item: NewsItem) -> str:
        """Fotosuratlar tagiga qo'yiladigan ixcham, lo'nda va to'liq HTML caption."""
        now_str = format_uz_time(fmt="%H:%M | %d.%m.%Y")
        if item.published_at:
            try:
                pub_dt = datetime.datetime.fromisoformat(item.published_at)
                now_str = format_uz_time(pub_dt, fmt="%H:%M | %d.%m.%Y")
            except Exception:
                pass

        clean_title = html.escape(self.title.strip() if self.title else item.title.strip(), quote=False)
        clean_badge = html.escape(self.badge.strip(), quote=False)
        
        raw_summary = self.summary.strip() if self.summary else item.content.strip()
        clean_summary = html.escape(safe_truncate_words(raw_summary, 220), quote=False)
        clean_source = html.escape(item.source_name, quote=False)

        details = []
        if self.station_and_line:
            st_l = self.station_and_line.lower()
            if not any(ign in st_l for ign in ["noma'lum", "umumiy tarmoq", "none", "butun", "tutash"]):
                details.append(f"📍 <b>Hudud:</b> {html.escape(self.station_and_line.strip(), quote=False)}")
        if self.incident_status:
            st_clean = safe_truncate_words(self.incident_status.strip(), 70)
            details.append(f"🚦 <b>Holat:</b> {html.escape(st_clean, quote=False)}")

        lines = [
            f"🚇 <b>TOSHKENT METROSI | {clean_badge}</b>\n",
            f"📌 <b>{clean_title}</b>\n",
            f"📋 <b>Tahlil:</b> {clean_summary}\n"
        ]
        if details:
            lines.append("\n".join(details) + "\n")

        if self.advice:
            lines.append(f"💡 <b>Tavsiya:</b> <i>{html.escape(self.advice.strip(), quote=False)}</i>\n")

        lines.append(
            f"🕒 <b>Vaqt:</b> {now_str} | 🏛️ <b>Manba:</b> {clean_source}"
        )
        return "\n".join(lines)


class AIAnalyzer:
    """
    Toshkent Metropoliteni yangiliklarini tahlil qiluvchi mukammal AI xizmati.
    Gemini API va OpenRouter API integratsiyasiga ega.
    Gemini limiti tugasa yoki xatolik bersa, avtomatik ravishda OpenRouter ga o'tadi.
    """

    def __init__(self):
        self.gemini_api_key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")).strip()
        gem_m = (settings.GEMINI_MODEL or os.environ.get("GEMINI_MODEL", "")).strip()
        self.gemini_model = normalize_model_name(gem_m, "gemini-1.5-flash")

        self.openrouter_api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
        open_m = (settings.OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "")).strip()
        self.openrouter_model = normalize_model_name(open_m, "meta-llama/llama-3.3-70b-instruct")

        self.timeout = getattr(settings, "AI_TIMEOUT", 25.0)

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

    async def analyze_news(self, item: NewsItem) -> AIAnalysisResult:
        """
        Yangilikni oldindan tozalab, AI orqali tahlil qilish.
        1-urinish: Google Gemini API (gemini-3.5-flash-lite)
        2-urinish: OpenRouter API Fallback (Zaxira)
        3-urinish: Mahalliy xavfsiz Fail-Safe
        """
        self.reload_keys()

        if not settings.AI_ENABLED:
            logger.info("AI tahlilchi sozlamalarda o'chirilgan, standart format ishlatilmoqda.")
            return self._build_fallback_result(item, reason="AI o'chirilgan")

        # Matnni oldindan reklamalardan tozalash
        cleaned_content = clean_raw_news_text(item.content)
        cleaned_title = clean_raw_news_text(item.title)

        user_prompt = (
            f"Manba: {item.source_name}\n"
            f"Sarlavha: {cleaned_title}\n"
            f"Matn:\n{cleaned_content[:2500]}"
        )

        # -------------------------------------------------------------
        # 1-QADAM: Google Gemini API orqali sinab ko'rish
        # -------------------------------------------------------------
        if self.gemini_api_key:
            try:
                logger.info(f"Yangilik Gemini API orqali tahlil qilinmoqda ({self.gemini_model})...")
                res = await self._call_gemini_api(user_prompt)
                if res:
                    res.provider_used = "Google Gemini AI"
                    res.model_name = self.gemini_model
                    logger.info(f"Gemini API tahlili muvaffaqiyatli yakunlandi: {res.title[:50]}...")
                    return res
            except Exception as e:
                logger.warning(
                    f"Gemini API xatoligi yoki kvota limiti tugadi: {e}. "
                    "OpenRouter zaxira provayderiga o'tilmoqda..."
                )

        # -------------------------------------------------------------
        # 2-QADAM: OpenRouter API Fallback (Zaxira)
        # -------------------------------------------------------------
        if self.openrouter_api_key:
            try:
                logger.info(f"Yangilik OpenRouter orqali tahlil qilinmoqda ({self.openrouter_model})...")
                res = await self._call_openrouter_api(user_prompt)
                if res:
                    res.provider_used = "OpenRouter AI (Zaxira)"
                    res.model_name = self.openrouter_model
                    logger.info(f"OpenRouter tahlili muvaffaqiyatli yakunlandi: {res.title[:50]}...")
                    return res
            except Exception as e:
                logger.error(f"OpenRouter API xatoligi: {e}")

        # -------------------------------------------------------------
        # 3-QADAM: Fail-Safe Mahalliy formatlash
        # -------------------------------------------------------------
        logger.warning("Barcha AI provayderlari band yoki kalitlar ko'rsatilmagan. Standart format qo'llanmoqda.")
        return self._build_fallback_result(item, reason="API kalitlar kiritilmagan yoki limit tugagan")

    async def _call_gemini_api(self, user_prompt: str) -> Optional[AIAnalysisResult]:
        """Google Gemini REST API ga to'g'ridan-to'g'ri xavfsiz murojaat."""
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
                "parts": [{"text": METRO_AI_SYSTEM_PROMPT}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 429:
                raise RuntimeError("Gemini API Quota / Rate limit exceeded (429)")
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini javob bermadi (bo'sh javob).")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini javob matni topilmadi.")

            raw_text = parts[0].get("text", "")
            return self._parse_json_response(raw_text)

    async def _call_openrouter_api(self, user_prompt: str) -> Optional[AIAnalysisResult]:
        """OpenRouter REST API orqali murojaat (Llama-3.3-70b-instruct)."""
        url = "https://openrouter.ai/api/v1/chat/completions"

        messages = [{"role": "system", "content": METRO_AI_SYSTEM_PROMPT}]
        for example in FEW_SHOT_EXAMPLES:
            messages.append({"role": example["role"], "content": example["content"]})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.openrouter_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 500
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
                raise RuntimeError("OpenRouter Rate limit exceeded (429)")
            if resp.status_code != 200:
                raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenRouter bo'sh javob qaytardi.")

            content = choices[0].get("message", {}).get("content", "")
            return self._parse_json_response(content)

    def _parse_json_response(self, text: str) -> AIAnalysisResult:
        """AI tomonidan qaytarilgan JSON matnini xavfsiz va xatoliklarga chidamli parse qilish."""
        clean_text = text.strip()

        # Markdown ```json va ``` bloklarini tozalash
        if "```json" in clean_text:
            m = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
            if m:
                clean_text = m.group(1).strip()
        elif "```" in clean_text:
            m = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
            if m:
                clean_text = m.group(1).strip()

        # Tashqi matnlardan faqat { ... } qismini ajratish
        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_text = clean_text[first_brace:last_brace + 1]

        data = {}
        try:
            data = json.loads(clean_text)
        except Exception:
            # Moslashuvchan regex fallback
            title_m = re.search(r'["\'](?:clean_title|sarlavha|title)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            summary_m = re.search(r'["\'](?:quick_summary|xulosa|summary)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            badge_m = re.search(r'["\']badge["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            advice_m = re.search(r'["\'](?:practical_advice|tavsiya|advice)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            station_m = re.search(r'["\'](?:station_and_line|bekat|hudud)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
            status_m = re.search(r'["\'](?:incident_status|holat|status)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)

            data = {
                "clean_title": title_m.group(1).strip() if title_m else "",
                "quick_summary": summary_m.group(1).strip() if summary_m else clean_text[:400],
                "badge": badge_m.group(1).strip() if badge_m else "🚇 METRO XABARI",
                "station_and_line": station_m.group(1).strip() if station_m else "",
                "incident_status": status_m.group(1).strip() if status_m else "",
                "practical_advice": advice_m.group(1).strip() if advice_m else "",
                "passenger_impact": []
            }

        category = str(data.get("category", "INFO")).upper()
        badge = str(data.get("badge", "ℹ️ RASMIY AXBOROT")).strip()
        title = str(data.get("clean_title", "")).strip()
        summary = str(data.get("quick_summary", "")).strip()
        station = str(data.get("station_and_line", "")).strip()
        status_line = str(data.get("incident_status", "")).strip()
        points = data.get("passenger_impact", [])
        if not isinstance(points, list):
            points = [str(points)]
        advice = str(data.get("practical_advice", "")).strip()

        # Kafolatlangan 100% O'zbek Lotin imlosi (agar AI javobida krill harflari qolib ketgan bo'lsa)
        if contains_cyrillic(title):
            title = cyrillic_to_latin(title)
        if contains_cyrillic(summary):
            summary = cyrillic_to_latin(summary)
        if contains_cyrillic(station):
            station = cyrillic_to_latin(station)
        if contains_cyrillic(status_line):
            status_line = cyrillic_to_latin(status_line)
        if contains_cyrillic(advice):
            advice = cyrillic_to_latin(advice)

        clean_points = []
        for p in points:
            p_str = str(p).strip()
            if p_str:
                if contains_cyrillic(p_str):
                    p_str = cyrillic_to_latin(p_str)
                clean_points.append(p_str)

        return AIAnalysisResult(
            success=True,
            category=category,
            badge=badge,
            title=title,
            summary=summary,
            station_and_line=station,
            incident_status=status_line,
            key_points=clean_points,
            advice=advice
        )

    def _build_fallback_result(self, item: NewsItem, reason: str = "") -> AIAnalysisResult:
        """
        AI mavjud bo'lmaganda yoki xatolik berganda
        asl matndan xavfsiz va toza formatlangan natija yaratish.
        Krill yoki ruscha matnlar avtomatik ravishda O'zbek lotin alifbosiga o'tkaziladi.
        """
        clean_c = clean_raw_news_text(item.content)
        title = item.title.strip()

        if clean_c == title or not clean_c:
            summary = title
        else:
            summary = clean_c[:350] + ("..." if len(clean_c) > 350 else "")

        # Krill yoki ruscha harflar bo'lsa, kafolatlangan lotin alifbosiga o'tkazish
        if contains_cyrillic(title):
            title = cyrillic_to_latin(title)
        if contains_cyrillic(summary):
            summary = cyrillic_to_latin(summary)

        badge = "🚇 RASMIY METRO XABARI"
        title_lower = title.lower()
        if any(w in title_lower for w in ["to'xtadi", "nosozlik", "kechikmoqda", "avariya", "toxtadi", "to'xtatildi"]):
            badge = "🟡 DIQQAT: HARAKAT O'ZGARISHI"
        elif any(w in title_lower for w in ["yangi", "ochildi", "zamonaviy", "qo'shildi"]):
            badge = "🟢 YANGILIK VA QULAYLIK"

        return AIAnalysisResult(
            success=False,
            category="INFO",
            badge=badge,
            title=title,
            summary=summary,
            station_and_line="Toshkent metropoliteni",
            incident_status="Ma'lumot o'rganilmoqda",
            key_points=[],
            advice="",
            provider_used=f"Standart rejim ({reason})" if reason else "Standart rejim",
            model_name="",
            error_message=reason
        )

ai_analyzer = AIAnalyzer()
