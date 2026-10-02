from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_, func
from app.db import Session, Listing, Alert, PriceHistory, init_db
from app.api_models import AlertCreate, ProfitRequest
from app.scoring import calculate_deal_score

app = FastAPI(title="VELORA API", version="0.2.0")

@app.on_event("startup")
async def startup():
    await init_db()

def listing_json(x, deal=None):
    return {"id":x.id,"source":x.source,"title":x.title,"description":x.description_raw,
            "description_raw":x.description_raw,"price":x.price,"currency":x.currency,
            "location":x.location,"seller":x.seller,"url":x.url,"image_url":x.image_url,
            "first_seen_at":x.first_seen_at,"last_seen_at":x.last_seen_at,
            **({"deal_score":deal.score,"market_price":deal.market_price,"deviation_pct":deal.deviation_pct,
                "estimated_profit":deal.estimated_profit,"liquidity":deal.liquidity,"risk":deal.risk,
                "reasons":deal.reasons} if deal else {})}

@app.get("/health")
async def health():
    return {"ok":True,"service":"velora","version":"0.2.0"}

@app.get("/api/stats")
async def stats():
    async with Session() as s:
        count=(await s.execute(select(func.count(Listing.id)))).scalar_one()
        return {"listings":count}

@app.get("/api/listings")
async def listings(q: str=Query("",max_length=200), limit: int=Query(30,ge=1,le=100)):
    async with Session() as s:
        stmt=select(Listing).order_by(Listing.first_seen_at.desc()).limit(limit)
        if q.strip():
            needle=f"%{q.strip()}%"
            stmt=select(Listing).where(or_(Listing.title.ilike(needle),Listing.description_raw.ilike(needle))).order_by(Listing.first_seen_at.desc()).limit(limit)
        rows=(await s.execute(stmt)).scalars().all()
        all_prices=(await s.execute(select(Listing.price).limit(200))).scalars().all()
        return [listing_json(x,calculate_deal_score(x.price,list(all_prices),x.description_raw)) for x in rows]

@app.get("/api/listings/{listing_id}")
async def listing(listing_id:int):
    async with Session() as s:
        x=await s.get(Listing,listing_id)
        if not x: return {"error":"not_found"}
        prices=(await s.execute(select(Listing.price).where(Listing.id!=x.id).limit(200))).scalars().all()
        history=(await s.execute(select(PriceHistory).where(PriceHistory.listing_id==x.id).order_by(PriceHistory.observed_at))).scalars().all()
        return {**listing_json(x,calculate_deal_score(x.price,list(prices),x.description_raw)),
                "price_history":[{"price":h.price,"observed_at":h.observed_at} for h in history]}

@app.post("/api/alerts")
async def create_alert(user_id:int, payload:AlertCreate):
    async with Session() as s:
        x=Alert(telegram_user_id=user_id,**payload.model_dump())
        s.add(x); await s.commit(); await s.refresh(x)
        return {"id":x.id,"active":x.active}

@app.get("/api/alerts")
async def get_alerts(user_id:int):
    async with Session() as s:
        rows=(await s.execute(select(Alert).where(Alert.telegram_user_id==user_id).order_by(Alert.id.desc()))).scalars().all()
        return [{"id":x.id,"query":x.query,"max_price":x.max_price,"min_score":x.min_score,"region":x.region,"active":x.active} for x in rows]

@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id:int,user_id:int):
    async with Session() as s:
        x=await s.get(Alert,alert_id)
        if not x or x.telegram_user_id!=user_id: return {"error":"not_found"}
        await s.delete(x); await s.commit(); return {"ok":True}

@app.post("/api/profit")
async def profit(payload:ProfitRequest):
    cost=payload.buy_price+payload.delivery+payload.repairs+payload.selling_costs
    profit=payload.resale_price-cost
    return {"total_cost":cost,"profit":profit,"roi_pct":profit/cost*100 if cost else 0}

app.mount("/",StaticFiles(directory="app/web",html=True),name="web")
