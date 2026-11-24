/* BLACKOUT.NETWORK /grid Sky view: chip auto-framing and follow lock (Nov 24 2026, pt1834u).
   - Turning on a constellation chip eases the camera to fit that whole group (out for GPS / GEO, in for low orbit).
   - Tapping a satellite (or the ISS chip) flies to it and keeps the camera locked on it as it moves; the globe's
     auto-spin already yields while something is selected. Unlock: tap empty space (net.js clears the selection),
     drag the map by hand, or close the card.
   Uses window.__nxSky / window.__nxSatCard from net.js. Own scope, st* names only. */
(function () {
  "use strict";
  var ST = { lock: false, sel: null, easeUntil: 0, raf: 0, bound: false, framed: null, hinted: false };
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var GROUPS = { iss: 1, starlink: 1, gps: 1, glonass: 1, galileo: 1, beidou: 1, iridium: 1, oneweb: 1, goes: 1, debris: 1 };
  function stBase() { return innerWidth < 768 ? -0.55 : -0.4; }   /* the Sky default zoom, which fits a geostationary radius */
  function stZoomFor(altKm, single) {
    var r = 1 + Math.max(0, altKm || 0) / 6371.0088;
    var z = stBase() + Math.log(6.6 / Math.max(r, 1.55)) / Math.LN2;
    return Math.min(single ? 2.6 : 2.0, z + (single ? 0.5 : 0));
  }
  function stFrame(g, tries) {
    var S = window.__nxSky, map = window.__nxMap; if (!S || !map || !S.on) return;
    var recs = (S.recs || []).filter(function (o) { return o.g === g && o.p; });
    if (!recs.length) { if ((tries || 0) < 12) setTimeout(function () { stFrame(g, (tries || 0) + 1); }, 300); return; }
    if (g === "iss" && window.__nxSatCard) { window.__nxSatCard(S.recs.indexOf(recs[0])); return; }   /* single object: select + follow */
    var alts = recs.map(function (o) { return o.p[2]; }).sort(function (a, b) { return a - b; });
    var hi = alts[Math.min(alts.length - 1, Math.floor(alts.length * 0.95))];
    var x = 0, y = 0, z = 0;
    recs.forEach(function (o) { var la = o.p[1] * Math.PI / 180, lo = o.p[0] * Math.PI / 180; x += Math.cos(la) * Math.cos(lo); y += Math.cos(la) * Math.sin(lo); z += Math.sin(la); });
    var n = Math.hypot(x, y, z) / recs.length, c = map.getCenter(), center = [c.lng, Math.max(-30, Math.min(30, c.lat))];
    if (n > 0.35) center = [Math.atan2(y, x) * 180 / Math.PI, Math.atan2(z, Math.hypot(x, y)) * 180 / Math.PI];   /* clustered group (e.g. GOES): face it */
    ST.lock = false;
    /* hold the auto-spin while the camera eases: its per-frame setCenter would cancel the ease */
    window.__nxSpinHold = true; clearTimeout(ST.holdT);
    ST.holdT = setTimeout(function () { var L = window.__nxLaunches; if (!(L && L.state && L.state.sel >= 0)) window.__nxSpinHold = false; }, reduce ? 50 : 1300);
    try { map.easeTo({ center: center, zoom: stZoomFor(hi, false), pitch: 0, duration: reduce ? 0 : 1100 }); } catch (e) {}
  }
  function stHint(b) {   /* one short on-map hint, the first time a tap frames instead of hiding */
    var map = window.__nxMap; if (ST.hinted || !map || !b) return; ST.hinted = true;
    var box = map.getContainer(), r = b.getBoundingClientRect(), c = box.getBoundingClientRect(), d = document.createElement("div");
    d.className = "nx-st-hint"; d.textContent = "Tap again to hide";
    d.style.cssText = "position:absolute;z-index:7;pointer-events:none;font-size:11.5px;color:#E8ECF5;background:rgba(8,10,16,.88);border:1px solid rgba(232,236,245,.3);border-radius:6px;padding:4px 8px;white-space:nowrap;transition:opacity .4s";
    d.style.left = Math.max(6, Math.min(c.width - 130, r.left - c.left)) + "px"; d.style.top = (r.bottom - c.top + 6) + "px";
    box.appendChild(d); setTimeout(function () { d.style.opacity = "0"; }, 2600); setTimeout(function () { d.remove(); }, 3100);
  }
  function stTick() {
    ST.raf = requestAnimationFrame(stTick);
    var S = window.__nxSky, map = window.__nxMap; if (!S || !map) return;
    if (!S.on || S.sel == null) { ST.sel = null; ST.lock = false; return; }
    var o = S.recs[S.sel]; if (!o || !o.p) return;
    if (S.sel !== ST.sel) {   /* new selection: fly there, then lock */
      ST.sel = S.sel; ST.lock = true; ST.easeUntil = performance.now() + (reduce ? 0 : 1000);
      try { map.easeTo({ center: [o.p[0], o.p[1]], zoom: stZoomFor(o.p[2], true), pitch: 0, duration: reduce ? 0 : 950 }); } catch (e) {}
      return;
    }
    if (!ST.lock || performance.now() < ST.easeUntil || document.hidden) return;
    var c = map.getCenter(), dl = o.p[0] - c.lng; if (dl > 180) dl -= 360; if (dl < -180) dl += 360;
    var dy = o.p[1] - c.lat; if (Math.abs(dl) < 1e-4 && Math.abs(dy) < 1e-4) return;
    try { map.jumpTo({ center: [c.lng + dl * 0.12, c.lat + dy * 0.12] }); } catch (e) {}
  }
  function stBind() {
    var map = window.__nxMap; if (!map || ST.bound) return; ST.bound = true;
    map.on("dragstart", function (e) { if (e && e.originalEvent) { ST.lock = false; ST.framed = null; } });   /* hand pan unlocks */
    map.on("zoomstart", function (e) { if (e && e.originalEvent) ST.framed = null; });
    var sf = document.getElementById("nx_sf");
    /* capture phase, before net.js toggles: tapping a chip that is ON frames that group; tapping again while framed turns it off */
    if (sf) sf.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("button[data-g]"); if (!b || !GROUPS[b.dataset.g]) return;
      if (b.getAttribute("aria-pressed") === "true" && ST.framed !== b.dataset.g) {
        e.stopPropagation(); e.preventDefault(); ST.framed = b.dataset.g; stFrame(b.dataset.g, 0); stHint(b); return;
      }
      ST.framed = b.getAttribute("aria-pressed") === "true" ? null : b.dataset.g;   /* turning on also frames (below) */
    }, true);
    if (sf) sf.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("button[data-g]"); if (!b || !GROUPS[b.dataset.g]) return;
      if (b.getAttribute("aria-pressed") === "true") setTimeout(function () { stFrame(b.dataset.g, 0); }, 60);
    });
    if (!ST.raf) ST.raf = requestAnimationFrame(stTick);
  }
  window.__nxTrack = { state: ST, frame: stFrame, hint: stHint, framed: function () { return ST.framed; }, setFramed: function (g) { ST.framed = g; } };
  if (window.__nxMap) stBind(); else document.addEventListener("nx:map", stBind);
  var iv = setInterval(function () { if (window.__nxMap) { stBind(); clearInterval(iv); } }, 500);
})();
