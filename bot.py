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
        except: self.connect(); return self.execute(sql, params)
    def fetchall(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

db = Database()
# Создаем таблицу с новыми полями для логики лотереи
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY, 
    username TEXT, 
    power_points INTEGER DEFAULT 100, 
    msg_count INTEGER DEFAULT 0, 
    role TEXT DEFAULT 'player',
    loss_streak INTEGER DEFAULT 0,
    spins_since_win INTEGER DEFAULT 0
)""")
db.execute("CREATE TABLE IF NOT EXISTS lotto_logs (user_id BIGINT, profit INTEGER, timestamp REAL)")

def check_user(u: types.User):
    name = u.username or u.first_name or "Путник"
    db.execute("""
    INSERT INTO users (user_id, username) VALUES (?, ?) 
    ON CONFLICT (user_id) DO UPDATE SET username = ?""", (u.id, name, name))

# --- ЯДРО УМНОЙ ЛОТЕРЕИ ---

BASE_WEIGHTS = {
    0: 50,    # Проигрыш
    1: 30,    # Возврат
    2: 12,    # x2
    3: 5,     # x3
    4: 2,     # x4
    5: 1,     # x5
    100: 0.02 # Джекпот (очень редкий)
}

TARGET_RTP = 0.92

def calculate_rtp(weights):
    total = sum(weights.values())
    return sum((m * w) for m, w in weights.items()) / total

def adjust_weights(weights, loss_streak, spins_since_win, balance, bet, is_protection):
    w = weights.copy()
    
    # 🔁 Anti-tilt: помогаем при серии неудач
    if loss_streak >= 3:
        w[0] -= 10
        w[2] += 5
        w[1] += 5
    
    # 🎁 Гарант: после 7 проигрышей победа обязательна
    if spins_since_win >= 7:
        w[0] = 0
        w[2] += 15
        w[1] += 10

    # 💰 Помощь новичкам / беднякам
    if balance < bet * 3:
        w[0] -= 5
        w[1] += 5

    # 🛡 СИСТЕМА ЗАЩИТЫ (если профит > 800)
    if is_protection:
        w[0] += 20  # Резко повышаем шанс проигрыша
        for k in [2, 3, 4, 5]: w[k] *= 0.5 # Режем иксы в два раза

    # 🧠 Контроль RTP
    curr_rtp = calculate_rtp(w)
    if curr_rtp > TARGET_RTP:
        w[0] += 5
        if w[5] > 0.5: w[5] -= 0.5
    elif curr_rtp < TARGET_RTP - 0.1:
        w[2] += 3

    # Убираем отрицательные веса
    return {k: max(0, v) for k, v in w.items()}

# --- КОМАНДА ЛОТЕРЕИ ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        parts = m.text.split()
        bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        if bet < 1 or bet > 500: return await m.reply("⚠️ Ставки от `1` до `500`!")

        u = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        balance, loss_s, spins_s = u

        if balance < bet: return await m.reply("❌ Недостаточно сил!")

        # Проверка защиты (профит за 5 мин)
        five_mins_ago = time.time() - 300
        logs = db.fetchall("SELECT profit FROM lotto_logs WHERE user_id = ? AND timestamp > ?", (m.from_user.id, five_mins_ago))
        recent_profit = sum(log[0] for log in logs)
        is_protection = recent_profit > 800

        # Получаем веса и крутим
        weights = adjust_weights(BASE_WEIGHTS, loss_s, spins_s, balance, bet, is_protection)
        
        # Выбор результата
        total_w = sum(weights.values())
        rand = random.uniform(0, total_w)
        cumulative = 0
        multiplier = 0
        for m_val, weight in weights.items():
            cumulative += weight
            if rand <= cumulative:
                multiplier = m_val
                break

        # Обновление статистики
        new_loss_s = loss_s + 1 if multiplier == 0 else 0
        new_spins_s = spins_s + 1 if multiplier <= 1 else 0
        win_amt = bet * multiplier
        profit = win_amt - bet

        db.execute("""
            UPDATE users SET power_points = power_points + ?, 
            loss_streak = ?, spins_since_win = ? WHERE user_id = ?""", 
            (profit, new_loss_s, new_spins_s, m.from_user.id))
        
        db.execute("INSERT INTO lotto_logs (user_id, profit, timestamp) VALUES (?, ?, ?)", 
                   (m.from_user.id, profit, time.time()))

        # Ответ игроку
        icons = {100: "🔱", 5: "💎", 4: "🔥", 3: "✨", 2: "✅", 1: "🌀", 0: "💀"}
        prot_warning = "\n⚠️ *Боги следят за твоей удачей...*" if is_protection else ""
        
        await m.answer(
            f"{icons.get(multiplier, '🎰')} **ЛОТЕРЕЯ**\n\n"
            f"Множитель: **x{multiplier}**\n"
            f"Итог: `{win_amt}` 💠{prot_warning}", 
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(e)

# --- ОСТАЛЬНЫЕ КОМАНДЫ (ПЕРЕДАЧА, АКТИВЧИКИ, ПРОФИЛЬ) ---
# (Код остается таким же стабильным, как в v33)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение получателя!")
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid or amt <= 0: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ Мало сил!")
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **СДЕЛКА:** {m.from_user.first_name} ➔ `{amt}` 💠 ➔ {m.reply_to_message.from_user.first_name}")
    except: pass

@dp.message_handler(lambda m: m.text and "активчики" in m.text.lower())
async def cmd_top_active(m: types.Message):
    users = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 **АКТИВЧИКИ ОБИТЕЛИ:**\n\n"
    for i, u in enumerate(users, 1): res += f"{i}. {u[0]} — `{u[1]}` 💬\n"
    await m.answer(res, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    await m.answer(f"💠 **ИНФО:** {t.full_name}\n🎖 **Ранг:** `{u[2].upper()}`\n⚡️ **Мощь:** `{u[0]}`\n💬 **Активность:** `{u[1]}`")

@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
