import sqlite3
import time
import math
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ChatMemberStatus

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=8771183679:AAG6JR-5fGNzMudXR5x9UBZjvPkF5dJOHTU)
dp = Dispatcher(bot)

conn = sqlite3.connect("scores.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    role TEXT DEFAULT 'Новичок',
    last_give INTEGER DEFAULT 0,
    last_target INTEGER DEFAULT 0
)
""")
conn.commit()

COOLDOWN = 30
MAX_POINTS = 50

def get_level(points):
    return int(math.sqrt(points / 50)) + 1

def get_role(level):
    if level >= 10:
        return "Легенда"
    elif level >= 5:
        return "Про"
    elif level >= 3:
        return "Участник"
    else:
        return "Новичок"

def add_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT points, level, role, last_give, last_target FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_user(user_id, points_change, target_id):
    now = int(time.time())

    user = get_user(user_id)
    if user:
        last_give, last_target = user[3], user[4]

        if now - last_give < COOLDOWN:
            return "cooldown"

        if last_target == target_id:
            return "same_target"

    cursor.execute("""
        UPDATE users 
        SET last_give = ?, last_target = ?
        WHERE user_id = ?
    """, (now, target_id, user_id))

    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_change, target_id))

    cursor.execute("SELECT points FROM users WHERE user_id = ?", (target_id,))
    total = cursor.fetchone()[0]

    level = get_level(total)
    role = get_role(level)

    cursor.execute("""
        UPDATE users SET level = ?, role = ?
        WHERE user_id = ?
    """, (level, role, target_id))

    conn.commit()

    return total, level, role

def get_top():
    cursor.execute("SELECT username, points, level FROM users ORDER BY points DESC LIMIT 10")
    return cursor.fetchall()

async def is_admin(chat_id, user_id):
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    await message.reply("🔥 Бот активен")

@dp.message_handler(commands=['score'])
async def score(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    data = get_user(message.from_user.id)

    if data:
        points, level, role = data[0], data[1], data[2]
        await message.reply(f"🎯 Баллы: {points}\n🏅 Уровень: {level}\n🎭 Роль: {role}")

@dp.message_handler(commands=['top'])
async def top(message: types.Message):
    top_users = get_top()

    text = "🏆 Топ:\n\n"
    for i, (username, points, level) in enumerate(top_users, 1):
        text += f"{i}. @{username} — {points} (lvl {level})\n"

    await message.reply(text)

@dp.message_handler(lambda message: message.reply_to_message and (message.text.startswith('+') or message.text.startswith('-')))
async def give_points(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только админы")
        return

    try:
        value = int(message.text)

        if abs(value) > MAX_POINTS:
            await message.reply(f"❌ Макс за раз: {MAX_POINTS}")
            return

        giver = message.from_user
        target = message.reply_to_message.from_user

        if giver.id == target.id:
            await message.reply("🚫 Сам себе нельзя")
            return

        add_user(giver.id, giver.username)
        add_user(target.id, target.username)

        result = update_user(giver.id, value, target.id)

        if result == "cooldown":
            await message.reply("⏳ Подожди")
            return

        if result == "same_target":
            await message.reply("🚫 Нельзя спамить")
            return

        total, level, role = result

        await message.reply(
            f"✅ @{target.username}\n"
            f"Баллы: {total}\n"
            f"Уровень: {level}\n"
            f"Роль: {role}"
        )

    except:
        await message.reply("Пример: +10 (ответом)")

if __name__ == "__main__":
    executor.start_polling(dp)
