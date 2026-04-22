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
# Добавляем таблицу логов для системы защиты
db.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player')")
db.execute("CREATE TABLE IF NOT EXISTS lotto_logs (user_id BIGINT, profit INTEGER, timestamp REAL)")

def check_user(u: types.User):
    name = u.username or u.first_name or "Путник"
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

# --- ЛОГИКА ЛОТЕРЕИ ---

async def get_recent_profit(user_id):
    five_mins_ago = time.time() - 300
    logs = db.fetchall("SELECT profit FROM lotto_logs WHERE user_id = ? AND timestamp > ?", (user_id, five_mins_ago))
    return sum(log[0] for log in logs)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        parts = m.text.split()
        bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        
        # Лимит ставки
        if bet < 1 or bet > 500:
            return await m.reply("⚠️ Боги принимают подношения только от `1` до `500` 💠!")

        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
        if bal < bet:
            return await m.reply("❌ Твоя мощь слишком слаба для такой ставки.")

        # Проверка системы защиты
        recent_profit = await get_recent_profit(m.from_user.id)
        is_protection_on = recent_profit > 800
        
        # Шансы: [x100, x5, x4, x3, x2, x1, x0]
        chances = [0.0002, 0.005, 0.015, 0.03, 0.12, 0.35, 0.4798]
        
        if is_protection_on:
            # Срезаем победные шансы на 15% (кроме x100 и x1)
            # Уменьшаем x5, x4, x3, x2
            reduction = 0
            for i in [1, 2, 3, 4]:
                old_val = chances[i]
                new_val = old_val * 0.85
                reduction += (old_val - new_val)
                chances[i] = new_val
            chances[6] += reduction # Отдаем срезанный шанс в проигрыш (x0)

        # Розыгрыш
        r = random.random()
        cumulative = 0
        multipliers = [100, 5, 4, 3, 2, 1, 0]
        mult = 0
        
        for i, chance in enumerate(chances):
            cumulative += chance
            if r <= cumulative:
                mult = multipliers[i]
                break
        
        win_amount = bet * mult
        profit = win_amount - bet
        
        # Обновляем БД
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (profit, m.from_user.id))
        db.execute("INSERT INTO lotto_logs (user_id, profit, timestamp) VALUES (?, ?, ?)", (m.from_user.id, profit, time.time()))
        
        # Визуал
        status_icon = "🟢" if mult > 1 else "🟡" if mult == 1 else "🔴"
        prot_msg = "\n⚠️ *Внимание богов привлечено (шансы снижены)*" if is_protection_on else ""
        
        res_text = {
            100: "🔥 СВЯТОЙ ДЖЕКПОТ x100!",
            5: "💎 Божественный дар x5!",
            4: "✨ Высшая магия x4!",
            3: "📜 Древний свиток x3!",
            2: "✅ Успех x2",
            1: "🌀 Равновесие x1",
            0: "💀 Пустота x0"
        }[mult]
        
        await m.answer(f"{status_icon} **ЛОТЕРЕЯ**\n\nРезультат: **{res_text}**\nИтог: `{win_amount}` 💠{prot_msg}", parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Lotto error: {e}")

# --- ПЕРЕДАЧА (ИСПРАВЛЕНО) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: 
        return await m.reply("⚠️ Нужно ответить на сообщение получателя!")
    
    try:
        parts = m.text.split()
        if len(parts) < 2: return
        amt = int(parts[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        
        if uid == tid: return await m.reply("Нельзя передать силы самому себе.")
        if amt <= 0: return
        
        check_user(m.from_user)
        check_user(m.reply_to_message.from_user)
        
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt:
            return await m.reply("❌ Недостаточно сил!")
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        
        await m.answer(f"🤝 **СДЕЛКА:** {m.from_user.first_name} передал `{amt}` 💠 {m.reply_to_message.from_user.first_name}")
    except:
        await m.reply("Используй формат: `передать 100` через ответ.")

# --- АКТИВЧИКИ ---
@dp.message_handler(lambda m: m.text and "активчики" in m.text.lower())
async def cmd_top_active(m: types.Message):
    users = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
    res = "🔥 **ТОП АКТИВЧИКОВ ОБИТЕЛИ:**\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {u[0]} — `{u[1]}` 💬\n"
    await m.answer(res, parse_mode="Markdown")

# --- АДМИН ПАНЕЛЬ (ГИВ, БОЖЕСТВО) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['гив', 'божество+', 'божество-'])
async def admin_tools(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    if not m.reply_to_message: return
    
    target_id = m.reply_to_message.from_user.id
    cmd = m.text.lower().split()[0]
    
    if cmd == 'божество+':
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await m.answer("⚡️ Смертный возведен в ранг **Божества**!")
    elif cmd == 'божество-':
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await m.answer("☁️ Ранг Божества отозван.")
    elif cmd == 'гив':
        try:
            amt = int(m.text.split()[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target_id))
            await m.answer(f"🔱 В дар получено `{amt}` 💠.")
        except: pass

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    await m.answer(f"💠 **ИНФО:** {t.full_name}\n🎖 **Ранг:** `{u[2].upper()}`\n⚡️ **Мощь:** `{u[0]}`\n💬 **Активность:** `{u[1]}`")

# --- СЧЕТЧИК (СТРОГО ПОСЛЕДНИЙ) ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
