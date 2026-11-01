/* Wire history (t246, wire_history.py): scrollable timeline on The Wire tab. Stored scanner stories (blackout.db) + real archived
   source items (trends_history.db, labelled ARCHIVE). Archive items are display-only: they never reach the live Wire, alert bar,
   briefs, pushes or newsletters. Lazy-loads older pages with ?before=<cursor>. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safe=u=>/^https?:\/\//i.test(u||"")?u:"#";
const TZ="America/New_York";
const fD=new Intl.DateTimeFormat("en-US",{timeZone:TZ,weekday:"long",year:"numeric",month:"long",day:"numeric"});
const fK=new Intl.DateTimeFormat("en-CA",{timeZone:TZ,year:"numeric",month:"2-digit",day:"2-digit"});
const fT=new Intl.DateTimeFormat("en-US",{timeZone:TZ,hour:"numeric",minute:"2-digit"});
const fS=new Intl.DateTimeFormat("en-US",{timeZone:TZ,year:"numeric",month:"short",day:"numeric"});
const fH=new Intl.DateTimeFormat("en-US",{timeZone:TZ,hour:"2-digit",hourCycle:"h23"});
const dayKey=t=>fK.format(new Date(t));
const sd=t=>t?fS.format(new Date(t))+" ET":"—";
const lv=s=>s>=60?"h":s>=35?"m":"l";
const CATC={"war/conflict":"#ff6b6b","natural disaster":"#ffa94d","disease":"#69db7c","cyber":"#4dabf7","political":"#b197fc","space weather":"#ffd43b",
 "financial":"#38d9a9","ufo/uap":"#e599f7","spiritual/religious":"#a9e34b","other":"#adb5bd"};
const cc=c=>CATC[c]||"#adb5bd";
/* UTC ISO for 00:00 Eastern on y-m-d (handles EDT/EST) */
function etMidnight(y,m,d){const n=new Date(Date.UTC(y,m-1,d));y=n.getUTCFullYear();m=n.getUTCMonth()+1;d=n.getUTCDate();for(const off of [4,5]){const t=new Date(Date.UTC(y,m-1,d,off));if(+fH.format(t)%24===0&&fK.format(t)===`${y}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")}`)return t}return new Date(Date.UTC(y,m-1,d,5))}
const iso=d=>d.toISOString().slice(0,19)+"Z";
const H={next:null,loading:false,end:false,req:0,lastDay:null,cats:new Set(),arch:"1",lists:new Set(["wire","watch"]),meta:null,n:0,jumped:false,inited:false};

function mount(){
 const host=$("tab-threat"),tl=$("tl");if(!host||$("wh"))return !!$("wh");
 const s=document.createElement("section");s.className="pn";s.id="wh";s.style.gridColumn="1/-1";
 s.innerHTML=`<h2>🗂 Timeline history <span class="meta">every stored scanner story + real archived source data · scroll to load older items</span></h2>
 <div class="wh-cov" id="wh_cov">loading coverage…</div>
 <details class="wh-src" id="wh_srcbox"><summary>Earliest date available per source</summary><div id="wh_src"></div></details>
 <div class="wh-bar">
  <form id="wh_jump" class="wh-jump" novalidate><label class="wh-lbl" for="wh_date">Jump to date</label><input type="date" id="wh_date" required><button type="submit">Go</button></form>
  <div class="wh-quick" role="group" aria-label="Quick jumps"><button data-j="0" class="on">Latest</button><button data-j="7">1 wk ago</button><button data-j="30">1 mo</button><button data-j="182">6 mo</button><button data-j="365">1 yr</button><button data-j="first">Earliest</button></div>
 </div>
 <div class="wh-bar">
  <div class="wh-seg" role="group" aria-label="Archive items"><span class="wh-lbl">Show</span><button data-a="1" class="on">Live + archive</button><button data-a="0">Live only</button><button data-a="only">Archive only</button></div>
  <div class="wh-lists"><label class="sw"><input type="checkbox" data-l="wire" checked> Wire</label><label class="sw"><input type="checkbox" data-l="watch" checked> Watchlist</label><label class="sw" title="Stories the scanner kept but suppressed as low signal"><input type="checkbox" data-l="bg"> Low-signal</label></div>
 </div>
 <div class="wh-cats" id="wh_cats" role="group" aria-label="Category filters"></div>
 <div class="wh-status"><span id="wh_at" class="meta"></span><button id="wh_top" hidden>↑ Back to latest</button></div>
 <div class="wh-list" id="wh_list" tabindex="0" aria-label="Timeline history list"><div id="wh_items"></div><div id="wh_sent" class="wh-sent meta">loading…</div></div>
 <div class="meta wh-note">Times are Eastern (ET). <b class="wh-ab">ARCHIVE</b> items are real records from public archives (USGS, GDACS, NASA EONET, WHO, CISA, GFZ Potsdam, NOAA SWPC and more), shown for history only. They never appear in the live Wire feed, the alert bar, briefs, push notifications or newsletters. Their "archive rank" comes from the scanner's own scoring code applied to the archived record, on the same 0–10 scale. Live items show the time the scanner first caught them.</div>`;
 if(tl&&tl.parentNode===host)tl.after(s);else host.prepend(s);
 s.querySelector(".wh-quick").onclick=e=>{const b=e.target.closest("button");if(!b)return;s.querySelectorAll(".wh-quick button").forEach(x=>x.classList.toggle("on",x===b));
  const j=b.dataset.j;if(j==="0")return jump(null);if(j==="first"){const m=H.meta;if(m&&m.earliest){const d=new Date(new Date(m.earliest).getTime());return jump(new Date(d.getTime()+86400e3*1))}return}
  const k=dayKey(Date.now()-(+j)*86400e3).split("-").map(Number);jump(etMidnight(k[0],k[1],k[2]+1))};
 $("wh_jump").onsubmit=e=>{e.preventDefault();let v=$("wh_date").value;if(!/^\d{4}-\d\d-\d\d$/.test(v))return;const mn=$("wh_date").min;H.clamp=mn&&v<mn?v:null;if(H.clamp){v=mn;$("wh_date").value=mn}const [y,m,d]=v.split("-").map(Number);
  s.querySelectorAll(".wh-quick button").forEach(x=>x.classList.remove("on"));jump(etMidnight(y,m,d+1))};
 s.querySelector(".wh-seg").onclick=e=>{const b=e.target.closest("button[data-a]");if(!b)return;H.arch=b.dataset.a;s.querySelectorAll(".wh-seg button").forEach(x=>x.classList.toggle("on",x===b));reset()};
 s.querySelector(".wh-lists").onchange=e=>{const k=e.target.dataset.l;if(!k)return;e.target.checked?H.lists.add(k):H.lists.delete(k);if(!H.lists.size){H.lists.add("wire");s.querySelector('[data-l=wire]').checked=true}reset()};
 $("wh_cats").onclick=e=>{const b=e.target.closest("button[data-c]");if(!b)return;const c=b.dataset.c;
  if(c==="*"){H.cats.clear()}else{H.cats.has(c)?H.cats.delete(c):H.cats.add(c)}
  $("wh_cats").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x.dataset.c==="*"?!H.cats.size:H.cats.has(x.dataset.c)));reset()};
 $("wh_top").onclick=()=>{s.querySelectorAll(".wh-quick button").forEach(x=>x.classList.toggle("on",x.dataset.j==="0"));jump(null)};
 const io=new IntersectionObserver(es=>{if(es.some(x=>x.isIntersecting))more()},{root:$("wh_list"),rootMargin:"600px 0px"});io.observe($("wh_sent"));
 return true}

async function loadMeta(){try{const r=await fetch("api/wire_history/meta",{cache:"no-store"});if(!r.ok)throw r.status;const m=await r.json();H.meta=m;drawMeta(m)}catch(e){$("wh_cov").textContent="coverage unavailable ("+e+")"}}
function drawMeta(m){const L=m.live,A=m.archive;
 $("wh_cov").innerHTML=`<b>Earliest date on this timeline: ${esc(sd(m.earliest))}</b> · Live scanner: ${L.stories.toLocaleString()} stored stories since ${esc(sd(L.earliest))}`+
  (A?` · <span class="wh-ab">ARCHIVE</span> ${A.stories.toLocaleString()} stories from public archives, ${esc(sd(A.earliest))} → ${esc(sd(A.latest))}`:` · archive data not available yet`);
 if(m.earliest){$("wh_date").min=dayKey(m.earliest)}$("wh_date").max=dayKey(Date.now());
 let h="";if(A){h+=`<table class="wh-t"><thead><tr><th>Archive source</th><th>Earliest item</th><th>Items kept</th><th>Status</th></tr></thead><tbody>`+
  A.sources.map(s=>`<tr class="${s.status!="ok"?"na":""}"><td><a href="${esc(safe(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.name)}</a></td><td>${esc(s.earliest?sd(s.earliest):"—")}</td><td>${(s.kept||0).toLocaleString()}</td><td>${esc(s.status)}${s.note?`<div class=meta>${esc(s.note)}</div>`:""}</td></tr>`).join("")+`</tbody></table>
  <div class="meta">Archive covers ${esc(sd(A.earliest))} up to the moment the live scanner started (${esc(sd(A.seam))}), so nothing is counted twice. Built ${esc(sd(A.built))}.</div>`}
 h+=`<table class="wh-t"><thead><tr><th>Live scanner source</th><th>Earliest stored</th><th>Items</th></tr></thead><tbody>`+L.sources.map(s=>`<tr><td>${esc(s.name)}</td><td>${esc(sd(s.earliest))}</td><td>${s.items.toLocaleString()}</td></tr>`).join("")+`</tbody></table>`;
 $("wh_src").innerHTML=h;
 const cats=Object.entries(m.categories).sort((a,b)=>b[1]-a[1]);
 $("wh_cats").innerHTML=`<button data-c="*" class="${H.cats.size?"":"on"}">All categories</button>`+cats.map(([c,n])=>`<button data-c="${esc(c)}" class="${H.cats.has(c)?"on":""}" style="--cc:${cc(c)}"><i></i>${esc(c)} <span>${n.toLocaleString()}</span></button>`).join("")}

function jump(d){H.before=d?iso(d):null;H.jumped=!!d;reset()}
function reset(){H.next=H.before||null;H.end=false;H.lastDay=null;H.n=0;H.req++;H.loading=false;$("wh_items").innerHTML="";$("wh_list").scrollTop=0;$("wh_top").hidden=!H.jumped;
 $("wh_at").textContent=(H.clamp?`Nothing is stored before ${sd(H.meta&&H.meta.earliest)}, so this starts at the earliest day. `:"")+(H.before?`Showing items up to the end of ${sd(new Date(new Date(H.before).getTime()-1))}, older below`:"Showing newest first");H.clamp=null;more()}
async function more(){if(H.loading||H.end)return;H.loading=true;const q=H.req;$("wh_sent").textContent="loading…";
 const p=new URLSearchParams({limit:"60",archive:H.arch,lists:[...H.lists].join(",")});if(H.next)p.set("before",H.next);if(H.cats.size)p.set("cats",[...H.cats].join(","));
 try{const r=await fetch("api/wire_history?"+p,{cache:"no-store"});const j=await r.json();if(q!==H.req)return;if(!r.ok)throw j.error||r.status;
  draw(j.items);H.next=j.next;H.end=j.end;H.n+=j.items.length;
  $("wh_sent").textContent=H.end?(H.n?`End of timeline · ${H.n.toLocaleString()} item(s) loaded`:"Nothing matches these filters."):`${H.n.toLocaleString()} loaded · scroll for older…`}
 catch(e){if(q===H.req)$("wh_sent").textContent="✗ "+e}
 finally{if(q===H.req){H.loading=false;const L=$("wh_list");if(!H.end&&L.scrollHeight<=L.clientHeight+700)setTimeout(more,50)}}}
function draw(items){let h="";for(const x of items){const k=dayKey(x.t);if(k!==H.lastDay){H.lastDay=k;h+=`<div class="wh-day">${esc(fD.format(new Date(x.t)))} <span>ET</span></div>`}
  const a=x.archive,fam=(x.families||[]).join(", ");const ev=x.event_time&&!a&&Math.abs(new Date(x.event_time)-new Date(x.t))>864e5?` · event ${esc(sd(x.event_time))}`:"";
  h+=`<article class="wh-it ${a?"ar":lv(x.score)}" style="--cc:${cc(x.category)}">
   <div class="wh-tm">${esc(fT.format(new Date(x.t)))}</div>
   <div class="wh-bd"><div class="wh-m">${a?`<b class="wh-ab" title="Real archived record; history only, not a live alert">ARCHIVE</b><span class="wh-rk" title="Scanner scoring code applied to the archived record (0–10)">archive rank ${x.rank}/10</span>`:`<span class="sc ${lv(x.score)}">${x.score}</span><span class="wh-rk">rank ${x.rank}/10</span>${x.watchlist==1?'<span class="wh-wl">Watchlist</span>':x.watchlist==2?'<span class="wh-wl bg">Low-signal</span>':""}`}
    <span class="wh-cat"><i></i>${esc(x.category)}</span>${x.location?`<span class="meta">${esc(x.location)}</span>`:""}</div>
    <div class="wh-ti">${esc(x.title)}</div>
    <div class="meta">${fam?esc(fam):""}${ev}${(x.links||[]).length?" · "+x.links.slice(0,3).map(l=>`<a href="${esc(safe(l.url))}" target="_blank" rel="noopener noreferrer">${esc(l.source||"source")}${a?" (archive)":""} ↗</a>`).join(" · "):""}</div></div></article>`}
 $("wh_items").insertAdjacentHTML("beforeend",h)}

function init(){if(H.inited)return;if(!mount())return setTimeout(init,400);H.inited=true;loadMeta();reset();setInterval(loadMeta,300000)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
window.BNWireHistory={reload:()=>{loadMeta();if(!H.jumped&&$("wh_list").scrollTop<40)reset()}};
})();
