// ---- ⚖ Gun Laws tab (served by gunlaws.py; data: gunlaws.db built on the box by gunlaws_collect.py, daily + hourly market prices) ----
// Second Amendment / firearms cases (Supreme Court + notable lower courts), firearms bills in Congress, Nov. 3 ballot measures,
// prediction markets (live prices, odds-history charts) and blackout.network's transparent statistical estimates. Neutral wording only.
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?u:"#";
const A=(u,t,c)=>`<a href="${E(U(u))}" target="_blank" rel="noopener noreferrer"${c?` class="${c}"`:""}>${E(t)}</a>`;
const TZ="America/New_York",API="api/gunlaws";
const ET=t=>{if(!t)return"—";const d=new Date(t);return isNaN(d)?E(t):d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const DD=s=>{if(!s)return"";const m=/^(\d{4})-(\d\d)-(\d\d)$/.exec(s);if(!m)return E(s);return new Date(Date.UTC(+m[1],m[2]-1,+m[3],12)).toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric",year:"numeric"})};
const TODAY=()=>new Date().toLocaleDateString("en-CA",{timeZone:TZ});
const HS=s=>E(s).replace(/\b(\d{4})-(\d\d)-(\d\d)\b/g,m=>DD(m));
const days=s=>{if(!s)return null;return Math.round((Date.parse(s+"T12:00:00Z")-Date.parse(TODAY()+"T12:00:00Z"))/864e5)};
const inD=s=>{const n=days(s);return n==null?"":n==0?" (today)":n==1?" (tomorrow)":n>0?` (in ${n} days)`:` (${-n} days ago)`};
const P=(p,d)=>p==null?"—":(p*100<1&&p>0&&!d?(p*100).toFixed(1):(p*100).toFixed(d||0))+"%";
const R=c=>c?`${P(c.lo,c.lo<.1?1:0)}–${P(c.hi,c.hi<.1?1:0)}`:"";
const ICON=`<svg class="gl-ic" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18"/><path d="M7 21h10"/><path d="M5 7h14"/><path d="M5 7l-3 7a3 3 0 0 0 6 0z"/><path d="M19 7l-3 7a3 3 0 0 0 6 0z"/></svg>`;
// ---- nav button (after Politics) + panel + deep link #gunlaws
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="gunlaws"]');
if(!tb){tb=document.createElement("button");tb.type="button";tb.dataset.tab="gunlaws";tb.textContent="⚖ Gun Laws";tb.title="Gun Laws: court cases, bills and forecasts";nav.appendChild(tb)}
const place=()=>{const a=nav.querySelector('button[data-tab="politics"]');if(a&&a.nextElementSibling!==tb)a.insertAdjacentElement("afterend",tb)};place();setTimeout(place,450);
try{if(typeof TABHASH=="object"){TABHASH.gunlaws="gunlaws";HASHTAB.gunlaws="gunlaws"}}catch(_){}
let M=document.getElementById("tab-gunlaws");
if(!M){M=document.createElement("main");M.id="tab-gunlaws";M.dataset.addon="gunlaws";M.className="gl";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn"><h2>${ICON} Gun Laws <span class="meta">— firearms cases in U.S. courts, bills in Congress, ballot measures and what the numbers say</span><button type="button" class="tab-ref" data-gl="reload" title="Reload">↻</button></h2>
 <div class="gl-fresh meta" data-el="fresh">Loading…</div>
 <div class="gl-counts" data-el="counts"></div>
 <h3 class="gl-h3">At a glance <span class="gl-tag">blackout.network's statistical estimate, not legal advice or a prediction of certainty</span></h3>
 <div class="gl-glance" data-el="glance"></div>
 <details class="gl-method"><summary>How the estimates work: formulas, inputs and limits</summary><div data-el="method"></div></details>
 </section>
 <section class="pn"><h2>Court cases <span class="meta">— Supreme Court docket and petitions, plus notable federal and state cases</span></h2>
  <div class="gl-tools" role="search">
   <label>Court <select data-el="f_level" aria-label="Filter by court level"><option value="">All courts</option><option value="scotus">Supreme Court</option><option value="federal appeals">Federal appeals</option><option value="federal district">Federal district</option><option value="state">State courts</option></select></label>
   <label>Status <select data-el="f_status" aria-label="Filter by status"><option value="">Any status</option><option value="soon">Next date within 30 days</option><option value="awaiting">Granted, argued or awaiting decision</option><option value="petition">Petition or application pending</option><option value="decided">Decided (appeal or petition possible)</option></select></label>
   <label>State <select data-el="f_state" aria-label="Filter by state"><option value="">All states</option></select></label>
   <label class="gl-q">Search <input type="search" data-el="f_q" placeholder="Case, docket, law, party…" aria-label="Search cases" autocomplete="off"></label>
  </div>
  <div class="meta" data-el="ccount"></div>
  <div class="gl-cases" data-el="cases"></div>
  <details class="gl-routine" data-el="routinewrap"><summary data-el="routinesum">Other Supreme Court petitions</summary><div data-el="routine"></div></details>
  <details><summary>Recent Supreme Court Second Amendment decisions</summary><div data-el="decided"></div></details>
 </section>
 <section class="pn"><h2>Bills in Congress <span class="meta">— 119th Congress (2025–26) bills on firearms; chance each becomes law before Jan. 3, 2027</span></h2>
  <div class="gl-tools">
   <label>Show <select data-el="b_scope" aria-label="Which bills"><option value="core">Gun-focused bills</option><option value="all">All bills tagged “Firearms and explosives”</option></select></label>
   <label>Stage <select data-el="b_stage" aria-label="Filter by stage"><option value="">Any stage</option><option value="passed_one">Passed a chamber</option><option value="reported">Reported by committee</option><option value="introduced">Introduced only</option></select></label>
   <label>Chamber <select data-el="b_ch" aria-label="Filter by chamber"><option value="">Both</option><option value="House">House</option><option value="Senate">Senate</option></select></label>
   <label class="gl-q">Search <input type="search" data-el="b_q" placeholder="Title, number, sponsor…" aria-label="Search bills" autocomplete="off"></label>
  </div>
  <div class="gl-bsum" data-el="bsum"></div>
  <div class="gl-bills" data-el="bills"><div class="meta">Loading bills…</div></div>
  <div class="gl-more" data-el="bmore"></div>
  <p class="meta gl-note" data-el="statenote"></p>
 </section>
 <section class="pn"><h2>On the ballot Nov. 3, 2026 <span class="meta">— statewide firearms measures</span></h2><div class="gl-ballot" data-el="ballot"></div></section>
 <section class="pn"><h2>Prediction markets <span class="meta">— public Kalshi and Polymarket prices on gun-law questions; live</span> <span class="gl-live" data-el="live" aria-live="polite"></span></h2>
  <p class="meta">A price of 80¢ means traders as a group put the chance near 80%. Markets can be thin and wrong; we show the bid–ask spread and volume so you can judge. Not an endorsement of betting.</p>
  <div class="gl-markets" data-el="markets"></div><div class="meta gl-note" data-el="mnone"></div></section>
 <section class="pn"><h2>Sources <span class="meta">— free, public and keyless; refreshed daily, market prices hourly (live on this page)</span></h2><div class="meta" data-el="srcs"></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
const q=s=>M.querySelector(`[data-el="${s}"]`);
const S={d:null,bills:null,busy:false,bn:60,live:{},liveAt:null,timer:null,charts:{}};
// ---- labels
const LV={scotus:"Supreme Court","federal appeals":"Federal appeals court","federal district":"Federal district court",state:"State court"};
const ST_SC={granted:"Review granted",argued:"Argued, awaiting decision",pending:"Petition pending",application:"Application",decided:"Decided",denied:"Denied",gvr:"Sent back"};
const STAGE_B={introduced:"Introduced",reported:"Reported by committee",passed_one:"Passed one chamber",passed_both:"Passed both chambers",law:"Became law",vetoed:"Vetoed"};
const CORE=/firearm|\bguns?\b|handgun|pistol|rifle|shotgun|ammunition|\bammo\b|concealed|\bcarry\b|second amendment|2nd amendment|\bNICS\b|background check|silencer|suppressor|\bATF\b|\bbump\b|machine ?gun|magazine|ghost gun|extreme risk|red flag|\bLEOSA\b|weapon|armed|shooting|gun-?free|arms\b/i;
const statusCat=c=>c.level=="scotus"?(["granted","argued"].includes(c.stage)?"awaiting":["pending","application"].includes(c.stage)?"petition":"decided"):(c.stage=="decided"?"decided":"awaiting");
// ---- math helpers (client side only for the bill totals; everything else is computed on the box and shown with its inputs)
const MATH=(...a)=>a.map(s=>`<div class="gl-mathbox"><math display="block" xmlns="http://www.w3.org/1998/Math/MathML">${s}</math></div>`).join("");
function estPill(m,lead){if(!m||!m.combined)return"";const c=m.combined;return `<div class="gl-est"><span class="gl-estn">${P(c.p,c.p<.1?1:0)}</span><span>${E(lead||m.question||"")}<br><span class="meta">90% range ${R(c)} · blackout.network statistical estimate</span></span></div>`}
function partsTable(m){if(!m||!m.parts||!m.parts.length)return"";const W=m.combined&&m.combined.weights||{};
 const rows=m.parts.map(p=>`<tr><td>${E(p.label)}${p.src?` <span class="meta">(${/^https?:/.test(p.src)?A(p.src,"source"):E(p.src)})</span>`:""}<div class="meta">${E(p.detail||"")}${p.rate?` · Jeffreys 90% interval ${R(p.rate)}`:""}</div></td><td class="gl-num">${P(p.p,p.p<.1?1:0)}</td><td class="gl-num">${W[p.key]!=null?Math.round(W[p.key]*100)+"%":"—"}</td></tr>`).join("");
 return `<div class="gl-tw"><table class="gl-t"><thead><tr><th>Input</th><th>Chance</th><th>Weight</th></tr></thead><tbody>${rows}<tr class="gl-tot"><td>Combined (weighted log-odds average)</td><td class="gl-num">${P(m.combined.p,m.combined.p<.1?1:0)}</td><td class="gl-num">90% range ${R(m.combined)}</td></tr></tbody></table></div>
 ${m.limits&&m.limits.length?`<ul class="gl-lim">${m.limits.map(l=>`<li>${E(l)}</li>`).join("")}</ul>`:""}`}
// ---- SVG charts
const COL=["var(--ac)","#d4a94a","#9fb3c8","#b48ad1","#62b8a4","#d9886a"];
function series(o){const h=(o.hist||[]).slice(),s=o.snaps||[];const last=h.length?h[h.length-1][0]:0;for(const p of s)if(p[0]>last)h.push(p);return h}
function spark(pts){if(!pts||pts.length<2)return`<span class="meta">no history yet</span>`;const W=120,H=28,t0=pts[0][0],t1=pts[pts.length-1][0]||t0+1;
 const d=pts.map((p,i)=>`${i?"L":"M"}${((p[0]-t0)/(t1-t0||1)*W).toFixed(1)},${(H-2-p[1]*(H-4)).toFixed(1)}`).join("");
 return `<svg class="gl-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="30-day price trend"><path d="${d}" fill="none" stroke="var(--ac)" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`}
function chart(lines,range,W){W=Math.round(Math.max(300,Math.min(900,W||640)));const H=W<500?190:230,L=36,Rr=8,T=10,B=24;let t1=0,t0=Infinity;const cut=range?Date.now()/1e3-range*86400:0;
 lines=lines.map(l=>({...l,pts:l.pts.filter(p=>p[0]>=cut&&p[1]!=null)})).filter(l=>l.pts.length);
 if(!lines.length)return`<div class="meta">No price history in this range.</div>`;
 for(const l of lines){t0=Math.min(t0,l.pts[0][0]);t1=Math.max(t1,l.pts[l.pts.length-1][0])}if(t1<=t0)t1=t0+3600;
 const X=t=>L+(t-t0)/(t1-t0)*(W-L-Rr),Y=p=>T+(1-p)*(H-T-B);
 let g="";for(const v of[0,.25,.5,.75,1])g+=`<line x1="${L}" x2="${W-Rr}" y1="${Y(v)}" y2="${Y(v)}" class="gl-grid"/><text x="${L-5}" y="${Y(v)+4}" text-anchor="end" class="gl-ax">${v*100}%</text>`;
 const n=4;for(let i=0;i<=n;i++){const t=t0+(t1-t0)*i/n;const lab=new Date(t*1e3).toLocaleDateString("en-US",{timeZone:TZ,month:"short",day:"numeric",...(t1-t0>300*86400?{year:"2-digit"}:{})});g+=`<text x="${X(t)}" y="${H-6}" text-anchor="${i==0?"start":i==n?"end":"middle"}" class="gl-ax">${lab}</text>`}
 const paths=lines.map((l,i)=>{const d=l.pts.map((p,j)=>`${j?"L":"M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");const lp=l.pts[l.pts.length-1];
  return `<path d="${d}" fill="none" stroke="${COL[i%COL.length]}" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${X(lp[0])}" cy="${Y(lp[1])}" r="3.5" fill="${COL[i%COL.length]}"/>`}).join("");
 const leg=lines.length>1?`<div class="gl-leg">${lines.map((l,i)=>`<span><i style="background:${COL[i%COL.length]}"></i>${E(l.name)} ${P(l.pts[l.pts.length-1][1])}</span>`).join("")}</div>`:"";
 const data=E(JSON.stringify({t0,t1,L,W,Rr,lines:lines.map(l=>({n:l.name,p:l.pts}))}));
 return `<div class="gl-chartbox"><svg class="gl-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Price history chart" data-c="${data}">${g}${paths}<line class="gl-cur" x1="0" x2="0" y1="${T}" y2="${H-B}" visibility="hidden"/></svg><div class="gl-tip" hidden></div></div>${leg}`}
M.addEventListener("pointermove",e=>{const sv=e.target.closest&&e.target.closest("svg.gl-chart");if(!sv)return;let c;try{c=JSON.parse(sv.dataset.c)}catch(_){return}
 const r=sv.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*c.W;const t=c.t0+(x-c.L)/(c.W-c.L-c.Rr)*(c.t1-c.t0);if(t<c.t0||t>c.t1)return;
 const vals=c.lines.map(l=>{let best=l.p[0];for(const p of l.p){if(p[0]<=t)best=p;else break}return[l.n,best]});
 const cur=sv.querySelector(".gl-cur");cur.setAttribute("x1",x);cur.setAttribute("x2",x);cur.setAttribute("visibility","visible");
 const tip=sv.parentNode.querySelector(".gl-tip");tip.hidden=false;tip.innerHTML=`<b>${E(new Date(vals[0][1][0]*1e3).toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"}))}</b>`+vals.map(v=>`<div>${E(v[0])}: ${P(v[1][1])}</div>`).join("");
 tip.style.left=Math.min(r.width-150,Math.max(0,e.clientX-r.left+10))+"px"});
M.addEventListener("pointerleave",e=>{M.querySelectorAll(".gl-tip").forEach(t=>t.hidden=true);M.querySelectorAll(".gl-cur").forEach(c=>c.setAttribute("visibility","hidden"))},true);
// ---- data
async function load(force){if(S.busy)return;S.busy=true;q("fresh").textContent="Loading…";
 try{const r=await fetch(API+(force?"?t="+Date.now():""),{cache:"no-store"});const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);S.d=d;paint();loadBills();live();if(!S.timer)S.timer=setInterval(()=>{if(vis())live()},60000)}
 catch(e){q("fresh").innerHTML=`<span class="gl-err">Could not load the Gun Laws data: ${E(e.message)}</span>`}finally{S.busy=false}}
const vis=()=>M.style.display!="none"&&!document.hidden;
function marketFor(key){return(S.d.markets.items||[]).find(m=>m.key==key)}
function mkByTicker(t){for(const m of S.d.markets.items||[])for(const o of m.outcomes)if(o.ticker==t)return[m,o];return[null,null]}
function scCases(){const d=S.d;return(d.scotus||[]).map(s=>({level:"scotus",id:s.docket,name:(s.cur&&s.cur.short)||s.short,state:(s.cur&&s.cur.state)||s.state,stage:s.stage,status:s.status,next:s.next,nextLabel:s.next_label,sc:s,notable:!!s.cur,
  text:[s.docket,s.short,s.pet,s.resp,s.lower,s.topic,s.cur&&s.cur.law,s.cur&&s.cur.summary,(s.duke||{}).issue].join(" ")}))}
function lowerCases(){return((S.d.curated||{}).lower||[]).map(l=>({level:l.level,id:l.id,name:l.name,state:l.state,stage:l.stage,status:l.status,next:l.next,nextLabel:l.next_label,lc:l,notable:true,
  text:[l.name,l.court,l.docket,l.law,l.summary,JSON.stringify(l.parties||{})].join(" ")}))}
function allCases(){return scCases().concat(lowerCases())}
// ---- paint
function paint(){const d=S.d,mo=d.model||{},cu=d.curated||{};const u=d.updated||{};
 q("fresh").innerHTML=`Case data refreshed ${ET(u.full)} · market prices ${ET(u.markets)} · curated summaries checked ${DD(cu.checked)}. Neutral summaries; we do not take sides on gun policy.`;
 const sc=d.scotus||[],cs=allCases(),bills=d.bill_stages||{};const nb=Object.values(bills).reduce((a,b)=>a+b,0);
 const nMk=(d.markets.items||[]).length,nOut=(d.markets.items||[]).reduce((a,m)=>a+m.outcomes.length,0);
 const gr=sc.filter(s=>["granted","argued"].includes(s.stage)).length,pet=sc.filter(s=>["pending","application"].includes(s.stage)).length;
 const up=cs.filter(c=>c.next&&days(c.next)>=0&&days(c.next)<=30).length;
 q("counts").innerHTML=[[sc.length,"Supreme Court dockets",`${gr} granted or argued · ${pet} petitions or applications pending`],[lowerCases().length,"notable lower-court cases","federal appeals, district and state"],[up,"court dates in the next 30 days","arguments, conferences, deadlines"],
  [nb,"firearms bills in Congress",`${(bills.passed_one||0)+(bills.passed_both||0)} passed a chamber · ${bills.reported||0} reported`],[(cu.ballot||[]).length,"statewide ballot measures","on Nov. 3, 2026"],[nMk,"prediction markets",`${nOut} priced outcomes`]]
  .map(([n,l,s])=>`<div class="gl-cnt"><b>${n}</b><span>${E(l)}</span><span class="meta">${E(s)}</span></div>`).join("");
 // glance
 const ar=(mo.cases||{})["25-238"],hr=(mo.cases||{}).HR38,bal=mo.ballot||{};
 const card=(t,m,lead,sub,go)=>`<div class="gl-card"><h4>${E(t)}</h4>${m&&m.combined?estPill(m,lead):`<div class="meta">${E(sub||"No estimate")}</div>`}${m&&m.combined?`<p class="meta">${E(sub||"")}</p>`:""}${go?`<button type="button" class="gl-link" data-goto="${E(go)}">See the details →</button>`:""}</div>`;
 const bt=billTotals();
 q("glance").innerHTML=[
  card("AR-15 cases at the Supreme Court",ar,"chance the challengers win (the Court protects AR-15-style rifles)","Viramontes v. Cook County & Grant v. Higgins · argument Dec. 2, 2026 · decision expected by early July 2027","case-25-238"),
  card("Massachusetts Question 9",bal["ma-q9"],"chance “yes” wins (the 2024 gun law is kept)","Veto referendum on the 2024 firearms law · Nov. 3, 2026","ballot-ma-q9"),
  card("Arkansas Issue 2",bal["ar-issue2"],"chance “yes” wins (right to bear arms amendment)","Legislatively referred constitutional amendment · Nov. 3, 2026","ballot-ar-issue2"),
  card("Nationwide concealed-carry reciprocity",hr,"chance H.R. 38 or similar becomes law before Jan. 4, 2027","Reported by House Judiciary; on the Union Calendar since Oct. 3, 2025","bill-HR38"),
  bt?`<div class="gl-card"><h4>Firearms bills becoming law this Congress</h4><div class="gl-est"><span class="gl-estn">${bt.e.toFixed(1)}</span><span>expected number of the ${bt.n} bills to become law by Jan. 3, 2027<br><span class="meta">90% range ${bt.lo}–${bt.hi} bills · blackout.network statistical estimate</span></span></div><p class="meta">Sum of each bill's stage-based chance (formula below).</p></div>`:""].join("");
 paintMethod();paintFilters();paintCases();paintDecided();paintBallot();paintMarkets();paintSources()}
function billTotals(){const mo=(S.d.model||{}).bills||{},r=mo.rates;if(!r)return null;const st=S.d.bill_stages||{};let e=0,v=0,n=0;
 for(const [s,c] of Object.entries(st)){const p=(r[s]||{}).p;if(p==null)continue;e+=p*c;v+=p*(1-p)*c;n+=c}
 const sd=Math.sqrt(v);return{e,n,lo:Math.max(0,Math.floor(e-1.645*sd)),hi:Math.ceil(e+1.645*sd)}}
function paintMethod(){const mo=S.d.model||{},b=mo.bills||{},pt=mo.petitions||{},rv=S.d.reversal||{};
 const rr=b.rates||{};const rt=Object.entries(STAGE_B).filter(([k])=>rr[k]).map(([k,l])=>`<tr><td>${E(l)}</td><td class="gl-num">${rr[k].k} of ${rr[k].n.toLocaleString()}</td><td class="gl-num">${P(rr[k].p,1)}</td><td class="gl-num">${R(rr[k])}</td></tr>`).join("");
 const fr=b.rates_fire||{};const ft=Object.entries(STAGE_B).filter(([k])=>fr[k]&&fr[k].n).map(([k,l])=>`${E(l)}: ${fr[k].k} of ${fr[k].n}`).join(" · ");
 q("method").innerHTML=`<p><b>In plain English.</b> For each question we start from how often similar things have happened before (a <i>base rate</i>), add what prediction-market traders are paying, and, for ballot measures, what polls say. We blend these on the log-odds scale with fixed, published weights, then re-run the blend 20,000 times with each input jiggled within its own uncertainty to get a 90% range. Everything is shown so you can redo the math.</p>
 <details><summary>1 · Base rates (Jeffreys estimate)</summary><p>When something happened <i>k</i> times in <i>n</i> past cases, our estimate and its 90% interval come from the Beta posterior with a Jeffreys prior:</p>
 ${MATH(`<mi>p</mi><mo>∼</mo><mi>Beta</mi><mo>(</mo><mi>k</mi><mo>+</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>,</mo><mi>n</mi><mo>−</mo><mi>k</mi><mo>+</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>)</mo>`,`<mover><mi>p</mi><mo>^</mo></mover><mo>=</mo><mfrac><mrow><mi>k</mi><mo>+</mo><mn>0.5</mn></mrow><mrow><mi>n</mi><mo>+</mo><mn>1</mn></mrow></mfrac>`)}
 <p>The interval is the 5th to 95th percentile of that Beta distribution (regularized incomplete beta function, solved numerically). The ½ terms keep small samples from giving 0% or 100%.</p></details>
 <details><summary>2 · Combining inputs (weighted log-odds average)</summary>
 ${MATH(`<mi>logit</mi><mo>(</mo><mi>p</mi><mo>)</mo><mo>=</mo><mi>ln</mi><mfrac><mi>p</mi><mrow><mn>1</mn><mo>−</mo><mi>p</mi></mrow></mfrac>`,`<msub><mi>p</mi><mtext>est</mtext></msub><mo>=</mo><msup><mi>logit</mi><mrow><mo>−</mo><mn>1</mn></mrow></msup><mrow><mo>(</mo><mfrac><mrow><munder><mo>∑</mo><mi>i</mi></munder><msub><mi>w</mi><mi>i</mi></msub><mspace width="0.2em"/><mi>logit</mi><mo>(</mo><msub><mi>p</mi><mi>i</mi></msub><mo>)</mo></mrow><mrow><munder><mo>∑</mo><mi>i</mi></munder><msub><mi>w</mi><mi>i</mi></msub></mrow></mfrac><mo>)</mo></mrow>`)}
 <p>Averaging log-odds instead of percentages treats a move from 90% to 99% as the big change it is. The 90% range is from a Monte Carlo run: each base rate is redrawn from its Beta distribution, each market price uniformly between its bid and ask, each poll average from a normal distribution, and the blend is recomputed 20,000 times.</p>
 <p><b>AR-15 cases:</b> Supreme Court reversal rate over the last three terms (${E(((rv.terms||[]).slice(0,3)).map(t=>t.term).join(", "))}) 25% · challengers' record in Second Amendment merits cases since Bruen 25% · Kalshi 25% · Polymarket 25%. <b>Ballot measures:</b> market 50%, polls 30%, the state's history with that kind of measure 20%, statewide firearm-measure history 20% (weights re-scaled to add to 100% when an input is missing). <b>Concealed-carry reciprocity:</b> bill-stage base rate 50%, Kalshi 50%.</p></details>
 <details><summary>3 · Polls (ballot measures)</summary>
 ${MATH(`<mover><mi>s</mi><mo>¯</mo></mover><mo>=</mo><mfrac><mrow><mo>∑</mo><msub><mi>N</mi><mi>j</mi></msub><msub><mi>s</mi><mi>j</mi></msub></mrow><mrow><mo>∑</mo><msub><mi>N</mi><mi>j</mi></msub></mrow></mfrac>`,`<msub><mi>P</mi><mtext>polls</mtext></msub><mo>=</mo><mtext>Φ</mtext><mrow><mo>(</mo><mfrac><mrow><mover><mi>s</mi><mo>¯</mo></mover><mo>−</mo><mn>0.5</mn></mrow><mtext>σ</mtext></mfrac><mo>)</mo></mrow>`)}
 <p><i>s<sub>j</sub></i> is each poll's yes share of yes + no (undecided dropped), <i>N<sub>j</sub></i> its sample size, Φ the normal CDF, and σ = 6 points an assumed real-world polling error for ballot questions (larger than any single poll's sampling error). Only polls from the last 60 days are used.</p></details>
 <details><summary>4 · Bills: chance of becoming law by stage</summary>
 ${MATH(`<mi>P</mi><mo>(</mo><mtext>law</mtext><mo>∣</mo><mtext>stage</mtext><mo>=</mo><mi>s</mi><mo>,</mo><mtext>day</mtext><mo>=</mo><mi>d</mi><mo>)</mo><mo>≈</mo><mfrac><mrow><msub><mi>k</mi><mi>s</mi></msub><mo>+</mo><mn>0.5</mn></mrow><mrow><msub><mi>n</mi><mi>s</mi></msub><mo>+</mo><mn>1</mn></mrow></mfrac>`,`<mi>E</mi><mo>[</mo><mtext>laws</mtext><mo>]</mo><mo>=</mo><munder><mo>∑</mo><mi>b</mi></munder><msub><mi>P</mi><mi>b</mi></msub>`,`<mi>Var</mi><mo>=</mo><munder><mo>∑</mo><mi>b</mi></munder><msub><mi>P</mi><mi>b</mi></msub><mo>(</mo><mn>1</mn><mo>−</mo><msub><mi>P</mi><mi>b</mi></msub><mo>)</mo>`)}
 <p>${E(b.note||"")} Today is day ${E(b.day_of_term||"")} of the 119th Congress, which ends ${DD(b.end)}. The expected count's 90% range uses a normal approximation (± 1.645 standard deviations).</p>
 <div class="gl-tw"><table class="gl-t"><thead><tr><th>Furthest stage by this day</th><th>Became law</th><th>Rate</th><th>90% interval</th></tr></thead><tbody>${rt}</tbody></table></div>
 <p class="meta">Firearms bills alone (CRS subject “Firearms and explosives”, same Congresses): ${ft||"—"}. Too few to use on their own, so the all-bills rates are used.</p></details>
 <details><summary>5 · Supreme Court petitions</summary><p>Chance a firearms petition is granted, from this term's decided firearms petitions in the Duke Center for Firearms Law's SCOTUS Gun Watch: paid petitions ${pt.paid?`${pt.paid.rate.k} of ${pt.paid.rate.n} granted (${P(pt.paid.rate.p)}, 90% ${R(pt.paid.rate)})`:"—"}; fee-waived (in forma pauperis) petitions ${pt.ifp?`${pt.ifp.rate.k} of ${pt.ifp.rate.n} (${P(pt.ifp.rate.p,1)}, 90% ${R(pt.ifp.rate)})`:"—"}. Cases the Court is holding for a granted case are usually sent back or denied after it rules.</p></details>
 <details><summary>Limits</summary><ul class="gl-lim"><li>Base rates describe groups of cases, not this case. The weights are our choice, and are shown so you can change them.</li><li>Prediction markets on these questions are thin (low volume); one trader can move the price.</li><li>Lower-court cases are a curated list of notable cases, not every firearms case in the country. State legislatures' pending bills are not tracked (no free, keyless nationwide source).</li><li>Nothing here is legal advice or a prediction of certainty. Courts and voters can and do surprise.</li></ul></details>`}
function paintFilters(){const sel=q("f_state"),cur=sel.value;const st=new Set();allCases().forEach(c=>c.state&&st.add(c.state));
 sel.innerHTML=`<option value="">All states</option>`+[...st].sort().map(s=>`<option${s==cur?" selected":""}>${E(s)}</option>`).join("")+`<option value="US"${cur=="US"?" selected":""}>Federal law (no state)</option>`}
function pass(c){const L=q("f_level").value,s=q("f_status").value,st=q("f_state").value,t=q("f_q").value.trim().toLowerCase();
 if(L&&c.level!=L)return false;if(st&&(st=="US"?!!c.state:c.state!=st))return false;
 if(s=="soon"){const n=days(c.next);if(n==null||n<0||n>30)return false}else if(s&&statusCat(c)!=s)return false;
 if(t&&!c.text.toLowerCase().includes(t))return false;return true}
function paintCases(){const all=allCases(),mo=S.d.model||{};
 const notable=all.filter(c=>c.notable&&pass(c)),routine=all.filter(c=>!c.notable&&pass(c));
 const rank=c=>({granted:0,argued:1}[c.stage]??(c.level=="scotus"?2:3));
 notable.sort((a,b)=>rank(a)-rank(b)||(a.next||"9999").localeCompare(b.next||"9999"));
 q("ccount").textContent=`Showing ${notable.length} featured case${notable.length==1?"":"s"} and ${routine.length} other Supreme Court petition${routine.length==1?"":"s"} (of ${all.length}).`;
 q("cases").innerHTML=notable.map(c=>c.level=="scotus"?scCard(c.sc,mo):lowerCard(c.lc)).join("")||`<div class="meta">No featured cases match these filters.</div>`;
 const pt=mo.petitions||{};const topics={};routine.forEach(c=>{const k=c.sc.topic||"other";topics[k]=(topics[k]||0)+1});
 q("routinesum").innerHTML=`${routine.length} other Supreme Court petitions <span class="meta">— mostly people convicted under federal gun laws (${Object.entries(topics).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${v} ${E(k)}`).join(", ")})</span>`;
 q("routinewrap").hidden=!routine.length;
 routine.sort((a,b)=>(a.next||"9999").localeCompare(b.next||"9999"));
 q("routine").innerHTML=`<p class="meta">Base rate this term: ${pt.ifp?`${P(pt.ifp.rate.p,1)} of fee-waived`:"—"} and ${pt.paid?`${P(pt.paid.rate.p)} of paid`:"—"} firearms petitions decided so far were granted (formula 5 above).</p>`+routine.map(c=>{const s=c.sc,du=s.duke||{};const r=pt[s.ifp?"ifp":"paid"];
  return `<details class="gl-row"><summary><b>${E(c.name)}</b> <span class="meta">No. ${E(s.docket)} · ${E(shortCourt(s.lower))} · ${HS(s.status)}${s.next?inD(s.next):""}</span></summary>
  ${du.issue?`<p><b>Issue:</b> ${E(du.issue)}</p>`:""}<p class="meta">${s.ifp?"Fee-waived (in forma pauperis) petition":"Paid petition"}${r?` · chance of review from the base rate: about ${P(r.rate.p,1)} (90% ${R(r.rate)})`:""}${s.topic?` · topic: ${E(s.topic)}`:""}</p>
  ${counsel(s)}${docket(s)}<p>${A(s.url,"Supreme Court docket")}</p></details>`}).join("")}
const shortCourt=s=>(s||"").replace("United States Court of Appeals for the ","").replace("United States District Court for the ","").replace("Supreme Court of ","Sup. Ct. ");
function counsel(s){const c=s.counsel||{};const one=(l)=>l.map(a=>`<li>${E(a.name)}${a.of_record?" <span class=\"meta\">(counsel of record)</span>":""}${a.firm?` — ${E(a.firm)}`:""}${a.party?`<div class="meta">for ${E(a.party)}</div>`:""}</li>`).join("");
 return `<div class="gl-par"><div><b>Petitioner${/et al|,/.test(s.pet||"")?"s":""}:</b> ${E((s.pet||"").replace(/, Petitioners?$/,""))}${c.petitioner&&c.petitioner.length?`<ul>${one(c.petitioner)}</ul>`:""}</div>
 <div><b>Respondent${/et al/.test(s.resp||"")?"s":""}:</b> ${E(s.resp||"")}${c.respondent&&c.respondent.length?`<ul>${one(c.respondent)}</ul>`:""}</div></div>${s.other_counsel&&s.other_counsel.length?`<details><summary>Other counsel on the docket (${s.other_counsel.length}), mostly for amici</summary><ul>${one(s.other_counsel)}</ul></details>`:""}`}
function docket(s){const e=(s.entries||[]).slice().reverse();if(!e.length)return"";
 return `<details><summary>Docket: latest ${e.length} of ${s.n_entries||e.length} entries</summary><ul class="gl-dk">${e.map(x=>`<li><span class="meta">${DD(x.date)}</span> ${E(x.text)}${(x.links||[]).map(l=>` ${A(l.u,l.d||"PDF")}`).join("")}</li>`).join("")}</ul></details>`}
function scCard(s,mo){const c=s.cur||{},m=(mo.cases||{})[s.docket],pt=(mo.petitions||{})[s.ifp?"ifp":"paid"];const qp=s.qp||{};
 const mk=c.market?mkByTicker(c.market):[null,null];
 const est=m?estPill(m,m.lead||(/challengers win/.test(m.question||"")?"chance the challengers win (the Court protects AR-15-style rifles)":/petitioner/.test(m.question||"")?"chance the Court rules for the petitioner (base rate only)":m.question)):(["pending"].includes(s.stage)&&pt?`<div class="meta gl-base">Base rate: about ${P(pt.rate.p,1)} of ${s.ifp?"fee-waived":"paid"} firearms petitions decided this term were granted (90% ${R(pt.rate)}).</div>`:"");
 return `<article class="gl-case" id="gl-case-${E(s.docket)}" data-anchor="case-${E(s.docket)}">
 <div class="gl-ch"><h3>${E(c.short||s.short)}</h3><span class="gl-b">Supreme Court</span><span class="gl-b">No. ${E(s.docket)}</span>${c.state||s.state?`<span class="gl-b">${E(c.state||s.state)}</span>`:""}<span class="gl-b gl-bs">${E(ST_SC[s.stage]||s.stage)}</span></div>
 <div class="gl-st">${HS(s.status)}${s.next?` · <b>${E(s.next_label||"Next")}: ${DD(s.next)}</b>${inD(s.next)}`:""}</div>
 ${c.summary?`<p>${E(c.summary)}</p>`:""}${est}
 <details><summary>The question, the law and what a ruling could mean</summary>
  ${qp.qp||(s.duke||{}).issue?`<p><b>Question presented:</b> ${E(qp.qp||(s.duke||{}).issue)}</p>`:""}${qp.limited?`<p class="meta"><b>Scope of review:</b> ${E(qp.limited)}</p>`:""}
  ${c.law?`<p><b>Law at issue:</b> ${E(c.law)}</p>`:""}${c.if_pet?`<p>${E(c.if_pet)}</p>`:""}${c.if_resp?`<p>${E(c.if_resp)}</p>`:""}
  <p class="meta"><b>Lower court:</b> ${E(s.lower||"")}${s.lower_no?` No. ${E(s.lower_no)}`:""}${s.lower_date?`, decided ${DD(s.lower_date)}`:""}${s.docketed?` · docketed here ${DD(s.docketed)}`:""}${s.related&&s.related.length?` · related: ${s.related.map(E).join(", ")}`:""}${s.times_distributed?` · distributed for conference ${s.times_distributed} time${s.times_distributed==1?"":"s"}`:""}</p></details>
 <details><summary>Parties and lawyers</summary>${counsel(s)}</details>
 ${s.amici&&s.amici.length?`<details><summary>Friend-of-the-court (amicus) briefs: ${s.amici.length}</summary><ul class="gl-am">${s.amici.map(a=>`<li>${E(a)}</li>`).join("")}</ul></details>`:""}
 ${docket(s)}
 ${m?`<details><summary>How we got ${P(m.combined.p)}</summary>${partsTable(m)}</details>`:""}
 <div class="gl-links">${A(s.url,"Docket")}${qp.url&&!(c.links||[]).some(l=>/\/qp\//.test(l[1]))?A(qp.url,"Question presented (PDF)"):""}${(c.links||[]).map(l=>A(l[1],l[0])).join("")}${mk[0]?`<button type="button" class="gl-link" data-goto="mk-${E(mk[0].key)}">Market odds ↓</button>`:""}</div></article>`}
function lowerCard(l){const pr=l.parties||{};
 return `<article class="gl-case" id="gl-lc-${E(l.id)}"><div class="gl-ch"><h3>${E(l.name)}</h3><span class="gl-b">${E(LV[l.level]||l.level)}</span>${l.state?`<span class="gl-b">${E(l.state)}</span>`:""}<span class="gl-b gl-bs">${E(l.stage=="decided"?"Decided":l.stage=="pending"?"Awaiting decision":l.stage)}</span></div>
 <div class="gl-st">${E(l.court)} · ${E(l.docket)}<br>${E(l.status)}${l.next?` · <b>${E(l.next_label||"Next")}: ${DD(l.next)}</b>${inD(l.next)}`:""}</div>
 <p>${E(l.summary)}</p>
 <details><summary>The question and the law</summary>${l.question?`<p><b>Question:</b> ${E(l.question)}</p>`:""}${l.law?`<p><b>Law at issue:</b> ${E(l.law)}</p>`:""}${l.judges?`<p class="meta"><b>Judges:</b> ${E(l.judges)}</p>`:""}</details>
 <details><summary>Parties</summary><ul>${Object.entries(pr).map(([k,v])=>`<li><b>${E(k)}:</b> ${E(v)}</li>`).join("")}</ul></details>
 ${l.prior&&l.prior.length?`<details><summary>Timeline</summary><ul class="gl-dk">${l.prior.map(p=>`<li><span class="meta">${DD(p[1])}</span> ${E(p[0])}</li>`).join("")}</ul></details>`:""}
 <div class="gl-links">${(l.links||[]).map(x=>A(x[1],x[0])).join("")}</div><p class="meta">No prediction market or base-rate estimate for this case.</p></article>`}
function paintDecided(){const cu=S.d.curated||{};q("decided").innerHTML=`<p class="meta">${E(cu.decided_note||"")}</p><ul class="gl-dk">${(cu.decided||[]).map(d=>`<li><b>${A(d.url,d.case)}</b> <span class="meta">No. ${E(d.docket)} · ${DD(d.date)} · ${E(d.vote)} · ${d.challenger_won?"challenger prevailed":"government prevailed"}</span><div>${E(d.holding)}</div></li>`).join("")}</ul>`}
// ---- bills
async function loadBills(){try{const r=await fetch(API+"/bills");const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);S.bills=d.bills||[];paintBills()}catch(e){q("bills").innerHTML=`<div class="gl-err">Could not load bills: ${E(e.message)}</div>`}}
function billP(b){const r=((S.d.model||{}).bills||{}).rates||{};return b.stage=="law"?1:(r[b.stage]||{}).p}
function paintBills(){if(!S.bills)return;const sc=q("b_scope").value,stg=q("b_stage").value,ch=q("b_ch").value,t=q("b_q").value.trim().toLowerCase();
 const rows=S.bills.filter(b=>(sc=="all"||CORE.test(b.title+" "+(b.short||"")))&&(!stg||b.stage==stg)&&(!ch||b.chamber==ch)&&(!t||[b.label,b.title,b.short,(b.sponsor||{}).name,b.policy].join(" ").toLowerCase().includes(t)));
 const so={passed_both:0,passed_one:1,reported:2,introduced:3};rows.sort((a,b)=>(so[a.stage]??9)-(so[b.stage]??9)||((b.latest||{}).date||"").localeCompare((a.latest||{}).date||""));
 const by={};rows.forEach(b=>by[b.stage]=(by[b.stage]||0)+1);
 q("bsum").innerHTML=`<p><b>${rows.length}</b> bill${rows.length==1?"":"s"} shown${Object.keys(by).length?": "+Object.entries(STAGE_B).filter(([k])=>by[k]).map(([k,l])=>`${by[k]} ${E(l.toLowerCase())}`).join(" · "):""}. Typical chance of becoming law by Jan. 3, 2027: <b>${P(billP({stage:"introduced"}),1)}</b> if only introduced, <b>${P(billP({stage:"reported"}),1)}</b> once reported, <b>${P(billP({stage:"passed_one"}),0)}</b> after passing one chamber.</p>`;
 const sh=rows.slice(0,S.bn);
 q("bills").innerHTML=sh.map(b=>{const p=billP(b),sp=b.sponsor||{},cp=b.cos_party||{};
  return `<details class="gl-row gl-bill" data-bill="${E(b.id)}" id="gl-bill-${E(b.id)}"><summary><span class="gl-bl">${E(b.label)}</span> <b>${E(b.short||b.title)}</b> <span class="gl-b gl-bs">${E(STAGE_B[b.stage]||b.stage)}</span>${p!=null?` <span class="gl-b" title="Chance of becoming law by Jan. 3, 2027 (base rate by stage)">${P(p,1)} law</span>`:""}
   <div class="meta">${E(sp.name||"")} · ${b.cosponsors||0} cosponsor${b.cosponsors==1?"":"s"}${Object.keys(cp).length?` (${Object.entries(cp).map(([k,v])=>`${v} ${E(k)}`).join(", ")})`:""} · latest ${DD((b.latest||{}).date)}: ${E(((b.latest||{}).text||"").slice(0,160))}</div></summary><div data-el="bd">Open to load the summary…</div></details>`}).join("")||`<div class="meta">No bills match.</div>`;
 q("bmore").innerHTML=rows.length>S.bn?`<button type="button" class="gl-btn" data-gl="bmore">Show ${Math.min(60,rows.length-S.bn)} more (${rows.length-S.bn} left)</button>`:"";
 const om=S.d.bills_omnibus||[];
 q("statenote").innerHTML=`Source: Library of Congress bill status via ${A((S.d.bills_src||{}).url||"https://www.govinfo.gov/bulkdata/BILLSTATUS/119","GovInfo BILLSTATUS bulk data")}, fetched ${ET((S.d.bills_src||{}).fetched)}. “Gun-focused” means the title mentions firearms; “all” adds every bill the Congressional Research Service tagged “Firearms and explosives”. ${om.length?`${om.length} large spending or package bills that also carry firearms provisions are left out of the counts (${om.slice(0,4).map(o=>E(o.label)).join(", ")}${om.length>4?"…":""}).`:""} State legislatures' pending gun bills are not listed: there is no free, keyless nationwide source; statewide ballot measures are below.`}
async function billDetail(el){const bd=el.querySelector('[data-el="bd"]');if(el.dataset.ld)return;el.dataset.ld=1;
 try{const r=await fetch(API+"/bill?id="+encodeURIComponent(el.dataset.bill));const b=await r.json();if(!r.ok)throw new Error(b.error);const sp=b.sponsor||{};
  bd.innerHTML=`${b.summary?`<p><b>CRS summary:</b> ${E(b.summary)}</p>`:`<p class="meta">No Congressional Research Service summary yet.</p>`}
  <p class="meta"><b>Full title:</b> ${E(b.title)}</p><p class="meta"><b>Sponsor:</b> ${E(sp.name||"")} · introduced ${DD(b.introduced)} in the ${E(b.chamber)}${b.committees&&b.committees.length?` · committees: ${b.committees.map(E).join(", ")}`:""}${b.policy?` · policy area: ${E(b.policy)}`:""}</p>
  ${b.subjects&&b.subjects.length?`<p class="meta"><b>Subjects:</b> ${b.subjects.slice(0,14).map(E).join(", ")}${b.subjects.length>14?"…":""}</p>`:""}
  <p>${A(b.url,"Congress.gov")} ${b.xml?A(b.xml,"Bill status (XML)"):""}</p>`}catch(e){bd.innerHTML=`<span class="gl-err">Could not load: ${E(e.message)}</span>`;delete el.dataset.ld}}
// ---- ballot
function paintBallot(){const cu=S.d.curated||{},mo=(S.d.model||{}).ballot||{};
 q("ballot").innerHTML=(cu.ballot||[]).map(b=>{const m=mo[b.id]||{};const mk=b.market&&!b.market.multi?mkByTicker(b.market.id):[null,null];
  const polls=b.polls&&b.polls.length?`<details><summary>Polls (${b.polls.length})</summary><div class="gl-tw"><table class="gl-t"><thead><tr><th>Pollster</th><th>Ended</th><th>Sample</th><th>Yes</th><th>No</th></tr></thead><tbody>${b.polls.map(p=>`<tr><td>${E(p.by)}</td><td>${DD(p.end)}</td><td class="gl-num">${E(p.n)} ${E(p.pop)}</td><td class="gl-num">${E(p.yes)}%</td><td class="gl-num">${E(p.no)}%</td></tr>`).join("")}</tbody></table></div><p class="meta">Undecided voters make up the rest. LV = likely voters, RV = registered voters.</p></details>`:"";
  const multi=m.multi?`<div class="gl-tw"><table class="gl-t"><thead><tr><th>Option</th><th>Kalshi</th><th>Polymarket</th></tr></thead><tbody>${(m.kalshi||[]).map(([n,p],i)=>{const pm=(m.polymarket||[]).find(x=>x[0].split(" ").slice(0,3).join(" ")==n.split(" (")[0].split(" ").slice(0,3).join(" ")||n.includes(x[0]))||(m.polymarket||[]).find(x=>x[0].includes("Peacemaker")&&/Single Action/.test(n));return`<tr><td>${E(n)}</td><td class="gl-num">${P(p)}</td><td class="gl-num">${pm?P(pm[1]):"—"}</td></tr>`}).join("")}</tbody></table></div><p class="meta">${E(m.plain||"")} Prices of all options can add up to more than 100% because of bid–ask spreads.</p>`:"";
  return `<article class="gl-case" id="gl-ballot-${E(b.id)}"><div class="gl-ch"><h3>${E(b.name)}</h3><span class="gl-b">${E(b.state)}</span><span class="gl-b">${E(b.type)}</span><span class="gl-b gl-bs">Vote ${DD(b.date)}${inD(b.date)}</span></div>
  <p>${E(b.what)}</p>${m.combined?estPill(m):""}${multi}
  <details><summary>What a yes or no vote means, and who is campaigning</summary><p><b>Yes:</b> ${E(b.yes)}</p><p><b>No:</b> ${E(b.no)}</p>${b.support?`<p class="meta"><b>Campaigning for yes:</b> ${E(b.support)}</p>`:""}${b.oppose?`<p class="meta"><b>Campaigning for no:</b> ${E(b.oppose)}</p>`:""}</details>
  ${polls}${m.combined?`<details><summary>How we got ${P(m.combined.p)}</summary>${partsTable(m)}</details>`:""}
  <div class="gl-links">${(b.links||[]).map(x=>A(x[1],x[0])).join("")}${mk[0]?`<button type="button" class="gl-link" data-goto="mk-${E(mk[0].key)}">Market odds ↓</button>`:""}</div></article>`}).join("")||`<div class="meta">No statewide firearms ballot measures found for Nov. 3, 2026.</div>`}
// ---- markets
function paintMarkets(){const it=S.d.markets.items||[];
 q("markets").innerHTML=it.map(m=>{const mid=E(m.key);
  return `<article class="gl-mk" id="gl-mk-${mid}" data-anchor="mk-${mid}"><div class="gl-ch"><h3>${A(m.url,m.title)}</h3><span class="gl-b gl-src">${E(m.src)}</span>${m.sub?`<span class="meta">${E(m.sub)}</span>`:""}</div>
  <div class="gl-outs">${m.outcomes.map(o=>{const k=m.src+":"+o.ticker;return `<div class="gl-out"><div class="gl-on">${E(m.outcomes.length>1||m.multi?o.name:"Yes")}</div><div class="gl-op" data-live="${E(k)}">${P(o.mid)}</div>
   <div class="meta gl-ob" data-live-ba="${E(k)}">${o.bid!=null&&o.ask!=null?`bid ${P(o.bid)} · ask ${P(o.ask)}`:""}${o.volume?` · vol ${Math.round(o.volume).toLocaleString()}`:""}</div>${spark(o.spark)}</div>`}).join("")}</div>
  <details class="gl-hist" data-mk="${mid}"><summary>Odds history chart</summary><div class="gl-rng" role="group" aria-label="Chart range">${[["7",7],["30",30],["90",90],["All",0]].map(([l,v])=>`<button type="button" class="gl-btn${v==90?" on":""}" data-rng="${v}">${l=="All"?"All":l+"D"}</button>`).join("")}</div><div data-el="ch" class="meta">Loading…</div>
   <p class="meta">Daily prices from ${E(m.src)} (hourly for the last two weeks) plus our own hourly snapshots. ${o1(m)}</p></details>
  ${m.outcomes[0]&&m.outcomes[0].rules?`<details><summary>How this market resolves</summary><p class="meta">${E(m.outcomes[0].rules)}</p></details>`:""}</article>`}).join("");
 const si=S.d.market_index||{},srch=S.d.markets.searched||si.searched;
 q("mnone").innerHTML=`${it.length?"":"<b>No prediction markets on gun laws are open right now.</b> "}We searched every open Kalshi event and Polymarket's search for firearms terms${srch?` (${E(Array.isArray(srch)?srch.join(", "):JSON.stringify(srch)).slice(0,300)})`:""}. <b>No markets exist</b> for the pending Supreme Court petitions, the lower-court cases, or any bill other than concealed-carry reciprocity, so those show base-rate estimates only.`}
const o1=m=>m.outcomes.length>1?"Up to six options are drawn.":"";
async function histChart(det,rng){const key=det.dataset.mk,m=marketFor(key);if(!m)return;const box=det.querySelector('[data-el="ch"]');
 if(!S.charts[key]){box.textContent="Loading…";try{S.charts[key]=await Promise.all(m.outcomes.slice(0,6).map(o=>fetch(`${API}/history?key=${encodeURIComponent(key)}&t=${encodeURIComponent(o.ticker)}`).then(r=>r.json()).then(h=>({name:m.outcomes.length>1?o.name:"Yes",pts:series(h)}))))}catch(e){box.innerHTML=`<span class="gl-err">Could not load history.</span>`;return}}
 box.className="";box.innerHTML=chart(S.charts[key],rng,box.clientWidth||det.clientWidth-26)}
async function live(){try{const r=await fetch(API+"/live",{cache:"no-store"});const d=await r.json();if(!r.ok)throw new Error(d.error||r.status);S.live=d.prices||{};S.liveAt=d.at;
  for(const [k,v] of Object.entries(S.live)){M.querySelectorAll(`[data-live="${CSS.escape(k)}"]`).forEach(el=>{const old=el.textContent;el.textContent=P(v.mid);if(old!=el.textContent){el.classList.remove("gl-flash");void el.offsetWidth;el.classList.add("gl-flash")}});
   M.querySelectorAll(`[data-live-ba="${CSS.escape(k)}"]`).forEach(el=>{el.textContent=(v.bid!=null&&v.ask!=null?`bid ${P(v.bid)} · ask ${P(v.ask)}`:"")+(v.volume?` · vol ${Math.round(v.volume).toLocaleString()}`:"")})}
  q("live").innerHTML=`<span class="gl-dot"></span>live · ${ET(d.at)}${d.stale&&d.stale.length?` · <span class="meta">${E(d.stale.join(" and "))} prices delayed; showing the latest available</span>`:""}`}
 catch(e){q("live").innerHTML=`<span class="meta">live prices unavailable; showing the last hourly snapshot</span>`}}
function paintSources(){const d=S.d,sc=d.scotus_src||{},rv=d.reversal||{};
 const L=[["Supreme Court dockets (JSON), questions presented and opinions","https://www.supremecourt.gov/"],["Duke Center for Firearms Law — SCOTUS Gun Watch"+(sc.duke&&sc.duke.week?` (week of ${sc.duke.week})`:""),(sc.duke||{}).url||"https://firearmslaw.duke.edu/secondthoughts"],
  ["SCOTUS 2A tracker (scotus2a.com)","https://scotus2a.com/"],["Ballotpedia — Supreme Court reversal rates",rv.url||"https://ballotpedia.org/SCOTUS_case_reversal_rates_(2007_-_Present)"],["Ballotpedia — firearms ballot measures and polls","https://ballotpedia.org/Firearms_policy_ballot_measures"],
  ["GovInfo BILLSTATUS bulk data (Library of Congress)","https://www.govinfo.gov/bulkdata/BILLSTATUS/119"],["Congress.gov bill pages","https://www.congress.gov/"],["Kalshi public market data API","https://kalshi.com/"],["Polymarket public Gamma and CLOB APIs","https://polymarket.com/"],["Court opinions via GovInfo and the federal courts' sites","https://www.govinfo.gov/app/collection/uscourts"]];
 q("srcs").innerHTML=`<ul class="gl-src">${L.map(([t,u])=>`<li>${A(u,t)}</li>`).join("")}</ul><p>Lower-court cases and ballot-measure summaries are written and checked by hand (last checked ${DD((d.curated||{}).checked)}); Supreme Court docket status, counsel, amici and dates are pulled from the Court's own docket daily. CourtListener, GovTrack and OpenStates were not used (they need an account key or block automated access).</p>`}
// ---- events
M.addEventListener("click",e=>{const t=e.target;let b;
 if((b=t.closest('[data-gl="reload"]'))){S.charts={};load(true);return}
 if((b=t.closest('[data-gl="bmore"]'))){S.bn+=60;paintBills();return}
 if((b=t.closest("[data-rng]"))){const det=b.closest("details");det.querySelectorAll("[data-rng]").forEach(x=>x.classList.toggle("on",x==b));histChart(det,+b.dataset.rng);return}
 if((b=t.closest("[data-goto]"))){const g=b.dataset.goto;let el=null;
  if(g.startsWith("case-"))el=document.getElementById("gl-"+g);else if(g.startsWith("ballot-"))el=document.getElementById("gl-"+g);else if(g.startsWith("mk-"))el=document.getElementById("gl-"+g);
  else if(g.startsWith("bill-")){q("b_scope").value="all";q("b_stage").value="";q("b_ch").value="";q("b_q").value=g.slice(5).replace(/^HR/,"H.R. ").replace(/^S(\d)/,"S. $1");S.bn=60;paintBills();el=document.getElementById("gl-"+g);if(el)el.open=true}
  if(!el&&g.startsWith("case-")){["f_level","f_status","f_state"].forEach(k=>q(k).value="");q("f_q").value="";paintCases();el=document.getElementById("gl-"+g)}
  if(el){el.scrollIntoView({behavior:"smooth",block:"start"});el.classList.add("gl-hl");setTimeout(()=>el.classList.remove("gl-hl"),2200)}}});
M.addEventListener("toggle",e=>{const d=e.target;if(!d.open)return;if(d.classList.contains("gl-bill"))billDetail(d);if(d.classList.contains("gl-hist")){const on=d.querySelector("[data-rng].on");histChart(d,on?+on.dataset.rng:90)}},true);
["f_level","f_status","f_state"].forEach(k=>q(k).addEventListener("change",paintCases));q("f_q").addEventListener("input",()=>{clearTimeout(S.fq);S.fq=setTimeout(paintCases,150)});
["b_scope","b_stage","b_ch"].forEach(k=>q(k).addEventListener("change",()=>{S.bn=60;paintBills()}));q("b_q").addEventListener("input",()=>{clearTimeout(S.bq);S.bq=setTimeout(()=>{S.bn=60;paintBills()},150)});
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&S.d&&vis())live()});
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="gunlaws")setTimeout(()=>{if(!S.d)load();else live()},0)});
if(location.hash=="#gunlaws")setTimeout(()=>{if(M.style.display=="none")tb.click();if(!S.d)load()},400);
})();
