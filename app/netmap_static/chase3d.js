/* BLACKOUT.NETWORK /grid Sky view: rocket chase camera (pt1842u, Nov 24 2026).
   Lazy-loaded by launches.js after three147.js when a launch is selected.
   Real: launch time, vehicle, pad, LL2 mission timeline and booster landing site / outcome (The Space Devs Launch Library 2).
   Modeled, not telemetry: every position, attitude, burn and the orbit propagation. Rocket, pad, droneship: procedural shapes,
   no photos or textures except the NASA Blue Marble Earth map (public domain).
   Own scope and ch* names only: nothing here re-declares a net.js or launches.js function. */
(function () {
  "use strict";
  var T = window.THREE; if (!T || !T.OrbitControls) return;
  var ER = 6371008.8, MU = 3.986004418e14, WE = 7.2921159e-5, D2R = Math.PI / 180;
  var mob = matchMedia("(max-width: 760px)").matches, reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var C = { open: false, L: null, t: 0, playing: false, speed: 0, focus: "auto", raf: 0, last: 0, tAsc: 0, tEnd: 0, orbP: 0, orbits: 0, ticks: [] };

  function chEsc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  /* Earth-fixed position (m), same mapping as THREE.SphereGeometry + an equirectangular map (u=0 at 180W, north = +Y) */
  function chPos(lon, lat, alt) {
    var r = ER + (alt || 0), ph = (lon + 180) * D2R, th = (90 - lat) * D2R, st = Math.sin(th);
    return [-r * Math.cos(ph) * st, r * Math.cos(th), r * Math.sin(ph) * st];
  }
  function chLL(p) { var r = Math.hypot(p[0], p[1], p[2]), lat = 90 - Math.acos(p[1] / r) / D2R, lon = Math.atan2(p[2], -p[0]) / D2R - 180; if (lon < -180) lon += 360; return [lon, lat, r - ER]; }
  function chN(v) { var l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; }
  function chX(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function chD(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function chSub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function chRotY(p, a) { var c = Math.cos(a), s = Math.sin(a); return [p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c]; }   /* rotation about the polar axis */
  function chRotAx(v, k, a) { var c = Math.cos(a), s = Math.sin(a), d = chD(k, v), x = chX(k, v); return [v[0] * c + x[0] * s + k[0] * d * (1 - c), v[1] * c + x[1] * s + k[1] * d * (1 - c), v[2] * c + x[2] * s + k[2] * d * (1 - c)]; }
  function chENU(p) {
    var u = chN(p), e = chX([0, 1, 0], u); if (Math.hypot(e[0], e[1], e[2]) < 1e-6) e = [1, 0, 0]; e = chN(e);
    return { u: u, e: e, n: chX(u, e) };
  }
  function chTPlus(s) { var neg = s < 0; s = Math.abs(Math.round(s)); var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (neg ? "T-" : "T+") + (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (x < 10 ? "0" : "") + x; }
  function chImp() { var U = window.BNUnits; return !U || !U.isImperial || U.isImperial(); }
  function chAlt(m) { var U = window.BNUnits, km = m / 1000; if (U && U.fmtAlt) return U.fmtAlt(km); return chImp() ? (km * 0.621371 < 1 ? Math.round(m * 3.28084).toLocaleString("en-US") + " ft" : (km * 0.621371).toFixed(km < 16 ? 1 : 0) + " mi") : (km < 1 ? Math.round(m) + " m" : km.toFixed(km < 10 ? 1 : 0) + " km"); }
  function chSpd(ms) { return chImp() ? Math.round(ms * 2.23694).toLocaleString("en-US") + " mph" : Math.round(ms * 3.6).toLocaleString("en-US") + " km/h"; }
  function chVeh(L) { var n = String(L.name || ""), i = n.indexOf("|"); return i >= 0 ? n.slice(0, i).trim() : (L.vehicle || ""); }
  function chMis(L) { var n = String(L.name || ""), i = n.indexOf("|"); return i >= 0 ? n.slice(i + 1).trim() : (L.mission || n); }

  /* ---------- trajectory (modeled) ---------- */
  function chLerpPath(a, t) {
    if (!a || !a.length) return null;
    if (t <= a[0][3]) return chPos(a[0][0], a[0][1], a[0][2]);
    for (var i = 1; i < a.length; i++) if (a[i][3] >= t) {
      var p = a[i - 1], q = a[i], u = (t - p[3]) / Math.max(1e-6, q[3] - p[3]), dl = q[0] - p[0]; if (dl > 180) dl -= 360; if (dl < -180) dl += 360;
      return chPos(p[0] + dl * u, p[1] + (q[1] - p[1]) * u, p[2] + (q[2] - p[2]) * u);
    }
    return null;
  }
  function chOrbitSetup(L) {
    var a = L.ascent, n = a.length; C.orb = null; C.orbits = 0;
    var sub = /^(sub|n\/a|none)/i.test(String(L.orbit || "")) || !L.orbit;
    var fail = L.status === "Failure" || L.failure;
    if (n < 2 || a[n - 1][2] < 120000 || sub || fail) return;
    var A = a[n - 2], B = a[n - 1];
    /* inertial (non-rotating) frame aligned with Earth-fixed at T+0 */
    var ra = chN(chRotY(chPos(A[0], A[1], 0), WE * A[3])), rb = chN(chRotY(chPos(B[0], B[1], 0), WE * B[3]));
    var k = chN(chX(ra, rb)), ang = Math.acos(Math.max(-1, Math.min(1, chD(ra, rb))));
    var r = ER + B[2], nMean = Math.sqrt(MU / (r * r * r)), w = ang / Math.max(1, B[3] - A[3]);
    if (!(w > 0) || Math.abs(w - nMean) / nMean > 0.5) w = nMean;
    C.orb = { r0: rb, k: k, w: w, t0: B[3], alt: B[2] }; C.orbP = 2 * Math.PI / w; C.orbits = 3;
  }
  function chUpper(t) {
    var a = C.L.ascent, end = a[a.length - 1][3];
    if (t > 0 && t < a[1][3]) t = a[1][3] * Math.pow(t / a[1][3], 2);   /* ease off the pad instead of jumping to speed */
    if (t <= end || !C.orb) return chLerpPath(a, Math.min(t, end));
    var o = C.orb, ri = chRotAx(o.r0, o.k, o.w * (t - o.t0)), rf = chRotY(ri, -WE * t), s = (ER + o.alt);
    return [rf[0] * s, rf[1] * s, rf[2] * s];
  }
  function chBooster(t) {
    var b = C.L.booster; if (!b.length) return null;
    var p = chLerpPath(b, Math.max(b[0][3], Math.min(t, b[b.length - 1][3]))) || (function () { var e = b[b.length - 1]; return chPos(e[0], e[1], e[2]); })();
    if (C.bOff) { var n = chN(p); p = [p[0] + n[0] * C.bOff, p[1] + n[1] * C.bOff, p[2] + n[2] * C.bOff]; }   /* droneship deck height */
    return p;
  }
  function chSepT() { var s = 0; C.L.labels.forEach(function (b) { if (b.k === "sep") s = b.t; }); return s || (C.L.booster.length ? C.L.booster[0][3] : 150); }
  function chEvT(k) { var s = null; C.L.labels.forEach(function (b) { if (b.k === k && s == null) s = b.t; }); return s; }
  function chLandT() { var b = C.L.booster; return b.length ? b[b.length - 1][3] : null; }

  /* ---------- styles ---------- */
  var css = document.createElement("style");
  css.textContent = [
    ".nx-ch{position:absolute;inset:0;z-index:5;background:#000;touch-action:none;overflow:hidden}",
    ".nx-ch canvas{display:block;width:100%!important;height:100%!important;touch-action:none;outline:none}",
    ".nx-ch-hud{position:absolute;left:10px;top:78px;pointer-events:none;background:rgba(8,10,16,.62);border-radius:8px;padding:6px 9px;color:#E8ECF5;font-size:12px;line-height:1.4;text-shadow:0 0 3px #000,0 0 6px #000;max-width:calc(100% - 20px)}",
    ".nx-ch-hud b{font-size:14px;font-weight:650}.nx-ch-hud .m{color:#AEB4C4}.nx-ch-hud .n{font-variant-numeric:tabular-nums}",
    ".nx-ch-ev{display:inline-block;margin-top:5px;background:rgba(8,10,16,.78);border:1px solid rgba(232,236,245,.25);border-radius:8px;padding:3px 9px;color:#E8ECF5;font-size:12.5px;font-weight:600;white-space:nowrap}",
    ".nx-ch-ev.k-land{color:#5CE1B6}.nx-ch-ev.k-landfail,.nx-ch-ev.k-fail{color:#FF5A5A}",
    ".nx-ch-tl{position:absolute;left:50%;transform:translateX(-50%);bottom:62px;width:min(720px,calc(100% - 16px));background:rgba(8,10,16,.86);border:1px solid rgba(232,236,245,.22);border-radius:10px;padding:6px 8px 7px;color:#E8ECF5;font-size:12.5px;box-sizing:border-box}",
    ".nx-ch-r{display:flex;align-items:center;gap:8px;flex-wrap:wrap}",
    ".nx-ch-tl button{all:unset;cursor:pointer;padding:5px 8px;border:1px solid rgba(232,236,245,.3);border-radius:6px;line-height:1;font-size:12.5px;white-space:nowrap}",
    ".nx-ch-tl button[aria-pressed=true]{background:#E8ECF5;color:#0A0C12}",
    ".nx-ch-tl .tp{font-variant-numeric:tabular-nums;min-width:58px;color:#C9CCD6}",
    ".nx-ch-sc{position:relative;flex:1 1 200px;min-width:140px;height:26px}",
    ".nx-ch-sc input{position:absolute;left:0;right:0;top:4px;width:100%;margin:0;accent-color:#E8ECF5;touch-action:pan-x}",
    ".nx-ch-tk{position:absolute;top:0;width:2px;height:7px;margin-left:-1px;background:#AEB4C4;border:0;padding:0;cursor:pointer}",
    ".nx-ch-tk.k-land{background:#5CE1B6}.nx-ch-tk.k-landfail,.nx-ch-tk.k-fail{background:#FF5A5A}.nx-ch-tk.k-orbitn{background:#4FC3F7}",
    ".nx-ch-tk:after{content:'';position:absolute;left:-7px;right:-7px;top:-6px;bottom:-4px}",
    ".nx-ch-f{display:flex;gap:4px;align-items:center}.nx-ch-f span{color:#AEB4C4}",
    ".nx-ch-note{margin-top:5px;font-size:10.5px;color:#AEB4C4}",
    ".nx-ch-tag{position:absolute;left:0;top:0;transform:translate(-9999px,0);pointer-events:none;font-size:11px;font-weight:600;color:#E8ECF5;text-shadow:0 0 3px #000,0 0 6px #000;white-space:nowrap}",
    ".nx-ch-tag:before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:currentColor;margin-right:5px;vertical-align:1px}",
    ".nx-ch-tag.k-land{color:#5CE1B6}.nx-ch-tag.k-landfail{color:#FF5A5A}",
    "body.nx-lc-chase #nx_sf,body.nx-lc-chase .nx-lc-lbls,body.nx-lc-chase .nx-lc-note,body.nx-lc-chase .nx-lc-bar input[type=range],body.nx-lc-chase .nx-lc-bar .tp,body.nx-lc-chase .nx-lc-bar [data-a=play]{display:none!important}",
    "@media (max-width:760px){.nx-ch-tl{bottom:54px;padding:5px 6px 6px;font-size:12px}.nx-ch-hud{font-size:11px;top:98px;left:8px}.nx-ch-hud b{font-size:12.5px}.nx-ch-ev{font-size:11.5px}.nx-ch-sc{flex-basis:100%;order:5}}"
  ].join("\n");
  document.head.appendChild(css);

  /* ---------- scene ---------- */
  function chMat(color, o) { var m = new T.MeshStandardMaterial(Object.assign({ color: color, roughness: 0.55, metalness: 0.05 }, o || {})); return m; }
  function chCyl(r1, r2, h, mat, y, seg) { var m = new T.Mesh(new T.CylinderGeometry(r1, r2, h, seg || 32, 1), mat); m.position.y = y + h / 2; return m; }
  function chOgive(r, h, mat, y) {
    var pts = []; for (var i = 0; i <= 16; i++) { var u = i / 16; pts.push(new T.Vector2(r * Math.sqrt(Math.max(0, 1 - u * u)) * (1 - 0.06 * u), u * h)); }
    pts[16].x = 0.02 * r; var m = new T.Mesh(new T.LatheGeometry(pts, 32), mat); m.position.y = y; return m;
  }
  function chPlume(r, len) {
    var g = new T.Group();
    var o = new T.Mesh(new T.ConeGeometry(r * 1.6, len, 20, 1, true), new T.MeshBasicMaterial({ color: 0xff8a3c, transparent: true, opacity: 0.55, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
    var i = new T.Mesh(new T.ConeGeometry(r * 0.8, len * 0.45, 16, 1, true), new T.MeshBasicMaterial({ color: 0xfff1d6, transparent: true, opacity: 0.9, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
    o.rotation.x = Math.PI; o.position.y = -len / 2; i.rotation.x = Math.PI; i.position.y = -len * 0.225;
    g.add(o); g.add(i); g.userData.len = len; return g;
  }
  function chKind(L) {
    var v = (chVeh(L) + " " + (L.vehicle || "")).toLowerCase();
    if (/starship|super heavy/.test(v)) return "starship";
    if (/falcon heavy/.test(v)) return "fh";
    if (/falcon 9/.test(v)) return "f9";
    if (/electron/.test(v)) return "electron";
    return "generic";
  }
  /* sizes in metres, after published vehicle dimensions */
  function chRocket(kind) {
    var white = chMat(0xeef0f3, { roughness: 0.45 }), black = chMat(0x15171c, { roughness: 0.6 }), grey = chMat(0x5b6069, { roughness: 0.4, metalness: 0.5 }),
        steel = chMat(0xc4c8cf, { roughness: 0.32, metalness: 0.85 }), tile = chMat(0x1a1c21, { roughness: 0.85 });
    var B = new T.Group(), U = new T.Group(), F = new T.Group(), R = { booster: B, upper: U, fairing: F, legs: [], fins: [], side: null };
    function engines(grp, r, n, y, nr) { for (var i = 0; i < n; i++) { var a = i / n * Math.PI * 2, e = new T.Mesh(new T.CylinderGeometry(nr * 0.55, nr, nr * 2.2, 12, 1, true), grey); e.position.set(n > 1 ? Math.cos(a) * r : 0, y - nr * 1.1, n > 1 ? Math.sin(a) * r : 0); grp.add(e); } }
    function f9core(grp, nose) {
      grp.add(chCyl(1.83, 1.83, 35, white, 0)); grp.add(chCyl(1.85, 1.85, 6.2, black, 35));
      engines(grp, 1.2, 8, 0, 0.42); engines(grp, 0, 1, 0, 0.42);
      for (var i = 0; i < 4; i++) {   /* landing legs, folded along the core */
        var a = i * Math.PI / 2 + Math.PI / 4, pv = new T.Group(); pv.position.set(Math.cos(a) * 1.9, 0.8, Math.sin(a) * 1.9); pv.rotation.y = -a; pv.userData.a = a;
        var leg = new T.Mesh(new T.BoxGeometry(0.35, 9.5, 0.9), black); leg.position.y = 4.75; pv.add(leg); grp.add(pv); R.legs.push(pv);
        var fin = new T.Mesh(new T.BoxGeometry(1.5, 0.2, 1.2), grey); fin.position.set(Math.cos(a) * 2.5, 39.6, Math.sin(a) * 2.5); fin.rotation.y = -a; grp.add(fin); R.fins.push(fin);
      }
      if (nose) grp.add(chOgive(1.83, 6, white, 41.2));
    }
    var h = 70, d = 3.7, sep = 41.2;
    if (kind === "f9" || kind === "fh") {
      f9core(B, false);
      U.add(chCyl(1.83, 1.83, 12.6, white, sep)); var mv = new T.Mesh(new T.CylinderGeometry(0.4, 1.3, 3.2, 20, 1, true), grey); mv.position.y = sep - 1.2; U.add(mv);
      F.add(chCyl(2.6, 2.6, 6.5, white, sep + 12.6)); F.add(chOgive(2.6, 6.6, white, sep + 19.1)); U.add(F);
      if (kind === "fh") {
        var S = new T.Group(); [-1, 1].forEach(function (sx) { var c = new T.Group(); f9core(c, true); c.position.x = sx * 4.2; S.add(c); }); R.side = S; B.add(S);
      }
      R.h = h; R.pl = [0.9, 26]; R.plU = [1.1, 22];
    } else if (kind === "starship") {
      B.add(chCyl(4.5, 4.5, 69.2, steel, 0)); B.add(chCyl(4.52, 4.52, 1.8, black, 69.2)); engines(B, 3.2, 20, 0, 0.7); engines(B, 1.6, 10, 0, 0.7); engines(B, 0, 3, 0, 0.7);
      for (var i = 0; i < 4; i++) { var a = i * Math.PI / 2 + Math.PI / 4, fin = new T.Mesh(new T.BoxGeometry(3.2, 0.4, 2.6), steel); fin.position.set(Math.cos(a) * 5.6, 66.5, Math.sin(a) * 5.6); fin.rotation.y = -a; B.add(fin); R.fins.push(fin); }
      sep = 71;
      U.add(chCyl(4.5, 4.5, 38, steel, sep)); U.add(chOgive(4.5, 12, steel, sep + 38));
      var hs = new T.Mesh(new T.CylinderGeometry(4.55, 4.55, 38, 32, 1, true, -Math.PI / 2, Math.PI), tile); hs.position.y = sep + 19; U.add(hs);
      [[sep + 2, 4.2, 6.5], [sep + 40, 2.4, 3.6]].forEach(function (f) { [-1, 1].forEach(function (sx) { var fl = new T.Mesh(new T.BoxGeometry(f[1], f[2], 0.35), tile); fl.position.set(sx * (4.5 + f[1] / 2), f[0] + f[2] / 2, 0); U.add(fl); }); });
      engines(U, 0, 1, sep, 0.9); h = 121; d = 9; R.h = h; R.pl = [3.4, 60]; R.plU = [1.6, 30];
    } else {
      var small = kind === "electron", s = small ? 0.33 : 0.75, m1 = small ? black : white;
      sep = 30 * s; B.add(chCyl(1.8 * s, 1.8 * s, sep, m1, 0)); engines(B, small ? 0.36 : 1.0, small ? 9 : 4, 0, small ? 0.13 : 0.45);
      U.add(chCyl(1.8 * s, 1.8 * s, 12 * s, m1, sep)); var mv2 = new T.Mesh(new T.CylinderGeometry(0.3 * s, 0.9 * s, 2.4 * s, 16, 1, true), grey); mv2.position.y = sep - 0.9 * s; U.add(mv2);
      F.add(chCyl(2.3 * s, 2.3 * s, 6 * s, white, sep + 12 * s)); F.add(chOgive(2.3 * s, 6 * s, white, sep + 18 * s)); U.add(F);
      h = 54 * s; d = 3.6 * s; R.h = h; R.pl = [small ? 0.5 : 1.2, small ? 10 : 28]; R.plU = [small ? 0.3 : 0.7, small ? 6 : 16];
    }
    R.sepY = sep; R.d = d;
    R.plumeB = chPlume(R.pl[0], R.pl[1]); B.add(R.plumeB);
    R.plumeU = chPlume(R.plU[0], R.plU[1]); R.plumeU.position.y = sep - (kind === "starship" ? 1.8 : 2.6); U.add(R.plumeU);
    if (R.side) { R.plumeS = [chPlume(R.pl[0], R.pl[1]), chPlume(R.pl[0], R.pl[1])]; R.plumeS[0].position.x = -4.2; R.plumeS[1].position.x = 4.2; R.side.add(R.plumeS[0]); R.side.add(R.plumeS[1]); }
    /* both stages live in their own holders so they can fly apart after staging */
    R.hb = new T.Group(); R.hb.add(B); R.hu = new T.Group(); R.hu.add(U); U.position.y = -sep;
    return R;
  }
  function chPad(withTower, rh, rd) {
    var g = new T.Group(), conc = chMat(0x8d9096, { roughness: 0.95 }), pr = withTower ? Math.max(20, rh * 0.9) : 75;
    g.add(chCyl(pr, pr * 1.06, 4, conc, -5, 48));
    if (withTower) {
      var tw = chMat(0x6b6f77, { roughness: 0.7, metalness: 0.4 }), th = rh * 1.12, tw2 = Math.max(2.5, rd * 2.2), off = rd * 0.5 + tw2 * 0.5 + rd * 1.4;
      var t = new T.Mesh(new T.BoxGeometry(tw2, th, tw2), tw); t.position.set(off, th / 2 - 1, 0); g.add(t);
      var arm = new T.Mesh(new T.BoxGeometry(off - rd * 0.5, Math.max(0.6, rd * 0.4), Math.max(1, rd * 0.6)), tw); arm.position.set((off + rd * 0.5) / 2, rh * 0.82, 0); g.add(arm);
    }
    var ring = new T.Mesh(new T.RingGeometry(16, 18, 48), new T.MeshBasicMaterial({ color: 0xE8ECF5, side: T.DoubleSide })); ring.rotation.x = -Math.PI / 2; ring.position.y = -0.9; if (!withTower) g.add(ring);
    return g;
  }
  function chShip() {
    var g = new T.Group(), deck = chMat(0x30343b, { roughness: 0.9 }), hull = chMat(0x1b1e24, { roughness: 0.8 });
    var h = new T.Mesh(new T.BoxGeometry(52, 6, 91), hull); h.position.y = -4.4; g.add(h);
    var d = new T.Mesh(new T.BoxGeometry(52, 0.4, 91), deck); d.position.y = -1.2; g.add(d);
    var ring = new T.Mesh(new T.RingGeometry(14, 16.5, 48), new T.MeshBasicMaterial({ color: 0xE8ECF5, side: T.DoubleSide })); ring.rotation.x = -Math.PI / 2; ring.position.y = -0.95; g.add(ring);
    [-1, 1].forEach(function (s) { var w = new T.Mesh(new T.BoxGeometry(2, 4, 91), hull); w.position.set(s * 26, 0.6, 0); g.add(w); });
    return g;
  }
  function chPlace(obj, p, upDir, fwd) {   /* Earth-fixed placement: local +Y along upDir */
    obj.position.set(p[0], p[1], p[2]);
    var q = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(upDir[0], upDir[1], upDir[2]));
    obj.quaternion.copy(q);
  }
  function chEarthPatch(tex, lon, lat, half) {
    var dlon = Math.min(60, half / Math.max(0.15, Math.cos(lat * D2R)));
    var lat0 = Math.max(-89, lat - half), lat1 = Math.min(89, lat + half);
    var ps = (lon - dlon + 180) * D2R, pl = 2 * dlon * D2R, ts = (90 - lat1) * D2R, tl = (lat1 - lat0) * D2R;
    var g = new T.SphereGeometry(ER, mob ? 140 : 200, mob ? 140 : 200, ps, pl, ts, tl), uv = g.attributes.uv;
    for (var i = 0; i < uv.count; i++) { var u = uv.getX(i), v = 1 - uv.getY(i); uv.setXY(i, (ps + u * pl) / (2 * Math.PI), 1 - (ts + v * tl) / Math.PI); }
    return new T.Mesh(g, new T.MeshPhongMaterial({ map: tex, shininess: 6, specular: 0x111111 }));
  }
  function chInit(host) {
    try {
      C.r = new T.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true, powerPreference: "high-performance" });
    } catch (e) { return false; }
    C.r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); C.r.outputEncoding = T.sRGBEncoding;
    C.scene = new T.Scene(); C.scene.background = new T.Color(0x000000);
    C.cam = new T.PerspectiveCamera(50, 1, 0.5, 2e8);
    C.world = new T.Group(); C.world.matrixAutoUpdate = false; C.scene.add(C.world);
    var tex = new T.TextureLoader().load("/api/netmap/planets/earth.jpg"); tex.encoding = T.sRGBEncoding; tex.wrapS = T.RepeatWrapping; tex.anisotropy = 4; C.tex = tex;
    C.earth = new T.Mesh(new T.SphereGeometry(ER * 0.9996, 128, 64), new T.MeshPhongMaterial({ map: tex, shininess: 6, specular: 0x111111 })); C.world.add(C.earth);
    C.atm = new T.Mesh(new T.SphereGeometry(ER * 1.016, 96, 48), new T.MeshBasicMaterial({ color: 0x5d8fdc, transparent: true, opacity: 0.16, side: T.BackSide, depthWrite: false, blending: T.AdditiveBlending })); C.world.add(C.atm);
    C.sun = new T.DirectionalLight(0xffffff, 1.25); C.scene.add(C.sun); C.scene.add(C.sun.target);
    C.scene.add(new T.HemisphereLight(0xbcd2ff, 0x30302c, 0.55));
    C.fill = new T.PointLight(0xffffff, 0.45, 0, 0); C.cam.add(C.fill); C.scene.add(C.cam);
    /* stars: fixed to the camera, no parallax */
    var sp = []; for (var i = 0; i < 1600; i++) { var z = Math.random() * 2 - 1, a = Math.random() * 6.283, r = Math.sqrt(1 - z * z); sp.push(r * Math.cos(a) * 1e8, z * 1e8, r * Math.sin(a) * 1e8); }
    var sg = new T.BufferGeometry(); sg.setAttribute("position", new T.Float32BufferAttribute(sp, 3));
    C.stars = new T.Points(sg, new T.PointsMaterial({ color: 0xffffff, size: 1.3, sizeAttenuation: false, transparent: true, opacity: 0.8, depthWrite: false })); C.stars.frustumCulled = false; C.scene.add(C.stars);
    function line(col) { var g = new T.BufferGeometry(); g.setAttribute("position", new T.BufferAttribute(new Float32Array(3 * 2400), 3)); g.setDrawRange(0, 0); var l = new T.Line(g, new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0.85 })); l.frustumCulled = false; C.world.add(l); return l; }
    C.trailU = line(0xE8ECF5); C.trailB = line(0x4FC3F7); C.trailO = line(0x7d8699);
    host.appendChild(C.r.domElement);
    C.ctl = new T.OrbitControls(C.cam, C.r.domElement); C.ctl.enableDamping = true; C.ctl.dampingFactor = 0.09; C.ctl.zoomSpeed = 1.1; C.ctl.rotateSpeed = mob ? 0.7 : 0.9;
    C.ctl.enablePan = false; C.ctl.maxDistance = 4.5e7;
    C.ctl.touches = { ONE: T.TOUCH.ROTATE, TWO: T.TOUCH.DOLLY_ROTATE };
    return true;
  }
  function chBuildMission(L) {
    if (C.mis) { C.world.remove(C.mis); C.mis.traverse(function (o) { if (o.geometry) o.geometry.dispose(); }); }
    var g = C.mis = new T.Group(); C.world.add(g);
    C.kind = chKind(L); C.R = chRocket(C.kind); g.add(C.R.hb); g.add(C.R.hu);
    var pad = chPos(L.pad_lon, L.pad_lat, 0), padN = chN(pad);
    var pm = chPad(true, C.R.h, C.R.d); chPlace(pm, pad, padN); g.add(pm);
    var b = L.booster, land = L.landing; C.site = null; C.bOff = 0;
    if (b.length) {
      var e = b[b.length - 1], lp = chPos(e[0], e[1], 0), ship = land && /asds|droneship/i.test(String(land.type || ""));
      var sm = ship ? chShip() : chPad(false, 0, 0), ln = chN(lp); C.bOff = ship ? 3 : 0;
      chPlace(sm, ship ? [lp[0] + ln[0] * 3, lp[1] + ln[1] * 3, lp[2] + ln[2] * 3] : lp, ln); g.add(sm);
      C.site = { p: lp, name: (land && (land.where || land.name)) || "Landing site", ship: ship, k: land && land.success === false ? "landfail" : "land" };
    }
    var cl = b.length ? [(L.pad_lon + b[b.length - 1][0]) / 2, (L.pad_lat + b[b.length - 1][1]) / 2] : [L.pad_lon, L.pad_lat];
    var half = b.length ? Math.max(3, Math.min(9, Math.hypot(b[b.length - 1][0] - L.pad_lon, b[b.length - 1][1] - L.pad_lat) * 0.7 + 2)) : 3;
    g.add(chEarthPatch(C.tex, cl[0], cl[1], half));
    /* orbit preview line (modeled propagation) */
    chOrbitSetup(L);
    var ends = L.ascent[L.ascent.length - 1][3];
    C.tAsc = Math.max(chEvT("seco") || 0, chLandT() || 0, chSepT() + 60) + 25;
    C.tAsc = Math.min(C.tAsc, ends);
    C.tEnd = C.orb ? ends + C.orbits * C.orbP : ends;
    if (!C.orb && C.L.booster.length) C.tEnd = Math.max(C.tEnd, chLandT() + 20);
    /* timeline ticks */
    var tk = [], sep = chSepT();
    L.labels.forEach(function (x) {
      if (x.k === "orbit") { if (C.orb) tk.push({ t: x.t, k: "orbit", n: "Orbit insertion (modeled)" }); return; }
      var nm = { liftoff: "Liftoff", maxq: "Max-Q", sep: "Stage separation", seco: "Second-stage cutoff (SECO)", fail: "Failure" }[x.k] || x.text;
      if (x.k === "land" || x.k === "landfail") nm = x.text.replace(/\s*T\+\d+:\d+.*$/, "");
      tk.push({ t: x.t, k: x.k, n: nm });
    });
    if (!L.labels.some(function (x) { return x.k === "meco"; })) tk.push({ t: Math.max(0, sep - 3), k: "meco", n: "Main engine cutoff (MECO)" });
    var lt = chLandT();
    if (lt != null) {
      if (L.landing && /rtls/i.test(L.landing.type || "")) tk.push({ t: sep + 14, k: "burn", n: "Boostback burn (modeled)" });
      tk.push({ t: lt - 75, k: "burn", n: "Entry burn (modeled)" }); tk.push({ t: lt - 28, k: "burn", n: "Landing burn (modeled)" });
    }
    if (C.orb) for (var i = 1; i <= C.orbits; i++) tk.push({ t: ends + i * C.orbP, k: "orbitn", n: "Orbit " + i + " complete" });
    tk.sort(function (a, z) { return a.t - z.t; }); C.ticks = tk;
  }

  /* ---------- time mapping: first 60% of the scrubber is the ascent, the rest the orbits ---------- */
  function chSplit() { return C.tEnd > C.tAsc + 60 ? 0.6 : 1; }
  function chT2S(t) { var s = chSplit(); return t <= C.tAsc || s >= 1 ? Math.min(1, t / (s >= 1 ? C.tEnd : C.tAsc)) * s : s + (1 - s) * (t - C.tAsc) / (C.tEnd - C.tAsc); }
  function chS2T(x) { var s = chSplit(); return x <= s ? x / s * (s >= 1 ? C.tEnd : C.tAsc) : C.tAsc + (x - s) / (1 - s) * (C.tEnd - C.tAsc); }
  function chRate() {
    if (C.speed) return C.speed;
    if (C.live) return 1;
    if (C.t < 20) return 2;
    if (C.t < C.tAsc) return 6;
    return Math.max(60, C.orbP / 30);   /* about 30 s per orbit */
  }

  /* ---------- UI ---------- */
  function chUi(host) {
    C.hud = document.createElement("div"); C.hud.className = "nx-ch-hud"; host.appendChild(C.hud);
    C.info = document.createElement("div"); C.hud.appendChild(C.info);
    C.ev = document.createElement("div"); C.ev.className = "nx-ch-ev"; C.hud.appendChild(C.ev);
    C.note = document.createElement("div"); C.note.className = "nx-ch-note"; C.note.textContent = "Modeled trajectory, not telemetry \u00b7 Launch data: The Space Devs Launch Library 2"; C.hud.appendChild(C.note);
    C.tagS = document.createElement("div"); C.tagS.className = "nx-ch-tag"; host.appendChild(C.tagS);
    C.tl = document.createElement("div"); C.tl.className = "nx-ch-tl"; C.tl.setAttribute("role", "group"); C.tl.setAttribute("aria-label", "Launch replay"); host.appendChild(C.tl);
    C.tl.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return; e.stopPropagation();
      if (b.dataset.a === "play") { if (!C.playing && C.t >= C.tEnd - 0.5) C.t = 0; C.playing = !C.playing; C.live = false; chBarSync(); }
      else if (b.dataset.a === "spd") { var seq = [0, 1, 10, 100], i = seq.indexOf(C.speed); C.speed = seq[(i + 1) % seq.length]; C.live = false; chBarSync(); }
      else if (b.dataset.f) { C.focus = b.dataset.f; chBarSync(); }
      else if (b.dataset.tk != null) { var k = C.ticks[+b.dataset.tk]; if (k) { C.t = k.t; C.live = false; chBarSync(); } }
    });
    C.tl.addEventListener("input", function (e) { if (e.target.type !== "range") return; C.t = chS2T(+e.target.value / 10000); C.live = false; C.scrub = true; chBarSync(); });
    C.tl.addEventListener("pointerdown", function (e) { if (e.target.type === "range") { C.wasPlaying = C.playing; C.playing = false; } });
    C.tl.addEventListener("change", function (e) { if (e.target.type === "range") { C.scrub = false; if (C.wasPlaying) C.playing = true; C.wasPlaying = false; chBarSync(); } });
    ["pointerdown", "touchstart", "wheel", "click"].forEach(function (n) { C.tl.addEventListener(n, function (e) { e.stopPropagation(); }, { passive: true }); });
  }
  function chBarHtml() {
    var hasB = C.L.booster.length > 0;
    var ticks = C.ticks.map(function (k, i) { return '<button type="button" class="nx-ch-tk k-' + chEsc(k.k) + '" data-tk="' + i + '" style="left:' + (100 * chT2S(k.t)).toFixed(2) + '%" title="' + chEsc(k.n + " \u00b7 " + chTPlus(k.t)) + '" aria-label="' + chEsc(k.n) + '"></button>'; }).join("");
    C.tl.innerHTML = '<div class="nx-ch-r"><button type="button" data-a="play" aria-label="Play">\u25B6</button><span class="tp">T+0:00</span>' +
      '<div class="nx-ch-sc">' + ticks + '<input type="range" min="0" max="10000" value="0" aria-label="Mission time"></div>' +
      '<button type="button" data-a="spd" aria-label="Playback speed">Auto</button>' +
      (hasB ? '<span class="nx-ch-f"><span>Follow</span><button type="button" data-f="auto" aria-pressed="false">Auto</button><button type="button" data-f="upper" aria-pressed="false">' + (C.kind === "starship" ? "Ship" : "Upper stage") + '</button><button type="button" data-f="booster" aria-pressed="false">Booster</button></span>' : "") + "</div>";
  }
  function chBarSync() {
    if (!C.tl) return;
    var r = C.tl.querySelector("input[type=range]"); if (r && !C.scrub) r.value = String(Math.round(10000 * chT2S(C.t)));
    var tp = C.tl.querySelector(".tp"); if (tp) tp.textContent = chTPlus(C.t);
    var pb = C.tl.querySelector('[data-a="play"]'); if (pb) { pb.textContent = C.playing ? "\u275A\u275A" : "\u25B6"; pb.setAttribute("aria-label", C.playing ? "Pause" : "Play"); }
    var sb = C.tl.querySelector('[data-a="spd"]'); if (sb) sb.textContent = C.speed ? C.speed + "\u00d7" : (C.live ? "Live" : "Auto");
    C.tl.querySelectorAll("[data-f]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.f === C.focus ? "true" : "false"); });
  }

  /* ---------- per-frame state ---------- */
  function chDir(fn, t, dt) { var a = fn(t - dt), b = fn(t + dt); return a && b ? chN(chSub(b, a)) : null; }
  function chState(t) {
    var L = C.L, R = C.R, sep = chSepT(), hasB = L.booster.length > 0, landT = chLandT(), fail = chEvT("fail");
    var staged = t >= sep, up = chUpper(t), upN = chN(up);
    /* upper stage (or full stack before staging) */
    var dU = t < 4 ? upN : (chDir(chUpper, t, 3) || upN);
    var w = Math.min(1, t / 12); dU = chN([upN[0] * (1 - w) + dU[0] * w, upN[1] * (1 - w) + dU[1] * w, upN[2] * (1 - w) + dU[2] * w]);
    var s = { t: t, up: up, dU: dU, staged: staged };
    if (hasB && staged) {
      var bp = chBooster(t), wS = Math.max(0, Math.min(1, (t - sep) / 45)); wS = wS * wS * wS;
      if (wS < 1) { var ua = chUpper(t); bp = [ua[0] * (1 - wS) + bp[0] * wS, ua[1] * (1 - wS) + bp[1] * wS, ua[2] * (1 - wS) + bp[2] * wS]; }   /* booster starts where the stack was */
      var bN = chN(bp), v = chDir(chBooster, Math.min(t, landT - 1), 2) || bN, tl = landT - t;
      var nose = t < sep + 12 ? dU : [-v[0], -v[1], -v[2]];   /* flip, then engines first */
      if (t >= sep + 12 && t < sep + 22) { var f = (t - sep - 12) / 10; nose = chN([dU[0] * (1 - f) - v[0] * f, dU[1] * (1 - f) - v[1] * f, dU[2] * (1 - f) - v[2] * f]); }
      if (tl < 25) { var g2 = Math.max(0, Math.min(1, (25 - tl) / 15)); nose = chN([nose[0] * (1 - g2) + bN[0] * g2, nose[1] * (1 - g2) + bN[1] * g2, nose[2] * (1 - g2) + bN[2] * g2]); }
      if (t >= landT) nose = bN;
      s.bp = bp; s.dB = nose; s.landed = t >= landT;
    } else if (staged) { s.bp = null; }
    s.fail = fail != null && t >= fail;
    return s;
  }
  function chOrient(obj, p, d) {
    obj.position.set(p[0], p[1], p[2]);
    obj.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(d[0], d[1], d[2]));
  }
  function chTrail(line, fn, t0, t1, step, ref) {
    var a = line.geometry.attributes.position, n = 0, max = a.count;
    if (t1 > t0) {
      var st = Math.max(step, (t1 - t0) / (max - 2));
      for (var t = t0; t < t1 && n < max - 1; t += st) { var p = fn(t); if (!p) continue; a.setXYZ(n++, p[0] - ref[0], p[1] - ref[1], p[2] - ref[2]); }
      var q = fn(t1); if (q) a.setXYZ(n++, q[0] - ref[0], q[1] - ref[1], q[2] - ref[2]);
    }
    line.position.set(ref[0], ref[1], ref[2]); a.needsUpdate = true; line.geometry.setDrawRange(0, n);
  }
  function chSunDir(ms) {
    var d = new Date(ms), doy = (Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5;
    var dec = 23.44 * Math.sin(2 * Math.PI * (doy - 81) / 365), hrs = d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600;
    return chN(chPos(-(hrs - 12) * 15, dec, 0));
  }
  function chFrame(now) {
    if (!C.open) return;
    C.raf = requestAnimationFrame(chFrame);
    var dt = Math.min(0.1, (now - (C.last || now)) / 1000); C.last = now;
    if (C.playing) { C.t = Math.min(C.tEnd, C.t + dt * chRate()); if (C.t >= C.tEnd) C.playing = false; }
    var L = C.L, R = C.R, s = chState(C.t), sep = chSepT(), landT = chLandT();
    /* place vehicle parts */
    if (!s.staged) {
      chOrient(R.hb, s.up, s.dU); R.hb.visible = true; R.hb.add(R.hu); R.hu.position.set(0, R.sepY, 0); R.hu.quaternion.identity();
    } else {
      if (R.hu.parent !== C.mis) C.mis.add(R.hu);
      var up = s.up, d = s.dU, dsep = Math.max(0, Math.min(1, (C.t - sep) / 6)) * Math.max(4, R.h * 0.25);   /* stages drift apart over the first seconds */
      chOrient(R.hu, [up[0] + d[0] * (R.sepY + dsep), up[1] + d[1] * (R.sepY + dsep), up[2] + d[2] * (R.sepY + dsep)], d);
      if (s.bp) { R.hb.visible = true; chOrient(R.hb, s.bp, s.dB); }
      else if (C.t < sep + 40) { R.hb.visible = true; var tb = sep + (C.t - sep) * 0.6; chOrient(R.hb, chUpper(tb), chDir(chUpper, tb, 3) || d); }   /* expendable stage falls behind */
      else R.hb.visible = false;
    }
    if (R.side) R.side.visible = C.t < sep - 20 || !!s.bp;
    R.fairing.visible = C.t < sep + 45;
    /* legs and grid fins */
    var legOut = landT != null && C.t > landT - 9 ? Math.min(1, (C.t - (landT - 9)) / 3) : 0;
    R.legs.forEach(function (p) { p.rotation.set(0, -p.userData.a, -1.75 * legOut); });
    /* burns (modeled) */
    var fl = 0.92 + Math.random() * 0.16, thin = Math.min(1, Math.max(0, (s.up && chLL(s.up)[2]) / 60000));
    var bBurn = !s.staged ? C.t < sep - 3 && !s.fail : !!s.bp && landT != null && ((C.t > sep + 14 && C.t < sep + 40 && L.landing && /rtls/i.test(L.landing.type || "")) || (C.t > landT - 75 && C.t < landT - 58) || (C.t > landT - 28 && C.t < landT));
    var uBurn = s.staged && C.t > sep + 4 && C.t < (chEvT("seco") || sep + 360) && !s.fail;
    R.plumeB.visible = bBurn; R.plumeB.scale.set(fl * (1 + thin * (s.staged ? 0 : 1.8)), fl, fl * (1 + thin * (s.staged ? 0 : 1.8)));
    if (R.plumeS) R.plumeS.forEach(function (p) { p.visible = bBurn && !s.staged; p.scale.copy(R.plumeB.scale); });
    R.plumeU.visible = uBurn; R.plumeU.scale.set(fl * 2.2, fl * 1.3, fl * 2.2);
    /* focus */
    var auto = s.staged && s.bp && !s.landed ? "booster" : s.staged && s.bp && C.t < landT + 12 ? "booster" : "upper";
    var who = C.focus === "auto" ? auto : C.focus; if (who === "booster" && !s.bp) who = "upper";
    var obj = who === "booster" ? R.hb : (s.staged ? R.hu : R.hb), hgt = who === "booster" ? R.sepY : (s.staged ? R.h - R.sepY : R.h);
    var org = obj.position, dir = who === "booster" ? s.dB : s.dU, cy = hgt / 2;   /* each holder's origin sits at its stage base */
    var fp = [org.x + dir[0] * cy, org.y + dir[1] * cy, org.z + dir[2] * cy];
    if (C.who !== who) { C.who = who; C.ctl.minDistance = Math.max(4, hgt * 0.35); }
    /* world matrix: focus at the origin, local east = +X, up = +Y, north = -Z */
    var f = chENU(fp), M = C.world.matrix;
    M.set(f.e[0], f.e[1], f.e[2], -chD(f.e, fp), f.u[0], f.u[1], f.u[2], -chD(f.u, fp), -f.n[0], -f.n[1], -f.n[2], chD(f.n, fp), 0, 0, 0, 1);
    C.world.matrixWorldNeedsUpdate = true;
    /* trails, rebased on the focus for float precision */
    var ascEnd = L.ascent[L.ascent.length - 1][3];
    chTrail(C.trailU, chUpper, 0, C.t, C.t > ascEnd ? 20 : 1, fp);
    if (L.booster.length && s.staged) chTrail(C.trailB, chBooster, sep, Math.min(C.t, landT), 1, fp); else C.trailB.geometry.setDrawRange(0, 0);
    if (C.orb && C.t > ascEnd - 200) chTrail(C.trailO, chUpper, C.t, Math.min(C.tEnd, C.t + C.orbP), 30, fp); else C.trailO.geometry.setDrawRange(0, 0);
    /* sun, sky */
    var sd = chSunDir(Date.parse(L.net) + C.t * 1000), wsd = new T.Vector3(sd[0], sd[1], sd[2]).applyMatrix4(new T.Matrix4().extractRotation(M));
    C.sun.position.copy(wsd).multiplyScalar(1e6); C.sun.target.position.set(0, 0, 0);
    var camW = C.cam.position, alt = chLL(fp)[2] + camW.y, air = Math.max(0, Math.min(1, 1 - alt / 70000)), day = Math.max(0, Math.min(1, chD(f.u, sd) * 4 + 0.35));
    C.scene.background.setRGB(0.36 * air * day, 0.56 * air * day, 0.85 * air * day);
    C.stars.material.opacity = 0.85 * (1 - air * day);
    C.ctl.update(); C.cam.updateMatrixWorld();
    C.r.render(C.scene, C.cam);
    chHud(s, who, fp);
    if (C.playing || C.scrub || C.uiT === undefined || now - C.uiT > 200) { C.uiT = now; chBarSync(); }
  }
  function chHud(s, who, fp) {
    var L = C.L, ll = chLL(who === "booster" && s.bp ? s.bp : s.up), fn = who === "booster" && s.bp ? chBooster : chUpper;
    var a = fn(C.t - 0.5), b = fn(C.t + 0.5), v = a && b ? Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) : 0;
    if (C.t > L.ascent[L.ascent.length - 1][3] && who !== "booster") v = Math.sqrt(MU / (ER + ll[2]));
    if (who === "booster" && s.landed) v = 0;
    var orb = C.orb && C.t > L.ascent[L.ascent.length - 1][3] ? Math.floor((C.t - L.ascent[L.ascent.length - 1][3]) / C.orbP) + 1 : 0;
    C.info.innerHTML = "<b>" + chEsc(chMis(L)) + '</b><div class="m">' + chEsc(chVeh(L)) + " \u00b7 " + chEsc(L.pad || "") + "</div>" +
      '<div class="n">' + chTPlus(C.t) + " \u00b7 " + (who === "booster" ? "Booster" : s.staged ? (C.kind === "starship" ? "Ship" : "Upper stage") : "Full stack") + "</div>" +
      '<div class="n">Altitude ' + chEsc(chAlt(Math.max(0, ll[2]))) + " \u00b7 Speed " + chEsc(chSpd(v)) + "</div>" + (orb ? '<div class="n">Orbit ' + Math.min(orb, C.orbits) + " of " + C.orbits + " (modeled)</div>" : "");
    /* only the current event, never a pile of labels */
    var cur = null; C.ticks.forEach(function (k) { if (k.t <= C.t + 0.01) cur = k; });
    var txt = cur ? cur.n + " \u00b7 " + chTPlus(cur.t) : "On the pad";
    if (C.evTxt !== txt) { C.evTxt = txt; C.ev.textContent = txt; C.ev.className = "nx-ch-ev" + (cur ? " k-" + cur.k : ""); }
    /* one tag for the landing site, only while it is on screen */
    if (C.site) {
      var p = new T.Vector3(C.site.p[0], C.site.p[1], C.site.p[2]).applyMatrix4(C.world.matrix), dist = p.distanceTo(C.cam.position);
      p.project(C.cam); var host = C.host, w = host.clientWidth, h = host.clientHeight;
      if (p.z < 1 && Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && dist < 2.5e6 && C.t >= chSepT()) {
        C.tagS.className = "nx-ch-tag k-" + (s.landed ? C.site.k : "land"); C.tagS.textContent = C.site.name + (C.site.ship ? " (droneship)" : " (landing zone)");
        C.tagS.style.transform = "translate(" + Math.round((p.x + 1) / 2 * w + 8) + "px," + Math.round((1 - p.y) / 2 * h - 7) + "px)";
      } else C.tagS.style.transform = "translate(-9999px,0)";
    }
  }
  function chResize() { if (!C.r || !C.host) return; var w = C.host.clientWidth || 1, h = C.host.clientHeight || 1; C.r.setSize(w, h, false); C.cam.aspect = w / h; C.cam.updateProjectionMatrix(); }

  /* ---------- public ---------- */
  function chOpen(L, opt) {
    opt = opt || {};
    var map = window.__nxMap, cont = opt.container || (map && map.getContainer()); if (!cont || !L || !L.ascent || L.ascent.length < 2) return false;
    if (!C.host) {
      C.host = document.createElement("div"); C.host.className = "nx-ch"; cont.appendChild(C.host);
      if (!chInit(C.host)) { C.host.remove(); C.host = null; return false; }
      chUi(C.host); window.addEventListener("resize", chResize);
      ["click", "dblclick", "wheel", "pointerdown", "touchstart", "mousedown"].forEach(function (n) { C.host.addEventListener(n, function (e) { e.stopPropagation(); }, { passive: true }); });
    }
    C.L = L; C.focus = "auto"; C.who = null; C.speed = 0; C.scrub = false; C.evTxt = null;
    chBuildMission(L); chBarHtml();
    C.t = Math.max(0, Math.min(C.tEnd, opt.t || 0)); C.live = !!opt.live; C.playing = !reduce || C.live;
    /* start close on the rocket at the pad, slightly low and off to one side */
    var h = C.R.h; C.cam.position.set(h * 0.75, h * 0.12, h * 1.6); C.ctl.target.set(0, 0, 0); C.ctl.minDistance = Math.max(4, h * 0.35); C.ctl.update();
    C.host.hidden = false; C.open = true; document.body.classList.add("nx-lc-chase"); chResize(); C.last = 0;
    cancelAnimationFrame(C.raf); C.raf = requestAnimationFrame(chFrame); chBarSync();
    return true;
  }
  function chClose() {
    C.open = false; cancelAnimationFrame(C.raf); if (C.host) C.host.hidden = true; document.body.classList.remove("nx-lc-chase");
  }
  window.BNChase = { open: chOpen, close: chClose, state: C, isOpen: function () { return C.open; } };
})();
