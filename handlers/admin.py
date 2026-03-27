from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from database import get_order_by_id, update_order_payment_status, get_user_by_telegram_id
from config import ADMIN_IDS, WEBAPP_URL

router = Router()

@router.message(Command("admin"))
async def admin_help(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Siz admin emassiz!")
        return

    if WEBAPP_URL:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🌐 Admin Panelni ochish",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )],
            [InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="admin_orders")],
        ])
        await message.answer(
            "👨‍💼 **Admin Panel**\n\n"
            "Quyidagi tugma orqali admin panelni oching:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "👨‍💼 **Admin Buyruqlari:**\n\n"
            "/check_{id} - Chekni tekshirish",
            parse_mode="Markdown"
        )

@router.message(F.text.startswith("/check_"))
async def check_order_receipt(message: Message, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        order_id = int(message.text.split("_")[1])
    except:
        await message.answer("❌ Xato buyurtma ID")
        return
        
    order = get_order_by_id(order_id)
    if not order or not order['receipt_url']:
        await message.answer("❌ Chek topilmadi!")
        return
        
    text = (
        f"📝 **Buyurtma #{order['order_number']}**\n"
        f"👤 Mijoz: {order['user_name']}\n"
        f"💰 Summa: {order['total_price']:,} so'm\n"
        f"💳 Holat: {order['payment_status']}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pay_{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_pay_{order_id}")]
    ])
    
    from aiogram.types import FSInputFile
    photo = FSInputFile(order['receipt_url'])
    await message.answer_photo(photo, caption=text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split("_")[2])
    order = get_order_by_id(order_id)
    
    update_order_payment_status(order_id, "confirmed")
    
    # Mijozga xabar
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ **To'lovingiz tasdiqlandi!**\n\n"
            f"Sizning buyurtmangiz #{order['order_number']} tez orada hodimga biriktiriladi.",
            parse_mode="Markdown"
        )
    except:
        pass
        
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ **TO'LOV TASDIQLANDI**", reply_markup=None)
    await callback.answer("To'lov tasdiqlandi!")

@router.callback_query(F.data.startswith("cancel_pay_"))
async def cancel_payment(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split("_")[2])
    order = get_order_by_id(order_id)
    
    update_order_payment_status(order_id, "cancelled")
    
    # Mijozga xabar
    try:
        await bot.send_message(
            order['user_id'],
            f"❌ **To'lovingiz bekor qilindi.**\n\n"
            f"Iltimos, chekni qaytadan yuboring yoki admin bilan bog'laning.",
            parse_mode="Markdown"
        )
    except:
        pass
        
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ **TO'LOV BEKOR QILINDI**", reply_markup=None)
    await callback.answer("To'lov bekor qilindi!")
