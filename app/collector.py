import asyncio, hashlib, json, re
from datetime import datetime
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from app.config import settings
from app.db import Session, Listing, PriceHistory
from app.notify import evaluate_and_notify

JSONLD=re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',re.I|re.S)

def _jsonld(html):
    out=[]
    for raw in JSONLD.findall(html):
        try:data=json.loads(raw)
        except Exception:continue
        out.extend(data if isinstance(data,list) else [data])
    return [x for x in out if isinstance(x,dict)]

def _number(value):
    if value is None:return None
    m=re.search(r'(?<!\d)(\d[\d\s.,]*)(?:\s*(?:BYN|р\.?|руб\.?))?',str(value),re.I)
    if not m:return None
    try:return float(m.group(1).replace(" ","").replace(",","."))
    except ValueError:return None

def _normalize(x,base):
    offer=x.get("offers") if isinstance(x.get("offers"),dict) else x
    url=x.get("url") or offer.get("url"); title=x.get("name") or x.get("title")
    price=_number(offer.get("price") or x.get("price"))
    if not url or not title or price is None:return None
    image=x.get("image") or ""; image=image[0] if isinstance(image,list) and image else image
    return {"source_id":hashlib.sha256(urljoin(base,str(url)).encode()).hexdigest()[:40],
            "url":urljoin(base,str(url)),"title":str(title).strip(),
            "description_raw":str(x.get("description") or "").strip(),"price":price,
            "currency":str(offer.get("priceCurrency") or "BYN"),"image_url":str(image),
            "location":str(x.get("address") or ""),"seller":str(x.get("seller") or "")}

def _html_fallback(html,base):
    soup=BeautifulSoup(html,"html.parser"); result=[]
    for node in soup.find_all(["article","li","div"]):
        a=node.find("a",href=True); h=node.find(["h1","h2","h3","h4"])
        if not a or not h:continue
        title=h.get_text(" ",strip=True); price=_number(node.get_text(" ",strip=True))
        if not title or price is None or len(title)>300:continue
        desc=node.find("p") or node.find(attrs={"class":re.compile("description|desc",re.I)})
        result.append({"source_id":hashlib.sha256(urljoin(base,a["href"]).encode()).hexdigest()[:40],
            "url":urljoin(base,a["href"]),"title":title,
            "description_raw":desc.get_text(" ",strip=True) if desc else "",
            "price":price,"currency":"BYN","image_url":"","location":"","seller":""})
    seen=set();out=[]
    for x in result:
        if x["source_id"] not in seen:seen.add(x["source_id"]);out.append(x)
    return out[:200]

def parse_page(html,base):
    items=[n for x in _jsonld(html) if (n:=_normalize(x,base))]
    return items or _html_fallback(html,base)

async def collect_url(url):
    async with httpx.AsyncClient(timeout=25,follow_redirects=True,headers={"User-Agent":"Mozilla/5.0 (compatible; VELORA/0.3)"}) as client:
        response=await client.get(url);response.raise_for_status()
    items=parse_page(response.text,str(response.url));changed=[]
    async with Session() as s:
        for n in items:
            old=(await s.execute(select(Listing).where(Listing.source=="web",Listing.source_id==n["source_id"]))).scalar_one_or_none()
            if old:
                if old.price!=n["price"]:s.add(PriceHistory(listing_id=old.id,price=n["price"]));old.price=n["price"];changed.append(old.id)
                old.description_raw=n["description_raw"];old.last_seen_at=datetime.utcnow()
            else:
                x=Listing(source="web",**n);s.add(x);await s.flush();s.add(PriceHistory(listing_id=x.id,price=x.price));changed.append(x.id)
        await s.commit()
    for listing_id in changed:
        try:await evaluate_and_notify(listing_id)
        except Exception:pass
    return len(items)

async def run_collector():
    while True:
        for url in settings.source_urls():
            try:await collect_url(url)
            except Exception:pass
        await asyncio.sleep(settings.collector_interval_seconds)
