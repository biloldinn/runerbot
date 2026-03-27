import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from config import DB_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    """Ma'lumotlar bazasini yaratish"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Foydalanuvchilar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Xizmatlar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                duration INTEGER DEFAULT 60,
                category TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Buyurtmalar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                worker_id INTEGER,
                service_id INTEGER,
                status TEXT DEFAULT 'new',
                total_price REAL,
                payment_method TEXT,
                payment_status TEXT DEFAULT 'pending',
                receipt_url TEXT,
                comment TEXT,
                voice_note_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (worker_id) REFERENCES users(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        ''')
        
        # Hodim statistikasi jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS worker_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                date DATE,
                orders_count INTEGER DEFAULT 0,
                total_amount REAL DEFAULT 0,
                UNIQUE(worker_id, date),
                FOREIGN KEY (worker_id) REFERENCES users(id)
            )
        ''')
        
        # Admin panel foydalanuvchilari
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Default admin yaratish
        cursor.execute("SELECT * FROM admin_users WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO admin_users (username, password, role)
                VALUES (?, ?, ?)
            ''', ('admin', 'admin123', 'superadmin'))
        
        print("Ma'lumotlar bazasi tayyor!")

# ============ USER FUNKSIYALARI ============

def get_or_create_user(telegram_id, username=None, full_name=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute('''
                INSERT INTO users (telegram_id, username, full_name)
                VALUES (?, ?, ?)
            ''', (telegram_id, username, full_name))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user = cursor.fetchone()
        
        return dict(user)

def update_user_phone(telegram_id, phone):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone = ? WHERE telegram_id = ?", (phone, telegram_id))
        conn.commit()

def get_user_by_telegram_id(telegram_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        return dict(user) if user else None

def get_all_workers():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE role = 'worker' AND is_active = 1")
        return [dict(row) for row in cursor.fetchall()]

def add_worker(telegram_id, username, full_name, phone):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, username, full_name, phone, role)
            VALUES (?, ?, ?, ?, 'worker')
            ON CONFLICT(telegram_id) DO UPDATE SET role = 'worker', is_active = 1
        ''', (telegram_id, username, full_name, phone))
        conn.commit()

def remove_worker(telegram_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = 'user', is_active = 0 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

def get_next_worker_round_robin():
    """Eng kam buyurtma olgan faol hodimni qaytaradi (round-robin)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.telegram_id, u.full_name, u.phone,
                   COUNT(o.id) as active_orders
            FROM users u
            LEFT JOIN orders o ON o.worker_id = u.id
                AND o.status NOT IN ('completed', 'cancelled')
            WHERE u.role = 'worker' AND u.is_active = 1
            GROUP BY u.id
            ORDER BY active_orders ASC, u.id ASC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        return dict(row) if row else None


# ============ SERVICE FUNKSIYALARI ============

def get_all_services(active_only=True):
    with get_db() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM services WHERE is_active = 1 ORDER BY id")
        else:
            cursor.execute("SELECT * FROM services ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]

def get_service_by_id(service_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_service(name, description, price, duration, category):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO services (name, description, price, duration, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, price, duration, category))
        conn.commit()

def update_service(service_id, name, description, price, duration, category, is_active):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE services 
            SET name = ?, description = ?, price = ?, duration = ?, category = ?, is_active = ?
            WHERE id = ?
        ''', (name, description, price, duration, category, is_active, service_id))
        conn.commit()

def delete_service(service_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
        conn.commit()

# ============ ORDER FUNKSIYALARI ============

def generate_order_number():
    return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

def create_order(user_id, service_id, total_price, payment_method, comment=None, voice_note_url=None):
    order_number = generate_order_number()
    # Round-robin: avtomatik hodim tanlash
    next_worker = get_next_worker_round_robin()
    worker_id = next_worker['id'] if next_worker else None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (order_number, user_id, worker_id, service_id, total_price, payment_method, comment, voice_note_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, user_id, worker_id, service_id, total_price, payment_method, comment, voice_note_url,
              'accepted' if worker_id else 'new'))
        conn.commit()
        order_id = cursor.lastrowid
        return get_order_by_id(order_id), next_worker

def get_order_by_id(order_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, u.full_name as user_name, u.phone as user_phone, s.name as service_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN services s ON o.service_id = s.id
            WHERE o.id = ?
        ''', (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_orders_by_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, s.name as service_name
            FROM orders o
            LEFT JOIN services s ON o.service_id = s.id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_new_orders():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, u.full_name as user_name, u.phone as user_phone, s.name as service_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN services s ON o.service_id = s.id
            WHERE o.status = 'new' AND o.payment_status = 'confirmed'
            ORDER BY o.created_at ASC
        ''')
        return [dict(row) for row in cursor.fetchall()]

def get_worker_orders(worker_id, status=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute('''
                SELECT o.*, u.full_name as user_name, u.phone as user_phone, s.name as service_name
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.id
                LEFT JOIN services s ON o.service_id = s.id
                WHERE o.worker_id = ? AND o.status = ?
                ORDER BY o.created_at DESC
            ''', (worker_id, status))
        else:
            cursor.execute('''
                SELECT o.*, u.full_name as user_name, u.phone as user_phone, s.name as service_name
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.id
                LEFT JOIN services s ON o.service_id = s.id
                WHERE o.worker_id = ?
                ORDER BY o.created_at DESC
            ''', (worker_id,))
        return [dict(row) for row in cursor.fetchall()]

def update_order_status(order_id, status, worker_id=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if worker_id:
            cursor.execute('''
                UPDATE orders SET status = ?, worker_id = ?, accepted_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, worker_id, order_id))
        else:
            cursor.execute('''
                UPDATE orders SET status = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, order_id))
        conn.commit()

def update_order_payment_status(order_id, status, receipt_url=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if receipt_url:
            cursor.execute('''
                UPDATE orders SET payment_status = ?, receipt_url = ?
                WHERE id = ?
            ''', (status, receipt_url, order_id))
        else:
            cursor.execute('''
                UPDATE orders SET payment_status = ?
                WHERE id = ?
            ''', (status, order_id))
        conn.commit()

def assign_order_to_worker(order_id, worker_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders SET worker_id = ?, status = 'accepted', accepted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (worker_id, order_id))
        conn.commit()

def update_worker_stats(worker_id, amount):
    today = datetime.now().date()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO worker_stats (worker_id, date, orders_count, total_amount)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(worker_id, date) DO UPDATE SET
                orders_count = orders_count + 1,
                total_amount = total_amount + ?
        ''', (worker_id, today, amount, amount))
        conn.commit()

def get_worker_today_stats(worker_id):
    today = datetime.now().date()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT orders_count, total_amount FROM worker_stats
            WHERE worker_id = ? AND date = ?
        ''', (worker_id, today))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"orders_count": 0, "total_amount": 0}

def get_worker_history(worker_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT date, orders_count, total_amount FROM worker_stats
            WHERE worker_id = ?
            ORDER BY date DESC
            LIMIT 30
        ''', (worker_id,))
        return [dict(row) for row in cursor.fetchall()]

# ============ ADMIN FUNKSIYALARI ============

def get_all_orders():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, u.full_name as user_name, u.phone as user_phone, 
                   s.name as service_name, w.full_name as worker_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN services s ON o.service_id = s.id
            LEFT JOIN users w ON o.worker_id = w.id
            ORDER BY o.created_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

def get_statistics():
    with get_db() as conn:
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Bugungi buyurtmalar
        cursor.execute('''
            SELECT COUNT(*) as count, COALESCE(SUM(total_price), 0) as total
            FROM orders
            WHERE date(created_at) = ?
        ''', (today,))
        today_stats = cursor.fetchone()
        
        # Oylik buyurtmalar
        cursor.execute('''
            SELECT COUNT(*) as count, COALESCE(SUM(total_price), 0) as total
            FROM orders
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        ''')
        monthly_stats = cursor.fetchone()
        
        # Kutilayotgan buyurtmalar
        cursor.execute('''
            SELECT COUNT(*) FROM orders WHERE payment_status = 'pending'
        ''')
        pending_count = cursor.fetchone()[0]
        
        # Jarayondagi buyurtmalar
        cursor.execute('''
            SELECT COUNT(*) FROM orders WHERE status = 'accepted' OR status = 'in_progress'
        ''')
        in_progress_count = cursor.fetchone()[0]
        
        return {
            "today_orders": today_stats[0] or 0,
            "today_amount": today_stats[1] or 0,
            "monthly_orders": monthly_stats[0] or 0,
            "monthly_amount": monthly_stats[1] or 0,
            "pending_payments": pending_count,
            "in_progress_orders": in_progress_count
        }

def get_workers_ranking():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.full_name, 
                   COALESCE(SUM(ws.orders_count), 0) as total_orders,
                   COALESCE(SUM(ws.total_amount), 0) as total_amount
            FROM users u
            LEFT JOIN worker_stats ws ON u.id = ws.worker_id
            WHERE u.role = 'worker'
            GROUP BY u.id
            ORDER BY total_amount DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

def check_admin_user(username, password):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_users WHERE username = ? AND password = ?", (username, password))
        return cursor.fetchone() is not None
