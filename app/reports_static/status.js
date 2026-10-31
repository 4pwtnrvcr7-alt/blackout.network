/* Public report status page. Shows ONE report by its reference ID; IDs you chose to remember live only in this browser. */
(function(){
 var $=function(i){return document.getElementById(i)},KEY="bn_report_ids";
 function el(t,a,k){var e=document.createElement(t);if(a)for(var x in a){if(x=="text")e.textContent=a[x];else e.setAttribute(x,a[x])}(k||[]).forEach(function(c){c&&e.appendChild(typeof c=="string"?document.createTextNode(c):c)});return e}
 function et(t){if(!t)return"—";var d=new Date(t);if(isNaN(d))return"—";return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"})+" ET"}
 function norm(s){s=String(s||"").replace(/[\s_]/g,"").toUpperCase().replace(/O/g,"0").replace(/[IL]/g,"1");if(/^BN[0-9A-Z]{8}$/.test(s))s="BN-"+s.slice(2,6)+"-"+s.slice(6);return s}
 function ids(){try{return JSON.parse(localStorage.getItem(KEY)||"[]").filter(function(x){return/^BN-[0-9A-Z]{4}-[0-9A-Z]{4}$/.test(x.id||"")})}catch(e){return[]}}
 function mine(){var l=ids(),ul=$("rs_mine_list");ul.innerHTML="";$("rs_mine").hidden=!l.length;
  l.forEach(function(x){var a=el("a",{href:"/report-status/"+x.id,text:x.id});a.onclick=function(e){e.preventDefault();go(x.id,true)};
   var rm=el("button",{type:"button","class":"rs-link","aria-label":"Forget "+x.id,text:"forget"});rm.onclick=function(){try{localStorage.setItem(KEY,JSON.stringify(ids().filter(function(y){return y.id!==x.id})))}catch(e){}mine()};
   ul.appendChild(el("li",null,[a," · saved "+et(x.t)+" · ",rm]))})}
 $("rs_forget").onclick=function(){try{localStorage.removeItem(KEY)}catch(e){}mine()};
 function stats(){fetch("/api/reports/stats",{cache:"no-store"}).then(function(r){return r.json()}).then(function(s){if(!s||!s.ok||!s.total)return;var c=s.counts||{},box=$("rs_stats");box.innerHTML="";
  [["open","Open"],["in_progress","In progress"],["resolved","Resolved"],["wont_fix","Won't fix"],["duplicate","Duplicate"]].forEach(function(k){box.appendChild(el("div",{"class":"rs-stat"},[el("b",{text:String(c[k[0]]||0)}),el("span",{text:k[1]})]))});
  box.appendChild(el("div",{"class":"rs-stat"},[el("b",{text:s.median_resolve_hours!=null?(s.median_resolve_hours<48?s.median_resolve_hours+" h":Math.round(s.median_resolve_hours/24)+" d"):"—"}),el("span",{text:s.median_resolve_hours!=null?"Median time to resolve":"Median time to resolve (shown after 3 resolved)"})]));
  box.hidden=false}).catch(function(){})}
 function render(r){var o=$("rs_out");o.innerHTML="";var c=el("section",{"class":"rs-card","aria-labelledby":"rs_h"});
  c.appendChild(el("h2",{id:"rs_h"},["Report ",el("code",{text:r.id})]));
  c.appendChild(el("p",null,[el("span",{"class":"rs-badge "+r.status,text:r.status_label})," ",r.status_explanation]));
  if(r.queue_position)c.appendChild(el("p",null,[el("b",{text:"Queue position: #"+r.queue_position.position+" of "+r.queue_position.of+" open"})," (reports are reviewed by priority, then oldest first)"]));
  else if(r.status=="received")c.appendChild(el("p",{"class":"rs-hint",text:"Its queue position appears once it reaches the review queue."}));
  if(r.status=="duplicate"&&r.duplicate_of){var a=el("a",{href:"/report-status/"+r.duplicate_of,text:r.duplicate_of});a.onclick=function(e){e.preventDefault();go(r.duplicate_of,true)};c.appendChild(el("p",null,["Original report: ",a]))}
  var kv=el("dl",{"class":"rs-kv"});function row(k,v){if(!v)return;kv.appendChild(el("dt",{text:k}));kv.appendChild(el("dd",{text:v}))}
  row("What you reported",r.category_label);row("Your description",r.description||"(none)");row("About the item",r.item_title);row("Page",r.page);row("Sent",et(r.submitted_at));row("Last update",et(r.updated_at));
  c.appendChild(kv);
  c.appendChild(el("h2",{text:"Response from Blackout Network"}));
  if(r.responses&&r.responses.length)r.responses.forEach(function(x){c.appendChild(el("div",{"class":"rs-resp"},[x.text,el("div",{"class":"rs-hint",text:"Published "+et(x.published_at)})]))});
  else c.appendChild(el("p",{"class":"rs-hint",text:"No written response yet. Status changes appear here as soon as they happen."}));
  c.appendChild(el("h2",{text:"Timeline"}));var tl=el("ol",{"class":"rs-tl"});(r.timeline||[]).forEach(function(t){tl.appendChild(el("li",null,[el("b",{text:t.label}),el("div",{"class":"rs-hint",text:et(t.t)})]))});c.appendChild(tl);
  var saved=ids().some(function(x){return x.id==r.id});
  if(!saved){var sv=el("button",{type:"button","class":"rs-link",text:"Remember this report on this device"});sv.onclick=function(){var l=ids();l.unshift({id:r.id,cat:r.category,t:new Date().toISOString()});try{localStorage.setItem(KEY,JSON.stringify(l.slice(0,50)))}catch(e){}sv.replaceWith(el("span",{"class":"rs-hint",text:"Saved on this device."}));mine()};c.appendChild(el("p",null,[sv]))}
  o.appendChild(c);c.setAttribute("tabindex","-1");c.focus()}
 function go(id,push){id=norm(id);$("rs_id").value=id;var o=$("rs_out");
  if(!/^BN-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$/.test(id)){o.innerHTML="";o.appendChild(el("p",{"class":"rs-err",text:"That doesn't look like a reference ID. IDs look like BN-7K2M-Q9XD."}));return}
  o.innerHTML="";o.appendChild(el("p",{"class":"rs-hint",text:"Looking it up…"}));
  if(push&&location.pathname!="/report-status/"+id)history.pushState({id:id},"","/report-status/"+id);
  fetch("/api/report/"+encodeURIComponent(id)+"/status",{cache:"no-store",credentials:"omit"}).then(function(r){return r.json().then(function(j){return[r.status,j]})}).then(function(x){
   if(x[0]==200&&x[1].ok)return render(x[1].report);o.innerHTML="";o.appendChild(el("p",{"class":"rs-err",role:"alert",text:x[1].error||"Lookup failed."}))})
  .catch(function(){o.innerHTML="";o.appendChild(el("p",{"class":"rs-err",role:"alert",text:"Network error. Please try again."}))})}
 $("rs_form").onsubmit=function(e){e.preventDefault();go($("rs_id").value,true)};
 addEventListener("popstate",function(){var m=location.pathname.match(/^\/report-status\/(.+)$/);if(m)go(decodeURIComponent(m[1]),false)});
 mine();stats();var pre=document.body.getAttribute("data-report-id");if(pre)go(pre,false);else $("rs_id").focus();
})();
