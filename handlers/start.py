from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_or_create_user, get_user_by_telegram_id, update_user_phone, get_settings, update_user_name
from keyboards import get_main_keyboard, get_worker_keyboard
from config import ADMIN_IDS

router = Router()

class RegisterState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    # Ismni tekshirish yoki so'rash
    if not user.get('phone') or user.get('full_name') == message.from_user.full_name:
        await message.answer("👋 Xush kelibsiz! Iltimos, ism-familiyangizni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.waiting_for_name)
        return
    
    is_admin = message.from_user.id in ADMIN_IDS
    
    # Agar foydalanuvchi hodim bo'lsa
    if user.get('role') == 'worker':
        await message.answer(
            "🖥 <b>TURON O‘QUV MARKAZI</b>\n👨💻 Hodim paneli\n\n"
            "Siz Turon o‘quv markazi hodimisiz!\n"
            "Xizmat ko‘rsatishga tayyormisiz?",
            reply_markup=get_worker_keyboard(is_admin=is_admin),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"🖥 <b>TURON O‘QUV MARKAZI</b>\nKompyuter xizmati\n\n"
            f"👋 Assalomu alaykum, {user['full_name']}!\n\n"
            f"Kompyuter xizmatlarimizdan foydalaning.",
            reply_markup=get_main_keyboard(is_admin=is_admin),
            parse_mode="HTML"
        )

@router.message(RegisterState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await update_user_name(message.from_user.id, message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        f"Rahmat, {message.text}! Endi iltimos, telefon raqamingizni yuboring:",
        reply_markup=keyboard
    )
    await state.set_state(RegisterState.waiting_for_phone)

@router.message(RegisterState.waiting_for_phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await update_user_phone(message.from_user.id, phone)
    
    await message.answer(
        "✅ Telefon raqam qabul qilindi!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    user = await get_user_by_telegram_id(message.from_user.id)
    is_admin = message.from_user.id in ADMIN_IDS
    
    if user.get('role') == 'worker':
        await message.answer(
            "🖥 <b>TURON O‘QUV MARKAZI</b>\n👨💻 Hodim paneli\n\n"
            "Siz Turon o‘quv markazi hodimisiz!\n"
            "Xizmat ko‘rsatishga tayyormisiz?",
            reply_markup=get_worker_keyboard(is_admin=is_admin),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🎉 Botdan foydalanishingiz mumkin!",
            reply_markup=get_main_keyboard(is_admin=is_admin)
        )
    
    await state.clear()

# ...
@router.message(F.text == "📞 Aloqa")
async def contact_info(message: Message):
    settings = get_settings()
    text = (
        "<b>📞 Aloqa ma'lumotlari</b>\n\n"
        f"📍 Manzil: {settings.get('address', 'Turon o\'quv markazi')}\n"
        f"☎️ Telefon: {settings.get('phone', '+998 90 123 45 67')}\n"
        f"📅 Ish kunlari: {settings.get('work_days', 'Dushanba - Shanba')}\n"
        f"🕰 Ish vaqti: {settings.get('work_hours', '09:00 - 18:00')}\n\n"
        "Savollaringiz bo'lsa, adminga murojaat qiling."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "✍️ Taklif va shikoyatlar")
async def support_info(message: Message):
    text = (
        "<b>✍️ Taklif va shikoyatlar bo'limi</b>\n\n"
        "Shikoyat yoki takliflaringiz bo'lsa, @Dasturchi_bt ga murojaat qiling.\n"
        "Sizning fikringiz biz uchun muhim!"
    )
    # Inline keyboard with button link
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Bog'lanish", url="https://t.me/Dasturchi_bt")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer("❌ Bekor qilindi!", reply_markup=get_main_keyboard(is_admin=is_admin))
