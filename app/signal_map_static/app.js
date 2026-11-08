/* Global signal map. Same Leaflet + Natural Earth drawing as Control panel v2.
   Dots: Wire and Watchlist only. Stored coordinates and city placements stay filled.
   Country centroids are hollow. Red is rank 7-10 only. No tile servers.
   The camera starts on the US. World and Conflicts move it; they do not change that default.
   Dots that share a coordinate are fanned out so each one can be tapped.
   Link order: Wire story, then the matching tracker, then the external source, then a site page so every dot links. */
(function (global) {
  "use strict";
  var GEO = "/api/signal/world.geojson";
  var LOW = "#55b7ff", MID = "#F5A524", HIGH = "#FF4D4F";
  var REFRESH_MS = 300000;
  var US = { lat: 39, lon: -98 };
  var WORLD = { lat: 20, lon: 0 };
  /* Europe through the Gulf, so Ukraine, the Levant and Iran are on screen together. */
  var CONFLICTS = { south: 28, west: -8, north: 58, east: 64 };

  function band(rank) {
    var r = Math.max(0, Math.min(10, Math.round(+rank || 0)));
    if (r >= 7) return { r: r, name: "High", color: HIGH };
    if (r >= 4) return { r: r, name: "Elevated", color: MID };
    return { r: r, name: "Low", color: LOW };
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
  function conflict(c) {
    return String(c && c.category || "").toLowerCase() === "war/conflict";
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
  function pass(c, f, now) {
    if (!real(c)) return false;
    var r = band(c.rank).r;
    if (f.rank === "7" && r < 7) return false;
    if (f.rank === "4" && (r < 4 || r > 6)) return false;
    if (f.rank === "0" && r > 3) return false;
    if (f.topic && c.category !== f.topic) return false;
    if (f.conflict && !conflict(c)) return false;
    if (f.hours) {
      var t = Date.parse(when(c));
      if (!isFinite(t) || now - t > f.hours * 3600000) return false;
    }
    return true;
  }
  function viewSpec(name) {
    if (name === "world") return { name: "world", lat: WORLD.lat, lon: WORLD.lon, conflict: false };
    if (name === "conflicts") return { name: "conflicts", bounds: CONFLICTS, conflict: true };
    return { name: "us", lat: US.lat, lon: US.lon, conflict: false };
  }
  /* Pixel offsets for stories that share a coordinate. A lone dot stays put. */
  function spread(items) {
    var groups = {}, out = [], i, c, k;
    for (i = 0; i < items.length; i++) {
      c = items[i];
      k = (Math.round(+c.lat * 100) / 100) + "," + (Math.round(+c.lon * 100) / 100);
      if (!groups[k]) groups[k] = [];
      groups[k].push(i);
      out.push({ lat: +c.lat, lon: +c.lon, dx: 0, dy: 0 });
    }
    Object.keys(groups).forEach(function (key) {
      var ix = groups[key], n = ix.length, rad, j, ang;
      if (n < 2) return;
      rad = Math.max(16, Math.min(90, (n * 16) / (2 * Math.PI) + 8));
      for (j = 0; j < n; j++) {
        ang = -Math.PI / 2 + (2 * Math.PI * j) / n;
        out[ix[j]].dx = Math.cos(ang) * rad;
        out[ix[j]].dy = Math.sin(ang) * rad;
      }
    });
    return out;
  }
  function counts(rows, f, now) {
    var base = { rank: f.rank, topic: f.topic, hours: f.hours, conflict: false };
    var cats = {}, total = 0, war = 0, i, k;
    for (i = 0; i < rows.length; i++) {
      if (!pass(rows[i], base, now)) continue;
      total++;
      k = rows[i].category || "other";
      cats[k] = (cats[k] || 0) + 1;
      if (conflict(rows[i])) war++;
    }
    return { cats: cats, total: total, war: war };
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
      zoomControl: true, worldCopyJump: true, preferCanvas: true, attributionControl: true,
      dragging: !embed, scrollWheelZoom: !embed, touchZoom: !embed, doubleClickZoom: !embed, boxZoom: !embed, keyboard: !embed
    });
    var framed = false;
    function usZoom() {
      var w = box.clientWidth, h = box.clientHeight;
      if (w < 40 || h < 40) return 0;
      // Narrow screens keep the whole country in frame. Desktop fills the view with the lower 48;
      // a short card cannot use the full-page zoom without cutting the country in half.
      if (w < 700) return h < 360 ? 2 : 3;
      return h < 520 ? 4 : 5;
    }
    function frameUS() {
      if (framed) return;
      var z = usZoom();
      if (!z) return;
      map.setView([39, -98], z, { animate: false });
      framed = true;
    }
    frameUS();
    if (!framed) map.setView([39, -98], (window.innerWidth || 800) < 700 ? 3 : 4);
    map.attributionControl.setPrefix("");
    map.attributionControl.addAttribution("Natural Earth");
    var world = null, markers = L.layerGroup().addTo(map), rows = [], armed = null, tip, hideT = 0, open = null;
    var viewName = "us", framing = 0, introduced = false, stamp = "", generated = "", unmapped = 0, timer = 0;

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
      var b = band(c.rank), time = et(when(c));
      tip.textContent = "";
      var h = document.createElement("b"), s = document.createElement("span");
      h.textContent = text(c.title) || "Untitled";
      s.textContent = "Rank " + b.r + "/10" + (time ? " · " + time : "");
      tip.appendChild(h); tip.appendChild(s);
      if (c.exact === false || c.approximate) {
        var n = document.createElement("span");
        n.className = "approx";
        n.textContent = "Approximate" + (c.place ? " · " + text(c.place) : " location, country centroid");
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
    function onMarker(c, marker, delay) {
      var b = band(c.rank), time = et(when(c));
      function label() {
        var s = (text(c.title) || "Story") + ". Rank " + b.r + " of 10." + (time ? " " + time + "." : "");
        if (c.exact === false || c.approximate) s += " Approximate location.";
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
        if (delay) node.style.setProperty("--bn-d", delay);
      });
    }
    function filters() {
      var f = { rank: "", topic: "", hours: 168, conflict: viewName === "conflicts" };
      if (embed) return f;
      var rank = el.querySelector("#bn_sig_rank"), topic = el.querySelector("#bn_sig_topic"), win = el.querySelector("#bn_sig_win");
      f.rank = rank ? rank.value : "";
      f.topic = topic ? topic.value : "";
      f.hours = win && win.value ? +win.value : 168;
      return f;
    }
    function say(s) { if (note) note.textContent = s; }
    function widthZoom(wide, narrow) {
      return (box.clientWidth || el.clientWidth || 800) < 700 ? narrow : wide;
    }
    function paintViews() {
      el.querySelectorAll("[data-view]").forEach(function (b) {
        var on = b.getAttribute("data-view") === viewName;
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }
    function paintCounts() {
      var tally = counts(rows, filters(), Date.now());
      el.querySelectorAll("[data-n]").forEach(function (n) {
        var k = n.getAttribute("data-n");
        n.textContent = k === "conflicts" ? String(tally.war) : String(tally.total);
      });
      var line = el.querySelector(".bn-sig-counts");
      if (!line) return;
      var names = Object.keys(tally.cats).sort(function (a, b) { return tally.cats[b] - tally.cats[a] || (a < b ? -1 : 1); });
      line.textContent = names.length ? names.map(function (k) { return k + " " + tally.cats[k]; }).join(" · ") : "";
    }
    function fan(list) {
      /* Screen-space groups catch dots that are not the same coordinate but still sit on top of each other. */
      var pts = list.map(function (c) { return { c: c, p: map.latLngToLayerPoint([+c.lat, +c.lon]) }; });
      var parent = pts.map(function (_, i) { return i; });
      function find(a) { while (parent[a] !== a) a = parent[a] = parent[parent[a]]; return a; }
      function unite(a, b) { a = find(a); b = find(b); if (a !== b) parent[b] = a; }
      var i, j, dx, dy;
      for (i = 0; i < pts.length; i++) {
        for (j = i + 1; j < pts.length; j++) {
          dx = pts[i].p.x - pts[j].p.x; dy = pts[i].p.y - pts[j].p.y;
          if (dx * dx + dy * dy < 20 * 20) unite(i, j);
        }
      }
      var buckets = {};
      pts.forEach(function (pt, idx) {
        var r = find(idx);
        if (!buckets[r]) buckets[r] = [];
        buckets[r].push(pt);
      });
      Object.keys(buckets).forEach(function (key) {
        var g = buckets[key], n = g.length, cx = 0, cy = 0, rad, a, ang;
        if (n === 1) { g[0].at = g[0].p; return; }
        g.forEach(function (pt) { cx += pt.p.x; cy += pt.p.y; });
        cx /= n; cy /= n;
        rad = Math.max(16, Math.min(90, (n * 16) / (2 * Math.PI) + 8));
        for (a = 0; a < n; a++) {
          ang = -Math.PI / 2 + (2 * Math.PI * a) / n;
          g[a].at = L.point(cx + Math.cos(ang) * rad, cy + Math.sin(ang) * rad);
        }
      });
      return pts;
    }
    function draw(first) {
      markers.clearLayers();
      hide(); armed = null;
      var f = filters(), now = Date.now(), shown = [], i;
      for (i = 0; i < rows.length; i++) if (pass(rows[i], f, now)) shown.push(rows[i]);
      var spots = fan(shown);
      var enter = first && !introduced;
      spots.forEach(function (spot) {
        var c = spot.c, b = band(c.rank);
        var delay = enter ? (Math.random() * 15).toFixed(3) + "s" : "";
        var approx = c.exact === false || c.approximate;
        var icon = L.divIcon({ className: "bn-sig-mk" + (enter ? " bn-sig-enter" : " bn-sig-fade"), html: '<div class="signal' + (approx ? " approx" : "") + '" style="color:' + b.color + '"></div>', iconSize: [12, 12], iconAnchor: [6, 6] });
        if (delay) icon.createIcon = function (old) {
          var node = L.DivIcon.prototype.createIcon.call(this, old);
          node.style.setProperty("--bn-d", delay);
          return node;
        };
        var ll = map.layerPointToLatLng(spot.at);
        var marker = L.marker(ll, { icon: icon, keyboard: false });
        onMarker(c, marker, delay);
        marker.addTo(markers);
      });
      if (enter) introduced = true;
      var inf = 0, noun = shown.length === 1 ? "record" : "records";
      for (i = 0; i < shown.length; i++) if (shown[i].exact === false || shown[i].approximate) inf++;
      var fresh = generated ? et(generated) : "";
      say(shown.length + " " + noun + " shown" + (rows.length > shown.length ? " of " + rows.length : "") + (inf ? " · " + inf + " approximate" : "") + (unmapped ? " · " + unmapped + " not on the map" : "") + (fresh ? " · as of " + fresh : "") + " · dots follow rank");
      paintCounts();
      setTimeout(function () { map.invalidateSize(); frameUS(); }, 60);
    }
    function frame(name) {
      var spec = viewSpec(name);
      viewName = spec.name;
      framed = true;
      paintViews();
      framing++;
      if (spec.bounds) {
        map.fitBounds([[spec.bounds.south, spec.bounds.west], [spec.bounds.north, spec.bounds.east]], { animate: false, padding: [28, 28] });
      } else if (spec.name === "world") {
        map.setView([spec.lat, spec.lon], widthZoom(2, 1), { animate: false });
      } else {
        map.setView([US.lat, US.lon], usZoom() || widthZoom(4, 3), { animate: false });
      }
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
      if (t && t.closest && t.closest("a,button,.leaflet-control,.bn-sig-tip,.bn-sig-mk,.bn-sig-views")) return;
      armed = null; hide();
      if (embed) location.href = "/map";
    });
    map.on("movestart", function () { if (!coarse) hide(); });
    map.on("zoomend", function () { if (!framing && rows.length) draw(false); });
    ["#bn_sig_rank", "#bn_sig_topic", "#bn_sig_win"].forEach(function (id) {
      var n = el.querySelector(id);
      if (n) n.addEventListener("change", function () { writeUrl(); draw(false); });
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
        frame(name);
        writeUrl();
        draw(false);
      });
    });
    if (window.ResizeObserver) new ResizeObserver(function () { map.invalidateSize(); frameUS(); if (open) show(open, L.latLng(+open.lat, +open.lon)); }).observe(box);
    else window.addEventListener("resize", function () { map.invalidateSize(); frameUS(); });

    fetch(GEO).then(function (r) { return r.json(); }).then(function (geo) {
      world = L.geoJSON(geo, { style: { color: "#364158", weight: 0.6, fillColor: "#192538", fillOpacity: 0.7 }, interactive: false }).addTo(map);
      if (world.bringToBack) world.bringToBack();
      map.invalidateSize();
    }).catch(function () { say("World outline could not load. Dots still use real coordinates."); });

    function digest(list) {
      return list.map(function (c) { return (c.cluster_id || "") + "|" + c.lat + "|" + c.lon + "|" + c.rank + "|" + (c.category || ""); }).join(";");
    }
    function pull(first) {
      fetch("/api/signal/points", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("points"); return r.json(); }).then(function (S) {
        var next = ((S && S.points) || []).filter(real);
        var nextStamp = digest(next);
        generated = (S && S.generated) || generated;
        unmapped = S && S.unmapped != null ? +S.unmapped : unmapped;
        if (!first && nextStamp === stamp) { paintCounts(); return; }
        stamp = nextStamp;
        rows = next;
        fillTopics();
        if (first) readUrl();
        draw(first);
      }).catch(function () { if (first) say("Stories could not load. The map is the bundled world outline."); });
    }
    readUrl();
    if (viewName === "us") { if (!framed) frameUS(); }
    else frame(viewName);
    pull(true);
    timer = setInterval(function () { pull(false); }, REFRESH_MS);
    el._bnSigRefresh = timer;
  }

  global.BNSignal = {
    mount: mount, band: band, real: real, dest: dest, pass: pass,
    conflict: conflict, viewSpec: viewSpec, spread: spread, counts: counts, refreshMs: REFRESH_MS
  };
})(typeof window !== "undefined" ? window : globalThis);
