import sqlite3
from datetime import datetime

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            plan TEXT DEFAULT 'free',
            used_this_month INTEGER DEFAULT 0,
            last_reset TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT plan, used_this_month, last_reset FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_user(user_id, plan=None, used_this_month=None, last_reset=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if get_user(user_id) is None:
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
    if plan:
        c.execute('UPDATE users SET plan=? WHERE user_id=?', (plan, user_id))
    if used_this_month is not None:
        c.execute('UPDATE users SET used_this_month=? WHERE user_id=?', (used_this_month, user_id))
    if last_reset:
        c.execute('UPDATE users SET last_reset=? WHERE user_id=?', (last_reset, user_id))
    conn.commit()
    conn.close()

def increment_usage(user_id):
    row = get_user(user_id)
    if row:
        used = row[1] or 0
        update_user(user_id, used_this_month=used+1)

def reset_monthly_usage(user_id):
    update_user(user_id, used_this_month=0, last_reset=datetime.now().strftime("%Y-%m")) 