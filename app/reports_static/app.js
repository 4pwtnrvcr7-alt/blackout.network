/* blackout.network "Report a problem" widget (served by reports.py; injected on every dashboard page).
   Captures only what the preview shows. No cookies, localStorage values, form contents or tokens are read; page URLs are
   sent without query strings. The only thing stored in this browser is the list of your own report IDs (if you opt in). */
(function(){
 if(window.BNReport)return;
 var ERR=(window.__bnErr=window.__bnErr||[]),MAXE=10,KEY="bn_report_ids",CFG=null,LAST=null,opened=0,trig=null;
 function clip(s,n){s=String(s==null?"":s);return s.length>n?s.slice(0,n)+"…":s}
 function scrub(s){return clip(String(s||"").replace(/https?:\/\/[^\s)'"]+/g,function(u){return u.split(/[?#]/)[0]}).replace(/[A-Za-z0-9_\-]{32,}/g,"[redacted]"),300)}
 function pushErr(o){ERR.push(o);while(ERR.length>MAXE)ERR.shift()}
 if(!window.__bnErrHooked){window.__bnErrHooked=1;
  addEventListener("error",function(e){if(e.target&&e.target!==window&&e.target.tagName){pushErr({kind:"resource",msg:"Failed to load "+e.target.tagName.toLowerCase(),src:String(e.target.src||e.target.href||"").split(/[?#]/)[0],t:new Date().toISOString()});return}
   pushErr({kind:"error",msg:scrub(e.message||"error"),src:String(e.filename||"").split(/[?#]/)[0],line:e.lineno||null,t:new Date().toISOString()})},true);
  addEventListener("unhandledrejection",function(e){var r=e.reason;pushErr({kind:"unhandledrejection",msg:scrub(r&&r.message?r.message:String(r)),t:new Date().toISOString()})})}
 function errs(){return ERR.slice(-MAXE).map(function(e){return{kind:e.kind||"error",msg:scrub(e.msg),src:String(e.src||"").split(/[?#]/)[0],line:e.line||null,t:e.t||null}})}
 function el(t,a,k){var e=document.createElement(t);if(a)for(var x in a){if(x=="text")e.textContent=a[x];else if(x=="html")e.innerHTML=a[x];else e.setAttribute(x,a[x])}(k||[]).forEach(function(c){c&&e.appendChild(typeof c=="string"?document.createTextNode(c):c)});return e}
 var FLAG='<svg viewBox="0 0 16 16" width="14" height="14" style="width:14px;height:14px;flex:none" aria-hidden="true"><path d="M3 1h1.5v14H3zM5 2h8l-2 3.5L13 9H5z"/></svg>';
 function ids(){try{return JSON.parse(localStorage.getItem(KEY)||"[]").filter(function(x){return/^BN-[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(x.id||"")})}catch(e){return[]}}
 function remember(id,cat){var l=ids().filter(function(x){return x.id!==id});l.unshift({id:id,cat:cat,t:new Date().toISOString()});try{localStorage.setItem(KEY,JSON.stringify(l.slice(0,50)))}catch(e){}}
 function activeTab(){var b=document.querySelector(".tabs button.on");return b?(b.getAttribute("data-tab")||""):""}
 function lastScan(){try{if(typeof S!="undefined"&&S&&S.scans&&S.scans[0])return String(S.scans[0].finished||"")}catch(e){}var s=document.getElementById("status");return s?clip(s.textContent,80):""}
 function context(){return{url:location.origin+location.pathname,hash:(location.hash||"").split(/[?&=]/)[0].slice(0,60),tab:activeTab(),client_time:new Date().toISOString(),
  user_agent:clip(navigator.userAgent,400),viewport:{w:innerWidth,h:innerHeight,dpr:Math.round((devicePixelRatio||1)*100)/100},language:clip(navigator.language||"",35),
  timezone:(Intl.DateTimeFormat().resolvedOptions().timeZone||"").slice(0,64),build:CFG?CFG.build:"",last_scan_shown:lastScan(),online:navigator.onLine,js_errors:errs()}}
 function loadCfg(){if(CFG)return Promise.resolve(CFG);return fetch("/api/report/config",{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){CFG=j;return j})}
 // ---------- dialog
 var back=el("div",{"class":"bnr-back",hidden:""}),dlg=el("div",{"class":"bnr-dlg",role:"dialog","aria-modal":"true","aria-labelledby":"bnr_title"});back.appendChild(dlg);
 var item=null;
 function close(){back.hidden=true;document.removeEventListener("keydown",onKey,true);if(trig&&trig.focus)trig.focus()}
 function onKey(e){if(e.key=="Escape"){e.preventDefault();close()}else if(e.key=="Tab"){var f=[].slice.call(dlg.querySelectorAll("button,select,textarea,input:not([tabindex='-1']),a[href]")).filter(function(x){return!x.disabled&&x.offsetParent!==null});if(!f.length)return;var a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}}}
 function head(t){dlg.innerHTML="";var x=el("button",{"class":"bnr-x",type:"button","aria-label":"Close"},["×"]);x.onclick=close;dlg.appendChild(x);dlg.appendChild(el("h2",{id:"bnr_title",text:t}))}
 function show(){if(!back.parentNode)document.body.appendChild(back);back.hidden=false;document.addEventListener("keydown",onKey,true);setTimeout(function(){var f=dlg.querySelector("select,textarea,button.pri");f&&f.focus()},30)}
 function form(prev){head("Report a problem");
  dlg.appendChild(el("p",{"class":"bnr-meta",text:"Tell us what went wrong. Reports go to the blackout.network review queue; you'll get a reference ID to check on it."}));
  var f=el("form",{novalidate:""}),cat=el("select",{id:"bnr_cat",required:""});cat.appendChild(el("option",{value:"",text:"Choose one…"}));
  CFG.categories.forEach(function(c){cat.appendChild(el("option",{value:c.id,text:c.label}))});
  f.appendChild(el("label",{"for":"bnr_cat",text:"What kind of problem?"}));f.appendChild(cat);
  if(item){var ib=el("div",{"class":"bnr-item",id:"bnr_item"},[el("b",{text:"About this item: "}),document.createTextNode(item.title||item.id||"")]);
   if(item.source_url)ib.appendChild(el("div",{"class":"bnr-meta",text:"Source: "+item.source_url}));
   if(item.id)ib.appendChild(el("div",{"class":"bnr-meta",text:"Alert ID: "+item.id}));
   var rm=el("button",{type:"button","class":"bnr-link",text:"Not about this item"});rm.onclick=function(){item=null;ib.remove()};ib.appendChild(rm);f.appendChild(ib);
   if(!prev)cat.value="wrong_data"}
  var max=CFG.limits.description,ta=el("textarea",{id:"bnr_desc",maxlength:String(max),"aria-describedby":"bnr_cnt",placeholder:"What did you see? What did you expect? (optional)"});
  f.appendChild(el("label",{"for":"bnr_desc",text:"Describe it (optional)"}));f.appendChild(ta);var cnt=el("div",{"class":"bnr-meta",id:"bnr_cnt","aria-live":"polite"});f.appendChild(cnt);
  function upd(){cnt.textContent=ta.value.length+" / "+max+" characters"}ta.oninput=upd;
  var hp=el("div",{"class":"bnr-hp","aria-hidden":"true"},[el("label",{"for":"bnr_web",text:"Leave this empty"}),el("input",{type:"text",id:"bnr_web",name:"website",tabindex:"-1",autocomplete:"off"})]);f.appendChild(hp);
  if(prev){cat.value=prev.category;ta.value=prev.description}upd();
  f.appendChild(el("div",{"class":"bnr-note"},[el("b",{text:"Privacy: "}),document.createTextNode(CFG.privacy+" ")]));
  var er=el("div",{"class":"bnr-err",role:"alert"});f.appendChild(er);
  var lk=el("a",{href:"/report-status",text:"Check an earlier report",target:"_blank",rel:"noopener"});
  var row=el("div",{"class":"bnr-row"},[el("span",{"class":"bnr-meta",style:"margin-right:auto;align-self:center"},[lk]),el("button",{type:"button","class":"bnr-btn",text:"Cancel"}),el("button",{type:"submit","class":"bnr-btn pri",text:"Review what will be sent →"})]);
  row.children[1].onclick=close;f.appendChild(row);
  f.onsubmit=function(e){e.preventDefault();if(!cat.value){er.textContent="Please choose what kind of problem it is.";cat.focus();return}
   if(!ta.value.trim()&&!item&&(cat.value=="suggestion"||cat.value=="other")){er.textContent="Please add a short description.";ta.focus();return}
   preview({category:cat.value,description:ta.value.trim(),website:document.getElementById("bnr_web").value})};
  dlg.appendChild(f);show()}
 function preview(p){var body={category:p.category,description:p.description,item:item||{},context:context(),website:p.website||"",elapsed_ms:Date.now()-opened};
  head("Check what will be sent");
  dlg.appendChild(el("p",{text:"This is exactly what your browser will send. Nothing else is attached."}));
  var shown={category:body.category,description:body.description,item:body.item,context:body.context};
  dlg.appendChild(el("pre",{"class":"bnr-pre",tabindex:"0","aria-label":"Report contents",text:JSON.stringify(shown,null,2)}));
  dlg.appendChild(el("p",{"class":"bnr-meta",text:"The server adds the time it received this, which site received it and a daily-rotating anonymous hash used only to stop spam. Page addresses never include query strings."}));
  var rem=el("input",{type:"checkbox",id:"bnr_rem"});rem.checked=true;
  dlg.appendChild(el("label",{"class":"bnr-chk","for":"bnr_rem"},[rem,document.createTextNode("Remember this report's ID on this device (stored only in this browser)")]));
  var er=el("div",{"class":"bnr-err",role:"alert"});dlg.appendChild(er);
  var bk=el("button",{type:"button","class":"bnr-btn",text:"← Edit"}),go=el("button",{type:"button","class":"bnr-btn pri",text:"Send report"});
  bk.onclick=function(){form(p)};dlg.appendChild(el("div",{"class":"bnr-row"},[bk,go]));
  go.onclick=function(){go.disabled=true;go.textContent="Sending…";er.textContent="";
   fetch("/api/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),credentials:"omit",cache:"no-store"})
   .then(function(r){return r.json().then(function(j){return[r.status,j]})}).then(function(x){var j=x[1];
    if(x[0]!=200||!j.ok){er.textContent=j.error||("Could not send (HTTP "+x[0]+"). Please try again.");go.disabled=false;go.textContent="Send report";return}
    if(rem.checked)remember(j.id,body.category);done(j)}).catch(function(){er.textContent="Network error: the report was not sent. Check your connection and try again.";go.disabled=false;go.textContent="Send report"})};
  show();go.focus()}
 function done(j){head("Thanks, your report was sent");LAST=j.id;
  dlg.appendChild(el("p",{text:"Your reference ID:"}));dlg.appendChild(el("div",{"class":"bnr-id",id:"bnr_ref",text:j.id}));
  var cp=el("button",{type:"button","class":"bnr-btn",text:"Copy ID"});cp.onclick=function(){(navigator.clipboard?navigator.clipboard.writeText(j.id):Promise.reject()).then(function(){cp.textContent="Copied ✓"}).catch(function(){var r=document.createRange();r.selectNodeContents(document.getElementById("bnr_ref"));getSelection().removeAllRanges();getSelection().addRange(r);cp.textContent="Selected: press Ctrl+C"})};
  var st=el("a",{"class":"bnr-btn pri",href:"/report-status/"+encodeURIComponent(j.id),target:"_blank",rel:"noopener",text:"Check its status →",style:"text-decoration:none"});
  dlg.appendChild(el("p",{"class":"bnr-meta",text:"Status: "+(j.status_label||j.status)+". Keep this ID: it's the only way to look the report up. Anyone with the ID can see this report's description and status."}));
  var cl=el("button",{type:"button","class":"bnr-btn",text:"Close"});cl.onclick=close;
  dlg.appendChild(el("div",{"class":"bnr-row"},[cp,st,cl]));show();st.focus()}
 function open(it,from){trig=from||document.activeElement;item=it||null;opened=Date.now();
  loadCfg().then(function(){form(null)}).catch(function(){head("Report a problem");dlg.appendChild(el("p",{text:"The report form could not load. Please try again in a moment."}));show()})}
 // ---------- floating button
 function fab(){if(document.querySelector(".bnr-fab"))return;var b=el("button",{type:"button","class":"bnr-fab","aria-haspopup":"dialog",title:"Report a problem with this page",
   style:"position:fixed;left:12px;bottom:12px;z-index:4900;display:inline-flex;align-items:center;gap:6px;max-width:220px;font:500 12px/1.2 Inter,system-ui,sans-serif"});   /* t347: inline basics so it stays small even if app.css fails to load */
  b.innerHTML=FLAG+'<span class="bnr-fab-t">Report a problem</span><span class="bnr-sr"> with this page</span>';b.onclick=function(){open(null,b)};document.body.appendChild(b)}
 // ---------- flag control on alert cards (The Wire, Watchlist, Timeline)
 function itemFor(card){var cid=card.getAttribute("data-cid")||"",d=null,kind="card";
  try{if(typeof S!="undefined"&&S){d=(S.main||[]).find(function(c){return c.cluster_id==cid});if(d)kind="wire";else{d=(S.watchlist||[]).find(function(c){return c.cluster_id==cid});if(d)kind="watchlist"}}}catch(e){}
  if(card.classList.contains("tl-card"))kind="timeline";
  var a=card.querySelector("a[href^='http']"),t=card.querySelector("b");
  return{id:cid,title:clip(d?d.title:(t?t.textContent:""),300),source_url:d&&d.links&&d.links[0]?d.links[0].url:(a?a.href:""),kind:kind}}
 function flags(root){(root||document).querySelectorAll(".card[data-cid],.tl-card[data-cid]").forEach(function(c){if(c.querySelector(":scope > .bnr-flag"))return;
  var t=c.querySelector("b"),b=el("button",{type:"button","class":"bnr-flag","aria-haspopup":"dialog",title:"Report a problem with this item","aria-label":"Report a problem with: "+clip(t?t.textContent:"this item",80)});
  b.innerHTML=FLAG;b.onclick=function(e){e.preventDefault();e.stopPropagation();open(itemFor(c),b)};c.classList.add("bnr-has-flag");c.appendChild(b)})}
 var pend=0;function sched(){if(pend)return;pend=setTimeout(function(){pend=0;flags()},150)}
 function init(){fab();flags();new MutationObserver(sched).observe(document.body,{childList:true,subtree:true})}
 window.BNReport={open:open,ids:ids,last:function(){return LAST},_context:context};
 if(document.readyState=="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
