from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_
from app.db import Session, Listing, init_db

app = FastAPI(title="VELORA API", version="0.1.0")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    return {"ok": True, "service": "velora"}

@app.get("/api/listings")
async def listings(q: str = Query("", max_length=200), limit: int = Query(30, ge=1, le=100)):
    async with Session() as s:
        stmt = select(Listing).order_by(Listing.first_seen_at.desc()).limit(limit)
        if q.strip():
            needle = f"%{q.strip()}%"
            stmt = select(Listing).where(
                or_(Listing.title.ilike(needle), Listing.description_raw.ilike(needle))
            ).order_by(Listing.first_seen_at.desc()).limit(limit)
        rows = (await s.execute(stmt)).scalars().all()
        return [{"id":x.id,"title":x.title,"description":x.description_raw,"price":x.price,
                 "currency":x.currency,"location":x.location,"seller":x.seller,"url":x.url,
                 "image_url":x.image_url} for x in rows]

@app.get("/api/listings/{listing_id}")
async def listing(listing_id: int):
    async with Session() as s:
        x = await s.get(Listing, listing_id)
        if not x:
            return {"error":"not_found"}
        return {"id":x.id,"title":x.title,"description":x.description_raw,"price":x.price,
                "currency":x.currency,"location":x.location,"seller":x.seller,"url":x.url,
                "image_url":x.image_url}

app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
