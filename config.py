import os
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class Config:
    API_TOKEN: str = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН")
    OWNER_ID: int = int(os.getenv("OWNER_ID", "123456789"))
    DB_URL: str = os.getenv("DATABASE_URL")
    
    # Использование default_factory исправляет ошибку со скриншота
    ADM_RANKS: Dict[int, str] = field(default_factory=lambda: {
        0: "Участник",
        1: "Модератор",
        2: "Советник",
        3: "Архангел"
    })

    EVO_STAGES: Dict[int, str] = field(default_factory=lambda: {
        0: "Вазон 🌱",
        100: "Росток 🌿",
        500: "Цветок 🌸",
        2000: "Древо 🌳",
        10000: "Титан ⚡"
    })
    
    LOTTERY_WEIGHTS: list = field(default_factory=lambda: [58, 22, 12, 6, 2])
    LOTTERY_MULTIS: list = field(default_factory=lambda: [0, 1, 2, 5, 10])

config = Config()
