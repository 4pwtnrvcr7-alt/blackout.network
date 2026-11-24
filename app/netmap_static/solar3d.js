/* Solar system explorer for The Grid Sky view (pt1828u, Nov 24 2026). Lazy-loaded by net.js after three147.js.
   Positions and trajectories: NASA/JPL Horizons (heliocentric ecliptic J2000) via /api/netmap/solar3d (server cache 6 h).
   Planet orbit rings: JPL "Approximate Positions of the Planets" Keplerian elements (J2000). Models are original, procedural,
   illustrative (not photos). Sizes and near-Earth offsets are exaggerated so everything is visible. */
(function (w) {
  "use strict";
  var T = w.THREE; if (!T || w.BNSolar) return;
  var d = document, S = {}, DATA = null, OBJ = {}, LIST = [], SEL = null, FLY = null, raf = 0, compressed = true, tries = 0;
  var MI_AU = 92955807.27, KM_AU = 149597870.7;
  var ELEM = { /* a, e, I, L, varpi, Omega (J2000, JPL approximate elements) */
    mercury: [0.38709927, 0.20563593, 7.00497902, 252.2503235, 77.45779628, 48.33076593],
    venus: [0.72333566, 0.00677672, 3.39467605, 181.9790995, 131.60246718, 76.67984255],
    earth: [1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0],
    mars: [1.52371034, 0.0933941, 1.84969142, -4.55343205, -23.94362959, 49.55953891],
    jupiter: [5.202887, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909],
    saturn: [9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448],
    uranus: [19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.9542763, 74.01692503],
    neptune: [30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574] };
  var PL = { mercury: [0.35, 0x9a9a9a], venus: [0.55, 0xd9c89a], earth: [0.6, 0x2f6fd1], mars: [0.45, 0xc1502e], jupiter: [1.6, 0xc9a27a], saturn: [1.35, 0xd8c48f], uranus: [1.0, 0x9fd6dc], neptune: [1.0, 0x3f62d6] };
  var PINFO = { mercury: "Closest planet to the Sun.", venus: "Hottest planet; thick CO2 atmosphere.", earth: "Home. Sun-watching spacecraft at L1 sit about 930,000 mi sunward.", mars: "The red planet.", jupiter: "Largest planet.", saturn: "Ringed gas giant.", uranus: "Ice giant tilted on its side.", neptune: "Outermost planet." };

  var PHOTOS = {"voyager1":{"c":"Voyager proof-test model, a full-scale twin of the flight craft, at JPL","by":"NASA/JPL-Caltech/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/PIA21477"},"voyager2":{"c":"Voyager 2 being encapsulated for launch, 1977","by":"NASA/JPL-Caltech","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/PIA21728"},"newhorizons":{"c":"New Horizons during processing at Kennedy, 2005","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-05pd2493"},"parker":{"c":"Parker Solar Probe solar array deployment test, Astrotech, 2018","by":"NASA/Kim Shiflett","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-20180603-PH_KLS01_0029"},"solo":{"c":"Solar Orbiter at Astrotech, Titusville, Dec 2019","by":"NASA/Frank Michaux","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-20191216-PH-FWM01_0149"},"soho":{"c":"SOHO during processing at Kennedy, 1995","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-95PC-1159"},"stereoa":{"c":"STEREO observatory at Astrotech, 2006","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-06pd1862"},"ace":{"c":"ACE during processing at Kennedy, 1997","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-97PC905"},"dscovr":{"c":"DSCOVR after arrival at Kennedy, 2014","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-314D-0517_0052"},"wind":{"c":"Wind spacecraft during processing at Kennedy, 1994","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-94PC-1147"},"jwst":{"c":"Webb's gold primary mirror at NASA Goddard","by":"NASA/Chris Gunn","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/GSFC_20171208_Archive_e000079"},"juno":{"c":"Juno during processing at Astrotech, 2011","by":"NASA/KSC","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-2011-3106"},"lucy":{"c":"Lucy at Astrotech before launch, 2021","by":"NASA/Ben Smegelsky","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-20210929-PH-JBS01_0093"},"psyche":{"c":"Psyche unwrapped at Astrotech, 2022","by":"NASA/Isaac Watson","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-20220503-PH-ILW01_0062"},"clipper":{"c":"Europa Clipper unboxed at Kennedy, 2024","by":"NASA/Kim Shiflett","lic":"Public domain (NASA)","src":"https://images.nasa.gov/details/KSC-20240528-PH-KLS01_0040"},"juice":{"c":"JUICE in the Airbus Astrolabe facility, Toulouse","by":"Don-vip (Wikimedia France)","lic":"CC BY-SA 4.0","src":"https://commons.wikimedia.org/wiki/File:JUICE_inside_Airbus_Defence_and_Space_Astrolabe_facilities_11.jpg"},"aditya":{"c":"Photo of an Aditya-L1 display model at an exhibition in Kolkata, 2022 (not the flight craft)","by":"Debapratim and Chinakpradhan","lic":"CC BY-SA 2.0","src":"https://commons.wikimedia.org/wiki/File:Aditya_L1.jpg"},"roadster":{"c":"Starman in the Roadster with Earth behind, 6 Feb 2018 (real photo)","by":"SpaceX","lic":"CC0 1.0","src":"https://commons.wikimedia.org/wiki/File:Elon_Musk%27s_Tesla_Roadster_(40143096241).jpg"}};
  function css() {
    if (d.getElementById("s3_css")) return;
    var st = d.createElement("style"); st.id = "s3_css";
    st.textContent = ".s3{position:fixed;inset:0;z-index:2147483000;background:#020306;color:#e8eaf0;font:13px/1.35 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;touch-action:none;overflow:hidden}" +
      ".s3 canvas{display:block;width:100%;height:100%}.s3-top{position:absolute;left:0;right:0;top:0;display:flex;gap:6px;align-items:center;padding:calc(env(safe-area-inset-top,0px) + 8px) 10px 6px;pointer-events:none}" +
      ".s3-top>*{pointer-events:auto}.s3 button{font:inherit;color:#e8eaf0;background:rgba(10,12,18,.72);border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:6px 11px;cursor:pointer;white-space:nowrap}" +
      ".s3 button[aria-pressed=true]{background:#e8eaf0;color:#05060a}.s3-sp{flex:1}.s3-k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.7}" +
      ".s3-objs{position:absolute;left:0;right:0;top:calc(env(safe-area-inset-top,0px) + 46px);display:flex;gap:6px;overflow-x:auto;padding:0 10px 4px;scrollbar-width:none}.s3-objs::-webkit-scrollbar{display:none}.s3-objs button{font-size:12px;padding:4px 9px}" +
      ".s3-lab{position:absolute;left:0;top:0;transform:translate(-50%,-130%);font-size:11px;padding:1px 6px;border-radius:8px;background:rgba(5,6,10,.55);color:#dfe3ec;white-space:nowrap;cursor:pointer;user-select:none}" +
      ".s3-lab.sc{color:#b9c6ff}.s3-lab.sel{background:#e8eaf0;color:#05060a}" +
      ".s3-info{position:absolute;left:10px;bottom:calc(env(safe-area-inset-bottom,0px) + 10px);max-width:min(420px,calc(100% - 20px));max-height:34%;overflow:auto;background:linear-gradient(90deg,rgba(5,6,10,.72),rgba(5,6,10,.35));border-left:2px solid rgba(255,255,255,.5);padding:6px 10px;font-size:12px}" +
      ".s3-info h3{margin:0 0 2px;font-size:15px}.s3-info p{margin:2px 0}.s3-info .s3-tag{display:inline-block;font-size:10px;border:1px solid rgba(255,255,255,.35);border-radius:6px;padding:0 5px;margin-left:6px;vertical-align:2px;opacity:.85}" +
      ".s3-info a{color:#b9c6ff}.s3-ph{margin:6px 0 2px}.s3-ph img{display:block;max-width:100%;max-height:42vh;width:auto;height:auto;object-fit:contain;margin:0 auto;border-radius:6px}.s3-ph figcaption{font-size:10.5px;opacity:.75;margin-top:2px}.s3 .s3-tog{display:inline-block;margin-left:8px;padding:1px 9px;font-size:11px;vertical-align:2px}.s3-info:not(.open) .s3-body{display:none}.s3-info:not(.open) h3{margin:0}.s3-info.open{max-height:62%}@media (max-width:600px){.s3-info{font-size:11.5px}.s3-info h3{font-size:14px}.s3-info.open{max-height:58%}.s3-ph img{max-height:34vh}}.s3-msg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);opacity:.8}";
    d.head.appendChild(st);
  }
  function imperial() { try { return !w.BNUnits || !w.BNUnits.isImperial || w.BNUnits.isImperial(); } catch (e) { return true; } }
  function big(n) { return n >= 1e9 ? (n / 1e9).toFixed(2) + " billion" : n >= 1e6 ? (n / 1e6).toFixed(1) + " million" : Math.round(n).toLocaleString("en-US"); }
  function fmtAU(au) { if (au == null) return "–"; var a = au >= 10 ? au.toFixed(1) : au >= 0.1 ? au.toFixed(3) : au.toFixed(4); return a + " AU (" + (imperial() ? big(au * MI_AU) + " mi" : big(au * KM_AU) + " km") + ")"; }
  function fmtV(kms) { if (kms == null) return "–"; return imperial() ? Math.round(kms * 2236.936).toLocaleString("en-US") + " mph" : Math.round(kms * 3600).toLocaleString("en-US") + " km/h"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function since(iso) { var t = Date.parse(iso + "T00:00:00Z"); if (!t) return ""; var days = (Date.now() - t) / 864e5, y = Math.floor(days / 365.25); return y + " yr " + Math.floor(days - y * 365.25) + " d"; }
  function rmap(r) { return compressed ? 20 * Math.pow(r, 0.45) : 20 * r; }
  function V(p) { /* ecliptic (x,y,z) AU -> scene (x, z up -> y) with radial scaling */
    var r = Math.sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]) || 1e-9, k = rmap(r) / r;
    return new T.Vector3(p[0] * k, p[2] * k, -p[1] * k);
  }
  function glowTex() {
    var c = d.createElement("canvas"); c.width = c.height = 128; var g = c.getContext("2d"), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, "rgba(255,250,235,1)"); gr.addColorStop(0.2, "rgba(255,225,170,.9)"); gr.addColorStop(0.45, "rgba(255,170,80,.35)"); gr.addColorStop(1, "rgba(255,140,40,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new T.CanvasTexture(c);
  }
  function bandTex(base, n) {
    var c = d.createElement("canvas"); c.width = 64; c.height = 128; var g = c.getContext("2d"), col = new T.Color(base);
    for (var i = 0; i < 128; i++) { var k = 0.82 + 0.18 * Math.sin(i / 128 * Math.PI * n) + (Math.random() - .5) * .06; g.fillStyle = "rgb(" + [col.r, col.g, col.b].map(function (v) { return Math.min(255, Math.round(v * 255 * k)); }).join(",") + ")"; g.fillRect(0, i, 64, 1); }
    return new T.CanvasTexture(c);
  }
  function M(c, o) { return new T.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.5, metalness: 0.1 }, o || {})); }
  function box(g, sx, sy, sz, mat, x, y, z) { var m = new T.Mesh(new T.BoxGeometry(sx, sy, sz), mat); m.position.set(x, y, z); g.add(m); return m; }

  /* ---------- Original procedural models (v1.2). Illustrative, not photos. Model units: Roadster ~4 long, x = forward, y = up, +z = right. ---------- */
  var ENV = null;
  function envMap() {
    if (ENV || !S.r) return ENV;
    try {
      var es = new T.Scene(), pm = new T.PMREMGenerator(S.r);
      es.add(new T.Mesh(new T.SphereGeometry(50, 32, 16), new T.MeshBasicMaterial({ color: 0x07090f, side: T.BackSide })));
      var sunM = new T.Mesh(new T.SphereGeometry(6, 16, 12), new T.MeshBasicMaterial({ color: 0xfff1d8 })); sunM.position.set(-40, 12, 0); es.add(sunM);
      var earthM = new T.Mesh(new T.SphereGeometry(10, 16, 12), new T.MeshBasicMaterial({ color: 0x1d3d78 })); earthM.position.set(30, -25, 20); es.add(earthM);
      var strip = new T.Mesh(new T.BoxGeometry(80, 1.5, 1.5), new T.MeshBasicMaterial({ color: 0x6f7686 })); strip.position.set(0, 30, -20); es.add(strip);
      ENV = pm.fromScene(es, 0.03).texture; pm.dispose();
    } catch (e) { ENV = null; }
    return ENV;
  }
  function P(c, o) { return new T.MeshPhysicalMaterial(Object.assign({ color: c, roughness: 0.45, metalness: 0.0, envMap: envMap(), envMapIntensity: 0.8 }, o || {})); }
  function ss(a, b, x) { var t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
  function limb(g, a, b, r, mat) {   /* capsule from point a to point b */
    var A = new T.Vector3().fromArray(a), B = new T.Vector3().fromArray(b), d = B.clone().sub(A), L = d.length();
    var m = new T.Mesh(new T.CapsuleGeometry(r, Math.max(0.001, L), 6, 14), mat);
    m.position.copy(A).add(B).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), d.normalize()); g.add(m); return m;
  }
  function at(g, geo, mat, x, y, z, rx, ry, rz) { var m = new T.Mesh(geo, mat); m.position.set(x, y, z); if (rx || ry || rz) m.rotation.set(rx || 0, ry || 0, rz || 0); g.add(m); return m; }
  /* Roadster v3 (pt1840u): rebuilt after the real 2008 Tesla Roadster (Lotus Elise based). Low, wide, short; tall front-fender
     humps over a dipped carbon-fibre hood; almond smoked headlights on the fender tops; slim slatted lower grille; twin roll hoops.
     Lofted superellipse cross-sections along x (x forward, y up, +z right; driver is left, -z). Original procedural geometry. */
  var BODY_N = 3.2, BX0 = -1.98, BX1 = 1.98, BWX = [[-1.18, 0.335], [1.17, 0.325]];
  function bHalf(x) {   /* plan-view half width: rounded bulbous nose, near-square tail, flared rear hips */
    var u = (x - BX0) / (BX1 - BX0), f = u > 0.5 ? Math.pow(Math.max(0, 1 - Math.pow((u - 0.5) * 2, 3.2)), 0.42) : Math.pow(Math.max(0, 1 - Math.pow((0.5 - u) * 2, 7)), 0.3);
    var w = 0.88 * f + 0.05 * Math.exp(-Math.pow((x + 1.12) / 0.45, 2)) + 0.03 * Math.exp(-Math.pow((x - 1.12) / 0.38, 2)) - 0.02 * Math.exp(-Math.pow((x + 0.15) / 0.42, 2));
    return w + 0.004;
  }
  function bTop(x, r) {   /* top height at relative lateral position r (0 centre .. 1 side) */
    if (x < -0.8) {        /* raised rear deck with rounded tail and slightly raised rear fender crowns */
      var deck = 0.92 + 0.03 * ss(0.4, 0.8, r) * (1 - ss(0.85, 1, r));
      return deck - 0.2 * (1 - ss(-1.98, -1.7, x));
    }
    if (x < 0.36) { var belt = 0.83; return belt + (0.92 - belt) * (1 - ss(-0.85, -0.68, x)); }   /* doors / belt line */
    /* front: fender crowns peak over the front wheel and stand well above the dipped hood valley */
    var fen = 0.83 + 0.07 * Math.exp(-Math.pow((x - 1.12) / 0.42, 2)) - 0.3 * ss(1.5, 1.98, x);
    var hood = 0.72 - 0.1 * ss(0.36, 1.5, x) - 0.2 * ss(1.5, 1.98, x);
    var crown = ss(0.18, 0.62, r) * (1 - 0.35 * ss(0.85, 1, r));
    return hood + (fen - hood) * crown;
  }
  function bBot(x, r) {   /* underside; wheel arches cut in only toward the sides (r > ~0.5) so they never poke through the hood */
    var u = (x - BX0) / (BX1 - BX0), b = 0.17 + 0.16 * (1 - ss(0, 0.07, u)) + 0.14 * ss(0.9, 1, u);
    BWX.forEach(function (w) { var dx = Math.abs(x - w[0]), R = w[1] + 0.06; if (dx < R) b = Math.max(b, b + (0.31 + Math.sqrt(R * R - dx * dx) * 0.97 - b) * ss(0.42, 0.62, r == null ? 1 : r)); });
    return b;
  }
  function bYC(t) { return Math.min(t - 0.06, 0.5); }
  function surfY(x, z) {   /* height of the top surface at (x, z) */
    var w = bHalf(x), Z = Math.min(0.999, Math.abs(z) / w), t = bTop(x, Z), yc = bYC(t);
    return yc + (t - yc) * Math.pow(1 - Math.pow(Z, BODY_N), 1 / BODY_N);
  }
  function inBody(x, y, z) {
    var w = bHalf(x); if (w <= 0.005) return false; var Z = Math.abs(z) / w; if (Z >= 1) return false;
    var t = bTop(x, Z), yc = bYC(t), Y = y >= yc ? (y - yc) / (t - yc) : (yc - y) / (yc - bBot(x, Z));
    return Math.pow(Z, BODY_N) + Math.pow(Math.abs(Y), BODY_N) <= 1;
  }
  function noseX(y, z) { for (var x = BX1; x > 1.2; x -= 0.003) if (inBody(x, y, z)) return x; return 1.2; }
  function carBody(mat) {
    var NX = 150, NA = 72, pos = [], idx = [];
    function cock(x) { return ss(-0.8, -0.7, x) * (1 - ss(0.2, 0.32, x)); }
    for (var i = 0; i <= NX; i++) {
      var u = i / NX, x = BX0 + (BX1 - BX0) * u, w = bHalf(x), cw = cock(x);
      for (var j = 0; j < NA; j++) {
        var th = j / NA * Math.PI * 2, c = Math.cos(th), s = Math.sin(th), n = BODY_N;
        var zz = Math.sign(c) * Math.pow(Math.abs(c), 2 / n), yy = Math.sign(s) * Math.pow(Math.abs(s), 2 / n), z = w * zz, r = Math.abs(zz);
        var t = bTop(x, r), yc = bYC(t), b = bBot(x, r), y;
        if (yy >= 0) {
          y = yc + (t - yc) * yy;
          var k = cw * (1 - ss(0.8, 0.9, r)) * ss(0.15, 0.7, yy);   /* open cockpit tub, floor at 0.3 */
          y = y + (0.3 - y) * k;
        } else y = yc + (yc - b) * yy;
        pos.push(x, y, z);
      }
    }
    for (i = 0; i < NX; i++) for (j = 0; j < NA; j++) {
      var a = i * NA + j, b2 = i * NA + (j + 1) % NA, c2 = (i + 1) * NA + j, d2 = (i + 1) * NA + (j + 1) % NA;
      idx.push(a, c2, b2, b2, c2, d2);
    }
    var geo = new T.BufferGeometry(); geo.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); geo.setIndex(idx); geo.computeVertexNormals();
    var m = new T.Mesh(geo, mat); m.material.side = T.DoubleSide; return m;
  }
  /* A panel that hugs the top surface: grid over (x, z) in [x0,x1] x [-1,1]*hw(x), kept where keep(x, z) is true, lifted by off. */
  function skin(x0, x1, hw, off, mat, nx, nz, zc) {
    var pos = [], idx = [], uv = []; nx = nx || 40; nz = nz || 20; zc = zc || 0;
    for (var i = 0; i <= nx; i++) for (var j = 0; j <= nz; j++) {
      var x = x0 + (x1 - x0) * i / nx, h = hw(x), z = zc + h * (2 * j / nz - 1);
      pos.push(x, surfY(x, z) + off, z); uv.push(i / nx, j / nz);
    }
    for (i = 0; i < nx; i++) for (j = 0; j < nz; j++) { var a = i * (nz + 1) + j, b = a + 1, c = a + nz + 1, e = c + 1; idx.push(a, b, c, b, e, c); }
    var geo = new T.BufferGeometry(); geo.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); geo.setAttribute("uv", new T.Float32BufferAttribute(uv, 2)); geo.setIndex(idx); geo.computeVertexNormals();
    var m = new T.Mesh(geo, mat); m.material.side = T.DoubleSide; return m;
  }
  function weaveTex() {   /* fine 2x2 twill for the bare carbon hood */
    var c = d.createElement("canvas"); c.width = c.height = 64; var g = c.getContext("2d"); g.fillStyle = "#26282c"; g.fillRect(0, 0, 64, 64);
    for (var y = 0; y < 16; y++) for (var x = 0; x < 16; x++) { g.fillStyle = ((x + y) >> 1) % 2 ? "#3a3d43" : "#1b1c1f"; g.fillRect(x * 4, y * 4, 4, 4); }
    var t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(10, 5); t.anisotropy = 8; return t;
  }
  function wheel(g, x, z, tire, rim) {   /* black alloy, 5 double spokes */
    var w = new T.Group(), sd = Math.sign(z); w.position.set(x, 0.31, z);
    var tr = at(w, new T.TorusGeometry(0.235, 0.085, 18, 48), tire, 0, 0, 0); tr.scale.set(1, 1, 1.5);
    at(w, new T.CylinderGeometry(0.205, 0.205, 0.2, 40, 1, true), rim, 0, 0, 0, Math.PI / 2);                 /* barrel */
    at(w, new T.TorusGeometry(0.2, 0.014, 8, 44), rim, 0, 0, sd * 0.1);                                    /* lip */
    for (var k = 0; k < 5; k++) [-0.11, 0.11].forEach(function (o) {
      var sp = new T.Mesh(new T.BoxGeometry(0.026, 0.165, 0.03), rim); sp.position.z = sd * 0.085; sp.rotation.z = k / 5 * Math.PI * 2 + o; sp.translateY(0.11); w.add(sp);
    });
    at(w, new T.CylinderGeometry(0.06, 0.06, 0.05, 20), rim, 0, 0, sd * 0.08, Math.PI / 2);                  /* hub */
    at(w, new T.CylinderGeometry(0.16, 0.16, 0.02, 32), P(0x3a3c40, { metalness: 0.9, roughness: 0.45 }), 0, 0, sd * 0.01, Math.PI / 2);   /* brake disc */
    g.add(w);
  }
  function roadster() {
    var g = new T.Group();
    var paint = P(0x8c0712, { metalness: 0.55, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.03, envMapIntensity: 1.25, sheen: 0.4, sheenColor: new T.Color(0xff3040) });
    var mirrorPaint = paint.clone(); mirrorPaint.side = T.FrontSide;
    var leather = P(0x111113, { roughness: 0.62 }), insert = P(0xb32a3e, { roughness: 0.6 }), carbon = P(0x2a2c30, { roughness: 0.28, metalness: 0.4, clearcoat: 1, clearcoatRoughness: 0.05, map: weaveTex() });
    var chrome = P(0xe4e8ee, { metalness: 1, roughness: 0.1 }), tire = P(0x0b0b0c, { roughness: 0.88 }), rim = P(0x17181a, { metalness: 0.7, roughness: 0.32, clearcoat: 0.6 }), black = P(0x060607, { roughness: 0.42 });
    var smoke = P(0x0d0f13, { metalness: 0.3, roughness: 0.03, clearcoat: 1, envMapIntensity: 1.6 });
    var glass = P(0x9fb9cc, { transparent: true, opacity: 0.22, roughness: 0.02, clearcoat: 1, side: T.DoubleSide, depthWrite: false });
    g.add(carBody(paint));
    /* bare carbon hood: windshield base to just above the nose, between the fender crowns */
    g.add(skin(0.34, 1.84, function (x) { return 0.36 - 0.14 * ss(0.5, 1.84, x); }, 0.006, carbon, 48, 16));
    /* almond smoked headlights on the front fender tops, angled outward, two round lamps each */
    [-1, 1].forEach(function (sd) {
      var cx = 1.66, cz = sd * 0.56, L = 0.2, Wd = 0.095, ang = -sd * 0.38, ca = Math.cos(ang), sa = Math.sin(ang), pos = [], idx = [], NR = 14, NT = 40;
      for (var i = 0; i <= NR; i++) for (var j = 0; j < NT; j++) {
        var th = j / NT * Math.PI * 2, rr = i / NR, ex = Math.cos(th), ez = Math.sin(th) * (0.62 + 0.38 * ex);   /* teardrop: fuller at the front */
        var lx = ex * L * rr, lz = ez * Wd * rr, x = cx + lx * ca - lz * sa * sd * 0, z = cz + lz + lx * sa;
        x = cx + lx * ca; z = cz + lx * sa + lz * ca;
        pos.push(x, surfY(x, z) + 0.012 + 0.012 * (1 - rr * rr), z);
      }
      for (i = 0; i < NR; i++) for (j = 0; j < NT; j++) { var a = i * NT + j, b = i * NT + (j + 1) % NT, c = a + NT, e = b + NT; idx.push(a, b, c, b, e, c); }
      var hg = new T.BufferGeometry(); hg.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); hg.setIndex(idx); hg.computeVertexNormals();
      var hm = new T.Mesh(hg, smoke); hm.material.side = T.DoubleSide; g.add(hm);
      [0.09, -0.05].forEach(function (o, k) {   /* two lamps along the lens */
        var x = cx + o * ca, z = cz + o * sa, y = surfY(x, z) + 0.014, nrm = new T.Vector3(surfY(x - 0.01, z) - surfY(x + 0.01, z), 0.02, surfY(x, z - 0.01) - surfY(x, z + 0.01)).normalize();
        var lp = new T.Group(); lp.position.set(x, y, z); lp.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), nrm); g.add(lp);
        at(lp, new T.CylinderGeometry(0.042 - k * 0.006, 0.042 - k * 0.006, 0.012, 24), chrome, 0, 0, 0);
        at(lp, new T.CylinderGeometry(0.028 - k * 0.005, 0.028 - k * 0.005, 0.016, 20), P(0xf4f6ff, { emissive: 0x9aa0b0, roughness: 0.05 }), 0, 0.002, 0);
      });
    });
    /* slim wide lower grille with black horizontal slats, small chrome T badge above it */
    (function () {
      var pos = [], idx = [], NZ = 40, NY = 6, Y0 = 0.33, Y1 = 0.42, HW = 0.5;
      for (var i = 0; i <= NZ; i++) for (var j = 0; j <= NY; j++) { var z = HW * (2 * i / NZ - 1), y = Y0 + (Y1 - Y0) * j / NY, hw = HW * (1 - 0.25 * Math.pow((y - Y0) / (Y1 - Y0), 2)); z = z * hw / HW; pos.push(noseX(y, z) + 0.004, y, z); }
      for (i = 0; i < NZ; i++) for (j = 0; j < NY; j++) { var a = i * (NY + 1) + j, b = a + 1, c = a + NY + 1, e = c + 1; idx.push(a, c, b, b, c, e); }
      var gg = new T.BufferGeometry(); gg.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); gg.setIndex(idx); gg.computeVertexNormals();
      var gm = new T.Mesh(gg, P(0x020203, { roughness: 0.9 })); gm.material.side = T.DoubleSide; g.add(gm);
      [0.35, 0.375, 0.4].forEach(function (y) {
        var pts = []; for (var k = 0; k <= 24; k++) { var z = 0.48 * (2 * k / 24 - 1); pts.push(new T.Vector3(noseX(y, z) + 0.01, y, z)); }
        g.add(new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(pts), 40, 0.006, 6, false), P(0x3a3c40, { metalness: 0.7, roughness: 0.3 })));
      });
      var bx = noseX(0.53, 0) + 0.008, bd = new T.Group(); bd.position.set(bx, 0.53, 0); bd.rotation.z = -0.5; g.add(bd);
      at(bd, new T.BoxGeometry(0.012, 0.018, 0.1), chrome, 0, 0.03, 0); at(bd, new T.BoxGeometry(0.012, 0.07, 0.018), chrome, 0, -0.01, 0);
    })();
    /* black louvered vents on the raised rear deck */
    for (var lv = 0; lv < 7; lv++) {
      var lx = -1.05 - lv * 0.085;
      g.add(skin(lx - 0.025, lx + 0.025, function () { return 0.34; }, 0.008, black, 2, 12));
    }
    /* open cockpit: tub floor, bulkhead, tunnel, cowl, dashboard */
    at(g, new T.BoxGeometry(1.1, 0.04, 1.45), carbon, -0.24, 0.3, 0);
    at(g, new T.BoxGeometry(0.05, 0.52, 1.5), black, -0.8, 0.6, 0);
    at(g, new T.BoxGeometry(0.85, 0.16, 0.18), carbon, -0.2, 0.38, 0);
    at(g, new T.BoxGeometry(0.42, 0.05, 1.5), black, 0.24, 0.68, 0);
    var dash = at(g, new T.CapsuleGeometry(0.12, 1.25, 6, 18), black, 0.32, 0.74, 0, Math.PI / 2, 0, 0); dash.scale.set(1.1, 1, 0.8);
    /* seats: black shells with red/pink centre inserts; driver left (-z), passenger right (+z) */
    [-0.37, 0.37].forEach(function (z) {
      var cu = at(g, new T.CapsuleGeometry(0.17, 0.2, 6, 14), leather, -0.45, 0.38, z, 0, 0, Math.PI / 2 - 0.12); cu.scale.set(0.55, 1, 1.35);
      var ci = at(g, new T.CapsuleGeometry(0.1, 0.16, 4, 10), insert, -0.44, 0.43, z, 0, 0, Math.PI / 2 - 0.12); ci.scale.set(0.35, 1, 1.1);
      var bk = at(g, new T.CapsuleGeometry(0.19, 0.42, 6, 14), leather, -0.66, 0.7, z, 0, 0, -0.36); bk.scale.set(0.42, 1, 1.3);
      var ins = at(g, new T.CapsuleGeometry(0.11, 0.36, 4, 10), insert, -0.6, 0.7, z, 0, 0, -0.36); ins.scale.set(0.3, 1, 1.15);
      [-0.22, 0.22].forEach(function (o) { at(g, new T.CapsuleGeometry(0.045, 0.36, 4, 8), leather, -0.62, 0.68, z + o, 0, 0, -0.36); });
      /* black roll hoop behind each seat */
      var hoop = at(g, new T.TorusGeometry(0.2, 0.034, 12, 32, Math.PI), black, -0.84, 0.86, z, 0, Math.PI / 2, 0); hoop.scale.set(1, 1.25, 1);
      [-0.2, 0.2].forEach(function (o) { limb(g, [-0.84, 0.86, z + o], [-0.83, 0.66, z + o * 1.05], 0.034, black); });
    });
    /* DON'T PANIC screen on a short stalk above the centre dash, tilted toward the driver */
    var sN = new T.Vector3(-0.2, 0.35, -0.91).normalize(), sX = new T.Vector3(0, 1, 0).cross(sN).normalize(), sY = sN.clone().cross(sX);
    var scr = at(g, new T.PlaneGeometry(0.25, 0.098), new T.MeshBasicMaterial({ map: screenTex(), toneMapped: false }), 0.07, 0.9, 0.0); scr.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(sX, sY, sN));
    var bz = new T.Mesh(new T.BoxGeometry(0.28, 0.122, 0.02), black); bz.position.set(0, 0, -0.012); scr.add(bz);
    limb(g, [0.14, 0.76, 0.0], [0.08, 0.88, 0.02], 0.018, black);
    /* round steering wheel in front of the left seat: rim, three spokes, hub, column into the dash */
    var wN = new T.Vector3(-Math.cos(0.44), Math.sin(0.44), 0), wX = new T.Vector3(0, 0, 1), wY = wN.clone().cross(wX);
    var swg = new T.Group(); swg.position.set(0.0, 0.85, -0.37); swg.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(wX, wY, wN));
    at(swg, new T.TorusGeometry(0.16, 0.02, 14, 56), leather, 0, 0, 0);
    [0, Math.PI, -Math.PI / 2].forEach(function (a) { var sp = new T.Mesh(new T.BoxGeometry(0.12, a === -Math.PI / 2 ? 0.05 : 0.034, 0.012), chrome); sp.rotation.z = a; sp.translateX(0.085); sp.position.z = -0.01; swg.add(sp); });
    at(swg, new T.CylinderGeometry(0.048, 0.052, 0.04, 24), black, 0, 0, -0.012, Math.PI / 2);
    at(swg, new T.CylinderGeometry(0.03, 0.03, 0.012, 20), chrome, 0, 0, 0.012, Math.PI / 2);
    at(swg, new T.CylinderGeometry(0.026, 0.034, 0.3, 14), black, 0, 0, -0.18, Math.PI / 2);
    g.add(swg);
    /* steeply raked windshield in a thick black frame */
    var wsg = new T.Group(); wsg.position.set(0.22, 0.99, 0); g.add(wsg);
    var ws = new T.Mesh(new T.PlaneGeometry(1.42, 0.46), glass); ws.rotation.y = Math.PI / 2; wsg.add(ws); wsg.rotation.z = 0.9;
    var fr = new T.CatmullRomCurve3([new T.Vector3(0.4, 0.78, -0.78), new T.Vector3(0.08, 1.14, -0.7), new T.Vector3(0.03, 1.17, 0), new T.Vector3(0.08, 1.14, 0.7), new T.Vector3(0.4, 0.78, 0.78)]);
    g.add(new T.Mesh(new T.TubeGeometry(fr, 64, 0.036, 10, false), black));
    var fb = new T.CatmullRomCurve3([new T.Vector3(0.4, 0.77, -0.78), new T.Vector3(0.38, 0.735, 0), new T.Vector3(0.4, 0.77, 0.78)]);
    g.add(new T.Mesh(new T.TubeGeometry(fb, 32, 0.03, 8, false), black));
    /* small body-colour mirrors on black stalks at the A-pillar base */
    [-1, 1].forEach(function (sd) {
      var mm = at(g, new T.SphereGeometry(0.07, 20, 14), mirrorPaint, 0.3, 0.95, sd * 1.0); mm.scale.set(0.6, 0.62, 1.15);
      at(g, new T.CircleGeometry(0.05, 18), black, 0.26, 0.95, sd * 1.0, 0, -Math.PI / 2, 0).scale.set(1.2, 0.85, 1);
      limb(g, [0.36, 0.84, sd * 0.86], [0.31, 0.93, sd * 0.96], 0.014, black);
    });
    /* side air scoops ahead of the rear wheels */
    [-1, 1].forEach(function (sd) { var sc = at(g, new T.SphereGeometry(0.2, 18, 12), black, -0.66, 0.55, sd * 0.88); sc.scale.set(0.85, 0.32, 0.3); sc.rotation.z = -0.15; });
    /* tail: twin round lamps each side in black surrounds, small carbon lip */
    [-1, 1].forEach(function (sd) {
      var sur = at(g, new T.SphereGeometry(0.2, 20, 12), black, -1.95, 0.66, sd * 0.5); sur.scale.set(0.16, 0.4, 1.05);
      [0.38, 0.6].forEach(function (zz, i) { at(g, new T.CylinderGeometry(0.065, 0.065, 0.05, 20), P(i ? 0xff2a3a : 0xd8d8dc, { emissive: i ? 0x550008 : 0x202022, roughness: 0.15, clearcoat: 1 }), -1.985, 0.66, sd * zz, 0, 0, Math.PI / 2); });
    });
    [[1.17, -0.8], [1.17, 0.8], [-1.18, -0.82], [-1.18, 0.82]].forEach(function (p) { wheel(g, p[0], p[1], tire, rim); });
    g.add(starman());
    g.userData.size = 4.2;
    return g;
  }
  /* Starman (after the 2018 SpaceX photos): left-hand driver's seat, sitting low with shoulders and helmet above the door line,
     left arm resting on the door sill, right hand on the wheel; white suit, black side panels and seatbelt, white helmet, dark gold-tint visor. */
  function starman() {
    var sm = new T.Group(), suit = P(0xf2f2f0, { roughness: 0.55, clearcoat: 0.3 }), blk = P(0x141517, { roughness: 0.5 }), visor = P(0x1a1206, { metalness: 1, roughness: 0.04, clearcoat: 1, envMapIntensity: 1.4 });
    var Z = -0.37, hip = [-0.5, 0.46, Z], sh = [-0.6, 0.93, Z];
    limb(sm, hip, sh, 0.165, suit);
    limb(sm, [-0.49, 0.53, Z - 0.155], [-0.59, 0.9, Z - 0.17], 0.028, blk);   /* black side panels */
    limb(sm, [-0.49, 0.53, Z + 0.155], [-0.59, 0.9, Z + 0.17], 0.028, blk);
    limb(sm, [-0.41, 0.9, Z - 0.13], [-0.36, 0.55, Z + 0.12], 0.02, blk);     /* seatbelt sash */
    limb(sm, [-0.37, 0.5, Z - 0.15], [-0.37, 0.5, Z + 0.15], 0.02, blk);      /* lap belt */
    at(sm, new T.TorusGeometry(0.1, 0.028, 10, 24), blk, -0.6, 1.02, Z, Math.PI / 2, 0, 0.2);
    var helm = at(sm, new T.SphereGeometry(0.15, 32, 22), suit, -0.58, 1.15, Z); helm.scale.set(1.06, 1.06, 0.98);
    var vis = at(sm, new T.SphereGeometry(0.153, 32, 22, -Math.PI * 0.47, Math.PI * 0.94, Math.PI * 0.24, Math.PI * 0.45), visor, -0.575, 1.15, Z, 0, Math.PI, 0); vis.scale.set(1.07, 1.08, 1.0);
    [-1, 1].forEach(function (sd) { at(sm, new T.CylinderGeometry(0.05, 0.05, 0.03, 16), blk, -0.6, 1.14, Z + sd * 0.148, Math.PI / 2, 0, 0); });
    var rS = [-0.58, 0.9, Z + 0.19], rE = [-0.34, 0.68, Z + 0.24], rH = [0.034, 0.922, Z + 0.139];
    var lS = [-0.58, 0.9, Z - 0.19], lE = [-0.36, 0.84, Z - 0.48], lH = [0.04, 0.87, Z - 0.5];
    [[rS, rE, rH], [lS, lE, lH]].forEach(function (a) {
      at(sm, new T.SphereGeometry(0.072, 16, 12), blk, a[0][0], a[0][1] + 0.02, a[0][2]);
      limb(sm, a[0], a[1], 0.055, suit); limb(sm, a[1], a[2], 0.05, suit);
      limb(sm, [a[1][0] + (a[2][0] - a[1][0]) * 0.55, a[1][1] + (a[2][1] - a[1][1]) * 0.55, a[1][2] + (a[2][2] - a[1][2]) * 0.55], [a[1][0] + (a[2][0] - a[1][0]) * 0.75, a[1][1] + (a[2][1] - a[1][1]) * 0.75, a[1][2] + (a[2][2] - a[1][2]) * 0.75], 0.056, blk);
      at(sm, new T.SphereGeometry(0.048, 12, 10), blk, a[2][0], a[2][1], a[2][2]);
    });
    [-1, 1].forEach(function (sd) {
      var hp = [hip[0] + 0.02, hip[1] - 0.04, Z + sd * 0.1], kn = [-0.06, 0.52, Z + sd * 0.12], ft = [0.36, 0.33, Z + sd * 0.12];
      limb(sm, hp, kn, 0.072, suit); limb(sm, kn, ft, 0.06, suit);
      at(sm, new T.SphereGeometry(0.068, 12, 10), blk, kn[0], kn[1] + 0.02, kn[2]);
      at(sm, new T.CapsuleGeometry(0.058, 0.12, 4, 10), blk, ft[0] + 0.05, ft[1] - 0.02, ft[2], 0, 0, Math.PI / 2);
    });
    return sm;
  }
  function screenTex() {
    var c = d.createElement("canvas"); c.width = 512; c.height = 200; var g = c.getContext("2d");
    var gr = g.createLinearGradient(0, 0, 0, 200); gr.addColorStop(0, "#071a10"); gr.addColorStop(1, "#020805"); g.fillStyle = gr; g.fillRect(0, 0, 512, 200);
    g.fillStyle = "#8dffaa"; g.shadowColor = "#3cff7a"; g.shadowBlur = 18; g.textAlign = "center"; g.textBaseline = "middle"; var fs = 92; g.font = "bold " + fs + "px Arial,Helvetica,sans-serif"; var mw = g.measureText("DON'T PANIC").width; if (mw > 440) { fs = Math.floor(fs * 440 / mw); g.font = "bold " + fs + "px Arial,Helvetica,sans-serif"; } g.fillText("DON'T PANIC", 256, 102); g.shadowBlur = 0; g.strokeStyle = "rgba(141,255,170,.35)"; g.lineWidth = 6; g.strokeRect(8, 8, 496, 184);
    var t = new T.CanvasTexture(c); t.anisotropy = 8; return t;
  }
  /* Spacecraft (original, simplified, recognizable). */
  function dishGeo(R, depth, n) { var pts = []; for (var i = 0; i <= 16; i++) { var r = R * i / 16; pts.push(new T.Vector2(r, depth * (r / R) * (r / R))); } return new T.LatheGeometry(pts, n || 40); }
  function wing(g, n, pw, ph, gap, x0, sd, mat, y, z, rotX) {   /* a solar wing of n panels along x (sd = +1/-1) */
    var w = new T.Group(); w.position.set(x0 * sd, y || 0, z || 0); if (rotX) w.rotation.x = rotX;
    for (var i = 0; i < n; i++) { var p = new T.Mesh(new T.BoxGeometry(pw, 0.03, ph), mat); p.position.x = sd * (pw / 2 + i * (pw + gap)); w.add(p); }
    limb(w, [0, 0, 0], [sd * (n * (pw + gap)), 0, 0], 0.025, mat.userData.frame || mat);
    g.add(w); return w;
  }
  function roundArray(g, R, x, mat, frame) {   /* Lucy-style round fan array */
    var a = at(g, new T.CircleGeometry(R, 10), mat, x, 0, 0, Math.PI / 2, 0, 0); a.material = mat.clone(); a.material.side = T.DoubleSide;
    for (var k = 0; k < 10; k++) { var r = new T.Mesh(new T.BoxGeometry(R, 0.02, 0.02), frame); r.position.set(x, 0.01, 0); r.rotation.y = k / 10 * Math.PI * 2; r.translateX(R / 2); g.add(r); }
    limb(g, [0, 0, 0], [x, 0, 0], 0.04, frame);
  }
  function craftModel(id) {
    var g = new T.Group(), foil = P(0xc79a2e, { metalness: 0.9, roughness: 0.38 }), pv = P(0x1a2552, { metalness: 0.5, roughness: 0.25, clearcoat: 0.8 }), wht = P(0xe6e6e2, { roughness: 0.5 }), gry = P(0x8a8f99, { metalness: 0.8, roughness: 0.35 }), blk = P(0x161616, { roughness: 0.6 }), silver = P(0xcfd2d6, { metalness: 0.95, roughness: 0.25 });
    pv.userData.frame = gry;
    function dish(R, depth, x, y, z, rx, rz, mat) { var dm = at(g, dishGeo(R, depth), (mat || wht).clone(), x, y, z, rx || 0, 0, rz || 0); dm.material.side = T.DoubleSide; return dm; }
    g.userData.size = 5;
    if (id === "voyager1" || id === "voyager2") {
      dish(1.85, 0.55, 0, 1.0, 0, Math.PI);
      at(g, new T.CylinderGeometry(0.06, 0.06, 0.6, 8), gry, 0, 0.6, 0);
      at(g, new T.CylinderGeometry(0.9, 0.9, 0.45, 10), foil, 0, 0.15, 0);
      limb(g, [0, 0.1, 0], [0, 0.1, -13], 0.02, gry);
      limb(g, [0.6, 0, 0], [2.6, -0.4, 0], 0.04, gry);
      [1.8, 2.2, 2.6].forEach(function (x) { at(g, new T.CylinderGeometry(0.2, 0.2, 0.4, 10), blk, x, -0.3 - (x - 1.8) * 0.2, 0, 0, 0, Math.PI / 2 - 0.2); });
      limb(g, [-0.6, 0, 0], [-2.4, -0.1, 0], 0.04, gry); at(g, new T.BoxGeometry(0.5, 0.4, 0.4), gry, -2.5, -0.1, 0);
      g.userData.size = 6;
    } else if (id === "newhorizons") {
      at(g, new T.CylinderGeometry(1.1, 1.1, 0.7, 3), foil, 0, 0, 0);
      dish(1.05, 0.3, 0, 0.75, 0, Math.PI);
      limb(g, [0.9, 0, 0], [1.8, 0, 0.2], 0.22, blk);
      g.userData.size = 4;
    } else if (id === "jwst") {
      var kite = new T.Shape(); kite.moveTo(-5, 0); kite.lineTo(0, 2.4); kite.lineTo(5, 0); kite.lineTo(0, -2.4); kite.lineTo(-5, 0);
      for (var L = 0; L < 5; L++) { var lay = at(g, new T.ShapeGeometry(kite), P(L ? 0xc9b8dd : 0xd8cbe8, { metalness: 0.8, roughness: 0.25, side: T.DoubleSide }), 0, L * 0.12, 0, -Math.PI / 2); lay.scale.setScalar(1 - L * 0.04); }
      at(g, new T.BoxGeometry(1.0, 0.5, 1.0), blk, 0, -0.35, 0);
      var mg = new T.Group(); mg.position.set(0, 2.4, 0.6); mg.rotation.x = -0.25; g.add(mg);
      var gold = P(0xe0b13a, { metalness: 1, roughness: 0.12, clearcoat: 1 }), hx = new T.CylinderGeometry(0.42, 0.42, 0.06, 6);
      [[1, 0], [-1, 0], [0.5, 0.866], [-0.5, 0.866], [0.5, -0.866], [-0.5, -0.866], [1.5, 0.866], [-1.5, 0.866], [1.5, -0.866], [-1.5, -0.866], [0, 1.732], [0, -1.732], [1, 1.732], [-1, 1.732], [1, -1.732], [-1, -1.732], [2, 0], [-2, 0]].forEach(function (p) { var h = at(mg, hx, gold, p[0] * 0.75, p[1] * 0.75, 0, Math.PI / 2, 0, 0); h.rotation.y = Math.PI / 6; });
      [[0.9, -1.2], [-0.9, -1.2], [0, 1.4]].forEach(function (p) { limb(mg, [p[0], p[1], 0], [0, 0, 2.2], 0.025, gry); });
      at(mg, new T.CylinderGeometry(0.2, 0.2, 0.06, 16), gold, 0, 0, 2.2, Math.PI / 2, 0, 0);
      g.userData.size = 9;
    } else if (id === "parker") {
      at(g, new T.CylinderGeometry(1.15, 1.15, 0.2, 40), wht, 0, 1.3, 0);
      at(g, new T.TorusGeometry(1.15, 0.06, 8, 40), blk, 0, 1.3, 0, Math.PI / 2, 0, 0);
      [[0.4, 0.4], [-0.4, 0.4], [0.4, -0.4], [-0.4, -0.4]].forEach(function (p) { limb(g, [p[0], 1.2, p[1]], [p[0] * 0.6, 0.6, p[1] * 0.6], 0.03, gry); });
      at(g, new T.CylinderGeometry(0.5, 0.5, 0.8, 6), foil, 0, 0.2, 0);
      [-1, 1].forEach(function (sd) { var pn = at(g, new T.BoxGeometry(0.7, 0.03, 0.35), pv, sd * 0.85, 0.15, 0); pn.rotation.z = sd * 0.5; });
      limb(g, [0, -0.2, 0], [0, -2.2, 0], 0.02, gry);
      g.userData.size = 4;
    } else if (id === "soho") {
      at(g, new T.BoxGeometry(1.2, 1.0, 1.2), foil, 0, 0, 0); at(g, new T.BoxGeometry(1.0, 1.4, 1.0), wht, 0, 1.2, 0);
      [-1, 1].forEach(function (sd) { wing(g, 2, 1.2, 1.1, 0.06, 0.6, sd, pv, -0.1); });
      dish(0.35, 0.12, 0.75, 0.4, 0.5, 0, Math.PI / 2);
      g.userData.size = 6;
    } else if (id === "solo") {   /* heat shield in front, two solar wings, high-gain antenna */
      at(g, new T.BoxGeometry(1.6, 1.0, 1.4), foil, 0, 0, 0);
      at(g, new T.BoxGeometry(0.12, 1.5, 1.7), P(0x2a2a2c, { roughness: 0.7 }), 0.95, 0, 0);
      [-1, 1].forEach(function (sd) { wing(g, 3, 0.9, 0.8, 0.05, 0.7, sd, pv, 0, 0, 0); });
      dish(0.5, 0.15, -0.6, 0.9, 0.4, 0, 0); limb(g, [-0.5, 0.5, 0.3], [-0.6, 0.9, 0.4], 0.03, gry);
      limb(g, [-0.8, 0, 0], [-4.5, 0, 0], 0.02, gry);
      g.userData.size = 6;
    } else if (id === "stereoa") {
      at(g, new T.BoxGeometry(1.1, 1.1, 1.1), foil, 0, 0, 0);
      [-1, 1].forEach(function (sd) { wing(g, 2, 0.6, 0.9, 0.05, 0.55, sd, pv, 0); });
      dish(0.55, 0.15, 0, 0.75, 0, Math.PI); limb(g, [0, 0, 0], [0, -3.5, 0], 0.02, gry);
    } else if (id === "ace") {   /* short octagonal drum with four solar panels */
      at(g, new T.CylinderGeometry(0.85, 0.85, 0.7, 8), foil, 0, 0, 0);
      [0, 1, 2, 3].forEach(function (k) { var p = new T.Mesh(new T.BoxGeometry(1.0, 0.03, 0.8), pv); p.rotation.y = k * Math.PI / 2; p.translateX(1.35); g.add(p); });
      limb(g, [0, 0, 0], [0, 0, 3.2], 0.02, gry); limb(g, [0, 0, 0], [0, 0, -3.2], 0.02, gry);
    } else if (id === "dscovr") {   /* box bus, two wings, EPIC telescope aperture facing Earth */
      at(g, new T.BoxGeometry(1.4, 1.0, 1.0), silver, 0, 0, 0);
      [-1, 1].forEach(function (sd) { wing(g, 2, 0.8, 0.8, 0.05, 0.7, sd, pv, 0); });
      at(g, new T.CylinderGeometry(0.22, 0.22, 0.5, 20), blk, 0, 0, 0.7, Math.PI / 2, 0, 0);
      dish(0.35, 0.1, 0, 0.7, 0, Math.PI);
    } else if (id === "wind") {   /* spin-stabilized drum with long wire antennas */
      at(g, new T.CylinderGeometry(1.2, 1.2, 1.2, 24), pv, 0, 0, 0);
      at(g, new T.CylinderGeometry(1.22, 1.22, 0.12, 24), foil, 0, 0.66, 0);
      [0, 1, 2, 3].forEach(function (k) { var a = k * Math.PI / 2; limb(g, [Math.cos(a), 0, Math.sin(a)], [Math.cos(a) * 9, 0, Math.sin(a) * 9], 0.01, gry); });
      limb(g, [0, 0.6, 0], [0, 5, 0], 0.03, gry); limb(g, [0, -0.6, 0], [0, -5, 0], 0.03, gry);
    } else if (id === "juno") {   /* hexagonal bus, three long solar wings, high-gain dish on top */
      at(g, new T.CylinderGeometry(0.9, 0.9, 0.9, 6), foil, 0, 0, 0);
      dish(1.1, 0.3, 0, 0.75, 0, Math.PI);
      [0, 1, 2].forEach(function (k) { var wg = new T.Group(); wg.rotation.y = k * Math.PI * 2 / 3; g.add(wg); wing(wg, 4, 1.9, 2.3, 0.06, 0.85, 1, pv, 0); });
      g.userData.size = 12;
    } else if (id === "lucy") {   /* two huge round solar arrays */
      at(g, new T.BoxGeometry(1.2, 1.4, 1.2), foil, 0, 0, 0);
      roundArray(g, 2.9, 3.6, pv, gry); roundArray(g, 2.9, -3.6, pv, gry);
      dish(1.0, 0.25, 0, 0.9, 0, Math.PI);
      g.userData.size = 12;
    } else if (id === "psyche") {   /* box bus, two cross-shaped 5-panel wings */
      at(g, new T.BoxGeometry(1.4, 1.2, 1.4), silver, 0, 0, 0);
      [-1, 1].forEach(function (sd) {
        wing(g, 3, 1.4, 1.3, 0.05, 0.7, sd, pv, 0);
        [-1, 1].forEach(function (o) { var p = at(g, new T.BoxGeometry(1.4, 0.03, 1.3), pv, sd * (0.7 + 1.45 * 1.5), 0, o * 1.35); });
      });
      dish(0.7, 0.2, 0, 0.75, 0, Math.PI);
      g.userData.size = 11;
    } else if (id === "clipper") {   /* tall bus, huge 5-panel arrays each side, large high-gain antenna */
      at(g, new T.CylinderGeometry(0.7, 0.7, 2.6, 12), silver, 0, 0, 0, 0, 0, Math.PI / 2);
      [-1, 1].forEach(function (sd) {
        wing(g, 3, 2.0, 2.0, 0.06, 1.4, sd, pv, 0);
        [-1, 1].forEach(function (o) { at(g, new T.BoxGeometry(2.0, 0.03, 2.0), pv, sd * (1.4 + 2.06 * 1.5), 0, o * 2.06); });
      });
      dish(1.5, 0.35, 0, 0.8, 0, Math.PI);
      limb(g, [-1.3, 0, 0], [-1.3, 0, 8], 0.02, gry);
      g.userData.size = 18;
    } else if (id === "juice") {   /* big cross-shaped arrays (10 panels), long magnetometer boom, large dish */
      at(g, new T.BoxGeometry(1.6, 1.6, 1.6), foil, 0, 0, 0);
      [-1, 1].forEach(function (sd) {
        wing(g, 3, 1.8, 1.6, 0.06, 0.8, sd, pv, 0);
        [-1, 1].forEach(function (o) { at(g, new T.BoxGeometry(1.8, 0.03, 1.6), pv, sd * (0.8 + 1.86 * 1.5), 0, o * 1.66); });
      });
      dish(1.25, 0.3, 0, 0.9, 0, Math.PI);
      limb(g, [0, 0, -0.8], [0, 0, -10.5], 0.02, gry);
      g.userData.size = 14;
    } else if (id === "aditya") {
      at(g, new T.BoxGeometry(1.2, 1.4, 1.2), foil, 0, 0, 0);
      wing(g, 2, 1.0, 1.0, 0.05, 0.6, 1, pv, 0);
      at(g, new T.CylinderGeometry(0.2, 0.2, 0.5, 16), wht, 0, 0.9, 0.3);
    } else {
      at(g, new T.BoxGeometry(1, 1, 1), foil, 0, 0, 0);
      [-1, 1].forEach(function (sd) { wing(g, 2, 0.9, 0.9, 0.05, 0.5, sd, pv, 0); });
      dish(0.4, 0.14, 0, 0.6, 0, Math.PI);
    }
    return g;
  }
  function line(pts, color, op) { var geo = new T.BufferGeometry().setFromPoints(pts); return new T.Line(geo, new T.LineBasicMaterial({ color: color, transparent: true, opacity: op })); }
  function ring(id) {
    var e = ELEM[id], a = e[0], ec = e[1], I = e[2] * Math.PI / 180, wp = e[4] * Math.PI / 180, Om = e[5] * Math.PI / 180, om = wp - Om, pts = [];
    for (var i = 0; i <= 256; i++) {
      var E = i / 256 * Math.PI * 2, xp = a * (Math.cos(E) - ec), yp = a * Math.sqrt(1 - ec * ec) * Math.sin(E);
      var x = (Math.cos(om) * Math.cos(Om) - Math.sin(om) * Math.sin(Om) * Math.cos(I)) * xp + (-Math.sin(om) * Math.cos(Om) - Math.cos(om) * Math.sin(Om) * Math.cos(I)) * yp;
      var y = (Math.cos(om) * Math.sin(Om) + Math.sin(om) * Math.cos(Om) * Math.cos(I)) * xp + (-Math.sin(om) * Math.sin(Om) + Math.cos(om) * Math.cos(Om) * Math.cos(I)) * yp;
      var z = Math.sin(om) * Math.sin(I) * xp + Math.cos(om) * Math.sin(I) * yp;
      pts.push(V([x, y, z]));
    }
    var rl = line(pts, 0x8090b0, 0.35); (S.rings = S.rings || []).push(rl); return rl;
  }
  function addObj(o) { OBJ[o.id] = o; LIST.push(o); S.root.add(o.node); }

  function flyTo(toT, toP, dur) {
    FLY = { t0: performance.now(), dur: dur || 1100, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: toT.clone(), toP: toP.clone() };
  }
  function hookApi() {
    return { T: T, S: S, LIST: LIST, OBJ: OBJ, esc: esc, imperial: imperial, fmtAU: fmtAU, fmtV: fmtV, flyTo: flyTo, cancelFly: function () { FLY = null; }, sel: function () { return SEL; } };
  }
  function attachPlanets() {
    var run = function () { try { if (w.BNPlanets && w.BNPlanets.attach) w.BNPlanets.attach(hookApi()); } catch (e) {} };
    if (w.BNPlanets) return run();
    if (attachPlanets.l) return;
    attachPlanets.l = 1;
    var s = d.createElement("script");
    s.src = w.BN_PLANETS3D || "/api/netmap/planets3d.js";
    s.async = true;
    s.onload = run;
    d.head.appendChild(s);
  }


  function build() {
    var root = S.root; while (root.children.length) root.remove(root.children[0]); OBJ = {}; LIST = []; S.rings = [];
    var sun = new T.Group(); sun.add(new T.Mesh(new T.SphereGeometry(3, 40, 24), new T.MeshBasicMaterial({ color: 0xfff1d0 })));
    var gl = new T.Sprite(new T.SpriteMaterial({ map: S.glow, color: 0xffffff, transparent: true, depthWrite: false, blending: T.AdditiveBlending })); gl.scale.set(18, 18, 1); sun.add(gl);
    addObj({ id: "sun", name: "Sun", kind: "sun", node: sun, size: 3, info: "Our star. Use Space weather to see the spacecraft watching it." });
    (DATA.planets || []).forEach(function (p) {
      var c = PL[p.id] || [0.5, 0x999999], gp = new T.Group(), mat = (p.id === "jupiter" || p.id === "saturn") ? new T.MeshStandardMaterial({ map: bandTex(c[1], p.id === "jupiter" ? 9 : 6), roughness: 0.9 }) : M(c[1], { roughness: 0.85 });
      gp.add(new T.Mesh(new T.SphereGeometry(c[0], 32, 20), mat));
      if (p.id === "saturn") { var rg = new T.Mesh(new T.RingGeometry(c[0] * 1.3, c[0] * 2.2, 48), new T.MeshBasicMaterial({ color: 0xcdb98a, side: T.DoubleSide, transparent: true, opacity: 0.6 })); rg.rotation.x = Math.PI / 2 - 0.47; gp.add(rg); }
      gp.position.copy(V(p.pos)); if (ELEM[p.id]) root.add(ring(p.id));
      addObj({ id: p.id, name: p.name, kind: "planet", node: gp, size: c[0], d: p, info: PINFO[p.id] || "" });
    });
    var E = OBJ.earth;
    if (E && DATA.moon) {
      var mg = new T.Mesh(new T.SphereGeometry(0.18, 20, 14), M(0xbbbbbb, { roughness: 1 })), g = DATA.moon.geo_km, L = Math.hypot(g[0], g[1], g[2]) || 1;
      mg.position.copy(E.node.position).add(new T.Vector3(g[0] / L, g[2] / L, -g[1] / L).multiplyScalar(1.2));
      addObj({ id: "moon", name: "Moon", kind: "planet", node: mg, size: 0.18, info: "Earth's Moon (distance from Earth exaggerated here). Real distance about " + (imperial() ? "239,000 mi" : "384,400 km") + "." });
    }
    (DATA.craft || []).forEach(function (c) {
      var isR = c.id === "roadster", node = new T.Group(), model = isR ? roadster() : craftModel(c.id), sc = isR ? 0.06 : 0.05;
      model.scale.setScalar(sc); node.add(model);
      var dot = new T.Mesh(new T.SphereGeometry(0.09, 10, 8), new T.MeshBasicMaterial({ color: isR ? 0xff4a5a : (c.sunwatch ? 0xffd27a : 0xb9c6ff) })); node.add(dot); node.userData.dot = dot;
      if (c.geo_km && E) { var gk = c.geo_km, Lg = Math.hypot(gk[0], gk[1], gk[2]) || 1; node.position.copy(E.node.position).add(new T.Vector3(gk[0], gk[2], -gk[1]).multiplyScalar(1.6 / 1.5e6)); }   /* true geometry around L1/L2, scale exaggerated */
      else node.position.copy(V(c.pos));
      if (c.track && c.track.length > 1 && !c.geo_km) {
        var now = Date.now() / 864e5, past = [], fut = [];
        c.track.forEach(function (t) { var v = V([t[1], t[2], t[3]]); if (t[0] <= now) past.push(v); else fut.push(v); });
        past.push(node.position.clone()); fut.unshift(node.position.clone());
        var lines = [];
        if (past.length > 1) { var lp = line(past, isR ? 0xff6b78 : 0x9fb2ff, 0.3); lp.userData.base = 0.3; root.add(lp); lines.push(lp); }
        if (fut.length > 1) { var lf = line(fut, 0xffffff, 0.18); lf.userData.base = 0.18; root.add(lf); lines.push(lf); }
        node.userData.lines = lines;
      }
      model.userData.spin = isR; model.userData.ph = Math.random() * 6;
      addObj({ id: c.id, name: c.name, kind: "craft", node: node, model: model, size: (model.userData.size || 4) * sc, d: c });
    });
    labels();
    try { attachPlanets(); } catch (e) {}
  }
  function labels() {
    S.labs.innerHTML = "";
    LIST.forEach(function (o) {
      var el = d.createElement("span"); el.className = "s3-lab" + (o.kind === "craft" ? " sc" : ""); el.textContent = o.id === "roadster" ? "Starman (Roadster)" : o.name; el.dataset.id = o.id;
      el.addEventListener("click", function (e) { e.stopPropagation(); focus(o.id); }); S.labs.appendChild(el); o.lab = el;
    });
    var h = "";
    LIST.forEach(function (o) { h += '<button type="button" data-id="' + esc(o.id) + '">' + esc(o.id === "roadster" ? "Starman" : o.name) + "</button>"; });
    S.objs.innerHTML = h;
    S.objs.querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { focus(b.dataset.id); }); });
  }
  function info(o) {
    if (!o) { S.info.hidden = true; return; }
    if (w.BNPlanets && w.BNPlanets.info && w.BNPlanets.info(o, S.info)) return;
    var h = "<h3>" + esc(o.id === "roadster" ? "Tesla Roadster / Starman" : o.name) + (o.kind === "craft" ? '<span class="s3-tag">illustrative model</span>' : "") + '<button type="button" class="s3-tog" aria-expanded="' + (S.infoOpen ? "true" : "false") + '">' + (S.infoOpen ? "Collapse" : "Expand") + "</button></h3><div class=\"s3-body\">", c = o.d;
    var earth = OBJ.earth && OBJ.earth.d;
    if (o.kind === "sun") h += "<p>" + esc(o.info) + "</p>" + (earth ? "<p>From Earth: " + fmtAU(Math.hypot.apply(null, earth.pos)) + "</p>" : "");
    else if (o.kind === "planet") {
      if (c) { h += "<p>From the Sun: " + fmtAU(Math.hypot.apply(null, c.pos)) + "</p>"; if (earth && c.id !== "earth") h += "<p>From Earth: " + fmtAU(Math.hypot(c.pos[0] - earth.pos[0], c.pos[1] - earth.pos[1], c.pos[2] - earth.pos[2])) + "</p>"; h += "<p>Orbital speed: " + fmtV(c.v_km_s) + "</p>"; }
      h += "<p>" + esc(o.info) + "</p>";
    } else if (c) {
      h += "<p>" + esc(c.operator) + " · launched " + esc(c.launch) + " · " + esc(since(c.launch)) + " in space</p>";
      h += "<p>From Earth: " + fmtAU(c.earth_au) + "<br>From the Sun: " + fmtAU(c.sun_au) + "<br>Speed (vs. Sun): " + fmtV(c.v_km_s) + "</p>";
      h += "<p>" + esc(c.status) + "</p><p>Monitors: " + esc(c.monitors) + "</p>";
      if (c.geo_km) h += "<p>Position near Earth is exaggerated so it can be seen; it moves around the Sun with Earth.</p>";
      else h += "<p>Line: past trajectory (color) and next months (white).</p>";
      if (c.id === "roadster") h += "<p>3D view: illustrative model built for this site, not a photo.</p>";
      var ph = PHOTOS[c.id];
      if (ph) h += '<figure class="s3-ph"><img src="/api/netmap/learn/s3_' + esc(c.id) + '.jpg" alt="' + esc(ph.c) + '" loading="lazy"><figcaption>Real photo: ' + esc(ph.c) + '. ' + esc(ph.by) + ' (' + esc(ph.lic) + '), <a href="' + esc(ph.src) + '" target="_blank" rel="noopener">source</a>.</figcaption></figure>';
    }
    h += '<p class="s3-k">Positions: <a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener">NASA/JPL Horizons</a>' + (DATA && DATA.epoch ? " · " + esc(DATA.epoch.slice(0, 16).replace("T", " ")) + " UTC" : "") + "</p>";
    S.info.innerHTML = h + "</div>"; S.info.hidden = false; S.info.classList.toggle("open", !!S.infoOpen);
    var tg = S.info.querySelector(".s3-tog"); if (tg) tg.addEventListener("click", function () { S.infoOpen = !S.infoOpen; S.info.classList.toggle("open", S.infoOpen); tg.textContent = S.infoOpen ? "Collapse" : "Expand"; tg.setAttribute("aria-expanded", S.infoOpen ? "true" : "false"); });
  }
  function focus(id, vdir, vmul) {
    var o = OBJ[id]; if (!o) return; SEL = o;
    LIST.forEach(function (x) { if (x.lab) x.lab.classList.toggle("sel", x === o); });
    S.objs.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.id === id ? "true" : "false"); });
    var tgt = o.node.getWorldPosition(new T.Vector3()); if (o.id === "roadster") tgt.y += 0.06; var dist = o.kind === "craft" ? o.size * (o.id === "roadster" ? (S.W < 500 ? 2.1 : 0.95) : 2.2) : o.kind === "sun" ? 26 : Math.max(o.size * 6, 1.5);
    if (w.BNPlanets && w.BNPlanets.focusDist) dist = w.BNPlanets.focusDist(o, dist, S);
    var dir = S.cam.position.clone().sub(S.ctl.target); if (dir.lengthSq() < 1e-9) dir.set(0, 0.4, 1); dir.normalize();
    if (o.kind === "craft") { dir.set(0.55, 0.35, 0.75); if (o.id === "roadster") { S.spin0 = performance.now(); dir.set(0.3, 0.6, -0.74); } dir.normalize(); }
    if (vdir) { dir.fromArray(vdir).normalize(); dist *= vmul || 1; }
    tracks(o);
    S._trk = null;
    FLY = { t0: performance.now(), dur: 1300, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: tgt, toP: tgt.clone().add(dir.multiplyScalar(dist)) };
    info(o);
  }
  function tracks(sel) {   /* fade every trajectory, highlight the selected one */
    LIST.forEach(function (x) { (x.node.userData.lines || []).forEach(function (l) { l.material.opacity = !sel ? l.userData.base : x === sel ? Math.min(1, l.userData.base * 3.2) : 0.06; }); });
    (S.rings || []).forEach(function (r) { r.material.opacity = sel ? 0.18 : 0.35; });
  }
  function overview() { SEL = null; S._trk = null; tracks(null); var far = compressed ? 110 : 160; FLY = { t0: performance.now(), dur: 1000, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: new T.Vector3(), toP: new T.Vector3(0, far * 0.75, far) }; info(null); }
  var tmp = new T.Vector3();
  function frame(now) {
    raf = w.requestAnimationFrame(frame); if (d.hidden) return;
    if (FLY) { var k = Math.min(1, (now - FLY.t0) / FLY.dur), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; S.cam.position.lerpVectors(FLY.fromP, FLY.toP, e); S.ctl.target.lerpVectors(FLY.fromT, FLY.toT, e); if (k >= 1) { FLY = null; S._trk = null; } }
    if (SEL && !FLY) {
      var tpos = SEL.node.getWorldPosition(new T.Vector3()); if (SEL.id === "roadster") tpos.y += 0.06;
      if (S._trk) { var dx = tpos.x - S._trk.x, dy = tpos.y - S._trk.y, dz = tpos.z - S._trk.z; S.ctl.target.x += dx; S.ctl.target.y += dy; S.ctl.target.z += dz; S.cam.position.x += dx; S.cam.position.y += dy; S.cam.position.z += dz; }
      S._trk = tpos;
    } else if (!SEL) S._trk = null;
    S.ctl.update();
    var cd = S.cam.position.length();
    LIST.forEach(function (o) {
      if (o.model) {
        if (o.model.userData.spin) { var tt = (now - (S.spin0 || 0)) / 1000, sel = SEL === o; o.model.rotation.y = (sel ? 0.05 : 0.12) * tt + (sel ? 0 : o.model.userData.ph); o.model.rotation.x = Math.sin(tt * 0.21) * (sel ? 0.05 : 0.22); o.model.rotation.z = Math.sin(tt * 0.13) * (sel ? 0.03 : 0.12); o.model.position.y = Math.sin(tt * 0.35) * 0.012; }
        var dd = S.cam.position.distanceTo(o.node.position), dot = o.node.userData.dot;
        if (dot) { dot.visible = dd > o.size * 8; dot.scale.setScalar(Math.max(1, dd / 30)); }
      }
      if (o.lab) {
        o.node.getWorldPosition(tmp); tmp.project(S.cam);
        var vis = tmp.z < 1 && Math.abs(tmp.x) < 1.1 && Math.abs(tmp.y) < 1.1;
        if (vis && o.model && S.cam.position.distanceTo(o.node.position) < o.size * 3) vis = false;
        if (vis) { o.lab.style.display = ""; o.lab.style.transform = "translate(" + ((tmp.x + 1) / 2 * S.W).toFixed(1) + "px," + ((1 - tmp.y) / 2 * S.H).toFixed(1) + "px) translate(-50%,-150%)"; }
        else o.lab.style.display = "none";
      }
    });
    if (w.BNPlanets && w.BNPlanets.tick) w.BNPlanets.tick();
    S.r.render(S.scene, S.cam);
  }
  function resize() { S.W = S.el.clientWidth; S.H = S.el.clientHeight; S.r.setSize(S.W, S.H, false); S.cam.aspect = S.W / Math.max(1, S.H); S.cam.updateProjectionMatrix(); }
  function load(after) {
    var x = new XMLHttpRequest(); x.open("GET", "/api/netmap/solar3d"); x.onload = function () {
      var j = null; try { j = JSON.parse(x.responseText); } catch (e) {}
      if (j && j.ok) { DATA = j; S.msg.hidden = true; build(); if (after) after(); }
      else if (tries++ < 20) { S.msg.textContent = "Loading positions from NASA/JPL Horizons…"; setTimeout(function () { load(after); }, 3000); }
      else S.msg.textContent = "Solar-system positions are unavailable right now.";
    }; x.onerror = function () { S.msg.textContent = "Solar-system positions are unavailable right now."; }; x.send();
  }
  function init() {
    css();
    var el = S.el = d.createElement("div"); el.className = "s3"; el.id = "bn_s3"; el.setAttribute("role", "region"); el.setAttribute("aria-label", "Solar system explorer. Drag to rotate, pinch or scroll to zoom.");
    el.innerHTML = '<div class="s3-top"><button type="button" id="s3_back">Back to Earth</button><button type="button" id="s3_all">Overview</button><button type="button" id="s3_sun">Sun</button><span class="s3-sp"></span><button type="button" id="s3_scale" aria-pressed="false" title="Compressed or true-scale distances">True scale</button></div>' +
      '<div class="s3-objs" id="s3_objs" aria-label="Objects"></div><div class="s3-labs" id="s3_labs"></div><div class="s3-info" id="s3_info" hidden aria-live="polite"></div><p class="s3-msg" id="s3_msg">Loading positions from NASA/JPL Horizons…</p>';
    d.body.appendChild(el);
    S.objs = el.querySelector("#s3_objs"); S.labs = el.querySelector("#s3_labs"); S.info = el.querySelector("#s3_info"); S.msg = el.querySelector("#s3_msg");
    S.r = new T.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true }); S.r.outputEncoding = T.sRGBEncoding; S.r.toneMapping = T.ACESFilmicToneMapping; S.r.toneMappingExposure = 1.15; S.r.setPixelRatio(Math.min(2, w.devicePixelRatio || 1)); el.insertBefore(S.r.domElement, el.firstChild);
    S.scene = new T.Scene(); S.cam = new T.PerspectiveCamera(50, 1, 0.0005, 50000); S.cam.position.set(0, 80, 110);
    S.scene.add(new T.AmbientLight(0xffffff, 0.28)); S.scene.add(new T.PointLight(0xfff2dd, 1.6, 0, 0));
    var cam_l = new T.DirectionalLight(0xffffff, 0.35); S.cam.add(cam_l); S.scene.add(S.cam);
    var sp = [], i; for (i = 0; i < 2500; i++) { var v = new T.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1).normalize().multiplyScalar(9000 + Math.random() * 3000); sp.push(v); }
    S.scene.add(new T.Points(new T.BufferGeometry().setFromPoints(sp), new T.PointsMaterial({ color: 0xcfd6ff, size: 1.4, sizeAttenuation: false })));
    S.root = new T.Group(); S.scene.add(S.root); S.glow = glowTex();
    S.ctl = new T.OrbitControls(S.cam, S.r.domElement); S.ctl.enableDamping = true; S.ctl.dampingFactor = 0.08; S.ctl.minDistance = 0.05; S.ctl.maxDistance = 6000; S.ctl.zoomSpeed = 1.2;
    S.ctl.addEventListener("start", function () { FLY = null; });
    S.r.domElement.addEventListener("wheel", function () { FLY = null; }, { passive: true });
    el.querySelector("#s3_back").addEventListener("click", close);
    el.querySelector("#s3_all").addEventListener("click", overview);
    el.querySelector("#s3_sun").addEventListener("click", function () { focus("sun"); });
    el.querySelector("#s3_scale").addEventListener("click", function () { compressed = !compressed; this.setAttribute("aria-pressed", compressed ? "false" : "true"); var id = SEL && SEL.id; if (DATA) build(); if (id) focus(id); else overview(); });
    var ray = new T.Raycaster(), dn = null;
    S.r.domElement.addEventListener("pointerdown", function (e) { dn = [e.clientX, e.clientY]; });
    S.r.domElement.addEventListener("pointerup", function (e) {
      if (!dn || Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 8) return;
      var rc = S.r.domElement.getBoundingClientRect(); ray.setFromCamera(new T.Vector2((e.clientX - rc.left) / rc.width * 2 - 1, -(e.clientY - rc.top) / rc.height * 2 + 1), S.cam);
      var hit = ray.intersectObjects(S.root.children, true).filter(function (h) { return h.object.type === "Mesh"; })[0];
      if (!hit) return; var n = hit.object; while (n && n.parent !== S.root) n = n.parent; var o = LIST.filter(function (x) { return x.node === n; })[0]; if (o && o !== SEL) focus(o.id);
    });
    w.addEventListener("resize", function () { if (S.el && !S.el.hidden) resize(); });
    w.addEventListener("bn-units", function () { if (SEL) info(SEL); });
    d.addEventListener("keydown", function (e) { if (e.key === "Escape" && S.el && !S.el.hidden) close(); });
  }
  function open(id) {
    if (!S.el) init();
    S.el.hidden = false; d.documentElement.style.overflow = "hidden"; resize();
    if (!raf) raf = w.requestAnimationFrame(frame);
    var go = function () { if (id === "sw") focus("sun"); else if (id && OBJ[id]) focus(id); else overview(); };
    if (DATA) go(); else load(go);
  }
  function close() {
    if (!S.el) return; S.el.hidden = true; d.documentElement.style.overflow = ""; if (raf) { w.cancelAnimationFrame(raf); raf = 0; }
    try { d.dispatchEvent(new CustomEvent("bn:solar-close")); } catch (e) {}
  }
  w.BNSolar = { open: open, close: close, focus: function (id, vdir, vmul) { focus(id, vdir, vmul); }, _state: function () { return { data: !!DATA, objects: LIST.map(function (o) { return o.id; }), sel: SEL && SEL.id, open: !!(S.el && !S.el.hidden) }; } };
})(window);
