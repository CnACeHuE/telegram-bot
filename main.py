import logging, random, asyncio
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
def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo_status(msgs):
    """Определяет статус эволюции по количеству сообщений"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit:
            return title
    return "Вазон 🌱"

# --- ПРОФИЛЬ (МИ / Ю*) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (t_id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0) ON CONFLICT DO NOTHING", (t_id, target.first_name))
        u = (100, 0, 0)

    pwr, exp, adm_lvl = u[0], u[1], u[2]
    
    # Логика отображения ранга
    if t_id == int(config.OWNER_ID):
        status = "БОЖЕСТВО 🔱"
    else:
        status = config.ADM_RANKS.get(adm_lvl, "Участник")
    
    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n"
           f"━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(t_id, target.first_name)}\n"
           f"🎖 <b>Эв. статус:</b> <i>{get_evo_status(exp)}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{exp}</code>\n"
           f"━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ЛОТЕРЕЯ (ДЕП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    u = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    if not u or u[0] < bet: 
        return await m.reply("❌ Недостаточно мощи!")
    
    # Шансы: Проигрыш (55%), X1 (25%), X2 (12%), X5 (6%), X10 (2%)
    mult = random.choices([0, 1, 2, 5, 10], weights=[55, 25, 12, 6, 2])[0]
    win_sum = bet * mult
    new_bal = u[0] - bet + win_sum
    db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
    
    if mult == 0: color = "🔴 ПРОИГРЫШ"
    elif mult == 1: color = "🟡 ПРИ СВОИХ x1"
    else: color = f"🟢 ВЫИГРЫШ x{mult}"
    
    res = (f"{color}\n"
           f"━━━━━━━━━━━━━━\n"
           f"💸 Ставка: {bet}\n"
           f"💎 Получено: {win_sum}\n"
           f"💰 Баланс: {new_bal} 💠")
    await m.answer(res)

# --- АДМИН-КОМАНДЫ (.ПД, ЭВОЛЮЦИЯ, ГИВ, КАРА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'эволюция', 'гив', 'кара')))
async def admin_tools(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    
    args = m.text.split()
    cmd = args[0].lower()
    target = m.reply_to_message.from_user
    
    try:
        if cmd in ['.пд', 'эволюция']:
            val = int(args[1])
            db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
            name = config.ADM_RANKS.get(val, f"Уровень {val}")
            await m.answer(f"🧬 Статус {get_mention(target.id, target.first_name)} изменен на: <b>{name}</b>")
            
        elif cmd == 'кара':
            amt = int(args[1]) if len(args) > 1 else 999999
            db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt, target.id))
            await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} поражен карой!")
            
        elif cmd == 'гив':
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил {amt} 💠")
    except: await m.reply("⚠️ Ошибка в формате команды!")

# --- .СБОР ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.сбор'))
async def mass_summon(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    
    args = m.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Обитель вызывает всех своих жителей!"
    
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 ORDER BY msg_count DESC LIMIT 50")
    mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
    
    res = (f"🔔 <b>ОБЩИЙ СБОР!</b>\n"
           f"━━━━━━━━━━━━━━\n"
           f"👤 {get_mention(m.from_user.id, m.from_user.first_name)}\n"
           f"📢 Объявил: {reason}\n"
           f"━━━━━━━━━━━━━━{mentions}")
    await m.answer(res)

# --- СЧЕТЧИК И РОУТЕР КЛАНОВ ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (m.from_user.id, m.from_user.first_name)
    )
    
    first_word = m.text.lower().split()[0] if m.text else ""
    if first_word in ['клан', 'пантеон', 'создать']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
            
