import logging, sqlite3, os, random, time
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
OWNER_ID = 7361338806 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

# Глобальные настройки прав
cmd_perms = {"кара": 3, "гив": 3, "эволюция": 100, ".пд": 100}

# --- БАЗА ДАННЫХ ---
class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None and "postgresql" in DATABASE_URL
        self.connect()
    def connect(self):
        if self.is_pg:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else:
            self.conn = sqlite3.connect("abode_gods.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player', admin_rank INTEGER DEFAULT 0, loss_streak INTEGER DEFAULT 0, spins_since_win INTEGER DEFAULT 0)")
        try: self.execute("ALTER TABLE users ADD COLUMN admin_rank INTEGER DEFAULT 0")
        except: pass
    def execute(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        try:
            self.cursor.execute(sql, params)
            if "SELECT" in sql.upper(): return self.cursor.fetchone()
            self.conn.commit()
        except: self.connect(); return self.execute(sql, params)
    def fetchall(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()

def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def get_rank_name(lvl):
    return {0: "Обычный", 1: "Младший админ", 2: "Средний админ", 3: "Старший админ", 100: "Создатель"}.get(lvl, "Неизвестно")

def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон"

# --- 1. АДМИН-КОМАНДЫ И ЭВОЛЮЦИЯ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'эволюция', 'гив', 'кара', 'деэволюция')))
async def admin_tools(m: types.Message):
    u_rank = 100 if m.from_user.id == OWNER_ID else (db.execute("SELECT admin_rank FROM users WHERE user_id = ?", (m.from_user.id,)) or (0,))[0]
    args = m.text.lower().split(); cmd = args[0]
    
    if u_rank < cmd_perms.get(cmd, 3): return await m.reply(f"⚠️ Нужен статус эв. {cmd_perms.get(cmd, 3)}+")

    if cmd == '.пд' and len(args) == 3:
        cmd_perms[args[1]] = int(args[2])
        return await m.answer(f"✅ Доступ к <b>{args[1]}</b> изменен на {args[2]} уровень.")

    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(target)

    if cmd == 'эволюция' and m.reply_to_message:
        lvl = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        db.execute("UPDATE users SET admin_rank = ? WHERE user_id = ?", (min(lvl, 3), target.id))
        await m.answer(f"🌟 Герой {get_mention(target.id, target.first_name)} эволюционировал в <b>{get_rank_name(lvl)}</b> ✨")
    
    elif cmd == 'деэволюция':
        if target.id == OWNER_ID: return
        db.execute("UPDATE users SET admin_rank = 0 WHERE user_id = ?", (target.id, ))
        await m.answer(f"☁️ {target.first_name} потерял статус эволюции.")

    elif cmd == 'кара' and m.reply_to_message:
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID: return await m.answer("🛡")
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        if amt: db.execute("UPDATE users SET power_points = MAX(0, power_points - ?) WHERE user_id = ?", (amt, target.id))
        else: db.execute("UPDATE users SET power_points = 0 WHERE user_id = ?", (target.id,))
        await m.answer(f"🔥 Казнь совершена.")

    elif cmd == 'гив' and m.reply_to_message:
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
        await m.answer(f"🔱 +{amt} мощи.")

# --- 2. ЛОТЕРЕЯ (БЕЗ ИЗМЕНЕНИЙ ОФОРМЛЕНИЯ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        if bet < 1 or bet > 500: return await m.reply("⚠️ Ставки 1-500")
        data = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if data[0] < bet: return await m.reply("❌ Мало мощи")
        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        if data[1] >= 3: w[0] -= 15; w[2] += 15
        res_m = 0; curr = 0; rand = random.uniform(0, sum(w.values()))
        for m_v, weight in w.items():
            curr += weight
            if rand <= curr: res_m = m_v; break
        new_bal = data[0] + (bet * res_m) - bet
        db.execute("UPDATE users SET power_points = ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", (new_bal, (data[1]+1 if res_m==0 else 0), (data[2]+1 if res_m<=1 else 0), m.from_user.id))
        icon = "🔴" if res_m == 0 else "🟡" if res_m == 1 else "🟢" if res_m < 100 else "💰"
        await m.answer(f"{icon} <b>{'ПРОИГРЫШ' if res_m==0 else 'ВЫИГРЫШ'} x{res_m}</b>\n━━━━━━━━━━━━━━\n💸 Ставка: <code>{bet}</code>\n💎 Итог: <code>{bet*res_m}</code>\n💰 Баланс: <code>{new_bal}</code> 💠")
    except: pass

# --- 3. ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
        if b1 < bet or b2 < bet: return await m.reply("❌ Недостаточно мощи у одного из бойцов!")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ", callback_data=f"pvp_{uid}_{bet}"))
        await m.answer(f"⚔️ {m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name}!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_call(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    b1 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (ch_id,)) or (0,))[0]
    b2 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,)) or (0,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ Бой отменен", show_alert=True)
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    await c.message.edit_text(f"🏆 Победил <b>{(await bot.get_chat_member(c.message.chat.id, win)).user.first_name}</b>! (+{bet} 💠)")

# --- 4. МИ, ТОПЫ, ПЕРЕДАЧА ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = ?", (t.id,))
    await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n🎖 <b>Статус эв.:</b> <i>{get_rank_name(u[2])}</i>\n⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n📜 <b>Ранг:</b> <code>{get_rank(u[1])}</code>\n━━━━━━━━━━━━━━")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('сильнейшие', 'активчики')))
async def tops(m: types.Message):
    sort_col = "power_points" if "сильнейшие" in m.text.lower() else "msg_count"
    users = db.fetchall(f"SELECT user_id, username, {sort_col} FROM users ORDER BY {sort_col} DESC LIMIT 10")
    res = f"🏆 <b>ТОП {sort_col.upper()}:</b>\n\n"
    for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code>\n"
    await m.answer(res)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal >= amt > 0:
            db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
            await m.answer(f"🤝 Передано {amt} 💠")
    except: pass

@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
