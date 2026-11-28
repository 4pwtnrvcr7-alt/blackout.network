/* BLACKOUT.NETWORK menu animation: a massive night city, the lights go out in waves, then a peer-to-peer mesh comes online.
   Original, code-rendered canvas loop (no images, no libraries). Loop 14.4 s. Lazy-loaded by menu5.py the first time a menu opens.
   Pauses when the menu is closed or the tab is hidden, DPR capped at 2 (and by a pixel budget), 30 fps on touch devices,
   prefers-reduced-motion draws one static frame. The canvas is pointer-events:none and sits behind the menu links. */
(function () {
  "use strict";
  if (window.__bnCity) return;
  var T = 14.4, RES = 0.035, STATIC_T = 11.0;
  var RM = false, COARSE = false;
  try { RM = matchMedia("(prefers-reduced-motion: reduce)").matches; COARSE = matchMedia("(pointer: coarse)").matches; } catch (e) {}
  var MENUS = "#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])";

  function mul(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function hash(a, b) { var h = Math.imul(a ^ 0x9E3779B1, 0x85EBCA6B) ^ Math.imul(b + 0x7F4A7C15, 0xC2B2AE35); h ^= h >>> 13; h = Math.imul(h, 0x27D4EB2F); h ^= h >>> 15; return (h >>> 0) / 4294967296; }
  function sm(x) { x = x < 0 ? 0 : x > 1 ? 1 : x; return x * x * (3 - 2 * x); }
  function cl(x, a, b) { return x < a ? a : x > b ? b : x; }
  function mk(w, h) { var c = document.createElement("canvas"); c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); return c; }

  var WARM = ["255,214,150", "255,196,128", "255,228,186", "255,170,100", "250,238,218", "255,205,140"];

  function cfgs(W, H, u) {
    return [
      { amp: 3 * u, mx: 8 * u, base: .74, minW: 7 * u, maxW: 16 * u, minH: .16, maxH: .46, gap: [0, 2 * u], ww: 1.3 * u, wh: 1.8 * u, sx: 2.7 * u, sy: 3.7 * u, lit: [.5, .85], rim: "#1b2633", body: "#0a1017", wa: .8, cols: 8, rows: 2, seed: 11, tall: .05, spire: .1 },
      { amp: 0, mx: 10 * u, ground: true, cols: 8, rows: 1, seed: 5 },
      { amp: 7 * u, mx: 16 * u, base: .80, minW: 12 * u, maxW: 30 * u, minH: .22, maxH: .64, gap: [0, 3 * u], ww: 2 * u, wh: 2.8 * u, sx: 4.2 * u, sy: 5.9 * u, lit: [.5, .88], rim: "#1f2c3a", body: "#080c12", wa: 1, cols: 10, rows: 3, seed: 23, tall: .08, spire: .1 },
      { amp: 13 * u, mx: 28 * u, base: 1.04, minW: 34 * u, maxW: 80 * u, minH: .22, maxH: .58, gap: [60 * u, 190 * u], ww: 3 * u, wh: 4.4 * u, sx: 7 * u, sy: 10 * u, lit: [.4, .8], rim: "#16202b", body: "#05070a", wa: 1, cols: 6, rows: 3, seed: 37, tall: .05, spire: 0 }
    ];
  }

  function City(cv) { this.cv = cv; this.ctx = cv.getContext("2d"); this.W = 0; this.H = 0; this.built = false; this.fixed = null; this.t0 = 0; this.raf = 0; this.on = false; this.last = 0; }

  City.prototype.build = function () {
    var cv = this.cv, W = Math.round(cv.clientWidth), H = Math.round(cv.clientHeight);
    if (W < 40 || H < 40) { this.built = false; return false; }
    var budget = COARSE ? 1.15e6 : 2.6e6;
    var dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(budget / (W * H))));
    this.W = W; this.H = H; this.dpr = dpr;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    var u = cl(W / 390, 1, 1.8), self = this, rnd = mul(7), L = [], roofs = [], bodies = [];
    var cf = cfgs(W, H, u), hy = H * .76;
    this.u = u; this.hy = hy; this.vpx = W * .5;
    for (var li = 0; li < cf.length; li++) {
      var c = cf[li], cwid = W + 2 * c.mx, dark = mk(cwid * dpr, H * dpr), lit = mk(cwid * dpr, H * dpr);
      var dx = dark.getContext("2d"), lx = lit.getContext("2d"); dx.scale(dpr, dpr); lx.scale(dpr, dpr);
      var r = mul(c.seed * 977 + W);
      if (c.ground) {
        var g = dx.createLinearGradient(0, hy, 0, H); g.addColorStop(0, "#0b1118"); g.addColorStop(1, "#05070a");
        dx.fillStyle = g; dx.fillRect(0, hy, cwid, H - hy);
        // street grid glow: avenues converge on the vanishing point, cross streets bunch toward the horizon
        var vx = cwid / 2, i, k, n = 16;
        lx.lineCap = "round";
        for (var pass = 0; pass < 2; pass++) {
          lx.strokeStyle = pass ? "rgba(255,176,104,.55)" : "rgba(255,150,80,.10)"; lx.lineWidth = pass ? 1 : 4.5 * u; lx.beginPath();
          for (i = -n; i <= n; i++) { var bx = vx + i * W * .105 * (1 + Math.abs(i) * .02); lx.moveTo(vx + i * 3 * u, hy); lx.lineTo(bx, H); }
          for (k = 1; k <= 10; k++) { var yy = hy + (H - hy) * Math.pow(k / 10, 2.1); lx.moveTo(0, yy); lx.lineTo(cwid, yy); }
          lx.stroke();
        }
        for (k = 1; k <= 10; k++) for (i = -n; i <= n; i++) {
          if (r() < .35) { var yy2 = hy + (H - hy) * Math.pow(k / 10, 2.1), bx2 = vx + i * 3 * u + (i * W * .105 * (1 + Math.abs(i) * .02) - i * 3 * u) * ((yy2 - hy) / (H - hy)); lx.fillStyle = "rgba(255,214,160," + (.35 + .5 * r()) + ")"; lx.fillRect(bx2 - 1, yy2 - 1, 2 * u * .8 + 1, 2); }
        }
        lx.globalCompositeOperation = "destination-in";
        var fg = lx.createLinearGradient(0, hy, 0, H); fg.addColorStop(0, "rgba(0,0,0,0)"); fg.addColorStop(.25, "rgba(0,0,0,.45)"); fg.addColorStop(1, "rgba(0,0,0,1)");
        lx.fillStyle = fg; lx.fillRect(0, 0, cwid, H); lx.globalCompositeOperation = "source-over";
      } else {
        dx.translate(c.mx, 0); lx.translate(c.mx, 0);
        var x = -c.mx + r() * c.maxW * .5, pal = [];
        for (i = 0; i < WARM.length; i++) pal.push("rgba(" + WARM[i] + "," + (c.wa * (.55 + .45 * (i % 3 === 0 ? 1 : .8))).toFixed(2) + ")");
        while (x < W + c.mx) {
          var w = c.minW + r() * (c.maxW - c.minW), dist = (x + w / 2) / W;
          var env = .62 + .55 * Math.exp(-Math.pow((dist - .4) / .3, 2)) + .12 * Math.sin(dist * 9 + c.seed);
          var h = H * (c.minH + (c.maxH - c.minH) * Math.pow(r(), 1.5)) * env; if (r() < c.tall) h *= 1.35;
          h = Math.min(h, H * .86);
          var top = c.base * H - h, rects = [[x, top, w, c.base * H - top + (li === 3 ? 20 : 4)]];
          if (r() < .38) { var w2 = w * (.5 + .25 * r()), h2 = h * (.1 + .12 * r()); rects.push([x + (w - w2) / 2, top - h2, w2, h2 + 1]); }
          var bp = c.lit[0] + (c.lit[1] - c.lit[0]) * r();
          for (var q = 0; q < rects.length; q++) {
            var R = rects[q];
            dx.fillStyle = c.body; dx.fillRect(R[0], R[1], R[2], R[3]);
            dx.fillStyle = c.rim; dx.fillRect(R[0], R[1], R[2], 1); dx.fillRect(R[0], R[1], 1, R[3]);
            var m = c.ww * 1.3, nc = Math.floor((R[2] - 2 * m + (c.sx - c.ww)) / c.sx), nr = Math.floor((R[3] - 2 * m + (c.sy - c.wh)) / c.sy);
            if (li === 3) nr = Math.min(nr, Math.floor((H * c.base - R[1] - 6) / c.sy));
            if (nc < 1 || nr < 1) continue;
            var ox = R[0] + (R[2] - (nc * c.sx - (c.sx - c.ww))) / 2, oy = R[1] + m;
            for (var rr = 0; rr < nr; rr++) {
              var rv = r(), pr = cl(bp * (rv < .18 ? 1.55 : rv < .42 ? .3 : 1), 0, .95), wy = oy + rr * c.sy;
              for (var cc = 0; cc < nc; cc++) {
                var wx = ox + cc * c.sx;
                dx.fillStyle = "rgba(78,98,118,.15)"; dx.fillRect(wx, wy, c.ww, c.wh);
                if (r() < pr) { lx.fillStyle = pal[(r() * pal.length) | 0]; lx.fillRect(wx, wy, c.ww, c.wh); }
              }
            }
          }
          if (c.spire && r() < c.spire && h > H * .3) { var sh = 14 * u + r() * 34 * u; dx.fillStyle = c.rim; dx.fillRect(x + w / 2, top - sh - (rects.length > 1 ? rects[1][3] : 0), 1, sh + 1); }
          if (li >= 2) {
            var tr = rects[rects.length - 1];
            if (tr[0] + tr[2] / 2 > W * .04 && tr[0] + tr[2] / 2 < W * .96 && tr[1] > H * .1) roofs.push({ l: li, x: tr[0] + tr[2] / 2, y: tr[1] - 1 });
            bodies.push({ l: li, x: R0(rects), y: rects[0][1], w: rects[0][2], h: Math.min(rects[0][3], H * c.base - rects[0][1]) });
          }
          x += w + c.gap[0] + r() * (c.gap[1] - c.gap[0]);
        }
      }
      // tiles: the unit the blackout switches off
      var tiles = [], cwd = cwid * dpr | 0, chd = H * dpr | 0, ti, tj;
      for (tj = 0; tj < c.rows; tj++) for (ti = 0; ti < c.cols; ti++) {
        var x0 = Math.floor(ti * cwd / c.cols), x1 = Math.floor((ti + 1) * cwd / c.cols), y0 = Math.floor(tj * chd / c.rows), y1 = Math.floor((tj + 1) * chd / c.rows);
        var cx = ((x0 + x1) / 2 / dpr - c.mx) / W, cy = ((y0 + y1) / 2 / dpr) / H, id = li * 100 + tj * 16 + ti;
        var h1 = hash(id, 1), h2 = hash(id, 2), h3 = hash(id, 3), ts;
        if (h1 < .3) ts = 3.3 + 2.0 * (1 - cl(cx, 0, 1)) + .6 * h2 + .25 * cy; else ts = 2.5 + 2.4 * cl(cx, 0, 1) + .6 * h2 + .25 * cy;
        tiles.push({ x0: x0, y0: y0, w: x1 - x0, h: y1 - y0, ts: ts, rs: 13.0 + .9 * h3, id: id, ph: h2 * 6.28 });
      }
      L.push({ c: c, dark: dark, lit: lit, tiles: tiles, mxd: Math.round(c.mx * dpr) });
    }
    function R0(rects) { return rects[0][0]; }
    this.L = L;
    // haze glow on the horizon
    var hz = mk(W * dpr, H * dpr), hx = hz.getContext("2d"); hx.scale(dpr, dpr);
    var hg = hx.createLinearGradient(0, hy - H * .34, 0, hy + H * .08); hg.addColorStop(0, "rgba(255,140,64,0)"); hg.addColorStop(.75, "rgba(255,150,76,.55)"); hg.addColorStop(1, "rgba(255,120,50,.2)");
    hx.fillStyle = hg; hx.fillRect(0, 0, W, H); this.haze = hz;
    // sky
    var sk = mk(4, H * dpr), sx = sk.getContext("2d"), sg = sx.createLinearGradient(0, 0, 0, H * dpr);
    sg.addColorStop(0, "rgba(5,8,12,0)"); sg.addColorStop(.55, "rgba(10,15,22,.85)"); sg.addColorStop(1, "rgba(14,20,29,.95)"); sx.fillStyle = sg; sx.fillRect(0, 0, 4, H * dpr); this.sky = sk;
    // halo sprite
    var hs = mk(64, 64), hc = hs.getContext("2d"), rg = hc.createRadialGradient(32, 32, 0, 32, 32, 32);
    rg.addColorStop(0, "rgba(190,240,255,.95)"); rg.addColorStop(.25, "rgba(110,215,255,.4)"); rg.addColorStop(1, "rgba(60,170,255,0)"); hc.fillStyle = rg; hc.fillRect(0, 0, 64, 64); this.halo = hs;
    this.mesh(roofs, bodies, rnd);
    this.built = true; return true;
  };

  City.prototype.par = function (li, t) { var a = this.L[li].c.amp; return Math.round(Math.sin(t / T * 6.2832) * a * this.dpr) / this.dpr; };

  City.prototype.mesh = function (roofs, bodies, rnd) {
    var W = this.W, H = this.H, u = this.u, area = W * H, N = cl(Math.round(area / (390 * 700) * 52), 40, 96), hy = this.hy, cand = [], i, j;
    for (i = 0; i < roofs.length; i++) cand.push({ l: roofs[i].l, x: roofs[i].x, y: roofs[i].y, k: "unit" });
    for (i = 0; i < bodies.length; i++) { var b = bodies[i]; if (b.h > 30 && b.w > 10) cand.push({ l: b.l, x: b.x + b.w * (.2 + .6 * rnd()), y: b.y + 10 + (b.h - 20) * rnd() * .8, k: "phone" }); }
    for (i = 0; i < 60; i++) cand.push({ l: 1, x: W * (.04 + .92 * rnd()), y: hy + (H - hy) * (.1 + .85 * rnd()), k: "phone" });
    for (i = cand.length - 1; i > 0; i--) { j = (rnd() * (i + 1)) | 0; var tmp = cand[i]; cand[i] = cand[j]; cand[j] = tmp; }
    var minD = Math.sqrt(area / N) * .66, nodes = [];
    for (i = 0; i < cand.length && nodes.length < N; i++) {
      var c = cand[i], ok = c.x > 8 && c.x < W - 8 && c.y > 28 && c.y < H - 8;
      for (j = 0; ok && j < nodes.length; j++) if (Math.hypot(nodes[j].x - c.x, nodes[j].y - c.y) < minD) ok = false;
      if (ok) nodes.push(c);
    }
    // seed: the node nearest the centre
    var s = 0, sd = 1e9; for (i = 0; i < nodes.length; i++) { var d = Math.hypot(nodes[i].x - W * .45, nodes[i].y - H * .55); if (d < sd) { sd = d; s = i; } }
    var n = nodes.length, E = [], seen = {}, maxD = minD * 2.5;
    function add(a, b) { var k = a < b ? a + "_" + b : b + "_" + a; if (seen[k] || a === b) return; seen[k] = 1; E.push({ a: a, b: b, len: Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) }); }
    for (i = 0; i < n; i++) {
      var ds = []; for (j = 0; j < n; j++) if (j !== i) ds.push([Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y), j]);
      ds.sort(function (p, q) { return p[0] - q[0]; });
      for (j = 0; j < 3 && j < ds.length; j++) if (ds[j][0] < maxD || j === 0) add(i, ds[j][1]);
    }
    // connect components
    var par = []; for (i = 0; i < n; i++) par[i] = i;
    function f(x) { while (par[x] !== x) { par[x] = par[par[x]]; x = par[x]; } return x; }
    for (i = 0; i < E.length; i++) par[f(E[i].a)] = f(E[i].b);
    for (var guard = 0; guard < n; guard++) {
      var best = null; for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) if (f(i) !== f(j)) { var dd = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y); if (!best || dd < best[0]) best = [dd, i, j]; }
      if (!best) break; add(best[1], best[2]); par[f(best[1])] = f(best[2]);
    }
    var adj = []; for (i = 0; i < n; i++) adj[i] = [];
    for (i = 0; i < E.length; i++) { adj[E[i].a].push(i); adj[E[i].b].push(i); }
    // Dijkstra from the seed on link length: node.on is when it joins; the tree edge that reached it grows from its parent
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
    this.nodes = nodes; this.E = E; this.adj = adj;
    // message packets hop node to node across the live mesh
    var P = [], flashes = [], r = mul(99), K = 20, spd = 120 * u;
    for (var k = 0; k < K; k++) {
      var st = 8.0 + k * .26 + r() * .2, act = []; for (i = 0; i < n; i++) if (nodes[i].on < st - .1) act.push(i);
      if (act.length < 3) continue;
      var a = act[(r() * act.length) | 0], q = [a], prev = {}, vis = {}; vis[a] = 1; var tgt = -1, tries = 0;
      // BFS over usable links, then walk to a node 3+ hops away
      var depth = {}; depth[a] = 0; var head = 0;
      while (head < q.length) { var cu = q[head++]; for (i = 0; i < adj[cu].length; i++) { var ee = E[adj[cu][i]]; if (ee.t1 > st) continue; var o2 = ee.a === cu ? ee.b : ee.a; if (vis[o2] || nodes[o2].on > st) continue; vis[o2] = 1; prev[o2] = cu; depth[o2] = depth[cu] + 1; q.push(o2); } }
      var far = q.filter(function (z) { return depth[z] >= 3; }); if (!far.length) far = q.filter(function (z) { return depth[z] >= 1; }); if (!far.length) continue;
      tgt = far[(r() * far.length) | 0]; var path = [tgt]; while (path[0] !== a) path.unshift(prev[path[0]]);
      var segs = [], tt = st;
      for (i = 0; i + 1 < path.length; i++) { var dl = Math.hypot(nodes[path[i]].x - nodes[path[i + 1]].x, nodes[path[i]].y - nodes[path[i + 1]].y) / spd + .05; segs.push({ a: path[i], b: path[i + 1], t0: tt, t1: tt + dl }); tt += dl; flashes.push({ t: tt, n: path[i + 1] }); }
      flashes.push({ t: st, n: a });
      P.push({ segs: segs, t0: st, t1: tt });
    }
    this.P = P; this.F = flashes;
  };

  City.prototype.pos = function (nd, t) { return { x: nd.x + this.par(nd.l, t), y: nd.y }; };

  City.prototype.light = function (tile, t) {
    var a;
    if (t < tile.ts) a = 1;
    else if (t < tile.ts + 1.1) { var p = (t - tile.ts) / 1.1, n = Math.floor((t - tile.ts) * 17); a = hash(tile.id, n + 5) > p * .95 ? (.55 + .45 * hash(tile.id, n + 9)) : .06; if (p > .9) a = RES; }
    else if (t < tile.rs) a = RES;
    else { var q = (t - tile.rs) / .5; a = RES + (1 - RES) * sm(q); if (q < 1 && hash(tile.id, Math.floor(t * 20)) < .25) a *= .5; }
    if (a > .5 && t < 2.5 || a === 1) a *= .96 + .04 * Math.sin(t * 1.9 + tile.ph);
    return a;
  };

  City.prototype.draw = function (t) {
    var ctx = this.ctx, W = this.W, H = this.H, dpr = this.dpr, cw = this.cv.width, ch = this.cv.height, i, j;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over"; ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(this.sky, 0, 0, 4, this.sky.height, 0, 0, cw, ch);
    var sum = 0, cnt = 0, li, L, tl, a, ox;
    for (li = 0; li < this.L.length; li++) {
      L = this.L[li]; ox = -L.mxd + Math.round(this.par(li, t) * dpr);
      ctx.globalAlpha = 1; ctx.drawImage(L.dark, ox, 0);
      for (j = 0; j < L.tiles.length; j++) {
        tl = L.tiles[j]; a = this.light(tl, t); if (li === 2) { sum += a; cnt++; }
        if (a < .01) continue;
        ctx.globalAlpha = a; ctx.drawImage(L.lit, tl.x0, tl.y0, tl.w, tl.h, ox + tl.x0, tl.y0, tl.w, tl.h);
      }
      if (li === 0) { ctx.globalAlpha = 1; }
    }
    var avg = cnt ? sum / cnt : 1;
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = .55 * avg; ctx.drawImage(this.haze, 0, 0); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.drawMesh(t);
    this.scrim(); this.fade(); this.caption(t);
  };

  City.prototype.drawMesh = function (t) {
    var ctx = this.ctx, nodes = this.nodes, E = this.E, u = this.u, i, j, ma = t > 12.9 ? 1 - sm((t - 12.9) / 1.0) : 1;
    if (t < 6.8 || ma <= 0.01) return;
    var pos = [], nd; for (i = 0; i < nodes.length; i++) pos.push(this.pos(nodes[i], t));
    ctx.globalAlpha = ma; ctx.lineCap = "round";
    // links: grown from the node that reached them; extra mesh links fade in afterwards
    var pass, e, p, A, B, x2, y2;
    for (pass = 0; pass < 2; pass++) {
      ctx.strokeStyle = pass ? "rgba(214,247,255,.55)" : "rgba(90,200,255,.12)"; ctx.lineWidth = pass ? 1 : 3.2; ctx.beginPath();
      for (i = 0; i < E.length; i++) {
        e = E[i]; if (t < e.t0) continue; p = e.tree ? sm((t - e.t0) / Math.max(.05, e.t1 - e.t0)) : 1; if (!e.tree && pass) { }
        A = pos[e.from]; B = pos[e.to]; x2 = A.x + (B.x - A.x) * p; y2 = A.y + (B.y - A.y) * p;
        if (!e.tree) { if (t < e.t1) continue; }
        ctx.moveTo(A.x, A.y); ctx.lineTo(x2, y2);
      }
      ctx.stroke();
    }
    // extra links fade in
    ctx.strokeStyle = "rgba(190,240,255,.35)"; ctx.lineWidth = 1;
    for (i = 0; i < E.length; i++) { e = E[i]; if (e.tree || t < e.t0 || t >= e.t1) continue; ctx.globalAlpha = ma * sm((t - e.t0) / (e.t1 - e.t0)); A = pos[e.from]; B = pos[e.to]; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke(); }
    ctx.globalAlpha = ma;
    // nodes: halo + one-time pulse ring, then phone or rooftop unit
    ctx.globalCompositeOperation = "lighter";
    for (i = 0; i < nodes.length; i++) {
      nd = nodes[i]; var dt = t - nd.on; if (dt < 0) continue; p = pos[i]; var a = sm(dt / .35), hs = (14 + 6 * Math.min(u, 1.4));
      ctx.globalAlpha = ma * a * .7; ctx.drawImage(this.halo, p.x - hs / 2, p.y - hs / 2, hs, hs);
      if (dt < 1.1) { ctx.globalAlpha = ma * (1 - dt / 1.1) * .8; ctx.strokeStyle = "rgba(170,235,255,1)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(p.x, p.y, 3 + dt * 20 * Math.min(u, 1.4), 0, 6.2832); ctx.stroke(); }
    }
    // hop flashes
    var F = this.F; for (i = 0; i < F.length; i++) { var df = t - F[i].t; if (df < 0 || df > .55) continue; p = pos[F[i].n]; var fs = 18 + df * 30; ctx.globalAlpha = ma * (1 - df / .55) * .9; ctx.drawImage(this.halo, p.x - fs / 2, p.y - fs / 2, fs, fs); }
    ctx.globalCompositeOperation = "source-over";
    var s = Math.min(u, 1.4);
    for (i = 0; i < nodes.length; i++) {
      nd = nodes[i]; if (t < nd.on) continue; p = pos[i]; ctx.globalAlpha = ma * sm((t - nd.on) / .3); ctx.fillStyle = "#eefcff"; ctx.strokeStyle = "rgba(220,248,255,.9)";
      if (nd.k === "unit") { ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x, p.y - 6 * s); ctx.stroke(); ctx.beginPath(); ctx.arc(p.x, p.y - 6 * s, 1.1 * s, 0, 6.2832); ctx.fill(); ctx.fillRect(p.x - 2 * s, p.y - .5, 4 * s, 2 * s); }
      else { var pw = 2.6 * s, ph = 4.6 * s; ctx.fillRect(p.x - pw / 2, p.y - ph / 2, pw, ph); ctx.fillStyle = "#4fc3f7"; ctx.fillRect(p.x - pw / 2 + .5, p.y - ph / 2 + .7, pw - 1, ph - 1.9); }
    }
    // packets
    ctx.globalCompositeOperation = "lighter";
    for (i = 0; i < this.P.length; i++) {
      var pk = this.P[i]; if (t < pk.t0 || t > pk.t1 + .3) continue;
      for (j = 0; j < pk.segs.length; j++) {
        var sg = pk.segs[j]; if (t < sg.t0 || t > sg.t1) continue;
        var q = (t - sg.t0) / (sg.t1 - sg.t0), A2 = pos[sg.a], B2 = pos[sg.b], hx = A2.x + (B2.x - A2.x) * q, hy2 = A2.y + (B2.y - A2.y) * q, q0 = Math.max(0, q - .35), tx = A2.x + (B2.x - A2.x) * q0, ty = A2.y + (B2.y - A2.y) * q0;
        var gr = ctx.createLinearGradient(tx, ty, hx, hy2); gr.addColorStop(0, "rgba(120,220,255,0)"); gr.addColorStop(1, "rgba(235,252,255,.95)");
        ctx.globalAlpha = ma; ctx.strokeStyle = gr; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy2); ctx.stroke();
        ctx.globalAlpha = ma * .9; ctx.drawImage(this.halo, hx - 6, hy2 - 6, 12, 12);
        ctx.globalAlpha = ma; ctx.fillStyle = "#fff"; ctx.fillRect(hx - 1.2, hy2 - 1.2, 2.4, 2.4);
      }
    }
    ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
  };

  City.prototype.scrim = function () {
    var ctx = this.ctx, W = this.W, H = this.H;
    if (W >= 900) { var g = ctx.createLinearGradient(W * .38, 0, W * .86, 0); g.addColorStop(0, "rgba(4,6,9,0)"); g.addColorStop(1, "rgba(4,6,9,.55)"); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
    else { ctx.fillStyle = "rgba(4,6,9,.18)"; ctx.fillRect(0, 0, W, H); }
  };

  // soften the canvas edges so the city melts into the menu instead of ending in a hard rectangle
  City.prototype.fade = function () {
    var ctx = this.ctx, W = this.W, H = this.H, f = Math.min(44 * this.u, W * .12), g;
    ctx.globalCompositeOperation = "destination-out";
    g = ctx.createLinearGradient(0, 0, f, 0); g.addColorStop(0, "rgba(0,0,0,1)"); g.addColorStop(1, "rgba(0,0,0,0)"); ctx.fillStyle = g; ctx.fillRect(0, 0, f, H);
    g = ctx.createLinearGradient(W - f, 0, W, 0); g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,1)"); ctx.fillStyle = g; ctx.fillRect(W - f, 0, f, H);
    g = ctx.createLinearGradient(0, H - f * .8, 0, H); g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,1)"); ctx.fillStyle = g; ctx.fillRect(0, H - f * .8, W, f * .8);
    ctx.globalCompositeOperation = "source-over";
  };

  City.prototype.caption = function (t) {
    var ctx = this.ctx, txt = "", col = "rgba(200,210,220,", al = 1, mark = 0, i;
    if (t < 2.4) { txt = "GRID ONLINE"; al = sm(t / .4) * (1 - sm((t - 2.1) / .3)); mark = 1; }
    else if (t < 6.8) { txt = "GRID DOWN"; al = sm((t - 2.8) / .3) * (1 - sm((t - 6.5) / .3)); mark = 2; if (t < 2.8) al = 0; }
    else if (t < 12.9) {
      var full = "blackout.network activated", k = Math.floor(clamp01((t - 7.0) / 1.1) * full.length); txt = full.slice(0, k); mark = 3; col = "rgba(190,238,255,";
      al = sm((t - 6.9) / .2) * (1 - sm((t - 12.6) / .3));
    } else { txt = "GRID RESTORED"; al = sm((t - 13.0) / .3) * (1 - sm((t - 14.1) / .3)); mark = 1; }
    function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
    if (al <= .01 || !txt) return;
    var u = Math.min(this.u, 1.3), fs = 10 * u, x = 18, y = 26;
    ctx.font = "600 " + fs.toFixed(1) + "px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"; ctx.textBaseline = "middle"; ctx.globalAlpha = al;
    ctx.fillStyle = mark === 1 ? "rgba(255,206,150,.95)" : mark === 2 ? "rgba(150,160,172,.9)" : "rgba(140,226,255,.95)";
    if (mark === 2) { ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = 1; ctx.strokeRect(x + .5, y - 3.5, 7, 7); } else ctx.fillRect(x, y - 4, 8, 8);
    ctx.fillStyle = col + ".95)"; var cx = x + 17, sp = 1.6 * u;
    for (i = 0; i < txt.length; i++) { ctx.fillText(txt[i], cx, y); cx += ctx.measureText(txt[i]).width + sp; }
    if (mark === 2 && Math.floor(t * 2.5) % 2 === 0) ctx.fillRect(cx + 1, y - 5, 5 * u, 10 * u * .9);
    ctx.globalAlpha = 1;
  };

  City.prototype.frame = function (now) {
    if (!this.on) return; var self = this;
    this.raf = requestAnimationFrame(function (n) { self.frame(n); });
    if (COARSE && now - this.last < 31) return; this.last = now;
    if (!this.built && !this.build()) return;
    var t = this.fixed != null ? this.fixed : ((now - this.t0) / 1000) % T;
    this.draw(t);
  };
  City.prototype.start = function () { if (this.on) return; this.on = true; this.t0 = performance.now(); this.last = 0; var self = this; this.raf = requestAnimationFrame(function (n) { self.frame(n); }); };
  City.prototype.stop = function () { this.on = false; if (this.raf) cancelAnimationFrame(this.raf); this.raf = 0; };
  City.prototype.still = function () { if (!this.built && !this.build()) return; this.draw(this.fixed != null ? this.fixed : STATIC_T); };

  var all = [];
  function inMenu(cv) { var m = cv.closest("#bn-menu,#h_menu,#w2_menu"); return m; }
  function menuOpen(cv) { var m = inMenu(cv); return m ? m.matches(MENUS) : true; }
  function sync(c) {
    var want = !document.hidden && menuOpen(c.cv) && c.vis !== false;
    if (RM) { if (want) c.still(); return; }
    if (want) c.start(); else c.stop();
  }
  function init(cv) {
    if (cv.__bnCity) return; var c = cv.__bnCity = new City(cv); all.push(c);
    var m = inMenu(cv);
    if (m && window.MutationObserver) new MutationObserver(function () { sync(c); }).observe(m, { attributes: true, attributeFilter: ["class", "hidden"] });
    if (window.ResizeObserver) { var tm; new ResizeObserver(function () { clearTimeout(tm); tm = setTimeout(function () { c.built = false; if (!c.on && menuOpen(cv) && !document.hidden) { if (RM) c.still(); } }, 120); }).observe(cv); }
    if (window.IntersectionObserver) new IntersectionObserver(function (es) { c.vis = es[es.length - 1].isIntersecting; sync(c); }).observe(cv);
    sync(c);
  }
  function scan() { var l = document.querySelectorAll("canvas.m5-city"); for (var i = 0; i < l.length; i++) init(l[i]); }
  document.addEventListener("visibilitychange", function () { for (var i = 0; i < all.length; i++) sync(all[i]); });
  window.__bnCity = { all: all, scan: scan, T: T, freeze: function (t) { for (var i = 0; i < all.length; i++) { all[i].fixed = t; all[i].stop(); all[i].built = all[i].built; all[i].still(); } } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan); else scan();
})();
