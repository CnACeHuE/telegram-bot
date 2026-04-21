import logging
import sqlite3
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Пытаемся импортировать драйвер для облачной базы
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL') # Ссылка из настроек Railway Postgres
ADMIN_ID = 7361338806 
ALLOWED_CHATS = [-1002408347623, -1003761187223] 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- УНИВЕРСАЛЬНЫЙ КОННЕКТОР ---
class Database:
    def __init__(self):
        self.is_pg = DATABASE_URL is not None and psycopg2 is not None
        self.connect()

    def connect(self):
        if self.is_pg:
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else:
            self.conn = sqlite3.connect("abode_gods.db", check_same_thread=False)
        self.cursor = self.conn.cursor()

    def execute(self, sql, params=()):
        # Заменяем ? на %s если работаем с Postgres
        if self.is_pg:
            sql = sql.replace('?', '%s')
        try:
            self.cursor.execute(sql, params)
            if "SELECT" in sql.upper():
                return self.cursor.fetchone()
            self.conn.commit()
        except Exception as e:
            logging.error(f"DB Error: {e}")
            self.connect() # Переподключаемся при ошибке

db = Database()

# Создаем таблицу
db.execute("""CREATE TABLE IF NOT EXISTS users 
              (user_id BIGINT PRIMARY KEY, username TEXT, 
               power_points INTEGER DEFAULT 0, msg_count INTEGER DEFAULT 0,
               role TEXT DEFAULT 'player')""")

def check_user(user_id, username):
    if db.is_pg:
        db.execute("INSERT INTO users (user_id, username, power_points) VALUES (?, ?, 0) ON CONFLICT (user_id) DO NOTHING", (user_id, username))
    else:
        db.execute("INSERT OR IGNORE INTO users (user_id, username, power_points) VALUES (?, ?, 0)", (user_id, username))

def get_rank(msgs):
    ranks = [(10000, "Лорд 👑"), (5000, "Золотая черепаха 🐢"), (3000, "Синий бафф 🟦"),
             (2000, "Красный бафф 🟥"), (1500, "Динозаврик 🦖"), (1000, "Жук 🪲"),
             (600, "Лесной медведь 🐻"), (300, "Краб 🦀")]
    for limit, title in ranks:
        if msgs >= limit: return title
    return "Вазон 🪴"

async def check_access(message: types.Message):
    if message.chat.type == 'private':
        return message.from_user.id == ADMIN_ID
    return message.chat.id in ALLOWED_CHATS

# --- ЛОТЕРЕЯ (деп) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith(('лотерея', 'деп')) or m.text.lower().startswith('/lottery')))
async def lottery_handler(message: types.Message):
    if not await check_access(message): return
    uid = message.from_user.id
    check_user(uid, message.from_user.username)
    
    args = message.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    if bet < 10: return
    
    res = db.execute("SELECT power_points FROM users WHERE user_id = ?", (uid,))
    balance = res[0] if res else 0

    if balance < bet: 
        return await message.reply(f"Недостаточно сил! Твой баланс: {balance} 💠")

    db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, uid))
    
    r = random.random() * 100
    if r < 0.2: mult = 100
    elif r < 0.7: mult = 50
    elif r < 2.2: mult = 10
    elif r < 10.2: mult = 5
    elif r < 30.2: mult = 2
    elif r < 65.2: mult = 1
    else: mult = 0
    
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, uid))
    
    if mult >= 50: txt = f"🎰 ДЖЕКПОТ! x{mult}\n💰 Выигрыш: {win} 💠"
    elif mult > 1: txt = f"🎰 Крупная удача! x{mult}\n💎 Забрал: {win} 💠"
    elif mult == 1: txt = f"🎰 Возврат! x{mult}\n💠 Твои {win} 💠 при тебе."
    else: txt = f"🎰 Мимо! x0\n💀 Ставка {bet} 💠 ушла в эфир."
    await message.reply(txt)

# --- АДМИНКА ---
@dp.message_handler(lambda m: m.text and any(m.text.lower().startswith(x) for x in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def admin_handler(message: types.Message):
    res = db.execute("SELECT role FROM users WHERE user_id = ?", (message.from_user.id,))
    is_admin = (message.from_user.id == ADMIN_ID) or (res and res[0] == 'admin')
    if not is_admin or not message.reply_to_message: return
    
    text = message.text.lower()
    tid = message.reply_to_message.from_user.id
    tname = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"
    
    if message.from_user.id == ADMIN_ID:
        if text.startswith("божество+"):
            db.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (tid,))
            return await message.answer(f"⚡️ {tname} возведен в ранг Божества!")
        elif text.startswith("божество-"):
            db.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (tid,))
            return await message.answer(f"☁️ {tname} лишен божественных сил.")

    try:
        val = int(text.split()[1])
        if text.startswith(("гив", "награда")):
            db.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, tid))
            await message.answer(f"✨ Милость Властителя: {tname} +{val} 💠")
        elif text.startswith(("кара", "зб")):
            db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, tid))
            await message.answer(f"🔥 Гнев Властителя: {tname} -{val} 💠")
    except: pass

# --- ПРОФИЛЬ И ПЕРЕДАЧА ---
@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith(('ю*', '/you', '/me'))))
async def profile_handler(message: types.Message):
    if not await check_access(message): return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    check_user(target.id, target.username)
    res = db.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    await message.answer(f"👤 {target.full_name}\n💠 Очки силы: {res[0]}\n📈 Ранг: {get_rank(res[1])}\n💬 Активность: {res[1]} сообщ.")

@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def counter(message: types.Message):
    if not await check_access(message): return
    check_user(message.from_user.id, message.from_user.username)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (message.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
