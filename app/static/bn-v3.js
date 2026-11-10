/* BLACKOUT.NETWORK design v3, phase 1 (2026-11-02): full-page menu layout, accordions on The Wire / Network Status / Solar & Seismic,
   live refresh of the Top of mind + What's coming bands. Additive only: every section, id, link and control stays in the DOM
   (accordions are native <details>, so find-in-page, print and screen readers keep working). No MutationObservers except one class
   watch on #bn-menu (menu open); a light 2 s check wraps content that a tab renders later. Open/closed choices are remembered for the session only (sessionStorage). */
(function(){
 if(window.__bnV3)return;window.__bnV3=1;
 var d=document,R=d.documentElement,$=function(s,r){return(r||d).querySelector(s)},$$=function(s,r){return[].slice.call((r||d).querySelectorAll(s))};
 var SS={get:function(k){try{return sessionStorage.getItem("bnacc:"+k)}catch(e){return null}},set:function(k,v){try{sessionStorage.setItem("bnacc:"+k,v)}catch(e){}}};
 var esc=function(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})};
 var SVG='<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">';
 var IC={
  clock:SVG+'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',eye:SVG+'<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  map:SVG+'<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/></svg>',bars:SVG+'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  trend:SVG+'<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg>',bell:SVG+'<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>',
  list:SVG+'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',code:SVG+'<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M14 4l-4 16"/></svg>',
  sun:SVG+'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  wave:SVG+'<path d="M2 12h4l2-6 4 12 3-9 2 3h5"/></svg>',book:SVG+'<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/></svg>',
  globe:SVG+'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',lab:SVG+'<path d="M9 3h6M10 3v6L4 19a1.5 1.5 0 0 0 1.3 2h13.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/></svg>'};
 window.bnV3={IC:IC,SS:SS};

 /* ---------- accordions ---------- */
 function kick(){try{window.dispatchEvent(new Event("resize"))}catch(e){}}
 function make(id,o){
  var det=d.createElement("details");det.className="bn-acc";det.id=id;if(o.color)det.style.setProperty("--bn-acc-c",o.color);
  det.innerHTML='<summary><span class="bn-acc-ic">'+(IC[o.icon]||IC.list)+'</span><span class="bn-acc-t"><b>'+esc(o.title)+'</b>'+(o.desc?'<small>'+esc(o.desc)+'</small>':'')+'</span><span class="bn-acc-v"></span></summary><div class="bn-acc-body"></div>';
  var saved=SS.get(id);det.open=saved?saved==="1":!!o.open;
  var sm=det.firstChild;sm.setAttribute("aria-expanded",det.open?"true":"false");
  sm.addEventListener("click",function(){setTimeout(function(){SS.set(id,det.open?"1":"0")},0)});
  det.addEventListener("toggle",function(){sm.setAttribute("aria-expanded",det.open?"true":"false");if(det.open)setTimeout(kick,30)});
  if(o.value)det._val=o.value;return det}
 function wrapEl(el,id,o){                       // move one element into a new accordion placed where it was
  if(!el||el.closest("details.bn-acc")||d.getElementById(id))return null;
  var det=make(id,o);el.parentNode.insertBefore(det,el);det.lastChild.appendChild(el);return det}
 function wrapRun(h,id,o){                        // a heading plus its following siblings up to the next heading of the same kind
  if(!h||h.closest("details.bn-acc"))return null;var old=d.getElementById(id);if(old&&!old.querySelector("h3,h2,div,section"))old.remove();else if(old)return null;
  var det=make(id,o),run=[h],n=h.nextElementSibling;while(n&&!n.matches("h2,h3.ss-h,details.bn-acc")){run.push(n);n=n.nextElementSibling}
  h.parentNode.insertBefore(det,h);run.forEach(function(x){det.lastChild.appendChild(x)});return det}
 function txt(sel,n){var e=typeof sel=="string"?$(sel):sel;return e?e.textContent.replace(/\s+/g," ").trim().slice(0,n||80):""}
 function setVal(det,html){if(!det)return;var v=det.querySelector(":scope>summary>.bn-acc-v");if(v&&v.innerHTML!==html)v.innerHTML=html}
 function allToggle(host,scope){                   // "Expand all / Collapse all" for 5+ accordions
  if(!host||$(".bn-acc-tools",host.parentNode))return;var t=d.createElement("div");t.className="bn-acc-tools";
  t.style.gridColumn="1/-1";t.innerHTML='<button type="button" class="bn-acc-all" aria-pressed="false">Expand all</button>';host.parentNode.insertBefore(t,host);
  var b=t.firstChild;b.onclick=function(){var on=b.getAttribute("aria-pressed")!=="true";$$("details.bn-acc",scope).forEach(function(x){x.open=on;SS.set(x.id,on?"1":"0")});
   b.setAttribute("aria-pressed",on?"true":"false");b.textContent=on?"Collapse all":"Expand all";kick()}}
 // print: everything expanded, then restored
 var printState=null;addEventListener("beforeprint",function(){printState=$$("details.bn-acc").map(function(x){var o=x.open;x.open=true;return[x,o]})});
 addEventListener("afterprint",function(){(printState||[]).forEach(function(p){p[0].open=p[1]});printState=null});

 /* The Wire: the confirmed feed stays open; long blocks collapse (map and the volume chart stay open: they are the graphics) */
 function wire(){
  var m=d.getElementById("tab-threat");if(!m)return;
  var sec=function(id){var e=d.getElementById(id);return e?e.closest("section"):null};
  var band=d.getElementById("v3_wireband");
  var wh=wrapEl(d.getElementById("wh"),"acc-history",{title:"Timeline history",desc:"Every stored scanner story plus archived source data, back to Oct 2024",icon:"book"});
  var tl=wrapEl(d.getElementById("tl"),"acc-timeline",{title:"Timeline",desc:"Scrub hour by hour through everything cataloged, with source snapshots",icon:"clock"});
  [wh,tl].forEach(function(x){if(x)x.style.gridColumn="1/-1"});
  wrapEl(sec("watch"),"acc-watchlist",{title:"Watchlist",desc:"Single-source, low-confidence items waiting for a second source",icon:"eye"});
  wrapEl(sec("map"),"acc-heatmap",{title:"Geographic heat map",desc:"Where the last 7 days of alerts cluster",icon:"map",open:true});
  wrapEl(sec("vol")||(function(){var h=$$("#tab-threat h2").filter(function(x){return/^Alert volume/.test(x.textContent.trim())})[0];return h&&h.closest("section")})(),"acc-volume",{title:"Alert volume by category",desc:"Merged items per day for 7 days, stacked by category",icon:"bars",open:true});
  wrapEl(sec("trend"),"acc-trend",{title:"Severity trend",desc:"Daily highest score, average and count of high items",icon:"trend"});
  wrapEl((function(){var h=$$("#tab-threat h2").filter(function(x){return/^Notification settings/.test(x.textContent.trim())})[0];return h&&h.closest("section")})(),"acc-notify",{title:"Notification settings",desc:"How and when alerts are pushed",icon:"bell"});
  wrapEl(sec("sources"),"acc-sources",{title:"Sources & health",desc:"Every feed the scanner reads and whether its last fetch worked",icon:"list"});
  wrapEl(sec("apilink"),"acc-api",{title:"API",desc:"Public JSON endpoints for high-severity items",icon:"code"});
  var first=d.getElementById("acc-history")||d.getElementById("acc-timeline");if(first&&!first.dataset.tools){first.dataset.tools=1;allToggle(first,m)}
  order(m);
  setVal(d.getElementById("acc-watchlist"),txt("#wcount")?'<span class="bn-acc-st warn">'+esc(txt("#wcount"))+' items</span>':"");
  setVal(d.getElementById("acc-timeline"),esc(txt("#tl_cnt",40)));
  var ok=$$("#sources .ok,#sources [data-ok=1]").length;setVal(d.getElementById("acc-sources"),ok?'<span class="bn-acc-st">'+ok+' OK</span>':"")}

 /* Solar & Seismic: Sun image, active NOAA alerts, Kp outlook, flare odds, X-ray flux and latest quakes stay open */
 function solar(){
  var m=d.getElementById("tab-solar");if(!m)return;
  var h3=function(re){return $$("#tab-solar h3.ss-h").filter(function(h){return re.test(h.textContent)&&!h.closest("details.bn-acc")})[0]};
  wrapRun(h3(/The science, from the Sun/),"acc-ss-science",{title:"The science, from the Sun to the ground",desc:"How flares, CMEs and storms reach Earth, and what they do",icon:"book"});
  wrapRun(h3(/^Recent flares/),"acc-ss-flares",{title:"Recent flares, past 7 days",desc:"Every C, M and X flare NOAA logged this week",icon:"sun"});
  wrapRun(h3(/^Active sunspot regions/),"acc-ss-spots",{title:"Active sunspot regions",desc:"Numbered regions on the visible disk",icon:"sun"});
  wrapEl(d.getElementById("sq_top"),"acc-ss-corrlab",{title:"Solar-Earthquake Correlation Lab",desc:"Does space weather line up with quakes? The data, side by side",icon:"lab"});
  wrapEl(d.getElementById("ss_live"),"acc-ss-history",{title:"Alert history and notable earthquakes",desc:"NOAA alerts, watches and warnings and tsunami flags, past 7 days",icon:"wave"});
  wrapEl(d.getElementById("ss_lab"),"acc-ss-lab",{title:"Correlation lab: where the quakes were",desc:"This week's M2.5+ quakes against the Kp record",icon:"globe"});
  var s=d.getElementById("acc-ss-science");if(s&&$$("details.bn-acc",m).length>=5)allToggle(s,m);
  [["acc-ss-flares",/past 7 days\s*·\s*(.*)$/],["acc-ss-spots",/·\s*(\d+ numbered[^·]*)/],["acc-ss-history",/·\s*(\d+ in 7[^·]*)/]].forEach(function(p){
   var det=d.getElementById(p[0]);if(!det)return;var h=det.querySelector("h3.ss-h");var mm=h&&h.textContent.match(p[1]);if(mm)setVal(det,esc(mm[1].trim().slice(0,40)))})}

 /* Network Status groups are built as accordions by dashboard.html (nsLoad); this only adds Expand all */
 function net(){var m=d.getElementById("tab-net"),first=m&&$("#ns_list details.bn-acc",m);if(first&&$$("#ns_list details.bn-acc",m).length>=5)allToggle(d.getElementById("ns_list"),m)}

 /* ---------- v3 graphical menu (approved Nov 2): desktop board, accordion keys, lazy art + live previews ----------
    Nothing here runs at first paint: art (/api/v3/menu-art) and previews (same-origin /api endpoints only) load the first
    time the menu opens; previews refresh at most every 5 minutes while it is open. A value that can't be fetched keeps a dash. */
 var M3={art:null,t:0,busy:false},RMQ=matchMedia("(prefers-reduced-motion: reduce)"),DESK=matchMedia("(min-width:768px)");
 function etFmt(iso){try{return new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit",month:"short",day:"numeric"}).replace(/^(\w+ \d+), /,"$1, ")+" ET"}catch(e){return ""}}
 function etTime(iso){try{return new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"})+" ET"}catch(e){return ""}}
 function pv(p,k){return $('[data-pv="'+k+'"]',p)}
 function put(p,k,v){var e=pv(p,k);if(e&&v!=null&&v!=="")e.textContent=v;return e}
 function count(e,to,dec,pre){if(!e)return;var f=function(v){return (pre||"")+v.toLocaleString("en-US",{minimumFractionDigits:dec,maximumFractionDigits:dec})};
  if(RMQ.matches||!window.requestAnimationFrame){e.textContent=f(to);return}var t0=null;(function s(t){t0=t0||t;var k=Math.min(1,(t-t0)/900),x=1-Math.pow(1-k,3);e.textContent=f(to*x);if(k<1)requestAnimationFrame(s)})(performance.now())}
 function J(u){return fetch(u,{cache:"no-store",credentials:"same-origin"}).then(function(r){return r.ok?r.json():null}).catch(function(){return null})}
 function m3desk(p){var g=$$(".m3-p",p);g.forEach(function(x){var s=$("summary",x);if(DESK.matches){if(!x.open){x.open=true;x.dataset.v3auto="1"}s&&s.setAttribute("tabindex","-1")}
   else{s&&s.removeAttribute("tabindex");if(x.dataset.v3auto){x.open=false;delete x.dataset.v3auto}}})}
 function m3art(p){if(M3.art)return;M3.art=1;J("/api/v3/menu-art").then(function(a){if(!a)return;
   $$("svg[data-art]",p).forEach(function(s){var k=s.getAttribute("data-art");if(!a[k])return;s.innerHTML=a[k];
    if(RMQ.matches)return;var w=s.parentNode;$$("path,circle",s).forEach(function(e){var l=1;try{l=Math.ceil(e.getTotalLength())}catch(_){}e.style.setProperty("--l",l)});w.classList.add("m3-draw");
    setTimeout(function(){w.classList.remove("m3-draw");$$("path,circle",s).forEach(function(e){e.style.removeProperty("--l")})},1600)})})}
 function m3data(p){var now=Date.now();if(M3.busy||now-M3.t<300000)return;M3.busy=true;M3.t=now;var stamp=[];
  var done=0,fin=function(){if(++done<6)return;M3.busy=false;var st=$("#m3_stamp",p);if(st)st.textContent=stamp.length?"As of "+etFmt(new Date().toISOString())+" · "+stamp.join(" · "):""};
  var sec=function(k){return $('[data-pvsec="'+k+'"]',p)};
  function fillWire(S){var x=sec("latest");if(S&&S.main&&S.main.length&&x){var top=S.main.reduce(function(a,b){return (+b.rank||0)>(+a.rank||0)?b:a},S.main[0]),rk=Math.max(0,Math.min(10,Math.round(+top.rank||0)));
    put(x,"wire-title",String(top.title||"").split(" | ")[0]);var m=pv(x,"wire-meter");
    if(m){var segs="";for(var i=0;i<10;i++)segs+='<i class="'+(i<rk?(i>=6?"on hot":"on"):"")+'"></i>';m.innerHTML='<span>Rank <b>'+rk+'</b>/10</span><span class="m3-segs" aria-hidden="true">'+segs+'</span>';m.setAttribute("role","img");m.setAttribute("aria-label","Rank "+rk+" of 10")}
    put(x,"wire-asof",(top.n_families?top.n_families+" source families · ":"")+"updated "+etFmt(top.updated));stamp.push("Wire "+etTime(top.updated))}
   else if(x)put(x,"wire-title","The Wire: latest item unavailable right now")}
  function withTimeout(p,ms){return Promise.race([p,new Promise(function(res){setTimeout(function(){res(null)},ms)})])}
  /* Prefer the slim /api/apple/home (a few KB) over /api/state (~500 KB), which can hang the "Loading the latest ranked item" placeholder on phones. */
  withTimeout(J("/api/apple/home"),8000).then(function(H){
    if(H&&H.main&&H.main.length){fillWire(H);fin();return}
    return withTimeout(J("/api/state"),8000).then(function(S){fillWire(S);fin()});
  }).catch(function(){fillWire(null);fin()});
  J("/api/solar_seismic").then(function(S){var x=sec("threats");if(S&&x){var kp=S.now&&S.now.kp;if(kp&&kp.value!=null){count(pv(x,"kp"),+kp.value,2);stamp.push("Kp period from "+etTime(kp.t))}
    var q=(S.quakes_notable||[])[0];if(q){count(pv(x,"quake"),+q.mag,1,"M");put(x,"quake-place",q.place);stamp.push("quake "+etTime(q.t))}
    put(x,"threats-asof",kp?"NOAA SWPC · USGS · "+etFmt(S.generated):"")}fin()});
  J("/api/grid").then(function(G){var x=sec("threats");if(G&&G.summary&&x){var br=G.summary.by_rank||{},top=0;Object.keys(br).forEach(function(k){if(/^\d+$/.test(k)&&br[k])top=Math.max(top,+k)});
    count(pv(x,"grid"),+G.summary.total,0);put(x,"grid-sub","items, top rank "+top)}fin()});
  J("/api/finance").then(function(F){var x=sec("markets");if(F&&F.groups&&x){var it=null;F.groups.forEach(function(g){(g.items||[]).forEach(function(i){if(!it&&i.sym==="^GSPC")it=i})});
    if(it){put(x,"spx-label",it.label+(it.spark&&it.spark.length>2?" · today":""));count(pv(x,"spx"),+it.price,2);var c=pv(x,"spx-chg");if(c&&it.chg_pct!=null){c.textContent=(it.chg_pct>=0?"+":"")+(+it.chg_pct).toFixed(2)+"%";c.classList.toggle("dn",it.chg_pct<0)}
     var s=(it.spark||[]).filter(function(v){return typeof v==="number"});if(s.length>2){var lo=Math.min.apply(null,s),hi=Math.max.apply(null,s)||1,r=(hi-lo)||1;
      pv(x,"spark").setAttribute("points",s.map(function(v,i){return (i*200/(s.length-1)).toFixed(1)+","+(38-(v-lo)/r*34).toFixed(1)}).join(" "))}
     put(x,"markets-asof","Quote "+etFmt(F.quotes_fetched||F.updated)+(F.delay_note?" (delayed)":""))}}fin()});
  J("/api/spacex").then(function(X){var x=sec("markets");if(X&&X.next&&x){put(x,"launch",X.next.name+" · NET "+etFmt(X.next.net))}fin()});
  J("/api/sources/catalog?per=1").then(function(C){var a=sec("about"),c=sec("community");if(C&&C.total){count(pv(a,"sources"),+C.total,0);count(pv(c,"sources-c"),+C.total,0);put(a,"sources-asof","as of "+etFmt(new Date().toISOString()))}fin()});
  var mx=sec("politics");if(mx){var d=Math.ceil((Date.UTC(2026,10,3,5)-Date.now())/86400000);if(d>0){count(pv(mx,"midterms"),d,0);put(mx,"midterms-unit",(d===1?"day":"days")+" to Election Day, Nov 3")}
   else if(d===0){put(mx,"midterms","Today");put(mx,"midterms-unit","Election Day, Nov 3")}else{put(mx,"midterms","Results");put(mx,"midterms-unit","Midterms 2026")}}}
 function menu(){
  var dr=d.getElementById("bn-menu"),p=dr&&$(".bn-panel",dr);if(!p||!dr.classList.contains("bn-m3")||p.dataset.m3)return;p.dataset.m3="1";
  m3desk(p);DESK.addEventListener?DESK.addEventListener("change",function(){m3desk(p)}):DESK.addListener(function(){m3desk(p)});
  // desktop: the board is always open (summaries are headings, not toggles)
  p.addEventListener("click",function(e){var s=e.target.closest&&e.target.closest(".m3-p>summary");if(s&&DESK.matches)e.preventDefault()},true);
  // phone accordion keys: Up/Down/Home/End move between section headers (Enter/Space toggle natively)
  p.addEventListener("keydown",function(e){var s=e.target.closest&&e.target.closest(".m3-p>summary");if(!s||DESK.matches)return;var all=$$(".m3-p>summary",p),i=all.indexOf(s),j=-1;
   if(e.key==="ArrowDown")j=Math.min(all.length-1,i+1);else if(e.key==="ArrowUp")j=Math.max(0,i-1);else if(e.key==="Home")j=0;else if(e.key==="End")j=all.length-1;if(j<0)return;e.preventDefault();all[j].focus()});
  // Alerts: opens the existing Alerts panel (alerts.js) when it is on the page
  $$(".m3-alerts",p).forEach(function(b){if(!(window.BN&&window.BN.enableAlerts)&&!d.querySelector(".bn-bell,[data-bn-alerts]"))b.hidden=true;
   b.addEventListener("click",function(){if(window.bnMenuClose)bnMenuClose(true);if(window.BN&&window.BN.enableAlerts)window.BN.enableAlerts({from:"menu"});else{var x=d.querySelector(".bn-bell,[data-bn-alerts]");x&&x.click()}})});
  var opened=function(){if(!dr.classList.contains("bn-open"))return;m3desk(p);m3art(p);m3data(p)};
  new MutationObserver(opened).observe(dr,{attributes:true,attributeFilter:["class"]});opened()}

 /* ---------- Wire bands: refresh from /api/v3/wire every 5 minutes (server already rendered them into the page) ---------- */
 var lastBand=null;
 function bands(){var host=d.getElementById("v3_wireband");if(!host)return;
  fetch("/api/v3/wire",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(j){if(!j||typeof j.html!="string")return;
   if(lastBand===null){lastBand=j.html;if(!host.children.length&&j.html)host.innerHTML=j.html;return}
   if(j.html!==lastBand){lastBand=j.html;host.innerHTML=j.html}}).catch(function(){})}

 /* ---------- Wire pulse: 4 live numbers from /api/state (the same data as the feed), animated; nothing shown until real data arrives ---------- */
 var RM=matchMedia("(prefers-reduced-motion: reduce)");
 function countUp(el,to){if(RM.matches||!window.requestAnimationFrame){el.textContent=to.toLocaleString();return}var t0=null,from=0;
  function f(t){t0=t0||t;var k=Math.min(1,(t-t0)/900),e=1-Math.pow(1-k,3);el.textContent=Math.round(from+(to-from)*e).toLocaleString();if(k<1)requestAnimationFrame(f)}requestAnimationFrame(f)}
 function pulse(){var m=d.getElementById("tab-threat");if(!m)return;
  fetch("/api/state",{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(S){if(!S||!S.main)return;
   var main=S.main,top=main.reduce(function(a,x){return(x.rank||0)>(a?a.rank||0:-1)?x:a},null),rk=top?top.rank||0:0;
   var src=S.sources||[],ok=src.filter(function(x){return x.ok}).length,wl=S.watchlist_count!=null?S.watchlist_count:(S.watchlist||[]).length;
   var days={};(S.volume||[]).forEach(function(v){days[v.d]=(days[v.d]||0)+v.n});var dk=Object.keys(days).sort().slice(-7),mx=Math.max.apply(null,dk.map(function(k){return days[k]}).concat([1]));
   var el=d.getElementById("v3_pulse"),fresh=!el;if(fresh){el=d.createElement("div");el.id="v3_pulse";el.className="v3-pulse";el.setAttribute("aria-label","The Wire right now");}
   var segs="";for(var i=1;i<=10;i++)segs+='<i class="'+(i<=rk?(rk>=7?"on hot":rk>=5?"on mid":"on"):"")+'" style="--k:'+i+'"></i>';
   var bars=dk.map(function(k,i){return'<i style="--h:'+Math.max(6,Math.round(days[k]/mx*100))+'%;--k:'+i+'" title="'+esc(k)+': '+days[k]+'"></i>'}).join("");
   var pct=src.length?ok/src.length:0,C=2*Math.PI*16;
   el.innerHTML='<div class="v3-pc"><span class="v3-pk">Top rank now</span><b class="v3-pn"><span data-n="'+rk+'">'+rk+'</span><small>/10</small></b><span class="v3-meter'+(rk>=7?" hot":"")+'" aria-hidden="true">'+segs+'</span><span class="v3-ps">'+esc(top?(top.category||"")+(top.location?", "+top.location:""):"")+'</span></div>'+
    '<div class="v3-pc"><span class="v3-pk">On The Wire</span><b class="v3-pn"><span data-n="'+main.length+'">'+main.length+'</span></b><span class="v3-spark" aria-hidden="true">'+bars+'</span><span class="v3-ps">confirmed items · alerts per day, last 7 days</span></div>'+
    '<div class="v3-pc"><span class="v3-pk">Watchlist</span><b class="v3-pn"><span data-n="'+wl+'">'+wl+'</span></b><span class="v3-ps">single-source, waiting for a second source</span></div>'+
    '<div class="v3-pc v3-pc-ring"><svg class="v3-ring" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="16"/><circle class="v3-ring-v" cx="20" cy="20" r="16" style="stroke-dasharray:'+C.toFixed(1)+';--off:'+(C*(1-pct)).toFixed(1)+'"/></svg><div><span class="v3-pk">Sources OK</span><b class="v3-pn"><span data-n="'+ok+'">'+ok+'</span><small> of '+src.length+'</small></b><span class="v3-ps">at the last scan</span></div></div>';
   if(fresh){m.insertBefore(el,m.firstElementChild);order(m);$$(".v3-pn [data-n]",el).forEach(function(n){countUp(n,+n.getAttribute("data-n"))})}
  }).catch(function(){})}
 function order(m){   // top of The Wire: pulse, bands, expand-all, timeline history, timeline (moves only what is out of place)
  var prev=null;[d.getElementById("v3_pulse"),d.getElementById("v3_wireband"),$(":scope>.bn-acc-tools",m),d.getElementById("acc-history"),d.getElementById("acc-timeline")].forEach(function(el){
   if(!el||el.parentNode!==m)return;var target=prev?prev.nextElementSibling:m.firstElementChild;if(el!==target)m.insertBefore(el,target);prev=el})}

 function tick(){try{wire()}catch(e){}try{solar()}catch(e){}try{net()}catch(e){}}
 function boot(){try{menu()}catch(e){}tick();setInterval(tick,2000);if(d.getElementById("v3_wireband")){bands();setInterval(bands,300000);pulse();setInterval(pulse,180000)}}
 if(d.readyState==="loading")d.addEventListener("DOMContentLoaded",boot);else boot();
})();
