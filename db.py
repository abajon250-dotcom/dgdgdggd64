import sqlite3
from datetime import datetime, timedelta

DB_NAME = "database.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            sub_end TEXT
        )
    ''')

    # Таблица VK аккаунтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vk_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT,
            name TEXT,
            friends INTEGER,
            is_valid BOOLEAN DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()


def add_or_update_user(user_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, username, sub_end) VALUES (?, ?, ?)",
                       (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def is_sub_active(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sub_end FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    try:
        sub_end = datetime.fromisoformat(row[0])
        return datetime.now() < sub_end
    except Exception:
        return False


def get_sub_end_date(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sub_end FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0])
    except Exception:
        return None


def set_subscription(user_id: int, days: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sub_end FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    now = datetime.now()
    if row and row[0]:
        try:
            current_end = datetime.fromisoformat(row[0])
            base_time = current_end if current_end > now else now
        except Exception:
            base_time = now
    else:
        base_time = now

    new_end = base_time + timedelta(days=days)

    if row:
        cursor.execute("UPDATE users SET sub_end = ? WHERE user_id = ?", (new_end.isoformat(), user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, sub_end) VALUES (?, ?)", (user_id, new_end.isoformat()))
    conn.commit()
    conn.close()


def revoke_subscription(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET sub_end = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()


def get_vk_accounts_stats(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN is_valid = 1 THEN 1 ELSE 0 END), 
               SUM(CASE WHEN is_valid = 0 THEN 1 ELSE 0 END) 
        FROM vk_accounts WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    total = row[0] or 0
    valid = row[1] or 0
    invalid = row[2] or 0
    return {"total": total, "valid": valid, "invalid": invalid}


def get_user_vk_accounts(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT token, name, friends, is_valid FROM vk_accounts WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    accounts = []
    for r in rows:
        accounts.append({
            "token": r[0],
            "name": r[1],
            "friends": r[2],
            "is_valid": bool(r[3])
        })
    return accounts


def save_vk_account(user_id: int, token: str, name: str, friends: int, is_valid: bool = True):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO vk_accounts (user_id, token, name, friends, is_valid) VALUES (?, ?, ?, ?, ?)",
                   (user_id, token, name, friends, 1 if is_valid else 0))
    conn.commit()
    conn.close()


def clear_user_vk_accounts(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vk_accounts WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_users_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    row = cursor.fetchone()
    conn.close()
    return row[0] or 0


init_db()