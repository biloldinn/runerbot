import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import asyncio

from database import (
    get_user_by_telegram_id, get_service_by_id, create_order,
    update_order_payment_status, get_orders_by_user,
    get_order_by_id
)
from keyboards import get_payment_keyboard, get_orders_keyboard, get_order_detail_keyboard
from config import ADMIN_IDS, CARD_NUMBER, CARD_OWNER

router = Router()

class OrderState(StatesGroup):
    waiting_for_comment = State()
    waiting_for_receipt = State()

@router.callback_query(F.data.startswith("order_"))
async def start_order(callback: CallbackQuery, state: FSMContext):
    service_id = callback.data.split("_")[1]
    service = await get_service_by_id(service_id)
    
    if not service:
        await callback.answer("Xizmat topilmadi!")
        return
    
    await state.update_data(service_id=service_id, service_price=service['price'])
    
    text = (
        f"📦 **Buyurtma berish**\n\n"
        f"🛠 Xizmat: {service['name']}\n"
        f"💰 Narxi: {service['price']:,} so‘m\n\n"
        f"📝 Qo‘shimcha ma’lumot yozishingiz mumkin:\n"
        f"(masalan: kompyuter modeli, maxsus talablar)\n\n"
        f"Yoki /skip - o‘tkazib yuborish"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_comment)
    await callback.answer()

@router.message(OrderState.waiting_for_comment)
async def get_comment(message: Message, state: FSMContext):
    if message.text == "/skip":
        comment = None
    else:
        comment = message.text
    
    await state.update_data(comment=comment)
    
    data = await state.get_data()
    service_price = data.get('service_price')
    
    # To'lov usulini tanlash
    text = (
        f"💳 **To‘lov usulini tanlang**\n\n"
        f"💰 Summa: {service_price:,} so‘m\n\n"
        f"To‘lovni amalga oshirib, chekni yuboring.\n"
        f"Admin tomonidan tasdiqlangandan so‘ng buyurtma qabul qilinadi."
    )
    
    keyboard = get_payment_keyboard()
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_receipt)

@router.callback_query(F.data == "payment_receipt")
async def payment_receipt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service_price = data.get('service_price')
    
    text = (
        f"💳 **To‘lov ma’lumotlari**\n\n"
        f"💰 Summa: {service_price:,} so‘m\n"
        f"💳 Karta raqami: `{CARD_NUMBER}`\n"
        f"👤 Karta egasi: {CARD_OWNER}\n\n"
        f"To‘lovni amalga oshirgandan so‘ng, **chekni (skrinshot)** yuboring.\n\n"
        f"⚠️ Diqqat: Chek aniq ko‘rinishi kerak!"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.answer()

@router.message(OrderState.waiting_for_receipt, F.photo)
async def get_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    service_id = data.get('service_id')
    service_price = data.get('service_price')
    comment = data.get('comment')
    
    # Rasmni saqlash
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = f"receipts/{photo.file_id}.jpg"
    os.makedirs("receipts", exist_ok=True)
    await bot.download_file(file.file_path, file_path)
    
    # Foydalanuvchini olish
    user = await get_user_by_telegram_id(message.from_user.id)
    
    # Buyurtma yaratish (round-robin bilan)
    order, assigned_worker = await create_order(
        user_id=user['telegram_id'], # Use telegram_id consistently
        service_id=service_id,
        total_price=service_price,
        payment_method="receipt",
        comment=comment
    )
    
    # Chekni saqlash
    await update_order_payment_status(order['id'], "pending", file_path)
    
    # Hodim haqida xabar
    worker_info = f"\n👨‍💻 Hodim: {assigned_worker['full_name']}" if assigned_worker else ""
    
    await message.answer(
        "✅ **Buyurtma qabul qilindi!**\n\n"
        f"📦 Buyurtma raqami: `{order['order_number']}`\n"
        f"💰 Summa: {service_price:,} so'm"
        f"{worker_info}\n\n"
        "⏳ To'lov tasdiqlanishi kutilmoqda.\n"
        "Admin tomonidan tasdiqlangandan so'ng sizga xabar keladi.",
        parse_mode="Markdown"
    )
    
    # Biriktirilgan hodimga bildirishnoma
    if assigned_worker:
        try:
            await bot.send_message(
                assigned_worker['telegram_id'],
                f"🆕 **Sizga yangi buyurtma biriktirildi!**\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"📞 Tel: {user.get('phone', 'Noma\'lum')}\n"
                f"💰 {service_price:,} so'm\n"
                f"📝 Izoh: {comment or 'Yoq'}\n\n"
                f"To'lov tasdiqlangandan so'ng ishlashni boshlang.",
                parse_mode="Markdown"
            )
        except:
            pass
    
    # Adminlarga xabar yuborish
    for admin_id in ADMIN_IDS:
        try:
            worker_name = assigned_worker['full_name'] if assigned_worker else "Biriktirilmagan"
            await bot.send_message(
                admin_id,
                f"🆕 **Yangi buyurtma!**\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"💰 {service_price:,} so'm\n"
                f"👨‍💻 Hodim: {worker_name}\n"
                f"📝 Izoh: {comment or 'Yoq'}\n\n"
                f"Chek: /check_{order['id']}",
                parse_mode="Markdown"
            )
        except:
            pass
    
    await state.clear()

@router.message(F.text == "📝 Mening buyurtmalarim")
async def my_orders(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    orders = await get_orders_by_user(user['telegram_id'])
    
    if not orders:
        await message.answer("❌ Sizning buyurtmalaringiz yo‘q.")
        return
    
    keyboard = get_orders_keyboard(orders)
    await message.answer(
        "📋 **Sizning buyurtmalaringiz:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("myorder_"))
async def my_order_detail(callback: CallbackQuery):
    order_id = callback.data.split("_")[1]
    order = await get_order_by_id(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi!")
        return
    
    status_text = {
        'new': '⏳ Kutilmoqda',
        'accepted': '✅ Qabul qilindi',
        'in_progress': '🔧 Jarayonda',
        'completed': '✅ Bajarildi',
        'cancelled': '❌ Bekor qilindi'
    }.get(order['status'], order['status'])
    
    payment_text = {
        'pending': '⏳ Kutilmoqda',
        'confirmed': '✅ Tasdiqlangan',
        'cancelled': '❌ Bekor qilindi'
    }.get(order['payment_status'], order['payment_status'])
    
    text = (
        f"📦 **Buyurtma #{order['order_number']}**\n\n"
        f"🛠 Xizmat: {order['service_name']}\n"
        f"💰 Narxi: {order['total_price']:,} so‘m\n"
        f"📝 Izoh: {order['comment'] or 'Yo‘q'}\n\n"
        f"📊 Holat: {status_text}\n"
        f"💳 To‘lov: {payment_text}\n"
        f"🕐 Berilgan vaqt: {order['created_at']}\n"
    )
    
    if order['completed_at']:
        text += f"✅ Bajarilgan vaqt: {order['completed_at']}\n"
    
    keyboard = get_order_detail_keyboard(order)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "back_to_orders")
async def back_to_orders(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    orders = await get_orders_by_user(user['telegram_id'])
    
    if not orders:
        await callback.message.edit_text("❌ Sizning buyurtmalaringiz yo‘q.")
        await callback.answer()
        return
    
    keyboard = get_orders_keyboard(orders)
    await callback.message.edit_text(
        "📋 **Sizning buyurtmalaringiz:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rate_"))
async def rate_order(callback: CallbackQuery):
    await callback.answer("⭐ Raxmat! Bahoingiz qabul qilindi.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)
