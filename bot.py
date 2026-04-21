import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 
MAIN_CHAT_ID = -1002408347623 

# ССЫЛКИ НА КАРТИНКИ (Вставь свои рабочие ссылки)
PHOTOS = {
    "main": "https://i.postimg.cc/shop-main.jpg",
    "gear": "https://i.postimg.cc/shop-gear.jpg",
    "magic": "https://i.postimg.cc/shop-magic.jpg",
    "power": "https://i.postimg.cc/shop-power.jpg"
}

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
    name = name or "Unknown"
    if db.is_pg: db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO NOTHING", (uid, name))
    else: db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, name))

# --- ТВОЯ СИСТЕМА РАНГОВ (ОБНОВЛЕННАЯ) ---
def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон 🪴"

# --- МАГАЗИН И ЦЕНЫ ---
PRICES = {
    "thief": 250, "altar": 500, "mirror": 300,
    "echo": 150, "curse": 400, "clean": 1000,
    "role": 700, "mute": 200, "seal": 200, "prefix": 55555
}
ITEM_NAMES = {"thief": "🗡 Вор", "altar": "🕯 Алтарь", "mirror": "🔮 Зеркало", "echo": "🌌 Эхо", "curse": "🌫 Нищета", "mute": "🔇 Мут", "seal": "🛡 Печать", "prefix": "👑 Префикс"}

def get_shop_kb(cat="main"):
    kb = InlineKeyboardMarkup(row_width=2)
    if cat == "main":
        kb.add(InlineKeyboardButton("🗡 Снаряжение", callback_data="shop_gear"),
               InlineKeyboardButton("🧪 Магия", callback_data="shop_magic"),
               InlineKeyboardButton("👑 Власть", callback_data="shop_power"))
    elif cat == "gear":
        kb.add(InlineKeyboardButton("Вор (250)", callback_data="buy_thief"), 
               InlineKeyboardButton("Алтарь (500)", callback_data="buy_altar"), 
               InlineKeyboardButton("Зеркало (300)", callback_data="buy_mirror"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    elif cat == "magic":
        kb.add(InlineKeyboardButton("Эхо (150)", callback_data="buy_echo"), 
               InlineKeyboardButton("Нищета (400)", callback_data="buy_curse"), 
               InlineKeyboardButton("Очищение (1000)", callback_data="buy_clean"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    elif cat == "power":
        kb.add(InlineKeyboardButton("Роль (700)", callback_data="buy_role"), 
               InlineKeyboardButton("Мут (200)", callback_data="buy_mute"), 
               InlineKeyboardButton("Префикс (55555)", callback_data="buy_prefix"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="shop_main"))
    return kb

@dp.message_handler(lambda m: m.text and m.text.lower() == "магазин")
async def cmd_shop(m: types.Message):
    await m.answer_photo(PHOTOS["main"], caption="🏛 **СОКРОВИЩНИЦА ОБИТЕЛИ**\n\nВыбирай категорию, путник:", reply_markup=get_shop_kb("main"), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_logic(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        photo_url = PHOTOS.get(val, PHOTOS["main"])
        media = InputMediaPhoto(photo_url, caption=f"🏛 **КАТЕГОРИЯ: {val.upper()}**\n\nВыбери желаемое:")
        try:
            await c.message.edit_media(media, reply_markup=get_shop_kb(val))
        except:
            await c.answer("Ошибка загрузки изображения")
            
    elif action == "buy":
        price = PRICES.get(val, 99999)
        uid = c.from_user.id
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Твоей силы недостаточно!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
        await c.answer(f"✅ Успешно: {ITEM_NAMES.get(val, val)}", show_alert=True)

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith('ю*')))
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t.id, t.username)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    rank = get_rank(u[1]) if u[2] != 'admin' else "Божество 🔱"
    inv_txt = "\n🎒 " + ", ".join([f"{ITEM_NAMES.get(i[0], i[0])} ({i[1]})" for i in inv]) if inv else "\n🎒 Инвентарь пуст"
    
    await m.answer(f"👤 **{t.full_name}**\n───────\n🎖 Ранг: **{rank}**\n💠 Сила: `{u[0]}`\n💬 Сообщ: `{u[1]}`\n───────{inv_txt}", parse_mode="Markdown")

# --- КОМАНДЫ (ПАССИВНЫЕ ТЕКСТЫ СОХРАНЕНЫ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    uid = m.from_user.id
    check_user(uid, m.from_user.username)
    parts = m.text.split()
    bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < bet: return await m.reply("❌ Недостаточно сил!")
    
    chance = random.random()
    if chance < 0.05: mult, msg = 10, "🎰 О БОГИ! ДЖЕКПОТ x10! 🔥"
    elif chance < 0.15: mult, msg = 5, "💎 Невероятная удача! x5!"
    elif chance < 0.30: mult, msg = 3, "✨ Магический резонанс! x3!"
    elif chance < 0.55: mult, msg = 2, "✅ Успех! x2."
    elif chance < 0.75: mult, msg = 1, "🌀 Пустота. Ставка возвращена."
    else: mult, msg = 0, "💀 Тьма поглотила твою силу. x0."
    
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, win, uid))
    await m.answer(f"🎰 **Лотерея Обители**\n\n{msg}\nСтавка: {bet} 💠 | Итог: {win} 💠")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    parts = m.text.split()
    if len(parts) < 2 or not parts[1].isdigit(): return
    amt = int(parts[1])
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < amt: return await m.reply("❌ Недостаточно силы!")
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
    await m.answer(f"🤝 **Передача силы**\n\nИгрок @{m.from_user.username} передал {amt} 💠 в дар @{m.reply_to_message.from_user.username}!")

@dp.message_handler(lambda m: m.text and any(x in m.text.lower() for x in ["божество+", "божество-", "гив"]))
async def admin_tools(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    if not m.reply_to_message: return
    tid = m.reply_to_message.from_user.id
    cmd = m.text.lower()
    if "божество+" in cmd:
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer("⚡️ Пользователь возведен в ранг Божества!")
    elif "божество-" in cmd:
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (tid,))
        await m.answer("🌑 Божественная сила отозвана.")
    elif "гив" in cmd:
        try:
            amt = int(cmd.split()[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
            await m.answer(f"🔱 Воля Богов: даровано {amt} 💠")
        except: pass

@dp.message_handler(content_types=['text'])
async def counter(m: types.Message):
    check_user(m.from_user.id, m.from_user.username)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
