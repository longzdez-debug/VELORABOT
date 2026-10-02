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
    return or_(
        Listing.title.ilike(needle),
        Listing.description_raw.ilike(needle),
        Listing.model.ilike(needle),
    )


def _stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "p10": _percentile(values, 0.10),
        "p25": _percentile(values, 0.25),
        "p50": _percentile(values, 0.50),
        "p75": _percentile(values, 0.75),
        "p90": _percentile(values, 0.90),
        "median": median(values) if values else None,
    }


async def market_snapshot(q: str = "", days: int = 30, limit: int = 5000) -> dict:
    now = datetime.utcnow()
    window = max(1, min(days, 90))
    since = now - timedelta(days=window)
    previous_since = since - timedelta(days=window)

    async with Session() as session:
        filt = _filter(q)
        stmt = select(Listing).where(Listing.last_seen_at >= since)
        if filt is not None:
            stmt = stmt.where(filt)
        rows = list((await session.execute(stmt.limit(limit))).scalars().all())
        ids = [x.id for x in rows]

        history_stmt = select(PriceHistory).where(
            PriceHistory.observed_at >= previous_since,
            PriceHistory.observed_at <= since,
        )
        if ids:
            history_stmt = history_stmt.where(PriceHistory.listing_id.in_(ids))
        else:
            history_stmt = history_stmt.where(False)
        history = list((await session.execute(history_stmt)).scalars().all())

    current = [float(x.price) for x in rows if x.price and x.price > 0]
    previous = [float(x.price) for x in history if x.price and x.price > 0]
    cur = _stats(current)
    prev = _stats(previous)
    trend_pct = None
    if cur["median"] and prev["median"]:
        trend_pct = (cur["median"] - prev["median"]) / prev["median"] * 100

    return {
        "query": q,
        "days": window,
        **cur,
        "previous": prev,
        "previous_median": prev["median"],
        "trend_pct": trend_pct,
        "supply": len(current),
        "observation_quality": "high" if len(current) >= 100 else "medium" if len(current) >= 25 else "low",
    }


async def market_timeseries(q: str = "", days: int = 30) -> list[dict]:
    now = datetime.utcnow()
    since = now - timedelta(days=max(7, min(days, 90)))
    async with Session() as session:
        filt = _filter(q)
        listing_stmt = select(Listing.id)
        if filt is not None:
            listing_stmt = listing_stmt.where(filt)
        ids = list((await session.execute(listing_stmt)).scalars().all())
        if not ids:
            return []
        history = list((await session.execute(
            select(PriceHistory)
            .where(PriceHistory.listing_id.in_(ids), PriceHistory.observed_at >= since)
            .order_by(PriceHistory.observed_at)
        )).scalars().all())

    buckets: dict[str, list[float]] = {}
    for h in history:
        if h.price and h.price > 0:
            buckets.setdefault(h.observed_at.strftime("%Y-%m-%d"), []).append(float(h.price))
    return [
        {"date": key, **_stats(values)}
        for key, values in sorted(buckets.items())
    ]
