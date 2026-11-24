/* BLACKOUT.NETWORK link guard (t338). The nightly link checker (tools/linkcheck.py) flags links that are dead two nights running;
   this hides them on every page and in lists rendered later (MutationObserver). Nothing is deleted: the data keeps the link with a
   'dead' flag, and it comes back as soon as a check finds it working again. A list row that is only the link is hidden; a link inside
   other text is turned back into plain text. */
(function(){if(window.__bnLinkGuard)return;window.__bnLinkGuard=1;var D=null,K="bn_dead_v1";
 function norm(h){try{var u=new URL(h,location.href);if(!/^https?:$/.test(u.protocol))return null;return u.protocol+"//"+u.host.toLowerCase()+(u.pathname||"/")+u.search}catch(e){return null}}
 function apply(root){if(!D||!D.size)return;var as=(root||document).querySelectorAll?(root||document).querySelectorAll('a[href^="http"]:not([data-bn-dead])'):[];
  for(var i=0;i<as.length;i++){var a=as[i],n=norm(a.getAttribute("href"));if(!n||!D.has(n))continue;a.setAttribute("data-bn-dead","1");
   var row=a.closest("li,tr,.card,[role=listitem]"),t=(a.textContent||"").trim();
   if(row&&row.querySelectorAll("a[href]").length===1&&(row.textContent||"").trim().length<=t.length+40){row.hidden=true;row.setAttribute("data-bn-dead-row","1")}
   else{var s=document.createElement("span");s.className="bn-dead-link";s.textContent=a.textContent;s.title="This link is offline";a.replaceWith(s)}}}
 function start(list){D=new Set(list||[]);if(!D.size)return;apply(document);var tm=0;
  new MutationObserver(function(ms){clearTimeout(tm);tm=setTimeout(function(){apply(document)},250)}).observe(document.body,{childList:true,subtree:true})}
 function go(){try{var c=JSON.parse(sessionStorage.getItem(K)||"null");if(c&&Date.now()-c.t<36e5){start(c.u);return}}catch(e){}
  fetch("/api/linkcheck/dead").then(function(r){return r.ok?r.json():null}).then(function(j){if(!j)return;try{sessionStorage.setItem(K,JSON.stringify({t:Date.now(),u:j.urls||[]}))}catch(e){}start(j.urls)}).catch(function(){})}
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",go);else go()})();
/* Deactivated pages (Nov 24 2026, Matt): links to a page in deactivated.py (window.BN_OFF, set in <head> by server.py) are removed
   on every page, including lists rendered later. A row/card that is only that link is hidden; a link inside other text becomes plain
   text. "off" pages 302 to "/"; "unlisted" pages still serve and keep links to themselves. Reactivate: remove the page from deactivated.py. */
(function(){if(window.__bnOffGuard)return;window.__bnOffGuard=1;var O=window.BN_OFF;if(!O||!O.on||!O.prefixes||!O.prefixes.length)return;
 var H={};(O.hashes||[]).forEach(function(h){H[h]=1});
 function inp(p,xs){for(var i=0;i<xs.length;i++){var x=xs[i];if(p===x||p.indexOf(x+"/")===0)return true}return false}
 var here=(location.pathname||"/").toLowerCase().replace(/\/+$/,"")||"/",own=[];(O.groups||[]).forEach(function(g){if(inp(here,g))own=g});   /* an "unlisted" page keeps links to itself */
 function off(href){try{var u=new URL(href,location.href);if(!/^https?:$/.test(u.protocol))return false;
   if(u.host!==location.host&&!/^(www\.)?blackout\.network$/i.test(u.hostname))return false;
   var p=(u.pathname||"/").toLowerCase().replace(/\/+$/,"")||"/";if(own.length&&inp(p,own))return false;
   for(var i=0;i<O.prefixes.length;i++){var x=O.prefixes[i];if(p===x||p.indexOf(x+"/")===0)return true}
   return (p==="/"||p==="/index.html")&&!!H[(u.hash||"").slice(1).toLowerCase()]}catch(e){return false}}
 function apply(root){var as=(root||document).querySelectorAll('a[href]:not([data-bn-off])');
  for(var i=0;i<as.length;i++){var a=as[i];if(!off(a.getAttribute("href")))continue;a.setAttribute("data-bn-off","1");
   var card=a.closest(".bnt-card,.h-chip,.m3-p"),row=card||a.closest("li,tr,.card,[role=listitem]"),t=(a.textContent||"").trim();
   if(row&&row.querySelectorAll("a[href]").length===1&&(card||(row.textContent||"").trim().length<=t.length+40)){row.hidden=true;row.style.display="none";row.setAttribute("data-bn-off-row","1")}
   else if(a.classList.contains("bnt-btn")||a.classList.contains("w2-btn")||/btn|button|cta/.test(a.className||"")){a.hidden=true;a.style.display="none"}
   else{var s=document.createElement("span");s.className="bn-off-link";s.innerHTML=a.innerHTML;a.replaceWith(s)}}}
 function go(){apply(document);var tm=0;new MutationObserver(function(){if(tm)return;tm=setTimeout(function(){tm=0;apply(document)},200)}).observe(document.body,{childList:true,subtree:true})}   /* throttle, not debounce: pages that re-render all the time (/network) still get checked */
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",go);else go()})();
