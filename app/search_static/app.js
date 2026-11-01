/* blackout.network global search: header bar on every page (dashboard tabs, /scoring, any page that loads this script).
   '/' focuses, Enter searches, Esc closes. Database results arrive instantly; the live scan streams in over SSE.
   Live results are ephemeral: shown here only, never added to the feed. Everything rendered as text (escaped). */
(function(){
 if(window.__bnSearch)return;window.__bnSearch=1;
 const ME=document.currentScript&&document.currentScript.src||"/api/search/app.js";
 const API=new URL(".",ME).href;            // .../api/search/
 const COL=["#3a4250","#4b5563","#2f7d4f","#52c41a","#a0d911","#fadb14","#faad14","#fa8c16","#ff4d4f","#cf1322","#8b0000"];
 const DARK=new Set([4,5,6]);
 const RKEY="bn_search_recent",MAXQ=200;
 const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
 const safe=u=>/^https?:\/\//i.test(u||"")?u:null;
 const fmt=t=>{if(!t)return"time n/a";const d=new Date(t);if(isNaN(d))return"time n/a";return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"};
 const rk=(r,big)=>{r=Math.max(0,Math.min(10,r|0));return `<span class="bns-rk${DARK.has(r)?" dk":""}" style="background:${COL[r]}" title="Rank ${r}/10">${r}${big?"<small>/10</small>":""}</span>`};
 const recent=()=>{try{return JSON.parse(localStorage.getItem(RKEY)||"[]").filter(x=>typeof x=="string").slice(0,10)}catch(e){return[]}};
 const pushRecent=q=>{const r=[q,...recent().filter(x=>x.toLowerCase()!=q.toLowerCase())].slice(0,10);try{localStorage.setItem(RKEY,JSON.stringify(r))}catch(e){}};
 function css(){if(document.getElementById("bns_css"))return;const l=document.createElement("link");l.id="bns_css";l.rel="stylesheet";l.href=API+"app.css";document.head.appendChild(l)}
 css();
 // ---------- header bar
 const box=document.createElement("div");box.id="bns";
 box.innerHTML=`<button type="button" class="bns-ico" aria-label="Open search" title="Search (/)">🔍</button>
 <form role="search" autocomplete="off"><input id="bns_q" type="search" maxlength="${MAXQ}" placeholder="Search threats, places, sources…" aria-label="Search all sources" enterkeyhint="search"><kbd>/</kbd><button class="bns-go" type="submit" aria-label="Search">🔍</button></form>
 <div id="bns_pop" role="listbox"></div>`;
 function mount(){const slot=document.getElementById("bn_dsearch");if(slot){slot.appendChild(box);return}   // sidebar menu (sitenav, t321)
  const h=document.querySelector("header");
  if(h){const ctl=h.querySelector(".ctl");if(ctl&&ctl.parentNode===h)h.insertBefore(box,ctl);else h.appendChild(box)}
  else{box.style.cssText="position:fixed;top:8px;right:10px;z-index:2400;width:300px";document.body.appendChild(box)}}
 mount();
 const inp=box.querySelector("#bns_q"),pop=box.querySelector("#bns_pop");
 box.querySelector(".bns-ico").onclick=()=>{box.classList.toggle("open");if(box.classList.contains("open"))setTimeout(()=>inp.focus(),0);else hidePop()};
 box.querySelector("form").onsubmit=e=>{e.preventDefault();const q=inp.value.trim();if(q)open(q)};
 let sugT=null,sugCtl=null,sel=-1;
 function hidePop(){pop.classList.remove("on");sel=-1}
 function showPop(sug){const r=recent();let h="";
  if(sug&&sug.length)h+=`<div class="bns-lbl">From the database</div>`+sug.map((d,i)=>`<div class="bns-sug" data-q="${esc(d.title)}" data-i="${i}">${rk(d.rank)}<span>${esc(d.title)}</span></div>`).join("");
  if(r.length)h+=`<div class="bns-lbl" style="margin-top:${sug&&sug.length?8:2}px">Recent searches <button type="button" data-clear="1">Clear</button></div><div class="bns-chips">${r.map(x=>`<button type="button" class="bns-chip" data-q="${esc(x)}">${esc(x)}</button>`).join("")}</div>`;
  if(!h)h=`<div class="bns-empty">Type a keyword or phrase and press Enter. Searches the database instantly, then runs a live scan of the sources.</div>`;
  pop.innerHTML=h;pop.classList.add("on")}
 pop.addEventListener("mousedown",e=>e.preventDefault());
 pop.onclick=e=>{if(e.target.closest("[data-clear]")){try{localStorage.removeItem(RKEY)}catch(x){}showPop([]);return}
  const s=e.target.closest(".bns-sug");if(s){open(inp.value.trim()||s.dataset.q);return}
  const c=e.target.closest(".bns-chip");if(c){inp.value=c.dataset.q;open(c.dataset.q)}};
 inp.addEventListener("focus",()=>showPop([]));
 inp.addEventListener("blur",()=>setTimeout(hidePop,150));
 inp.addEventListener("input",()=>{clearTimeout(sugT);const q=inp.value.trim();if(q.length<2){showPop([]);return}
  sugT=setTimeout(async()=>{try{sugCtl&&sugCtl.abort();sugCtl=new AbortController();
   const r=await fetch(API+"db?limit=6&q="+encodeURIComponent(q.slice(0,MAXQ)),{signal:sugCtl.signal});const j=await r.json();if(inp.value.trim()===q&&document.activeElement===inp)showPop(j.results||[])}catch(e){}},350)}); // debounced, database only
 inp.addEventListener("keydown",e=>{if(e.key==="Escape"){inp.blur();hidePop();box.classList.remove("open")}});
 document.addEventListener("keydown",e=>{
  if(e.key==="/"&&!e.ctrlKey&&!e.metaKey&&!e.altKey){const t=e.target;if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))return;
   e.preventDefault();if(getComputedStyle(box.querySelector("form")).display==="none")box.classList.add("open");inp.focus();inp.select()}
  else if(e.key==="Escape"&&panel.classList.contains("on")&&document.activeElement!==inp)close()});
 // ---------- results overlay
 const shade=document.createElement("div");shade.id="bns_shade";
 const panel=document.createElement("aside");panel.id="bns_panel";panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Search results");
 panel.innerHTML=`<div class="bns-head"><div class="bns-title"><h2>Search results</h2><button class="bns-x" type="button" title="Close (Esc)">✕ Close</button></div>
 <form class="bns-pq" autocomplete="off"><input type="search" maxlength="${MAXQ}" aria-label="Search again"><button type="submit">Search</button></form>
 <div class="bns-ctl"><label>Category <select data-f="cat"><option value="">All</option></select></label>
 <label>Min rank <select data-f="min">${[0,1,2,3,4,5,6,7,8,9,10].map(i=>`<option value="${i}">${i}+</option>`).join("")}</select></label>
 <label>Sort <select data-f="sort"><option value="rank">Rank, then newest</option><option value="new">Newest</option><option value="rel">Relevance</option></select></label>
 <label><input type="checkbox" data-f="watch" checked> Include Watchlist</label></div>
 <div class="bns-stat"></div><div class="bns-prog"></div></div><div class="bns-body"></div>`;
 document.body.append(shade,panel);
 const P=s=>panel.querySelector(s),body=P(".bns-body");
 P(".bns-x").onclick=()=>close();shade.onclick=()=>close();
 P(".bns-pq").onsubmit=e=>{e.preventDefault();const q=P(".bns-pq input").value.trim();if(q)open(q)};
 P(".bns-pq input").addEventListener("keydown",e=>{if(e.key==="Escape"){e.stopPropagation();close()}});
 panel.querySelectorAll("[data-f]").forEach(el=>el.onchange=render);
 let S=null,es=null,prevHash=null;
 function close(){es&&es.close();es=null;const ph=P(".bns-prog");if(ph&&ph._bnp)ph._bnp.destroy();panel.classList.remove("on");shade.classList.remove("on");document.documentElement.style.overflow="";
  if(/^#search=/.test(location.hash))history.replaceState(null,"",location.pathname+location.search+(prevHash&&!/^#search=/.test(prevHash)?prevHash:""));box.classList.remove("open")}
 function open(q){q=q.replace(/[\u0000-\u001f]/g," ").trim().slice(0,MAXQ);if(!q)return;clearTimeout(sugT);sugCtl&&sugCtl.abort();hidePop();inp.blur();inp.value=q;pushRecent(q);
  if(!/^#search=/.test(location.hash))prevHash=location.hash;
  history.replaceState(null,"","#search="+encodeURIComponent(q));
  panel.classList.add("on");if(matchMedia("(max-width:700px)").matches){shade.classList.remove("on");document.documentElement.style.overflow="hidden"}else shade.classList.add("on");
  box.classList.remove("open");P(".bns-pq input").value=q;P(".bns-title h2").innerHTML=`Search: <q>${esc(q)}</q>`;
  const BP=window.BNProgress;let pg=BP?BP.create(P(".bns-prog"),{label:"Searching the database…",name:"Site search"}).stage(null,0.03).ease(0.25,1500):null;   // t480 shared progress bar: real stages from the event stream
  S={q,db:null,live:new Map(),src:new Map(),una:[],t0:performance.now(),dbms:null,done:null,notes:[],running:true,mode:null};render();
  es&&es.close();es=new EventSource(API+"stream?q="+encodeURIComponent(q));const my=es;
  const on=(ev,fn)=>my.addEventListener(ev,e=>{if(my!==es)return;try{fn(JSON.parse(e.data))}catch(x){console.warn("search",ev,x)}});
  on("hello",d=>{if(pg)pg.steps(d.sources.length||1,"Checking "+d.sources.length+" live sources");d.sources.forEach(s=>S.src.set(s.key,{...s,status:"waiting"}));S.una=d.unavailable||[];render()});
  on("db",d=>{if(pg&&!d.sources)pg.stage(null,0.3);S.db=d.results||[];S.dbms=d.ms;S.mode=d.mode;S.hidden=d.hidden_noise;S.dbclient=Math.round(performance.now()-S.t0);
   const m=new Map(S.db.map(x=>[x.cluster_id,x]));S.dbmap=m;render()});
  on("source",d=>{const was=(S.src.get(d.key)||{}).status;if(pg&&!/^(searching|waiting)$/.test(d.status||"")&&/^(searching|waiting)$/.test(was||"waiting"))pg.tick();S.src.set(d.key,{...(S.src.get(d.key)||{}),...d});renderChips();renderStat()});
  on("results",d=>{(d.items||[]).forEach(x=>{x._fresh=1;if(S.dbmap&&(S.dbmap.has(x.cluster_id)||x.origin!=="live")){S.dbmap.set(x.cluster_id,{...(S.dbmap.get(x.cluster_id)||{}),...x})}else S.live.set(x.cluster_id,x)});render()});
  on("notice",d=>{S.notes.push(d.text);render()});
  on("queued",d=>{S.notes.push(d.reason);render()});
  on("limited",d=>{S.notes.push(d.reason);S.limited=1;render()});
  on("done",d=>{S.done=d;S.running=false;my.close();if(pg){d.error?pg.fail("Live search stopped: "+d.error,()=>open(q)):d.cached?pg.cached():pg.done("Done")}if(d.error)S.notes.push("Search stopped: "+d.error);render()});
  my.onerror=()=>{if(my!==es)return;if(S.running){if(pg)pg.fail("The live connection closed early. Database results are complete.",()=>open(q));S.running=false;S.notes.push("The live connection closed early. Database results above are complete.");render()}my.close()};
 }
 function chip(s){const st=s.status||"waiting";let t=st==="ok"?`<b>${s.n}</b>`:st==="searching"||st==="waiting"?"searching":st;
  return `<span class="bns-src ${esc(st)}${st==="ok"&&s.n?" hit":""}" title="${esc((s.note||"")+(s.error?" · "+s.error:"")+(s.ms!=null?" · "+s.ms+" ms":"")+(s.cached?" · cached result":""))}">${esc(s.label)} · ${t}</span>`}
 function renderChips(){const el=body.querySelector(".bns-srcs");if(!el||!S)return;
  el.innerHTML=[...S.src.values()].map(chip).join("")+S.una.map(u=>`<span class="bns-src na" title="${esc(u.why)}">${esc(u.label)} · n/a</span>`).join("")}
 function renderStat(){if(!S)return;const n=[...S.src.values()],dn=n.filter(s=>!/^(searching|waiting)$/.test(s.status)).length;
  P(".bns-stat").textContent=(S.dbms!=null?`Database: ${S.dbms} ms server · ${S.dbclient} ms total`:"Database: searching…")+" · "+
   (S.done?(S.done.error?"Live scan: stopped early":S.done.live===false?"Live scan: not run":`Live scan: ${S.done.cached?"cached ("+S.done.age_s+" s old)":(S.done.live_ms/1000).toFixed(1)+" s"} · ${S.done.sources_ok??dn}/${n.length} sources answered`):`Live scan: ${dn}/${n.length} sources answered…`)}
 function filt(arr){const c=P('[data-f="cat"]').value,m=+P('[data-f="min"]').value,w=P('[data-f="watch"]').checked,so=P('[data-f="sort"]').value;
  const tt=x=>Date.parse(x.event_time||x.first_seen||0)||0;
  let a=arr.filter(x=>x.watchlist!==2&&(!c||x.category===c)&&(x.rank|0)>=m&&(w||x.watchlist!==1));
  if(so==="rank")a.sort((x,y)=>(y.rank-x.rank)||(tt(y)-tt(x)));else if(so==="new")a.sort((x,y)=>tt(y)-tt(x));else a.sort((x,y)=>(y.relevance||0)-(x.relevance||0)||(y.rank-x.rank));
  return a}
 function row(x){const link=(x.links||[]).map(l=>({...l,url:safe(l.url)})).filter(l=>l.url);const main=link[0];
  const tags=[];if((x.eff_families|0)>=2)tags.push(`<span class="bns-tag conf" title="Independent source families: ${esc((x.families||[]).join(", "))}">✔ Confirmed by ${x.eff_families} sources</span>`);
  if(x.watchlist===1)tags.push(`<span class="bns-tag unc" title="Single-source / low confidence: Watchlist only">Watchlist · UNCONFIRMED</span>`);
  tags.push(x.origin==="live"?`<span class="bns-tag live" title="Found by this live scan only. Not added to the feed.">Live only · not in feed</span>`:x.origin==="db+live"?`<span class="bns-tag live" title="In the feed; this live scan found more reports: ${esc((x.live_sources||[]).join(", "))}">In feed + live reports</span>`:`<span class="bns-tag">In feed</span>`);
  const srcs=(x.sources||[]).slice(0,3).join(", ")+((x.sources||[]).length>3?` +${x.sources.length-3}`:"");
  return `<div class="bns-res${x._fresh?" fresh":""}">${rk(x.rank,1)}<div>${main?`<a class="bns-t" href="${esc(main.url)}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a>`:`<span class="bns-t">${esc(x.title)}</span>`}
  <div class="bns-m">score ${x.score}/100 · ${esc(x.category||"other")}${x.location?" · 📍 "+esc(String(x.location).slice(0,80)):""} · ${esc(fmt(x.event_time||x.first_seen))} · ${esc(srcs)}</div>
  <div class="bns-tags">${tags.join("")}</div>${link.length>1?`<div class="bns-links">${link.slice(0,4).map(l=>`<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(String(l.source||"source").slice(0,40))} ↗</a>`).join("")}</div>`:""}</div></div>`}
 function render(){if(!S)return;
  const dbArr=S.dbmap?[...S.dbmap.values()]:[],liveArr=[...S.live.values()];
  const cats=[...new Set([...dbArr,...liveArr].map(x=>x.category).filter(Boolean))].sort();const cs=P('[data-f="cat"]'),cv=cs.value;
  cs.innerHTML=`<option value="">All</option>`+cats.map(c=>`<option${c===cv?" selected":""}>${esc(c)}</option>`).join("");
  const skel=n=>Array.from({length:n},()=>`<div class="bns-skel"></div>`).join("");
  const D=filt(dbArr),L=filt(liveArr),hidL=liveArr.filter(x=>x.watchlist===2).length;
  let h=`<div class="bns-srcs"></div>`+S.notes.map(t=>`<div class="bns-note">${esc(t)}</div>`).join("");
  h+=`<div class="bns-sec"><span>From the database</span><small>${S.db?`${D.length} shown${S.db.length>D.length?" of "+S.db.length:""}${S.mode==="or"?" · partial matches (not every word found)":""}${S.hidden?` · ${S.hidden} noise posts hidden`:""}`:"searching…"}</small></div>`;
  h+=S.db?(D.length?D.map(row).join(""):`<div class="bns-empty">No stored alerts match${dbArr.length?" these filters":""}.</div>`):skel(4);
  h+=`<div class="bns-sec"><span>Live scan · not added to the feed</span><small>${S.running?"scanning sources…":S.done&&S.done.live===false?"not run":`${L.length} new stor${L.length==1?"y":"ies"}${hidL?` · ${hidL} noise posts hidden`:""}`}</small></div>`;
  h+=L.length?L.map(row).join(""):"";
  if(S.running)h+=skel(L.length?1:3);else if(!L.length)h+=`<div class="bns-empty">${S.limited?"Live scan not run.":"No new stories beyond what is already in the database."}</div>`;
  h+=`<div class="bns-foot">Ranks and scores use the scanner's own 0–10 / 0–100 rules (70 = rank 7) and its dedupe; reports of the same event are merged and counted as independent sources. Single-source items are Watchlist / UNCONFIRMED. Live results are research leads only, kept for 10 minutes and never added to the feed or alerts. <a href="${esc(new URL("../../scoring",API).href)}" style="color:var(--ac,#4aa3ff)">How we score</a>.</div>`;
  const st=body.scrollTop;body.innerHTML=h;body.scrollTop=st;renderChips();renderStat();
  dbArr.concat(liveArr).forEach(x=>delete x._fresh)}
 function fromHash(){const m=location.hash.match(/^#search=(.+)$/);if(!m)return;let q="";try{q=decodeURIComponent(m[1])}catch(e){return}if(q&&(!S||S.q!==q||!panel.classList.contains("on")))open(q)}
 addEventListener("hashchange",fromHash);fromHash();
})();
