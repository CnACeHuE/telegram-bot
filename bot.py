import logging
import sqlite3
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 7361338806 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
# ВАЖНО: На Railway файл базы будет удаляться при деплое.
conn = sqlite3.connect("abode_gods_v9.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, 
                   power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0,
                   role TEXT DEFAULT 'player')""")
conn.commit()

def get_rank(msgs):
    ranks = [(10000, "Лорд 👑"), (5000, "Золотая черепаха 🐢"), (3000, "Синий бафф 🟦"),
             (2000, "Красный бафф 🟥"), (1500, "Динозаврик 🦖"), (1000, "Жук 🪲"),
             (600, "Лесной медведь 🐻"), (300, "Краб 🦀")]
    for limit, title in ranks:
        if msgs >= limit: return title
    return "Вазон 🪴"

def check_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

# --- КОМАНДЫ ПРОФИЛЯ ---
@dp.message_handler(commands=['me', 'you', 'myid'])
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'стата'])
async def profile_handler(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    check_user(target.id, target.username)
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    await message.answer(f"👤 {target.full_name}\n💠 Очки силы: {res[0]}\n📈 Ранг: {get_rank(res[1])}\n💬 Сообщений: {res[1]}")

# --- ЛОТЕРЕЯ ---
@dp.message_handler(commands=['lottery'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'лотерея')
async def lottery_handler(message: types.Message):
    user_id = message.from_user.id
    check_user(user_id, message.from_user.username)
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < 50:
        return await message.reply("Лотерея стоит 50 💠. У тебя маловато сил!")

    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    r = random.randint(1, 100)
    mult = 0
    if r == 100: mult = 50
    elif r > 95: mult = 10
    elif r > 80: mult = 3
    elif r > 50: mult = 1
    
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Результат лотереи: x{mult}!\n💰 Получено: {win} 💠")

# --- ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("пвп"))
async def pvp_start(message: types.Message):
    if not message.reply_to_message: return
    args = message.text.split()
    price = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30
    
    user_id, target_id = message.from_user.id, message.reply_to_message.from_user.id
    if user_id == target_id: return
    
    check_user(user_id, message.from_user.username)
    check_user(target_id, message.reply_to_message.from_user.username)
    
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (user_id, target_id))
    bals = cursor.fetchall()
    if len(bals) < 2 or any(b[0] < price for b in bals):
        return await message.reply(f"У кого-то из вас нет {price} 💠!")

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(f"Принять дуэль ({price} 💠)", callback_data=f"pvp_{user_id}_{target_id}_{price}"))
    await message.answer(f"🔫 Вызов принят? Ставка: {price} 💠", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_end(callback: types.CallbackQuery):
    _, ch_id, tg_id, price = callback.data.split('_')
    price = int(price)
    if callback.from_user.id != int(tg_id): return
    
    winner_id = random.choice([int(ch_id), int(tg_id)])
    loser_id = int(tg_id) if winner_id == int(ch_id) else int(ch_id)
    
    winner = await bot.get_chat_member(callback.message.chat.id, winner_id)
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (price, winner_id))
    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, loser_id))
    conn.commit()
    await callback.message.edit_text(f"🎯 Дуэль окончена!\n🏆 Победитель: {winner.user.first_name}\n💰 Выигрыш: {price} 💠")

# --- АДМИНКА ---
@dp.message_handler(lambda m: any(x in m.text.lower() for x in ["гив", "награда", "кара", "зб", "божество"]))
async def admin_power(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return
    
    text = message.text.lower()
    target_id = message.reply_to_message.from_user.id
    name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"
    
    if "божество+" in text:
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {name} возведен в ранг Божества!")
    elif "гив" in text or "награда" in text:
        val = int(text.split()[1]) if len(text.split()) > 1 and text.split()[1].isdigit() else 0
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, target_id))
        await message.answer(f"✨ Милость Властителя: {name} +{val} 💠")
    elif "кара" in text or "зб" in text:
        val = int(text.split()[1]) if len(text.split()) > 1 and text.split()[1].isdigit() else 0
        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, target_id))
        await message.answer(f"🔥 Гнев Властителя: {name} -{val} 💠")
    conn.commit()

# --- СЧЕТЧИК ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def counter(message: types.Message):
    check_user(message.from_user.id, message.from_user.username)
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
