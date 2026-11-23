/* Network Status (/network, Nov 23 2026, pt1755u). MapLibre GL + OpenFreeMap, same brighter base style as /weather.
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
  var US = [[-125.5, 23.5], [-66, 50]];
  function PAD() { var m = innerWidth < 768; return m ? { top: 150, bottom: 120, left: 18, right: 18 } : { top: 160, bottom: 90, left: 60, right: 80 }; }

  /* ---------- loader: glowing network built in front of you, progress tracks the real preload ---------- */
  var P = { map: 0, nets: 0, out: 0, dc: 0 }, W8 = { map: 0.35, nets: 0.3, out: 0.15, dc: 0.2 }, shown = 0, ldDone = false, t0 = performance.now();
  function prog() { var p = 0; for (var k in P) p += W8[k] * P[k]; return Math.min(1, p); }
  function step(k, v) { P[k] = Math.max(P[k], v); if (v >= 1) { var li = document.querySelector('.nx-lds li[data-s="' + k + '"]'); if (li) li.classList.add("on"); } if (prog() >= 0.999) setTimeout(finish, reduce ? 50 : Math.max(650, 2600 - (performance.now() - t0))); }   /* never a flash: the build shows for at least ~2.6 s */
  function finish() {
    if (ldDone) return; ldDone = true; shown = 1; $("nx_ldn").textContent = "100%";
    document.body.classList.add("nx-ready");
    try { window.__nxLoad = Math.round(performance.now() - t0); } catch (e) {}
    setTimeout(function () { var l = $("nx_ld"); if (l) l.remove(); }, 900);
  }
  setTimeout(function () { if (!ldDone) { var m = $("nx_ldmsg"); if (m) { m.hidden = false; m.textContent = "Some layers are still loading. They finish in the background."; } setTimeout(finish, 900); } }, 25000);
  (function loader() {
    var cv = $("nx_ldcv"); if (!cv) return; var cx = cv.getContext("2d"), Wd, Ht, dpr, nodes = [], links = [], pulses = [], last = 0, flash = 0;
    function build() {
      dpr = Math.min(2, devicePixelRatio || 1); Wd = cv.clientWidth; Ht = cv.clientHeight; cv.width = Wd * dpr; cv.height = Ht * dpr; cx.setTransform(dpr, 0, 0, dpr, 0, 0);
      nodes = []; links = [];
      var s = Wd < 600 ? 34 : 46, cols = Math.ceil(Wd / s) + 1, rows = Math.ceil(Ht / s) + 1, ox = (Wd - (cols - 1) * s) / 2, oy = (Ht - (rows - 1) * s) / 2, mx = Wd / 2, my = Ht * 0.42;
      var seed = 7; function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
      var idx = {};
      for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
        if (rnd() < 0.18) continue;
        var x = ox + c * s + (rnd() - 0.5) * s * 0.36, y = oy + r * s + (rnd() - 0.5) * s * 0.36;
        var d = Math.hypot((x - mx) / Wd, (y - my) / Ht) + rnd() * 0.06;
        var hub = rnd() < 0.07; idx[r + "," + c] = nodes.length;
        nodes.push({ x: x, y: y, d: d, hub: hub, on: 0, t: 0, r: c, q: r });
      }
      nodes.forEach(function (n, i) {
        [[0, 1], [1, 0], [1, 1], [1, -1]].forEach(function (o, k) {
          if (k >= 2 && rnd() < 0.72) return;
          var j = idx[(n.q + o[0]) + "," + (n.r + o[1])]; if (j == null) return;
          links.push({ a: i, b: j, d: Math.max(n.d, nodes[j].d), t: 0 });
        });
      });
      var ord = nodes.map(function (n, i) { return i; }).sort(function (a, b) { return nodes[a].d - nodes[b].d; });
      ord.forEach(function (i, k) { nodes[i].rank = k / ord.length; });
      links.forEach(function (l) { l.rank = Math.max(nodes[l.a].rank, nodes[l.b].rank); });
    }
    build(); addEventListener("resize", function () { if (!ldDone) build(); });
    function draw(ts) {
      if (ldDone && document.body.classList.contains("nx-ready") && !$("nx_ld")) return;
      var dt = Math.min(64, ts - (last || ts)); last = ts;
      var target = prog(); shown += (target - shown) * Math.min(1, dt / 260); if (ldDone) shown = 1;
      var pctEl = $("nx_ldn"); if (pctEl) pctEl.textContent = (shown >= 0.995 ? 100 : Math.floor(shown * 100)).toString().padStart(2, "0") + "%";
      var lit = 0.04 + shown * 0.96;
      cx.clearRect(0, 0, Wd, Ht);
      var g = cx.createRadialGradient(Wd / 2, Ht * 0.42, 0, Wd / 2, Ht * 0.42, Math.max(Wd, Ht) * 0.75);
      g.addColorStop(0, "rgba(127,212,255," + (0.06 + 0.06 * shown) + ")"); g.addColorStop(1, "rgba(3,4,10,0)"); cx.fillStyle = g; cx.fillRect(0, 0, Wd, Ht);
      cx.lineCap = "round";
      for (var i = 0; i < links.length; i++) {
        var l = links[i], A = nodes[l.a], B = nodes[l.b];
        cx.strokeStyle = "rgba(240,240,250,.05)"; cx.lineWidth = 1; cx.beginPath(); cx.moveTo(A.x, A.y); cx.lineTo(B.x, B.y); cx.stroke();
        if (l.rank <= lit) {
          l.t = Math.min(1, l.t + dt / (reduce ? 1 : 420));
          var x2 = A.x + (B.x - A.x) * l.t, y2 = A.y + (B.y - A.y) * l.t;
          cx.strokeStyle = "rgba(127,212,255," + (0.18 + 0.22 * l.t) + ")"; cx.lineWidth = 1.1; cx.beginPath(); cx.moveTo(A.x, A.y); cx.lineTo(x2, y2); cx.stroke();
          if (!reduce && l.t >= 1 && Math.random() < 0.0016 * (dt / 16)) pulses.push({ l: l, p: 0, rev: Math.random() < 0.5 });
        }
      }
      if (!reduce) {
        cx.shadowColor = "rgba(127,212,255,.9)"; cx.shadowBlur = 10;
        for (var k = pulses.length - 1; k >= 0; k--) {
          var q = pulses[k]; q.p += dt / 700; if (q.p >= 1) { pulses.splice(k, 1); continue; }
          var a = nodes[q.l.a], b = nodes[q.l.b], pp = q.rev ? 1 - q.p : q.p, px = a.x + (b.x - a.x) * pp, py = a.y + (b.y - a.y) * pp;
          cx.fillStyle = "rgba(240,248,255,.95)"; cx.beginPath(); cx.arc(px, py, 1.7, 0, 6.283); cx.fill();
        }
        cx.shadowBlur = 0;
      }
      for (var j = 0; j < nodes.length; j++) {
        var n = nodes[j];
        if (n.rank <= lit) n.t = Math.min(1, n.t + dt / (reduce ? 1 : 360));
        if (n.t > 0) {
          var rr = (n.hub ? 3.2 : 1.7) * (0.6 + 0.4 * n.t);
          if (n.hub) { cx.fillStyle = "rgba(127,212,255," + (0.12 * n.t) + ")"; cx.beginPath(); cx.arc(n.x, n.y, rr * 4, 0, 6.283); cx.fill(); }
          cx.fillStyle = n.hub ? "rgba(240,248,255," + n.t + ")" : "rgba(127,212,255," + (0.5 + 0.5 * n.t) + ")";
          cx.beginPath(); cx.arc(n.x, n.y, rr, 0, 6.283); cx.fill();
          if (n.t < 1 && !reduce) { cx.strokeStyle = "rgba(127,212,255," + (1 - n.t) + ")"; cx.lineWidth = 1; cx.beginPath(); cx.arc(n.x, n.y, rr + 10 * n.t, 0, 6.283); cx.stroke(); }
        } else { cx.fillStyle = "rgba(240,240,250,.10)"; cx.fillRect(n.x - 0.7, n.y - 0.7, 1.4, 1.4); }
      }
      if (!reduce && !ldDone) {   /* scan line sweeping down */
        var sy = ((ts / 2600) % 1) * Ht, sg = cx.createLinearGradient(0, sy - 60, 0, sy);
        sg.addColorStop(0, "rgba(127,212,255,0)"); sg.addColorStop(1, "rgba(127,212,255,.07)"); cx.fillStyle = sg; cx.fillRect(0, sy - 60, Wd, 60);
      }
      requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
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
  var pData = retry("/api/netmap/data", "nets", 3), pDc = retry("/api/netmap/dc", "dc", 2), pWorld = getJSON("/api/signal/world.geojson");
  pData.then(function () { step("out", 0.5); }, function () {});
  var D = null, DC = null, WORLD = null, map = null, ready = false;
  var ON = { internet: true, power: true, cloud: true, dc: false, mobile: false, sat: false, pay: false, apps: false };
  try { var sv = JSON.parse(localStorage.getItem("bn_net_layers") || "null"); if (sv && typeof sv === "object") for (var k0 in ON) if (k0 in sv) ON[k0] = !!sv[k0]; } catch (e) {}

  function boot() {
    if (!window.maplibregl) { setTimeout(boot, 60); return; }
    map = new maplibregl.Map({ container: "nx_map", style: style(), bounds: US, fitBoundsOptions: { padding: PAD() }, minZoom: 1, maxZoom: 13,
      attributionControl: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, fadeDuration: reduce ? 0 : 300, renderWorldCopies: true });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · <a href="https://ioda.inetintel.cc.gatech.edu/" target="_blank" rel="noopener">IODA</a> · <a href="https://www.peeringdb.com/" target="_blank" rel="noopener">PeeringDB</a>' }), "bottom-right");
    setTimeout(function () { var a = document.querySelector(".nx-map .maplibregl-ctrl-attrib"); if (a) a.classList.remove("maplibregl-compact-show"); }, 1500);
    map.on("dataloading", function () { if (!ready) step("map", Math.min(0.8, P.map + 0.04)); });
    map.on("load", function () {
      step("map", 0.5); addLayers(); bindLayers();
      Promise.allSettled([pData, pWorld]).then(function (r) {
        if (r[0].status === "fulfilled") { D = r[0].value; applyData(); }
        else { $("nx_sum").textContent = "Network data is unavailable right now"; }
        if (r[1].status === "fulfilled") { WORLD = r[1].value; applyWorld(); }
        step("out", 1);
      });
      pDc.then(function (j) { DC = j; applyDc(); }, function () {});
      var tk = setInterval(function () {   /* the first view's tiles are all in (the pulse animation would keep "idle" from ever firing) */
        if (map.areTilesLoaded() && map.isStyleLoaded()) { clearInterval(tk); ready = true; step("map", 1); startPulse(); }
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
    map.addSource("dc", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "dc-glow", type: "circle", source: "dc", layout: { visibility: ON.dc ? "visible" : "none" }, paint: { "circle-color": COL.dc, "circle-blur": 1, "circle-opacity": ["interpolate", ["linear"], ["zoom"], 1, 0.14, 6, 0.3],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["+", 2, ["*", 0.04, ["min", ["get", "n"], 200]]], 8, ["+", 6, ["*", 0.08, ["min", ["get", "n"], 200]]]] } });
    map.addLayer({ id: "dc", type: "circle", source: "dc", layout: { visibility: ON.dc ? "visible" : "none" }, paint: { "circle-color": COL.dc, "circle-opacity": 0.9,
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
      map.on("mousemove", id, function (e) { if (!pinned) showCard(e.features[0], e.point, false); map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, function () { if (!pinned) hideCard(); map.getCanvas().style.cursor = ""; });
    });
    map.on("click", function (e) {
      var f = map.queryRenderedFeatures([[e.point.x - 8, e.point.y - 8], [e.point.x + 8, e.point.y + 8]], { layers: ["pt", "dc"].filter(function (l) { return map.getLayoutProperty(l, "visibility") !== "none"; }) })[0];
      if (f) showCard(f, e.point, true); else hideCard(true);
    });
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
    (D.outages.countries || []).forEach(function (c, i) {
      if (c.lon == null) return;
      f.push(feat(c.lon, c.lat, { kind: "country", i: i, c: c.major ? COL.out : COL.deg, fill: c.cur ? (c.major ? COL.out : COL.deg) : "#05060a", sw: 2, r: c.cur ? 7 : 5, hot: !!c.cur, label: c.name, layer: "internet" }));
    });
    (D.outages.us_regions || []).forEach(function (r, i) {
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
  function vis() {
    if (!map || !map.getSource("pts")) return;
    map.getSource("pts").setData({ type: "FeatureCollection", features: PTS.filter(function (x) { return ON[x.properties.layer]; }) });
    ["cty-fill", "cty-line"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", ON.internet ? "visible" : "none"); });
    ["dc", "dc-glow"].forEach(function (l) { if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", ON.dc ? "visible" : "none"); });
    document.querySelectorAll("#nx_f button").forEach(function (b) { b.setAttribute("aria-pressed", ON[b.dataset.k] ? "true" : "false"); });
  }

  function summary() {
    var s = D.summary || {}, iss = (D.nets || []).filter(function (n) { return n.level >= 2; }), maj = iss.filter(function (n) { return n.level >= 3; });
    var chip = $("nx_chip"), txt;
    if (maj.length) { txt = maj.length + " major outage" + (maj.length > 1 ? "s" : "") + " · " + maj[0].name; chip.className = "nx-chip live s-out"; }
    else if (iss.length) { txt = iss.length + " network" + (iss.length > 1 ? "s" : "") + " disrupted · " + iss[0].name; chip.className = "nx-chip live s-deg"; }
    else { txt = "No major U.S. network outages · " + (s.ok || 0) + " of " + (s.networks || 0) + " normal"; chip.className = "nx-chip live s-ok"; }
    $("nx_sum").textContent = txt;
    $("nx_more_lbl").textContent = "All " + (s.networks || "") + " networks";
  }

  /* ---------- detail card ---------- */
  var card = $("nx_card"), pinned = false;
  function linkA(u, t) { var h = url(u); return h ? '<a href="' + h + '"' + (/^\//.test(u) ? "" : ' target="_blank" rel="noopener noreferrer"') + '>' + esc(t) + '</a>' : ""; }
  function showCard(ft, pt, pin) {
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
        '<div class="acts"><a href="/grid">Open The Grid</a></div>';
    } else if (p.kind === "cloud") {
      var cl = D.cloud[p.i], n = (D.nets || []).filter(function (x) { return x.id === cl.p; })[0] || {}; c = lvCol(cl.level);
      h = '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(PNAME[cl.p]) + ' · ' + esc(lvName(cl.level)) + '</span><h3>' + esc(cl.name) + '</h3><p>' + esc(n.status || "") + '</p>' +
        '<div class="acts">' + linkA(n.status_url, "Official status") + linkA(n.page, "Full analysis") + linkA(n.support, "Support") + '</div>';
    }
    card.innerHTML = h + '<button type="button" class="nx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
    card.hidden = false; requestAnimationFrame(function () { card.classList.add("in"); });
    pinned = !!pin; card.classList.toggle("pin", pinned);
    if (innerWidth >= 768) { var x = pt.x + 18, y = pt.y - 20; if (x + 330 > innerWidth) x = pt.x - 338; card.style.left = Math.max(12, x) + "px"; card.style.top = Math.max(70, Math.min(y, innerHeight - card.offsetHeight - 16)) + "px"; }
    var cxb = card.querySelector(".nx-cx"); if (cxb) cxb.onclick = function () { hideCard(true); };
  }
  function hideCard(force) { if (pinned && !force) return; pinned = false; card.classList.remove("in", "pin"); setTimeout(function () { if (!card.classList.contains("in")) card.hidden = true; }, 200); }
  addEventListener("keydown", function (e) { if (e.key === "Escape") { hideCard(true); more(false); } });

  /* ---------- chips ---------- */
  var GMAP = { internet: ["isp"], mobile: ["mobile"], sat: ["sat"], cloud: ["cloud"], pay: ["pay"], apps: ["apps"] };
  document.querySelectorAll("#nx_f button").forEach(function (b) {
    b.addEventListener("click", function () {
      var k = b.dataset.k; ON[k] = !ON[k];
      try { localStorage.setItem("bn_net_layers", JSON.stringify(ON)); } catch (e) {}
      vis(); if (D) list();
      if (ON[k] && k === "dc" && map) map.easeTo({ zoom: Math.max(map.getZoom(), 2.6), duration: reduce ? 0 : 700 });
      if (ON[k] && ["mobile", "sat", "pay", "apps"].indexOf(k) >= 0) { more(true); var g = $("nxg-" + GMAP[k][0]); if (g) setTimeout(function () { g.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }); }, 420); }
    });
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
    var shownGroups = (D.groups || []).filter(function (g) { return g.id === "isp" ? ON.internet : g.id === "mobile" ? ON.mobile : g.id === "sat" ? ON.sat : g.id === "cloud" ? ON.cloud : g.id === "pay" ? ON.pay : g.id === "apps" ? ON.apps : true; });
    if (!shownGroups.length) shownGroups = D.groups || [];
    shownGroups.forEach(function (g) {
      var ns = nets.filter(function (n) { return n.group === g.id; }).sort(function (a, b) { return (b.level - a.level) || a.name.localeCompare(b.name); });
      var bad = ns.filter(function (n) { return n.level >= 2; }).length;
      h += '<div class="nx-gh" id="nxg-' + g.id + '"><h3>' + esc(g.name) + '</h3><span>' + (bad ? bad + " disrupted" : "All normal") + '</span></div>';
      ns.forEach(function (n) {
        h += '<details class="nx-net"><summary><i style="background:' + lvCol(n.level) + '"></i><b>' + esc(n.name) + '</b><em>' + (n.uptime != null ? n.uptime.toFixed(2) + "%" : "") + '</em><small>' + esc(lvName(n.level)) + ' · ' + esc(n.status) + '</small>' + bars(n.days) + '</summary>' +
          '<div class="nx-nb">' + ((n.incidents || []).length ? '<ul>' + n.incidents.map(function (i) { return '<li>' + esc(i.t) + (i.since ? ' · ' + esc(ago(i.since)) : '') + '</li>'; }).join("") + '</ul>' : '<p style="margin:0">No active incidents.</p>') +
          (n.uptime != null ? '<p style="margin:6px 0 0">30-day availability ' + n.uptime.toFixed(2) + '% (from ' + esc(n.basis || "public data") + ').</p>' : '') +
          '<div class="nx-acts">' + linkA(n.status_url, "Official status") + linkA(n.support, "Contact support") + linkA(n.page, "Full analysis") + linkA(n.ioda, "IODA signal") + '</div></div></details>';
      });
    });
    h += '<p class="nx-src">Bars show the last 30 days: green normal, grey minor, orange disruption, red major outage. Sources: ' + (D.sources || []).map(function (x) { return linkA(x.url, x.name); }).join(" · ") +
      '. Updated ' + esc(ago(D.generated)) + '. Cell coverage by carrier is in the <a href="https://broadbandmap.fcc.gov/" target="_blank" rel="noopener noreferrer">FCC National Broadband Map</a>. <a href="/network/providers">Cloud provider pages</a></p>';
    $("nx_list").innerHTML = h;
  }

  /* ---------- live refresh every 5 minutes ---------- */
  setInterval(function () { if (document.hidden) return; getJSON("/api/netmap/data").then(function (j) { D = j; applyData(); }, function () {}); }, 300000);
})();
