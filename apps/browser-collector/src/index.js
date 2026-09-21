import { chromium } from "playwright";
const API=process.env.API_PUBLIC_URL||"http://api:8080";
const INTERVAL=Number(process.env.COLLECTOR_INTERVAL_MS||1500);
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({userAgent:"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"});
const page=await context.newPage();
async function monitors(){const r=await fetch(API+"/api/collector/monitors");return r.ok?r.json():[]}
async function scan(m){
 await page.goto(m.url,{waitUntil:"domcontentloaded",timeout:30000});
 const items=await page.evaluate(()=>{const a=[];for(const x of document.querySelectorAll("a[href]")){const h=x.href;if(!/kufar\.by\//i.test(h))continue;const id=(h.match(/(\d{6,})/)||[])[1];if(!id)continue;const c=x.closest("article,li")||x.parentElement;const raw=(c?.innerText||x.innerText||"").replace(/\s+/g," ").trim();const p=(raw.match(/([\d\s]+)\s*(?:BYN|р\.?)/i)||[])[1];const img=c?.querySelector("img")?.src||null;a.push({kufar_id:id,url:h,title:(x.innerText||raw).trim().slice(0,240),price:p?Number(p.replace(/\s/g,"")):null,images:img?[img]:[]})}return [...new Map(a.map(x=>[x.kufar_id,x])).values()].slice(0,100)});
 for(const item of items)await fetch(API+"/api/ingest/listing",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({...item,monitor_id:m.id,currency:"BYN"})}).catch(()=>{});
}
while(true){try{for(const m of await monitors())try{await scan(m)}catch(e){console.error("scan",m.id,e.message)}}catch(e){console.error("loop",e.message)}await new Promise(r=>setTimeout(r,INTERVAL))}
