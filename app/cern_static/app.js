/* BLACKOUT.NETWORK · CERN & LHC explainer. Plain JS, no frameworks.
   Maps: MapLibre GL JS 5.24.0 (BSD-3, SRI-pinned, unpkg with jsDelivr fallback; same pins as the Crime page) + OpenFreeMap tiles. No OSM tile servers.
   Live: our own /api/cern/status and /api/cern/live/*.png (server caches CERN's public Vistar captures for 60 s).
   Honours prefers-reduced-motion; every control is a real button/select/range, so it works by keyboard. */
(function(){"use strict";
var D=document,H=D.documentElement;H.classList.add("cx-js");
var RM=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var DATA={};try{DATA=JSON.parse(D.getElementById("cx-data").textContent)}catch(e){}
function $(s,r){return (r||D).querySelector(s)}function $$(s,r){return Array.prototype.slice.call((r||D).querySelectorAll(s))}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function srcLinks(keys){return (keys||[]).map(function(k){var s=(DATA.src||{})[k];return s?'<a class="cx-src" href="'+esc(s.u)+'" target="_blank" rel="noopener">'+esc(s.t)+'</a>':""}).filter(Boolean).join(" · ")}
function etTime(iso){try{return new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}catch(e){return iso||""}}
function ago(iso){if(!iso)return null;var s=Math.max(0,Math.round((Date.now()-new Date(iso).getTime())/1000));if(s<90)return s+" s ago";var m=Math.round(s/60);if(m<90)return m+" min ago";var h=Math.round(m/60);return h<48?h+" h ago":Math.round(h/24)+" d ago"}
function onNear(el,fn,margin){if(!el)return;if(!("IntersectionObserver" in window)){fn();return}var io=new IntersectionObserver(function(es){if(es.some(function(x){return x.isIntersecting})){io.disconnect();fn()}},{rootMargin:margin||"300px"});io.observe(el)}

/* ---------- hero particle tracks (illustration) ---------- */
(function(){var cv=$("#cx-tracks");if(!cv||!cv.getContext)return;var ctx=cv.getContext("2d"),W=0,Hh=0,dpr=1,tracks=[],run=false,last=0,spawnT=0,vis=true;
 function size(){var r=cv.getBoundingClientRect();dpr=Math.min(2,window.devicePixelRatio||1);W=r.width;Hh=r.height;cv.width=Math.round(W*dpr);cv.height=Math.round(Hh*dpr);ctx.setTransform(dpr,0,0,dpr,0,0)}
 function burst(){var vx=W*(.62+Math.random()*.25),vy=Hh*(.3+Math.random()*.4),n=10+Math.floor(Math.random()*10);
  for(var i=0;i<n;i++){var pt=.4+Math.random()*Math.random()*12;tracks.push({x:vx,y:vy,a:Math.random()*6.283,k:(Math.random()<.5?-1:1)*.9/(pt*40),len:0,max:60+Math.min(420,pt*70),c:Math.random()<.5?"34,211,238":"232,121,249",life:1})}}
 function draw(full){ctx.clearRect(0,0,W,Hh);ctx.lineWidth=1.3;
  for(var i=0;i<tracks.length;i++){var t=tracks[i],x=t.x,y=t.y,a=t.a,L=full?t.max:t.len;ctx.beginPath();ctx.moveTo(x,y);
   for(var s=0;s<L;s+=4){a+=t.k*4*40/10;x+=Math.cos(a)*4;y+=Math.sin(a)*4;ctx.lineTo(x,y)}
   ctx.strokeStyle="rgba("+t.c+","+(.75*t.life).toFixed(3)+")";ctx.stroke()}}
 function frame(ts){if(!run)return;requestAnimationFrame(frame);if(ts-last<33)return;var dt=last?ts-last:33;last=ts;spawnT-=dt;if(spawnT<=0){burst();spawnT=2600}
  for(var i=tracks.length-1;i>=0;i--){var t=tracks[i];if(t.len<t.max)t.len+=dt*.35;else{t.life-=dt/1800;if(t.life<=0)tracks.splice(i,1)}}draw(false)}
 function start(){if(run||RM||!vis||D.hidden)return;run=true;last=0;requestAnimationFrame(frame)}function stop(){run=false}
 size();window.addEventListener("resize",function(){size();if(RM)draw(true)});
 if(RM){burst();burst();draw(true);return}
 if("IntersectionObserver" in window)new IntersectionObserver(function(es){vis=es[0].isIntersecting;vis?start():stop()}).observe(cv);
 D.addEventListener("visibilitychange",function(){D.hidden?stop():start()});start()})();

/* ---------- accelerator chain diagram ---------- */
(function(){var panel=$("#cx-chain-panel");if(!panel)return;var st={},ex={};(DATA.stages||[]).forEach(function(s){st[s.id]=s});(DATA.expts||[]).forEach(function(e){ex[e.id]=e});
 function show(k,g){$$(".cx-chain-svg .cx-hit").forEach(function(x){x.classList.toggle("sel",x===g);x.setAttribute("aria-pressed",x===g?"true":"false")});var h;
  if(st[k]){var s=st[k];h='<p class="cx-mono cx-dim">MACHINE · '+esc(s.energy)+'</p><h3>'+esc(s.name)+'</h3><p>'+esc(s.what)+'</p><p class="cx-dim">'+esc(s.fact)+'</p><p class="cx-cite">'+srcLinks(s.src)+'</p>'}
  else if(ex[k]){var e=ex[k];h='<p class="cx-mono cx-dim">EXPERIMENT · '+esc(e.pt)+'</p><h3>'+esc(e.name)+'</h3><p>'+esc(e.focus)+'</p><ul class="cx-ul"><li>'+esc(e.place)+'</li><li>'+esc(e.size)+'</li><li>'+esc(e.lead)+'</li></ul><p><a href="#exp-'+esc(e.id)+'">More on '+esc(e.name)+'</a></p><p class="cx-cite">'+srcLinks(e.src)+'</p>'}
  if(h)panel.innerHTML=h}
 $$(".cx-chain-svg .cx-hit").forEach(function(g){g.setAttribute("aria-pressed","false");g.addEventListener("click",function(){show(g.getAttribute("data-k"),g)});
  g.addEventListener("keydown",function(ev){if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();show(g.getAttribute("data-k"),g)}})})})();

/* ---------- collision simulator (illustration) ---------- */
(function(){var cv=$("#cx-cv");if(!cv||!cv.getContext)return;var ctx=cv.getContext("2d"),N=720,C=N/2,PX=44,go=$("#cx-go"),selE=$("#cx-e"),selP=$("#cx-p"),lbl=$("#cx-lbl"),out=$("#cx-read"),anim=0,ev=null;
 /* simplified CMS-like layers in metres (end-on view) */
 var L={trk:1.15,ecal0:1.29,ecal1:1.75,hcal0:1.8,hcal1:2.9,sol0:2.95,sol1:3.25,mu0:3.9,mu1:7.4};
 var B_IN=3.8,B_OUT=-1.8;
 function rnd(a,b){return a+Math.random()*(b-a)}function sgn(){return Math.random()<.5?-1:1}
 function layers(){ctx.fillStyle="#03060a";ctx.fillRect(0,0,N,N);
  function ring(r0,r1,col){ctx.beginPath();ctx.arc(C,C,r1*PX,0,6.2832);ctx.arc(C,C,r0*PX,0,6.2832,true);ctx.fillStyle=col;ctx.fill()}
  for(var k=0;k<4;k++)ring(L.mu0+k*.9,L.mu0+k*.9+.45,"rgba(232,121,249,.10)");
  ring(L.sol0,L.sol1,"rgba(160,175,190,.20)");ring(L.hcal0,L.hcal1,"rgba(255,194,26,.08)");ring(L.ecal0,L.ecal1,"rgba(52,211,153,.10)");ring(0,L.trk,"rgba(34,211,238,.05)");
  ctx.strokeStyle="rgba(34,211,238,.25)";ctx.lineWidth=1;for(var r=.25;r<=L.trk;r+=.22){ctx.beginPath();ctx.arc(C,C,r*PX,0,6.2832);ctx.stroke()}
  ctx.beginPath();ctx.arc(C,C,3,0,6.2832);ctx.fillStyle="#fff";ctx.fill();
  if(lbl&&lbl.checked){var fs=Math.round(Math.max(15,11*N/(cv.clientWidth||N)));ctx.font="600 "+fs+"px ui-monospace,Menlo,Consolas,monospace";ctx.textAlign="left";
   [["TRACKER",L.trk*.5,"#7ff3ff",-2.6],["ECAL",(L.ecal0+L.ecal1)/2,"#6ee7b7",-1.95],["HCAL",(L.hcal0+L.hcal1)/2,"#ffd76a",-1.2],["SOLENOID",(L.sol0+L.sol1)/2,"#c8d3dd",-0.55],["MUON CHAMBERS",(L.mu0+L.mu1)/2+.3,"#f5b6ff",-2.4]].forEach(function(a){
    var ang=a[3],x=C+Math.cos(ang)*a[1]*PX,y=C+Math.sin(ang)*a[1]*PX;ctx.fillStyle="rgba(0,0,0,.6)";var w=ctx.measureText(a[0]).width;ctx.fillRect(x-4,y-fs,w+8,fs*1.35);ctx.fillStyle=a[2];ctx.fillText(a[0],x,y)})}}
 /* propagate a charged/neutral particle: r = pT / (0.3 B) metres */
 function path(p){var pts=[[0,0]],x=0,y=0,a=p.phi,ds=.02,stop=p.stop,s=0;
  while(s<14){var r=Math.hypot(x,y);if(r>=stop)break;var B=r<L.sol0?B_IN:(r>=L.mu0?B_OUT:(r<L.sol1?B_IN*.5:B_OUT*.5));
   if(p.q){a+=p.q*.3*B/p.pt*ds}x+=Math.cos(a)*ds;y+=Math.sin(a)*ds;s+=ds;pts.push([x,y])}
  p.pts=pts;p.end=[x,y];return p}
 function particle(type,pt,phi,q){var stop={mu:L.mu1,e:(L.ecal0+L.ecal1)/2,g:(L.ecal0+L.ecal1)/2,h:rnd(L.hcal0+.2,L.hcal1-.1),nu:0}[type];return path({type:type,pt:pt,phi:phi,q:q||0,stop:stop})}
 function make(proc,E){var ps=[],phi=rnd(0,6.283),soft=Math.round(6+E*1.3),i;
  for(i=0;i<soft;i++)ps.push(particle("h",rnd(.3,2.2),rnd(0,6.283),sgn()));
  var f=Math.sqrt(E/13.6);
  if(proc==="jets"){[phi,phi+Math.PI+rnd(-.2,.2)].forEach(function(ax){var n=6+Math.round(rnd(2,6)*f);for(var j=0;j<n;j++){var t=Math.random()<.3?"g":"h";ps.push(particle(t,rnd(2,30)*f,ax+rnd(-.22,.22),t==="h"?sgn():0))}})}
  if(proc==="zmm"){ps.push(particle("mu",rnd(35,48),phi,1));ps.push(particle("mu",rnd(35,48),phi+Math.PI+rnd(-.3,.3),-1))}
  if(proc==="hgg"){ps.push(particle("g",rnd(50,70),phi,0));ps.push(particle("g",rnd(45,65),phi+Math.PI+rnd(-.35,.35),0))}
  if(proc==="h4m"){var q=[1,1,-1,-1];for(i=0;i<4;i++)ps.push(particle("mu",rnd(12,40),phi+i*1.5+rnd(-.4,.4),q[i]))}
  if(proc==="wen"){ps.push(particle("e",rnd(32,45),phi,sgn()));ps.push({type:"nu",pt:rnd(30,45),phi:phi+Math.PI+rnd(-.3,.3),pts:[[0,0]],q:0})}
  return ps}
 var COL={h:"rgba(255,215,106,.85)",mu:"#ff5fd2",e:"#6ee7b7",g:"#7ff3ff",nu:"#ffffff"};
 function render(frac){layers();if(!ev)return;ev.forEach(function(p){
  if(p.type==="nu"){if(frac<.6)return;var len=Math.min(L.mu1,1.2+p.pt/12)*PX;ctx.setLineDash([10,8]);ctx.strokeStyle="rgba(255,255,255,.9)";ctx.lineWidth=2.5;ctx.beginPath();ctx.moveTo(C,C);var ex2=C+Math.cos(p.phi)*len,ey2=C+Math.sin(p.phi)*len;ctx.lineTo(ex2,ey2);ctx.stroke();ctx.setLineDash([]);
   var fs2=Math.round(Math.max(14,11*N/(cv.clientWidth||N)));ctx.font="600 "+fs2+"px ui-monospace,Menlo,monospace";ctx.fillStyle="#fff";var tw=ctx.measureText("missing energy").width,tx=Math.cos(p.phi)<0?ex2-6-tw:ex2+6;tx=Math.max(6,Math.min(N-tw-6,tx));var ty=Math.max(fs2+4,Math.min(N-8,ey2+(Math.sin(p.phi)<0?-8:fs2)));ctx.fillText("missing energy",tx,ty);return}
  var n=Math.max(2,Math.floor(p.pts.length*frac));ctx.beginPath();ctx.moveTo(C,C);
  if(p.type==="g")ctx.setLineDash([3,6]);
  for(var i=1;i<n;i++)ctx.lineTo(C+p.pts[i][0]*PX,C+p.pts[i][1]*PX);
  ctx.strokeStyle=COL[p.type];ctx.lineWidth=p.type==="mu"?3:(p.pt>5?2:1.2);ctx.stroke();ctx.setLineDash([]);
  if(frac>=1&&p.type!=="mu"&&Math.hypot(p.end[0],p.end[1])>=L.ecal0){var e=p.end,a=Math.atan2(e[1],e[0]),w=Math.min(36,4+p.pt*.9);ctx.save();ctx.translate(C+e[0]*PX,C+e[1]*PX);ctx.rotate(a);ctx.fillStyle=p.type==="h"?"rgba(255,194,26,.75)":"rgba(52,211,153,.85)";ctx.fillRect(-3,-w/6-2,8+w*.5,w/3+4);ctx.restore()}
  if(frac>=1&&p.type==="mu"){var m=p.end;ctx.fillStyle="#ff5fd2";ctx.beginPath();ctx.arc(C+m[0]*PX,C+m[1]*PX,5,0,6.283);ctx.fill()}})}
 var NAMES={jets:"Two jets",zmm:"Z boson to two muons",hgg:"Higgs boson to two photons",h4m:"Higgs boson to four muons",wen:"W boson to electron plus neutrino"};
 var WHY={jets:"Quarks or gluons knocked out of the protons turn into sprays of hadrons. This is by far the most common kind of hard collision.",
  zmm:"Two opposite-charge muons curve opposite ways in the tracker, then bend back the other way in the return yoke and reach the outer chambers.",
  hgg:"Photons carry no charge, so they leave no track (dotted lines here) and deposit their energy in the electromagnetic calorimeter.",
  h4m:"Two Z bosons each give a pair of opposite-charge muons. This clean signature was one of the two main channels in the 2012 Higgs discovery.",
  wen:"The electron stops in the electromagnetic calorimeter. The neutrino escapes unseen; physicists infer it from the momentum that is missing when everything else is added up."};
 function readout(proc,E){var hard=ev.filter(function(p){return p.type!=="h"||p.pt>2}),mu=ev.filter(function(p){return p.type==="mu"}),g=ev.filter(function(p){return p.type==="g"&&p.pt>20});
  var h='<p><span class="k">EVENT</span> '+esc(NAMES[proc])+' · '+esc(E)+' TeV</p><p><span class="k">TRACKS</span> '+ev.filter(function(p){return p.q}).length+' charged · <span class="m">MUONS</span> '+mu.length+(g.length?' · <span class="y">PHOTONS</span> '+g.length:'')+'</p>';
  if(mu.length)h+='<p>'+mu.map(function(p){return '<span class="m">μ'+(p.q>0?"+":"−")+'</span> pT '+p.pt.toFixed(0)+' GeV, radius '+(p.pt/(.3*B_IN)).toFixed(0)+' m'}).join("<br>")+'</p>';
  h+='<p class="cx-dim">'+esc(WHY[proc])+'</p><p class="cx-dim">Illustration · simulated numbers, not real data</p>';out.innerHTML=h}
 function fire(){cancelAnimationFrame(anim);var E=parseFloat(selE.value),proc=selP.value;ev=make(proc,E);readout(proc,E);
  if(RM){render(1);return}var t0=performance.now();(function step(t){var f=Math.min(1,(t-t0)/900);render(f);if(f<1)anim=requestAnimationFrame(step)})(t0)}
 go.addEventListener("click",fire);lbl&&lbl.addEventListener("change",function(){render(1)});selP.addEventListener("change",fire);selE.addEventListener("change",fire);
 layers();onNear(cv,function(){fire()},"0px")})();

/* ---------- timeline slider ---------- */
(function(){var r=$("#cx-tl-r"),tr=$("#cx-tl-track"),yr=$("#cx-tl-yr");if(!r||!tr)return;var items=$$(".cx-tl-i",tr),lock=0;
 function mark(i){items.forEach(function(x,j){x.classList.toggle("on",j===i)});var y=items[i].getAttribute("data-year");yr.textContent=y;r.value=i;r.setAttribute("aria-valuetext",y+": "+(items[i].querySelector("h3")||{}).textContent)}
 function go(i,smooth){i=Math.max(0,Math.min(items.length-1,i));mark(i);lock=Date.now();tr.scrollTo({left:items[i].offsetLeft-tr.offsetLeft,behavior:(smooth&&!RM)?"smooth":"auto"})}
 r.addEventListener("input",function(){go(+r.value,true)});
 $("#cx-tl-prev").addEventListener("click",function(){go(+r.value-1,true)});$("#cx-tl-next").addEventListener("click",function(){go(+r.value+1,true)});
 tr.addEventListener("keydown",function(e){if(e.key==="ArrowRight"){e.preventDefault();go(+r.value+1,true)}if(e.key==="ArrowLeft"){e.preventDefault();go(+r.value-1,true)}});
 var t;tr.addEventListener("scroll",function(){clearTimeout(t);t=setTimeout(function(){if(Date.now()-lock<700)return;var x=tr.scrollLeft,b=0,bd=1e9;items.forEach(function(it,j){var d=Math.abs(it.offsetLeft-tr.offsetLeft-x);if(d<bd){bd=d;b=j}});mark(b)},120)},{passive:true});
 mark(0)})();

/* ---------- map + scale overlay ---------- */
(function(){var el=$("#cx-map");if(!el)return;
 var LIB=["dist/maplibre-gl.js","sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp"],CSS=["dist/maplibre-gl.css","sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK"],
  CDN=["https://unpkg.com/maplibre-gl@5.24.0/","https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/"],STYLE_D="https://tiles.openfreemap.org/styles/dark",STYLE_L="https://tiles.openfreemap.org/styles/positron";
 var CEN=[6.06632,46.27205],ring=null,map=null,cur={lon:CEN[0],lat:CEN[1],real:true,name:"Geneva"},sel=$("#cx-city"),note=$("#cx-geo-note");
 function light(){return H.getAttribute("data-theme")==="light"}
 function tag(n,a){return new Promise(function(ok,no){var e=D.createElement(n);for(var k in a)e.setAttribute(k,a[k]);e.crossOrigin="anonymous";e.onload=ok;e.onerror=no;D.head.appendChild(e)})}
 function lib(){if(window.maplibregl)return Promise.resolve(true);return (async function(){for(var i=0;i<CDN.length;i++){try{await tag("link",{rel:"stylesheet",href:CDN[i]+CSS[0],integrity:CSS[1]}).catch(function(){});await tag("script",{src:CDN[i]+LIB[0],integrity:LIB[1]});if(window.maplibregl)return true}catch(e){}}return false})()}
 function moved(lon,lat){var k0=111320*Math.cos(CEN[1]*Math.PI/180),k1=111320*Math.cos(lat*Math.PI/180);return ring.map(function(p){return [lon+(p[0]-CEN[0])*k0/k1,lat+(p[1]-CEN[1])]})}
 function gj(){var c=moved(cur.lon,cur.lat);c.push(c[0]);return {type:"FeatureCollection",features:[{type:"Feature",properties:{},geometry:{type:"LineString",coordinates:c}}]}}
 function ptsGJ(){return {type:"FeatureCollection",features:cur.real?(DATA.pts||[]).map(function(p){return {type:"Feature",properties:{label:p.label,exp:p.exp||""},geometry:{type:"Point",coordinates:[p.lon,p.lat]}}}):[]}}
 function layers(){if(!map||!ring)return;if(map.getSource("ring")){map.getSource("ring").setData(gj());map.getSource("pts").setData(ptsGJ());return}
  map.addSource("ring",{type:"geojson",data:gj()});map.addSource("pts",{type:"geojson",data:ptsGJ()});
  map.addLayer({id:"ring-glow",type:"line",source:"ring",paint:{"line-color":"#22d3ee","line-width":12,"line-opacity":.25,"line-blur":6}});
  map.addLayer({id:"ring",type:"line",source:"ring",paint:{"line-color":light()?"#0e7490":"#22d3ee","line-width":3.5}});
  map.addLayer({id:"pts",type:"circle",source:"pts",paint:{"circle-radius":["case",["!=",["get","exp"],""],8,5],"circle-color":["case",["!=",["get","exp"],""],"#e879f9","#9fb0bf"],"circle-stroke-color":"#fff","circle-stroke-width":1.5}});
  map.addLayer({id:"pts-l",type:"symbol",source:"pts",filter:["!=",["get","exp"],""],layout:{"text-field":["get","label"],"text-size":12,"text-offset":[0,1.3],"text-anchor":"top","text-font":["Noto Sans Regular"]},paint:{"text-color":light()?"#0d141b":"#e8eef4","text-halo-color":light()?"#fff":"#000","text-halo-width":1.4}})}
 function fit(){if(!map||!ring)return;var c=moved(cur.lon,cur.lat),b=new maplibregl.LngLatBounds(c[0],c[0]);c.forEach(function(p){b.extend(p)});map.fitBounds(b,{padding:40,duration:RM?0:900})}
 function place(lon,lat,name,real){cur={lon:lon,lat:lat,name:name,real:!!real};layers();fit()}
 function pick(){var k=sel.value,c=(DATA.cities||[]).filter(function(x){return x.k===k})[0];if(!c)return;if(k==="geneva")place(CEN[0],CEN[1],c.n,true);else place(c.lon,c.lat,c.n,false);
  note.textContent=k==="geneva"?"Showing the real ring. Tap a point for its experiment.":"The 26.7 km ring, same size and shape, centred on "+c.n+". Your location is used only in your browser; it is never sent to our server."}
 async function init(){var ok=await lib();try{var r=await fetch("/api/cern/ring.json");ring=await r.json()}catch(e){ring=null}
  if(!ok||!ring||!window.maplibregl){el.innerHTML='<p class="cx-map-ph">The map could not load here. The ring lies about 100 m under the French-Swiss border between Geneva airport and the Jura mountains; see the satellite image below.</p>';return}
  el.innerHTML="";var c0=(DATA.cities||[]).filter(function(x){return x.k===sel.value})[0]||{lon:CEN[0],lat:CEN[1],k:"geneva"};
  map=new maplibregl.Map({container:el,style:light()?STYLE_L:STYLE_D,center:[c0.lon,c0.lat],zoom:9.5,attributionControl:{compact:true},cooperativeGestures:true,dragRotate:false,pitchWithRotate:false,maxZoom:15});
  map.touchZoomRotate.disableRotation();map.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
  map.on("style.load",function(){layers()});map.on("load",function(){pick()});
  var pop=new maplibregl.Popup({closeButton:true,offset:10});
  map.on("click","pts",function(e){var f=e.features[0],d=D.createElement("div"),b=D.createElement("b");b.textContent=f.properties.label;d.appendChild(b);
   var ex=(DATA.expts||[]).filter(function(x){return x.id===f.properties.exp})[0];if(ex){var p=D.createElement("div");p.textContent=ex.focus;d.appendChild(p)}pop.setLngLat(f.geometry.coordinates).setDOMContent(d).addTo(map)});
  map.on("mouseenter","pts",function(){map.getCanvas().style.cursor="pointer"});map.on("mouseleave","pts",function(){map.getCanvas().style.cursor=""});
  new MutationObserver(function(){map.setStyle(light()?STYLE_L:STYLE_D)}).observe(H,{attributes:true,attributeFilter:["data-theme"]})}
 sel.addEventListener("change",function(){if(map)pick()});
 var geo=$("#cx-geo");if(geo){if(!navigator.geolocation)geo.hidden=true;else geo.addEventListener("click",function(){note.textContent="Asking your browser for your location...";
  navigator.geolocation.getCurrentPosition(function(p){var la=p.coords.latitude,lo=p.coords.longitude;if(map)place(lo,la,"your location",false);note.textContent="The ring, centred on your location. Your position stayed in your browser; it was not sent to our server."},
   function(){note.textContent="Location not available. Pick a city instead."},{maximumAge:600000,timeout:10000})})}
 onNear(el,init,"400px")})();

/* ---------- funding chart ---------- */
(function(){var box=$(".cx-fund");if(!box)return;var det=$(".cx-fund-detail",box),F=DATA.fund||[],A=DATA.assoc||[];
 function mil(v){return (v/1e6).toLocaleString("en-US",{minimumFractionDigits:1,maximumFractionDigits:1})}
 function show(b){$$(".cx-bar",box).forEach(function(x){x.classList.toggle("sel",x===b);x.setAttribute("aria-pressed",x===b?"true":"false")});var h;
  if(b.hasAttribute("data-i")){var f=F[+b.getAttribute("data-i")];h='<p class="cx-mono cx-dim">MEMBER STATE · 2026</p><p class="cx-fd-big">'+esc(f.c)+'</p><p>'+f.pct.toFixed(2)+'% of Member State contributions: <b>CHF '+mil(f.chf)+' million</b> in 2026.'+(f.since?' Member since '+esc(f.since)+'.':'')+'</p>'}
  else{var a=A[+b.getAttribute("data-a")];h='<p class="cx-mono cx-dim">ASSOCIATE MEMBER · 2026</p><p class="cx-fd-big">'+esc(a.c)+'</p><p><b>CHF '+mil(a.chf)+' million</b> in 2026.'+(a.since?' Associate Member since '+esc(a.since)+'.':'')+'</p>'}
  det.innerHTML=h}
 $$(".cx-bar",box).forEach(function(b){b.setAttribute("aria-pressed","false");b.addEventListener("click",function(){show(b)})});
 $$(".cx-segb",box).forEach(function(s){s.addEventListener("click",function(){var v=s.getAttribute("data-v");box.setAttribute("data-view",v);$$(".cx-segb",box).forEach(function(x){x.setAttribute("aria-pressed",x===s?"true":"false")});var first=$(v==="m"?".cx-bars-m .cx-bar":".cx-bars-a .cx-bar",box);if(first)show(first)})})})();

/* ---------- myth flip cards ---------- */
$$(".cx-flipb").forEach(function(b){var art=b.closest(".cx-myth"),f=$(".cx-flip",art),claim=$(".cx-face-claim",f),phys=$(".cx-face-phys",f);
 function set(side){f.setAttribute("data-side",side);var p=side==="phys";b.setAttribute("aria-expanded",p?"true":"false");b.textContent=p?"Show the claim again":"Show what physics says";phys.setAttribute("aria-hidden",p?"false":"true");claim.setAttribute("aria-hidden",p?"true":"false")}
 set("claim");b.addEventListener("click",function(){set(f.getAttribute("data-side")==="phys"?"claim":"phys")})});

/* ---------- quiz ---------- */
(function(){var qs=$$(".cx-q"),score=$("#cx-q-score"),got=0,done=0;
 qs.forEach(function(q){var a=+q.getAttribute("data-a"),res=$(".cx-q-r",q),opts=$$(".cx-qo",q);opts.forEach(function(o){o.setAttribute("aria-pressed","false");o.addEventListener("click",function(){if(q.getAttribute("data-done"))return;q.setAttribute("data-done","1");done++;
  var ok=+o.getAttribute("data-o")===a;if(ok)got++;o.setAttribute("aria-pressed","true");o.classList.add(ok?"ok":"no");opts[a].classList.add("right");
  res.hidden=false;res.insertAdjacentHTML("afterbegin","<b>"+(ok?"Correct.":"Not quite: the answer is "+esc(opts[a].textContent)+".")+"</b> ");
  score.textContent="SCORE "+got+" / "+qs.length+(done===qs.length?" · DONE":"")})})})})();

/* ---------- live status ---------- */
(function(){var box=$("#cx-live");if(!box)return;var timer=null,inView=false;
 function setImg(card,id){var wrap=$(".cx-live-img",card),img=$("img",wrap);img.onerror=function(){wrap.classList.add("fail");wrap.setAttribute("data-fail","Display unavailable right now. CERN may have paused this capture; open CERN's live displays below.");img.style.visibility="hidden"};
  img.onload=function(){wrap.classList.remove("fail");img.style.visibility=""};img.src="/api/cern/live/"+id+".png?t="+Math.floor(Date.now()/60000)}
 function refreshImgs(){$$(".cx-live-card",box).forEach(function(c){setImg(c,c.getAttribute("data-id"))})}
 function poll(){fetch("/api/cern/status",{cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
  var s=d.state||{};if(s.lhc)$("#cx-st-lhc").textContent=s.lhc;if(s.lhc_note)$("#cx-st-lhcn").textContent=s.lhc_note;if(s.inj)$("#cx-st-inj").textContent=s.inj;if(s.inj_note)$("#cx-st-injn").textContent=s.inj_note;
  (d.displays||[]).forEach(function(x){var a=$('[data-age="'+x.id+'"]',box);if(a)a.textContent=x.updated?"CERN capture "+ago(x.updated)+" · "+etTime(x.updated):(x.ok?"capture time not reported":"waiting for capture");
   if(x.id==="lhc1")$("#cx-st-p1").textContent=x.updated?ago(x.updated).toUpperCase():"UNAVAILABLE"});
  var gen=$("#cx-live-gen");if(!gen){gen=D.createElement("p");gen.id="cx-live-gen";gen.className="cx-mono cx-dim";$(".cx-readout",box).insertAdjacentElement("afterend",gen)}gen.textContent="LAST CHECKED "+etTime(d.generated).toUpperCase()})
  .catch(function(){$("#cx-st-p1").textContent="UNAVAILABLE";$$("[data-age]",box).forEach(function(a){if(a.textContent==="loading")a.textContent="status unavailable; image may be stale"})})}
 function tick(){if(D.hidden||!inView)return;refreshImgs();setTimeout(poll,2500)}
 function start(){refreshImgs();poll();setTimeout(poll,4000);if(!timer)timer=setInterval(tick,60000)}
 if("IntersectionObserver" in window)new IntersectionObserver(function(es){inView=es[0].isIntersecting},{rootMargin:"200px"}).observe(box);else inView=true;
 onNear(box,start,"600px");D.addEventListener("visibilitychange",function(){if(!D.hidden&&timer)tick()});
 /* Open Data counts */
 onNear($("#cx-od"),function(){var od=$("#cx-od");fetch("/api/cern/opendata").then(function(r){return r.json()}).then(function(d){if(!d.ok)throw 0;
  var ex=(d.experiments||[]).slice(0,4).map(function(e){return '<div><b>'+Number(e[1]).toLocaleString("en-US")+'</b><span class="cx-dim">'+esc(e[0])+' records</span></div>'}).join("");
  od.innerHTML='<h3>CERN Open Data, live count</h3><p><b class="cx-mono">'+Number(d.total).toLocaleString("en-US")+'</b> public records (datasets, software, documentation) on the CERN Open Data portal.</p><div class="cx-od-grid">'+ex+'</div><p class="cx-cite">Counted from the portal API '+(d.fetched?esc(etTime(d.fetched)):"")+' · refreshed every 6 hours · <a href="https://opendata.cern.ch/" target="_blank" rel="noopener">opendata.cern.ch</a> (metadata CC0)</p>'})
  .catch(function(){od.innerHTML='<h3>CERN Open Data</h3><p>The live count is unavailable right now. Browse the records at <a href="https://opendata.cern.ch/" target="_blank" rel="noopener">opendata.cern.ch</a>.</p>'})},"600px")})();

/* ---------- beam chip + table of contents ---------- */
(function(){var chip=$("#cx-beamchip"),e=$("#cx-beamchip-e"),s=$("#cx-beamchip-s"),stages=$$(".cx-stage");if(!chip||!("IntersectionObserver" in window))return;
 var hero=$("#top");new IntersectionObserver(function(es){chip.classList.toggle("on",!es[0].isIntersecting)}).observe(hero);

 function upd(){var cur=null;stages.forEach(function(st){if(st.getBoundingClientRect().top<window.innerHeight*.5)cur=st});
  if(cur){e.textContent=cur.getAttribute("data-energy");s.textContent=$(".cx-stage-tag b",cur).textContent}else{e.textContent="0 eV";s.textContent="ion source"}}var raf=0;window.addEventListener("scroll",function(){if(!raf)raf=requestAnimationFrame(function(){raf=0;upd()})},{passive:true});upd();
 var links=$$(".cx-toc a"),secs=links.map(function(a){return D.getElementById(a.getAttribute("href").slice(1))}).filter(Boolean);
 var so=new IntersectionObserver(function(){var c=null;secs.forEach(function(x){if(x.getBoundingClientRect().top<140)c=x});links.forEach(function(a){var on=c&&a.getAttribute("href")==="#"+c.id;a.setAttribute("aria-current",on?"true":"false");if(on&&a.scrollIntoView&&a.parentNode.scrollWidth>a.parentNode.clientWidth){a.parentNode.scrollLeft=a.offsetLeft-20}})},{rootMargin:"-120px 0px -60% 0px"});secs.forEach(function(x){so.observe(x)})})();
})();
