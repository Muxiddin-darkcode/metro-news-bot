import re
import json
from pathlib import Path
from typing import List, Tuple, Dict
from config import DATA_DIR

CUSTOM_KEYWORDS_FILE = DATA_DIR / "custom_keywords.json"
_custom_keywords_cache: List[str] = []

def load_custom_keywords() -> List[str]:
    """Admin tomonidan qo'shilgan maxsus kalit so'zlarni yuklash."""
    global _custom_keywords_cache
    if CUSTOM_KEYWORDS_FILE.exists():
        try:
            with open(CUSTOM_KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    _custom_keywords_cache = [str(k).strip().lower() for k in data if str(k).strip()]
                    return _custom_keywords_cache
        except Exception:
            pass
    _custom_keywords_cache = []
    return _custom_keywords_cache

def save_custom_keywords(keywords: List[str]) -> bool:
    """Maxsus kalit so'zlarni faylga saqlash."""
    global _custom_keywords_cache
    try:
        CUSTOM_KEYWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        unique_kws = sorted(list({str(k).strip().lower() for k in keywords if str(k).strip()}))
        with open(CUSTOM_KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_kws, f, ensure_ascii=False, indent=2)
        _custom_keywords_cache = unique_kws
        return True
    except Exception:
        return False

def add_custom_keyword(keyword: str) -> bool:
    """Yangi kalit so'z qo'shish."""
    k = keyword.strip().lower()
    if not k or len(k) < 3:
        return False
    current = load_custom_keywords()
    if k in current:
        return True
    current.append(k)
    return save_custom_keywords(current)

def remove_custom_keyword(keyword: str) -> bool:
    """Mavjud kalit so'zni o'chirish."""
    k = keyword.strip().lower()
    current = load_custom_keywords()
    if k not in current:
        return False
    current.remove(k)
    return save_custom_keywords(current)

def get_custom_keywords() -> List[str]:
    """Kalit so'zlar ro'yxatini olish."""
    return load_custom_keywords()

load_custom_keywords()


# Aniqlik bilan faqat Metro va Metropolitenni tutuvchi qat'iy regex qoliplari (O'zbek Lotin, O'zbek Kirill, Rus)
METRO_EXPLICIT_PATTERNS = [
    # O'zbekcha Lotin: metro, metrosi, metroda, metrodan, metroga, metroning, metroni, metrolar, metrolari...
    r'\bmetro(?:da|dan|ga|ni|ning|si|sida|sidan|siga|sini|sining|lar|lari|larida|lariga|lardan|lardagi)?\b',
    # O'zbekcha Kirill: метро, метроси, метрода, метродан, метрога, метронинг, метролар...
    r'\bметро(?:да|дан|га|ни|нинг|си|сида|сидан|сига|сини|сининг|лар|лари|ларида|ларига|лардан|лардаги)?\b',
    # Metropoliten (Lotin & Kirill)
    r'\bmetropoliten(?:i|da|dan|ga|ning|ining|ida|idan)?\b',
    r'\bметрополитен(?:и|да|дан|га|нинг|ининг|ида|идан|га|да)?\b',
    # Tashmetro / Toshmetro
    r'\b(?:tosh|tash)metro(?:si|da|dan|ga|ning)?\b',
    r'\bтошметро(?:си|да|дан|га|нинг)?\b',
    # Ruscha: подземка, ташкентское метро, станция метро, поезда метро
    r'\bподземк[аиеуой]\b',
    r'\bстанци[яиеей]\s+метро\b',
    r'\bпоезд[а-я]{0,3}\s+метро\b',
    r'\bвагон[а-я]{0,3}\s+метро\b'
]

# Bekatlar (FAQAT "bekat", "бекат", "станция" so'zi bilan birgalikda)
SPECIFIC_STATIONS = [
    # Lotin
    "paxtakor bekati", "chilonzor bekati", "amir temur bekati",
    "buyuk ipak yo'li bekati", "beruniy bekati", "do'stlik bekati",
    "novza bekati", "alisher navoiy bekati", "ming o'rik bekati",
    "turkiston bekati", "shahriston bekati", "bodomzor bekati",
    "minor bekati", "abdulla qodiriy bekati", "qipchoq bekati",
    "olmazor bekati", "kosmonavtlar bekati", "oybek bekati",
    "tinchlik bekati", "g'afur g'ulom bekati", "chorsu bekati",
    "mashinasozlar bekati", "toshkent bekati", "sergeli bekati",
    "xalqlar do'stligi bekati", "milliy bog' bekati", "mirzo ulug'bek bekati",
    "hamid olimjon bekati", "pushkin bekati", "choshtepa bekati",
    "texnopark bekati", "yangiobod bekati", "rohat bekati",
    "qo'yliq bekati", "chinor bekati", "yangihayot bekati",
    # Kirill
    "пахтакор бекати", "чилонзор бекати", "амир темур бекати",
    "буюк ипак йўли бекати", "беруний бекати", "дўстлик бекати",
    "новза бекати", "алишер навоий бекати", "минг ўрик бекати",
    "туркистон бекати", "шаҳристон бекати", "бодомзор бекати",
    "минор бекати", "абдулла қодирий бекати", "қипчоқ бекати",
    "олмазор бекати", "космонавтлар бекати", "ойбек бекати",
    "тинчлик бекати", "ғафур ғулом бекати", "чорсу бекати",
    "машинасозлар бекати", "тошкент бекати", "сергели бекати",
    "халқлар дўстлиги бекати", "миллий боғ бекати", "мирзо улуғбек бекати",
    "ҳомид олимжон бекати", "пушкин бекати", "чоштепа бекати",
    "технопарк бекати", "янгиобод бекати", "роҳат бекати",
    "қўйлиқ бекати", "чинор бекати", "янгиҳаёт бекати",
    # Ruscha
    "станция пахтакор", "станция чилонзор", "станция амир темур",
    "станция беруни", "станция дустлик", "станция новза",
    "станция алишера навои", "станция минг урик", "станция туркестан",
    "станция шахристан", "станция бадамзар", "станция минор",
    "станция кипчак", "станция алмазар", "станция космонавтов",
    "станция айбек", "станция тинчлик", "станция чорсу",
    "станция дружбы народов", "станция национальный парк", "станция мирзо улугбек",
    "станция хамида олимджана", "станция пушкина", "станция сергели"
]

# Metro yo'nalishlari (O'zbek va Rus tillarida)
METRO_LINES = [
    "chilonzor yo'li", "чилонзор йўли", "chilonzor yo'nalishi", "чилонзор йўналиши", "chilonzor liniyasi", "чилонзор линияси",
    "yunusobod yo'li", "юнусобод йўли", "yunusobod yo'nalishi", "юнусобод йўналиши", "yunusobod liniyasi", "юнусобод линияси",
    "o'zbekiston metro", "ўзбекистон метро", "o'zbekiston yo'nalishi metro", "ўзбекистон йўналиши метро", "o'zbekiston liniyasi",
    "sergeli metro", "сергели метро", "sergeli yo'nalishi", "сергели йўналиши", "sergeli liniyasi",
    "yerusti metro", "ерусти метро", "yer osti metro", "ер ости метро",
    "halqa metro", "ҳалқа метро", "yerusti halqa yo'li", "ерусти ҳалқа йўли", "halqa liniyasi", "ҳалқа линияси"
]

# Uy-joy va ko'chmas mulk reklamalari (filtrlash shart)
REAL_ESTATE_PATTERNS = [
    r"metro(?:ga)?\s+(?:yaqin|5\s*daqiqa|10\s*daqiqa|qadam).*?(?:uy|kvartira|xonadon|hovli|joy|kafe|restoran|do'kon|sotiladi|ijara|narxi|arenda|\$)",
    r"(?:kvartira|uy|xonadon|kottedj|dom|ofis|noturar|bino)\s+(?:sotiladi|ijaraga|arenda|narxi|olaman).*?metro",
    r"рядом\s+с\s+метро.*?(?:квартира|дом|офис|аренда|продается|цена|новостройка|\$)",
    r"(?:квартира|дом|аренда|новостройка|продается|сдается|недвижимость).*?метро",
]

# Sport va yengil atletika masofalari (metr, 200 metr yugurish, estafeta)
SPORTS_DISTANCE_PATTERNS = [
    r"(?:\d+\s*metr|\d+\s*метр[а-я]{0,3})\s+(?:masofa|yugurish|suzish|eshkak|marafon|дистанци\w*|забег|эстафет\w*)",
    r"\b(?:дистанци[ия]\s+\d+\s*м|\bзабег\b|\bэстафет\w*|\bгребл\w*|\bплавани\w*|\bмедал[ьяеи]\w*|\bазиатск\w+\s+игр\w*|\bчемпионат\w*)",
]

# Toshkent metrosiga oid kuchli, shubhasiz belgilar
STRONG_METRO_SIGNALS = [
    "toshkent metropoliteni", "тошкент метрополитен", "tashkent metro",
    "metro bekati", "metro bekatlari", "станция метро", "станции метро",
    "metro poyezdi", "вагон метро", "поезд метро", "chilonzor yo'li",
    "chilonzor yo'nalishi", "yunusobod yo'nalishi", "o'zbekiston yo'nalishi",
    "toshmetro", "тошметро"
]

# Metro so'zi bilan bog'liq bo'lmagan soxta so'zlar
EXCLUSION_WORDS = [
    "metrolog", "метролог", "geometr", "геометр", "barometr", "термометр",
    "santimetr", "сантиметр", "millimetr", "миллиметр", "kilometr", "километр",
    "metronom", "метроном", "metropol mehmonxona", "metropol hotel", "metro cash"
]

# Chet el metrosi haqidagi xabarlarni filtrlash (Toshkent/O'zbekiston bo'lmasa)
FOREIGN_METRO_CLUES = [
    "московск", "токийск", "парижск", "нью-йорк", "пекинск", "японск", "санкт-петербург",
    "петербургск", "киевск", "берлинск", "стамбул", "алматы", "туркия",
    "в москве", "в токио", "в париже", "в лондоне", "россиис", "moskva metrosi", "rossiya metrosi"
]

# Hodisa va transport detallarini teglash (O'zbekcha va Ruscha)
DETAIL_TAGS = [
    ("to'xtab qoldi", "#toxtab_qoldi"),
    ("тўхтаб қолди", "#toxtab_qoldi"),
    ("kechikish", "#kechikish"),
    ("кечикиш", "#kechikish"),
    ("nosozlik", "#nosozlik"),
    ("носозлик", "#nosozlik"),
    ("vagon", "#vagon"),
    ("вагон", "#vagon"),
    ("poyezd", "#poyezd"),
    ("поезд", "#poyezd"),
    ("eskalator", "#eskalator"),
    ("эскалатор", "#eskalator"),
    ("turniket", "#turniket"),
    ("турникет", "#turniket"),
    ("chipta", "#chipta"),
    ("чипта", "#chipta"),
    ("chilonzor", "#chilonzor"),
    ("чилонзор", "#chilonzor"),
    ("yunusobod", "#yunusobod"),
    ("юнусобод", "#yunusobod"),
    ("sergeli", "#sergeli"),
    ("сергели", "#sergeli"),
    ("tarif", "#tarif"),
    ("тариф", "#tarif"),
    ("narx", "#narx"),
    ("narxi", "#narx")
]

def clean_text(text: str) -> str:
    """Matnni tozalash va kichik harfga o'tkazish."""
    if not text:
        return ""
    text = text.lower()
    text = text.replace("ʻ", "'").replace("ʼ", "'").replace("`", "'")
    return text

def is_metro_related(title: str, content: str) -> Tuple[bool, List[str]]:
    """
    Xabar FAQAT Toshkent metrosiga tegishli ekanligini 100% aniqlikda tekshiradi.
    O'zbekcha (Lotin va Kirill) hamda mahalliy ruscha xabarlarni to'liq qamrab oladi.
    Reklamalar va sport masofalarini qat'iy chetlab o'tadi.
    """
    full_text = f"{title} {content}"
    cleaned = clean_text(full_text)

    # 1. Soxta so'zlar tekshiruvi (metrologiya, santimetr va h.k.)
    for excl in EXCLUSION_WORDS:
        if excl in cleaned:
            has_real_metro = any(re.search(pat, cleaned) for pat in METRO_EXPLICIT_PATTERNS)
            if not has_real_metro:
                return False, []

    # 2. Uy-joy yoki ko'chmas mulk reklamalari
    if any(re.search(pat, cleaned) for pat in REAL_ESTATE_PATTERNS):
        return False, []

    # 3. Sport va yengil atletika masofalari (200 metr, suzish, medallar)
    has_sports_distance = any(re.search(pat, cleaned) for pat in SPORTS_DISTANCE_PATTERNS)
    if has_sports_distance:
        # Faqat Toshkent metrosi aniq va kuchli tilga olingan bo'lsa ruxsat beriladi
        has_strong_metro = any(sig in cleaned for sig in STRONG_METRO_SIGNALS)
        if not has_strong_metro:
            return False, []

    # 4. Chet el metrosi tekshiruvi (agar Toshkent/O'zbekiston tilga olinmagan bo'lsa)
    is_foreign = any(clue in cleaned for clue in FOREIGN_METRO_CLUES)
    is_local = any(loc in cleaned for loc in ["toshkent", "тошкент", "tashkent", "o'zbekiston", "ўзбекистон", "узбекистан", "пойтахт"])
    if is_foreign and not is_local:
        return False, []

    matched_tags = []
    is_metro = False

    # 5. Qat'iy Metro so'zi tekshiruvi (metro, metrosi, metropoliten...)
    for pat in METRO_EXPLICIT_PATTERNS:
        if re.search(pat, cleaned):
            is_metro = True
            if "#metro" not in matched_tags:
                matched_tags.append("#metro")
            break

    # 6. Aniq metro bekatlari tekshiruvi ("... bekati")
    for st in SPECIFIC_STATIONS:
        if st in cleaned:
            is_metro = True
            bekat_tag = "#" + st.split()[0].replace("'", "")
            if bekat_tag not in matched_tags:
                matched_tags.append(bekat_tag)
            break

    # 7. Aniq metro yo'nalishlari tekshiruvi
    for line in METRO_LINES:
        if line in cleaned:
            is_metro = True
            line_tag = "#" + line.split()[0].replace("'", "")
            if line_tag not in matched_tags:
                matched_tags.append(line_tag)
            break

    # 7.5 Dinamik maxsus kalit so'zlar tekshiruvi (Admin qo'shgan)
    for kw in _custom_keywords_cache:
        if kw and kw in cleaned:
            is_metro = True
            tag = "#" + kw.replace(" ", "_").replace("'", "")[:20]
            if tag not in matched_tags:
                matched_tags.append(tag)
            break

    if not is_metro:
        return False, []

    # 8. Qo'shimcha teglash (hodisalar, yo'nalishlar)
    for word, tag in DETAIL_TAGS:
        if word in cleaned and tag not in matched_tags:
            matched_tags.append(tag)

    return True, matched_tags[:6]

def explain_filter(title: str, content: str) -> Dict:
    """
    Filtr qanday qaror chiqarganini tahlil qiluvchi diagnostik funksiya.
    Admin uchun test vositasida ishlatiladi.
    """
    full_text = f"{title} {content}"
    cleaned = clean_text(full_text)

    # 1. Soxta so'zlar
    for excl in EXCLUSION_WORDS:
        if excl in cleaned:
            has_real_metro = any(re.search(pat, cleaned) for pat in METRO_EXPLICIT_PATTERNS)
            if not has_real_metro:
                return {
                    "is_metro": False,
                    "tags": [],
                    "reason": f"Soxta metro so'zi aniqlandi: '{excl}' (metrologiya, santimetr va h.k.)",
                    "matched": [excl]
                }

    # 2. Ko'chmas mulk
    for pat in REAL_ESTATE_PATTERNS:
        m = re.search(pat, cleaned)
        if m:
            return {
                "is_metro": False,
                "tags": [],
                "reason": f"Ko'chmas mulk / Uy-joy reklamasi deb topildi ('{m.group(0)[:60]}...')",
                "matched": [m.group(0)]
            }

    # 3. Sport masofasi
    for pat in SPORTS_DISTANCE_PATTERNS:
        m = re.search(pat, cleaned)
        if m:
            has_strong_metro = any(sig in cleaned for sig in STRONG_METRO_SIGNALS)
            if not has_strong_metro:
                return {
                    "is_metro": False,
                    "tags": [],
                    "reason": f"Sport/masofa metri deb topildi ('{m.group(0)[:60]}...')",
                    "matched": [m.group(0)]
                }

    # 4. Chet el metrosi
    is_foreign = any(clue in cleaned for clue in FOREIGN_METRO_CLUES)
    is_local = any(loc in cleaned for loc in ["toshkent", "тошкент", "tashkent", "o'zbekiston", "ўзбекистон", "узбекистан", "пойтахт"])
    if is_foreign and not is_local:
        foreign_match = [c for c in FOREIGN_METRO_CLUES if c in cleaned]
        return {
            "is_metro": False,
            "tags": [],
            "reason": f"Chet el metrosi aniqlandi ({', '.join(foreign_match)}), Toshkent ko'rsatilmagan",
            "matched": foreign_match
        }

    is_metro, tags = is_metro_related(title, content)
    matched_clues = []
    for pat in METRO_EXPLICIT_PATTERNS:
        m = re.search(pat, cleaned)
        if m:
            matched_clues.append(f"Qat'iy pattern: {m.group(0)}")
            break
    for st in SPECIFIC_STATIONS:
        if st in cleaned:
            matched_clues.append(f"Bekat: {st}")
            break
    for line in METRO_LINES:
        if line in cleaned:
            matched_clues.append(f"Liniya: {line}")
            break
    for kw in _custom_keywords_cache:
        if kw in cleaned:
            matched_clues.append(f"Maxsus kalit so'z: {kw}")
            break

    if is_metro:
        return {
            "is_metro": True,
            "tags": tags,
            "reason": "Toshkent metrosiga oid haqiqiy xabar deb tasdiqlandi!",
            "matched": matched_clues
        }
    else:
        return {
            "is_metro": False,
            "tags": [],
            "reason": "Metro, bekat yoki metropoliten bilan bog'liq kalit so'z topilmadi.",
            "matched": []
        }

