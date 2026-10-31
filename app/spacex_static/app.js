// ---- 🚀 SpaceX tab (served by spacex.py). Informational only; times in ET. ----
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):"#";const TZ="America/New_York";
const etT=t=>{if(!t)return"—";const d=new Date(t);return isNaN(d)?E(t):d.toLocaleString("en-US",{timeZone:TZ,weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const ago=t=>{const m=Math.round((Date.now()-Date.parse(t))/60000);return isNaN(m)?"":m<60?m+" min ago":m<1440?Math.round(m/60)+" h ago":Math.round(m/1440)+" d ago"};
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="spacex"]');if(!tb){tb=document.createElement("button");tb.dataset.tab="spacex";tb.textContent="🚀 SpaceX";nav.appendChild(tb)}
const anchor=nav.querySelector('button[data-tab="jets"]');if(anchor)anchor.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.spacex="spacex";HASHTAB.spacex="spacex"}}catch(_){}
let M=document.getElementById("tab-spacex");
if(!M){M=document.createElement("main");M.id="tab-spacex";M.dataset.addon="spacex";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn" id="sx_top"><h2><span>🚀</span> SpaceX <span class="meta">— next launch countdown, the launch schedule, Starship, Starlink, news and related alerts</span><button type="button" class="tab-ref" id="sx_ref" title="Re-check the sources now (cached 20–30 min; Launch Library allows 15 calls an hour)">⟳ Refresh</button></h2><div id="sx_app"><div class="meta">Loading SpaceX…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
if(location.hash=="#spacex")setTimeout(()=>tb.click(),350);
const app=M.querySelector("#sx_app");const S={d:null,t:0,busy:false};
const stc=s=>({Go:"go",Success:"ok",Failure:"bad","Partial Failure":"bad",Hold:"warn",TBD:"tbd",TBC:"tbd","In Flight":"go"}[s]||"tbd");
function row(x,past){return `<tr><td>${etT(x.net)}${x.precision&&x.precision!="Second"&&x.precision!="Minute"?`<div class=meta>NET, precision: ${E(x.precision)}</div>`:""}</td>
 <td><b>${E(x.mission||x.name)}</b><div class=meta>${E(x.rocket||"")}${x.orbit?" · "+E(x.orbit):""}${x.mission_type?" · "+E(x.mission_type):""}</div></td>
 <td>${E(x.pad||"")}<div class=meta>${E(x.site||"")}</div></td><td><span class="sx-st ${stc(x.status)}" title="${E(x.status_desc||"")}">${E(x.status||"—")}</span>${x.prob!=null?`<div class=meta>weather ${x.prob}% go</div>`:""}${x.fail?`<div class=meta>${E(x.fail)}</div>`:""}${x.hold?`<div class=meta>${E(x.hold)}</div>`:""}</td></tr>`}
function cd(){const el=app.querySelector(".sx-cd");if(!el)return;const t=Date.parse(el.dataset.t)-Date.now(),a=Math.abs(t)/1000,d=Math.floor(a/86400),h=Math.floor(a%86400/3600),m=Math.floor(a%3600/60),s=Math.floor(a%60);
 el.textContent=(t<0?"T+ ":"T− ")+(d?d+"d ":"")+String(h).padStart(2,"0")+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0")}
setInterval(cd,1000);
function render(){const d=S.d;if(!d)return;const n=d.next,up=(d.upcoming||{}).items||[],pv=(d.previous||{}).items||[],ss=d.starship||{},sl=d.starlink,nw=(d.news||{}).items||[],al=(d.alerts||{}).items||[];
 const hero=n?`<div class=sx-hero>${n.image?`<img src="${U(n.image)}" alt="" loading=lazy referrerpolicy=no-referrer>`:""}<div><div class=meta>Next SpaceX launch</div><div class=sx-hn>${E(n.mission||n.name)}</div>
  <div>${E(n.rocket||"")} · ${E(n.pad||"")}, ${E(n.site||"")}</div><div class=sx-cd data-t="${E(n.net)}"></div><div>${etT(n.net)} <span class="sx-st ${stc(n.status)}">${E(n.status_long||n.status||"")}</span>${n.win_end&&n.win_end!=n.win_start?` <span class=meta>window to ${etT(n.win_end)}</span>`:""}</div>
  ${n.desc?`<div class="meta sx-desc">${E(n.desc)}</div>`:""}<div class=sx-lk><a href="https://www.spacex.com/launches/" target=_blank rel=noopener>Watch: spacex.com/launches</a> · <a href="https://x.com/SpaceX" target=_blank rel=noopener>@SpaceX on X</a>${n.map?` · <a href="${U(n.map)}" target=_blank rel=noopener>pad map</a>`:""}</div></div></div>`:`<div class=meta>No upcoming SpaceX launch in Launch Library right now.</div>`;
 const stats=`<div class=sx-stats><span><b>${d.previous&&d.previous.year_count!=null?d.previous.year_count:"—"}</b> SpaceX launches in ${E((d.previous||{}).year||"")}</span><span><b>${(d.upcoming||{}).count??"—"}</b> scheduled</span><span><b>${ss.total_flights??"—"}</b> Starship flights to date</span><span><b>${sl?sl.tracked.toLocaleString():"—"}</b> Starlink satellites tracked${sl?` <span class=meta>(${sl.launched_this_year.toLocaleString()} launched in ${sl.year}; CelesTrak)</span>`:' <span class=meta>(CelesTrak unavailable)</span>'}</span></div>`;
 const tbl=(a,p)=>a.length?`<table class=sx-tb><tr><th>When (ET)</th><th>Mission</th><th>Pad</th><th>Status</th></tr>${a.map(x=>row(x,p)).join("")}</table>`:`<div class=meta>None listed.</div>`;
 const star=`<div class=sx-col><h3>Starship</h3><div class=meta>Upcoming</div>${tbl(ss.upcoming||[])}<div class=meta style="margin-top:6px">Recent flights</div>${tbl((ss.previous||[]).slice(0,4),1)}</div>`;
 const news=nw.map(x=>`<li><a href="${U(x.url)}" target=_blank rel=noopener>${E(x.title)}</a><div class=meta>${E(x.source||"")} · ${etT(x.time)} (${ago(x.time)}) · via ${E(x.via)}</div>${x.summary?`<div class=sx-sum>${E(x.summary)}</div>`:""}</li>`).join("");
 const alerts=al.length?al.map(x=>`<li><a href="#" data-goto="${E(x.cid)}">${E(x.title)}</a><div class=meta>${E(x.list)} · rank ${x.rank??"—"}/10 · score ${x.score??"—"} · ${E(x.confidence||"")} confidence · ${etT(x.time)}${x.url?` · <a href="${U(x.url)}" target=_blank rel=noopener>source</a>`:""}</div></li>`).join(""):`<li class=meta>No SpaceX/Starlink items on The Wire or Watchlist in the last ${(d.alerts||{}).days||14} days.</li>`;
 app.innerHTML=`<div class=sx-note>${E(d.note)} Updated ${etT(d.updated)}.${Object.keys(d.errors||{}).length?` <span class=sx-err>Source issues: ${Object.entries(d.errors).map(([k,v])=>E(k+": "+v)).join(" · ")} (showing last good data where available)</span>`:""}</div>
 ${hero}${stats}
 <div class=sx-grid><div class=sx-col><h3>Upcoming launches <span class=meta>— Launch Library 2</span></h3>${tbl(up.filter(x=>x!==n).slice(0,12))}</div>
 <div class=sx-col><h3>Recent launches <span class=meta>— this year</span></h3>${tbl(pv.slice(0,10),1)}</div>${star}
 <div class=sx-col><h3>Related alerts <span class=meta>— SpaceX/Starlink items the scanner has (read-only, last 14 days)</span></h3><ul class=sx-ul>${alerts}</ul></div></div>
 <div class=sx-col><h3>News <span class=meta>— Spaceflight News API + Google News, newest first, headlines verbatim</span></h3><ul class="sx-ul sx-news">${news||"<li class=meta>No articles.</li>"}</ul></div>
 <div class=sx-src>Links: ${d.links.map(l=>`<a href="${U(l[1])}" target=_blank rel=noopener>${E(l[0])}</a>`).join(" · ")}</div>`;
 cd();
 app.querySelectorAll("[data-goto]").forEach(a=>a.onclick=e=>{e.preventDefault();document.querySelector('.tabs button[data-tab="threat"]').click();setTimeout(()=>{const el=document.querySelector(`[data-cid="${CSS.escape(a.dataset.goto)}"]`);if(el){el.scrollIntoView({block:"center"});el.style.outline="2px solid var(--hi)";setTimeout(()=>el.style.outline="",2500)}},300)})}
async function load(force){if(S.busy)return;S.busy=true;const b=M.querySelector("#sx_ref");b&&(b.disabled=true);
 try{const r=await fetch("api/spacex"+(force?"?force=1":""),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);S.d=j;S.t=Date.now();render()}
 catch(e){if(!S.d)app.innerHTML=`<div class=meta>SpaceX data unavailable: ${E(e.message||e)}</div>`}finally{S.busy=false;b&&(b.disabled=false)}}
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="spacex")setTimeout(()=>{if(!S.d||Date.now()-S.t>300000)load()},0)});
setInterval(()=>{if(M.style.display!="none"&&!document.hidden)load()},600000);
M.querySelector("#sx_ref").onclick=()=>load(true);
})();
