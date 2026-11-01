// ---- 👥 Key Figures tab (served by figures.py, t353). Neutral reference cards: role, country, why in the news, related headlines.
// No person is labelled a threat; no ranks, scores or aircraft tracking for people. #elon (old tab) redirects here. Times in ET.
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const U=u=>/^https?:\/\//i.test(u||"")?E(u):"#";const TZ="America/New_York";
const etT=t=>{if(!t)return"";const d=new Date(t);return isNaN(d)?"":d.toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"})};
const fromElon=()=>{if(location.hash=="#elon"||location.hash.startsWith("#elon/")){history.replaceState(null,"","#figures");return true}return false};
const redirected=fromElon();
const nav=document.querySelector(".tabs");if(!nav)return;
let tb=nav.querySelector('button[data-tab="figures"]');if(!tb){tb=document.createElement("button");tb.type="button";tb.dataset.tab="figures";tb.textContent="👥 Key Figures";nav.appendChild(tb)}
try{if(typeof TABHASH=="object"){TABHASH.figures="figures";HASHTAB.figures="figures";HASHTAB.elon="figures"}}catch(_){}
let M=document.getElementById("tab-figures");
if(!M){M=document.createElement("main");M.id="tab-figures";M.dataset.addon="figures";M.style.cssText="display:none;grid-template-columns:minmax(0,1fr)";
 M.innerHTML=`<section class="pn kf" id="kf_top"><h2 class=kf-h>People in the news</h2><div class=kf-tools><label class=kf-q><span class=kf-sr>Filter people</span><input id=kf_q type=search placeholder="Filter by name, role or country" autocomplete=off></label></div><div id="kf_app"><div class="meta">Loading…</div></div></section>`;
 const last=[...document.querySelectorAll("main[data-addon]")].pop();(last||document.body).insertAdjacentElement(last?"afterend":"beforeend",M)}
if(location.hash=="#figures"||redirected)setTimeout(()=>{if(!tb.classList.contains("on"))tb.click()},350);
addEventListener("hashchange",()=>{if(fromElon()&&!tb.classList.contains("on"))tb.click()});
const app=M.querySelector("#kf_app");const S={d:null,t:0,busy:false,q:""};
function hl(x){const t=etT(x.time);
 if(x.via=="scanner")return `<li><a href="/wire/${E(x.cid)}" data-goto="${E(x.cid)}">${E(x.title)}</a><div class=kf-m>${E(x.list)}${t?" · "+E(t):""}${x.url?` · <a href="${U(x.url)}" target=_blank rel=noopener>${E(x.source||"source")}</a>`:""}</div></li>`;
 return `<li><a href="${U(x.url)}" target=_blank rel=noopener>${E(x.title)}</a><div class=kf-m>${E(x.source||"")}${t?" · "+E(t):""} · via Google News</div></li>`}
// t370: real photo (self-hosted, freely licensed; credits listed under the grid). Initials tile stays underneath as the fallback if the image fails.
function av(p){const ph=p.photo;const cr=ph?`Photo: ${ph.author||"Wikimedia Commons"}${ph.license?" · "+ph.license:""}`:"";
 return `<div class="kf-av${ph?"":" kf-noimg"}"><span class=kf-ini aria-hidden=true>${E(p.initials)}</span>${ph?`<img src="${E(ph.src)}" alt="Photo of ${E(p.name)}" title="${E(cr)}" width=72 height=72 loading=lazy decoding=async onerror="this.parentNode.classList.add('kf-noimg');this.remove()">`:""}</div>`}
function credits(ps){const c=ps.filter(p=>p.photo);if(!c.length)return"";
 return `<details class=kf-cred><summary>Photo credits (${c.length})</summary><ul>${c.map(p=>{const f=p.photo;
  return `<li><b>${E(p.name)}</b>: ${f.source?`<a href="${U(f.source)}" target=_blank rel=noopener>${E(f.author||"Wikimedia Commons")}</a>`:E(f.author||"")}${f.license?` · ${f.license_url?`<a href="${U(f.license_url)}" target=_blank rel="noopener license">${E(f.license)}</a>`:E(f.license)}`:""}${f.auto?" · via Wikidata":""}</li>`}).join("")}</ul>
 <p>Photos are cropped and resized from the files linked above (Wikimedia Commons, many of them official government portraits). Public-domain images need no attribution; it is given anyway.</p></details>`}
function card(p){const n=p.alerts;
 return `<article class=kf-card data-k="${E((p.name+" "+p.role+" "+p.country).toLowerCase())}"><div class=kf-hd>${av(p)}<div class=kf-id><h3>${E(p.name)}</h3><div class=kf-role>${E(p.role)}</div><div class=kf-ctry>${E(p.country)}</div></div></div>
 <p class=kf-why>${E(p.why)}</p><div class=kf-cnt>${n?`${n} related alert${n==1?"":"s"} on The Wire in the last ${S.d.days} days`:`No related alerts on The Wire in the last ${S.d.days} days`}</div>
 <ul class=kf-ul>${(p.headlines||[]).map(hl).join("")||"<li class=kf-m>No recent headlines found.</li>"}</ul>
 <div class=kf-lk>${(p.links||[]).map(l=>`<a href="${U(l[1])}" target=_blank rel=noopener>${E(l[0])} ↗</a>`).join("")}</div></article>`}
function render(){const d=S.d;if(!d)return;const q=S.q.trim().toLowerCase();
 const ps=d.people.filter(p=>!q||(p.name+" "+p.role+" "+p.country).toLowerCase().includes(q));
 app.innerHTML=`<div class=kf-grid>${ps.map(card).join("")||`<div class=meta>No one matches “${E(S.q)}”.</div>`}</div><p class=kf-note>${E(d.note)} Updated ${E(etT(d.updated))}.</p>${credits(d.people)}`;
 app.querySelectorAll("[data-goto]").forEach(a=>a.onclick=e=>{const w=document.querySelector('.tabs button[data-tab="threat"]');if(!w)return;
  const find=()=>document.querySelector(`#tab-threat [data-cid="${CSS.escape(a.dataset.goto)}"]`)||document.querySelector(`main:not(#tab-figures) [data-cid="${CSS.escape(a.dataset.goto)}"]`);
  e.preventDefault();w.click();setTimeout(()=>{const el=find();if(el&&el.offsetParent!==null){el.scrollIntoView({block:"center"});el.style.outline="2px solid var(--bn-brand,#ff4d4f)";setTimeout(()=>el.style.outline="",2500)}else location.href=a.getAttribute("href")},350)})}
async function load(){if(S.busy)return;S.busy=true;
 try{const r=await fetch("api/figures",{cache:"no-store"});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);S.d=j;S.t=Date.now();render()}
 catch(e){if(!S.d)app.innerHTML=`<div class=meta>Data unavailable right now. Please try again in a minute.</div>`}finally{S.busy=false}}
M.querySelector("#kf_q").addEventListener("input",e=>{S.q=e.target.value;render()});
nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&b.dataset.tab=="figures")setTimeout(()=>{if(!S.d||Date.now()-S.t>300000)load()},0)});
setInterval(()=>{if(M.style.display!="none"&&!document.hidden)load()},600000);
})();
