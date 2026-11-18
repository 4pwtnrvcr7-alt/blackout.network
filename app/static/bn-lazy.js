/* Lazy-load tab/module CSS+JS when a tab is opened, hashed, or scrolled into view. */
(function(){
  if(window.__bnLazy)return;window.__bnLazy=1;
  var G=window.BN_LAZY_GROUPS||{}, loaded={}, inflight={};
  function pathOf(u){return String(u||"").split("?")[0];}
  function loadCSS(u){
    if(document.querySelector('link[rel="stylesheet"][href="'+u+'"]'))return Promise.resolve();
    return new Promise(function(res,rej){
      var l=document.createElement("link");l.rel="stylesheet";l.href=u;
      l.onload=function(){res()};l.onerror=function(){res()};
      document.head.appendChild(l);
    });
  }
  function loadJS(u){
    if(document.querySelector('script[src="'+u+'"]'))return Promise.resolve();
    return new Promise(function(res,rej){
      var s=document.createElement("script");s.src=u;s.async=false;
      s.onload=function(){res()};s.onerror=function(){res()};
      document.head.appendChild(s);
    });
  }
  function seq(urls,fn){
    return (urls||[]).reduce(function(p,u){return p.then(function(){return fn(u);});},Promise.resolve());
  }
  window.bnLazyLoad=function(name){
    name=String(name||"").replace(/^tab-/,"").toLowerCase();
    var alias=G.__alias||{};
    name=alias[name]||name;
    var g=G[name];if(!g)return Promise.resolve();
    if(loaded[name])return inflight[name]||Promise.resolve();
    loaded[name]=1;
    var deps=(g.deps||[]).map(window.bnLazyLoad);
    inflight[name]=Promise.all(deps).then(function(){return seq(g.css,loadCSS);}).then(function(){return seq(g.js,loadJS);});
    return inflight[name];
  };
  function fromHash(){
    var h=(location.hash||"").replace(/^#/,"").split(/[/?&]/)[0].toLowerCase();
    if(!h || h==="bn-menu" || h==="home") return;
    window.bnLazyLoad(h).then(function(){
      /* Addon tabs (weather, finance, …) only self-click if their JS was already on the page.
         After lazy-load, click exactly one matching data-tab button. */
      var alias=G.__alias||{};
      var primary={wire:"threat",solar:"solar_seismic",network:"net",resources:"res",
                   broadcasts:"bcast",government:"gov",spacex:"jets"};
      var b=document.querySelector('button[data-tab="'+h+'"]');
      if(!b && primary[h]) b=document.querySelector('button[data-tab="'+primary[h]+'"]');
      if(!b && alias[h]) b=document.querySelector('button[data-tab="'+alias[h]+'"]');
      if(b && !b.classList.contains("on")) b.click();
    });
  }
  document.addEventListener("click",function(e){
    var el=e.target&&e.target.closest&&e.target.closest("[data-tab],a[href*='#']");
    if(!el)return;
    var k=el.getAttribute("data-tab");
    if(!k && el.getAttribute("href")){
      var m=(el.getAttribute("href")||"").match(/#([a-z0-9_-]+)/i);
      k=m&&m[1];
    }
    if(k)window.bnLazyLoad(k);
  },true);
  addEventListener("hashchange",fromHash);
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",fromHash);
  else fromHash();
  function observe(){
    if(!window.IntersectionObserver)return;
    var roots=document.querySelectorAll("main[id^='tab-']");
    roots.forEach(function(el){
      var io=new IntersectionObserver(function(ents){
        ents.forEach(function(en){
          if(!en.isIntersecting)return;
          window.bnLazyLoad(el.id);
          io.disconnect();
        });
      },{rootMargin:"240px"});
      io.observe(el);
    });
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",observe);
  else observe();
  /* Non-critical modules after window load so they don't hold loadEvent / TTI. */
  function startIdle(){
    var idle=window.requestIdleCallback||function(fn){setTimeout(fn,2200);};
    idle(function(){(G.__idle||[]).forEach(function(n){window.bnLazyLoad(n);});},{timeout:4000});
  }
  if(document.readyState==="complete") startIdle();
  else addEventListener("load", function(){ setTimeout(startIdle, 0); });
})();
