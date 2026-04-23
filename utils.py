from config import config
from database import db

def get_mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo(msgs: int) -> str:
    for limit in sorted(config.EVO_STAGES.keys(), reverse=True):
        if msgs >= limit:
            return config.EVO_STAGES[limit]
    return "Странник 🌫"

async def check_access(m, level: int) -> bool:
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,), fetch=True)
    if m.from_user.id == config.OWNER_ID or (res and res[0] >= level):
        return True
    await m.reply("❌ <b>ОТКАЗАНО</b>\nВашего ранга недостаточно.")
    return False
    
