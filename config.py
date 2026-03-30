import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_TOKEN = "8735699118:AAFwDVP2TX6p8qaQPZ5NRTRy8O-dJRpx73Q"
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

MONGODB_URI = "mongodb+srv://bilol:bilol006@cluster0.hdolzub.mongodb.net/turon_zakas?retryWrites=true&w=majority&appName=Cluster0"
DATABASE_NAME = "turon_zakas"
# DB_PATH olib tashlandi, MongoDB ishlatiladi.

# To'lov uchun karta raqami
CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 1234 5678 9012")
CARD_OWNER = os.getenv("CARD_OWNER", "TURON OQUV MARKAZI")

# Bot sozlamalari
BOT_NAME = "Turon Buyurtma Bot"
BOT_DESCRIPTION = "Kompyuter va boshqa xizmatlarga buyurtma berish tizimi"
_env_url = os.getenv("WEBAPP_URL", "")
if "vercel.app" in _env_url:
    WEBAPP_URL = _env_url
else:
    WEBAPP_URL = "https://turon-zakas.vercel.app"
