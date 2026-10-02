export {};

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?:()=>void; expand?:()=>void } };
    veloraTimer?: number;
  }
}

type Listing = {
  id:number; title:string; description:string; price:number; currency:string;
  location:string; seller:string; url:string; image_url:string;
  deal_score:number; market_price:number|null; deviation_pct:number|null;
  estimated_profit:number|null; risk:number; liquidity:number; reasons:string[];
  first_seen_at:string; last_seen_at:string;
};

const esc=(s:string)=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]!));
const q=document.querySelector<HTMLInputElement>("#q")!;
const list=document.querySelector<HTMLElement>("#list")!;
const count=document.querySelector<HTMLElement>("#count")!;
const max=document.querySelector<HTMLInputElement>("#maxPrice")!;
const min=document.querySelector<HTMLInputElement>("#minScore")!;
const region=document.querySelector<HTMLInputElement>("#region")!;
const initData=window.Telegram?.WebApp?.initData||"";
const authHeaders=initData?{"X-Telegram-Init-Data":initData}:{};

async function json(path:string){
  const r=await fetch(path,{headers:authHeaders});
  if(!r.ok) throw new Error(String(r.status));
  return r.json();
}

function listingCard(x:Listing){
  const description=x.description||"Описание не указано";
  return `<article class="card" data-id="${x.id}">
    <div class="muted">${esc(x.location||"Регион не указан")} · ${esc(x.seller||"Продавец не указан")}</div>
    <div class="score">DEAL ${x.deal_score}/100</div>
    <h2>${esc(x.title)}</h2>
    <div class="price">${x.price.toLocaleString("ru-RU")} ${esc(x.currency)}</div>
    <div class="market">Market ${x.market_price==null?"—":x.market_price.toLocaleString("ru-RU")+" "+x.currency}
      · Profit ${x.estimated_profit==null?"—":x.estimated_profit.toLocaleString("ru-RU")+" "+x.currency}</div>
    <div class="desc">${esc(description.slice(0,420))}${description.length>420?"…":""}</div>
    <div class="reasons">${(x.reasons||[]).slice(0,3).map(esc).join(" · ")}</div>
    <button class="open-detail" data-id="${x.id}">Подробнее →</button>
  </article>`;
}

async function loadListings(){
  const p=new URLSearchParams({q:q.value,limit:"100"});
  if(max.value)p.set("max_price",max.value);
  if(min.value)p.set("min_score",min.value);
  const r=await fetch("/api/listings?"+p,{headers:authHeaders});
  if(!r.ok){list.textContent="Ошибка загрузки";return;}
  let a:Listing[]=await r.json();
  if(region.value.trim()){
    const needle=region.value.trim().toLowerCase();
    a=a.filter(x=>(x.location||"").toLowerCase().includes(needle));
  }
  count.textContent=String(a.length);
  list.innerHTML=a.map(listingCard).join("");
  document.querySelectorAll<HTMLButtonElement>(".open-detail").forEach(b=>b.addEventListener("click",()=>showDetail(Number(b.dataset.id))));
}

async function showDetail(id:number){
  try{
    const x=await json("/api/listings/"+id) as Listing & {price_history:{price:number;observed_at:string}[]};
    const history=x.price_history||[];
    list.innerHTML=`<article class="card detail">
      <button id="back">← Назад</button>
      <div class="score">DEAL ${x.deal_score}/100 · RISK ${x.risk}/100 · LIQUIDITY ${x.liquidity}/100</div>
      <h1>${esc(x.title)}</h1>
      <div class="price">${x.price.toLocaleString("ru-RU")} ${esc(x.currency)}</div>
      <p class="muted">${esc(x.location)} · ${esc(x.seller)}</p>
      <h3>ОРИГИНАЛЬНОЕ ОПИСАНИЕ</h3>
      <pre class="description-full">${esc(x.description||"Описание не указано")}</pre>
      <h3>VELORA ANALYSIS</h3>
      <p>${(x.reasons||[]).map(esc).join("<br>")}</p>
      <p>Рынок: ${x.market_price==null?"—":x.market_price.toLocaleString("ru-RU")+" "+x.currency}
      · Отклонение: ${x.deviation_pct==null?"—":x.deviation_pct.toFixed(1)+"%"}</p>
      <h3>ИСТОРИЯ ЦЕНЫ</h3>
      <div>${history.length?history.map(h=>`<div>${esc(new Date(h.observed_at).toLocaleString("ru-RU"))} — <b>${h.price.toLocaleString("ru-RU")} ${esc(x.currency)}</b></div>`).join(""):"История пока отсутствует"}</div>
      <a class="open" href="${esc(x.url)}" target="_blank" rel="noopener">Открыть источник →</a>
    </article>`;
    document.getElementById("back")!.addEventListener("click",loadListings);
  }catch(e){list.textContent="Не удалось загрузить объявление";}
}

async function loadMarket(){
  try{
    const m=await json("/api/market?q="+encodeURIComponent(q.value)+"&days=30");
    count.textContent=String(m.count??0);
    const ts=await json("/api/market/timeseries?q="+encodeURIComponent(q.value)+"&days=30");
    list.innerHTML=`<article class="card market-panel">
      <div class="score">MARKET · 30 DAYS</div>
      <h2>${esc(m.query||"Весь рынок")}</h2>
      <div class="price">${m.median==null?"—":m.median.toLocaleString("ru-RU")+" BYN"}</div>
      <p>P10 ${m.p10==null?"—":m.p10.toLocaleString("ru-RU")} · P25 ${m.p25==null?"—":m.p25.toLocaleString("ru-RU")}</p>
      <p>P50 ${m.p50==null?"—":m.p50.toLocaleString("ru-RU")} · P75 ${m.p75==null?"—":m.p75.toLocaleString("ru-RU")} · P90 ${m.p90==null?"—":m.p90.toLocaleString("ru-RU")}</p>
      <p>Supply: ${m.supply??0} · Trend: ${m.trend_pct==null?"—":m.trend_pct.toFixed(1)+"%"}</p>
      <p class="muted">Качество наблюдений: ${esc(m.observation_quality||"—")}</p>
      <h3>ИСТОРИЯ</h3>
      <div class="history">${ts.slice(-14).map((p:any)=>`<div>${esc(p.date)} — <b>${p.median==null?"—":p.median.toLocaleString("ru-RU")+" BYN"}</b> · ${p.count}</div>`).join("")||"Нет исторических наблюдений"}</div>
    </article>`;
  }catch(e){list.textContent="Ошибка Market Engine";}
}

async function createAlert(){
  if(!initData){ list.innerHTML="<article class=\"card\">Откройте Mini App внутри Telegram, чтобы создавать правила.</article>"; return; }
  const query=prompt("Что искать? Можно оставить пустым для всех объявлений.") ?? "";
  if(query===null) return;
  const maxRaw=prompt("Максимальная цена BYN (необязательно):") ?? "";
  const scoreRaw=prompt("Минимальный Deal Score 0-100:","70") ?? "70";
  const payload={query,max_price:maxRaw?Number(maxRaw):null,min_score:Math.max(0,Math.min(100,Number(scoreRaw)||0)),region:region.value.trim()};
  const r=await fetch("/api/alerts",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders},body:JSON.stringify(payload)});
  if(!r.ok){list.innerHTML="<article class=\"card\">Не удалось создать правило.</article>";return;}
  await loadAlerts();
}

async function loadAlerts(){
  try{
    const a=await json("/api/alerts");
    count.textContent=String(a.length);
    list.innerHTML=`<article class="card">
      <h2>ALERTS</h2>
      <p class="muted">Уведомления Telegram привязаны к вашему аккаунту.</p>
      ${a.length?a.map((x:any)=>`<div class="alert-row"><b>${esc(x.query||"Все объявления")}</b> · max ${x.max_price??"—"} · score ≥ ${x.min_score}<button class="stop-alert" data-id="${x.id}">Удалить</button></div>`).join(""):"Активных правил нет."}
    </article>`;
    const add=document.createElement("button"); add.id="new-alert"; add.textContent="Создать правило"; add.className="primary"; list.querySelector(".card")?.prepend(add); add.addEventListener("click",createAlert);
    document.querySelectorAll<HTMLButtonElement>(".stop-alert").forEach(b=>b.addEventListener("click",async()=>{await fetch("/api/alerts/"+b.dataset.id,{method:"DELETE",headers:authHeaders});loadAlerts();}));
  }catch(e){list.textContent="Для ALERTS откройте Mini App из Telegram.";}
}



async function runHunt(){
  const budget=Number((document.getElementById("huntBudget") as HTMLInputElement).value);
  if(!budget){ return; }
  const payload={
    query:q.value.trim(),
    budget,
    min_profit:Number((document.getElementById("huntProfit") as HTMLInputElement).value||0),
    max_risk:Number((document.getElementById("huntRisk") as HTMLInputElement).value||60),
    min_liquidity:Number((document.getElementById("huntLiquidity") as HTMLInputElement).value||0),
    limit:50
  };
  const r=await fetch("/api/hunt",{method:"POST",headers:{"Content-Type":"application/json",...authHeaders},body:JSON.stringify(payload)});
  if(!r.ok){return;}
  const a=await r.json();
  const target=document.getElementById("huntList")!;
  target.innerHTML=a.length?a.map((x:Listing)=>listingCard(x)).join(""):"<article class='card'>Подходящих аномалий не найдено.</article>";
  target.querySelectorAll<HTMLButtonElement>(".open-detail").forEach(b=>b.addEventListener("click",()=>showDetail(Number(b.dataset.id))));
}

function loadTab(tab:string){
  document.getElementById("hunt-panel")?.classList.add("hidden");
  if(tab==="market") return loadMarket();
  if(tab==="alerts") return loadAlerts();
  if(tab==="hunt"){ document.getElementById("hunt-panel")?.classList.remove("hidden"); return runHunt(); }
  return loadListings();
}

q.addEventListener("input",()=>{clearTimeout(window.veloraTimer);window.veloraTimer=window.setTimeout(()=>loadTab("radar"),220)});
document.getElementById("apply")!.addEventListener("click",()=>loadTab("radar"));
document.querySelectorAll<HTMLButtonElement>("[data-q]").forEach(b=>b.addEventListener("click",()=>{q.value=b.dataset.q||"";loadTab("radar")}));
document.getElementById("huntRun")!.addEventListener("click",runHunt);
document.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll("[data-tab]").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");
  if(b.dataset.tab==="deals")min.value="70";
  if(b.dataset.tab==="radar")min.value="0";
  loadTab(b.dataset.tab||"radar");
}));
window.Telegram?.WebApp?.ready?.();
window.Telegram?.WebApp?.expand?.();
loadListings();
