from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.config import settings

router = Router()

@router.message(CommandStart())
async def start(message: Message):
    if settings.telegram_webapp_url:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть VELORA", web_app=WebAppInfo(url=settings.telegram_webapp_url))
        ]])
        await message.answer(
            "VELORA\n\nРадар выгодных объявлений для перекупов.\n"
            "Ищи объявления, смотри рынок и открывай полное описание продавца.",
            reply_markup=kb
        )
    else:
        await message.answer(
            "VELORA запущена, но Mini App URL ещё не настроен. "
            "Укажи TELEGRAM_WEBAPP_URL в .env."
        )

async def run_bot():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)
