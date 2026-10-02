from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.config import settings

router=Router()

def menu():
    rows=[]
    if settings.telegram_webapp_url:
        rows.append([InlineKeyboardButton(text="Открыть VELORA",web_app=WebAppInfo(url=settings.telegram_webapp_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

@router.message(CommandStart())
async def start(message:Message):
    await message.answer(
        "VELORA\n\nРадар выгодных объявлений для перекупов.\n"
        "Ищи по названию и полному описанию, смотри Market Price, Deal Score и историю цены.",
        reply_markup=menu())

@router.message(Command("help"))
async def help_cmd(message:Message):
    await message.answer("VELORA: поиск, рыночная цена, Deal Score, история цены и алерты. Открой Mini App.",reply_markup=menu())

@router.message()
async def fallback(message:Message):
    if message.text:
        await message.answer("Используй Mini App для поиска и настройки алертов.",reply_markup=menu())

async def run_bot():
    bot=Bot(settings.telegram_bot_token)
    dp=Dispatcher(); dp.include_router(router)
    await dp.start_polling(bot)
