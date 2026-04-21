import logging
import sqlite3
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 7361338806  # ТВОЙ ID ЗДЕСЬ

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ (Расширенная) ---
conn = sqlite3.connect("abode_gods_v5.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, 
                   power_points INTEGER DEFAULT 100, msg_count INTEGER DEFAULT 0,
                   role TEXT DEFAULT 'player', clan_id TEXT DEFAULT NULL)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS clans 
                  (clan_id INTEGER PRIMARY KEY AUTOINCREMENT, clan_name TEXT, 
                   leader_id INTEGER, total_power INTEGER DEFAULT 0)""")
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

# --- 1. АДМИН-ЛОГИКА (ГИВ, КАРА, БОЖЕСТВО) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def super_admin_logic(message: types.Message):
    if not await is_admin(message.from_user.id): return
    if not message.reply_to_message:
        return await message.reply("Ответь на сообщение цели!")

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

# --- 2. МАГАЗИН И ПРЕДМЕТЫ ---
@dp.message_handler(commands=['shop', 'магазин'])
async def shop_menu(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🧤 Инструмент бога вора (250 💠)", callback_data="buy_steal_tool"),
        InlineKeyboardButton("✨ Очистка варна (1000 💠)", callback_data="buy_clear"),
        InlineKeyboardButton("🎭 Уникальная роль (700 💠)", callback_data="buy_role")
    )
    await message.answer("🏪 **Лавка Обители**\nУ тебя есть Очки силы? Покупай силу!", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "buy_steal_tool")
async def process_steal_buy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance < 250:
        return await callback.answer("Недостаточно очков (нужно 250)!", show_alert=True)
    
    # Логика кражи
    cursor.execute("UPDATE users SET power_points = power_points - 250 WHERE user_id = ?", (user_id,))
    stolen = random.randint(1, 800)
    chance = 0.4 if stolen <= 250 else 0.1 # Шанс падает если куш большой
    
    if random.random() < chance:
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (stolen, user_id))
        await callback.message.answer(f"💰 @{callback.from_user.username} использовал Инструмент Вора и вынес {stolen} 💠!")
    else:
        await callback.message.answer(f"💀 @{callback.from_user.username} пытался украсть очки, но Инструмент сломался!")
    conn.commit()

# --- 3. ПВП И ЛОТЕРЕЯ ---
@dp.message_handler(commands=['lottery', 'лотерея'])
async def lotto(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] < 50: return await message.reply("Лотерея стоит 50 💠")
    
    cursor.execute("UPDATE users SET power_points = power_points - 50 WHERE user_id = ?", (user_id,))
    r = random.random() * 100
    if r <= 0.05: mult = 100
    elif r <= 2.05: mult = 15
    elif r <= 10.05: mult = 6
    elif r <= 30.05: mult = 3
    elif r <= 70.05: mult = 1
    else: mult = 0
    
    win = 50 * mult
    cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (win, user_id))
    conn.commit()
    await message.reply(f"🎰 Ставка принята! Множитель x{mult}. Получено {win} 💠")

# --- 4. ОБЩАЯ ЛОГИКА ГРУППЫ ---
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
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять дуэль (30 💠)", callback_data=f"pvp_accept_{user_id}_{target_id}"))
        await message.answer(f"🔫 @{message.from_user.username} вызывает @{message.reply_to_message.from_user.username} на перестрелку!", reply_markup=kb)

    # Передача
    if text.startswith("*передать") and message.reply_to_message:
        if message.reply_to_message.from_user.id == user_id: return
        try:
            val = int(text.split()[1])
            cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] >= val > 0:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, user_id))
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, message.reply_to_message.from_user.id))
                await message.answer(f"📦 Передано {val} 💠")
        except: pass
    conn.commit()

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_accept_'))
async def pvp_battle(callback: types.CallbackQuery):
    _, _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): return
    
    # Честный рандом 50/50 для ПВП
    winner = random.choice([int(ch_id), int(tg_id)])
    loser = int(tg_id) if winner == int(ch_id) else int(ch_id)
    
    cursor.execute("UPDATE users SET power_points = power_points + 30 WHERE user_id = ?", (winner,))
    cursor.execute("UPDATE users SET power_points = power_points - 30 WHERE user_id = ?", (loser,))
    conn.commit()
    await callback.message.edit_text(f"🎯 Дуэль окончена! Победитель забрал 30 💠")

@dp.message_handler(commands=['me', 'you'])
async def show_profile(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    if res:
        await message.answer(f"👤 {target.full_name}\n💠 Очки: {res[0]}\n📈 Ранг: {get_rank(res[1])}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
