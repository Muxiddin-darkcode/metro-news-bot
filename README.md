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

## 🎮 Admin Buyruqlari

Adminlar Telegram orqali botga quyidagi komandalarni berishi mumkin:
- `/start` — Tizim bilan tanishuv va tezkor klaviatura;
- `/status` — Tizim holati (oxirgi tekshiruv vaqti, qancha soniya ketgani, keshdagi xabarlar soni);
- `/check` — 80 ta manbani navbatdan tashqari darhol tekshirish;
- `/sources` — Hozirda kuzatilayotgan 40 ta kanal va 40 ta sayt ro'yxati;
- `/keywords` — Hozirgi filtr kalit so'zlari.

---

## 🧪 Testlarni Ishga Tushirish

Filtr, kirill/lotin tahlili va kross-dublikat algoritmlarini tekshirish uchun:
```powershell
.\.venv\Scripts\python -m unittest tests/test_monitor.py
```
