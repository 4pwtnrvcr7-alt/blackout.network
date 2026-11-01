/* Solar–Earthquake Correlation Lab (solar_quake.py). Exploratory analysis, not established science.
   Everything shown is read from /api/solar_quake (precomputed by tools/solar_quake_build.py from GFZ, NOAA and USGS data). */
(function(){
"use strict";
const TAB=document.getElementById("tab-solar");if(!TAB)return;
const E=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const Q={d:null,m:null,agg:"m",set:"declustered",lat:"geo",mapMode:"both",ev:"",charts:{},map:null,layer:null,sun:null,term:null,loading:false,built:false};
const COL={kp:"#faad14",fl:"#ff7a45",qk:"#4aa3ff",qk2:"#8fc7ff",in:"#ff9c3a",out:"#4aa3ff",null:"rgba(139,149,163,.28)",grid:"#252b33",mu:"#8b95a3"};
// t302: Render's free tier throws short 502/503 bursts; retry JSON fetches with backoff instead of failing permanently.
const getJSON=(u,waits=[1500,4000,9000,15000])=>fetch(u).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).catch(e=>{if(!waits.length)throw e;return new Promise(res=>setTimeout(res,waits[0])).then(()=>getJSON(u,waits.slice(1)))});
const f2=(v,n=2)=>v==null?"n/a":(+v).toFixed(n);
const pF=p=>p==null?"n/a":p<0.001?"< 0.001":(+p).toFixed(3);
const pct=(v,n=1)=>v==null?"n/a":(+v).toFixed(n)+"%";
const fmtD=s=>{if(!s)return"";const d=new Date(s.length<=10?s+"T00:00:00Z":s.replace(/Z?$/,"Z").replace("ZZ","Z"));return d.toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric",year:"numeric"})};
const fmtET=s=>{if(!s)return"";const d=new Date(s.endsWith("Z")?s:s+"Z");return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};

function host(){let s=document.getElementById("sq_top");
 if(!s){s=document.createElement("section");s.className="pn";s.id="sq_top";s.innerHTML='<div id="sq_app"></div>';TAB.appendChild(s)}
 if(!s.querySelector(".sq-head"))s.insertAdjacentHTML("afterbegin",`<h2 class="sq-head"><span class="sq-ic" aria-hidden="true">☀⇄◉</span> Solar–Earthquake Correlation Lab <span class="meta">— does space weather line up with earthquakes? 16+ years of real data, tested properly</span></h2>`);
 return s.querySelector("#sq_app")||s}

function visible(){return TAB.style.display!=="none"&&TAB.offsetParent!==null}
function boot(){const el=host();if(Q.built||Q.loading)return;
 el.innerHTML='<div class="sq-badge">Exploratory analysis, not established science</div><div class="meta">Loading the correlation lab…</div>';
 const go=()=>{if(Q.loading||Q.built)return;Q.loading=true;getJSON("api/solar_quake").then(d=>{Q.d=d;Q.loading=false;render()}).catch(e=>{Q.loading=false;el.innerHTML=`<div class="sq-badge">Exploratory analysis, not established science</div><div class="meta">The correlation lab couldn't load (${E(e.message)}).</div>`})};
 if("IntersectionObserver"in window){const io=new IntersectionObserver(es=>{if(es.some(x=>x.isIntersecting)){io.disconnect();go()}},{rootMargin:"600px"});io.observe(el)}else go()}

function verdict(d){const S=d.summary,T=d.tests;const sig=T.filter(t=>t.sig_holm);
 const nom=T.filter(t=>t.sig_raw);
 if(!sig.length)return{cls:"none",h:"No reliable correlation found",b:`We ran ${S.n_tests} pre-planned tests. After correcting for running that many tests (Holm), <b>none</b> is statistically significant. ${nom.length?`${nom.length} test${nom.length>1?"s":""} dipped under p&nbsp;=&nbsp;0.05 on its own, about what chance alone produces in ${S.n_tests} tries (expected ≈ ${(S.n_tests*0.05).toFixed(1)}).`:"None was even nominally significant."}`};
 return{cls:"some",h:`${sig.length} test${sig.length>1?"s":""} significant after correction`,b:`${sig.map(t=>E(t.label)+" ("+E(t.set)+")").join("; ")}. Treat this as a lead to re-test on future data, not as evidence of a physical link.`}}

function rateLine(r){const ch=r.pct_change;const dir=ch==null?"":ch>=0?`${f2(Math.abs(ch),1)}% more`:`${f2(Math.abs(ch),1)}% fewer`;
 const ok=r.p_perm!=null&&r.p_perm<0.05;
 return `${dir} quakes per day than at other times (rate ratio ${f2(r.rr,3)}, 95% CI ${f2(r.ci_low,2)}–${f2(r.ci_high,2)}; shuffle-test p = ${pF(r.p_perm)}) → <b>${ok?"nominally significant":"no detectable change"}</b>`}

function cards(){const d=Q.d,s=Q.set,R=d.rate,G=d.geo[s],L=d.lag;const v=verdict(d);
 const lk=L["kp_max:"+s],lf=L["flares_mx:"+s];
 const dn=G.day_own,di=G.day_impact,gl=G.geo_lat,ml=G.mag_lat,mg=G.mag;
 const c=(ic,h,b,cl="")=>`<div class="sq-card ${cl}"><div class="sq-ci">${ic}</div><div><h4>${h}</h4><p>${b}</p></div></div>`;
 return `<div class="sq-verdict ${v.cls}"><div class="sq-vh">${v.h}</div><p>${v.b}</p></div>
 <div class="sq-cards">
 ${c("🌐","During geomagnetic storms (Kp ≥ 5)",rateLine(R.g1_bins[s]))}
 ${c("💥","3 days after a storm hits (" + d.counts.g1_onsets + " onsets)",rateLine(R.g1_onset72[s]))}
 ${c("☀","3 days after an X-class flare",rateLine(R.x_flare72[s]))}
 ${c("📈","Lagged correlation, 0–10 days",`Strongest daily link: Kp vs quakes r = ${f2(lk.max_abs_r,3)} at ${lk.best_lag} d (chance alone reaches ${f2(lk.null95_max_abs_r,3)}; p = ${pF(lk.p_family)}); M+X flares r = ${f2(lf.max_abs_r,3)} (p = ${pF(lf.p_family)}). ${lk.p_family<0.05||lf.p_family<0.05?"<b>Nominal signal</b>":"<b>Indistinguishable from noise</b>"}. r² = ${f2(Math.max(lk.max_abs_r,lf.max_abs_r)**2*100,2)}% of day-to-day variation at most.`)}
 ${c("🌗","Day side or night side?",`${pct(dn.in_pct)} of impact-window quakes were in daylight vs ${pct(dn.base_pct)} at other times (shuffle p = ${pF(dn.p_perm)}). Relative to the Sun-facing side at the moment of impact: ${pct(di.in_pct)} vs ${pct(di.null_mean_pct)} expected (p = ${pF(di.p_perm)}).`)}
 ${c("🧭","Latitude bands",`Geographic bands χ² = ${f2(gl.chi2,1)} (shuffle p = ${pF(gl.p_perm)}); geomagnetic bands χ² = ${f2(ml.chi2,1)} (p = ${pF(ml.p_perm)}). ${gl.p_perm<0.05||ml.p_perm<0.05?"A nominal difference that does not survive the multiple-test correction.":"No clustering beyond what normal seismicity shows."}`)}
 ${c("📏","Bigger quakes during impacts?",`Mean magnitude M${f2(mg.mean_in,2)} vs M${f2(mg.mean_out,2)}; b-value ${f2(mg.b_in,2)} ± ${f2(mg.b_in_se,2)} vs ${f2(mg.b_out,2)} ± ${f2(mg.b_out_se,2)} (shuffle p = ${pF(mg.b_p_perm)}); KS p = ${pF(mg.ks_p_perm)}. ${mg.b_p_perm<0.05||mg.ks_p_perm<0.05?"Nominal shift only.":"No shift in the magnitude mix."}`)}
 </div>`}

function skeleton(){const d=Q.d,C=d.counts,P=d.params;const el=host();
 el.innerHTML=`<div class="sq-badge">Exploratory analysis, not established science</div>
 <p class="sq-lead">Some people claim solar flares and geomagnetic storms trigger earthquakes. Mainstream seismology finds no reliable link; for example, a USGS study of historical solar, geomagnetic and earthquake records could not reject “no solar-terrestrial triggering” (<a href="https://doi.org/10.1002/grl.50211" target="_blank" rel="noopener noreferrer">Love &amp; Thomas 2013, <i>Geophysical Research Letters</i></a>). Here we test it ourselves on ${C.quakes_m45.toLocaleString()} USGS earthquakes and ${(C.flares.C+C.flares.M+C.flares.X).toLocaleString()} C/M/X flares, and we show the results whether or not they are exciting.</p>
 <div class="sq-fresh">Analysis computed <b>${E(d.generated_et)}</b> · data ${E(fmtD(d.span.start))} → ${E(d.span.end_et)} (${Math.round(d.span.days).toLocaleString()} days) · quakes M${P.m_min}+ (catalog complete above about M${P.mc_maxc})</div>
 <div class="sq-ctl"><span>Earthquake set</span><span class="sq-seg" id="sq_set"><button data-v="declustered">Declustered (main shocks)</button><button data-v="raw">Raw (with aftershocks)</button></span>
 <span class="sq-hint">Aftershocks come in bursts and fake “significance”. The declustered set (Gardner–Knopoff) is the fair test; the raw set is shown for comparison.</span></div>
 <div id="sq_cards"></div>
 <div class="sq-grid">
  <figure class="sq-fig wide"><figcaption>Solar activity vs earthquakes over time <small>bars: M${P.m_min}+ quakes · lines: max Kp and M+X flare count in each period</small></figcaption><div class="sq-ctl sm"><span class="sq-seg" id="sq_agg"><button data-v="m">4-week totals</button><button data-v="w">Weekly</button></span></div><div class="sq-cv tall"><canvas id="sq_c_ts"></canvas></div></figure>
  <figure class="sq-fig"><figcaption>Superposed epoch: quakes per day around storm onsets <small>day 0 = onset · shaded = 95% range from shuffled onsets</small></figcaption><div class="sq-ctl sm"><span class="sq-seg" id="sq_sea"><button data-v="g1" class="on">G1+ (${C.g1_onsets})</button><button data-v="g3">G3+ (${C.g3_onsets})</button></span></div><div class="sq-cv"><canvas id="sq_c_sea"></canvas></div></figure>
  <figure class="sq-fig"><figcaption>Lag correlation (solar leads by 0–10 days) <small>dashed = 95% of the largest |r| chance gives across all lags</small></figcaption><div class="sq-cv"><canvas id="sq_c_lag"></canvas></div></figure>
  <figure class="sq-fig"><figcaption>Day side vs night side in impact windows <small>% of quakes vs the baseline expectation</small></figcaption><div class="sq-cv"><canvas id="sq_c_dn"></canvas></div></figure>
  <figure class="sq-fig"><figcaption>Latitude bands in impact windows vs baseline</figcaption><div class="sq-ctl sm"><span class="sq-seg" id="sq_lat"><button data-v="geo">Geographic</button><button data-v="mag">Geomagnetic (dipole)</button></span></div><div class="sq-cv"><canvas id="sq_c_lat"></canvas></div></figure>
 </div>
 <figure class="sq-fig wide sq-mapfig"><figcaption>Where the quakes were: impact windows vs other times <small>orange = within 72 h of a G1+ storm onset · blue = other times · ☀ = point directly under the Sun at the impact moment, line = day/night edge</small></figcaption>
  <div class="sq-ctl sm"><span class="sq-seg" id="sq_mm"><button data-v="both">Both</button><button data-v="in">Impact windows</button><button data-v="out">Other times</button></span>
  <label class="sq-sel">Storm event <select id="sq_ev"><option value="">All events (M6+ only, like for like)</option></select></label><span id="sq_mapnote" class="sq-hint"></span></div>
  <div id="sq_map" class="sq-map" role="region" aria-label="Map of earthquakes in storm impact windows vs other times"></div></figure>
 <details class="sq-det"><summary>All ${d.tests.length} tests, with corrected p-values</summary><div id="sq_tests"></div></details>
 <details class="sq-det"><summary>Rate ratios for every window definition</summary><div id="sq_rates"></div></details>
 <details class="sq-det"><summary>Method, data and caveats</summary><div id="sq_meth"></div></details>`;
 el.querySelectorAll(".sq-seg").forEach(g=>g.addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
  if(g.id==="sq_set"){Q.set=b.dataset.v;renderAll()}else if(g.id==="sq_lat"){Q.lat=b.dataset.v;chartLat()}else if(g.id==="sq_sea"){Q.sea=b.dataset.v;chartSea()}else if(g.id==="sq_mm"){Q.mapMode=b.dataset.v;drawMap()}else if(g.id==="sq_agg"){Q.agg=b.dataset.v;chartTs()}
  segs()}));
 const sel=el.querySelector("#sq_ev");d.events.slice().reverse().forEach(ev=>{const o=document.createElement("option");o.value=ev.i;o.textContent=`${fmtD(ev.t)} — peak Kp ${f2(ev.kp_peak,1)}${ev.g3?" (G3+)":""}`;sel.appendChild(o)});
 sel.addEventListener("change",()=>{Q.ev=sel.value;drawMap()});
 Q.sea=Q.sea||"g1";Q.built=true}
function segs(){const m={sq_set:Q.set,sq_lat:Q.lat,sq_sea:Q.sea,sq_mm:Q.mapMode,sq_agg:Q.agg};for(const id in m){const g=document.getElementById(id);if(g)g.querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.v===m[id]))}}

function base(){if(typeof Chart==="undefined")return null;Chart.defaults.color=COL.mu;Chart.defaults.borderColor=COL.grid;Chart.defaults.font.family="system-ui,-apple-system,Segoe UI,sans-serif";Chart.defaults.font.size=11;return Chart}
function mk(id,cfg){const C=base();if(!C)return;if(Q.charts[id])Q.charts[id].destroy();const cv=document.getElementById(id);if(!cv)return;cfg.options=Object.assign({responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},plugins:{legend:{labels:{boxWidth:12,usePointStyle:true}}}},cfg.options||{});Q.charts[id]=new C(cv,cfg)}

function chartTs(){const S=Q.d.series,s=Q.set,k=Q.agg==="w"?1:4;const q0=s==="raw"?S.quakes_raw:S.quakes_decl;const mx0=S.flares_m.map((v,i)=>v+S.flares_x[i]);
 const grp=(a,f)=>{const o=[];for(let i=0;i+k<=a.length;i+=k)o.push(f(a.slice(i,i+k)));return o};const sum=a=>a.reduce((x,y)=>x+(y||0),0),max=a=>Math.max(...a.map(v=>v??0));
 const q=grp(q0,sum),mx=grp(mx0,sum),kp=grp(S.kp_max,max),lab=grp(S.week_start,a=>new Date(a[0]+"T00:00:00Z").toLocaleDateString("en-US",{timeZone:"UTC",month:"short",year:"numeric"})),u=k===1?"week":"4 weeks";
 mk("sq_c_ts",{data:{labels:lab,datasets:[
  {type:"bar",label:`Quakes M${Q.d.params.m_min}+ (${s}) / ${u}`,data:q,backgroundColor:"rgba(74,163,255,.55)",yAxisID:"y",order:3,barPercentage:1,categoryPercentage:1},
  {type:"line",label:`Max Kp in ${u==="week"?"the week":"4 weeks"}`,data:kp,borderColor:COL.kp,borderWidth:1.2,pointRadius:0,yAxisID:"y1",order:1,tension:.2},
  {type:"line",label:`M+X flares / ${u}`,data:mx,borderColor:COL.fl,borderWidth:1,pointRadius:0,yAxisID:"y2",order:2,tension:.2}]},
  options:{scales:{x:{ticks:{maxTicksLimit:innerWidth<600?5:10,maxRotation:0,autoSkip:true},grid:{display:false}},y:{position:"left",title:{display:true,text:"quakes / "+u},beginAtZero:true},
   y1:{position:"right",min:0,max:9,title:{display:true,text:"Kp"},grid:{display:false}},y2:{display:false,beginAtZero:true}}}})}
function chartSea(){const k=(Q.sea||"g1")+":"+Q.set,A=Q.d.sea[k];
 mk("sq_c_sea",{type:"line",data:{labels:A.days.map(x=>x>0?"+"+x:""+x),datasets:[
  {label:"chance range (high)",data:A.null_hi,borderWidth:0,pointRadius:0,backgroundColor:COL.null,fill:"+1"},
  {label:"chance range (low)",data:A.null_lo,borderWidth:0,pointRadius:0,fill:false},
  {label:`Mean quakes/day around ${A.n_events} onsets`,data:A.mean,borderColor:COL.in,backgroundColor:COL.in,pointRadius:2.5,borderWidth:1.8},
  {label:"Long-run average",data:A.days.map(()=>A.baseline_per_day),borderColor:COL.mu,borderDash:[4,4],pointRadius:0,borderWidth:1}]},
  options:{plugins:{legend:{labels:{filter:i=>!/chance range \(low\)/.test(i.text),boxWidth:12,usePointStyle:true}}},scales:{x:{title:{display:true,text:"days from storm onset"}},y:{title:{display:true,text:"quakes / day"}}}}})}
function chartLag(){const s=Q.set,a=Q.d.lag["kp_max:"+s],b=Q.d.lag["flares_mx:"+s];const n=a.null95_max_abs_r;
 mk("sq_c_lag",{data:{labels:a.lags.map(x=>x+" d"),datasets:[
  {type:"bar",label:"Kp (daily max)",data:a.r,backgroundColor:"rgba(250,173,20,.7)"},{type:"bar",label:"M+X flares (daily)",data:b.r,backgroundColor:"rgba(255,122,69,.7)"},
  {type:"line",label:"chance level (+)",data:a.lags.map(()=>n),borderColor:COL.mu,borderDash:[5,4],pointRadius:0,borderWidth:1},
  {type:"line",label:"chance level (−)",data:a.lags.map(()=>-n),borderColor:COL.mu,borderDash:[5,4],pointRadius:0,borderWidth:1}]},
  options:{plugins:{legend:{labels:{filter:i=>!/\(−\)/.test(i.text),boxWidth:12,usePointStyle:true}}},scales:{y:{suggestedMin:-.08,suggestedMax:.08,title:{display:true,text:"correlation r"}},x:{title:{display:true,text:"solar series leads quakes by"}}}}})}
function chartDn(){const G=Q.d.geo[Q.set],a=G.day_own,b=G.day_impact;
 mk("sq_c_dn",{type:"bar",data:{labels:["Daylight at the quake's own time","On the side facing the Sun at impact"],datasets:[
  {label:"Impact-window quakes",data:[a.in_pct,b.in_pct],backgroundColor:COL.in},{label:"Expected (baseline / shuffled)",data:[a.base_pct,b.null_mean_pct],backgroundColor:"rgba(139,149,163,.6)"}]},
  options:{scales:{y:{min:30,max:70,title:{display:true,text:"% of quakes on the day side"}},x:{ticks:{autoSkip:false,maxRotation:0,callback:function(v){const l=this.getLabelForValue(v);return innerWidth<600?l.split(" ").reduce((a,w)=>{const t=a[a.length-1];if((t+" "+w).length>18)a.push(w);else a[a.length-1]=(t?t+" ":"")+w;return a},[""]):l}}}}}})}
function chartLat(){const G=Q.d.geo[Q.set],B=Q.lat==="geo"?G.geo_lat:G.mag_lat;
 mk("sq_c_lat",{type:"bar",data:{labels:B.bands,datasets:[{label:"Impact-window quakes",data:B.obs_pct,backgroundColor:COL.in},{label:"Baseline (other times)",data:B.base_pct,backgroundColor:"rgba(74,163,255,.6)"}]},
  options:{scales:{y:{beginAtZero:true,title:{display:true,text:"% of quakes"}},x:{title:{display:true,text:(Q.lat==="geo"?"geographic":"geomagnetic")+" latitude (either hemisphere)"}}}}})}

function tables(){const d=Q.d;
 document.getElementById("sq_tests").innerHTML=`<p class="sq-note">p = shuffle (permutation) test unless noted; analytic p assumes independent events and is shown for contrast. Holm controls the chance of even one false positive across all ${d.tests.length} tests; BH q controls the false-discovery rate.</p><div class="sq-tw"><table class="sq-tb"><tr><th>Test</th><th>Set</th><th class=n>p</th><th class=n>analytic p</th><th class=n>Holm p</th><th class=n>BH q</th><th>Verdict</th></tr>${d.tests.map(t=>`<tr class="${t.sig_holm?"sig":t.sig_raw?"nom":""}"><td>${E(t.label)}</td><td>${E(t.set)}</td><td class=n>${pF(t.p)}</td><td class=n>${t.p_analytic==null?"—":pF(t.p_analytic)}</td><td class=n>${pF(t.p_holm)}</td><td class=n>${pF(t.q_bh)}</td><td>${t.sig_holm?"significant":t.sig_raw?"nominal only":"not significant"}</td></tr>`).join("")}</table></div>`;
 const R=d.rate,lab={g1_bins:"Kp ≥ 5− intervals (G1+ storm in progress)",g3_bins:"Kp ≥ 7− intervals (G3+)",g1_onset72:"0–72 h after G1+ onsets",g3_onset72:"0–72 h after G3+ onsets",x_flare72:"0–72 h after X-class flares"};
 let h=`<div class="sq-tw"><table class="sq-tb"><tr><th>Window</th><th>Set</th><th class=n>Quakes in</th><th class=n>Days in</th><th class=n>Rate in /day</th><th class=n>Rate out /day</th><th class=n>Rate ratio (95% CI)</th><th class=n>analytic p</th><th class=n>shuffle p</th><th class=n>chance RR range</th></tr>`;
 for(const k in R)for(const s of["raw","declustered"]){const r=R[k][s];h+=`<tr><td>${lab[k]}</td><td>${s}</td><td class=n>${r.quakes_in.toLocaleString()}</td><td class=n>${f2(r.days_in,1)}</td><td class=n>${f2(r.rate_in_per_day,2)}</td><td class=n>${f2(r.rate_out_per_day,2)}</td><td class=n>${f2(r.rr,3)} (${f2(r.ci_low,2)}–${f2(r.ci_high,2)})</td><td class=n>${pF(r.p_poisson)}</td><td class=n>${pF(r.p_perm)}</td><td class=n>${f2(r.null_rr_2_5,2)}–${f2(r.null_rr_97_5,2)}</td></tr>`}
 document.getElementById("sq_rates").innerHTML=h+`</table></div><p class="sq-note">The analytic CI and p-value treat every quake as independent. Aftershocks aren't, which is why the raw X-flare row can look “significant” analytically yet sits well inside the range chance produces when the same windows are slid to random dates (shuffle p).</p>`;
 const C=d.counts,P=d.params,fs=C.flare_sources.map(x=>`${E(x.source)} (${fmtD(x.first)} – ${fmtD(x.last)})`).join("; ");
 document.getElementById("sq_meth").innerHTML=`<ul>
 <li><b>Storms:</b> GFZ Potsdam 3-hourly Kp, ${C.kp_bins.toLocaleString()} intervals from ${fmtD(C.kp_first)} (definitive through ${fmtD(C.kp_definitive_through)}, nowcast after). G1+ = Kp ≥ 5− (${C.g1_bins} intervals), G3+ = Kp ≥ 7− (${C.g3_bins}). A storm <i>onset</i> is the first G1+ interval after ≥ ${P.quiet_h} h without one: ${C.g1_onsets} G1+ and ${C.g3_onsets} G3+ onsets. We use onsets as the “impact time”, at 3-hour resolution.</li>
 <li><b>Flares:</b> ${C.flares.C.toLocaleString()} C, ${C.flares.M.toLocaleString()} M and ${C.flares.X} X-class flares by peak time. Sources: ${fs}.</li>
 <li><b>Earthquakes:</b> USGS ComCat, ${C.quakes_m45.toLocaleString()} M4.5+ events worldwide (${fmtD(C.quakes_first)} → ${fmtET(C.quakes_last)}). Completeness estimated at M${P.mc_maxc} (max curvature + 0.2), so tests use M${P.m_min}+: ${C.quakes_raw.toLocaleString()} raw, ${C.quakes_decl.toLocaleString()} after Gardner–Knopoff declustering (${C.aftershock_share_pct}% removed as fore/aftershocks).</li>
 <li><b>Tests:</b> Rate ratios with exact Poisson CIs; p-values from ${P.nperm.toLocaleString()} random circular shifts of the window pattern (keeps the storm and flare timing structure); superposed epoch ±10 days; lag correlation of 81-day-detrended daily series against ${P.lag_surrogates} shifted surrogates (max |r| over all 11 lags, so the lag search is corrected); day/night from the solar zenith angle; latitude bands by χ²; geomagnetic latitude from the IGRF-13 dipole pole (${P.dipole_pole[0]}°N, ${Math.abs(P.dipole_pole[1])}°W, approximate); magnitude shift by KS test and Aki b-value (MLE). Holm and Benjamini–Hochberg corrections across all ${d.tests.length} tests. Random seed ${P.seed}.</li>
 <li><b>Caveats:</b> Correlation isn't causation, and no correlation here doesn't prove that no effect exists. It means none is detectable at this scale. Storm onsets come from Kp, not from spacecraft CME arrival lists. NASA's DONKI service wasn't reachable from our server, and the ISGI sudden-commencement list needs a registered download. The flare lists switch from GOES-15 reports to GOES-R summaries in Feb 2017, which changes detection thresholds, so flare <i>counts</i> aren't perfectly comparable across that date. Recent Kp values are preliminary, and recent USGS events may still be revised. Declustering windows are a convention, not ground truth.</li></ul>
 <p class="sq-credit">Data: <a href="https://kp.gfz.de/" target="_blank" rel="noopener noreferrer">GFZ Helmholtz Centre Potsdam (Kp)</a> · <a href="https://www.ncei.noaa.gov/" target="_blank" rel="noopener noreferrer">NOAA NCEI</a> &amp; <a href="https://www.swpc.noaa.gov/" target="_blank" rel="noopener noreferrer">NOAA SWPC</a> (GOES X-ray flares) · <a href="https://earthquake.usgs.gov/fdsnws/event/1/" target="_blank" rel="noopener noreferrer">USGS ComCat</a> (earthquakes). Reproducible: <code>tools/solar_quake_build.py</code>. blackout.network</p>`}

// ---- map
function terminator(slat,slon){const pts=[];const t=Math.tan(slat*Math.PI/180)||1e-6;for(let lo=-180;lo<=180;lo+=2){const la=Math.atan(-Math.cos((lo-slon)*Math.PI/180)/t)*180/Math.PI;pts.push([la,lo])}return pts}
function ensureMap(){if(Q.map||typeof L==="undefined")return!!Q.map;const el=document.getElementById("sq_map");if(!el)return false;
 const nar=el.clientWidth<640;Q.map=L.map(el,{worldCopyJump:true,minZoom:0,maxZoom:8,zoomSnap:.5}).setView(nar?[15,170]:[15,150],nar?0.5:1.5);
 // t252: basemap only via the shared bnBaseLayer() in dashboard.html (OSM standard/HOT tiles block blackout.network); no direct tile servers here.
 if(window.bnBaseLayer)bnBaseLayer(Q.map,{maxZoom:8});
 Q.layer=L.layerGroup().addTo(Q.map);return true}
function drawMap(){if(!Q.m){if(!Q.mload){Q.mload=1;getJSON("api/solar_quake/map").then(m=>{Q.m=m;drawMap()}).catch(()=>{Q.mload=0;const n=document.getElementById("sq_mapnote");if(n)n.textContent="Map data couldn't load. Reload the page to try again."})}return}
 if(!ensureMap())return;Q.layer.clearLayers();const m=Q.m,ev=Q.ev===""?null:+Q.ev,decl=Q.set==="declustered";
 const pt=(p,col,inw)=>{const r=Math.max(2.5,(p[2]-4.5)*(ev==null?2.2:3.2));return L.circleMarker([p[0],p[1]<-30?p[1]+360:p[1]],{radius:r,color:col,weight:1,fillColor:col,fillOpacity:inw?.75:.45,opacity:.9}).bindPopup(`<b>M${p[2].toFixed(1)}</b> · ${E(fmtET(p[5]))}<br>${inw?"Within 72 h of storm onset "+E(fmtD(m.events[p[3]].t)):"Outside storm impact windows"}${p[4]?"":"<br><i>flagged as fore/aftershock</i>"}`)};
 let nIn=0,nOut=0;
 const inPts=m.impact.filter(p=>(!decl||p[4])&&(ev==null?p[2]>=6:p[3]===ev));
 const outPts=ev==null?m.other_m6.filter(p=>!decl||p[4]):[];
 if(Q.mapMode!=="in")outPts.forEach(p=>{pt(p,COL.out,false).addTo(Q.layer);nOut++});
 if(Q.mapMode!=="out")inPts.forEach(p=>{pt(p,COL.in,true).addTo(Q.layer);nIn++});
 const note=document.getElementById("sq_mapnote");
 if(ev!=null){const e=m.events[ev];L.marker([e.ss_lat,e.ss_lon],{icon:L.divIcon({className:"sq-sun",html:"☀",iconSize:[26,26]}),title:"Subsolar point at impact"}).bindPopup(`Subsolar point at onset ${E(fmtET(e.t))}<br>${e.ss_lat.toFixed(1)}°, ${e.ss_lon.toFixed(1)}° · peak Kp ${e.kp_peak}`).addTo(Q.layer);
  const tp=terminator(e.ss_lat,e.ss_lon);[-360,0,360].forEach(o=>L.polyline(tp.map(([a,b])=>[a,b+o]),{color:"#ffd666",weight:1.4,dashArray:"5 5",opacity:.85,interactive:false}).addTo(Q.layer));
  Q.map.setView([Math.max(-30,Math.min(30,e.ss_lat)),e.ss_lon],Q.map.getZoom(),{animate:false});
  if(note)note.textContent=`${nIn} M${Q.d.params.m_min}+ ${decl?"main shocks":"quakes"} in the 72 h after the ${fmtET(e.t)} onset`}
 else if(note)note.textContent=`${nIn.toLocaleString()} impact-window vs ${nOut.toLocaleString()} other-time M6+ ${decl?"main shocks":"quakes"}`;
 // t308: Pacific-centred continuous longitudes (Americas shifted +360) and fit to data so Chile/Mexico stay on screen on phones
 if(ev==null&&!Q.fitted){const b=L.latLngBounds([]);Q.layer.eachLayer(l=>{if(l.getLatLng)b.extend(l.getLatLng())});if(b.isValid()){Q.fitted=1;Q.map.invalidateSize();Q.map.fitBounds(b,{padding:[8,8],animate:false})}}
 setTimeout(()=>Q.map&&Q.map.invalidateSize(),60)}

function renderAll(){document.getElementById("sq_cards").innerHTML=cards();chartTs();chartSea();chartLag();chartDn();chartLat();tables();segs();
 const mel=document.getElementById("sq_map");if(mel&&"IntersectionObserver"in window&&!Q.mapIO){Q.mapIO=new IntersectionObserver(es=>{if(es.some(x=>x.isIntersecting)){Q.mapIO.disconnect();drawMap()}},{rootMargin:"300px"});Q.mapIO.observe(mel)}else if(Q.m)drawMap()}
function render(){skeleton();renderAll()}

function check(){if(visible())boot()}
new MutationObserver(check).observe(TAB,{attributes:true,attributeFilter:["style","class"]});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",check);else check();
addEventListener("resize",()=>{if(Q.map)Q.map.invalidateSize()});
})();
