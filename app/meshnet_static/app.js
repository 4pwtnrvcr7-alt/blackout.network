// BLACKOUT.NETWORK /mesh: live public Meshtastic node map (MeshMap.net snapshot via our box collector) + drop-off watch.
// Maps: MapLibre GL JS 5.24.0 (BSD-3, SRI-pinned, unpkg with jsDelivr fallback; same pins as the Crime page) + OpenFreeMap vector tiles. No OSM tile servers.
(function(){"use strict";
if(window.__bnMesh)return;window.__bnMesh=1;
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
var LIB=["dist/maplibre-gl.js","sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp"],
    CSS=["dist/maplibre-gl.css","sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK"],CDN=["https://unpkg.com/maplibre-gl@5.24.0/","https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/"];
var STYLE_D="https://tiles.openfreemap.org/styles/dark",STYLE_L="https://tiles.openfreemap.org/styles/positron";
var ROLE={R:"Router",P:"Repeater",C:"Client",M:"Client (mute)",B:"Client (base)",T:"Tracker",S:"Sensor"};
var VIEWS={cfl:{center:[-81.33,28.70],zoom:8.2},us:{center:[-96,38.5],zoom:3.3},world:{center:[10,25],zoom:1.1}};
function light(){return document.documentElement.getAttribute("data-theme")==="light"}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function tag(n,a){return new Promise(function(ok,no){var e=document.createElement(n);for(var k in a)e.setAttribute(k,a[k]);e.crossOrigin="anonymous";e.onload=ok;e.onerror=no;document.head.appendChild(e)})}
var libP=null;
function lib(){if(window.maplibregl)return Promise.resolve(true);if(libP)return libP;
 libP=(async function(){for(var i=0;i<CDN.length;i++){try{await tag("link",{rel:"stylesheet",href:CDN[i]+CSS[0],integrity:CSS[1]}).catch(function(){});
  await tag("script",{src:CDN[i]+LIB[0],integrity:LIB[1]});if(window.maplibregl)return true}catch(e){}}return false})();return libP}
function ago(m){if(m==null)return"–";if(m<1)return"just now";if(m<60)return m+" min ago";var h=Math.round(m/60);return h<48?h+" h ago":Math.round(h/24)+" d ago"}
function etTime(iso){try{return new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit",month:"short",day:"numeric"})+" ET"}catch(e){return iso||""}}
var S={d:null,map:null,view:"cfl"};
function geo(d){var hw=d.hw||[];return {type:"FeatureCollection",features:(d.nodes||[]).map(function(n){
 return {type:"Feature",geometry:{type:"Point",coordinates:[n[1],n[0]]},properties:{r:(n[2]==="R"||n[2]==="P")?1:0,role:ROLE[n[2]]||"Client",hw:hw[n[3]]||"",age:n[4],old:n[4]>60?1:0,sn:n[5]||""}}})}}
function ring(lon,lat,km){var pts=[],R=6371,d=km/R,la=lat*Math.PI/180,lo=lon*Math.PI/180;for(var i=0;i<=64;i++){var b=i/64*2*Math.PI;
 var la2=Math.asin(Math.sin(la)*Math.cos(d)+Math.cos(la)*Math.sin(d)*Math.cos(b));var lo2=lo+Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(la),Math.cos(d)-Math.sin(la)*Math.sin(la2));
 pts.push([lo2*180/Math.PI,la2*180/Math.PI])}return pts}
function areasGeo(d){var st={};(d.regions||[]).forEach(function(r){st[r.id]=r});return {type:"FeatureCollection",features:(d.areas||[]).map(function(a){var r=st[a.id]||{};
 return {type:"Feature",geometry:{type:"Polygon",coordinates:[ring(a.lon,a.lat,a.r_km)]},properties:{id:a.id,name:a.name,focus:a.id===d.focus?1:0,watch:r.status==="watch"?1:0}}})}}
function layers(m){var d=S.d||{};var Y=light()?"#C97B00":"#FFC21A",C=light()?"#1f6fd1":"#4aa3ff",O=light()?"#9aa3ae":"#5b6573";
 if(m.getSource("mx-n")){m.getSource("mx-n").setData(geo(d));m.getSource("mx-a").setData(areasGeo(d));return}
 m.addSource("mx-a",{type:"geojson",data:areasGeo(d)});m.addSource("mx-n",{type:"geojson",data:geo(d)});
 m.addLayer({id:"mx-af",type:"fill",source:"mx-a",paint:{"fill-color":Y,"fill-opacity":["case",["==",["get","focus"],1],.07,.03]}});
 m.addLayer({id:"mx-al",type:"line",source:"mx-a",paint:{"line-color":Y,"line-width":["case",["==",["get","focus"],1],2,1],"line-dasharray":[2,2],"line-opacity":.8}});
 m.addLayer({id:"mx-nc",type:"circle",source:"mx-n",paint:{"circle-radius":["interpolate",["linear"],["zoom"],1,["case",["==",["get","r"],1],2.4,1.6],8,["case",["==",["get","r"],1],5.5,3.8],12,7],
  "circle-color":["case",["==",["get","old"],1],O,["==",["get","r"],1],Y,C],"circle-opacity":["case",["==",["get","old"],1],.55,.9],
  "circle-stroke-color":light()?"#ffffff":"#0b0d10","circle-stroke-width":.6}});
 var pop=new maplibregl.Popup({closeButton:false,offset:8});
 m.on("mousemove","mx-nc",function(e){m.getCanvas().style.cursor="pointer";var p=e.features[0].properties;
  pop.setLngLat(e.lngLat).setHTML('<div class="mx-pop"><b>'+esc(p.sn||"Node")+'</b><br>'+esc(p.role)+(p.hw?' · '+esc(p.hw.replace(/_/g," ")):"")+'<br>Last heard '+esc(ago(+p.age))+'</div>').addTo(m)});
 m.on("mouseleave","mx-nc",function(){m.getCanvas().style.cursor="";pop.remove()});
 m.on("click","mx-nc",function(e){var p=e.features[0].properties;pop.setLngLat(e.lngLat).setHTML('<div class="mx-pop"><b>'+esc(p.sn||"Node")+'</b><br>'+esc(p.role)+(p.hw?' · '+esc(p.hw.replace(/_/g," ")):"")+'<br>Last heard '+esc(ago(+p.age))+'</div>').addTo(m)})}
function mk(){var el=$("#mx_map");if(!el||S.map)return;var v=VIEWS[S.view];
 var m=new maplibregl.Map({container:el,style:light()?STYLE_L:STYLE_D,center:v.center,zoom:v.zoom,attributionControl:{compact:true},cooperativeGestures:true,dragRotate:false,pitchWithRotate:false,maxZoom:13});
 m.touchZoomRotate.disableRotation();m.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");S.map=m;
 m.on("style.load",function(){layers(m)});
 new MutationObserver(function(){if(!S.map)return;S.map.setStyle(light()?STYLE_L:STYLE_D)}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]})}
function view(k){S.view=k;$$(".mx-seg button").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.view===k?"true":"false")});
 if(S.map){var v=VIEWS[k];S.map.jumpTo({center:v.center,zoom:v.zoom})}}
function panels(){var d=S.d||{};var reg={};(d.regions||[]).forEach(function(r){reg[r.id]=r});var f=d.feed||{};
 var st=$("#mx_stats");if(st&&d.counts)st.textContent=(d.counts.total||0).toLocaleString()+" nodes on the map · "+(d.counts.active||0).toLocaleString()+" heard in the last hour";
 var fr=$("#mx_fresh");if(fr)fr.innerHTML=d.generated?("Updated "+esc(etTime(d.generated))+" · source <a href=\"https://meshmap.net/\" target=\"_blank\" rel=\"noopener\">MeshMap.net</a>"+(f.ok?"":" · <b>data source delayed: drop-off watch paused</b>")):"Waiting for the first sync.";
 var c=reg[d.focus||"area:cfl"]||{};var kv=$$("#mx_focus_kv b");
 if(kv.length===3){kv[0].textContent=c.total!=null?c.total:"–";kv[1].textContent=c.active!=null?c.active:"–";
  var num=c.regular>=10&&c.silent_pct!=null;kv[2].textContent=num?(c.silent+" of "+c.regular):(f.baseline_ready?"Too few to judge":"Baseline building");kv[2].classList.toggle("mx-kt",!num)}
 var wl=$("#mx_watch_list");if(!wl)return;var sig=d.signals||[];
 var rows=(d.regions||[]).filter(function(r){return r.kind!=="world"&&r.regular>=10}).sort(function(a,b){return (b.silent_pct||0)-(a.silent_pct||0)}).slice(0,8);
 if(!f.baseline_ready){wl.innerHTML='<p class="mx-mu">Building the 24-hour baseline (needs 6 hours of checks). No flags until then.</p>';return}
 if(!f.ok){wl.innerHTML='<p class="mx-mu">The public data source is delayed, so the watch is paused. No flags are raised on stale data.</p>';return}
 var h=sig.length?sig.map(function(s){return '<div class="mx-wr mx-watch"><span class="mx-pill">WATCHLIST · RANK '+s.rank+'</span><b>'+esc(s.name)+'</b><span>'+s.silent+' of '+s.regular+' regular nodes quiet ('+Math.round(s.silent_pct*100)+'%) · unconfirmed</span></div>'}).join("")
  :'<p class="mx-ok">No region flagged right now.</p>';
 h+='<details class="mx-det"><summary>Quietest regions</summary>'+rows.map(function(r){return '<div class="mx-wr"><b>'+esc(r.name)+'</b><span>'+r.silent+' of '+r.regular+' regular nodes quiet ('+Math.round((r.silent_pct||0)*100)+'%)</span></div>'}).join("")+'</details>';
 wl.innerHTML=h}
async function load(){try{var r=await fetch("/api/mesh/nodes",{cache:"no-store"});S.d=await r.json()}catch(e){S.d=S.d||{}}
 panels();if(S.map&&S.map.isStyleLoaded())layers(S.map)}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".mx-seg button");if(b)view(b.dataset.view)});
async function start(){load();var ok=await lib();if(!ok){var el=$("#mx_map");if(el)el.innerHTML='<p class="mx-mu" style="padding:16px">The map library could not load. The counts and watch list below still update.</p>';return}
 mk();setInterval(load,300000)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start();
})();
