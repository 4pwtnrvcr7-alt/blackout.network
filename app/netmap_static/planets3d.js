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
      if (c.isMesh && c.geometry && c.geometry.type === "SphereGeometry" && !c.userData.pin && !c.userData.cap && !c.userData.aurora) found = c;
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

  function applyMap(o, file) {
    var mesh = sphereOf(o); if (!mesh) return;
    var segs = SEG[o.id] || SEG.default;
    var old = mesh.geometry;
    mesh.geometry = new T.SphereGeometry(o.size, segs, Math.round(segs * 0.65));
    if (old) old.dispose();
    loadTex(file, function (tex) {
      if (!tex) return;
      var prev = mesh.material;
      mesh.material = new T.MeshStandardMaterial({ map: tex, roughness: 0.92, metalness: 0, color: 0xffffff });
      if (o.id === "earth") mesh.material.metalness = 0.05;
      if (prev && prev !== mesh.material && prev.dispose) prev.dispose();
      CS[o.id] = { mesh: mesh, ready: true };
    });
  }

  function addHexCap(o) {
    var mesh = sphereOf(o); if (!mesh) return;
    loadTex("saturn_hex.webp", function (tex) {
      if (!tex) return;
      tex.encoding && (tex.encoding = T.sRGBEncoding);
      var alpha = 22 * Math.PI / 180, r = o.size;
      var cap = new T.Mesh(new T.CircleGeometry(r * Math.sin(alpha), 64),
        new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: T.DoubleSide }));
      cap.rotation.x = -Math.PI / 2;
      cap.position.y = r * Math.cos(alpha) * 1.001;
      cap.userData.cap = true;
      cap.renderOrder = 2;
      mesh.add(cap);
    });
  }

  function pinGeom() {
    if (pinGeom.g) return pinGeom.g;
    pinGeom.g = new T.ConeGeometry(1, 2.4, 8);
    return pinGeom.g;
  }
  function addPin(o, rec, kind) {
    var mesh = sphereOf(o); if (!mesh) return;
    var r = o.size, loc = latLonLocal(rec.lat, rec.lon, r * 1.01);
    var g = new T.Group(); g.position.copy(loc);
    var outward = loc.clone().normalize();
    g.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), outward);
    var scale = Math.max(0.012, r * 0.045);
    var mat = new T.MeshBasicMaterial({ color: kind === "feature" ? 0xd7c4a2 : 0xe8eaf0 });
    var cone = new T.Mesh(pinGeom(), mat);
    cone.position.y = scale * 1.2;
    cone.scale.setScalar(scale);
    cone.userData.pin = true; cone.userData.site = rec; cone.userData.body = o.id; cone.userData.kind = kind;
    g.add(cone);
    var stem = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, 1, 6), mat);
    stem.position.y = scale * 0.45; stem.scale.set(scale, scale, scale);
    stem.userData.pin = true; stem.userData.site = rec; stem.userData.body = o.id;
    g.add(stem);
    mesh.add(g);
    var lab = document.createElement("button");
    lab.type = "button"; lab.className = "s3-lab s3-pin"; lab.textContent = rec.name;
    lab.hidden = true;
    lab.addEventListener("click", function (e) { e.stopPropagation(); openSite(o, rec, kind); });
    if (API.S.labs) API.S.labs.appendChild(lab);
    PINS.push({ o: o, rec: rec, kind: kind, group: g, cone: cone, lab: lab, loc: loc, r: r });
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
    var h = "<h3>" + titleInner + '<button type="button" class="s3-tog" aria-expanded="' + (open ? "true" : "false") + '">' + (open ? "Less" : "More") + "</button></h3><div class=\"s3-body\">" + bodyInner + "</div>";
    API.S.info.innerHTML = h; API.S.info.hidden = false; API.S.info.classList.toggle("open", open);
    var tg = API.S.info.querySelector(".s3-tog");
    if (tg) tg.addEventListener("click", function () {
      API.S.infoOpen = !API.S.infoOpen;
      API.S.info.classList.toggle("open", !!API.S.infoOpen);
      tg.textContent = API.S.infoOpen ? "Less" : "More";
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
    if (o.id === "jupiter") h += "<p>The Great Red Spot is marked as Cassini recorded it in December 2000. Tap the pin for details. Scroll to explore the cloud bands.</p>";
    if (o.id === "saturn") h += "<p>The north-pole hexagon is marked; tap the pin or zoom in over the pole. Atmosphere bands are a natural-color stand-in; see credits.</p>";
    if (o.id === "moon") h += "<p>Landing sites are marked (Apollo, Luna, Chang'e, Chandrayaan-3, SLIM, IM-1). Tap a pin or zoom in to read the site. Scroll to see craters.</p>";
    if (o.id === "mars") h += "<p>Landing sites are marked (Viking through Perseverance and Zhurong). Tap a pin or zoom in. Scroll to see craters and canyons.</p>";
    h += '<p class="s3-k">Surface: NASA / USGS public-domain imagery · <a href="/api/netmap/planets/CREDITS.txt" target="_blank" rel="noopener">credits</a></p>';
    h += '<p class="s3-k">Positions: <a href="https://ssd.jpl.nasa.gov/horizons/" target="_blank" rel="noopener">NASA/JPL Horizons</a></p>';
    paintInfo(esc(o.name), h);
    return true;
  }

  function updatePinLabels() {
    if (!API || !API.S || !API.S.cam) return;
    var cam = API.S.cam, W = API.S.W, H = API.S.H, tmp = new T.Vector3();
    PINS.forEach(function (p) {
      if (!p.lab) return;
      var mesh = sphereOf(p.o); if (!mesh) { p.lab.style.display = "none"; return; }
      mesh.localToWorld(tmp.copy(p.loc));
      var dist = cam.position.distanceTo(tmp);
      var close = dist < p.o.size * 9;
      tmp.project(cam);
      var vis = close && tmp.z < 1 && Math.abs(tmp.x) < 1.15 && Math.abs(tmp.y) < 1.15;
      if (vis) {
        p.lab.style.display = "";
        p.lab.style.transform = "translate(" + ((tmp.x + 1) / 2 * W).toFixed(1) + "px," + ((1 - tmp.y) / 2 * H).toFixed(1) + "px) translate(-50%,-150%)";
      } else p.lab.style.display = "none";
    });
  }

  function onPointer(e) {
    if (!API || !API.S || !API.S.r || !PINS.length) return;
    var dn = onPointer._dn; if (!dn) return;
    if (Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 6) return;
    var rc = API.S.r.domElement.getBoundingClientRect();
    var ray = new T.Raycaster();
    ray.setFromCamera(new T.Vector2((e.clientX - rc.left) / rc.width * 2 - 1, -(e.clientY - rc.top) / rc.height * 2 + 1), API.S.cam);
    var objs = [];
    PINS.forEach(function (p) { p.group.traverse(function (c) { if (c.isMesh) objs.push(c); }); });
    var hit = ray.intersectObjects(objs, true)[0];
    if (!hit || !hit.object.userData.site) return;
    e.stopImmediatePropagation();
    var rec = hit.object.userData.site, body = hit.object.userData.body, kind = hit.object.userData.kind;
    var o = API.OBJ[body]; if (o) openSite(o, rec, kind);
  }

  function css() {
    if (document.getElementById("s3p_css")) return;
    var st = document.createElement("style"); st.id = "s3p_css";
    st.textContent = ".s3-pin{z-index:2;font-size:10px;padding:1px 6px}.s3-pin.sel{background:#e8eaf0;color:#05060a}";
    document.head.appendChild(st);
  }

  function decorate() {
    if (!API) return;
    css();
    clearPins();
    var map = { mercury: "mercury.jpg", venus: "venus.jpg", earth: "earth.jpg", mars: "mars.jpg", jupiter: "jupiter.jpg", saturn: "saturn.jpg", uranus: "uranus.jpg", neptune: "neptune.jpg", moon: "moon.jpg" };
    Object.keys(map).forEach(function (id) {
      var o = API.OBJ[id]; if (o) applyMap(o, map[id]);
    });
    var sat = API.OBJ.saturn; if (sat) addHexCap(sat);
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
    }
    if (!attach._loop) {
      attach._loop = true;
      var tick = function () { updatePinLabels(); w.requestAnimationFrame(tick); };
      w.requestAnimationFrame(tick);
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

  w.BNPlanets = {
    attach: attach,
    info: info,
    focusDist: focusDist,
    openSite: function (body, id) {
      var o = API && API.OBJ[body]; if (!o) return;
      var p = PINS.filter(function (x) { return x.o === o && x.rec.id === id; })[0];
      if (p) openSite(p.o, p.rec, p.kind);
    },
    _state: function () {
      return { attached: !!API, sites: !!(SITES && SITES.moon), pins: PINS.map(function (p) { return p.rec.id; }), site: SITE && SITE.id, textures: Object.keys(TEX) };
    }
  };
})(window);
