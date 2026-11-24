/* Shared metric/imperial formatter (pt1827u). Default imperial. Persists in localStorage; live switch via "bn-units". */
(function (w) {
  "use strict";
  var KEY = "bn-units", KM_MI = 0.621371192, M_FT = 3.280839895, imperial = true;
  try { var saved = w.localStorage && w.localStorage.getItem(KEY); if (saved === "metric") imperial = false; else if (saved === "imperial") imperial = true; } catch (e) {}
  function rnd(x) { return Math.round(x).toLocaleString("en-US"); }
  function dec(x, d) {
    var n = Number(x).toFixed(d), sign = n.charAt(0) === "-" ? "-" : "", body = sign ? n.slice(1) : n, parts = body.split(".");
    parts[0] = Number(parts[0]).toLocaleString("en-US");
    return sign + parts.join(".");
  }
  function auto(x) { var a = Math.abs(x); return a >= 10 ? rnd(x) : a >= 1 ? dec(x, 1) : dec(x, 2); }
  function fmtDist(km, digits) {
    if (km == null || !isFinite(Number(km))) return "–";
    km = Number(km);
    if (imperial) { var mi = km * KM_MI; return (digits != null ? dec(mi, digits) : auto(mi)) + " mi"; }
    return (digits != null ? dec(km, digits) : auto(km)) + " km";
  }
  function fmtAlt(km, digits) { return fmtDist(km, digits); }
  function fmtSpeed(kmPer, per) {
    if (kmPer == null || !isFinite(Number(kmPer))) return "–";
    kmPer = Number(kmPer); per = per === "h" ? "h" : "s";
    var v = imperial ? kmPer * KM_MI : kmPer;
    if (per === "h") return (Math.abs(v) >= 100 ? rnd(v) : dec(v, 1)) + (imperial ? " mph" : " km/h");
    return v.toFixed(2) + (imperial ? " mi/s" : " km/s");
  }
  function fmtLenM(m, digits) {
    if (m == null || !isFinite(Number(m))) return "–";
    m = Number(m);
    if (imperial) { var ft = m * M_FT; return (digits != null ? dec(ft, digits) : rnd(ft)) + " ft"; }
    return (digits != null ? dec(m, digits) : rnd(m)) + " m";
  }
  function fmtFt(ft, digits) {
    if (ft == null || !isFinite(Number(ft))) return "–";
    ft = Number(ft);
    if (imperial) return (digits != null ? dec(ft, digits) : rnd(ft)) + " ft";
    var m = ft / M_FT; return (digits != null ? dec(m, digits) : rnd(m)) + " m";
  }
  function fmtSizeKm(km) {
    if (km == null || !isFinite(Number(km))) return "–";
    km = Number(km);
    if (km >= 1) return fmtDist(km, km >= 10 ? 0 : 1);
    return fmtLenM(km * 1000);
  }
  function fmtTempC(c, digits) {
    if (c == null || !isFinite(Number(c))) return "–";
    c = Number(c);
    if (imperial) return (digits != null ? dec(c * 9 / 5 + 32, digits) : rnd(c * 9 / 5 + 32)) + " °F";
    return (digits != null ? dec(c, digits) : rnd(c)) + " °C";
  }
  function sync() {
    var box = document.getElementById("nx_units"); if (!box) return;
    var sys = imperial ? "imperial" : "metric";
    [].forEach.call(box.querySelectorAll("button[data-u]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-u") === sys ? "true" : "false"); });
  }
  function set(sys) {
    var next = sys !== "metric";
    if (next === imperial) { sync(); return; }
    imperial = next;
    try { if (w.localStorage) w.localStorage.setItem(KEY, imperial ? "imperial" : "metric"); } catch (e) {}
    sync();
    try { w.dispatchEvent(new CustomEvent("bn-units", { detail: { system: imperial ? "imperial" : "metric" } })); } catch (e) {}
  }
  function bind() {
    var box = document.getElementById("nx_units"); if (!box || box.getAttribute("data-bn-bound")) return;
    box.setAttribute("data-bn-bound", "1");
    box.addEventListener("click", function (e) { var b = e.target.closest && e.target.closest("button[data-u]"); if (b) set(b.getAttribute("data-u")); });
    sync();
  }
  w.BNUnits = {
    key: KEY, isImperial: function () { return imperial; }, system: function () { return imperial ? "imperial" : "metric"; },
    set: set, fmtSpeed: fmtSpeed, fmtDist: fmtDist, fmtAlt: fmtAlt, fmtLenM: fmtLenM, fmtFt: fmtFt, fmtSizeKm: fmtSizeKm, fmtTempC: fmtTempC
  };
  bind();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
})(window);

/* Network Status (/grid, Nov 23 2026, pt1755u). MapLibre GL + OpenFreeMap, same brighter base style as /weather.
   Data: /api/netmap/data (networks, IODA outages, power), /api/netmap/dc (PeeringDB data centers), /api/signal/world.geojson.
   The loader builds a glowing network while the page preloads every dataset and the map tiles for the first view. */
(function () {
  "use strict";
  var F = ["Noto Sans Regular"], FB = ["Noto Sans Bold"];
  function style() {
    var lbl = "rgba(240,240,250,", halo = "rgba(5,6,10,.85)";   /* pt1748u: brighter base map, still dark */
    return {
      version: 8, glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
      sources: { omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: "" } },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#232a3a" } },
        { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": "#0f1828", "fill-antialias": true } },
        { id: "ice", type: "fill", source: "omt", "source-layer": "landcover", filter: ["==", ["get", "subclass"], "glacier"], paint: { "fill-color": "#2c3344", "fill-opacity": 0.6 } },
        { id: "park", type: "fill", source: "omt", "source-layer": "park", minzoom: 8, paint: { "fill-color": "#1f2635", "fill-opacity": 0.6 } },
        { id: "waterway", type: "line", source: "omt", "source-layer": "waterway", minzoom: 7, paint: { "line-color": "#0f1828", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 14, 2] } },
        { id: "coast", type: "line", source: "omt", "source-layer": "water", filter: ["!=", ["get", "class"], "swimming_pool"], paint: { "line-color": "rgba(150,185,230,.30)", "line-width": ["interpolate", ["linear"], ["zoom"], 1, 0.5, 5, 0.8, 10, 1.2] } },
        { id: "building", type: "fill", source: "omt", "source-layer": "building", minzoom: 14, paint: { "fill-color": "#2a3142", "fill-opacity": 0.7 } },
        { id: "road-minor", type: "line", source: "omt", "source-layer": "transportation", minzoom: 10, filter: ["match", ["get", "class"], ["minor", "service", "tertiary", "secondary"], true, false],
          paint: { "line-color": "rgba(240,240,250,.10)", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.4, 16, 3] } },
        { id: "road-major", type: "line", source: "omt", "source-layer": "transportation", minzoom: 5, filter: ["match", ["get", "class"], ["motorway", "trunk", "primary"], true, false],
          paint: { "line-color": "rgba(240,240,250,.15)", "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.3, 10, 1, 16, 4] } },
        { id: "admin-state", type: "line", source: "omt", "source-layer": "boundary", minzoom: 1.8, filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
          paint: { "line-color": "rgba(240,240,250,.34)", "line-width": ["interpolate", ["linear"], ["zoom"], 2, 0.6, 3, 0.75, 8, 1.4], "line-dasharray": [3, 2] } },
        { id: "admin-country", type: "line", source: "omt", "source-layer": "boundary", filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1], ["!=", ["get", "disputed"], 1]],
          paint: { "line-color": "rgba(240,240,250,.56)", "line-width": ["interpolate", ["linear"], ["zoom"], 0, 0.6, 5, 1.3, 10, 2] } },
        { id: "lbl-country", type: "symbol", source: "omt", "source-layer": "place", minzoom: 1.5, maxzoom: 7, filter: ["==", ["get", "class"], "country"],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": FB, "text-transform": "uppercase", "text-letter-spacing": 0.22,
            "text-size": ["interpolate", ["linear"], ["zoom"], 1.5, 8.5, 4, 11, 6, 13], "text-max-width": 7, "symbol-sort-key": ["coalesce", ["get", "rank"], 9] },
          paint: { "text-color": lbl + ".66)", "text-halo-color": halo, "text-halo-width": 1.3 } },
        { id: "lbl-state", type: "symbol", source: "omt", "source-layer": "place", minzoom: 4, maxzoom: 8, filter: ["==", ["get", "class"], "state"],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-transform": "uppercase", "text-letter-spacing": 0.24, "text-size": 9.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".48)", "text-halo-color": halo, "text-halo-width": 1.1 } },
        { id: "lbl-city", type: "symbol", source: "omt", "source-layer": "place", minzoom: 3, filter: ["match", ["get", "class"], ["city"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": ["interpolate", ["linear"], ["zoom"], 3, 10, 8, 13, 12, 15],
            "text-letter-spacing": 0.04, "text-max-width": 8, "symbol-sort-key": ["coalesce", ["get", "rank"], 20],
            "text-variable-anchor": ["top", "bottom", "left", "right"], "text-radial-offset": 0.6 },
          paint: { "text-color": lbl + ".88)", "text-halo-color": halo, "text-halo-width": 1.4, "text-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.85, 5, 1] } },
        { id: "lbl-town", type: "symbol", source: "omt", "source-layer": "place", minzoom: 8, filter: ["match", ["get", "class"], ["town"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": 11.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".74)", "text-halo-color": halo, "text-halo-width": 1.2 } },
        { id: "lbl-village", type: "symbol", source: "omt", "source-layer": "place", minzoom: 11, filter: ["match", ["get", "class"], ["village", "suburb"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": 10.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".56)", "text-halo-color": halo, "text-halo-width": 1.1 } }
      ]
    };
  }

  /* ---------- helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function url(u) { return /^https?:\/\//i.test(u || "") || /^\/[a-z]/.test(u || "") ? esc(u) : ""; }
  function num(n) { return n == null ? "–" : Math.round(n).toLocaleString("en-US"); }
  function ago(ts) {
    var t = Date.parse(ts || ""); if (!isFinite(t)) return "";
    var m = Math.max(0, Math.round((Date.now() - t) / 60000));
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " d ago";
  }
  var COL = { ok: "#2FD67B", deg: "#FF7A1A", out: "#FF3B3B", na: "#7C8190", dc: "#7FD4FF", minor: "#C9CCD6" };
  var PROV = { aws: "#9DB4FF", azure: "#4FC3F7", gcp: "#B39DFF" };
  var PNAME = { aws: "AWS", azure: "Microsoft Azure", gcp: "Google Cloud" };
  function lvCol(l) { return l >= 3 ? COL.out : l === 2 ? COL.deg : l === 1 ? COL.minor : l === 0 ? COL.ok : COL.na; }
  function lvName(l) { return l >= 3 ? "Major outage" : l === 2 ? "Disruption" : l === 1 ? "Minor issue" : l === 0 ? "Normal" : "No live data"; }
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SKY = { on: false };
  var US = [[-125.5, 23.5], [-66, 50]];
  function PAD() { var m = innerWidth < 768; return m ? { top: 150, bottom: 120, left: 18, right: 18 } : { top: 160, bottom: 90, left: 60, right: 80 }; }

  /* ---------- loader: glowing network built in front of you, progress tracks the real preload ---------- */
  var P = { map: 0, nets: 0, out: 0, dc: 0, rep: 0 }, W8 = { map: 0.3, nets: 0.3, out: 0.1, dc: 0.15, rep: 0.15 }, shown = 0, ldDone = false, t0 = performance.now();
  function prog() { var p = 0; for (var k in P) p += W8[k] * P[k]; return Math.min(1, p); }
  function step(k, v) { P[k] = Math.max(P[k], v); if (v >= 1) { var li = document.querySelector('#nx_ld li[data-s="' + k + '"]'); if (li) li.classList.add("on"); } if (!BOOT && !ldDone) { var pn = $("nx_ldn"); if (pn) pn.textContent = ("0" + Math.min(99, Math.round(prog() * 100))).slice(-2) + "%"; } if (prog() >= 0.999) setTimeout(finish, reduce ? 50 : Math.max(650, 2600 - (performance.now() - t0))); }   /* never a flash: the build shows for at least ~2.6 s */
  function finish() {
    if (ldDone) return; ldDone = true; shown = 1; if (!BOOT) $("nx_ldn").textContent = "100%";
    var gone = false;
    function reveal() {   /* the last parts power on, the board flashes, then it fades into the page */
      if (gone) return; gone = true;
      document.body.classList.add("nx-ready");
      try { window.__nxLoad = Math.round(performance.now() - t0); } catch (e) {}
      setTimeout(function () { if (BOOT) BOOT.stop(); var l = $("nx_ld"); if (l) l.remove(); }, 900);
    }
    if (BOOT) { BOOT.done(reveal); setTimeout(reveal, 3200); } else setTimeout(reveal, reduce ? 0 : 520);
  }
  setTimeout(function () { if (!ldDone) { var m = $("nx_ldmsg"); if (m) { m.hidden = false; m.textContent = "Some layers are still loading. They finish in the background."; } setTimeout(finish, 900); } }, 25000);
  var BOOT = null;
  (function loader() {   /* pt1759u: boot sequence in boot.js; the percentage and every stage follow prog() */
    var cv = $("nx_ldcv"); if (!cv || !window.BNBoot) return;
    BOOT = window.BNBoot({ canvas: cv, panel: $("nx_ldp"), progress: prog, pct: $("nx_ldn"), bar: $("nx_ldbar"), status: $("nx_ldst") });
  })();

  /* ---------- preload: every dataset in parallel ---------- */
  function getJSON(u, k) {
    return fetch(u, { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { if (k) step(k, 1); return j; }, function (e) { if (k) step(k, 1); throw e; });
  }
  function retry(u, k, n) {
    return fetch(u, { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { step(k, 1); return j; }, function (e) {
        if (n > 0) { step(k, 0.4); return new Promise(function (res) { setTimeout(res, 2500); }).then(function () { return retry(u, k, n - 1); }); }
        step(k, 1); throw e; });
  }
  window.__nxStep = step;   /* board.js reports its own preload (reports + timeline) */
  /* pt1787u: the page shows only services with a live signal; feedless ("No live signal") and link-only entries are dropped,
     and the counts are recomputed from what is shown. board.js reads the same filtered object. */
  function liveOnly(j) {
    if (!j || !j.nets) return j;
    var ns = j.nets.filter(function (n) { return !n.link_only && n.level >= 0; }), s = {}, k;
    for (k in (j.summary || {})) s[k] = j.summary[k];
    s.networks = ns.length; s.ok = ns.filter(function (n) { return n.level <= 1; }).length; s.issues = ns.filter(function (n) { return n.level >= 2; }).length; s.unknown = 0; s.no_signal = 0;
    j.nets = ns; j.summary = s; j.live_only = true; return j;
  }
  window.__nxLive = liveOnly;
  var pData = retry("/api/netmap/data", "nets", 3).then(liveOnly), pDc = retry("/api/netmap/dc", "dc", 2), pWorld = getJSON("/api/signal/world.geojson"),
    pInet = Promise.all([getJSON("/api/netmap/inet"), getJSON("/api/netmap/inet.json")]);   /* pt1810u: internet status per state, territory, country */
  pData.then(function () { step("out", 0.5); }, function () {});
  setTimeout(function () { step("rep", 1); }, 9000);   /* the board's own fetch normally lands first; never hold the loader on it */
  window.__nxData = pData;   /* the status board (board.js) reads the same download */
  var D = null, DC = null, WORLD = null, INET = null, INETG = null, map = null, ready = false;
  /* Nov 24 2026 (Matt): map pop-ups sit next to the tapped item, always fully inside the visible screen (below the header and chips,
     inside safe areas), scroll inside when tall, and can be dragged by their top strip (touch + mouse). Close: X, tap the map, Esc. */
  function cardBounds() {
    var vv = window.visualViewport, VW = vv ? vv.width : innerWidth, VH = vv ? vv.height : innerHeight, top = 12;
    ["#bn_topbar", ".nx-top"].forEach(function (q) { var e = document.querySelector(q); if (!e || !e.offsetParent && getComputedStyle(e).position !== "fixed") return;
      var r = e.getBoundingClientRect(); if (r.height && r.bottom < VH / 2) top = Math.max(top, Math.round(r.bottom) + 8); });
    return { l: 10, t: top, r: VW - 10, b: VH - 12 - (innerWidth < 768 ? 64 : 0) };
  }
  function clampCard(c, x, y) {
    var B = cardBounds(), w = c.offsetWidth, h = c.offsetHeight;
    x = Math.max(B.l, Math.min(x, B.r - w)); y = Math.max(B.t, Math.min(y, B.b - h));
    c.style.left = x + "px"; c.style.top = y + "px"; c.style.setProperty("--dx", x + "px"); c.style.setProperty("--dy", y + "px");
  }
  function placeCard(c, pt) {
    if (!c) return;
    c.classList.remove("dragged");
    var B = cardBounds(); c.style.maxHeight = Math.max(140, B.b - B.t) + "px";
    if (!c.querySelector(".bn-drag")) c.insertAdjacentHTML("afterbegin", '<div class="bn-drag" title="Drag to move" aria-hidden="true"><i></i></div>');
    if (innerWidth < 768) return;   /* phones: bottom sheet (CSS), capped height with its own scroll; drag frees it */
    var w = c.offsetWidth, x = pt ? pt.x + 18 : B.r - w, y = pt ? pt.y - 20 : B.t;
    if (pt && x + w > B.r) x = pt.x - w - 18;
    clampCard(c, x, y);
  }
  function dragCard(c) {
    if (!c || c.__drag) return; c.__drag = 1;
    var st = null;
    c.addEventListener("pointerdown", function (e) {
      var h = e.target.closest(".bn-drag, .st, h3"); if (!h || e.target.closest("a,button") || (e.pointerType === "mouse" && e.button)) return;
      var r = c.getBoundingClientRect(); st = { id: e.pointerId, dx: e.clientX - r.left, dy: e.clientY - r.top };
      c.style.maxHeight = Math.max(140, cardBounds().b - cardBounds().t) + "px";
      c.classList.add("dragged", "dragging"); clampCard(c, r.left, r.top); try { c.setPointerCapture(e.pointerId); } catch (x) {} e.preventDefault();
    });
    c.addEventListener("pointermove", function (e) { if (st && e.pointerId === st.id) { clampCard(c, e.clientX - st.dx, e.clientY - st.dy); e.preventDefault(); } });
    function end(e) { if (st && e.pointerId === st.id) { st = null; c.classList.remove("dragging"); } }
    c.addEventListener("pointerup", end); c.addEventListener("pointercancel", end);
  }
  window.__bnPlace = function (c, pt) { dragCard(c); placeCard(c, pt); };
  addEventListener("resize", function () { ["nx_card", "gx_card"].forEach(function (id) { var c = document.getElementById(id); if (c && !c.hidden) { var r = c.getBoundingClientRect(); clampCard(c, r.left, r.top); } }); });
  var ON = { internet: true, power: true, ops: true, cloud: true, dc: true, mobile: true, sat: true, pay: true, apps: true, hydro: true, sea: true, towers: true, grid: true };   /* pt1787u: opens with every layer on */
  var MAPR = { show: {}, timer: 0, seq: 0 };
  var MAP_ORDER = ["internet", "grid", "sea", "dc", "towers", "hydro", "cloud"];   /* pt1833u: Map layers in one at a time, ~400 ms apart */
  function mapOn(k) {
    if (k === "power" || k === "ops") k = "grid";
    return !!ON[k] && !!MAPR.show[k];
  }
  function mapLayerIn() {
    if (SKY.on) return;
    if (MAPR.timer) { clearTimeout(MAPR.timer); MAPR.timer = 0; }
    MAPR.show = {}; MAPR.seq += 1;
    var seq = MAPR.seq;
    vis();
    var keys = MAP_ORDER.filter(function (k) { return ON[k]; });
    if (reduce || !keys.length) { keys.forEach(function (k) { MAPR.show[k] = true; }); vis(); return; }
    var i = 0, gap = 400;
    (function next() {
      if (seq !== MAPR.seq || SKY.on) return;
      if (i < keys.length) {
        MAPR.show[keys[i]] = true;
        try { (window.__mapLayerInAt = window.__mapLayerInAt || []).push({ k: keys[i], t: performance.now() }); } catch (e) {}
        i += 1; vis();
        if (i < keys.length) MAPR.timer = setTimeout(next, gap);
      }
    })();
  }
  for (var k1 in ON) if (!document.querySelector('#nx_f [data-k="' + k1 + '"]')) ON[k1] = false;   /* a layer whose chip is gone stays off */

  function bindAttrib() {   /* pt1831u: credits stay a collapsed info button; MapLibre compact starts open and re-opens on source/resize */
    var el = document.querySelector(".nx-map .maplibregl-ctrl-attrib");
    if (!el) return;
    el.classList.add("maplibregl-compact", "nx-attrib");
    var on = false;
    function setOpen(v) {
      on = !!v;
      el.classList.toggle("nx-attrib-open", on);
      el.classList.toggle("maplibregl-compact-show", on);
      if (on) el.setAttribute("open", "");
      else el.removeAttribute("open");
      var sum = el.querySelector(".maplibregl-ctrl-attrib-button");
      if (sum) sum.setAttribute("aria-expanded", on ? "true" : "false");
    }
    setOpen(false);
    if (!el.querySelector(".nx-attrib-x")) {
      var x = document.createElement("button");
      x.type = "button";
      x.className = "nx-attrib-x";
      x.setAttribute("aria-label", "Close credits");
      x.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
      x.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); setOpen(false); });
      el.appendChild(x);
    }
    var btn = el.querySelector(".maplibregl-ctrl-attrib-button");
    if (btn && !btn.dataset.nxAttrib) {
      btn.dataset.nxAttrib = "1";
      btn.setAttribute("aria-expanded", "false");
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        setOpen(!on);
      }, true);
    }
    if (!document.documentElement.dataset.nxAttribDoc) {
      document.documentElement.dataset.nxAttribDoc = "1";
      document.addEventListener("pointerdown", function (e) {
        var a = document.querySelector(".nx-map .maplibregl-ctrl-attrib");
        if (a && a.classList.contains("nx-attrib-open") && !a.contains(e.target)) setOpen(false);
      }, true);
    }
    if (window.MutationObserver && !el._nxAttribObs) {
      el._nxAttribObs = new MutationObserver(function () {
        if (on) return;
        if (el.classList.contains("maplibregl-compact-show")) el.classList.remove("maplibregl-compact-show");
        if (el.hasAttribute("open")) el.removeAttribute("open");
        if (!el.classList.contains("maplibregl-compact")) el.classList.add("maplibregl-compact");
      });
      el._nxAttribObs.observe(el, { attributes: true, attributeFilter: ["class", "open"] });
    }
  }
  function boot() {
    if (!window.maplibregl) { setTimeout(boot, 60); return; }
    map = new maplibregl.Map({ container: "nx_map", style: style(), bounds: US, fitBoundsOptions: { padding: PAD() }, minZoom: 1, maxZoom: 13,
      attributionControl: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, fadeDuration: reduce ? 0 : 300, renderWorldCopies: true });
    map.touchZoomRotate.disableRotation();
    window.__nxMap = map; try { document.dispatchEvent(new CustomEvent("nx:map", { detail: map })); } catch (e) {}   /* gridlayer.js adds the grid operator layer to this map */
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a> · <a href="https://ioda.inetintel.cc.gatech.edu/" target="_blank" rel="noopener">IODA</a> · <a href="https://www.peeringdb.com/" target="_blank" rel="noopener">PeeringDB</a> · Cables: OpenStreetMap (ODbL), <a href="https://marinecadastre.gov/" target="_blank" rel="noopener">NOAA OCM</a> · Towers: <a href="https://www.fcc.gov/antenna-structure-registration" target="_blank" rel="noopener">FCC ASR</a> · Power grid: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a> (ODbL)' }), "bottom-right");
    bindAttrib();
    map.on("dataloading", function () { if (!ready) step("map", Math.min(0.8, P.map + 0.04)); });
    map.on("load", function () {
      step("map", 0.5); addLayers(); seaLayers(); infLayers(); bindLayers(); if (location.hash !== "#sky") mapLayerIn();
      Promise.allSettled([pData, pWorld]).then(function (r) {
        if (r[0].status === "fulfilled") { D = r[0].value; applyData(); }
        else { $("nx_sum").textContent = "Network data is unavailable right now"; }
        if (r[1].status === "fulfilled") { WORLD = r[1].value; applyWorld(); }
        step("out", 1);
      });
      pDc.then(function (j) { DC = j; applyDc(); }, function () {});
      pInet.then(function (r) { INET = r[0]; INETG = r[1]; applyInet(); }, function () {});
      setInterval(function () {   /* refresh the Internet layer every 5 min (server cache is 10 min); keeps the last good copy on failure */
        if (document.hidden) return;
        Promise.all([getJSON("/api/netmap/inet"), INETG ? Promise.resolve(INETG) : getJSON("/api/netmap/inet.json")]).then(function (r) { INET = r[0]; INETG = r[1]; applyInet(); }, function () {});
      }, 300000);
      var tk = setInterval(function () {   /* the first view's tiles are all in (the pulse animation would keep "idle" from ever firing) */
        if (map.areTilesLoaded() && map.isStyleLoaded()) { clearInterval(tk); ready = true; step("map", 1); startPulse(); if (location.hash === "#sky") setTimeout(function () { view("sky"); }, 400); }
      }, 150);
    });
    map.on("error", function () { });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();

  var EMPTY = { type: "FeatureCollection", features: [] };
  function addLayers() {
    map.addSource("cty", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "cty-fill", type: "fill", source: "cty", paint: { "fill-color": ["get", "c"], "fill-opacity": ["case", ["get", "cur"], 0.26, 0.1] } }, "admin-state");
    map.addLayer({ id: "cty-line", type: "line", source: "cty", paint: { "line-color": ["get", "c"], "line-opacity": ["case", ["get", "cur"], 0.75, 0.35], "line-width": 1 } }, "admin-state");
    map.addSource("inet", { type: "geojson", data: EMPTY, tolerance: 0.5 });
    map.addLayer({ id: "inet-fill", type: "fill", source: "inet", paint: { "fill-color": ["get", "c"], "fill-opacity": ["get", "o"] } }, "admin-state");
    map.addLayer({ id: "inet-line", type: "line", source: "inet", paint: { "line-color": ["get", "c"], "line-opacity": 0.45, "line-width": 0.6 } }, "admin-state");
    map.addSource("dc", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "dc-glow", type: "circle", source: "dc", layout: { visibility: "none" }, paint: { "circle-color": COL.dc, "circle-blur": 1, "circle-opacity": ["interpolate", ["linear"], ["zoom"], 1, 0.14, 6, 0.3],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["+", 2, ["*", 0.04, ["min", ["get", "n"], 200]]], 8, ["+", 6, ["*", 0.08, ["min", ["get", "n"], 200]]]] } });
    map.addLayer({ id: "dc", type: "circle", source: "dc", layout: { visibility: "none" }, paint: { "circle-color": COL.dc, "circle-opacity": 0.9,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 0.9, 5, 1.8, 10, 3.6] } });
    map.addSource("pts", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "glow", type: "circle", source: "pts", paint: { "circle-color": ["get", "c"], "circle-blur": 1, "circle-opacity": ["case", ["get", "hot"], 0.45, 0.2],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["*", 1.6, ["get", "r"]], 8, ["*", 3, ["get", "r"]]] } });
    map.addLayer({ id: "pulse", type: "circle", source: "pts", filter: ["==", ["get", "hot"], true], paint: { "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": ["get", "c"], "circle-stroke-width": 1.3, "circle-radius": 10, "circle-stroke-opacity": 0.6 } });
    map.addLayer({ id: "pt", type: "circle", source: "pts", paint: { "circle-color": ["get", "fill"], "circle-stroke-color": ["get", "c"], "circle-stroke-width": ["get", "sw"],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["*", 0.55, ["get", "r"]], 8, ["get", "r"]] } });
    map.addLayer({ id: "pt-lbl", type: "symbol", source: "pts", filter: ["==", ["get", "hot"], true], minzoom: 2, layout: { "text-field": ["get", "label"], "text-font": FB, "text-size": 10, "text-letter-spacing": 0.14, "text-transform": "uppercase", "text-offset": [0, 1.3], "text-anchor": "top", "text-optional": true },
      paint: { "text-color": "rgba(240,240,250,.82)", "text-halo-color": "rgba(5,6,10,.9)", "text-halo-width": 1.2 } });
  }
  function startPulse() {
    if (!reduce) (function anim() { if (!map.getLayer("pulse")) return; var t = (performance.now() % 2200) / 2200; map.setPaintProperty("pulse", "circle-radius", 8 + t * 18); map.setPaintProperty("pulse", "circle-stroke-opacity", 0.7 * (1 - t)); setTimeout(function () { requestAnimationFrame(anim); }, 50); })();
  }
  function bindLayers() {
    ["pt", "dc"].forEach(function (id) {
      map.on("mousemove", id, function (e) { if (window.__gxWxHit && window.__gxWxHit(e.point)) return; if (!pinned) showCard(e.features[0], e.point, false); map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, function () { if (!pinned) hideCard(); map.getCanvas().style.cursor = ""; });
    });
    map.on("click", function (e) {
      if (SKY.on) {
        if (SKY.alt3d) { var pi = skyPick(e.point); if (pi != null) satCard(pi, e.point); else clearSat(); return; }
        var sf = map.getLayer("sat") ? map.queryRenderedFeatures([[e.point.x - 10, e.point.y - 10], [e.point.x + 10, e.point.y + 10]], { layers: ["sat"] }) : [];
        var cc = map.getCenter(), R = Math.PI / 180;
        sf = sf.filter(function (f) { var q = f.geometry.coordinates; return Math.sin(cc.lat * R) * Math.sin(q[1] * R) + Math.cos(cc.lat * R) * Math.cos(q[1] * R) * Math.cos((q[0] - cc.lng) * R) > 0.05; });
        sf.sort(function (a, b) { var pa = map.project(a.geometry.coordinates), pb = map.project(b.geometry.coordinates); return Math.hypot(pa.x - e.point.x, pa.y - e.point.y) - Math.hypot(pb.x - e.point.x, pb.y - e.point.y); });
        if (sf.length) satCard(sf[0].properties.i, e.point); else clearSat(); return; }
      if (window.__gxWxHit && window.__gxWxHit(e.point)) { hideCard(true); return; }   /* a grid alert diamond on top: gridlayer.js shows its card */
      /* follow-up pt1810u: inside an Internet region (chip on), other items win only on a tight 3 px hit; otherwise the region card opens */
      var inetHit = ON.internet && INET && map.getLayer("inet-fill") && map.getLayoutProperty("inet-fill", "visibility") !== "none" ? map.queryRenderedFeatures(e.point, { layers: ["inet-fill"] })[0] : null,
        T = inetHit ? 3 : 8, T9 = inetHit ? 3 : 9;
      var f = map.queryRenderedFeatures([[e.point.x - T, e.point.y - T], [e.point.x + T, e.point.y + T]], { layers: ["pt", "dc"].filter(function (l) { return map.getLayoutProperty(l, "visibility") !== "none"; }) })[0];
      if (!f && (ON.towers || ON.grid || ON.hydro)) {
        var il = []; INF_K.forEach(function (k) { if (ON[k]) il = il.concat(INF[k].Q); });
        var fl = map.queryRenderedFeatures([[e.point.x - T9, e.point.y - T9], [e.point.x + T9, e.point.y + T9]], { layers: il.filter(function (l) { return map.getLayer(l); }) });
        f = fl.filter(function (x) { return x.source === "hy"; })[0] || fl[0];   /* a dam wins over the substation at its foot */
        if (f && f.source === "grid") f.properties.kind = f.geometry.type === "Point" ? "ss" : "gl";
        if (f && f.properties.cluster) { var cid = f.properties.cluster_id, cc0 = f.geometry.coordinates; hideCard(true);
          map.getSource("tw").getClusterExpansionZoom(cid).then(function (z) { map.easeTo({ center: cc0, zoom: Math.min(z, 12), duration: reduce ? 0 : 600 }); }, function () {}); return; }
      }
      if (!f && ON.sea && (map.getLayer("sea-line") || map.getLayer("sea-line-approx"))) f = map.queryRenderedFeatures([[e.point.x - T, e.point.y - T], [e.point.x + T, e.point.y + T]], { layers: ["sea-ls", "sea-line", "sea-line-approx"].filter(function (l) { return map.getLayer(l); }) })[0];
      if (!f) f = inetHit;
      if (f) showCard(f, e.point, true); else hideCard(true);
    });
  }

  /* pt1810u: choropleth of IODA internet status. Green normal, amber degraded, red outage, grey = IODA has no live data for it. */
  function inetCol(l) { return l >= 3 ? COL.out : l === 2 ? COL.deg : l === 0 ? COL.ok : COL.na; }
  function applyInet() {
    if (!INET || !INETG || !map || !map.getSource("inet")) return;
    var P = INET.places || {};
    map.getSource("inet").setData({ type: "FeatureCollection", features: (INETG.features || []).map(function (f) {
      var r = P[f.properties.k], l = r ? r.level : INET.all_down ? -1 : 0;   /* Matt: green unless there is evidence of a problem */
      return { type: "Feature", geometry: f.geometry, properties: { kind: "inet", k: f.properties.k, n: f.properties.n, c: inetCol(l), l: l, o: l >= 3 ? 0.55 : l === 2 ? 0.45 : l === 0 ? 0.28 : 0.08 } }; }) });
    if (D) applyData();
    var nd = document.querySelector("#nx_leg .s-na"); if (nd && nd.parentNode) nd.parentNode.style.display = INET.all_down ? "" : "none";   /* "No data" only when every feed is down */
  }
  function inetCard(p) {
    var r = (INET && INET.places || {})[p.k] || (INET && !INET.all_down ? { name: p.n, level: 0, status: "Normal", signals: [] } : { name: p.n, level: -1, status: "No data", signals: [] }), c = inetCol(r.level);
    var nws = (r.news || []).map(function (h) { return '<li>' + (url(h.url) ? '<a href="' + url(h.url) + '" target="_blank" rel="noopener noreferrer">' + esc(h.t) + '</a>' : esc(h.t)) + (h.src ? ' · ' + esc(h.src) : '') + (h.at ? ' · ' + esc(ago(h.at)) : '') + '</li>'; }).join("");
    var sig = (r.signals || []).map(function (s) { return '<li>' + esc(s.name) + ' · ' + (s.pct != null ? (s.live ? 'now ' : '') + esc(s.pct) + '% of normal (' + esc(100 - s.pct) + '% drop)' : 'below normal') + (s.since ? ' · since ' + esc(ago(s.since)) : '') + '</li>'; }).join("");
    return '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Internet · ' + esc(r.status) + '</span><h3>' + esc(r.name || p.n) + '</h3>' +
      (r.level < 0 ? '<p>No live internet measurements for this place right now.</p>' :
       sig ? '<p>Signals below their normal level:</p><ul>' + sig + '</ul>' : nws ? '' : '<p>No problem reported. IODA signals (routing, active probing, network telescope) at normal levels.</p>') +
      (nws ? '<p>In the news:</p><ul>' + nws + '</ul>' : '') +
      '<dl>' + (r.since ? '<dt>Since</dt><dd>' + esc(ago(r.since)) + '</dd>' : '') + (r.alerts_24h != null ? '<dt>IODA alerts, 24 h</dt><dd>' + num(r.alerts_24h) + '</dd>' : '') +
      '<dt>IODA data from</dt><dd>' + esc(ago(INET && INET.generated || r.checked)) + (INET && INET.via === "box-relay" ? ' (relayed)' : '') + '</dd></dl>' +
      '<div class="acts">' + linkA(r.src || "https://ioda.inetintel.cc.gatech.edu/", "Live IODA dashboard") + '</div><p class="age">Measured by IODA, Georgia Tech. A drop can be a local network problem, a power cut or a shutdown.</p>';
  }
  function applyWorld() {
    if (!WORLD || !D || !map.getSource("cty")) return;
    var by = {}; (D.outages.countries || []).forEach(function (c) { by[c.geo] = c; });
    var feats = (WORLD.features || []).filter(function (f) { return by[f.properties.name]; }).map(function (f) {
      var c = by[f.properties.name]; return { type: "Feature", geometry: f.geometry, properties: { c: c.major ? COL.out : COL.deg, cur: !!c.cur } };
    });
    map.getSource("cty").setData({ type: "FeatureCollection", features: feats });
    vis();
  }
  function applyDc() {
    if (!DC || !map.getSource("dc")) return;
    var ix = {}; (DC.cols || []).forEach(function (c, i) { ix[c] = i; });
    map.getSource("dc").setData({ type: "FeatureCollection", features: (DC.rows || []).map(function (r, i) {
      return { type: "Feature", id: i, geometry: { type: "Point", coordinates: [r[ix.lon], r[ix.lat]] }, properties: { kind: "dc", i: i, n: r[ix.nets] || 0 } }; }) });
  }
  var PTS = [];
  function applyData() {
    var f = [];
    if (!INET) (D.outages.countries || []).forEach(function (c, i) {   /* pt1810u: the choropleth replaces these dots once it is in */
      if (c.lon == null) return;
      f.push(feat(c.lon, c.lat, { kind: "country", i: i, c: c.major ? COL.out : COL.deg, fill: c.cur ? (c.major ? COL.out : COL.deg) : "#05060a", sw: 2, r: c.cur ? 7 : 5, hot: !!c.cur, label: c.name, layer: "internet" }));
    });
    if (!INET) (D.outages.us_regions || []).forEach(function (r, i) {
      f.push(feat(r.lon + 0.6, r.lat - 0.4, { kind: "region", i: i, c: COL.deg, fill: "#05060a", sw: 2, r: 5, hot: false, label: r.name, layer: "internet" }));
    });
    ((D.power || {}).states || []).forEach(function (s, i) {
      if (!s.outages) return;
      var big = s.outages >= 1500;
      f.push(feat(s.lon, s.lat, { kind: "power", i: i, c: big ? COL.deg : "#C9CCD6", fill: big ? COL.deg : "rgba(201,204,214,.35)", sw: 1.2, r: Math.min(12, 3.5 + Math.log10(s.outages + 1) * 2), hot: big, label: s.name, layer: "power" }));
    });
    (D.cloud || []).forEach(function (c, i) {
      var l = c.level, ring = l >= 2 ? lvCol(l) : PROV[c.p] || COL.minor;
      f.push(feat(c.lon, c.lat, { kind: "cloud", i: i, c: ring, fill: PROV[c.p] || COL.minor, sw: l >= 2 ? 3 : 1.5, r: 4.5, hot: l >= 2, label: c.name, layer: "cloud" }));
    });
    PTS = f; vis(); summary(); list(); if (WORLD) applyWorld();
  }
  function feat(lon, lat, p) { return { type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: p }; }
  function leg() {
    var box = $("nx_leg"); if (!box) return;
    box.querySelectorAll("[data-leg]").forEach(function (el) { el.hidden = !ON[el.getAttribute("data-leg")]; });
  }
  function key() {
    var btn = $("nx_leg_btn"), body = $("nx_leg_body"); if (!btn || !body) return;
    var open = body.hidden;
    body.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function vis() {
    leg();
    if (!map || !map.getSource("pts")) return;
    if (SKY.on) return;
    ON.power = ON.ops = !!ON.grid;   /* Nov 24 2026 (Matt): one "Power grid" chip runs outages, operators and the 230 kV+ lines */
    map.getSource("pts").setData({ type: "FeatureCollection", features: PTS.filter(function (x) { return mapOn(x.properties.layer); }) });
    ["cty-fill", "cty-line"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", mapOn("internet") && !INET ? "visible" : "none"); });
    ["inet-fill", "inet-line"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", mapOn("internet") ? "visible" : "none"); });
    /* Nov 24 2026 (pt1816u): with Power grid on, the "normal" internet green is a faint tint so the green / yellow / red power lines stay readable (#129 raised it to 0.28 and washed every U.S. line green) */
    if (map.getLayer("inet-fill")) map.setPaintProperty("inet-fill", "fill-opacity", mapOn("grid") ? ["case", ["==", ["get", "l"], 0], 0.06, ["get", "o"]] : ["get", "o"]);
    if (map.getLayer("inet-line")) map.setPaintProperty("inet-line", "line-opacity", mapOn("grid") ? ["case", ["==", ["get", "l"], 0], 0.12, 0.45] : 0.45);
    ["dc", "dc-glow"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", mapOn("dc") ? "visible" : "none"); });
    SEA_L.forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", mapOn("sea") ? "visible" : "none"); });
    if (mapOn("sea")) seaLoad();
    INF_K.forEach(function (k) { INF[k].L.forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", mapOn(k) ? "visible" : "none"); }); if (mapOn(k)) infLoad(k); }); infPanel();
    document.querySelectorAll("#nx_f button").forEach(function (b) { b.setAttribute("aria-pressed", ON[b.dataset.k] ? "true" : "false"); });
    try { document.dispatchEvent(new CustomEvent("nx:layers", { detail: { ops: mapOn("grid") } })); } catch (e) {}   /* gridlayer.js (merged The Grid) */
  }

  function summary() {
    if (SKY.on) return;
    var s = D.summary || {}, iss = (D.nets || []).filter(function (n) { return n.level >= 2; }), maj = iss.filter(function (n) { return n.level >= 3; });
    var chip = $("nx_chip"), txt;
    if (maj.length) { txt = maj.length + " major outage" + (maj.length > 1 ? "s" : "") + " · " + maj[0].name; chip.className = "nx-chip live s-out"; }
    else if (iss.length) { txt = iss.length + " network" + (iss.length > 1 ? "s" : "") + " disrupted · " + iss[0].name; chip.className = "nx-chip live s-deg"; }
    else { txt = innerWidth < 768 ? "No major U.S. outages · " + (s.networks || 0) + " tracked" : "No major U.S. network outages · " + (s.networks || 0) + " tracked"; chip.className = "nx-chip live s-ok"; }
    $("nx_sum").textContent = txt;
    $("nx_more_lbl").textContent = "All " + (s.networks || "") + " networks";
  }

  /* ---------- detail card ---------- */
  var card = $("nx_card"), pinned = false;
  function linkA(u, t) { var h = url(u); return h ? '<a href="' + h + '"' + (/^\//.test(u) ? "" : ' target="_blank" rel="noopener noreferrer"') + '>' + esc(t) + '</a>' : ""; }
  function showCard(ft, pt, pin) {
    LASTPT = pt; LASTFT = ft;
    var p = ft.properties, h = "", c;
    if (p.kind === "dc") {
      var ix = {}; (DC.cols || []).forEach(function (k, i) { ix[k] = i; }); var r = DC.rows[p.i];
      h = '<span class="st" style="color:' + COL.dc + '"><i style="background:' + COL.dc + '"></i>Data center</span><h3>' + esc(r[ix.name]) + '</h3><dl><dt>Operator</dt><dd>' + esc(r[ix.org]) + '</dd><dt>Location</dt><dd>' + esc([r[ix.city], r[ix.cc]].filter(Boolean).join(", ")) +
        '</dd><dt>Networks</dt><dd>' + num(r[ix.nets]) + '</dd><dt>Exchanges</dt><dd>' + num(r[ix.ixs]) + '</dd></dl><div class="acts">' + linkA("https://www.peeringdb.com/fac/" + r[ix.id], "PeeringDB record") + '</div>';
    } else if (p.kind === "country") {
      var o = D.outages.countries[p.i]; c = o.major ? COL.out : COL.deg;
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Internet · ' + (o.cur ? (o.major ? "Major outage now" : "Outage signal now") : "Outage in the last 24 h") + '</span><h3>' + esc(o.name) + '</h3>' +
        '<dl><dt>Signals</dt><dd>' + esc((o.signals || []).map(function (s) { return { bgp: "Routing (BGP)", "ping-slash24": "Active probing", "merit-nt": "Network telescope", gtr: "Google traffic", "gtr-norm": "Google traffic" }[s] || s; }).join(", ")) + '</dd><dt>Started</dt><dd>' + esc(ago(o.last)) + '</dd></dl>' +
        '<div class="acts">' + linkA(o.ioda, "Live IODA dashboard") + '</div><p class="age">Measured by IODA, Georgia Tech. A signal can be a local network problem, a power cut or a shutdown.</p>';
    } else if (p.kind === "region") {
      var rg = D.outages.us_regions[p.i];
      h = '<span class="st" style="color:' + COL.deg + '"><i style="background:' + COL.deg + '"></i>Internet · outage signal, last 24 h</span><h3>' + esc(rg.name) + '</h3><dl><dt>Events</dt><dd>' + num(rg.events) + '</dd></dl><div class="acts">' + linkA(rg.ioda, "Live IODA dashboard") + '</div>';
    } else if (p.kind === "power") {
      var s = D.power.states[p.i]; c = s.outages >= 1500 ? COL.deg : COL.minor;
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Power · ' + (s.outages >= 1500 ? "Major outages" : "Outages reported") + '</span><h3>' + esc(s.name) + '</h3><dl><dt>Customers out</dt><dd>' + num(s.outages) + '</dd></dl>' +
        ((s.top || []).length ? '<ul>' + s.top.map(function (u) { return '<li>' + (url(u.web) ? '<a href="' + url(u.web) + '" target="_blank" rel="noopener noreferrer">' + esc(u.name) + '</a>' : esc(u.name)) + ' · ' + num(u.outages) + '</li>'; }).join("") + '</ul>' : '') +
        '<div class="acts">' + (s.st ? '<button type="button" class="gx-fly" data-state="' + esc(s.st) + '">Utilities and outage maps</button>' : '') + '<button type="button" class="gx-fly" data-more="gx-outages">Outages by state</button></div>';
    } else if (p.kind === "cable" || p.kind === "ls") { h = seaCard(p);
    } else if (p.kind === "tw" || p.kind === "gl" || p.kind === "ss" || p.kind === "hy") { h = infCard(p);
    } else if (p.kind === "inet") { h = inetCard(p);
    } else if (p.kind === "cloud") {
      var cl = D.cloud[p.i], n = (D.nets || []).filter(function (x) { return x.id === cl.p; })[0] || {}; c = lvCol(cl.level);
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(PNAME[cl.p]) + ' · ' + esc(lvName(cl.level)) + '</span><h3>' + esc(cl.name) + '</h3><p>' + esc(n.status || "") + '</p>' +
        '<div class="acts">' + linkA(n.status_url, "Official status") + linkA(n.page, "Full analysis") + linkA(n.support, "Support") + '</div>';
    }
    card.innerHTML = h + '<button type="button" class="nx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
    card.hidden = false; requestAnimationFrame(function () { card.classList.add("in"); });
    pinned = !!pin; card.classList.toggle("pin", pinned);
    window.__bnPlace(card, pt);
    var cxb = card.querySelector(".nx-cx"); if (cxb) cxb.onclick = function () { hideCard(true); };
  }
  function hideCard(force) { if (pinned && !force) return; pinned = false; card.classList.remove("in", "pin"); setTimeout(function () { if (!card.classList.contains("in")) card.hidden = true; }, 200); }
  addEventListener("keydown", function (e) { if (e.key === "Escape") { if (SKY.on && SKY.sel != null) clearSat(); else hideCard(true); more(false); } });


  /* ---------- undersea cables (pt1812u): OSM + NOAA routes, coloured green / yellow / red by inferred status. No chokepoint notes. ---------- */
  var SEA = { geo: null, st: null, busy: false }, SEA_L = ["sea-line", "sea-line-approx", "sea-ls"];
  var CCOL = { 0: "#2FD67B", 1: "#F5D547", 2: "#FF3B3B" };
  function seaCol(lv) { return CCOL[lv] || CCOL[0]; }
  function seaLayers() {
    map.addSource("sea", { type: "geojson", data: EMPTY, tolerance: 0.6 });
    var vz = "none";   /* pt1833u: mapLayerIn reveals sea after internet and the grid */
    var seaPaint = { "line-color": ["match", ["get", "lv"], 2, CCOL[2], 1, CCOL[1], CCOL[0]], "line-opacity": ["case", [">", ["get", "lv"], 0], 0.95, 0.75],
        "line-width": ["interpolate", ["linear"], ["zoom"], 1, ["case", [">", ["get", "lv"], 0], 1.6, 0.7], 6, ["case", [">", ["get", "lv"], 0], 3, 1.5], 10, 2.4] };
    map.addLayer({ id: "sea-line", type: "line", source: "sea", filter: ["all", ["==", ["geometry-type"], "LineString"], ["!=", ["get", "s"], "approx"]], layout: { visibility: vz, "line-cap": "round", "line-join": "round" },
      paint: seaPaint }, "glow");
    map.addLayer({ id: "sea-line-approx", type: "line", source: "sea", filter: ["all", ["==", ["geometry-type"], "LineString"], ["==", ["get", "s"], "approx"]], layout: { visibility: vz, "line-cap": "round", "line-join": "round" },
      paint: Object.assign({ "line-dasharray": [2.4, 1.4] }, seaPaint) }, "glow");
    map.addLayer({ id: "sea-ls", type: "circle", source: "sea", filter: ["==", ["geometry-type"], "Point"], minzoom: 2.5, layout: { visibility: vz },
      paint: { "circle-color": "#05060a", "circle-stroke-color": "#E8ECF5", "circle-stroke-width": 1.2, "circle-radius": ["interpolate", ["linear"], ["zoom"], 2.5, 2, 8, 4.5] } }, "glow");
  }
  function seaLoad() {
    if (SEA.geo || SEA.busy || !map) return; SEA.busy = true;
    var el = $("nx_sea"); if (el) el.hidden = true;
    Promise.all([getJSON("/api/netmap/cables.json"), getJSON("/api/netmap/cables").catch(function () { return null; })]).then(function (r) {
      SEA.geo = r[0]; SEA.st = r[1]; SEA.busy = false; seaApply();
    }, function () { SEA.busy = false; });
  }
  function seaSquish(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, ""); }
  function seaInfo(n) {
    var d = (SEA.st && SEA.st.cables) || {}, k, best = null; if (!n) return null;
    var ns = seaSquish(n);
    for (k in d) {
      var ks = seaSquish(k);
      if (ns && ks && (ns === ks || ns.indexOf(ks) === 0 || ks.indexOf(ns) === 0)) {
        if (!best || ks.length > (best._ks || "").length) best = Object.assign({ _ks: ks }, d[k]);
      }
    }
    return best;
  }
  function seaApply() {
    if (!map.getSource("sea") || !SEA.geo) return;
    SEA.geo.features.forEach(function (f, i) {
      var p = f.properties; p.kind = f.geometry.type === "Point" ? "ls" : "cable"; p.i = i;
      var inf = p.kind === "cable" ? seaInfo(p.n) : null; p.lv = inf ? inf.lv : 0;
    });
    map.getSource("sea").setData(SEA.geo);
  }
  function seaWhen(ts) { var d = new Date(ts); return isFinite(d) ? d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : ""; }
  function seaCard(p) {
    var f = SEA.geo.features[p.i].properties;
    if (p.kind === "ls") {
      return '<span class="st">Cable landing station</span><h3>' + esc(f.n || "Cable landing station") + '</h3><dl>' +
        (f.op ? '<dt>Operator</dt><dd>' + esc(f.op) + '</dd>' : "") +
        '<dt>Source</dt><dd>' + (f.s === "noaa" ? "NOAA cable area, U.S. waters" : "OpenStreetMap") + '</dd></dl>' +
        '<p class="age">' + (f.s === "noaa" ? "General location of the cable area, from NOAA Office for Coastal Management." : "Landing station as mapped by OpenStreetMap contributors.") + '</p>';
    }
    var inf = seaInfo(f.n), lv = inf ? inf.lv : 0, c = seaCol(lv), st = inf ? inf.status : "Working";
    var why = inf && inf.reason ? esc(inf.reason) : "No fault reports.";
    var src = "";
    if (inf && (inf.src || inf.url)) src = '<dt>Source</dt><dd>' + (inf.url ? linkA(inf.url, inf.src || "Source") : esc(inf.src || "")) + (inf.at ? ", " + esc(seaWhen(inf.at)) : "") + '</dd>';
    return '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(st) + '</span>' +
      '<h3>' + esc(f.n || "Unnamed cable") + '</h3><dl>' + (f.op ? '<dt>Operator</dt><dd>' + esc(f.op) + '</dd>' : "") +
      '<dt>Status</dt><dd>' + esc(st) + '</dd><dt>Why</dt><dd>' + why + '</dd>' + src +
      (f.st ? '<dt>NOAA record</dt><dd>' + esc(f.st) + '</dd>' : "") +
      (f.s === "approx" ? '<dt>Route</dt><dd>Approximate route</dd>' : "") +
      '<dt>Route source</dt><dd>' + (f.s === "noaa" ? "NOAA cable area, U.S. waters" : f.s === "approx" ? "Official landing points, Wikidata coordinates (CC0). Not a surveyed cable path." : "OpenStreetMap") + '</dd></dl>' +
      '<p class="age">' + esc((SEA.st && SEA.st.basis) || "Status is inferred from public fault reports. Operators publish no live feed.") + '</p>';
  }

  /* ---------- U.S. infrastructure (pt1785u Stage 3): FCC ASR towers and the OSM power grid. Both off by default, loaded on first use ---------- */
  var INF = {
    towers: { url: "/api/netmap/towers.json", L: ["tw-cl", "tw-cnt", "tw-pt"], Q: ["tw-cl", "tw-pt"], d: null, busy: false, err: false },
    grid: { url: "/api/netmap/grid.json", L: ["gl-lo", "gl-hi", "gss"], Q: ["gss", "gl-hi", "gl-lo"], d: null, busy: false, err: false }
,
    hydro: { url: "/api/netmap/hydro.json", L: ["hy-pt"], Q: ["hy-pt"], d: null, busy: false, err: false }   /* pt1815u stage 2: hydro dams + reservoir level risk */
  }, INF_K = ["towers", "grid", "hydro"], INF_L = [];
  var HCOL = { ok: "#2FD67B", low: "#FF7A1A", out: "#FF3B3B", na: "#7C8190" }, HWORD = { ok: "Water level normal", low: "Low water: output reduced", out: "Near or below minimum power pool", na: "No water level data" }, HLV = {};
  function hydroData() {
    var d = INF.hydro.d; if (!d || !map || !map.getSource("hy")) return;
    map.getSource("hy").setData({ type: "FeatureCollection", features: d.p.map(function (r, i) { var lv = HLV[r[7]]; return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { kind: "hy", i: i, mw: r[3], st: lv ? lv.status : "na" } }; }) });
  }
  function hydroLevels() { getJSON("/api/netmap/reservoirs").then(function (j) { HLV = j.levels || {}; hydroData(); }, function () {}); }
  INF_K.forEach(function (k) { INF_L = INF_L.concat(INF[k].L); });
  var TWC = "#9FB4FF";
  /* Nov 24 2026 (Matt): 230 kV+ lines coloured by the live status of the U.S. operator/BA area they sit in (no public per-line status exists).
     green normal, yellow strained/warning, red outage/emergency, grey = crosses operator areas or outside them. */
  var LCOL = { ok: "#2FD67B", strain: "#F5D547", out: "#FF3B3B", na: "#7C8190" }, LWORD = { ok: "Normal", strain: "Strained or warning", out: "Outage or emergency", na: "No live status" };
  var OPS = null, LASTPT = null, LASTFT = null, FOPS = null, FST = {};   /* pt1815u: FOPS = synchronous areas outside the U.S. with a keyless live frequency feed */
  function opSt(id) { return (window.__gxRegionStatus || {})[id] || FST[id] || "na"; }
  function lineCol() {
    if (!OPS || !OPS.length) return LCOL.na;
    var e = ["case"]; OPS.forEach(function (o) { e.push(["within", o.g], LCOL[opSt(o.id)] || LCOL.na); }); e.push(LCOL.na); return e;
  }
  function gridColor() {
    if (FOPS && !(OPS && OPS.__f)) { OPS = (OPS || []).concat(FOPS); OPS.__f = 1; }   /* gridops.json may land before or after the frequency areas */
    if (!map) return; var c = lineCol();
    ["gl-lo", "gl-hi"].forEach(function (l) { if (map.getLayer(l)) map.setPaintProperty(l, "line-color", c); });
    if (map.getLayer("gss")) map.setPaintProperty("gss", "circle-stroke-color", c);
  }
  function inRing(x, y, r) { var c = false; for (var i = 0, j = r.length - 1; i < r.length; j = i++) { var a = r[i], b = r[j]; if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) c = !c; } return c; }
  function opAt(ll) {
    if (!OPS || !ll) return null;
    for (var i = 0; i < OPS.length; i++) { var ps = OPS[i].g.coordinates; for (var k = 0; k < ps.length; k++) if (inRing(ll.lng, ll.lat, ps[k][0]) && !ps[k].slice(1).some(function (h) { return inRing(ll.lng, ll.lat, h); })) return OPS[i]; }
    return null;
  }
  document.addEventListener("gx:status", gridColor);
  function kvCol() { return ["step", ["get", "v"], "#6E6A9A", 300, "#9C8CE0", 450, "#C9B8FF", 700, "#F0F0FA"]; }
  function infLayers() {
    map.addSource("tw", { type: "geojson", data: EMPTY, cluster: true, clusterRadius: 46, clusterMaxZoom: 10, maxzoom: 12 });
    function L(o) { o.layout = o.layout || {}; o.layout.visibility = "none"; map.addLayer(o, "glow"); }
    L({ id: "tw-cl", type: "circle", source: "tw", filter: ["has", "point_count"],
      paint: { "circle-color": "rgba(159,180,255,.16)", "circle-stroke-color": TWC, "circle-stroke-width": 1, "circle-stroke-opacity": 0.6,
        "circle-radius": ["step", ["get", "point_count"], 9, 100, 13, 1000, 17, 5000, 22] } });
    L({ id: "tw-cnt", type: "symbol", source: "tw", filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": FB, "text-size": 10, "text-allow-overlap": true },
      paint: { "text-color": "rgba(240,240,250,.9)" } });
    map.addSource("hy", { type: "geojson", data: EMPTY });
    L({ id: "hy-pt", type: "circle", source: "hy", layout: { "circle-sort-key": ["case", ["==", ["get", "st"], "na"], 0, 1] },
      paint: { "circle-color": ["match", ["get", "st"], "ok", HCOL.ok, "low", HCOL.low, "out", HCOL.out, "rgba(124,129,144,.35)"], "circle-stroke-color": ["match", ["get", "st"], "na", "#A9AEBB", "#05060a"], "circle-stroke-width": 1,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["case", ["!=", ["get", "st"], "na"], 6, [">=", ["get", "mw"], 2000], 3, 1.6], 6, ["interpolate", ["linear"], ["sqrt", ["get", "mw"]], 5, 3, 150, 11]] } });
    L({ id: "tw-pt", type: "circle", source: "tw", filter: ["!", ["has", "point_count"]],
      paint: { "circle-color": TWC, "circle-stroke-color": "#05060a", "circle-stroke-width": 1, "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 2.5, 12, 5] } });
  }
  function gridLayers() {
    if (map.getSource("grid")) return;
    fetch("/api/netmap/gridops.json").then(function (r) { return r.json(); }).then(function (j) { OPS = j.ops || []; gridColor(); }).catch(function () {});
    function freq() { fetch("/api/netmap/gridfreq").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) {
      FST = {}; FOPS = (j.areas || []).map(function (a) { FST[a.id] = a.status; return { id: a.id, name: a.name, g: a.g, fr: a }; }); if (OPS) OPS.__f = 0; gridColor(); infPanel();
      var lv = $("gx_live"); if (lv) lv.textContent = "Live: U.S., " + FOPS.map(function (a) { return a.name.replace(/ synchronous grid| grid \(NESO\)/, "").replace("Continental Europe", "Europe").replace("Great Britain", "GB"); }).join(", "); }).catch(function () {}); }
    freq(); setInterval(function () { if (!document.hidden) freq(); }, 300000);
    map.addSource("grid", { type: "vector", tiles: [location.origin + "/api/netmap/gridtiles/{z}/{x}/{y}.pbf"], minzoom: 0, maxzoom: 8 });
    function L(o) { o.layout = o.layout || {}; o.layout.visibility = mapOn("grid") && !SKY.on ? "visible" : "none"; map.addLayer(o, "glow"); }
    L({ id: "gl-lo", type: "line", source: "grid", "source-layer": "grid", minzoom: 5, filter: ["all", ["==", ["geometry-type"], "LineString"], ["<", ["get", "v"], 300]], layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": lineCol(), "line-opacity": 0.75, "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.6, 10, 1.6] } });
    L({ id: "gl-hi", type: "line", source: "grid", "source-layer": "grid", filter: ["all", ["==", ["geometry-type"], "LineString"], [">=", ["get", "v"], 300]], layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": lineCol(), "line-opacity": 0.8, "line-width": ["interpolate", ["linear"], ["zoom"], 2, ["case", [">=", ["get", "v"], 450], 0.9, 0.5], 6, ["case", [">=", ["get", "v"], 450], 1.8, 1.1], 10, 2.6] } });
    L({ id: "gss", type: "circle", source: "grid", "source-layer": "grid", minzoom: 5.5, filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-color": "#05060a", "circle-stroke-color": lineCol(), "circle-stroke-width": 1.4, "circle-radius": ["interpolate", ["linear"], ["zoom"], 5.5, 2, 10, 4.5] } });
  }
  function infLoad(k) {
    if (k === "grid" && map) gridLayers();
    var o = INF[k]; if (o.d || o.busy || !map) return; o.busy = true; o.err = false; infPanel();
    getJSON(o.url).then(function (j) {
      o.d = j; o.busy = false;
      if (k === "towers") map.getSource("tw").setData({ type: "FeatureCollection", features: j.p.map(function (r, i) { return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { kind: "tw", i: i } }; }) });
      if (k === "hydro") { hydroData(); hydroLevels(); setInterval(function () { if (!document.hidden) hydroLevels(); }, 1800000); }
      // Grid geometry is fetched as vector tiles for the visible viewport, never a national GeoJSON download.
      infPanel();
    }, function () { o.busy = false; o.err = true; infPanel(); });
  }
  function infPanel() {
    var el = $("nx_inf"); if (!el) return; var on = INF_K.filter(function (k) { return ON[k]; });
    el.hidden = !on.length || SKY.on; if (el.hidden) return;
    var row = function (k, key, txt) { var o = INF[k]; return '<li>' + key + '<span>' + (o.err ? "Unavailable right now" : o.busy || !o.d ? "Loading…" : txt(o.d)) + '</span></li>'; };
    el.innerHTML = '<ul>' + on.map(function (k) {
      if (k === "towers") return row(k, '<i style="background:' + TWC + '"></i><b>Cell towers</b>', function (d) { return num(d.p.length) + " FCC-registered towers · not every cell site"; });
      return row(k, '<i class="ln" style="background:' + LCOL.ok + '"></i><i class="ln" style="background:' + LCOL.strain + '"></i><i class="ln" style="background:' + LCOL.out + '"></i><b>Power grid</b>', function (d) { return "Worldwide lines and substations, 220 kV and up: green normal, yellow strained or warning, red outage or emergency. Live status: U.S. grid operator areas" + (FOPS ? ", " + FOPS.map(function (a) { return a.name.replace(/ synchronous grid| grid \(NESO\)/, ""); }).join(", ") + " (grid frequency)" : "") + ". Grey: no free live status feed · © OpenStreetMap contributors, Overture Maps Foundation"; });
    }).join("") + '</ul>';
  }
  function kvTxt(v) { return v ? v + " kV" : "Unknown"; }
  function infCard(p) {
    var h = "", c;
    if (p.kind === "hy") {
      var hd = INF.hydro.d, hr = hd.p[p.i], lv = HLV[hr[7]], hs = lv ? lv.status : "na", sat = lv && lv.method === "satellite, relative to usual level"; c = HCOL[hs];
      var hw = sat && hs !== "na" ? { ok: "Near usual level (satellite)", low: "Well below usual level (satellite)", out: "Far below usual level (satellite)" }[hs] : HWORD[hs];
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Hydroelectric dam · ' + esc(hw) + '</span><h3>' + esc(lv && lv.dam ? lv.dam : hr[2]) + '</h3><dl>' +
        '<dt>Capacity</dt><dd>' + num(hr[3]) + ' MW</dd>' + (hr[4] ? '<dt>Operator</dt><dd>' + esc(hr[4]) + '</dd>' : "") + (hr[5] ? '<dt>In service</dt><dd>' + hr[5] + '</dd>' : "") + '<dt>Country</dt><dd>' + esc(hr[6]) + '</dd>' +
        (lv && !sat && lv.ft != null ? '<dt>' + esc(lv.lake) + '</dt><dd>' + window.BNUnits.fmtFt(lv.ft) + ', ' + window.BNUnits.fmtFt(lv.above_min) + ' above ' + esc(lv.min_name || "minimum power pool") + ' (' + window.BNUnits.fmtFt(lv.min_pool) + ')</dd>' +
          '<dt>7-day trend</dt><dd>' + (lv.chg7 == null ? "–" : (lv.chg7 > 0 ? "+" : "") + window.BNUnits.fmtFt(lv.chg7, 1)) + '</dd><dt>Reading</dt><dd>' + esc(lv.date) + '</dd>' : "") +
        (sat && lv.dev_m != null ? '<dt>Reservoir</dt><dd>' + esc(lv.lake) + ' (satellite)</dd><dt>Vs. usual level</dt><dd>' + (lv.dev_m > 0 ? "+" : "") + window.BNUnits.fmtLenM(lv.dev_m, 1) + ' vs. the median for this time of year (' + lv.years + ' years since ' + lv.since + ')</dd><dt>Satellite pass</dt><dd>' + esc(lv.date) + '</dd>' : "") +
        (sat && lv.dev_m == null && lv.date ? '<dt>Last satellite pass</dt><dd>' + esc(lv.date) + '</dd>' : "") + '</dl>' +
        (!lv ? '<p class="age">No free live water-level feed for this reservoir, so no risk colour is shown.</p>'
          : sat ? '<div class="acts">' + linkA(lv.url, "NASA G-REALM lake levels") + '</div><p class="age">Method: satellite, relative to usual level. Amber when below the 20th percentile for this time of year and ' + window.BNUnits.fmtLenM(0.5, 1) + ' or more under the median; red below the 5th percentile and ' + window.BNUnits.fmtLenM(1, 1) + ' or more under. No power-pool threshold is published for this lake.' + (hs === "na" ? " Grey: " + esc(lv.err || "no recent reading") + "." : "") + ' Source: ' + esc(lv.src) + '.</p>'
          : '<div class="acts">' + linkA(lv.url, /Army/.test(lv.src) ? "USACE project data" : "Reclamation lake levels") + '</div><p class="age">Method: lake elevation vs. the official ' + esc(lv.min_name || "minimum power pool") + (lv.level ? ' (CWMS "' + esc(lv.level) + '")' : "") + '. Amber at or below ' + window.BNUnits.fmtFt(lv.amber) + ', red at or below ' + window.BNUnits.fmtFt(lv.red) + '.' + (lv.top ? ' Planned seasonal drawdown can bring this pool low.' : "") + ' Source: ' + esc(lv.src) + '.</p>') +
        '<p class="age">Plant data: WRI Global Power Plant Database (2021), CC BY 4.0. Plants of 25 MW and up.</p>';
    } else if (p.kind === "tw") {
      var d = INF.towers.d, r = d.p[p.i];
      h = '<span class="st" style="color:' + TWC + '"><i style="background:' + TWC + '"></i>Registered antenna structure</span><h3>' + esc(d.owners[r[2]]) + '</h3><dl>' +
        '<dt>Type</dt><dd>' + esc(d.tnames[d.types[r[4]]] || d.types[r[4]]) + '</dd><dt>Height</dt><dd>' + (r[3] ? window.BNUnits.fmtLenM(r[3]) : "–") + '</dd></dl>' +
        '<div class="acts">' + linkA("https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey=" + r[5], "FCC registration record") + '</div>' +
        '<p class="age">FCC Antenna Structure Registration, data as of ' + esc(d.asof) + '. The owner registered the structure; the FCC file does not list which carriers use it. Shorter sites and rooftop or small cells are usually not registered.</p>';
    } else if (p.kind === "gl" || p.kind === "ss") {
      var f = p, oa = map && LASTPT ? opAt(map.unproject([LASTPT.x, LASTPT.y])) : null, os = oa ? opSt(oa.id) : "na"; c = LCOL[os];
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + (p.kind === "ss" ? "Substation" : "Transmission line") + ' · ' + esc(LWORD[os]) + '</span><h3>' + esc(f.n || (p.kind === "ss" ? "Substation" : "Transmission line")) + '</h3><dl>' +
        '<dt>Voltage</dt><dd>' + esc(f.vt || kvTxt(f.v)) + '</dd>' + (f.op ? '<dt>Owner</dt><dd>' + esc(f.op) + '</dd>' : "") + '<dt>Grid area</dt><dd>' + (oa ? esc(oa.name) : "No live operator feed here") + '</dd></dl>' +
        '<p class="age">' + (oa && oa.fr ? 'Status from live grid frequency for the whole ' + esc(oa.name) + (oa.fr.hz ? ' (' + oa.fr.hz.toFixed(3) + ' Hz now, largest swing in 5 min ' + oa.fr.dev_mhz + ' mHz)' : '') + ': within 0.2 Hz of 50 Hz is normal, 0.2-0.8 Hz strained, beyond 0.8 Hz emergency. Source: ' + esc(oa.fr.src) + '. There is no public per-line status.' : oa ? 'Status from ' + esc(oa.name) + ' live feed (EIA-930 demand, ODIN outages, NWS alerts). There is no public per-line status: the colour is the operator area\'s status, and lines that cross operator areas stay grey.' : 'No live operator status here; there is no public per-line status.') + '</p>' +
        '<p class="age">© OpenStreetMap contributors (ODbL). Shows lines and substations of 220 kV and up worldwide; coverage and voltage tags are incomplete and vary by country. No lines below 220 kV. Routes are simplified.' + (f.u ? ' Underground or submarine cable.' : '') + '</p>';
    }
    return h;
  }
  /* ---------- chips ---------- */
  var GMAP = { internet: ["isp"], mobile: ["mobile"], sat: ["sat"], cloud: ["cloud"], pay: ["pay"], apps: ["apps"] };
  document.querySelectorAll("#nx_f button").forEach(function (b) {
    b.addEventListener("click", function () {
      var k = b.dataset.k; ON[k] = !ON[k];
      if (ON[k]) MAPR.show[k] = true; else MAPR.show[k] = false;
      vis(); if (D) list();
      if (ON[k] && k === "dc" && map) map.easeTo({ zoom: Math.max(map.getZoom(), 2.6), duration: reduce ? 0 : 700 });
    });
  });
  if ($("nx_leg_btn")) $("nx_leg_btn").addEventListener("click", function (e) { e.stopPropagation(); key(); });
  document.addEventListener("click", function (e) {
    var box = $("nx_leg"), body = $("nx_leg_body"), btn = $("nx_leg_btn");
    if (!box || !body || body.hidden || box.contains(e.target)) return;
    body.hidden = true; if (btn) btn.setAttribute("aria-expanded", "false");
  });
  vis();
  $("nx_zin").onclick = function () { map && map.zoomIn(); };
  $("nx_zout").onclick = function () { map && map.zoomOut(); };
  $("nx_home").onclick = function () { map && map.fitBounds(US, { padding: PAD(), duration: reduce ? 0 : 900 }); };
  $("nx_world").onclick = function () { map && map.easeTo({ center: [-30, 25], zoom: innerWidth < 768 ? 0.6 : 1.4, duration: reduce ? 0 : 1100 }); };

  /* ---------- All networks panel ---------- */
  function more(on) {
    document.body.classList.toggle("nx-more-on", on); $("nx_more").hidden = !on; $("nx_more_btn").setAttribute("aria-expanded", on ? "true" : "false");
  }
  $("nx_more_btn").onclick = function () { more(true); };
  $("nx_more_x").onclick = function () { more(false); };
  function bars(days) {
    if (!days) return '<div class="nx-bars" aria-hidden="true">' + new Array(31).join('<span class="na"></span>') + '</div>';
    return '<div class="nx-bars" role="img" aria-label="Last 30 days">' + days.map(function (l) { return '<span class="' + (l >= 3 ? "l3" : l === 2 ? "l2" : l === 1 ? "l1" : "") + '"></span>'; }).join("") + '</div>';
  }
  function list() {
    var nets = D.nets || [], s = D.summary || {}, od = D.outages || {};
    var daily = od.daily || [], mx = Math.max.apply(null, daily.concat([1]));
    var w = 300, bw = w / Math.max(1, daily.length);
    var chart = '<div class="nx-chart"><p class="nx-k">Internet outages worldwide, last 30 days</p><svg viewBox="0 0 300 64" preserveAspectRatio="none" role="img" aria-label="Daily count of internet outage events worldwide">' +
      daily.map(function (v, i) { var hh = Math.max(1.5, 60 * v / mx); return '<rect x="' + (i * bw + 1).toFixed(1) + '" y="' + (64 - hh).toFixed(1) + '" width="' + (bw - 2).toFixed(1) + '" height="' + hh.toFixed(1) + '"' + (v >= mx * 0.6 && v > 40 ? ' class="hi"' : '') + '><title>' + v + ' events</title></rect>'; }).join("") +
      '</svg><div class="ax"><span>30 days ago</span><span>Today</span></div></div>';
    var h = '<div class="nx-kpis"><div class="nx-kpi"><b>' + num(s.ok) + '/' + num(s.networks) + '</b><span>Networks normal</span></div><div class="nx-kpi"><b>' + num(s.countries_now) + '</b><span>Countries with an outage now</span></div><div class="nx-kpi"><b>' + num(s.power_customers) + '</b><span>U.S. power customers out</span></div></div>' + chart;
    var shownGroups = (D.groups || []).filter(function (g) { return g.id === "isp" ? ON.internet : g.id === "mobile" ? ON.mobile : g.id === "sat" ? ON.sat : g.id === "cloud" ? ON.cloud : (g.id === "pay" || g.id === "rails") ? ON.pay : g.id === "apps" ? ON.apps : true; });
    if (!shownGroups.length) shownGroups = D.groups || [];
    shownGroups.forEach(function (g) {
      var ns = nets.filter(function (n) { return n.group === g.id; }).sort(function (a, b) { return (b.level - a.level) || a.name.localeCompare(b.name); });
      var bad = ns.filter(function (n) { return n.level >= 2; }).length;
      h += '<div class="nx-gh" id="nxg-' + g.id + '"><h3>' + esc(g.name) + '</h3><span>' + (bad ? bad + " disrupted" : "All normal") + '</span></div>';
      ns.forEach(function (n) {
        h += '<details class="nx-net"><summary><i style="background:' + lvCol(n.level) + '"></i><b>' + esc(n.name) + '</b><em>' + (n.uptime != null ? n.uptime.toFixed(2) + "%" : "") + '</em><small>' + esc(n.link_only ? "Official page" : lvName(n.level)) + ' · ' + esc(n.status) + '</small>' + bars(n.days) + '</summary>' +
          '<div class="nx-nb">' + ((n.incidents || []).length ? '<ul>' + n.incidents.map(function (i) { return '<li>' + esc(i.t) + (i.since ? ' · ' + esc(ago(i.since)) : '') + '</li>'; }).join("") + '</ul>' : '<p style="margin:0">No active incidents.</p>') +
          (n.uptime != null ? '<p style="margin:6px 0 0">30-day availability ' + n.uptime.toFixed(2) + '% (from ' + esc(n.basis || "public data") + ').</p>' : '') +
          '<div class="nx-acts">' + linkA(n.status_url, "Official status") + linkA(n.support, "Contact support") + linkA(n.page, "Full analysis") + linkA(n.ioda, "IODA signal") + '</div></div></details>';
      });
    });
    h += '<p class="nx-src">Bars show the last 30 days: green normal, grey minor, orange disruption, red major outage. Sources: ' + (D.sources || []).map(function (x) { return linkA(x.url, x.name); }).join(" · ") +
      '. Updated ' + esc(ago(D.generated)) + '. Cell coverage by carrier is in the <a href="https://broadbandmap.fcc.gov/" target="_blank" rel="noopener noreferrer">FCC National Broadband Map</a>. <a href="/grid/providers">Cloud provider pages</a></p>';
    $("nx_list").innerHTML = h;
  }

  /* ---------- Sky view: satellite constellations, propagated live in the browser (satellite.js SGP4, CelesTrak elements) ---------- */
  var SKYC = { iss: "#FFFFFF", starlink: "#E8ECF5", gps: "#4FC3F7", glonass: "#B39DFF", galileo: "#5CE1B6", beidou: "#FF8FB1", iridium: "#9DB4FF", oneweb: "#FFA270", goes: "#FF7AE0", debris: "#8A94A8", ss: "#F0E6D2", sw: "#7FD4FF" };
  SKY = { on: false, loaded: false, loading: null, recs: [], groups: [], show: {}, reveal: {}, timer: null, layerT: 0, sel: null, SW: null, ss: null, cad: null, spinPaused: false, spinRaf: 0, spinT: 0, bound: false, learn: {}, alt3d: false, mvp: null, path3: [], vis: [] };
  var mob = innerWidth < 768;
  function loadScript(u, i) { return new Promise(function (ok, no) { if (window.satellite) return ok(); var s = document.createElement("script"); s.src = u; s.integrity = i; s.crossOrigin = "anonymous"; s.onload = ok; s.onerror = function () { no(new Error("satellite.js did not load")); }; document.head.appendChild(s); }); }
  function skyLoad() {
    if (SKY.loading) return SKY.loading;
    var sj = window.BN_SATJS || [];
    SKY.loading = Promise.all([loadScript(sj[0], sj[1]), getJSON("/api/netmap/sky" + (mob ? "?lite=1" : "")), getJSON("/api/netmap/space").catch(function () { return null; }), getJSON("/api/netmap/learn.json").catch(function () { return {}; })]).then(function (r) {
      var D2 = r[1], sat = window.satellite; SKY.SW = r[2]; SKY.learn = r[3] || {}; SKY.groups = D2.groups || [];
      SKY.groups.forEach(function (g) { SKY.show[g.id] = g.id !== "debris"; });
      SKY.show.ss = false; SKY.show.sw = false;
      document.querySelectorAll("#nx_sf button[data-g]").forEach(function (b) {
        var g = b.dataset.g; if (SKY.show[g] !== undefined) b.setAttribute("aria-pressed", SKY.show[g] ? "true" : "false");
      });
      skyChipLabels();
      (D2.sats || []).forEach(function (s) {
        try {
          var g = SKY.groups[s[0]].id;
          SKY.recs.push({ g: g, gi: s[0], no: s[1], name: s[10] || (SKY.groups[s[0]].name + " " + s[1]), mm: s[3], inc: s[5], ep: s[2],
            r: sat.json2satrec({ OBJECT_NAME: s[10] || "SAT", OBJECT_ID: "", EPOCH: new Date(s[2] * 1000).toISOString().replace("Z", ""), MEAN_MOTION: s[3], ECCENTRICITY: s[4], INCLINATION: s[5],
              RA_OF_ASC_NODE: s[6], ARG_OF_PERICENTER: s[7], MEAN_ANOMALY: s[8], EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: s[1], ELEMENT_SET_NO: 999, REV_AT_EPOCH: 0, BSTAR: s[9], MEAN_MOTION_DOT: 0, MEAN_MOTION_DDOT: 0 }), p: null });
        } catch (e) {}
      });
      SKY.loaded = true;
    });
    return SKY.loading;
  }
  function skyLayers() {
    if (map.getSource("sats")) return;
    map.addSource("sats", { type: "geojson", data: EMPTY });
    map.addSource("trk", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "trk", type: "line", source: "trk", layout: { "line-cap": "round" }, paint: { "line-color": ["get", "c"], "line-width": 1.6, "line-opacity": 0.75, "line-dasharray": [2, 2] } });
    map.addLayer({ id: "sat-glow", type: "circle", source: "sats", filter: ["!=", ["get", "g"], "starlink"], paint: { "circle-color": ["get", "c"], "circle-blur": 1, "circle-opacity": 0.35, "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 6, 5, 14] } });
    map.addLayer({ id: "sat", type: "circle", source: "sats", paint: { "circle-color": ["get", "c"], "circle-opacity": ["case", ["==", ["get", "g"], "starlink"], 0.75, ["==", ["get", "g"], "debris"], 0.7, 1],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, ["case", ["==", ["get", "g"], "iss"], 4.2, ["==", ["get", "g"], "starlink"], 1, ["==", ["get", "g"], "oneweb"], 1.4, ["==", ["get", "g"], "debris"], 1.2, 2.6], 5, ["case", ["==", ["get", "g"], "iss"], 7.5, ["==", ["get", "g"], "starlink"], 2.2, ["==", ["get", "g"], "oneweb"], 2.6, ["==", ["get", "g"], "debris"], 2.2, 4.6]],
      "circle-stroke-color": "rgba(5,6,10,.6)", "circle-stroke-width": ["case", ["==", ["get", "g"], "starlink"], 0, 0.8] } });
    map.addLayer({ id: "sat-sel", type: "circle", source: "trk", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#F0F0FA", "circle-stroke-width": 1.6, "circle-radius": 9 } });
    map.on("mousemove", "sat", function (e) { if (!SKY.on) return; map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "sat", function () { map.getCanvas().style.cursor = ""; });
  }
  var EARTH_R = 6371008.8, GEO_ALT = 35786000, SKY3 = null;   /* MapLibre globe unit sphere; Op = 6371008.8 m */
  function hexRgb(h) {
    h = String(h || "#C9CCD6").replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    return [parseInt(h.slice(0, 2), 16) / 255, parseInt(h.slice(2, 4), 16) / 255, parseInt(h.slice(4, 6), 16) / 255];
  }
  function globePos(lon, lat, altM) {
    var r = 1 + (altM || 0) / EARTH_R, la = lat * Math.PI / 180, lo = lon * Math.PI / 180, cl = Math.cos(la);
    return [r * cl * Math.sin(lo), r * Math.sin(la), r * cl * Math.cos(lo)];
  }
  function mulMVP(m, x, y, z) {
    var w = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (Math.abs(w) < 1e-8) return null;
    return [(m[0] * x + m[4] * y + m[8] * z + m[12]) / w, (m[1] * x + m[5] * y + m[9] * z + m[13]) / w, (m[2] * x + m[6] * y + m[10] * z + m[14]) / w];
  }
  function camFrame() {
    var c = map.getCenter(), dir = globePos(c.lng, c.lat, 0);
    return { dir: dir, dist: Math.max(3.2, Math.pow(2, 1.8 - map.getZoom())) };
  }
  function skyVisible(pos, camDir, camDist) {
    var cx = camDir[0] * camDist, cy = camDir[1] * camDist, cz = camDir[2] * camDist;
    var dx = pos[0] - cx, dy = pos[1] - cy, dz = pos[2] - cz;
    var a = dx * dx + dy * dy + dz * dz, b = 2 * (cx * dx + cy * dy + cz * dz), c0 = cx * cx + cy * cy + cz * cz - 1, disc = b * b - 4 * a * c0;
    if (disc <= 0) return true;
    var t = (-b - Math.sqrt(disc)) / (2 * a);
    return !(t > 0.002 && t < 0.998);
  }
  function skyPick(pt) {
    var m = SKY.mvp, vis = SKY.vis; if (!m || !vis || !vis.length) return null;
    var hit = null, best = 20, cnv = map.getCanvas(), w = cnv.clientWidth, h = cnv.clientHeight, cam = camFrame();
    for (var i = 0; i < vis.length; i++) {
      var v = vis[i];
      if (!skyVisible([v.x, v.y, v.z], cam.dir, cam.dist)) continue;
      var ndc = mulMVP(m, v.x, v.y, v.z);
      if (!ndc || ndc[2] < -1 || ndc[2] > 1) continue;
      var d = Math.hypot((ndc[0] + 1) * 0.5 * w - pt.x, (1 - ndc[1]) * 0.5 * h - pt.y);
      if (d < Math.max(16, (v.sz || 6) * 0.8) && d < best) { best = d; hit = v.i; }
    }
    return hit;
  }
  function yearsInOrbit(iso) {
    if (!iso) return "";
    var t = Date.parse(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    if (!isFinite(t)) return "";
    var y = (Date.now() - t) / (365.25 * 864e5);
    if (y < 1) return Math.max(1, Math.round(y * 12)) + " months in orbit";
    return (y < 10 ? y.toFixed(1) : String(Math.round(y))) + " years in orbit";
  }
  function uText(s) {
    var U = window.BNUnits; if (!U || s == null) return s || "";
    return String(s).replace(/([0-9][0-9,]*(?:\.[0-9]+)?)\s*km\/s\b/g, function (_, n) { return U.fmtSpeed(parseFloat(n.replace(/,/g, "")), "s"); })
      .replace(/([0-9][0-9,]*(?:\.[0-9]+)?)\s*km\/h\b/g, function (_, n) { return U.fmtSpeed(parseFloat(n.replace(/,/g, "")), "h"); })
      .replace(/([0-9][0-9,]*(?:\.[0-9]+)?)\s*km\b/g, function (_, n) { return U.fmtDist(parseFloat(n.replace(/,/g, ""))); });
  }
  function learnHtml(gId) {
    var L = (SKY.learn || {})[gId]; if (!L) return "";
    var yrs = yearsInOrbit(L.first), h = '<div class="nx-learn">';
    if (L.image) {
      h += '<figure class="nx-learn-fig"><img src="' + esc(L.image) + '" alt="' + esc(L.alt || L.name || "") + '" width="900" loading="lazy"><figcaption>' + esc(L.credit || "");
      if (L.license_url) h += " " + linkA(L.license_url, L.license || "License");
      h += "</figcaption></figure>";
    }
    h += '<dl class="nx-learn-dl">';
    if (L.operator) h += "<dt>Operator</dt><dd>" + esc(L.operator) + "</dd>";
    if (L.first_label) h += "<dt>First in orbit</dt><dd>" + esc(L.first_label) + (yrs ? " · " + esc(yrs) : "") + "</dd>";
    else if (yrs) h += "<dt>Years in orbit</dt><dd>" + esc(yrs) + "</dd>";
    if (L.purpose) h += "<dt>Purpose</dt><dd>" + esc(uText(L.purpose)) + "</dd>";
    if (L.depends) h += "<dt>Who depends on it</dt><dd>" + esc(uText(L.depends)) + "</dd>";
    if (L.failure) h += "<dt>If it failed</dt><dd>" + esc(uText(L.failure)) + "</dd>";
    h += "</dl>";
    if (L.sources && L.sources.length) h += '<p class="nx-learn-src">Sources: ' + L.sources.map(function (s) { return linkA(s.url, s.name); }).join(" · ") + "</p>";
    return h + "</div>";
  }
  function shd(gl, type, src) {
    var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { console.warn("sky3d shader", gl.getShaderInfoLog(s)); gl.deleteShader(s); return null; }
    return s;
  }
  function glProg(gl, vsSrc, fsSrc, attribs) {   /* not prog(): that name is the loader's progress function (a second declaration replaced it and broke map setup) */
    var vs = shd(gl, gl.VERTEX_SHADER, vsSrc), fs = shd(gl, gl.FRAGMENT_SHADER, fsSrc); if (!vs || !fs) return null;
    var p = gl.createProgram(); gl.attachShader(p, vs); gl.attachShader(p, fs);
    (attribs || []).forEach(function (n, i) { gl.bindAttribLocation(p, i, n); });
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { console.warn("sky3d program", gl.getProgramInfoLog(p)); return null; }
    return p;
  }
  function geoRing() {
    var pts = [], n = 128, r = 1 + GEO_ALT / EARTH_R;
    for (var i = 0; i <= n; i++) { var a = (i / n) * Math.PI * 2; pts.push(r * Math.sin(a), 0, r * Math.cos(a)); }
    return new Float32Array(pts);
  }
  function sky2dVis() {
    var v = (SKY.on && !SKY.alt3d) ? "visible" : "none";
    ["sat", "sat-glow", "trk", "sat-sel"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", v); });
  }
  function sky3dOnAdd(layer, mapObj, gl) {
    var gl2 = typeof WebGL2RenderingContext !== "undefined" && gl instanceof WebGL2RenderingContext;
    var pVS = gl2
      ? ["#version 300 es", "uniform mat4 u_matrix;", "in vec3 a_pos;", "in vec3 a_col;", "in float a_size;", "out vec3 v_col;",
        "void main(){ gl_Position = u_matrix * vec4(a_pos,1.0); gl_PointSize = max(1.0, a_size); v_col = a_col; }"].join("\n")
      : ["uniform mat4 u_matrix;", "attribute vec3 a_pos;", "attribute vec3 a_col;", "attribute float a_size;", "varying vec3 v_col;",
        "void main(){ gl_Position = u_matrix * vec4(a_pos,1.0); gl_PointSize = max(1.0, a_size); v_col = a_col; }"].join("\n");
    var pFS = gl2
      ? ["#version 300 es", "precision mediump float;", "in vec3 v_col;", "out vec4 outColor;",
        "void main(){ vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p); if (r > 1.0) discard; float a = smoothstep(1.0, 0.4, r); outColor = vec4(v_col * a, a); }"].join("\n")
      : ["precision mediump float;", "varying vec3 v_col;",
        "void main(){ vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p); if (r > 1.0) discard; float a = smoothstep(1.0, 0.4, r); gl_FragColor = vec4(v_col * a, a); }"].join("\n");
    var lVS = gl2
      ? ["#version 300 es", "uniform mat4 u_matrix;", "in vec3 a_pos;", "void main(){ gl_Position = u_matrix * vec4(a_pos,1.0); }"].join("\n")
      : ["uniform mat4 u_matrix;", "attribute vec3 a_pos;", "void main(){ gl_Position = u_matrix * vec4(a_pos,1.0); }"].join("\n");
    var lFS = gl2
      ? ["#version 300 es", "precision mediump float;", "uniform vec4 u_color;", "out vec4 outColor;", "void main(){ outColor = u_color; }"].join("\n")
      : ["precision mediump float;", "uniform vec4 u_color;", "void main(){ gl_FragColor = u_color; }"].join("\n");
    layer.ptProg = glProg(gl, pVS, pFS, ["a_pos", "a_col", "a_size"]);
    layer.lnProg = glProg(gl, lVS, lFS, ["a_pos"]);
    if (!layer.ptProg || !layer.lnProg) { SKY.alt3d = false; return; }
    layer.uMatP = gl.getUniformLocation(layer.ptProg, "u_matrix");
    layer.uMatL = gl.getUniformLocation(layer.lnProg, "u_matrix");
    layer.uCol = gl.getUniformLocation(layer.lnProg, "u_color");
    layer.ptBuf = gl.createBuffer(); layer.lnBuf = gl.createBuffer(); layer.ringBuf = gl.createBuffer();
    layer.ring = geoRing();
    gl.bindBuffer(gl.ARRAY_BUFFER, layer.ringBuf); gl.bufferData(gl.ARRAY_BUFFER, layer.ring, gl.STATIC_DRAW);
    layer.vao = gl.createVertexArray ? gl.createVertexArray() : null;
    SKY3 = layer; SKY.alt3d = true; sky2dVis();
    if (!SKY._pickMove) {
      SKY._pickMove = true;
      map.on("mousemove", function (e) {
        if (!SKY.on || !SKY.alt3d) return;
        map.getCanvas().style.cursor = skyPick(e.point) != null ? "pointer" : "";
      });
    }
  }
  function sky3dOnRemove(layer, gl) {
    ["ptBuf", "lnBuf", "ringBuf"].forEach(function (k) { if (layer[k]) gl.deleteBuffer(layer[k]); });
    if (layer.vao && gl.deleteVertexArray) gl.deleteVertexArray(layer.vao);
    SKY3 = null; SKY.alt3d = false;
  }
  function sky3dRender(layer, gl, args) {
    if (!SKY.on || !SKY.alt3d || !layer.ptProg) return;
    var mat = args && args.defaultProjectionData && args.defaultProjectionData.mainMatrix;
    if (!mat) return;
    SKY.mvp = mat;
    var m = mat instanceof Float32Array ? mat : new Float32Array(mat);
    try {
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(false);
      if (layer.vao) gl.bindVertexArray(layer.vao);
      gl.useProgram(layer.lnProg); gl.uniformMatrix4fv(layer.uMatL, false, m);
      gl.enableVertexAttribArray(0);   /* pt1834u: the always-on GEO ring (35,786 km circle) is no longer drawn; only paths of a selected object */
      var path = SKY._path, pn = SKY._pathN || 0;
      if (pn > 1) {
        gl.bindBuffer(gl.ARRAY_BUFFER, layer.lnBuf);
        if (SKY._pathDirty) { gl.bufferData(gl.ARRAY_BUFFER, path, gl.DYNAMIC_DRAW); SKY._pathDirty = false; }
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
        var col = hexRgb(SKY.sel != null && SKY.recs[SKY.sel] ? SKYC[SKY.recs[SKY.sel].g] : "#C9CCD6");
        gl.uniform4f(layer.uCol, col[0], col[1], col[2], 0.85);
        gl.drawArrays(gl.LINE_STRIP, 0, pn);
      }
      var n = SKY._ptN || 0;
      if (n) {
        gl.useProgram(layer.ptProg); gl.uniformMatrix4fv(layer.uMatP, false, m);
        gl.bindBuffer(gl.ARRAY_BUFFER, layer.ptBuf);
        if (SKY._ptsDirty) { gl.bufferData(gl.ARRAY_BUFFER, SKY._pts.subarray(0, n * 7), gl.DYNAMIC_DRAW); SKY._ptsDirty = false; }
        gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 28, 0);
        gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 28, 12);
        gl.enableVertexAttribArray(2); gl.vertexAttribPointer(2, 1, gl.FLOAT, false, 28, 24);
        gl.drawArrays(gl.POINTS, 0, n);
        gl.disableVertexAttribArray(1); gl.disableVertexAttribArray(2);
      }
      gl.disableVertexAttribArray(0);
      if (layer.vao) gl.bindVertexArray(null);
      gl.depthMask(true);
      gl.bindBuffer(gl.ARRAY_BUFFER, null);
    } catch (err) { console.warn("sky3d render", err); }
  }
  function sky3dRetry(ms) {
    if (SKY._3dWait) return;
    SKY._3dWait = setTimeout(function () {
      SKY._3dWait = 0;
      if (SKY.on && !SKY3 && !SKY._3dFail) sky3dEnsure();
    }, ms || 200);
  }
  function sky3dEnsure() {
    if (!map || SKY3 || SKY._3dFail) return;
    /* do not wait only on map "idle": startPulse() can keep idle from firing, which left the 3D layer uninstalled */
    if (!map.isStyleLoaded || !map.isStyleLoaded()) { sky3dRetry(200); return; }
    try {
      if (map.getLayer("sats3d")) { sky2dVis(); return; }
      map.addLayer({ id: "sats3d", type: "custom", renderingMode: "3d",
        onAdd: function (m, gl) { sky3dOnAdd(this, m, gl); },
        onRemove: function (m, gl) { sky3dOnRemove(this, gl); },
        render: function (gl, args) { sky3dRender(this, gl, args); } });
      if (!SKY.alt3d) {
        SKY._3dTries = (SKY._3dTries || 0) + 1;
        if (SKY._3dTries >= 6) SKY._3dFail = true;
        else sky3dRetry(250);
      }
      sky2dVis();
    } catch (e) {
      console.warn("sky3d", e);
      SKY.alt3d = false;
      SKY._3dTries = (SKY._3dTries || 0) + 1;
      if (SKY._3dTries >= 8) { SKY._3dFail = true; sky2dVis(); }
      else sky3dRetry(250);
    }
  }
  function sky3dUpdate() {
    if (!SKY.alt3d) return;
    var recs = SKY.recs, dpr = Math.min(2, window.devicePixelRatio || 1);
    var n = 0, vis = [], cap = Math.max(recs.length, 8), focus = SKY.sel != null && document.body.classList.contains("nx-sky-focus");
    if (!SKY._pts || SKY._pts.length < cap * 7) SKY._pts = new Float32Array(cap * 7);
    var buf = SKY._pts;
    for (var i = 0; i < recs.length; i++) {
      var o = recs[i]; if (!o.p || !SKY.show[o.g] || !SKY.reveal[o.g]) continue;
      if (focus && i !== SKY.sel) continue;
      var g = globePos(o.p[0], o.p[1], o.p[2] * 1000);
      var c = hexRgb(SKYC[o.g]);
      var sz = (o.g === "iss" ? 12 : o.g === "starlink" ? 3.4 : o.g === "oneweb" ? 4.6 : o.g === "goes" ? 8.5 : o.g === "debris" ? 2.8 : 6.8) * dpr;
      if (SKY.sel === i) sz *= 1.85;
      var o7 = n * 7;
      buf[o7] = g[0]; buf[o7 + 1] = g[1]; buf[o7 + 2] = g[2];
      buf[o7 + 3] = c[0]; buf[o7 + 4] = c[1]; buf[o7 + 5] = c[2];
      buf[o7 + 6] = Math.min(24, sz);
      vis.push({ i: i, x: g[0], y: g[1], z: g[2], sz: sz / dpr }); n++;
    }
    SKY._ptN = n; SKY.vis = vis; SKY._ptsDirty = true;
    var path = SKY.path3 || [];
    SKY._path = path instanceof Float32Array ? path : new Float32Array(path);
    SKY._pathN = SKY._path.length / 3; SKY._pathDirty = true;
    if (map) map.triggerRepaint();
  }
  function prop() {
    if (!SKY.on || !SKY.loaded) return;
    if (!SKY.alt3d && !SKY._3dFail) sky3dEnsure();
    var sat = window.satellite, d = new Date(), gm = sat.gstime(d), f = [], n = 0, nDeb = 0;
    var focus = SKY.sel != null && document.body.classList.contains("nx-sky-focus");
    for (var i = 0; i < SKY.recs.length; i++) {
      var o = SKY.recs[i]; if (!SKY.show[o.g] || !SKY.reveal[o.g]) continue;
      if (focus && i !== SKY.sel) continue;
      try {
        var pv = sat.propagate(o.r, d); if (!pv || !pv.position) continue;
        var gd = sat.eciToGeodetic(pv.position, gm), lon = sat.degreesLong(gd.longitude), lat = sat.degreesLat(gd.latitude);
        o.p = [lon, lat, gd.height, pv.velocity ? Math.hypot(pv.velocity.x, pv.velocity.y, pv.velocity.z) : null];
        f.push({ type: "Feature", id: i, geometry: { type: "Point", coordinates: [lon, lat] }, properties: { i: i, g: o.g, c: SKYC[o.g] || "#C9CCD6" } });
        if (o.g === "debris") nDeb++; else n++;
      } catch (e) {}
    }
    if (SKY.alt3d) sky3dUpdate();
    else if (map.getSource("sats")) map.getSource("sats").setData({ type: "FeatureCollection", features: f });
    if (SKY.sel != null) track(SKY.sel, false);
    $("nx_chip").className = "nx-chip";
    if (!n && !nDeb) $("nx_sum").textContent = "Tap a chip to show a layer";
    else $("nx_sum").textContent = "Tracking " + num(n) + " satellites live" + (nDeb ? " · " + num(nDeb) + " debris" : "");
    skyLabs();
  }
  function track(i, fly) {
    var o = SKY.recs[i], sat = window.satellite; if (!o) return;
    var per = 1440 / o.mm, pts = [], seg = [], path3 = [], now = Date.now(), last = null;
    for (var k = -120; k <= 120; k++) {   /* two full orbits (was one, a short-looking arc on the globe) */
      var t = new Date(now + k * per / 120 * 60000);
      try { var pv = sat.propagate(o.r, t); if (!pv || !pv.position) continue; var gd = sat.eciToGeodetic(pv.position, sat.gstime(t)); var lon = sat.degreesLong(gd.longitude), lat = sat.degreesLat(gd.latitude);
        var gp = globePos(lon, lat, gd.height * 1000); path3.push(gp[0], gp[1], gp[2]);
        if (last != null && Math.abs(lon - last) > 180) { if (seg.length > 1) pts.push(seg); seg = []; } seg.push([lon, lat]); last = lon; } catch (e) {}
    }
    if (seg.length > 1) pts.push(seg);
    SKY.path3 = path3;
    if (SKY.alt3d) sky3dUpdate();
    else if (map.getSource("trk")) {
      var fs = pts.map(function (sg) { return { type: "Feature", geometry: { type: "LineString", coordinates: sg }, properties: { c: SKYC[o.g] } }; });
      if (o.p) fs.push({ type: "Feature", geometry: { type: "Point", coordinates: [o.p[0], o.p[1]] }, properties: {} });
      map.getSource("trk").setData({ type: "FeatureCollection", features: fs });
    }
    if (fly && o.p) map.easeTo({ center: [o.p[0], o.p[1]], duration: reduce ? 0 : 900 });
  }
  function orbitClass(o) { var h = o.p ? o.p[2] : null; return h == null ? "" : h < 2000 ? "Low Earth orbit" : h < 30000 ? "Medium Earth orbit" : "Geosynchronous orbit"; }
  function satFacts(o, g, age) {
    return '<dl><dt>Altitude</dt><dd>' + (o.p ? window.BNUnits.fmtAlt(o.p[2]) : '–') + '</dd><dt>Speed</dt><dd>' + (o.p && o.p[3] ? window.BNUnits.fmtSpeed(o.p[3], "s") : '–') + '</dd><dt>One orbit</dt><dd>' + (1440 / o.mm).toFixed(0) + ' min</dd>' +
      '<dt>Inclination</dt><dd>' + o.inc.toFixed(1) + '°</dd><dt>Over</dt><dd>' + (o.p ? Math.abs(o.p[1]).toFixed(1) + '°' + (o.p[1] >= 0 ? 'N' : 'S') + ' ' + Math.abs(o.p[0]).toFixed(1) + '°' + (o.p[0] >= 0 ? 'E' : 'W') : '–') + '</dd><dt>NORAD ID</dt><dd>' + esc(o.no) + '</dd></dl>' +
      '<p class="age">' + esc(g.what || "") + '. Position computed live from CelesTrak elements ' + (age < 48 ? Math.round(age) + ' h' : Math.round(age / 24) + ' days') + ' old. The dashed line is two orbits.</p>' +
      '<div class="acts">' + linkA("https://celestrak.org/satcat/table-satcat.php?CATNR=" + o.no, "CelesTrak record") + '</div>';
  }
  function clearSat() {
    hideCard(true); SKY.sel = null; document.body.classList.remove("nx-sky-focus");
    card.classList.remove("nx-sat-chip", "open", "nx-learn-panel");
    SKY.path3 = []; if (SKY.alt3d) sky3dUpdate();
    if (map && map.getSource("trk")) map.getSource("trk").setData(EMPTY);
    if (SKY.on && SKY.loaded) prop();
    skySpinResume(1800);
  }
  function launchLayerIn() {
    if (typeof window.__nxLaunchLayerIn === "function") window.__nxLaunchLayerIn();
    else window.__nxLaunchLayerInQueued = true;
  }
  function layerIn() {
    if (SKY.layerT) { clearTimeout(SKY.layerT); SKY.layerT = 0; }
    SKY.reveal = {};
    var gs = (SKY.groups || []).filter(function (g) { return g.id !== "debris" && SKY.show[g.id]; }).slice().sort(function (a, b) {
      if (a.id === "starlink") return 1; if (b.id === "starlink") return -1;
      return (a.total || 0) - (b.total || 0) || String(a.name || "").localeCompare(String(b.name || ""));
    });
    if (reduce || !gs.length) { gs.forEach(function (g) { SKY.reveal[g.id] = true; }); prop(); launchLayerIn(); return; }
    var i = 0, gap = Math.max(280, Math.min(600, 3200 / Math.max(gs.length + 1, 1)));
    (function next() {
      if (!SKY.on) return;
      if (i < gs.length) {
        if (SKY.show[gs[i].id]) SKY.reveal[gs[i].id] = true;
        i += 1; prop();
        SKY.layerT = setTimeout(i < gs.length ? next : launchLayerIn, gap);
      }
    })();
  }
  function skySpinStop() { if (SKY.spinRaf) { cancelAnimationFrame(SKY.spinRaf); SKY.spinRaf = 0; } if (SKY.spinT) { clearTimeout(SKY.spinT); SKY.spinT = 0; } }
  function skySpinPause() { SKY.spinPaused = true; if (SKY.spinT) { clearTimeout(SKY.spinT); SKY.spinT = 0; } }
  function skySpinResume(ms) {
    if (SKY.spinT) clearTimeout(SKY.spinT);
    SKY.spinT = setTimeout(function () { SKY.spinT = 0; if (SKY.on && SKY.sel == null) SKY.spinPaused = false; }, ms || 2200);
  }
  function skySpinStart() {
    if (reduce || SKY.spinRaf) return;
    SKY.spinPaused = false;
    var last = performance.now();
    (function tick(now) {
      SKY.spinRaf = requestAnimationFrame(tick);
      var dt = Math.min(64, now - last); last = now;
      if (!SKY.on || SKY.spinPaused || SKY.sel != null || window.__nxSpinHold || document.hidden) return;   /* launches.js holds the spin while a launch is open */
      var c = map.getCenter(); map.setCenter([c.lng + 1.5 * dt / 1000, c.lat]);   /* ~4 minutes per revolution */
    })(last);
  }
  function skySpinBind() {
    if (SKY.bound || !map) return; SKY.bound = true;
    map.on("dragstart", skySpinPause); map.on("zoomstart", skySpinPause);
    map.on("rotatestart", skySpinPause); map.on("pitchstart", skySpinPause);
    map.on("dragend", function () { skySpinResume(2200); });
    map.on("zoomend", function () { skySpinResume(2200); });
    map.on("rotateend", function () { skySpinResume(2200); });
    map.on("pitchend", function () { skySpinResume(2200); });
    var cv = map.getCanvas();
    cv.addEventListener("wheel", skySpinPause, { passive: true });
    cv.addEventListener("touchstart", skySpinPause, { passive: true });
    cv.addEventListener("touchend", function () { skySpinResume(2200); }, { passive: true });
  }
  function satCard(i, pt) {
    var o = SKY.recs[i]; if (!o) return; SKY.sel = i; skySpinPause(); track(i, false);
    var g = SKY.groups[o.gi] || {}, c = SKYC[o.g], compact = innerWidth < 768;
    var age = (Date.now() / 1000 - o.ep) / 3600, alt = o.p ? window.BNUnits.fmtAlt(o.p[2]) : "–";
    var facts = satFacts(o, g, age), learn = learnHtml(o.g);
    var cx = '<button type="button" class="nx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
    card.classList.remove("dragged", "open", "nx-sat-chip", "nx-learn-panel");
    card.style.left = card.style.top = card.style.right = card.style.bottom = card.style.width = "";
    document.body.classList.add("nx-sky-focus");
    if (compact) {
      prop();
      card.classList.add("nx-sat-chip");
      card.innerHTML = '<button type="button" class="nx-sat-more" aria-expanded="false" aria-label="Show satellite details"><span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(g.name) + '</span><h3>' + esc(o.name) + '</h3><p class="nx-sat-alt">' + alt + '</p></button><div class="nx-sat-extra" hidden>' + facts + learn + '</div>' + cx;
    } else {
      card.classList.add("nx-learn-panel");
      card.innerHTML = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(g.name) + ' · ' + esc(orbitClass(o)) + '</span><h3>' + esc(o.name) + '</h3>' + facts + learn + cx;
    }
    card.hidden = false; requestAnimationFrame(function () { card.classList.add("in"); }); pinned = true; card.classList.add("pin");
    var moreBtn = card.querySelector(".nx-sat-more");
    if (moreBtn) moreBtn.onclick = function () {
      var open = card.classList.toggle("open"); this.setAttribute("aria-expanded", open ? "true" : "false");
      var ex = card.querySelector(".nx-sat-extra"); if (ex) ex.hidden = !open;
    };
    card.querySelector(".nx-cx").onclick = function () { clearSat(); };
  }
  function addSkyRecs(group, sats, gi) {
    var sat = window.satellite; if (!sat) return 0;
    var n = 0;
    (sats || []).forEach(function (s) {
      try {
        SKY.recs.push({ g: group, gi: gi, no: s[1], name: s[10] || (group + " " + s[1]), mm: s[3], inc: s[5], ep: s[2],
          r: sat.json2satrec({ OBJECT_NAME: s[10] || "SAT", OBJECT_ID: "", EPOCH: new Date(s[2] * 1000).toISOString().replace("Z", ""), MEAN_MOTION: s[3], ECCENTRICITY: s[4], INCLINATION: s[5],
            RA_OF_ASC_NODE: s[6], ARG_OF_PERICENTER: s[7], MEAN_ANOMALY: s[8], EPHEMERIS_TYPE: 0, CLASSIFICATION_TYPE: "U", NORAD_CAT_ID: s[1], ELEMENT_SET_NO: 999, REV_AT_EPOCH: 0, BSTAR: s[9], MEAN_MOTION_DOT: 0, MEAN_MOTION_DDOT: 0 }), p: null });
        n++;
      } catch (e) {}
    });
    return n;
  }
  function debrisLoad() {
    if (SKY.debrisLoading) return SKY.debrisLoading;
    SKY.debrisLoading = getJSON("/api/netmap/debris" + (mob ? "?lite=1" : "")).then(function (D2) {
      if (SKY.debrisLoaded) return;
      var gi = SKY.groups.length;
      SKY.groups.push({ id: "debris", name: "Debris", what: "Tracked space debris from CelesTrak debris groups", total: (D2 && D2.total) || 0, shown: (D2 && D2.shown) || ((D2 && D2.sats) || []).length, source_url: D2 && D2.source_url });
      addSkyRecs("debris", (D2 && D2.sats) || [], gi);
      SKY.debrisLoaded = true;
      SKY.reveal.debris = !!SKY.show.debris; skyChipLabels();
      if (SKY.on) prop();
    }).catch(function () { SKY.debrisLoading = null; });
    return SKY.debrisLoading;
  }
  function fmtAU(x) {
    if (!x || x.au == null) return "–";
    var au = x.au, km = x.km, auS = au >= 10 ? au.toFixed(1) : au.toFixed(3);
    return (km != null ? window.BNUnits.fmtDist(km) : "") + " (" + auS + " AU)";
  }
  function fmtLight(min) {
    if (min == null || !isFinite(min)) return "";
    if (min >= 60) { var h = Math.floor(min / 60), m = Math.round(min - h * 60); return h + " h " + m + " min light-time from Earth"; }
    return (min < 10 ? min.toFixed(2) : min.toFixed(1)) + " min light-time from Earth";
  }
  function fmtCadDate(cd) {
    if (!cd) return "";
    var m = String(cd).match(/^(\d{4})-([A-Za-z]{3})-(\d{2})(?:\s+(\d{2}:\d{2}))?/);
    if (!m) return String(cd);
    return Number(m[3]) + " " + m[2] + " " + m[1] + (m[4] ? ", " + m[4] + " UTC" : "");
  }
  function fmtSize(o) {
    var km = o.diameter_km != null ? o.diameter_km : o.size_est_km, est = o.diameter_km == null && o.size_est_km != null;
    if (km == null) return o.h != null ? "H " + o.h : "size not published";
    var s = window.BNUnits.fmtSizeKm(km);
    return (est ? "about " : "") + s + (est ? " (from H, albedo 0.14)" : "");
  }
  function ssDiagram(objs) {
    var W = 220, H = 132, cx = 70, cy = 66, rMin = 16, rMax = 58;
    function rOf(au) { var x = Math.log10(Math.max(au || 0.05, 0.05)); return rMin + (rMax - rMin) * (x - Math.log10(0.05)) / (Math.log10(200) - Math.log10(0.05)); }
    var h = '<svg class="nx-ss-svg" viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" aria-hidden="true">';
    h += '<circle cx="' + cx + '" cy="' + cy + '" r="6" fill="#F0E6D2"/><text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" fill="rgba(240,240,250,.55)" font-size="8">Sun</text>';
    var earthR = rOf(1);
    h += '<circle cx="' + cx + '" cy="' + cy + '" r="' + earthR + '" fill="none" stroke="rgba(240,240,250,.2)" stroke-width="1"/>';
    h += '<circle cx="' + (cx + earthR) + '" cy="' + cy + '" r="3" fill="#6EA8FF"/><text x="' + (cx + earthR + 6) + '" y="' + (cy + 3) + '" fill="rgba(240,240,250,.7)" font-size="8">Earth</text>';
    var col = { roadster: "#E8ECF5", voyager1: "#9DB4FF", voyager2: "#5CE1B6" };
    var ang = { roadster: -0.55, voyager2: 0.7, voyager1: 2.15 };
    (objs || []).forEach(function (o) {
      if (!o.ok || !o.sun) return;
      var r = rOf(o.sun.au), a = ang[o.id] != null ? ang[o.id] : 1, x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
      h += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (o.id.indexOf("voyager") === 0 ? 3.2 : 2.6) + '" fill="' + (col[o.id] || "#C9CCD6") + '"/>';
      h += '<text x="' + (x + 5).toFixed(1) + '" y="' + (y - 5).toFixed(1) + '" fill="rgba(240,240,250,.8)" font-size="8">' + esc(o.id === "roadster" ? "Roadster" : o.name) + "</text>";
    });
    h += "</svg><p class=\"nx-ss-note\">Log scale from the Sun (not a sky chart).</p>";
    return h;
  }
  function skyChipLabels() {
    var names = { iss: "ISS", starlink: "Starlink", gps: "GPS", glonass: "GLONASS", galileo: "Galileo", beidou: "BeiDou", iridium: "Iridium", oneweb: "OneWeb", goes: "GOES", debris: "Debris", ss: "Solar system", sw: "Space weather" };
    document.querySelectorAll("#nx_sf button").forEach(function (b) {
      var g = b.dataset.g, span = b.querySelector("span") || b, label = names[g] || span.textContent.replace(/\s[\d.]+k?$/, ""), grp = (SKY.groups || []).filter(function (x) { return x.id === g; })[0];
      if (g === "ss" || g === "sw" || !grp) { if (span) span.textContent = label; return; }
      var n = grp.shown || grp.total || 0, s = n >= 1000 ? ((n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k") : String(n);
      span.textContent = label + " " + s;
    });
  }
  function dest90(lon, lat, brng) {
    var φ1 = lat * Math.PI / 180, λ1 = lon * Math.PI / 180, θ = brng * Math.PI / 180, δ = Math.PI / 2;
    var φ2 = Math.asin(Math.sin(φ1) * Math.cos(δ) + Math.cos(φ1) * Math.sin(δ) * Math.cos(θ));
    var λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(δ) * Math.cos(φ1), Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2));
    return [((λ2 * 180 / Math.PI + 540) % 360) - 180, φ2 * 180 / Math.PI];
  }
  function skyLabs() {
    var box = $("nx_sky_labs"); if (!box || !map || !SKY.on) { if (box) { box.hidden = true; box.innerHTML = ""; } return; }
    var showSs = !!SKY.show.ss, showSw = !!SKY.show.sw;
    if (!showSs && !showSw) { box.hidden = true; box.innerHTML = ""; return; }
    box.hidden = false;
    var c = map.getCenter(), p0 = map.project(c), rim = map.project(dest90(c.lng, c.lat, 0));
    var R = Math.max(48, Math.hypot(rim.x - p0.x, rim.y - p0.y));
    var h = "";
    if (showSs && SKY.ss && SKY.ss.ok) {
      (SKY.ss.objects || []).forEach(function (o) {
        var au = o.earth && o.earth.au, label = (o.id === "roadster" ? "Roadster" : o.name) + (au != null ? " · " + (au >= 10 ? au.toFixed(0) : au.toFixed(1)) + " AU" : "");
        var lon = o.earth && o.earth.lon, lat = o.earth && o.earth.lat, x, y;
        if (lon != null && lat != null) {
          var sub = map.project([lon, lat]), dx = sub.x - p0.x, dy = sub.y - p0.y, L = Math.hypot(dx, dy) || 1;
          x = p0.x + dx / L * (R + 10); y = p0.y + dy / L * (R + 10);
        } else { x = p0.x; y = p0.y + R + 14; }
        h += '<span class="nx-ss-pin" data-s3="' + esc(o.id) + '" role="button" tabindex="0" style="pointer-events:auto;cursor:pointer;left:' + x.toFixed(0) + 'px;top:' + y.toFixed(0) + 'px">' + esc(label) + "</span>";
      });
    } else if (showSs) {
      h += '<span class="nx-ss-pin" style="left:' + p0.x.toFixed(0) + 'px;top:' + (p0.y + R + 14).toFixed(0) + 'px">Solar system distances unavailable</span>';
    }
    if (showSw) {
      var w = SKY.SW, txt = "Space weather unavailable";
      if (w && w.ok) txt = "Kp " + (w.kp != null ? Number(w.kp).toFixed(1) : "–") + " · R" + w.scales.R + " S" + w.scales.S + " G" + w.scales.G;
      h += '<span class="nx-sw-pin" data-s3="sw" role="button" tabindex="0" style="pointer-events:auto;cursor:pointer;left:' + p0.x.toFixed(0) + 'px;top:' + (p0.y + R + (showSs ? 36 : 14)).toFixed(0) + 'px">' + esc(txt) + "</span>";
    }
    box.innerHTML = h;
  }
  function ssPanel() {
    var el = $("nx_ss"); if (!el) return;
    var ss = SKY.ss, cad = SKY.cad, h = '<p class="nx-k">Solar system</p>';
    if (ss && ss.ok) {
      h += ssDiagram(ss.objects);
      h += '<ul class="nx-ss-list">';
      (ss.objects || []).forEach(function (o) {
        h += "<li><button type=\"button\" class=\"nx-ss-item\" data-id=\"" + esc(o.id) + "\" aria-expanded=\"false\"><b>" + esc(o.name) + "</b>";
        if (o.ok && o.earth) h += "<span>" + fmtAU(o.earth) + " from Earth</span>";
        else h += "<span>Position unavailable</span>";
        h += "</button><div class=\"nx-ss-more\" hidden>";
        if (o.ok && o.earth) h += "<p>" + fmtAU(o.earth) + " from Earth</p>";
        if (o.ok && o.sun) h += "<p>" + fmtAU(o.sun) + " from the Sun</p>";
        if (o.ok && o.earth && o.earth.light_min != null) h += "<p>" + esc(fmtLight(o.earth.light_min)) + "</p>";
        h += "<p>Launched " + esc(o.launch_label || o.launch || "") + "</p>";
        h += "<p>" + esc(o.status || "") + "</p>";
        if (o.source_url) h += "<p>" + linkA(o.source_url, o.source_name || "Source") + "</p>";
        h += "</div></li>";
      });
      h += "</ul>";
      if (ss.source_url) h += '<p class="nx-swm">Distances ' + linkA(ss.source_url, ss.source || "NASA/JPL Horizons") + ".</p>";
    } else {
      h += '<p class="nx-swm">Solar-system distances are unavailable right now.</p>';
    }
    h += '<p class="nx-k" style="margin-top:10px">Approaches, next 60 days</p>';
    if (cad && cad.ok && cad.objects && cad.objects.length) {
      var rows = cad.objects.slice(0, 5);
      h += '<ul class="nx-cad">';
      rows.forEach(function (o) {
        h += "<li>" + linkA(o.source_url, o.des || o.name) + "<span>" + esc(fmtCadDate(o.cd)) + " · " + window.BNUnits.fmtDist(o.dist_km) + " (" + (o.dist_ld != null ? o.dist_ld.toFixed(2) + " LD" : "") + ") · " + esc(fmtSize(o)) + "</span></li>";
      });
      h += "</ul>";
      if (cad.objects.length > 5) h += '<p class="nx-swm">' + num(cad.objects.length) + " close approaches within 0.05 AU.</p>";
      h += '<p class="nx-swm">Source: ' + linkA(cad.source_url, "JPL SBDB Close-Approach Data") + ".</p>";
    } else if (cad && cad.ok) {
      h += '<p class="nx-swm">No asteroids or comets within 0.05 AU of Earth in the next 60 days. ' + linkA((cad && cad.source_url) || "https://ssd-api.jpl.nasa.gov/doc/cad.html", "JPL SBDB") + ".</p>";
    } else {
      h += '<p class="nx-swm">Close-approach data is unavailable right now.</p>';
    }
    el.innerHTML = h;
    el.querySelectorAll(".nx-ss-item").forEach(function (b) {
      b.addEventListener("click", function () {
        var more = this.nextElementSibling, open = more && more.hidden;
        el.querySelectorAll(".nx-ss-more").forEach(function (m) { m.hidden = true; });
        el.querySelectorAll(".nx-ss-item").forEach(function (x) { x.setAttribute("aria-expanded", "false"); });
        if (more && open) { more.hidden = false; this.setAttribute("aria-expanded", "true"); }
      });
    });
  }
  /* pt1828u: 3D solar system explorer, lazy-loaded (three147.js + solar3d.js, content-hash URLs in window.BN_SOLAR3D) */
  function solarOpen(id) {
    var u = window.BN_SOLAR3D; if (!u) return;
    var go = function () { if (window.BNSolar) window.BNSolar.open(id); };
    if (window.BNSolar) return go();
    if (!SKY.s3p) SKY.s3p = new Promise(function (ok, no) { var i = 0; (function nx() { if (i >= u.length) return ok(); var sc = document.createElement("script"); sc.src = u[i++]; sc.onload = nx; sc.onerror = no; document.head.appendChild(sc); })(); });
    SKY.s3p.then(go, function () { SKY.s3p = null; });
  }
  (function () { var bx = $("nx_sky_labs"); if (bx) bx.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("[data-s3]"); if (t) solarOpen(t.getAttribute("data-s3")); }); })();
  function ssLoad() {
    if (SKY.ssLoading) return SKY.ssLoading;
    SKY.ssLoading = Promise.all([
      getJSON("/api/netmap/ss").catch(function () { return null; }),
      getJSON("/api/netmap/cad").catch(function () { return null; })
    ]).then(function (r) {
      SKY.ss = r[0]; SKY.cad = r[1];
      if (SKY.on) skyLabs();
    });
    return SKY.ssLoading;
  }
  function swPanel() {
    var w = SKY.SW, el = $("nx_sw"); if (!el) return;
    var counts = SKY.groups.map(function (g) { return '<li><i style="background:' + SKYC[g.id] + '"></i>' + esc(g.name) + '<b>' + (mob && g.total >= 1000 ? (g.total / 1000).toFixed(1) + 'k' : num(g.total)) + '</b></li>'; }).join("");
    var h = '<p class="nx-k">Constellations</p><ul class="nx-cnt">' + counts + '</ul>';
    if (w && w.ok) {
      var col = w.gnss === "Degraded" ? COL.out : w.gnss === "Watch" ? COL.deg : COL.ok;
      h += '<p class="nx-k" style="margin-top:12px">Space weather</p><p class="nx-swl"><i style="background:' + col + '"></i>GPS and satellite links: <b>' + esc(w.gnss) + '</b></p>' +
        '<p class="nx-swm">Radio R' + w.scales.R + ' · Radiation S' + w.scales.S + ' · Geomagnetic G' + w.scales.G + (w.kp != null ? ' · Kp ' + Number(w.kp).toFixed(1) : '') + '</p>' +
        '<p class="nx-swm' + (w.gnss === "Normal" ? ' nx-imp' : '') + '">' + esc((w.impacts || [])[0] || "") + '</p><p class="nx-swm">' + linkA(w.source_url, "NOAA SWPC") + ' · ' + linkA(w.jamming.url, "GPS jamming map") + ' · Orbits ' + linkA("https://celestrak.org/", "CelesTrak") + '</p>';
    }
    h += '<p class="nx-swm nx-scale">Drawn to scale from Earth. GPS sits about ' + window.BNUnits.fmtAlt(20200) + ' up; a geostationary satellite about ' + window.BNUnits.fmtAlt(35786) + '. The faint ring is geostationary altitude.</p>';
    el.innerHTML = h;
  }
  function setMode(m) {
    var sky = m === "sky"; if (sky === SKY.on || !map) return;
    SKY.on = sky; document.body.classList.toggle("nx-sky", sky);
    document.querySelectorAll("#nx_mode button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.m === m ? "true" : "false"); });
    $("nx_f").hidden = sky; $("nx_sf").hidden = !sky; $("nx_sw").hidden = true; if ($("nx_ss")) $("nx_ss").hidden = true; if ($("nx_sky_labs")) $("nx_sky_labs").hidden = !sky; $("nx_leg").hidden = sky; if (sky) { var lb = $("nx_leg_body"), lt = $("nx_leg_btn"); if (lb) lb.hidden = true; if (lt) lt.setAttribute("aria-expanded", "false"); } hideCard(true);
    if (sky) { if (MAPR.timer) { clearTimeout(MAPR.timer); MAPR.timer = 0; } MAPR.seq += 1; MAPR.show = {}; }
    if (sky) SEA_L.concat(INF_L).forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", "none"); });
    try { history.replaceState(null, "", sky ? "#sky" : "#map"); } catch (e) {}
    ["cty-fill", "cty-line", "inet-fill", "inet-line", "dc", "dc-glow", "glow", "pulse", "pt", "pt-lbl"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", "none"); });
    if (!sky) {
      clearInterval(SKY.timer); SKY.timer = null; SKY.sel = null;
      if (SKY.layerT) { clearTimeout(SKY.layerT); SKY.layerT = 0; }
      skySpinStop(); document.body.classList.remove("nx-sky-focus"); SKY.reveal = {}; SKY.path3 = [];
      if (card) card.classList.remove("nx-learn-panel", "nx-sat-chip");
      ["sat", "sat-glow", "trk", "sat-sel"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", "none"); });
      try { map.setMinZoom(1); } catch (e) {}
      try { map.setProjection({ type: "mercator" }); } catch (e) {}
      mapLayerIn(); if (D) summary(); map.fitBounds(US, { padding: PAD(), duration: reduce ? 0 : 900 }); return;
    }
    try { map.setProjection({ type: "globe" }); } catch (e) {}
    try { map.setMinZoom(-2); } catch (e) {}
    $("nx_chip").className = "nx-chip";
    map.easeTo({ center: [-95, 20], zoom: mob ? -0.55 : -0.4, duration: reduce ? 0 : 1200 });
    $("nx_sum").textContent = "Loading satellites…";
    skyLayers(); sky3dEnsure(); skySpinBind(); sky2dVis();
    skyLoad().then(function () { if (!SKY.on) return; layerIn(); ssLoad(); skyChipLabels(); skyLabs(); if (!SKY._labMove && map) { SKY._labMove = true; map.on("move", skyLabs); map.on("pitch", skyLabs); map.on("rotate", skyLabs); } clearInterval(SKY.timer); SKY.timer = setInterval(function () { if (!document.hidden) prop(); }, reduce ? 10000 : (mob ? 2000 : 1200));
      setTimeout(function () { if (SKY.on) skySpinStart(); }, reduce ? 0 : 1300); },
      function () { $("nx_sum").textContent = "Orbital data is unavailable right now"; });
  }
  /* pt1758u: three views. Status (the board, default) sits over the map; Map and Sky are the map views */
  function view(v) {
    var board = v === "status";
    if (board && SKY.on) setMode("map");   /* leave the globe first, so its own button state does not win */
    document.body.classList.toggle("nx-board", board);
    document.querySelectorAll("#nx_mode button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.m === v ? "true" : "false"); });
    if (board) { hideCard(true); document.body.classList.remove("nx-more-on"); try { history.replaceState(null, "", "#status"); } catch (e) {} return; }
    if (map) { map.resize(); if (v === "map" && !SKY.on) { try { history.replaceState(null, "", "#map"); } catch (e) {} } setMode(v); }
  }
  document.querySelectorAll("#nx_mode button").forEach(function (b) { b.addEventListener("click", function () { view(b.dataset.m); }); });
  window.__nxSky = SKY; window.__nxSatCard = function (i) { satCard(i); };   /* skytrack.js: chip auto-framing + follow lock (pt1834u) */
  window.__nxView = view;   /* gridlayer.js: "Show on map" from the grid sheet */
  var m0 = document.body.classList.contains("nx-board") ? "status" : location.hash === "#sky" ? "sky" : "map";   /* pt1787u: Map is the default view */
  document.querySelectorAll("#nx_mode button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.m === m0 ? "true" : "false"); });
  document.querySelectorAll("#nx_sf button").forEach(function (b) {
    b.addEventListener("click", function () {
      var g = b.dataset.g; SKY.show[g] = !SKY.show[g];   /* ss/sw are not in SKY.groups: undefined used to flip to false, so the first tap did nothing */ b.setAttribute("aria-pressed", SKY.show[g] ? "true" : "false");
      if (g === "debris") { SKY.reveal.debris = !!SKY.show.debris; if (SKY.show.debris) debrisLoad(); }
      else if (g === "ss") { if (SKY.show.ss) { ssLoad(); solarOpen(); } skyLabs(); return; }
      else if (g === "sw") { if (SKY.show.sw) solarOpen("sw"); skyLabs(); return; }
      else SKY.reveal[g] = !!SKY.show[g];
      prop();
    });
  });

  /* ---------- units toggle (pt1827u): re-render open cards and sky labels, no reload ---------- */
  document.addEventListener("bn-units", function () {
    if (SKY.on) skyLabs();
    if (SKY.on && SKY.sel != null && card && !card.hidden) {
      var wasOpen = card.classList.contains("open");
      satCard(SKY.sel, LASTPT);
      if (wasOpen) {
        card.classList.add("open");
        var moreBtn = card.querySelector(".nx-sat-more"), ex = card.querySelector(".nx-sat-extra");
        if (moreBtn) moreBtn.setAttribute("aria-expanded", "true");
        if (ex) ex.hidden = false;
      }
    } else if (LASTFT && card && !card.hidden) showCard(LASTFT, LASTPT, pinned);
  });

  /* ---------- live refresh every 5 minutes ---------- */
  setInterval(function () { if (document.hidden) return; getJSON("/api/netmap/data").then(function (j) { D = liveOnly(j); applyData(); try { document.dispatchEvent(new CustomEvent("nx:data", { detail: j })); } catch (e) {} }, function () {}); }, 300000);
})();
