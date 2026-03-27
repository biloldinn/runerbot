from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_order_by_id, update_order_payment_status, add_worker, add_service, get_all_services, update_settings
from config import ADMIN_IDS, WEBAPP_URL

router = Router()

class AdminStates(StatesGroup):
    # Xodim qo'shish holatlari
    waiting_worker_id = State()
    waiting_worker_name = State()
    waiting_worker_phone = State()
    # Xizmat qo'shish holatlari
    waiting_service_name = State()
    waiting_service_price = State()
    waiting_service_desc = State()
    # Sozlamalar
    waiting_settings_phone = State()

@router.message(Command("admin"))
async def admin_main(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web Hisobotlar", web_app=WebAppInfo(url=WEBAPP_URL))] if WEBAPP_URL else [],
        [InlineKeyboardButton(text="👤 Xodim qo'shish", callback_data="add_worker_bot")],
        [InlineKeyboardButton(text="🛠 Xizmat qo'shish", callback_data="add_service_bot")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="admin_orders")],
    ])
    
    await message.answer(
        "👨‍💼 **Admin Boshqaruvi**\n\n"
        "Quyidagi tugmalar orqali tizimni boshqaring:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# --- Xodim qo'shish (FSM) ---
@router.callback_query(F.data == "add_worker_bot")
async def start_add_worker(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➡️ Xodimning **Telegram ID** sini yuboring:")
    await state.set_state(AdminStates.waiting_worker_id)
    await callback.answer()

@router.message(AdminStates.waiting_worker_id)
async def process_worker_id(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Telegram ID raqamlardan iborat bo'lishi kerak!")
        return
    await state.update_data(worker_id=int(message.text))
    await message.answer("➡️ Xodimning **Ism-familiyasini** yuboring:")
    await state.set_state(AdminStates.waiting_worker_name)

@router.message(AdminStates.waiting_worker_name)
async def process_worker_name(message: Message, state: FSMContext):
    await state.update_data(worker_name=message.text)
    await message.answer("➡️ Xodimning **Telefon raqamini** yuboring:")
    await state.set_state(AdminStates.waiting_worker_phone)

@router.message(AdminStates.waiting_worker_phone)
async def process_worker_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_worker(data['worker_id'], None, data['worker_name'], message.text)
    await message.answer(f"✅ Xodim qo'shildi: **{data['worker_name']}**")
    await state.clear()

# --- Xizmat qo'shish (FSM) ---
@router.callback_query(F.data == "add_service_bot")
async def start_add_service(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➡️ Xizmat **Nomini** yuboring:")
    await state.set_state(AdminStates.waiting_service_name)
    await callback.answer()

@router.message(AdminStates.waiting_service_name)
async def process_service_name(message: Message, state: FSMContext):
    await state.update_data(s_name=message.text)
    await message.answer("➡️ Xizmat **Narxini** yuboring (faqat raqam):")
    await state.set_state(AdminStates.waiting_service_price)

@router.message(AdminStates.waiting_service_price)
async def process_service_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Narx raqam bo'lishi kerak!")
        return
    await state.update_data(s_price=float(message.text))
    await message.answer("➡️ Xizmat haqida **Qisqacha ma'lumot** yuboring:")
    await state.set_state(AdminStates.waiting_service_desc)

@router.message(AdminStates.waiting_service_desc)
async def process_service_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_service(data['s_name'], message.text, data['s_price'], 60, "Umumiy")
    await message.answer(f"✅ Xizmat qo'shildi: **{data['s_name']}**")
    await state.clear()

# --- Sozlamalar ---
@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "⚙️ **Sozlamalar bo'limi**\n\n"
        "Yangi kontakt telefon raqamini yuboring (masalan: +998901234567):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_settings_phone)
    await callback.answer()

@router.message(AdminStates.waiting_settings_phone)
async def process_settings_phone(message: Message, state: FSMContext):
    new_phone = message.text
    await update_settings({"phone": new_phone})
    await message.answer(f"✅ Kontakt telefon raqami muvaffaqiyatli saqlandi: {new_phone}")
    await state.clear()
@router.message(F.text.startswith("/check_"))
async def check_order_receipt(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        order_id = message.text.split("_")[1]
    except: return
        
    order = await get_order_by_id(order_id)
    if not order or not order['receipt_url']:
        await message.answer("❌ Chek topilmadi!")
        return
        
    text = f"📝 **Buyurtma #{order['order_number']}**\n👤 Mijoz: {order['user_name']}\n💰 Summa: {order['total_price']:,} so'm"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pay_{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_pay_{order_id}")]
    ])
    from aiogram.types import FSInputFile
    await message.answer_photo(FSInputFile(order['receipt_url']), caption=text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = await get_order_by_id(order_id)
    await update_order_payment_status(order_id, "confirmed")
    try:
        await bot.send_message(order['user_id'], f"✅ **To'lovingiz tasdiqlandi!** #{order['order_number']}")
    except: pass
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ **TASDIQLANDI**", reply_markup=None)

@router.callback_query(F.data.startswith("cancel_pay_"))
async def cancel_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.split("_")[2]
    order = await get_order_by_id(order_id)
    await update_order_payment_status(order_id, "cancelled")
    try:
        await bot.send_message(order['user_id'], f"❌ **To'lovingiz bekor qilindi.**")
    except: pass
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ **BEKOR QILINDI**", reply_markup=None)

@router.callback_query(F.data == "admin_orders")
async def admin_orders_list(callback: CallbackQuery):
    from database import get_all_orders
    orders = await get_all_orders()
    
    if not orders:
        await callback.answer("Hozircha buyurtmalar yo'q.")
        return
        
    text = "📦 **Barcha buyurtmalar ro'yxati:**\n\n"
    for o in orders[:10]: # Oxirgi 10 tasini ko'rsatamiz
        status = "⏳" if o['status'] == 'new' else "✅" if o['status'] == 'completed' else "🔧"
        text += f"{status} #{o['order_number']} | {o['total_price']:,} so'm | {o['user_name']}\n"
        
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
