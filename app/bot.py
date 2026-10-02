from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select
from app.config import settings
from app.db import Session, Alert

router=Router()

def menu():
    rows=[]
    if settings.telegram_webapp_url:
        rows.append([InlineKeyboardButton(text="Открыть VELORA",web_app=WebAppInfo(url=settings.telegram_webapp_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

@router.message(CommandStart())
async def start(message:Message):
    await message.answer(
        "VELORA\n\nРадар выгодных объявлений. Я могу присылать новые и подешевевшие объявления с KUFAR.\n\n"
        "Команда: /watch iphone 15 | max=2000 | score=70\n"
        "/alerts — мои активные радары.",
        reply_markup=menu())

@router.message(Command("help"))
async def help_cmd(message:Message):
    await message.answer(
        "Команды VELORA:\n"
        "/watch <запрос> | max=цена | score=0..100\n"
        "/alerts — список радаров\n"
        "/stop <id> — отключить радар\n\n"
        "Описание объявления сохраняется полностью и используется при поиске/оценке.",
        reply_markup=menu())

@router.message(Command("watch"))
async def watch(message:Message):
    raw=(message.text or "").partition(" ")[2].strip()
    parts=[p.strip() for p in raw.split("|") if p.strip()]
    query=parts[0] if parts else ""
    if not query:
        await message.answer("Пример: /watch iphone 15 | max=2000 | score=70")
        return
    max_price=None; min_score=70
    for part in parts[1:]:
        k,sep,v=part.partition("=")
        if not sep: continue
        try:
            if k.strip().lower()=="max": max_price=float(v)
            elif k.strip().lower()=="score": min_score=max(0,min(100,int(v)))
        except ValueError: pass
    async with Session() as s:
        x=Alert(telegram_user_id=message.from_user.id,query=query,max_price=max_price,min_score=min_score)
        s.add(x); await s.commit(); await s.refresh(x)
    await message.answer(f"Радар #{x.id} включён: {query}\nmax={max_price or 'без лимита'} · score≥{min_score}")

@router.message(Command("alerts"))
async def alerts(message:Message):
    async with Session() as s:
        rows=(await s.execute(select(Alert).where(
            Alert.telegram_user_id==message.from_user.id,Alert.active.is_(True)).order_by(Alert.id))).scalars().all()
    if not rows:
        await message.answer("Активных радаров нет. Создай: /watch iphone 15 | max=2000")
        return
    await message.answer("\n".join(f"#{x.id} · {x.query} · max={x.max_price or '—'} · score≥{x.min_score}" for x in rows))

@router.message(Command("stop"))
async def stop(message:Message):
    raw=(message.text or "").partition(" ")[2].strip()
    try: alert_id=int(raw)
    except ValueError:
        await message.answer("Пример: /stop 12"); return
    async with Session() as s:
        x=await s.get(Alert,alert_id)
        if not x or x.telegram_user_id!=message.from_user.id:
            await message.answer("Радар не найден"); return
        x.active=False; await s.commit()
    await message.answer(f"Радар #{alert_id} отключён.")

@router.message()
async def fallback(message:Message):
    if message.text:
        await message.answer("Используй /watch для радара или открой Mini App.",reply_markup=menu())

async def run_bot():
    bot=Bot(settings.telegram_bot_token)
    dp=Dispatcher(); dp.include_router(router)
    try: await dp.start_polling(bot)
    finally: await bot.session.close()
