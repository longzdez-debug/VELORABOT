from aiogram import Bot
from sqlalchemy import select
from app.db import Session, Listing, Alert
from app.scoring import calculate_deal_score
from app.config import settings

async def evaluate_and_notify(listing_id: int):
    if not settings.telegram_bot_token: return 0
    async with Session() as s:
        x=await s.get(Listing,listing_id)
        if not x: return 0
        prices=list((await s.execute(select(Listing.price).where(Listing.id!=x.id).limit(300))).scalars().all())
        d=calculate_deal_score(x.price,prices,x.description_raw)
        alerts=(await s.execute(select(Alert).where(Alert.active.is_(True)))).scalars().all()
        targets=[a for a in alerts if
                 (not a.query or a.query.lower() in (x.title+" "+x.description_raw).lower()) and
                 (a.max_price is None or x.price<=a.max_price) and
                 (not a.region or a.region.lower() in x.location.lower()) and d.score>=a.min_score]
    if not targets: return 0
    bot=Bot(settings.telegram_bot_token)
    try:
        text=(f"🔥 VELORA DEAL\n\n{x.title}\n"
              f"Цена: {x.price:g} {x.currency}\n"
              f"Market: {d.market_price:g} {x.currency}\n"
              f"Deal Score: {d.score}/100\n"
              f"Отклонение: {d.deviation_pct:.1f}%\n"
              f"Риск: {d.risk}/100 · Ликвидность: {d.liquidity}/100\n\n"
              f"{x.description_raw[:1000]}\n\n{x.url}")
        for a in targets:
            await bot.send_message(a.telegram_user_id,text)
    finally:
        await bot.session.close()
    return len(targets)
