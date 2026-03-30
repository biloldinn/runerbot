import pymongo
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from config import MONGODB_URI, DATABASE_NAME

client = pymongo.MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

async def init_db():
    """MongoDB indekslarini yaratish (Sync)"""
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
    
    # Check if settings exist
    settings = db.settings.find_one({"type": "general"})
    if not settings:
        db.settings.insert_one({
            "type": "general",
            "phone": "+998 90 123 45 67",
            "card_number": "8600 0000 0000 0000",
            "card_owner": "TURON ADMIN",
            "address": "Markaziy bino"
        })

# ============ SETTINGS FUNKSIYALARI ============

def get_settings():
    return db.settings.find_one({"type": "general"})

def update_settings(new_settings):
    db.settings.update_one(
        {"type": "general"},
        {"$set": new_settings}
    )

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

def get_all_users_count():
    return db.users.count_documents({})

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
            "is_active": True,
            "balance": 0
        }},
        upsert=True
    )

def remove_worker(telegram_id):
    db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"role": "user", "is_active": False}}
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

def update_service(service_id, name, description, price, duration, category, is_active):
    db.services.update_one(
        {"_id": ObjectId(service_id)},
        {"$set": {
            "name": name,
            "description": description,
            "price": float(price),
            "duration": int(duration),
            "category": category,
            "is_active": bool(is_active)
        }}
    )

def delete_service(service_id):
    db.services.delete_one({"_id": ObjectId(service_id)})

# ============ ORDER FUNKSIYALARI ============

async def create_order(user_id, service_id, total_price, payment_method, comment=None, voice_note_url=None, photos=None, documents=None, pickup_day=None):
    from random import choice
    
    # Xizmat nomini olish
    service = await get_service_by_id(service_id)
    service_name = service['name'] if service else "Boshqa xizmat"
    
    # Hodimni biriktirish (Round-robin)
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

def get_all_orders():
    orders = list(db.orders.find().sort("created_at", -1))
    for o in orders:
        o['id'] = str(o['_id'])
        if o.get('worker_id'):
            worker = db.users.find_one({"telegram_id": o['worker_id']})
            o['worker_name'] = worker['full_name'] if worker else "Noma'lum"
    return orders

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
    
    # If confirmed and has a worker, add to balance
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
    
    # If completed and payment_method is at_location, add to balance
    if status == "completed" and order.get('payment_method') == "at_location" and order.get('worker_id'):
        update_worker_balance(order['worker_id'], order['total_price'])

def assign_order_to_worker(order_id, worker_id):
    db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"worker_id": worker_id, "status": "accepted", "accepted_at": datetime.now()}}
    )

def rate_order(order_id, rating):
    order = get_order_by_id(order_id)
    if not order or not order.get('worker_id'): return
    
    db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"rating": int(rating)}}
    )
    
    # Update worker's rating
    db.users.update_one(
        {"telegram_id": order['worker_id']},
        {"$inc": {"rating_sum": int(rating), "rating_count": 1}}
    )

# ============ STATISTIKA ============

def get_statistics():
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    today_orders = db.orders.count_documents({"created_at": {"$gte": today}})
    
    # Today amount
    today_res = list(db.orders.aggregate([
        {"$match": {"created_at": {"$gte": today}, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
    ]))
    today_amount = today_res[0]['total'] if today_res else 0

    # Monthly amount
    month_res = list(db.orders.aggregate([
        {"$match": {"created_at": {"$gte": month_start}, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}, "count": {"$sum": 1}}}
    ]))
    monthly_amount = month_res[0]['total'] if month_res else 0
    monthly_orders = month_res[0]['count'] if month_res else 0

    pending = db.orders.count_documents({"payment_status": "pending"})
    in_progress = db.orders.count_documents({"status": {"$in": ["accepted", "in_progress"]}})
    total_users = db.users.count_documents({})

    return {
        "today_orders": today_orders,
        "today_amount": today_amount,
        "monthly_orders": monthly_orders,
        "monthly_amount": monthly_amount,
        "pending_payments": pending,
        "in_progress_orders": in_progress,
        "total_start_users": total_users
    }

def get_workers_ranking():
    # Use users collection for stats to include balance and average rating
    workers = list(db.users.find({"role": "worker"}))
    ranking = []
    
    for w in workers:
        # Get count of completed orders
        completed_count = db.orders.count_documents({"worker_id": w['telegram_id'], "status": "completed"})
        
        avg_rating = 0
        if w.get('rating_count', 0) > 0:
            avg_rating = round(w['rating_sum'] / w['rating_count'], 1)
            
        ranking.append({
            "full_name": w['full_name'],
            "telegram_id": w['telegram_id'],
            "total_orders": completed_count,
            "total_amount": w.get('balance', 0), # Balance is their earned amount
            "rating": avg_rating,
            "rating_count": w.get('rating_count', 0),
            "phone": w.get('phone', ''),
            "is_active": w.get('is_active', True)
        })
    
    # Sort by balance descending
    ranking.sort(key=lambda x: x['total_amount'], reverse=True)
    return ranking

def get_admin_user(username, password):
    return db.admin_users.find_one({"username": username, "password": password})

def get_admin_by_id(user_id):
    try:
        return db.admin_users.find_one({"_id": ObjectId(user_id)})
    except:
        return None

# ============ YANGILIKLAR VA E'LONLAR ============

def get_all_news(limit=10):
    news = list(db.news.find().sort("created_at", -1).limit(limit))
    for item in news:
        item['id'] = str(item['_id'])
    return news

def add_news(title, content, author="Admin"):
    return db.news.insert_one({
        "title": title,
        "content": content,
        "author": author,
        "created_at": datetime.now()
    })

def delete_news(news_id):
    try:
        db.news.delete_one({"_id": ObjectId(news_id)})
        return True
    except:
        return False
def get_all_users():
    users = list(db.users.find())
    for u in users:
        u['id'] = str(u['_id'])
    return users

# ============ CONFLICT PREVENTION (LOCKING) ============

async def check_and_lock_instance():
    """Boshqa instance ishlayotganini tekshirish va lock qo'yish"""
    import socket
    hostname = socket.gethostname()
    now = datetime.now()
    
    lock = db.locks.find_one({"type": "bot_poll"})
    
    if lock:
        # Agar lock 120 soniyadan ko'p vaqt oldin yangilangan bo'lsa, u eskirdi deb hisoblaymiz
        if now - lock['last_heartbeat'] > timedelta(seconds=120):
            db.locks.update_one(
                {"type": "bot_poll"},
                {"$set": {"hostname": hostname, "last_heartbeat": now, "status": "active"}}
            )
            return True
        else:
            # Boshqa biri ishlayapti
            return False
    else:
        # Yangi lock yaratish
        db.locks.insert_one({
            "type": "bot_poll",
            "hostname": hostname,
            "last_heartbeat": now,
            "status": "active"
        })
        return True

async def update_heartbeat():
    """Lockni yangilab turish"""
    import socket
    hostname = socket.gethostname()
    db.locks.update_one(
        {"type": "bot_poll", "hostname": hostname},
        {"$set": {"last_heartbeat": datetime.now()}}
    )

async def release_lock():
    """Lockni bo'shatish"""
    import socket
    hostname = socket.gethostname()
    db.locks.delete_one({"type": "bot_poll", "hostname": hostname})

def get_new_orders():
    orders = list(db.orders.find({"status": "new"}).sort("created_at", -1))
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

def get_worker_orders(worker_id, status):
    orders = list(db.orders.find({"worker_id": worker_id, "status": status}).sort("created_at", -1))
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

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
    return stat

def get_worker_history(worker_id, days=30):
    start_date = datetime.now() - timedelta(days=days)
    history = list(db.worker_stats.find({
        "worker_id": worker_id, 
        "date": {"$gte": start_date}
    }).sort("date", -1))
    return history
