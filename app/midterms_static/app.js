// ---- 🗳 Midterms 2026 tab (served by midterms.py; data: midterms.db built on the box from free public sources, pushed to the site) ----
// Strictly descriptive: every rating, poll, market price and result is shown as its cited source published it. Nothing is projected here.
(()=>{"use strict";
const E=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const U=u=>(/^https?:\/\//i.test(u||"")||/^\/api\//.test(u||""))?E(u):"#";
const TZ="America/New_York";
const ET=(t,o)=>{if(!t)return"—";const d=new Date(t);if(isNaN(d))return E(t);return d.toLocaleString("en-US",Object.assign({timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"},o||{}))};
const TM=t=>{const d=new Date(t);return isNaN(d)?"—":d.toLocaleTimeString("en-US",{timeZone:TZ,hour:"numeric",minute:"2-digit"})+" ET"};
const API="/api/midterms";
const N=v=>v==null?"—":Number(v).toLocaleString("en-US");
const P=p=>p==null?"—":p>=.995&&p<1?"≥99%":p>0&&p<.01?"<1%":Math.round(p*100)+"%";
const PN={D:"Democratic",R:"Republican",I:"Independent",L:"Libertarian",G:"Green",C:"Constitution",F:"Forward",O:"Other"};
const OFF={senate:"U.S. Senate",governor:"Governor",house:"U.S. House"};
const ICON=`<svg class="mt-ic" width="20" height="20" style="width:20px;height:20px" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16v9H4z"/><path d="M8 12V8l4-5 4 5v4"/><path d="M10 16h4"/></svg>`;
// rating scale -> color (site palette: --ac blue, --hi red, --md amber); v is -3 (Safe D) .. +3 (Safe R)
const RC=v=>v==null?"#3a424d":v<=-2.5?"#1f6fd1":v<=-1.5?"#4aa3ff":v<=-0.75?"#86c2ff":v<-0.25?"#b9dcff":v<0.25?"#faad14":v<0.75?"#ffc4c4":v<1.5?"#ff8c8d":v<2.5?"#ff4d4f":"#c4292c";
const RT=v=>v==null?"#e6e9ee":(Math.abs(v)<0.8)?"#0b0d10":"#fff";
const PC={D:"#4aa3ff",R:"#ff4d4f",I:"#b37feb",L:"#d4b106",G:"#52c41a",O:"#8b95a3",C:"#8b95a3",F:"#8b95a3"};
const ln=n=>{n=String(n||"").replace(/\([^)]*\)/g," ").replace(/\[[^\]]*\]/g," ").replace(/,?\s+(Jr|Sr|II|III|IV)\.?$/i,"").trim();const p=n.split(/\s+/);return(p[p.length-1]||"").toLowerCase().replace(/[".,]/g,"")};

// ---- nav button (Monitor group, right after Politics) + panel + deep link #midterms
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="midterms"]');
if(!tb){tb=document.createElement("button");tb.type="button";tb.dataset.tab="midterms";tb.textContent="🗳 Midterms 2026";tb.title="2026 midterm elections: races, ratings, polls, market prices and results";nav.appendChild(tb)}
const place=()=>{const a=nav.querySelector('button[data-tab="politics"]');if(a&&a.nextElementSibling!==tb)a.insertAdjacentElement("afterend",tb)};place();setTimeout(place,450);setTimeout(place,1500);
try{if(typeof TABHASH=="object"){TABHASH.midterms="midterms";HASHTAB.midterms="midterms"}}catch(_){}
let M=document.getElementById("tab-midterms");
if(!M){M=document.createElement("main");M.id="tab-midterms";M.dataset.addon="midterms";M.className="mt";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn mt-hero"><h2>${ICON} Midterms 2026 <span class="meta">— Tuesday, November 3, 2026: who holds what, what is on the ballot, and the count as it comes in</span><button type="button" class="tab-ref" data-mt="reload" title="Reload this tab">⟳ Refresh</button></h2>
  <div class="mt-clock" data-el="clock" aria-live="polite">Loading…</div>
  <div class="meta mt-fresh" data-el="fresh"></div>
  <p class="mt-note">Descriptive only. Ratings, polls, market prices and results are shown exactly as the cited sources publish them, each with its date. BLACKOUT.NETWORK does not rate races, project winners or endorse anyone.</p></section>
 <section class="pn"><h2>Balance of power <span class="meta">— current seats, seats on the ballot and what a majority takes</span></h2><div class="mt-bal" data-el="bal"></div><div data-el="generic"></div></section>
 <section class="pn"><h2>Map <span class="meta">— colored by the published race ratings; a state turns solid once a winner is recorded</span></h2>
  <div class="mt-seg" role="tablist" data-el="mapseg"><button type="button" data-map="senate" class="on" role="tab" aria-selected="true">Senate</button><button type="button" data-map="governor" role="tab" aria-selected="false">Governor</button></div>
  <div class="mt-map" data-el="map" role="img" aria-label="Map of U.S. states colored by race rating"></div><div class="mt-legend" data-el="legend"></div></section>
 <section class="pn"><h2>Races <span class="meta">— every Senate and governor race and the competitive House seats, with candidates on the ballot</span></h2>
  <div class="mt-tools" role="search"><div class="mt-seg" data-el="off"><button type="button" data-off="senate" class="on">Senate</button><button type="button" data-off="governor">Governor</button><button type="button" data-off="house">House (competitive)</button></div>
   <input type="search" data-el="q" placeholder="Search a state, district or candidate…" aria-label="Search races" autocomplete="off">
   <label>Sort <select data-el="sort" aria-label="Sort races"><option value="close">Most competitive first</option><option value="state">State A–Z</option><option value="time">Poll closing time</option></select></label></div>
  <div class="meta" data-el="count"></div><div class="mt-list" data-el="list"></div></section>
 <section class="pn"><h2>Polls next to markets <span class="meta">— public polling averages beside Kalshi and Polymarket prices</span></h2>
  <p class="mt-note">These measure different things. A polling average estimates vote share. A market price is what traders pay for a contract that pays $1 if a candidate wins, so 70% means 70¢. Neither is an official result.</p>
  <div class="mt-pvo" data-el="pvo"></div></section>
 <section class="pn"><h2>Election-night results <span class="meta">— official state feeds and recorded winners, refreshed automatically on election night</span></h2><div data-el="feeds"></div></section>
 <section class="pn"><h2>All 435 House seats <span class="meta">— every district, its incumbent and the candidates on the ballot</span></h2><div data-el="house"></div></section>
 <section class="pn mt-src"><h2>Sources and method <span class="meta">— every input is free and public; nothing is estimated by us</span></h2><div data-el="src"></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
// if this tab's stylesheet failed to load (the host occasionally answers 502 during a busy page load), fetch it again
setTimeout(()=>{const ok=[...document.styleSheets].some(x=>{try{return /api\/midterms\/app\.css/.test(x.href||"")&&x.cssRules.length>0}catch(_){return false}});
 if(!ok){const l=document.createElement("link");l.rel="stylesheet";l.href=API+"/app.css?r="+Date.now();document.head.appendChild(l)}},2500);
const q=s=>M.querySelector(`[data-el="${s}"]`);
const S={d:null,live:null,off:"senate",map:"senate",sort:"close",qq:"",busy:false,lmap:null,glayer:null,geo:null,timer:null,shown:false};
// ---- lookups
const odds=rid=>(((S.d||{}).odds||{}).odds||{})[rid]||[];
function oddsFor(rid,c){const out={};for(const m of odds(rid)){const o=(m.outcomes||[]).find(o=>ln(o.name)===ln(c.name))||
  (m.outcomes||[]).find(o=>c.code==="D"&&/democrat|\(d\)/i.test(o.name)||c.code==="R"&&/republican|\(r\)/i.test(o.name));if(o)out[m.src]={p:o.p,url:m.url,basis:o.basis}}return out}
function pollCols(r){const a=(r.page||{}).aggregates;return a||null}
function avgRow(a){if(!a||!a.rows||!a.rows.length)return null;const av=a.rows.find(x=>/^average$/i.test(x.source));if(!av)return a.rows[0];
 const others=a.rows.filter(x=>x!==av);const ds=others.map(x=>Date.parse(x.updated)).filter(x=>!isNaN(x));
 return Object.assign({},av,{source:`average of the ${others.length} aggregators listed (computed on Wikipedia)`,updated:ds.length?new Date(Math.max(...ds)).toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric",timeZone:"UTC"}):""})}
function pollFor(r,c){const a=pollCols(r);if(!a)return null;const col=a.columns.find(k=>ln(k)===ln(c.name));if(!col)return null;const row=avgRow(a);
 return row&&row.values[col]!=null?{v:row.values[col],src:row.source,upd:row.updated}:null}
const feeds=()=>(((S.live&&S.live.official)||(S.d||{}).official_live||{}).feeds)||{};
function contestFor(r){const f=feeds()[r.state];if(!f||!f.published)return null;return(f.contests||[]).find(c=>c.kind===r.office&&(r.office!=="house"||String(c.district)===String(r.district)))||null}
function feedFor(r){return feeds()[r.state]||null}
function wk(r){const w=((S.live||{}).wikipedia||{})[r.id];if(w)return w;const res=(r.page||{}).results||{};
 return{winners:r.candidates.filter(c=>c.winner).map(c=>c.name),status:r.status,page_winner:res.winner,page_status:res.status,page_votes:(res.candidates||[]).filter(c=>c.votes)}}
function winnerOf(r){const w=wk(r);const n=(w.winners&&w.winners[0])||w.page_winner;if(!n)return null;const c=r.candidates.find(c=>ln(c.name)===ln(n));return{name:n,code:c?c.code:null,status:w.page_status||w.status}}
const races=()=>((S.d||{}).races||[]);
const houseAll=()=>((S.d||{}).house||[]);
const isComp=r=>{const k=r.consensus;if(k&&Math.abs(k.v)<2.5)return true;return["Cook","IE","Sabato"].some(x=>r.ratings&&r.ratings[x]&&r.ratings[x].v!=null&&Math.abs(r.ratings[x].v)<3)};
const title=r=>`${E(r.state_name||r.state)}${r.office==="house"?` ${r.district==="AL"?"at-large":"District "+E(r.district)}`:""} · ${OFF[r.office]}${r.special?" (special)":""}`;
// color follows the label text when it is a standard rating, so a chip's color always matches its words
const TV=t=>{const m=String(t||"").match(/\b(Safe|Solid|Likely|Lean|Tilt|Toss-?up)\b(?:\s+([DRI]))?/i);if(!m)return null;const k=m[1].toLowerCase();if(k.startsWith("toss"))return 0;const mag={safe:3,solid:3,likely:2,lean:1,tilt:.5}[k];return m[2]&&m[2].toUpperCase()==="D"?-mag:m[2]&&m[2].toUpperCase()==="R"?mag:null};
const chip=(t,v,extra)=>{const w=TV(t);v=w==null?v:w;return `<span class="mt-chip" style="background:${RC(v)};color:${RT(v)}"${extra||""}>${E(t)}</span>`};

const pchip=c=>`<span class="mt-p" style="--pc:${PC[c]||PC.O}" title="${E(PN[c]||"Other")}">${E(c||"?")}</span>`;
// ---- countdown to polls closing (times from 270toWin's 2026 poll closing page, Eastern Time)
function clock(){const d=S.d;if(!d)return;const t=Date.now(),first=Date.parse(d.first_close.at),lastc=Date.parse(d.last_close.at);
 const pc=Object.entries(Object.fromEntries(races().concat(houseAll()).map(r=>[r.state,r.poll_close]))).filter(x=>x[1]).map(([s,a])=>[s,Date.parse(a)]);
 const dur=ms=>{ms=Math.max(0,ms);const dd=Math.floor(ms/864e5),h=Math.floor(ms%864e5/36e5),m=Math.floor(ms%36e5/6e4),s=Math.floor(ms%6e4/1e3);return(dd?dd+"d ":"")+(dd||h?h+"h ":"")+m+"m "+String(s).padStart(2,"0")+"s"};
 let h;
 if(t<first)h=`<b>First polls close in <span class="mt-cd">${dur(first-t)}</span></b><div class="meta">${TM(d.first_close.at)} Tuesday, Nov 3, in the ${E(d.first_close.where)}. Last polls close ${TM(d.last_close.at)} Wednesday, Nov 4, in ${E(d.last_close.where)}.</div>`;
 else if(t<lastc){const closed=pc.filter(x=>x[1]<=t).map(x=>x[0]).sort();const nx=pc.filter(x=>x[1]>t).sort((a,b)=>a[1]-b[1]);const nt=nx.length?nx[0][1]:lastc;const ns=nx.filter(x=>x[1]===nt).map(x=>x[0]).sort();
  h=`<b>Polls are closing.</b> All polls closed in ${closed.length} states so far. <b>Next: <span class="mt-cd">${dur(nt-t)}</span></b> at ${TM(new Date(nt).toISOString())} (${E(ns.join(", ")||"remaining areas")}).<div class="meta">Last polls close ${TM(d.last_close.at)} in ${E(d.last_close.where)}.</div>`}
 else h=`<b>All polls have closed.</b> <span class="meta">Counting continues; states keep adding ballots for days, and official certification comes later.</span>`;
 q("clock").innerHTML=h}
// ---- balance of power
function bar(parts,total){return `<div class="mt-bar" role="img" aria-label="${E(parts.map(p=>p.n+" "+p.l).join(", "))}">${parts.map(p=>`<i style="width:${100*p.n/total}%;background:${p.c}" title="${E(p.l)}: ${p.n}"></i>`).join("")}</div>`}
function balance(){const b=(S.d||{}).balance||{},src=(S.d||{}).sources||{};const g=(o,k)=>{const v=((o||{})[k]||"").match(/-?\d+/);return v?+v[0]:null};
 const sen=b.senate||{},hou=b.house||{},gov=b.governor||{};
 const card=(ttl,o,total,maj,srck,note,extra)=>{const ks=Object.keys(o);const code=k=>/democrat/i.test(k)?"D":/republican/i.test(k)?"R":/independent/i.test(k)?"I":"O";
  const cur=ks.map(k=>({l:k,n:g(o[k],"Current seats")??g(o[k],"Seats before")??0,c:PC[code(k)]})).filter(x=>x.n>0);const sum=cur.reduce((a,x)=>a+x.n,0);
  const won=ks.some(k=>o[k]["Seats won"]||o[k]["Seats after"]);
  const rows=ks.map(k=>`<tr><th scope="row">${pchip(code(k))} ${E(k)}</th><td>${E(o[k]["Current seats"]||o[k]["Seats before"]||"—")}</td><td>${E(o[k]["Seats up"]||"—")}</td>${o[k]["Seats needed"]!==undefined?`<td>${E(o[k]["Seats needed"]||"—")}</td>`:""}${won?`<td><b>${E(o[k]["Seats won"]||o[k]["Seats after"]||"—")}</b></td><td>${E(o[k]["Seat change"]||"—")}</td>`:""}</tr>`).join("");
  const hasNeed=ks.some(k=>o[k]["Seats needed"]!==undefined);
  return `<div class="mt-card"><h3>${ttl}</h3>${bar(cur,total||sum)}<div class="mt-scroll"><table class="mt-t mt-balt"><thead><tr><th>Party</th><th>${/Governor/.test(ttl)?"Now":"Current"}</th><th>Up in 2026</th>${hasNeed?"<th>Seats needed</th>":""}${won?"<th>Won</th><th>Change</th>":""}</tr></thead><tbody>${rows}</tbody></table></div>
   <div class="meta">${maj}${total&&sum<total?` ${total-sum} seat${total-sum>1?"s":""} vacant.`:""} ${note||""} Source: <a href="${U((src[srck]||{}).url)}" target="_blank" rel="noopener">Wikipedia</a>, ${ET((src[srck]||{}).fetched)}.</div>${extra||""}</div>`};
 const ctlh=k=>ctl("control-"+k)?`<div class="mt-ctl meta">Market prices for ${k==="senate"?"Senate":"House"} control — ${ctl("control-"+k)}</div>`:"";
 const ctl=k=>odds(k).map(m=>`<a href="${U(m.url)}" target="_blank" rel="noopener">${E(m.src)}</a>: ${(m.outcomes||[]).slice(0,2).map(o=>`${E(o.name)} ${P(o.p)}`).join(" · ")}`).join("<br>");
 q("bal").innerHTML=card("Senate",sen,100,`A majority is 51 seats, or 50 plus the Vice President's tie-breaking vote. ${races().filter(r=>r.office==="senate").length} seats are on the ballot (${races().filter(r=>r.office==="senate"&&!r.special).length} regular, ${races().filter(r=>r.office==="senate"&&r.special).length} special).`,"senate","",ctlh("senate"))+
  card("House",hou,435,"All 435 seats are on the ballot. A majority is 218.","house","",ctlh("house"))+
  card("Governors",gov,50,`${races().filter(r=>r.office==="governor"&&r.state.length===2&&!["GU","MP","VI","AS","PR"].includes(r.state)).length} state governorships and ${races().filter(r=>r.office==="governor"&&["GU","MP","VI","AS","PR"].includes(r.state)).length} territorial governorships are on the ballot.`,"governor","");
 const gb=(S.d||{}).generic;
 q("generic").innerHTML=gb&&gb.rows&&gb.rows.length?`<details class="mt-det"><summary>Generic congressional ballot polling averages (which party voters say they prefer for Congress)</summary><div class="mt-scroll"><table class="mt-t"><thead><tr><th>Aggregator</th>${gb.columns.map(c=>`<th>${E(c)}</th>`).join("")}<th>Margin</th><th>Updated</th></tr></thead><tbody>${gb.rows.map(r=>`<tr><th scope="row">${E(r.source)}</th>${gb.columns.map(c=>`<td>${r.values[c]!=null?r.values[c]+"%":"—"}</td>`).join("")}<td>${E(r.margin||"")}</td><td>${E(r.updated||"")}</td></tr>`).join("")}</tbody></table></div><div class="meta">As compiled on <a href="${U((gb.source||{}).url)}" target="_blank" rel="noopener">Wikipedia</a> from each aggregator. "Average" is Wikipedia's average of the rows above.</div></details>`:""}
// ---- one race
function photo(c){const src=c.gov_photo||c.photo;const ini=E((c.name||"?").split(/\s+/).filter(Boolean).map(x=>x[0]).slice(0,2).join(""));
 return src?`<img class="mt-ph" src="${U(src)}" alt="${E(c.name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="44" height="44" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'mt-ph mt-ini',textContent:'${ini}'}))">`:`<span class="mt-ph mt-ini" aria-hidden="true">${ini}</span>`}
function ratings(r){const meta=((S.d||{}).ratings_meta||{})[r.office]||[];const R=r.ratings||{};const core=["Cook","IE","Sabato"];
 const one=k=>{const x=R[k];const m=meta.find(z=>z.key===k)||{};return x?`<span class="mt-rt"><span class="meta">${E(k==="IE"?"Inside Elections":k==="Sabato"?"Sabato":k)}</span> ${chip(x.t+(x.flip?" (flip)":""),x.v,` title="${E((m.name||k)+(m.date?", "+m.date:""))}"`)}</span>`:""};
 const others=Object.keys(R).filter(k=>!core.includes(k));
 if(!Object.keys(R).length)return `<div class="meta">No published ratings compiled for this race.</div>`;
 return `<div class="mt-rts">${core.map(one).join("")}${r.consensus?`<span class="mt-rt"><span class="meta">Average of the three</span> ${chip(r.consensus.t,r.consensus.v)}</span>`:""}</div>
  ${others.length?`<details class="mt-det"><summary>${others.length} more published ratings</summary><div class="mt-rts">${others.map(k=>{const x=R[k],m=meta.find(z=>z.key===k)||{};return `<span class="mt-rt"><span class="meta">${E(m.name||k)}${x.date?" · "+E(x.date):""}</span> ${chip(x.t+(x.flip?" (flip)":""),x.v)}</span>`}).join("")}</div></details>`:""}`}
function results(r){const out=[];const c=contestFor(r),f=feedFor(r),w=winnerOf(r);
 if(c){const tot=c.votes||0;out.push(`<div class="mt-res"><b>Official count</b> — <a href="${U(f.url)}" target="_blank" rel="noopener">${E(f.source)}</a>, as of ${ET(c.as_of||f.as_of)}: ${tot?c.options.slice(0,4).map(o=>`${E(o.name)} ${o.pct!=null?o.pct.toFixed(1)+"%":"—"} (${N(o.votes)})`).join(" · "):"no votes counted yet"} · ${N(c.reporting)} of ${N(c.total_units)} ${E(c.unit)} reporting${tot?". Leading is not a projection.":"."}</div>`)}
 else if(f&&f.ok&&!f.published&&["senate","governor","house"].includes(r.office))out.push(`<div class="mt-res meta">Official feed (${E(f.source)}): ${E(f.note||"not published yet")}</div>`);
 if(w)out.push(`<div class="mt-res mt-win">${pchip(w.code)} <b>${E(w.name)}</b> recorded as the winner on <a href="${U((r.page||{}).url||r.article)}" target="_blank" rel="noopener">Wikipedia</a>${w.status?` (“${E(w.status)}”)`:""}. <span class="meta">Wikipedia editors record winners from media projections and official counts; the official count governs.</span></div>`);
 const pv=(wk(r).page_votes||[]);if(!c&&pv.length&&!w)out.push(`<div class="mt-res meta">Vote totals recorded on Wikipedia: ${pv.slice(0,4).map(x=>`${E(x.name)} ${x.pct!=null?x.pct+"%":""} (${N(x.votes)})`).join(" · ")}</div>`);
 return out.join("")}
function card(r){const main=r.candidates.filter(c=>["D","R"].includes(c.code)||oddsFor(r.id,c).Kalshi||oddsFor(r.id,c).Polymarket||pollFor(r,c));
 const rest=r.candidates.filter(c=>!main.includes(c));const inc=r.incumbents||[];const f=((S.d||{}).official_links||{})[r.state];
 const row=c=>{const po=pollFor(r,c),od=oddsFor(r.id,c);const gl=c.gov_id?`<a class="mt-gov" href="/#government" data-gov="${E(c.gov_id)}">Government profile</a>`:"";
  return `<li class="mt-c">${photo(c)}<div class="mt-cn"><b>${E(c.name)}</b> ${pchip(c.code)} <span class="meta">${E(c.party||PN[c.code]||"")}</span>${c.incumbent?` <span class="mt-inc">Incumbent</span>`:""}${c.winner?` <span class="mt-inc mt-w">Winner recorded</span>`:""}
   <div class="meta">${c.wiki?`<a href="${U(c.wiki)}" target="_blank" rel="noopener">Wikipedia</a>`:""}${c.wiki&&gl?" · ":""}${gl}</div></div>
   <div class="mt-nums"><span title="${po?E(po.src+", updated "+(po.upd||"")):"No polling average published"}"><span class="meta">Polls</span> ${po?po.v.toFixed(1)+"%":"—"}</span><span><span class="meta">Kalshi</span> ${od.Kalshi?`<a href="${U(od.Kalshi.url)}" target="_blank" rel="noopener">${P(od.Kalshi.p)}</a>`:"—"}</span><span><span class="meta">Polymarket</span> ${od.Polymarket?`<a href="${U(od.Polymarket.url)}" target="_blank" rel="noopener">${P(od.Polymarket.p)}</a>`:"—"}</span></div></li>`};
 const a=pollCols(r),pl=(r.page||{}).polls;
 return `<article class="mt-race" id="race-${E(r.id)}"><header><h3>${title(r)}</h3>${r.consensus?chip(r.consensus.t,r.consensus.v):""}</header>
  <div class="meta">${inc.length?"Incumbent"+(inc.length>1?"s":"")+": "+inc.map(i=>`${E(i.name)} (${E(i.party||PN[i.code]||"")})`).join(", ")+(r.status?` — ${E(r.status)}`:""):"Open seat"+(r.status?` — ${E(r.status)}`:"")}${r.pvi?` · Cook PVI ${E(r.pvi)}`:""}${r.poll_close?` · Polls close ${TM(r.poll_close)}`:""}</div>
  ${ratings(r)}
  <ul class="mt-cands">${main.map(row).join("")}</ul>
  ${rest.length?`<div class="meta mt-rest">Also on the ballot: ${rest.map(c=>`${E(c.name)} (${E(c.party||"")})`).join(", ")}</div>`:""}
  ${results(r)}
  ${a||pl?`<details class="mt-det"><summary>Polling detail</summary>${a?`<div class="mt-scroll"><table class="mt-t"><thead><tr><th>Average</th>${a.columns.map(c=>`<th>${E(c)}</th>`).join("")}<th>Margin</th><th>Updated</th></tr></thead><tbody>${a.rows.map(x=>`<tr><th scope="row">${E(x.source)}</th>${a.columns.map(c=>`<td>${x.values[c]!=null?x.values[c]+"%":"—"}</td>`).join("")}<td>${E(x.margin||"")}</td><td>${E(x.updated||"")}</td></tr>`).join("")}</tbody></table></div>`:"<div class='meta'>No polling average is published for this race.</div>"}
   ${pl?`<div class="mt-scroll"><table class="mt-t"><thead><tr><th>Latest polls</th><th>Dates</th><th>Sample</th><th>Margin of error</th>${pl.columns.map(c=>`<th>${E(c)}</th>`).join("")}</tr></thead><tbody>${pl.rows.map(x=>`<tr><th scope="row">${E(x.source)}</th><td>${E(x.dates)}</td><td>${E(x.sample||"")}</td><td>${E(x.moe||"")}</td>${pl.columns.map(c=>`<td>${x.values[c]!=null?x.values[c]+"%":"—"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:""}
   <div class="meta">Compiled on <a href="${U((r.page||{}).url)}" target="_blank" rel="noopener">Wikipedia</a> (revision ${E((r.page||{}).revid||"")}); each poll's citation is there. Wikipedia marks polls sponsored by a party or partisan group with (R) or (D) after the pollster's name.</div></details>`:""}
  <div class="meta mt-links">${r.article?`<a href="${U(r.article)}" target="_blank" rel="noopener">Race article</a> · `:""}${f?`<a href="${U(f)}" target="_blank" rel="noopener">Official results (${E(r.state_name||r.state)})</a>`:""}${odds(r.id).map(m=>` · <a href="${U(m.url)}" target="_blank" rel="noopener">${E(m.src)} market</a>`).join("")}</div></article>`}
// ---- race list
function list(){const qq=S.qq.trim().toLowerCase();let rs=S.off==="house"?houseAll().filter(isComp):races().filter(r=>r.office===S.off);
 if(qq)rs=rs.filter(r=>(r.state_name+" "+r.state+" "+r.label+" "+r.candidates.map(c=>c.name).join(" ")+" "+(r.incumbents||[]).map(i=>i.name).join(" ")).toLowerCase().includes(qq));
 const cv=r=>r.consensus?Math.abs(r.consensus.v):9;
 rs=rs.slice().sort(S.sort==="state"?(a,b)=>(a.state_name||"").localeCompare(b.state_name||"")||(+a.district||0)-(+b.district||0):S.sort==="time"?(a,b)=>(a.poll_close||"").localeCompare(b.poll_close||"")||(a.state_name||"").localeCompare(b.state_name||""):(a,b)=>cv(a)-cv(b)||(a.state_name||"").localeCompare(b.state_name||""));
 q("count").textContent=`${rs.length} ${S.off==="house"?"competitive House races (not rated Safe/Solid by all of Cook, Inside Elections and Sabato)":S.off==="senate"?"Senate races":"governor races"}${qq?" matching “"+S.qq+"”":""}`;
 q("list").innerHTML=rs.map(card).join("")||`<div class="meta">No races match.</div>`}
// ---- polls next to markets (Senate + governor, one row per race)
function pvo(){const rs=races().slice().sort((a,b)=>(a.consensus?Math.abs(a.consensus.v):9)-(b.consensus?Math.abs(b.consensus.v):9)||a.state_name.localeCompare(b.state_name));
 const lead=(r,src)=>{const m=odds(r.id).find(x=>x.src===src);if(!m||!m.outcomes||!m.outcomes.length)return"—";const o=m.outcomes[0];const c=r.candidates.find(c=>ln(c.name)===ln(o.name));return `<a href="${U(m.url)}" target="_blank" rel="noopener">${E(o.name.replace(/\s*\([DRI]\)\s*$/,""))}${c?" "+pchip(c.code):""} ${P(o.p)}</a>`};
 const pm=r=>{const row=avgRow(pollCols(r));return row?`${E(row.margin||"")} <span class="meta">${E(row.source)}${row.updated?", "+E(row.updated):""}</span>`:`<span class="meta">no average published</span>`};
 q("pvo").innerHTML=`<div class="mt-scroll"><table class="mt-t mt-pvot"><thead><tr><th>Race</th><th>Rating (avg. of 3)</th><th>Polling average</th><th>Kalshi leader</th><th>Polymarket leader</th></tr></thead><tbody>${rs.map(r=>`<tr><th scope="row"><a href="#race-${E(r.id)}" data-jump="${E(r.id)}">${E(r.state_name)} ${r.office==="senate"?"Sen.":"Gov."}${r.special?" (sp.)":""}</a></th><td>${r.consensus?chip(r.consensus.t,r.consensus.v):"—"}</td><td>${pm(r)}</td><td>${lead(r,"Kalshi")}</td><td>${lead(r,"Polymarket")}</td></tr>`).join("")}</tbody></table></div>
 <div class="meta">Polling averages are the latest row of each race's Wikipedia "Source of poll aggregation" table (its own "Average" row when present). Market prices: <a href="https://kalshi.com/" target="_blank" rel="noopener">Kalshi</a> and <a href="https://polymarket.com/" target="_blank" rel="noopener">Polymarket</a> public APIs, fetched ${ET(((S.d||{}).odds||{}).fetched)}.</div>`}
// ---- election-night feeds
function feedsPanel(){const f=feeds(),L=(S.d||{}).official_links||{};const night=(S.live&&S.live.night)||((S.d||{}).night||{}).active;
 const rows=Object.values(f).map(x=>`<tr><th scope="row">${E(x.state)}</th><td><a href="${U(x.url)}" target="_blank" rel="noopener">${E(x.source)}</a></td><td>${!x.ok?`<span class="mt-bad">error: ${E(x.error||"")}</span>`:x.published?`${(x.contests||[]).length} federal/governor contests · ${N((x.contests||[]).reduce((a,c)=>a+(c.votes||0),0))} votes counted`:E(x.note||"not published yet")}</td><td>${x.as_of?ET(x.as_of):"—"}</td><td>${ET(x.checked)}</td></tr>`).join("");
 const won=[...races(),...houseAll()].map(r=>({r,w:winnerOf(r)})).filter(x=>x.w);
 q("feeds").innerHTML=`<p class="mt-note">${night?"<b>Election night mode:</b> this tab reloads results every 60 seconds.":"On election night (from 6 PM ET Nov 3) this tab reloads results every 60 seconds."} Official counts come straight from the state election offices that publish a free public data feed. Winners are shown only once Wikipedia records them (editors cite media projections and official counts). The Associated Press results service is licensed, not free, so it is not used; some state sites block automated access, so for those states use the official links below.</p>
 <div class="mt-scroll"><table class="mt-t"><thead><tr><th>State</th><th>Official feed</th><th>Status</th><th>State's time stamp</th><th>Checked</th></tr></thead><tbody>${rows||"<tr><td colspan=5>Loading…</td></tr>"}</tbody></table></div>
 <p class="meta">Recorded winners so far: <b>${won.length}</b>${won.length?" — "+won.slice(0,60).map(x=>`<a href="#race-${E(x.r.id)}" data-jump="${E(x.r.id)}">${E(x.r.state)}${x.r.office==="house"?"-"+E(x.r.district):" "+(x.r.office==="senate"?"Sen.":"Gov.")}</a> ${pchip(x.w.code)} ${E(x.w.name)}`).join(" · "):" (none yet)."}</p>
 <details class="mt-det"><summary>Official results pages for every state</summary><div class="mt-links2">${Object.entries(L).sort().map(([s,u])=>`<a href="${U(u)}" target="_blank" rel="noopener">${E(s)}</a>`).join(" ")}</div></details>`}
// ---- all 435 House seats, one collapsible block per state (rendered when opened)
function house(){const by={};for(const r of houseAll())(by[r.state_name]=by[r.state_name]||[]).push(r);
 q("house").innerHTML=`<div class="meta">${houseAll().length} districts. Candidates as compiled on <a href="${U((((S.d||{}).sources||{}).house||{}).url)}" target="_blank" rel="noopener">Wikipedia</a>; ratings from <a href="${U((((S.d||{}).sources||{}).house_ratings||{}).url)}" target="_blank" rel="noopener">its House ratings article</a> (competitive seats only).</div>`+
 Object.keys(by).sort().map(st=>`<details class="mt-det mt-hst" data-st="${E(st)}"><summary>${E(st)} <span class="meta">${by[st].length} seat${by[st].length>1?"s":""}</span></summary><div class="mt-hb"></div></details>`).join("");
 q("house").querySelectorAll("details.mt-hst").forEach(d=>d.addEventListener("toggle",()=>{if(!d.open||d.dataset.ok)return;d.dataset.ok=1;const rs=by[d.dataset.st].slice().sort((a,b)=>(a.district==="AL"?0:a.district)-(b.district==="AL"?0:b.district));
  d.querySelector(".mt-hb").innerHTML=`<div class="mt-scroll"><table class="mt-t"><thead><tr><th>District</th><th>Incumbent</th><th>Candidates on the ballot</th><th>Rating</th><th>Markets</th></tr></thead><tbody>${rs.map(r=>{const w=winnerOf(r),c=contestFor(r);const k=odds(r.id).map(m=>m.outcomes&&m.outcomes[0]?`<a href="${U(m.url)}" target="_blank" rel="noopener">${E(m.src)}: ${E(m.outcomes[0].name)} ${P(m.outcomes[0].p)}</a>`:"").filter(Boolean).join("<br>");
   return `<tr id="race-${E(r.id)}"><th scope="row">${r.district==="AL"?"At-large":E(r.district)}</th><td>${(r.incumbents||[]).map(i=>`${E(i.name)} ${pchip(i.code)}${i.gov_id?` <a class="mt-gov" href="/#government" data-gov="${E(i.gov_id)}">profile</a>`:""}`).join("<br>")||"<span class='meta'>Open / new seat</span>"}<div class="meta">${E(r.status||"")}</div></td>
   <td>${r.candidates.map(c=>`${E(c.name)} ${pchip(c.code)}${c.winner?" ✓":""}`).join("<br>")}${w?`<div class="mt-win">Winner recorded on Wikipedia: ${E(w.name)}</div>`:""}${c&&c.votes?`<div class="meta">Official: ${c.options.slice(0,2).map(o=>E(o.name)+" "+(o.pct!=null?o.pct.toFixed(1)+"%":"")).join(" · ")}, ${N(c.reporting)}/${N(c.total_units)} ${E(c.unit)}</div>`:""}</td>
   <td>${r.consensus?chip(r.consensus.t,r.consensus.v):"<span class='meta'>not on the competitive list</span>"}</td><td class="meta">${k||"—"}</td></tr>`}).join("")}</tbody></table></div>`}))}
// ---- sources and method
function sources(){const d=S.d||{},s=d.sources||{},rm=d.ratings_meta||{},o=d.odds||{},t=d.pipeline_test;
 const wl=k=>s[k]?`<li><a href="${U(s[k].url)}" target="_blank" rel="noopener">${E(s[k].title)}</a> — <a href="${U(s[k].permalink)}" target="_blank" rel="noopener">revision ${E(s[k].revid)}</a>, fetched ${ET(s[k].fetched)}</li>`:"";
 const rl=k=>(rm[k]||[]).map(m=>`${E(m.name)}${m.date?" ("+E(m.date)+")":""}`).join(", ");
 q("src").innerHTML=`<ul class="mt-ul">
 <li><b>Candidates, incumbents, balance of power, ratings and polling averages</b>: Wikipedia (text and tables CC BY-SA 4.0), read through the MediaWiki API:<ul>${wl("senate")}${wl("governor")}${wl("house")}${wl("house_ratings")}<li>Each Senate and governor race article (linked on its card, with its revision number) for polling averages, recent polls, results tables and candidate photos.</li></ul></li>
 <li><b>Race ratings</b> as published and dated by each rater and compiled on Wikipedia. Senate: ${rl("senate")}. Governor: ${rl("governor")}. House: ${rl("house")}. The colored “average of the three” is the plain average of Cook Political Report, Inside Elections and Sabato's Crystal Ball on a −3 (Safe D) to +3 (Safe R) scale; it is arithmetic, not a forecast.</li>
 <li><b>Polling averages</b>: the aggregators named in each table (for example RealClearPolitics, Decision Desk HQ, 270toWin, FiftyPlusOne, Silver Bulletin), as compiled on Wikipedia with their dates.</li>
 <li><b>Market prices</b>: <a href="https://docs.polymarket.com/" target="_blank" rel="noopener">Polymarket gamma API</a> and <a href="https://trading-api.readme.io/" target="_blank" rel="noopener">Kalshi trade API</a>, public and keyless, fetched ${ET(o.fetched)}${(o.errors||[]).length?` (${o.errors.length} request errors)`:""}. Prices are the markets' own.</li>
 <li><b>Official results</b>: Arizona Secretary of State, Georgia Secretary of State, Virginia Department of Elections and Washington Secretary of State (their public Enhanced Voting results API) and the North Carolina State Board of Elections results file. Votes, reporting counties or precincts and the state's own time stamp, unchanged. No winner is projected from them.</li>
 <li><b>Poll closing times</b>: <a href="${U((d.poll_close_source||{}).url)}" target="_blank" rel="noopener">${E((d.poll_close_source||{}).label)}</a> (fetched ${E((d.poll_close_source||{}).fetched)}), Eastern Time; a state is counted as closed at its latest closing time.</li>
 <li><b>Photos</b>: incumbents' official photos through the Government tab, and candidate photos from each race article's infobox (Wikimedia Commons; each file's license is on its Commons page).</li>
 <li><b>Not used</b>: the Associated Press results service (licensed, not free); Florida's results site (it sits behind a bot challenge); Clarity/Scytl results hosts used by several states (they refuse automated requests). For those states, use the official results links above.</li></ul>
 ${t?`<details class="mt-det"${t.ok?"":" open"}><summary>Pipeline test against the 2024 general election: ${t.ok?"all checks passed":"some checks failed"} (${ET(t.ran)})</summary><ul class="mt-ul">${(t.checks||[]).map(c=>`<li>${c.ok?"✅":"❌"} <b>${E(c.name)}</b>: ${E(c.detail)}</li>`).join("")}</ul></details>`:""}
 <p class="meta">Data built ${ET(d.built)} on the scanner node; page data checked ${ET(d.server_time)}.</p>`}
// ---- map (shared keyless basemap window.bnBaseLayer; state shapes: Natural Earth, public domain)
function mapStyle(f){const st=f.properties.st;const r=races().find(x=>x.office===S.map&&x.state===st);
 if(!r)return{color:"#2f3742",weight:1,fillColor:"#1b1f24",fillOpacity:.15};const w=winnerOf(r);
 if(w)return{color:"#0b0d10",weight:1.5,fillColor:PC[w.code]||PC.O,fillOpacity:.9};
 return{color:"#0b0d10",weight:1,fillColor:RC(r.consensus?(TV(r.consensus.t)??r.consensus.v):null),fillOpacity:.78}}
function legend(){const L=[["Safe D",-3],["Likely D",-2],["Lean D",-1],["Tilt D",-.5],["Tossup",0],["Tilt R",.5],["Lean R",1],["Likely R",2],["Safe R",3]];
 q("legend").innerHTML=L.map(([t,v])=>`<span><i style="background:${RC(v)}"></i>${t}</span>`).join("")+`<span><i style="background:transparent;border:1px solid var(--bd)"></i>No ${S.map==="senate"?"Senate":"governor"} race</span><span class="meta">Average of Cook, Inside Elections and Sabato. Solid ${pchip("D")}/${pchip("R")} fill = winner recorded on Wikipedia.</span>`+(()=>{const far=races().filter(r=>r.office===S.map&&["AK","HI"].includes(r.state));return far.length?`<div class="mt-far">Off the map view: ${far.map(r=>`<a href="#race-${E(r.id)}" data-jump="${E(r.id)}">${E(r.state_name)}</a> ${r.consensus?chip(r.consensus.t,r.consensus.v):""}${winnerOf(r)?" "+pchip(winnerOf(r).code)+" "+E(winnerOf(r).name):""}`).join(" · ")}</div>`:""})()}
async function map(){if(typeof L=="undefined")return;const el=q("map");
 if(!S.lmap){S.lmap=L.map(el,{zoomSnap:.25,scrollWheelZoom:false,attributionControl:true,worldCopyJump:false});const w=el.clientWidth||360;
  S.lmap.fitBounds([[24.5,-124.8],[49.4,-66.9]],{padding:[4,4]});if(window.bnBaseLayer)window.bnBaseLayer(S.lmap,{maxZoom:8,extra:"states: Natural Earth"});
  try{S.geo=await(await fetch(API+"/states.geojson")).json()}catch(e){el.insertAdjacentHTML("afterend",`<div class="meta">Map shapes did not load.</div>`);return}}
 if(S.glayer)S.glayer.remove();
 S.glayer=L.geoJSON(S.geo,{style:mapStyle,onEachFeature:(f,lay)=>{const r=races().find(x=>x.office===S.map&&x.state===f.properties.st);
  const w=r&&winnerOf(r);lay.bindTooltip(`<b>${E(f.properties.name)}</b><br>${r?(w?"Winner recorded: "+E(w.name):r.consensus?"Ratings average: "+E(r.consensus.t):"No ratings compiled"):"No "+(S.map==="senate"?"Senate":"governor")+" race in 2026"}`,{sticky:true});
  if(r)lay.on("click",()=>jump(r.id))}}).addTo(S.lmap);legend();setTimeout(()=>S.lmap.invalidateSize(),60)}
function jump(id){const r=[...races(),...houseAll()].find(x=>x.id===id);if(!r)return;
 if(r.office==="house"&&!isComp(r)){const d=q("house").querySelector(`details[data-st="${CSS.escape(r.state_name)}"]`);if(d){d.open=true;d.dispatchEvent(new Event("toggle"))}}
 else if(S.off!==r.office){S.off=r.office;seg();list()}
 setTimeout(()=>{const el=document.getElementById("race-"+id);if(el){el.scrollIntoView({behavior:"smooth",block:"start"});el.classList.add("mt-flash");setTimeout(()=>el.classList.remove("mt-flash"),1600)}},80)}
function seg(){q("off").querySelectorAll("button").forEach(b=>{b.classList.toggle("on",b.dataset.off===S.off);b.setAttribute("aria-pressed",b.dataset.off===S.off)})}
// ---- load + refresh
function paintAll(){if(!S.d)return;clock();balance();list();pvo();feedsPanel();if(!q("house").dataset.ok){house();q("house").dataset.ok=1}sources();if(S.shown)map();
 q("fresh").innerHTML=`Data built ${ET(S.d.built)} · market prices ${ET(((S.d.odds||{}).fetched))} · official feeds checked ${ET(((S.live&&S.live.official)||S.d.official_live||{}).fetched)}${S.live?` · results refreshed ${ET(S.live.server_time)}`:""}`}
async function load(force){if(S.busy)return;S.busy=true;try{const r=await fetch(API,{cache:force?"no-store":"default"});const j=await r.json();if(!r.ok)throw j.error||r.status;S.d=j;paintAll()}
 catch(e){q("clock").innerHTML=`<span class="mt-bad">Could not load: ${E(e)}</span>`}finally{S.busy=false}}
async function live(){try{const r=await fetch(API+"/live",{cache:"no-store"});if(!r.ok)return;S.live=await r.json();if(S.live.balance&&S.d)S.d.balance=S.live.balance;paintAll()}catch(e){}}
function schedule(){clearInterval(S.timer);const night=()=>{const t=Date.now(),n=(S.d||{}).night||{};return n.start&&t>=Date.parse(n.start)&&t<=Date.parse(n.end)};
 S.timer=setInterval(()=>{if(document.hidden||M.style.display=="none")return;if(night())live();else if(Date.now()-(S.lastFull||0)>6e5){S.lastFull=Date.now();load(true)}},60000)}
setInterval(()=>{if(S.d&&M.style.display!="none")clock()},1000);
M.addEventListener("click",e=>{const b=e.target.closest("[data-mt=reload]");if(b){load(true).then(live);return}
 const o=e.target.closest("[data-off]");if(o){S.off=o.dataset.off;seg();list();return}
 const m=e.target.closest("[data-map]");if(m){S.map=m.dataset.map;q("mapseg").querySelectorAll("button").forEach(x=>{x.classList.toggle("on",x===m);x.setAttribute("aria-selected",x===m)});map();return}
 const j=e.target.closest("[data-jump]");if(j){e.preventDefault();jump(j.dataset.jump);return}
 const g=e.target.closest("a[data-gov]");if(g){e.preventDefault();const id=g.dataset.gov;const gb=nav.querySelector('button[data-tab="gov"]');if(gb)gb.click();
  let n=0;const tryOpen=()=>{if(window.BNGov&&window.BNGov.open){window.BNGov.open(id)}else if(n++<40)setTimeout(tryOpen,150);else location.hash="#government"};tryOpen()}});
q("q").addEventListener("input",e=>{S.qq=e.target.value;clearTimeout(S.qt);S.qt=setTimeout(list,150)});
q("sort").addEventListener("change",e=>{S.sort=e.target.value;list()});
const show=()=>{S.shown=true;if(!S.d)load().then(()=>{map();live()});else map();schedule()};
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="midterms")setTimeout(show,0)});
if(location.hash=="#midterms")setTimeout(()=>tb.click(),400);
})();
