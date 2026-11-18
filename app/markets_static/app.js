/* /markets (Nov 18 2026): tiles + debt clock. Polls /api/markets/data every 60 s (server caches upstream); Refresh pulls now. */
(function(){"use strict";
var d=document,W=window,D=null,RM=W.matchMedia&&W.matchMedia("(prefers-reduced-motion: reduce)").matches;
function $(s){return d.querySelector(s)}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function fmt(v,dp){if(v==null||isNaN(v))return"n/a";if(dp==null)dp=Math.abs(v)>=1000?0:Math.abs(v)>=10?2:Math.abs(v)>=1?3:4;return v.toLocaleString("en-US",{minimumFractionDigits:dp,maximumFractionDigits:dp})}
function money(v){if(v==null)return"n/a";var a=Math.abs(v);return(v<0?"-":"")+"$"+(a>=1e12?(a/1e12).toFixed(2)+"T":a>=1e9?(a/1e9).toFixed(1)+"B":a>=1e6?(a/1e6).toFixed(1)+"M":fmt(a,0))}
function spark(xs){if(!xs||xs.length<2)return"";var mn=Math.min.apply(0,xs),mx=Math.max.apply(0,xs),r=mx-mn||1,n=xs.length-1;
  return'<svg viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><path d="'+xs.map(function(v,i){return(i?"L":"M")+(i/n*100).toFixed(1)+" "+(28-(v-mn)/r*26).toFixed(1)}).join("")+'"/></svg>'}
function chg(p,sev){if(p==null)return'<span class="mk-tc mk-dn2">n/a</span>';var s=sev&&Math.abs(p)>=sev,cls=s?"mk-sev":p>=0?"mk-up":"mk-dn2";
  return'<span class="mk-tc '+cls+'">'+(p>=0?"\u25B2 +":"\u25BC ")+p.toFixed(2)+"%</span>"}
function tile(t,isVol){var sev=t.severe&&t.chg_pct!=null&&Math.abs(t.chg_pct)>=t.severe;if(t.sym==="^VIX"&&t.price>=30)sev=true;
  return'<div class="mk-t'+(sev?" sev":"")+'"><div class="mk-tl"><span>'+esc(t.label)+'</span><small>'+esc(t.sub||"")+'</small></div><div class="mk-tp">'+fmt(t.price)+'</div>'+chg(t.chg_pct,t.severe)+spark(t.spark)+"</div>"}
function grid(list){return list&&list.length?'<div class="mk-tiles">'+list.map(function(t){return tile(t)}).join("")+"</div>":'<div class="mk-load">No data right now. It refreshes every minute.</div>'}
function sec(k,html){var n=d.querySelector('.mk-body[data-sec="'+k+'"]');if(n)n.innerHTML=html}
/* ---------- debt clock */
function debtNow(){if(!D||!D.debt||!D.debt.official)return null;var now=Date.now()/1000+(D._skew||0);return D.debt.official+D.debt.rate_per_s*(now-D.debt.t_official)}
function popNow(){var p=D&&D.pop;if(!p||!p.population)return 343e6;return p.population+(p.rate||0)*((Date.now()/1000)-(p.t||0))}
var dn=$("#mk_dn"),ds=$("#mk_ds"),dz=null;
function tickDebt(){var v=debtNow();if(v==null)return;var s="$"+Math.floor(v).toLocaleString("en-US");if(dn)dn.textContent=s;
  if(!dz)dz=d.getElementById("mk_dlive");if(dz)dz.textContent=s;var pc=d.getElementById("mk_pc");if(pc)pc.textContent="$"+Math.round(v/popNow()).toLocaleString("en-US");
  var it=d.getElementById("mk_int");if(it&&D.interest&&D.interest.per_s){var t0=new Date();t0.setHours(0,0,0,0);it.textContent="$"+Math.round(D.interest.per_s*((Date.now()-t0)/1000)).toLocaleString("en-US")}}
function renderDebt(){var b=D.debt||{},i=D.interest||{};if(!b.official){sec("debt",'<div class="mk-load">Treasury data is unavailable right now.</div>');return}
  var perDay=b.rate_per_s*86400,dt=new Date(b.date+"T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
  if(ds)ds.textContent="Estimate. Official total "+money(b.official)+" on "+dt+" (U.S. Treasury). Ticking at the recent average of "+money(perDay)+" a day.";
  sec("debt",'<div class="mk-big">'+
   '<div class="mk-t"><div class="mk-tl"><span>National debt, estimated now</span></div><div class="mk-tp" id="mk_dlive">&nbsp;</div><span class="mk-tc mk-dn2">+'+money(b.rate_per_s)+' a second</span></div>'+
   '<div class="mk-t"><div class="mk-tl"><span>Per U.S. resident</span></div><div class="mk-tp" id="mk_pc">&nbsp;</div><span class="mk-tc mk-dn2">'+fmt(popNow()/1e6,1)+' million people</span></div>'+
   '<div class="mk-t"><div class="mk-tl"><span>Official total</span><small>'+esc(dt)+'</small></div><div class="mk-tp">'+money(b.official)+'</div><span class="mk-tc mk-dn2">'+(b.day_change>=0?"+":"")+money(b.day_change)+' on the last update</span></div>'+
   '<div class="mk-t"><div class="mk-tl"><span>Held by the public</span></div><div class="mk-tp">'+money(b.public)+'</div><span class="mk-tc mk-dn2">Intragovernmental '+money(b.intragov)+'</span></div>'+
   (i.month?'<div class="mk-t"><div class="mk-tl"><span>Interest cost</span><small>'+esc(i.date||"")+'</small></div><div class="mk-tp">'+money(i.month)+'</div><span class="mk-tc mk-dn2">in one month, about '+money(i.per_s*86400)+' a day</span></div>'+
    '<div class="mk-t"><div class="mk-tl"><span>Interest so far today</span></div><div class="mk-tp" id="mk_int">&nbsp;</div><span class="mk-tc mk-dn2">estimate, since midnight</span></div>':"")+
   '</div><p class="mk-note">The ticking figures are estimates: the last official total plus the average daily change since '+esc(b.rate_ref_date)+'. The Treasury publishes the official number once each business day (<a href="'+esc(b.src)+'" rel="noopener" target="_blank">Debt to the Penny</a>). Per-resident figure uses the <a href="https://www.census.gov/popclock/" rel="noopener" target="_blank">Census population clock</a>.</p>');
  tickDebt()}
/* ---------- yields */
function renderYields(y){if(!y||!y.tenors||!y.tenors.length){sec("yields",'<div class="mk-load">Treasury curve unavailable right now.</div>');return}
  var cells=["3 Mo","2 Yr","5 Yr","10 Yr","30 Yr"].filter(function(k){return y.pts[k]}).map(function(k){var p=y.pts[k],dlt=p.prev!=null?Math.round((p.now-p.prev)*100):null;
   return'<div class="mk-t"><div class="mk-tl"><span>US '+esc(k.replace(" Mo","-month").replace(" Yr","-year"))+'</span></div><div class="mk-tp">'+fmt(p.now,2)+'%</div><span class="mk-tc '+(dlt!=null&&Math.abs(dlt)>=20?"mk-sev":"mk-dn2")+'">'+(dlt==null?"":(dlt>=0?"+":"")+dlt+" bp on the day")+"</span></div>"});
  function sp(lbl,v){var inv=v!=null&&v<0;return'<div class="mk-t"><div class="mk-tl"><span>'+lbl+'</span></div><div class="mk-tp">'+(v==null?"n/a":(v>=0?"+":"")+v+" bp")+'</div><span class="mk-tc mk-dn2">'+(v==null?"":inv?"Inverted: a classic recession warning":"Normal (not inverted)")+"</span></div>"}
  cells.push(sp("Curve 10y minus 2y",y.s2s10));cells.push(sp("Curve 10y minus 3m",y.s3m10));
  var n=y.now||[],a=y.month_ago||[],all=n.concat(a).filter(function(v){return v!=null}),mn=Math.min.apply(0,all)-.1,mx=Math.max.apply(0,all)+.1,L=y.tenors.length-1;
  function path(xs){return xs.map(function(v,i){return v==null?"":(i?"L":"M")+(40+i/L*540).toFixed(1)+" "+(160-(v-mn)/(mx-mn)*140).toFixed(1)}).join("")}
  var ticks=y.tenors.map(function(t,i){return i%2&&i!==L?"":'<text x="'+(40+i/L*540).toFixed(0)+'" y="176" text-anchor="middle">'+esc(t.replace(" Mo","m").replace(" Month","m").replace(" Yr","y"))+"</text>"}).join("");
  var gl=[0,.5,1].map(function(f){var v=mn+(mx-mn)*f,yy=160-f*140;return'<line class="ax" x1="40" x2="580" y1="'+yy+'" y2="'+yy+'"/><text x="34" y="'+(yy+3)+'" text-anchor="end">'+v.toFixed(2)+"%</text>"}).join("");
  sec("yields",'<div class="mk-tiles">'+cells.join("")+'</div><div class="mk-curve"><svg viewBox="0 0 600 182" preserveAspectRatio="none" role="img" aria-label="U.S. Treasury yield curve">'+gl+'<path class="ago" d="'+path(a)+'"/><path class="now" d="'+path(n)+'"/>'+ticks+
   '</svg><div class="mk-lg"><span><i></i>'+esc(y.date||"latest")+'</span><span><i class="a"></i>One month earlier</span></div></div><p class="mk-note">Official end-of-day par yields from the <a href="'+esc(y.src||"https://home.treasury.gov/")+'" rel="noopener" target="_blank">U.S. Treasury</a>.</p>')}
function renderStress(st){if(!st||!st.length)return"";return'<div class="mk-big" style="margin-top:18px">'+st.slice(0,6).map(function(s){var hi=/high|severe|stress/i.test(s.level||"");
  return'<div class="mk-t'+(hi?" sev":"")+'"><div class="mk-tl"><span>'+esc(s.k)+'</span><small>'+esc(s.level||"")+'</small></div><div class="mk-tp">'+esc(s.value)+'</div><span class="mk-tc mk-dn2" style="line-height:1.4">'+esc(s.rule||"")+"</span></div>"}).join("")+"</div>"}
function render(){var m=D.markets||{};renderDebt();
  ["metals","us","world","fx"].forEach(function(k){sec(k,grid(m[k]))});
  var cm=m.crypto_mkt||{};sec("crypto",grid(m.crypto)+(cm.mcap?'<p class="mk-note">Total crypto market '+money(cm.mcap)+' ('+(cm.chg>=0?"+":"")+(cm.chg||0).toFixed(1)+'% in 24 hours), Bitcoin share '+(cm.btc_dom||0).toFixed(1)+'%. Stablecoins under $0.98 trigger a Wire alert.</p>':""));
  sec("vol",grid(m.vol)+renderStress(m.stress)+'<p class="mk-note">VIX above 30 or a 20% jump, and moves past each market\u2019s alert line, show in red and post to the Wire.</p>');
  renderYields(m.yields);
  var st=$("#mk_stat");if(st){var u=m.updated?new Date(m.updated):null;st.textContent=(u?"Prices updated "+u.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",timeZoneName:"short"})+". ":"")+(m.stale?"Some sources are slow; showing the last good data. ":"")+"Delayed quotes; this page refreshes every minute."}}
var busy=false;
function load(force){if(busy)return;busy=true;var b=$("#mk_ref");if(b)b.setAttribute("aria-busy","true");
  fetch("/api/markets/data"+(force?"?t="+Date.now():""),{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){D=j;D._skew=j.server_time?j.server_time-Date.now()/1000:0;render()})
  .catch(function(){var st=$("#mk_stat");if(st)st.textContent="Could not reach the server. Retrying in a minute."}).then(function(){busy=false;if(b)b.removeAttribute("aria-busy")})}
function syncBar(){var b=d.getElementById("w2_bar");if(b)d.documentElement.style.setProperty("--mk-bar",b.offsetHeight+"px")}syncBar();W.addEventListener("resize",syncBar);
var rb=$("#mk_ref");if(rb)rb.addEventListener("click",function(){load(true)});
load(false);setInterval(function(){if(!d.hidden)load(false)},60000);setInterval(tickDebt,RM?1000:100);
/* full-screen loop on desktop/tablet only; phones, reduced motion and Save-Data keep the still */
(function(){var v=d.querySelector(".mk-vid"),n=navigator.connection||{};if(!v||W.innerWidth<=700||RM||n.saveData)return;
  setTimeout(function(){[["webm","video/webm"],["mp4","video/mp4"]].forEach(function(a){var s=d.createElement("source");s.src=v.getAttribute("data-"+a[0]);s.type=a[1];v.appendChild(s)});
    v.muted=true;v.autoplay=true;v.preload="auto";v.addEventListener("playing",function(){v.classList.add("on")},{once:true});v.load();var p=v.play();if(p&&p.catch)p.catch(function(){})},300)})();
})();
