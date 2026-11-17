/* BLACKOUT.NETWORK full-screen heat map (/map, Nov 17 2026).
   One MapLibre GL renderer: OpenFreeMap vector base restyled to the site theme, the heat as a native "heatmap" layer and the alerts
   as native circle layers in the same WebGL scene, so heat, dots and labels pan and zoom as one piece (no overlay canvas, no drift).
   Data: /api/signal/heat (the Heat Map tab's located alerts, 60 s cache). Filters: view, rank, window, topic. Read-only. */
(function () {
  "use strict";
  var d = document, $ = function (id) { return d.getElementById(id); };
  var CFG = window.BNM_CFG || {};
  var C = { calm: "#6B7076", elev: "#C9CDD3", high: "#FF4D4F", y: "#F2F2F4", ink: "#F0F0FA" };
  var RN = ["Noise", "Low", "Low", "Guarded", "Elevated", "Elevated", "Elevated", "Major", "Severe", "Critical", "Catastrophic"];
  var TOPIC = { "war/conflict": "Conflict", "natural disaster": "Weather & quakes", "disease": "Health", "cyber": "Cyber", "political": "Politics", "financial": "Markets", "space weather": "Space weather", "infrastructure": "Infrastructure" };
  var state = { view: CFG.view || "world", rank: CFG.rank || "", window: CFG.window || "168", topic: CFG.topic || "" };
  var rows = [], meta = {}, map = null, ready = false, loadedAt = 0;
  var touch = matchMedia("(pointer:coarse)").matches;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var VIEWS = { world: { center: [15, 22], zoom: touch ? 0.9 : 1.75 }, us: { bounds: [[-125.5, 24], [-66.5, 49.6]] }, conflicts: { center: [35, 33], zoom: touch ? 2.1 : 2.8 } };

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function band(r) { return r >= 7 ? "high" : r >= 4 ? "elev" : "calm"; }
  function et(iso) { var t = Date.parse(iso); if (!isFinite(t)) return ""; try { return new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(t)) + " ET"; } catch (e) { return ""; } }
  function inUS(r) { var lat = r.lat, lon = r.lon; if (String(r.cc).toUpperCase() === "US") return true;
    return (lat >= 24.5 && lat <= 49.5 && lon >= -125 && lon <= -66.5) || (lat >= 51 && lat <= 72 && lon >= -170 && lon <= -129) || (lat >= 18.5 && lat <= 22.5 && lon >= -161 && lon <= -154) || (lat >= 17.5 && lat <= 18.6 && lon >= -67.5 && lon <= -65); }
  function dest(r) {
    if (/^[0-9a-f]{16}$/.test(String(r.id))) return { href: "/wire/" + r.id, ext: false, label: "Read on blackout.network" };
    if (/^https?:\/\//i.test(r.url || "")) return { href: r.url, ext: true, label: "Source: " + (r.src || "link").replace(/\s*\([^)]*\)/g, "").slice(0, 40) };
    return { href: "/wire", ext: false, label: "Open The Wire" };
  }

  /* ---------- base style: OpenFreeMap vector tiles, our palette, few quiet labels ---------- */
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

  /* ---------- data ---------- */
  function pass(r, f, now, ignoreView) {
    if (f.rank === "7" && r.rank < 7) return false;
    if (f.rank === "4" && (r.rank < 4 || r.rank > 6)) return false;
    if (f.rank === "0" && r.rank > 3) return false;
    if (f.topic && r.cat !== f.topic) return false;
    if (f.window) { var t = Date.parse(r.t); if (!isFinite(t) || now - t > (+f.window) * 3600000) return false; }
    if (!ignoreView && f.view === "conflicts" && r.cat !== "war/conflict") return false;
    return true;
  }
  function fc(list) {
    return { type: "FeatureCollection", features: list.map(function (r, i) {
      return { type: "Feature", id: i, geometry: { type: "Point", coordinates: [r.lon, r.lat] },
        properties: { i: r.i, rank: r.rank, w: Math.max(0.08, Math.pow(r.rank / 10, 1.6)), b: band(r.rank) } }; }) };
  }
  var shown = [];
  function apply(fit) {
    var now = Date.now(), base = rows.filter(function (r) { return pass(r, state, now, true); });
    shown = base.filter(function (r) { return pass(r, state, now, false); });
    if (state.view === "us") shown = shown.filter(inUS);
    var n = { world: base.length, us: base.filter(inUS).length, conflicts: base.filter(function (r) { return r.cat === "war/conflict"; }).length };
    [].forEach.call(d.querySelectorAll("[data-n]"), function (e) { e.textContent = n[e.getAttribute("data-n")] || 0; });
    var hi = shown.filter(function (r) { return r.rank >= 7; }).length;
    $("bnm_count").textContent = shown.length.toLocaleString() + " located alerts" + (hi ? " · " + hi + " high" : "") + " · " + ({ "24": "24 hours", "72": "3 days", "168": "7 days" }[state.window] || "");
    $("bnm_chip").className = "bnm-chip" + (hi ? " hot" : "");
    var active = (state.rank ? 1 : 0) + (state.topic ? 1 : 0) + (state.window !== "168" ? 1 : 0) + (state.view !== "world" ? 1 : 0);
    $("bnm_fn").hidden = !active; $("bnm_fn").textContent = active;
    paintSeg();
    if (ready) { map.getSource("heat").setData(fc(shown)); map.getSource("dots").setData(fc(shown)); }
    if (fit) frame(true);
    try { var q = new URLSearchParams(); if (state.view !== "world") q.set("view", state.view); if (state.rank) q.set("rank", state.rank); if (state.window !== "168") q.set("window", state.window); if (state.topic) q.set("topic", state.topic);
      history.replaceState(null, "", "/map" + (q.toString() ? "?" + q : "")); } catch (e) {}
  }
  function frame(anim) {
    if (!map) return; var v = VIEWS[state.view] || VIEWS.world, o = { duration: anim && !reduce ? 1100 : 0, essential: true };
    if (v.bounds) map.fitBounds(v.bounds, Object.assign({ padding: touch ? 24 : 80 }, o)); else map.flyTo(Object.assign({ center: v.center, zoom: v.zoom }, o));
  }
  function paintSeg() {
    [].forEach.call(d.querySelectorAll(".bnm-seg"), function (g) { var k = g.getAttribute("data-k");
      [].forEach.call(g.querySelectorAll("button"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-v") === String(state[k]) ? "true" : "false"); }); });
    $("bnm_topic").value = state.topic;
  }
  function load(fresh) {
    return fetch("/api/signal/heat", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) {
      var cols = j.cols || [], ix = {}; cols.forEach(function (c, i) { ix[c] = i; });
      rows = (j.rows || []).map(function (a, i) { return { i: i, id: a[ix.id], lat: +a[ix.lat], lon: +a[ix.lon], rank: +a[ix.rank] || 0, cat: a[ix.cat] || "", t: a[ix.t] || "", title: a[ix.title] || "",
        place: a[ix.place] || "", prec: a[ix.prec] || "", watch: +a[ix.watch] || 0, src: a[ix.src] || "", url: a[ix.url] || "", cc: a[ix.cc] || "", fam: +a[ix.fam] || 0 }; })
        .filter(function (r) { return isFinite(r.lat) && isFinite(r.lon) && !(r.lat === 0 && r.lon === 0) && Math.abs(r.lat) <= 90 && Math.abs(r.lon) <= 180; });
      meta = j; loadedAt = Date.now();
      var cats = {}; rows.forEach(function (r) { if (r.cat) cats[r.cat] = (cats[r.cat] || 0) + 1; });
      var sel = $("bnm_topic"), keep = state.topic;
      sel.innerHTML = '<option value="">All topics</option>' + Object.keys(cats).sort(function (a, b) { return cats[b] - cats[a]; }).map(function (k) { return '<option value="' + esc(k) + '">' + esc(TOPIC[k] || k) + " (" + cats[k] + ")</option>"; }).join("");
      if (keep && !cats[keep]) sel.insertAdjacentHTML("beforeend", '<option value="' + esc(keep) + '">' + esc(TOPIC[keep] || keep) + "</option>");
      var cv = j.coverage || {};
      $("bnm_cov").textContent = (cv.located != null ? cv.located.toLocaleString() + " of " + (cv.total || 0).toLocaleString() + " alerts from the last " + (j.window_days || 7) + " days have a place" + (cv.pct != null ? " (" + cv.pct + "%)" : "") + ". " : "") + "Country-level places are approximate.";
      apply(false); stamp();
    }).catch(function () { $("bnm_count").textContent = "The map data did not load. Try the refresh button."; });
  }
  function stamp() {
    var el = $("bnm_up"); if (!el || !window.BNT || !BNT.up) return;
    var at = Date.parse(meta.generated || "") || loadedAt, nx = loadedAt + 300000;
    BNT.up(el, { label: "the heat layer", at: at, next: nx, run: function () { return load(true); } });
  }

  /* ---------- card (tap a dot) ---------- */
  function card(list) {
    var el = $("bnm_card"); if (!list.length) { el.hidden = true; return; }
    list.sort(function (a, b) { return b.rank - a.rank; });
    var r = list[0], b = band(r.rank), dd = dest(r), more = list.length - 1;
    el.innerHTML = '<button type="button" class="bnm-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' +
      '<div class="bnm-ct"><span class="bnm-rk ' + b + '"><b>' + r.rank + "</b>/10 · " + RN[Math.max(0, Math.min(10, r.rank))] + "</span>" + (r.watch ? '<span class="bnm-tag">Single source</span>' : "") + "</div>" +
      "<h2>" + esc(r.title) + "</h2>" +
      '<p class="bnm-cm">' + [esc(r.place) + (r.prec === "country" ? " (approximate)" : ""), esc(TOPIC[r.cat] || r.cat), esc(et(r.t)), r.fam > 1 ? r.fam + " sources" : ""].filter(Boolean).join(" · ") + "</p>" +
      '<a class="bnm-go" href="' + esc(dd.href) + '"' + (dd.ext ? ' target="_blank" rel="noopener"' : "") + ">" + esc(dd.label) + " &rarr;</a>" +
      (more ? '<details class="bnm-more"><summary>' + more + " more here</summary><ul>" + list.slice(1, 25).map(function (x) { var y = dest(x);
        return '<li><a href="' + esc(y.href) + '"' + (y.ext ? ' target="_blank" rel="noopener"' : "") + '><span class="bnm-rk ' + band(x.rank) + '"><b>' + x.rank + "</b></span>" + esc(x.title) + "</a></li>"; }).join("") + "</ul></details>" : "");
    el.hidden = false; el.classList.remove("in"); void el.offsetWidth; el.classList.add("in");
    el.querySelector(".bnm-cx").onclick = function () { el.hidden = true; };
  }

  /* ---------- header: slides away, small X stays ---------- */
  var headT = 0;
  function head(show) {
    d.body.classList.toggle("bnm-hd-on", !!show); clearTimeout(headT);
    if (show) headT = setTimeout(function () { if (!d.querySelector(".bnm-head :focus") && !d.querySelector(".bnm-head .bn-menu[open], .bn-drawer.open, body.bn-menu-open")) head(false); }, 3200);
  }
  function back() {
    var ref = d.referrer || "";
    try { if (ref && new URL(ref).origin === location.origin && history.length > 1 && !/\/map(\?|$)/.test(new URL(ref).pathname)) { history.back(); return; } } catch (e) {}
    location.href = "/live";
  }

  /* ---------- map ---------- */
  function boot() {
    if (!window.maplibregl) { $("bnm_count").textContent = "The map could not start in this browser."; return; }
    var v = VIEWS[state.view] || VIEWS.world, t0 = Date.now();
    map = new maplibregl.Map({
      container: "bnm_map", style: style(), center: v.center || [-96, 38], zoom: v.zoom != null ? v.zoom : 3, minZoom: 0.4, maxZoom: 15,
      attributionControl: false, maplibreLogo: false, dragRotate: false, pitchWithRotate: false, touchPitch: false,
      cooperativeGestures: false, renderWorldCopies: true, fadeDuration: 180, maxPitch: 0, hash: false
    });
    if (v.bounds) map.fitBounds(v.bounds, { padding: touch ? 24 : 80, duration: 0 });
    window.__bnmMap = map;   /* QA hook (read-only use in tests) */
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation && map.keyboard.disableRotation();
    map.dragPan.enable({ linearity: 0.25, easing: function (t) { return 1 - Math.pow(1 - t, 3); }, deceleration: 2200, maxSpeed: 1600 });
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>' }), "bottom-right");
    map.on("load", function () {
      map.addSource("heat", { type: "geojson", data: fc(shown), buffer: 64, tolerance: 0.4 });
      map.addSource("dots", { type: "geojson", data: fc(shown), cluster: true, clusterRadius: 34, clusterMaxZoom: 9,
        clusterProperties: { mx: ["max", ["get", "rank"]] } });
      var before = "lbl-country";
      map.addLayer({ id: "heat", type: "heatmap", source: "heat", maxzoom: 12, paint: {
        "heatmap-weight": ["get", "w"],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 0.7, 3, 1.2, 6, 2.2, 10, 3.2],
        "heatmap-radius": ["interpolate", ["exponential", 1.6], ["zoom"], 0, 9, 2, 16, 4, 28, 7, 48, 10, 70],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 0, 0.9, 6, 0.85, 9, 0.55, 12, 0.25],
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
          0, "rgba(0,0,0,0)", 0.06, "rgba(124,196,255,0.10)", 0.18, "rgba(107,112,118,0.30)", 0.36, "rgba(242,242,244,0.50)",
          0.58, "rgba(201,205,211,0.70)", 0.8, "rgba(255,77,79,0.85)", 1, "rgba(255,226,205,0.95)"] } }, before);
      map.addLayer({ id: "cl", type: "circle", source: "dots", filter: ["has", "point_count"], minzoom: 2.6, paint: {
        "circle-color": ["step", ["get", "mx"], C.calm, 4, C.elev, 7, C.high], "circle-opacity": ["interpolate", ["linear"], ["zoom"], 2.6, 0, 3.4, 0.22],
        "circle-stroke-color": ["step", ["get", "mx"], C.calm, 4, C.elev, 7, C.high], "circle-stroke-width": 1, "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 2.6, 0, 3.4, 0.85],
        "circle-radius": ["interpolate", ["linear"], ["get", "point_count"], 2, 11, 20, 16, 200, 24] } });
      map.addLayer({ id: "cl-n", type: "symbol", source: "dots", filter: ["has", "point_count"], minzoom: 2.6, layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": FB, "text-size": 11, "text-allow-overlap": true },
        paint: { "text-color": C.ink, "text-opacity": ["interpolate", ["linear"], ["zoom"], 2.6, 0, 3.4, 1] } });
      map.addLayer({ id: "pt", type: "circle", source: "dots", filter: ["!", ["has", "point_count"]], paint: {
        "circle-color": ["match", ["get", "b"], "high", C.high, "elev", C.elev, C.calm],
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, ["+", 1, ["*", 0.25, ["get", "rank"]]], 6, ["+", 3, ["*", 0.5, ["get", "rank"]]], 12, ["+", 5, ["*", 0.6, ["get", "rank"]]]],
        "circle-opacity": ["interpolate", ["linear"], ["zoom"], 1, 0.0, 2.6, 0.75, 5, 0.95],
        "circle-stroke-color": "#05060a", "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 2, 0, 5, 1.5],
        "circle-blur": ["interpolate", ["linear"], ["zoom"], 1, 0.6, 5, 0.1] } });
      map.addLayer({ id: "pt-glow", type: "circle", source: "dots", filter: ["all", ["!", ["has", "point_count"]], [">=", ["get", "rank"], 7]], paint: {
        "circle-color": C.high, "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 6, 8, 16], "circle-opacity": ["interpolate", ["linear"], ["zoom"], 2, 0, 3, 0.18], "circle-blur": 1 } }, "pt");
      ready = true; apply(false);
      /* fade in once tiles + heat have drawn (no flash, no layout shift); 5 s safety net */
      var reveal = function () { d.body.classList.add("bnm-ready"); };
      var tryReveal = function () { if (rows.length || Date.now() - t0 > 2500) { reveal(); map.off("idle", tryReveal); } };
      map.on("idle", tryReveal); setTimeout(reveal, 5000);
    });
    var hit = ["pt", "cl"];
    map.on("click", function (e) {
      var f = map.queryRenderedFeatures([[e.point.x - 10, e.point.y - 10], [e.point.x + 10, e.point.y + 10]], { layers: hit.filter(function (l) { return map.getLayer(l); }) });
      if (!f.length) { $("bnm_card").hidden = true; closePanel(); return; }
      var g = f[0];
      if (g.properties.cluster) {
        var src = map.getSource("dots"), cid = g.properties.cluster_id;
        if (map.getZoom() >= 9.5) {
          Promise.resolve(src.getClusterLeaves(cid, 50, 0)).then(function (lv) { card(lv.map(function (x) { return rows[x.properties.i]; }).filter(Boolean)); });
        } else Promise.resolve(src.getClusterExpansionZoom(cid)).then(function (z) { map.easeTo({ center: g.geometry.coordinates, zoom: Math.min(z + 0.2, 12), duration: reduce ? 0 : 650 }); });
        return;
      }
      var list = f.filter(function (x) { return !x.properties.cluster; }).map(function (x) { return rows[x.properties.i]; }).filter(Boolean);
      var seen = {}; card(list.filter(function (r) { if (seen[r.i]) return false; seen[r.i] = 1; return true; }));
    });
    hit.forEach(function (l) { map.on("mouseenter", l, function () { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", l, function () { map.getCanvas().style.cursor = ""; }); });
    map.on("movestart", function (e) { if (e.originalEvent) head(false); });
    /* frame-time probe for QA: window.__bnmFrames */
    var last = 0, fr = window.__bnmFrames = []; map.on("render", function () { var n = performance.now(); if (last && n - last < 1000) { fr.push(n - last); if (fr.length > 600) fr.shift(); } last = n; });
  }

  /* ---------- panel ---------- */
  function openPanel() { var p = $("bnm_panel"); p.hidden = false; requestAnimationFrame(function () { p.classList.add("in"); }); $("bnm_fbtn").setAttribute("aria-expanded", "true"); $("bnm_card").hidden = true; }
  function closePanel() { var p = $("bnm_panel"); if (p.hidden) return; p.classList.remove("in"); $("bnm_fbtn").setAttribute("aria-expanded", "false"); setTimeout(function () { if (!p.classList.contains("in")) p.hidden = true; }, 260); }

  function wire() {
    $("bnm_fbtn").onclick = function () { $("bnm_panel").hidden ? openPanel() : closePanel(); };
    $("bnm_pclose").onclick = closePanel;
    [].forEach.call(d.querySelectorAll(".bnm-seg"), function (g) {
      g.addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; var k = g.getAttribute("data-k"), v = b.getAttribute("data-v");
        if (state[k] === v) return; state[k] = v; apply(k === "view"); }); });
    $("bnm_topic").onchange = function () { state.topic = this.value; apply(false); };
    $("bnm_lh").onchange = function () { if (ready) map.setLayoutProperty("heat", "visibility", this.checked ? "visible" : "none"); };
    $("bnm_ld").onchange = function () { var on = this.checked ? "visible" : "none"; if (ready) ["pt", "pt-glow", "cl", "cl-n"].forEach(function (l) { map.setLayoutProperty(l, "visibility", on); }); };
    $("bnm_zin").onclick = function () { map && map.zoomIn({ duration: reduce ? 0 : 300 }); };
    $("bnm_zout").onclick = function () { map && map.zoomOut({ duration: reduce ? 0 : 300 }); };
    $("bnm_x").onclick = back;
    $("bnm_report").onclick = function () { var f = d.querySelector(".bnr-fab"); if (f) f.click(); else location.href = "/sources"; };
    $("bnm_edge").addEventListener("mouseenter", function () { head(true); });
    $("bnm_edge").addEventListener("click", function () { head(true); });
    var hd = $("bnm_head");
    hd.addEventListener("mouseenter", function () { clearTimeout(headT); });
    hd.addEventListener("mouseleave", function () { head(true); });
    hd.addEventListener("focusin", function () { head(true); });
    d.addEventListener("keydown", function (e) { if (e.key === "Escape") { closePanel(); $("bnm_card").hidden = true; } });
    head(true);
  }
  function start() { wire(); paintSeg(); boot(); load(false); setInterval(function () { if (!d.hidden && Date.now() - loadedAt > 300000) load(false); }, 60000); }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", start); else start();
})();
