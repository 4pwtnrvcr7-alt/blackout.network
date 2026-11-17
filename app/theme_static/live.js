/* /live overview: gauges, tiles, top signals, dot map, rank spread, alerts per day, categories. Data: /api/live/summary (60 s cache). */
(function(){
var d=document,$=function(id){return d.getElementById(id)},root=$("bntl");if(!root)return;
var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var band=function(r){return r>=7?"h":r>=4?"e":"c"},col={c:"#3DDC97",e:"#FFB020",h:"#FF4D4F"},word={c:"Calm",e:"Elevated",h:"High"};
var rname={0:"Noise",1:"Background",2:"Minor",3:"Minor regional",4:"Regional",5:"Significant",6:"Serious",7:"Major",8:"Severe",9:"Critical",10:"Catastrophic"};
var esc=function(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})};
function count(el,to,dec){dec=dec||0;if(!el)return;if(reduce){el.textContent=to.toFixed(dec);return}var t0=performance.now();(function f(t){var p=Math.min(1,(t-t0)/1400),e=1-Math.pow(1-p,3);el.textContent=(to*e).toFixed(dec);if(p<1)requestAnimationFrame(f)})(t0)}
function arc(cx,cy,r,a0,a1){var p=function(a){return [cx+r*Math.cos(a*Math.PI/180),cy+r*Math.sin(a*Math.PI/180)]},s=p(a0),e=p(a1);return "M"+s[0]+" "+s[1]+"A"+r+" "+r+" 0 "+(a1-a0>180?1:0)+" 1 "+e[0]+" "+e[1]}
var FILTER='<filter id="bntl_gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
function gauge(v,top,S){S=S||{};var A0=150,A1=390,cx=200,cy=190,r=150,ang=function(x){return A0+(A1-A0)*x/10},b=band(Math.floor(v));
 var s='<svg viewBox="0 0 400 330" role="img" aria-label="Top stories average rank '+v.toFixed(1)+' of 10, '+word[b]+'"><defs>'+FILTER+'<linearGradient id="bntl_gf" x1="0" x2="1"><stop offset="0" stop-color="#3DDC97"/><stop offset=".45" stop-color="#FFB020"/><stop offset="1" stop-color="#FF4D4F"/></linearGradient><radialGradient id="bntl_core"><stop offset="0" stop-color="'+col[b]+'" stop-opacity=".22"/><stop offset="1" stop-color="'+col[b]+'" stop-opacity="0"/></radialGradient></defs><circle cx="'+cx+'" cy="'+cy+'" r="118" fill="url(#bntl_core)"/>';
 [[0,3.5,"c"],[3.5,6.5,"e"],[6.5,10,"h"]].forEach(function(z){s+='<path d="'+arc(cx,cy,r,ang(z[0])+1,ang(z[1])-1)+'" stroke="'+col[z[2]]+'" stroke-opacity=".16" stroke-width="18" fill="none" stroke-linecap="round"/>'});
 for(var i=0;i<=10;i++){var a=ang(i)*Math.PI/180,c=Math.cos(a),sn=Math.sin(a);s+='<line x1="'+(cx+(r-24)*c)+'" y1="'+(cy+(r-24)*sn)+'" x2="'+(cx+(r-31)*c)+'" y2="'+(cy+(r-31)*sn)+'" stroke="rgba(240,240,250,.35)" stroke-width="2" stroke-linecap="round"/><text x="'+(cx+(r+26)*c)+'" y="'+(cy+(r+26)*sn+4)+'" text-anchor="middle" font-family="Montserrat" font-weight="600" font-size="12" fill="rgba(240,240,250,.5)">'+i+'</text>'}
 s+='<path id="bntl_arc" d="'+arc(cx,cy,r,A0,ang(10))+'" stroke="url(#bntl_gf)" stroke-width="18" fill="none" stroke-linecap="round" filter="url(#bntl_gl)" pathLength="100" stroke-dasharray="0 100"/>';
 s+='<g id="bntl_dot" style="transform-origin:'+cx+'px '+cy+'px;transform:rotate('+A0+'deg)"><circle cx="'+(cx+r)+'" cy="'+cy+'" r="12" fill="#05060a" stroke="'+col[b]+'" stroke-width="4" filter="url(#bntl_gl)"/></g>';
 s+='<text id="bntl_num" x="'+cx+'" y="'+(cy+6)+'" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="84" fill="#F0F0FA">0.0</text><text x="'+cx+'" y="'+(cy+44)+'" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="17" letter-spacing="4" fill="'+col[b]+'">'+word[b].toUpperCase()+'</text><text x="'+cx+'" y="'+(cy+88)+'" text-anchor="middle" font-family="Inter" font-size="13" fill="rgba(240,240,250,.55)">out of 10</text></svg>';
 $("bntl_g").innerHTML=s;var ar=$("bntl_arc"),dot=$("bntl_dot");
 requestAnimationFrame(function(){if(!reduce){ar.style.transition="stroke-dasharray 1.6s cubic-bezier(.2,.7,.2,1)";dot.style.transition="transform 1.6s cubic-bezier(.2,.7,.2,1)"}
  setTimeout(function(){ar.setAttribute("stroke-dasharray",(v*10)+" 100");dot.style.transform="rotate("+ang(v)+"deg)"},120)});
 count($("bntl_num"),v,1);
 $("bntl_gt").innerHTML="The "+(S.level_n||"")+" top stories right now"+(S.level_hi?" (every High alert, rank 7+, on The Wire)":" (the highest-ranked alerts on The Wire)")+" average <b>"+v.toFixed(1)+"</b> out of 10."+(top?' The highest active alert is a <b style="color:'+col[band(top)]+'">'+top+" ("+(rname[top]||word[band(top)])+")</b>.":"")}
var ICON={"natural disaster":'<path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A3.5 3.5 0 0 1 17 18z"/>',"disease":'<path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z"/>',"war/conflict":'<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',"financial":'<path d="M3 20h18M5 16l4-5 4 3 6-8"/>',"political":'<path d="M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10M2 10l10-6 10 6z"/>',"cyber":'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'};
var CAT={"natural disaster":"Weather & quakes","disease":"Health","war/conflict":"Conflict","financial":"Markets","political":"Politics","cyber":"Cyber"};
function render(S,land,only){var on=function(k){return !only||only===k};LAST=S;stamps(S,only);
 $("bntl_asof").innerHTML="<i></i>Live &middot; last scan "+esc(S.last_scan_et)+' &middot; <a href="/?intro=1">Watch the intro</a>';
if(on("g")){ var top=0;S.top.forEach(function(t){top=Math.max(top,t.rank)});gauge(S.level,S.max_rank||top,S);}
if(on("t")){ ["h","e","c"].forEach(function(k){var n=S.bands[{h:"high",e:"elevated",c:"calm"}[k]]||0;count($("bntl_t"+k),n,0);var m=$("bntl_m"+k);m.innerHTML="<i></i>";setTimeout(function(){m.firstChild.style.width=(S.wire?100*n/S.wire:0)+"%"},150)});
 var p=S.sources_total?S.sources_ok/S.sources_total:0,R=40,C=2*Math.PI*R;
 $("bntl_ring").innerHTML='<svg viewBox="0 0 100 100" role="img" aria-label="'+Math.round(p*100)+' percent of sources online"><circle cx="50" cy="50" r="'+R+'" stroke="rgba(124,196,255,.14)" stroke-width="9" fill="none"/><circle id="bntl_sa" cx="50" cy="50" r="'+R+'" stroke="#7CC4FF" stroke-width="9" fill="none" stroke-linecap="round" stroke-dasharray="0 '+C+'" transform="rotate(-90 50 50)" style="transition:stroke-dasharray 1.6s cubic-bezier(.2,.7,.2,1)"/><text x="50" y="57" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="21" fill="#F0F0FA">'+Math.round(p*100)+'%</text></svg>';
 setTimeout(function(){var a=$("bntl_sa");if(a)a.setAttribute("stroke-dasharray",(C*p)+" "+C)},150);
 $("bntl_src").innerHTML="<b>"+S.sources_ok+" of "+S.sources_total+"</b> feeds answered the last scan. "+(S.fetched||0).toLocaleString()+" items checked, "+(S.new_items||0)+" new.";}
if(on("s")){ $("bntl_sigs").innerHTML=S.top.length?S.top.map(function(t){var b=band(t.rank),seg="";for(var i=0;i<10;i++){var bb=band(i+1);seg+='<i style="'+(i<t.rank?"background:"+col[bb]+";box-shadow:0 0 6px "+col[bb]+"66":"")+'"></i>'}
  return '<div class="bnt-card l-sig"><div class="l-top"><span class="l-cat"><svg viewBox="0 0 24 24" aria-hidden="true">'+(ICON[t.cat]||"")+"</svg>"+esc(CAT[t.cat]||t.cat||"Alert")+'</span><span class="l-rk" aria-label="Rank '+t.rank+' of 10"><span class="l-segs" aria-hidden="true">'+seg+'</span><b style="color:'+col[b]+'">'+t.rank+"</b><small>/10</small></span></div><h4><a class='l-sl' href='"+esc(t.url)+"'>"+esc(t.title)+'</a></h4><button type="button" class="l-xp" aria-expanded="false" hidden>More</button><div class="l-meta"><span class="l-pill '+b+'">'+esc(rname[t.rank]||word[b])+"</span>"+(t.rising?'<span class="l-pill up">Rising</span>':"")+(t.loc?"<span>"+esc(t.loc)+"</span>":"")+"<span>"+t.sources+" source"+(t.sources==1?"":"s")+"</span><span>Seen "+esc(t.first_seen_et)+"</span></div></div>"}).join(""):'<p class="l-empty">No ranked alerts right now.</p>';
 clampBtns();}
 // map
if(on("m")){ var W=360,H=155,x=function(l){return l+180},y=function(a){return (82-a)*(H/155)};
 var s='<svg viewBox="0 0 '+W+" "+H+'" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Map of '+S.geo.length+' located alerts"><defs><filter id="bntl_g3" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><g fill="rgba(240,240,250,.13)">';
 (land||[]).forEach(function(p){s+='<circle cx="'+x(p[0])+'" cy="'+y(p[1])+'" r=".62"/>'});s+="</g>";
 var pts=S.geo.slice().sort(function(a,b){return a[2]-b[2]}),cn={c:0,e:0,h:0};
 pts.forEach(function(g,i){var b=band(g[2]),rad=b==="h"?2.1:b==="e"?1.5:1.1;cn[b]++;if(g[0]<-73||g[0]>82)return;
  s+='<circle cx="'+x(g[1]).toFixed(1)+'" cy="'+y(g[0]).toFixed(1)+'" r="'+rad+'" fill="'+col[b]+'" fill-opacity="'+(b==="c"?.7:.95)+'" filter="url(#bntl_g3)">'+(b==="h"&&!reduce?'<animate attributeName="r" values="'+rad+";"+(rad+1.6)+";"+rad+'" dur="2.4s" begin="'+((i%7)*.3)+'s" repeatCount="indefinite"/>':"")+"</circle>"});
 $("bntl_map").innerHTML=s+"</svg>";$("bntl_maph").textContent=pts.length+" located alerts · "+cn.h+" high, "+cn.e+" elevated, "+cn.c+" calm";}
 // rank spread
if(on("d")){ var mx=1;for(var k=0;k<=10;k++)mx=Math.max(mx,S.ranks[k]||0);var h="";
 for(k=0;k<=10;k++){var n=S.ranks[k]||0,b2=band(k);h+='<div><em>'+(n||"")+'</em><i data-h="'+(n?Math.max(4,100*n/mx):2)+'" style="background:linear-gradient(180deg,'+col[b2]+","+col[b2]+'55);box-shadow:0 0 14px '+col[b2]+'40"></i><span>'+k+"</span></div>"}
 $("bntl_dist").innerHTML=h;setTimeout(function(){[].forEach.call(d.querySelectorAll("#bntl_dist i"),function(e){e.style.height=e.getAttribute("data-h")+"%"})},200);}
 // alerts per day
if(on("v")){ var M=innerWidth<=900,VW=M?340:520,VH=M?220:200,pl=40,pr=10,pt=24,pb=30,V=S.volume||[],vm=1;V.forEach(function(v){vm=Math.max(vm,v.n)});var bw=(VW-pl-pr)/Math.max(1,V.length);
 var vs='<svg viewBox="0 0 '+VW+" "+VH+'" role="img" aria-label="Alerts logged per day"><defs><linearGradient id="bntl_vb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC21A"/><stop offset="1" stop-color="#FFC21A" stop-opacity=".25"/></linearGradient></defs>';
 [0,.5,1].forEach(function(f){var yy=pt+(VH-pt-pb)*(1-f);vs+='<line x1="'+pl+'" x2="'+(VW-pr)+'" y1="'+yy+'" y2="'+yy+'" stroke="rgba(240,240,250,.07)"/><text x="'+(pl-8)+'" y="'+(yy+4)+'" text-anchor="end" font-family="Montserrat" font-size="10.5" fill="rgba(240,240,250,.45)">'+Math.round(vm*f).toLocaleString()+"</text>"});
 V.forEach(function(v,i){var hh=(VH-pt-pb)*v.n/vm,xx=pl+i*bw+bw*.18,ww=bw*.64;vs+='<rect x="'+xx+'" y="'+(VH-pb-hh)+'" width="'+ww+'" height="'+hh+'" rx="5" fill="url(#bntl_vb)"/><text x="'+(xx+ww/2)+'" y="'+(VH-pb-hh-7)+'" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="11" fill="#F0F0FA">'+v.n.toLocaleString()+'</text><text x="'+(xx+ww/2)+'" y="'+(VH-9)+'" text-anchor="middle" font-family="Montserrat" font-weight="600" font-size="11" fill="rgba(240,240,250,.55)">'+esc(v.d)+"</text>"});
 $("bntl_vol").innerHTML=vs+"</svg>";}
 // categories
if(on("c")){ var cs=Object.keys(S.cats||{}).map(function(k){return [k,S.cats[k]]}).sort(function(a,b){return b[1]-a[1]}),cm=cs.length?cs[0][1]:1;
 $("bntl_cath").textContent="Items logged "+(S.today||"today");
 $("bntl_cats").innerHTML=cs.length?cs.map(function(c){return '<div class="l-catrow"><span>'+esc(c[0])+'</span><div class="b"><i data-w="'+(100*c[1]/cm)+'"></i></div><b>'+c[1].toLocaleString()+"</b></div>"}).join(""):'<p class="l-empty">Nothing logged yet today.</p>';
 setTimeout(function(){[].forEach.call(d.querySelectorAll("#bntl_cats i"),function(e){e.style.width=e.getAttribute("data-w")+"%"})},250);}
}
/* Top signals: three lines, then a More/Less toggle when the headline is longer (CoS Nov 17 1:00 AM). The card link is the headline, stretched over the card. */
function clampBtns(){[].forEach.call(d.querySelectorAll("#bntl_sigs .l-sig"),function(c){var h=c.querySelector("h4"),b=c.querySelector(".l-xp");if(!h||!b||c.classList.contains("full"))return;b.hidden=h.scrollHeight<=h.clientHeight+2})}
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("#bntl_sigs .l-xp");if(!b)return;e.preventDefault();e.stopPropagation();var c=b.closest(".l-sig"),o=!c.classList.contains("full");c.classList.toggle("full",o);b.setAttribute("aria-expanded",o?"true":"false");b.textContent=o?"Less":"More"});
var rzT;addEventListener("resize",function(){clearTimeout(rzT);rzT=setTimeout(clampBtns,200)});
var land=null,LAST=null,MODS=[["g","bntl_ug","the gauge"],["t","bntl_ut","the counts"],["s","bntl_us","top signals"],["m","bntl_um","the map"],["d","bntl_ud","rank spread"],["v","bntl_uv","alerts per day"],["c","bntl_uc","today's categories"]];
/* per-module refresh (Matt Nov 17 1:10 AM): each stamp shows the scan time and the next scan; its button reloads the summary and redraws only that module */
function stamps(S,only){if(!window.BNT||!BNT.up)return;var at=Date.parse(S.last_scan||S.generated||"")||Date.now(),iv=(S.interval||5)*60000,nx=at+iv;while(nx<Date.now()-30000)nx+=iv;
 MODS.forEach(function(m){if(only&&m[0]!==only)return;var el=$(m[1]);if(el)BNT.up(el,{label:m[2],at:at,next:nx,run:function(){return fetchS(true).then(function(T){if(T)render(T,land,m[0])})}})})}
function fetchS(fresh){return fetch("/api/live/summary"+(fresh?"?fresh=1":""),{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){return j&&j.ranks?j:null}).catch(function(){return null})}
function load(){Promise.all([fetch("/api/live/summary",{cache:"no-store"}).then(function(r){return r.json()}),land?Promise.resolve(land):fetch("/bnt/land.json").then(function(r){return r.json()}).catch(function(){return []})])
 .then(function(a){land=a[1];if(a[0]&&a[0].ranks)render(a[0],land)}).catch(function(){})}
load();setInterval(function(){if(!d.hidden&&root.getBoundingClientRect().height>0)load()},120000);
})();
