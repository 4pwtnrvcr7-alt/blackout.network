/* bn-snap: shared full-section snapping (BN_SNAP). Opt in: <main data-bn-snap> with full-screen children marked data-snap.
   One gesture = one section, eased (cubic in-out, 820 ms) with rAF window scrolling; wheel/trackpad momentum tails are ignored
   (gesture lock + 240 ms quiet gap), touch swipes and keys move one section. Sections taller than the screen and anything after
   the last data-snap section scroll freely so long content stays readable. prefers-reduced-motion: instant jumps. */
(function(){
var d=document,W=window,root=d.querySelector("[data-bn-snap]");if(!root||W.BNSnap)return;
var secs=[].slice.call(root.querySelectorAll("[data-snap]"));if(secs.length<2&&!root.hasAttribute("data-snap-hero"))return;
var reduce=W.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,DUR=reduce?0:820,html=d.documentElement;
html.classList.add("bn-snap-js");
var anim=null,lastWheel=0,acc=0,tail=false,touch=null;
var offSel=root.getAttribute("data-snap-offset");function off(){var h=offSel&&d.querySelector(offSel);return h?h.offsetHeight:0}  /* sticky header height */
function live(){return root.offsetHeight>0&&!root.hidden}                                              /* hidden hero (other tab) = native scrolling */
function tops(){var y=W.scrollY||W.pageYOffset,o=off();return secs.map(function(s){return Math.max(0,Math.round(s.getBoundingClientRect().top+y-o))})}
function freeStart(){var s=secs[secs.length-1],r=s.getBoundingClientRect();return Math.round(r.bottom+(W.scrollY||0)-off())}
function vh(){return W.innerHeight-off()}
function ease(t){return t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2}
function menuOpen(){return !!d.querySelector("#bn-menu.bn-open,.h-menu.open,#w2_menu.open,.w2-menu.open")}
function to(y,cb){y=Math.max(0,Math.min(y,d.documentElement.scrollHeight-W.innerHeight));if(anim){cancelAnimationFrame(anim.id);d.documentElement.classList.remove("bn-snapping")}
 var y0=W.scrollY,dy=y-y0;if(!DUR||Math.abs(dy)<2){W.scrollTo(0,y);anim=null;cb&&cb();return}
 var t0=performance.now();anim={to:y};d.documentElement.classList.add("bn-snapping");
 (function step(now){var t=Math.min(1,(now-t0)/DUR);W.scrollTo(0,y0+dy*ease(t));if(t<1)anim.id=requestAnimationFrame(step);else{anim=null;lastWheel=performance.now();d.documentElement.classList.remove("bn-snapping");W.dispatchEvent(new Event("bnsnap:end"));cb&&cb()}})(t0)}
/* where are we: index of the section whose top is nearest at or above the viewport top (+ tolerance) */
function state(){var y=W.scrollY,T=tops(),i=0;for(var k=0;k<T.length;k++)if(T[k]<=y+4)i=k;
 var top=T[i],h=secs[i].offsetHeight,inner=h>vh()+4;return {y:y,T:T,i:i,top:top,bottom:top+h,inner:inner,free:y>=freeStart()-4&&y>top+4&&i===T.length-1}}
/* returns true when the gesture was handled (snap), false = let the browser scroll natively */
function move(dir){var s=state(),T=s.T;
 if(dir>0){
  if(s.inner&&s.y+vh()<s.bottom-4)return false;           /* inside a tall section: read on */
  if(s.i<T.length-1){to(T[s.i+1]);return true}
  var fs=freeStart();if(s.y<fs-4){to(fs);return true}         /* last section -> start of the free-scroll area */
  return false}
 if(s.y>=freeStart()-4&&s.y>s.top+4){                         /* in the free area below the last section */
  if(s.y<=freeStart()+4){to(T[T.length-1]+(s.inner?Math.max(0,secs[T.length-1].offsetHeight-vh()):0));return true}
  return false}
 if(s.inner&&s.y>s.top+4){return false}                        /* inside a tall section: read back up */
 if(s.y>s.top+4){to(s.top);return true}
 if(s.i>0){var p=s.i-1,ph=secs[p].offsetHeight;to(T[p]+(ph>vh()+4?ph-vh():0));return true}
 return false}
function inSnapZone(){return (W.scrollY||0)<freeStart()+4}
W.addEventListener("wheel",function(e){if(e.ctrlKey||!live())return;if(menuOpen()){var m=e.target.closest&&e.target.closest("#bn-menu,.h-menu,#w2_menu,.w2-menu");if(!m||(e.deltaY>0?m.scrollTop+m.clientHeight>=m.scrollHeight-1:m.scrollTop<=0))e.preventDefault();return}var now=performance.now(),gap=now-lastWheel;lastWheel=now;
 if(Math.abs(e.deltaX)>Math.abs(e.deltaY))return;
 if(anim){e.preventDefault();return}                           /* locked during the transition */
 if(tail){if(gap<240){e.preventDefault();return}tail=false}       /* momentum tail of a snap: swallowed, even where native scroll would apply */
 var dir=e.deltaY>0?1:-1,s=state();
 var wouldSnap=(dir>0&&(!s.inner||s.y+vh()>=s.bottom-4)&&s.y<freeStart()-4)||(dir<0&&(s.y<=freeStart()+4)&&!(s.inner&&s.y>s.top+4));
 if(!wouldSnap)return;                                          /* native scroll in tall sections / free area */
 e.preventDefault();
 if(gap>240)acc=0;acc+=e.deltaY*(e.deltaMode===1?33:1);if(Math.abs(acc)<24)return;
 acc=0;if(move(dir))tail=true},{passive:false});
W.addEventListener("touchstart",function(e){if(menuOpen()||e.touches.length!==1||!live())return;touch={y:e.touches[0].clientY,t:performance.now(),y0:W.scrollY}},{passive:true});
W.addEventListener("touchmove",function(e){if(!touch)return;if(anim){e.preventDefault();return}var dy=touch.y-e.touches[0].clientY,s=state(),dir=dy>0?1:-1;
 var wouldSnap=(dir>0&&(!s.inner||s.y+vh()>=s.bottom-4)&&s.y<freeStart()-4)||(dir<0&&s.y<=freeStart()+4&&!(s.inner&&s.y>s.top+4));
 if(wouldSnap){e.preventDefault();touch.snap=true}},{passive:false});
W.addEventListener("touchend",function(e){if(!touch)return;var t=touch;touch=null;if(!t.snap||anim)return;var dy=t.y-(e.changedTouches[0]||{}).clientY,dt=performance.now()-t.t;
 if(Math.abs(dy)>40||(Math.abs(dy)>24&&dt<220))move(dy>0?1:-1)},{passive:true});
d.addEventListener("keydown",function(e){if(!live()||menuOpen()||e.altKey||e.ctrlKey||e.metaKey)return;var a=d.activeElement,tg=a&&a.tagName;
 if(tg==="INPUT"||tg==="TEXTAREA"||tg==="SELECT"||(a&&a.isContentEditable))return;
 var k=e.key,dir=(k==="ArrowDown"||k==="PageDown"||(k===" "&&!e.shiftKey))?1:(k==="ArrowUp"||k==="PageUp"||(k===" "&&e.shiftKey))?-1:0;
 if(k==="Home"&&inSnapZone()){e.preventDefault();to(0);return}
 if(!dir||anim&&(e.preventDefault(),true))return;if(!inSnapZone()&&dir>0)return;if(move(dir))e.preventDefault()});
/* after a resize/rotation, settle on the nearest section */
var rt;W.addEventListener("resize",function(){clearTimeout(rt);rt=setTimeout(function(){if(anim||!live()||!inSnapZone())return;var s=state();if(!s.inner&&Math.abs(s.y-s.top)>2)W.scrollTo(0,s.top)},180)});
d.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;var id=a.getAttribute("href").slice(1),t=id&&d.getElementById(id);
 var i=secs.indexOf(t);if(i<0)return;e.preventDefault();var T=tops();to(T[i]);if(history.replaceState)history.replaceState(null,"","#"+id)});
W.BNSnap={go:function(i){var T=tops();if(T[i]!=null)to(T[i])},to:to,duration:DUR};
})();
