/* BLACKOUT.NETWORK menu animation: a massive night city, the lights go out block by block, people switch on flashlights,
   then a peer-to-peer mesh of phones, windows and rooftop units comes online. A calm loop that keeps living afterwards.
   Original, code-rendered canvas (no images, no libraries). Loop 25 s. Lazy-loaded by menu5.py the first time a menu opens.
   Smoothness: the scene is built in small slices across animation frames (no long task when the menu opens), the old frame keeps
   drawing while a resize rebuilds, buildings and windows are baked once into canvases (a frame is a few blits plus a handful of
   small sprites), per-frame work allocates nothing, the caption is cached, 60 fps with an automatic step down to 30 fps if frames
   run long. DPR <= 2 and a pixel budget. Pauses when the menu is closed or the tab is hidden; prefers-reduced-motion draws one
   static frame. The canvas is pointer-events:none and sits behind the menu links.
   Every mesh node is anchored to a lit window, a rooftop unit or a person, drawn and not hidden behind a nearer building. */
(function () {
  "use strict";
  if (window.__bnCity) return;
  var T = 25, RES = 0.03, STATIC_T = 16.5;
  var BOOM = 11.6, MESH0 = 11.75, MESHSPAN = 4.3, MESHEND = 21.2;
  var RM = false;
  try { RM = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  var COARSE = false; try { COARSE = matchMedia("(pointer: coarse)").matches; } catch (e) {}
  var MENUS = "#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])";
  var TAU = 6.2832;

  function mul(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function hash(a, b) { var h = Math.imul(a ^ 0x9E3779B1, 0x85EBCA6B) ^ Math.imul(b + 0x7F4A7C15, 0xC2B2AE35); h ^= h >>> 13; h = Math.imul(h, 0x27D4EB2F); h ^= h >>> 15; return (h >>> 0) / 4294967296; }
  function sm(x) { x = x < 0 ? 0 : x > 1 ? 1 : x; return x * x * (3 - 2 * x); }
  function cl(x, a, b) { return x < a ? a : x > b ? b : x; }
  function fr(x) { return x - Math.floor(x); }
  function vn(a, x) { var i = Math.floor(x), f = sm(x - i); return hash(a, i) * (1 - f) + hash(a, i + 1) * f; }
  function mk(w, h) { var c = document.createElement("canvas"); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; }

  var WARM = ["255,214,150", "255,196,128", "255,228,186", "255,170,100", "250,238,218", "255,205,140", "255,182,112", "206,228,255"];

  // building layers, far to near (the ground is drawn between "far" and "mid2")
  function cfgs(u) {
    return [
      { base: .70, minW: 5 * u, maxW: 12 * u, minH: .08, maxH: .25, gap: [0, 1 * u], ww: .9 * u, wh: 1.2 * u, sx: 2 * u, sy: 2.8 * u, lit: [.2, .5], rim: "#2a3d55", g0: "#16243a", g1: "#233650", wa: .4, seed: 3, tall: .03, spire: .05, ds: .5, deco: .3 },
      { base: .74, minW: 7 * u, maxW: 16 * u, minH: .14, maxH: .44, gap: [0, 2 * u], ww: 1.2 * u, wh: 1.7 * u, sx: 2.6 * u, sy: 3.6 * u, lit: [.45, .8], rim: "#2a3b52", g0: "#0e1827", g1: "#1b2c42", wa: .72, seed: 11, tall: .05, spire: .12, ds: .7, deco: .38 },
      { ground: true },
      { base: .79, minW: 10 * u, maxW: 24 * u, minH: .2, maxH: .56, gap: [0, 3 * u], ww: 1.7 * u, wh: 2.4 * u, sx: 3.6 * u, sy: 5 * u, lit: [.5, .88], rim: "#2a3b52", g0: "#09101a", g1: "#142136", wa: .92, seed: 17, tall: .06, spire: .1, ds: .85, deco: .42, anchor: 1 },
      { base: .82, minW: 14 * u, maxW: 34 * u, minH: .2, maxH: .62, gap: [2 * u, 12 * u], ww: 2.1 * u, wh: 2.9 * u, sx: 4.4 * u, sy: 6 * u, lit: [.5, .88], rim: "#22303f", g0: "#070b12", g1: "#101a28", wa: 1, seed: 23, tall: .08, spire: .1, ds: 1, deco: .42, anchor: 1 },
      { base: 1.04, minW: 34 * u, maxW: 80 * u, minH: .22, maxH: .56, gap: [70 * u, 220 * u], ww: 3 * u, wh: 4.4 * u, sx: 7 * u, sy: 10 * u, lit: [.4, .8], rim: "#1a2634", g0: "#04060a", g1: "#090d14", wa: 1, seed: 37, tall: .05, spire: 0, ds: 1.3, deco: .5, anchor: 1, near: 1 }
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

  function sprite(sz, stops) {
    var c = mk(sz, sz), x = c.getContext("2d"), g = x.createRadialGradient(sz / 2, sz / 2, 0, sz / 2, sz / 2, sz / 2);
    for (var i = 0; i < stops.length; i++) g.addColorStop(stops[i][0], stops[i][1]);
    x.fillStyle = g; x.fillRect(0, 0, sz, sz); return c;
  }

  // roof furniture, drawn into the baked skyline: antennas, water towers, roof boxes, dishes, crowns
  function roofDeco(dx, c, x, w, top, u, r, out) {
    var ds = c.ds, p = r(), mx, hg, tw, th, k;
    if (p < .24) {
      mx = Math.round(x + w * (.2 + .6 * r())); hg = (9 + r() * 26) * u * ds;
      dx.fillStyle = c.rim; dx.fillRect(mx, top - hg, Math.max(1, ds > .8 ? 1 : .8), hg + 1);
      dx.fillRect(mx - 2 * ds, top - hg * .78, 5 * ds, 1); dx.fillRect(mx - 1.4 * ds, top - hg * .56, 3.4 * ds, 1);
      if (hg > 14 * u * ds) out.push({ x: mx + .5, y: top - hg, ph: r() * TAU, k: 1 + ((r() * 3) | 0), l: c.idx });
    } else if (p < .38 && w > 9 * u * ds) {
      tw = Math.min(w * .55, 9 * u * ds); th = tw * .85; mx = x + (w - tw) / 2 + (r() - .5) * w * .15;
      dx.fillStyle = c.rim; dx.fillRect(mx + tw * .15, top - th * .55, 1, th * .55 + 1); dx.fillRect(mx + tw * .85 - 1, top - th * .55, 1, th * .55 + 1);
      dx.fillStyle = c.g1; dx.fillRect(mx, top - th * 1.45, tw, th * .9); dx.fillStyle = c.rim; dx.fillRect(mx, top - th * 1.45, tw, 1); dx.fillRect(mx, top - th * 1.45, 1, th * .9);
      dx.fillStyle = c.g1; dx.beginPath(); dx.moveTo(mx - 1, top - th * 1.45); dx.lineTo(mx + tw / 2, top - th * 1.95); dx.lineTo(mx + tw + 1, top - th * 1.45); dx.closePath(); dx.fill();
      dx.strokeStyle = c.rim; dx.lineWidth = 1; dx.beginPath(); dx.moveTo(mx - 1, top - th * 1.45); dx.lineTo(mx + tw / 2, top - th * 1.95); dx.lineTo(mx + tw + 1, top - th * 1.45); dx.stroke();
    } else if (p < .6) {
      k = 1 + ((r() * 3) | 0); mx = x + w * .12;
      for (var i = 0; i < k; i++) { var bw = (3 + r() * 5) * u * ds, bh = (2 + r() * 3) * u * ds; dx.fillStyle = c.g1; dx.fillRect(mx, top - bh, bw, bh + 1); dx.fillStyle = c.rim; dx.fillRect(mx, top - bh, bw, 1); mx += bw + (1 + r() * 4) * u * ds; if (mx > x + w - 3) break; }
    } else if (p < .72) {
      mx = x + w * (.3 + .4 * r()); hg = (3 + r() * 3) * u * ds;
      dx.strokeStyle = c.rim; dx.lineWidth = 1; dx.beginPath(); dx.arc(mx, top - hg, hg, Math.PI * 1.15, Math.PI * 1.95); dx.stroke(); dx.fillStyle = c.rim; dx.fillRect(mx, top - hg, 1, hg + 1);
    } else if (p < .84 && w > 8 * u * ds) {
      dx.fillStyle = c.g1; dx.fillRect(x + w * .1, top - 3 * u * ds, w * .8, 3 * u * ds + 1); dx.fillStyle = c.rim; dx.fillRect(x + w * .1, top - 3 * u * ds, w * .8, 1);
    }
  }

  City.prototype.gen = function* (W, H, dpr) {
    var u = cl(W / 390, 1, 1.8), cf = cfgs(u), hy = H * .76, ys = Math.floor(hy - 16 * u), i, j, rects = [], roofs = [], wins = [], anim = [], avi = [], S, gi = 0;
    var base = mk(W * dpr, H * dpr), lit = mk(W * dpr, H * dpr);
    var dyn = mk(W * dpr, (H - ys) * dpr), occ = mk(W * dpr, (H - ys) * dpr);
    var dx = base.getContext("2d"), lx = lit.getContext("2d"), ox = occ.getContext("2d");
    dx.scale(dpr, dpr); lx.scale(dpr, dpr); ox.scale(dpr, dpr); ox.translate(0, -ys);
    S = { W: W, H: H, dpr: dpr, u: u, hy: hy, ys: ys, rects: rects, base: base, lit: lit, dyn: dyn, occ: occ, dctx: dyn.getContext("2d") };
    // night sky: deep blue, a faint violet and teal glow, a pale band above the skyline
    var g = dx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, "#02040a"); g.addColorStop(.4, "#06101f"); g.addColorStop(.7, "#10203a"); g.addColorStop(.8, "#162a47"); g.addColorStop(1, "#0a111d");
    dx.fillStyle = g; dx.fillRect(0, 0, W, H);
    var bl = [[W * .18, H * .26, W * .9, "70,48,130", .16], [W * .82, H * .36, W * .85, "26,120,150", .12], [W * .5, hy - H * .06, W * .8, "80,110,180", .12]];
    for (i = 0; i < bl.length; i++) { var b = bl[i], rg = dx.createRadialGradient(b[0], b[1], 0, b[0], b[1], b[2]); rg.addColorStop(0, "rgba(" + b[3] + "," + b[4] + ")"); rg.addColorStop(1, "rgba(" + b[3] + ",0)"); dx.fillStyle = rg; dx.fillRect(0, 0, W, H); }
    var rs = mul(41), ns = cl(Math.round(W * H / (390 * 844) * 150), 90, 280), stars = [];
    for (i = 0; i < ns; i++) { var sy2 = Math.pow(rs(), 1.35) * hy * .93, bt = .35 + .65 * rs(); stars.push({ x: rs() * W, y: sy2, r: (.5 + rs() * .8) * (bt > .85 ? 1.3 : 1), b: bt * (1 - .65 * sy2 / hy), ph: rs() * TAU, k: 1 + ((rs() * 4) | 0), par: .25 + rs() * .5, c: rs() < .2 ? "170,205,255" : rs() < .35 ? "255,226,190" : "235,242,255" }); }
    for (i = 0; i < stars.length; i++) { var st0 = stars[i]; dx.globalAlpha = st0.b * .55; dx.fillStyle = "rgb(" + st0.c + ")"; dx.fillRect(st0.x - st0.r / 2, st0.y - st0.r / 2, st0.r, st0.r); }
    dx.globalAlpha = 1; S.stars = stars;
    yield;
    var warmS = sprite(32, [[0, "rgba(255,226,180,1)"], [.2, "rgba(255,190,120,.55)"], [1, "rgba(255,150,70,0)"]]);
    for (var li = 0; li < cf.length; li++) {
      var c = cf[li], lr = []; rects[li] = lr; c.idx = li;
      if (c.ground) {
        gi = li;
        var gg = dx.createLinearGradient(0, hy, 0, H); gg.addColorStop(0, "#0d1520"); gg.addColorStop(1, "#05070a");
        dx.fillStyle = gg; dx.fillRect(0, hy, W, H - hy);
        var gl = mk(W * dpr, H * dpr), gx = gl.getContext("2d"), r5 = mul(5 + W); gx.scale(dpr, dpr);
        var vx = W / 2, n = 16, kk;
        gx.lineCap = "round";
        for (var pass = 0; pass < 2; pass++) {
          gx.strokeStyle = pass ? "rgba(255,176,104,.5)" : "rgba(255,150,80,.09)"; gx.lineWidth = pass ? 1 : 4.5 * u; gx.beginPath();
          for (i = -n; i <= n; i++) { var bx = vx + i * W * .105 * (1 + Math.abs(i) * .02); gx.moveTo(vx + i * 3 * u, hy); gx.lineTo(bx, H); }
          for (kk = 1; kk <= 10; kk++) { var yy = hy + (H - hy) * Math.pow(kk / 10, 2.1); gx.moveTo(0, yy); gx.lineTo(W, yy); }
          gx.stroke();
        }
        // street lamps: warm pools along the streets
        for (kk = 3; kk <= 10; kk++) {
          var ly = hy + (H - hy) * Math.pow((kk - .45) / 10, 2.1), sc = (ly - hy) / (H - hy), step = (46 + 120 * sc) * u, lxp = r5() * step;
          while (lxp < W + 20) { var ps = (20 + 90 * sc) * u; gx.globalAlpha = .55 + .3 * r5(); gx.drawImage(warmS, lxp - ps / 2, ly - ps * .22, ps, ps * .44); gx.globalAlpha = .9; gx.fillStyle = "rgba(255,238,205,1)"; gx.fillRect(lxp - .6, ly - .6, 1.4 + sc, 1.4 + sc); lxp += step * (.8 + .4 * r5()); }
        }
        gx.globalAlpha = 1;
        gx.globalCompositeOperation = "destination-in";
        var fg = gx.createLinearGradient(0, hy, 0, H); fg.addColorStop(0, "rgba(0,0,0,0)"); fg.addColorStop(.25, "rgba(0,0,0,.45)"); fg.addColorStop(1, "rgba(0,0,0,1)");
        gx.fillStyle = fg; gx.fillRect(0, 0, W, H);
        lx.setTransform(1, 0, 0, 1, 0, 0); lx.drawImage(gl, 0, 0); lx.setTransform(dpr, 0, 0, dpr, 0, 0);
        yield;
      } else {
        var r = mul(c.seed * 977 + W), rr2 = mul(c.seed * 31 + 5), x = -c.maxW * .5 + r() * c.maxW * .5, pal = [], cnt = 0, keep = c.near ? .5 : .3;
        for (i = 0; i < WARM.length; i++) pal.push("rgba(" + WARM[i] + "," + (c.wa * (.55 + .45 * (i % 3 === 0 ? 1 : .8))).toFixed(2) + ")");
        var bg = dx.createLinearGradient(0, H * .05, 0, c.base * H); bg.addColorStop(0, c.g0); bg.addColorStop(1, c.g1);
        while (x < W + 4) {
          var w = c.minW + r() * (c.maxW - c.minW), dist = (x + w / 2) / W;
          var env = .62 + .55 * Math.exp(-Math.pow((dist - .4) / .3, 2)) + .12 * Math.sin(dist * 9 + c.seed);
          var h = H * (c.minH + (c.maxH - c.minH) * Math.pow(r(), 1.5)) * env; if (r() < c.tall) h *= 1.35;
          h = Math.min(h, H * .86);
          var top = c.base * H - h, rects2 = [[x, top, w, c.base * H - top + (c.near ? 20 : 4)]];
          if (r() < .4) { var w2 = w * (.5 + .25 * r()), h2 = h * (.1 + .12 * r()); rects2.push([x + (w - w2) / 2, top - h2, w2, h2 + 1]); }
          var bp = c.lit[0] + (c.lit[1] - c.lit[0]) * r();
          for (var q = 0; q < rects2.length; q++) {
            var R = rects2[q];
            dx.fillStyle = bg; dx.fillRect(R[0], R[1], R[2], R[3]);
            dx.fillStyle = c.rim; dx.fillRect(R[0], R[1], R[2], 1); dx.fillRect(R[0], R[1], 1, R[3]);
            lx.globalCompositeOperation = "destination-out"; lx.fillStyle = "#000"; lx.fillRect(R[0], R[1], R[2], R[3]); lx.globalCompositeOperation = "source-over";
            lr.push(R);
            if (c.anchor && q === rects2.length - 1 && R[0] + R[2] / 2 > W * .03 && R[0] + R[2] / 2 < W * .97 && R[1] > H * .08 && R[2] >= 8 * u) roofs.push({ l: li, x: R[0] + R[2] / 2, y: R[1] });
            var m = c.ww * 1.3, nc = Math.floor((R[2] - 2 * m + (c.sx - c.ww)) / c.sx), nr = Math.floor((R[3] - 2 * m + (c.sy - c.wh)) / c.sy);
            if (c.near) nr = Math.min(nr, Math.floor((H * c.base - R[1] - 6) / c.sy));
            if (nc < 1 || nr < 1) continue;
            var ox0 = R[0] + (R[2] - (nc * c.sx - (c.sx - c.ww))) / 2, oy = R[1] + m;
            for (var row = 0; row < nr; row++) {
              var rv = r(), pr = cl(bp * (rv < .18 ? 1.55 : rv < .42 ? .3 : 1), 0, .95), wy = oy + row * c.sy;
              for (var cc = 0; cc < nc; cc++) {
                var wx = ox0 + cc * c.sx;
                dx.fillStyle = "rgba(78,98,118,.14)"; dx.fillRect(wx, wy, c.ww, c.wh);
                if (r() < pr) {
                  var pc = (r() * pal.length) | 0;
                  if (c.anchor && rr2() < .02 && anim.length < 90) { anim.push({ x: wx, y: wy, w: c.ww, h: c.wh, col: pal[pc], ph: r() * TAU, k: 1 + ((r() * 3) | 0) }); continue; }
                  lx.fillStyle = pal[pc]; lx.fillRect(wx, wy, c.ww, c.wh);
                  if (c.anchor && rr2() < keep) wins.push({ l: li, x: wx + c.ww / 2, y: wy + c.wh / 2 });
                }
              }
            }
          }
          var Rt = rects2[rects2.length - 1];
          if (c.spire && r() < c.spire && h > H * .28) { var sh = 14 * u + r() * 34 * u; dx.fillStyle = c.rim; dx.fillRect(x + w / 2, top - sh - (rects2.length > 1 ? rects2[1][3] : 0), 1, sh + 1); if (sh > 24 * u) avi.push({ x: x + w / 2 + .5, y: top - sh - (rects2.length > 1 ? rects2[1][3] : 0), ph: r() * TAU, k: 1 + ((r() * 3) | 0), l: li }); }
          else if (r() < c.deco) roofDeco(dx, c, Rt[0], Rt[2], Rt[1], u, r, avi);
          x += w + c.gap[0] + r() * (c.gap[1] - c.gap[0]);
          if ((++cnt & 3) === 0) yield;
        }
        yield;
      }
    }
    S.stars = stars.filter(function (q0) { return q0.y > 4 && !hidden(S, -1, q0.x, q0.y); }).slice(0, 110); S.gi = gi; S.avi = avi.filter(function (a) { return a.y > H * .06 && a.x > 6 && a.x < W - 6 && !hidden(S, a.l, a.x, a.y - 1); }).slice(0, 14); S.anim = anim;
    // occluders for street level things: every building that stands in front of the street
    ox.fillStyle = "#000";
    for (li = gi + 1; li < rects.length; li++) for (j = 0; j < rects[li].length; j++) { var Q = rects[li][j]; ox.fillRect(Q[0], Q[1], Q[2], Q[3]); }
    // tile grid: the unit the blackout switches off, grouped into irregular city blocks that go dark in turn
    var cols = cl(Math.round(W / 46), 8, 28), rows = cl(Math.round(H / 105), 6, 10), tiles = [], cwd = base.width, chd = base.height, ti, tj;
    var rb = mul(1234 + (W | 0)), seeds = [], nbx = W / H > .9 ? 5 : 3, nby = W / H > .9 ? 2 : 3, ord = [];
    for (tj = 0; tj < nby; tj++) for (ti = 0; ti < nbx; ti++) seeds.push({ x: (ti + .5 + (rb() - .5) * .7) * W / nbx, y: (tj + .5 + (rb() - .5) * .7) * H / nby });
    while (seeds.length < 10) seeds.push({ x: rb() * W, y: rb() * H });
    for (i = 0; i < seeds.length; i++) ord.push(i);
    for (i = ord.length - 1; i > 0; i--) { j = (rb() * (i + 1)) | 0; var zz = ord[i]; ord[i] = ord[j]; ord[j] = zz; }
    for (i = 0; i < ord.length; i++) seeds[ord[i]].t = 3.9 + i * .82 + rb() * .12;
    for (tj = 0; tj < rows; tj++) for (ti = 0; ti < cols; ti++) {
      var x0 = Math.floor(ti * cwd / cols), x1 = Math.floor((ti + 1) * cwd / cols), y0 = Math.floor(tj * chd / rows), y1 = Math.floor((tj + 1) * chd / rows);
      var cx = ((x0 + x1) / 2 / dpr), cy = ((y0 + y1) / 2 / dpr), id = tj * 40 + ti, bi = 0, bd = 1e12;
      for (i = 0; i < seeds.length; i++) { var dd = Math.pow(seeds[i].x - cx, 2) + Math.pow((seeds[i].y - cy) * .8, 2); if (dd < bd) { bd = dd; bi = i; } }
      var h1 = hash(id, 1), h2b = hash(id, 2), h3 = hash(id, 3);
      tiles.push({ x0: x0, y0: y0, w: x1 - x0, h: y1 - y0, ts: seeds[bi].t + h1 * .3, rs: 21.5 + 1.3 * (cx / W) + .5 * h3, id: id, ph: h2b * TAU });
    }
    yield;
    S.tiles = tiles; S.cols = cols; S.rows = rows; S.ta = new Float32Array(tiles.length);
    var hc0 = dx.createLinearGradient(0, hy - H * .34, 0, hy + H * .08); hc0.addColorStop(0, "rgba(255,140,64,0)"); hc0.addColorStop(.75, "rgba(255,150,76,.5)"); hc0.addColorStop(1, "rgba(255,120,50,.18)");
    S.hazeG = hc0; S.hazeY = hy - H * .34; S.hazeH = H * .42;
    var cg = dx.createLinearGradient(0, hy - H * .3, 0, H); cg.addColorStop(0, "rgba(80,190,255,0)"); cg.addColorStop(.7, "rgba(80,190,255,.16)"); cg.addColorStop(1, "rgba(80,190,255,.08)");
    S.coolG = cg;
    S.halo = sprite(64, [[0, "rgba(190,240,255,.95)"], [.25, "rgba(110,215,255,.4)"], [1, "rgba(60,170,255,0)"]]);
    S.hw = sprite(48, [[0, "rgba(255,248,230,1)"], [.2, "rgba(255,236,190,.6)"], [1, "rgba(255,210,140,0)"]]);
    S.hr = sprite(48, [[0, "rgba(255,150,130,1)"], [.2, "rgba(255,50,40,.6)"], [1, "rgba(255,20,10,0)"]]);
    S.hv = sprite(32, [[0, "rgba(255,170,160,1)"], [.3, "rgba(255,60,50,.5)"], [1, "rgba(255,30,20,0)"]]);
    var cn = mk(96, 48), cx2 = cn.getContext("2d");
    cx2.save(); cx2.translate(0, 24); cx2.scale(1, .5);
    var cr = cx2.createRadialGradient(0, 0, 1, 0, 0, 96); cr.addColorStop(0, "rgba(235,248,255,.85)"); cr.addColorStop(.35, "rgba(190,230,255,.38)"); cr.addColorStop(1, "rgba(150,210,255,0)");
    cx2.fillStyle = cr; cx2.fillRect(0, -96, 96, 192); cx2.restore();
    cx2.globalCompositeOperation = "destination-in"; var cm = cx2.createLinearGradient(0, 0, 0, 48); cm.addColorStop(0, "rgba(0,0,0,0)"); cm.addColorStop(.5, "rgba(0,0,0,1)"); cm.addColorStop(1, "rgba(0,0,0,0)"); cx2.fillStyle = cm; cx2.fillRect(0, 0, 96, 48);
    S.cone = cn;
    yield;
    this.street(S, mul(77));
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
  // street-level point covered by a building in front of the street
  function occluded(S, x, y) {
    var m, j, R;
    for (m = S.gi + 1; m < S.rects.length; m++) {
      for (j = 0; j < S.rects[m].length; j++) { R = S.rects[m][j]; if (x > R[0] - 2 && x < R[0] + R[2] + 2 && y > R[1] - 2 && y < R[1] + R[3] + 2) return true; }
    }
    return false;
  }
  function tileAt(S, x, y) { return cl(Math.floor(y / (S.H / S.rows)), 0, S.rows - 1) * S.cols + cl(Math.floor(x / (S.W / S.cols)), 0, S.cols - 1); }
  function avx(S, i, p) { var vx = S.W / 2, tx = vx + i * 3 * S.u, bx = vx + i * S.W * .105 * (1 + Math.abs(i) * .02); return tx + (bx - tx) * p; }
  function perY(S, kk) { return S.hy + (S.H - S.hy) * Math.pow(kk / 10, 2.1); }

  // cars (lights only) and people on the streets
  City.prototype.street = function (S, r) {
    var W = S.W, H = S.H, hy = S.hy, u = S.u, cars = [], ppl = [], i, k, kk, tries;
    var av = [-4, -3, -2, -1, 0, 1, 2, 3, 4];
    for (i = 0; i < av.length; i++) for (k = 0; k < 2; k++) cars.push({ kind: 0, ai: av[i], dir: k ? -1 : 1, ph: r(), sp: 1 + ((r() * 2) | 0), die: 4 + r() * 7.4, on: 14.2 + r() * 7, surv: r() < .3 });
    for (kk = 5; kk <= 10; kk++) { var nn = kk < 7 ? 1 : 2; for (k = 0; k < nn; k++) cars.push({ kind: 1, y: perY(S, kk - .55), s: (perY(S, kk - .55) - hy) / (H - hy), dir: r() < .5 ? -1 : 1, ph: r(), sp: kk < 8 ? 1 : 2, die: 4 + r() * 7.4, on: 14.2 + r() * 7, surv: r() < .3 }); }
    var M = cl(Math.round(W * H / (390 * 844) * 26), 18, 46);
    for (i = 0; i < M; i++) {
      for (tries = 0; tries < 10; tries++) {
        kk = 5 + ((r() * 5) | 0); var y = perY(S, kk - .12 + r() * .2), s = (y - hy) / (H - hy), sc = .62 + .85 * s, A = (12 + r() * 30) * u * (.5 + s), cx = W * .06 + r() * W * .88, ok = y < H - 10 * u;
        for (var q = -1; q <= 1 && ok; q += .5) if (occluded(S, cx + A * q, y) || occluded(S, cx + A * q, y - 7 * sc) || cx + A * q < W * .04 || cx + A * q > W * .96) ok = false;
        if (!ok) continue;
        var ti = tileAt(S, cx, y), tl = S.tiles[ti];
        ppl.push({ cx: cx, A: A, y: y, s: s, sc: sc, k: 1 + ((r() * 2) | 0), ph: r() * TAU, ti: ti, fl: tl.ts + .5 + r() * 1.3, off: tl.rs, id: i });
        break;
      }
    }
    S.cars = cars; S.ppl = ppl;
  };

  function nodePos(nd, t, o) {
    var p = nd.p;
    if (p) { var a = TAU * (p.k * t / T) + p.ph; o.x = p.cx + p.A * Math.sin(a); o.y = p.y - 3.4 * p.sc; } else { o.x = nd.x; o.y = nd.y; }
  }

  City.prototype.mesh = function (S, roofs, wins) {
    var W = S.W, H = S.H, u = S.u, area = W * H, N = cl(Math.round(area / (390 * 700) * 52), 38, 96), rnd = mul(7), i, j, z, L = [[], [], []];
    for (i = 0; i < roofs.length; i++) if (!hidden(S, roofs[i].l, roofs[i].x, roofs[i].y - 2)) L[0].push({ l: roofs[i].l, x: roofs[i].x, y: roofs[i].y, k: "unit" });
    for (i = 0; i < S.ppl.length; i++) { var pe = S.ppl[i]; L[1].push({ l: -1, x: pe.cx, y: pe.y - 3.4 * pe.sc, k: "person", p: pe }); }
    for (i = 0; i < wins.length; i++) if (wins[i].y > 34 && wins[i].y < H - 10 && !hidden(S, wins[i].l, wins[i].x, wins[i].y)) L[2].push({ l: wins[i].l, x: wins[i].x, y: wins[i].y, k: "phone" });
    for (var li = 0; li < 3; li++) for (i = L[li].length - 1; i > 0; i--) { j = (rnd() * (i + 1)) | 0; z = L[li][i]; L[li][i] = L[li][j]; L[li][j] = z; }
    L[2] = L[2].slice(0, 700);
    var nodes = [], minD = Math.sqrt(area / N) * .66, pat = [0, 1, 2, 2, 1, 2, 0, 2, 1, 2];
    for (var pass = 0; pass < 3 && nodes.length < Math.min(N, 32); pass++) {
      nodes = []; var ptr = [0, 0, 0], dn = [0, 0, 0], cnt = 0, guard = 0;
      while (nodes.length < N && (dn[0] + dn[1] + dn[2]) < 3 && guard++ < 4000) {
        var ty = pat[cnt++ % pat.length]; if (dn[ty]) continue;
        var got = false;
        while (ptr[ty] < L[ty].length) {
          var c = L[ty][ptr[ty]++], ok = c.x > 8 && c.x < W - 8 && c.y > 28 && c.y < H - 8;
          for (j = 0; ok && j < nodes.length; j++) if (Math.hypot(nodes[j].x - c.x, nodes[j].y - c.y) < minD) ok = false;
          if (ok) { nodes.push(c); got = true; break; }
        }
        if (!got) dn[ty] = 1;
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
    for (var guard2 = 0; guard2 < n; guard2++) {
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
    var sp = mx / MESHSPAN;
    for (i = 0; i < n; i++) nodes[i].on = MESH0 + (dist[i] < 1e9 ? dist[i] / sp : MESHSPAN);
    for (i = 0; i < E.length; i++) {
      var ed = E[i], tree = (from[ed.a] === i) || (from[ed.b] === i);
      ed.tree = tree;
      if (tree) { var ch = from[ed.b] === i ? ed.b : ed.a, pr = ch === ed.a ? ed.b : ed.a; ed.from = pr; ed.to = ch; ed.t0 = nodes[pr].on; ed.t1 = nodes[ch].on; }
      else { ed.from = ed.a; ed.to = ed.b; ed.t0 = Math.max(nodes[ed.a].on, nodes[ed.b].on) + .25; ed.t1 = ed.t0 + .5; }
    }
    S.nodes = nodes; S.E = E; S.px = new Float32Array(n); S.py = new Float32Array(n); S.seed = s; S.o = { x: 0, y: 0 };
    for (i = 0; i < S.anim.length; i++) S.anim[i].ti = tileAt(S, S.anim[i].x, S.anim[i].y);
    var P = [], flashes = [], r = mul(99), K = 48, spd = 110 * u;
    for (var k = 0; k < K; k++) {
      var st = 13.1 + k * .165 + r() * .1, act = []; for (i = 0; i < n; i++) if (nodes[i].on < st - .1) act.push(i);
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
    else if (t < tile.ts + 1.05) {
      var p = (t - tile.ts) / 1.05, fl = vn(tile.id, t * 9);
      a = (1 - sm(p)) * (1 - .6 * fl * (1 - p * .5)); if (p < .75 && hash(tile.id, Math.floor(t * 13)) < .16) a *= .4;
      if (a < RES) a = RES;
    }
    else if (t < tile.rs) a = RES;
    else { var q = (t - tile.rs) / 1.1; a = RES + (1 - RES) * sm(q); if (q < .8 && hash(tile.id, Math.floor(t * 15)) < .12) a *= .6; }
    if (a === 1) a *= .965 + .035 * Math.sin(TAU * t / T * 7 + tile.ph);
    return a;
  };

  function carAlpha(c, t) {
    if (c.surv || t < c.die) return 1;
    var dt = t - c.die;
    if (dt < .8) return (1 - sm(dt / .8)) * (hash((c.ph * 997) | 0, Math.floor(t * 12)) > .3 ? 1 : .45);
    if (t < c.on) return 0;
    return sm((t - c.on) / 1.6);
  }

  City.prototype.drawStreet = function (cc, t) {
    var S = this.S, d = S.dctx, dpr = S.dpr, ys = S.ys, ta = S.ta, u = S.u, hy = S.hy, H = S.H, W = S.W, cars = S.cars, ppl = S.ppl, i, c, al, p, q, x, y, s, sz, sep, spr, bs;
    d.setTransform(1, 0, 0, 1, 0, 0); d.globalCompositeOperation = "source-over"; d.globalAlpha = 1; d.clearRect(0, 0, S.dyn.width, S.dyn.height);
    d.setTransform(dpr, 0, 0, dpr, 0, -ys * dpr); d.globalCompositeOperation = "lighter";
    for (i = 0; i < cars.length; i++) {
      c = cars[i]; al = carAlpha(c, t); if (al < .02) continue;
      if (c.kind === 0) {
        q = fr(c.ph + c.dir * c.sp * t / T); al *= sm(q / .1) * sm((1 - q) / .1); if (al < .02) continue;
        p = .14 + .86 * q; y = hy + (H - hy) * p; x = avx(S, c.ai, p) + c.dir * 7 * u * p; sep = 3.2 * u * p + .6; sz = (4 + 11 * p) * u; spr = c.dir > 0 ? S.hw : S.hr;
        d.globalAlpha = al * (.5 + .5 * p) * (c.dir > 0 ? .95 : .8);
        d.drawImage(spr, x - sep - sz / 2, y - sz / 2, sz, sz); d.drawImage(spr, x + sep - sz / 2, y - sz / 2, sz, sz);
      } else {
        q = fr(c.ph + c.dir * c.sp * t / T); al *= sm(q / .08) * sm((1 - q) / .08); if (al < .02) continue;
        x = -20 * u + q * (W + 40 * u); y = c.y; s = c.s; var L = (7 + 13 * s) * u * .5; sz = (4 + 7 * s) * u;
        var fx = x + c.dir * L, rx = x - c.dir * L;
        d.globalAlpha = al * .95; d.drawImage(S.hw, fx - sz / 2, y - sz / 2, sz, sz);
        d.globalAlpha = al * .85; d.drawImage(S.hr, rx - sz * .35, y - sz * .35, sz * .7, sz * .7);
        bs = (.09 + .16 * s) * u; d.setTransform(dpr * c.dir * bs, 0, 0, dpr * bs, dpr * fx, dpr * (y - ys)); d.globalAlpha = al * .22; d.drawImage(S.cone, 0, -24, 96, 48);
        d.setTransform(dpr, 0, 0, dpr, 0, -ys * dpr);
      }
    }
    // people: warm figures in the lit city, cool figures with phone flashlights in the dark
    for (i = 0; i < ppl.length; i++) {
      var pe = ppl[i], ang = TAU * (pe.k * t / T) + pe.ph, vs = Math.cos(ang), sxd = cl(vs * 3, -1, 1), a = ta[pe.ti], bob = Math.abs(Math.sin(TAU * t * 1.8 + pe.ph * 3)) * .3 * pe.sc;
      x = pe.cx + pe.A * Math.sin(ang); var hh = 7.4 * pe.sc, w = 2.2 * pe.sc, y0 = pe.y - bob;
      var dt = t - pe.fl, g = 0;
      if (dt > 0) { g = dt < .5 ? (hash(pe.id, Math.floor(dt * 18)) > .5 ? 1 : .12) : 1; g *= 1 - sm((t - pe.off) / .6); }
      d.globalCompositeOperation = "source-over";
      if (a > .02) { d.globalAlpha = .85 * a; d.fillStyle = "#ffd6a6"; d.fillRect(x - w / 2, y0 - hh, w, hh * .66); d.fillRect(x - w * .4, y0 - hh - w * .75, w * .8, w * .8); d.fillRect(x - w * .5, y0 - hh * .34, w * .4, hh * .34); d.fillRect(x + w * .1, y0 - hh * .34, w * .4, hh * .34); }
      if (a < .98) { d.globalAlpha = .62 * (1 - a); d.fillStyle = "#9cc8e6"; d.fillRect(x - w / 2, y0 - hh, w, hh * .66); d.fillRect(x - w * .4, y0 - hh - w * .75, w * .8, w * .8); d.fillRect(x - w * .5, y0 - hh * .34, w * .4, hh * .34); d.fillRect(x + w * .1, y0 - hh * .34, w * .4, hh * .34); }
      if (g > .02) {
        d.globalCompositeOperation = "lighter"; bs = (.2 + .3 * pe.s) * u;
        d.setTransform(dpr * sxd * bs, 0, 0, dpr * bs, dpr * (x + sxd * 1.3 * pe.sc), dpr * (y0 - hh * .45 - ys)); d.globalAlpha = g * .75; d.drawImage(S.cone, 0, -24, 96, 48);
        d.setTransform(dpr, 0, 0, dpr, 0, -ys * dpr); d.globalAlpha = g * .8; sz = 7 * pe.sc + 3; d.drawImage(S.halo, x + sxd * 1.3 * pe.sc - sz / 2, y0 - hh * .45 - sz / 2, sz, sz);
      }
    }
    d.globalCompositeOperation = "destination-out"; d.setTransform(1, 0, 0, 1, 0, 0); d.globalAlpha = 1; d.drawImage(S.occ, 0, 0);
    d.globalCompositeOperation = "source-over";
    cc.setTransform(1, 0, 0, 1, 0, 0); cc.globalCompositeOperation = "source-over"; cc.globalAlpha = 1; cc.drawImage(S.dyn, 0, Math.round(ys * dpr));
    cc.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  City.prototype.draw = function (t, now) {
    var S = this.S, ctx = this.ctx, cc = ctx, dpr = S.dpr, W = S.W, H = S.H, u = S.u, cw = this.cv.width, ch = this.cv.height, tiles = S.tiles, n = tiles.length, ta = S.ta, j, a, sum = 0, tl, i;
    for (j = 0; j < n; j++) { a = this.light(tiles[j], t); ta[j] = a; sum += a; }
    var lf = sum / n, dim = W >= 900 ? 1 : .86;
    // scene pass: skyline, lit windows per tile, animated windows, haze, street, beacons, mesh
    cc.setTransform(1, 0, 0, 1, 0, 0); cc.globalCompositeOperation = "source-over"; cc.globalAlpha = 1;
    cc.drawImage(S.base, 0, 0);
    for (j = 0; j < n; j++) {
      tl = tiles[j]; a = ta[j]; if (a < .01) continue;
      cc.globalAlpha = a * dim; cc.drawImage(S.lit, tl.x0, tl.y0, tl.w, tl.h, tl.x0, tl.y0, tl.w, tl.h);
    }
    cc.setTransform(dpr, 0, 0, dpr, 0, 0);
    var an = S.anim;
    for (i = 0; i < an.length; i++) {
      var w = an[i]; a = ta[w.ti] * dim * (.12 + .88 * sm((Math.sin(TAU * w.k * t / T + w.ph) * .5 + .5 - .25) / .45)); if (a < .02) continue;
      cc.globalAlpha = a; cc.fillStyle = w.col; cc.fillRect(w.x, w.y, w.w, w.h);
    }
    cc.globalCompositeOperation = "lighter"; cc.globalAlpha = .5 * lf; cc.fillStyle = S.hazeG; cc.fillRect(0, S.hazeY, W, S.hazeH);
    cc.globalCompositeOperation = "source-over"; cc.globalAlpha = 1;
    this.drawStreet(cc, t);
    var av = S.avi; cc.globalCompositeOperation = "lighter";
    for (i = 0; i < av.length; i++) { var b = av[i], pu = .5 + .5 * Math.sin(TAU * (b.k * 5) * t / T + b.ph); pu = pu * pu * pu; cc.globalAlpha = .12 + .85 * pu; var bz = 7 + 5 * u * .5; cc.drawImage(S.hv, b.x - bz / 2, b.y - bz / 2, bz, bz); }
    cc.globalAlpha = 1; cc.globalCompositeOperation = "source-over";
    this.drawMesh(cc, t);
    // twinkling stars (the rest of the sky is baked into the skyline canvas)
    var st = S.stars; cc.globalCompositeOperation = "lighter";
    for (i = 0; i < st.length; i++) {
      var s = st[i], tw = .5 + .5 * Math.sin(TAU * s.k * t / T + s.ph); a = s.b * (.15 + .85 * tw) * .9; if (a < .03) continue;
      cc.globalAlpha = a; cc.fillStyle = "rgb(" + s.c + ")"; cc.fillRect(s.x - s.r / 2, s.y - s.r / 2, s.r, s.r);
      if (s.r > .95) { cc.globalAlpha = a * .35; cc.drawImage(S.halo, s.x - 4.5, s.y - 4.5, 9, 9); }
    }
    cc.globalCompositeOperation = "source-over"; cc.globalAlpha = 1;
    if (W >= 900) this.scrim();
    this.fade(); this.caption(t);
    var k = cl((now - this.born) / 700, 0, 1);
    if (k < 1) { ctx.globalCompositeOperation = "destination-out"; ctx.fillStyle = "rgba(0,0,0," + (1 - k * k * (3 - 2 * k)).toFixed(3) + ")"; ctx.fillRect(0, 0, S.W, S.H); ctx.globalCompositeOperation = "source-over"; }
  };

  City.prototype.drawMesh = function (ctx, t) {
    var S = this.S, nodes = S.nodes, E = S.E, u = S.u, i, j, ma = t > MESHEND ? 1 - sm((t - MESHEND) / 1.1) : 1, n = nodes.length, px = S.px, py = S.py, nd, o = S.o, W = S.W, H = S.H;
    // a cool wash and a ring when the network comes online
    if (t > BOOM - .05 && t < BOOM + 2.2) {
      var bq = (t - BOOM) / 2.2; nodePos(nodes[S.seed], t, o);
      ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = .1 * (1 - sm(bq * 1.2)); ctx.fillStyle = "rgb(80,190,255)"; ctx.fillRect(0, 0, W, H);
      ctx.globalAlpha = (1 - bq) * (1 - bq) * .55; ctx.strokeStyle = "rgba(170,235,255,1)"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(o.x, o.y, 6 + bq * W * .95, 0, TAU); ctx.stroke();
      ctx.globalAlpha = (1 - bq) * (1 - bq) * .18; ctx.lineWidth = 9; ctx.beginPath(); ctx.arc(o.x, o.y, 6 + bq * W * .95, 0, TAU); ctx.stroke();
      ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    }
    if (t < MESH0 - .1 || ma <= 0.01) return;
    for (i = 0; i < n; i++) { nodePos(nodes[i], t, o); px[i] = o.x; py[i] = o.y; }
    var mp = sm((t - MESH0) / MESHSPAN) * ma;
    ctx.globalCompositeOperation = "lighter"; ctx.globalAlpha = .16 * mp; ctx.fillStyle = S.coolG; ctx.fillRect(0, S.hy - H * .3, W, H); ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = ma; ctx.lineCap = "round";
    var pass, e, p, ax, ay, bx, by;
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
      nd = nodes[i]; var dt = t - nd.on; if (dt < 0) continue; var a = sm(dt / .4);
      ctx.globalAlpha = ma * a * .7; ctx.drawImage(S.halo, px[i] - hs / 2, py[i] - hs / 2, hs, hs);
      if (dt < 1.3) { ctx.globalAlpha = ma * (1 - dt / 1.3) * .8; ctx.strokeStyle = "rgba(170,235,255,1)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(px[i], py[i], 3 + dt * 18 * us, 0, TAU); ctx.stroke(); }
    }
    var F = S.F; for (i = 0; i < F.length; i++) { var df = t - F[i].t; if (df < 0 || df > .55) continue; var fs = 18 + df * 30, fi = F[i].n; ctx.globalAlpha = ma * (1 - df / .55) * .9; ctx.drawImage(S.halo, px[fi] - fs / 2, py[fi] - fs / 2, fs, fs); }
    ctx.globalCompositeOperation = "source-over";
    var s = us;
    for (i = 0; i < n; i++) {
      nd = nodes[i]; if (t < nd.on) continue; ctx.globalAlpha = ma * sm((t - nd.on) / .35); ctx.fillStyle = "#eefcff"; ctx.strokeStyle = "rgba(220,248,255,.9)";
      var x = px[i], y = py[i];
      if (nd.k === "unit") { ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 6 * s); ctx.stroke(); ctx.beginPath(); ctx.arc(x, y - 6 * s, 1.1 * s, 0, TAU); ctx.fill(); ctx.fillRect(x - 2 * s, y - .5, 4 * s, 2 * s); }
      else if (nd.k === "person") { var pz = 1.5 * s + .8; ctx.fillRect(x - pz / 2, y - pz / 2, pz, pz); }
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
    if (t < 3.6) { txt = "GRID ONLINE"; al = sm((t - .4) / .4) * (1 - sm((t - 3.1) / .4)); mark = 1; }
    else if (t < 11.55) { txt = "GRID DOWN"; al = sm((t - 3.9) / .3) * (1 - sm((t - 11.2) / .3)); mark = 2; }
    else if (t < 21.7) { var full = "blackout.network activated"; txt = full.slice(0, Math.floor(clamp01((t - 11.9) / 1.2) * full.length)); mark = 3; al = sm((t - 11.7) / .2) * (1 - sm((t - 21.2) / .4)); }
    else { txt = "GRID RESTORED"; al = sm((t - 22.2) / .3) * (1 - sm((t - 24.0) / .4)); mark = 1; }
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
    if (this.prev) { var iv = now - this.prev; if (iv < 120) this.iv = this.iv ? this.iv * .96 + iv * .04 : iv; } this.prev = now;
    if (now - this.last < this.minDt) return; this.last = now;
    var w0 = performance.now(), t = this.fixed != null ? this.fixed : ((now - this.t0) / 1000) % T;
    this.draw(t, now);
    var dt = performance.now() - w0; this.ema = this.ema ? this.ema * .92 + dt * .08 : dt;
    // frames running long: step down to 30 fps instead of stuttering
    if (this.minDt < 20 && (this.ema > 11 || this.iv > 25)) { if (++this.slow > 100) { this.minDt = 31; this.slow = 0; } } else this.slow = 0;
  };
  City.prototype.start = function () { if (this.on) return; this.on = true; this.last = 0; this.prev = 0; if (this.S) this.t0 = performance.now(); var self = this; this.raf = requestAnimationFrame(function (n) { self.frame(n); }); };
  City.prototype.stop = function () { this.on = false; if (this.raf) cancelAnimationFrame(this.raf); this.raf = 0; };
  City.prototype.still = function (t) {
    if (!this.S && !this.finishSync()) return;
    this.draw(t != null ? t : (this.fixed != null ? this.fixed : STATIC_T), this.born + 1e6);
  };

  // anchoring audit: paint every building (far to near, ids = layer) on a scratch canvas, then every node must sit on a building
  // of its own layer (not sky, not street, not hidden behind a nearer building); people must stand on the street, in view, at any time of the loop
  City.prototype.audit = function () {
    var S = this.S, out = { nodes: S.nodes.length, floating: 0, hidden: 0, units: 0, phones: 0, people: 0 }, i, j, k, m = mk(S.W, S.H), x = m.getContext("2d", { willReadFrequently: true }), o = { x: 0, y: 0 };
    for (i = 0; i < S.rects.length; i++) { x.fillStyle = "rgb(" + (i + 1) * 30 + ",0,0)"; for (j = 0; j < S.rects[i].length; j++) { var R = S.rects[i][j]; x.fillRect(R[0], R[1], R[2], R[3]); } }
    for (i = 0; i < S.nodes.length; i++) {
      var nd = S.nodes[i];
      if (nd.k === "person") {
        out.people++;
        for (k = 0; k < 8; k++) {
          nodePos(nd, T * k / 8, o); var p = nd.p;
          var d1 = x.getImageData(Math.round(o.x), Math.round(o.y), 1, 1).data, d2 = x.getImageData(Math.round(o.x), Math.round(p.y), 1, 1).data;
          if (o.y < S.hy || o.y > S.H - 4 || o.x < 4 || o.x > S.W - 4) { out.floating++; break; }
          if ((d1[3] > 200 && d1[0] > S.gi * 30) || (d2[3] > 200 && d2[0] > S.gi * 30)) { out.hidden++; break; }
        }
        continue;
      }
      nd.k === "unit" ? out.units++ : out.phones++;
      var d = x.getImageData(Math.round(nd.x), Math.round(nd.k === "unit" ? nd.y + 1.5 : nd.y), 1, 1).data;
      if (d[3] < 200) out.floating++; else if (d[0] !== (nd.l + 1) * 30) out.hidden++;
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
