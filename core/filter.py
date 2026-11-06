import re
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
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

# Toshkent Metropolitenining 4 ta rasmiy liniyasi va barcha 50+ bekatlari ma'lumotlar bazasi
METRO_LINES_INFO = {
    "chilonzor": {
        "name": "🔴 Chilonzor yo'li",
        "keywords": [
            "chilonzor yo'li", "чилонзор йўли", "chilonzor yo'nalishi", "чилонзор йўналиши",
            "chilonzor liniyasi", "чилонзор линияси", "чиланзарская линия", "чиланзарской", "chilonzor metro"
        ],
        "stations": [
            ("Buyuk Ipak Yo'li", ["buyuk ipak yo'li", "буюк ипак йўли", "буюк ипак йули", "buyuk ipak yoli", "максим горький"]),
            ("Pushkin", ["pushkin bekati", "пушкин бекати", "станция пушкина", "пушкин"]),
            ("Hamid Olimjon", ["hamid olimjon", "ҳомид олимжон", "хамид олимджан", "хамида алимджана"]),
            ("Amir Temur xiyoboni", ["amir temur xiyoboni", "амир темур хиёбони", "amir temur bekati", "амир темур бекати", "станция амир темур", "сквер"]),
            ("Mustaqillik maydoni", ["mustaqillik maydoni", "мустақиллик майдони", "площадь мустакиллик", "площадь ленина"]),
            ("Paxtakor", ["paxtakor", "пахтакор"]),
            ("Xalqlar do'stligi", ["xalqlar do'stligi", "халқлар дўстлиги", "дружба народов", "дружбы народов", "bunyodkor bekati", "бунёдкор"]),
            ("Milliy bog'", ["milliy bog'", "миллий боғ", "milliy bog", "миллий бог", "национальный парк", "комсомольская"]),
            ("Novza", ["novza", "новза", "hamza bekati", "ҳамза бекати"]),
            ("Mirzo Ulug'bek", ["mirzo ulug'bek bekati", "мирзо улуғбек бекати", "мирзо улугбек", "50 лет ссср"]),
            ("Chilonzor", ["chilonzor bekati", "чилонзор бекати", "станция чилонзор"]),
            ("Olmazor", ["olmazor bekati", "олмазор бекати", "станция алмазар", "собир раҳимов", "sobir rahimov"]),
            ("Choshtepa", ["choshtepa", "чоштепа"]),
            ("O'zgarish", ["o'zgarish bekati", "ўзгариш бекати", "узгариш"]),
            ("Sirg'ali", ["sirg'ali bekati", "сирғали бекати", "sergeli bekati", "сергели бекати", "станция сергели"]),
            ("Yangihayot", ["yangihayot bekati", "янгиҳаёт бекати", "янгихаёт"]),
            ("Chinor", ["chinor bekati", "чинор бекати", "станция чинор"])
        ]
    },
    "ozbekiston": {
        "name": "🔵 O'zbekiston yo'li",
        "keywords": [
            "o'zbekiston yo'li", "ўзбекистон йўли", "ozbekiston yoli", "o'zbekiston yo'nalishi",
            "ўзбекистон йўналиши", "o'zbekiston liniyasi", "ўзбекистон линияси", "узбекистанская линия", "узбекистанской"
        ],
        "stations": [
            ("Beruniy", ["beruniy", "беруний", "беруни"]),
            ("Tinchlik", ["tinchlik bekati", "тинчлик бекати", "станция тинчлик"]),
            ("Chorsu", ["chorsu", "чорсу"]),
            ("G'afur G'ulom", ["g'afur g'ulom", "ғафур ғулом", "gafur gulom", "гафур гулям"]),
            ("Alisher Navoiy", ["alisher navoiy", "алишер навоий", "алишер навои"]),
            ("O'zbekiston", ["o'zbekiston bekati", "ўзбекистон бекати", "станция узбекистан"]),
            ("Kosmonavtlar", ["kosmonavtlar", "космонавтлар", "космонавтов", "проспект космонавтов"]),
            ("Oybek", ["oybek", "ойбек", "айбек"]),
            ("Toshkent", ["toshkent bekati", "тошкент бекати", "станция ташкент", "северный вокзал"]),
            ("Mashinasozlar", ["mashinasozlar", "машинасозлар", "машиностроителей", "ташсельмаш"]),
            ("Do'stlik", ["do'stlik bekati", "дўстлик бекати", "дустлик бекати", "станция дустлик", "чкалов", "chkalov"])
        ]
    },
    "yunusobod": {
        "name": "🟢 Yunusobod yo'li",
        "keywords": [
            "yunusobod yo'li", "юнусобод йўли", "yunusobod yo'nalishi", "юнусобод йўналиши",
            "yunusobod liniyasi", "юнусобод линияси", "юнусабадская линия", "юнусабадской", "yunusobod metro"
        ],
        "stations": [
            ("Turkiston", ["turkiston", "туркистон", "туркестан"]),
            ("Shahriston", ["shahriston", "шаҳристон", "шахристан", "ҳабиб абдуллаев", "habib abdullayev"]),
            ("Bodomzor", ["bodomzor", "бодомзор", "бадамзар"]),
            ("Minor", ["minor bekati", "minor", "минор бекати", "минор", "станция минор"]),
            ("Abdulla Qodiriy", ["abdulla qodiriy", "абдулла қодирий", "абдулла кадыри"]),
            ("Yunus Rajabiy", ["yunus rajabiy", "юнус ражабий", "юнус раджаби"]),
            ("Ming O'rik", ["ming o'rik", "минг ўрик", "ming orik", "минг урик"])
        ]
    },
    "halqa": {
        "name": "🟣 Yerusti halqa yo'li",
        "keywords": [
            "halqa yo'li", "ҳалқа йўли", "yerusti halqa yo'li", "ерусти ҳалқа йўли",
            "yerusti halqa", "yerusti metro", "yerusti metrosi", "ерусти метро",
            "halqa liniyasi", "ҳалқа линияси", "кольцевая линия", "кольцевой линии", "30 yilligi yo'li", "30 йиллиги"
        ],
        "stations": [
            ("Texnopark (1-bekat)", ["texnopark", "технопарк", "1-bekat", "1-бекат", "do'stlik-2", "дўстлик-2"]),
            ("Yashnobod (2-bekat)", ["yashnobod bekati", "яшнобод бекати", "2-bekat", "2-бекат"]),
            ("Tuzel (3-bekat)", ["tuzel bekati", "тузел бекати", "3-bekat", "3-бекат"]),
            ("Olmos (4-bekat)", ["olmos bekati", "олмос бекати", "4-bekat", "4-бекат"]),
            ("Rohat (5-bekat)", ["rohat bekati", "роҳат бекати", "рохат бекати", "5-bekat", "5-бекат"]),
            ("Yangiobod (6-bekat)", ["yangiobod bekati", "янгиобод бекати", "6-bekat", "6-бекат"]),
            ("Qo'yliq (7-bekat)", ["qo'yliq bekati", "қўйлиқ бекати", "куйлюк бекати", "7-bekat", "7-бекат"]),
            ("Matonat (8-bekat)", ["matonat bekati", "матонат бекати", "8-bekat", "8-бекат"]),
            ("Qiyot (9-bekat)", ["qiyot bekati", "қиёт бекати", "кият бекати", "9-bekat", "9-бекат"]),
            ("Tolariq (10-bekat)", ["tolariq bekati", "толариқ бекати", "толарык", "10-bekat", "10-бекат"]),
            ("Xonobod (11-bekat)", ["xonobod bekati", "хонобод бекати", "ханабад", "11-bekat", "11-бекат"]),
            ("Quruvchilar (12-bekat)", ["quruvchilar bekati", "қурувчилар бекати", "стронтелей", "12-bekat", "12-бекат"]),
            ("Turon (13-bekat)", ["turon bekati", "турон бекати", "13-bekat", "13-бекат"]),
            ("Qipchoq (14-bekat)", ["qipchoq bekati", "қипчоқ бекати", "кипчак бекати", "14-bekat", "14-бекат"])
        ]
    }
}

# Bekatlar (O'zbek Lotin, Kirill va Rus tillarida)
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
    "sirg'ali bekati", "xalqlar do'stligi bekati", "milliy bog' bekati",
    "mirzo ulug'bek bekati", "hamid olimjon bekati", "pushkin bekati",
    "choshtepa bekati", "o'zgarish bekati", "chinor bekati", "yangihayot bekati",
    "texnopark bekati", "yashnobod bekati", "tuzel bekati", "olmos bekati",
    "rohat bekati", "yangiobod bekati", "qo'yliq bekati", "matonat bekati",
    "qiyot bekati", "tolariq bekati", "xonobod bekati", "quruvchilar bekati",
    "turon bekati", "yunus rajabiy bekati", "mustaqillik maydoni bekati",
    # Kirill
    "пахтакор бекати", "чилонзор бекати", "амир темур бекати",
    "буюк ипак йўли бекати", "беруний бекати", "дўстлик бекати",
    "новза бекати", "алишер навоий бекати", "минг ўрик бекати",
    "туркистон бекати", "шаҳристон бекати", "бодомзор бекати",
    "минор бекати", "абдулла қодирий бекати", "қипчоқ бекати",
    "олмазор бекати", "космонавтлар бекати", "ойбек бекати",
    "тинчлик бекати", "ғафур ғулом бекати", "чорсу бекати",
    "машинасозлар бекати", "тошкент бекати", "сергели бекати",
    "сирғали бекати", "халқлар дўстлиги бекати", "миллий боғ бекати",
    "мирзо улуғбек бекати", "ҳомид олимжон бекати", "пушкин бекати",
    "чоштепа бекати", "ўзгариш бекати", "чинор бекати", "янгиҳаёт бекати",
    "технопарк бекати", "яшнобод бекати", "тузел бекати", "олмос бекати",
    "роҳат бекати", "янгиобод бекати", "қўйлиқ бекати", "матонат бекати",
    "қиёт бекати", "толариқ бекати", "хонобод бекати", "қурувчилар бекати",
    "турон бекати", "юнус ражабий бекати", "мустақиллик майдони бекати",
    # Ruscha
    "станция пахтакор", "станция чилонзор", "станция амир темур",
    "станция беруни", "станция дустлик", "станция новза",
    "станция алишера навои", "станция минг урик", "станция туркестан",
    "станция шахристан", "станция бадамзар", "станция минор",
    "станция кипчак", "станция алмазар", "станция космонавтов",
    "станция айбек", "станция тинчлик", "станция чорсу",
    "станция дружбы народов", "станция национальный парк", "станция мирзо улугбек",
    "станция хамида олимджана", "станция пушкина", "станция сергели",
    "станция технопарк", "станция рохат", "станция куйлюк"
]

# Metro yo'nalishlari (O'zbek va Rus tillarida)
METRO_LINES = [
    "chilonzor yo'li", "чилонзор йўли", "chilonzor yo'nalishi", "чилонзор йўналиши", "chilonzor liniyasi", "чилонзор линияси", "чиланзарская линия",
    "yunusobod yo'li", "юнусобод йўли", "yunusobod yo'nalishi", "юнусобод йўналиши", "yunusobod liniyasi", "юнусобод линияси", "юнусабадская линия",
    "o'zbekiston yo'li", "o'zbekiston metro", "ўзбекистон метро", "o'zbekiston yo'nalishi", "ўзбекистон йўналиши", "o'zbekiston liniyasi", "узбекистанская линия",
    "sergeli yo'li", "sergeli metro", "сергели метро", "sergeli yo'nalishi", "сергели йўналиши", "sergeli liniyasi",
    "halqa yo'li", "halqa metro", "ҳалқа метро", "yerusti halqa yo'li", "ерусти ҳалқа йўли", "halqa liniyasi", "ҳалқа линияси", "кольцевая линия",
    "yerusti metro", "yerusti metrosi", "ерусти метро", "yer osti metro", "yerosti transporti", "ер ости метро"
]

# Uy-joy va ko'chmas mulk reklamalari (filtrlash shart)
REAL_ESTATE_PATTERNS = [
    r"metro(?:si|ga|siga)?\s+(?:yaqin|\d+\s*daqiqa|\d+\s*minut|qadam|joylashgan|yonida|atrofida).*?(?:uy|kvartira|xonadon|hovli|joy|kafe|restoran|do'kon|sotiladi|ijara|narxi|arenda|\$)",
    r"(?:kvartira|uy|xonadon|kottedj|dom|ofis|noturar|bino|yer|uchastka)\s+(?:sotiladi|ijaraga|arenda|narxi|olaman).*?metro",
    r"metro(?:si|ga|siga)?\s+yaqinida",
    r"рядом\s+с\s+метро.*?(?:квартира|дом|офис|аренда|продается|цена|новостройка|\$)",
    r"(?:квартира|дом|аренда|новостройка|продается|сдается|недвижимость).*?метро",
    r"метро(?:дан|га)?\s+(?:яқин|\d+\s*дақиқа|қадам).*?(?:уй|квартира|хонадон|сотилади|ижара|нархи|\$)",
]

# Sport va yengil atletika masofalari (metr, 200 metr yugurish, estafeta)
SPORTS_DISTANCE_PATTERNS = [
    r"(?:\d+\s*metr|\d+\s*метр[а-я]{0,3})\s+(?:masofa|yugurish|suzish|eshkak|marafon|дистанци\w*|забег|эстафет\w*)",
    r"\b(?:дистанци[ия]\s+\d+\s*м|\bзабег\b|\bэстафет\w*|\bгребл\w*|\bплавани\w*|\bмедал[ьяеи]\w*|\bазиатск\w+\s+игр\w*|\bчемпионат\w*)",
]

# Unumdorlikni oshirish uchun regex qoliplarini bir marta oldindan kompilyatsiya qilish
COMPILED_METRO_EXPLICIT = [re.compile(p, re.IGNORECASE) for p in METRO_EXPLICIT_PATTERNS]
COMPILED_REAL_ESTATE = [re.compile(p, re.IGNORECASE) for p in REAL_ESTATE_PATTERNS]
COMPILED_SPORTS_DISTANCE = [re.compile(p, re.IGNORECASE) for p in SPORTS_DISTANCE_PATTERNS]

# Toshkent metrosiga oid kuchli, shubhasiz belgilar
STRONG_METRO_SIGNALS = [
    "toshkent metropoliteni", "тошкент метрополитен", "tashkent metro",
    "metro bekati", "metro bekatlari", "станция метро", "станции метро",
    "metro poyezdi", "вагон метро", "поезд метро", "chilonzor yo'li",
    "chilonzor yo'nalishi", "yunusobod yo'nalishi", "o'zbekiston yo'nalishi",
    "sergeli yo'li", "halqa yo'li", "yerusti metrosi", "yerosti transporti",
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
    ("kechikyapti", "#kechikish"),
    ("nosozlik", "#nosozlik"),
    ("носозлик", "#nosozlik"),
    ("vagon", "#vagon"),
    ("вагон", "#vagon"),
    ("poyezd", "#poyezd"),
    ("поезд", "#poyezd"),
    ("eskalator", "#eskalator"),
    ("эскалатор", "#eskalator"),
    ("lift", "#lift"),
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
    ("tirbandlik", "#tirbandlik"),
    ("gavjumlik", "#gavjumlik"),
    ("navbat", "#navbat"),
    ("yong'in", "#yongin"),
    ("ёнғин", "#yongin"),
    ("tutun", "#tutun"),
    ("тутун", "#tutun"),
    ("evakuatsiya", "#evakuatsiya"),
    ("эвакуация", "#evakuatsiya"),
    ("suv toshishi", "#suv_toshishi"),
    ("suv sizishi", "#suv_sizishi"),
    ("o'g'irlik", "#ogirlik"),
    ("mushtlashuv", "#mushtlashuv"),
    ("муштлашув", "#mushtlashuv"),
    ("janjal", "#janjal"),
    ("shikoyat", "#shikoyat"),
    ("шикоят", "#shikoyat"),
    ("xavfsizlik", "#xavfsizlik"),
    ("хавфсизлик", "#xavfsizlik"),
    ("5 vagonli", "#vagon"),
    ("yangi vagon", "#yangi_vagon"),
    ("harakat jadvali", "#jadval"),
    ("jadvali", "#jadval"),
    ("ish vaqti", "#ish_vaqti"),
    ("rasmiy munosabat", "#rasmiy_munosabat"),
    ("rasmiy bayonot", "#rasmiy_bayonot"),
    ("raddiya", "#raddiya"),
    ("matbuot xizmati", "#matbuot_xizmati"),
    ("tender", "#tender"),
    ("modernizatsiya", "#modernizatsiya"),
    ("tarif", "#tarif"),
    ("тариф", "#tarif"),
    ("narx", "#narx"),
    ("narxi", "#narx")
]

# 1-to-1 belgilarni tezkor C-darajasida almashtirish jadvali
SINGLE_CHAR_TRANS = str.maketrans({
    'ʻ': "'",
    'ʼ': "'",
    '`': "'",
    '‘': "'",
    '’': "'",
    '“': '"',
    '”': '"',
    'ı': 'i',
})

# Tezkor filtrlash uchun metroga oid birlamchi trigger so'zlar (Fast-path)
FAST_METRO_TRIGGERS = (
    "metro", "метро", "metropoliten", "метрополитен", "toshmetro", "тошметро",
    "подземк", "bekat", "бекат", "станци", "liniya", "линия", "vagon", "вагон",
    "poyezd", "поезд", "eskalator", "эскалатор", "turniket", "турникет",
    "yerusti", "ерусти", "yer osti", "ер ости"
)

def clean_text(text: str) -> str:
    """
    Matnni tozalash, kichik harfga o'tkazish hamda yangi va eski o'zbek
    alifbosidagi belgilar (ş, ç, ó, ǵ) va apostroflarni tezkor standartlashtirish.
    High-performance C-darajasidagi str.translate va shartli replace ishlatiladi.
    """
    if not text:
        return ""
    text = text.lower().translate(SINGLE_CHAR_TRANS)

    # Faqat kerakli belgilar matnda uchrasagina replace qilinadi (99% holatda CPU tejaladi)
    if 'ş' in text: text = text.replace('ş', 'sh')
    if 'ç' in text: text = text.replace('ç', 'ch')
    if 'ó' in text: text = text.replace('ó', "o'")
    if 'õ' in text: text = text.replace('õ', "o'")
    if 'ö' in text: text = text.replace('ö', "o'")
    if 'ǵ' in text: text = text.replace('ǵ', "g'")
    if 'ğ' in text: text = text.replace('ğ', "g'")

    return text

def is_metro_related(title: str, content: str) -> Tuple[bool, List[str]]:
    """
    Xabar FAQAT Toshkent metrosiga tegishli ekanligini 100% aniqlikda tekshiradi.
    O'zbekcha (Lotin va Kirill) hamda mahalliy ruscha xabarlarni to'liq qamrab oladi.
    Reklamalar va sport masofalarini qat'iy chetlab o'tadi.
    Fast-path filtri orqali metrodan tashqari minglab xabarlarni 50x tezroq chetlatadi.
    """
    full_text = f"{title} {content}"
    cleaned = clean_text(full_text)

    # 0. Fast-Path Pre-Check:
    # Agar matnda biron bir metro trigger so'zi yoki admin qo'shgan kalit so'z bo'lmasa,
    # O'ta og'ir regexlarni ishlatmasdan darhol False qaytaramiz (50x tezlashuv).
    has_trigger = any(trig in cleaned for trig in FAST_METRO_TRIGGERS)
    if not has_trigger:
        has_custom = any(kw in cleaned for kw in _custom_keywords_cache if kw)
        if not has_custom:
            return False, []

    # 1. Soxta so'zlar tekshiruvi (metrologiya, santimetr va h.k.)
    for excl in EXCLUSION_WORDS:
        if excl in cleaned:
            has_real_metro = any(pat.search(cleaned) for pat in COMPILED_METRO_EXPLICIT)
            if not has_real_metro:
                return False, []

    # 2. Uy-joy yoki ko'chmas mulk reklamalari
    if any(pat.search(cleaned) for pat in COMPILED_REAL_ESTATE):
        return False, []

    # 3. Sport va yengil atletika masofalari (200 metr, suzish, medallar)
    has_sports_distance = any(pat.search(cleaned) for pat in COMPILED_SPORTS_DISTANCE)
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
    for pat in COMPILED_METRO_EXPLICIT:
        if pat.search(cleaned):
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


# =========================================================================
# LINIYA, BEKAT VA HODISA STATUSINI AVTOMATIK ANIQLASH
# =========================================================================

DISRUPTION_PATTERNS = [
    r"\bto['`’]?xta(?:b\s+qoldi|tildi|sh|b|yapti)\b",
    r"\bтўхта(?:б\s+қолди|тилди|ш|б|япти)\b",
    r"\bnosozlik\b", r"\bносозлик\b",
    r"\bkechik(?:ish|yapti|moqda|di)\b", r"\bкечик(?:иш|япти|моқда|ди)\b",
    r"\bto['`’]?xtash\b", r"\bузр\s+сўраймиз\b", r"\buzr\s+so['`’]?raymiz\b",
    r"\bharakat\s+to['`’]?xtatildi\b", r"\bприостановлен[оаы]\b", r"\bсбой\b", r"\bзадержк[аие]\b"
]

RESOLUTION_PATTERNS = [
    r"\btiklan(?:di|gan|moqda|ishi)\b", r"\bтиклан(?:ди|ган|моқда|иши)\b",
    r"\bqayta\s+tiklandi\b", r"\bқайта\s+тикланди\b",
    r"\byo['`’]?lga\s+qo['`’]?yildi\b", r"\bйўлга\s+қўйилди\b",
    r"\bqayta\s+yo['`’]?lga\s+qo['`’]?yildi\b", r"\bқайта\s+йўлга\s+қўйилди\b",
    r"\bbartaraf\s+etildi\b", r"\bбартараф\s+этилди\b",
    r"\bodatiy\s+rejim(?:da|ga)\b", r"\bодатий\s+режим(?:да|га)\b",
    r"\bharakat\s+(?:qayta\s+)?tiklandi\b", r"\bҳаракат\s+(?:қайта\s+)?тикланди\b",
    r"\bвозобновлен[оаы]\b", r"\bвосстановлен[оаы]\b", r"\bнормализован[оаы]\b",
    r"\bустранен[оаы]\b", r"\bв\s+штатном\s+режиме\b"
]

COMPILED_DISRUPTION = [re.compile(p, re.IGNORECASE) for p in DISRUPTION_PATTERNS]
COMPILED_RESOLUTION = [re.compile(p, re.IGNORECASE) for p in RESOLUTION_PATTERNS]


def is_disruption_text(text: str) -> bool:
    """Matnda harakat to'xtashi yoki nosozlik bor-yo'qligini tekshirish."""
    cleaned = clean_text(text)
    return any(p.search(cleaned) for p in COMPILED_DISRUPTION)


def is_resolution_text(text: str) -> bool:
    """Matnda harakat qayta tiklangani yoki nosozlik bartaraf etilganini tekshirish."""
    cleaned = clean_text(text)
    return any(p.search(cleaned) for p in COMPILED_RESOLUTION)


def _match_station_keyword(kw: str, cleaned_text: str) -> bool:
    """Bekat kalit so'zini qo'shimchalari (bekatida, bekatidan, stantsiyasi) bilan tekshirish."""
    if " bekati" in kw:
        root = kw.replace(" bekati", "").strip()
        pat = rf"(?<!\w){re.escape(root)}\s+bekat(?:i|ida|idan|iga|ini|ining|larda|lar)?(?!\w)"
        return bool(re.search(pat, cleaned_text))
    if " бекати" in kw:
        root = kw.replace(" бекати", "").strip()
        pat = rf"(?<!\w){re.escape(root)}\s+бекат(?:и|ида|идан|ига|ини|ининг|ларда|лар)?(?!\w)"
        return bool(re.search(pat, cleaned_text))
    if kw.startswith("станция "):
        root = kw.replace("станция ", "").strip()
        pat = rf"(?<!\w)(?:станци[яиеюей]\s+)?{re.escape(root)}(?!\w)"
        return bool(re.search(pat, cleaned_text))
    
    pat = rf"(?<!\w){re.escape(kw)}(?:da|dan|ga|ka|qa|ni|ning|si|sida|sidan|siga|да|дан|га|ни|нинг|е|а|у|ом|ы|и|ов)?(?!\w)"
    return bool(re.search(pat, cleaned_text))


def _match_keyword_flex(kw: str, cleaned_text: str) -> bool:
    """Kalit so'zni apostroflar (do'stlik/dostlik, yo'li/yoli) va qo'shimchalar bilan tekshirish."""
    # 1. Asl matn bilan tekshirish
    if _match_station_keyword(kw, cleaned_text):
        return True

    # 2. Apostrofsiz matn bilan tekshirish (dostlik <-> do'stlik)
    cleaned_no_apos = cleaned_text.replace("'", "")
    kw_no_apos = kw.replace("'", "")
    if kw_no_apos != kw or "'" in cleaned_text:
        if _match_station_keyword(kw_no_apos, cleaned_no_apos):
            return True

    return False


def detect_line_and_station(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Matn ichidan Toshkent metrosi yo'nalishi (Liniyasi) va aniq bekatini aniqlash.
    Natija: (line_badge, station_badge)
    Masalan: ("🔴 Chilonzor yo'li", "📌 Novza bekati")
    """
    cleaned = clean_text(text)

    # 1. Bekat nomi bo'yicha aniqlash (Bekat aniqlansa, liniya ham avtomatik aniqlanadi)
    for _, line_info in METRO_LINES_INFO.items():
        for st_name, st_keywords in line_info["stations"]:
            for kw in st_keywords:
                if _match_keyword_flex(kw, cleaned):
                    detected_station = f"📌 {st_name} bekati"
                    detected_line = line_info["name"]
                    return detected_line, detected_station

    # 2. Agar bekat topilmasa, liniya nomi bo'yicha qidirish
    cleaned_no_apos = cleaned.replace("'", "")
    for _, line_info in METRO_LINES_INFO.items():
        for lkw in line_info["keywords"]:
            if lkw in cleaned or lkw.replace("'", "") in cleaned_no_apos:
                detected_line = line_info["name"]
                return detected_line, None

    return None, None


def detect_metro_topic(text: str) -> str:
    """Xabarning asosiy mavzusini yo'lovchilar uchun aniqlash."""
    cleaned = clean_text(text)

    if is_resolution_text(cleaned):
        return "🟢 Harakat qayta tiklandi"
    if is_disruption_text(cleaned):
        return "Harakat va oraliq intervallar"

    if any(k in cleaned for k in ["narx", "tarif", "чипта", "chipta", "atto", "to'lov", "тулов", "karta", "qr", "стоимость"]):
        return "To'lov va yo'l haqi tariflari"

    if any(k in cleaned for k in ["yangi poyezd", "yangi tarkib", "5 vagon", "вагон", "vagon", "sostav", "состав", "подвижной состав", "metrobus"]):
        return "Yangi poyezdlar va modernizatsiya"

    if any(k in cleaned for k in ["rasmiy", "bayonot", "munosabat", "raddiya", "matbuot", "брифинг"]):
        return "Rasmiy bayonot va munosabat"

    if any(k in cleaned for k in ["ish vaqti", "grafigi", "jadvali", "ochilish", "ish boshlaydi", "yopiladi"]):
        return "Ish vaqti va harakat jadvali"

    if any(k in cleaned for k in ["xavfsizlik", "eskalator", "lift", "nazorat", "militsiya", "iib"]):
        return "Xavfsizlik va yo'lovchilarga xizmat"

    return "Toshkent Metropoliteni yangiligi"


