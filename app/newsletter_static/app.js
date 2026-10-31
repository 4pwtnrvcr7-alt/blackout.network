// ---- blackout.network newsletter: signup form (dashboard Community tab card + /newsletter page) and the manage-preferences form ----
(()=>{"use strict";
if(window.BNNL)return;window.BNNL=1;
const SRC=(document.currentScript&&document.currentScript.src)||location.origin+"/api/newsletter/app.js";
const API=SRC.replace(/app\.js(\?.*)?$/,"");                       // ".../api/newsletter/"
const RE=/^[^\s@"<>(),;:\\[\]]{1,64}@[^\s@"<>(),;:\\[\]]+\.[A-Za-z]{2,63}$/;
const post=async(path,body)=>{const r=await fetch(API+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),credentials:"same-origin"});
 let j={};try{j=await r.json()}catch(_){}return {ok:r.ok,status:r.status,j}};
const say=(el,txt,ok)=>{if(!el)return;el.textContent=txt;el.className="nl-msg "+(ok?"ok":"err")};

function enhance(f){
 if(f.dataset.nlReady)return;f.dataset.nlReady=1;
 const em=f.querySelector('input[name=email]'),msg=f.querySelector(".nl-msg"),btn=f.querySelector("button[type=submit]");
 em&&em.addEventListener("input",()=>{em.removeAttribute("aria-invalid");if(msg&&msg.classList.contains("err"))msg.textContent=""});
 f.addEventListener("submit",async e=>{e.preventDefault();
  const v=(em.value||"").trim();
  if(!v){say(msg,"Enter your email address.");em.setAttribute("aria-invalid","true");em.focus();return}
  if(v.length>254||!RE.test(v)){say(msg,"That doesn't look like a valid email address.");em.setAttribute("aria-invalid","true");em.focus();return}
  const fd=new FormData(f),cats=[...f.querySelectorAll('input[name=interests]')],picked=cats.filter(c=>c.checked).map(c=>c.value);
  const body={email:v,frequency:fd.get("frequency")||"twice",interests:(!picked.length||picked.length==cats.length)?["all"]:picked,
   csrf:fd.get("csrf"),website:fd.get("website")||"",source:fd.get("source")||"form"};
  btn.disabled=true;const old=btn.textContent;btn.textContent="Subscribing…";say(msg,"",true);
  try{let r=await post("subscribe",body);
   if(r.status==403){const m=await (await fetch(API+"meta",{cache:"no-store"})).json();body.csrf=m.csrf;f.querySelector('input[name=csrf]').value=m.csrf;r=await post("subscribe",body)}
   say(msg,(r.j&&r.j.message)||("Something went wrong ("+r.status+"). Please try again."),r.ok);
   if(r.ok){em.value="";}else if(r.j&&r.j.field=="email"){em.setAttribute("aria-invalid","true");em.focus()}
  }catch(err){say(msg,"Network error. Please try again.")}
  finally{btn.disabled=false;btn.textContent=old}});
}
function enhanceManage(f){
 if(!f||f.dataset.nlReady)return;f.dataset.nlReady=1;const msg=f.querySelector(".nl-msg");
 f.addEventListener("submit",async e=>{e.preventDefault();const fd=new FormData(f),cats=[...f.querySelectorAll('input[name=interests]')],picked=cats.filter(c=>c.checked).map(c=>c.value);
  const r=await post("manage",{token:fd.get("token"),frequency:fd.get("frequency"),interests:(!picked.length||picked.length==cats.length)?["all"]:picked});
  say(msg,(r.j&&r.j.message)||("Error "+r.status),r.ok)});
}

// dashboard: tab button in the Community group + deep link #newsletter, form card fetched from the server
const M=document.getElementById("tab-newsletter");
if(M){
 const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="newsletter"]');
 if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="newsletter";tb.textContent="✉ Newsletter";tb.title="Get the morning/evening brief by email";nav.appendChild(tb)}
 const place=()=>{const a=nav&&nav.querySelector('button[data-tab="ranked"]');if(a&&tb&&a.nextElementSibling!==tb)a.insertAdjacentElement("afterend",tb)};
 place();setTimeout(place,500);setTimeout(place,1500);
 try{if(typeof TABHASH=="object"){TABHASH.newsletter="newsletter";HASHTAB.newsletter="newsletter"}}catch(_){}
 if(location.hash=="#newsletter")setTimeout(()=>tb&&!tb.classList.contains("on")&&tb.click(),350);
 const box=document.getElementById("nl_app");
 const load=async()=>{if(box.dataset.loaded)return;box.dataset.loaded=1;
  try{const r=await fetch(API+"form?mode=card",{cache:"no-store"});box.innerHTML=await r.text();box.querySelectorAll("form[data-nl-form]").forEach(enhance)}
  catch(e){box.dataset.loaded="";box.innerHTML='<p class="nl-msg err">Couldn\'t load the form. <a href="newsletter">Open the newsletter page</a>.</p>'}};
 load();
}
document.querySelectorAll("form[data-nl-form]").forEach(enhance);
enhanceManage(document.getElementById("nl_manage"));
})();
