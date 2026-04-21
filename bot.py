import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 
MODERATORS = [7361338806] 
# Если бот молчит в группе, убедись что ID верный (должен начинаться с -100)
ALLOWED_CHATS = [-1002408347623, -1002306782404] # Добавь сюда ID своего тест-чата

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None and psycopg2 is not None
        self.connect()
    def connect(self):
        if self.is_pg: self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else: self.conn = sqlite3.connect("abode_gods.db", check_same_thread=False)
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
db.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player', custom_role TEXT DEFAULT '', warn_points INTEGER DEFAULT 0)")
db.execute("CREATE TABLE IF NOT EXISTS inventory (user_id BIGINT, item_id TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, item_id))")

def check_user(uid, name):
    if db.is_pg: db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO NOTHING", (uid, name))
    else: db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, name))

async def is_allowed(m): 
    # Если хочешь, чтобы бот работал ВЕЗДЕ на время теста, замени на: return True
    return m.chat.id in ALLOWED_CHATS or m.chat.type == 'private' or m.from_user.id == ADMIN_ID

# --- ЛОТЕРЕЯ / ПВП / ПЕРЕДАЧА ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_lottery(m: types.Message):
    if not await is_allowed(m): return
    uid = m.from_user.id
    check_user(uid, m.from_user.username)
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < bet: return await m.reply(f"Недостаточно сил! Баланс: {bal} 💠")

    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, uid))
    res = random.random()
    if res < 0.1: mult = 3 # 10% шанс на х3
    elif res < 0.4: mult = 2 # 30% шанс на х2
    elif res < 0.7: mult = 1 # 30% шанс вернуть своё
    else: mult = 0

    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, uid))
    await m.reply(f"🎰 Результат: x{mult}\n💠 Баланс: {bal - bet + win}")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not await is_allowed(m) or not m.reply_to_message: return
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    
    args = m.text.split()
    if len(args) < 2 or not args[1].isdigit(): return
    amt = int(args[1])

    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < amt: return await m.reply("Недостаточно сил!")

    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
    await m.answer(f"✅ Передано {amt} 💠 пользователю {m.reply_to_message.from_user.first_name}")

# --- МАГАЗИН И ПРОФИЛЬ (ОСТАВЛЯЕМ) ---
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "role": 700, "mute": 200, "seal": 200}

@dp.message_handler(lambda m: m.text and m.text.lower() == "магазин")
async def cmd_shop(m: types.Message):
    if not await is_allowed(m): return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🗡 Снаряжение", callback_data="shop_gear"),
           InlineKeyboardButton("🧪 Магия", callback_data="shop_magic"),
           InlineKeyboardButton("👑 Власть", callback_data="shop_power"))
    await m.answer("🏛 **Сокровищница Обители**\nВыбери категорию:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_logic(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        kb = InlineKeyboardMarkup(row_width=2)
        if val == "gear":
            kb.add(InlineKeyboardButton("Вор (250)", callback_data="buy_thief"), InlineKeyboardButton("Зеркало (300)", callback_data="buy_mirror"))
        elif val == "magic":
            kb.add(InlineKeyboardButton("Эхо (150)", callback_data="buy_echo"), InlineKeyboardButton("Очищение (1000)", callback_data="buy_clean"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
        await c.message.edit_text(f"🏛 Категория: {val}", reply_markup=kb)
    elif action == "buy":
        price = PRICES.get(val, 999)
        uid = c.from_user.id
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Мало сил!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
        await c.answer("✅ Куплено!", show_alert=True)

@dp.message_handler(lambda m: m.text and m.text.lower() in ["ми", "профиль"])
async def cmd_me(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t.id, t.username)
    u = db.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (t.id,))
    await m.answer(f"👤 {t.full_name}\n💠 Сила: {u[0]}\n💬 Сообщ: {u[1]}")

# --- АДМИН КОМАНДЫ (ГИВ / БОЖЕСТВО) ---
@dp.message_handler(lambda m: m.text and any(m.text.lower().startswith(x) for x in ["гив", "божество+"]))
async def admin_cmds(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    if not m.reply_to_message: return
    
    cmd = m.text.lower()
    tid = m.reply_to_message.from_user.id
    
    if cmd.startswith("гив"):
        amt = int(cmd.split()[1]) if len(cmd.split()) > 1 else 100
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"✨ Даровано {amt} 💠")
    elif cmd.startswith("божество+"):
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer("⚡️ Пользователь возведен в ранг Божества!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
