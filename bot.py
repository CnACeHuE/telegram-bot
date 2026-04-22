import logging, sqlite3, os, random, time
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 

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
        except Exception as e: 
            logging.error(f"DB Error: {e}")
            self.connect()
            return self.execute(sql, params)
    def fetchall(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()

# Инициализация структуры
def init_db():
    # Создаем основную таблицу
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 100, 
        msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player',
        loss_streak INTEGER DEFAULT 0, spins_since_win INTEGER DEFAULT 0)""")
    # Проверка и добавление недостающих колонок (для миграции)
    try:
        db.execute("ALTER TABLE users ADD COLUMN loss_streak INTEGER DEFAULT 0")
        db.execute("ALTER TABLE users ADD COLUMN spins_since_win INTEGER DEFAULT 0")
    except: pass
    db.execute("CREATE TABLE IF NOT EXISTS lotto_logs (user_id BIGINT, profit INTEGER, timestamp REAL)")

init_db()

def check_user(u: types.User):
    name = f"@{u.username}" if u.username else u.first_name
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

def get_rank(msgs):
    if msgs >= 10000: return "Лорд Обители 👑"
    if msgs >= 5000: return "Верховный Бог ⚡️"
    if msgs >= 1000: return "Младшее Божество ✨"
    return "Смертный Путник 🪴"

# --- 1. АДМИН-КОМАНДЫ ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.lower().split()[0] in ['гив', 'божество+', 'божество-'])
async def admin_tools(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение цели!")
    cmd = m.text.lower().split()[0]
    target_id = m.reply_to_message.from_user.id
    
    if cmd == 'божество+':
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await m.answer("🟢 Смертный возведен в ранг **Божества**!")
    elif cmd == 'божество-':
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await m.answer("🔴 Ранг Божества аннулирован.")
    elif cmd == 'гив':
        try:
            amt = int(m.text.split()[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target_id))
            await m.answer(f"🔱 В дар ниспослано `{amt}` 💠 силы.")
        except: pass

# --- 2. ЛОГИКА ЛОТЕРЕИ (SMART SOUL) ---
BASE_WEIGHTS = {0: 45, 1: 35, 2: 13, 3: 5, 4: 1.5, 5: 0.5, 100: 0.02}

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        parts = m.text.split()
        bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        if bet < 1 or bet > 500: return await m.reply("⚠️ Ставки: от `1` до `500` 💠")

        u = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        balance, loss_s, spins_s = u
        if balance < bet: return await m.reply("❌ Твоя энергия исчерпана.")

        # Система защиты
        logs = db.fetchall("SELECT profit FROM lotto_logs WHERE user_id = ? AND timestamp > ?", (m.from_user.id, time.time() - 300))
        is_prot = sum(l[0] for l in logs) > 800

        # Крутим веса
        w = BASE_WEIGHTS.copy()
        if loss_s >= 3: w[0] -= 10; w[2] += 10
        if spins_s >= 7: w[0] = 0; w[1] += 20
        if is_prot: w[0] += 30; w[5] = 0

        total_w = sum(w.values())
        rand = random.uniform(0, total_w)
        curr, mult = 0, 0
        for m_val, weight in w.items():
            curr += weight
            if rand <= curr: mult = m_val; break

        # Обновление
        profit = (bet * mult) - bet
        db.execute("UPDATE users SET power_points = power_points + ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (profit, (loss_s+1 if mult==0 else 0), (spins_s+1 if mult<=1 else 0), m.from_user.id))
        db.execute("INSERT INTO lotto_logs VALUES (?, ?, ?)", (m.from_user.id, profit, time.time()))

        icon = {100: "🔱", 5: "💎", 4: "🔥", 3: "✨", 2: "✅", 1: "🌀", 0: "💀"}.get(mult)
        await m.answer(f"{icon} **ЛОТЕРЕЯ**\n\nРезультат: **x{mult}**\nБаланс: `{balance + profit}` 💠")
    except: pass

# --- 3. ПВП С КНОПКОЙ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_invite(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_{uid}_{bet}"))
        await m.answer(f"⚔️ **ВЫЗОВ НА ДУЭЛЬ!**\n\n{m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name}!\nСтавка: `{bet}` 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_confirm(c: types.CallbackQuery):
    _, challenger_id, bet = c.data.split('_')
    challenger_id, bet = int(challenger_id), int(bet)
    defender_id = c.from_user.id
    if defender_id == challenger_id: return
    
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (challenger_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (defender_id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("❌ Недостаточно сил!", show_alert=True)
    
    win = random.choice([challenger_id, defender_id])
    lose = defender_id if win == challenger_id else challenger_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    
    winner = await bot.get_chat_member(c.message.chat.id, win)
    await c.message.edit_text(f"🏆 **АРЕНА:** Победил **{winner.user.first_name}**! (+{bet} 💠)")

# --- 4. ТОПЫ И ПЕРЕДАЧА ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith('/top') or "сильнейшие" in m.text.lower()))
async def cmd_top_power(m: types.Message):
    users = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 **СИЛЬНЕЙШИЕ БОГИ:**\n" + "\n".join([f"{i}. {u[0]} — `{u[1]}` 💠" for i, u in enumerate(users, 1)])
    await m.answer(res)

@dp.message_handler(lambda m: m.text and "активчики" in m.text.lower())
async def cmd_top_active(m: types.Message):
    users = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 **ТОП АКТИВЧИКОВ:**\n" + "\n".join([f"{i}. {u[0]} — `{u[1]}` 💬" for i, u in enumerate(users, 1)])
    await m.answer(res)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        if db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0] < amt: return
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **СДЕЛКА:** `{amt}` 💠 переданы успешно.")
    except: pass

# --- 5. ОБНОВЛЕННЫЙ ПРОФИЛЬ "МИ" ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    
    username = f"@{t.username}" if t.username else t.first_name
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    
    profile_ui = (
        f"✨ **СВИТОК БОЖЕСТВА** ✨\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 **Имя:** `{username}`\n"
        f"🎖 **Ранг:** _{rank}_\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚡️ **Мощь:** `{u[0]}` 💠\n"
        f"💬 **Опыт:** `{u[1]}` 📜\n"
        f"━━━━━━━━━━━━━━"
    )
    await m.answer(profile_ui, parse_mode="Markdown")

# --- 6. СЧЕТЧИК (СТРОГО ПОСЛЕДНИЙ) ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
