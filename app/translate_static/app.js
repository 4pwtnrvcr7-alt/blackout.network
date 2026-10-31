/* blackout.network display-only translation (offline Argos engine via /api/translate).
   English renders first; text nodes + title/placeholder/aria-label attributes are swapped in place after the batch returns.
   Originals are kept in memory (never written anywhere), so "Show original" and per-card "EN" flip back instantly. */
(()=>{
if(window.BNTR)return;
const SRC=(document.currentScript&&document.currentScript.src)||location.origin+"/api/translate/app.js";
const API=SRC.replace(/app\.js(\?.*)?$/,"").replace(/\/$/,"");
const RTL=new Set(["ar","fa","he","ur"]);
const HTMLLANG={zh:"zh-Hans",zt:"zh-Hant",pb:"pt-BR",nb:"nb"};
const NOTE_EN="Machine-translated. Original English is authoritative.";
const UI_EN=[NOTE_EN,"Show original","Show translation"];
const SKIP_TAGS=new Set(["SCRIPT","STYLE","NOSCRIPT","CODE","PRE","KBD","SAMP","TEXTAREA","INPUT","svg","SVG","CANVAS","IFRAME","TEMPLATE"]);
const SKIP_SEL='[translate="no"],.notranslate,#bntr_bar,#bntr_note,.bntr-orig,.leaflet-control-attribution,.leaflet-tile-pane';
const CARD_SEL='.card,.tl-card,.mp-card,.st-card,.clip,.arc,.ns-row,.st-seg,[data-cid]';
const PROTECT=/(https?:\/\/\S+|\bblackout\.network\b|\s·\s|\s\|\s)/i;
const PROTECT_G=new RegExp(PROTECT.source,"gi");
const BRAND=/^(BLACKOUT\.?|NETWORK|BLACKOUT\.NETWORK|blackout\.network)$/i;
const ATTRS=["title","placeholder","aria-label"];
const getC=k=>(document.cookie.match("(?:^|; )"+k+"=([^;]*)")||[])[1];
let lang="en";try{lang=localStorage.getItem("bn_lang")||getC("bn_lang")||"en"}catch(e){lang=getC("bn_lang")||"en"}
let showOrig=false,LANGS=null,busy=0,timer=0,pending=new Set();
const recs=new WeakMap();     // text node -> {o: original English, t: text we wrote, l: lang}
const arecs=new WeakMap();    // element -> {attr: {o, t, l}}
const cache=new Map();        // lang -> Map(english segment -> translation)
const stats={reqs:0,strings:0,ms:0,last:null};
const inflight=new Map(),failed=new Map();let ctl=null;   // dedupe in-flight strings; failed strings retry after 30 s
const IF=l=>{if(!inflight.has(l))inflight.set(l,new Set());return inflight.get(l)};
const C=l=>{if(!cache.has(l))cache.set(l,new Map());return cache.get(l)};
const translatable=s=>/[^\W\d_]{2,}/u.test(s)&&!BRAND.test(s.trim());
function segs(s){return s.split(PROTECT_G).filter(x=>x!==undefined)}
function vis(el){if(!el)return false;if(el.tagName=="OPTION"){el=el.closest("select");if(!el)return false}
 if(el.checkVisibility)return el.checkVisibility();return !!(el.offsetParent||el.getClientRects().length)}
function skipEl(el){if(!el||SKIP_TAGS.has(el.tagName))return true;if(el.closest(SKIP_SEL))return true;
 if(el.isContentEditable)return true;
 if(el.tagName=="OPTION"&&!el.hasAttribute("value"))return true;   // option text doubles as its value: never change it
 const a=el.closest("a[href]");if(a&&/^https?:/i.test(a.getAttribute("href")||"")&&(a.textContent||"").trim().length<48)return true;  // source names / outbound links
 return false}
function cardOrig(el){const c=el.closest&&el.closest(".bntr-show-orig");return !!c}
function persist(l){try{localStorage.setItem("bn_lang",l)}catch(e){}document.cookie="bn_lang="+l+";path=/;max-age=31536000;SameSite=Lax"}
function render(o,l){const m=C(l);return segs(o).map(p=>{if(PROTECT.test(p)&&p.match(PROTECT)[0]===p)return p;const t=p.trim();if(!t||!translatable(t))return p;
 const tr=m.get(t);if(tr==null)return null;const lead=p.match(/^\s*/)[0],tail=p.match(/\s*$/)[0];return lead+tr+tail}).reduce((a,b)=>a==null||b==null?null:a+b,"")}
function need(o,l,set){const m=C(l),f=IF(l),now=Date.now();segs(o).forEach(p=>{if(PROTECT.test(p)&&p.match(PROTECT)[0]===p)return;const t=p.trim();if(t&&translatable(t)&&!m.has(t)&&!f.has(t)&&!(now-(failed.get(l+"\u0001"+t)||0)<30000)&&t.length<=2000)set.add(t)})}
function eachText(root,fn){const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const p=n.parentElement;if(!p||skipEl(p))return NodeFilter.FILTER_REJECT;return n.data.trim()?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});let n;while(n=w.nextNode())fn(n)}
function origOf(n){const r=recs.get(n);if(r&&n.data!==r.t)r.o=n.data,r.t=null,r.l=null;return r?r.o:n.data}
function hot(el){const b=el.getBoundingClientRect();return b.bottom>-innerHeight*.5&&b.top<innerHeight*1.5}
function scan(){if(!document.body)return;const target=showOrig?"en":lang,want=new Set(),wantHot=new Set(),work=[];
 eachText(document.body,n=>{let r=recs.get(n);if(!r){if(target=="en")return;r={o:n.data,t:null,l:null};recs.set(n,r)}else if(n.data!==r.t&&n.data!==r.o){r.o=n.data;r.t=null;r.l=null}
  const tl=cardOrig(n.parentElement)?"en":target;
  if(tl=="en"){if(r.l&&r.l!="en"){r.t=r.o;r.l="en";n.data=r.o}return}
  if(r.l==tl&&n.data===r.t)return;
  if(!translatable(r.o))return;
  if(!vis(n.parentElement))return;
  need(r.o,tl,hot(n.parentElement)?wantHot:want);work.push([n,r,tl])});
 document.body.querySelectorAll("[title],[placeholder],[aria-label]").forEach(el=>{if(el.closest(SKIP_SEL)&&!el.closest(".bntr-orig"))return;if(el.closest(".bntr-orig"))return;
  let ar=arecs.get(el);ATTRS.forEach(a=>{const v=el.getAttribute(a);if(v==null||!v.trim())return;if(!ar){if(target=="en")return;ar={};arecs.set(el,ar)}
   let r=ar[a];if(!r||(v!==r.t&&v!==r.o)){r=ar[a]={o:v,t:null,l:null}}
   const tl=cardOrig(el)?"en":target;if(tl=="en"){if(r.l&&r.l!="en"){r.l="en";r.t=r.o;el.setAttribute(a,r.o)}return}
   if(r.l==tl&&v===r.t)return;if(!translatable(r.o)||!vis(el))return;need(r.o,tl,want);work.push([el,r,tl,a])})});
 apply(work);
 const list=[...wantHot,...[...want].filter(t=>!wantHot.has(t))];
 if(list.length&&target!="en")fetchAll(list,target,()=>apply(work)).then(()=>{apply(work);marks()});else marks()}
function apply(work){work.forEach(([n,r,tl,a])=>{let s=render(r.o,tl);if(s==null){if(!r.l||r.l==tl)return;s=r.o;r.t=s;r.l=null;if(a)n.setAttribute(a,s);else n.data=s;return}r.t=s;r.l=tl;if(a){if(n.getAttribute(a)!==s)n.setAttribute(a,s)}else if(n.data!==s)n.data=s})}
async function fetchAll(list,l,onBatch){const m=C(l),f=IF(l),batches=[];let b=[],sz=0;list=list.filter(t=>!f.has(t));list.forEach(t=>f.add(t));if(!ctl)ctl=new AbortController();const sig=ctl.signal;
 list.forEach(t=>{const n=JSON.stringify(t).length*3+2;if(b.length&&(sz+n>8600||b.length>=180)){batches.push(b);b=[];sz=0}b.push(t);sz+=n});if(b.length)batches.push(b);
 busy++;status();const t0=performance.now();
 const run=async bt=>{try{if(sig.aborted)return;const r=await fetch(API,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({to:l,texts:bt}),signal:sig});
   if(!r.ok){stats.last="error "+r.status;bt.forEach(t=>failed.set(l+"\u0001"+t,Date.now()));return}const j=await r.json();bt.forEach((t,i)=>m.set(t,j.out[i]));stats.reqs++;stats.strings+=bt.length;stats.last=null;if(onBatch&&l==lang)onBatch()}
  catch(e){if(!sig.aborted){stats.last="offline";bt.forEach(t=>failed.set(l+"\u0001"+t,Date.now()))}}finally{bt.forEach(t=>f.delete(t))}};
 // visible-first: batches already ordered by DOM order; run 2 at a time
 const q=batches.slice();await Promise.all([0,1].map(async()=>{while(q.length)await run(q.shift())}));
 stats.ms=Math.round(performance.now()-t0);busy=Math.max(0,busy-1);status()}
// per-card "EN" disclosure so each alert's English source text is one click away
function marks(){const on=lang!="en"&&!showOrig;document.querySelectorAll(CARD_SEL).forEach(c=>{if(c.closest("#bntr_bar"))return;let b=c.querySelector(":scope > .bntr-orig");
  if(!on){if(b)b.remove();c.classList.remove("bntr-show-orig");return}
  if(b||!vis(c))return;let has=false;eachText(c,n=>{const r=recs.get(n);if(r&&r.l&&r.l!="en"&&r.t!==r.o)has=true});if(!has)return;
  b=document.createElement("button");b.type="button";b.className="bntr-orig";b.setAttribute("translate","no");b.textContent="EN";b.title="Show this item's original English text";
  b.onclick=e=>{e.preventDefault();e.stopPropagation();c.classList.toggle("bntr-show-orig");b.classList.toggle("on",c.classList.contains("bntr-show-orig"));b.textContent=c.classList.contains("bntr-show-orig")?"⇄ "+(LANGS&&(LANGS.find(x=>x.code==lang)||{}).native||lang):"EN";scan()};
  c.appendChild(b)})}
function schedule(ms){clearTimeout(timer);timer=setTimeout(scan,ms==null?200:ms)}
// ---- UI: picker in header + footer, Show original toggle, notice bar ----
function picker(id){const s=document.createElement("select");s.id=id;s.className="bntr-sel";s.setAttribute("translate","no");s.setAttribute("aria-label","Language / Idioma / Langue / اللغة / 语言");
 s.innerHTML=(LANGS||[{code:"en",native:"English",english:"English"}]).map(x=>`<option value="${x.code}"${x.code==lang?" selected":""}>${x.native}${x.code!="en"&&x.native!=x.english?" · "+x.english:""}</option>`).join("");
 s.onchange=()=>setLang(s.value);return s}
function ui(){if(document.getElementById("bntr_bar"))return;
 const bar=document.createElement("span");bar.id="bntr_bar";bar.setAttribute("translate","no");
 bar.innerHTML='<span class="bntr-globe" aria-hidden="true">🌐</span>';bar.appendChild(picker("bntr_lang"));
 const t=document.createElement("button");t.type="button";t.id="bntr_toggle";t.className="bntr-tog";t.onclick=()=>{showOrig=!showOrig;try{sessionStorage.setItem("bn_orig",showOrig?"1":"")}catch(e){}refresh();scan()};bar.appendChild(t);
 const st=document.createElement("span");st.id="bntr_status";st.className="bntr-st";bar.appendChild(st);
 const host=document.querySelector("header .ctl")||document.querySelector("header")||document.querySelector("nav");
 if(host)host.appendChild(bar);else{bar.classList.add("bntr-float");document.body.appendChild(bar)}
 const note=document.createElement("div");note.id="bntr_note";note.setAttribute("role","note");
 const hd=document.querySelector("header");if(hd)hd.insertAdjacentElement("afterend",note);else document.body.prepend(note);
 const f=document.getElementById("site_foot")||document.querySelector("footer");if(f){const w=document.createElement("span");w.className="bntr-foot";w.setAttribute("translate","no");w.append(" · 🌐 ",picker("bntr_lang_f"));f.appendChild(w)}
 refresh()}
function refresh(){const t=document.getElementById("bntr_toggle"),n=document.getElementById("bntr_note");if(!t)return;
 const en=lang=="en";t.style.display=en?"none":"";const L=k=>C(lang).get(k)||k;t.textContent="⇄ "+(showOrig?L("Show translation"):L("Show original"));t.title=showOrig?"Show translation: show the machine translation again":"Show original: show the original English text everywhere";
 t.classList.toggle("on",showOrig);document.querySelectorAll(".bntr-sel").forEach(s=>{if(s.value!==lang)s.value=lang});
 const R=RTL.has(lang)&&!showOrig;document.documentElement.dir=R?"rtl":"ltr";document.documentElement.lang=showOrig||en?"en":(HTMLLANG[lang]||lang);
 if(n){n.style.display=en?"none":"block";
  const loc=C(lang).get(NOTE_EN);n.innerHTML=en?"":(showOrig?'<b>Showing original English.</b> ':'')+(loc&&!showOrig?`<span>${esc(loc)}</span> · `:"")+`<span translate="no" lang="en" dir="ltr">${NOTE_EN}</span>`}
 status()}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function status(){const s=document.getElementById("bntr_status");if(!s)return;s.textContent=busy?"translating…":(stats.last&&lang!="en"?"⚠ "+stats.last:"");s.title=stats.reqs?`${stats.strings} strings in ${stats.reqs} request(s), last pass ${stats.ms} ms`:""}
async function setLang(l){if(LANGS&&!LANGS.some(x=>x.code==l))l="en";if(l!==lang&&ctl){ctl.abort();ctl=null;busy=0}lang=l;persist(l);showOrig=false;try{sessionStorage.removeItem("bn_orig")}catch(e){}
 if(l!="en"&&!C(l).has(NOTE_EN))fetchAll(UI_EN,l).then(refresh);refresh();scan()}
async function init(){try{showOrig=sessionStorage.getItem("bn_orig")=="1"}catch(e){}
 try{const j=await (await fetch(API+"/langs")).json();LANGS=j.langs}catch(e){LANGS=null}
 if(LANGS&&!LANGS.some(x=>x.code==lang))lang="en";
 ui();if(lang!="en"){fetchAll(UI_EN,lang).then(refresh);setTimeout(scan,50)}
 new MutationObserver(ms=>{if(lang=="en"&&!showOrig)return;for(const m of ms){if(m.target.closest&&m.target.closest("#bntr_bar,#bntr_note"))continue;
   if(m.type=="attributes"&&ATTRS.includes(m.attributeName)){const ar=arecs.get(m.target),r=ar&&ar[m.attributeName];if(r&&m.target.getAttribute(m.attributeName)===r.t)continue}
   if(m.type=="characterData"){const r=recs.get(m.target);if(r&&m.target.data===r.t)continue}
   return schedule(m.type=="attributes"&&!ATTRS.includes(m.attributeName)?60:250)}})
  .observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:["style","hidden","open","class","title","placeholder","aria-label"]});
 addEventListener("hashchange",()=>schedule(80));addEventListener("click",()=>schedule(120),true);addEventListener("scroll",()=>schedule(300),{passive:true})}
// English text for anything that reads the DOM (e.g. vote titles): BNTR.orig(el)
function origText(el){if(!el)return "";let s="";const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){if(n.parentElement&&n.parentElement.closest(".bntr-orig"))continue;const r=recs.get(n);s+=r&&n.data===r.t?r.o:n.data}return s}
window.BNTR={get busy(){let n=busy;inflight.forEach(x=>n+=x.size);return n},setLang,get lang(){return lang},get showOriginal(){return showOrig},orig:origText,stats,rescan:()=>schedule(0)};
if(document.readyState=="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
