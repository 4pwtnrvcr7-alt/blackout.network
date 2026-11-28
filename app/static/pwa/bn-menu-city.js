/* BLACKOUT.NETWORK menu animation: a massive night city, the lights go out in waves, then a device mesh comes online.
   Original, code-rendered canvas loop (no images, no libraries). Loop 14.4 s. Lazy-loaded by menu5.py the first time a menu opens.
   Smoothness: the scene is built in small slices across animation frames (no long task when the menu opens), the old frame keeps
   drawing while a resize rebuilds, the whole city is two canvases (a baked skyline and a baked window layer, so a frame is one
   blit plus the lit sectors), per-frame work allocates nothing, the caption is cached, 60 fps with an automatic step down to
   30 fps if frames run long. DPR <= 2 and a pixel budget. Pauses when the menu is closed or the tab is hidden;
   prefers-reduced-motion draws one static frame. The canvas is pointer-events:none and sits behind the menu links.
   Every mesh node is anchored to a lit window or a rooftop of a drawn building that is not hidden behind a nearer one. */
(function () {
  "use strict";
  if (window.__bnCity) return;
  var T = 14.4, RES = 0.035, STATIC_T = 11.0;
  var RM = false;
  try { RM = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  var COARSE = false; try { COARSE = matchMedia("(pointer: coarse)").matches; } catch (e) {}
  var MENUS = "#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])";
  var TAU = 6.2832;

  function mul(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function hash(a, b) { var h = Math.imul(a ^ 0x9E3779B1, 0x85EBCA6B) ^ Math.imul(b + 0x7F4A7C15, 0xC2B2AE35); h ^= h >>> 13; h = Math.imul(h, 0x27D4EB2F); h ^= h >>> 15; return (h >>> 0) / 4294967296; }
  function sm(x) { x = x < 0 ? 0 : x > 1 ? 1 : x; return x * x * (3 - 2 * x); }
  function cl(x, a, b) { return x < a ? a : x > b ? b : x; }
  function mk(w, h) { var c = document.createElement("canvas"); c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); return c; }

  var WARM = ["255,214,150", "255,196,128", "255,228,186", "255,170,100", "250,238,218", "255,205,140"];

  function cfgs(u) {
    return [
      { base: .74, minW: 7 * u, maxW: 16 * u, minH: .16, maxH: .46, gap: [0, 2 * u], ww: 1.3 * u, wh: 1.8 * u, sx: 2.7 * u, sy: 3.7 * u, lit: [.5, .85], rim: "#1b2633", body: "#0a1017", wa: .8, cols: 8, rows: 2, seed: 11, tall: .05, spire: .1 },
      { ground: true, cols: 8, rows: 1, seed: 5 },
      { base: .80, minW: 12 * u, maxW: 30 * u, minH: .22, maxH: .64, gap: [0, 3 * u], ww: 2 * u, wh: 2.8 * u, sx: 4.2 * u, sy: 5.9 * u, lit: [.5, .88], rim: "#1f2c3a", body: "#080c12", wa: 1, cols: 10, rows: 3, seed: 23, tall: .08, spire: .1 },
      { base: 1.04, minW: 34 * u, maxW: 80 * u, minH: .22, maxH: .58, gap: [60 * u, 190 * u], ww: 3 * u, wh: 4.4 * u, sx: 7 * u, sy: 10 * u, lit: [.4, .8], rim: "#16202b", body: "#05070a", wa: 1, cols: 6, rows: 3, seed: 37, tall: .05, spire: 0 }
    ];
  }

  function City(cv) {
    this.cv = cv; this.ctx = cv.getContext("2d"); this.S = null; this.job = null; this.fixed = null; this.t0 = 0; this.born = 0;
    this.raf = 0; this.on = false; this.last = 0; this.minDt = 14.5; this.ema = 0; this.slow = 0; this.dirty = 0; this.vis = true; this.capCache = {};
  }

  City.prototype.measure = function () {
    var cv = this.cv, W = Math.round(cv.clientWidth), H = Math.round(cv.clientHeight);
    var budget = COARSE ? 1.3e6 : 2.6e6;
    return { W: W, H: H, dpr: Math.max(1, Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(budget / Math.max(1, W * H)))) };
  };
  City.prototype.stale = function () {
    var m = this.measure(), S = this.S; if (!S) return true;
    return Math.abs(m.W - S.W) > 6 || Math.abs(m.H - S.H) > 6 || Math.abs(m.dpr - S.dpr) > .05;
  };
  City.prototype.startBuild = function () {
    if (this.job) return true;
    var m = this.measure(); if (m.W < 60 || m.H < 60) return false;
    this.job = this.gen(m.W, m.H, m.dpr); return true;
  };
  City.prototype.pump = function (budget) {
    var j = this.job; if (!j) return; var t0 = performance.now(), r;
    do { r = j.next(); if (r.done) { this.apply(r.value); this.job = null; return; } } while (performance.now() - t0 < budget);
  };
  City.prototype.finishSync = function () { var r; if (!this.job && !this.startBuild()) return false; do { r = this.job.next(); } while (!r.done); this.apply(r.value); this.job = null; return true; };
  City.prototype.apply = function (S) {
    var cv = this.cv; cv.width = Math.round(S.W * S.dpr); cv.height = Math.round(S.H * S.dpr);
    var first = !this.S; this.S = S; this.capCache = {};
    if (first) { this.t0 = performance.now(); this.born = this.t0; }
  };

  // ---- scene build, in slices (generator: yields between small chunks of work) ----
  // Two baked canvases: S.base = sky + every building silhouette, S.lit = every lit window + street glow, with each nearer
  // building punched out of the layers behind it. A frame is then one blit of S.base plus the lit sectors from S.lit.
  City.prototype.gen = function* (W, H, dpr) {
    var u = cl(W / 390, 1, 1.8), cf = cfgs(u), hy = H * .76, i, L = [], roofs = [], wins = [], rects = [], S;
    var base = mk(W * dpr, H * dpr), lit = mk(W * dpr, H * dpr), dx = base.getContext("2d"), lx = lit.getContext("2d");
    dx.scale(dpr, dpr); lx.scale(dpr, dpr);
    S = { W: W, H: H, dpr: dpr, u: u, hy: hy, rects: rects, base: base, lit: lit };
    var sg = dx.createLinearGradient(0, 0, 0, H); sg.addColorStop(0, "rgba(5,8,12,0)"); sg.addColorStop(.55, "rgba(10,15,22,.85)"); sg.addColorStop(1, "rgba(14,20,29,.95)");
    dx.fillStyle = sg; dx.fillRect(0, 0, W, H);
    yield;
    for (var li = 0; li < cf.length; li++) {
      var c = cf[li], r = mul(c.seed * 977 + W), rr2 = mul(c.seed * 31 + 5), lr = []; rects[li] = lr;
      if (c.ground) {
        var g = dx.createLinearGradient(0, hy, 0, H); g.addColorStop(0, "#0b1118"); g.addColorStop(1, "#05070a");
        dx.fillStyle = g; dx.fillRect(0, hy, W, H - hy);
        // street grid glow on its own scratch layer (faded toward the horizon), then composited onto S.lit
        var gl = mk(W * dpr, H * dpr), gx = gl.getContext("2d"); gx.scale(dpr, dpr);
        var vx = W / 2, n = 16, kk;
        gx.lineCap = "round";
        for (var pass = 0; pass < 2; pass++) {
          gx.strokeStyle = pass ? "rgba(255,176,104,.55)" : "rgba(255,150,80,.10)"; gx.lineWidth = pass ? 1 : 4.5 * u; gx.beginPath();
          for (i = -n; i <= n; i++) { var bx = vx + i * W * .105 * (1 + Math.abs(i) * .02); gx.moveTo(vx + i * 3 * u, hy); gx.lineTo(bx, H); }
          for (kk = 1; kk <= 10; kk++) { var yy = hy + (H - hy) * Math.pow(kk / 10, 2.1); gx.moveTo(0, yy); gx.lineTo(W, yy); }
          gx.stroke();
        }
        for (kk = 1; kk <= 10; kk++) for (i = -n; i <= n; i++) {
          if (r() < .35) { var yy2 = hy + (H - hy) * Math.pow(kk / 10, 2.1), bx2 = vx + i * 3 * u + (i * W * .105 * (1 + Math.abs(i) * .02) - i * 3 * u) * ((yy2 - hy) / (H - hy)); gx.fillStyle = "rgba(255,214,160," + (.35 + .5 * r()) + ")"; gx.fillRect(bx2 - 1, yy2 - 1, 2 * u * .8 + 1, 2); }
        }
        gx.globalCompositeOperation = "destination-in";
        var fg = gx.createLinearGradient(0, hy, 0, H); fg.addColorStop(0, "rgba(0,0,0,0)"); fg.addColorStop(.25, "rgba(0,0,0,.45)"); fg.addColorStop(1, "rgba(0,0,0,1)");
        gx.fillStyle = fg; gx.fillRect(0, 0, W, H);
        lx.setTransform(1, 0, 0, 1, 0, 0); lx.drawImage(gl, 0, 0); lx.setTransform(dpr, 0, 0, dpr, 0, 0);
        yield;
      } else {
        var x = -c.maxW * .5 + r() * c.maxW * .5, pal = [], cnt = 0, keep = li === 3 ? .5 : .3;
        for (i = 0; i < WARM.length; i++) pal.push("rgba(" + WARM[i] + "," + (c.wa * (.55 + .45 * (i % 3 === 0 ? 1 : .8))).toFixed(2) + ")");
        while (x < W + 4) {
          var w = c.minW + r() * (c.maxW - c.minW), dist = (x + w / 2) / W;
          var env = .62 + .55 * Math.exp(-Math.pow((dist - .4) / .3, 2)) + .12 * Math.sin(dist * 9 + c.seed);
          var h = H * (c.minH + (c.maxH - c.minH) * Math.pow(r(), 1.5)) * env; if (r() < c.tall) h *= 1.35;
          h = Math.min(h, H * .86);
          var top = c.base * H - h, rects2 = [[x, top, w, c.base * H - top + (li === 3 ? 20 : 4)]];
          if (r() < .38) { var w2 = w * (.5 + .25 * r()), h2 = h * (.1 + .12 * r()); rects2.push([x + (w - w2) / 2, top - h2, w2, h2 + 1]); }
          var bp = c.lit[0] + (c.lit[1] - c.lit[0]) * r();
          for (var q = 0; q < rects2.length; q++) {
            var R = rects2[q];
            dx.fillStyle = c.body; dx.fillRect(R[0], R[1], R[2], R[3]);
            dx.fillStyle = c.rim; dx.fillRect(R[0], R[1], R[2], 1); dx.fillRect(R[0], R[1], 1, R[3]);
            lx.globalCompositeOperation = "destination-out"; lx.fillStyle = "#000"; lx.fillRect(R[0], R[1], R[2], R[3]); lx.globalCompositeOperation = "source-over";
            lr.push(R);
            if (li >= 2 && q === rects2.length - 1 && R[0] + R[2] / 2 > W * .03 && R[0] + R[2] / 2 < W * .97 && R[1] > H * .08 && R[2] >= 8 * u) roofs.push({ l: li, x: R[0] + R[2] / 2, y: R[1] });
            var m = c.ww * 1.3, nc = Math.floor((R[2] - 2 * m + (c.sx - c.ww)) / c.sx), nr = Math.floor((R[3] - 2 * m + (c.sy - c.wh)) / c.sy);
            if (li === 3) nr = Math.min(nr, Math.floor((H * c.base - R[1] - 6) / c.sy));
            if (nc < 1 || nr < 1) continue;
            var ox = R[0] + (R[2] - (nc * c.sx - (c.sx - c.ww))) / 2, oy = R[1] + m;
            for (var row = 0; row < nr; row++) {
              var rv = r(), pr = cl(bp * (rv < .18 ? 1.55 : rv < .42 ? .3 : 1), 0, .95), wy = oy + row * c.sy;
              for (var cc = 0; cc < nc; cc++) {
                var wx = ox + cc * c.sx;
                dx.fillStyle = "rgba(78,98,118,.15)"; dx.fillRect(wx, wy, c.ww, c.wh);
                if (r() < pr) {
                  lx.fillStyle = pal[(r() * pal.length) | 0]; lx.fillRect(wx, wy, c.ww, c.wh);
                  if (li >= 2 && rr2() < keep) wins.push({ l: li, x: wx + c.ww / 2, y: wy + c.wh / 2 });
                }
              }
            }
          }
          if (c.spire && r() < c.spire && h > H * .3) { var sh = 14 * u + r() * 34 * u; dx.fillStyle = c.rim; dx.fillRect(x + w / 2, top - sh - (rects2.length > 1 ? rects2[1][3] : 0), 1, sh + 1); }
          x += w + c.gap[0] + r() * (c.gap[1] - c.gap[0]);
          if ((++cnt & 3) === 0) yield;
        }
        yield;
      }
    }
    // one tile grid over the screen: the unit the blackout switches off
    var cols = cl(Math.round(W / 62), 6, 20), rows = cl(Math.round(H / 125), 4, 7), tiles = [], cwd = base.width, chd = base.height, ti, tj;
    for (tj = 0; tj < rows; tj++) for (ti = 0; ti < cols; ti++) {
      var x0 = Math.floor(ti * cwd / cols), x1 = Math.floor((ti + 1) * cwd / cols), y0 = Math.floor(tj * chd / rows), y1 = Math.floor((tj + 1) * chd / rows);
      var cx = ((x0 + x1) / 2 / dpr) / W, cy = ((y0 + y1) / 2 / dpr) / H, id = tj * 32 + ti;
      var h1 = hash(id, 1), h2b = hash(id, 2), h3 = hash(id, 3), ts;
      if (h1 < .3) ts = 3.3 + 2.0 * (1 - cx) + .6 * h2b + .25 * cy; else ts = 2.5 + 2.4 * cx + .6 * h2b + .25 * cy;
      tiles.push({ x0: x0, y0: y0, w: x1 - x0, h: y1 - y0, ts: ts, rs: 13.0 + .9 * h3, id: id, ph: h2b * 6.28 });
    }
    S.tiles = tiles;
    // horizon haze gradient (cached, drawn as one additive fill)
    var hc0 = dx.createLinearGradient(0, hy - H * .34, 0, hy + H * .08); hc0.addColorStop(0, "rgba(255,140,64,0)"); hc0.addColorStop(.75, "rgba(255,150,76,.55)"); hc0.addColorStop(1, "rgba(255,120,50,.2)");
    S.hazeG = hc0; S.hazeY = hy - H * .34; S.hazeH = H * .42;
    var hs = mk(64, 64), hc = hs.getContext("2d"), rg = hc.createRadialGradient(32, 32, 0, 32, 32, 32);
    rg.addColorStop(0, "rgba(190,240,255,.95)"); rg.addColorStop(.25, "rgba(110,215,255,.4)"); rg.addColorStop(1, "rgba(60,170,255,0)"); hc.fillStyle = rg; hc.fillRect(0, 0, 64, 64); S.halo = hs;
    yield;
    this.mesh(S, roofs, wins);
    return S;
  };

  // true when a point of layer l is covered by a nearer layer's building
  function hidden(S, l, x, y) {
    var m, j, R;
    for (m = l + 1; m < S.rects.length; m++) {
      for (j = 0; j < S.rects[m].length; j++) { R = S.rects[m][j]; if (x > R[0] - 3 && x < R[0] + R[2] + 3 && y > R[1] - 3 && y < R[1] + R[3] + 3) return true; }
    }
    return false;
  }

  City.prototype.mesh = function (S, roofs, wins) {
    var W = S.W, H = S.H, u = S.u, area = W * H, N = cl(Math.round(area / (390 * 700) * 48), 36, 90), rnd = mul(7), cand = [], i, j, z;
    for (i = 0; i < roofs.length; i++) if (!hidden(S, roofs[i].l, roofs[i].x, roofs[i].y - 2)) cand.push({ l: roofs[i].l, x: roofs[i].x, y: roofs[i].y, k: "unit" });
    var wc = [];
    for (i = 0; i < wins.length; i++) if (wins[i].y > 34 && wins[i].y < H - 10 && !hidden(S, wins[i].l, wins[i].x, wins[i].y)) wc.push({ l: wins[i].l, x: wins[i].x, y: wins[i].y, k: "phone" });
    for (i = wc.length - 1; i > 0; i--) { j = (rnd() * (i + 1)) | 0; z = wc[i]; wc[i] = wc[j]; wc[j] = z; }
    var rc = cand.slice(), pick = [], nodes = [], minD = Math.sqrt(area / N) * .66;
    for (i = rc.length - 1; i > 0; i--) { j = (rnd() * (i + 1)) | 0; z = rc[i]; rc[i] = rc[j]; rc[j] = z; }
    for (i = 0; i < wc.length && i < 700; i++) pick.push(wc[i]);
    // rooftop units first (about a third of the mesh), then lit windows, so both are spread over the skyline
    for (var pass = 0; pass < 3 && nodes.length < Math.min(N, 30); pass++) {
      nodes = [];
      var seq = rc.concat(pick), nroof = 0, lim = Math.round(N * .34);
      for (i = 0; i < seq.length && nodes.length < N; i++) {
        var c = seq[i]; if (c.k === "unit" && nroof >= lim) continue;
        var ok = c.x > 8 && c.x < W - 8 && c.y > 28 && c.y < H - 8;
        for (j = 0; ok && j < nodes.length; j++) if (Math.hypot(nodes[j].x - c.x, nodes[j].y - c.y) < minD) ok = false;
        if (ok) { nodes.push(c); if (c.k === "unit") nroof++; }
      }
      minD *= .8;
    }
    var s = 0, sd = 1e9; for (i = 0; i < nodes.length; i++) { var d = Math.hypot(nodes[i].x - W * .45, nodes[i].y - H * .55); if (d < sd) { sd = d; s = i; } }
    var n = nodes.length, E = [], seen = {}, maxD = minD * 3;
    function add(a, b) { var k = a < b ? a + "_" + b : b + "_" + a; if (seen[k] || a === b) return; seen[k] = 1; E.push({ a: a, b: b, len: Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) }); }
    for (i = 0; i < n; i++) {
      var ds = []; for (j = 0; j < n; j++) if (j !== i) ds.push([Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y), j]);
      ds.sort(function (p, q) { return p[0] - q[0]; });
      for (j = 0; j < 3 && j < ds.length; j++) if (ds[j][0] < maxD || j === 0) add(i, ds[j][1]);
    }
    var par = []; for (i = 0; i < n; i++) par[i] = i;
    function f(x) { while (par[x] !== x) { par[x] = par[par[x]]; x = par[x]; } return x; }
    for (i = 0; i < E.length; i++) par[f(E[i].a)] = f(E[i].b);
    for (var guard = 0; guard < n; guard++) {
      var best = null; for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) if (f(i) !== f(j)) { var dd = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y); if (!best || dd < best[0]) best = [dd, i, j]; }
      if (!best) break; add(best[1], best[2]); par[f(best[1])] = f(best[2]);
    }
    var adj = []; for (i = 0; i < n; i++) adj[i] = [];
    for (i = 0; i < E.length; i++) { adj[E[i].a].push(i); adj[E[i].b].push(i); }
    var dist = [], done = [], from = []; for (i = 0; i < n; i++) { dist[i] = 1e9; done[i] = 0; from[i] = -1; } dist[s] = 0;
    for (var it = 0; it < n; it++) {
      var m = -1; for (i = 0; i < n; i++) if (!done[i] && (m < 0 || dist[i] < dist[m])) m = i;
      if (m < 0 || dist[m] >= 1e9) break; done[m] = 1;
      for (i = 0; i < adj[m].length; i++) { var e = E[adj[m][i]], o = e.a === m ? e.b : e.a; if (dist[m] + e.len < dist[o]) { dist[o] = dist[m] + e.len; from[o] = adj[m][i]; } }
    }
    var mx = 1; for (i = 0; i < n; i++) if (dist[i] < 1e9) mx = Math.max(mx, dist[i]);
    var T0 = 6.9, SPAN = 4.7, sp = mx / SPAN;
    for (i = 0; i < n; i++) nodes[i].on = T0 + (dist[i] < 1e9 ? dist[i] / sp : SPAN);
    for (i = 0; i < E.length; i++) {
      var ed = E[i], tree = (from[ed.a] === i) || (from[ed.b] === i);
      ed.tree = tree;
      if (tree) { var ch = from[ed.b] === i ? ed.b : ed.a, pr = ch === ed.a ? ed.b : ed.a; ed.from = pr; ed.to = ch; ed.t0 = nodes[pr].on; ed.t1 = nodes[ch].on; }
      else { ed.from = ed.a; ed.to = ed.b; ed.t0 = Math.max(nodes[ed.a].on, nodes[ed.b].on) + .25; ed.t1 = ed.t0 + .5; }
    }
    S.nodes = nodes; S.E = E; S.px = new Float32Array(n); S.py = new Float32Array(n);
    var P = [], flashes = [], r = mul(99), K = 20, spd = 120 * u;
    for (var k = 0; k < K; k++) {
      var st = 8.0 + k * .26 + r() * .2, act = []; for (i = 0; i < n; i++) if (nodes[i].on < st - .1) act.push(i);
      if (act.length < 3) continue;
      var a = act[(r() * act.length) | 0], q = [a], prev = {}, vis = {}; vis[a] = 1;
      var depth = {}; depth[a] = 0; var head = 0;
      while (head < q.length) { var cu = q[head++]; for (i = 0; i < adj[cu].length; i++) { var ee = E[adj[cu][i]]; if (ee.t1 > st) continue; var o2 = ee.a === cu ? ee.b : ee.a; if (vis[o2] || nodes[o2].on > st) continue; vis[o2] = 1; prev[o2] = cu; depth[o2] = depth[cu] + 1; q.push(o2); } }
      var far = q.filter(function (z2) { return depth[z2] >= 3; }); if (!far.length) far = q.filter(function (z2) { return depth[z2] >= 1; }); if (!far.length) continue;
      var tgt = far[(r() * far.length) | 0], path = [tgt]; while (path[0] !== a) path.unshift(prev[path[0]]);
      var segs = [], tt = st;
      for (i = 0; i + 1 < path.length; i++) { var dl = Math.hypot(nodes[path[i]].x - nodes[path[i + 1]].x, nodes[path[i]].y - nodes[path[i + 1]].y) / spd + .05; segs.push({ a: path[i], b: path[i + 1], t0: tt, t1: tt + dl }); tt += dl; flashes.push({ t: tt, n: path[i + 1] }); }
      flashes.push({ t: st, n: a });
      P.push({ segs: segs, t0: st, t1: tt });
    }
    S.P = P; S.F = flashes;
  };


  City.prototype.light = function (tile, t) {
    var a;
    if (t < tile.ts) a = 1;
    else if (t < tile.ts + 1.1) { var p = (t - tile.ts) / 1.1, n = Math.floor((t - tile.ts) * 17); a = hash(tile.id, n + 5) > p * .95 ? (.55 + .45 * hash(tile.id, n + 9)) : .06; if (p > .9) a = RES; }
    else if (t < tile.rs) a = RES;
    else { var q = (t - tile.rs) / .5; a = RES + (1 - RES) * sm(q); if (q < 1 && hash(tile.id, Math.floor(t * 20)) < .25) a *= .5; }
    if (a === 1) a *= .96 + .04 * Math.sin(t * 1.9 + tile.ph);
    return a;
  };

  City.prototype.draw = function (t, now) {
    var S = this.S, ctx = this.ctx, dpr = S.dpr, cw = this.cv.width, ch = this.cv.height, j, tl, a, sum = 0, tiles = S.tiles, n = tiles.length;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1; ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(S.base, 0, 0);
    var dim = S.W >= 900 ? 1 : .86;
    for (j = 0; j < n; j++) {
      tl = tiles[j]; a = this.light(tl, t); sum += a;
      if (a < .01) continue;
      ctx.globalAlpha = a * dim; ctx.drawImage(S.lit, tl.x0, tl.y0, tl.w, tl.h, tl.x0, tl.y0, tl.w, tl.h);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = .55 * (sum / n); ctx.fillStyle = S.hazeG; ctx.fillRect(0, S.hazeY, S.W, S.hazeH); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    this.drawMesh(t);
    if (S.W >= 900) this.scrim();
    this.fade(); this.caption(t);
    var k = cl((now - this.born) / 600, 0, 1);
    if (k < 1) { ctx.globalCompositeOperation = "destination-out"; ctx.fillStyle = "rgba(0,0,0," + (1 - k * k * (3 - 2 * k)).toFixed(3) + ")"; ctx.fillRect(0, 0, S.W, S.H); ctx.globalCompositeOperation = "source-over"; }
  };

  City.prototype.drawMesh = function (t) {
    var S = this.S, ctx = this.ctx, nodes = S.nodes, E = S.E, u = S.u, i, j, ma = t > 12.9 ? 1 - sm((t - 12.9) / 1.0) : 1;
    if (t < 6.8 || ma <= 0.01) return;
    var px = S.px, py = S.py, nd, n = nodes.length;
    for (i = 0; i < n; i++) { px[i] = nodes[i].x; py[i] = nodes[i].y; }
    ctx.globalAlpha = ma; ctx.lineCap = "round";
    var pass, e, p, x2, y2, ax, ay, bx, by;
    for (pass = 0; pass < 2; pass++) {
      ctx.strokeStyle = pass ? "rgba(214,247,255,.55)" : "rgba(90,200,255,.12)"; ctx.lineWidth = pass ? 1 : 3.2; ctx.beginPath();
      for (i = 0; i < E.length; i++) {
        e = E[i]; if (t < e.t0) continue; if (!e.tree && t < e.t1) continue;
        p = e.tree ? sm((t - e.t0) / Math.max(.05, e.t1 - e.t0)) : 1;
        ax = px[e.from]; ay = py[e.from]; bx = px[e.to]; by = py[e.to];
        ctx.moveTo(ax, ay); ctx.lineTo(ax + (bx - ax) * p, ay + (by - ay) * p);
      }
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(190,240,255,.35)"; ctx.lineWidth = 1;
    for (i = 0; i < E.length; i++) { e = E[i]; if (e.tree || t < e.t0 || t >= e.t1) continue; ctx.globalAlpha = ma * sm((t - e.t0) / (e.t1 - e.t0)); ctx.beginPath(); ctx.moveTo(px[e.from], py[e.from]); ctx.lineTo(px[e.to], py[e.to]); ctx.stroke(); }
    ctx.globalAlpha = ma;
    ctx.globalCompositeOperation = "lighter";
    var us = Math.min(u, 1.4), hs = 14 + 6 * us;
    for (i = 0; i < n; i++) {
      nd = nodes[i]; var dt = t - nd.on; if (dt < 0) continue; var a = sm(dt / .35);
      ctx.globalAlpha = ma * a * .7; ctx.drawImage(S.halo, px[i] - hs / 2, py[i] - hs / 2, hs, hs);
      if (dt < 1.1) { ctx.globalAlpha = ma * (1 - dt / 1.1) * .8; ctx.strokeStyle = "rgba(170,235,255,1)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(px[i], py[i], 3 + dt * 20 * us, 0, TAU); ctx.stroke(); }
    }
    var F = S.F; for (i = 0; i < F.length; i++) { var df = t - F[i].t; if (df < 0 || df > .55) continue; var fs = 18 + df * 30, fi = F[i].n; ctx.globalAlpha = ma * (1 - df / .55) * .9; ctx.drawImage(S.halo, px[fi] - fs / 2, py[fi] - fs / 2, fs, fs); }
    ctx.globalCompositeOperation = "source-over";
    var s = us;
    for (i = 0; i < n; i++) {
      nd = nodes[i]; if (t < nd.on) continue; ctx.globalAlpha = ma * sm((t - nd.on) / .3); ctx.fillStyle = "#eefcff"; ctx.strokeStyle = "rgba(220,248,255,.9)";
      var x = px[i], y = py[i];
      if (nd.k === "unit") { ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 6 * s); ctx.stroke(); ctx.beginPath(); ctx.arc(x, y - 6 * s, 1.1 * s, 0, TAU); ctx.fill(); ctx.fillRect(x - 2 * s, y - .5, 4 * s, 2 * s); }
      else { var pw = 2.6 * s, ph = 4.6 * s; ctx.fillRect(x - pw / 2, y - ph / 2, pw, ph); ctx.fillStyle = "#4fc3f7"; ctx.fillRect(x - pw / 2 + .5, y - ph / 2 + .7, pw - 1, ph - 1.9); }
    }
    ctx.globalCompositeOperation = "lighter";
    for (i = 0; i < S.P.length; i++) {
      var pk = S.P[i]; if (t < pk.t0 || t > pk.t1 + .3) continue;
      for (j = 0; j < pk.segs.length; j++) {
        var sg = pk.segs[j]; if (t < sg.t0 || t > sg.t1) continue;
        var q = (t - sg.t0) / (sg.t1 - sg.t0), a2x = px[sg.a], a2y = py[sg.a], b2x = px[sg.b], b2y = py[sg.b], hx = a2x + (b2x - a2x) * q, hy2 = a2y + (b2y - a2y) * q, q0 = Math.max(0, q - .35), tx = a2x + (b2x - a2x) * q0, ty = a2y + (b2y - a2y) * q0;
        var gr = ctx.createLinearGradient(tx, ty, hx, hy2); gr.addColorStop(0, "rgba(120,220,255,0)"); gr.addColorStop(1, "rgba(235,252,255,.95)");
        ctx.globalAlpha = ma; ctx.strokeStyle = gr; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy2); ctx.stroke();
        ctx.globalAlpha = ma * .9; ctx.drawImage(S.halo, hx - 6, hy2 - 6, 12, 12);
        ctx.globalAlpha = ma; ctx.fillStyle = "#fff"; ctx.fillRect(hx - 1.2, hy2 - 1.2, 2.4, 2.4);
      }
    }
    ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  };

  City.prototype.scrim = function () {
    var S = this.S, ctx = this.ctx, W = S.W, H = S.H;
    if (!S.scrimG) { var g = ctx.createLinearGradient(W * .38, 0, W * .86, 0); g.addColorStop(0, "rgba(4,6,9,0)"); g.addColorStop(1, "rgba(4,6,9,.55)"); S.scrimG = g; }
    ctx.fillStyle = S.scrimG; ctx.fillRect(W * .38, 0, W * .62, H);
  };

  // soften the canvas edges so the city melts into the menu instead of ending in a hard rectangle
  City.prototype.fade = function () {
    var S = this.S, ctx = this.ctx, W = S.W, H = S.H, f = Math.min(44 * S.u, W * .12);
    if (!S.fadeG) {
      var a = ctx.createLinearGradient(0, 0, f, 0), b = ctx.createLinearGradient(W - f, 0, W, 0), c = ctx.createLinearGradient(0, H - f * .8, 0, H);
      a.addColorStop(0, "rgba(0,0,0,1)"); a.addColorStop(1, "rgba(0,0,0,0)"); b.addColorStop(0, "rgba(0,0,0,0)"); b.addColorStop(1, "rgba(0,0,0,1)"); c.addColorStop(0, "rgba(0,0,0,0)"); c.addColorStop(1, "rgba(0,0,0,1)");
      S.fadeG = [a, b, c];
    }
    ctx.globalCompositeOperation = "destination-out";
    ctx.fillStyle = S.fadeG[0]; ctx.fillRect(0, 0, f, H);
    ctx.fillStyle = S.fadeG[1]; ctx.fillRect(W - f, 0, f, H);
    ctx.fillStyle = S.fadeG[2]; ctx.fillRect(0, H - f * .8, W, f * .8);
    ctx.globalCompositeOperation = "source-over";
  };

  // caption: each text state is drawn once into a small cached canvas, then blitted
  City.prototype.cap = function (txt, mark) {
    var key = mark + "|" + txt, c = this.capCache[key]; if (c) return c;
    var S = this.S, dpr = S.dpr, u = Math.min(S.u, 1.3), fs = 10 * u, sp = 1.6 * u, i, w = 17, cv, x;
    var m = mk(4, 4).getContext("2d"); m.font = "600 " + fs.toFixed(1) + "px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace";
    for (i = 0; i < txt.length; i++) w += m.measureText(txt[i]).width + sp;
    var cw = Math.ceil(w + 8), chh = Math.ceil(16 * u + 8);
    cv = mk(cw * dpr, chh * dpr); x = cv.getContext("2d"); x.scale(dpr, dpr);
    x.font = m.font; x.textBaseline = "middle"; var y = chh / 2;
    x.fillStyle = mark === 1 ? "rgba(255,206,150,.95)" : mark === 2 ? "rgba(150,160,172,.9)" : "rgba(140,226,255,.95)";
    if (mark === 2) { x.strokeStyle = x.fillStyle; x.lineWidth = 1; x.strokeRect(.5, y - 3.5, 7, 7); } else x.fillRect(0, y - 4, 8, 8);
    x.fillStyle = mark === 3 ? "rgba(190,238,255,.95)" : "rgba(200,210,220,.95)";
    var cx = 17; for (i = 0; i < txt.length; i++) { x.fillText(txt[i], cx, y); cx += m.measureText(txt[i]).width + sp; }
    c = { cv: cv, w: cw, h: chh, end: cx, y: y, u: u }; this.capCache[key] = c; return c;
  };

  City.prototype.caption = function (t) {
    var ctx = this.ctx, txt = "", al = 1, mark = 0;
    function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
    if (t < 2.4) { txt = "GRID ONLINE"; al = sm(t / .4) * (1 - sm((t - 2.1) / .3)); mark = 1; }
    else if (t < 6.8) { txt = "GRID DOWN"; al = sm((t - 2.8) / .3) * (1 - sm((t - 6.5) / .3)); mark = 2; }
    else if (t < 12.9) { var full = "blackout.network activated"; txt = full.slice(0, Math.floor(clamp01((t - 7.0) / 1.1) * full.length)); mark = 3; al = sm((t - 6.9) / .2) * (1 - sm((t - 12.6) / .3)); }
    else { txt = "GRID RESTORED"; al = sm((t - 13.0) / .3) * (1 - sm((t - 14.1) / .3)); mark = 1; }
    if (al <= .01 || !txt) return;
    var c = this.cap(txt, mark), x = 18, y = 26;
    ctx.globalAlpha = al; ctx.drawImage(c.cv, x, y - c.h / 2, c.w, c.h);
    if (mark === 2 && Math.floor(t * 2.5) % 2 === 0) { ctx.fillStyle = "rgba(200,210,220,.95)"; ctx.fillRect(x + c.end + 1, y - 5, 5 * c.u, 9 * c.u); }
    ctx.globalAlpha = 1;
  };

  City.prototype.frame = function (now) {
    if (!this.on) return; var self = this;
    this.raf = requestAnimationFrame(function (n) { self.frame(n); });
    if (this.job) this.pump(this.S ? 3 : 7);
    else if (!this.S) { if (!this.startBuild()) return; this.pump(7); }
    else if (this.dirty && now - this.dirty > 250) { this.dirty = 0; if (this.stale()) this.startBuild(); }
    if (!this.S) return;
    if (now - this.last < this.minDt) return; this.last = now;
    var w0 = performance.now(), t = this.fixed != null ? this.fixed : ((now - this.t0) / 1000) % T;
    this.draw(t, now);
    var dt = performance.now() - w0; this.ema = this.ema ? this.ema * .92 + dt * .08 : dt;
    // frames running long: step down to 30 fps instead of stuttering
    if (this.minDt < 20 && this.ema > 11) { if (++this.slow > 90) { this.minDt = 31; this.slow = 0; } } else this.slow = 0;
  };
  City.prototype.start = function () { if (this.on) return; this.on = true; this.last = 0; if (this.S) this.t0 = performance.now(); var self = this; this.raf = requestAnimationFrame(function (n) { self.frame(n); }); };
  City.prototype.stop = function () { this.on = false; if (this.raf) cancelAnimationFrame(this.raf); this.raf = 0; };
  City.prototype.still = function (t) {
    if (!this.S && !this.finishSync()) return;
    this.draw(t != null ? t : (this.fixed != null ? this.fixed : STATIC_T), this.born + 1e6);
  };

  // anchoring audit: paint every building (far to near, ids = layer) on a scratch canvas, then every node must sit on a building
  // of its own layer (not sky, not street, not hidden behind a nearer building)
  City.prototype.audit = function () {
    var S = this.S, out = { nodes: S.nodes.length, floating: 0, hidden: 0, units: 0, phones: 0 }, i, j, m = mk(S.W, S.H), x = m.getContext("2d", { willReadFrequently: true });
    for (i = 0; i < S.rects.length; i++) { x.fillStyle = "rgb(" + (i + 1) * 40 + ",0,0)"; for (j = 0; j < S.rects[i].length; j++) { var R = S.rects[i][j]; x.fillRect(R[0], R[1], R[2], R[3]); } }
    for (i = 0; i < S.nodes.length; i++) {
      var nd = S.nodes[i]; nd.k === "unit" ? out.units++ : out.phones++;
      var d = x.getImageData(Math.round(nd.x), Math.round(nd.k === "unit" ? nd.y + 1.5 : nd.y), 1, 1).data;
      if (d[3] < 200) out.floating++; else if (d[0] !== (nd.l + 1) * 40) out.hidden++;
    }
    return out;
  };

  var all = [];
  function inMenu(cv) { return cv.closest("#bn-menu,#h_menu,#w2_menu"); }
  function menuOpen(cv) { var m = inMenu(cv); return m ? m.matches(MENUS) : true; }
  function sync(c) {
    var want = !document.hidden && menuOpen(c.cv) && c.vis !== false;
    if (RM) { if (want) { c.finishSync(); c.still(); } return; }
    if (want) c.start(); else c.stop();
  }
  function init(cv) {
    if (cv.__bnCity) return; var c = cv.__bnCity = new City(cv); all.push(c);
    var m = inMenu(cv);
    if (m && window.MutationObserver) new MutationObserver(function () { sync(c); }).observe(m, { attributes: true, attributeFilter: ["class", "hidden"] });
    if (window.ResizeObserver) new ResizeObserver(function () {
      if (!c.S) return;
      if (c.on) c.dirty = performance.now();
      else if (RM) { clearTimeout(c.rt); c.rt = setTimeout(function () { if (c.stale() && menuOpen(cv)) { c.S = null; c.job = null; c.finishSync(); c.still(); } }, 250); }
    }).observe(cv);
    if (window.IntersectionObserver) new IntersectionObserver(function (es) { c.vis = es[es.length - 1].isIntersecting; sync(c); }).observe(cv);
    sync(c);
  }
  function scan() { var l = document.querySelectorAll("canvas.m5-city"); for (var i = 0; i < l.length; i++) init(l[i]); }
  document.addEventListener("visibilitychange", function () { for (var i = 0; i < all.length; i++) sync(all[i]); });
  window.__bnCity = { all: all, scan: scan, T: T, freeze: function (t) { for (var i = 0; i < all.length; i++) { all[i].fixed = t; all[i].stop(); all[i].finishSync(); all[i].still(t); } }, audit: function () { return all.map(function (c) { return c.S ? c.audit() : null; }); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan); else scan();
})();
