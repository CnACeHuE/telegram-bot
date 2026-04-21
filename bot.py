import logging
import sqlite3
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 12345678  # СЮДА ВСТАВЬ СВОЙ ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("abode_gods_v4.db", check_same_thread=False)
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

# --- 1. АДМИН-КОМАНДЫ (ГИВ, КАРА, БОЖЕСТВО) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def admin_commands(message: types.Message):
    if not await is_admin(message.from_user.id): return
    if not message.reply_to_message: return
    
    text = message.text.lower()
    args = text.split()
    target_id = message.reply_to_message.from_user.id
    target_user = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"

    if text.startswith("божество+"):
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {target_user} теперь Божество!")
    elif text.startswith("божество-"):
        cursor.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await message.answer(f"☁️ {target_user} лишен полномочий.")
    elif len(args) >= 2 and args[1].isdigit():
        amount = int(args[1])
        if any(text.startswith(c) for c in ["гив", "награда"]):
            cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"✨ {target_user} получил {amount} 💠 из эфира!")
        elif any(text.startswith(c) for c in ["кара", "зб"]):
            cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"🔥 У {target_user} аннулировано {amount} 💠")
    conn.commit()

# --- 2. ЛОТЕРЕЯ (ИСПРАВЛЕНА) ---
@dp.message_handler(commands=['lottery', 'лотерея'])
async def lottery_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] < 50: return await message.reply("Нужно 50 💠!")

    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    r = random.random() * 100
    mult = 0
    if r <= 0.5: mult = 50
    elif r <= 5: mult = 10
    elif r <= 15: mult = 3
    elif r <= 45: mult = 1
    
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Результат: x{mult}! Выигрыш: {win} 💠")

# --- 3. МАГАЗИН ---
@dp.message_handler(commands=['shop', 'магазин'])
async def shop_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🗡 Инструмент вора (250 💠)", callback_data="buy_steal"),
        InlineKeyboardButton("🛡 Свиток очищения (500 💠)", callback_data="buy_clear")
    )
    await message.answer("🏪 **Магазин Обители**\nВыбери товар:", reply_markup=kb)

# --- 4. ПВП (ЧЕСТНЫЙ ШАНС) ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_eval(callback: types.CallbackQuery):
    _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): return await callback.answer("Это не твой вызов!")
    
    # 50/50 шанс для честной игры
    winner_id = random.choice([int(ch_id), int(tg_id)])
    loser_id = int(tg_id) if winner_id == int(ch_id) else int(ch_id)
    
    cursor.execute("UPDATE users SET power_points = power_points + 30 WHERE user_id = ?", (winner_id,))
    cursor.execute("UPDATE users SET power_points = power_points - 30 WHERE user_id = ?", (loser_id,))
    conn.commit()
    await callback.message.edit_text(f"🎯 Дуэль окончена! Победитель забрал 30 💠")

# --- 5. ЛОГИКА ГРУППЫ ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower() if message.text else ""
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    
    # ПВП активация
    if text.startswith("пвп") and message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if target_id == user_id: return
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять бой", callback_data=f"pvp_{user_id}_{target_id}"))
        await message.answer(f"🔫 Вызов принят? Ставка 30 💠", reply_markup=kb)

    # Передача (запрет себе)
    if text.startswith("*передать") and message.reply_to_message:
        if message.reply_to_message.from_user.id == user_id: return
        try:
            val = int(text.split()[1])
            cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] >= val:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, user_id))
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, message.reply_to_message.from_user.id))
                await message.answer(f"📦 Передано {val} 💠")
        except: pass
    conn.commit()

# Профили
@dp.message_handler(commands=['me', 'you'])
async def profile(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    if res:
        await message.answer(f"👤 {target.full_name}\n💠 Сила: {res[0]}\n📈 Ранг: {get_rank(res[1])}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                         
