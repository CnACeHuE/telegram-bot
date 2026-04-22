import sqlite3, os

DATABASE_URL = os.getenv('DATABASE_URL')

class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None and "postgresql" in DATABASE_URL
        self.connect()
        self.init_db()

    def connect(self):
        if self.is_pg:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else:
            self.conn = sqlite3.connect("abode_gods.db", check_same_thread=False)
        self.cursor = self.conn.cursor()

    def init_db(self):
        # Таблица душ
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, username TEXT, 
                power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0, 
                admin_rank INTEGER DEFAULT 0, clan_id INTEGER DEFAULT 0,
                clan_role TEXT DEFAULT 'Нет'
            )
        """)
        # Таблица Пантеонов
        self.execute("""
            CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_name TEXT UNIQUE, creator_id BIGINT,
                treasury INTEGER DEFAULT 0, level INTEGER DEFAULT 1
            )
        """)

    def execute(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        try:
            self.cursor.execute(sql, params)
            if "SELECT" in sql.upper(): return self.cursor.fetchone()
            self.conn.commit()
        except: self.connect(); return self.execute(sql, params)

    def fetchall(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()
