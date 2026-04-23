import logging, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- УТИЛИТЫ ---
def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон 🌱"

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

async def is_admin(user_id):
    if user_id == config.OWNER_ID: return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (int(user_id),))
    return res and res[0] >= 3

# --- ХЕЛП ---
HELP_TEXT = """📖 <b>БИБЛИОТЕКА</b>
━━━━━━━━━━━━━━
🎮 <b>Игры:</b>
— лотерея / пвп / *передать
— ми / профиль / ю*

🛠 <b>Админ:</b>
— сильнейшие / активчики
— кара [реплей] / гив [реплей]

👑 <b>Создатель:</b>
— эволюция / .пд / .сбор
━━━━━━━━━━━━━━"""

@dp.message_handler(commands=['help'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'хелп')
async def send_help(m: types.Message):
    await m.answer(HELP_TEXT)

# --- ИСПРАВЛЕННЫЙ ПРОФИЛЬ (СИНХРОНИЗАЦИЯ) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    
    # Пытаемся получить данные
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (t_id,))
    
    if not u:
        # Если нет в базе - создаем и запрашиваем ЗАНОВО
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 0) ON CONFLICT DO NOTHING", (t_id, target.first_name))
        u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (t_id,))
    
    # Теперь берем данные только из того, что вернула база
    power = u[0] if u else 100
    exp = u[1] if u else 0
    admin_lvl = u[2] if u else 0
    
    rank = get_rank(exp)
    adm_status = "БОЖЕСТВО 🔱" if admin_lvl >= 3 or t_id == config.OWNER_ID else "Житель"
    
    ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
          f"👤 <b>Имя:</b> {get_mention(t_id, target.first_name)}\n"
          f"🎖 <b>Эв. статус:</b> <i>{rank}</i>\n"
          f"🔱 <b>Ранг:</b> {adm_status}\n"
          f"⚡️ <b>Мощь:</b> <code>{power}</code> 💠\n"
          f"📜 <b>Опыт:</b> <code>{exp}</code>\n━━━━━━━━━━━━━━")
    await m.answer(ui)

# --- ТОПЫ (БЕЗ ИЗМЕНЕНИЙ) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def tops(m: types.Message):
    is_power = "сильнейшие" in m.text.lower()
    col = "power_points" if is_power else "msg_count"
    icon = "💠" if is_power else "📜"
    
    users = db.fetchall(f"SELECT user_id, username, {col} FROM users ORDER BY {col} DESC LIMIT 10")
    res = f"🏆 <b>{'СИЛЬНЕЙШИЕ БОГИ' if is_power else 'АКТИВЧИКИ'}:</b>\n\n"
    for i, row in enumerate(users, 1):
        res += f"{i}. {get_mention(row[0], row[1])} — <code>{row[2]}</code> {icon}\n"
    await m.answer(res)

# --- ИСПРАВЛЕННЫЙ СЧЕТЧИК СООБЩЕНИЙ ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    u_id = int(m.from_user.id)
    name = m.from_user.first_name.replace("<", "").replace(">", "")
    
    # Прибавляем +1 к msg_count, если юзер уже есть
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (u_id, name)
    )
    
    if m.text and m.text.lower().split()[0] in ['клан', 'пантеон', 'создать']:
        await clan_router(m)
    
    # Обработка игровых команд (лотерея, пвп и т.д.)
    txt = m.text.lower()
    if txt.startswith(('лотерея', 'деп')): await cmd_loto(m)
    elif txt.startswith('пвп'): await pvp_start(m)
    elif txt.startswith('*передать'): await transfer(m)
    elif txt.startswith(('гив', 'кара')): await admin_tools(m)

# --- ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ (loto, pvp, admin_tools) ОСТАЮТСЯ ТАКИМИ ЖЕ ---
# ... (вставь сюда функции loto, transfer, pvp_start, pvp_call и admin_tools из прошлого сообщения) ...

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
