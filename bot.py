import asyncio
import os
import sqlite3
import time
import math

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# =====================
# TOKEN
# =====================
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в переменных окружения")

# =====================
# BOT INIT (ВАЖНО: СНАЧАЛА ЭТО)
# =====================
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# =====================
# DATABASE
# =====================
conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    role TEXT DEFAULT 'Новичок',
    last_action INTEGER DEFAULT 0
)
""")
conn.commit()

# =====================
# CONFIG
# =====================
COOLDOWN = 20
MAX_POINTS = 50

# =====================
# FUNCTIONS
# =====================
def add_user(user_id, username):
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()


def get_user(user_id):
    cur.execute("SELECT points, level, role, last_action FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone()


def calc_level(points):
    return int(math.sqrt(points / 100)) + 1


def calc_role(level):
    if level >= 15:
        return "Легенда"
    elif level >= 8:
        return "Элита"
    elif level >= 4:
        return "Опытный"
    return "Новичок"


def update_points(giver_id, target_id, value):
    now = int(time.time())

    cur.execute("SELECT last_action FROM users WHERE user_id=?", (giver_id,))
    last = cur.fetchone()[0]

    if now - last < COOLDOWN:
        return "cooldown"

    cur.execute("UPDATE users SET last_action=? WHERE user_id=?", (now, giver_id))

    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (value, target_id)
    )

    cur.execute("SELECT points FROM users WHERE user_id=?", (target_id,))
    points = cur.fetchone()[0]

    level = calc_level(points)
    role = calc_role(level)

    cur.execute(
        "UPDATE users SET level=?, role=? WHERE user_id=?",
        (level, role, target_id)
    )

    conn.commit()

    return points, level, role


def get_top():
    cur.execute("SELECT username, points, level FROM users ORDER BY points DESC LIMIT 10")
    return cur.fetchall()

# =====================
# HANDLERS
# =====================

@dp.message(Command("start"))
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    await message.answer("🔥 Бот баллов запущен")


@dp.message(Command("me"))
async def me(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    data = get_user(message.from_user.id)

    await message.answer(
        f"🏆 Баллы: {data[0]}\n"
        f"📊 Уровень: {data[1]}\n"
        f"🎭 Роль: {data[2]}"
    )


@dp.message(Command("top"))
async def top(message: types.Message):
    data = get_top()

    text = "🏆 Топ игроков:\n\n"
    for i, (u, p, l) in enumerate(data, 1):
        text += f"{i}. @{u} — {p} (lvl {l})\n"

    await message.answer(text)


@dp.message()
async def points(message: types.Message):
    if not message.reply_to_message:
        return

    if not message.text:
        return

    if not (message.text.startswith("+") or message.text.startswith("-")):
        return

    try:
        value = int(message.text)

        if abs(value) > MAX_POINTS:
            await message.answer("❌ Слишком много за раз")
            return

        giver = message.from_user
        target = message.reply_to_message.from_user

        if giver.id == target.id:
            await message.answer("🚫 Нельзя самому себе")
            return

        add_user(giver.id, giver.username)
        add_user(target.id, target.username)

        result = update_points(giver.id, target.id, value)

        if result == "cooldown":
            await message.answer("⏳ Подожди немного")
            return

        points, level, role = result

        await message.answer(
            f"✅ @{target.username}\n"
            f"⭐ Баллы: {points}\n"
            f"📊 Уровень: {level}\n"
            f"🎭 Роль: {role}"
        )

    except:
        await message.answer("Используй: +10 (ответом)")


# =====================
# START BOT
# =====================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
