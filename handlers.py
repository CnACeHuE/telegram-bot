import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from utils import get_mention, get_evo, check_access

# --- ПРОФИЛЬ ---
async def cmd_profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_line = ""
    if c_id:
        c_name = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_name: clan_line = f"🏛 <b>Пантеон:</b> {c_name[0]} (<i>{c_role}</i>)\n"

    await m.answer(
        f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{get_evo(msgs)}</i>\n"
        f"🔱 <b>Ранг:</b> {status}\n{clan_line}"
        f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━"
    )

# --- ЛИДЕРБОРДЫ ---
async def cmd_tops(m: types.Message):
    text = m.text.lower()
    if 'сильнейшие' in text:
        rows = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title, unit = "СИЛЬНЕЙШИЕ 💠", "мощи"
    else:
        rows = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title, unit = "АКТИВЧИКИ 📈", "сообщ."

    res = f"🏆 <b>{title}</b>\n━━━━━━━━━━━━━━\n"
    for i, r in enumerate(rows, 1):
        res += f"{i}. {get_mention(r[0], r[1])} — <code>{r[2]}</code> {unit}\n"
    await m.answer(res + "━━━━━━━━━━━━━━")

# --- АДМИНКА ---
async def cmd_admin(m: types.Message):
    text = m.text.lower()
    args = text.split()

    if text.startswith('.сбор'):
        if not await check_access(m, 1): return await m.reply("❌ Недостаточно прав!")
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР ОБИТЕЛИ!</b>\n━━━━━━━━━━━━━━\n📢 {m.text[6:] or 'Пробудитесь!'}\n━━━━━━━━━━━━━━{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    target = m.reply_to_message.from_user

    if text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚙️ <b>РАНГ ИЗМЕНЕН</b>\n👤 {get_mention(target.id, target.first_name)} ➜ <code>{val}</code>")

    elif text.startswith('кара'):
        if not await check_access(m, 2): return await m.reply("❌ Недостаточно прав!")
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 500
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n📉 Изъято: <code>{val}</code> 💠")
      
