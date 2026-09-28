import os
import sys
import asyncio
import logging
import httpx
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

health_runner = None

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
    global health_runner
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="🚇 Metro News Monitoring Bot is Running 24/7!"))
    app.router.add_get("/health", lambda req: web.Response(text="OK"))
    health_runner = web.AppRunner(app)
    await health_runner.setup()
    site = web.TCPSite(health_runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check veb server {port}-portda ishga tushirildi.")

async def keep_alive_loop():
    """
    Render Free Web Service 15 daqiqada uxlab (spin down) qolmasligi uchun
    har 7 daqiqada serverning /health manziliga so'rov yuborib, uyg'oq ushlab turadi.
    """
    await asyncio.sleep(60)  # Server to'liq ko'tarilishini kutish
    external_url = (
        os.environ.get("RENDER_EXTERNAL_URL") or 
        os.environ.get("SELF_PING_URL") or 
        "https://metro-news-bot.onrender.com"
    ).rstrip("/")
    health_url = f"{external_url}/health"
    logger.info(f"Keep-alive self-ping xizmati ishga tushdi: {health_url}")

    while True:
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    logger.info("Keep-alive ping muvaffaqiyatli: Server 24/7 faol holatda.")
                else:
                    logger.warning(f"Keep-alive ping status: {resp.status_code}")
        except Exception as e:
            logger.debug(f"Keep-alive ping xatosi (qayta uriniladi): {e}")

        # Har 7 daqiqada (420 soniya) ping yuborish (Render 15 daqiqada uxlaydi)
        await asyncio.sleep(420)

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

    # Avvalgi webhook va qolib ketgan xabarlarni tozalash (polling xatosiz boshlanishi uchun)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook tozalandi va kutayotgan eski yangilanishlar olib tashlandi.")
    except Exception as e:
        logger.warning(f"Webhook tozalashda xatolik: {e}")

    # Orqa fondagi monitoring vazifasini ishga tushirish
    monitor_task = asyncio.create_task(monitor_background_loop(bot))
    # Render uxlamasligi uchun keep-alive vazifasi
    keep_alive_task = asyncio.create_task(keep_alive_loop())

    logger.info(
        f"Metro Monitoring Bot muvaffaqiyatli ishga tushdi! "
        f"Adminlar: {settings.admin_id_list}"
    )

    try:
        # Bot pollingni uzluksiz, avtomatik qayta tiklanuvchi rejimda boshlash
        while True:
            try:
                await dp.start_polling(bot, handle_signals=False)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Telegram pollingda kutilmagan uzilish: {exc}. 5 soniyadan so'ng qayta ulanadi...")
                await asyncio.sleep(5)
    finally:
        monitor_task.cancel()
        keep_alive_task.cancel()
        if health_runner:
            await health_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")

