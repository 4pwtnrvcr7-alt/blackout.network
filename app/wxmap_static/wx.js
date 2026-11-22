/* Weather (/weather, Nov 22 2026, pt1742u). MapLibre GL + OpenFreeMap, same base style as /grid and /map.
   Every overlay is a map-native layer (raster tiles, image or GeoJSON sources), so it moves with the map at zero lag.
   Data: /api/wxmap/frames|grid|alerts|storms|tropical (cached, keyless public sources), /api/weather (point forecast). */
(function () {
  "use strict";
  var F = ["Noto Sans Regular"], FB = ["Noto Sans Bold"];
  function style() {
    var lbl = "rgba(240,240,250,", halo = "rgba(5,6,10,.9)";
    return {
      version: 8, glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
      sources: { omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: "" } },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#0c0e15" } },
        { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": "#05060a", "fill-antialias": true } },
        { id: "ice", type: "fill", source: "omt", "source-layer": "landcover", filter: ["==", ["get", "subclass"], "glacier"], paint: { "fill-color": "#11141c", "fill-opacity": 0.6 } },
        { id: "park", type: "fill", source: "omt", "source-layer": "park", minzoom: 8, paint: { "fill-color": "#0f131a", "fill-opacity": 0.6 } },
        { id: "waterway", type: "line", source: "omt", "source-layer": "waterway", minzoom: 7, paint: { "line-color": "#070910", "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.5, 14, 2] } },
        { id: "building", type: "fill", source: "omt", "source-layer": "building", minzoom: 14, paint: { "fill-color": "#141822", "fill-opacity": 0.7 } },
        { id: "road-minor", type: "line", source: "omt", "source-layer": "transportation", minzoom: 10, filter: ["match", ["get", "class"], ["minor", "service", "tertiary", "secondary"], true, false],
          paint: { "line-color": "rgba(240,240,250,.06)", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.4, 16, 3] } },
        { id: "road-major", type: "line", source: "omt", "source-layer": "transportation", minzoom: 5, filter: ["match", ["get", "class"], ["motorway", "trunk", "primary"], true, false],
          paint: { "line-color": "rgba(240,240,250,.09)", "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.3, 10, 1, 16, 4] } },
        { id: "admin-state", type: "line", source: "omt", "source-layer": "boundary", minzoom: 2.5, filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
          paint: { "line-color": "rgba(240,240,250,.07)", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 8, 1], "line-dasharray": [3, 2] } },
        { id: "admin-country", type: "line", source: "omt", "source-layer": "boundary", filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1], ["!=", ["get", "disputed"], 1]],
          paint: { "line-color": "rgba(240,240,250,.17)", "line-width": ["interpolate", ["linear"], ["zoom"], 0, 0.4, 5, 0.9, 10, 1.6] } },
        { id: "lbl-country", type: "symbol", source: "omt", "source-layer": "place", minzoom: 1.5, maxzoom: 7, filter: ["==", ["get", "class"], "country"],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": FB, "text-transform": "uppercase", "text-letter-spacing": 0.22,
            "text-size": ["interpolate", ["linear"], ["zoom"], 1.5, 8.5, 4, 11, 6, 13], "text-max-width": 7, "symbol-sort-key": ["coalesce", ["get", "rank"], 9] },
          paint: { "text-color": lbl + ".38)", "text-halo-color": halo, "text-halo-width": 1.2 } },
        { id: "lbl-state", type: "symbol", source: "omt", "source-layer": "place", minzoom: 4, maxzoom: 8, filter: ["==", ["get", "class"], "state"],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-transform": "uppercase", "text-letter-spacing": 0.24, "text-size": 9.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".24)", "text-halo-color": halo, "text-halo-width": 1 } },
        { id: "lbl-city", type: "symbol", source: "omt", "source-layer": "place", minzoom: 3, filter: ["match", ["get", "class"], ["city"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": ["interpolate", ["linear"], ["zoom"], 3, 10, 8, 13, 12, 15],
            "text-letter-spacing": 0.04, "text-max-width": 8, "symbol-sort-key": ["coalesce", ["get", "rank"], 20],
            "text-variable-anchor": ["top", "bottom", "left", "right"], "text-radial-offset": 0.6 },
          paint: { "text-color": lbl + ".58)", "text-halo-color": halo, "text-halo-width": 1.2, "text-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 5, 1] } },
        { id: "lbl-town", type: "symbol", source: "omt", "source-layer": "place", minzoom: 8, filter: ["match", ["get", "class"], ["town"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": 11.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".45)", "text-halo-color": halo, "text-halo-width": 1 } },
        { id: "lbl-village", type: "symbol", source: "omt", "source-layer": "place", minzoom: 11, filter: ["match", ["get", "class"], ["village", "suburb"], true, false],
          layout: { "text-field": ["coalesce", ["get", "name:en"], ["get", "name_en"], ["get", "name"]], "text-font": F, "text-size": 10.5, "text-max-width": 8 },
          paint: { "text-color": lbl + ".34)", "text-halo-color": halo, "text-halo-width": 1 } }
      ]
    };
  }

  /* ---------- helpers ---------- */
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function url(u) { return /^https?:\/\//i.test(u || "") ? esc(u) : ""; }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  var ET = "America/New_York";
  var FW = new Intl.DateTimeFormat("en-US", { timeZone: ET, weekday: "short", hour: "numeric", minute: "2-digit" });
  var FD = new Intl.DateTimeFormat("en-US", { timeZone: ET, weekday: "short" });
  var FDAY = new Intl.DateTimeFormat("en-US", { timeZone: ET, year: "numeric", month: "2-digit", day: "2-digit" });
  var FDATE = new Intl.DateTimeFormat("en-US", { timeZone: ET, month: "short", day: "numeric", year: "numeric" });
  var FT = new Intl.DateTimeFormat("en-US", { timeZone: ET, month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  function when(ms) { return FW.format(new Date(ms)) + " ET"; }
  function stamp(ms) { return FT.format(new Date(ms)) + " ET"; }
  function rel(ms) {
    var m = Math.round((ms - Date.now()) / 60000), a = Math.abs(m);
    var s = a < 60 ? a + " min" : a < 2880 ? Math.round(a / 60) + " h" : Math.round(a / 1440) + " days";
    return m <= 0 ? s + " ago" : "in " + s;
  }
  function tms(s) { var t = Date.parse(s || ""); return isFinite(t) ? t : null; }
  var touch = matchMedia("(hover: none), (pointer: coarse)").matches;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  function jget(u) { return fetch(u, { cache: "no-store" }).then(function (r) { return r.json().then(function (j) { if (!r.ok) { var e = new Error(j && j.reason || ("HTTP " + r.status)); e.reason = j && j.reason; throw e; } return j; }); }); }

  /* ---------- palettes (no yellow) ---------- */
  var WC = { tor: "#FF3B3B", svr: "#FF7A1A", flood: "#2FD67B", trop: "#E040FB", winter: "#5AB4FF", wind: "#B39DFF", cold: "#7FE3F0", heat: "#FF6FAE" };
  var WL = { tor: "Tornado", svr: "Severe storm", flood: "Flood", trop: "Tropical", winter: "Winter", wind: "High wind", cold: "Extreme cold", heat: "Heat or fire" };
  var RC = { tor: "#FF3B3B", hail: "#7FE3F0", wind: "#B39DFF", flood: "#2FD67B", snow: "#F0F0FA" };
  var EFC = ["#9BD8FF", "#2FD67B", "#FF9A3D", "#FF7A1A", "#FF3B3B", "#E040FB"];
  var TCC = { "-1": "#7C8190", "0": "#7FB2FF", "1": "#22C7A9", "2": "#2FD67B", "3": "#FF9A3D", "4": "#FF6A2A", "5": "#E040FB" };
  var GDC = { green: "#2FD67B", orange: "#FF9A3D", red: "#FF3B3B" };
  var OLC = { TSTM: "#7C8190", MRGL: "#2FD67B", SLGT: "#FFB070", ENH: "#FF7A1A", MDT: "#FF3B3B", HIGH: "#E040FB" };
  var OLN = { TSTM: "General thunderstorms", MRGL: "Marginal risk (1 of 5)", SLGT: "Slight risk (2 of 5)", ENH: "Enhanced risk (3 of 5)", MDT: "Moderate risk (4 of 5)", HIGH: "High risk (5 of 5)" };
  function match(prop, obj, dflt) { var e = ["match", ["to-string", ["get", prop]]]; Object.keys(obj).forEach(function (k) { e.push(k, obj[k]); }); e.push(dflt); return e; }
  /* model-grid colour ramps: [value, r, g, b, alpha] */
  var PAL = {
    temp: [[-20, 236, 232, 255, .82], [0, 168, 140, 255, .82], [15, 110, 108, 255, .82], [32, 47, 155, 255, .82], [45, 34, 199, 199, .8], [60, 47, 214, 123, .78],
           [78, 255, 154, 61, .78], [90, 255, 106, 42, .8], [100, 255, 66, 52, .82], [112, 224, 64, 251, .85]],
    rain: [[0.005, 47, 120, 220, 0], [0.02, 47, 140, 255, .45], [0.1, 47, 170, 255, .62], [0.25, 34, 199, 169, .72], [0.5, 47, 214, 123, .8], [1, 255, 154, 61, .85], [2, 224, 64, 251, .9]],
    snow: [[0.05, 150, 180, 255, 0], [0.3, 150, 180, 255, .45], [1, 175, 205, 255, .65], [3, 240, 244, 255, .8], [6, 195, 155, 255, .85], [12, 155, 92, 255, .88], [24, 224, 64, 251, .92]]
  };
  function ramp(p, v) {
    if (v == null || isNaN(v)) return null;
    if (v <= p[0][0]) return p[0].slice(1);
    for (var i = 1; i < p.length; i++) if (v <= p[i][0]) {
      var a = p[i - 1], b = p[i], t = (v - a[0]) / (b[0] - a[0]);
      return [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t];
    }
    return p[p.length - 1].slice(1);
  }
  function grad(p, lo, hi) { return "linear-gradient(90deg," + p.filter(function (s) { return s[0] >= lo && s[0] <= hi; }).map(function (s) { return "rgba(" + s[1] + "," + s[2] + "," + s[3] + "," + Math.max(s[4], .55) + ")"; }).join(",") + ")"; }
  /* radar palette: the worker repaints NOAA radar, NASA IMERG and GFS rain with these stops (dBZ, r, g, b, alpha) */
  var RADAR_GRAD = "linear-gradient(90deg,rgba(50,118,205,.6),#3e9cee,#38c4e2,#2ed496,#24ba60,#ff9a3d,#ff6a2a,#ff3b3b,#d62678,#e040fb,#f6ecff)";
  var WMO = { 0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorms", 96: "Thunderstorms, hail", 99: "Severe thunderstorms" };

  /* ---------- loader: thin-line globe with a radar sweep; progress is the real preload (map, frames, radar tiles, storms) ---------- */
  var LD = { map: 0, frames: 0, storms: 0, need: 0, have: 0 }, ldT0 = Date.now(), ldDone = false;
  function ldRow(k, txt, ok) { var li = document.querySelector('.wx-ldl li[data-s="' + k + '"]'); if (!li) return; li.querySelector("b").textContent = txt; li.classList.toggle("on", !!ok); }
  function ldPct() { return Math.min(1, 0.2 * LD.map + 0.1 * LD.frames + 0.15 * LD.storms + 0.55 * (LD.need ? Math.min(1, LD.have / LD.need) : (LD.frames ? 1 : 0))); }
  function ldUpdate() {
    if (ldDone) return;
    var p = ldPct(), n = $("wx_ldn"), f = $("wx_ldfill");
    if (n) n.textContent = ("00" + Math.round(p * 100)).slice(-3);
    if (f) f.style.transform = "scaleX(" + p.toFixed(3) + ")";
    var ph = !LD.map ? "Starting the map engine" : !LD.frames ? "Reading the radar index" : LD.need && LD.have < LD.need ? "Buffering radar frames" : !LD.storms ? "Loading warnings and storms" : "Ready";
    var e = $("wx_ldphase"); if (e) e.textContent = ph;
    if (p >= 0.999) finish();
  }
  function step(k) {
    if (LD[k]) return; LD[k] = 1;
    if (k === "map") ldRow("map", "Online", true);
    if (k === "storms") ldRow("alerts", "Synced", true);
    ldUpdate();
  }
  function finish() {
    if (ldDone) return; ldDone = true; ldUpdate.done = 1;
    var n = $("wx_ldn"), f = $("wx_ldfill"); if (n) n.textContent = "100"; if (f) f.style.transform = "scaleX(1)";
    setTimeout(function () { document.body.classList.add("wx-ready"); setTimeout(function () { globeStop = true; }, 900); }, Math.max(250, 1400 - (Date.now() - ldT0)));
  }
  setTimeout(function () { if (!ldDone) { var m = $("wx_ldmsg"); if (m) { m.hidden = false; m.textContent = "Still buffering. The rest loads in the background."; } setTimeout(finish, 1200); } }, 11000);
  var globeStop = false;
  (function globe() {
    var cv = $("wx_ldg"); if (!cv || !cv.getContext) return;
    var dpr = Math.min(2, window.devicePixelRatio || 1), S = 260; cv.width = S * dpr; cv.height = S * dpr; cv.style.width = S + "px"; cv.style.height = S + "px";
    var c = cv.getContext("2d"), R = 78, C = S / 2, tilt = -0.36, t0 = performance.now();
    var blips = []; for (var i = 0; i < 26; i++) blips.push([Math.random() * 360 - 180, Math.random() * 110 - 50, Math.random()]);
    function proj(lon, lat, rot) {
      var l = (lon + rot) * Math.PI / 180, p = lat * Math.PI / 180, x = Math.cos(p) * Math.sin(l), y = Math.sin(p), z = Math.cos(p) * Math.cos(l);
      var y2 = y * Math.cos(tilt) - z * Math.sin(tilt), z2 = y * Math.sin(tilt) + z * Math.cos(tilt);
      return [C + R * x, C - R * y2, z2];
    }
    function line(pts, rot, front) {
      c.beginPath(); var pen = false;
      for (var i = 0; i < pts.length; i++) { var q = proj(pts[i][0], pts[i][1], rot); if ((q[2] >= 0) === front) { if (!pen) c.moveTo(q[0], q[1]); else c.lineTo(q[0], q[1]); pen = true; } else pen = false; }
      c.stroke();
    }
    function frame(now) {
      if (globeStop) return;
      var t = (now - t0) / 1000, rot = t * 14, sw = (t * 1.35) % (Math.PI * 2);
      c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, S, S);
      /* bezel ticks */
      c.save(); c.translate(C, C); c.rotate(-t * 0.08);
      for (var k = 0; k < 120; k++) { var a = k / 120 * Math.PI * 2, long = k % 10 === 0, r0 = long ? 112 : 116, r1 = 121;
        c.strokeStyle = long ? "rgba(240,240,250,.55)" : "rgba(240,240,250,.16)"; c.lineWidth = 1; c.beginPath(); c.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); c.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); c.stroke(); }
      c.restore();
      c.strokeStyle = "rgba(240,240,250,.10)"; c.lineWidth = 1; c.beginPath(); c.arc(C, C, 104, 0, Math.PI * 2); c.stroke();
      /* sweep wedge */
      var N = 28; for (var j = 0; j < N; j++) { var a0 = sw - j * 0.035, al = 0.22 * (1 - j / N);
        c.fillStyle = "rgba(90,180,255," + al.toFixed(3) + ")"; c.beginPath(); c.moveTo(C, C); c.arc(C, C, 104, a0 - 0.036, a0); c.closePath(); c.fill(); }
      c.strokeStyle = "rgba(150,205,255,.85)"; c.lineWidth = 1.2; c.beginPath(); c.moveTo(C, C); c.lineTo(C + Math.cos(sw) * 104, C + Math.sin(sw) * 104); c.stroke();
      /* globe: back graticule faint, front brighter */
      var lon, lat, pts;
      [false, true].forEach(function (front) {
        c.strokeStyle = front ? "rgba(240,240,250,.30)" : "rgba(240,240,250,.06)"; c.lineWidth = front ? 0.8 : 0.6;
        for (lon = -180; lon < 180; lon += 20) { pts = []; for (lat = -90; lat <= 90; lat += 5) pts.push([lon, lat]); line(pts, rot, front); }
        for (lat = -60; lat <= 60; lat += 20) { pts = []; for (lon = -180; lon <= 180; lon += 5) pts.push([lon, lat]); line(pts, rot, front); }
      });
      c.strokeStyle = "rgba(240,240,250,.6)"; c.lineWidth = 1; c.beginPath(); c.arc(C, C, R, 0, Math.PI * 2); c.stroke();
      /* echoes: light up as the sweep passes them */
      blips.forEach(function (b) {
        var q = proj(b[0], b[1], rot); if (q[2] < 0.05) return;
        var ang = Math.atan2(q[1] - C, q[0] - C); ang = (ang + Math.PI * 2) % (Math.PI * 2);
        var d = (sw - ang + Math.PI * 2) % (Math.PI * 2), glow = Math.max(0, 1 - d / 2.2);
        if (glow <= 0.02) return;
        c.fillStyle = "rgba(150,205,255," + (glow * 0.9 * q[2]).toFixed(3) + ")"; c.beginPath(); c.arc(q[0], q[1], 1.2 + 1.6 * glow * b[2], 0, Math.PI * 2); c.fill();
      });
      /* crosshair */
      c.strokeStyle = "rgba(240,240,250,.22)"; c.lineWidth = 1; c.beginPath(); c.moveTo(C - 128, C); c.lineTo(C - 108, C); c.moveTo(C + 108, C); c.lineTo(C + 128, C); c.moveTo(C, C - 128); c.lineTo(C, C - 108); c.moveTo(C, C + 108); c.lineTo(C, C + 128); c.stroke();
      requestAnimationFrame(frame);
    }
    if (reduce) { frame(t0 + 4000); globeStop = true; } else requestAnimationFrame(frame);
  })();

  /* ---------- state ---------- */
  var map = null, US = [[-125.5, 23.5], [-66, 50]], BEFORE = "admin-state";
  var MODE = "radar", FRAMES = [], IDX = 0, NOWI = 0, playing = false, live = true;
  var FR = null, AL = null, ST = null, TR = null, GL = null;
  var ERR = { radar: null, grid: null };
  var LAYS = Object.assign({ clouds: true, global: true, warn: true, reports: true, tracks: true, trop: false, outlook: false, labels: true }, store("bn_wx_lays") || {});
  function PAD() { return innerWidth < 768 ? { top: 150, bottom: 150, left: 2, right: 2 } : { top: 140, bottom: 140, left: 70, right: 80 }; }
  var US0 = innerWidth < 768 ? [[-124.6, 24.6], [-67.2, 49.2]] : US;

  /* ---------- frames (timeline) ---------- */
  function buildFrames(keepT) {
    var out = [];
    if (MODE === "radar" && FR) {
      FR.past.forEach(function (f) { out.push({ t: tms(f.t), layer: f.layer, sat: f.sat || {}, im: f.im || null, kind: "past" }); });
      FR.forecast.forEach(function (f) { var t = tms(f.t); if (!out.length || t > out[out.length - 1].t) out.push({ t: t, layer: f.layer, kind: "fc", run: f.run }); });
      var gt = gfsTimes();   /* past the U.S. forecast: worldwide GFS every 3 hours out to 7 days */
      gt.forEach(function (t) { if (!out.length || t > out[out.length - 1].t + 1800000) out.push({ t: t, layer: null, kind: "fc" }); });
      out.forEach(function (f) {   /* worldwide rain: IMERG where it has arrived, else the nearest GFS hour; clouds: satellite (past) or GFS (forecast) */
        var b = -1, bd = Infinity; gt.forEach(function (t, k) { var d = Math.abs(t - f.t); if (d < bd) { bd = d; b = k; } });
        var tol = f.kind === "fc" ? 5400000 : 10800000;
        f.gp = !f.im && b >= 0 && bd <= tol ? b : -1;
        f.gc = f.kind === "fc" && b >= 0 && bd <= 5400000 ? b : -1;
      });
    } else if (MODE !== "radar" && (GD.us || GD.world)) {
      var ts = {}; ["world", "us"].forEach(function (gk) { if (GD[gk]) GD[gk].times.forEach(function (t) { ts[t] = 1; }); });
      Object.keys(ts).map(Number).sort(function (a, b) { return a - b; }).forEach(function (t) { out.push({ t: t, kind: t <= Date.now() ? "past" : "fc" }); });
    }
    FRAMES = out;
    var now = Date.now(); NOWI = 0;
    for (var i = 0; i < out.length; i++) if (out[i].t <= now + 60000 && (MODE !== "radar" || out[i].kind === "past")) NOWI = i;   /* radar "now" is always the latest observed scan */
    var r = $("wx_range"); r.max = Math.max(0, out.length - 1);
    var target = (keepT == null || live) ? NOWI : nearest(keepT);
    ticks();
    go(target, true);
    if (MODE === "radar") setTimeout(prefetch, 60); else mPreload();
    bufTick();
  }
  function nearest(t) { var b = 0, bd = Infinity; FRAMES.forEach(function (f, i) { var d = Math.abs(f.t - t); if (d < bd) { bd = d; b = i; } }); return b; }
  function pos(i) { return FRAMES.length > 1 ? i / (FRAMES.length - 1) * 100 : 0; }
  function ticks() {
    var h = "", last = null, n = FRAMES.length;
    if (n > 1 && NOWI < n - 1) h += '<span class="fc-zone" style="left:' + pos(NOWI) + '%;right:0"></span>';
    var nowP = pos(NOWI), tw = ($("wx_ticks").clientWidth || 300), gap = Math.max(7, 34 / tw * 100), lastP = -99;   // day labels never closer than ~34px
    FRAMES.forEach(function (f, i) {
      var d = FDAY.format(new Date(f.t));
      if (last !== null && d !== last) {
        var p = pos(i); h += '<i style="left:' + p + '%"></i>';
        if (Math.abs(p - nowP) > gap && p - lastP >= gap) { h += '<b style="left:' + p + '%">' + esc(FD.format(new Date(f.t))) + '</b>'; lastP = p; }
      }
      last = d;
    });
    if (n > 1) h += '<b style="left:' + nowP + '%;color:#5AB4FF">Now</b>';
    $("wx_ticks").innerHTML = h;
    $("wx_nowm").style.left = nowP + "%";
    $("wx_nowm").style.display = n > 1 ? "" : "none";
  }
  function label() {
    var f = FRAMES[IDX]; if (!f) { $("wx_when").textContent = MODE === "radar" ? (ERR.radar || "Radar unavailable") : (ERR.grid || "Loading the forecast grid…"); $("wx_rel").textContent = ""; return; }
    var r = $("wx_rel"), isNow = IDX === NOWI;
    var what = MODE === "radar" ? (f.kind === "fc" ? "Forecast" : "Radar") : MODE === "temp" ? "Temperature" : MODE === "rain" ? "Rain, 3 h to" : "Snow, 24 h to";
    $("wx_when").textContent = what + " · " + when(f.t);
    r.textContent = isNow ? (MODE === "radar" ? "Live" : "Now") : rel(f.t);
    r.classList.toggle("fc", f.kind === "fc");
    $("wx_fill").style.width = pos(IDX) + "%";
    var rg = $("wx_range"); rg.value = IDX; rg.setAttribute("aria-valuetext", what + ", " + when(f.t) + (isNow ? ", now" : ", " + rel(f.t)));
  }
  var legFc = null;
  function go(i, instant) {
    if (!FRAMES.length) { label(); return; }
    IDX = clamp(i, 0, FRAMES.length - 1); live = IDX === NOWI;
    var isFc = MODE === "radar" ? FRAMES[IDX].kind + (FRAMES[IDX].layer ? "u" : "w") : MODE; if (isFc !== legFc) { legFc = isFc; legend(); }
    if (map && ready) { if (MODE === "radar") rShow(IDX, instant); else gShow(IDX, instant); timeFilters(); }
    label();
  }

  /* ---------- radar: one map raster layer per frame. Tiles come through a local "wxr://" protocol: the bytes are prefetched for every
     frame in view, and a worker repaints them (one palette, soft edges). Outside the NOAA domain each frame also has worldwide layers:
     past = geostationary infrared clouds (NASA GIBS, EUMETSAT) + NASA IMERG rain (else GFS), forecast = GFS rain + cloud cover. ---------- */
  var RLIVE = {}, RCUR = null, ROP = 0.92, RMZ = 7, SMZ = 5, IMZ = 4, OPF = {}, WK = null, wkId = 0, wkCb = {}, BYTES = new Map(), PROTO = false, NOAA_B = [-130, 20, -60, 55];
  function wk() {
    if (WK !== null) return WK;
    try {
      if (typeof OffscreenCanvas === "undefined" || !window.Worker || !window.createImageBitmap) throw 0;
      var oc = new OffscreenCanvas(1, 1); if (!oc.getContext("2d") || !oc.transferToImageBitmap) throw 0;
      var n = clamp((navigator.hardwareConcurrency || 4) - 1, 2, 4);   /* a small pool: tiles decode in parallel, the map thread stays free */
      for (var i = 0; i < n; i++) {
        var w = new Worker("/api/wxmap/wxw.js?v=" + ($("wx_main").dataset.wxw || "1"));
        w.onmessage = function (e) { var m = e.data, cb = wkCb[m.id]; delete wkCb[m.id]; if (cb) cb(m); this.busy--; tPump(); };
        w.busy = 0; POOL.push(w);
      }
      WK = POOL[0];
    } catch (e) { WK = false; POOL = []; }
    return WK;
  }
  /* tile jobs: queued on this side so a frame the map has already dropped (aborted request) never costs a decode */
  var POOL = [], TQ = [];
  function tileCall(msg, tr, ac) {
    return new Promise(function (res, rej) { TQ.push({ msg: msg, tr: tr || [], ac: ac, res: res, rej: rej }); tPump(); });
  }
  function tPump() {
    while (TQ.length) {
      var w = null; for (var i = 0; i < POOL.length; i++) if (POOL[i].busy < 2 && (!w || POOL[i].busy < w.busy)) w = POOL[i];
      if (!w) return;
      var j = TQ.shift();
      if (j.ac && j.ac.signal && j.ac.signal.aborted) { j.res({ bmp: null }); continue; }
      (function (j, w) { var id = ++wkId; j.msg.id = id; wkCb[id] = function (m) { if (m.err) j.rej(new Error(m.err)); else j.res(m); }; w.busy++; w.postMessage(j.msg, j.tr); })(j, w);
    }
  }
  function poolAll(mk) {   /* the same message to every worker (GFS data); resolves when all have it */
    return Promise.all(POOL.map(function (w) { return new Promise(function (res, rej) { var o = mk(), id = ++wkId; o.msg.id = id; wkCb[id] = function (m) { if (m.err) rej(new Error(m.err)); else res(m); }; w.busy++; w.postMessage(o.msg, o.tr); }); }));
  }
  function wkCall(msg, tr) { return new Promise(function (res, rej) { var id = ++wkId; msg.id = id; wkCb[id] = function (m) { if (m.err) rej(new Error(m.err)); else res(m); }; WK.busy++; WK.postMessage(msg, tr || []); }); }
  function blank() { var c = new OffscreenCanvas(1, 1); c.getContext("2d"); return c.transferToImageBitmap(); }
  var GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/", GL_ = { ge: "GOES-East_ABI_Band13_Clean_Infrared", gw: "GOES-West_ABI_Band13_Clean_Infrared", hi: "Himawari_AHI_Band13_Clean_Infrared" };
  var EUMW = "https://view.eumetsat.int/geoserver/wms?service=WMS&version=1.3.0&request=GetMap&styles=&format=image/png&crs=EPSG:3857&width=256&height=256", EL = { ms: "msg_fes:ir108", io: "msg_iodc:ir108" };
  var SECB = { gw: [-180, -75, -103.5, 75], ge: [-108.5, -75, -35, 75], ms: [-40, -75, 32.5, 75], io: [27.5, -75, 92.5, 75], hi: [87.5, -75, 180, 75] };
  function upURL(kind, id, z, x, y) {
    if (kind === "s") { var p = id.split("|"); return GIBS + GL_[p[0]] + "/default/" + p[1] + "/GoogleMapsCompatible_Level6/" + z + "/" + y + "/" + x + ".png"; }
    if (kind === "i") return GIBS + "IMERG_Precipitation_Rate_30min/default/" + id + "/GoogleMapsCompatible_Level6/" + z + "/" + y + "/" + x + ".png";
    if (kind === "e") {
      var q = id.split("|"), n = Math.pow(2, z), R = 20037508.342789244, sz = 2 * R / n;
      return EUMW + "&layers=" + EL[q[0]] + "&time=" + q[1] + "&bbox=" + (-R + x * sz).toFixed(1) + "," + (R - (y + 1) * sz).toFixed(1) + "," + (-R + (x + 1) * sz).toFixed(1) + "," + (R - y * sz).toFixed(1);
    }
    return FR.tile.replace("{layer}", id).replace("{z}", z).replace("{x}", x).replace("{y}", y);
  }
  /* fetch queue: 6 at a time per host is what browsers allow over HTTP/1.1 anyway; highest priority first */
  var Q = [], QN = 0, QMAX = 16;
  function bytes(u, prio) {
    var h = BYTES.get(u);
    if (h) { if (!h.done && prio < h.prio) { h.prio = prio; if (h.q) h.q.prio = prio; } return h.p; }
    h = { prio: prio, done: false }; BYTES.set(u, h);
    h.p = new Promise(function (res) { h.q = { u: u, prio: prio, res: res, h: h }; Q.push(h.q); });
    pump(); return h.p;
  }
  function pump() {
    while (QN < QMAX && Q.length) {
      var bi = 0; for (var i = 1; i < Q.length; i++) if (Q[i].prio < Q[bi].prio) bi = i;
      var it = Q.splice(bi, 1)[0]; it.h.q = null; QN++;
      (function (it) {
        fetch(it.u, { mode: "cors", credentials: "omit" }).then(function (r) { return r.ok ? r.arrayBuffer() : null; }).catch(function () { return null; })
          .then(function (b) { it.h.done = true; it.h.ok = !!b; if (!b) BYTES.delete(it.u); QN--; it.res(b); pump(); bufTick(); });
      })(it);
    }
  }
  function trim() {   /* keep memory bounded: drop the oldest finished downloads beyond 6,000 tiles */
    if (BYTES.size < 6000) return;
    var n = BYTES.size - 5000; BYTES.forEach(function (h, u) { if (n > 0 && h.done) { BYTES.delete(u); n--; } });
  }
  function proto(params, ac) {
    var m = /^wxr:\/\/([mhseig])\/([^/]+)\/(\d+)\/(\d+)\/(\d+)/.exec(params.url);
    if (!m || !FR) return Promise.resolve({ data: blank() });
    var kind = m[1], id = decodeURIComponent(m[2]), z = +m[3], x = +m[4], y = +m[5];
    if (kind === "g") {   /* worldwide GFS: drawn in the worker from the model grid, no download */
      var gp = id.split("|");
      if (!GFSR || gp[2] !== GTAG) return Promise.resolve({ data: blank() });
      return tileCall({ op: "gfstile", run: GFSR, kind: gp[0], k: +gp[1], z: z, x: x, y: y }, [], ac).then(function (r) { return { data: r.bmp || blank() }; }, function () { return { data: blank() }; });
    }
    return bytes(upURL(kind, id, z, x, y), -1).then(function (buf) {
      if (!buf || !buf.byteLength) return { data: blank() };
      var cp = buf.slice(0);
      return tileCall({ op: "tile", kind: kind, buf: cp, z: z, x: x, y: y, sec: id.split("|")[0] }, [cp], ac).then(function (r) { return { data: r.bmp || blank() }; }, function () { return { data: blank() }; });
    });
  }
  function rSrcs(f) {
    var a = [];
    if (PROTO) {
      if (f.kind === "past") {   /* clouds: one geostationary satellite per sector (tiles are 512 px on screen: soft, and a quarter of the requests) */
        ["gw", "ge", "ms", "io", "hi"].forEach(function (k) { var t = f.sat && f.sat[k]; if (t) a.push({ k: k === "ms" || k === "io" ? "e" : "s", id: k + "|" + t, b: SECB[k], mz: SMZ, ts: 512, cl: 1 }); });
      } else if (f.gc >= 0 && GFSR) a.push({ k: "g", id: "c|" + f.gc + "|" + GTAG, mz: 6, ts: 256, cl: 1 });
      if (f.im) a.push({ k: "i", id: f.im, b: [-180, -60, 180, 60], mz: IMZ, ts: 256, ex: 1 });
      else if (f.gp >= 0 && GFSR) a.push({ k: "g", id: "p" + (f.layer ? "m" : "") + "|" + f.gp + "|" + GTAG, mz: 6, ts: 256 });
    }
    if (f.layer) a.push({ k: f.kind === "fc" ? "h" : "m", id: f.layer, b: NOAA_B, mz: RMZ, ts: 256 });
    return a;
  }
  function rId(f) { return "r-" + f.t + (GFSR ? "g" : "") + (f.layer ? "" : "n"); }
  function rEnsure(f) {
    var id = rId(f);
    if (!RLIVE[id]) {
      RLIVE[id] = [];
      rSrcs(f).forEach(function (s) {
        var sid = id + s.k + s.id.replace(/[^A-Za-z0-9]/g, "");
        if (!map.getSource(sid)) {
          var t = PROTO ? "wxr://" + s.k + "/" + encodeURIComponent(s.id) + "/{z}/{x}/{y}" : upURL(s.k, s.id, "{z}", "{x}", "{y}");
          var src = { type: "raster", tiles: [t], tileSize: s.ts, maxzoom: s.mz, attribution: "" }; if (s.b) src.bounds = s.b;
          map.addSource(sid, src);
          map.addLayer({ id: sid, type: "raster", source: sid, paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 0, delay: 0 }, "raster-fade-duration": 0, "raster-resampling": "linear" } }, BEFORE);
        }
        OPF[sid] = s.cl ? "cl" : "";
        RLIVE[id].push(sid);
      });
    }
    return id;
  }
  function rLoaded(i) {
    var f = FRAMES[i]; if (!f) return true; var id = rEnsure(f);
    return RLIVE[id].every(function (s) { try { return map.isSourceLoaded(s); } catch (e) { return false; } });
  }
  function rOp(id, v, ms) { (RLIVE[id] || []).forEach(function (s) { if (!map.getLayer(s)) return; var o = OPF[s] === "cl" ? (LAYS.clouds ? (v ? 1 : 0) : 0) : v; map.setPaintProperty(s, "raster-opacity-transition", { duration: ms, delay: 0 }); map.setPaintProperty(s, "raster-opacity", o); }); }
  var rTok = 0;
  function rShow(i, instant) {
    var f = FRAMES[i]; if (!f) return; var id = rEnsure(f), tok = ++rTok, t0 = Date.now();
    for (var k = -1; k <= 4; k++) if (FRAMES[i + k]) rEnsure(FRAMES[i + k]);
    (function swap() {
      if (tok !== rTok || MODE !== "radar") return;
      if (!rLoaded(i) && RCUR && Date.now() - t0 < 2500) { setTimeout(swap, 40); return; }   /* keep the last frame up until the next is decoded: no blank flash */
      var ms = instant || reduce ? 0 : 180;
      if (RCUR && RCUR !== id) rOp(RCUR, 0, instant ? 0 : 260);
      rOp(id, ROP, ms); RCUR = id; rPrune(i);
    })();
  }
  function rPrune(i) {
    var keep = {};   /* (layer ids carry the frame time) */ for (var k = -3; k <= 6; k++) if (FRAMES[i + k]) keep[rId(FRAMES[i + k])] = 1;
    Object.keys(RLIVE).forEach(function (x) { if (!keep[x] && x !== RCUR) { RLIVE[x].forEach(function (s) { if (map.getLayer(s)) map.removeLayer(s); if (map.getSource(s)) map.removeSource(s); delete OPF[s]; }); delete RLIVE[x]; } });
  }
  function rHideAll() { rTok++; Object.keys(RLIVE).forEach(function (x) { rOp(x, 0, 250); }); RCUR = null; }
  function rClear() { rTok++; Object.keys(RLIVE).forEach(function (x) { RLIVE[x].forEach(function (s) { if (map.getLayer(s)) map.removeLayer(s); if (map.getSource(s)) map.removeSource(s); }); }); RLIVE = {}; RCUR = null; }
  /* tiles in view at the zoom MapLibre will request: 256 px sources ask for round(zoom) + 1, 512 px sources for round(zoom) */
  function viewTiles(off, zmax) {
    var z = clamp(Math.round(map.getZoom()) + off, 0, zmax), n = Math.pow(2, z), b = map.getBounds();
    var w = b.getWest(), e = b.getEast(), no = clamp(b.getNorth(), -85, 85), so = clamp(b.getSouth(), -85, 85);
    function tx(lon) { return Math.floor((lon + 180) / 360 * n); }
    function ty(lat) { var r = lat * Math.PI / 180; return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n); }
    var x0 = tx(w), x1 = tx(e), y0 = clamp(ty(no), 0, n - 1), y1 = clamp(ty(so), 0, n - 1), out = [], seen = {};
    if (x1 - x0 > n) { x0 = 0; x1 = n - 1; }
    for (var x = x0; x <= x1; x++) for (var y = y0; y <= y1; y++) { var xx = ((x % n) + n) % n, k = xx + "/" + y; if (seen[k]) continue; seen[k] = 1; out.push([z, xx, y]); }
    return out;
  }
  function tileBox(t) { var n = Math.pow(2, t[0]); function lat(y) { var a = Math.PI - 2 * Math.PI * y / n; return 180 / Math.PI * Math.atan(0.5 * (Math.exp(a) - Math.exp(-a))); }
    return [t[1] / n * 360 - 180, lat(t[2] + 1), (t[1] + 1) / n * 360 - 180, lat(t[2])]; }
  function hits4(a, b) { return !(a[2] < b[0] || a[0] > b[2] || a[3] < b[1] || a[1] > b[3]); }
  function inside4(a, b) { return a[0] >= b[0] && a[2] <= b[2] && a[1] >= b[1] && a[3] <= b[3]; }
  var PF = { urls: [], frames: [] };
  function frameURLs(f, T) {
    var out = [];
    rSrcs(f).forEach(function (s) {
      if (s.k === "g") return;   /* worldwide model tiles are drawn locally from the GFS grid (ready as soon as it has loaded) */
      (s.ts === 512 ? T.s : s.k === "i" ? T.i : T.n).forEach(function (t) { var bx = tileBox(t);
        if (s.b && !hits4(bx, s.b)) return;
        if (s.ex && inside4(bx, NOAA_B)) return;
        out.push(upURL(s.k, s.id, t[0], t[1], t[2])); });
    });
    return out;
  }
  function prefetch() {
    if (!PROTO || !map || !ready || MODE !== "radar" || !FRAMES.length || !FR) return;
    var tiles = { n: viewTiles(1, RMZ).slice(0, 80), s: viewTiles(0, SMZ).slice(0, 40), i: viewTiles(1, IMZ).slice(0, 60) };
    Q.forEach(function (it) { if (it.prio >= 0) it.prio += 1000; });   /* demote whatever the old view still had queued (never what the map is asking for right now) */
    var order = [], seen = {};
    function add(i) { if (i >= 0 && i < FRAMES.length && !seen[i]) { seen[i] = 1; order.push(i); } }
    for (var d = 0; d <= 6; d++) { add(IDX - d); if (d <= 2) add(IDX + d); }   /* the last hour first: that is what the loader waits for */
    for (var i = 0; i < FRAMES.length; i++) add(i);   /* then oldest first, so Play from the start never waits */
    PF = { frames: [] };
    order.forEach(function (i, n) {
      var us = frameURLs(FRAMES[i], tiles); PF.frames[i] = us;
      us.forEach(function (u) { bytes(u, n); });
    });
    trim(); bufTick();
  }
  function frameBuffered(i) { var us = PF.frames && PF.frames[i]; if (!us) return !PROTO; for (var k = 0; k < us.length; k++) { var h = BYTES.get(us[k]); if (!h || !h.done) return false; } return true; }
  var bufT = 0;
  function bufTick() {
    if (bufT) return; bufT = setTimeout(function () { bufT = 0; bufPaint(); }, 120);
  }
  function bufPaint() {
    var n = FRAMES.length, el = $("wx_buf"); if (!n || !el) return;
    var ready_ = [], cnt = 0, past = 0, pastOk = 0;
    for (var i = 0; i < n; i++) { var ok = MODE === "radar" ? frameBuffered(i) : !!mReadyK(i); ready_.push(ok); if (ok) cnt++; if (i <= NOWI && i >= NOWI - 6) { past++; if (ok) pastOk++; } }
    var stops = [], w = 100 / n;
    for (var j = 0; j < n; j++) { var c = ready_[j] ? "rgba(240,240,250,.28)" : "rgba(240,240,250,0)"; stops.push(c + " " + (j * w).toFixed(2) + "%", c + " " + ((j + 1) * w).toFixed(2) + "%"); }
    el.style.background = "linear-gradient(90deg," + stops.join(",") + ")";
    BUF = cnt / n; $("wx_play").style.setProperty("--buf", (BUF * 100).toFixed(1) + "%"); $("wx_play").classList.toggle("buf", BUF < 0.999);
    if (MODE === "radar" && !ldDone) {
      LD.need = Math.max(1, past); LD.have = pastOk; ldRow("radar", cnt + " / " + n, pastOk >= past);
      ldUpdate();
    }
  }
  var BUF = 0;

  /* ---------- model fields (temperature / rain / snow): a 4-degree world grid with a 1.5-degree U.S. grid blended on top. Every frame
     is rendered ahead of time in the worker (bicubic, smooth colour ramp) and held as a decoded bitmap, then shown as a map image layer. ---------- */
  var GD = { us: null, world: null }, GERR = { us: null, world: null }, GOPT = { us: { w: 420, fade: 2.2 }, world: { w: 560, fade: 1.2 } };
  var MB = new Map(), MLIVE = {}, MCUR = null, GOP = 0.9, GBEFORE = "water", mGen = 0, mQ = [], mBusy = 0;
  function my(lat) { return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)); }
  function expand(gk, d) {
    var nx = d.nx, ny = d.ny, N = nx * ny, nt = d.times.length, cells = d.cells, np = cells ? cells.length : N;
    var T = new Float32Array(nt * N).fill(NaN), P = new Float32Array(nt * N).fill(NaN), S = new Float32Array(nt * N).fill(NaN);
    for (var k = 0; k < nt; k++) for (var p = 0; p < np; p++) {
      var si = k * np + p, di = k * N + (cells ? cells[p] : p), a = d.temp[si], b = d.precip[si], c = d.snow[si];
      if (a != null) T[di] = a; if (b != null) P[di] = b; if (c != null) S[di] = c;
    }
    var g = { nx: nx, ny: ny, lat0: d.lat0, lon0: d.lon0, step: d.step, wrap: !!d.wrap, nt: nt, N: N, temp: T, precip: P, snow: S };
    g.times = d.times.map(tms); g.tix = new Map(); g.times.forEach(function (t, k) { g.tix.set(t, k); });
    g.s = d.lat0; g.n = d.lat0 + (ny - 1) * d.step; g.lw = d.wrap ? -180 : d.lon0; g.le = d.wrap ? 180 : d.lon0 + (nx - 1) * d.step;
    g.W = GOPT[gk].w; g.H = Math.round(g.W * (my(g.n) - my(g.s)) / ((g.le - g.lw) * Math.PI / 180));
    g.co = [[g.lw, g.n], [g.le, g.n], [g.le, g.s], [g.lw, g.s]]; g.gen = d.generated;
    return g;
  }
  /* point sampling on the main thread (hover values, city labels): same maths as the worker */
  var FC = {};
  function fieldOf(gk, mode, k) {
    var key = gk + mode + k; if (FC.key === key) return FC.F;
    var g = GD[gk], N = g.N, F = new Float32Array(N), j, q, b = k * N;
    if (mode === "temp") for (j = 0; j < N; j++) F[j] = g.temp[b + j];
    else if (mode === "rain") for (j = 0; j < N; j++) F[j] = g.precip[b + j] / 254;
    else for (j = 0; j < N; j++) { var s = 0, ok = false; for (q = Math.max(0, k - 7); q <= k; q++) { var v = g.snow[q * N + j]; if (v === v) { s += v; ok = true; } } F[j] = ok ? s / 25.4 : NaN; }
    if (mode !== "temp") F = blurF(g, F);
    FC = { key: key, F: F }; return F;
  }
  function blurF(g, F) {   /* NaN-aware 3x3 [1 2 1] pass: rain and snow cells read as soft weather shapes, not grid squares */
    var nx = g.nx, ny = g.ny, out = new Float32Array(F.length);
    for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) {
      var c = F[j * nx + i]; if (c !== c) { out[j * nx + i] = NaN; continue; }
      var s = 0, w = 0;
      for (var dj = -1; dj <= 1; dj++) { var jj = j + dj; if (jj < 0 || jj >= ny) continue;
        for (var di = -1; di <= 1; di++) { var ii = i + di; if (g.wrap) ii = (ii + nx) % nx; else if (ii < 0 || ii >= nx) continue;
          var v = F[jj * nx + ii]; if (v !== v) continue; var k = (di ? 1 : 2) * (dj ? 1 : 2); s += v * k; w += k; } }
      out[j * nx + i] = s / w;
    }
    return out;
  }
  function cr(p0, p1, p2, p3, t) { return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0))); }
  function gAt(g, F, i, j) { j = clamp(j, 0, g.ny - 1); if (g.wrap) i = ((i % g.nx) + g.nx) % g.nx; else i = clamp(i, 0, g.nx - 1); return F[j * g.nx + i]; }
  function gBil(g, F, gx, gy) {
    var x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0, v = [gAt(g, F, x0, y0), gAt(g, F, x0 + 1, y0), gAt(g, F, x0, y0 + 1), gAt(g, F, x0 + 1, y0 + 1)], w = [(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy], s = 0, ws = 0;
    for (var i = 0; i < 4; i++) if (v[i] === v[i]) { s += v[i] * (w[i] + 1e-3); ws += w[i] + 1e-3; }
    return ws ? s / ws : NaN;
  }
  function gSm(g, F, gx, gy) {
    if (gy < 0 || gy > g.ny - 1 || (!g.wrap && (gx < 0 || gx > g.nx - 1))) return NaN;
    var x1 = Math.floor(gx), y1 = Math.floor(gy), fx = gx - x1, fy = gy - y1, r = [];
    for (var j = -1; j <= 2; j++) { var a = gAt(g, F, x1 - 1, y1 + j), b = gAt(g, F, x1, y1 + j), c = gAt(g, F, x1 + 1, y1 + j), d = gAt(g, F, x1 + 2, y1 + j);
      if (a !== a || b !== b || c !== c || d !== d) return gBil(g, F, gx, gy); r.push(cr(a, b, c, d, fx)); }
    return cr(r[0], r[1], r[2], r[3], fy);
  }
  function gPart(gk, lng, lat, t) {
    var g = GD[gk]; if (!g) return null; var k = g.tix.get(t); if (k == null) return null;
    var gx = (lng - g.lon0) / g.step, gy = (lat - g.lat0) / g.step, v = gSm(g, fieldOf(gk, MODE, k), gx, gy); if (v !== v) return null;
    var e = g.wrap ? Math.min(gy, g.ny - 1 - gy) : Math.min(gx, g.nx - 1 - gx, gy, g.ny - 1 - gy), w = clamp(e / GOPT[gk].fade, 0, 1);
    return { v: v, w: w * w * (3 - 2 * w) };
  }
  function gValueAt(lng, lat, t) {
    lng = ((lng + 540) % 360) - 180;
    var u = gPart("us", lng, lat, t), w = gPart("world", lng, lat, t), v;
    if (u && w) v = u.v * u.w + w.v * (1 - u.w); else if (u) v = u.v; else if (w) v = w.v; else return NaN;
    return MODE === "temp" ? v : Math.max(0, v);
  }
  /* rendering queue: current frame first, then forward from it; a mode switch cancels the rest */
  function mKey(gk, mode, t) { return gk + "|" + mode + "|" + t; }
  function mNeed(f) { var a = []; ["world", "us"].forEach(function (gk) { if (GD[gk] && GD[gk].tix.has(f.t)) a.push(gk); }); return a; }
  function mReadyK(i) { var f = FRAMES[i]; if (!f) return false; return mNeed(f).every(function (gk) { return MB.has(mKey(gk, MODE, f.t)); }); }
  function mRender(gk, mode, t) {
    var key = mKey(gk, mode, t), g = GD[gk]; if (MB.has(key)) return Promise.resolve(MB.get(key));
    return wkCall({ op: "field", g: gk + ":" + g.gen, mode: mode, k: g.tix.get(t), pal: PAL[mode], w: g.W, h: g.H, lw: g.lw, le: g.le, s: g.s, n: g.n, fade: GOPT[gk].fade })
      .then(function (r) { if (r.bmp) { if (mode === MODE) MB.set(key, r.bmp); else r.bmp.close(); } return r.bmp; });
  }
  function mPreload() {
    if (!WK || MODE === "radar" || !FRAMES.length) return;
    var gen = ++mGen, order = [];
    for (var i = IDX; i < FRAMES.length; i++) order.push(i);
    for (i = 0; i < IDX; i++) order.push(i);
    mQ = []; order.forEach(function (i) { mNeed(FRAMES[i]).forEach(function (gk) { if (!MB.has(mKey(gk, MODE, FRAMES[i].t))) mQ.push([gk, MODE, FRAMES[i].t, gen]); }); });
    if (!mBusy) mPump();
  }
  function mPump() {
    var it = mQ.shift(); if (!it) { mBusy = 0; return; }
    if (it[3] !== mGen || it[1] !== MODE) { mPump(); return; }
    mBusy = 1; mRender(it[0], it[1], it[2]).then(function () { bufTick(); mPump(); }, function () { mPump(); });
  }
  function mFree(keepMode) { MB.forEach(function (b, k) { if (k.split("|")[1] !== keepMode) { try { b.close(); } catch (e) {} MB.delete(k); } }); }
  /* ---------- worldwide GFS forecast (rain rate + cloud cover, every 3 hours to 7 days): two small PNG atlases from /api/wxmap/gfs,
     decoded once in the worker; map tiles are then drawn locally (bicubic, radar palette), so they are sharp at every zoom and need no download. ---------- */
  var GFSR = null, GFSM = null, GTAG = "", gfsLoading = null;
  function gfsTimes() { return GFSR && GFSM ? GFSM.times.map(tms) : []; }
  function loadGfs() {
    var g = FR && FR.gfs; if (!g || !WK || GFSR === g.run || gfsLoading === g.run) return;
    gfsLoading = g.run;
    function bin(f) { return fetch("/api/wxmap/gfs?f=" + f + "&r=" + encodeURIComponent(g.run), { credentials: "omit" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.arrayBuffer(); }); }
    Promise.all([bin("p"), bin("c")]).then(function (b) { return poolAll(function () { var p = b[0].slice(0), c = b[1].slice(0); return { msg: { op: "gfs", p: p, c: c, meta: g }, tr: [p, c] }; }); }).then(function () {
      GFSR = g.run; GFSM = g; GTAG = g.run.replace(/\D/g, "").slice(0, 10); gfsLoading = null;
      srcSet("gfs", "Worldwide forecast · NOAA GFS", true, "Rain and clouds every 3 hours to 7 days (run " + stamp(tms(g.run)) + ")");
      if (MODE === "radar") { var t = FRAMES[IDX] ? FRAMES[IDX].t : null; buildFrames(live ? null : t); }
    }, function (e) { gfsLoading = null; srcSet("gfs", "Worldwide forecast · NOAA GFS", false, "Unavailable: " + (e && e.message || "the model data did not load")); });
  }
  function protoG(params) {
    var m = /^wxg:\/\/(\w+)\/(\w+)\/(\d+)/.exec(params.url);
    if (!m || !GD[m[1]]) return Promise.resolve({ data: blank() });
    var gk = m[1], mode = m[2], t = +m[3], key = mKey(gk, mode, t), b = MB.get(key);
    return (b ? Promise.resolve(b) : mRender(gk, mode, t)).then(function (bmp) { return bmp ? createImageBitmap(bmp).then(function (c) { return { data: c }; }) : { data: blank() }; });
  }
  function mEnsure(f) {
    var id = "m-" + MODE + "-" + f.t;
    if (!MLIVE[id]) {
      MLIVE[id] = [];
      mNeed(f).forEach(function (gk) {
        var sid = id + gk, g = GD[gk];
        if (!map.getSource(sid)) {
          map.addSource(sid, { type: "image", url: "wxg://" + gk + "/" + MODE + "/" + f.t, coordinates: g.co });
          map.addLayer({ id: sid, type: "raster", source: sid, paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 0, delay: 0 }, "raster-fade-duration": 0, "raster-resampling": "linear" } }, GBEFORE);
        }
        MLIVE[id].push(sid);
      });
    }
    return id;
  }
  function mLoaded(i) { var f = FRAMES[i]; if (!f) return true; var id = mEnsure(f); return MLIVE[id].every(function (s) { try { return map.isSourceLoaded(s); } catch (e) { return false; } }); }
  function mOp(id, v, ms) { (MLIVE[id] || []).forEach(function (s) { if (!map.getLayer(s)) return; map.setPaintProperty(s, "raster-opacity-transition", { duration: ms, delay: 0 }); map.setPaintProperty(s, "raster-opacity", v); }); }
  var mTok = 0;
  function gShow(i, instant) {
    var f = FRAMES[i]; if (!f || !WK) return; var id = mEnsure(f), tok = ++mTok, t0 = Date.now();
    for (var k = -2; k <= 6; k++) if (FRAMES[i + k]) mEnsure(FRAMES[i + k]);
    if (map.getSource("gv")) map.getSource("gv").setData(LAYS.labels ? gLabels(f.t) : EMPTY);
    (function swap() {
      if (tok !== mTok || MODE === "radar") return;
      if (!mLoaded(i) && MCUR && Date.now() - t0 < 3000) { setTimeout(swap, 30); return; }
      if (MCUR && MCUR !== id) mOp(MCUR, 0, instant ? 0 : 240);
      mOp(id, GOP, instant || reduce ? 0 : 160); MCUR = id; mPrune(i);
    })();
  }
  function mPrune(i) {
    var keep = {}; for (var k = -6; k <= 10; k++) if (FRAMES[i + k]) keep["m-" + MODE + "-" + FRAMES[i + k].t] = 1;
    Object.keys(MLIVE).forEach(function (x) { if (!keep[x] && x !== MCUR) { MLIVE[x].forEach(function (s) { if (map.getLayer(s)) map.removeLayer(s); if (map.getSource(s)) map.removeSource(s); }); delete MLIVE[x]; } });
  }
  function gHide() { mTok++; Object.keys(MLIVE).forEach(function (x) { MLIVE[x].forEach(function (s) { if (map.getLayer(s)) map.removeLayer(s); if (map.getSource(s)) map.removeSource(s); }); }); MLIVE = {}; MCUR = null; if (map.getSource("gv")) map.getSource("gv").setData(EMPTY); }

  /* values shown at major cities (the base map already names them; the value sits just under the name) */
  var CITIES = [[-122.33, 47.61], [-122.68, 45.52], [-122.42, 37.77], [-121.49, 38.58], [-118.24, 34.05], [-117.16, 32.72], [-119.79, 36.74], [-115.14, 36.17], [-112.07, 33.45], [-110.97, 32.22],
    [-111.89, 40.76], [-116.2, 43.62], [-108.5, 45.78], [-106.65, 35.08], [-104.99, 39.74], [-104.82, 41.14], [-100.78, 46.81], [-96.73, 43.55], [-96.0, 41.26], [-97.52, 35.47], [-97.33, 37.69],
    [-96.8, 32.78], [-95.37, 29.76], [-98.49, 29.42], [-101.85, 33.58], [-106.49, 31.76], [-93.27, 44.98], [-94.58, 39.1], [-90.2, 38.63], [-87.63, 41.88], [-87.91, 43.04], [-93.61, 41.59],
    [-90.07, 29.95], [-90.05, 35.15], [-86.78, 36.16], [-86.8, 33.52], [-84.39, 33.75], [-81.66, 30.33], [-81.38, 28.54], [-82.46, 27.95], [-80.19, 25.76], [-81.69, 41.5], [-83.05, 42.33],
    [-84.51, 39.1], [-86.16, 39.77], [-85.76, 38.25], [-80.84, 35.23], [-78.64, 35.78], [-79.94, 32.78], [-77.44, 37.54], [-77.04, 38.91], [-76.61, 39.29], [-75.17, 39.95], [-74.01, 40.71],
    [-79.99, 40.44], [-78.88, 42.89], [-73.76, 42.65], [-71.06, 42.36], [-72.68, 41.76], [-70.26, 43.66], [-73.21, 44.48], [-92.29, 34.75], [-89.4, 43.07], [-84.55, 42.73], [-100.35, 44.37],
    /* worldwide */
    [-79.38, 43.65], [-73.57, 45.5], [-123.12, 49.28], [-114.07, 51.05], [-149.9, 61.22], [-157.86, 21.31], [-99.13, 19.43], [-103.35, 20.67], [-100.31, 25.69], [-90.51, 14.64], [-79.52, 8.98],
    [-74.07, 4.71], [-66.9, 10.48], [-77.04, -12.05], [-78.47, -0.18], [-70.67, -33.45], [-58.38, -34.6], [-56.16, -34.9], [-46.63, -23.55], [-43.17, -22.91], [-47.88, -15.79], [-38.5, -12.97], [-60.02, -3.12],
    [-0.13, 51.51], [-6.26, 53.35], [-3.19, 55.95], [2.35, 48.86], [4.9, 52.37], [4.35, 50.85], [13.4, 52.52], [11.58, 48.14], [8.68, 50.11], [16.37, 48.21], [14.42, 50.08], [21.01, 52.23], [19.04, 47.5],
    [12.5, 41.9], [9.19, 45.46], [-3.7, 40.42], [2.17, 41.39], [-9.14, 38.72], [23.73, 37.98], [28.98, 41.01], [32.85, 39.93], [26.1, 44.43], [30.52, 50.45], [37.62, 55.76], [30.32, 59.94], [18.07, 59.33],
    [10.75, 59.91], [12.57, 55.68], [24.94, 60.17], [-21.9, 64.15], [31.24, 30.04], [3.06, 36.75], [-7.59, 33.57], [3.38, 6.52], [7.49, 9.06], [-0.19, 5.6], [-17.45, 14.69], [36.82, -1.29], [38.75, 9.03],
    [32.58, 0.35], [39.27, -6.79], [28.05, -26.2], [18.42, -33.92], [31.03, -29.86], [15.27, -4.44], [13.23, -8.84], [47.52, -18.91], [32.53, 15.5], [46.68, 24.71], [55.27, 25.2], [51.53, 25.29],
    [51.39, 35.69], [44.37, 33.31], [35.21, 31.77], [35.5, 33.89], [69.17, 34.53], [67.01, 24.86], [74.34, 31.55], [77.21, 28.61], [72.88, 19.08], [77.59, 12.97], [80.27, 13.08], [88.36, 22.57], [90.41, 23.81],
    [85.32, 27.72], [79.86, 6.93], [96.16, 16.84], [100.5, 13.76], [105.85, 21.03], [106.7, 10.78], [101.69, 3.14], [103.82, 1.35], [106.85, -6.21], [112.75, -7.25], [120.98, 14.6], [116.4, 39.9],
    [121.47, 31.23], [113.26, 23.13], [114.17, 22.32], [104.07, 30.67], [108.94, 34.34], [126.98, 37.57], [129.08, 35.18], [139.69, 35.69], [135.5, 34.69], [141.35, 43.06], [121.56, 25.03], [87.62, 43.83],
    [76.95, 43.24], [69.24, 41.3], [71.43, 51.13], [82.92, 55.03], [104.3, 52.29], [131.89, 43.12], [106.92, 47.92], [151.21, -33.87], [144.96, -37.81], [153.03, -27.47], [115.86, -31.95], [138.6, -34.93],
    [130.84, -12.46], [174.76, -36.85], [172.64, -43.53], [147.18, -9.44], [178.44, -18.14]];
  function gLabels(t) {
    var f = [];
    CITIES.forEach(function (c) {
      var v = gValueAt(c[0], c[1], t); if (isNaN(v)) return;
      var s = MODE === "temp" ? Math.round(v) + "°" : MODE === "rain" ? (v >= 0.01 ? (v >= 1 ? v.toFixed(1) : v.toFixed(2).replace(/^0/, "")) + '"' : "") : (v >= 0.1 ? (v >= 10 ? Math.round(v) : v.toFixed(1)) + '"' : "");
      if (s) f.push({ type: "Feature", geometry: { type: "Point", coordinates: c }, properties: { v: s, s: -v } });
    });
    return { type: "FeatureCollection", features: f };
  }

  /* ---------- legend ---------- */
  function legend() {
    var h;
    var fc = FRAMES[IDX] && FRAMES[IDX].kind === "fc" && FRAMES[IDX].layer;   /* HRRR keeps its own rain / snow / mix colours; GFS uses the radar scale */
    if (MODE === "radar" && FRAMES[IDX] && FRAMES[IDX].kind === "fc" && !fc) h = '<span class="u">Model</span><span>Light</span><span class="bar" style="background:' + RADAR_GRAD + '"></span><span>Heavy</span>';
    else if (MODE === "radar" && fc) h = '<span class="u">Forecast</span><span>Rain</span><span class="bar sm" style="background:linear-gradient(90deg,#d6efd0,#73c476,#228a44,#006c2c)"></span><span>Snow</span><span class="bar sm" style="background:linear-gradient(90deg,#81c0d5,#1b8db3,#003f7f)"></span><span>Mix</span><span class="bar sm" style="background:linear-gradient(90deg,#e6e5f1,#7e79b8)"></span>';
    else if (MODE === "radar") h = '<span class="u">Radar</span><span>Light</span><span class="bar" style="background:' + RADAR_GRAD + '"></span><span>Heavy</span>';
    else if (MODE === "temp") h = '<span class="u">°F</span><span>0</span><span class="bar" style="background:' + grad(PAL.temp, -20, 112) + '"></span><span>100+</span>';
    else if (MODE === "rain") h = '<span class="u">Rain</span><span>.02"</span><span class="bar" style="background:' + grad(PAL.rain, 0.02, 2) + '"></span><span>2"+ / 3 h</span>';
    else h = '<span class="u">Snow</span><span>.3"</span><span class="bar" style="background:' + grad(PAL.snow, 0.3, 24) + '"></span><span>24"+ / 24 h</span>';
    $("wx_leg").innerHTML = h;
  }

  /* ---------- mode switch ---------- */
  function setMode(m, keep) {
    if (m === MODE && keep !== false && FRAMES.length) return;
    var t = FRAMES[IDX] ? FRAMES[IDX].t : null;
    MODE = m; mGen++; mQ = []; mFree(m);
    [].forEach.call(document.querySelectorAll("#wx_modes button"), function (b) { b.setAttribute("aria-pressed", b.dataset.m === m ? "true" : "false"); });
    if (map && ready) { gHide(); if (m !== "radar") rHideAll(); setLayerVis(); }
    legFc = null; hideCard(true);
    buildFrames(t); legend();
  }
  $("wx_modes").addEventListener("click", function (e) { var b = e.target.closest("button[data-m]"); if (b && !b.disabled) { stop(); setMode(b.dataset.m); } });

  /* ---------- play ---------- */
  var playT = null;
  function frameReady(i) { return MODE === "radar" ? frameBuffered(i) && rLoaded(i) : mReadyK(i) && mLoaded(i); }
  function play() {
    if (!FRAMES.length) return; playing = true; $("wx_play").classList.add("on"); $("wx_play").setAttribute("aria-label", "Pause");
    if (IDX >= FRAMES.length - 1) go(0);
    tick();
  }
  function stop() { playing = false; clearTimeout(playT); $("wx_play").classList.remove("on"); $("wx_play").setAttribute("aria-label", "Play"); }
  function tick() {
    clearTimeout(playT); if (!playing) return;
    var n = IDX + 1, wait = MODE === "radar" ? (FRAMES[IDX] && FRAMES[IDX].kind === "fc" ? 520 : 380) : 650;
    if (n >= FRAMES.length) { playT = setTimeout(function () { if (playing) { go(0); tick(); } }, 1400); return; }
    if (IDX === NOWI) wait = 1200;   // a beat on "now"
    var t0 = Date.now();
    playT = setTimeout(function w() {
      if (!playing) return;
      if (frameReady(n) || Date.now() - t0 > 9000 + wait) { go(n); tick(); }
      else playT = setTimeout(w, 90);
    }, wait);
  }
  $("wx_play").addEventListener("click", function () { if (playing) stop(); else play(); });
  $("wx_range").addEventListener("input", function (e) { stop(); go(+e.target.value); });
  document.addEventListener("keydown", function (e) {
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && e.target.id !== "wx_range") return;
    if (e.key === " " && e.target.id !== "wx_range") { e.preventDefault(); if (playing) stop(); else play(); }
    if (e.key === "Escape") { if (pinned) hideCard(true); else closeLays(); }
  });

  /* ---------- overlays ---------- */
  var EMPTY = { type: "FeatureCollection", features: [] };
  function addOverlayLayers() {
    map.addSource("ol", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "ol-fill", type: "fill", source: "ol", paint: { "fill-color": match("cat", OLC, "#7C8190"), "fill-opacity": 0.13 } }, "lbl-country");
    map.addLayer({ id: "ol-line", type: "line", source: "ol", paint: { "line-color": match("cat", OLC, "#7C8190"), "line-width": 1.4, "line-opacity": 0.85 } }, "lbl-country");
    map.addSource("warn", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "warn-fill", type: "fill", source: "warn", paint: { "fill-color": match("g", WC, "#7C8190"), "fill-opacity": ["case", ["get", "watch"], 0.06, 0.2] } }, "lbl-country");
    map.addLayer({ id: "watch-line", type: "line", source: "warn", filter: ["==", ["get", "watch"], true], paint: { "line-color": match("g", WC, "#7C8190"), "line-width": 1.3, "line-dasharray": [2, 2], "line-opacity": 0.85 } }, "lbl-country");
    map.addLayer({ id: "warn-glow", type: "line", source: "warn", filter: ["all", ["==", ["get", "watch"], false], ["==", ["get", "g"], "tor"]], paint: { "line-color": WC.tor, "line-width": 7, "line-blur": 5, "line-opacity": 0.55 } }, "lbl-country");
    map.addLayer({ id: "warn-line", type: "line", source: "warn", filter: ["==", ["get", "watch"], false], paint: { "line-color": match("g", WC, "#7C8190"), "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.2, 8, 2.2] } }, "lbl-country");
    map.addSource("season", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "season-line", type: "line", source: "season", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": match("cat", TCC, "#7C8190"), "line-width": ["interpolate", ["linear"], ["zoom"], 1, 1, 6, 2.6], "line-opacity": 0.7 } });
    map.addLayer({ id: "season-lbl", type: "symbol", source: "season", minzoom: 2.5, layout: { "symbol-placement": "line", "text-field": ["get", "name"], "text-font": F, "text-size": 10, "text-letter-spacing": 0.1, "symbol-spacing": 400 },
      paint: { "text-color": "rgba(240,240,250,.7)", "text-halo-color": "rgba(5,6,10,.9)", "text-halo-width": 1.2 } });
    map.addSource("nhc", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "nhc-cone", type: "fill", source: "nhc", filter: ["==", ["get", "kind"], "cone"], paint: { "fill-color": "#F0F0FA", "fill-opacity": 0.1 } });
    map.addLayer({ id: "nhc-cone-l", type: "line", source: "nhc", filter: ["==", ["get", "kind"], "cone"], paint: { "line-color": "#F0F0FA", "line-width": 1.2, "line-opacity": 0.6 } });
    map.addLayer({ id: "nhc-track", type: "line", source: "nhc", filter: ["in", ["get", "kind"], ["literal", ["track", "past"]]], paint: { "line-color": WC.trop, "line-width": 2.2, "line-dasharray": [2, 1.5] } });
    map.addLayer({ id: "nhc-pt", type: "circle", source: "nhc", filter: ["==", ["get", "kind"], "point"], paint: { "circle-color": WC.trop, "circle-radius": 5, "circle-stroke-color": "#05060a", "circle-stroke-width": 1.5 } });
    map.addSource("gd", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "gd-halo", type: "circle", source: "gd", paint: { "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": match("alert", GDC, "#7C8190"), "circle-stroke-width": 1.2, "circle-stroke-opacity": 0.55,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 7, 6, 13] } });
    map.addLayer({ id: "gd", type: "circle", source: "gd", paint: { "circle-color": match("alert", GDC, "#7C8190"), "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3, 6, 5.5], "circle-stroke-color": "#05060a", "circle-stroke-width": 1.2 } });
    map.addLayer({ id: "gd-lbl", type: "symbol", source: "gd", minzoom: 2.2, layout: { "text-field": ["get", "short"], "text-font": FB, "text-size": 9.5, "text-letter-spacing": 0.12, "text-transform": "uppercase", "text-offset": [0, 1.2], "text-anchor": "top", "text-optional": true },
      paint: { "text-color": "rgba(240,240,250,.75)", "text-halo-color": "rgba(5,6,10,.9)", "text-halo-width": 1.2 } });
    map.addSource("tracks", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "trk-glow", type: "line", source: "tracks", layout: { "line-cap": "round" }, paint: { "line-color": ["match", ["get", "n"], 0, EFC[0], 1, EFC[1], 2, EFC[2], 3, EFC[3], 4, EFC[4], 5, EFC[5], "#7C8190"], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 5, 10, 14], "line-blur": 4, "line-opacity": 0.35 } });
    map.addLayer({ id: "trk", type: "line", source: "tracks", layout: { "line-cap": "round" }, paint: { "line-color": ["match", ["get", "n"], 0, EFC[0], 1, EFC[1], 2, EFC[2], 3, EFC[3], 4, EFC[4], 5, EFC[5], "#7C8190"], "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["+", 1.2, ["*", 0.4, ["max", ["get", "n"], 0]]], 10, ["+", 3, ["max", ["get", "n"], 0]]] } });
    map.addLayer({ id: "trk-hit", type: "line", source: "tracks", paint: { "line-color": "#000", "line-opacity": 0, "line-width": 16 } });
    map.addSource("rep", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "rep", type: "circle", source: "rep", paint: { "circle-color": match("k", RC, "#7C8190"), "circle-opacity": 0.95, "circle-stroke-color": "#05060a", "circle-stroke-width": 1.2,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, ["match", ["get", "k"], "tor", 4.5, "snow", 1.8, 3], 9, ["match", ["get", "k"], "tor", 8, "snow", 5, 6]] } });
    map.addLayer({ id: "rep-lbl", type: "symbol", source: "rep", minzoom: 4.5, filter: ["==", ["get", "k"], "snow"], layout: { "text-field": ["concat", ["to-string", ["get", "mag"]], "\""], "text-font": FB, "text-size": 10.5, "text-offset": [0, 1.1], "text-anchor": "top" },
      paint: { "text-color": "#F0F0FA", "text-halo-color": "rgba(5,6,10,.95)", "text-halo-width": 1.4 } });
    map.addSource("gv", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "gv", type: "symbol", source: "gv", layout: { "text-field": ["get", "v"], "text-font": FB, "text-size": ["interpolate", ["linear"], ["zoom"], 2, 9.5, 5, 12, 8, 14], "text-padding": 2, "text-anchor": "top", "text-offset": [0, 0.15], "text-allow-overlap": false, "symbol-sort-key": ["get", "s"] },
      paint: { "text-color": "rgba(255,255,255,.92)", "text-halo-color": "rgba(5,6,10,.85)", "text-halo-width": 1.3 } });
    map.addSource("me", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "me-ring", type: "circle", source: "me", paint: { "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#5AB4FF", "circle-stroke-width": 1.5, "circle-radius": 14, "circle-stroke-opacity": 0.6 } });
    map.addLayer({ id: "me", type: "circle", source: "me", paint: { "circle-color": "#5AB4FF", "circle-radius": 6, "circle-stroke-color": "#F0F0FA", "circle-stroke-width": 2 } });
    var t0 = performance.now();
    function pulse(now) { var p = ((now - t0) % 2000) / 2000; if (map.getLayer("me-ring")) { map.setPaintProperty("me-ring", "circle-radius", 8 + p * 18); map.setPaintProperty("me-ring", "circle-stroke-opacity", 0.8 * (1 - p)); } requestAnimationFrame(pulse); }
    if (!reduce) requestAnimationFrame(pulse);
  }
  var LGRP = { global: ["gd-halo", "gd", "gd-lbl"], warn: ["warn-fill", "watch-line", "warn-glow", "warn-line"], reports: ["rep", "rep-lbl"], tracks: ["trk-glow", "trk", "trk-hit"], trop: ["season-line", "season-lbl"], outlook: ["ol-fill", "ol-line"], labels: ["gv"] };
  function setLayerVis() {
    if (!map || !ready) return;
    Object.keys(LGRP).forEach(function (k) {
      var on = !!LAYS[k] && !(k === "labels" && MODE === "radar");
      LGRP[k].forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none"); });
    });
    [].forEach.call(document.querySelectorAll("[data-lay]"), function (i) { i.checked = !!LAYS[i.dataset.lay]; });
    if (MODE === "radar" && RCUR) rOp(RCUR, ROP, 150);
  }
  function timeFilters() {
    if (!map || !ready || !map.getLayer("rep")) return;
    var f = FRAMES[IDX], T = f ? Math.round(f.t / 1000) : 9e9;
    var kf = MODE === "snow" ? ["==", ["get", "k"], "snow"] : ["!=", ["get", "k"], "snow"];
    map.setFilter("rep", ["all", ["<=", ["get", "t"], T], kf]);
    map.setFilter("rep-lbl", ["all", ["<=", ["get", "t"], T], ["==", ["get", "k"], "snow"], MODE === "snow"]);
    var d = olDay(f ? f.t : Date.now());
    map.setFilter("ol-fill", ["==", ["get", "day"], d]); map.setFilter("ol-line", ["==", ["get", "day"], d]);
  }
  var OLW = {};
  function olDay(t) {
    var days = Object.keys(OLW).map(Number).sort(); if (!days.length) return 0;
    for (var i = 0; i < days.length; i++) { var w = OLW[days[i]]; if (t < w[1]) return days[i]; }
    return 0;
  }
  function loadAlerts() {
    return jget("/api/wxmap/alerts").then(function (d) {
      AL = d; if (map && map.getSource("warn")) map.getSource("warn").setData(d);
      var c = d.counts || {}, tor = (c["Tornado Warning"] || 0) + (c["Tornado Emergency"] || 0), svr = c["Severe Thunderstorm Warning"] || 0, n = d.features.length;
      var p = $("wx_pill");
      if (tor || svr) { p.hidden = false; p.className = "wx-pill" + (tor ? " tor" : ""); p.innerHTML = "<i></i>" + esc([tor ? tor + " tornado warning" + (tor > 1 ? "s" : "") : "", svr ? svr + " severe storm warning" + (svr > 1 ? "s" : "") : ""].filter(Boolean).join(" · ")); }
      else p.hidden = true;
      status("warn", n ? n + " active" + (n === 1 ? "" : "") + " · NWS" : "None active right now · NWS", true);
    }).catch(function (e) { status("warn", "Unavailable: " + (e.reason || "NWS did not answer"), false); });
  }
  function loadStorms() {
    return jget("/api/wxmap/storms").then(function (d) {
      ST = d; var s = d.status || {};
      if (d.reports && map) map.getSource("rep").setData(d.reports);
      if (d.tracks && map) map.getSource("tracks").setData(d.tracks);
      if (d.outlook && map) {
        OLW = {}; d.outlook.features.forEach(function (f) { var p = f.properties, a = tms(p.valid), b = tms(p.expire); if (a && b) OLW[p.day] = [a, b]; });
        map.getSource("ol").setData(d.outlook);
      }
      var nr = d.reports ? d.reports.features.filter(function (f) { return f.properties.k !== "snow"; }).length : 0, ns = d.reports ? d.reports.features.length - nr : 0;
      status("reports", s.reports && s.reports.ok ? nr + " severe, " + ns + " snow · last 72 h" : "Unavailable: " + ((s.reports && s.reports.reason) || "no answer"), !!(s.reports && s.reports.ok));
      status("tracks", s.tracks && s.tracks.ok ? (d.tracks.features.length + " surveyed · last 90 days") : "Unavailable: " + ((s.tracks && s.tracks.reason) || "no answer"), !!(s.tracks && s.tracks.ok));
      var no = d.outlook ? d.outlook.features.length : 0;
      status("outlook", s.outlook && s.outlook.ok ? (no ? "Day 1-3 · follows the timeline" : "No thunderstorm risk areas today") : "Unavailable: " + ((s.outlook && s.outlook.reason) || "no answer"), !!(s.outlook && s.outlook.ok));
      timeFilters();
    }).catch(function (e) { ["reports", "tracks", "outlook"].forEach(function (k) { status(k, "Unavailable: " + (e.reason || "no answer"), false); }); });
  }
  function loadTropical() {
    return jget("/api/wxmap/tropical").then(function (d) {
      TR = d;
      if (d.season && map) map.getSource("season").setData(d.season);
      nhcPaint();
      var a = d.active && d.active.active ? d.active.active.length : 0, s = d.season ? d.season.features.length : 0;
      var ok = d.season_status.ok || d.active_status.ok;
      status("trop", d.season_status.ok ? s + " storms in " + d.season.season + (a ? " · " + a + " active now (always shown)" : " · none active now") : "Unavailable: " + d.season_status.reason, !!d.season_status.ok);
    }).catch(function (e) { status("trop", "Unavailable: " + (e.reason || "no answer"), false); });
  }
  function nhcPaint() {
    if (!map || !map.getSource("nhc")) return;
    var f = [].concat(TR && TR.active && TR.active.features || [], GL && GL.cyclones && GL.cyclones.features || []);
    map.getSource("nhc").setData({ type: "FeatureCollection", features: f });
  }
  function loadGlobal() {
    return jget("/api/wxmap/global").then(function (d) {
      GL = d;
      d.events.features.forEach(function (f) { var p = f.properties; p.short = (p.et === "TC" ? (p.name || "").replace(/^Tropical Cyclone\s+/i, "").replace(/-\d+$/, "") : p.kind); });
      if (map && map.getSource("gd")) map.getSource("gd").setData(d.events);
      nhcPaint();
      var c = { TC: 0, FL: 0, DR: 0 }; d.events.features.forEach(function (f) { c[f.properties.et] = (c[f.properties.et] || 0) + 1; });
      status("global", [c.TC ? c.TC + " cyclone" + (c.TC > 1 ? "s" : "") : "", c.FL ? c.FL + " flood" + (c.FL > 1 ? "s" : "") : "", c.DR ? c.DR + " drought" + (c.DR > 1 ? "s" : "") : ""].filter(Boolean).join(", ") + (d.events.features.length ? "" : "Nothing active") + " · GDACS", true);
    }).catch(function (e) { status("global", "Unavailable: " + (e.reason || "GDACS did not answer"), false); });
  }
  function status(k, txt, ok) {
    var el = document.querySelector('[data-st="' + k + '"]'); if (el) el.textContent = txt;
    var row = document.querySelector('.wx-lay[data-k="' + k + '"]'); if (row) { row.classList.toggle("off", !ok); var i = row.querySelector("input"); if (i) i.disabled = !ok; }
  }
  /* overlay panel */
  function openLays() { document.body.classList.add("wx-lays-on"); $("wx_lays").hidden = false; $("wx_lay_btn").setAttribute("aria-expanded", "true"); hideCard(true); }
  function closeLays() { document.body.classList.remove("wx-lays-on"); $("wx_lay_btn").setAttribute("aria-expanded", "false"); setTimeout(function () { if (!document.body.classList.contains("wx-lays-on")) $("wx_lays").hidden = true; }, 250); }
  $("wx_lay_btn").addEventListener("click", function () { if (document.body.classList.contains("wx-lays-on")) closeLays(); else openLays(); });
  $("wx_lays_x").addEventListener("click", closeLays);
  $("wx_lays").addEventListener("change", function (e) {
    var k = e.target.dataset.lay; if (!k) return; LAYS[k] = e.target.checked; store("bn_wx_lays", LAYS); setLayerVis();
    if (k === "labels" && MODE !== "radar") gShow(IDX);
  });
  (function keys() {
    var w = document.querySelector('.wx-lay[data-k="warn"] .wx-lt');
    if (w) w.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + Object.keys(WL).map(function (k) { return '<span><i style="background:' + WC[k] + '"></i>' + esc(WL[k]) + '</span>'; }).join("") + '</span>');
    var gx = document.querySelector('.wx-lay[data-k="global"] .wx-lt');
    if (gx) gx.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + [["green", "Minor"], ["orange", "Moderate"], ["red", "Severe"]].map(function (x) { return '<span><i style="border-radius:50%;background:' + GDC[x[0]] + '"></i>' + x[1] + '</span>'; }).join("") + '</span>');
    var t = document.querySelector('.wx-lay[data-k="tracks"] .wx-lt');
    if (t) t.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + EFC.map(function (c, n) { return '<span><i style="background:' + c + '"></i>EF' + n + '</span>'; }).join("") + '</span>');
    var h = document.querySelector('.wx-lay[data-k="trop"] .wx-lt');
    if (h) h.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + [["0", "Storm"], ["1", "Cat 1"], ["2", "Cat 2"], ["3", "Cat 3"], ["4", "Cat 4"], ["5", "Cat 5"]].map(function (x) { return '<span><i style="background:' + TCC[x[0]] + '"></i>' + x[1] + '</span>'; }).join("") + '</span>');
    var o = document.querySelector('.wx-lay[data-k="outlook"] .wx-lt');
    if (o) o.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + ["MRGL", "SLGT", "ENH", "MDT", "HIGH"].map(function (k) { return '<span><i style="background:' + OLC[k] + '"></i>' + k + '</span>'; }).join("") + '</span>');
    var r = document.querySelector('.wx-lay[data-k="reports"] .wx-lt');
    if (r) r.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + [["tor", "Tornado"], ["hail", "Hail"], ["wind", "Wind"], ["flood", "Flash flood"], ["snow", "Snow"]].map(function (x) { return '<span><i style="border-radius:50%;background:' + RC[x[0]] + '"></i>' + x[1] + '</span>'; }).join("") + '</span>');
  })();
  $("wx_src").innerHTML = 'U.S. radar: NOAA MRMS via <a href="https://mesonet.agron.iastate.edu/" target="_blank" rel="noopener">Iowa Environmental Mesonet</a>; forecast radar: NOAA HRRR. Worldwide: satellite clouds from NASA GIBS (GOES-East, GOES-West, Himawari) and <a href="https://www.eumetsat.int/" target="_blank" rel="noopener">EUMETSAT</a> Meteosat (CC BY 4.0), satellite rain from NASA IMERG, forecast rain and clouds from NOAA GFS. Temperature, rain and snow: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> (CC BY 4.0). Warnings and storm reports: NWS. Tornado tracks: NWS Damage Assessment Toolkit. Cyclones: NHC, <a href="https://www.gdacs.org/" target="_blank" rel="noopener">GDACS</a> and IBTrACS (NOAA NCEI). Global alerts: GDACS (UN, European Commission). Outlooks: NOAA SPC.';

  /* ---------- cards ---------- */
  var card = $("wx_card"), pinned = null, IDXF = {};
  var CX = '<button type="button" class="wx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
  function stl(c, t) { return '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>' + esc(t) + '</span>'; }
  function featHTML(f) {
    var p = f.properties || {}, L = f.layer.id, h = "";
    if (L === "rep") {
      var c = RC[p.k] || "#7C8190", mag = p.mag != null && p.mag !== "" ? (p.k === "hail" ? p.mag + " in hail" : p.k === "wind" ? p.mag + " " + (p.unit || "mph") : p.k === "snow" ? p.mag + " in of snow" : "") : "";
      h = stl(c, "Storm report") + "<h3>" + esc(p.type) + (mag ? " · " + esc(mag) : "") + "</h3><p class=\"age\">" + esc(p.place) + " · " + esc(stamp(p.t * 1000)) + " (" + esc(rel(p.t * 1000)) + ")</p>" +
        (p.remark ? "<p>" + esc(p.remark) + "</p>" : "") + '<p class="age">NWS ' + esc(p.wfo || "") + (p.src ? " · reported by " + esc(p.src) : "") + "</p>";
    } else if (L === "trk-hit" || L === "trk") {
      var cc = EFC[p.n] || "#7C8190";
      h = stl(cc, "Tornado track · " + (p.ef || "EFU")) + "<h3>" + esc(p.name || "Tornado") + "</h3><dl><dt>Date</dt><dd>" + esc(FDATE.format(new Date(tms(p.date) || 0))) + "</dd>" +
        (p.len_mi != null ? "<dt>Path length</dt><dd>" + esc(Number(p.len_mi).toFixed(1)) + " mi</dd>" : "") + (p.width_yd ? "<dt>Max width</dt><dd>" + esc(p.width_yd) + " yd</dd>" : "") +
        (p.wind ? "<dt>Peak wind</dt><dd>" + esc(p.wind) + " mph</dd>" : "") + "<dt>Injuries · deaths</dt><dd>" + esc(p.inj || 0) + " · " + esc(p.fat || 0) + "</dd></dl><p class=\"age\">NWS damage survey · " + esc(p.wfo || "") + "</p>";
    } else if (L === "season-line" || L === "season-lbl") {
      var tc = TCC[String(p.cat)] || "#7C8190", cat = p.cat >= 1 ? "Category " + p.cat + " peak" : p.cat === 0 ? "Tropical storm peak" : "Depression";
      var BAS = { NA: "North Atlantic", EP: "Eastern Pacific", WP: "Western Pacific", NI: "North Indian", SI: "South Indian", SP: "South Pacific", SA: "South Atlantic" };
      h = stl(tc, "Storm track · " + cat) + "<h3>" + esc(p.name) + "</h3><dl><dt>Basin</dt><dd>" + esc(BAS[p.basin] || p.basin) + "</dd><dt>Peak wind</dt><dd>" + esc(p.max_kt || "–") + " kt (" + Math.round((p.max_kt || 0) * 1.151) + " mph)</dd><dt>Active</dt><dd>" + esc(p.first) + " to " + esc(p.last) + "</dd></dl><p class=\"age\">IBTrACS best track (NOAA NCEI), " + esc(TR && TR.season ? TR.season.season : "") + " season</p>";
    } else if (L === "gd") {
      var gc = GDC[p.alert] || "#7C8190";
      h = stl(gc, (p.kind || "Alert") + " · " + (p.alert || "") + " alert") + "<h3>" + esc(p.name) + "</h3>" + (p.country ? "<p>" + esc(p.country) + "</p>" : "") + (p.sev ? '<p class="age">' + esc(p.sev) + "</p>" : "") +
        '<p class="age">Since ' + esc(FDATE.format(new Date(tms(p.from + "Z") || 0))) + "</p>" + (url(p.url) ? '<div class="acts"><a href="' + url(p.url) + '" target="_blank" rel="noopener noreferrer">GDACS report</a></div>' : "");
    } else if (L.indexOf("nhc") === 0 && p.src === "gdacs") {
      h = stl(WC.trop, "Active cyclone · " + (p.kind === "cone" ? "forecast area" : p.kind === "point" ? "position" : "track")) + "<h3>" + esc(p.name || "Tropical cyclone") + "</h3>" + (p.cls ? "<p>" + esc(p.cls) + "</p>" : "") +
        (p.country ? '<p class="age">' + esc(p.country) + (p.source ? " · " + esc(p.source) : "") + "</p>" : "") + (url(p.url) ? '<div class="acts"><a href="' + url(p.url) + '" target="_blank" rel="noopener noreferrer">GDACS report</a></div>' : "");
    } else if (L.indexOf("nhc") === 0) {
      h = stl(WC.trop, "Active storm · " + (p.kind === "cone" ? "forecast cone" : p.kind === "past" ? "past track" : "forecast track")) + "<h3>" + esc(p.name || "Tropical system") + "</h3><dl>" + (p.cls ? "<dt>Type</dt><dd>" + esc(p.cls) + "</dd>" : "") +
        (p.wind_kt ? "<dt>Wind</dt><dd>" + esc(p.wind_kt) + " kt</dd>" : "") + (p.pressure ? "<dt>Pressure</dt><dd>" + esc(p.pressure) + " mb</dd>" : "") + (p.label ? "<dt>Point</dt><dd>" + esc(p.label) + "</dd>" : "") + "</dl>" +
        '<div class="acts"><a href="https://www.nhc.noaa.gov/" target="_blank" rel="noopener noreferrer">National Hurricane Center</a></div>';
    } else if (L === "warn-fill" || L === "warn-line" || L === "watch-line") {
      var wc = WC[p.g] || "#7C8190";
      h = stl(wc, p.watch ? "Watch" : "Warning") + "<h3>" + esc(p.event) + "</h3>" + (p.ends ? "<p class=\"age\">Until " + esc(stamp(tms(p.ends))) + "</p>" : "") + "<p>" + esc(p.area) + "</p>" + (p.sender ? '<p class="age">' + esc(p.sender) + "</p>" : "") +
        (url(p.url) ? '<div class="acts"><a href="' + url(p.url) + '" target="_blank" rel="noopener noreferrer">Full alert</a></div>' : "");
    } else if (L === "ol-fill" || L === "ol-line") {
      var oc = OLC[p.cat] || "#7C8190";
      h = stl(oc, "SPC Day " + p.day + " outlook") + "<h3>" + esc(OLN[p.cat] || p.label) + "</h3><p class=\"age\">Valid " + esc(stamp(tms(p.valid))) + " to " + esc(stamp(tms(p.expire))) + "</p>" +
        '<div class="acts"><a href="https://www.spc.noaa.gov/products/outlook/" target="_blank" rel="noopener noreferrer">SPC outlook</a></div>';
    }
    return h;
  }
  function valueHTML(lng, lat) {
    var f = FRAMES[IDX]; if (MODE === "radar" || !f) return "";
    var v = gValueAt(lng, lat, f.t); if (isNaN(v)) return "";
    if (MODE === "temp") return Math.round(v) + "°F";
    if (MODE === "rain") return (v < 0.01 ? "No rain" : v.toFixed(2) + " in of rain") + " in 3 h";
    return (v < 0.1 ? "No snow" : v.toFixed(1) + " in of snow") + " in 24 h";
  }
  function place(pt) {
    if (touch || innerWidth < 768) { card.style.left = ""; card.style.top = ""; return; }
    if (!pt) { card.style.left = "16px"; card.style.top = "124px"; return; }
    var w = card.offsetWidth, h = card.offsetHeight, x = pt.x + 18, y = pt.y + 18;
    if (x + w > innerWidth - 70) x = pt.x - w - 18; if (y + h > innerHeight - 150) y = Math.max(130, innerHeight - h - 150);
    card.style.left = Math.max(12, x) + "px"; card.style.top = Math.max(120, y) + "px";
  }
  function showCard(html, pt, pin, tip) {
    if (!pin && pinned) return;
    card.innerHTML = (pin ? CX : "") + html; card.hidden = false; card.classList.toggle("pin", !!pin); card.classList.toggle("tip", !!tip);
    pinned = pin ? 1 : null; place(pt);
    requestAnimationFrame(function () { card.classList.add("in"); });
  }
  function hideCard(force) {
    if (pinned && !force) return;
    pinned = null; card.classList.remove("in", "pin"); setTimeout(function () { if (!card.classList.contains("in")) card.hidden = true; }, 200);
  }
  card.addEventListener("click", function (e) {
    if (e.target.closest(".wx-cx")) { hideCard(true); return; }
    var b = e.target.closest("[data-fc]"); if (b) { var a = b.dataset.fc.split(","); forecast({ lat: +a[0], lon: +a[1], name: "This spot" }, false); }
  });
  var HIT = ["gd", "rep", "trk-hit", "nhc-pt", "nhc-track", "nhc-cone", "season-line", "warn-fill", "ol-fill"];
  function hits(pt, pad) {
    var bb = pad ? [[pt.x - pad, pt.y - pad], [pt.x + pad, pt.y + pad]] : pt;
    var ly = HIT.filter(function (id) { return map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none"; });
    return ly.length ? map.queryRenderedFeatures(bb, { layers: ly }) : [];
  }

  /* ---------- point forecast (reuses /api/weather and /api/weather/geocode) ---------- */
  function setMe(lon, lat) { if (map && map.getSource("me")) map.getSource("me").setData({ type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }] }); }
  function fF(c) { return c == null ? "–" : Math.round(c * 9 / 5 + 32) + "°"; }
  function MPH(k) { return k == null ? "–" : Math.round(k * 0.621371) + " mph"; }
  function forecast(loc, fly) {
    if (fly && map) map.flyTo({ center: [loc.lon, loc.lat], zoom: Math.max(map.getZoom(), 7.2), speed: 1.1, curve: 1.4, essential: true, padding: innerWidth < 768 ? { top: 120, bottom: Math.round(innerHeight * 0.62), left: 10, right: 10 } : { top: 120, bottom: 160, left: 380, right: 80 } });
    setMe(loc.lon, loc.lat); stop();
    showCard('<span class="st" style="color:#5AB4FF"><i style="background:#5AB4FF"></i>Forecast</span><h3>' + esc(loc.name || "This spot") + '</h3><p class="age">Loading the forecast…</p>', null, true);
    var q = "lat=" + loc.lat.toFixed(4) + "&lon=" + loc.lon.toFixed(4) + (loc.cc ? "&cc=" + encodeURIComponent(loc.cc) : "") + (loc.name ? "&name=" + encodeURIComponent(loc.name) : "") + (loc.admin1 ? "&admin1=" + encodeURIComponent(loc.admin1) : "");
    jget("/api/weather?" + q).then(function (d) {
      var s = d.sources || {}, om = s.open_meteo && s.open_meteo.ok ? s.open_meteo.data : null, h = "";
      var nm = [loc.name, loc.admin1 && loc.admin1 !== loc.name ? loc.admin1 : ""].filter(Boolean).join(", ");
      h += '<span class="st" style="color:#5AB4FF"><i style="background:#5AB4FF"></i>Forecast</span><h3>' + esc(nm || "This spot") + "</h3>";
      if (om && om.current) {
        var c = om.current;
        h += '<div class="wx-now-big"><b>' + fF(c.temperature_2m) + '</b><span>' + esc(WMO[c.weather_code] || "") + "<br>Feels like " + fF(c.apparent_temperature) + "</span></div>";
        h += '<p class="age">Wind ' + MPH(c.wind_speed_10m) + (c.wind_gusts_10m ? ", gusts " + MPH(c.wind_gusts_10m) : "") + " · Humidity " + esc(c.relative_humidity_2m) + "%</p>";
        var hr = om.hourly || {}, out = "";
        for (var i = 0, n = 0; hr.time && i < hr.time.length && n < 12; i++) {
          var hh = hr.time[i]; if (hh < (c.time || "")) continue;
          var hrs = +hh.slice(11, 13), lab = n === 0 ? "Now" : (hrs % 12 || 12) + (hrs < 12 ? "a" : "p");
          out += "<div><small>" + lab + "</small><b>" + fF(hr.temperature_2m[i]) + "</b><em>" + (hr.precipitation_probability && hr.precipitation_probability[i] >= 20 ? hr.precipitation_probability[i] + "%" : "") + "</em></div>"; n++;
        }
        if (out) h += '<div class="wx-hrs">' + out + "</div>";
        var dy = om.daily || {};
        if (dy.time) {
          h += '<ul class="wx-days">';
          dy.time.forEach(function (t, i) {
            var dn = i === 0 ? "Today" : new Date(t + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
            h += "<li><b style=\"text-align:left;min-width:0\">" + dn + "</b><span>" + esc(WMO[dy.weather_code[i]] || "") + "</span><em>" + (dy.precipitation_probability_max[i] >= 20 ? dy.precipitation_probability_max[i] + "%" : "") + "</em><b>" + fF(dy.temperature_2m_max[i]) + " / " + fF(dy.temperature_2m_min[i]) + "</b></li>";
          });
          h += "</ul>";
        }
      } else h += '<p class="age">The forecast is unavailable right now.</p>';
      var al = s.nws_alerts && s.nws_alerts.ok ? s.nws_alerts.data || [] : [];
      al.slice(0, 3).forEach(function (a) { h += '<div class="wx-al' + (/Tornado/.test(a.event || "") ? " tor" : "") + '"><b>' + esc(a.event) + "</b>" + (a.expires ? '<span class="age">Until ' + esc(stamp(tms(a.expires))) + "</span>" : "") + "</div>"; });
      var nf = s.nws_forecast && s.nws_forecast.ok && s.nws_forecast.data.periods && s.nws_forecast.data.periods[0];
      if (nf) h += "<p><b>" + esc(nf.name) + ":</b> " + esc(nf.detailedForecast || nf.shortForecast) + "</p>";
      h += '<p class="age">' + (nf ? "National Weather Service · " : "") + "Open-Meteo</p>";
      showCard(h, null, true);
    }).catch(function () { showCard('<h3>' + esc(loc.name || "This spot") + '</h3><p class="age">The forecast is unavailable right now.</p>', null, true); });
  }
  /* search */
  var sq = $("wx_q"), hl = $("wx_hits"), hitsL = [], sel = -1, qT = 0;
  function renderHits() {
    if (!hitsL.length) { hl.hidden = true; hl.innerHTML = ""; return; }
    hl.innerHTML = hitsL.map(function (r, i) { return '<li role="option" data-i="' + i + '" aria-selected="' + (i === sel) + '">' + esc(r.name) + "<small>" + esc([r.admin2, r.admin1, r.country].filter(Boolean).join(", ")) + "</small></li>"; }).join("");
    hl.hidden = false;
  }
  function pick(r) {
    if (!r) return; hitsL = []; renderHits(); sq.value = r.name; sq.blur();
    var loc = { name: r.name, admin1: r.admin1 || "", admin2: r.admin2 || "", country: r.country || "", cc: r.cc || "", lat: +r.lat, lon: +r.lon, tz: r.tz || "" };
    try { localStorage.setItem("bn_wx_loc", JSON.stringify(loc)); } catch (e) {}
    forecast(loc, true);
  }
  sq.addEventListener("input", function () {
    clearTimeout(qT); var q = sq.value.trim(); if (q.length < 2) { hitsL = []; renderHits(); return; }
    qT = setTimeout(function () { jget("/api/weather/geocode?q=" + encodeURIComponent(q)).then(function (d) { if (sq.value.trim() !== q) return; hitsL = (d.results || []).slice(0, 6); sel = hitsL.length ? 0 : -1; renderHits(); }).catch(function () {}); }, 230);
  });
  sq.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (!hitsL.length) return; sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + hitsL.length) % hitsL.length; renderHits(); }
    if (e.key === "Escape") { hitsL = []; renderHits(); }
  });
  $("wx_search").addEventListener("submit", function (e) {
    e.preventDefault(); var q = sq.value.trim(); if (q.length < 2) return;
    if (hitsL.length) { pick(hitsL[Math.max(0, sel)]); return; }
    jget("/api/weather/geocode?q=" + encodeURIComponent(q)).then(function (d) { pick((d.results || [])[0]); }).catch(function () {});
  });
  hl.addEventListener("mousedown", function (e) { var li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pick(hitsL[+li.dataset.i]); } });
  document.addEventListener("click", function (e) { if (!e.target.closest("#wx_search")) { hitsL = []; renderHits(); } });
  /* my location */
  $("wx_loc").addEventListener("click", function () {
    if (!navigator.geolocation) return;
    var b = $("wx_loc"); b.classList.add("on");
    navigator.geolocation.getCurrentPosition(function (p) {
      var lat = p.coords.latitude, lon = p.coords.longitude;
      jget("/api/weather/reverse?lat=" + lat.toFixed(4) + "&lon=" + lon.toFixed(4)).then(function (d) { var r = d.result || {}; forecast({ lat: lat, lon: lon, name: r.name || "My location", admin1: r.admin1, cc: r.cc }, true); })
        .catch(function () { forecast({ lat: lat, lon: lon, name: "My location" }, true); });
      setTimeout(function () { b.classList.remove("on"); }, 1500);
    }, function () { b.classList.remove("on"); showCard('<h3>Location unavailable</h3><p class="age">Allow location access in your browser, or search a city or ZIP code.</p>', null, true); }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  });
  /* region switcher (same views as /grid); the page always opens on the lower 48 */
  var VIEWS = { us: { b: US0 }, eu: { b: [[-11, 35], [32, 61]] }, apac: { b: [[66, -46], [179, 50]] }, world: { c: [12, 22], z: innerWidth < 768 ? 0.45 : 1.35 } }, regBusy = 0;
  function regPress(r) { [].forEach.call(document.querySelectorAll("#wx_reg button"), function (b) { b.setAttribute("aria-pressed", b.dataset.r === r ? "true" : "false"); }); }
  function region(r) {
    var v = VIEWS[r]; if (!map || !v) return; regPress(r); hideCard(true); regBusy = Date.now();
    var ease = function (t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
    if (v.b) map.fitBounds(v.b, { padding: PAD(), duration: 1500, essential: true, easing: ease });
    else map.flyTo({ center: v.c, zoom: v.z, speed: 0.9, curve: 1.4, essential: true });
  }
  function regSync() {   /* after a free pan, light up the region the map is now over (or none) */
    if (Date.now() - regBusy < 1700) return;
    var c = map.getCenter(), z = map.getZoom(), r = z < 2 ? "world" : (c.lng > -130 && c.lng < -60 && c.lat > 20 && c.lat < 55) ? "us" : (c.lng > -15 && c.lng < 40 && c.lat > 33 && c.lat < 66) ? "eu" : (c.lng > 60 && c.lat < 55) ? "apac" : "";
    regPress(r);
  }
  $("wx_reg").addEventListener("click", function (e) { var b = e.target.closest("button[data-r]"); if (b) region(b.dataset.r); });
  $("wx_zin").addEventListener("click", function () { map && map.zoomIn({ duration: 450 }); });
  $("wx_zout").addEventListener("click", function () { map && map.zoomOut({ duration: 450 }); });
  $("wx_home").addEventListener("click", function () { map && map.fitBounds(US0, { padding: PAD(), duration: 1100 }); });
  $("wx_pill").addEventListener("click", function () {
    if (!AL || !map) return; var b = null;
    AL.features.forEach(function (f) { if (f.properties.watch || (f.properties.g !== "tor" && f.properties.g !== "svr")) return;
      (function walk(c) { if (typeof c[0] === "number") { b = b ? [[Math.min(b[0][0], c[0]), Math.min(b[0][1], c[1])], [Math.max(b[1][0], c[0]), Math.max(b[1][1], c[1])]] : [[c[0], c[1]], [c[0], c[1]]]; } else c.forEach(walk); })(f.geometry.coordinates); });
    if (b) map.fitBounds(b, { padding: PAD(), maxZoom: 8, duration: 1300 });
  });

  /* ---------- map ---------- */
  var ready = false;
  function boot() {
    if (!window.maplibregl) { $("wx_when").textContent = "The map could not start in this browser."; finish(); return; }
    if (maplibregl.setMaxParallelImageRequests) maplibregl.setMaxParallelImageRequests(48);   /* frames ahead load in parallel (our own queue does the throttling) */
    if (PROTO) maplibregl.addProtocol("wxr", proto);
    if (WK) maplibregl.addProtocol("wxg", protoG);
    map = new maplibregl.Map({ container: "wx_map", style: style(), bounds: US0, fitBoundsOptions: { padding: PAD() }, minZoom: 1.2, maxZoom: 11,
      attributionControl: false, maplibreLogo: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0, fadeDuration: 200 });
    window.__wxMap = map;   /* QA hooks (read-only) */
    window.__wxDbg = function () {
      var vis = [];
      (map.getStyle().layers || []).forEach(function (l) { if (/^(r-|m-)/.test(l.id) && map.getPaintProperty(l.id, "raster-opacity") > 0) vis.push([l.id, map.isSourceLoaded(l.id)]); });
      return { mode: MODE, frames: FRAMES.length, idx: IDX, buf: BUF, bytes: BYTES.size, queue: Q.length, inflight: QN, bitmaps: MB.size, mq: mQ.length, vis: vis, proto: PROTO, grids: { us: !!GD.us, world: !!GD.world }, src: SRC };
    };
    map.touchZoomRotate.disableRotation();
    map.dragPan.enable({ linearity: 0.25, easing: function (t) { return 1 - Math.pow(1 - t, 3); }, deceleration: 2200, maxSpeed: 1600 });
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · Weather: NOAA/NWS, IEM, NASA GIBS, <a href="https://www.eumetsat.int/" target="_blank" rel="noopener">&copy; EUMETSAT</a> (CC BY 4.0), <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>, GDACS' }), "bottom-right");
    map.on("load", function () {
      var at = document.querySelector(".maplibregl-ctrl-attrib"); if (at) at.classList.remove("maplibregl-compact-show");
      addOverlayLayers(); ready = true; setLayerVis();
      if (AL) map.getSource("warn").setData(AL);
      map.once("idle", function () { step("map"); });
      var pfT = 0; map.on("moveend", function () { clearTimeout(pfT); pfT = setTimeout(function () { if (MODE === "radar") prefetch(); }, 350); });
      map.on("moveend", regSync);
      setTimeout(function () { step("map"); }, 7000);
      if (FRAMES.length) { go(IDX, true); if (MODE === "radar") prefetch(); else mPreload(); }
      Promise.all([loadAlerts(), loadStorms(), loadTropical(), loadGlobal()]).then(function () { step("storms"); }, function () { step("storms"); });
      setTimeout(function () { step("storms"); }, 8000);
      map.on("mousemove", function (e) {
        if (touch) return;
        var f = hits(e.point, 3)[0];
        map.getCanvas().style.cursor = f ? "pointer" : "";
        if (f) { showCard(featHTML(f), e.point, false); return; }
        var v = valueHTML(e.lngLat.lng, e.lngLat.lat);
        if (v) showCard(esc(v), e.point, false, true); else hideCard(false);
      });
      map.on("mouseout", function () { hideCard(false); });
      map.on("click", function (e) {
        if (document.body.classList.contains("wx-lays-on")) { closeLays(); return; }
        var f = hits(e.point, 8)[0], v = valueHTML(e.lngLat.lng, e.lngLat.lat);
        var fc = '<div class="acts"><button type="button" class="lnk" data-fc="' + e.lngLat.lat.toFixed(4) + "," + e.lngLat.lng.toFixed(4) + '">Forecast for this spot</button></div>';
        if (f) showCard(featHTML(f) + (v ? '<p class="age">' + esc(v) + "</p>" : "") + fc, e.point, true);
        else if (pinned) hideCard(true);
        else showCard((v ? "<h3>" + esc(v) + "</h3>" : "<h3>This spot</h3>") + '<p class="age">' + esc(FRAMES[IDX] ? when(FRAMES[IDX].t) : "") + "</p>" + fc, e.point, true);
      });
    });
  }

  /* ---------- data ---------- */
  var SRC = {};
  function srcSet(k, label, ok, why) { SRC[k] = { label: label, ok: ok, why: why }; srcPaint(); }
  function srcPaint() {
    var el = $("wx_srcs"); if (!el) return;
    el.innerHTML = ["radar_us", "radar_fc", "sat", "imerg", "gfs", "grid_us", "grid_world"].filter(function (k) { return SRC[k]; }).map(function (k) {
      var x = SRC[k]; return '<li class="' + (x.ok ? "ok" : "off") + '"><i></i><span><b>' + esc(x.label) + "</b>" + (x.why ? "<small>" + esc(x.why) + "</small>" : "") + "</span></li>";
    }).join("");
  }
  function loadFrames(first) {
    return jget("/api/wxmap/frames").then(function (d) {
      var s = d.sources || {};
      FR = d; ERR.radar = (!d.past.length && !d.forecast.length && !d.gfs) ? ((s.past && s.past.reason) || "Radar is unavailable right now") : null;
      srcSet("radar_us", "U.S. radar · NOAA MRMS", !!(s.past && s.past.ok), s.past && s.past.ok ? "Past 12 hours" : s.past && s.past.reason);
      srcSet("radar_fc", "U.S. radar forecast · NOAA HRRR", !!(s.forecast && s.forecast.ok), s.forecast && s.forecast.ok ? "Out to about 48 hours" : s.forecast && s.forecast.reason);
      var sd = s.sat && s.sat.down ? Object.keys(s.sat.down) : [], SN = { ge: "GOES-East", gw: "GOES-West", hi: "Himawari", ms: "Meteosat", io: "Meteosat Indian Ocean" };
      srcSet("sat", "Satellite clouds · NASA GIBS, EUMETSAT", !!(s.sat && s.sat.ok) && PROTO, !PROTO ? "Needs a newer browser" : s.sat && s.sat.ok ? (sd.length ? "Infrared, every 10 to 60 minutes. Missing now: " + sd.map(function (k) { return SN[k] || k; }).join(", ") : "Infrared, worldwide, every 10 to 60 minutes") : s.sat && s.sat.reason);
      srcSet("imerg", "Satellite rain · NASA IMERG", !!(s.imerg && s.imerg.ok) && PROTO, !PROTO ? "Needs a newer browser" : s.imerg && s.imerg.ok ? "Worldwide, every 30 minutes, arrives about 4 to 6 hours late (newest " + stamp(tms(s.imerg.latest)) + ")" : s.imerg && s.imerg.reason);
      if (!d.gfs) srcSet("gfs", "Worldwide forecast · NOAA GFS", false, (s.gfs && s.gfs.reason) || "Loading");
      loadGfs();
      var b = document.querySelector('#wx_modes [data-m="radar"]'); b.disabled = !!ERR.radar; b.title = ERR.radar || "";
      LD.frames = 1; ldRow("radar", "Indexed", false); ldUpdate();
      if (MODE === "radar") {
        if (ERR.radar && (GD.us || GD.world)) { setMode("temp", false); return; }
        var t = FRAMES[IDX] ? FRAMES[IDX].t : null; buildFrames(first ? null : t);
      }
      if (ERR.radar) { LD.need = 0; ldUpdate(); }
    }).catch(function (e) {
      ERR.radar = e.reason || "Radar is unavailable right now"; var b = document.querySelector('#wx_modes [data-m="radar"]'); b.disabled = true; b.title = ERR.radar;
      LD.frames = 1; LD.need = 0; ldUpdate();
      srcSet("radar_us", "Radar", false, ERR.radar);
      if (MODE === "radar") { if (GD.us || GD.world) setMode("temp", false); else label(); }
    });
  }
  var gRetry = {};
  function loadGrid(gk) {
    return jget("/api/wxmap/grid?r=" + gk).then(function (d) {
      if (GD[gk] && GD[gk].gen === d.generated) return;
      var g = expand(gk, d);
      var post = WK ? wkCall({ op: "grid", key: gk + ":" + g.gen, grid: { nx: g.nx, ny: g.ny, lat0: g.lat0, lon0: g.lon0, step: g.step, wrap: g.wrap, nt: g.nt, N: g.N, temp: g.temp, precip: g.precip, snow: g.snow } }) : Promise.resolve();
      return post.then(function () {
        GD[gk] = g; GERR[gk] = null; FC = {};
        MB.forEach(function (b, k) { if (k.indexOf(gk + "|") === 0) { try { b.close(); } catch (e) {} MB.delete(k); } });
        srcSet("grid_" + gk, gk === "us" ? "U.S. temperature, rain, snow · Open-Meteo 1.5°" : "Worldwide temperature, rain, snow · Open-Meteo 4°", true, "Past day and next 7 days, every 3 hours");
        if (WK) ["temp", "rain", "snow"].forEach(function (m) { var b = document.querySelector('#wx_modes [data-m="' + m + '"]'); b.disabled = false; b.title = ""; });
        ERR.grid = null;
        if (MODE !== "radar") { if (map && ready) gHide(); buildFrames(FRAMES[IDX] ? FRAMES[IDX].t : null); }
        else if (ERR.radar) setMode("temp", false);
      });
    }).catch(function (e) {
      GERR[gk] = e.reason || "the forecast source did not answer";
      srcSet("grid_" + gk, gk === "us" ? "U.S. temperature, rain, snow · Open-Meteo" : "Worldwide temperature, rain, snow · Open-Meteo", false, "Unavailable: " + GERR[gk]);
      if (!GD.us && !GD.world) {
        ERR.grid = "Temperature, rain and snow are unavailable: " + GERR[gk];
        ["temp", "rain", "snow"].forEach(function (m) { var b = document.querySelector('#wx_modes [data-m="' + m + '"]'); b.disabled = true; b.title = ERR.grid; });
      }
      clearTimeout(gRetry[gk]); gRetry[gk] = setTimeout(function () { loadGrid(gk); }, 30000);
    });
  }
  function loadGrids() { return loadGrid("us").then(function () { return loadGrid("world"); }); }
  PROTO = !!wk();
  if (!WK) ["temp", "rain", "snow"].forEach(function (m) { var b = document.querySelector('#wx_modes [data-m="' + m + '"]'); b.disabled = true; b.title = "Needs a newer browser"; });
  legend(); label(); boot(); loadFrames(true); loadGrids();
  setInterval(function () { if (document.hidden) return; loadFrames(false); loadAlerts(); }, 180000);
  setInterval(function () { if (!document.hidden) { loadStorms(); loadTropical(); loadGlobal(); } }, 600000);
  setInterval(function () { if (!document.hidden) loadGrids(); }, 1800000);
  setInterval(function () { if (!document.hidden && !playing) label(); }, 60000);
})();
