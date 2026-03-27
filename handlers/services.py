from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database import get_all_services, get_service_by_id
from ..keyboards import get_services_keyboard

router = Router()

@router.message(F.text == "🛠 Xizmatlar")
async def show_services(message: Message):
    services = get_all_services()
    
    if not services:
        await message.answer("❌ Hozircha xizmatlar mavjud emas.")
        return
    
    keyboard = get_services_keyboard(services)
    await message.answer(
        "📋 **Bizning xizmatlar:**\n\n"
        "Kerakli xizmatni tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("service_"))
async def service_detail(callback: CallbackQuery):
    service_id = int(callback.data.split("_")[1])
    service = get_service_by_id(service_id)
    
    if not service:
        await callback.answer("Xizmat topilmadi!")
        return
    
    text = (
        f"🛠 **{service['name']}**\n\n"
        f"📝 {service['description'] or 'Tavsif mavjud emas'}\n\n"
        f"💰 Narxi: **{service['price']:,} so‘m**\n"
        f"⏱ Vaqt: {service['duration']} daqiqa\n"
        f"📂 Kategoriya: {service['category'] or 'Umumiy'}\n\n"
        f"Buyurtma berish uchun quyidagi tugmani bosing:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Buyurtma berish", callback_data=f"order_{service_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_services")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery):
    services = get_all_services()
    keyboard = get_services_keyboard(services)
    await callback.message.edit_text(
        "📋 **Bizning xizmatlar:**\n\nKerakli xizmatni tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()
