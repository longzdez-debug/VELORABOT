import { chromium } from "playwright";

const API=process.env.API_PUBLIC_URL||"http://api:8080";
const TOKEN=process.env.COLLECTOR_TOKEN||"";
const FALLBACK_INTERVAL=Number(process.env.COLLECTOR_INTERVAL_MS||1500);
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({userAgent:"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"});
const headers={"x-collector-token":TOKEN,"content-type":"application/json"};

async function monitors(){const r=await fetch(API+"/api/collector/monitors",{headers});return r.ok?r.json():[]}
function normalize(raw){
  if(!raw||typeof raw!=="object")return null;
  const id=String(raw.id??raw.kufar_id??raw.ad_id??raw.advert_id??"");
  const url=String(raw.url??raw.link??raw.href??"");
  const title=String(raw.title??raw.name??raw.subject??"").trim();
  const price=Number(raw.price??raw.cost??NaN);
  if(!/^\d{6,}$/.test(id)||(!url&&!title))return null;
  return {kufar_id:id,url:url||"https://www.kufar.by/item/"+id,title:title.slice(0,240),price:Number.isFinite(price)?price:null,description:raw.description??raw.text??null,location:raw.location??raw.city??raw.region??null,images:Array.isArray(raw.images)?raw.images.filter(Boolean).slice(0,10):[]};
}
async function scan(m){
  const page=await context.newPage();
  const network=[];
  const onResponse=async response=>{
    try{
      const ct=response.headers()["content-type"]||"";
      if(!ct.includes("json"))return;
      const data=await response.json();
      const stack=[data];
      while(stack.length){
        const x=stack.pop();
        if(Array.isArray(x)){for(const y of x)stack.push(y);continue}
        const n=normalize(x); if(n)network.push(n);
        if(x&&typeof x==="object")for(const v of Object.values(x))if(v&&typeof v==="object")stack.push(v);
      }
    }catch{}
  };
  page.on("response",onResponse);
  await page.goto(m.url,{waitUntil:"domcontentloaded",timeout:30000});
  await page.waitForTimeout(250);
  page.off("response",onResponse);
  const dom=await page.evaluate(()=>{const a=[];for(const x of document.querySelectorAll("a[href]")){const h=x.href;if(!/kufar\.by\//i.test(h))continue;const id=(h.match(/(\d{6,})/)||[])[1];if(!id)continue;const c=x.closest("article,li")||x.parentElement;const raw=(c?.innerText||x.innerText||"").replace(/\s+/g," ").trim();const p=(raw.match(/([\d\s]+)\s*(?:BYN|р\.?)/i)||[])[1];const imgs=[...((c?.querySelectorAll("img"))||[])].map(i=>i.src).filter(Boolean).slice(0,10);a.push({kufar_id:id,url:h,title:(x.innerText||raw).trim().slice(0,240),price:p?Number(p.replace(/\s/g,"")):null,images:imgs})}return a});
  const unique=[...new Map([...network,...dom].map(x=>[x.kufar_id,x])).values()].slice(0,200);
  await Promise.all(unique.map(item=>fetch(API+"/api/ingest/listing",{method:"POST",headers,body:JSON.stringify({...item,monitor_id:m.id,currency:"BYN"})}).catch(()=>{})));
  await fetch(API+"/api/collector/heartbeat",{method:"POST",headers,body:JSON.stringify({monitor_id:m.id,collector:"browser",observed_kufar_ids:unique.map(x=>x.kufar_id)})}).catch(()=>{});
  await page.close();
}
while(true){
  try{
    const ms=await monitors();
    await Promise.all(ms.map(m=>scan(m).catch(e=>console.error("scan",m.id,e.message))));
    const delay=ms.length?Math.min(...ms.map(m=>Number(m.interval_ms)||FALLBACK_INTERVAL)):FALLBACK_INTERVAL;
    await new Promise(r=>setTimeout(r,Math.max(750,delay)));
  }catch(e){console.error("loop",e.message);await new Promise(r=>setTimeout(r,FALLBACK_INTERVAL))}
}