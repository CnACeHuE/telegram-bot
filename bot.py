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

# РЕЕСТР КОМАНД И РАНГОВ (Ветви)
# 0: Все, 1: Мл, 2: Ср, 3: Ст, 100: Создатель
cmd_perms = {
    "кара": 3,
    "гив": 3,
    "эволюция": 100,
    "деэволюция": 3,
    "пвп": 0,
    "лотерея": 0,
    "деп": 0,
    "ми": 0,
    "профиль": 0,
    "сильнейшие": 0,
    "активчики": 0,
    ".пд": 100
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
        # Создаем таблицу сразу со всеми полями, чтобы избежать ошибок ALTER TABLE
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, 
                username TEXT, 
                power_points INTEGER DEFAULT 100, 
                msg_count INTEGER DEFAULT 0, 
                admin_rank INTEGER DEFAULT 0,
                loss_streak INTEGER DEFAULT 0, 
                spins_since_win INTEGER DEFAULT 0
            )
        """)

    def execute(self, sql, params=()):
        if self.is_pg: sql = sql.replace('?', '%s')
        try:
            self.cursor.execute(sql, params)
            if "SELECT" in sql.upper(): return self.cursor.fetchone()
            self.conn.commit()
        except Exception as e:
            logging.error(f"DB Error: {e}")
            self.connect()
            return self.execute(sql, params)

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

def get_rank_name(lvl):
    return {0: "Обычный", 1: "Младший админ", 2: "Средний админ", 3: "Старший админ", 100: "Создатель"}.get(lvl, "Неизвестно")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ПРАВ ---
async def has_access(user_id, cmd_name):
    if user_id == OWNER_ID: return True
    user_data = db.execute("SELECT admin_rank FROM users WHERE user_id = ?", (user_id,))
    u_rank = user_data[0] if user_data else 0
    req_rank = cmd_perms.get(cmd_name.lower(), 0)
    return u_rank >= req_rank

# --- 1. АДМИН-ЛОГИКА (ВЕТВЬ УПРАВЛЕНИЯ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'эволюция', 'гив', 'кара', 'деэволюция')))
async def admin_branch(m: types.Message):
    args = m.text.lower().split()
    cmd = args[0]
    
    if not await has_access(m.from_user.id, cmd):
        return await m.reply("⚠️ Твой статус эволюции слишком мал.")

    # Динамическая настройка прав
    if cmd == '.пд' and len(args) == 3:
        target_cmd, target_rank = args[1], int(args[2])
        if target_cmd in cmd_perms:
            cmd_perms[target_cmd] = target_rank
            return await m.answer(f"⚙️ Система перенастроена: <b>{target_cmd}</b> теперь доступна рангу <b>{target_rank}+</b>")

    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(target)

    if cmd == 'эволюция' and m.reply_to_message:
        lvl = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        db.execute("UPDATE users SET admin_rank = ? WHERE user_id = ?", (min(lvl, 3), target.id))
        await m.answer(f"🌟 Герой {get_mention(target.id, target.first_name)} эволюционировал в <b>{get_rank_name(lvl)}</b> ✨")

    elif cmd == 'деэволюция' and m.reply_to_message:
        if target.id == OWNER_ID: return
        db.execute("UPDATE users SET admin_rank = 0 WHERE user_id = ?", (target.id,))
        await m.answer(f"☁️ {target.first_name} утратил статус эволюции.")

    elif cmd == 'кара' and m.reply_to_message:
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID: return await m.answer("🛡")
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        if amt:
            db.execute("UPDATE users SET power_points = CASE WHEN power_points - ? < 0 THEN 0 ELSE power_points - ? END WHERE user_id = ?", (amt, amt, target.id))
            await m.answer(f"🔥 Поражение на <code>{amt}</code> мощи!")
        else:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = ?", (target.id,))
            await m.answer("⚡️ Полное обнуление!")

    elif cmd == 'гив' and m.reply_to_message:
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, target.id))
        await m.answer(f"🔱 Даровано +<code>{amt}</code> мощи.")

# --- 2. ИГРОВАЯ ЛОГИКА ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def game_loto(m: types.Message):
    check_user(m.from_user)
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        if bet < 1 or bet > 500: return await m.reply("⚠️ Ставки 1-500")
        
        data = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if data[0] < bet: return await m.reply("❌ Недостаточно мощи!")

        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        if data[1] >= 3: w[0] -= 15; w[2] += 15
        
        res_m = 0; curr = 0; rand = random.uniform(0, sum(w.values()))
        for m_v, weight in w.items():
            curr += weight
            if rand <= curr: res_m = m_v; break
            
        new_bal = data[0] + (bet * res_m) - bet
        db.execute("UPDATE users SET power_points = ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (new_bal, (data[1]+1 if res_m==0 else 0), (data[2]+1 if res_m<=1 else 0), m.from_user.id))
        
        icon = "🔴" if res_m == 0 else "🟡" if res_m == 1 else "🟢" if res_m < 100 else "💰"
        await m.answer(f"{icon} <b>{'ПРОИГРЫШ' if res_m==0 else 'ВЫИГРЫШ'} x{res_m}</b>\n━━━━━━━━━━━━━━\n💸 Ставка: <code>{bet}</code>\n💎 Итог: <code>{bet*res_m}</code>\n💰 Баланс: <code>{new_bal}</code> 💠")
    except: pass

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def game_pvp(m: types.Message):
    if not m.reply_to_message: return
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        
        b1 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,)) or (0,))[0]
        b2 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,)) or (0,))[0]
        
        if b1 < bet or b2 < bet: return await m.reply("❌ Недостаточно мощи!")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ", callback_data=f"pvp_{uid}_{bet}"))
        await m.answer(f"⚔️ {m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name}!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    
    b1 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (ch_id,)) or (0,))[0]
    b2 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (c.from_user.id,)) or (0,))[0]
    
    if b1 < bet or b2 < bet: return await c.answer("❌ Бой невозможен", show_alert=True)
    
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    
    winner_name = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"🏆 Победил <b>{winner_name}</b>! (+{bet} 💠)")

# --- 3. ИНФО-БЛОК ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль'])
async def info_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = ?", (t.id,))
    
    def get_msg_rank(msgs):
        if msgs >= 10000: return "Лорд 👑"
        if msgs >= 5000: return "Золотая черепаха 🐢"
        if msgs >= 1000: return "Жук 🪲"
        return "Вазон"

    await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n🎖 <b>Статус эв.:</b> <i>{get_rank_name(u[2])}</i>\n⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n📜 <b>Ранг:</b> <code>{get_msg_rank(u[1])}</code>\n━━━━━━━━━━━━━━")

@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
