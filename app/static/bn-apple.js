/* BLACKOUT.NETWORK apple_style_v1 phase 2: homepage data + row arrows. Same-origin only (/api/apple/home). Loaded only when BN_APPLE=1. */
/* Page groups (html.bna-pg): display-only tidy-ups, text nodes only, nothing removed from the DOM.
   - a panel title that repeats the page title is visually hidden (kept for screen readers);
   - the leading "— " of a panel description is trimmed;
   - unicode glyph icons at the start of headings and controls (e.g. the refresh arrow) are dropped, the label stays. */
(function(){
 var R=document.documentElement,GL=/^[\u2190-\u21FF\u2300-\u23FF\u2460-\u27FF\u2900-\u2BFF\u{1F000}-\u{1FAFF}]\uFE0F?\s*/u,t=0;
 function norm(x){return (x||"").replace(/\s+/g," ").trim().toLowerCase()}
 function lead(el,re){for(var n=el.firstChild;n;n=n.nextSibling){if(n.nodeType==3){if(!n.textContent.trim())continue;var v=n.textContent.replace(/^\s+/,"");if(re.test(v))n.textContent=v.replace(re,"");return}if(n.nodeType==1&&/^(SVG|IMG|I)$/i.test(n.tagName))continue;if(n.nodeType==1&&!n.children.length&&re.test(n.textContent.trim())&&n.textContent.trim().replace(re,"")==""){n.classList.add("bna-glyph");continue}return}}
 function scan(){t=0;if(!R.classList.contains("bna-pg"))return;
  var ph=[].filter.call(document.querySelectorAll(".bn-pagehead h1"),function(e){return e.offsetParent!==null})[0],pt=norm(ph?ph.textContent:"");
  var m=[].filter.call(document.querySelectorAll("body>main"),function(e){return e.offsetParent!==null||getComputedStyle(e).display!="none"});
  m.forEach(function(main){
   main.querySelectorAll(".pn>h2,.pn>h3,section>h2").forEach(function(h){lead(h,GL);var me=h.querySelector(".meta");if(me)lead(me,/^[\u2014\u2013-]\s*/);
    if(pt){var own=[].filter.call(h.childNodes,function(n){return n.nodeType==3}).map(function(n){return n.textContent}).join(" ");h.classList.toggle("bna-dup",norm(own)==pt)}});
   main.querySelectorAll("button,a.btn,.tab-ref,summary").forEach(function(b){lead(b,GL)});
   var f=main.querySelector(":scope>h1,:scope>h2,:scope>.title");if(f&&pt&&!f.classList.contains("bn-ptitle"))f.classList.toggle("bna-dup2",norm(f.textContent)==pt);
  })}
 function soon(){if(!t)t=setTimeout(scan,400)}
 addEventListener("hashchange",function(){setTimeout(scan,60)});
 if(document.readyState=="loading")addEventListener("DOMContentLoaded",scan);else scan();
 try{new MutationObserver(soon).observe(document.body||R,{childList:true,subtree:true})}catch(e){}
})();
(function(){
 var H=document.getElementById("bna_home"),R=document.documentElement;if(!H)return;
 function onHome(){var h=location.hash;return !h||h=="#"||h=="#home"}
 function sync(){R.classList.toggle("bna-home",onHome())}
 addEventListener("hashchange",sync);addEventListener("popstate",sync);sync();
 ["pushState","replaceState"].forEach(function(m){var o=history[m];if(!o)return;history[m]=function(){var r=o.apply(this,arguments);try{sync()}catch(e){}return r}});   // menu tab links change the hash via history (no hashchange event): keep the homepage/tab view in sync
 if(window.BNA){setTimeout(BNA.refresh,BNA.had?45000:0);setInterval(function(){if(!document.hidden)BNA.refresh()},120000)}
})();
/* Phase 3a: the bar keeps the wordmark, the theme icon and the menu button. The Wire, Sources, Free brief, alerts, search and
   settings live in the menu's top row (search, Alerts, theme, Settings and Free brief were already there; The Wire + Sources are added
   here). The header theme button is the same data-bn-theme control as the menu row. Network alerts move from the page banner
   (#ns_gbanner, hidden by CSS) into the menu, with a small dot on the menu button. */
(function(){
 var d=document;
 function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
 function txt(v){return v==null?"":typeof v=="string"||typeof v=="number"?String(v):Array.isArray(v)?v.map(txt).filter(Boolean).join(", "):typeof v=="object"?txt(v.src||v.name||v.label||v.title||v.status||""):""}
 function tools(){var t=d.querySelector("#bn-menu .m3-tools");if(!t||t.querySelector(".bna-mlinks"))return t;
  var w=d.createElement("span");w.className="bna-mlinks";w.innerHTML='<a class="m3-tl bna-ml" href="/#wire">The Wire</a><a class="m3-tl bna-ml" href="/sources">Sources</a>';
  t.insertBefore(w,t.firstChild);return t}
 function alerts(a){if(a&&a.data&&a.count==null)a=a.data;a=a||{};
  var list=(Array.isArray(a.alerts)?a.alerts:[]).map(function(x){return typeof x=="object"&&x?[txt(x.src),typeof x.status=="string"?x.status:""].filter(Boolean).join(": "):txt(x)}).filter(Boolean);
  var n=list.length?(+a.count||list.length):0,ph=d.querySelector("#bn-menu .bn-ph"),box=d.getElementById("bna_malert"),b=d.querySelector("header.bn-top .bn-burger");
  if(b){var dot=b.querySelector(".bna-dot");if(n&&!dot){dot=d.createElement("span");dot.className="bna-dot";b.appendChild(dot)}if(!n&&dot)dot.remove();
   if(n)b.setAttribute("aria-label","Open menu ("+n+" network alert"+(n>1?"s":"")+")");else b.setAttribute("aria-label","Open menu")}
  if(!ph)return;if(!n){box&&box.remove();return}
  if(!box){box=d.createElement("a");box.id="bna_malert";box.className="bna-malert";box.href="/#network";ph.parentNode.insertBefore(box,ph.nextSibling);
   box.addEventListener("click",function(){if(window.bnMenuClose)try{bnMenuClose(true)}catch(e){}})}
  box.innerHTML='<span class="bna-mdot" aria-hidden="true"></span><span><b>Network alert'+(n>1?"s ("+n+")":"")+'</b> '+esc(list.join("; "))+'. <span class="bna-mopen">Open Network Status</span></span>'}
 function load(){fetch("/api/netstatus/alerts",{cache:"no-store"}).then(function(r){return r.json()}).then(alerts).catch(function(){})}
 function go(){tools();load();setInterval(load,300000)}
 // same-page hash links in the menu (The Wire, network alert, other /#tab links without a data-tab handler): close the menu and go to the top
 d.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("#bn-menu a[href]");if(!a||e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||e.button)return;
  var h=a.getAttribute("href")||"";if(h.charAt(0)=="#"||a.pathname!=location.pathname||!a.hash||a.hash=="#bn-menu")return;
  if(window.bnMenuClose)try{bnMenuClose(true)}catch(_){}setTimeout(function(){window.scrollTo(0,0)},0)});
 if(d.readyState=="loading")d.addEventListener("DOMContentLoaded",go);else go();
})();
/* Light-mode legibility (AA): the restyled pages inherit many older text colors that were tuned for dark. In light mode only, after
   render, every visible text color below 4.5:1 (3:1 for large text) against its real background is corrected in place: neutral or
   yellow text becomes ink or white (never brown), colored text is darkened toward black keeping its hue. Yellow fills/rules are snapped
   to the one brand yellow (#FFC21A). Maps, SVG and media are skipped; switching to dark restores the original colors. */
(function(){
 var d=document,R=d.documentElement,done=[],Y="rgb(255, 194, 26)",slow=false;
 function on(){return R.getAttribute("data-theme")=="light"&&(R.classList.contains("bna-pg")||R.classList.contains("bna-home"))}
 function rgb(s){var m=/rgba?\(([^)]+)\)/.exec(s||"");if(!m)return null;var p=m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);return[p[0],p[1],p[2],p.length>3?p[3]:1]}
 function lum(c){var a=[0,1,2].map(function(i){var v=c[i]/255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]}
 function ratio(a,b){var x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
 function mix(f,b){var a=f[3];return[f[0]*a+b[0]*(1-a),f[1]*a+b[1]*(1-a),f[2]*a+b[2]*(1-a),1]}
 function hsl(c){var r=c[0]/255,g=c[1]/255,b=c[2]/255,mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2,s=mx==mn?0:(l>.5?(mx-mn)/(2-mx-mn):(mx-mn)/(mx+mn)),h=0;
  if(mx!=mn){h=mx==r?(g-b)/(mx-mn)+(g<b?6:0):mx==g?(b-r)/(mx-mn)+2:(r-g)/(mx-mn)+4;h*=60}return[h,s,l]}
 function yellow(c){var h=hsl(c);return h[0]>=38&&h[0]<=54&&h[1]>.6&&h[2]>.38}
 function brown(c){var h=hsl(c);return h[0]>=20&&h[0]<=56&&h[1]>.45&&h[2]<.4&&h[2]>.08}
 function yb(c){return yellow(c)||brown(c)}
 var bgc=new Map();
 function bgOf(e){var st=[],x=e;while(x&&x.nodeType==1){if(bgc.has(x)){var b0=bgc.get(x);if(!b0)return null;for(var i=st.length-1;i>=0;i--)b0=mix(st[i],b0);return b0}
   var cs=getComputedStyle(x);if(cs.backgroundImage&&cs.backgroundImage!="none"&&!/gradient/.test(cs.backgroundImage)){bgc.set(x,null);return null}
   var c=rgb(cs.backgroundColor);if(c&&c[3]>0){st.push(c);if(c[3]>=1)break}x=x.parentElement}
  var b=[255,255,255,1];for(var j=st.length-1;j>=0;j--)b=mix(st[j],b);bgc.set(e,b);return b}
 function css(c){return"rgb("+c.slice(0,3).map(Math.round).join(",")+")"}
 function setp(e,p,v){done.push([e,p,e.style.getPropertyValue(p),e.style.getPropertyPriority(p)]);e.style.setProperty(p,v,"important")}
 var DARKOK="[class*=bng],.bna-card,header,.bn-top,#bn-menu,.bn-drawer,.bng,.bng-bar,[class*=toast],[role=tooltip],[role=dialog],video,iframe,canvas,pre,code,.bna-ch,.leaflet-container,.maplibregl-map,.hm-map,[class*=player],[class*=modal],#bn_sig,.bn-sig,.bn-map-page";
 var SKIP=".leaflet-container,svg,canvas,video,iframe,#bn-menu,.bna-ch,script,style,noscript,#bn_sig,.bn-sig,.bn-map-page";
 function roots(){var out=[];if(!d.body)return out;for(var c=d.body.firstElementChild;c;c=c.nextElementSibling){if(/^(SCRIPT|STYLE|NOSCRIPT)$/.test(c.tagName))continue;
   if(c.tagName=="MAIN"||c.id=="bna_home"){if(getComputedStyle(c).display=="none")continue}out.push(c)}return out}
 var queue=[],qi=0,running=false;
 function fix(){if(!on())return;bgc=new Map();queue=[];qi=0;roots().forEach(function(r){var l=r.getElementsByTagName("*");queue.push(r);for(var i=0;i<l.length;i++)queue.push(l[i])});if(!running){running=true;step()}}
 function step(dl){var t0=Date.now();while(qi<queue.length&&(dl?dl.timeRemaining()>2:Date.now()-t0<12)){var e=queue[qi++];one(e)}
  if(qi<queue.length){window.requestIdleCallback?requestIdleCallback(step,{timeout:500}):setTimeout(step,30)}else running=false}
 function one(e){if(!e.isConnected||e.closest(SKIP))return;
   var has=false;for(var n=e.firstChild;n;n=n.nextSibling)if(n.nodeType==3&&n.nodeValue.trim()){has=true;break}
   var cs=null;
   if(e.nodeType==1&&!e.dataset.bnaD){var c0=getComputedStyle(e),b0=rgb(c0.backgroundColor);var f0=rgb(c0.color);if(b0&&b0[3]>.8&&lum(b0)<.03&&f0&&ratio(f0,b0)<4.5&&c0.backgroundImage=="none"&&!e.closest(DARKOK)&&!e.querySelector("img,picture,video,canvas")){var r0=e.getBoundingClientRect();if(r0.width>=120&&r0.height>=36){e.dataset.bnaD=1;setp(e,"background-color","#FFFFFF");bgc=new Map()}}}
   if(!has){cs=getComputedStyle(e);var bc=rgb(cs.backgroundColor);if(bc&&bc[3]>.5&&yb(bc)&&cs.backgroundColor!=Y&&!e.dataset.bnaY){e.dataset.bnaY=1;setp(e,"background-color","#FFC21A");if(e.children.length)setp(e,"color","#1D1D1F")}return}
   var r=e.getBoundingClientRect();if(r.width<1||r.height<1)return;
   cs=cs||getComputedStyle(e);var bcol=rgb(cs.backgroundColor);if(bcol&&bcol[3]>.5&&yb(bcol)&&cs.backgroundColor!=Y){setp(e,"background-color","#FFC21A");bgc.delete(e)}
   var fg=rgb(cs.color),bg=bgOf(e);if(!fg||!bg)return;var f=mix(fg,bg),fs=parseFloat(cs.fontSize),need=(fs>=24||(+cs.fontWeight>=700&&fs>=18.66))?3:4.5;
   if(ratio(f,bg)>=need&&!brown(f))return;e.dataset.bnaC=1;var h=hsl(f),light=lum(bg)>.4,out;
   if(h[1]<.25||yb(f)||!light){out=ratio([29,29,31],bg)>=ratio([255,255,255],bg)?[29,29,31]:[255,255,255]}
   else{out=f.slice();for(var k=0;k<20&&ratio(out,bg)<need;k++)out=out.map(function(v,ix){return ix<3?v*.88:v})}
   setp(e,"color",css(out))}
 function undo(){while(done.length){var x=done.pop();x[0].style.removeProperty(x[1]);if(x[2])x[0].style.setProperty(x[1],x[2],x[3]);delete x[0].dataset.bnaC;delete x[0].dataset.bnaY;delete x[0].dataset.bnaD}}
 var t=0;function soon(ms){if(t)return;t=setTimeout(function(){t=0;var go=function(){try{fix()}catch(e){}};window.requestIdleCallback?requestIdleCallback(go,{timeout:1500}):go()},ms||900)}
 function start(){soon(400);addEventListener("hashchange",function(){soon(700)});addEventListener("load",function(){soon(300)});
  try{new MutationObserver(function(){soon(running?4000:1500)}).observe(d.body,{childList:true,subtree:true,attributes:true,attributeFilter:["class","hidden","open"]})}catch(e){}
  try{new MutationObserver(function(){if(on())soon(100);else undo()}).observe(R,{attributes:true,attributeFilter:["data-theme"]})}catch(e){}}
 if(d.readyState=="loading")d.addEventListener("DOMContentLoaded",start);else start();
})();
/* Phase 3b+: fold secondary content, Apple style. Per page (see ON): the first panel stays open; every later panel folds to its title
   (tap the title to open; nothing is removed). Very long lists show their first part with a "Show all" button. Pages are switched on
   group by group via ON. Nothing here runs when BN_APPLE=0 (this file is not served then). */
(function(){
 var d=document,ON=[/^(wire|streams|noise|heatmap|trends|broadcasts|radio)$/,/^(ranked|intel|ai|finance|weather|grid|solar|network|jets|spacex|maps|politics|government)$/];
 function key(){var p=location.pathname,h=location.hash.replace(/^#/,"");return p=="/"?(h||"home"):p}
 function on(){var k=key();return d.documentElement.classList.contains("bna-pg")&&ON.some(function(r){return r.test(k)})}
 function mainEl(){var ms=d.querySelectorAll("body>main");for(var i=0;i<ms.length;i++){var r=ms[i].getBoundingClientRect();if(r.height>0&&getComputedStyle(ms[i]).display!="none")return ms[i]}return null}
 function setOpen(p,open){p.classList.toggle("bna-shut",!open);var h=p.querySelector(":scope>h2,:scope>h3");if(h)h.setAttribute("aria-expanded",open?"true":"false");
  if(open)setTimeout(function(){try{window.dispatchEvent(new Event("resize"))}catch(e){}},30)}
 function fold(m){var ps=[].filter.call(m.querySelectorAll(":scope>section.pn,:scope>div>section.pn,:scope>div.pn"),function(p){return p.querySelector(":scope>h2")&&p.getBoundingClientRect().height>0||p.classList.contains("bna-fold")});
  if(ps.length<2)return;
  ps.forEach(function(p,i){if(i==0||p.dataset.bnaF)return;p.dataset.bnaF="1";var h=p.querySelector(":scope>h2");p.classList.add("bna-fold");
   h.setAttribute("role","button");h.setAttribute("tabindex","0");var c=d.createElement("span");c.className="bna-chev";c.setAttribute("aria-hidden","true");h.appendChild(c);
   h.addEventListener("click",function(e){if(e.target.closest("a,button,input,select,label,summary")&&!e.target.closest(".bna-chev"))return;setOpen(p,p.classList.contains("bna-shut"))});
   h.addEventListener("keydown",function(e){if(e.target!==h)return;if(e.key=="Enter"||e.key==" "){e.preventDefault();setOpen(p,p.classList.contains("bna-shut"))}});
   setOpen(p,false)})}
 function clamp(m){[].forEach.call(m.querySelectorAll("ol,ul,div"),function(l){if(l.dataset.bnaC||l.closest(".bna-clamp,.bna-shut,details:not([open])"))return;
   if(l.children.length<15||l.getBoundingClientRect().height<1800)return;var r=l.getBoundingClientRect();if(r.width<240)return;
   l.dataset.bnaC="1";l.classList.add("bna-clamp");var b=d.createElement("button");b.type="button";b.className="bna-more";b.textContent="Show all";b.setAttribute("aria-expanded","false");
   b.addEventListener("click",function(){var o=l.classList.toggle("bna-open");b.textContent=o?"Show less":"Show all";b.setAttribute("aria-expanded",o?"true":"false");if(!o)l.scrollIntoView({block:"start"})});
   l.parentNode.insertBefore(b,l.nextSibling)})}
 var t=0;function scan(){t=0;last=Date.now();if(!on())return;var m=mainEl();if(!m)return;try{fold(m);clamp(m)}catch(e){}}
 var last=0,T0=Date.now();function soon(){if(t||Date.now()-T0>45000)return;t=setTimeout(scan,Math.max(400,1500-(Date.now()-last)))}
 function go(){scan();addEventListener("hashchange",function(){setTimeout(scan,300)});new MutationObserver(soon).observe(d.body,{childList:true,subtree:true});setTimeout(scan,2500);setTimeout(scan,6000)}
 if(d.readyState=="loading")d.addEventListener("DOMContentLoaded",go);else go();
})();
