
import asyncio
import os
import sqlite3
import math

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================= CONFIG =================
API_TOKEN = os.getenv("API_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================
conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    power INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    role TEXT DEFAULT 'Новичок',
    admin_rank INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= HELPERS =================

def add_user(user: types.User):
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username or "unknown")
    )
    conn.commit()


def get_user(uid):
    cur.execute(
        "SELECT power, level, role, admin_rank, username FROM users WHERE user_id=?",
        (uid,)
    )
    return cur.fetchone()


def get_rank(uid):
    cur.execute("SELECT admin_rank FROM users WHERE user_id=?", (uid,))
    res = cur.fetchone()
    return res[0] if res else 0


def update_stats(uid):
    cur.execute("SELECT power FROM users WHERE user_id=?", (uid,))
    power = cur.fetchone()[0]

    level = int(math.sqrt(power / 100)) + 1

    if level >= 15:
        role = "Легенда"
    elif level >= 8:
        role = "Элита"
    elif level >= 4:
        role = "Опытный"
    else:
        role = "Новичок"

    cur.execute(
        "UPDATE users SET level=?, role=? WHERE user_id=?",
        (level, role, uid)
    )
    conn.commit()


# ================= START =================

@dp.message(Command("start"))
async def start(message: types.Message):
    add_user(message.from_user)

    await message.answer("🔥 Система Очков Мощи активна")


# ================= /me =================

@dp.message(Command("me"))
async def me(message: types.Message):
    add_user(message.from_user)

    data = get_user(message.from_user.id)

    if not data:
        await message.answer("Нет данных")
        return

    await message.answer(
        f"👤 @{data[4]}\n"
        f"⚡ Очки мощи: {data[0]}\n"
        f"📊 Уровень: {data[1]}\n"
        f"🎭 Роль: {data[2]}\n"
        f"🛡 Ранг: {data[3]}"
    )


# ================= TOP =================

@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, power FROM users ORDER BY power DESC LIMIT 10")
    data = cur.fetchall()

    text = "🏆 Топ держателей:\n\n"

    for i, (u, p) in enumerate(data, 1):
        text += f"{i}. @{u} — {p} ⚡\n"

    await message.answer(text)


# ================= MAIN LOGIC =================

@dp.message()
async def handler(message: types.Message):
    if not message.text:
        return

    text = message.text.lower()

    if not message.reply_to_message:
        return

    giver = message.from_user
    target = message.reply_to_message.from_user

    add_user(giver)
    add_user(target)

    giver_rank = get_rank(giver.id)

    # ================= NAGRADIT =================
    if text.startswith("наградить") or text.startswith("пд"):

        if giver.id != OWNER_ID and giver_rank < 1:
            await message.answer("🚫 Нет прав")
            return

        try:
            value = int(text.split()[1])
        except:
            await message.answer("Формат: наградить 10 (ответом)")
            return

        cur.execute(
            "UPDATE users SET power = power + ? WHERE user_id=?",
            (value, target.id)
        )
        conn.commit()

        update_stats(target.id)

        await message.answer(f"⚡ +{value} Очков мощи")

    # ================= ZABRAT =================
    elif text.startswith("забрать") or text.startswith("зб"):

        if giver.id != OWNER_ID and giver_rank < 2:
            await message.answer("🚫 Нет прав")
            return

        try:
            value = int(text.split()[1])
        except:
            await message.answer("Формат: забрать 10 (ответом)")
            return

        cur.execute(
            "UPDATE users SET power = power - ? WHERE user_id=?",
            (value, target.id)
        )
        conn.commit()

        update_stats(target.id)

        await message.answer(f"🔥 -{value} Очков мощи")

    # ================= PEREDAT =================
    elif text.startswith("передать"):

        try:
            value = int(text.split()[1])
        except:
            await message.answer("Формат: передать 10 (ответом)")
            return

        cur.execute("SELECT power FROM users WHERE user_id=?", (giver.id,))
        giver_power = cur.fetchone()[0]

        if giver_power < value:
            await message.answer("❌ Недостаточно очков")
            return

        cur.execute(
            "UPDATE users SET power = power - ? WHERE user_id=?",
            (value, giver.id)
        )

        cur.execute(
            "UPDATE users SET power = power + ? WHERE user_id=?",
            (value, target.id)
        )

        conn.commit()

        update_stats(giver.id)
        update_stats(target.id)

        await message.answer(f"🔁 Передано {value} Очков мощи")


# ================= GOD MODE =================

@dp.message()
async def god_mode(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    if message.text.lower() != "божество+":
        return

    if not message.reply_to_message:
        await message.answer("Ответь на пользователя")
        return

    target = message.reply_to_message.from_user

    cur.execute(
        "UPDATE users SET admin_rank = admin_rank + 1 WHERE user_id=?",
        (target.id,)
    )
    conn.commit()

    await message.answer(f"👑 {target.username} получил ранг")


# ================= RUN =================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
