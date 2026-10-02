import asyncio, hashlib, json, logging, re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.config import settings
from app.db import Session, Listing, PriceHistory
from app.events import new_listing_event
from app.pipeline import publish_listing_event
from app.attributes import extract_attributes
from app.duplicates import duplicate_key_for

log = logging.getLogger(__name__)

JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def _jsonld(html):
    out = []
    for raw in JSONLD.findall(html):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        out.extend(data if isinstance(data, list) else [data])
    return [x for x in out if isinstance(x, dict)]


def _number(value):
    if value is None:
        return None
    m = re.search(r"(?<!\d)(\d[\d\s.,]*)(?:\s*(?:BYN|р\.?|руб\.?)?)?", str(value), re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _normalize(x, base):
    offer = x.get("offers") if isinstance(x.get("offers"), dict) else x
    url = x.get("url") or offer.get("url")
    title = x.get("name") or x.get("title")
    price = _number(offer.get("price") or x.get("price"))
    if not url or not title or price is None:
        return None
    image = x.get("image") or ""
    image = image[0] if isinstance(image, list) and image else image
    description = str(x.get("description") or "").strip()
    attrs = extract_attributes(str(title), description)
    return {
        "source_id": hashlib.sha256(urljoin(base, str(url)).encode()).hexdigest()[:40],
        "url": urljoin(base, str(url)),
        "title": str(title).strip(),
        "description_raw": description,
        "model": attrs.model or "",
        "condition": attrs.condition,
        "storage_gb": attrs.storage_gb,
        "memory_gb": attrs.memory_gb,
        "fingerprint": hashlib.sha256((str(title).casefold()+"|"+description[:1000].casefold()+"|"+str(price)).encode()).hexdigest(),
        "duplicate_key": duplicate_key_for(str(title), attrs.model or "", attrs.storage_gb, str(image)),
        "price": price,
        "currency": str(offer.get("priceCurrency") or "BYN"),
        "image_url": str(image),
        "location": str(x.get("address") or ""),
        "seller": str(x.get("seller") or ""),
    }


def _html_fallback(html, base):
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for node in soup.find_all(["article", "li", "div"]):
        a = node.find("a", href=True)
        h = node.find(["h1", "h2", "h3", "h4"])
        if not a or not h:
            continue
        title = h.get_text(" ", strip=True)
        price = _number(node.get_text(" ", strip=True))
        if not title or price is None or len(title) > 300:
            continue
        desc = node.find("p") or node.find(attrs={"class": re.compile("description|desc", re.I)})
        desc_text = desc.get_text(" ", strip=True) if desc else ""
        attrs = extract_attributes(title, desc_text)
        result.append({
            "source_id": hashlib.sha256(urljoin(base, a["href"]).encode()).hexdigest()[:40],
            "url": urljoin(base, a["href"]),
            "title": title,
            "description_raw": desc_text,
            "model": attrs.model or "",
            "condition": attrs.condition,
            "storage_gb": attrs.storage_gb,
            "memory_gb": attrs.memory_gb,
            "fingerprint": hashlib.sha256((title.casefold()+"|"+desc_text[:1000].casefold()+"|"+str(price)).encode()).hexdigest(),
            "duplicate_key": duplicate_key_for(title, attrs.model or "", attrs.storage_gb, ""),
            "price": price,
            "currency": "BYN",
            "image_url": "",
            "location": "",
            "seller": "",
        })
    seen = set()
    out = []
    for x in result:
        if x["source_id"] not in seen:
            seen.add(x["source_id"])
            out.append(x)
    return out[:200]


def parse_page(html, base):
    items = [n for x in _jsonld(html) if (n := _normalize(x, base))]
    return items or _html_fallback(html, base)


async def collect_url(url):
    async with httpx.AsyncClient(
        timeout=25,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; VELORA/0.3)"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    items = parse_page(response.text, str(response.url))
    changed = []
    async with Session() as s:
        for n in items:
            old = (await s.execute(
                select(Listing).where(Listing.source == "web", Listing.source_id == n["source_id"])
            )).scalar_one_or_none()
            if old:
                event = "UPDATED"
                if old.price != n["price"]:
                    s.add(PriceHistory(listing_id=old.id, price=n["price"]))
                    old.price = n["price"]
                    event = "PRICE_CHANGED"
                old.url = n["url"]
                if n["description_raw"]:
                    old.description_raw = n["description_raw"]
                old.model = n.get("model") or old.model
                old.condition = n.get("condition") or old.condition
                old.storage_gb = n.get("storage_gb")
                old.memory_gb = n.get("memory_gb")
                old.fingerprint = n.get("fingerprint") or old.fingerprint
                old.duplicate_key = n.get("duplicate_key") or old.duplicate_key
                old.image_url = n.get("image_url") or old.image_url
                old.location = n.get("location") or old.location
                old.seller = n.get("seller") or old.seller
                old.currency = n.get("currency") or old.currency
                old.last_seen_at = datetime.utcnow()
                changed.append((old.id, event, old.price, n["source_id"]))
            else:
                x = Listing(source="web", **n)
                s.add(x)
                await s.flush()
                s.add(PriceHistory(listing_id=x.id, price=x.price))
                changed.append((x.id, "NEW", x.price, n["source_id"]))
        await s.commit()

    for listing_id, event, price, source_id in changed:
        try:
            await publish_listing_event(
                new_listing_event(event, listing_id, "web", source_id, price)
            )
        except Exception:
            # Redis is a transport optimization; persistence remains intact.
            pass
    return len(items)


async def run_collector():
    while True:
        for url in settings.source_urls():
            try:
                await collect_url(url)
            except Exception:
                log.exception("generic collector failed url=%s", url)
        await asyncio.sleep(settings.collector_interval_seconds)
