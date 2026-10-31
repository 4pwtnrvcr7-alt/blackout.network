// ---- Radio tab (served by radio.py): number stations, military HF and live radio, playable inline; audio archive. All times ET. ----
(()=>{"use strict";
const M=document.getElementById("tab-radio");if(!M)return;
const E=s=>(typeof esc=="function"?esc:(x=>String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))))(s==null?"":String(s));
const TZ="America/New_York";
const fT=(t,d)=>{if(!t)return"";const o={timeZone:TZ,hour:"numeric",minute:"2-digit"};if(d){o.month="short";o.day="numeric"}return new Date(t).toLocaleString("en-US",o)+" ET"};
const until=t=>{const s=Math.round((Date.parse(t)-Date.now())/1000);if(s<=0)return s>-600?"on now":"";const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`in ${h}h ${m}m`:`in ${m}m`};
const mb=b=>b>=1e9?(b/1e9).toFixed(2)+" GB":b>=1e6?(b/1e6).toFixed(1)+" MB":Math.round(b/1e3)+" KB";
const R={d:null,arc:null,st:LS("rd_arc_st",""),day:"",busy:false};
function LS(k,d){try{return localStorage.getItem(k)||d}catch(_){return d}}
function SS(k,v){try{localStorage.setItem(k,v)}catch(_){}}

// tab button + deep link (#radio): in the Monitor group right after Live Streams
const nav=document.querySelector(".tabs");let tb=nav&&nav.querySelector('button[data-tab="radio"]');
if(nav&&!tb){tb=document.createElement("button");tb.dataset.tab="radio";tb.textContent="📻 Radio";const s=nav.querySelector('button[data-tab="streams"]');s?s.after(tb):nav.appendChild(tb)}
try{if(typeof TABHASH=="object"){TABHASH.radio="radio";HASHTAB.radio="radio"}}catch(_){}

const app=document.getElementById("rd_app");
app.innerHTML=`<div id=rd_sum class=rd-sum>Checking streams…</div>
<div id=rd_geo></div><div id=rd_local></div>
<h3 class=rd-h>📡 Shortwave relays <span class=meta>— live from a public KiwiSDR receiver, relayed by this dashboard</span></h3><div id=rd_relays class=rd-grid></div>
<h3 class=rd-h>🔊 Live streams <span class=meta>— play straight from the source</span></h3><div id=rd_direct></div>
<h3 class=rd-h>🔢 Number stations: next transmissions <span class=meta>— Priyom.org public schedule</span></h3><div id=rd_sched></div>
<details class=rd-det><summary>Station guide (frequencies and locations as published by Priyom.org)</summary><div id=rd_guide></div></details>
<h3 class=rd-h>🔗 More live radio <span class=meta>— opens the source's own player (can't be embedded here)</span></h3><div id=rd_links class=rd-links></div>
<h3 class=rd-h id=rd_arch_h>🗄 Audio archive <span class=meta>— 15-minute recordings you can play or download</span></h3>
<div class=rd-arcbar><label>Station <select id=rd_arc_st></select></label> <label>Date <select id=rd_arc_day></select></label> <span class=meta id=rd_arc_meta></span></div>
<audio id=rd_arc_player controls preload=none class=rd-arcplayer></audio><div id=rd_arc_now class=meta></div><div id=rd_arc_list></div>
<div id=la_mount_radio></div>
<div class="meta rd-attr">Sources: <a href="https://priyom.org/" target=_blank rel=noopener>Priyom.org</a> (schedule, station data) · <a href="https://wxradio.org/" target=_blank rel=noopener>WXRadio.org</a> (NOAA relays) · KiwiSDR receivers by HB9HEH (Hasenberg, Switzerland) · <a href="https://websdr.ewi.utwente.nl:8901/" target=_blank rel=noopener>University of Twente WebSDR</a> · <a href="https://somafm.com/" target=_blank rel=noopener>SomaFM</a> · BBC · NPR · VOA · NHK · RFE/RL · <a href="https://www.broadcastify.com/" target=_blank rel=noopener>Broadcastify</a> · <a href="https://www.liveatc.net/" target=_blank rel=noopener>LiveATC</a>. Receive-only monitoring; attribution of stations is as publicly reported.</div>`;

// ---------- players ----------
let hlsP=null;const hlsLoad=()=>hlsP||(hlsP=new Promise((ok,no)=>{if(window.Hls)return ok();const s=document.createElement("script");s.src="api/radio/hls.min.js";s.onload=ok;s.onerror=no;document.head.appendChild(s)}));
const ALL=()=>[...M.querySelectorAll("audio")];
function solo(a){ALL().forEach(x=>{if(x!==a&&!x.paused)x.pause()})}
M.addEventListener("play",e=>{if(e.target.tagName=="AUDIO")solo(e.target)},true);
async function playHls(btn){const card=btn.closest(".rd-card"),a=card.querySelector("audio"),url=btn.dataset.hls;btn.disabled=true;btn.textContent="Connecting…";
 try{if(a.canPlayType("application/vnd.apple.mpegurl")&&!window.MediaSource){a.src=url}else{await hlsLoad();if(a._hls)a._hls.destroy();const h=new Hls({liveSyncDurationCount:2});h.loadSource(url);h.attachMedia(a);a._hls=h;
   h.on(Hls.Events.ERROR,(_,d)=>{if(d.fatal){btn.disabled=false;btn.textContent="▶ Retry";card.querySelector(".rd-err").textContent="Stream error: "+(d.details||d.type)}})}
  a.hidden=false;solo(a);await a.play();btn.hidden=true}catch(e){btn.disabled=false;btn.textContent="▶ Retry";card.querySelector(".rd-err").textContent="Couldn't start: "+e}}
M.addEventListener("click",e=>{const b=e.target.closest("button[data-hls]");if(b)playHls(b)});

const dot=(ok,txt)=>`<span class="rd-dot ${ok===true?"on":ok===false?"off":"unk"}" title="${E(txt||"")}"></span>`;
function relayCard(r){const t=r.tuned||{},ev=t.archive_id=="priyom";
 const st=r.live?`${dot(true)} LIVE${ev?" · scheduled number-station window":""}`:`${dot(false)} offline${r.next_try?" · retry "+fT(r.next_try):""}${r.worker!="running"?" · relay "+E(r.worker):""}`;
 return `<div class="rd-card relay"><div class=rd-top><b>${E(ev?t.label:r.name)}</b><span class=rd-badge>SDR relay</span></div>
 <div class=rd-st>${st}</div><div class=rd-f>${E((t.khz||r.freq_khz)+" kHz "+String(t.mode||r.mode).toUpperCase())}${r.receiver?` · ${E(r.receiver.label)}`:""}${r.until?` · until ${fT(r.until)}`:""}</div>
 <div class=rd-d>${E(r.desc)}</div>
 ${r.live?`<button class=pri data-hls="${E(r.hls)}">▶ Play live</button>`:""}<audio controls preload=none hidden></audio><div class="rd-err meta"></div>
 <div class=rd-l><a href="${E(r.tune_url)}" target=_blank rel=noopener>Listen on WebSDR ↗</a> · <a href="${E(r.src_url)}" target=_blank rel=noopener>${E(r.src)} ↗</a> · <a href="#" data-arc="${E(ev?"priyom":r.id)}">Archive</a></div></div>`}
function directCard(s){const v=s.status;const ok=v?v.ok:null;
 return `<div class=rd-card><div class=rd-top><b>${E(s.name)}</b><span class=rd-badge>${s.kind=="hls"?"HLS":"MP3"} stream</span></div>
 <div class=rd-st>${dot(ok,v&&v.err)} ${ok===true?"on air":ok===false?"offline"+(v.err?" ("+E(v.err)+")":""):"checking…"}${s.recording?" · <span class=rd-rec>● archiving</span>":""}</div>
 ${s.freq?`<div class=rd-f>${E(s.freq)}</div>`:""}<div class=rd-d>${E(s.desc)}</div>
 ${s.kind=="hls"?`<button class=pri data-hls="${E(s.url)}">▶ Play live</button><audio controls preload=none hidden></audio>`:`<audio controls preload=none src="${E(s.url)}"></audio>`}<div class="rd-err meta"></div>
 <div class=rd-l>Source: <a href="${E(s.src_url)}" target=_blank rel=noopener>${E(s.src)} ↗</a>${s.archive?` · <a href="#" data-arc="${E(s.id)}">Archive</a>`:""}</div></div>`}

function render(){const d=R.d;if(!d)return;
 const playing=ALL().some(a=>!a.paused&&a.id!="rd_arc_player");
 const on=d.direct.filter(s=>s.status&&s.status.ok).length+d.relays.filter(r=>r.live).length,tot=d.direct.length+d.relays.length;
 const ret=d.retention;
 $("rd_sum").innerHTML=`<b>${on} of ${tot}</b> live sources on air · streams checked ${d.checked?fT(d.checked):"—"} (every 5 min) · ${d.schedule.length?`next number station: <b>${E(d.schedule[0].station)} ${d.schedule[0].khz} kHz</b> ${fT(d.schedule[0].start)} (${until(d.schedule[0].start)})`:"schedule unavailable"}${ret?` · archive ${mb(ret.total_bytes)} of ${mb(ret.cap_bytes)} cap, ${ret.retain_days}-day retention`:""}`;
 if(!playing){$("rd_relays").innerHTML=d.relays.map(relayCard).join("");
  const g={};d.direct.filter(s=>s.featured!==false).forEach(s=>(g[s.group]=g[s.group]||[]).push(s));
  $("rd_direct").innerHTML=Object.entries(g).map(([k,v])=>`<div class=rd-grp>${E(k)}</div><div class=rd-grid>${v.map(directCard).join("")}</div>`).join("")}
 else{d.relays.forEach((r,i)=>{const c=$("rd_relays").children[i];if(c)c.querySelector(".rd-st").innerHTML=r.live?`${dot(true)} LIVE`:`${dot(false)} offline`})}
 const sc=d.schedule.slice(0,14);
 $("rd_sched").innerHTML=sc.length?`<table class=rd-tab><tr><th>When (ET)</th><th>Station</th><th>Frequency</th><th>Mode</th><th></th></tr>${sc.map(e=>`<tr><td>${fT(e.start,true)} <span class=meta>${until(e.start)}</span></td><td><b>${E(e.station)}</b>${/\[Target/.test(e.summary)?` <span class=meta>${E(e.summary.replace(/^.*\[Target: ?/,"→ ").replace("]",""))}</span>`:""}</td><td>${e.khz} kHz</td><td>${E(e.mode)}</td><td>${e.tune_url?`<a href="${E(e.tune_url)}" target=_blank rel=noopener>Tune WebSDR ↗</a>`:""}</td></tr>`).join("")}</table>
 <div class=meta>Times from Priyom's public calendar; stations don't always transmit as scheduled. Voice/CW windows are also relayed and archived automatically in the HFGCS slot above (digital-only XPA/F06 skipped).</div>`:`<div class=meta>Priyom schedule unavailable right now.</div>`;
 $("rd_guide").innerHTML=`<table class=rd-tab><tr><th>ID</th><th>Name</th><th>Frequency</th><th>Location (Priyom)</th><th>Next scheduled</th></tr>${d.stations.map(s=>`<tr><td><a href="${E(s.url)}" target=_blank rel=noopener>${E(s.code)}</a></td><td>${E(s.name)}</td><td>${E(s.freq)}${s.tune_url?` · <a href="${E(s.tune_url)}" target=_blank rel=noopener>tune ↗</a>`:""}</td><td>${E(s.loc)}</td><td>${s.next?`${fT(s.next.start,true)} · ${s.next.khz} kHz`:s.code=="S28"||s.code=="S30"||s.code=="S32"?"continuous channel marker":"<span class=meta>none in next 24 h</span>"}</td></tr>`).join("")}</table>`;
 $("rd_links").innerHTML=d.links.map(g=>`<div><div class=rd-grp>${E(g.group)}</div><ul>${g.items.map(i=>`<li><a href="${E(i.url)}" target=_blank rel=noopener>${E(i.name)} ↗</a></li>`).join("")}</ul></div>`).join("")}

async function load(){if(R.busy)return;R.busy=true;try{const r=await fetch("api/radio",{cache:"no-store"});R.d=await r.json();render();if(!R.d.checked)setTimeout(load,9000)}catch(e){$("rd_sum").textContent="Radio unavailable: "+e}R.busy=false;arcLoad()}

// ---------- archive ----------
async function arcLoad(){try{const q=new URLSearchParams();if(R.st)q.set("station",R.st);if(R.day)q.set("date",R.day);
 const a=await (await fetch("api/radio/archive?"+q,{cache:"no-store"})).json();R.arc=a;
 const ss=$("rd_arc_st");if(!a.stations.length){ss.innerHTML="";$("rd_arc_day").innerHTML="";$("rd_arc_list").innerHTML=`<div class=meta>${R.d&&R.d.web_only?"Audio recordings are kept on the scanner node; this public copy doesn't carry them.":"No recordings yet. The recorder starts automatically."}</div>`;return}
 if(!R.st||!a.stations.some(s=>s.id==R.st)){R.st=a.stations[0].id;return arcLoad()}
 ss.innerHTML=a.stations.map(s=>`<option value="${E(s.id)}"${s.id==R.st?" selected":""}>${E(s.name)}</option>`).join("");
 const st=a.stations.find(s=>s.id==R.st);if(!R.day||!st.days.some(x=>x.date==R.day)){R.day=st.days.length?st.days[0].date:"";if(R.day)return arcLoad()}
 $("rd_arc_day").innerHTML=st.days.map(x=>`<option value="${x.date}"${x.date==R.day?" selected":""}>${x.date.slice(0,4)}-${x.date.slice(4,6)}-${x.date.slice(6)} UTC · ${x.files} files · ${mb(x.bytes)}</option>`).join("");
 $("rd_arc_meta").textContent=`Total ${mb(a.total_bytes)} · keeps ${a.retention.days} days or ${mb(a.retention.cap_bytes)} (oldest deleted first) · ${a.retention.kbps} kbps mono MP3`;
 $("rd_arc_list").innerHTML=a.files.length?`<table class=rd-tab><tr><th>Start</th><th>End</th><th>Size</th><th></th></tr>${a.files.slice().reverse().map(f=>`<tr><td>${fT(f.start,true)}</td><td>${f.recording?"<span class=rd-rec>● recording</span>":fT(f.end)}</td><td>${mb(f.bytes)}</td><td><button data-play="${E(f.url)}" data-lbl="${E(st.name+" · "+fT(f.start,true))}">▶ Play</button> <a href="${E(f.url)}?dl=1" download>⬇ Download</a></td></tr>`).join("")}</table>`:`<div class=meta>No files for this day.</div>`}catch(e){$("rd_arc_list").textContent="Archive unavailable: "+e}}
$("rd_arc_st").onchange=e=>{R.st=e.target.value;R.day="";SS("rd_arc_st",R.st);arcLoad()};
$("rd_arc_day").onchange=e=>{R.day=e.target.value;arcLoad()};
M.addEventListener("click",e=>{const p=e.target.closest("button[data-play]");if(p){const a=$("rd_arc_player");a.src=p.dataset.play;$("rd_arc_now").textContent="Playing: "+p.dataset.lbl;solo(a);a.play();return}
 const l=e.target.closest("a[data-arc]");if(l){e.preventDefault();R.st=l.dataset.arc;R.day="";arcLoad().then(()=>$("rd_arch_h").scrollIntoView({behavior:"smooth"}))}});

// ---------- location: local channels for the place the visitor picks (no default; global until chosen) ----------
const km=k=>k==null?"":k<1?"<1 km":k+" km";
const playBtn=(name,url,kind)=>kind=="hls"?`<div class="rd-card mini"><b>${E(name)}</b><button class=pri data-hls="${E(url)}">▶ Play live</button><audio controls preload=none hidden></audio><div class="rd-err meta"></div></div>`
 :`<div class="rd-card mini"><b>${E(name)}</b><audio controls preload=none src="${E(url)}"></audio><div class="rd-err meta"></div></div>`;
let locSeq=0;
async function localLoad(){const L=$("rd_local"),l=window.BNGeo&&BNGeo.get();
 if(!l){L.innerHTML=`<div class="meta rd-locnote">🌐 Showing the global view. Pick a country/state or “Use my location” to add local channels: NOAA Weather Radio, scanner feeds, nearest airports on LiveATC, nearest shortwave receivers and broadcasters. Your choice stays in this browser only.</div>`;return}
 const q=new URLSearchParams();if(l.lat!=null&&l.lon!=null){q.set("lat",l.lat);q.set("lon",l.lon)}else{q.set("cc",l.cc||"");if(l.st)q.set("st",l.st)}
 const my=++locSeq;L.innerHTML=`<div class=meta>Finding local channels for ${E(l.label)} and checking which streams are live…</div>`;
 try{const r=await fetch("api/radio/local?"+q,{cache:"no-store"});const j=await r.json();if(my!=locSeq)return;if(!r.ok)throw j.error||r.status;if(j.global){L.innerHTML="";return}
  const nw=j.nwr.length?`<div class=rd-grp>NOAA Weather Radio near ${E(j.label)}</div><div class=rd-grid>${j.nwr.map(n=>n.stream?playBtn(`${n.cs} ${n.site}, ${n.st} · ${n.freq} MHz · ${km(n.km)}`,n.stream,"mp3")
     :`<div class="rd-card mini"><b>${E(n.cs)} ${E(n.site)}, ${E(n.st)}</b><div class=rd-f>${E(n.freq)} MHz · ${km(n.km)}${n.status&&n.status!="NORMAL"?" · "+E(n.status):""}</div><div class=meta>${n.stream_checked?"Online relay is offline right now":"No public online stream; tune a weather radio to "+E(n.freq)+" MHz"}</div></div>`).join("")}</div>`:"";
  const bc=j.broadcasters.length?`<div class=rd-grp>Broadcasters (${E(j.stname||j.label)})</div><div class=rd-grid>${j.broadcasters.map(b=>b.playable?playBtn(b.name,b.url,b.kind)
     :`<div class="rd-card mini"><b>${E(b.name)}</b><div class=meta>Couldn't verify a live stream from here · <a href="${E(b.homepage||b.url)}" target=_blank rel=noopener>open source ↗</a></div></div>`).join("")}</div>`:`<div class=meta>No broadcasters listed for this area.</div>`;
  const ln=(t,a)=>a.length?`<div><div class=rd-grp>${t}</div><ul>${a.join("")}</ul></div>`:"";
  L.innerHTML=`<div class=meta>Local channels for <b>${E(j.label)}</b> (distances from the ${E(j.point)}).</div>${nw}${bc}
  <div class=rd-links>${ln("Scanner feeds",j.scanners.map(x=>`<li><a href="${E(x.url)}" target=_blank rel=noopener>${E(x.name)} ↗</a></li>`))}
  ${ln("Air traffic control (LiveATC)",j.atc.map(a=>`<li><a href="${E(a.url)}" target=_blank rel=noopener>${E(a.icao)} ${E(a.name)}</a> <span class=meta>${E(a.city)} · ${km(a.km)}</span></li>`))}
  ${ln("Nearest shortwave receivers (KiwiSDR)",j.kiwis.map(k=>`<li><a href="${E(k.url)}" target=_blank rel=noopener>${E(k.label)} ↗</a> <span class=meta>${km(k.km)}</span></li>`))}</div>
  <div class="meta rd-attr">Local sources: ${Object.values(j.sources).map(E).join(" · ")}. Inline players appear only for streams verified live from the server just now; everything else is a link.</div>`}
 catch(e){if(my==locSeq)L.innerHTML=`<div class=meta>Local channels unavailable: ${E(e)}</div>`}}
function geoInit(){if(!window.BNGeo)return setTimeout(geoInit,300);BNGeo.picker($("rd_geo"));BNGeo.on(()=>localLoad());localLoad()}
geoInit();

$("rd_ref").onclick=()=>{R.d=null;load();localLoad()};
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="radio")load()});
setInterval(()=>{if(M.style.display!="none")load()},60000);
if(location.hash=="#radio")setTimeout(load,350);
})();
