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
})();
