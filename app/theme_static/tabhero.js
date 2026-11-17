/* Latest tab heroes (BN_TAB_HERO). /live#streams|noise|heatmap|trends|broadcasts|radio get a full-screen header: looping, silent
   NASA video on desktop/tablet, the still image on phones, with prefers-reduced-motion or Save-Data. The tab's own page head
   (h1 + one line) moves into the hero and goes back when another tab opens. Snapping comes from snap.js (data-snap-hero). */
(function(){
var d=document,W=window,H=d.getElementById("bn_th"),M=W.BN_TAB_HEROES||{};if(!H)return;
var bg=H.querySelector(".bn-th-bg"),src=bg.querySelector("source"),img=bg.querySelector("img"),v=bg.querySelector("video"),box=H.querySelector(".bn-th-c");
var head=d.querySelector(".bn-pagehead"),mark=d.createComment("bn-pagehead"),cur=null,n=navigator.connection||{};
function mm(q){return W.matchMedia&&matchMedia(q).matches}
function motionOK(){return innerWidth>700&&!mm("(prefers-reduced-motion: reduce)")&&!n.saveData}
function hdr(){var h=d.querySelector("header.bn-top");d.documentElement.style.setProperty("--bn-th-hdr",(h?h.offsetHeight:0)+"px")}
function stop(){v.pause();v.classList.remove("on");while(v.firstChild)v.removeChild(v.firstChild);v.removeAttribute("src");try{v.load()}catch(e){}}
function play(k){stop();if(!motionOK())return;
 [["webm","video/webm"],["mp4","video/mp4"]].forEach(function(a){var s=d.createElement("source");s.src="/bnt/media/"+k+"vid-d."+a[0]+"?v=1";s.type=a[1];v.appendChild(s)});
 v.muted=true;v.autoplay=true;v.preload="auto";v.addEventListener("playing",function on(){v.removeEventListener("playing",on);if(cur===k)v.classList.add("on")});
 v.load();var p=v.play();if(p&&p.catch)p.catch(function(){})}
function show(k){if(cur===k)return;cur=k;hdr();
 src.srcset="/bnt/media/"+k+"hero-m.jpg?v=1";img.src="/bnt/media/"+k+"vid-d.jpg?v=1";
 if(head&&head.parentNode!==box){head.parentNode.insertBefore(mark,head);box.appendChild(head)}
 H.hidden=false;d.documentElement.classList.add("bn-th-on");play(k)}
function hide(){if(cur===null&&H.hidden)return;cur=null;stop();H.hidden=true;d.documentElement.classList.remove("bn-th-on");
 if(head&&mark.parentNode){mark.parentNode.insertBefore(head,mark);mark.parentNode.removeChild(mark)}}
var TT=W.BN_TAB_HERO_TITLES||{},orig=null,ours=null;
function title(h){var e=d.getElementById("bn_ptitle");if(!e)return;var want=TT[h];
 if(want){if(e.textContent!==want){if(e.textContent!==ours)orig=e.textContent;e.textContent=want;ours=want}}
 else if(ours&&e.textContent===ours&&orig!=null){e.textContent=orig;ours=null}}
function sync(){var h=location.hash.slice(1).split(/[/?]/)[0],k=M[h];if(k)show(k);else hide();title(k?h:"")}
var t;function later(){clearTimeout(t);t=setTimeout(sync,0)}
addEventListener("hashchange",later);
/* tab buttons switch with history.replaceState (no hashchange): follow the page title instead */
var ttl=d.getElementById("bn_ptitle");if(ttl&&W.MutationObserver)new MutationObserver(later).observe(ttl,{childList:true,characterData:true,subtree:true});
d.addEventListener("click",function(e){if(e.target.closest&&e.target.closest("button[data-tab],a[href*='#']"))setTimeout(sync,60)},true);
addEventListener("resize",hdr);
H.querySelector(".bn-th-cue").addEventListener("click",function(e){var end=d.getElementById("bn_th_end");if(!end)return;e.preventDefault();
 var hh=(d.querySelector("header.bn-top")||{}).offsetHeight||0,y=Math.round(end.getBoundingClientRect().top+scrollY-hh);
 if(W.BNSnap&&BNSnap.to)BNSnap.to(y);else scrollTo(0,y)});
/* off-screen or background tab: pause the loop */
if(W.IntersectionObserver)new IntersectionObserver(function(es){es.forEach(function(e){if(!cur||!v.firstChild)return;if(e.isIntersecting){var p=v.play();if(p&&p.catch)p.catch(function(){})}else v.pause()})}).observe(H);
d.addEventListener("visibilitychange",function(){if(!cur||!v.firstChild)return;if(d.hidden)v.pause();else{var p=v.play();if(p&&p.catch)p.catch(function(){})}});
sync();setTimeout(sync,350);
})();
