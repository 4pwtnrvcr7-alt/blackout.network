// ---- 🏛 Government tab (served by government.py; data: government.db built daily on the box by government_collect.py) ----
// Composite health index (blackout.network composite index, not an official rating) + lazy-loaded org chart with profiles.
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?u:"#";
const TZ="America/New_York";
const ET=t=>{if(!t)return"—";const d=new Date(t);return isNaN(d)?E(t):d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const API="api/government";
const ICON=`<svg class="gv-ic" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 22h18"/><path d="M6 18v-7"/><path d="M10 18v-7"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M12 2 20 7H4z"/><path d="M4 18h16"/></svg>`;
// ---- nav button (Reference group, after Maps) + panel + deep link #government
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="gov"]');
if(!tb){tb=document.createElement("button");tb.type="button";tb.dataset.tab="gov";tb.textContent="🏛 Government";tb.title="U.S. government: health index and org chart";nav.appendChild(tb)}
const place=()=>{const a=nav.querySelector('button[data-tab="maps"]')||nav.querySelector('button[data-tab="res"]');if(a&&a.nextElementSibling!==tb)a.insertAdjacentElement("afterend",tb)};place();setTimeout(place,450);
try{if(typeof TABHASH=="object"){TABHASH.gov="government";HASHTAB.government="gov"}}catch(_){}
let M=document.getElementById("tab-gov");
if(!M){M=document.createElement("main");M.id="tab-gov";M.dataset.addon="gov";M.className="gv";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn"><h2>${ICON} Government <span class="meta">— how the U.S. government is doing by branch and agency, and who holds office from the President to big-city mayors</span><button type="button" class="tab-ref" data-gv="reload" title="Reload this tab">⟳ Refresh</button></h2>
 <div class="gv-fresh meta" data-el="fresh">Loading…</div>
 <div class="gv-score" data-el="score"></div>
 <details class="gv-method"><summary>How the index is calculated</summary><div data-el="method"></div></details>
 <details class="gv-all" data-el="allwrap"><summary>Every scored agency, with each component</summary><div data-el="all" class="meta">Open to load…</div></details>
 </section>
 <section class="pn gv-chart"><h2>Org chart <span class="meta">— expand a branch, or search by name, office, state or city</span></h2>
  <div class="gv-tools" role="search">
   <div class="gv-sbox"><input type="search" data-el="q" placeholder="Search a name, office, state or city…" aria-label="Search the org chart" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="gv_res" aria-autocomplete="list">
    <ul id="gv_res" class="gv-res" role="listbox" data-el="res" hidden></ul></div>
   <label>Branch <select data-el="branch" aria-label="Filter by branch"><option value="">All</option><option value="executive">Executive</option><option value="legislative">Legislative</option><option value="judicial">Judicial</option><option value="state">States</option><option value="local">Local (mayors)</option></select></label>
   <label>State <select data-el="state" aria-label="Filter by state"><option value="">All</option></select></label>
  </div>
  <div class="gv-quick" data-el="quick" hidden></div>
  <nav class="gv-crumbs" aria-label="Breadcrumb" data-el="crumbs"></nav>
  <div class="gv-tree" role="tree" aria-label="U.S. government org chart" data-el="tree"></div>
  <div class="gv-cov meta" data-el="cov"></div>
 </section>
 <section class="pn gv-src"><h2>Data sources <span class="meta">— every input is free, keyless and public; checked daily</span></h2><div data-el="srcs" class="meta"></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
const q=s=>M.querySelector(`[data-el="${s}"]`);
const S={d:null,full:null,busy:false,loaded:{},open:new Set()};
const score=v=>v==null?`<span class="gv-nd">no data</span>`:`<b class="gv-n ${v>=75?"g":v>=55?"m":"b"}">${Number(v).toFixed(1)}</b>`;
const bar=v=>v==null?"":`<span class="gv-bar" aria-hidden="true"><i style="width:${Math.max(2,Math.min(100,v))}%" class="${v>=75?"g":v>=55?"m":"b"}"></i></span>`;
const srcLink=k=>{const s=(S.d&&S.d.sources||{})[k];return s?`<a href="${E(U(s.url))}" target="_blank" rel="noopener noreferrer">${E(s.label.split(":")[0].split(" (")[0])}</a>`:""};
const CN={gao_hr:"GAO High-Risk List areas",ig_recs:"Inspector General open-recommendation age",data_quality:"USAspending reporting checks",ig_vacancy:"Inspector General vacancy",budget_exec:"Budget execution (obligated ÷ available)",
 laws:"Laws enacted (pace)",house_attendance:"House roll-call participation",senate_attendance:"Senate roll-call participation",appropriations_on_time:"Appropriations on time",vacancy_rate:"Judgeship vacancy rate",emergencies:"Judicial emergencies",nominees:"Vacancies with a nominee",caseload:"Caseload"};
function comps(o,weights){return Object.entries(o||{}).map(([k,c])=>{const w=weights?weights[k]:c.weight;
 return `<li><span class="gv-cn">${E(CN[k]||k)}</span> <span class="meta">weight ${w||0}%</span> ${score(c.score)} ${bar(c.score)}<div class="meta">${E(c.value||"")}${c.source?` · ${srcLink(c.source)}`:""}${c.date?` · data ${E(/^\d{4}-\d\d-\d\dT/.test(c.date)?ET(c.date):c.date)}`:""}</div></li>`}).join("")}
function paint(){const d=S.d;if(!d)return;const b=d.branches||{};
 q("fresh").innerHTML=`<span class="gv-tag">blackout.network composite index — not an official rating</span> Data refreshed ${ET(d.updated)} · scores computed ${ET(d.computed)}. Scores institutions only, never parties or people.`;
 const exT=(d.top||[]).map(a=>`<li><button type="button" class="gv-link" data-agency="${E(a.code)}">${E(a.name)}</button> ${score(a.score)}</li>`).join("");
 const exB=(d.bottom||[]).map(a=>`<li><button type="button" class="gv-link" data-agency="${E(a.code)}">${E(a.name)}</button> ${score(a.score)}</li>`).join("");
 q("score").innerHTML=`<div class="gv-ovr"><div class="gv-big">${score(d.overall)}<span class="meta">/ 100</span></div><div><b>Overall U.S. government index</b><div class="meta">Equal-weight average of the three federal branches below.</div></div></div>
 <div class="gv-br">
  <div class="gv-card"><h3>Executive ${score(b.executive)}</h3>${bar(b.executive)}<div class="meta">Average of ${d.n_scored||0} scored agencies (of ${d.n_agencies||0} with ≥ $0.5B budget authority; an agency needs ${d.min_components||4}+ of 5 components to be scored).</div>
   <div class="gv-tb"><div><b>Highest</b><ol>${exT}</ol></div><div><b>Lowest</b><ol>${exB}</ol></div></div></div>
  <div class="gv-card"><h3>Legislative ${score(b.legislative)}</h3>${bar(b.legislative)}<ul class="gv-comp">${comps(d.legislative)}</ul></div>
  <div class="gv-card"><h3>Judicial ${score(b.judicial)}</h3>${bar(b.judicial)}<ul class="gv-comp">${comps(d.judicial)}</ul></div>
 </div>`;
 const w=d.weights||{};
 q("method").innerHTML=`<p>Each component is converted to a 0–100 score (higher = healthier), using public data only. A component a source does not publish is shown as <b>no data</b> and left out: the remaining weights are re-scaled and the number of components used is shown. Nothing is imputed.</p>
 <p><b>Executive agencies</b> (weights): GAO High-Risk areas specific to the agency ${w.gao_hr}% (100 − 20 per area; government-wide areas are not charged to one agency) · Inspector General open recommendations ${w.ig_recs}% (100 × (1 − average of the share open over 1 year and the share open over 5 years)) · USAspending reporting checks ${w.data_quality}% (certified year-end submission, no accounts missing from GTAS, $0 File A vs GTAS obligation difference: 1/3 each) · Inspector General vacancy ${w.ig_vacancy}% (100 if filled, −1 per 10 days vacant) · budget execution ${w.budget_exec}% (share of the fiscal year's budgetary resources obligated; unobligated funds can be legitimate multi-year money, so it carries a low weight). The Executive score is the plain average of the scored executive-branch agencies (legislative-branch agencies such as GAO are listed but not averaged in). The GAO list is read from the Internet Archive copy of gao.gov/high-risk-list because gao.gov refuses automated requests; its capture date is shown under Data sources.</p>
 <p><b>Legislative</b>: public laws enacted, as the full-term pace of the current Congress against the median of the six before it (50%), and House roll-call participation (50%). Senate attendance and on-time appropriations: no keyless structured source, shown as no data.</p>
 <p><b>Judicial</b>: Article III judgeship vacancy rate (40%; 0% → 100, 10%+ → 0), share of vacancies that are judicial emergencies (30%), share of vacancies with a nominee pending (30%).</p>
 <p><b>Overall</b> = average of the three branch scores. Senate-confirmed leadership vacancies (Partnership for Public Service tracker) and OPM workforce data are not used: neither is published in a machine-readable keyless form. The thresholds are blackout.network's own choices, published here so anyone can recompute them.</p>`;
 const sel=q("state");if(sel.options.length<3)(d.states||[]).forEach(s=>sel.insertAdjacentHTML("beforeend",`<option value="${E(s.state)}">${E(s.name)}</option>`));
 const c=d.counts||{},cv=d.coverage||{};
 const pc=(a,b)=>b?Math.round(100*a/b)+"%":"—";
 const ppl=Object.values(cv).reduce((a,x)=>a+(x.p||0),0),ph=Object.values(cv).reduce((a,x)=>a+(x.ph||0),0);
 q("cov").innerHTML=`<b>Coverage:</b> ${(c.federal_agencies||0).toLocaleString()} federal agencies & offices, ${c.federal_courts||0} federal courts, ${c.cabinet||0} Cabinet members, ${c.senators||0} senators, ${c.representatives||0} House members & delegates, ${c.justices||0} Supreme Court justices, ${c.governors||0} governors, ${(c.state_legislators||0).toLocaleString()} state legislators, ${(c.mayors||0).toLocaleString()} mayors (cities 30,000+).
  Official photos: ${pc(ph,ppl)} of ${ppl.toLocaleString()} people (the rest show a labelled placeholder). Local coverage is limited to mayors: there is no clean keyless nationwide dataset for county, council or school-board officials.`+
  Object.entries(cv).map(([k,x])=>x.p?`<div>${E(k)}: ${x.p.toLocaleString()} people · photo ${pc(x.ph,x.p)} · phone ${pc(x.phn,x.p)} · address ${pc(x.ad,x.p)} · published email ${pc(x.em,x.p)} · contact form ${pc(x.cf,x.p)}</div>`:"").join("");
 q("srcs").innerHTML=Object.values(d.sources||{}).map(s=>`<div>${s.ok?"✓":"⚠"} <a href="${E(U(s.url))}" target="_blank" rel="noopener noreferrer">${E(s.label)}</a> · ${E(s.license||"")}${s.count!=null?` · ${Number(s.count).toLocaleString()} records`:""}${s.as_of?` · as of ${E(s.as_of)}`:""} · checked ${ET(s.fetched)}${s.note?` · ${E(s.note)}`:""}${s.error?` · <span class="gv-warn">${E(s.error)}</span>`:""}</div>`).join("")}
async function load(force){if(S.busy)return;S.busy=true;try{const r=await fetch(API,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;S.d=j;paint();if(force||!S.loaded.us)await openNode("us",q("tree"),0,true)}
 catch(e){q("fresh").textContent="Government data unavailable: "+e}finally{S.busy=false}}
async function loadAll(){if(S.full)return;try{const r=await fetch(API+"/scores",{cache:"no-store"});S.full=await r.json();const ag=(S.full.executive||{}).agencies||[];const w=(S.full.executive||{}).weights;
 q("all").innerHTML=`<div class="meta">Sorted by score. Agencies with fewer than ${(S.full.executive||{}).min_components||3} components show “no data” instead of a score.</div>`+ag.map(a=>`<details class="gv-ag" id="gv_ag_${E(a.code)}"><summary>${score(a.score)} ${bar(a.score)} <b>${E(a.name)}</b> <span class="meta">${a.branch&&a.branch!="executive"?`${E(a.branch)}-branch agency, not in the Executive average · `:""}${a.n_components}/5 components${a.missing&&a.missing.length?` · no data: ${a.missing.map(k=>E(CN[k]||k)).join(", ")}`:""}</span>${a.node?` <button type="button" class="gv-link" data-goto="${E(a.node)}">show in org chart</button>`:""}</summary><ul class="gv-comp">${comps(a.components,w)}</ul></details>`).join("")}catch(e){q("all").textContent="Could not load: "+e}}
q("allwrap").addEventListener("toggle",e=>{if(e.target.open)loadAll()});
// ---- placeholders (initials, site line style); never a likeness
function initials(n){const p=String(n||"?").replace(/\b(Jr|Sr|II|III|IV)\.?\b/g,"").split(/[\s.]+/).filter(x=>/^[A-Za-zÀ-ž]/.test(x));return ((p[0]||"?")[0]+(p.length>1?p[p.length-1][0]:"")).toUpperCase()}
function ph(n,why){return `<figure class="gv-ph"><svg viewBox="0 0 80 96" role="img" aria-label="Placeholder: ${E(why)}"><rect x="1" y="1" width="78" height="94" rx="8" fill="#0f1317" stroke="#2f3742"/><circle cx="40" cy="36" r="17" fill="none" stroke="#8b95a3" stroke-width="2.4"/><path d="M12 92c3-19 14-28 28-28s25 9 28 28" fill="none" stroke="#8b95a3" stroke-width="2.4" stroke-linecap="round"/><text x="40" y="42" text-anchor="middle" font-size="15" font-weight="700" fill="#e6e9ee" font-family="system-ui,sans-serif">${E(initials(n))}</text></svg><figcaption>Placeholder, ${E(why)}</figcaption></figure>`}
function photo(n,big){if(n.kind!="person")return `<span class="gv-kic" aria-hidden="true">${n.kind=="court"?"⚖":n.kind=="state"?"◈":ICON}</span>`;
 if(n.has_photo)return `<img class="gv-img${big?" big":""}" loading="lazy" decoding="async" src="${API}/img?id=${encodeURIComponent(n.id)}" alt="Official photo of ${E(n.name)}" data-name="${E(n.name)}">`;
 return ph(n.name,"official image not found")}
M.addEventListener("error",e=>{const t=e.target;if(t.tagName=="IMG"&&t.classList.contains("gv-img")){t.outerHTML=ph(t.dataset.name,"official image could not be loaded")}},true);
// ---- tree
function rowHTML(n,depth){const kids=n.n_children>0;const lab=n.kind=="person"?`${E(n.name)}<span class="meta"> · ${E(n.title||"")}${n.party?` · ${E(n.party)}`:""}</span>`:`${E(n.name)}${n.title&&n.kind=="agency"?` <span class="meta">${E(n.title)}</span>`:""}${kids?` <span class="gv-cnt">${n.n_children.toLocaleString()}</span>`:""}`;
 return `<div class="gv-node k-${E(n.kind)}" role="treeitem" aria-level="${depth+1}" ${kids?`aria-expanded="false"`:""} data-id="${E(n.id)}" id="gvn_${E(n.id).replace(/[^\w-]/g,"_")}">
 <div class="gv-row">${kids?`<button type="button" class="gv-tg" data-tg="${E(n.id)}" aria-label="Expand ${E(n.name)}">▸</button>`:`<span class="gv-tg sp"></span>`}
 ${n.kind=="person"?`<span class="gv-th">${photo(n)}</span>`:""}<button type="button" class="gv-nm" data-pf="${E(n.id)}">${lab}</button></div><div class="gv-kids" role="group" hidden></div></div>`}
async function fetchNode(id,off){const p=new URLSearchParams({id,offset:off||0,limit:60});const st=q("state").value;if(st&&/^(leg:senate|leg:house|jud:district|states|local)$/.test(id))p.set("state",st);
 const r=await fetch(API+"/node?"+p,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;return j}
async function openNode(id,box,depth,root){let j;try{j=await fetchNode(id,0)}catch(e){box.innerHTML=`<div class="meta">Could not load: ${E(e)}</div>`;return}
 S.loaded[id]=true;const br=q("branch").value;let kids=j.children;if(root&&br)kids=kids.filter(k=>k.branch==br);
 box.innerHTML=kids.map(k=>rowHTML(k,depth)).join("")+(j.total>j.offset+j.children.length&&!(root&&br)?moreBtn(id,j.children.length,j.total):"");box.hidden=false;if(!root)crumbs(j.crumbs);return j}
const moreBtn=(id,n,t)=>`<button type="button" class="gv-more" data-more="${E(id)}" data-off="${n}">Show more (${n.toLocaleString()} of ${t.toLocaleString()})</button>`;
async function more(b){const id=b.dataset.more,off=+b.dataset.off;b.disabled=true;b.textContent="Loading…";try{const j=await fetchNode(id,off);const depth=+(b.closest(".gv-node")?.getAttribute("aria-level")||0);
 b.insertAdjacentHTML("beforebegin",j.children.map(k=>rowHTML(k,depth)).join(""));const n=off+j.children.length;if(n<j.total)b.outerHTML=moreBtn(id,n,j.total);else b.remove()}catch(e){b.textContent="Retry: "+e;b.disabled=false}}
async function toggle(el,force){const kids=el.querySelector(":scope>.gv-kids"),tg=el.querySelector(":scope>.gv-row>.gv-tg");const open=el.getAttribute("aria-expanded")=="true";
 if(open&&force!==true){el.setAttribute("aria-expanded","false");kids.hidden=true;tg.textContent="▸";tg.setAttribute("aria-label","Expand");return}
 el.setAttribute("aria-expanded","true");tg.textContent="▾";tg.setAttribute("aria-label","Collapse");
 if(!kids.dataset.ok){kids.innerHTML='<div class="meta">Loading…</div>';kids.hidden=false;await openNode(el.dataset.id,kids,+el.getAttribute("aria-level"));kids.dataset.ok=1}else kids.hidden=false}
function crumbs(c){q("crumbs").innerHTML=(c||[]).map((x,i)=>i==c.length-1?`<span aria-current="page">${E(x.name)}</span>`:`<button type="button" class="gv-link" data-goto="${E(x.id)}">${E(x.name)}</button>`).join(" › ")}
async function goto(id,openProfile){let j;try{j=await fetchNode(id,0)}catch(e){return}
 const chain=j.crumbs.map(x=>x.id);let box=q("tree");if(!S.loaded.us)await openNode("us",box,0,true);
 if(q("branch").value){q("branch").value="";await openNode("us",q("tree"),0,true)}
 for(let i=1;i<chain.length;i++){const cid=chain[i];let el=[...q("tree").querySelectorAll(".gv-node")].find(x=>x.dataset.id==cid);
  if(!el){const par=[...q("tree").querySelectorAll(".gv-node")].find(x=>x.dataset.id==chain[i-1]);const kb=par?par.querySelector(":scope>.gv-kids"):q("tree");
   const r=await fetchNode(cid,0).catch(()=>null);if(!r)break;kb.insertAdjacentHTML("afterbegin",rowHTML({...r.node,n_children:r.total},i-1));el=kb.querySelector(`.gv-node[data-id="${CSS.escape(cid)}"]`)}
  if(i<chain.length-1&&el.getAttribute("aria-expanded")!="true")await toggle(el,true)}
 const el=[...q("tree").querySelectorAll(".gv-node")].find(x=>x.dataset.id==id);crumbs(j.crumbs);
 if(el){el.scrollIntoView({block:"center",behavior:"smooth"});el.classList.add("gv-hl");setTimeout(()=>el.classList.remove("gv-hl"),2600);const nb=el.querySelector(".gv-nm");nb&&nb.focus({preventScroll:true})}
 if(openProfile)profile(id)}
// ---- profile dialog
let dlg=null,lastFocus=null;
function closeP(){if(dlg){dlg.hidden=true;lastFocus&&lastFocus.focus()}}
async function profile(id){let j;try{j=await fetchNode(id,0)}catch(e){return}const n=j.node,x=n.extra||{};lastFocus=document.activeElement;
 if(!dlg){dlg=document.createElement("div");dlg.className="gv-dlg";dlg.hidden=true;dlg.innerHTML=`<div class="gv-dbox" role="dialog" aria-modal="true" aria-labelledby="gv_pt" tabindex="-1"></div>`;document.body.appendChild(dlg);
  dlg.addEventListener("click",e=>{if(e.target==dlg||e.target.closest("[data-x]"))closeP();const g=e.target.closest("[data-goto]");if(g){closeP();goto(g.dataset.goto)}});addEventListener("keydown",e=>{if(e.key=="Escape"&&dlg&&!dlg.hidden)closeP()})}
 const f=(l,v)=>`<div class="gv-f"><span>${l}</span><div>${v}</div></div>`;const np=v=>`<span class="gv-nd">${v||"not published by the source"}</span>`;
 const person=n.kind=="person";
 const email=n.email?`<a href="mailto:${E(n.email)}">${E(n.email)}</a>`:np(x.email_note||(n.contact_form?"no email published — use the contact form":"not published by the source"));
 const sc=n.score;
 dlg.querySelector(".gv-dbox").innerHTML=`<button type="button" class="gv-x" data-x="1" aria-label="Close profile">✕</button>
 <div class="gv-ph-wrap">${photo(n,true)}${person&&n.has_photo?`<div class="meta gv-cred">${E(n.photo_credit||"")}${n.photo_license?` · ${E(n.photo_license)}`:""}</div>`:""}</div>
 <div class="gv-pi"><h3 id="gv_pt">${E(n.name)}</h3><div class="meta">${E(n.title||"")}${n.party?` · ${E(n.party)}`:""}</div>
 <nav class="gv-crumbs meta" aria-label="Where this sits">${j.crumbs.slice(0,-1).map(c=>`<button type="button" class="gv-link" data-goto="${E(c.id)}">${E(c.name)}</button>`).join(" › ")}</nav>
 ${n.about?`<p>${E(n.about)}</p>`:""}
 ${person||n.phone||n.address||n.website?`${f("Email",email)}${f("Phone",n.phone?`<a href="tel:${E(n.phone.replace(/[^\d+]/g,""))}">${E(n.phone)}</a>`:np())}${f("Office address",n.address?E(n.address):np())}
 ${x.district_address&&x.district_address!=n.address?f("District office",E(x.district_address)+(x.district_phone?` · ${E(x.district_phone)}`:"")):""}
 ${f("Website",n.website?`<a href="${E(U(n.website))}" target="_blank" rel="noopener noreferrer">${E(n.website.replace(/^https?:\/\/(www\.)?/,"").slice(0,60))}</a>`:np())}
 ${n.contact_form?f("Contact form",`<a href="${E(U(n.contact_form))}" target="_blank" rel="noopener noreferrer">Official contact form</a>`):""}`:""}
 ${x.population?f("City population",Number(x.population).toLocaleString()+(x.next_election?` · next election ${E(x.next_election)}`:"")):""}
 ${x.agency?f("Leads",`<button type="button" class="gv-link" data-goto="${E(x.agency)}">open department in the org chart</button>`):""}
 ${sc?`<div class="gv-psc"><b>Agency index ${score(sc.score)}</b> <span class="meta">${sc.n_components}/5 components · blackout.network composite index, not an official rating</span><ul class="gv-comp">${comps(sc.components,S.d&&S.d.weights)}</ul></div>`:""}
 ${n.n_children?`<button type="button" class="gv-link" data-goto="${E(n.id)}">Show its ${n.n_children.toLocaleString()} sub-units in the org chart</button>`:""}
 <div class="meta gv-srcl">Source: ${n.source_url?`<a href="${E(U(n.source_url))}" target="_blank" rel="noopener noreferrer">${E(n.source_label||"source")}</a>`:E(n.source_label||"—")} · fetched ${ET(n.fetched)}. Public-record office contact only; nothing is guessed.</div></div>`;
 dlg.hidden=false;dlg.querySelector(".gv-dbox").focus()}
// ---- search
let tq,sel=-1,res=[];
async function search(){const v=q("q").value.trim(),br=q("branch").value,st=q("state").value;const L=q("res");
 if(v.length<2&&!st){L.hidden=true;q("q").setAttribute("aria-expanded","false");return}
 const p=new URLSearchParams({q:v,limit:25});if(br)p.set("branch",br);if(st)p.set("state",st);
 try{const r=await fetch(API+"/search?"+p,{cache:"no-store"});const j=await r.json();res=j.results||[];sel=-1;
  L.innerHTML=res.length?res.map((x,i)=>`<li role="option" id="gv_o${i}" data-i="${i}" aria-selected="false"><b>${E(x.name)}</b> <span class="meta">${E(x.title||"")}${x.party?` · ${E(x.party)}`:""}</span><div class="meta">${E(x.path||"")}</div></li>`).join(""):`<li class="meta" role="option" aria-disabled="true">No matches${st?" in this state":""}.</li>`;
  L.hidden=false;q("q").setAttribute("aria-expanded","true")}catch(e){}}
function pick(i){const x=res[i];if(!x)return;q("res").hidden=true;q("q").setAttribute("aria-expanded","false");goto(x.id,x.kind=="person")}
q("q").addEventListener("input",()=>{clearTimeout(tq);tq=setTimeout(search,180)});
q("q").addEventListener("keydown",e=>{const L=q("res");if(L.hidden)return;const n=res.length;
 if(e.key=="ArrowDown"||e.key=="ArrowUp"){e.preventDefault();sel=(sel+(e.key=="ArrowDown"?1:-1)+n)%n;[...L.children].forEach((li,i)=>li.setAttribute("aria-selected",i==sel?"true":"false"));q("q").setAttribute("aria-activedescendant","gv_o"+sel);L.children[sel]&&L.children[sel].scrollIntoView({block:"nearest"})}
 else if(e.key=="Enter"){e.preventDefault();pick(sel<0?0:sel)}else if(e.key=="Escape"){L.hidden=true}});
q("res").addEventListener("mousedown",e=>{const li=e.target.closest("li[data-i]");if(li){e.preventDefault();pick(+li.dataset.i)}});
q("q").addEventListener("blur",()=>setTimeout(()=>{q("res").hidden=true},150));
q("branch").addEventListener("change",()=>{openNode("us",q("tree"),0,true);search()});
q("state").addEventListener("change",()=>{const st=q("state").value,Q=q("quick");search();
 if(!st){Q.hidden=true;return}const nm=q("state").selectedOptions[0].textContent;
 Q.innerHTML=`<b>${E(nm)}:</b> `+[["st:"+st,"Governor & legislature"],["leg:senate:"+st,"U.S. senators"],["leg:house:"+st,"U.S. House members"],["jud:district:"+st,"Federal district courts"],["local:"+st,"Mayors"]].map(([id,l])=>`<button type="button" class="gv-link" data-goto="${E(id)}">${l}</button>`).join(" · ");Q.hidden=false});
M.addEventListener("click",e=>{const t=e.target;let b;
 if(b=t.closest("[data-tg]"))return toggle(b.closest(".gv-node"));
 if(b=t.closest("[data-pf]")){const el=b.closest(".gv-node");if(el.classList.contains("k-person"))return profile(b.dataset.pf);
  if(el.getAttribute("aria-expanded")=="false"&&!e.shiftKey){toggle(el);}return profile(b.dataset.pf)}
 if(b=t.closest("[data-more]"))return more(b);
 if(b=t.closest("[data-goto]"))return goto(b.dataset.goto);
 if(b=t.closest("[data-agency]")){const d=M.querySelector("[data-el=allwrap]");d.open=true;loadAll().then(()=>{const a=document.getElementById("gv_ag_"+b.dataset.agency);if(a){a.open=true;a.scrollIntoView({block:"center",behavior:"smooth"})}});return}
 if(t.closest('[data-gv="reload"]')){S.full=null;S.loaded={};load(true)}});
q("tree").addEventListener("keydown",e=>{const el=e.target.closest(".gv-node");if(!el)return;
 if(e.key=="ArrowRight"&&el.getAttribute("aria-expanded")=="false"){e.preventDefault();toggle(el)}else if(e.key=="ArrowLeft"){e.preventDefault();if(el.getAttribute("aria-expanded")=="true")toggle(el);else{const p=el.parentElement.closest(".gv-node");p&&p.querySelector(".gv-nm").focus()}}});
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="gov")setTimeout(()=>{if(!S.d)load()},0)});
if(location.hash=="#government")setTimeout(()=>tb.click(),400);
})();
