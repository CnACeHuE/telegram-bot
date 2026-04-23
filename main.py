import logging
from aiogram import Bot, Dispatcher, executor, types
import config, handlers
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# 1. Справка
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def h_help(m: types.Message):
    await m.answer("📖 <b>СПРАВОЧНИК</b>\n━━━━━━━━━━━━━━\n👤 <code>Ми</code>, <code>Профиль</code>\n🎮 <code>Деп</code>, <code>Пвп</code>\n🏛 <code>Клан</code>, <code>Возглавить</code>\n🛡 <code>Кара</code>, <code>Гив</code>, <code>.сбор</code>")

# 2. Игры
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('деп', 'лотерея')))
async def h_dep(m: types.Message): await handlers.cmd_dep(m)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def h_pvp(m: types.Message): await handlers.cmd_pvp(m)

# 3. Кланы
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('возглавить', 'клан')))
async def h_clan(m: types.Message): await handlers.cmd_clan(m)

# 4. Админка (Включая ГИВ)
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def h_admin(m: types.Message): await handlers.cmd_admin(m)

# 5. Профиль и Топы (через импорт handlers)
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def h_profile(m: types.Message): await handlers.cmd_profile(m)

# 6. Кнопки ПВП (Callback)
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def h_pvp_btn(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    winner = random.choice([creator_id, c.from_user.id])
    loser = c.from_user.id if winner == creator_id else creator_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser))
    await c.message.edit_text(f"⚔️ Победил: {handlers.get_mention(winner, 'Чемпион')}\nВыигрыш: <code>{bet}</code> 💠")

# 7. Опыт (ВСЕГДА В КОНЦЕ)
@dp.message_handler(content_types=['text'])
async def h_xp(m: types.Message):
    db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) "
               "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1", (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
