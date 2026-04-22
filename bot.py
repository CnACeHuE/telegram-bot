import logging, sqlite3, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = 7361338806 

# Вставь сюда ссылки, когда загрузишь свои картинки. Сейчас тут заглушки.
PHOTOS = {
    "main": "https://example.com/main.jpg",
    "gear": "https://example.com/gear.jpg",
    "magic": "https://example.com/magic.jpg",
    "power": "https://example.com/power.jpg"
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

# --- ИНТЕРФЕЙСЫ ---
ITEM_NAMES = {"thief": "🗡 Вор", "altar": "🕯 Алтарь", "mirror": "🔮 Зеркало", "echo": "🌌 Эхо", "curse": "🌫 Нищета", "mute": "🔇 Мут", "prefix": "👑 Префикс"}
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "mute": 200, "prefix": 55555}

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

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    items = ", ".join([f"{ITEM_NAMES.get(i[0], i[0])} ({i[1]})" for i in inv]) if inv else "Пусто"
    await m.answer(f"💠 **ПРОФИЛЬ БОЖЕСТВА**\n──────────────\n👤 **Имя:** {t.full_name}\n🎖 **Ранг:** `{rank}`\n⚡️ **Сила:** `{u[0]}`\n💬 **Опыт:** `{u[1]}`\n🎒 **Сумка:** _{items}_", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text and "магазин" in m.text.lower())
async def cmd_shop(m: types.Message):
    check_user(m.from_user)
    cap = "🟢 **НЕОНОВЫЙ МАРКЕТ**\n\nВыбери отсек сокровищницы:"
    try:
        await m.answer_photo(PHOTOS["main"], caption=cap, reply_markup=get_shop_kb("main"))
    except:
        await m.answer(cap, reply_markup=get_shop_kb("main"))

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_callback(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        cap = f"✨ **КАТЕГОРИЯ: {val.upper()}**"
        try:
            await c.message.edit_media(InputMediaPhoto(PHOTOS.get(val, PHOTOS["main"]), caption=cap), reply_markup=get_shop_kb(val))
        except:
            await c.message.edit_text(cap, reply_markup=get_shop_kb(val))
    elif action == "buy":
        price = PRICES.get(val, 99999)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,))[0]
        if bal < price: return await c.answer("❌ Мало силы!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, c.from_user.id))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (c.from_user.id, val))
        await c.answer(f"✅ Получено: {ITEM_NAMES.get(val, val)}", show_alert=True)

# --- ТОП СИЛЬНЕЙШИХ ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith('/top') or "сильнейшие" in m.text.lower()))
async def cmd_top(m: types.Message):
    users = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
    res = "🏆 **СИЛЬНЕЙШИЕ В ОБИТЕЛИ**\n\n"
    for i, u in enumerate(users, 1):
        res += f"{i}. {u[0]} — `{u[1]}` 💠\n"
    await m.answer(res, parse_mode="Markdown")

# --- ПВП С КНОПКОЙ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_invite(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_acc_{uid}_{bet}"))
        await m.answer(f"👊 **ВЫЗОВ НА БОЙ!**\n\nИгрок {m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name} на битву!\n💰 Ставка: `{bet}` 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_acc'))
async def pvp_start(c: types.CallbackQuery):
    _, _, challenger_id, bet = c.data.split('_')
    challenger_id, bet = int(challenger_id), int(bet)
    defender_id = c.from_user.id
    
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (challenger_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (defender_id,))[0]
    
    if b1 < bet or b2 < bet: return await c.answer("❌ У кого-то не хватает сил!", show_alert=True)
    
    win = random.choice([challenger_id, defender_id])
    lose = defender_id if win == challenger_id else challenger_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    
    winner_name = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"⚔️ **ИТОГ БИТВЫ**\n\nВ кровавой схватке на `{bet}` 💠 победил **{winner_name}**! 🎉", reply_markup=None)

# --- ПЕРЕДАЧА ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение получателя!")
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        check_user(m.from_user); check_user(m.reply_to_message.from_user)
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < amt: return await m.reply("❌ Недостаточно силы!")
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🤝 **СДЕЛКА:** {m.from_user.first_name} ➔ `{amt}` 💠 ➔ {m.reply_to_message.from_user.first_name}")
    except: await m.reply("Пример: `передать 100` (через ответ)")

# --- ЛОТЕРЕЯ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
        if bal < bet: return await m.reply("❌ Мало силы!")
        r = random.random()
        mult = 10 if r < 0.05 else 5 if r < 0.15 else 3 if r < 0.3 else 2 if r < 0.55 else 1 if r < 0.75 else 0
        db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, m.from_user.id))
        await m.answer(f"🎰 **ЛОТЕРЕЯ:** Множитель **x{mult}**\nИтог: `{bet*mult}` 💠")
    except: pass

# --- СЧЕТЧИК ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
