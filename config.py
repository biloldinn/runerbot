import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

DB_PATH = os.path.join(BASE_DIR, "turon_bot.db")

# To'lov uchun karta raqami
CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 1234 5678 9012")
CARD_OWNER = os.getenv("CARD_OWNER", "TURON OQUV MARKAZI")

# Bot sozlamalari
BOT_NAME = "Turon Kompyuter Xizmati"
BOT_DESCRIPTION = "Kompyuter xizmatlariga oldindan buyurtma berish tizimi"
WEBAPP_URL = os.getenv("WEBAPP_URL") # E.g., https://your-domain.com/
