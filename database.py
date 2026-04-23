import logging
from typing import Optional, List, Dict, Any
import psycopg2
import psycopg2.extras
from config import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT
        )
        self.conn.autocommit = False
        psycopg2.extras.register_default_jsonb(globally=True)
    
    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Any:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall() if cur.description else None
            self.conn.commit()
            return cur.rowcount
    
    def execute_returning(self, query: str, params: tuple = None) -> Optional[Dict]:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            self.conn.commit()
            return cur.fetchone()
    
    # Пользователи
    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.execute(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,),
            fetch=True
        )[0] if self.execute("SELECT id FROM users WHERE user_id = %s", (user_id,), fetch=True) else None
    
    def register_user(self, user_id: int, username: str) -> Dict:
        return self.execute_returning(
            "INSERT INTO users (user_id, username, power, experience, rank_level) "
            "VALUES (%s, %s, %s, 0, 0) "
            "ON CONFLICT (user_id) DO UPDATE SET username = %s "
            "RETURNING *",
            (user_id, username, config.STARTING_POWER, username)
        )
    
    def add_experience(self, user_id: int, amount: int = 1) -> Optional[Dict]:
        """Добавляет опыт и обновляет ранг при необходимости"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        new_exp = user['experience'] + amount
        new_rank = min(config.RANKS.keys(), key=lambda x: abs(x - (new_exp // config.EXPERIENCE_PER_RANK)))
        
        return self.execute_returning(
            "UPDATE users SET experience = %s, rank_level = %s WHERE user_id = %s RETURNING *",
            (new_exp, new_rank, user_id)
        )
    
    def get_balance(self, user_id: int) -> int:
        user = self.get_user(user_id)
        return user['power'] if user else 0
    
    def transfer_power(self, from_id: int, to_id: int, amount: int) -> bool:
        """Безопасный перевод мощи с проверкой баланса"""
        with self.conn.cursor() as cur:
            try:
                cur.execute("BEGIN")
                cur.execute("SELECT power FROM users WHERE user_id = %s FOR UPDATE", (from_id,))
                from_balance = cur.fetchone()
                if not from_balance or from_balance[0] < amount:
                    cur.execute("ROLLBACK")
                    return False
                
                cur.execute("UPDATE users SET power = power - %s WHERE user_id = %s", (amount, from_id))
                cur.execute("UPDATE users SET power = power + %s WHERE user_id = %s", (amount, to_id))
                self.conn.commit()
                return True
            except Exception as e:
                cur.execute("ROLLBACK")
                logger.error(f"Transfer error: {e}")
                return False
    
    # Кланы
    def create_clan(self, leader_id: int, clan_name: str) -> Optional[Dict]:
        return self.execute_returning(
            "INSERT INTO clans (name, leader_id, members_count) "
            "VALUES (%s, %s, 1) RETURNING clan_id",
            (clan_name, leader_id)
        )
    
    def get_clan(self, clan_id: int) -> Optional[Dict]:
        return self.execute("SELECT * FROM clans WHERE clan_id = %s", (clan_id,), fetch=True)[0]
    
    def set_user_clan(self, user_id: int, clan_id: int) -> None:
        self.execute("UPDATE users SET clan_id = %s WHERE user_id = %s", (clan_id, user_id))
    
    def get_active_users(self, limit: int = 50) -> List[Dict]:
        return self.execute(
            "SELECT user_id, username FROM users WHERE is_active = TRUE LIMIT %s",
            (limit,),
            fetch=True
        )

db = Database()
