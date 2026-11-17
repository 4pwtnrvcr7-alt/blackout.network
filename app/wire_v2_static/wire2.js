/* Wire v2 preview: menu overlay, bar hide/show, reveal, hero parallax (0.15x, heroes only), more, copy. */
(function(){"use strict";
var d=document,b=d.body,bar=d.getElementById("w2_bar"),menu=d.getElementById("w2_menu"),op=d.getElementById("w2_open"),cl=d.getElementById("w2_close");
var RM=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,last=0;
function openM(){menu.hidden=false;requestAnimationFrame(function(){menu.classList.add("open")});b.classList.add("w2-lock");op.setAttribute("aria-expanded","true");cl.focus()}
function closeM(){menu.classList.remove("open");b.classList.remove("w2-lock");op.setAttribute("aria-expanded","false");setTimeout(function(){menu.hidden=true},200);op.focus()}
op&&op.addEventListener("click",openM);cl&&cl.addEventListener("click",closeM);
d.addEventListener("keydown",function(e){if(menu.hidden)return;if(e.key==="Escape")closeM();if(e.key==="Tab"){var f=menu.querySelectorAll("a,button"),a=f[0],z=f[f.length-1];if(e.shiftKey&&d.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&d.activeElement===z){e.preventDefault();a.focus()}}});
var heroes=[].slice.call(d.querySelectorAll("[data-par]")),tick=false;
function frame(){tick=false;var y=window.scrollY,vh=window.innerHeight;
 bar.classList.toggle("solid",y>40);bar.classList.toggle("up",y>last&&y>200&&menu.hidden);last=y;
 if(!RM)heroes.forEach(function(im){var r=im.parentNode.parentNode.getBoundingClientRect();if(r.bottom<0||r.top>vh)return;im.style.transform="translate3d(0,"+(-r.top*0.15).toFixed(1)+"px,0)"})}
window.addEventListener("scroll",function(){if(!tick){tick=true;requestAnimationFrame(frame)}},{passive:true});frame();
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}})},{rootMargin:"0px 0px -8% 0px"});
 d.querySelectorAll(".w2-rv").forEach(function(el){io.observe(el)})}else b.classList.add("w2-nojs");
var mb=d.getElementById("w2_more");mb&&mb.addEventListener("click",function(){var h=d.querySelectorAll(".w2-row.w2-more[hidden]");[].slice.call(h,0,12).forEach(function(r){r.hidden=false;r.classList.add("in")});if(h.length<=12)mb.parentNode.remove()});
d.querySelectorAll("[data-copy]").forEach(function(x){x.addEventListener("click",function(){try{navigator.clipboard.writeText(location.href.split("#")[0]);x.textContent="COPIED"}catch(e){}})});
})();
