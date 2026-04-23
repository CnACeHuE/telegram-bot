
from typing import Optional, Dict, List
import random
from config import config

def mention_html(user_id: int, username: str) -> str:
    """Создает кликабельное HTML-упоминание пользователя"""
    name = username or f"user{user_id}"
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def get_rank_info(rank_level: int) -> tuple:
    """Возвращает название и эмодзи ранга"""
    rank = config.RANKS.get(rank_level, config.RANKS[0])
    return rank[0], rank[1]

def format_profile(user_data: Dict) -> str:
    """Форматирует карточку профиля"""
    name, emoji = get_rank_info(user_data['rank_level'])
    mention = mention_html(user_data['user_id'], user_data['username'])
    
    clan_text = "Нет клана"
    if user_data.get('clan_name'):
        clan_text = f"🏛 {user_data['clan_name']}"
    
    return (
        f"━━━━━━━━━━━━━━\n"
        f"👤 {mention}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔱 Статус: {emoji} {name}\n"
        f"⚡ Мощь: {user_data['power']}\n"
        f"📊 Опыт: {user_data['experience']}\n"
        f"🏆 Ранг: {user_data['rank_level']} уровень\n"
        f"{clan_text}\n"
        f"━━━━━━━━━━━━━━"
    )

def lottery_result() -> tuple:
    """Генерирует случайный множитель для лотереи"""
    multiplier = random.choice(list(config.BASE_MULTIPLIERS.keys()))
    return multiplier, config.BASE_MULTIPLIERS[multiplier]

def is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_ID

def validate_pvp_bet(bet: int, attacker_balance: int, defender_balance: int) -> Optional[str]:
    """Проверяет возможность проведения PvP"""
    if bet <= 0:
        return "Ставка должна быть положительной"
    if bet > attacker_balance:
        return f"Недостаточно мощи! Ваш баланс: {attacker_balance}"
    if bet > defender_balance:
        return f"У противника недостаточно мощи! Баланс противника: {defender_balance}"
    return None
