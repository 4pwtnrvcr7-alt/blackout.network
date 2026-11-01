/* BLACKOUT.NETWORK shared nav (t301/t302): tab order + grouping, per-tab <title>/meta description/Open Graph tags and the
   one-line tab description, all from sitenav.py (the data below is embedded by the server). Loaded by dashboard.html. */
(function(){"use strict";
var D=/*BN_SITENAV_DATA*/null;if(!D)return;
var byKey={},byHash={};D.tabs.forEach(function(t){byKey[t.key]=t;byHash[t.hash]=t});
function meta(attr,name,val){var m=document.head.querySelector("meta["+attr+'="'+name+'"]');if(!m){m=document.createElement("meta");m.setAttribute(attr,name);document.head.appendChild(m)}m.setAttribute("content",val)}
function setMeta(title,desc,url){if(document.title!==title)document.title=title;meta("name","description",desc);meta("property","og:title",title);
 meta("property","og:description",desc);meta("property","og:url",url);meta("name","twitter:title",title);meta("name","twitter:description",desc)}
function init(){
 var nav=document.querySelector("nav.tabs");if(!nav||!nav.querySelector("button[data-tab]"))return;
 var desc=document.getElementById("bn_tabdesc");
 if(!desc){desc=document.createElement("p");desc.id="bn_tabdesc";desc.className="bn-tabdesc";nav.parentNode.insertBefore(desc,nav.nextSibling)}
 // ---- one tab bar: groups and order from sitenav.py; tabs not listed there go at the end of the first group
 function el(t){return t.key==="@scoring"?document.getElementById("tab_howscore"):nav.querySelector('button[data-tab="'+t.key+'"]')}
 function want(){var out=[],known={};D.tabs.forEach(function(t){known[t.key]=1});
  D.groups.forEach(function(g,i){if(i)out.push("sep");if(g)out.push("grp:"+g);
   D.tabs.forEach(function(t){if(t.group===g){var e=el(t);if(e)out.push(e)}});
   if(i===0)[].forEach.call(nav.querySelectorAll("button[data-tab]"),function(b){if(!known[b.dataset.tab])out.push(b)})});
  return out}
 function sig(list){return list.map(function(x){return typeof x==="string"?x:(x.dataset&&x.dataset.tab)||x.id}).join("|")}
 function cur(){return [].map.call(nav.children,function(c){return c.classList.contains("tab-sep")?"sep":c.classList.contains("tab-grp")?"grp:"+c.textContent:c})}
 var busy=false;
 function order(){var w=want();if(sig(w)===sig(cur()))return;busy=true;var f=document.createDocumentFragment();
  w.forEach(function(x){if(typeof x!=="string")return f.appendChild(x);var s=document.createElement("span");
   if(x==="sep")s.className="tab-sep";else{s.className="tab-grp";s.textContent=x.slice(4)}f.appendChild(s)});
  [].slice.call(nav.children).forEach(function(c){if(c.classList.contains("tab-sep")||c.classList.contains("tab-grp"))c.remove()});
  nav.appendChild(f);busy=false}
 // ---- per-tab title / description
 var last="";
 function upd(){var b=nav.querySelector("button.on[data-tab]");if(!b)return;var k=b.dataset.tab,t=byKey[k],title,d,url;
  if(!t||k==="threat"){title=D.home.title;d=D.home.desc;url=D.site+"/"}
  else{title=(t.title||b.textContent.trim())+" | "+D.brand;d=t.desc||D.home.desc;url=D.site+"/#"+t.hash}
  if(!t&&k!=="threat"){title=b.textContent.replace(/^\W+/,"").trim()+" | "+D.brand}
  var line=(t&&t.desc)||D.home.desc;if(desc.textContent!==line)desc.textContent=line;
  if(title+d===last&&document.title===title)return;last=title+d;setMeta(title,d,url)}
 var tm=0;function soon(){clearTimeout(tm);tm=setTimeout(function(){if(!busy)order();upd()},60)}
 new MutationObserver(soon).observe(nav,{childList:true,subtree:true,attributes:true,attributeFilter:["class"]});
 addEventListener("hashchange",soon);addEventListener("load",soon);order();upd();setTimeout(soon,500);setTimeout(soon,2500)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init()})();
