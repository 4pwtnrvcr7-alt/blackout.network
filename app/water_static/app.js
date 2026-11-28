/* /water: Water treatment status tracker (preview). Map via MapLibre + OpenFreeMap (no key). Data: /api/water/data. */
(function () {
  "use strict";
  var COLORS = { dnd: "#FF4D4F", boil: "#FFFFFF", serious: "#6EA8FE", viol: "#6EA8FE", snc: "#B79CFF" };
  var ORDER = { dnd: 0, boil: 1, serious: 2, viol: 3, snc: 4, news: 5 };
  var PAGE = 40;
  var D = null, ITEMS = [], KINDS = { advisory: true, violation: true, wastewater: true, news: true }, Q = "", SHOWN = PAGE, SEL = null, MAP = null, READY = false, POP = null;
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function href(u) { return /^https:\/\//i.test(u || "") ? esc(u) : "#"; }
  function fmtDate(iso) { if (!iso) return ""; var d = new Date(iso); if (isNaN(d)) return ""; return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
  function ago(iso) {
    var d = new Date(iso); if (isNaN(d)) return ""; var s = (Date.now() - d.getTime()) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + " min ago"; if (s < 86400) return Math.round(s / 3600) + " h ago"; return Math.round(s / 86400) + " d ago";
  }
  function pop(it) { if (it.pop) return it.pop.toLocaleString("en-US") + " people"; return it.pop_text || ""; }
  function when(it) {
    if (it.kind === "news") return it.since ? "Reported " + ago(it.since) : "";
    if (!it.since) return "";
    return (it.kind === "advisory" ? "In effect since " : "Status as of ") + fmtDate(it.since);
  }
  function vis(it) {
    if (!KINDS[it.kind]) return false;
    if (!Q) return true;
    return (it.name + " " + it.place + " " + (it.label || "")).toLowerCase().indexOf(Q) >= 0;
  }
  function sorted(list) {
    return list.slice().sort(function (a, b) {
      var d = ORDER[a.level] - ORDER[b.level]; if (d) return d;
      if (a.kind === "violation" || a.kind === "advisory") { var p = (b.pop || 0) - (a.pop || 0); if (p && a.kind === "violation") return p; }
      return (b.since || "").localeCompare(a.since || "");
    });
  }
  /* ---------- list ---------- */
  function render() {
    var list = sorted(ITEMS.filter(vis)), box = $("wt_list");
    if (!list.length) { box.innerHTML = '<p class="wt-empty">' + (D ? "Nothing matches. Try another filter or search." : "Loading") + "</p>"; $("wt_more").hidden = true; return; }
    var out = [];
    list.slice(0, SHOWN).forEach(function (it) { out.push(card(it)); });
    box.innerHTML = out.join("");
    revealShare();
    var more = $("wt_more"); more.hidden = list.length <= SHOWN; more.textContent = "Show more (" + (list.length - SHOWN) + " left)";
  }
  function shareRow(it) {
    var url = it.permalink || ("https://blackout.network/water/" + it.id);
    var text = it.name || "Water treatment status";
    var intent = it.xu || ("https://x.com/intent/post?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(url + "?s=x"));
    var src = '<a class="bng-sb" href="' + href(it.url) + '" target="_blank" rel="noopener">Source: ' + esc(it.src) + "</a>";
    var perm = '<a class="bng-sb" href="' + esc(url) + '">Permalink</a>';
    var map = it.lat != null ? '<button type="button" class="bng-sb" data-show="' + esc(it.id) + '">Show on map</button>' : "";
    return '<div class="bng-share" data-url="' + esc(url) + '" data-text="' + esc(text) + '"><span class="bng-share-l">Share</span>' +
      '<a class="bng-sb" href="' + esc(intent) + '" target="_blank" rel="noopener">Post on X</a>' +
      '<button type="button" class="bng-sb bng-copy">Copy link</button>' +
      '<button type="button" class="bng-sb bng-native" hidden>Share…</button>' +
      src + perm + map + "</div>";
  }
  function revealShare() {
    document.querySelectorAll(".bng-share .bng-native[hidden]").forEach(function (b) { if (navigator.share) b.hidden = false; });
  }
  function bootId() {
    if (window.WT_OPEN) return window.WT_OPEN;
    var m = location.pathname.match(/^\/water\/([A-Za-z][A-Za-z0-9._-]{3,40})\/?$/);
    if (m) return m[1];
    try { var q = new URLSearchParams(location.search).get("id"); if (q) return q; } catch (e) {}
    var h = (location.hash || "").replace(/^#/, "");
    return h || "";
  }
  function openBoot() {
    var id = bootId(); if (!id) return;
    var it = byId(id); if (!it) return;
    if (!KINDS[it.kind]) { KINDS[it.kind] = true; var c = document.querySelector('.wt-chip[data-k="' + it.kind + '"]'); if (c) c.setAttribute("aria-pressed", "true"); }
    select(id, true);
  }
  function card(it) {
    var meta = [it.place, pop(it), when(it)].filter(Boolean).join(" · ");
    var note = it.note ? "<p>" + esc(it.note) + "</p>" : "";
    var prec = it.precision === "county" ? '<p class="k">Map dot is at the centre of the county served. EPA does not publish this system\'s exact location.</p>' : "";
    var acts = shareRow(it);
    var pb = D && D.pubs && D.pubs[it.src];
    var by = it.kind === "news" || !pb ? "" : '<p class="k">Published by ' + esc(pb) + "</p>";
    var why = it.kind === "violation" ? '<p class="k">EPA lists a current health-based violation for this system. This is a compliance finding, not a boil-water notice.</p>' :
      it.kind === "wastewater" ? '<p class="k">A compliance finding about discharge permits, not a drinking-water notice.</p>' : "";
    return '<article class="wt-it' + (SEL === it.id ? " open sel" : "") + '" data-id="' + esc(it.id) + '"><button type="button" aria-expanded="' + (SEL === it.id) + '">' +
      '<i class="wt-dot wt-' + (it.level === "dnd" ? "dnd" : it.kind === "advisory" ? "boil" : it.kind) + '"></i><span class="t">' + esc(it.name) + '</span><span class="b ' + esc(it.level) + '">' + esc(it.label) + '</span>' +
      '<span class="m">' + esc(meta) + '</span></button><div class="x">' + why + note + prec + by + acts + "</div></article>";
  }
  function counts() {
    var c = { advisory: 0, violation: 0, wastewater: 0, news: 0 };
    ITEMS.forEach(function (i) { c[i.kind]++; });
    Object.keys(c).forEach(function (k) { var n = document.querySelector('[data-n="' + k + '"]'); if (n) n.textContent = c[k].toLocaleString("en-US"); });
  }
  function sub() {
    if (!D) return;
    var ok = D.sources.filter(function (s) { return s.ok; }), bad = D.sources.filter(function (s) { return !s.ok && !s.loading; }), t = null;
    ok.forEach(function (s) { if (s.updated && (!t || s.updated < t)) t = s.updated; });
    var a = D.counts.advisory || 0;
    $("wt_sub").textContent = a.toLocaleString("en-US") + " active boil or do-not-drink notices from state and provincial agencies. " + (t ? "Oldest source pull " + ago(t) + "." : "") + (bad.length ? " " + bad.length + " source" + (bad.length > 1 ? "s" : "") + " unavailable." : "");
    var li = D.sources.map(function (s) {
      return '<li class="' + (s.ok ? "" : "bad") + '"><a href="' + href(s.url) + '" target="_blank" rel="noopener">' + esc(s.label) + "</a><span>" + (s.ok ? s.count.toLocaleString("en-US") + " · " + ago(s.updated) : s.loading ? "loading" : "unavailable" + (s.updated ? ", last good " + ago(s.updated) : "")) + "</span></li>";
    }).join("");
    $("wt_src").innerHTML = "<h2>Data sources</h2><ul>" + li + "</ul>";
  }
  /* ---------- map ---------- */
  function fc() {
    return { type: "FeatureCollection", features: ITEMS.filter(function (i) { return i.lat != null && vis(i); }).map(function (i) {
      return { type: "Feature", id: undefined, properties: { id: i.id, lv: i.level, k: i.kind, big: i.level === "serious" ? 1 : 0 }, geometry: { type: "Point", coordinates: [i.lon, i.lat] } };
    }) };
  }
  function mapData() { if (MAP && READY) MAP.getSource("wt").setData(fc()); }
  function initMap() {
    if (!window.maplibregl) { setTimeout(initMap, 80); return; }
    var narrow = window.innerWidth < 700;
    MAP = new maplibregl.Map({ container: "wt_map", style: "https://tiles.openfreemap.org/styles/dark", center: [-96.5, 39.2], zoom: narrow ? 2.3 : 3.15, minZoom: 1.6, maxZoom: 12, attributionControl: false, dragRotate: false, pitchWithRotate: false, touchPitch: false });
    MAP.touchZoomRotate.disableRotation();
    MAP.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    MAP.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap contributors</a> · EPA ECHO · U.S. Census Bureau' }), "bottom-right");
    MAP.on("load", function () {
      MAP.addSource("wt", { type: "geojson", data: fc() });
      var col = ["match", ["get", "lv"], "dnd", COLORS.dnd, "boil", COLORS.boil, "serious", COLORS.serious, "viol", COLORS.viol, "snc", COLORS.snc, "#8E97A6"];
      var z = function (a, b) { return ["interpolate", ["linear"], ["zoom"], 2, a, 8, b]; };
      MAP.addLayer({ id: "wt-viol", type: "circle", source: "wt", filter: ["==", ["get", "k"], "violation"], paint: { "circle-radius": z(3.4, 9), "circle-color": col, "circle-opacity": 0.5, "circle-stroke-color": col, "circle-stroke-width": 1 } });
      MAP.addLayer({ id: "wt-snc", type: "circle", source: "wt", filter: ["==", ["get", "k"], "wastewater"], paint: { "circle-radius": z(3.6, 9), "circle-color": col, "circle-opacity": 0.75, "circle-stroke-color": "#05060a", "circle-stroke-width": 1 } });
      MAP.addLayer({ id: "wt-adv", type: "circle", source: "wt", filter: ["==", ["get", "k"], "advisory"], paint: { "circle-radius": z(4.2, 10), "circle-color": col, "circle-opacity": 0.95, "circle-stroke-color": "#05060a", "circle-stroke-width": 1.2 } });
      MAP.addLayer({ id: "wt-sel", type: "circle", source: "wt", filter: ["==", ["get", "id"], ""], paint: { "circle-radius": 13, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#FFFFFF", "circle-stroke-width": 2 } });
      READY = true; MAP.resize();
      var at = document.querySelector(".wt-map .maplibregl-ctrl-attrib"); if (at) { at.classList.remove("maplibregl-compact-show"); var dt = at.querySelector("details"); if (dt) dt.removeAttribute("open"); }
      ["wt-adv", "wt-snc", "wt-viol"].forEach(function (l) {
        MAP.on("click", l, function (e) { var f = e.features && e.features[0]; if (f) { e.originalEvent._wt = 1; select(f.properties.id, false); } });
        MAP.on("mouseenter", l, function () { MAP.getCanvas().style.cursor = "pointer"; });
        MAP.on("mouseleave", l, function () { MAP.getCanvas().style.cursor = ""; });
      });
      MAP.on("click", function (e) { if (!e.originalEvent._wt) { closePop(); } });
      document.body.setAttribute("data-wt-map", "ready");
    });
  }
  function closePop() { if (POP) { POP.remove(); POP = null; } }
  function byId(id) { for (var i = 0; i < ITEMS.length; i++) if (ITEMS[i].id === id) return ITEMS[i]; return null; }
  function select(id, fly) {
    var it = byId(id); if (!it) return;
    SEL = id;
    try { history.replaceState(null, "", "/water/" + encodeURIComponent(id)); } catch (e) {}
    var idx = sorted(ITEMS.filter(vis)).findIndex(function (x) { return x.id === id; });
    if (idx >= SHOWN) SHOWN = idx + 1;
    render();
    var el = document.querySelector('.wt-it[data-id="' + id + '"]');
    if (el && !fly) { var wide = window.innerWidth >= 900; if (wide) el.scrollIntoView({ block: "center", behavior: "smooth" }); }
    if (MAP && READY && it.lat != null) {
      MAP.setFilter("wt-sel", ["==", ["get", "id"], id]);
      if (fly) MAP.flyTo({ center: [it.lon, it.lat], zoom: Math.max(MAP.getZoom(), it.precision === "county" ? 6.2 : 7.5), speed: 1.4, essential: false });
      closePop();
      POP = new maplibregl.Popup({ className: "wt-pop", offset: 14, closeButton: true, closeOnClick: false, maxWidth: "260px" }).setLngLat([it.lon, it.lat])
        .setHTML("<b>" + esc(it.name) + '</b><span class="k">' + esc(it.label) + " · " + esc(it.place) + "</span>" + (when(it) ? '<span class="k">' + esc(when(it)) + "</span>" : "") + '<a href="' + href(it.url) + '" target="_blank" rel="noopener">Source: ' + esc(it.src) + "</a>").addTo(MAP);
    }
  }
  /* ---------- data ---------- */
  function load(fresh, btn) {
    var R = window.BNRefresh;
    if (btn && R) { R.busy(btn, true); R.stage(btn, 10); }
    return fetch("/api/water/data" + (fresh ? "?fresh=1&_=" + Date.now() : ""), { credentials: "same-origin" }).then(function (r) {
      if (btn && R) R.stage(btn, 60);
      if (!r.ok) throw new Error("http " + r.status); return r.json();
    }).then(function (j) {
      D = j; ITEMS = j.items || [];
      if (btn && R) R.stage(btn, 85);
      counts(); sub(); render(); mapData(); openBoot();
      if (btn && R) { R.stage(btn, 100); setTimeout(function () { R.busy(btn, false); R.done(btn, (fresh && j.pulled && !j.pulled.length) ? "Already current" : "Updated"); }, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 220); }
      return (fresh && j.pulled && !j.pulled.length) ? "Already current" : "Updated";
    }).catch(function () {
      if (btn && R) { R.stage(btn, 100); R.busy(btn, false); R.done(btn, "Couldn't refresh"); }
      if (!D) $("wt_list").innerHTML = '<p class="wt-empty">Live data is unavailable right now. Try Refresh in a moment.</p>';
    });
  }
  function fitTop() {
    var t = document.querySelector(".bn-tbar"), h = document.querySelector("header.bn-top"), m = $("wt_main");
    if (!t || !m) return;
    var tb = t.offsetHeight, hh = h ? h.offsetHeight : 0;
    m.style.marginTop = Math.max(0, tb - hh) + "px"; m.style.setProperty("--wt-hd", Math.max(tb, hh) + "px");
  }
  function boot() {
    fitTop(); window.addEventListener("resize", fitTop); setTimeout(fitTop, 600);
    var m = document.getElementById("bn-menu"); if (m && m.parentNode !== document.body) document.body.appendChild(m);
    $("wt_chips").addEventListener("click", function (e) {
      var b = e.target.closest(".wt-chip"); if (!b) return; var k = b.getAttribute("data-k");
      KINDS[k] = !KINDS[k]; b.setAttribute("aria-pressed", String(KINDS[k])); SHOWN = PAGE; render(); mapData();
    });
    var qi = $("wt_q"), qt = 0;
    qi.addEventListener("input", function () { clearTimeout(qt); qt = setTimeout(function () { Q = qi.value.trim().toLowerCase(); SHOWN = PAGE; render(); mapData(); }, 120); });
    $("wt_more").addEventListener("click", function () { SHOWN += PAGE; render(); });
    $("wt_list").addEventListener("click", function (e) {
      var s = e.target.closest("[data-show]"); if (s) { select(s.getAttribute("data-show"), true); if (window.innerWidth < 900) { var mp = $("wt_map"); if (mp) window.scrollTo({ top: 0, behavior: "smooth" }); } return; }
      var b = e.target.closest(".wt-it > button"); if (!b || e.target.closest("a")) return;
      var id = b.parentNode.getAttribute("data-id");
      if (SEL === id) { SEL = null; closePop(); if (MAP && READY) MAP.setFilter("wt-sel", ["==", ["get", "id"], ""]); try { history.replaceState(null, "", "/water"); } catch (x) {} render(); }
      else { var it = byId(id); if (it && it.lat != null) select(id, window.innerWidth >= 900); else { SEL = id; render(); } }
    });
    var rb = $("wt_ref");
    if (rb && window.BNRefresh) BNRefresh.bind(rb, function () { return load(true, rb); });
    window.bnRefreshPage = function () { return load(true, rb); };
    initMap(); load(false);
    setInterval(function () { if (!document.hidden) load(false); }, 300000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
