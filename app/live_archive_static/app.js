// ---- Live Archive panels (live_archive.py): a searchable, date-by-date log of what was live, on the Live Streams,
// Live Broadcasts, Network Status and Radio tabs. Times in ET. Logged every 5 min; nothing is recorded here, only listed.
(()=>{"use strict";
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const TZ="America/New_York";
const fT=t=>new Date(t).toLocaleString("en-US",{timeZone:TZ,month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
const today=()=>new Date().toLocaleDateString("en-CA",{timeZone:TZ});
const dur=(a,b)=>{const m=Math.max(0,Math.round((Date.parse(b)-Date.parse(a))/60000));return m<60?m+" min":Math.floor(m/60)+" h "+(m%60)+" min"};
const LBL={streams:"what was live on air",bcast:"which live sources were up or down",net:"each service's status over time",radio:"which radio sources were on air",finance:"each instrument's last price per trading day (updated every 10 min while markets trade)"};
function mount(sec,host){if(!host||host.querySelector(".la-box"))return;
 const d=document.createElement("details");d.className="pn la-box";d.dataset.sec=sec;
 d.innerHTML=`<summary><b>🗄 Archive</b> <span class=meta>— ${LBL[sec]} (logged every 5 min, kept 90 days)</span></summary>
 <div class=la-bar><label>Day (ET) <input type=date class=la-day value="${today()}" max="${today()}"></label><input type=search class=la-q placeholder="Search title, channel, status…"><span class="meta la-meta"></span></div><div class=la-list></div>`;
 host.appendChild(d);const go=()=>load(d);d.addEventListener("toggle",()=>{if(d.open)go()});
 d.querySelector(".la-day").onchange=go;let t;d.querySelector(".la-q").oninput=()=>{clearTimeout(t);t=setTimeout(go,300)}}
async function load(d){const q=new URLSearchParams({section:d.dataset.sec,date:d.querySelector(".la-day").value||today(),q:d.querySelector(".la-q").value});
 const L=d.querySelector(".la-list");try{const j=await (await fetch("api/live_archive?"+q,{cache:"no-store"})).json();if(j.error){L.textContent=j.error;return}
  d.querySelector(".la-meta").textContent=`${j.items.length} entr${j.items.length==1?"y":"ies"}${j.since?" · log starts "+fT(j.since)+" ET":""}`;
  L.innerHTML=j.items.length?`<table class=la-tab><tr><th>Seen (ET)</th><th>What</th><th>Status</th></tr>${j.items.map(x=>`<tr><td>${fT(x.first_seen)} – ${x.ended?fT(x.last_seen):"<b class=la-now>now</b>"}<div class=meta>${dur(x.first_seen,x.last_seen)}</div></td>
   <td>${x.url&&/^https?:/.test(x.url)?`<a href="${E(x.url)}" target=_blank rel=noopener>${E(x.title)}</a>`:E(x.title)}<div class=meta>${E(x.channel||"")}</div></td><td>${E(x.status)}</td></tr>`).join("")}</table>`:`<div class=meta>Nothing logged for this day${j.q?" matching “"+E(j.q)+"”":""}.</div>`}catch(e){L.textContent="Archive unavailable: "+e}}
function init(){mount("streams",document.getElementById("tab-streams"));mount("bcast",document.getElementById("tab-bcast"));mount("net",document.getElementById("tab-net"));
 mount("radio",document.getElementById("la_mount_radio"))}
window.BN_LA_MOUNT=mount;init();setTimeout(init,800);
})();
