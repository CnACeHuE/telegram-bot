import psycopg2
import os

class Database:
    def __init__(self):
        # Подключаемся к Postgres на Railway
        self.conn = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
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
        self.conn.commit()

    def execute(self, sql, params=()):
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            # ВОТ ТУТ ИСПРАВЛЕНИЕ: если это SELECT, возвращаем данные
            if sql.strip().upper().startswith("SELECT"):
                return self.cursor.fetchone()
        except Exception as e:
            self.conn.rollback()
            print(f"Ошибка БД: {e}")
            return None

    def fetchall(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()
