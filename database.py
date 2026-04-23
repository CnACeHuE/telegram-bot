import psycopg2
from config import config

class Database:
    def __init__(self):
        # sslmode='require' необходим для Railway
        self.conn = psycopg2.connect(config.DB_URL, sslmode='require')
        self.conn.autocommit = True

    def execute(self, query: str, params: tuple = None, fetch: bool = False):
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchone()
            return cur.rowcount

    def fetchall(self, query: str, params: tuple = None):
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def register_user(self, uid: int, name: str):
        return self.execute(
            "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 0) "
            "ON CONFLICT (user_id) DO UPDATE SET username = %s "
            "RETURNING power_points, msg_count, admin_rank, clan_id, clan_role",
            (uid, name, name), fetch=True
        )

db = Database()
