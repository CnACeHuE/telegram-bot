from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
import config

async def clan_router(m: types.Message):
    text = m.text.lower()
    args = m.text.split()
    u_id = m.from_user.id

    # --- ТОПЫ: СИЛЬНЕЙШИЕ И АКТИВЧИКИ ---
    if text == 'сильнейшие':
        users = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        res = "💠 <b>СИЛЬНЕЙШИЕ В ОБИТЕЛИ:</b>\n\n"
        for i, row in enumerate(users, 1):
            res += f"{i}. <b>{row[0]}</b> — <code>{row[1]}</code> мощь\n"
        return await m.answer(res)

    elif text == 'активчики':
        users = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        res = "📈 <b>САМЫЕ АКТИВНЫЕ:</b>\n\n"
        for i, row in enumerate(users, 1):
            res += f"{i}. <b>{row[0]}</b> — <code>{row[1]}</code> сообщ.\n"
        return await m.answer(res)

    # --- ТОП ПАНТЕОНОВ ---
    elif text in ['топ пантеонов', 'топ кланов']:
        clans = db.fetchall("SELECT clan_name, level, treasury FROM clans ORDER BY level DESC, treasury DESC LIMIT 10")
        if not clans: return await m.reply("🏛 Пантеонов еще не основано...")
        res = "🏆 <b>ВЕЛИКИЕ ПАНТЕОНЫ:</b>\n\n"
        for i, row in enumerate(clans, 1):
            res += f"{i}. <b>{row[0]}</b> — {row[1]} лвл ({row[2]} 💠)\n"
        return await m.answer(res)

    # --- ВОЗГЛАВИТЬ ПАНТЕОН (Создание) ---
    elif text.startswith('возглавить пантеон'):
        clan_name = " ".join(args[2:])
        if not clan_name:
            return await m.reply("⚠️ Введите название: <code>возглавить пантеон Название</code>")
        
        user_data = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (u_id,))
        if user_data and user_data[1]: return await m.reply("❌ Вы уже состоите в клане!")
        if not user_data or user_data[0] < 5000: return await m.reply("❌ Нужно 5000 мощи для основания!")

        check_name = db.execute("SELECT clan_id FROM clans WHERE clan_name = %s", (clan_name,))
        if check_name: return await m.reply("❌ Пантеон с таким названием уже существует!")

        try:
            # Исправленная вставка: получаем ID сразу
            db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s)", (clan_name, u_id))
            # Ищем ID созданного клана по лидеру
            new_clan = db.execute("SELECT clan_id FROM clans WHERE leader_id = %s ORDER BY clan_id DESC", (u_id,))
            
            if new_clan:
                db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава', power_points = power_points - 5000 WHERE user_id = %s", (new_clan[0], u_id))
                await m.answer(f"🏛 <b>Пантеон «{clan_name}» основан!</b>\nГлава: {m.from_user.first_name}")
            else:
                await m.reply("❌ Ошибка: клан создался, но не найден. Напиши админу.")
        except Exception as e:
            await m.reply(f"❌ Ошибка при создании: {e}")

    # --- ИНФОРМАЦИЯ ---
    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if not u or not u[0]: return await m.reply("🕵️ Вы пока странник. Используйте <code>возглавить пантеон [имя]</code>")
        
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        if not c: return await m.reply("❌ Ошибка: данные пантеона не найдены.")
        
        res = (f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n"
               f"👤 <b>Ваша роль:</b> {u[1]}\n"
               f"📈 <b>Уровень:</b> {c[2]}\n"
               f"💰 <b>Казна:</b> <code>{c[1]}</code> 💠\n━━━━━━━━━━━━━━")
        await m.answer(res)

    # --- ПРИНЯТЬ (.принять) ---
    elif text.startswith('.принять'):
        if not m.reply_to_message: return await m.reply("Ответьте на сообщение того, кого зовете!")
        
        leader_data = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if not leader_data or leader_data[1] != 'Глава': 
            return await m.reply("❌ Только Глава может принимать новых богов!")
            
        target_id = m.reply_to_message.from_user.id
        target_clan = db.execute("SELECT clan_id FROM users WHERE user_id = %s", (target_id,))
        if target_clan and target_clan[0]: return await m.reply("❌ Этот игрок уже в другом Пантеоне!")

        db.execute("UPDATE users SET clan_id = %s, clan_role = 'Участник' WHERE user_id = %s", (leader_data[0], target_id))
        await m.answer(f"🤝 {m.reply_to_message.from_user.first_name} теперь часть Пантеона!")

    # --- КРАХ ---
    elif text == 'крах пантеона':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if not u or u[1] != 'Глава': return await m.reply("❌ Только Глава может объявить Крах!")

        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("☠️ ПОДТВЕРДИТЬ", callback_data=f"dissolve_{u[0]}"))
        await m.answer("⚠️ Вы уверены, что хотите распустить Пантеон?", reply_markup=kb)

async def dissolve_callback(c: types.CallbackQuery):
    clan_id = int(c.data.split('_')[1])
    clan_data = db.execute("SELECT leader_id, treasury FROM clans WHERE clan_id = %s", (clan_id,))
    
    if not clan_data or c.from_user.id != clan_data[0]:
        return await c.answer("❌ Нет власти!", show_alert=True)

    loot = int(clan_data[1] * 0.65)
    db.execute("UPDATE users SET power_points = power_points + %s, clan_id = NULL, clan_role = NULL WHERE user_id = %s", (loot, c.from_user.id))
    db.execute("UPDATE users SET clan_id = NULL, clan_role = NULL WHERE clan_id = %s", (clan_id,))
    db.execute("DELETE FROM clans WHERE clan_id = %s", (clan_id,))
    await c.message.edit_text(f"💥 Пантеон пал! Глава забрал {loot} 💠")
    
