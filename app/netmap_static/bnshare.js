/* Post on X for every shareable item (Grid, Sky, weather, provider pages).
   Manual only: the button is a plain link to x.com/intent/post. Text is crafted per item by the caller,
   hashtags come from the server generator (x_share.py via /api/share/tags), and the link points at
   /share/<kind>/<id>, whose page carries the per-item og:image + twitter:card. Nothing here posts. */
(function (w) {
  "use strict";
  if (w.BNShare) return;
  var d = document, SITE = "https://blackout.network", TAGS = {}, KIND = {
    planet: ["#Space", "#Astronomy"], moon: ["#Moon", "#Space"], sun: ["#Sun", "#Space"], craft: ["#Spacecraft", "#Space"], roadster: ["#Starman", "#SpaceX"],
    site: ["#Space", "#Exploration"], sat: ["#Satellites", "#Orbit"], launch: ["#Launch", "#Spaceflight"], cloud: ["#Cloud", "#Outage"],
    network: ["#Outage", "#Internet"], outage: ["#Outage", "#Internet"], weather: ["#Weather", "#Radar"], solar: ["#SpaceWeather", "#Sun"],
    page: ["#Infrastructure", "#Grid"], water: ["#Water", "#DrinkingWater"], dc: ["#DataCenter", "#Cloud"], cable: ["#UnderseaCables", "#Internet"], power: ["#PowerOutage", "#Grid"], grid: ["#PowerGrid", "#Energy"]
  };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function clean(s, n) { return String(s == null ? "" : s).replace(/[\u0000-\u001f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, n || 120); }
  function slug(s) { return String(s || "x").replace(/[^A-Za-z0-9_.:-]/g, "").slice(0, 60) || "x"; }   /* same sanitiser the server uses, case kept so server-side lookups match */
  function shareUrl(s) {
    var q = [], add = function (k, v) { if (v) q.push(k + "=" + encodeURIComponent(v)); };
    add("n", clean(s.n, 90)); add("d", clean(s.d, 140)); add("l", clean(s.l, 80)); add("p", s.p ? clean(s.p, 80) : "");
    return SITE + "/share/" + s.k + "/" + slug(s.i) + (q.length ? "?" + q.join("&") : "");
  }
  function href(s, tags) {
    var url = shareUrl(s), text = clean(s.t, 400);
    tags = (tags && tags.length ? tags : KIND[s.k] || KIND.page).slice(0, 5);
    function len(t) { return t.length + 1 + 23; }
    var full = (text + " " + tags.join(" ")).trim();
    while (len(full) > 280 && tags.length > 3) { tags = tags.slice(0, -1); full = (text + " " + tags.join(" ")).trim(); }
    if (len(full) > 280) { var cut = Math.max(20, 280 - 24 - tags.join(" ").length - 2); text = text.slice(0, cut).replace(/\s+\S*$/, "").replace(/[,;:\-\u2013 ]+$/, "") + "\u2026"; full = (text + " " + tags.join(" ")).trim(); }
    return "https://x.com/intent/post?text=" + encodeURIComponent(full) + "&url=" + encodeURIComponent(url);
  }
  var css = d.createElement("style");
  css.textContent = ".bn-x{display:inline-block;box-sizing:border-box;margin:4px 8px 2px 0;padding:2px 10px;font:600 11px/1.6 Inter,system-ui,sans-serif;letter-spacing:.04em;color:#fff!important;text-decoration:none!important;background:transparent;border:1px solid rgba(255,255,255,.4);border-radius:6px;pointer-events:auto!important;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}.bn-x:hover,.bn-x:focus-visible{background:#fff;color:#05060a!important;border-color:#fff}.bn-xs{pointer-events:none}.bn-xs .bn-x{pointer-events:auto!important}";
  (d.head || d.documentElement).appendChild(css);
  function upgrade(a, s) {
    var key = [s.k, s.n, s.l, s.d].join("|");
    var go = function (tg) { if (a.isConnected !== false) a.href = href(s, tg); };
    if (TAGS[key]) return TAGS[key].then ? TAGS[key].then(go) : go(TAGS[key]);
    var p = fetch("/api/share/tags?k=" + encodeURIComponent(s.k) + "&n=" + encodeURIComponent(clean(s.n, 90)) + "&l=" + encodeURIComponent(clean(s.l, 80)) + "&d=" + encodeURIComponent(clean(s.d, 140)) + "&t=" + encodeURIComponent(clean(s.t, 300)), { credentials: "same-origin" })
      .then(function (r) { return r.json(); }).then(function (j) { TAGS[key] = (j && j.tags) || null; return TAGS[key]; }, function () { return null; });
    TAGS[key] = p; p.then(function (tg) { TAGS[key] = tg || null; go(tg); });
  }
  var PENDING = [];
  function flush() {
    PENDING = PENDING.filter(function (it) {
      var a = d.querySelector('a.bn-x[data-bnid="' + it.id + '"]');
      if (!a) return Date.now() - it.t0 < 3000;
      upgrade(a, it.s); return false;
    });
  }
  var seq = 0;
  function html(s, label) {
    s = { k: s.k, i: slug(s.i), n: clean(s.n, 90), t: clean(s.t, 400), d: clean(s.d, 140), l: clean(s.l, 80), p: s.p || "" };
    var id = "bx" + (++seq);
    PENDING.push({ id: id, s: s, t0: Date.now() }); setTimeout(flush, 0); setTimeout(flush, 120);
    return '<a class="bn-x" data-bnid="' + id + '" href="' + esc(href(s)) + '" target="_blank" rel="noopener">' + esc(label || "Post on X") + "</a>";
  }
  function attach(el, s, label) {
    if (!el) return null;
    var old = el.querySelector(".bn-xs"); if (old) old.remove();
    var wrap = d.createElement("div"); wrap.className = "bn-xs"; wrap.innerHTML = html(s, label);
    el.appendChild(wrap); return wrap;
  }
  function firstSentence(t, n) { t = clean(t, 400); var m = t.match(/^(.+?[.!?])(\s|$)/); t = m ? m[1] : t; return t.length > n ? t.slice(0, n - 1).replace(/\s+\S*$/, "") + "\u2026" : t; }
  function skyHtml(o, A) {
    try {
      var c = o.d, E = A.OBJ && A.OBJ.earth && A.OBJ.earth.d, nm = o.id === "roadster" ? "Tesla Roadster (Starman)" : o.name, t, k, dd = "";
      if (o.kind === "sun") { k = "sun"; t = "The Sun is " + (E ? A.fmtAU(Math.hypot.apply(null, E.pos)) : "about 93 million mi") + " from Earth right now. Fly through the solar system in 3D with live NASA/JPL positions:"; }
      else if (o.id === "moon") { k = "moon"; t = "The Moon is about " + (A.imperial && A.imperial() ? "239,000 mi" : "384,400 km") + " from Earth. Explore every landing site on it in 3D:"; }
      else if (o.kind === "planet") {
        k = "planet";
        if (o.id === "earth") t = "Earth right now: " + (c ? A.fmtAU(Math.hypot.apply(null, c.pos)) : "") + " from the Sun, racing around it at " + (c ? A.fmtV(c.v_km_s) : "") + ". See it live in 3D:";
        else t = nm + " right now: " + (c && E ? A.fmtAU(Math.hypot(c.pos[0] - E.pos[0], c.pos[1] - E.pos[1], c.pos[2] - E.pos[2])) : "") + " from Earth, orbiting the Sun at " + (c ? A.fmtV(c.v_km_s) : "") + ". Explore it live in 3D:";
      } else {
        k = o.id === "roadster" ? "roadster" : "craft";
        t = (o.id === "roadster" ? "Starman's Tesla Roadster" : nm) + " is " + (c ? A.fmtAU(c.earth_au) : "") + " from Earth right now, moving " + (c ? A.fmtV(c.v_km_s) : "") + " relative to the Sun. Track it live:";
        dd = c ? clean((c.operator || "") + " \u00b7 launched " + (c.launch || ""), 140) : "";
      }
      return html({ k: k, i: o.id, n: nm, t: t, d: dd });
    } catch (e) { return ""; }
  }
  function siteHtml(o, rec, kind) {
    try {
      var nm = rec.name + (rec.place ? " (" + rec.place + ")" : "");
      return html({ k: "site", i: rec.id, n: nm, t: nm + ": " + firstSentence(rec.text || "", 150) + " Explore it in 3D:", d: firstSentence(rec.text || "", 140) });
    } catch (e) { return ""; }
  }
  w.BNShare = { html: html, attach: attach, href: href, shareUrl: shareUrl, clean: clean, skyHtml: skyHtml, siteHtml: siteHtml, first: firstSentence };

  /* ---------- deep links: /grid?sky=<id>[&site=<id>]#sky , /grid?launch=<id>#sky ---------- */
  function boot() {
    var q; try { q = new URLSearchParams(location.search); } catch (e) { return; }
    var sky = q.get("sky"), site = q.get("site"), launch = q.get("launch");
    if (!sky && !launch) return;
    try { w.scrollTo(0, 0); } catch (e) {}
    var n = 0;
    if (sky) {
      var openSky = function () {
        var u = w.BN_SOLAR3D; if (!u) return;
        var go = function () {
          if (!w.BNSolar) return;
          w.BNSolar.open(site ? sky : sky);
          if (site) { var t = 0, iv = setInterval(function () { if (w.BNPlanets && w.BNPlanets.openSite && w.BNPlanets._state && w.BNPlanets._state().pins.indexOf(site) >= 0) { clearInterval(iv); w.BNPlanets.openSite(sky, site); } else if (++t > 60) clearInterval(iv); }, 500); }
        };
        if (w.BNSolar) return go();
        var i = 0; (function nx() { if (i >= u.length) return go(); var sc = d.createElement("script"); sc.src = u[i++]; sc.onload = nx; sc.onerror = function () {}; d.head.appendChild(sc); })();
      };
      var iv0 = setInterval(function () { if (w.BN_SOLAR3D && d.getElementById("nx_sf") || ++n > 80) { clearInterval(iv0); openSky(); } }, 250);
    }
    if (launch) {
      var t2 = 0, st = 0, iv1 = setInterval(function () {
        t2++; var chip = d.getElementById("nx_lc_chip"), LCx = w.__nxLaunches;
        if (t2 > 120) return clearInterval(iv1);
        if (!chip || !LCx) return;
        var list = (LCx.state.data && LCx.state.data.launches) || [];
        if (!list.length) { if (!st) { st = 1; chip.click(); } return; }
        var i = -1; list.forEach(function (L, j) { if (L.id === launch) i = j; });
        clearInterval(iv1); if (i >= 0) LCx.select(i);
      }, 400);
    }
  }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", boot); else boot();
})(window);
