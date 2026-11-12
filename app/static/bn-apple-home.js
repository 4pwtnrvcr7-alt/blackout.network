/* BLACKOUT.NETWORK homepage renderer (apple_style_v1). Inlined into "/" by apple_v1.home_html together with the server's last snapshot,
   so the Wire row and Active Threat Monitoring are filled on first paint (no empty or loading state). bn-apple.js refreshes in place. */
(function(){
 var H=document.getElementById("bna_home");if(!H||window.BNA)return;var lastRow=null;
 var CAT={"natural disaster":"Natural hazard","war/conflict":"Conflict","disease":"Health","political":"Politics","financial":"Markets","cyber":"Cyber","space weather":"Space weather"};
 function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
 function et(z){if(!z)return"";var d=new Date(z);if(isNaN(d))return"";return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}
 function title(t){return String(t||"").replace(/\s+\./g,".").replace(/ \| [A-Z][\w .]{1,30}$/,"").trim()}
 function isQuake(x){return /earthquake|^m ?\d/i.test(x.title||"")}
 // Same-event quakes (one quake reported by several agencies) collapse into one card: same category, within 1.5 degrees and 36 h.
 function group(items){var out=[];items.forEach(function(x){
   if(isQuake(x)&&x.lat!=null){for(var i=0;i<out.length;i++){var y=out[i];if(y.q&&Math.abs(y.lat-x.lat)<1.5&&Math.abs(y.lon-x.lon)<1.5&&Math.abs(new Date(y.first_seen)-new Date(x.first_seen))<1296e5){y.more++;return}}}
   out.push({cluster_id:x.cluster_id,title:x.title,category:x.category,location:x.location,lat:x.lat,lon:x.lon,rank:x.rank,n_families:x.n_families,updated:x.updated,first_seen:x.first_seen,social:x.social,posted:x.posted,q:isQuake(x),more:0})});return out}
 // Display-only category fix (t100u): the scanner's keyword order labels "governor declares emergency over flooding" Political.
 // Hazard and outbreak terms outrank political ones here; the stored category is unchanged (proposed scanner fix: category_fix.patch).
 var HZ=/\b(earthquake|tsunami|flood|flooding|flash flood|cyclone|hurricane|typhoon|tropical storm|winter storm|wildfire|volcan|eruption|landslide|drought|tornado|blizzard|severe weather|severe storms?)/i,
  DZ=/\b(ebola|marburg|cholera|measles|influenza|h5n1|bird flu|avian flu|mpox|dengue|plague|epidemic|pandemic|polio|outbreak)/i,NO=/\b(war|weather|storm|tornado) outbreaks?\b/i,
  WZ=/\b(missile|airstrike|strike|attack|troops|drone|military|war\b|bomb|shelling|invasion|ceasefire)/i;
 function dcat(x){var c=x.category||"",t=x.title||"";if(c=="political"||c=="other"||(c=="war/conflict"&&!WZ.test(t))){if(DZ.test(t)&&!NO.test(t))return"disease";if(HZ.test(t))return"natural disaster"}return c}
 function sid(x){return /^[0-9a-f]{16}$/.test(x.cluster_id||"")?x.cluster_id:""}
 function okx(u){return /^https:\/\/(x|twitter)\.com\/BlkoutNtw\/status\/\d{5,25}$/i.test(u||"")}
 function oky(u){return /^https:\/\/(www\.)?youtube\.com\/(shorts\/|watch\?v=)[A-Za-z0-9_\-]{11}$/.test(u||"")}
 // "Follow this story": only links that passed the box link check (HTTP 200, deleted posts skipped) and the server passed on.
 function follow(x){var s=x.social||{},id=sid(x),a=[];
  if(okx(s.x))a.push('<a href="'+esc(s.x)+'" target="_blank" rel="noopener" aria-label="Follow this story on X">X</a>');
  if(oky(s.yt))a.push('<a href="'+esc(s.yt)+'" target="_blank" rel="noopener" aria-label="Watch this story on YouTube">YouTube</a>');
  if(!a.length)return"";if(id&&s.story!==null)a.push('<a href="/wire/'+id+'">Story page</a>');
  return '<div class="bna-fol"><span>Follow this story</span>'+a.join("")+'</div>'}
 function card(x){x=Object.assign({},x,{category:dcat(x)});var hi=x.rank>=7,loc=x.location&&x.location.length<34?" · "+esc(x.location):"",id=sid(x),fo=follow(x);
  return '<article class="bna-card bna-it'+(hi?" hi":"")+(fo?" bna-has-fol":"")+'"><a class="bna-cardlnk" href="'+(id?"/wire/"+id:"/#wire")+'">'+(x.posted?'<p class="bna-pstw"><b class="bna-pst">On our channels</b></p>':'')+'<div class="bna-ct"><p class="bna-k">'+esc(CAT[x.category]||x.category||"")+'</p><span class="bna-rk'+(hi?" red":"")+'">Rank '+x.rank+'<i>/10</i></span></div>'+
   '<h3>'+esc(title(x.title))+'</h3><p class="bna-m">'+x.n_families+(x.n_families==1?' source':' sources')+(x.more?" · "+(x.more+1)+" agency reports grouped":"")+loc+'<br>Updated '+esc(et(x.updated))+'</p></a>'+fo+'</article>'}
 function set(k,v){var e=H.querySelector('[data-bna="'+k+'"]');if(e)e.innerHTML=v}
 var row=document.getElementById("bna_row_latest"),arws=H.querySelectorAll(".bna-arw");
 function arrows(){if(!row)return;var m=row.scrollWidth-row.clientWidth;arws.forEach(function(b){b.disabled=b.dataset.dir<0?row.scrollLeft<=2:row.scrollLeft>=m-2})}
 arws.forEach(function(b){b.addEventListener("click",function(){var rm=matchMedia("(prefers-reduced-motion: reduce)").matches;row.scrollBy({left:(+b.dataset.dir)*row.clientWidth*.8,behavior:rm?"auto":"smooth"})})});
 if(row){row.addEventListener("scroll",arrows,{passive:true});addEventListener("resize",arrows)}
 // Refresh right after each social posting slot (8, 11 AM, 2, 4, 8, 10 PM ET) so the story we just posted shows here; normal live updates continue.
 var SLOTT=0;
 function nextSlot(sl){try{var f=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).formatToParts(new Date()),o={};
  f.forEach(function(p){o[p.type]=+p.value});var now=o.hour*3600+o.minute*60+o.second,best=null;
  sl.forEach(function(s){var p=s.split(":"),t=(+p[0])*3600+(+p[1])*60+240,dt=t-now;if(dt<=0)dt+=86400;if(best===null||dt<best)best=dt});
  if(best===null)return 0;return setTimeout(function(){SLOTT=0;if(window.BNA)BNA.refresh()},best*1000)}catch(e){return 0}}
 function renderHome(d){
  if(d.sources!=null)set("sources",Number(d.sources).toLocaleString("en-US"));
  var g=group((d.main||[]).filter(function(x){var t=x.title||"";return /^[\x20-\x7E]/.test(t)&&!/[\u2600-\u27BF\uD83C-\uDBFF]/.test(t)})),pick=[],per={},N=10;
  // Stories posted on X/YouTube in the last day that pass the topic policy lead the row (highest rank first, then newest; max 3).
  // The rest keep the server order from /api/apple/home (home_feed.latest: 48/72h freshness, topic+junk filter, rank with recency bias).
  g.filter(function(x){return x.posted}).sort(function(a,b){return (b.rank||0)-(a.rank||0)||String((b.social||{}).posted_at||"").localeCompare(String((a.social||{}).posted_at||""))}).slice(0,3).forEach(function(x){pick.push(x)});
  var lead=pick.length;
  g.forEach(function(x){if(pick.length<N&&pick.indexOf(x)<0&&(per[x.category]||0)<2){per[x.category]=(per[x.category]||0)+1;pick.push(x)}});
  g.forEach(function(x){if(pick.length<N&&pick.indexOf(x)<0)pick.push(x)});
  // preserve relative server order among non-pinned cards (do not re-sort by rank alone)
  pick=pick.slice(0,lead).concat(pick.slice(lead));
  var hh=pick.length?pick.map(card).join(""):'<p class="bna-empty">The Wire is quiet right now.</p>';if(row&&hh!==lastRow){lastRow=hh;row.innerHTML=hh;arrows()}
  if(d.slots_et&&!SLOTT)SLOTT=nextSlot(d.slots_et);
  if(d.generated)set("asof","Live data as of "+esc(et(d.generated))+".");
 }
 var renderDash=(function(){
 var d=document,S=d.getElementById("bna_dash");if(!S)return function(){};
 var NS="http://www.w3.org/2000/svg",W=300,H=64;
 function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
 function et(z){if(z==null||z==="")return"";var t=typeof z=="number"?new Date(z*1000):new Date(z);if(isNaN(t))return"";return t.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}
 function n(x){return Number(x).toLocaleString("en-US")}
 function pl(k,w,ws){return n(k)+" "+(k==1?w:(ws||w+"s"))}
 function card(k){return S.querySelector('[data-mc="'+k+'"]')}
 function put(k,o){var c=card(k);if(!c)return;["v","s","t","x","c"].forEach(function(f){if(o[f]!=null){var e=c.querySelector('[data-f="'+f+'"]');if(e&&e.innerHTML!==o[f])e.innerHTML=o[f]}});c.classList.toggle("bna-sev",!!o.sev);c.classList.add("bna-ok")}
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
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" focusable="false" aria-hidden="true">'+out+'</svg>';
  if(!o.days)return svg+lab;
  // Transparent hit targets over each day column (touch + mouse + keyboard)
  var hits='<div class="bna-barhit" role="tablist" aria-label="Stories by day" style="grid-template-columns:repeat('+cols.length+',1fr)">'+
    cols.map(function(c,i){var n=(c.v||[]).reduce(function(a,b){return a+b},0),day=o.days[i]||"";
     return '<button type="button" role="tab" class="bna-barday" data-day="'+esc(day)+'" aria-selected="false" aria-label="'+(c.l||"Day")+', '+n+' stor'+(n==1?"y":"ies")+(n?", show list":", none")+'"'+(n?"":" disabled")+'></button>'}).join("")+"</div>";
  return '<div class="bna-bars">'+svg+hits+lab+"</div>"}
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
    c:line(N.series||[],{lo:0,hi:3,from:"24 hours ago"}),t:"Provider status pages &middot; "+esc(et(N.t)),
    x:x(N.count?a.map(function(z){return"<b>"+esc(z.src)+"</b>: "+esc(z.status)}).join("; ")+".":"Every monitored internet, cloud and DNS provider reports normal operation.",
     "We poll the status pages and DNS of major cloud, CDN, DNS and app providers. The chart counts providers with a problem at each check.",
     "Operational, Notice, Degraded, Major outage.")})}else none("net");
  var R=D.wire;if(R&&R.days&&R.days.length){var DN=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
   put("wire",{v:n(R.total)+" <small>stories</small>",s:pl(R.hi,"high-severity story","high-severity stories")+" (rank 7+) in 7 days",
    c:bars(R.days.map(function(z){var dt=new Date(z[0]+"T12:00:00");return{v:[z[3],z[2],z[1]],l:DN[dt.getDay()].charAt(0)}}),{labels:1}),t:"BLACKOUT.NETWORK scanner &middot; "+esc(et(D.now)),
    x:x("<b>"+n(R.total)+"</b> stories reached The Wire in the last 7 days; "+n(R.hi)+" ranked 7 or higher.",
     "Every story we track gets a rank from 0 to 10 using published rules. Bars show stories per day: gray rank 0 to 3, yellow 4 to 6, red 7 and up.",
     "0 to 3 low, 4 to 6 notable, 7 to 10 high severity.")})}else none("wire");
  try{board(D)}catch(e){}
 }

 // ---- widget board groups (elections, conflict, health, hardship, quake map). Real data only; empty states say so plainly.
 var LASTD=null,TK=null;
 function hm(sec){sec=Math.max(0,Math.round(sec/60));var h=Math.floor(sec/60),m=sec%60;return h?h+"h "+(m<10?"0":"")+m+"m":m+" min"}
 function tET(ts){return new Date(ts*1000).toLocaleTimeString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"})+" ET"}
 function PN(c){return c=="D"?"D":c=="R"?"R":c?c:""}
 function el(D){var E=D.el;if(!E){["el_next","el_sen","el_gov","el_house"].forEach(function(k){none(k)});return}
  var now=Date.now()/1000,nt=E.next&&E.next>now?E.next:null;
  if(!nt&&E.waves)E.waves.forEach(function(w){if(!nt&&w[0]>now)nt=w[0]});
  var wave=nt===E.next?E.wave:[],first=E.first&&now<E.first;
  var cols=(E.waves||[]).map(function(w){var d=new Date(w[0]*1000),l=d.toLocaleTimeString("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"}).replace(":00","").replace(/ [AP]M/,"");return{v:w[0]<=now?[w[1]]:[0,w[1]],l:l}});
  if(nt){put("el_next",{v:esc(hm(nt-now))+" <small>until "+(first?"first":"next")+" polls close</small>",
    s:(wave&&wave.length?esc(wave.slice(0,3).join(", "))+(wave.length>3?" and "+(wave.length-3)+" more":"")+" at ":"Next closing at ")+esc(tET(nt))+" &middot; last polls close "+esc(tET(E.last))+" (in "+esc(hm(E.last-now))+")",
    c:bars(cols,{labels:1}),t:"270toWin, NCSL &middot; "+E.closed+" of "+E.states+" states closed",
    x:x((E.closed?"Polls have closed in <b>"+E.closed+"</b> of "+E.states+" states and D.C. ":"No polls have closed yet. ")+"The next closing is at <b>"+esc(tET(nt))+"</b>. The last polls close at "+esc(tET(E.last))+".",
     "Scheduled poll closing times in Eastern Time for Election Day, Tuesday, November 3. Voters in line when polls close can still vote. Bars count states closing at each time; gray ones have closed.",
     "Results start to come in after a state's polls close. Split-time-zone states close in two steps.")})}
  else put("el_next",{v:"All polls closed",s:"Last polls closed at "+esc(tET(E.last))+". Counting continues.",c:bars(cols,{labels:1}),t:"270toWin, NCSL",
    x:x("Every state's polls have closed. Counting can take days in some states.","Scheduled poll closing times in Eastern Time.","")});
  [["el_sen","senate","Senate"],["el_gov","governor","Governor"],["el_house","house","House"]].forEach(function(z){var R=E[z[1]]||[];if(!R.length){none(z[0],"No rated races in the data.");return}
   var have=R.filter(function(r){return r.lead}).length,
    li=R.map(function(r){var L=r.lead,rt=esc(r.label)+'<em>'+esc(r.rating||"")+'</em>';
     var right=L?'<b>'+esc(L.name.split(" ").slice(-1)[0])+" ("+PN(L.code)+")"+(L.won?" won":" +"+L.margin.toFixed(1))+'</b>'+(L.rep&&L.rep[1]?'<small>'+Math.round(100*L.rep[0]/L.rep[1])+"% of "+esc(L.rep[2]||"units")+" in</small>":""):'<small>'+(r.close&&r.close>now?"Polls close "+esc(tET(r.close)):"Results after polls close")+'</small>';
     return '<li><span>'+rt+'</span><span>'+right+'</span></li>'}).join("");
   put(z[0],{v:have?have+" of "+R.length+" <small>with early results</small>":"Results after polls close",
    s:"Closest "+R.length+" races by forecaster ratings",c:'<ul class="bna-rl">'+li+'</ul>',t:"State results feeds, Wikipedia &middot; "+esc(et(E.t)),
    x:x(have?"Leaders shown with their margin in points and the share of counties reporting, as published by the official state results feeds (or Wikipedia where no feed exists). We do not call races.":"No results yet. Each race shows its scheduled poll closing time.",
     "The "+z[2]+" races that forecasters rate closest, using the consensus of published ratings. Margin is the leader's lead in percentage points.",
     "Ratings: Tossup, Tilt, Lean, Likely, Safe.")})});
 }
 var DNS=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
 function dayList(o,day){var list=(o.stories&&o.stories[day])||[],dn="";
  try{dn=new Date(day+"T12:00:00").toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}catch(e){dn=day}
  if(!list.length)return '<p><b>'+esc(dn)+'.</b> No stories this day.</p>';
  return '<p><b>'+esc(dn)+'.</b> '+pl(list.length,"story","stories")+(o.src?"":" on The Wire")+'.</p><ul class="bna-day">'+list.map(function(z){
    var ext=z.ext?' target="_blank" rel="noopener"':"";
    return '<li><a class="bna-lnk" href="'+esc(z.url)+'"'+ext+'>'+esc(z.title)+(z.ext?' <span class="bna-ext" aria-label="opens the original article">&#8599;</span>':"")+'</a> <span class="bna-rkchip'+(z.rank>=7?" red":"")+'">'+z.rank+'/10</span> <small>'+esc(z.src||"The Wire")+'</small></li>'}).join("")+"</ul>"}
 function wg(k,o,def){if(!o){none(k);return}var tp=o.top,c=card(k);if(c)c._bnaO=o;
  var dayKeys=(o.days||[]).map(function(z){return z[0]});
  var cols=(o.days||[]).map(function(z){var dt=new Date(z[0]+"T12:00:00");return{v:[0,z[1],z[2]],l:DNS[dt.getDay()].charAt(0)}});
  var vline=o.n24?pl(o.n24,"story","stories")+" <small>in 24 hours</small>":"Quiet <small>in 24 hours</small>";
  if(k==="unrest"&&(o.us||o.world)){
    var U=o.us||{},W=o.world||{};
    vline="U.S. "+(U.n24||0)+" · World "+(W.n24||0)+" <small>in 24 hours</small>";
  }
  var sline=tp?esc(tp.title):(o.n7?pl(o.n7,"story","stories")+" in 7 days, none in the last 24 hours":"No stories in 7 days");
  if(k==="unrest"&&(o.us||o.world)){
    var U2=o.us||{},W2=o.world||{};
    sline="U.S. "+(U2.n7||0)+" · World "+(W2.n7||0)+" in 7 days"+(tp?": "+esc(tp.title):"");
  }
  put(k,{v:vline,sev:o.max24>=7||(o.us&&o.us.max24>=7)||(o.world&&o.world.max24>=7),
   s:sline,
   c:bars(cols,{labels:1,days:dayKeys}),t:esc(o.src||"The Wire")+" &middot; "+pl(o.n7,"story","stories")+" in 7 days",
   x:x(tp?'Top story now (rank '+tp.rank+'/10): <a class="bna-lnk" href="'+esc(tp.url)+'"'+(tp.ext?' target="_blank" rel="noopener"':"")+'>'+esc(tp.title)+'</a>, updated '+esc(et(tp.t))+".":"Nothing ranked in the last 24 hours.",
    def+" Tap a day bar for that day's stories. Red marks rank 7 and up.","Rank 0 to 3 low, 4 to 6 notable, 7 to 10 high severity.")})}
 function hl3(o){return (o.latest||[]).map(function(z){return '<li><a class="bna-lnk" href="'+esc(z.url)+'">'+esc(z.title)+'</a> <small>'+esc(et(z.t))+(z.single?" &middot; single source":"")+'</small></li>'}).join("")}
 function spc(D){var S=D.spec||{},N=S.nuke,P=S.disp;
  function cols(o){return(o.days||[]).map(function(z){var dt=new Date(z[0]+"T12:00:00");return{v:[0,z[1],z[2]],l:DNS[dt.getDay()].charAt(0)}})}
  function dayKeys(o){return(o.days||[]).map(function(z){return z[0]})}
  if(N){var lv=N.max24>=8?"High":(N.max24>=6||N.conf24>=3)?"Elevated":N.n24?"Watch":"Low",tp=(N.latest||[])[0],cn=card("c_nuke");if(cn)cn._bnaO=N;
   put("c_nuke",{v:lv+" <small>"+pl(N.n24,"item")+" in 24 hours</small>",sev:N.max24>=7,s:tp?esc(tp.title):"No nuclear-related items in 7 days",c:bars(cols(N),{labels:1,days:dayKeys(N)}),
    t:"The Wire &middot; "+pl(N.n7,"item")+" in 7 days",
    x:'<p><b>Latest.</b></p><ul class="bna-hl">'+(hl3(N)||"<li>Nothing in 7 days.</li>")+'</ul>'+x(pl(N.n24,"item")+" in the last 24 hours ("+N.conf24+" confirmed by 2+ sources), highest rank "+N.max24+"/10.",
     "Wire items about nuclear strikes or threats, warheads, ICBMs, tactical weapons, nuclear tests, Zaporizhzhia and other plant risks, and the Doomsday Clock. Single-source items are marked. Tap a day bar for that day's stories. Red marks rank 7 and up.",
     "High: an item ranked 8+ in 24 hours. Elevated: rank 6+ or 3+ confirmed items. Watch: any item. Low: none. Our wording, from Wire ranks; not an official alert level.")})}else none("c_nuke");
  if(P){var tq=(P.latest||[])[0],cp=card("el_disp");if(cp)cp._bnaO=P;
   put("el_disp",{v:P.n24?pl(P.n24,"report")+" <small>in 24 hours</small>":"Quiet <small>in 24 hours</small>",sev:P.max24>=7,s:tq?esc(tq.title):"No reports in 7 days",c:bars(cols(P),{labels:1,days:dayKeys(P)}),
    t:"The Wire &middot; "+pl(P.n7,"report")+" in 7 days",
    x:'<p><b>Latest 3.</b></p><ul class="bna-hl">'+(hl3(P)||"<li>Nothing in 7 days.</li>")+'</ul>'+x(pl(P.n24,"report")+" in the last 24 hours.",
     "U.S. reports about polling places, vote counting, certification, lawsuits, recounts, voter access, and Democratic or Republican party legal and monitoring actions. Single-source items are marked; check the linked sources. Tap a day bar for that day's stories. Red marks rank 7 and up.","")})}else none("el_disp")}
 function board(D){LASTD=D;el(D);spc(D);
  var C=D.conf||{},H=D.health||{},R=D.hard||{};
  wg("c_il",C.il,"Conflict stories on The Wire that mention Israel, Gaza, Lebanon, Yemen or the Houthis.");
  wg("c_ir",C.ir,"Conflict stories on The Wire that mention Iran.");
  wg("c_ru",C.ru,"Conflict stories on The Wire that mention Russia or Ukraine.");
  wg("c_uk",C.uk,"Conflict and security stories about the UK and London from The Wire and major outlets (BBC, Guardian, Sky News and others): terror, protests and disorder, cyber attacks and state threats.");
  wg("c_other",C.other,"Conflict stories on The Wire from every other region.");
  wg("h_ebola",H.ebola,"Stories on The Wire about Ebola (and the related Marburg virus).");
  wg("h_measles",H.measles,"Stories on The Wire about measles.");
  wg("h_other",H.other,"Other outbreak and disease stories on The Wire: cholera, dengue, bird flu, mpox and more.");
  wg("food",R.food,"Stories on The Wire plus world news feeds about food supply, shortages, recalls, shipping, grain, fertilizer and supply chains.");
  wg("unrest",R.unrest,"Protests, riots, clashes, curfews, crackdowns, general strikes, coups and troop deployments in the U.S. and worldwide, from The Wire and major outlets. One entry per event.");
  var M=D.comms;if(M){var bad=(M.isp_bad||[]).concat(M.cloud_bad||[]),N=D.net||{};
   put("comms",{v:bad.length?pl(bad.length,"provider issue"):"All clear",sev:bad.length>=3,
    s:(M.isp_bad&&M.isp_bad.length?esc(M.isp_bad.map(function(z){return z.src}).join(", "))+" reporting problems":"Carriers normal: "+esc((M.isp||[]).join(", ")))+(M.cloud_bad&&M.cloud_bad.length?" &middot; "+esc(M.cloud_bad.map(function(z){return z.src.replace(/ \(.*\)/,"")+": "+z.status}).join("; ")):""),
    c:line(N.series||[],{lo:0,hi:3,from:"24 hours ago"}),t:"Provider status pages &middot; "+esc(et(M.t)),
    x:x(bad.length?bad.map(function(z){return"<b>"+esc(z.src)+"</b>: "+esc(z.status)}).join("; ")+".":"Every monitored carrier, internet, cloud and DNS provider reports normal operation.",
     "We check "+(M.isp_n||0)+" U.S. phone and home internet carriers and "+(M.cloud_n||0)+" cloud, DNS and app services every few minutes. The chart counts providers with a problem at each check.",
     "Operational, Notice, Degraded, Major outage.")})}else none("comms");
  var q=D.quake;if(q&&q.sig&&q.map){var C2=["Minor","Light","Moderate","Strong","Major","Great"],b=q.sig,m=+b.mag,ci=Math.min(5,Math.max(0,Math.floor(m)-3)),mp=q.map;
   var map='<svg class="bna-map" viewBox="0 0 300 165" preserveAspectRatio="xMidYMid slice" focusable="false"><rect class="sea" width="300" height="165"/><path class="land" d="'+mp.d+'"/><circle class="ring" cx="'+mp.x+'" cy="'+mp.y+'" r="14"/><circle class="dot" cx="'+mp.x+'" cy="'+mp.y+'" r="4.5"/></svg>';
   put("quake",{v:esc(C2[ci])+" <small>M"+m.toFixed(1)+"</small>",sev:m>=7,s:esc(b.place||"")+" &middot; "+esc(et(b.t)),c:map,t:"USGS &middot; "+pl(q.n24,"quake")+" M2.5+ in 24 hours",
    x:x("The latest quake of magnitude 5 or more was <b>"+esc(C2[ci].toLowerCase())+"</b>, M"+m.toFixed(1)+", "+esc(b.place||"")+", at "+esc(et(b.t))+(b.tsunami?". USGS flagged it for tsunami review.":".")+" Last 24 hours by magnitude:</p>"+bars(q.classes.map(function(v,i){return{v:i>=4?[0,0,v]:[0,v],l:["<4","4","5","6","7","8+"][i]}}),{labels:1})+"<p>",
     "Magnitude 5 and up is where quakes start to damage buildings and disrupt daily life. Each whole step is about 32 times more energy.",
     "USGS classes: light 4 to 4.9, moderate 5 to 5.9, strong 6 to 6.9, major 7 to 7.9, great 8 and up.")})}
  if(!TK)TK=setInterval(function(){if(!document.hidden&&LASTD)try{el(LASTD)}catch(e){}},30000);
 }
 // Drawer motion (t1276u): open and close slide the panel's height with ease-in-out while the content fades and settles.
 // Interrupt-safe (a second tap reverses from the current height), animates content swaps while open (day bars),
 // ends at height:auto so live refreshes reflow normally, and is instant under prefers-reduced-motion.
 var DMS=380,RM=window.matchMedia?window.matchMedia("(prefers-reduced-motion: reduce)"):null;
 function dDone(p,g,open){if(p._bnaG!==g)return;clearTimeout(p._bnaT);p.classList.remove("bna-dz","bna-dz0");p.style.height="";if(!open)p.hidden=true}
 function drawer(p,open,from){var g=(p._bnaG||0)+1;p._bnaG=g;clearTimeout(p._bnaT);
  if(RM&&RM.matches||!p.animate&&!("transition" in p.style)){p.classList.remove("bna-dz","bna-dz0");p.style.height="";p.hidden=!open;return}
  var wasHidden=p.hidden,cur=wasHidden?0:(from!=null?from:p.getBoundingClientRect().height);
  p.hidden=false;p.classList.remove("bna-dz","bna-dz0");p.style.height="";
  var to=open?p.getBoundingClientRect().height:0;
  if(Math.abs(to-cur)<1){dDone(p,g,open);return}
  if(wasHidden)p.classList.add("bna-dz0");p.style.height=cur+"px";void p.offsetHeight;
  p.classList.add("bna-dz");void p.offsetHeight;p.classList.toggle("bna-dz0",!open);p.style.height=to+"px";
  var end=function(e){if(e&&(e.target!==p||e.propertyName!=="height"))return;p.removeEventListener("transitionend",end);dDone(p,g,open)};
  p.addEventListener("transitionend",end);p._bnaT=setTimeout(end,DMS+120)}
 function toggle(c,open,from){var b=c.querySelector(".bna-mh"),p=c.querySelector(".bna-mx");b.setAttribute("aria-expanded",open?"true":"false");c.classList.toggle("bna-open",open);drawer(p,open,from)}
 function pickDay(c,day){
   var o=c._bnaO||{},prev=c.getAttribute("data-day"),open=c.classList.contains("bna-open");
   if(prev===day&&open){toggle(c,false);c.removeAttribute("data-day");
    c.querySelectorAll(".bna-barday").forEach(function(b){b.setAttribute("aria-selected","false");b.classList.remove("on")});return}
   c.setAttribute("data-day",day);
   c.querySelectorAll(".bna-barday").forEach(function(b){var on=b.getAttribute("data-day")===day;b.setAttribute("aria-selected",on?"true":"false");b.classList.toggle("on",on)});
   var px=c.querySelector(".bna-mx"),h0=open&&px&&!px.hidden?px.getBoundingClientRect().height:null;
   var xel=c.querySelector('[data-f="x"]');if(xel)xel.innerHTML=dayList(o,day)+x(
    ((o.top)?'Top overall: <a class="bna-lnk" href="'+esc(o.top.url)+'"'+(o.top.ext?' target="_blank" rel="noopener"':"")+'>'+esc(o.top.title)+'</a>.':""),
    (o.src?"Bars count stories per day for 7 days from The Wire plus world news feeds (BBC, Guardian, Sky, Al Jazeera and other major outlets), one entry per event. Outlet count shows how many outlets reported it.":"Bars count Wire stories per day for 7 days.")+" Red marks rank 7 and up.","Rank 0 to 3 low, 4 to 6 notable, 7 to 10 high severity.");
   toggle(c,true,h0)}
 S.addEventListener("click",function(e){
  var dayBtn=e.target.closest&&e.target.closest(".bna-barday");
  if(dayBtn){e.preventDefault();e.stopPropagation();var c=dayBtn.closest(".bna-mc");if(c&&dayBtn.getAttribute("data-day"))pickDay(c,dayBtn.getAttribute("data-day"));return}
  var b=e.target.closest&&e.target.closest(".bna-mh");if(!b)return;var c=b.closest(".bna-mc");
  if(c&&c.getAttribute("data-day")&&b.getAttribute("aria-expanded")==="true"){c.removeAttribute("data-day");c.querySelectorAll(".bna-barday").forEach(function(x){x.setAttribute("aria-selected","false");x.classList.remove("on")})}
  toggle(c,b.getAttribute("aria-expanded")!="true")});
 S.addEventListener("keydown",function(e){var b=e.target.closest&&e.target.closest(".bna-barday");if(!b)return;
  if(e.key==="Enter"||e.key===" "){e.preventDefault();b.click()}
  if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();var all=[].slice.call(S.querySelectorAll(".bna-barday:not([disabled])")),i=all.indexOf(b),n=e.key==="ArrowRight"?i+1:i-1;if(all[n])all[n].focus()}});
 return render;
 })();
 function get(u,f){return fetch(u,{credentials:"same-origin"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){if(j&&!j.pending)f(j)}).catch(function(){})}
 window.BNA={had:false,render:function(h,dd){try{if(h&&h.main&&h.main.length){renderHome(h);BNA.had=true}}catch(e){}try{if(dd&&dd.now)renderDash(dd)}catch(e){}},
  refresh:function(){get("/api/apple/home",function(j){BNA.render(j,null)});get("/api/apple/dash",function(j){BNA.render(null,j)})}};
})();
