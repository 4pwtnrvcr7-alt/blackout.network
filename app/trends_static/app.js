// ---- Trends tab (served by trends.py; read-only charts of blackout.db). Reuses the dashboard's Chart.js; all times shown in ET. ----
(()=>{"use strict";
const M=document.getElementById("tab-trends");if(!M)return;
const E=s=>(typeof esc=="function"?esc:(x=>String(x)))(s==null?"":String(s));
const TZ="America/New_York";
const CATS=[["war/conflict","violence","#ff4d4f"],["political","unrest","#b37feb"],["natural disaster","infra","#fadb14"],["disease","disease","#fa8c16"],["cyber","cyber","#4aa3ff"],
 ["space weather","nuclear","#36cfc9"],["financial",null,"#52c41a"],["ufo/uap",null,"#f759ab"],["spiritual/religious",null,"#d3adf7"],["other",null,"#8a93a6"]];
const cc=c=>{const r=CATS.find(x=>x[0]==c);if(!r)return"#8a93a6";return r[1]&&typeof catColor=="function"?catColor(r[1],r[2]):r[2]};
const LS=(k,d)=>{try{return localStorage.getItem(k)||d}catch(_){return d}},SS=(k,v)=>{try{localStorage.setItem(k,v)}catch(_){}};
const T={rng:LS("tr_rng","7d"),vmode:LS("tr_vmode","bars"),bk:LS("tr_bk","6h"),supp:LS("tr_supp","0")=="1",d:null,charts:{},busy:false,stale:true,last:0};
if(!["24h","7d","30d"].includes(T.rng))T.rng="7d";if(!["1h","6h","day"].includes(T.bk))T.bk="6h";if(!["bars","lines"].includes(T.vmode))T.vmode="bars";

// ---------- tab button + deep link (#trends), placed in the Monitor group after the other Monitor add-ons ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="trends"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="trends";tb.textContent="📈 Trends";nav.appendChild(tb)}
const after=nav&&(nav.querySelector('button[data-tab="weather"]')||nav.querySelector('button[data-tab="politics"]')||nav.querySelector('button[data-tab="heatmap"]')||nav.querySelector('button[data-tab="solar_seismic"]'));
if(after&&tb)after.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.trends="trends";HASHTAB.trends="trends"}}catch(_){}

// ---------- skeleton ----------
const seg=(id,opts,cur)=>`<div class=tr-seg id=${id} role=group>${opts.map(([v,l,t])=>`<button type=button data-v="${v}"${t?` title="${E(t)}"`:""} class="${v==cur?"on":""}">${l}</button>`).join("")}</div>`;
const app=document.getElementById("tr_app");
app.innerHTML=`<div class=tr-bar><span class=tr-lbl>Range</span>${seg("tr_rng",[["24h","24 h"],["7d","7 days"],["30d","30 days"]],T.rng)}
 <label class=sw title="Rank 0–1 items the scanner stores but keeps off The Wire and the Watchlist (local trivia, no threat signal)"><input type=checkbox id=tr_supp${T.supp?" checked":""}> include suppressed items</label>
 <span class=meta id=tr_msg></span></div>
<div id=tr_cov class=tr-cov>Loading history…</div>
<div id=tr_kpis class=tr-kpis></div>
<div class=tr-grid>
 <div class="tr-card wide"><h3>Alert volume by category ${seg("tr_vmode",[["bars","Stacked bars"],["lines","Hourly lines"]],T.vmode)}</h3>
  <div class=tr-sub id=tr_vsub></div><div class=tr-cv><canvas id=tr_vol aria-label="Alert volume by category"></canvas></div><div class=tr-tot id=tr_vtot></div></div>
 <div class=tr-card><h3>Severity trend ${seg("tr_bk",[["1h","1 h"],["6h","6 h"],["day","Day"]],T.bk)}</h3>
  <div class=tr-sub>The Wire only: average and maximum 0–100 score of stories first seen in each period, plus how many reached rank 7+.</div><div class=tr-cv><canvas id=tr_sev aria-label="Severity trend"></canvas></div></div>
 <div class=tr-card><h3>The Wire vs Watchlist</h3>
  <div class=tr-sub>New stories per period: confirmed / official (The Wire) vs single-source, low-confidence (Watchlist).</div><div class=tr-cv><canvas id=tr_wl aria-label="Wire versus Watchlist"></canvas></div></div>
 <div class="tr-card wide"><h3>Scan volume &amp; source health</h3>
  <div class=tr-sub>One point per scanner pass: new items it added, items it fetched, and how many sources failed.</div><div class=tr-cv><canvas id=tr_scan aria-label="Scan volume and source health"></canvas></div><div class=tr-tot id=tr_stot></div></div>
</div>`;
const $$=id=>document.getElementById(id);

if(typeof hwAttach=="function"){
 try{if(typeof HW_ICONS=="object"&&typeof hwI=="function"&&!HW_ICONS.trends)HW_ICONS.trends=hwI(`<path d="M20 98 h160 M20 98 V12"/><rect x="32" y="70" width="14" height="28"/><rect x="62" y="58" width="14" height="40"/><rect x="92" y="76" width="14" height="22"/><rect x="122" y="50" width="14" height="48"/><rect x="152" y="40" width="14" height="58"/><path d="M30 60 L68 44 L98 56 L130 30 L170 20" stroke="#ff4d4f"/>`)}catch(_){}
 hwAttach(M.querySelector("#tr_top h2"),"trends",()=>"Everything here is counted from the scanner's own database (blackout.db), opened read-only. A 'story' is one cluster of related reports; each is counted once, in the hour the scanner first saw it, under its category and its current list (The Wire, Watchlist or suppressed). Severity uses each story's current 0–100 score and 0–10 rank. The server adds things up by hour; your browser groups the hours into 6-hour blocks or days on Eastern Time. Scan volume is one point per scanner pass. The charts redraw by themselves after every scan. If the database holds less history than the range you pick, the charts show all of it and say so.")}

// ---------- time helpers (ET) ----------
const fP=new Intl.DateTimeFormat("en-US",{timeZone:TZ,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"});
const parts=d=>{const o={};fP.formatToParts(d).forEach(p=>o[p.type]=p.value);return o};
const hDate=h=>new Date(h+":00:00Z");
const fmtD=(d,o)=>d.toLocaleString("en-US",Object.assign({timeZone:TZ},o));
const tzName=d=>(new Intl.DateTimeFormat("en-US",{timeZone:TZ,timeZoneName:"short"}).formatToParts(d).find(p=>p.type=="timeZoneName")||{}).value||"ET";
const full=d=>fmtD(d,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" "+tzName(d);
function bucketKey(h,bk){const d=hDate(h),p=parts(d);const day=`${p.year}-${p.month}-${p.day}`;if(bk=="day")return day;if(bk=="6h")return day+"T"+String(Math.floor(+p.hour/6)*6).padStart(2,"0");return h}
function bucketLabels(key,bk,first){ // short axis label + full tooltip title, both ET
 if(bk=="day"){const d=new Date(key+"T12:00:00Z");const s=d.toLocaleDateString("en-US",{timeZone:"UTC",weekday:"short",month:"short",day:"numeric"});return[s,s+" (ET day)"]}
 if(bk=="6h"){const[dd,hh]=key.split("T");const d=new Date(dd+"T12:00:00Z"),h=+hh,ap=x=>x==0||x==24?"12 AM":x==12?"12 PM":x<12?x+" AM":(x-12)+" PM";
  const day=d.toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric"});return[`${day} ${ap(h).replace(":00","")}`,`${day}, ${ap(h)} – ${ap(h+6)} ET`]}
 const d=hDate(key);return[fmtD(d,{month:"short",day:"numeric",hour:"numeric"}),full(d).replace(":00 "," ")+" (hour starting)"]}
function group(hours,bk){const keys=[],idx=[],at={};hours.forEach((h,i)=>{const k=bucketKey(h,bk);if(!(k in at)){at[k]=keys.length;keys.push(k)}idx[i]=at[k]});return{keys,idx}}
const sumBy=(arr,g)=>{const o=new Array(g.keys.length).fill(0);arr.forEach((v,i)=>{if(g.idx[i]!=null)o[g.idx[i]]+=v||0});return o};

// ---------- chart helpers (same look as the Wire's charts) ----------
const AX=()=>({ticks:{color:"#999",maxRotation:0,autoSkip:true,autoSkipPadding:10},grid:{color:"#222"}});
const ttl=(t,c)=>({display:true,text:t,color:c||"#8b95a3",font:{size:11}});
function base(xT,yT,extra){return Object.assign({responsive:true,maintainAspectRatio:false,animation:{duration:250},interaction:{mode:"index",intersect:false},
 plugins:{legend:{labels:{color:"#ccc",boxWidth:10,font:{size:11}}},tooltip:{backgroundColor:"#0c0f12ee",borderColor:"#2f3742",borderWidth:1,titleColor:"#e6e9ee",bodyColor:"#c9d0d9"}},
 scales:{x:Object.assign(AX(),{title:ttl(xT)}),y:Object.assign(AX(),{beginAtZero:true,title:ttl(yT)})}},extra||{})}
function draw(id,cfg){const old=T.charts[id];if(old){old.destroy();delete T.charts[id]}
 const cv=$$(id);if(!cv)return;if(typeof Chart=="undefined"){cv.parentElement.innerHTML='<div class=tr-err>Chart library did not load (it comes from the same place as the Wire charts). Reload the page to try again.</div>';return}
 T.charts[id]=new Chart(cv,cfg)}

// ---------- render ----------
function render(){const D=T.d;if(!D)return;
 // trim hours before the scanner's history begins so empty pre-history never looks like "zero alerts"
 let from=0;if(D.history_since){const hs=D.history_since.slice(0,13);const i=D.hours.indexOf(hs);if(i>0)from=i;else if(D.hours[0]<hs)from=D.hours.findIndex(h=>h>=hs)}
 if(from<0)from=0;
 const H=D.hours.slice(from),cut=a=>a.slice(from);
 const first=D.history_since?new Date(D.history_since):null,days=(D.history_hours/24);
 const rl={"24h":"24 hours","7d":"7 days","30d":"30 days"}[T.rng];
 const cov=$$("tr_cov");
 if(D.partial){cov.className="tr-cov";cov.innerHTML=`<b>${rl} requested, ${days<1?Math.round(D.history_hours)+" hours":days.toFixed(1)+" days"} of history exist.</b> The scanner's database starts ${E(first?full(first):"—")}, so these charts show everything it has. ${T.rng=="30d"?"The 30-day view fills in as the scanner keeps running.":""}`}
 else{cov.className="tr-cov full";cov.innerHTML=`Showing the last ${rl}: ${E(full(hDate(H[0])))} to now · ${D.scans.length} scans · last scan ${E(D.last_scan_finished?full(new Date(D.last_scan_finished)):"—")}`}
 if(D.partial&&D.first_scan&&H.length&&H[0]<=D.first_scan.slice(0,13))cov.innerHTML+=` The first scan (${E(full(new Date(D.first_scan)))}) took in the sources' existing backlog, so the first hours and day read high.`;
 if(D.partial)cov.innerHTML+=` · ${D.scans.length} scans · last scan ${E(D.last_scan_finished?full(new Date(D.last_scan_finished)):"—")}`;
 // KPIs
 const BL=D.by_list,s=a=>cut(a).reduce((x,y)=>x+y,0);
 const wire=s(BL.wire),watch=s(BL.watch),supp=s(BL.supp),r7=s(D.severity.r7_all),newItems=D.scans.reduce((a,x)=>a+(x.new_items||0),0);
 const mx=Math.max(0,...cut(D.severity.max).filter(v=>v!=null));
 $$("tr_kpis").innerHTML=[[wire+watch+(T.supp?supp:0),"stories"+(T.supp?" (incl. suppressed)":" on The Wire + Watchlist")],[wire,"on The Wire"],[watch,"on the Watchlist"],[r7,"rank 7+","hi"],[mx||"—","top Wire score"],[D.scans.length,"scans"],[newItems.toLocaleString(),"new items scanned"]]
  .map(([v,l,c])=>`<div class="tr-kpi ${c||""}"><b>${E(typeof v=="number"?v.toLocaleString():v)}</b><span>${E(l)}</span></div>`).join("");
 // (a) volume by category
 const vb=T.vmode=="lines"?"1h":(T.rng=="24h"?"1h":"day"),gv=group(H,vb),labs=gv.keys.map(k=>bucketLabels(k,vb));
 const cats=Object.keys(D.categories).sort((a,b)=>{const ia=CATS.findIndex(x=>x[0]==a),ib=CATS.findIndex(x=>x[0]==b);return(ia<0?99:ia)-(ib<0?99:ib)});
 const series=cats.map(c=>{const v=cut(D.categories[c].vis),sp=cut(D.categories[c].supp);return{c,data:sumBy(T.supp?v.map((x,i)=>x+sp[i]):v,gv)}}).filter(x=>x.data.some(Boolean));
 $$("tr_vsub").textContent=(T.vmode=="lines"?"New stories per hour, one line per category":vb=="day"?"New stories per day (Eastern Time days), stacked by category":"New stories per hour, stacked by category")+(T.supp?", including suppressed rank 0–1 items.":" on The Wire and the Watchlist.");
 const vt={callbacks:{title:it=>it.length?labs[it[0].dataIndex][1]:"",footer:it=>T.vmode=="bars"?"Total: "+it.reduce((a,x)=>a+x.parsed.y,0):""}};
 draw("tr_vol",T.vmode=="lines"?
  {type:"line",data:{labels:labs.map(l=>l[0]),datasets:series.map(x=>({label:x.c,data:x.data,borderColor:cc(x.c),backgroundColor:cc(x.c),borderWidth:1.6,pointRadius:0,pointHoverRadius:3,tension:.25}))},
   options:base("Hour (ET)","New stories per hour",{plugins:Object.assign({},base().plugins,{tooltip:Object.assign({},base().plugins.tooltip,vt,{filter:i=>i.parsed.y>0})})})}:
  {type:"bar",data:{labels:labs.map(l=>l[0]),datasets:series.map(x=>({label:x.c,data:x.data,backgroundColor:cc(x.c),borderWidth:0,maxBarThickness:46}))},
   options:(()=>{const o=base(vb=="day"?"Day (ET)":"Hour (ET)",vb=="day"?"New stories per day":"New stories per hour");o.scales.x.stacked=true;o.scales.y.stacked=true;o.plugins.tooltip=Object.assign({},o.plugins.tooltip,vt,{filter:i=>i.parsed.y>0});return o})()});
 const tots=series.map(x=>[x.c,x.data.reduce((a,b)=>a+b,0)]).sort((a,b)=>b[1]-a[1]);
 $$("tr_vtot").innerHTML=`<span>Totals for the period:</span>`+tots.map(([c,n])=>`<span><i style="background:${cc(c)}"></i>${E(c)} <b>${n.toLocaleString()}</b></span>`).join("");
 // (b) severity
 const gs=group(H,T.bk),sl=gs.keys.map(k=>bucketLabels(k,T.bk)),SV=D.severity;
 const ssum=sumBy(cut(SV.sum),gs),sn=sumBy(cut(SV.n),gs),r7w=sumBy(cut(SV.r7),gs),smax=new Array(gs.keys.length).fill(null);
 cut(SV.max).forEach((v,i)=>{if(v!=null){const j=gs.idx[i];smax[j]=Math.max(smax[j]??0,v)}});
 const avg=ssum.map((v,i)=>sn[i]?Math.round(v/sn[i]*10)/10:null);
 const bkT={"1h":"Hour (ET)","6h":"6-hour block (ET)","day":"Day (ET)"}[T.bk];
 draw("tr_sev",{data:{labels:sl.map(l=>l[0]),datasets:[
  {type:"line",label:"max score",data:smax,borderColor:"#ff4d4f",backgroundColor:"#ff4d4f",pointRadius:T.bk=="1h"?0:2,pointHoverRadius:4,borderWidth:1.8,spanGaps:true,yAxisID:"y",tension:.2},
  {type:"line",label:"avg score",data:avg,borderColor:"#faad14",backgroundColor:"#faad14",pointRadius:T.bk=="1h"?0:2,pointHoverRadius:4,borderWidth:1.8,spanGaps:true,yAxisID:"y",tension:.2},
  {type:"line",label:"high threshold (60)",data:sl.map(()=>D.high_threshold),borderColor:"#ff4d4f66",borderDash:[5,5],pointRadius:0,borderWidth:1,yAxisID:"y"},
  {type:"bar",label:"# rank 7+",data:r7w,backgroundColor:"#4aa3ffaa",yAxisID:"y2",maxBarThickness:30}]},
  options:(()=>{const o=base(bkT,"Score (0–100)");o.scales.y.max=100;o.scales.y2={position:"right",beginAtZero:true,ticks:{color:"#4aa3ff",precision:0},grid:{display:false},title:ttl("Rank 7+ stories","#4aa3ff")};
   o.plugins.tooltip.callbacks={title:it=>it.length?sl[it[0].dataIndex][1]:"",footer:it=>it.length?`${sn[it[0].dataIndex]} Wire stor${sn[it[0].dataIndex]==1?"y":"ies"} in this period`:""};return o})()});
 // (c) Wire vs Watchlist
 const w1=sumBy(cut(BL.wire),gs),w2=sumBy(cut(BL.watch),gs),w3=sumBy(cut(BL.supp),gs);
 const wds=[{label:"The Wire",data:w1,borderColor:"#4aa3ff",backgroundColor:"#4aa3ff33",fill:true},{label:"Watchlist",data:w2,borderColor:"#faad14",backgroundColor:"#faad1422",fill:true}];
 if(T.supp)wds.push({label:"suppressed (rank 0–1)",data:w3,borderColor:"#8a93a6",borderDash:[4,4],backgroundColor:"#8a93a6",fill:false});
 draw("tr_wl",{type:"line",data:{labels:sl.map(l=>l[0]),datasets:wds.map(d=>Object.assign({pointRadius:T.bk=="1h"?0:2,pointHoverRadius:4,borderWidth:1.8,tension:.25},d))},
  options:(()=>{const o=base(bkT,"New stories");o.scales.y.ticks.precision=0;o.plugins.tooltip.callbacks={title:it=>it.length?sl[it[0].dataIndex][1]:"",footer:it=>{if(!it.length)return"";const i=it[0].dataIndex,t=w1[i]+w2[i];return t?`Wire share ${Math.round(100*w1[i]/t)}%`:""}};return o})()});
 // (d) scans
 const SC=D.scans,scl=SC.map(x=>new Date(x.finished||x.started));
 draw("tr_scan",{data:{labels:scl.map(d=>fmtD(d,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})),datasets:[
  {type:"line",label:"new items",data:SC.map(x=>x.new_items),borderColor:"#ff4d4f",backgroundColor:"#ff4d4f",pointRadius:2.5,pointHoverRadius:5,borderWidth:1.8,yAxisID:"y",tension:.2},
  {type:"line",label:"items fetched",data:SC.map(x=>x.fetched),borderColor:"#36cfc9",backgroundColor:"#36cfc9",pointRadius:0,pointHoverRadius:4,borderWidth:1.4,borderDash:[3,3],yAxisID:"y3"},
  {type:"bar",label:"failed sources",data:SC.map(x=>x.failed_sources),backgroundColor:"#b37febaa",yAxisID:"y2",maxBarThickness:14}]},
  options:(()=>{const o=base("Scan finished (ET)","New items per scan");o.scales.y.ticks.color="#ff7875";
   o.scales.y2={position:"right",beginAtZero:true,suggestedMax:5,ticks:{color:"#b37feb",precision:0},grid:{display:false},title:ttl("Failed sources","#b37feb")};
   o.scales.y3={display:innerWidth>600,position:"right",beginAtZero:true,ticks:{color:"#36cfc9"},grid:{display:false},title:ttl("Items fetched","#36cfc9")};
   o.plugins.tooltip.callbacks={title:it=>{if(!it.length)return"";const x=SC[it[0].dataIndex];return`Scan #${x.id} · ${full(scl[it[0].dataIndex])}`},
    footer:it=>{if(!it.length)return"";const x=SC[it[0].dataIndex];return`${x.trigger} · ${x.ok_sources} sources OK, ${x.failed_sources} failed${x.err?" · scan reported an error":""}`}};return o})()});
 const avgNew=SC.length?Math.round(newItems/SC.length):0,maxS=SC.reduce((a,x)=>x.new_items>(a?a.new_items:-1)?x:a,null);
 $$("tr_stot").innerHTML=SC.length?`<span>Average <b>${avgNew}</b> new items per scan</span><span>Busiest: <b>${maxS.new_items}</b> at ${E(full(new Date(maxS.finished||maxS.started)))}</span><span>Sources now: <b>${D.sources_ok}</b> OK, <b>${D.sources_failed}</b> failing${D.sources_total-D.sources_ok-D.sources_failed?`, ${D.sources_total-D.sources_ok-D.sources_failed} switched off`:""}</span><span>Raw reports in period: <b>${D.raw_items.toLocaleString()}</b></span>`:"<span>No scans in this period.</span>";
 $$("tr_msg").textContent=`Updated ${full(new Date(D.generated))}${D.cached?" (cached)":""}`}

// ---------- data ----------
const vis=()=>M.style.display!="none";
async function load(){if(T.busy)return;T.busy=true;try{const r=await fetch("api/trends?range="+encodeURIComponent(T.rng),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);
 T.d=j;T.stale=false;T.last=Date.now();render()}catch(e){$$("tr_msg").innerHTML=`<span class=tr-err>Couldn't load the history: ${E(e.message||e)}</span>`}finally{T.busy=false}}
const segOn=(id,v)=>$$(id).querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.v==v));
$$("tr_rng").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b||b.dataset.v==T.rng)return;T.rng=b.dataset.v;SS("tr_rng",T.rng);segOn("tr_rng",T.rng);
 if(T.rng=="24h"&&T.bk=="day"){T.bk="6h";segOn("tr_bk",T.bk)}load()};
$$("tr_vmode").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b)return;T.vmode=b.dataset.v;SS("tr_vmode",T.vmode);segOn("tr_vmode",T.vmode);render()};
$$("tr_bk").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b)return;T.bk=b.dataset.v;SS("tr_bk",T.bk);segOn("tr_bk",T.bk);render()};
$$("tr_supp").onchange=e=>{T.supp=e.target.checked;SS("tr_supp",T.supp?"1":"0");render()};
const rb=$$("tr_ref");if(rb)rb.onclick=async e=>{e.stopPropagation();rb.disabled=true;rb.textContent="scanning…";try{if($("refresh")&&$("refresh").onclick)await $("refresh").onclick()}catch(_){}await load();rb.textContent="⟳ Refresh";rb.disabled=false};
if(nav)nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="trends")setTimeout(()=>{if(T.stale||!T.d||Date.now()-T.last>120000)load();else Object.values(T.charts).forEach(c=>c.resize())},30)});
// auto-refresh: every scanner pass pushes a "scan" event; redraw if the tab is open, otherwise refresh on next open
let st=0;const hook=()=>{if(typeof LV=="object"&&LV&&LV.es){LV.es.addEventListener("scan",()=>{T.stale=true;clearTimeout(st);st=setTimeout(()=>{if(vis())load()},3000)});return true}return false};if(!hook())setTimeout(hook,2000);
setInterval(()=>{if(vis())load();else T.stale=true},300000);
if(vis())load();
})();
