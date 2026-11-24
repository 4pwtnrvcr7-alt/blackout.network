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
      ".s3-info a{color:#b9c6ff}.s3-msg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);opacity:.8}";
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
  function screenTex() {
    var c = d.createElement("canvas"); c.width = 256; c.height = 96; var g = c.getContext("2d");
    g.fillStyle = "#06120a"; g.fillRect(0, 0, 256, 96); g.fillStyle = "#7dff9a"; g.font = "bold 40px Arial,Helvetica,sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("DON'T PANIC", 128, 50);
    var t = new T.CanvasTexture(c); t.anisotropy = 4; return t;
  }
  function M(c, o) { return new T.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.5, metalness: 0.1 }, o || {})); }
  function box(g, sx, sy, sz, mat, x, y, z) { var m = new T.Mesh(new T.BoxGeometry(sx, sy, sz), mat); m.position.set(x, y, z); g.add(m); return m; }

  /* Original procedural Tesla Roadster (2008, cherry red) with Starman. Length ~4 model units, x = forward. */
  function roadster() {
    var g = new T.Group(), red = M(0xb3121f, { roughness: 0.28, metalness: 0.35 }), blk = M(0x111214, { roughness: 0.8 }), chrome = M(0xcfd3d8, { metalness: 0.9, roughness: 0.25 }), glass = new T.MeshStandardMaterial({ color: 0x9fb6c8, transparent: true, opacity: 0.35, roughness: 0.05 });
    var sh = new T.Shape(); /* side profile (x forward, y up) */
    sh.moveTo(-1.95, 0.25); sh.lineTo(-2.0, 0.62); sh.quadraticCurveTo(-1.9, 0.86, -1.5, 0.9); sh.lineTo(-0.55, 0.92); sh.lineTo(0.35, 0.86);
    sh.quadraticCurveTo(1.3, 0.78, 1.85, 0.6); sh.quadraticCurveTo(2.05, 0.5, 2.0, 0.28); sh.lineTo(1.6, 0.22);
    sh.absarc(1.25, 0.28, 0.36, 0, Math.PI, false); sh.lineTo(-0.95, 0.22); sh.absarc(-1.3, 0.28, 0.36, 0, Math.PI, false); sh.lineTo(-1.95, 0.25);
    var body = new T.Mesh(new T.ExtrudeGeometry(sh, { depth: 1.62, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.06, bevelSegments: 3, curveSegments: 18 }), red);
    body.position.z = -0.81; g.add(body);
    /* cockpit cut-out look: black tub + seats */
    box(g, 1.25, 0.14, 1.4, blk, -0.25, 0.93, 0);
    box(g, 0.42, 0.62, 0.55, blk, -0.6, 1.15, 0.35); box(g, 0.42, 0.62, 0.55, blk, -0.6, 1.15, -0.35);
    /* windshield frame + glass */
    var ws = new T.Mesh(new T.PlaneGeometry(1.5, 0.5), glass); ws.position.set(0.45, 1.15, 0); ws.rotation.set(0, Math.PI / 2, 0); ws.rotateX(-0.75); g.add(ws);
    box(g, 0.05, 0.05, 1.55, chrome, 0.32, 1.35, 0);
    /* dashboard + screen reading DON'T PANIC */
    box(g, 0.35, 0.18, 1.45, blk, 0.32, 1.03, 0);
    var scr = new T.Mesh(new T.PlaneGeometry(0.5, 0.19), new T.MeshBasicMaterial({ map: screenTex() })); scr.position.set(0.12, 1.16, 0); scr.rotation.y = -Math.PI / 2; scr.rotateX(-0.35); g.add(scr);
    /* steering wheel */
    var sw = new T.Mesh(new T.TorusGeometry(0.17, 0.025, 8, 24), blk); sw.position.set(0.05, 1.18, 0.35); sw.rotation.y = Math.PI / 2; sw.rotateX(0.5); g.add(sw);
    /* wheels */
    [[1.25, 0.82], [1.25, -0.82], [-1.3, 0.82], [-1.3, -0.82]].forEach(function (p) {
      var t = new T.Mesh(new T.CylinderGeometry(0.33, 0.33, 0.24, 28), blk); t.rotation.x = Math.PI / 2; t.position.set(p[0], 0.28, p[1]); g.add(t);
      var r = new T.Mesh(new T.CylinderGeometry(0.2, 0.2, 0.25, 10), chrome); r.rotation.x = Math.PI / 2; r.position.set(p[0], 0.28, p[1]); g.add(r);
    });
    /* lights, mirrors */
    [0.55, -0.55].forEach(function (z) {
      var hl = new T.Mesh(new T.SphereGeometry(0.11, 12, 8), M(0xf4f6ff, { emissive: 0x333344 })); hl.scale.set(0.6, 0.6, 1); hl.position.set(1.95, 0.55, z); g.add(hl);
      var tl = box(g, 0.05, 0.1, 0.3, M(0x5a0008, { emissive: 0x220000 }), -2.06, 0.62, z * 1.1);
      box(g, 0.12, 0.08, 0.06, red, 0.35, 1.2, z * 1.55);
    });
    /* Starman: white suit, black panels, dark visor; driver's seat (left-hand drive, +z), right arm on the door */
    var suit = M(0xf2f2f2, { roughness: 0.6 }), pan = M(0x1a1a1a, { roughness: 0.6 });
    var sm = new T.Group(); sm.position.set(-0.55, 1.0, 0.35);
    var torso = new T.Mesh(new T.CylinderGeometry(0.2, 0.18, 0.62, 16), suit); torso.position.y = 0.42; torso.rotation.z = 0.2; sm.add(torso);
    var chest = new T.Mesh(new T.BoxGeometry(0.06, 0.3, 0.28), pan); chest.position.set(0.18, 0.48, 0); chest.rotation.z = 0.2; sm.add(chest);
    var helm = new T.Mesh(new T.SphereGeometry(0.19, 24, 18), suit); helm.position.set(0.08, 0.88, 0); sm.add(helm);
    var vis = new T.Mesh(new T.SphereGeometry(0.155, 24, 18, -Math.PI / 2.4, Math.PI / 1.2, Math.PI / 4, Math.PI / 2.2), new T.MeshStandardMaterial({ color: 0x050608, metalness: 0.9, roughness: 0.08 }));
    vis.position.set(0.11, 0.88, 0); vis.rotation.y = Math.PI / 2; sm.add(vis);
    var la = new T.Mesh(new T.CylinderGeometry(0.06, 0.055, 0.55, 10), suit); la.position.set(0.25, 0.42, -0.2); la.rotation.z = -1.1; sm.add(la);
    var ra = new T.Mesh(new T.CylinderGeometry(0.06, 0.055, 0.5, 10), suit); ra.position.set(0.05, 0.5, 0.27); ra.rotation.x = -0.9; sm.add(ra);
    [0.1, -0.1].forEach(function (z) { var lg = new T.Mesh(new T.CylinderGeometry(0.075, 0.065, 0.7, 10), suit); lg.position.set(0.4, 0.13, z); lg.rotation.z = Math.PI / 2.2; sm.add(lg); var bt = box(sm, 0.16, 0.1, 0.1, pan, 0.78, 0.02, z); });
    g.add(sm);
    g.userData.size = 4.2;
    return g;
  }
  /* Simple original spacecraft models (recognizable shapes, illustrative). */
  function craftModel(id) {
    var g = new T.Group(), foil = M(0xc9a13b, { metalness: 0.7, roughness: 0.35 }), pv = M(0x1b2a5a, { metalness: 0.3, roughness: 0.4 }), wht = M(0xe9e9e9), gry = M(0x8a8f99, { metalness: 0.6 });
    if (id === "voyager1" || id === "voyager2" || id === "newhorizons") {
      var dish = new T.Mesh(new T.SphereGeometry(1.8, 28, 10, 0, Math.PI * 2, 0, 0.55), wht); dish.material.side = T.DoubleSide; dish.rotation.x = Math.PI; dish.position.y = 1.6; g.add(dish);
      box(g, 1.1, 0.6, 1.1, gry, 0, 0.6, 0);
      if (id !== "newhorizons") { var boom = box(g, 4.5, 0.05, 0.05, gry, 2.6, 0.5, 0); var rtg = box(g, 0.08, 0.08, 2.6, gry, 0, 0.4, -1.6); }
      else box(g, 0.3, 0.3, 1.2, gry, 0, 0.3, -1);
    } else if (id === "jwst") {
      var sh = new T.Mesh(new T.CircleGeometry(3, 5), M(0xd7c7e8, { metalness: 0.6, side: T.DoubleSide })); sh.rotation.x = -Math.PI / 2; g.add(sh);
      var mir = new T.Mesh(new T.CircleGeometry(1.4, 6), M(0xd9a930, { metalness: 1, roughness: 0.15, side: T.DoubleSide })); mir.position.y = 1.4; g.add(mir);
    } else if (id === "parker") {
      var shld = new T.Mesh(new T.CylinderGeometry(1.2, 1.2, 0.15, 24), M(0xf2f2f2)); shld.position.y = 1.2; g.add(shld);
      box(g, 0.8, 1.4, 0.8, foil, 0, 0.3, 0); box(g, 2.4, 0.04, 0.5, pv, 0, 0.1, 0);
    } else {
      box(g, 1, 1, 1, foil, 0, 0, 0); box(g, 4.2, 0.05, 0.9, pv, 0, 0, 0);
      var ant = new T.Mesh(new T.ConeGeometry(0.4, 0.4, 16, 1, true), wht); ant.position.set(0, 0.7, 0); g.add(ant);
    }
    g.userData.size = 5;
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
    return line(pts, 0x8090b0, 0.35);
  }
  function addObj(o) { OBJ[o.id] = o; LIST.push(o); S.root.add(o.node); }

  function build() {
    var root = S.root; while (root.children.length) root.remove(root.children[0]); OBJ = {}; LIST = [];
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
      if (c.geo_km && E) { var gk = c.geo_km, Lg = Math.hypot(gk[0], gk[1], gk[2]) || 1; node.position.copy(E.node.position).add(new T.Vector3(gk[0] / Lg, gk[2] / Lg, -gk[1] / Lg).multiplyScalar(c.id === "jwst" ? 1.9 : 1.6)); }
      else node.position.copy(V(c.pos));
      if (c.track && c.track.length > 1 && !c.geo_km) {
        var now = Date.now() / 864e5, past = [], fut = [];
        c.track.forEach(function (t) { var v = V([t[1], t[2], t[3]]); if (t[0] <= now) past.push(v); else fut.push(v); });
        past.push(node.position.clone()); fut.unshift(node.position.clone());
        if (past.length > 1) root.add(line(past, isR ? 0xff6b78 : 0x9fb2ff, 0.75));
        if (fut.length > 1) { var lf = line(fut, 0xffffff, 0.5); root.add(lf); }
      }
      model.userData.spin = isR;
      addObj({ id: c.id, name: c.name, kind: "craft", node: node, model: model, size: (model.userData.size || 4) * sc, d: c });
    });
    labels();
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
    var h = "<h3>" + esc(o.id === "roadster" ? "Tesla Roadster / Starman" : o.name) + (o.kind === "craft" ? '<span class="s3-tag">illustrative model</span>' : "") + "</h3>", c = o.d;
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
      if (c.id === "roadster") h += "<p>Illustrative model built for this site, not a photo. Real 2018 photos: SpaceX.</p>";
    }
    h += '<p class="s3-k">Positions: <a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener">NASA/JPL Horizons</a>' + (DATA && DATA.epoch ? " · " + esc(DATA.epoch.slice(0, 16).replace("T", " ")) + " UTC" : "") + "</p>";
    S.info.innerHTML = h; S.info.hidden = false;
  }
  function focus(id) {
    var o = OBJ[id]; if (!o) return; SEL = o;
    LIST.forEach(function (x) { if (x.lab) x.lab.classList.toggle("sel", x === o); });
    S.objs.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.id === id ? "true" : "false"); });
    var tgt = o.node.getWorldPosition(new T.Vector3()); if (o.id === "roadster") tgt.y += 0.06; var dist = o.kind === "craft" ? o.size * (o.id === "roadster" ? (S.W < 500 ? 1.5 : 0.95) : 2.2) : o.kind === "sun" ? 26 : Math.max(o.size * 6, 1.5);
    var dir = S.cam.position.clone().sub(S.ctl.target); if (dir.lengthSq() < 1e-9) dir.set(0, 0.4, 1); dir.normalize();
    if (o.kind === "craft") { dir.set(0.55, 0.35, 0.75); if (o.id === "roadster") { o.model.rotation.set(0, 0, 0); dir.set(-0.5, 0.72, -0.5); } dir.normalize(); }
    FLY = { t0: performance.now(), dur: 1300, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: tgt, toP: tgt.clone().add(dir.multiplyScalar(dist)) };
    info(o);
  }
  function overview() { SEL = null; var far = compressed ? 110 : 160; FLY = { t0: performance.now(), dur: 1000, fromP: S.cam.position.clone(), fromT: S.ctl.target.clone(), toT: new T.Vector3(), toP: new T.Vector3(0, far * 0.75, far) }; info(null); }
  var tmp = new T.Vector3();
  function frame(now) {
    raf = w.requestAnimationFrame(frame); if (d.hidden) return;
    if (FLY) { var k = Math.min(1, (now - FLY.t0) / FLY.dur), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; S.cam.position.lerpVectors(FLY.fromP, FLY.toP, e); S.ctl.target.lerpVectors(FLY.fromT, FLY.toT, e); if (k >= 1) FLY = null; }
    S.ctl.update();
    var cd = S.cam.position.length();
    LIST.forEach(function (o) {
      if (o.model) {
        if (o.model.userData.spin && SEL !== o) { o.model.rotation.y += 0.002; o.model.rotation.x = Math.sin(now / 9000) * 0.25; }
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
    S.r = new T.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true }); S.r.setPixelRatio(Math.min(2, w.devicePixelRatio || 1)); el.insertBefore(S.r.domElement, el.firstChild);
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
  w.BNSolar = { open: open, close: close, focus: function (id) { focus(id); }, _state: function () { return { data: !!DATA, objects: LIST.map(function (o) { return o.id; }), sel: SEL && SEL.id, open: !!(S.el && !S.el.hidden) }; } };
})(window);
