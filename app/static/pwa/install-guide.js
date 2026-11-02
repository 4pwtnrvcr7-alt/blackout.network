/* BLACKOUT.NETWORK "Add to Home Screen" sheet (t339/t340). Vanilla JS + inline SVG/CSS animation, no dependencies.
   Rules (Matt, t339/t340): show once to every visitor who has not installed or dismissed; Dismiss = gone for good;
   never shown to anyone who installed; only the steps for THIS phone + browser; understandable in 3 seconds.
   Flows checked Nov 2026 against: Apple Support (Safari iPhone/iPad, Safari Mac), Google Chrome Help (Android, iOS, desktop),
   Microsoft Edge docs, Mozilla Firefox help, Samsung Internet guides. Sources are listed in FLOW_SOURCES below.
   Privacy: detection runs locally (userAgent / userAgentData); nothing is sent anywhere, no analytics.
   Storage: localStorage "bn_installed", "bnig_dismissed" (+ cookie "bnig_dismissed" as backup), sessionStorage "bnig_shown".
   Testing: ?bnig=1 forces the sheet (ignores installed/dismissed/session) for the detected browser. */
(function () {
  "use strict";
  if (window.__bnig) return; window.__bnig = 1;
  try { if (window.top !== window.self) return; } catch (e) { return; }      // never inside iframes
  var IKEY = "bn_installed", DKEY = "bnig_dismissed", SKEY = "bnig_shown", DELAY = 1800, STEP_MS = 2600;
  var ls = function (k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  var ss = function (k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } };
  var ck = function (k, v) { try { if (v === undefined) return (document.cookie.match("(?:^|; )" + k + "=([^;]*)") || [])[1] || null;
    document.cookie = k + "=" + v + "; Max-Age=315360000; Path=/; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : ""); } catch (e) { return null; } };
  var reduced = false; try { reduced = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

  // ---------------- installed / dismissed ----------------
  function standalone() {
    try { if (matchMedia("(display-mode: standalone)").matches || matchMedia("(display-mode: fullscreen)").matches ||
              matchMedia("(display-mode: minimal-ui)").matches || matchMedia("(display-mode: window-controls-overlay)").matches) return true; } catch (e) {}
    return navigator.standalone === true;
  }
  function markInstalled() { ls(IKEY, "1"); ck(IKEY, "1"); }
  function isInstalled() { return ls(IKEY) === "1" || ck(IKEY) === "1"; }
  function isDismissed() { return ls(DKEY) === "1" || ck(DKEY) === "1"; }
  if (standalone()) markInstalled();                                         // launched from the home screen: remember it in this browser too

  // ---------------- detection (local only) ----------------
  function detect() {
    var ua = navigator.userAgent || "", uad = navigator.userAgentData || null, tp = navigator.maxTouchPoints || 0;
    var d = { device: "desktop", os: "other", ver: null, safari: null, browser: "other", inApp: false, mobile: false };
    var iPadDesktop = /Macintosh/.test(ua) && tp > 1;                         // iPadOS "desktop website" mode looks like a Mac
    if (/iPhone|iPod/.test(ua)) d.device = "iphone";
    else if (/iPad/.test(ua) || iPadDesktop) d.device = "ipad";
    else if (/Android/i.test(ua) || (uad && /Android/i.test(uad.platform || ""))) d.device = "android";
    else if (/Macintosh|Mac OS X/.test(ua)) d.os = "mac";
    if (d.device === "iphone" || d.device === "ipad") {
      d.os = "ios"; var m = ua.match(/OS (\d+)[_.](\d+)/); if (m && !iPadDesktop) d.ver = parseFloat(m[1] + "." + m[2]);
    } else if (d.device === "android") d.os = "android";
    var sv = ua.match(/Version\/(\d+)(?:\.(\d+))?/); if (sv) d.safari = parseFloat(sv[1] + "." + (sv[2] || 0));   // Safari 26 freezes the OS number at 18.x, so use Version/
    d.mobile = d.os === "ios" || d.os === "android" || !!(uad && uad.mobile);
    if (/FBAN|FBAV|FB_IAB|Instagram|Line\/|Twitter|LinkedInApp|Snapchat|TikTok|musical_ly|GSA\//.test(ua)) d.inApp = true;
    if (/SamsungBrowser/i.test(ua)) d.browser = "samsung";
    else if (/EdgiOS|EdgA|Edg\//.test(ua)) d.browser = "edge";
    else if (/OPR\/|OPT\/|OPiOS|OPX\//.test(ua)) d.browser = "opera";
    else if (/FxiOS|Firefox\//.test(ua)) d.browser = "firefox";
    else if (/CriOS|Chrome\//.test(ua)) d.browser = "chrome";
    else if (/Safari\//.test(ua)) d.browser = "safari";
    return d;
  }

  // ---------------- drawings: simplified, accurate versions of the real buttons ----------------
  var IC = {
    share: '<path d="M0 -9v11M-4 -5l4-4 4 4"/><path d="M-6 -2h-1.5v10h15v-10h-1.5" />',
    dotsh: '<circle cx="-6" cy="0" r="1.8" class="f"/><circle cx="0" cy="0" r="1.8" class="f"/><circle cx="6" cy="0" r="1.8" class="f"/>',
    dotsv: '<circle cx="0" cy="-6" r="1.8" class="f"/><circle cx="0" cy="0" r="1.8" class="f"/><circle cx="0" cy="6" r="1.8" class="f"/>',
    burger: '<path d="M-7 -5h14M-7 0h14M-7 5h14"/>',
    install: '<rect x="-9" y="-7" width="18" height="12" rx="2"/><path d="M0 -4v6M-3 -1l3 3 3-3M-4 8h8"/>',
    addsq: '<rect x="-7" y="-7" width="14" height="14" rx="3.5"/><path d="M0 -3.5v7M-3.5 0h7"/>',
    plus: '<path d="M0 -6v12M-6 0h6 6"/>',
    back: '<path d="M2 -6l-6 6 6 6"/>', fwd: '<path d="M-2 -6l6 6 -6 6"/>', tabs: '<rect x="-6" y="-6" width="12" height="12" rx="2.5"/>',
    book: '<path d="M-7 -6h6c1 0 1 1 1 1v12c0-1-1-1-1-1h-6zM7 -6h-6c-1 0-1 1-1 1v12c0-1 1-1 1-1h6z"/>',
    file: '<path d="M-5 -7h7l4 4v10h-11z"/>', dock: '<rect x="-9" y="2" width="18" height="5" rx="2"/><rect x="-4" y="-7" width="8" height="7" rx="1.5"/>',
    home: '<path d="M-7 0l7-7 7 7M-5 -2v8h10v-8"/>', app: '<rect x="-7" y="-7" width="14" height="14" rx="3.5"/>',
    pagemenu: '<path d="M-6.5 -4.5h13M-6.5 0h13M-6.5 4.5h8"/>',                                    // Safari 26 Page Menu button (left end of the address bar)
    reload: '<path d="M5.2 -1.8A5.6 5.6 0 1 0 5.4 2.6"/><path d="M5.6 -6.2v4.6H1"/>',
    tabs2: '<rect x="-6.5" y="-3" width="9.5" height="9.5" rx="2.2"/><path d="M-3 -3.4v-1.4a2.2 2.2 0 0 1 2.2-2.2h5.1a2.2 2.2 0 0 1 2.2 2.2v5.1a2.2 2.2 0 0 1-2.2 2.2h-1.3"/>'
  };
  function ico(name, x, y, s) { return '<g transform="translate(' + x + " " + y + ") scale(" + (s || 1) + ')">' + IC[name] + "</g>"; }
  function ring(x, y, r) { return '<circle class="bnig-pulse" cx="' + x + '" cy="' + y + '" r="' + r + '"/><circle class="bnig-ring" cx="' + x + '" cy="' + y + '" r="' + r + '"/>'; }
  // a browser bar (top or bottom of the phone) with icons; the target icon gets the pulsing highlight
  function sceneBar(where, icons, target, url) {
    var W = 300, H = 132, y = where === "top" ? 30 : 100, s = '<svg viewBox="0 0 ' + W + " " + H + '" class="bnig-svg" aria-hidden="true">';
    s += '<rect class="ph" x="1" y="1" width="' + (W - 2) + '" height="' + (H - 2) + '" rx="18"/>';
    s += '<g class="pg">' + [0, 1, 2].map(function (i) { return '<rect x="22" y="' + (where === "top" ? 58 + i * 16 : 18 + i * 16) + '" width="' + (200 - i * 50) + '" height="7" rx="3.5"/>'; }).join("") + "</g>";
    var left = icons.filter(function (i) { return i.side === "l"; }), right = icons.filter(function (i) { return i.side !== "l"; });
    var x0 = 14 + left.length * 34, x1 = W - 14 - right.length * 34;
    s += '<rect class="url" x="' + x0 + '" y="' + (y - 15) + '" width="' + (x1 - x0) + '" height="30" rx="15"/><text class="ut" x="' + (x0 + 14) + '" y="' + (y + 4) + '">' + (url || "blackout.network") + "</text>";
    var tgt = null;
    left.forEach(function (ic, i) { var cx = 30 + i * 34; if (ic.t) tgt = [cx, y]; s += '<g class="ic' + (ic.t ? " on" : "") + '">' + ico(ic.n, cx, y) + "</g>"; });
    right.forEach(function (ic, i) { var cx = x1 + 17 + i * 34; if (ic.t) tgt = [cx, y]; s += '<g class="ic' + (ic.t ? " on" : "") + '">' + ico(ic.n, cx, y) + "</g>"; });
    if (tgt) s = s + ring(tgt[0], tgt[1], 17);
    return s + "</svg>";
  }
  // Safari 26+ on iPhone (Compact tabs, the default): back button, floating address bar with the Page Menu button at its left end
  // and reload at its right end, tabs button on the right. Drawn from Matt's iPhone screenshot (Nov 1 2026) + Apple Support.
  function sceneSafari26() {
    var W = 300, H = 132, y = 100, s = '<svg viewBox="0 0 ' + W + " " + H + '" class="bnig-svg" aria-hidden="true">';
    s += '<rect class="ph" x="1" y="1" width="' + (W - 2) + '" height="' + (H - 2) + '" rx="18"/>';
    s += '<g class="pg">' + [0, 1, 2].map(function (i) { return '<rect x="22" y="' + (18 + i * 16) + '" width="' + (200 - i * 50) + '" height="7" rx="3.5"/>'; }).join("") + "</g>";
    s += '<circle class="url" cx="32" cy="' + y + '" r="16"/><g class="ic">' + ico("back", 31, y) + "</g>";
    s += '<rect class="url" x="56" y="' + (y - 16) + '" width="188" height="32" rx="16"/>';
    s += '<g class="ic on">' + ico("pagemenu", 76, y) + '</g><text class="ut" x="152" y="' + (y + 4) + '" text-anchor="middle">blackout.network</text><g class="ic">' + ico("reload", 226, y, .85) + "</g>";
    s += '<circle class="url" cx="268" cy="' + y + '" r="16"/><g class="ic">' + ico("tabs2", 268, y, .9) + "</g>";
    return s + ring(76, y, 14) + "</svg>";
  }
  // a menu / share sheet with rows; the target row is highlighted
  function sceneMenu(title, rows, target, from) {
    var W = 300, H = 132, s = '<svg viewBox="0 0 ' + W + " " + H + '" class="bnig-svg" aria-hidden="true"><rect class="ph" x="1" y="1" width="' + (W - 2) + '" height="' + (H - 2) + '" rx="18"/>';
    var top = from === "top" ? 10 : 18, mx = 34, mw = W - 68;
    s += '<rect class="menu" x="' + mx + '" y="' + top + '" width="' + mw + '" height="' + (rows.length * 30 + (title ? 22 : 6)) + '" rx="12"/>';
    if (title) s += '<text class="mt" x="' + (mx + 14) + '" y="' + (top + 15) + '">' + title + "</text>";
    var y0 = top + (title ? 22 : 6), tgt = null;
    rows.forEach(function (r, i) {
      var y = y0 + i * 30, on = i === target;
      if (on) { s += '<rect class="row on" x="' + (mx + 4) + '" y="' + y + '" width="' + (mw - 8) + '" height="28" rx="8"/>'; tgt = [mx + mw - 30, y + 14]; }
      s += '<text class="rt' + (on ? " on" : "") + '" x="' + (mx + 16) + '" y="' + (y + 18) + '">' + r[0] + "</text>";
      if (r[1]) s += '<g class="ic' + (on ? " on" : "") + '">' + ico(r[1], mx + mw - 22, y + 14, .8) + "</g>";
    });
    return s + "</svg>";
  }
  // the one-tap install: the BN tile landing on a home screen
  function sceneInstall(where) {
    var s = '<svg viewBox="0 0 300 132" class="bnig-svg" aria-hidden="true"><rect class="ph" x="1" y="1" width="298" height="130" rx="18"/>';
    for (var i = 0; i < 6; i++) if (i !== 2) s += '<rect class="ap" x="' + (32 + i * 42) + '" y="44" width="30" height="30" rx="8"/>';
    s += '<clipPath id="bnig-cp"><rect x="116" y="44" width="30" height="30" rx="8"/></clipPath><g class="bnig-drop"><image href="/apple-touch-icon.png" x="116" y="44" width="30" height="30" clip-path="url(#bnig-cp)"/></g>';
    s += '<text class="ut" x="104" y="92">BLACKOUT</text>' + (where ? '<text class="mt" x="22" y="118">' + where + "</text>" : "");
    return s + "</svg>";
  }

  // ---------------- flows: max 3 steps, minimal words ----------------
  // Each step: [text (html), scene]. Buttons named exactly as on screen.
  var B = function (t) { return "<b>" + t + "</b>"; };
  function flow(d, canPrompt) {
    var ipad = d.device === "ipad", ios26 = d.safari !== null && d.safari >= 26;
    if (canPrompt) return { key: "prompt", sub: "One tap. No app store.", install: true, desktop: !d.mobile, steps: [["Tap " + B("Install") + " below", sceneInstall("")]] };
    if (d.inApp) return { key: "inapp", sub: "This in-app browser can't add apps.", steps: [
      ["Tap " + B("•••") + " or the menu", sceneBar("top", [{ n: "dotsh", t: 1 }], 0, "")],
      ["Tap " + B(d.os === "ios" ? "Open in Safari" : "Open in browser"), sceneMenu("", [["Copy link", ""], [d.os === "ios" ? "Open in Safari" : "Open in browser", "fwd"]], 1)],
      ["Then use these steps again", sceneInstall("")]] };
    if (d.os === "ios") {
      var addRows = [["Copy", ""], ["Add to Reading List", "book"], ["Add to Home Screen", "addsq"]];
      if (d.browser === "safari" || d.browser === "other") {
        if (ios26 && !ipad) return { key: "ios26-safari", sub: "iPhone · Safari",
          note: "No " + B("Add to Home Screen") + "? Scroll down or tap " + B("View More") + ".<br>Tabs set to Top or Bottom? Tap Share " + svgInline("share") + " first.", steps: [
          ["Tap " + svgInline("pagemenu") + " at the left of the address bar", sceneSafari26()],
          ["Tap " + B("Share"), sceneMenu("", [["Add Bookmark", "book"], ["Share", "share"], ["New Tab", "plus"]], 1)],
          ["Tap " + B("Add to Home Screen") + ", then " + B("Add"), sceneMenu("Share", addRows, 2)]] };
        if (ipad) return { key: "ipad-safari", sub: "iPad · Safari", note: "Don't see Share? Tap ••• first.", steps: [
          ["Tap " + B("Share") + " " + svgInline("share") + " at the top right", sceneBar("top", [{ n: "back", side: "l" }, { n: "share", t: 1 }, { n: "plus" }, { n: "tabs" }])],
          ["Tap " + B("Add to Home Screen"), sceneMenu("Share", addRows, 2, "top")],
          ["Tap " + B("Add"), sceneInstall("")]] };
        return { key: "ios-safari", sub: "iPhone · Safari", steps: [
          ["Tap " + B("Share") + " " + svgInline("share") + " at the bottom", sceneBar("bottom", [{ n: "back", side: "l" }, { n: "share", t: 1 }, { n: "tabs" }])],
          ["Scroll down, tap " + B("Add to Home Screen"), sceneMenu("Share", addRows, 2)],
          ["Tap " + B("Add"), sceneInstall("")]] };
      }
      if (d.ver !== null && d.ver < 16.4) return { key: "ios-old", sub: "Open this page in Safari", copy: true, steps: [
        ["Tap " + B("Copy link") + " below", sceneInstall("")], ["Paste it in " + B("Safari"), sceneBar("bottom", [{ n: "share" }])],
        ["Tap " + B("Share") + " → " + B("Add to Home Screen"), sceneMenu("Share", addRows, 2)]] };
      var nm = { chrome: "Chrome", firefox: "Firefox", edge: "Edge", opera: "Opera" }[d.browser] || "your browser";
      if (d.browser === "edge") return { key: "ios-edge", sub: (ipad ? "iPad" : "iPhone") + " · Edge", note: "Not listed? Open this page in Safari.", steps: [
        ["Tap " + B("•••") + " at the bottom", sceneBar("bottom", [{ n: "back", side: "l" }, { n: "dotsh", t: 1 }, { n: "tabs" }])],
        ["Tap " + B("Share"), sceneMenu("", [["Add to favorites", "book"], ["Share", "share"], ["Settings", ""]], 1)],
        ["Tap " + B("Add to Home Screen") + ", then " + B("Add"), sceneMenu("Share", addRows, 2)]] };
      if (d.browser === "firefox") return { key: "ios-firefox", sub: (ipad ? "iPad" : "iPhone") + " · Firefox", note: "No Share in the address bar? Tap ☰ → Share.", steps: [
        ["Tap " + B("Share") + " " + svgInline("share") + " in the address bar", sceneBar("top", [{ n: "share", t: 1 }])],
        ["Tap " + B("Add to Home Screen"), sceneMenu("Share", addRows, 2, "top")],
        ["Tap " + B("Add"), sceneInstall("")]] };
      return { key: "ios-chrome", sub: (ipad ? "iPad" : "iPhone") + " · " + nm, steps: [
        ["Tap " + B("Share") + " " + svgInline("share") + " in the address bar", sceneBar("top", [{ n: "share", t: 1 }])],
        ["Tap " + B("Add to Home Screen"), sceneMenu("Share", addRows, 2, "top")],
        ["Tap " + B("Add"), sceneInstall("")]] };
    }
    if (d.os === "android") {
      if (d.browser === "samsung") return { key: "samsung", sub: "Samsung Internet", steps: [
        ["Tap the menu " + B("≡") + " at the bottom right", sceneBar("bottom", [{ n: "back", side: "l" }, { n: "home", side: "l" }, { n: "tabs" }, { n: "burger", t: 1 }], 0, "blackout.net…")],
        ["Tap " + B("Add page to"), sceneMenu("", [["Bookmarks", "book"], ["Add page to", "plus"], ["Settings", ""]], 1)],
        ["Tap " + B("Home screen") + ", then " + B("Add"), sceneMenu("Add page to", [["Bookmarks", "book"], ["Quick access", "app"], ["Home screen", "home"]], 2)]] };
      if (d.browser === "firefox") return { key: "android-firefox", sub: "Android · Firefox", steps: [
        ["Tap the menu " + B("⋮"), sceneBar("bottom", [{ n: "home", side: "l" }, { n: "tabs" }, { n: "dotsv", t: 1 }])],
        ["Tap " + B("Add to Home screen"), sceneMenu("", [["Bookmark", "book"], ["Share", "share"], ["Add to Home screen", "home"]], 2)],
        ["Tap " + B("Add"), sceneInstall("")]] };
      if (d.browser === "edge") return { key: "android-edge", sub: "Android · Edge", steps: [
        ["Tap " + B("•••") + " at the bottom", sceneBar("bottom", [{ n: "back", side: "l" }, { n: "dotsh", t: 1 }, { n: "tabs" }])],
        ["Tap " + B("Add to phone"), sceneMenu("", [["Favorites", "book"], ["Share", "share"], ["Add to phone", "home"]], 2)],
        ["Tap " + B("Install"), sceneInstall("")]] };
      return { key: "android-chrome", sub: "Android · " + ({ chrome: "Chrome", opera: "Opera" }[d.browser] || "browser"), steps: [
        ["Tap the menu " + B("⋮") + " at the top right", sceneBar("top", [{ n: "home", side: "l" }, { n: "tabs" }, { n: "dotsv", t: 1 }])],
        ["Tap " + B("Add to home screen") + " (or " + B("Install app") + ")", sceneMenu("", [["Bookmarks", "book"], ["Share", "share"], ["Add to home screen", "home"]], 2, "top")],
        ["Tap " + B("Install"), sceneInstall("")]] };
    }
    if (d.os === "mac" && d.browser === "safari" && d.safari >= 17) return { key: "mac-safari", sub: "Mac · Safari", desktop: true, steps: [
      ["Click " + B("File") + " in the menu bar", sceneBar("top", [{ n: "file", side: "l", t: 1 }], 0, "")],
      ["Click " + B("Add to Dock…"), sceneMenu("File", [["New Window", ""], ["Share", "share"], ["Add to Dock…", "dock"]], 2, "top")],
      ["Click " + B("Add"), sceneInstall("")]] };
    if (d.browser === "chrome" || d.browser === "edge") return { key: "desktop-" + d.browser, sub: d.browser === "edge" ? "Edge" : "Chrome", desktop: true, steps: [
      ["Click the install icon in the address bar", sceneBar("top", [{ n: "back", side: "l" }, { n: "install", t: 1 }, { n: "dotsv" }])],
      ["Click " + B("Install"), sceneInstall("")]] };
    return null;
  }
  var ICN = { pagemenu: "Page Menu button", share: "Share button" };
  function svgInline(n) { return '<svg class="bnig-ic" viewBox="-10 -10 20 20" aria-label="' + (ICN[n] || n + " icon") + '" role="img">' + IC[n] + "</svg>"; }

  // ---------------- share (kept: [data-bn-share] buttons elsewhere use it) ----------------
  function toast(msg) { var t = document.createElement("div"); t.className = "bnig-toast"; t.setAttribute("role", "status"); t.textContent = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2200); }
  function copy(url) {
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) return navigator.clipboard.writeText(url).then(function () { toast("Link copied"); }, function () { prompt("Copy this link", url); });
    prompt("Copy this link", url);
  }
  window.bnShare = function () { var url = location.origin + "/"; if (navigator.share) return navigator.share({ title: "BLACKOUT.NETWORK", url: url }).catch(function () {}); copy(url); };
  document.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("[data-bn-share]"); if (t) { e.preventDefault(); window.bnShare(); } });

  // ---------------- sheet ----------------
  var deferred = null, D = null, el = null, F = null, cur = 0, timer = null, forced = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    if (isInstalled() || isDismissed()) { if (!forced) return; }
    e.preventDefault(); deferred = e;
    if (el && D) { render(); } else if (D && D.ready && !D.mobile && !ss(SKEY)) show();   // desktop Chromium: only shown once install is really possible
  });
  window.addEventListener("appinstalled", function () { markInstalled(); hide(); });
  function pad(on) { try { document.body.style.paddingBottom = on && el ? (el.offsetHeight + 16) + "px" : ""; } catch (e) {} }
  function hide() { if (!el) return; stop(); pad(false); el.classList.remove("bnig-on"); var x = el; setTimeout(function () { x.hidden = true; }, 260); }
  function dismiss() { ls(DKEY, "1"); ck(DKEY, "1"); hide(); }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  function go(i, user) {
    if (!F) return; cur = (i + F.steps.length) % F.steps.length;
    el.querySelector(".bnig-stage").innerHTML = F.steps[cur][1];
    [].forEach.call(el.querySelectorAll(".bnig-step"), function (b, k) { b.classList.toggle("on", k === cur); b.setAttribute("aria-current", k === cur ? "step" : "false"); });
    if (user) stop();
  }
  function render() {
    F = flow(D, !!deferred); if (!F) return hide();
    var h = '<div class="bnig-hd"><img src="/apple-touch-icon.png" alt="" width="44" height="44"><div class="bnig-tt">' +
      '<p class="bnig-t" id="bnig-t">Add BLACKOUT.NETWORK to your ' + (F.desktop ? "computer" : "home screen") + "</p>" +
      '<p class="bnig-sub">' + F.sub + "</p></div>" +
      '<button type="button" class="bnig-x" data-a="dismiss" aria-label="Dismiss">' +
      '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>';
    h += '<div class="bnig-stage" aria-hidden="true"></div>';
    if (F.steps.length > 1) h += '<ol class="bnig-steps">' + F.steps.map(function (s, i) {
      return '<li><button type="button" class="bnig-step" data-i="' + i + '"><span class="n">' + (i + 1) + '</span><span class="tx">' + s[0] + "</span></button></li>"; }).join("") + "</ol>";
    if (F.note) h += '<p class="bnig-note">' + F.note + "</p>";
    h += '<div class="bnig-row">' + (F.install ? '<button type="button" class="bnig-pri" data-a="install">Install</button>' : "") +
      (F.copy ? '<button type="button" class="bnig-pri" data-a="copy">Copy link</button>' : "") +
      '<button type="button" class="bnig-sec" data-a="dismiss">Dismiss</button></div>';
    el.innerHTML = h; el.setAttribute("data-flow", F.key); go(0);
    stop(); if (!reduced && F.steps.length > 1) timer = setInterval(function () { go(cur + 1); }, STEP_MS);
  }
  function show() {
    if (el) return; ss(SKEY, "1");
    el = document.createElement("div"); el.id = "bnig"; el.className = "bnig"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "false"); el.setAttribute("aria-labelledby", "bnig-t");
    el.setAttribute("data-bn-device", D.device + "/" + D.browser + "/" + D.os + (D.safari ? " safari" + D.safari : ""));
    render(); if (!F) { el = null; return; }
    document.body.appendChild(el);
    el.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      if (b.dataset.i) return go(+b.dataset.i, true);
      if (b.dataset.a === "dismiss") return dismiss();
      if (b.dataset.a === "copy") return copy(location.origin + "/");
      if (b.dataset.a === "install" && deferred) { var p = deferred; deferred = null; p.prompt();
        (p.userChoice || Promise.resolve({})).then(function (r) { if (r && r.outcome === "accepted") { markInstalled(); hide(); } else render(); }); }
    });
    el.addEventListener("pointerdown", function () { stop(); });
    el.addEventListener("keydown", function (e) { if (e.key === "Escape") dismiss(); });
    void el.offsetWidth; pad(true); setTimeout(function () { el.classList.add("bnig-on"); }, 30);
    addEventListener("resize", function () { if (el && !el.hidden && el.classList.contains("bnig-on")) pad(true); });
  }
  // ---------------- Home Screen app: ask before the official notification prompt (Matt, t561u/t562u) ----------------
  // Shown only when running from the Home Screen (standalone) and Notification.permission is "default". "Turn on alerts" calls
  // Notification.requestPermission() inside the tap (via BN.turnOnAlerts in alerts.js) and subscribes to our existing Web Push.
  // "Not now" / close = ask again after 7 days. Storage: localStorage "bnna_snooze" (time of the last "Not now").
  // Testing: ?bnna=ask | granted | denied | error forces that state (nothing is requested or stored in forced mode).
  var NKEY = "bnna_snooze", NDAYS = 7, na = null;
  var NI = {
    bell: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.6 1.8H4.4z"/><path d="M10 20.6a2.2 2.2 0 0 0 4 0"/>',
    bolt: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.8 5.2 3.8 8.5s-1.2 6.1-3.8 8.5c-2.6-2.4-3.8-5.2-3.8-8.5S9.4 5.9 12 3.5z"/>',
    gauge: '<path d="M4 16a8 8 0 1 1 16 0"/><path d="M12 16l4-5"/><path d="M4 19.5h16"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m7.8 12.3 2.8 2.8 5.6-5.8"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M5.5 18.5l1.8-1.8M16.7 7.3l1.8-1.8"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>'
  };
  function nico(n, cls) { return '<svg class="' + (cls || "bnna-i") + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + NI[n] + "</svg>"; }
  // lock-screen preview: what a real alert looks like (format of webpush_notifier: "rank/10 · CATEGORY" + headline)
  function sceneNotif() {
    return '<svg viewBox="0 0 300 132" class="bnig-svg bnna-svg" aria-hidden="true"><rect class="ph" x="1" y="1" width="298" height="130" rx="18"/>' +
      '<text class="bnna-clk" x="150" y="34" text-anchor="middle">9:41</text>' +
      '<rect class="bnna-n" x="22" y="48" width="256" height="66" rx="16"/>' +
      '<clipPath id="bnna-cp"><rect x="34" y="60" width="30" height="30" rx="7"/></clipPath><image href="/apple-touch-icon.png" x="34" y="60" width="30" height="30" clip-path="url(#bnna-cp)"/>' +
      '<text class="bnna-a" x="74" y="68">BLACKOUT</text><text class="bnna-t" x="266" y="68" text-anchor="end">now</text>' +
      '<rect class="bnna-rk" x="74" y="76" width="34" height="14" rx="4"/><text class="bnna-rkt" x="91" y="86.5" text-anchor="middle">8/10</text>' +
      '<text class="bnna-c" x="114" y="87">NATURAL DISASTER</text>' +
      '<rect class="bnna-l" x="74" y="96" width="176" height="6" rx="3"/><rect class="bnna-l" x="74" y="106" width="118" height="5" rx="2.5"/></svg>';
  }
  function naSnoozed() { var t = +ls(NKEY) || 0; return t && Date.now() - t < NDAYS * 864e5; }
  function naEnv() { return { api: "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && window.isSecureContext,
    ios: /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && (navigator.maxTouchPoints || 0) > 1),
    android: /Android/i.test(navigator.userAgent) }; }
  function naShell() {
    if (na) return na;
    na = document.createElement("div"); na.id = "bnna"; na.className = "bnig bnna"; na.setAttribute("role", "dialog"); na.setAttribute("aria-modal", "false"); na.setAttribute("aria-labelledby", "bnna-t");
    document.body.appendChild(na);
    na.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return; var a = b.dataset.na;
      if (a === "on") return naOn(b);
      if (a === "later") { if (!forcedNa) ls(NKEY, String(Date.now())); return naHide(); }
      if (a === "done") return naHide();
      if (a === "bell") { naHide(); try { window.BN.enableAlerts({}); } catch (er) {} }
    });
    na.addEventListener("keydown", function (e) { if (e.key === "Escape") { if (!forcedNa && na.dataset.state === "ask") ls(NKEY, String(Date.now())); naHide(); } });
    return na;
  }
  function naHide() { if (!na) return; na.classList.remove("bnig-on"); try { document.body.style.paddingBottom = ""; } catch (e) {} var x = na; setTimeout(function () { x.hidden = true; }, 260); }
  function naHead(icon, title, sub, closeAs) {
    return '<div class="bnig-hd"><span class="bnna-badge' + (icon === "check" ? " ok" : icon === "gear" ? " off" : "") + '">' + nico(icon, "bnna-bi") + '</span><div class="bnig-tt">' +
      '<p class="bnig-t" id="bnna-t">' + title + '</p><p class="bnig-sub">' + sub + '</p></div>' +
      '<button type="button" class="bnig-x" data-na="' + closeAs + '" aria-label="Close"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">' + NI.x + '</svg></button></div>';
  }
  function naRender(state, info) {
    naShell(); na.dataset.state = state; var h = "", E2 = naEnv();
    var dev = /iPad/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && (navigator.maxTouchPoints || 0) > 1) ? "iPad" : (E2.ios || E2.android || /Mobi/i.test(navigator.userAgent)) ? "phone" : "computer";
    if (state === "ask") {
      h = naHead("bell", "Get alerts on this " + dev + "?", "Free · Turn off any time", "later") +
        '<div class="bnig-stage">' + sceneNotif() + '</div>' +
        '<ul class="bnna-list">' +
        '<li>' + nico("bolt") + '<span><b>Major threats, once confirmed</b><small>Rank 7+ out of 10, usually a few a week.</small></span></li>' +
        '<li>' + nico("globe") + '<span><b>What we track</b><small>War, disasters, cyber attacks, outbreaks, space weather.</small></span></li>' +
        '<li>' + nico("gauge") + '<span><b>Never more than 6 an hour</b><small>No ads or promos. Manage them from the bell.</small></span></li></ul>' +
        '<p class="bnig-note bnna-msg" role="status" aria-live="polite">Your ' + (dev === "computer" ? "browser" : dev) + ' asks next. Tap <b>Allow</b>.</p>' +
        '<div class="bnig-row"><button type="button" class="bnig-pri bnna-pri" data-na="on">' + nico("bell", "bnna-bti") + '<span>Turn on alerts</span></button>' +
        '<button type="button" class="bnig-sec" data-na="later">Not now</button></div>';
    } else if (state === "granted") {
      h = naHead("check", "Alerts are on", info && info.live === false ? "You’re signed up. Alerts start soon." : "You’ll get major alerts (rank 7+).", "done") +
        '<ul class="bnna-list"><li>' + nico("bell") + '<span><b>Change them any time</b><small>Tap the bell at the top of any page to pick more alerts, send a test, or turn them off.</small></span></li></ul>' +
        '<div class="bnig-row"><button type="button" class="bnig-pri bnna-pri" data-na="done">Done</button><button type="button" class="bnig-sec" data-na="bell">Settings</button></div>';
    } else if (state === "denied") {
      var how = E2.ios ? "Open <b>Settings</b> › <b>Notifications</b> › <b>BLACKOUT</b> and turn on <b>Allow Notifications</b>."
        : E2.android ? "Open <b>Settings</b> › <b>Apps</b> › <b>BLACKOUT</b> › <b>Notifications</b> and allow them."
        : "Open this app’s site settings and set <b>Notifications</b> to <b>Allow</b>.";
      h = naHead("gear", "Notifications are off", "You can turn them on later in Settings.", "done") +
        '<ol class="bnna-steps"><li><span class="n">1</span><span>' + how + '</span></li><li><span class="n">2</span><span>Come back here and tap the bell to finish.</span></li></ol>' +
        '<div class="bnig-row"><button type="button" class="bnig-pri bnna-pri" data-na="done">Got it</button></div>';
    } else if (state === "error") {
      h = naHead("bell", "Couldn’t turn on alerts", "Notifications are allowed. One more try should do it.", "done") +
        '<p class="bnig-note bnna-msg bnna-err" role="status">' + ((info && info.error) || "Something went wrong. Please try again.").replace(/[<>&]/g, "") + '</p>' +
        '<div class="bnig-row"><button type="button" class="bnig-pri bnna-pri" data-na="on">Try again</button><button type="button" class="bnig-sec" data-na="done">Close</button></div>';
    }
    na.innerHTML = h; na.hidden = false; void na.offsetWidth;
    setTimeout(function () { na.classList.add("bnig-on"); try { document.body.style.paddingBottom = (na.offsetHeight + 16) + "px"; } catch (e) {} }, 30);
  }
  function naOn(btn) {
    if (forcedNa) return naRender(forcedNa === "ask" ? "granted" : forcedNa, { live: true });
    btn.disabled = true; var m = na.querySelector(".bnna-msg"); if (m) m.textContent = "Waiting for your answer…";
    var run = window.BN && window.BN.turnOnAlerts ? window.BN.turnOnAlerts({ level: "major" })     // requestPermission runs inside this tap
      : new Promise(function (res) { var p = Notification.requestPermission(res); if (p && p.then) p.then(res); }).then(function (perm) { return { perm: perm, ok: false, error: perm === "granted" ? "Tap the bell to finish turning on alerts." : "" }; });
    run.then(function (r) {
      if (r.perm === "granted" && r.ok) return naRender("granted", r);
      if (r.perm === "granted") return naRender("error", r);
      if (r.perm === "denied") return naRender("denied");
      ls(NKEY, String(Date.now())); naHide();                                    // closed the system prompt without answering: ask again in 7 days
    });
  }
  var forcedNa = null;
  function maybeAsk(q) {
    forcedNa = q && /^(ask|granted|denied|error)$/.test(q) ? q : null;
    if (forcedNa) return setTimeout(function () { naRender(forcedNa, forcedNa === "error" ? { error: "Alerts are not available right now. Please try again later." } : { live: true }); }, 200);
    var E2 = naEnv();
    if (!standalone() || !E2.api || Notification.permission !== "default" || naSnoozed()) return;
    try { if ((JSON.parse(ls("bn_alerts") || "{}") || {}).on) return; } catch (e) {}
    setTimeout(function () { if (Notification.permission === "default" && !document.querySelector(".bnal.bnal-open")) naRender("ask"); }, DELAY + 600);
  }
  window.BN = window.BN || {};
  window.BN.showInstallGuide = function () {                                    // used by the Alerts panel's "Show me how" button
    D = D || detect(); if (el) { el.hidden = false; render(); void el.offsetWidth; pad(true); setTimeout(function () { el.classList.add("bnig-on"); }, 30); } else show();
  };
  function start() {
    var q = (location.search.match(/[?&]bnig=([\w-]+)/) || [])[1] || null; forced = q;
    D = detect(); window.__bnigDetect = D;
    maybeAsk((location.search.match(/[?&]bnna=([\w-]+)/) || [])[1] || null);
    if (forcedNa) return;                                                     // testing a soft-ask state: no install sheet
    if (!q) {
      if (standalone() || isInstalled() || isDismissed() || ss(SKEY)) return;
      if (!D.mobile && !(D.os === "mac" && D.browser === "safari")) { D.ready = true; return; }   // desktop Chromium waits for beforeinstallprompt
    }
    var go2 = function () { if (!q && (standalone() || isInstalled())) return; show(); };
    if (!q && navigator.getInstalledRelatedApps) {                            // Chromium: is the web app already installed from this origin?
      navigator.getInstalledRelatedApps().then(function (apps) { if (apps && apps.length) { markInstalled(); return; } setTimeout(go2, DELAY); }, function () { setTimeout(go2, DELAY); });
    } else setTimeout(go2, q ? 200 : DELAY);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
