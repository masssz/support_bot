import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import Command
from config import BOT_TOKEN, ADMINS
import db

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

active_chats = {}

# ---------- КЛАВИАТУРЫ ----------

def user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📨 Создать заявку")],
            [KeyboardButton(text="ℹ️ Моя заявка")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все заявки")]
        ],
        resize_keyboard=True
    )

# ---------- START ----------

@dp.startup()
async def startup():
    await db.init_db()
    print("Bot started")

@dp.message(Command("start"))
async def start(message: types.Message):

    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await db.create_user(user_id, user_id in ADMINS)

        if user_id in ADMINS:
            await message.answer(
                "👨‍💼 Вы зарегистрированы как администратор.",
                reply_markup=admin_menu()
            )
        else:
            await message.answer(
                "👋 Добро пожаловать в поддержку PAXAT VPN!\n\n"
                "📌 Инструкция:\n"
                "1️⃣ Нажмите «📨 Создать заявку»\n"
                "2️⃣ Опишите проблему\n"
                "3️⃣ Дождитесь ответа оператора\n\n"
                "Статус можно проверить кнопкой «ℹ️ Моя заявка».",
                reply_markup=user_menu()
            )
        return

    if user_id in ADMINS:
        await message.answer("Админ панель:", reply_markup=admin_menu())
    else:
        await message.answer("Главное меню:", reply_markup=user_menu())

# ---------- СОЗДАНИЕ ----------

@dp.message(F.text == "📨 Создать заявку")
async def ask_problem(message: types.Message):
    await message.answer("Опишите вашу проблему одним сообщением.")

@dp.message(lambda m: m.from_user.id not in ADMINS)
async def create_ticket(message: types.Message):

    if message.text in ["📨 Создать заявку", "ℹ️ Моя заявка"]:
        return

    existing = await db.get_active_ticket_by_user(message.from_user.id)
    if existing:
        await message.answer("У вас уже есть активная заявка.")
        return

    ticket_id = await db.create_ticket(message.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Взять",
            callback_data=f"take_{ticket_id}"
        )]
    ])

    for admin in ADMINS:
        await bot.send_message(
            admin,
            f"🆕 Заявка #{ticket_id}\n"
            f"User: {message.from_user.full_name}\n"
            f"{message.text}",
            reply_markup=kb
        )

    await message.answer("✅ Заявка создана.")

# ---------- МОЯ ЗАЯВКА ----------

@dp.message(F.text == "ℹ️ Моя заявка")
async def my_ticket(message: types.Message):

    ticket = await db.get_active_ticket_by_user(message.from_user.id)

    if not ticket:
        await message.answer("У вас нет активных заявок.")
        return

    await message.answer(
        f"Заявка #{ticket.id}\n"
        f"Статус: {ticket.status}"
    )

# ---------- ВСЕ ЗАЯВКИ ----------

@dp.message(F.text == "📋 Все заявки")
async def all_tickets(message: types.Message):

    if message.from_user.id not in ADMINS:
        return

    tickets = await db.get_all_tickets()

    if not tickets:
        await message.answer("Заявок нет.")
        return

    for ticket in tickets:
        kb = None
        if ticket.status == "open":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Взять",
                    callback_data=f"take_{ticket.id}"
                )]
            ])

        await message.answer(
            f"Заявка #{ticket.id}\n"
            f"User: {ticket.user_id}\n"
            f"Статус: {ticket.status}",
            reply_markup=kb
        )

# ---------- ВЗЯТЬ ----------

@dp.callback_query(F.data.startswith("take_"))
async def take_ticket(callback: types.CallbackQuery):

    ticket_id = int(callback.data.split("_")[1])
    ticket = await db.get_ticket(ticket_id)

    if not ticket or ticket.status != "open":
        await callback.answer("Уже занята.", show_alert=True)
        return

    await db.assign_ticket(ticket_id, callback.from_user.id)

    active_chats[ticket.user_id] = callback.from_user.id
    active_chats[callback.from_user.id] = ticket.user_id

    close_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data=f"close_{ticket_id}"
        )]
    ])

    await bot.send_message(ticket.user_id, "Оператор подключился.")
    await callback.message.edit_text(
        f"Вы взяли заявку #{ticket_id}",
        reply_markup=close_kb
    )

    await callback.answer()

# ---------- ЗАКРЫТЬ ----------

@dp.callback_query(F.data.startswith("close_"))
async def close_ticket(callback: types.CallbackQuery):

    ticket_id = int(callback.data.split("_")[1])
    ticket = await db.get_ticket(ticket_id)

    if not ticket:
        return

    await db.close_ticket(ticket_id)

    active_chats.pop(ticket.user_id, None)
    active_chats.pop(ticket.admin_id, None)

    await bot.send_message(ticket.user_id, "✅ Заявка закрыта.")
    await callback.message.edit_text(f"Заявка #{ticket_id} закрыта.")

    await callback.answer("Закрыто")

# ---------- ЧАТ ----------

@dp.message()
async def relay(message: types.Message):

    user_id = message.from_user.id

    if user_id in active_chats:
        await bot.send_message(
            active_chats[user_id],
            message.text
        )

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))