
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
conn = sqlite3.connect("abode_gods_v7.db", check_same_thread=False)
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

# --- 1. АДМИН-БЛОК (САМЫЙ ВЕРХ) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "награда", "кара", "зб", "божество+", "божество-"]), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
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
            await message.answer(f"✨ Милость: {target_name} +{amount} 💠")
        elif any(x in text for x in ["кара", "зб"]):
            cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"🔥 Гнев: {target_name} -{amount} 💠")
    conn.commit()

# --- 2. КОМАНДЫ ПРОФИЛЯ ---
@dp.message_handler(commands=['me', 'you'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def profile_handler(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    if res:
        await message.answer(f"👤 {target.full_name}\n💠 Очки: {res[0]}\n📈 Ранг: {get_rank(res[1])}")

# --- 3. ЛОТЕРЕЯ ---
@dp.message_handler(commands=['lottery'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'лотерея', chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def lottery_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] < 50: return await message.reply("Лотерея стоит 50 💠!")

    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    r = random.random() * 100
    mult = 50 if r < 0.2 else (10 if r < 2 else (3 if r < 15 else (1 if r < 45 else 0)))
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Множитель x{mult}! Результат: {win} 💠")

# --- 4. ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("пвп"), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def pvp_start(message: types.Message):
    if not message.reply_to_message: return
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    if user_id == target_id: return
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять дуэль (30 💠)", callback_data=f"pvp_acc_{user_id}_{target_id}"))
    await message.answer(f"🔫 @{message.from_user.username} вызывает на дуэль @{message.reply_to_message.from_user.username}!", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_acc_'))
async def pvp_battle(callback: types.CallbackQuery):
    _, _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): 
        return await callback.answer("Это не твой вызов!", show_alert=True)
    
    winner_id = random.choice([int(ch_id), int(tg_id)])
    loser_id = int(tg_id) if winner_id == int(ch_id) else int(ch_id)
    
    # Получаем имя победителя
    winner_member = await bot.get_chat_member(callback.message.chat.id, winner_id)
    winner_name = f"@{winner_member.user.username}" if winner_member.user.username else winner_member.user.first_name

    cursor.execute("UPDATE users SET power_points = power_points + 30 WHERE user_id = ?", (winner_id,))
    cursor.execute("UPDATE users SET power_points = power_points - 30 WHERE user_id = ?", (loser_id,))
    conn.commit()
    await callback.message.edit_text(f"🎯 Дуэль окончена!\n🏆 Победитель: {winner_name}\n💰 Выигрыш: 30 💠")

# --- 5. ФИНАЛЬНЫЙ ОБРАБОТЧИК (СЧЕТЧИК СМС) ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def msg_counter(message: types.Message):
    user_id = message.from_user.id
    # Регистрация и инкремент
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    
    # Передача (текстовая команда)
    if message.text and message.text.lower().startswith("*передать") and message.reply_to_message:
        try:
            val = int(message.text.split()[1])
            cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] >= val > 0:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, user_id))
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, message.reply_to_message.from_user.id))
                await message.answer(f"📦 Передано {val} 💠")
        except: pass
    conn.commit()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
