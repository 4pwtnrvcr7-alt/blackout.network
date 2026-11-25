/* Planet surfaces, close zoom and landing-site pins for the solar explorer (pt1837u).
   Lazy-loaded by solar3d.js. Textures: NASA/USGS public-domain maps served from /api/netmap/planets/. */
(function (w) {
  "use strict";
  var T = w.THREE; if (!T || w.BNPlanets) return;
  var API = null, SITES = null, PINS = [], SITE = null, TEX = {}, CS = {};
  var BASE = "/api/netmap/planets";
  var SEG = { moon: 128, mars: 96, earth: 64, jupiter: 64, saturn: 64, default: 48 };
  var CLOSE = { moon: 2.2, mars: 2.3, earth: 3.2 };

  function esc(s) { return API ? API.esc(s) : String(s == null ? "" : s); }
  function imperial() { try { return !w.BNUnits || !w.BNUnits.isImperial || w.BNUnits.isImperial(); } catch (e) { return true; } }
  function fmtKm(km) {
    if (km == null) return "–";
    if (imperial()) return Math.round(km * 0.621371).toLocaleString("en-US") + " mi";
    return Math.round(km).toLocaleString("en-US") + " km";
  }
  function fmtCoord(lat, lon) {
    var L = ((lon + 540) % 360) - 180;
    var ns = (lat < 0 ? Math.abs(lat).toFixed(3) + "°S" : lat.toFixed(3) + "°N");
    var ew = (L < 0 ? Math.abs(L).toFixed(3) + "°W" : L.toFixed(3) + "°E");
    return ns + ", " + ew;
  }
  function fmtDate(iso) {
    if (!iso) return "";
    var p = iso.split("-").map(Number), months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    if (p.length < 3 || !p[1]) return iso;
    return p[2] + " " + months[p[1] - 1] + " " + p[0];
  }
  function lon360(lon) { var L = Number(lon); if (L > 180) L -= 360; if (L < -180) L += 360; return L; }
  function latLonLocal(lat, lon, r) {
    var L = lon360(lon), phi = (L + 180) * Math.PI / 180, th = (90 - lat) * Math.PI / 180;
    return new T.Vector3(-Math.cos(phi) * Math.sin(th) * r, Math.cos(th) * r, Math.sin(phi) * Math.sin(th) * r);
  }
  function sphereOf(o) {
    if (!o || !o.node) return null;
    if (o.node.isMesh && o.node.geometry && o.node.geometry.type === "SphereGeometry") return o.node;
    var found = null;
    o.node.traverse(function (c) {
      if (found) return;
      if (c.isMesh && c.geometry && c.geometry.type === "SphereGeometry" && !c.userData.pin && !c.userData.cap && !c.userData.aurora && !c.userData.atmo && !c.userData.night) found = c;
    });
    return found;
  }
  function sRGB(tex) {
    if ("SRGBColorSpace" in T) tex.colorSpace = T.SRGBColorSpace;
    else if ("sRGBEncoding" in T) tex.encoding = T.sRGBEncoding;
    tex.anisotropy = (API && API.S && API.S.r && API.S.r.capabilities) ? Math.min(8, API.S.r.capabilities.getMaxAnisotropy()) : 4;
    tex.needsUpdate = true;
    return tex;
  }
  function loadTex(name, done) {
    if (TEX[name]) { done(TEX[name]); return; }
    var loader = new T.TextureLoader();
    loader.load(BASE + "/" + name, function (t) { TEX[name] = sRGB(t); done(TEX[name]); }, undefined, function () { done(null); });
  }

  function fixLights() {
    var S = API && API.S; if (!S || !S.scene) return;
    S.scene.traverse(function (obj) {
      if (obj.isAmbientLight) obj.intensity = 0.045;
      if (obj.isPointLight) { obj.intensity = 1.15; obj.color.setHex(0xffffff); obj.decay = 0; obj.distance = 0; }
      if (obj.isDirectionalLight) obj.intensity = 0;
    });
    if (S.r) S.r.toneMappingExposure = 1.08;
  }

  function oceanRoughness(tex, done) {
    try {
      var img = tex.image; if (!img) return done(null);
      var c = document.createElement("canvas");
      c.width = Math.min(1024, img.width || 1024);
      c.height = Math.min(512, img.height || 512);
      var ctx = c.getContext("2d");
      ctx.drawImage(img, 0, 0, c.width, c.height);
      var data = ctx.getImageData(0, 0, c.width, c.height), d = data.data, i;
      for (i = 0; i < d.length; i += 4) {
        var r = d[i], g = d[i + 1], b = d[i + 2];
        var ocean = b > r + 16 && b > g + 6;
        var v = ocean ? 180 : 230;
        d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255;
      }
      ctx.putImageData(data, 0, 0);
      var rt = new T.CanvasTexture(c);
      if ("SRGBColorSpace" in T) rt.colorSpace = T.LinearSRGBColorSpace || T.NoColorSpace || rt.colorSpace;
      else if ("LinearEncoding" in T) rt.encoding = T.LinearEncoding;
      rt.wrapS = T.ClampToEdgeWrapping; rt.wrapT = T.ClampToEdgeWrapping;
      done(rt);
    } catch (e) { done(null); }
  }

  function addNightLights(o, mesh, nightTex) {
    mesh.children.slice().forEach(function (c) { if (c.userData && c.userData.night) mesh.remove(c); });
    var u = { map: { value: nightTex }, sunDir: { value: new T.Vector3(0, 1, 0) } };
    var mat = new T.ShaderMaterial({
      uniforms: u,
      vertexShader: [
        "#include <common>",
        "#include <logdepthbuf_pars_vertex>",
        "varying vec2 vUv; varying vec3 vObjN;",
        "void main() {",
        "  vUv = uv;",
        "  vObjN = normalize(normal);",
        "  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);",
        "  #include <logdepthbuf_vertex>",
        "}"
      ].join("\n"),
      fragmentShader: [
        "#include <common>",
        "#include <logdepthbuf_pars_fragment>",
        "uniform sampler2D map; uniform vec3 sunDir;",
        "varying vec2 vUv; varying vec3 vObjN;",
        "void main() {",
        "  #include <logdepthbuf_fragment>",
        "  float night = 1.0 - smoothstep(-0.08, 0.2, dot(normalize(vObjN), normalize(sunDir)));",
        "  vec3 lights = texture2D(map, vUv).rgb;",
        "  gl_FragColor = vec4(lights * night * 1.35, 1.0);",
        "}"
      ].join("\n"),
      blending: T.AdditiveBlending,
      transparent: true,
      depthWrite: false,
      toneMapped: false,
      side: T.FrontSide
    });
    mat.userData.sunDirObj = u.sunDir;
    var m = new T.Mesh(mesh.geometry, mat);
    m.scale.setScalar(1.003);
    m.userData.night = true;
    m.renderOrder = 2;
    mesh.add(m);
  }

  function addAtmosphere(o, mesh) {
    mesh.children.slice().forEach(function (c) { if (c.userData && c.userData.atmo) mesh.remove(c); });
    var mat = new T.ShaderMaterial({
      uniforms: { color: { value: new T.Color(0x4f96ff) } },
      vertexShader: [
        "#include <common>",
        "#include <logdepthbuf_pars_vertex>",
        "varying vec3 vN; varying vec3 vV;",
        "void main() {",
        "  vN = normalize(normalMatrix * normal);",
        "  vec4 mv = modelViewMatrix * vec4(position, 1.0);",
        "  vV = normalize(-mv.xyz);",
        "  gl_Position = projectionMatrix * mv;",
        "  #include <logdepthbuf_vertex>",
        "}"
      ].join("\n"),
      fragmentShader: [
        "#include <common>",
        "#include <logdepthbuf_pars_fragment>",
        "uniform vec3 color;",
        "varying vec3 vN; varying vec3 vV;",
        "void main() {",
        "  #include <logdepthbuf_fragment>",
        "  float f = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 3.8);",
        "  gl_FragColor = vec4(color * f * 0.62, 1.0);",
        "}"
      ].join("\n"),
      blending: T.AdditiveBlending,
      transparent: true,
      depthWrite: false,
      side: T.BackSide,
      toneMapped: false
    });
    var atmo = new T.Mesh(new T.SphereGeometry(o.size * 1.055, 64, 48), mat);
    atmo.userData.atmo = true;
    atmo.renderOrder = 1;
    mesh.add(atmo);
  }

  function applyMap(o, file) {
    var mesh = sphereOf(o); if (!mesh) return;
    var segs = SEG[o.id] || SEG.default;
    var old = mesh.geometry;
    mesh.geometry = new T.SphereGeometry(o.size, segs, Math.round(segs * 0.65));
    if (old) old.dispose();
    loadTex(file, function (tex) {
      if (!tex) return;
      var isEarth = o.id === "earth";
      var prev = mesh.material;
      var mat = isEarth ? new T.MeshLambertMaterial({
        map: tex,
        color: 0xffffff,
        emissive: 0x000000,
        toneMapped: false
      }) : new T.MeshStandardMaterial({
        map: tex,
        color: 0xffffff,
        roughness: 0.72,
        metalness: 0,
        emissive: 0x000000,
        emissiveIntensity: 0,
        toneMapped: false
      });
      mesh.material = mat;
      if (prev && prev !== mat && prev.dispose) prev.dispose();
      CS[o.id] = { mesh: mesh, ready: true, mat: mat };
      if (isEarth) {
        loadTex("earth_night.jpg", function (night) {
          if (!night) return;
          addNightLights(o, mesh, night);
        });
        addAtmosphere(o, mesh);
      }
    });
  }


  function addHexCap(o) {
    var mesh = sphereOf(o); if (!mesh) return;
    loadTex("saturn_hex.webp", function (tex) {
      if (!tex) return;
      tex.encoding && (tex.encoding = T.sRGBEncoding);
      var alpha = 22 * Math.PI / 180, r = o.size;
      var cap = new T.Mesh(new T.CircleGeometry(r * Math.sin(alpha), 64),
        new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: T.DoubleSide, toneMapped: false }));
      cap.rotation.x = -Math.PI / 2;
      cap.position.y = r * Math.cos(alpha) * 1.001;
      cap.userData.cap = true;
      cap.renderOrder = 2;
      mesh.add(cap);
    });
  }

  function auroraBandTex() {
    if (auroraBandTex._t) return auroraBandTex._t;
    var c = document.createElement("canvas"); c.width = 8; c.height = 128;
    var g = c.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 128);
    gr.addColorStop(0, "rgba(255,255,255,0)");
    gr.addColorStop(0.36, "rgba(255,255,255,0)");
    gr.addColorStop(0.46, "rgba(255,255,255,0.22)");
    gr.addColorStop(0.5, "rgba(255,255,255,0.95)");
    gr.addColorStop(0.54, "rgba(255,255,255,0.22)");
    gr.addColorStop(0.64, "rgba(255,255,255,0)");
    gr.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 8, 128);
    var tex = new T.CanvasTexture(c);
    tex.needsUpdate = true;
    auroraBandTex._t = tex;
    return tex;
  }

  function auroraMat(color, op, tex) {
    return new T.MeshBasicMaterial({
      color: color,
      map: tex,
      alphaMap: tex,
      transparent: true,
      opacity: op,
      blending: T.AdditiveBlending,
      depthWrite: false,
      toneMapped: false,
      side: T.DoubleSide
    });
  }

  function addAurora(o, opt) {
    var mesh = sphereOf(o); if (!mesh) return;
    mesh.children.slice().forEach(function (c) { if (c.userData && c.userData.aurora) mesh.remove(c); });
    var tex = auroraBandTex();
    function ringAt(axis) {
      var g = new T.Group();
      g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), axis.clone().normalize());
      var y = o.size * Math.cos(opt.oval) * 1.014;
      var R = o.size * Math.sin(opt.oval) * 1.014;
      var w = Math.max(o.size * opt.width * 0.55, o.size * 0.01);
      var layers = [
        { inn: Math.max(0.001, R - w * 0.4), out: R + w * 0.4, op: Math.min(0.30, opt.gain * 0.62) },
        { inn: Math.max(0.001, R - w * 1.1), out: R + w * 1.1, op: Math.min(0.20, opt.gain * 0.36) }
      ];
      layers.forEach(function (L) {
        var m = new T.Mesh(new T.RingGeometry(L.inn, L.out, 128), auroraMat(opt.color, L.op, tex));
        m.rotation.x = -Math.PI / 2;
        m.position.y = y;
        m.userData.aurora = true;
        m.renderOrder = 3;
        g.add(m);
      });
      g.userData.aurora = true;
      mesh.add(g);
    }
    ringAt(latLonLocal(opt.nlat, opt.nlon, 1));
    ringAt(latLonLocal(opt.slat, opt.slon, 1));
  }


  function pinMat(color, op) {
    return new T.MeshBasicMaterial({ color: color, transparent: true, opacity: op, side: T.DoubleSide, depthWrite: false, toneMapped: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  }
  function addPin(o, rec, kind) {
    var mesh = sphereOf(o); if (!mesh) return;
    var r = o.size, loc = latLonLocal(rec.lat, rec.lon, r * 1.0018);
    var g = new T.Group(); g.position.copy(loc);
    g.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), loc.clone().normalize());
    var accent = kind === "feature" ? 0xd7c4a2 : 0xf3f5f8;
    var ring = new T.Mesh(new T.RingGeometry(0.36, 0.5, 28), pinMat(accent, 0.96));
    var dot = new T.Mesh(new T.CircleGeometry(0.16, 16), pinMat(accent, 0.96));
    var hit = new T.Mesh(new T.CircleGeometry(1.15, 16), new T.MeshBasicMaterial({ visible: false, side: T.DoubleSide }));
    [ring, dot, hit].forEach(function (m) { m.userData.pin = true; m.userData.site = rec; m.userData.body = o.id; m.userData.kind = kind; g.add(m); });
    mesh.add(g);
    var lab = document.createElement("button");
    lab.type = "button"; lab.className = "s3-lab s3-pin"; lab.textContent = rec.name;
    lab.style.display = "none";
    lab.addEventListener("click", function (e) { e.stopPropagation(); openSite(o, rec, kind); });
    if (API.S.labs) API.S.labs.appendChild(lab);
    PINS.push({ o: o, rec: rec, kind: kind, group: g, lab: lab, loc: loc, r: r });
  }

  function clearPins() {
    PINS.forEach(function (p) {
      if (p.lab && p.lab.parentNode) p.lab.parentNode.removeChild(p.lab);
      if (p.group && p.group.parent) p.group.parent.remove(p.group);
    });
    PINS = []; SITE = null;
  }

  function openSite(o, rec, kind) {
    SITE = rec;
    PINS.forEach(function (p) { if (p.lab) p.lab.classList.toggle("sel", p.rec === rec); });
    var mesh = sphereOf(o); if (!mesh) { siteInfo(o, rec, kind); return; }
    var local = latLonLocal(rec.lat, rec.lon, o.size);
    var world = mesh.localToWorld(local.clone());
    var center = new T.Vector3(); mesh.getWorldPosition(center);
    var outward = world.clone().sub(center).normalize();
    var dist = o.size * (CLOSE[o.id] || 2.4) * 0.72;
    if (API.flyTo) API.flyTo(world, world.clone().add(outward.multiplyScalar(dist)), 1100);
    siteInfo(o, rec, kind);
  }

  function paintInfo(titleInner, bodyInner) {
    if (!API.S.info) return;
    var open = !!API.S.infoOpen;
    var h = "<h3>" + titleInner + '<button type="button" class="s3-tog" aria-expanded="' + (open ? "true" : "false") + '">' + (open ? "Collapse" : "Expand") + "</button></h3><div class=\"s3-body\">" + bodyInner + "</div>";
    API.S.info.innerHTML = h; API.S.info.hidden = false; API.S.info.classList.toggle("open", open);
    var tg = API.S.info.querySelector(".s3-tog");
    if (tg) tg.addEventListener("click", function () {
      API.S.infoOpen = !API.S.infoOpen;
      API.S.info.classList.toggle("open", !!API.S.infoOpen);
      tg.textContent = API.S.infoOpen ? "Collapse" : "Expand";
      tg.setAttribute("aria-expanded", API.S.infoOpen ? "true" : "false");
    });
  }
  function siteInfo(o, rec, kind) {
    API.S.infoOpen = true;
    var tag = kind === "feature" ? "feature" : (o.id === "moon" ? "Moon landing" : "Mars landing");
    var title = esc(rec.name) + (rec.place ? " · " + esc(rec.place) : "") + '<span class="s3-tag">' + esc(tag) + "</span>";
    var h = "";
    if (rec.date) h += "<p>" + esc(fmtDate(rec.date)) + (rec.agency ? " · " + esc(rec.agency) : "") + "</p>";
    h += "<p>Coordinates: " + esc(fmtCoord(rec.lat, rec.lon)) + "</p>";
    if (rec.crew) h += "<p>" + esc(rec.crew) + "</p>";
    if (rec.text) h += "<p>" + esc(rec.text) + "</p>";
    if (rec.width_km) h += "<p>About " + esc(fmtKm(rec.width_km)) + " across.</p>";
    if (rec.source) h += '<p class="s3-k">Source: <a href="' + esc(rec.source) + '" target="_blank" rel="noopener">' + esc(rec.source_name || rec.source) + "</a></p>";
    h += '<p class="s3-k">Surfaces: NASA / USGS public-domain maps. Positions: <a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener">NASA/JPL Horizons</a></p>';
    paintInfo(title, h);
  }

  function planetInfo(o) {
    var c = o.d, earth = API.OBJ.earth && API.OBJ.earth.d, h = "";
    if (c) {
      h += "<p>From the Sun: " + API.fmtAU(Math.hypot.apply(null, c.pos)) + "</p>";
      if (earth && c.id !== "earth") h += "<p>From Earth: " + API.fmtAU(Math.hypot(c.pos[0] - earth.pos[0], c.pos[1] - earth.pos[1], c.pos[2] - earth.pos[2])) + "</p>";
      h += "<p>Orbital speed: " + API.fmtV(c.v_km_s) + "</p>";
    }
    if (o.info) h += "<p>" + esc(o.info) + "</p>";
    if (o.id === "earth") h += "<p>A faint auroral oval sits around each magnetic pole. It is an illustrative shader, not a live space-weather map. City lights on the night side are NASA Black Marble 2016.</p>";
    if (o.id === "jupiter") h += "<p>The Great Red Spot is marked as Cassini recorded it in December 2000. Tap the pin for details. Scroll to explore the cloud bands. A faint persistent auroral oval is drawn at each magnetic pole (illustrative shader).</p>";
    if (o.id === "saturn") h += "<p>The north-pole hexagon is marked; tap the pin or zoom in over the pole. The globe map is a natural-color stand-in graded to Cassini true-color photos; the hexagon overlay is a real Cassini image. A faint auroral oval is drawn at each pole (illustrative shader). See credits.</p>";
    if (o.id === "venus") h += "<p>The globe is a visible-light stand-in in pale cream, color-matched to how Venus looks in ordinary light, where cloud markings are very faint. It is not the Magellan radar surface map. See credits.</p>";
    if (o.id === "uranus") h += "<p>The globe is a pale cyan stand-in color-matched to Voyager 2 true-color photos. See credits.</p>";
    if (o.id === "neptune") h += "<p>The globe is a deep-blue stand-in color-matched to Voyager 2 true-color photos. See credits.</p>";
    if (o.id === "moon") h += "<p>Landing sites are marked (Apollo, Luna, Chang'e, Chandrayaan-3, SLIM, IM-1). Tap a pin or zoom in to read the site. Scroll to see craters.</p>";
    if (o.id === "mars") h += "<p>Landing sites are marked (Viking through Perseverance and Zhurong). Tap a pin or zoom in. Scroll to see craters and canyons.</p>";
    h += '<p class="s3-k">Surface: NASA / USGS public-domain imagery · <a href="/api/netmap/planets/CREDITS.txt" target="_blank" rel="noopener">credits</a></p>';
    h += '<p class="s3-k">Positions: <a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener">NASA/JPL Horizons</a></p>';
    paintInfo(esc(o.name), h);
    return true;
  }

  var HOVER = null, LEADS = [];

  function pxSize(cam, dist, px, H) {
    return 2 * dist * Math.tan((cam.fov * Math.PI) / 360) / Math.max(1, H) * px;
  }

  function updatePins() {
    if (!API || !API.S || !API.S.cam) return;
    var cam = API.S.cam, W = API.S.W, H = API.S.H, tmp = new T.Vector3();
    PINS.forEach(function (p) {
      var mesh = sphereOf(p.o); if (!mesh) return;
      mesh.localToWorld(tmp.copy(p.loc));
      var dist = cam.position.distanceTo(tmp);
      var world = pxSize(cam, dist, 10, H);
      p.group.scale.setScalar(Math.max(world, p.r * 0.0004));
      if (!p.lab) return;
      tmp.project(cam);
      var on = (SITE && SITE.id === p.rec.id) || (HOVER && HOVER.rec === p.rec);
      var vis = on && tmp.z < 1 && Math.abs(tmp.x) < 1.2 && Math.abs(tmp.y) < 1.2;
      if (vis) {
        p.lab.style.display = "";
        p.lab.classList.toggle("sel", !!(SITE && SITE.id === p.rec.id));
        p.lab.style.transform = "translate(" + ((tmp.x + 1) / 2 * W).toFixed(1) + "px," + ((1 - tmp.y) / 2 * H).toFixed(1) + "px) translate(-50%,-150%)";
      } else p.lab.style.display = "none";
    });
  }

  function onPointer(e) {
    if (!API || !API.S || !API.S.r || !PINS.length) return;
    var dn = onPointer._dn; if (!dn) return;
    if (Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 8) return;
    var rec = hitPin(e.clientX, e.clientY); if (!rec) return;
    e.stopImmediatePropagation();
    var o = API.OBJ[rec.body]; if (o) openSite(o, rec.site, rec.kind);
  }
  function onMove(e) {
    if (!API || !PINS.length) return;
    var rec = hitPin(e.clientX, e.clientY);
    var next = rec && PINS.filter(function (p) { return p.rec === rec.site; })[0];
    if (HOVER !== next) HOVER = next || null;
  }
  function hitPin(cx, cy) {
    if (!API || !API.S || !API.S.r) return null;
    var rc = API.S.r.domElement.getBoundingClientRect();
    var ray = new T.Raycaster();
    ray.params.Points = ray.params.Points || {};
    ray.setFromCamera(new T.Vector2((cx - rc.left) / rc.width * 2 - 1, -(cy - rc.top) / rc.height * 2 + 1), API.S.cam);
    var objs = [];
    PINS.forEach(function (p) { p.group.traverse(function (c) { if (c.isMesh) objs.push(c); }); });
    var hit = ray.intersectObjects(objs, true)[0];
    if (!hit || !hit.object.userData.site) return null;
    return { site: hit.object.userData.site, body: hit.object.userData.body, kind: hit.object.userData.kind };
  }

  function ensureLead(i) {
    while (LEADS.length <= i) {
      var el = document.createElement("div"); el.className = "s3-lead"; el.hidden = true;
      if (API.S.labs) API.S.labs.appendChild(el);
      LEADS.push(el);
    }
    return LEADS[i];
  }
  function hideLeads() { LEADS.forEach(function (el) { el.hidden = true; }); }

  function declutterLabels() {
    if (!API || !API.S || !API.S.cam || !API.LIST) { hideLeads(); return; }
    var S = API.S, cam = S.cam, W = S.W, H = S.H, LIST = API.LIST;
    var sel = API.sel ? API.sel() : null;
    var tmp = new T.Vector3(), limb = new T.Vector3();
    var disc = null;
    hideLeads();
    if (sel && (sel.kind === "planet" || sel.id === "sun") && sel.node) {
      sel.node.getWorldPosition(tmp);
      var dist = cam.position.distanceTo(tmp);
      var r = sel.size || 1;
      var scr = tmp.clone().project(cam);
      var cx = (scr.x + 1) / 2 * W, cy = (1 - scr.y) / 2 * H;
      var px = pxSize(cam, Math.max(0.001, dist), 1, H);
      disc = { o: sel, cx: cx, cy: cy, r: r / px * 1.05, world: tmp.clone(), rad: r };
    }
    var items = [];
    LIST.forEach(function (o) {
      if (!o.lab) return;
      o.node.getWorldPosition(tmp);
      var world = tmp.clone();
      tmp.project(cam);
      var sx = (tmp.x + 1) / 2 * W, sy = (1 - tmp.y) / 2 * H;
      var hide = o.lab.style.display === "none";
      if (!hide && disc && o !== disc.o && tmp.z < 1) {
        var dx = sx - disc.cx, dy = sy - disc.cy;
        if (dx * dx + dy * dy < (disc.r + 18) * (disc.r + 18)) {
          var inFront = world.distanceTo(cam.position) < disc.world.distanceTo(cam.position) - disc.rad * 0.8;
          if (!inFront) { o.lab.style.display = "none"; hide = true; }
        }
      }
      if (hide) return;
      var pri = (sel && o === sel) ? 5 : (o.id === "earth" ? 4 : (o.id === "sun" ? 3 : (o.kind === "planet" ? 2 : 1)));
      items.push({ o: o, sx: sx, sy: sy, pri: pri });
    });
    var earth = API.OBJ && API.OBJ.earth;
    if (earth && earth.lab) {
      var closeE = earth.node && cam.position.distanceTo(earth.node.position) < Math.max(28, (earth.size || 1) * 45);
      var eItem = items.filter(function (it) { return it.o === earth; })[0];
      if (!sel && !closeE && eItem) {
        var rad = Math.min(W, H) * 0.28, near = [];
        items.forEach(function (it) {
          if (it.o.kind === "craft" && Math.hypot(it.sx - eItem.sx, it.sy - eItem.sy) < rad) near.push(it);
        });
        if (near.length >= 2) {
          near.forEach(function (it) { it.o.lab.style.display = "none"; });
          items = items.filter(function (it) { return near.indexOf(it) < 0; });
          earth.lab.textContent = "Earth + " + near.length + " craft";
        } else earth.lab.textContent = "Earth";
      } else earth.lab.textContent = "Earth";
    }
    items.sort(function (a, b) { return b.pri - a.pri; });
    var kept = [];
    items.forEach(function (it) {
      var el = it.o.lab, lw = el.offsetWidth || 90, lh = el.offsetHeight || 16;
      var x = it.sx, y = it.sy;
      var left = x - lw / 2, top = y - lh * 1.5;
      if (left < 6) x += 6 - left;
      if (x + lw / 2 > W - 6) x -= (x + lw / 2) - (W - 6);
      if (y - lh * 1.5 < 6) y = 6 + lh * 1.5;
      if (y > H - 8) y = H - 8;
      left = x - lw / 2; top = y - lh * 1.5;
      if (left < 2 || left + lw > W - 2 || top < 2 || y > H - 2) { el.style.display = "none"; return; }
      var hit = false, i;
      for (i = 0; i < kept.length; i++) {
        var k = kept[i];
        if (Math.abs(x - k.x) < (lw + k.w) / 2 + 4 && Math.abs((y - lh) - (k.y - k.h)) < (lh + k.h) / 2 + 4) { hit = true; break; }
      }
      if (hit) {
        if (it.o.id === "earth" || it.o.id === "sun") {
          var k = kept[i], ox = x - k.x, oy = y - k.y, len = Math.hypot(ox, oy) || 1;
          x += ox / len * ((lw + k.w) / 2 + 8);
          y += oy / len * ((lh + k.h) / 2 + 6);
          left = x - lw / 2; top = y - lh * 1.5;
          if (left < 6) x += 6 - left;
          if (x + lw / 2 > W - 6) x -= (x + lw / 2) - (W - 6);
        } else { el.style.display = "none"; return; }
      }
      el.style.display = "";
      el.style.transform = "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) translate(-50%,-150%)";
      kept.push({ x: x, y: y, w: lw, h: lh });
    });
  }

  var _sunLocal = new T.Vector3(), _sunWorld = new T.Vector3(), _worldPos = new T.Vector3();
  function updateSunDirs() {
    var S = API && API.S; if (!S) return;
    Object.keys(CS).forEach(function (id) {
      var rec = CS[id], mesh = rec.mesh; if (!mesh) return;
      mesh.updateWorldMatrix(true, false);
      mesh.getWorldPosition(_worldPos);
      _sunWorld.copy(_worldPos).multiplyScalar(-1);
      if (_sunWorld.lengthSq() > 1e-12) _sunWorld.normalize();
      _sunLocal.set(0, 0, 0);
      mesh.worldToLocal(_sunLocal);
      if (_sunLocal.lengthSq() > 1e-12) _sunLocal.normalize();
      mesh.traverse(function (c) {
        var m = c.material; if (!m || !m.userData) return;
        if (m.userData.sunDirObj) m.userData.sunDirObj.value.copy(_sunLocal);
        if (m.userData.sunDir) m.userData.sunDir.value.copy(_sunWorld);
        if (m.userData.planetPos) m.userData.planetPos.value.copy(_worldPos);
      });
    });
  }

  function fixCraftDots() {
    var S = API && API.S; if (!S || !S.cam) return;
    var cam = S.cam, H = Math.max(1, S.H || 900);
    var half = (cam.fov * Math.PI / 180) / 2;
    var sel = API.sel && API.sel();
    (API.LIST || []).forEach(function (o) {
      if (!o || o.kind !== "craft" || !o.node) return;
      var selected = sel === o;
      if (o.model) o.model.visible = selected;
      var dot = o.node.userData.dot; if (!dot) return;
      var dd = cam.position.distanceTo(o.node.position);
      var world = 2 * Math.tan(half) * dd * (5 / H);
      var sc = world / 0.09;
      if (sc * 0.09 > 0.016) sc = 0.016 / 0.09;
      if (sc < 0.04) sc = 0.04;
      dot.scale.setScalar(sc);
      dot.visible = !selected;
    });
  }

  function fadeGuides() {
    var S = API && API.S; if (!S) return;
    var sel = API.sel && API.sel();
    var zoomed = false;
    if (sel && sel.node && sel.kind !== "sun") {
      zoomed = S.cam.position.distanceTo(sel.node.position) < Math.max(10, (sel.size || 1) * 22);
    }
    (S.rings || []).forEach(function (r) { r.visible = !zoomed; });
  }

  function tick() {
    updatePins();
    declutterLabels();
    updateSunDirs();
    fixCraftDots();
    fadeGuides();
  }

  function css() {
    if (document.getElementById("s3p_css")) return;
    var st = document.createElement("style"); st.id = "s3p_css";
    st.textContent = ".s3-pin{z-index:3;font-size:10px;padding:1px 6px}.s3-pin.sel{background:#e8eaf0;color:#05060a}" +
      ".s3-lead{position:absolute;left:0;top:0;height:1px;background:rgba(223,227,236,.45);transform-origin:0 50%;pointer-events:none;z-index:1}";
    document.head.appendChild(st);
  }

  function decorate() {
    if (!API) return;
    css();
    fixLights();
    clearPins();
    var map = { mercury: "mercury.jpg", venus: "venus.jpg", earth: "earth.jpg", mars: "mars.jpg", jupiter: "jupiter.jpg", saturn: "saturn.jpg", uranus: "uranus.jpg", neptune: "neptune.jpg", moon: "moon.jpg" };
    Object.keys(map).forEach(function (id) {
      var o = API.OBJ[id]; if (o) applyMap(o, map[id]);
    });
    var sat = API.OBJ.saturn; if (sat) addHexCap(sat);
    var earth = API.OBJ.earth;
    if (earth) addAurora(earth, { nlat: 80.7, nlon: -72.7, slat: -74.3, slon: 125.6, oval: 0.40, width: 0.060, gain: 0.32, night: 1, color: 0x3ae87a });
    var jup = API.OBJ.jupiter;
    if (jup) addAurora(jup, { nlat: 80.0, nlon: 200.0, slat: -80.0, slon: 20.0, oval: 0.28, width: 0.042, gain: 0.28, night: 0, color: 0xd98cff });
    if (sat) addAurora(sat, { nlat: 90, nlon: 0, slat: -90, slon: 0, oval: 0.26, width: 0.038, gain: 0.22, night: 0, color: 0x7aa8ff });
    function pinsWhenReady() {
      var moon = API.OBJ.moon, mars = API.OBJ.mars;
      if (SITES && SITES.moon && moon) SITES.moon.forEach(function (rec) { addPin(moon, rec, "landing"); });
      if (SITES && SITES.mars && mars) SITES.mars.forEach(function (rec) { addPin(mars, rec, "landing"); });
      if (SITES && SITES.features) SITES.features.forEach(function (rec) {
        var o = API.OBJ[rec.body]; if (o) addPin(o, rec, "feature");
      });
    }
    if (SITES) pinsWhenReady();
    else {
      var x = new XMLHttpRequest(); x.open("GET", BASE + "/sites.json");
      x.onload = function () { try { SITES = JSON.parse(x.responseText); } catch (e) { SITES = {}; } pinsWhenReady(); };
      x.onerror = function () { SITES = {}; };
      x.send();
    }
  }

  function attach(api) {
    API = api;
    if (api && api.base) BASE = api.base;
    decorate();
    if (API.S && API.S.r && !attach._ptr) {
      attach._ptr = true;
      API.S.r.domElement.addEventListener("pointerdown", function (e) { onPointer._dn = [e.clientX, e.clientY]; }, true);
      API.S.r.domElement.addEventListener("pointerup", onPointer, true);
      API.S.r.domElement.addEventListener("pointermove", onMove, true);
    }
    w.addEventListener("bn-units", function () {
      if (SITE) {
        var p = PINS.filter(function (x) { return x.rec === SITE; })[0];
        if (p) siteInfo(p.o, p.rec, p.kind);
      }
    });
  }

  function info(o, _infoEl) {
    if (!o || !API) return false;
    if (SITE && o && (o.id === "moon" || o.id === "mars" || o.id === "jupiter" || o.id === "saturn")) {
      /* planet re-focus clears a site only when the body itself was chosen, not a pin */
    }
    SITE = null;
    if (o.kind === "planet" && (TEX[o.id + ".jpg"] || o.id === "moon" || o.id === "mars" || o.id === "jupiter" || o.id === "saturn" || o.id === "earth")) {
      return planetInfo(o);
    }
    return false;
  }

  function focusDist(o, dist) {
    if (!o) return dist;
    if (CLOSE[o.id]) return Math.max(o.size * CLOSE[o.id], 0.28);
    return dist;
  }

  function focusDir(o, dir) {
    if (!o || o.id !== "earth" || !o.node) return dir;
    var sunFrom = o.node.position.clone();
    if (sunFrom.lengthSq() < 1e-8) return dir;
    sunFrom.normalize();
    var up = new T.Vector3(0, 1, 0);
    var side = new T.Vector3().crossVectors(sunFrom, up);
    if (side.lengthSq() < 1e-8) side.set(1, 0, 0);
    side.normalize();
    return side.add(up.multiplyScalar(0.28)).add(sunFrom.multiplyScalar(-0.35)).normalize();
  }

  w.BNPlanets = {
    attach: attach,
    info: info,
    focusDist: focusDist,
    focusDir: focusDir,
    tick: tick,
    openSite: function (body, id) {
      var o = API && API.OBJ[body]; if (!o) return;
      var p = PINS.filter(function (x) { return x.o === o && x.rec.id === id; })[0];
      if (p) openSite(p.o, p.rec, p.kind);
    },
    _state: function () {
      var au = [];
      ["earth", "jupiter", "saturn"].forEach(function (id) {
        var o = API && API.OBJ[id], m = sphereOf(o), has = false;
        if (m) m.traverse(function (c) { if (c.userData && c.userData.aurora) has = true; });
        if (has) au.push(id);
      });
      return { attached: !!API, sites: !!(SITES && SITES.moon), pins: PINS.map(function (p) { return p.rec.id; }), site: SITE && SITE.id, textures: Object.keys(TEX), auroras: au };
    }
  };
})(window);
