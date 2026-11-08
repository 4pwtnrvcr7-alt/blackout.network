/* Global signal map. Same Leaflet + Natural Earth drawing as Control panel v2.
   Dots: /api/state main (watchlist 0) and watchlist (watchlist 1) only, and only rows that
   already have coordinates. Red is rank 7-10 only. No tile servers. */
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
  function dest(c) {
    var id = String(c && c.cluster_id || "");
    if (/^[0-9a-f]{16}$/.test(id)) return { href: "/wire/" + id, ext: false };
    var links = (c && c.links) || [], i, u;
    for (i = 0; i < links.length; i++) {
      u = links[i] && (links[i].url || links[i].u);
      if (typeof u === "string" && /^https?:\/\//i.test(u)) return { href: u, ext: true };
    }
    return null;
  }
  function when(c) { return c.event_time || c.first_seen || c.updated || ""; }
  function pass(c, f, now) {
    if (!real(c)) return false;
    var r = band(c.rank).r;
    if (f.rank === "7" && r < 7) return false;
    if (f.rank === "4" && (r < 4 || r > 6)) return false;
    if (f.rank === "0" && r > 3) return false;
    if (f.topic && c.category !== f.topic) return false;
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
    }).setView([18, 12], 2);
    map.attributionControl.setPrefix("");
    map.attributionControl.addAttribution("Natural Earth");
    var world = null, markers = L.layerGroup().addTo(map), rows = [], armed = null, tip, hideT = 0, open = null;

    tip = document.createElement("div");
    tip.className = "bn-sig-tip";
    tip.hidden = true;
    tip.setAttribute("role", "tooltip");
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
      var b = band(c.rank), time = et(when(c));
      function label() { return (text(c.title) || "Story") + ". Rank " + b.r + " of 10." + (time ? " " + time + "." : ""); }
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
      var f = { rank: "", topic: "", hours: embed ? 168 : 168 };
      if (embed) return f;
      var rank = el.querySelector("#bn_sig_rank"), topic = el.querySelector("#bn_sig_topic"), win = el.querySelector("#bn_sig_win");
      f.rank = rank ? rank.value : "";
      f.topic = topic ? topic.value : "";
      f.hours = win && win.value ? +win.value : 168;
      return f;
    }
    function say(s) { if (note) note.textContent = s; }
    function draw() {
      markers.clearLayers();
      hide(); armed = null;
      var f = filters(), now = Date.now(), shown = [], i;
      for (i = 0; i < rows.length; i++) if (pass(rows[i], f, now)) shown.push(rows[i]);
      shown.forEach(function (c) {
        var b = band(c.rank);
        var marker = L.marker([+c.lat, +c.lon], {
          icon: L.divIcon({ className: "bn-sig-mk", html: '<div class="signal" style="color:' + b.color + '"></div>', iconSize: [12, 12], iconAnchor: [6, 6] }),
          keyboard: false
        });
        onMarker(c, marker);
        marker.addTo(markers);
      });
      var noun = shown.length === 1 ? "record" : "records";
      say(shown.length + " geocoded " + noun + " shown" + (rows.length > shown.length ? " of " + rows.length : "") + " · dots follow rank");
      setTimeout(function () { map.invalidateSize(); }, 60);
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
    }
    function writeUrl() {
      if (embed) return;
      var f = filters();
      var p = new URLSearchParams();
      if (f.topic) p.set("topic", f.topic);
      if (f.rank) p.set("rank", f.rank);
      if (String(f.hours) !== "168") p.set("window", String(f.hours));
      var s = p.toString();
      history.replaceState(null, "", s ? "?" + s : location.pathname);
    }
    map.on("click", function (e) {
      var t = e.originalEvent && e.originalEvent.target;
      if (t && t.closest && t.closest("a,button,.leaflet-control,.bn-sig-tip,.bn-sig-mk")) return;
      armed = null; hide();
      if (embed) location.href = "/map";
    });
    map.on("movestart", function () { if (!coarse) hide(); });
    ["#bn_sig_rank", "#bn_sig_topic", "#bn_sig_win"].forEach(function (id) {
      var n = el.querySelector(id);
      if (n) n.addEventListener("change", function () { writeUrl(); draw(); });
    });
    if (window.ResizeObserver) new ResizeObserver(function () { map.invalidateSize(); if (open) show(open, L.latLng(+open.lat, +open.lon)); }).observe(box);
    else window.addEventListener("resize", function () { map.invalidateSize(); });

    fetch(GEO).then(function (r) { return r.json(); }).then(function (geo) {
      world = L.geoJSON(geo, { style: { color: "#364158", weight: 0.6, fillColor: "#192538", fillOpacity: 0.7 }, interactive: false }).addTo(map);
      if (world.bringToBack) world.bringToBack();
      map.invalidateSize();
    }).catch(function () { say("World outline could not load. Dots still use real coordinates."); });

    readUrl();
    fetch("/api/state", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("state"); return r.json(); }).then(function (S) {
      var main = (S && S.main) || [], watch = (S && S.watchlist) || [], i;
      rows = [];
      for (i = 0; i < main.length; i++) rows.push(main[i]);
      for (i = 0; i < watch.length; i++) rows.push(watch[i]);
      rows = rows.filter(real);
      fillTopics();
      readUrl();
      draw();
    }).catch(function () { say("Stories could not load. The map is the bundled world outline."); });
  }

  global.BNSignal = { mount: mount, band: band, real: real, dest: dest, pass: pass };
})(typeof window !== "undefined" ? window : globalThis);
