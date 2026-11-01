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
const RNG=[["24h","24 h"],["7d","7 days"],["30d","30 days"],["90d","90 days"],["1y","1 year"],["all","All"]];
if(!RNG.some(r=>r[0]==T.rng))T.rng="7d";if(!["1h","6h","day","week"].includes(T.bk))T.bk="6h";if(!["bars","lines"].includes(T.vmode))T.vmode="bars";

// ---------- tab button + deep link (#trends), placed in the Monitor group after the other Monitor add-ons ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="trends"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="trends";tb.textContent="📈 Trends";nav.appendChild(tb)}
const after=nav&&(nav.querySelector('button[data-tab="weather"]')||nav.querySelector('button[data-tab="politics"]')||nav.querySelector('button[data-tab="heatmap"]')||nav.querySelector('button[data-tab="solar_seismic"]'));
if(after&&tb)after.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.trends="trends";HASHTAB.trends="trends"}}catch(_){}

// ---------- skeleton ----------
const seg=(id,opts,cur)=>`<div class=tr-seg id=${id} role=group>${opts.map(([v,l,t])=>`<button type=button data-v="${v}"${t?` title="${E(t)}"`:""} class="${v==cur?"on":""}">${l}</button>`).join("")}</div>`;
const app=document.getElementById("tr_app");
app.innerHTML=`<div class=tr-bar><span class=tr-lbl>Range</span>${seg("tr_rng",RNG,T.rng)}
 <label class=sw title="Rank 0–1 items the scanner stores but keeps off The Wire and the Watchlist (local trivia, no threat signal)"><input type=checkbox id=tr_supp${T.supp?" checked":""}> include suppressed items</label>
 <span class=meta id=tr_msg></span></div>
<div id=tr_cov class=tr-cov>Loading history…</div>
<details id=tr_covd class=tr-covd><summary>Data coverage: earliest date per graph, category and source</summary><div id=tr_covt></div></details>
<div id=tr_kpis class=tr-kpis></div>
<div class=tr-grid>
 <div class="tr-card wide"><h3>Alert volume by category ${seg("tr_vmode",[["bars","Stacked bars"],["lines","Hourly lines"]],T.vmode)}</h3>
  <div class=tr-sub id=tr_vsub></div><div class=tr-from id=tr_f_vol></div><div class=tr-cv><canvas id=tr_vol aria-label="Alert volume by category"></canvas></div><div class=tr-tot id=tr_vtot></div></div>
 <div class=tr-card><h3>Severity trend ${seg("tr_bk",[["1h","1 h"],["6h","6 h"],["day","Day"],["week","Week"]],T.bk)}</h3>
  <div class=tr-sub>The Wire only: average and maximum 0–100 score of stories first seen in each period, plus how many reached rank 7+.</div><div class=tr-from id=tr_f_sev></div><div class=tr-cv><canvas id=tr_sev aria-label="Severity trend"></canvas></div></div>
 <div class=tr-card><h3>The Wire vs Watchlist</h3>
  <div class=tr-sub>New stories per period: confirmed / official (The Wire) vs single-source, low-confidence (Watchlist).</div><div class=tr-from id=tr_f_wl></div><div class=tr-cv><canvas id=tr_wl aria-label="Wire versus Watchlist"></canvas></div></div>
 <div class="tr-card wide"><h3>Scan volume &amp; source health</h3>
  <div class=tr-sub>One point per scanner pass: new items it added, items it fetched, and how many sources failed.</div><div class=tr-from id=tr_f_scan></div><div class=tr-cv><canvas id=tr_scan aria-label="Scan volume and source health"></canvas></div><div class=tr-tot id=tr_stot></div></div>
 <div class="tr-card wide"><h3>Geographic heat map</h3>
  <div class=tr-sub>Where located stories in the selected range happened (1° grid; brighter = more stories). Includes archive backfill.</div><div class=tr-from id=tr_f_geo></div>
  <div id=tr_geo class=tr-geo role=img aria-label="Geographic heat map of stories"></div><div class=tr-tot id=tr_gtot></div></div>
</div>
<section class="tr-card tr-stream" id=tr_stream_card><h3>Alert stream <span class=tr-sub style="margin:0;text-transform:none;letter-spacing:0">newest first · keeps loading as you scroll</span>
 <select id=tr_scat aria-label="Stream category"><option value="">All categories</option>${CATS.map(c=>`<option value="${E(c[0])}">${E(c[0])}</option>`).join("")}</select>
 <select id=tr_sorg aria-label="Stream origin"><option value="">Live + archive</option><option value="live">Live scanner only</option><option value="archive">Archive backfill only</option></select></h3>
 <div class=tr-sub>Every story the scanner put on The Wire or the Watchlist, then older stories from the archive backfill (marked <span class="tr-org a">archive</span>). Times are Eastern.</div>
 <ol id=tr_slist class=tr-slist></ol><div id=tr_sstate class=tr-sstate>Loading…</div><div id=tr_ssent class=tr-ssent aria-hidden=true></div></section>`;
const $$=id=>document.getElementById(id);
const vis=()=>M.style.display!="none";

if(typeof hwAttach=="function"){
 try{if(typeof HW_ICONS=="object"&&typeof hwI=="function"&&!HW_ICONS.trends)HW_ICONS.trends=hwI(`<path d="M20 98 h160 M20 98 V12"/><rect x="32" y="70" width="14" height="28"/><rect x="62" y="58" width="14" height="40"/><rect x="92" y="76" width="14" height="22"/><rect x="122" y="50" width="14" height="48"/><rect x="152" y="40" width="14" height="58"/><path d="M30 60 L68 44 L98 56 L130 30 L170 20" stroke="#ff4d4f"/>`)}catch(_){}
 hwAttach(M.querySelector("#tr_top h2"),"trends",()=>"Everything here is counted from the scanner's own database (blackout.db), opened read-only. A 'story' is one cluster of related reports; each is counted once, in the hour the scanner first saw it, under its category and its current list (The Wire, Watchlist or suppressed). Severity uses each story's current 0–100 score and 0–10 rank. The server adds things up by hour; your browser groups the hours into 6-hour blocks or days on Eastern Time. Scan volume is one point per scanner pass. The charts redraw by themselves after every scan. Before the live scanner started, the charts use an archive backfill: real past items from public archives (USGS, GDACS, NASA EONET, WHO, CISA, GFZ Kp and others), clustered and scored with the scanner's own rules and marked 'archive'. They never appear on The Wire, the alert bar or in alerts. Gaps stay gaps; nothing is estimated. 'Data coverage' lists the earliest date per graph, category and source. The alert stream at the bottom keeps loading older stories as you scroll.")}

// ---------- time helpers (ET) ----------
const fP=new Intl.DateTimeFormat("en-US",{timeZone:TZ,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"});
const parts=d=>{const o={};fP.formatToParts(d).forEach(p=>o[p.type]=p.value);return o};
const hDate=h=>new Date(h+":00:00Z");
const fmtD=(d,o)=>d.toLocaleString("en-US",Object.assign({timeZone:TZ},o));
const tzName=d=>(new Intl.DateTimeFormat("en-US",{timeZone:TZ,timeZoneName:"short"}).formatToParts(d).find(p=>p.type=="timeZoneName")||{}).value||"ET";
const full=d=>fmtD(d,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" "+tzName(d);
const DAYK=h=>h.length==10;
function weekKey(day){const d=new Date(day+"T12:00:00Z");const w=(d.getUTCDay()+6)%7;d.setUTCDate(d.getUTCDate()-w);return"W"+d.toISOString().slice(0,10)}
function bucketKey(h,bk){if(DAYK(h))return bk=="week"?weekKey(h):h;if(bk=="week"){const p=parts(hDate(h));return weekKey(`${p.year}-${p.month}-${p.day}`)}const d=hDate(h),p=parts(d);const day=`${p.year}-${p.month}-${p.day}`;if(bk=="day")return day;if(bk=="6h")return day+"T"+String(Math.floor(+p.hour/6)*6).padStart(2,"0");return h}
function bucketLabels(key,bk,first){ // short axis label + full tooltip title, both ET
 if(key[0]=="W"){const d=new Date(key.slice(1)+"T12:00:00Z");const s=d.toLocaleDateString("en-US",{timeZone:"UTC",month:"short",day:"numeric",year:"2-digit"});return[s,"Week of "+d.toLocaleDateString("en-US",{timeZone:"UTC",weekday:"short",month:"short",day:"numeric",year:"numeric"})+" (ET)"]}
 if(bk=="day"||key.length==10){const d=new Date(key+"T12:00:00Z");const s=d.toLocaleDateString("en-US",{timeZone:"UTC",weekday:"short",month:"short",day:"numeric"});return[s,s+" (ET day)"]}
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
const DAYF=d=>fmtD(d,{month:"short",day:"numeric",year:"numeric"});
const fDay=iso=>iso?DAYF(new Date(iso)):"—";
// dashed vertical marker where the archive backfill hands over to the live scanner
const seamPlug={id:"trSeam",afterDatasetsDraw(ch,_a,o){if(!o||o.index==null||o.index<0)return;const x=ch.scales.x;if(!x)return;const px=x.getPixelForValue(o.index)-(o.half?((x.getPixelForValue(1)-x.getPixelForValue(0))/2):0);
 const c=ch.ctx,ar=ch.chartArea;if(px<ar.left||px>ar.right)return;c.save();c.strokeStyle="#9aa4b2";c.setLineDash([4,4]);c.lineWidth=1;c.beginPath();c.moveTo(px,ar.top);c.lineTo(px,ar.bottom);c.stroke();
 c.setLineDash([]);c.fillStyle="#c9d0d9";c.font="10.5px system-ui,sans-serif";const t="◀ archive backfill · live scanner ▶";const w=c.measureText(t).width;c.fillText(t,Math.min(Math.max(ar.left+2,px-w/2),ar.right-w-2),ar.top+10);c.restore()}};
function seamIdx(D,keys,bk){if(!D.seam||!D.archive_since)return -1;const sd=new Date(D.seam);let k;
 if(D.bucket=="day"){const p=parts(sd);k=bucketKey(`${p.year}-${p.month}-${p.day}`,bk)}else k=bucketKey(sd.toISOString().slice(0,13),bk);return keys.indexOf(k)}
function render(){const D=T.d;if(!D)return;
 const H=D.hours,cut=a=>a,DM=D.bucket=="day";
 const first=D.history_since?new Date(D.history_since):null,days=(D.history_hours/24);
 const rl={"24h":"24 hours","7d":"7 days","30d":"30 days","90d":"90 days","1y":"1 year","all":"all history"}[T.rng];
 const cov=$$("tr_cov"),arch=D.archive_since?` Archive backfill (real items from public archives, scored with the scanner's own rules) covers ${E(fDay(D.archive_since))} – ${E(fDay(D.seam))}; the live scanner takes over at ${E(full(new Date(D.seam)))}.`:"";
 if(T.rng=="all"){cov.className="tr-cov full";cov.innerHTML=`<b>All history: data from ${E(fDay(D.history_since))}.</b>${arch}`}
 else if(D.partial){cov.className="tr-cov";cov.innerHTML=`<b>${rl} requested, ${days<1?Math.round(D.history_hours)+" hours":days<400?days.toFixed(1)+" days":(days/365).toFixed(1)+" years"} of history exist (data from ${E(fDay(D.history_since))}).</b> The charts show everything there is.${arch}`}
 else{cov.className="tr-cov full";cov.innerHTML=`Showing the last ${rl}: ${E(DM?fDay(D.start):full(hDate(H[0])))} to now · data from ${E(fDay(D.history_since))} · ${D.scans.length} scans · last scan ${E(D.last_scan_finished?full(new Date(D.last_scan_finished)):"—")}.${arch}`}
 // per-graph "Data from"
 const G=(D.coverage||{}).graphs||{},fr=(id,iso,extra)=>{const el=$$(id);if(el)el.innerHTML=`Data from <b>${E(fDay(iso))}</b>${extra?" · "+extra:""}`};
 fr("tr_f_vol",G.volume,D.archive_since?`archive backfill before ${E(fDay(D.seam))}; war/conflict, political and other news-driven categories start with the live scanner (see Data coverage)`:"");
 fr("tr_f_sev",G.severity,D.archive_since?"archive stories are scored and ranked with the scanner's own rules":"");fr("tr_f_wl",G.wire_watch,D.archive_since?"archive items are official single sources, so they count as The Wire":"");
 fr("tr_f_scan",G.scans,"scanner pass logs exist only since the scanner started; there is nothing to backfill");fr("tr_f_geo",G.geo,"");
 covTable(D);
 // KPIs
 const BL=D.by_list,s=a=>cut(a).reduce((x,y)=>x+y,0);
 const wire=s(BL.wire),watch=s(BL.watch),supp=s(BL.supp),r7=s(D.severity.r7_all),newItems=D.scans.reduce((a,x)=>a+(x.new_items||0),0),ar=s(BL.archive||[]);
 const mx=Math.max(0,...cut(D.severity.max).filter(v=>v!=null));
 $$("tr_kpis").innerHTML=[[wire+watch+(T.supp?supp:0),"stories"+(T.supp?" (incl. suppressed)":" on The Wire + Watchlist")],[wire,"on The Wire"],[watch,"on the Watchlist"],[r7,"rank 7+","hi"],[mx||"—","top Wire score"],[ar,"from archive backfill"],[D.scans.length,"scans"],[newItems.toLocaleString(),"new items scanned"]]
  .map(([v,l,c])=>`<div class="tr-kpi ${c||""}"><b>${E(typeof v=="number"?v.toLocaleString():v)}</b><span>${E(l)}</span></div>`).join("");
 // (a) volume by category
 const big=T.rng=="1y"||T.rng=="all";
 const vb=big?"week":(T.vmode=="lines"&&!DM)?"1h":(T.rng=="24h"?"1h":"day"),gv=group(H,vb),labs=gv.keys.map(k=>bucketLabels(k,vb));
 const cats=Object.keys(D.categories).sort((a,b)=>{const ia=CATS.findIndex(x=>x[0]==a),ib=CATS.findIndex(x=>x[0]==b);return(ia<0?99:ia)-(ib<0?99:ib)});
 const series=cats.map(c=>{const v=cut(D.categories[c].vis),sp=cut(D.categories[c].supp);return{c,data:sumBy(T.supp?v.map((x,i)=>x+sp[i]):v,gv)}}).filter(x=>x.data.some(Boolean));
 const per={"1h":"hour","day":"day","week":"week"}[vb];
 $$("tr_vsub").textContent=(T.vmode=="lines"?`New stories per ${per}, one line per category`:`New stories per ${per} (Eastern Time), stacked by category`)+(T.supp?", including suppressed rank 0–1 items.":" on The Wire and the Watchlist.");
 const vt={callbacks:{title:it=>it.length?labs[it[0].dataIndex][1]:"",footer:it=>T.vmode=="bars"?"Total: "+it.reduce((a,x)=>a+x.parsed.y,0):""}};
 const sv=seamIdx(D,gv.keys,vb),xT={"1h":"Hour (ET)","day":"Day (ET)","week":"Week (ET)"}[vb];
 draw("tr_vol",T.vmode=="lines"?
  {type:"line",data:{labels:labs.map(l=>l[0]),datasets:series.map(x=>({label:x.c,data:x.data,borderColor:cc(x.c),backgroundColor:cc(x.c),borderWidth:1.6,pointRadius:0,pointHoverRadius:3,tension:.25}))},
   plugins:[seamPlug],options:base(xT,`New stories per ${per}`,{plugins:Object.assign({},base().plugins,{trSeam:{index:sv},tooltip:Object.assign({},base().plugins.tooltip,vt,{filter:i=>i.parsed.y>0})})})}:
  {type:"bar",data:{labels:labs.map(l=>l[0]),datasets:series.map(x=>({label:x.c,data:x.data,backgroundColor:cc(x.c),borderWidth:0,maxBarThickness:46}))},plugins:[seamPlug],
   options:(()=>{const o=base(xT,`New stories per ${per}`);o.scales.x.stacked=true;o.scales.y.stacked=true;o.plugins.trSeam={index:sv,half:true};o.plugins.tooltip=Object.assign({},o.plugins.tooltip,vt,{filter:i=>i.parsed.y>0});return o})()});
 const tots=series.map(x=>[x.c,x.data.reduce((a,b)=>a+b,0)]).sort((a,b)=>b[1]-a[1]);
 $$("tr_vtot").innerHTML=`<span>Totals for the period:</span>`+tots.map(([c,n])=>`<span><i style="background:${cc(c)}"></i>${E(c)} <b>${n.toLocaleString()}</b></span>`).join("");
 // (b) severity
 let bk=T.bk;if(DM&&(bk=="1h"||bk=="6h"))bk=big?"week":"day";
 $$("tr_bk").querySelectorAll("button").forEach(b=>{const off=DM&&(b.dataset.v=="1h"||b.dataset.v=="6h");b.disabled=off;b.title=off?"Hourly blocks are available up to the 30-day range":"";b.classList.toggle("on",b.dataset.v==bk)});
 const gs=group(H,bk),sl=gs.keys.map(k=>bucketLabels(k,bk)),SV=D.severity,ss=seamIdx(D,gs.keys,bk);
 const ssum=sumBy(cut(SV.sum),gs),sn=sumBy(cut(SV.n),gs),r7w=sumBy(cut(SV.r7),gs),smax=new Array(gs.keys.length).fill(null);
 cut(SV.max).forEach((v,i)=>{if(v!=null){const j=gs.idx[i];smax[j]=Math.max(smax[j]??0,v)}});
 const avg=ssum.map((v,i)=>sn[i]?Math.round(v/sn[i]*10)/10:null);
 const bkT={"1h":"Hour (ET)","6h":"6-hour block (ET)","day":"Day (ET)","week":"Week (ET)"}[bk],pr=(bk=="1h"||gs.keys.length>120)?0:2;
 draw("tr_sev",{data:{labels:sl.map(l=>l[0]),datasets:[
  {type:"line",label:"max score",data:smax,borderColor:"#ff4d4f",backgroundColor:"#ff4d4f",pointRadius:pr,pointHoverRadius:4,borderWidth:1.8,spanGaps:false,yAxisID:"y",tension:.2},
  {type:"line",label:"avg score",data:avg,borderColor:"#faad14",backgroundColor:"#faad14",pointRadius:pr,pointHoverRadius:4,borderWidth:1.8,spanGaps:false,yAxisID:"y",tension:.2},
  {type:"line",label:"high threshold (60)",data:sl.map(()=>D.high_threshold),borderColor:"#ff4d4f66",borderDash:[5,5],pointRadius:0,borderWidth:1,yAxisID:"y"},
  {type:"bar",label:"# rank 7+",data:r7w,backgroundColor:"#4aa3ffaa",yAxisID:"y2",maxBarThickness:30}]},plugins:[seamPlug],
  options:(()=>{const o=base(bkT,"Score (0–100)");o.plugins.trSeam={index:ss,half:true};o.scales.y.max=100;o.scales.y2={position:"right",beginAtZero:true,ticks:{color:"#4aa3ff",precision:0},grid:{display:false},title:ttl("Rank 7+ stories","#4aa3ff")};
   o.plugins.tooltip.callbacks={title:it=>it.length?sl[it[0].dataIndex][1]:"",footer:it=>it.length?`${sn[it[0].dataIndex]} Wire stor${sn[it[0].dataIndex]==1?"y":"ies"} in this period`:""};return o})()});
 // (c) Wire vs Watchlist
 const w1=sumBy(cut(BL.wire),gs),w2=sumBy(cut(BL.watch),gs),w3=sumBy(cut(BL.supp),gs);
 const wds=[{label:"The Wire",data:w1,borderColor:"#4aa3ff",backgroundColor:"#4aa3ff33",fill:true},{label:"Watchlist",data:w2,borderColor:"#faad14",backgroundColor:"#faad1422",fill:true}];
 if(T.supp)wds.push({label:"suppressed (rank 0–1)",data:w3,borderColor:"#8a93a6",borderDash:[4,4],backgroundColor:"#8a93a6",fill:false});
 draw("tr_wl",{type:"line",data:{labels:sl.map(l=>l[0]),datasets:wds.map(d=>Object.assign({pointRadius:pr,pointHoverRadius:4,borderWidth:1.8,tension:.25},d))},plugins:[seamPlug],
  options:(()=>{const o=base(bkT,"New stories");o.plugins.trSeam={index:ss};o.scales.y.ticks.precision=0;o.plugins.tooltip.callbacks={title:it=>it.length?sl[it[0].dataIndex][1]:"",footer:it=>{if(!it.length)return"";const i=it[0].dataIndex,t=w1[i]+w2[i];return t?`Wire share ${Math.round(100*w1[i]/t)}%`:""}};return o})()});
 // (d) scans
 const SC=D.scans,scl=SC.map(x=>new Date(x.finished||x.started));
 draw("tr_scan",{data:{labels:scl.map(d=>fmtD(d,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})),datasets:[
  {type:"line",label:"new items",data:SC.map(x=>x.new_items),borderColor:"#ff4d4f",backgroundColor:"#ff4d4f",pointRadius:SC.length>200?0:2.5,pointHoverRadius:5,borderWidth:1.8,yAxisID:"y",tension:.2},
  {type:"line",label:"items fetched",data:SC.map(x=>x.fetched),borderColor:"#36cfc9",backgroundColor:"#36cfc9",pointRadius:0,pointHoverRadius:4,borderWidth:1.4,borderDash:[3,3],yAxisID:"y3"},
  {type:"bar",label:"failed sources",data:SC.map(x=>x.failed_sources),backgroundColor:"#b37febaa",yAxisID:"y2",maxBarThickness:14}]},
  options:(()=>{const o=base("Scan finished (ET)","New items per scan");o.scales.y.ticks.color="#ff7875";
   o.scales.y2={position:"right",beginAtZero:true,suggestedMax:5,ticks:{color:"#b37feb",precision:0},grid:{display:false},title:ttl("Failed sources","#b37feb")};
   o.scales.y3={display:innerWidth>600,position:"right",beginAtZero:true,ticks:{color:"#36cfc9"},grid:{display:false},title:ttl("Items fetched","#36cfc9")};
   o.plugins.tooltip.callbacks={title:it=>{if(!it.length)return"";const x=SC[it[0].dataIndex];return`Scan #${x.id} · ${full(scl[it[0].dataIndex])}`},
    footer:it=>{if(!it.length)return"";const x=SC[it[0].dataIndex];return`${x.trigger} · ${x.ok_sources} sources OK, ${x.failed_sources} failed${x.err?" · scan reported an error":""}`}};return o})()});
 const avgNew=SC.length?Math.round(newItems/SC.length):0,maxS=SC.reduce((a,x)=>x.new_items>(a?a.new_items:-1)?x:a,null);
 $$("tr_stot").innerHTML=SC.length?`<span>Average <b>${avgNew}</b> new items per scan</span><span>Busiest: <b>${maxS.new_items}</b> at ${E(full(new Date(maxS.finished||maxS.started)))}</span><span>Sources now: <b>${D.sources_ok}</b> OK, <b>${D.sources_failed}</b> failing${D.sources_total-D.sources_ok-D.sources_failed?`, ${D.sources_total-D.sources_ok-D.sources_failed} switched off`:""}</span><span>Raw reports in period: <b>${D.raw_items.toLocaleString()}</b></span>`:"<span>No scans in this period.</span>";
 geoRender(D);
 $$("tr_msg").textContent=`Updated ${full(new Date(D.generated))}${D.cached?" (cached)":""}`}

// ---------- data coverage table ----------
function covTable(D){const C=D.coverage||{},el=$$("tr_covt");if(!el)return;const G=C.graphs||{};
 const cr=Object.entries(C.categories||{}).sort((a,b)=>(a[1].since||"").localeCompare(b[1].since||""));
 const src=C.archive_sources||[];
 el.innerHTML=`<div class=tr-cvg><div><h4>Per graph</h4><table><tr><th>Graph</th><th>Data from</th></tr>${[["Alert volume by category",G.volume],["Severity trend",G.severity],["The Wire vs Watchlist",G.wire_watch],["Geographic heat map",G.geo],["Scan volume & source health",G.scans],["Alert stream",G.stream]].map(([a,b])=>`<tr><td>${E(a)}</td><td>${E(fDay(b))}</td></tr>`).join("")}</table></div>
 <div><h4>Per category</h4><table><tr><th>Category</th><th>Data from</th><th>Archive</th><th>Live</th></tr>${cr.map(([k,v])=>`<tr><td><i style="background:${cc(k)}"></i>${E(k)}</td><td>${E(fDay(v.since))}</td><td>${v.archive_n?(v.archive_n.toLocaleString()+" from "+E(fDay(v.archive_since))):"—"}</td><td>${(v.live_n||0).toLocaleString()} from ${E(fDay(v.live_since))}</td></tr>`).join("")}</table></div></div>
 ${src.length?`<h4>Archive sources</h4><table class=tr-srct><tr><th>Source</th><th>Status</th><th>Stories kept</th><th>Earliest kept</th><th>Notes</th></tr>${src.map(x=>`<tr><td>${/^https?:/.test(x.url||"")?`<a href="${E(x.url)}" target=_blank rel="noopener noreferrer">${E(x.name)}</a>`:E(x.name)}</td><td>${E(x.status)}</td><td>${(x.kept||0).toLocaleString()}${x.fetched&&x.fetched!=x.kept?` <span class=meta>of ${x.fetched.toLocaleString()} fetched</span>`:""}</td><td>${E(x.kept_earliest?fDay(x.kept_earliest):"—")}</td><td>${E(x.note||"")}</td></tr>`).join("")}</table>
 <p class=meta>Archive items are only kept for the time before the live scanner's first story, and anything the scanner already holds is dropped, so nothing is counted twice. Gaps stay gaps: nothing is estimated or interpolated. ${C.archive_built?"Built "+E(full(new Date(C.archive_built)))+".":""}</p>`:`<p class=meta>No archive backfill is loaded on this server yet.</p>`}`}

// ---------- geographic heat map ----------
const GM={map:null,layer:null};
function geoRender(D){const el=$$("tr_geo");if(!el||typeof L=="undefined"){if(el)el.innerHTML='<div class=tr-err>Map library did not load.</div>';return}
 if(!vis())return;
 if(!GM.map){GM.map=L.map(el,{worldCopyJump:true,minZoom:1,maxZoom:8,zoomSnap:.5,attributionControl:true}).setView([20,10],innerWidth<600?1:2);
  if(window.bnBaseLayer)bnBaseLayer(GM.map,{maxZoom:8})   /* t252: shared keyless basemap (OpenFreeMap); CARTO needs a key, OSM tile servers block the site */}
 else setTimeout(()=>GM.map.invalidateSize(),50);
 if(GM.layer){GM.map.removeLayer(GM.layer);GM.layer=null}
 const P=D.geo||[],mx=Math.max(1,...P.map(p=>p[2]));
 const w=n=>Math.min(1,Math.log1p(n)/Math.log1p(mx));
 if(typeof L.heatLayer=="function")GM.layer=L.heatLayer(P.map(p=>[p[0],p[1],w(p[2])]),{radius:innerWidth<600?12:18,blur:15,maxZoom:5,max:1,minOpacity:.3,gradient:{.15:"#3b2a6b",.35:"#7a2d8c",.55:"#c2255c",.72:"#f0532d",.86:"#fa8c16",1:"#ffe58f"}});
 else GM.layer=L.layerGroup(P.map(p=>L.circleMarker([p[0],p[1]],{radius:2+6*w(p[2]),color:"#ff4d4f",weight:0,fillOpacity:.6})));
 GM.layer.addTo(GM.map);
 const tot=P.reduce((a,p)=>a+p[2],0),ar=P.reduce((a,p)=>a+p[4],0),top=P.slice(0,1)[0];
 $$("tr_gtot").innerHTML=`<span><b>${tot.toLocaleString()}</b> located stories</span><span><b>${ar.toLocaleString()}</b> from archive backfill</span><span><b>${P.length.toLocaleString()}</b> grid cells</span>${top?`<span>Busiest cell: <b>${top[2].toLocaleString()}</b> stories near ${top[0]}°, ${top[1]}°</span>`:""}`}

// ---------- infinite-scroll stream ----------
const RKC=["#3a4250","#4b5563","#2f7d4f","#52c41a","#a0d911","#fadb14","#faad14","#fa8c16","#ff4d4f","#cf1322","#8b0000"];
const SM={next:null,busy:false,end:false,pages:0,n:0,err:null,io:null,started:false,gen:0};
const stT=iso=>{const d=new Date(iso);return fmtD(d,{month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"})+" "+tzName(d)};
function stItem(x){const rk=Math.max(0,Math.min(10,x.rank|0)),fg=rk>=5&&rk<=7?"#000":"#fff",u=(x.links||[])[0];
 const t=u?`<a href="${E(u.url)}" target=_blank rel="noopener noreferrer">${E(x.title)}</a>`:E(x.title);
 return `<li class="tr-si${x.origin=="live"?"":" arch"}" data-id="${E(x.id)}"><span class=tr-rk style="background:${RKC[rk]};color:${fg}" title="rank ${rk}/10 · score ${E(x.score)}/100">${rk}</span>
 <div class=tr-sb><div class=tr-st>${t}</div><div class=meta><i class=tr-cd style="background:${cc(x.category)}"></i>${E(x.category)} · ${E(stT(x.t))}${x.location?" · "+E(String(x.location).slice(0,80)):""} · ${x.list=="watch"?"Watchlist":"The Wire"} · score ${E(x.score)}
 ${x.origin=="live"?'<span class="tr-org l">live</span>':'<span class="tr-org a" title="Archive backfill: real item from a public archive, scored with the scanner\'s rules; never on The Wire or the alert bar">archive</span>'}</div>
 ${(x.links||[]).length?`<div class=tr-sl>${x.links.map(l=>`<a href="${E(l.url)}" target=_blank rel="noopener noreferrer">${E(l.source||"source")}</a>`).join(" · ")}</div>`:""}</div></li>`}
async function stMore(){if(SM.busy||SM.end)return;SM.busy=true;const g=SM.gen,st=$$("tr_sstate");st.className="tr-sstate";st.textContent=SM.pages?"Loading older stories…":"Loading…";
 try{const q=new URLSearchParams({limit:"50"});if(SM.next)q.set("before",SM.next);const c=$$("tr_scat").value,o=$$("tr_sorg").value;if(c)q.set("cat",c);if(o)q.set("origin",o);
  const r=await fetch("api/trends/stream?"+q,{cache:"no-store"}),j=await r.json();if(!r.ok)throw new Error(j.error||r.status);if(g!=SM.gen)return;
  $$("tr_slist").insertAdjacentHTML("beforeend",j.items.map(stItem).join(""));SM.pages++;SM.n+=j.items.length;SM.next=j.next;SM.end=!j.next;
  const last=j.items.length?j.items[j.items.length-1]:null;
  st.textContent=SM.end?(SM.n?`End of history · ${SM.n.toLocaleString()} stories · oldest ${stT((last||{}).t||"")}`:"No stories for this filter."):`${SM.n.toLocaleString()} stories loaded · back to ${E(last?stT(last.t):"")}`;if(SM.end)st.classList.add("end");
 }catch(e){if(g!=SM.gen)return;st.className="tr-sstate err";st.innerHTML=`Couldn't load more: ${E(e.message||e)} <button type=button id=tr_sretry>Retry</button>`;const b=$$("tr_sretry");if(b)b.onclick=()=>{SM.busy=false;stMore()}}
 finally{if(g==SM.gen){SM.busy=false;setTimeout(stCheck,60)}}}
function stCheck(){if(SM.end||SM.busy||!vis())return;const r=$$("tr_ssent").getBoundingClientRect();if(r.top<innerHeight+700)stMore()}
function stReset(){SM.gen++;SM.next=null;SM.end=false;SM.pages=0;SM.n=0;SM.busy=false;$$("tr_slist").innerHTML="";stMore()}
function stStart(){if(SM.started)return;SM.started=true;
 if("IntersectionObserver" in window){SM.io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting))stMore()},{rootMargin:"0px 0px 700px 0px"});SM.io.observe($$("tr_ssent"))}
 else addEventListener("scroll",stCheck,{passive:true});
 $$("tr_scat").onchange=stReset;$$("tr_sorg").onchange=stReset;stMore()}

// ---------- data ----------
async function load(){if(T.busy)return;T.busy=true;try{const r=await fetch("api/trends?range="+encodeURIComponent(T.rng),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);
 T.d=j;T.stale=false;T.last=Date.now();render();stStart()}catch(e){$$("tr_msg").innerHTML=`<span class=tr-err>Couldn't load the history: ${E(e.message||e)}</span>`}finally{T.busy=false}}
const segOn=(id,v)=>$$(id).querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.v==v));
$$("tr_rng").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b||b.dataset.v==T.rng)return;T.rng=b.dataset.v;SS("tr_rng",T.rng);segOn("tr_rng",T.rng);
 if(T.rng=="24h"&&(T.bk=="day"||T.bk=="week")){T.bk="6h";segOn("tr_bk",T.bk)}load()};
$$("tr_vmode").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b)return;T.vmode=b.dataset.v;SS("tr_vmode",T.vmode);segOn("tr_vmode",T.vmode);render()};
$$("tr_bk").onclick=e=>{const b=e.target.closest("button[data-v]");if(!b||b.disabled)return;T.bk=b.dataset.v;SS("tr_bk",T.bk);segOn("tr_bk",T.bk);render()};
$$("tr_supp").onchange=e=>{T.supp=e.target.checked;SS("tr_supp",T.supp?"1":"0");render()};
const rb=$$("tr_ref");if(rb)rb.onclick=async e=>{e.stopPropagation();rb.disabled=true;rb.textContent="scanning…";try{if($("refresh")&&$("refresh").onclick)await $("refresh").onclick()}catch(_){}await load();rb.textContent="⟳ Refresh";rb.disabled=false};
if(nav)nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="trends")setTimeout(()=>{if(T.stale||!T.d||Date.now()-T.last>120000)load();else{Object.values(T.charts).forEach(c=>c.resize());if(T.d)geoRender(T.d)}stStart()},30)});
// auto-refresh: every scanner pass pushes a "scan" event; redraw if the tab is open, otherwise refresh on next open
let st=0;const hook=()=>{if(typeof LV=="object"&&LV&&LV.es){LV.es.addEventListener("scan",()=>{T.stale=true;clearTimeout(st);st=setTimeout(()=>{if(vis())load()},3000)});return true}return false};if(!hook())setTimeout(hook,2000);
setInterval(()=>{if(vis())load();else T.stale=true},300000);
if(vis())load();
})();
