import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
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
    waiting_for_media = State()
    waiting_for_pickup = State()
    waiting_for_payment_method = State()
    waiting_for_receipt = State()
    waiting_for_final_amount = State()
    waiting_for_rating = State()

@router.callback_query(F.data.startswith("order_"))
async def start_order(callback: CallbackQuery, state: FSMContext):
    service_id = callback.data.split("_")[1]
    service = await get_service_by_id(service_id)
    
    if not service:
        await callback.answer("Xizmat topilmadi!")
        return
    
    await state.update_data(
        service_id=service_id, 
        service_name=service['name'],
        service_price=service['price'],
        photos=[],
        documents=[],
        voice_note_url=None,
        comment=None
    )
    
    text = (
        f"📦 <b>Buyurtma: {service['name']}</b>\n"
        f"💰 Narxi: {service['price']:,} so‘m\n\n"
        f"Iltimos, buyurtma haqida ma'lumot bering:\n"
        f"📸 <b>Rasm (JPG)</b>, 📄 <b>PDF/Hujjat</b>, 🎤 <b>Ovozli xabar</b> yoki 📝 <b>Matn</b> yuboring.\n\n"
        "Barcha ma'lumotlarni yuborgach <b>\"✅ Davom etish\"</b> tugmasini bosing."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Davom etish", callback_data="confirm_media")],
        [InlineKeyboardButton(text="🗑 Ma'lumotlarni tozalash", callback_data="clear_media")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_media)
    await callback.answer()

@router.callback_query(F.data == "service_other")
async def start_other_service(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        service_id="other", 
        service_name="Boshqa xizmat",
        service_price=0,
        photos=[],
        documents=[],
        voice_note_url=None,
        comment=None
    )
    text = (
        "🆕 <b>Boshqa xizmat turi</b>\n\n"
        "Qanday xizmat kerek? Ma'lumotlarni yozing yoki fayllarni (Rasm, PDF, Ovozli xabar) yuboring.\n\n"
        "Xizmat narxi ma'lumotlar o'rganib chiqilgandan so'ng xabar qilinadi."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ma'lumotlarni yakunlash", callback_data="confirm_media")],
        [InlineKeyboardButton(text="❌ Hammasini o'chirish", callback_data="clear_media")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_media)
    await callback.answer()

@router.message(OrderState.waiting_for_media)
async def process_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        os.makedirs("order_photos", exist_ok=True)
        file_path = f"order_photos/{file_id}.jpg"
        await bot.download_file(file.file_path, file_path)
        
        photos = data.get('photos', [])
        photos.append(file_path)
        await state.update_data(photos=photos)
        txt = "📸 Rasm qo'shildi!"
        
    elif message.document:
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        os.makedirs("order_docs", exist_ok=True)
        file_path = f"order_docs/{message.document.file_name}"
        await bot.download_file(file.file_path, file_path)
        
        docs = data.get('documents', [])
        docs.append(file_path)
        await state.update_data(documents=docs)
        txt = f"📄 Hujjat ({message.document.file_name}) qo'shildi!"
        
    elif message.voice:
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        os.makedirs("voice_notes", exist_ok=True)
        file_path = f"voice_notes/{file_id}.ogg"
        await bot.download_file(file.file_path, file_path)
        await state.update_data(voice_note_url=file_path)
        txt = "🎤 Ovozli xabar yuborildi!"
        
    elif message.text:
        await state.update_data(comment=message.text)
        txt = "📝 Matnli izoh saqlandi!"
    else:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Davom etish", callback_data="confirm_media")],
        [InlineKeyboardButton(text="🗑 Hammasini qaytadan yuklash", callback_data="clear_media")]
    ])
    
    await message.answer(f"{txt}\nYana biror narsa yuborasizmi yoki davom etamiz?", reply_markup=kb)

@router.callback_query(F.data == "clear_media", OrderState.waiting_for_media)
async def clear_media_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photos=[], documents=[], voice_note_url=None, comment=None)
    await callback.message.answer("🗑 Barcha yuklangan ma'lumotlar o'chirildi. Qaytadan yuborishingiz mumkin.")
    await callback.answer()

@router.callback_query(F.data == "confirm_media", OrderState.waiting_for_media)
async def confirm_media(callback: CallbackQuery, state: FSMContext):
    text = (
        "📅 <b>Qachon olib ketasiz?</b>\n\n"
        "Iltimos, qay kuni va soat nechada tayyor bo'lishi kerakligini yozing.\n"
        "Masalan: <i>Dushanba, soat 14:00 da</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_pickup)
    await callback.answer()

@router.message(OrderState.waiting_for_pickup)
async def process_pickup(message: Message, state: FSMContext):
    await state.update_data(pickup_info=message.text)
    
    data = await state.get_data()
    service_price = data.get('service_price')
    photos_count = len(data.get('photos', []))
    has_voice = "Bor" if data.get('voice_note_url') else "Yo‘q"
    
    summary = (
        f"📝 <b>Buyurtma xulosasi:</b>\n\n"
        f"🛠 Xizmat: {data.get('service_id')}\n"
        f"💰 Narx: {service_price:,} so‘m\n"
        f"📅 Muddat: {message.text}\n"
        f"📸 Rasmlar: {photos_count} ta\n"
        f"🎤 Ovozli xabar: {has_voice}\n"
        f"💬 Izoh: {data.get('comment') or 'Yo‘q'}\n\n"
        "Barchasi to'g'rimi? To'lov usulini tanlang:"
    )
    
    keyboard = get_payment_keyboard()
    await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_payment_method)

@router.callback_query(F.data == "pay_at_location", OrderState.waiting_for_payment_method)
async def pay_at_location_final(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = await get_user_by_telegram_id(callback.from_user.id)
    
    order, worker = await create_order(
        user_id=user['telegram_id'],
        service_id=data.get('service_id'),
        total_price=data.get('service_price'),
        payment_method="at_location",
        comment=data.get('comment'),
        voice_note_url=data.get('voice_note_url'),
        photos=data.get('photos'),
        pickup_day=data.get('pickup_info') # Temporary simplified
    )
    
    worker_text = f"\n👨‍💻 Hodim: {worker['full_name']}" if worker else ""
    await callback.message.edit_text(
        "✅ <b>Buyurtma yuborildi!</b>\n\n"
        f"📦 Raqam: <code>{order['order_number']}</code>\n"
        f"📅 Muddat: {data.get('pickup_info')}"
        f"{worker_text}\n\n"
        "Admin tasdiqlashi bilan xabar yuboramiz.",
        parse_mode="HTML"
    )
    
    # Notify worker
    if worker:
        try:
            await bot.send_message(
                worker['telegram_id'],
                f"🆕 <b>Yangi buyurtma (Joyida to'lov)!</b>\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"📅 Muddat: {data.get('pickup_info')}\n\n"
                "Iltimos, buyurtmani qabul qiling.", 
                parse_mode="HTML"
            )
        except: pass
        
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "pay_online")
async def pay_online_handler(callback: CallbackQuery, state: FSMContext):
    from database import get_settings
    settings = await get_settings()
    data = await state.get_data()
    service_price = data.get('service_price')
    
    text = (
        f"💳 <b>Online To‘lov</b>\n\n"
        f"💰 Summa: {service_price:,} so‘m\n"
        f"💳 Karta: <code>{settings.get('card_number', 'Belgilanmagan')}</code>\n"
        f"👤 Egasi: {settings.get('card_owner', 'Belgilanmagan')}\n\n"
        f"To‘lovdan so‘ng <b>chekni (rasm)</b> yuboring."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_receipt)
    await callback.answer()

@router.callback_query(F.data == "pay_at_location")
async def pay_at_location_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    service_id = data.get('service_id')
    service_price = data.get('service_price')
    comment = data.get('comment')
    voice_note_url = data.get('voice_note_url')
    user = await get_user_by_telegram_id(callback.from_user.id)
    
    order, assigned_worker = await create_order(
        user_id=user['telegram_id'],
        service_id=service_id,
        total_price=service_price,
        payment_method="at_location",
        comment=comment,
        voice_note_url=voice_note_url
    )
    
    # Notify user
    worker_info = f"\n👨‍💻 Hodim: {assigned_worker['full_name']}" if assigned_worker else ""
    await callback.message.edit_text(
        "✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"📦 Buyurtma raqami: <code>{order['order_number']}</code>\n"
        f"💰 Summa: {service_price:,} so'm\n"
        "📍 To'lov: Xizmat ko'rsatilgan joyda."
        f"{worker_info}\n\n"
        "Xizmat ko'rsatish boshlanishi bilanoq sizga bildirishnoma keladi.",
        parse_mode="HTML"
    )
    
    # Notify worker and admin
    if assigned_worker:
        try:
            voice_text = "\n🎤 <b>Ovozli xabar mavjud!</b>" if voice_note_url else ""
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎤 Ovozni eshitish", callback_data=f"play_voice_{order['id']}")] if voice_note_url else []
            ])
            await bot.send_message(
                assigned_worker['telegram_id'],
                f"🆕 <b>Yangi buyurtma (Joyida to'lov)!</b>\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"💰 {service_price:,} so'm\n"
                f"📝 Izoh: {comment or 'Yoq'}{voice_text}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except: pass
        
    for admin_id in ADMIN_IDS:
        try:
            voice_text = "\n🎤 <b>Ovozli xabar mavjud!</b>" if voice_note_url else ""
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎤 Ovozni eshitish", callback_data=f"play_voice_{order['id']}")] if voice_note_url else []
            ])
            await bot.send_message(
                admin_id,
                f"🆕 <b>Yangi buyurtma (Joyida to'lov)!</b>\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"📝 Izoh: {comment or 'Yoq'}{voice_text}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except: pass
        
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "payment_receipt")
async def payment_receipt(callback: CallbackQuery, state: FSMContext):
    from database import get_settings
    settings = await get_settings()
    data = await state.get_data()
    service_price = data.get('service_price')
    
    text = (
        f"💳 <b>To‘lov ma’lumotlari</b>\n\n"
        f"💰 Summa: {service_price:,} so‘m\n"
        f"💳 Karta raqami: <code>{settings.get('card_number', 'Belgilanmagan')}</code>\n"
        f"👤 Karta egasi: {settings.get('card_owner', 'Belgilanmagan')}\n\n"
        f"To‘lovni amalga oshirgandan so‘ng, <b>chekni (skrinshot)</b> yuboring.\n\n"
        f"⚠️ Diqqat: Chek aniq ko‘rinishi kerak!"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.answer()

@router.message(OrderState.waiting_for_receipt, F.photo)
async def get_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = f"receipts/{photo.file_id}.jpg"
    os.makedirs("receipts", exist_ok=True)
    await bot.download_file(file.file_path, file_path)
    
    user = await get_user_by_telegram_id(message.from_user.id)
    
    order, assigned_worker = await create_order(
        user_id=user['telegram_id'],
        service_id=data.get('service_id'),
        total_price=data.get('service_price'),
        payment_method="receipt",
        comment=data.get('comment'),
        voice_note_url=data.get('voice_note_url'),
        photos=data.get('photos'),
        documents=data.get('documents'),
        pickup_day=data.get('pickup_info')
    )
    
    await update_order_payment_status(order['id'], "pending", file_path)
    
    worker_info = f"\n👨‍💻 Hodim: {assigned_worker['full_name']}" if assigned_worker else ""
    await message.answer(
        "✅ <b>Buyurtma qabul qilindi!</b>\n\n"
        f"📦 Buyurtma raqami: <code>{order['order_number']}</code>\n"
        f"💰 Summa: {data.get('service_price'):,} so'm"
        f"{worker_info}\n\n"
        "⏳ To'lov tasdiqlanishi kutilmoqda.",
        parse_mode="HTML"
    )
    
    if assigned_worker:
        try:
            doc_count = len(data.get('documents', []))
            doc_text = f"\n📄 <b>Hujjatlar: {doc_count} ta</b>" if doc_count else ""
            await bot.send_message(
                assigned_worker['telegram_id'],
                f"🆕 <b>Sizga yangi buyurtma biriktirildi!</b>\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"💰 {data.get('service_price'):,} so'm\n"
                f"📅 Muddat: {data.get('pickup_info')}{doc_text}",
                parse_mode="HTML"
            )
        except: pass
    
    for admin_id in ADMIN_IDS:
        try:
            worker_name = assigned_worker['full_name'] if assigned_worker else "Biriktirilmagan"
            await bot.send_message(
                admin_id,
                f"🆕 <b>Yangi buyurtma (Online)!</b>\n\n"
                f"📦 #{order['order_number']}\n"
                f"👤 Mijoz: {user['full_name']}\n"
                f"👨‍💻 Hodim: {worker_name}\n"
                f"💰 {data.get('service_price'):,} so'm",
                parse_mode="HTML"
            )
        except: pass
    
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
        "📋 <b>Sizning buyurtmalaringiz:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
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
        f"📦 <b>Buyurtma #{order['order_number']}</b>\n\n"
        f"🛠 Xizmat: {order['service_name']}\n"
        f"📝 Izoh: {order['comment'] or 'Yo‘q'}\n\n"
        f"📊 Holat: {status_text}\n"
        f"💳 To‘lov: {payment_text}\n"
        f"🕐 Berilgan vaqt: {order['created_at']}\n"
    )
    
    if order['completed_at']:
        text += f"✅ Bajarilgan vaqt: {order['completed_at']}\n"
    
    keyboard = get_order_detail_keyboard(order)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
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
        "📋 <b>Sizning buyurtmalaringiz:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(OrderState.waiting_for_final_amount)
async def process_final_amount(message: Message, state: FSMContext):
    # To'langan summani saqlash va baholashni so'rash
    text = (
        "<b>🌟 Rahmat! Ma'lumot qabul qilindi.</b>\n\n"
        "Xizmatimiz sifatini qanday baholaysiz? Bahoingiz biz uchun juda muhim! ⭐"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 1", callback_data="rate_1"),
            InlineKeyboardButton(text="⭐ 2", callback_data="rate_2"),
            InlineKeyboardButton(text="⭐ 3", callback_data="rate_3"),
            InlineKeyboardButton(text="⭐ 4", callback_data="rate_4"),
            InlineKeyboardButton(text="⭐ 5", callback_data="rate_5")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await state.set_state(OrderState.waiting_for_rating)

@router.callback_query(F.data.startswith("rate_"))
async def rate_order_handler(callback: CallbackQuery, state: FSMContext):
    from database import rate_order, get_settings
    
    data = await state.get_data()
    # Find the last completed order for this user to rate
    user_orders = await get_orders_by_user(callback.from_user.id)
    if user_orders:
        last_order = user_orders[0]
        rating = callback.data.split("_")[1]
        await rate_order(last_order['id'], rating)
        await callback.answer(f"⭐ {rating} baho uchun rahmat!", show_alert=True)
    
    settings = await get_settings()
    phone = settings.get('phone', '+998 90 123 45 67')
    
    adv_text = (
        "<b>🎓 Turon o'quv markazi — Sifatli ta'lim garovi!</b>\n\n"
        "Bizni tanlaganingiz uchun tashakkur! Bizda quyidagi yo'nalishlar mavjud:\n"
        "💻 — <b>Kompyuter savodxonligi</b>\n"
        "🎨 — <b>Grafik va 3D dizayn</b>\n"
        "🌐 — <b>Frontend & Backend dasturlash</b>\n"
        "🤖 — <b>Robototexnika</b>\n\n"
        "<i>Kelajagingizni biz bilan yanada yorqinroq quring! 🚀</i>\n\n"
        f"📞 Tel: {phone}\n"
        "📍 Bizning manzil: Markaziy bino."
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Telegram Kanal", url="https://t.me/Dasturchi_bt")],
        [InlineKeyboardButton(text="🎓 Kursga yozilish", url="https://t.me/Dasturchi_bt")]
    ])

    await callback.message.edit_text(adv_text, reply_markup=markup, parse_mode=ParseMode.HTML)
    await state.clear()
