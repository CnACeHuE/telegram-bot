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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (user_id,))
    return res and res[0] >= 3

# --- КОМАНДА ПОМОЩИ (ХЕЛП) ---
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

# --- ПРОФИЛЬ (МИ / Ю*) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    
    # Запрос данных (индексы: 0-мощь, 1-опыт, 2-ранг, 3-клан)
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 0)", (target.id, target.first_name, 100, 0))
        u = (100, 0, 0, "Нет")

    power, experience, admin_lvl, clan_status = u[0], u[1], u[2], (u[3] if u[3] else "Нет")
    rank = get_rank(experience)
    adm_status = "БОЖЕСТВО 🔱" if admin_lvl >= 3 or target.id == config.OWNER_ID else "Житель"
    
    ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
          f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
          f"🎖 <b>Эв. статус:</b> <i>{rank}</i>\n"
          f"🔱 <b>Ранг:</b> {adm_status}\n"
          f"⚡️ <b>Мощь:</b> <code>{power}</code> 💠\n"
          f"📜 <b>Опыт:</b> <code>{experience}</code>\n━━━━━━━━━━━━━━")
    await m.answer(ui)

# --- ТОПЫ (СИЛЬНЕЙШИЕ / АКТИВЧИКИ) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def tops(m: types.Message):
    is_power = "сильнейшие" in m.text.lower()
    order_col = "power_points" if is_power else "msg_count"
    icon = "💠" if is_power else "📜"
    
    users = db.fetchall(f"SELECT user_id, username, {order_col} FROM users ORDER BY {order_col} DESC LIMIT 10")
    res = f"🏆 <b>{'СИЛЬНЕЙШИЕ БОГИ' if is_power else 'АКТИВЧИКИ'}:</b>\n\n"
    for i, row in enumerate(users, 1):
        res += f"{i}. {get_mention(row[0], row[1])} — <code>{row[2]}</code> {icon}\n"
    await m.answer(res)

# --- АДМИН-ИНСТРУМЕНТЫ (КАРА / ГИВ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'кара')))
async def admin_tools(m: types.Message):
    if not await is_admin(m.from_user.id): return
    if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
    
    args = m.text.split()
    target = m.reply_to_message.from_user
    
    if args[0].lower() == 'кара':
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        if target.id == config.OWNER_ID: return await m.answer("🛡 Кара бессильна против Создателя.")
        
        if amt > 0:
            db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt, target.id))
            await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
        else:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target.id,))
            await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b> Мощь {get_mention(target.id, target.first_name)} обнулена.")
            
    elif args[0].lower() == 'гив':
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил <code>{amt}</code> 💠")
        except: pass

# --- ИГРОВЫЕ КОМАНДЫ (ДЕП / ПВП / ПЕРЕДАТЬ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    try:
        args = m.text.split()
        bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
        u_bal = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        
        if u_bal < bet: return await m.reply("❌ Недостаточно мощи!")
        
        w = {0: 50, 1: 20, 2: 15, 3: 8, 5: 5, 10: 1.98, 100: 0.02}
        mult = random.choices(list(w.keys()), weights=list(w.values()))[0]
        win_amt = bet * mult
        new_bal = u_bal - bet + win_amt
        db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
        
        icon = {100: "💰", 10: "👑", 5: "🟢", 3: "🟢", 2: "🟢", 1: "🟡", 0: "🔴"}.get(mult)
        status = "ДЖЕКПОТ" if mult == 100 else "ВЫИГРЫШ" if mult > 1 else "ПРОИГРЫШ"
        await m.answer(f"{icon} <b>{status} x{mult}</b>\n━━━━━━━━━━━━━━\n💸 Ставка: <code>{bet}</code>\n💎 Получено: <code>{win_amt}</code>\n💰 Баланс: <code>{new_bal}</code> 💠")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if amt <= 0 or uid == tid: return
        u_bal = db.execute("SELECT power_points FROM users WHERE user_id = %s", (uid,))[0]
        if u_bal >= amt:
            db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (amt, uid))
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, tid))
            await m.answer(f"🤝 {get_mention(uid, m.from_user.first_name)} ➡ <code>{amt}</code> 💠 ➡ {get_mention(tid, m.reply_to_message.from_user.first_name)}")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))[0]
        if p1 < bet or p2 < bet: return await m.reply("❌ Недостаточно мощи!")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} бросает вызов!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_call(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (ch_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ Бой отменен: нехватка💠", show_alert=True)
    
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, lose))
    w_name = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"🏆 В битве победил <b>{w_name}</b>!\n💰 Выигрыш: <code>{bet}</code> 💠")

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК (ОПЫТ + КЛАНЫ) ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Учет сообщения
    name = m.from_user.first_name.replace("<", "").replace(">", "")
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = %s",
        (m.from_user.id, name, name)
    )
    # Кланы
    if m.text and m.text.lower().split()[0] in ['клан', 'пантеон', 'создать']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
