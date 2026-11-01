// ---- ⚡ Energy Grid status panels (gridstatus.py, t234), injected at the top of the #grid tab (tabfeeds.py / gridwatch.py keep the threat list):
// 1) grid-operator sections map colored by derived status, 2) local outage view for any state, 3) weather-triggered infrastructure check worldwide.
// Free public data only; every input shows its age; no outage polygons are drawn. Times in ET. ----
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):(/^#grid\/state\/[A-Z]{2}$/.test(u||"")?u:"#");
const ET=t=>{if(!t)return"n/a";const d=new Date(t);if(isNaN(d))return"n/a";return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)};
const AGO=m=>m==null?"":m<1?"just now":m<60?m+" min ago":m<1440?Math.round(m/60)+" h ago":Math.round(m/1440)+" d ago";
const agoT=t=>{const m=Math.round((Date.now()-Date.parse(t))/60000);return isNaN(m)?"":AGO(m)};
const COL={online:"#52c41a",watch:"#fadb14",degraded:"#fa8c16",offline:"#ff4d4f",nodata:"#5b6573",nodata_ok:"#3f7f5a"};
const LAB={online:"Online",watch:"Watch",degraded:"Degraded",offline:"Offline",nodata:"No data",nodata_ok:"No hourly feed · no warnings"};
const STN={AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};
const H0=(location.hash.match(/^#grid\/state\/([A-Z]{2})$/)||[])[1]||null;
const G={d:null,geo:null,map:null,lay:null,sel:null,st:H0,busy:false,t:0};
function host(){return document.getElementById("tab-grid")}
function build(){const M=host();if(!M||M.querySelector("#gs_top"))return!!M;
 const w=document.createElement("div");w.id="gs_top";
 w.innerHTML=`<section class="pn gs"><h2><span>🗺</span> Grid sections <span class="meta">— the U.S. grid by operator, colored by current status. Tap a section for local outages</span></h2>
  <div class="gs-fresh meta" id="gs_fresh">Loading grid status…</div>
  <div class="gs-mapw"><div id="gs_map" class="gs-map" role="img" aria-label="Map of U.S. grid operator sections colored by status"></div>
  <div class="gs-leg">${["online","watch","degraded","offline","nodata_ok","nodata"].map(k=>`<span><i style="background:${COL[k]}"></i>${LAB[k]}</span>`).join("")}</div></div>
  <div class="gs-cards" id="gs_cards"></div>
  <details class="gs-how"><summary>How the status is worked out</summary><div class="meta">blackout.network derives each section's color from public data; it is not an official operator status.
  <b>Offline</b>: reported demand collapsed (half or less of the same hour yesterday). <b>Degraded</b>: demand 15%+ below both the EIA day-ahead forecast and yesterday (possible load loss), 5,000+ outages reported to DOE's ODIN, an extreme NWS alert (hurricane, ice storm, blizzard…), a confirmed scanner grid alert ranked 6+, or a G4+ geomagnetic storm.
  <b>Watch</b>: demand 8%+ below forecast and yesterday, 1,500+ ODIN outages, 5+ power-relevant NWS warnings, a scanner grid alert ranked 5+, a G3 storm or EIA data older than 6 h.
  EIA-930 covers the Lower 48 only and posts each hour with a 1–2 h lag. ODIN covers the utilities that share data with it (about 150). Operator dashboards linked on each card have the official real-time picture.</div></details>
  <div class="meta gs-src" id="gs_src"></div></section>
 <section class="pn gs" id="gs_local"><h2><span>🏘</span> Local outage view <span class="meta">— is the power on where you are? Works for every state</span></h2>
  <div class="gs-bar"><label for="gs_state" class="gs-lbl">State</label><select id="gs_state"><option value="">Choose a state…</option>${Object.entries(STN).sort((a,b)=>a[1].localeCompare(b[1])).map(([k,v])=>`<option value="${k}">${E(v)}</option>`).join("")}</select><span class="meta" id="gs_lmsg"></span></div>
  <div id="gs_lv"><div class="meta">Pick a state, or tap a section on the map. Sections that turn watch, degraded or offline open here automatically.</div></div></section>
 <section class="pn gs" id="gs_wx"><h2><span>🌪</span> Weather-triggered infrastructure check <span class="meta">— every major weather or disaster alert the scanner ranked 5+ (4+ in the U.S.) in the last 72 h, anywhere in the world</span></h2>
  <div id="gs_wxl"><div class="meta">Loading…</div></div></section>`;
 M.insertBefore(w,M.firstChild);
 w.querySelector("#gs_state").onchange=e=>{G.st=e.target.value||null;local()};
 w.addEventListener("click",e=>{const a=e.target.closest('a[href^="#grid/state/"]');if(a){e.preventDefault();pick(a.getAttribute("href").slice(-2))}
  const c=e.target.closest(".gs-card[data-s]");if(c&&!e.target.closest("a"))selSec(c.dataset.s,true)});
 return true}
function pick(st){G.st=st;const s=document.getElementById("gs_state");if(s)s.value=st;local();document.getElementById("gs_local").scrollIntoView({behavior:"smooth",block:"start"})}
function spark(se){if(!se||se.length<3)return"";const v=se.flatMap(x=>[x[1],x[2]]).filter(x=>x!=null);const lo=Math.min(...v),hi=Math.max(...v),W=160,H=34,n=se.length-1;
 const P=i=>se.map((x,j)=>x[i]==null?null:`${(j/n*W).toFixed(1)},${(H-2-(x[i]-lo)/((hi-lo)||1)*(H-4)).toFixed(1)}`).filter(Boolean).join(" ");
 return `<svg class="gs-sp" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Demand (solid) vs day-ahead forecast (dashed), last 36 h"><polyline points="${P(2)}" fill="none" stroke="#6b7a8c" stroke-width="1.2" stroke-dasharray="3 2"/><polyline points="${P(1)}" fill="none" stroke="#4aa3ff" stroke-width="1.6"/></svg>`}
const ORDER={offline:0,degraded:1,watch:2,nodata:3,online:4,nodata_ok:5};
function cards(){const S=(G.d||{}).sections||{};const L=Object.values(S).sort((a,b)=>(ORDER[a.status]-ORDER[b.status])||a.name.localeCompare(b.name));
 document.getElementById("gs_cards").innerHTML=L.map(s=>{const pct=v=>v==null?"–":(v>0?"+":"")+v+"%";
  return `<div class="gs-card ${s.id==G.sel?"on":""}" data-s="${E(s.id)}" tabindex="0" style="--sc:${COL[s.status]||"#5b6573"}"><div class="gs-ch"><b>${E(s.name)}</b><span class="gs-pill" style="background:${COL[s.status]}">${E(LAB[s.status]||s.status)}</span></div>
  ${s.demand_mw!=null?`<div class="gs-num">${Number(s.demand_mw).toLocaleString()} MW <span class="meta">demand · forecast ${s.forecast_mw!=null?Number(s.forecast_mw).toLocaleString():"–"} MW (${pct(s.vs_forecast_pct)}) · vs yesterday ${pct(s.vs_yesterday_pct)}</span></div>${spark(s.series)}
  <div class="meta">EIA-930 hour ${E(ET(s.eia_hour))} (${E(AGO(Math.round((s.eia_age_h||0)*60)))})</div>`:`<div class="meta">${E(s.no_eia||"No EIA-930 hourly data")}</div>`}
  ${s.reasons&&s.reasons.length?`<ul class="gs-rs">${s.reasons.map(r=>`<li>${E(r)}</li>`).join("")}</ul>`:`<div class="meta">No warning signs in the public inputs.</div>`}
  <div class="meta">${s.odin?`ODIN: ${Number(s.odin.outages).toLocaleString()} outages from ${s.odin.reporting_outages} of ${s.odin.utilities} reporting utilities · `:""}NWS: ${s.nws?s.nws.power_alerts:0} power-relevant alerts${s.scanner&&s.scanner.alerts_12h?` · scanner: ${s.scanner.alerts_12h} grid alert(s) in 12 h`:""}</div>
  <div class="meta">${s.site?`<a href="${U(s.site)}" target="_blank" rel="noopener noreferrer">Official operator dashboard ↗</a> · `:""}States: ${s.states.map(t=>`<a href="#grid/state/${t}">${t}</a>`).join(" ")}</div></div>`}).join("")}
function fresh(){const d=G.d||{},f=d.freshness||{};const eh=Object.values(d.sections||{}).map(s=>s.eia_hour).filter(Boolean).sort().pop();
 const it=[["Status computed",f.sections],["EIA-930",f.eia],["ODIN",f.odin],["NWS",f.nws],["SWPC",f.swpc],["FEMA shelters",f.shelters]].filter(x=>x[1]&&x[1].ts).map(([l,x])=>`${l} ${E(AGO(x.age_min))}`);
 const sw=d.swpc;document.getElementById("gs_fresh").innerHTML=`<b>Data freshness:</b> ${it.join(" · ")||"waiting for the first sync"}${eh?` · latest EIA-930 hour <b>${E(ET(eh))}</b>`:""}${sw?` · geomagnetic now <b>G${E(sw.g)}</b> (NOAA)`:""}`;
 document.getElementById("gs_src").innerHTML="Sources: "+(d.sources||[]).map(s=>`<a href="${U(s.url)}" target="_blank" rel="noopener noreferrer">${E(s.name)}</a>`).join(" · ")}
function styleFor(id){const s=((G.d||{}).sections||{})[id]||{};return {color:id==G.sel?"#ffffff":"#0b0d10",weight:id==G.sel?2.5:1,fillColor:COL[s.status]||"#5b6573",fillOpacity:id==G.sel?.62:.45}}
function initMap(){if(G.map||typeof L=="undefined"||!G.geo)return;const el=document.getElementById("gs_map");if(!el||!el.offsetWidth)return;
 G.map=L.map(el,{zoomSnap:.25,minZoom:2,maxZoom:9,worldCopyJump:true,scrollWheelZoom:false}).setView([39,-98],3.6);
 if(window.bnBaseLayer)bnBaseLayer(G.map,{maxZoom:9,extra:'grid sections <a href="https://commongrid.info/" target="_blank" rel="noopener">CommonGrid</a> (ODbL) · EIA · ODIN · NWS'});
 else L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:9,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(G.map);
 G.lay=L.geoJSON(G.geo,{style:f=>styleFor(f.properties.id),onEachFeature:(f,l)=>{l.on("click",()=>selSec(f.properties.id,true));
  l.bindTooltip(()=>{const s=((G.d||{}).sections||{})[f.properties.id]||{};return `<b>${E(f.properties.name)}</b><br>${E(LAB[s.status]||"loading")}${s.demand_mw!=null?` · ${Number(s.demand_mw).toLocaleString()} MW`:""}`},{sticky:true})}}).addTo(G.map);
 const fc=L.control({position:"bottomleft"});fc.onAdd=()=>{const d=L.DomUtil.create("div","gs-mfresh");d.id="gs_mfresh";return d};fc.addTo(G.map);mfresh();
 const ak=L.control({position:"topright"});ak.onAdd=()=>{const d=L.DomUtil.create("div","gs-jump");d.innerHTML='<button type="button" data-v="l48">Lower 48</button><button type="button" data-v="ak">Alaska</button><button type="button" data-v="hi">Hawaii</button>';
  L.DomEvent.disableClickPropagation(d);d.onclick=e=>{const v=e.target.dataset.v;if(v=="ak")G.map.setView([63,-152],3.4);else if(v=="hi")G.map.setView([20.6,-157.3],6);else G.map.setView([39,-98],3.6)};return d};ak.addTo(G.map)}
function mfresh(){const el=document.getElementById("gs_mfresh");if(!el)return;const f=((G.d||{}).freshness||{}).sections;const eh=Object.values((G.d||{}).sections||{}).map(s=>s.eia_hour).filter(Boolean).sort().pop();
 el.innerHTML=`Status ${f&&f.ts?E(AGO(f.age_min)):"n/a"}${eh?` · EIA hour ${E(ET(eh))}`:""}<br><span>derived by blackout.network, not an official status</span>`}
function paintMap(){if(G.lay)G.lay.setStyle(f=>styleFor(f.properties.id));mfresh()}
function selSec(id,user){G.sel=id;paintMap();cards();const s=((G.d||{}).sections||{})[id];if(!s)return;
 if(user||!G.st||!s.states.includes(G.st)){G.st=s.states[0];const el=document.getElementById("gs_state");if(el)el.value=G.st;local()}
 if(user)document.getElementById("gs_local").scrollIntoView({behavior:"smooth",block:"start"})}
async function local(){const box=document.getElementById("gs_lv"),msg=document.getElementById("gs_lmsg");if(!G.st){box.innerHTML='<div class="meta">Pick a state.</div>';return}
 msg.textContent="loading…";
 try{const r=await fetch("api/gridstatus/state?st="+encodeURIComponent(G.st),{cache:"no-store"});const d=await r.json();if(!r.ok)throw d.error||r.status;msg.textContent="";
  const si=d.section_info||{};
  const nws=(d.nws||[]).sort((a,b)=>(b.power-a.power)||(a.event||"").localeCompare(b.event||""));
  box.innerHTML=`<div class="gs-lh"><b>${E(d.name)}</b> · grid section <b>${E(si.name||d.section||"–")}</b> <span class="gs-pill" style="background:${COL[si.status]||"#5b6573"}">${E(LAB[si.status]||"–")}</span>${si.reasons&&si.reasons.length?` <span class="meta">${E(si.reasons.join(" · "))}</span>`:""}</div>
  <div class="gs-lgrid">
  <div class="gs-lc"><h3>⚡ Utilities reporting to DOE's ODIN</h3><div class="meta">Live outage counts from utilities that share data with the U.S. Department of Energy (ODIN, Oak Ridge National Laboratory). Checked ${E(agoT(d.odin_ts))}.</div>
   ${(d.odin||[]).length?`<ul class="gs-ul">${d.odin.map(u=>`<li><b>${E(u.name)}</b> — ${u.outages?`<span class="gs-bad">${Number(u.outages).toLocaleString()} outage(s)</span>`:'<span class="gs-ok">no outages reported</span>'}<div class="meta">${E((u.resolution||"").toLowerCase())}-level data · reported ${E(ET(u.received))}${u.error?" · feed error":""}${u.web?` · <a href="${U(u.web)}" target="_blank" rel="noopener noreferrer">utility site ↗</a>`:""}</div></li>`).join("")}</ul>`:'<div class="meta">No utility in this state shares live data with ODIN yet. Use the outage maps below.</div>'}</div>
  <div class="gs-lc"><h3>🗺 Check your utility's outage map</h3><div class="meta">Street-by-street detail lives on each utility's own outage map. Largest utilities serving ${E(d.name)} (customer counts are company-wide, EIA-861 via CommonGrid):</div>
   <ul class="gs-ul">${(d.utilities||[]).map(u=>`<li><a href="${U(u.web)}" target="_blank" rel="noopener noreferrer">${E(u.name)} ↗</a> <span class="meta">${u.customers?Number(u.customers).toLocaleString()+" customers":""}</span></li>`).join("")||'<li class="meta">No utility list for this state.</li>'}</ul>
   <div class="meta">Can't find yours? Your power bill names your utility. <a href="https://www.ready.gov/power-outages" target="_blank" rel="noopener noreferrer">Ready.gov: what to do in an outage ↗</a></div></div>
  <div class="gs-lc"><h3>🌩 Active NWS alerts (severe + extreme)</h3><div class="meta">National Weather Service, checked ${E(agoT(d.nws_ts))}. ⚡ marks events that often cause power outages.</div>
   ${nws.length?`<ul class="gs-ul">${nws.slice(0,12).map(a=>`<li>${a.power?"⚡ ":""}<a href="${U(a.url)}" target="_blank" rel="noopener noreferrer"><b>${E(a.event)}</b></a> <span class="meta">until ${E(ET(a.expires))}</span><div class="meta">${E(a.area)}</div></li>`).join("")}</ul>${nws.length>12?`<div class="meta">+${nws.length-12} more</div>`:""}`:'<div class="meta">No severe or extreme NWS alerts for this state right now.</div>'}</div>
  <div class="gs-lc"><h3>🏠 FEMA-listed open shelters</h3><div class="meta">FEMA National Shelter System, checked ${E(agoT(d.shelters_ts))}.</div>
   ${(d.shelters||[]).length?`<ul class="gs-ul">${d.shelters.map(s=>`<li><b>${E(s.name)}</b><div class="meta">${E([s.address,s.city,s.state,s.zip].filter(Boolean).join(", "))}${s.org?` · ${E(s.org)}`:""}${s.capacity?` · capacity ${E(s.capacity)}`:""}</div></li>`).join("")}</ul>`:'<div class="meta">No FEMA-listed open shelters in this state right now.</div>'}
   <div class="meta"><a href="https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html" target="_blank" rel="noopener noreferrer">Red Cross shelter finder ↗</a> · <a href="https://www.211.org/" target="_blank" rel="noopener noreferrer">211 local help ↗</a> · emergencies: dial 911</div></div>
  <div class="gs-lc gs-wide"><h3>💬 What people are reporting</h3><div class="meta">Posts and news the scanner already collected in the last 48 h that mention a power outage in ${E(d.name)}. Unconfirmed: single reports, not verified.</div>
   ${(d.reports||[]).length?`<ul class="gs-ul">${d.reports.map(x=>`<li><a href="${U(x.url)}" target="_blank" rel="noopener noreferrer">${E(x.title)}</a> <span class="unc">unconfirmed</span><div class="meta">${E(x.source)} · ${E(ET(x.time))}</div></li>`).join("")}</ul>`:'<div class="meta">No outage reports for this state in the last 48 h.</div>'}</div>
  </div><div class="meta gs-note">blackout.network does not draw outage areas: ODIN shares outage polygons only with signed-in partners, and drawing our own would be guesswork.</div>`}
 catch(e){msg.textContent="Local view offline: "+e}}
function wx(){const L=(G.d||{}).weather||[];const el=document.getElementById("gs_wxl");
 if(!L.length){el.innerHTML='<div class="meta">No major weather or disaster alerts in the last 72 h.</div>';return}
 const RC=r=>r>=7?"h":r>=5?"m":"l2";
 el.innerHTML=`<div class="meta">Checked automatically from the scanner's own disaster alerts (GDACS, USGS, NWS, JMA and others). Nearby reports below are real scanner items with their links; unconfirmed ones are labeled.</div>`+L.map(ev=>{
  const chk=(ev.checks||[]).filter(c=>c.items.length);
  return `<details class="gs-ev" ${ev.rank>=7||ev.us?"open":""}><summary><span class="gs-rk ${RC(ev.rank)}">rank ${E(ev.rank)}/10</span><b>${E(ev.title)}</b>${ev.unconfirmed?' <span class="unc">unconfirmed</span>':""}<div class="meta">${E(ev.location||(ev.us?"United States":"location n/a"))} · updated ${E(ET(ev.updated))}${ev.us&&ev.state?` · ${E(STN[ev.state]||ev.state)}`:""}${ev.section_status?` · grid section <span class="gs-pill" style="background:${COL[ev.section_status]}">${E(LAB[ev.section_status])}</span>`:""}</div></summary>
  <div class="gs-evb"><div class="meta">Verify: ${(ev.links||[]).map(l=>`<a href="${U(l.url)}" target="_blank" rel="noopener noreferrer">${E(l.source||"source")}</a>`).join(" · ")||"no link"}</div>
  ${ev.own_impacts&&ev.own_impacts.length?`<div class="meta">The alert itself mentions: ${E(ev.own_impacts.join(", "))}</div>`:""}
  <div class="gs-chk">${chk.map(c=>`<div class="gs-ck has"><b>${E(c.label)}</b>${c.items.length?`<ul>${c.items.map(i=>`<li>${i.url?`<a href="${U(i.url)}" target="_blank" rel="noopener noreferrer">${E(i.title)}</a>`:E(i.title)}${i.unconfirmed?' <span class="unc">unconfirmed</span>':""}<div class="meta">${i.km!=null?i.km+" km away · ":""}${E(ET(i.time))}${i.source?` · ${E(i.source)}`:""}</div></li>`).join("")}</ul>`:""}</div>`).join("")}</div>${(ev.checks||[]).filter(c=>!c.items.length).length?`<div class="meta">No nearby scanner reports yet on: ${E((ev.checks||[]).filter(c=>!c.items.length).map(c=>c.label).join(", "))}</div>`:""}
  ${ev.us?`<div class="gs-us">${(ev.nws||[]).length?`<div><b>NWS alerts in ${E(STN[ev.state]||ev.state)}</b><ul>${ev.nws.map(a=>`<li><a href="${U(a.url)}" target="_blank" rel="noopener noreferrer">${E(a.event)}</a> <span class="meta">until ${E(ET(a.expires))}</span></li>`).join("")}</ul></div>`:""}
   ${(ev.odin||[]).length?`<div><b>Utilities reporting to ODIN</b><ul>${ev.odin.map(u=>`<li>${E(u.name)}: ${u.outages?Number(u.outages).toLocaleString()+" outage(s)":"none reported"}</li>`).join("")}</ul></div>`:""}
   <div><b>FEMA open shelters nearby</b>${(ev.shelters||[]).length?`<ul>${ev.shelters.map(s=>`<li>${E(s.name)} <span class="meta">${E(s.city||"")}, ${E(s.state||"")} · ${E(s.km)} km</span></li>`).join("")}</ul>`:'<div class="meta">None listed within 250 km right now</div>'}</div></div>`:""}
  <div class="gs-res"><b>Help and official info</b> ${(ev.resources||[]).map(r=>`<a href="${U(r.url)}" ${/^#/.test(r.url)?"":'target="_blank" rel="noopener noreferrer"'}>${E(r.label)}${/^#/.test(r.url)?"":" ↗"}</a>`).join("")}</div></div></details>`}).join("")}
async function load(){if(G.busy)return;G.busy=true;
 try{if(!G.geo){const g=await fetch("api/gridstatus/sections.geojson");G.geo=await g.json()}
  const r=await fetch("api/gridstatus",{cache:"no-store"});const d=await r.json();if(!r.ok)throw d.error||r.status;G.d=d;G.t=Date.now();
  fresh();cards();wx();initMap();paintMap();
  if(!G.sel){const bad=Object.values(d.sections||{}).filter(s=>["offline","degraded","watch"].includes(s.status)).sort((a,b)=>ORDER[a.status]-ORDER[b.status])[0];
   if(G.st){const el=document.getElementById("gs_state");el.value=G.st;local()}else if(bad)selSec(bad.id,false)}}
 catch(e){const f=document.getElementById("gs_fresh");if(f)f.textContent="Grid status offline: "+e}finally{G.busy=false}}
function onShow(){if(!build())return;if(!G.d||Date.now()-G.t>240000)load();else setTimeout(()=>{initMap();if(G.map)G.map.invalidateSize()},60);setTimeout(()=>{if(G.map)G.map.invalidateSize()},350)}
const nav=document.querySelector(".tabs");
if(nav)nav.addEventListener("click",e=>{const b=e.target.closest('button[data-tab="grid"]');if(b)setTimeout(onShow,30)});
const wait=setInterval(()=>{if(build()){clearInterval(wait);const M=host();if(M&&M.style.display!="none")onShow()}},300);setTimeout(()=>clearInterval(wait),20000);
addEventListener("hashchange",()=>{const m=location.hash.match(/^#grid\/state\/([A-Z]{2})$/);if(m){const b=nav&&nav.querySelector('button[data-tab="grid"]');if(b&&!b.classList.contains("on"))b.click();setTimeout(()=>{build();pick(m[1])},100)}});
if(H0)setTimeout(()=>{const b=nav&&nav.querySelector('button[data-tab="grid"]');if(b&&!b.classList.contains("on"))b.click();setTimeout(onShow,60)},700);
setInterval(()=>{const M=host();if(M&&M.style.display!="none")load()},300000);
})();
