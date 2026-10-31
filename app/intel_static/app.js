// ---- 🗂 Intel Streams tab (served by intel_streams.py): Research, Leaks, Patents, M&A, Markets. Informational only; times in ET. ----
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):"#";const TZ="America/New_York";
const etT=t=>{if(!t)return"—";const d=new Date(t);if(isNaN(d))return E(t);const dateOnly=/T00:00:00Z$/.test(t);return dateOnly?d.toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric",year:"numeric"}):d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const ago=t=>{const m=Math.round((Date.now()-Date.parse(t))/60000);return isNaN(m)?"":m<60?m+" min ago":m<1440?Math.round(m/60)+" h ago":Math.round(m/1440)+" d ago"};
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="intel"]');if(!tb){tb=document.createElement("button");tb.dataset.tab="intel";tb.textContent="🗂 Intel Streams";nav.appendChild(tb)}
const anchor=nav.querySelector('button[data-tab="finance"]')||nav.querySelector('button[data-tab="spacex"]');if(anchor)anchor.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.intel="intel";HASHTAB.intel="intel"}}catch(_){}
let M=document.getElementById("tab-intel");
if(!M){M=document.createElement("main");M.id="tab-intel";M.dataset.addon="intel";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn"><h2><span>🗂</span> Intel Streams <span class="meta">— new research, leak releases, patents, mergers and market shocks, each with a checked source link</span><button type="button" class="tab-ref" id="is_ref" title="Reload">⟳ Refresh</button></h2><div id="is_app"><div class="meta">Loading Intel Streams…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
const app=M.querySelector("#is_app");const S={d:null,t:0,busy:false,f:"all",q:""};
const ICON={research:"🔬",leaks:"📂",patents:"📜",mna:"🤝",markets:"📉"};
const hashF=()=>{const m=location.hash.match(/^#intel(?:[-/](research|leaks|patents|mna|markets))?$/);return m?(m[1]||"all"):null};
if(hashF()){S.f=hashF();setTimeout(()=>tb.click(),350)}
function item(x){return `<li class="is-it is-${E(x.stream)}"><div class="is-top"><span class="is-b is-b-${E(x.stream)}">${ICON[x.stream]||""} ${E(x.label)}</span>${(x.tags||[]).filter(t=>t&&t!=x.label).slice(0,3).map(t=>`<span class="is-tag${t=="NEW"?" is-new":""}">${E(t)}</span>`).join("")}</div>
 <a class="is-t" href="${U(x.url)}" target="_blank" rel="noopener">${E(x.title)}</a>
 <div class="meta">${E(x.source)} · ${etT(x.time)}${x.time&&!/T00:00:00Z$/.test(x.time)?` (${ago(x.time)})`:""}${x.alt?` · <a href="${U(x.alt)}" target="_blank" rel="noopener">Espacenet</a>`:""} · <span title="${E(x.verified)}">✓ link checked</span></div>
 ${x.summary?`<div class="is-sum">${E(x.summary)}</div>`:""}</li>`}
function render(){const d=S.d;if(!d)return;const st=d.streams||{};
 const items=(d.items||[]).filter(x=>(S.f=="all"||x.stream==S.f)&&(!S.q||(x.title+" "+x.summary+" "+x.source).toLowerCase().includes(S.q)));
 const chips=[["all","All",(d.items||[]).length]].concat(Object.entries(st).map(([k,v])=>[k,(ICON[k]||"")+" "+v.label,v.items])).map(([k,l,n])=>`<button type="button" class="is-chip${S.f==k?" on":""}" data-f="${k}">${E(l)} <b>${n}</b></button>`).join("");
 const wl=d.wikileaks||{};const wlL=wl.latest;
 const wlBox=(S.f=="all"||S.f=="leaks")&&wlL?`<div class="is-wl">📂 <b>WikiLeaks:</b> ${(st.leaks||{}).items?`<b class="is-new">new release flagged below</b>`:`no new release since the last one on record`} — latest listed: <a href="${U(wlL.url)}" target="_blank" rel="noopener">${E(wlL.title)}</a> (${etT(wlL.date)})${wl.latest_news?`; latest statement: <a href="${U(wl.latest_news.url)}" target="_blank" rel="noopener">${E(wl.latest_news.title)}</a> (${etT(wl.latest_news.date)})`:""}. ${wl.checked?`Checked ${etT(wl.checked.ts)}.`:""}</div>`:"";
 const epo=d.epo&&(S.f=="all"||S.f=="patents")?`<div class="meta is-epo">EPO week of ${E(String(d.epo.week).replace(/(\d{4})(\d\d)(\d\d)/,"$1-$2-$3"))}: ${Number(d.epo.processed).toLocaleString()} of ${Number(d.epo.total).toLocaleString()} European publications screened for the applicant watch list.</div>`:"";
 const srcs=Object.entries(st).map(([k,v])=>`<details class="is-src"><summary>${ICON[k]||""} ${E(v.label)}: ${v.sources.length} sources · ${v.new_24h} new in 24 h</summary><ul>${v.sources.map(s=>`<li><a href="${U(s.url)}" target="_blank" rel="noopener">${E(s.name)}</a> <span class="meta">· start rating ${s.rating}/10 · checked ${etT(s.checked)}${s.ok?"":` · <span class="is-err">issue: ${E(s.error||"failed")}</span>`}</span></li>`).join("")}</ul></details>`).join("");
 const th=d.thresholds||{};
 app.innerHTML=`<div class="is-note">${E(d.note)} ${d.updated?`Updated ${etT(d.updated)}.`:""} <a href="api/intel/feed.xml" target="_blank" rel="noopener">RSS feed</a> · <a href="/sources" target="_blank" rel="noopener">Sources &amp; ratings</a></div>
 <div class="is-chips">${chips}<input type="search" id="is_q" placeholder="Filter…" value="${E(S.q)}" aria-label="Filter items"></div>${wlBox}${epo}
 <ul class="is-list">${items.map(item).join("")||`<li class="meta">No ${S.f=="all"?"":E((st[S.f]||{}).label||"")+" "}items in the last ${d.days} days${S.f=="leaks"?" — WikiLeaks has published no new release":""}.</li>`}</ul>
 <div class="is-foot"><div class="meta">Market thresholds: stock indexes ${E(th.indexes)}, currencies ${E(th.fx)}, oil ${E(th.oil)}, natural gas ${E(th["natural gas"])}, gold ${E(th.gold)}, copper ${E(th.copper)}, Bitcoin ${E(th.bitcoin)}, VIX ${E(th.vix)}, U.S. 10-year ${E(th.us10y)}. M&amp;A news: ${E(th.mna_news)}; SEC takeover filings (tender offers, merger proxies, merger registrations) are all listed.</div>${srcs}</div>`;
 app.querySelectorAll(".is-chip").forEach(b=>b.onclick=()=>{S.f=b.dataset.f;try{history.replaceState(null,"","#intel"+(S.f=="all"?"":"-"+S.f))}catch(_){}render()});
 const q=app.querySelector("#is_q");q.oninput=()=>{S.q=q.value.trim().toLowerCase();const p=q.selectionStart;render();const n=app.querySelector("#is_q");n.focus();try{n.setSelectionRange(p,p)}catch(_){}}}
async function load(){if(S.busy)return;S.busy=true;const b=M.querySelector("#is_ref");b&&(b.disabled=true);
 try{const r=await fetch("api/intel?days=7",{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);S.d=j;S.t=Date.now();render()}
 catch(e){if(!S.d)app.innerHTML=`<div class=meta>Intel Streams unavailable: ${E(e.message||e)}</div>`}finally{S.busy=false;b&&(b.disabled=false)}}
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="intel")setTimeout(()=>{if(!S.d||Date.now()-S.t>300000)load()},0)});
setInterval(()=>{if(M.style.display!="none"&&!document.hidden)load()},600000);
M.querySelector("#is_ref").onclick=()=>load();
})();
