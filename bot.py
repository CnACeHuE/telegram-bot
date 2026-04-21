@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🔥 Я ТВОЙ КОД ЗАПУСТИЛСЯ")
