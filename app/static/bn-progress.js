/* BNProgress (t480): one honest progress bar for every search/lookup on BLACKOUT.NETWORK.
 Usage:
   const p = BNProgress.create(containerEl, {label:"Finding Orlando, FL…"});   // shows at 0%
   p.stage("Checking sources…", 0.3)      // jump to a real stage (0..1)
   p.steps(6, "Checking 6 sources")       // n countable sub-steps between current pct and 95%
   p.tick()                                // one sub-step finished -> "Checking 6 sources… 3 of 6"
   p.ease(0.9)                             // unknown duration: eased creep toward 90% (slows down, never reaches it)
   p.done("Done")                          // jumps to 100% and hides shortly after (opts.keep to stay)
   p.fail("Couldn't reach the server.", () => retry())   // error + Retry button
   p.cached()                              // cache hit: finish instantly, nothing shown
   BNProgress.run(el, asyncFn, {label, fail})  // helper: create + ease + done/fail(+retry) around a promise
 No ETA is ever shown; only elapsed time (after 2 s). role=progressbar + aria-valuenow, polite aria-live label. */
(function(){
 if(window.BNProgress)return;
 const RM=()=>matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
 function css(){if(document.querySelector('link[href="/bn-progress.css"]'))return;const l=document.createElement("link");l.rel="stylesheet";l.href="/bn-progress.css";document.head.appendChild(l)}
 function create(host,o){o=o||{};css();
  if(host._bnp)host._bnp.destroy();
  const el=document.createElement("div");el.className="bnp";
  el.innerHTML='<div class="bnp-row"><span class="bnp-label" aria-live="polite"></span><span class="bnp-pct" aria-hidden="true">0%</span></div>'+
   '<div class="bnp-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="bnp-fill"></div></div><div class="bnp-meta"></div>';
  const L=el.querySelector(".bnp-label"),P=el.querySelector(".bnp-pct"),T=el.querySelector(".bnp-track"),F=el.querySelector(".bnp-fill"),M=el.querySelector(".bnp-meta");
  T.setAttribute("aria-label",o.name||"Search progress");
  let v=0,raf=0,timer=0,t0=performance.now(),base="",n=0,k=0,s0=0,dead=false,hideT=0;
  function set(x){v=Math.max(v,Math.min(1,x));const pc=Math.round(v*100);F.style.transform="scaleX("+v+")";P.textContent=pc+"%";T.setAttribute("aria-valuenow",pc);T.setAttribute("aria-valuetext",pc+"% "+L.textContent)}
  function label(s){if(s!=null)L.textContent=s}
  function stopEase(){cancelAnimationFrame(raf);raf=0}
  timer=setInterval(()=>{const s=(performance.now()-t0)/1000;M.textContent=s>=2?Math.floor(s)+" s elapsed":""},500);
  const api={el,
   stage(s,x){if(dead)return api;label(s);if(x!=null){stopEase();set(x)}return api},
   steps(total,s){n=Math.max(1,total|0);k=0;s0=v;base=s||base;label(base+"… 0 of "+n);return api},
   tick(s){if(dead||!n)return api;k=Math.min(n,k+1);label((s||base)+"… "+k+" of "+n);stopEase();set(s0+(0.95-s0)*k/n);return api},
   ease(cap,tau){cap=cap||0.9;tau=tau||8000;stopEase();const from=v,ts=performance.now();
    (function f(){if(dead)return;const t=performance.now()-ts;set(from+(cap-from)*(1-Math.exp(-t/tau)));if(!RM()||t<1)raf=requestAnimationFrame(f);else raf=setTimeout(f,1000)})();return api},
   done(s){if(dead)return api;stopEase();clearInterval(timer);el.classList.add("is-done");label(s||"Done");set(1);
    if(!o.keep)hideT=setTimeout(()=>{if(!dead)api.destroy()},RM()?400:900);return api},
   cached(){api.destroy();return api},
   fail(msg,retry){if(dead)return api;stopEase();clearInterval(timer);el.classList.add("is-err");label("Search stopped");M.textContent="";
    const d=document.createElement("div");d.className="bnp-err";d.setAttribute("role","alert");const b=document.createElement("b");b.textContent=msg||"Something went wrong.";d.appendChild(b);
    if(retry){const r=document.createElement("button");r.type="button";r.className="bnp-retry";r.textContent="Retry";r.onclick=()=>{api.destroy();retry()};d.appendChild(r)}
    el.appendChild(d);return api},
   destroy(){dead=true;stopEase();clearInterval(timer);clearTimeout(hideT);el.remove();if(host._bnp===api)host._bnp=null}};
  label(o.label||"Working…");set(0);host.appendChild(el);host._bnp=api;return api}
 async function run(host,fn,o){o=o||{};const t0=performance.now();let p=null;
  const show=setTimeout(()=>{p=create(host,o);p.ease(o.cap||0.9,o.tau)},o.delay==null?150:o.delay);   // fast/cached answers never flash a bar
  try{const r=await fn(lbl=>p&&p.stage(lbl));clearTimeout(show);if(p)p.done(o.doneLabel);return r}
  catch(e){clearTimeout(show);if(!p)p=create(host,o);p.fail((o.fail&&o.fail(e))||String(e&&e.message||e),o.retry);throw e}}
 window.BNProgress={create,run};
})();
