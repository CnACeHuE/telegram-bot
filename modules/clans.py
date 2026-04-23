from aiogram import types
from database import db
import config

async def clan_router(m: types.Message):
    text = m.text.lower()
    args = m.text.split()
    u_id = m.from_user.id

    # --- СОЗДАНИЕ КЛАНА ---
    if text.startswith('создать'):
        if len(args) < 2:
            return await m.reply("⚠️ Введите название: <code>создать Название</code>")
        
        clan_name = " ".join(args[1:])
        user_data = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (u_id,))
        
        if user_data[1]: return await m.reply("❌ Вы уже состоите в клане!")
        if user_data[0] < 5000: return await m.reply("❌ Нужно минимум 5000 мощи для основания Пантеона!")

        try:
            # Создаем клан
            db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s)", (clan_name, u_id))
            new_clan = db.execute("SELECT clan_id FROM clans WHERE clan_name = %s", (clan_name,))
            # Привязываем лидера к клану
            db.execute("UPDATE users SET clan_id = %s, clan_role = 'Лидер', power_points = power_points - 5000 WHERE user_id = %s", (new_clan[0], u_id))
            
            await m.answer(f"🏛 <b>Пантеон «{clan_name}» основан!</b>\nС вашего баланса списано 5000 💠")
        except:
            await m.reply("❌ Клан с таким названием уже существует.")

    # --- ИНФОРМАЦИЯ О КЛАНЕ ---
    elif text == 'клан':
        u = db.execute("SELECT clan_id FROM users WHERE user_id = %s", (u_id,))
        if not u or not u[0]:
            return await m.reply("🕵️ Вы пока странник. Используйте <code>создать [имя]</code>")

        c = db.execute("SELECT clan_name, treasury, level, leader_id FROM clans WHERE clan_id = %s", (u[0],))
        leader = db.execute("SELECT username FROM users WHERE user_id = %s", (c[3],))
        
        res = (f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"👑 <b>Глава:</b> {leader[0]}\n"
               f"📈 <b>Уровень:</b> {c[2]}\n"
               f"💰 <b>Казна:</b> <code>{c[1]}</code> 💠\n"
               f"━━━━━━━━━━━━━━\n"
               f"📍 <i>Чтобы внести вклад: <code>депозит [сумма]</code></i>")
        await m.answer(res)

    # --- ПОПОЛНЕНИЕ КАЗНЫ ---
    elif text.startswith('депозит'):
        if len(args) < 2 or not args[1].isdigit():
            return await m.reply("⚠️ Укажите сумму: <code>депозит 100</code>")
        
        amount = int(args[1])
        u = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (u_id,))
        
        if not u[1]: return await m.reply("❌ Вы не состоите в клане.")
        if u[0] < amount: return await m.reply("❌ У вас нет столько мощи.")

        db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (amount, u_id))
        db.execute("UPDATE clans SET treasury = treasury + %s WHERE clan_id = %s", (amount, u[1]))
        
        await m.answer(f"💎 Вы внесли <code>{amount}</code> 💠 в казну Пантеона!")
        
