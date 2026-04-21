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
ALLOWED_CHATS = [-1002408347623, -1003761187223] 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("abode_gods_v17.db", check_same_thread=False)
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

async def check_access(message: types.Message):
    if message.chat.type == 'private':
        return message.from_user.id == ADMIN_ID
    return message.chat.id in ALLOWED_CHATS

# --- 1. ПЕРЕДАЧА ОЧКОВ (*передать) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("*передать"))
async def transfer_points(message: types.Message):
    if not await check_access(message): return
    if not message.reply_to_message: return

    user_id, target_id = message.from_user.id, message.reply_to_message.from_user.id
    if user_id == target_id: return

    try:
        parts = message.text.split()
        amount = int(parts[1])
        if amount <= 0: return

        check_user(user_id, message.from_user.username)
        check_user(target_id, message.reply_to_message.from_user.username)

        cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone()[0] < amount:
            return await message.reply("Недостаточно 💠!")

        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        await message.answer(f"📦 {message.from_user.first_name} передал {message.reply_to_message.from_user.first_name} {amount} 💠")
    except: pass

# --- 2. ЛОТЕРЕЯ (деп, лотерея) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith(('лотерея', 'деп')) or m.text.lower().startswith('/lottery')))
async def lottery_handler(message: types.Message):
    if not await check_access(message): return
    user_id = message.from_user.id
    check_user(user_id, message.from_user.username)
    
    args = message.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    if bet < 10: return
    
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance < bet: 
        return await message.reply(f"Недостаточно сил! Баланс: {balance} 💠")

    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, user_id))
    r = random.random() * 100
    
    if r < 0.2: mult = 100
    elif r < 0.7: mult = 50
    elif r < 2.2: mult = 10
    elif r < 10.2: mult = 5
    elif r < 30.2: mult = 2
    elif r < 65.2: mult = 1
    else: mult = 0
    
    win = bet * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    
    if mult >= 50:
        res = f"🎰 ДЖЕКПОТ! x{mult}\n💰 Выигрыш: {win} 💠"
    elif mult > 1:
        res = f"🎰 Крупная удача! x{mult}\n💎 Забрал: {win} 💠"
    elif mult == 1:
        res = f"🎰 Возврат! x{mult}\n💠 Твои {win} 💠 при тебе."
    else:
        res = f"🎰 Мимо! x0\n💀 Ставка {bet} 💠 ушла в эфир."
    await message.reply(res)

# --- 3. АДМИНКА (ГИВ, КАРА, БОЖЕСТВО) ---
@dp.message_handler(lambda m: m.text and any(m.text.lower().startswith(x) for x in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def admin_handler(message: types.Message):
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (message.from_user.id,))
    res_role = cursor.fetchone()
    is_mod = res_role[0] == 'admin' if res_role else False
    
    if message.from_user.id != ADMIN_ID and not is_mod: return
    if not message.reply_to_message: return
    
    text = message.text.lower()
    target_id = message.reply_to_message.from_user.id
    target_name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"
    
    if message.from_user.id == ADMIN_ID:
        if text.startswith("божество+"):
            cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
            await message.answer(f"⚡️ {target_name} возведен в ранг Божества!")
            conn.commit(); return
        elif text.startswith("божество-"):
            cursor.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
            await message.answer(f"☁️ {target_name} лишен божественных сил.")
            conn.commit(); return

    try:
        val = int(text.split()[1])
        if text.startswith(("гив", "награда")):
            cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, target_id))
            await message.answer(f"✨ Милость Властителя: {target_name} +{val} 💠")
        elif text.startswith(("кара", "зб")):
            cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, target_id))
            await message.answer(f"🔥 Гнев Властителя: {target_name} -{val} 💠")
        conn.commit()
    except: pass

# --- 4. ПРОФИЛЬ, ПВП И СЧЕТЧИК ---
@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith(('ю*', '/you', '/me'))))
async def profile_handler(message: types.Message):
    if not await check_access(message): return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    check_user(target.id, target.username)
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    await message.answer(f"👤 {target.full_name}\n💠 Очки силы: {res[0]}\n📈 Ранг: {get_rank(res[1])}\n💬 Активность: {res[1]} сообщ.")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith("пвп"))
async def pvp_start(message: types.Message):
    if not await check_access(message): return
    if not message.reply_to_message: return
    args = message.text.split()
    price = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30
    u1, u2 = message.from_user.id, message.reply_to_message.from_user.id
    if u1 == u2: return
    check_user(u1, message.from_user.username); check_user(u2, message.reply_to_message.from_user.username)
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (u1, u2))
    if any(b[0] < price for b in cursor.fetchall()): return await message.reply(f"Нужно {price} 💠!")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(f"Принять ({price} 💠)", callback_data=f"pvp_{u1}_{u2}_{price}"))
    await message.answer(f"🔫 Вызов на бой! Ставка: {price} 💠", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(callback: types.CallbackQuery):
    _, c_id, t_id, p = callback.data.split('_'); p = int(p)
    if callback.from_user.id != int(t_id): return
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (int(c_id), int(t_id)))
    if any(b[0] < p for b in cursor.fetchall()): return await callback.message.edit_text("❌ Бой отменен.")
    win_id = random.choice([int(c_id), int(t_id)]); los_id = int(t_id) if win_id == int(c_id) else int(c_id)
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (p, win_id))
    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (p, los_id))
    conn.commit()
    winner = await bot.get_chat_member(callback.message.chat.id, win_id)
    await callback.message.edit_text(f"🎯 Победитель: **{winner.user.first_name}**\n💰 Куш: {p} 💠")

@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def counter(message: types.Message):
    if not await check_access(message): return
    check_user(message.from_user.id, message.from_user.username)
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
