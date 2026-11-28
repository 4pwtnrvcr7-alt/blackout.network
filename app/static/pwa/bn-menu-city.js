/* BLACKOUT.NETWORK menu background (Nov 27 2026).
   Bump-style Earth loop (HERO v3h look), adapted as a seamless menu backdrop:
   night lights, grid down, cyan mesh up, then "blackout.network activated".
   Captions baked into the loop: GRID ONLINE, GRID DOWN, blackout.network activated, GRID RESTORED.
   The canvas is pointer-events:none and sits behind the menu links.
   Pauses when the menu is closed or the tab is hidden; prefers-reduced-motion draws one static frame.
   DPR <= 2. Kill switch is BN_MENU_CITY=0 in menu5.py (this file is not loaded). */
(function () {
  if (window.__bnCity) return;
  var RM = false;
  try { RM = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  var MENUS = "#bn-menu.bn-open,#h_menu.open,#w2_menu:not([hidden])";
  var T = 22;
  var STATIC_T = 4.0;
  var VER = "0";
  try {
    var sc = document.currentScript || document.querySelector('script[src*="bn-menu-city.js"]');
    var vm = sc && /[?&]v=([^&]+)/.exec(sc.src);
    if (vm) VER = vm[1];
  } catch (e) {}
  var SRC_M = "/bn-menu-city-m.mp4?v=" + VER;
  var SRC_D = "/bn-menu-city-d.mp4?v=" + VER;
  var all = [];

  function srcFor(w, h) { return (w >= h * 1.05) ? SRC_D : SRC_M; }

  function City(cv) {
    this.cv = cv;
    this.ctx = cv.getContext("2d", { alpha: false, desynchronized: true });
    this.raf = 0;
    this.which = "";
    this.fixed = null;
    this._tick = this.tick.bind(this);
    this.vid = document.createElement("video");
    this.vid.muted = true;
    this.vid.defaultMuted = true;
    this.vid.loop = true;
    this.vid.playsInline = true;
    this.vid.setAttribute("playsinline", "");
    this.vid.setAttribute("muted", "");
    this.vid.setAttribute("aria-hidden", "true");
    this.vid.preload = "auto";
    this.vid.tabIndex = -1;
    this.vid.style.cssText = "position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;pointer-events:none;z-index:-2";
    (document.body || cv.parentNode).appendChild(this.vid);
    var self = this;
    this.vid.addEventListener("loadeddata", function () { self.draw(); });
    this.vid.addEventListener("seeked", function () { self.draw(); });
    this.resize();
    this.sync();
  }

  City.prototype.menuOpen = function () {
    var m = this.cv.closest("#bn-menu,#h_menu,#w2_menu");
    return !!(m && m.matches(MENUS));
  };

  City.prototype.wantPlay = function () {
    return !RM && this.fixed == null && this.menuOpen() && !document.hidden;
  };

  City.prototype.resize = function () {
    var r = this.cv.getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cssW = Math.max(1, r.width), cssH = Math.max(1, r.height);
    var w = Math.max(1, Math.round(cssW * dpr)), h = Math.max(1, Math.round(cssH * dpr));
    if (w * h > 2800000) {
      var k = Math.sqrt(2800000 / (w * h));
      w = Math.max(1, Math.round(w * k));
      h = Math.max(1, Math.round(h * k));
    }
    if (this.cv.width !== w || this.cv.height !== h) { this.cv.width = w; this.cv.height = h; }
    var want = srcFor(cssW, cssH);
    if (want !== this.which) {
      this.which = want;
      this.vid.src = want;
      try { this.vid.load(); } catch (e) {}
    }
    this.draw();
  };

  City.prototype.draw = function () {
    var ctx = this.ctx, cv = this.cv, v = this.vid;
    ctx.fillStyle = "#0B0D10";
    ctx.fillRect(0, 0, cv.width, cv.height);
    if (!v || v.readyState < 2 || !v.videoWidth) return;
    var cw = cv.width, ch = cv.height, vw = v.videoWidth, vh = v.videoHeight;
    var s = Math.max(cw / vw, ch / vh);
    var dw = vw * s, dh = vh * s, dx, dy;
    if (cw >= ch) {
      dx = 0;
      dy = (ch - dh) / 2;
    } else {
      dx = (cw - dw) / 2;
      dy = Math.min(0, ch - dh);
    }
    ctx.drawImage(v, dx, dy, dw, dh);
  };

  City.prototype.tick = function () {
    this.raf = 0;
    this.draw();
    if (this.wantPlay()) this.raf = requestAnimationFrame(this._tick);
  };

  City.prototype.stop = function () {
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
    try { this.vid.pause(); } catch (e) {}
  };

  City.prototype.still = function (t) {
    var self = this;
    var go = function () {
      try {
        var d = self.vid.duration;
        var tt = (t == null || isNaN(t)) ? STATIC_T : t;
        if (d && isFinite(d)) tt = Math.max(0, Math.min(d - 0.05, tt));
        self.vid.currentTime = tt;
      } catch (e) {}
      self.draw();
    };
    if (this.vid.readyState >= 1) go();
    else this.vid.addEventListener("loadedmetadata", go, { once: true });
  };

  City.prototype.sync = function () {
    this.resize();
    if (this.wantPlay()) {
      var p = this.vid.play();
      if (p && p.catch) p.catch(function () {});
      if (!this.raf) this.raf = requestAnimationFrame(this._tick);
    } else {
      this.stop();
      if (RM || this.fixed != null) this.still(this.fixed != null ? this.fixed : STATIC_T);
      else this.draw();
    }
  };

  City.prototype.finishSync = function () {};

  function inMenu(cv) { return cv.closest("#bn-menu,#h_menu,#w2_menu"); }

  function bind(cv) {
    if (cv.__bnCity) return;
    var c = cv.__bnCity = new City(cv);
    all.push(c);
  }

  function scan() {
    var cs = document.querySelectorAll("canvas.m5-city");
    for (var i = 0; i < cs.length; i++) if (inMenu(cs[i])) bind(cs[i]);
    for (var j = 0; j < all.length; j++) all[j].sync();
  }

  function onVis() { for (var i = 0; i < all.length; i++) all[i].sync(); }

  var ro = (window.ResizeObserver) ? new ResizeObserver(function () { for (var i = 0; i < all.length; i++) all[i].resize(); }) : null;
  function watch() {
    scan();
    for (var i = 0; i < all.length; i++) {
      if (ro) try { ro.observe(all[i].cv); } catch (e) {}
      var m = all[i].cv.closest("#bn-menu,#h_menu,#w2_menu");
      if (m && window.MutationObserver && !m.__bnCityObs) {
        m.__bnCityObs = 1;
        new MutationObserver(scan).observe(m, { attributes: true, attributeFilter: ["class", "hidden"] });
      }
    }
  }

  document.addEventListener("visibilitychange", onVis);
  window.addEventListener("resize", function () { for (var i = 0; i < all.length; i++) all[i].resize(); });
  window.__bnCity = {
    all: all, scan: scan, T: T, STATIC_T: STATIC_T,
    freeze: function (t) {
      for (var i = 0; i < all.length; i++) { all[i].fixed = t; all[i].stop(); all[i].still(t); }
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
  else watch();
})();
