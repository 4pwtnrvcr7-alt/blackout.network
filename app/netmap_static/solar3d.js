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
      ".s3-info a{color:#b9c6ff}.s3-ph{margin:6px 0 2px}.s3-ph img{display:block;width:100%;max-height:170px;object-fit:cover;border-radius:6px}.s3-ph figcaption{font-size:10.5px;opacity:.75;margin-top:2px}.s3 .s3-tog{display:none;margin-left:8px;padding:1px 9px;font-size:11px;vertical-align:2px}@media (max-width:600px){.s3 .s3-tog{display:inline-block}.s3-info:not(.open) .s3-body{display:none}.s3-info{max-height:45%;font-size:11.5px}.s3-info h3{font-size:14px;margin:0}.s3-ph img{max-height:120px}}.s3-msg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);opacity:.8}";
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
  /* Car body after the 2008 Tesla Roadster (Lotus Elise based): low, wide, short wheelbase, valley hood between rounded front fenders,
     cockpit well back, raised rear deck. Lofted rounded cross-sections along x (x forward, y up, +z right; driver is left, -z). */
  function carBody(mat) {
    var NX = 130, NA = 64, pos = [], idx = [], X0 = -1.98, X1 = 1.98;
    var WX = [[-1.18, 0.34], [1.17, 0.33]];
    function half(u, x) {
      var w = 0.9 * Math.pow(Math.max(0, 1 - Math.pow(Math.abs(2 * u - 1), 5)), 0.3);
      w += 0.035 * Math.exp(-Math.pow((x - 1.17) / 0.35, 2)) + 0.05 * Math.exp(-Math.pow((x + 1.15) / 0.45, 2)) - 0.02 * Math.exp(-Math.pow((x + 0.1) / 0.4, 2));
      return w + 0.004;
    }
    function topY(u, x, r) {   /* r = |z| / half-width, 0 centre .. 1 side */
      var deck = 0.9 + 0.02 * (1 - r * r), belt = 0.82, side = 0.6;
      var t;
      if (x < -0.82) { t = deck - 0.15 * (1 - ss(-1.98, -1.75, x)); }                         /* rear deck, rounding down at the tail */
      else if (x < 0.3) { t = belt + (deck - belt) * (1 - ss(-0.85, -0.7, x)); }            /* door / belt line */
      else {                                                                               /* hood valley between the front fenders */
        var hc = 0.72 - 0.3 * ss(0.3, 1.98, x), hf = 0.82 - 0.02 * ss(0.3, 1.3, x) - 0.36 * ss(1.4, 1.98, x);
        t = hc + (hf - hc) * ss(0.25, 0.72, r);
        t = t * (1 - ss(0.0, 0.3, 0.3 - x + 0.3) * 0) ;
      }
      return t - 0.12 * ss(0.8, 1, r) * 0;
    }
    function bot(x, u) {
      var b = 0.16 + 0.12 * (1 - ss(0, 0.1, u)) + 0.1 * ss(0.88, 1, u);
      WX.forEach(function (w) { var dx = Math.abs(x - w[0]), R = w[1] + 0.06; if (dx < R) b = Math.max(b, 0.3 + Math.sqrt(R * R - dx * dx) * 0.95); });
      return b;
    }
    function cock(x) { return ss(-0.82, -0.72, x) * (1 - ss(0.22, 0.34, x)); }
    for (var i = 0; i <= NX; i++) {
      var u = i / NX, x = X0 + (X1 - X0) * u, w = half(u, x), cw = cock(x), b = bot(x, u);
      for (var j = 0; j < NA; j++) {
        var th = j / NA * Math.PI * 2, c = Math.cos(th), s = Math.sin(th), n = 3.4;
        var zz = Math.sign(c) * Math.pow(Math.abs(c), 2 / n), yy = Math.sign(s) * Math.pow(Math.abs(s), 2 / n), z = w * zz, r = Math.abs(zz);
        var t = topY(u, x, r), yc = Math.min(t - 0.05, 0.5), y;
        if (yy >= 0) {
          y = yc + (t - yc) * yy;
          var k = cw * (1 - ss(0.78, 0.9, r)) * ss(0.2, 0.75, yy);   /* open cockpit well, floor at 0.3 */
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
  function wheel(g, x, z, tire, rim, disc) {   /* 5-spoke alloy, dark tire */
    var w = new T.Group(), sd = Math.sign(z); w.position.set(x, 0.31, z);
    at(w, new T.TorusGeometry(0.24, 0.085, 18, 44), tire, 0, 0, 0);
    at(w, new T.TorusGeometry(0.2, 0.018, 8, 40), rim, 0, 0, sd * 0.06);
    for (var k = 0; k < 5; k++) { var sp = new T.Mesh(new T.BoxGeometry(0.06, 0.17, 0.035), rim); sp.position.z = sd * 0.06; sp.rotation.z = k / 5 * Math.PI * 2; sp.translateY(0.1); w.add(sp); }
    at(w, new T.CylinderGeometry(0.15, 0.15, 0.04, 28), disc, 0, 0, 0, Math.PI / 2);
    at(w, new T.CylinderGeometry(0.045, 0.045, 0.16, 12), rim, 0, 0, 0, Math.PI / 2);
    g.add(w);
  }
  function screenTex() {
    var c = d.createElement("canvas"); c.width = 512; c.height = 200; var g = c.getContext("2d");
    var gr = g.createLinearGradient(0, 0, 0, 200); gr.addColorStop(0, "#071a10"); gr.addColorStop(1, "#020805"); g.fillStyle = gr; g.fillRect(0, 0, 512, 200);
    g.fillStyle = "#8dffaa"; g.shadowColor = "#3cff7a"; g.shadowBlur = 18; g.font = "bold 86px Arial,Helvetica,sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("DON'T PANIC", 256, 102);
    var t = new T.CanvasTexture(c); t.anisotropy = 8; return t;
  }
  function roadster() {
    var g = new T.Group();
    var paint = P(0x9e0b16, { metalness: 0.5, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.05 });
    var leather = P(0x121214, { roughness: 0.6 }), insert = P(0x8a1d14, { roughness: 0.65 }), carbon = P(0x18191c, { roughness: 0.32, metalness: 0.35, clearcoat: 0.7 }), chrome = P(0xdfe3e8, { metalness: 1, roughness: 0.12 });
    var tire = P(0x0c0c0d, { roughness: 0.85 }), rim = P(0xc4c8ce, { metalness: 1, roughness: 0.2 }), disc = P(0x55585e, { metalness: 0.9, roughness: 0.4 }), black = P(0x050506, { roughness: 0.4 });
    var glass = P(0x9fb9cc, { transparent: true, opacity: 0.25, roughness: 0.02, clearcoat: 1, side: T.DoubleSide, depthWrite: false });
    g.add(carBody(paint));
    at(g, new T.BoxGeometry(1.05, 0.04, 1.4), carbon, -0.26, 0.3, 0);                                  /* cockpit floor */
    at(g, new T.BoxGeometry(0.05, 0.5, 1.45), carbon, -0.8, 0.58, 0);                                  /* rear bulkhead */
    /* seats (black with red inserts), driver left (-z), passenger right (+z) empty */
    [-0.37, 0.37].forEach(function (z) {
      var cu = at(g, new T.CapsuleGeometry(0.17, 0.2, 6, 14), leather, -0.45, 0.38, z, 0, 0, Math.PI / 2 - 0.12); cu.scale.set(0.55, 1, 1.35);
      var bk = at(g, new T.CapsuleGeometry(0.19, 0.4, 6, 14), leather, -0.66, 0.68, z, 0, 0, -0.38); bk.scale.set(0.42, 1, 1.3);
      var ins = at(g, new T.CapsuleGeometry(0.11, 0.34, 4, 10), insert, -0.6, 0.68, z, 0, 0, -0.38); ins.scale.set(0.3, 1, 1.2);
      [-0.22, 0.22].forEach(function (o) { at(g, new T.CapsuleGeometry(0.04, 0.34, 4, 8), leather, -0.63, 0.66, z + o, 0, 0, -0.38); });
    });
    at(g, new T.BoxGeometry(0.85, 0.16, 0.18), carbon, -0.2, 0.38, 0);                                  /* centre tunnel */
    at(g, new T.BoxGeometry(0.42, 0.05, 1.5), carbon, 0.2, 0.7, 0);   /* cowl over the footwell */
    /* dashboard across the cockpit, DON'T PANIC screen in the centre */
    var dash = at(g, new T.CapsuleGeometry(0.12, 1.25, 6, 18), carbon, 0.3, 0.74, 0, Math.PI / 2, 0, 0); dash.scale.set(1.1, 1, 0.8);
    var scr = at(g, new T.PlaneGeometry(0.3, 0.12), new T.MeshBasicMaterial({ map: screenTex(), toneMapped: false }), 0.2, 0.8, 0.0); scr.rotation.set(0, -Math.PI / 2 - 0.75, 0); scr.rotateX(-0.45); var bz = new T.Mesh(new T.PlaneGeometry(0.34, 0.15), black); bz.position.set(0, 0, -0.004); scr.add(bz);
    /* steering wheel in front of the driver */
    var swg = new T.Group(); swg.position.set(0.1, 0.8, -0.37); swg.rotation.set(0, Math.PI / 2, 0); swg.rotateX(-0.5);
    at(swg, new T.TorusGeometry(0.13, 0.02, 10, 36), leather, 0, 0, 0);
    [Math.PI / 2, -Math.PI / 6, Math.PI + Math.PI / 6].forEach(function (a) { var sp = new T.Mesh(new T.BoxGeometry(0.025, 0.14, 0.02), chrome); sp.rotation.z = a; sp.translateY(0.07); swg.add(sp); });
    at(swg, new T.CylinderGeometry(0.04, 0.04, 0.04, 16), black, 0, 0, 0, Math.PI / 2);
    g.add(swg); limb(g, [0.1, 0.83, -0.37], [0.3, 0.72, -0.37], 0.025, carbon);
    /* raked windshield and black frame */
    var wsg = new T.Group(); wsg.position.set(0.2, 0.98, 0); g.add(wsg);
    var ws = new T.Mesh(new T.PlaneGeometry(1.5, 0.48), glass); ws.rotation.y = Math.PI / 2; wsg.add(ws); wsg.rotation.z = 0.84;
    var fr = new T.CatmullRomCurve3([new T.Vector3(0.38, 0.82, -0.78), new T.Vector3(0.05, 1.12, -0.72), new T.Vector3(0.0, 1.15, 0), new T.Vector3(0.05, 1.12, 0.72), new T.Vector3(0.38, 0.82, 0.78)]);
    g.add(new T.Mesh(new T.TubeGeometry(fr, 56, 0.024, 8, false), black));
    /* black roll hoop (targa bar) behind the seats */
    var hp = new T.CatmullRomCurve3([new T.Vector3(-0.86, 0.85, -0.8), new T.Vector3(-0.88, 1.08, -0.62), new T.Vector3(-0.9, 1.12, 0), new T.Vector3(-0.88, 1.08, 0.62), new T.Vector3(-0.86, 0.85, 0.8)]);
    g.add(new T.Mesh(new T.TubeGeometry(hp, 48, 0.05, 10, false), black));
    /* door mirrors */
    [-1, 1].forEach(function (sd) { var mm = at(g, new T.SphereGeometry(0.075, 18, 12), black, 0.3, 0.92, sd * 0.97); mm.scale.set(0.55, 0.65, 1.1); limb(g, [0.33, 0.83, sd * 0.85], [0.31, 0.9, sd * 0.94], 0.014, black); });
    /* swept-back almond headlights on the front fenders */
    [-1, 1].forEach(function (sd) {
      var hl = at(g, new T.SphereGeometry(0.2, 24, 14), P(0x1a1c22, { metalness: 0.6, roughness: 0.05, clearcoat: 1 }), 1.62, 0.69, sd * 0.6); hl.scale.set(1.25, 0.2, 0.45); hl.rotation.set(0, sd * 0.45, sd * 0.12);
      var lens = at(g, new T.SphereGeometry(0.06, 14, 10), P(0xf0f4ff, { emissive: 0x30343e, roughness: 0.05 }), 1.72, 0.7, sd * 0.56); lens.scale.set(1, 0.6, 1);
    });
    /* narrow Tesla nose opening + wide lower intake */
    var nose = at(g, new T.SphereGeometry(0.2, 20, 10), black, 1.95, 0.52, 0); nose.scale.set(0.12, 0.18, 1.0);
    var mouth = at(g, new T.SphereGeometry(0.4, 24, 10), black, 1.92, 0.32, 0); mouth.scale.set(0.12, 0.17, 1.35);
    /* side air scoops behind the doors (in front of the rear wheels) */
    [-1, 1].forEach(function (sd) { var sc = at(g, new T.SphereGeometry(0.2, 18, 12), black, -0.68, 0.52, sd * 0.86); sc.scale.set(1.1, 0.42, 0.32); sc.rotation.z = -0.15; });
    /* raised rear deck: twin round tail lights each side in black surrounds */
    [-1, 1].forEach(function (sd) {
      var sur = at(g, new T.SphereGeometry(0.2, 20, 12), black, -1.95, 0.64, sd * 0.47); sur.scale.set(0.16, 0.42, 1.05);
      [0.36, 0.58].forEach(function (zz, i) { var tl = at(g, new T.CylinderGeometry(0.065, 0.065, 0.05, 20), P(i ? 0xff2a3a : 0xd8d8dc, { emissive: i ? 0x550008 : 0x202022, roughness: 0.15, clearcoat: 1 }), -1.985, 0.64, sd * zz, 0, 0, Math.PI / 2); });
    });
    var spoiler = at(g, new T.BoxGeometry(0.16, 0.03, 1.35), carbon, -1.88, 0.86, 0, 0, 0, -0.12);
    [[1.17, -0.8], [1.17, 0.8], [-1.18, -0.82], [-1.18, 0.82]].forEach(function (p) { wheel(g, p[0], p[1], tire, rim, disc); });
    g.add(starman());
    g.userData.size = 4.2;
    return g;
  }
  /* Starman (after the 2018 SpaceX photos): left-hand driver's seat, left arm resting on the door sill, right hand on the wheel,
     white suit with black panels, white helmet with a large dark visor. */
  function starman() {
    var sm = new T.Group(), suit = P(0xf2f2f0, { roughness: 0.55, clearcoat: 0.3 }), blk = P(0x141517, { roughness: 0.5 }), visor = P(0x050607, { metalness: 1, roughness: 0.03, clearcoat: 1 });
    var Z = -0.37, hip = [-0.5, 0.48, Z], sh = [-0.6, 0.96, Z];
    limb(sm, hip, sh, 0.165, suit);                                                         /* torso */
    var chest = at(sm, new T.BoxGeometry(0.05, 0.18, 0.17), blk, -0.43, 0.84, Z, 0, 0, -0.2);
    limb(sm, [-0.49, 0.55, Z - 0.15], [-0.59, 0.92, Z - 0.17], 0.028, blk);                    /* black side panels */
    limb(sm, [-0.49, 0.55, Z + 0.15], [-0.59, 0.92, Z + 0.17], 0.028, blk);
    at(sm, new T.TorusGeometry(0.1, 0.028, 10, 24), blk, -0.6, 1.05, Z, Math.PI / 2, 0, 0.2);    /* neck ring */
    var helm = at(sm, new T.SphereGeometry(0.15, 32, 22), suit, -0.58, 1.18, Z); helm.scale.set(1.06, 1.06, 0.98);
    var vis = at(sm, new T.SphereGeometry(0.152, 32, 22, -Math.PI * 0.45, Math.PI * 0.9, Math.PI * 0.26, Math.PI * 0.42), visor, -0.575, 1.18, Z, 0, Math.PI, 0); vis.scale.set(1.07, 1.08, 1.0);
    [-1, 1].forEach(function (sd) { var ear = at(sm, new T.CylinderGeometry(0.05, 0.05, 0.03, 16), blk, -0.6, 1.17, Z + sd * 0.148, Math.PI / 2, 0, 0); });
    /* right arm (centre side, +z) to the wheel; left arm (door side, -z) over the door sill */
    var rS = [-0.58, 0.93, Z + 0.19], rE = [-0.36, 0.66, Z + 0.25], rH = [0.08, 0.865, Z + 0.113];
    var lS = [-0.58, 0.93, Z - 0.19], lE = [-0.5, 0.84, Z - 0.47], lH = [-0.16, 0.86, Z - 0.51];
    [[rS, rE, rH], [lS, lE, lH]].forEach(function (a) {
      at(sm, new T.SphereGeometry(0.072, 16, 12), blk, a[0][0], a[0][1] + 0.02, a[0][2]);           /* shoulder panel */
      limb(sm, a[0], a[1], 0.055, suit); limb(sm, a[1], a[2], 0.05, suit);
      limb(sm, [a[1][0] + (a[2][0] - a[1][0]) * 0.55, a[1][1] + (a[2][1] - a[1][1]) * 0.55, a[1][2] + (a[2][2] - a[1][2]) * 0.55], [a[1][0] + (a[2][0] - a[1][0]) * 0.75, a[1][1] + (a[2][1] - a[1][1]) * 0.75, a[1][2] + (a[2][2] - a[1][2]) * 0.75], 0.056, blk);   /* cuff */
      at(sm, new T.SphereGeometry(0.048, 12, 10), blk, a[2][0], a[2][1], a[2][2]);                     /* glove */
    });
    [-1, 1].forEach(function (sd) {
      var hp = [hip[0] + 0.02, hip[1] - 0.04, Z + sd * 0.1], kn = [-0.06, 0.52, Z + sd * 0.12], ft = [0.36, 0.33, Z + sd * 0.12];
      limb(sm, hp, kn, 0.072, suit); limb(sm, kn, ft, 0.06, suit);
      at(sm, new T.SphereGeometry(0.068, 12, 10), blk, kn[0], kn[1] + 0.02, kn[2]);
      at(sm, new T.CapsuleGeometry(0.058, 0.12, 4, 10), blk, ft[0] + 0.05, ft[1] - 0.02, ft[2], 0, 0, Math.PI / 2);
    });
    return sm;
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
    return { T: T, S: S, LIST: LIST, OBJ: OBJ, esc: esc, imperial: imperial, fmtAU: fmtAU, fmtV: fmtV, flyTo: flyTo };
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
    var h = "<h3>" + esc(o.id === "roadster" ? "Tesla Roadster / Starman" : o.name) + (o.kind === "craft" ? '<span class="s3-tag">illustrative model</span>' : "") + '<button type="button" class="s3-tog" aria-expanded="' + (S.infoOpen ? "true" : "false") + '">' + (S.infoOpen ? "Less" : "More") + "</button></h3><div class=\"s3-body\">", c = o.d;
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
    var tg = S.info.querySelector(".s3-tog"); if (tg) tg.addEventListener("click", function () { S.infoOpen = !S.infoOpen; S.info.classList.toggle("open", S.infoOpen); tg.textContent = S.infoOpen ? "Less" : "More"; tg.setAttribute("aria-expanded", S.infoOpen ? "true" : "false"); });
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
    FLY = { t0: performance.now(), dur: 1300, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: tgt, toP: tgt.clone().add(dir.multiplyScalar(dist)) };
    info(o);
  }
  function tracks(sel) {   /* fade every trajectory, highlight the selected one */
    LIST.forEach(function (x) { (x.node.userData.lines || []).forEach(function (l) { l.material.opacity = !sel ? l.userData.base : x === sel ? Math.min(1, l.userData.base * 3.2) : 0.06; }); });
    (S.rings || []).forEach(function (r) { r.material.opacity = sel ? 0.18 : 0.35; });
  }
  function overview() { SEL = null; tracks(null); var far = compressed ? 110 : 160; FLY = { t0: performance.now(), dur: 1000, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: new T.Vector3(), toP: new T.Vector3(0, far * 0.75, far) }; info(null); }
  var tmp = new T.Vector3();
  function frame(now) {
    raf = w.requestAnimationFrame(frame); if (d.hidden) return;
    if (FLY) { var k = Math.min(1, (now - FLY.t0) / FLY.dur), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; S.cam.position.lerpVectors(FLY.fromP, FLY.toP, e); S.ctl.target.lerpVectors(FLY.fromT, FLY.toT, e); if (k >= 1) FLY = null; }
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
    el.querySelector("#s3_back").addEventListener("click", close);
    el.querySelector("#s3_all").addEventListener("click", overview);
    el.querySelector("#s3_sun").addEventListener("click", function () { focus("sun"); });
    el.querySelector("#s3_scale").addEventListener("click", function () { compressed = !compressed; this.setAttribute("aria-pressed", compressed ? "false" : "true"); var id = SEL && SEL.id; if (DATA) build(); if (id) focus(id); else overview(); });
    var ray = new T.Raycaster(), dn = null;
    S.r.domElement.addEventListener("pointerdown", function (e) { dn = [e.clientX, e.clientY]; });
    S.r.domElement.addEventListener("pointerup", function (e) {
      if (!dn || Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 6) return;
      var rc = S.r.domElement.getBoundingClientRect(); ray.setFromCamera(new T.Vector2((e.clientX - rc.left) / rc.width * 2 - 1, -(e.clientY - rc.top) / rc.height * 2 + 1), S.cam);
      var hit = ray.intersectObjects(S.root.children, true).filter(function (h) { return h.object.type === "Mesh"; })[0];
      if (!hit) return; var n = hit.object; while (n && n.parent !== S.root) n = n.parent; var o = LIST.filter(function (x) { return x.node === n; })[0]; if (o) focus(o.id);
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
