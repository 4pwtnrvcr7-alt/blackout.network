/* Water layer on /grid. Same pattern as Internet, Power grid and Hydro dams:
   a chip, circle markers, the shared Key, and the shared #nx_card popup. No side or bottom panel.
   Lazy: nothing is fetched until the Water chip is on (or /grid/water[/id] is opened). Not part of the loader weights.
   Plants: /api/netmap/water?w&s&e&n&z (viewport clusters below z 9, capped points at z 9+).
   Advisories: /api/water/map (slim status dots). One item: /api/water/item?id=.
   /grid/water (no item) recenters on the lower 48, same box as the rest of The Grid. */
(function () {
  var COL = { plant: "#4FC3F7", dnd: "#FF3B3B", boil: "#FFA040", viol: "#FFA040", serious: "#FF3B3B", snc: "#FFA040", news: "#7C8190" };
  var LABEL = { dnd: "Do not drink or use", boil: "Boil water", viol: "Drinking-water violation", serious: "Serious violation", snc: "Sewage plant noncompliance", news: "News report" };
  var EMPTY = { type: "FeatureCollection", features: [] };
  var US = [[-125.5, 23.5], [-66, 50]];
  var PAD = function () { return innerWidth < 768 ? { top: 150, bottom: 120, left: 18, right: 18 } : { top: 160, bottom: 90, left: 60, right: 80 }; };
  var map = null, on = false, bootTried = false, vt = 0, vctl = null, lastKey = "", fitted = false, bound = false, pinned = false;
  var curFeats = [], stFeats = [], items = {}, statusRows = null;

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function href(u) { try { var x = new URL(u, "https://blackout.network"); if (x.protocol === "http:" || x.protocol === "https:") return x.href; } catch (e) {} return ""; }
  function getJSON(url, sig) { return fetch(url, { credentials: "same-origin", signal: sig }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function wantOpen() { return !!(window.BN_WATER && window.BN_WATER.open); }
  function bootId() {
    if (window.BN_WATER && window.BN_WATER.id) return window.BN_WATER.id;
    var m = location.pathname.match(/^\/grid\/water\/([A-Za-z][A-Za-z0-9._-]{3,40})\/?$/);
    return m ? m[1] : "";
  }
  function chip() { return document.querySelector('#nx_f [data-k="water"]'); }
  function linkA(u, t) { var h = href(u); return h ? '<a href="' + esc(h) + '"' + (/^\//.test(u) ? "" : ' target="_blank" rel="noopener noreferrer"') + ">" + esc(t) + "</a>" : ""; }
  function colorOf(lv) { return COL[lv] || COL.plant; }
  function fmtSince(s) {
    if (!s) return "";
    var str = String(s);
    var m = str.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (m && (!m[4] || (m[4] === "00" && m[5] === "00" && (!m[6] || m[6] === "00")))) {
      var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      return months[parseInt(m[2], 10) - 1] + " " + parseInt(m[3], 10) + ", " + m[1];
    }
    var d = new Date(str);
    if (isNaN(d.getTime())) return str;
    try {
      var parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).formatToParts(d);
      function get(tp) { for (var i = 0; i < parts.length; i++) if (parts[i].type === tp) return parts[i].value; return ""; }
      return get("month") + " " + get("day") + ", " + get("year") + ", " + get("hour") + ":" + get("minute") + " " + get("dayPeriod") + " ET";
    } catch (e) { return str; }
  }

  function shareFor(it) {
    /* Prefer the server-built intent (facts, place tags, no #BlackoutNetwork). */
    if (it && it.xu) {
      return '<div class="nx-xs"><a class="bn-x" href="' + esc(it.xu) + '" target="_blank" rel="noopener">Post on X</a></div>';
    }
    var S = window.BNShare; if (!S || !it) return "";
    try {
      var n = it.name || "Water treatment", place = it.place || "", url = it.permalink || ("https://blackout.network/water/" + it.id);
      var t = it.note ? (n + (place ? ", " + place : "") + ". " + String(it.note)) : ((it.label || LABEL[it.level] || "Water treatment plant") + " at " + n + (place ? ", " + place : "") + ".");
      t = String(t).replace(/\s+/g, " ").trim();
      if (t.length > 280) t = t.slice(0, 279).replace(/\s+\S*$/, "").replace(/[,;:\-\u2013 ]+$/, "") + ".";
      return '<div class="nx-xs">' + S.html({ k: "water", i: it.id, n: n, t: t, d: String(it.note || t).slice(0, 200), l: place, p: url }) + "</div>";
    } catch (e) { return ""; }
  }

  function plantHtml(it) {
    var typ = it.level === "ww" || it.kind === "ww" ? "Wastewater plant" : "Drinking-water plant";
    var c = COL.plant;
    return '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Water treatment plant · Operating</span><h3>' + esc(it.name || typ) + "</h3><dl>" +
      "<dt>Type</dt><dd>" + typ + "</dd>" +
      (it.place ? "<dt>Location</dt><dd>" + esc(it.place) + "</dd>" : "") +
      (it.src || it.by ? "<dt>Source</dt><dd>" + esc(it.src || it.by) + "</dd>" : "") + "</dl>" +
      (it.url ? '<div class="acts">' + linkA(it.url, "Source record") + "</div>" : "") +
      '<p class="age">Operating plants are shown in blue, the same way other Grid layers colour a live, working site by its type.</p>' +
      shareFor(it);
  }

  function statusHtml(it) {
    var lv = it.level || (it.kind === "advisory" ? "boil" : it.kind) || "";
    var c = colorOf(lv === "advisory" ? "boil" : lv);
    var lab = it.label || LABEL[lv] || "Advisory";
    var prec = it.precision === "county" ? '<p class="age">Map dot is at the centre of the county served. The source does not publish an exact location.</p>' : "";
    return '<span class="st" style="color:' + c + '"><i style="background:' + c + '"></i>Water · ' + esc(lab) + "</span><h3>" + esc(it.name || lab) + "</h3>" +
      (it.note ? "<p>" + esc(it.note) + "</p>" : "") +
      "<dl>" + (it.place ? "<dt>Location</dt><dd>" + esc(it.place) + "</dd>" : "") +
      (it.since ? "<dt>Since</dt><dd>" + esc(fmtSince(it.since)) + "</dd>" : "") +
      (it.src || it.by ? "<dt>Source</dt><dd>" + esc(it.src || it.by) + "</dd>" : "") + "</dl>" +
      (it.url ? '<div class="acts">' + linkA(it.url, "Official notice") + "</div>" : "") +
      prec + shareFor(it);
  }

  function showCard(html, pt, pin) {
    var card = $("nx_card"); if (!card) return;
    card.innerHTML = html + '<button type="button" class="nx-cx" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
    card.hidden = false;
    requestAnimationFrame(function () { card.classList.add("in"); });
    pinned = !!pin;
    card.classList.toggle("pin", pinned);
    if (window.__bnPlace) window.__bnPlace(card, pt);
    var cx = card.querySelector(".nx-cx"); if (cx) cx.onclick = function () { hideCard(true); };
  }
  function hideCard(force) {
    if (pinned && !force) return;
    pinned = false;
    var card = $("nx_card"); if (!card) return;
    card.classList.remove("in", "pin");
    setTimeout(function () { if (card && !card.classList.contains("in")) card.hidden = true; }, 200);
  }

  function itemOf(id) {
    if (items[id]) return Promise.resolve(items[id]);
    var b = window.BN_WATER && window.BN_WATER.item;
    if (b && typeof b === "object" && b.id === id) { items[id] = b; return Promise.resolve(b); }
    return getJSON("/api/water/item?id=" + encodeURIComponent(id)).then(function (j) { items[id] = j; return j; });
  }

  function openItem(id, pt, pin) {
    itemOf(id).then(function (it) {
      if (!it) return;
      try { history.replaceState(null, "", "/grid/water/" + encodeURIComponent(id)); } catch (e) {}
      var html = (it.kind === "dw" || it.kind === "ww" || it.level === "dw" || it.level === "ww") ? plantHtml(it) : statusHtml(it);
      showCard(html, pt, pin);
    }, function () {});
  }

  function hitAt(pt) {
    if (!on || !map || !pt) return null;
    var layers = ["wt-st", "wt-pt", "wt-cl"].filter(function (id) { return map.getLayer(id); });
    if (!layers.length) return null;
    var hits = map.queryRenderedFeatures([[pt.x - 8, pt.y - 8], [pt.x + 8, pt.y + 8]], { layers: layers });
    return hits[0] || null;
  }

  window.__wtHit = function (e) {
    if (!on || !e || !e.point) return false;
    var f = hitAt(e.point); if (!f) return false;
    var p = f.properties || {};
    if (p.t === "c") { map.easeTo({ center: f.geometry.coordinates, zoom: Math.min(14, map.getZoom() + 2.2), duration: 500 }); hideCard(true); return true; }
    if (p.uid) openItem(p.uid, e.point, true);
    else if (p.id) openItem(p.id, e.point, true);
    return true;
  };

  function addLayers(n) {
    if (!map) return;
    n = n || 0;
    try {
      if (!map.getSource("wt")) map.addSource("wt", { type: "geojson", data: EMPTY });
      if (!map.getSource("wtst")) map.addSource("wtst", { type: "geojson", data: EMPTY });
    } catch (e) {
      if (n < 40) setTimeout(function () { addLayers(n + 1); }, 400);
      return;
    }
    function L(o) {
      if (map.getLayer(o.id)) return;
      o.layout = o.layout || {};
      if (o.layout.visibility == null) o.layout.visibility = on ? "visible" : "none";
      map.addLayer(o);
    }
    L({ id: "wt-cl", type: "circle", source: "wt", filter: ["==", ["get", "t"], "c"],
      paint: { "circle-color": "rgba(79,195,247,.18)", "circle-stroke-color": COL.plant, "circle-stroke-width": 1.2, "circle-stroke-opacity": 0.9,
        "circle-radius": ["step", ["get", "n"], 9, 10, 12, 100, 16, 500, 20, 2000, 26, 10000, 32] } });
    L({ id: "wt-cnt", type: "symbol", source: "wt", filter: ["==", ["get", "t"], "c"],
      layout: { "text-field": ["get", "label"], "text-font": ["Noto Sans Regular"], "text-size": 10, "text-allow-overlap": true },
      paint: { "text-color": "rgba(240,240,250,.92)" } });
    L({ id: "wt-pt", type: "circle", source: "wt", filter: ["==", ["get", "t"], "p"],
      paint: { "circle-color": COL.plant, "circle-stroke-color": "#05060a", "circle-stroke-width": 1,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 3.5, 12, 5.5, 15, 7] } });
    L({ id: "wt-st", type: "circle", source: "wtst",
      layout: { "circle-sort-key": ["match", ["get", "lv"], "dnd", 5, "serious", 4, "boil", 3, "viol", 2, "snc", 2, 1] },
      paint: { "circle-color": ["match", ["get", "lv"], "dnd", COL.dnd, "serious", COL.serious, "boil", COL.boil, "viol", COL.viol, "snc", COL.snc, COL.news],
        "circle-stroke-color": "#05060a", "circle-stroke-width": 1.2,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 4, 8, 6.5, 12, 8] } });
    if (!bound) bindMap();
    map.getSource("wt").setData({ type: "FeatureCollection", features: curFeats });
    map.getSource("wtst").setData({ type: "FeatureCollection", features: stFeats });
  }

  function bindMap() {
    bound = true;
    ["wt-st", "wt-pt", "wt-cl"].forEach(function (id) {
      map.on("mouseenter", id, function (e) {
        if (!on) return;
        map.getCanvas().style.cursor = "pointer";
        if (pinned) return;
        var f = e.features && e.features[0]; if (!f) return;
        var p = f.properties || {};
        if (p.uid) openItem(p.uid, e.point, false);
        else if (p.id) openItem(p.id, e.point, false);
      });
      map.on("mouseleave", id, function () { map.getCanvas().style.cursor = ""; if (!pinned) hideCard(); });
    });
    map.on("moveend", function () { if (!on) return; clearTimeout(vt); vt = setTimeout(function () { fetchView(false); }, 220); });
  }

  function abbr(n) { return n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n); }

  function fetchView(force) {
    if (!map || !on) return;
    var b = map.getBounds(), z = map.getZoom();
    var q = "w=" + b.getWest().toFixed(2) + "&s=" + b.getSouth().toFixed(2) + "&e=" + b.getEast().toFixed(2) + "&n=" + b.getNorth().toFixed(2) + "&z=" + z.toFixed(1);
    if (!force && q === lastKey) return;
    lastKey = q;
    if (vctl) try { vctl.abort(); } catch (e) {}
    vctl = window.AbortController ? new AbortController() : null;
    getJSON("/api/netmap/water?" + q, vctl && vctl.signal).then(function (j) {
      var feats;
      if (j.t === "c") {
        feats = (j.r || []).map(function (r) {
          return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { t: "c", n: r[2], w: r[3], label: abbr(r[2]) } };
        });
      } else {
        feats = (j.r || []).map(function (r) {
          return { type: "Feature", geometry: { type: "Point", coordinates: [r[0], r[1]] }, properties: { t: "p", k: r[2], uid: r[3], name: r[4] } };
        });
      }
      curFeats = feats;
      if (map.getSource("wt")) map.getSource("wt").setData({ type: "FeatureCollection", features: feats });
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
        if (j.loading) setTimeout(function () { if (on) loadStatus(true); }, 1200);
      }, function () { if (on) setTimeout(function () { loadStatus(true); }, 2000); });
    }
  }

  function goUS() {
    if (!map || fitted) return;
    fitted = true;
    map.fitBounds(US, { padding: PAD(), duration: 0, pitch: 0, bearing: 0 });
  }

  function openBoot() {
    if (bootTried) return;
    var id = bootId(); if (!id) return;
    bootTried = true;
    itemOf(id).then(function (it) {
      if (map && it && it.lat != null && it.lon != null) {
        map.easeTo({ center: [it.lon, it.lat], zoom: Math.max(map.getZoom(), (it.level === "dw" || it.level === "ww" || it.kind === "dw" || it.kind === "ww") ? 11 : 8), duration: 700 });
        setTimeout(function () {
          var pt = map.project([it.lon, it.lat]);
          openItem(id, pt, true);
        }, 750);
      } else openItem(id, { x: innerWidth / 2, y: innerHeight / 2 }, true);
    }, function () {});
  }

  function setOn(v) {
    on = !!v;
    vis();
    if (on) { loadStatus(); fetchView(true); if (wantOpen() && !bootId()) goUS(); openBoot(); }
  }

  function vis() {
    if (!map) return;
    ["wt-cl", "wt-cnt", "wt-pt", "wt-st"].forEach(function (id) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    });
  }

  var fixing = false;
  function hook() {
    var c = chip();
    if (c && !c.dataset.wtHook) {
      c.dataset.wtHook = "1";
      c.addEventListener("click", function () {
        if (fixing) return;
        setTimeout(function () { setOn(c.getAttribute("aria-pressed") === "true"); }, 0);
      });
    }
  }
  function syncChip(n) {
    var c = chip(); if (!c || c.getAttribute("aria-pressed") === "true" || n > 12) return;
    fixing = true; c.click(); fixing = false;
    setTimeout(function () { syncChip(n + 1); }, 600);
  }

  function ready(m) {
    map = m || window.__nxMap;
    if (!map) return;
    addLayers();
    hook();
    if (wantOpen() || bootId()) { setOn(true); syncChip(0); } else vis();
  }

  document.addEventListener("nx:map", function (e) { ready(e.detail); });
  document.addEventListener("nx:data", function () { if (on) { loadStatus(true); fetchView(true); } });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();
  if (window.__nxMap) ready(window.__nxMap);
  else setTimeout(function () { if (window.__nxMap) ready(window.__nxMap); }, 2000);
})();
