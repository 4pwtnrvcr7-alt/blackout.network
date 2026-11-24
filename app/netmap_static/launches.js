/* BLACKOUT.NETWORK /grid Sky view: Launches chip (Nov 24 2026, pt1824u).
   Real: launch times, status, vehicle, mission, orbit, pad, LL2 mission timeline, booster landing site and outcome
   (The Space Devs Launch Library 2, cached on our server). Modeled, not telemetry: every path point.
   Own scope and lc* names only: nothing here re-declares a net.js function. */
(function () {
  "use strict";
  var ER = 6371008.8, mob = matchMedia("(max-width: 760px)").matches, reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var LC = { on: true, reveal: false, data: null, sel: -1, anim: null, layer: null, lbl: null, bar: null, t0: 0, loadT: 0, hidden: null };
  var COL = { up: [0.91, 0.93, 0.96], past: [0.62, 0.66, 0.74], boost: [0.31, 0.76, 0.97], ok: [0.36, 0.88, 0.71], bad: [1, 0.35, 0.35] };
  function lcEsc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function lcPos(lon, lat, alt) {
    var r = 1 + (alt || 0) / ER, la = lat * Math.PI / 180, lo = lon * Math.PI / 180, cl = Math.cos(la);
    return [r * cl * Math.sin(lo), r * Math.sin(la), r * cl * Math.cos(lo)];
  }
  function lcProj(m, p) {
    var w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15]; if (w <= 1e-8) return null;
    return [(m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12]) / w, (m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13]) / w, (m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14]) / w];
  }
  function lcNetMs(L) { return Date.parse(L.net); }
  function lcDur(s) {
    s = Math.max(0, Math.floor(s)); var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    function z(n) { return (n < 10 ? "0" : "") + n; }
    if (d) return d + "d " + h + "h " + z(m) + "m";
    return z(h) + ":" + z(m) + ":" + z(x);
  }
  function lcTPlus(s) { s = Math.max(0, Math.round(s)); return "T+" + Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60); }
  function lcClock(L) {
    var dt = (Date.now() - lcNetMs(L)) / 1000, end = L.ascent.length ? L.ascent[L.ascent.length - 1][3] : 0;
    if (dt < 0) return "T-" + lcDur(-dt) + (L.status === "Go" ? "" : " (" + (L.status || "TBD") + ")");
    if (dt <= end && L.status !== "Success" && L.status !== "Failure") return "In flight " + lcTPlus(dt) + " (modeled)";
    if (dt < 86400) return Math.max(1, Math.round(dt / 3600)) + "h ago \u00b7 " + (L.status_name || L.status);
    return Math.round(dt / 86400) + "d ago \u00b7 " + (L.status_name || L.status);
  }
  function lcMission(L) { var n = String(L.name || ""), i = n.indexOf("|"); return i >= 0 ? n.slice(i + 1).trim() : (L.mission || n); }
  function lcVehicle(L) { var n = String(L.name || ""), i = n.indexOf("|"); return i >= 0 ? n.slice(0, i).trim() : (L.vehicle || ""); }

  /* ---------- styles (own sheet; nothing in net.css changes) ---------- */
  var css = document.createElement("style");
  css.textContent = [
    ".nx-lc-lbls{position:absolute;inset:0;pointer-events:none;z-index:3;overflow:hidden}",
    ".nx-lc-l{position:absolute;left:0;top:0;transform:translate(-9999px,0);white-space:nowrap;font-size:11px;font-weight:600;line-height:1.25;color:#E8ECF5;text-shadow:0 0 3px #000,0 0 6px #000}",
    ".nx-lc-pad{pointer-events:auto;cursor:pointer;background:rgba(8,10,16,.72);border:1px solid rgba(232,236,245,.35);border-radius:6px;padding:3px 6px;margin:-6px 0 0 8px}",
    ".nx-lc-pad small{display:block;font-weight:500;color:#AEB4C4;font-variant-numeric:tabular-nums}",
    ".nx-lc-pad.past{border-color:rgba(174,180,196,.25)}",
    ".nx-lc-ev{font-weight:500;color:#C9CCD6;padding-left:8px}",
    ".nx-lc-ev.k-land{color:#5CE1B6}.nx-lc-ev.k-landfail,.nx-lc-ev.k-fail{color:#FF5A5A}.nx-lc-ev.k-boost{color:#4FC3F7}",
    ".nx-lc-ev:before{content:'';position:absolute;left:-3px;top:4px;width:6px;height:6px;border-radius:50%;background:currentColor}",
    ".nx-lc-ev.dim{opacity:0}",
    ".nx-lc-ev.left{padding:0 8px 0 0}.nx-lc-ev.left:before{left:auto;right:-3px}",
    ".nx-lc-bar{position:absolute;left:50%;bottom:10px;transform:translateX(-50%);z-index:6;display:flex;align-items:center;gap:8px;max-width:min(720px,calc(100% - 16px));width:max-content;background:rgba(8,10,16,.86);border:1px solid rgba(232,236,245,.22);border-radius:10px;padding:6px 8px;color:#E8ECF5;font-size:12.5px}",
    ".nx-lc-bar button{all:unset;cursor:pointer;padding:4px 7px;border:1px solid rgba(232,236,245,.3);border-radius:6px;line-height:1;font-size:13px}",
    ".nx-lc-bar .t{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".nx-lc-bar .t b{font-weight:650}.nx-lc-bar .t span{color:#AEB4C4}",
    ".nx-lc-bar input[type=range]{width:120px;accent-color:#E8ECF5}",
    ".nx-lc-bar .tp{font-variant-numeric:tabular-nums;color:#C9CCD6;min-width:44px}",
    ".nx-lc-note{position:absolute;left:8px;bottom:56px;z-index:6;font-size:10.5px;color:#AEB4C4;text-shadow:0 0 3px #000;pointer-events:none}",
    "body.nx-lc-focus #nx_sky_labs,body.nx-lc-focus .nx-sw,body.nx-lc-focus .nx-ss,body.nx-lc-focus .nx-chip,body.nx-lc-focus .nx-ctl,body.nx-lc-focus .nx-leg,body.nx-lc-focus .nx-card,body.nx-lc-focus .maplibregl-ctrl-bottom-right{display:none!important}",
    "@media (max-width:760px){body.nx-lc-focus .nx-sf{display:none!important}.nx-lc-bar{bottom:8px;gap:6px;padding:5px 6px;font-size:12px}.nx-lc-bar input[type=range]{width:84px}.nx-lc-l{font-size:10.5px}.nx-lc-bar .t .v{display:none}.nx-lc-bar .t{max-width:96px}.nx-lc-note{bottom:52px;right:8px}}"
  ].join("\n");
  document.head.appendChild(css);

  /* ---------- data ---------- */
  function lcLoad() {
    if (LC.data && Date.now() - LC.loadT < 600000) return Promise.resolve(LC.data);
    return fetch("/api/netmap/launches", { headers: { Accept: "application/json" } }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { LC.data = j; LC.loadT = Date.now(); lcBuildPads(); return j; });
  }
  function lcList() { return (LC.data && LC.data.launches) || []; }
  function lcBuildPads() {
    /* one label per pad: the next launch there, else the most recent */
    var by = {}, now = Date.now();
    lcList().forEach(function (L, i) {
      var k = L.pad_lat.toFixed(1) + "," + L.pad_lon.toFixed(1), b = by[k] || (by[k] = { ids: [] });
      b.ids.push(i);
    });
    LC.pads = Object.keys(by).map(function (k) {
      var ids = by[k].ids, up = ids.filter(function (i) { return lcNetMs(lcList()[i]) >= now - 1800000; });
      var pick = up.length ? up[0] : ids[ids.length - 1];
      return { i: pick, n: ids.length, ids: ids };
    });
    lcLabelsDom();
  }

  /* ---------- labels ---------- */
  function lcLabelsDom() {
    var map = window.__nxMap; if (!map) return;
    if (!LC.lbl) { LC.lbl = document.createElement("div"); LC.lbl.className = "nx-lc-lbls"; map.getContainer().appendChild(LC.lbl); }
    var h = "";
    (LC.pads || []).forEach(function (p, j) {
      var L = lcList()[p.i], past = lcNetMs(L) < Date.now();
      h += '<div class="nx-lc-l nx-lc-pad' + (past ? " past" : "") + '" data-pad="' + j + '" role="button" tabindex="0" aria-label="' + lcEsc(lcMission(L)) + ' launch">' + lcEsc(lcMission(L)) +
        (p.n > 1 ? ' <span style="color:#AEB4C4;font-weight:500">+' + (p.n - 1) + "</span>" : "") + '<small data-clk="' + p.i + '">' + lcEsc(lcVehicle(L)) + " \u00b7 " + lcEsc(lcClock(L)) + "</small></div>";
    });
    LC.lbl.innerHTML = h + '<div class="nx-lc-evs"></div>';
    LC.lbl.querySelectorAll(".nx-lc-pad").forEach(function (el) {
      function go(e) { e.stopPropagation(); e.preventDefault(); lcSelect((LC.pads[+el.dataset.pad] || {}).i); }
      el.addEventListener("click", go); el.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") go(e); });
    });
  }
  function lcEvLabels() {
    var box = LC.lbl && LC.lbl.querySelector(".nx-lc-evs"); if (!box) return;
    var L = lcList()[LC.sel]; if (!L) { box.innerHTML = ""; return; }
    box.innerHTML = L.labels.map(function (b, j) {
      var left = b.k === "land" || b.k === "landfail" || b.k === "sep";
      var txt = b.k === "liftoff" ? "Liftoff \u00b7 " + (L.pad || "") : b.text;
      return '<div class="nx-lc-l nx-lc-ev k-' + lcEsc(b.k) + (left ? " left" : "") + '" data-ev="' + j + '">' + lcEsc(txt) + "</div>";
    }).join("") + '<div class="nx-lc-l nx-lc-ev k-boost" data-ev="head" style="font-weight:650;color:#E8ECF5"></div>';
  }
  function lcPlace(el, m, p, cw, ch, cen, placed) {
    var q = lcProj(m, p);
    var vis = q && q[2] > -1 && q[2] < 1 && lcFront(p, cen);
    if (!vis) { el.style.transform = "translate(-9999px,0)"; return; }
    var x = Math.round((q[0] + 1) * 0.5 * cw), y = Math.round((1 - q[1]) * 0.5 * ch);
    var w = el.offsetWidth || 0, h = el.offsetHeight || 13;
    if (el.classList.contains("left")) x -= w + 6;   /* booster / landing labels sit left of their point, ascent labels right */
    x = Math.max(4, Math.min(cw - w - 4, x));
    if (placed) {   /* stack labels that would overlap (events close together near the pad) */
      for (var k = 0, moved = true; moved && k < 8; k++) {
        moved = false;
        for (var i = 0; i < placed.length; i++) { var r = placed[i]; if (x < r[0] + r[2] && x + w > r[0] && y < r[1] + r[3] && y + h > r[1]) { y = r[1] + r[3] + 1; moved = true; } }
      }
      placed.push([x, y, w, h]);
    }
    el.style.transform = "translate(" + x + "px," + y + "px)";
  }
  function lcFront(p, cen) { /* hide labels on the far side of the globe */
    var r = Math.hypot(p[0], p[1], p[2]); return (p[0] * cen[0] + p[1] * cen[1] + p[2] * cen[2]) / r > 0.12;
  }
  function lcLabelsFrame(m) {
    if (!LC.lbl) return;
    var map = window.__nxMap, cnv = map.getCanvas(), cw = cnv.clientWidth, ch = cnv.clientHeight, c = map.getCenter(), cen = lcPos(c.lng, c.lat, 0);
    var focus = LC.sel >= 0, padPlaced = [];
    LC.lbl.querySelectorAll(".nx-lc-pad").forEach(function (el) {
      var p = LC.pads[+el.dataset.pad], L = lcList()[p.i];
      if (!LC.on || !LC.reveal || focus) { el.style.transform = "translate(-9999px,0)"; return; }
      lcPlace(el, m, lcPos(L.pad_lon, L.pad_lat, 0), cw, ch, cen, padPlaced);
    });
    var L = lcList()[LC.sel];
    if (!L) return;
    var t = LC.anim ? LC.anim.t : Infinity, placed = [];
    LC.lbl.querySelectorAll(".nx-lc-ev").forEach(function (el) {
      if (el.dataset.ev === "head") {
        var hp = LC.anim ? lcAt(L, LC.anim.t) : null;
        if (!hp) { el.style.transform = "translate(-9999px,0)"; return; }
        el.textContent = lcVehicle(L).replace(/ Block \d+$/, "") + " " + lcTPlus(LC.anim.t) + " \u00b7 " + Math.round(hp.alt / 1000) + " km";
        lcPlace(el, m, lcPos(hp.lon, hp.lat, hp.alt), cw, ch, cen, placed); return;
      }
      var b = L.labels[+el.dataset.ev];
      el.classList.toggle("dim", b.t > t);
      if (b.t > t) { el.style.transform = "translate(-9999px,0)"; return; }
      lcPlace(el, m, lcPos(b.at[0], b.at[1], b.at[2]), cw, ch, cen, placed);
    });
  }
  function lcAt(L, t) { /* modeled position of the upper stage at T+t */
    var a = L.ascent; if (!a.length) return null;
    for (var i = 1; i < a.length; i++) if (a[i][3] >= t) {
      var p = a[i - 1], q = a[i], u = (t - p[3]) / Math.max(1e-6, q[3] - p[3]);
      var dl = q[0] - p[0]; if (dl > 180) dl -= 360; if (dl < -180) dl += 360;
      return { lon: p[0] + dl * u, lat: p[1] + (q[1] - p[1]) * u, alt: p[2] + (q[2] - p[2]) * u, i: i };
    }
    var e = a[a.length - 1]; return { lon: e[0], lat: e[1], alt: e[2], i: a.length };
  }

  /* ---------- 3D layer (true scale, same unit sphere as the satellites) ---------- */
  function lcShader(gl, type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { console.warn("launch3d shader", gl.getShaderInfoLog(s)); return null; } return s; }
  function lcProgram(gl, vs, fs) {
    var a = lcShader(gl, gl.VERTEX_SHADER, vs), b = lcShader(gl, gl.FRAGMENT_SHADER, fs); if (!a || !b) return null;
    var p = gl.createProgram(); gl.attachShader(p, a); gl.attachShader(p, b); gl.bindAttribLocation(p, 0, "a_pos"); gl.linkProgram(p);
    return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
  }
  function lcOnAdd(layer, m, gl) {
    var g2 = typeof WebGL2RenderingContext !== "undefined" && gl instanceof WebGL2RenderingContext;
    var vs = g2 ? "#version 300 es\nuniform mat4 u_matrix;uniform float u_size;in vec3 a_pos;void main(){gl_Position=u_matrix*vec4(a_pos,1.0);gl_PointSize=u_size;}"
                : "uniform mat4 u_matrix;uniform float u_size;attribute vec3 a_pos;void main(){gl_Position=u_matrix*vec4(a_pos,1.0);gl_PointSize=u_size;}";
    var fs = g2 ? "#version 300 es\nprecision mediump float;uniform vec4 u_color;uniform float u_pt;out vec4 o;void main(){if(u_pt>0.5){vec2 p=gl_PointCoord*2.0-1.0;if(dot(p,p)>1.0)discard;}o=u_color;}"
                : "precision mediump float;uniform vec4 u_color;uniform float u_pt;void main(){if(u_pt>0.5){vec2 p=gl_PointCoord*2.0-1.0;if(dot(p,p)>1.0)discard;}gl_FragColor=u_color;}";
    layer.prog = lcProgram(gl, vs, fs); if (!layer.prog) return;
    layer.uM = gl.getUniformLocation(layer.prog, "u_matrix"); layer.uC = gl.getUniformLocation(layer.prog, "u_color");
    layer.uS = gl.getUniformLocation(layer.prog, "u_size"); layer.uP = gl.getUniformLocation(layer.prog, "u_pt");
    layer.buf = gl.createBuffer(); layer.vao = gl.createVertexArray ? gl.createVertexArray() : null;
  }
  function lcStrip(pts, upto, head) {
    var out = [];
    for (var i = 0; i < pts.length; i++) { if (pts[i][3] > upto) break; var p = lcPos(pts[i][0], pts[i][1], pts[i][2]); out.push(p[0], p[1], p[2]); }
    if (head) { var h = lcPos(head.lon, head.lat, head.alt); out.push(h[0], h[1], h[2]); }
    return new Float32Array(out);
  }
  function lcDraw(layer, gl, arr, mode, col, a, size) {
    if (!arr || arr.length < 3) return;
    gl.bindBuffer(gl.ARRAY_BUFFER, layer.buf); gl.bufferData(gl.ARRAY_BUFFER, arr, gl.STREAM_DRAW);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.uniform4f(layer.uC, col[0] * a, col[1] * a, col[2] * a, a); gl.uniform1f(layer.uS, size || 1); gl.uniform1f(layer.uP, mode === gl.POINTS ? 1 : 0);
    gl.drawArrays(mode, 0, arr.length / 3);
  }
  function lcBoosterAt(L, t) {
    var b = L.booster; if (!b.length || t < b[0][3]) return null;
    for (var i = 1; i < b.length; i++) if (b[i][3] >= t) { var p = b[i - 1], q = b[i], u = (t - p[3]) / Math.max(1e-6, q[3] - p[3]); return { lon: p[0] + (q[0] - p[0]) * u, lat: p[1] + (q[1] - p[1]) * u, alt: p[2] + (q[2] - p[2]) * u }; }
    var e = b[b.length - 1]; return { lon: e[0], lat: e[1], alt: e[2] };
  }
  function lcRender(layer, gl, args) {
    var mat = args && args.defaultProjectionData && args.defaultProjectionData.mainMatrix;
    if (!mat || !layer.prog || !LC.on || !LC.reveal || !document.body.classList.contains("nx-sky")) { if (LC.lbl) LC.lbl.style.display = "none"; return; }
    var m = mat instanceof Float32Array ? mat : new Float32Array(mat);
    if (LC.lbl) LC.lbl.style.display = "";
    try {
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(false);
      if (layer.vao) gl.bindVertexArray(layer.vao);
      gl.useProgram(layer.prog); gl.uniformMatrix4fv(layer.uM, false, m); gl.enableVertexAttribArray(0);
      var now = Date.now(), dpr = Math.min(2, window.devicePixelRatio || 1);
      lcList().forEach(function (L, i) {
        var focus = LC.sel >= 0, me = i === LC.sel;
        if (focus && !me) return;
        var past = lcNetMs(L) < now, fail = L.status === "Failure" || L.status === "Partial Failure";
        var col = fail ? COL.bad : past ? COL.past : COL.up, a = me ? 0.95 : 0.4;
        var t = me && LC.anim ? LC.anim.t : Infinity;
        var live = (now - lcNetMs(L)) / 1000;
        if (!me && live >= 0 && live < L.ascent[L.ascent.length - 1][3] && !past) t = live;
        if (!me && !LC.anim) t = Infinity;
        var head = t !== Infinity ? lcAt(L, t) : null;
        lcDraw(layer, gl, lcStrip(L.ascent, t, head), gl.LINE_STRIP, col, a);
        if (L.booster.length && (me || !focus)) {
          var bh = t !== Infinity ? lcBoosterAt(L, t) : null, bcol = L.landing && L.landing.success === false ? COL.bad : COL.boost;
          if (t === Infinity || bh) lcDraw(layer, gl, lcStrip(L.booster, t, bh), gl.LINE_STRIP, bcol, me ? 0.95 : 0.35);
          if (bh) lcDraw(layer, gl, new Float32Array(lcPos(bh.lon, bh.lat, bh.alt)), gl.POINTS, bcol, 1, 7 * dpr);
          if (me && (t === Infinity || t >= L.booster[L.booster.length - 1][3])) { var e = L.booster[L.booster.length - 1]; lcDraw(layer, gl, new Float32Array(lcPos(e[0], e[1], 0)), gl.POINTS, L.landing && L.landing.success === false ? COL.bad : L.landing && L.landing.success ? COL.ok : COL.boost, 1, 9 * dpr); }
        }
        lcDraw(layer, gl, new Float32Array(lcPos(L.pad_lon, L.pad_lat, 0)), gl.POINTS, col, 1, (me ? 9 : 6) * dpr);
        if (head) lcDraw(layer, gl, new Float32Array(lcPos(head.lon, head.lat, head.alt)), gl.POINTS, [1, 1, 1], 1, 9 * dpr);
      });
      gl.disableVertexAttribArray(0); if (layer.vao) gl.bindVertexArray(null); gl.depthMask(true); gl.bindBuffer(gl.ARRAY_BUFFER, null);
    } catch (err) { console.warn("launch3d render", err); }
    lcLabelsFrame(m);
  }
  function lcEnsureLayer() {
    var map = window.__nxMap; if (!map || LC.layer) return;
    if (!map.isStyleLoaded || !map.isStyleLoaded()) { setTimeout(lcEnsureLayer, 250); return; }
    try {
      if (map.getLayer("launch3d")) return;
      map.addLayer({ id: "launch3d", type: "custom", renderingMode: "3d",
        onAdd: function (m, gl) { lcOnAdd(this, m, gl); LC.layer = this; },
        onRemove: function (m, gl) { if (this.buf) gl.deleteBuffer(this.buf); LC.layer = null; },
        render: function (gl, args) { lcRender(this, gl, args); } });
    } catch (e) { console.warn("launch3d", e); setTimeout(lcEnsureLayer, 500); }
  }

  /* ---------- selection, animation, slim bar ---------- */
  function lcRepaint() { var map = window.__nxMap; if (map) map.triggerRepaint(); }
  function lcTEnd(L) { var e = 0; L.labels.forEach(function (b) { if (b.k !== "orbit") e = Math.max(e, b.t); }); return Math.min(L.ascent[L.ascent.length - 1][3], e + 90); }
  function lcBar() {
    var map = window.__nxMap; if (!map) return;
    if (!LC.bar) {
      LC.bar = document.createElement("div"); LC.bar.className = "nx-lc-bar"; LC.bar.setAttribute("role", "group"); LC.bar.setAttribute("aria-label", "Launch");
      LC.note = document.createElement("div"); LC.note.className = "nx-lc-note"; LC.note.textContent = "Modeled trajectory, not telemetry \u00b7 Launch data: The Space Devs Launch Library 2";
      map.getContainer().appendChild(LC.bar); map.getContainer().appendChild(LC.note);
      LC.bar.addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return; e.stopPropagation();
        var a = b.dataset.a;
        if (a === "x") lcClose();
        else if (a === "prev" || a === "next") { var n = lcList().length; lcSelect((LC.sel + (a === "next" ? 1 : n - 1)) % n); }
        else if (a === "play") lcPlay(LC.anim && LC.anim.playing ? "pause" : "play");
      });
      LC.bar.addEventListener("input", function (e) {
        if (e.target.type !== "range") return; var L = lcList()[LC.sel]; if (!L) return;
        lcPlay("pause"); LC.anim = LC.anim || {}; LC.anim.t = (+e.target.value / 1000) * lcTEnd(L); LC.anim.playing = false; lcBarTime(); lcRepaint();
      });
    }
    var L = lcList()[LC.sel]; if (!L) { LC.bar.hidden = true; LC.note.hidden = true; return; }
    LC.bar.hidden = false; LC.note.hidden = false;
    LC.bar.innerHTML = '<button type="button" data-a="prev" aria-label="Previous launch">\u2039</button>' +
      '<button type="button" data-a="play" aria-label="Replay launch">\u25B6</button>' +
      '<input type="range" min="0" max="1000" value="0" aria-label="Launch timeline">' +
      '<span class="tp">T+0:00</span>' +
      '<span class="t"><b>' + lcEsc(lcMission(L)) + '</b> <span class="v">' + lcEsc(lcVehicle(L)) + " \u00b7 " + lcEsc(L.location || L.pad || "") + " \u00b7 <span data-clk2>" + lcEsc(lcClock(L)) + "</span></span></span>" +
      '<button type="button" data-a="next" aria-label="Next launch">\u203A</button><button type="button" data-a="x" aria-label="Close launch">\u00d7</button>';
  }
  function lcBarTime() {
    var L = lcList()[LC.sel]; if (!L || !LC.bar) return;
    var r = LC.bar.querySelector("input[type=range]"), tp = LC.bar.querySelector(".tp"), pb = LC.bar.querySelector('[data-a="play"]');
    var t = LC.anim ? LC.anim.t : 0;
    if (r) r.value = String(Math.round(1000 * Math.min(1, t / lcTEnd(L))));
    if (tp) tp.textContent = lcTPlus(t);
    if (pb) { pb.textContent = LC.anim && LC.anim.playing ? "\u275A\u275A" : "\u25B6"; pb.setAttribute("aria-label", LC.anim && LC.anim.playing ? "Pause" : "Replay launch"); }
  }
  function lcPlay(cmd) {
    var L = lcList()[LC.sel]; if (!L) return;
    if (cmd === "pause") { if (LC.anim) LC.anim.playing = false; lcBarTime(); return; }
    var end = lcTEnd(L), dur = reduce ? 1 : 24000;
    if (!LC.anim || LC.anim.t >= end - 0.5) LC.anim = { t: 0 };
    LC.anim.playing = true; var last = performance.now();
    (function lcStep(now) {
      if (!LC.anim || !LC.anim.playing || LC.sel < 0) return;
      var dt = Math.min(64, now - last); last = now;
      LC.anim.t = Math.min(end, LC.anim.t + end * dt / dur);
      lcBarTime(); lcRepaint();
      if (LC.anim.t >= end) { LC.anim.playing = false; lcBarTime(); return; }
      requestAnimationFrame(lcStep);
    })(last);
    lcBarTime();
  }
  function lcHideOthers(hide) {
    var map = window.__nxMap; if (!map) return;
    var ids = ["sats3d", "sat", "sat-glow", "trk", "sat-sel"];
    if (hide) {
      if (!LC.hidden) { LC.hidden = {}; ids.forEach(function (id) { if (map.getLayer(id)) { LC.hidden[id] = map.getLayoutProperty(id, "visibility") || "visible"; map.setLayoutProperty(id, "visibility", "none"); } }); }
    } else if (LC.hidden) {
      Object.keys(LC.hidden).forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", LC.hidden[id]); }); LC.hidden = null;
    }
  }
  function lcSelect(i) {
    var L = lcList()[i], map = window.__nxMap; if (!L || !map) return;
    LC.sel = i; LC.anim = null; window.__nxSpinHold = true;
    document.body.classList.add("nx-lc-focus"); lcHideOthers(true);
    lcEvLabels(); lcBar();
    var live = (Date.now() - lcNetMs(L)) / 1000;
    var mid = lcAt(L, Math.min(lcTEnd(L) * 0.55, 400)) || { lon: L.pad_lon, lat: L.pad_lat };
    try { map.easeTo({ center: [mid.lon, mid.lat], zoom: mob ? 2.3 : 3, pitch: mob ? 40 : 50, duration: reduce ? 0 : 1000 }); } catch (e) {}
    if (live >= 0 && live < lcTEnd(L) && L.status !== "Success" && L.status !== "Failure") { LC.anim = { t: live, playing: false, live: true }; }
    else setTimeout(function () { if (LC.sel === i) lcPlay("play"); }, reduce ? 0 : 1100);
    lcBarTime(); lcRepaint();
  }
  function lcClose() {
    var map = window.__nxMap; LC.sel = -1; LC.anim = null; window.__nxSpinHold = false;
    document.body.classList.remove("nx-lc-focus"); lcHideOthers(false); lcEvLabels(); lcBar();
    try { map.easeTo({ pitch: 0, zoom: mob ? -0.55 : -0.4, duration: reduce ? 0 : 900 }); } catch (e) {}
    lcRepaint();
  }

  /* ---------- chip ---------- */
  function lcChip() {
    var sf = document.getElementById("nx_sf"); if (!sf || document.getElementById("nx_lc_chip")) return;
    var b = document.createElement("button"); b.type = "button"; b.id = "nx_lc_chip"; b.setAttribute("aria-pressed", LC.on ? "true" : "false");
    b.innerHTML = '<i style="background:#E8ECF5;border-color:#E8ECF5"></i>Launches';
    b.addEventListener("click", function (e) {
      e.stopPropagation(); LC.on = !LC.on; b.setAttribute("aria-pressed", LC.on ? "true" : "false");
      if (!LC.on) { LC.reveal = false; if (LC.sel >= 0) lcClose(); lcRepaint(); return; }
      LC.reveal = true;
      lcEnsureLayer();
      lcLoad().then(function () { lcRepaint(); }, function () { b.setAttribute("aria-pressed", "false"); LC.on = false; LC.reveal = false; b.title = "Launch data is unavailable right now"; });
    });
    sf.insertBefore(b, sf.firstChild);   /* first chip, so it is visible without scrolling the row */
  }
  function lcSkyChanged() {
    var sky = document.body.classList.contains("nx-sky");
    if (!sky && LC.sel >= 0) { LC.sel = -1; LC.anim = null; window.__nxSpinHold = false; document.body.classList.remove("nx-lc-focus"); LC.hidden = null; lcEvLabels(); lcBar(); }
    if (LC.lbl) LC.lbl.style.display = sky && LC.on && LC.reveal ? "" : "none";
    if (sky) { lcChip(); if (LC.on) lcLoad(); }
  }
  function lcLayerIn() {
    if (!document.body.classList.contains("nx-sky") || !LC.on) return;
    LC.reveal = true;
    var b = document.getElementById("nx_lc_chip"); if (b) b.setAttribute("aria-pressed", "true");
    lcEnsureLayer();
    lcLoad().then(function () { lcRepaint(); }, function () {
      var c = document.getElementById("nx_lc_chip");
      if (c) { c.setAttribute("aria-pressed", "false"); c.title = "Launch data is unavailable right now"; }
      LC.on = false; LC.reveal = false;
    });
  }
  window.__nxLaunchLayerIn = lcLayerIn;
  if (window.__nxLaunchLayerInQueued) { window.__nxLaunchLayerInQueued = false; lcLayerIn(); }
  new MutationObserver(lcSkyChanged).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  setInterval(function () { /* countdown text */
    if (!LC.on || document.hidden || !LC.lbl) return;
    LC.lbl.querySelectorAll("[data-clk]").forEach(function (el) { var L = lcList()[+el.dataset.clk]; if (L) el.textContent = lcVehicle(L) + " \u00b7 " + lcClock(L); });
    var c2 = LC.bar && LC.bar.querySelector("[data-clk2]"), L = lcList()[LC.sel]; if (c2 && L) c2.textContent = lcClock(L);
    if (LC.anim && LC.anim.live && L) { LC.anim.t = (Date.now() - lcNetMs(L)) / 1000; lcBarTime(); lcRepaint(); }
    if (Date.now() - LC.loadT > 600000) lcLoad().then(function () { if (LC.sel >= 0) { lcEvLabels(); lcBar(); lcBarTime(); } });
  }, 1000);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && LC.sel >= 0) lcClose(); });
  window.__nxLaunches = { state: LC, select: lcSelect, close: lcClose };
  lcSkyChanged();
})();
