// ---- Politics tab (served by politics.py). Strictly neutral: headlines, market questions and outcome names are shown verbatim; no party colors. ----
(()=>{"use strict";
const M=document.getElementById("tab-politics");if(!M)return;
const e_=s=>esc(s==null?"":String(s)),U=u=>esc(safeUrl(u||"#"));
const etF=t=>{if(!t)return"—";const d=new Date(t);if(isNaN(d))return e_(t);return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"})+" ET"};
const etD=t=>{if(!t)return"—";const d=new Date(t);if(isNaN(d))return e_(t);return d.toLocaleDateString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric"})};
const num=v=>v==null?"—":v>=1e9?(v/1e9).toFixed(2)+"B":v>=1e6?(v/1e6).toFixed(1)+"M":v>=1e3?(v/1e3).toFixed(1)+"K":Math.round(v).toString();
const pct=p=>p==null?"—":p>=.995&&p<1?"≥99%":p>0&&p<.01?"<1%":Math.round(p*100)+"%";
const sev=s=>typeof lv=="function"?lv(s):(s>=60?"h":s>=35?"m":"l");
const TOPICS=["Control of Congress","Senate races","Governor races","House races","Presidential & nominations","Other races","Policy & government"];
const P={d:null,win:localStorage.getItem("pol_win")||"24h",src:localStorage.getItem("pol_src")||"all",wl:localStorage.getItem("pol_wl")||"all",topic:"all",busy:false,t:0};

// tab button (Monitor group, after Heat Map / Solar) + deep link #politics
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="politics"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="politics";tb.textContent="🏛 Politics";nav.appendChild(tb)}
const after=nav&&(nav.querySelector('button[data-tab="heatmap"]')||nav.querySelector('button[data-tab="solar_seismic"]'));if(after&&tb)after.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.politics="politics";HASHTAB.politics="politics"}}catch(_){}

const app=document.getElementById("pol_app");
app.innerHTML=`<div class=pol-note id=pol_range>Data range: loading…</div>
<div class=pol-grid>
 <div class=pol-col id=pol_dev><h3>Political developments <span class=meta>— the scanner's alerts in the political category, ranked by severity</span></h3>
  <div class=pol-ctl><span class=pol-seg id=pol_win><button data-w=24h>24 hours</button><button data-w=7d>7 days</button></span><span class=pol-seg id=pol_wl><button data-l=all>Wire + Watchlist</button><button data-l=wire>The Wire only</button></span><span class=pol-cnt id=pol_cnt></span></div>
  <div class=pol-list id=pol_alerts><div class=meta>Loading…</div></div></div>
 <div class=pol-col id=pol_mkts><h3>Prediction markets <span class=meta>— current prices on major US political questions</span></h3>
  <div class=pol-src id=pol_srcst></div><div id=pol_unav></div>
  <div class=pol-ctl><span class=pol-seg id=pol_srcf><button data-s=all>Both</button><button data-s=Polymarket>Polymarket</button><button data-s=Kalshi>Kalshi</button></span></div>
  <div class=pol-ctl id=pol_topics></div>
  <div class=pol-note>A price of 70% means traders on that market are paying 70¢ for a contract that pays $1 if the outcome happens. Prices are the markets' own, shown as-is for information; they are not forecasts by blackout.network.</div>
  <div class=pol-mk id=pol_mk><div class=meta>Loading…</div></div>
  <details class=pol-log><summary>Fetch log</summary><div id=pol_log></div></details></div>
</div>
<div class="pol-col pol-wide" id=pol_acc><h3>Track record <span class=meta>— how often each platform's favorite won on comparable past US political markets that have already resolved</span></h3><div id=pol_acc_body><div class=meta>Loading…</div></div></div>
<div class="pol-col pol-wide" id=pol_own><h3>Who's behind this <span class=meta>— ownership and funding of each data source shown on this tab, with citations</span></h3><div id=pol_own_body><div class=meta>Loading…</div></div></div>`;

if(typeof hwAttach=="function"){
 try{if(typeof HW_ICONS=="object"&&typeof hwI=="function"&&!HW_ICONS.politics)HW_ICONS.politics=hwI(`<path d="M30 40 L100 14 L170 40 Z"/><path d="M40 46 v40 M70 46 v40 M100 46 v40 M130 46 v40 M160 46 v40"/><path d="M26 92 h148"/><path d="M118 70 h40 M118 78 h28" stroke="#ff4d4f"/>`)}catch(_){}
 hwAttach(M.querySelector("#pol_top h2"),"politics",()=>"Left: every alert the bot's scanner already filed under the political category (coups, martial law, states of emergency, sanctions, impeachment, contested elections, mass protests, resignations and similar), read straight from its database and ranked by the same 0–10 rank and 0–100 score as The Wire. Headlines are shown exactly as the source wrote them, with the source links underneath; single-source items are marked Watchlist. Right: public prices from Polymarket and Kalshi for major US political questions (control of Congress, Senate and governor races, nominations, policy outcomes). This computer reads their free public data with no account or key every 10 minutes, keeps a copy in a separate politics.db, and never trades. Kalshi's open events are re-ranked by 24-hour volume every 6 hours. If a market site can't be reached, its last good copy stays up and is marked unavailable. Nothing on this tab changes any score or rank.")}

function card(c){const k=sev(c.score),wl=c.watchlist==1;
 return `<div class="card ${k}"><span class="sc ${k}">${c.score}</span><span class=pol-rk>rank <b>${c.rank}</b>/10</span><span class=pol-tag>${wl?"Watchlist":"The Wire"}</span><b>${e_(c.title)}</b>
 <div class=meta>${c.location?e_(c.location)+" · ":""}${e_(fmt(c.event_time||c.first_seen))} · confidence <b>${e_(c.confidence)}</b> · ${c.n_items} report(s) from ${c.n_families} source famil${c.n_families==1?"y":"ies"}${c.families&&c.families.length?": "+c.families.map(e_).join(", "):""}</div>
 <div class=meta>${(c.links||[]).slice(0,6).map(l=>`<a href="${U(l.url)}" target=_blank rel="noopener noreferrer">${e_(l.source)}</a>`).join(" · ")}</div></div>`}
function mk(m){const o=m.outcomes||[];
 return `<div class=mk><div class=meta><span class=pol-tag>${e_(m.src)}</span>${e_(m.topic)}</div>
 <a class=mt href="${U(m.url)}" target=_blank rel="noopener noreferrer">${e_(m.title)}${m.sub_title&&m.src=="Kalshi"?` <span class=meta>· ${e_(m.sub_title)}</span>`:""}</a>
 ${o.map(x=>`<div class=oc title="${e_(x.q||"")}${x.bid!=null&&x.ask!=null?` · bid ${pct(x.bid)} / ask ${pct(x.ask)}`:""}${x.basis?` · price = ${e_(x.basis)}`:""}"><span>${e_(x.name)}</span><span class=bar><i style="width:${Math.max(0,Math.min(100,x.p*100)).toFixed(1)}%"></i></span><span class=pc>${pct(x.p)}</span></div>`).join("")}
 ${m.n_outcomes>o.length?`<div class=more>+ ${m.n_outcomes-o.length} more outcome(s) on ${e_(m.src)}</div>`:""}
 ${sparkHTML(m)}${trackLine(m)}
 <div class=meta>Volume ${m.vol_unit=="USD"?"$":""}${num(m.volume)}${m.vol_unit=="USD"?"":" contracts"} · 24 h ${m.vol_unit=="USD"?"$":""}${num(m.volume24h)} · ${m.src=="Kalshi"?"closes":"ends"} ${etD(m.end)} · <a href="${U(m.url)}" target=_blank rel="noopener noreferrer">${e_(m.src)} ↗</a></div></div>`}
// ---------- odds history (sparklines + expandable chart; inline SVG, no external libraries) ----------
const LC=["var(--ac)","#c9d0d9","#7d8896"];
function gaps(pts,gapS){const segs=[];let cur=[];for(let i=0;i<pts.length;i++){if(cur.length&&pts[i][0]-pts[i-1][0]>gapS){segs.push(cur);cur=[]}cur.push(pts[i])}if(cur.length)segs.push(cur);return segs}
function medGap(pts){const d=[];for(let i=1;i<pts.length;i++)d.push(pts[i][0]-pts[i-1][0]);d.sort((a,b)=>a-b);return d.length?d[Math.floor(d.length/2)]:3600}
function sparkHTML(m){const s=m.spark||[];const lead=(m.outcomes||[])[0];if(!lead)return"";
 const id=`${m.src}|${m.id}`;
 if(s.length<2)return `<div class=pol-sp><span class=meta>No price history yet for “${e_(lead.name)}”</span> <button class=pol-hx data-h="${e_(id)}">📈 Odds history</button></div><div class=pol-ch data-for="${e_(id)}" hidden></div>`;
 const W=150,Hh=28,t0=s[0][0],t1=s[s.length-1][0]||t0+1,x=t=>((t-t0)/Math.max(1,t1-t0)*W).toFixed(1),y=p=>(Hh-2-p*(Hh-4)).toFixed(1);
 const gs=2*86400,sg=gaps(s,gs);
 const path=sg.map(g=>"M"+g.map(([t,p])=>x(t)+","+y(p)).join(" L")).join(" ");
 const gapR=sg.slice(1).map((g,i)=>{const a=sg[i][sg[i].length-1][0],b=g[0][0];return `<rect x="${x(a)}" y=0 width="${(x(b)-x(a)).toFixed(1)}" height=${Hh} class=gap><title>No data ${etD(a*1e3)} – ${etD(b*1e3)}</title></rect>`}).join("");
 return `<div class=pol-sp title="Leading outcome “${e_(lead.name)}”, last 30 days (${etD(t0*1e3)} – ${etD(t1*1e3)}). Shaded = no data.">
 <svg viewBox="0 0 ${W} ${Hh}" width=${W} height=${Hh} preserveAspectRatio=none><line x1=0 x2=${W} y1=${y(.5)} y2=${y(.5)} class=mid></line>${gapR}<path d="${path}" class=ln></path></svg>
 <span class=meta>${e_(lead.name)} · 30 d${(m.spark_src||[]).includes("u")?"":" · own snapshots only"}</span> <button class=pol-hx data-h="${e_(id)}">📈 Odds history</button></div><div class=pol-ch data-for="${e_(id)}" hidden></div>`}
const RANGES={"24h":86400,"7d":7*86400,"30d":30*86400,"all":1e12};
async function openChart(id,box){const [src,mid]=id.split("|");box.hidden=!box.hidden;if(box.hidden)return;box.innerHTML="<div class=meta>Loading price history…</div>";
 try{const r=await fetch(`api/politics/history?src=${encodeURIComponent(src)}&id=${encodeURIComponent(mid)}`,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;box._d=j;box._r=box._r||"30d";drawChart(box)}catch(e){box.innerHTML=`<div class=meta>Price history unavailable: ${e_(e)}</div>`}}
function drawChart(box){const j=box._d,R=RANGES[box._r],now=j.now;const names=Object.keys(j.series);
 const ser=names.map(n=>({n,pts:(j.series[n].points||[]).filter(p=>p[0]>=now-R),ok:j.series[n].upstream_ok,own:j.series[n].own_snapshots}));
 const all=ser.flatMap(s=>s.pts);const have=Object.fromEntries(Object.keys(RANGES).map(k=>[k,names.some(n=>(j.series[n].points||[]).some(p=>p[0]>=now-RANGES[k]))]));
 const seg=`<span class=pol-seg>${Object.keys(RANGES).map(k=>`<button data-r=${k} class="${box._r==k?"on":""}" ${have[k]?"":"disabled title='No history in this range'"}>${k}</button>`).join("")}</span>`;
 if(all.length<2){box.innerHTML=`<div class=pol-ctl>${seg}</div><div class=meta>No price history in this range.</div>`;return}
 const W=640,Hh=200,L=34,B=22,t0=Math.min(...all.map(p=>p[0])),t1=Math.max(...all.map(p=>p[0])),x=t=>(L+(t-t0)/Math.max(1,t1-t0)*(W-L-6)).toFixed(1),y=p=>(6+(1-p)*(Hh-B-6)).toFixed(1);
 let g="";[0,.25,.5,.75,1].forEach(v=>g+=`<line x1=${L} x2=${W-6} y1=${y(v)} y2=${y(v)} class=grid></line><text x=${L-4} y=${+y(v)+3} class=ax text-anchor=end>${v*100}%</text>`);
 const fmtT=t=>new Date(t*1e3).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",...(t1-t0<3*86400?{hour:"numeric"}:{})});
 for(let i=0;i<=4;i++){const t=t0+(t1-t0)*i/4;g+=`<text x=${x(t)} y=${Hh-6} class=ax text-anchor=middle>${e_(fmtT(t))}</text>`}
 let gapsN=0;ser.forEach((s,i)=>{if(s.pts.length<1)return;const gs=R<=7*86400?3*3600:2*86400,sg=gaps(s.pts,gs);
  sg.slice(1).forEach((q,k)=>{const a=sg[k][sg[k].length-1][0],b=q[0][0];gapsN++;if(i==0)g+=`<rect x=${x(a)} y=6 width=${(x(b)-x(a)).toFixed(1)} height=${Hh-B-6} class=gap><title>No data ${fmtT(a)} – ${fmtT(b)} ET</title></rect><text x=${((+x(a)+ +x(b))/2).toFixed(1)} y=16 class="ax gapt" text-anchor=middle>no data</text>`});
  g+=`<path d="${sg.map(q=>"M"+q.map(([t,p])=>x(t)+","+y(p)).join(" L")).join(" ")}" class=ln style="stroke:${LC[i]}"></path>`;
  s.pts.filter(p=>p[2]=="s").forEach(p=>g+=`<circle cx=${x(p[0])} cy=${y(p[1])} r=1.6 style="fill:${LC[i]}"></circle>`)});
 const lg=ser.map((s,i)=>`<span><i style="background:${LC[i]}"></i>${e_(s.n)} ${s.pts.length?pct(s.pts[s.pts.length-1][1]):"—"}${s.ok&&(s.ok.all||s.ok.week)?"":" · upstream history unavailable"}</span>`).join("");
 box.innerHTML=`<div class=pol-ctl>${seg}<span class=pol-lg>${lg}</span></div><svg viewBox="0 0 ${W} ${Hh}" class=pol-big>${g}</svg>
 <div class=meta>Lines: ${e_(j.series&&Object.values(j.series)[0]&&Object.values(j.series)[0].upstream_ok&&Object.values(j.series)[0].upstream_ok.all?(j.id&&box.dataset.for.startsWith("Kalshi")?"Kalshi candlesticks (daily; hourly for the last 7 days)":"Polymarket CLOB price history (daily; hourly for the last 7 days)"):"upstream history unavailable")}; dots = this dashboard's own 10-minute snapshots after the last upstream point. Shaded “no data” = a gap with no price points.${gapsN?` ${gapsN} gap(s) in this view.`:""} Times ET.</div>`}
M.addEventListener("click",e=>{const b=e.target.closest(".pol-hx");if(b){const box=b.closest(".mk").querySelector(`.pol-ch[data-for="${CSS.escape(b.dataset.h)}"]`);if(box)openChart(b.dataset.h,box);return}
 const r=e.target.closest(".pol-ch .pol-seg button");if(r&&!r.disabled){const box=r.closest(".pol-ch");box._r=r.dataset.r;drawChart(box)}});
// ---------- track record ----------
const A={d:null,h:"7",plat:"all",topic:"all",shown:40};
const TMAP={"Control of Congress":"Control of Congress","Senate races":"Senate races","Governor races":"Governor races","House races":"House races","Presidential & nominations":"Presidential & nominations","Other races":"Other races","Policy & government":"Policy & government"};
function recFor(plat,topic,h){const G=A.d&&(A.d.groups||{})[plat];if(!G)return null;const g=(G[topic]||{})[h];return g&&g.nontrivial&&g.nontrivial.n_fav?g:null}
function trackLine(m){if(!A.d)return"";const g=recFor(m.src,m.topic,"7"),o=recFor(m.src,"all","7");
 const f=(x,lab)=>x?`${lab}: favorite won <b>${x.nontrivial.acc}%</b> (n=${x.nontrivial.n_fav}) · Brier ${x.nontrivial.brier}`:`${lab}: no resolved comparable markets with price history yet`;
 return `<div class=pol-tr title="This market has not resolved; the figures are the platform's record on comparable past US political markets, 7 days before they were decided, excluding favorites priced above 97%.">🎯 ${f(g,e_(m.src)+" · "+e_(m.topic))}<br><span>${f(o,e_(m.src)+" overall")}</span></div>`}
function accRender(){const D=A.d,b=$("pol_acc_body");if(!D||!Array.isArray(D.events)||!D.counts){b.innerHTML="<div class=meta>Track record loading…</div>";return}
 const G0=(D.groups||{}).all||{},GG=D.groups||{};
 const c=D.counts,hz=D.horizon_counts,run=D.running?` · harvest in progress since ${etF(D.running)}`:"";
 const cell=g=>g&&g.n_fav?`<b>${g.acc}%</b> <small>(${g.n_fav})</small>`:"<small>—</small>",br=g=>g&&g.n?`${g.brier} <small>(${g.n})</small>`:"<small>—</small>";
 const row=(lab,G)=>`<tr><td>${lab}</td>${["30","7","1"].map(h=>`<td>${cell(G&&G[h]&&G[h].nontrivial)}</td><td class=mu>${cell(G&&G[h]&&G[h].all)}</td><td>${br(G&&G[h]&&G[h].nontrivial)}</td>`).join("")}</tr>`;
 const hd=`<tr><th rowspan=2></th>${["30 days before","7 days before","1 day before"].map(h=>`<th colspan=3>${h}</th>`).join("")}</tr><tr>${["30","7","1"].map(()=>`<th>Accuracy</th><th class=mu>incl. >97%</th><th>Brier</th>`).join("")}</tr>`;
 const plats=["all","Polymarket","Kalshi"],pl={all:"Both platforms (running overall)",Polymarket:"Polymarket",Kalshi:"Kalshi"};
 const topics=[...new Set(Object.keys(G0).filter(t=>t!="all"))];
 let ev=D.events.filter(r=>(A.plat=="all"||r.platform==A.plat)&&(A.topic=="all"||r.topic==A.topic));
 const scored=ev.filter(r=>r.horizons[A.h]),uns=ev.filter(r=>!r.horizons[A.h]);ev=[...scored,...uns];
 b.innerHTML=`<div class=pol-src><span><b>Polymarket</b> ${c.Polymarket.resolved} resolved markets scored · ${c.Polymarket.with_history} with price history (30 d: ${hz.Polymarket["30"]}, 7 d: ${hz.Polymarket["7"]}, 1 d: ${hz.Polymarket["1"]})</span><span><b>Kalshi</b> ${c.Kalshi.resolved} resolved · ${c.Kalshi.with_history} with price history (30 d: ${hz.Kalshi["30"]}, 7 d: ${hz.Kalshi["7"]}, 1 d: ${hz.Kalshi["1"]})</span><span>last harvest ${D.last?etF(D.last):"not finished yet"}${run} · refreshed daily</span></div>
 <div class=pol-acc-grid><div><div class=pol-tbw><table class=pol-tb>${hd}${plats.map(p=>row(pl[p],GG[p]&&GG[p].all)).join("")}</table></div>
 <h4>By topic (both platforms)</h4><div class=pol-tbw><table class=pol-tb>${hd}${topics.map(t=>row(e_(t),G0[t])).join("")}</table></div>
 <h4>By topic and platform</h4><div class=pol-tbw><table class=pol-tb>${hd}${["Polymarket","Kalshi"].flatMap(p=>Object.keys(GG[p]||{}).filter(t=>t!="all").map(t=>row(e_(p)+" · "+e_(t),GG[p][t]))).join("")}</table></div></div>
 <div class=pol-method><b>Method.</b> Only markets the platforms themselves have resolved are used, with their own resolution fields as the outcome (nothing is inferred). Each market's <i>decision time</i> is the first day from which the eventual winner stayed at or above ${D.method.decided*100}% until close (or the last price point). At 30, 7 and 1 day(s) before that, the highest-priced outcome is the <i>favorite</i>; a price must be no older than ${D.method.stale_days} days at that point. <b>Accuracy</b> = share of markets whose favorite was priced above 50% and won. <b>Brier</b> = mean of (favorite's price − 1 if it won, else 0)², 0 is perfect and 0.25 equals a coin flip. Headline figures leave out favorites priced above ${D.method.trivial_cut*100}% (near-certain markets); the gray column includes them. Multi-outcome markets use their ${D.method.max_outcomes} highest-volume outcomes plus the winner; mutually exclusive markets only. Up to ${D.method.max_scored} of the largest resolved US political events per platform, newest first. Small samples (n) are shown in brackets; treat them with care. The live markets above have <b>not</b> resolved: their 🎯 line shows the record of comparable past markets, not their own.</div></div>
 <div class=pol-ctl style="margin-top:10px"><span class=pol-seg id=pol_ah>${["30","7","1"].map(h=>`<button data-h=${h} class="${A.h==h?"on":""}">${h} d before</button>`).join("")}</span><span class=pol-seg id=pol_ap>${plats.map(p=>`<button data-p=${p} class="${A.plat==p?"on":""}">${p=="all"?"Both":p}</button>`).join("")}</span>
 <select id=pol_at><option value=all>All topics</option>${topics.map(t=>`<option ${A.topic==t?"selected":""}>${e_(t)}</option>`).join("")}</select><span class=meta>${scored.length} scored at this horizon · ${uns.length} without a price at this horizon</span></div>
 <div class=pol-tbw><table class="pol-tb pol-past"><tr><th>Market (verbatim)</th><th>Platform</th><th>Decided</th><th>Projected at the time</th><th>Outcome</th><th>Result</th></tr>
 ${ev.slice(0,A.shown).map(r=>{const x=r.horizons[A.h];return `<tr><td><a href="${U(r.url)}" target=_blank rel="noopener noreferrer">${e_(r.title)}</a><div class=meta>${e_(r.topic)}</div></td><td>${e_(r.platform)}</td><td>${r.decided_ts?etD(r.decided_ts*1e3):"—"}</td>
  <td>${x?`favorite <b>${e_(x.fav)}</b> ${pct(x.p_fav)}${x.won?"":` · winner was ${pct(x.p_win)}`}${x.p_fav>D.method.trivial_cut?" <small class=mu>(near-certain)</small>":""}`:`<span class=mu>${e_(r.status)}</span>`}</td><td>${e_(r.winner)}</td>
  <td>${x?(x.p_fav<=.5?`<span class=mu>no favorite >50%</span>`:x.won?`<span class=ok>✓ correct</span>`:`<span class=bad>✗ wrong</span>`):"<span class=mu>not scored</span>"}</td></tr>`}).join("")}</table></div>
 ${ev.length>A.shown?`<button class=pol-more id=pol_amore>Show more (${ev.length-A.shown} left)</button>`:""}`;
 b.querySelectorAll("#pol_ah button").forEach(x=>x.onclick=()=>{A.h=x.dataset.h;accRender()});b.querySelectorAll("#pol_ap button").forEach(x=>x.onclick=()=>{A.plat=x.dataset.p;accRender()});
 $("pol_at").onchange=e=>{A.topic=e.target.value;accRender()};const mb=$("pol_amore");if(mb)mb.onclick=()=>{A.shown+=60;accRender()}}
async function accLoad(){try{A.d=await (await fetch("api/politics/accuracy",{cache:"no-store"})).json()}catch(e){A.d=null}if(!A.d||!Array.isArray(A.d.events)){A.d=null;setTimeout(accLoad,60000)}accRender();render()}
// ---------- who's behind this ----------
async function ownLoad(){const b=$("pol_own_body");try{const o=await (await fetch("api/politics/ownership.json",{cache:"no-store"})).json();
 const det=o.detected||{},dn=o.detected_n||{};const shown=o.orgs.filter(x=>x.always||det[x.id]);const watchHit=(o.watch||[]).filter(w=>det[w.id]);
 b.innerHTML=`<div class=pol-note>${e_(o.about)} File: politics_static/ownership.json (updated ${e_(o.updated)}). Pollsters are listed only when a market or political alert on this tab actually names them; ${watchHit.length?watchHit.length+" detected without a profile yet: "+watchHit.map(w=>e_(w.name)).join(", "):"none are named right now"} (checked ${(o.watch||[]).length} pollster names).</div>
 <div class=pol-own>${shown.map(x=>`<div class=own><div class=meta><span class=pol-tag>${e_(x.kind)}</span>as of ${e_(x.as_of)}${det[x.id]?` · referenced by ${dn[x.id]} item(s) here`:""}</div><h4>${e_(x.name)}</h4><div class=own-sum>${e_(x.summary)}</div>
 ${x.sections.map(s=>`<div class=own-h>${e_(s.h)}</div><ul>${s.facts.map(f=>`<li>${e_(f.t)}${f.s=="reported"?` <span class=pol-tag>reported</span>`:""} <span class=cite>${f.cite.map((c,i)=>`<a href="${U(c.url)}" target=_blank rel="noopener noreferrer" title="${e_(c.title)} (${e_(c.date)})">[${i+1}] ${e_(c.title)}</a>`).join(" ")}</span></li>`).join("")}</ul>`).join("")}
 ${det[x.id]?`<details><summary class=meta>Where it is referenced</summary><div class=meta>${det[x.id].map(e_).join("<br>")}</div></details>`:""}</div>`).join("")}</div>`}
 catch(e){b.innerHTML=`<div class=meta>Ownership profiles unavailable: ${e_(e)}</div>`}}
function render(){const D=P.d;if(!D)return;
 M.querySelectorAll("#pol_win button").forEach(b=>b.classList.toggle("on",b.dataset.w==P.win));
 M.querySelectorAll("#pol_srcf button").forEach(b=>b.classList.toggle("on",b.dataset.s==P.src));
 const c=D.counts||{},a=c["24h"]||{},b=c["7d"]||{};
 $("pol_cnt").innerHTML=`24 h: <b>${(a.wire||0)+(a.watchlist||0)}</b> (${a.wire||0} Wire, ${a.watchlist||0} Watchlist) · 7 d: <b>${(b.wire||0)+(b.watchlist||0)}</b> (${b.wire||0} Wire, ${b.watchlist||0} Watchlist)`;
 M.querySelectorAll("#pol_wl button").forEach(b=>b.classList.toggle("on",b.dataset.l==P.wl));
 const AL=P.wl=="wire"?D.alerts.filter(x=>x.watchlist==0):D.alerts;
 $("pol_alerts").innerHTML=AL.length?AL.map(card).join(""):`<div class=meta>No political alerts in the last ${P.win=="7d"?"7 days":"24 hours"}.</div>`;
 try{$("pol_range").textContent=(typeof dataRange=="function"?dataRange(AL):"")+` · alerts updated ${etF(D.generated)}`}catch(_){}
 const S=D.markets||{},L={polymarket:"Polymarket",kalshi:"Kalshi"};
 $("pol_srcst").innerHTML=Object.entries(L).map(([k,n])=>{const s=S[k]||{};const cls=s.ok===true?"":s.ok===false?"bad":"wait";
  return `<span><i class="d ${cls}"></i><b>${n}</b> ${s.ok===true?`live · ${(s.items||[]).length} markets · last updated ${etF(s.fetched_at)}`:s.ok===false?"unavailable":"first fetch running…"}</span>`}).join("")+`<span>refreshes every ${Math.round((D.refresh_seconds||600)/60)} min</span>`;
 $("pol_unav").innerHTML=Object.entries(L).filter(([k])=>S[k]&&S[k].ok===false).map(([k,n])=>`<div class=pol-unav>⚠ ${n} unavailable at ${etF(S[k].fetched_at)}: ${e_(S[k].error)}. ${S[k].last_good_at?`Showing its last good data from ${etF(S[k].last_good_at)}.`:"No earlier data to show."}</div>`).join("");
 let all=[...((S.polymarket||{}).items||[]),...((S.kalshi||{}).items||[])];if(P.src!="all")all=all.filter(m=>m.src==P.src);
 const n={};all.forEach(m=>n[m.topic]=(n[m.topic]||0)+1);
 $("pol_topics").innerHTML=`<button class="pol-chip ${P.topic=="all"?"on":""}" data-t=all>All topics<small>${all.length}</small></button>`+TOPICS.filter(t=>n[t]).map(t=>`<button class="pol-chip ${P.topic==t?"on":""}" data-t="${e_(t)}">${e_(t)}<small>${n[t]}</small></button>`).join("");
 if(P.topic!="all")all=all.filter(m=>m.topic==P.topic);
 all.sort((x,y)=>TOPICS.indexOf(x.topic)-TOPICS.indexOf(y.topic)||(y.volume24h||0)-(x.volume24h||0));
 if(M.querySelector(".pol-ch:not([hidden])"))return;
 $("pol_mk").innerHTML=all.length?all.map(mk).join(""):`<div class=meta>No markets to show${P.src!="all"?" for "+e_(P.src):""}.</div>`;
 $("pol_log").innerHTML=`<table><tr><th>Time (ET)</th><th>Source</th><th>Result</th><th>Markets</th><th>ms</th><th>KB</th></tr>${(D.fetchlog||[]).map(r=>`<tr><td>${etF(r.ts)}</td><td>${e_(r.src)}</td><td class="${r.ok?"ok":"bad"}">${r.ok?"✓":"✗ "+e_(r.error||"")}</td><td>${r.n}</td><td>${r.ms}</td><td>${r.kbytes}</td></tr>`).join("")}</table>`}
async function load(force){if(P.busy)return;P.busy=true;try{const r=await fetch(`api/politics?window=${P.win}${force?"&force=1":""}`,{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;P.d=j;P.t=Date.now();render()}
 catch(e){$("pol_alerts").innerHTML=`<div class=meta>Politics data unavailable: ${e_(e)}</div>`}P.busy=false}
M.addEventListener("click",e=>{const w=e.target.closest("#pol_win button");if(w){P.win=w.dataset.w;localStorage.setItem("pol_win",P.win);load();return}
 const l=e.target.closest("#pol_wl button");if(l){P.wl=l.dataset.l;localStorage.setItem("pol_wl",P.wl);render();return}
 const s=e.target.closest("#pol_srcf button");if(s){P.src=s.dataset.s;localStorage.setItem("pol_src",P.src);P.topic="all";M.querySelectorAll(".pol-ch").forEach(x=>x.hidden=true);render();return}
 const t=e.target.closest(".pol-chip");if(t){P.topic=t.dataset.t;M.querySelectorAll(".pol-ch").forEach(x=>x.hidden=true);render()}});
const vis=()=>M.style.display!="none";
const rb=document.getElementById("pol_ref");if(rb)rb.onclick=async e=>{e.stopPropagation();rb.disabled=true;rb.textContent="scanning…";try{if($("refresh")&&$("refresh").onclick)await $("refresh").onclick()}catch(_){}rb.textContent="checking markets…";await load(true);rb.textContent="⟳ Refresh";rb.disabled=false};
let extraT=0;function loadExtra(){if(Date.now()-extraT<300000)return;extraT=Date.now();accLoad();ownLoad()}
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="politics"){load();loadExtra()}});
setInterval(()=>{if(vis())load()},60000);
let st=0;const hook=()=>{if(typeof LV=="object"&&LV&&LV.es){LV.es.addEventListener("scan",()=>{clearTimeout(st);st=setTimeout(()=>{if(vis())load()},3000)});return true}return false};if(!hook())setTimeout(hook,2000);
if(location.hash=="#politics")setTimeout(()=>{if(!vis()&&tb)tb.click();load();loadExtra()},350);
})();
