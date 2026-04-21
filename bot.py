import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 
MODERATORS = [7361338806] # Можешь добавить ID второго админа через запятую
MAIN_CHAT_ID = -1002408347623 # Твой ID с префиксом -100 для супергрупп

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- УНИВЕРСАЛЬНАЯ БАЗА ДАННЫХ ---
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
db.execute("""CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, 
              power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, 
              role TEXT DEFAULT 'player', custom_role TEXT DEFAULT '', warn_points INTEGER DEFAULT 0)""")
db.execute("""CREATE TABLE IF NOT EXISTS inventory (user_id BIGINT, item_id TEXT, 
              count INTEGER DEFAULT 0, PRIMARY KEY (user_id, item_id))""")

def check_user(uid, name):
    if db.is_pg: db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO NOTHING", (uid, name))
    else: db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, name))

async def is_allowed(m): return m.chat.id == MAIN_CHAT_ID or m.from_user.id == ADMIN_ID

# --- ЦЕНЫ И НАЗВАНИЯ ---
PRICES = {
    "thief": 250, "altar": 500, "mirror": 300,
    "echo": 150, "curse": 400, "clean": 1000,
    "role": 700, "mute": 200, "seal": 200
}
ITEM_NAMES = {
    "thief": "🗡 Инструмент вора", "altar": "🕯 Жертвенный алтарь", 
    "mirror": "🔮 Осколок зеркала", "echo": "🌌 Эхо бездны", 
    "curse": "🌫 Проклятие нищеты", "mute": "🔇 Рофл-мут", "seal": "🛡 Печать молчания"
}

# --- МАГАЗИН (ИНТЕРФЕЙС) ---
def get_shop_kb(cat="main"):
    kb = InlineKeyboardMarkup(row_width=2)
    if cat == "main":
        kb.add(InlineKeyboardButton("🗡 Снаряжение", callback_data="shop_gear"),
               InlineKeyboardButton("🧪 Магия", callback_data="shop_magic"),
               InlineKeyboardButton("👑 Власть", callback_data="shop_power"))
    elif cat == "gear":
        kb.add(InlineKeyboardButton("Вор (250)", callback_data="buy_thief"),
               InlineKeyboardButton("Алтарь (500)", callback_data="buy_altar"),
               InlineKeyboardButton("Зеркало (300)", callback_data="buy_mirror"),
               InlineKeyboardButton("⬅️", callback_data="shop_main"))
    elif cat == "magic":
        kb.add(InlineKeyboardButton("Эхо (150)", callback_data="buy_echo"),
               InlineKeyboardButton("Нищета (400)", callback_data="buy_curse"),
               InlineKeyboardButton("Очищение (1000)", callback_data="buy_clean"),
               InlineKeyboardButton("⬅️", callback_data="shop_main"))
    elif cat == "power":
        kb.add(InlineKeyboardButton("Роль (700)", callback_data="buy_role"),
               InlineKeyboardButton("Мут (200)", callback_data="buy_mute"),
               InlineKeyboardButton("Печать (200)", callback_data="buy_seal"),
               InlineKeyboardButton("⬅️", callback_data="shop_main"))
    return kb

@dp.message_handler(lambda m: m.text and m.text.lower() == "магазин")
async def cmd_shop(m: types.Message):
    if not await is_allowed(m): return
    await m.answer("🏛 **Сокровищница Обители**\nВыбери категорию:", reply_markup=get_shop_kb())

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_logic(c: types.CallbackQuery):
    action, val = c.data.split('_')
    uid = c.from_user.id
    check_user(uid, c.from_user.username)

    if action == "shop":
        await c.message.edit_text(f"🏛 Категория: {val}", reply_markup=get_shop_kb(val))
    
    elif action == "buy":
        price = PRICES.get(val, 999999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Недостаточно сил!", show_alert=True)
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        if val == "clean":
            db.execute("UPDATE users SET warn_points = 0 WHERE user_id = ?", (uid,))
            await c.answer("🧪 Очищение проведено!", show_alert=True)
        elif val == "role":
            await c.answer("🎭 Используй команду: роль [текст]", show_alert=True)
        else:
            db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
            await c.answer(f"✅ Куплено: {ITEM_NAMES.get(val)}", show_alert=True)

# --- КОМАНДЫ ПРЕДМЕТОВ ---
@dp.message_handler(lambda m: m.text and m.text.lower() == "кость судьбы")
async def cmd_dice(m: types.Message):
    if not await is_allowed(m): return
    uid = m.from_user.id
    check_user(uid, m.from_user.username)
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < 100: return await m.reply("Минимум 100 💠")
    
    db.execute("UPDATE users SET power_points = power_points - 100 WHERE user_id = ?", (uid,))
    side = random.randint(1, 6)
    if side <= 2:
        db.execute("UPDATE users SET power_points = power_points - 100 WHERE user_id = ?", (uid,))
        await m.reply("🌑 Кость: 1-2. Потеря очков (-200 💠)")
    elif side <= 4: await m.reply(f"🌫 Выпало {side}. Тишина.")
    elif side == 5:
        db.execute("UPDATE users SET power_points = power_points + 300 WHERE user_id = ?", (uid,))
        await m.reply("✨ Удача: 5! (+300 💠)")
    else:
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, 'echo', 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid,))
        await m.reply("🎁 ДЖЕКПОТ! Выпало 6. Предмет: Эхо бездны")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith("использовать вор"))
async def cmd_thief(m: types.Message):
    if not await is_allowed(m) or not m.reply_to_message: return
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    
    cnt = db.execute("SELECT count FROM inventory WHERE user_id = ? AND item_id = 'thief'", (uid,))
    if not cnt or cnt[0] < 1: return await m.reply("Нет Инструмента вора!")

    # Проверка зеркала
    mir = db.execute("SELECT count FROM inventory WHERE user_id = ? AND item_id = 'mirror'", (tid,))
    db.execute("UPDATE inventory SET count = count - 1 WHERE user_id = ? AND item_id = 'thief'", (uid,))
    
    if mir and mir[0] > 0:
        db.execute("UPDATE inventory SET count = count - 1 WHERE user_id = ? AND item_id = 'mirror'", (tid,))
        loss = random.randint(100, 300)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (loss, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (loss, tid))
        return await m.answer(f"🔮 Осколок Зеркала! Вор потерял {loss} 💠")

    t_bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
    amt = random.randint(1, 800)
    if random.randint(1, 100) <= (70 if amt <= 250 else 15) and t_bal >= amt:
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, tid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, uid))
        await m.answer(f"🗡 Украдено {amt} 💠!")
    else:
        db.execute("UPDATE users SET power_points = power_points - 250 WHERE user_id = ?", (uid,))
        await m.answer("💀 Провал! Минус 250 💠")

# --- ЛС И РОЛИ ---
@dp.message_handler(lambda m: m.chat.type == 'private' and m.text.lower().startswith('/echo'))
async def l_echo(m: types.Message):
    txt = m.text[6:].strip()
    res = db.execute("SELECT count FROM inventory WHERE user_id = ? AND item_id = 'echo'", (m.from_user.id,))
    if not res or res[0] < 1: return await m.reply("Нужно купить Эхо!")
    db.execute("UPDATE inventory SET count = count - 1 WHERE user_id = ? AND item_id = 'echo'", (m.from_user.id,))
    await bot.send_message(MAIN_CHAT_ID, f"🌌 **Эхо Бездны:**\n« {txt} »")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith("роль"))
async def cmd_role(m: types.Message):
    txt = m.text[5:].strip()
    if not txt or len(txt) > 20: return
    m_text = " ".join([f"ID:{aid}" for aid in MODERATORS])
    await m.answer(f"⏳ Запрос отправлен богам.\n🎭 Роль: {txt}\n{m_text}")

# --- ПРОФИЛЬ И СЧЕТЧИК ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль'])
async def cmd_me(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t.id, t.username)
    u = db.execute("SELECT power_points, msg_count, custom_role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    inv_s = "\n🎒: " + ", ".join([f"{i[0]} x{i[1]}" for i in inv]) if inv else ""
    await m.answer(f"👤 {t.full_name}\n💠 Сила: {u[0]}\n💬 Сообщ: {u[1]}{inv_s}")

@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    if m.chat.id != MAIN_CHAT_ID: return
    check_user(m.from_user.id, m.from_user.username)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
