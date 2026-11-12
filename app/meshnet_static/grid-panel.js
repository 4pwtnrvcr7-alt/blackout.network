// BLACKOUT.NETWORK Energy Grid tab (#grid): "Mesh network drop-offs" panel from /api/mesh/summary (meshnet.py). Single source, unconfirmed.
(function(){"use strict";
if(window.__bnMeshGrid)return;window.__bnMeshGrid=1;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
var CSS='.mxg{border:1px solid var(--bn-line,#252b33);background:var(--bn-surface,#14181d);border-radius:14px;padding:14px 16px;margin:0 0 14px}'+
'.mxg h3{margin:0 0 4px;font:800 16px/1.3 Montserrat,Inter,system-ui,sans-serif}.mxg .mu{color:var(--bn-muted,#8b95a3);font-size:12.5px;margin:0 0 8px}'+
'.mxg .g{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(200px,100%),1fr));gap:8px}.mxg .c{border:1px solid var(--bn-line,#252b33);border-radius:10px;padding:8px 10px;font-size:13px}'+
'.mxg .c b{display:block;font-size:13.5px}.mxg .w{border-color:#FFC21A}html[data-theme=light] .mxg .w{border-color:#C97B00}.mxg .pill{display:inline-block;font:800 10.5px/1 Montserrat,sans-serif;letter-spacing:.4px;padding:3px 6px;border-radius:5px;background:#FFC21A;color:#111;margin:0 0 4px}'+
'html[data-theme=light] .mxg .pill{background:#C97B00;color:#fff}.mxg a{color:var(--ac,#4aa3ff)}';
function host(){return document.getElementById("tab-grid")}
async function build(){var M=host();if(!M||M.querySelector("#mxg"))return;
 if(!document.getElementById("mxg_css")){var st=document.createElement("style");st.id="mxg_css";st.textContent=CSS;document.head.appendChild(st)}
 var el=document.createElement("section");el.className="mxg";el.id="mxg";el.innerHTML='<h3>Mesh network drop-offs</h3><p class="mu">Loading…</p>';
 var top=M.querySelector("#gs_top");if(top&&top.parentNode)top.parentNode.insertBefore(el,top.nextSibling);else M.insertBefore(el,M.firstChild);
 var d;try{d=await (await fetch("/api/mesh/summary",{cache:"no-store"})).json()}catch(e){d={ok:false}}
 if(!d.ok){el.innerHTML='<h3>Mesh network drop-offs</h3><p class="mu">Waiting for the first sync. <a href="/mesh">Open the off-grid network map</a>.</p>';return}
 var f=d.feed||{},sig=d.signals||[],grid=(d.regions||[]).filter(function(r){return r.kind==="grid"}).sort(function(a,b){return (b.silent_pct||0)-(a.silent_pct||0)});
 var flagged={};sig.forEach(function(s){flagged[s.region]=s});
 el.innerHTML='<h3>Mesh network drop-offs</h3><p class="mu">Mesh gateway radios need power and internet. When many regular nodes in one grid section go quiet at once it can point to an outage. '+
  'Single source (MeshMap.net public node data), unconfirmed, never above rank 5. '+(f.baseline_ready?(f.ok?"":"<b>Data source delayed: watch paused.</b> "):"Baseline still building. ")+'<a href="/mesh">Off-grid network map</a></p><div class="g">'+
  grid.map(function(r){var s=flagged[r.id];return '<div class="c'+(s?" w":"")+'">'+(s?'<span class="pill">WATCHLIST · RANK '+s.rank+'</span>':'')+'<b>'+esc(r.name)+'</b>'+
   r.total+' nodes · '+r.active+' heard in 1 h'+(r.regular>=10?'<br>'+r.silent+' of '+r.regular+' regular quiet ('+Math.round((r.silent_pct||0)*100)+'%)':'')+'</div>'}).join("")+'</div>'}
function tick(){if(location.hash.indexOf("#grid")===0||host()&&host().offsetParent)build()}
window.addEventListener("hashchange",tick);if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",tick);else tick();setTimeout(tick,2500);
})();
