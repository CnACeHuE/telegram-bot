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

# --- 1. АДМИН-ЛОГИКА ---
async def is_admin(user_id):
    if user_id == OWNER_ID: return True
    res = db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    return res and res[0] == 'admin'

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'божество+', 'божество-', 'кара')))
async def admin_tools(m: types.Message):
    if not await is_admin(m.from_user.id): return
    
    args = m.text.lower().split()
    cmd = args[0]
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    
    if cmd == 'божество+':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target.id,))
        await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} возведен в ранг <b>Божества</b>!")
    
    elif cmd == 'божество-':
        # Запрет только если КТО-ТО ДРУГОЙ пытается снять роль с Создателя
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID:
            return await m.answer("🪐 Лишь сам Создатель властен над своей судьбой.")
        
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target.id,))
        await m.answer(f"☁️ {get_mention(target.id, target.first_name)} теперь в ранге игрока.")
    
    elif cmd == 'кара':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение грешника!</b>")
        if target.id == OWNER_ID: return await m.answer("🛡 Кара бессильна против Создателя.")
        
        try:
            amt = int(args[1]) if len(args) > 1 else None
            if amt is not None:
                db.execute("UPDATE users SET power_points = MAX(0, power_points - ?) WHERE user_id = ?", (amt, target.id))
                await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
            else:
                db.execute("UPDATE users SET power_points = 0 WHERE user_id = ?", (target.id,))
                await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b> Мощь {get_mention(target.id, target.first_name)} обнулена.")
        except: pass
        
    elif cmd == 'гив':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил <code>{amt}</code> 💠 мощи.")
        except: pass

# --- 2. ЛОТЕРЕЯ (БЕЗ ИЗМЕНЕНИЙ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        if bet < 1 or bet > 500: return await m.reply("<b>⚠️ Ставки от 1 до 500!</b>")
        data = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if data[0] < bet: return await m.reply("<b>❌ Недостаточно мощи для ставки!</b>")
        
        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        if data[1] >= 3: w[0] -= 15; w[2] += 15
        if data[2] >= 5: w[0] = 0; w[2] += 20
        
        total_w = sum(w.values()); rand = random.uniform(0, total_w)
        curr, mult = 0, 0
        for m_val, weight in w.items():
            curr += weight
            if rand <= curr: mult = m_val; break
            
        win_amt = bet * mult
        profit = win_amt - bet
        new_balance = data[0] + profit
        db.execute("UPDATE users SET power_points = ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (new_balance, (data[1]+1 if mult==0 else 0), (data[2]+1 if mult<=1 else 0), m.from_user.id))
        
        icon = {100: "💰", 5: "🟢", 4: "🟢", 3: "🟢", 2: "🟢", 1: "🟡", 0: "🔴"}.get(mult if mult <= 5 else 5 if mult < 100 else 100)
        status = "ДЖЕКПОТ" if mult == 100 else "ВЫИГРЫШ" if mult > 1 else "ПРИ СВОИХ" if mult == 1 else "ПРОИГРЫШ"

        res = (f"{icon} <b>{status} x{mult}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"💸 Ставка: <code>{bet}</code>\n"
               f"💎 Получено: <code>{win_amt}</code>\n"
               f"💰 Баланс: <code>{new_balance}</code> 💠")
        await m.answer(res)
    except: pass

# --- 3. ТОПЫ И ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    role = "БОЖЕСТВО 🔱" if u[2] == 'admin' else get_rank(u[1])
    
    ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
          f"👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n"
          f"🎖 <b>Ранг:</b> <i>{role}</i>\n"
          f"⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n"
          f"📜 <b>Опыт:</b> <code>{u[1]}</code> сообщений\n━━━━━━━━━━━━━━")
    await m.answer(ui)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('сильнейшие', '/top')))
async def top_power(m: types.Message):
    users = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 <b>СИЛЬНЕЙШИЕ БОГИ:</b>\n\n"
    for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 💠\n"
    await m.answer(res)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('активчики'))
async def top_active(m: types.Message):
    users = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 <b>АКТИВЧИКИ ОБИТЕЛИ:</b>\n\n"
    for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 📜\n"
    await m.answer(res)

# --- 4. ПЕРЕДАЧА И ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1]); uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid or amt <= 0: return
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("<b>❌ Недостаточно мощи!</b>")
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 {get_mention(uid, m.from_user.first_name)} передал <code>{amt}</code> 💠 {get_mention(tid, m.reply_to_message.from_user.first_name)}")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return
    bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} бросает вызов!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_call(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (ch_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ Недостаточно мощи!", show_alert=True)
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    w_n = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"🏆 В битве победил <b>{w_n}</b>! (+{bet} 💠)")

@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
