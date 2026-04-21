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
# Основной чат (2408347623) и Тестовый (3761187223)
ALLOWED_CHATS = [-1002408347623, -1003761187223] 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
# Напоминание: На Railway база сбросится при деплое, если не подключить Volume или Postgres
conn = sqlite3.connect("abode_gods_v13.db", check_same_thread=False)
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
    if not message.reply_to_message:
        return await message.reply("Нужно ответить на сообщение того, кому передаешь очки!")

    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    if user_id == target_id: return

    try:
        parts = message.text.split()
        if len(parts) < 2: return
        amount = int(parts[1])
        if amount <= 0: return

        check_user(user_id, message.from_user.username)
        check_user(target_id, message.reply_to_message.from_user.username)

        cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]

        if balance < amount:
            return await message.reply(f"Недостаточно 💠. Твой баланс: {balance}")

        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()

        await message.answer(f"📦 {message.from_user.first_name} передал {message.reply_to_message.from_user.first_name} {amount} 💠")
    except (ValueError, IndexError):
        await message.reply("Используй формат: `*передать 100`")

# --- 2. ЛОТЕРЕЯ (Джекпот x100) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().startswith('лотерея') or m.text.lower().startswith('/lottery')))
async def lottery_handler(message: types.Message):
    if not await check_access(message): return
    user_id = message.from_user.id
    check_user(user_id, message.from_user.username)
    
    args = message.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    if bet < 10: return await message.reply("Минимальная ставка — 10 💠")

    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance < bet: return await message.reply(f"Недостаточно сил! Баланс: {balance} 💠")

    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (bet, user_id))
    
    r = random.random() * 100
    # Настройка шансов: x100(0.2%), x10(2.3%), x5(6%), x2(12%), x1(45%), x0(34.5%)
    if r < 0.2: mult = 100
    elif r < 2.5: mult = 10
    elif r < 8.5: mult = 5
    elif r < 20.5: mult = 2
    elif r < 65.5: mult = 1
    else: mult = 0
    
    win = bet * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    
    if mult == 100:
        res = f"🔥 ЛЕГЕНДАРНЫЙ ДЖЕКПОТ! 🔥\n🎰 Множитель x100!\n💰 Выигрыш: {win} 💠"
    elif mult > 1:
        res = f"🎰 Удача! x{mult}\n💎 Забрал: {win} 💠"
    elif mult == 1:
        res = f"🎰 Возврат! x1\n💠 {win} 💠 сохранены."
    else:
        res = f"🎰 Проигрыш x0.\n💀 Ставка {bet} 💠 сгорела."
    await message.reply(res)

# --- 3. ПРОФИЛЬ (Ми, ю*, /me, /you) ---
@dp.message_handler(lambda m: m.text and (m.text.lower().strip() in ['ми', 'профиль'] or m.text.lower().startswith(('ю*', '/you', '/me'))))
async def profile_handler(message: types.Message):
    if not await check_access(message): return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    check_user(target.id, target.username)
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    await message.answer(f"👤 {target.full_name}\n💠 Очки силы: {res[0]}\n📈 Ранг: {get_rank(res[1])}\n💬 Активность: {res[1]} сообщ.")

# --- 4. ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("пвп"))
async def pvp_start(message: types.Message):
    if not await check_access(message): return
    if not message.reply_to_message: return
    args = message.text.split()
    price = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30
    user_id, target_id = message.from_user.id, message.reply_to_message.from_user.id
    if user_id == target_id: return
    check_user(user_id, message.from_user.username); check_user(target_id, message.reply_to_message.from_user.username)
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (user_id, target_id))
    bals = cursor.fetchall()
    if len(bals) < 2 or any(b[0] < price for b in bals): return await message.reply(f"Нужно {price} 💠 у обоих!")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(f"Принять ({price} 💠)", callback_data=f"pvp_{user_id}_{target_id}_{price}"))
    await message.answer(f"🔫 Вызов на бой! Ставка: {price} 💠", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(callback: types.CallbackQuery):
    _, ch_id, tg_id, price = callback.data.split('_'); price = int(price)
    if callback.from_user.id != int(tg_id): return
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (int(ch_id), int(tg_id)))
    if any(b[0] < price for b in cursor.fetchall()): return await callback.message.edit_text("❌ Бой отменен.")
    winner_id = random.choice([int(ch_id), int(tg_id)]); loser_id = int(tg_id) if winner_id == int(ch_id) else int(ch_id)
    winner = await bot.get_chat_member(callback.message.chat.id, winner_id)
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (price, winner_id))
    cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (price, loser_id))
    conn.commit()
    await callback.message.edit_text(f"🎯 Победитель: **{winner.user.first_name}**\n💰 Куш: {price} 💠")

# --- 5. АДМИНКА ---
@dp.message_handler(lambda m: any(x in m.text.lower() for x in ["гив", "награда", "кара", "зб"]))
async def admin_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return
    text = message.text.lower(); target_id = message.reply_to_message.from_user.id
    name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"
    try: val = int(text.split()[1])
    except: val = 0
    if "гив" in text or "награда" in text:
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, target_id))
        await message.answer(f"✨ Милость Властителя: {name} +{val} 💠")
    else:
        cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, target_id))
        await message.answer(f"🔥 Гнев Властителя: {name} -{val} 💠")
    conn.commit()

# --- 6. СЧЕТЧИК (В самом низу) ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def counter(message: types.Message):
    if not await check_access(message): return
    check_user(message.from_user.id, message.from_user.username)
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (message.from_user.id,))
    conn.commit()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
