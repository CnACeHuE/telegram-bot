import logging
import sqlite3
import os
import asyncio
import random
from datetime import datetime, time
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 12345678  # ВСТАВЬ СВОЙ ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("abode_final.db")
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, 
                   power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0,
                   role TEXT DEFAULT 'player', mutes_until INTEGER DEFAULT 0)""")
conn.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Странник 👤"

# --- КОМАНДЫ АДМИНИСТРАЦИИ (ГИВ, КАРА, БОЖЕСТВО+) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "пд", "награда", "зб", "кара", "божество+"]))
async def god_commands(message: types.Message):
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (message.from_user.id,))
    user_data = cursor.fetchone()
    is_god = (message.from_user.id == ADMIN_ID) or (user_data and user_data[0] == 'admin')
    
    if not is_god: return

    args = message.text.split()
    if not message.reply_to_message or len(args) < 2: return
    
    cmd = args[0].lower()
    amount = int(args[1]) if args[1].isdigit() else 0
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.full_name

    if cmd in ["гив", "пд", "награда"]:
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
        await message.answer(f"✨ Божественная щедрость! {target_name} +{amount} Очков силы.")
    elif cmd in ["зб", "кара"]:
        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
        await message.answer(f"🔥 Гнев Богов! {target_name} -{amount} Очков силы.")
    elif cmd == "божество+":
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {target_name} теперь Божество!")
    conn.commit()

# --- ЭКОНОМИКА И ПЕРЕДАЧА ---
@dp.message_handler(lambda m: m.text.startswith('*передать'))
async def transfer(message: types.Message):
    if not message.reply_to_message: return
    try:
        amount = int(message.text.split()[1])
    except: return

    sender_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (sender_id,))
    balance = cursor.fetchone()[0]
    
    if balance >= amount > 0:
        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, sender_id))
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        await message.answer(f"📦 Передача: {amount} 💠 от {message.from_user.first_name} к {message.reply_to_message.from_user.first_name}")

# --- ЛОТЕРЕЯ ---
@dp.message_handler(commands=['лотерея'])
async def lottery(message: types.Message):
    cost = 50
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < cost: return await message.reply("Нужно 50 💠 для участия!")

    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (cost, user_id))
    
    r = random.random() * 100
    mult = 0
    if r <= 0.05: mult = 100
    elif r <= 2.05: mult = 15
    elif r <= 10.05: mult = 6
    elif r <= 30.05: mult = 3
    elif r <= 70.05: mult = 1
    
    win = cost * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Результат: x{mult}! Ты получил {win} 💠")

# --- МАГАЗИН И МЕНЮ /me ---
@dp.message_handler(commands=['me'])
async def me(message: types.Message):
    cursor.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (message.from_user.id,))
    res = cursor.fetchone()
    if not res: return
    
    rank = get_rank(res[1])
    text = (f"👤 **{message.from_user.full_name}**\n"
            f"📈 Ранг: {rank}\n"
            f"💠 Очки силы: {res[0]}\n"
            f"💬 Сообщений: {res[1]}\n"
            f"🎭 Роль: {res[2]}")
    await message.answer(text)

# --- ЕЖЕДНЕВНЫЕ СОБЫТИЯ ---
async def daily_tasks():
    while True:
        now = datetime.now()
        # 12:00 МСК (если сервер UTC, то это 09:00)
        if now.hour == 9 and now.minute == 0:
            cursor.execute("UPDATE users SET power_points = power_points + 50 WHERE msg_count > 0")
            conn.commit()
            logging.info("Бонусы розданы.")
            await asyncio.sleep(60)
        await asyncio.sleep(30)

# --- ОСНОВНОЙ ОБРАБОТЧИК ---
@dp.message_handler()
async def handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    
    cursor.execute("SELECT msg_count FROM users WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    if count % 100 == 0:
        cursor.execute("UPDATE users SET power_points = power_points + 10 WHERE user_id = ?", (user_id,))
        await message.answer(f"🆙 {message.from_user.first_name} преодолел порог {count} сообщений! +10 💠")
    conn.commit()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(daily_tasks())
    executor.start_polling(dp, skip_updates=True)
  
