import config
from database import db

def get_mention(uid, name):
    """Создает кликабельную ссылку на пользователя (HTML)"""
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo(msgs):
    """Считает статус на основе количества сообщений"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

async def check_access(m, req_lvl):
    """Проверяет ранг. Владелец всегда имеет доступ 999."""
    if int(m.from_user.id) == int(config.OWNER_ID): return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    current = res[0] if res else 0
    return current >= req_lvl
  
