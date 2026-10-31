// ---- blackout.network Sources catalog: /sources list (search, filter, sort, paging, rating reasons), submit form, dashboard Reference-tab card ----
(function(){
const API="/api/sources/",$=id=>document.getElementById(id),esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmtET(iso){if(!iso)return "—";const d=new Date(iso);if(isNaN(d))return "—";return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(d)}
const BL={blue:"9–10 official / fully trusted",green:"7–8 reliable",amber:"4–6 mixed: confirm first",red:"0–3 unverified / low trust",na:"collector, not a source"};
function reasonText(r){return (r.reason||[]).map(s=>`${s[0]}: ${s[1]} (${s[2]})`).join("\n")}
function row(r){
 const rv=r.rating==null?"n/a":r.rating,cats=Object.entries(r.categories||{}).slice(0,4).map(([c,n])=>`<span class="sc-chip cat">${esc(c)}${n?` · ${n}`:""}</span>`).join("");
 const pol=r.origin=="political"?`<span class="sc-chip pol">political watch · ${esc(r.party||"")}</span>`:"";
 const ov=r.overridden?`<span class="sc-chip ov">admin override</span>`:"";
 const prof=r.profile?`<div class="pf">${esc(r.profile)}</div>`:`<div class="pf pend">Profile pending</div>`;
 const id="w"+Math.random().toString(36).slice(2,9);
 const steps=(r.reason||[]).map(s=>`<li><b>${esc(s[0])}</b> ${esc(s[1])}: ${esc(s[2])}</li>`).join("");
 const link=r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener noreferrer nofollow">${esc(r.name)}</a>`:esc(r.name);
 return `<article class="sc-row k-${r.band}"><button type="button" class="sc-r b-${r.band}" aria-expanded="false" aria-controls="${id}" title="${esc("Confidence "+rv+"/10, "+BL[r.band]+"\n"+reasonText(r))}">${rv}</button>
 <div><div class="nm">${link}</div><div><span class="sc-chip">${esc(r.type)}</span>${pol}${ov}${cats}</div>${prof}${r.role?`<div class="sc-sm mu">${esc(r.role)}</div>`:""}</div>
 <div class="st"><b>${(r.n_items||0).toLocaleString()}</b> item${r.n_items==1?"":"s"}<br>${r.first_seen?`first ${esc(fmtET(r.first_seen))}<br>last ${esc(fmtET(r.last_seen))}`:"no stored items"}${r.status?`<br>${esc(r.status)}`:""}</div>
 <div class="sc-why" id="${id}" hidden><b>Why ${rv}/10</b> (${esc(BL[r.band])})<ol>${steps}</ol></div></article>`}
const L=$("sc_list");
if(L){
 const st={page:1};let timer=0;
 const params=()=>{const p=new URLSearchParams({q:$("sc_q").value,type:$("sc_type").value,cat:$("sc_cat").value,band:$("sc_band").value,origin:$("sc_origin").value,sort:$("sc_sort").value,page:st.page,per:40});if($("sc_prof").checked)p.set("profiled","1");return p};
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
