from aiogram import types
from database import db
import config

async def clan_router(m: types.Message): # Переименовали для main.py
    txt = m.text.lower().split()
    if not txt: return
    cmd = txt[0]
    uid = m.from_user.id

    # --- ИНФОРМАЦИЯ О ПАНТЕОНЕ ---
    if cmd in ['пантеон', 'клан']:
        user = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = ?", (uid,))
        if not user or user[0] == 0:
            return await m.answer("👣 Вы — странник без обители. Создайте свой <b>Пантеон</b> или дождитесь призыва.")
        
        clan = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = ?", (user[0],))
        members = db.fetchall("SELECT username, clan_role FROM users WHERE clan_id = ?", (user[0],))
        
        res = f"🏛 <b>Пантеон: «{clan[0]}»</b>\n"
        res += f"━━━━━━━━━━━━━━\n"
        res += f"🔱 Ваш статус: <b>{user[1]}</b>\n"
        res += f"💰 Казна: <code>{clan[1]}</code> 💠\n"
        res += f"🌟 Уровень: <code>{clan[2]}</code>\n\n"
        res += f"👥 <b>Небожители ({len(members)}):</b>\n"
        
        for i, mem in enumerate(members, 1):
            res += f"{i}. {mem[0]} — <i>{mem[1]}</i>\n"
        
        await m.answer(res + "━━━━━━━━━━━━━━")

    # --- ОСНОВАТЬ ПАНТЕОН ---
    elif cmd == 'создать' and len(txt) > 2 and txt[1] == 'пантеон':
        name = " ".join(txt[2:])
        user = db.execute("SELECT clan_id, power_points FROM users WHERE user_id = ?", (uid,))
        
        if user[0] != 0: return await m.answer("🌌 Вы уже состоите в Пантеоне.")
        if user[1] < 5000: return await m.answer("❌ Нужно 5000 💠 для возведения храма.")

        db.execute("UPDATE users SET power_points = power_points - 5000 WHERE user_id = ?", (uid,))
        db.execute("INSERT INTO clans (clan_name, creator_id) VALUES (?, ?)", (name, uid))
        new_id = db.execute("SELECT clan_id FROM clans WHERE clan_name = ?", (name,))[0]
        db.execute("UPDATE users SET clan_id = ?, clan_role = 'Бог' WHERE user_id = ?", (new_id, uid))
        
        await m.answer(f"🏛 <b>Пантеон «{name}» воздвигнут!</b>\n{m.from_user.first_name}, отныне вы его <b>Бог</b>.")

    # --- ПРИЗВАТЬ (Приглашение) ---
    elif cmd == 'призвать' and m.reply_to_message:
        boss = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = ?", (uid,))
        if boss[1] != 'Бог': return await m.answer("👑 Только Бог может призывать в свои чертоги.")
        
        target_id = m.reply_to_message.from_user.id
        target = db.execute("SELECT clan_id FROM users WHERE user_id = ?", (target_id,))
        
        if target[0] != 0: return await m.answer("✨ Этот герой уже обрел свою веру.")
        
        db.execute("UPDATE users SET clan_id = ?, clan_role = 'Небожитель' WHERE user_id = ?", (boss[0], target_id))
        await m.answer(f"☁️ {m.reply_to_message.from_user.first_name} примкнул к вашему Пантеону!")

    # --- ПОПОЛНИТЬ КАЗНУ ---
    elif cmd == 'внести' and len(txt) > 1 and txt[1].isdigit():
        amt = int(txt[1])
        user = db.execute("SELECT clan_id, power_points FROM users WHERE user_id = ?", (uid,))
        
        if user[0] == 0: return await m.answer("👣 У вас нет Пантеона, чтобы жертвовать.")
        if user[1] < amt or amt <= 0: return await m.answer("❌ У вас недостаточно мощи для такого подношения.")
        
        db.execute("UPDATE users SET power_points = power_points - ? WHERE user_id = ?", (amt, uid))
        db.execute("UPDATE clans SET treasury = treasury + ? WHERE clan_id = ?", (amt, user[0]))
        await m.answer(f"💎 <b>Пожертвование:</b>\nВы внесли <code>{amt}</code> 💠 в казну своего Пантеона.")
        
