// BLACKOUT.NETWORK "Push to Mesh" (share row on story pages). Builds a compact mesh-ready message (headline + short URL, <= 200 bytes),
// shows it for review, and sends it ONLY from the reader's own radio after they tap "Send to mesh". Our servers never transmit.
// No Web Bluetooth / Web Serial (Safari, iPhone, iPad, Firefox): Share… / Copy the mesh-ready text for the official Meshtastic app.
(function(){"use strict";
if(window.BNMeshShare)return;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
var CSS='.mxs-scrim{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9998;display:flex;align-items:flex-end;justify-content:center}'+
'@media(min-width:640px){.mxs-scrim{align-items:center}}'+
'.mxs{background:var(--bn-surface,#14181d);color:var(--bn-text,#e6e9ee);border:1px solid var(--bn-line,#252b33);border-radius:16px 16px 0 0;width:100%;max-width:520px;max-height:92vh;overflow:auto;padding:18px 18px 22px;font:15px/1.5 Inter,system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.45)}'+
'@media(min-width:640px){.mxs{border-radius:16px}}'+
'.mxs h2{font:800 18px/1.25 Montserrat,Inter,system-ui,sans-serif;margin:0 0 4px}.mxs p{margin:6px 0}.mxs .mu{color:var(--bn-muted,#8b95a3);font-size:13px}'+
'.mxs textarea{width:100%;box-sizing:border-box;min-height:92px;resize:vertical;background:var(--bn-bg,#0b0d10);color:inherit;border:1px solid var(--bn-line,#2f3742);border-radius:10px;padding:10px;font:14px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}'+
'.mxs .row{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0;align-items:center}.mxs .sp{flex:1}'+
'.mxs button,.mxs a.b{display:inline-flex;align-items:center;justify-content:center;gap:6px;font:700 13.5px/1 Montserrat,Inter,system-ui,sans-serif;padding:11px 14px;border-radius:10px;border:1px solid var(--bn-line,#2f3742);background:transparent;color:inherit;cursor:pointer;text-decoration:none;min-height:42px}'+
'.mxs .pri{background:#FFC21A;border-color:#FFC21A;color:#111}html[data-theme=light] .mxs .pri{background:#C97B00;border-color:#C97B00;color:#fff}'+
'.mxs button:disabled{opacity:.45;cursor:not-allowed}.mxs select{background:var(--bn-bg,#0b0d10);color:inherit;border:1px solid var(--bn-line,#2f3742);border-radius:10px;padding:9px;font:inherit;min-height:42px;max-width:100%}'+
'.mxs .cnt{font-size:12.5px;color:var(--bn-muted,#8b95a3)}.mxs .cnt.over{color:#ff4d4f;font-weight:700}.mxs .st{font-size:13px;min-height:1.4em}'+
'.mxs [hidden]{display:none!important}.mxs .x{float:right;border:0;padding:6px 8px;min-height:0;font-size:20px;line-height:1}.mxs hr{border:0;border-top:1px solid var(--bn-line,#252b33);margin:14px 0}';
function css(){if(document.getElementById("mxs_css"))return;var s=document.createElement("style");s.id="mxs_css";s.textContent=CSS;document.head.appendChild(s)}
function dev(){if(window.BNMesh)return Promise.resolve(window.BNMesh);return new Promise(function(ok,no){var s=document.createElement("script");s.src="/api/mesh/device.js?v=1";s.onload=function(){ok(window.BNMesh)};s.onerror=no;document.head.appendChild(s)})}
function compose(B,title,url){
 title=String(title||"").replace(/\s+via BLACKOUT\.NETWORK\s*$/i,"").replace(/\s+/g," ").trim();
 var u=String(url||"").replace(/^https?:\/\//,"").replace(/[?#].*$/,"");
 var pre="BLACKOUT: ",room=B.MAX_BYTES-B.bytes(pre)-1-B.bytes(u);
 return pre+B.trimBytes(title,Math.max(20,room))+" "+u}
async function open(wrap){css();var B=await dev();var sup=B.support();
 var text=compose(B,wrap.dataset.text,wrap.dataset.url);
 var sc=document.createElement("div");sc.className="mxs-scrim";sc.innerHTML='<div class="mxs" role="dialog" aria-modal="true" aria-labelledby="mxs_t">'+
  '<button type="button" class="x" aria-label="Close">×</button><h2 id="mxs_t">Push to Mesh</h2>'+
  '<p class="mu">Send this story to a Meshtastic channel from <b>your own radio</b>. Review it first. BLACKOUT.NETWORK never sends anything to the mesh.</p>'+
  '<label class="mu" for="mxs_txt">Message (edit if you like)</label><textarea id="mxs_txt" maxlength="400">'+esc(text)+'</textarea>'+
  '<div class="row"><span class="cnt" id="mxs_cnt"></span></div>'+
  (sup.any?('<hr><div class="row" id="mxs_conn">'+(sup.bt?'<button type="button" data-k="bt">Connect by Bluetooth</button>':'')+(sup.serial?'<button type="button" data-k="usb">Connect by USB</button>':'')+'</div>'+
   '<div class="row" id="mxs_chrow" hidden><label class="mu" for="mxs_ch">Channel</label><select id="mxs_ch"><option value="0">Primary (channel 0)</option></select></div>'+
   '<p class="st" id="mxs_st" role="status" aria-live="polite">'+(B.state()==="ready"?"Radio connected.":"Not connected.")+'</p>'+
   '<div class="row"><button type="button" class="pri" id="mxs_send" disabled>Send to mesh</button><button type="button" id="mxs_cancel">Cancel</button>'+
   '<span class="sp"></span><button type="button" id="mxs_copy">Copy text</button></div>'+
   '<p class="mu">One message every 30 seconds, at most 5 in 10 minutes. The default channel is public.</p>')
  :('<hr><p class="st" id="mxs_st">'+(sup.ios?'Safari on iPhone and iPad cannot talk to a radio from a web page. Share or copy the text, then paste it into a channel in the Meshtastic app.'
     :'This browser cannot talk to a radio from a web page. Share or copy the text, then paste it into a channel in the Meshtastic app, or use Chrome or Edge.')+'</p>'+
   '<div class="row">'+(navigator.share?'<button type="button" class="pri" id="mxs_share">Share…</button>':'')+'<button type="button" id="mxs_copy"'+(navigator.share?'':' class="pri"')+'>Copy text</button></div>'+
   '<div class="row">'+(sup.ios?'<a class="b" href="'+B.IOS_OPEN+'">Open Meshtastic</a><a class="b" href="'+B.IOS_APP+'" target="_blank" rel="noopener">Get the app (App Store)</a>'
     :sup.android?'<a class="b" id="mxs_and" href="#">Open in Meshtastic</a><a class="b" href="'+B.ANDROID_APP+'" target="_blank" rel="noopener">Get the app (Google Play)</a>'
     :'<a class="b" href="'+B.IOS_APP+'" target="_blank" rel="noopener">App Store</a><a class="b" href="'+B.ANDROID_APP+'" target="_blank" rel="noopener">Google Play</a>')+'</div>'+
   '<p class="mu">Tip: in the Meshtastic app, open Messages, pick a channel, then paste.</p>'))+'</div>';
 document.body.appendChild(sc);var q=function(s){return sc.querySelector(s)};var ta=q("#mxs_txt"),prev=document.activeElement;
 function close(){sc.remove();document.removeEventListener("keydown",key);try{prev&&prev.focus()}catch(e){}}
 function key(e){if(e.key==="Escape")close()}document.addEventListener("keydown",key);
 sc.addEventListener("click",function(e){if(e.target===sc)close()});q(".x").addEventListener("click",close);if(q("#mxs_cancel"))q("#mxs_cancel").addEventListener("click",close);
 function upd(){var n=B.bytes(ta.value.trim());var c=q("#mxs_cnt");c.textContent=n+" / "+B.MAX_BYTES+" bytes";c.classList.toggle("over",n>B.MAX_BYTES);
  var s=q("#mxs_send");if(s)s.disabled=!(B.state()==="ready"||B.state()==="configuring")||!ta.value.trim()||n>B.MAX_BYTES;
  var a=q("#mxs_and");if(a)a.href=B.androidShare(ta.value.trim())}
 ta.addEventListener("input",upd);upd();
 function chs(list){var sel=q("#mxs_ch");if(!sel)return;sel.innerHTML=list.map(function(c){return '<option value="'+c.index+'"'+(c.primary?" selected":"")+'>'+esc(c.name)+'</option>'}).join("")||'<option value="0">Primary (channel 0)</option>'}
 function onst(s){var st=q("#mxs_st");if(!st||!document.body.contains(sc))return;st.textContent={connecting:"Connecting… pick your radio in the browser prompt.",configuring:"Connected. Reading channels…",ready:"Radio connected. Pick a channel and tap Send.",disconnected:"Not connected."}[s]||s;
  var on=s==="ready"||s==="configuring";if(q("#mxs_conn"))q("#mxs_conn").hidden=on;if(q("#mxs_chrow"))q("#mxs_chrow").hidden=!on;upd()}
 if(sup.any){B.on("status",onst);B.on("ch",chs);chs(B.channels());onst(B.state());
  [].forEach.call(sc.querySelectorAll("#mxs_conn button"),function(b){b.addEventListener("click",function(){B.connect(b.dataset.k).catch(function(e){var st=q("#mxs_st");if(st)st.textContent=(e&&e.name==="NotFoundError")?"No radio picked.":"Could not connect."})})});
  q("#mxs_send").addEventListener("click",function(){var t=ta.value.trim();var ch=+(q("#mxs_ch")||{}).value||0;q("#mxs_send").disabled=true;
   B.send(t,ch).then(function(){q("#mxs_st").textContent="Sent to your radio for channel "+ch+".";q("#mxs_send").textContent="Sent";setTimeout(upd,30500)})
    .catch(function(e){q("#mxs_st").textContent=e.message==="rate"?("Please wait "+e.wait+" s before the next message."):"Not sent: "+e.message;upd()})})}
 var cp=q("#mxs_copy");if(cp)cp.addEventListener("click",function(){var t=ta.value.trim();var done=function(){cp.textContent="Copied";setTimeout(function(){cp.textContent="Copy text"},1600)};
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(t).then(done,function(){ta.select();try{document.execCommand("copy");done()}catch(e){}});else{ta.select();try{document.execCommand("copy");done()}catch(e){}}});
 var sh=q("#mxs_share");if(sh)sh.addEventListener("click",function(){navigator.share({text:ta.value.trim()}).catch(function(){})});
 ta.focus()}
window.BNMeshShare={open:open,compose:function(t,u){return dev().then(function(B){return compose(B,t,u)})}};
})();
