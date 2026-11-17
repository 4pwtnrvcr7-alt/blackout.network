/* BLACKOUT.NETWORK shared theme behaviour (bnt-*): accordions, hover/tap/keyboard peek panels, tabs, "more" expanders,
   and the /live hash bridge (old "/#tab" links land on "/live#tab" without a detour through the intro). */
(function(){
if(window.BNT)return;window.BNT={};
var d=document,reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
/* 1. hash bridge: "/" is now the intro; dashboard tabs live on /live */
function bridge(a){try{if(!a||!a.getAttribute)return;var h=a.getAttribute("href")||"";if(!/^(https?:\/\/(www\.)?blackout\.network)?\/(index\.html)?(\?[^#]*)?#[^_]/.test(h))return;
 var u=new URL(h,location.href);if(u.origin!==location.origin&&!/blackout\.network$/.test(u.hostname))return;if(u.hash==="#bn-menu")return;
 a.setAttribute("href","/live"+u.search+u.hash)}catch(e){}}
["pointerdown","click","keydown","focusin"].forEach(function(t){d.addEventListener(t,function(e){var a=e.target&&e.target.closest&&e.target.closest("a[href]");if(a)bridge(a)},true)});
/* 2. accordions */
function accToggle(h,open){var b=d.getElementById(h.getAttribute("aria-controls"))||h.nextElementSibling;if(!b)return;
 if(open===undefined)open=h.getAttribute("aria-expanded")!=="true";h.setAttribute("aria-expanded",open?"true":"false");
 if(reduce){b.hidden=!open;b.style.height="";return}
 if(open){b.hidden=false;var full=b.scrollHeight;b.style.height="0px";requestAnimationFrame(function(){b.style.height=full+"px"});b.addEventListener("transitionend",function f(){b.style.height="";b.removeEventListener("transitionend",f)})}
 else{b.style.height=b.scrollHeight+"px";requestAnimationFrame(function(){b.style.height="0px"});b.addEventListener("transitionend",function f(){b.hidden=true;b.style.height="";b.removeEventListener("transitionend",f)})}}
d.addEventListener("click",function(e){var h=e.target.closest&&e.target.closest(".bnt-acc-h");if(h){e.preventDefault();accToggle(h)}});
BNT.acc=accToggle;
/* 3. peek panels: hover on mouse, tap on touch, focus on keyboard; fold away when you move on */
var touch=false;d.addEventListener("touchstart",function(){touch=true},{passive:true,capture:true});
function setPeek(p,on){if(!p)return;p.classList.toggle("open",on);p.setAttribute("aria-expanded",on?"true":"false")}
d.addEventListener("mouseover",function(e){if(touch)return;var p=e.target.closest&&e.target.closest(".bnt-peek");if(p)setPeek(p,true)});
d.addEventListener("mouseout",function(e){if(touch)return;var p=e.target.closest&&e.target.closest(".bnt-peek");if(p&&!p.contains(e.relatedTarget))setPeek(p,false)});
d.addEventListener("focusin",function(e){var p=e.target.closest&&e.target.closest(".bnt-peek");if(p&&!p.classList.contains("open")){p._bt=Date.now();setPeek(p,true)}});
d.addEventListener("focusout",function(e){var p=e.target.closest&&e.target.closest(".bnt-peek");if(p&&!p.contains(e.relatedTarget))setPeek(p,false)});
d.addEventListener("click",function(e){var p=e.target.closest&&e.target.closest(".bnt-peek");
 [].forEach.call(d.querySelectorAll(".bnt-peek.open"),function(o){if(o!==p&&touch)setPeek(o,false)});
 if(p&&touch&&!e.target.closest("a,button,input,select,textarea")){if(p._bt&&Date.now()-p._bt<600){p._bt=0;return}setPeek(p,!p.classList.contains("open"))}});
d.addEventListener("keydown",function(e){if(e.key==="Escape")[].forEach.call(d.querySelectorAll(".bnt-peek.open"),function(o){setPeek(o,false)});
 var p=e.target.classList&&e.target.classList.contains("bnt-peek")?e.target:null;if(p&&(e.key==="Enter"||e.key===" ")&&e.target===p){e.preventDefault();setPeek(p,!p.classList.contains("open"))}});
/* 4. tabs */
d.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest(".bnt-tabs [role=tab]");if(!t)return;var l=t.closest("[role=tablist]");
 [].forEach.call(l.querySelectorAll("[role=tab]"),function(x){var on=x===t;x.setAttribute("aria-selected",on?"true":"false");x.tabIndex=on?0:-1;var pn=d.getElementById(x.getAttribute("aria-controls"));if(pn)pn.hidden=!on})});
d.addEventListener("keydown",function(e){var t=e.target.closest&&e.target.closest(".bnt-tabs [role=tab]");if(!t||(e.key!=="ArrowRight"&&e.key!=="ArrowLeft"))return;
 var ts=[].slice.call(t.closest("[role=tablist]").querySelectorAll("[role=tab]")),i=ts.indexOf(t)+(e.key==="ArrowRight"?1:-1);i=(i+ts.length)%ts.length;ts[i].focus();ts[i].click()});
/* 5. more expanders */
d.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest(".bnt-more-t");if(!t)return;var m=t.closest(".bnt-more");var o=!m.classList.contains("open");m.classList.toggle("open",o);t.setAttribute("aria-expanded",o?"true":"false");t.textContent=o?(t.dataset.less||"Show less"):(t.dataset.more||"Read more")});
/* 6. per-module refresh stamps (Matt Nov 17 1:10 AM): "Updated 1:12 AM ET · next in 4m" + a small refresh button that reloads only that module.
   BNT.up(el, {label, at: ms, next: ms, run: function(){return Promise}}) ; call again with new at/next after each load. */
var UPS=[],ETF=null;try{ETF=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"})}catch(e){}
var RF='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.8 4.2v4.6h-4.6"/></svg>';
function upText(u){var o=u.o,t=o.at?(ETF?ETF.format(new Date(o.at)):new Date(o.at).toLocaleTimeString())+" ET":"",x="";
 if(o.next){var m=Math.round((o.next-Date.now())/60000);x=m>=1?" \u00b7 next in "+m+"m":" \u00b7 next any moment"}
 return (t?"Updated "+t:"Updating\u2026")+x}
function upPaint(u){var t=u.el.querySelector(".bnt-up-t");if(t)t.textContent=upText(u)}
BNT.up=function(el,o){if(!el)return;var u=null;for(var i=0;i<UPS.length;i++)if(UPS[i].el===el)u=UPS[i];
 if(!u){u={el:el,o:{}};UPS.push(u);el.classList.add("bnt-up");
  el.innerHTML='<button type="button" class="bnt-rf" aria-label="Refresh '+(o.label||"this module")+'" title="Refresh '+(o.label||"")+'">'+RF+'</button><span class="bnt-up-t" aria-live="polite"></span>';
  el.querySelector(".bnt-rf").addEventListener("click",function(e){e.preventDefault();e.stopPropagation();var b=e.currentTarget;if(b.getAttribute("aria-busy")==="true"||!u.o.run)return;
   b.setAttribute("aria-busy","true");b.classList.add("spin");var done=function(){b.setAttribute("aria-busy","false");b.classList.remove("spin")};
   try{Promise.resolve(u.o.run()).then(done,done)}catch(x){done()}})}
 for(var k in o)u.o[k]=o[k];upPaint(u)};
setInterval(function(){UPS.forEach(upPaint)},15000);
})();

/* Nov 17: very subtle GPU parallax for a few hero backdrops. Opt in with data-bn-par="0.12".
   transform only, one rAF per frame, passive listener, off under reduced motion, only while on screen. */
(function(){try{
 if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)return;
 var els=[].slice.call(document.querySelectorAll("[data-bn-par]"));if(!els.length)return;
 var vis=new Set(),tick=false;
 function frame(){tick=false;var y=window.pageYOffset;vis.forEach(function(e){var f=parseFloat(e.getAttribute("data-bn-par"))||.1;
  e.style.transform="translate3d(0,"+Math.min(y*f,160).toFixed(1)+"px,0)"})}
 function req(){if(!tick&&vis.size){tick=true;requestAnimationFrame(frame)}}
 if("IntersectionObserver"in window){var io=new IntersectionObserver(function(es){es.forEach(function(x){x.isIntersecting?vis.add(x.target):vis.delete(x.target)});req()});els.forEach(function(e){io.observe(e)})}else els.forEach(function(e){vis.add(e)});
 window.addEventListener("scroll",req,{passive:true});req();
}catch(x){}})();

/* Nov 17 push B (Matt 2:37 AM "Simplify"): on the remaining pages, headings lose emoji and trailing explanations,
   long intro copy goes behind one "More" expander and long tables show 6 rows with "Show all". Content is moved, never removed. */
(function(){try{
 var EMO=/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{2300}-\u{23FF}\u{FE0F}\u{200D}]\s*/gu;
 function skip(el){return !el||el.closest(".bnt-live,.bn-wire,.bnt-home,.bnm,form,[data-bnt-skip],svg,.bn-top")}
 function hd(h){if(skip(h))return;if(h.dataset.bntH){EMO.lastIndex=0;if(!EMO.test(h.textContent))return;EMO.lastIndex=0}for(var n=h.firstChild;n;n=n.nextSibling){if(n.nodeType!==3)continue;var t=n.nodeValue,u=t.replace(EMO,"");
   if(!h.dataset.bntH&&/^(H1|H2)$/.test(h.tagName)){var m=u.match(/^(\s*[^:—–]{2,48}?)\s*(?::|\s[—–]\s)\s*(.{8,})$/);if(m&&m[1].trim().split(/\s+/).length<=5){u=m[1];if(!h.title)h.title=m[2].trim()}}
   if(u!==t)n.nodeValue=u;break}h.dataset.bntH=1}
 function tabs(){document.querySelectorAll(".tabs button,.bn-side a,.m3-list a").forEach(function(b){for(var n=b.firstChild;n;n=n.nextSibling){if(n.nodeType===3&&EMO.test(n.nodeValue)){EMO.lastIndex=0;n.nodeValue=n.nodeValue.replace(EMO,"")}EMO.lastIndex=0}})}
 function plain(p){return p.tagName==="P"&&!p.id&&!p.querySelector("[id],input,button,select,textarea,img,video,iframe")}
 function intro(box){if(skip(box)||box.dataset.bntI)return;box.dataset.bntI=1;var ps=[].filter.call(box.children,plain);if(!ps.length)return;
   var txt=ps.map(function(p){return p.textContent}).join(" ").trim();if(txt.length<160)return;
   var keep=ps[0].textContent.trim().length<=110?ps.shift():null;if(!ps.length)return;
   var d=document.createElement("details");d.className="bnt-more";d.innerHTML="<summary>More</summary>";ps[0].parentNode.insertBefore(d,ps[0]);ps.forEach(function(p){d.appendChild(p)})}
 function tables(){document.querySelectorAll("main table").forEach(function(t){if(skip(t)||t.dataset.bntT)return;var b=t.tBodies[0];if(!b||b.rows.length<=8)return;t.dataset.bntT=1;t.classList.add("bnt-fold");
   var x=document.createElement("button");x.type="button";x.className="bnt-foldb";var lab=function(){x.textContent=t.classList.contains("bnt-open")?"Show fewer":"Show all "+t.tBodies[0].rows.length};lab();
   x.addEventListener("click",function(){t.classList.toggle("bnt-open");lab()});(t.closest(".tbl-wrap,.table-wrap")||t).insertAdjacentElement("afterend",x)})}
 function lead(){document.querySelectorAll("body:not(.bnt-home):not(.bnm) h1 + p").forEach(function(p){if(!skip(p)&&p.textContent.trim().length>90)p.classList.add("bnt-lead")})}
 var LEGAL=/^\/(terms|tos|privacy|cookies|privacy-choices)\b/.test(location.pathname);
 function clampLong(){if(LEGAL)return;document.querySelectorAll("p").forEach(function(p){if(p.dataset.bntC||skip(p)||p.closest("details,.bnt-lead"))return;p.dataset.bntC=1;
   if(plain(p)&&p.textContent.trim().length>260){p.classList.add("bnt-clamp");p.title="Tap to read more"}})}
 function run(){lead();clampLong();document.querySelectorAll("main h1,main h2,main h3,.np-wrap h2,.bn-page h2,h1").forEach(hd);tabs();
   document.querySelectorAll("main .pn,main[id^='tab-']>section,main section,main article,body>section,body>article,[class*='wrap']>section,[class*='wrap']>article,.np-wrap section,.bn-page section").forEach(intro);tables()}
 var Y=/^rgba?\(255, ?194, ?26/;
 function deyellow(){if(document.body.classList.contains("bnt-home"))return;var els=document.querySelectorAll("body *:not(svg *):not(script):not(style)"),n=0;
   for(var i=0;i<els.length&&n<4000;i++){var e=els[i];if(e.closest(".bnt-live,.bn-wire,.bnm"))continue;n++;var c=getComputedStyle(e);
     if(Y.test(c.color))e.style.setProperty("color","#F2F2F4","important");
     if(Y.test(c.backgroundColor)){e.style.setProperty("background-color","transparent","important");e.style.setProperty("color","#F2F2F4","important");e.style.setProperty("border","1px solid rgba(242,242,244,.85)","important")}
     if(/^(A|BUTTON)$/.test(e.tagName)&&e.textContent.trim().length>12){var m=c.backgroundColor.match(/^rgba?\((\d+), ?(\d+), ?(\d+)/);if(m&&+m[1]>170&&+m[2]<90&&+m[3]<90){e.style.setProperty("background-color","transparent","important");e.style.setProperty("color","#F2F2F4","important");e.style.setProperty("border","1px solid rgba(242,242,244,.85)","important");e.style.setProperty("border-radius","0","important")}}
     ["Top","Right","Bottom","Left"].forEach(function(k){if(Y.test(c["border"+k+"Color"])&&parseFloat(c["border"+k+"Width"])>0)e.style.setProperty("border-"+k.toLowerCase()+"-color","rgba(242,242,244,.25)","important")})}}
 var q=0;function soon(){if(q)return;q=setTimeout(function(){q=0;run()},400)}
 document.addEventListener("click",function(e){var d=e.target.closest&&e.target.closest(".bn-tabdesc,.bn-pagehead p,.bnt-lead,.bnt-clamp");if(d)d.classList.toggle("bnt-open")});
 var go=function(){run();setTimeout(deyellow,1200);setTimeout(deyellow,5000);try{new MutationObserver(soon).observe(document.body,{childList:true,subtree:true})}catch(e){}};
 if(document.readyState!=="loading")go();else document.addEventListener("DOMContentLoaded",go);
}catch(x){}})();
