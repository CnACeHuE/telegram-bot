
import os
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
    OWNER_ID: int = int(os.getenv("OWNER_ID", "123456789"))
    
    # Ранги и эволюция
    RANKS: Dict[int, Tuple[str, str]] = {
        0: ("Вазон", "🌱"),
        1: ("Росток", "🌿"),
        2: ("Цветок", "🌸"),
        3: ("Древо", "🌳"),
        4: ("Титан", "⚡"),
        5: ("Божество", "🔱")
    }
    
    EXPERIENCE_PER_RANK: int = 100
    BASE_MULTIPLIERS: Dict[int, float] = {0: 0.0, 1: 1.0, 2: 2.0, 5: 5.0, 10: 10.0}
    
    # Экономика
    STARTING_POWER: int = 100
    MAX_ACTIVE_USERS_FOR_PING: int = 50
    
    # База данных
    DB_NAME: str = os.getenv("DB_NAME", "abode_of_gods")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))

config = Config()
