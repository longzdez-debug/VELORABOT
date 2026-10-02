from sqlalchemy import select
from app.db import Session, Listing, Alert
from app.scoring import calculate_deal_score

async def evaluate_alerts(listing_id: int) -> list[int]:
    async with Session() as s:
        listing=await s.get(Listing,listing_id)
        if not listing: return []
        prices=(await s.execute(select(Listing.price).where(Listing.id!=listing.id).limit(100))).scalars().all()
        deal=calculate_deal_score(listing.price,list(prices),listing.description_raw)
        alerts=(await s.execute(select(Alert).where(Alert.active.is_(True)))).scalars().all()
        return [a.telegram_user_id for a in alerts if
                (not a.query or a.query.lower() in (listing.title+" "+listing.description_raw).lower()) and
                (a.max_price is None or listing.price<=a.max_price) and deal.score>=a.min_score]
