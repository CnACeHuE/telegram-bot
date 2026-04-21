import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 
MAIN_CHAT_ID = -1002408347623 

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

# --- ЦЕНЫ И ПРЕДМЕТЫ ---
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "role": 700, "mute": 200, "seal": 200}
ITEM_NAMES = {"thief": "🗡 Инструмент вора", "altar": "🕯 Жертвенный алтарь", "mirror": "🔮 Осколок зеркала", "echo": "🌌 Эхо бездны", "curse": "🌫 Проклятие нищеты", "mute": "🔇 Рофл-мут", "seal": "🛡 Печать молчания"}

# --- МАГАЗИН ---
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
               InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    elif cat == "magic":
        kb.add(InlineKeyboardButton("Эхо (150)", callback_data="buy_echo"),
               InlineKeyboardButton("Нищета (400)", callback_data="buy_curse"),
               InlineKeyboardButton("Очищение (1000)", callback_data="buy_clean"),
               InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    elif cat == "power":
        kb.add(InlineKeyboardButton("Роль (700)", callback_data="buy_role"),
               InlineKeyboardButton("Мут (200)", callback_data="buy_mute"),
               InlineKeyboardButton("Печать (200)", callback_data="buy_seal"),
               InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    return kb

@dp.message_handler(lambda m: m.text and m.text.lower() == "магазин")
async def cmd_shop(m: types.Message):
    await m.answer("🏛 **Сокровищница Обители**\n\nЗдесь ты можешь обменять свою силу на артефакты и влияние. Выбери категорию:", reply_markup=get_shop_kb("main"))

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_logic(c: types.CallbackQuery):
    action, val = c.data.split('_')
    uid = c.from_user.id
    check_user(uid, c.from_user.username)

    if action == "shop":
        await c.message.edit_text(f"🏛 **Категория: {val.upper()}**\n\nВыбирай с умом, путник.", reply_markup=get_shop_kb(val))
    
    elif action == "buy":
        price = PRICES.get(val, 999999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Твоей веры и силы недостаточно для этой покупки!", show_alert=True)
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        if val == "clean":
            db.execute("UPDATE users SET warn_points = 0 WHERE user_id = ?", (uid,))
            await c.answer("🧪 Очищение проведено! Твои грехи (варны) искуплены.", show_alert=True)
        else:
            db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
            await c.answer(f"✅ Предмет '{ITEM_NAMES.get(val)}' добавлен в твой инвентарь.", show_alert=True)

# --- ЛОТЕРЕЯ (С КРАСИВЫМ ВЫВОДОМ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    uid = m.from_user.id
    check_user(uid, m.from_user.username)
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    
    if bal < bet: return await m.reply(f"❌ Твой баланс слишком мал ({bal} 💠) для такой ставки!")
    
    res = random.random()
    if res < 0.2: mult, txt = 2, "🔥 Удача на твоей стороне! Очки удвоены!"
    elif res < 0.5: mult, txt = 1, "🌀 Судьба нейтральна. Ты вернул свою ставку."
    else: mult, txt = 0, "💀 Тьма поглотила твою ставку. Ты ничего не получил."
    
    win_total = bet * mult
    db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, win_total, uid))
    await m.answer(f"🎰 **Лотерея Обители**\n\n{txt}\n💰 Ставка: {bet}\n💎 Итог: {win_total}\n💠 Твой баланс: {bal - bet + win_total}")

# --- ПЕРЕДАЧА ОЧКОВ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    
    args = m.text.split()
    if len(args) < 2 or not args[1].isdigit(): return
    amt = int(args[1])
    
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < amt: return await m.reply("❌ У тебя нет столько силы, чтобы делиться!")

    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
    await m.answer(f"🤝 **Передача силы**\n\nИгрок @{m.from_user.username} передал {amt} 💠 в дар @{m.reply_to_message.from_user.username}!")

# --- АДМИН КОМАНДЫ (ГИВ / БОЖЕСТВО) ---
@dp.message_handler(lambda m: m.text and any(m.text.lower().startswith(x) for x in ["гив", "божество+", "божество-"]))
async def admin_power(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    if not m.reply_to_message: return
    tid = m.reply_to_message.from_user.id
    cmd = m.text.lower()

    if "гив" in cmd:
        amt = int(cmd.split()[1]) if len(cmd.split()) > 1 else 100
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🔱 **Воля Богов**\n\nИз пустоты возникло {amt} 💠 и перешло к @{m.reply_to_message.from_user.username}!")
    elif "божество+" in cmd:
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer(f"⚡️ **Вознесение**\n\n@{m.reply_to_message.from_user.username} теперь признан Божеством этой Обители!")
    elif "божество-" in cmd:
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (tid,))
        await m.answer(f"🌑 **Падение**\n\n@{m.reply_to_message.from_user.username} лишен божественных полномочий.")

# --- ПРОФИЛЬ (Ю* / МИ) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith('ю*')))
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t.id, t.username)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    inv_text = "\n🎒 **Твой инвентарь:**\n" + "\n".join([f"— {ITEM_NAMES.get(i[0], i[0])}: {i[1]} шт." for i in inv]) if inv else "\n🎒 Инвентарь пуст."
    
    await m.answer(f"👤 **Профиль: {t.full_name}**\n\n🎖 Статус: {u[2].upper()}\n💠 Сила: {u[0]}\n💬 Сообщений: {u[1]}\n{inv_text}", parse_mode="Markdown")

# --- СЧЕТЧИК СООБЩЕНИЙ ---
@dp.message_handler(content_types=['text'])
async def process_msgs(m: types.Message):
    check_user(m.from_user.id, m.from_user.username)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
