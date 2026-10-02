import asyncio, html, logging, re
from datetime import datetime

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import Session, Listing, PriceHistory
from app.events import new_listing_event
from app.pipeline import publish_listing_event

log = logging.getLogger(__name__)
SEARCH_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"


def _price(value):
    if value is None:
        return None
    try:
        return int(value) // 100
    except (TypeError, ValueError):
        m = re.search(r"(\d[\d\s.,]*)", str(value))
        return float(m.group(1).replace(" ", "").replace(",", ".")) if m else None


def _param(params, names):
    for p in params or []:
        if p.get("p") in names:
            v = p.get("vl", p.get("v", ""))
            if v not in (None, ""):
                return str(v)
    return ""


def normalize_ad(raw):
    ad_id = str(raw.get("ad_id") or "").strip()
    if not ad_id:
        return None
    url = (raw.get("ad_link") or f"https://www.kufar.by/item/{ad_id}").split("?")[0]
    title = str(raw.get("subject") or "").strip()
    price = _price(raw.get("price_byn") or raw.get("price"))
    if not title or price is None:
        return None

    params = raw.get("ad_parameters") or []
    region = _param(params, ("region",))
    area = _param(params, ("area",))
    body = raw.get("body") or raw.get("body_short") or ""
    if not isinstance(body, str):
        body = str(body)
    body = re.sub(r"\s+", " ", html.unescape(body)).strip()

    images = []
    for image in raw.get("images") or []:
        if isinstance(image, dict) and image.get("path"):
            images.append(f"https://rms.kufar.by/v1/gallery/{str(image['path']).lstrip('/')}")

    return {
        "source_id": ad_id,
        "url": url,
        "title": title,
        "description_raw": body,
        "price": price,
        "currency": "BYN",
        "image_url": images[0] if images else "",
        "location": ", ".join(x for x in (region, area) if x),
        "seller": str(raw.get("company_name") or raw.get("seller_name") or ""),
    }


async def _fetch_json(client, params):
    for attempt in range(3):
        try:
            r = await client.get(SEARCH_URL, params=params)
            if r.status_code == 429:
                await asyncio.sleep(float(r.headers.get("Retry-After", "1")) * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            if attempt == 2:
                raise
            await asyncio.sleep(.25 * (attempt + 1))
            log.warning("Kufar request retry: %s", e)
    return {}


async def collect_query(query):
    params = {
        "query": query,
        "lang": "ru",
        "size": str(settings.kufar_size),
        "sort": "lst.d",
        "cur": "BYR",
    }
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; VELORA/1.0)",
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": "https://www.kufar.by/",
            "Origin": "https://www.kufar.by",
        },
    ) as client:
        data = await _fetch_json(client, params)

    items = [x for raw in data.get("ads") or [] if (x := normalize_ad(raw))]
    changed = []
    async with Session() as s:
        for n in items:
            old = (await s.execute(
                select(Listing).where(Listing.source == "kufar", Listing.source_id == n["source_id"])
            )).scalar_one_or_none()
            now = datetime.utcnow()
            if old:
                event = "UPDATED"
                if old.price != n["price"]:
                    s.add(PriceHistory(listing_id=old.id, price=n["price"]))
                    old.price = n["price"]
                    event = "PRICE_CHANGED"
                old.title = n["title"]
                if n["description_raw"]:
                    old.description_raw = n["description_raw"]
                old.location = n["location"]
                old.seller = n["seller"]
                old.image_url = n["image_url"] or old.image_url
                old.last_seen_at = now
                changed.append((old.id, event, old.price, n["source_id"]))
            else:
                x = Listing(
                    source="kufar",
                    source_id=n["source_id"],
                    url=n["url"],
                    title=n["title"],
                    description_raw=n["description_raw"],
                    price=n["price"],
                    currency=n["currency"],
                    location=n["location"],
                    seller=n["seller"],
                    image_url=n["image_url"],
                    first_seen_at=now,
                    last_seen_at=now,
                )
                s.add(x)
                await s.flush()
                s.add(PriceHistory(listing_id=x.id, price=x.price))
                changed.append((x.id, "NEW", x.price, n["source_id"]))
        await s.commit()

    for listing_id, event, price, source_id in changed:
        try:
            await publish_listing_event(
                new_listing_event(event, listing_id, "kufar", source_id, price)
            )
        except Exception:
            log.exception("Kufar event publish failed id=%s", listing_id)
    return len(items)


async def run_kufar():
    queries = settings.kufar_query_list()
    if not queries:
        log.info("Kufar collector disabled: KUFAR_QUERIES is empty")
        return
    delay = max(.25, settings.kufar_interval_ms / 1000)
    while True:
        started = asyncio.get_running_loop().time()
        await asyncio.gather(*(collect_query(q) for q in queries), return_exceptions=True)
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0, delay - elapsed))
