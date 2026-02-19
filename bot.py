import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from database import init_db, user_exists, add_user

# Настройки
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8080))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Машина состояний
class Form(StatesGroup):
    surname = State()
    name = State()
    patronymic = State()

# Хендлеры
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    init_db()
    if user_exists(message.from_user.id):
        await message.answer("Вы уже зарегистрированы в системе!")
    else:
        await message.answer("Привет! Давайте заполним анкету. Напишите вашу фамилию:")
        await state.set_state(Form.surname)

@dp.message(Form.surname)
async def process_surname(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Фамилия слишком короткая. Попробуйте еще раз:")
        return
    await state.update_data(surname=message.text)
    await message.answer("Теперь введите ваше имя:")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Имя слишком короткое. Попробуйте еще раз:")
        return
    await state.update_data(name=message.text)
    await message.answer("Введите отчество (или напишите 'нет'):")
    await state.set_state(Form.patronymic)

@dp.message(Form.patronymic)
async def process_patronymic(message: types.Message, state: FSMContext):
    patronymic = message.text if message.text.lower() != 'нет' else None
    data = await state.get_data()
    success = add_user(
        telegram_id=message.from_user.id,
        surname=data['surname'],
        name=data['name'],
        patronymic=patronymic
    )
    if success:
        await message.answer("Спасибо! Ваши данные сохранены.")
    else:
        await message.answer("Ошибка сохранения.")
    await state.clear()

# Веб-сервер
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
setup_application(app, dp, bot=bot)

async def on_startup(bot: Bot):  # ← ВАЖНО: (bot: Bot)
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(bot: Bot):  # ← ВАЖНО: (bot: Bot)
    await bot.delete_webhook()

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
