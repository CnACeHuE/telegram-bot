import logging
import sqlite3
import os
import asyncio
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 7361338806 # ЗАМЕНИ НА СВОЙ ID (цифрами)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("abode_gods_v3.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, 
                   power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0,
                   role TEXT DEFAULT 'player', warns INTEGER DEFAULT 0)""")
conn.commit()

def get_rank(msgs):
    ranks = [(10000, "Лорд 👑"), (5000, "Золотая черепаха 🐢"), (3000, "Синий бафф 🟦"),
             (2000, "Красный бафф 🟥"), (1500, "Динозаврик 🦖"), (1000, "Жук 🪲"),
             (600, "Лесной медведь 🐻"), (300, "Краб 🦀")]
    for limit, title in ranks:
        if msgs >= limit: return title
    return "Вазон 🪴"

# --- ФУНКЦИЯ ПРОВЕРКИ АДМИНА ---
async def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    return res and res[0] == 'admin'

# --- 1. АДМИН-КОМАНДЫ (ГИВ, КАРА, БОЖЕСТВО) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "пд", "награда", "зб", "кара", "божество+"]))
async def admin_tools(message: types.Message):
    if not await is_admin(message.from_user.id): return
    if not message.reply_to_message: return
    
    args = message.text.split()
    cmd = args[0].lower()
    target_id = message.reply_to_message.from_user.id
    target_user = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"

    if cmd == "божество+":
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {target_user} возведен в ранг Божества!")
    else:
        try:
            amount = int(args[1])
            if cmd in ["гив", "пд", "награда"]:
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
                await message.answer(f"✨ {target_user} получил {amount} 💠")
            elif cmd in ["зб", "кара"]:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
                await message.answer(f"🔥 У {target_user} изъято {amount} 💠")
        except: pass
    conn.commit()

# --- 2. ЛОТЕРЕЯ (КОМАНДОЙ) ---
@dp.message_handler(commands=['lottery', 'лотерея'])
async def lottery_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance < 50: return await message.reply("Лотерея стоит 50 💠")

    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    r = random.random() * 100
    mult = 0
    if r <= 0.05: mult = 100
    elif r <= 2: mult = 15
    elif r <= 8: mult = 6
    elif r <= 20: mult = 3
    elif r <= 40: mult = 1
    
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Множитель x{mult}! Выигрыш: {win} 💠")

# --- 3. ПВП, ПЕРЕДАЧА И СЧЕТЧИК ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_logic(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    user_mention = f"@{message.from_user.username}" if message.from_user.username else "юзер"

    # Регистрация
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    # ПВП
    if text.startswith("пвп") and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if target_id == user_id: return await message.reply("Нельзя воевать с тенью!")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять (20 💠)", callback_data=f"pvp_{user_id}_{target_id}"))
        await message.answer(f"🔫 {user_mention} выхватил пистолет против @{message.reply_to_message.from_user.username}!", reply_markup=kb)

    # ПЕРЕДАЧА
    if text.startswith("*передать") and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if target_id == user_id: return await message.reply("Очки и так твои!")
        try:
            val = int(text.split()[1])
            cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] >= val > 0:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, user_id))
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, target_id))
                await message.answer(f"📦 {user_mention} передал {val} 💠 юзеру @{message.reply_to_message.from_user.username}")
            else: await message.reply("Недостаточно сил.")
        except: pass
    conn.commit()

# --- 4. CALLBACK ДЛЯ ПВП ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(callback: types.CallbackQuery):
    _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): return await callback.answer("Это не твой вызов!")
    
    # Шанс 5% как заказывали
    win_id = int(tg_id) if random.random() < 0.05 else int(ch_id)
    lose_id = int(ch_id) if win_id == int(tg_id) else int(tg_id)
    
    cursor.execute("UPDATE users SET power_points = power_points + 20 WHERE user_id = ?", (win_id,))
    cursor.execute("UPDATE users SET power_points = power_points - 20 WHERE user_id = ?", (lose_id,))
    conn.commit()
    await callback.message.edit_text(f"🎯 Выстрел! Победитель забрал 20 💠")

# --- КОМАНДЫ ПРОФИЛЯ ---
@dp.message_handler(commands=['me', 'you'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def profile_cmds(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    if res:
        await message.answer(f"👤 {target.full_name}\n💠 Очки: {res[0]}\n📈 Ранг: {get_rank(res[1])}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
