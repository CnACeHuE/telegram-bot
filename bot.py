import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
OWNER_ID = 7361338806 
BOT_TAG = "@Testaotgvv_bot"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

# РЕЕСТР ПРАВ
cmd_perms = {
    "кара": 3, "гив": 3, "эволюция": 100, ".пд": 100, ".сбор": 100,
    "пвп": 0, "лотерея": 0, "деп": 0, "ми": 0, "профиль": 0, "ю*": 0,
    "сильнейшие": 0, "активчики": 0, "*передать": 0, "help": 0
}

EVO_MAP = {
    300: "Краб 🦀", 600: "Лесной медведь 🐻", 1000: "Жук 🪲", 
    1500: "Динозаврик 🦖", 2000: "Красный бафф 🟥", 3000: "Синий бафф 🟦",
    5000: "Золотая черепаха 🐢", 10000: "Лорд 👑"
}

# --- БАЗА ДАННЫХ ---
class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None and "postgresql" in DATABASE_URL
        self.connect()
        self.init_db()

    def connect(self):
        if self.is_pg:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else:
            self.conn = sqlite3.connect("abode_gods.db", check_same_thread=False)
        self.cursor = self.conn.cursor()

    def init_db(self):
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, username TEXT, 
                power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0, 
                admin_rank INTEGER DEFAULT 0
            )
        """)

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

# --- ВСПОМОГАТЕЛЬНОЕ ---
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

async def get_user_rank(user_id):
    if user_id == OWNER_ID: return 100
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = ?", (user_id,))
    return res[0] if res else 0

def get_evo_status(msgs):
    current = "Вазон 🪴"
    for threshold, name in EVO_MAP.items():
        if msgs >= threshold: current = name
    return current

# --- 1. ВЫСШИЕ КОМАНДЫ (Кара, Гив, ПД) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'кара', 'гив', 'эволюция')))
async def boss_commands(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    u_rank = await get_user_rank(m.from_user.id)
    
    if u_rank < cmd_perms.get(cmd, 3): return

    if cmd == '.пд' and len(txt) == 3:
        cmd_perms[txt[1]] = int(txt[2])
        return await m.answer(f"⚙️ <b>Правки внесены:</b> <code>{txt[1]}</code> -> {txt[2]} ранг")

    if not m.reply_to_message: return
    target = m.reply_to_message.from_user
    check_user(target)

    if cmd == 'кара':
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID: return
        amt = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else None
        if amt:
            # Логика для SQLite (MAX) или ручной расчет баланса
            curr_p = db.execute("SELECT power_points FROM users WHERE user_id = ?", (target.id,))[0]
            new_p = max(0, curr_p - amt)
            db.execute("UPDATE users SET power_points = ? WHERE user_id = ?", (new_p, target.id))
            await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
        else:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = ?", (target.id,))
            await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b>\nМощь {target.first_name} обнулена.")

    elif cmd == 'гив':
        if len(txt) > 1 and txt[1].isdigit():
            amt = int(txt[1])
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} даровано <code>{amt}</code> 💠")

    elif cmd == 'эволюция':
        if len(txt) > 1 and txt[1].isdigit():
            lvl = int(txt[1])
            db.execute("UPDATE users SET admin_rank = ? WHERE user_id = ?", (lvl, target.id))
            await m.answer(f"🌟 Ранг {target.first_name} теперь: <b>{lvl}</b>")

# --- 2. ИГРЫ (ПВП, Лотерея) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['пвп', 'лотерея', 'деп'])
async def games_block(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    check_user(m.from_user)
    
    if cmd == 'пвп' and m.reply_to_message:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        b1 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        b2 = db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,))[0]
        if b1 < bet: return await m.reply("❌ <b>У тебя</b> мало мощи!")
        if b2 < bet: return await m.reply("❌ <b>У оппонента</b> мало сил!")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ", callback_data=f"pvp_{uid}_{bet}"))
        await m.answer(f"⚔️ {m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name} на <b>{bet}</b> 💠", reply_markup=kb)

    elif cmd in ['лотерея', 'деп']:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        u = db.execute("SELECT power_points FROM users WHERE user_id = ?", (m.from_user.id,))
        if u[0] < bet or bet < 1: return await m.reply("❌ Недостаточно мощи!")
        res = random.choices([0, 1, 2, 3, 5, 100], weights=[40, 30, 18, 8, 3.98, 0.02])[0]
        new_bal = u[0] + (bet * res) - bet
        db.execute("UPDATE users SET power_points = ? WHERE user_id = ?", (new_bal, m.from_user.id))
        status = "ДЖЕКПОТ" if res == 100 else "ВЫИГРЫШ" if res > 1 else "ПРОИГРЫШ"
        await m.answer(f"{'💰' if res>1 else '🔴'} <b>{status} x{res}</b>\n💰 Баланс: <code>{new_bal}</code> 💠")

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_run(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    await c.message.edit_text(f"🏆 Победил <b>{(await bot.get_chat_member(c.message.chat.id, win)).user.first_name}</b>! (+{bet} 💠)")

# --- 3. ИНФО (Свиток, Помощь, Топы) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().split()[0] in ['ми', 'профиль', 'ю*', 'help', '/help', '/help@testaotgvv_bot', 'сильнейшие', 'активчики', '*передать', '.сбор']))
async def info_block(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]

    if cmd in ['ми', 'профиль', 'ю*']:
        t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = ?", (t.id,))
        ranks = {0: "Участник", 1: "Мл. Админ", 2: "Ср. Админ", 3: "Ст. Админ", 100: "Создатель"}
        await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n🎖 <b>Ранг:</b> <i>{ranks.get(u[2], '???')}</i>\n🧬 <b>Статус эв.:</b> <code>{get_evo_status(u[1])}</code>\n⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━")

    elif cmd in ['help', '/help', '/help@testaotgvv_bot']:
        r = await get_user_rank(m.from_user.id)
        msg = "📖 <b>БИБЛИОТЕКА</b>\n━━━━━━━━━━━━━━\n🎮 <b>Игры:</b>\n— <code>лотерея / пвп / *передать</code>\n— <code>ми / профиль / ю*</code>\n\n"
        if r >= 1: msg += f"🛠 <b>Админ:</b>\n— <code>сильнейшие / активчики</code>\n"
        if r >= 3: msg += "— <code>кара [реплей] / гив [реплей]</code>\n"
        if r == 100: msg += "\n👑 <b>Создатель:</b>\n— <code>эволюция / .пд / .сбор</code>"
        await m.answer(msg + "\n━━━━━━━━━━━━━━")

    elif cmd == '*передать' and m.reply_to_message:
        try:
            amt = int(txt[1]); uid, tid = m.from_user.id, m.reply_to_message.from_user.id
            bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
            if bal >= amt > 0:
                db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
                db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
                await m.answer(f"🤝 <b>СДЕЛКА:</b> {m.from_user.first_name} ➔ {amt} 💠")
        except: pass

    elif cmd in ['сильнейшие', 'активчики']:
        col = "power_points" if cmd == "сильнейшие" else "msg_count"
        users = db.fetchall(f"SELECT user_id, username, {col} FROM users ORDER BY 3 DESC LIMIT 10")
        res = f"🏆 <b>{'ТОП МОЩИ' if col == 'power_points' else 'ТОП АКТИВА'}:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code>\n"
        await m.answer(res)

    elif cmd == '.сбор' and m.from_user.id == OWNER_ID:
        all_u = db.fetchall("SELECT user_id FROM users")
        stich = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in all_u])
        await m.answer(f"🔔 <b>ПРИЗЫВ ОБИТЕЛИ!</b>{stich}")

# --- 4. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК (Опыт и Эволюция) ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    check_user(m.from_user)
    # Игнорируем команды для начисления опыта (опционально, но лучше оставить для честности)
    if m.text.startswith(('/', '.', 'кара', 'гив', 'пвп', 'лотерея', 'деп')): return

    u = db.execute("SELECT msg_count FROM users WHERE user_id = ?", (m.from_user.id,))
    old, new = u[0], u[0] + 1
    db.execute("UPDATE users SET msg_count = ? WHERE user_id = ?", (new, m.from_user.id))
    
    for threshold, name in EVO_MAP.items():
        if old < threshold <= new:
            await m.answer(f"🎊 <b>ЭВОЛЮЦИЯ!</b>\nГерой {get_mention(m.from_user.id, m.from_user.first_name)} достиг стадии: <b>{name}</b>! ✨")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
