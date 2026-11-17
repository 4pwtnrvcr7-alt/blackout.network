/* "/" onboarding behaviour: lazy background loops, section pager, live numbers, language rotator, menu, newsletter options. */
(function(){
var d=document,$=function(id){return d.getElementById(id)},V=window.BNT_MEDIA_V||"1";
var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var secs=[].slice.call(d.querySelectorAll(".h-sec"));
var portrait=function(){return innerWidth<=900||innerHeight>innerWidth};
var sfx=portrait()?"m":"d",media=function(k,ext){return "/bnt/media/"+k+"-"+sfx+"."+ext+"?v="+V};
/* posters, credits, pager */
var pager=$("h_pager");
secs.forEach(function(s,i){var k=s.getAttribute("data-clip");s.style.backgroundImage="url("+media(k,"jpg")+")";
 var b=d.createElement("button");b.type="button";b.setAttribute("aria-label","Go to section "+(i+1));b.onclick=function(){if(window.BNSnap)BNSnap.go(i);else s.scrollIntoView({behavior:reduce?"auto":"smooth"})};pager.appendChild(b)});
function mount(s){if(reduce||s.querySelector("video"))return;var k=s.getAttribute("data-clip"),v=d.createElement("video");
 v.muted=true;v.defaultMuted=true;v.loop=true;v.playsInline=true;v.setAttribute("playsinline","");v.setAttribute("muted","");v.setAttribute("aria-hidden","true");v.preload="auto";v.poster=media(k,"jpg");
 v.src=media(k,"mp4");v.addEventListener("playing",function(){v.classList.add("on")},{once:true});s.insertBefore(v,s.firstChild)}
var nav=$("h_nav");
if("IntersectionObserver" in window){
 var near=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)mount(e.target)})},{rootMargin:"100% 0px"});
 var vis=new IntersectionObserver(function(es){es.forEach(function(e){var s=e.target,v=s.querySelector("video");
  if(e.isIntersecting){s.classList.add("in");var i=secs.indexOf(s);[].forEach.call(pager.children,function(b,j){b.classList.toggle("on",j===i)});nav.classList.toggle("solid",i>0);if(v){var go=function(){if(s.getBoundingClientRect().bottom>0&&s.getBoundingClientRect().top<innerHeight){var p=v.play();if(p&&p.catch)p.catch(function(){})}};if(d.documentElement.classList.contains("bn-snapping"))addEventListener("bnsnap:end",go,{once:true});else go()}}
  else if(v)v.pause()})},{threshold:.5});
 secs.forEach(function(s){near.observe(s);vis.observe(s)});
}else secs.forEach(function(s){s.classList.add("in")});
/* rank bar */
var bar=$("h_bar");if(bar){var h="";for(var i=0;i<=10;i++)h+='<i style="background:'+(i>=7?"#E5484D":"#fff")+';opacity:'+(i>=7?1:.18+i*.1)+'"></i>';bar.innerHTML=h}
/* live numbers */
function fmtAgo(iso){try{var m=Math.round((Date.now()-new Date(iso).getTime())/60000);return m<1?"just now":m<60?m+" min ago":Math.round(m/60)+" h ago"}catch(e){return""}}
fetch("/api/live/summary",{cache:"no-store"}).then(function(r){return r.json()}).then(function(S){if(!S||!S.wire)return;
 $("h_n_wire").textContent=S.wire;$("h_n_src").textContent=S.sources_ok+"/"+S.sources_total;$("h_n_high").textContent=S.bands.high;
 $("h_asof").innerHTML="<i></i>Live: last scan "+S.last_scan_et+(S.last_scan?" ("+fmtAgo(S.last_scan)+")":"")}).catch(function(){});
/* language rotator */
var L=[["English","Free for everyone<br>on the planet","ltr"],["Español","Gratis para todos<br>en el planeta","ltr"],["Français","Gratuit pour tous<br>sur la planète","ltr"],["Português","Grátis para todos<br>no planeta","ltr"],["Deutsch","Kostenlos für alle<br>auf der Welt","ltr"],["Українська","Безкоштовно<br>для всіх","ltr"],["हिन्दी","सबके लिए<br>मुफ़्त","ltr"],["العربية","مجاني للجميع<br>في كل مكان","rtl"]];
var rot=$("h_rot"),langs=$("h_langs"),li=0;
langs.innerHTML=L.map(function(l,i){return '<span lang="'+["en","es","fr","pt","de","uk","hi","ar"][i]+'" class="'+(i?"":"on")+'">'+l[0]+"</span>"}).join("");
if(!reduce)setInterval(function(){if(!$("s5").classList.contains("in")||d.documentElement.className.indexOf("translated")>=0)return;rot.classList.add("out");setTimeout(function(){li=(li+1)%L.length;rot.innerHTML=L[li][1];rot.dir=L[li][2];[].forEach.call(langs.children,function(c,j){c.classList.toggle("on",j===li)});rot.classList.remove("out")},450)},2800);
$("h_lang_btn").addEventListener("click",function(e){var s=d.querySelector(".bntr-sel");if(s){e.preventDefault();s.scrollIntoView({block:"center",behavior:reduce?"auto":"smooth"});setTimeout(function(){s.focus()},400)}});
/* newsletter: more options */
var mo=$("h_moreopt"),box=$("nl_app");if(mo)mo.addEventListener("click",function(){var o=!box.classList.contains("more");box.classList.toggle("more",o);mo.setAttribute("aria-expanded",o?"true":"false");mo.textContent=o?"Fewer options":"More options: how often, your area, topics"});
/* extra layers */
var inst=$("h_install");if(inst)inst.addEventListener("click",function(){if(window.BN&&BN.showInstallGuide)BN.showInstallGuide();else location.href="/live"});
/* remember: skip the intro next time */
var sk=$("h_skip");if(sk)try{sk.checked=localStorage.getItem("bn_skip_intro")==="1"}catch(e){}
if(sk)sk.addEventListener("change",function(){try{localStorage.setItem("bn_skip_intro",sk.checked?"1":"0")}catch(e){}});
/* slide-out menu: header burger toggles, icon falls into an X, items rise in / fall out */
var menu=$("h_menu"),scrim=$("h_scrim"),last=null,hxBtn=d.querySelector(".h-burger"),closing=false,ct=0;
function hx(on){if(hxBtn){hxBtn.setAttribute("data-bn-hx",on?"open":"close");hxBtn.setAttribute("aria-label",on?"Close menu":"Open menu")}}
function finish(on){closing=false;if(ct){clearTimeout(ct);ct=0}menu.classList.toggle("open",on);menu.classList.remove("h-closing");scrim.classList.toggle("on",on);menu.setAttribute("aria-hidden",on?"false":"true");
 if(nav)nav.classList.toggle("h-open",on);
 [].forEach.call(d.querySelectorAll("[data-h-menu]"),function(b){b.setAttribute("aria-expanded",on?"true":"false");if(b.classList.contains("h-burger"))b.setAttribute("aria-label",on?"Close menu":"Open menu")});
 if(on){last=d.activeElement;try{hxBtn&&hxBtn.focus({preventScroll:true})}catch(e){}}else if(last&&last.focus)try{last.focus({preventScroll:true})}catch(e){}}
function open(on){if(ct){clearTimeout(ct);ct=0}
 if(on){if(closing)menu.classList.remove("h-closing");hx(true);finish(true);return}
 if(!menu.classList.contains("open")&&!closing)return;
 hx(false);if(reduce){finish(false);return}
 closing=true;menu.classList.add("h-closing");if(nav)nav.classList.add("h-open");
 ct=setTimeout(function(){finish(false)},680)}
d.addEventListener("click",function(e){if(!e.target.closest("[data-h-menu]"))return;e.preventDefault();open(!(menu.classList.contains("open")&&!closing))});
var hxClose=menu.querySelector(".h-x");if(hxClose)hxClose.onclick=function(){open(false)};
menu.addEventListener("click",function(e){var a=e.target.closest("a[href]");if(a&&(menu.classList.contains("open")||closing)){last=null;open(false)}});scrim.onclick=function(){open(false)};
d.addEventListener("keydown",function(e){if(e.key==="Escape"&&(menu.classList.contains("open")||closing))open(false)});
})();
