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
conn = sqlite3.connect("abode_gods_v6.db", check_same_thread=False)
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

async def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    return res and res[0] == 'admin'

# --- 1. ПРОФИЛЬ (/ME, МИ, /YOU) ---
@dp.message_handler(commands=['me', 'you'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'ми', chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def profile_handler(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    if res:
        await message.answer(f"👤 {target.full_name}\n💠 Очки: {res[0]}\n📈 Ранг: {get_rank(res[1])}")
    else:
        await message.answer("Юзер еще не зарегистрирован в базе.")

# --- 2. ЛОТЕРЕЯ (/LOTTERY, ЛОТЕРЕЯ) ---
@dp.message_handler(commands=['lottery'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'лотерея', chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def lottery_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    
    if not res or res[0] < 50:
        return await message.reply("Лотерея стоит 50 💠. У тебя недостаточно сил!")

    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    
    r = random.random() * 100
    mult = 0
    if r <= 0.1: mult = 50   # 0.1% шанс на x50
    elif r <= 3: mult = 10   # 3% шанс на x10
    elif r <= 15: mult = 3   # 12% шанс на x3
    elif r <= 50: mult = 1   # 35% шанс вернуть своё
    
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    
    status = "Удача!" if mult > 1 else "Бывает..."
    await message.reply(f"🎰 {status} Множитель x{mult}. Получено {win} 💠")

# --- 3. АДМИН-КОМАНДЫ (ГИВ, КАРА) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def admin_handler(message: types.Message):
    if not await is_admin(message.from_user.id): return
    if not message.reply_to_message: return

    text = message.text.lower()
    args = text.split()
    target_id = message.reply_to_message.from_user.id
    target_name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"

    if "божество+" in text:
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {target_name} возведен в ранг Божества!")
    elif "божество-" in text:
        cursor.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await message.answer(f"☁️ {target_name} разжалован.")
    elif len(args) >= 2 and args[1].isdigit():
        amount = int(args[1])
        if any(x in text for x in ["гив", "награда"]):
            cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"✨ Милость Властителя: {target_name} +{amount} 💠")
        elif any(x in text for x in ["кара", "зб"]):
            cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"🔥 Гнев Властителя: {target_name} -{amount} 💠")
    conn.commit()

# --- 4. ПВП ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_acc_'))
async def pvp_callback(callback: types.CallbackQuery):
    _, _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): return
    
    players = [int(ch_id), int(tg_id)]
    winner_id = random.choice(players)
    loser_id = players[1] if winner_id == players[0] else players[0]
    
    winner_user = await bot.get_chat_member(callback.message.chat.id, winner_id)
    winner_name = f"@{winner_user.user.username}" if winner_user.user.username else winner_user.user.first_name

    cursor.execute("UPDATE users SET power_points = power_points + 30 WHERE user_id = ?", (winner_id,))
    cursor.execute("UPDATE users SET power_points = power_points - 30 WHERE user_id = ?", (loser_id,))
    conn.commit()
    
    await callback.message.edit_text(f"🎯 Дуэль окончена!\n🏆 Победитель: **{winner_name}**\n💰 Награда: 30 💠")

# --- 5. ОБЩИЙ ОБРАБОТЧИК (ПВП СТАРТ И СМС) ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    if text.startswith("пвп") and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if target_id == user_id: return
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять бой (30 💠)", callback_data=f"pvp_acc_{user_id}_{target_id}"))
        await message.answer(f"🔫 Вызов на дуэль принят? Жми кнопку!", reply_markup=kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
