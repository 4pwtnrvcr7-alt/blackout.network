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
 var CAT={"natural disaster":"Natural hazard","war/conflict":"Conflict","disease":"Health","political":"Politics","financial":"Markets","cyber":"Cyber","space weather":"Space weather"};
 function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
 function et(z){if(!z)return"";var d=new Date(z);if(isNaN(d))return"";return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}
 function title(t){return String(t||"").replace(/\s+\./g,".").replace(/ \| [A-Z][\w .]{1,30}$/,"").trim()}
 function isQuake(x){return /earthquake|^m ?\d/i.test(x.title||"")}
 // Same-event quakes (one quake reported by several agencies) collapse into one card: same category, within 1.5 degrees and 36 h.
 function group(items){var out=[];items.forEach(function(x){
   if(isQuake(x)&&x.lat!=null){for(var i=0;i<out.length;i++){var y=out[i];if(y.q&&Math.abs(y.lat-x.lat)<1.5&&Math.abs(y.lon-x.lon)<1.5&&Math.abs(new Date(y.first_seen)-new Date(x.first_seen))<1296e5){y.more++;return}}}
   out.push({title:x.title,category:x.category,location:x.location,lat:x.lat,lon:x.lon,rank:x.rank,n_families:x.n_families,updated:x.updated,first_seen:x.first_seen,q:isQuake(x),more:0})});return out}
 function card(x){var hi=x.rank>=7,loc=x.location&&x.location.length<34?" · "+esc(x.location):"";
  return '<a class="bna-card bna-it'+(hi?" hi":"")+'" href="/#wire"><div class="bna-ct"><p class="bna-k">'+esc(CAT[x.category]||x.category||"")+'</p><span class="bna-rk'+(hi?" red":"")+'">Rank '+x.rank+'<i>/10</i></span></div>'+
   '<h3>'+esc(title(x.title))+'</h3><p class="bna-m">'+x.n_families+' source families'+(x.more?" · "+(x.more+1)+" agency reports grouped":"")+loc+'<br>Updated '+esc(et(x.updated))+'</p></a>'}
 function set(k,v){var e=H.querySelector('[data-bna="'+k+'"]');if(e)e.innerHTML=v}
 var row=document.getElementById("bna_row_latest"),arws=H.querySelectorAll(".bna-arw");
 function arrows(){if(!row)return;var m=row.scrollWidth-row.clientWidth;arws.forEach(function(b){b.disabled=b.dataset.dir<0?row.scrollLeft<=2:row.scrollLeft>=m-2})}
 arws.forEach(function(b){b.addEventListener("click",function(){var rm=matchMedia("(prefers-reduced-motion: reduce)").matches;row.scrollBy({left:(+b.dataset.dir)*row.clientWidth*.8,behavior:rm?"auto":"smooth"})})});
 if(row){row.addEventListener("scroll",arrows,{passive:true});addEventListener("resize",arrows)}
 fetch("/api/apple/home",{credentials:"same-origin"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
  if(d.sources!=null)set("sources",Number(d.sources).toLocaleString("en-US"));
  var g=group((d.main||[]).filter(function(x){var t=x.title||"";return /^[\x20-\x7E]/.test(t)&&!/[\u2600-\u27BF\uD83C-\uDBFF]/.test(t)})),pick=[],per={};
  g.forEach(function(x){if(pick.length<8&&(per[x.category]||0)<2){per[x.category]=(per[x.category]||0)+1;pick.push(x)}});
  g.forEach(function(x){if(pick.length<8&&pick.indexOf(x)<0)pick.push(x)});
  pick.sort(function(a,b){return b.rank-a.rank||b.n_families-a.n_families});
  if(row)row.innerHTML=pick.length?pick.map(card).join(""):'<p class="bna-empty">The Wire is quiet right now.</p>';arrows();
  if(d.kp){set("kp",Number(d.kp.value).toFixed(2)+"<small>/ 9</small>");set("kpd",d.kp.max24!=null?"24-hour high: Kp "+Math.round(d.kp.max24):"");set("kps","NOAA SWPC · "+esc(d.kp.t_et||et(d.kp.t)))}
  if(d.quake){set("qm","M"+Number(d.quake.mag).toFixed(1));set("qp",esc(d.quake.place));set("qs","USGS · "+esc(d.quake.t_et||et(d.quake.t)))}
  if(d.grid&&d.grid.total!=null){var k=d.grid.by_kind||{};set("gt",d.grid.total+"<small>items</small>");set("gd",(d.grid.top!=null?"Top rank "+d.grid.top+" · ":"")+(k.cyber||0)+" cyber advisories · "+(k.outage||0)+" outages");set("gs","As of "+esc(et(d.grid.generated)))}
  if(d.generated)set("asof","Live data as of "+esc(et(d.generated))+".");
 }).catch(function(){if(row)row.innerHTML='<p class="bna-empty">Live data is unavailable right now. <a class="bna-lnk" href="/#wire">Open The Wire</a></p>'});
})();
/* Phase 3a: near-empty top bar. The bar keeps the wordmark and the menu button; The Wire, Sources, Free brief, alerts, search, theme and
   settings live in the menu's top row (search, Alerts, theme, Settings and Free brief were already there; The Wire + Sources are added
   here). Network alerts move from the page banner (#ns_gbanner, hidden by CSS) into the menu, with a small dot on the menu button. */
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
