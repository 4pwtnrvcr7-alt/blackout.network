// ---- Background Noise tab (served by bnoise.py; read-only view of blackout.db). Every alert ranked 0-6, newest first. ----
(()=>{"use strict";
const M=document.getElementById("tab-noise");if(!M)return;
const E=s=>(typeof esc=="function"?esc:(x=>String(x)))(s==null?"":String(s));
const U=u=>typeof safeUrl=="function"?safeUrl(u):(/^https?:\/\//i.test(u||"")?u:"#");
const ET=t=>{if(!t)return"time n/a";const d=new Date(t);if(isNaN(d))return"time n/a";
 return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)};
const LV2=s=>typeof lv=="function"?lv(s):(s>=60?"h":s>=35?"m":"l");
const RL=r=>r>=5?"m":r>=3?"l2":"l";   // rank-badge shade inside the 0-6 band
const LIST={wire:"",watchlist:'<span class="wl">Watchlist</span><span class="unc">unconfirmed</span>',suppressed:'<span class="unc" title="Low-signal item the scanner stores but keeps off The Wire and the Watchlist">off the Wire · unconfirmed</span>'};
const PAGE=100;
const N={items:[],ids:new Set(),total:0,matching:0,rank:"",busy:false,done:false,loaded:false,summary:null,last:0};

// ---------- tab button + deep link (#noise), in the Monitor group right after The Wire ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="noise"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="noise";tb.textContent="🔉 Background Noise";tb.title="Every alert ranked 0 to 6, newest first";nav.appendChild(tb)}
const wire=nav&&nav.querySelector('button[data-tab="threat"]');if(wire&&tb)wire.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.noise="noise";HASHTAB.noise="noise"}}catch(_){}
if(location.hash=="#noise")setTimeout(()=>{if(!tb.classList.contains("on"))tb.click()},350);

// ---------- skeleton ----------
const app=document.getElementById("bn_app");
app.innerHTML=`<div class="bn-bar"><span class="bn-lbl">Rank</span><div class="bn-seg" id="bn_rank" role="group" aria-label="Show rank"></div><span class="meta" id="bn_msg"></span></div>
<div class="bn-sum" id="bn_sum">Loading…</div><div id="bn_list" class="bn-list"></div><div id="bn_more" class="bn-more"></div>`;
const h2=M.querySelector("h2");
if(h2&&typeof hwAttach=="function")hwAttach(h2,"noise",()=>"This tab lists every alert ranked 0 to 6 that blackout.network has stored, newest first. Anything in that range comes in automatically with no extra filtering, including Watchlist and other unconfirmed single-source items, which are labeled unconfirmed. Each row shows its 0–10 rank and 0–100 score, category, time in ET, place if known and links to the original sources. It refreshes with the rest of the dashboard.");

function badge(r){return window.bnMeter?bnMeter(r,"s"):`<span class="bn-rk ${RL(r)}" title="rank ${r} of 10">rank ${r}/10</span>`}
function row(x){const t=LV2(x.score);const loc=x.location?` · ${E(x.location)}`:"";
 const fam=x.n_families?` · ${x.n_items} report(s) from ${x.n_families} source famil${x.n_families==1?"y":"ies"}`:"";
 const ev=x.event_time&&x.event_time!=x.first_seen?` · event ${E(ET(x.event_time))}`:"";
 return `<div class="bn-row ${t}" data-cid="${E(x.cluster_id)}"><span class="sc ${t}">${E(x.score)}</span>${badge(x.rank)}<b>${E(x.title)}</b> ${LIST[x.list]||""}
<div class="meta">${E(x.category||"other")}${loc} · seen ${E(ET(x.first_seen))}${ev}${fam}</div>
<div class="meta">${(x.links||[]).map(l=>`<a href="${E(U(l.url))}" target="_blank" rel="noopener noreferrer">${E(l.source||"source")}</a>`).join(" · ")||"no source link"}</div>
${x.brief?`<div class="brief">${E(x.brief)}</div>`:""}</div>`}
function sumHTML(s){if(!s)return"";const bl=s.by_list||{};
 return `<b>${(s.total||0).toLocaleString()}</b> alerts ranked 0–6 · lowest rank shown <b>${s.rank_min??"–"}</b>, highest <b>${s.rank_max??"–"}</b>
 <span class="meta"> · ${(bl.wire||0).toLocaleString()} on The Wire, ${((bl.watchlist||0)+(bl.suppressed||0)).toLocaleString()} unconfirmed · ${s.oldest?`${E(ET(s.oldest))} – ${E(ET(s.newest))}`:""}</span>`}
function segs(){const s=N.summary||{},br=s.by_rank||{};
 document.getElementById("bn_rank").innerHTML=[["","All 0–6",s.total],...[0,1,2,3,4,5,6].map(r=>[String(r),String(r),br[r]])].map(([v,l,n])=>`<button type="button" data-v="${v}" class="${v==N.rank?"on":""}">${l}${n!=null?` <span class="meta">${Number(n).toLocaleString()}</span>`:""}</button>`).join("")}
document.getElementById("bn_rank").addEventListener("click",e=>{const b=e.target.closest("button[data-v]");if(!b||b.dataset.v==N.rank)return;N.rank=b.dataset.v;reset()});

async function fetchPage(off,lim){const q=new URLSearchParams({offset:off,limit:lim});if(N.rank!=="")q.set("rank",N.rank);
 const r=await fetch("api/noise?"+q,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;return j}
function paint(){const L=document.getElementById("bn_list");
 L.innerHTML=N.items.map(row).join("")||'<div class="meta">No alerts ranked 0–6 stored yet.</div>';
 document.getElementById("bn_sum").innerHTML=sumHTML(N.summary);segs();
 document.getElementById("bn_more").innerHTML=N.done?`<span class="meta">Showing all ${N.items.length.toLocaleString()} of ${N.matching.toLocaleString()}</span>`:`<button type="button" id="bn_more_b">Load more (${N.items.length.toLocaleString()} of ${N.matching.toLocaleString()} shown)</button>`;
 const b=document.getElementById("bn_more_b");if(b)b.onclick=more;
}
async function more(){if(N.busy||N.done)return;N.busy=true;const m=document.getElementById("bn_msg");m.textContent="loading…";
 try{const j=await fetchPage(N.items.length,PAGE);N.summary=j.summary;N.matching=j.matching;
  j.items.forEach(x=>{if(!N.ids.has(x.cluster_id)){N.ids.add(x.cluster_id);N.items.push(x)}});
  N.done=!j.items.length||N.items.length>=N.matching;m.textContent="";N.loaded=true;N.last=Date.now();paint()}
 catch(e){m.textContent="Background Noise offline: "+e}finally{N.busy=false}}
function reset(){N.items=[];N.ids=new Set();N.done=false;N.matching=0;more()}
// auto-refresh: pull the newest page and merge new / updated items on top, without losing what's scrolled in
async function refresh(){if(!N.loaded||N.busy)return;N.busy=true;
 try{const j=await fetchPage(0,PAGE);N.summary=j.summary;N.matching=j.matching;const fresh=[];
  j.items.forEach(x=>{if(N.ids.has(x.cluster_id)){const i=N.items.findIndex(y=>y.cluster_id==x.cluster_id);if(i>=0)N.items[i]=x}else{N.ids.add(x.cluster_id);fresh.push(x)}});
  // drop items that left the band (e.g. re-ranked into High)
  const keep=new Set(j.items.map(x=>x.cluster_id)),cut=j.items.length?j.items[j.items.length-1].first_seen:"";
  N.items=fresh.concat(N.items).filter(x=>keep.has(x.cluster_id)||x.first_seen<cut);N.ids=new Set(N.items.map(x=>x.cluster_id));
  N.done=N.items.length>=N.matching;N.last=Date.now();paint();
  const m=document.getElementById("bn_msg");m.textContent=fresh.length?`${fresh.length} new since last refresh`:"";}
 catch(_){}finally{N.busy=false}}
const vis=()=>M.style.display!="none";
// infinite scroll: load the next page when the Load more button comes into view
if(window.IntersectionObserver){const io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting)&&vis()&&N.loaded)more()},{rootMargin:"600px"});io.observe(document.getElementById("bn_more"))}
if(nav)nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="noise"){if(!N.loaded)more();else if(Date.now()-N.last>30000)refresh()}});
const hook=()=>{if(typeof LV=="object"&&LV.es){["scan","alert"].forEach(ev=>LV.es.addEventListener(ev,()=>{clearTimeout(N.t);N.t=setTimeout(()=>vis()?refresh():(N.last=0),2000)}));return true}return false};
if(!hook())setTimeout(hook,1500);
setInterval(()=>{if(vis())refresh()},120000);
// the dashboard-wide Manual refresh / per-tab ⟳ Refresh: re-pull after the scan finishes
const rb=document.getElementById("refresh");if(rb)rb.addEventListener("click",()=>setTimeout(()=>{if(vis())refresh()},4000));
M.addEventListener("click",e=>{if(e.target.closest(".tab-ref"))setTimeout(refresh,4000)});
})();
