import logging, sqlite3, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from datetime import datetime, timedelta

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 

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
db.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player', last_bonus TEXT)")
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
        kb.add(*(InlineKeyboardButton(f"{ITEM_NAMES[i]} ({PRICES[i]})", callback_data=f"buy_{i}") for i in ["thief", "altar", "mirror"]))
        kb.add(InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    elif cat == "magic":
        kb.add(*(InlineKeyboardButton(f"{ITEM_NAMES[i]} ({PRICES[i]})", callback_data=f"buy_{i}") for i in ["echo", "curse"]))
        kb.add(InlineKeyboardButton("🧪 Очистка (1000)", callback_data="buy_clean"), InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    elif cat == "power":
        kb.add(InlineKeyboardButton("🔇 Мут (200)", callback_data="buy_mute"), InlineKeyboardButton("👑 Префикс (55555)", callback_data="buy_prefix"))
        kb.add(InlineKeyboardButton("⬅️ НАЗАД", callback_data="shop_main"))
    return kb

# --- ОСНОВНЫЕ КОМАНДЫ ---

@dp.message_handler(commands=['start', 'help'])
async def cmd_start(m: types.Message):
    check_user(m.from_user)
    await m.answer("🌿 **Добро пожаловать в Обитель Богов!**\n\nПиши `профиль` или `ю*` чтобы увидеть свою мощь.\nПиши `магазин` для покупок.\nИспользуй `/bonus` каждый день!")

@dp.message_handler(lambda m: "магазин" in m.text.lower())
async def open_shop(m: types.Message):
    await m.answer_photo(PHOTOS["main"], caption="🏛 **СОКРОВИЩНИЦА ОБИТЕЛИ**\n\nВыбирай категорию:", reply_markup=get_shop_kb("main"))

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_logic(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        await c.message.edit_media(InputMediaPhoto(PHOTOS.get(val, PHOTOS["main"]), caption=f"✨ **КАТЕГОРИЯ: {val.upper()}**"), reply_markup=get_shop_kb(val))
    elif action == "buy":
        check_user(c.from_user)
        price = PRICES.get(val, 99999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,))[0]
        if bal < price: return await c.answer("❌ Недостаточно сил!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, c.from_user.id))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (c.from_user.id, val))
        await c.answer(f"✅ Успешно куплено: {ITEM_NAMES.get(val, val)}", show_alert=True)

@dp.message_handler(lambda m: m.text and (m.text.lower() in ['ми', 'профиль'] or m.text.lower().startswith('ю*')))
async def show_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    items = ", ".join([f"{ITEM_NAMES.get(i[0], i[0])}({i[1]})" for i in inv]) if inv else "Пусто"
    
    await m.answer(f"┏━━━━━━━━━━━━━━┓\n   👤 **{t.full_name}**\n┗━━━━━━━━━━━━━━┛\n🎖 **Ранг:** `{rank}`\n💠 **Сила:** `{u[0]}`\n💬 **Опыт:** `{u[1]}`\n🎒 **Сумка:** _{items}_", parse_mode="Markdown")

@dp.message_handler(commands=['bonus'])
async def get_bonus(m: types.Message):
    check_user(m.from_user)
    row = db.execute("SELECT last_bonus FROM users WHERE user_id = ?", (m.from_user.id,))
    now = datetime.now()
    if row[0] and datetime.fromisoformat(row[0]) + timedelta(days=1) > now:
        return await m.reply("⏳ Боги еще спят. Вернись позже!")
    
    gift = random.randint(50, 200)
    db.execute("UPDATE users SET power_points = power_points + ?, last_bonus = ? WHERE user_id = ?", (gift, now.isoformat(), m.from_user.id))
    await m.answer(f"✨ **БЛАГОСЛОВЕНИЕ:** Ты получил `{gift}` 💠 силы!")

@dp.message_handler(commands=['top'])
async def show_top(m: types.Message):
    users = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 **ТОП МОГУЩЕСТВЕННЫХ:**\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {u[0]} — `{u[1]}` 💠\n"
    await m.answer(res, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text.lower().startswith('передать'))
async def transfer_points(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Нужно ответить на сообщение!")
    try:
        amt = int(m.text.split()[1])
        if amt <= 0: return
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ Недостаточно сил!")
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **ПЕРЕДАЧА:** @{m.from_user.username} передал `{amt}` 💠 игроку @{m.reply_to_message.from_user.username}!")
    except: await m.reply("Пример: `передать 100` (через реплай)")

@dp.message_handler(lambda m: m.text.lower().startswith('пвп'))
async def pvp_battle(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        
        b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
        if b1 < bet or b2 < bet: return await m.reply("❌ Недостаточно сил для битвы!")

        win = random.choice([uid, tid])
        lose = tid if win == uid else uid
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
        
        winner_name = m.from_user.first_name if win == uid else m.reply_to_message.from_user.first_name
        await m.answer(f"⚔️ **АРЕНА:** В схватке на `{bet}` 💠 победил **{winner_name}**!")
    except: pass

@dp.message_handler(lambda m: m.text.lower().startswith(('лотерея', 'деп')))
async def lottery(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
        if bal < bet: return await m.reply("❌ Недостаточно сил!")
        
        r = random.random()
        mult = 10 if r < 0.05 else 5 if r < 0.15 else 3 if r < 0.3 else 2 if r < 0.55 else 1 if r < 0.75 else 0
        msgs = {10: "🎰 ДЖЕКПОТ x10!", 5: "💎 УДАЧА x5!", 3: "✨ МАГИЯ x3!", 2: "✅ УСПЕХ x2", 1: "🌀 ПУСТО x1", 0: "💀 ТЬМА x0"}
        
        db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, m.from_user.id))
        await m.answer(f"🎰 **ЛОТЕРЕЯ:** {msgs[mult]}\nСтавка: `{bet}` | Итог: `{bet*mult}` 💠")
    except: pass

@dp.message_handler(content_types=['text'])
async def count_messages(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
