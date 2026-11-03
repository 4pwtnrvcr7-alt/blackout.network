// ---- Regional Heat Map tab (served by heatmap.py; geolocation from geo.py / geo.db). Read-only view: it never changes scores or ranks. ----
(()=>{"use strict";
const M=document.getElementById("tab-heatmap");if(!M)return;
const e_=s=>esc(s==null?"":String(s)),U=u=>esc(safeUrl(u||"#"));
const GR=[["violence","Violence / attack","war/conflict"],["disease","Disease","disease"],["infra","Infrastructure & hazards","natural disaster, space weather"],["cyber","Cyber","cyber"],["unrest","Unrest / political","political"],["other","Other","financial, UFO/UAP, religious, other"]];
const COLF={violence:"#ff4d4f",disease:"#fa8c16",infra:"#fadb14",cyber:"#4aa3ff",unrest:"#b37feb",other:"#8a93a6"};
const col=g=>g=="other"?COLF.other:(typeof catColor=="function"?catColor(g,COLF[g]):COLF[g]);
const WIN={"6h":6,"24h":24,"7d":168},WINL={"6h":"last 6 hours","24h":"last 24 hours","7d":"last 7 days"};
const PREC={point:"exact point (source coordinates)",city:"city",county:"county / NWS zones",state:"state / province",country:"country"};
let savedCats=null;try{savedCats=JSON.parse(localStorage.getItem("hm_cats")||"null")}catch(_){}
const H={d:null,shown:false,map:null,win:localStorage.getItem("hm_win")||"24h",cats:new Set(Array.isArray(savedCats)&&savedCats.length?savedCats:GR.map(g=>g[0])),
 sev:+(localStorage.getItem("hm_sev")||0),wm:localStorage.getItem("hm_w")||"sev",lay:{heat:true,reg:true,pts:true},sel:null,open:new Set(),openU:new Set(),
 a0:null,a1:null,a1raw:null,a1loading:false,heat:null,mc:null,agg:null,page:25,upage:{},busy:false,lastLoad:0};
const etF=t=>t?new Date(t).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET":"—";
const ago=t=>{const s=(Date.now()-Date.parse(t))/1e3;if(!isFinite(s))return"";if(s<3600)return Math.max(1,Math.round(s/60))+"m ago";if(s<86400)return Math.round(s/3600)+"h ago";return Math.round(s/86400)+"d ago"};
const rk=r=>r>=7?"h":r>=4?"m":"l";
// inline SVG line icons (24px grid, 2px stroke, currentColor; same paths as the site icon set) - no emoji on the site
const ICO={globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 2.6 4.2 5.6 4.2 9s-1.4 6.4-4.2 9c-2.8-2.6-4.2-5.6-4.2-9S9.2 5.6 12 3z"/>',fire:'<path d="M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.4 2.4-5.4 3.6-8.3.9 1.6 1.7 2.5 2.9 3 .2-2.9 1.3-5.1 3.3-6.5-.3 3.1 3.2 6.1 3.2 11.4C18.5 18.4 15.9 21 12 21z"/>',pin:'<path d="M12 21.5s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10.5" r="2.4"/>',chev:'<path d="M9 5l7 7-7 7"/>'},ico=k=>`<svg class=hm-i viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" aria-hidden=true focusable=false>${ICO[k]}</svg>`;
const RAMP=["#1b2a3a","#3b2a6b","#7a2d8c","#c2255c","#f0532d","#fa8c16","#ffd666"];
function ramp(f){f=Math.max(0,Math.min(1,f));const p=f*(RAMP.length-1),i=Math.floor(p),k=p-i;if(i>=RAMP.length-1)return RAMP[RAMP.length-1];
 const a=RAMP[i],b=RAMP[i+1],h=(s,o)=>parseInt(s.substr(o,2),16),m=o=>Math.round(h(a,o)+(h(b,o)-h(a,o))*k).toString(16).padStart(2,"0");return"#"+m(1)+m(3)+m(5)}

// ---------- tab button placement + deep link (#heatmap) ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="heatmap"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="heatmap";tb.innerHTML=ico("fire")+" Heat Map";nav.appendChild(tb)}
const after=nav&&nav.querySelector('button[data-tab="solar_seismic"]');if(after&&tb)after.insertAdjacentElement("afterend",tb);
try{if(typeof TABHASH=="object"){TABHASH.heatmap="heatmap";HASHTAB.heatmap="heatmap"}}catch(_){}

// ---------- skeleton ----------
const app=document.getElementById("hm_app");
app.innerHTML=`<div class=hm-status id=hm_status><span class=meta>Loading geolocated alerts…</span></div>
<div class=hm-ctl>
 <div class=hm-cats id=hm_cats role=group aria-label="Categories"></div>
 <div class=hm-seg id=hm_win role=group aria-label="Time window">${Object.keys(WIN).map(w=>`<button type=button data-w="${w}">${w}</button>`).join("")}</div>
 <label class=hm-sev title="Hide alerts ranked below this (0–10 rank)">Severity ≥ <b id=hm_sevv></b><input type=range id=hm_sev min=0 max=10 step=1></label>
 <div class=hm-seg id=hm_wm role=group aria-label="Heat weighting"><button type=button data-m="dens" title="Every alert counts the same">Density</button><button type=button data-m="sev" title="Alerts weighted by their 0–10 rank">Severity</button></div>
 <span class=hm-lay><label><input type=checkbox id=hm_lh checked> heat</label><label><input type=checkbox id=hm_lr checked> regions</label><label><input type=checkbox id=hm_lp checked> points</label></span>
</div>
<div class=hm-grid><div class=hm-mapw><div id=hm_map></div><div class=hm-crumb id=hm_crumb></div><div class=hm-zoomhint id=hm_zh></div></div><aside class=hm-side id=hm_side aria-live=polite></aside></div>
<div class=hm-foot id=hm_foot></div>
<div class=hm-stats id=hm_stats></div>
<div class=hm-unl id=hm_unlw><h2>${ico("pin")} Unlocated alerts <span class=meta id=hm_unlmeta></span></h2><div id=hm_unl></div></div>`;
const $$=id=>document.getElementById(id);

// how-this-works notes (shared component)
if(typeof HW_ICONS=="object"&&typeof hwI=="function"){const O="#ff7a45";
 HW_ICONS.heatmap=hwI(`<path d="M20 80 C30 40 60 30 70 50 C80 70 110 20 130 40 C150 60 170 40 182 50" /><circle cx="70" cy="52" r="16" stroke="${O}"/><circle cx="70" cy="52" r="7" fill="${O}" stroke="${O}"/><circle cx="132" cy="42" r="11" stroke="${O}"/><path d="M150 72 h30 v24 h-30 z M156 80 h18 M156 88 h12"/><path d="M84 62 L150 84" stroke-dasharray="4 4"/>`);
 HW_ICONS.heatmap_unl=hwI(`<circle cx="60" cy="50" r="22"/><path d="M60 72 L60 96" /><path d="M46 36 l28 28 M74 36 l-28 28" stroke="#ff4d4f"/><path d="M110 30 h70 M110 50 h56 M110 70 h64 M110 90 h44"/>`)}
if(typeof hwAttach=="function"){
 hwAttach(M.querySelector("#hm_top h2"),"heatmap",()=>"Each alert from the last 7 days on The Wire and the Watchlist is geolocated by a sidecar worker on this computer (geo.py, results in geo.db), every 5 minutes and on every refresh. It first uses coordinates already in the source data (USGS, GDACS, NWS, tsunami.gov), then the alert's location field and NWS zone lists, then place names in the headline matched against an offline GeoNames gazetteer (cities over 15,000 people, every country and state or province), with rules that skip people's names and ordinary words and use other places in the same text to pick the right Springfield. Only when that fails does it ask OpenStreetMap's free Nominatim service, at most once per second, caching every answer. Nothing is guessed: alerts it cannot place go to the Unlocated list with the reason. The map shows a heat layer (Density counts alerts, Severity weights them by their 0–10 rank; country-level alerts count half), countries shaded by alert load, states and provinces when you zoom in, and clustered points at city level. Boundaries are Natural Earth; tiles are OpenStreetMap.");
 hwAttach(M.querySelector("#hm_unlw h2"),"heatmap_unl",()=>"These alerts could not be put on the map. Each one says why: the text names no place, it only uses nationality words or flags (which say who, not where), several places carry equal weight, a place name matches several real places, the source itself marks it as global, the topic is not geographic (cyber, financial), or the place was not found in the gazetteer or by the online geocoder. Alerts waiting for the online geocoder are retried on the next pass. The list follows the same category, time and severity filters as the map.")}

// ---------- controls ----------
function ctlRender(){const it=H.d?H.d.items.concat(H.d.unlocated):[];const cnt={};it.forEach(x=>{if(inWin(x)&&x.rank>=H.sev)cnt[x.grp]=(cnt[x.grp]||0)+1});
 $$("hm_cats").innerHTML=GR.map(([g,l,t])=>`<button type=button class="hm-chip${H.cats.has(g)?"":" off"}" data-g="${g}" aria-pressed="${H.cats.has(g)}" title="${e_(t)}"><i style="background:${col(g)}"></i>${e_(l)} <small>${cnt[g]||0}</small></button>`).join("");
 $$("hm_win").querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.w==H.win));
 $$("hm_wm").querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.m==H.wm));
 $$("hm_sev").value=H.sev;$$("hm_sevv").textContent=H.sev}
$$("hm_cats").onclick=e=>{const b=e.target.closest("[data-g]");if(!b)return;const g=b.dataset.g;
 if(e.altKey||e.metaKey){H.cats=new Set([g])}else{H.cats.has(g)?H.cats.delete(g):H.cats.add(g);if(!H.cats.size)H.cats=new Set(GR.map(x=>x[0]))}
 localStorage.setItem("hm_cats",JSON.stringify([...H.cats]));redraw()};
$$("hm_win").onclick=e=>{const b=e.target.closest("[data-w]");if(!b)return;H.win=b.dataset.w;localStorage.setItem("hm_win",H.win);redraw()};
$$("hm_wm").onclick=e=>{const b=e.target.closest("[data-m]");if(!b)return;H.wm=b.dataset.m;localStorage.setItem("hm_w",H.wm);redraw()};
$$("hm_sev").oninput=e=>{H.sev=+e.target.value;$$("hm_sevv").textContent=H.sev;localStorage.setItem("hm_sev",H.sev);clearTimeout(H.st);H.st=setTimeout(redraw,120)};
[["hm_lh","heat"],["hm_lr","reg"],["hm_lp","pts"]].forEach(([id,k])=>$$(id).onchange=e=>{H.lay[k]=e.target.checked;layers()});

// ---------- filtering + aggregation ----------
function inWin(x){const t=Date.parse(x.t);return isFinite(t)&&t>=Date.now()-WIN[H.win]*36e5}
const pass=x=>H.cats.has(x.grp)&&x.rank>=H.sev&&inWin(x);
const wt=x=>(H.wm=="sev"?Math.max(.08,(x.rank||0)/10):1)*(x.prec=="country"?.5:1);
const val=x=>H.wm=="sev"?Math.max(.5,x.rank||0):1;
function aggregate(L){const cc={},a1={};L.forEach(x=>{if(x.cc){const o=cc[x.cc]||(cc[x.cc]={n:0,v:0,max:0,c:{},name:x.cn,a1n:0});o.n++;o.v+=val(x);o.max=Math.max(o.max,x.rank);o.c[x.grp]=(o.c[x.grp]||0)+1;if(x.a1)o.a1n++}
  if(x.a1){const o=a1[x.a1]||(a1[x.a1]={n:0,v:0,max:0,c:{},name:x.a1n,cc:x.cc,cn:x.cn});o.n++;o.v+=val(x);o.max=Math.max(o.max,x.rank);o.c[x.grp]=(o.c[x.grp]||0)+1}});
 const mx=o=>Math.max(1,...Object.values(o).map(r=>r.v));return{cc,a1,mx0:mx(cc),mx1:mx(a1)}}
function catbar(c,n){return `<div class=hm-catbar>${GR.map(([g])=>c[g]?`<i style="width:${100*c[g]/n}%;background:${col(g)}" title="${e_(g)}: ${c[g]}"></i>`:"").join("")}</div>`}

// ---------- map ----------
function initMap(){if(H.map||typeof L=="undefined")return;
 H.map=L.map("hm_map",{worldCopyJump:true,minZoom:2,maxZoom:12,zoomSnap:.5,scrollWheelZoom:false,preferCanvas:false}).setView([24,12],2);
 (window.bnBaseLayer?bnBaseLayer(H.map,{maxZoom:12,extra:"boundaries © Natural Earth · places © GeoNames"}):null)/* t252: shared keyless basemap (OpenFreeMap → VersaTiles → NASA GIBS); no OSM tile servers */;
 H.map.createPane("hmReg");H.map.getPane("hmReg").style.zIndex=350;H.map.createPane("hmHeat");H.map.getPane("hmHeat").style.zIndex=420;H.map.getPane("hmHeat").style.pointerEvents="none";
 H.rend0=L.canvas({pane:"hmReg",padding:.4});H.rend1=L.canvas({pane:"hmReg",padding:.4});
 H.map.on("click",()=>H.map.scrollWheelZoom.enable());H.map.on("mouseout",()=>H.map.scrollWheelZoom.disable());
 H.map.on("zoomend",()=>{layers();crumb()});H.map.on("resize",legendLift);
 const lg=L.control({position:"bottomleft"});lg.onAdd=()=>{const d=L.DomUtil.create("div","hm-legend");d.id="hm_legend";L.DomEvent.disableClickPropagation(d);return d};lg.addTo(H.map);
 fetch("api/heatmap/admin0.geojson").then(r=>r.json()).then(j=>{H.a0=L.geoJSON(j,{renderer:H.rend0,pane:"hmReg",style:st0,onEachFeature:(f,l)=>{
   l.on("click",e=>{L.DomEvent.stopPropagation(e);const cc=f.properties.ISO_A2_EH;selectRegion({type:"cc",key:cc,name:f.properties.NAME},l)});
   l.on("mouseover",()=>l.setStyle({weight:1.6,color:"#ffffffcc"}));l.on("mouseout",()=>H.a0.resetStyle(l));
   l.bindTooltip(()=>tt0(f),{sticky:true,className:"hm-tt",direction:"top",offset:[0,-6]})}});layers()}).catch(err=>{$$("hm_zh").textContent="country boundaries failed to load: "+err})}
function tt0(f){const cc=f.properties.ISO_A2_EH,o=H.agg&&H.agg.cc[cc];return `<b>${e_(f.properties.NAME)}</b><br>${o?`${o.n} alert${o.n==1?"":"s"} · top rank ${o.max}`:"no located alerts in this view"}`}
function tt1(f){const k=f.properties.gn_a1_code,o=H.agg&&H.agg.a1[k];return `<b>${e_(f.properties.name)}</b>, ${e_(f.properties.admin)}<br>${o?`${o.n} alert${o.n==1?"":"s"} · top rank ${o.max}`:"no alerts placed at state level or finer"}`}
function st0(f){const o=H.agg&&H.agg.cc[f.properties.ISO_A2_EH];const z=H.map?H.map.getZoom():2,deep=z>=4;
 if(!o)return{color:"#3a4250",weight:deep?.4:.5,fillOpacity:deep?0:.06,fillColor:"#1b2a3a",opacity:deep?.5:.7};
 return{color:deep?"#7d8796":"#0b0d10",weight:deep?.8:.6,fillColor:ramp(Math.sqrt(o.v/H.agg.mx0)*.92+.08),fillOpacity:deep?0:.62,opacity:.9}}
function st1(f){const o=H.agg&&H.agg.a1[f.properties.gn_a1_code];const z=H.map.getZoom(),pts=z>=6;
 if(!o)return{color:"#3a4250",weight:.35,fillOpacity:0,opacity:.55};
 return{color:"#0b0d10",weight:.5,fillColor:ramp(Math.sqrt(o.v/H.agg.mx1)*.92+.08),fillOpacity:pts?.25:.6,opacity:.8}}
function loadA1(){if(H.a1||H.a1loading)return;H.a1loading=true;$$("hm_zh").textContent="loading states and provinces…";
 fetch("api/heatmap/admin1.geojson").then(r=>r.json()).then(j=>{H.a1raw=j;buildA1();H.a1loading=false;layers()}).catch(err=>{H.a1loading=false;$$("hm_zh").textContent="state boundaries failed to load: "+err})}
function buildA1(){if(!H.a1raw||!H.d)return;const have=new Set(H.d.items.map(x=>x.cc).filter(Boolean));if(H.a1)H.map.removeLayer(H.a1);
 H.a1=L.geoJSON({type:"FeatureCollection",features:H.a1raw.features.filter(f=>have.has(f.properties.iso_a2))},{renderer:H.rend1,pane:"hmReg",style:st1,onEachFeature:(f,l)=>{
  l.on("click",e=>{L.DomEvent.stopPropagation(e);selectRegion({type:"a1",key:f.properties.gn_a1_code,cc:f.properties.iso_a2,name:f.properties.name,cn:f.properties.admin},l)});
  l.on("mouseover",()=>l.setStyle({weight:1.6,color:"#ffffffcc"}));l.on("mouseout",()=>H.a1.resetStyle(l));
  l.bindTooltip(()=>tt1(f),{sticky:true,className:"hm-tt",direction:"top",offset:[0,-6]})}});H.a1cc=[...have].sort().join()}
function layers(){if(!H.map)return;const z=H.map.getZoom(),m=H.map;
 if(z>=4&&!H.a1)loadA1();
 const want0=H.lay.reg&&H.a0,want1=H.lay.reg&&H.a1&&z>=4;
 if(H.a0){if(want0&&!m.hasLayer(H.a0))H.a0.addTo(m);if(!want0&&m.hasLayer(H.a0))m.removeLayer(H.a0);if(want0)H.a0.setStyle(st0)}
 if(H.a1){if(want1&&!m.hasLayer(H.a1))H.a1.addTo(m);if(!want1&&m.hasLayer(H.a1))m.removeLayer(H.a1);if(want1)H.a1.setStyle(st1)}
 if(H.heat){if(H.lay.heat&&!m.hasLayer(H.heat))H.heat.addTo(m);if(!H.lay.heat&&m.hasLayer(H.heat))m.removeLayer(H.heat)}
 if(H.mc){const w=H.lay.pts&&z>=6;if(w&&!m.hasLayer(H.mc))H.mc.addTo(m);if(!w&&m.hasLayer(H.mc))m.removeLayer(H.mc)}
 $$("hm_zh").textContent=z<4?"World view · countries shaded by alert load · zoom in (or click a country) for states and provinces":z<6?"Regional view · states and provinces · zoom in further for individual alerts":"City view · clustered alerts · click a dot or cluster";
 legend()}
function legend(){const el=$$("hm_legend");if(!el)return;const z=H.map.getZoom();const mx=z>=4?(H.agg?H.agg.mx1:1):(H.agg?H.agg.mx0:1);
 el.innerHTML=`<b>${z>=4?"States / provinces":"Countries"}</b> — ${H.wm=="sev"?"severity (sum of ranks)":"number of alerts"}<div class=ramp style="background:linear-gradient(90deg,${RAMP.join(",")})"></div><div class=rl><span>low</span><span>${Math.round(mx)}</span></div>
 <div style="margin-top:4px">${GR.map(([g,l])=>`<span style="white-space:nowrap;margin-right:6px"><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${col(g)};margin-right:3px"></i>${e_(l.split(" ")[0])}</span>`).join("")}</div>`;legendLift()}
// narrow maps: the attribution line wraps under the legend, so lift the legend just above it
function legendLift(){const el=$$("hm_legend"),at=H.map&&H.map.getContainer().querySelector(".leaflet-control-attribution");if(!el||!at)return;
 el.style.marginBottom="";const a=at.getBoundingClientRect(),b=el.getBoundingClientRect();el.style.marginBottom=(a.width&&a.left<b.right&&a.top<b.bottom)?(at.offsetHeight+4)+"px":""}
function heatAndPoints(L_){if(!H.map)return;const m=H.map;
 const pts=L_.map(x=>[x.lat,x.lon,wt(x)]);
 if(H.heat)m.removeLayer(H.heat);
 if(typeof L.heatLayer=="function")H.heat=L.heatLayer(pts,{pane:"hmHeat",radius:22,blur:20,maxZoom:6,max:H.wm=="sev"?1.1:3,minOpacity:.28,gradient:{.15:"#3b2a6b",.35:"#7a2d8c",.55:"#c2255c",.72:"#f0532d",.86:"#fa8c16",1:"#ffe58f"}});
 if(H.mc)m.removeLayer(H.mc);
 if(L.markerClusterGroup){H.mc=L.markerClusterGroup({maxClusterRadius:42,showCoverageOnHover:false,spiderfyOnMaxZoom:true,
   iconCreateFunction:c=>{const ms=c.getAllChildMarkers(),mx=Math.max(...ms.map(k=>k.options.hmRank||0)),n=c.getChildCount(),s=n<10?30:n<50?36:44;
    return L.divIcon({html:`<div><span>${n}</span></div>`,className:`marker-cluster hm-mc ${mx>=7?"hi":mx>=4?"":"lo"}`,iconSize:[s,s]})}});
  L_.filter(x=>x.prec!="country"&&x.prec!="state").sort((a,b)=>a.rank-b.rank).forEach(x=>{const s=Math.round(9+x.rank*1.3);
   const mk=L.marker([x.lat,x.lon],{hmRank:x.rank,icon:L.divIcon({className:"",html:`<span class=hm-pin style="display:block;width:${s}px;height:${s}px;background:${col(x.grp)}"></span>`,iconSize:[s,s]}),title:x.title.slice(0,120)});
   mk.on("click",()=>selectRegion({type:"pt",lat:x.lat,lon:x.lon,name:x.city||x.place||"This location",id:x.id}));H.mc.addLayer(mk)})}
 layers()}

// ---------- region selection + side panel ----------
function bigBounds(layer){let best=null,ba=-1;const walk=ls=>{ls.forEach(r=>{if(Array.isArray(r[0])&&!("lat" in r[0])){walk(r);return}if(r&&r.length){const b=L.latLngBounds(r),a=(b.getEast()-b.getWest())*(b.getNorth()-b.getSouth());if(a>ba){ba=a;best=b}}})};
 try{walk(layer.getLatLngs())}catch(_){}return best||layer.getBounds()}
function selectRegion(sel,layer){H.sel=sel;H.page=25;if(layer&&H.map){const b=bigBounds(layer);if(b&&b.isValid())H.map.flyToBounds(b,{maxZoom:sel.type=="a1"?7:5,padding:[20,20],duration:.6})}
 side();crumb()}
function crumb(){const el=$$("hm_crumb"),s=H.sel;let h=`<a data-c="world">${ico("globe")} World</a>`;
 if(s){const cc=s.type=="cc"?s.key:s.cc||(H.d&&(H.d.items.find(x=>x.id==s.id)||{}).cc);const cn=(H.agg&&H.agg.cc[cc]||{}).name||(s.type=="cc"?s.name:s.cn)||cc;
  if(cc)h+=` › ${s.type=="cc"?`<b>${e_(cn)}</b>`:`<a data-c="cc" data-k="${e_(cc)}">${e_(cn)}</a>`}`;if(s.type!="cc")h+=` › <b>${e_(s.name)}</b>`}
 el.innerHTML=h}
$$("hm_crumb").onclick=e=>{const a=e.target.closest("[data-c]");if(!a)return;if(a.dataset.c=="world"){H.sel=null;H.map&&H.map.flyTo([24,12],2,{duration:.6});side();crumb();return}
 const k=a.dataset.k,l=H.a0&&H.a0.getLayers().find(l=>l.feature.properties.ISO_A2_EH==k);selectRegion({type:"cc",key:k,name:l?l.feature.properties.NAME:k},l)};
function selItems(){const s=H.sel,L_=H.vis||[];if(!s)return[];if(s.type=="cc")return L_.filter(x=>x.cc==s.key);if(s.type=="a1")return L_.filter(x=>x.a1==s.key);
 return L_.filter(x=>x.prec!="country"&&x.prec!="state"&&Math.abs(x.lat-s.lat)<.02&&Math.abs(x.lon-s.lon)<.02)}
function sortA(L_){return L_.slice().sort((a,b)=>(b.rank-a.rank)||(Date.parse(b.t)-Date.parse(a.t)))}
function accItem(x,opt){opt=opt||{};const id=(opt.pre||"")+x.id,open=(opt.set||H.open).has(id);
 const lk=(x.links||[]).map(l=>`<a href="${U(l.u)}" target=_blank rel="noopener noreferrer">${e_(l.s||"source")} ↗</a>`).join("")+(x.nlinks>5?`<span class=meta>+${x.nlinks-5} more on The Wire</span>`:"");
 const kv=[["Category",x.cat],["Rank / score",`${x.rank}/10 · ${x.score}/100`],["Confidence",`${x.conf||"—"} · ${x.n||1} report${x.n==1?"":"s"} from ${x.fam||1} source${x.fam==1?"":"s"}`],["Time",etF(x.t)+" ("+ago(x.t)+")"]];
 if(x.lat!=null)kv.push(["Place",x.place||"—"],["Precision",PREC[x.prec]||x.prec],["Located by",`${(H.d.labels.method||{})[x.m]||x.m}${x.md?" — "+x.md:""}`],["Geo confidence",x.gc||"—"],["Coordinates",`${(+x.lat).toFixed(3)}, ${(+x.lon).toFixed(3)}`]);
 if(x.ev)kv.push(["Evidence",x.ev]);
 if(x.reason)kv.push(["Why unlocated",x.reason]);if(x.cands&&x.cands.length)kv.push(["Candidates",x.cands.join(" · ")]);
 const sub=opt.sub!=null?opt.sub:`${etF(x.t)} · ${x.conf||"?"} confidence${x.watch?' <span class="hm-tag unc">watchlist</span>':' <span class="hm-tag ok">on The Wire</span>'}${x.place?" · "+e_(x.place):""}`;
 return `<div class="hm-acc${open?" open":""}" data-acc="${e_(id)}" style="border-left-color:${col(x.grp)}"><button class=hm-ah type=button aria-expanded="${open}"><span class="hm-rank ${rk(x.rank)}" title="Rank ${x.rank}/10 · score ${x.score}">${x.rank}</span><span class=t>${e_(x.title)}<small>${sub}</small></span><span class=hm-chev>${ico("chev")}</span></button>
 <div class=hm-ab><div class=hm-ai><div class=hm-ac><div class=kv>${kv.map(([k,v])=>`<span>${e_(k)}</span><span>${e_(v)}</span>`).join("")}</div><div class=lk>${lk||'<span class=meta>no source link</span>'}${x.watch==0?`<a href="#wire" data-goto="${e_(x.id)}">show on The Wire →</a>`:""}</div></div></div></div></div>`}
function regRow(i,name,o,mx,attrs){return `<button type=button class=hm-reg ${attrs}><span class=rk>${i}</span><span><span>${e_(name)}</span><div class=bar style="width:${Math.max(4,100*o.v/mx)}%;background:${ramp(Math.sqrt(o.v/mx)*.92+.08)}"></div></span><span class=n><b>${o.n}</b> · max ${o.max}</span></button>`}
function side(){const el=$$("hm_side");if(!H.d){el.innerHTML='<div class=hm-empty>Loading…</div>';return}const s=H.sel,A=H.agg;
 if(!s){const C=Object.entries(A.cc).sort((a,b)=>b[1].v-a[1].v),S=Object.entries(A.a1).sort((a,b)=>b[1].v-a[1].v);
  const n=(H.vis||[]).length;
  el.innerHTML=`<div class=hm-sh><div class=nm>Top regions</div><div class=sub>${n} located alert${n==1?"":"s"} · ${WINL[H.win]} · ranked by ${H.wm=="sev"?"severity (sum of ranks)":"number of alerts"}. Click a row or the map.</div></div>
  <div class=hm-sb>${C.length?`<div class=hm-h4>Countries</div>${C.slice(0,12).map(([k,o],i)=>regRow(i+1,o.name||k,o,C[0][1].v,`data-cc="${e_(k)}"`)).join("")}`:'<div class=hm-empty>No located alerts match these filters. Widen the time window, lower the severity slider or turn categories back on.</div>'}
  ${S.length?`<div class=hm-h4>States / provinces</div>${S.slice(0,10).map(([k,o],i)=>regRow(i+1,`${o.name||k}, ${o.cn||o.cc}`,o,S[0][1].v,`data-a1="${e_(k)}"`)).join("")}`:""}
  ${n?`<div class=hm-h4>Highest-ranked located alerts</div>${sortA(H.vis).slice(0,8).map(x=>accItem(x)).join("")}`:""}</div>`;return}
 const L_=sortA(selItems());let name=s.name,sub="",extra="";
 if(s.type=="cc"){const o=A.cc[s.key];name=(o&&o.name)||s.name;const subs=Object.entries(A.a1).filter(([k,v])=>v.cc==s.key).sort((a,b)=>b[1].v-a[1].v);
  sub=`${L_.length} alert${L_.length==1?"":"s"} · ${o?o.a1n:0} with state or city detail · top rank ${o?o.max:"—"}`;
  if(subs.length)extra=`<div class=hm-h4>Inside ${e_(name)}</div>${subs.slice(0,8).map(([k,v],i)=>regRow(i+1,v.name||k,v,subs[0][1].v,`data-a1="${e_(k)}"`)).join("")}${subs.length>8?`<div class=meta style="padding:2px 8px">+${subs.length-8} more — zoom in on the map</div>`:""}<div class=hm-h4>Alerts</div>`}
 else if(s.type=="a1"){const o=A.a1[s.key];const cl=(H.vis||[]).filter(x=>x.cc==s.cc&&!x.a1).length;const cnm=(A.cc[s.cc]||{}).name||(o&&o.cn)||s.cn;name=`${s.name}${cnm?", "+cnm:""}`;
  sub=`${L_.length} alert${L_.length==1?"":"s"} placed in this state/province · top rank ${o?o.max:"—"}`;
  if(cl)extra=`<button type=button class=hm-more data-cc="${e_(s.cc)}">+ ${cl} country-level alert${cl==1?"":"s"} for ${e_((A.cc[s.cc]||{}).name||s.cc)} (no state named) →</button>`}
 else{sub=`${L_.length} alert${L_.length==1?"":"s"} at this spot`}
 const c={};L_.forEach(x=>c[x.grp]=(c[x.grp]||0)+1);
 el.innerHTML=`<div class=hm-sh><div class=nm>${e_(name)}<button type=button class=x id=hm_close title="Back to top regions">✕ close</button></div><div class=sub>${sub} · ${WINL[H.win]}</div>${L_.length?catbar(c,L_.length):""}</div>
 <div class=hm-sb>${extra}${L_.slice(0,H.page).map(x=>accItem(x)).join("")||'<div class=hm-empty>No alerts here match the current filters.</div>'}${L_.length>H.page?`<button type=button class=hm-more id=hm_more>Show ${Math.min(25,L_.length-H.page)} more of ${L_.length-H.page} remaining</button>`:""}</div>`}
$$("hm_side").addEventListener("click",e=>{
 const h=e.target.closest(".hm-ah");if(h&&!e.target.closest("a")){togAcc(h.parentElement,H.open);return}
 if(e.target.closest("#hm_close")){H.sel=null;side();crumb();return}
 if(e.target.closest("#hm_more")){H.page+=25;const sb=$$("hm_side").querySelector(".hm-sb"),y=sb.scrollTop;side();$$("hm_side").querySelector(".hm-sb").scrollTop=y;return}
 const cc=e.target.closest("[data-cc]");if(cc){const k=cc.dataset.cc,l=H.a0&&H.a0.getLayers().find(l=>l.feature.properties.ISO_A2_EH==k);selectRegion({type:"cc",key:k,name:l?l.feature.properties.NAME:k},l);return}
 const a1=e.target.closest("[data-a1]");if(a1){const k=a1.dataset.a1,o=H.agg.a1[k]||{};const go=()=>{const l=H.a1&&H.a1.getLayers().find(l=>l.feature.properties.gn_a1_code==k);selectRegion({type:"a1",key:k,cc:o.cc,name:o.name||k,cn:o.cn},l)};
  if(H.a1)go();else{selectRegion({type:"a1",key:k,cc:o.cc,name:o.name||k,cn:o.cn});loadA1();const w=setInterval(()=>{if(H.a1){clearInterval(w);go()}},200);setTimeout(()=>clearInterval(w),15000)}return}
 gotoWire(e)});
function gotoWire(e){const a=e.target.closest("[data-goto]");if(!a)return;e.preventDefault();const id=a.dataset.goto;const b=document.querySelector('.tabs button[data-tab="threat"]');if(b)b.click();
 setTimeout(()=>{const el=document.querySelector(`[data-cid="${CSS.escape(id)}"]`);if(el){el.scrollIntoView({block:"center"});el.style.outline="2px solid var(--hi)";setTimeout(()=>el.style.outline="",2500)}},350)}
function togAcc(acc,set){const id=acc.dataset.acc,o=!acc.classList.contains("open");acc.classList.toggle("open",o);acc.querySelector(":scope>.hm-ah").setAttribute("aria-expanded",String(o));o?set.add(id):set.delete(id)}

// ---------- unlocated list ----------
function unlRender(){const U_=(H.d.unlocated||[]).filter(pass);const g={};U_.forEach(x=>(g[x.rc]=g[x.rc]||[]).push(x));const lab=H.d.labels.reason||{};
 const G_=Object.entries(g).sort((a,b)=>b[1].length-a[1].length);
 $$("hm_unlmeta").textContent=`— ${U_.length} alert${U_.length==1?"":"s"} in the ${WINL[H.win]} could not be placed (matching the filters above), grouped by reason`;
 $$("hm_unl").innerHTML=G_.map(([rc,L_])=>{const id="g_"+rc,open=H.openU.has(id),n=H.upage[rc]||20;const S=sortA(L_);
  return `<div class="hm-acc hm-grp${open?" open":""}" data-acc="${e_(id)}"><button class=hm-ah type=button aria-expanded="${open}"><span class=hm-cnt>${L_.length}</span><span class=t><b>${e_(lab[rc]||rc)}</b><small>e.g. “${e_(S[0].title.slice(0,90))}${S[0].title.length>90?"…":""}” — ${e_(S[0].reason.slice(0,140))}</small></span><span class=hm-chev>${ico("chev")}</span></button>
  <div class=hm-ab><div class=hm-ai><div class=hm-ac>${S.slice(0,n).map(x=>accItem(x,{pre:"u_",set:H.openU,sub:`${etF(x.t)} · ${e_(x.cat)} · <span class=hm-rsn>${e_(x.reason)}</span>`})).join("")}${L_.length>n?`<button type=button class=hm-more data-umore="${e_(rc)}">Show ${Math.min(20,L_.length-n)} more of ${L_.length-n}</button>`:""}</div></div></div></div>`}).join("")||'<div class=hm-empty>Every alert matching the filters has a location.</div>'}
$$("hm_unl").addEventListener("click",e=>{const m=e.target.closest("[data-umore]");if(m){const rc=m.dataset.umore;H.upage[rc]=(H.upage[rc]||20)+20;unlRender();return}
 const h=e.target.closest(".hm-ah");if(h&&!e.target.closest("a")){togAcc(h.parentElement,H.openU);return}gotoWire(e)});

// ---------- status, footer, stats ----------
function status(){const d=H.d,c=d.coverage,w=d.worker;const busy=w.running;
 $$("hm_status").innerHTML=`<span class=hm-cov><span class="hm-dot${busy?" busy":""}"></span>Geocoding coverage: <b>located ${c.located} of ${c.total}</b> alerts from the last ${d.window_days} days (<b>${c.pct}%</b>) <span class=hm-covbar><i style="width:${c.pct}%"></i></span></span>
 <span>${busy?"geocoder running now…":`last pass ${e_(w.last_run_et||"—")}${w.next_in_s!=null?` · next in ${Math.floor(w.next_in_s/60)}:${String(w.next_in_s%60).padStart(2,"0")}`:""}`}</span><span>data ${e_(d.generated_et||"")}</span>`}
function footStats(){const d=H.d,c=d.coverage,w=d.worker;
 const v=H.vis||[],u=(d.unlocated||[]).filter(pass),tot=v.length+u.length;
 $$("hm_foot").innerHTML=`<span>This view: located <b>${v.length}</b> of ${tot}${tot?` (${Math.round(100*v.length/tot)}%)`:""} · ${WINL[H.win]} · severity ≥ ${H.sev}</span><span>All ${d.window_days} days: located ${c.located} of ${c.total} (${c.pct}%)</span><span>Nominatim answers cached: ${w.nominatim_cached} (${w.nominatim_calls_total} lookups made, max 1/s)</span><span><a href="api/heatmap/geo.csv" download>located CSV</a> · <a href="api/heatmap/unlocated.csv" download>unlocated CSV</a></span>`;
 const bar=(o,labf,colr)=>{const T=Object.values(o).reduce((a,b)=>a+b,0)||1,mx=Math.max(1,...Object.values(o));return Object.entries(o).map(([k,n])=>`<div class=r><span>${e_(labf(k))}</span><span class=v>${n}</span><span><i style="width:${100*n/mx}%;background:${colr}"></i></span></div>`).join("")||'<div class=meta>none</div>'};
 const cnt=(L_,k)=>{const o={};L_.forEach(x=>o[x[k]]=(o[x[k]]||0)+1);return Object.fromEntries(Object.entries(o).sort((a,b)=>b[1]-a[1]))};
 $$("hm_stats").innerHTML=`<div class=hm-stat><h4>Located by method · this view</h4>${bar(cnt(v,"m"),k=>(d.labels.method||{})[k]||k,"#4aa3ff")}</div>
 <div class=hm-stat><h4>Precision · this view</h4>${bar(cnt(v,"prec"),k=>PREC[k]||k,"#52c41a")}</div>
 <div class=hm-stat><h4>Geocode confidence · this view</h4>${bar(cnt(v,"gc"),k=>k||"—","#faad14")}</div>
 <div class=hm-stat><h4>Unlocated by reason · this view</h4>${bar(cnt(u,"rc"),k=>(d.labels.reason||{})[k]||k,"#ff7a45")}</div>`}

// ---------- draw ----------
function redraw(){if(!H.d)return;H.vis=H.d.items.filter(pass);H.agg=aggregate(H.vis);ctlRender();status();footStats();
 if(H.shown){initMap();if(H.map){if(H.a1raw&&H.a1cc!==[...new Set(H.d.items.map(x=>x.cc).filter(Boolean))].sort().join())buildA1();heatAndPoints(H.vis);setTimeout(()=>H.map.invalidateSize(),60)}}
 side();crumb();unlRender()}
async function load(run){if(H.busy)return;H.busy=true;try{const r=await fetch("api/heatmap"+(run?"?run=1":""),{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);H.d=j;H.lastLoad=Date.now();redraw()}
 catch(err){$$("hm_status").innerHTML=`<span style="color:var(--hi)">Heat map data unavailable: ${e_(err.message||err)}</span>`}finally{H.busy=false}}

// ---------- tab wiring, refresh, auto-refresh ----------
function onShow(){H.shown=true;if(!H.d)load(true);else{redraw()}}
nav&&nav.addEventListener("click",e=>{const b=e.target.closest("button");if(!b||!b.dataset.tab)return;if(b.dataset.tab=="heatmap")setTimeout(onShow,30);else H.shown=false});
const rb=$$("hm_ref");if(rb)rb.onclick=async e=>{e.stopPropagation();rb.disabled=true;rb.textContent="refreshing…";try{if($("refresh")&&$("refresh").onclick)await $("refresh").onclick()}catch(_){}
 await load(true);rb.textContent="⟳ Refresh";rb.disabled=false};
// every scanner pass (scheduled or manual) pushes a "scan" event: geocode the new alerts and redraw
let scanT=0;const hook=()=>{if(typeof LV=="object"&&LV&&LV.es){LV.es.addEventListener("scan",()=>{clearTimeout(scanT);scanT=setTimeout(()=>load(true),4000)});LV.es.addEventListener("alert",()=>{clearTimeout(scanT);scanT=setTimeout(()=>load(true),6000)});return true}return false};
if(!hook()){let n=0;const w=setInterval(()=>{if(hook()||++n>20)clearInterval(w)},1000)}
setInterval(()=>{if(H.shown&&!document.hidden)load(false)},60000);
setInterval(()=>{if(H.d&&H.d.worker&&H.d.worker.next_in_s!=null&&H.shown){H.d.worker.next_in_s=Math.max(0,H.d.worker.next_in_s-1);status()}},1000);
if((location.hash||"")=="#heatmap")setTimeout(()=>{const b=document.querySelector('.tabs button[data-tab="heatmap"]');if(b&&!b.classList.contains("on"))b.click()},350);
})();
