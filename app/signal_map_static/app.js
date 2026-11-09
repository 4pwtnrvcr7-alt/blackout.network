/* Global signal map. Same Leaflet + Natural Earth drawing as Control panel v2.
   Dots: Wire and Watchlist only. Stored coordinates stay filled. Inferred places are hollow.
   Red is rank 7-10 only. No tile servers. */
(function (global) {
  "use strict";
  var GEO = "/api/signal/world.geojson";
  var LOW = "#55b7ff", MID = "#F5A524", HIGH = "#FF4D4F";

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
      /* the homepage preview stays up with its dots; never show a failure line over them */
      if (missing) missing.textContent = el.querySelector(".bn-sig-pre circle") ? "Top stories shown. Open the map for every dot." : "The map library could not load.";
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
    var viewName = "us", framing = 0, listEl = null, timer = 0, seedIds = {};
    frameUS();

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
    function onMarker(c, marker, delay) {
      var b = band(c.rank), time = et(when(c));
      function label() {
        var s = (text(c.title) || "Story") + ". Rank " + b.r + " of 10." + (time ? " " + time + "." : "");
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
    function paintViews() {
      el.querySelectorAll("[data-view]").forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-view") === viewName ? "true" : "false");
      });
    }
    function activeRows(list, f, now) {
      var out = [], i;
      for (i = 0; i < list.length; i++) if (pass(list[i], f, now)) out.push(list[i]);
      return out;
    }
    function paintCounts(shown) {
      var f = filters(), now = Date.now();
      var base = { rank: f.rank, topic: f.topic, hours: f.hours, conflict: false };
      var all = activeRows(rows, base, now), us = [], war = [], i, cats = {};
      for (i = 0; i < all.length; i++) {
        if (inUS(all[i])) us.push(all[i]);
        if (conflict(all[i])) war.push(all[i]);
      }
      el.querySelectorAll("[data-n]").forEach(function (n) {
        var k = n.getAttribute("data-n");
        n.textContent = String(k === "us" ? us.length : k === "conflicts" ? war.length : all.length);
      });
      var line = el.querySelector(".bn-sig-counts");
      var focus = viewName === "us" ? us : viewName === "conflicts" ? war : all;
      for (i = 0; i < focus.length; i++) {
        var name = focus[i].category || "other";
        cats[name] = (cats[name] || 0) + 1;
      }
      if (line) {
        var names = Object.keys(cats).sort(function (a, b) { return cats[b] - cats[a]; });
        line.textContent = names.map(function (k) { return k + " " + cats[k]; }).join(" · ");
      }
      return { us: us.length, world: all.length, conflicts: war.length };
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
        var d = dest(c), row = document.createElement("button");
        row.type = "button";
        row.className = "bn-sig-list-i";
        var t = document.createElement("b");
        t.textContent = text(c.title) || "Untitled";
        var s = document.createElement("span");
        s.textContent = (c.place ? text(c.place) + " · " : "") + "Rank " + band(c.rank).r + "/10 · " + (d ? d.label : "");
        row.appendChild(t); row.appendChild(s);
        row.onclick = function (ev) { ev.preventDefault(); ev.stopPropagation(); go(c); };
        ul.appendChild(row);
      });
      listEl.appendChild(ul);
      listEl.hidden = false;
    }
    function dotIcon(c, first) {
      var b = band(c.rank);
      if (seedIds[c.cluster_id]) first = false;          /* first batch (inline seed): shown at once, never re-animated */
      var delay = first ? (Math.random() * 15).toFixed(3) + "s" : "";
      var approx = c.exact === false || c.approximate || c.precision === "country";
      var icon = L.divIcon({ className: "bn-sig-mk" + (seedIds[c.cluster_id] ? "" : first ? " bn-sig-enter" : " bn-sig-fade"), html: '<div class="signal' + (approx ? " approx" : "") + '" style="color:' + b.color + '"></div>', iconSize: [12, 12], iconAnchor: [6, 6] });
      if (delay) icon.createIcon = function (old) {
        var node = L.DivIcon.prototype.createIcon.call(this, old);
        node.style.setProperty("--bn-d", delay);
        return node;
      };
      return icon;
    }
    function countIcon(n) {
      var size = Math.min(40, 24 + Math.round(Math.log(n) / Math.LN2) * 2);
      return L.divIcon({
        className: "bn-sig-cl",
        html: '<div class="bn-count" style="width:' + size + 'px;height:' + size + 'px">' + n + "</div>",
        iconSize: [size, size], iconAnchor: [size / 2, size / 2]
      });
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
      var f = filters(), now = Date.now(), shown = activeRows(rows, f, now), i;
      var zoom = map.getZoom() || 2;
      var plan = clusterPlan(shown, zoom);
      plan.forEach(function (g) {
        var members = g.idx.map(function (ix) { return shown[ix]; });
        if (g.n === 1) {
          var c = members[0];
          var marker = L.marker([+c.lat, +c.lon], { icon: dotIcon(c, first), keyboard: false });
          onMarker(c, marker, "");
          marker.addTo(markers);
          return;
        }
        if (g.spider) {
          var center = map.latLngToLayerPoint([+members[0].lat, +members[0].lon]);
          members.forEach(function (c, j) {
            var at = map.layerPointToLatLng(L.point(center.x + g.offsets[j].dx, center.y + g.offsets[j].dy));
            var mk = L.marker(at, { icon: dotIcon(c, first), keyboard: false });
            onMarker(c, mk, "");
            mk.addTo(markers);
          });
          return;
        }
        var lat = 0, lon = 0;
        members.forEach(function (c) { lat += +c.lat; lon += +c.lon; });
        var cm = L.marker([lat / g.n, lon / g.n], { icon: countIcon(g.n), keyboard: false });
        onCluster(members, cm);
        cm.addTo(markers);
      });
      var tally = paintCounts(shown);
      var noun = shown.length === 1 ? "record" : "records";
      var focus = viewName === "us" ? tally.us : viewName === "conflicts" ? tally.conflicts : shown.length;
      var label = viewName === "us" ? " in the United States" : viewName === "conflicts" ? " war/conflict" : "";
      say(focus + label + " · " + shown.length + " " + noun + " on this view · dots follow rank");
      setTimeout(function () { refit(); }, 60);
      if (shown.length) dropPreview();
    }
    function dropPreview() {
      var pre = box.querySelector(".bn-sig-pre");
      if (pre && pre.parentNode) requestAnimationFrame(function () { if (pre.parentNode) pre.parentNode.removeChild(pre); });
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
      if (t && t.closest && t.closest("a,button,.leaflet-control,.bn-sig-tip,.bn-sig-mk,.bn-sig-cl,.bn-sig-list,.bn-sig-views")) return;
      armed = null; hide(); closeList();
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
    function refit() {
      framing++;
      map.invalidateSize({ animate: false, pan: false });
      framing--;
      frameUS();
      if (open) show(open, L.latLng(+open.lat, +open.lon));
    }
    if (window.ResizeObserver) new ResizeObserver(function () { refit(); }).observe(box);
    else window.addEventListener("resize", function () { refit(); });

    fetch(GEO).then(function (r) { return r.json(); }).then(function (geo) {
      world = L.geoJSON(geo, { style: { color: "#364158", weight: 0.6, fillColor: "#192538", fillOpacity: 0.7 }, interactive: false }).addTo(map);
      if (world.bringToBack) world.bringToBack();
      map.invalidateSize();
    }).catch(function () { say("World outline could not load. Dots still use real coordinates."); });

    function pull(first) {
      fetch("/api/signal/points", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("points"); return r.json(); }).then(function (S) {
        rows = ((S && S.points) || []).filter(real);
        if (first) { fillTopics(); readUrl(); if (viewName !== "us") frame(viewName); }
        draw(first);
        if (first && note && note.getAttribute("data-done")) say(note.getAttribute("data-done"));
      }).catch(function () {
        if (!first) return;
        if (seedN) { say("Top stories shown. Updating\u2026"); setTimeout(function () { pull(true); }, 20000); }
        else say("Stories could not load. The map is the bundled world outline.");
      });
    }
    readUrl();
    if (viewName !== "us") frame(viewName);
    /* Homepage speed (Nov 8): the page carries the top dots inline (#bn_sig_seed). Draw them now, then load the rest. */
    var seedEl = el.querySelector("#bn_sig_seed"), seed = [], seedN = 0;
    if (seedEl) { try { seed = (JSON.parse(seedEl.textContent || "[]") || []).filter(real); } catch (e) { seed = []; } }
    if (seed.length) {
      seed.forEach(function (c) { if (c.cluster_id) seedIds[c.cluster_id] = 1; });
      rows = seed; seedN = seed.length; draw(false);
    }
    pull(true);
    timer = setInterval(function () { pull(false); }, 300000);
  }

  global.BNSignal = {
    mount: mount, band: band, real: real, dest: dest, pass: pass,
    conflict: conflict, inUS: inUS, clusterPlan: clusterPlan, FAN_MAX: FAN_MAX, SPIDER_PX: SPIDER_PX
  };
})(typeof window !== "undefined" ? window : globalThis);
