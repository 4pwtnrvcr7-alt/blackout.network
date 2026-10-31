// ---- 👤 Elon Musk tab (served by elon.py). Neutral: headlines verbatim, topic sorting by keywords only. Times in ET. ----
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):"#";const TZ="America/New_York";
const etT=t=>{if(!t)return"—";const d=new Date(t);return isNaN(d)?E(t):d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const ago=t=>{const m=Math.round((Date.now()-Date.parse(t))/60000);return isNaN(m)?"":m<60?m+" min ago":m<1440?Math.round(m/60)+" h ago":Math.round(m/1440)+" d ago"};
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="elon"]');if(!tb){tb=document.createElement("button");tb.dataset.tab="elon";tb.textContent="👤 Elon Musk";nav.appendChild(tb)}
const anchor=nav.querySelector('button[data-tab="spacex"]')||nav.querySelector('button[data-tab="jets"]');if(anchor)anchor.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.elon="elon";HASHTAB.elon="elon"}}catch(_){}
let M=document.getElementById("tab-elon");
if(!M){M=document.createElement("main");M.id="tab-elon";M.dataset.addon="elon";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn" id="em_top"><h2><span>👤</span> Elon Musk <span class="meta">— news by company and topic, net worth, Tesla stock, prediction markets, his jets and related alerts</span><button type="button" class="tab-ref" id="em_ref" title="Re-check the sources now (cached 5–30 min)">⟳ Refresh</button></h2><div id="em_app"><div class="meta">Loading…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
if(location.hash=="#elon")setTimeout(()=>tb.click(),350);
const app=M.querySelector("#em_app");const S={d:null,t:0,busy:false,topic:"All"};
const pc=v=>v==null?"—":(v>0?"+":"")+v.toFixed(2)+"%";const cl=v=>v==null?"":v>0?"up":v<0?"dn":"";
function spark(a,up){if(!a||a.length<2)return"";let lo=Math.min(...a),hi=Math.max(...a);if(hi==lo){hi++;lo--}
 return `<svg class=em-sp viewBox="0 0 100 28" preserveAspectRatio="none"><polyline points="${a.map((v,i)=>`${(i/(a.length-1)*100).toFixed(1)},${(26-(v-lo)/(hi-lo)*24).toFixed(1)}`).join(" ")}" fill=none stroke="${up?"#3fb950":"#f85149"}" stroke-width=1.4 vector-effect=non-scaling-stroke /></svg>`}
function render(){const d=S.d;if(!d)return;const nw=d.networth,t=d.tsla,items=(d.news||{}).items||[],mk=(d.markets||{}).items||[],jt=(d.jets||{}).items||[],al=(d.alerts||{}).items||[];
 const counts={};items.forEach(x=>x.topics.forEach(k=>counts[k]=(counts[k]||0)+1));
 const shown=S.topic=="All"?items:items.filter(x=>x.topics.includes(S.topic));
 const kpi=`<div class=em-kpis>
  <div class=em-kpi><div class=meta>Net worth (Forbes real-time)</div>${nw?`<b>$${nw.usd_b.toLocaleString()}B</b> <span class=meta>#${nw.rank} worldwide${nw.stale?" · stale":""}</span><div class=meta>${(nw.top||[]).slice(1,3).map(p=>`#${p.rank} ${E(p.name)} $${p.usd_b}B`).join(" · ")}</div><div class=meta>fetched ${etT(nw.fetched)} · <a href="${U(nw.src)}" target=_blank rel=noopener>Forbes</a>${nw.history&&nw.history.length>1?` · ${nw.history.length}-day log`:""}</div>`:"<span class=meta>unavailable</span>"}</div>
  <button type=button class="em-kpi em-tsla" title="Open the Tesla chart (Finance tab chart viewer)"><div class=meta>Tesla (TSLA) · Yahoo, delayed</div>${t&&t.price!=null?`<b>$${t.price.toFixed(2)}</b> <span class="em-ch ${cl(t.chg_pct)}">${pc(t.chg_pct)}</span>${spark(t.spark,(t.chg_pct||0)>=0)}<div class=meta>last trade ${etT(t.market_time)}</div>`:"<span class=meta>unavailable</span>"}</button>
  <div class=em-kpi><div class=meta>His posts on X</div><a href="https://x.com/elonmusk" target=_blank rel=noopener><b>@elonmusk →</b></a><div class=meta>Link only: X has no free, keyless API, so posts are not pulled into this page.</div></div></div>`;
 const jets=`<div class=em-col><h3>✈ Musk-linked jets <span class=meta>— observed ADS-B (${E((d.jets||{}).src||"adsb.lol")}), checked ${etT((d.jets||{}).fetched)}</span></h3><ul class=em-ul>${jt.map(j=>`<li><b>${E(j.reg)}</b> <span class="em-pill ${j.airborne?"air":""}">${j.airborne?"airborne":j.seen?"on ground":"not seen"}</span> <span class=meta>${E(j.label)}</span>
  ${j.airborne?`<div class=meta>${j.alt!=null?Number(j.alt).toLocaleString()+" ft":""}${j.gs!=null?" · "+Math.round(j.gs)+" kt":""}${j.track!=null?" · heading "+Math.round(j.track)+"°":""}${j.lat!=null?` · ${j.lat.toFixed(2)}, ${j.lon.toFixed(2)}`:""}</div>`:""}<a href="${U(j.map)}" target=_blank rel=noopener>live map →</a></li>`).join("")}</ul>
  <div class=meta>"Not seen" never means "not flying" (transponder privacy programs, coverage gaps). Who is aboard is never known from ADS-B.</div></div>`;
 const pm=`<div class=em-col><h3>Prediction markets <span class=meta>— open Polymarket markets tagged Elon Musk, read-only prices</span></h3><ul class=em-ul>${mk.map(m=>`<li><a href="${U(m.url)}" target=_blank rel=noopener>${E(m.title)}</a><div class=meta>${m.top.map(o=>`${E(o.q)} <b>${Math.round(o.yes*100)}%</b>`).join(" · ")}${m.vol24?` · 24h vol $${Math.round(m.vol24).toLocaleString()}`:""}</div></li>`).join("")||"<li class=meta>none open</li>"}</ul></div>`;
 const alerts=`<div class=em-col><h3>Related alerts <span class=meta>— items on The Wire / Watchlist mentioning Musk or his companies (read-only, last 14 days)</span></h3><ul class=em-ul>${al.map(x=>`<li><a href="#" data-goto="${E(x.cid)}">${E(x.title)}</a><div class=meta>${E(x.list)} · rank ${x.rank??"—"}/10 · score ${x.score??"—"} · ${etT(x.time)}${x.url?` · <a href="${U(x.url)}" target=_blank rel=noopener>source</a>`:""}</div></li>`).join("")||"<li class=meta>none</li>"}</ul></div>`;
 const chips=["All",...d.buckets].filter(k=>k=="All"||counts[k]).map(k=>`<button type=button class="em-chip${S.topic==k?" on":""}" data-k="${E(k)}">${E(k)} <span>${k=="All"?items.length:counts[k]}</span></button>`).join("");
 const news=`<div class=em-col><h3>News <span class=meta>— Google News, last 2 days, newest first; headlines verbatim from each publisher</span></h3><div class=em-chips>${chips}</div><ul class="em-ul em-news">${shown.map(x=>`<li><a href="${U(x.url)}" target=_blank rel=noopener>${E(x.title)}</a><div class=meta>${E(x.source)} · ${etT(x.time)} (${ago(x.time)}) · ${x.topics.map(E).join(", ")}</div></li>`).join("")||"<li class=meta>No headlines.</li>"}</ul></div>`;
 app.innerHTML=`<div class=em-note>${E(d.note)} Updated ${etT(d.updated)}.${Object.keys(d.errors||{}).length?` <span class=em-err>Source issues: ${Object.entries(d.errors).map(([k,v])=>E(k+": "+v)).join(" · ")}</span>`:""}</div>${kpi}
 <div class=em-grid>${news}<div>${jets}${pm}${alerts}</div></div><div class=em-src>Links: ${d.links.map(l=>`<a href="${U(l[1])}" target=_blank rel=noopener>${E(l[0])}</a>`).join(" · ")}</div>`;
 app.querySelectorAll(".em-chip").forEach(b=>b.onclick=()=>{S.topic=b.dataset.k;render()});
 const ts=app.querySelector(".em-tsla");if(ts)ts.onclick=()=>{if(window.BNFin)window.BNFin.open("TSLA","Tesla");else{const f=document.querySelector('.tabs button[data-tab="finance"]');f&&f.click()}};
 app.querySelectorAll("[data-goto]").forEach(a=>a.onclick=e=>{e.preventDefault();document.querySelector('.tabs button[data-tab="threat"]').click();setTimeout(()=>{const el=document.querySelector(`[data-cid="${CSS.escape(a.dataset.goto)}"]`);if(el){el.scrollIntoView({block:"center"});el.style.outline="2px solid var(--hi)";setTimeout(()=>el.style.outline="",2500)}},300)})}
async function load(force){if(S.busy)return;S.busy=true;const b=M.querySelector("#em_ref");b&&(b.disabled=true);
 try{const r=await fetch("api/elon"+(force?"?force=1":""),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);S.d=j;S.t=Date.now();render()}
 catch(e){if(!S.d)app.innerHTML=`<div class=meta>Data unavailable: ${E(e.message||e)}</div>`}finally{S.busy=false;b&&(b.disabled=false)}}
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="elon")setTimeout(()=>{if(!S.d||Date.now()-S.t>240000)load()},0)});
setInterval(()=>{if(M.style.display!="none"&&!document.hidden)load()},300000);
M.querySelector("#em_ref").onclick=()=>load(true);
})();
