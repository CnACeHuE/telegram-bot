import logging, sqlite3, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806  # Твой ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
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
db.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player')")

def check_user(u: types.User):
    name = u.username or u.first_name or "Путник"
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1000: return "Жук 🪲"
    return "Вазон 🪴"

# --- 1. АДМИН-КОМАНДЫ (ПРИОРЕТЕТ) ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.lower().split()[0] in ['гив', 'божество+', 'божество-'])
async def admin_tools(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение цели!")
    target_id = m.reply_to_message.from_user.id
    cmd = m.text.lower().split()[0]
    
    if cmd == 'божество+':
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await m.answer("⚡️ Смертный возведен в ранг **Божества**!")
    elif cmd == 'божество-':
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await m.answer("☁️ Божественные силы покинули этого игрока.")
    elif cmd == 'гив':
        try:
            amt = int(m.text.split()[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target_id))
            await m.answer(f"🔱 В дар получено `{amt}` 💠 силы.")
        except: await m.answer("Формат: `гив 100` (через ответ)")

# --- 2. ИГРОВЫЕ КОМАНДЫ ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Нужно ответить на сообщение получателя!")
    try:
        parts = m.text.split()
        if len(parts) < 2: return
        amt = int(parts[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid or amt <= 0: return
        
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ Недостаточно сил для такого жеста!")
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **ПЕРЕДАЧА:** {m.from_user.first_name} ➔ `{amt}` 💠 ➔ {m.reply_to_message.from_user.first_name}")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        parts = m.text.split()
        bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
        if bal < bet: return await m.reply("❌ Твоя чакра пуста для такой ставки!")
        
        # --- НОВАЯ ЛОГИКА ШАНСОВ ---
        r = random.random()
        if r < 0.01: mult = 10    # 1% шанс
        elif r < 0.04: mult = 5   # 3% шанс
        elif r < 0.10: mult = 3   # 6% шанс
        elif r < 0.35: mult = 2   # 25% шанс
        elif r < 0.55: mult = 1   # 20% шанс (возврат)
        else: mult = 0            # 45% шанс проигрыша
        
        db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, m.from_user.id))
        res_text = {10: "🎰 ОЛИМПИЙСКИЙ КУШ x10!", 5: "💎 ВЕЗЕНИЕ x5!", 3: "✨ МАГИЯ x3!", 2: "✅ УСПЕХ x2", 1: "🌀 ВОЗВРАТ x1", 0: "💀 ПУСТОТА x0"}[mult]
        await m.answer(f"🎰 **ЛОТЕРЕЯ:** {res_text}\nРезультат: `{bet*mult}` 💠")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_invite(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_acc_{uid}_{bet}"))
        await m.answer(f"👊 **ВЫЗОВ!** {m.from_user.first_name} жаждет битвы с {m.reply_to_message.from_user.first_name}!\nСтавка: `{bet}` 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_acc'))
async def pvp_start(c: types.CallbackQuery):
    _, _, challenger_id, bet = c.data.split('_')
    challenger_id, bet = int(challenger_id), int(bet)
    defender_id = c.from_user.id
    if c.from_user.id == challenger_id: return await c.answer("Нельзя биться с самим собой!")
    
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (challenger_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (defender_id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ У кого-то не хватает сил!", show_alert=True)
    
    win = random.choice([challenger_id, defender_id])
    lose = defender_id if win == challenger_id else challenger_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    
    winner = await bot.get_chat_member(c.message.chat.id, win)
    await c.message.edit_text(f"⚔️ **АРЕНА:** В жестоком бою победил **{winner.user.first_name}**! (+{bet} 💠)")

# --- 3. ЛИДЕРБОРДЫ ---

@dp.message_handler(lambda m: m.text and (m.text.lower().startswith('/top') or "сильнейшие" in m.text.lower()))
async def cmd_top_power(m: types.Message):
    users = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 **СИЛЬНЕЙШИЕ БОГИ:**\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {u[0]} — `{u[1]}` 💠\n"
    await m.answer(res, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text and "активчики" in m.text.lower())
async def cmd_top_active(m: types.Message):
    users = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 **САМЫЕ АКТИВНЫЕ:**\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {u[0]} — `{u[1]}` 💬\n"
    await m.answer(res, parse_mode="Markdown")

# --- 4. ПРОФИЛЬ ---

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    await m.answer(f"💠 **ИНФО:** {t.full_name}\n🎖 **Ранг:** `{rank}`\n⚡️ **Мощь:** `{u[0]}`\n💬 **Активность:** `{u[1]}`", parse_mode="Markdown")

# --- 5. СЧЕТЧИК (СТРОГО ПОСЛЕДНИЙ) ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                    
