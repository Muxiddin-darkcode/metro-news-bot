# 🚇 Metro News Monitoring Telegram Bot

Ushbu loyiha internet tarmoqlaridagi (40 ta yirik Telegram kanal va 40 ta yangilik veb-sayti, jami **80 ta manba**) barcha ma'lumotlar oqimini 24/7 rejimida asinxron kuzatib boradi. 
**Toshkent metropoliteni**ga oid har qanday xabar, nosozlik, kechikish, vagonlar yoki yangiliklar internetda paydo bo'lishi bilanoq:
1. **Tezkor ushlaydi** (Asinxron parallel worker pool orqali);
2. **Kross-manbali matn o'xshashligi (Cross-source Semantic Deduplication)** orqali tekshiradi — agar bir xil voqeani bir vaqtda bir nechta OAV yozsa, adminga faqat **1 marta** (birinchi e'lon qilgan manbadan) boradi, takrorlar bloklanadi;
3. **Faqat 2 ta mas'ul admin**ning shaxsiy Telegramiga havola va to'liq tafsilotlar bilan alert yuboradi;
4. **No-DB**: Hech qanday og'ir ma'lumotlar bazasi talab qilinmaydi. Xotirada LRU Cache va `data/seen_posts.json` faylidan foydalanadi. Begona foydalanuvchilar botga kira olmaydi.

---

## 📁 Loyiha Tuzilmasi

```text
Metro News/
│
├── config.py                 # Konfiguratsiya (.env o'qish, Admin ID lar, sozlamalar)
├── main.py                   # Asosiy kirish nuqtasi (aiogram 3 bot + 24/7 monitoring loop)
│
├── bot/
│   ├── handlers.py           # Admin buyruqlari (/start, /status, /check, /sources, /keywords)
│   ├── notifier.py           # Adminga chiroyli alert jo'natuvchi xizmat
│   └── middlewares.py        # 2 ta admindan boshqalarni 100% cheklovchi xavfsizlik
│
├── core/
│   ├── ai_analyzer.py        # Dual AI Tahlilchi (Gemini API + OpenRouter Fallback)
│   ├── filter.py             # Metro so'z boyligi va bekatlar filtri (Lotin va Krill)
│   ├── deduplicator.py       # Kross-manbali matn o'xshashligi tahlili (Stemming + Jaccard/Overlap)
│   └── storage.py            # No-DB: Dublikatlardan himoya (xotira keshi + disk)
│
├── parsers/
│   ├── base.py               # NewsItem ma'lumot modeli
│   ├── telegram_channels.py  # 40 ta Telegram kanalni t.me/s/... orqali sessiyasiz o'quvchi
│   ├── web_scrapers.py       # 40 ta OAV saytlarini RSS va HTML orqali o'quvchi
│   └── manager.py            # 80 ta manbani Semaphore (15-20 parallel oqim) bilan boshqaruvchi
│
├── data/
│   ├── sources.json          # 40 ta Telegram kanal va 40 ta Veb-sayt ro'yxati
│   ├── seen_posts.json       # Avval ko'rilgan xabarlar arxivi (avtomatik yangilanadi)
│   └── seen_fingerprints.json# Oxirgi 24 soatlik voqealar izi (antidublikat uchun)
│
├── tests/
│   ├── test_ai_analyzer.py   # AI tahlilchi, fallback va HTML formatlash testlari
│   └── test_monitor.py       # Birlik testlar (Filtr, Antidublikat, Kross-o'xshashlik)
│
├── requirements.txt          # Kerakli Python kutubxonalari
├── .env.example              # Sozlamalar namunasi
└── .env                      # Sizning shaxsiy Telegram Token va Admin ID laringiz
```

---

## ⚙️ O'rnatish va Sozlash

### 1. Kutubxonalarni o'rnatish:
```powershell
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. `.env` faylini sozlash:
Loyiha papkasidagi `.env` faylini oching va quyidagi parametrlarni kiriting:

```env
# Telegram @BotFather dan olingan bot tokeni
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# 2 ta mas'ul adminning Telegram User ID lari (vergul bilan ajrating)
# O'z IDingizni Telegramdagi @userinfobot orqali bilib olishingiz mumkin
ADMIN_IDS=123456789,987654321

# Barcha 80 ta manbani tekshirish oralig'i (soniyalarda, default: 60)
CHECK_INTERVAL_SECONDS=60

# Bir vaqtning o'zida nechta manba parallel so'ralishi
MAX_CONCURRENT_REQUESTS=15

# Kross-dublikat o'xshashlik chegarasi (0.65 = 65%)
SIMILARITY_THRESHOLD=0.65

# AI Tahlilchi sozlamalari (Gemini + OpenRouter Fallback)
AI_ENABLED=True
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-1.5-flash
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
```

---

## 🚀 Ishga Tushirish

Botni ishga tushirish uchun quyidagi buyruqni bering:

```powershell
.\.venv\Scripts\python main.py
```

Bot ishga tushishi bilanoq:
1. `aiogram 3` orqali 2 ta admin bilan muloqotga tayyor bo'ladi;
2. Fondagi asinxron vazifa har daqiqada barcha 80 ta manbani tekshirib turadi;
3. Yangi metro xabari topilganda ikkala adminga darhol xabar va asl havola yetkaziladi.

---

## 🎮 Kengaytirilgan Admin Imkoniyatlari va Buyruqlari

Adminlar Telegram orqali zamonaviy **Inline Dashboard** va qulay Reply klaviatura yordamida quyidagi buyruqlardan foydalanishi mumkin:

- `/panel` (yoki `/admin`, `🎛️ Boshqaruv paneli`) — Asosiy interaktiv admin boshqaruv paneli (Dashboard);
- `/start` — Tizim bilan tanishuv, asosiy menyu va tezkor klaviatura;
- `/today` (`📅 Bugungi yangiliklar`) — Bugun O'zbekiston vaqti bilan topilgan barcha yangiliklarni AI xulosalari bilan birga ko'rish;
- `/status` — Tizim holati (monitoring holati, tekshiruv vaqti, kesh va antidublikat statistikasi);
- `/check` — Barcha manbalarni navbatdan tashqari parallel tekshirish va yangi xabarlarni darhol jo'natish;
- `/sources` — Manbalar boshqaruvi (Telegram kanallarni va saytlarni sahifalab ko'rish, yangi kanal qo'shish, o'chirish va bittalab testlash);
- `/keywords` — Filtr kalit so'zlari hamda yangi maxsus metro kalit so'zlarini qo'shish/o'chirish;
- `/history` (yoki `/news`, `📰 So'nggi xabarlar`) — Oxirgi 24 soatda aniqlangan yangi metro hodisalari ro'yxati;
- `/logs` (`📋 So'nggi loglar`) — Botning so'nggi jonli loglarini Telegram orqali ko'rish va yangilab turish;
- `/settings` (`⚙️ Sozlamalar`) — Monitoringni vaqtincha to'xtatish (Pause/Resume), tekshirish oralig'ini (30s, 60s, 120s, 300s) va dublikat sezgirligini (0.50, 0.65, 0.75, 0.85) to'g'ridan-to'g'ri sozlash;
- `/ping` (yoki `/diag`) — Telegram API kechikishi (ping), server vaqti (UTC+5) va diagnostika ma'lumotlari;
- `/test_alert` — Namuna tariqasida haqiqiy ko'rinishdagi test metro xabarnomasini jo'natish;
- `/ai` (yoki `/ai_test`) — AI tahlilini namunaviy xabar yoki o'z matningiz orqali sinab ko'rish;
- `/id` — Chat yoki Guruh ID sini aniqlash (guruhga qo'shib /id yozilsa, uning ID sini beradi);
- **AI Tahlilchi Boshqaruvi** — Admin paneldan AI holatini ko'rish, yoqish/o'chirish, Gemini va OpenRouter provayderlarini tekshirish;
- **Keshni tozalash** — Keshdagi ko'rilgan xabarlar yoki antidublikat izlarini xavfsiz tozalash.



---

## 🧪 Testlarni Ishga Tushirish

1. **AI Tahlilchi va Fallback testi:**
```powershell
.\.venv\Scripts\python tests/test_ai_analyzer.py
```

2. **Filtr, kirill/lotin tahlili va kross-dublikat algoritmlarini tekshirish:**
```powershell
.\.venv\Scripts\python -m unittest tests/test_monitor.py
```
