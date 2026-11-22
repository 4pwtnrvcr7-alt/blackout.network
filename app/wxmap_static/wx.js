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
  var RADAR_GRAD = "linear-gradient(90deg,#04e9e7,#019ff4,#0300f4,#02fd02,#01c501,#008e00,#e5bc00,#fd9500,#fd0000,#bc0000,#f800fd,#9854c6)";
  var WMO = { 0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorms", 96: "Thunderstorms, hail", 99: "Severe thunderstorms" };

  /* ---------- loader ---------- */
  var ld = { map: 0, radar: 0, storms: 0 }, ldT0 = Date.now(), ldDone = false;
  function step(k) {
    if (ld[k]) return; ld[k] = 1; var li = document.querySelector('.wx-lds li[data-s="' + k + '"]'); if (li) li.classList.add("on");
    var n = ld.map + ld.radar + ld.storms; $("wx_ldn").textContent = Math.round(n / 3 * 100) + "%";
    if (n === 3) finish();
  }
  function finish() { if (ldDone) return; ldDone = true; setTimeout(function () { document.body.classList.add("wx-ready"); }, Math.max(0, 1100 - (Date.now() - ldT0))); }
  setTimeout(function () { if (!ldDone) { var m = $("wx_ldmsg"); m.hidden = false; m.textContent = "Still connecting. Showing what has arrived."; setTimeout(finish, 1500); } }, 9000);

  /* ---------- state ---------- */
  var map = null, US = [[-125.5, 23.5], [-66, 50]], BEFORE = "admin-state";
  var MODE = "radar", FRAMES = [], IDX = 0, NOWI = 0, playing = false, live = true;
  var FR = null, G = null, AL = null, ST = null, TR = null;
  var ERR = { radar: null, grid: null };
  var LAYS = Object.assign({ warn: true, reports: true, tracks: true, trop: false, outlook: false, labels: true }, store("bn_wx_lays") || {});
  function PAD() { return innerWidth < 768 ? { top: 150, bottom: 150, left: 2, right: 2 } : { top: 140, bottom: 140, left: 70, right: 80 }; }
  var US0 = innerWidth < 768 ? [[-124.6, 24.6], [-67.2, 49.2]] : US;

  /* ---------- frames (timeline) ---------- */
  function buildFrames(keepT) {
    var out = [];
    if (MODE === "radar" && FR) {
      FR.past.forEach(function (f) { out.push({ t: tms(f.t), layer: f.layer, kind: "past" }); });
      FR.forecast.forEach(function (f) { var t = tms(f.t); if (!out.length || t > out[out.length - 1].t) out.push({ t: t, layer: f.layer, kind: "fc", run: f.run }); });
    } else if (MODE !== "radar" && G) {
      G.times.forEach(function (s, k) { var t = tms(s); out.push({ t: t, k: k, kind: t <= Date.now() ? "past" : "fc" }); });
    }
    FRAMES = out;
    var now = Date.now(); NOWI = 0;
    for (var i = 0; i < out.length; i++) if (out[i].t <= now + 60000 && (MODE !== "radar" || out[i].kind === "past")) NOWI = i;   /* radar "now" is always the latest observed scan */
    var r = $("wx_range"); r.max = Math.max(0, out.length - 1);
    var target = (keepT == null || live) ? NOWI : nearest(keepT);
    ticks();
    go(target, true);
  }
  function nearest(t) { var b = 0, bd = Infinity; FRAMES.forEach(function (f, i) { var d = Math.abs(f.t - t); if (d < bd) { bd = d; b = i; } }); return b; }
  function pos(i) { return FRAMES.length > 1 ? i / (FRAMES.length - 1) * 100 : 0; }
  function ticks() {
    var h = "", last = null, n = FRAMES.length;
    if (n > 1 && NOWI < n - 1) h += '<span class="fc-zone" style="left:' + pos(NOWI) + '%;right:0"></span>';
    var nowP = pos(NOWI);
    FRAMES.forEach(function (f, i) {
      var d = FDAY.format(new Date(f.t));
      if (last !== null && d !== last) {
        var p = pos(i); h += '<i style="left:' + p + '%"></i>';
        if (Math.abs(p - nowP) > 7) h += '<b style="left:' + p + '%">' + esc(FD.format(new Date(f.t))) + '</b>';
      }
      last = d;
    });
    if (n > 1) h += '<b style="left:' + nowP + '%;color:#5AB4FF">Now</b>';
    $("wx_ticks").innerHTML = h;
    $("wx_nowm").style.left = nowP + "%";
    $("wx_nowm").style.display = n > 1 ? "" : "none";
  }
  function label() {
    var f = FRAMES[IDX]; if (!f) { $("wx_when").textContent = MODE === "radar" ? (ERR.radar || "Radar unavailable") : (ERR.grid || "Unavailable"); $("wx_rel").textContent = ""; return; }
    var r = $("wx_rel"), isNow = IDX === NOWI;
    var what = MODE === "radar" ? (f.kind === "fc" ? "Forecast radar" : "Radar") : MODE === "temp" ? "Temperature" : MODE === "rain" ? "Rain, 3 h to" : "Snow, 24 h to";
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
    var isFc = MODE === "radar" && FRAMES[IDX].kind === "fc"; if (isFc !== legFc) { legFc = isFc; legend(); }
    if (map && ready) { if (MODE === "radar") rShow(IDX, instant); else gShow(IDX); timeFilters(); }
    label();
  }

  /* ---------- radar layers (one raster source per frame, created ahead of time, crossfaded) ---------- */
  var RLIVE = {}, RCUR = null, ROP = 0.82;
  function rId(f) { return "r-" + f.layer.replace(/[^A-Za-z0-9]/g, ""); }
  function rEnsure(f) {
    var id = rId(f);
    if (!map.getSource(id)) {
      map.addSource(id, { type: "raster", tiles: [FR.tile.replace("{layer}", f.layer)], tileSize: 256, maxzoom: f.kind === "fc" ? 7 : 8, bounds: [-128, 20, -62, 52.5], attribution: "" });
      map.addLayer({ id: id, type: "raster", source: id, paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 220, delay: 0 }, "raster-fade-duration": 0, "raster-resampling": "linear" } }, BEFORE);
    }
    RLIVE[id] = 1; return id;
  }
  function rLoaded(i) { var f = FRAMES[i]; if (!f) return true; var id = rEnsure(f); try { return map.isSourceLoaded(id); } catch (e) { return false; } }
  function rShow(i, instant) {
    var f = FRAMES[i]; if (!f) return; var id = rEnsure(f);
    Object.keys(RLIVE).forEach(function (x) {
      if (x === id || !map.getLayer(x)) return;
      if (map.getPaintProperty(x, "raster-opacity") !== 0) { map.setPaintProperty(x, "raster-opacity-transition", { duration: instant ? 0 : 340, delay: instant ? 0 : 60 }); map.setPaintProperty(x, "raster-opacity", 0); }
    });
    map.setPaintProperty(id, "raster-opacity-transition", { duration: instant ? 0 : 200, delay: 0 });
    map.setPaintProperty(id, "raster-opacity", ROP); RCUR = id;
    for (var k = -3; k <= 6; k++) if (FRAMES[i + k]) rEnsure(FRAMES[i + k]);
    rPrune(i);
    if (!ld.radar) { var t0 = Date.now(); (function w() { if (rLoaded(i) || Date.now() - t0 > 6000) step("radar"); else setTimeout(w, 150); })(); }
  }
  function rPrune(i) {
    var keep = {}; for (var k = -8; k <= 12; k++) if (FRAMES[i + k] && FRAMES[i + k].layer) keep[rId(FRAMES[i + k])] = 1;
    Object.keys(RLIVE).forEach(function (x) { if (!keep[x] && x !== RCUR) { if (map.getLayer(x)) map.removeLayer(x); if (map.getSource(x)) map.removeSource(x); delete RLIVE[x]; } });
  }
  function rHideAll() { Object.keys(RLIVE).forEach(function (x) { if (map.getLayer(x)) { map.setPaintProperty(x, "raster-opacity-transition", { duration: 250, delay: 0 }); map.setPaintProperty(x, "raster-opacity", 0); } }); RCUR = null; }
  function rClear() { Object.keys(RLIVE).forEach(function (x) { if (map.getLayer(x)) map.removeLayer(x); if (map.getSource(x)) map.removeSource(x); }); RLIVE = {}; RCUR = null; }

  /* ---------- model grid (temperature / rain / snow): drawn in the browser into a Web-Mercator image, crossfaded ---------- */
  var GW = 560, GH = 0, GCO = null, GIMG = {}, gCur = "gA", gTok = 0, GOP = 0.92, GBEFORE = "water";
  function my(lat) { return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)); }
  function iy(y) { return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI; }
  function gDims() {
    var la1 = G.lat0 + (G.ny - 1) * G.step, lo1 = G.lon0 + (G.nx - 1) * G.step;
    GH = Math.round(GW * (my(la1) - my(G.lat0)) / ((lo1 - G.lon0) * Math.PI / 180));
    GCO = [[G.lon0, la1], [lo1, la1], [lo1, G.lat0], [G.lon0, G.lat0]];
  }
  function gField(k, mode) {
    var N = G.nx * G.ny, out = new Float32Array(N), j, q;
    if (mode === "temp") { for (j = 0; j < N; j++) { var t = G.temp[k * N + j]; out[j] = t == null ? NaN : t; } }
    else if (mode === "rain") { for (j = 0; j < N; j++) { var p = G.precip[k * N + j]; out[j] = p == null ? NaN : p / 254; } }
    else { for (j = 0; j < N; j++) { var s = 0, ok = false; for (q = Math.max(0, k - 7); q <= k; q++) { var v = G.snow[q * N + j]; if (v != null) { s += v; ok = true; } } out[j] = ok ? s / 25.4 : NaN; } }
    return out;
  }
  function gSample(F, gx, gy) {
    var x0 = Math.floor(gx), y0 = Math.floor(gy), x1 = Math.min(x0 + 1, G.nx - 1), y1 = Math.min(y0 + 1, G.ny - 1), fx = gx - x0, fy = gy - y0;
    if (x0 < 0 || y0 < 0 || x0 >= G.nx || y0 >= G.ny) return NaN;
    var a = F[y0 * G.nx + x0], b = F[y0 * G.nx + x1], c = F[y1 * G.nx + x0], d = F[y1 * G.nx + x1];
    if (isNaN(a) || isNaN(b) || isNaN(c) || isNaN(d)) { var s = 0, n = 0; [a, b, c, d].forEach(function (v) { if (!isNaN(v)) { s += v; n++; } }); return n ? s / n : NaN; }
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  }
  function cr(p0, p1, p2, p3, t) { return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0))); }
  function gSmooth(F, gx, gy) {   /* Catmull-Rom (bicubic) so fields read as smooth weather, not 1.5-degree blocks */
    var x1 = Math.floor(gx), y1 = Math.floor(gy), fx = gx - x1, fy = gy - y1, nx = G.nx, ny = G.ny, rows = [];
    if (x1 < 0 || y1 < 0 || x1 >= nx || y1 >= ny) return NaN;
    for (var j = -1; j <= 2; j++) {
      var yy = clamp(y1 + j, 0, ny - 1), r = [];
      for (var i = -1; i <= 2; i++) { var v = F[yy * nx + clamp(x1 + i, 0, nx - 1)]; if (isNaN(v)) return gSample(F, gx, gy); r.push(v); }
      rows.push(cr(r[0], r[1], r[2], r[3], fx));
    }
    return cr(rows[0], rows[1], rows[2], rows[3], fy);
  }
  function gValueAt(lng, lat, k) {
    if (!G) return NaN; var F = gField(k, MODE);
    var v = gSmooth(F, (lng - G.lon0) / G.step, (lat - G.lat0) / G.step); return MODE === "temp" ? v : Math.max(0, v);
  }
  function gImg(k, mode) {
    var key = mode + ":" + k; if (GIMG[key]) return GIMG[key];
    var F = gField(k, mode), P = PAL[mode], cv = document.createElement("canvas"); cv.width = GW; cv.height = GH;
    var cx = cv.getContext("2d"), im = cx.createImageData(GW, GH), D = im.data;
    var yT = my(G.lat0 + (G.ny - 1) * G.step), yB = my(G.lat0);
    var LUT = {}, lo = P[0][0], hi = P[P.length - 1][0], NL = 400;
    var lut = new Array(NL + 1); for (var u = 0; u <= NL; u++) lut[u] = ramp(P, lo + (hi - lo) * u / NL);
    for (var py = 0; py < GH; py++) {
      var lat = iy(yT - (py + 0.5) / GH * (yT - yB)), gy = (lat - G.lat0) / G.step;
      for (var px = 0; px < GW; px++) {
        var gx = px / (GW - 1) * (G.nx - 1), v = gSmooth(F, gx, gy), o = (py * GW + px) * 4;
        var soft = 1;
        if (mode !== "temp") { if (isNaN(v) || v < lo * 0.25) { D[o + 3] = 0; continue; } if (v < lo) { soft = (v - lo * 0.25) / (lo * 0.75); soft *= soft; } }
        else if (isNaN(v)) { D[o + 3] = 0; continue; }
        var c = lut[Math.round(clamp((v - lo) / (hi - lo), 0, 1) * NL)];
        var e = Math.min(gx, G.nx - 1 - gx, gy, G.ny - 1 - gy), fade = clamp(e / 2.2, 0, 1); fade = fade * fade * (3 - 2 * fade) * soft;
        D[o] = c[0]; D[o + 1] = c[1]; D[o + 2] = c[2]; D[o + 3] = Math.round(c[3] * 255 * fade);
      }
    }
    cx.putImageData(im, 0, 0);
    return (GIMG[key] = cv.toDataURL("image/png"));
  }
  /* values shown at major cities (the base map already names them; the value sits just under the name) */
  var CITIES = [[-122.33, 47.61], [-122.68, 45.52], [-122.42, 37.77], [-121.49, 38.58], [-118.24, 34.05], [-117.16, 32.72], [-119.79, 36.74], [-115.14, 36.17], [-112.07, 33.45], [-110.97, 32.22],
    [-111.89, 40.76], [-116.2, 43.62], [-108.5, 45.78], [-106.65, 35.08], [-104.99, 39.74], [-104.82, 41.14], [-100.78, 46.81], [-96.73, 43.55], [-96.0, 41.26], [-97.52, 35.47], [-97.33, 37.69],
    [-96.8, 32.78], [-95.37, 29.76], [-98.49, 29.42], [-101.85, 33.58], [-106.49, 31.76], [-93.27, 44.98], [-94.58, 39.1], [-90.2, 38.63], [-87.63, 41.88], [-87.91, 43.04], [-93.61, 41.59],
    [-90.07, 29.95], [-90.05, 35.15], [-86.78, 36.16], [-86.8, 33.52], [-84.39, 33.75], [-81.66, 30.33], [-81.38, 28.54], [-82.46, 27.95], [-80.19, 25.76], [-81.69, 41.5], [-83.05, 42.33],
    [-84.51, 39.1], [-86.16, 39.77], [-85.76, 38.25], [-80.84, 35.23], [-78.64, 35.78], [-79.94, 32.78], [-77.44, 37.54], [-77.04, 38.91], [-76.61, 39.29], [-75.17, 39.95], [-74.01, 40.71],
    [-79.99, 40.44], [-78.88, 42.89], [-73.76, 42.65], [-71.06, 42.36], [-72.68, 41.76], [-70.26, 43.66], [-73.21, 44.48], [-92.29, 34.75], [-89.4, 43.07], [-84.55, 42.73], [-100.35, 44.37]];
  function gLabels(k) {
    var F = gField(k, MODE), f = [];
    CITIES.forEach(function (c) {
      var v = gSmooth(F, (c[0] - G.lon0) / G.step, (c[1] - G.lat0) / G.step); if (isNaN(v)) return; if (MODE !== "temp") v = Math.max(0, v);
      var t = MODE === "temp" ? Math.round(v) + "°" : MODE === "rain" ? (v >= 0.01 ? (v >= 1 ? v.toFixed(1) : v.toFixed(2).replace(/^0/, "")) + '"' : "") : (v >= 0.1 ? (v >= 10 ? Math.round(v) : v.toFixed(1)) + '"' : "");
      if (t) f.push({ type: "Feature", geometry: { type: "Point", coordinates: c }, properties: { v: t, s: -v } });
    });
    return { type: "FeatureCollection", features: f };
  }
  function gEnsure() {
    if (map.getSource("gA") || !G) return;
    var blank = gImg(0, MODE);
    ["gA", "gB"].forEach(function (id) {
      map.addSource(id, { type: "image", url: blank, coordinates: GCO });
      map.addLayer({ id: id, type: "raster", source: id, paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 260, delay: 0 }, "raster-fade-duration": 0, "raster-resampling": "linear" } }, GBEFORE);
    });
  }
  function gShow(k) {
    if (!G) return; gEnsure();
    var f = FRAMES[k]; if (!f) return;
    var u = gImg(f.k, MODE), nxt = gCur === "gA" ? "gB" : "gA", tok = ++gTok;
    map.getSource(nxt).updateImage({ url: u, coordinates: GCO });
    setTimeout(function () {
      if (tok !== gTok || MODE === "radar") return;
      map.setPaintProperty(nxt, "raster-opacity", GOP); map.setPaintProperty(gCur, "raster-opacity", 0); gCur = nxt;
    }, 45);
    if (map.getSource("gv")) map.getSource("gv").setData(LAYS.labels ? gLabels(f.k) : { type: "FeatureCollection", features: [] });
    var n1 = FRAMES[k + 1]; if (n1) setTimeout(function () { gImg(n1.k, MODE); }, 0);
  }
  function gHide() { gTok++; ["gA", "gB"].forEach(function (id) { if (map.getLayer(id)) map.setPaintProperty(id, "raster-opacity", 0); }); if (map.getSource("gv")) map.getSource("gv").setData({ type: "FeatureCollection", features: [] }); }

  /* ---------- legend ---------- */
  function legend() {
    var h;
    var fc = FRAMES[IDX] && FRAMES[IDX].kind === "fc";
    if (MODE === "radar" && fc) h = '<span class="u">Forecast</span><span>Rain</span><span class="bar sm" style="background:linear-gradient(90deg,#d6efd0,#73c476,#228a44,#006c2c)"></span><span>Snow</span><span class="bar sm" style="background:linear-gradient(90deg,#81c0d5,#1b8db3,#003f7f)"></span><span>Mix</span><span class="bar sm" style="background:linear-gradient(90deg,#e6e5f1,#7e79b8)"></span>';
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
    MODE = m; GIMG = {};
    [].forEach.call(document.querySelectorAll("#wx_modes button"), function (b) { b.setAttribute("aria-pressed", b.dataset.m === m ? "true" : "false"); });
    if (map && ready) { if (m === "radar") gHide(); else rHideAll(); setLayerVis(); }
    legFc = null; hideCard(true);
    buildFrames(t); legend();
  }
  $("wx_modes").addEventListener("click", function (e) { var b = e.target.closest("button[data-m]"); if (b && !b.disabled) { stop(); setMode(b.dataset.m); } });

  /* ---------- play ---------- */
  var playT = null;
  function frameReady(i) { return MODE === "radar" ? rLoaded(i) : true; }
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
      if (frameReady(n) || Date.now() - t0 > 2600 + wait) { go(n); tick(); }
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
  var LGRP = { warn: ["warn-fill", "watch-line", "warn-glow", "warn-line"], reports: ["rep", "rep-lbl"], tracks: ["trk-glow", "trk", "trk-hit"], trop: ["season-line", "season-lbl"], outlook: ["ol-fill", "ol-line"], labels: ["gv"] };
  function setLayerVis() {
    if (!map || !ready) return;
    Object.keys(LGRP).forEach(function (k) {
      var on = !!LAYS[k] && !(k === "labels" && MODE === "radar");
      LGRP[k].forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none"); });
    });
    [].forEach.call(document.querySelectorAll("[data-lay]"), function (i) { i.checked = !!LAYS[i.dataset.lay]; });
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
      if (d.active && map) map.getSource("nhc").setData(d.active);
      var a = d.active && d.active.active ? d.active.active.length : 0, s = d.season ? d.season.features.length : 0;
      var ok = d.season_status.ok || d.active_status.ok;
      status("trop", d.season_status.ok ? s + " storms in " + d.season.season + (a ? " · " + a + " active now (always shown)" : " · none active now") : "Unavailable: " + d.season_status.reason, !!d.season_status.ok);
    }).catch(function (e) { status("trop", "Unavailable: " + (e.reason || "no answer"), false); });
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
    var t = document.querySelector('.wx-lay[data-k="tracks"] .wx-lt');
    if (t) t.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + EFC.map(function (c, n) { return '<span><i style="background:' + c + '"></i>EF' + n + '</span>'; }).join("") + '</span>');
    var h = document.querySelector('.wx-lay[data-k="trop"] .wx-lt');
    if (h) h.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + [["0", "Storm"], ["1", "Cat 1"], ["2", "Cat 2"], ["3", "Cat 3"], ["4", "Cat 4"], ["5", "Cat 5"]].map(function (x) { return '<span><i style="background:' + TCC[x[0]] + '"></i>' + x[1] + '</span>'; }).join("") + '</span>');
    var o = document.querySelector('.wx-lay[data-k="outlook"] .wx-lt');
    if (o) o.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + ["MRGL", "SLGT", "ENH", "MDT", "HIGH"].map(function (k) { return '<span><i style="background:' + OLC[k] + '"></i>' + k + '</span>'; }).join("") + '</span>');
    var r = document.querySelector('.wx-lay[data-k="reports"] .wx-lt');
    if (r) r.insertAdjacentHTML("beforeend", '<span class="wx-keys">' + [["tor", "Tornado"], ["hail", "Hail"], ["wind", "Wind"], ["flood", "Flash flood"], ["snow", "Snow"]].map(function (x) { return '<span><i style="border-radius:50%;background:' + RC[x[0]] + '"></i>' + x[1] + '</span>'; }).join("") + '</span>');
  })();
  $("wx_src").innerHTML = 'Radar: NWS NEXRAD via <a href="https://mesonet.agron.iastate.edu/" target="_blank" rel="noopener">Iowa Environmental Mesonet</a>. Forecast radar: NOAA HRRR. Temperature, rain and snow: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> (CC BY 4.0). Warnings and storm reports: NWS. Tornado tracks: NWS Damage Assessment Toolkit. Hurricanes: NHC and IBTrACS (NOAA NCEI). Outlooks: NOAA SPC.';

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
    var v = gValueAt(lng, lat, f.k); if (isNaN(v)) return "";
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
  var HIT = ["rep", "trk-hit", "nhc-pt", "nhc-track", "nhc-cone", "season-line", "warn-fill", "ol-fill"];
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
    if (!window.maplibregl) { $("wx_when").textContent = "The map could not start in this browser."; step("map"); step("radar"); return; }
    map = new maplibregl.Map({ container: "wx_map", style: style(), bounds: US0, fitBoundsOptions: { padding: PAD() }, minZoom: 1.2, maxZoom: 11,
      attributionControl: false, maplibreLogo: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0, fadeDuration: 200 });
    window.__wxMap = map;   /* QA hook (read-only) */
    map.touchZoomRotate.disableRotation();
    map.dragPan.enable({ linearity: 0.25, easing: function (t) { return 1 - Math.pow(1 - t, 3); }, deceleration: 2200, maxSpeed: 1600 });
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · Weather: NOAA/NWS, IEM, <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>' }), "bottom-right");
    map.on("load", function () {
      var at = document.querySelector(".maplibregl-ctrl-attrib"); if (at) at.classList.remove("maplibregl-compact-show");
      addOverlayLayers(); ready = true; setLayerVis();
      if (AL) map.getSource("warn").setData(AL);
      map.once("idle", function () { step("map"); });
      setTimeout(function () { step("map"); }, 7000);
      if (FRAMES.length) go(IDX, true);
      Promise.all([loadAlerts(), loadStorms(), loadTropical()]).then(function () { step("storms"); }, function () { step("storms"); });
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
  function loadFrames(first) {
    return jget("/api/wxmap/frames").then(function (d) {
      var s = d.sources || {};
      FR = d; ERR.radar = (!d.past.length && !d.forecast.length) ? ((s.past && s.past.reason) || "Radar is unavailable right now") : null;
      var b = document.querySelector('#wx_modes [data-m="radar"]'); b.disabled = !!ERR.radar; b.title = ERR.radar || "";
      if (MODE === "radar") {
        if (ERR.radar && G) { setMode("temp", false); return; }
        var t = FRAMES[IDX] ? FRAMES[IDX].t : null; buildFrames(first ? null : t);
      }
      if (ERR.radar) step("radar");
    }).catch(function (e) {
      ERR.radar = e.reason || "Radar is unavailable right now"; var b = document.querySelector('#wx_modes [data-m="radar"]'); b.disabled = true; b.title = ERR.radar; step("radar");
      if (MODE === "radar") { if (G) setMode("temp", false); else label(); }
    });
  }
  function loadGrid() {
    return jget("/api/wxmap/grid").then(function (d) {
      G = d; gDims(); ERR.grid = null; GIMG = {};
      ["temp", "rain", "snow"].forEach(function (m) { var b = document.querySelector('#wx_modes [data-m="' + m + '"]'); b.disabled = false; b.title = ""; });
      if (map && map.getSource("gA")) { map.getSource("gA").setCoordinates(GCO); map.getSource("gB").setCoordinates(GCO); }
      if (MODE !== "radar") buildFrames(FRAMES[IDX] ? FRAMES[IDX].t : null);
      else if (ERR.radar) setMode("temp", false);
    }).catch(function (e) {
      ERR.grid = "Temperature, rain and snow are unavailable: " + (e.reason || "the forecast source did not answer");
      ["temp", "rain", "snow"].forEach(function (m) { var b = document.querySelector('#wx_modes [data-m="' + m + '"]'); b.disabled = true; b.title = ERR.grid; });
    });
  }
  legend(); label(); boot(); loadFrames(true); loadGrid();
  setInterval(function () { if (document.hidden) return; loadFrames(false); loadAlerts(); }, 180000);
  setInterval(function () { if (!document.hidden) { loadStorms(); loadTropical(); } }, 600000);
  setInterval(function () { if (!document.hidden) loadGrid(); }, 1800000);
  setInterval(function () { if (!document.hidden && !playing) label(); }, 60000);
})();
