/* BLACKOUT.NETWORK shared nav (t301/t302/t320/t321/t323), loaded by the dashboard and every standalone page.
   - Sidebar menu (#bn-menu, markup from sitenav_ui.py): modal dialog with focus trap, Escape / scrim / close button, body scroll lock,
     aria-expanded on the menu button, collapsible sections remembered per visitor, current tab highlighted, site search inside.
   - Light / dark theme toggle (the initial theme is set before paint by server.py THEME_HEAD); charts and maps follow the theme.
   - Settings popover (dashboard scan status, refresh, interval; language picker).
   - Dashboard: tab order + grouping, per-tab <title>/meta/Open Graph, the page title + one-line description, deep links.
   All data (tabs, groups, labels, titles) is embedded by the server from sitenav.py. */
(function(){"use strict";
if(window.bnSitenav)return;window.bnSitenav=1;
var D=/*BN_SITENAV_DATA*/null;var R=document.documentElement;R.classList.add("bn-js");
var LS={get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},set:function(k,v){try{v==null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch(e){}}};
if(!window.bnMeter)window.bnMeter=function(r,sz){r=Math.max(0,Math.min(10,Math.round(+r||0)));return '<span class="bn-meter bn-r'+r+(sz?" bn-meter-"+sz:"")+'" role="img" aria-label="Rank '+r+' of 10" title="Rank '+r+' of 10"><span class="bn-segs" aria-hidden="true">'+new Array(11).join("<i></i>")+'</span><b class="bn-num" aria-hidden="true">'+r+'<small>/10</small></b></span>'};
function $(s,r){return (r||document).querySelector(s)}function $$(s,r){return [].slice.call((r||document).querySelectorAll(s))}

/* ---------------- theme ---------------- */
function cssv(n){return getComputedStyle(R).getPropertyValue(n).trim()}
function chartTheme(ch){try{var tx=cssv("--bn-muted"),gr=cssv("--bn-line"),o=ch.options;if(!o)return;
  var sc=o.scales||{};Object.keys(sc).forEach(function(k){var s=sc[k];if(!s)return;if(s.ticks)s.ticks.color=tx;if(s.grid)s.grid.color=gr;if(s.title)s.title.color=tx;if(s.pointLabels)s.pointLabels.color=tx;if(s.angleLines)s.angleLines.color=gr;if(s.border)s.border.color=gr});
  if(o.plugins&&o.plugins.legend&&o.plugins.legend.labels)o.plugins.legend.labels.color=tx;if(o.plugins&&o.plugins.title)o.plugins.title.color=tx}catch(e){}}
var chartHooked=false;
function charts(redraw){var C=window.Chart;if(!C||!C.defaults)return;C.defaults.color=cssv("--bn-muted");C.defaults.borderColor=cssv("--bn-line");
 if(!chartHooked&&C.register){chartHooked=true;try{C.register({id:"bnTheme",beforeUpdate:function(ch){if(R.getAttribute("data-theme")==="light"||ch.$bnThemed)chartTheme(ch)}})}catch(e){}}
 if(redraw){var I=C.instances||{};Object.keys(I).forEach(function(k){var ch=I[k];ch.$bnThemed=true;chartTheme(ch);try{ch.update("none")}catch(e){}})}}
function setTheme(t,save){t=t==="light"?"light":"dark";R.setAttribute("data-theme",t);R.style.colorScheme=t;if(save)LS.set("bn_theme",t);
 var m=$('meta[name="theme-color"]');if(m)m.setAttribute("content",t==="light"?"#f6f7f9":"#0b0d10");
 $$("[data-bn-theme]").forEach(function(b){var nx=t==="light"?"dark":"light";b.setAttribute("aria-label","Switch to "+nx+" mode");b.setAttribute("aria-pressed",t==="light"?"true":"false");
  var l=$(".bn-tl",b);if(l)l.textContent=(nx==="light"?"Light":"Dark")+" mode"});
 charts(true);try{window.dispatchEvent(new CustomEvent("bn-theme",{detail:{theme:t}}))}catch(e){}}
window.bnTheme=function(){return R.getAttribute("data-theme")==="light"?"light":"dark"};
if(window.matchMedia){var mq=matchMedia("(prefers-color-scheme: light)");var onmq=function(){if(!LS.get("bn_theme"))setTheme(mq.matches?"light":"dark",false)};
 if(mq.addEventListener)mq.addEventListener("change",onmq);else if(mq.addListener)mq.addListener(onmq)}

/* t397: the language picker + site-wide translation (/api/translate/app.js) on every page, not just the four that linked it */
function trLoad(){if(window.BNTR||document.querySelector('script[src*="api/translate/app.js"]'))return;var d=document,l=d.createElement("link");l.rel="stylesheet";l.href="/api/translate/app.css";d.head.appendChild(l);
 var s=d.createElement("script");s.src="/api/translate/app.js";d.head.appendChild(s)}
function init(){
 try{trLoad()}catch(e){}
 setTheme(window.bnTheme(),false);setTimeout(function(){charts(false)},1500);addEventListener("load",function(){charts(R.getAttribute("data-theme")==="light")});
 document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-bn-theme]");if(b){e.preventDefault();setTheme(window.bnTheme()==="light"?"dark":"light",true)}});

 /* ---------------- sidebar ---------------- */
 var dr=document.getElementById("bn-menu"),panel=dr&&$(".bn-panel",dr),burger=$(".bn-burger"),lastFocus=null;
 if(dr&&panel){
  panel.setAttribute("role","dialog");panel.setAttribute("aria-modal","true");panel.setAttribute("aria-label","Site menu");panel.setAttribute("tabindex","-1");dr.setAttribute("aria-hidden","true");
  var focusables=function(){return $$('a[href],button:not([disabled]),input:not([disabled]),select,summary,[tabindex]:not([tabindex="-1"])',panel).filter(function(x){return x.offsetParent!==null||x===document.activeElement})};
  var setExp=function(v){$$('[aria-controls="bn-menu"]').forEach(function(b){b.setAttribute("aria-expanded",v?"true":"false")})};
  var menuHist=false;
  window.bnMenuOpen=function(opts){opts=opts||{};if(dr.classList.contains("bn-open")){if(opts.search)focusSearch();return}lastFocus=document.activeElement;closePop();
   dr.classList.add("bn-open");dr.removeAttribute("aria-hidden");R.classList.add("bn-lock");setExp(true);
   if(!menuHist){try{history.pushState({bnMenu:1},"");menuHist=true}catch(e){}}
   if(opts.search)focusSearch();else{var c=$(".bn-close",panel);(c||panel).focus({preventScroll:true})}};
  window.bnMenuClose=function(noFocus,opts){opts=opts||{};if(!dr.classList.contains("bn-open"))return false;dr.classList.remove("bn-open");dr.setAttribute("aria-hidden","true");R.classList.remove("bn-lock");setExp(false);
   if(opts.replace){if(menuHist&&history.state&&history.state.bnMenu){try{history.replaceState(null,"",opts.replace)}catch(e){}}else try{history.pushState(null,"",opts.replace)}catch(e){}menuHist=false}
   else if(menuHist&&!opts.fromPop&&history.state&&history.state.bnMenu){menuHist=false;try{history.back()}catch(e){}}
   else{menuHist=false;if(location.hash==="#bn-menu")try{history.replaceState(null,"",location.pathname+location.search)}catch(e){}}
   if(!noFocus){var f=lastFocus&&document.contains(lastFocus)&&lastFocus.offsetParent!==null?lastFocus:burger;if(f)try{f.focus({preventScroll:true})}catch(e){}}return true};
  addEventListener("popstate",function(){if(dr.classList.contains("bn-open"))bnMenuClose(false,{fromPop:true})});
  var focusSearch=function(){var i=document.getElementById("bns_q");if(i&&panel.contains(i)){i.focus();try{i.select()}catch(e){}}else{var c=$(".bn-close",panel);c&&c.focus()}};
  document.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest("a,button");if(!t)return;
   if(t.matches(".bn-burger")){e.preventDefault();dr.classList.contains("bn-open")?bnMenuClose():bnMenuOpen();return}
   if(t.matches(".bn-searchbtn")){e.preventDefault();bnMenuOpen({search:true});return}
   if(t.matches(".bn-close,.bn-scrim")){e.preventDefault();bnMenuClose();return}
   if(t.matches(".bn-gear-row")){e.preventDefault();bnMenuClose(true);openPop(t);return}});
  dr.addEventListener("keydown",function(e){if(!dr.classList.contains("bn-open"))return;
   if(e.key==="Escape"){var p=$("#bns_pop.on");if(p&&p.contains(document.activeElement))return;e.preventDefault();bnMenuClose();return}
   if(e.key!=="Tab")return;var f=focusables();if(!f.length)return;var a=f[0],z=f[f.length-1];
   if(e.shiftKey&&(document.activeElement===a||document.activeElement===panel)){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}});
  document.addEventListener("focusin",function(e){if(dr.classList.contains("bn-open")&&!panel.contains(e.target)&&!(document.getElementById("bns_panel")||{contains:function(){return false}}).contains(e.target)){var c=$(".bn-close",panel);c&&c.focus()}});
  if(location.hash==="#bn-menu")bnMenuOpen();
  // sections: remember open/closed (the current tab's section always opens)
  $$("details.bn-grp",panel).forEach(function(d){var k="bn_grp_"+d.dataset.grp,v=LS.get(k);if(v==="1")d.open=true;else if(v==="0"&&!$('a[aria-current="page"]',d))d.open=false;
   d.addEventListener("toggle",function(){if(!d.dataset.v3auto)LS.set(k,d.open?"1":"0")})});
  // "/" opens the sidebar with search focused (the search script then focuses its field)
  document.addEventListener("keydown",function(e){if(e.key!=="/"||e.ctrlKey||e.metaKey||e.altKey)return;var a=document.activeElement;if(a&&(/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)||a.isContentEditable))return;
   if(document.getElementById("bns")){bnMenuOpen({search:true})}},true);
  // move the site search (search_static/app.js mounts it in the header) into the sidebar
  var slot=document.getElementById("bn_dsearch");
  var moveSearch=function(){var b=document.getElementById("bns");if(!b||!slot)return false;if(b.parentNode!==slot){b.classList.remove("open");slot.appendChild(b)}return true};
  if(!moveSearch()){var mo=new MutationObserver(function(){if(moveSearch())mo.disconnect()});mo.observe(document.body,{childList:true,subtree:true});setTimeout(function(){mo.disconnect()},30000)}
  // a search result panel replaces the sidebar
  var watchPanel=function(){var p=document.getElementById("bns_panel");if(!p)return setTimeout(watchPanel,1000);
   new MutationObserver(function(){if(getComputedStyle(p).display!=="none")bnMenuClose(true)}).observe(p,{attributes:true,attributeFilter:["style","class"]})};watchPanel();
  if(slot)slot.addEventListener("submit",function(){setTimeout(function(){bnMenuClose(true)},0)},true);
 }

 /* ---------------- settings popover ---------------- */
 var pop=document.getElementById("bn_settings"),gear=$(".bn-gear"),popFrom=null;
 function openPop(from){if(!pop)return;popFrom=from||gear;pop.hidden=false;gear&&gear.setAttribute("aria-expanded","true");var f=$("button,select,input,a[href]",pop);(f||pop).focus&&setTimeout(function(){try{(f||pop).focus({preventScroll:true})}catch(e){}},0)}
 function closePop(back){if(!pop||pop.hidden)return;pop.hidden=true;gear&&gear.setAttribute("aria-expanded","false");if(back&&popFrom&&popFrom.offsetParent!==null)popFrom.focus()}
 if(pop){pop.setAttribute("tabindex","-1");
  gear&&gear.addEventListener("click",function(e){e.preventDefault();pop.hidden?openPop(gear):closePop(true)});
  document.addEventListener("pointerdown",function(e){if(!pop.hidden&&!pop.contains(e.target)&&!(gear&&gear.contains(e.target))&&!e.target.closest(".bn-gear-row"))closePop()},true);
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!pop.hidden){closePop(true)}})}

 /* ---------------- dashboard tabs ---------------- */
 if(!D)return;
 var byKey={},byHash={};D.tabs.forEach(function(t){byKey[t.key]=t;byHash[t.hash]=t});
 function meta(attr,name,val){var m=document.head.querySelector("meta["+attr+'="'+name+'"]');if(!m){m=document.createElement("meta");m.setAttribute(attr,name);document.head.appendChild(m)}m.setAttribute("content",val)}
 function setMeta(title,desc,url){if(document.title!==title)document.title=title;meta("name","description",desc);meta("property","og:title",title);
  meta("property","og:description",desc);meta("property","og:url",url);meta("name","twitter:title",title);meta("name","twitter:description",desc)}
 var nav=$("body>nav.tabs")||$("nav.tabs");if(!nav||!nav.querySelector("button[data-tab]"))return;
 var desc=document.getElementById("bn_tabdesc"),ptitle=document.getElementById("bn_ptitle");
 if(!desc){desc=document.createElement("p");desc.id="bn_tabdesc";desc.className="bn-tabdesc";nav.parentNode.insertBefore(desc,nav.nextSibling)}
 // sidebar / bar links switch tabs in place
 function btn(k){return nav.querySelector('button[data-tab="'+k+'"]')}
 document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("#bn-menu a[data-tab],.bn-primary a[data-tab]");if(!a||e.ctrlKey||e.metaKey||e.shiftKey||e.button)return;
  var k=a.dataset.tab;if(k.charAt(0)==="@")return;var b=btn(k);if(!b)return;e.preventDefault();
  var dest=a.hash&&a.hash!==location.hash?a.hash:"";if(!(window.bnMenuClose&&bnMenuClose(true,dest?{replace:dest}:{}))&&dest)try{history.pushState(null,"",dest)}catch(_){}
  if(!b.classList.contains("on"))b.click();window.scrollTo(0,0);var h=document.getElementById("bn_ptitle");if(h){h.setAttribute("tabindex","-1");try{h.focus({preventScroll:true})}catch(_){}}});
 // ---- one tab order (kept for add-ons that read the strip); tabs not listed in sitenav.py go at the end of the first group
 function el(t){if(t.key==="@scoring")return document.getElementById("tab_howscore");
  if(t.key.charAt(0)==="@"&&t.hash.charAt(0)==="/"){var id="tab_"+t.key.slice(1),a=document.getElementById(id);
   if(!a){a=document.createElement("a");a.id=id;a.href=t.hash;a.textContent=t.label;a.dataset.link=t.key}return a}
  return btn(t.key)}
 function want(){var out=[],known={};D.tabs.forEach(function(t){known[t.key]=1});
  D.groups.forEach(function(g,i){if(i)out.push("sep");if(g)out.push("grp:"+g);
   D.tabs.forEach(function(t){if(t.group===g){var e=el(t);if(e)out.push(e)}});
   if(i===0)$$("button[data-tab]",nav).forEach(function(b){if(!known[b.dataset.tab])out.push(b)})});
  return out}
 function sig(list){return list.map(function(x){return typeof x==="string"?x:(x.dataset&&x.dataset.tab)||x.id}).join("|")}
 function cur(){return [].map.call(nav.children,function(c){return c.classList.contains("tab-sep")?"sep":c.classList.contains("tab-grp")?"grp:"+c.textContent:c})}
 var busy=false;
 function order(){var w=want();if(sig(w)===sig(cur()))return;busy=true;var f=document.createDocumentFragment();
  w.forEach(function(x){if(typeof x!=="string")return f.appendChild(x);var s=document.createElement("span");
   if(x==="sep")s.className="tab-sep";else{s.className="tab-grp";s.textContent=x.slice(4)}f.appendChild(s)});
  [].slice.call(nav.children).forEach(function(c){if(c.classList.contains("tab-sep")||c.classList.contains("tab-grp"))c.remove()});
  nav.appendChild(f);busy=false}
 // ---- sidebar mirrors the live tab list: add-on tabs not in sitenav.py, hidden/removed tabs, badges
 function syncMenu(){if(!dr)return;var first=$("details.bn-grp ul",dr);
  $$("button[data-tab]",nav).forEach(function(b){var k=b.dataset.tab;if(byKey[k]||k==="thread")return;var a=$('a[data-tab="'+k+'"]',dr);
   if(!a&&first){var li=document.createElement("li");a=document.createElement("a");a.dataset.tab=k;a.href="#"+k;li.appendChild(a);first.appendChild(li)}
   if(a){var lb=b.textContent.trim();if(a.textContent!==lb)a.textContent=lb}});
  $$("a[data-tab]",dr).forEach(function(a){var k=a.dataset.tab;if(k.charAt(0)==="@")return;var b=btn(k);
   var bad=b&&b.querySelector(".ns-badge,[class*=badge]"),mine=a.querySelector(".bn-badge"),txt=bad&&bad.textContent.trim();
   if(txt){if(!mine){mine=document.createElement("span");mine.className="bn-badge";a.appendChild(mine)}if(mine.textContent!==txt)mine.textContent=txt;mine.setAttribute("aria-label",txt+" alerts")}
   else if(mine)mine.remove()})}
 // ---- per-tab title / description / highlight
 var last="";
 function upd(){var b=nav.querySelector("button.on[data-tab]");if(!b)return;var k=b.dataset.tab,t=byKey[k],title,d,url;
  if(!t||k==="threat"){title=D.home.title;d=D.home.desc;url=D.site+"/"}
  else{title=(t.title||b.textContent.trim())+" | "+D.brand;d=t.desc||D.home.desc;url=D.site+"/#"+t.hash}
  if(!t&&k!=="threat"){title=b.textContent.replace(/^\W+/,"").trim()+" | "+D.brand}
  var line=(t&&t.desc)||"";if(desc.textContent!==line)desc.textContent=line;desc.hidden=!line;
  var nm=(D.plain&&D.plain[k])||b.textContent.replace(/^[^\w(]+/,"").replace(/\d+$/,"").trim();if(ptitle&&ptitle.textContent!==nm)ptitle.textContent=nm;
  $$("#bn-menu a[data-tab],.bn-primary a[data-tab]").forEach(function(a){if(a.dataset.tab===k)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
  var act=dr&&$('#bn-menu a[aria-current="page"]');if(act){var dd=act.closest("details");if(dd&&!dd.open)dd.open=true}
  if(title+d===last&&document.title===title)return;last=title+d;setMeta(title,d,url)}
 // deep links to tabs whose add-on loads late (e.g. /#government): honor the first hash once its button appears
 var pending=(location.hash||"").slice(1);if(pending==="bn-menu")pending="";setTimeout(function(){pending=""},30000);
 nav.addEventListener("pointerdown",function(){pending=""},true);if(dr)dr.addEventListener("pointerdown",function(){pending=""},true);
 function deep(){if(!pending)return;var t=byHash[pending];if(!t||t.hidden||t.key.charAt(0)==="@"){pending="";return}
  var b=btn(t.key);if(!b)return;pending="";if(!b.classList.contains("on"))b.click()}
 var tm=0;function soon(){clearTimeout(tm);tm=setTimeout(function(){if(!busy)order();deep();syncMenu();upd()},60)}
 new MutationObserver(soon).observe(nav,{childList:true,subtree:true,attributes:true,attributeFilter:["class"],characterData:true});
 addEventListener("hashchange",function(){var h=(location.hash||"").slice(1);if(h==="bn-menu")return;pending=h;soon()});addEventListener("load",soon);order();syncMenu();upd();setTimeout(soon,500);setTimeout(soon,2500)}
/* ---------------- t357: top-bar fitter ----------------
   Steps the bar down (see sitenav.css "t357") until logo + nav + actions fit on one row without clipping the wordmark.
   Re-runs on resize/zoom, font load, and when add-ons insert buttons (Alerts bell). Only classes on <header> change. */
function fitBar(){var hd=$("header.bn-top"),bar=hd&&$(".bn-tbar",hd);if(!hd||!bar)return;
 var acts=$(".bn-acts",bar),logo=$(".bn-logo",bar),MAX=6,busy=false,raf=0,lastW=-1;
 function set(n){hd.classList.toggle("bn-roomy",n===0);for(var i=1;i<=MAX;i++)hd.classList.toggle("bn-f"+i,n>=i)}
 function ok(){var min=parseFloat(getComputedStyle(bar).minHeight)||0,h=bar.getBoundingClientRect().height;
  if(h>min+1)return false;if(bar.scrollWidth>bar.clientWidth+1)return false;
  if(logo&&logo.scrollWidth>logo.clientWidth+1)return false;
  if(acts){var ar=acts.getBoundingClientRect(),br=bar.getBoundingClientRect();if(ar.right>br.right+1||acts.scrollWidth>acts.clientWidth+1)return false}
  return true}
 function run(){raf=0;if(busy)return;busy=true;var n=0;for(;n<MAX;n++){set(n);if(ok())break}if(n===MAX)set(MAX);lastW=R.clientWidth;busy=false}
 function soon(){if(!raf)raf=requestAnimationFrame(run)}
 run();addEventListener("resize",function(){if(R.clientWidth!==lastW)soon()});addEventListener("load",soon);
 if(document.fonts&&document.fonts.ready)document.fonts.ready.then(soon);
 if(acts&&window.MutationObserver)new MutationObserver(function(){if(!busy)soon()}).observe(acts,{childList:true,subtree:true,characterData:true});
 setTimeout(soon,1200)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){try{fitBar()}catch(e){}init()});else{try{fitBar()}catch(e){}init()}})();
