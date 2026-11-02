/* BLACKOUT.NETWORK easter eggs (t347). Discreet, on-brand, no layout shift (fixed-position only), no network calls, no tracking,
   prefers-reduced-motion respected, never while typing, never on top of the sidebar, dialogs or alerts.
   1. Konami code (up up down down left right left right B A): the 10-segment meter sweeps to "all clear" with a short note.
   2. Seven quick clicks on the small BN tile at the start of the page footer: a hidden "Signal over noise." card.
   3. Developers: a short greeting in the browser console.
   4. The 404 page: about 1 visit in 20 shows a quiet extra line.
   5. Seasonal: on New Year's Day and on the solstice/equinox days the tri-color rule under the top bar shimmers once. */
(function(){if(window.__bnEggs)return;window.__bnEggs=1;
 var RM=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,d=document;
 function css(){if(d.getElementById("bn-eggs-css"))return;var s=d.createElement("style");s.id="bn-eggs-css";s.textContent=
  ".bn-egg{position:fixed;right:max(12px,env(safe-area-inset-right));bottom:max(60px,calc(env(safe-area-inset-bottom) + 60px));z-index:2400;max-width:min(320px,calc(100vw - 24px));"+
  "background:var(--bn-surface,#14181D);color:var(--bn-text,#E6E9EE);border:1px solid var(--bn-line,#252B33);border-radius:12px;padding:14px 16px;box-shadow:var(--bn-shadow,0 12px 40px rgba(0,0,0,.5));"+
  "font:500 14px/1.4 var(--bn-font-body,Inter,system-ui,sans-serif);text-align:left;opacity:0;transform:translateY(6px);transition:opacity .25s,transform .25s}"+
  ".bn-egg.on{opacity:1;transform:none}.bn-egg b{font:800 16px/1.2 var(--bn-font-ui,Montserrat,system-ui,sans-serif);letter-spacing:-.01em;display:block;margin-bottom:6px}"+
  ".bn-egg .m{display:flex;gap:3px;margin:2px 0 8px}.bn-egg .m i{width:12px;height:18px;border-radius:2px;background:var(--bn-seg-off,#252B33);transition:background .12s}"+
  ".bn-egg .x{position:absolute;top:6px;right:6px;width:32px;height:32px;border:0;background:none;color:var(--bn-muted,#8B95A3);font-size:18px;cursor:pointer;border-radius:8px}"+
  ".bn-egg .x:focus-visible{outline:2px solid var(--bn-brand,#FF4D4F)}"+
  ".bn-ftile{display:inline-block;width:14px;height:14px;vertical-align:-2px;margin-right:6px;cursor:default;-webkit-tap-highlight-color:transparent}"+
  "@keyframes bnShimmer{0%{filter:none}50%{filter:brightness(1.6) saturate(1.3)}100%{filter:none}}"+
  "html.bn-shimmer body header.bn-top::after{animation:bnShimmer 2.4s ease-in-out 1}"+
  "@media (prefers-reduced-motion: reduce){.bn-egg{transition:none}.bn-egg .m i{transition:none}html.bn-shimmer body header.bn-top::after{animation:none}}";d.head.appendChild(s)}
 function busy(){return d.querySelector(".bn-drawer.bn-open,.bnr-back:not([hidden]),[role=dialog][open],dialog[open]")||/INPUT|TEXTAREA|SELECT/.test((d.activeElement||{}).tagName||"")||(d.activeElement&&d.activeElement.isContentEditable)}
 var cur=null;function card(html,ms){css();if(cur)cur.remove();var c=d.createElement("div");c.className="bn-egg";c.setAttribute("role","status");c.setAttribute("aria-live","polite");
  c.innerHTML=html+'<button class="x" type="button" aria-label="Close">\u00d7</button>';d.body.appendChild(c);cur=c;
  var close=function(){c.classList.remove("on");setTimeout(function(){c.remove()},RM?0:260);if(cur===c)cur=null;d.removeEventListener("keydown",esc)};
  var esc=function(e){if(e.key==="Escape")close()};d.addEventListener("keydown",esc);c.querySelector(".x").onclick=close;
  requestAnimationFrame(function(){c.classList.add("on")});if(ms)setTimeout(close,ms);return c}
 // 1. Konami code -> meter sweeps to "all clear"
 var K=["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"],k=0;
 d.addEventListener("keydown",function(e){var key=e.key&&e.key.length===1?e.key.toLowerCase():e.key;k=(key===K[k])?k+1:(key===K[0]?1:0);if(k<K.length)return;k=0;if(busy())return;
  var c=card('<div class="m" aria-hidden="true">'+"<i></i>".repeat(10)+'</div><b>All clear.</b>For about one second, anyway. Signal over noise.',6000),seg=c.querySelectorAll(".m i");
  var col=function(i){return i<3?"var(--bn-sev-lo,#2BB673)":i<6?"var(--bn-sev-md,#F5A524)":"var(--bn-sev-hi,#FF4D4F)"};
  if(RM){seg.forEach(function(s){s.style.background="var(--bn-sev-lo,#2BB673)"});return}
  seg.forEach(function(s,i){setTimeout(function(){s.style.background=col(i)},90*i)});
  setTimeout(function(){seg.forEach(function(s,i){setTimeout(function(){s.style.background="var(--bn-sev-lo,#2BB673)"},60*(9-i))})},1200)});
 // 2. seven quick clicks on the footer BN tile -> hidden card
 function tile(){var f=d.querySelector("#site_foot,body>footer,footer.ft");if(!f||f.querySelector(".bn-ftile"))return;css();
  var t=d.createElementNS("http://www.w3.org/2000/svg","svg");t.setAttribute("class","bn-ftile");t.setAttribute("aria-hidden","true");
  t.setAttribute("viewBox","0 0 16 16");t.innerHTML='<rect width="16" height="16" rx="3" fill="#0B0D10"/><path fill="#FFFFFF" d="M3 4h3v1h-3zM8 4h3v1h-3zM13 4h2v1h-2zM5 5h2v1h-2zM8 5h3v1h-3zM13 5h2v1h-2zM5 6h2v1h-2zM8 6h4v1h-4zM13 6h2v1h-2zM3 7h3v1h-3zM8 7h2v1h-2zM11 7h1v1h-1zM13 7h2v1h-2zM5 8h2v1h-2zM8 8h2v1h-2zM11 8h1v1h-1zM13 8h2v1h-2zM5 9h2v1h-2zM8 9h2v1h-2zM11 9h4v1h-4zM5 10h2v1h-2zM8 10h2v1h-2zM12 10h3v1h-3zM3 11h3v1h-3zM8 11h2v1h-2zM12 11h3v1h-3z"/><path fill="#C8102E" d="M1 4h2v1h-2zM1 5h2v1h-2z"/><path fill="#FFC21A" d="M1 7h2v1h-2zM1 8h2v1h-2z"/><path fill="#3FAE80" d="M1 10h2v1h-2zM1 11h2v1h-2z"/>';   // logo V2-final, 16 px pixel-fitted master
  f.insertBefore(t,f.firstChild);var n=0,tm=0;t.addEventListener("click",function(){n++;clearTimeout(tm);tm=setTimeout(function(){n=0},2500);if(n>=7){n=0;if(!busy())card("<b>Signal over noise.</b>Who says so? How do they know? What would change your mind? Every alert on this site links to its sources, so you can check.",12000)}})}
 // 3. console greeting
 try{console.log("%cBLACKOUT.NETWORK%c  Signal over noise.\nEvery rank is explained at "+location.origin+"/scoring \u2014 and every alert links to its sources.","font:800 14px Montserrat,system-ui,sans-serif;color:#FF4D4F","font:500 12px Inter,system-ui,sans-serif;color:inherit")}catch(e){}
 // 5. seasonal shimmer (one per day, once)
 function seasonal(){var t=new Date(),m=t.getMonth()+1,day=t.getDate(),key="bn_season_"+t.toISOString().slice(0,10);
  var hit=(m===1&&day===1)||(m===3&&day===20)||(m===6&&day===21)||(m===9&&day===22)||(m===12&&day===21);if(!hit||RM)return;
  try{if(localStorage.getItem(key))return;localStorage.setItem(key,"1")}catch(e){}css();d.documentElement.classList.add("bn-shimmer");setTimeout(function(){d.documentElement.classList.remove("bn-shimmer")},2600)}
 function go(){tile();seasonal();setTimeout(tile,4000)}
 if(d.readyState==="loading")d.addEventListener("DOMContentLoaded",go);else go()})();
