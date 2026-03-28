import motor.motor_asyncio
from datetime import datetime, timedelta
import asyncio
from config import MONGODB_URI, DATABASE_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE_NAME]

async def init_db():
    """MongoDB indekslarini yaratish"""
    # Unique indexes
    await db.users.create_index("telegram_id", unique=True)
    await db.orders.create_index("order_number", unique=True)
    await db.admin_users.create_index("username", unique=True)
    await db.worker_stats.create_index([("worker_id", 1), ("date", 1)], unique=True)
    await db.locks.create_index("name", unique=True)

async def check_and_lock_instance(instance_name="bot_main"):
    """Boshqa bot ishlayotganini tekshiradi va lock qo'yadi"""
    # 30 sekunddan oshgan locklarni ochilgan deb hisoblaymiz (dead lock prevention)
    expiry_time = datetime.now() - timedelta(seconds=120)
    
    # Eskirgan lockni o'chirish
    await db.locks.delete_many({"name": instance_name, "last_heartbeat": {"$lt": expiry_time}})
    
    try:
        await db.locks.insert_one({
            "name": instance_name,
            "last_heartbeat": datetime.now(),
            "started_at": datetime.now()
        })
        return True
    except:
        return False

async def update_heartbeat(instance_name="bot_main"):
    await db.locks.update_one(
        {"name": instance_name},
        {"$set": {"last_heartbeat": datetime.now()}}
    )

async def release_lock(instance_name="bot_main"):
    await db.locks.delete_many({"name": instance_name})
    
    # Initialize default settings
    if not await db.settings.find_one({"key": "contact_info"}):
        await db.settings.insert_one({
            "key": "contact_info",
            "phone": "+998 90 123 45 67",
            "address": "Turon o‘quv markazi",
            "work_hours": "09:00 - 18:00",
            "card_number": "",
            "card_owner": ""
        })

async def get_settings():
    return await db.settings.find_one({"key": "contact_info"})

async def update_settings(data):
    await db.settings.update_one({"key": "contact_info"}, {"$set": data}, upsert=True)
    
    # Check if default admin exists
    admin = await db.admin_users.find_one({"username": "admin"})
    if not admin:
        await db.admin_users.insert_one({
            "username": "admin",
            "password": "admin123", # Plain text as per original code
            "role": "superadmin",
            "created_at": datetime.now()
        })
    print("MongoDB tayyor!")

# ============ USER FUNKSIYALARI ============

async def get_or_create_user(telegram_id, username=None, full_name=None):
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        new_user = {
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "phone": None,
            "role": "user",
            "is_active": True,
            "created_at": datetime.now()
        }
        await db.users.insert_one(new_user)
        user = await db.users.find_one({"telegram_id": telegram_id})
    return user

async def get_all_users():
    return await db.users.find({}).to_list(length=None)


async def update_user_name(telegram_id, full_name):
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"full_name": full_name}}
    )

async def update_user_phone(telegram_id, phone):
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"phone": phone}}
    )

async def get_user_by_telegram_id(telegram_id):
    return await db.users.find_one({"telegram_id": telegram_id})

async def get_all_workers():
    workers = await db.users.find({"role": "worker", "is_active": True}).to_list(length=None)
    return workers

async def add_worker(telegram_id, username, full_name, phone):
    await db.users.update_one(
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

async def remove_worker(telegram_id):
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"role": "user", "is_active": False}}
    )

async def get_next_worker_round_robin():
    """Eng kam buyurtma olgan faol hodimni qaytaradi"""
    # Simple logic: Sort by total active orders
    workers = await db.users.find({"role": "worker", "is_active": True}).to_list(length=None)
    if not workers:
        return None
    
    # Count active orders for each worker
    worker_loads = []
    for w in workers:
        count = await db.orders.count_documents({
            "worker_id": w["telegram_id"], # Link by telegram_id now for simplicity
            "status": {"$nin": ["completed", "cancelled"]}
        })
        worker_loads.append({"worker": w, "count": count})
    
    # Sort by count
    worker_loads.sort(key=lambda x: x["count"])
    return worker_loads[0]["worker"]

# ============ SERVICE FUNKSIYALARI ============

async def get_all_services(active_only=True):
    query = {"is_active": True} if active_only else {}
    services = await db.services.find(query).sort("created_at", 1).to_list(length=None)
    # Convert _id to id string for frontend compatibility if needed, or just use as is
    for s in services:
        s['id'] = str(s['_id'])
    return services

async def get_service_by_id(service_id):
    from bson.objectid import ObjectId
    try:
        service = await db.services.find_one({"_id": ObjectId(service_id)})
        if service:
            service['id'] = str(service['_id'])
        return service
    except:
        return None

async def add_service(name, description, price, duration, category):
    await db.services.insert_one({
        "name": name,
        "description": description,
        "price": float(price),
        "duration": int(duration),
        "category": category,
        "is_active": True,
        "created_at": datetime.now()
    })

async def update_service(service_id, name, description, price, duration, category, is_active):
    from bson.objectid import ObjectId
    await db.services.update_one(
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

async def delete_service(service_id):
    from bson.objectid import ObjectId
    await db.services.delete_one({"_id": ObjectId(service_id)})

# ============ ORDER FUNKSIYALARI ============

def generate_order_number():
    return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

async def create_order(user_id, service_id, total_price, payment_method, comment=None, voice_note_url=None):
    order_number = generate_order_number()
    next_worker = await get_next_worker_round_robin()
    worker_id = next_worker['telegram_id'] if next_worker else None # Store telegram_id
    
    # Find service name
    service = await get_service_by_id(service_id)
    service_name = service['name'] if service else "Noma'lum"

    # Find user info
    user = await db.users.find_one({"telegram_id": user_id})
    user_name = user['full_name'] if user else "Mijoz"

    new_order = {
        "order_number": order_number,
        "user_id": user_id,
        "user_name": user_name,
        "worker_id": worker_id,
        "service_id": service_id,
        "service_name": service_name,
        "total_price": float(total_price),
        "payment_method": payment_method,
        "payment_status": "at_location" if payment_method == "at_location" else "pending",
        "status": "accepted" if worker_id else "new",
        "comment": comment,
        "voice_note_url": voice_note_url,
        "receipt_url": None,
        "created_at": datetime.now(),
        "accepted_at": datetime.now() if worker_id else None,
        "completed_at": None
    }
    
    result = await db.orders.insert_one(new_order)
    new_order['id'] = str(result.inserted_id)
    return new_order, next_worker

async def get_order_by_id(order_id):
    from bson.objectid import ObjectId
    try:
        order = await db.orders.find_one({"_id": ObjectId(order_id)})
        if order:
            order['id'] = str(order['_id'])
        return order
    except:
        return None

async def get_orders_by_user(user_id):
    orders = await db.orders.find({"user_id": user_id}).sort("created_at", -1).to_list(length=None)
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

async def get_new_orders():
    orders = await db.orders.find({
        "status": "new", 
        "payment_status": {"$in": ["confirmed", "at_location"]}
    }).sort("created_at", 1).to_list(length=None)
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

async def get_worker_orders(worker_id, status=None):
    query = {"worker_id": worker_id}
    if status:
        query["status"] = status
    orders = await db.orders.find(query).sort("created_at", -1).to_list(length=None)
    for o in orders:
        o['id'] = str(o['_id'])
    return orders

async def update_order_status(order_id, status, worker_id=None):
    from bson.objectid import ObjectId
    update_data = {"status": status}
    if worker_id:
        update_data["worker_id"] = worker_id
        update_data["accepted_at"] = datetime.now()
    if status == "completed":
        update_data["completed_at"] = datetime.now()
        
    await db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_data}
    )

async def update_order_payment_status(order_id, status, receipt_url=None):
    from bson.objectid import ObjectId
    update_data = {"payment_status": status}
    if receipt_url:
        update_data["receipt_url"] = receipt_url
    
    await db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_data}
    )

async def assign_order_to_worker(order_id, worker_id):
    from bson.objectid import ObjectId
    await db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"worker_id": worker_id, "status": "accepted", "accepted_at": datetime.now()}}
    )

async def update_worker_stats(worker_id, amount):
    today = datetime.now().strftime("%Y-%m-%d")
    await db.worker_stats.update_one(
        {"worker_id": worker_id, "date": today},
        {"$inc": {"orders_count": 1, "total_amount": float(amount)}},
        upsert=True
    )

async def get_worker_today_stats(worker_id):
    today = datetime.now().strftime("%Y-%m-%d")
    stats = await db.worker_stats.find_one({"worker_id": worker_id, "date": today})
    if stats:
        return stats
    return {"orders_count": 0, "total_amount": 0}

async def get_worker_history(worker_id):
    history = await db.worker_stats.find({"worker_id": worker_id}).sort("date", -1).limit(30).to_list(length=None)
    return history

# ============ ADMIN FUNKSIYALARI ============

async def get_all_orders():
    orders = await db.orders.find().sort("created_at", -1).to_list(length=None)
    for o in orders:
        o['id'] = str(o['_id'])
        # Add worker_name
        if o.get('worker_id'):
            worker = await db.users.find_one({"telegram_id": o['worker_id']})
            o['worker_name'] = worker['full_name'] if worker else "Noma'lum"
    return orders

async def get_statistics():
    today_str = datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.now().strftime("%Y-%m")
    
    # Today
    today_query = {"created_at": {"$gte": datetime.strptime(today_str, "%Y-%m-%d")}}
    today_orders = await db.orders.count_documents(today_query)
    
    # Today total amount (aggregation)
    pipeline = [
        {"$match": today_query},
        {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
    ]
    today_res = await db.orders.aggregate(pipeline).to_list(length=1)
    today_amount = today_res[0]['total'] if today_res else 0

    # Pending and in progress
    pending = await db.orders.count_documents({"payment_status": "pending"})
    in_progress = await db.orders.count_documents({"status": {"$in": ["accepted", "in_progress"]}})

    return {
        "today_orders": today_orders,
        "today_amount": today_amount,
        "monthly_orders": 0, # Simplified for now
        "monthly_amount": 0,
        "pending_payments": pending,
        "in_progress_orders": in_progress
    }

async def get_workers_ranking():
    # Group by worker_id in orders or worker_stats
    pipeline = [
        {"$group": {
            "_id": "$worker_id", 
            "total_orders": {"$sum": 1},
            "total_amount": {"$sum": "$total_price"}
        }},
        {"$sort": {"total_amount": -1}}
    ]
    results = await db.orders.aggregate(pipeline).to_list(length=None)
    
    ranking = []
    for res in results:
        if res['_id']:
            worker = await db.users.find_one({"telegram_id": res['_id']})
            if worker:
                ranking.append({
                    "full_name": worker['full_name'],
                    "total_orders": res['total_orders'],
                    "total_amount": res['total_amount'],
                    "phone": worker.get('phone', '')
                })
    return ranking

async def check_admin_user(username, password):
    user = await db.admin_users.find_one({"username": username, "password": password})
    return user is not None

async def get_admin_user(username, password):
    return await db.admin_users.find_one({"username": username, "password": password})

async def get_admin_by_id(user_id):
    from bson.objectid import ObjectId
    try:
        return await db.admin_users.find_one({"_id": ObjectId(user_id)})
    except:
        return None
