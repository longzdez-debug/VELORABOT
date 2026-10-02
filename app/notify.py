import hashlib
from aiogram import Bot
from sqlalchemy import select
from app.db import Session, Listing, Alert, NotificationEvent
from app.scoring import calculate_deal_score
from app.config import settings

async def evaluate_and_notify(listing_id:int,event_type="NEW"):
    if not settings.telegram_bot_token:return 0
    async with Session() as s:
        x=await s.get(Listing,listing_id)
        if not x:return 0
        prices=list((await s.execute(select(Listing.price).where(Listing.id!=x.id).limit(300))).scalars().all())
        d=calculate_deal_score(x.price,prices,x.description_raw)
        alerts=(await s.execute(select(Alert).where(Alert.active.is_(True)))).scalars().all()
        targets=[]
        for a in alerts:
            if a.query and a.query.lower() not in (x.title+" "+x.description_raw).lower():continue
            if a.max_price is not None and x.price>a.max_price:continue
            if a.region and a.region.lower() not in x.location.lower():continue
            if d.score<a.min_score:continue
            fp=hashlib.sha256(f"{event_type}:{x.price}:{x.description_raw}".encode()).hexdigest()
            exists=(await s.execute(select(NotificationEvent).where(
                NotificationEvent.alert_id==a.id,NotificationEvent.listing_id==x.id,
                NotificationEvent.fingerprint==fp))).scalar_one_or_none()
            if exists:continue
            s.add(NotificationEvent(alert_id=a.id,listing_id=x.id,event_type=event_type,fingerprint=fp))
            targets.append(a.telegram_user_id)
        await s.commit()
    if not targets:return 0
    bot=Bot(settings.telegram_bot_token)
    try:
        tag={"NEW":"🆕","PRICE_CHANGED":"📉","UPDATED":"♻️"}.get(event_type,"🔔")
        text=(f"{tag} VELORA {event_type}\n\n{x.title}\n"
              f"Цена: {x.price:g} {x.currency}\nMarket: {d.market_price:g} {x.currency}\n"
              f"Deal Score: {d.score}/100\nОтклонение: {d.deviation_pct:.1f}%\n"
              f"Риск: {d.risk}/100 · Ликвидность: {d.liquidity}/100\n\n"
              f"{x.description_raw[:1500] or 'Описание не указано'}\n\n{x.url}")
        for user_id in targets: await bot.send_message(user_id,text)
    finally: await bot.session.close()
    return len(targets)
