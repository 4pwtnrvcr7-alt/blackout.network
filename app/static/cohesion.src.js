
const $=id=>document.getElementById(id);
// ---- Cohesion: shared palette lookups, shared red-string path, one tab bar, deep links (#wire, #thread, #network …) ----
function catColor(id,fb){const al={infrastructure:"infra",link:"link"}[id]||id;const v=getComputedStyle(document.documentElement).getPropertyValue("--c-"+al).trim();return v||fb||"#8a5a5a"}
function redStringD(ax,ay,bx,by,sag,wob){wob=wob||0;const mx=(ax+bx)/2,my=(ay+by)/2;return `M${ax.toFixed(1)},${ay.toFixed(1)} Q${(mx+wob).toFixed(1)},${(my+sag+wob*.5).toFixed(1)} ${bx.toFixed(1)},${by.toFixed(1)}`}
const TABHASH={threat:"wire",jets:"jets",thread:"thread",bcast:"broadcasts",streams:"streams",radio:"radio",net:"network",solar_seismic:"solar",ranked:"ranked",res:"resources",maps:"maps",bush:"bushcraft",med:"medical",tips:"tips"};
const HASHTAB=Object.fromEntries(Object.entries(TABHASH).map(([k,v])=>[v,k]));
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeUrl=u=>/^https?:\/\//i.test(u||"")?u:"#";
const fmt=t=>{if(!t)return"time n/a";const d=new Date(t);return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET"};
const lv=s=>s>=60?"h":s>=35?"m":"l";
const CATS=["war/conflict","disease","natural disaster","cyber","space weather","other"];
const COL={"war/conflict":"#ff4d4f","disease":"#b37feb","natural disaster":"#faad14","cyber":"#36cfc9","space weather":"#4aa3ff","other":"#8c8c8c"};
let S=null,filter="all",map,heat,markers,volC,trC,settingsLoaded=false;
/* Rank Meter (brand A "Signal", t323): 10 segments + numeral; styles in /sitenav.css */
window.bnMeter=function(r,sz){r=Math.max(0,Math.min(10,Math.round(+r||0)));return `<span class="bn-meter bn-r${r}${sz?" bn-meter-"+sz:""}" role="img" aria-label="Rank ${r} of 10" title="Rank ${r} of 10"><span class="bn-segs" aria-hidden="true">${"<i></i>".repeat(10)}</span><b class="bn-num" aria-hidden="true">${r}<small>/10</small></b></span>`};
function card(c){return `<div class="card ${lv(c.score)}" data-cid="${esc(c.cluster_id)}">${c.rank!=null?`<div class="bn-rkline">${bnMeter(c.rank,"s")}<span class="sc ${lv(c.score)}" title="Severity score 0–100">${c.score}</span></div>`:`<span class="sc ${lv(c.score)}">${c.score}</span>`}<b>${esc(c.title)}</b>
<div class="meta">${esc(c.category)} · ${esc(c.location||"")} · ${fmt(c.event_time)} · confidence <b>${esc(c.confidence)}</b> · ${c.n_families} source${c.n_families==1?"":"s"}</div>
<div class="meta">${c.links.slice(0,6).map(l=>`<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer">${esc(l.source)}</a>`).join(" · ")}</div>
${c.brief?`<div class="brief">${esc(c.brief)}</div>`:""}</div>`}
function render(){
 $("thr").textContent=S.high_threshold;
 $("status").textContent=`Updated ${fmt(S.generated)} · last scan ${S.scans[0]?fmt(S.scans[0].finished):"—"} · next ${S.next_scan?fmt(S.next_scan):"—"}${S.scanning?" · scanning…":""}`;;try{/* t414: freshness watchdog: banner when no scan within 2x interval; lagging-source count (failing 6h+) in Settings status */const _iv=(S.interval_minutes||60)*60e3,_ls=S.scans&&S.scans.find(x=>x.finished&&!x.error),_age=_ls?Date.now()-Date.parse(_ls.finished):1/0,_lag=(S.sources||[]).filter(h=>h.ok===0&&h.last_ok&&Date.now()-Date.parse(h.last_ok)>=216e5);let _b=document.getElementById("bn_stale");if(_age>2*_iv){if(!_b){_b=document.createElement("div");_b.id="bn_stale";_b.setAttribute("role","status");_b.style.cssText="margin:8px auto;max-width:1100px;padding:8px 12px;border:1px solid #C9CDD3;border-radius:10px;background:rgba(201,205,211,.10);color:inherit;font:600 13px/1.4 Inter,system-ui,sans-serif;overflow-wrap:anywhere";const _h=document.querySelector(".bn-pagehead");(_h&&_h.parentNode?_h.parentNode.insertBefore(_b,_h.nextSibling):document.body.prepend(_b))}_b.textContent=`Data may be stale: the last successful scan was ${_ls?fmt(_ls.finished):"unknown"} (scans normally run every ${S.interval_minutes||60} min). Showing the latest data we have.`}else if(_b)_b.remove();if(_lag.length)$("status").textContent+=` · ${_lag.length} source${_lag.length>1?"s":""} lagging 6h+`}catch(_){}
 vrFill();if(S.interval_minutes)$("status").textContent+=` · scanner checks sources every ${S.interval_minutes<60?S.interval_minutes+" min":(S.interval_minutes/60)+" h"}`;
 $("filters").innerHTML=["all",...CATS].map(c=>`<button class="${c==filter?"on":""}" data-c="${c}">${c}</button>`).join("");
 const feed=S.main.filter(c=>filter=="all"||c.category==filter).sort((a,b)=>(b.score>=S.high_threshold)-(a.score>=S.high_threshold)||(b.score-a.score));
 $("feed").innerHTML=feed.map(card).join("")||"<div class=meta>No items.</div>";
 $("wcount").textContent=S.watchlist_count;$("watch").innerHTML=S.watchlist.map(card).join("")||"<div class=meta>Empty.</div>";
 $("sources").innerHTML="<table><tr><th>Source</th><th>Status</th><th>Items</th><th>Checked</th></tr>"+S.sources.map(s=>`<tr><td><a href="${esc(safeUrl(s.url))}" target=_blank rel="noopener noreferrer">${esc(s.name)}</a>${s.error?`<div class=meta>${esc(s.error)}</div>`:""}</td><td class="${s.ok==1?"ok":s.ok==0?"bad":"dis"}">${s.ok==1?"OK":s.ok==0?"FAIL":"disabled"}</td><td>${s.items}</td><td>${fmt(s.last_checked)}</td></tr>`).join("")+"</table>";
  if((typeof L!=="undefined"&&typeof Chart!=="undefined")||bnThreatOn()) bnPaintMapCharts();
 if(!settingsLoaded){applySettings(S.settings);settingsLoaded=true}
 $("apilink").href="api/new_high?since="+new Date(Date.now()-864e5).toISOString().slice(0,19)+"Z";
}
function bnThreatOn(){if(document.documentElement.classList.contains("bna-home"))return false;const t=$("tab-threat");if(!t)return false;try{const cs=getComputedStyle(t);if(cs.display==="none"||cs.visibility==="hidden"||t.hidden)return false}catch(e){}return !!document.querySelector('button[data-tab="threat"].on')}
function bnGuardHeat(){if(typeof L==="undefined"||!L.HeatLayer||L.HeatLayer.prototype._bnGuard)return;const o=L.HeatLayer.prototype._redraw;L.HeatLayer.prototype._redraw=function(){if(!this._map||!this._map.getSize().x||!this._canvas||!this._canvas.width){this._frame=null;return}return o.call(this)};L.HeatLayer.prototype._bnGuard=1}
function bnPaintMapCharts(){
  const go=()=>{
    if(typeof L==="undefined")return;
    bnGuardHeat();
    if(!map){map=L.map("map",{worldCopyJump:true}).setView([20,0],2);bnBaseLayer(map,{maxZoom:10});markers=L.layerGroup().addTo(map)}
    heatDirty=true;if($("map").offsetWidth)drawHeat();
    markers.clearLayers();S.geo.filter(g=>g.score>=35).forEach(g=>L.circleMarker([g.lat,g.lon],{radius:4+g.score/12,color:COL[g.category],weight:1,fillOpacity:.6}).bindPopup(`<b>${g.score}</b> ${esc(g.title)}`).addTo(markers));
    if(typeof Chart==="undefined")return;
    const days=(function(endIso){const et=new Intl.DateTimeFormat("en-CA",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit"}).format(endIso?new Date(endIso):new Date());const p=et.split("-").map(Number),utc=Date.UTC(p[0],p[1]-1,p[2],12),out=[];for(let i=6;i>=0;i--)out.push(new Date(utc-i*864e5).toISOString().slice(0,10));return out})(S.generated);
    const ds=CATS.map(c=>({label:c,backgroundColor:COL[c],data:days.map(d=>(S.volume.find(v=>v.d==d&&v.category==c)||{n:0}).n)}));
    const opt={responsive:true,plugins:{legend:{labels:{color:"#ccc",boxWidth:10}}},scales:{x:{stacked:true,ticks:{color:"#999"}},y:{stacked:true,ticks:{color:"#999"},grid:{color:"#222"}}}};
    if(volC){volC.data.labels=days;volC.data.datasets=ds;volC.update()}else volC=new Chart($("vol"),{type:"bar",data:{labels:days,datasets:ds},options:opt});
    const tl=days,td=[{label:"max",data:days.map(d=>(S.trend.find(t=>t.d==d)||{mx:0}).mx),borderColor:"#ff4d4f"},{label:"avg",data:days.map(d=>(S.trend.find(t=>t.d==d)||{avg:0}).avg),borderColor:"#faad14"},{label:"# high",data:days.map(d=>(S.trend.find(t=>t.d==d)||{high:0}).high),borderColor:"#4aa3ff"}];
    const o2={responsive:true,plugins:{legend:{labels:{color:"#ccc",boxWidth:10}}},scales:{x:{ticks:{color:"#999"}},y:{min:0,ticks:{color:"#999"},grid:{color:"#222"}}}};
    if(trC){trC.data.labels=tl;trC.data.datasets=td;trC.update()}else trC=new Chart($("trend"),{type:"line",data:{labels:tl,datasets:td},options:o2});
  };
  if(typeof L!=="undefined"&&typeof Chart!=="undefined") go();
  else if(window.bnLazyLoad) Promise.all([window.bnLazyLoad("leaflet"),window.bnLazyLoad("chart")]).then(go);
}
let heatDirty=false;function drawHeat(){if(typeof L==="undefined"||!map||!S||!heatDirty||!$("map").offsetWidth)return;heatDirty=false;if(heat)map.removeLayer(heat);heat=L.heatLayer(S.geo.map(g=>[g.lat,g.lon,Math.max(.15,g.score/100)]),{radius:22,blur:18,maxZoom:6}).addTo(map)}
function applySettings(s){
 $("phonecur").textContent=s.phone_saved?"saved: "+s.phone_masked:"no number saved";
 $("ch_email").checked=s.channels.email;$("ch_app").checked=s.channels.app;$("ch_sms").checked=s.channels.sms;
 $("d_sms").textContent=s.delivery_status.sms;$("d_email").textContent=s.delivery_status.email;$("d_app").textContent=s.delivery_status.app;
 updSms(s.phone_saved);
}
function normPhone(v){let d=v.replace(/[\s().\-]/g,"");if(d.startsWith("+1"))d=d.slice(2);else if(d.length==11&&d[0]=="1")d=d.slice(1);return /^[2-9]\d{2}[2-9]\d{6}$/.test(d)?d:null}
let phoneSaved=false;function updSms(saved){phoneSaved=saved;const ok=saved;$("ch_sms").disabled=!ok;if(!ok)$("ch_sms").checked=false;$("ch_sms").title=ok?"":"Save a valid phone number first"}
$("phone").addEventListener("input",()=>{const v=$("phone").value.trim();$("smsg").textContent=v&&!normPhone(v)?"Not a valid US 10-digit number yet":"";$("smsg").className=""});
$("save").onclick=async()=>{
 const v=$("phone").value.trim(),body={passcode:$("pass").value,channels:{email:$("ch_email").checked,app:$("ch_app").checked,sms:$("ch_sms").checked}};
 if(v){const n=normPhone(v);if(!n){$("smsg").innerHTML='<span class=bad>✗ Phone must be a valid US 10-digit number, e.g. (555) 555-0100</span>';return}body.phone=n}
 if(!body.passcode){$("smsg").innerHTML='<span class=bad>✗ Enter the admin passcode</span>';return}
 $("save").disabled=true;
 try{const r=await fetch("api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const j=await r.json();
  if(r.ok){$("smsg").innerHTML='<span class=ok>✓ Settings saved '+esc(fmt(j.updated))+'</span>';$("phone").value="";applySettings(j)}
  else $("smsg").innerHTML='<span class=bad>✗ '+esc(j.error||r.status)+'</span>'}catch(e){$("smsg").innerHTML='<span class=bad>✗ '+esc(e)+'</span>'}
 $("save").disabled=false};
$("filters").onclick=e=>{if(e.target.dataset.c){filter=e.target.dataset.c;render()}};
async function load(){try{S=await bnJSON("api/state");render();try{fdr()}catch(_){}}catch(e){$("status").textContent="reconnecting…";clearTimeout(window.__bnLoadRt);window.__bnLoadRt=setTimeout(load,10000)}}
/* t225: the public node never triggers scans or changes settings (POST /api/refresh and /api/interval are refused server-side by render_app.py BOX_ONLY).
   Here Manual refresh only reloads the latest synced data; scans run on the scanner node on its own schedule. */
$("refresh").textContent="⟳ Reload data";$("refresh").title="Reload the latest data. Scans run automatically on the scanner node.";
$("refresh").onclick=async()=>{const b=$("refresh");b.disabled=true;$("msg").textContent="reloading…";
 try{await load();$("msg").textContent=S&&S.scans&&S.scans[0]?`✓ latest data loaded · last scan ${fmt(S.scans[0].finished)}`:"✓ latest data loaded"}catch(e){$("msg").textContent="error "+e}b.disabled=false};
/* t397: "Refresh my view every" is a per-visitor setting (localStorage bn_view_refresh): how often this page re-pulls /api/state.
   Live (default) = every minute plus instant SSE pushes. The scanner's own schedule is set on the scanner node and shown read-only in the status line. */
const VR_KEY="bn_view_refresh",VR_OPTS=[1,5,10,15,20,30,45,60,90,120,180,240,300,360];let vrTimer=0;
function vrGet(){let v=1;try{v=+localStorage.getItem(VR_KEY)||1}catch(_){}return VR_OPTS.includes(v)?v:1}
function vrLabel(m){return m==1?"Live (1 min)":m<60?m+" min":(m/60)+" h"}
function vrFill(){const sel=$("interval");if(!sel)return;sel.disabled=false;if(sel.options.length!==VR_OPTS.length){sel.innerHTML="";VR_OPTS.forEach(m=>{const o=document.createElement("option");o.value=m;o.textContent=vrLabel(m);sel.appendChild(o)})}
 if(document.activeElement!==sel&&+sel.value!==vrGet())sel.value=vrGet()}
function vrArm(){clearInterval(vrTimer);vrTimer=setInterval(load,vrGet()*60000)}
vrFill();$("interval").title="How often this page pulls the latest data on this device";
$("interval").onchange=e=>{const v=+e.target.value;try{localStorage.setItem(VR_KEY,String(v))}catch(_){}vrArm();$("msg").textContent=`✓ saved · this page refreshes ${v==1?"every minute (live)":"every "+vrLabel(v)}`};
load();vrArm();
// ---- private jets tab (informational only; never affects threat ranks) ----
let J=null,jTab=false,jC=null,jKTouched=false;
const tbl=(o,n)=>{const e=Object.entries(o||{}).slice(0,n||99);const mx=Math.max(1,...e.map(x=>x[1]));return e.length?"<table>"+e.map(([k,v])=>`<tr><td>${esc(k)}</td><td style="width:45%"><span class=bar style="width:${Math.round(100*v/mx)}%"></span></td><td>${v}</td></tr>`).join("")+"</table>":"<div class=meta>No data yet.</div>"};
document.querySelector(".tabs").onclick=e=>{const t=e.target.dataset.tab;if(!t)return;document.querySelectorAll(".tabs button").forEach(b=>b.classList.toggle("on",b.dataset.tab==t));
 $("tab-threat").style.display=t=="threat"?"":"none";$("tab-jets").style.display=t=="jets"?"":"none";jTab=t=="jets";if(jTab)loadJets();else if(map)setTimeout(()=>{map.invalidateSize();drawHeat()},50)};
async function loadJets(){try{const r=await fetch("api/jets",{cache:"no-store"});J=await r.json();renderJets()}catch(e){$("j_fresh").textContent="jet data offline: "+e}}
function renderJets(){
 const s=J.snapshot;$("j_big").textContent=s?s.airborne.toLocaleString():"—";
 $("j_fresh").textContent=s?`Last good sample ${fmt(s.ts)} (${s.age_minutes} min ago) · ${s.on_ground} more on the ground · ${s.privacy} privacy-flagged (LADD/PIA) · sampler every ${J.settings.sample_minutes} min (scan interval ${J.settings.scan_interval_minutes} min)`:"No sample yet.";
 let w=[];if(!s)w.push("No jet data yet.");else{if(s.stale)w.push(`⚠ STALE: showing last-known value from ${fmt(s.ts)}; the source has not answered since.`);if(J.last_attempt_failed)w.push(`⚠ Last fetch at ${fmt(J.last_attempt)} failed; value shown is last-known.`);if(s.partial)w.push("⚠ Partial sample: one or more source requests failed.")}
 $("j_warn").innerHTML=w.map(x=>`<div class=warn>${esc(x)}</div>`).join("");$("j_note").textContent="What this counts: "+J.note;
 if(s){$("j_reg").innerHTML=tbl(s.by_region);$("j_mfr").innerHTML=tbl(s.by_mfr);$("j_st").innerHTML=tbl(s.by_status);$("j_cty").innerHTML=tbl(s.by_country,15);$("j_typ").innerHTML=tbl(s.by_type,15)}
 const b=J.baseline;$("j_base").innerHTML=`Baseline for this hour: <b>${esc(b.basis_for_current_hour)}</b>${b.mean!=null&&b.basis_for_current_hour!="warming_up"?` · mean ${b.mean.toFixed(1)} ± ${b.std.toFixed(1)} (n=${b.n})`:""} · valid hours in last 7 days: ${b.valid_hours_7d} · ${esc(b.warmup_rule)}${J.last_eval?` · last hour evaluated: ${fmt(J.last_eval.hour)} → ${J.last_eval.count} takeoffs, ${esc(J.last_eval.status)}`:""}`;
 $("j_nsp").textContent=J.spikes.length;
 $("j_recur").innerHTML=Object.keys(J.recurring_hours).length?`<div class=warn>Recurring spike hours (likely routine schedule peaks): ${Object.entries(J.recurring_hours).map(([k,v])=>esc(k)+" ×"+v).join(", ")}</div>`:"";
 $("j_spikes").innerHTML=J.spikes.map(x=>`<div class="card ${x.suppressed?"l":"m"}"><b>${esc(x.hour_et)}</b> · ${x.count} takeoffs · ${x.pct_above!=null?"+"+x.pct_above+"%":""} vs baseline${x.recurring?'<span class="badge rec">recurring pattern</span>':""}${x.suppressed?`<span class="badge sup">${esc(x.suppressed)}</span>`:""}
  <div class=brief>${esc(x.paragraph)}</div>${(x.coinciding||[]).map(c=>`<div class=meta>[${c.rank}] ${esc(c.title)} ${(c.links||[]).map(l=>`<a href="${esc(safeUrl(l))}" target=_blank rel="noopener noreferrer">link</a>`).join(" ")}</div>`).join("")}</div>`).join("")||"<div class=meta>No takeoff spikes logged yet.</div>";
 $("j_dreg").innerHTML="<div class=meta>By region</div>"+tbl(J.departures_3h.by_region);
 $("j_dap").innerHTML="<div class=meta>Top departure airports</div>"+(J.departures_3h.top_airports.length?"<table>"+J.departures_3h.top_airports.map(a=>`<tr><td>${esc(a.airport)}</td><td>${esc(a.airport_name)} (${esc(a.airport_country)})</td><td>${a.n}</td></tr>`).join("")+"</table>":"<div class=meta>None yet.</div>");
 $("j_src").innerHTML="<table><tr><th>Request</th><th>Status</th><th>Items</th><th>Checked</th></tr>"+J.sources.map(x=>`<tr><td><a href="${esc(safeUrl(x.url))}" target=_blank rel="noopener noreferrer">${esc(x.name)}</a>${x.error?`<div class=meta>${esc(x.error)}</div>`:""}</td><td class="${x.ok?"ok":"bad"}">${x.ok?"OK":"FAIL"}</td><td>${x.items}</td><td>${fmt(x.last_checked)}${!x.ok&&x.last_ok?"<div class=meta>last OK "+fmt(x.last_ok)+"</div>":""}</td></tr>`).join("")+"</table>";
 $("j_links").innerHTML="Sources: "+J.source_links.map(l=>`<a href="${esc(safeUrl(l.url))}" target=_blank rel="noopener noreferrer">${esc(l.name)}</a>`).join(" · ")+" · No API keys required.";
 if(document.activeElement!==$("j_k")&&!jKTouched){$("j_k").value=J.settings.k;$("j_kv").textContent=J.settings.k}
 if(document.activeElement!==$("j_en"))$("j_en").checked=J.settings.enabled;
 const t=J.trend24,lab=t.map(x=>x.label),ds=[{type:"line",label:"avg airborne",data:t.map(x=>x.avg_airborne),borderColor:"#4aa3ff",yAxisID:"y"},
  {type:"bar",label:"takeoffs",data:t.map(x=>x.departures),backgroundColor:"#faad14",yAxisID:"y2"},{type:"line",label:"spike threshold",data:t.map(x=>x.threshold),borderColor:"#ff4d4f",borderDash:[4,4],yAxisID:"y2"}];
 if(jC){jC.data.labels=lab;jC.data.datasets=ds;jC.update()}else jC=new Chart($("j_trend"),{data:{labels:lab,datasets:ds},options:{responsive:true,plugins:{legend:{labels:{color:"#ccc",boxWidth:10}}},
  scales:{x:{ticks:{color:"#999"}},y:{position:"left",min:0,ticks:{color:"#4aa3ff"},grid:{color:"#222"}},y2:{position:"right",min:0,ticks:{color:"#faad14"},grid:{display:false}}}}});
}
$("j_k").oninput=()=>{jKTouched=true;$("j_kv").textContent=(+$("j_k").value).toFixed(1)};
$("j_save").onclick=async()=>{const p=$("j_pass").value||$("pass").value;if(!p){$("j_msg").innerHTML='<span class=bad>✗ Enter the admin passcode</span>';return}
 try{const r=await fetch("api/jets/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({passcode:p,k:+$("j_k").value,enabled:$("j_en").checked})});const j=await r.json();
 $("j_msg").innerHTML=r.ok?`<span class=ok>✓ Saved: alerts ${j.jet_spike_alerts_enabled?"on":"off"}, k=${j.jet_spike_k}</span>`:'<span class=bad>✗ '+esc(j.error||r.status)+'</span>';if(r.ok){jKTouched=false;loadJets()}}catch(e){$("j_msg").innerHTML='<span class=bad>✗ '+esc(e)+'</span>'}};
setInterval(()=>{if(jTab)loadJets()},60000);
// ---- Story Arcs (read-only add-on; separate functions, does not alter existing behaviour) ----
let ARCS=null,arcsOpen=new Set(),arcsShown=30,arcsAuto=true;
const arcLv=r=>r>=6?"h":r>=4?"m":"l";
function arcsInit(){const sel=$("arcs_window");const ls=localStorage.getItem("arcs_window");if(ls)sel.value=ls;$("arcs_multi").checked=localStorage.getItem("arcs_multi")=="1";
 fetch("api/arcs_window",{cache:"no-store"}).then(r=>r.json()).then(j=>{if(j.window){sel.value=j.window;localStorage.setItem("arcs_window",j.window)}arcsLoad()}).catch(()=>arcsLoad())}
async function arcsLoad(){try{const w=$("arcs_window").value||"24h";const r=await fetch("api/arcs?window="+encodeURIComponent(w),{cache:"no-store"});const j=await r.json();if(!r.ok)throw j.error||r.status;ARCS=j;
 if(arcsAuto){ARCS.arcs.slice(0,2).forEach(a=>{if(a.n_updates>1)arcsOpen.add(a.id)});arcsAuto=false}arcsRender()}catch(e){$("arcs_meta").textContent="story arcs unavailable: "+e}}
function arcUpd(u){const lk=(u.links||[]).map(l=>`<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer">${esc(l.source||"link")}</a>`).join(" · ")||"<span class=meta>no link</span>";
 return `<li class="${arcLv(u.rank)}"><span class="meta">${esc(u.time_et)}</span> · <b>${u.rank}/10</b> <span class=meta>(score ${u.score})</span>${u.unconfirmed?'<span class=unc>unconfirmed</span>':""}<br>${esc(u.title)}<br><span class=chg>${esc(u.changed)}</span> · ${lk}</li>`}
function arcCard(a){const open=arcsOpen.has(a.id);const con=(a.connections||[]).map(c=>`<span class=chip data-arc="${esc(c.arc)}" title="${esc(c.title)}">${esc(c.title.slice(0,48))}${c.title.length>48?"…":""} <i>${c.shared.map(esc).join(", ")}</i></span>`).join("");
 return `<div class="arc ${arcLv(a.severity)}" id="${esc(a.id)}"><div class="arc-hd" data-tog="${esc(a.id)}"><span class="sc ${arcLv(a.severity)=="h"?"h":arcLv(a.severity)=="m"?"m":"l"}">${a.severity}</span><b>${esc(a.title)}</b><span class=arc-tog>${open?"▾ hide":"▸ "+a.n_updates+" update"+(a.n_updates==1?"":"s")}</span></div>
 <div class=meta>${esc(a.category)} · started ${esc(a.start_et)} · latest ${esc(a.latest_et)} · ${a.n_updates} update${a.n_updates==1?"":"s"} · ${a.n_sources} source${a.n_sources==1?"":"s"}${a.confirmed?"":' <span class=unc>unconfirmed</span>'} · latest ${a.latest_rank}/10${a.places.length?" · "+a.places.map(esc).join(", "):""}</div>
 ${con?`<div class=meta style="margin-top:3px">Connected to: ${con}</div>`:""}
 ${open?`<ul class=tl>${a.updates.slice().reverse().map(arcUpd).join("")}</ul>${a.updates_truncated?`<div class=meta>+${a.updates_truncated} older updates not shown</div>`:""}`:""}</div>`}
function arcsRender(){if(!ARCS)return;const multi=$("arcs_multi").checked;const list=ARCS.arcs.filter(a=>!multi||a.n_updates>1);
 $("arcs_meta").textContent=` ${list.length} stories (${ARCS.multi_update_arcs} with 2+ updates) from ${ARCS.clusters_in_window} alerts in the last ${ARCS.window_label} · updated ${ARCS.generated_et}`;
 $("arcs_list").innerHTML=list.slice(0,arcsShown).map(arcCard).join("")||"<div class=meta>No stories in this window.</div>";
 $("arcs_more").style.display=list.length>arcsShown?"":"none"}
$("arcs_list").onclick=e=>{const c=e.target.closest(".chip[data-arc]");if(c){const id=c.dataset.arc;let el=$(id);if(!el){const i=ARCS.arcs.findIndex(a=>a.id==id);if(i>=0){arcsShown=Math.max(arcsShown,i+1);arcsRender();el=$(id)}}
 if(el){arcsOpen.add(id);arcsRender();el=$(id);el.scrollIntoView({behavior:"smooth",block:"center"});el.classList.add("flash");setTimeout(()=>el.classList.remove("flash"),1500)}return}
 const t=e.target.closest("[data-tog]");if(t&&!e.target.closest("a")){const id=t.dataset.tog;arcsOpen.has(id)?arcsOpen.delete(id):arcsOpen.add(id);arcsRender()}};
$("arcs_more").onclick=()=>{arcsShown+=30;arcsRender()};
$("arcs_multi").onchange=()=>{localStorage.setItem("arcs_multi",$("arcs_multi").checked?"1":"0");arcsRender()};
$("arcs_window").onchange=async e=>{const w=e.target.value;localStorage.setItem("arcs_window",w);arcsShown=30;
 try{const r=await fetch("api/arcs_window",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({window:w})});const j=await r.json();$("arcs_msg").textContent=r.ok?` · ✓ window saved: ${j.label}`:" · ✗ "+(j.error||r.status)}catch(err){$("arcs_msg").textContent=" · ✗ "+err}
 arcsLoad()};
arcsInit();setInterval(arcsLoad,60000);
// ---- add-on tabs: show/hide <main data-addon> panels (runs alongside the existing tab handler) ----
document.querySelector(".tabs").addEventListener("click",e=>{const t=e.target.closest("button")&&e.target.closest("button").dataset.tab;if(!t)return;
 document.querySelectorAll("main[data-addon]").forEach(m=>m.style.display=m.dataset.addon==t?"":"none");if(t=="bcast")bcLoad()});
// ---- Live Broadcasts ----
let BC=null,bcKw="",bcRe=null,bcCat={},bcCol={};
function bcBuild(kw){bcCat={};bcCol={};const ws=[];kw.categories.forEach(c=>{bcCol[c.id]=catColor(c.id,c.color);c.words.forEach(w=>{bcCat[w.toLowerCase().replace(/\s+/g," ")]=c.id;ws.push(w)})});
 ws.sort((a,b)=>b.length-a.length);bcRe=ws.length?new RegExp("(?<![A-Za-z0-9])("+ws.map(w=>w.trim().split(/\s+/).map(p=>p.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("\\s+")).join("|")+")(?![A-Za-z0-9])","gi"):null}
function bcHi(t){t=String(t??"");if(!bcRe)return esc(t);let out="",i=0;t.replace(bcRe,(m,g,off)=>{out+=esc(t.slice(i,off));const c=bcCat[m.toLowerCase().replace(/\s+/g," ")];out+=`<mark style="color:${bcCol[c]||"#fff"};border-color:${bcCol[c]||"#fff"}">${esc(m)}</mark>`;i=off+m.length;return m});return out+esc(t.slice(i))}
async function bcLoad(){bcStations();try{const q=new URLSearchParams({window:$("bc_win").value,source:$("bc_src").value,kw:bcKw});const r=await fetch("api/broadcasts?"+q,{cache:"no-store"});BC=await r.json();if(!r.ok)throw BC.error;bcRender()}catch(e){$("bc_meta").textContent="broadcasts unavailable: "+e}}
function bcRender(){const B=BC;bcBuild(B.keywords);
 const sel=$("bc_src"),cur=sel.value;sel.innerHTML='<option value="">All sources</option>'+B.sources.map(x=>`<option${x==cur?" selected":""}>${esc(x)}</option>`).join("");
 $("bc_meta").textContent=`· ${B.total} clips · updated ${B.generated_et}`;$("bc_filt").innerHTML=bcKw?`filtered to “<b>${esc(bcKw)}</b>” <button id="bc_clr">clear</button>`:"";if($("bc_clr"))$("bc_clr").onclick=()=>{bcKw="";bcLoad()};
 $("bc_clips").innerHTML=B.clips.map(c=>{const au=c.kind=="audio"&&/^https?:/i.test(safeUrl(c.link)),su=safeUrl(c.link).split("#")[0];if(au){const a=bnpMedia(c.id,su);a._name=c.source}return `<${au?"div":"a"} class="clip ${c.kind=="audio"?"audio":""}" data-bid="${esc(c.id)}"${au?"":` href="${esc(safeUrl(c.link))}" target="_blank" rel="noopener noreferrer"`}>
  <div class=meta>${c.kind=="audio"?"🎙 ":"📰 "}<b>${esc(c.source)}</b> · ${esc(c.published_et)}${c.matches.length?" · "+[...new Set(c.matches.map(m=>m.cat))].map(k=>`<span class=swatch style="background:${bcCol[k]}"></span>`).join(""):""}</div>
  <div><b>${bcHi(c.title)}</b></div>${c.text?`<div class=txt>${bcHi(c.kind=="audio"?c.text:c.text.slice(0,300))}</div>`:""}${au?bnpHtml(c.id,su,c.source+" (live)")+`<div class="meta bnp-src">Plays the live stream now. <a href="${esc(safeUrl((c.extra&&c.extra.page)||su))}" target=_blank rel="noopener noreferrer">Open source ↗</a> · <a href="${esc(su)}" target=_blank rel="noopener noreferrer">raw stream ↗</a></div>`:""}</${au?"div":"a"}>`}).join("")+(B.truncated?`<div class=meta>+${B.truncated} more; narrow the filters</div>`:"")||"<div class=meta>No clips match.</div>";
 $("bc_kw").innerHTML=B.keywords.categories.map(c=>`<div class=kwcat><span class=swatch style="background:${catColor(c.id,c.color)}"></span><b style="color:${catColor(c.id,c.color)}">${esc(c.label)}</b><br>${c.words.map(w=>`<span class="kwchip${bcKw==w.toLowerCase()?" on":""}" style="color:${c.color}" data-w="${esc(w)}" data-c="${c.id}">${esc(w)} <span class=meta>${B.keyword_counts[w.toLowerCase()]||0}</span><span class=x data-del="1" title="remove">×</span></span>`).join("")}</div>`).join("");
 const cs=$("bc_cat"),cv=cs.value;cs.innerHTML=B.keywords.categories.map(c=>`<option value="${c.id}"${c.id==cv?" selected":""}>${esc(c.label)}</option>`).join("");
 $("bc_health").innerHTML="<table><tr><th>Source</th><th>Status</th><th>Items</th><th>Checked</th></tr>"+B.health.map(h=>`<tr><td><a href="${esc(safeUrl(h.url))}" target=_blank rel="noopener noreferrer">${esc(h.name)}</a><div class=meta>${esc(h.note||"")}${h.error?" · "+esc(h.error):""}</div></td><td class="${h.ok?"ok":"bad"}">${h.ok?"OK":"FAIL"}</td><td>${h.items}</td><td>${esc(h.last_checked_et||"—")}${!h.ok&&h.last_ok_et?"<div class=meta>last OK "+esc(h.last_ok_et)+"</div>":""}</td></tr>`).join("")+"</table>";
 $("bc_audio").textContent="Audio transcription: "+B.audio_transcription+` · text feeds polled every ${B.text_poll_minutes} min`;bcStations();bcNow()}
// ---- Inline broadcast players (t245): native <audio preload=none>; hls.js (bundled, api/radio/hls.min.js) only for .m3u8, and only where MediaSource exists (it exposes the stream's seekable live window; Chrome's native HLS doesn't); iPhone Safari uses native HLS. ----
// One global coordinator: starting any player stops the others and pauses other <audio>/<video> and YouTube embeds on the page.
const BNP={el:{},hlsP:null,vol:Math.min(1,Math.max(0,+(localStorage.getItem("bnp_vol")??1))),volOK:(()=>{try{const t=document.createElement("audio");t.volume=.5;return t.volume==.5}catch(e){return false}})()};
const bnpFmt=s=>{if(!isFinite(s)||s<0)s=0;s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s/60)%60,x=s%60;return(h?h+":"+String(m).padStart(2,"0"):m)+":"+String(x).padStart(2,"0")};
const bnpUI=pid=>document.querySelectorAll(`.bnp[data-pid="${CSS.escape(pid)}"]`);
function bnpHtml(pid,src,name){const n=esc(name);return `<div class="bnp" data-pid="${esc(pid)}" data-src="${esc(src)}" data-name="${n}" role="group" aria-label="${n} player">
 <button type=button class="bnp-play" aria-label="Play ${n}" aria-pressed="false">▶ Play</button><button type=button class="bnp-stop" aria-label="Stop ${n}" hidden>■ Stop</button>
 <span class="bnp-live" hidden title="Live stream with no fixed length">LIVE</span>
 <input type=range class="bnp-seek" min=0 max=0 step=0.5 value=0 aria-label="Rewind or fast-forward ${n}" disabled><span class="bnp-t" aria-hidden="true">—</span>
 <button type=button class="bnp-edge" aria-label="Jump to live on ${n}" hidden>⏭ Jump to live</button>
 <span class="bnp-volw"><button type=button class="bnp-mute" aria-label="Mute ${n}" aria-pressed="false">Mute</button>${BNP.volOK?`<input type=range class="bnp-vol" min=0 max=1 step=0.05 value="${BNP.vol}" aria-label="Volume ${n}">`:`<span class=meta>use your device volume</span>`}</span>
 <div class="bnp-st meta" role="status" aria-live="polite"></div></div>`}
function bnpMedia(pid,src){let a=BNP.el[pid];if(a)return a;a=document.createElement("audio");a.preload="none";a.dataset.bnp=pid;a._src=src;if(BNP.volOK)a.volume=BNP.vol;
 let pool=$("bnp_pool");if(!pool){pool=document.createElement("div");pool.id="bnp_pool";pool.hidden=true;document.body.appendChild(pool)}pool.appendChild(a);BNP.el[pid]=a;
 const st=(s)=>()=>{a._st=s;bnpSync(pid)};a.addEventListener("waiting",st("Buffering…"));a.addEventListener("playing",()=>{a._st="";a._err="";bnpSync(pid)});
 a.addEventListener("pause",()=>{if(a._loaded)a._st="Paused";bnpSync(pid)});
 a.addEventListener("error",()=>{if(!a.error||!a._loaded)return;a._err=["","Playback aborted","Network error: the stream didn't respond","The stream couldn't be decoded","The stream is offline or its format isn't supported by this browser"][a.error.code]||"Playback error";a._loaded=0;bnpSync(pid)});
 ["timeupdate","progress","durationchange","volumechange","ended"].forEach(ev=>a.addEventListener(ev,()=>bnpSync(pid)));return a}
async function bnpLoad(a){if(a._loaded)return;a._loaded=1;const src=a._src;
 if(/\.m3u8(\?|#|$)/i.test(src)&&(window.MediaSource||!a.canPlayType("application/vnd.apple.mpegurl"))){
  await (BNP.hlsP||(BNP.hlsP=new Promise((ok,no)=>{if(window.Hls)return ok();const s=document.createElement("script");s.src="api/radio/hls.min.js";s.onload=ok;s.onerror=()=>{BNP.hlsP=null;no(new Error("hls.js failed to load"))};document.head.appendChild(s)})));
  if(!window.Hls||!Hls.isSupported())throw new Error("This browser can't play HLS streams");const h=new Hls({liveDurationInfinity:true});a._hls=h;h.loadSource(src);h.attachMedia(a);
  h.on(Hls.Events.ERROR,(e,d)=>{if(d.fatal){a._err="Stream error ("+d.details+")";bnpStop(a.dataset.bnp,true)}})}
 else a.src=src}
function bnpStopAll(keep){Object.keys(BNP.el).forEach(k=>{const m=BNP.el[k];if(m!==keep&&(m._loaded||!m.paused))bnpStop(k)});
 document.querySelectorAll("audio,video").forEach(m=>{if(m!==keep&&!m.paused)try{m.pause()}catch(e){}});
 document.querySelectorAll('iframe[src*="youtube"]').forEach(f=>{try{f.contentWindow.postMessage(JSON.stringify({event:"command",func:"pauseVideo",args:[]}),"*")}catch(e){}})}
async function bnpPlay(pid){const ui=bnpUI(pid)[0];if(!ui)return;const a=bnpMedia(pid,ui.dataset.src);bnpStopAll(a);a._err="";a._st="Connecting…";bnpSync(pid);
 try{await bnpLoad(a);await a.play()}catch(e){if(e&&e.name=="AbortError")return;a._loaded=0;a._err=(e&&e.name=="NotAllowedError")?"The browser blocked playback; press Play again":String(e&&e.message||e);bnpSync(pid)}}
function bnpStop(pid,keepErr){const a=BNP.el[pid];if(!a)return;try{a.pause()}catch(e){}if(a._hls){a._hls.destroy();a._hls=null}a._loaded=0;a.removeAttribute("src");a.load();a._st=keepErr?"":"Stopped";if(!keepErr)a._err="";bnpSync(pid)}
function bnpWin(a){if(!a||!a._loaded||a.readyState<1)return null;const d=a.duration;if(isFinite(d)&&d>0)return{s:0,e:d,live:false};
 const sk=a.seekable,b=a.buffered;if(sk.length&&isFinite(sk.end(sk.length-1))){const se=sk.end(sk.length-1),lp=a._hls&&a._hls.liveSyncPosition;return{s:sk.start(0),e:lp?Math.min(se,lp+1):se,live:true,mode:"dvr"}}
 if(sk.length&&b.length)return{s:Math.max(b.start(0),sk.start(0)),e:b.end(b.length-1),live:true,mode:"buffer"};return{s:0,e:0,live:true,mode:"none"}}
function bnpSync(pid){const a=BNP.el[pid];bnpUI(pid).forEach(u=>{const q=s=>u.querySelector(s),nm=u.dataset.name,on=!!(a&&!a.paused),ld=!!(a&&a._loaded),w=bnpWin(a);
 const pl=q(".bnp-play");pl.textContent=on?"❚❚ Pause":"▶ Play";pl.setAttribute("aria-label",(on?"Pause ":"Play ")+nm);pl.setAttribute("aria-pressed",String(on));q(".bnp-stop").hidden=!ld;u.classList.toggle("on",on);
 const mu=q(".bnp-mute"),vo=q(".bnp-vol"),m=!!(a&&a.muted);mu.textContent=m?"Unmute":"Mute";mu.setAttribute("aria-pressed",String(m));mu.setAttribute("aria-label",(m?"Unmute ":"Mute ")+nm);if(vo&&a&&document.activeElement!==vo)vo.value=m?0:a.volume;
 const sk=q(".bnp-seek"),t=q(".bnp-t"),lv=q(".bnp-live"),ed=q(".bnp-edge");lv.hidden=!(w&&w.live);
 if(!w){sk.disabled=true;sk.min=0;sk.max=0;sk.value=0;t.textContent="—";ed.hidden=true;sk.title="Press Play to start";}
 else if(!w.live){sk.disabled=false;sk.min=0;sk.max=w.e;if(document.activeElement!==sk)sk.value=a.currentTime;t.textContent=bnpFmt(a.currentTime)+" / "+bnpFmt(w.e);ed.hidden=true;sk.setAttribute("aria-valuetext",t.textContent)}
 else{const len=w.e-w.s,beh=Math.max(0,w.e-a.currentTime);sk.disabled=len<2;sk.min=w.s;sk.max=w.e;if(document.activeElement!==sk)sk.value=Math.min(w.e,Math.max(w.s,a.currentTime));
  ed.hidden=!(beh>3||(!on&&ld));t.textContent=len<2?"live":(beh>3?"−"+bnpFmt(beh)+" behind":"at live edge")+" · "+bnpFmt(len)+" window";sk.setAttribute("aria-valuetext",beh>3?bnpFmt(beh)+" behind live":"at live edge");
  sk.title=w.mode=="dvr"?"This stream has a rewind (DVR) window":w.mode=="buffer"?"Live stream with no server rewind: you can rewind and fast-forward within what your browser has buffered since you pressed Play":"This live stream can't be rewound in this browser"}
 const s=q(".bnp-st");s.classList.toggle("bad",!!(a&&a._err));s.textContent=a&&a._err?"⚠ "+a._err+" — try again, or use the open-source link below.":(a&&a._st)||(w&&w.live&&w.mode=="none"&&on?"Live only: this browser can't rewind this stream.":"")})}
function bnpSyncAll(){Object.keys(BNP.el).forEach(bnpSync)}
document.addEventListener("click",e=>{const u=e.target.closest(".bnp");if(!u)return;const b=e.target.closest("button");if(!b)return;e.preventDefault();e.stopPropagation();const pid=u.dataset.pid,a=BNP.el[pid];
 if(b.classList.contains("bnp-play")){if(a&&!a.paused)a.pause();else if(a&&a._loaded){bnpStopAll(a);a.play().catch(()=>{})}else bnpPlay(pid)}
 else if(b.classList.contains("bnp-stop"))bnpStop(pid);
 else if(b.classList.contains("bnp-mute")){const m=a||bnpMedia(pid,u.dataset.src);m.muted=!m.muted;if(!m.muted&&m.volume==0)m.volume=.5;bnpSync(pid)}
 else if(b.classList.contains("bnp-edge")&&a){const w=bnpWin(a);if(w&&w.mode=="dvr"){a.currentTime=a._hls&&a._hls.liveSyncPosition||w.e-1;a.play().catch(()=>{})}
  else if(w&&w.mode=="buffer"&&!a.paused&&w.e-a.currentTime>3)a.currentTime=Math.max(w.s,w.e-1);else{bnpStop(pid);bnpPlay(pid)}}},true);
document.addEventListener("input",e=>{const u=e.target.closest&&e.target.closest(".bnp");if(!u)return;const pid=u.dataset.pid,a=BNP.el[pid]||bnpMedia(pid,u.dataset.src),el=e.target;
 if(el.classList.contains("bnp-vol")){a.volume=+el.value;a.muted=+el.value==0;BNP.vol=+el.value;localStorage.setItem("bnp_vol",el.value);Object.values(BNP.el).forEach(m=>{if(m!==a)m.volume=BNP.vol})}
 else if(el.classList.contains("bnp-seek")&&a._loaded){try{a.currentTime=+el.value}catch(x){}}bnpSync(pid)});
document.addEventListener("play",e=>{if(e.target instanceof HTMLMediaElement)bnpStopAll(e.target)},true);
document.addEventListener("load",e=>{const f=e.target;if(f&&f.tagName=="IFRAME"&&/youtube/.test(f.src)&&/enablejsapi=1/.test(f.src))try{f.contentWindow.postMessage(JSON.stringify({event:"listening",id:"bnp",channel:"widget"}),"*")}catch(x){}},true);
window.addEventListener("message",e=>{if(!/^https:\/\/www\.youtube(-nocookie)?\.com$/.test(e.origin))return;let d=e.data;try{if(typeof d=="string")d=JSON.parse(d)}catch(x){return}
 if(!(d&&d.info&&d.info.playerState===1))return;Object.keys(BNP.el).forEach(k=>{if(BNP.el[k]._loaded)bnpStop(k)});document.querySelectorAll("audio,video").forEach(m=>{if(!m.paused)m.pause()});
 document.querySelectorAll('iframe[src*="youtube"]').forEach(f=>{if(f.contentWindow!==e.source)try{f.contentWindow.postMessage(JSON.stringify({event:"command",func:"pauseVideo",args:[]}),"*")}catch(x){}})});
window.bnMedia={stopAll:()=>bnpStopAll(null)};
// ---- Live stations (t251): official, keyless, publisher-published streams; player-only (not in the transcription list). Tested inline in Chrome 2026-10-31. ----
const BC_STATIONS=[
 {id:"npr",n:"NPR Program Stream",reg:"United States",lang:"English",cat:"Public radio news",fmt:"MP3",u:"https://npr-ice.streamguys1.com/live.mp3",pg:"https://www.npr.org/",fund:"Public broadcaster"},
 {id:"bbcws",n:"BBC World Service",reg:"United Kingdom · global",lang:"English",cat:"International news",fmt:"MP3",u:"https://stream.live.vc.bbcmedia.co.uk/bbc_world_service",pg:"https://www.bbc.co.uk/sounds/play/live:bbc_world_service",fund:"Public broadcaster"},
 {id:"cbc1tor",n:"CBC Radio One — Toronto",reg:"Canada (Ontario)",lang:"English",cat:"Public radio news",fmt:"HLS (AAC)",u:"https://cbcradiolive.akamaized.net/hls/live/2041036/ES_R1ETR/master.m3u8",pg:"https://www.cbc.ca/listen/streams/r1_toronto.html",fund:"Public broadcaster"},
 {id:"rfien",n:"RFI English",reg:"France · Africa/global",lang:"English",cat:"International news",fmt:"MP3",u:"https://rfienanglais64k.ice.infomaniak.ch/rfienanglais-64.mp3",pg:"https://www.rfi.fr/en/",fund:"State-funded international broadcaster (France)"},
 {id:"rfifr",n:"RFI Monde",reg:"France · global",lang:"French",cat:"International news",fmt:"MP3",u:"https://rfimonde64k.ice.infomaniak.ch/rfimonde-64.mp3",pg:"https://www.rfi.fr/fr/",fund:"State-funded international broadcaster (France)"},
 {id:"aje",n:"Al Jazeera English (audio)",reg:"Qatar · global",lang:"English",cat:"International news",fmt:"HLS (AAC)",u:"https://live-hls-audio-web-aje.getaj.net/VOICE-AJE/index.m3u8",pg:"https://www.aljazeera.com/audio/live",fund:"Funded by the Government of Qatar"},
 {id:"abcnr",n:"ABC NewsRadio",reg:"Australia",lang:"English",cat:"Public radio news",fmt:"HLS (AAC)",u:"https://streaming.abc-cdn.net.au/audio/hls/rnnsw.m3u8",pg:"https://www.abc.net.au/listen/live/news",fund:"Public broadcaster"},
 {id:"rnz",n:"RNZ National",reg:"New Zealand",lang:"English",cat:"Public radio news",fmt:"MP3",u:"https://stream-ice.radionz.co.nz/national.mp3",pg:"https://www.rnz.co.nz/listen/audiohelp",fund:"Public broadcaster"},
 {id:"rnzp",n:"RNZ Pacific",reg:"New Zealand · Pacific",lang:"English",cat:"International news",fmt:"MP3",u:"https://stream-ice.radionz.co.nz/international.mp3",pg:"https://www.rnz.co.nz/international",fund:"Public broadcaster"},
 {id:"finfo",n:"franceinfo",reg:"France",lang:"French",cat:"Public radio news",fmt:"MP3",u:"https://icecast.radiofrance.fr/franceinfo-midfi.mp3",pg:"https://www.francetvinfo.fr/en-direct/radio.html",fund:"Public broadcaster"},
 {id:"dlf",n:"Deutschlandfunk",reg:"Germany",lang:"German",cat:"Public radio news",fmt:"MP3",u:"https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3",pg:"https://www.deutschlandfunk.de/",fund:"Public broadcaster"},
 {id:"nwr63",n:"NOAA Weather Radio KIH63 — Orlando (162.475 MHz)",reg:"Central Florida · covers Seminole County (SAME 012117)",lang:"English",cat:"Weather alerts",fmt:"link",pg:"https://www.broadcastify.com/listen/feed/45304",pg2:["NWS Melbourne NWR page","https://www.weather.gov/mlb/nwr"],why:"NOAA publishes no official web stream. This is a volunteer Broadcastify relay, and Broadcastify's terms forbid embedding or re-streaming its audio, so it opens on Broadcastify. The feed may go quiet overnight unless severe weather is near."},
 {id:"nwr26",n:"NOAA Weather Radio KIH26 — Daytona Beach (162.400 MHz)",reg:"East Central Florida · covers Seminole County (SAME 012117)",lang:"English",cat:"Weather alerts",fmt:"link",pg:"https://www.broadcastify.com/listen/feed/47344",pg2:["NWS Melbourne NWR page","https://www.weather.gov/mlb/nwr"],why:"Same reason as KIH63: there's no official NOAA stream, and Broadcastify doesn't allow embedding."},
 {id:"voa",n:"Voice of America",reg:"United States · global",lang:"English",cat:"International news",fmt:"link",pg:"https://www.voanews.com/live/audio/92",fund:"U.S. government-funded international broadcaster",why:"VOA's official live-audio page says \"No live streaming currently available\"."},
 {id:"dw",n:"Deutsche Welle (English)",reg:"Germany · global",lang:"English",cat:"International news",fmt:"link",pg:"https://www.dw.com/en/live-tv/channel-english",fund:"State-funded international broadcaster (Germany)",why:"DW no longer runs an English live radio stream; it offers live TV (video) and on-demand audio on its own site."},
 {id:"nhk",n:"NHK World-Japan Radio",reg:"Japan · global",lang:"English (scheduled)",cat:"International news",fmt:"link",pg:"https://www3.nhk.or.jp/nhkworld/en/shows/audio/",fund:"Public broadcaster",why:"NHK's English live-radio page now goes to on-demand audio, and its radio HLS segments return Access Denied outside NHK's own player."},
 {id:"rci",n:"Radio Canada International",reg:"Canada · global",lang:"English/French + 5 more",cat:"International news",fmt:"link",pg:"https://ici.radio-canada.ca/rci/en",fund:"Public broadcaster",why:"RCI has had no live radio stream since 2012; it publishes web articles and podcasts."},
 {id:"cgtn",n:"CGTN",reg:"China · global",lang:"English",cat:"International news",fmt:"link",pg:"https://www.cgtn.com/tv",fund:"Chinese state media",why:"No official, publisher-published audio stream found; live TV is on CGTN's own site."},
];
function bcStations(){const el=$("bc_stations");if(!el||el.dataset.done)return;el.dataset.done=1;const inl=BC_STATIONS.filter(s=>s.u),lk=BC_STATIONS.filter(s=>!s.u);
 const tags=s=>`<div><span class=tg>${esc(s.cat)}</span><span class=tg>${esc(s.reg)}</span><span class=tg>${esc(s.lang)}</span><span class=tg>${esc(s.fmt)}</span>${s.fund?`<span class="tg${/state|government/i.test(s.fund)?" fund":""}">${esc(s.fund)}</span>`:""}</div>`;
 el.innerHTML=`<details open><summary>Live stations (${inl.length} play here · ${lk.length} open on the source site)</summary><div class=meta>Official streams published by each broadcaster: free, no key or account. They're for listening only and aren't transcribed or scored. One plays at a time.</div>
 <div class=bcs-grid>${inl.map(s=>{const pid="st_"+s.id;const a=bnpMedia(pid,s.u);a._name=s.n;return `<div class=bcs><b>${esc(s.n)}</b>${tags(s)}${bnpHtml(pid,s.u,s.n)}<div class=meta>${/HLS/.test(s.fmt)?"HLS live window: the scrubber can rewind within the stream's own window.":"Icecast MP3: rewind only within what your browser has buffered."} <a href="${esc(safeUrl(s.pg))}" target=_blank rel="noopener noreferrer">Open source ↗</a></div></div>`}).join("")}
 ${lk.map(s=>`<div class="bcs lnk"><b>${esc(s.n)}</b>${tags(s)}<div class=meta>Why it's a link: ${esc(s.why)}</div><div><a class=go href="${esc(safeUrl(s.pg))}" target=_blank rel="noopener noreferrer">Open on source site ↗</a>${s.pg2?` <a href="${esc(safeUrl(s.pg2[1]))}" target=_blank rel="noopener noreferrer">${esc(s.pg2[0])} ↗</a>`:""}</div></div>`).join("")}</div></details>`;bnpSyncAll()}
function bcNow(){const n=$("bc_now");if(!n)return;const pid=Object.keys(BNP.el).find(k=>BNP.el[k]._loaded);const inList=pid&&document.querySelector(`#bc_clips .bnp[data-pid="${CSS.escape(pid)}"],#bc_stations .bnp[data-pid="${CSS.escape(pid)}"]`);
 if(!pid||inList){n.innerHTML="";bnpSyncAll();return}if(!n.querySelector(`.bnp[data-pid="${CSS.escape(pid)}"]`)){const a=BNP.el[pid];n.innerHTML=`<div class=meta>Now playing (no longer in the filtered list):</div>`+bnpHtml(pid,a._src,a._name||"broadcast")}bnpSyncAll()}
async function bcKwPost(body){const r=await fetch("api/broadcast_keywords",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const j=await r.json();
 $("bc_kmsg").innerHTML=r.ok?`<span class=ok>✓ ${esc(j.action=="add"?"added":"removed")} “${esc(j.word)}”</span>`:`<span class=bad>✗ ${esc(j.error||r.status)}</span>`;if(r.ok)bcLoad()}
$("bc_kw").onclick=e=>{const ch=e.target.closest(".kwchip");if(!ch)return;if(e.target.dataset.del){if(confirm(`Remove keyword “${ch.dataset.w}”?`))bcKwPost({action:"remove",category:ch.dataset.c,word:ch.dataset.w});return}
 const w=ch.dataset.w.toLowerCase();bcKw=bcKw==w?"":w;bcLoad()};
$("bc_add").onclick=()=>{const w=$("bc_new").value.trim();if(!w)return;bcKwPost({action:"add",category:$("bc_cat").value,word:w});$("bc_new").value=""};
$("bc_src").onchange=bcLoad;$("bc_win").onchange=bcLoad;
setInterval(()=>{if($("tab-bcast").style.display!="none")bcLoad()},60000);
// ---- The Thread: conspiracy-board graph view of Story Arcs (plain JS + SVG, no external libraries) ----
const TH={nodes:[],edges:[],pos:{},sel:null,view:"board",pepe:false,k:1,tx:0,ty:0,alpha:0,raf:0,drag:null,t0:performance.now()};
const thNS="http://www.w3.org/2000/svg",thEl=(t,a)=>{const e=document.createElementNS(thNS,t);for(const k in a)e.setAttribute(k,a[k]);return e};
const TH_NOTES=["IT'S ALL CONNECTED","coincidence? …","follow the oil","who benefits??","check the timestamps!!","they don't want you to see this","3 sources = a pattern","not a drill (probably)"];
const TH_PEPE=["PEPE SILVIA","who is CAROL in HR??","there IS no Pepe!!","I've been in the mailroom for DAYS","BARNEY'S DEAD?!"];
function thPick(){const a=ARCS?ARCS.arcs.slice():[];a.sort((x,y)=>y.severity-x.severity||(y.latest>x.latest?1:-1));let top=a.slice(0,80);
 const ids=new Set(top.map(x=>x.id));let edges=[];top.forEach(x=>(x.connections||[]).forEach(c=>{if(ids.has(c.arc)&&x.id<c.arc)edges.push({a:x.id,b:c.arc,s:c.strength,sh:c.shared,ta:x.title,tb:c.title})}));
 if($("th_isol").checked){const lk=new Set();edges.forEach(e=>{lk.add(e.a);lk.add(e.b)});top=top.filter(x=>lk.has(x.id))}return{top,edges}}
function thBuild(){if(!ARCS)return;const {top,edges}=thPick();const W=$("th_board").clientWidth||1200,H=$("th_board").clientHeight||760;
 TH.nodes=top.map(a=>{const p=TH.pos[a.id]||{x:W/2+(Math.random()-.5)*W*.5,y:H/2+(Math.random()-.5)*H*.5,vx:0,vy:0};TH.pos[a.id]=p;
  return{id:a.id,a,p,r:Math.min(24,6+Math.sqrt(a.n_sources)*2.6),seed:Math.random()*6.28}});
 const by={};TH.nodes.forEach(n=>by[n.id]=n);TH.edges=edges.filter(e=>by[e.a]&&by[e.b]).map(e=>({...e,A:by[e.a],B:by[e.b],seed:Math.random()*6.28}));TH.by=by;
 const eg=$("th_edges"),ng=$("th_nodes");eg.innerHTML="";ng.innerHTML="";
 TH.edges.forEach(e=>{e.el=thEl("path",{class:"str","stroke-width":(1.2+e.s*9).toFixed(1)});e.hit=thEl("path",{class:"hit"});
  const tip=`🧵 <b>${esc(e.ta.slice(0,60))}</b><br>↔ <b>${esc(e.tb.slice(0,60))}</b><br>shared: <span style="color:#ff6b6b">${e.sh.map(esc).join(", ")}</span> · strength ${e.s}`;
  e.hit.addEventListener("mousemove",ev=>thTip(ev,tip));e.hit.addEventListener("mouseleave",()=>{$("th_tip").style.display="none";e.el.classList.remove("hl")});e.hit.addEventListener("mouseenter",()=>e.el.classList.add("hl"));
  eg.appendChild(e.el);eg.appendChild(e.hit)});
 const showLab=new Set(TH.nodes.slice().sort((x,y)=>y.a.severity-x.a.severity||y.a.n_sources-x.a.n_sources).slice(0,28).map(n=>n.id));TH.showLab=showLab;
 TH.nodes.forEach(n=>{const g=thEl("g",{class:"nd"});const sv=n.a.severity;
  if(sv>=5)g.appendChild(thEl("circle",{class:"pulse",r:n.r,cx:0,cy:0}));
  g.appendChild(thEl("ellipse",{cx:2,cy:n.r*.55,rx:n.r*.8,ry:n.r*.35,fill:"rgba(0,0,0,.45)"}));
  const c=thEl("circle",{class:"pinc",r:n.r,fill:"url(#th_pin)",opacity:(.55+Math.min(sv,8)*.06).toFixed(2)});if(sv>=6)c.setAttribute("filter","url(#th_glow)");g.appendChild(c);
  g.appendChild(thEl("circle",{r:Math.max(2,n.r*.28),cx:-n.r*.3,cy:-n.r*.3,fill:"rgba(255,255,255,.75)"}));
  const t=thEl("text",{x:n.r+5,y:4});t.textContent=(n.a.title.length>38?n.a.title.slice(0,37)+"…":n.a.title);if(!showLab.has(n.id))t.style.display="none";g.appendChild(t);n.lab=t;
  g.addEventListener("mouseenter",ev=>{t.style.display="";thTip(ev,`<b>[${sv}/10]</b> ${esc(n.a.title)}<br><span class=meta>${n.a.n_updates} updates · ${n.a.n_sources} sources · latest ${esc(n.a.latest_et)}</span>`)});
  g.addEventListener("mousemove",ev=>thTip(ev));g.addEventListener("mouseleave",()=>{$("th_tip").style.display="none";if(!showLab.has(n.id)&&TH.sel!==n.id)t.style.display="none"});
  g.addEventListener("pointerdown",ev=>{ev.stopPropagation();TH.drag={n,moved:false,sx:ev.clientX,sy:ev.clientY};$("th_svg").setPointerCapture(ev.pointerId)});
  n.g=g;ng.appendChild(g)});
 const mk=$("th_marks");mk.innerHTML="";TH.top=null;const top1=TH.nodes.slice().sort((x,y)=>y.a.severity-x.a.severity||y.a.n_sources-x.a.n_sources)[0];
 if(top1){TH.top=top1;TH.mark=thEl("path",{class:"marker"});TH.mtxt=thEl("text",{class:"mtext"});TH.mtxt.textContent="← THIS!!";mk.appendChild(TH.mark);mk.appendChild(TH.mtxt)}
 if(TH.sel&&by[TH.sel])by[TH.sel].g.classList.add("sel");
 if(!TH.notesDone){thNotes();TH.notesDone=true}if(!TH.userMoved)TH.fitPending=true;TH.alpha=Math.max(TH.alpha,.9);thKick()}
function thFit(){const N=TH.nodes;if(!N.length)return;const W=$("th_board").clientWidth,H=$("th_board").clientHeight,pw=$("th_panel").style.display=="block"?Math.min(410,W*.92):0;let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;N.forEach(n=>{x0=Math.min(x0,n.p.x-n.r);y0=Math.min(y0,n.p.y-n.r);x1=Math.max(x1,n.p.x+n.r+150);y1=Math.max(y1,n.p.y+n.r+10)});const aw=W-pw-40,ah=H-60,k=Math.max(.35,Math.min(1.6,aw/(x1-x0),ah/(y1-y0)));TH.k=k;TH.tx=20+(aw-(x1-x0)*k)/2-x0*k;TH.ty=30+(ah-(y1-y0)*k)/2-y0*k;TH.fitPending=false;thDraw()}
function thNotes(){const W=$("th_board").clientWidth||1200,H=$("th_board").clientHeight||760;const list=TH.pepe?TH_PEPE.concat(TH_NOTES.slice(0,3)):TH_NOTES.slice().sort(()=>Math.random()-.5).slice(0,4);
 const spots=[[14,14],[W*.42,10],[W-230,18],[18,H-110],[W*.55,H-80],[W-240,H-150],[W*.25,H*.42],[W*.7,H*.4]];
 $("th_notes").innerHTML=list.slice(0,TH.pepe?8:4).map((t,i)=>`<div class="th-note ${["","pink","blue"][i%3]}" style="left:${Math.max(6,spots[i][0])}px;top:${spots[i][1]}px;transform:rotate(${(Math.random()*14-7).toFixed(1)}deg)">${esc(t)}</div>`).join("")}
function thTip(ev,h){const tp=$("th_tip"),b=$("th_board").getBoundingClientRect();if(h)tp.innerHTML=h;tp.style.display="block";tp.style.left=Math.max(0,Math.min(b.width-330,ev.clientX-b.left+14))+"px";tp.style.top=(ev.clientY-b.top+14)+"px"}
function thStep(){const N=TH.nodes,E=TH.edges,W=$("th_board").clientWidth||1200,H=$("th_board").clientHeight||760,al=TH.alpha;
 for(let i=0;i<N.length;i++){const a=N[i].p;for(let j=i+1;j<N.length;j++){const b=N[j].p;let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01;if(d2>32000)continue;const f=900/d2*al;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f}}
 E.forEach(e=>{const a=e.A.p,b=e.B.p,dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,f=(d-110)/d*.03*al*(.5+e.s);a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f});
 N.forEach(n=>{const p=n.p;p.vx+=(W*.42-p.x)*.012*al;p.vy+=(H/2-p.y)*.016*al;if(TH.drag&&TH.drag.n===n)return;p.vx*=.82;p.vy*=.82;p.x+=p.vx;p.y+=p.vy});TH.alpha*=.985}
function thDraw(){const t=(performance.now()-TH.t0)/1000,pp=TH.pepe;
 TH.nodes.forEach(n=>{const jx=pp?Math.sin(t*9+n.seed)*2.5:0,jy=pp?Math.cos(t*11+n.seed)*2.5:0;n.g.setAttribute("transform",`translate(${(n.p.x+jx).toFixed(1)},${(n.p.y+jy).toFixed(1)})`)});
 TH.edges.forEach(e=>{const a=e.A.p,b=e.B.p,mx=(a.x+b.x)/2,my=(a.y+b.y)/2,d=Math.hypot(b.x-a.x,b.y-a.y),wob=pp?Math.sin(t*7+e.seed)*(14+d*.08):Math.sin(t*.8+e.seed)*2,sag=10+d*.12;
  const dd=redStringD(a.x,a.y,b.x,b.y,sag,wob);e.el.setAttribute("d",dd);e.hit.setAttribute("d",dd)});
 if(TH.top&&TH.mark){const p=TH.top.p,r=TH.top.r+16;let d="";for(let i=0;i<=26;i++){const an=i/24*6.6-0.4,rr=r*(1+.08*Math.sin(i*1.7));d+=(i?"L":"M")+(p.x+Math.cos(an)*rr*1.35).toFixed(1)+","+(p.y+Math.sin(an)*rr).toFixed(1)}TH.mark.setAttribute("d",d);TH.mtxt.setAttribute("x",p.x+r*1.4+6);TH.mtxt.setAttribute("y",p.y-r*.6)}
 $("th_vp").setAttribute("transform",`translate(${TH.tx},${TH.ty}) scale(${TH.k})`)}
function thKick(){if(TH.raf)return;const loop=()=>{TH.raf=0;if(TH.view!="board"||$("tab-thread").style.display=="none")return;if(TH.alpha>.02||TH.drag)thStep();if(TH.fitPending&&TH.alpha<.08&&!TH.userMoved)thFit();
 if(TH.alpha>.02||TH.drag||TH.pepe||(performance.now()-(TH.lastDraw||0))>120){thDraw();TH.lastDraw=performance.now()}TH.raf=requestAnimationFrame(loop)};TH.raf=requestAnimationFrame(loop)}
function thPanel(id){const a=ARCS&&ARCS.arcs.find(x=>x.id==id);if(!a)return;TH.sel=id;TH.nodes.forEach(n=>{n.g.classList.toggle("sel",n.id==id)});
 const con=(a.connections||[]).map(c=>`<span class=chip data-th="${esc(c.arc)}">${esc(c.title.slice(0,52))}${c.title.length>52?"…":""} <i>${c.shared.map(esc).join(", ")}</i></span>`).join("")||"<span class=meta>none found</span>";
 const P=$("th_panel");P.style.display="block";P.innerHTML=`<span class=x title=close>✕</span><h3><span class="sc ${arcLv(a.severity)}">${a.severity}</span>${esc(a.title)}</h3>
 <div class=meta>${esc(a.category)} · started ${esc(a.start_et)} · latest ${esc(a.latest_et)}<br>${a.n_updates} update${a.n_updates==1?"":"s"} · ${a.n_sources} source${a.n_sources==1?"":"s"}${a.confirmed?"":' <span class=unc>unconfirmed</span>'} · peak ${a.severity}/10 · latest ${a.latest_rank}/10</div>
 <div class=meta style="margin-top:6px">🧵 Connected to: ${con}</div><ul class=tl>${a.updates.slice().reverse().map(arcUpd).join("")}</ul>${a.updates_truncated?`<div class=meta>+${a.updates_truncated} older updates not shown</div>`:""}`}
function thFocus(id){const n=TH.by&&TH.by[id];if(!n){thPanel(id);return}TH.userMoved=true;const W=$("th_board").clientWidth,H=$("th_board").clientHeight;TH.tx=W*.33-n.p.x*TH.k;TH.ty=H/2-n.p.y*TH.k;n.lab.style.display="";thPanel(id);thDraw()}
$("th_panel").onclick=e=>{if(e.target.classList.contains("x")){$("th_panel").style.display="none";TH.sel=null;TH.nodes.forEach(n=>n.g.classList.remove("sel"));return}const c=e.target.closest("[data-th]");if(c)thFocus(c.dataset.th)};
(()=>{const sv=$("th_svg");let pan=null;
 sv.addEventListener("pointerdown",ev=>{if(TH.drag)return;pan={x:ev.clientX,y:ev.clientY,tx:TH.tx,ty:TH.ty};sv.classList.add("drag");sv.setPointerCapture(ev.pointerId)});
 sv.addEventListener("pointermove",ev=>{if(TH.drag){const d=TH.drag;const b=sv.getBoundingClientRect();d.n.p.x=(ev.clientX-b.left-TH.tx)/TH.k;d.n.p.y=(ev.clientY-b.top-TH.ty)/TH.k;d.n.p.vx=d.n.p.vy=0;if(Math.hypot(ev.clientX-d.sx,ev.clientY-d.sy)>4)d.moved=true;TH.alpha=Math.max(TH.alpha,.3);thKick()}
  else if(pan){TH.userMoved=true;TH.tx=pan.tx+ev.clientX-pan.x;TH.ty=pan.ty+ev.clientY-pan.y;thDraw()}});
 const up=()=>{if(TH.drag){if(!TH.drag.moved)thPanel(TH.drag.n.id);TH.drag=null}pan=null;sv.classList.remove("drag")};sv.addEventListener("pointerup",up);sv.addEventListener("pointercancel",up);
 sv.addEventListener("wheel",ev=>{ev.preventDefault();const b=sv.getBoundingClientRect(),mx=ev.clientX-b.left,my=ev.clientY-b.top,k2=Math.min(4,Math.max(.3,TH.k*Math.exp(-ev.deltaY*.0015)));
  TH.userMoved=true;TH.tx=mx-(mx-TH.tx)*k2/TH.k;TH.ty=my-(my-TH.ty)*k2/TH.k;TH.k=k2;thDraw()},{passive:false})})();
function thSetView(v){TH.view=v;$("th_vboard").classList.toggle("on",v=="board");$("th_vlist").classList.toggle("on",v=="list");$("th_board").style.display=v=="board"?"":"none";$("th_listwrap").style.display=v=="list"?"":"none";
 ["th_isol_l","th_reset","th_pepe"].forEach(i=>$(i).style.display=v=="board"?"":"none");$("arcs_multi").parentElement.style.display=v=="list"?"":"none";localStorage.setItem("th_view",v);if(v=="board"){thBuild();thKick()}}
$("th_vboard").onclick=()=>thSetView("board");$("th_vlist").onclick=()=>thSetView("list");
$("th_isol").onchange=()=>{localStorage.setItem("th_isol",$("th_isol").checked?"1":"0");thBuild()};
$("th_reset").onclick=()=>{TH.k=1;TH.tx=TH.ty=0;TH.pos={};TH.userMoved=false;thBuild()};
$("th_pepe").onclick=()=>{TH.pepe=!TH.pepe;$("th_pepe").classList.toggle("on",TH.pepe);$("th_pepe_l").textContent=TH.pepe?"PEPE SILVIA MODE (on)":"Pepe Silvia mode";thNotes();TH.alpha=Math.max(TH.alpha,.4);thKick()};
$("th_isol").checked=localStorage.getItem("th_isol")=="1";
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="thread")setTimeout(()=>thSetView(localStorage.getItem("th_view")||"board"),30)});
const thOrigRender=arcsRender;arcsRender=function(){thOrigRender();if(TH.view=="board"&&$("tab-thread").style.display!="none")thBuild();if(TH.sel&&$("th_panel").style.display!="none")thPanel(TH.sel)};
// ---- Local Resources ----
let RS=null,rsOpen=new Set(JSON.parse(localStorage.getItem("rs_open")||'["police","fire","hospital"]')),rsLoaded=false;
function rsItem(i){const ph=i.phone&&i.phone.tel?`<a href="tel:${esc(i.phone.tel)}">📞 ${esc(i.phone.display)}</a>`:'<span class=meta>no phone listed</span>';
 return `<div class="card l" style="border-color:var(--bn-line,#2c3440)"><b>${esc(i.name)}</b> <span class=tag>${i.miles.toFixed(1)} mi</span>${i.er?' <span class=tag style="color:#ff7875;border-color:#ff7875">ER</span>':""}
 <div class=meta>${i.address?esc(i.address):"address not listed"}${i.hours?" · 🕒 "+esc(i.hours):""}${i.status?" · status: "+esc(i.status):""}</div>
 <div class=meta>${ph} · <a href="${esc(safeUrl(i.map))}" target=_blank rel="noopener noreferrer">🗺 map</a>${i.website?` · <a href="${esc(safeUrl(i.website))}" target=_blank rel="noopener noreferrer">website</a>`:""}${i.osm?` · <a href="${esc(safeUrl(i.osm))}" target=_blank rel="noopener noreferrer">OSM</a>`:""}</div></div>`}
function rsRender(){const R=RS;$("rs_meta").textContent=` ${R.geocode.display.slice(0,90)} · within ${R.radius_miles} mi (${R.radius_km} km)`;
 $("rs_fema").innerHTML=R.fema_open_shelters.length?`<details open class=pn style="margin:8px 0;background:var(--bn-raised,#181d23)"><summary><b>🏠 FEMA open shelters nearby (${R.fema_open_shelters.length})</b></summary>${R.fema_open_shelters.map(rsItem).join("")}</details>`:
  `<div class=meta style="margin:6px 0">🏠 FEMA open shelters: ${R.fema_error?"feed unavailable ("+esc(R.fema_error)+")":"none open near this location right now (FEMA National Shelter System)"}.</div>`;
 $("rs_cats").innerHTML=R.categories.map(c=>`<details class=pn style="margin:8px 0;background:var(--bn-surface,#14181d)" data-c="${c.id}"${rsOpen.has(c.id)?" open":""}><summary style="cursor:pointer;font-size:15px"><b>${c.emoji} ${esc(c.label)}</b> <span class=meta>(${c.total} found${c.total>c.items.length?", nearest "+c.items.length+" shown":""})</span></summary>
  ${c.note?`<div class=meta style="margin:4px 0">ℹ️ ${esc(c.note)}${c.link?` <a href="${esc(safeUrl(c.link))}" target=_blank rel="noopener noreferrer">FDEM county directory</a>`:""}</div>`:""}${c.items.map(rsItem).join("")||"<div class=meta>None mapped in OpenStreetMap within this radius.</div>"}</details>`).join("");
 $("rs_src").innerHTML=`Sources: ${esc(R.sources.geocoder)} · ${esc(R.sources.pois)} · ${esc(R.sources.shelters)} · ${esc(R.attribution)} · No paid API keys used${R.google_places_key_found?" (a Google Places key variable exists on the box but is not used)":" (no Google Places key on the box)"}.`}
async function rsSearch(q){q=(q||"").trim();if(!q){$("rs_meta").textContent=" Enter an address, city or postcode, or pick a location (nothing is pre-selected).";return}$("rs_q").value=q;localStorage.setItem("rs_last",q);$("rs_meta").textContent="";const my=window.rsSeq=(window.rsSeq||0)+1;
 const ph=$("rs_prog"),BP=window.BNProgress;let p=null;const pt=setTimeout(()=>{if(my!==window.rsSeq)return;if(BP){p=BP.create(ph,{label:"Finding "+q.slice(0,60)+"…",name:"Local resources search"});p.stage(null,0.04).ease(0.9,12000)}else $("rs_meta").textContent=" Searching…"},150);   // t480: cache hits finish before the bar appears
 try{const ac=new AbortController(),at=setTimeout(()=>ac.abort(),45000);let r;try{r=await fetch("api/resources?q="+encodeURIComponent(q),{cache:"no-store",signal:ac.signal,bnNoRetry:true})}catch(x){throw ac.signal.aborted?"the lookup took too long":x}finally{clearTimeout(at)}if(my!==window.rsSeq){clearTimeout(pt);return}if(p)p.stage("Sorting nearby places…",0.94);const j=await r.json();if(!r.ok)throw j.error||r.status;clearTimeout(pt);RS=j;rsRender();if(p)p.done("Done")}
 catch(e){clearTimeout(pt);if(my!==window.rsSeq)return;if(!p&&BP)p=BP.create(ph,{label:"Finding "+q.slice(0,60)+"…"});if(p)p.fail("Couldn't load resources: "+e,()=>rsSearch(q));else $("rs_meta").innerHTML=' <span class=bad>'+esc(e)+'</span>'}}
$("rs_form").onsubmit=e=>{e.preventDefault();rsSearch($("rs_q").value)};
$("rs_form").addEventListener("click",e=>{const b=e.target.closest("button[data-q]");if(b)rsSearch(b.dataset.q)});
$("rs_all").onclick=()=>{const ds=[...document.querySelectorAll("#rs_cats details")];const open=!ds.every(d=>d.open);ds.forEach(d=>d.open=open)};
$("rs_cats").addEventListener("toggle",e=>{const d=e.target;if(!d.dataset||!d.dataset.c)return;d.open?rsOpen.add(d.dataset.c):rsOpen.delete(d.dataset.c);localStorage.setItem("rs_open",JSON.stringify([...rsOpen]))},true);
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="res"&&!rsLoaded){rsLoaded=true;rsSearch(localStorage.getItem("rs_last")||(window.BNGeo&&BNGeo.get()?(BNGeo.get().resources_q||BNGeo.get().label):""))}});
// ---- static guide tabs (Bushcraft, Medical): content lives in /guides/*.html, loaded once ----
const GD={css:false,loaded:{}};
async function gdLoad(tab,file){if(GD.loaded[tab])return;GD.loaded[tab]=true;const box=$("gd_"+tab);
 try{if(!GD.css){const c=await (await fetch("guides/guide.css")).text();const st=document.createElement("style");st.textContent=c;document.head.appendChild(st);GD.css=true}
  const r=await fetch("guides/"+file);if(!r.ok)throw r.status;box.innerHTML=await r.text();
  if(innerWidth<900)box.querySelectorAll(".toc details").forEach(d=>d.open=false)}catch(e){GD.loaded[tab]=false;box.innerHTML='<div class="warn">Guide failed to load: '+esc(e)+'</div>'}}
document.addEventListener("click",e=>{const b=e.target.closest("[data-print]");if(!b)return;const m=b.closest("main");document.body.classList.add("gd-print");m.classList.add("gd-printing");
 window.print();setTimeout(()=>{document.body.classList.remove("gd-print");m.classList.remove("gd-printing")},500)});
document.addEventListener("click",e=>{const a=e.target.closest(".gd .toc a");if(!a)return;const t=document.querySelector(a.getAttribute("href"));if(t){e.preventDefault();t.scrollIntoView({behavior:"smooth",block:"start"});if(innerWidth<900)a.closest("details").open=false}});
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;if(b.dataset.tab=="bush")gdLoad("bush","bushcraft.html");if(b.dataset.tab=="med")gdLoad("med","medical.html")});
// ---- Maps tab: printable PDF downloads (priority) + interactive Leaflet map (secondary) ----
const MP={map:null,cl:null,pois:null,cats:null,on:new Set(["hospital","clinic","fire","ems","police","em","shelter","water"]),evac:null,pin:null};
const mpSize=b=>b>=1e6?(b/1e6).toFixed(1)+" MB":Math.max(1,Math.round(b/1e3))+" KB";
async function mpList(){try{const j=await (await fetch("api/maps/list",{cache:"no-store"})).json();
 const card=m=>`<div class="mp-card"><b>${esc(m.title)}</b><div class="meta">${esc(m.desc||"")}</div><div>${(m.tags||[]).map(t=>`<span class=pill>${esc(t)}</span>`).join("")}<span class=pill>${m.available?mpSize(m.bytes):"not built yet"}</span></div>
  ${m.available?`<a class="dl" href="maps/${encodeURIComponent(m.file)}" download>⬇ Download PDF (${mpSize(m.bytes)})</a>`:`<span class=meta>Not available yet</span>`}${m.source_url?`<a class="dl sec" href="${esc(safeUrl(m.source_url))}" target=_blank rel="noopener noreferrer">Official USGS copy ↗</a>`:""}</div>`;
 $("mp_list").innerHTML=j.maps.filter(m=>m.group!="topo").map(card).join("")||"<div class=meta>No maps built yet.</div>";
 $("mp_topo").innerHTML=j.maps.filter(m=>m.group=="topo").map(card).join("")||"<div class=meta>None.</div>";
 $("mp_attr").textContent=(j.attribution||"")+(j.built_et?" · built "+j.built_et:"")}catch(e){$("mp_list").innerHTML='<div class=warn>Map list unavailable: '+esc(e)+'</div>'}}
function mpDraw(){if(!MP.cl||!MP.pois)return;MP.cl.clearLayers();const ms=[];
 MP.pois.pois.forEach(p=>{if(!MP.on.has(p[0]))return;const c=MP.cats[p[0]];
  ms.push(L.marker([p[1],p[2]],{icon:L.divIcon({className:"mp-ic",html:c.emoji,iconSize:[22,22]}),title:p[3]||c.label}).bindPopup(`<b>${esc(p[3]||c.label)}</b><br>${esc(c.label)}${p[4]?"<br>"+esc(p[4]):""}${p[5]?`<br><a href="tel:${esc(p[5].replace(/[^0-9+]/g,""))}">${esc(p[5])}</a>`:""}<br><a href="https://www.openstreetmap.org/${esc(p[6])}" target=_blank rel="noopener noreferrer">OSM ↗</a>`))});
 MP.cl.addLayers(ms);$("mp_msg").textContent=`${ms.length.toLocaleString()} emergency points shown`}
async function mpInit(){if(MP.map){setTimeout(()=>MP.map.invalidateSize(),60);return}
 MP.map=L.map("mp_map",{maxZoom:19,minZoom:2,zoomSnap:.5,worldCopyJump:true});{const g=window.BNGeo&&BNGeo.get();g&&g.lat!=null?MP.map.setView([g.lat,g.lon],11):MP.map.setView([20,0],2)}
 bnBaseLayer(MP.map,{maxZoom:19});
 L.control.scale({imperial:true,metric:true}).addTo(MP.map);
 MP.cl=L.markerClusterGroup?L.markerClusterGroup({disableClusteringAtZoom:16,maxClusterRadius:50,chunkedLoading:true}):L.layerGroup();MP.cl.addTo(MP.map);
 try{const j=await (await fetch("api/maps/pois")).json();MP.pois=j;MP.cats=j.cats;
  $("mp_cats").innerHTML=Object.entries(j.cats).map(([k,c])=>`<label class=cb><input type=checkbox data-k="${k}" checked> ${c.emoji} ${esc(c.label)} <span class=meta>${j.pois.filter(p=>p[0]==k).length}</span></label>`).join("")+`<label class=cb><input type=checkbox id=mp_evac checked> <span style="color:#b36bff">┅</span> Evacuation routes (FDEM)</label>`;
  mpDraw()}catch(e){$("mp_msg").textContent="points unavailable: "+e}
 try{const g=await (await fetch("maps/evac_routes.json")).json();MP.evac=L.geoJSON(g,{style:{color:"#b36bff",weight:3,opacity:.85,dashArray:"6 4"},onEachFeature:(f,l)=>l.bindPopup("Evacuation route: "+esc(f.properties.NAME||"")+(f.properties.NAMELSAD?" · "+esc(f.properties.NAMELSAD)+" Co.":""))}).addTo(MP.map)}catch(e){}}
$("mp_cats").onchange=e=>{const k=e.target.dataset.k;if(k){e.target.checked?MP.on.add(k):MP.on.delete(k);mpDraw()}if(e.target.id=="mp_evac"&&MP.evac)e.target.checked?MP.evac.addTo(MP.map):MP.map.removeLayer(MP.evac)};
$("mp_form").onsubmit=async e=>{e.preventDefault();const q=$("mp_q").value.trim();if(q.length<3)return;$("mp_msg").textContent="";const mh=$("mp_prog")||(()=>{const d=document.createElement("div");d.id="mp_prog";$("mp_msg").after(d);return d})();   // t480 shared progress bar
 try{const j=await (window.BNProgress?BNProgress.run(mh,async()=>{const r=await fetch("api/maps/geocode?q="+encodeURIComponent(q));const j=await r.json();if(!r.ok)throw j.error||r.status;return j},{label:"Finding "+q.slice(0,60)+"…",name:"Map address search",fail:e=>"Couldn't find that place: "+e,retry:()=>$("mp_form").requestSubmit()}):fetch("api/maps/geocode?q="+encodeURIComponent(q)).then(r=>r.json()));
  if(MP.pin)MP.map.removeLayer(MP.pin);MP.pin=L.marker([j.lat,j.lon]).addTo(MP.map).bindPopup(esc(j.display)).openPopup();MP.map.setView([j.lat,j.lon],17);$("mp_msg").textContent=j.display}catch(err){if(!window.BNProgress)$("mp_msg").textContent=String(err)}};
$("mp_fl").onclick=()=>MP.map&&MP.map.setView([20,0],2);$("mp_home").onclick=()=>{if(!MP.map)return;const g=window.BNGeo&&BNGeo.get();if(g&&g.lat!=null)return MP.map.setView([g.lat,g.lon],12);if(g&&g.label){$("mp_q").value=g.label;$("mp_form").requestSubmit();return}$("mp_msg").textContent="Pick a location (Radio, Local Resources) or search above."};
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="maps"){mpList();mpInit()}if(b&&b.dataset.tab=="threat"){setTimeout(()=>S&&bnPaintMapCharts(),0)}});
// ---- Timeline slider: hourly histogram since the first scan + items/snapshots for the chosen window. Polls every 60 s (live push may also call tlRefresh). ----
const TL={hours:[],idx:0,live:true,play:0,ov:null,req:0};
const tlEt=t=>new Date(t).toLocaleString("en-US",{timeZone:"America/New_York",weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
async function bnJSON(u){const r=await fetch(u,{cache:"no-store"});const ct=r.headers.get("content-type")||"";if(!r.ok||ct.indexOf("json")<0)throw new Error("busy");return r.json()}
async function tlRefresh(){try{const j=await bnJSON("api/timeline");TL.ov=j;const by={};j.hours.forEach(h=>by[h.h]=h);
 const s=new Date(j.start);s.setUTCMinutes(0,0,0);const e=new Date(j.now);const H=[];for(let t=s.getTime();t<=e.getTime();t+=36e5){const k=new Date(t).toISOString().slice(0,13)+":00:00Z";H.push(by[k]||{h:k,n:0,high:0,max:0,main:0})}
 TL.hours=H;const r=$("tl_rng");r.max=H.length-1;if(TL.live)TL.idx=H.length-1;r.value=TL.idx;
 const mx=Math.max(1,...H.map(h=>Math.sqrt(h.n)));$("tl_hist").innerHTML=H.map((h,i)=>`<i data-i="${i}" class="${h.high?"h":""}" style="height:${Math.max(2,Math.round(44*Math.sqrt(h.n)/mx))}px" title="${esc(tlEt(h.h))}: ${h.n} item(s), ${h.high} high"></i>`).join("");
 const sn=j.snapshots;$("tl_meta").textContent=`· ${j.total.toLocaleString()} items since ${tlEt(j.start)} · ${sn.ok} source snapshots`;
 $("tl_snapinfo").textContent=`Snapshots: ${sn.ok} captured, ${sn.failed} unavailable · ${(sn.bytes/1e6).toFixed(1)} MB of ${(sn.cap_bytes/1073741824).toFixed(0)} GB cap · worker ${sn.worker_running?"running":"stopped"} · rule: ${sn.rule}. Each image has a black bar below the page with the headline, rank/score, sources, full source link and capture time (ET and UTC), and the same details embedded in the file.`;
 tlShow()}catch(e){$("tl_meta").textContent="· reloading the timeline…";clearTimeout(TL.rt);TL.rt=setTimeout(tlRefresh,15000)}}
async function tlShow(){if(!TL.hours.length)return;const w=+$("tl_win").value,i=TL.idx,end=new Date(new Date(TL.hours[i].h).getTime()+36e5),st=new Date(end.getTime()-w*36e5);
 $("tl_hist").querySelectorAll("i").forEach((b,k)=>b.classList.toggle("sel",k>i-w&&k<=i));$("tl_at").textContent=`${tlEt(st)} → ${tlEt(end)}`;$("tl_live").classList.toggle("on",TL.live);
 const q=++TL.req;try{const j=await bnJSON(`api/timeline/items?from=${st.toISOString().slice(0,19)}Z&to=${end.toISOString().slice(0,19)}Z`);if(q!=TL.req)return;
  let it=j.items;if($("tl_snaponly").checked)it=it.filter(x=>x.snapshot&&x.snapshot.file);if($("tl_main").checked)it=it.filter(x=>!x.watchlist);
  $("tl_cnt").textContent=` · ${it.length} item(s)${j.items.length>=400?" (first 400)":""}`;
  $("tl_items").innerHTML=it.map(x=>`<div class="tl-card ${lv(x.score)}" data-cid="${esc(x.cluster_id)}"><div class=meta>${esc(tlEt(x.first_seen))} · <span class="sc ${lv(x.score)}">${x.score}</span>rank ${x.rank}/10 ${x.watchlist?'<span class=wl>Watchlist</span>':""}</div>
   ${x.snapshot&&x.snapshot.file?`<a href="${esc(x.snapshot.file)}" target=_blank rel="noopener" title="Open full snapshot (metadata bar at the bottom)"><img loading=lazy src="${esc(x.snapshot.file)}" alt="Snapshot of the source page for: ${esc(x.title)}"></a>`:`<div class=noimg>${x.snapshot?"snapshot unavailable":(x.rank>=4||x.n_families>=2||x.eff_families>=2?"snapshot queued":"no snapshot (below rank 4, single source)")}</div>`}
   <b>${esc(x.title)}</b><div class=meta>${esc(x.category)}${x.location?" · "+esc(x.location):""} · ${x.n_families} source${x.n_families==1?"":"s"}</div>
   <div class=meta>${x.links.slice(0,3).map(l=>`<a href="${esc(safeUrl(l.url))}" target=_blank rel="noopener noreferrer">${esc(l.source)}</a>`).join(" · ")}</div></div>`).join("")||"<div class=meta>Nothing cataloged in this window.</div>";
  if(TL.live)$("tl_items").scrollLeft=$("tl_items").scrollWidth}catch(e){$("tl_cnt").textContent=" · error "+e}}
$("tl_rng").oninput=e=>{TL.idx=+e.target.value;TL.live=TL.idx==TL.hours.length-1;clearTimeout(TL.t);TL.t=setTimeout(tlShow,120);$("tl_hist").querySelectorAll("i").forEach((b,k)=>b.classList.toggle("sel",k==TL.idx))};
$("tl_hist").onclick=e=>{const i=e.target.dataset.i;if(i==null)return;TL.idx=+i;TL.live=TL.idx==TL.hours.length-1;$("tl_rng").value=i;tlShow()};
const tlStep=d=>{TL.idx=Math.max(0,Math.min(TL.hours.length-1,TL.idx+d));TL.live=TL.idx==TL.hours.length-1;$("tl_rng").value=TL.idx;tlShow()};
$("tl_prev").onclick=()=>tlStep(-(+$("tl_win").value));$("tl_next").onclick=()=>tlStep(+$("tl_win").value);
$("tl_live").onclick=()=>{TL.live=true;TL.idx=TL.hours.length-1;$("tl_rng").value=TL.idx;tlShow()};
$("tl_play").onclick=()=>{if(TL.play){clearInterval(TL.play);TL.play=0;$("tl_play").textContent="▶ Play";return}if(TL.idx>=TL.hours.length-1)TL.idx=0;$("tl_play").textContent="❚❚ Pause";
 TL.play=setInterval(()=>{if(TL.idx>=TL.hours.length-1){clearInterval(TL.play);TL.play=0;$("tl_play").textContent="▶ Play";return}tlStep(1)},1600)};
$("tl_win").onchange=tlShow;$("tl_snaponly").onchange=tlShow;$("tl_main").onchange=tlShow;
tlRefresh();setInterval(tlRefresh,60000);

// ---- Live Streams tab: curated channels, click-to-play youtube-nocookie embeds, live transcripts with shared keyword colors ----
const STR={d:null,kw:"",playing:new Set()};
async function stLoad(){try{const q=new URLSearchParams({region:$("st_reg").value,live_only:$("st_live").checked?"1":"0",hours:$("st_hrs").value,kw:STR.kw});
 const r=await fetch("api/streams?"+q,{cache:"no-store"});const d=await r.json();if(!r.ok)throw d.error||r.status;STR.d=d;stRender()}catch(e){$("st_meta").textContent="streams unavailable: "+e}}
function stRender(){const d=STR.d;bcBuild(d.keywords);const sel=$("st_reg");if(sel.options.length<2)d.regions.forEach(x=>sel.add(new Option(x,x)));
 const w=d.worker||{};$("st_meta").textContent=`· ${d.n_live} of ${d.n_channels} channels live · live status checked ${d.last_live_check?fmt(d.last_live_check):"—"} (every ${d.check_minutes} min)`;
 $("st_worker").innerHTML=`🎧 Continuous watcher ${w.running?"<b class=ok>running</b>":"<b class=bad>stopped</b>"}: listening to <b>${esc(w.slots||0)}</b> stream(s) at once (auto-tuned to keep total CPU ${esc(w.cpu_target||"")}; now ${esc(w.cpu_pct||"?")}%), rotating every ${Math.round((w.rotate_seconds||600)/60)} min across all live channels · ${esc(w.chunks||0)} × ${esc(w.chunk_seconds||30)} s chunks transcribed (faster-whisper base.en on CPU, ${esc(w.rtf||"?")}× real time) · now: ${(w.watching||[]).map(id=>esc((d.channels.find(c=>c.id==id)||{name:id}).name)).join(", ")||"—"}`;
 $("st_filt").innerHTML=STR.kw?`filtered to “<b>${esc(STR.kw)}</b>” across all streams <button id="st_clr">clear</button>`:"";if($("st_clr"))$("st_clr").onclick=()=>{STR.kw="";stLoad()};
 $("st_kw").innerHTML=d.keywords.categories.map(c=>`<span class=swatch style="background:${catColor(c.id,c.color)}"></span><b style="color:${catColor(c.id,c.color)};font-size:12.5px">${esc(c.label)}</b> `+c.words.map(x=>`<span class="kwchip${STR.kw==x.toLowerCase()?" on":""}" style="color:${c.color}" data-w="${esc(x.toLowerCase())}">${esc(x)} <span class=meta>${d.keyword_counts[x.toLowerCase()]||0}</span></span>`).join("")).join("<br>");
 const seg=s=>`<div data-sid="${s.id}" class=st-seg${(s.confirmed_by.find(c=>c.cluster_id)||{}).cluster_id?` data-cid="${esc(s.confirmed_by.find(c=>c.cluster_id).cluster_id)}"`:""}><span class="sc ${s.high?"h":lv(s.score)}">${s.score}</span><span class=meta>${esc(fmt(s.t_start))} · r${s.rank}${s.high?" · HIGH (confirmed on The Wire)":s.confirmed_by.length?" · confirmed by "+s.confirmed_by.map(c=>esc(c.name)).join(", "):" · single source"}</span><br>${bcHi(s.text)}</div>`;
 $("st_grid").innerHTML=d.channels.map(c=>{const v=c.live[0];return `<div class=st-card>${v?`<div class="st-play${STR.playing.has(v.video_id)?" on":""}" data-v="${esc(v.video_id)}" title="Click to play">${STR.playing.has(v.video_id)?`<iframe src="https://www.youtube-nocookie.com/embed/${esc(v.video_id)}?autoplay=1&mute=1&playsinline=1" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen title="${esc(c.name)} live" referrerpolicy="strict-origin-when-cross-origin"></iframe>`:`<img loading=lazy src="https://i.ytimg.com/vi/${esc(v.video_id)}/hqdefault_live.jpg" alt="${esc(c.name)} live thumbnail">`}</div>`:""}
  <div class=st-body><div><span class=nm>${esc(c.name)}</span>${v?'<span class="st-badge live">● LIVE NOW</span>':'<span class="st-badge off">offline</span>'}${c.watching?'<span class="st-badge watch">🎧 transcribing</span>':""} <span class=meta>${esc(c.region)}</span></div>
  ${v?`<div class=meta><a href="https://www.youtube.com/watch?v=${esc(v.video_id)}" target=_blank rel="noopener noreferrer">${esc(v.title)}</a></div>`:`<div class=meta><a href="https://www.youtube.com/channel/${esc(c.id)}/live" target=_blank rel="noopener noreferrer">channel ↗</a></div>`}
  <div class=st-sum>${c.summary?"<b>What's on:</b> "+bcHi(c.summary):'<span class=meta>No transcript yet — summary appears after the watcher has listened to this stream.</span>'}</div>
  ${c.segments.length?`<div class=st-tr>${c.segments.map(seg).join("")}</div>`:""}<div class=meta>${c.n_segments} segment(s) in window · top score ${c.max_score}</div></div></div>`}).join("")||"<div class=meta>No channels match.</div>";
 $("st_watch").innerHTML=d.stream_watchlist.map(s=>`<div class="card ${lv(s.score)}"><span class="sc ${lv(s.score)}">${s.score}</span><b>${esc(s.channel)}</b> <span class=meta>${esc(fmt(s.t_start))} · single channel, unconfirmed</span><div>${bcHi(s.text)}</div></div>`).join("")||"<div class=meta>Empty.</div>"}
$("st_grid").onclick=e=>{const p=e.target.closest(".st-play");if(!p||p.classList.contains("on"))return;STR.playing.add(p.dataset.v);p.classList.add("on");p.innerHTML=`<iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(p.dataset.v)}?autoplay=1&mute=1&playsinline=1&enablejsapi=1&origin=${encodeURIComponent(location.origin)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen title="live stream" referrerpolicy="strict-origin-when-cross-origin"></iframe>`};
$("st_kw").onclick=e=>{const c=e.target.closest(".kwchip");if(!c)return;STR.kw=STR.kw==c.dataset.w?"":c.dataset.w;stLoad()};
$("st_reg").onchange=stLoad;$("st_live").onchange=stLoad;$("st_hrs").onchange=stLoad;
$("st_ref").onclick=async()=>{const b=$("st_ref");b.disabled=true;$("st_msg").textContent=" checking every channel…";try{const r=await fetch("api/streams/refresh",{method:"POST"});const j=await r.json();$("st_msg").textContent=r.status==429?` rate-limited, retry in ${j.retry_after_s}s`:" ✓ "+j.note;stLoad()}catch(e){$("st_msg").textContent=" ✗ "+e}b.disabled=false};
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="streams")stLoad()});
setInterval(()=>{if($("tab-streams").style.display!="none")stLoad()},45000);

// ---- Cross-page red threads: any item (data-cid = cluster id) that belongs to a multi-update or connected story on The Thread gets a red
// push-pin with a red string running off the right edge of the page; clicking it opens #thread/<arc_id>. Map refreshed every 5 min (7-day window). ----
const XT={map:{},arcs:{},t:0};
async function xtLoad(){if(!window.THREAD_ENABLED)return;try{const j=await (await fetch("api/arcs?window=7d",{cache:"no-store"})).json();const m={},A={};
 j.arcs.forEach(a=>{if(a.n_updates<2&&!(a.connections||[]).length)return;A[a.id]=a;a.updates.forEach(u=>{if(u.cluster_id)m[u.cluster_id]=a.id})});XT.map=m;XT.arcs=A;xtApply(true)}catch(e){}}
function xtPath(i,w){const sag=26+(i%4)*14,dy=-(i%3)*10;return redStringD(0,30,w,30+dy-8,sag,0)}
function xtApply(all){const vw=document.documentElement.clientWidth;let i=0;
 document.querySelectorAll("[data-cid]").forEach(el=>{const aid=XT.map[el.dataset.cid];let x=el.querySelector(":scope > .xt");
  if(!aid){if(x)x.remove();return}if(x&&!all&&x.dataset.arc==aid)return;if(x)x.remove();
  const r=el.getBoundingClientRect();if(!r.width)return;const a=XT.arcs[aid];const w=Math.max(60,vw-r.right+36);i++;
  el.classList.add("xt-host");x=document.createElement("a");x.className="xt";x.dataset.arc=aid;x.href="#thread/"+aid;
  x.title=`🧵 On The Thread: ${a.title} — ${a.n_updates} update(s), ${a.n_sources} source(s)${(a.connections||[]).length?`, tied to ${a.connections.length} other stor${a.connections.length==1?"y":"ies"}`:""}. Click to follow the string.`;
  x.innerHTML=`<svg width="${w}" height="80"><path class="redstring" d="${xtPath(i,w)}"/></svg><span class=pin></span><span class=lab>🧵 follow the thread →</span>`;el.appendChild(x)})}
let xtMo=0;new MutationObserver(m=>{if(m.some(r=>[...r.addedNodes].some(n=>n.nodeType==1&&!(n.classList&&n.classList.contains("xt")))) ){clearTimeout(xtMo);xtMo=setTimeout(()=>xtApply(false),250)}}).observe(document.body,{childList:true,subtree:true});
addEventListener("resize",()=>{clearTimeout(XT.t);XT.t=setTimeout(()=>xtApply(true),300)});
document.querySelector(".tabs").addEventListener("click",()=>setTimeout(()=>xtApply(true),120));
async function xtOpen(){if(!window.THREAD_ENABLED)return;const m=location.hash.match(/^#thread\/(arc_[\w-]+)/);if(!m)return;const id=m[1];
 document.querySelector('.tabs button[data-tab="thread"]').click();
 const tryFocus=()=>ARCS&&ARCS.arcs.some(a=>a.id==id);
 if(!tryFocus()){$("arcs_window").value="7d";await arcsLoad()}
 setTimeout(()=>{if(TH.view!="board")thSetView("board");setTimeout(()=>{thFocus(id);const n=TH.by&&TH.by[id];if(n)n.g.classList.add("sel")},400)},250)}
addEventListener("hashchange",xtOpen);if(location.hash.startsWith("#thread/"))setTimeout(xtOpen,1500);
xtLoad();setInterval(xtLoad,300000);

/*BN_TIPS*/
// ---- Tips tab: builds https://www.paypal.me/<handle>/<amount>USD from tips.json; disabled until a handle is set ----
const TIP={h:"",st:"loading",n:0,t:0};
const tipAmt=()=>{const el=$("tip_amt");if(!el)return null;const v=el.value.trim().replace(/^\$/,"");return /^\d{1,5}(\.\d{1,2})?$/.test(v)&&+v>=1?(+v).toFixed(2).replace(/\.00$/,""):null};
// A real <a target=_blank> (not window.open) so popup blockers, iOS home-screen mode and in-app browsers follow it; href tracks the amount live.
function tipUpd(){const a=tipAmt(),b=$("tip_btn"),ok=!!(TIP.h&&a);
 if(ok)b.href=`https://www.paypal.me/${encodeURIComponent(TIP.h)}/${a}USD`;else b.removeAttribute("href");
 b.setAttribute("aria-disabled",ok?"false":"true");b.tabIndex=ok?0:-1;
 $("tip_msg").textContent=!TIP.h?(TIP.st=="loading"?"Loading the tip link…":TIP.st=="error"?"Couldn't reach the server for the tip link. Retrying…":"Tip link not set up yet"):$("tip_amt").value.trim()&&!a?"Enter an amount of $1 or more (up to 2 decimals).":"Opens PayPal in a new tab. No login or account here, and nothing you type is stored."}
// /api/tips can fail during a Render restart or the Syncing period: retry after 2 s, 5 s and 15 s, and again whenever the Tips tab is opened.
async function tipInit(){if(TIP.h||TIP.busy)return;TIP.busy=1;clearTimeout(TIP.t);
 try{const r=await fetch("api/tips",{cache:"no-store"});if(!r.ok)throw new Error("HTTP "+r.status);const j=await r.json();TIP.h=j.configured&&j.paypal_me?String(j.paypal_me):"";TIP.st=TIP.h?"ok":"unset"}
 catch(e){TIP.st="error";const d=[2000,5000,15000][TIP.n++];if(d)TIP.t=setTimeout(tipInit,d)}
 TIP.busy=0;tipUpd()}
if($("tip_amt"))$("tip_amt").oninput=tipUpd;
if($("tip_form"))$("tip_form").onsubmit=e=>{e.preventDefault();const b=$("tip_btn");if(b&&b.getAttribute("aria-disabled")!="true"&&b.href)b.click()};
const tipTab=document.querySelector('.tabs button[data-tab="tips"]');if(tipTab)tipTab.addEventListener("click",()=>{if(!TIP.h){TIP.n=0;tipInit()}});
if($("tip_amt"))tipInit();
/*/BN_TIPS*/

// ---- The Thread: string colour = connection type (keywords.json palette, shared with Live Broadcasts); pins unchanged ----
const THC={kw:null,get neutral(){return catColor("neutral","#8a5a5a")},catMap:{"war/conflict":"violence","disease":"disease","cyber":"cyber","political":"unrest"}};
async function thcKw(){if(THC.kw)return THC.kw;try{THC.kw=(await (await fetch("api/broadcast_keywords",{cache:"no-store"})).json())}catch(e){}
 if(!THC.kw||!THC.kw.categories)try{THC.kw=(await (await fetch("api/broadcasts?window=1h",{cache:"no-store"})).json()).keywords}catch(e){THC.kw={categories:[]}}return THC.kw}
function thcClass(e){const K=THC.kw;if(!K||!K.categories)return null;const sc={};const add=(c,w)=>{if(c)sc[c]=(sc[c]||0)+w};
 const words=K.categories.flatMap(c=>c.words.map(w=>[w.toLowerCase(),c.id]));
 const hit=(txt,w)=>{const t=" "+String(txt||"").toLowerCase().replace(/[^a-z0-9 ]+/g," ")+" ";words.forEach(([k,c])=>{if(t.includes(" "+k+" ")||(k.length>4&&t.includes(" "+k)))add(c,w)})};
 (e.sh||[]).forEach(s=>hit(s,3));hit(e.A.a.title,1);hit(e.B.a.title,1);hit((e.A.a.terms||[]).join(" "),.5);hit((e.B.a.terms||[]).join(" "),.5);
 add(THC.catMap[e.A.a.category],1.5);add(THC.catMap[e.B.a.category],1.5);
 const best=Object.entries(sc).sort((a,b)=>b[1]-a[1]);if(!best.length||best[0][1]<2)return null;
 const col=c=>(K.categories.find(x=>x.id==c)||{}).color;return{c:best[0][0],col:col(best[0][0]),c2:best[1]&&best[1][1]>=.7*best[0][1]?best[1][0]:null,col2:best[1]?col(best[1][0]):null}}
function thcPaint(){if(!TH.edges)return;TH.edges.forEach(e=>{const k=thcClass(e);e.cat=k?k.c:"link";e.el.style.stroke=k?catColor(k.c,k.col):THC.neutral;
 if(e.el2){e.el2.remove();e.el2=null}if(k&&k.c2){e.el2=thEl("path",{class:"str str2","stroke-width":e.el.getAttribute("stroke-width")});e.el2.style.stroke=k.col2;e.el.after(e.el2)}});thcLegend();if(typeof thDraw=="function")thDraw()}
function thcLegend(){const K=THC.kw;if(!K||!K.categories)return;let L=$("th_legend");if(!L){L=document.createElement("div");L.id="th_legend";L.className="th-legend";$("th_board").appendChild(L)}
 const n={};(TH.edges||[]).forEach(e=>n[e.cat]=(n[e.cat]||0)+1);
 L.innerHTML=`<b>STRING KEY</b>`+K.categories.map(c=>`<div><i style="background:${catColor(c.id,c.color)}"></i>${esc(c.label)} <span>${n[c.id]||0}</span></div>`).join("")+`<div><i style="background:${THC.neutral}"></i>other / shared place or topic <span>${n.link||0}</span></div><div class=mix><i class=dash></i>two-tone dash = mixed</div>`}
const thcOrigBuild=thBuild;thBuild=function(){thcOrigBuild();thcKw().then(thcPaint)};
const thcOrigDraw=thDraw;thDraw=function(){thcOrigDraw();(TH.edges||[]).forEach(e=>{if(e.el2)e.el2.setAttribute("d",e.el.getAttribute("d"))})};

// ---- "How this works" (i) notes: one collapsed note + one line-icon per tab/section. Text describes the real mechanics in scanner.py/server.py/config.json. ----
const HW_TAIL="Automated research tool: it monitors and reports only, and takes no live actions.";
const HW_RANK="Every item gets a 0–100 severity score and a 0–10 rank; rank 7+ confirmed by 2+ independent sources is high severity, while single-source, low-confidence items are capped and go to the Watchlist instead of The Wire.";
const HW_SCAN=()=>`The bot scans its public sources automatically every ${(S&&S.interval_minutes)||60} minutes by default (adjustable from 5 minutes to 6 hours) and on Manual refresh.`;
const hwI=(b)=>`<svg class="hw-svg" viewBox="0 0 200 110" role="img" aria-hidden="true" fill="none" stroke="#e6e9ee" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${b}</svg>`;
const R="#ff4d4f";
const HW_ICONS={
 wire:hwI(`<rect x="8" y="12" width="34" height="16" rx="3"/><rect x="8" y="47" width="34" height="16" rx="3"/><rect x="8" y="82" width="34" height="16" rx="3"/><path d="M42 20 L82 52 M42 55 L82 55 M42 90 L82 58" stroke="${R}"/><circle cx="96" cy="55" r="14"/><path d="M106 65 L116 75"/><path d="M128 55 h12" stroke="${R}"/><path d="M146 22 h46 M146 40 h40 M146 58 h34 M146 76 h28 M146 94 h20"/><circle cx="150" cy="22" r="3" fill="${R}" stroke="${R}"/>`),
 watch:hwI(`<path d="M30 55 Q100 5 170 55 Q100 105 30 55Z"/><circle cx="100" cy="55" r="16"/><circle cx="100" cy="55" r="5" fill="${R}" stroke="${R}"/><rect x="146" y="80" width="40" height="18" rx="3"/><text x="166" y="93" font-size="11" fill="#e6e9ee" stroke="none" text-anchor="middle">1 src</text>`),
 heat:hwI(`<circle cx="100" cy="55" r="44"/><path d="M56 55 h88 M100 11 v88 M70 22 Q100 55 70 88 M130 22 Q100 55 130 88"/><circle cx="82" cy="40" r="9" fill="${R}" stroke="none" opacity=".75"/><circle cx="120" cy="66" r="6" fill="${R}" stroke="none" opacity=".55"/>`),
 volume:hwI(`<path d="M20 98 h160"/><rect x="34" y="60" width="20" height="38"/><rect x="34" y="44" width="20" height="16" stroke="${R}"/><rect x="74" y="40" width="20" height="58"/><rect x="74" y="24" width="20" height="16" stroke="${R}"/><rect x="114" y="70" width="20" height="28"/><rect x="154" y="50" width="20" height="48"/><rect x="154" y="34" width="20" height="16" stroke="${R}"/>`),
 trend:hwI(`<path d="M20 98 h160 M20 98 V12"/><path d="M28 80 L60 70 L90 76 L120 44 L150 50 L176 22" stroke="${R}"/><path d="M28 90 L60 86 L90 88 L120 72 L150 74 L176 62"/>`),
 notify:hwI(`<path d="M70 80 V52 a30 30 0 0 1 60 0 V80 l10 10 H60Z"/><path d="M92 98 a8 8 0 0 0 16 0"/><path d="M146 30 q12 10 0 20 M156 22 q22 18 0 36" stroke="${R}"/>`),
 sources:hwI(`<rect x="30" y="12" width="110" height="20" rx="3"/><rect x="30" y="45" width="110" height="20" rx="3"/><rect x="30" y="78" width="110" height="20" rx="3"/><path d="M152 18 l6 8 l12 -14 M152 51 l6 8 l12 -14"/><path d="M152 82 l14 14 M166 82 l-14 14" stroke="${R}"/>`),
 api:hwI(`<path d="M60 20 Q40 20 40 38 V48 Q40 55 30 55 Q40 55 40 62 V72 Q40 90 60 90 M140 20 Q160 20 160 38 V48 Q160 55 170 55 Q160 55 160 62 V72 Q160 90 140 90"/><path d="M80 55 h40" stroke="${R}"/><circle cx="100" cy="55" r="3" fill="${R}" stroke="${R}"/>`),
 jets:hwI(`<path d="M30 70 L110 50 L150 30 Q162 26 160 36 L120 62 L40 82 Z"/><path d="M90 56 L76 30 M100 66 L96 90"/><path d="M130 96 l12 -20 l12 10 l14 -40" stroke="${R}"/>`),
 thread:hwI(`<path d="M30 30 Q70 60 100 34 Q130 14 170 40 M100 34 Q96 70 60 86 M100 34 Q130 70 150 86" stroke="${R}"/><circle cx="30" cy="30" r="7" fill="${R}" stroke="#fff" stroke-width="1.5"/><circle cx="100" cy="34" r="9" fill="${R}" stroke="#fff" stroke-width="1.5"/><circle cx="170" cy="40" r="7" fill="${R}" stroke="#fff" stroke-width="1.5"/><circle cx="60" cy="86" r="6" fill="${R}" stroke="#fff" stroke-width="1.5"/><circle cx="150" cy="86" r="6" fill="${R}" stroke="#fff" stroke-width="1.5"/>`),
 bcast:hwI(`<path d="M100 40 L80 100 M100 40 L120 100 M86 80 h28 M83 92 h34"/><circle cx="100" cy="36" r="6" fill="${R}" stroke="${R}"/><path d="M80 22 q-12 14 0 28 M120 22 q12 14 0 28 M66 12 q-22 24 0 48 M134 12 q22 24 0 48" stroke="${R}"/>`),
 res:hwI(`<path d="M100 96 C80 66 70 56 70 40 a30 30 0 0 1 60 0 C130 56 120 66 100 96Z" stroke="${R}"/><circle cx="100" cy="40" r="10"/><circle cx="40" cy="70" r="6"/><circle cx="160" cy="62" r="6"/><circle cx="150" cy="96" r="5"/><circle cx="46" cy="30" r="5"/><path d="M40 70 L70 60 M160 62 L130 56" stroke-dasharray="3 4"/>`),
 bush:hwI(`<path d="M50 96 L110 80 M50 80 L110 96"/><path d="M80 78 C60 60 74 46 80 26 C86 46 100 56 80 78Z" stroke="${R}"/><path d="M80 74 C72 64 78 56 80 48 C82 56 88 64 80 74Z"/><path d="M150 30 C150 30 132 56 132 68 a18 18 0 0 0 36 0 C168 56 150 30 150 30Z"/>`),
 med:hwI(`<rect x="62" y="17" width="76" height="76" rx="14"/><path d="M90 33 h20 v22 h22 v20 h-22 v22 h-20 v-22 h-22 v-20 h22Z" stroke="${R}" transform="translate(0,-8) scale(1,.95)"/>`),
 maps:hwI(`<path d="M20 24 L70 12 L130 24 L180 12 V86 L130 98 L70 86 L20 98Z M70 12 V86 M130 24 V98"/><circle cx="118" cy="56" r="20" stroke="${R}"/><path d="M132 70 L150 88" stroke="${R}"/><path d="M106 56 h24 M118 44 v24" stroke-width="1.4"/>`),
 systems:hwI(`<rect x="20" y="16" width="34" height="24" rx="4"/><rect x="146" y="16" width="34" height="24" rx="4"/><rect x="83" y="70" width="34" height="24" rx="4"/><path d="M54 28 h92 M37 40 L90 70 M163 40 L110 70" stroke="${R}"/><path d="M96 82 h8 M30 28 h6 M156 28 h6"/>`),
 timeline:hwI(`<path d="M16 70 h168"/><path d="M30 64 v12 M70 64 v12 M110 64 v12 M150 64 v12"/><rect x="96" y="58" width="16" height="24" rx="4" stroke="${R}"/><rect x="60" y="14" width="80" height="32" rx="3"/><rect x="60" y="38" width="80" height="8" fill="#e6e9ee"/>`),
 streams:hwI(`<rect x="18" y="14" width="110" height="70" rx="6"/><path d="M62 36 L86 49 L62 62Z" stroke="${R}"/><path d="M48 96 h50"/><path d="M144 40 v20 M154 32 v36 M164 44 v12 M174 36 v28" stroke="${R}"/>`),
 tips:hwI(`<path d="M60 40 h70 v30 a26 26 0 0 1 -26 26 h-18 a26 26 0 0 1 -26 -26Z"/><path d="M130 48 h10 a12 12 0 0 1 0 24 h-10"/><path d="M95 34 C80 22 80 10 90 10 C95 10 95 16 95 16 C95 16 95 10 100 10 C110 10 110 22 95 34Z" stroke="${R}"/>`),
 net:hwI(`<circle cx="70" cy="56" r="40"/><path d="M30 56 h80 M70 16 c-22 22 -22 58 0 80 M70 16 c22 22 22 58 0 80"/><path d="M128 84 l18 -36 l18 36 Z" stroke="${R}"/><path d="M146 62 v10 M146 77 v2" stroke="${R}"/>`),
 solar:hwI(`<circle cx="50" cy="50" r="18" stroke="${R}"/><path d="M50 14 v10 M50 76 v10 M14 50 h10 M76 50 h10 M25 25 l7 7 M68 68 l7 7 M25 75 l7 -7 M68 32 l7 -7" stroke="${R}"/><path d="M100 60 h14 l6 -22 l8 44 l8 -34 l6 12 h18 l5 -8 l5 8 h12"/>`),
 ranked:hwI(`<path d="M20 98 h160"/><rect x="34" y="50" width="30" height="48"/><rect x="85" y="26" width="30" height="72" stroke="${R}"/><rect x="136" y="64" width="30" height="34"/><path d="M100 8 l4 8 l9 1 l-7 6 l2 9 l-8 -5 l-8 5 l2 -9 l-7 -6 l9 -1Z" fill="${R}" stroke="${R}"/>`)
};
// key -> [main id, h2 text prefix (or null = add a header to the tab), text()]
const HW_NOTES=[
 ["wire","tab-threat","The Wire",()=>`${HW_SCAN()} It pulls about 40 public feeds (official alerts such as USGS, NWS, GDACS, NOAA, WHO, CIDRAP and CISA; news searches such as Google News and GDELT; and public OSINT channels such as Telegram, Reddit and Bluesky), then merges reports of the same event across sources. Scope is global: it monitors worldwide (war, disease, disasters, cyber, space weather and more) and ranks by worldwide relevance; no region gets extra weight. ${HW_RANK}`],
 ["timeline","tab-threat","Timeline",()=>"Drag the slider to scrub hour by hour through every item the bot has cataloged since it started scanning; bar height is items per hour and red bars contain high-severity items. New scans extend the timeline automatically. For items ranked 4+ or reported by 2+ sources, a background worker screenshots the source page and burns a black bar under it with the headline, rank, sources, link and capture time."],
 ["watch","tab-threat","Watchlist",()=>"Items here came from only one source or are otherwise low confidence, so their score is capped at 45 and they stay out of The Wire. If a second independent source confirms an item on a later scan, it moves up to The Wire automatically. "+HW_SCAN()],
 ["heat","tab-threat","Geographic heat map",()=>"Every item from the last 7 days that has a location is plotted here; hotter color means a higher 0–100 severity score. Dots mark items scoring 35 or more, colored by category, and clicking one shows its headline. Locations come from the source or are estimated from place names, so treat them as approximate."],
 ["volume","tab-threat","Alert volume",()=>"Counts of merged items per day for the last 7 days, stacked by category (war/conflict, disease, natural disaster, cyber, space weather, other). It shows how busy each category is, not how severe. The chart refreshes with every scan."],
 ["trend","tab-threat","Severity trend",()=>`For each day of items on The Wire it plots the highest score, the average score and how many items reached the high-severity line (${(S&&S.high_threshold)||60}+ on the 0–100 scale). Watchlist items are excluded. Scores never change because of this chart.`],
 ["notify","tab-threat","Notification settings",()=>"Pushes go out only for items ranked 7+ (0–10 rank) that are confirmed by 2+ independent sources; each item is pushed once. Today the active channel is a message in the Grok Bot chat after each hourly check; email and SMS are not yet connected. Changing settings needs the admin passcode."],
 ["sources","tab-threat","Sources",()=>`One row per feed the scanner reads, with whether the last fetch worked, how many items it returned and when it was checked. ${HW_SCAN()} A failed source is skipped for that scan and retried on the next one.`],
 ["api","tab-threat","API",()=>"Read-only JSON endpoints used by the hourly chat check and this page: /api/new_high lists high-severity items since a given time, and /api/state returns everything on this dashboard. Nothing here can change scores or take action."],
 ["jets","tab-jets","Private / business jets",()=>"Every 5 minutes the bot samples public ADS-B trackers for business jets that are airborne and transponding, then counts takeoffs per hour. An hour is flagged as a spike when takeoffs exceed the 7-day average for that hour by the set number of standard deviations. Jet data is informational only and never changes threat scores or ranks."],
 ["jets_trend","tab-jets","Last 24 hours",()=>"Hourly averages of airborne business jets and takeoff counts for the past day, with the spike threshold line. The threshold is the 7-day mean for that hour plus the chosen multiple of the standard deviation; until a week of data exists the baseline is still warming up."],
 ["jets_alerts","tab-jets","Jet Activity Alerts",()=>"An hour is listed here when its takeoff count crosses the spike threshold; recurring patterns are grouped above the list. Spike alerts can be pushed to chat if enabled, but they never change threat scores or ranks."],
 ["jets_set","tab-jets","Spike alert settings",()=>"Sets how many standard deviations above normal counts as a spike and whether spike alerts are sent. Changes need the admin passcode and only affect the jet tab."],
 ["jets_src","tab-jets","Jet data sources",()=>"The public ADS-B feeds sampled every 5 minutes, with their last status. Aircraft that block tracking (LADD/PIA) are counted but not identified, and jets with transponders off are not seen at all."],
 ["thread","tab-thread","The Thread",()=>"Related alerts are grouped into story threads when they share an event, place or topic, and new alerts that match an existing thread are linked into it on every scan. Each red pin is a thread (bigger = more sources); a string means two threads share terms, colored by connection type (red violence, orange disease, yellow infrastructure, blue cyber, purple unrest, teal nuclear, muted gray-red for a shared place or topic). Use the time-window control to choose how far back to look."],
 ["bcast","tab-bcast","Live Broadcasts",()=>"Text feeds (AP and Reuters via Google News, WESH 2, Spectrum News 13 and ClickOrlando RSS) are polled every 7 minutes, and short samples of NPR and BBC World Service live audio are transcribed on this computer with speech-to-text every 15 minutes. Every clip is scanned for the keywords in the color key; click a keyword, source or time window to filter. Clips are not scored here; the main scanner still decides severity."],
 ["bcast_kw","tab-bcast","Keyword key",()=>"Each color is one keyword category (red violence/attack, orange disease/outbreak, yellow infrastructure/grid, blue cyber, purple civil unrest). Adding or removing a keyword changes only highlighting and filtering on this tab and Live Streams, never the bot's scores."],
 ["bcast_h","tab-bcast","Broadcast source health",()=>"Whether each broadcast or text feed answered on its last poll, how many items it returned and when. Failed feeds are retried automatically on the next poll."],
 ["streams","tab-streams","Live Streams",()=>"Every 10 minutes the bot checks each curated news channel's public YouTube live page (no account or API key) and shows the ones on air; video loads only when you click. A background watcher listens to a few live streams at a time, rotating every 10 minutes, transcribes 30-second chunks on this computer and colors keywords like Live Broadcasts. Each segment is scored 0–100 with the same rules as the scanner: a single channel stays capped and goes to the stream watchlist, and it only counts as confirmed when another channel or The Wire reports the same thing."],
 ["streams_w","tab-streams","Stream watchlist",()=>"Transcript segments with threat terms that only one channel has said so far. They are capped at 45 like single-source items on The Wire and move up if another channel or a Wire item confirms them. Transcripts are machine-generated and can mishear words."],
 ["solar","tab-solar","Solar & Seismic",()=>"A separate add-on (solar_seismic.py) reads NOAA Space Weather Prediction Center data (solar flares, the geomagnetic Kp index, solar wind) and the USGS earthquake feeds, and shows them side by side with plain-language explanations. Strong geomagnetic storms can disturb GPS, HF radio and, rarely, power grids. Earthquakes come from USGS's own magnitude and location data. This tab doesn't feed The Wire's scoring."],
 ["net","tab-net","Network Status",()=>"Every 5 minutes the server checks official public status feeds (AWS, Google Cloud and Workspace, Azure, Microsoft 365, Apple, Meta, Slack, and the Statuspage feeds for Cloudflare, Akamai, GitHub, Discord, Reddit, Zoom, Dropbox, OpenAI and DigitalOcean). It also tests DNS and HTTPS from this computer, including direct lookups through Cloudflare 1.1.1.1, Google 8.8.8.8 and Quad9 9.9.9.9. Results go into a separate netstatus.db; the colored strips show the worst status in each time slice. An alert means a feed reports degraded or major trouble, or a probe fails twice in a row. A worldwide sprinkling of Cloudflare edge sites being down is normal; it counts when one of ~30 major hubs worldwide is fully out, 3+ major hubs are degraded, 60+ sites are out at once, or a site near Florida is hit (labelled 'near Florida'). ISP rows (Spectrum, Xfinity/Comcast, AT&T, Verizon, T-Mobile) come from IODA, Georgia Tech's public internet-outage monitor, checked every 15 minutes across each provider's networks. Probes reflect this box's network, not yours. Nothing here affects The Wire's scores."],
 ["ranked","tab-ranked","Ranked by Users",()=>"Anyone viewing the dashboard can rate an item's threat level from 0 to 10 with the small slider under it; each browser gets a random anonymous id, one vote per item, and re-voting updates it. This list sorts by a weighted average that pulls items with few votes toward the overall mean, and shows the bot's own rank beside the crowd's. User ratings never change the bot's scores, ranks or The Wire's order."],
/*BN_TIPS*/ ["tips","tab-tips","Tips",()=>"The button opens the BLACKOUT.NETWORK PayPal.me page in a new tab with your amount filled in; the payment happens entirely on PayPal. This dashboard has no login, stores nothing you type and processes no payments."],/*/BN_TIPS*/
 ["res","tab-res","Local Resources",()=>"Enter an address or ZIP and the bot geocodes it with OpenStreetMap's free Nominatim service, then lists the nearest police, fire, EMS, hospitals, urgent care, pharmacies, fuel, government offices, shelters and water from a statewide OpenStreetMap index, plus any FEMA open shelters. Distances are straight-line. Data can be incomplete, so call ahead and dial 911 in an emergency."],
 ["bush","tab-bush",null,()=>"A static beginner survival guide written from Ready.gov/FEMA, CDC, EPA and Red Cross guidance, ordered by survival priority starting with the first 72 hours. Nothing on this tab is automated or scanned, so it works the same offline once loaded or printed. Educational only, not professional advice."],
 ["med","tab-med",null,()=>"A static first-aid reference ordered by priority (scene safety, bleeding, wounds, burns, fractures, CPR, choking, allergies, heat, medications). Nothing here is automated, personalised or scanned; it is general education, not medical advice. In an emergency call 911."],
 ["maps","tab-maps","Maps — printable",()=>"The PDFs were rendered on this computer from OpenStreetMap, US Census county lines and the Florida Division of Emergency Management evacuation-route layer, plus the official USGS US Topo quads. Download or print them now: they work with no power, cell or internet. Each map has a scale bar, north arrow, legend, date and attribution."],
 ["maps_live","tab-maps","Interactive map",()=>"Map tiles stream from OpenStreetMap and need internet; emergency points come from the same statewide OpenStreetMap index as Local Resources and are grouped into clusters until you zoom in. Address search uses the same free Nominatim lookup. Use the category boxes to show or hide point types."]
];
function hwAttach(h2,key,txt){if(!h2||h2.querySelector(".hw-i"))return;const id="hw_"+key;
 const b=document.createElement("button");b.type="button";b.className="hw-i";b.title="How this works";b.setAttribute("aria-expanded","false");b.setAttribute("aria-controls",id);b.textContent="i";
 const p=document.createElement("div");p.className="hw-p";p.id=id;p.hidden=true;p.dataset.key=key;
 b.onclick=e=>{e.stopPropagation();p.hidden=!p.hidden;b.setAttribute("aria-expanded",String(!p.hidden));if(!p.hidden)p.innerHTML=`<div class="hw-t"><b>How this works.</b> ${esc(txt())} <i>${esc(HW_TAIL)}</i></div>${HW_ICONS[key]||HW_ICONS[key.split("_")[0]]||""}`};
 h2.appendChild(b);h2.insertAdjacentElement("afterend",p)}
function hwInit(){HW_NOTES.forEach(([key,mid,pre,txt])=>{if(!window.THREAD_ENABLED&&mid=="tab-thread")return;const m=$(mid);if(!m)return;let h2;
 if(pre===null){h2=m.querySelector(":scope > .hw-head h2");if(!h2){const d=document.createElement("div");d.className="hw-head";d.innerHTML=`<h2>${key=="bush"?"🏕 Bushcraft — grid-down survival guide":"⛑ Medical — grid-down first aid"}</h2>`;m.prepend(d);h2=d.querySelector("h2")}}
 else h2=[...m.querySelectorAll("h2")].find(h=>h.textContent.trim().replace(/^[^A-Za-z]+/,"").startsWith(pre.replace(/^[^A-Za-z]+/,"")));
 hwAttach(h2,key,txt)})}
hwInit();
// ---- Live push (SSE /api/stream) + a Manual refresh button on every tab (same /api/refresh, same 2 min cooldown) ----
const LV={es:null,n:0};
function lvToast(a){if(a.watchlist!=0&&!(a.rank>=4||a.high))return;const box=$("toasts");const d=document.createElement("div");d.className="toast "+(a.high?"h":lv(a.score));d.dataset.cid=a.cluster_id;
 const u=(a.links&&a.links[0])?safeUrl(a.links[0].url):"#";
 d.innerHTML=`<span class=x title="Dismiss">✕</span><div class=meta>${a.high?"🚨 HIGH · ":"New · "}rank ${a.rank}/10 · score ${a.score} · ${esc(a.category)}${a.watchlist?" · Watchlist":" · The Wire"}</div><b><a class=tl href="${esc(u)}" target=_blank rel="noopener noreferrer">${esc(a.title)}</a></b>${u!="#"?`<div class=src>Open source ↗ ${esc(a.links[0].source||(()=>{try{return new URL(u).hostname}catch(e){return""}})())}</div>`:""}
 ${a.snapshot&&a.snapshot.file?`<a href="${esc(a.snapshot.file)}" target=_blank rel=noopener><img src="${esc(a.snapshot.file)}" alt="Source snapshot"></a>`:a.snapshot_pending?`<div class=wait>📸 snapshot still capturing — it will appear here</div>`:""}`;
 d.querySelector(".x").onclick=e=>{e.stopPropagation();d.remove()};lvLink(d,u);box.prepend(d);while(box.children.length>4)box.lastChild.remove();setTimeout(()=>d.remove(),a.high?60000:20000)}
/* t228: the whole notification is clickable and keyboard-accessible; it opens the alert's primary verification link (same URL as the headline) in a new tab */
function lvLink(d,u,fn){if(u=="#"&&!fn)return;d.classList.add("lk");d.tabIndex=0;d.setAttribute("role","link");const go=()=>fn?fn():window.open(u,"_blank","noopener,noreferrer");
 d.addEventListener("click",e=>{if(e.target.closest("a,.x,button"))return;go()});d.addEventListener("keydown",e=>{if((e.key=="Enter"||e.key==" ")&&e.target==d){e.preventDefault();go()}})}
const LVB={w:0,l:0,t:0};function lvBatch(a){a.watchlist==0?LVB.w++:LVB.l++;clearTimeout(LVB.t);LVB.t=setTimeout(()=>{const d=document.createElement("div");d.className="toast";
 d.innerHTML=`<span class=x title="Dismiss">✕</span><b>📡 ${LVB.w+LVB.l} new item(s) just landed</b><div class=meta>${LVB.w} on The Wire · ${LVB.l} on the Watchlist · pushed live, no refresh needed</div>`;d.querySelector(".x").onclick=e=>{e.stopPropagation();d.remove()};d.title="Open The Wire";lvLink(d,"#",()=>{const b=document.querySelector('.tabs button[data-tab="threat"]');b&&b.click();const f=$("feed");f&&f.scrollIntoView({behavior:"smooth",block:"start"})});
 $("toasts").prepend(d);while($("toasts").children.length>4)$("toasts").lastChild.remove();setTimeout(()=>d.remove(),20000);LVB.w=LVB.l=0},2500)}
let lvT=0;function lvReload(){clearTimeout(lvT);lvT=setTimeout(()=>{load();if(typeof tlRefresh=="function")tlRefresh()},1500)}
function lvConnect(){if(!window.EventSource)return;const es=new EventSource("api/stream");LV.es=es;const ind=$("live_ind");
 es.addEventListener("hello",()=>{ind.classList.add("on");ind.title="Connected: new alerts arrive instantly"});
 es.onerror=()=>{ind.classList.remove("on");ind.title="Reconnecting…"};
 es.addEventListener("alert",e=>{const a=JSON.parse(e.data);if(a.watchlist==2)return;LV.n++;lvBatch(a);$("live_n").textContent=LV.n?` · ${LV.n} new`:"";lvToast(a);lvReload()});
 es.addEventListener("snapshot",e=>{const s=JSON.parse(e.data);document.querySelectorAll(`.toast[data-cid="${CSS.escape(s.cluster_id)}"] .wait`).forEach(w=>w.outerHTML=`<a href="${esc(s.file)}" target=_blank rel=noopener><img src="${esc(s.file)}" alt="Source snapshot"></a>`);if(typeof tlRefresh=="function")tlRefresh()});
 es.addEventListener("scan",()=>lvReload())}
(()=>{const c=document.querySelector("header .ctl");const s=document.createElement("span");s.id="live_ind";s.innerHTML='<i></i>Live<span id="live_n"></span>';s.title="Connecting…";c.prepend(s);
 const t=document.createElement("div");t.id="toasts";document.body.appendChild(t);lvConnect();
 document.querySelectorAll("body>main").forEach(m=>{if(m.id=="tab-threat")return;const h=m.querySelector("h2");if(!h||h.querySelector(".tab-ref"))return;
  const b=document.createElement("button");b.type="button";b.className="tab-ref";b.textContent="⟳ Refresh";b.title="Run a scan now (same as Manual refresh at the top)";
  b.onclick=async e=>{e.stopPropagation();b.disabled=true;b.textContent="scanning…";await $("refresh").onclick();b.textContent="⟳ Refresh";b.disabled=false;
   const tb=m.dataset.addon;if(tb=="bcast")bcLoad();if(tb=="thread")arcsLoad();if(tb=="maps")mpList();if(m.id=="tab-jets")loadJets()};
  const hw=h.querySelector(".hw-i");hw?h.insertBefore(b,hw):h.appendChild(b)})})();
// ---- User votes: compact 0-10 selector on items across tabs + Ranked by Users tab (votes.db; never touches bot scoring) ----
const VT={voter:localStorage.getItem("bn_voter")||(()=>{const a=new Uint8Array(16);crypto.getRandomValues(a);const v=[...a].map(x=>x.toString(16).padStart(2,"0")).join("");localStorage.setItem("bn_voter",v);return v})(),pend:0};
function vtTargets(){const T=[];
 document.querySelectorAll(".card[data-cid],.tl-card[data-cid]").forEach(el=>T.push([el,"cluster",el.dataset.cid,el,null]));
 document.querySelectorAll("#tab-bcast .clip[data-bid]").forEach(el=>T.push([el,"bcast",el.dataset.bid,null,el]));
 document.querySelectorAll(".st-seg[data-sid]").forEach(el=>T.push([el,"stream",el.dataset.sid,el,null]));
 document.querySelectorAll("#arcs .arc .arc-hd[data-tog]").forEach(el=>T.push([el,"arc",el.dataset.tog,el.parentElement,null]));
 const P=$("th_panel");if(P&&P.style.display!="none"&&TH.sel)T.push([P,"arc",TH.sel,P.querySelector("h3"),null]);return T}
function vtTitle(typ,el){if(typ=="arc"){const a=ARCS&&ARCS.arcs.find(x=>x.id==(el.dataset.tog||TH.sel));return a?[a.title,""]:["",""]}
 const b=el.querySelector("b");const a=el.tagName=="A"?el:el.querySelector("a[href^=http]");return[(window.BNTR?BNTR.orig(b||el):(b?b.textContent:el.textContent)).slice(0,280),a?a.href:""]}
function vtApply(){const need={};vtTargets().forEach(([el,typ,id,host,after])=>{const key=typ+"|"+id;let w=(after?after.nextElementSibling:host.querySelector(":scope > .vt"));
 if(!(w&&w.classList&&w.classList.contains("vt")&&w.dataset.k==key)){w=document.createElement("div");w.className="vt";w.dataset.k=key;w.innerHTML=`<span title="Your threat level for this item (0 = none, 10 = extreme). Never changes the bot's rank.">⚖ rate</span><input type=range min=0 max=10 step=1 value=5 aria-label="Your threat level 0 to 10"><span class=vt-l>—</span>`;
  w.querySelector("input").addEventListener("click",e=>e.stopPropagation());w.addEventListener("click",e=>{e.stopPropagation();e.preventDefault()},true);
  w.querySelector("input").onchange=e=>vtSend(typ,id,+e.target.value,w,el);if(after)after.after(w);else host.appendChild(w)}
 (need[typ]=need[typ]||[]).push(id)});
 Object.entries(need).forEach(async([typ,ids])=>{try{const j=await (await fetch(`api/votes?type=${typ}&voter=${VT.voter}&ids=${encodeURIComponent([...new Set(ids)].slice(0,300).join(","))}`)).json();
  Object.entries(j.votes).forEach(([id,v])=>document.querySelectorAll(`.vt[data-k="${CSS.escape(typ+"|"+id)}"]`).forEach(w=>vtShow(w,v)))}catch(e){}})}
function vtShow(w,v){w.classList.toggle("has",v.mine!=null);if(v.mine!=null)w.querySelector("input").value=v.mine;w.querySelector(".vt-l").innerHTML=(v.mine!=null?`you <b>${v.mine}</b> · `:"")+(v.n?`avg <b>${v.avg}</b> (${v.n})`:"no votes")}
async function vtSend(typ,id,r,w,el){const[t,u]=vtTitle(typ,el);try{const res=await fetch("api/vote",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({item_type:typ,item_id:id,rating:r,voter:VT.voter,title:t,url:u})});const j=await res.json();
 if(!res.ok)throw j.error||res.status;vtShow(w,{mine:r,avg:j.avg,n:j.n});w.classList.remove("pulse");void w.offsetWidth;w.classList.add("pulse");if($("tab-ranked").style.display!="none")rkLoad()}catch(e){w.querySelector(".vt-l").textContent="✗ "+e}}
let vtMo=0;new MutationObserver(m=>{if(m.some(r=>[...r.addedNodes].some(n=>n.nodeType==1&&!n.classList.contains("vt")&&!n.classList.contains("xt")))){clearTimeout(vtMo);vtMo=setTimeout(vtApply,400)}}).observe(document.body,{childList:true,subtree:true});
// Ranked by Users tab
const RK={pos:{}};
async function rkLoad(){try{const q=new URLSearchParams({sort:$("rk_sort").value,window:$("rk_win").value,min:$("rk_min").value});const j=await (await fetch("api/user_ranked?"+q,{cache:"no-store"})).json();
 $("rk_meta").textContent=`· ${j.items.length} rated item(s) · weighted average = (${j.prior_weight} × ${j.prior_mean} + sum of votes) ÷ (${j.prior_weight} + votes)`;
 const L=$("rk_list"),old={};L.querySelectorAll(".rk-row").forEach(r=>old[r.dataset.k]=r.getBoundingClientRect().top);
 const tl={cluster:"The Wire item",arc:"The Thread story",bcast:"Live Broadcasts clip",stream:"Live Streams segment"};
 L.innerHTML=j.items.filter(x=>window.THREAD_ENABLED||x.item_type!="arc").map((x,i)=>{const d=x.diff;const bd=d==null?`<span class="rk-badge eq">no bot rank</span>`:d>=1?`<span class="rk-badge up">crowd +${d} vs bot</span>`:d<=-1?`<span class="rk-badge dn">crowd ${d} vs bot</span>`:`<span class="rk-badge eq">crowd ≈ bot</span>`;
  return `<div class=rk-row data-k="${esc(x.item_type+"|"+x.item_id)}"><div class=rk-pos>${i+1}</div><div><b>${x.url?`<a href="${esc(safeUrl(x.url))}" target=_blank rel="noopener noreferrer" style="color:var(--tx)">${esc(x.title||x.item_id)}</a>`:esc(x.title||x.item_id)}</b><div class=meta>${tl[x.item_type]}${x.category?" · "+esc(x.category):""} · last vote ${esc(fmt(x.last))}</div></div>
  <div><span class=rk-big>${x.bayes}</span><div class=meta>weighted · raw ${x.avg}</div></div><div><b>${x.n}</b> vote${x.n==1?"":"s"}<div class=meta>bot: ${x.bot_rank!=null?`rank ${x.bot_rank}/10 · score ${x.bot_score}`:"n/a"}</div></div><div>${bd}</div></div>`}).join("")||"<div class=meta>No rated items in this window yet.</div>";
 L.querySelectorAll(".rk-row").forEach(r=>{const o=old[r.dataset.k];if(o==null){r.classList.add("new");setTimeout(()=>r.classList.remove("new"),900);return}const dy=o-r.getBoundingClientRect().top;if(dy){r.style.transition="none";r.style.transform=`translateY(${dy}px)`;requestAnimationFrame(()=>{r.style.transition="";r.style.transform=""})}})}catch(e){$("rk_meta").textContent="unavailable: "+e}}
const rkAgo=t=>{const s=(Date.now()-new Date(t))/1e3;return s<60?"just now":s<3600?Math.round(s/60)+" min ago":fmt(t)};
async function rkTick(){try{const j=await (await fetch("api/votes/recent",{cache:"no-store"})).json();if(!j.items.length)return;
 $("rk_tick_in").innerHTML=j.items.map(v=>`<span>🗳 <b>${v.rating}/10</b> threat vote on “${esc((v.title||v.item_id).slice(0,80))}” · ${rkAgo(v.ts)}</span>`).join("")}catch(e){}}
$("rk_sort").onchange=rkLoad;$("rk_win").onchange=rkLoad;$("rk_min").onchange=rkLoad;
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="ranked"){rkLoad();rkTick()}});
if(LV&&LV.es)LV.es.addEventListener("vote",()=>{rkTick();if($("tab-ranked").style.display!="none")rkLoad();vtApply()});
setInterval(()=>{if($("tab-ranked").style.display!="none")rkTick()},30000);vtApply();
// ---- Network Status tab (netstatus.py; official feeds + this box's probes) ----
const NS={win:"24h",d:null};
const nsCls=l=>l==null?"":"ns-l"+l, nsGroups=["Big cloud","DNS & CDN","Apps & social","Dev & cloud","ISPs","Box probes: DNS resolvers","Box probes: HTTPS","Status feeds unavailable"];
async function nsLoad(){try{const d=NS.d=await (await fetch("api/netstatus?window="+NS.win,{cache:"no-store"})).json();
 $("ns_meta").textContent=d.polled?`· last checked ${fmt(d.polled)} · every ${d.poll_seconds/60} min · each history cell = ${d.bucket_minutes>=60?d.bucket_minutes/60+" h":d.bucket_minutes+" min"} (${d.polls_stored} polls stored)`:"· first poll running…";
 const by={};d.sources.forEach(s=>(by[s.grp]=by[s.grp]||[]).push(s));
 /* design v3: each group is an accordion; a group with anything not operational opens by default; the visitor's own open/close wins for the session */
 const nsAcc=(g,rows)=>{const id="acc-ns-"+g.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,""),bad=rows.filter(s=>s.level>0),worst=Math.max(0,...rows.map(s=>s.level||0));
  let saved=null;try{saved=sessionStorage.getItem("bnacc:"+id)}catch(e){}const open=saved?saved==="1":bad.length>0;
  const names=rows.length<=5?rows.map(s=>s.src).join(", "):rows.slice(0,4).map(s=>s.src).join(", ")+` and ${rows.length-4} more`;
  const st=bad.length?`<span class="bn-acc-st ${worst>=2?"bad":"warn"}">${bad.length} not normal · ${rows.length}</span>`:`<span class="bn-acc-st">All normal · ${rows.length}</span>`;
  const mini=rows[0]&&rows[0].hist?`<span class="bn-acc-mini" aria-hidden="true">${rows[0].hist.slice(-24).map((_,i)=>{const w=Math.max(...rows.map(s=>(s.hist||[])[s.hist.length-24+i]??-9));return`<i class="${w>-9?nsCls(w):""}"></i>`}).join("")}</span>`:"";
  return `<details class="bn-acc bn-acc-ns" id="${id}"${open?" open":""}><summary aria-expanded="${open}" onclick="var d=this.parentNode;setTimeout(function(){try{sessionStorage.setItem('bnacc:'+d.id,d.open?'1':'0')}catch(e){}},0)"><span class="bn-acc-ic">${(window.bnV3&&bnV3.IC.globe)||""}</span><span class="bn-acc-t"><b>${esc(g)}</b><small>${esc(names)}</small></span>${mini}<span class="bn-acc-v">${st}</span></summary><div class="bn-acc-body"><h3>${esc(g)}</h3>`};
 $("ns_list").innerHTML=[...nsGroups.filter(g=>by[g]),...Object.keys(by).filter(g=>!nsGroups.includes(g))].map(g=>nsAcc(g,by[g])+by[g].sort((a,b)=>b.level-a.level).map(s=>`<div class=ns-row title="${esc(d.levels[s.level]||"")}"><span class="d ${nsCls(s.level)}"></span>
  <span>${s.url?`<a href="${esc(safeUrl(s.url))}" target=_blank rel="noopener noreferrer">${esc(s.src)}</a>`:esc(s.src)}</span><span><span class=st>${esc(s.status)}</span>${s.detail?`<span class=dt title="${esc(s.detail)}">${esc(s.detail)}</span>`:""}</span>
  <span class=ns-h>${s.hist.map(l=>`<i class="${nsCls(l)}"></i>`).join("")}</span></div>`).join("")+"</div></details>").join("")||"<div class=meta>Waiting for the first poll…</div>";
 const al=d.sources.filter(s=>d.alerts.includes(s.src));
 $("ns_banner").style.display=al.length?"block":"none";$("ns_banner").innerHTML=al.length?`⚠ <b>${al.length} active network alert${al.length>1?"s":""}:</b> `+al.map(s=>`${esc(s.src)}: ${esc(s.status)}`).join(" · "):"";
 const C=d.corroboration;$("ns_cor").innerHTML=(C.wire.map(w=>`<a href="#" data-goto="${esc(w.id)}">📡 <b>${esc(w.title)}</b><span class=meta> · The Wire · rank ${w.rank}/10 · ${esc(fmt(w.first_seen))}</span></a>`).join("")+
  C.broadcasts.map(b=>`<a href="${esc(safeUrl(b.url))}" target=_blank rel="noopener noreferrer">📻 ${esc(b.title)}<span class=meta> · ${esc(b.source)} · ${esc(fmt(b.published))}</span></a>`).join(""))||"<div class=meta>Nothing outage-related in the last 24 hours.</div>";
 $("ns_cor").querySelectorAll("[data-goto]").forEach(a=>a.onclick=e=>{e.preventDefault();document.querySelector('.tabs button[data-tab="threat"]').click();setTimeout(()=>{const el=document.querySelector(`[data-cid="${CSS.escape(a.dataset.goto)}"]`);if(el){el.scrollIntoView({block:"center"});el.style.outline="2px solid var(--hi)";setTimeout(()=>el.style.outline="",2500)}},300)});
 nsBadge({count:al.length,alerts:al.map(s=>s.src)})}catch(e){$("ns_meta").textContent="· temporarily unavailable, retrying shortly"}}
function nsTxt(v){return v==null?"":typeof v=="string"||typeof v=="number"?String(v):Array.isArray(v)?v.map(nsTxt).filter(Boolean).join(", "):typeof v=="object"?nsTxt(v.src||v.name||v.label||v.title||v.status||""):""}
function nsBadge(a){if(a&&a.data&&a.count==null)a=a.data;a=a||{};a={count:+a.count||0,alerts:(Array.isArray(a.alerts)?a.alerts:[]).map(x=>typeof x=="object"&&x?[nsTxt(x.src),typeof x.status=="string"?x.status:""].filter(Boolean).join(": "):nsTxt(x)).filter(Boolean)};if(!a.alerts.length)a.count=0;const b=document.querySelector('.tabs button[data-tab="net"]');let s=b.querySelector(".ns-badge");if(!a.count){s&&s.remove();$("ns_gbanner").style.display="none";return}
 if(s)s.remove();   // no count badge on the Network Status tab (Matt, Nov 12); the banner below still shows the alert text
 const key=nsKey(a.alerts);if(!nsDismissed(key)){$("ns_gbanner").innerHTML=`<span class=ns-txt>🌐 <b>Network alert:</b> ${a.alerts.map(esc).join("; ")}. <span class=meta>Tap to open Network Status.</span></span><button class=ns-x type=button aria-label="Dismiss until the alerts change" title="Dismiss until the alerts change" style="background:none;border:0;color:#ffccc7;cursor:pointer">✕</button>`;$("ns_gbanner").style.display="flex";$("ns_gbanner").dataset.k=key}}
/* t397: a dismissed network alert stays dismissed across page loads (localStorage "bn_dismiss_ns" = {k, t}). Identity = the sorted list of
   affected services (status wording changes don't re-show it); it comes back only for a new/different set of services or after 24 h. */
function nsKey(al){return al.map(x=>String(x).split(":")[0].trim().toLowerCase()).filter(Boolean).sort().join("|")}
function nsDismissed(k){if(!k)return false;try{const v=JSON.parse(localStorage.getItem("bn_dismiss_ns")||"null");return !!v&&v.k===k&&Date.now()-v.t<864e5}catch(_){return false}}
function nsDismiss(k){if(!k)return;try{localStorage.setItem("bn_dismiss_ns",JSON.stringify({k:k,t:Date.now()}))}catch(_){}}
async function nsAlerts(){try{nsBadge(await (await fetch("api/netstatus/alerts",{cache:"no-store"})).json())}catch(e){}}
$("ns_gbanner").onclick=e=>{if(e.target.closest(".ns-x")){nsDismiss($("ns_gbanner").dataset.k);$("ns_gbanner").style.display="none";return}document.querySelector('.tabs button[data-tab="net"]').click()};
$("ns_win").onchange=e=>{NS.win=e.target.value;nsLoad()};
document.querySelector(".tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b&&b.dataset.tab=="net"){nsLoad();nsDismiss($("ns_gbanner").dataset.k||"");$("ns_gbanner").style.display="none"}});
if(LV&&LV.es)LV.es.addEventListener("netstatus",e=>{try{nsBadge(JSON.parse(e.data))}catch(_){}if($("tab-net").style.display!="none")nsLoad()});
setInterval(()=>{nsAlerts();if($("tab-net").style.display!="none")nsLoad()},300000);nsAlerts();
(function(){const nav=document.querySelector(".tabs"),B=t=>nav.querySelector(`button[data-tab="${t}"]`);
 const groups=[["Monitor",["threat","thread","bcast","streams","radio","net","solar_seismic","jets"]],["Community",["ranked"]],["Reference",["res","maps","bush","med"]],["",["tips"]]];
 const frag=document.createDocumentFragment();groups.forEach(([g,ts],i)=>{if(i){const s=document.createElement("span");s.className="tab-sep";frag.appendChild(s)}
  if(g){const l=document.createElement("span");l.className="tab-grp";l.textContent=g;frag.appendChild(l)}ts.forEach(t=>B(t)&&frag.appendChild(B(t)))});
 [...nav.querySelectorAll("button[data-tab]")].forEach(b=>frag.appendChild(b));nav.appendChild(frag);
 // clicks on a tab's icon, badge or thumbnail count as clicks on the tab itself
 nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b&&e.target!==b){e.stopImmediatePropagation();e.preventDefault();b.click()}},true);
 nav.addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(!b)return;const h=TABHASH[b.dataset.tab];if(!h)return;
  if(b.dataset.tab=="thread"&&location.hash.startsWith("#thread/"))return;if(location.hash!="#"+h)history.replaceState(null,"","#"+h)});
 function go(){const h=location.hash.slice(1);if(h==="heatmap"||h==="map"){location.replace("/map"+location.search);return}if(!window.THREAD_ENABLED&&/^thread(\/|$)/.test(h)){history.replaceState(null,"","#wire");if(B("threat")&&!B("threat").classList.contains("on"))B("threat").click();return}if(h.startsWith("thread/"))return;const t=HASHTAB[h];if(t&&B(t)&&!B(t).classList.contains("on"))B(t).click()}
 addEventListener("hashchange",go);setTimeout(go,300)})();

