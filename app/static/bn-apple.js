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
   '<h3>'+esc(title(x.title))+'</h3><p class="bna-m">'+x.n_families+(x.n_families==1?' source':' sources')+(x.more?" · "+(x.more+1)+" agency reports grouped":"")+loc+'<br>Updated '+esc(et(x.updated))+'</p></a>'}
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
/* Active Threat Monitoring: homepage chart cards (same-origin /api/apple/dash, loaded when the section nears the viewport).
   Hand-built inline SVG, no library, no third-party requests. Each card expands in place (accordion, aria-expanded). */
(function(){
 var d=document,S=d.getElementById("bna_dash");if(!S)return;
 var NS="http://www.w3.org/2000/svg",W=300,H=64;
 function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
 function et(z){if(z==null||z==="")return"";var t=typeof z=="number"?new Date(z*1000):new Date(z);if(isNaN(t))return"";return t.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}
 function n(x){return Number(x).toLocaleString("en-US")}
 function pl(k,w,ws){return n(k)+" "+(k==1?w:(ws||w+"s"))}
 function card(k){return S.querySelector('[data-mc="'+k+'"]')}
 function put(k,o){var c=card(k);if(!c)return;["v","s","t","x"].forEach(function(f){if(o[f]!=null){var e=c.querySelector('[data-f="'+f+'"]');if(e)e.innerHTML=o[f]}});
  if(o.c){var e=c.querySelector('[data-f="c"]');e.innerHTML=o.c}c.classList.toggle("bna-sev",!!o.sev);c.classList.add("bna-ok")}
 function none(k,msg){put(k,{v:"&ndash;",s:esc(msg||"Data unavailable right now."),c:""})}
 // charts: thin line or bars, no gridlines; y scaled to the data with an optional reference line
 function line(pts,o){o=o||{};pts=pts.filter(function(p){return p&&p[1]!=null&&isFinite(p[1])});if(pts.length<2)return"";
  var f=o.f||function(v){return v},xs=pts.map(function(p){return p[0]}),ys=pts.map(function(p){return f(p[1])}),x0=Math.min.apply(0,xs),x1=Math.max.apply(0,xs),
   lo=o.lo!=null?Math.min(o.lo,Math.min.apply(0,ys)):Math.min.apply(0,ys),hi=o.hi!=null?Math.max(o.hi,Math.max.apply(0,ys)):Math.max.apply(0,ys);if(hi-lo<1e-9){hi+=1;lo-=1}
  function X(v){return x1>x0?(v-x0)/(x1-x0)*(W-8)+4:W/2}function Y(v){return H-4-(v-lo)/(hi-lo)*(H-10)}
  var dd=pts.map(function(p,i){return(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(f(p[1])).toFixed(1)}).join(""),last=pts[pts.length-1],
   ref=o.ref!=null&&f(o.ref)<=hi&&f(o.ref)>=lo?'<path class="r" d="M0 '+Y(f(o.ref)).toFixed(1)+'H'+W+'"/>':"";
  return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" focusable="false">'+ref+'<path class="a" d="'+dd+'L'+X(last[0]).toFixed(1)+' '+H+'L'+X(pts[0][0]).toFixed(1)+' '+H+'Z"/><path class="l" d="'+dd+'"/></svg>'+
   '<span class="bna-cx"><i>'+esc(o.from||"")+'</i><i>'+esc(o.to||"Now")+'</i></span>'}
 function bars(cols,o){o=o||{};if(!cols.length)return"";var mx=Math.max.apply(0,cols.map(function(c){return c.v.reduce(function(a,b){return a+b},0)}))||1,
   bw=W/cols.length,g=Math.min(6,bw*.28),out="";
  cols.forEach(function(c,i){var y=H,ww=Math.min(Math.max(1,bw-g),34),x=(i*bw+(bw-ww)/2).toFixed(1),w=ww.toFixed(1);c.v.forEach(function(v,j){if(!v)return;var h=Math.max(1.5,v/mx*(H-4));y-=h;
   out+='<rect class="b'+j+'" x="'+x+'" y="'+y.toFixed(1)+'" width="'+w+'" height="'+h.toFixed(1)+'" rx="1.5"/>'})});
  if(!out)out='<path class="r" d="M0 '+(H-1)+'H'+W+'"/>';
  var lab=o.labels?'<span class="bna-cx bna-cl" style="grid-template-columns:repeat('+cols.length+',1fr)">'+cols.map(function(c){return"<i>"+esc(c.l||"")+"</i>"}).join("")+"</span>":
   '<span class="bna-cx"><i>'+esc(o.from||"")+'</i><i>'+esc(o.to||"Now")+'</i></span>';
  return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" focusable="false">'+out+'</svg>'+lab}
 function x(now,def,lv){return '<p><b>Now.</b> '+now+'</p><p><b>What it is.</b> '+def+'</p>'+(lv?'<p><b>Levels.</b> '+lv+'</p>':"")}
 var GW=["Quiet","Minor storm","Moderate storm","Strong storm","Severe storm","Extreme storm"];
 function render(D){
  var k=D.kp;if(k){var g=+k.g||0,v=+k.value,w=g?GW[g]:(v>=4?"Active, no storm":"Quiet");
   put("kp",{v:esc(w),sev:g>=3,s:"Kp "+v.toFixed(1)+" of 9 &middot; NOAA G"+g+(k.max24!=null?" &middot; 24-hour high Kp "+(+k.max24).toFixed(0):""),
    c:line(k.series,{lo:0,hi:5,ref:5,from:"72 hours ago"}),t:"NOAA SWPC &middot; "+esc(et(k.t)),
    x:x("Geomagnetic storm level is <b>"+esc(w)+"</b> (G"+g+"), Kp "+v.toFixed(2)+". Forecast for the next 3 days: "+esc((k.fc||[]).map(function(z){return"G"+(z||0)}).join(", ")||"not posted")+".",
     "Solar storms shake Earth's magnetic field. NOAA measures it with the Kp index (0 to 9) and rates storms G1 to G5. The dashed line marks storm level (Kp 5).",
     "G1 minor (Kp 5), G2 moderate (6), G3 strong (7), G4 severe (8), G5 extreme (9). G3 and up can disrupt power grids, GPS and radio.")})}else none("kp");
  var q=D.quake;if(q){var C=["Minor","Light","Moderate","Strong","Major","Great"],b=q.big,m=b?+b.mag:null,ci=m==null?0:Math.min(5,Math.max(0,Math.floor(m)-3));
   put("quake",{v:b?esc(C[ci])+" <small>M"+m.toFixed(1)+"</small>":"None",sev:m>=7,s:b?esc(b.place||"")+" &middot; "+esc(et(b.t)):"No quakes M2.5+ in 24 hours",
    c:bars(q.classes.map(function(v,i){return{v:i>=4?[0,0,v]:[0,v],l:["<4","4","5","6","7","8+"][i]}}),{labels:1}),t:"USGS &middot; "+pl(q.n24,"quake")+" M2.5+ in 24 hours",
    x:x(b?"The strongest quake in the last 24 hours was <b>"+esc(C[ci].toLowerCase())+"</b>, magnitude "+m.toFixed(1)+", "+esc(b.place||"")+", at "+esc(et(b.t))+(b.tsunami?". USGS flagged it for tsunami review.":"."):"No quakes of magnitude 2.5 or more were recorded in the last 24 hours.",
     "Magnitude measures the energy a quake releases. Each whole step is about 32 times more energy. The chart counts the last 24 hours of quakes by magnitude.",
     "USGS classes: minor 3 to 3.9, light 4 to 4.9, moderate 5 to 5.9, strong 6 to 6.9, major 7 to 7.9, great 8 and up.")})}else none("quake");
  var f=D.flare;if(f&&f.cls){var L=String(f.cls).charAt(0),FW={A:"Quiet",B:"Quiet",C:"Minor flares",M:"Strong flares",X:"Major flares"}[L]||"Quiet",cnt=f.count||{};
   put("flare",{v:esc(FW),sev:L=="X",s:"X-ray level "+esc(f.cls)+" &middot; this week "+pl((cnt.C||0),"C flare")+", "+(cnt.M||0)+" M, "+(cnt.X||0)+" X",
    c:line(f.series,{f:function(v){return Math.log(v)/Math.LN10},lo:-7,hi:-5,ref:1e-5,from:"72 hours ago"}),t:"NOAA GOES &middot; "+esc(f.t_et||""),
    x:x("The Sun's X-ray output is class <b>"+esc(f.cls)+"</b>. Biggest flare this week: "+esc((f.biggest||{}).class||"none")+(f.biggest&&f.biggest.t?" on "+esc(et(f.biggest.t)):"")+".",
     "Solar flares are bursts of X-rays from the Sun. Strong ones can black out shortwave radio and GPS on the sunlit side of Earth within minutes. The dashed line marks M class.",
     "Classes A, B, C, M, X, each 10 times stronger than the last. M flares cause minor radio blackouts (R1 to R2); X flares can cause strong ones (R3 to R5).")})}else none("flare");
  var s=D.wind;if(s&&s.speed!=null){var sp=+s.speed,SW=sp<400?"Calm":sp<600?"Moderate":sp<800?"Fast":"Very fast";
   put("wind",{v:esc(SW)+" <small>"+n(Math.round(sp))+" km/s</small>",sev:sp>=800,s:"Magnetic field Bz "+(s.bz!=null?(+s.bz).toFixed(1)+" nT":"n/a")+(s.bz!=null&&s.bz<=-10?" (southward: storm risk)":""),
    c:line(s.series,{lo:300,hi:600,from:"24 hours ago"}),t:"NOAA DSCOVR &middot; "+esc(s.t_et||""),
    x:x("The solar wind is <b>"+esc(SW.toLowerCase())+"</b> at "+n(Math.round(sp))+" km/s.",
     "A steady stream of charged particles from the Sun. Fast wind with a southward magnetic field (negative Bz) is what drives geomagnetic storms.",
     "Under 400 km/s calm, 400 to 600 moderate, 600 to 800 fast, over 800 very fast.")})}else none("wind");
  var G=D.grid;if(G&&G.regions){var st=G.status||{},ok=st.online||0,bad=G.regions-ok;
   put("grid",{v:ok+" of "+G.regions+" <small>regions normal</small>",sev:!!st.offline,s:(bad?[st.watch?st.watch+" on watch":"",st.degraded?st.degraded+" degraded":"",st.offline?st.offline+" offline":""].filter(Boolean).join(", ")+" &middot; ":"")+n(G.outages||0)+" outages reported by "+pl(G.utilities||0,"utility","utilities"),
    c:bars((G.series||[]).map(function(p){return{v:[p[1],p[2]]}}),{from:"48 hours ago"}),t:"EIA, DOE ODIN &middot; "+esc(et(G.t)),
    x:x(bad?"Flagged: "+(G.flagged||[]).map(function(z){return"<b>"+esc(z.name)+"</b> ("+esc(z.status)+(z.why?": "+esc(z.why):"")+")"}).join("; ")+".":"All monitored U.S. grid regions look normal.",
     "We compare each U.S. grid region's demand with forecasts and yesterday, and add utility outage reports (DOE ODIN) and power-relevant weather warnings. The chart counts regions each hour: gray on watch, yellow degraded.",
     "Normal, Watch (early signs such as 1,500+ reported outages), Degraded (possible load loss or 5,000+ outages), Offline (reported demand collapsed).")})}else none("grid");
  if(G&&G.nws){var nw=G.nws,tot=nw.power||0;
   put("wx",{v:tot?pl(tot,"alert"):"None",sev:(nw.extreme||0)>0,s:tot?pl(nw.warnings||0,"warning")+", "+(nw.extreme||0)+" extreme &middot; U.S.":"No power-threatening NWS alerts in the U.S.",
    c:bars([["Warnings",nw.warnings||0],["Extreme",nw.extreme||0],["Other",Math.max(0,tot-(nw.warnings||0))]].map(function(z,i){return{v:i==1?[0,0,z[1]]:i==0?[0,z[1]]:[z[1]],l:z[0]}}),{labels:1}),
    t:"NWS &middot; "+esc(et(G.nws_t||G.t)),
    x:x(tot?"The National Weather Service has <b>"+pl(tot,"active alert")+"</b> for weather that can knock out power ("+pl(nw.warnings||0,"warning")+", "+(nw.extreme||0)+" extreme).":"No active NWS alerts for power-threatening weather in the U.S.",
     "Counts active NWS alerts for weather that can cut power (high wind, ice, hurricanes, extreme heat or cold) across U.S. grid regions."+((G.storms||[]).length?" Worldwide, the top storm on The Wire: "+esc(G.storms[0].title)+".":""),
     "Advisory (be aware), Watch (be prepared), Warning (take action), Extreme (life-threatening).")})}else none("wx");
  var N=D.net;if(N&&N.count!=null){var a=N.alerts||[];
   put("net",{v:N.count?pl(N.count,"provider issue"):"All clear",sev:N.count>=3,s:N.count?esc(a.map(function(z){return z.src}).join(", ")):(N.checked?n(N.checked)+" services checked":"Major providers operating normally"),
    c:bars((N.series||[]).map(function(p){return{v:[0,p[1]]}}),{from:"24 hours ago"}),t:"Provider status pages &middot; "+esc(et(N.t)),
    x:x(N.count?a.map(function(z){return"<b>"+esc(z.src)+"</b>: "+esc(z.status)}).join("; ")+".":"Every monitored internet, cloud and DNS provider reports normal operation.",
     "We poll the status pages and DNS of major cloud, CDN, DNS and app providers. The chart counts providers with a problem at each check.",
     "Operational, Notice, Degraded, Major outage.")})}else none("net");
  var R=D.wire;if(R&&R.days&&R.days.length){var DN=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
   put("wire",{v:n(R.total)+" <small>stories</small>",s:pl(R.hi,"high-severity story","high-severity stories")+" (rank 7+) in 7 days",
    c:bars(R.days.map(function(z){var dt=new Date(z[0]+"T12:00:00");return{v:[z[3],z[2],z[1]],l:DN[dt.getDay()].charAt(0)}}),{labels:1}),t:"BLACKOUT.NETWORK scanner &middot; "+esc(et(D.now)),
    x:x("<b>"+n(R.total)+"</b> stories reached The Wire in the last 7 days; "+n(R.hi)+" ranked 7 or higher.",
     "Every story we track gets a rank from 0 to 10 using published rules. Bars show stories per day: gray rank 0 to 3, yellow 4 to 6, red 7 and up.",
     "0 to 3 low, 4 to 6 notable, 7 to 10 high severity.")})}else none("wire");
 }
 function toggle(c,open){var b=c.querySelector(".bna-mh"),p=c.querySelector(".bna-mx");b.setAttribute("aria-expanded",open?"true":"false");p.hidden=!open;c.classList.toggle("bna-open",open)}
 S.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".bna-mh");if(!b)return;var c=b.closest(".bna-mc");toggle(c,b.getAttribute("aria-expanded")!="true")});
 var got=0;function load(){if(got)return;got=1;fetch("/api/apple/dash",{credentials:"same-origin"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(render)
  .catch(function(){["kp","quake","flare","wind","grid","wx","net","wire"].forEach(function(k){none(k)})})}
 if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){if(es.some(function(z){return z.isIntersecting})){io.disconnect();load()}},{rootMargin:"600px 0px"});io.observe(S)}else load();
})();
