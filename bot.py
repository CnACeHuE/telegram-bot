import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Настройки
API_TOKEN = 'ТВОЙ_ТОКЕН_ИЗ_BOTFATHER'
ADMIN_ID = 12345678  # Твой ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Работа с базой данных
conn = sqlite3.connect("abode_base.db")
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, ether INTEGER DEFAULT 0)""")
conn.commit()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Приветствую в Обители! Твои слова теперь превращаются в Эфир. Пиши в чате, чтобы расти в рейтинге.")

@dp.message_handler(commands=['top'])
async def leaderboard(message: types.Message):
    cursor.execute("SELECT username, ether FROM users ORDER BY ether DESC LIMIT 10")
    top_users = cursor.fetchall()
    
    text = "🏆 **СКРИЖАЛИ СУДЬБЫ: ТОП-10**\n\n"
    for i, user in enumerate(top_users, 1):
        name = user[0] if user[0] else "Инкогнито"
        text += f"{i}. {name} — {user[1]} Эфира\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler()
async def track_activity(message: types.Message):
    # Начисляем Эфир за сообщение (минимум 5 символов)
    if len(message.text) > 5:
        user_id = message.from_user.id
        username = message.from_user.username
        
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        cursor.execute("UPDATE users SET ether = ether + 1, username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
