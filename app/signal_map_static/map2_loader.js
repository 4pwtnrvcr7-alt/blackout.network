/* BLACKOUT.NETWORK heat map loader, "Signal acquisition" (Nov 20 2026, Matt pt1675u).
   A night-side globe drawn as scan lines, a radar sweep that lights up the real Wire alerts as they are placed, and a HUD with the real stages:
   feed bytes received, exact pins, approximate rings, region rings, no-location items (in orbit) and basemap tiles. Every number on it comes
   from the actual /api/signal/heat response and the actual map engine. It fades out the moment the map is ready, never blocks the map controls
   (pointer-events: none) and turns slow or failed loads into a retry message instead of an endless spinner. Canvas 2D only, no libraries.
   It also starts the feed request before the map engine has downloaded, so the map is ready sooner than before. API for map2.js: window.BNML. */
(function () {
  "use strict";
  var d = document, w = window, root = d.getElementById("bnm_ld");
  var reduce = w.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var COL = { calm: [140, 146, 154], elev: [201, 205, 211], high: [255, 77, 79] };   /* site bands; red only for rank 7+ */
  var ICE = "207,228,255";                                                           /* sweep / scan accent: cool white only */
  var SIZE_KEY = "bnm_heat_bytes";
  function $(id) { return d.getElementById(id); }
  function band(r) { return r >= 7 ? "high" : r >= 4 ? "elev" : "calm"; }
  function fmtB(n) { return n >= 1048576 ? (n / 1048576).toFixed(n >= 10485760 ? 0 : 1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; }
  function num(n) { return (+n || 0).toLocaleString("en-US"); }

  /* ---------- feed: started now, before MapLibre (about 800 KB) has even downloaded ---------- */
  var feedP = null, attempt = 0, retryT = 0, retryNow = null, gotData = false;
  function msg(html, btn) {
    var m = $("bnl_msg"); if (!m) return;
    m.innerHTML = html || ""; m.hidden = !html; root && root.classList.toggle("bnl-warn", !!html);
    if (btn) { var b = m.querySelector("button"); if (b) b.onclick = btn; }
  }
  function once() {
    var t0 = performance.now(), got = 0, total = 0, ctl = w.AbortController ? new AbortController() : null, slowT, killT;
    try { total = +localStorage.getItem(SIZE_KEY) || 0; } catch (e) {}
    S.link = { got: 0, total: total, t0: t0 }; setStage("link", "on"); paintLink();
    slowT = setInterval(function () {
      var s = Math.round((performance.now() - t0) / 1000); if (s < 6) return;
      if (!got) msg("Slow link. Still waiting on the Wire feed · " + s + " s");
      else msg("Slow link. " + fmtB(got) + " received at " + fmtB(got / Math.max(1, s)) + "/s");
    }, 1000);
    if (ctl) killT = setTimeout(function () { ctl.abort(); }, 45000);
    function done() { clearInterval(slowT); clearTimeout(killT); }
    return fetch("/api/signal/heat", { cache: "no-store", signal: ctl ? ctl.signal : undefined }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      var cl = +r.headers.get("content-length") || 0, enc = r.headers.get("content-encoding");
      if (cl && !enc) { total = cl; S.link.total = cl; }
      if (!r.body || !r.body.getReader || !w.TextDecoder) return r.text();
      var rd = r.body.getReader(), dec = new TextDecoder(), parts = [];
      return (function pump() {
        return rd.read().then(function (x) {
          if (x.done) { parts.push(dec.decode()); return parts.join(""); }
          got += x.value.byteLength; S.link.got = got; parts.push(dec.decode(x.value, { stream: true })); paintLink(); return pump();
        });
      })();
    }).then(function (txt) {
      done(); var j = JSON.parse(txt);
      if (!j || !Array.isArray(j.rows)) throw new Error("bad payload");
      S.link.got = got || txt.length; S.link.total = S.link.got; paintLink(); setStage("link", "ok");
      try { localStorage.setItem(SIZE_KEY, String(S.link.got)); } catch (e) {}
      msg(""); return j;
    }, function (e) { done(); throw e; });
  }
  function feed() {
    if (feedP) return feedP;
    feedP = new Promise(function (resolve) {
      function go() {
        attempt++; clearInterval(retryT);
        once().then(resolve, function () {
          var wait = [4, 10, 20, 30][Math.min(attempt - 1, 3)], left = wait;
          setStage("link", "err"); setVal("link", "no response"); bar();
          var say = function () {
            msg("The Wire feed did not load. Retrying in " + left + " s" + (attempt >= 3 ? ' · <a href="/wire">Open The Wire</a>' : "") + ' <button type="button">Retry now</button>', function () { go(); });
          };
          say(); retryNow = go;
          retryT = setInterval(function () { left--; if (left <= 0) { clearInterval(retryT); msg("Retrying…"); go(); } else say(); }, 1000);
        });
      }
      go();
    });
    return feedP;
  }

  /* ---------- state ---------- */
  var S = { link: { got: 0, total: 0 }, n: { exact: 0, approx: 0, region: 0, global: 0 }, shown: { exact: 0, approx: 0, region: 0, global: 0 }, regs: 0, tiles: 0,
    phase: "link", pass: 0, mapReady: false, speed: 1, out: false };
  var PLACE_MS = 2000, ORDER = ["exact", "approx", "region", "global"], DUR = { exact: 1150, approx: 750, region: 520, global: 620 };
  var pts = [], orbit = [], flashes = [];
  function setStage(k, st) { var li = root && root.querySelector('[data-s="' + k + '"]'); if (li) li.className = st || ""; }
  function setVal(k, t) { var li = root && root.querySelector('[data-s="' + k + '"] em'); if (li && li.textContent !== t) li.textContent = t; }
  function paintLink() {
    var L = S.link; setVal("link", L.total && L.got < L.total ? fmtB(L.got) + " / " + fmtB(L.total) : L.got ? fmtB(L.got) : "connecting");
    bar();
  }
  function bar() {
    var L = S.link, f = L.total ? Math.min(0.97, L.got / L.total) : (L.got ? 0.5 : 0.04), p = 0.5 * (S.phase === "link" ? f : 1);
    ORDER.forEach(function (k) { var n = S.n[k]; if (S.phase !== "link") p += 0.1 * (n ? S.shown[k] / n : (ORDER.indexOf(k) < S.pass || S.phase === "base" || S.phase === "done" ? 1 : 0)); });
    p += S.mapReady ? 0.1 : Math.min(0.08, S.tiles / 400);
    var i = root && root.querySelector(".bnl-bar i"); if (i) i.style.transform = "scaleX(" + Math.min(1, p).toFixed(3) + ")";
  }
  function counters() {
    setVal("exact", S.phase === "link" ? "waiting" : num(S.shown.exact) + " pins");
    setVal("approx", S.phase === "link" ? "waiting" : num(S.shown.approx) + " rings");
    setVal("region", S.phase === "link" ? "waiting" : num(S.shown.region) + (S.regs && S.shown.region === S.n.region ? " in " + S.regs + " regions" : ""));
    setVal("global", S.phase === "link" ? "waiting" : num(S.shown.global) + " in orbit");
    setVal("base", S.mapReady ? "ready" : S.tiles ? num(S.tiles) + " tiles" : "loading");
    bar();
  }

  /* ---------- geometry ---------- */
  var cv = root && root.querySelector("canvas"), cx2 = cv && cv.getContext && cv.getContext("2d");
  var W = 0, H = 0, DPR = 1, CX = 0, CY = 0, R = 100, PS = 1, side = false, globeImg = null, spr = {};
  var lon0 = -38 * Math.PI / 180, LAT0 = 17 * Math.PI / 180, sinT = Math.sin(LAT0), cosT = Math.cos(LAT0), sweep = -Math.PI / 2, t0 = 0, last = 0;
  function sprite(rgb, kind) {
    var s = 48, c = d.createElement("canvas"); c.width = c.height = s; var g = c.getContext("2d"), m = s / 2;
    if (kind === "glow") { var gr = g.createRadialGradient(m, m, 0, m, m, m); gr.addColorStop(0, "rgba(" + rgb + ",.95)"); gr.addColorStop(0.18, "rgba(" + rgb + ",.55)"); gr.addColorStop(1, "rgba(" + rgb + ",0)"); g.fillStyle = gr; g.fillRect(0, 0, s, s); }
    else { g.strokeStyle = "rgba(" + rgb + ",1)"; g.lineWidth = kind === "reg" ? 2.4 : 3; g.beginPath(); g.arc(m, m, m - 4, 0, 6.2832); g.stroke(); }
    return c;
  }
  function layout() {
    if (!cv) return;
    W = w.innerWidth; H = w.innerHeight; DPR = Math.min(2, w.devicePixelRatio || 1);
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); cv.style.width = W + "px"; cv.style.height = H + "px";
    side = W >= 1000 && H >= 560;
    if (side) { R = Math.min(H * 0.31, W * 0.2); CX = W * 0.4; CY = H * 0.5; }
    else { R = Math.min(W * 0.36, H * 0.23); CX = W / 2; CY = Math.max(R * 1.5 + 40, H * 0.37); }
    PS = Math.max(0.9, Math.min(1.5, R / 170));
    var hud = root.querySelector(".bnl-hud");
    if (side) { hud.style.left = Math.round(CX + R * 1.38 + 22) + "px"; hud.style.top = "50%"; hud.style.transform = "translateY(-50%)"; hud.style.width = Math.min(300, W - (CX + R * 1.38 + 22) - 28) + "px"; }
    else { hud.style.left = "50%"; hud.style.top = Math.round(CY + R * 1.32 + 16) + "px"; hud.style.transform = "translateX(-50%)"; hud.style.width = Math.min(320, W - 40) + "px"; }
    /* sphere + atmosphere, drawn once per size */
    var g = d.createElement("canvas"), pad = R * 0.35, sz = Math.ceil((R + pad) * 2 * DPR); g.width = g.height = sz; var x = g.getContext("2d"), m = sz / 2, r = R * DPR;
    var atm = x.createRadialGradient(m, m, r * 0.96, m, m, r * 1.3); atm.addColorStop(0, "rgba(" + ICE + ",.16)"); atm.addColorStop(0.25, "rgba(" + ICE + ",.05)"); atm.addColorStop(1, "rgba(" + ICE + ",0)");
    x.fillStyle = atm; x.fillRect(0, 0, sz, sz);
    var sp = x.createRadialGradient(m - r * 0.42, m - r * 0.5, r * 0.05, m, m, r); sp.addColorStop(0, "rgba(28,32,42,.98)"); sp.addColorStop(0.55, "rgba(12,14,20,.98)"); sp.addColorStop(1, "rgba(6,7,11,.98)");
    x.fillStyle = sp; x.beginPath(); x.arc(m, m, r, 0, 6.2832); x.fill();
    x.strokeStyle = "rgba(" + ICE + ",.22)"; x.lineWidth = 1 * DPR; x.beginPath(); x.arc(m, m, r, 0, 6.2832); x.stroke();
    globeImg = { c: g, s: sz / DPR };
    ["calm", "elev", "high"].forEach(function (b) { var rgb = COL[b].join(","); spr[b] = { glow: sprite(rgb, "glow"), ring: sprite(rgb, "ring"), reg: sprite(rgb, "reg") }; });
    spr.ice = { glow: sprite(ICE, "glow") };
    if (reduce) draw(performance.now());
  }
  /* orthographic projection: returns screen x, y and depth z (z > 0 faces us) */
  function proj(cl, sl, lon, o) {
    var dl = lon - lon0, x = cl * Math.sin(dl), y0 = cl * Math.cos(dl), z = y0 * cosT + sl * sinT, y = sl * cosT - y0 * sinT;
    o.x = CX + R * x; o.y = CY - R * y; o.z = z; return o;
  }
  var P = { x: 0, y: 0, z: 0 };
  function grat(c, k) {
    c.lineWidth = 1; c.strokeStyle = "rgba(240,240,250," + (0.075 * k).toFixed(3) + ")"; c.beginPath();
    var i, j, la, lo, pen;
    for (i = -180; i < 180; i += 20) { lo = i * Math.PI / 180; pen = false;
      for (j = -90; j <= 90; j += 6) { la = j * Math.PI / 180; proj(Math.cos(la), Math.sin(la), lo, P); if (P.z > 0) { pen ? c.lineTo(P.x, P.y) : c.moveTo(P.x, P.y); pen = true; } else pen = false; } }
    for (j = -60; j <= 60; j += 20) { la = j * Math.PI / 180; var cl = Math.cos(la), sl = Math.sin(la); pen = false;
      for (i = -180; i <= 180; i += 5) { proj(cl, sl, i * Math.PI / 180, P); if (P.z > 0) { pen ? c.lineTo(P.x, P.y) : c.moveTo(P.x, P.y); pen = true; } else pen = false; } }
    c.stroke();
    /* equator a touch brighter */
    c.strokeStyle = "rgba(" + ICE + "," + (0.14 * k).toFixed(3) + ")"; c.beginPath(); pen = false;
    for (i = -180; i <= 180; i += 4) { proj(1, 0, i * Math.PI / 180, P); if (P.z > 0) { pen ? c.lineTo(P.x, P.y) : c.moveTo(P.x, P.y); pen = true; } else pen = false; }
    c.stroke();
  }
  /* no-location items orbit on a tilted ring around the globe */
  var OT = -0.24, OA = 1.3, OB = 0.3;
  function orbXY(a, o) { var ex = Math.cos(a) * R * OA, ey = Math.sin(a) * R * OB; o.x = CX + ex * Math.cos(OT) - ey * Math.sin(OT); o.y = CY + ex * Math.sin(OT) + ey * Math.cos(OT); o.z = Math.sin(a); return o; }
  function orbitRing(c, front, k) {
    c.strokeStyle = "rgba(240,240,250," + (0.1 * k).toFixed(3) + ")"; c.lineWidth = 1; c.setLineDash([2, 5]); c.beginPath();
    var a, pen = false; for (a = 0; a <= 6.30; a += 0.06) { orbXY(a, P); if ((P.z > 0) === front) { pen ? c.lineTo(P.x, P.y) : c.moveTo(P.x, P.y); pen = true; } else pen = false; }
    c.stroke(); c.setLineDash([]);
  }
  function drawOrbit(c, now, front) {
    for (var i = 0; i < orbit.length; i++) { var o = orbit[i]; if (!o.at) continue;
      var age = now - o.at, e = Math.min(1, age / 700), ee = 1 - Math.pow(1 - e, 3), a = o.a + (reduce ? 0 : now * 0.00012);
      orbXY(a, P); if ((P.z > 0) !== front) continue;
      var x = CX + (P.x - CX) * ee, y = CY + (P.y - CY) * ee, s = o.b === "high" ? 2.6 : 2;
      c.globalAlpha = front ? 0.95 : 0.45; c.fillStyle = o.fill; c.fillRect(x - s / 2, y - s / 2, s, s);
      if (age < 700 && !reduce) { c.globalAlpha = (1 - e) * 0.9; var gs = 18; c.drawImage(spr[o.b].glow, x - gs / 2, y - gs / 2, gs, gs); }
    }
    c.globalAlpha = 1;
  }

  /* ---------- frame ---------- */
  var brgT = 0;
  function draw(now) {
    if (!cx2 || !W) return;
    var c = cx2, el = now - t0; c.setTransform(DPR, 0, 0, DPR, 0, 0); c.clearRect(0, 0, W, H);
    var intro = reduce ? 1 : Math.min(1, el / 950);   /* graticule draws in as a falling scan line */
    orbitRing(c, false, intro); drawOrbit(c, now, false);
    c.drawImage(globeImg.c, CX - globeImg.s / 2, CY - globeImg.s / 2, globeImg.s, globeImg.s);
    c.save(); c.beginPath(); c.arc(CX, CY, R, 0, 6.2832); c.clip();
    if (intro < 1) { var sy = CY - R + 2 * R * intro; c.save(); c.beginPath(); c.rect(CX - R, CY - R, 2 * R, sy - (CY - R)); c.clip(); grat(c, 1); c.restore();
      var lg = c.createLinearGradient(0, sy - 26, 0, sy + 2); lg.addColorStop(0, "rgba(" + ICE + ",0)"); lg.addColorStop(1, "rgba(" + ICE + ",.32)"); c.fillStyle = lg; c.fillRect(CX - R, sy - 26, 2 * R, 28);
      c.fillStyle = "rgba(" + ICE + ",.8)"; c.fillRect(CX - R, sy, 2 * R, 1); }
    else grat(c, 1);
    /* radar sweep: hand + fading wedge */
    if (!reduce && intro >= 1 && !S.out) {
      var N = 14, span = 0.62;
      for (var k = 0; k < N; k++) { var a1 = sweep - span * (k + 1) / N, a2 = sweep - span * k / N;
        c.fillStyle = "rgba(" + ICE + "," + (0.11 * (1 - k / N) * (1 - k / N)).toFixed(3) + ")"; c.beginPath(); c.moveTo(CX, CY); c.arc(CX, CY, R, a1, a2); c.closePath(); c.fill(); }
      var hg = c.createLinearGradient(CX, CY, CX + Math.cos(sweep) * R, CY + Math.sin(sweep) * R); hg.addColorStop(0, "rgba(" + ICE + ",.05)"); hg.addColorStop(1, "rgba(" + ICE + ",.75)");
      c.strokeStyle = hg; c.lineWidth = 1.2; c.beginPath(); c.moveTo(CX, CY); c.lineTo(CX + Math.cos(sweep) * R, CY + Math.sin(sweep) * R); c.stroke();
    }
    /* placed alerts: exact = solid dots, approximate = hollow rings, region = larger rings (same language as the map) */
    for (var i = 0; i < pts.length; i++) { var p = pts[i]; if (!p.at) continue; proj(p.cl, p.sl, p.lo, P); if (P.z <= 0.02) continue;
      var fade = Math.min(1, P.z * 3), age = now - p.at;
      if (p.k === "exact") { var s = (p.b === "high" ? 2.6 : 1.8) * PS; c.globalAlpha = fade * (p.b === "calm" ? 0.8 : 0.95); c.fillStyle = p.fill; c.fillRect(P.x - s / 2, P.y - s / 2, s, s); }
      else { var rs = (p.k === "region" ? 13 + Math.min(10, Math.sqrt(p.n) * 2.2) : 5 + p.rank * 0.22) * PS; c.globalAlpha = fade * (p.k === "region" ? 0.6 : 0.55); c.drawImage(spr[p.b][p.k === "region" ? "reg" : "ring"], P.x - rs / 2, P.y - rs / 2, rs, rs); }
      if (age < 650 && !reduce) { var e = age / 650, gs = (p.k === "region" ? 34 : p.b === "high" ? 20 : 11) * PS * (0.7 + e * 0.8); c.globalAlpha = fade * (1 - e) * (1 - e) * (p.b === "high" ? 1 : 0.55); c.drawImage(spr[p.b].glow, P.x - gs / 2, P.y - gs / 2, gs, gs); }
    }
    c.globalAlpha = 1; c.restore();
    orbitRing(c, true, intro); drawOrbit(c, now, true);
    if (now - brgT > 100) { brgT = now; var b = $("bnl_brg"); if (b) { var deg = Math.round(((sweep + Math.PI / 2) * 180 / Math.PI % 360 + 360) % 360); b.textContent = "BRG " + ("00" + deg).slice(-3) + "°"; } }
  }
  function screenAng(p) { proj(p.cl, p.sl, p.lo, P); return Math.atan2(P.y - CY, P.x - CX); }
  var passStart = 0, passT = 0, raf = 0;
  function tick(now) {
    raf = 0; if (S.gone) return;
    var rdt = last ? Math.min(250, now - last) : 16, dt = Math.min(64, rdt); last = now;   /* placement runs on wall time even if frames drop */
    lon0 += dt * 0.0001;                       /* about 6 degrees a second */
    var spin = S.phase === "link" ? 0.0022 : 0;  /* idle sweep while the feed downloads */
    if (S.phase !== "link" && S.phase !== "base" && S.phase !== "done") {
      var k = ORDER[S.pass], D = DUR[k], step = rdt * S.speed; passT += step;
      var f = Math.min(1, passT / D);
      if (k === "global") { var m = Math.floor(f * S.n.global); for (var q = S.shown.global; q < m; q++) orbit[q].at = now; S.shown.global = Math.max(S.shown.global, m); }
      else {
        sweep = passStart + f * 6.2832;
        var sw = f * 6.2832;
        for (var i = 0; i < pts.length; i++) { var p = pts[i]; if (p.at || p.k !== k) continue;
          var rel = ((screenAng(p) - passStart) % 6.2832 + 6.2832) % 6.2832; if (rel <= sw || f >= 1) { p.at = now; S.shown[k] += p.n; } }
      }
      if (f >= 1) { S.shown[k] = S.n[k]; if (k === "global") for (var z = 0; z < orbit.length; z++) orbit[z].at = orbit[z].at || now;
        setStage(k, "ok"); S.pass++; passT = 0; passStart = sweep;
        if (S.pass >= ORDER.length) { S.phase = "base"; setStage("base", S.mapReady ? "ok" : "on"); } else setStage(ORDER[S.pass], "on"); }
      counters();
    } else sweep += dt * (S.phase === "link" ? spin : 0.0016);
    if (S.phase === "base" && S.mapReady) finish();
    var c0 = performance.now(); draw(now); var cst = w.__bnlCost || (w.__bnlCost = []); cst.push(performance.now() - c0); if (cst.length > 600) cst.shift();
    if (!S.gone) raf = requestAnimationFrame(tick);
  }
  function finish() {
    if (S.out) return; S.out = true; S.phase = "done"; setStage("base", "ok"); counters();
    d.body.classList.add("bnl-done");
    root.classList.add("bnl-out");
    setTimeout(function () { S.gone = true; if (raf) cancelAnimationFrame(raf); root.hidden = true; if (cv) { cv.width = cv.height = 0; } }, reduce ? 0 : 750);
  }

  /* ---------- API used by map2.js ---------- */
  function data(rows) {
    if (gotData || !root) return; gotData = true;
    var by = {};
    rows.forEach(function (r) {
      var k = r.tier === "global" ? "global" : r.tier === "region" ? "region" : r.tier === "approx" ? "approx" : "exact", b = band(r.rank), fill = "rgb(" + COL[b].join(",") + ")";
      S.n[k]++;
      if (k === "global") { orbit.push({ a: Math.random() * 6.2832, b: b, fill: fill, at: 0 }); return; }
      if (k === "region") { var key = r.rid || r.lat + "," + r.lon; if (by[key]) { by[key].n++; if (r.rank > by[key].rank) { by[key].rank = r.rank; by[key].b = b; } return; } }
      var la = r.lat * Math.PI / 180, o = { k: k, cl: Math.cos(la), sl: Math.sin(la), lo: r.lon * Math.PI / 180, rank: r.rank, b: b, fill: fill, at: 0, n: 1 };
      if (k === "region") by[r.rid || r.lat + "," + r.lon] = o;
      pts.push(o);
    });
    S.regs = Object.keys(by).length;   /* region items are counted one by one, drawn as one ring per region centre */
    S.phase = "place"; S.pass = 0; passT = 0; passStart = sweep;
    while (S.pass < ORDER.length && !S.n[ORDER[S.pass]]) { setStage(ORDER[S.pass], "ok"); S.pass++; }
    if (S.pass < ORDER.length) setStage(ORDER[S.pass], "on"); else S.phase = "base";
    if (reduce) {   /* no motion: everything placed at once */
      pts.forEach(function (p) { p.at = 1; }); orbit.forEach(function (o) { o.at = 1; });
      ORDER.forEach(function (k) { S.shown[k] = S.n[k]; setStage(k, "ok"); }); S.phase = "base"; setStage("base", S.mapReady ? "ok" : "on");
    }
    counters(); if (reduce) { draw(performance.now()); if (S.mapReady) finish(); }
  }
  function mapReady() {
    if (S.mapReady || !root) return; S.mapReady = true;
    /* compress whatever placement is left into PLACE_MS, so the loader never holds a ready map back for long */
    var left = 0; for (var i = S.pass; i < ORDER.length; i++) left += DUR[ORDER[i]] - (i === S.pass ? passT : 0);
    S.speed = Math.max(1, left / PLACE_MS);
    setStage("base", "ok"); counters();
    if (S.phase === "base" || (reduce && gotData)) finish();
  }
  var seenT = {};
  function tile(k) { if (k != null) { if (seenT[k]) return; seenT[k] = 1; } S.tiles++; if (!(S.tiles % 3)) counters(); }   /* unique basemap tiles */
  function engineFail() { msg('The map engine could not start in this browser. <a href="/wire">The Wire</a> lists the same alerts.'); setStage("base", "err"); setVal("base", "unavailable"); }

  w.BNML = { feed: feed, data: data, mapReady: mapReady, tile: tile, engineFail: engineFail };
  if (!root) return;
  feed();
  layout(); w.addEventListener("resize", layout);
  t0 = performance.now(); counters();
  if (!reduce) raf = requestAnimationFrame(tick);
  else { /* static frame; redraw on data */ var _t = function () { draw(performance.now()); }; _t(); }
})();
