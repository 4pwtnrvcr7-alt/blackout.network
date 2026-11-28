/* Pulse intro: one live instrument. Data from /api/pulse/live (read-only roll-up of the Wire summary, EIA grid, USGS quakes, NOAA Kp), polled every 60 s while visible.
   No stored numbers: a ring with no data is not drawn. One slow ambient motion (a hairline pulse every 4.8 s); everything else is still. Native scroll, passive listeners only. */
(function(){
"use strict";
var d=document,$=function(i){return d.getElementById(i)};
var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- menu, brief options, install (same behaviour the previous intro had; its home.js is not loaded here) ---------- */
var nav=$("h_nav"),menu=$("h_menu"),scrim=$("h_scrim"),last=null,hxBtn=d.querySelector(".h-burger"),closing=false,ct=0;
if(menu&&scrim){
function hx(on){if(hxBtn){hxBtn.setAttribute("data-bn-hx",on?"open":"close");hxBtn.setAttribute("aria-label",on?"Close menu":"Open menu")}}
function finish(on){closing=false;if(ct){clearTimeout(ct);ct=0}menu.classList.toggle("open",on);menu.classList.remove("h-closing");scrim.classList.toggle("on",on);menu.setAttribute("aria-hidden",on?"false":"true");
 if(nav)nav.classList.toggle("h-open",on);
 [].forEach.call(d.querySelectorAll("[data-h-menu]"),function(b){b.setAttribute("aria-expanded",on?"true":"false");if(b.classList.contains("h-burger"))b.setAttribute("aria-label",on?"Close menu":"Open menu")});
 if(on){last=d.activeElement;try{hxBtn&&hxBtn.focus({preventScroll:true})}catch(e){}}else if(last&&last.focus)try{last.focus({preventScroll:true})}catch(e){}}
function open(on){if(ct){clearTimeout(ct);ct=0}
 if(on){if(closing)menu.classList.remove("h-closing");hx(true);finish(true);return}
 if(!menu.classList.contains("open")&&!closing)return;
 hx(false);if(reduce){finish(false);return}
 closing=true;menu.classList.add("h-closing");if(nav)nav.classList.add("h-open");
 ct=setTimeout(function(){finish(false)},680)}
d.addEventListener("click",function(e){if(!e.target.closest("[data-h-menu]"))return;e.preventDefault();open(!(menu.classList.contains("open")&&!closing))});
var hxClose=menu.querySelector(".h-x");if(hxClose)hxClose.onclick=function(){open(false)};
menu.addEventListener("click",function(e){var a=e.target.closest("a[href]");if(a&&(menu.classList.contains("open")||closing)){last=null;open(false)}});scrim.onclick=function(){open(false)};
d.addEventListener("keydown",function(e){if(e.key==="Escape"&&(menu.classList.contains("open")||closing))open(false)});
}
var mo=$("h_moreopt"),box=$("nl_app");if(mo&&box)mo.addEventListener("click",function(){var o=!box.classList.contains("more");box.classList.toggle("more",o);mo.setAttribute("aria-expanded",o?"true":"false");mo.textContent=o?"Fewer options":"More options: how often, your area, topics"});
var inst=$("h_install");if(inst)inst.addEventListener("click",function(){if(window.BN&&BN.showInstallGuide)BN.showInstallGuide();else location.href="/live"});
var sec=d.querySelector(".pl"),brief=d.querySelector(".pl-brief");
if("IntersectionObserver" in window){
 if(brief)new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)e.target.classList.add("in")})},{threshold:.15}).observe(brief);
 if(sec&&nav)new IntersectionObserver(function(es){es.forEach(function(e){nav.classList.toggle("solid",!e.isIntersecting)})},{threshold:.5}).observe(sec);
}else if(brief)brief.classList.add("in");

/* ---------- instrument ---------- */
var cv=$("pl_cv"),sv=$("pl_sv");if(!cv||!sv||!cv.getContext)return;
var g=cv.getContext("2d"),sg=sv.getContext("2d");
var WH=[240,240,250],ACC=[124,196,255],LBL=[126,131,140],DIM=[104,109,118];
var FF="Inter,'Noto Sans',Arial,sans-serif";
function col(c,a){return"rgba("+c[0]+","+c[1]+","+c[2]+","+a+")"}
function clamp(x,a,b){return Math.min(b===undefined?1:b,Math.max(a===undefined?0:a,x))}
function sm(a,b,x){var t=clamp((x-a)/(b-a));return t*t*(3-2*t)}
function eo(t){return 1-Math.pow(1-clamp(t),3)}
function eio(t){t=clamp(t);return t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2}
var KEYS=["wire","quake","grid","space"],STC={online:0,watch:1,degraded:1};
var D=null,lastOk=0,R0={},focus=null,foc={wire:0,quake:0,grid:0,space:0},pulseT0=null,scopeT0=null;
var dpr=1,ds=0,sW=0,sH=0,vis=true,raf=0,tPrev=0;

/* data -> render arrays */
var RK=[],Q=[],REG=[],KP=[],NAT=[],hiN=0,qMax=0,gwNow=0,kpNow=0;
function prep(j){
 RK=[];Q=[];REG=[];KP=[];NAT=[];
 if(j.wire){Object.keys(j.wire.ranks).map(Number).sort(function(a,b){return a-b}).forEach(function(r){for(var k=0;k<j.wire.ranks[r];k++)RK.push(r)});hiN=RK.filter(function(r){return r>=7}).length}
 if(j.quakes){var now=Date.now()/1000;Q=j.quakes.filter(function(q){return now-q[0]<86400&&now-q[0]>=-60});qMax=Q.reduce(function(a,q){return Math.max(a,q[1])},0)}
 if(j.grid){var tot=j.grid.regions.reduce(function(a,r){return a+r.mw},0);REG=j.grid.regions.map(function(r){return{id:r.id,st:STC[r.status]===undefined?1:STC[r.status],status:r.status,sh:r.mw/tot}});NAT=j.grid.series;gwNow=NAT.length?NAT[NAT.length-1][1]/1000:tot/1000}
 if(j.space){KP=j.space.kp;kpNow=j.space.now}
}
var ET=function(ts,withDate){try{return new Date(ts*1000).toLocaleString("en-US",{timeZone:"America/New_York",month:withDate?"short":undefined,day:withDate?"numeric":undefined,hour:"numeric",minute:"2-digit"})}catch(e){return""}};
function txt(sel,v){var el=d.querySelector(sel);if(el&&el.textContent!==v)el.textContent=v}
function fill(j){
 var w=j.wire,ok=function(k){return KEYS.indexOf(k)>=0};
 if(w){txt('[data-n="def"]',w.level!=null?Number(w.level).toFixed(1):"–");txt('[data-v="wire"]',String(w.n));txt('[data-n="wire"]',String(w.n));txt('[data-u="wire"]',"rank 7+ · "+hiN);
  var dot=$("pl_dot");if(dot){var lv=Number(w.level)||0;dot.className=lv>=7?"h":lv>=4?"e":""}
  txt('[data-c="def1"]',w.level_hi?"Threat level is the average rank of the "+w.level_n+" stories ranked 7 and up.":"Threat level is the average rank of the top "+w.level_n+" stories.");
  txt('[data-c="wire1"]',w.n+" stories on the Wire, "+hiN+" ranked 7 and up. Last scan "+w.scan_et+".")}
 if(Q.length||j.quakes){txt('[data-v="quake"]',String(Q.length));txt('[data-n="quake"]',String(Q.length));txt('[data-u="quake"]',Q.length?"largest M"+qMax.toFixed(1):"M2.5+");txt('[data-c="quake1"]',Q.length+" quakes of M2.5 or more in the last 24 hours"+(Q.length?"; the largest was M"+qMax.toFixed(1)+".":"."))}
 if(j.grid){txt('[data-v="grid"]',String(Math.round(gwNow)));txt('[data-n="grid"]',String(Math.round(gwNow)));txt('[data-u="grid"]',"GW · "+REG.length+" regions");
  var att=REG.filter(function(r){return r.st}).map(function(r){return r.id+" "+r.status}),on=REG.length-att.length;txt('[data-c="grid1"]',(att.length?att.join(" · ")+" · ":"")+on+" online.");
  if(NAT.length){txt("#pl_t0",ET(NAT[0][0],true)+" ET");txt("#pl_t1",ET(NAT[NAT.length-1][0],true)+" ET")}}
 if(j.space){txt('[data-v="space"]',kpNow.toFixed(1));txt('[data-n="space"]',kpNow.toFixed(1));txt('[data-u="space"]',"G"+j.space.g+" · NOAA SWPC");txt('[data-c="space1"]',"Kp "+kpNow.toFixed(1)+" now, NOAA G"+j.space.g+" scale.")}
 KEYS.forEach(function(k){var b=d.querySelector('.pl-pill[data-k="'+k+'"]'),has=k==="wire"?!!j.wire:k==="quake"?!!j.quakes:k==="grid"?!!j.grid:!!j.space;if(b)b.disabled=!has;if(!has&&focus===k)setFocus(null)});
 var live=$("pl_live");if(live){var lbl=live.querySelector("span"),stale=false;
  if(w&&w.scan){var m=(Date.now()-new Date(w.scan).getTime())/60000;stale=m>25;lbl.textContent=stale?"Delayed · last scan "+w.scan_et:"Live"}else lbl.textContent=w?"Live":"Updating";live.classList.toggle("off",stale||!w)}
}
function apply(j){
 var first=!D;D=j;lastOk=Date.now();prep(j);fill(j);var t=performance.now();
 if(j.wire&&R0.wire==null)R0.wire=t;if(j.quakes&&R0.quake==null)R0.quake=t;if(j.grid&&R0.grid==null)R0.grid=t;if(j.space&&R0.space==null)R0.space=t;
 if(NAT.length&&scopeT0==null)scopeT0=t;if(first&&pulseT0==null)pulseT0=t;
 start();
}
var inflight=false;
function load(){if(inflight||d.hidden)return;inflight=true;
 var c=window.AbortController?new AbortController():null,to=setTimeout(function(){c&&c.abort()},30000);
 fetch("/api/pulse/live",{cache:"no-store",signal:c?c.signal:undefined}).then(function(r){return r.ok?r.json():Promise.reject()}).then(function(j){if(j&&(j.wire||j.grid||j.space||j.quakes))apply(j)}).catch(function(){
  if(D&&Date.now()-lastOk>600000){D={ts:0};RK=[];Q=[];REG=[];KP=[];NAT=[];fill({});var l=$("pl_live");if(l){l.classList.add("off");l.querySelector("span").textContent="Offline"}}
 }).then(function(){clearTimeout(to);inflight=false})}
load();setInterval(load,60000);d.addEventListener("visibilitychange",function(){if(!d.hidden){load();start()}});

/* focus (single tap on a pill; tap again to release) */
function setFocus(k){focus=k;
 [].forEach.call(d.querySelectorAll(".pl-pill"),function(b){b.setAttribute("aria-pressed",b.getAttribute("data-k")===k?"true":"false")});
 var key=k||"def";
 [].forEach.call(d.querySelectorAll(".pl-cs,.pl-cap p"),function(e){e.classList.toggle("on",e.getAttribute("data-for")===key)});
 start()}
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".pl-pill");if(!b||b.disabled)return;var k=b.getAttribute("data-k");setFocus(focus===k?null:k)});

/* ---------- drawing ---------- */
function size(){dpr=Math.min(window.devicePixelRatio||1,2);var w=cv.clientWidth||320;ds=w/372;cv.width=Math.round(w*dpr);cv.height=Math.round(w*dpr);
 sW=sv.clientWidth||300;sH=sv.clientHeight||78;sv.width=Math.round(sW*dpr);sv.height=Math.round(sH*dpr)}
function hair(c,x0,y0,x1,y1,col_,a,w){c.strokeStyle=col(col_,a);c.lineWidth=w;c.beginPath();c.moveTo(x0,y0);c.lineTo(x1,y1);c.stroke()}
function ringU(k,now,delay,dur){if(R0[k]==null)return 0;return reduce?1:eio((now-R0[k]-delay)/dur)}
function draw(now){
 var W=cv.width,s=ds*dpr,cx=W/2,cy=W/2;g.setTransform(1,0,0,1,0,0);g.clearRect(0,0,W,W);
 var F=foc.wire+foc.quake+foc.grid+foc.space,mul=function(k){return 1-.78*(F-foc[k])};
 var tp=pulseT0==null||reduce?-1:(now-pulseT0)/1000-1.4,per=4.8,pp=tp>0?(tp%per)/per:0;
 var pr=tp>0?eo(pp*1.15)*160*s:0,pa=tp>0?(1-sm(.1,1,pp))*.2:0;
 var ping=function(r,wd){return tp>0?Math.exp(-Math.pow((pr-r*s)/(wd*s),2))*pa*2.2:0};
 var ang=function(f){return -Math.PI/2+f*Math.PI*2},lw=Math.max(.5,.6*dpr);
 /* bezel */
 var bz=reduce?1:eo((now-T0)/1600);
 for(var i=0;i<72;i++){var a=i/72*Math.PI*2-Math.PI/2,big=i%6===0,r0=140*s,r1=r0+(big?6:3)*s,al=(big?.42:.16)*clamp(bz*1.4-i/72*.4);if(al<=0)continue;hair(g,cx+Math.cos(a)*r0,cy+Math.sin(a)*r0,cx+Math.cos(a)*r1,cy+Math.sin(a)*r1,WH,al,lw)}
 /* quake-ring time labels (outside the bezel) */
 if(D&&D.quakes){var la=sm(0,1,reduce?1:(now-(R0.quake||now)-300)/900)*mul("quake"),lr=151*s,fs=Math.max(7*dpr,7.2*s);g.font="600 "+fs+"px "+FF;try{g.letterSpacing=(1.8*s)+"px"}catch(e){}g.fillStyle=col(LBL,la);
  g.textAlign="center";g.fillText("NOW",cx,cy-lr-2*s);g.fillText("−12 H",cx,cy+lr+9*s);g.textAlign="right";g.fillText("−6 H",cx-lr,cy+3*s);g.textAlign="left";g.fillText("−18 H",cx+lr,cy+3*s)}
 /* pulse */
 if(pa>0){g.strokeStyle=col(WH,pa);g.lineWidth=lw;g.beginPath();g.arc(cx,cy,pr,0,6.2832);g.stroke()}
 /* ring 1: wire */
 if(RK.length){var u=ringU("wire",now,0,2800),m=mul("wire"),r0=64*s,n=RK.length;
  for(var i=0;i<n;i++){var f=i/n,a=ang(f),rk=RK[i],vis_=clamp(u*1.25-f*.9);if(vis_<=0)continue;var len=(3.5+rk*1.55)*s*eo(vis_),base=rk>=7?.95:rk>=4?.46:.2,al=Math.min(1,(base+ping(64+len/s/2,9))*m),cs=Math.cos(a),sn=Math.sin(a);
   hair(g,cx+cs*r0,cy+sn*r0,cx+cs*(r0+len),cy+sn*(r0+len),WH,al,Math.max(.6,.75*dpr))}}
 /* ring 2: quakes, now = top, counter-clockwise, radius = magnitude */
 if(Q.length){var u2=ringU("quake",now,600,2400),m2=mul("quake"),q0=86*s,q1=106*s,nowS=Date.now()/1000;
  for(var i=0;i<Q.length;i++){var q=Q[i],fr=-((nowS-q[0])/86400),a=ang(fr),rr=q0+clamp((q[1]-2.4)/3.6)*(q1-q0),v=clamp(u2*1.3-(-fr)*.8);if(v<=0)continue;
   g.fillStyle=col(WH,Math.min(1,(.7+ping(rr/s,9))*m2*v));g.beginPath();g.arc(cx+Math.cos(a)*rr,cy+Math.sin(a)*rr,(.8+q[1]*.26)*s,0,6.2832);g.fill()}}
 /* ring 3: grid */
 if(REG.length){var u3=ringU("grid",now,1000,2400),m3=mul("grid"),gr=114*s,gap=.016,f=0;g.lineWidth=2*s;g.lineCap="butt";
  for(var i=0;i<REG.length;i++){var r=REG[i],len=r.sh-gap,a0=ang(f+gap/2),a1=ang(f+gap/2+len*u3),c=r.st?ACC:WH,base=r.st?.95:.5,al=Math.min(1,(base+ping(114,9))*m3*(!r.st&&foc.grid>0?(.6+.4*foc.grid):1));
   if(u3>0){g.strokeStyle=col(c,al);g.beginPath();g.arc(cx,cy,gr,a0,a1);g.stroke()}f+=len+gap}}
 /* ring 4: space (Kp bars, last 72 h) */
 if(KP.length){var u4=ringU("space",now,1400,2400),m4=mul("space"),k0=122*s,n4=KP.length;
  for(var i=0;i<n4;i++){var f=i/n4,a=ang(f+.5/n4),len=(1.5+KP[i]/9*9)*s*eo(clamp(u4*1.3-f*.8));if(len<=0)continue;var last_=i===n4-1,cs=Math.cos(a),sn=Math.sin(a);
   hair(g,cx+cs*k0,cy+sn*k0,cx+cs*(k0+len),cy+sn*(k0+len),last_?ACC:WH,Math.min(1,((last_?1:.5)+ping(122+len/s/2,9))*m4),Math.max(.8,1*s))}}
}
function drawScope(now){
 var c=sg,W=sv.width,H=sv.height;c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,W,H);if(NAT.length<2)return;
 var x0=1*dpr,x1=W-1*dpr,y1=H-3*dpr,sh=H-10*dpr,t0=NAT[0][0],t1=NAT[NAT.length-1][0],vmin=Infinity,vmax=-Infinity;
 NAT.forEach(function(p){vmin=Math.min(vmin,p[1]);vmax=Math.max(vmax,p[1])});vmin*=.985;vmax*=1.015;
 var X=function(t){return x0+(t-t0)/(t1-t0)*(x1-x0)},Y=function(v){return y1-(v-vmin)/(vmax-vmin)*sh*.74-3*dpr};
 var u=scopeT0==null?0:reduce?1:eio((now-scopeT0-500)/6000),head=u*(t1-t0)+t0,gf=.55+.45*foc.grid,dq=1-.6*foc.grid;
 hair(c,x0,y1,x1,y1,WH,.18,Math.max(.5,.6*dpr));
 var pts=[];for(var t=t0;t<=head;t+=(t1-t0)/240){var i=0;while(i<NAT.length-2&&NAT[i+1][0]<t)i++;var f=clamp((t-NAT[i][0])/(NAT[i+1][0]-NAT[i][0])),v=NAT[i][1]+(NAT[i+1][1]-NAT[i][1])*f;pts.push([X(t),Y(v),v])}
 if(pts.length>1){var gr=c.createLinearGradient(0,0,0,H);gr.addColorStop(0,"rgba(240,240,250,.07)");gr.addColorStop(1,"rgba(240,240,250,0)");c.fillStyle=gr;c.beginPath();c.moveTo(pts[0][0],y1);pts.forEach(function(p){c.lineTo(p[0],p[1])});c.lineTo(pts[pts.length-1][0],y1);c.closePath();c.fill();
  c.strokeStyle=col(WH,gf);c.lineWidth=Math.max(1,1*dpr);c.lineJoin="round";c.beginPath();pts.forEach(function(p,i){i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1])});c.stroke()}
 if(D&&D.quakes)D.quakes.forEach(function(q){if(q[0]<t0||q[0]>head||q[0]>t1)return;var x=X(q[0]),h=(q[1]-2.2)*8*dpr,a=clamp((head-q[0])/2400);hair(c,x,y1,x,y1-h-2*dpr,WH,.5*a*dq,Math.max(.6,.8*dpr))});
 if(pts.length){var p=pts[pts.length-1];c.fillStyle=col(ACC,1);c.beginPath();c.arc(p[0],p[1],2.2*dpr,0,6.2832);c.fill();
  c.font="500 "+(9.5*dpr)+"px "+FF;c.textAlign="center";c.fillStyle=col(WH,.95);var lx=Math.min(x1-22*dpr,Math.max(x0+24*dpr,p[0]));c.fillText(Math.round(p[2]/1000)+" GW",lx,p[1]-11*dpr)}
}
var T0=performance.now();
function frame(now){raf=0;if(!vis||d.hidden)return;
 var dt=Math.min(.1,(now-(tPrev||now))/1000);tPrev=now;var kk=1-Math.exp(-dt*3.2),moving=false;
 KEYS.forEach(function(k){var tg=focus===k?1:0;foc[k]+=(tg-foc[k])*kk;if(Math.abs(tg-foc[k])<.002)foc[k]=tg;else moving=true});
 draw(now);drawScope(now);
 var busy=!reduce||moving||!D||(now-T0<9000); /* reduced motion: draw until settled, then only on change */
 if(!reduce||busy)raf=requestAnimationFrame(frame)}
function start(){if(!raf&&vis&&!d.hidden){tPrev=0;raf=requestAnimationFrame(frame)}}
size();if("ResizeObserver" in window)new ResizeObserver(function(){size();start()}).observe(cv);else addEventListener("resize",function(){size();start()});
if("IntersectionObserver" in window&&sec)new IntersectionObserver(function(es){vis=es[0].isIntersecting;if(vis)start()},{threshold:0}).observe(sec);
start();
})();
