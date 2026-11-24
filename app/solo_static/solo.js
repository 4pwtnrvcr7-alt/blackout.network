// Reworked standalone pages (solo.py): run the old tab add-on inside this page's single <main>, plus guide TOC/print helpers.
(function(){"use strict";
var key=document.body.getAttribute("data-solo"),M=document.getElementById("tab-"+key),slot=document.getElementById("solo_slot");
// Add-ons that build their own <main> append it to <body>; move it into the page slot.
if(M&&slot){M.classList.add("solo-main");slot.replaceWith(M)}
if(!M)return;
M.style.display="block";
// Links to other site pages open at the top (Matt's rule): only an in-page #anchor keeps its scroll target.
if("scrollRestoration" in history)history.scrollRestoration="manual";
if(!location.hash)window.scrollTo(0,0);
// The add-on scripts listen for a click on their own tab button inside .tabs; fire it once so they load here.
function kick(){var nav=document.querySelector(".tabs");if(!nav)return;var b=nav.querySelector('button[data-tab="'+key+'"]');
 if(b){try{b.click()}catch(_){}}}
if(document.readyState==="complete")setTimeout(kick,0);else window.addEventListener("load",function(){setTimeout(kick,0)});
// Guides: contents links scroll smoothly; on phones the contents list starts closed.
if(innerWidth<900)M.querySelectorAll(".toc details").forEach(function(d){d.open=false});
document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest(".gd .toc a");if(!a)return;var h=a.getAttribute("href")||"";
 if(h.charAt(0)!=="#")return;var t=document.getElementById(h.slice(1));if(!t)return;e.preventDefault();t.scrollIntoView({behavior:"smooth",block:"start"});
 if(innerWidth<900){var d=a.closest("details");if(d)d.open=false}});
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-print]");if(!b)return;document.body.classList.add("gd-print");
 M.classList.add("gd-printing");window.print();setTimeout(function(){document.body.classList.remove("gd-print");M.classList.remove("gd-printing")},500)});
})();
