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
ADMIN_ID = 12345678  # ТВОЙ ID

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

# --- СИСТЕМА РАНГОВ ---
def get_rank(msgs):
    ranks = [
        (10000, "Лорд 👑"), (5000, "Золотая черепаха 🐢"), (3000, "Синий бафф 🟦"),
        (2000, "Красный бафф 🟥"), (1500, "Динозаврик 🦖"), (1000, "Жук 🪲"),
        (600, "Лесной медведь 🐻"), (300, "Краб 🦀")
    ]
    for limit, title in ranks:
        if msgs >= limit: return title
    return "Странник 👤"

# --- ОБРАБОТКА ТЕКСТОВЫХ КОМАНД (ГИВ, ПЕРЕДАТЬ, ПВП) ---
@dp.message_handler()
async def main_logic(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    # Регистрация и каунтер
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    cursor.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (user_id,))
    
    # 100 сообщений = 10 очков
    cursor.execute("SELECT msg_count FROM users WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    if count % 100 == 0:
        cursor.execute("UPDATE users SET power_points = power_points + 10 WHERE user_id = ?", (user_id,))
        await message.answer(f"📈 Эволюция! {message.from_user.first_name} достиг {count} СМС. +10 Очков силы!")

    # --- ПЕРЕДАЧА ОЧКОВ ---
    if text.startswith('*передать') and message.reply_to_message:
        try:
            val = int(text.split()[1])
            cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
            balance = cursor.fetchone()[0]
            if balance >= val > 0:
                cursor.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (val, user_id))
                cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (val, message.reply_to_message.from_user.id))
                await message.answer(f"📦 Передано {val} 💠 от {message.from_user.first_name}")
            else: await message.reply("Недостаточно сил.")
        except: pass

    # --- ПВП НА ПИСТОЛЕТАХ ---
    if text == "пвп" and message.reply_to_message:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять дуэль (20 💠)", callback_data=f"pvp_{user_id}_{message.reply_to_message.from_user.id}"))
        await message.answer(f"🔫 {message.from_user.first_name} вызывает {message.reply_to_message.from_user.first_name} на дуэль!", reply_markup=kb)

    # --- СТАТИСТИКА /ME ---
    if text == "/me":
        cursor.execute("SELECT power_points, msg_count, role FROM users WHERE user_id = ?", (user_id,))
        p, m, r = cursor.fetchone()
        await message.answer(f"👤 **{message.from_user.full_name}**\n💠 Очки: {p}\n📈 Ранг: {get_rank(m)}\n💬 СМС: {m}")

    conn.commit()

# --- ОБРАБОТКА МАГАЗИНА И ПВП (CALLBACK) ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def process_pvp(callback: types.CallbackQuery):
    _, ch_id, tg_id = callback.data.split('_')
    if callback.from_user.id != int(tg_id):
        return await callback.answer("Это вызов не тебе!", show_alert=True)
    
    # Шанс 5%. Кнопка "Целиться" будет в следующем шаге, пока — быстрый выстрел
    if random.random() < 0.05:
        winner, loser = tg_id, ch_id
        res_text = "🎯 Прямо в яблочко! Защитник победил."
    else:
        winner, loser = ch_id, tg_id
        res_text = "💨 Промах! Агрессор оказался быстрее."
    
    cursor.execute("UPDATE users SET power_points = power_points + 20 WHERE user_id = ?", (winner,))
    cursor.execute("UPDATE users SET power_points = power_points - 20 WHERE user_id = ?", (loser,))
    conn.commit()
    await callback.message.edit_text(f"{res_text}\n🏆 Победитель забрал 20 💠")

# --- ИНСТРУМЕНТ БОГА ВОРА ---
@dp.message_handler(commands=['steal'])
async def steal_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT power_points FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] < 250:
        return await message.reply("Инструмент вора стоит 250 💠")
    
    cursor.execute("UPDATE users SET power_points = power_points - 250 WHERE user_id = ?", (user_id,))
    stolen = random.randint(1, 800)
    # Шансы: выше 250 — успех 10%, ниже — 40%
    chance = 0.1 if stolen > 250 else 0.4
    
    if random.random() < chance:
        cursor.execute("UPDATE users SET power_points = power_points + ? WHERE user_id = ?", (stolen, user_id))
        await message.answer(f"💰 Успешная кража! Ты вынес {stolen} 💠")
    else:
        await message.answer("💀 Тебя поймали! 250 очков сгорели впустую.")
    conn.commit()

# --- ЗАПУСК ---
async def daily_bonus():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0: # 12:00 MSK
            cursor.execute("UPDATE users SET power_points = power_points + 50")
            conn.commit()
        await asyncio.sleep(60)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(daily_bonus())
    executor.start_polling(dp, skip_updates=True)
  
