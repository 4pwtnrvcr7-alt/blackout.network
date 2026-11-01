// ---- blackout.network Sources catalog: /sources list (search, filter, sort, paging, rating reasons), submit form, dashboard Reference-tab card ----
(function(){
const API="/api/sources/",$=id=>document.getElementById(id),esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmtET(iso){if(!iso)return "—";const d=new Date(iso);if(isNaN(d))return "—";return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)}
const BL={blue:"9–10 official / fully trusted",green:"7–8 reliable",amber:"4–6 mixed: confirm first",red:"0–3 unverified / low trust",na:"collector, not a source"};
// ---- category colors + icons (t237 visual pass). Icons: Lucide v1.66.0 (ISC license, https://lucide.dev), path data bundled here, no CDN ----
const BNI={"graduation-cap":"<path d=\"M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z\"/><path d=\"M22 10v6\"/><path d=\"M6 12.5V16a6 3 0 0 0 12 0v-3.5\"/>","cloud-sun-rain":"<path d=\"M12 2v2\"/><path d=\"m4.93 4.93 1.41 1.41\"/><path d=\"M20 12h2\"/><path d=\"m19.07 4.93-1.41 1.41\"/><path d=\"M15.947 12.65a4 4 0 0 0-5.925-4.128\"/><path d=\"M3 20a5 5 0 1 1 8.9-4H13a3 3 0 0 1 2 5.24\"/><path d=\"M11 20v2\"/><path d=\"M7 19v2\"/>","activity":"<path d=\"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2\"/>","satellite":"<path d=\"m13.5 6.5-3.148-3.148a1.205 1.205 0 0 0-1.704 0L6.352 5.648a1.205 1.205 0 0 0 0 1.704L9.5 10.5\"/><path d=\"M16.5 7.5 19 5\"/><path d=\"m17.5 10.5 3.148 3.148a1.205 1.205 0 0 1 0 1.704l-2.296 2.296a1.205 1.205 0 0 1-1.704 0L13.5 14.5\"/><path d=\"M9 21a6 6 0 0 0-6-6\"/><path d=\"M9.352 10.648a1.205 1.205 0 0 0 0 1.704l2.296 2.296a1.205 1.205 0 0 0 1.704 0l4.296-4.296a1.205 1.205 0 0 0 0-1.704l-2.296-2.296a1.205 1.205 0 0 0-1.704 0z\"/>","waves":"<path d=\"M2 12q2.5 2 5 0t5 0 5 0 5 0\"/><path d=\"M2 19q2.5 2 5 0t5 0 5 0 5 0\"/><path d=\"M2 5q2.5 2 5 0t5 0 5 0 5 0\"/>","stethoscope":"<path d=\"M11 2v2\"/><path d=\"M5 2v2\"/><path d=\"M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1\"/><path d=\"M8 15a6 6 0 0 0 12 0v-3\"/><circle cx=\"20\" cy=\"10\" r=\"2\"/>","landmark":"<path d=\"M10 18v-7\"/><path d=\"M11.119 2.205a2 2 0 0 1 1.762 0l7.84 3.846A.5.5 0 0 1 20.5 7h-17a.5.5 0 0 1-.22-.949z\"/><path d=\"M14 18v-7\"/><path d=\"M18 18v-7\"/><path d=\"M3 22h18\"/><path d=\"M6 18v-7\"/>","newspaper":"<path d=\"M15 18h-5\"/><path d=\"M18 14h-8\"/><path d=\"M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-4 0v-9a2 2 0 0 1 2-2h2\"/><rect width=\"8\" height=\"4\" x=\"10\" y=\"6\" rx=\"1\"/>","shield-check":"<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\"/><path d=\"m9 12 2 2 4-4\"/>","shield-user":"<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\"/><path d=\"M6.376 18.91a6 6 0 0 1 11.249.003\"/><circle cx=\"12\" cy=\"11\" r=\"4\"/>","siren":"<path d=\"M7 18v-6a5 5 0 1 1 10 0v6\"/><path d=\"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z\"/><path d=\"M21 12h1\"/><path d=\"M18.5 4.5 18 5\"/><path d=\"M2 12h1\"/><path d=\"M12 2v1\"/><path d=\"m4.929 4.929.707.707\"/><path d=\"M12 12v6\"/>","radio":"<path d=\"M16.247 7.761a6 6 0 0 1 0 8.478\"/><path d=\"M19.075 4.933a10 10 0 0 1 0 14.134\"/><path d=\"M4.925 19.067a10 10 0 0 1 0-14.134\"/><path d=\"M7.753 16.239a6 6 0 0 1 0-8.478\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/>","chart-column":"<path d=\"M3 3v16a2 2 0 0 0 2 2h16\"/><path d=\"M18 17V9\"/><path d=\"M13 17V5\"/><path d=\"M8 17v-3\"/>","network":"<rect x=\"16\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\"/><rect x=\"2\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\"/><rect x=\"9\" y=\"2\" width=\"6\" height=\"6\" rx=\"1\"/><path d=\"M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3\"/><path d=\"M12 12V8\"/>","building-2":"<path d=\"M10 12h4\"/><path d=\"M10 8h4\"/><path d=\"M14 21v-3a2 2 0 0 0-4 0v3\"/><path d=\"M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2\"/><path d=\"M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16\"/>","swords":"<path d=\"m13 19 6-6\"/><path d=\"M14.5 17.5 3.586 6.586A2 2 0 013 5.172V3h2.172a2 2 0 011.414.586L17.5 14.5\"/><path d=\"m14.828 6.172 2.586-2.586A2 2 0 0118.828 3H21v2.172a2 2 0 01-.586 1.414l-2.586 2.586\"/><path d=\"m16 16 4 4\"/><path d=\"m19 21 2-2\"/><path d=\"m5 14 4 4\"/><path d=\"m5 21-2-2\"/><path d=\"M7.5 16.5 4 20\"/>","biohazard":"<circle cx=\"12\" cy=\"11.9\" r=\"2\"/><path d=\"M6.7 3.4c-.9 2.5 0 5.2 2.2 6.7C6.5 9 3.7 9.6 2 11.6\"/><path d=\"m8.9 10.1 1.4.8\"/><path d=\"M17.3 3.4c.9 2.5 0 5.2-2.2 6.7 2.4-1.2 5.2-.6 6.9 1.5\"/><path d=\"m15.1 10.1-1.4.8\"/><path d=\"M16.7 20.8c-2.6-.4-4.6-2.6-4.7-5.3-.2 2.6-2.1 4.8-4.7 5.2\"/><path d=\"M12 13.9v1.6\"/><path d=\"M13.5 5.4c-1-.2-2-.2-3 0\"/><path d=\"M17 16.4c.7-.7 1.2-1.6 1.5-2.5\"/><path d=\"M5.5 13.9c.3.9.8 1.8 1.5 2.5\"/>","tornado":"<path d=\"M21 4H3\"/><path d=\"M18 8H6\"/><path d=\"M19 12H9\"/><path d=\"M16 16h-6\"/><path d=\"M11 20H9\"/>","shield-alert":"<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\"/><path d=\"M12 8v4\"/><path d=\"M12 16h.01\"/>","sun":"<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2\"/><path d=\"M12 20v2\"/><path d=\"m4.93 4.93 1.41 1.41\"/><path d=\"m17.66 17.66 1.41 1.41\"/><path d=\"M2 12h2\"/><path d=\"M20 12h2\"/><path d=\"m6.34 17.66-1.41 1.41\"/><path d=\"m19.07 4.93-1.41 1.41\"/>","vote":"<path d=\"m9 12 2 2 4-4\"/><path d=\"M5 7c0-1.1.9-2 2-2h10a2 2 0 0 1 2 2v12H5V7Z\"/><path d=\"M22 19H2\"/>","banknote":"<rect width=\"20\" height=\"12\" x=\"2\" y=\"6\" rx=\"2\"/><circle cx=\"12\" cy=\"12\" r=\"2\"/><path d=\"M6 12h.01M18 12h.01\"/>","book-open":"<path d=\"M12 5v16\"/><path d=\"M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z\"/>","mail":"<path d=\"m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7\"/><rect x=\"2\" y=\"4\" width=\"20\" height=\"16\" rx=\"2\"/>","book-marked":"<path d=\"M10 2v7.751a.25.25 0 00.407.195l2.28-1.834a.5.5 0 01.627 0l2.28 1.834A.25.25 0 0016 9.751V2\"/><path d=\"M4 19.5v-15A2.5 2.5 0 016.5 2H19a1 1 0 011 1v18a1 1 0 01-1 1H6.5a1 1 0 010-5H20\"/>"};
const BNCAT={"Research & academia":["graduation-cap","#f2d55f"],"Weather, radar & ocean":["cloud-sun-rain","#4fe0d6"],"Seismic, volcanic & geophysical":["activity","#ff9f5a"],
 "Satellites & space":["satellite","#b98cff"],"Hydrology & flood gauges":["waves","#5fc8f2"],"Health & medical institutions":["stethoscope","#ff7a9c"],
 "Government & public agencies":["landmark","#e07cf2"],"News & media":["newspaper","#f26fc8"],"Security & cyber":["shield-check","#6f9dff"],
 "Police & law enforcement":["shield-user","#9a9aff"],"Emergency management":["siren","#ff6363"],"Scanner & public-safety audio":["radio","#8fe85c"],
 "Government data feeds":["chart-column","#c8ec5a"],"Internet outage sensors":["network","#5ff2b0"],"Local government":["building-2","#d9b38c"],
 "war/conflict":["swords","#ff6363"],"disease":["biohazard","#fa8c16"],"natural disaster":["tornado","#36cfc9"],"cyber":["shield-alert","#4aa3ff"],
 "space weather":["sun","#b98cff"],"political":["vote","#f26fc8"],"financial":["banknote","#fadb14"]};
const bnIco=(n,c)=>`<svg class="${c||"bn-ico"}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${BNI[n]||BNI["book-marked"]}</svg>`;
const catOf=c=>BNCAT[c]||["book-marked","#8b95a3"],catSt=c=>`--cc:${catOf(c)[1]}`;
window.BNcat={icon:bnIco,of:catOf};
function bnDecorate(root){(root||document).querySelectorAll("[data-ccat]:not([data-cdone])").forEach(el=>{const[i,col]=catOf(el.dataset.ccat);el.style.setProperty("--cc",col);el.dataset.cdone=1;
  if(el.hasAttribute("data-cico"))el.insertAdjacentHTML("afterbegin",`<span class="sd-tile sm" aria-hidden="true">${bnIco(i)}</span>`)});
 (root||document).querySelectorAll("[data-ico]:not([data-cdone])").forEach(el=>{el.dataset.cdone=1;el.innerHTML=bnIco(el.dataset.ico)})}
bnDecorate();
function reasonText(r){return (r.reason||[]).map(s=>`${s[0]}: ${s[1]} (${s[2]})`).join("\n")}
function row(r){
 const rv=r.rating==null?"n/a":r.rating,cats=Object.entries(r.categories||{}).slice(0,4).map(([c,n])=>`<span class="sc-chip cat cc" style="${catSt(c)}"><i class="cdot" aria-hidden="true"></i>${esc(c)}${n?` · ${n}`:""}</span>`).join("");
 const mon=r.monitor?`<span class="sc-chip mon">${esc(r.monitor)}</span>`:"";
 const pol=r.origin=="political"?`<span class="sc-chip pol">political watch · ${esc(r.party||"")}</span>`:"";
 const ov=r.overridden?`<span class="sc-chip ov">admin override</span>`:"";
 const prof=r.profile?`<div class="pf">${esc(r.profile)}</div>`:`<div class="pf pend">Profile pending</div>`;
 const id="w"+Math.random().toString(36).slice(2,9);
 const steps=(r.reason||[]).map(s=>`<li><b>${esc(s[0])}</b> ${esc(s[1])}: ${esc(s[2])}</li>`).join("");
 const link=r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener noreferrer nofollow">${esc(r.name)}</a>`:esc(r.name);
 return `<article class="sc-row k-${r.band}"><button type="button" class="sc-r b-${r.band}" aria-expanded="false" aria-controls="${id}" title="${esc("Confidence "+rv+"/10, "+BL[r.band]+"\n"+reasonText(r))}">${rv}</button>
 <div><div class="nm">${link}</div><div>${mon}<span class="sc-chip">${esc(r.type)}</span>${pol}${ov}${cats}</div>${prof}${r.role?`<div class="sc-sm mu">${esc(r.role)}</div>`:""}${window.SDgrade?window.SDgrade(r.sid,r.grade):""}</div>
 <div class="st"><b>${(r.n_items||0).toLocaleString()}</b> item${r.n_items==1?"":"s"}<br>${r.first_seen?`first ${esc(fmtET(r.first_seen))}<br>last ${esc(fmtET(r.last_seen))}`:"no stored items"}${r.status?`<br>${esc(r.status)}`:""}</div>
 <div class="sc-why" id="${id}" hidden><b>Why ${rv}/10</b> (${esc(BL[r.band])})<ol>${steps}</ol></div></article>`}

// ---- reliability grades from visitors (1-5 stars; votes.db source_votes; never affects alert scores) + global directory ----
const SDvoter=window.SDvoter=(()=>{try{let v=localStorage.getItem("bn_voter");if(!/^[a-f0-9]{32}$/.test(v||"")){const a=new Uint8Array(16);crypto.getRandomValues(a);v=[...a].map(x=>x.toString(16).padStart(2,"0")).join("");localStorage.setItem("bn_voter",v)}return v}catch(_){return ""}})();
const gcls=g=>g&&g.grade?"g-"+g.grade.toLowerCase():"g-na";
function gradeHTML(sid,g){g=g||{n:0,label:"Not yet rated"};const mine=g.mine||0;
 const stars=[1,2,3,4,5].map(n=>`<button type="button" class="sd-star${n<=mine?" on":""}" data-sid="${esc(sid)}" data-stars="${n}" aria-label="Rate ${n} of 5 stars" aria-pressed="${n<=mine}">★</button>`).join("");
 return `<div class="sd-grade" data-sid="${esc(sid)}"><span class="sd-g ${gcls(g)}" title="${esc(g.n?`Score ${g.score}/100 from ${g.n} vote${g.n==1?"":"s"} (average ${g.avg} stars), starting point ${g.prior}/100`:`Starting point ${g.prior==null?"":g.prior+"/100"}; needs 3 votes for a grade`)}">${g.grade?esc(g.grade):"–"}</span>
 <span class="sd-gl">${esc(g.label||"Not yet rated")}</span><span class="sd-stars" role="group" aria-label="Rate this source's reliability">${stars}</span><span class="sd-msg" aria-live="polite"></span></div>`}
window.SDgrade=gradeHTML;
document.addEventListener("click",async e=>{const b=e.target.closest(".sd-star");if(!b)return;const box=b.closest(".sd-grade"),m=box.querySelector(".sd-msg");
 box.querySelectorAll(".sd-star").forEach(x=>x.disabled=true);m.textContent="Saving…";
 try{const r=await fetch("/api/vote/source",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:b.dataset.sid,stars:+b.dataset.stars,voter:SDvoter})}),j=await r.json();
  if(!r.ok){m.textContent=j.error||("Error "+r.status);box.querySelectorAll(".sd-star").forEach(x=>x.disabled=false);return}
  const t=document.createElement("div");t.innerHTML=gradeHTML(b.dataset.sid,j);const nb=t.firstElementChild;box.replaceWith(nb);nb.querySelector(".sd-msg").textContent="Thanks, rating saved."}
 catch(_){m.textContent="Couldn't save. Try again.";box.querySelectorAll(".sd-star").forEach(x=>x.disabled=false)}});
const DL=$("sd_list");
if(DL&&$("sd_q")){
 const st={page:1};let tm=0,ctl=null;
 const ccSel=$("sd_cc");try{const dn=typeof Intl.DisplayNames=="function"?new Intl.DisplayNames(["en"],{type:"region"}):null;
  JSON.parse(ccSel.dataset.cc||"[]").map(([c,n])=>[c,n,(()=>{try{return dn?dn.of(c):c}catch(_){return c}})()]).sort((a,b)=>a[2].localeCompare(b[2])).forEach(([c,n,l])=>ccSel.add(new Option(`${l} (${n.toLocaleString()})`,c)))}catch(_){}
 const dnR=(()=>{try{return new Intl.DisplayNames(["en"],{type:"region"})}catch(_){return null}})(),flag=c=>{if(!c||!/^[A-Z]{2}$/.test(c))return "";let n="";try{n=dnR?dnR.of(c):""}catch(_){}return n&&n!=c?`${c} · ${n}`:c};
 const drow=r=>`<article class="sc-row sd-row cc" style="${catSt(r.cat)}"><div class="sd-ic sd-tile" aria-hidden="true" title="${esc(r.cat)}">${bnIco(catOf(r.cat)[0])}</div><div><div class="nm"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer nofollow">${esc(r.name)}</a></div>
  <div><span class="sc-chip dir">Directory reference</span><span class="sc-chip cat cc"><i class="cdot" aria-hidden="true"></i>${esc(r.cat)}</span><span class="sc-chip">${esc(r.kind)}</span>${r.cc?`<span class="sc-chip">${esc(flag(r.cc))}</span>`:""}</div>
  ${r.detail?`<div class="sc-sm mu">${esc(r.detail)}</div>`:""}${gradeHTML(r.sid,r.grade)}</div><div class="st">from <b class="sd-reg">${esc(r.reg)}</b>${r.checked?`<br>link checked ${esc(r.checked)}`:""}</div></article>`;
 function pager(j){const P=$("sd_pager"),p=j.page,n=j.pages;if(n<=1){P.innerHTML="";return}
  const nums=[...new Set([1,p-2,p-1,p,p+1,p+2,n].filter(x=>x>=1&&x<=n))].sort((a,b)=>a-b);let h=`<button type="button" data-p="${p-1}" ${p<=1?"disabled":""}>‹ Prev</button>`,last=0;
  nums.forEach(x=>{if(x-last>1)h+=`<span class="mu">…</span>`;h+=`<button type="button" data-p="${x}" ${x==p?'aria-current="page" class="on"':""}>${x.toLocaleString()}</button>`;last=x});
  P.innerHTML=h+`<button type="button" data-p="${p+1}" ${p>=n?"disabled":""}>Next ›</button>`}
 const prm=()=>{const p=new URLSearchParams({q:$("sd_q").value,cat:$("sd_cat").value,cc:ccSel.value,reg:$("sd_reg").value,page:st.page,per:50,voter:SDvoter});if($("sd_rated").checked)p.set("rated","1");return p};
 async function dload(scroll){$("sd_count").textContent="Loading…";if(ctl)ctl.abort();ctl=new AbortController();
  try{const r=await fetch(API+"directory?"+prm(),{cache:"no-store",signal:ctl.signal}),j=await r.json();
   if(!r.ok){$("sd_count").textContent=j.error||"Couldn't load the directory.";return}
   DL.innerHTML=j.items.map(drow).join("");const a=(j.page-1)*j.per;
   $("sd_count").textContent=j.total?`Showing ${(a+1).toLocaleString()}–${(a+j.items.length).toLocaleString()} of ${j.total.toLocaleString()} directory sources`:"No directory sources match these filters.";
   pager(j);if(scroll)$("directory").scrollIntoView({behavior:"smooth",block:"start"})}
  catch(e){if(e.name!="AbortError")$("sd_count").textContent="Couldn't load the directory. Try again in a moment."}}
 document.querySelectorAll(".sd-cats button[data-cat]").forEach(b=>b.addEventListener("click",()=>{$("sd_cat").value=b.dataset.cat;st.page=1;dload(true)}));
 ["sd_cat","sd_reg","sd_rated"].forEach(i=>$(i).addEventListener("change",()=>{st.page=1;dload()}));ccSel.addEventListener("change",()=>{st.page=1;dload()});
 $("sd_q").addEventListener("input",()=>{clearTimeout(tm);tm=setTimeout(()=>{st.page=1;dload()},300)});
 $("sd_pager").addEventListener("click",e=>{const b=e.target.closest("button[data-p]");if(!b||b.disabled)return;st.page=+b.dataset.p;dload(true)});
 dload();
}
const L=$("sc_list");
if(L){
 const st={page:1};let timer=0;
 const params=()=>{const p=new URLSearchParams({q:$("sc_q").value,type:$("sc_type").value,cat:$("sc_cat").value,band:$("sc_band").value,origin:$("sc_origin").value,sort:$("sc_sort").value,page:st.page,per:40,voter:window.SDvoter||""});if($("sc_prof").checked)p.set("profiled","1");return p};
 async function load(append){
  $("sc_count").textContent="Loading…";
  try{const r=await fetch(API+"catalog?"+params(),{cache:"no-store"}),j=await r.json();
   const ts=$("sc_type");if(ts.options.length<2)j.types.forEach(t=>ts.add(new Option(`${t.type} (${t.n})`,t.type)));
   L.insertAdjacentHTML(append?"beforeend":"afterbegin",append?j.items.map(row).join(""):"");if(!append)L.innerHTML=j.items.map(row).join("");
   const shown=Math.min(j.total,j.page*j.per);$("sc_count").textContent=j.total?`Showing ${shown.toLocaleString()} of ${j.total.toLocaleString()} sources`:"No sources match these filters.";
   $("sc_more").hidden=shown>=j.total}
  catch(e){$("sc_count").textContent="Couldn't load the catalog. Try again in a moment."}}
 L.addEventListener("click",e=>{const b=e.target.closest(".sc-r[aria-controls]");if(!b)return;const p=$(b.getAttribute("aria-controls"));p.hidden=!p.hidden;b.setAttribute("aria-expanded",String(!p.hidden))});
 ["sc_type","sc_cat","sc_band","sc_origin","sc_sort","sc_prof"].forEach(i=>$(i).addEventListener("change",()=>{st.page=1;load(false)}));
 $("sc_q").addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(()=>{st.page=1;load(false)},250)});
 $("sc_more").addEventListener("click",()=>{st.page++;load(true)});
 load(false);
 const rg=$("sc_range"),fr=$("sc_foot_range");if(rg&&fr&&rg.dataset.first)fr.textContent=`Data range: ${fmtET(rg.dataset.first)} – ${fmtET(rg.dataset.last)}`;
}
const F=$("sc_form");
if(F){F.addEventListener("submit",async e=>{e.preventDefault();const m=F.querySelector(".sc-msg"),b=F.querySelector("button[type=submit]");
 const d=Object.fromEntries(new FormData(F).entries());
 if(!d.name||!d.url||!d.type||!d.category||!d.why){m.className="sc-msg err";m.textContent="Fill in the name, link, type, category and why it's useful.";return}
 b.disabled=true;m.className="sc-msg";m.textContent="Sending…";
 try{const r=await fetch(API+"submit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)}),j=await r.json();
  m.className="sc-msg "+(j.ok?"ok":"err");m.textContent=j.message||("Error "+r.status);if(j.ok&&!j.duplicate)F.reset()}
 catch(_){m.className="sc-msg err";m.textContent="Couldn't send. Check your connection and try again."}
 finally{b.disabled=false}})}
// dashboard: "📚 Sources" tab in the Reference group (after "How we score"), deep link #sources, card fetched from the server
const M=document.getElementById("tab-sources");
if(M){const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="sources"]');
 if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="sources";tb.textContent="📚 Sources";tb.title="Every source we use, with a 0–10 confidence rating";nav.appendChild(tb)}
 const place=()=>{const a=nav&&(nav.querySelector("#tab_howscore")||nav.querySelector('button[data-tab="med"]'));if(a&&tb&&a.nextElementSibling!==tb)a.insertAdjacentElement("afterend",tb)};
 place();setTimeout(place,500);setTimeout(place,1500);
 try{if(typeof TABHASH=="object"){TABHASH.sources="sources";HASHTAB.sources="sources"}}catch(_){}
 if(location.hash=="#sources")setTimeout(()=>tb&&!tb.classList.contains("on")&&tb.click(),350);
 const box=document.getElementById("sc_app");
 const load=async()=>{if(box.dataset.loaded)return;box.dataset.loaded=1;
  try{const r=await fetch(API+"card",{cache:"no-store"});box.innerHTML=await r.text()}catch(e){box.dataset.loaded="";box.innerHTML='<p class="meta">Couldn\'t load. <a href="sources">Open the Sources page</a>.</p>'}};
 tb&&tb.addEventListener("click",load);if(location.hash=="#sources")load()}
})();
