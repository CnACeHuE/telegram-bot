import asyncio
import sqlite3
import time
import math
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ===== БАЗА =====
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

# ===== НАСТРОЙКИ =====
COOLDOWN = 30
MAX_POINTS = 50

# ===== ЛОГИКА =====

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
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()

def get_user(user_id):
    cursor.execute(
        "SELECT points, level, role, last_give, last_target FROM users WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()

def update_user(giver_id, target_id, points_change):
    now = int(time.time())

    giver = get_user(giver_id)
    if giver:
        last_give, last_target = giver[3], giver[4]

        if now - last_give < COOLDOWN:
            return "cooldown"

        if last_target == target_id:
            return "same_target"

    cursor.execute("""
        UPDATE users SET last_give = ?, last_target = ?
        WHERE user_id = ?
    """, (now, target_id, giver_id))

    cursor.execute(
        "UPDATE users SET points = points + ? WHERE user_id = ?",
        (points_change, target_id)
    )

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
    cursor.execute(
        "SELECT username, points, level FROM users ORDER BY points DESC LIMIT 10"
    )
    return cursor.fetchall()

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    await message.answer("🔥 Бот с уровнями работает")

@dp.message(Command("score"))
async def score(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    data = get_user(message.from_user.id)

    if data:
        points, level, role = data[0], data[1], data[2]
        await message.answer(
            f"🎯 Баллы: {points}\n🏅 Уровень: {level}\n🎭 Роль: {role}"
        )

@dp.message(Command("top"))
async def top(message: types.Message):
    top_users = get_top()

    text = "🏆 Топ:\n\n"
    for i, (username, points, level) in enumerate(top_users, 1):
        text += f"{i}. @{username} — {points} (lvl {level})\n"

    await message.answer(text)

# ===== ВЫДАЧА БАЛЛОВ =====

@dp.message()
async def give_points(message: types.Message):
    if not message.reply_to_message:
        return

    text = message.text.strip()

    if not (text.startswith("+") or text.startswith("-")):
        return

    try:
        value = int(text)

        if abs(value) > MAX_POINTS:
            await message.answer(f"❌ Макс за раз: {MAX_POINTS}")
            return

        giver = message.from_user
        target = message.reply_to_message.from_user

        if giver.id == target.id:
            await message.answer("🚫 Сам себе нельзя")
            return

        add_user(giver.id, giver.username)
        add_user(target.id, target.username)

        result = update_user(giver.id, target.id, value)

        if result == "cooldown":
            await message.answer("⏳ Подожди перед выдачей")
            return

        if result == "same_target":
            await message.answer("🚫 Нельзя подряд одному и тому же")
            return

        total, level, role = result

        await message.answer(
            f"✅ @{target.username}\n"
            f"Баллы: {total}\n"
            f"Уровень: {level}\n"
            f"Роль: {role}"
        )

    except:
        await message.answer("Пример: +10 (ответом)")

# ===== ЗАПУСК =====

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
