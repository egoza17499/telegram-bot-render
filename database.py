import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

DB_NAME = "users.db"

def init_db():
    """Создаёт все таблицы"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            surname TEXT NOT NULL,
            name TEXT NOT NULL,
            patronymic TEXT,
            rank TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица ВЛК и УМО
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical (
            telegram_id INTEGER PRIMARY KEY,
            vlk_date DATE,
            umo_date DATE,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    # Таблица проверок КБП
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            telegram_id INTEGER PRIMARY KEY,
            exercise_4_date DATE,
            exercise_7_date DATE,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    # Таблица отпусков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vacation (
            telegram_id INTEGER PRIMARY KEY,
            start_date DATE,
            end_date DATE,
            days INTEGER,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    conn.commit()
    conn.close()

# ==================== USERS ====================
def add_user(telegram_id: int, surname: str, name: str, patronymic: str, rank: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (telegram_id, surname, name, patronymic, rank)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, surname, name, patronymic, rank))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(telegram_id: int) -> Optional[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_user(telegram_id: int, surname: str = None, name: str = None, 
                patronymic: str = None, rank: str = None) -> bool:
    """Обновляет данные пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if surname:
        cursor.execute("UPDATE users SET surname = ? WHERE telegram_id = ?", (surname, telegram_id))
    if name:
        cursor.execute("UPDATE users SET name = ? WHERE telegram_id = ?", (name, telegram_id))
    if patronymic:
        cursor.execute("UPDATE users SET patronymic = ? WHERE telegram_id = ?", (patronymic, telegram_id))
    if rank:
        cursor.execute("UPDATE users SET rank = ? WHERE telegram_id = ?", (rank, telegram_id))
    
    conn.commit()
    conn.close()
    return True

def delete_user(telegram_id: int) -> bool:
    """Удаляет пользователя и все связанные данные"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        cursor.execute("DELETE FROM medical WHERE telegram_id = ?", (telegram_id,))
        cursor.execute("DELETE FROM checks WHERE telegram_id = ?", (telegram_id,))
        cursor.execute("DELETE FROM vacation WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def get_all_users() -> List[Tuple]:
    """Получает всех пользователей (для админа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, surname, name, rank, created_at FROM users")
    result = cursor.fetchall()
    conn.close()
    return result

# ==================== MEDICAL (ВЛК/УМО) ====================
def add_medical(telegram_id: int, vlk_date: str, umo_date: str = None) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO medical (telegram_id, vlk_date, umo_date)
            VALUES (?, ?, ?)
        """, (telegram_id, vlk_date, umo_date))
        conn.commit()
        return True
    finally:
        conn.close()

def get_medical(telegram_id: int) -> Optional[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medical WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def check_vlk_status(vlk_date: str) -> dict:
    """Проверяет статус ВЛК"""
    vlk = datetime.strptime(vlk_date, "%Y-%m-%d")
    today = datetime.now()
    days_passed = (today - vlk).days
    vlk_valid_days = 365
    days_remaining = vlk_valid_days - days_passed
    umo_deadline = 180
    
    return {
        "days_passed": days_passed,
        "days_remaining": days_remaining,
        "umo_needed": days_passed >= umo_deadline,
        "vlk_expired": days_passed >= vlk_valid_days,
        "remind_30": 0 < days_remaining <= 30,
        "remind_15": 0 < days_remaining <= 15,
        "remind_7": 0 < days_remaining <= 7,
    }

# ==================== CHECKS (КБП) ====================
def add_check(telegram_id: int, exercise: int, check_date: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if exercise == 4:
        cursor.execute("""
            INSERT OR REPLACE INTO checks (telegram_id, exercise_4_date)
            VALUES (?, ?)
        """, (telegram_id, check_date))
    elif exercise == 7:
        cursor.execute("""
            INSERT OR REPLACE INTO checks (telegram_id, exercise_7_date)
            VALUES (?, ?)
        """, (telegram_id, check_date))
    
    conn.commit()
    conn.close()
    return True

def add_check(telegram_id: int, exercise: int, check_date: str) -> bool:
    """Добавляет или обновляет проверку КБП"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Сначала проверяем есть ли пользователь
    cursor.execute("SELECT telegram_id FROM checks WHERE telegram_id = ?", (telegram_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Если есть — обновляем нужное поле
        if exercise == 4:
            cursor.execute("""
                UPDATE checks SET exercise_4_date = ? WHERE telegram_id = ?
            """, (check_date, telegram_id))
        elif exercise == 7:
            cursor.execute("""
                UPDATE checks SET exercise_7_date = ? WHERE telegram_id = ?
            """, (check_date, telegram_id))
    else:
        # Если нет — создаём новую запись
        if exercise == 4:
            cursor.execute("""
                INSERT INTO checks (telegram_id, exercise_4_date, exercise_7_date)
                VALUES (?, ?, NULL)
            """, (telegram_id, check_date))
        elif exercise == 7:
            cursor.execute("""
                INSERT INTO checks (telegram_id, exercise_4_date, exercise_7_date)
                VALUES (?, NULL, ?)
            """, (telegram_id, check_date))
    
    conn.commit()
    conn.close()
    return True

def check_exercise_status(check_date: str, valid_months: int) -> dict:
    check = datetime.strptime(check_date, "%Y-%m-%d")
    today = datetime.now()
    valid_until = check + timedelta(days=valid_months * 30)
    days_remaining = (valid_until - today).days
    
    return {
        "days_remaining": days_remaining,
        "expired": days_remaining < 0,
        "valid_until": valid_until.strftime("%d.%m.%Y")
    }

# ==================== VACATION (Отпуск) ====================
def add_vacation(telegram_id: int, start_date: str, end_date: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1
    
    cursor.execute("""
        INSERT OR REPLACE INTO vacation (telegram_id, start_date, end_date, days)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, start_date, end_date, days))
    
    conn.commit()
    conn.close()
    return True

def get_vacation(telegram_id: int) -> Optional[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vacation WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def check_vacation_status(end_date: str) -> dict:
    end = datetime.strptime(end_date, "%Y-%m-%d")
    today = datetime.now()
    days_passed = (today - end).days
    days_until_year = 365 - days_passed
    
    return {
        "days_passed": days_passed,
        "days_until_next": days_until_year,
        "expired": days_passed >= 365,
        "remind_30": 0 < days_until_year <= 30,
        "remind_15": 0 < days_until_year <= 15,
        "remind_7": 0 < days_until_year <= 7,
    }

