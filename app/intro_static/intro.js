/* Intro v2: loader (real progress), panel media, live overlays, menu. Native scroll only: no scroll listeners, no snap. */
(function(){
"use strict";
var d=document,de=d.documentElement,$=function(id){return d.getElementById(id)},V=window.BNT_MEDIA_V||"1";
var mq=function(q){return window.matchMedia&&matchMedia(q).matches};
var reduce=mq("(prefers-reduced-motion: reduce)");
var save=!!(navigator.connection&&navigator.connection.saveData);
var portrait=innerWidth<=900||innerHeight>innerWidth,sfx=portrait?"m":"d";
var panels=[].slice.call(d.querySelectorAll(".ix-p"));
var noVideo=reduce||save;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function fmt(n){return Number(n).toLocaleString("en-US")}

/* ---------- loader: 100 blocks, one per real percent, bottom-to-top ---------- */
var ld=$("ix_ld"),ldn=$("ix_ldn"),cells=ld?[].slice.call(ld.querySelectorAll(".ix-ldc")):[],order=[],shown=0,want=0,done=false,t0=performance.now(),timer=0;
(function(){var rows=[];for(var r=9;r>=0;r--){var row=[];for(var c=0;c<10;c++)row.push(r*10+c);for(var i=row.length-1;i>0;i--){var j=Math.random()*(i+1)|0,t=row[i];row[i]=row[j];row[j]=t}order=order.concat(row)}})();
var W={data:.1,img:.2,vid:.7},P={data:0,img:0,vid:noVideo?1:0};
function prog(){return Math.min(1,W.data*P.data+W.img*P.img+W.vid*P.vid)}
function tick(){timer=0;if(shown<want){var el=cells[order[shown]];if(el)el.classList.add("in");shown++;if(ldn)ldn.textContent=String(shown);if(ld)ld.setAttribute("aria-valuenow",String(shown))}
 if(shown<want)timer=setTimeout(tick,reduce?0:9);else if(shown>=100)finish()}
function update(){if(done)return;want=Math.max(want,Math.floor(prog()*100+1e-6));if(!timer)tick()}
function finish(){if(done)return;done=true;setTimeout(reveal,reduce?0:160)}
function reveal(){de.classList.add("ix-ready");de.classList.remove("ix-loading");panels.length&&panels[0].classList.add("in");
 setTimeout(function(){if(ld)ld.style.display="none"},700);startIO()}
function fast(){/* everything was already cached: no animation, show at once */done=true;if(ldn)ldn.textContent="100";cells.forEach(function(c){c.classList.add("in")});reveal()}
setTimeout(function(){if(!done){P.data=P.img=P.vid=1;want=100;if(!timer)tick()}},9000);  /* never hold the page longer than 9 s; late media attaches when it lands */

/* ---------- posters ---------- */
var imgs=panels.map(function(s){return s.querySelector(".ix-bg img")}),imgN=0;
function imgDone(){imgN++;P.img=imgN/imgs.length;update();check()}
imgs.forEach(function(im){if(!im){imgDone();return}im.loading="eager";var ok=function(){(im.decode?im.decode():Promise.resolve()).catch(function(){}).then(imgDone)};if(im.complete&&im.naturalWidth)ok();else{im.addEventListener("load",ok,{once:true});im.addEventListener("error",imgDone,{once:true})}});

/* ---------- videos: fetched whole behind the loader, then played from memory (no network stalls while scrolling) ---------- */
var keys=window.BN_IX_MEDIA||[],blobs={},bytes={},total={};
function vidProg(){var a=0,b=0;keys.forEach(function(k){a+=bytes[k]||0;b+=total[k]||0});var known=keys.every(function(k){return total[k]!=null});P.vid=known&&b?a/b:Math.min(.95,a/(keys.length*400000));update();check()}
function attach(k){var s=panels[keys.indexOf(k)];if(!s||!blobs[k])return;var v=s.querySelector("video");if(!v||v.src)return;
 v.muted=true;v.defaultMuted=true;v.setAttribute("muted","");v.src=blobs[k];v.addEventListener("playing",function(){v.classList.add("on")},{once:true});
 sync(s)}
function getVid(k){var url="/bnt/media/"+k+"-"+sfx+".mp4?v="+V;
 return fetch(url).then(function(r){if(!r.ok)throw 0;total[k]=+r.headers.get("content-length")||0;
  if(!r.body||!r.body.getReader)return r.blob().then(function(b){bytes[k]=total[k]=b.size;return b});
  var rd=r.body.getReader(),parts=[];bytes[k]=0;
  return (function pump(){return rd.read().then(function(x){if(x.done)return new Blob(parts,{type:"video/mp4"});parts.push(x.value);bytes[k]+=x.value.length;vidProg();return pump()})})();
 }).then(function(b){blobs[k]=URL.createObjectURL(b);bytes[k]=total[k]=total[k]||b.size;vidProg();attach(k)}).catch(function(){bytes[k]=total[k]=1;vidProg()})}
if(!noVideo){/* hero first, then the rest two at a time */
 var q=keys.slice(),run=0;function next(){while(run<2&&q.length){run++;getVid(q.shift()).then(function(){run--;next()})}}next()}

/* ---------- live data ---------- */
var L=null,lastFetch=0;
function load(first){lastFetch=Date.now();return fetch("/api/intro/live",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(j){if(j){L=j;paint()}}).catch(function(){}).then(function(){if(first){P.data=1;update();check()}})}
function slot(f){return d.querySelector('[data-f="'+f+'"]')}
function set(f,h){var el=slot(f);if(el&&el.innerHTML!==h)el.innerHTML=h}
function band(r){return r>=7?"r10":r>=4?"r6":"r3"}
function paint(){var w=L.wire,ln=L.launch,wx=L.wx,g=L.grid,mk=L.mk,br=L.brief;
 if(w){set("scan",esc(w.scan));set("wire",w.wire?fmt(w.wire)+" stories":"");set("high",fmt(w.high));
  set("top",(w.top||[]).map(function(x){return '<li><a href="'+esc(x.u)+'"><b class="'+band(x.r)+'" aria-label="Rank '+x.r+'">'+x.r+'</b><div><span>'+esc(x.t)+'</span>'+(x.loc||x.n?'<small>'+esc([x.loc,x.n?x.n+" sources":""].filter(Boolean).join(" · "))+'</small>':'')+'</div></a></li>'}).join(""));
  set("bands",'<div class="hi"><b>'+fmt(w.high)+'</b><span>High 7–10</span></div><div><b>'+fmt(w.elev)+'</b><span>Elevated 4–6</span></div><div><b>'+fmt(w.calm)+'</b><span>Calm 0–3</span></div>'+(w.mapped?'<div><b>'+fmt(w.mapped)+'</b><span>On the map</span></div>':''))}
 set("launch",ln?esc(ln.name+(ln.prov?" · "+ln.prov:"")+(ln.prec&&!/^(Minute|Second)$/.test(ln.prec)?" · time ±1 "+ln.prec.toLowerCase():"")):"");
 if(wx){set("wxn",'<div><b>'+fmt(wx.n)+'</b><span>Active NWS alerts</span></div>'+(wx.counts||[]).slice(0,2).map(function(c){return '<div><b>'+fmt(c[1])+'</b><span>'+esc(c[0])+'</span></div>'}).join(""));
  set("wx",(wx.rows||[]).map(function(r){return '<li><span>'+esc(r.e)+(r.a?" · "+esc(r.a):"")+'</span><em>'+esc(r.s)+'</em></li>'}).join(""))}
 if(g){set("gridn",'<div'+(g.out>=100000?' class="hi"':'')+'><b>'+fmt(g.out)+'</b><span>Customers out (US)</span></div><div><b>'+(g.bad+g.watch)+'<small style="font-size:.45em;opacity:.6"> / '+g.regions+'</small></b><span>Grid regions on watch</span></div><div><b>G'+g.g+'</b><span>Geomagnetic storm</span></div>');
  set("grid",(g.states||[]).map(function(s){return '<li><span>'+esc(s.n)+'</span><em>'+fmt(s.o)+' out</em></li>'}).join(""))}
 if(mk&&mk.q&&mk.q.length){set("mk",mk.q.map(function(x){var up=x.c>=0;return '<div><span>'+esc(x.l)+'</span><b>'+(x.p>=1000?fmt(Math.round(x.p)):x.p.toFixed(2))+'</b><i class="'+(up?"up":"dn")+'">'+(up?"+":"−")+Math.abs(x.c).toFixed(2)+'%</i></div>'}).join(""));
  var n=slot("mk");if(n&&!n.nextElementSibling.classList.contains("ix-note")){var s=d.createElement("small");s.className="ix-note";n.parentNode.insertBefore(s,n.nextSibling)}
  if(n&&n.nextElementSibling.classList.contains("ix-note"))n.nextElementSibling.textContent="Delayed quotes"+(mk.asof?" · as of "+mk.asof:"")}
 clock();
 [].forEach.call(d.querySelectorAll(".ix-strip>div"),function(c){var e=c.querySelector("dd");c.hidden=!(e&&e.textContent.trim())})}
function hms(ms){var s=Math.max(0,Math.floor(ms/1000)),dd=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60),x=s%60,p=function(n){return(n<10?"0":"")+n};return(dd?dd+"d ":"")+p(h)+":"+p(m)+":"+p(x)}
function clock(){if(!L)return;var now=Date.now();
 if(L.launch){var t=Date.parse(L.launch.net)-now;set("tminus",t>0?"T−"+hms(t):"Liftoff window")}
 if(L.brief){var b=Date.parse(L.brief.next)-now;if(b<0){load();return}set("brief",'<div><b>'+hms(b)+'</b><span>Next brief · '+esc(L.brief.label)+'</span></div>')}}
setInterval(function(){if(d.visibilityState==="visible")clock()},1000);
setInterval(function(){if(d.visibilityState==="visible")load()},60000);
d.addEventListener("visibilitychange",function(){if(d.visibilityState==="visible"&&Date.now()-lastFetch>60000)load()});
load(true);

/* ---------- loader completion ---------- */
var checked=false;
function check(){if(done)return;if(prog()>=.999){if(!checked&&performance.now()-t0<350){checked=true;fast();return}want=100;if(!timer)tick()}}

/* ---------- panels: reveal once, play only what is on screen ---------- */
var nav=$("h_nav"),moving=false,st=0;
function sync(s){var v=s.querySelector("video");if(!v||!v.src)return;var want=s.classList.contains("vis")&&!moving&&d.visibilityState==="visible";
 if(want&&v.paused){var p=v.play();if(p&&p.catch)p.catch(function(){})}else if(!want&&!v.paused)v.pause()}
d.addEventListener("visibilitychange",function(){panels.forEach(sync)});
function startIO(){if(!("IntersectionObserver" in window)){panels.forEach(function(s){s.classList.add("in")});return}
 var rv=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");rv.unobserve(e.target)}})},{threshold:.3});
 /* one decoder at a time: the panel holding at least half the screen plays, every other panel holds its frame.
    While a scroll is in motion the video holds its frame too (resumes 160 ms after the page settles), so the
    compositor only moves pixels: no decode work competes with the scroll. Passive listener, no layout reads. */
 var pl=new IntersectionObserver(function(es){es.forEach(function(e){var s=e.target,on=e.isIntersecting&&e.intersectionRatio>=.5;s.classList.toggle("vis",on);sync(s)})},{threshold:[0,.5,1]});
 addEventListener("scroll",function(){if(!moving){moving=true;panels.forEach(sync)}if(st)clearTimeout(st);st=setTimeout(function(){st=0;moving=false;panels.forEach(sync)},160)},{passive:true});
 panels.forEach(function(s,i){if(i)rv.observe(s);pl.observe(s)});
 if(panels[0]&&nav){new IntersectionObserver(function(es){nav.classList.toggle("solid",!es[0].isIntersecting)},{rootMargin:"-72px 0px 0px 0px",threshold:0}).observe(panels[0])}}

/* ---------- menu (same behaviour as the previous intro) ---------- */
var menu=$("h_menu"),scrim=$("h_scrim"),last=null,hxBtn=d.querySelector(".h-burger"),closing=false,ct=0;
if(menu&&scrim){
function hx(on){if(hxBtn){hxBtn.setAttribute("data-bn-hx",on?"open":"close");hxBtn.setAttribute("aria-label",on?"Close menu":"Open menu")}}
function fin(on){closing=false;if(ct){clearTimeout(ct);ct=0}menu.classList.toggle("open",on);menu.classList.remove("h-closing");scrim.classList.toggle("on",on);menu.setAttribute("aria-hidden",on?"false":"true");
 if(nav)nav.classList.toggle("h-open",on);
 [].forEach.call(d.querySelectorAll("[data-h-menu]"),function(b){b.setAttribute("aria-expanded",on?"true":"false")});
 if(on){last=d.activeElement;try{hxBtn&&hxBtn.focus({preventScroll:true})}catch(e){}}else if(last&&last.focus)try{last.focus({preventScroll:true})}catch(e){}}
function open(on){if(ct){clearTimeout(ct);ct=0}
 if(on){if(closing)menu.classList.remove("h-closing");hx(true);fin(true);return}
 if(!menu.classList.contains("open")&&!closing)return;
 hx(false);if(reduce){fin(false);return}
 closing=true;menu.classList.add("h-closing");if(nav)nav.classList.add("h-open");
 ct=setTimeout(function(){fin(false)},680)}
d.addEventListener("click",function(e){if(!e.target.closest("[data-h-menu]"))return;e.preventDefault();open(!(menu.classList.contains("open")&&!closing))});
var xb=menu.querySelector(".h-x");if(xb)xb.onclick=function(){open(false)};
menu.addEventListener("click",function(e){var a=e.target.closest("a[href]");if(a&&(menu.classList.contains("open")||closing)){last=null;open(false)}});scrim.onclick=function(){open(false)};
d.addEventListener("keydown",function(e){if(e.key==="Escape"&&(menu.classList.contains("open")||closing))open(false)});
}
/* in-page links (the hero "Explore" and the menu "Intro") scroll natively */
d.addEventListener("click",function(e){var a=e.target.closest('a[href^="#"]');if(!a)return;var t=$(a.getAttribute("href").slice(1));if(!t)return;e.preventDefault();t.scrollIntoView({behavior:reduce?"auto":"smooth",block:"start"})});
})();
