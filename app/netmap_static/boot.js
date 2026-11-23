/* BLACKOUT.NETWORK boot loader (Matt, Nov 23 2026, pt1759u): a retro-futurist machine powering on.
   Parts light up in sequence (power, fans, CPU, memory, network bus, GPU, satellite uplink), neon traces carry
   pulses between connection points, and a fan spins up. Every stage is driven by the page's real preload progress.
   No yellow, no red. Text lives in its own opaque panel (CSS), never on top of the board.
   window.BNBoot({ canvas, progress: fn -> 0..1, pct, bar, status }) -> { done(), stop() } */
(function () {
  "use strict";
  var C = { pwr: "#36FFB0", fan: "#22E5FF", cpu: "#9D7BFF", mem: "#FF4FD8", net: "#4D8DFF", gpu: "#2EF2FF", sat: "#5CFF8F" };
  var STAGES = [   /* at = progress threshold */
    { k: "pwr", at: 0.0, t: "Power on" }, { k: "fan", at: 0.06, t: "Spinning up fans" }, { k: "cpu", at: 0.16, t: "CPU online · base map" },
    { k: "mem", at: 0.3, t: "Memory · provider status" }, { k: "net", at: 0.48, t: "Network bus · outage signals" },
    { k: "gpu", at: 0.66, t: "GPU · data centers, power" }, { k: "sat", at: 0.84, t: "Satellite uplink" }, { k: "rdy", at: 0.995, t: "Ready" }];
  function rgba(hex, a) { var n = parseInt(hex.slice(1), 16); return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")"; }
  /* board layouts in logical units: wide (desktop) and tall (phones) */
  function layout(tall) {
    if (!tall) return { W: 1000, H: 600, parts: {
      fan: { x: 70, y: 60, w: 220, h: 220, kind: "fan" }, sat: { x: 800, y: 50, w: 150, h: 120, kind: "sat" },
      cpu: { x: 420, y: 180, w: 160, h: 160, kind: "cpu" }, mem: { x: 640, y: 170, w: 120, h: 180, kind: "mem" },
      net: { x: 830, y: 230, w: 110, h: 170, kind: "net" }, gpu: { x: 260, y: 420, w: 520, h: 110, kind: "gpu" }, pwr: { x: 60, y: 400, w: 150, h: 140, kind: "pwr" } },
      links: [["pwr", "gpu", "pwr", 3], ["pwr", "fan", "pwr", 2]] };
    return { W: 600, H: 820, parts: {
      fan: { x: 40, y: 40, w: 230, h: 230, kind: "fan" }, sat: { x: 380, y: 50, w: 170, h: 130, kind: "sat" },
      cpu: { x: 220, y: 320, w: 160, h: 160, kind: "cpu" }, mem: { x: 430, y: 300, w: 120, h: 200, kind: "mem" },
      net: { x: 40, y: 310, w: 120, h: 180, kind: "net" }, gpu: { x: 200, y: 570, w: 360, h: 110, kind: "gpu" }, pwr: { x: 30, y: 590, w: 130, h: 190, kind: "pwr" } },
      links: [["pwr", "gpu", "pwr", 3], ["pwr", "net", "pwr", 2]] };
  }
  var LINKS = [ /* from, to, stage that lights it, lanes (plus each layout's own power rails) */
    ["gpu", "cpu", "cpu", 4], ["cpu", "fan", "fan", 2], ["cpu", "mem", "mem", 4], ["cpu", "net", "net", 3], ["net", "sat", "sat", 2], ["mem", "sat", "sat", 2]];
  var TAG = { pwr: "PSU 01", fan: "FAN 01", cpu: "CPU", mem: "MEM 4x", net: "NET BUS", gpu: "GPU", sat: "SAT UPLINK" };
  function ctr(p) { return { x: p.x + p.w / 2, y: p.y + p.h / 2 }; }
  function edge(p, q) {   /* point on p's border facing q */
    var a = ctr(p), b = ctr(q), dx = b.x - a.x, dy = b.y - a.y;
    if (Math.abs(dx) * p.h > Math.abs(dy) * p.w) return { x: a.x + Math.sign(dx) * p.w / 2, y: a.y, hz: true };
    return { x: a.x, y: a.y + Math.sign(dy) * p.h / 2, hz: false };
  }
  function route(a, b, hz, hz2) {   /* orthogonal trace with 45-degree chamfers */
    var dx = b.x - a.x, dy = b.y - a.y, sx = Math.sign(dx) || 1, sy = Math.sign(dy) || 1, k = Math.min(Math.abs(dx), Math.abs(dy)) * 0.6;
    if (hz && hz2) { var mx = (a.x + b.x) / 2, d = Math.min(Math.abs(dy), Math.abs(dx) * 0.8) / 2; return [a, { x: mx - sx * d, y: a.y }, { x: mx + sx * d, y: b.y }, b]; }
    if (!hz && !hz2) { var my = (a.y + b.y) / 2, e = Math.min(Math.abs(dx), Math.abs(dy) * 0.8) / 2; return [a, { x: a.x, y: my - sy * e }, { x: b.x, y: my + sy * e }, b]; }
    if (hz) return [a, { x: b.x - sx * k, y: a.y }, { x: b.x, y: a.y + sy * k }, b];
    return [a, { x: a.x, y: b.y - sy * k }, { x: a.x + sx * k, y: b.y }, b];
  }
  function lens(pts) { var L = [0]; for (var i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y)); return L; }
  function at(pts, L, d) {
    for (var i = 1; i < pts.length; i++) if (d <= L[i] || i === pts.length - 1) { var f = (d - L[i - 1]) / Math.max(1e-6, L[i] - L[i - 1]); f = Math.max(0, Math.min(1, f));
      return { x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * f, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * f, i: i }; }
    return pts[pts.length - 1];
  }
  function sprite(hex) {   /* pre-rendered glow: drawImage is far cheaper than shadowBlur on phones */
    var s = document.createElement("canvas"); s.width = s.height = 64; var g = s.getContext("2d"), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.18, rgba(hex, 0.95)); r.addColorStop(0.5, rgba(hex, 0.25)); r.addColorStop(1, rgba(hex, 0));
    g.fillStyle = r; g.fillRect(0, 0, 64, 64); return s;
  }

  window.BNBoot = function (o) {
    var cv = o.canvas, cx = cv.getContext("2d"), reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    var dpr, Wd, Ht, S, OX, OY, LY, traces = [], deco = [], base = null, pulses = [], shown = 0, last = 0, stopped = false, fin = 0, fanA = 0, fanV = 0;
    var lit = {}, litT = {}, SPR = {}; for (var k in C) SPR[k] = sprite(C[k]);
    var t0 = performance.now();
    function build() {
      dpr = Math.min(2, devicePixelRatio || 1); Wd = cv.clientWidth; Ht = cv.clientHeight; cv.width = Math.round(Wd * dpr); cv.height = Math.round(Ht * dpr);
      var panel = o.panel ? o.panel.getBoundingClientRect() : { top: Ht * 0.7 }, top = Wd < 768 ? 64 : 84, bot = Math.max(top + 160, panel.top - (Wd < 768 ? 18 : 34));
      var tall = Wd < 700; LY = layout(tall);
      S = Math.min((Wd - (tall ? 24 : 120)) / LY.W, (bot - top) / LY.H); OX = (Wd - LY.W * S) / 2; OY = top + (bot - top - LY.H * S) / 2;
      traces = [];
      LY.links.concat(LINKS).forEach(function (l, li) {
        var A = LY.parts[l[0]], B = LY.parts[l[1]], ea = edge(A, B), eb = edge(B, A), n = l[3];
        var sxy = (Math.sign(eb.x - ea.x) || 1) * (Math.sign(eb.y - ea.y) || 1), flip = ea.hz !== eb.hz ? -sxy : 1;   /* nested lanes never cross at the corner */
        for (var j = 0; j < n; j++) {
          var o2 = (j - (n - 1) / 2) * 9, o3 = o2 * flip, a = { x: ea.x + (ea.hz ? 0 : o2), y: ea.y + (ea.hz ? o2 : 0) }, b = { x: eb.x + (eb.hz ? 0 : o3), y: eb.y + (eb.hz ? o3 : 0) };
          var pts = route(a, b, ea.hz, eb.hz); traces.push({ pts: pts, L: lens(pts), st: l[2], col: C[l[2]], t: 0, d: j * 70 + li * 20 });
        }
      });
      deco = [];   /* short stubs out to free connection points ("gateways") around each part */
      var seed = 11; function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
      Object.keys(LY.parts).forEach(function (pk) {
        var p = LY.parts[pk];
        for (var i = 0; i < 4; i++) {
          var side = Math.floor(rnd() * 4), u = 0.2 + rnd() * 0.6, len = 26 + rnd() * 46, a, b, m;
          if (side === 0) { a = { x: p.x + p.w * u, y: p.y }; m = { x: a.x, y: a.y - len * 0.55 }; b = { x: m.x + (rnd() < 0.5 ? -1 : 1) * len * 0.45, y: m.y - len * 0.45 }; }
          else if (side === 1) { a = { x: p.x + p.w, y: p.y + p.h * u }; m = { x: a.x + len * 0.55, y: a.y }; b = { x: m.x + len * 0.45, y: m.y + (rnd() < 0.5 ? -1 : 1) * len * 0.45 }; }
          else if (side === 2) { a = { x: p.x + p.w * u, y: p.y + p.h }; m = { x: a.x, y: a.y + len * 0.55 }; b = { x: m.x + (rnd() < 0.5 ? -1 : 1) * len * 0.45, y: m.y + len * 0.45 }; }
          else { a = { x: p.x, y: p.y + p.h * u }; m = { x: a.x - len * 0.55, y: a.y }; b = { x: m.x - len * 0.45, y: m.y + (rnd() < 0.5 ? -1 : 1) * len * 0.45 }; }
          if (b.x < 8 || b.x > LY.W - 8 || b.y < 8 || b.y > LY.H - 8) continue;
          var pts = [a, m, b]; deco.push({ pts: pts, L: lens(pts), st: pk, col: C[pk], t: 0, d: 180 + i * 90 });
        }
      });
      drawBase();
    }
    function X(x) { return OX + x * S; } function Y(y) { return OY + y * S; }
    function path(g, pts, upto, L) {
      g.beginPath(); g.moveTo(X(pts[0].x), Y(pts[0].y));
      if (upto == null) { for (var i = 1; i < pts.length; i++) g.lineTo(X(pts[i].x), Y(pts[i].y)); return; }
      var e = at(pts, L, upto); for (var j = 1; j < e.i; j++) g.lineTo(X(pts[j].x), Y(pts[j].y)); g.lineTo(X(e.x), Y(e.y));
    }
    function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
    function drawBase() {   /* the dark board, unpowered parts and dim traces, drawn once */
      base = document.createElement("canvas"); base.width = cv.width; base.height = cv.height; var g = base.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
      var gr = g.createRadialGradient(Wd / 2, Y(LY.H * 0.45), 0, Wd / 2, Y(LY.H * 0.45), Math.max(Wd, Ht) * 0.8);
      gr.addColorStop(0, "#0b0d1c"); gr.addColorStop(1, "#03040a"); g.fillStyle = gr; g.fillRect(0, 0, Wd, Ht);
      g.strokeStyle = "rgba(120,140,255,.05)"; g.lineWidth = 1;   /* faint board grid, inside the board only */
      for (var gx = 0; gx <= LY.W; gx += 40) { g.beginPath(); g.moveTo(X(gx), Y(0)); g.lineTo(X(gx), Y(LY.H)); g.stroke(); }
      for (var gy = 0; gy <= LY.H; gy += 40) { g.beginPath(); g.moveTo(X(0), Y(gy)); g.lineTo(X(LY.W), Y(gy)); g.stroke(); }
      g.lineCap = "round"; g.lineJoin = "round";
      traces.concat(deco).forEach(function (t) { g.strokeStyle = "rgba(170,180,230,.10)"; g.lineWidth = 1.4; path(g, t.pts); g.stroke(); var e = t.pts[t.pts.length - 1];
        g.beginPath(); g.arc(X(e.x), Y(e.y), 2.6, 0, 6.283); g.stroke(); });
      g.font = "600 " + Math.max(8, Math.round(11 * S * (Wd < 700 ? 1.5 : 1))) + "px ui-monospace,SFMono-Regular,Menlo,monospace"; g.textBaseline = "top";
      for (var pk in LY.parts) { var p = LY.parts[pk]; rr(g, X(p.x), Y(p.y), p.w * S, p.h * S, Math.max(4, 10 * S)); g.fillStyle = "#090b16"; g.fill(); g.strokeStyle = "rgba(170,180,230,.16)"; g.lineWidth = 1; g.stroke(); }
    }
    function tag(pk, p, on) {   /* label sits on its own dark chip, so no trace ever runs through the text */
      var fs = Math.max(8, Math.round(11 * S * (Wd < 700 ? 1.5 : 1))); cx.font = "600 " + fs + "px ui-monospace,SFMono-Regular,Menlo,monospace"; cx.textBaseline = "top";
      var tw = cx.measureText(TAG[pk]).width, lx = pk === "fan" ? X(p.x) + 6 : X(p.x + p.w) - 4 - tw, ly = Y(p.y + p.h) + 5;
      cx.fillStyle = "rgba(7,8,15,.94)"; cx.fillRect(lx - 4, ly - 3, tw + 8, fs + 6);
      cx.fillStyle = on > 0 ? rgba(C[pk], 0.25 + 0.65 * on) : "rgba(170,180,230,.24)"; cx.fillText(TAG[pk], lx, ly); }
    function glow(k, x, y, r, a) { cx.globalAlpha = a; cx.drawImage(SPR[k], x - r, y - r, r * 2, r * 2); cx.globalAlpha = 1; }
    function part(pk, p, on, ts) {   /* a powered part: colored edge light, inner detail */
      var col = C[pk], x = X(p.x), y = Y(p.y), w = p.w * S, h = p.h * S, rad = Math.max(4, 10 * S);
      cx.save(); rr(cx, x, y, w, h, rad);
      var f = cx.createLinearGradient(x, y, x + w, y + h); f.addColorStop(0, rgba(col, 0.10 * on)); f.addColorStop(1, rgba(col, 0.03 * on)); cx.fillStyle = f; cx.fill();
      cx.strokeStyle = rgba(col, 0.25 + 0.6 * on); cx.lineWidth = 1.5; cx.stroke(); cx.clip();
      var lw = Math.max(1, 1.3 * S * 2);
      if (p.kind === "cpu") {
        var m = w * 0.22; rr(cx, x + m, y + m, w - 2 * m, h - 2 * m, rad * 0.6); cx.strokeStyle = rgba(col, 0.5 * on); cx.lineWidth = lw; cx.stroke();
        var gg = cx.createRadialGradient(x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, w * 0.35); gg.addColorStop(0, rgba("#ffffff", 0.55 * on)); gg.addColorStop(0.3, rgba(col, 0.45 * on)); gg.addColorStop(1, rgba(col, 0));
        cx.fillStyle = gg; cx.fillRect(x, y, w, h);
        cx.fillStyle = rgba(col, 0.6 * on); for (var i = 1; i < 8; i++) { var u = i / 8; cx.fillRect(x + w * u - 1, y + 2, 2, m * 0.5); cx.fillRect(x + w * u - 1, y + h - 2 - m * 0.5, 2, m * 0.5); cx.fillRect(x + 2, y + h * u - 1, m * 0.5, 2); cx.fillRect(x + w - 2 - m * 0.5, y + h * u - 1, m * 0.5, 2); }
      } else if (p.kind === "mem") {
        for (var s2 = 0; s2 < 4; s2++) {
          var sx = x + w * (0.12 + s2 * 0.21), sw = w * 0.13, sy = y + h * 0.08, sh = h * 0.84; cx.fillStyle = "rgba(20,22,40,.9)"; cx.fillRect(sx, sy, sw, sh);
          var hue = (ts / 18 + s2 * 40) % 360, lg = cx.createLinearGradient(0, sy, 0, sy + sh);   /* RGB strip: cyan -> violet -> magenta, flowing */
          [0, 0.5, 1].forEach(function (q, qi) { var hh = (hue + qi * 60) % 360; hh = 180 + (hh % 140); lg.addColorStop(q, "hsla(" + hh + ",100%,62%," + (0.9 * on) + ")"); });
          cx.fillStyle = lg; cx.fillRect(sx + sw * 0.32, sy + 3, sw * 0.36, sh - 6);
        }
      } else if (p.kind === "net") {
        for (var r2 = 0; r2 < 4; r2++) {
          var py = y + h * (0.12 + r2 * 0.2), ph = h * 0.13; cx.strokeStyle = rgba(col, 0.45 * on); cx.lineWidth = lw; cx.strokeRect(x + w * 0.18, py, w * 0.5, ph);
          var blink = on > 0.9 && !reduce ? (Math.sin(ts / (90 + r2 * 37) + r2) > 0.2 ? 1 : 0.25) : on;
          cx.fillStyle = rgba(r2 % 2 ? "#5CFF8F" : col, 0.9 * blink); cx.fillRect(x + w * 0.74, py + ph * 0.25, w * 0.08, ph * 0.5);
        }
      } else if (p.kind === "gpu") {
        cx.fillStyle = rgba(col, 0.75 * on); cx.fillRect(x, y + h - 3 * S * 2, w * (0.25 + 0.75 * on), 3 * S * 2);   /* underglow bar */
        for (var fi = 0; fi < 2; fi++) fan(x + w * (0.3 + fi * 0.4), y + h * 0.46, h * 0.36, col, on, fi);
      } else if (p.kind === "fan") {
        fan(x + w / 2, y + h / 2, Math.min(w, h) * 0.42, col, on, 2);
      } else if (p.kind === "pwr") {
        cx.strokeStyle = rgba(col, 0.6 * on); cx.lineWidth = lw * 1.4; var cxp = x + w / 2, cyp = y + h / 2, R = Math.min(w, h) * 0.24;
        cx.beginPath(); cx.arc(cxp, cyp, R, -Math.PI / 2 + 0.6, Math.PI * 1.5 - 0.6); cx.stroke(); cx.beginPath(); cx.moveTo(cxp, cyp - R * 1.25); cx.lineTo(cxp, cyp - R * 0.1); cx.stroke();
      } else if (p.kind === "sat") {
        var ax = x + w * 0.32, ay = y + h * 0.7; cx.strokeStyle = rgba(col, 0.7 * on); cx.lineWidth = lw;
        cx.beginPath(); cx.moveTo(ax, ay); cx.lineTo(ax + w * 0.12, y + h * 0.3); cx.stroke();
        for (var wv = 0; wv < 3; wv++) { var ph2 = reduce ? 0 : ((ts / 900 + wv / 3) % 1); cx.strokeStyle = rgba(col, on * (1 - ph2) * 0.8); cx.beginPath(); cx.arc(ax + w * 0.12, y + h * 0.3, 8 + ph2 * w * 0.5, -1.2, 0.1); cx.stroke(); }
      }
      cx.restore();
      if (on > 0) glow(pk, x + w / 2, y + h / 2, Math.max(w, h) * 0.9, 0.16 * on * (p.kind === "cpu" ? 1.6 : 1));
    }
    function fan(fx, fy, R, col, on, id) {
      cx.save(); cx.translate(fx, fy);
      cx.strokeStyle = rgba(col, 0.35 + 0.5 * on); cx.lineWidth = Math.max(1, 2 * S); cx.beginPath(); cx.arc(0, 0, R, 0, 6.283); cx.stroke();   /* RGB ring */
      if (on > 0) { var ring = cx.createLinearGradient(-R, -R, R, R); ring.addColorStop(0, rgba("#22E5FF", on)); ring.addColorStop(0.5, rgba("#9D7BFF", on)); ring.addColorStop(1, rgba("#FF4FD8", on));
        cx.strokeStyle = ring; cx.lineWidth = Math.max(1.5, 3 * S); cx.beginPath(); cx.arc(0, 0, R * 0.96, 0, 6.283); cx.stroke(); }
      cx.rotate(fanA * (id === 1 ? -1.1 : 1) + id);
      var blades = 7, blur = Math.min(1, fanV / 14);
      for (var b = 0; b < blades; b++) {
        cx.rotate(6.283 / blades); cx.beginPath(); cx.moveTo(R * 0.2, 0); cx.quadraticCurveTo(R * 0.55, -R * 0.42, R * 0.86, -R * 0.12); cx.quadraticCurveTo(R * 0.6, R * 0.02, R * 0.2, R * 0.14); cx.closePath();
        cx.fillStyle = "rgba(200,210,255," + (0.16 + 0.1 * on - 0.08 * blur) + ")"; cx.fill();
      }
      if (blur > 0.2) { cx.fillStyle = rgba(col, 0.07 * blur * on); cx.beginPath(); cx.arc(0, 0, R * 0.86, 0, 6.283); cx.fill(); }   /* motion haze at speed */
      cx.beginPath(); cx.arc(0, 0, R * 0.2, 0, 6.283); cx.fillStyle = "#0a0c18"; cx.fill(); cx.strokeStyle = rgba(col, 0.8 * on); cx.lineWidth = 1.2; cx.stroke();
      cx.restore();
    }
    var want = false, wantCb = null, lastLit = -1e9;
    var perf = window.__bnBootPerf = { n: 0, ms: 0, max: 0 };
    function frame(ts) {
      if (stopped) return;
      var tq = performance.now();
      var dt = Math.min(50, ts - (last || ts)); last = ts;
      var target = Math.min(1, o.progress()); shown += (target - shown) * Math.min(1, dt / 240); if (want) shown = Math.max(shown, Math.min(1, shown + dt / 900)); if (fin) shown = 1;
      var pct = shown >= 0.995 ? 100 : Math.floor(shown * 100);
      if (o.pct) o.pct.textContent = String(pct).padStart(2, "0") + "%";
      if (o.bar) o.bar.style.transform = "scaleX(" + shown.toFixed(4) + ")";
      var stIdx = 0; for (var i = 0; i < STAGES.length; i++) if (shown >= STAGES[i].at || (STAGES[i].k === "fan" && ts - t0 > 500)) stIdx = i;
      if (want) stIdx = STAGES.length - 2;   /* data is in: light whatever is left, still one part at a time */
      for (var q = 0; q <= stIdx; q++) if (!lit[STAGES[q].k]) { if (!reduce && ts - lastLit < 240) break; lit[STAGES[q].k] = 1; litT[STAGES[q].k] = ts; lastLit = ts; break; }
      if (want && !fin && lit.sat && (reduce || ts - litT.sat > 380)) { fin = ts; setTimeout(function () { if (wantCb) wantCb(); }, reduce ? 0 : 520); }
      if (o.status) { var li = 0; for (var qq = 0; qq < STAGES.length; qq++) if (lit[STAGES[qq].k]) li = qq; var st = fin ? "Ready" : STAGES[Math.min(li, STAGES.length - 2)].t; if (o.status.textContent !== st) o.status.textContent = st; }
      if (lit.fan) { fanV = Math.min(reduce ? 0 : 26, fanV + dt * 0.018); fanA += fanV * dt / 1000; }
      cx.setTransform(1, 0, 0, 1, 0, 0); cx.drawImage(base, 0, 0); cx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var flash = fin ? Math.max(0, 1 - (ts - fin) / 700) : 0;
      cx.lineCap = "round"; cx.lineJoin = "round"; cx.globalCompositeOperation = "lighter";
      var all = traces.concat(deco);
      for (var j = 0; j < all.length; j++) {
        var t = all[j]; if (!lit[t.st]) continue;
        var age = ts - litT[t.st] - t.d; if (age < 0) continue;
        t.t = reduce ? 1 : Math.min(1, age / 650); var e = t.t * t.L[t.L.length - 1];
        cx.strokeStyle = rgba(t.col, 0.16 + 0.1 * flash); cx.lineWidth = 5; path(cx, t.pts, e, t.L); cx.stroke();
        cx.strokeStyle = rgba(t.col, 0.85); cx.lineWidth = 1.3; path(cx, t.pts, e, t.L); cx.stroke();
        var head = at(t.pts, t.L, e); if (t.t < 1) glow(t.st, X(head.x), Y(head.y), 14, 1);
        else { var end = t.pts[t.pts.length - 1]; glow(t.st, X(end.x), Y(end.y), 10 + 3 * Math.sin(ts / 400 + j), 0.8);   /* gateway node */
          if (!reduce && t.L.length > 3 && Math.random() < 0.012 * dt / 16) pulses.push({ t: t, p: 0, v: 0.45 + Math.random() * 0.4, rev: Math.random() < 0.35 }); }
      }
      for (var pi = pulses.length - 1; pi >= 0; pi--) {
        var pu = pulses[pi]; pu.p += pu.v * dt / 1000; if (pu.p >= 1) { pulses.splice(pi, 1); continue; }
        var dd = (pu.rev ? 1 - pu.p : pu.p) * pu.t.L[pu.t.L.length - 1], h2 = at(pu.t.pts, pu.t.L, dd); glow(pu.t.st, X(h2.x), Y(h2.y), 9, 1);
      }
      for (var pk in LY.parts) { if (!lit[pk]) continue; var on = reduce ? 1 : Math.min(1, (ts - litT[pk]) / 420);
        var fl = on < 1 ? 0.6 + 0.4 * Math.abs(Math.sin((ts - litT[pk]) / 35)) : 1;   /* a short power-on flicker */
        cx.globalCompositeOperation = "source-over"; part(pk, LY.parts[pk], Math.min(1, on * fl + flash * 0.3), ts); cx.globalCompositeOperation = "lighter"; }
      cx.globalCompositeOperation = "source-over";
      for (var tk in LY.parts) tag(tk, LY.parts[tk], lit[tk] ? (reduce ? 1 : Math.min(1, (ts - litT[tk]) / 420)) : 0);
      var cost = performance.now() - tq; perf.n++; perf.ms += cost; if (cost > perf.max) perf.max = cost;
      requestAnimationFrame(frame);
    }
    build(); var rz; addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(build, 120); });
    requestAnimationFrame(frame);
    return { done: function (cb) { if (want) return; want = true; wantCb = cb; }, stop: function () { stopped = true; } };
  };
})();
