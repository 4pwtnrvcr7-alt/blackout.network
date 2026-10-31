/* blackout.network: mobile "Add to Home Screen" guide + Share button. Vanilla JS, no dependencies.
   Privacy: detection runs entirely in this browser (userAgent / userAgentData); nothing is sent anywhere, no analytics, no cookies.
   Storage: localStorage "bnig_dismissed_until" (30-day dismissal) and sessionStorage "bnig_shown" (once per session). */
(function () {
  "use strict";
  if (window.__bnig) return; window.__bnig = 1;
  try { if (window.top !== window.self) return; } catch (e) { return; }      // never inside iframes (newsletter/sources cards)
  var KEY = "bnig_dismissed_until", SKEY = "bnig_shown", DAYS = 30, DELAY = 2500;
  var ls = function (k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  var ss = function (k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } };

  // ---------------- detection (local only) ----------------
  function detect() {
    var ua = navigator.userAgent || "", uad = navigator.userAgentData || null, tp = navigator.maxTouchPoints || 0;
    var d = { device: "desktop", os: "other", osVersion: null, browser: "other", inApp: false, mobile: false };
    var iPadDesktop = /Macintosh/.test(ua) && tp > 1;                         // iPadOS 13+ "Request Desktop Website" (default) looks like a Mac
    if (/iPhone|iPod/.test(ua)) d.device = "iphone";
    else if (/iPad/.test(ua) || iPadDesktop) d.device = "ipad";
    else if (/Android/i.test(ua) || (uad && /Android/i.test(uad.platform || ""))) d.device = /Mobile/i.test(ua) || (uad && uad.mobile) ? "android-phone" : "android-tablet";
    if (d.device === "iphone" || d.device === "ipad") {
      d.os = "ios";
      var m = ua.match(/OS (\d+)[_.](\d+)/);                                  // "CPU iPhone OS 17_4 like Mac OS X"
      if (m && !iPadDesktop) d.osVersion = parseFloat(m[1] + "." + m[2]);
      else { var v = ua.match(/Version\/(\d+)(?:\.(\d+))?/); if (v) d.osVersion = parseFloat(v[1] + "." + (v[2] || 0)); }   // Safari version tracks iOS
    } else if (d.device.indexOf("android") === 0) {
      d.os = "android"; var a = ua.match(/Android (\d+(?:\.\d+)?)/); if (a) d.osVersion = parseFloat(a[1]);
    }
    d.mobile = d.os === "ios" || d.os === "android" || !!(uad && uad.mobile);
    if (/FBAN|FBAV|FB_IAB|Instagram|Line\/|Twitter|LinkedInApp|Snapchat|GSA\//.test(ua)) d.inApp = true;
    if (/SamsungBrowser/i.test(ua)) d.browser = "samsung";
    else if (/EdgiOS|EdgA|Edg\//.test(ua)) d.browser = "edge";
    else if (/OPR\/|OPT\/|OPiOS|Opera|OPX\//.test(ua)) d.browser = "opera";
    else if (/FxiOS|Firefox\//.test(ua)) d.browser = "firefox";
    else if (/CriOS|Chrome\//.test(ua)) d.browser = "chrome";
    else if (/Safari\//.test(ua) && d.os === "ios") d.browser = "safari";
    else if (/Safari\//.test(ua)) d.browser = "safari";
    if (uad && uad.brands && d.browser === "other") {
      var b = uad.brands.map(function (x) { return x.brand; }).join(" ");
      if (/Edge/.test(b)) d.browser = "edge"; else if (/Opera/.test(b)) d.browser = "opera"; else if (/Samsung/.test(b)) d.browser = "samsung"; else if (/Chrom/.test(b)) d.browser = "chrome";
    }
    return d;
  }
  function refineAndroidVersion(d, cb) {                                       // Chrome's reduced UA says "Android 10; K"; ask locally for the real one
    var uad = navigator.userAgentData;
    if (d.os !== "android" || !uad || !uad.getHighEntropyValues) return cb(d);
    uad.getHighEntropyValues(["platformVersion"]).then(function (h) { var v = parseFloat(h.platformVersion); if (v) d.osVersion = v; cb(d); }, function () { cb(d); });
  }
  function standalone() {
    try { if (window.matchMedia && (matchMedia("(display-mode: standalone)").matches || matchMedia("(display-mode: fullscreen)").matches || matchMedia("(display-mode: minimal-ui)").matches)) return true; } catch (e) {}
    return navigator.standalone === true;
  }

  // ---------------- steps per device/browser ----------------
  var SHARE = '<svg class="bnig-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M6 11v9h12v-9"/></svg>';
  var DOTS_V = "<b aria-label='menu (three dots)'>⋮</b>", DOTS_H = "<b aria-label='more (three dots)'>⋯</b>", PLUS = "<b>⊕</b>";
  function steps(d, canPrompt) {
    var ipad = d.device === "ipad", where = ipad ? "at the top right" : "in the toolbar";
    if (d.inApp) return { sub: "You're in an in-app browser.", steps: ["Tap " + DOTS_H + " or the menu in this app", "Choose <b>Open in " + (d.os === "ios" ? "Safari" : "browser") + "</b>", "Then add it to your Home Screen from there"] };
    if (d.os === "ios") {
      var modern = d.osVersion === null || d.osVersion >= 16.4;
      if (d.browser === "safari") return { sub: (ipad ? "iPad" : "iPhone") + " · Safari", steps: [
        "Tap <b>Share</b> " + SHARE + " " + where + (ipad ? "" : " (if you don't see it, tap " + DOTS_H + " first)"),
        "Scroll down and tap <b>Add to Home Screen</b>", "Tap <b>Add</b>"] };
      if (!modern) return { sub: (ipad ? "iPad" : "iPhone") + " · iOS " + d.osVersion, steps: [
        "On this iOS version only Safari can add sites to the Home Screen", "Tap <b>Copy link</b>, then open it in <b>Safari</b>",
        "Then tap <b>Share</b> " + SHARE + " → <b>Add to Home Screen</b>"], copy: true };
      var name = { chrome: "Chrome", firefox: "Firefox", edge: "Edge", opera: "Opera" }[d.browser] || "your browser";
      var first = d.browser === "chrome" ? "Tap <b>Share</b> " + SHARE + " in the address bar (top right)"
        : d.browser === "firefox" ? "Tap the menu <b>☰</b>, then <b>Share</b> " + SHARE
        : d.browser === "edge" ? "Tap " + DOTS_H + " (menu), then <b>Share</b> " + SHARE
        : "Tap your browser's <b>Share</b> " + SHARE + " button";
      return { sub: (ipad ? "iPad" : "iPhone") + " · " + name, steps: [first, "Tap <b>Add to Home Screen</b> (scroll down if needed)", "Tap <b>Add</b>"],
        note: "Not listed? Open this page in Safari and use Share → Add to Home Screen." };
    }
    if (d.os === "android") {
      if (canPrompt && (d.browser === "chrome" || d.browser === "edge" || d.browser === "samsung" || d.browser === "opera" || d.browser === "other"))
        return { sub: "Android · " + ({ chrome: "Chrome", edge: "Edge", samsung: "Samsung Internet", opera: "Opera" }[d.browser] || "browser"), steps: ["Tap <b>Install</b> below, then confirm"], install: true };
      if (d.browser === "samsung") return { sub: "Android · Samsung Internet", steps: ["Tap the menu <b>≡</b> (bottom right)", "Tap <b>Add page to</b>", "Choose <b>Home screen</b>"] };
      if (d.browser === "firefox") return { sub: "Android · Firefox", steps: ["Tap the menu " + DOTS_V, "Tap <b>Install</b> (or <b>Add to Home screen</b>)", "Tap <b>Add</b>"] };
      if (d.browser === "edge") return { sub: "Android · Edge", steps: ["Tap the menu " + DOTS_H + " (bottom)", "Tap <b>Add to phone</b> / <b>Install app</b>", "Tap <b>Install</b>"] };
      if (d.browser === "opera") return { sub: "Android · Opera", steps: ["Tap the menu " + DOTS_V, "Tap <b>Add to</b> → <b>Home screen</b>", "Tap <b>Add</b>"] };
      if (d.browser === "chrome") return { sub: "Android · Chrome", steps: ["Tap the menu " + DOTS_V + " (top right)", "Tap <b>Install app</b> or <b>Add to Home screen</b>", "Tap <b>Install</b> / <b>Add</b>"] };
    }
    return { sub: "", steps: ["Open your browser's menu or Share button", "Choose <b>Add to Home Screen</b> or <b>Install</b>", "Confirm"] };
  }

  // ---------------- share ----------------
  function toast(msg) {
    var t = document.createElement("div"); t.className = "bnig-toast"; t.setAttribute("role", "status"); t.setAttribute("aria-live", "polite"); t.textContent = msg;
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2200);
  }
  function showUrl(host, url) {
    var box = (host || document.body).querySelector(".bnig-url");
    if (!box) { box = document.createElement("input"); box.className = "bnig-url"; box.readOnly = true; box.setAttribute("aria-label", "Link to this page"); (host || document.body).appendChild(box); }
    box.value = url; box.focus(); box.select(); try { box.setSelectionRange(0, url.length); } catch (e) {}
  }
  function share(host) {
    var url = location.origin + "/", title = "blackout.network: Know first. Be ready.";
    if (navigator.share) return navigator.share({ title: title, url: url }).catch(function (e) { if (e && e.name !== "AbortError") copy(url, host); });
    copy(url, host);
  }
  function copy(url, host) {
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext)
      return navigator.clipboard.writeText(url).then(function () { toast("Link copied"); }, function () { showUrl(host, url); toast("Select and copy the link"); });
    showUrl(host, url); toast("Select and copy the link");
  }
  window.bnShare = function () { share(document.getElementById("bnig")); };
  document.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("[data-bn-share]"); if (t) { e.preventDefault(); window.bnShare(); } });

  // ---------------- banner ----------------
  var deferred = null, D = null, el = null;
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); deferred = e; if (el && D) render(); });
  window.addEventListener("appinstalled", function () { ls(KEY, String(Date.now() + 365 * 864e5)); hide(); });
  function pad(on) { try { document.body.style.paddingBottom = on && el ? (el.offsetHeight + 24) + "px" : ""; } catch (e) {} }   // never leave page content stuck under the banner
  function hide() { if (!el) return; pad(false); el.classList.remove("bnig-on"); var x = el; setTimeout(function () { x.hidden = true; }, 260); }
  function dismiss() { ls(KEY, String(Date.now() + DAYS * 864e5)); hide(); }
  function render() {
    var s = steps(D, !!deferred), h = "";
    h += '<button type="button" class="bnig-x" aria-label="Dismiss home screen tip">×</button>';
    h += '<div class="bnig-hd"><img src="/icons/icon-192.png" alt="" width="32" height="32"><div><p class="bnig-t" id="bnig-t">Add Blackout to your Home Screen</p>' +
         (s.sub ? '<p class="bnig-sub">' + s.sub + "</p>" : "") + "</div></div>";
    h += "<ol>" + s.steps.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ol>";
    if (s.note) h += '<p class="bnig-sub" style="margin:0 0 8px">' + s.note + "</p>";
    h += '<div class="bnig-row">' + (s.install ? '<button type="button" class="bnig-pri" data-a="install">Install</button>' : "") +
         (s.copy ? '<button type="button" class="bnig-pri" data-a="copy">Copy link</button>' : "") +
         '<button type="button" data-a="share" aria-label="Share blackout.network">Share</button><button type="button" data-a="later">Not now</button></div>';
    el.innerHTML = h;
  }
  function build() {
    el = document.createElement("div"); el.id = "bnig"; el.className = "bnig"; el.setAttribute("role", "region"); el.setAttribute("aria-labelledby", "bnig-t");
    el.setAttribute("data-bn-device", D.device + "/" + D.browser + "/" + D.os + (D.osVersion ? " " + D.osVersion : ""));
    render(); document.body.appendChild(el);
    el.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      if (b.classList.contains("bnig-x") || b.dataset.a === "later") return dismiss();
      if (b.dataset.a === "share") return share(el);
      if (b.dataset.a === "copy") return copy(location.origin + "/", el);
      if (b.dataset.a === "install" && deferred) { var p = deferred; deferred = null; p.prompt(); (p.userChoice || Promise.resolve({})).then(function (r) { if (r && r.outcome === "accepted") dismiss(); else render(); }); }
    });
    el.addEventListener("keydown", function (e) { if (e.key === "Escape") dismiss(); });
    void el.offsetWidth; pad(true); setTimeout(function () { el.classList.add("bnig-on"); }, 30);
    window.addEventListener("resize", function () { if (el && !el.hidden && el.classList.contains("bnig-on")) pad(true); });
  }
  function start() {
    var force = /[?&]bnig=1\b/.test(location.search);                         // ?bnig=1 shows it for testing regardless of dismissal/session
    D = detect(); window.__bnigDetect = D;
    if (!force) {
      if (standalone() || !D.mobile) return;
      if (+(ls(KEY) || 0) > Date.now() || ss(SKEY)) return;
    }
    refineAndroidVersion(D, function () { setTimeout(function () { if (!force && standalone()) return; ss(SKEY, "1"); build(); }, force ? 300 : DELAY); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
