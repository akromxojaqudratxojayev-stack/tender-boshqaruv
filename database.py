import os
from datetime import datetime

DB_PATH = "./tendir.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = 0

    def execute(self, sql, parameters=()):
        if parameters:
            sql = sql.replace('?', '%s')
        # Handle SQLite specific INSERT OR REPLACE -> PostgreSQL INSERT ... ON CONFLICT
        if sql.startswith("INSERT OR REPLACE INTO settings"):
            sql = "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        self.cursor.execute(sql, parameters)
        self.rowcount = self.cursor.rowcount
        return self

    def fetchall(self):
        return self.cursor.fetchall()
        
    def fetchone(self):
        return self.cursor.fetchone()

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        import psycopg2.extras
        return PostgresCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_connection():
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return PostgresConnectionWrapper(conn)
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL init
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            full_name TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id SERIAL PRIMARY KEY,
            link TEXT UNIQUE,
            title TEXT,
            deadline TIMESTAMP,
            start_date TIMESTAMP,
            total_sum TEXT,
            deposit_sum TEXT,
            company_name TEXT,
            delivery_term TEXT,
            source_site TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            group_message_id BIGINT,
            status TEXT DEFAULT 'active',
            full_text TEXT,
            is_started_notified BOOLEAN DEFAULT FALSE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tender_mutes (
            id SERIAL PRIMARY KEY,
            user_telegram_id BIGINT,
            tender_id INTEGER REFERENCES tenders(id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
    else:
        # SQLite init
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            full_name TEXT,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            title TEXT,
            deadline TIMESTAMP,
            start_date TIMESTAMP,
            total_sum TEXT,
            deposit_sum TEXT,
            company_name TEXT,
            delivery_term TEXT,
            source_site TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            group_message_id INTEGER,
            status TEXT DEFAULT 'active',
            full_text TEXT,
            is_started_notified BOOLEAN DEFAULT 0
        )
        ''')
        
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN start_date TIMESTAMP")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN total_sum TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN deposit_sum TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN company_name TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN delivery_term TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN group_message_id INTEGER")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN status TEXT DEFAULT 'active'")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN is_started_notified BOOLEAN DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE tenders ADD COLUMN full_text TEXT")
        except: pass
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tender_mutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_telegram_id INTEGER,
            tender_id INTEGER,
            FOREIGN KEY(tender_id) REFERENCES tenders(id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
    
    conn.commit()
    conn.close()

# Auto-initialize database on import
try:
    init_db()
except Exception as e:
    print("Database init error:", e)
