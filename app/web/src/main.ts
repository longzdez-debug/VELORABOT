declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?:()=>void; expand?:()=>void } };
  }
}
type Listing = {
  id:number; title:string; description:string; price:number; currency:string;
  location:string; seller:string; url:string; deal_score:number; market_price:number|null;
  deviation_pct:number|null; estimated_profit:number|null; risk:number; liquidity:number;
};

const esc=(s:string)=>s.replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]!));
const q=document.querySelector<HTMLInputElement>("#q")!;
const list=document.querySelector<HTMLElement>("#list")!;
const count=document.querySelector<HTMLElement>("#count")!;
const max=document.querySelector<HTMLInputElement>("#maxPrice")!;
const min=document.querySelector<HTMLInputElement>("#minScore")!;
const region=document.querySelector<HTMLInputElement>("#region")!;
const initData=window.Telegram?.WebApp?.initData||"";
const authHeaders=initData?{"X-Telegram-Init-Data":initData}:{};

async function load(){
  const p=new URLSearchParams({q:q.value,limit:"100"});
  if(max.value)p.set("max_price",max.value);
  if(min.value)p.set("min_score",min.value);
  const r=await fetch("/api/listings?"+p);
  if(!r.ok){list.textContent="Ошибка загрузки";return;}
  let a:Listing[]=await r.json();
  if(region.value.trim()) {
    const needle=region.value.trim().toLowerCase();
    a=a.filter(x=>x.location.toLowerCase().includes(needle));
  }
  count.textContent=String(a.length);
  list.innerHTML=a.map(x=>`<article class="card">
    <div class="muted">${esc(x.location||"Регион не указан")} · ${esc(x.seller||"Продавец не указан")}</div>
    <div class="score">DEAL ${x.deal_score}/100</div>
    <h2>${esc(x.title)}</h2>
    <div class="price">${x.price.toLocaleString("ru-RU")} ${esc(x.currency)}</div>
    <div class="market">Market ${x.market_price==null?"—":x.market_price.toLocaleString("ru-RU")+" "+x.currency}
      · Profit ${x.estimated_profit==null?"—":x.estimated_profit.toLocaleString("ru-RU")+" "+x.currency}</div>
    <div class="desc">${esc(x.description||"Описание не указано")}</div>
    <a class="open" href="${esc(x.url)}" target="_blank" rel="noopener">Открыть объявление →</a>
  </article>`).join("");
}
q.addEventListener("input",()=>{clearTimeout((window as any).veloraTimer);(window as any).veloraTimer=setTimeout(load,220)});
document.getElementById("apply")!.addEventListener("click",load);
document.querySelectorAll<HTMLButtonElement>("[data-q]").forEach(b=>b.addEventListener("click",()=>{
  q.value=b.dataset.q||""; load();
window.Telegram?.WebApp?.ready?.();
window.Telegram?.WebApp?.expand?.();
}));
document.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll("[data-tab]").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");
  if(b.dataset.tab==="deals") min.value="70";
  if(b.dataset.tab==="radar") min.value="0";
  load();
}));
load();

