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
from database import init_db
from handlers import start, services, orders, worker, admin

logging.basicConfig(level=logging.INFO)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="cancel", description="Bekor qilish"),
    ]
    if ADMIN_IDS:
        commands.append(BotCommand(command="admin", description="Admin panel (Bot ichida)"))
    await bot.set_my_commands(commands)

async def main():
    # Initialize database
    init_db()
    
    # Create bot and dispatcher
    from aiogram.client.default import DefaultBotProperties
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Include routers
    dp.include_router(start.router)
    dp.include_router(services.router)
    dp.include_router(orders.router)
    dp.include_router(worker.router)
    dp.include_router(admin.router)
    
    # Set commands
    await set_commands(bot)
    
    # Start polling
    print("Bot ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
