from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import asyncio

from database import (
    get_user_by_telegram_id, get_new_orders, get_worker_orders,
    assign_order_to_worker, update_order_status, update_worker_stats,
    get_worker_today_stats, get_worker_history, get_order_by_id
)
from keyboards import get_worker_orders_keyboard
from config import ADMIN_IDS

router = Router()

@router.message(F.text == "📋 Yangi buyurtmalar")
async def worker_new_orders(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    
    if user.get('role') != 'worker':
        await message.answer("❌ Bu funksiya faqat hodimlar uchun!")
        return
    
    orders = await get_new_orders()
    
    if not orders:
        await message.answer("📭 Yangi buyurtmalar yo‘q.")
        return
    
    keyboard = get_worker_orders_keyboard(orders, "new")
    await message.answer(
        f"🆕 <b>Yangi buyurtmalar ({len(orders)} ta)</b>\n\n"
        "Qabul qilmoqchi bo‘lgan buyurtmani tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("worker_accept_"))
async def worker_accept_order(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    worker = await get_user_by_telegram_id(callback.from_user.id)
    order = await get_order_by_id(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi!")
        return
    
    # Buyurtmani hodimga biriktirish
    await assign_order_to_worker(order_id, worker['telegram_id'])
    await update_order_status(order_id, "accepted")
    
    # Mijozga xabar
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ <b>Buyurtma #{order['order_number']} qabul qilindi!</b>\n\n"
            f"👨💻 Hodim: <b>{worker['full_name']}</b>\n"
            f"📍 Turon o'quv markaziga kelganingizda <b>{worker['full_name']}</b> deb so'rang, sizga yordam beradi.\n\n"
            f"🕐 Tez orada siz bilan bog‘lanadi.\n"
            f"📞 Tel: {worker.get('phone', 'Noma\'lum')}",
            parse_mode="HTML"
        )
    except:
        pass
    
    # Adminlarga xabar
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ Buyurtma #{order['order_number']} hodim {worker['full_name']} ga biriktirildi.",
                parse_mode="HTML"
            )
        except:
            pass
    
    await callback.message.edit_text(
        f"✅ <b>Buyurtma #{order['order_number']} qabul qilindi!</b>\n\n"
        f"👤 Mijoz: {order['user_name']}\n"
        f"📞 Tel: {order['user_phone']}\n"
        f"🛠 Xizmat: {order['service_name']}\n"
        f"💰 {order['total_price']:,} so‘m\n"
        f"📝 Izoh: {order['comment'] or 'Yo‘q'}\n\n"
        f"⏳ Holat: Jarayonda",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.text == "🔧 Jarayondagilar")
async def worker_in_progress(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    
    if user.get('role') != 'worker':
        await message.answer("❌ Bu funksiya faqat hodimlar uchun!")
        return
    
    orders = await get_worker_orders(user['telegram_id'], "accepted")
    orders += await get_worker_orders(user['telegram_id'], "in_progress")
    
    if not orders:
        await message.answer("🔧 Jarayondagi buyurtmalar yo‘q.")
        return
    
    keyboard = get_worker_orders_keyboard(orders, "progress")
    await message.answer(
        f"🔧 <b>Jarayondagi buyurtmalar ({len(orders)} ta)</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("worker_complete_"))
async def worker_complete_order(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    worker = get_user_by_telegram_id(callback.from_user.id)
    order = get_order_by_id(order_id)
    
    if not order:
        await callback.answer("Buyurtma topilmadi!")
        return
    
    # Buyurtmani bajarilgan deb belgilash
    update_order_status(order_id, "completed")
    update_worker_stats(worker['telegram_id'], order['total_price'])
    
    # Foydalanuvchiga so'rov yuborish
    from handlers.orders import OrderState
    from main import bot
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ <b>Buyurtmangiz #{order['order_number']} yakunlandi!</b>\n\n"
            "Iltimos, ushbu buyurtma uchun qancha to'lov qildingiz?\n"
            "<b>Aniq summani yozing:</b>",
            parse_mode="HTML"
        )
        # State ni o'rnatish uchun dispatcherdan foydalanishimiz kerak yoki state ni qo'lda boshqarish
        # Lekin osonroq yo'li: stateni user_id va chat_id bo'yicha o'rnatish
        from aiogram.fsm.storage.base import StorageKey
        from main import dp
        await dp.storage.set_state(
            StorageKey(bot_id=bot.id, chat_id=order['user_id'], user_id=order['user_id']),
            OrderState.waiting_for_final_amount
        )
        await dp.storage.update_data(
            StorageKey(bot_id=bot.id, chat_id=order['user_id'], user_id=order['user_id']),
            {"finishing_order_id": order_id, "worker_id": worker['telegram_id']}
        )
    except Exception as e:
        print(f"Error sending message to user: {e}")

    # 10 daqiqadan keyin mijozga xabar yuborish (eski logika o'chirildi yoki qoldirildi)
    await callback.message.answer(
        f"✅ Buyurtma #{order['order_number']} bajarildi!\n\n"
        f"Mijozga to'lov summasini so'rab xabar yuborildi.",
        parse_mode="HTML"
    )
    
    # Mijozga kechiktirilgan xabar
    async def notify_user():
        await asyncio.sleep(600)  # 10 daqiqa
        try:
            await bot.send_message(
                order['user_id'],
                f"✅ <b>Buyurtma #{order['order_number']} tayyor!</b>\n\n"
                f"📍 Manzil: Turon o‘quv markazi\n"
                f"🕐 Tayyor bo‘lgan vaqt: {datetime.now().strftime('%H:%M')}\n\n"
                f"Kelib olishingiz mumkin.",
                parse_mode="HTML"
            )
        except:
            pass
    
    asyncio.create_task(notify_user())
    await callback.answer()

@router.message(F.text == "✅ Bajarilganlar")
async def worker_completed(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    
    if user.get('role') != 'worker':
        await message.answer("❌ Bu funksiya faqat hodimlar uchun!")
        return
    
    orders = await get_worker_orders(user['telegram_id'], "completed")
    today_stats = await get_worker_today_stats(user['telegram_id'])
    
    if not orders:
        await message.answer("📭 Bajarilgan buyurtmalar yo‘q.")
        return
    
    text = f"✅ <b>Bajarilgan buyurtmalar</b>\n\n"
    text += f"📊 <b>Bugungi statistika:</b>\n"
    text += f"📦 Buyurtmalar: {today_stats['orders_count']} ta\n"
    text += f"💰 Daromad: {today_stats['total_amount']:,} so‘m\n\n"
    text += f"<b>Oxirgi 5 ta buyurtma:</b>\n"
    
    for order in orders[:5]:
        text += f"\n• #{order['order_number']} | {order['service_name']} | {order['total_price']:,} so‘m"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📊 Mening statistikam")
async def worker_stats(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    
    if user.get('role') != 'worker':
        await message.answer("❌ Bu funksiya faqat hodimlar uchun!")
        return
    
    today_stats = await get_worker_today_stats(user['telegram_id'])
    history = await get_worker_history(user['telegram_id'])
    
    total_orders = sum(h['orders_count'] for h in history)
    total_amount = sum(h['total_amount'] for h in history)
    
    text = (
        f"📊 <b>Mening statistikam</b>\n\n"
        f"👤 {user['full_name']}\n\n"
        f"<b>Bugun:</b>\n"
        f"📦 {today_stats['orders_count']} ta buyurtma\n"
        f"💰 {today_stats['total_amount']:,} so‘m\n\n"
        f"<b>Umumiy (30 kun):</b>\n"
        f"📦 {total_orders} ta buyurtma\n"
        f"💰 {total_amount:,} so‘m\n"
    )
    
    await message.answer(text, parse_mode="HTML")
