/* Weather map worker (/weather, Nov 22 2026, pt1743u). Runs off the main thread so panning never stutters:
   1) radar tiles: decodes NOAA MRMS (IEM) and RainViewer tiles, converts their colours back to reflectivity (dBZ) with the
      providers' published colour tables, softens the edges and repaints them in one palette (no yellow), then hands the map an ImageBitmap;
   2) model fields: renders temperature / rain / snow frames from the Open-Meteo grids into Web-Mercator bitmaps (bicubic, smooth ramp). */
"use strict";
var LC = [[11.0,164,164,255],[11.5,161,161,252],[12.0,158,158,249],[12.5,154,154,246],[13.0,151,151,242],[13.5,148,148,239],[14.0,145,145,236],[14.5,142,142,233],[15.0,138,138,230],[15.5,135,135,227],[16.0,132,132,224],[16.5,129,129,220],[17.0,126,126,217],[17.5,122,122,214],[18.0,119,119,211],[18.5,116,116,208],[19.0,113,113,205],[19.5,110,110,201],[20.0,106,106,198],[20.5,103,103,195],[21.0,64,128,255],[21.5,62,125,249],[22.0,61,122,242],[22.5,59,118,236],[23.0,58,115,230],[23.5,56,112,223],[24.0,54,109,217],[24.5,53,106,211],[25.0,51,102,204],[25.5,50,99,198],[26.0,48,96,192],[26.5,46,93,185],[27.0,45,90,179],[27.5,43,86,172],[28.0,42,83,166],[28.5,40,80,160],[29.0,38,77,153],[29.5,37,74,147],[30.0,35,70,141],[30.5,34,67,134],[31.0,32,64,128],[31.5,0,249,0],[32.0,0,242,0],[32.5,0,236,0],[33.0,0,230,0],[33.5,0,223,0],[34.0,0,217,0],[34.5,0,211,0],[35.0,0,204,0],[35.5,0,198,0],[36.0,0,192,0],[36.5,0,185,0],[37.0,0,179,0],[37.5,0,172,0],[38.0,0,166,0],[38.5,0,160,0],[39.0,0,153,0],[39.5,0,147,0],[40.0,0,141,0],[40.5,0,134,0],[41.0,0,128,0],[41.5,255,249,0],[42.0,255,242,0],[42.5,255,236,0],[43.0,255,230,0],[43.5,255,223,0],[44.0,255,217,0],[44.5,255,211,0],[45.0,255,204,0],[45.5,255,198,0],[46.0,255,192,0],[46.5,255,185,0],[47.0,255,179,0],[47.5,255,172,0],[48.0,255,166,0],[48.5,255,160,0],[49.0,255,153,0],[49.5,255,147,0],[50.0,255,141,0],[50.5,255,134,0],[51.0,255,0,0],[51.5,250,0,0],[52.0,245,0,0],[52.5,241,0,0],[53.0,236,0,0],[53.5,231,0,0],[54.0,227,0,0],[54.5,222,0,0],[55.0,217,0,0],[55.5,212,0,0],[56.0,207,0,0],[56.5,203,0,0],[57.0,198,0,0],[57.5,193,0,0],[58.0,189,0,0],[58.5,184,0,0],[59.0,179,0,0],[59.5,174,0,0],[60.0,170,0,0],[60.5,165,0,0],[61.0,255,0,255],[61.5,249,0,249],[62.0,242,0,242],[62.5,236,0,236],[63.0,230,0,230],[63.5,223,0,223],[64.0,217,0,217],[64.5,211,0,211],[65.0,204,0,204],[65.5,198,0,198],[66.0,192,0,192],[66.5,185,0,185],[67.0,179,0,179],[67.5,172,0,172],[68.0,166,0,166],[68.5,160,0,160],[69.0,153,0,153],[69.5,147,0,147],[70.0,141,0,141],[70.5,134,0,134],[71.0,255,255,255],[71.5,249,249,249],[72.0,242,242,242],[72.5,236,236,236],[73.0,230,230,230],[73.5,223,223,223],[74.0,217,217,217],[74.5,211,211,211],[75.0,204,204,204],[75.5,198,198,198],[76.0,192,192,192],[76.5,185,185,185],[77.0,179,179,179],[77.5,172,172,172],[78.0,166,166,166],[78.5,160,160,160],[79.0,153,153,153],[79.5,147,147,147],[80.0,141,141,141],[80.5,134,134,134],[81.0,128,128,128],[81.5,128,128,128],[82.0,128,128,128],[82.5,128,128,128],[83.0,128,128,128],[83.5,128,128,128],[84.0,128,128,128],[84.5,128,128,128],[85.0,128,128,128],[85.5,128,128,128],[86.0,128,128,128],[86.5,128,128,128],[87.0,128,128,128],[87.5,128,128,128],[88.0,128,128,128],[88.5,128,128,128],[89.0,128,128,128],[89.5,128,128,128],[90.0,128,128,128],[90.5,128,128,128],[91.0,128,128,128],[91.5,128,128,128],[92.0,128,128,128],[92.5,128,128,128],[93.0,128,128,128],[93.5,128,128,128],[94.0,128,128,128],[94.5,128,128,128],[95.0,128,128,128]];
var RVT = [[-10,99,97,89,20],[-9,102,99,90,25],[-8,105,102,92,30],[-7,108,104,93,36],[-6,111,107,95,41],[-5,114,110,97,46],[-4,117,112,98,52],[-3,120,115,100,57],[-2,124,117,101,62],[-1,127,120,103,68],[0,130,123,105,73],[1,133,125,106,78],[2,136,128,108,84],[3,139,130,109,89],[4,142,133,111,94],[5,146,136,113,100],[6,158,147,117,110],[7,170,158,121,120],[8,182,169,126,130],[9,194,180,130,140],[10,206,192,135,150],[11,210,196,139,160],[12,214,200,143,170],[13,218,204,147,180],[14,222,208,151,190],[15,136,221,238,255],[16,108,209,235,255],[17,81,197,232,255],[18,54,186,229,255],[19,27,174,226,255],[20,0,163,224,255],[21,0,154,213,255],[22,0,145,202,255],[23,0,136,191,255],[24,0,127,180,255],[25,0,119,170,255],[26,0,112,163,255],[27,0,105,156,255],[28,0,98,149,255],[29,0,91,142,255],[30,0,85,136,255],[31,0,81,128,255],[32,0,78,120,255],[33,0,74,112,255],[34,0,71,104,255],[35,255,238,0,255],[36,255,224,0,255],[37,255,210,0,255],[38,255,197,0,255],[39,255,183,0,255],[40,255,170,0,255],[41,255,159,0,255],[42,255,149,0,255],[43,255,139,0,255],[44,255,129,0,255],[45,255,68,0,255],[46,242,54,0,255],[47,230,40,0,255],[48,217,27,0,255],[49,205,13,0,255],[50,193,0,0,255],[51,168,0,0,255],[52,143,0,0,255],[53,118,0,0,255],[54,93,0,0,255],[55,255,170,255,255],[56,255,159,255,255],[57,255,149,255,255],[58,255,139,255,255],[59,255,129,255,255],[60,255,119,255,255],[61,255,108,255,255],[62,255,98,255,255],[63,255,88,255,255],[64,255,78,255,255],[65,255,255,255,255],[66,255,255,255,255],[67,255,255,255,255],[68,255,255,255,255],[69,255,255,255,255],[70,255,255,255,255],[71,255,255,255,255],[72,255,255,255,255],[73,255,255,255,255],[74,255,255,255,255],[75,0,255,0,255],[76,0,255,0,255],[77,0,255,0,255],[78,0,255,0,255],[79,0,255,0,255],[80,0,255,0,255],[81,0,255,0,255],[82,0,255,0,255],[83,0,255,0,255],[84,0,255,0,255],[85,0,255,0,255],[86,0,255,0,255],[87,0,255,0,255],[88,0,255,0,255],[89,0,255,0,255],[90,0,255,0,255],[91,0,255,0,255],[92,0,255,0,255],[93,0,255,0,255],[94,0,255,0,255],[95,0,255,0,255],[-9,206,255,255,12],[-8,205,255,255,25],[-7,204,255,255,38],[-6,203,255,255,51],[-5,203,255,255,63],[-4,202,255,255,76],[-3,201,255,255,89],[-2,200,255,255,102],[-1,199,255,255,114],[0,199,255,255,127],[1,198,255,255,140],[2,197,255,255,153],[3,196,255,255,165],[4,195,255,255,178],[5,195,255,255,191],[6,194,255,255,204],[7,193,255,255,216],[8,192,255,255,229],[9,191,255,255,242],[10,191,255,255,255],[11,184,248,255,255],[12,178,242,255,255],[13,171,235,255,255],[14,165,229,255,255],[15,159,223,255,255],[16,152,216,255,255],[17,146,210,255,255],[18,139,203,255,255],[19,133,197,255,255],[20,127,191,255,255],[21,120,184,255,255],[22,114,178,255,255],[23,107,171,255,255],[24,101,165,255,255],[25,95,159,255,255],[26,91,155,255,255],[27,88,152,255,255],[28,85,149,255,255],[29,82,146,255,255],[30,79,143,255,255],[31,75,139,255,255],[32,72,136,255,255],[33,69,133,255,255],[34,66,130,255,255],[35,63,127,255,255],[36,59,123,255,255],[37,56,120,255,255],[38,53,117,255,255],[39,50,114,255,255],[40,47,111,255,255],[41,43,107,255,255],[42,40,104,255,255],[43,37,101,255,255],[44,34,98,255,255],[45,31,95,255,255],[46,27,91,255,255],[47,24,88,255,255],[48,21,85,255,255],[49,18,82,255,255],[50,15,79,255,255],[51,12,75,255,255],[52,9,72,255,255],[53,6,69,255,255],[54,2,66,255,255],[55,0,63,255,255],[56,0,59,255,255],[57,0,56,255,255],[58,0,53,255,255],[59,0,50,255,255],[60,0,47,255,255],[61,0,43,255,255],[62,0,40,255,255],[63,0,37,255,255],[64,0,34,255,255],[65,0,31,255,255],[66,0,27,255,255],[67,0,24,255,255],[68,0,21,255,255],[69,0,18,255,255],[70,0,15,255,255],[71,0,12,255,255],[72,0,9,255,255],[73,0,6,255,255],[74,0,2,255,255],[75,0,0,255,255],[76,0,0,255,255],[77,0,0,255,255],[78,0,0,255,255],[79,0,0,255,255],[80,0,0,255,255],[81,0,0,255,255],[82,0,0,255,255],[83,0,0,255,255],[84,0,0,255,255],[85,0,0,255,255],[86,0,0,255,255],[87,0,0,255,255],[88,0,0,255,255],[89,0,0,255,255],[90,0,0,255,255],[91,0,0,255,255],[92,0,0,255,255],[93,0,0,255,255],[94,0,0,255,255],[95,0,0,255,255]];
/* ---- reflectivity palette (dBZ -> RGBA). Soft alpha at the light end so echoes read as clouds, not pixels. ---- */
var RP = [[6, 40, 90, 170, 0], [12, 50, 118, 205, .42], [18, 62, 156, 238, .66], [24, 56, 196, 226, .78], [30, 46, 212, 150, .86], [36, 36, 186, 96, .9],
          [41, 255, 154, 61, .93], [47, 255, 106, 42, .95], [52, 255, 59, 59, .96], [58, 214, 38, 120, .97], [63, 224, 64, 251, .98], [70, 246, 236, 255, 1]];
var DLUT = new Uint8ClampedArray(201 * 4);   /* dBZ 0..100 in 0.5 steps */
(function () {
  for (var i = 0; i <= 200; i++) {
    var v = i / 2, c;
    if (v <= RP[0][0]) c = [0, 0, 0, 0];
    else if (v >= RP[RP.length - 1][0]) c = RP[RP.length - 1].slice(1);
    else for (var k = 1; k < RP.length; k++) if (v <= RP[k][0]) { var a = RP[k - 1], b = RP[k], t = (v - a[0]) / (b[0] - a[0]); c = [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t]; break; }
    DLUT[i * 4] = c[0]; DLUT[i * 4 + 1] = c[1]; DLUT[i * 4 + 2] = c[2]; DLUT[i * 4 + 3] = Math.round(c[3] * 255);
  }
})();
var MRMS = new Map(); LC.forEach(function (e) { MRMS.set(e[1] << 16 | e[2] << 8 | e[3], e[0]); });
var RVC = new Map();
function rvDbz(r, g, b, a) {
  var key = (r << 24 | g << 16 | b << 8 | a) >>> 0, hit = RVC.get(key); if (hit !== undefined) return hit;
  var best = -99, bd = 1e9;
  for (var i = 0; i < RVT.length; i++) { var e = RVT[i], d = (e[1] - r) * (e[1] - r) + (e[2] - g) * (e[2] - g) + (e[3] - b) * (e[3] - b) + 0.5 * (e[4] - a) * (e[4] - a); if (d < bd) { bd = d; best = e[0]; } }
  if (bd > 2500) best = -99;
  RVC.set(key, best); return best;
}
/* NOAA MRMS domain: RainViewer is hidden inside it so the two never double up */
var DOM = { w: -130, e: -60, s: 20, n: 55 };
function tileLon(x, z) { return x / Math.pow(2, z) * 360 - 180; }
function tileLat(y, z) { var n = Math.PI - 2 * Math.PI * y / Math.pow(2, z); return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n))); }
var CV = null, CX = null;
function blank1() { var c = new OffscreenCanvas(1, 1); c.getContext("2d"); return c.transferToImageBitmap(); }
function canvas(w, h) {
  if (!CV) { CV = new OffscreenCanvas(w, h); CX = CV.getContext("2d", { willReadFrequently: true }); }
  if (CV.width !== w || CV.height !== h) { CV.width = w; CV.height = h; }
  return CX;
}
function radarTile(kind, buf, z, x, y) {
  return createImageBitmap(new Blob([buf], { type: "image/png" })).then(function (bmp) {
    var W = bmp.width, H = bmp.height;
    if (kind === "h") return bmp;   /* HRRR forecast tiles keep their own rain / snow / mix colours */
    var cx = canvas(W, H); cx.clearRect(0, 0, W, H); cx.drawImage(bmp, 0, 0); bmp.close();
    var im = cx.getImageData(0, 0, W, H), d = im.data, N = W * H, D = new Float32Array(N), any = false;
    var mask = null;
    if (kind === "g") {
      var lw = tileLon(x, z), le = tileLon(x + 1, z), ln = tileLat(y, z), ls = tileLat(y + 1, z);
      if (lw >= DOM.w && le <= DOM.e && ls >= DOM.s && ln <= DOM.n) return blank1();   /* fully inside: NOAA covers it */
      if (!(le < DOM.w || lw > DOM.e || ln < DOM.s || ls > DOM.n)) {
        mask = new Uint8Array(N);
        for (var py = 0; py < H; py++) { var la = tileLat(y + (py + 0.5) / H, z), inLat = la >= DOM.s && la <= DOM.n;
          if (!inLat) continue;
          for (var px = 0; px < W; px++) { var lo = tileLon(x + (px + 0.5) / W, z); if (lo >= DOM.w && lo <= DOM.e) mask[py * W + px] = 1; } }
      }
    }
    for (var i = 0; i < N; i++) {
      var o = i * 4, a = d[o + 3], v = 0;
      if (a > 0 && !(mask && mask[i])) {
        if (kind === "m") { var k = MRMS.get(d[o] << 16 | d[o + 1] << 8 | d[o + 2]); v = k === undefined ? 0 : k; }
        else { v = rvDbz(d[o], d[o + 1], d[o + 2], a); if (v < 0) v = 0; }
        if (v > 0) any = true;
      }
      D[i] = v;
    }
    if (!any) return blank1();
    /* soften: 3x3 Gaussian on reflectivity (edges clamp), so scans read as smooth cloud shapes at every zoom */
    var S = new Float32Array(N);
    for (var yy = 0; yy < H; yy++) for (var xx = 0; xx < W; xx++) {
      var s = 0, wsum = 0;
      for (var dy = -1; dy <= 1; dy++) { var y2 = yy + dy; if (y2 < 0 || y2 >= H) continue;
        for (var dx = -1; dx <= 1; dx++) { var x2 = xx + dx; if (x2 < 0 || x2 >= W) continue; var w = (dx ? 1 : 2) * (dy ? 1 : 2); s += D[y2 * W + x2] * w; wsum += w; } }
      S[yy * W + xx] = s / wsum;
    }
    for (var j = 0; j < N; j++) {
      var q = j * 4, val = Math.max(S[j], D[j] * 0.85), li = Math.min(200, Math.round(val * 2)) * 4;
      d[q] = DLUT[li]; d[q + 1] = DLUT[li + 1]; d[q + 2] = DLUT[li + 2]; d[q + 3] = DLUT[li + 3];
    }
    cx.putImageData(im, 0, 0);
    return CV.transferToImageBitmap ? (function () { var b = CV.transferToImageBitmap(); CV = null; return b; })() : createImageBitmap(CV);
  });
}

/* ---- model grids ---- */
var GR = {};   /* key -> {nx, ny, lat0, lon0, step, wrap, nt, N, temp, precip, snow} (Float32, NaN = no data) */
function my(lat) { return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)); }
function iy(y) { return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180 / Math.PI; }
function field(g, mode, k) {
  var N = g.N, out = new Float32Array(N), j, q, b = k * N;
  if (mode === "temp") for (j = 0; j < N; j++) out[j] = g.temp[b + j];
  else if (mode === "rain") for (j = 0; j < N; j++) { var p = g.precip[b + j]; out[j] = p !== p ? NaN : p / 254; }
  else for (j = 0; j < N; j++) { var s = 0, ok = false; for (q = Math.max(0, k - 7); q <= k; q++) { var v = g.snow[q * N + j]; if (v === v) { s += v; ok = true; } } out[j] = ok ? s / 25.4 : NaN; }
  return mode === "temp" ? out : blurF(g, out);
}
function blurF(g, F) {   /* NaN-aware 3x3 [1 2 1] pass: rain and snow cells read as soft weather shapes, not grid squares */
  var nx = g.nx, ny = g.ny, out = new Float32Array(F.length);
  for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) {
    var c = F[j * nx + i]; if (c !== c) { out[j * nx + i] = NaN; continue; }
    var s = 0, w = 0;
    for (var dj = -1; dj <= 1; dj++) { var jj = j + dj; if (jj < 0 || jj >= ny) continue;
      for (var di = -1; di <= 1; di++) { var ii = i + di; if (g.wrap) ii = (ii + nx) % nx; else if (ii < 0 || ii >= nx) continue;
        var v = F[jj * nx + ii]; if (v !== v) continue; var k = (di ? 1 : 2) * (dj ? 1 : 2); s += v * k; w += k; } }
    out[j * nx + i] = s / w;
  }
  return out;
}
function cr(p0, p1, p2, p3, t) { return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0))); }
function at(g, F, i, j) { if (j < 0) j = 0; else if (j >= g.ny) j = g.ny - 1; if (g.wrap) i = ((i % g.nx) + g.nx) % g.nx; else if (i < 0) i = 0; else if (i >= g.nx) i = g.nx - 1; return F[j * g.nx + i]; }
function bilin(g, F, gx, gy) {
  var x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0, a = at(g, F, x0, y0), b = at(g, F, x0 + 1, y0), c = at(g, F, x0, y0 + 1), d = at(g, F, x0 + 1, y0 + 1);
  if (a === a && b === b && c === c && d === d) return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  var s = 0, w = 0;
  if (a === a) { var wa = (1 - fx) * (1 - fy) + 1e-3; s += a * wa; w += wa; } if (b === b) { var wb = fx * (1 - fy) + 1e-3; s += b * wb; w += wb; }
  if (c === c) { var wc = (1 - fx) * fy + 1e-3; s += c * wc; w += wc; } if (d === d) { var wd = fx * fy + 1e-3; s += d * wd; w += wd; }
  return w ? s / w : NaN;
}
function smooth(g, F, gx, gy) {
  if (gy < 0 || gy > g.ny - 1 || (!g.wrap && (gx < 0 || gx > g.nx - 1))) return NaN;
  var x1 = Math.floor(gx), y1 = Math.floor(gy), fx = gx - x1, fy = gy - y1, rows = [0, 0, 0, 0];
  for (var j = -1; j <= 2; j++) {
    var r0 = at(g, F, x1 - 1, y1 + j), r1 = at(g, F, x1, y1 + j), r2 = at(g, F, x1 + 1, y1 + j), r3 = at(g, F, x1 + 2, y1 + j);
    if (r0 !== r0 || r1 !== r1 || r2 !== r2 || r3 !== r3) return bilin(g, F, gx, gy);
    rows[j + 1] = cr(r0, r1, r2, r3, fx);
  }
  return cr(rows[0], rows[1], rows[2], rows[3], fy);
}
function ramp(p, v) {
  if (v <= p[0][0]) return p[0].slice(1);
  for (var i = 1; i < p.length; i++) if (v <= p[i][0]) { var a = p[i - 1], b = p[i], t = (v - a[0]) / (b[0] - a[0]); return [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t]; }
  return p[p.length - 1].slice(1);
}
function fieldImage(m) {
  var g = GR[m.g]; if (!g) return null;
  var F = field(g, m.mode, m.k), P = m.pal, lo = P[0][0], hi = P[P.length - 1][0], NL = 512, lut = new Array(NL + 1);
  for (var u = 0; u <= NL; u++) lut[u] = ramp(P, lo + (hi - lo) * u / NL);
  var W = m.w, H = m.h, cx = canvas(W, H), im = cx.createImageData(W, H), D = im.data;
  var yT = my(m.n), yB = my(m.s), lonW = m.lw, lonE = m.le;
  for (var py = 0; py < H; py++) {
    var lat = iy(yT - (py + 0.5) / H * (yT - yB)), gy = (lat - g.lat0) / g.step;
    var ey = Math.min(gy, g.ny - 1 - gy);
    for (var px = 0; px < W; px++) {
      var lon = lonW + (px + 0.5) / W * (lonE - lonW), gx = (lon - g.lon0) / g.step, v = smooth(g, F, gx, gy), o = (py * W + px) * 4;
      if (v !== v) { D[o + 3] = 0; continue; }
      var soft = 1;
      if (m.mode !== "temp") { if (v < lo * 0.25) { D[o + 3] = 0; continue; } if (v < lo) { soft = (v - lo * 0.25) / (lo * 0.75); soft *= soft; } }
      var c = lut[Math.round(Math.min(1, Math.max(0, (v - lo) / (hi - lo))) * NL)];
      var e = g.wrap ? ey : Math.min(gx, g.nx - 1 - gx, ey), fade = Math.min(1, Math.max(0, e / (m.fade || 2.2))); fade = fade * fade * (3 - 2 * fade) * soft;
      D[o] = c[0]; D[o + 1] = c[1]; D[o + 2] = c[2]; D[o + 3] = Math.round(c[3] * 255 * fade);
    }
  }
  cx.putImageData(im, 0, 0);
  var b = CV.transferToImageBitmap(); CV = null; return b;
}

self.onmessage = function (e) {
  var m = e.data;
  if (m.op === "tile") {
    radarTile(m.kind, m.buf, m.z, m.x, m.y).then(function (bmp) { self.postMessage({ id: m.id, bmp: bmp }, [bmp]); }, function (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); });
  } else if (m.op === "grid") {
    GR[m.key] = m.grid; self.postMessage({ id: m.id, ok: 1 });
  } else if (m.op === "field") {
    try { var b = fieldImage(m); self.postMessage({ id: m.id, bmp: b }, b ? [b] : []); } catch (err) { self.postMessage({ id: m.id, err: String(err && err.message || err) }); }
  }
};
