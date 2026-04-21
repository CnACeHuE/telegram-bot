import asyncio
import os
import sqlite3
import time
import math

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= DB =================
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

# ================= OWNER CONFIG =================
OWNER_ID = None  # поставь свой Telegram ID сюда

# ================= HELPERS =================
def add_user(uid, username):
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, username))
    conn.commit()

def get_user(uid):
    cur.execute("SELECT power, level, role, admin_rank, username FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def is_admin(uid):
    cur.execute("SELECT admin_rank FROM users WHERE user_id=?", (uid,))
    res = cur.fetchone()
    return res and res[0] > 0

def calc_level(power):
    return int(math.sqrt(power / 100)) + 1

def calc_role(level):
    if level >= 15:
        return "Легенда"
    elif level >= 8:
        return "Элита"
    elif level >= 4:
        return "Опытный"
    return "Новичок"

def update_power(uid):
    cur.execute("SELECT power FROM users WHERE user_id=?", (uid,))
    power = cur.fetchone()[0]

    level = calc_level(power)
    role = calc_role(level)

    cur.execute("UPDATE users SET level=?, role=? WHERE user_id=?", (level, role, uid))
    conn.commit()

# ================= COMMANDS =================

@dp.message(Command("start"))
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    await message.answer("🔥 Система Очков Мощи активна")

# ---------- /me ----------
@dp.message(Command("me"))
async def me(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)
    data = get_user(message.from_user.id)

    await message.answer(
        f"👤 @{data[4]}\n"
        f"⚡ Очки мощи: {data[0]}\n"
        f"📊 Уровень: {data[1]}\n"
        f"🎭 Роль: {data[2]}"
    )

# ---------- TOP ----------
@dp.message(Command("top"))
async def top(message: types.Message):
    cur.execute("SELECT username, power FROM users ORDER BY power DESC LIMIT 10")
    data = cur.fetchall()

    text = "🏆 Топ держателей:\n\n"
    for i, (u, p) in enumerate(data, 1):
        text += f"{i}. @{u} — {p} ⚡\n"

    await message.answer(text)

# ================= ADMIN SYSTEM =================

def check_permission(user_id, required_rank):
    cur.execute("SELECT admin_rank FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    return res and res[0] >= required_rank

# ---------- GIVE POWER ----------
@dp.message()
async def handle(message: types.Message):
    if not message.text:
        return

    text = message.text.lower()

    if not message.reply_to_message:
        return

    giver = message.from_user
    target = message.reply_to_message.from_user

    add_user(giver.id, giver.username)
    add_user(target.id, target.username)

    giver_data = get_user(giver.id)

    # ================= GIVE =================
    if text.startswith("наградить") or text.startswith("пд"):
        if giver_data[3] < 1 and giver.id != OWNER_ID:
            await message.answer("🚫 Нет прав")
            return

        try:
            value = int(message.text.split()[1])
        except:
            await message.answer("Пример: наградить 10 (ответом)")
            return

        cur.execute("UPDATE users SET power = power + ? WHERE user_id=?", (value, target.id))
        conn.commit()
        update_power(target.id)

        await message.answer(f"⚡ +{value} Очков мощи")

    # ================= TAKE =================
    elif text.startswith("забрать") or text.startswith("зб"):
        if giver_data[3] < 2 and giver.id != OWNER_ID:
            await message.answer("🚫 Нет прав")
            return

        try:
            value = int(message.text.split()[1])
        except:
            await message.answer("Пример: забрать 10 (ответом)")
            return

        cur.execute("UPDATE users SET power = power - ? WHERE user_id=?", (value, target.id))
        conn.commit()
        update_power(target.id)

        await message.answer(f"🔥 -{value} Очков мощи")

    # ================= TRANSFER =================
    elif text.startswith("передать"):
        try:
            value = int(message.text.split()[1])
        except:
            await message.answer("Пример: передать 10 (ответом)")
            return

        cur.execute("SELECT power FROM users WHERE user_id=?", (giver.id,))
        giver_power = cur.fetchone()[0]

        if giver_power < value:
            await message.answer("❌ Недостаточно очков")
            return

        cur.execute("UPDATE users SET power = power - ? WHERE user_id=?", (value, giver.id))
        cur.execute("UPDATE users SET power = power + ? WHERE user_id=?", (value, target.id))
        conn.commit()

        update_power(giver.id)
        update_power(target.id)

        await message.answer(f"🔁 Передано {value} очков")

# ================= OWNER RANK =================

@dp.message()
async def owner_rank(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    if message.text.lower() == "божество+" and message.reply_to_message:
        target = message.reply_to_message.from_user

        cur.execute("UPDATE users SET admin_rank = admin_rank + 1 WHERE user_id=?", (target.id,))
        conn.commit()

        await message.answer(f"👑 {target.username} повышен в ранге")

# ================= RUN =================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
