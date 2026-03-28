import asyncio
import logging
import os
import sys

# Move project root to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import (
    init_db, get_all_users, check_and_lock_instance, 
    update_heartbeat, release_lock
)
from handlers import start, services, orders, worker, admin
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def send_daily_notification(bot: Bot):
    # Bugun haftaning qaysi kuni? (0-Dushanba, 6-Yakshanba)
    if datetime.now().weekday() == 6:
        return # Yakshanba kuni yubormaslik
        
    users = await get_all_users()
    text = (
        "☀️ **Assalomu alaykum!**\n\n"
        "🏢 Turon kompyuter xizmatlari o'z ishini boshladi!\n"
        "Bugun soat 18:00 ga qadar xizmatingizdamiz.\n\n"
        "💻 Xizmatlarimizdan foydalanish uchun /start bosing."
    )
    
    for user in users:
        try:
            await bot.send_message(user['telegram_id'], text, parse_mode="Markdown")
            await asyncio.sleep(0.05) # Telegram limitlaridan oshib ketmaslik uchun
        except Exception:
            continue

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="cancel", description="Bekor qilish"),
    ]
    if ADMIN_IDS:
        commands.append(BotCommand(command="admin", description="Admin panel (Bot ichida)"))
    await bot.set_my_commands(commands)

from aiogram.client.default import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def heartbeat_loop():
    while True:
        await update_heartbeat()
        await asyncio.sleep(60)

async def main():
    # Initialize database
    await init_db()
    
    # Conflict prevention: Check if another instance is running
    is_locked = await check_and_lock_instance()
    if not is_locked:
        logging.error("CRITICAL: Another bot instance is already running! Exiting to prevent conflict.")
        return

    try:
        # Start heartbeat
        asyncio.create_task(heartbeat_loop())
        
        # Include routers
        dp.include_router(start.router)
        dp.include_router(services.router)
        dp.include_router(orders.router)
        dp.include_router(worker.router)
        dp.include_router(admin.router)
        
        # Setup scheduler
        scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
        scheduler.add_job(send_daily_notification, 'cron', hour=8, minute=0, args=[bot])
        scheduler.start()

        # Set commands
        await set_commands(bot)
        
        # Start polling
        logging.info("--- TURON BOT STARTED ---")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await release_lock()
        logging.info("--- TURON BOT STOPPED ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
