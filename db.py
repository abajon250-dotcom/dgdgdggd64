import sqlite3
from datetime import datetime, timedelta

DB_NAME = "bot_database.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            sub_end TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vk_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_data TEXT UNIQUE,
            is_valid INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def add_or_update_user(user_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
    ''', (user_id, username))
    conn.commit()
    conn.close()


def is_sub_active(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT sub_end FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    try:
        sub_end = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return datetime.now() < sub_end
    except Exception:
        return False


def get_sub_end_date(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT sub_end FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def set_subscription(user_id: int, days: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if days <= 0:
        new_end_str = None
    else:
        cursor.execute('SELECT sub_end FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        base_time = datetime.now()
        if row and row[0]:
            try:
                current_end = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                if current_end > base_time:
                    base_time = current_end
            except Exception:
                pass
        new_end = base_time + timedelta(days=days)
        new_end_str = new_end.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('UPDATE users SET sub_end = ? WHERE user_id = ?', (new_end_str, user_id))
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO users (user_id, sub_end) VALUES (?, ?)', (user_id, new_end_str))
    conn.commit()
    conn.close()
    return new_end_str or "Аннулирована"


def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_total_users_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def add_vk_accounts_bulk(accounts: list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    added = 0
    skipped = 0
    for acc in accounts:
        try:
            cursor.execute('INSERT INTO vk_accounts (account_data, is_valid) VALUES (?, 1)', (acc,))
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    return added, skipped


def get_user_vk_accounts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, account_data, is_valid FROM vk_accounts')
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_vk_accounts_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM vk_accounts')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM vk_accounts WHERE is_valid = 1')
    valid = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM vk_accounts WHERE is_valid = 0')
    invalid = cursor.fetchone()[0]
    conn.close()
    return {"total": total, "valid": valid, "invalid": invalid}


def clear_all_vk_accounts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vk_accounts')
    conn.commit()
    conn.close()