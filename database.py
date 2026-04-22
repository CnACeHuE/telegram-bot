import psycopg2
import os
import logging

class Database:
    def __init__(self):
        # Берем URL базы из переменных Railway
        db_url = os.getenv('DATABASE_URL')
        self.conn = psycopg2.connect(db_url)
        self.conn.autocommit = True
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # В PostgreSQL вместо AUTOINCREMENT используем SERIAL
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                power_points INTEGER DEFAULT 0,
                msg_count INTEGER DEFAULT 0,
                clan_id INTEGER,
                clan_role TEXT DEFAULT 'Участник'
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clans (
                clan_id SERIAL PRIMARY KEY,
                clan_name TEXT UNIQUE,
                owner_id BIGINT,
                members_count INTEGER DEFAULT 1
            )
        """)

    def execute(self, sql, params=()):
        # В PostgreSQL используется %s вместо ?
        sql = sql.replace('?', '%s')
        self.cursor.execute(sql, params)
        if self.cursor.description:
            return self.cursor.fetchone()
        return None

db = Database()
