// ---- blackout.network Sources catalog: /sources list (search, filter, sort, paging, rating reasons), submit form, dashboard Reference-tab card ----
(function(){
const API="/api/sources/",$=id=>document.getElementById(id),esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmtET(iso){if(!iso)return "—";const d=new Date(iso);if(isNaN(d))return "—";return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)}
const BL={blue:"9–10 official / fully trusted",green:"7–8 reliable",amber:"4–6 mixed: confirm first",red:"0–3 unverified / low trust",na:"collector, not a source"};
function reasonText(r){return (r.reason||[]).map(s=>`${s[0]}: ${s[1]} (${s[2]})`).join("\n")}
function row(r){
 const rv=r.rating==null?"n/a":r.rating,cats=Object.entries(r.categories||{}).slice(0,4).map(([c,n])=>`<span class="sc-chip cat">${esc(c)}${n?` · ${n}`:""}</span>`).join("");
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
 const flag=c=>c&&/^[A-Z]{2}$/.test(c)?String.fromCodePoint(...[...c].map(x=>127397+x.charCodeAt(0)))+" "+c:"";
 const ICO={"Research & academia":"🎓","Weather, radar & ocean":"📡","Seismic, volcanic & geophysical":"🌋","Satellites & space":"🛰️","Hydrology & flood gauges":"🌊","Health & medical institutions":"🩺","Government & public agencies":"🏛️","News & media":"📰","Security & cyber":"🛡️","Police & law enforcement":"🚓","Emergency management":"🚨","Scanner & public-safety audio":"📻","Government data feeds":"📊","Internet outage sensors":"🌐","Local government":"🏙️"};
 const drow=r=>`<article class="sc-row sd-row"><div class="sd-ic" aria-hidden="true">${ICO[r.cat]||"•"}</div><div><div class="nm"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer nofollow">${esc(r.name)}</a></div>
  <div><span class="sc-chip dir">Directory reference</span><span class="sc-chip cat">${esc(r.cat)}</span><span class="sc-chip">${esc(r.kind)}</span>${r.cc?`<span class="sc-chip">${esc(flag(r.cc))}</span>`:""}</div>
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
