// BLACKOUT.NETWORK Crime tab (t392): in-place search, near-real-time heat map, US county and world choropleths.
// Maps: MapLibre GL JS 5.24.0 (BSD-3, SRI-pinned, unpkg with jsDelivr fallback) + OpenFreeMap vector tiles (no OSM tile servers).
(function(){"use strict";
if(window.__bnCrime)return;window.__bnCrime=1;
var $=function(s,r){return (r||document).querySelector(s)},$$=function(s,r){return [].slice.call((r||document).querySelectorAll(s))};
var LIB=["dist/maplibre-gl.js","sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp"],
    CSS=["dist/maplibre-gl.css","sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK"],CDN=["https://unpkg.com/maplibre-gl@5.24.0/","https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/"];
var STYLE_D="https://tiles.openfreemap.org/styles/dark",STYLE_L="https://tiles.openfreemap.org/styles/positron";
var ATTR='<a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
function light(){return document.documentElement.getAttribute("data-theme")==="light"}
function tag(n,a){return new Promise(function(ok,no){var e=document.createElement(n);for(var k in a)e.setAttribute(k,a[k]);e.crossOrigin="anonymous";e.onload=ok;e.onerror=no;document.head.appendChild(e)})}
var libP=null;
function lib(){if(window.maplibregl)return Promise.resolve(true);if(libP)return libP;
 libP=(async function(){for(var i=0;i<CDN.length;i++){try{await tag("link",{rel:"stylesheet",href:CDN[i]+CSS[0],integrity:CSS[1]}).catch(function(){});
  await tag("script",{src:CDN[i]+LIB[0],integrity:LIB[1]});if(window.maplibregl)return true}catch(e){}}return false})();return libP}
function mk(el,opt){var m=new maplibregl.Map(Object.assign({container:el,style:light()?STYLE_L:STYLE_D,attributionControl:{compact:true},
  cooperativeGestures:true,dragRotate:false,pitchWithRotate:false,maxZoom:16},opt||{}));m.touchZoomRotate.disableRotation();m.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
  m.once("load",function(){var a=el.querySelector(".maplibregl-ctrl-attrib");if(a&&el.clientWidth<700)a.classList.remove("maplibregl-compact-show")});
  if(opt&&opt.fit)m.once("load",function(){m.fitBounds(opt.fit,{padding:10,animate:false})});return m}
function fail(el,msg){el.innerHTML='<div class="cr-empty" style="margin:16px">'+msg+'</div>'}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function fmt(v){return v==null?"—":(v<100?v.toFixed(1):Math.round(v).toLocaleString())}
function getJ(u){return fetch(u,{credentials:"same-origin"}).then(function(r){if(!r.ok)throw r.status;return r.json()})}
// ---- TopoJSON -> GeoJSON (Polygon / MultiPolygon only)
function topo(t,name){var sc=t.transform.scale,tr=t.transform.translate,arcs=t.arcs.map(function(a){var x=0,y=0;return a.map(function(p){x+=p[0];y+=p[1];return [x*sc[0]+tr[0],y*sc[1]+tr[1]]})});
 function ring(r){var out=[];r.forEach(function(i){var a=i<0?arcs[~i].slice().reverse():arcs[i];out.push.apply(out,out.length?a.slice(1):a)});
  for(var k=1;k<out.length;k++){var d=out[k][0]-out[k-1][0];if(d>180||d<-180)out[k]=[out[k][0]-360*Math.round(d/360),out[k][1]]}return out}  /* unwrap rings that cross the antimeridian (Russia, Fiji) */
 return {type:"FeatureCollection",features:t.objects[name].geometries.filter(function(g){return g.arcs&&String(g.id)!=="010"})  /* no Antarctica */.map(function(g){
  var c=g.type==="Polygon"?g.arcs.map(ring):g.arcs.map(function(p){return p.map(ring)});return {type:"Feature",id:g.id,properties:Object.assign({id:String(g.id)},g.properties||{}),geometry:{type:g.type,coordinates:c}}})}}
function RAMP(){return light()?["interpolate",["linear"],["get","r"],0,"#fde8e8",0.25,"#f6b3b3",0.5,"#e5605f",0.75,"#b8202a",1,"#6b0b12"]:["interpolate",["linear"],["get","r"],0,"#1d2a36",0.25,"#5b3a3f",0.5,"#a8383d",0.75,"#ff4d4f",1,"#ffb3b4"]}
function choro(m,src,gj){m.addSource(src,{type:"geojson",data:gj});
 var first=(m.getStyle().layers.find(function(l){return l.type==="symbol"})||{}).id;
 m.addLayer({id:src+"-f",type:"fill",source:src,paint:{"fill-color":["case",["<",["get","r"],0],light()?"#e3e6ea":"#252b33",RAMP()],"fill-opacity":0.82}},first);
 m.addLayer({id:src+"-l",type:"line",source:src,paint:{"line-color":light()?"#ffffff":"#0b0d10","line-width":0.3}},first)}
// ---- near-real-time heat map
var heatMap=null;
function initHeat(){var el=$("#cr-heat");if(!el)return;if(heatMap){try{heatMap.remove()}catch(e){}heatMap=null}
 lib().then(function(ok){if(!ok)return fail(el,"The map library could not load. The numbers above are complete without it.");
  getJ("/api/crime/heat?feed="+encodeURIComponent(el.dataset.feed)).then(function(d){
   var lat=+el.dataset.lat,lon=+el.dataset.lon,m=mk(el,{center:[lon,lat],zoom:11});heatMap=m;
   var pts={type:"FeatureCollection",features:d.cells.map(function(c){return {type:"Feature",properties:{v:c[2],p:c[3],o:c[4],t:c[2]+c[3]+c[4]},geometry:{type:"Point",coordinates:[c[1],c[0]]}}})};
   var ser={type:"FeatureCollection",features:d.serious.map(function(s){return {type:"Feature",properties:{c:s[2],w:s[3]},geometry:{type:"Point",coordinates:[s[1],s[0]]}}})};
   var mx=Math.max.apply(null,d.cells.map(function(c){return c[2]+c[3]+c[4]}).concat([1])),cap=Math.max(4,Math.round(mx*0.35));
   m.on("load",function(){
    if(d.bbox&&!el.dataset.fit){try{m.fitBounds([[d.bbox[0],d.bbox[1]],[d.bbox[2],d.bbox[3]]],{padding:20,duration:0,maxZoom:12.5})}catch(e){}}
    if(Math.abs(lat-((d.bbox[1]+d.bbox[3])/2))>0.02||Math.abs(lon-((d.bbox[0]+d.bbox[2])/2))>0.03){m.jumpTo({center:[lon,lat],zoom:12})}
    var first=(m.getStyle().layers.find(function(l){return l.type==="symbol"})||{}).id;
    m.addSource("cells",{type:"geojson",data:pts});m.addSource("ser",{type:"geojson",data:ser});
    m.addLayer({id:"heat",type:"heatmap",source:"cells",maxzoom:16,paint:{"heatmap-weight":["min",1,["/",["get","t"],cap]],
     "heatmap-intensity":["interpolate",["linear"],["zoom"],9,0.9,14,2.2],"heatmap-radius":["interpolate",["linear"],["zoom"],9,7,12,16,15,34],
     "heatmap-color":["interpolate",["linear"],["heatmap-density"],0,"rgba(0,0,0,0)",0.15,"rgba(91,58,63,.55)",0.4,"rgba(168,56,61,.75)",0.65,"#ff4d4f",0.85,"#ffb35c",1,"#fff1c9"],
     "heatmap-opacity":["interpolate",["linear"],["zoom"],13,0.85,16,0.45]}},first);
    m.addLayer({id:"cellpts",type:"circle",source:"cells",minzoom:14,paint:{"circle-radius":["interpolate",["linear"],["get","t"],1,3,20,10],"circle-color":"#ff4d4f","circle-opacity":0.35,"circle-stroke-width":0}});
    m.addLayer({id:"ser",type:"circle",source:"ser",paint:{"circle-radius":["interpolate",["linear"],["zoom"],9,2.2,14,5],"circle-color":"#ff4d4f","circle-stroke-color":"#fff","circle-stroke-width":1,"circle-opacity":0.95}});
    var pop=new maplibregl.Popup({closeButton:false,offset:8});
    m.on("click","ser",function(e){var p=e.features[0].properties;pop.setLngLat(e.lngLat).setHTML('<div class="cr-pop"><b>'+esc(p.c)+'</b><br>'+esc(p.w.replace("T"," ").slice(0,13))+':00 local · block-level location</div>').addTo(m)});
    m.on("click","cellpts",function(e){var p=e.features[0].properties;pop.setLngLat(e.lngLat).setHTML('<div class="cr-pop"><b>'+p.t+' reports</b> in this ~200 m block (30 days)<br>'+p.v+' violent · '+p.p+' property · '+p.o+' other</div>').addTo(m)});
    ["ser","cellpts"].forEach(function(l){m.on("mouseenter",l,function(){m.getCanvas().style.cursor="pointer"});m.on("mouseleave",l,function(){m.getCanvas().style.cursor=""})});
    $$(".cr-maptools button").forEach(function(b){b.onclick=function(){$$(".cr-maptools button").forEach(function(x){x.classList.toggle("on",x===b)});
     var g=b.dataset.g,w=g==="v"?["get","v"]:g==="p"?["get","p"]:["get","t"],c=g==="v"?Math.max(2,cap/3):g==="p"?Math.max(3,cap*0.7):cap;
     m.setPaintProperty("heat","heatmap-weight",["min",1,["/",w,c]]);m.setLayoutProperty("ser","visibility",g==="p"?"none":"visible")}})});
  }).catch(function(){fail(el,"Map data is not available right now.")})})}
// ---- lazy choropleths
function whenVisible(el,fn){if(!el)return;if(!("IntersectionObserver" in window))return fn();var io=new IntersectionObserver(function(es){if(es.some(function(e){return e.isIntersecting})){io.disconnect();fn()}},{rootMargin:"300px"});io.observe(el)}
function initUS(){var el=$("#cr-us");whenVisible(el,function(){lib().then(function(ok){if(!ok)return fail(el,"The map library could not load.");
 Promise.all([getJ("/api/crime/static/counties-10m.json"),getJ("/api/crime/counties")]).then(function(r){
  var gj=topo(r[0],"counties"),D=r[1],vals=Object.keys(D).map(function(k){return D[k][0]}).filter(function(v){return v!=null}).sort(function(a,b){return a-b}),
      q=function(p){return vals[Math.min(vals.length-1,Math.floor(vals.length*p))]||1},hi=q(0.97)||1;
  gj.features.forEach(function(f){var x=D[String(f.id).padStart(5,"0")];f.properties.r=x&&x[0]!=null?Math.min(1,Math.sqrt(x[0]/hi)):-1;f.properties.v=x?x[0]:null;f.properties.pr=x?x[1]:null;
   f.properties.y=x?x[2]:null;f.properties.cv=x?x[3]:null;f.properties.nm=x?x[4]+", "+x[5]:(f.properties.name||"")});
  var m=mk(el,{center:[-96.5,38.5],zoom:3.2,minZoom:1.5,fit:[[-125,24.5],[-66.9,49.5]]});
  m.on("load",function(){m.fitBounds([[-125,24.5],[-66.9,49.5]],{padding:10,duration:0});choro(m,"us",gj);var pop=new maplibregl.Popup({closeButton:false,offset:6});
   m.on("click","us-f",function(e){var p=e.features[0].properties;pop.setLngLat(e.lngLat).setHTML('<div class="cr-pop"><b>'+esc(p.nm)+'</b><br>'+(p.v!=null&&p.v!=="null"?'Violent '+fmt(+p.v)+' · property '+fmt(+p.pr)+' per 100k ('+p.y+')'+(+p.cv<0.6?'<br><i>partial: '+Math.round(+p.cv*100)+'% of residents covered</i>':'')+'<br><a href="/crime?place='+encodeURIComponent(p.nm)+'" data-q="'+esc(p.nm)+'">Open details</a>':'No recent complete FBI data')+'</div>').addTo(m)});
   m.on("mouseenter","us-f",function(){m.getCanvas().style.cursor="pointer"});m.on("mouseleave","us-f",function(){m.getCanvas().style.cursor=""})})}).catch(function(){fail(el,"County data is not available right now.")})})})}
function initWorld(){var el=$("#cr-world");whenVisible(el,function(){lib().then(function(ok){if(!ok)return fail(el,"The map library could not load.");
 Promise.all([getJ("/api/crime/static/countries-110m.json"),getJ("/api/crime/global")]).then(function(r){
  var gj=topo(r[0],"countries"),D={};r[1].forEach(function(x){D[x[0]]=x});
  gj.features.forEach(function(f){var x=D[String(f.id)];f.properties.r=x?Math.min(1,Math.sqrt(x[3]/30)):-1;f.properties.v=x?x[3]:null;f.properties.y=x?x[4]:null;f.properties.nm=x?x[2]:f.properties.name});
  var m=mk(el,{center:[10,20],zoom:0.9,minZoom:0,renderWorldCopies:false,fit:[[-168,-56],[180,75]]});
  m.on("load",function(){choro(m,"w",gj);var pop=new maplibregl.Popup({closeButton:false,offset:6});
   m.on("click","w-f",function(e){var p=e.features[0].properties;pop.setLngLat(e.lngLat).setHTML('<div class="cr-pop"><b>'+esc(p.nm)+'</b><br>'+(p.v!=null&&p.v!=="null"?fmt(+p.v)+' homicides per 100k ('+p.y+')<br><a href="/crime?place='+encodeURIComponent(p.nm)+'" data-q="'+esc(p.nm)+'">Open details</a>':'No recent official figure')+'</div>').addTo(m)});
   m.on("mouseenter","w-f",function(){m.getCanvas().style.cursor="pointer"});m.on("mouseleave","w-f",function(){m.getCanvas().style.cursor=""})})}).catch(function(){fail(el,"Country data is not available right now.")})})})}
// ---- in-place search
var res=$("#cr-result"),inp=$("#cr-q");
function go(q,push){q=(q||"").trim();if(!q)return;res.classList.add("busy");if(inp)inp.value=q;
 getJ("/api/crime/search?q="+encodeURIComponent(q)).then(function(d){res.innerHTML=d.html||'<div class="cr-empty">'+esc(d.message||"Not found")+'</div>';
  if(d.place){document.title="Crime in "+d.place.label+": rates, trends and map | BLACKOUT.NETWORK"}if(push)history.pushState({q:q},"","/crime?place="+encodeURIComponent(q));initHeat()})
 .catch(function(st){if(st===404)return fetch("/api/crime/search?q="+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(d){res.innerHTML='<div class="cr-empty">'+esc(d.message||"We couldn't find that place.")+'</div>'});
  res.innerHTML='<div class="cr-empty">Something went wrong loading that place. Please try again.</div>'})
 .then(function(){res.classList.remove("busy");var y=res.getBoundingClientRect().top+scrollY-80;if(Math.abs(scrollY-y)>200)scrollTo({top:y,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"})})}
var form=$(".cr-search");if(form)form.addEventListener("submit",function(e){e.preventDefault();go(inp.value,true)});
document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("[data-q]");if(!a||e.metaKey||e.ctrlKey||e.shiftKey)return;e.preventDefault();go(a.dataset.q,true)});
addEventListener("popstate",function(){var q=new URLSearchParams(location.search).get("place");if(q)go(q,false)});
initHeat();initUS();initWorld();
})();
