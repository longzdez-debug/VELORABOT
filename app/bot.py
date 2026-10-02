from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta
from sqlalchemy import select
from app.config import settings
from app.db import Session, Alert, UserSubscription
from app.alert_index import AlertIndex

PRO_PRICE_STARS = 500
PRO_DAYS = 30

router = Router()


def menu():
    rows = []
    if settings.telegram_webapp_url:
        rows.append([InlineKeyboardButton(text="Открыть VELORA", web_app=WebAppInfo(url=settings.telegram_webapp_url))])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "VELORA — радар выгодных объявлений.\n\n"
        "Создай радар: /watch iphone 15 | max=2000 | score=70\n"
        "/alerts — активные радары\n"
        "/pro — VELORA Pro\n"
        "/stop <id> — выключить радар",
        reply_markup=menu(),
    )


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "VELORA\n\n"
        "/watch <запрос> | max=цена | score=0..100\n"
        "/alerts — активные радары\n"
        "/pro — VELORA Pro\n"
        "/stop <id> — отключить радар\n\n"
        "Поиск учитывает название и полное оригинальное описание объявления.",
        reply_markup=menu(),
    )


@router.message(Command("watch"))
async def watch(message: Message):
    raw = (message.text or "").partition(" ")[2].strip()
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    query = parts[0] if parts else ""
    if not query:
        await message.answer("Пример: /watch iphone 15 | max=2000 | score=70")
        return

    max_price = None
    min_score = 70
    for part in parts[1:]:
        key, sep, value = part.partition("=")
        if not sep:
            continue
        try:
            if key.strip().lower() == "max":
                max_price = float(value)
            elif key.strip().lower() == "score":
                min_score = max(0, min(100, int(value)))
        except ValueError:
            continue

    async with Session() as s:
        alert = Alert(
            telegram_user_id=message.from_user.id,
            query=query,
            max_price=max_price,
            min_score=min_score,
        )
        s.add(alert)
        await s.commit()
        await s.refresh(alert)
    index = AlertIndex()
    try:
        await index.add(alert)
    finally:
        await index.close()

    await message.answer(
        f"Радар #{alert.id} включён\n"
        f"Запрос: {query}\n"
        f"max: {max_price if max_price is not None else 'без лимита'} · score ≥ {min_score}"
    )


@router.message(Command("pro"))
async def pro(message: Message):
    await message.answer_invoice(
        title="VELORA Pro",
        description="30 дней расширенного радара, Deal Score, Market Intelligence и Hunt Mode.",
        payload=f"velora-pro:{message.from_user.id}:{PRO_DAYS}",
        currency="XTR",
        prices=[LabeledPrice(label="VELORA Pro · 30 дней", amount=PRO_PRICE_STARS)],
        provider_token="",
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    if not query.invoice_payload.startswith("velora-pro:"):
        await query.answer(ok=False, error_message="Неизвестный товар")
        return
    await query.answer(ok=True)


@router.message(lambda message: message.successful_payment is not None)
async def successful_payment(message: Message):
    payment = message.successful_payment
    async with Session() as s:
        sub = await s.get(UserSubscription, message.from_user.id)
        now = datetime.utcnow()
        if not sub:
            sub = UserSubscription(telegram_user_id=message.from_user.id, plan="pro")
            s.add(sub)
        base = sub.active_until if sub.active_until and sub.active_until > now else now
        sub.plan = "pro"
        sub.active_until = base + timedelta(days=PRO_DAYS)
        sub.telegram_charge_id = payment.telegram_payment_charge_id
        await s.commit()
    await message.answer("VELORA Pro активирован на 30 дней. Открой Mini App для доступа к расширенной аналитике.")


@router.message(Command("alerts"))
async def alerts(message: Message):
    async with Session() as s:
        rows = list((await s.execute(
            select(Alert).where(
                Alert.telegram_user_id == message.from_user.id,
                Alert.active.is_(True),
            ).order_by(Alert.id)
        )).scalars().all())
    if not rows:
        await message.answer("Активных радаров нет. Создай: /watch iphone 15 | max=2000")
        return
    await message.answer(
        "\n".join(
            f"#{x.id} · {x.query} · max={x.max_price if x.max_price is not None else '—'} · score≥{x.min_score}"
            for x in rows
        )
    )


@router.message(Command("stop"))
async def stop(message: Message):
    raw = (message.text or "").partition(" ")[2].strip()
    try:
        alert_id = int(raw)
    except ValueError:
        await message.answer("Пример: /stop 12")
        return
    async with Session() as s:
        alert = await s.get(Alert, alert_id)
        if not alert or alert.telegram_user_id != message.from_user.id:
            await message.answer("Радар не найден")
            return
        alert.active = False
        await s.commit()
    index = AlertIndex()
    try:
        await index.remove(alert)
    finally:
        await index.close()
    await message.answer(f"Радар #{alert_id} отключён.")


@router.message()
async def fallback(message: Message):
    if message.text:
        await message.answer("Используй /watch для радара или открой Mini App.", reply_markup=menu())


async def run_bot():
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
