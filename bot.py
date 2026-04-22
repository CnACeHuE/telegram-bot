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
    "сильнейшие": 0, "активчики": 0, "*передать": 0, ".пд": 100, "help": 0, ".сбор": 100
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
    current = "Вазон 🪴"
    for threshold, name in EVO_MAP.items():
        if msgs >= threshold: current = name
    return current

async def get_user_rank(user_id):
    if user_id == OWNER_ID: return 100
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = ?", (user_id,))
    return res[0] if res else 0

# --- 1. АДМИНИСТРИРОВАНИЕ ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['.пд', 'кара', 'гив', 'эволюция'])
async def admin_commands(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    u_rank = await get_user_rank(m.from_user.id)
    
    if u_rank < cmd_perms.get(cmd, 3): return

    if cmd == '.пд' and len(txt) == 3:
        cmd_perms[txt[1]] = int(txt[2])
        return await m.answer(f"⚙️ Система: Команда <code>{txt[1]}</code> теперь для ранга {txt[2]}")

    if not m.reply_to_message: return
    target = m.reply_to_message.from_user
    check_user(target)

    if cmd == 'кара':
        if target.id == OWNER_ID and m.from_user.id != OWNER_ID: return
        amt = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else None
        if amt:
            db.execute("UPDATE users SET power_points = MAX(0, power_points - ?) WHERE user_id = ?", (amt, target.id))
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
            await m.answer(f"🌟 Ранг {target.first_name} изменен на: <b>{get_admin_rank_name(lvl)}</b>")

# --- 2. ИГРЫ И ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['пвп', 'лотерея', 'деп'])
async def game_commands(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    check_user(m.from_user)
    
    if cmd == 'пвп':
        if not m.reply_to_message: return
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        if uid == tid: return
        
        b1 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,)) or (0,))[0]
        b2 = (db.execute("SELECT power_points FROM users WHERE user_id = ?", (tid,)) or (0,))[0]
        
        if b1 < bet: return await m.reply("❌ <b>У тебя</b> недостаточно мощи!")
        if b2 < bet: return await m.reply("❌ <b>У оппонента</b> недостаточно мощи!")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ", callback_data=f"pvp_{uid}_{bet}"))
        await m.answer(f"⚔️ {m.from_user.first_name} вызывает {m.reply_to_message.from_user.first_name} на <b>{bet}</b> 💠", reply_markup=kb)

    elif cmd in ['лотерея', 'деп']:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        u = db.execute("SELECT power_points, loss_streak, spins_since_win FROM users WHERE user_id = ?", (m.from_user.id,))
        if u[0] < bet or bet < 1: return await m.reply("❌ Недостаточно мощи!")
        
        w = {0: 40, 1: 30, 2: 18, 3: 8, 4: 3, 5: 1, 100: 0.02}
        res_m, curr, rand = 0, 0, random.uniform(0, sum(w.values()))
        for m_v, weight in w.items():
            curr += weight
            if rand <= curr: res_m = m_v; break
            
        new_bal = u[0] + (bet * res_m) - bet
        db.execute("UPDATE users SET power_points = ?, loss_streak = ?, spins_since_win = ? WHERE user_id = ?", 
                   (new_bal, (u[1]+1 if res_m==0 else 0), (u[2]+1 if res_m<=1 else 0), m.from_user.id))
        
        icon = {100: "💰", 0: "🔴", 1: "🟡"}.get(res_m, "🟢")
        status = "ДЖЕКПОТ" if res_m == 100 else "ВЫИГРЫШ" if res_m > 1 else "ПРОИГРЫШ"
        await m.answer(f"{icon} <b>{status} x{res_m}</b>\n━━━━━━━━━━━━━━\n💸 Ставка: <code>{bet}</code>\n💎 Итог: <code>{bet*res_m}</code>\n💰 Баланс: <code>{new_bal}</code> 💠")

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    win = random.choice([ch_id, c.from_user.id]); lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, lose))
    await c.message.edit_text(f"🏆 Победил <b>{(await bot.get_chat_member(c.message.chat.id, win)).user.first_name}</b>! (+{bet} 💠)")

# --- 3. ИНФО-ВЕТВЬ (Ми, Помощь, Сделки) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().split()[0] in ['ми', 'профиль', 'ю*', 'help', '/help', 'сильнейшие', 'активчики', '*передать', '.сбор']))
async def info_commands(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    
    if cmd == '.сбор' and m.from_user.id == OWNER_ID:
        all_u = db.fetchall("SELECT user_id FROM users")
        stich = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in all_u])
        return await m.answer(f"🔔 <b>ПРИЗЫВ ОБИТЕЛИ!</b>{stich}")

    if cmd in ['ми', 'профиль', 'ю*']:
        t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = ?", (t.id,))
        await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n🎖 <b>Ранг:</b> <i>{get_admin_rank_name(u[2])}</i>\n🧬 <b>Статус эв.:</b> <code>{get_evo_status(u[1])}</code>\n⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━")

    elif cmd == '*передать' and m.reply_to_message:
        try:
            amt = int(txt[1]); uid, tid = m.from_user.id, m.reply_to_message.from_user.id
            bal = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))[0]
            if bal >= amt > 0:
                db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
                db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amt, tid))
                await m.answer(f"🤝 <b>СДЕЛКА:</b>\n{get_mention(uid, m.from_user.first_name)} ➔ <code>{amt}</code> 💠 ➔ {get_mention(tid, m.reply_to_message.from_user.first_name)}")
        except: pass

    elif cmd in ['help', '/help']:
        r = await get_user_rank(m.from_user.id)
        msg = "📖 <b>БИБЛИОТЕКА ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n🎮 <b>Игры:</b>\n— <code>лотерея [сумма]</code>\n— <code>пвп [сумма]</code>\n— <code>*передать [сумма]</code>\n— <code>ми / профиль / ю*</code>\n\n"
        if r >= 1:
            msg += f"🛠 <b>Админ (Ранг {r}):</b>\n— <code>сильнейшие / активчики</code>\n"
            if r >= 3: msg += "— <code>кара [сумма]</code>\n— <code>гив [сумма]</code>\n"
        if r == 100: msg += "\n👑 <b>Создатель:</b>\n— <code>эволюция [1-3]</code>\n— <code>.пд [ком] [ранг]</code>\n— <code>.сбор</code>"
        await m.answer(msg + "\n━━━━━━━━━━━━━━")

    elif cmd in ['сильнейшие', 'активчики']:
        is_p = cmd == 'сильнейшие'
        users = db.fetchall(f"SELECT user_id, username, {'power_points' if is_p else 'msg_count'} FROM users ORDER BY 3 DESC LIMIT 10")
        res = f"🏆 <b>{'СИЛЬНЕЙШИЕ' if is_p else 'АКТИВЧИКИ'}:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code>\n"
        await m.answer(res)

# --- 4. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    check_user(m.from_user)
    u = db.execute("SELECT msg_count FROM users WHERE user_id = ?", (m.from_user.id,))
    old, new = u[0], u[0] + 1
    db.execute("UPDATE users SET msg_count = ? WHERE user_id = ?", (new, m.from_user.id))
    for threshold, name in EVO_MAP.items():
        if old < threshold <= new:
            await m.answer(f"🎊 <b>ЭВОЛЮЦИЯ!</b>\nГерой {get_mention(m.from_user.id, m.from_user.first_name)} достиг стадии: <b>{name}</b>! ✨")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
