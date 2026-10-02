from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from sqlalchemy import select, or_

from app.db import Listing, PriceHistory, Session


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _filter(q: str):
    if not q.strip():
        return None
    needle = f"%{q.strip()}%"
    return or_(Listing.title.ilike(needle), Listing.description_raw.ilike(needle))


async def market_snapshot(q: str = "", days: int = 30, limit: int = 5000) -> dict:
    now = datetime.utcnow()
    window = max(1, min(days, 90))
    since = now - timedelta(days=window)
    previous_since = since - timedelta(days=window)

    async with Session() as session:
        stmt = select(Listing).where(Listing.last_seen_at >= since).limit(limit)
        filt = _filter(q)
        if filt is not None:
            stmt = select(Listing).where(filt, Listing.last_seen_at >= since).limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())

        history_stmt = select(PriceHistory).where(PriceHistory.observed_at >= previous_since)
        history = list((await session.execute(history_stmt)).scalars().all())

    current = [float(x.price) for x in rows if x.price and x.price > 0]
    previous = [float(x.price) for x in history if x.price and x.price > 0]
    current_median = median(current) if current else None
    previous_median = median(previous) if previous else None
    trend_pct = None
    if current_median and previous_median:
        trend_pct = (current_median - previous_median) / previous_median * 100

    return {
        "query": q,
        "days": window,
        "count": len(current),
        "p10": _percentile(current, 0.10),
        "p25": _percentile(current, 0.25),
        "p50": _percentile(current, 0.50),
        "p75": _percentile(current, 0.75),
        "p90": _percentile(current, 0.90),
        "median": current_median,
        "previous_median": previous_median,
        "trend_pct": trend_pct,
        "supply": len(current),
        "observation_quality": "high" if len(current) >= 100 else "medium" if len(current) >= 25 else "low",
    }
