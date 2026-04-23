
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

# --- РАНГИ ---
def get_rank(msgs):
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон 🌱"

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

# --- ПРОФИЛЬ (МИ / Ю*) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    
    # Пытаемся получить данные
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (t_id,))
    
    # Если юзера нет - создаем его
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 0) ON CONFLICT DO NOTHING", (t_id, target.first_name))
        # Сразу запрашиваем еще раз, чтобы получить свежие данные
        u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (t_id,))

    # Теперь данные точно есть
    pwr = u[0] if u else 100
    exp = u[1] if u else 0
    adm = u[2] if u else 0
    
    rank = get_rank(exp)
    status = "БОЖЕСТВО 🔱" if adm >= 3 or t_id == config.OWNER_ID else "Житель"
    
    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(t_id, target.first_name)}\n"
           f"🎖 <b>Эв. статус:</b> <i>{rank}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{exp}</code>\n━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ТОПЫ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def tops(m: types.Message):
    is_pwr = "сильнейшие" in m.text.lower()
    col = "power_points" if is_pwr else "msg_count"
    icon = "💠" if is_pwr else "📜"
    
    users = db.fetchall(f"SELECT user_id, username, {col} FROM users ORDER BY {col} DESC LIMIT 10")
    res = f"🏆 <b>{'СИЛЬНЕЙШИЕ' if is_pwr else 'АКТИВЧИКИ'}:</b>\n\n"
    for i, row in enumerate(users, 1):
        res += f"{i}. {get_mention(row[0], row[1])} — <code>{row[2]}</code> {icon}\n"
    await m.answer(res)

# --- КАРА / ГИВ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'кара')))
async def admin_tools(m: types.Message):
    if m.from_user.id != config.OWNER_ID: return
    if not m.reply_to_message: return
    
    args = m.text.split()
    target = m.reply_to_message.from_user
    
    if args[0].lower() == 'кара':
        amt = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt or 999999, target.id))
        await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} поражен карой!")
    elif args[0].lower() == 'гив':
        amt = int(args[1])
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target.id))
        await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил {amt} 💠")

# --- ЛОТЕРЕЯ (ДЕП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    if not u or u[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[50, 25, 15, 8, 2])[0]
    new_bal = u[0] - bet + (bet * mult)
    db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
    
    msg = "ВЫИГРЫШ" if mult > 1 else "ПРОИГРЫШ"
    await m.answer(f"🎰 <b>{msg} x{mult}</b>\nБаланс: <code>{new_bal}</code> 💠")

# --- СЧЕТЧИК СООБЩЕНИЙ ---
@dp.message_handler(content_types=['text'])
async def global_counter(m: types.Message):
    # Обновляем опыт и имя
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (m.from_user.id, m.from_user.first_name)
    )
    # Если команда клана
    if m.text and m.text.lower().split()[0] in ['клан', 'создать', 'пантеон']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
