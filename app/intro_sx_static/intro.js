/* Homepage intro (intro_sx.py). One full-screen panel per menu section; live strips from /api/intro/live (read-only), polled every 60 s while the tab is visible.
   Strips stay hidden until real data arrives. Footage plays on desktop only, near the viewport, never with reduced motion or Save-Data. Passive listeners only. */
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
var brief=$("brief"),rail=d.querySelector(".sx-rail"),secs=[].slice.call(d.querySelectorAll("section.sx"));
var rl={};if(rail)[].forEach.call(rail.querySelectorAll("a"),function(a){rl[a.getAttribute("href").slice(1)]=a});
var conn=navigator.connection||{},wide=window.matchMedia&&matchMedia("(min-width: 901px)").matches;
var vidOK=wide&&!reduce&&!conn.saveData&&!/(^|-)2g$/.test(conn.effectiveType||"");
function vid(s,on){var v=s.querySelector(".sx-bg video");if(!v||!vidOK)return;
 if(on){if(!v.src&&!v.querySelector("source")){var c=v.dataset.webm&&v.canPlayType("video/webm")?v.dataset.webm:v.dataset.mp4;if(!c)return;v.src=c;v.addEventListener("playing",function(){v.classList.add("on")},{once:true})}
  var p=v.play();if(p&&p.catch)p.catch(function(){})}
 else if(!v.paused)v.pause()}
if("IntersectionObserver" in window){
 var io=new IntersectionObserver(function(es){es.forEach(function(e){var s=e.target;
  if(e.isIntersecting&&e.intersectionRatio>=.5){s.classList.add("sx-in");for(var k in rl)rl[k].classList.toggle("on",k===s.id);if(rail)rail.classList.remove("off");vid(s,true)}
  else if(!e.isIntersecting||e.intersectionRatio<.2)vid(s,false)})},{threshold:[0,.2,.5]});
 secs.forEach(function(s){io.observe(s)});
 if(brief)new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");if(rail)rail.classList.add("off")}})},{threshold:.25}).observe(brief);
}else{secs.forEach(function(s){s.classList.add("sx-in")});if(brief)brief.classList.add("in")}

/* ---------- live strips ---------- */
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function n0(x){return Number(x).toLocaleString("en-US")}
function ago(t){var s=(Date.now()-Date.parse(t))/1000;if(!(s>=0))return"";if(s<3600)return Math.max(1,Math.round(s/60))+"m ago";if(s<86400)return Math.round(s/3600)+"h ago";return Math.round(s/86400)+"d ago"}
function rk(r){r=Number(r)||0;return'<span class="rk"><i'+(r>=7?' class="h"':"")+'></i>Rank '+r+"</span>"}
function row(x,href){var l=String(x.loc||""),l0=l.split(/[:,]/)[0].trim().toLowerCase(),loc=l.length>2&&String(x.h).toLowerCase().indexOf(l0)<0?' <em>· '+esc(l)+"</em>":"";
 return'<a class="sx-r" href="'+esc(href)+'">'+rk(x.r)+'<span class="tx">'+esc(x.h)+loc+"</span>"+(x.t?'<span class="tm">'+esc(ago(x.t))+"</span>":"")+"</a>"}
function kv(a){return'<div class="sx-kv">'+a.filter(function(p){return p[0]!=null&&p[0]!==""}).map(function(p){return"<div><b>"+esc(p[0])+"</b><span>"+esc(p[1])+"</span></div>"}).join("")+"</div>"}
function src(t){return'<p class="sx-src">'+esc(t)+"</p>"}
function etTime(dt){try{return dt.toLocaleString("en-US",{timeZone:"America/New_York",weekday:"short",hour:"numeric",minute:"2-digit"})+" ET"}catch(e){return""}}
function nextSlot(b){if(b.next){var t=new Date(b.next);if(!isNaN(t))return t}
 var sl=b.slots||{},best=null,now=Date.now();
 for(var dd=0;dd<3;dd++)Object.keys(sl).forEach(function(k){var hm=String(sl[k]).split(":");if(hm.length<2)return;
  /* the slot time is New York wall time: find the UTC instant whose ET clock reads hh:mm on day now+dd */
  var base=new Date(now+dd*864e5),ymd=base.toLocaleDateString("en-CA",{timeZone:"America/New_York"});
  for(var off=4;off<=5;off++){var t=new Date(ymd+"T"+("0"+hm[0]).slice(-2)+":"+hm[1]+":00-0"+off+":00");
   if(t.toLocaleTimeString("en-GB",{timeZone:"America/New_York",hour:"2-digit",minute:"2-digit"})===("0"+hm[0]).slice(-2)+":"+hm[1]){if(t.getTime()>now&&(!best||t<best))best=t;break}}});
 return best}
var R={
 wire:function(w){if(!w||!w.top||!w.top.length)return"";return w.top.map(function(x){return row(x,"/wire/"+x.id)}).join("")+src(n0(w.n)+(w.more?"+":"")+" stories in the last 24 h"+(w.hi?" · "+w.hi+" at rank 7+":""))},
 map:function(m){if(!m||!m.n)return"";var top=(m.by||[])[0];return kv([[n0(m.n),"Located stories, 24 h"],[m.regions,m.regions===1?"Region":"Regions"],[top?top.name:null,"Most active"]])},
 weather:function(w){if(!w||w.total==null)return"";var t=(w.top||[]).map(function(s){return esc(s.name)+" "+s.n}).join(" · ");
  return kv([[n0(w.total),"NWS alerts in effect"],[n0(w.land),"Over land"],[w.states,"States"]])+(t?'<div class="sx-r"><span class="rk">Most</span><span class="tx">'+t+"</span></div>":"")+src("Source: National Weather Service, now")},
 grid:function(g){if(!g)return"";var st=g.top_state;
  return kv([[g.customers!=null?n0(g.customers):null,"U.S. customers without power"],[g.countries!=null?g.countries:null,"Countries with internet disruptions, 24 h"],[g.n24!=null?g.n24:null,"Outage reports, 24 h"]])+
   (st?'<div class="sx-r"><span class="rk">Most</span><span class="tx">'+esc(st.name)+" · "+n0(st.n)+" customers out</span></div>":"")},
 markets:function(m){if(!m||!m.rows||!m.rows.length)return"";return m.rows.map(function(r){var c=Number(r.chg),up=c>=0;
  return'<a class="sx-r" href="/markets"><span class="tx">'+esc(r.label)+'</span><span class="v">'+Number(r.price).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})+'</span><span class="c'+(up?" up":"")+'">'+(isNaN(c)?"":(up?"+":"\u2212")+Math.abs(c).toFixed(2)+"%")+"</span></a>"}).join("")},
 brief:function(b){if(!b||!b.top||!b.top.length)return"";var nx=nextSlot(b);
  return b.top.map(function(x){return row({r:x.r,h:x.h,loc:x.loc},"/wire/"+x.id)}).join("")+src("Top-ranked in the brief"+(nx?" · next issue "+etTime(nx):""))}
};
var busy=false;
function load(){if(busy||d.hidden)return;busy=true;
 fetch("/api/intro/live",{headers:{Accept:"application/json"},cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(j){busy=false;if(!j)return;
  Object.keys(R).forEach(function(k){var el=d.querySelector('.sx-d[data-d="'+k+'"]'),lv=d.querySelector('.sx-live[data-live="'+k+'"]');if(!el)return;var h="";try{h=R[k](j[k])}catch(e){h=""}
   if(h){if(el.innerHTML!==h)el.innerHTML=h;el.hidden=false;if(lv)lv.hidden=false}else{el.hidden=true;if(lv)lv.hidden=true}})}).catch(function(){busy=false})}
var idle=window.requestIdleCallback||function(f){return setTimeout(f,400)};
if(d.readyState==="complete")idle(load);else window.addEventListener("load",function(){idle(load)});
setInterval(load,60000);d.addEventListener("visibilitychange",function(){if(!d.hidden)load()});
})();
