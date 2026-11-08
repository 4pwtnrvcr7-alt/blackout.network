/* BLACKOUT.NETWORK growth enhancer (growth.py). No cookies, no trackers, no third-party scripts.
   Wire cards: thumbnail (our YouTube Short, else a Natural Earth locator map), headshots of named people, share row, full-story link.
   In-feed follow cards every 10 items, footer "Follow BLACKOUT.NETWORK" block, post-signup follow prompt, ?q= search deep link. */
(function(){"use strict";if(window.__bnGrowth)return;window.__bnGrowth=1;
var SITE="https://blackout.network",XU="https://x.com/BlkoutNtw",YT="https://www.youtube.com/@blkoutntw",YTS=YT+"?sub_confirmation=1";
var D={shorts:{},figures:[]},ready=false;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function utm(u,s,m,c){return u+(u.indexOf("?")<0?"?":"&")+"utm_source="+s+"&utm_medium="+m+"&utm_campaign="+c}
function xIntent(text,url,camp){return "https://x.com/intent/post?text="+encodeURIComponent(text.slice(0,200))+"&url="+encodeURIComponent(utm(url,"x","social",camp||"share"))+"&via=BlkoutNtw"}
var IX='<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-7.6 8.7L23 22h-6.8l-5.3-6.9L4.8 22H1.7l8.1-9.3L1 2h7l4.8 6.3L18.9 2zm-1.2 18h1.7L7.1 3.9H5.3L17.7 20z"/></svg>';
var IY='<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8zM9.7 15.1V8.9l5.8 3.1-5.8 3.1z"/></svg>';
var IM='<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm1 2.3V17h16V7.3l-8 5.3-8-5.3zM5.6 7l6.4 4.2L18.4 7H5.6z"/></svg>';
function btns(camp){return '<a class="bng-btn bng-p" href="/newsletter?utm_source=site&utm_medium=cta&utm_campaign='+camp+'">'+IM+'<span>Get the free brief</span></a>'+
 '<a class="bng-btn" href="'+XU+'" target="_blank" rel="noopener">'+IX+'<span>Follow @BlkoutNtw</span></a>'+
 '<a class="bng-btn" href="'+YTS+'" target="_blank" rel="noopener">'+IY+'<span>Subscribe on YouTube</span></a>'}
function people(text){var t=text||"",out=[];D.figures.forEach(function(f){var i=t.indexOf(f.name);if(i<0&&f.alias){var m=new RegExp("\\b"+f.alias.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"\\b").exec(t);if(m)i=m.index}if(i>=0)out.push([i,f])});
 return out.sort(function(a,b){return a[0]-b[0]}).slice(0,3).map(function(x){return x[1]})}
function findC(cid){try{if(typeof S!=="undefined"&&S){var all=(S.main||[]).concat(S.watchlist||[]);for(var i=0;i<all.length;i++)if(all[i].cluster_id===cid)return all[i]}}catch(e){}return null}
function media(c,cid,title){var s=D.shorts[cid];
 if(s&&/^[\w-]{11}$/.test(s.yt||""))return '<a class="bng-th bng-vid" href="https://www.youtube.com/shorts/'+s.yt+'" target="_blank" rel="noopener" aria-label="Watch the Short: '+esc(title)+'"><img src="https://i.ytimg.com/vi/'+s.yt+'/hqdefault.jpg" alt="'+esc(title)+' (BLACKOUT.NETWORK Short)" loading="lazy" decoding="async" width="160" height="120"><span class="bng-play" aria-hidden="true"></span><span class="bng-cr">Short · YouTube</span></a>';
 var lat=c&&c.lat,lon=c&&c.lon;if(lat==null||lon==null||isNaN(+lat))return '<span class="bng-th bng-loc bng-noloc" role="img" aria-label="Global story"><span class="bng-map"></span><span class="bng-cat">'+esc((c&&c.category)||"global")+'</span><span class="bng-cr">Map: Natural Earth</span></span>';
 var x=((+lon+180)/360).toFixed(4),y=((90-lat)/180).toFixed(4);
 return '<span class="bng-th bng-loc" style="--fx:'+x+';--fy:'+y+'" role="img" aria-label="Locator map: '+esc((c&&c.location)||"event location")+'"><span class="bng-map"></span><span class="bng-dot"></span><span class="bng-cr">Map: Natural Earth</span></span>'}
function shareRow(url,text,camp){return '<div class="bng-share" data-url="'+esc(url)+'" data-text="'+esc(text)+'"><a class="bng-sb bng-full" href="'+esc(url.replace(SITE,""))+'">Full story →</a>'+
 '<a class="bng-sb" href="'+esc(xIntent(text,url,camp))+'" target="_blank" rel="noopener">'+IX+' Post</a><button type="button" class="bng-sb bng-copy">Copy link</button>'+
 (navigator.share?'<button type="button" class="bng-sb bng-native">Share…</button>':'')+'</div>'}
function enhanceCard(el){if(el.dataset.bng)return;var cid=el.getAttribute("data-cid");if(!/^[0-9a-f]{16}$/.test(cid||""))return;el.dataset.bng=1;
 var c=findC(cid),b=el.querySelector("b"),title=(c&&c.title)||(b?b.textContent:"")||"Story",rank=c&&c.rank!=null?c.rank:null;
 var body=document.createElement("div");body.className="bng-body";Array.prototype.slice.call(el.childNodes).forEach(function(n){if(!(n.classList&&n.classList.contains("bnr-flag")))body.appendChild(n)});
 var m=document.createElement("div");m.className="bng-media";m.innerHTML=media(c,cid,title);el.insertBefore(body,el.firstChild);el.insertBefore(m,body);el.classList.add("bng-card");
 var ps=people(title+" "+((c&&c.brief)||""));if(ps.length){var p=document.createElement("div");p.className="bng-people";
  p.innerHTML=ps.map(function(f){return '<a class="bng-person" href="/#figures" title="'+esc(f.name)+' · Photo: '+esc(f.author)+', '+esc(f.license)+'"><img src="'+esc(f.img)+'" alt="'+esc(f.name)+'" width="28" height="28" loading="lazy" decoding="async" onerror="this.style.visibility=\'hidden\'"><span>'+esc(f.name)+'</span></a>'}).join("");body.appendChild(p)}
 var br=body.querySelector(".brief");if(br&&br.textContent.length>260){var mb=document.createElement("button");mb.type="button";mb.className="bng-more";mb.textContent="Read the full brief ▾";
  mb.onclick=function(){var o=br.classList.toggle("bng-open");mb.textContent=o?"Show less ▴":"Read the full brief ▾"};br.after(mb)}
 var t=title+(rank!=null?" (rank "+rank+"/10)":"")+" via BLACKOUT.NETWORK";var sh=document.createElement("div");sh.innerHTML=shareRow(SITE+"/wire/"+cid,t,"wire");body.appendChild(sh.firstChild)}
var CTAS=[["Never miss a rank 7+","The free morning and evening brief: every confirmed threat from the last 12 hours, ranked and sourced.","brief"],
 ["Watch the 60-second version","Our Shorts turn the biggest stories into maps, satellite views and plain-English narration.","yt"],
 ["Follow the live wire on X","@BlkoutNtw posts confirmed, ranked alerts as they break. No hype, every source linked.","x"]];
function ctaCard(i){var k=CTAS[i%CTAS.length],d=document.createElement("div");d.className="card bng-cta";d.setAttribute("data-bng-cta",1);
 d.innerHTML='<div class="bng-cta-k">BLACKOUT.NETWORK</div><div class="bng-cta-h">'+k[0]+'</div><p>'+k[1]+'</p><div class="bng-btns">'+btns("wire_"+k[2])+'</div>';return d}
function enhanceFeed(root){if(!root)return;var cards=root.querySelectorAll(":scope > .card[data-cid]");cards.forEach(enhanceCard);
 if(root.id!=="feed"||root.querySelector(":scope > [data-bng-cta]"))return;var n=0;
 cards.forEach(function(c,i){if((i+1)%10===0&&i+1<cards.length&&n<6){c.after(ctaCard(n++))}})}
function footer(){if(document.getElementById("bng_follow"))return;var f=document.getElementById("site_foot")||document.querySelector("footer.ft")||document.querySelector("footer");if(!f)return;
 var s=document.createElement("section");s.id="bng_follow";s.className="bng-foot";s.setAttribute("aria-labelledby","bng_follow_h");
 s.innerHTML='<h2 id="bng_follow_h">Follow BLACKOUT.NETWORK</h2><p>Signal over noise. Ranked, sourced alerts on the site, in your inbox, on X and on YouTube. Find BLACKOUT.NETWORK at <b>blackout.network</b>.</p><div class="bng-btns">'+btns("footer")+'</div>';
 f.parentNode.insertBefore(s,f)}
function thanks(el){if(!el||el.dataset.bngThanks)return;el.dataset.bngThanks=1;var d=document.createElement("div");d.className="bng-thanks";
 d.innerHTML='<b>One more step to stay ahead:</b> follow along where the stories break first.<div class="bng-btns"><a class="bng-btn bng-p" href="'+XU+'" target="_blank" rel="noopener">'+IX+'<span>Follow @BlkoutNtw on X</span></a><a class="bng-btn" href="'+YTS+'" target="_blank" rel="noopener">'+IY+'<span>Subscribe on YouTube</span></a></div>';
 el.parentNode.insertBefore(d,el.nextSibling)}
function signup(){document.querySelectorAll(".nl-result.ok").forEach(function(r){var p=r.querySelector("p");if(p)thanks(p)});
 document.querySelectorAll(".nl-msg.ok").forEach(function(m){if(m.textContent.trim().length>8){thanks(m);markSub()}})}
function share(){document.querySelectorAll(".bng-share .bng-native[hidden]").forEach(function(b){if(navigator.share)b.hidden=false})}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".bng-copy,.bng-native");if(!b)return;var w=b.closest(".bng-share"),u=w.dataset.url,t=w.dataset.text;
 if(b.classList.contains("bng-copy")){var done=function(){var o=b.textContent;b.textContent="Copied ✓";setTimeout(function(){b.textContent=o},1600)};
  if(navigator.clipboard)navigator.clipboard.writeText(u).then(done,function(){prompt("Copy this link:",u)});else prompt("Copy this link:",u)}
 else navigator.share({title:t,text:t,url:utm(u,"share","native","share")}).catch(function(){})});

/* ---- Newsletter-first growth (Matt, Nov 1 8:40 AM): engagement prompt, inline blocks, sticky bar. Signups carry source=prompt|inline_home|
   inline_story|sticky|page_<utm> (stored per subscriber by newsletter.py; aggregated for stats). localStorage only: bn_nl_sub (subscribed),
   bn_nl_dis (prompt dismissed at), bn_nl_bar (bar dismissed at), bn_pv (page views). No cookies. Mobile: bottom sheet, never full screen. */
var LS={g:function(k){try{return localStorage.getItem(k)}catch(e){return null}},s:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
var WEEK=7*864e5,isNL=/^\/newsletter/.test(location.pathname);
function subscribed(){return LS.g("bn_nl_sub")==="1"}
function markSub(){LS.s("bn_nl_sub","1");var p=document.getElementById("bng_prompt");if(p)setTimeout(function(){closePrompt(false)},15000);var b=document.getElementById("bng_bar");if(b)b.remove();document.body.classList.remove("bng-bar-on")}
var FORM=null;function getForm(){if(!FORM)FORM=fetch("/api/newsletter/form?mode=card",{cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.text()});return FORM}
var NLRE=/^[^\s@"<>(),;:\\[\]]{1,64}@[^\s@"<>(),;:\\[\]]+\.[A-Za-z]{2,63}$/;
function mountForm(box,src,cb){getForm().then(function(h){box.innerHTML=h;var f=box.querySelector("form[data-nl-form]");if(!f)throw 0;f.dataset.nlReady=1;
 var si=f.querySelector("input[name=source]");if(si)si.value=src;var em=f.querySelector("input[name=email]"),msg=f.querySelector(".nl-msg"),btn=f.querySelector("button[type=submit]");
 if(btn)btn.textContent="Get the brief";
 var ll=f.querySelector(".nl-loc-l"),li=f.querySelector(".nl-loc"),row=f.querySelector(".nl-row");
 if(ll&&li&&row&&btn){var w=document.createElement("div");w.className="bng-locrow";w.appendChild(ll);w.appendChild(li);row.after(w);w.after(btn);btn.classList.add("bng-submit");var hint=w.nextElementSibling&&w.nextElementSibling.nextElementSibling;
  li.placeholder="ZIP, city or country (optional)";var nh=f.querySelector(".nl-loc ~ .nl-sm, .bng-locrow + button + .nl-sm");if(nh)nh.classList.add("bng-lochint")}
 f.querySelectorAll("[id]").forEach(function(el){var o=el.id,n=o+"_"+src;el.id=n;var l=f.querySelector('label[for="'+o+'"]');if(l)l.htmlFor=n;f.querySelectorAll('[aria-describedby="'+o+'"]').forEach(function(x){x.setAttribute("aria-describedby",n)})});
 var say=function(t,ok){if(msg){msg.textContent=t;msg.className="nl-msg "+(ok?"ok":"err")}};
 f.addEventListener("submit",function(e){e.preventDefault();var v=(em.value||"").trim();if(!NLRE.test(v)||v.length>254){say("Enter a valid email address.");em.focus();return}
  var fd=new FormData(f),body={},cats=[].slice.call(f.querySelectorAll("input[name=interests]")),pk=cats.filter(function(c){return c.checked}).map(function(c){return c.value});
  fd.forEach(function(val,k){if(k!=="interests")body[k]=val});body.email=v;body.frequency=body.frequency||"twice";body.interests=(!pk.length||pk.length==cats.length)?["all"]:pk;body.source=src;
  var go=function(){return fetch("/api/newsletter/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),credentials:"same-origin"}).then(function(r){return r.json().catch(function(){return{}}).then(function(j){return{ok:r.ok,status:r.status,j:j}})})};
  btn.disabled=true;say("",true);
  go().then(function(r){if(r.status!==403)return r;return fetch("/api/newsletter/meta",{cache:"no-store"}).then(function(m){return m.json()}).then(function(m){body.csrf=m.csrf;var c=f.querySelector("input[name=csrf]");if(c)c.value=m.csrf;return go()})})
   .then(function(r){say((r.j&&r.j.message)||("Something went wrong ("+r.status+"). Please try again."),r.ok);if(r.ok){em.value="";markSub();if(cb)cb()}})
   .catch(function(){say("Network error. Please try again.")}).then(function(){btn.disabled=false})});
}).catch(function(){box.innerHTML='<a class="bng-btn bng-p" href="/newsletter?utm_source=site&utm_medium=cta&utm_campaign='+src+'">Get the free brief</a>'})}
function inlineBlock(src,title){var d=document.createElement("section");d.className="card bng-inline";d.setAttribute("data-bng-inline",src);d.setAttribute("aria-label","Newsletter signup");
 d.innerHTML='<div class="bng-cta-k">FREE · 7 AM &amp; 7 PM ET</div><div class="bng-cta-h">'+(title||"Get the brief: every confirmed threat, twice a day")+'</div><p>The last 12 hours, ranked 0–10 and sourced, in a 2-minute read. Double opt-in, one-click unsubscribe.</p><div class="bng-nlbox"></div>';
 mountForm(d.querySelector(".bng-nlbox"),src);return d}
function inlines(){if(subscribed()||isNL)return;var feed=document.getElementById("feed");
 if(feed&&!feed.querySelector("[data-bng-inline]")){var c=feed.querySelectorAll(":scope > .card[data-cid]");if(c.length>=3)c[2].after(inlineBlock("inline_home"))}
 document.querySelectorAll(".bng-inline-slot:not([data-done])").forEach(function(s){s.dataset.done=1;s.replaceWith(inlineBlock(s.dataset.src||"inline_story","Follow stories like this in your inbox"))})}
function closePrompt(dismissed){var p=document.getElementById("bng_prompt");if(!p)return;if(dismissed)LS.s("bn_nl_dis",String(Date.now()));p.classList.remove("bng-in");setTimeout(function(){p.remove()},300);document.removeEventListener("keydown",escK)}
function escK(e){if(e.key==="Escape")closePrompt(true)}
function mapRoot(){return document.documentElement.classList.contains("bn-map-root")}
function mapOnScreen(){
 if(mapRoot())return true;
 var el=document.getElementById("bn_sig");if(!el)return false;
 var r=el.getBoundingClientRect();
 return r.bottom>72&&r.top<window.innerHeight-24&&r.height>40}
function showMapChip(){
 if(document.getElementById("bng_mapchip")||subscribed()||isNL)return;
 var d=+LS.g("bn_nl_dis")||0;if(Date.now()-d<WEEK)return;
 var chip=document.createElement("aside");chip.id="bng_mapchip";chip.className="bng-mapchip";chip.setAttribute("role","region");chip.setAttribute("aria-label","Newsletter");
 chip.innerHTML='<p class="bng-mapchip-t"><b>Finding this useful?</b> <span>The 7 AM / 7 PM brief, ranked and sourced.</span></p><a class="bng-btn bng-p" href="/newsletter?utm_source=site&utm_medium=corner&utm_campaign=map">Get the brief</a><button type="button" class="bng-x" aria-label="Close">×</button>';
 chip.querySelector(".bng-x").onclick=function(){LS.s("bn_nl_dis",String(Date.now()));chip.remove();document.body.classList.remove("bng-chip-on")};
 document.body.classList.add("bng-chip-on");document.body.appendChild(chip)}
var shown=false;function showPrompt(){if(shown||subscribed()||isNL||location.hash==="#newsletter")return;var d=+LS.g("bn_nl_dis")||0;if(Date.now()-d<WEEK)return;
 if(document.querySelector(".bnr-back"))return;
 if(mapRoot()){showMapChip();return}
 if(mapOnScreen())return;
 shown=true;
 var p=document.createElement("aside");p.id="bng_prompt";p.className="bng-prompt";p.setAttribute("role","dialog");p.setAttribute("aria-modal","false");p.setAttribute("aria-labelledby","bng_prompt_h");
 p.innerHTML='<button type="button" class="bng-x" aria-label="Close">×</button><div class="bng-cta-k">BLACKOUT.NETWORK BRIEF</div><h2 id="bng_prompt_h">Finding this useful?</h2><p>Get the 7 AM / 7 PM brief tailored to your area: every confirmed threat from the last 12 hours, ranked and sourced. Free.</p><div class="bng-nlbox"></div><p class="bng-fine">Double opt-in · one-click unsubscribe · <a href="/privacy">Privacy</a></p><button type="button" class="bng-no">No thanks</button>';
 document.body.appendChild(p);p.querySelector(".bng-x").onclick=function(){closePrompt(true)};p.querySelector(".bng-no").onclick=function(){closePrompt(true)};
 document.addEventListener("keydown",escK);mountForm(p.querySelector(".bng-nlbox"),"prompt");requestAnimationFrame(function(){p.classList.add("bng-in")});
 var b=document.getElementById("bng_bar");if(b){b.hidden=true;document.body.classList.remove("bng-bar-on")}}
function promptTriggers(){if(subscribed()||isNL)return;var pv=(+LS.g("bn_pv")||0)+1;LS.s("bn_pv",String(pv));
 if(mapRoot()){showMapChip();return}
 setTimeout(showPrompt,pv>=2?8000:50000);
 var onS=function(){if(mapOnScreen())return;var h=document.documentElement,max=h.scrollHeight-h.clientHeight;if(max>400&&h.scrollTop/max>=.5){removeEventListener("scroll",onS);showPrompt()}};addEventListener("scroll",onS,{passive:true})}
function bar(){if(subscribed()||isNL||mapRoot()||document.getElementById("bng_bar"))return;var d=+LS.g("bn_nl_bar")||0;if(Date.now()-d<WEEK)return;
 var b=document.createElement("div");b.id="bng_bar";b.className="bng-bar";b.setAttribute("role","region");b.setAttribute("aria-label","Newsletter");
 b.innerHTML='<span class="bng-bar-t"><b>Get the free brief</b><span class="bng-bar-s"> · 7 AM &amp; 7 PM ET, ranked and sourced</span></span><a class="bng-btn bng-p" href="/newsletter?utm_source=site&utm_medium=sticky&utm_campaign=bar">Sign up</a><button type="button" class="bng-x" aria-label="Dismiss">×</button>';
 b.querySelector(".bng-x").onclick=function(){LS.s("bn_nl_bar",String(Date.now()));b.remove();document.body.classList.remove("bng-bar-on")};
 b.querySelector("a").onclick=function(e){e.preventDefault();shown=false;LS.s("bn_nl_dis","0");showPrompt();if(!document.getElementById("bng_prompt"))location.href=this.href};
 document.body.appendChild(b);var on=function(){var h=document.documentElement;if(h.scrollTop>600){removeEventListener("scroll",on);if(!document.getElementById("bng_prompt")){b.classList.add("bng-in");document.body.classList.add("bng-bar-on")}}};addEventListener("scroll",on,{passive:true})}
function nlPage(){if(!isNL)return;var m=/[?&]utm_source=([A-Za-z0-9_-]{1,12})/.exec(location.search);if(m)document.querySelectorAll("form[data-nl-form] input[name=source]").forEach(function(i){i.value="page_"+m[1].toLowerCase()});
 if(document.querySelector(".nl-result.ok")&&/confirm/.test(location.pathname))markSub()}
function scan(){if(!ready)return;inlines();["feed","watch"].forEach(function(id){enhanceFeed(document.getElementById(id))});footer();signup();share()}
function q(){var m=/[?&]q=([^&#]+)/.exec(location.search);if(!m||!window.bnMenuOpen)return;var v=decodeURIComponent(m[1].replace(/\+/g," ")).slice(0,120);
 window.bnMenuOpen({search:true});setTimeout(function(){var i=document.getElementById("bns_q");if(!i)return;i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));var f=i.closest("form");if(f&&f.requestSubmit)f.requestSubmit()},150)}
function watchMap(){function sync(){document.documentElement.classList.toggle("bn-sig-visible",mapOnScreen())}sync();addEventListener("scroll",sync,{passive:true});var el=document.getElementById("bn_sig");if(el&&"IntersectionObserver"in window)new IntersectionObserver(sync,{threshold:[0,0.2]}).observe(el)}
function start(){watchMap();fetch("/api/growth/data").then(function(r){return r.json()}).then(function(j){D=j||D}).catch(function(){}).then(function(){ready=true;scan()});
 var t=null;new MutationObserver(function(){if(t)return;t=setTimeout(function(){t=null;scan()},120)}).observe(document.body,{childList:true,subtree:true});setTimeout(q,600);nlPage();promptTriggers();bar()}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start()})();
