// ---- Watch tabs (tabfeeds.py): 🤖 AI Threats (#ai, aithreats.py) and ⚡ U.S. Energy Grid (#grid, gridwatch.py; status map in gridstatus.py). ----
// Listed in the main nav (Monitor group, right after Network Status) since t233; deep links #ai, #grid and #grid/state/XX.
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>typeof safeUrl=="function"?safeUrl(u):(/^https?:\/\//i.test(u||"")?u:"#");
const ET=t=>{if(!t)return"time n/a";const d=new Date(t);if(isNaN(d))return"time n/a";
 return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)};
const LV=s=>typeof lv=="function"?lv(s):(s>=60?"h":s>=35?"m":"l");
const RC=r=>r>=7?"h":r>=5?"m":r>=3?"l2":"l";
const TABS={
 ai:{api:"api/ai",icon:"🤖",title:"AI Threats",sub:"AI hacking, rogue bots and agents, AI-enabled cyber attacks, deepfake fraud, model jailbreaks and AI supply-chain compromises",
  help:"Every alert the blackout.network scanner has stored (news, agencies and the Telegram, Discord, Mastodon and Bluesky analyst channels it reads) that mentions an AI system together with a threat (hacking, fraud, deepfakes, jailbreaks, rogue agents, supply-chain compromise, AI weapons). Ranks 0–10 and scores 0–100 are the scanner's own, exactly as on The Wire. Extra feeds (AI Incident Database, The Hacker News) are listed as unscored unless the same link is already a scored scanner alert."},
 grid:{api:"api/grid",icon:"⚡",title:"U.S. Energy Grid",sub:"physical and cyber attacks on U.S. power infrastructure, energy-sector ICS vulnerabilities, blackout risk and grid-stressing geomagnetic storms",
  help:"Scanner alerts that name the power grid (substations, transmission, outages, utilities, grid emergencies, ICS/SCADA) with a U.S. anchor: a U.S. place, grid operator, utility or agency, or U.S. coordinates. Space weather counts only at NOAA G3 or stronger. Ranks 0–10 and scores 0–100 are the scanner's own. Extra official feeds (CISA ICS advisories for the Energy sector, NOAA SWPC G3+ alerts, ERCOT grid conditions) are unscored unless the same link is already a scored scanner alert."}};
const ST={};
const nav=document.querySelector(".tabs");
const NAVB={grid:["⚡ Energy Grid","U.S. power grid status, outages and threats"],ai:["🤖 AI Threats","AI hacking, rogue bots and agents, AI-enabled cyber attacks"]};
function btn(k){if(!nav)return null;let b=nav.querySelector(`button[data-tab="${k}"]`);if(!b){b=document.createElement("button");b.dataset.tab=k;b.textContent=NAVB[k][0];b.title=NAVB[k][1];nav.appendChild(b)}return b}
function placeNav(){const g=btn("grid"),a=btn("ai");if(!g||!a)return;const anc=nav.querySelector('button[data-tab="net"]');if(anc){if(anc.nextElementSibling!==g)anc.insertAdjacentElement("afterend",g);if(g.nextElementSibling!==a)g.insertAdjacentElement("afterend",a)}}
try{if(typeof TABHASH=="object"){TABHASH.grid="grid";HASHTAB.grid="grid";TABHASH.ai="ai";HASHTAB.ai="ai"}}catch(_){}
function hashTab(){const m=location.hash.match(/^#(ai|grid)(?:[\/-].*)?$/);return m?m[1]:null}
function mk(k){const T=TABS[k];let M=document.getElementById("tab-"+k);if(M)return M;
 M=document.createElement("main");M.id="tab-"+k;M.dataset.addon=k;M.className="tfx";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn"><h2><span>${T.icon}</span> ${E(T.title)} <span class="meta">— ${E(T.sub)}</span><button type="button" class="tab-ref" data-r="1" title="Reload this tab">⟳ Refresh</button></h2>
 <div class="tfx-help meta">${E(T.help)}</div>
 <div class="tfx-sum" data-el="sum">Loading…</div>
 <div class="tfx-bar"><span class="tfx-lbl">Rank</span><div class="tfx-seg" data-el="rank"></div></div>
 <div class="tfx-bar"><span class="tfx-lbl">Type</span><div class="tfx-seg" data-el="kind"></div></div>
 <div class="tfx-bar"><span class="tfx-lbl">From</span><div class="tfx-seg" data-el="origin"></div><span class="tfx-lbl">Sort</span><div class="tfx-seg" data-el="sort"></div>
  <input type="search" data-el="q" placeholder="Filter…" aria-label="Filter items"><span class="meta" data-el="msg"></span></div>
 <div data-el="list" class="tfx-list"></div><div data-el="more" class="tfx-more"></div>
 <details class="tfx-feeds"><summary>Extra feeds (live-checked)</summary><div data-el="feeds" class="meta">…</div></details></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M);
 ST[k]={items:[],rank:"",kind:"",origin:"",sort:"new",q:"",busy:false,done:false,d:null};
 const S=ST[k],q=s=>M.querySelector(`[data-el="${s}"]`);
 M.addEventListener("click",e=>{const b=e.target.closest("button[data-f]");if(b){S[b.dataset.f]=b.dataset.v;reset(k);return}
  if(e.target.closest("button[data-r]"))reset(k);if(e.target.closest("button[data-more]"))more(k)});
 let tq;q("q").addEventListener("input",e=>{clearTimeout(tq);tq=setTimeout(()=>{S.q=e.target.value.trim();reset(k)},300)});
 const h2=M.querySelector("h2");if(h2&&typeof hwAttach=="function")try{hwAttach(h2,k+"tab",()=>T.help)}catch(_){}
 return M}
function badge(x){if(x.rank==null)return `<span class="tfx-rk un" title="Not scored by the scanner">unscored</span>`;return `<span class="tfx-rk ${RC(x.rank)}" title="rank ${x.rank} of 10 (scanner)">rank ${x.rank}/10</span>`}
function status(x){if(x.origin=="feed"&&x.rank==null)return x.official?`<span class="tfx-off" title="Official agency feed; not scored by the scanner">official feed</span>`:`<span class="unc">unconfirmed · single source</span>`;
 return x.list=="wire"?"":x.list=="watchlist"?`<span class="wl">Watchlist</span><span class="unc">unconfirmed</span>`:`<span class="unc" title="Low-signal item the scanner stores but keeps off The Wire and the Watchlist">off the Wire · unconfirmed</span>`}
function row(k,x){const kinds=(ST[k].d||{}).kinds||{};const t=x.score!=null?LV(x.score):"l";
 const fam=x.n_families&&x.origin=="scanner"?` · ${x.n_items} report(s) from ${x.n_families} source famil${x.n_families==1?"y":"ies"}`:"";
 const ev=x.event_time&&x.event_time!=x.first_seen?` · event ${E(ET(x.event_time))}`:"";
 const links=(x.links||[]).filter(l=>l&&l.url).map(l=>`<a href="${E(U(l.url))}" target="_blank" rel="noopener noreferrer">${E(l.source||"source")}</a>`).join(" · ")||"no source link";
 return `<div class="tfx-row ${x.rank!=null&&x.rank>=7?"h":t}">${x.score!=null?`<span class="sc ${t}" title="score 0–100">${E(x.score)}</span>`:""}${badge(x)}<span class="tfx-k">${E(kinds[x.kind]||x.kind)}</span><b>${E(x.title)}</b> ${status(x)}
<div class="meta">${E(x.category||"other")}${x.location?` · ${E(x.location)}`:""} · seen ${E(ET(x.first_seen))}${ev}${fam}${x.origin=="feed"?` · via ${E((x.sources||[])[0]||x.feed)}`:x.sources&&x.sources.length?` · ${E(x.sources.slice(0,3).join(", "))}`:""}</div>
<div class="meta">Verify: ${links}</div>
${x.match&&x.match.replace(/…/g,"").trim()!=String(x.title||"").trim()?`<div class="tfx-m" title="Text that matched this tab's filter">“${E(x.match)}”</div>`:x.brief&&x.origin=="feed"?`<div class="tfx-m">${E(String(x.brief).slice(0,280))}</div>`:""}
${x.brief&&x.origin=="scanner"?`<div class="brief">${E(x.brief)}</div>`:""}</div>`}
function seg(k,el,f,opts){const S=ST[k];document.getElementById("tab-"+k).querySelector(`[data-el="${el}"]`).innerHTML=opts.map(([v,l,n])=>`<button type="button" data-f="${f}" data-v="${E(v)}" class="${v==S[f]?"on":""}">${E(l)}${n!=null?` <span class="meta">${Number(n).toLocaleString()}</span>`:""}</button>`).join("")}
function paint(k){const S=ST[k],d=S.d||{},s=d.summary||{},br=s.by_rank||{},bk=s.by_kind||{},M=document.getElementById("tab-"+k),q=x=>M.querySelector(`[data-el="${x}"]`);
 const hi=Object.entries(br).filter(([r])=>r!="unscored"&&+r>=7).reduce((a,[,n])=>a+n,0);
 q("sum").innerHTML=`<b>${(s.total||0).toLocaleString()}</b> items · <b>${hi}</b> ranked 7+ · ${(s.by_list||{}).wire||0} on The Wire, ${((s.by_list||{}).watchlist||0)+((s.by_list||{}).suppressed||0)} unconfirmed scanner items, ${br.unscored||0} unscored feed items${s.oldest?` <span class="meta">· ${E(ET(s.oldest))} – ${E(ET(s.newest))}</span>`:""}`;
 seg(k,"rank","rank",[["","All",s.total],["7+","7+",hi],...[10,9,8,7,6,5,4,3,2,1,0].filter(r=>br[r]).map(r=>[String(r),String(r),br[r]]),...(br.unscored?[["unscored","unscored",br.unscored]]:[])]);
 seg(k,"kind","kind",[["","All",null],...Object.entries(d.kinds||{}).filter(([v])=>bk[v]).map(([v,l])=>[v,l,bk[v]])]);
 seg(k,"origin","origin",[["","All",null],["scanner","Scanner alerts",null],["feed","Extra feeds",null]]);
 seg(k,"sort","sort",[["new","Newest",null],["rank","Highest rank",null]]);
 q("list").innerHTML=S.items.map(x=>row(k,x)).join("")||'<div class="meta">Nothing matches yet. The scanner and the extra feeds are checked continuously; matching items appear here automatically.</div>';
 q("more").innerHTML=S.done?`<span class="meta">Showing all ${S.items.length.toLocaleString()} of ${(d.matching||0).toLocaleString()}</span>`:`<button type="button" data-more="1">Load more (${S.items.length} of ${(d.matching||0).toLocaleString()} shown)</button>`;
 q("feeds").innerHTML=(d.feeds||[]).map(f=>`<div>${f.ok?"✅":"⚠️"} <a href="${E(U(f.url))}" target="_blank" rel="noopener noreferrer">${E(f.label)}</a> · ${f.ok?`${f.kept} kept`:"failed: "+E(f.error||"")} · checked ${E(ET(f.last_checked))}${f.note?` · ${E(f.note)}`:""}</div>`).join("")||"No extra-feed data synced yet."}
async function more(k){const S=ST[k];if(S.busy||S.done)return;S.busy=true;const msg=document.getElementById("tab-"+k).querySelector('[data-el="msg"]');msg.textContent="loading…";
 try{const p=new URLSearchParams({offset:S.items.length,limit:60,sort:S.sort});["rank","kind","origin","q"].forEach(f=>{if(S[f])p.set(f,S[f])});
  const r=await fetch(TABS[k].api+"?"+p,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;
  S.d=j;S.items.push(...j.items);S.done=!j.items.length||S.items.length>=j.matching;msg.textContent="";paint(k)}
 catch(e){msg.textContent=TABS[k].title+" offline: "+e}finally{S.busy=false}}
function reset(k){const S=ST[k];S.items=[];S.done=false;more(k)}
function show(k){mk(k);const b=btn(k);if(b&&!b.classList.contains("on"))b.click();if(!ST[k].items.length&&!ST[k].busy)reset(k)}
function route(){const k=hashTab();if(k)show(k)}
mk("grid");mk("ai");placeNav();setTimeout(placeNav,600);
if(nav)nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(!b||!TABS[b.dataset.tab])return;const k=b.dataset.tab;if(!ST[k].items.length&&!ST[k].busy)reset(k)});
addEventListener("hashchange",route);if(hashTab())setTimeout(route,400);
setInterval(()=>{const k=hashTab();if(k&&document.getElementById("tab-"+k)&&document.getElementById("tab-"+k).style.display!="none"&&!ST[k].busy&&ST[k].items.length<=60)reset(k)},300000);
})();
