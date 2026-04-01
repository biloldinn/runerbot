from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_order_by_id, update_order_payment_status, add_worker, add_service, 
    get_all_services, update_settings, find_user_by_username, get_all_workers, 
    remove_worker, get_all_orders
)
from config import ADMIN_IDS
WEBAPP_URL = "https://turon-zakas.vercel.app"

router = Router()

class AdminStates(StatesGroup):
    # Xodim qo'shish holatlari
    waiting_worker_username = State()
    waiting_worker_name = State()
    waiting_worker_phone = State()
    # Xizmat qo'shish holatlari
    waiting_service_name = State()
    waiting_service_price = State()
    waiting_service_desc = State()
    # Sozlamalar
    waiting_settings_phone = State()
    waiting_settings_card = State()
    waiting_settings_card_owner = State()

@router.message(Command("admin"))
async def admin_main(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web Hisobotlar", web_app=WebAppInfo(url=WEBAPP_URL))] if WEBAPP_URL else [],
        [InlineKeyboardButton(text="👤 Xodim qo'shish", callback_data="add_worker_bot")],
        [InlineKeyboardButton(text="👥 Xodimlar ro'yxati", callback_data="admin_workers_list")],
        [InlineKeyboardButton(text="🛠 Xizmat qo'shish", callback_data="add_service_bot")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")],
        [InlineKeyboardButton(text="💳 Karta sozlamalari", callback_data="admin_card_settings")],
        [InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="admin_orders")],
    ])
    
    await message.answer("🔧 **Admin Panel**\n\nKerakli bo'limni tanlang:", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "admin_workers_list")
async def admin_workers_list(callback: CallbackQuery):
    from database import get_all_workers
    workers = get_all_workers()
    
    if not workers:
        await callback.answer("Hozircha xodimlar yo'q.")
        return
        
    text = "👥 **Xodimlar ro'yxati:**\n\n"
    keyboard = []
    
    for w in workers:
        text += f"👤 {w['full_name']} (@{w.get('username', 'Yoq')})\n📞 {w.get('phone', 'Yoq')}\n\n"
        keyboard.append([InlineKeyboardButton(text=f"❌ {w['full_name']} ni o'chirish", callback_data=f"delete_worker_{w['telegram_id']}")])
    
    keyboard.append([InlineKeyboardButton(text="Orqaga", callback_data="admin_main_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("delete_worker_"))
async def delete_worker_handler(callback: CallbackQuery):
    from database import remove_worker
    worker_id = int(callback.data.split("_")[2])
    remove_worker(worker_id)
    await callback.answer("✅ Xodim o'chirildi!", show_alert=True)
    await admin_workers_list(callback) # Ro'yxatni yangilash

@router.callback_query(F.data == "admin_main_back")
async def admin_main_back(callback: CallbackQuery):
    await callback.message.delete()
    await admin_main(callback.message)
    await callback.answer()

# --- Xodim qo'shish (FSM) ---
@router.callback_query(F.data == "add_worker_bot")
async def start_add_worker(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➡️ Xodimning <b>Username</b>ini yuboring (masalan: @username):", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_worker_username)
    await callback.answer()

@router.message(AdminStates.waiting_worker_username)
async def process_worker_username(message: Message, state: FSMContext):
    try:
        username = message.text.replace("@", "")
        user = find_user_by_username(username)
        
        if not user:
            await message.answer("❌ Bu username bilan foydalanuvchi topilmadi!\n\nAvval xodim botga kirib /start bosishi kerak.")
            return
            
        await state.update_data(worker_id=user['telegram_id'], worker_username=user.get('username'))
        await message.answer(f"✅ Foydalanuvchi topildi: <b>{user['full_name']}</b>\n\n➡️ Endi xodimning <b>familiyasi va ismini</b> kiriting:", parse_mode="HTML")
        await state.set_state(AdminStates.waiting_worker_name)
    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {e}")

@router.message(AdminStates.waiting_worker_name)
async def process_worker_name(message: Message, state: FSMContext):
    await state.update_data(worker_name=message.text)
    await message.answer("➡️ Xodimning <b>Telefon raqamini</b> yuboring:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_worker_phone)

@router.message(AdminStates.waiting_worker_phone)
async def process_worker_phone(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    add_worker(data['worker_id'], data.get('worker_username'), data['worker_name'], message.text)
    
    # Notify Worker
    try:
        worker_text = (
            "👨‍💻 <b>Tabriklaymiz!</b>\n\n"
            "Siz Turon buyurtma botida <b>xodim</b> bo'lib ro'yxatdan o'tdingiz.\n"
            "Endi buyurtmalar kelishini kuting! Buyurtmalar shu yerda ko'rinadi."
        )
        await bot.send_message(data['worker_id'], worker_text, parse_mode="HTML")
    except:
        pass # If we can't send, we just proceed
        
    await message.answer(f"✅ Xodim muvaffaqiyatli qo'shildi: <b>{data['worker_name']}</b>", parse_mode="HTML")
    await state.clear()

# --- Xizmat qo'shish (FSM) ---
@router.callback_query(F.data == "add_service_bot")
async def start_add_service(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➡️ Xizmat <b>Nomini</b> yuboring:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_service_name)
    await callback.answer()

@router.message(AdminStates.waiting_service_name)
async def process_service_name(message: Message, state: FSMContext):
    await state.update_data(s_name=message.text)
    await message.answer("➡️ Xizmat <b>Narxini</b> yuboring (faqat raqam):", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_service_price)

@router.message(AdminStates.waiting_service_price)
async def process_service_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Narx raqam bo'lishi kerak!")
        return
    await state.update_data(s_price=float(message.text))
    await message.answer("➡️ Xizmat haqida <b>Qisqacha ma'lumot</b> yuboring:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_service_desc)

@router.message(AdminStates.waiting_service_desc)
async def process_service_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    from database import add_service
    add_service(data['s_name'], message.text, data['s_price'], 60, "Umumiy")
    await message.answer(f"✅ Xizmat qo'shildi: <b>{data['s_name']}</b>\n💰 Narxi: {data['s_price']:,} so'm", parse_mode="HTML")
    await state.clear()

# --- Sozlamalar ---
@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "⚙️ <b>Sozlamalar bo'limi</b>\n\n"
        "Yangi kontakt telefon raqamini yuboring (masalan: +998905418414):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_settings_phone)
    await callback.answer()

@router.message(AdminStates.waiting_settings_phone)
async def process_settings_phone(message: Message, state: FSMContext):
    new_phone = message.text
    update_settings({"phone": new_phone})
    await message.answer(f"✅ Kontakt telefon raqami muvaffaqiyatli saqlandi: {new_phone}")
    await state.clear()
@router.message(F.text.startswith("/check_"))
async def check_order_receipt(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        order_id = message.text.split("_")[1]
    except: return
        
    order = get_order_by_id(order_id)
    if not order or not order['receipt_url']:
        await message.answer("❌ Chek topilmadi!")
        return
        
    text = f"📝 <b>Buyurtma #{order['order_number']}</b>\n👤 Mijoz: {order['user_name']}\n💰 Summa: {order['total_price']:,} so'm"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pay_{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_pay_{order_id}")]
    ])
    from aiogram.types import FSInputFile
    await message.answer_photo(FSInputFile(order['receipt_url']), caption=text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    update_order_payment_status(order_id, "confirmed")
    try:
        await bot.send_message(order['user_id'], f"✅ <b>To'lovingiz tasdiqlandi!</b> #{order['order_number']}", parse_mode="HTML")
    except: pass
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ <b>TASDIQLANDI</b>", reply_markup=None, parse_mode="HTML")

@router.callback_query(F.data.startswith("cancel_pay_"))
async def cancel_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    update_order_payment_status(order_id, "cancelled")
    try:
        await bot.send_message(order['user_id'], f"❌ <b>To'lovingiz bekor qilindi.</b>")
    except: pass
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ <b>BEKOR QILINDI</b>", reply_markup=None, parse_mode="HTML")

@router.callback_query(F.data == "admin_orders")
async def admin_orders_list(callback: CallbackQuery):
    from database import get_all_orders
    orders = get_all_orders()
    
    if not orders:
        await callback.answer("Hozircha buyurtmalar yo'q.")
        return
        
    text = "📦 <b>Barcha buyurtmalar ro'yxati:</b>\n\n"
    for o in orders[:10]: # Oxirgi 10 tasini ko'rsatamiz
        status = "⏳" if o['status'] == 'new' else "✅" if o['status'] == 'completed' else "🔧"
        text += f"{status} #{o['order_number']} | {o['total_price']:,} so'm | {o['user_name']}\n"
        
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_card_settings")
async def admin_card_settings_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💳 <b>Karta raqamini kiriting:</b>\n(Masalan: 8600123456789012)", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_settings_card)
    await callback.answer()

@router.message(AdminStates.waiting_settings_card)
async def process_card_num(message: Message, state: FSMContext):
    await state.update_data(card_number=message.text)
    await message.answer("👤 <b>Karta egasining ism-familiyasi:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_settings_card_owner)

@router.message(AdminStates.waiting_settings_card_owner)
async def process_card_own(message: Message, state: FSMContext):
    data = await state.get_data()
    update_settings({
        "card_number": data['card_number'],
        "card_owner": message.text
    })
    await message.answer(f"✅ Karta ma'lumotlari saqlandi!\n💳 {data['card_number']}\n👤 {message.text}")
    await state.clear()

@router.callback_query(F.data.startswith("play_voice_"))
async def play_voice_handler(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    if order and order['voice_note_url']:
        from aiogram.types import FSInputFile
        await callback.message.answer_voice(FSInputFile(order['voice_note_url']), caption=f"🎤 #{order['order_number']} ovozli izohi")
    else:
        await callback.answer("Ovozli xabar topilmadi!")
    await callback.answer()

@router.callback_query(F.data.startswith("check_receipt_"))
async def check_receipt_handler(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    if order and order['receipt_url']:
        from aiogram.types import FSInputFile
        text = f"📝 <b>Buyurtma #{order['order_number']}</b>\n👤 Mijoz: {order['user_name']}\n💰 Summa: {order['total_price']:,} so'm"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pay_{order_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_pay_{order_id}")]
        ])
        await callback.message.answer_photo(FSInputFile(order['receipt_url']), caption=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.answer("Chek topilmadi!")
    await callback.answer()
