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
  p.innerHTML=ps.map(function(f){return '<a class="bng-person" href="/#figures" title="'+esc(f.name)+' · Photo: '+esc(f.author)+', '+esc(f.license)+'"><img src="'+esc(f.img)+'" alt="'+esc(f.name)+'" width="28" height="28" loading="lazy" decoding="async"><span>'+esc(f.name)+'</span></a>'}).join("");body.appendChild(p)}
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
 s.innerHTML='<h2 id="bng_follow_h">Follow BLACKOUT.NETWORK</h2><p>Ask better questions. Ranked, sourced alerts on the site, in your inbox, on X and on YouTube. Our full address is <b>blackout.network</b>, no .com.</p><div class="bng-btns">'+btns("footer")+'</div>';
 f.parentNode.insertBefore(s,f)}
function thanks(el){if(!el||el.dataset.bngThanks)return;el.dataset.bngThanks=1;var d=document.createElement("div");d.className="bng-thanks";
 d.innerHTML='<b>One more step to stay ahead:</b> follow along where the stories break first.<div class="bng-btns"><a class="bng-btn bng-p" href="'+XU+'" target="_blank" rel="noopener">'+IX+'<span>Follow @BlkoutNtw on X</span></a><a class="bng-btn" href="'+YTS+'" target="_blank" rel="noopener">'+IY+'<span>Subscribe on YouTube</span></a></div>';
 el.parentNode.insertBefore(d,el.nextSibling)}
function signup(){document.querySelectorAll(".nl-result.ok").forEach(function(r){var p=r.querySelector("p");if(p)thanks(p)});
 document.querySelectorAll(".nl-msg.ok").forEach(function(m){if(m.textContent.trim().length>8)thanks(m)})}
function share(){document.querySelectorAll(".bng-share .bng-native[hidden]").forEach(function(b){if(navigator.share)b.hidden=false})}
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".bng-copy,.bng-native");if(!b)return;var w=b.closest(".bng-share"),u=w.dataset.url,t=w.dataset.text;
 if(b.classList.contains("bng-copy")){var done=function(){var o=b.textContent;b.textContent="Copied ✓";setTimeout(function(){b.textContent=o},1600)};
  if(navigator.clipboard)navigator.clipboard.writeText(u).then(done,function(){prompt("Copy this link:",u)});else prompt("Copy this link:",u)}
 else navigator.share({title:t,text:t,url:utm(u,"share","native","share")}).catch(function(){})});
function scan(){if(!ready)return;["feed","watch"].forEach(function(id){enhanceFeed(document.getElementById(id))});footer();signup();share()}
function q(){var m=/[?&]q=([^&#]+)/.exec(location.search);if(!m||!window.bnMenuOpen)return;var v=decodeURIComponent(m[1].replace(/\+/g," ")).slice(0,120);
 window.bnMenuOpen({search:true});setTimeout(function(){var i=document.getElementById("bns_q");if(!i)return;i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));var f=i.closest("form");if(f&&f.requestSubmit)f.requestSubmit()},150)}
function start(){fetch("/api/growth/data").then(function(r){return r.json()}).then(function(j){D=j||D}).catch(function(){}).then(function(){ready=true;scan()});
 var t=null;new MutationObserver(function(){if(t)return;t=setTimeout(function(){t=null;scan()},120)}).observe(document.body,{childList:true,subtree:true});setTimeout(q,600)}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start()})();
