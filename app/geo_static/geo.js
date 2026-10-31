// ---- Shared visitor location picker (visitor_geo.py). No default location: "Global" until the visitor chooses.
// The choice lives only in this browser (localStorage "bn_loc"); "Use my location" asks the browser, rounds the position,
// sends it once with the lookup request (never logged/stored server-side) and keeps only a ~10 km rounded point here.
// The owner's private preset appears only on the box-local dashboard and only after the admin passcode (sessionStorage).
(()=>{"use strict";if(window.BNGeo)return;
const E=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rd=(k,st)=>{try{return JSON.parse(st.getItem(k)||"null")}catch(_){return null}};
let META=null,metaP=null;const meta=()=>metaP||(metaP=fetch("api/geo/meta").then(r=>r.json()).then(j=>META=j).catch(()=>META={countries:[],states:[]}));
const G={get(){return rd("bn_loc_private",sessionStorage)||rd("bn_loc",localStorage)},
 set(l,priv){try{if(priv){sessionStorage.setItem("bn_loc_private",JSON.stringify(l))}else{sessionStorage.removeItem("bn_loc_private");l?localStorage.setItem("bn_loc",JSON.stringify(l)):localStorage.removeItem("bn_loc")}}catch(_){}
  window.dispatchEvent(new CustomEvent("bn-geo",{detail:G.get()}))},
 on(cb){window.addEventListener("bn-geo",e=>cb(e.detail))},
 label(l){return l?l.label:"Global (no location)"},
 async picker(el){if(!el||el.querySelector(".geo-pick"))return;await meta();const w=document.createElement("div");w.className="geo-pick";
  w.innerHTML=`<label>📍 Location <select class=geo-cc aria-label=Country><option value="">🌐 Global (no location)</option>${META.countries.filter(c=>c.name).map(c=>`<option value="${E(c.cc)}">${E(c.name)}</option>`).join("")}</select></label>
  <select class=geo-st aria-label="State or region" hidden><option value="">All states</option>${META.states.map(s=>`<option value="${E(s.code)}">${E(s.name)}</option>`).join("")}</select>
  <button type=button class=geo-me title="Ask your browser for your position (only when you click). It's rounded and used for this lookup only.">📍 Use my location</button><span class="meta geo-msg"></span>`;
  el.appendChild(w);const cc=w.querySelector(".geo-cc"),st=w.querySelector(".geo-st"),msg=w.querySelector(".geo-msg");
  const sync=()=>{const l=G.get();if(l&&l.private){cc.value="__private";st.hidden=true;msg.textContent=l.label;return}
   cc.value=l&&l.cc||"";st.hidden=cc.value!="US";st.value=l&&l.st||"";msg.textContent=l&&l.lat!=null&&l.city?"near "+l.label:""};
  sync();G.on(sync);
  cc.onchange=async()=>{const v=cc.value;if(!v){G.set(null);return}const c=META.countries.find(x=>x.cc==v);G.set({cc:v,country:c?c.name:v,st:"",label:c?c.name:v})};
  st.onchange=()=>{const s=META.states.find(x=>x.code==st.value);G.set(s?{cc:"US",country:"United States",st:s.code,stname:s.name,label:s.name+", United States"}:{cc:"US",country:"United States",st:"",label:"United States"})};
  w.querySelector(".geo-me").onclick=()=>{if(!navigator.geolocation){msg.textContent="Location not available in this browser";return}msg.textContent="asking your browser…";
   navigator.geolocation.getCurrentPosition(async p=>{try{const la=p.coords.latitude.toFixed(2),lo=p.coords.longitude.toFixed(2);const j=await (await fetch(`api/geo/where?lat=${la}&lon=${lo}`,{cache:"no-store"})).json();
     G.set({...j,lat:Math.round(p.coords.latitude*10)/10,lon:Math.round(p.coords.longitude*10)/10,geo:true})}catch(e){msg.textContent="✗ "+e}},e=>{msg.textContent="✗ "+(e.message||"permission denied")},{timeout:15000,maximumAge:600000})}}};
window.BNGeo=G;
})();
