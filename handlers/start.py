from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_or_create_user, get_user_by_telegram_id, update_user_phone
from ..keyboards import get_main_keyboard, get_worker_keyboard
from config import ADMIN_IDS

router = Router()

class RegisterState(StatesGroup):
    waiting_for_phone = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    # Telefon raqam so'rash
    if not user.get('phone'):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "👋 Xush kelibsiz! Iltimos, telefon raqamingizni yuboring:",
            reply_markup=keyboard
        )
        await state.set_state(RegisterState.waiting_for_phone)
        return
    
    is_admin = message.from_user.id in ADMIN_IDS
    
    # Agar foydalanuvchi hodim bo'lsa
    if user.get('role') == 'worker':
        await message.answer(
            "🖥 **TURON O‘QUV MARKAZI**\n👨💻 Hodim paneli\n\n"
            "Siz Turon o‘quv markazi hodimisiz!\n"
            "Xizmat ko‘rsatishga tayyormisiz?",
            reply_markup=get_worker_keyboard(is_admin=is_admin),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"🖥 **TURON O‘QUV MARKAZI**\nKompyuter xizmati\n\n"
            f"👋 Assalomu alaykum, {user['full_name']}!\n\n"
            f"Kompyuter xizmatlarimizdan foydalaning.",
            reply_markup=get_main_keyboard(is_admin=is_admin),
            parse_mode="Markdown"
        )

@router.message(RegisterState.waiting_for_phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    update_user_phone(message.from_user.id, phone)
    
    await message.answer(
        "✅ Telefon raqam qabul qilindi!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    user = get_user_by_telegram_id(message.from_user.id)
    is_admin = message.from_user.id in ADMIN_IDS
    
    if user.get('role') == 'worker':
        await message.answer(
            "🖥 **TURON O‘QUV MARKAZI**\n👨💻 Hodim paneli\n\n"
            "Siz Turon o‘quv markazi hodimisiz!\n"
            "Xizmat ko‘rsatishga tayyormisiz?",
            reply_markup=get_worker_keyboard(is_admin=is_admin),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "🎉 Botdan foydalanishingiz mumkin!",
            reply_markup=get_main_keyboard(is_admin=is_admin)
        )
    
    await state.clear()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer("❌ Bekor qilindi!", reply_markup=get_main_keyboard(is_admin=is_admin))
