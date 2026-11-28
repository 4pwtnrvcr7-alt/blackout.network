/* Wire timeline (/wire). Windowed list, two-way paging, dim-in-place filters, anchored Condense (FLIP), live poll + refresh. */
(function(){"use strict";
var d=document,W=window,CFG=W.BN_TL||{cats:[],regions:[]};
var RM=W.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var DUR=RM?0:460,EASE="cubic-bezier(.22,.8,.24,1)";
var $=function(id){return d.getElementById(id)};
var list=$("tl_list"),foot=$("tl_foot"),ctl=$("tl_ctl"),pill=$("tl_now"),stat=$("tl_stat"),qIn=$("tl_q"),qX=$("tl_qx"),
    bCond=$("tl_cond"),bWhen=$("tl_when"),jump=$("tl_jump"),jq=$("tl_jq"),dIn=$("tl_date"),bTop=$("tl_top"),bClear=$("tl_clear"),
    bFilt=$("tl_filt"),sheet=$("tl_sheet"),chipsC=$("tl_chips_c"),chipsR=$("tl_chips_r"),badge=$("tl_fbadge"),
    locF=$("tl_locf"),locIn=$("tl_loc"),locLab=$("tl_loclab"),radBox=$("tl_rad"),timeBox=$("tl_time"),sevBox=$("tl_sev"),
    bar=$("w2_bar"),bRef=$("tl_ref"),bNew=$("tl_new"),elUpd=$("tl_upd");
if(!list)return;
var CAT={},REG={};CFG.cats.forEach(function(c){CAT[c.k]=c});CFG.regions.forEach(function(r){REG[r.k]=r});
var DAYH=52,BUF=1.25,DBG={};
/* ---------- state */
var items=[],seen={},rows=[],rendered=new Map(),Hc={},He={},exp=new Set();
var topCur=null,topEnd=true,botCur=null,botEnd=false,loading={o:0,n:0},gen=0;
var F={cats:new Set(),regs:new Set(),time:"",sev:"",loc:null,r:25},condensed=false,Q="",meta=null,total=0,tlTop=0,listH=0,padX=0,anim=false,crimeItems=[];
var NEW={},UPD={},GLOW={},SCANMSG="",pending=0,pollT=0,POLL=12000;
var SEEN_KEY="bn.wire.ref.v1";
var fS=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit",second:"2-digit"});
/* ---------- time (ET) */
var fD=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit"});
var fT=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",hour:"numeric",minute:"2-digit"});
var fL=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",weekday:"short",month:"short",day:"numeric",year:"numeric"});
var fF=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",weekday:"long",month:"long",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"});
function dt(s){return new Date(s)}
function dayKey(s){var p=fD.formatToParts(dt(s)),o={};p.forEach(function(x){o[x.type]=x.value});return o.year+"-"+o.month+"-"+o.day}
var todayK=dayKey(new Date().toISOString()),yK=dayKey(new Date(Date.now()-864e5).toISOString());
function dayLabel(k,s){return k===todayK?"Today":k===yK?"Yesterday":fL.format(dt(s))}
var fU=new Intl.DateTimeFormat("en-US",{timeZone:"UTC",weekday:"long",month:"long",day:"numeric",year:"numeric"}),fUs=new Intl.DateTimeFormat("en-US",{timeZone:"UTC",weekday:"short",month:"short",day:"numeric",year:"numeric"});
function tm(s){return fT.format(dt(s))}
function seenAt(it){return it.t}
/* ---------- helpers */
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
var qRx=null;
function hl(s){s=esc(s);return qRx?s.replace(qRx,"<mark>$1</mark>"):s}
function rkc(r){if(r==null)return"rn";return r>=7?"rh":"r"+Math.max(0,Math.min(6,r))}
var RN={0:"Noise",1:"Low",2:"Low",3:"Minor",4:"Elevated",5:"Notable",6:"Serious",7:"Major",8:"Severe",9:"Critical",10:"Catastrophic"};
function ticks(r){var h="";for(var i=1;i<=10;i++)h+='<i class="'+(r!=null&&i<=r?(r>=7?"on hot":"on"):"")+'"></i>';return'<span class="tl-ticks" aria-hidden="true">'+h+"</span>"}
function nFilt(){return F.cats.size+F.regs.size+(F.time?1:0)+(F.sev?1:0)+(F.loc?1:0)}
function active(){return nFilt()>0}
function miles(a,b,c,d){var p=Math.PI/180,x=0.5-Math.cos((c-a)*p)/2+Math.cos(a*p)*Math.cos(c*p)*(1-Math.cos((d-b)*p))/2;return 3958.8*2*Math.asin(Math.sqrt(Math.max(0,x)))}
function match(it){
  if(F.cats.size&&!F.cats.has(it.k))return false;
  if(F.regs.size&&!F.regs.has(it.g))return false;
  if(F.sev){var r=it.r==null?-1:it.r;if(F.sev==="lo"&&!(r>=0&&r<=3))return false;if(F.sev==="mid"&&!(r>=4&&r<=6))return false;if(F.sev==="hi"&&!(r>=7&&r<=10))return false}
  if(F.time){var tw=seenAt(it);if(F.time==="today"){if(dayKey(tw)!==todayK)return false}else if(new Date(tw).getTime()<Date.now()-Number(F.time)*864e5)return false}
  if(F.loc){if(it.crime)return true;if(it.lat==null||it.lon==null)return false;if(miles(F.loc.lat,F.loc.lon,it.lat,it.lon)>F.loc.r)return false}
  return true;
}
/* ---------- row html */
function itemHTML(it,open){
  var c=CAT[it.k]||CAT.other||{color:"#777",label:"Other"};
  var h='<button type="button" class="tl-hd" aria-expanded="'+(open?"true":"false")+'"><span class="tl-tm">'+(it["do"]?'<abbr title="Dated by day only">&mdash;</abbr>':esc(tm(seenAt(it))))+'</span><span class="tl-nd" aria-hidden="true"></span>'+
    '<span class="tl-tx"><span class="tl-h">'+hl(it.h)+'</span><span class="tl-s"><b class="tl-k">'+esc(c.label)+"</b>"+(it.a?'<b class="tl-ar">Archive</b>':"")+(it.s?hl(it.s):"")+"</span></span>"+
    '<span class="tl-rk '+rkc(it.r)+'" title="Rank '+(it.r==null?"n/a":it.r)+'">'+(it.r==null?"&ndash;":it.r)+"</span></button>";
  if(open)h+=drawerHTML(it);
  return h;
}
function lazyXu(it){
  /* rows the server has not pre-warmed arrive with no xu: fetch the 3-5 tag Post-on-X URL once, then fix the link */
  if(!it._xp){it._xp=1;fetch("/api/wire_tl/xu?id="+encodeURIComponent(it.id),{credentials:"same-origin"}).then(function(r){return r.ok?r.json():null}).then(function(j){
    if(!j||!j.xu)return;it.xu=j.xu;var a=document.querySelectorAll('a[data-xid="'+it.id+'"]');for(var i=0;i<a.length;i++)a[i].href=j.xu}).catch(function(){it._xp=0})}
  return""}
function drawerHTML(it){
  var r=it.r,cnt={},src=(it.l||[]).map(function(l){var nm=l.s||l.u.replace(/^https?:\/\/(www\.)?/,"").split("/")[0];cnt[nm]=(cnt[nm]||0)+1;if(cnt[nm]>1)nm+=" ("+cnt[nm]+")";return'<li><a href="'+esc(l.u)+'" target="_blank" rel="noopener nofollow">'+esc(nm)+'<span aria-hidden="true"> &#8599;</span></a></li>'}).join("");
  var when=it["do"]?fU.format(dt(seenAt(it)))+" (date only)":fF.format(dt(seenAt(it)))+" ET";
  var go=!it.a?'<a class="w2-btn tl-go" href="/wire/'+esc(it.id)+'">Full story <span aria-hidden="true">&rarr;</span></a>':
        ((it.l&&it.l[0])?'<a class="w2-btn tl-go" href="'+esc(it.l[0].u)+'" target="_blank" rel="noopener nofollow">View source record <span aria-hidden="true">&#8599;</span></a>':"");
  var xshare=(!it.a&&it.xu)?'<a class="w2-btn tl-go" href="'+esc(it.xu)+'" target="_blank" rel="noopener">Post on X</a>':
    (!it.a?'<a class="w2-btn tl-go" data-xid="'+esc(it.id)+'" href="/wire/'+esc(it.id)+'?s=x" target="_blank" rel="noopener">Post on X</a>'+lazyXu(it):"");
  return'<div class="tl-dr"><div class="tl-dri">'+(it.d?'<p class="tl-d">'+hl(it.d)+"</p>":"")+
    '<dl class="tl-facts"><div><dt>'+(it.a?"Archive rank":"Rank")+'</dt><dd class="tl-rkf '+rkc(r)+'">'+ticks(r)+"<b>"+(r==null?"&ndash;":r)+"</b><span>"+(r==null?"":esc(RN[r]||""))+"</span></dd></div>"+
    (it.c?"<div><dt>Confidence</dt><dd>"+esc(it.c)+"</dd></div>":"")+
    "<div><dt>"+(it.a?"Recorded":"Seen")+"</dt><dd>"+esc(when)+"</dd></div>"+
    (it.loc?"<div><dt>Where</dt><dd>"+esc(it.loc)+"</dd></div>":"<div><dt>Region</dt><dd>"+esc((REG[it.g]||{}).label||"")+"</dd></div>")+
    (it.a?"":"<div><dt>Reports</dt><dd>"+(it.n||1)+" report"+((it.n||1)===1?"":"s")+(it.f?" &middot; "+it.f+" source famil"+(it.f===1?"y":"ies"):"")+"</dd></div>")+"</dl>"+
    (it.a&&it.tg&&it.tg.length?'<p class="tl-tg">'+it.tg.map(esc).join(" ")+"</p>":"")+
    (src?'<p class="tl-sl">Sources</p><ul class="tl-src">'+src+"</ul>":"")+
    '<div class="tl-act">'+go+xshare+(it.a?'<span class="tl-arch">Archive record</span>':"")+"</div></div></div>";
}
/* ---------- rows model */
function rebuild(){
  var out=[],last=null,day=null,i,it,k,pins=[],rest=[];
  if(SCANMSG)out.push({key:"scan",scan:1,day:0,k:"scan",label:SCANMSG,n:0,m:0,top:0,hid:false});
  for(i=0;i<items.length;i++){if(items[i]._pin)pins.push(items[i]);else rest.push(items[i])}
  if(pins.length){
    day={key:"d:pin",day:1,k:"pin",label:"Updated",n:pins.length,m:0,top:0,hid:false,pin:1};out.push(day);
    for(i=0;i<pins.length;i++){day.n++;out.push({key:pins[i].id,it:pins[i],top:0,hid:false,day:0})}
  }
  for(i=0;i<rest.length;i++){it=rest[i];k=dayKey(seenAt(it));
    if(k!==last){day={key:"d:"+k,day:1,k:k,label:dayLabel(k,seenAt(it)),n:0,m:0,top:0,hid:false};out.push(day);last=k}
    day.n++;out.push({key:it.id,it:it,top:0,hid:false,day:0});}
  rows=out;flags();
}
function flags(){ /* match + hidden */
  var a=active(),day=null;
  for(var i=0;i<rows.length;i++){var r=rows[i];
    if(r.scan){r.hid=false;r.mt=true;continue}
    if(r.day){day=r;r.m=0;continue}
    r.mt=!a||match(r.it);if(day&&r.mt)day.m++;r.hid=condensed&&a&&!r.mt;}
  for(i=0;i<rows.length;i++){r=rows[i];if(r.day)r.hid=condensed&&a&&r.m===0}
}
function hOf(r){if(r.scan)return 48;if(r.day)return DAYH;return exp.has(r.key)?(He[r.key]||Hc[r.key]||96):(Hc[r.key]||est(r.it))}
var cw=360;
function est(it){var cpl=Math.max(18,(cw-130)/8.6);return 34+Math.min(2,Math.ceil(it.h.length/cpl))*22+20}
function layout(){var y=0;for(var i=0;i<rows.length;i++){var r=rows[i];r.top=y;if(!r.hid)y+=hOf(r)}listH=y;setH()}
function setH(){list.style.height=(listH+padX)+"px"}
function measureTop(){tlTop=list.getBoundingClientRect().top+W.scrollY}
/* measurer: exact heights before rows are ever shown */
var meas=d.createElement("div");meas.className="tl-list tl-meas";meas.setAttribute("aria-hidden","true");list.parentNode.appendChild(meas);
function measure(arr,open){
  if(!arr.length)return;meas.style.width=list.clientWidth+"px";
  meas.innerHTML=arr.map(function(it){return'<div class="tl-it'+(open?" open":"")+'">'+itemHTML(it,open)+"</div>"}).join("");
  var ch=meas.children;for(var i=0;i<ch.length;i++){var h=ch[i].offsetHeight;if(open)He[arr[i].id]=h;else Hc[arr[i].id]=h}
  meas.innerHTML="";
}
/* ---------- window rendering */
function idxAt(y){var lo=0,hi=rows.length-1,a=0;while(lo<=hi){var m=(lo+hi)>>1;if(rows[m].top<=y){a=m;lo=m+1}else hi=m-1}
  while(a>0&&rows[a].hid)a--;return a}
function rowAt(y){var i=idxAt(y);while(i<rows.length&&rows[i].hid)i++;return i}
function nodeFor(r){
  var n=rendered.get(r.key);if(n)return n;
  n=d.createElement("div");
  if(r.scan){n.className="tl-scanline";n.setAttribute("role","status");n.innerHTML="<span>"+esc(r.label)+"</span>"}
  else if(r.day){n.className="tl-day";n.innerHTML='<span>'+esc(r.label)+"</span>"}
  else{var c=CAT[r.it.k]||{color:"#777"};n.className="tl-it"+(exp.has(r.key)?" open":"");n.setAttribute("role","listitem");n.style.setProperty("--c",c.color);
    n.innerHTML=itemHTML(r.it,exp.has(r.key));n._r=r}
  n._k=r.key;list.appendChild(n);rendered.set(r.key,n);return n;
}
function isNew(id){return !!(NEW[id]&&Date.now()-NEW[id]<90000)}
function isUpdated(id){return !!(UPD[id]&&Date.now()-UPD[id]<90000)}
function isGlow(id){return !!(GLOW[id]&&Date.now()-GLOW[id]<2600)}
function paint(n,r){n.style.top=r.top+"px";n._r=r;if(r.scan)return;if(!r.day){var dim=!condensed&&!r.mt;if(n._dim!==dim){n._dim=dim;n.classList.toggle("dim",dim)}
    var nw=isNew(r.it.id),up=!nw&&isUpdated(r.it.id),gl=isGlow(r.it.id);
    if(n._new!==nw){n._new=nw;n.classList.toggle("fresh",nw)}
    if(n._upd!==up){n._upd=up;n.classList.toggle("updated",up)}
    if(n._glow!==gl){n._glow=gl;n.classList.toggle("glow",gl)}}else{var dd=active()&&!condensed&&r.m===0;if(n._dim!==dd){n._dim=dd;n.classList.toggle("dim",dd)}}}
function render(keep){
  var sy=W.scrollY,vh=W.innerHeight,y0=sy-tlTop-vh*BUF,y1=sy-tlTop+vh*(1+BUF),want=new Set();
  if(rows.length){for(var i=idxAt(Math.max(0,y0));i<rows.length&&rows[i].top<=y1;i++){var r=rows[i];if(r.hid)continue;want.add(r.key);paint(nodeFor(r),r)}}
  var gone=[];rendered.forEach(function(n,k){if(!want.has(k)){rendered.delete(k);if(keep)gone.push(n);else n.remove()}});
  return gone;
}
/* ---------- scroll anchoring */
function anchorRow(){ /* row at the viewport centre that is shown */
  var c=W.scrollY+W.innerHeight/2-tlTop;if(!rows.length)return null;var i=rowAt(c);if(i>=rows.length)i=rows.length-1;
  while(i>0&&(rows[i].hid||rows[i].top>c))i--;return rows[i]||null;
}
function keepAnchor(fn){ /* run fn (which rebuilds rows) and keep the first visible row's screen position */
  var sy=W.scrollY,a=null,off=0;
  if(rows.length&&sy+W.innerHeight>tlTop){var i=rowAt(Math.max(0,sy-tlTop+ctlH()));a=rows[i];if(a)off=a.top+tlTop-sy}
  var ak=a&&a.key;fn();layout();
  if(ak){for(var j=0;j<rows.length;j++)if(rows[j].key===ak){var ny=rows[j].top+tlTop-off;if(Math.abs(ny-sy)>.5)W.scrollTo(0,ny);break}}
  render();
}
function ctlH(){return ctl.getBoundingClientRect().bottom>0?ctl.getBoundingClientRect().bottom:0}
/* ---------- FLIP transition: change hidden/expanded state while one row stays put on screen */
function transition(mut,pin){
  measureTop();
  var sy=W.scrollY,vh=W.innerHeight,old=new Map(),cY=sy+vh/2-tlTop;
  rows.forEach(function(r){old.set(r.key,{top:r.top,hid:r.hid,h:r.hid?0:hOf(r)})});
  var before=new Map(rendered);
  mut();flags();layout();
  var a=null,target=null;
  if(pin){for(var i=0;i<rows.length;i++)if(rows[i].key===pin){a=rows[i];break}}
  if(!a){ /* the row under the viewport centre; if Condense removes it, the nearest surviving row (in time) takes its place */
    var ci=-1;for(i=0;i<rows.length;i++){var o0=old.get(rows[i].key);if(o0.hid)continue;if(o0.top<=cY)ci=i;else break}
    if(ci>=0&&!rows[ci].hid)a=rows[ci];
    else if(ci>=0){var c0=old.get(rows[ci].key);target=c0.top+tlTop-sy;
      for(var dd=1;dd<rows.length&&!a;dd++){var up=rows[ci-dd],dn=rows[ci+dd];
        if(dn&&!dn.hid&&!dn.day&&!old.get(dn.key).hid){a=dn;break}if(up&&!up.hid&&!up.day&&!old.get(up.key).hid){a=up;break}}}
  }
  var ny=sy;DBG.pin=a&&a.key;DBG.moved=target!=null;
  if(a){var o=old.get(a.key);ny=target!=null?a.top+tlTop-target:a.top-o.top+sy}
  var need=ny+vh-(tlTop+listH+foot.offsetHeight);padX=need>0?Math.ceil(need)+2:0;setH();
  if(ny<0)ny=0;
  if(Math.abs(ny-W.scrollY)>.5)W.scrollTo(0,ny);
  var gone=render(true),dy0=ny-sy;
  if(!DUR){gone.forEach(function(n){n.remove()});return}
  anim=true;var done=0,fin=function(){if(--done<=0){anim=false;trimPad()}};
  rendered.forEach(function(n,k){var r=n._r,o=old.get(k);if(!r)return;
    if(!o||o.hid){done++;n.animate([{opacity:0},{opacity:1}],{duration:DUR,easing:EASE}).onfinish=fin;return}
    var dy=(o.top+tlTop-sy)-(r.top+tlTop-ny);
    if(Math.abs(dy)<.5)return;
    if(dy>vh*1.15)dy=vh*1.15;if(dy<-vh*1.15)dy=-vh*1.15;
    done++;n.animate([{transform:"translateY("+dy+"px)"},{transform:"translateY(0)"}],{duration:DUR,easing:EASE}).onfinish=fin;
  });
  gone.forEach(function(n){var o=old.get(n._k);if(!o){n.remove();return}
    var r=null;for(var i=0;i<rows.length;i++)if(rows[i].key===n._k){r=rows[i];break}
    if(r&&!r.hid){ /* still shown, just moved out of the window: slide it along, then drop it */
      var dy=(o.top+tlTop-sy)-(r.top+tlTop-ny);n.style.top=r.top+"px";done++;
      n.animate([{transform:"translateY("+dy+"px)"},{transform:"translateY(0)"}],{duration:DUR,easing:EASE}).onfinish=function(){n.remove();fin()};return}
    /* removed by Condense: fade where it was on screen */
    n.style.top=(o.top+dy0)+"px";n.style.pointerEvents="none";done++;
    n.animate([{opacity:1,transform:"scale(1)"},{opacity:0,transform:"scale(.985)"}],{duration:DUR*.7,easing:"ease-out",fill:"forwards"}).onfinish=function(){n.remove();fin()};
  });
  if(!done){anim=false;trimPad()}
}
function trimPad(){if(!padX)return;var need=W.scrollY+W.innerHeight-(tlTop+listH+foot.offsetHeight);var p=need>0?Math.ceil(need)+2:0;if(p<padX){padX=p;setH()}}
/* ---------- expand / collapse */
function toggle(key){
  var r=null;for(var i=0;i<rows.length;i++)if(rows[i].key===key){r=rows[i];break}if(!r||anim)return;
  var n=rendered.get(key),opening=!exp.has(key),hd=n&&n.querySelector(".tl-hd");
  if(opening){
    if(!He[key])measure([r.it],true);
    if(!r.it.a&&!r.it._pf){r.it._pf=1;try{var pl=d.createElement("link");pl.rel="prefetch";pl.href="/wire/"+r.it.id;d.head.appendChild(pl)}catch(e){}}
    transition(function(){exp.add(key);if(n){n.classList.add("open");n.insertAdjacentHTML("beforeend",drawerHTML(r.it));hd&&hd.setAttribute("aria-expanded","true");var dr=n.querySelector(".tl-dr");
      if(DUR&&dr)dr.animate([{clipPath:"inset(0 0 100% 0)",opacity:.3},{clipPath:"inset(0 0 0 0)",opacity:1}],{duration:DUR,easing:EASE});}},key);
    /* if the drawer runs below the fold, glide it into view */
    setTimeout(function(){var nn=rendered.get(key);if(!nn)return;var b=nn.getBoundingClientRect();var over=b.bottom-(W.innerHeight-16);
      if(over>0)W.scrollBy({top:Math.min(over,b.top-ctlH()-12),behavior:RM?"auto":"smooth"})},DUR+20);
  }else{
    transition(function(){var dr2=n&&n.querySelector(".tl-dr");exp.delete(key);hd&&hd.setAttribute("aria-expanded","false");
      if(n&&dr2&&DUR){dr2.style.position="absolute";dr2.style.left="0";dr2.style.right="0";dr2.style.top=(hd?hd.offsetHeight:0)+"px";
        dr2.animate([{clipPath:"inset(0 0 0 0)",opacity:1},{clipPath:"inset(0 0 100% 0)",opacity:.2}],{duration:DUR,easing:EASE,fill:"forwards"}).onfinish=function(){dr2.remove();n.classList.remove("open")};}
      else if(n){dr2&&dr2.remove();n.classList.remove("open")}},key);
  }
}
list.addEventListener("click",function(e){if(e.target.closest("a,.tl-src,.tl-act,.tl-dr"))return;var hd=e.target.closest(".tl-hd");if(!hd)return;var n=hd.parentNode;if(n&&n._k)toggle(n._k)});
/* ---------- data */
function api(qs){return fetch("/api/wire_tl?"+qs+(qs?"&":"")+"_="+Date.now(),{credentials:"same-origin",cache:"no-store",headers:{"Cache-Control":"no-store","Pragma":"no-cache"}}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()})}
function qp(){var p=[];if(Q)p.push("q="+encodeURIComponent(Q));if(F.loc){p.push("lat="+F.loc.lat);p.push("lon="+F.loc.lon);p.push("r="+F.loc.r)}if(F.sev)p.push("sev="+encodeURIComponent(F.sev));if(F.cats.size)p.push("cats="+encodeURIComponent(Array.from(F.cats).join(",")));if(F.regs.size)p.push("regs="+encodeURIComponent(Array.from(F.regs).join(",")));if(F.time)p.push("time="+encodeURIComponent(F.time));return p.join("&")}
function add(arr,where){var fresh=[];arr.forEach(function(it){if(!seen[it.id]){seen[it.id]=1;fresh.push(it)}});measure(fresh,false);
  if(where==="top"){items=fresh.concat(items);items.sort(function(a,b){return a.t<b.t?1:a.t>b.t?-1:a.id<b.id?1:a.id>b.id?-1:0})}else items=items.concat(fresh);return fresh.length}
function lim(){return condensed&&active()?200:100}
function loadOlder(){
  if(loading.o||botEnd)return Promise.resolve();loading.o=1;var g=gen;footState();
  return api((botCur?"before="+encodeURIComponent(botCur)+"&":"")+"limit="+lim()+"&"+qp()).then(function(j){if(g!==gen)return;
    botCur=j.next;botEnd=!!j.end;if(!items.length&&j.items[0]){topCur=j.items[0].t+"|"+j.items[0].id;topEnd=true}
    add(j.items,"bot");rebuild();layout();render();if(!loadSeen()||!loadSeen().top)saveSeen();}).catch(function(){}).then(function(){if(g!==gen)return;loading.o=0;footState();status();stamp();check()});
}
function loadNewer(){
  if(loading.n||topEnd||!topCur)return Promise.resolve();loading.n=1;var g=gen;
  return api("after="+encodeURIComponent(topCur)+"&limit=100&"+qp()).then(function(j){if(g!==gen)return;
    topEnd=!!j.end;if(j.items[0])topCur=j.items[0].t+"|"+j.items[0].id;else topEnd=true;
    keepAnchor(function(){add(j.items,"top");rebuild()});}).catch(function(){topEnd=true}).then(function(){if(g!==gen)return;loading.n=0;status();check()});
}
function nearTop(){return W.scrollY<=tlTop+24}
/* ---------- live status: "Live · updated just now", ticking (Nov 21 2026, pt1688u) */
var stampAt=0,noneT=0,liveMode="off",tickT=0,msgUntil=0;
function ago(t){var s=Math.max(0,Math.round((Date.now()-t)/1000));if(s<45)return"just now";var m=Math.round(s/60);if(m<60)return m+" min ago";var h=Math.floor(m/60);return h+" h "+(m%60)+" min ago"}
function paintUpd(){if(!elUpd||!stampAt||Date.now()<msgUntil)return;elUpd.hidden=false;
  elUpd.innerHTML=(liveMode==="live"?'<i class="tl-live" aria-hidden="true"></i>Live &middot; ':"")+"Updated "+ago(stampAt);elUpd.title="Last checked "+fS.format(new Date(stampAt))+" ET"}
function stamp(){stampAt=Date.now();paintUpd()}
function tick(){var k=dayKey(new Date().toISOString());if(k!==todayK){todayK=k;yK=dayKey(new Date(Date.now()-864e5).toISOString());relabel()}paintUpd()}
tickT=setInterval(tick,15000);
function relabel(){ /* re-render on-screen rows so day labels and times are current */
  if(hold()){setTimeout(relabel,2000);return}
  rebuild();layout();rendered.forEach(function(n){n.remove()});rendered.clear();render()}
function sinceLabel(){return items[0]?fT.format(dt(items[0].t)):fT.format(new Date())}
function flash(txt,ms){if(!elUpd)return;elUpd.hidden=false;elUpd.textContent=txt;msgUntil=Date.now()+(ms||3200);
  if(stat)stat.style.visibility="hidden";clearTimeout(noneT);noneT=setTimeout(function(){msgUntil=0;if(stat)stat.style.visibility="";paintUpd()},ms||3200)}
function showNone(){flash("Up to date · nothing new since "+sinceLabel()+" ET")}
function showPill(){if(!bNew)return;bNew.hidden=pending<=0;if(pending>0)bNew.textContent=pending+" new"}
function loadSeen(){try{var s=JSON.parse(localStorage.getItem(SEEN_KEY)||"");return s&&typeof s==="object"?s:null}catch(e){return null}}
function saveSeen(){try{if(!items.length)return;var map={};items.slice(0,120).forEach(function(it){map[it.id]={t:it.t,n:it.n||0,f:it.f||0,h:it.h||""}});
  localStorage.setItem(SEEN_KEY,JSON.stringify({top:items[0].t+"|"+items[0].id,at:new Date().toISOString(),map:map}))}catch(e){}}
function scanLine(s){
  var r=(s&&s.in_review!=null?s.in_review:0),src=(s&&s.sources!=null?s.sources:0);
  var rs=Number(r).toLocaleString(),ss=Number(src).toLocaleString();
  if(s&&s.last_scan){return "Scanned "+ss+" sources at "+fT.format(dt(s.last_scan))+" ET · "+rs+" new signals in review"}
  return "Scan complete · "+rs+" new signals in review";
}
function scrollToKey(key){
  var r=null;for(var i=0;i<rows.length;i++)if(rows[i].key===key){r=rows[i];break}
  if(!r)return;var top=r.top+tlTop-Math.max(8,ctlH()+8);
  W.scrollTo({top:Math.max(0,top),behavior:RM?"auto":"smooth"});
}
var refP=0,refTgt=0,refRAF=0,refBusy=0;
function refApply(p){
  if(!bRef)return;
  p=Math.max(0,Math.min(100,p));
  if(refTgt>=100&&p>=99)p=100;
  refP=p;var shown=Math.round(p);if(refTgt>=100&&shown>=99)shown=100;
  bRef.style.setProperty("--tl-ref-p",shown+"%");
  var lab=(refBusy&&shown<100)?("Refresh "+shown+"%"):"Refresh";
  var a=bRef.querySelector(".tl-ref-lab-a"),b=bRef.querySelector(".tl-ref-lab-b");
  if(a)a.textContent=lab;if(b)b.textContent=lab;
  if(refBusy){bRef.setAttribute("aria-label","Refreshing, "+shown+" percent");bRef.setAttribute("aria-valuenow",String(shown))}
}
function refTick(){refRAF=0;var d=refTgt-refP;if(Math.abs(d)<0.4){refApply(refTgt);return}
  var step=RM?d:(refTgt>=100?Math.max(4,d*0.4):Math.max(0.6,d*0.22));
  refApply(refP+step);refRAF=requestAnimationFrame(refTick)}
function refStage(p){refTgt=Math.max(refTgt,Math.min(100,p));if(refTgt>=100)refTgt=100;if(RM){refApply(refTgt);return}if(!refRAF)refRAF=requestAnimationFrame(refTick)}
function busy(on){if(!bRef)return;
  if(on){refBusy=1;refP=0;refTgt=0;if(refRAF){cancelAnimationFrame(refRAF);refRAF=0}refApply(0);
    bRef.classList.remove("is-result");bRef.classList.add("is-filling");
    bRef.setAttribute("role","progressbar");bRef.setAttribute("aria-valuemin","0");bRef.setAttribute("aria-valuemax","100");
    bRef.setAttribute("aria-label","Refreshing, 0 percent")}
  else{refBusy=0;if(refRAF){cancelAnimationFrame(refRAF);refRAF=0};bRef.classList.remove("is-filling");
    bRef.removeAttribute("role");bRef.removeAttribute("aria-valuemin");bRef.removeAttribute("aria-valuemax");bRef.removeAttribute("aria-valuenow");
    bRef.style.removeProperty("--tl-ref-p")}
  bRef.classList.toggle("busy",!!on);bRef.setAttribute("aria-busy",on?"true":"false")}
function doneBtn(lab){if(!bRef)return;var a=bRef.querySelector(".tl-ref-lab-a"),b=bRef.querySelector(".tl-ref-lab-b");clearTimeout(bRef._doneT);
  if(!lab){bRef.classList.remove("is-result");if(a)a.textContent="Refresh";if(b)b.textContent="Refresh";bRef.setAttribute("aria-label","Refresh");return}
  bRef.classList.add("is-result");if(a)a.textContent=lab;if(b)b.textContent=lab;bRef.setAttribute("aria-label",lab);
  bRef._doneT=setTimeout(function(){doneBtn("")},2600)}
/* ---------- arrivals: near the top, new items slide in one at a time (oldest first, newest ends on top) */
var drip=[],queued={},dripT=0;
/* Nov 25 2026 (pt1918u): Full story needed 3-4 taps on iPhone because arrivals re-laid the list mid-tap. */
var touching=0,touchT=0,heldArr=[];
function hold(){return !!touching||exp.size>0}
function flushHeld(){if(!heldArr.length||hold())return;var a=heldArr;heldArr=[];arrive(a)}
d.addEventListener("touchstart",function(){touching=1;clearTimeout(touchT)},{passive:true,capture:true});
["touchend","touchcancel"].forEach(function(ev){d.addEventListener(ev,function(){clearTimeout(touchT);touchT=setTimeout(function(){touching=0;flushHeld()},450)},{passive:true,capture:true})});
setInterval(flushHeld,2000);
function gap(){return RM?0:Math.max(180,Math.min(700,4000/(drip.length+1)))}   /* a scan's batch streams in over about 4 s */
function flipAdd(it){
  var old=new Map();rendered.forEach(function(n,k){if(n._r)old.set(k,n._r.top)});
  add([it],"top");rebuild();layout();render();
  if(RM)return;
  rendered.forEach(function(n,k){var r=n._r;if(!r)return;
    if(k===it.id){n.animate([{opacity:0,transform:"translateY(-18px)"},{opacity:1,transform:"translateY(0)"}],{duration:520,easing:EASE});return}
    var o=old.get(k);if(o==null||Math.abs(o-r.top)<.5)return;
    n.animate([{transform:"translateY("+(o-r.top)+"px)"},{transform:"translateY(0)"}],{duration:520,easing:EASE})});
}
function dripNext(){dripT=0;
  if(!drip.length)return;
  if(hold()){dripT=setTimeout(dripNext,800);return}
  if(!nearTop()||anim){var rest=drip.splice(0);rest.forEach(function(x){delete queued[x.id]});
    keepAnchor(function(){var n=add(rest.slice().reverse(),"top");rebuild();pending+=n});showPill();return}
  var it=drip.shift();delete queued[it.id];if(seen[it.id])return dripNext();
  NEW[it.id]=Date.now();flipAdd(it);status();
  if(drip.length)dripT=setTimeout(dripNext,gap());
}
function arrive(arr){
  if(!arr||!arr.length)return 0;
  if(hold()){heldArr=heldArr.concat(arr);return 0}  /* Nov 25 (pt1918u): never shift rows under a finger or an open drawer */
  var fresh=arr.filter(function(it){return !seen[it.id]&&!queued[it.id]});if(!fresh.length)return 0;
  var t=Date.now();fresh.forEach(function(it){NEW[it.id]=t});
  if(nearTop()&&!RM){fresh.slice().reverse().forEach(function(it){queued[it.id]=1;drip.push(it)});if(!dripT)dripNext();return fresh.length}
  var n=0;
  if(nearTop()){n=add(fresh,"top");rebuild();layout();render()}
  else{keepAnchor(function(){n=add(fresh,"top");rebuild()});pending+=n;showPill()}
  return n;
}
function pollNewer(manual){
  if(loading.n||!topCur)return Promise.resolve(0);
  if(!manual&&d.hidden)return Promise.resolve(0);
  loading.n=1;var g=gen,got=0;if(manual)busy(true);
  /* Nov 25 2026 (pt1925u): read the top of the Wire, not "after the top row". A story is dated by its event time, so one that
     finished its write-up/card a few minutes later sorts just under the current top and an after= cursor never returned it. */
  return api("limit=100&"+qp()).then(function(j){if(g!==gen)return;
    var arr=(j.items||[]).filter(function(it){return !seen[it.id]&&!queued[it.id]});
    if(j.items&&j.items[0]&&(!topCur||j.items[0].t+"|"+j.items[0].id>topCur))topCur=j.items[0].t+"|"+j.items[0].id;
    topEnd=true;
    if(arr.length)got=arrive(arr);
    stamp();
  }).catch(function(){}).then(function(){if(g!==gen)return got;loading.n=0;if(manual)busy(false);status();check();return got});
}
/* safety poll: every 12 s without a live connection, every 60 s with one (the stream rings the bell the moment items land) */
function startPoll(){stopPoll();pollT=setInterval(function(){if(!d.hidden&&topEnd)pollNewer(false)},liveMode==="live"?60000:POLL)}
function stopPoll(){if(pollT){clearInterval(pollT);pollT=0}}
if(W.BNRT){
  BNRT.onMode(function(m){var was=liveMode;liveMode=m;if(was!==m&&pollT)startPoll();paintUpd()});
  BNRT.on(function(ev){ /* a scan landed on the server: fetch the new items through the normal API (keeps search/filters exact) */
    if(!(ev.reset||(ev.new&&ev.new.length)||ev.more_new))return;
    if(topEnd)pollNewer(false);else{pending+=(ev.new||[]).length+(ev.more_new||0);showPill()}});
}
function refresh(){
  /* Real refresh: fetch the top of the Wire immediately with fresh=1 (no cache), in parallel with asking the
     scanner for anything newer. Progress (0-100%) tracks real stages: ask scanner, scanner pull, fetch fresh, render.
     Never stuck at 99. Always surface something real: (a) stories newer than the last-seen top, (b) stories
     corroborated or rewritten since the last refresh, marked UPDATED and moved to the top, or (c) a live scan
     line from scanner stats. Never invent a story or bypass the publish gate. */
  if(bRef&&(bRef.classList.contains("busy")||refBusy))return Promise.resolve();
  busy(true);refStage(6);var g=gen,t0=Date.now(),prev=loadSeen()||{};
  function mergeItem(old,nu){["h","s","d","n","f","l","src","u","r","c","loc"].forEach(function(k){if(nu[k]!=null)old[k]=nu[k]});return old}
  function applyPage(j,res){
    if(g!==gen||!j)return {n:0,u:0,scan:""};
    var arr=j.items||[];
    var lastTop=prev.top||(items[0]?items[0].t+"|"+items[0].id:"");
    var lastMap=prev.map||{};
    items.forEach(function(it){it._pin=0});
    var newer=[],updated=[],seenUp={};
    arr.forEach(function(it){
      var cur=it.t+"|"+it.id;
      if(lastTop&&cur>lastTop){newer.push(it);return}
      if(!lastTop&&!seen[it.id]&&!lastMap[it.id]){newer.push(it);return}
      var was=lastMap[it.id];
      if(was&&((it.n||0)>(was.n||0)||(it.f||0)>(was.f||0)||(it.h&&was.h&&it.h!==was.h)))updated.push(it);
    });
    if(arr[0])topCur=arr[0].t+"|"+arr[0].id;
    topEnd=true;todayK=dayKey(new Date().toISOString());yK=dayKey(new Date(Date.now()-864e5).toISOString());
    var n=0;
    if(newer.length){
      n=arrive(newer);
      newer.forEach(function(it){NEW[it.id]=NEW[it.id]||Date.now();GLOW[it.id]=Date.now()});
      if(n<newer.length)n=newer.length;
    }
    if(updated.length){
      var ids={};updated.forEach(function(it){ids[it.id]=1});
      items.forEach(function(it){if(ids[it.id]){var nu=updated.filter(function(u){return u.id===it.id})[0];if(nu)mergeItem(it,nu);it._pin=1;UPD[it.id]=Date.now();GLOW[it.id]=Date.now();seenUp[it.id]=1}});
      var missing=updated.filter(function(u){return !seenUp[u.id]});
      missing.forEach(function(it){it._pin=1;UPD[it.id]=Date.now();GLOW[it.id]=Date.now();if(!seen[it.id]){seen[it.id]=1;items.unshift(it)}});
      var pins=items.filter(function(it){return it._pin}),rest=items.filter(function(it){return !it._pin});
      items=pins.concat(rest);
      measure(updated,false);
    }
    var scan=(j&&j.scan)||(res&&res.scan)||null;
    SCANMSG=(!newer.length&&!updated.length)?scanLine(scan):"";
    if(!newer.length&&!updated.length&&!drip.length)relabel();
    else{rebuild();layout();render()}
    stamp();
    var first=newer[0]||updated[0];
    if(first)scrollToKey(first.id);else if(SCANMSG)scrollToKey("scan");
    saveSeen();
    var got=0;for(var k in NEW)if(NEW[k]>=t0)got++;
    return {n:got||n,u:updated.length,scan:SCANMSG,obj:scan};
  }
  function loadFresh(){
    if(!topEnd){reset();scrollToList();return loadOlder().then(function(){return {n:-1,u:0,scan:""}})}
    loading.n=1;
    return api("fresh=1&limit="+lim()+"&"+qp()).then(function(j){if(g!==gen)return {n:0,u:0,scan:""};refStage(78);return j});
  }
  function loadMeta(){
    return fetch("/api/wire_tl/meta?_="+Date.now(),{credentials:"same-origin",cache:"no-store",headers:{"Cache-Control":"no-store","Pragma":"no-cache"}}).then(function(r){return r.json()}).then(function(m){if(m&&m.total!=null){meta=m;total=m.total;status()}}).catch(function(){});
  }
  function askScanner(){
    refStage(18);
    var p=W.BNRT?BNRT.refresh():Promise.resolve({});
    return p.then(function(res){refStage(48);return res},function(){refStage(48);return {}});
  }
  loadMeta();
  return Promise.all([loadFresh(),askScanner()]).then(function(pair){
    if(g!==gen)return pair[0];
    var page=pair[0],res=pair[1]||{};
    if(page&&page.items){ /* first fetch resolved to raw page; apply after we know scanner result */ }
    if(res&&res.pulled_new>0){
      refStage(58);
      return api("fresh=1&limit="+lim()+"&"+qp()).then(function(j2){refStage(88);return {j:j2||page,res:res}});
    }
    refStage(88);
    return {j:page,res:res};
  }).then(function(pack){
    if(g!==gen)return;
    refStage(92);
    var j=pack&&pack.j,res=pack&&pack.res||{};
    /* loadFresh may have returned a raw page (has items) or a counted result if we jumped through loadOlder */
    if(j&&j.n===-1)return {n:-1,u:0,scan:""};
    if(j&&j.items)return applyPage(j,res);
    if(j&&(j.n!=null||j.u!=null))return j;
    return applyPage(j,res);
  }).then(function(out){
    if(g!==gen)return;
    refStage(100);
    var wait=RM?0:Math.max(220,320-(Date.now()-t0));
    setTimeout(function(){
      var n=out&&out.n||0,u=out&&out.u||0;
      busy(false);
      if(n===-1){doneBtn("Latest");flash("Showing the latest stories")}
      else if(n){doneBtn(n+" new");flash(n+" new stor"+(n===1?"y":"ies"));}
      else if(u){doneBtn(u+" updated");flash(u+" updated stor"+(u===1?"y":"ies"))}
      else{doneBtn("Scanned");flash(out&&out.scan||scanLine(out&&out.obj),4200)}
    },wait);
  }).catch(function(){flash("Could not reach the server. Try again in a moment.")}).then(function(){if(g!==gen)return;loading.n=0;if(refBusy){refStage(100);setTimeout(function(){busy(false)},RM?0:200)}status();check()});
}
var chk=0;
function check(){if(chk)return;chk=requestAnimationFrame(function(){chk=0;if(anim)return;
  var sy=W.scrollY,vh=W.innerHeight,bottom=tlTop+listH;
  if(!botEnd&&!loading.o&&bottom-(sy+vh)<vh*2.2)loadOlder();
  if(!topEnd&&!loading.n&&sy-tlTop<vh*1.6&&sy+vh>tlTop-vh)loadNewer();})}
function footState(){
  if(loading.o&&!botEnd){foot.className="tl-foot load";foot.innerHTML='<span class="tl-scan" aria-hidden="true"><i></i></span><span>'+(items.length?"Loading older signals":"Loading the timeline")+"</span>";return}
  if(botEnd&&items.length&&!Q&&!active()){var e=items[items.length-1];foot.className="tl-foot end";
    foot.innerHTML='<svg class="tl-flat" viewBox="0 0 320 40" aria-hidden="true"><path d="M0 20H140l6-12 8 26 6-14H320" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>'+
      "<p class=\"tl-zero\">Signal zero</p><p>"+esc((e["do"]?fUs:fL).format(dt(seenAt(e))).replace(/^\w+, /,""))+". The earliest entry on our record. Before this, silence.</p>";return}
  if(botEnd&&(Q||active())){var label=Q?("&ldquo;"+esc(Q)+"&rdquo;"):esc(filtNames().join(" + "));foot.className="tl-foot end";foot.innerHTML="<p>"+(items.length?"End of results":"No signals match")+" for "+label+".</p>";return}
  foot.className="tl-foot";foot.innerHTML="";
}
/* ---------- status line + compact Filters sheet */
function loadedMatch(){var n=0,a=0;for(var i=0;i<items.length;i++){a++;if(match(items[i]))n++}return[n,a]}
function filtNames(){
  var names=[];F.cats.forEach(function(k){names.push((CAT[k]||{}).label)});F.regs.forEach(function(k){names.push((REG[k]||{}).label)});
  if(F.loc)names.push(F.loc.label+" · "+F.loc.r+" mi");
  if(F.time)names.push(F.time==="today"?"Today":F.time==="1"?"24 hours":F.time+" days");
  if(F.sev)names.push({lo:"Rank 0–3",mid:"Rank 4–6",hi:"Rank 7–10"}[F.sev]);
  return names;
}
function status(){
  var s,n=nFilt();
  if(badge){if(n){badge.hidden=false;badge.textContent=String(n)}else badge.hidden=true}
  if(bFilt)bFilt.classList.toggle("on",sheet&&!sheet.hidden);
  if(active()){var m=loadedMatch();s=filtNames().join(" + ")+" &middot; "+m[0].toLocaleString()+" of "+m[1].toLocaleString()+" loaded"+(condensed?" &middot; condensed":"")}
  else if(Q)s="&ldquo;"+esc(Q)+"&rdquo; &middot; "+(qCount==null?"searching":qCount.toLocaleString()+" match"+(qCount===1?"":"es"));
  else s="";
  stat.innerHTML=s;bClear.hidden=!active();bCond.disabled=!active()&&!condensed;
}
function chipHTML(k,label,color,grp){return'<button type="button" class="tl-chip" data-g="'+grp+'" data-k="'+k+'" aria-pressed="false"'+(color?' style="--c:'+color+'"':"")+">"+(color?'<i aria-hidden="true"></i>':"")+esc(label)+"</button>"}
if(chipsC)chipsC.innerHTML=CFG.cats.map(function(c){return chipHTML(c.k,c.label,c.color,"c")}).join("");
if(chipsR)chipsR.innerHTML=CFG.regions.map(function(r){return chipHTML(r.k,r.label,"","r")}).join("");
function setFilter(fn){
  fn();
  if(!active()&&condensed){condensed=false;bCond.setAttribute("aria-pressed","false");bCond.querySelector(".tl-cl").textContent="Condense"}
  syncChips();reset();scrollToList();loadOlder();
}
function syncChips(){
  if(sheet)sheet.querySelectorAll("#tl_chips_c .tl-chip, #tl_chips_r .tl-chip").forEach(function(b){var on=(b.dataset.g==="c"?F.cats:F.regs).has(b.dataset.k);b.setAttribute("aria-pressed",on?"true":"false");b.classList.toggle("on",on)});
  if(timeBox)timeBox.querySelectorAll(".tl-chip").forEach(function(b){var on=String(b.dataset.t||"")===String(F.time||"");b.setAttribute("aria-pressed",on?"true":"false");b.classList.toggle("on",on)});
  if(sevBox)sevBox.querySelectorAll(".tl-chip").forEach(function(b){var on=String(b.dataset.s||"")===String(F.sev||"");b.setAttribute("aria-pressed",on?"true":"false");b.classList.toggle("on",on)});
  if(radBox)radBox.querySelectorAll(".tl-chip").forEach(function(b){var on=Number(b.dataset.r)===(F.loc?F.loc.r:F.r);b.setAttribute("aria-pressed",on?"true":"false");b.classList.toggle("on",on)});
}
function openSheet(on){if(!sheet)return;sheet.hidden=!on;bFilt.setAttribute("aria-expanded",on?"true":"false");if(on)openJump(false);status();syncBar()}
function clearFilters(refetch){
  setFilter(function(){F.cats.clear();F.regs.clear();F.time="";F.sev="";F.loc=null});
  if(locIn)locIn.value="";if(locLab){locLab.hidden=true;locLab.textContent=""}
  crimeItems=[];
}
if(sheet)sheet.addEventListener("click",function(e){var b=e.target.closest(".tl-chip");if(!b)return;
  if(b.closest("#tl_chips_c")||b.closest("#tl_chips_r")){var S=b.dataset.g==="c"?F.cats:F.regs,k=b.dataset.k;setFilter(function(){S.has(k)?S.delete(k):S.add(k)});return}
  if(b.closest("#tl_time")){var t=b.dataset.t||"";setFilter(function(){F.time=(F.time===t?"":t)});return}
  if(b.closest("#tl_sev")){var s=b.dataset.s||"";setFilter(function(){F.sev=(F.sev===s?"":s)});return}
  if(b.closest("#tl_rad")){F.r=Number(b.dataset.r)||25;if(F.loc){F.loc.r=F.r;syncChips();status();reset();scrollToList();loadOlder();loadCrime()}else syncChips()}
});
if(bFilt)bFilt.addEventListener("click",function(){openSheet(sheet.hidden)});
bClear.addEventListener("click",function(){clearFilters(false)});
var bFclear=$("tl_fclear");if(bFclear)bFclear.addEventListener("click",function(){clearFilters(false)});
function setLocLab(ok,msg){if(!locLab)return;locLab.hidden=!msg;locLab.textContent=msg||"";locLab.classList.toggle("err",!ok)}
function applyPlace(p,r){
  F.loc={q:locIn.value.trim(),label:p.label,lat:p.lat,lon:p.lon,r:r||F.r||25};
  setLocLab(true,p.label+" · "+F.loc.r+" mi");
  syncChips();status();reset();scrollToList();loadOlder();loadCrime();
}
function loadCrime(){
  crimeItems=[];if(!F.loc)return;
  var q=F.loc.q||F.loc.label;if(!q)return;
  fetch("/api/wire_tl/crime?q="+encodeURIComponent(q),{credentials:"same-origin",cache:"no-store"}).then(function(r){return r.json()}).then(function(j){
    if(!F.loc)return;
    crimeItems=(j.items||[]).map(function(it){it.lat=it.lat==null?F.loc.lat:it.lat;it.lon=it.lon==null?F.loc.lon:it.lon;return it});
    if(crimeItems.length){add(crimeItems,"top");rebuild();layout();render();status()}
  }).catch(function(){});
}
if(locF)locF.addEventListener("submit",function(e){e.preventDefault();var q=(locIn.value||"").trim();if(!q){F.loc=null;crimeItems=[];setLocLab(true,"");syncChips();status();reset();scrollToList();loadOlder();return}
  locF.classList.add("busy");
  fetch("/api/wire_tl/geo?q="+encodeURIComponent(q),{credentials:"same-origin",cache:"no-store"}).then(function(r){return r.json()}).then(function(j){
    if(!j.ok||!j.place||j.place.lat==null){setLocLab(false,j.message||"We couldn't find that place.");return}
    applyPlace(j.place,F.r);
  }).catch(function(){setLocLab(false,"Lookup failed. Try a US ZIP.")}).then(function(){locF.classList.remove("busy")});
});
bCond.addEventListener("click",function(){if(anim)return;var to=!condensed;
  transition(function(){condensed=to});
  bCond.setAttribute("aria-pressed",to?"true":"false");bCond.querySelector(".tl-cl").textContent=to?"Show all":"Condense";status();check()});
/* ---------- search */
var qCount=null,qT=0,preQ=null;
function setQ(v){v=(v||"").trim().slice(0,80);if(v===Q)return;
  if(!Q&&v){var a=anchorRow();preQ=a&&!a.day?a.it.t:null}
  Q=v;qX.hidden=!v;
  var w=v.split(/\s+/).filter(Boolean).map(function(x){return x.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")});
  qRx=w.length?new RegExp("("+w.join("|")+")","gi"):null;qCount=null;
  if(v){fetch("/api/wire_tl/count?q="+encodeURIComponent(v)).then(function(r){return r.json()}).then(function(j){if(Q===v){qCount=j.count;status()}}).catch(function(){})}
  if(!v&&preQ){var t=preQ;preQ=null;jumpTo(isoPlus(t,1000));return}
  reset();scrollToList();loadOlder();
}
qIn.addEventListener("input",function(){clearTimeout(qT);var v=qIn.value;qT=setTimeout(function(){setQ(v)},380)});
qIn.addEventListener("keydown",function(e){if(e.key==="Enter"){clearTimeout(qT);setQ(qIn.value);qIn.blur()}if(e.key==="Escape"){qIn.value="";setQ("")}});
qX.addEventListener("click",function(){qIn.value="";setQ("")});
d.addEventListener("keydown",function(e){if(e.key==="/"&&d.activeElement!==qIn&&!/input|textarea/i.test((d.activeElement||{}).tagName||"")){e.preventDefault();scrollToList();qIn.focus()}});
/* ---------- jump to date */
function reset(){gen++;items=[];seen={};rows=[];rendered.forEach(function(n){n.remove()});rendered.clear();exp.clear();
  topCur=null;topEnd=true;botCur=null;botEnd=false;loading={o:0,n:0};padX=0;NEW={};pending=0;drip=[];queued={};clearTimeout(dripT);dripT=0;showPill();layout();footState()}
function scrollToList(){measureTop();var tgt=tlTop-(ctl.offsetHeight+barH())-4;if(W.scrollY<tgt-2||W.scrollY>tgt+2)W.scrollTo(0,tgt)}
function barH(){return bar?bar.getBoundingClientRect().height:0}
function endOfDayET(ymd){ /* ET day end in UTC: try both offsets, pick the one that maps back to the same ET day */
  for(var off=4;off<=5;off++){var t=new Date(ymd+"T23:59:59Z");t=new Date(t.getTime()+off*36e5);if(dayKey(t.toISOString())===ymd)return t.toISOString().slice(0,19)+"Z"}
  return ymd+"T23:59:59Z";
}
function jumpTo(cur){ /* cur: ISO UTC; everything at or before it, newest first; then page newer above */
  reset();measureTop();scrollToList();var g=gen;
  loading.o=1;footState();
  api("before="+encodeURIComponent(cur)+"&limit=100&"+qp()).then(function(j){if(g!==gen)return;
    botCur=j.next;botEnd=!!j.end;add(j.items,"bot");
    if(j.items[0]){topCur=j.items[0].t+"|"+j.items[0].id;topEnd=false}else topEnd=true;
    rebuild();layout();measureTop();
    var tgt=tlTop+(rows[0]?rows[0].top:0)-(ctl.offsetHeight+barH())-4;padX=Math.max(0,Math.ceil(tgt+W.innerHeight-(tlTop+listH+foot.offsetHeight)));setH();
    W.scrollTo(0,tgt);render();}).catch(function(){}).then(function(){if(g!==gen)return;loading.o=0;footState();status();
      setTimeout(function(){if(g===gen)loadNewer()},250);check()});
}
function isoPlus(t,ms){return new Date(new Date(t).getTime()+ms).toISOString().slice(0,19)+"Z"}
var QJ=[["Latest",0],["24 hours ago",1],["1 week ago",7],["1 month ago",30],["6 months ago",182],["1 year ago",365],["Beginning",-1]];
function buildJump(){
  var h=QJ.map(function(x){return'<button type="button" class="tl-jb" data-d="'+x[1]+'">'+x[0]+"</button>"}).join("");
  if(meta&&meta.months&&meta.months.length){
    /* months before 2023 collapse into one bar per year (the archive reaches back to 2000); a year bar jumps to Dec 31 of that year */
    var bars=[],yr={};meta.months.forEach(function(m){if(m[0]<"2023-01"){var y=m[0].slice(0,4);if(!yr[y]){yr[y]={key:y+"-12",y:y,n:0,year:1};bars.push(yr[y])}yr[y].n+=m[1]}else bars.push({key:m[0],y:m[0].slice(0,4),n:m[1],mo:+m[0].slice(5,7)})});
    var mx=Math.max.apply(null,bars.map(function(b){return b.year?b.n/12:b.n}));
    h+='<div class="tl-hist" role="group" aria-label="Jump to a month or year">'+bars.map(function(b,i){
      var lab=b.year?b.y:new Date(Date.UTC(+b.y,b.mo-1,15)).toLocaleString("en-US",{month:"short",timeZone:"UTC"})+" "+b.y;
      var v=b.year?b.n/12:b.n,show=b.year?(+b.y%5===0||i===0):(b.mo===1);
      return'<button type="button" class="tl-hb" data-m="'+b.key+'" title="'+lab+": "+b.n.toLocaleString()+' signals" aria-label="'+lab+'"><i style="height:'+Math.max(6,Math.round(100*Math.sqrt(v/mx)))+'%"></i>'+(show?"<b>"+b.y+"</b>":"")+"</button>"}).join("")+"</div>";}
  jq.innerHTML=h;
  if(meta&&meta.earliest){dIn.min=dayKey(meta.earliest);dIn.max=todayK}
}
function openJump(on){jump.hidden=!on;bWhen.setAttribute("aria-expanded",on?"true":"false");bWhen.classList.toggle("on",on)}
bWhen.addEventListener("click",function(){openJump(jump.hidden)});
jq.addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;openJump(false);
  if(b.dataset.m){var p=b.dataset.m.split("-"),last=new Date(Date.UTC(+p[0],+p[1],0)).getUTCDate();jumpTo(endOfDayET(b.dataset.m+"-"+("0"+last).slice(-2)));return}
  var n=+b.dataset.d;if(n===0){goLatest();return}
  if(n<0){if(meta&&meta.earliest)jumpTo(endOfDayET(dayKey(meta.earliest)));return}
  jumpTo(isoPlus(new Date().toISOString(),-n*864e5))});
dIn.addEventListener("change",function(){if(dIn.value){openJump(false);jumpTo(endOfDayET(dIn.value))}});
d.addEventListener("click",function(e){if(!jump.hidden&&!e.target.closest("#tl_jump")&&!e.target.closest("#tl_when"))openJump(false);if(sheet&&!sheet.hidden&&!e.target.closest("#tl_sheet")&&!e.target.closest("#tl_filt"))openSheet(false)});
function goLatest(){if(topEnd&&items.length){scrollToList();pending=0;showPill();return}reset();scrollToList();loadOlder()}
bTop.addEventListener("click",goLatest);
if(bNew)bNew.addEventListener("click",function(){pending=0;showPill();goLatest()});
if(bRef)bRef.addEventListener("click",refresh);
d.addEventListener("visibilitychange",function(){if(d.hidden)stopPoll();else{pollNewer(false);startPoll()}});
pill.addEventListener("click",function(e){e.stopPropagation();openJump(jump.hidden)});
/* ---------- scroll loop: window, pill, background veil */
var ticking=false,veil=d.querySelector(".tl-veil"),lastW=0;
function frame(){ticking=false;var sy=W.scrollY,vh=W.innerHeight;
  if(!anim)render();
  var inTl=sy+ctlH()>tlTop+10&&rows.length;
  if(inTl){var i=rowAt(Math.max(0,sy-tlTop+ctlH()+8));if(i>=rows.length)i=rows.length-1;while(i>0&&(!rows[i].day||rows[i].hid))i--;var dr=rows[i];if(dr&&dr.day&&pill._k!==dr.key){pill._k=dr.key;pill.textContent=dr.label}}
  else if(pill._k){pill._k=null;pill.textContent=""}
  bTop.hidden=!(sy>tlTop+vh*2.5||(!topEnd&&inTl));
  if(veil){var p=Math.max(0,Math.min(1,(sy-vh*.15)/(vh*.7)));veil.style.opacity=(.35+.55*p).toFixed(3)}
  check();
}
W.addEventListener("scroll",function(){if(!ticking){ticking=true;requestAnimationFrame(frame)}},{passive:true});
function onResize(){syncBar();var w=list.clientWidth;if(Math.abs(w-lastW)<1){measureTop();render();return}lastW=w;cw=w;
  keepAnchor(function(){Hc={};He={};measure(items,false);var o=items.filter(function(it){return exp.has(it.id)});if(o.length)measure(o,true);
    rendered.forEach(function(n){n.remove()});rendered.clear()});measureTop();render();}
var rzT=0;W.addEventListener("resize",function(){clearTimeout(rzT);rzT=setTimeout(onResize,120)});
/* ---------- hero video (desktop/tablet only; phones get the still) */
(function(){var v=d.querySelector(".tl-vid"),n=navigator.connection||{};if(!v||W.innerWidth<=700||RM||n.saveData)return;
  setTimeout(function(){[["webm","video/webm"],["mp4","video/mp4"]].forEach(function(a){var s=d.createElement("source");s.src=v.getAttribute("data-"+a[0]);s.type=a[1];v.appendChild(s)});
    v.muted=true;v.autoplay=true;v.preload="auto";v.addEventListener("playing",function(){v.classList.add("on")},{once:true});v.load();var p=v.play();if(p&&p.catch)p.catch(function(){})},300)})();
/* keep the controls under the site bar (the bar stays put on this page) */
function syncBar(){d.documentElement.style.setProperty("--tl-bar",barH()+"px");d.documentElement.style.setProperty("--tl-ctl",ctl.offsetHeight+"px")}
/* ---------- feed freshness notice (clears on its own when scans resume) */
function feedHealth(){var el=$("tl_stale");if(!el)return;
  fetch("/api/signal/feed-health",{cache:"no-store"}).then(function(r){return r.json()}).then(function(H){
    if(H&&H.stale&&H.notice){el.hidden=false;el.textContent=H.notice;el.classList.toggle("is-severe",!!H.severe)}
    else{el.hidden=true;el.textContent="";el.classList.remove("is-severe")}
  }).catch(function(){})}
setInterval(feedHealth,30000);
/* ---------- boot */
function boot(){syncBar();lastW=list.clientWidth;cw=lastW;measureTop();feedHealth();
  fetch("/api/wire_tl/meta?_="+Date.now(),{credentials:"same-origin",cache:"no-store",headers:{"Cache-Control":"no-store","Pragma":"no-cache"}}).then(function(r){return r.json()}).then(function(m){meta=m;total=m.total||0;buildJump();status()}).catch(function(){buildJump()});
  var hs=(location.hash||"").match(/^#d=(\d{4}-\d{2}-\d{2})$/);
  if(hs)jumpTo(endOfDayET(hs[1]));else loadOlder();
  startPoll();
  frame();
}
W.BN_TL_DEBUG={dbg:DBG,rows:function(){return rows},items:function(){return items},anchor:anchorRow,rendered:rendered,jumpTo:jumpTo,state:function(){return{condensed:condensed,anim:anim,tlTop:tlTop,listH:listH,padX:padX,topEnd:topEnd,botEnd:botEnd,n:items.length}}};
if(d.fonts&&d.fonts.ready)d.fonts.ready.then(boot);else boot();
})();
