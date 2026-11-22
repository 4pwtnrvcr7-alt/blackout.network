/* The Grid (/grid, Nov 21 2026, pt1737u). MapLibre GL + OpenFreeMap tiles, same base style as the heat map (map2.js). Read-only: /api/gridpage/data, /api/gridstatus, /api/grid. */
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
  function num(n) { return n == null ? "–" : Math.round(n).toLocaleString("en-US"); }
  function pct(n) { return n == null ? "–" : (n > 0 ? "+" : "") + n.toFixed(1) + "%"; }
  function ago(ts) {
    var t = Date.parse(ts || ""); if (!isFinite(t)) return "";
    var m = Math.max(0, Math.round((Date.now() - t) / 60000));
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " d ago";
  }
  var COL = { ok: "#2FD67B", strain: "#FF7A1A", out: "#FF3B3B", na: "#7C8190" };
  var LBL = { ok: "Operational", strain: "Strained or degraded", out: "Outage", na: "No live data" };
  function regStatus(s) { return s === "online" ? "ok" : s === "watch" || s === "degraded" ? "strain" : s === "offline" ? "out" : "na"; }
  function regLabel(s) { return { online: "Operational", watch: "Watch: strained", degraded: "Degraded", offline: "Outage", nodata: "No live data", nodata_ok: "No live feed (outside EIA-930)" }[s] || "No live data"; }
  function stStatus(n) { return n >= 1500 ? "out" : n > 0 ? "strain" : "ok"; }
  function wxStatus(r) { return (r.rank || 0) >= 7 ? "out" : "strain"; }
  function spark(series, col) {
    if (!series || series.length < 2) return "";
    var v = series.map(function (x) { return x[1]; }), mn = Math.min.apply(null, v), mx = Math.max.apply(null, v), sp = (mx - mn) || 1;
    var pts = v.map(function (y, i) { return (i / (v.length - 1) * 100).toFixed(1) + "," + (34 - (y - mn) / sp * 30).toFixed(1); }).join(" ");
    return '<svg class="gx-spark" viewBox="0 0 100 36" preserveAspectRatio="none" aria-label="Demand, last ' + v.length + ' hours"><polyline points="' + pts + '" stroke="' + col + '"/></svg>';
  }

  /* ---------- loader ---------- */
  var ld = { map: 0, data: 0, pts: 0 }, ldT0 = Date.now(), ldDone = false;
  function step(k) {
    ld[k] = 1; var li = document.querySelector('.gx-lds li[data-s="' + k + '"]'); if (li) li.classList.add("on");
    var n = ld.map + ld.data + ld.pts; $("gx_ldn").textContent = (n === 3 ? 100 : Math.round(n / 3 * 100)) + "%";
    if (n === 3) finish();
  }
  function finish() {
    if (ldDone) return; ldDone = true;
    setTimeout(function () { document.body.classList.add("gx-ready"); }, Math.max(0, 900 - (Date.now() - ldT0)));
  }
  setTimeout(function () { if (!ldDone) { var m = $("gx_ldmsg"); m.hidden = false; m.textContent = "Still connecting. Showing what has arrived."; setTimeout(finish, 1500); } }, 9000);

  /* ---------- state ---------- */
  var D = null, map = null, touch = matchMedia("(hover: none), (pointer: coarse)").matches, pinned = null, US = [[-125.5, 23.5], [-66, 50]];
  var IDX = {};
  function PAD() { return innerWidth < 768 ? { top: 130, bottom: 90, left: 6, right: 6 } : { top: 90, bottom: 70, left: 70, right: 70 }; }

  function features() {
    var f = [];
    D.regions.forEach(function (r) { if (r.lon == null) return; var s = regStatus(r.status); IDX["r:" + r.id] = r;
      f.push({ type: "Feature", geometry: { type: "Point", coordinates: [r.lon, r.lat] }, properties: { k: "r:" + r.id, kind: "region", s: s, c: COL[s], label: r.id === "SE" ? "SOUTHEAST" : r.id === "WEST" ? "WEST" : r.id } }); });
    D.states.forEach(function (x) { var s = stStatus(x.outages); IDX["s:" + x.st] = x;
      f.push({ type: "Feature", geometry: { type: "Point", coordinates: [x.lon, x.lat] }, properties: { k: "s:" + x.st, kind: "state", s: s, c: COL[s], n: x.outages } }); });
    D.weather.forEach(function (w) { if (w.lat == null || w.lon == null) return; var s = wxStatus(w); IDX["w:" + w.cluster_id] = w;
      f.push({ type: "Feature", geometry: { type: "Point", coordinates: [w.lon, w.lat] }, properties: { k: "w:" + w.cluster_id, kind: "weather", s: s, c: COL[s] } }); });
    if (WD) {
      WD.operators.forEach(function (o) { var s = regStatus(o.status); IDX["i:" + o.id] = o;
        f.push({ type: "Feature", geometry: { type: "Point", coordinates: [o.lon, o.lat] }, properties: { k: "i:" + o.id, kind: "region", s: s, c: COL[s], label: o.id === "GRIDINDIA" ? "INDIA" : o.id === "ENTSOE" ? "ENTSO-E" : o.id } }); });
      var seen = {}; D.weather.forEach(function (w) { seen[w.cluster_id] = 1; });
      WD.wire.forEach(function (x) { if (seen[x.id]) return; var s = (x.rank || 0) >= 7 ? "out" : "strain"; IDX["x:" + x.id] = x;
        f.push({ type: "Feature", geometry: { type: "Point", coordinates: [x.lon, x.lat] }, properties: { k: "x:" + x.id, kind: "weather", s: s, c: COL[s] } }); });
    }
    return { type: "FeatureCollection", features: f };
  }

  /* ---------- card ---------- */
  function cardHTML(k) {
    var o = IDX[k]; if (!o) return "";
    var t = k[0], h = "";
    if (t === "r") {
      var s = regStatus(o.status);
      h = '<span class="st" style="color:' + COL[s] + '"><i style="background:' + COL[s] + '"></i>Grid operator · ' + esc(regLabel(o.status)) + '</span><h3>' + esc(o.name) + '</h3>';
      if (o.demand_mw != null) {
        h += '<dl><dt>Demand</dt><dd>' + num(o.demand_mw) + ' MW</dd><dt>vs forecast</dt><dd>' + pct(o.vs_forecast_pct) + '</dd><dt>vs yesterday</dt><dd>' + pct(o.vs_yesterday_pct) + '</dd>' +
          '<dt>Outages (ODIN)</dt><dd>' + (o.odin ? num(o.odin.outages) : "no report") + '</dd><dt>NWS power alerts</dt><dd>' + (o.nws ? o.nws.power_alerts : 0) + '</dd></dl>' + spark(o.series, COL[s]);
      } else h += '<p class="age">' + esc(o.no_eia || "No hourly demand data from EIA-930 right now.") + '</p>';
      if (o.reasons && o.reasons.length) h += '<ul>' + o.reasons.slice(0, 3).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + '</ul>';
      h += '<p class="age">States: ' + esc((o.states || []).join(", ")) + (o.eia_hour ? ' · EIA hour ' + esc(ago(o.eia_hour)) : '') + '</p>';
      h += '<div class="acts">' + (url(o.site) ? '<a href="' + url(o.site) + '" target="_blank" rel="noopener noreferrer">Operator dashboard</a>' : '') + '<button type="button" class="gx-fly" data-more="gx-regions">All operators</button></div>';
    } else if (t === "i") {
      var si = regStatus(o.status);
      h = '<span class="st" style="color:' + COL[si] + '"><i style="background:' + COL[si] + '"></i>Grid operator · ' + esc(regLabel(o.status)) + '</span><h3>' + esc(o.name) + '</h3>';
      if (o.status !== "nodata") {
        h += '<dl><dt>Demand</dt><dd>' + num(o.demand_mw) + ' MW</dd>' + (o.vs_yesterday_pct != null ? '<dt>vs yesterday</dt><dd>' + pct(o.vs_yesterday_pct) + '</dd>' : '') +
          (o.carbon_g_kwh != null ? '<dt>Carbon intensity</dt><dd>' + esc(o.carbon_g_kwh) + ' g/kWh' + (o.carbon_index ? ' (' + esc(o.carbon_index) + ')' : '') + '</dd>' : '') +
          '<dt>Wire grid alerts, 12 h</dt><dd>' + o.alerts_12h + '</dd></dl>' + spark(o.series, COL[si]);
      }
      if (o.reason) h += '<ul><li>' + esc(o.reason) + '</li></ul>';
      h += '<p class="age">' + (o.source ? esc(o.source) : 'No live feed') + (o.data_time ? ' · ' + esc(ago(o.data_time)) : '') + '</p>';
      h += '<div class="acts">' + (url(o.site) ? '<a href="' + url(o.site) + '" target="_blank" rel="noopener noreferrer">Operator site</a>' : '') + '<button type="button" class="gx-fly" data-more="gx-world">Worldwide</button></div>';
    } else if (t === "x") {
      var sx = (o.rank || 0) >= 7 ? "out" : "strain", dx = /^[0-9a-f]{16}$/.test(o.id || "") ? "/wire/" + o.id : "";
      h = '<span class="st" style="color:' + COL[sx] + '"><i style="background:' + COL[sx] + '"></i>Grid alert · rank ' + esc(o.rank) + '</span><h3>' + esc(o.title) + '</h3>' +
        (o.place ? '<p class="age">' + esc(o.place) + (o.prec && o.prec !== "exact" && o.prec !== "city" ? ' (approximate)' : '') + '</p>' : '') +
        '<p class="age">' + esc(ago(o.t)) + (o.src ? ' · ' + esc(String(o.src).replace(/\s*\([^)]*\)/g, "").slice(0, 40)) : '') + '</p><div class="acts">' + (dx ? '<a href="' + dx + '">Read on the Wire</a>' : '') +
        (url(o.url) ? '<a href="' + url(o.url) + '" target="_blank" rel="noopener noreferrer">Source</a>' : '') + '</div>';
    } else if (t === "s") {
      var s2 = stStatus(o.outages);
      h = '<span class="st" style="color:' + COL[s2] + '"><i style="background:' + COL[s2] + '"></i>State · ' + (o.outages ? (o.outages >= 1500 ? "Major outages" : "Outages reported") : "No outages reported") + '</span><h3>' + esc(o.name) + '</h3>' +
        '<dl><dt>Outages</dt><dd>' + num(o.outages) + '</dd><dt>Utilities reporting</dt><dd>' + o.reporting + ' of ' + o.utilities + '</dd>' + (o.nws.length ? '<dt>NWS power alerts</dt><dd>' + o.nws.length + '</dd>' : '') + '</dl>';
      if (o.top.length) h += '<ul>' + o.top.slice(0, 3).map(function (u) { return "<li>" + esc(u.name) + ": " + num(u.outages) + "</li>"; }).join("") + '</ul>';
      if (o.nws.length) h += '<ul>' + o.nws.slice(0, 2).map(function (a) { return "<li>" + esc(a.event) + "</li>"; }).join("") + '</ul>';
      h += '<p class="age">DOE / ORNL ODIN' + (o.received ? ' · ' + esc(ago(o.received)) : '') + '</p><div class="acts"><button type="button" class="gx-fly" data-state="' + esc(o.st) + '">Utilities and outage maps</button></div>';
    } else {
      var s3 = wxStatus(o), d = /^[0-9a-f]{16}$/.test(o.cluster_id || "") ? "/wire/" + o.cluster_id : "";
      h = '<span class="st" style="color:' + COL[s3] + '"><i style="background:' + COL[s3] + '"></i>Weather threat · rank ' + esc(o.rank) + '</span><h3>' + esc(o.title) + '</h3>' +
        (o.location ? '<p class="age">' + esc(o.location) + '</p>' : '');
      if (o.power && o.power.length) h += '<ul>' + o.power.slice(0, 3).map(function (x) { return "<li>" + esc(x.title || x.label || x) + "</li>"; }).join("") + '</ul>';
      h += '<p class="age">Updated ' + esc(ago(o.updated)) + (o.unconfirmed ? ' · unconfirmed' : '') + '</p><div class="acts">' + (d ? '<a href="' + d + '">Read the story</a>' : '') +
        ((o.links && o.links[0] && url(o.links[0].url)) ? '<a href="' + url(o.links[0].url) + '" target="_blank" rel="noopener noreferrer">Source</a>' : '') + '</div>';
    }
    return '<button type="button" class="gx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' + h;
  }
  var card = null;
  function showCard(k, pt, pin) {
    card = card || $("gx_card");
    if (!pin && pinned) return;
    card.innerHTML = cardHTML(k); card.hidden = false; card.classList.toggle("pin", !!pin);
    if (pin) pinned = k;
    if (!touch && pt && innerWidth >= 768) {
      var w = card.offsetWidth, h = card.offsetHeight, x = pt.x + 18, y = pt.y + 18;
      if (x + w > innerWidth - 12) x = pt.x - w - 18; if (y + h > innerHeight - 12) y = Math.max(12, innerHeight - h - 12);
      card.style.left = Math.max(12, x) + "px"; card.style.top = Math.max(70, y) + "px";
    }
    requestAnimationFrame(function () { card.classList.add("in"); });
  }
  function hideCard(force) {
    if (!card || (pinned && !force)) return;
    pinned = null; card.classList.remove("in", "pin"); setTimeout(function () { if (!card.classList.contains("in")) card.hidden = true; }, 200);
  }

  /* ---------- map ---------- */
  function boot() {
    if (!window.maplibregl) { $("gx_sum").textContent = "The map could not start in this browser."; step("map"); return; }
    map = new maplibregl.Map({ container: "gx_map", style: style(), bounds: US, fitBoundsOptions: { padding: PAD() }, minZoom: 1.2, maxZoom: 12,
      attributionControl: false, maplibreLogo: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0, fadeDuration: 200 });
    window.__gxMap = map; window.__gxIdx = IDX;   /* QA hooks (read-only) */
    map.touchZoomRotate.disableRotation();
    map.dragPan.enable({ linearity: 0.25, easing: function (t) { return 1 - Math.pow(1 - t, 3); }, deceleration: 2200, maxSpeed: 1600 });
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>' }), "bottom-right");
    map.on("load", function () {
      map.addSource("sec", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "sec-fill", type: "fill", source: "sec", paint: { "fill-color": ["coalesce", ["get", "c"], COL.na], "fill-opacity": 0.07 } }, "lbl-country");
      map.addLayer({ id: "sec-line", type: "line", source: "sec", paint: { "line-color": ["coalesce", ["get", "c"], COL.na], "line-opacity": 0.35, "line-width": 1 } }, "lbl-country");
      map.addSource("pts", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "glow", type: "circle", source: "pts", paint: { "circle-color": ["get", "c"], "circle-blur": 1, "circle-opacity": 0.35,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, ["match", ["get", "kind"], "region", 22, "weather", 12, 8], 6, ["match", ["get", "kind"], "region", 40, "weather", 14, 16]] } });
      map.addLayer({ id: "pulse", type: "circle", source: "pts", filter: ["any", ["==", ["get", "s"], "out"], ["all", ["==", ["get", "kind"], "region"], ["==", ["get", "s"], "strain"]]], paint: { "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": ["get", "c"], "circle-stroke-width": 1.4, "circle-radius": 10, "circle-stroke-opacity": 0.6 } });
      map.addLayer({ id: "region", type: "circle", source: "pts", filter: ["==", ["get", "kind"], "region"], paint: { "circle-color": "#05060a", "circle-stroke-color": ["get", "c"], "circle-stroke-width": 3,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 7, 6, 11] } });
      map.addLayer({ id: "region-core", type: "circle", source: "pts", filter: ["==", ["get", "kind"], "region"], paint: { "circle-color": ["get", "c"], "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 3, 6, 5] } });
      map.addLayer({ id: "state", type: "circle", source: "pts", filter: ["==", ["get", "kind"], "state"], paint: { "circle-color": ["get", "c"], "circle-opacity": 0.95, "circle-stroke-color": "#05060a", "circle-stroke-width": 1.2,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, ["interpolate", ["linear"], ["get", "n"], 0, 3, 1500, 5, 20000, 8], 7, ["interpolate", ["linear"], ["get", "n"], 0, 5, 1500, 8, 20000, 13]] } });
      var cv = document.createElement("canvas"); cv.width = cv.height = 32; var cx = cv.getContext("2d"); cx.fillStyle = "#fff"; cx.beginPath(); cx.moveTo(16, 3); cx.lineTo(29, 16); cx.lineTo(16, 29); cx.lineTo(3, 16); cx.closePath(); cx.fill();
      map.addImage("gx-dia", { width: 32, height: 32, data: cx.getImageData(0, 0, 32, 32).data }, { sdf: true, pixelRatio: 2 });
      map.addLayer({ id: "weather", type: "symbol", source: "pts", filter: ["==", ["get", "kind"], "weather"], layout: { "icon-image": "gx-dia", "icon-size": ["interpolate", ["linear"], ["zoom"], 2, 0.8, 7, 1.3], "icon-allow-overlap": true, "icon-ignore-placement": true },
        paint: { "icon-color": ["get", "c"], "icon-halo-color": "#05060a", "icon-halo-width": 1.2 } });
      map.addLayer({ id: "region-lbl", type: "symbol", source: "pts", filter: ["==", ["get", "kind"], "region"], layout: { "text-field": ["get", "label"], "text-font": FB, "text-size": 10.5, "text-letter-spacing": 0.18, "text-offset": [0, 1.6], "text-anchor": "top", "text-allow-overlap": false },
        paint: { "text-color": "rgba(240,240,250,.82)", "text-halo-color": "rgba(5,6,10,.95)", "text-halo-width": 1.4 } });
      var t0 = performance.now(), reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      function tick(now) { var p = ((now - t0) % 2000) / 2000; if (map.getLayer("pulse")) { map.setPaintProperty("pulse", "circle-radius", 8 + p * 22); map.setPaintProperty("pulse", "circle-stroke-opacity", 0.7 * (1 - p)); } requestAnimationFrame(tick); }
      if (!reduce) requestAnimationFrame(tick);
      var LY = ["region", "state", "weather"];
      map.on("mousemove", function (e) {
        if (touch) return;
        var f = map.queryRenderedFeatures(e.point, { layers: LY })[0];
        map.getCanvas().style.cursor = f ? "pointer" : "";
        if (f) showCard(f.properties.k, e.point, false); else hideCard(false);
      });
      map.on("click", function (e) {
        var bb = [[e.point.x - 8, e.point.y - 8], [e.point.x + 8, e.point.y + 8]], f = map.queryRenderedFeatures(bb, { layers: LY })[0];
        if (f) { pinned = null; showCard(f.properties.k, e.point, true); map.easeTo({ center: f.geometry.coordinates, duration: 700, easing: function (t) { return 1 - Math.pow(1 - t, 3); }, offset: (touch || innerWidth < 768) ? [0, -innerHeight * 0.18] : [0, 0] }); }
        else hideCard(true);
      });
      map.once("idle", function () { step("map"); });
      setTimeout(function () { step("map"); }, 7000);
      fetch("/api/gridstatus/sections.geojson").then(function (r) { return r.json(); }).then(function (g) { SECG = g; paint(); }).catch(function () {});
      ready = true; paint();
    });
  }
  var SECG = null, ready = false, WD = null;
  var VIEWS = { us: { b: US }, eu: { b: [[-11, 35], [32, 61]] }, apac: { b: [[66, -46], [179, 50]] }, world: { c: [12, 22], z: innerWidth < 768 ? 0.6 : 1.4 } };
  function region(r) {
    var v = VIEWS[r]; if (!map || !v) return;
    [].forEach.call(document.querySelectorAll("#gx_reg button"), function (b) { b.setAttribute("aria-pressed", b.dataset.r === r ? "true" : "false"); });
    hideCard(true);
    if (v.b) map.fitBounds(v.b, { padding: PAD(), duration: 1400, essential: true, easing: function (t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; } });
    else map.flyTo({ center: v.c, zoom: v.z, speed: 0.9, curve: 1.4, essential: true });
  }
  document.getElementById("gx_reg").addEventListener("click", function (e) { var b = e.target.closest("button[data-r]"); if (b) region(b.dataset.r); });
  function paint() {
    if (!ready || !D) return;
    map.getSource("pts").setData(features());
    if (SECG) {
      var by = {}; D.regions.forEach(function (r) { by[r.id] = COL[regStatus(r.status)]; });
      SECG.features.forEach(function (f) { f.properties.c = by[f.properties.id] || COL.na; });
      map.getSource("sec").setData(SECG);
    }
    step("pts");
  }
  function fly(lon, lat, z) { if (!map) return; map.flyTo({ center: [lon, lat], zoom: z || 5.2, speed: 0.9, curve: 1.5, essential: true }); }

  /* ---------- sections ---------- */
  function sec(id, html) { var b = document.querySelector('.gx-body[data-sec="' + id + '"]'); if (b) b.innerHTML = html; }
  function render() {
    var regs = D.regions.slice().sort(function (a, b) { var o = { out: 0, strain: 1, ok: 2, na: 3 }; return o[regStatus(a.status)] - o[regStatus(b.status)] || (b.demand_mw || 0) - (a.demand_mw || 0); });
    var cnt = { ok: 0, strain: 0, out: 0, na: 0 }; regs.forEach(function (r) { cnt[regStatus(r.status)]++; });
    var totD = regs.reduce(function (a, r) { return a + (r.demand_mw || 0); }, 0), totO = D.states.reduce(function (a, s) { return a + (s.outages || 0); }, 0);
    var worst = cnt.out ? "out" : cnt.strain ? "strain" : regs.length ? "ok" : "na";
    var chip = $("gx_chip"); chip.className = "gx-chip live s-" + worst;
    $("gx_sum").textContent = regs.length ? (cnt.ok + " operational · " + cnt.strain + " strained" + (cnt.out ? " · " + cnt.out + " outage" : "") + " · " + num(totO) + " outages") : "Grid status feed has no data right now";
    $("gx_kpis").innerHTML = '<div class="gx-kpi"><b>' + num(totD) + ' MW</b><span>Lower 48 demand, latest EIA hour</span></div><div class="gx-kpi"><b>' + num(totO) + '</b><span>Outages reported to ODIN</span></div>' +
      '<div class="gx-kpi"><b>' + cnt.ok + ' / ' + regs.length + '</b><span>Operators operational</span></div><div class="gx-kpi"><b>' + (D.swpc ? "G" + D.swpc.g : "–") + '</b><span>Geomagnetic storm level</span></div>';
    sec("gx-regions", regs.length ? regs.map(function (r) { var s = regStatus(r.status);
      return '<div class="gx-row"><h4><i style="background:' + COL[s] + '"></i>' + esc(r.name) + '</h4><span class="n">' + (r.demand_mw != null ? num(r.demand_mw) + " MW" : "–") + '</span>' +
        '<span class="m">' + esc(regLabel(r.status)) + (r.demand_mw != null ? ' · ' + pct(r.vs_forecast_pct) + ' vs forecast · ' + pct(r.vs_yesterday_pct) + ' vs yesterday' : '') + (r.reasons && r.reasons.length ? ' · ' + esc(r.reasons[0]) : '') + '</span>' +
        (r.series && r.series.length > 1 ? '<span class="spk">' + spark(r.series, COL[s]) + '</span>' : '') +
        '<span class="m">' + (r.lon != null ? '<button type="button" class="gx-fly" data-fly="r:' + esc(r.id) + '">Show on map</button> · ' : '') + (url(r.site) ? '<a href="' + url(r.site) + '" target="_blank" rel="noopener noreferrer">Operator dashboard</a>' : '') + '</span></div>'; }).join("")
      : '<p class="gx-empty">The grid status feed has no operator data right now.</p>');
    var sts = D.states.filter(function (s) { return s.outages > 0; }).sort(function (a, b) { return b.outages - a.outages; });
    sec("gx-outages", (sts.length ? sts.slice(0, 20).map(function (s) { var c = COL[stStatus(s.outages)];
      return '<div class="gx-row"><h4><i style="background:' + c + '"></i>' + esc(s.name) + '</h4><span class="n">' + num(s.outages) + '</span><span class="m">' + s.reporting + ' of ' + s.utilities + ' utilities reporting outages' +
        (s.top[0] ? ' · largest: ' + esc(s.top[0].name) + ' (' + num(s.top[0].outages) + ')' : '') + ' · <button type="button" class="gx-fly" data-fly="s:' + esc(s.st) + '">Show on map</button> · <button type="button" class="gx-fly" data-state="' + esc(s.st) + '">Utilities</button></span></div>'; }).join("")
      : '<p class="gx-empty">No utility reporting to ODIN shows outages right now (' + D.states.length + ' states reporting).</p>') +
      '<p class="gx-empty" style="margin-top:10px">Only utilities that report to ODIN are counted, so a quiet state may still have local outages.</p>');
    var wx = D.weather.slice().sort(function (a, b) { return (b.rank || 0) - (a.rank || 0); });
    sec("gx-weather", wx.length ? wx.map(function (w) { var d = /^[0-9a-f]{16}$/.test(w.cluster_id || "") ? "/wire/" + w.cluster_id : "";
      return '<div class="gx-row"><h4><span class="gx-rk' + ((w.rank || 0) >= 7 ? " hi" : "") + '">' + esc(w.rank) + '</span>' + esc(w.title) + '</h4><span class="n"></span><span class="m">' + esc(w.location || "") + (w.location ? ' · ' : '') + 'updated ' + esc(ago(w.updated)) + (w.unconfirmed ? ' · unconfirmed' : '') +
        (w.lat != null ? ' · <button type="button" class="gx-fly" data-fly="w:' + esc(w.cluster_id) + '">Show on map</button>' : '') + (d ? ' · <a href="' + d + '">Story</a>' : '') +
        (w.resources || []).slice(0, 2).map(function (x) { return url(x.url) ? ' · <a href="' + url(x.url) + '" target="_blank" rel="noopener noreferrer">' + esc(x.label) + '</a>' : ""; }).join("") + '</span></div>'; }).join("")
      : '<p class="gx-empty">No ranked weather alerts are threatening infrastructure right now.</p>');
    var sw = D.swpc;
    sec("gx-space", sw ? '<div class="gx-g"><div><b>G' + esc(sw.g) + '</b><span>Geomagnetic</span></div><div><b>S' + esc(sw.s) + '</b><span>Radiation</span></div><div><b>R' + esc(sw.r) + '</b><span>Radio blackout</span></div></div>' +
      '<p class="gx-empty">Next 3 days: ' + (sw.forecast || []).map(function (f) { return esc(f.date) + " G" + esc(f.g); }).join(" · ") + '. G3 and above can stress transformers and long lines.</p><p class="gx-empty">NOAA SWPC · ' + esc(ago(sw.time)) +
      (url(sw.url) ? ' · <a href="' + url(sw.url) + '" target="_blank" rel="noopener noreferrer">Scale explained</a>' : '') + '</p>' : '<p class="gx-empty">The NOAA space weather feed has no data right now.</p>');
    var opts = D.states.slice().sort(function (a, b) { return a.name < b.name ? -1 : 1; }).map(function (s) { return '<option value="' + esc(s.st) + '">' + esc(s.name) + '</option>'; }).join("");
    sec("gx-local", '<select class="gx-sel" id="gx_st" aria-label="Choose a state"><option value="">Choose a state</option>' + opts + '</select><div id="gx_stv"><p class="gx-empty">Pick a state to see its utilities with outage map links, active NWS alerts, open FEMA shelters and recent outage reports.</p></div>');
    var fr = D.freshness || {};
    sec("gx-sources", '<ul style="margin:0;padding-left:18px">' + (D.sources || []).map(function (s) { return '<li><a href="' + url(s.url) + '" target="_blank" rel="noopener noreferrer">' + esc(s.name) + '</a></li>'; }).join("") +
      '<li>BLACKOUT.NETWORK scanner and watch feeds (CISA ICS, NOAA SWPC alerts, ERCOT)</li></ul><p class="gx-empty" style="margin-top:10px">Data age: ' +
      ["eia", "odin", "nws", "swpc", "shelters"].map(function (k) { return k.toUpperCase() + " " + (fr[k] && fr[k].age_min != null ? fr[k].age_min + " min" : "no data"); }).join(" · ") +
      '. Operator status is our own reading of these feeds, not an official operator status.</p>');
    $("gx_st").addEventListener("change", function () { loadState(this.value); });
    renderWorld();
  }
  function renderWorld() {
    if (!WD) return;
    var ops = WD.operators.slice().sort(function (a, b) { var o = { online: 0, watch: 1, degraded: 1, offline: 1, nodata: 2 }; return (o[a.status] || 2) - (o[b.status] || 2); });
    var h = '<p class="gx-k" style="margin-top:6px">Operators outside the U.S.</p>' + ops.map(function (o) { var s = regStatus(o.status);
      return '<div class="gx-row"><h4><i style="background:' + COL[s] + '"></i>' + esc(o.name) + '</h4><span class="n">' + (o.status !== "nodata" && o.demand_mw != null ? num(o.demand_mw) + " MW" : "No live data") + '</span>' +
        '<span class="m">' + (o.status !== "nodata" ? esc(regLabel(o.status)) + (o.vs_yesterday_pct != null ? ' · ' + pct(o.vs_yesterday_pct) + ' vs yesterday' : '') + (o.carbon_g_kwh != null ? ' · ' + esc(o.carbon_g_kwh) + ' g CO2/kWh' : '') + ' · ' + esc(ago(o.data_time)) : esc(o.reason || "No live feed")) +
        ' · <button type="button" class="gx-fly" data-fly="i:' + esc(o.id) + '">Show on map</button>' + (url(o.site) ? ' · <a href="' + url(o.site) + '" target="_blank" rel="noopener noreferrer">Operator site</a>' : '') + '</span>' +
        (o.series && o.series.length > 1 && o.status !== "nodata" ? '<span class="spk">' + spark(o.series, COL[s]) + '</span>' : '') + '</div>'; }).join("");
    var wx = WD.wire.slice(0, 25);
    h += '<p class="gx-k" style="margin-top:16px">Grid and blackout alerts on the Wire, last 7 days</p>' + (wx.length ? wx.map(function (x) { var d = /^[0-9a-f]{16}$/.test(x.id || "") ? "/wire/" + x.id : "";
      return '<div class="gx-row"><h4><span class="gx-rk' + ((x.rank || 0) >= 7 ? " hi" : "") + '">' + esc(x.rank) + '</span>' + esc(x.title) + '</h4><span class="n"></span><span class="m">' + esc(x.place || x.cc || "") + ' · ' + esc(ago(x.t)) +
        ' · <button type="button" class="gx-fly" data-fly="x:' + esc(x.id) + '">Show on map</button>' + (d ? ' · <a href="' + d + '">Story</a>' : '') + '</span></div>'; }).join("")
      : '<p class="gx-empty">No grid or blackout alerts with a place on the Wire in the last 7 days.</p>');
    h += '<p class="gx-empty" style="margin-top:10px">Live operator feeds refresh every ' + Math.round((WD.ttl_s || 300) / 60) + ' minutes. Operators without a free public feed show as no live data; nothing is estimated.</p>';
    sec("gx-world", h);
  }
  function loadWorld() {
    return fetch("/api/gridpage/world").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (w) {
      WD = w; WD.operators = WD.operators || []; WD.wire = WD.wire || []; renderWorld(); if (D) paint();
    }).catch(function () { sec("gx-world", '<p class="gx-empty">Worldwide grid data could not be loaded right now.</p>'); });
  }
  function loadThreats() {
    fetch("/api/grid?limit=60").then(function (r) { return r.json(); }).then(function (g) {
      var kinds = g.kinds || {}, it = (g.items || []).filter(function (x) { return x.list !== "suppressed"; }).slice(0, 15);
      var feeds = (g.feeds || []).map(function (f) { return esc(f.label) + (f.ok ? "" : " (not responding)"); }).join(" · ");
      sec("gx-threats", (it.length ? it.map(function (x) { var u = (x.links && x.links[0] && x.links[0].url) || x.url || "", d = x.origin === "scanner" && x.list === "wire" && /^[0-9a-f]{16}$/.test(x.id || "") ? "/wire/" + x.id : url(u);
        var r = x.rank; return '<div class="gx-row"><h4>' + (r != null ? '<span class="gx-rk' + (r >= 7 ? " hi" : "") + '">' + esc(r) + '</span>' : '') + esc(String(x.title || "").replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{1F3FB}-\u{1F3FF}]/gu, "").split("\n").filter(function (l) { return l.trim() && !/^\S+\.\S+\/\S*\s*$/.test(l.trim()); })[0] || "").slice(0, 160) + '</h4><span class="n"></span><span class="m">' +
          (kinds[x.kind] ? '<span class="gx-tag">' + esc(kinds[x.kind]) + '</span>' : '') + esc(ago(x.first_seen || x.event_time)) + (d ? ' · <a href="' + d + '"' + (d[0] === "/" ? "" : ' target="_blank" rel="noopener noreferrer"') + '>Open</a>' : '') + '</span></div>'; }).join("")
        : '<p class="gx-empty">No grid threats in the watch list right now.</p>') + (feeds ? '<p class="gx-empty" style="margin-top:10px">Watch feeds: ' + feeds + '</p>' : ''));
    }).catch(function () { sec("gx-threats", '<p class="gx-empty">The grid threat list could not be loaded right now.</p>'); });
  }
  function loadState(st) {
    var v = $("gx_stv"); if (!st) return;
    v.innerHTML = '<p class="gx-empty">Loading…</p>';
    fetch("/api/gridstatus/state?st=" + encodeURIComponent(st)).then(function (r) { return r.json(); }).then(function (o) {
      var h = "", od = {}; (o.odin || []).forEach(function (u) { od[u.eia] = u; });
      h += '<p class="gx-k" style="margin-top:6px">Utilities</p>' + ((o.utilities || []).length ? (o.utilities || []).slice(0, 12).map(function (u) { var x = od[u.eia];
        return '<div class="gx-row"><h4>' + esc(u.name) + '</h4><span class="n">' + (x ? num(x.outages) + " out" : "") + '</span><span class="m">' + num(u.customers) + ' customers' + (url(u.web) ? ' · <a href="' + url(u.web) + '" target="_blank" rel="noopener noreferrer">Website and outage map</a>' : '') + '</span></div>'; }).join("") : '<p class="gx-empty">No utility list for this state.</p>');
      h += '<p class="gx-k" style="margin-top:14px">Severe NWS alerts</p>' + ((o.nws || []).length ? (o.nws || []).slice(0, 8).map(function (a) { return '<div class="gx-row"><h4>' + esc(a.event) + '</h4><span class="n"></span><span class="m">' + esc(a.headline) + '</span></div>'; }).join("") : '<p class="gx-empty">No severe or extreme NWS alerts.</p>');
      h += '<p class="gx-k" style="margin-top:14px">Open FEMA shelters</p>' + ((o.shelters || []).length ? (o.shelters || []).map(function (s) { return '<div class="gx-row"><h4>' + esc(s.name) + '</h4><span class="n"></span><span class="m">' + esc([s.address, s.city].filter(Boolean).join(", ")) + (s.population != null ? ' · ' + esc(s.population) + ' people' : '') + '</span></div>'; }).join("") : '<p class="gx-empty">No open FEMA shelters listed.</p>');
      if ((o.reports || []).length) h += '<p class="gx-k" style="margin-top:14px">Recent outage reports (unconfirmed)</p>' + o.reports.slice(0, 6).map(function (r) { return '<div class="gx-row"><h4>' + esc(r.title) + '</h4><span class="n"></span><span class="m">' + esc(r.source) + ' · ' + esc(ago(r.time)) + (url(r.url) ? ' · <a href="' + url(r.url) + '" target="_blank" rel="noopener noreferrer">Source</a>' : '') + '</span></div>'; }).join("");
      v.innerHTML = h;
    }).catch(function () { v.innerHTML = '<p class="gx-empty">State details could not be loaded right now.</p>'; });
  }

  /* ---------- panel ---------- */
  function openMore(secId) {
    var p = $("gx_more"); p.hidden = false; document.body.classList.add("gx-more-on"); $("gx_more_btn").setAttribute("aria-expanded", "true"); hideCard(true);
    if (secId) { var d = $(secId); if (d) { d.open = true; setTimeout(function () { var sc = $("gx_scroll"); sc.scrollTo({ top: d.offsetTop - 8, behavior: "smooth" }); }, 380); } }
  }
  function closeMore() { document.body.classList.remove("gx-more-on"); $("gx_more_btn").setAttribute("aria-expanded", "false"); setTimeout(function () { if (!document.body.classList.contains("gx-more-on")) $("gx_more").hidden = true; }, 520); }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-fly],[data-more],[data-state],.gx-cx"); if (!b) return;
    if (b.classList.contains("gx-cx")) return hideCard(true);
    if (b.dataset.more) return openMore(b.dataset.more);
    if (b.dataset.state) { openMore("gx-local"); var s = $("gx_st"); if (s) { s.value = b.dataset.state; loadState(b.dataset.state); } return; }
    var o = IDX[b.dataset.fly]; if (!o) return;
    if (innerWidth < 768) closeMore();
    fly(o.lon, o.lat, b.dataset.fly[0] === "r" ? 4.6 : 6);
    map && map.once("moveend", function () { showCard(b.dataset.fly, map.project([o.lon, o.lat]), true); });
  });
  $("gx_more_btn").addEventListener("click", function () { openMore(); });
  $("gx_more_x").addEventListener("click", closeMore);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { if (pinned) hideCard(true); else closeMore(); } });
  $("gx_zin").addEventListener("click", function () { map && map.zoomIn({ duration: 450 }); });
  $("gx_zout").addEventListener("click", function () { map && map.zoomOut({ duration: 450 }); });
  $("gx_home").addEventListener("click", function () { map && map.fitBounds(US, { padding: PAD(), duration: 1100 }); });
  /* swipe the sheet down to close (phones) */
  (function () { var g = document.querySelector(".gx-grab"), y0 = null; var mh = document.querySelector(".gx-mh");
    [g, mh].forEach(function (el) { if (!el) return; el.addEventListener("touchstart", function (e) { y0 = e.touches[0].clientY; }, { passive: true });
      el.addEventListener("touchend", function (e) { if (y0 != null && e.changedTouches[0].clientY - y0 > 60) closeMore(); y0 = null; }); }); })();

  /* ---------- go ---------- */
  function load() {
    return fetch("/api/gridpage/data", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      D = d; D.regions = D.regions || []; D.states = D.states || []; D.weather = D.weather || [];
      step("data"); render(); paint(); if (!ready) setTimeout(function () { step("pts"); }, 6000);
    }).catch(function () { $("gx_sum").textContent = "Grid status is unavailable right now"; step("data"); step("pts"); });
  }
  boot(); load(); loadThreats(); loadWorld();
  setInterval(function () { if (!document.hidden) { load(); loadWorld(); } }, 120000);
})();
