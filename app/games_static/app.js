// ---- Games tab (served by games.py). Self-hosted original 8-bit games; nothing leaves this computer. ----
(()=>{"use strict";
const M=document.getElementById("tab-games");if(!M)return;
const E=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
// ---------- tab button: its own "Play" group, placed before the Tips group; deep link #games ----------
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="games"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="games";tb.textContent="👾 Games";
 const sep=document.createElement("span");sep.className="tab-sep";const lab=document.createElement("span");lab.className="tab-grp";lab.textContent="Play";
 const tips=nav.querySelector('button[data-tab="tips"]');const anchor=tips&&tips.previousElementSibling&&tips.previousElementSibling.classList.contains("tab-sep")?tips.previousElementSibling:null;
 if(anchor){nav.insertBefore(sep,anchor);nav.insertBefore(lab,anchor);nav.insertBefore(tb,anchor)}else{nav.appendChild(sep);nav.appendChild(lab);nav.appendChild(tb)}}
try{if(typeof TABHASH=="object"){TABHASH.games="games";HASHTAB.games="games"}}catch(_){}
if(typeof hwAttach=="function"){
 try{if(typeof HW_ICONS=="object"&&typeof hwI=="function"&&!HW_ICONS.games)HW_ICONS.games=hwI(`<rect x="40" y="30" width="120" height="56" rx="18"/><path d="M66 50 v16 M58 58 h16"/><circle cx="128" cy="52" r="5" stroke="#ff4d4f"/><circle cx="142" cy="64" r="5" stroke="#ff4d4f"/>`)}catch(_){}
 hwAttach(M.querySelector("#gm_top h2"),"games",()=>"Every game here was written from scratch for this dashboard, with original pixel art drawn in code. The names are generic and each card says which classic inspired it. No ROMs, emulators, copied sprites, music or outside servers are used. Pictures are drawn on an HTML5 canvas, and the beeps are made live by your browser's Web Audio synthesizer, so there are no sound files. Only one game runs at a time. Opening a game captures the arrow keys and space bar so the page doesn't scroll, and closing it, or switching tabs, releases them and pauses the game. High scores, best times, the sound setting and your last difficulty are saved only in this browser (localStorage). Nothing is sent anywhere, and games never touch the scanner, scores or alerts.")}
// ---------- skeleton ----------
const app=document.getElementById("gm_app");
const CATS=["All","Arcade","Action","Puzzle","Board/Card","Classic"];
app.innerHTML=`<div class="gm-bar"><input id="gm_q" type="search" placeholder="Search games (name, classic, style)…" autocomplete="off" aria-label="Search games">
 <div class="gm-chips" role="group" aria-label="Filter by category">${CATS.map((c,i)=>`<button type="button" class="gm-chip${i?"":" on"}" data-cat="${E(c)}" aria-pressed="${i?"false":"true"}">${E(c)}</button>`).join("")}</div>
 <span class="meta" id="gm_count"></span></div>
 <div id="gm_grid" class="gm-grid"><div class="meta">Loading games…</div></div><div id="gm_play" hidden></div>`;
const G={loaded:false,loading:false,cat:"All",q:"",thumbs:{},want:(/^#games\/([a-z0-9_]+)$/.exec(location.hash||"")||[])[1]||null};
const $g=id=>document.getElementById(id);
function best(d){const ks=Object.keys(localStorage).filter(k=>k=="bn_games_hi_"+d.id||k.startsWith("bn_games_hi_"+d.id+"_"));if(!ks.length)return null;
 const vs=ks.map(k=>+localStorage.getItem(k)).filter(v=>isFinite(v));if(!vs.length)return null;return d.best=="time"?"best "+BNG.fmtT(Math.min(...vs)):"best "+Math.max(...vs)}
function render(){const grid=$g("gm_grid");if(!window.BNG)return;const q=G.q.trim().toLowerCase();
 const ORDER=["snake","jumper","blockdrop","maze","rocks","breakout","pong","invaders","centipede","swarm","frogger","barrels","missile","tank","cube","digger","gems","lander","simon","t2048","t4096","n81","mines","solitaire","chess","checkers"],rank=d=>{const i=ORDER.indexOf(d.id);return i<0?99:i};
 const list=BNG.games.slice().sort((a,b)=>rank(a)-rank(b)).filter(d=>(G.cat=="All"||d.cats.includes(G.cat))&&(!q||[d.name,d.inspired,d.desc,d.cats.join(" ")].join(" ").toLowerCase().includes(q)));
 $g("gm_count").textContent=`${list.length} of ${BNG.games.length} games`;
 if(!list.length){grid.innerHTML=`<div class="meta">No games match “${E(G.q)}”.</div>`;return}
 grid.innerHTML=list.map(d=>`<button type="button" class="gm-card" data-id="${E(d.id)}" aria-label="Play ${E(d.name)}"><div class="gm-th" data-th="${E(d.id)}"></div>
  <div class="gm-ci"><b>${E(d.name)}</b><span class="gm-cats">${d.cats.map(c=>`<i>${E(c)}</i>`).join("")}</span></div>
  <div class="gm-insp">Inspired by ${E(d.inspired)}</div><div class="gm-d">${E(d.desc)}</div><div class="gm-hi">${E(best(d)||"no score yet")}</div></button>`).join("");
 grid.querySelectorAll("[data-th]").forEach(el=>{const id=el.dataset.th;let cv=G.thumbs[id];if(!cv){cv=G.thumbs[id]=BNG.thumb(BNG.games.find(d=>d.id==id))}el.appendChild(cv)})}
function play(id){const d=BNG.games.find(x=>x.id==id);if(!d)return;$g("gm_grid").hidden=true;app.querySelector(".gm-bar").hidden=true;const p=$g("gm_play");p.hidden=false;
 BNG.open(id,p,back);try{history.replaceState(null,"","#games/"+id)}catch(_){}const st=p.querySelector(".gm-stage");if(st)st.scrollIntoView({block:"center"})}
function back(){BNG.close();$g("gm_play").hidden=true;$g("gm_grid").hidden=false;app.querySelector(".gm-bar").hidden=false;try{history.replaceState(null,"","#games")}catch(_){}render()}
app.addEventListener("click",e=>{const c=e.target.closest(".gm-card");if(c){play(c.dataset.id);return}
 const ch=e.target.closest(".gm-chip");if(ch){G.cat=ch.dataset.cat;app.querySelectorAll(".gm-chip").forEach(b=>{b.classList.toggle("on",b==ch);b.setAttribute("aria-pressed",String(b==ch))});render()}});
$g("gm_q").addEventListener("input",e=>{G.q=e.target.value;render()});
function load(){if(G.loaded||G.loading)return Promise.resolve();G.loading=true;return new Promise(res=>{const sc=document.createElement("script");sc.src="api/games/bundle.js";
 sc.onload=()=>{G.loaded=true;G.loading=false;render();res()};sc.onerror=()=>{G.loading=false;$g("gm_grid").innerHTML=`<div class="meta">Couldn't load the games bundle from this computer. Try ⟳ reloading the page.</div>`;res()};document.head.appendChild(sc)})}
function onShow(){const w=G.want;G.want=null;load().then(()=>{if(w&&!(BNG.cur&&BNG.cur.def.id==w))play(w);else if(BNG.cur&&!$g("gm_play").hidden){try{history.replaceState(null,"","#games/"+BNG.cur.def.id)}catch(_){}}})}
const shown=()=>M.style.display!="none";
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(!b)return;if(b.dataset.tab=="games")setTimeout(onShow,0);else if(window.BNG)BNG.pause()});
addEventListener("hashchange",()=>{const m=/^#games\/([a-z0-9_]+)$/.exec(location.hash||"");if(!m)return;G.want=m[1];if(tb&&!tb.classList.contains("on"))tb.click();else onShow()});
if((location.hash||"").startsWith("#games"))setTimeout(()=>{if(tb&&!tb.classList.contains("on"))tb.click();else onShow()},350);
window.BNG_UI={play,back,load};
})();
