import psycopg2
import os

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Таблица пользователей
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                power_points BIGINT DEFAULT 100,
                msg_count INTEGER DEFAULT 0,
                admin_rank INTEGER DEFAULT 0,
                clan_id INTEGER,
                clan_role TEXT
            )
        """)
        # Таблица кланов (SERIAL вместо AUTOINCREMENT)
        self.execute("""
            CREATE TABLE IF NOT EXISTS clans (
                clan_id SERIAL PRIMARY KEY,
                clan_name TEXT UNIQUE,
                owner_id BIGINT,
                balance BIGINT DEFAULT 0,
                members_count INTEGER DEFAULT 1
            )
        """)

    def execute(self, sql, params=()):
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            if sql.strip().upper().startswith("SELECT"):
                return self.cursor.fetchone()
        except Exception as e:
            self.conn.rollback()
            print(f"DB Error: {e}")

    def fetchall(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()
