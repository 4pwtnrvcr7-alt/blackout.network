/* blackout.network · Solar & Seismic live layer (t239-t241): live Sun imagery + NOAA SWPC status cards, flares / sunspots / CME impact
   countdown / 3-day Kp, and a real-time USGS world earthquake map. Data: /api/solar_seismic/live (server-cached NOAA SWPC + NASA CCMC),
   USGS GeoJSON straight from earthquake.usgs.gov (CORS) with /api/solar_seismic/usgs/<feed> as a cached fallback. */
(function(){
const TAB=document.getElementById("tab-solar");if(!TAB)return;
const g=id=>document.getElementById(id);
const E=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const TZ="America/New_York";
const hm=d=>new Date(d).toLocaleTimeString("en-US",{timeZone:TZ,hour:"numeric",minute:"2-digit"})+" ET";
const dt=d=>new Date(d).toLocaleString("en-US",{timeZone:TZ,weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
const ago=ms=>{const s=Math.max(0,Math.round((Date.now()-ms)/1000));return s<90?s+" s ago":s<5400?Math.round(s/60)+" min ago":s<172800?Math.round(s/3600)+" h ago":Math.round(s/86400)+" d ago"};
const LV={ok:"#52c41a",watch:"#ffd666",warn:"#faad14",high:"#ff7a45",bad:"#ff4d4f",ext:"#b37feb",mu:"#8b95a3"};
const FLC={A:"#6b7785",B:"#4aa3ff",C:"#52c41a",M:"#faad14",X:"#ff4d4f"};
const flc=c=>FLC[(c||"?")[0]]||LV.mu;
const kpCol=k=>k==null?LV.mu:k>=8.67?LV.ext:k>=7.67?LV.bad:k>=6.67?LV.high:k>=5.67?LV.warn:k>=4.67?LV.watch:k>=4?"#d4b106":LV.ok;
const SWPC='<a href="https://www.swpc.noaa.gov/" target=_blank rel=noopener>swpc.noaa.gov</a>';
const IMG=[["sdo_0193","SDO 193 Å","Corona & coronal holes","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg","https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_1024_0193.mp4"],
 ["sdo_0171","SDO 171 Å","Quiet corona & loops","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0171.jpg","https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_1024_0171.mp4"],
 ["sdo_0304","SDO 304 Å","Chromosphere & prominences","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0304.jpg","https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_1024_0304.mp4"],
 ["sdo_0131","SDO 131 Å","Flaring regions","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0131.jpg","https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_1024_0131.mp4"],
 ["sdo_hmiic","SDO HMI","Visible light: sunspots","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIIC.jpg","https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_1024_HMIIC.mp4"],
 ["sdo_hmib","SDO magnetogram","Magnetic polarity","https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIB.jpg",null],
 ["soho_c2","SOHO LASCO C2","Coronagraph: CMEs leaving the Sun","https://soho.nascom.nasa.gov/data/realtime/c2/1024/latest.jpg","https://soho.nascom.nasa.gov/data/LATEST/current_c2.mp4"],
 ["soho_c3","SOHO LASCO C3","Wide coronagraph (30 solar radii)","https://soho.nascom.nasa.gov/data/realtime/c3/1024/latest.jpg","https://soho.nascom.nasa.gov/data/LATEST/current_c3.mp4"],
 ["soho_eit195","SOHO EIT 195 Å","Extreme ultraviolet corona","https://soho.nascom.nasa.gov/data/realtime/eit_195/1024/latest.jpg",null]];
const MOV=[["0171","AIA 171 Å","Quiet corona & coronal loops"],["0304","AIA 304 Å","Chromosphere & prominences"],["0193","AIA 193 Å","Corona & coronal holes"],["0131","AIA 131 Å","Flaring regions"],["HMIIC","HMI","Visible light: sunspots"]];
const FEEDS=[["all_hour","Past hour · all"],["all_day","Past day · all"],["2.5_day","Past day · M2.5+"],["4.5_week","Past week · M4.5+"]];
const S={on:false,built:false,img:0,cyc:null,d:null,feed:"all_day",q:null,qT:0,seen:null,newIds:new Map(),map:null,lay:null,sig:null,timers:[]};

// ---------------------------------------------------------------- skeleton
function build(){
 const top=g("ss_top");if(!top)return false;
 const a=document.createElement("section");a.className="pn ssl";a.id="ssl_sun";
 a.innerHTML=`<h2><span class=ssl-ic>☀</span> Live Sun <span class=meta>— near-real-time imagery from NASA SDO and ESA/NASA SOHO, with NOAA SWPC's current solar weather</span></h2>
 <div class=ssl-cards id=ssl_cards><div class=meta>Loading NOAA SWPC status…</div></div>
 <div class=ssl-sun><div class=ssl-mv><div class=ssl-tabs id=ssl_mtabs role=tablist>${MOV.map((m,i)=>`<button role=tab data-m=${i} class="${i?"":"on"}" title="${E(m[2])}">${E(m[1])}</button>`).join("")}</div>
  <figure class=ssl-fig><video id=ssl_vid muted loop playsinline preload=metadata aria-label="NASA SDO movie of the Sun, latest 48 hours"></video><figcaption id=ssl_mcap></figcaption></figure></div>
  <div class=ssl-view><div class=ssl-tabs id=ssl_itabs role=tablist>${IMG.map((x,i)=>`<button role=tab data-i=${i} class="${i?"":"on"}" title="${E(x[2])}">${E(x[1])}</button>`).join("")}</div>
  <figure class=ssl-fig><img id=ssl_img loading=lazy decoding=async width=1024 height=1024 alt=""><figcaption id=ssl_cap></figcaption></figure></div></div>
  <div class=ssl-side><h3 class=ss-h>Active NOAA alerts, watches &amp; warnings <span class=meta id=ssl_acount></span></h3><div id=ssl_alerts class=ssl-alerts></div></div>`;
 const b=document.createElement("section");b.className="pn ssl";b.id="ssl_flare";
 b.innerHTML=`<h2><span class=ssl-ic>💥</span> Flares, sunspots &amp; CME impact watch <span class=meta>— NOAA SWPC forecasts and GOES X-ray data, NASA CCMC DONKI for CME arrivals</span></h2>
 <div class=ssl-grid2><div><h3 class=ss-h>Impact countdown <span class=meta>— when a CME is due at Earth's magnetosphere</span></h3><div id=ssl_cme class=ssl-cme></div></div>
  <div><h3 class=ss-h>Geomagnetic outlook: 3-hour Kp, next 3 days <span class=meta id=ssl_kpm></span></h3><div class=ssl-chart><canvas id=ssl_kpc height=190></canvas></div><div class=ssl-leg id=ssl_kpleg></div></div></div>
 <div class=ssl-grid2><div><h3 class=ss-h>Flare probabilities <span class=meta id=ssl_pdate></span></h3><div id=ssl_probs></div>
   <h3 class=ss-h style="margin-top:12px">Recent flares, past 7 days <span class=meta id=ssl_fcount></span></h3><div id=ssl_flares class=ssl-flares></div></div>
  <div><h3 class=ss-h>GOES X-ray flux, past 24 h <span class=meta id=ssl_xnow></span></h3><div class=ssl-chart><canvas id=ssl_xc height=190></canvas></div>
   <h3 class=ss-h style="margin-top:12px">Active sunspot regions <span class=meta id=ssl_rdate></span></h3><div id=ssl_regions></div></div></div>
 <p class="meta ssl-credit">Data: NOAA Space Weather Prediction Center (${SWPC}) · NASA CCMC DONKI (<a href="https://kauai.ccmc.gsfc.nasa.gov/DONKI/" target=_blank rel=noopener>kauai.ccmc.gsfc.nasa.gov</a>). Forecasts are NOAA's and NASA's own, shown as published.</p>`;
 const c=document.createElement("section");c.className="pn ssl";c.id="ssl_eq";
 c.innerHTML=`<h2><span class=ssl-ic>🌍</span> Live earthquakes <span class=meta>— real-time world seismicity from the U.S. Geological Survey, refreshed every 60 seconds</span></h2>
 <div class=ssl-eqbar><span class=ss-seg id=ssl_feed>${FEEDS.map(([k,l])=>`<button data-f="${k}" class="${k==S.feed?"on":""}">${l}</button>`).join("")}</span>
  <button type=button class=ssl-sig id=ssl_sig hidden></button><span class=meta id=ssl_eqfresh></span></div>
 <div class=ssl-eqgrid><div><div id=ssl_eqmap></div><div class=ssl-leg id=ssl_eqleg></div></div><div><h3 class=ss-h>Latest quakes <span class=meta id=ssl_eqcount></span></h3><div id=ssl_eqlist class=ssl-eqlist></div></div></div>
 <p class="meta ssl-credit">Earthquake data: <a href="https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php" target=_blank rel=noopener>USGS Earthquake Hazards Program real-time GeoJSON feeds</a>. Magnitudes and locations are preliminary and may be revised by USGS.</p>`;
 top.after(a,b,c);
 g("ssl_mtabs").onclick=e=>{const t=e.target.closest("button[data-m]");if(!t)return;showMov(+t.dataset.m,true)};
 g("ssl_itabs").onclick=e=>{const t=e.target.closest("button[data-i]");if(!t)return;stopCycle();showImg(+t.dataset.i)};
 g("ssl_feed").onclick=e=>{const t=e.target.closest("button[data-f]");if(!t)return;S.feed=t.dataset.f;g("ssl_feed").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x==t));S.seen=null;loadQ()};
 g("ssl_sig").onclick=()=>{if(!S.sig||!S.sig.length)return;const q=S.sig[0];if(S.map){S.map.setView([q.lat,q.lon],5);const m=S.mk&&S.mk[q.id];if(m)m.openPopup()}};
 g("ssl_eqlist").onclick=e=>{const r=e.target.closest("[data-q]");if(!r||e.target.closest("a"))return;const m=S.mk&&S.mk[r.dataset.q];if(m&&S.map){S.map.setView(m.getLatLng(),Math.max(S.map.getZoom(),4));m.openPopup()}};
 S.built=true;showImg(0);showMov(0,false);return true}

// ---------------------------------------------------------------- imagery
function bust(){return Math.floor(Date.now()/300000)}
function showImg(i){S.img=i;const x=IMG[i],im=g("ssl_img");if(!im)return;
 g("ssl_itabs").querySelectorAll("button").forEach((b,j)=>b.classList.toggle("on",j==i));
 im.alt=`Latest ${x[1]} image of the Sun (${x[2]}) from ${x[0].startsWith("soho")?"ESA/NASA SOHO":"NASA SDO"}`;
 im.dataset.try="0";im.onerror=()=>{if(im.dataset.try=="0"){im.dataset.try="1";im.src=`api/solar_seismic/img/${x[0]}?t=${bust()}`}else{im.removeAttribute("src");im.alt="";
   g("ssl_cap").innerHTML=`<span class=ssl-bad>Image source temporarily unavailable.</span> <a href="${x[3]}" target=_blank rel=noopener>Open it at ${x[0].startsWith("soho")?"SOHO":"SDO"} →</a>`}};
 im.onload=()=>{g("ssl_cap").innerHTML=cap(x)};
 im.src=x[3]+"?t="+bust();g("ssl_cap").innerHTML=cap(x)}
function cap(x){const soho=x[0].startsWith("soho");
 return `<b>${E(x[1])}</b> · ${E(x[2])} · auto-refreshes every 5 min (loaded ${hm(Date.now())}) · ${soho?'Credit: <a href="https://soho.nascom.nasa.gov/" target=_blank rel=noopener>ESA/NASA SOHO</a>':'Credit: <a href="https://sdo.gsfc.nasa.gov/" target=_blank rel=noopener>NASA/SDO</a> and the AIA/HMI science teams'}
 ${x[4]?` · <a href="${x[4]}" target=_blank rel=noopener>48-hour movie (MP4) →</a>`:""} · <button type=button class=ssl-cyc id=ssl_cyc>${S.cyc?"⏸ stop cycling":"▶ cycle views"}</button>`}
// NASA SDO's latest-48h MP4s (512 px, 4-13 MB): NASA publishes no official 24/7 live video, so this is near-real-time, labeled as such.
// Plays muted and looped only while this tab is visible and nothing else on the page is playing; site-wide media coordinator
// (t245) pauses it whenever another player starts, and a manual play here stops the others (that coordinator listens for "play").
const MU=w=>`https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_512_${w}.mp4`;
function othersPlaying(v){return [...document.querySelectorAll("audio,video")].some(m=>m!==v&&!m.paused&&!m.muted)}
function showMov(i,user){S.mov=i;const m=MOV[i],v=g("ssl_vid");if(!v)return;g("ssl_mtabs").querySelectorAll("button").forEach((b,j)=>b.classList.toggle("on",j==i));
 v.hidden=false;v.poster=`https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_${m[0]}.jpg?t=${bust()}`;v.src=MU(m[0])+"?t="+Math.floor(Date.now()/36e5);
 v.setAttribute("aria-label",`NASA SDO ${m[1]} movie of the Sun (${m[2]}), latest about 48 hours`);
 v.onerror=()=>{v.hidden=true;g("ssl_mcap").innerHTML=`<span class=ssl-bad>SDO movie temporarily unavailable.</span> The auto-updating still images ${innerWidth<900?"below":"beside this"} keep refreshing every 5 min. <a href="https://sdo.gsfc.nasa.gov/data/" target=_blank rel=noopener>SDO data page →</a>`};
 v.controls=true;mcap();if(S.on&&(user||!othersPlaying(v)))v.play().catch(()=>{})}
function mcap(){const m=MOV[S.mov||0],x=S.d&&S.d.movies&&S.d.movies[m[0]];const c=g("ssl_mcap");if(!c||g("ssl_vid").hidden)return;
 c.innerHTML=`<b>Near-real-time, not live:</b> NASA SDO's latest ~48-hour movie (${E(m[1])}, ${E(m[2])}), about one frame every 7 minutes in a 20-second loop. NASA rebuilds it every few hours${x&&x.updated_et?`; this copy was published <b>${E(x.updated_et)}</b>`:""}. NASA runs no official 24/7 live video of the Sun. Credit: <a href="https://sdo.gsfc.nasa.gov/" target=_blank rel=noopener>NASA/SDO</a> and the AIA/HMI science teams · <a href="${E(x?x.url1024:MU(m[0]).replace("_512_","_1024_"))}" target=_blank rel=noopener>full-size 1024 px movie →</a>`}
function stopCycle(){if(S.cyc){clearInterval(S.cyc);S.cyc=null}}
TAB.addEventListener("click",e=>{if(e.target.id!="ssl_cyc")return;if(S.cyc){stopCycle();showImg(S.img)}else{S.cyc=setInterval(()=>{if(S.on)showImg((S.img+1)%IMG.length)},6000);showImg(S.img)}});

// ---------------------------------------------------------------- NOAA live block
async function loadLive(){try{const r=await fetch("api/solar_seismic/live",{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;S.d=j;renderLive()}
 catch(err){const c=g("ssl_cards");if(c&&!S.d)c.innerHTML=`<div class=ssl-bad>NOAA SWPC status temporarily unavailable. See ${SWPC} directly.</div>`}}
const card=(t,v,sub,col,fresh,href)=>`<a class=ssl-card style="--c:${col}" href="${href||"https://www.swpc.noaa.gov/"}" target=_blank rel=noopener><span class=t>${t}</span><span class=v>${v}</span><span class=s>${sub}</span><span class=f>${fresh?"updated "+E(fresh.replace(/^\w{3} \w{3} \d+, /,"")):"no recent reading"}</span></a>`;
function renderLive(){const D=S.d;if(!D)return;const w=D.wind||{},k=D.kp_now||{},sc=(D.scales||{}).now||{};
 const sp=w.speed,de=w.density,bz=w.bz;
 const gl=x=>x&&x.scale!=null?(+x.scale):0,G=gl(sc.G),Sv=gl(sc.S),R=gl(sc.R);
 const scCol=n=>[LV.ok,LV.watch,LV.warn,LV.high,LV.bad,LV.ext][n]||LV.mu;
 g("ssl_cards").innerHTML=[
  card("Planetary Kp (1-min estimate)",k.est!=null?k.est.toFixed(2):"–",k.est==null?"":k.est>=4.67?`G${Math.min(5,Math.floor(k.est+.34)-4)} storm level`:k.est>=4?"active":k.est>=3?"unsettled":"quiet",kpCol(k.est),k.t_et,"https://www.swpc.noaa.gov/products/planetary-k-index"),
  card("Solar wind speed",sp!=null?`${Math.round(sp)} <small>km/s</small>`:"–",sp==null?"":sp>=700?"very fast":sp>=500?"elevated":"normal",sp==null?LV.mu:sp>=700?LV.bad:sp>=500?LV.warn:LV.ok,w.t_et,"https://www.swpc.noaa.gov/products/real-time-solar-wind"),
  card("Proton density",de!=null?`${de.toFixed(1)} <small>p/cm³</small>`:"–",de==null?"":de>=20?"very dense":de>=10?"dense":"normal",de==null?LV.mu:de>=20?LV.bad:de>=10?LV.warn:LV.ok,w.density_t_et,"https://www.swpc.noaa.gov/products/real-time-solar-wind"),
  card("IMF Bz (north/south)",bz!=null?`${bz>0?"+":""}${bz.toFixed(0)} <small>nT</small>`:"–",bz==null?"":bz<=-10?"strongly south: storm-favorable":bz<0?"southward":"northward",bz==null?LV.mu:bz<=-10?LV.bad:bz<=-5?LV.warn:bz<0?LV.watch:LV.ok,w.mag_t_et,"https://www.swpc.noaa.gov/products/real-time-solar-wind"),
  card("NOAA scales now",`<span style="color:${scCol(G)}">G${G}</span> <span style="color:${scCol(Sv)}">S${Sv}</span> <span style="color:${scCol(R)}">R${R}</span>`,`24 h max: G${gl((D.scales.max24||{}).G)} S${gl((D.scales.max24||{}).S)} R${gl((D.scales.max24||{}).R)}`,scCol(Math.max(G,Sv,R)),D.generated_et,"https://www.swpc.noaa.gov/noaa-scales-explanation"),
  card("Active alerts",`${D.alerts.n_active}`,`warnings/alerts in force or issued in the last 24 h`,D.alerts.active.some(a=>/G[3-5]|S[3-5]|R[3-5]/.test(a.scale||""))?LV.bad:D.alerts.n_active?LV.warn:LV.ok,D.generated_et,"https://www.swpc.noaa.gov/products/alerts-watches-and-warnings")].join("");
 g("ssl_acount").textContent=`· ${D.alerts.n_active} active · checked ${hm(D.generated)}`;
 g("ssl_alerts").innerHTML=D.alerts.active.length?D.alerts.active.slice(0,12).map(a=>`<details class=ssl-al style="--c:${/[GSR][3-5]/.test(a.scale||"")?LV.bad:/[GSR]2/.test(a.scale||"")?LV.warn:a.scale?LV.watch:LV.mu}"><summary><b>${E(a.head||a.pid)}</b>${a.scale?` <span class=ssl-chip>${E(a.scale)}</span>`:""}<small>${E(a.t_et)}${a.valid_to_et?" · valid to "+E(a.valid_to_et):""}</small></summary><pre>${E(a.msg)}</pre></details>`).join("")
  :`<div class=meta>No NOAA alerts or warnings are in force. <a href="https://www.swpc.noaa.gov/products/alerts-watches-and-warnings" target=_blank rel=noopener>Archive →</a></div>`;
 renderFlares();renderCME();drawKp();drawX();mcap()}

function renderFlares(){const D=S.d,p=D.probs||{},F=D.flares||{};
 g("ssl_pdate").textContent=p.date?`· NOAA SWPC, issued for ${p.date}`:"";
 const row=(L,k)=>`<div class=ssl-pr><span class=ssl-cls style="--c:${FLC[L]}">${L}</span>${[1,2,3].map(d=>{const v=p[k+d];return `<span class=ssl-pb title="day ${d}"><i style="width:${Math.max(2,v||0)}%;background:${FLC[L]}"></i><b>${v??"–"}%</b><small>day ${d}</small></span>`}).join("")}</div>`;
 g("ssl_probs").innerHTML=row("C","c")+row("M","m")+row("X","x")+`<div class=meta>Chance of at least one flare of each class per day. Proton event (S1+) day 1: ${p.p10??"–"}%.</div>`;
 const c=F.count7||{};g("ssl_fcount").innerHTML=`· ${"XMCB".split("").map(L=>`<span style="color:${FLC[L]}">${c[L]||0} ${L}</span>`).join(" · ")}`;
 g("ssl_flares").innerHTML=(F.list||[]).filter(f=>/^[CMX]/.test(f.class)).slice(0,14).map(f=>`<span class=ssl-fl style="--c:${flc(f.class)}"><b>${E(f.class)}</b><small>${E(f.t_et)}</small></span>`).join("")||
  `<div class=meta>No C, M or X flares in the past 7 days.</div>`;
 if(F.latest)g("ssl_flares").insertAdjacentHTML("afterbegin",`<div class=meta style="width:100%">Latest flare: <b style="color:${flc(F.latest.class)}">${E(F.latest.class)}</b> peaking ${E(F.latest.t_et)}${F.biggest?` · biggest this week: <b style="color:${flc(F.biggest.class)}">${E(F.biggest.class)}</b> (${E(F.biggest.t_et)})`:""}</div>`);
 const R=(D.regions||{}).list||[];g("ssl_rdate").textContent=D.regions.date?`· ${R.length} numbered region(s) on ${D.regions.date}`:"";
 g("ssl_regions").innerHTML=R.length?`<table class="ss-tb ssl-tb"><tr><th>Region</th><th>Location</th><th>Spots</th><th>Magnetic class</th><th class=n>C / M / X chance</th><th class=n>Flares C/M/X</th></tr>${R.map(r=>`<tr><td><b>AR${E(r.region)}</b></td><td>${E(r.location)}</td><td>${E(r.spot_class||"–")}${r.number_spots!=null?" · "+r.number_spots:""}</td><td>${E(r.mag_class||"–")}</td><td class=n><span style="color:${FLC.C}">${r.c_flare_probability??"–"}%</span> / <span style="color:${FLC.M}">${r.m_flare_probability??"–"}%</span> / <span style="color:${FLC.X}">${r.x_flare_probability??"–"}%</span></td><td class=n>${r.c_xray_events||0}/${r.m_xray_events||0}/${r.x_xray_events||0}</td></tr>`).join("")}</table>`
  :`<div class=meta>No numbered sunspot regions in NOAA's latest report.</div>`;
 g("ssl_xnow").textContent=F.current_class?`· now ${F.current_class} (${(F.current_t_et||"").replace(/^\w{3} \w{3} \d+, /,"")})`:""}

// ---------------------------------------------------------------- CME countdown
function renderCME(){const C=S.d.cme||{},el=g("ssl_cme");let h="";
 (C.events||[]).forEach((ev,i)=>{const rough=ev.kind=="rough";
  h+=`<div class="ssl-cd ${rough?"rough":""}"><div class=ssl-cdh>${rough?"⚠ Rough estimate, not an official forecast":"Official model estimate"} · <span class=meta>${E(ev.source)}</span></div>
  <div class=ssl-tick data-at="${E(ev.arrival)}">–</div><div>Estimated arrival at Earth: <b>${E(ev.arrival_et)}</b>${ev.window_et?` <span class=meta>(window ${E(ev.window_et[0])} – ${E(ev.window_et[1])})</span>`:""}</div>
  <div class=meta>${ev.cme_start_et?`CME launched ${E(ev.cme_start_et)}`:""}${ev.speed?` · ${Math.round(ev.speed)} km/s`:""}${ev.glancing?" · glancing blow expected":""}${ev.kp_range&&ev.kp_range.some(x=>x!=null)?` · model Kp ${E(ev.kp_range.filter(x=>x!=null).join("–"))}`:""}${ev.link?` · <a href="${E(ev.link)}" target=_blank rel=noopener>DONKI record →</a>`:""}</div>
  ${ev.assumptions?`<div class="meta ssl-asm">Assumptions: ${E(ev.assumptions)}</div>`:""}</div>`});
 if(!(C.events||[]).length)h+=`<div class=ssl-cd quiet><div class=ssl-cdh>No CME countdown active</div><div>${E(C.note||"")}</div></div>`;
 const la=C.last_arrival;h+=`<div class=ssl-kv><span>Last arrival at Earth</span><b>${la?E(la.t_et):"none in the data window"}</b>${la?`<small>${E(la.source)}${la.link?` · <a href="${E(la.link)}" target=_blank rel=noopener>record</a>`:""} · ${ago(Date.parse(la.t))}</small>`:""}</div>`;
 const nw=C.next_window;h+=`<div class=ssl-kv><span>Next predicted storm window (Kp ≥ 5)</span><b>${nw?E(nw.t_et)+` · Kp ${nw.kp}${nw.g?" ("+E(nw.g)+")":""}`:"none in NOAA's 3-day Kp forecast"}</b><small>NOAA SWPC 3-hour Kp forecast</small></div>`;
 (C.watches||[]).forEach(w=>{h+=`<div class=ssl-kv><span>Latest NOAA watch</span><b>${E(w.head)}</b><small>${E(w.t_et)}${w.days.length?" · "+w.days.map(d=>`${E(d.day)}: ${E(d.g)}`).join(", "):""}${w.cme?" · CME-driven":""}</small></div>`});
 const f3=S.d.forecast3||{};if(f3.rationale)h+=`<div class=ssl-kv><span>NOAA 3-day forecast</span><b>Max Kp ${f3.kp_max??"–"}${f3.g_max?" ("+E(f3.g_max)+")":""}</b><small>${E(f3.rationale)} · <a href="${E(f3.url)}" target=_blank rel=noopener>issued ${E(f3.issued)}</a></small></div>`;
 const ds=(S.d.discussion||{}).cme_sentences||[];if(ds.length)h+=`<div class=ssl-kv><span>NOAA forecast discussion on CMEs</span><small>${ds.map(E).join(" ")} · <a href="${E(S.d.discussion.url)}" target=_blank rel=noopener>issued ${E(S.d.discussion.issued)}</a></small></div>`;
 if(!C.donki_ok)h+=`<div class=meta>NASA CCMC DONKI is temporarily unavailable; showing NOAA SWPC only. <a href="https://kauai.ccmc.gsfc.nasa.gov/DONKI/" target=_blank rel=noopener>Open DONKI →</a></div>`;
 el.innerHTML=h;tick()}
function tick(){document.querySelectorAll("#ssl_cme .ssl-tick").forEach(t=>{const ms=Date.parse(t.dataset.at)-Date.now();
 if(ms<=0){t.textContent="Arrival time reached: watch the Kp and Bz cards";return}
 const s=Math.floor(ms/1000),d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60),x=s%60;
 t.textContent=`${d?d+"d ":""}${String(h).padStart(2,"0")}h ${String(m).padStart(2,"0")}m ${String(x).padStart(2,"0")}s`})}

// ---------------------------------------------------------------- canvases
function cv(id){const c=g(id);if(!c)return null;const W=c.clientWidth||600,H=c.clientHeight||190,r=window.devicePixelRatio||1;c.width=W*r;c.height=H*r;const x=c.getContext("2d");x.setTransform(r,0,0,r,0,0);x.clearRect(0,0,W,H);x.font="11px system-ui,sans-serif";return {x,W,H}}
function drawKp(){const o=cv("ssl_kpc");if(!o||!S.d)return;const {x,W,H}=o,now=Date.now();
 const K=(S.d.kp_forecast||[]).filter(r=>Date.parse(r.t)>=now-36*3600e3);if(!K.length)return;
 const L=28,B=H-22,T=8,bw=(W-L-4)/K.length;
 x.strokeStyle="#252b33";x.fillStyle="#8b95a3";for(let k=0;k<=9;k+=3){const y=B-(B-T)*k/9;x.beginPath();x.moveTo(L,y);x.lineTo(W,y);x.stroke();x.fillText(k,8,y+4)}
 // highlight: CME arrival windows, else NOAA watch days
 const evs=(S.d.cme.events||[]);const win=evs.map(e=>e.window?[Date.parse(e.window[0]),Date.parse(e.window[1])]:[Date.parse(e.arrival)-6*3600e3,Date.parse(e.arrival)+12*3600e3]);
 K.forEach((r,i)=>{const t=Date.parse(r.t),inW=win.some(([a,b])=>t+3*3600e3>a&&t<b);if(inW){x.fillStyle="rgba(255,77,79,.16)";x.fillRect(L+i*bw,T,bw,B-T)}});
 K.forEach((r,i)=>{const v=r.kp||0,h=(B-T)*v/9,px=L+i*bw;x.fillStyle=kpCol(v);x.globalAlpha=r.kind=="observed"?1:r.kind=="estimated"?.8:.55;x.fillRect(px+1,B-h,Math.max(1,bw-2),h);x.globalAlpha=1;
  const d=new Date(r.t),hr=+d.toLocaleString("en-US",{timeZone:TZ,hour:"numeric",hour12:false});if(hr<3){x.fillStyle="#8b95a3";x.fillText(d.toLocaleDateString("en-US",{timeZone:TZ,weekday:"short",day:"numeric"}),px,H-6)}});
 const y5=B-(B-T)*4.67/9;x.strokeStyle="#ffd666";x.setLineDash([4,3]);x.beginPath();x.moveTo(L,y5);x.lineTo(W,y5);x.stroke();x.setLineDash([]);x.fillStyle="#ffd666";x.fillText("G1 (Kp 5)",W-62,y5-3);
 const ni=K.findIndex(r=>Date.parse(r.t)+3*3600e3>now);if(ni>=0){const px=L+ni*bw;x.strokeStyle="#4aa3ff";x.beginPath();x.moveTo(px,T);x.lineTo(px,B);x.stroke();x.fillStyle="#4aa3ff";x.fillText("now",px+3,T+10)}
 const m=S.d.kp_forecast_max;g("ssl_kpm").textContent=m?`· forecast max Kp ${m.kp}${m.g?" ("+m.g+")":""} at ${dt(m.t)}`:"";
 g("ssl_kpleg").innerHTML=`<span><i style="background:${LV.ok}"></i>quiet</span><span><i style="background:#d4b106"></i>active (Kp 4)</span><span><i style="background:${LV.watch}"></i>G1</span><span><i style="background:${LV.warn}"></i>G2</span><span><i style="background:${LV.high}"></i>G3</span><span><i style="background:${LV.bad}"></i>G4</span><span><i style="background:${LV.ext}"></i>G5</span><span>solid = observed, faded = NOAA forecast</span>${evs.length?`<span><i style="background:rgba(255,77,79,.4)"></i>CME arrival window</span>`:""}<span>Times ET · <a href="https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json" target=_blank rel=noopener>NOAA data</a></span>`}
function drawX(){const o=cv("ssl_xc");if(!o||!S.d)return;const {x,W,H}=o,X=S.d.xray||[];if(X.length<2)return;
 const L=28,B=H-18,T=6,lo=-9,hi=-3,t0=Date.parse(X[0][0]),t1=Date.parse(X[X.length-1][0]);const Y=v=>B-(B-T)*(Math.log10(v)-lo)/(hi-lo),Xp=t=>L+(W-L-4)*(t-t0)/(t1-t0||1);
 [["A",-8],["B",-7],["C",-6],["M",-5],["X",-4]].forEach(([c,e])=>{const y0=Y(10**e),y1=Y(10**(e+1));x.fillStyle=FLC[c];x.globalAlpha=.08;x.fillRect(L,y1,W-L,y0-y1);x.globalAlpha=1;x.fillStyle=FLC[c];x.fillText(c,10,(y0+y1)/2+4)});
 x.strokeStyle="#ffd666";x.lineWidth=1.5;x.beginPath();X.forEach(([t,v],i)=>{const px=Xp(Date.parse(t)),py=Y(Math.max(v,1e-9));i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.lineWidth=1;
 x.fillStyle="#8b95a3";for(let i=0;i<=4;i++){const t=t0+(t1-t0)*i/4;x.fillText(new Date(t).toLocaleTimeString("en-US",{timeZone:TZ,hour:"numeric"}),Xp(t)-10,H-4)}}

// ---------------------------------------------------------------- USGS earthquakes
const mcol=m=>m>=7?"#b37feb":m>=6?"#ff4d4f":m>=5?"#ff7a45":m>=4?"#faad14":m>=2.5?"#ffd666":"#73d13d";
const mrad=m=>Math.max(3,Math.min(30,2.5+Math.pow(Math.max(m,0),1.65)));
async function getUSGS(f){const u=`https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/${f}.geojson`;
 try{const r=await fetch(u,{cache:"no-store"});if(!r.ok)throw r.status;return [await r.json(),"usgs"]}
 catch(e){const r=await fetch(`api/solar_seismic/usgs/${f}`,{cache:"no-store"});if(!r.ok)throw "proxy "+r.status;return [await r.json(),"proxy"]}}
async function loadQ(){const f=S.feed;try{const [j,via]=await getUSGS(f);if(f!=S.feed)return;S.qT=Date.now();S.via=via;
  const Q=(j.features||[]).filter(x=>x.geometry&&x.properties&&x.properties.mag!=null).map(x=>({id:x.id,mag:+x.properties.mag,place:x.properties.place||x.properties.title,t:x.properties.time,url:x.properties.url,
   lat:x.geometry.coordinates[1],lon:x.geometry.coordinates[0],depth:x.geometry.coordinates[2],tsu:x.properties.tsunami,alert:x.properties.alert,sig:x.properties.sig,felt:x.properties.felt,type:x.properties.type}));
  const now=Date.now();if(S.seen){Q.forEach(q=>{if(!S.seen.has(q.id))S.newIds.set(q.id,now)})}else Q.forEach(q=>{if(now-q.t<30*60e3)S.newIds.set(q.id,now)});
  S.seen=new Set(Q.map(q=>q.id));for(const [k,t] of S.newIds)if(now-t>15*60e3)S.newIds.delete(k);
  S.q=Q.sort((a,b)=>b.t-a.t);S.meta=j.metadata||{};renderQ()}
 catch(err){g("ssl_eqfresh").innerHTML=`<span class=ssl-bad>USGS feed temporarily unavailable.</span> <a href="https://earthquake.usgs.gov/earthquakes/map/" target=_blank rel=noopener>Open the USGS map →</a>`}}
async function loadSig(){try{const [j]=await getUSGS("significant_week");S.sig=(j.features||[]).map(x=>({id:x.id,mag:x.properties.mag,place:x.properties.place,t:x.properties.time,url:x.properties.url,lat:x.geometry.coordinates[1],lon:x.geometry.coordinates[0]})).sort((a,b)=>b.t-a.t);
 const b=g("ssl_sig");if(S.sig.length){const q=S.sig[0];b.hidden=false;b.innerHTML=`⚠ USGS significant this week: <b>${S.sig.length}</b> · latest M${q.mag.toFixed(1)} ${E(q.place)} (${E(ago(q.t))})`}else{b.hidden=false;b.innerHTML="USGS significant this week: none";b.disabled=true}}catch(e){}}
function renderQ(){const Q=S.q||[];if(typeof L=="undefined")return;
 if(!S.map){S.map=L.map("ssl_eqmap",{worldCopyJump:true,scrollWheelZoom:false,minZoom:1}).setView([15,-170+190],2);
  if(window.bnBaseLayer)bnBaseLayer(S.map,{maxZoom:10});   // shared keyless basemap from dashboard.html (no hardcoded tile URLs here)
  S.map.attributionControl.addAttribution('Quakes: <a href="https://earthquake.usgs.gov/" target=_blank rel=noopener>USGS</a>');
  S.lay=L.layerGroup().addTo(S.map);S.map.on("click",()=>S.map.scrollWheelZoom.enable());S.map.on("mouseout",()=>S.map.scrollWheelZoom.disable())}
 S.lay.clearLayers();S.mk={};
 Q.slice().sort((a,b)=>a.mag-b.mag).forEach(q=>{const nw=S.newIds.has(q.id),c=mcol(q.mag);
  const m=L.circleMarker([q.lat,q.lon],{radius:mrad(q.mag),color:nw?"#ffffff":c,weight:nw?2.5:1,fillColor:c,fillOpacity:.62,className:nw?"ssl-new":""})
   .bindPopup(`<b>M${q.mag.toFixed(1)}</b> ${E(q.place)}<br>Depth ${q.depth!=null?q.depth.toFixed(1)+" km":"–"}<br>${E(dt(q.t))} (${E(ago(q.t))})${q.tsu?"<br><b>Tsunami flag set by USGS</b> (check tsunami.gov)":""}${q.alert?`<br>PAGER alert: ${E(q.alert)}`:""}${q.type&&q.type!="earthquake"?`<br>Type: ${E(q.type)}`:""}<br><a href="${E(q.url)}" target=_blank rel=noopener>USGS event page →</a>`);
  m.addTo(S.lay);S.mk[q.id]=m});
 const nn=Q.filter(q=>S.newIds.has(q.id)).length;
 g("ssl_eqfresh").innerHTML=`<span class=ssl-dotlive></span>last updated ${hm(S.qT)} · next check in 60 s${S.via=="proxy"?" · via blackout.network cache":""}${nn?` · <b class=ssl-newc>${nn} new</b>`:""}`;
 g("ssl_eqcount").textContent=`· ${Q.length} quake${Q.length==1?"":"s"} · ${(FEEDS.find(f=>f[0]==S.feed)||[])[1]||""}`;
 g("ssl_eqleg").innerHTML=[["< 2.5","#73d13d",1.8],["2.5–4","#ffd666",3],["4–5","#faad14",4.5],["5–6","#ff7a45",5.5],["6–7","#ff4d4f",6.5],["7+","#b37feb",7.3]].map(([l,c,m])=>`<span><i style="background:${c};width:${mrad(m)*2}px;height:${mrad(m)*2}px"></i>M${l}</span>`).join("")+`<span><i class=ring></i>new since last check</span><span>Circle size and color = magnitude · click the map to scroll-zoom</span>`;
 g("ssl_eqlist").innerHTML=Q.slice(0,40).map(q=>`<div class="ssl-q ${S.newIds.has(q.id)?"new":""}" data-q="${E(q.id)}" tabindex=0><span class=m style="--c:${mcol(q.mag)}">${q.mag.toFixed(1)}</span><span class=p><b>${E(q.place)}</b><small>${E(dt(q.t))} · ${E(ago(q.t))} · ${q.depth!=null?q.depth.toFixed(0)+" km deep":""}${q.tsu?" · tsunami flag":""}</small></span>${S.newIds.has(q.id)?"<span class=nb>NEW</span>":""}<a href="${E(q.url)}" target=_blank rel=noopener title="USGS event page">↗</a></div>`).join("")||`<div class=meta>No quakes in this feed window.</div>`}

// ---------------------------------------------------------------- lifecycle
function visible(){return getComputedStyle(TAB).display!="none"}
let lastLive=0,lastQ=0,lastImg=0,lastSig=0;
function step(){const v=visible();
 if(v&&!S.built&&!build())return;
 if(v&&!S.on){S.on=true;const vd=g("ssl_vid");if(vd&&!vd.hidden&&vd.paused&&!othersPlaying(vd))vd.play().catch(()=>{});setTimeout(()=>{if(S.map)S.map.invalidateSize();drawKp();drawX()},120)}
 if(!v){if(S.on){const vd=g("ssl_vid");if(vd&&!vd.paused)vd.pause()}S.on=false;return}
 if(document.hidden)return;const t=Date.now();
 if(t-lastQ>=60e3){lastQ=t;loadQ()}
 if(t-lastSig>=300e3){lastSig=t;loadSig()}
 if(t-lastLive>=120e3){lastLive=t;loadLive()}
 if(t-lastImg>=300e3){if(lastImg&&!S.cyc)showImg(S.img);lastImg=t}
 if(!S.movT)S.movT=t;else if(t-S.movT>=3*36e5){S.movT=t;const vd=g("ssl_vid");if(vd&&(vd.paused||vd.muted))showMov(S.mov||0,false)}
 tick()}
setInterval(step,1000);step();
let rz;window.addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{if(S.on){drawKp();drawX()}},200)});
})();
