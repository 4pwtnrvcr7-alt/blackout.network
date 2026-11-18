/* /live overview: gauges, tiles, top signals, dot map, rank spread, alerts per day, categories. Data: /api/live/summary (60 s cache).
   Vacuum-strip loader (Nov 17, 8:20 PM ET): compact canvas under the header vacuums grey particles into a moving intake; only readout is 0–100%. Tied to real fetches, min ~1.2s (0 if reduced-motion), 120s refresh does not retrigger. */
(function(){
var d=document,$=function(id){return d.getElementById(id)},root=$("bntl");if(!root||window.__bnLive)return;window.__bnLive=1;
var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var t0=performance.now(),revealed=!!root.classList.contains("l-ready");
var acqPart=function(){},reveal=function(){},failSoft=function(){};
(function bootAcq(){
 var wrap=$("bntl_acq"),cv=$("bntl_acq_cv"),pctEl=$("bntl_acq_pct");
 if(!wrap||!root.classList.contains("l-loading")||revealed){
  reveal=function(){if(revealed||!root.classList.contains("l-loading"))return;revealed=true;root.classList.remove("l-loading");root.classList.add("l-ready");root.removeAttribute("aria-busy")};
  failSoft=function(){var el=$("bntl_asof");if(el&&/Loading the latest/.test(el.textContent||""))el.innerHTML='<i></i>Signals delayed &middot; <a href="/?intro=1">Watch the intro</a>';reveal()};
  return;
 }
 var MIN=reduce?0:1200, parts={sum:0,land:0,paint:0}, W={sum:62,land:26,paint:12};
 var shown=0, collapsing=false, folded=false, pulse=0, pulseT=0, raf=0, hid=false;
 var ctx=cv&&cv.getContext?cv.getContext("2d",{alpha:true}):null;
 var pool=[], sparks=[], MAX=110, lastT=0, dpr=1, cw=0, ch=0;
 function fmt(n){n=Math.max(0,Math.min(100,n|0));return (n<10?"0":"")+n}
 function setPct(v){var n=Math.max(0,Math.min(100,Math.round(v)));if(pctEl)pctEl.textContent=fmt(n);wrap.setAttribute("aria-label","Loading "+n+" percent")}
 function target(){
  var t=(parts.sum?W.sum:0)+(parts.land?W.land:0)+(parts.paint?W.paint:0);
  var creep=Math.min(32,(performance.now()-t0)/150);
  t=Math.max(t,creep);
  if(parts.sum&&parts.land&&parts.paint&&(performance.now()-t0)>=MIN) return 100;
  return Math.min(t,98);
 }
 function foldAway(){
  if(folded)return;folded=true;revealed=true;
  wrap.classList.add("l-acq-fold");
  wrap.setAttribute("aria-label","Loaded");
  wrap.setAttribute("aria-hidden","true");
  setTimeout(function(){
   root.classList.remove("l-loading");root.classList.add("l-ready");root.removeAttribute("aria-busy");
   if(raf){cancelAnimationFrame(raf);raf=0}
  }, reduce?0:420);
 }
 function beginCollapse(){
  if(collapsing)return;collapsing=true;shown=100;setPct(100);
  pulse=1;pulseT=performance.now();
  setTimeout(foldAway, reduce?0:320);
 }
 acqPart=function(k){if(parts[k]!=null)parts[k]=1};
 reveal=function(){acqPart("paint");if(reduce&&(performance.now()-t0)>=MIN&&parts.sum&&parts.land&&parts.paint)beginCollapse()};
 failSoft=function(){var el=$("bntl_asof");if(el&&/Loading the latest/.test(el.textContent||""))el.innerHTML='<i></i>Signals delayed &middot; <a href="/?intro=1">Watch the intro</a>';parts.sum=parts.land=parts.paint=1;reveal()};
 function resize(){
  if(!cv)return;
  var r=cv.getBoundingClientRect();
  dpr=Math.max(1,Math.min(2,window.devicePixelRatio||1));
  cw=Math.max(1,Math.round(r.width));ch=Math.max(1,Math.round(r.height));
  if(cv.width!==Math.round(cw*dpr)||cv.height!==Math.round(ch*dpr)){cv.width=Math.round(cw*dpr);cv.height=Math.round(ch*dpr)}
 }
 function spawn(prefer){
  if(pool.length>=MAX||collapsing)return;
  var fromL=prefer=== "L" || (prefer!=="R" && Math.random()<.5);
  var p={x:fromL?-8:cw+8, y:4+Math.random()*(ch-8), vx:(fromL?1:-1)*(0.35+Math.random()*0.55), vy:(Math.random()-.5)*0.35,
   kind:Math.random()<.28?1:0, precious:0, life:1, cap:0};
  var r=Math.random();
  if(r<.0018)p.precious=2; else if(r<.028)p.precious=1;
  pool.push(p);
 }
 function tick(now){
  raf=0;if(folded||hid)return;
  var dt=Math.min(32, now-(lastT||now))/16.666;lastT=now;
  var want=target();
  var k=collapsing?1:(want>=100?.22:.09);
  shown+=(want-shown)*k*dt;
  if(want>=100&&shown>=99.2)shown=100;
  setPct(shown);
  if(!collapsing&&shown>=100&&parts.sum&&parts.land&&parts.paint)beginCollapse();
  if(!ctx){if(!folded)raf=requestAnimationFrame(tick);return}
  resize();
  var pad=10, barY=ch*0.52, barL=pad, barR=cw-pad, span=Math.max(1,barR-barL);
  var ix=barL+span*(shown/100);
  if(!reduce){
   var need=collapsing?0:(shown<30?3:2);
   for(var s=0;s<need;s++)spawn();
   if(Math.random()<.35)spawn();
  }
  var i,p,dx,dy,dist,pull,nx,ny;
  for(i=pool.length-1;i>=0;i--){
   p=pool[i];
   dx=ix-p.x; dy=barY-p.y; dist=Math.sqrt(dx*dx+dy*dy)||1;
   pull=(collapsing?0.22:0.085)+0.55/(dist+8);
   p.vx=p.vx*0.92+dx/dist*pull*dt*6.2;
   p.vy=p.vy*0.90+dy/dist*pull*dt*6.2;
   var spd=Math.sqrt(p.vx*p.vx+p.vy*p.vy);
   if(spd>5.4){p.vx*=5.4/spd;p.vy*=5.4/spd}
   p.x+=p.vx*dt*1.15; p.y+=p.vy*dt*1.15;
   if(dist<5.2||(collapsing&&dist<9)){
    if(p.precious&&!p.cap){sparks.push({x:ix,y:barY,t:now,c:p.precious});pulse=Math.max(pulse,p.precious===2?1:0.55);pulseT=now}
    pool.splice(i,1);
   }
  }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,cw,ch);
  ctx.strokeStyle="rgba(240,240,250,.18)";ctx.lineWidth=1;ctx.lineCap="round";
  ctx.beginPath();ctx.moveTo(barL,barY);ctx.lineTo(barR,barY);ctx.stroke();
  if(shown>0.2){
   ctx.strokeStyle="rgba(240,240,250,.82)";ctx.lineWidth=1.25;
   ctx.beginPath();ctx.moveTo(barL,barY);ctx.lineTo(ix,barY);ctx.stroke();
  }
  for(i=0;i<pool.length;i++){
   p=pool[i];
   if(p.precious===2){ctx.fillStyle="#FF4D4F";ctx.strokeStyle="#FF4D4F"}
   else if(p.precious===1){ctx.fillStyle="#F0F0FA";ctx.strokeStyle="rgba(240,240,250,.9)"}
   else {ctx.fillStyle="rgba(201,205,211,.55)";ctx.strokeStyle="rgba(201,205,211,.4)"}
   if(p.kind){ctx.lineWidth=0.7;ctx.beginPath();ctx.moveTo(p.x-2.2,p.y);ctx.lineTo(p.x+2.2,p.y);ctx.stroke()}
   else {ctx.beginPath();ctx.arc(p.x,p.y,p.precious?1.35:0.9,0,6.2832);ctx.fill()}
  }
  for(i=sparks.length-1;i>=0;i--){
   var k2=(now-sparks[i].t)/280;if(k2>=1){sparks.splice(i,1);continue}
   var rad=2+k2*11, a=1-k2;
   ctx.strokeStyle=sparks[i].c===2?("rgba(255,77,79,"+a+")"):("rgba(240,240,250,"+a+")");
   ctx.lineWidth=1;
   ctx.beginPath();ctx.arc(sparks[i].x,sparks[i].y,rad,0,6.2832);ctx.stroke();
   ctx.fillStyle=sparks[i].c===2?("rgba(255,77,79,"+(a*.9)+")"):("rgba(240,240,250,"+(a*.9)+")");
   ctx.beginPath();ctx.arc(sparks[i].x,sparks[i].y,1.4*(1-k2),0,6.2832);ctx.fill();
  }
  var age=pulseT?now-pulseT:9999, pu=pulse>0&&age<420? (1-age/420)*pulse : 0;
  var ir=collapsing? Math.max(1.1, 4.6*(1-Math.min(1,(pulseT?(now-pulseT):0)/300))) : 3.1+pu*3.2;
  if(collapsing&&age>160){ir=1.15+pu*6}
  ctx.fillStyle=pu>0.7?"#FF4D4F":"#F0F0FA";
  ctx.globalAlpha=collapsing&&age>260?Math.max(0,1-(age-260)/120):1;
  ctx.beginPath();ctx.arc(ix,barY,ir,0,6.2832);ctx.fill();
  if(!collapsing||age<260){
   ctx.globalAlpha=0.85;
   ctx.strokeStyle="#F0F0FA";ctx.lineWidth=1;
   ctx.beginPath();
   ctx.moveTo(ix-7,barY-4.5);ctx.lineTo(ix-1.2,barY);ctx.lineTo(ix-7,barY+4.5);
   ctx.stroke();
   ctx.beginPath();
   ctx.moveTo(ix+7,barY-4.5);ctx.lineTo(ix+1.2,barY);ctx.lineTo(ix+7,barY+4.5);
   ctx.stroke();
  }
  ctx.globalAlpha=1;
  if(!folded)raf=requestAnimationFrame(tick);
 }
 function onVis(){hid=!!d.hidden;if(!hid&&!folded&&!raf){lastT=0;raf=requestAnimationFrame(tick)}}
 d.addEventListener("visibilitychange",onVis);
 addEventListener("resize",function(){if(!folded)resize()}, {passive:true});
 resize();setPct(0);
 if(!reduce){for(var z=0;z<28;z++)spawn(z%2?'L':'R')}
 raf=requestAnimationFrame(tick);
})();
var band=function(r){return r>=7?"h":r>=4?"e":"c"},col={c:"#6B7076",e:"#C9CDD3",h:"#FF4D4F"},word={c:"Calm",e:"Elevated",h:"High"};
var rname={0:"Noise",1:"Background",2:"Minor",3:"Minor regional",4:"Regional",5:"Significant",6:"Serious",7:"Major",8:"Severe",9:"Critical",10:"Catastrophic"};
var esc=function(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})};
function count(el,to,dec){dec=dec||0;if(!el)return;if(reduce){el.textContent=to.toFixed(dec);return}var t0=performance.now();(function f(t){var p=Math.min(1,(t-t0)/1400),e=1-Math.pow(1-p,3);el.textContent=(to*e).toFixed(dec);if(p<1)requestAnimationFrame(f)})(t0)}
function arc(cx,cy,r,a0,a1){var p=function(a){return [cx+r*Math.cos(a*Math.PI/180),cy+r*Math.sin(a*Math.PI/180)]},s=p(a0),e=p(a1);return "M"+s[0]+" "+s[1]+"A"+r+" "+r+" 0 "+(a1-a0>180?1:0)+" 1 "+e[0]+" "+e[1]}
var FILTER='<filter id="bntl_gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
function gauge(v,top,S){S=S||{};var A0=150,A1=390,cx=200,cy=190,r=150,ang=function(x){return A0+(A1-A0)*x/10},b=band(Math.floor(v));
 var s='<svg viewBox="0 0 400 330" role="img" aria-label="Top stories average rank '+v.toFixed(1)+' of 10, '+word[b]+'"><defs>'+FILTER+'<linearGradient id="bntl_gf" x1="0" x2="1"><stop offset="0" stop-color="#6B7076"/><stop offset=".45" stop-color="#C9CDD3"/><stop offset="1" stop-color="#FF4D4F"/></linearGradient><radialGradient id="bntl_core"><stop offset="0" stop-color="'+col[b]+'" stop-opacity=".22"/><stop offset="1" stop-color="'+col[b]+'" stop-opacity="0"/></radialGradient></defs><circle cx="'+cx+'" cy="'+cy+'" r="118" fill="url(#bntl_core)"/>';
 [[0,3.5,"c"],[3.5,6.5,"e"],[6.5,10,"h"]].forEach(function(z){s+='<path d="'+arc(cx,cy,r,ang(z[0])+1,ang(z[1])-1)+'" stroke="'+col[z[2]]+'" stroke-opacity=".16" stroke-width="18" fill="none" stroke-linecap="round"/>'});
 for(var i=0;i<=10;i++){var a=ang(i)*Math.PI/180,c=Math.cos(a),sn=Math.sin(a);s+='<line x1="'+(cx+(r-24)*c)+'" y1="'+(cy+(r-24)*sn)+'" x2="'+(cx+(r-31)*c)+'" y2="'+(cy+(r-31)*sn)+'" stroke="rgba(240,240,250,.35)" stroke-width="2" stroke-linecap="round"/><text x="'+(cx+(r+26)*c)+'" y="'+(cy+(r+26)*sn+4)+'" text-anchor="middle" font-family="Montserrat" font-weight="600" font-size="12" fill="rgba(240,240,250,.5)">'+i+'</text>'}
 s+='<path id="bntl_arc" d="'+arc(cx,cy,r,A0,ang(10))+'" stroke="url(#bntl_gf)" stroke-width="18" fill="none" stroke-linecap="round" filter="url(#bntl_gl)" pathLength="100" stroke-dasharray="0 100"/>';
 s+='<g id="bntl_dot" style="transform-origin:'+cx+'px '+cy+'px;transform:rotate('+A0+'deg)"><circle cx="'+(cx+r)+'" cy="'+cy+'" r="12" fill="#05060a" stroke="'+col[b]+'" stroke-width="4" filter="url(#bntl_gl)"/></g>';
 s+='<text id="bntl_num" x="'+cx+'" y="'+(cy+6)+'" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="84" fill="#F0F0FA">0.0</text><text x="'+cx+'" y="'+(cy+44)+'" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="17" letter-spacing="4" fill="'+col[b]+'">'+word[b].toUpperCase()+'</text><text x="'+cx+'" y="'+(cy+88)+'" text-anchor="middle" font-family="Inter" font-size="13" fill="rgba(240,240,250,.55)">out of 10</text></svg>';
 $("bntl_g").innerHTML=s;var ar=$("bntl_arc"),dot=$("bntl_dot");
 requestAnimationFrame(function(){if(!reduce){ar.style.transition="stroke-dasharray 1.6s cubic-bezier(.2,.7,.2,1)";dot.style.transition="transform 1.6s cubic-bezier(.2,.7,.2,1)"}
  setTimeout(function(){ar.setAttribute("stroke-dasharray",(v*10)+" 100");dot.style.transform="rotate("+ang(v)+"deg)"},120)});
 count($("bntl_num"),v,1);
 var H=S.hi;$("bntl_gt").innerHTML=H&&H.title?'<span class="l-hk">Highest threat right now</span><a class="l-ht" href="'+esc(H.url)+'"><span class="l-hc" style="--c:'+col[band(H.rank)]+'"><b>'+(H.rank|0)+'</b><small>/10</small></span><span class="l-htt">'+esc(H.title)+'</span></a>':'<span class="l-hk">Highest threat right now</span><span class="l-htt">No active alerts</span>'}
var ICON={"natural disaster":'<path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A3.5 3.5 0 0 1 17 18z"/>',"disease":'<path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z"/>',"war/conflict":'<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',"financial":'<path d="M3 20h18M5 16l4-5 4 3 6-8"/>',"political":'<path d="M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10M2 10l10-6 10 6z"/>',"cyber":'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'};
var CAT={"natural disaster":"Weather & quakes","disease":"Health","war/conflict":"Conflict","financial":"Markets","political":"Politics","cyber":"Cyber"};
function render(S,land,only){var on=function(k){return !only||only===k};LAST=S;stamps(S,only);
 $("bntl_asof").innerHTML="<i></i>Live &middot; last scan "+esc(S.last_scan_et)+' &middot; <a href="/?intro=1">Watch the intro</a>';
if(on("g")){ var top=0;S.top.forEach(function(t){top=Math.max(top,t.rank)});gauge(S.level,S.max_rank||top,S);}
if(on("t")){ ["h","e","c"].forEach(function(k){var n=S.bands[{h:"high",e:"elevated",c:"calm"}[k]]||0;count($("bntl_t"+k),n,0);var m=$("bntl_m"+k);m.innerHTML="<i></i>";setTimeout(function(){m.firstChild.style.width=(S.wire?100*n/S.wire:0)+"%"},150)});
 var p=S.sources_total?S.sources_ok/S.sources_total:0,R=40,C=2*Math.PI*R;
 $("bntl_ring").innerHTML='<svg viewBox="0 0 100 100" role="img" aria-label="'+Math.round(p*100)+' percent of sources online"><circle cx="50" cy="50" r="'+R+'" stroke="rgba(124,196,255,.14)" stroke-width="9" fill="none"/><circle id="bntl_sa" cx="50" cy="50" r="'+R+'" stroke="#7CC4FF" stroke-width="9" fill="none" stroke-linecap="round" stroke-dasharray="0 '+C+'" transform="rotate(-90 50 50)" style="transition:stroke-dasharray 1.6s cubic-bezier(.2,.7,.2,1)"/><text x="50" y="57" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="21" fill="#F0F0FA">'+Math.round(p*100)+'%</text></svg>';
 setTimeout(function(){var a=$("bntl_sa");if(a)a.setAttribute("stroke-dasharray",(C*p)+" "+C)},150);
 $("bntl_src").innerHTML="<b>"+S.sources_ok+" of "+S.sources_total+"</b> feeds";}
if(on("s")){ $("bntl_sigs").innerHTML=S.top.length?S.top.map(function(t){var b=band(t.rank),seg="";for(var i=0;i<10;i++){var bb=band(i+1);seg+='<i style="'+(i<t.rank?"background:"+col[bb]+";box-shadow:0 0 6px "+col[bb]+"66":"")+'"></i>'}
  return '<div class="bnt-card l-sig"><div class="l-top"><span class="l-cat"><svg viewBox="0 0 24 24" aria-hidden="true">'+(ICON[t.cat]||"")+"</svg>"+esc(CAT[t.cat]||t.cat||"Alert")+'</span><span class="l-rk" aria-label="Rank '+t.rank+' of 10"><span class="l-segs" aria-hidden="true">'+seg+'</span><b style="color:'+col[b]+'">'+t.rank+"</b><small>/10</small></span></div><h4><a class='l-sl' href='"+esc(t.url)+"'>"+esc(t.title)+'</a></h4><button type="button" class="l-xp" aria-expanded="false" hidden>More</button><div class="l-meta"><span class="l-pill '+b+'">'+esc(rname[t.rank]||word[b])+"</span>"+(t.rising?'<span class="l-pill up">Rising</span>':"")+(t.loc?"<span>"+esc(t.loc)+"</span>":"")+"<span>"+t.sources+" source"+(t.sources==1?"":"s")+"</span><span>Seen "+esc(t.first_seen_et)+"</span></div></div>"}).join(""):'<p class="l-empty">No ranked alerts right now.</p>';
 clampBtns();}
 // map
if(on("m")){ var W=360,H=155,x=function(l){return l+180},y=function(a){return (82-a)*(H/155)};
 var s='<svg viewBox="0 0 '+W+" "+H+'" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Map of '+S.geo.length+' located alerts"><defs><filter id="bntl_g3" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><g fill="rgba(240,240,250,.13)">';
 (land||[]).forEach(function(p){s+='<circle cx="'+x(p[0])+'" cy="'+y(p[1])+'" r=".62"/>'});s+="</g>";
 var pts=S.geo.slice().sort(function(a,b){return a[2]-b[2]}),cn={c:0,e:0,h:0};
 pts.forEach(function(g,i){var b=band(g[2]),rad=b==="h"?2.1:b==="e"?1.5:1.1;cn[b]++;if(g[0]<-73||g[0]>82)return;
  s+='<circle cx="'+x(g[1]).toFixed(1)+'" cy="'+y(g[0]).toFixed(1)+'" r="'+rad+'" fill="'+col[b]+'" fill-opacity="'+(b==="c"?.7:.95)+'" filter="url(#bntl_g3)">'+""/* Nov 17 1:45 AM: SMIL pulse removed, it repainted the blurred SVG every frame and caused most scroll jank on /live */+"</circle>"});
 /* Nov 17 push 2: ~4,000 SVG nodes + 100 blur filters re-rasterised while scrolling; draw them once into an image instead */
 var svgS=(s+"</svg>").replace("<svg ",'<svg xmlns="http://www.w3.org/2000/svg" '),im=new Image();im.alt="";im.decoding="async";im.setAttribute("role","img");
 im.setAttribute("aria-label",pts.length+" located alerts on a world map");im.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(svgS);
 var mp=$("bntl_map");if(im.decode)im.decode().then(function(){mp.replaceChildren(im)},function(){mp.innerHTML=svgS});else{mp.innerHTML="";mp.appendChild(im)}$("bntl_maph").textContent=pts.length+" located alerts · "+cn.h+" high, "+cn.e+" elevated, "+cn.c+" calm";}
 // rank spread
if(on("d")){ var mx=1;for(var k=0;k<=10;k++)mx=Math.max(mx,S.ranks[k]||0);var h="";
 for(k=0;k<=10;k++){var n=S.ranks[k]||0,b2=band(k);h+='<div><em>'+(n||"")+'</em><i data-h="'+(n?Math.max(4,100*n/mx):2)+'" style="background:linear-gradient(180deg,'+col[b2]+","+col[b2]+'55);box-shadow:0 0 14px '+col[b2]+'40"></i><span>'+k+"</span></div>"}
 $("bntl_dist").innerHTML=h;setTimeout(function(){[].forEach.call(d.querySelectorAll("#bntl_dist i"),function(e){e.style.height=e.getAttribute("data-h")+"%"})},200);}
 // alerts per day
if(on("v")){ var M=innerWidth<=900,VW=M?340:520,VH=M?220:200,pl=40,pr=10,pt=24,pb=30,V=S.volume||[],vm=1;V.forEach(function(v){vm=Math.max(vm,v.n)});var bw=(VW-pl-pr)/Math.max(1,V.length);
 var vs='<svg viewBox="0 0 '+VW+" "+VH+'" role="img" aria-label="Alerts logged per day"><defs><linearGradient id="bntl_vb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E9EAF0"/><stop offset="1" stop-color="#E9EAF0" stop-opacity=".25"/></linearGradient></defs>';
 [0,.5,1].forEach(function(f){var yy=pt+(VH-pt-pb)*(1-f);vs+='<line x1="'+pl+'" x2="'+(VW-pr)+'" y1="'+yy+'" y2="'+yy+'" stroke="rgba(240,240,250,.07)"/><text x="'+(pl-8)+'" y="'+(yy+4)+'" text-anchor="end" font-family="Montserrat" font-size="10.5" fill="rgba(240,240,250,.45)">'+Math.round(vm*f).toLocaleString()+"</text>"});
 V.forEach(function(v,i){var hh=(VH-pt-pb)*v.n/vm,xx=pl+i*bw+bw*.18,ww=bw*.64;vs+='<rect x="'+xx+'" y="'+(VH-pb-hh)+'" width="'+ww+'" height="'+hh+'" rx="5" fill="url(#bntl_vb)"/><text x="'+(xx+ww/2)+'" y="'+(VH-pb-hh-7)+'" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="11" fill="#F0F0FA">'+v.n.toLocaleString()+'</text><text x="'+(xx+ww/2)+'" y="'+(VH-9)+'" text-anchor="middle" font-family="Montserrat" font-weight="600" font-size="11" fill="rgba(240,240,250,.55)">'+esc(v.d)+"</text>"});
 $("bntl_vol").innerHTML=vs+"</svg>";}
 // categories
if(on("c")){ var cs=Object.keys(S.cats||{}).map(function(k){return [k,S.cats[k]]}).sort(function(a,b){return b[1]-a[1]}),cm=cs.length?cs[0][1]:1;
 $("bntl_cath").textContent="Items logged "+(S.today||"today");
 $("bntl_cats").innerHTML=cs.length?cs.map(function(c){return '<div class="l-catrow"><span>'+esc(c[0])+'</span><div class="b"><i data-w="'+(100*c[1]/cm)+'"></i></div><b>'+c[1].toLocaleString()+"</b></div>"}).join(""):'<p class="l-empty">Nothing logged yet today.</p>';
 setTimeout(function(){[].forEach.call(d.querySelectorAll("#bntl_cats i"),function(e){e.style.width=e.getAttribute("data-w")+"%"})},250);}
}
/* Top signals: three lines, then a More/Less toggle when the headline is longer (CoS Nov 17 1:00 AM). The card link is the headline, stretched over the card. */
function clampBtns(){[].forEach.call(d.querySelectorAll("#bntl_sigs .l-sig"),function(c){var h=c.querySelector("h4"),b=c.querySelector(".l-xp");if(!h||!b||c.classList.contains("full"))return;b.hidden=h.scrollHeight<=h.clientHeight+2})}
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("#bntl_sigs .l-xp");if(!b)return;e.preventDefault();e.stopPropagation();var c=b.closest(".l-sig"),o=!c.classList.contains("full");c.classList.toggle("full",o);b.setAttribute("aria-expanded",o?"true":"false");b.textContent=o?"Less":"More"});
var rzT;addEventListener("resize",function(){clearTimeout(rzT);rzT=setTimeout(clampBtns,200)});
var land=null,LAST=null,MODS=[["g","bntl_ug","the gauge"],["t","bntl_ut","the counts"],["s","bntl_us","top signals"],["m","bntl_um","the map"],["d","bntl_ud","rank spread"],["v","bntl_uv","alerts per day"],["c","bntl_uc","today's categories"]];
/* per-module refresh (Matt Nov 17 1:10 AM): each stamp shows the scan time and the next scan; its button reloads the summary and redraws only that module */
function stamps(S,only){if(!window.BNT||!BNT.up)return;var at=Date.parse(S.last_scan||S.generated||"")||Date.now(),iv=(S.interval||5)*60000,nx=at+iv;while(nx<Date.now()-30000)nx+=iv;
 MODS.forEach(function(m){if(only&&m[0]!==only)return;var el=$(m[1]);if(el)BNT.up(el,{label:m[2],at:at,next:nx,run:function(){return fetchS(true).then(function(T){if(T)render(T,land,m[0])})}})})}
function fetchS(fresh){return fetch("/api/live/summary"+(fresh?"?fresh=1":""),{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){return j&&j.ranks?j:null}).catch(function(){return null})}
function load(){var sumP=fetch("/api/live/summary",{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){acqPart("sum");return j&&j.ranks?j:null});
 var landP=land?Promise.resolve(land).then(function(L){acqPart("land");return L}):fetch("/bnt/land.json").then(function(r){return r.json()}).catch(function(){return []}).then(function(L){acqPart("land");return L});
 Promise.all([sumP,landP]).then(function(a){land=a[1];if(a[0]&&a[0].ranks){render(a[0],land);if(!revealed)reveal()}else if(!revealed)failSoft()}).catch(function(){if(!revealed)failSoft()})}
load();setInterval(function(){if(!d.hidden&&root.getBoundingClientRect().height>0)load()},120000);
})();
