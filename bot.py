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
conn = sqlite3.connect("abode_gods_v8.db", check_same_thread=False)
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

# Регистратор юзера (чтобы команды не падали)
def check_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

# --- 1. КОМАНДЫ ПРОФИЛЯ (Ми, /me, /you) ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', '/me', '/you'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def profile_handler(message: types.Message):
    target = message.reply_to_message.from_user if (message.text.startswith('/you') and message.reply_to_message) else message.from_user
    check_user(target.id, target.username)
    
    cursor.execute("SELECT power_points, msg_count FROM users WHERE user_id = ?", (target.id,))
    res = cursor.fetchone()
    await message.answer(f"👤 {target.full_name}\n💠 Очки: {res[0]}\n📈 Ранг: {get_rank(res[1])}")

# --- 2. ПВП (С ПРОВЕРКОЙ БАЛАНСА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith("пвп"), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def pvp_start(message: types.Message):
    if not message.reply_to_message: return
    
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    if user_id == target_id: return
    
    check_user(user_id, message.from_user.username)
    check_user(target_id, message.reply_to_message.from_user.username)

    # Проверка баланса перед вызовом
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (user_id, target_id))
    balances = cursor.fetchall()
    
    if any(b[0] < 30 for b in balances):
        return await message.reply("У одного из бойцов меньше 30 💠. Дуэль невозможна!")

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять бой (30 💠)", callback_data=f"pvp_acc_{user_id}_{target_id}"))
    await message.answer(f"🔫 @{message.from_user.username} вызывает на дуэль @{message.reply_to_message.from_user.username}!", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_acc_'))
async def pvp_battle(callback: types.CallbackQuery):
    _, _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id): return
    
    # Повторная проверка баланса в момент нажатия кнопки
    cursor.execute("SELECT power_points FROM users WHERE user_id IN (?, ?)", (int(ch_id), int(tg_id)))
    balances = cursor.fetchall()
    if any(b[0] < 30 for b in balances):
        return await callback.message.edit_text("❌ Дуэль отменена: недостаточно средств у одного из игроков.")

    winner_id = random.choice([int(ch_id), int(tg_id)])
    loser_id = int(tg_id) if winner_id == int(ch_id) else int(ch_id)
    
    winner_member = await bot.get_chat_member(callback.message.chat.id, winner_id)
    winner_name = f"@{winner_member.user.username}" if winner_member.user.username else winner_member.user.first_name

    cursor.execute("UPDATE users SET power_points = power_points + 30 WHERE user_id = ?", (winner_id,))
    cursor.execute("UPDATE users SET power_points = power_points - 30 WHERE user_id = ?", (loser_id,))
    conn.commit()
    await callback.message.edit_text(f"🎯 Дуэль окончена!\n🏆 Победитель: {winner_name}\n💰 Забрал 30 💠")

# --- 3. АДМИН-КОМАНДЫ (ГИВ / КАРА) ---
@dp.message_handler(lambda m: any(m.text.lower().startswith(c) for c in ["гив", "награда", "кара", "зб", "божество+", "божество-"]))
async def admin_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (message.from_user.id,))
        if not cursor.fetchone() or cursor.fetchone()[0] != 'admin': return

    if not message.reply_to_message: return
    text = message.text.lower()
    target_id = message.reply_to_message.from_user.id
    target_name = f"@{message.reply_to_message.from_user.username}" if message.reply_to_message.from_user.username else "юзер"

    if "божество+" in text:
        cursor.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (target_id,))
        await message.answer(f"⚡️ {target_name} стал Божеством!")
    elif "божество-" in text:
        cursor.execute("UPDATE users SET role = 'player' WHERE user_id = ?", (target_id,))
        await message.answer(f"☁️ {target_name} разжалован.")
    elif len(text.split()) >= 2 and text.split()[1].isdigit():
        amount = int(text.split()[1])
        if "гив" in text or "награда" in text:
            cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"✨ {target_name} +{amount} 💠")
        else:
            cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amount, target_id))
            await message.answer(f"🔥 {target_name} -{amount} 💠")
    conn.commit()

# --- 4. ФИНАЛЬНЫЙ ОБРАБОТЧИК (СМС И ПЕРЕДАЧА) ---
@dp.message_handler(chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def msg_counter(message: types.Message):
    user_id = message.from_user.id
    check_user(user_id, message.from_user.username)
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    
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
  
