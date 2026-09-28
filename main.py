import os
import sys
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import settings, logger
from core.storage import storage
from core.deduplicator import deduplicator
from parsers.manager import source_manager
from bot.middlewares import AdminOnlyMiddleware
from bot.handlers import router as admin_router
from bot.notifier import send_metro_alert

async def monitor_background_loop(bot: Bot):
    """
    24/7 orqa fonda ishlovchi asinxron kuzatuvchi.
    Har CHECK_INTERVAL_SECONDS (masalan 60s) vaqtda barcha 80 ta manbani
    tekshirib, yangi metro xabarlarini darhol 2 ta adminga yetkazadi.
    """
    logger.info("Asinxron monitoring tsikli ishga tushirildi...")
    
    # Dastlabki yuklanishda kutish (bot to'liq ishga tushishi uchun)
    await asyncio.sleep(3)

    while True:
        try:
            logger.info("Manbalar bo'yicha navbatdagi tekshiruv boshlanmoqda...")
            new_alerts, stats = await source_manager.scan_all_sources()

            if new_alerts:
                logger.info(f"🚨 {len(new_alerts)} ta yangi metro xabari topildi! Adminlarga yuborilmoqda...")
                for item in new_alerts:
                    await send_metro_alert(bot, item)
            else:
                logger.info("Yangi metro xabarlari aniqlanmadi.")

        except asyncio.CancelledError:
            logger.info("Monitoring tsikli to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"Monitoring tsiklida kutilmagan xatolik: {e}", exc_info=True)

        # Keyingi tekshiruvgacha kutish
        await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)

async def start_health_server():
    """Render va boshqa bulutli serverlar uchun bepul HTTP port eshituvchisi."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="🚇 Metro News Monitoring Bot is Running 24/7!"))
    app.router.add_get("/health", lambda req: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check veb server {port}-portda ishga tushirildi.")

async def run_bot():
    """Asosiy bot va monitoringni ishga tushirish funksiyasi."""
    # Render yoki bulutli serverlarda HTTP port ochish
    if "PORT" in os.environ:
        await start_health_server()
    token = settings.BOT_TOKEN
    
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.warning(
            "\n" + "="*70 + "\n"
            "DIQQAT: .env faylida BOT_TOKEN ko'rsatilmagan!\n"
            "Iltimos, Telegram @BotFather dan olgan bot tokeningizni .env fayliga kiriting.\n"
            "Admin ID laringizni ham ADMIN_IDS qatoriga yozing.\n"
            "="*70
        )
        # Agar bot token hali kiritilmagan bo'lsa, monitoring tizimini konsol test rejimida sinab ko'ramiz
        logger.info("Sinov (Test-Scan) rejimida 80 ta manbani bir marta to'liq skanerlab ko'ramiz...")
        alerts, stats = await source_manager.scan_all_sources()
        print("\n--- TEKSHIRUV STATISTIKASI ---")
        for k, v in stats.items():
            print(f"{k}: {v}")
        if alerts:
            print(f"\nTopilgan metro xabarlari ({len(alerts)} ta):")
            for a in alerts:
                print(f"[{a.source_name}] {a.title} ({a.url})")
        else:
            print("\nUshbu so'nggi xabarlar orasida metroga oid yangilik topilmadi.")
        return

    # aiogram Bot va Dispatcher yaratish
    bot = Bot(token=token)
    dp = Dispatcher()

    # Xavfsizlik: Begonalarni cheklovchi middleware
    dp.message.middleware(AdminOnlyMiddleware())
    dp.include_router(admin_router)

    # Orqa fondagi monitoring vazifasini ishga tushirish
    monitor_task = asyncio.create_task(monitor_background_loop(bot))

    logger.info(
        f"Metro Monitoring Bot muvaffaqiyatli ishga tushdi! "
        f"Adminlar: {settings.admin_id_list}"
    )

    try:
        # Bot pollingni boshlash
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
