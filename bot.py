import logging, sqlite3, os, random, time
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
OWNER_ID = 7361338806 # ID Создателя

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

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

# --- 1. АДМИН-ЛОГИКА (ДЛЯ ВСЕХ БОЖЕСТВ) ---
async def is_admin(user_id):
    if user_id == OWNER_ID: return True
    res = db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    return res and res[0] == 'admin'

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'божество+', 'божество-')))
async def admin_tools(m: types.Message):
    if not await is_admin(m.from_user.id): return
    if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
    
    args = m.text.lower().split()
    cmd = args[0]
    target = m.reply_to_message.from_user
    
    if cmd == 'божество+':
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target.id,))
        await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} возведен в ранг <b>Божества</b>!")
    elif cmd == 'божество-':
        if target.id == OWNER_ID: return # Нельзя снять роль с создателя
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target.id,))
        await m.answer(f"☁️ {get_mention(target.id, target.first_name)} низвергнут до игрока.")
    elif cmd == 'гив':
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил <code>{amt}</code> 💠 силы.")
        except: pass

# --- 2. ПЕРЕДАЧА СИЛЫ (*передать) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение получателя!</b>")
    try:
        parts = m.text.split()
        if len(parts) < 2: return
        amt = int(parts[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid or amt <= 0: return

        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("<b>❌ Недостаточно сил!</b>")

        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 {get_mention(uid, m.from_user.first_name)} передал <code>{amt}</code> 💠 {get_mention(tid, m.reply_to_message.from_user.first_name)}")
    except: pass

# --- 3. ТОПЫ (КЛИКАБЕЛЬНЫЕ) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith('/top') or "сильнейшие" in m.text.lower()))
async def top_power(m: types.Message):
    users = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 <b>СИЛЬНЕЙШИЕ БОГИ:</b>\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 💠\n"
    await m.answer(res)

@dp.message_handler(lambda m: m.text and "активчики" in m.text.lower())
async def top_active(m: types.Message):
    users = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 <b>АКТИВЧИКИ ОБИТЕЛИ:</b>\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 💬\n"
    await m.answer(res)

# --- 4. ЛОТЕРЕЯ (БЕЗ ИЗМЕНЕНИЙ В ЛОГИКЕ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        if bet < 1 or bet > 500: return await m.reply("<b>⚠️ Ставки от 1 до 500!</b>")
        data = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if data[0] < bet: return await m.reply("<b>❌ Мало энергии.</b>")
        
        # Упрощенный весовой рандом
        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        if data[1] >= 3: w[0] -= 15; w[2] += 15
        if data[2] >= 5: w[0] = 0; w[2] += 20
        
        total_w = sum(w.values()); rand = random.uniform(0, total_w)
        curr, mult = 0, 0
        for m_val, weight in w.items():
            curr += weight
            if rand <= curr: mult = m_val; break
            
        profit = (bet * mult) - bet
        db.execute("UPDATE users SET power_points = power_points + ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (profit, (data[1]+1 if mult==0 else 0), (data[2]+1 if mult<=1 else 0), m.from_user.id))
        
        icon = {100: "🔱", 5: "💎", 4: "🔥", 3: "✨", 2: "✅", 1: "🌀", 0: "💀"}.get(mult)
        await m.answer(f"{icon} <b>ЛОТЕРЕЯ</b>\nМножитель: <b>x{mult}</b>\nБаланс: <code>{data[0] + profit}</code> 💠")
    except: pass

# --- 5. ПРОФИЛЬ "МИ" ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    role = "БОЖЕСТВО 🔱" if u[2] == 'admin' else "ИГРОК 🪴"
    
    ui = (
        f"✨ <b>СВИТОК БОЖЕСТВА</b> ✨\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{role}</i>\n"
        f"⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n"
        f"💬 <b>Опыт:</b> <code>{u[1]}</code> 📜\n"
        f"━━━━━━━━━━━━━━"
    )
    await m.answer(ui)

# --- 6. ПВП И СЧЕТЧИК ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return
    bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
    check_user(m.from_user); check_user(m.reply_to_message.from_user)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_call(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_')
    ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (ch_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ Мало сил!", show_alert=True)
    win = random.choice([ch_id, c.from_user.id])
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, (c.from_user.id if win==ch_id else ch_id)))
    w_name = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"🏆 В битве победил <b>{w_name}</b>! (+{bet} 💠)")

@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
