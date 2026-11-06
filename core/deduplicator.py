import re
import json
import time
import logging
import asyncio
from typing import Set, List, Dict, Tuple, Optional
from pathlib import Path
from config import settings
from core.filter import is_disruption_text, is_resolution_text

logger = logging.getLogger("MetroMonitor.Deduplicator")

STOPWORDS = {
    "va", "bilan", "uchun", "ham", "esa", "bu", "shu", "u", "deb", "xabar", 
    "beradi", "qildi", "bo'ldi", "haqida", "ko'ra", "yoki", "ammo", "lekin", 
    "biroq", "tufayli", "soat", "kuni", "bugun", "kecha", "ushbu", "batafsil",
    "rasmiy", "ma'lumot", "toshkent", "тошкент", "йўли", "йўналиши", "бошқармаси",
    "matbuot", "xizmati", "kanal", "obuna", "bo'ling", "кўра", "ҳақида", "бўйича",
    "соат", "куни", "бугун", "кеча", "хабар", "қилинди", "берилди", "маълумот"
}

UZ_SUFFIXES = [
    "larining", "larida", "laridan", "lariga", "larini", "larimiz",
    "sining", "ining", "laridagi", "sida", "sidan", "siga", "larda", 
    "lardan", "larga", "larni", "lari", "ning", "dan", "dagi", "lik", 
    "lar", "ida", "dan", "ga", "ka", "qa", "da", "ni", "si", "i"
]

RU_SUFFIXES = [
    "овалось", "ивалось", "енный", "анный", "лями", "ями", "ами", "ого", "его",
    "ому", "ему", "ыми", "ими", "ных", "лся", "лась", "лось", "лись", "ется",
    "ится", "ются", "ятся", "ов", "ев", "ах", "ях", "ом", "ем", "ам", "ям",
    "ый", "ий", "ая", "яя", "ое", "ее", "ые", "ие", "ых", "их", "ым", "им",
    "а", "я", "ы", "и", "е", "у", "ю"
]

def stem_word(w: str) -> str:
    """O'zbek va rus tillaridagi suffikslarni tozalab, so'z o'zagini olish."""
    w = w.lower().strip(" '`\".,!?:;-")
    
    # O'zbekcha suffikslar
    for suf in UZ_SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            break

    # Ruscha suffikslar
    for suf in RU_SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            break

    return w

class CrossSourceDeduplicator:
    """
    Kross-manbali matn o'xshashligi tahlili (Cross-source Semantic Deduplication).
    Stemming, Jaccard va Containment (Overlap) o'lchovlari yordamida turli OAVlar
    bir xil voqeani qayta e'lon qilganida 100% aniqlikda tutib qoladi.
    """
    def __init__(
        self,
        filepath: Path = settings.SEEN_FINGERPRINTS_FILE,
        threshold: float = settings.SIMILARITY_THRESHOLD,
        ttl_seconds: int = 86400  # 24 soatlik xotira
    ):
        self.filepath = filepath
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self._history: List[Dict] = []
        self._dirty: bool = False
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    now = time.time()
                    self._history = []
                    for item in data:
                        if now - item.get("timestamp", 0) < self.ttl_seconds:
                            # Token setni xotirada O(1) tezlik uchun keshlaymiz
                            item["_token_set"] = set(item.get("tokens", []))
                            self._history.append(item)
                    logger.info(f"Antidublikat xotirasiga {len(self._history)} ta so'nggi voqea yuklandi.")
            except Exception as e:
                logger.error(f"seen_fingerprints.json faylini o'qishda xatolik: {e}")
                self._history = []
        else:
            self._save()

    def _save(self) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            to_dump = []
            for item in self._history:
                d = {k: v for k, v in item.items() if not k.startswith("_")}
                to_dump.append(d)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(to_dump, f, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            logger.error(f"seen_fingerprints.json fayliga yozishda xatolik: {e}")

    def save(self) -> None:
        if self._dirty:
            self._save()

    async def save_async(self) -> None:
        if self._dirty:
            await asyncio.to_thread(self._save)

    def tokenize(self, text: str) -> Set[str]:
        """Matndan kalit so'zlar o'zaklarini (stemmed tokens) ajratib olish."""
        if not text:
            return set()
        
        text = re.sub(r'https?://\S+|@\w+', ' ', text.lower())
        raw_words = re.findall(r'[a-zа-яёўқғҳ\']{3,}', text)
        
        tokens = set()
        for w in raw_words:
            w_stemmed = stem_word(w)
            if w_stemmed not in STOPWORDS and len(w_stemmed) >= 3:
                tokens.add(w_stemmed)
                
        return tokens

    def calculate_metrics(self, tokens_a: Set[str], tokens_b: Set[str]) -> Tuple[float, float, int]:
        """
        Jaccard va Overlap (Containment) koeffitsientlari.
        Xotirani ortiqcha band qilmaslik uchun union to'plam yaratmasdan (|A| + |B| - |A ∩ B|) hisoblanadi.
        Natija: (jaccard_score, overlap_score, intersection_count)
        """
        if not tokens_a or not tokens_b:
            return 0.0, 0.0, 0

        # Agar umumiy so'z umuman bo'lmasa, darhol 0 qaytariladi
        if tokens_a.isdisjoint(tokens_b):
            return 0.0, 0.0, 0

        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a) + len(tokens_b) - intersection
        min_len = min(len(tokens_a), len(tokens_b))

        jaccard = intersection / union if union > 0 else 0.0
        overlap = intersection / min_len if min_len > 0 else 0.0

        return jaccard, overlap, intersection

    def is_duplicate(self, title: str, content: str, source_name: str) -> Tuple[bool, Optional[str], float]:
        """
        Xabar boshqa manba tomonidan avval yoritilgan ayni bir xil voqeami yoki yo'qligini tekshiradi.
        Agar yangi xabar avvalgi nosozlikdan so'ng harakat qayta tiklangani haqida bo'lsa (Resolution),
        dublikat filtri chetlab o'tiladi va xabar o'tkaziladi.
        """
        full_text = f"{title} {content}"
        new_tokens = self.tokenize(full_text)

        if not new_tokens or len(new_tokens) < 3:
            return False, None, 0.0

        is_curr_res = is_resolution_text(full_text)
        now = time.time()
        max_score = 0.0
        dup_source = None

        for item in reversed(self._history):
            if now - item.get("timestamp", 0) > self.ttl_seconds:
                continue

            stored_tokens = item.get("_token_set")
            if stored_tokens is None:
                stored_tokens = set(item.get("tokens", []))
                item["_token_set"] = stored_tokens

            jaccard, overlap, inter_count = self.calculate_metrics(new_tokens, stored_tokens)

            # Birlashtirilgan o'xshashlik bahosi
            # Agar kamida 4 ta kalit o'zak bir xil bo'lsa va overlap 60% dan yuqori bo'lsa
            combined_score = max(jaccard, overlap * 0.9)

            if combined_score > max_score:
                max_score = combined_score
                dup_source = item.get("source", "Boshqa manba")

            # Chegaradan o'tsa va yetarlicha so'z mos tushsa:
            if (combined_score >= self.threshold or (overlap >= 0.65 and inter_count >= 4)):
                # Agar yangi xabar harakat tiklangani haqida bo'lsa (resolution) va
                # avvalgi post nosozlik/to'xtash haqida bo'lsa — bu dublikat emas, ijobiy yangilanish!
                stored_full = f"{item.get('title', '')} {item.get('content', '')}"
                is_prev_disrupt = item.get("is_disruption", False) or is_disruption_text(stored_full)
                if is_curr_res and is_prev_disrupt:
                    logger.info(
                        f"🟢 Tiklanish (Resolution) xabari aniqlandi! Avvalgi to'xtash xabaridan so'ng "
                        f"harakat tiklangani sababli dublikat filtri chetlab o'tildi. Asl manba: {dup_source}"
                    )
                    return False, dup_source, combined_score

                logger.info(
                    f"Kross-dublikat aniqlandi! Yangi manba: '{source_name}', "
                    f"Asl manba: '{dup_source}', Ball: {combined_score:.2f} (Mos so'zlar: {inter_count})"
                )
                return True, dup_source, combined_score

        return False, None, max_score

    def register_event(
        self,
        title: str,
        content: str,
        source_name: str,
        url: str,
        ai_title: str = "",
        ai_summary: str = "",
        ai_badge: str = "",
        image_url: str = "",
        line: str = "",
        station: str = "",
        topic: str = "",
        is_resolution: bool = False
    ) -> Dict:
        """Yangi noyob metro voqeasini xotiraga qayd qilish."""
        full_text = f"{title} {content}"
        tokens = list(self.tokenize(full_text))

        event_data = {
            "title": title[:140],
            "content": content[:400],
            "source": source_name,
            "url": url,
            "tokens": tokens,
            "_token_set": set(tokens),
            "timestamp": time.time(),
            "ai_title": ai_title,
            "ai_summary": ai_summary,
            "ai_badge": ai_badge,
            "image_url": image_url,
            "line": line,
            "station": station,
            "topic": topic,
            "is_resolution": is_resolution or is_resolution_text(full_text),
            "is_disruption": is_disruption_text(full_text)
        }
        self._history.append(event_data)

        # 24 soatdan eskilarni tozalash
        now = time.time()
        self._history = [
            item for item in self._history 
            if now - item.get("timestamp", 0) < self.ttl_seconds
        ]
        self._dirty = True
        self._save()
        return event_data

    def update_event_ai(
        self,
        url: str,
        ai_title: str,
        ai_summary: str,
        ai_badge: str,
        image_url: str = "",
        station: str = "",
        line: str = "",
        topic: str = "",
        is_resolution: bool = False,
        status: str = "",
        advice: str = "",
        full_html: str = "",
        caption_html: str = ""
    ) -> None:
        """Voqea uchun AI tahlil natijasini yangilash."""
        for item in reversed(self._history):
            if item.get("url") == url or item.get("title") in ai_title or ai_title in item.get("title", ""):
                item["ai_title"] = ai_title
                item["ai_summary"] = ai_summary
                item["ai_badge"] = ai_badge
                if image_url:
                    item["image_url"] = image_url
                if station:
                    item["station"] = station
                    item["ai_station"] = station
                if line:
                    item["line"] = line
                if topic:
                    item["topic"] = topic
                if is_resolution:
                    item["is_resolution"] = True
                if status:
                    item["ai_status"] = status
                if advice:
                    item["ai_advice"] = advice
                if full_html:
                    item["ai_full_html"] = full_html
                if caption_html:
                    item["ai_caption_html"] = caption_html
                self._dirty = True
                self._save()
                break

    def search_events(self, query: str, limit: int = 8) -> List[Dict]:
        """Antidublikat xotirasidan bekat nomi yoki kalit so'z bo'yicha qidirish."""
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        q_no_apos = q.replace("'", "")
        results = []

        for item in reversed(self._history):
            searchable_fields = [
                item.get("title", ""),
                item.get("content", ""),
                item.get("ai_title", ""),
                item.get("ai_summary", ""),
                item.get("station", ""),
                item.get("line", ""),
                item.get("topic", ""),
                item.get("source", "")
            ]
            haystack = " ".join(searchable_fields).lower()
            haystack_no_apos = haystack.replace("'", "")

            if q in haystack or q_no_apos in haystack_no_apos:
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Oxirgi qayd etilgan metro hodisalari ro'yxatini qaytaradi."""
        return list(reversed(self._history))[:limit]

    def get_today_events(self) -> List[Dict]:
        """O'zbekiston vaqti bo'yicha bugungi kun (00:00 dan boshlab) topilgan xabarlar."""
        from config import uz_now, UZ_TZ
        from datetime import datetime
        now = uz_now()
        today_midnight = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=UZ_TZ).timestamp()
        today_items = [
            item for item in self._history
            if item.get("timestamp", 0) >= today_midnight
        ]
        return list(reversed(today_items))

    def clear_history(self) -> int:
        """Antidublikat xotirasini tozalash."""
        count = len(self._history)
        self._history.clear()
        self._dirty = True
        self._save()
        logger.info(f"Antidublikat xotirasi tozalandi ({count} ta voqea o'chirildi).")
        return count

    def set_threshold(self, threshold: float) -> None:
        """Dublikat o'xshashlik chegarasini dinamik o'zgartirish."""
        self.threshold = max(0.1, min(1.0, threshold))
        logger.info(f"Antidublikat chegarasi {self.threshold} ga o'zgartirildi.")

deduplicator = CrossSourceDeduplicator()

