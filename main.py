import logging
import random
from aiogram import Bot, Dispatcher, executor, types
import config, handlers, utils
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def h_profile(m: types.Message): await handlers.cmd_profile(m)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('деп', 'лотерея')))
async def h_dep(m: types.Message): await handlers.cmd_dep(m)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def h_pvp(m: types.Message): await handlers.cmd_pvp(m)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.сбор', 'гив', 'кара')))
async def h_admin(m: types.Message): await handlers.cmd_admin(m)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def h_pvp_btn(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (creator_id,), fetch=True)
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,), fetch=True)
    if not p1 or p1[0] < bet or not p2 or p2[0] < bet: return await c.answer("Недостаточно мощи!", show_alert=True)

    winner = random.choice([creator_id, c.from_user.id])
    loser = c.from_user.id if winner == creator_id else creator_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser))
    await c.message.edit_text(f"⚔️ Победил: {utils.get_mention(winner, 'Чемпион')}\nВыигрыш: <code>{bet}</code> 💠")

@dp.message_handler(content_types=['text'])
async def h_xp(m: types.Message):
    if m.text and not m.text.startswith(('/', '.', '!')):
        db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) "
                   "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1", (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
