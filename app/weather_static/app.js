// ---- Weather tab (served by weather.py). The chosen location is stored only in this browser (localStorage, cookie fallback). ----
(()=>{"use strict";
const M=document.getElementById("tab-weather");if(!M)return;
const E=s=>(typeof esc=="function"?esc:(x=>String(x)))(s==null?"":String(s)),U=u=>E(typeof safeUrl=="function"?safeUrl(u||"#"):(u||"#"));
const DEF=null;   // no default place: the visitor picks one (search, "Use my location", or the shared location picker); nothing is pre-selected
const KEY="bn_wx_loc",UKEY="bn_wx_units",REFRESH=600000;
const WMO={0:["☀️","Clear"],1:["🌤","Mainly clear"],2:["⛅","Partly cloudy"],3:["☁️","Overcast"],45:["🌫","Fog"],48:["🌫","Rime fog"],51:["🌦","Light drizzle"],53:["🌦","Drizzle"],55:["🌧","Heavy drizzle"],
 56:["🌧","Freezing drizzle"],57:["🌧","Heavy freezing drizzle"],61:["🌦","Light rain"],63:["🌧","Rain"],65:["🌧","Heavy rain"],66:["🌧","Freezing rain"],67:["🌧","Heavy freezing rain"],
 71:["🌨","Light snow"],73:["🌨","Snow"],75:["❄️","Heavy snow"],77:["🌨","Snow grains"],80:["🌦","Light showers"],81:["🌧","Showers"],82:["⛈","Violent showers"],85:["🌨","Snow showers"],86:["❄️","Heavy snow showers"],
 95:["⛈","Thunderstorm"],96:["⛈","Thunderstorm, hail"],99:["⛈","Severe thunderstorm, hail"]};
const wmo=(c,day)=>{const w=WMO[c]||["🌡","Code "+c];if(day===0&&(c===0||c===1))return[c===0?"🌙":"🌙",w[1]];return w};
const etF=t=>t?new Date(t).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}):"—";
// Open-Meteo returns local wall-clock strings ("2026-10-31T14:00"); show them as-is in the location's own time
const lt=(s,o)=>{const m=/^(\d+)-(\d+)-(\d+)T(\d+):(\d+)/.exec(s||"");if(!m)return s||"";return new Date(Date.UTC(+m[1],m[2]-1,+m[3],+m[4],+m[5])).toLocaleString("en-US",Object.assign({timeZone:"UTC"},o))};
const cardinal=d=>d==null?"":["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][Math.round(d/22.5)%16];

// ---------- saved location (client-side only) ----------
function ck(n){const m=document.cookie.split("; ").find(c=>c.startsWith(n+"="));return m?decodeURIComponent(m.slice(n.length+1)):null}
function loadLoc(){for(const raw of [(()=>{try{return localStorage.getItem(KEY)}catch(_){return null}})(),ck(KEY)]){try{const j=JSON.parse(raw);if(j&&isFinite(j.lat)&&isFinite(j.lon))return j}catch(_){}}return null}
function saveLoc(l){const s=JSON.stringify({name:l.name,admin1:l.admin1||"",admin2:l.admin2||"",country:l.country||"",cc:l.cc||"",lat:+l.lat,lon:+l.lon,tz:l.tz||""});
 try{localStorage.setItem(KEY,s)}catch(_){}
 document.cookie=`${KEY}=${encodeURIComponent(s)}; max-age=31536000; path=/; SameSite=Lax`}
const W={loc:loadLoc(),saved:false,units:null,d:null,last:0,busy:false,shown:false,hits:[],sel:-1,qt:0};
W.saved=!!W.loc;if(!W.loc){try{const g=JSON.parse(localStorage.getItem("bn_loc")||sessionStorage.getItem("bn_loc_private")||"null");if(g&&isFinite(g.lat)&&isFinite(g.lon))W.loc={name:g.city||g.label,admin1:g.stname||"",admin2:"",country:g.country||"",cc:g.cc||"",lat:+g.lat,lon:+g.lon,tz:""}}catch(_){}}
W.units=(()=>{try{return localStorage.getItem(UKEY)}catch(_){return null}})()||(W.loc&&["US","PR","GU","VI","AS","MP","LR","MM"].includes(W.loc.cc)?"F":"C");
const T=c=>c==null?"—":Math.round(W.units=="F"?c*9/5+32:c)+"°",TU=()=>"°"+W.units;
const SP=k=>k==null?"—":W.units=="F"?Math.round(k*0.621371)+" mph":Math.round(k)+" km/h";
const PR=mm=>mm==null?"—":W.units=="F"?(mm/25.4).toFixed(2)+" in":mm.toFixed(1)+" mm";
const locLabel=l=>[l.name,l.admin1&&l.admin1!=l.name?l.admin1:"",l.country].filter(Boolean).join(", ");

// ---------- tab button placement + deep link (#weather) ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="weather"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="weather";tb.textContent="🌦 Weather";nav.appendChild(tb)}
const after=nav&&(nav.querySelector('button[data-tab="politics"]')||nav.querySelector('button[data-tab="heatmap"]')||nav.querySelector('button[data-tab="solar_seismic"]'));if(after&&tb)after.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.weather="weather";HASHTAB.weather="weather"}}catch(_){}

// ---------- skeleton ----------
const app=document.getElementById("wx_app");
app.innerHTML=`<div class=wx-bar>
 <div class=wx-search><input id=wx_q type=search placeholder="Search a city, region or country…" autocomplete=off role=combobox aria-autocomplete=list aria-expanded=false aria-controls=wx_list aria-label="Search location">
  <div class=wx-list id=wx_list role=listbox hidden></div></div>
 <button type=button id=wx_geo title="Ask the browser for your position (only when you click; nothing is sent anywhere except the weather lookups)">📍 Use my location</button>
 <div class=wx-seg role=group aria-label=Units><button type=button data-u=F>°F</button><button type=button data-u=C>°C</button></div>
 <span class=meta id=wx_msg></span></div>
<div id=wx_head class=meta>Loading…</div>
<div id=wx_alerts></div>
<div class="wx-card wx-radar" id=wx_radar style="margin-top:12px"><h3>Live radar <span class=meta id=wx_rfresh style="text-transform:none;letter-spacing:0"></span></h3>
 <div class=wx-rctl>
  <label class=wx-rsw><input type=checkbox id=wx_ron> Radar</label>
  <select id=wx_rsrc aria-label="Radar source"><option value=auto>Auto: NOAA in the US, RainViewer elsewhere</option><option value=noaa>NOAA / NWS MRMS (lower 48 US)</option><option value=rv>RainViewer (worldwide)</option></select>
  <button type=button id=wx_rplay aria-label="Pause radar loop">⏸ Pause</button>
  <input type=range id=wx_rfr min=0 max=0 value=0 aria-label="Radar frame">
  <span id=wx_rts class=wx-rts>—</span>
  <label class=wx-rop>Opacity <input type=range id=wx_rop min=10 max=100 step=5 aria-label="Radar opacity"></label>
 </div>
 <div id=wx_rmap class=wx-rmap role=region aria-label="Radar map"><div class=meta style="padding:12px">Pick a place to see radar around it.</div></div>
 <div class=wx-rleg id=wx_rleg></div><div class=meta id=wx_rnote></div></div>
<div class=wx-grid style="margin-top:12px">
 <div class=wx-card id=wx_now><h3>Current conditions</h3><div class=meta>Loading…</div></div>
 <div class=wx-card id=wx_hourly><h3>Next 48 hours</h3><div class=meta>Loading…</div></div>
 <div class="wx-card wx-full" id=wx_daily><h3>7-day forecast</h3><div class=meta>Loading…</div></div>
 <div class="wx-card wx-full" id=wx_nws style="display:none"><h3>National Weather Service forecast</h3></div>
 <div class="wx-card wx-full" id=wx_srcw><h3>Sources</h3><div id=wx_src class=wx-src></div></div>
</div>`;
const $w=id=>document.getElementById(id);
if(typeof hwAttach=="function")hwAttach(M.querySelector("#wx_top h2"),"weather",()=>"Pick a place with the search box (Open-Meteo's free GeoNames-based location search) or the opt-in 'Use my location' button (the browser asks first; the position is turned into a place name with OpenStreetMap's free Nominatim). Your choice is saved only in this browser (localStorage, with a cookie as backup) and is loaded automatically next time; no place is pre-selected (any place worldwide works). Forecasts and current conditions everywhere come from Open-Meteo. US locations also get the National Weather Service forecast, the nearest NWS station observation and NWS active alerts for that exact point. In Europe, official warnings come from MeteoAlarm (EUMETNET's national weather services), matched to the place by warning polygon or area name. GDACS (UN/European Commission) adds current major disaster events nearby anywhere in the world; other countries have no free official warning feed here yet. This computer caches each location for 10 minutes and the tab refreshes itself every 10 minutes. A source that fails shows as unavailable without breaking the rest. Live radar: a map centred on the chosen place with an animated loop of the last ~2 hours of radar (about one frame every 10 minutes). Inside the lower 48 US it defaults to NOAA/NWS MRMS quality-controlled base reflectivity (public domain, NOAA NCEP OpenGeo WMS); elsewhere, or if NOAA is down, it uses RainViewer's free radar mosaic (Weather data by RainViewer; tiles stop at zoom 7). Pick the source, opacity and frame yourself; new scans are checked every 5 minutes. Weather here never changes threat scores or ranks.");

// ---------- search / typeahead ----------
const q=$w("wx_q"),list=$w("wx_list");
function closeList(){list.hidden=true;q.setAttribute("aria-expanded","false");W.sel=-1}
function drawList(){if(!W.hits.length){list.innerHTML=`<div class=meta style="padding:6px 10px">${q.value.trim().length<2?"Type at least 2 letters":"No matches"}</div>`}
 else list.innerHTML=W.hits.map((h,i)=>`<div role=option id=wx_o${i} data-i=${i} aria-selected=${i==W.sel}>${E(h.name)}<span class=meta>${E([h.admin1,h.admin2&&h.admin2!=h.admin1?h.admin2:"",h.country].filter(Boolean).join(" · "))}${h.pop?" · pop "+(+h.pop).toLocaleString():""}</span></div>`).join("");
 list.hidden=false;q.setAttribute("aria-expanded","true");if(W.sel>=0)q.setAttribute("aria-activedescendant","wx_o"+W.sel)}
async function search(){const v=q.value.trim();if(v.length<2){W.hits=[];drawList();return}
 try{const r=await fetch("api/weather/geocode?q="+encodeURIComponent(v),{cache:"no-store"});const j=await r.json();if(q.value.trim()!=v)return;
  W.hits=j.results||[];W.sel=W.hits.length?0:-1;drawList();if(j.error)$w("wx_msg").textContent=j.error}catch(e){list.innerHTML=`<div class=meta style="padding:6px 10px">Location search unavailable: ${E(e)}</div>`;list.hidden=false}}
q.addEventListener("input",()=>{clearTimeout(W.qt);W.qt=setTimeout(search,250)});
q.addEventListener("keydown",e=>{if(list.hidden&&e.key!="Enter")return;
 if(e.key=="ArrowDown"){e.preventDefault();W.sel=Math.min(W.hits.length-1,W.sel+1);drawList()}
 else if(e.key=="ArrowUp"){e.preventDefault();W.sel=Math.max(0,W.sel-1);drawList()}
 else if(e.key=="Enter"){e.preventDefault();if(W.hits[W.sel])pick(W.hits[W.sel]);else search()}
 else if(e.key=="Escape")closeList()});
list.addEventListener("mousedown",e=>{const o=e.target.closest("[data-i]");if(o){e.preventDefault();pick(W.hits[+o.dataset.i])}});
q.addEventListener("blur",()=>setTimeout(closeList,150));
function pick(h){closeList();q.value="";W.loc=h;W.saved=true;saveLoc(h);$w("wx_msg").textContent="✓ saved in this browser: "+locLabel(h);load(false)}
$w("wx_geo").onclick=()=>{if(!navigator.geolocation){$w("wx_msg").textContent="This browser has no location access.";return}
 $w("wx_msg").textContent="Asking the browser for your location…";
 navigator.geolocation.getCurrentPosition(async p=>{const lat=+p.coords.latitude.toFixed(4),lon=+p.coords.longitude.toFixed(4);let h={name:"My location",lat,lon,cc:""};
  try{const j=await (await fetch(`api/weather/reverse?lat=${lat}&lon=${lon}`)).json();if(j.result)h=Object.assign(h,j.result)}catch(_){}
  pick(h)},err=>{$w("wx_msg").textContent="Location not shared ("+(err.message||"denied")+"). Search for a place instead."},{timeout:15000,maximumAge:600000})};
M.querySelectorAll(".wx-seg button").forEach(b=>{b.classList.toggle("on",b.dataset.u==W.units);b.onclick=()=>{W.units=b.dataset.u;try{localStorage.setItem(UKEY,W.units)}catch(_){}
 M.querySelectorAll(".wx-seg button").forEach(x=>x.classList.toggle("on",x==b));if(W.d)render()}});

// ---------- data ----------
async function load(force){if(!W.loc){$w("wx_head").innerHTML='<b>Pick a place</b> <span class=meta>— search above or use “📍 Use my location”. No location is pre-selected; your choice stays in this browser.</span>';["wx_now","wx_hourly","wx_daily"].forEach(i=>{const c=$w(i);if(c&&c.querySelector(".meta"))c.querySelector(".meta").textContent="Choose a location to see the forecast."});return}
 try{radarLoc()}catch(_){}
 if(W.busy)return;W.busy=true;const l=W.loc;
 const p=new URLSearchParams({lat:l.lat,lon:l.lon,cc:l.cc||"",name:l.name||"",admin1:l.admin1||"",admin2:l.admin2||""});if(force)p.set("force","1");
 $w("wx_head").innerHTML=`<span class=wx-loc>${E(locLabel(l))}</span> <span class=meta>· loading live data…</span>`;
 try{const r=await fetch("api/weather?"+p,{cache:"no-store"});const d=await r.json();if(!r.ok)throw d.error||r.status;W.d=d;W.last=Date.now();render()}
 catch(e){$w("wx_head").innerHTML=`<span class=wx-loc>${E(locLabel(l))}</span><div class=warn>Weather unavailable: ${E(e)}</div>`}
 finally{W.busy=false}}
const S=k=>(W.d&&W.d.sources[k])||null,OK=k=>S(k)&&S(k).ok?S(k).data:null;
const sevC=s=>({Extreme:"ex",Severe:"sv",Moderate:"md",Minor:"mi"}[s]||"");
function alertHTML(a,src){return `<div class="wx-al ${sevC(a.severity)}"><div><span class=sev>${E((a.severity||"Unknown").toUpperCase())}</span><b>${E(a.event)}</b>
 <span class=meta> · ${E(a.sender||src)}${a.level?" · MeteoAlarm level "+E(a.level):""}</span></div>
 ${a.headline?`<div style="margin-top:4px">${E(a.headline)}</div>`:""}
 <div class=meta style="margin-top:4px">From ${etF(a.onset)} until ${etF(a.expires)} · urgency ${E(a.urgency||"—")} · certainty ${E(a.certainty||"—")}${a.msgtype&&a.msgtype!="Alert"?" · "+E(a.msgtype):""}</div>
 ${a.area?`<div class=meta>Area: ${E(a.area.length>260?a.area.slice(0,260)+"…":a.area)}</div>`:""}
 <details><summary>Official text</summary><pre>${E(a.description||"")}${a.instruction?"\n\nWhat to do:\n"+E(a.instruction):""}</pre></details>
 <div class=meta style="margin-top:4px">Source: <a href="${U(a.url)}" target=_blank rel="noopener noreferrer">${E(src)}</a>${a.link?` · <a href="${U(a.link)}" target=_blank rel="noopener noreferrer">official page</a>`:""} · matched by ${E(a.match||"—")}</div></div>`}
function render(){const d=W.d,l=W.loc,om=OK("open_meteo");
 const pts=OK("nws_points");
 $w("wx_head").innerHTML=`<span class=wx-loc>${E(locLabel(l))}</span> <span class=meta>· ${(+d.lat).toFixed(3)}, ${(+d.lon).toFixed(3)}${om?" · local time zone "+E(om.timezone)+" ("+E(om.timezone_abbreviation)+")":""}${pts?` · NWS ${E(pts.office)} grid ${E(pts.grid)}, zone ${E(pts.zone)}`:""}
  · <b>Last updated ${etF(d.generated)}</b>${d.cached?" (cached copy, refreshed every 10 min)":""} · next auto-refresh in ~10 min${W.saved?"":" · default location (nothing saved yet)"}</span>`;
 // alerts
 let h="",n=0;
 if(d.us){const a=OK("nws_alerts");if(a){n+=a.length;h+=a.map(x=>alertHTML(x,"National Weather Service")).join("")}else h+=`<div class=warn>NWS alerts unavailable: ${E((S("nws_alerts")||{}).error)}</div>`}
 const ma=S("meteoalarm");if(ma){if(ma.ok){n+=ma.data.alerts.length;h+=ma.data.alerts.map(x=>alertHTML(x,"MeteoAlarm")).join("");const el=Object.entries(ma.data.elsewhere||{});
   if(el.length)h+=`<div class=meta style="margin:6px 0">Elsewhere in this country (not matched to this place): ${el.map(([k,v])=>E(k)+(v>1?" ×"+v:"")).join(", ")} · <a href="${U(ma.data.country_page)}" target=_blank rel="noopener noreferrer">MeteoAlarm country map</a></div>`}
  else h+=`<div class=warn>MeteoAlarm warnings unavailable: ${E(ma.error)}</div>`}
 const gd=S("gdacs");if(gd&&gd.ok&&gd.data.length){h+=`<div class=meta style="margin:8px 0 2px">Major disaster events nearby (GDACS):</div>`+gd.data.map(g=>`<div class="wx-al ${g.level=="Red"?"ex":g.level=="Orange"?"sv":"mi"}"><span class=sev>GDACS ${E((g.level||"").toUpperCase())}</span><b>${E(g.type)}: ${E(g.name)}</b><span class=meta> · ${g.dist_km} km away · ${etF(g.from+"Z")}</span>
   <div class=meta>${E(g.summary)} · <a href="${U(g.url)}" target=_blank rel="noopener noreferrer">GDACS report</a></div></div>`).join("")}
 else if(gd&&!gd.ok)h+=`<div class=meta>GDACS unavailable: ${E(gd.error)}</div>`;
 const head=`<h3 style="font-size:13px;margin:0 0 6px;color:var(--mu);text-transform:uppercase;letter-spacing:.06em">Active alerts${n?` <span style="color:var(--hi)">· ${n}</span>`:""}</h3>`;
 const none=!n&&(d.us?OK("nws_alerts"):ma&&ma.ok)?`<div class=meta><span class=wx-ok>✓</span> No active official ${d.us?"NWS":"MeteoAlarm"} alerts for this location right now.</div>`:"";
 $w("wx_alerts").innerHTML=`<div class=wx-card>${head}${none}${h}${d.alerts_note?`<div class=warn>${E(d.alerts_note)}</div>`:""}</div>`;
 // current
 if(om&&om.current){const c=om.current,[ic,tx]=wmo(c.weather_code,c.is_day),ob=OK("nws_obs");
  $w("wx_now").innerHTML=`<h3>Current conditions <span class=meta style="text-transform:none;letter-spacing:0">· model ${lt(c.time,{hour:"numeric",minute:"2-digit"})} local</span></h3>
  <div class=wx-now><div class=ic>${ic}</div><div><div class=t>${T(c.temperature_2m)}</div><div>${E(tx)}</div></div></div>
  <div class=wx-kv><div><span>Feels like</span> ${T(c.apparent_temperature)}</div><div><span>Humidity</span> ${c.relative_humidity_2m}%</div>
   <div><span>Wind</span> ${SP(c.wind_speed_10m)} ${cardinal(c.wind_direction_10m)}</div><div><span>Gusts</span> ${SP(c.wind_gusts_10m)}</div>
   <div><span>Precip (now)</span> ${PR(c.precipitation)}</div><div><span>UV index</span> ${c.uv_index??"—"}</div>
   <div><span>Cloud cover</span> ${c.cloud_cover??"—"}%</div><div><span>Pressure</span> ${c.pressure_msl!=null?Math.round(c.pressure_msl)+" hPa":"—"}</div></div>
  ${ob?`<div class=meta style="margin-top:10px">NWS station <a href="${U(ob.link)}" target=_blank rel="noopener noreferrer">${E(ob.station)}</a> (${E(ob.station_name)}, ${ob.dist_km} km): ${E(ob.text||"")} ${T(ob.temp_c)}, dew point ${T(ob.dew_c)}, humidity ${ob.rh!=null?Math.round(ob.rh)+"%":"—"}, wind ${SP(ob.wind_kmh)} ${cardinal(ob.wind_dir)}${ob.gust_kmh?", gusts "+SP(ob.gust_kmh):""} · observed ${etF(ob.time)}</div>`:d.us&&S("nws_obs")?`<div class=meta style="margin-top:10px">NWS station observation unavailable: ${E(S("nws_obs").error)}</div>`:""}
  <div class=meta style="margin-top:6px">Open-Meteo model data</div>`}
 else $w("wx_now").innerHTML=`<h3>Current conditions</h3><div class=warn>Open-Meteo unavailable: ${E((S("open_meteo")||{}).error)}</div>`;
 // hourly chart
 if(om&&om.hourly){const H=om.hourly,N=H.time.length,w=760,ht=230,pl=34,pr=34,pt=14,pb=34,iw=w-pl-pr,ih=ht-pt-pb;
  const tv=H.temperature_2m.map(c=>c==null?null:(W.units=="F"?c*9/5+32:c)),fv=H.apparent_temperature.map(c=>c==null?null:(W.units=="F"?c*9/5+32:c));
  const all=[...tv,...fv].filter(v=>v!=null);let lo=Math.floor(Math.min(...all)-2),hi=Math.ceil(Math.max(...all)+2);
  const X=i=>pl+i*iw/(N-1),Y=v=>pt+ih-(v-lo)/(hi-lo)*ih,P=v=>pt+ih-(v/100)*ih;
  const line=arr=>arr.map((v,i)=>v==null?"":`${i&&arr[i-1]!=null?"L":"M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  let g=`<svg class=wx-chart viewBox="0 0 ${w} ${ht}" role=img aria-label="Temperature, feels-like and chance of precipitation for the next 48 hours">`;
  for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4;g+=`<line x1=${pl} x2=${w-pr} y1=${Y(v)} y2=${Y(v)} stroke="#252b33"/><text x=${pl-4} y=${Y(v)+4} text-anchor=end>${Math.round(v)}°</text><text x=${w-pr+4} y=${P(k*25)+4}>${k*25}%</text>`}
  const bw=iw/N*0.7;H.precipitation_probability.forEach((p,i)=>{if(p)g+=`<rect x=${(X(i)-bw/2).toFixed(1)} y=${P(p).toFixed(1)} width=${bw.toFixed(1)} height=${(pt+ih-P(p)).toFixed(1)} fill="#4aa3ff" opacity=.35><title>${lt(H.time[i],{weekday:"short",hour:"numeric"})}: ${p}% chance of precipitation</title></rect>`});
  H.time.forEach((t,i)=>{const hr=+t.slice(11,13);if(hr%6==0)g+=`<line x1=${X(i)} x2=${X(i)} y1=${pt} y2=${pt+ih} stroke="#1f252d"/><text x=${X(i)} y=${ht-pb+14} text-anchor=middle>${hr==0?lt(t,{weekday:"short"}):lt(t,{hour:"numeric"})}</text>`});
  g+=`<path d="${line(fv)}" fill=none stroke="#fa8c16" stroke-width=1.5 stroke-dasharray="4 3"/><path d="${line(tv)}" fill=none stroke="#ff4d4f" stroke-width=2.2/>`;
  tv.forEach((v,i)=>{if(v!=null)g+=`<circle cx=${X(i).toFixed(1)} cy=${Y(v).toFixed(1)} r=6 fill=transparent><title>${lt(H.time[i],{weekday:"short",hour:"numeric"})}: ${Math.round(v)}${TU()}, feels ${Math.round(fv[i])}°, ${H.precipitation_probability[i]??0}% precip, wind ${SP(H.wind_speed_10m[i])} gusts ${SP(H.wind_gusts_10m[i])}, humidity ${H.relative_humidity_2m[i]}%, UV ${H.uv_index[i]}</title></circle>`});
  g+=`</svg>`;
  const gmax=Math.max(...H.wind_gusts_10m.filter(v=>v!=null)),pmax=Math.max(...H.precipitation_probability.filter(v=>v!=null)),uvmax=Math.max(...H.uv_index.filter(v=>v!=null));
  $w("wx_hourly").innerHTML=`<h3>Next 48 hours <span class=meta style="text-transform:none;letter-spacing:0">· local time · <span style="color:#ff4d4f">━ temperature</span> · <span style="color:#fa8c16">┅ feels like</span> · <span style="color:#4aa3ff">▮ chance of precipitation</span> · hover for details</span></h3>${g}
  <div class=meta>Peak gust ${SP(gmax)} · highest precipitation chance ${pmax}% · max UV ${uvmax}</div>`}
 else $w("wx_hourly").innerHTML=`<h3>Next 48 hours</h3><div class=warn>Hourly forecast unavailable.</div>`;
 // daily
 if(om&&om.daily){const D=om.daily;$w("wx_daily").innerHTML=`<h3>7-day forecast</h3><div class=wx-days>${D.time.map((t,i)=>{const[ic,tx]=wmo(D.weather_code[i]);
   return `<div class=wx-day title="${E(tx)} · feels ${T(D.apparent_temperature_min[i])}–${T(D.apparent_temperature_max[i])} · sunrise ${lt(D.sunrise[i],{hour:"numeric",minute:"2-digit"})}, sunset ${lt(D.sunset[i],{hour:"numeric",minute:"2-digit"})}">
   <div>${i?lt(t+"T12:00",{weekday:"short",month:"short",day:"numeric"}):"Today"}</div><div class=ic>${ic}</div><div>${E(tx)}</div>
   <div><b>${T(D.temperature_2m_max[i])}</b> <span class=lo>${T(D.temperature_2m_min[i])}</span></div>
   <div class=pp>💧 ${D.precipitation_probability_max[i]??"—"}% · ${PR(D.precipitation_sum[i])}</div>
   <div class=meta>💨 ${SP(D.wind_speed_10m_max[i])}, gusts ${SP(D.wind_gusts_10m_max[i])}</div><div class=meta>UV ${D.uv_index_max[i]??"—"}</div></div>`}).join("")}</div>`}
 else $w("wx_daily").innerHTML=`<h3>7-day forecast</h3><div class=warn>Daily forecast unavailable.</div>`;
 // NWS text forecast
 const nf=S("nws_forecast");
 if(d.us&&nf){$w("wx_nws").style.display="";$w("wx_nws").innerHTML=`<h3>National Weather Service forecast${pts?` <span class=meta style="text-transform:none;letter-spacing:0">· ${E(pts.office)} office · <a href="https://forecast.weather.gov/MapClick.php?lat=${d.lat}&lon=${d.lon}" target=_blank rel="noopener noreferrer">forecast.weather.gov</a></span>`:""}</h3>`+
  (nf.ok?`<div class=wx-nws>${nf.data.periods.slice(0,8).map(p=>`<div><b>${E(p.name)}</b> · ${p.temperatureUnit=="F"?(W.units=="F"?p.temperature+"°F":Math.round((p.temperature-32)*5/9)+"°C"):E(p.temperature)}${p.probabilityOfPrecipitation!=null?" · 💧 "+p.probabilityOfPrecipitation+"%":""} · ${E(p.windSpeed)} ${E(p.windDirection)}<br>${E(p.detailedForecast)}</div>`).join("")}</div><div class=meta>NWS forecast issued ${etF(nf.data.updated)}</div>`
   :`<div class=warn>NWS forecast unavailable: ${E(nf.error)}</div>`)}
 else $w("wx_nws").style.display="none";
 // sources
 const lab={open_meteo:"Open-Meteo forecast",nws_points:"NWS grid lookup",nws_forecast:"NWS forecast",nws_hourly:"NWS hourly forecast",nws_obs:"NWS station observation",nws_alerts:"NWS active alerts",meteoalarm:"MeteoAlarm warnings",gdacs:"GDACS disaster events"};
 $w("wx_src").innerHTML=Object.entries(d.sources).map(([k,s])=>`<div>${s.ok?"<span class=wx-ok>●</span>":"<span class=wx-bad>●</span>"} ${s.url?`<a href="${U(s.url)}" target=_blank rel="noopener noreferrer">${E(lab[k]||s.label)}</a>`:E(lab[k]||s.label)} <span class=meta>· ${s.ok?"ok":"unavailable: "+E(s.error)} · fetched ${etF(s.fetched)}${s.secs!=null?" · "+s.secs+" s":""}</span></div>`).join("")+
  `<div class=meta style="grid-column:1/-1;margin-top:4px">Forecast data © Open-Meteo.com (CC BY 4.0). US data: NOAA National Weather Service. European warnings: MeteoAlarm / EUMETNET. Disaster events: GDACS (UN OCHA / European Commission JRC). Location search: GeoNames via Open-Meteo; reverse lookup © OpenStreetMap contributors.</div>`}

// ---------- t244: live radar (Leaflet; tiles load straight from NOAA / RainViewer, frame lists via api/weather/radar) ----------
const RKEY="bn_wx_radar",RREF=300000;
const RP=(()=>{try{return JSON.parse(localStorage.getItem(RKEY)||"{}")||{}}catch(_){return{}}})();
const R={map:null,base:null,mk:null,on:RP.on!==false,src:["auto","noaa","rv"].includes(RP.src)?RP.src:"auto",op:isFinite(RP.op)?+RP.op:0.7,
 d:null,layers:[],times:[],i:0,play:true,tick:0,hold:0,used:null,key:null,fell:false,last:0,timer:0,busy:false};
const rSave=()=>{try{localStorage.setItem(RKEY,JSON.stringify({on:R.on,src:R.src,op:R.op}))}catch(_){}};
const etT=ms=>new Date(ms).toLocaleTimeString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"})+" ET";
const RV_A='Radar: <a href="https://www.rainviewer.com/" target=_blank rel="noopener noreferrer">Weather data by RainViewer</a>';
const NO_A='Radar: <a href="https://www.nssl.noaa.gov/projects/mrms/" target=_blank rel="noopener noreferrer">NOAA/NWS MRMS</a> via <a href="https://opengeo.ncep.noaa.gov/" target=_blank rel="noopener noreferrer">NCEP OpenGeo</a> (public domain)';
const inConus=l=>l&&(!l.cc||l.cc=="US")&&l.lat>=24&&l.lat<=50&&l.lon>=-125.5&&l.lon<=-66;
const rWant=()=>R.src=="auto"?(inConus(W.loc)&&!R.fell?"noaa":"rv"):R.src;
const NEX=[[5,"#00efe7"],[10,"#009cf7"],[15,"#0000f7"],[20,"#00ff00"],[25,"#03b703"],[30,"#087305"],[35,"#ffff00"],[40,"#ecce00"],[45,"#fe9300"],[50,"#ff0000"],[55,"#bd0000"],[65,"#fe00fe"],[70,"#9c52c6"],[75,"#fefefe"]];
function rLegend(){const g=$w("wx_rleg");if(!g)return;
 if(R.used=="rv")g.innerHTML=`<span class=meta>Reflectivity (dBZ)</span><div class=wx-rbar>${NEX.map(([v,c])=>`<span style="background:${c}" title="${v} dBZ"><i>${v}</i></span>`).join("")}</div><span class=meta>light rain → heavy rain → hail · NEXRAD Level III colors</span>`;
 else if(R.used=="noaa")g.innerHTML=`<span class=meta>Reflectivity</span><div class="wx-rbar wx-rgrad" style="background:linear-gradient(90deg,#7c89af,#4660a0,#59bdbd,#30d65b,#0ece14,#0a6b0b,#cec802,#ffb100,#ff0000,#ff00ff)"></div><div class=wx-rlab><span>light</span><span>moderate</span><span>heavy</span><span>intense / hail</span></div><span class=meta>MRMS quality-controlled base reflectivity, 1 km grid, colors as rendered by NOAA</span>`;
 else g.innerHTML=""}
function rClear(){R.layers.forEach(x=>{try{R.map.removeLayer(x)}catch(_){}});R.layers=[];R.times=[]}
function rShow(i){if(!R.layers.length)return;R.i=(i+R.layers.length)%R.layers.length;R.layers.forEach((x,k)=>x.setOpacity(k==R.i?R.op:0));
 $w("wx_rfr").value=R.i;$w("wx_rts").textContent=etT(R.times[R.i])+(R.i==R.layers.length-1?" · latest":"")}
function rBuild(){if(!R.map)return;rClear();R.used=null;
 if(!R.on||!R.d){rLegend();$w("wx_rts").textContent=R.on?"—":"radar off";return}
 let use=rWant(),note="";
 if(use=="noaa"&&!(R.d.noaa&&R.d.noaa.ok&&R.d.noaa.data.length)){note="NOAA radar unavailable right now ("+E((R.d.noaa||{}).error||"no frames")+"); showing RainViewer.";use="rv"}
 if(use=="rv"&&!(R.d.rainviewer&&R.d.rainviewer.ok&&R.d.rainviewer.data.frames.length)){$w("wx_rnote").textContent="Radar unavailable: "+((R.d.rainviewer||{}).error||"no frames");rLegend();return}
 if(use=="noaa"){R.times=R.d.noaa.data.map(t=>Date.parse(t));
  R.layers=R.d.noaa.data.map(t=>L.tileLayer.wms(R.d.noaa_wms,{layers:R.d.noaa_layer,format:"image/png",transparent:true,version:"1.3.0",TIME:t,opacity:0,maxZoom:12,attribution:NO_A,className:"wx-rtile"}));
  if(!inConus(W.loc))note+=(note?" ":"")+"NOAA's MRMS mosaic covers the lower 48 US only; switch to RainViewer for this place."}
 else{const rv=R.d.rainviewer.data;R.times=rv.frames.map(f=>f.time*1000);
  R.layers=rv.frames.map(f=>L.tileLayer(rv.host+f.path+"/256/{z}/{x}/{y}/6/1_0.png",{maxNativeZoom:7,maxZoom:12,opacity:0,attribution:RV_A,className:"wx-rtile"}));
  if(R.map.getZoom()>7)note+=(note?" ":"")+"RainViewer's free tiles stop at zoom 7, so the radar is upscaled when you zoom in further."}
 R.used=use;let ok=0,bad=0,lat=R.layers[R.layers.length-1];
 lat.on("tileload",()=>ok++);lat.on("tileerror",()=>{bad++;if(R.used=="noaa"&&R.src=="auto"&&bad>=6&&bad>ok*2&&!R.fell){R.fell=true;$w("wx_rnote").textContent="NOAA radar tiles failing; switched to RainViewer.";rBuild()}});
 R.layers.forEach(x=>x.addTo(R.map));
 $w("wx_rfr").max=R.layers.length-1;rShow(R.layers.length-1);
 $w("wx_rnote").textContent=note;rLegend();rFresh()}
function rFresh(){const f=$w("wx_rfresh");if(!f)return;if(!R.on||!R.times.length){f.textContent=R.on?"":"· off";return}
 const t=R.times[R.times.length-1],age=Math.max(0,Math.round((Date.now()-t)/60000));
 f.innerHTML=`· <b>Radar updated ${etT(t)}</b> (${age} min ago) · ${R.used=="noaa"?"NOAA/NWS MRMS":"RainViewer"} · ${R.times.length} frames, ~${R.used=="noaa"?10:10} min apart · checks for new scans every 5 min`}
// direct browser fallback (both upstreams send CORS *): used when api/weather/radar is unreachable, e.g. while the server is still syncing after a deploy
const R_WMS="https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows";
async function rDirect(){const ok=data=>({ok:true,data}),bad=e=>({ok:false,error:String(e).slice(0,200)});
 const [n,v]=await Promise.all([
  fetch(R_WMS+"?service=WMS&request=GetCapabilities&version=1.3.0",{cache:"no-store"}).then(r=>r.text()).then(x=>{const m=/<Dimension[^>]*name="time"[^>]*>([^<]+)<\/Dimension>/.exec(x);if(!m)throw "no time dimension";
   const ts=m[1].split(",").map(t=>t.trim()).filter(Boolean).sort().reverse(),out=[];let last=null;
   for(const t of ts){const d=Date.parse(t);if(last==null||last-d>=570000){out.push(t);last=d}if(out.length>=12)break}return ok(out.reverse())}).catch(bad),
  fetch("https://api.rainviewer.com/public/weather-maps.json",{cache:"no-store"}).then(r=>r.json()).then(j=>ok({host:j.host||"https://tilecache.rainviewer.com",frames:((j.radar||{}).past||[]).filter(f=>f.path).slice(-12)})).catch(bad)]);
 return {noaa:n,rainviewer:v,noaa_wms:R_WMS,noaa_layer:"conus_bref_qcd",direct:true}}
async function rFetch(){if(R.busy)return;R.busy=true;
 try{let d;try{const r=await fetch("api/weather/radar",{cache:"no-store"});d=await r.json();if(!r.ok||!d.noaa)throw 0}catch(_){d=await rDirect()}
  const k=JSON.stringify([d.noaa&&d.noaa.data,d.rainviewer&&d.rainviewer.data&&d.rainviewer.data.frames]);R.d=d;R.last=Date.now();
  if(k!=R.key||!R.layers.length){R.key=k;rBuild()}else rFresh()}
 catch(e){$w("wx_rnote").textContent="Radar frame list unavailable: "+e}
 finally{R.busy=false}}
function rLoop(){clearInterval(R.timer);R.timer=setInterval(()=>{if(!R.play||!R.layers.length||!shown()||document.hidden)return;
 if(R.i==R.layers.length-1&&R.hold++<3)return;R.hold=0;rShow(R.i+1)},650)}
function radarInit(){if(R.map||typeof L=="undefined"||!W.loc)return;const el=$w("wx_rmap");if(!el||!el.offsetWidth)return;el.innerHTML="";
 R.map=L.map(el,{minZoom:3,maxZoom:12,worldCopyJump:true,scrollWheelZoom:false}).setView([+W.loc.lat,+W.loc.lon],8);
 R.map.on("click",()=>R.map.scrollWheelZoom.enable());
 R.base=window.bnBaseLayer?bnBaseLayer(R.map,{maxZoom:12}):L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:12,className:"bn-tiles"}).addTo(R.map);
 R.mk=L.circleMarker([+W.loc.lat,+W.loc.lon],{radius:7,color:"#fff",weight:2,fillColor:"#4aa3ff",fillOpacity:.9}).addTo(R.map).bindTooltip(E(locLabel(W.loc)));
 R.loc=W.loc.lat+","+W.loc.lon;R.map.on("zoomend",()=>{if(R.used=="rv"&&R.map.getZoom()>7&&!/zoom 7/.test($w("wx_rnote").textContent))$w("wx_rnote").textContent="RainViewer's free tiles stop at zoom 7, so the radar is upscaled when you zoom in further."});
 rLoop();rFetch()}
function radarLoc(){if(!W.loc)return;if(!R.map){if(shown())setTimeout(radarInit,0);return}const k=W.loc.lat+","+W.loc.lon;if(k==R.loc)return;R.loc=k;
 R.map.setView([+W.loc.lat,+W.loc.lon],8);R.mk.setLatLng([+W.loc.lat,+W.loc.lon]).setTooltipContent(E(locLabel(W.loc)));R.fell=false;
 if(R.used!=rWant())rBuild();else rLegend()}
$w("wx_ron").checked=R.on;$w("wx_rsrc").value=R.src;$w("wx_rop").value=Math.round(R.op*100);
$w("wx_ron").onchange=e=>{R.on=e.target.checked;rSave();M.querySelector(".wx-rctl").classList.toggle("off",!R.on);if(R.on&&!R.d)rFetch();else rBuild()};
M.querySelector(".wx-rctl").classList.toggle("off",!R.on);
$w("wx_rsrc").onchange=e=>{R.src=e.target.value;R.fell=false;rSave();rBuild()};
$w("wx_rop").oninput=e=>{R.op=+e.target.value/100;rSave();rShow(R.i)};
$w("wx_rplay").onclick=()=>{R.play=!R.play;$w("wx_rplay").textContent=R.play?"⏸ Pause":"▶ Play";$w("wx_rplay").setAttribute("aria-label",(R.play?"Pause":"Play")+" radar loop")};
$w("wx_rfr").oninput=e=>{if(R.play)$w("wx_rplay").click();rShow(+e.target.value)};
setInterval(()=>{if(R.map&&R.on&&shown()&&!document.hidden)rFetch()},RREF);
setInterval(rFresh,60000);

// ---------- show / refresh ----------
const shown=()=>M.style.display!="none";
function onShow(){if(!W.d||Date.now()-W.last>REFRESH)load(false);setTimeout(()=>{radarInit();if(R.map){R.map.invalidateSize();if(R.on&&Date.now()-R.last>RREF)rFetch()}},50)}
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="weather")setTimeout(onShow,0)});
$w("wx_ref").onclick=e=>{e.stopPropagation();load(true)};
setInterval(()=>{if(shown())load(false)},REFRESH);
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&shown())onShow()});
if((location.hash||"")=="#weather")setTimeout(()=>{const b=document.querySelector('.tabs button[data-tab="weather"]');if(b&&!b.classList.contains("on"))b.click()},350);
})();
