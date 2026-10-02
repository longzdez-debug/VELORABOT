from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.config import settings

router = Router()

def menu():
    rows = []
    if settings.telegram_webapp_url:
        rows.append([InlineKeyboardButton(text="Открыть VELORA", web_app=WebAppInfo(url=settings.telegram_webapp_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "VELORA\n\n"
        "Радар выгодных объявлений для перекупов.\n"
        "Ищи по названию и описанию, открывай полное объявление и анализируй рынок.",
        reply_markup=menu()
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer("VELORA отправляет только полезные сигналы. Основной интерфейс — Mini App.")

@router.message()
async def fallback(message: Message):
    if message.text:
        await message.answer("Открой VELORA и используй поиск внутри Mini App.", reply_markup=menu())

async def run_bot():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)
