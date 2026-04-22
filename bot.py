import logging, sqlite3, os, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
OWNER_ID = 7361338806 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

# РЕЕСТР ПРАВ (0: Все, 1: Мл, 2: Ср, 3: Ст, 100: Создатель)
cmd_perms = {
    "кара": 3, "гив": 3, "эволюция": 100, "деэволюция": 3,
    "пвп": 0, "лотерея": 0, "деп": 0, "ми": 0, "профиль": 0, "ю*": 0,
    "сильнейшие": 0, "активчики": 0, "*передать": 0, ".пд": 100, "/help": 0
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
                admin_rank INTEGER DEFAULT 0, loss_streak INTEGER DEFAULT 0, 
                spins_since_win INTEGER DEFAULT 0
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

def get_admin_rank_name(lvl):
    return {0: "Участник", 1: "Младший админ", 2: "Средний админ", 3: "Старший админ", 100: "Создатель"}.get(lvl, "Неизвестно")

def get_evo_status(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 1000: return "Жук 🪲"
    return "Вазон 🪴"

async def get_user_rank(user_id):
    if user_id == OWNER_ID: return 100
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = ?", (user_id,))
    return res[0] if res else 0

# --- 1. АДМИН-ВЕТВЬ ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ('.пд', 'эволюция', 'гив', 'кара', 'деэволюция'))
async def admin_branch(m: types.Message):
    args = m.text.lower().split()
    cmd = args[0]
    u_rank = await get_user_rank(m.from_user.id)
    
    if u_rank < cmd_perms.get(cmd, 3): return

    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(target)

    if cmd == 'кара' and m.reply_to_message:
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID: return
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        if amt:
            db.execute("UPDATE users SET power_points = MAX(0, power_points - ?) WHERE user_id = ?", (amt, target.id))
            await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
        else:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = ?", (target.id,))
            await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b>\nМощь {target.first_name} обнулена.")

    elif cmd == 'гив' and m.reply_to_message:
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
        await m.answer(f"🔱 {get_mention(target.id, target.first_name)} даровано <code>{amt}</code> 💠")

    elif cmd == 'эволюция' and m.reply_to_message:
        lvl = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        db.execute("UPDATE users SET admin_rank = ? WHERE user_id = ?", (lvl, target.id))
        await m.answer(f"🌟 Ранг {target.first_name} изменен на: <b>{get_admin_rank_name(lvl)}</b>")

# --- 2. ЛОТЕРЕЯ (OLD DESIGN) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ('лотерея', 'деп'))
async def game_loto(m: types.Message):
    check_user(m.from_user)
    try:
        args = m.text.split()
        bet = int(args[1]) if len(args) > 1 else 50
        data = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if data[0] < bet or bet < 1: return await m.reply("❌ Недостаточно мощи!")

        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        res_m = 0; curr = 0; rand = random.uniform(0, sum(w.values()))
        for m_v, weight in w.items():
            curr += weight
            if rand <= curr: res_m = m_v; break
            
        new_bal = data[0] + (bet * res_m) - bet
        db.execute("UPDATE users SET power_points = ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (new_bal, (data[1]+1 if res_m==0 else 0), (data[2]+1 if res_m<=1 else 0), m.from_user.id))
        
        icon = {100: "💰", 0: "🔴", 1: "🟡"}.get(res_m, "🟢")
        status = "ДЖЕКПОТ" if res_m == 100 else "ВЫИГРЫШ" if res_m > 1 else "ПРОИГРЫШ" if res_m == 0 else "ПРИ СВОИХ"
        
        await m.answer(f"{icon} <b>{status} x{res_m}</b>\n━━━━━━━━━━━━━━\n💸 Ставка: <code>{bet}</code>\n💎 Итог: <code>{bet*res_m}</code>\n💰 Баланс: <code>{new_bal}</code> 💠")
    except: pass

# --- 3. ПРОФИЛЬ (ю*, ми, профиль) ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def info_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = ?", (t.id,))
    await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n🎖 <b>Ранг:</b> <i>{get_admin_rank_name(u[2])}</i>\n🧬 <b>Статус эв.:</b> <code>{get_evo_status(u[1])}</code>\n⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━")

# --- 4. ПЕРЕДАЧА (*передать) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def cmd_transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
        if bal >= amt > 0:
            db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
            await m.answer(f"🤝 <b>СДЕЛКА:</b>\n{get_mention(uid, m.from_user.first_name)} ➔ <code>{amt}</code> 💠 ➔ {get_mention(tid, m.reply_to_message.from_user.first_name)}")
    except: pass

# --- 5. ТОПЫ И СЕРВИС ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['сильнейшие', 'активчики'])
async def cmd_tops(m: types.Message):
    is_p = "сильнейшие" in m.text.lower()
    col = "power_points" if is_p else "msg_count"
    users = db.fetchall(f"SELECT user_id, username, {col} FROM users ORDER BY {col} DESC LIMIT 10")
    res = f"🏆 <b>{'СИЛЬНЕЙШИЕ' if is_p else 'АКТИВЧИКИ'}:</b>\n\n"
    for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code>\n"
    await m.answer(res)

@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
               
