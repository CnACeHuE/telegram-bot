
import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.dispatcher.filters import Text, Regexp

# --- КОНФИГУРАЦИЯ ---
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
db.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0, role TEXT DEFAULT 'player', married_to BIGINT DEFAULT 0)")
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

# --- ИНТЕРФЕЙС МАГАЗИНА ---
ITEM_NAMES = {"thief": "🗡 Вор", "altar": "🕯 Алтарь", "mirror": "🔮 Зеркало", "echo": "🌌 Эхо", "curse": "🌫 Нищета", "mute": "🔇 Мут", "prefix": "👑 Префикс"}
PRICES = {"thief": 250, "altar": 500, "mirror": 300, "echo": 150, "curse": 400, "clean": 1000, "mute": 200, "prefix": 55555}

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

# --- ОБРАБОТЧИКИ (МАГАЗИН) ---

@dp.message_handler(Text(contains="магазин", ignore_case=True))
@dp.message_handler(commands=['shop'])
async def open_shop(m: types.Message):
    check_user(m.from_user)
    await m.answer_photo(PHOTOS["main"], caption="╔════════════════╗\n     🟢 **МАРКЕТ ОБИТЕЛИ** \n╚════════════════╝\n\nЗдесь твоя сила превращается в возможности. Выбери раздел:", reply_markup=get_shop_kb("main"))

@dp.callback_query_handler(lambda c: c.data.startswith(('shop_', 'buy_')))
async def shop_callback(c: types.CallbackQuery):
    action, val = c.data.split('_')
    if action == "shop":
        cap = f"✨ **РАЗДЕЛ: {val.upper()}**\n\nПриобретай мудро и осторожно..."
        try:
            await c.message.edit_media(InputMediaPhoto(PHOTOS.get(val, PHOTOS["main"]), caption=cap), reply_markup=get_shop_kb(val))
        except: await c.answer("Ошибка обновления")
    elif action == "buy":
        price = PRICES.get(val, 99999)
        uid = c.from_user.id
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal < price: return await c.answer("❌ Недостаточно силы!", show_alert=True)
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, uid))
        db.execute("INSERT INTO inventory (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = inventory.count + 1", (uid, val))
        await c.answer(f"✅ Успешно куплено: {ITEM_NAMES.get(val, val)}", show_alert=True)

# --- ПРОФИЛЬ ---

@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith('ю*')))
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, role, married_to FROM users WHERE user_id = ?", (t.id,))
    inv = db.fetchall("SELECT item_id, count FROM inventory WHERE user_id = ? AND count > 0", (t.id,))
    
    rank = u[2].upper() if u[2] == 'admin' else get_rank(u[1])
    items = ", ".join([f"{ITEM_NAMES.get(i[0], i[0])} ({i[1]})" for i in inv]) if inv else "Пусто"
    marry_status = ""
    if u[3] != 0:
        partner = db.execute("SELECT username FROM users WHERE user_id = ?", (u[3],))
        marry_status = f"\n💞 **В браке с:** {partner[0] if partner else 'Кем-то великим'}"

    res = (f"┏━━━━━━━━━━━━━━━━━━┓\n"
           f"   👤 **{t.full_name}**\n"
           f"┗━━━━━━━━━━━━━━━━━━┛\n"
           f"🎖 **Ранг:** `{rank}`\n"
           f"💠 **Сила:** `{u[0]}`\n"
           f"💬 **Опыт:** `{u[1]}`\n"
           f"🎒 **Сумка:** _{items}_{marry_status}")
    await m.answer(res, parse_mode="Markdown")

# --- ПЕРЕДАЧА И ПВП ---

@dp.message_handler(Regexp(r'^(передать)\s(\d+)'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение получателя!")
    amt = int(m.text.split()[1])
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    
    check_user(m.from_user); check_user(m.reply_to_message.from_user)
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    if bal < amt: return await m.reply("❌ Недостаточно сил!")
    
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
    await m.answer(f"🤝 **СДЕЛКА:** @{m.from_user.username} передал `{amt}` 💠 игроку @{m.reply_to_message.from_user.username}")

@dp.message_handler(Text(startswith="пвп", ignore_case=True))
async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение противника!")
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    
    check_user(m.from_user); check_user(m.reply_to_message.from_user)
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
    if b1 < bet or b2 < bet: return await m.reply("❌ Недостаточно сил!")

    win = random.choice([uid, tid])
    lose = tid if win == uid else uid
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    w_name = m.from_user.first_name if win == uid else m.reply_to_message.from_user.first_name
    await m.answer(f"⚔️ **АРЕНА:** Победил **{w_name}**! Забрал куш `{bet}` 💠")

# --- ЛОТЕРЕЯ ---

@dp.message_handler(Text(startswith=("лотерея", "деп"), ignore_case=True))
async def cmd_loto(m: types.Message):
    check_user(m.from_user)
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))[0]
    if bal < bet: return await m.reply("❌ Недостаточно сил!")
    
    r = random.random()
    mult = 10 if r < 0.05 else 5 if r < 0.15 else 3 if r < 0.3 else 2 if r < 0.55 else 1 if r < 0.75 else 0
    res_text = {10: "🎰 ДЖЕКПОТ x10!", 5: "💎 УДАЧА x5!", 3: "✨ МАГИЯ x3!", 2: "✅ УСПЕХ x2", 1: "🌀 ПУСТО x1", 0: "💀 ТЬМА x0"}[mult]
    
    db.execute("UPDATE users SET power_points = power_points - ? + ? WHERE user_id = ?", (bet, bet*mult, m.from_user.id))
    await m.answer(f"🎰 **ЛОТЕРЕЯ:** {res_text}\nИтог: `{bet*mult}` 💠")

# --- БРАКИ (НОВОЕ) ---

@dp.message_handler(commands=['marry'])
async def marry_user(m: types.Message):
    if not m.reply_to_message: return await m.reply("⚠️ Ответь на сообщение того, с кем хочешь создать союз!")
    uid, tid = m.from_user.id, m.reply_to_message.from_user.id
    if uid == tid: return
    check_user(m.from_user); check_user(m.reply_to_message.from_user)
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Согласен", callback_data=f"marry_yes_{uid}_{tid}"),
        InlineKeyboardButton("❌ Отказ", callback_data=f"marry_no")
    )
    await m.answer(f"💍 @{m.from_user.username} предлагает союз @{m.reply_to_message.from_user.username}!\nВы согласны?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('marry_'))
async def marry_callback(c: types.CallbackQuery):
    if c.data == "marry_no": return await c.message.edit_text("💔 В союзе отказано.")
    data = c.data.split('_')
    uid, tid = int(data[2]), int(data[3])
    if c.from_user.id != tid: return await c.answer("Это не вам!", show_alert=True)
    
    db.execute("UPDATE users SET married_to = ? WHERE user_id = ?", (tid, uid))
    db.execute("UPDATE users SET married_to = ? WHERE user_id = ?", (uid, tid))
    await c.message.edit_text(f"🎊 Поздравляем! Теперь вы связаны божественным союзом! 💍")

# --- АДМИН-ПАНЕЛЬ ---

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and any(x in m.text.lower() for x in ["божество+", "божество-", "гив"]))
async def admin_tools(m: types.Message):
    if not m.reply_to_message: return
    tid = m.reply_to_message.from_user.id
    if "божество+" in m.text.lower():
        db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
        await m.answer("⚡️ Возведен в ранг **Божества**!")
    elif "гив" in m.text.lower():
        amt = int(m.text.split()[1])
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
        await m.answer(f"🔱 Даровано `{amt}` 💠")

# --- СЧЕТЧИК (В САМОМ КОНЦЕ) ---
@dp.message_handler(content_types=['text'])
async def count_msgs(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
