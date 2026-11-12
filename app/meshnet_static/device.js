// BLACKOUT.NETWORK mesh device helper (window.BNMesh). Talks ONLY to the reader's own Meshtastic radio, in the browser, over
// Web Bluetooth or Web Serial, using the official @meshtastic/core JS (GPL-3.0, vendored as /api/mesh/lib.js; see /api/mesh/LICENSES.txt).
// Nothing here talks to BLACKOUT.NETWORK servers about the radio or its messages. Sending happens only from send(), which callers
// invoke from an explicit user tap after a preview. Limits: 200 bytes per message, 1 message / 30 s, 5 messages / 10 min.
(function(){"use strict";
if(window.BNMesh)return;
var MAXB=200,GAP=30000,WIN=600000,WINMAX=5,KEY="bn_mesh_sends";
var ua=navigator.userAgent||"",ios=/iPad|iPhone|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1),android=/Android/.test(ua);
function bytes(s){try{return new TextEncoder().encode(s||"").length}catch(e){return (s||"").length}}
function trimBytes(s,max){s=String(s||"");if(bytes(s)<=max)return s;var e="…";while(s&&bytes(s+e)>max)s=s.slice(0,-1);return s.replace(/\s+\S*$/,"")+e}
function sends(){try{return JSON.parse(localStorage.getItem(KEY)||"[]").filter(function(t){return Date.now()-t<WIN})}catch(e){return []}}
function rateLeft(){var s=sends();var now=Date.now();if(s.length&&now-s[s.length-1]<GAP)return {ok:false,wait:Math.ceil((GAP-(now-s[s.length-1]))/1000),why:"gap"};
 if(s.length>=WINMAX)return {ok:false,wait:Math.ceil((WIN-(now-s[0]))/1000),why:"window"};return {ok:true}}
function noteSend(){var s=sends();s.push(Date.now());try{localStorage.setItem(KEY,JSON.stringify(s))}catch(e){}}
var libP=null;
function lib(){if(window.BNMeshLib)return Promise.resolve(window.BNMeshLib);if(libP)return libP;
 libP=new Promise(function(ok,no){var s=document.createElement("script");s.src="/api/mesh/lib.js?v=1";s.onload=function(){window.BNMeshLib?ok(window.BNMeshLib):no(new Error("lib"))};s.onerror=function(){libP=null;no(new Error("lib"))};document.head.appendChild(s)});return libP}
var L={status:[],msg:[],ch:[]};function emit(k,v){L[k].forEach(function(f){try{f(v)}catch(e){}})}
var S={dev:null,tr:null,state:"disconnected",kind:null,channels:{},nodes:{},me:null};
function setState(s){S.state=s;emit("status",s)}
async function driver(kind){
 if(window.__BN_MESH_MOCK&&window.__BN_MESH_MOCK.driver)return window.__BN_MESH_MOCK.driver(kind);   // tests/screenshots only (set by the test harness)
 var M=await lib();var tr=kind==="usb"?await M.TransportWebSerial.create(115200):await M.TransportWebBluetooth.create();return {device:new M.MeshDevice(tr),transport:tr}}
async function connect(kind){
 if(S.dev&&S.state!=="disconnected")return S;
 var sup=support();if(kind==="usb"?!sup.serial:!sup.bt)throw new Error("unsupported");
 setState("connecting");S.kind=kind;S.channels={};S.nodes={};
 var r;try{r=await driver(kind)}catch(e){setState("disconnected");throw e}
 var d=r.device;S.dev=d;S.tr=r.transport;
 d.onDeviceStatus.subscribe(function(st){if(st===7)setState("ready");else if(st===2)setState("disconnected");else if(st===6&&S.state!=="ready")setState("configuring")});
 d.onMyNodeInfo.subscribe(function(i){S.me=i&&i.myNodeNum});
 d.onNodeInfoPacket.subscribe(function(n){if(n&&n.num!=null&&n.user)S.nodes[n.num]={short:n.user.shortName||"",long:n.user.longName||""}});
 d.onChannelPacket.subscribe(function(c){if(!c)return;var role=c.role||0;if(role===0){delete S.channels[c.index];emit("ch",chList());return}
  var nm=(c.settings&&c.settings.name)||"";S.channels[c.index]={index:c.index,primary:role===1,name:nm||(role===1?"Primary (default LongFast)":"Channel "+c.index)};emit("ch",chList())});
 d.onMessagePacket.subscribe(function(p){if(!p)return;var who=S.nodes[p.from]||{};
  emit("msg",{id:p.id,from:p.from,fromName:who.long||who.short||("!"+(p.from>>>0).toString(16).padStart(8,"0").slice(-4)),to:p.to,channel:p.channel,type:p.type,text:String(p.data||"").slice(0,500),
   t:p.rxTime instanceof Date?p.rxTime:new Date(),mine:S.me!=null&&p.from===S.me})});
 try{await d.configure()}catch(e){}
 if(kind==="usb"&&d.setHeartbeatInterval)try{d.setHeartbeatInterval(60000)}catch(e){}   // serial keep-alive to the local radio only (not sent over the air)
 if(S.state==="connecting")setState("configuring");
 return S}
function chList(){return Object.keys(S.channels).map(function(k){return S.channels[k]}).sort(function(a,b){return a.index-b.index})}
async function send(text,channel){
 if(!S.dev||S.state==="disconnected")throw new Error("not connected");
 text=String(text||"").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g,"").trim();
 if(!text)throw new Error("empty");if(bytes(text)>MAXB)throw new Error("too long");
 var rl=rateLeft();if(!rl.ok){var e=new Error("rate");e.wait=rl.wait;throw e}
 noteSend();
 var id=await S.dev.sendText(text,"broadcast",true,+channel||0);
 emit("msg",{id:id,from:S.me,fromName:"You",channel:+channel||0,type:"broadcast",text:text,t:new Date(),mine:true});return id}
async function disconnect(){try{if(S.dev)await S.dev.disconnect()}catch(e){}S.dev=null;S.tr=null;setState("disconnected")}
function support(){return {bt:!!(navigator.bluetooth&&navigator.bluetooth.requestDevice),serial:!!(navigator.serial&&navigator.serial.requestPort),ios:ios,android:android,
 any:!!((navigator.bluetooth&&navigator.bluetooth.requestDevice)||(navigator.serial&&navigator.serial.requestPort))}}
window.BNMesh={MAX_BYTES:MAXB,bytes:bytes,trimBytes:trimBytes,support:support,connect:connect,send:send,disconnect:disconnect,rateLeft:rateLeft,
 channels:chList,state:function(){return S.state},on:function(k,f){if(L[k])L[k].push(f)},
 IOS_APP:"https://apps.apple.com/us/app/meshtastic/id1586432531",ANDROID_APP:"https://play.google.com/store/apps/details?id=com.geeksville.mesh",
 // Documented app links: iOS meshtastic:///messages (opens Messages; no text parameter is documented), Android meshtastic://meshtastic/share?message=
 IOS_OPEN:"meshtastic:///messages",androidShare:function(t){return "meshtastic://meshtastic/share?message="+encodeURIComponent(t)}};
})();
