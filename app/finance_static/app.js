// ---- 💹 Finance tab (served by finance.py). Informational only: nothing here feeds threat scoring. Times in ET. ----
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const TZ="America/New_York";
const etT=t=>{if(!t)return"—";const d=new Date(t);return isNaN(d)?E(t):d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
// ---- tab button (Monitor group) + panel + deep link #finance
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="finance"]');if(!tb){tb=document.createElement("button");tb.dataset.tab="finance";tb.textContent="💹 Finance";nav.appendChild(tb)}
const anchor=nav.querySelector('button[data-tab="elon"]')||nav.querySelector('button[data-tab="spacex"]')||nav.querySelector('button[data-tab="jets"]');if(anchor)anchor.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.finance="finance";HASHTAB.finance="finance"}}catch(_){}
let M=document.getElementById("tab-finance");
if(!M){M=document.createElement("main");M.id="tab-finance";M.dataset.addon="finance";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn" id="fin_top"><h2><span class="fin-ic">💹</span> Finance <span class="meta">— global markets: indices, ETFs, stocks, bonds, options/volatility, forex, crypto and commodities</span><button type="button" class="tab-ref" id="fin_ref" title="Re-check the market data now (cached 3 min; a forced re-check is allowed once a minute)">⟳ Refresh</button></h2><div id="fin_app"><div class="meta">Loading Finance…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
if(location.hash=="#finance")setTimeout(()=>tb.click(),350);
const app=M.querySelector("#fin_app");
const F={d:null,t:0,busy:false,timer:null};
const fmtP=(v,s)=>{if(v==null)return"—";const a=Math.abs(v);const dg=/=X$/.test(s||"")&&a<20?4:a>=1000?2:a>=1?2:a>=0.01?4:6;return v.toLocaleString("en-US",{minimumFractionDigits:dg,maximumFractionDigits:dg})};
const big=v=>v==null?"—":v>=1e12?"$"+(v/1e12).toFixed(2)+"T":v>=1e9?"$"+(v/1e9).toFixed(1)+"B":v>=1e6?"$"+(v/1e6).toFixed(0)+"M":"$"+v.toFixed(0);
const pc=v=>v==null?"—":(v>0?"+":"")+v.toFixed(2)+"%";const cl=v=>v==null?"":v>0?"up":v<0?"dn":"";
function spark(a,up){if(!a||a.length<2)return'<svg class=fin-sp viewBox="0 0 100 28"></svg>';let lo=Math.min(...a),hi=Math.max(...a);if(hi==lo){hi+=1;lo-=1}
 const pts=a.map((v,i)=>`${(i/(a.length-1)*100).toFixed(1)},${(26-(v-lo)/(hi-lo)*24).toFixed(1)}`).join(" ");
 return `<svg class=fin-sp viewBox="0 0 100 28" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${up?"#3fb950":"#f85149"}" stroke-width="1.4" vector-effect="non-scaling-stroke"/></svg>`}
function card(x,unit){const up=(x.chg_pct??0)>=0;const pct=x.chg_pct!=null?x.chg_pct:(x.price!=null&&x.prev?(x.price/x.prev-1)*100:null);
 const extra=x.mcap?`<span class=meta>mcap ${big(x.mcap)}${x.ath_chg!=null?" · "+x.ath_chg.toFixed(0)+"% vs ATH":""}</span>`:x.sub?`<span class=meta>${E(x.sub)}</span>`:"";
 return `<button type=button class=fin-card data-s="${E(x.sym)}" data-l="${E(x.label)}" title="${E(x.label)} (${E(x.sym)}) — click for a larger chart${x.market_time?"\nLast trade "+etT(x.market_time):""}${x.exch?"\n"+E(x.exch):""}">
 <span class=fin-nm><b>${E(x.label)}</b><span class=fin-sym>${E(x.sym)}</span></span>
 <span class=fin-px>${fmtP(x.price,x.sym)}${unit||""} <span class="fin-ch ${cl(pct)}">${pc(pct)}</span></span>${spark(x.spark,up)}${extra}</button>`}
const LV={calm:["fin-ok","calm"],elevated:["fin-warn","elevated"],high:["fin-bad","high"]};
function render(){const d=F.d;if(!d)return;
 const mk=d.markets.map(m=>`<span class="fin-mk ${m.status=="open"?"op":m.status=="closed"?"cl":"pp"}" title="${E(m.session?"Regular session: "+m.session:"")}${m.last_trade?"\nLast trade "+etT(m.last_trade):""}"><i></i>${E(m.name)} <b>${E(m.status)}</b></span>`).join("");
 const st=d.stress.map(s=>{const l=LV[s.level]||["fin-na","info"];return `<div class="fin-st ${l[0]}"><div class=fin-st-h>${E(s.k)} <b>${E(s.value)}</b> <span class=fin-lv>${l[1]}</span></div>
  <div class=meta>${E(s.detail||"")}</div><div class=fin-rule>Threshold: ${E(s.rule)}</div><a class=fin-cite href="${E(s.cite[1])}" target=_blank rel=noopener>Source: ${E(s.cite[0])}</a></div>`}).join("");
 const gs=d.groups.map(g=>{const unit=g.id=="rates"?"%":"";const cg=g.id=="crypto"&&d.crypto?`<div class=fin-cgl>Total crypto market cap <b>${big(d.crypto.total_mcap)}</b> <span class="fin-ch ${cl(d.crypto.mcap_chg_24h)}">${pc(d.crypto.mcap_chg_24h)} 24h</span> · BTC dominance <b>${(d.crypto.btc_dom||0).toFixed(1)}%</b> · ETH ${(d.crypto.eth_dom||0).toFixed(1)}% · 24h volume ${big(d.crypto.total_vol)} <span class=meta>(CoinGecko, ${etT(d.crypto.fetched)})</span></div>`:"";
  return `<div class=fin-grp id="fin_g_${g.id}"><h3>${E(g.label)} <span class=meta>— ${E(g.note)}</span></h3>${cg}<div class=fin-cards>${g.items.map(x=>card(x,unit)).join("")}</div>${g.id=="rates"?bonds():""}${g.id=="vol"?opts():""}${g.id=="fx"?ecb():""}</div>`}).join("");
 app.innerHTML=`<div class=fin-note>${E(d.delay_note)} Quotes fetched ${etT(d.quotes_fetched)}${d.stale?' · <b class=fin-stale>showing last good data (source unavailable)</b>':""}. Server cache ${d.cache_s.quotes/60} min. Informational only — never affects threat scores.</div>
 <div class=fin-mks><span class=meta>Markets (ET):</span>${mk}</div>
 <div class=fin-stress><h3>Market stress <span class=meta>— informational dashboard of common stress gauges with cited thresholds; it does not feed The Wire's scoring</span></h3><div class=fin-sts>${st}</div></div>
 <div class=fin-jump>${d.groups.map(g=>`<a href="#fin_g_${g.id}" data-j="${g.id}">${E(g.label)}</a>`).join("")}</div>
 ${gs}
 <div class=fin-grp><h3>🗄 Daily closes archive <span class=meta>— every instrument's last price per trading day is saved on the server (finance.db) and in the Live Archive log${d.archive_days&&d.archive_days.since?" · since "+E(d.archive_days.since)+", "+d.archive_days.days+" day(s)":""}</span></h3><div id=la_mount_finance></div></div>
 <div class=fin-src>Sources: ${d.sources.map(s=>`<a href="${E(s[1])}" target=_blank rel=noopener>${E(s[0])}</a>`).join(" · ")} · Charts: <a href="api/finance/LWC_LICENSE.txt" target=_blank>TradingView Lightweight Charts™ (Apache-2.0)</a>, served locally.${Object.keys(d.errors||{}).length?`<div class=fin-err>Source issues: ${Object.entries(d.errors).map(([k,v])=>E(k+": "+v)).join(" · ")}</div>`:""}</div>`;
 app.querySelectorAll(".fin-jump a").forEach(a=>a.onclick=e=>{e.preventDefault();const el=document.getElementById("fin_g_"+a.dataset.j);el&&el.scrollIntoView({behavior:"smooth",block:"start"})});
 if(window.BN_LA_MOUNT)window.BN_LA_MOUNT("finance",document.getElementById("la_mount_finance"))}
function bonds(){const d=F.d,c=d.curve;let h="";
 if(c){const W=520,H=150,P=28,vals=[...c.now,...(c.month_ago||[])].filter(v=>v!=null),lo=Math.floor(Math.min(...vals)*4)/4-.1,hi=Math.ceil(Math.max(...vals)*4)/4+.1;
  const x=i=>P+i*(W-P-8)/(c.tenors.length-1),y=v=>H-18-(v-lo)/(hi-lo)*(H-30);
  const line=(a,col,dash)=>`<polyline fill=none stroke="${col}" stroke-width=2 ${dash?'stroke-dasharray="4 3"':""} points="${a.map((v,i)=>v==null?"":x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ")}"/>`;
  const ticks=[0,.25,.5,.75,1].map(f=>lo+f*(hi-lo)).map(v=>`<text x=2 y=${y(v)+3} class=fin-ax>${v.toFixed(2)}</text><line x1=${P} x2=${W-8} y1=${y(v)} y2=${y(v)} class=fin-gl />`).join("");
  h+=`<div class=fin-curve><div><b>US Treasury par yield curve</b> <span class=meta>— official end of day ${E(c.date)} (solid) vs ${E(c.month_ago_date||"")} (dashed)${c.stale?" · stale":""} · <a href="${E(c.src)}" target=_blank rel=noopener>Treasury</a></span></div>
  <svg viewBox="0 0 ${W} ${H}" class=fin-cv>${ticks}${c.month_ago?line(c.month_ago,"#6e7681",1):""}${line(c.now,"#58a6ff")}${c.tenors.map((t,i)=>`<text x=${x(i)} y=${H-4} class=fin-ax text-anchor=middle>${E(t.replace(" Mo","M").replace(" Yr","Y"))}</text>`).join("")}
  ${c.now.map((v,i)=>v==null?"":`<circle cx=${x(i)} cy=${y(v)} r=2.6 fill="#58a6ff"><title>${E(c.tenors[i])}: ${v}%</title></circle>`).join("")}</svg>
  <table class=fin-tb><tr>${c.tenors.map(t=>`<th>${E(t)}</th>`).join("")}</tr><tr>${c.now.map((v,i)=>`<td data-s="UST:${E(c.tenors[i])}" data-l="US Treasury ${E(c.tenors[i])}" class=fin-cl>${v==null?"—":v.toFixed(2)}</td>`).join("")}</tr>
  ${c.prev?`<tr class=meta>${c.now.map((v,i)=>{const p=c.prev[i];if(v==null||p==null)return"<td>—</td>";const b=Math.round((v-p)*100);return `<td class="${cl(b)}">${b>0?"+":""}${b} bp</td>`}).join("")}</tr>`:""}</table></div>`}
 if(d.intl_yields&&d.intl_yields.length)h+=`<div class=fin-cards>${d.intl_yields.map(x=>card({...x,sub:"official, end of day "+x.date+(x.stale?" (stale)":""),chg_pct:null,price:x.price},"%").replace(/<span class="fin-ch[^"]*">[^<]*<\/span>/,x.prev!=null?`<span class="fin-ch ${cl(x.price-x.prev)}">${(x.price-x.prev)>=0?"+":""}${Math.round((x.price-x.prev)*100)} bp</span>`:"")).join("")}</div>`;
 return h}
function opts(){const p=F.d.pcr;if(!p||!p.ratios)return `<div class=meta>Cboe put/call ratios unavailable right now — <a href="https://www.cboe.com/us/options/market_statistics/daily/" target=_blank rel=noopener>view on Cboe</a>.</div>`;
 return `<div class=fin-pcr><b>Cboe put/call ratios</b> <span class=meta>— session ${E(p.date)} (previous trading day, end of day)${p.stale?" · stale":""} · <a href="${E(p.src)}" target=_blank rel=noopener>Cboe</a></span>
 <div class=fin-pcrs>${Object.entries(p.ratios).map(([k,v])=>`<span class=fin-pc data-s="PCR:${E(k)}" data-l="${E(k)}" title="Click for the archived daily history (builds up day by day)">${E(k.replace(" PUT/CALL RATIO","").replace("CBOE VOLATILITY INDEX (VIX)","VIX options").toLowerCase())} <b>${v.toFixed(2)}</b></span>`).join("")}</div>
 <div class=meta>Options chains and intraday options flow are not freely available as an API here: <a href="https://www.cboe.com/delayed_quotes/spx/quote_table" target=_blank rel=noopener>SPX delayed chain (Cboe)</a> · <a href="https://www.cboe.com/us/options/market_statistics/" target=_blank rel=noopener>Cboe market statistics</a> (link only).</div></div>`}
function ecb(){const x=F.d.ecb;if(!x||!x.rates)return"";const K=["EUR","JPY","GBP","CHF","CAD","AUD","CNY","INR","MXN","BRL","KRW","SEK"];
 return `<div class=fin-pcr><b>ECB euro reference rates, per 1 USD</b> <span class=meta>— ${E(x.date)} (published ~16:00 CET on TARGET days) · <a href="${E(x.src)}" target=_blank rel=noopener>ECB</a> via Frankfurter</span><div class=fin-pcrs>${K.filter(k=>x.rates[k]).map(k=>`<span class=fin-pc>${k} <b>${x.rates[k]}</b></span>`).join("")}</div></div>`}
async function load(force){if(F.busy)return;F.busy=true;const b=M.querySelector("#fin_ref");b&&(b.disabled=true);
 try{const r=await fetch("api/finance"+(force?"?force=1":""),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);F.d=j;F.t=Date.now();render()}
 catch(e){if(!F.d)app.innerHTML=`<div class=meta>Finance data unavailable: ${E(e.message||e)}</div>`}finally{F.busy=false;b&&(b.disabled=false)}}
const vis=()=>M.style.display!="none";
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(!b)return;if(b.dataset.tab=="finance"){setTimeout(()=>{if(!F.d||Date.now()-F.t>170000)load()},0)}});
setInterval(()=>{if(vis()&&!document.hidden)load()},180000);
M.querySelector("#fin_ref").onclick=()=>load(true);
// ---- big interactive chart (lightweight-charts, local copy) ----
let lwcP=null;const lwc=()=>lwcP||(lwcP=new Promise((ok,no)=>{if(window.LightweightCharts)return ok(window.LightweightCharts);const s=document.createElement("script");s.src="api/finance/lwc.js";s.onload=()=>ok(window.LightweightCharts);s.onerror=no;document.head.appendChild(s)}));
const RANGES=[["1d","1D"],["5d","5D"],["1mo","1M"],["6mo","6M"],["1y","1Y"]];
let dlg=null,chartObj=null;
async function openChart(sym,label,rg){rg=rg||(/^(UST:|BUND|JGB|PCR:)/.test(sym)?"6mo":"1d");
 if(!dlg){dlg=document.createElement("div");dlg.className="fin-modal";dlg.innerHTML=`<div class=fin-box role=dialog aria-modal=true><div class=fin-bh><b class=fin-bt></b><span class=fin-rg></span><button type=button class=fin-x title="Close (Esc)">✕</button></div><div class=fin-bm></div><div class=fin-cc></div><div class="meta fin-bf"></div></div>`;
  document.body.appendChild(dlg);dlg.addEventListener("click",e=>{if(e.target==dlg||e.target.closest(".fin-x"))close()});addEventListener("keydown",e=>{if(e.key=="Escape"&&dlg.style.display!="none")close()})}
 dlg.style.display="flex";dlg.querySelector(".fin-bt").textContent=`${label} (${sym})`;
 dlg.querySelector(".fin-rg").innerHTML=RANGES.map(([k,l])=>`<button type=button data-r=${k} class="${k==rg?"on":""}">${l}</button>`).join("");
 dlg.querySelectorAll(".fin-rg button").forEach(b=>b.onclick=()=>openChart(sym,label,b.dataset.r));
 const cc=dlg.querySelector(".fin-cc");dlg.querySelector(".fin-bm").textContent="Loading…";
 try{const [L,r]=await Promise.all([lwc(),fetch(`api/finance/chart?s=${encodeURIComponent(sym)}&r=${rg}`,{cache:"no-store"})]);const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);
  if(chartObj){chartObj.remove();chartObj=null}cc.innerHTML="";
  const pts=j.points||[];if(!pts.length){dlg.querySelector(".fin-bm").textContent="No data points for this range yet"+(sym.startsWith("PCR:")?" — the put/call history builds up one session per day.":".");return}
  const daily=j.daily||/^(6mo|1y)$/.test(rg);
  const fmt=t=>new Date(t*1000).toLocaleString("en-US",daily?{timeZone:daily&&j.daily?"UTC":TZ,month:"short",day:"numeric",year:"numeric"}:{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
  chartObj=L.createChart(cc,{autoSize:true,layout:{background:{color:"#0f1318"},textColor:"#c9d1d9",attributionLogo:true},grid:{vertLines:{color:"#1d232b"},horzLines:{color:"#1d232b"}},
   rightPriceScale:{borderColor:"#30363d"},timeScale:{borderColor:"#30363d",timeVisible:!daily,secondsVisible:false,tickMarkFormatter:(t,ty)=>new Date(t*1000).toLocaleString("en-US",(daily||ty<3)?{timeZone:j.daily?"UTC":TZ,month:"short",day:"numeric"}:{timeZone:TZ,hour:"numeric",minute:"2-digit"})},
   localization:{timeFormatter:fmt},crosshair:{mode:0}});
  const first=pts[0][1],lastv=pts[pts.length-1][1],base=(rg=="1d"&&j.prev)?j.prev:first,up=lastv>=base;
  const s=chartObj.addSeries(L.AreaSeries,{lineColor:up?"#3fb950":"#f85149",topColor:up?"rgba(63,185,80,.35)":"rgba(248,81,73,.35)",bottomColor:"rgba(0,0,0,0)",lineWidth:2,priceFormat:{type:"price",precision:Math.abs(lastv)<20?4:2,minMove:Math.abs(lastv)<20?.0001:.01}});
  s.setData(pts.map(p=>({time:p[0],value:p[1]})));if(rg=="1d"&&j.prev)s.createPriceLine({price:j.prev,color:"#8b949e",lineStyle:2,lineWidth:1,axisLabelVisible:true,title:"prev close"});
  chartObj.timeScale().fitContent();
  const ch=(lastv/base-1)*100;dlg.querySelector(".fin-bm").innerHTML=`<b>${fmtP(lastv,sym)}</b> <span class="fin-ch ${cl(ch)}">${pc(ch)}</span> <span class=meta>over ${E(RANGES.find(x=>x[0]==rg)[1])}${rg=="1d"&&j.prev?" vs previous close":""}</span>`;
  dlg.querySelector(".fin-bf").textContent=`${j.src||"Official end-of-day data"}${j.exch?" · "+j.exch:""}${j.interval?" · "+j.interval+" bars":""}${j.fetched?" · fetched "+etT(j.fetched):""} · times in ET${j.note?" · "+j.note:""}`}
 catch(e){dlg.querySelector(".fin-bm").textContent="Chart unavailable: "+(e.message||e)}}
function close(){dlg.style.display="none";if(chartObj){chartObj.remove();chartObj=null}}
app.addEventListener("click",e=>{const c=e.target.closest("[data-s]");if(c&&!e.target.closest("a"))openChart(c.dataset.s,c.dataset.l||c.dataset.s)});
window.BNFin={open:openChart};
})();
