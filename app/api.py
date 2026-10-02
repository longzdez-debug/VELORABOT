from fastapi import FastAPI, Query, Header, HTTPException
from datetime import datetime, timedelta
from statistics import median
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_, func, text
from app.db import Session, Listing, Alert, PriceHistory, init_db
from app.api_models import AlertCreate, ProfitRequest
from app.scoring import calculate_deal_score
from app.events import EventBus
from app.config import settings
from app.alert_index import AlertIndex
from app.telegram_auth import validate_init_data, TelegramAuthError
from app.market import market_snapshot

app = FastAPI(title="VELORA API", version="0.3.0")

@app.on_event("startup")
async def startup():
    await init_db()


def resolve_user_id(user_id: int | None, init_data: str | None) -> int:
    if init_data:
        try:
            return validate_init_data(init_data)
        except TelegramAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user_id is None:
        raise HTTPException(status_code=401, detail="Telegram authentication required")
    return user_id

def listing_json(x, d):
    return {"id": x.id, "source": x.source, "title": x.title,
            "description": x.description_raw, "description_raw": x.description_raw,
            "price": x.price, "currency": x.currency, "location": x.location,
            "seller": x.seller, "url": x.url, "image_url": x.image_url,
            "first_seen_at": x.first_seen_at, "last_seen_at": x.last_seen_at,
            "deal_score": d.score, "market_price": d.market_price,
            "deviation_pct": d.deviation_pct, "estimated_profit": d.estimated_profit,
            "liquidity": d.liquidity, "risk": d.risk, "reasons": d.reasons}

@app.get("/health")
async def health():
    return {"ok": True, "service": "velora", "version": "0.3.0"}

@app.get("/ready")
async def ready():
    checks = {"database": False, "redis": False}
    async with Session() as s:
        await s.execute(text("SELECT 1"))
        checks["database"] = True
    bus = EventBus(settings.redis_url)
    try:
        checks["redis"] = bool(await bus.redis.ping())
    finally:
        await bus.close()
    return {"ok": all(checks.values()), "checks": checks}


@app.get("/api/market")
async def market(q: str = Query("", max_length=200), days: int = Query(30, ge=1, le=90)):
    return await market_snapshot(q=q, days=days)


@app.get("/api/market/timeseries")
async def market_timeseries(q: str = Query("", max_length=200), days: int = Query(30, ge=7, le=90)):
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    async with Session() as s:
        stmt = select(PriceHistory).where(PriceHistory.observed_at >= since).order_by(PriceHistory.observed_at)
        history = list((await s.execute(stmt)).scalars().all())
    buckets: dict[str, list[float]] = {}
    for h in history:
        key = h.observed_at.strftime("%Y-%m-%d")
        buckets.setdefault(key, []).append(float(h.price))
    return [{"date": key, "median": median(values), "count": len(values)}
            for key, values in sorted(buckets.items())]


rom fastapi import FastAPI, Query, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_, func, text
from app.db import Session, Listing, Alert, PriceHistory, init_db
from app.api_models import AlertCreate, ProfitRequest
from app.scoring import calculate_deal_score
from app.events import EventBus
from app.config import settings
from app.alert_index import AlertIndex
from app.telegram_auth import validate_init_data, TelegramAuthError
from app.market import market_snapshot

app = FastAPI(title="VELORA API", version="0.3.0")

@app.on_event("startup")
async def startup():
    await init_db()


def resolve_user_id(user_id: int | None, init_data: str | None) -> int:
    if init_data:
        try:
            return validate_init_data(init_data)
        except TelegramAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user_id is None:
        raise HTTPException(status_code=401, detail="Telegram authentication required")
    return user_id

def listing_json(x, d):
    return {"id": x.id, "source": x.source, "title": x.title,
            "description": x.description_raw, "description_raw": x.description_raw,
            "price": x.price, "currency": x.currency, "location": x.location,
            "seller": x.seller, "url": x.url, "image_url": x.image_url,
            "first_seen_at": x.first_seen_at, "last_seen_at": x.last_seen_at,
            "deal_score": d.score, "market_price": d.market_price,
            "deviation_pct": d.deviation_pct, "estimated_profit": d.estimated_profit,
            "liquidity": d.liquidity, "risk": d.risk, "reasons": d.reasons}

@app.get("/health")
async def health():
    return {"ok": True, "service": "velora", "version": "0.3.0"}

@app.get("/ready")
async def ready():
    checks = {"database": False, "redis": False}
    async with Session() as s:
        await s.execute(text("SELECT 1"))
        checks["database"] = True
    bus = EventBus(settings.redis_url)
    try:
        checks["redis"] = bool(await bus.redis.ping())
    finally:
        await bus.close()
    return {"ok": all(checks.values()), "checks": checks}


@app.get("/api/market")
async def market(q: str = Query("", max_length=200)):
    async with Session() as s:
        stmt = select(Listing).order_by(Listing.last_seen_at.desc()).limit(2000)
        if q.strip():
            n = f"%{q.strip()}%"
            stmt = select(Listing).where(
                or_(Listing.title.ilike(n), Listing.description_raw.ilike(n))
            ).order_by(Listing.last_seen_at.desc()).limit(2000)
        rows = list((await s.execute(stmt)).scalars().all())
    prices = sorted(float(x.price) for x in rows if x.price and x.price > 0)
    if not prices:
        return {"count": 0, "median": None, "p10": None, "p25": None, "p50": None, "p75": None, "p90": None}
    def percentile(p: float) -> float:
        pos = (len(prices) - 1) * p
        lo, hi = int(pos), min(int(pos) + 1, len(prices) - 1)
        frac = pos - lo
        return prices[lo] + (prices[hi] - prices[lo]) * frac
    return {
        "count": len(prices),
        "median": percentile(0.5),
        "p10": percentile(0.1),
        "p25": percentile(0.25),
        "p50": percentile(0.5),
        "p75": percentile(0.75),
        "p90": percentile(0.9),
    }


@app.get("/api/stats")
async def stats():
    async with Session() as s:
        count = (await s.execute(select(func.count(Listing.id)))).scalar_one()
        return {"listings": count}

@app.get("/api/listings")
async def listings(q: str = Query("", max_length=200),
                   limit: int = Query(30, ge=1, le=100),
                   min_score: int = Query(0, ge=0, le=100),
                   max_price: float | None = None):
    async with Session() as s:
        stmt = select(Listing).order_by(Listing.first_seen_at.desc()).limit(limit)
        if q.strip():
            n = f"%{q.strip()}%"
            stmt = select(Listing).where(
                or_(Listing.title.ilike(n), Listing.description_raw.ilike(n))
            ).order_by(Listing.first_seen_at.desc()).limit(limit)
        rows = list((await s.execute(stmt)).scalars().all())
        prices = list((await s.execute(select(Listing.price).limit(300))).scalars().all())
        result = [listing_json(x, calculate_deal_score(x.price, prices, x.description_raw)) for x in rows]
        return [x for x in result if x["deal_score"] >= min_score and
                (max_price is None or x["price"] <= max_price)]

@app.get("/api/listings/{listing_id}")
async def listing(listing_id: int):
    async with Session() as s:
        x = await s.get(Listing, listing_id)
        if not x:
            return {"error": "not_found"}
        prices = list((await s.execute(
            select(Listing.price).where(Listing.id != x.id).limit(300)
        )).scalars().all())
        d = calculate_deal_score(x.price, prices, x.description_raw)
        history = (await s.execute(
            select(PriceHistory).where(PriceHistory.listing_id == x.id)
            .order_by(PriceHistory.observed_at)
        )).scalars().all()
        return {**listing_json(x, d),
                "price_history": [{"price": h.price, "observed_at": h.observed_at} for h in history]}

@app.post("/api/alerts")
async def create_alert(payload: AlertCreate, user_id: int | None = None, x_telegram_init_data: str | None = Header(default=None)):
    user_id = resolve_user_id(user_id, x_telegram_init_data)
    async with Session() as s:
        x = Alert(telegram_user_id=user_id, **payload.model_dump())
        s.add(x)
        await s.commit()
        await s.refresh(x)
    index = AlertIndex()
    try:
        await index.add(x)
    finally:
        await index.close()
    return {"id": x.id, "active": x.active}

@app.get("/api/alerts")
async def get_alerts(user_id: int | None = None, x_telegram_init_data: str | None = Header(default=None)):
    user_id = resolve_user_id(user_id, x_telegram_init_data)
    async with Session() as s:
        rows = (await s.execute(
            select(Alert).where(Alert.telegram_user_id == user_id).order_by(Alert.id.desc())
        )).scalars().all()
        return [{"id": x.id, "query": x.query, "max_price": x.max_price,
                 "min_score": x.min_score, "region": x.region, "active": x.active} for x in rows]

@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, user_id: int | None = None, x_telegram_init_data: str | None = Header(default=None)):
    user_id = resolve_user_id(user_id, x_telegram_init_data)
    async with Session() as s:
        x = await s.get(Alert, alert_id)
        if not x or x.telegram_user_id != user_id:
            return {"error": "not_found"}
        await s.delete(x)
        await s.commit()
    index = AlertIndex()
    try:
        await index.remove(x)
    finally:
        await index.close()
    return {"ok": True}

@app.post("/api/profit")
async def profit(payload: ProfitRequest):
    cost = payload.buy_price + payload.delivery + payload.repairs + payload.selling_costs
    profit = payload.resale_price - cost
    return {"total_cost": cost, "profit": profit, "roi_pct": profit / cost * 100 if cost else 0}

app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
