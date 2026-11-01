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
