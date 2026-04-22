from aiogram import types
from database import db
import config

async def clan_commands(m: types.Message):
    txt = m.text.lower().split()
    cmd = txt[0]
    uid = m.from_user.id

    # Основать Пантеон
    if cmd == 'создать' and len(txt) > 2 and txt[1] == 'пантеон':
        name = " ".join(txt[2:])
        user = db.execute("SELECT clan_id, power_points FROM users WHERE user_id = ?", (uid,))
        
        if user[0] != 0: return await m.answer("🌌 Вы уже принадлежите к Пантеону.")
        if user[1] < 5000: return await m.answer("❌ Недостаточно мощи (нужно 5000 💠).")

        db.execute("UPDATE users SET power_points = power_points - 5000 WHERE user_id = ?", (uid,))
        db.execute("INSERT INTO clans (clan_name, creator_id) VALUES (?, ?)", (name, uid))
        new_id = db.execute("SELECT clan_id FROM clans WHERE clan_name = ?", (name,))[0]
        db.execute("UPDATE users SET clan_id = ?, clan_role = 'Бог' WHERE user_id = ?", (new_id, uid))
        
        await m.answer(f"🏛 **Пантеон «{name}» основан!**\nВы признаны его **Богом**.")

    # Пригласить в Пантеон (по реплею)
    elif cmd == 'призвать' and m.reply_to_message:
        boss = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = ?", (uid,))
        if boss[1] != 'Бог': return await m.answer("👑 Только Бог Пантеона может призывать новых небожителей.")
        
        target_id = m.reply_to_message.from_user.id
        target_clan = db.execute("SELECT clan_id FROM users WHERE user_id = ?", (target_id,))
        
        if target_clan[0] != 0: return await m.answer("✨ Этот герой уже нашел свою обитель.")
        
        db.execute("UPDATE users SET clan_id = ?, clan_role = 'Небожитель' WHERE user_id = ?", (boss[0], target_id))
        db.execute("UPDATE clans SET members_count = members_count + 1 WHERE clan_id = ?", (boss[0],))
        await m.answer(f"☁️ {m.reply_to_message.from_user.first_name} теперь **Небожитель** вашего Пантеона!")
      
