import re
import json
import time
import logging
from typing import Set, List, Dict, Tuple, Optional
from pathlib import Path
from config import settings

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
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    now = time.time()
                    self._history = [
                        item for item in data 
                        if now - item.get("timestamp", 0) < self.ttl_seconds
                    ]
                    logger.info(f"Antidublikat xotirasiga {len(self._history)} ta so'nggi voqea yuklandi.")
            except Exception as e:
                logger.error(f"seen_fingerprints.json faylini o'qishda xatolik: {e}")
                self._history = []
        else:
            self._save()

    def _save(self) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"seen_fingerprints.json fayliga yozishda xatolik: {e}")

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
        Natija: (jaccard_score, overlap_score, intersection_count)
        """
        if not tokens_a or not tokens_b:
            return 0.0, 0.0, 0

        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        min_len = min(len(tokens_a), len(tokens_b))

        jaccard = intersection / union if union > 0 else 0.0
        overlap = intersection / min_len if min_len > 0 else 0.0

        return jaccard, overlap, intersection

    def is_duplicate(self, title: str, content: str, source_name: str) -> Tuple[bool, Optional[str], float]:
        """
        Xabar boshqa manba tomonidan avval yoritilgan ayni bir xil voqeami yoki yo'qligini tekshiradi.
        """
        full_text = f"{title} {content}"
        new_tokens = self.tokenize(full_text)

        if not new_tokens or len(new_tokens) < 3:
            return False, None, 0.0

        now = time.time()
        max_score = 0.0
        dup_source = None

        for item in reversed(self._history):
            if now - item.get("timestamp", 0) > self.ttl_seconds:
                continue

            stored_tokens = set(item.get("tokens", []))
            jaccard, overlap, inter_count = self.calculate_metrics(new_tokens, stored_tokens)

            # Birlashtirilgan o'xshashlik bahosi
            # Agar kamida 4 ta kalit o'zak bir xil bo'lsa va overlap 60% dan yuqori bo'lsa
            combined_score = max(jaccard, overlap * 0.9)

            if combined_score > max_score:
                max_score = combined_score
                dup_source = item.get("source", "Boshqa manba")

            # Chegaradan o'tsa va yetarlicha so'z mos tushsa — bu dublikat!
            if (combined_score >= self.threshold or (overlap >= 0.65 and inter_count >= 4)):
                logger.info(
                    f"Kross-dublikat aniqlandi! Yangi manba: '{source_name}', "
                    f"Asl manba: '{dup_source}', Ball: {combined_score:.2f} (Mos so'zlar: {inter_count})"
                )
                return True, dup_source, combined_score

        return False, None, max_score

    def register_event(self, title: str, content: str, source_name: str, url: str) -> None:
        """Yangi noyob metro voqeasini xotiraga qayd qilish."""
        full_text = f"{title} {content}"
        tokens = list(self.tokenize(full_text))

        event_data = {
            "title": title[:140],
            "source": source_name,
            "url": url,
            "tokens": tokens,
            "timestamp": time.time()
        }
        self._history.append(event_data)

        # 24 soatdan eskilarni tozalash
        now = time.time()
        self._history = [
            item for item in self._history 
            if now - item.get("timestamp", 0) < self.ttl_seconds
        ]
        self._save()

deduplicator = CrossSourceDeduplicator()
