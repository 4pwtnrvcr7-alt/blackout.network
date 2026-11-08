/* Global signal map. Leaflet + Natural Earth. No tile servers.
   Dots are colored by a fixed category palette (not by rank). Rank stays in the popup.
   Approximate places stay solid at 72% opacity. First paint fades each dot in over 0–15s. */
(function (global) {
  "use strict";
  var GEO = "/api/signal/world.geojson";
  var LOW = "#55b7ff", MID = "#F5A524", HIGH = "#FF4D4F";
  var SEARCH_MS = 200, CAT_KEY = "bn-sig-cats", NEUTRAL = "#8B95A3", NEUTRAL_LIGHT = "#5C6673";
  /* One palette for dark land and light land. Chips use the same hexes. */
  var CATS = {
    health:   {id: "health",   label: "Health",   color: "#FF8C42", light: "#C65A00"},
    weather:  {id: "weather",  label: "Weather",  color: "#3BA3F5", light: "#0B6EBF"},
    conflict: {id: "conflict", label: "Conflict", color: "#F2554A", light: "#C23128"},
    quake:    {id: "quake",    label: "Quake",    color: "#F0A05A", light: "#9A3412"},
    solar:    {id: "solar",    label: "Solar",    color: "#FFE34D", light: "#8A6A00"},
    grid:     {id: "grid",     label: "Grid",     color: "#2BBBAD", light: "#0C756C"},
    cyber:    {id: "cyber",    label: "Cyber",    color: "#7C8CFF", light: "#3A46C9"},
    nuclear:  {id: "nuclear",  label: "Nuclear",  color: "#F472B6", light: "#BE185D"},
    politics: {id: "politics", label: "Politics", color: "#C084FC", light: "#7A3DBF"},
    other:    {id: "other",    label: "Other",    color: "#94A3B8", light: "#475569"}
  };
  var CAT_IDS = ["health", "weather", "conflict", "quake", "solar", "grid", "cyber", "nuclear", "politics", "other"];
  var RX = {
    solar: /\b(geomagnetic|solar flare|solar storm|space weather|coronal mass|kp[- ]?index|radiation storm)\b/i,
    nuclear: /\b(nuclear|radioactive|meltdown|chernobyl|fukushima|iaea|warhead|non-proliferation|nonproliferation)\b/i,
    health: /\b(outbreak|virus|ebola|marburg|cholera|measles|influenza|h5n1|avian flu|bird flu|mpox|dengue|plague|pathogen|epidemic|pandemic|polio|covid|disease)\b/i,
    healthFalse: /\b(war|weather|storm|tornado) outbreaks?\b/i,
    quake: /\b(earthquakes?|seismic|aftershocks?|foreshocks?|tremors?|tsunami|usgs)\b/i,
    weather: /\b(hurricanes?|typhoons?|cyclones?|tornado(?:es)?|flood(?:ing)?|wildfires?|blizzards?|droughts?|landslides?|storms?|severe weather|mudslides?|volcan\w*|eruptions?)\b/i,
    grid: /\b(power outages?|blackouts?|power grid|electrical grid|grid (?:failure|outage|collapse)|substations?|rolling blackouts?|electricity (?:outage|failure)|pipeline (?:leak|rupture|explosion)|internet outages?|network outages?)\b/i,
    cyber: /\b(ransomware|malware|cyber|hack(?:ed|ers|ing)?|data breach|ddos|cve-|phishing)\b/i,
    conflict: /\b(airstrikes?|missiles?|shelling|troops|invasions?|artillery|ceasefires?|military|drone strikes?|war)\b/i
  };

  function band(rank) {
    var r = Math.max(0, Math.min(10, Math.round(+rank || 0)));
    if (r >= 7) return { r: r, name: "High", color: HIGH };
    if (r >= 4) return { r: r, name: "Elevated", color: MID };
    return { r: r, name: "Low", color: LOW };
  }
  function themeLight() {
    try { return document.documentElement.getAttribute("data-theme") === "light"; }
    catch (e) { return false; }
  }
  function colorFor(id, light) {
    var meta = CATS[id] || CATS.other;
    var useLight = light == null ? themeLight() : !!light;
    return useLight ? meta.light : meta.color;
  }
  function neutralColor(light) {
    var useLight = light == null ? themeLight() : !!light;
    return useLight ? NEUTRAL_LIGHT : NEUTRAL;
  }
  function inkOn(hex) {
    var h = String(hex || "").replace("#", "");
    if (h.length !== 6) return "#1d1d1f";
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 160 ? "#1d1d1f" : "#ffffff";
  }
  function catOf(c) {
    var raw = String((c && c.category) || "").toLowerCase().trim();
    var blob = String((c && c.title) || "") + "\n" + String((c && (c.place || c.location)) || "");
    if (raw === "space weather" || (RX.solar.test(blob) && raw !== "war/conflict" && raw !== "cyber" && raw !== "disease")) return CATS.solar;
    if (RX.nuclear.test(blob)) return CATS.nuclear;
    if (raw === "cyber" || (RX.cyber.test(blob) && raw !== "war/conflict" && raw !== "natural disaster" && raw !== "disease")) {
      if (RX.grid.test(blob) && !RX.cyber.test(blob)) return CATS.grid;
      return CATS.cyber;
    }
    if (raw === "disease" || (RX.health.test(blob) && !RX.healthFalse.test(blob))) return CATS.health;
    if (RX.quake.test(blob) && raw !== "war/conflict" && raw !== "political" && raw !== "financial") return CATS.quake;
    if (RX.grid.test(blob) && raw !== "war/conflict") return CATS.grid;
    if (raw === "war/conflict") return CATS.conflict;
    if (raw === "political" || raw === "financial") return CATS.politics;
    if (raw === "natural disaster" || (RX.weather.test(blob) && raw !== "ufo/uap")) return CATS.weather;
    if (RX.conflict.test(blob)) return CATS.conflict;
    return CATS.other;
  }
  function readDisabled(raw) {
    if (raw == null || raw === "") return null;
    try {
      var v = JSON.parse(raw), out = [], i;
      if (!Array.isArray(v)) return null;
      for (i = 0; i < v.length; i++) if (CATS[v[i]] && out.indexOf(v[i]) < 0) out.push(v[i]);
      return out;
    } catch (e) { return null; }
  }
  function enabledFrom(raw) {
    var off = readDisabled(raw), i, deny = {};
    if (!off) return CAT_IDS.slice();
    for (i = 0; i < off.length; i++) deny[off[i]] = 1;
    return CAT_IDS.filter(function (id) { return !deny[id]; });
  }
  function disabledFrom(enabled) {
    var on = {};
    (enabled || []).forEach(function (id) { on[id] = 1; });
    return CAT_IDS.filter(function (id) { return !on[id]; });
  }
  function real(c) {
    if (!c) return false;
    if (c.watchlist != null && +c.watchlist !== 0 && +c.watchlist !== 1) return false;
    if (c.lat == null || c.lon == null || c.lat === "" || c.lon === "") return false;
    var lat = +c.lat, lon = +c.lon;
    if (!isFinite(lat) || !isFinite(lon)) return false;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return false;
    if (lat === 0 && lon === 0) return false;
    return true;
  }
  function blob(c) {
    var links = (c && c.links) || [], i, parts = [c && c.category, c && c.title];
    for (i = 0; i < links.length; i++) parts.push(links[i] && links[i].source);
    return text(parts.join(" "));
  }
  function sourceName(link) {
    var s = text(link && link.source).replace(/\s*\([^)]*\)\s*/g, " ").trim();
    if (!s && link && link.url) {
      s = String(link.url).replace(/^https?:\/\//i, "").replace(/^www\./i, "").split("/")[0];
    }
    s = text(s) || "source";
    return s.length > 48 ? s.slice(0, 48).trim() : s;
  }
  function httpLink(c) {
    var links = (c && c.links) || [], i, u, l;
    for (i = 0; i < links.length; i++) {
      l = links[i] || {};
      u = l.url || l.u;
      if (typeof u === "string" && /^https?:\/\//i.test(u)) return { url: u, name: sourceName(l) };
    }
    return null;
  }
  function tracker(c) {
    var b = blob(c);
    if (/\b(usgs|emsc|geofon|geonet|ingv|csn)\b/i.test(b) || /\b(earthquake|quake|seismic)\b/i.test(b))
      return { href: "/#solar", ext: false, kind: "tracker", label: "Quakes on BLACKOUT.NETWORK ›" };
    if (/\b(nws|noaa|meteoalarm)\b/i.test(b) || /weather\.gov/i.test(b))
      return { href: "/#weather", ext: false, kind: "tracker", label: "Weather on BLACKOUT.NETWORK ›" };
    if (/\bioda\b|internet outage/i.test(b))
      return { href: "/network", ext: false, kind: "tracker", label: "Network status on BLACKOUT.NETWORK ›" };
    if (/\b(swpc|space weather|solar flare|geomagnetic)\b/i.test(b))
      return { href: "/#solar", ext: false, kind: "tracker", label: "Solar & Seismic on BLACKOUT.NETWORK ›" };
    if (/\b(power grid|grid status)\b/i.test(b))
      return { href: "/#grid", ext: false, kind: "tracker", label: "Energy grid on BLACKOUT.NETWORK ›" };
    return null;
  }
  function fallback(c) {
    var cat = String(c && c.category || ""), href = "/#wire";
    if (cat === "natural disaster") href = "/#weather";
    else if (cat === "space weather") href = "/#solar";
    else if (cat === "political") href = "/#politics";
    else if (cat === "financial") href = "/#finance";
    return { href: href, ext: false, kind: "fallback", label: "Read on BLACKOUT.NETWORK ›" };
  }
  function dest(c) {
    var id = String(c && (c.cluster_id || c.id) || "");
    var page, ext;
    if (/^[0-9a-f]{16}$/.test(id)) return { href: "/wire/" + id, ext: false, kind: "wire", label: "Read on BLACKOUT.NETWORK ›" };
    page = tracker(c);
    if (page) return page;
    ext = httpLink(c);
    if (ext) return { href: ext.url, ext: true, kind: "source", label: "Source: " + ext.name + " ›" };
    return fallback(c);
  }
  function when(c) { return c.event_time || c.first_seen || c.updated || ""; }
  function conflict(c) {
    return String(c && c.category || "").toLowerCase() === "war/conflict";
  }
  function inUS(c) {
    var cc = String(c && (c.cc || c.country) || "").toUpperCase();
    if (cc === "US") return true;
    var lat = +c.lat, lon = +c.lon;
    if (lat >= 24.5 && lat <= 49.5 && lon >= -125 && lon <= -66.5) return true;
    if (lat >= 51 && lat <= 72 && lon >= -170 && lon <= -129) return true;
    if (lat >= 18.5 && lat <= 22.5 && lon >= -161 && lon <= -154) return true;
    if (lat >= 17.5 && lat <= 18.6 && lon >= -67.5 && lon <= -65) return true;
    return false;
  }
  var FAN_MAX = 8, SPIDER_PX = 28, CELL = 48, MAX_Z = 8;
  function project(lat, lon, zoom) {
    var s = 256 * Math.pow(2, zoom);
    var x = ((+lon) + 180) / 360 * s;
    var sl = Math.sin(Math.max(-89.9, Math.min(89.9, +lat)) * Math.PI / 180);
    var y = (0.5 - Math.log((1 + sl) / (1 - sl)) / (4 * Math.PI)) * s;
    return { x: x, y: y };
  }
  /* Screen grid, not a geographic radius. Country piles stay one count dot.
     A ring is only for 8 or fewer non-country dots, and only 20–40 px across. */
  function clusterPlan(items, zoom) {
    var pts = [], i, p, k, buckets = {}, groups = [];
    for (i = 0; i < items.length; i++) {
      p = project(+items[i].lat, +items[i].lon, zoom);
      pts.push({ i: i, c: items[i], x: p.x, y: p.y });
    }
    for (i = 0; i < pts.length; i++) {
      k = Math.floor(pts[i].x / CELL) + ":" + Math.floor(pts[i].y / CELL);
      if (!buckets[k]) buckets[k] = [];
      buckets[k].push(pts[i]);
    }
    Object.keys(buckets).forEach(function (key) {
      var g = buckets[key], n = g.length, country = true, j, spider = false, rad = 0, offsets = [];
      for (j = 0; j < n; j++) {
        if (!(g[j].c.precision === "country" || g[j].c.approximate)) country = false;
      }
      if (n > 1 && country) spider = false;
      else if (n > 1 && n <= FAN_MAX) {
        spider = true;
        rad = Math.min(36, Math.max(20, 14 + n));
        for (j = 0; j < n; j++) {
          var ang = -Math.PI / 2 + (2 * Math.PI * j) / n;
          offsets.push({ dx: Math.cos(ang) * rad, dy: Math.sin(ang) * rad });
        }
      }
      groups.push({
        n: n, spider: spider, country: n > 1 && country, radius: spider ? rad : 0,
        idx: g.map(function (pt) { return pt.i; }), offsets: offsets
      });
    });
    return groups;
  }
  function dominantColor(members, light) {
    var counts = {}, i, id, top = 0, winners = [], k;
    members = members || [];
    for (i = 0; i < members.length; i++) {
      id = catOf(members[i]).id;
      counts[id] = (counts[id] || 0) + 1;
      if (counts[id] > top) top = counts[id];
    }
    for (k in counts) if (Object.prototype.hasOwnProperty.call(counts, k) && counts[k] === top) winners.push(k);
    if (winners.length !== 1) return neutralColor(light);
    return colorFor(winners[0], light);
  }
  function haystack(c) {
    var links = (c && c.links) || [], meta = catOf(c), parts = [c && c.title, c && c.place, c && c.location, c && c.category, meta.label, meta.id], i;
    for (i = 0; i < links.length; i++) parts.push(links[i] && links[i].source, links[i] && links[i].url);
    return text(parts.join(" ")).toLowerCase();
  }
  function matches(c, q) {
    q = text(q).toLowerCase();
    if (!q) return true;
    var h = haystack(c), parts = q.split(/\s+/), i;
    for (i = 0; i < parts.length; i++) if (parts[i] && h.indexOf(parts[i]) < 0) return false;
    return true;
  }
  function topMatches(list, q, n) {
    q = text(q).toLowerCase();
    if (!q) return [];
    var out = [], i;
    for (i = 0; i < (list || []).length; i++) if (matches(list[i], q)) out.push(list[i]);
    out.sort(function (a, b) {
      var as = text(a.title).toLowerCase().indexOf(q), bs = text(b.title).toLowerCase().indexOf(q);
      var ap = as === 0 ? 0 : 1, bp = bs === 0 ? 0 : 1;
      if (ap !== bp) return ap - bp;
      var ar = +a.rank || 0, br = +b.rank || 0;
      if (ar !== br) return br - ar;
      return text(a.title).localeCompare(text(b.title));
    });
    return out.slice(0, n || 8);
  }
  function pass(c, f, now) {
    if (!real(c)) return false;
    var r = band(c.rank).r;
    if (f.rank === "7" && r < 7) return false;
    if (f.rank === "4" && (r < 4 || r > 6)) return false;
    if (f.rank === "0" && r > 3) return false;
    if (f.topic && c.category !== f.topic) return false;
    if (f.cats && f.cats.indexOf(catOf(c).id) < 0) return false;
    if (f.conflict && !conflict(c)) return false;
    if (f.hours) {
      var t = Date.parse(when(c));
      if (!isFinite(t) || now - t > f.hours * 3600000) return false;
    }
    return true;
  }
  function viewCounts(list, f, now) {
    var base = { rank: f.rank || "", topic: f.topic || "", hours: f.hours, conflict: false, cats: f.cats };
    var all = [], us = 0, war = 0, i, row;
    for (i = 0; i < list.length; i++) if (pass(list[i], base, now)) all.push(list[i]);
    for (i = 0; i < all.length; i++) {
      row = all[i];
      if (inUS(row)) us++;
      if (conflict(row)) war++;
    }
    return { us: us, world: all.length, conflicts: war };
  }
  function et(iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    try {
      return new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(d) + " ET";
    } catch (e) { return ""; }
  }
  function text(s) { return String(s == null ? "" : s).replace(/\s+/g, " ").trim(); }
  function qs() {
    var q = {};
    (location.search || "").replace(/^\?/, "").split("&").forEach(function (p) {
      if (!p) return;
      var i = p.indexOf("="), k = decodeURIComponent(i < 0 ? p : p.slice(0, i)), v = decodeURIComponent((i < 0 ? "" : p.slice(i + 1)).replace(/\+/g, " "));
      q[k] = v;
    });
    return q;
  }
  function dotClass(c, dim) {
    var approx = !!(c && (c.exact === false || c.approximate || c.precision === "country"));
    return "signal" + (approx ? " approx" : "") + (dim ? " dim" : "");
  }
  function landStyle() {
    if (themeLight()) return { color: "#C5D0DC", weight: 0.7, fillColor: "#F7F9FB", fillOpacity: 1 };
    return { color: "#364158", weight: 0.6, fillColor: "#192538", fillOpacity: 0.7 };
  }

  function mount(el) {
    if (!el || el.getAttribute("data-map")) return;
    if (!(global.L && L.map)) {
      var missing = el.querySelector(".bn-sig-note");
      if (missing) missing.textContent = "The map library could not load.";
      return;
    }
    el.setAttribute("data-map", "1");
    el.style.removeProperty("background-color");
    var embed = el.getAttribute("data-embed") !== "0";
    var box = el.querySelector(".bn-sig-map");
    var note = el.querySelector(".bn-sig-note");
    if (!box) return;
    var coarse = false;
    try { coarse = window.matchMedia("(hover: none), (pointer: coarse)").matches; } catch (e) {}
    box.style.removeProperty("background-color");
    if (embed) box.style.touchAction = "pan-y";
    var map = L.map(box, {
      zoomControl: true, worldCopyJump: true, preferCanvas: true, attributionControl: true, maxZoom: MAX_Z,
      zoomSnap: 0,
      dragging: !embed, scrollWheelZoom: !embed, touchZoom: !embed, doubleClickZoom: !embed, boxZoom: !embed, keyboard: !embed
    });
    var usLocked = false;
    var LOWER48 = [[24.5, -125], [49.5, -66.5]];
    function fitUS() {
      if ((box.clientWidth || 0) < 40 || (box.clientHeight || 0) < 40) return false;
      framing++;
      map.fitBounds(LOWER48, { animate: false, padding: [12, 12] });
      framing--;
      return true;
    }
    function frameUS() {
      if (viewName !== "us" || usLocked) return;
      fitUS();
    }
    map.on("zoomstart", function () { if (!framing && viewName === "us") usLocked = true; });
    map.on("dragstart", function () { if (!framing && viewName === "us") usLocked = true; });
    map.attributionControl.setPrefix("");
    map.attributionControl.addAttribution("Natural Earth");
    var world = null, markers = L.layerGroup().addTo(map), rows = [], armed = null, tip, hideT = 0, open = null;
    var viewName = "us", framing = 0, listEl = null, timer = 0;
    var enabled = CAT_IDS.slice(), query = "", qTimer = 0, flown = false;
    var input = el.querySelector(".bn-sig-search input");
    var clearBtn = el.querySelector(".bn-sig-clear");
    var results = el.querySelector(".bn-sig-results");
    var form = el.querySelector(".bn-sig-search");
    frameUS();

    try { enabled = enabledFrom(localStorage.getItem(CAT_KEY)); } catch (e) {}

    tip = document.createElement("div");
    tip.className = "bn-sig-tip";
    tip.hidden = true;
    tip.setAttribute("role", "tooltip");
    tip.addEventListener("mouseenter", function () { clearTimeout(hideT); });
    tip.addEventListener("mouseleave", hideSoon);
    box.appendChild(tip);

    function hide() { tip.hidden = true; open = null; }
    function hideSoon() { clearTimeout(hideT); hideT = setTimeout(hide, 160); }
    function show(c, latlng) {
      clearTimeout(hideT);
      var b = band(c.rank), time = et(when(c)), meta = catOf(c);
      tip.textContent = "";
      var h = document.createElement("b"), s = document.createElement("span");
      h.textContent = text(c.title) || "Untitled";
      s.textContent = meta.label + " · Rank " + b.r + "/10" + (time ? " · " + time : "");
      tip.appendChild(h); tip.appendChild(s);
      if (c.exact === false) {
        var n = document.createElement("span");
        n.className = "approx";
        n.textContent = "Approximate location, inferred from report";
        tip.appendChild(n);
      }
      var d = dest(c), a = document.createElement("a");
      a.href = d.href;
      a.textContent = d.label;
      if (d.ext) { a.target = "_blank"; a.rel = "noopener"; }
      tip.appendChild(a);
      tip.hidden = false;
      open = c;
      var p = map.latLngToContainerPoint(latlng), w = tip.offsetWidth, ht = tip.offsetHeight;
      var x = p.x - w / 2, y = p.y - ht - 12, cw = box.clientWidth, ch = box.clientHeight;
      if (x < 8) x = 8;
      if (x + w > cw - 8) x = Math.max(8, cw - 8 - w);
      if (y < 8) y = Math.min(p.y + 14, ch - ht - 8);
      tip.style.left = x + "px"; tip.style.top = y + "px";
    }
    function go(c) {
      var d = dest(c);
      if (!d) return;
      if (d.ext) window.open(d.href, "_blank", "noopener");
      else location.href = d.href;
    }
    function onMarker(c, marker) {
      var b = band(c.rank), time = et(when(c)), meta = catOf(c);
      function label() {
        var s = (text(c.title) || "Story") + ". " + meta.label + ". Rank " + b.r + " of 10." + (time ? " " + time + "." : "");
        if (c.exact === false) s += " Approximate location, inferred from report.";
        s += " " + dest(c).label;
        return s;
      }
      marker.on("mouseover", function (ev) {
        var pt = ev && ev.originalEvent && ev.originalEvent.pointerType;
        if (pt === "touch") return;
        show(c, marker.getLatLng());
      });
      marker.on("mouseout", function (ev) {
        var pt = ev && ev.originalEvent && ev.originalEvent.pointerType;
        if (pt === "touch") return;
        hideSoon();
      });
      marker.on("click", function (ev) {
        if (L.DomEvent) L.DomEvent.stop(ev);
        var oe = (ev && ev.originalEvent) || {};
        var touch = oe.pointerType === "touch" || (oe.sourceCapabilities && oe.sourceCapabilities.firesTouchEvents);
        if ((touch || coarse) && armed !== c.cluster_id) { armed = c.cluster_id; show(c, marker.getLatLng()); return; }
        go(c);
      });
      marker.on("add", function () {
        var node = marker.getElement();
        if (!node) return;
        node.setAttribute("role", "button");
        node.setAttribute("aria-label", label());
      });
    }
    function filters() {
      var f = { rank: "", topic: "", hours: 168, conflict: viewName === "conflicts", cats: enabled.slice() };
      if (embed) return f;
      var rank = el.querySelector("#bn_sig_rank"), topic = el.querySelector("#bn_sig_topic"), win = el.querySelector("#bn_sig_win");
      f.rank = rank ? rank.value : "";
      f.topic = topic ? topic.value : "";
      f.hours = win && win.value ? +win.value : 168;
      return f;
    }
    function drawFilters() {
      var f = filters();
      if (!query) return f;
      return { rank: f.rank, topic: f.topic, hours: f.hours, conflict: false, cats: f.cats };
    }
    function say(s) { if (note) note.textContent = s; }
    function paintViews() {
      el.querySelectorAll("[data-view]").forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-view") === viewName ? "true" : "false");
      });
    }
    function paintCats() {
      var on = {}, i;
      for (i = 0; i < enabled.length; i++) on[enabled[i]] = 1;
      el.querySelectorAll(".bn-sig-cats button").forEach(function (b) {
        var id = b.getAttribute("data-cat");
        var pressed = id === "all" ? enabled.length === CAT_IDS.length : id === "none" ? enabled.length === 0 : !!on[id];
        b.setAttribute("aria-pressed", pressed ? "true" : "false");
        if (CATS[id]) {
          var dot = b.querySelector("i");
          if (dot) dot.style.background = colorFor(id);
        }
      });
    }
    function saveCats() {
      try { localStorage.setItem(CAT_KEY, JSON.stringify(disabledFrom(enabled))); } catch (e) {}
    }
    function activeRows(list, f, now) {
      var out = [], i;
      for (i = 0; i < list.length; i++) if (pass(list[i], f, now)) out.push(list[i]);
      return out;
    }
    function searchPool() {
      var f = filters();
      return activeRows(rows, { rank: f.rank, topic: f.topic, hours: f.hours, conflict: false, cats: f.cats }, Date.now());
    }
    function paintCounts() {
      var tally = viewCounts(rows, filters(), Date.now());
      el.querySelectorAll("[data-n]").forEach(function (n) {
        var k = n.getAttribute("data-n");
        n.textContent = String(k === "us" ? tally.us : k === "conflicts" ? tally.conflicts : tally.world);
      });
      var line = el.querySelector(".bn-sig-counts");
      var f = filters(), now = Date.now();
      var focusF = { rank: f.rank, topic: f.topic, hours: f.hours, conflict: viewName === "conflicts", cats: f.cats };
      var focus = activeRows(rows, focusF, now), cats = {}, i, name;
      if (viewName === "us") focus = focus.filter(inUS);
      for (i = 0; i < focus.length; i++) {
        name = catOf(focus[i]).label;
        cats[name] = (cats[name] || 0) + 1;
      }
      if (line) {
        var names = Object.keys(cats).sort(function (a, b) { return cats[b] - cats[a]; });
        line.textContent = names.map(function (k) { return k + " " + cats[k]; }).join(" · ");
      }
      return tally;
    }
    function closeResults() {
      if (!results) return;
      results.hidden = true;
      results.textContent = "";
      if (input) input.setAttribute("aria-expanded", "false");
    }
    function paintResults() {
      if (!results) return;
      var q = text(query);
      results.textContent = "";
      if (!q) { closeResults(); return; }
      var hits = topMatches(searchPool(), q, 6), i;
      if (!hits.length) {
        var empty = document.createElement("p");
        empty.className = "bn-sig-none";
        empty.textContent = "No matching stories";
        results.appendChild(empty);
      }
      for (i = 0; i < hits.length; i++) {
        (function (c) {
          var meta = catOf(c), b = document.createElement("button"), sw = document.createElement("i"), col = document.createElement("span"), t = document.createElement("b"), s = document.createElement("span");
          b.type = "button";
          b.className = "bn-sig-hit";
          b.setAttribute("role", "option");
          sw.style.background = colorFor(meta.id);
          sw.setAttribute("aria-hidden", "true");
          t.textContent = text(c.title) || "Untitled";
          s.textContent = meta.label + (c.place ? " · " + text(c.place) : "");
          col.className = "bn-sig-hit-t";
          col.appendChild(t); col.appendChild(s);
          b.appendChild(sw); b.appendChild(col);
          b.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            focusStory(c);
          });
          results.appendChild(b);
        })(hits[i]);
      }
      results.hidden = false;
      if (input) input.setAttribute("aria-expanded", "true");
    }
    function setQuery(v) {
      v = text(v);
      var changed = v !== query;
      query = v;
      if (input && input.value !== v) input.value = v;
      if (clearBtn) clearBtn.hidden = !v;
      if (!v && flown) {
        flown = false;
        usLocked = false;
        frame(viewName);
      }
      if (changed) draw(false);
      paintResults();
    }
    function focusStory(c) {
      if (!c || !real(c)) return;
      closeResults();
      flown = true;
      usLocked = true;
      var country = c.precision === "country" || c.approximate;
      var z = Math.min(MAX_Z, Math.max(map.getZoom() || 2, country ? 4 : 6));
      var reduce = false, finished = false;
      try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
      function done() {
        draw(false);
        show(c, L.latLng(+c.lat, +c.lon));
      }
      function finish() {
        if (finished) return;
        finished = true;
        framing = Math.max(0, framing - 1);
        done();
      }
      framing++;
      if (reduce) {
        map.setView([+c.lat, +c.lon], z, { animate: false });
        finish();
        return;
      }
      map.once("moveend", finish);
      map.flyTo([+c.lat, +c.lon], z, { animate: true, duration: 0.7 });
      setTimeout(finish, 1200);
    }
    function closeList() {
      if (listEl) { listEl.hidden = true; listEl.textContent = ""; }
    }
    function showList(group) {
      if (!listEl) {
        listEl = document.createElement("div");
        listEl.className = "bn-sig-list";
        listEl.setAttribute("role", "dialog");
        listEl.setAttribute("aria-label", "Stories at this place");
        box.appendChild(listEl);
      }
      listEl.textContent = "";
      var head = document.createElement("div");
      head.className = "bn-sig-list-h";
      var title = document.createElement("b");
      title.textContent = group.length + " stories";
      var x = document.createElement("button");
      x.type = "button";
      x.className = "bn-sig-list-x";
      x.setAttribute("aria-label", "Close");
      x.textContent = "×";
      x.onclick = function (ev) { ev.preventDefault(); ev.stopPropagation(); closeList(); };
      head.appendChild(title); head.appendChild(x);
      listEl.appendChild(head);
      var ul = document.createElement("div");
      ul.className = "bn-sig-list-b";
      group.forEach(function (c) {
        var d = dest(c), row = document.createElement("button"), meta = catOf(c);
        row.type = "button";
        row.className = "bn-sig-list-i";
        var t = document.createElement("b");
        t.textContent = text(c.title) || "Untitled";
        var s = document.createElement("span");
        s.textContent = meta.label + (c.place ? " · " + text(c.place) : "") + " · Rank " + band(c.rank).r + "/10 · " + (d ? d.label : "");
        row.appendChild(t); row.appendChild(s);
        row.onclick = function (ev) { ev.preventDefault(); ev.stopPropagation(); go(c); };
        ul.appendChild(row);
      });
      listEl.appendChild(ul);
      listEl.hidden = false;
    }
    function dotIcon(c, first, dim) {
      var col = colorFor(catOf(c).id);
      var delay = first ? (Math.random() * 15).toFixed(3) + "s" : "";
      var icon = L.divIcon({
        className: "bn-sig-mk" + (first ? " bn-sig-enter" : " bn-sig-fade"),
        html: '<div class="' + dotClass(c, dim) + '" style="color:' + col + '"></div>',
        iconSize: [12, 12], iconAnchor: [6, 6]
      });
      if (delay) icon.createIcon = function (old) {
        var node = L.DivIcon.prototype.createIcon.call(this, old);
        node.style.setProperty("--bn-d", delay);
        return node;
      };
      return icon;
    }
    function countIcon(n, members, dim) {
      var size = Math.min(40, 24 + Math.round(Math.log(n) / Math.LN2) * 2);
      var color = dominantColor(members);
      var neutral = color === neutralColor();
      var bg, fg, bd;
      if (neutral) {
        bg = themeLight() ? "#ffffff" : "#1b2838";
        fg = themeLight() ? "#1d1d1f" : "#e5ecf7";
        bd = color;
      } else {
        bg = color; bd = color; fg = inkOn(color);
      }
      return L.divIcon({
        className: "bn-sig-cl",
        html: '<div class="bn-count' + (dim ? " dim" : "") + '" style="width:' + size + 'px;height:' + size + 'px;background:' + bg + ';color:' + fg + ';border-color:' + bd + '">' + n + "</div>",
        iconSize: [size, size], iconAnchor: [size / 2, size / 2]
      });
    }
    function groupDim(members) {
      if (!query) return false;
      var i;
      for (i = 0; i < members.length; i++) if (matches(members[i], query)) return false;
      return true;
    }
    function onCluster(group, marker) {
      var last = 0;
      function activate(ev) {
        if (L.DomEvent) L.DomEvent.stop(ev);
        var now = Date.now();
        if (now - last < 450) return;
        last = now;
        var oe = (ev && ev.originalEvent) || {};
        var touch = coarse || oe.pointerType === "touch" || oe.type === "touchend" || oe.type === "touchstart" || (oe.sourceCapabilities && oe.sourceCapabilities.firesTouchEvents);
        var bounds = L.latLngBounds(group.map(function (c) { return [+c.lat, +c.lon]; }));
        var country = group.every(function (c) { return c.precision === "country" || c.approximate; });
        var tiny = bounds.getNorthEast().distanceTo(bounds.getSouthWest()) < 40000;
        if (!touch && !country && !tiny && map.getZoom() < map.getMaxZoom()) {
          usLocked = true;
          framing++;
          map.fitBounds(bounds, { maxZoom: map.getMaxZoom(), animate: false, padding: [36, 36] });
          framing--;
          return;
        }
        showList(group);
      }
      marker.on("click", activate);
      marker.on("touchend", activate);
      marker.on("add", function () {
        var node = marker.getElement();
        if (!node) return;
        node.setAttribute("role", "button");
        node.setAttribute("aria-label", group.length + " stories. Open the list or zoom in.");
        node.style.touchAction = "manipulation";
      });
    }
    function draw(first) {
      markers.clearLayers();
      hide(); closeList(); armed = null;
      var f = drawFilters(), now = Date.now(), shown = activeRows(rows, f, now), i;
      var zoom = map.getZoom() || 2;
      var plan = clusterPlan(shown, zoom);
      plan.forEach(function (g) {
        var members = g.idx.map(function (ix) { return shown[ix]; });
        if (g.n === 1) {
          var c = members[0];
          var marker = L.marker([+c.lat, +c.lon], { icon: dotIcon(c, first, query && !matches(c, query)), keyboard: false });
          onMarker(c, marker);
          marker.addTo(markers);
          return;
        }
        if (g.spider) {
          var center = map.latLngToLayerPoint([+members[0].lat, +members[0].lon]);
          members.forEach(function (c, j) {
            var at = map.layerPointToLatLng(L.point(center.x + g.offsets[j].dx, center.y + g.offsets[j].dy));
            var mk = L.marker(at, { icon: dotIcon(c, first, query && !matches(c, query)), keyboard: false });
            onMarker(c, mk);
            mk.addTo(markers);
          });
          return;
        }
        var lat = 0, lon = 0;
        members.forEach(function (c) { lat += +c.lat; lon += +c.lon; });
        var cm = L.marker([lat / g.n, lon / g.n], { icon: countIcon(g.n, members, groupDim(members)), keyboard: false });
        onCluster(members, cm);
        cm.addTo(markers);
      });
      var tally = paintCounts();
      var noun = shown.length === 1 ? "record" : "records";
      if (query) {
        var nMatch = 0;
        for (i = 0; i < shown.length; i++) if (matches(shown[i], query)) nMatch++;
        say(nMatch + (nMatch === 1 ? " match" : " matches") + " · other stories dimmed");
      } else {
        var focus = viewName === "us" ? tally.us : viewName === "conflicts" ? tally.conflicts : shown.length;
        var label = viewName === "us" ? " in the United States" : viewName === "conflicts" ? " war/conflict" : "";
        say(focus + label + " · " + shown.length + " " + noun + " on this view · colored by category");
      }
      setTimeout(function () { refit(); }, 60);
    }
    function widthZoom(wide, narrow) { return (box.clientWidth || 800) < 700 ? narrow : wide; }
    function frame(name) {
      viewName = name === "world" || name === "conflicts" ? name : "us";
      if (viewName === "us") usLocked = false;
      paintViews();
      framing++;
      if (viewName === "conflicts") map.fitBounds([[28, -8], [58, 64]], { animate: false, padding: [28, 28] });
      else if (viewName === "world") map.setView([20, 0], widthZoom(2, 1), { animate: false });
      else fitUS();
      framing--;
    }
    function fillTopics() {
      var sel = el.querySelector("#bn_sig_topic");
      if (!sel) return;
      var cur = sel.value, seen = {}, list = [], i;
      for (i = 0; i < rows.length; i++) if (rows[i].category && !seen[rows[i].category]) { seen[rows[i].category] = 1; list.push(rows[i].category); }
      list.sort();
      sel.textContent = "";
      var all = document.createElement("option"); all.value = ""; all.textContent = "All topics"; sel.appendChild(all);
      list.forEach(function (name) {
        var o = document.createElement("option"); o.value = name; o.textContent = name; if (name === cur) o.selected = true; sel.appendChild(o);
      });
      if (cur && !seen[cur]) { var extra = document.createElement("option"); extra.value = cur; extra.textContent = cur; extra.selected = true; sel.appendChild(extra); }
    }
    function readUrl() {
      if (embed) return;
      var q = qs();
      var rank = el.querySelector("#bn_sig_rank"), win = el.querySelector("#bn_sig_win"), topic = el.querySelector("#bn_sig_topic");
      if (rank && (q.rank === "0" || q.rank === "4" || q.rank === "7")) rank.value = q.rank;
      if (win && (q.window === "24" || q.window === "72" || q.window === "168")) win.value = q.window;
      if (topic && q.topic) topic.value = q.topic;
      if (q.view === "world" || q.view === "conflicts" || q.view === "us") viewName = q.view;
    }
    function writeUrl() {
      if (embed) return;
      var f = filters();
      var p = new URLSearchParams();
      if (f.topic) p.set("topic", f.topic);
      if (f.rank) p.set("rank", f.rank);
      if (String(f.hours) !== "168") p.set("window", String(f.hours));
      if (viewName && viewName !== "us") p.set("view", viewName);
      var s = p.toString();
      history.replaceState(null, "", s ? "?" + s : location.pathname);
    }
    map.on("click", function (e) {
      var t = e.originalEvent && e.originalEvent.target;
      if (t && t.closest && t.closest("a,button,.leaflet-control,.bn-sig-tip,.bn-sig-mk,.bn-sig-cl,.bn-sig-list,.bn-sig-views,.bn-sig-find,.bn-sig-cats")) return;
      armed = null; hide(); closeList();
      if (embed) location.href = "/map";
    });
    map.on("movestart", function () { if (!coarse) hide(); });
    map.on("zoomend", function () { if (!framing && rows.length) draw(false); });
    ["#bn_sig_rank", "#bn_sig_topic", "#bn_sig_win"].forEach(function (id) {
      var n = el.querySelector(id);
      if (n) n.addEventListener("change", function () { writeUrl(); draw(false); });
    });
    el.querySelectorAll(".bn-sig-cats button").forEach(function (b) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var id = b.getAttribute("data-cat"), i;
        if (id === "all") enabled = CAT_IDS.slice();
        else if (id === "none") enabled = [];
        else if (CATS[id]) {
          i = enabled.indexOf(id);
          if (i >= 0) enabled.splice(i, 1);
          else enabled.push(id);
        } else return;
        paintCats();
        saveCats();
        draw(false);
        if (query) paintResults();
      });
    });
    el.querySelectorAll("[data-view]").forEach(function (b) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var name = b.getAttribute("data-view");
        if (name !== "us" && name !== "world" && name !== "conflicts") return;
        if (name === "conflicts") {
          var topic = el.querySelector("#bn_sig_topic");
          if (topic && topic.value && topic.value !== "war/conflict") topic.value = "";
        }
        flown = false;
        frame(name);
        writeUrl();
        draw(false);
      });
    });
    if (form) form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      clearTimeout(qTimer);
      setQuery(input ? input.value : "");
      var hits = topMatches(searchPool(), query, 1);
      if (hits[0]) focusStory(hits[0]);
    });
    if (input) {
      input.addEventListener("input", function () {
        if (clearBtn) clearBtn.hidden = !input.value;
        clearTimeout(qTimer);
        qTimer = setTimeout(function () { setQuery(input.value); }, SEARCH_MS);
      });
      input.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") {
          ev.preventDefault();
          clearTimeout(qTimer);
          input.value = "";
          setQuery("");
        } else if (ev.key === "ArrowDown") {
          var first = results && results.querySelector(".bn-sig-hit");
          if (first) { ev.preventDefault(); first.focus(); }
        }
      });
    }
    if (clearBtn) clearBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      clearTimeout(qTimer);
      if (input) input.value = "";
      setQuery("");
      if (input) input.focus();
    });
    document.addEventListener("click", function (ev) {
      if (!results || results.hidden) return;
      if (ev.target && ev.target.closest && ev.target.closest(".bn-sig-find")) return;
      results.hidden = true;
      if (input) input.setAttribute("aria-expanded", "false");
    });
    function refit() {
      framing++;
      map.invalidateSize({ animate: false, pan: false });
      framing--;
      frameUS();
      if (open) show(open, L.latLng(+open.lat, +open.lon));
    }
    if (window.ResizeObserver) new ResizeObserver(function () { refit(); }).observe(box);
    else window.addEventListener("resize", function () { refit(); });
    if (window.MutationObserver) {
      new MutationObserver(function () {
        paintCats();
        if (world && world.setStyle) world.setStyle(landStyle());
        if (rows.length) draw(false);
      }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
    paintCats();

    fetch(GEO).then(function (r) { return r.json(); }).then(function (geo) {
      world = L.geoJSON(geo, { style: function () { return landStyle(); }, interactive: false }).addTo(map);
      if (world.bringToBack) world.bringToBack();
      map.invalidateSize();
    }).catch(function () { say("World outline could not load. Dots still use real coordinates."); });

    function pull(first) {
      fetch("/api/signal/points", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("points"); return r.json(); }).then(function (S) {
        rows = ((S && S.points) || []).filter(real);
        if (first) { fillTopics(); readUrl(); if (viewName !== "us") frame(viewName); }
        draw(first);
        if (query) paintResults();
      }).catch(function () { if (first) say("Stories could not load. The map is the bundled world outline."); });
    }
    readUrl();
    if (viewName !== "us") frame(viewName);
    pull(true);
    timer = setInterval(function () { pull(false); }, 300000);
  }

  global.BNSignal = {
    mount: mount, band: band, real: real, dest: dest, pass: pass,
    conflict: conflict, inUS: inUS, clusterPlan: clusterPlan, FAN_MAX: FAN_MAX, SPIDER_PX: SPIDER_PX,
    catOf: catOf, CATS: CATS, CAT_IDS: CAT_IDS, colorFor: colorFor, matches: matches, topMatches: topMatches,
    dominantColor: dominantColor, neutralColor: neutralColor, enabledFrom: enabledFrom, disabledFrom: disabledFrom,
    viewCounts: viewCounts, dotClass: dotClass, SEARCH_MS: SEARCH_MS, CAT_KEY: CAT_KEY
  };
})(typeof window !== "undefined" ? window : globalThis);
