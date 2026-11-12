// BLACKOUT.NETWORK /mesh/chat: live channel chat through the reader's own radio (window.BNMesh) + optional read-only public feed.
// Messages live only in this page's memory. Nothing is posted to our servers.
(function(){"use strict";
var $=function(s){return document.querySelector(s)};
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function hm(d){try{return d.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit"})}catch(e){return ""}}
var M=[],MAXM=200,chSel=0;
function start(){var B=window.BNMesh;if(!B)return;var sup=B.support();
 var st=$("#mx_support_status");
 if(sup.any){st.textContent="This browser can connect to a radio"+(sup.bt&&sup.serial?" by Bluetooth or USB.":sup.bt?" by Bluetooth.":" by USB.");
  $("#mx_bt").disabled=!sup.bt;$("#mx_usb").disabled=!sup.serial;if(!sup.bt)$("#mx_bt").title="Bluetooth is not available in this browser";if(!sup.serial)$("#mx_usb").title="USB is not available in this browser"}
 else{document.documentElement.classList.add("mx-nodev");
  st.innerHTML=sup.ios?'This iPhone or iPad cannot connect a radio from a web page. You can read the public feed below; to reply, use the <a href="'+B.IOS_APP+'" target="_blank" rel="noopener">Meshtastic app</a>.'
   :'This browser cannot connect to a radio. Use Chrome or Edge, or the official Meshtastic app. You can still read the public feed below.';
  $("#mx_text").placeholder="Replying needs the Meshtastic app, or Chrome or Edge";$("#mx_cstat").textContent="Not available in this browser."}
 B.on("status",function(s){var t={connecting:"Connecting… pick your radio in the browser prompt.",configuring:"Connected. Reading channels…",ready:"Connected.",disconnected:"Not connected."}[s]||s;
  $("#mx_cstat").textContent=t;var on=s==="ready"||s==="configuring";$("#mx_disc").hidden=!on;$("#mx_bt").hidden=on;$("#mx_usb").hidden=on;
  $("#mx_text").disabled=!on;$("#mx_ch").disabled=!on;upd();if(on&&M.length===0)$("#mx_msgs").innerHTML='<li class="mx-mu mx-empty">Connected. New messages on your channels show up here.</li>'});
 B.on("ch",function(list){var sel=$("#mx_ch");sel.innerHTML=list.map(function(c){return '<option value="'+c.index+'"'+(c.index===chSel?" selected":"")+'>'+esc(c.name)+(c.primary?"":" (ch "+c.index+")")+'</option>'}).join("")||'<option value="0">Primary (channel 0)</option>'});
 B.on("msg",function(m){M.push(m);if(M.length>MAXM)M.shift();render()});
 $("#mx_ch").addEventListener("change",function(e){chSel=+e.target.value;render()});
 function go(kind){B.connect(kind).catch(function(e){$("#mx_cstat").textContent=(e&&e.name==="NotFoundError")?"No radio picked.":"Could not connect"+(e&&e.message?" ("+e.message+")":"")+"."})}
 $("#mx_bt").addEventListener("click",function(){go("bt")});$("#mx_usb").addEventListener("click",function(){go("usb")});
 $("#mx_disc").addEventListener("click",function(){B.disconnect()});
 $("#mx_text").addEventListener("input",upd);
 $("#mx_form").addEventListener("submit",function(e){e.preventDefault();var t=$("#mx_text").value.trim();if(!t)return;var btn=$("#mx_send");btn.disabled=true;
  B.send(t,chSel).then(function(){$("#mx_text").value="";$("#mx_rate").textContent="Sent to your radio. Next message in 30 seconds.";upd();setTimeout(upd,30500)})
   .catch(function(err){$("#mx_rate").textContent=err.message==="rate"?("Please wait "+err.wait+" s before the next message (mesh etiquette)."):err.message==="too long"?"That message is over 200 bytes.":"Not sent: "+err.message;upd()})});
 pub();setInterval(function(){if(!document.hidden)pub()},30000)}
function upd(){var B=window.BNMesh,t=$("#mx_text").value,n=B.bytes(t),on=B.state()==="ready"||B.state()==="configuring",rl=B.rateLeft();
 $("#mx_count").textContent=n+" / "+B.MAX_BYTES+" bytes";$("#mx_count").classList.toggle("mx-over",n>B.MAX_BYTES);
 $("#mx_send").disabled=!on||!t.trim()||n>B.MAX_BYTES||!rl.ok}
function render(){var L=M.filter(function(m){return m.type==="direct"||m.channel===chSel});var ol=$("#mx_msgs");
 if(!L.length){ol.innerHTML='<li class="mx-mu mx-empty">No messages on this channel yet.</li>';return}
 ol.innerHTML=L.slice(-80).map(function(m){return '<li class="mx-m'+(m.mine?" mine":"")+'"><span class="mx-who">'+esc(m.fromName)+(m.type==="direct"?' <em>direct</em>':"")+'</span><span class="mx-when">'+esc(hm(m.t))+'</span><p>'+esc(m.text)+'</p></li>'}).join("");
 ol.scrollTop=ol.scrollHeight}
async function pub(){var note=$("#mx_pub_note"),ol=$("#mx_pub_msgs");try{var r=await fetch("/api/mesh/chat",{cache:"no-store"});var d=await r.json();
 if(!d.enabled){note.textContent=d.note||"The public feed is off.";ol.innerHTML="";return}
 note.innerHTML=esc(d.note)+' Source: <a href="'+esc(d.source_url)+'" target="_blank" rel="noopener">'+esc(d.source)+'</a>'+(d.error?" · "+esc(d.error):"");
 ol.innerHTML=(d.messages||[]).map(function(m){return '<li class="mx-m"><span class="mx-who">'+esc(m.from)+(m.ch?' · '+esc(m.ch):"")+'</span><span class="mx-when">'+esc(hm(new Date(m.t)))+'</span><p>'+esc(m.text)+'</p></li>'}).join("")||'<li class="mx-mu mx-empty">No public messages right now.</li>'}
 catch(e){note.textContent="The public feed is unavailable right now."}}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start();
})();
