/* Water layer + panel on /grid. Lazy: nothing is fetched until the Water chip is on (or /grid/water[/id] is opened). Not part of the loader weights.
   Plants: /api/netmap/water?w&s&e&n&z -> viewport clusters (z<9) or capped points (z>=9) from a read-only SQLite store, every plant cites a source.
   Status dots: /api/water/map (slim). Panel list: /api/water/data?limit=30 (severity, then US first, then recency; paged). One item: /api/water/item?id=.
   /grid/water (no item) recenters on the lower 48, with padding so the panel does not hide the United States. */
(function () {
  var COL = { dnd: "#FF4D4F", boil: "#F0F0FA", viol: "#6EA8FE", snc: "#B79CFF", news: "#8E97A6", dw: "#2EE6D6", ww: "#C084FC" };
  var LABEL = { dnd: "Do not drink or use", boil: "Boil water", viol: "Drinking-water violation", serious: "Serious violation", snc: "Sewage plant noncompliance", news: "News report" };
  var EMPTY = { type: "FeatureCollection", features: [] };
  var US = [[-125.5, 23.5], [-66, 50]];   /* same box as net.js: the lower 48, not Canada */
  var map = null, on = false, sel = "", bootTried = false, vt = 0, vctl = null, lastKey = "", info = null, fitted = false;
  var curFeats = [], stFeats = [], adv = [], advTotal = 0, advPulled = false, items = {}, statusRows = null;
  var plantTotal = (window.BN_WATER && window.BN_WATER.plants) || 0;
  var plantCountries = (window.BN_WATER && window.BN_WATER.countries) || 0;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function href(u) { try { var x = new URL(u, "https://blackout.network"); if (x.protocol === "http:" || x.protocol === "https:") return x.href; } catch (e) {} return "#"; }
  function getJSON(url, sig) { return fetch(url, { credentials: "same-origin", signal: sig }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function wantOpen() { return !!(window.BN_WATER && window.BN_WATER.open); }
  function bootId() {
    if (window.BN_WATER && window.BN_WATER.id) return window.BN_WATER.id;
    var m = location.pathname.match(/^\/grid\/water\/([A-Za-z][A-Za-z0-9._-]{3,40})\/?$/);
    return m ? m[1] : "";
  }
  function chip() { return document.querySelector('#nx_f [data-k="water"]'); }
  function num(n) { return Number(n || 0).toLocaleString("en-US"); }

  function mkDrop(fill) {
    var s = 64, c = document.createElement("canvas");
    c.width = s; c.height = s;
    var g = c.getContext("2d"), cx = 32, top = 4, r = 16, cy = 38;
    g.beginPath();
    g.moveTo(cx, top);
    g.bezierCurveTo(cx + 20, top + 20, cx + r + 6, cy - 10, cx + r, cy);
    g.arc(cx, cy, r, 0.08 * Math.PI, 0.92 * Math.PI, false);
    g.bezierCurveTo(cx - r - 6, cy - 10, cx - 20, top + 20, cx, top);
    g.closePath();
    g.fillStyle = fill;
    g.fill();
    g.lineWidth = 3.2;
    g.strokeStyle = "#05060A";
    g.stroke();
    g.beginPath();
    g.ellipse(cx - 4, cy - 4, 5, 3.5, -0.5, 0, Math.PI * 2);
    g.fillStyle = "rgba(255,255,255,.4)";
    g.fill();
    return g.getImageData(0, 0, s, s);
  }
  function ensureIcons() {
    if (!map || !map.addImage) return;
    try {
      if (!map.hasImage("wt-dw")) map.addImage("wt-dw", mkDrop(COL.dw), { pixelRatio: 2 });
      if (!map.hasImage("wt-ww")) map.addImage("wt-ww", mkDrop(COL.ww), { pixelRatio: 2 });
    } catch (e) {}
  }

  function panelPad() {
    var m = innerWidth < 768, onp = document.body.classList.contains("nx-water-on");
    if (m) {
      var bottom = onp ? Math.min(Math.round(innerHeight * 0.58) + 16, innerHeight - 150 - 200) : 120;
      return { top: 150, bottom: Math.max(80, bottom), left: 18, right: 18 };
    }
    var left = onp ? Math.min(520, innerWidth) + 24 : 60;
    left = Math.min(left, Math.max(60, innerWidth - 400));
    return { top: 160, bottom: 90, left: left, right: 80 };
  }
  function accountForPanel() {
    if (!map || bootId()) return;
    var z = 0;
    try { z = map.getZoom(); } catch (e) { return; }
    var pad = panelPad(), opts = { padding: pad, pitch: 0, bearing: 0, duration: fitted ? 400 : 0 };
    try {
      if (!fitted || z < 6) map.fitBounds(US, opts);
      else map.easeTo({ center: map.getCenter(), padding: pad, duration: 300 });
      fitted = true;
    } catch (e) {}
  }

  function setOn(v) {
    on = !!v;
    vis();
    if (on) { loadStatus(); fetchView(true); openPanel(true); accountForPanel(); openBoot(); } else openPanel(false);
    syncLeg();
  }

  function vis() {
    if (!map) return;
    ["wt-cl", "wt-cnt", "wt-pt-halo", "wt-pt", "wt-st"].forEach(function (id) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    });
    syncLeg();
  }

  function addLayers(n) {
    if (!map) return;
    n = n || 0;
    try {
      if (!map.getSource("wt")) map.addSource("wt", { type: "geojson", data: EMPTY });
      if (!map.getSource("wtst")) map.addSource("wtst", { type: "geojson", data: EMPTY });
      ensureIcons();
    } catch (e) {   /* style not parsed yet: try again shortly (never a page error) */
      if (n < 40) setTimeout(function () { addLayers(n + 1); }, 400);
      return;
    }
    if (map.getLayer("wt-st")) return;
    function L(o) { o.layout = o.layout || {}; o.layout.visibility = on ? "visible" : "none"; map.addLayer(o); }
    L({ id: "wt-cl", type: "circle", source: "wt", filter: ["==", ["get", "t"], "c"],
      paint: { "circle-color": "rgba(46,230,214,.16)", "circle-stroke-color": ["case", [">", ["get", "w"], ["*", ["get", "n"], 0.5]], COL.ww, COL.dw], "circle-stroke-width": 1.2, "circle-stroke-opacity": 0.9,
        "circle-radius": ["step", ["get", "n"], 9, 10, 12, 100, 16, 500, 20, 2000, 26, 10000, 32] } });
    L({ id: "wt-cnt", type: "symbol", source: "wt", filter: ["==", ["get", "t"], "c"],
      layout: { "text-field": ["get", "label"], "text-font": ["Noto Sans Regular"], "text-size": 10, "text-allow-overlap": true },
      paint: { "text-color": "rgba(240,240,250,.92)" } });
    L({ id: "wt-pt-halo", type: "circle", source: "wt", filter: ["==", ["get", "t"], "p"],
      paint: { "circle-color": "rgba(5,6,10,.55)", "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 6, 12, 9, 15, 12], "circle-opacity": 0.7 } });
    L({ id: "wt-pt", type: "symbol", source: "wt", filter: ["==", ["get", "t"], "p"],
      layout: { "icon-image": ["match", ["get", "k"], 1, "wt-ww", "wt-dw"], "icon-anchor": "bottom",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 9, 0.55, 11, 0.8, 13, 1.05],
        "icon-allow-overlap": true, "icon-ignore-placement": true } });
    L({ id: "wt-st", type: "circle", source: "wtst",
      paint: { "circle-color": ["match", ["get", "lv"], "dnd", COL.dnd, "boil", COL.boil, "serious", COL.dnd, "viol", COL.viol, "snc", COL.snc, COL.news],
        "circle-stroke-color": ["match", ["get", "lv"], "boil", "#8E97A6", "#05060a"], "circle-stroke-width": 1.2,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 4, 8, 7, 12, 9] } });
    if (!bound) bindMap();
    map.getSource("wt").setData({ type: "FeatureCollection", features: curFeats });
    map.getSource("wtst").setData({ type: "FeatureCollection", features: stFeats });
  }
  var bound = false;
  function bindMap() {
    bound = true;
    map.on("click", function (e) {
      if (!on) return;
      var layers = ["wt-st", "wt-pt", "wt-cl"].filter(function (id) { return map.getLayer(id); });
      var hits = map.queryRenderedFeatures(e.point, { layers: layers });
      if (!hits.length) return;
      var f = hits[0], p = f.properties || {};
      if (p.t === "c") { map.easeTo({ center: f.geometry.coordinates, zoom: Math.min(14, map.getZoom() + 2.2), duration: 500 }); return; }
      if (p.uid) select(p.uid, false);
      else if (p.id) select(p.id, false);
    });
    ["wt-st", "wt-pt", "wt-cl"].forEach(function (id) {
      map.on("mouseenter", id, function () { if (on) map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, function () { map.getCanvas().style.cursor = ""; });
    });
    map.on("moveend", function () { if (!on) return; clearTimeout(vt); vt = setTimeout(function () { fetchView(false); }, 220); });
  }

  function abbr(n) { return n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n); }

  function fetchView(force) {
    if (!map || !on) return;
    var b = map.getBounds(), z = map.getZoom();
    var w = b.getWest(), e = b.getEast(), s = Math.max(-90, b.getSouth()), n = Math.min(90, b.getNorth());
    if (e - w >= 360 || w < -180 || e > 180) { w = -180; e = 180; }
    var q = "w=" + w.toFixed(2) + "&s=" + s.toFixed(2) + "&e=" + e.toFixed(2) + "&n=" + n.toFixed(2) + "&z=" + (Math.floor(z * 2) / 2);
    if (!force && q === lastKey) return;
    lastKey = q;
    if (vctl) try { vctl.abort(); } catch (x) {}
    vctl = window.AbortController ? new AbortController() : null;
    getJSON("/api/netmap/water?" + q, vctl && vctl.signal).then(function (j) {
      if (j.total) { plantTotal = j.total[0]; plantCountries = j.total[1]; head(); }
      var feats;
      if (j.t === "c") {
        feats = j.r.map(function (r) {
          return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { t: "c", n: r[2], w: r[3], label: abbr(r[2]) } };
        });
      } else {
        feats = j.r.map(function (r) {
          return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { t: "p", k: r[2], uid: r[3], name: r[4] } };
        });
      }
      info = { t: j.t, n: feats.length, more: !!j.more };
      curFeats = feats;
      if (map.getSource("wt")) map.getSource("wt").setData({ type: "FeatureCollection", features: feats });
      head();
    }, function (err) { if (err && err.name === "AbortError") return; lastKey = ""; });
  }

  function loadStatus(fresh) {
    if (!statusRows || fresh) {
      getJSON("/api/water/map" + (fresh ? "?_=" + Date.now() : "")).then(function (j) {
        statusRows = j.r || [];
        var feats = stFeats = statusRows.map(function (r) {
          return { type: "Feature", geometry: { type: "Point", coordinates: [r[1], r[2]] }, properties: { id: r[0], lv: r[3], name: r[4] } };
        });
        if (map && map.getSource("wtst")) map.getSource("wtst").setData({ type: "FeatureCollection", features: feats });
      }, function () {});
    }
    if (!advPulled || fresh) pullAdv(0, fresh);
  }

  function pullAdv(off, fresh) {
    advPulled = true;
    getJSON("/api/water/data?limit=30&offset=" + off + (fresh ? "&fresh=1&_=" + Date.now() : "")).then(function (j) {
      var it = j.items || [];
      if (off === 0) adv = [];
      it.forEach(function (x) { adv.push(x); items[x.id] = x; });
      advTotal = j.total || adv.length;
      window._wtByState = j.by_state || null;
      renderList();
      openBoot();
    }, function () { renderList(); });
  }

  function itemOf(id) {
    if (items[id]) return Promise.resolve(items[id]);
    var b = window.BN_WATER && window.BN_WATER.item;
    if (b && typeof b === "object" && b.id === id) { items[id] = b; return Promise.resolve(b); }
    return getJSON("/api/water/item?id=" + encodeURIComponent(id)).then(function (j) { items[id] = j; return j; });
  }

  function shareRow(it) {
    var url = it.permalink || ("https://blackout.network/water/" + it.id);
    var text = it.name || "Water treatment status";
    var intent = it.xu || ("https://x.com/intent/post?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(url + "?s=x"));
    var src = it.url ? '<a class="bng-sb" href="' + href(it.url) + '" target="_blank" rel="noopener">Source</a>' : "";
    var perm = '<a class="bng-sb" href="' + esc(url) + '">Permalink</a>';
    var show = it.lat != null ? '<button type="button" class="bng-sb" data-show="' + esc(it.id) + '">Show on map</button>' : "";
    return '<div class="bng-share" data-url="' + esc(url) + '" data-text="' + esc(text) + '"><span class="bng-share-l">Share</span>' +
      '<a class="bng-sb" href="' + esc(intent) + '" target="_blank" rel="noopener">Post on X</a>' +
      '<button type="button" class="bng-sb bng-copy">Copy link</button>' +
      '<button type="button" class="bng-sb bng-native" hidden>Share…</button>' +
      src + perm + show + "</div>";
  }
  function revealShare() {
    document.querySelectorAll("#nx_water .bng-share .bng-native[hidden]").forEach(function (b) { if (navigator.share) b.hidden = false; });
  }

  function card(it) {
    var meta = [it.place, it.src || it.by].filter(Boolean).join(" · ");
    var note = it.note ? "<p>" + esc(it.note) + "</p>" : "";
    var prec = it.precision === "county" ? '<p class="k">Map dot is at the centre of the county served. The source does not publish this system's exact location.</p>' : "";
    var cls = it.level === "dnd" ? "dnd" : it.kind === "advisory" ? "boil" : (it.kind || "plant");
    var open = sel === it.id;
    return '<article class="wt-it' + (open ? " open sel" : "") + '" data-id="' + esc(it.id) + '"><button type="button" aria-expanded="' + open + '">' +
      '<i class="wt-dot wt-' + cls + '"></i><span class="t">' + esc(it.name) + '</span><span class="b">' + esc(it.label || LABEL[it.level] || "") + '</span>' +
      '<span class="m">' + esc(meta) + "</span></button><div class=\"x\">" + note + prec + shareRow(it) + "</div></article>";
  }

  function head() {
    var h = $("nx_water_sum"); if (!h) return;
    var bits = [];
    if (plantTotal) bits.push(num(plantTotal) + " treatment plants in " + num(plantCountries) + " countries");
    if (advTotal) bits.push(num(advTotal) + " current advisories and findings");
    var bs = window._wtByState, usN = 0, usS = 0;
    if (bs) { Object.keys(bs).forEach(function (k) { usN += bs[k]; usS += 1; }); }
    if (usN) bits.push(num(usN) + " U.S. boil or do-not-drink notices in " + usS + " state" + (usS === 1 ? "" : "s"));
    if (info && info.t === "c" && plantTotal) bits.push("zoom in to see individual plants");
    if (info && info.t === "p" && info.more) bits.push("showing the first " + num(info.n) + " here, zoom in for the rest");
    h.textContent = bits.join(" · ") || "Plant inventory is loading…";
  }

  function renderList() {
    var el = $("nx_water_list"); if (!el) return;
    var out = '<p class="nx-empty" id="nx_water_sum"></p>';
    var shown = {}, selIt = sel ? items[sel] : null;
    if (selIt) { out += card(selIt); shown[selIt.id] = 1; }
    var rest = adv.filter(function (x) { return !shown[x.id]; });
    if (rest.length) out += rest.map(card).join("");
    else if (advPulled && !selIt) out += '<p class="nx-empty">No current boil-water, do-not-drink or compliance items in the live feeds. Plants stay on the map, each with a cited source.</p>';
    if (adv.length < advTotal) out += '<button type="button" class="bng-sb wt-more" id="nx_water_more">Show more (' + num(advTotal - adv.length) + ')</button>';
    el.innerHTML = out;
    head();
    revealShare();
    el.querySelectorAll(".wt-it > button").forEach(function (b) {
      b.addEventListener("click", function () { select(b.parentNode.getAttribute("data-id"), true); });
    });
    el.querySelectorAll("[data-show]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); select(b.getAttribute("data-show"), true); });
    });
    var more = $("nx_water_more"); if (more) more.addEventListener("click", function () { more.disabled = true; pullAdv(adv.length, false); });
  }

  function select(id, fly) {
    itemOf(id).then(function (it) {
      sel = id;
      try { history.replaceState(null, "", "/grid/water/" + encodeURIComponent(id)); } catch (e) {}
      renderList();
      if (fly && map && it.lat != null && it.lon != null) {
        var wide = window.innerWidth >= 768;
        map.easeTo({ center: [it.lon, it.lat], zoom: Math.max(map.getZoom(), it.level === "dw" || it.level === "ww" ? 11 : 8), duration: 700,
          offset: wide ? [-Math.round(Math.min(520, window.innerWidth) / 2), 0] : [0, -Math.round(window.innerHeight * 0.58 / 2)] });
      }
      var el = document.querySelector('#nx_water_list .wt-it[data-id="' + id + '"]');
      if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
      openPanel(true);
    }, function () {});
  }

  function openBoot() {
    if (bootTried) return;
    var id = bootId(); if (!id) return;
    bootTried = true;
    select(id, true);
  }

  function openPanel(show) {
    var pan = $("nx_water"), btn = $("nx_water_btn");
    if (btn) { btn.hidden = !on; btn.setAttribute("aria-expanded", show && on ? "true" : "false"); }
    if (!pan) return;
    document.body.classList.toggle("nx-water-on", !!(show && on));
    pan.hidden = !(show && on);
    syncLeg();
  }

  function syncLeg() {
    var el = $("nx_water_leg");
    if (!el) {
      el = document.createElement("div");
      el.id = "nx_water_leg";
      el.className = "wt-mapleg";
      el.setAttribute("aria-label", "Water layer key");
      el.innerHTML = '<span><i class="wt-drop wt-dw"></i>Drinking-water plant</span><span><i class="wt-drop wt-ww"></i>Wastewater plant</span><span><i class="wt-dot wt-dnd"></i>Do not drink</span><span><i class="wt-dot wt-boil"></i>Boil water</span>';
      document.body.appendChild(el);
    }
    el.hidden = !on;
  }

  function hook() {
    var c = chip();
    if (c && !c.dataset.wtHook) {
      c.dataset.wtHook = "1";
      c.addEventListener("click", function () {
        if (fixing) return;
        setTimeout(function () { setOn(c.getAttribute("aria-pressed") === "true"); }, 0);
      });
    }
    var xb = $("nx_water_x"); if (xb && !xb.dataset.wtHook) { xb.dataset.wtHook = "1"; xb.addEventListener("click", function () { openPanel(false); }); }
    var wb = $("nx_water_btn"); if (wb && !wb.dataset.wtHook) { wb.dataset.wtHook = "1"; wb.addEventListener("click", function () { openPanel(!document.body.classList.contains("nx-water-on")); }); }
  }

  var fixing = false;
  function syncChip(n) {   /* make net.js's own chip state agree (it owns the aria + summary); retry until its handler is bound */
    var c = chip(); if (!c || c.getAttribute("aria-pressed") === "true" || n > 12) return;
    fixing = true; c.click(); fixing = false;
    setTimeout(function () { syncChip(n + 1); }, 600);
  }

  function ready(m) {
    map = m || window.__nxMap;
    if (!map) return;
    addLayers();
    hook();
    syncLeg();
    if (wantOpen() || bootId()) { setOn(true); syncChip(0); } else vis();
  }

  document.addEventListener("nx:map", function (e) { ready(e.detail); });
  document.addEventListener("nx:data", function () { if (on) { loadStatus(true); fetchView(true); } });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();
  if (window.__nxMap) ready(window.__nxMap);
  else setTimeout(function () { if (window.__nxMap) ready(window.__nxMap); }, 2000);
})();
