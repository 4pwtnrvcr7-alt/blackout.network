/* blackout.network · English subtitles for linked foreign-language videos (display-only).
   Adds a "CC EN" button next to every allow-listed video link (YouTube, Telegram, X, Rumble, direct .mp4). Clicking opens a panel
   under the link: player (YouTube embed synced over postMessage, or <video> with <track> for Telegram/direct files), the
   "Translated from …" label, an English / Original / Both toggle and a clickable transcript. When translation isn't possible the panel
   shows a neutral "Translation is not supported" notice with the reason and a link to the original platform. */
(()=>{
const VRX=/^https?:\/\/(?:(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?[^#]*v=|shorts\/|live\/|embed\/)|youtu\.be\/)[\w-]{11}|(?:www\.)?t\.me\/(?:s\/)?[A-Za-z0-9_]{4,64}\/\d+\/?(?:[?#].*)?$|(?:www\.|mobile\.)?(?:x|twitter)\.com\/[A-Za-z0-9_]{1,15}\/status\/\d+|(?:www\.)?rumble\.com\/v[0-9a-z]{4,12}[\w-]*\.html|[^?#]+\.(?:mp4|webm|m4v)(?:[?#]|$))/i;
const RTLL=new Set(["ar","fa","he","iw","ur","ps","yi","sd","ug","dv"]);
const T=s=>{try{const f=window.bnT||(window.BN_I18N&&window.BN_I18N.t)||(window.bnI18n&&window.bnI18n.t);return f?f(s):s}catch(e){return s}};
const e=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const mmss=s=>{s=Math.max(0,Math.floor(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=String(s%60).padStart(2,"0");return h?`${h}:${String(m).padStart(2,"0")}:${x}`:`${m}:${x}`};
const ytId=u=>{const m=u.match(/(?:v=|youtu\.be\/|shorts\/|live\/|embed\/)([\w-]{11})/);return m?m[1]:null};
const MODE_KEY="bn_vs_mode";let mode=localStorage.getItem(MODE_KEY)||"en";
const OPEN=new Map(); // url -> panel; dashboard tabs re-render every 45-60 s, so open panels are re-attached to the fresh link
const NEUTRAL_FALLBACK="Translation couldn't be completed for this video.";
function addButtons(root){
 (root||document).querySelectorAll("main a[href]:not([data-vs]),#vs-test a[href]:not([data-vs])").forEach(a=>{
  a.dataset.vs="1";const h=a.getAttribute("href")||"";if(!VRX.test(h)||a.closest(".vs-panel"))return;
  const b=document.createElement("button");b.type="button";b.className="vs-btn";b.setAttribute("translate","no");b.textContent="CC EN";b.title=T("English subtitles / translation for this video");
  b.addEventListener("click",ev=>{ev.preventDefault();ev.stopPropagation();toggle(a,b)});a.after(b);
  const p=OPEN.get(a.href);if(p&&!p.isConnected&&(a.closest("main")||{}).id===p._main){(a.closest(".meta")||a.parentElement).after(p);b._panel=p;b.classList.add("on");p._btn=b}})}
function toggle(a,b){
 if(b._panel){clearTimeout(b._panel._t);OPEN.delete(b._panel.dataset.url);b._panel.remove();b._panel=null;b.classList.remove("on");return}
 b.classList.add("on");const p=document.createElement("div");p.className="vs-panel";p.dataset.url=a.href;
 const host=a.closest(".meta")||a.parentElement;host.after(p);b._panel=p;p._main=(a.closest("main")||{}).id;OPEN.set(a.href,p);
 const sc=a.closest(".st-card");p._hasOwnPlayer=!!(sc&&sc.querySelector(".st-play")); // Live Streams tiles already have a player
 load(p,a.href,0)}
async function load(p,url,n,retry){
 if(!p.isConnected&&!OPEN.has(url))return;let d;
 try{const r=await fetch("/api/video_subs?url="+encodeURIComponent(url)+(retry?"&retry=1":""));d=await r.json()}catch(x){d={status:"unsupported",reason:"generic",reason_text:NEUTRAL_FALLBACK,watch_url:url,watch_label:"Open original ↗"}}
 render(p,d,url);
 if(["queued","processing","none"].includes(d.status)&&n<450)p._t=setTimeout(()=>load(p,url,n+1),4000)}
function player(p,d){
 if(p._hasOwnPlayer||p.querySelector(".vs-player"))return p.querySelector(".vs-player");
 let html="";const id=d.platform=="youtube"?ytId(d.watch_url||""):null;
 if(id)html=`<iframe src="https://www.youtube-nocookie.com/embed/${id}?enablejsapi=1&playsinline=1&rel=0&origin=${encodeURIComponent(location.origin)}" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin" title="video" loading="lazy"></iframe>`;
 else if((d.platform=="telegram"||d.platform=="direct")&&d.media_url)html=`<video controls preload="metadata" playsinline src="${e(d.media_url)}"></video>`;
 else if(d.platform=="telegram"){const m=(d.watch_url||"").match(/t\.me\/([A-Za-z0-9_]+)\/(\d+)/);if(m)html=`<iframe src="https://t.me/${m[1]}/${m[2]}?embed=1" title="Telegram post" loading="lazy" style="background:#fff"></iframe>`}
 if(!html)return null;
 const w=document.createElement("div");w.className="vs-player";w.innerHTML=html;p.prepend(w);
 const v=w.querySelector("video");if(v)v.addEventListener("error",()=>{w.remove()},{once:true});
 const f=w.querySelector("iframe[src*='youtube']");if(f)f.addEventListener("load",()=>{p._yt=f;try{f.contentWindow.postMessage(JSON.stringify({event:"listening",id:"vs",channel:"widget"}),"*")}catch(x){}});
 return w}
function notice(d,title,why,cls){
 const link=d.watch_url?`<a href="${e(d.watch_url)}" target="_blank" rel="noopener noreferrer">${e(T(d.watch_label||"Watch on the original platform ↗"))}</a>`:"";
 return `<div class="vs-notice ${cls||""}" role="note"><span class="i" aria-hidden="true">i</span><div><div class="h">${e(T(title))}</div><div class="w">${e(T(why))}</div>${link}</div></div>`}
function trLinks(root){ // the site picker leaves link text alone, so translate our "Watch on … ↗" links through the same /api/translate engine
 const L=window.BNTR&&BNTR.lang;if(!L||L=="en"||BNTR.engine=="google")return;root.querySelectorAll(".vs-notice a").forEach(async a=>{const src=a.dataset.src||a.textContent;a.dataset.src=src;
  try{const r=await fetch("/api/translate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({to:L,texts:[src.replace(/\s*↗$/,"")]})});const j=await r.json();if(j.out&&j.out[0])a.textContent=j.out[0]+" ↗"}catch(x){}})}
function render(p,d,url){
 const st=d.status;let body=p.querySelector(".vs-body");if(!body){body=document.createElement("div");body.className="vs-body";p.append(body)}
 if(st==="done"){
  if(p._done)return;p._done=true;player(p,d);
  const v=p.querySelector("video");if(v&&!v.querySelector("track")){const q="/api/video_subs/vtt?url="+encodeURIComponent(url);
   v.insertAdjacentHTML("beforeend",`<track kind="subtitles" srclang="en" label="${e(T("English (machine translation)"))}" src="${q}&track=en" default><track kind="subtitles" srclang="${e(d.src_lang||"und")}" label="${e(d.src_lang_name||"Original")}" src="${q}&track=orig">`);v.crossOrigin=null}
  const rtl=RTLL.has((d.src_lang||"").split("-")[0]);
  body.innerHTML=`<div class="vs-capbar" aria-live="polite"></div>
  <div class="vs-label"><b>${e(T("Translated from"))} ${e(T(d.src_lang_name))}</b> · ${e(T("machine translation"))} (${e(T(d.method||""))})${d.partial?` · ${e(T("translated part"))}: ${e(T(d.partial))}`:""}
   <span class="vs-tog" role="group" aria-label="${e(T("Subtitle language"))}"><button data-m="en">${e(T("English"))}</button><button data-m="orig">${e(T("Original"))} (${e(d.src_lang_name)})</button><button data-m="both">${e(T("Both"))}</button></span></div>
  <div class="vs-tx">${(()=>{const M=assignOrig(d.cues_en||[],d.cues_orig||[]);return (d.cues_en||[]).map((c,i)=>{const o=M[i];return `<div class="vs-cue" data-s="${c[0]}" data-e="${c[1]}"><span class="t">${mmss(c[0])}</span><span class="en">${e(c[2])}</span><span class="o" translate="no" lang="${e(d.src_lang||"")}" dir="${rtl?"rtl":"auto"}">${e(o)}</span></div>`}).join("")})()}</div>
  <div class="vs-note">${e(T("Machine translation can miss names, numbers and nuance. Verify against the original before relying on it."))} ${e(d.model?("Engine: "+d.model+"."):"")} ${e(d.lang_method?("Language detected from "+d.lang_method+"."):"")}</div>`;
  if(!p._hasOwnPlayer&&!p.querySelector(".vs-player"))body.insertAdjacentHTML("beforeend",notice(d,"Video can't be embedded here","The translated transcript is shown above.","ok"));
  body.querySelectorAll(".vs-tog button").forEach(b=>b.onclick=()=>{mode=b.dataset.m;localStorage.setItem(MODE_KEY,mode);applyMode(p)});
  body.querySelectorAll(".vs-cue").forEach(r=>r.onclick=()=>seek(p,+r.dataset.s));applyMode(p);startSync(p);return}
 if(st==="english"){player(p,d);body.innerHTML=notice(d,"No translation needed",d.label||"This video is already in English.","ok");trLinks(body);return}
 if(st==="unsupported"){
  player(p,d);const retry=["rate_limited","timeout","queue_full","generic","download_blocked"].includes(d.reason);
  body.innerHTML=notice(d,d.notice_title||"Translation is not supported",d.reason_text||NEUTRAL_FALLBACK)+(retry?`<button class="vs-retry">${e(T("Try again"))}</button>`:"");
  const rb=body.querySelector(".vs-retry");if(rb)rb.onclick=()=>{p._done=false;load(p,url,0,true)};trLinks(body);return}
 // queued / processing / none
 player(p,d);
 const eta=d.eta_s?` ~${Math.max(1,Math.round(d.eta_s/60))} min`:"";
 const msg=st==="processing"?`${T("Translating…")}${eta}`:st==="queued"?(d.retrying?T("Waiting to retry (the platform limited requests)…"):`${T("Queued for translation")}${d.queue_pos?` (#${d.queue_pos+1} ${T("in line")})`:""}…`):T("Checking video…");
 body.innerHTML=`<span class="vs-chip">${e(msg)}</span><div class="vs-note">${e(T("Runs on our own server at low priority. You can keep browsing; this panel updates by itself."))}</div>`}
function assignOrig(en,orig){ // each original cue goes to the English cue it overlaps most (nearest start if none overlap)
 const out=en.map(()=>[]);if(!en.length)return [];let j=0;
 for(const o of orig){let best=-1,bo=0;for(let i=Math.max(0,j-3);i<en.length&&en[i][0]<o[1]+1;i++){const ov=Math.min(en[i][1],o[1])-Math.max(en[i][0],o[0]);if(ov>bo){bo=ov;best=i}}
  if(best<0){let md=1e9;for(let i=Math.max(0,j-3);i<Math.min(en.length,j+6);i++){const dd=Math.abs(en[i][0]-o[0]);if(dd<md){md=dd;best=i}}}
  if(best>=0){out[best].push(o[2]);j=best}}
 return out.map(x=>x.join(" "))}
function applyMode(p){
 p.querySelectorAll(".vs-tog button").forEach(b=>b.classList.toggle("on",b.dataset.m==mode));
 const tx=p.querySelector(".vs-tx");if(!tx)return;tx.classList.toggle("both",mode=="both");
 tx.querySelectorAll(".vs-cue").forEach(r=>{r.querySelector(".en").style.display=mode=="orig"?"none":"";r.querySelector(".o").style.display=mode=="en"?"none":""});
 const v=p.querySelector("video");if(v&&v.textTracks)[...v.textTracks].forEach((t,i)=>t.mode=(mode=="orig"?i==1:i==0)?"showing":"hidden");
 caption(p,p._now||0,true)}
function seek(p,t){
 const v=p.querySelector("video");if(v){v.currentTime=t;v.play().catch(()=>{});return}
 const f=p.querySelector(".vs-player iframe[src*='youtube']");if(f){const s=x=>f.contentWindow.postMessage(JSON.stringify(x),"*");s({event:"command",func:"seekTo",args:[t,true]});s({event:"command",func:"playVideo",args:[]})}}
function caption(p,t,force){
 p._now=t;const rows=[...p.querySelectorAll(".vs-cue")];let cur=null;
 for(const r of rows){if(+r.dataset.s<=t+0.2&&t<=+r.dataset.e+0.6)cur=r}
 if(cur===p._cur&&!force)return;p._cur=cur;rows.forEach(r=>r.classList.toggle("cur",r===cur));
 const bar=p.querySelector(".vs-capbar");if(bar&&!p.querySelector("video")){
  if(!cur){bar.innerHTML="";return}const en=cur.querySelector(".en").textContent,o=cur.querySelector(".o");
  bar.innerHTML=mode=="orig"?`<span translate="no" dir="${o.dir}">${e(o.textContent)}</span>`:mode=="both"?`${e(en)}<span class="o" translate="no" dir="${o.dir}">${e(o.textContent)}</span>`:e(en)}
 if(cur&&!force){const tx=p.querySelector(".vs-tx");const y=cur.offsetTop-tx.offsetTop-tx.clientHeight/3;if(Math.abs(tx.scrollTop-y)>40)tx.scrollTo({top:y,behavior:"smooth"})}}
function startSync(p){const v=p.querySelector("video");if(v){v.addEventListener("timeupdate",()=>caption(p,v.currentTime));return}}
window.addEventListener("message",ev=>{ // YouTube embed reports currentTime over postMessage once we've sent {event:"listening"}
 if(!/youtube(-nocookie)?\.com$/.test(new URL(ev.origin).hostname))return;let d;try{d=typeof ev.data=="string"?JSON.parse(ev.data):ev.data}catch(x){return}
 if(!d||!d.info||typeof d.info.currentTime!="number")return;
 document.querySelectorAll(".vs-panel").forEach(p=>{const f=p.querySelector(".vs-player iframe");if(f&&f.contentWindow===ev.source)caption(p,d.info.currentTime)})});
let tm=null;new MutationObserver(()=>{clearTimeout(tm);tm=setTimeout(()=>addButtons(),400)}).observe(document.body,{childList:true,subtree:true});
addButtons();window.BN_VSUBS={addButtons,open:(a)=>{const b=a.nextElementSibling;if(b&&b.classList.contains("vs-btn"))b.click()}};
})();
