import pymongo
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from config import MONGODB_URI, DATABASE_NAME

client = pymongo.MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

async def init_db():
    """MongoDB indekslarini yaratish"""
    db.users.create_index("telegram_id", unique=True)
    db.orders.create_index("order_number", unique=True)
    db.admin_users.create_index("username", unique=True)
    db.worker_stats.create_index([("worker_id", 1), ("date", 1)], unique=True)
    
    # Check if default admin exists
    admin = db.admin_users.find_one({"username": "admin"})
    if not admin:
        db.admin_users.insert_one({
            "username": "admin",
            "password": "admin123",
            "role": "superadmin",
            "created_at": datetime.now()
        })

# ============ SETTINGS FUNKSIYALARI ============

def get_settings():
    settings = db.settings.find_one({"type": "general"})
    if not settings:
        return {
            "phone": "+998 90 123 45 67",
            "address": "Turon o'quv markazi",
            "work_hours": "09:00 - 18:00",
            "card_number": "8600 1234 5678 9012",
            "card_owner": "TURON OQUV MARKAZI"
        }
    return settings

def get_all_users():
    users = list(db.users.find())
    for u in users:
        u['id'] = str(u['_id'])
    return users

def update_settings(data):
    db.settings.update_one(
        {"type": "general"},
        {"$set": data},
        upsert=True
    )
    return True

# ============ USER FUNKSIYALARI ============

def get_or_create_user(telegram_id, username=None, full_name=None):
    user = db.users.find_one({"telegram_id": telegram_id})
    if not user:
        new_user = {
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "phone": None,
            "role": "user",
            "balance": 0,
            "rating_sum": 0,
            "rating_count": 0,
            "is_active": True,
            "created_at": datetime.now()
        }
        db.users.insert_one(new_user)
        user = db.users.find_one({"telegram_id": telegram_id})
    return user

def get_user_by_telegram_id(telegram_id):
    return db.users.find_one({"telegram_id": telegram_id})

def get_all_workers():
    workers = list(db.users.find({"role": "worker", "is_active": True}))
    for w in workers:
        w['id'] = str(w['_id'])
    return workers

def find_user_by_username(username):
    if not username: return None
    username = username.replace("@", "")
    return db.users.find_one({"username": username})

def add_worker(telegram_id, username, full_name, phone):
    db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {
            "username": username,
            "full_name": full_name,
            "phone": phone,
            "role": "worker",
            "is_active": True
        }},
        upsert=True
    )

def update_worker_balance(worker_id, amount):
    db.users.update_one(
        {"telegram_id": worker_id},
        {"$inc": {"balance": float(amount)}}
    )

def update_user_name(telegram_id, full_name):
    db.users.update_one({"telegram_id": telegram_id}, {"$set": {"full_name": full_name}})

def update_user_phone(telegram_id, phone):
    db.users.update_one({"telegram_id": telegram_id}, {"$set": {"phone": phone}})

# ============ SERVICE FUNKSIYALARI ============

def get_all_services(active_only=True):
    query = {"is_active": True} if active_only else {}
    services = list(db.services.find(query).sort("created_at", 1))
    for s in services:
        s['id'] = str(s['_id'])
    return services

def get_service_by_id(service_id):
    try:
        service = db.services.find_one({"_id": ObjectId(service_id)})
        if service:
            service['id'] = str(service['_id'])
        return service
    except:
        return None

def add_service(name, description, price, duration, category):
    db.services.insert_one({
        "name": name,
        "description": description,
        "price": float(price),
        "duration": int(duration),
        "category": category,
        "is_active": True,
        "created_at": datetime.now()
    })

# ============ ORDER FUNKSIYALARI ============

def create_order(user_id, service_id, total_price, payment_method, comment=None, voice_note_url=None, photos=None, documents=None, pickup_day=None):
    from random import choice
    
    if service_id == "other":
        service_name = "Boshqa xizmat"
    else:
        service = get_service_by_id(service_id)
        service_name = service['name'] if service else "Boshqa xizmat"
    
    workers = get_all_workers()
    assigned_worker = choice(workers) if workers else None
    worker_id = assigned_worker['telegram_id'] if assigned_worker else None
    
    user = get_user_by_telegram_id(user_id)
    
    order_doc = {
        "order_number": db.orders.count_documents({}) + 1001,
        "user_id": user_id,
        "user_name": user['full_name'],
        "user_phone": user.get('phone'),
        "service_id": service_id,
        "service_name": service_name,
        "total_price": float(total_price),
        "payment_method": payment_method,
        "payment_status": "pending",
        "status": "new",
        "comment": comment,
        "voice_note_url": voice_note_url,
        "photos": photos or [],
        "documents": documents or [],
        "pickup_day": pickup_day,
        "worker_id": worker_id,
        "rating": None,
        "created_at": datetime.now(),
        "completed_at": None,
        "accepted_at": None
    }
    
    res = db.orders.insert_one(order_doc)
    order_doc['id'] = str(res.inserted_id)
    return order_doc, assigned_worker

def get_order_by_id(order_id):
    try:
        order = db.orders.find_one({"_id": ObjectId(order_id)})
        if order:
            order['id'] = str(order['_id'])
        return order
    except:
        return None

def get_orders_by_user(user_id):
    orders = list(db.orders.find({"user_id": user_id}).sort("created_at", -1))
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

def update_order_payment_status(order_id, status, receipt_url=None):
    update_data = {"payment_status": status}
    if receipt_url:
        update_data["receipt_url"] = receipt_url
    
    order = get_order_by_id(order_id)
    if not order: return
    
    db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_data}
    )
    
    if status == "confirmed" and order.get('worker_id'):
        update_worker_balance(order['worker_id'], order['total_price'])

def update_order_status(order_id, status):
    update_data = {"status": status}
    if status == "completed":
        update_data["completed_at"] = datetime.now()
    
    order = get_order_by_id(order_id)
    if not order: return

    db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_data}
    )
    
    if status == "completed" and order.get('payment_method') == "at_location" and order.get('worker_id'):
        update_worker_balance(order['worker_id'], order['total_price'])

def rate_order(order_id, rating):
    order = get_order_by_id(order_id)
    if not order or not order.get('worker_id'): return
    
    db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"rating": int(rating)}}
    )
    
    db.users.update_one(
        {"telegram_id": order['worker_id']},
        {"$inc": {"rating_sum": int(rating), "rating_count": 1}}
    )

# ============ WORKER STATS ============

def update_worker_stats(worker_id, amount):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    db.worker_stats.update_one(
        {"worker_id": worker_id, "date": today},
        {"$inc": {"orders_count": 1, "total_amount": float(amount)}},
        upsert=True
    )

def get_worker_today_stats(worker_id):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stat = db.worker_stats.find_one({"worker_id": worker_id, "date": today})
    if not stat:
        return {"orders_count": 0, "total_amount": 0}
    stat['id'] = str(stat['_id'])
    return stat

def get_worker_history(worker_id, days=30):
    start_date = datetime.now() - timedelta(days=days)
    history = list(db.worker_stats.find({
        "worker_id": worker_id, 
        "date": {"$gte": start_date}
    }).sort("date", -1))
    for h in history:
        h['id'] = str(h['_id'])
    return history

# ============ CONFLICT PREVENTION (LOCKING) ============

async def check_and_lock_instance(instance_id="local"):
    """Conflict prevention bypassed for migration fixes"""
    return True

async def update_heartbeat():
    pass

async def release_lock():
    pass
