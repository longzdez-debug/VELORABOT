import asyncio, hashlib, json, re
from datetime import datetime
from urllib.parse import urljoin
import httpx
from sqlalchemy import select
from app.config import settings
from app.db import Session, Listing, PriceHistory

JSONLD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)

def _parse_jsonld(html: str):
    out=[]
    for raw in JSONLD.findall(html):
        try: data=json.loads(raw)
        except Exception: continue
        for x in (data if isinstance(data,list) else [data]):
            if isinstance(x,dict) and ("name" in x or "offers" in x): out.append(x)
    return out

def normalize_item(item: dict, base_url: str):
    offer=item.get("offers") if isinstance(item.get("offers"),dict) else item
    url=item.get("url") or offer.get("url")
    title=item.get("name") or item.get("title")
    price=offer.get("price") or item.get("price")
    if not url or not title or price is None: return None
    try: price=float(str(price).replace(",", "."))
    except ValueError: return None
    image=item.get("image") or ""
    if isinstance(image,list): image=image[0] if image else ""
    return {"source_id":hashlib.sha256(url.encode()).hexdigest()[:40],"url":urljoin(base_url,url),
            "title":str(title),"description_raw":str(item.get("description") or ""),
            "price":price,"currency":str(offer.get("priceCurrency") or "BYN"),
            "image_url":str(image),"location":"","seller":""}

async def collect_url(url: str) -> int:
    async with httpx.AsyncClient(timeout=20,follow_redirects=True,headers={"User-Agent":"VELORA/0.1"}) as client:
        r=await client.get(url); r.raise_for_status()
    items=[n for raw in _parse_jsonld(r.text) if (n:=normalize_item(raw,str(r.url)))]
    async with Session() as s:
        for n in items:
            existing=(await s.execute(select(Listing).where(Listing.source=="generic",Listing.source_id==n["source_id"]))).scalar_one_or_none()
            if existing:
                if existing.price != n["price"]: s.add(PriceHistory(listing_id=existing.id,price=n["price"]))
                existing.price=n["price"]; existing.description_raw=n["description_raw"]; existing.last_seen_at=datetime.utcnow()
            else:
                x=Listing(source="generic",**n); s.add(x); await s.flush(); s.add(PriceHistory(listing_id=x.id,price=x.price))
        await s.commit()
    return len(items)

async def run_collector():
    while True:
        if settings.collector_url:
            try: await collect_url(settings.collector_url)
            except Exception: pass
        await asyncio.sleep(settings.collector_interval_seconds)
