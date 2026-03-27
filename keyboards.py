from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import WEBAPP_URL

def get_main_keyboard(is_admin=False):
    buttons = [
        [KeyboardButton(text="💻 Xizmatlar")],
        [KeyboardButton(text="📝 Mening buyurtmalarim")],
        [KeyboardButton(text="📞 Aloqa"), KeyboardButton(text="👤 Profil")]
    ]
    if is_admin and WEBAPP_URL:
        buttons.insert(0, [KeyboardButton(text="🌐 Boshqaruv Paneli", web_app=WebAppInfo(url=WEBAPP_URL))])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_worker_keyboard(is_admin=False):
    buttons = [
        [KeyboardButton(text="📋 Yangi buyurtmalar")],
        [KeyboardButton(text="🔧 Jarayondagilar"), KeyboardButton(text="✅ Bajarilganlar")],
        [KeyboardButton(text="📊 Mening statistikam"), KeyboardButton(text="👤 Profil")]
    ]
    if is_admin and WEBAPP_URL:
        buttons.insert(0, [KeyboardButton(text="🌐 Boshqaruv Paneli", web_app=WebAppInfo(url=WEBAPP_URL))])
        
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_services_keyboard(services):
    buttons = []
    for service in services:
        buttons.append([InlineKeyboardButton(
            text=f"{service['name']} - {service['price']:,} so‘m",
            callback_data=f"service_{service['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Chek yuborish", callback_data="payment_receipt")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_order")]
    ])

def get_orders_keyboard(orders):
    buttons = []
    for order in orders:
        status_emoji = {
            'new': '⏳',
            'accepted': '✅',
            'in_progress': '🔧',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '📦')
        
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} #{order['order_number']} - {order['service_name']}",
            callback_data=f"myorder_{order['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_order_detail_keyboard(order):
    buttons = []
    if order['status'] == 'completed' and order['payment_status'] == 'confirmed':
        buttons.append([InlineKeyboardButton(text="⭐ Baholash", callback_data=f"rate_{order['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_worker_orders_keyboard(orders, order_type):
    buttons = []
    for order in orders:
        if order_type == "new":
            buttons.append([InlineKeyboardButton(
                text=f"🆕 #{order['order_number']} - {order['service_name']} - {order['total_price']:,} so‘m",
                callback_data=f"worker_accept_{order['id']}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"🔧 #{order['order_number']} - {order['service_name']}",
                callback_data=f"worker_complete_{order['id']}"
            )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
