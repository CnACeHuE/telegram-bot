import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 

# ССЫЛКИ НА КАРТИНКИ (Замени на свои, если эти перестанут работать)
PHOTOS = {
    "main": "https://i.postimg.cc/90pX7pLz/main.jpg",
    "gear": "https://i.postimg.cc/85zX3S0r/gear.jpg",
    "magic": "https://i.postimg.cc/3R6M3yv1/magic.jpg",
    "power": "https://i.postimg.cc/vHzZfN3F/power.jpg"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ (Postgres/SQLite) ---
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

def check_user(uid, name):
    name = name or "Путник"
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (uid, name, name))

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

# --- ИНТЕРФЕЙС МАГАЗИНА ---
ITEM_NAMES = {"thief": "🗡 Вор", "altar": "🕯 Алтарь", "mirror": "🔮 Зеркало", "echo": "🌌 Эхо", "curse": "🌫 Нищета", "mute": "🔇 Мут", "prefix": "👑 Префикс"}
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "role": 700, "mute": 200, "prefix": 55555}

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

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message_handler(lambda m: "магазин" in m.text.lower())
async def cmd_shop(m: types.Message):
    await m.answer_photo(PHOTOS["main"], caption="╔════════════════╗\n     🏛 **СОКРОВИЩНИЦА** \n╚════════════════╝\n\nПутник, здесь ты можешь обменять накопленную силу на редкие артефакты.", reply_markup=get_shop_kb("main"), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_callback(c: types.CallbackQuery):
    action, val = c.data.split('_')
    uid = c.from_user.id
    check_user(uid, c.from_user.username)

    if action == "shop":
        cap = f"╔════════════════╗\n     ✨ **{val.upper()}** \n╚════════════════╝\n\nВыбирай с умом..."
        await c.message.edit_media(InputMediaPhoto(PHOTOS.get(val, PHOTOS["main"]), caption=cap, parse_mode="Markdown"), reply_markup=get_shop_kb(val))
    
    elif action == "buy":
        price = PRICES.get(val, 99999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Твоей веры и силы недостаточно!", show_alert=True)
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
        await c.answer(f"✅ Приобретено: {ITEM_NAMES.get(val, val)}", show_alert=True)

@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith('ю*')))
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t.id, t.username)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    rank = get_rank(u[1]) if u[2] != 'admin' else "Божество 🔱"
    items = ", ".join([f"{ITEM_NAMES.get(i[0], i[0])}({i[1]})" for i in inv]) if inv else "Пусто"
    
    res = (f"┏━━━━━━━━━━━━━━━━━━┓\n"
           f"   👤 **{t.full_name}**\n"
           f"┗━━━━━━━━━━━━━━━━━━┛\n"
           f"🎖 **Ранг:** `{rank}`\n"
           f"💠 **Сила:** `{u[0]}`\n"
           f"💬 **Опыт:** `{u[1]}`\n"
           f"🎒 **Сумка:** _{items}_")
    await m.answer(res, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение получателя!")
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    try:
        amt = int(m.text.split()[1])
        if amt <= 0: return
        check_user(uid, m.from_user.username); check_user(tid, m.reply_to_message.from_user.username)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ У тебя нет столько силы!")
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **ПЕРЕДАЧА СИЛЫ**\n\nИгрок @{m.from_user.username} пожертвовал `{amt}` 💠 в пользу @{m.reply_to_message.from_user.username}!")
    except: await m.reply("Используй: `передать [число]`")

@dp.message_handler(lambda m: m.text.lower().startswith('пвп'))
async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Вызови противника через ответ на сообщение!")
    u1, u2 = m.from_user.id, m.reply_to_message.from_user.id
    if u1 == u2: return
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        check_user(u1, m.from_user.username); check_user(u2, m.reply_to_message.from_user.username)
        b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (u1,))[0]
        b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (u2,))[0]
        if b1 < bet or b2 < bet: return await m.reply("❌ У кого-то из вас не хватает сил для ставки!")

        win = random.choice([u1, u2])
        lose = u2 if win == u1 else u1
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
        
        w_name = m.from_user.first_name if win == u1 else m.reply_to_message.from_user.first_name
        await m.answer(f"⚔️ **АРЕНА БОГОВ**\n\nВ жестокой битве на `{bet}` 💠 победу одержал **{w_name}**! Слава чемпиону!")
    except: pass

@dp.message_handler(lambda m: m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    uid = m.from_user.id
    check_user(uid, m.from_user.username)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < bet: return await m.reply("❌ Недостаточно сил!")
        
        chance = random.random()
        if chance < 0.05: mult, msg = 10, "🎰 **О БОГИ! ДЖЕКПОТ x10!** 🔥"
        elif chance < 0.15: mult, msg = 5, "💎 Невероятная удача! **x5**!"
        elif chance < 0.30: mult, msg = 3, "✨ Магический резонанс! **x3**!"
        elif chance < 0.55: mult, msg = 2, "✅ Успех! **x2**."
        elif chance < 0.75: mult, msg = 1, "🌀 Пустота. Ставка возвращена."
        else: mult, msg = 0, "💀 Тьма поглотила твою силу. **x0**."
        
        db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, uid))
        await m.answer(f"🎰 **ЛОТЕРЕЯ ОБИТЕЛИ**\n\n{msg}\nСтавка: `{bet}` | Итог: `{bet*mult}` 💠")
    except: pass

@dp.message_handler(lambda m: any(x in m.text.lower() for x in ["божество+", "божество-", "гив"]))
async def admin_tools(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    if not m.reply_to_message: return
    tid = m.reply_to_message.from_user.id
    if "божество+" in m.text.lower():
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer("⚡️ Путник вознесен в ранг **Божества**!")
    elif "божество-" in m.text.lower():
        db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (tid,))
        await m.answer("🌑 Божественная искра отозвана.")
    elif "гив" in m.text.lower():
        amt = int(m.text.split()[1])
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🔱 **ДАР БОГОВ:** `{amt}` 💠 даровано пользователю!")

@dp.message_handler(content_types=['text'])
async def counter(m: types.Message):
    check_user(m.from_user.id, m.from_user.username)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
