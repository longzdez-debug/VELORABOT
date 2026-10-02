import hashlib
import time

from aiogram import Bot
from sqlalchemy import select, or_

from app.db import Session, Listing, Alert, NotificationEvent
from app.scoring import calculate_deal_score
from app.config import settings


def _match(alert: Alert, listing: Listing, score: int) -> bool:
    text = f"{listing.title} {listing.description_raw}".lower()
    if alert.query:
        terms = [x for x in alert.query.lower().split() if x]
        if not all(term in text for term in terms):
            return False
    if alert.max_price is not None and listing.price > alert.max_price:
        return False
    if alert.region and alert.region.lower() not in listing.location.lower():
        return False
    return score >= alert.min_score


async def evaluate_and_notify(listing_id: int, event_type: str = "NEW") -> int:
    if not settings.telegram_bot_token:
        return 0

    async with Session() as s:
        listing = await s.get(Listing, listing_id)
        if not listing:
            return 0

        prices = list((await s.execute(
            select(Listing.price)
            .where(Listing.id != listing.id)
            .limit(500)
        )).scalars().all())
        deal = calculate_deal_score(listing.price, prices, listing.description_raw)

        alerts = list((await s.execute(
            select(Alert).where(Alert.active.is_(True))
        )).scalars().all())

        targets = []
        fingerprint = hashlib.sha256(
            f"{event_type}:{listing.source}:{listing.source_id}:{listing.price}:{listing.description_raw}".encode()
        ).hexdigest()

        for alert in alerts:
            if not _match(alert, listing, deal.score):
                continue
            exists = (await s.execute(
                select(NotificationEvent).where(
                    NotificationEvent.alert_id == alert.id,
                    NotificationEvent.listing_id == listing.id,
                    NotificationEvent.fingerprint == fingerprint,
                )
            )).scalar_one_or_none()
            if exists:
                continue
            s.add(NotificationEvent(
                alert_id=alert.id,
                listing_id=listing.id,
                event_type=event_type,
                fingerprint=fingerprint,
            ))
            targets.append(alert.telegram_user_id)
        await s.commit()

    if not targets:
        return 0

    tag = {"NEW": "🆕", "PRICE_CHANGED": "📉", "UPDATED": "♻️"}.get(event_type, "🔔")
    market = f"{deal.market_price:g} {listing.currency}" if deal.market_price is not None else "—"
    deviation = f"{deal.deviation_pct:.1f}%" if deal.deviation_pct is not None else "—"
    text = (
        f"{tag} VELORA {event_type}\n\n"
        f"{listing.title}\n"
        f"Цена: {listing.price:g} {listing.currency}\n"
        f"Market: {market}\n"
        f"Deal Score: {deal.score}/100\n"
        f"Отклонение: {deviation}\n"
        f"Риск: {deal.risk}/100 · Ликвидность: {deal.liquidity}/100\n\n"
        f"{listing.description_raw[:1800] or 'Описание не указано'}\n\n"
        f"{listing.url}"
    )

    bot = Bot(settings.telegram_bot_token)
    try:
        for user_id in targets:
            try:
                await bot.send_message(user_id, text)
            except Exception:
                # One blocked/deleted Telegram account must not stop other alerts.
                continue
    finally:
        await bot.session.close()
    return len(targets)
