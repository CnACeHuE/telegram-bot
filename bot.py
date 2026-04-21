import logging, sqlite3, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 

# ССЫЛКИ НА КАРТИНКИ (Если ссылка не работает, бот не упадет)
PHOTOS = {
    "main": "https://i.postimg.cc/90pX7pLz/main.jpg",
    "gear": "https://i.postimg.cc/85zX3S0r/gear.jpg",
    "magic": "https://i.postimg.cc/3R6M3yv1/magic.jpg",
    "power": "https://i.postimg.cc/vHzZfN3F/power.jpg"
}

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
db.execute("CREATE TABLE IF NOT EXISTS inventory (user_id BIGINT, item_id TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, item_id))")

def check_user(u: types.User):
    name = u.username or u.first_name or "Путник"
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

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

# --- МАГАЗИН ---
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "mute": 200, "prefix": 55555}
ITEM_NAMES = {"thief": "🗡 Вор", "altar": "🕯 Алтарь", "mirror": "🔮 Зеркало", "echo": "🌌 Эхо", "curse": "🌫 Нищета", "mute": "🔇 Мут", "prefix": "👑 Префикс"}

def get_shop_kb(cat="main"):
    kb = InlineKeyboardMarkup(row_width=2)
    if cat == "main":
        kb.add(InlineKeyboardButton("🗡 СНАРЯЖЕНИЕ", callback_data="shop_gear"),
               InlineKeyboardButton("🧪 МАГИЯ", callback_data="shop_magic"),
               InlineKeyboardButton("👑 ВЛАСТЬ", callback_data="shop_power"))
    elif cat == "gear":
        kb.add(InlineKeyboardButton("🗡 Вор (250)", callback_data="buy_thief"), 
               InlineKeyboardButton("🕯 Алтарь (500)", callback_data="buy_altar"), 
               InlineKeyboardButton("🔮 Зеркало (300)", callback_data="buy_mirror"))
        kb.add(InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    elif cat == "magic":
        kb.add(InlineKeyboardButton("🌌 Эхо (150)", callback_data="buy_echo"), 
               InlineKeyboardButton("🌫 Нищета (400)", callback_data="buy_curse"), 
               InlineKeyboardButton("🧪 Очистка (1000)", callback_data="buy_clean"))
        kb.add(InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    elif cat == "power":
        kb.add(InlineKeyboardButton("🔇 Мут (200)", callback_data="buy_mute"), 
               InlineKeyboardButton("👑 Префикс (55555)", callback_data="buy_prefix"))
        kb.add(InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    return kb

# --- ПРИОРЕТЕТНЫЕ КОМАНДЫ (ПРОФИЛЬ И МАГАЗИН) ---

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    items = ", ".join([f"{ITEM_NAMES.get(i[0], i[0])} ({i[1]})" for i in inv]) if inv else "Пусто"
    
    res = (f"💠 **ОБИТЕЛЬ: ПРОФИЛЬ** 💠\n"
           f"──────────────\n"
           f"👤 **Имя:** {t.full_name}\n"
           f"🎖 **Ранг:** `{rank}`\n"
           f"⚡️ **Сила:** `{u[0]}`\n"
           f"💬 **Опыт:** `{u[1]}`\n"
           f"🎒 **Сумка:** _{items}_\n"
           f"──────────────")
    await m.answer(res, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text and "магазин" in m.text.lower())
async def cmd_shop(m: types.Message):
    check_user(m.from_user)
    await m.answer_photo(PHOTOS["main"], caption="🟢 **НЕОНОВЫЙ МАРКЕТ**\n\nВыбери нужный отсек сокровищницы:", reply_markup=get_shop_kb("main"))

# --- CALLBACKS (МАГАЗИН) ---
@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_callback(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        try:
            await c.message.edit_media(InputMediaPhoto(PHOTOS.get(val, PHOTOS["main"]), caption=f"✨ **КАТЕГОРИЯ: {val.upper()}**"), reply_markup=get_shop_kb(val))
        except: await c.answer("Обновление...")
    elif action == "buy":
        price = PRICES.get(val, 99999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,))[0]
        if bal < price: return await c.answer("❌ Мало силы!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, c.from_user.id))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (c.from_user.id, val))
        await c.answer(f"✅ Получено: {ITEM_NAMES.get(val, val)}", show_alert=True)

# --- ИГРОВЫЕ КОМАНДЫ (ПЕРЕДАЧА, ПВП, ДЕП) ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение получателя!")
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ Недостаточно силы!")
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **СДЕЛКА:** {m.from_user.first_name} ➔ {amt} 💠 ➔ {m.reply_to_message.from_user.first_name}")
    except: await m.reply("Формат: `передать 100` (через ответ)")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    try:
        args = m.text.split()
        bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
        if b1 < bet or b2 < bet: return await m.reply("❌ Кто-то слишком слаб для такой ставки!")
        win = random.choice([uid, tid])
        lose = tid if win == uid else uid
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
        w_name = m.from_user.first_name if win == uid else m.reply_to_message.from_user.first_name
        await m.answer(f"⚔️ **АРЕНА:** Победа за **{w_name}**! (+{bet} 💠)")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
        if bal < bet: return await m.reply("❌ Мало сил!")
        r = random.random()
        mult = 10 if r < 0.05 else 5 if r < 0.15 else 3 if r < 0.3 else 2 if r < 0.55 else 1 if r < 0.75 else 0
        db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, m.from_user.id))
        await m.answer(f"🎰 **ЛОТЕРЕЯ:** Множитель **x{mult}**\nИтог: `{bet*mult}` 💠")
    except: pass

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and ("гив" in m.text.lower() or "божество" in m.text.lower()))
async def admin_tools(m: types.Message):
    if not m.reply_to_message: return
    tid = m.reply_to_message.from_user.id
    if "божество+" in m.text.lower():
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer("🔱 Ранг Божества выдан!")
    elif "гив" in m.text.lower():
        amt = int(m.text.split()[1])
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🔱 Даровано {amt} силы.")

# --- СЧЕТЧИК (СТРОГО В КОНЦЕ) ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
