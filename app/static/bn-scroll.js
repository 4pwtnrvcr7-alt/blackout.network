/* BLACKOUT.NETWORK scroll policy: a new page or dashboard tab starts at the top.
   Real in-page anchors (e.g. /tos#acknowledgments) still scroll to the element.
   The Back button restores the previous scroll position. Tab hashes on "/"
   (injected as TABS by sitenav.scroll_script) are not treated as element ids,
   even if a mid-page node happens to use the same id.
   history.scrollRestoration is manual because the browser otherwise reapplies
   the previous page's scrollY after a same-document tab hash change.
   Save the outgoing position on popstate in the capture phase: Chrome fires
   popstate for some hash updates, and bn-apple.js toggles .bna-home there,
   which would otherwise shrink the page and clamp scrollY before hashchange. */
(function(){if(window.bnScroll)return;window.bnScroll=1;
try{if("scrollRestoration" in history)history.scrollRestoration="manual"}catch(e){}
var TABS=/*BN_TABS*/{};
function norm(p,s,h){h=h||"";if(h==="#"||h==="#home"||h==="#bn-menu")h="";return p+s+h}
function keyLoc(){return norm(location.pathname,location.search,location.hash)}
function save(k){try{sessionStorage.setItem("bn_scroll:"+k,String(window.scrollY||0))}catch(e){}}
function restore(k){
  try{
    var v=sessionStorage.getItem("bn_scroll:"+k);
    if(v==null)return false;
    var y=parseInt(v,10)||0,user=false,n=0;
    function onUser(){user=true}
    addEventListener("wheel",onUser,{passive:true,once:true});
    addEventListener("touchstart",onUser,{passive:true,once:true});
    addEventListener("keydown",onUser,{passive:true,once:true});
    function apply(){if(!user)window.scrollTo(0,y)}
    apply();
    var iv=setInterval(function(){apply();if(++n>12||user)clearInterval(iv)},100);
    return true;
  }catch(e){return false}
}
function part(){var h=(location.hash||"").slice(1);if(!h)return"";try{return decodeURIComponent(h.split(/[/?]/)[0]).toLowerCase()}catch(e){return h.split(/[/?]/)[0].toLowerCase()}}
function go(){
  var p=part();
  if(p==="bn-menu")return;
  var onDash=location.pathname==="/"||location.pathname==="";
  if(!p||p==="home"||(onDash&&TABS[p])){window.scrollTo(0,0);return}
  var el=p&&document.getElementById(p);
  if(el){el.scrollIntoView({block:"start",behavior:"auto"});return}
  window.scrollTo(0,0);
}
var lastKey=keyLoc();
addEventListener("popstate",function(){
  var incoming=keyLoc();
  save(lastKey);
  lastKey=incoming;
  setTimeout(function(){if(!restore(incoming))go()},0);
},true);
addEventListener("hashchange",function(){
  var incoming=keyLoc();
  if(incoming===lastKey)return;
  save(lastKey);
  lastKey=incoming;
  setTimeout(go,0);
});
function arrive(){
  lastKey=keyLoc();
  var back=false;
  try{var n=performance.getEntriesByType("navigation")[0];back=n&&n.type==="back_forward"}catch(e){}
  if(back&&restore(lastKey))return;
  go();
}
if(document.readyState==="loading")addEventListener("DOMContentLoaded",arrive);else arrive();
addEventListener("pageshow",function(e){if(e.persisted){lastKey=keyLoc();if(!restore(lastKey))go()}});
addEventListener("pagehide",function(){save(keyLoc())});
})();
