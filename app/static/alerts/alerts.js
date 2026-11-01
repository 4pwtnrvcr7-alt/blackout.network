/* BLACKOUT.NETWORK Alerts (t341): bell button + Alerts panel for standards-based Web Push.
   Public hooks (for the add-to-home-screen pop-up and any page):
     window.BN.enableAlerts(opts)  open the Alerts panel (opts.from = "install" adds a "You're installed" line)
     window.BN.alertsStatus()      Promise -> {supported, ios, standalone, permission, on, level, cats}
     any element with [data-bn-alerts] opens the panel on tap.
   Permission is requested ONLY inside a tap on "Turn on alerts", never on page load. */
(function () {
  if (window.__bnal) return; window.__bnal = 1;
  try { if (window.top !== window.self) return; } catch (e) { return; }
  var BN = window.BN = window.BN || {};
  var KEY = "bn_alerts";
  function ls(k, v) { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } }
  function st() { try { return JSON.parse(ls(KEY) || "{}") || {}; } catch (e) { return {}; } }
  function save(o) { ls(KEY, o ? JSON.stringify(o) : null); paintBell(); }
  try { if (/[?&]test=1(&|$)/.test(location.search)) sessionStorage.setItem("bn_alerts_test", "1"); } catch (e) {}
  function isTest() { try { return sessionStorage.getItem("bn_alerts_test") === "1" || !!st().test; } catch (e) { return !!st().test; } }

  function env() {
    var ua = navigator.userAgent || "", tp = navigator.maxTouchPoints || 0;
    var ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && tp > 1);
    var sa = false; try { sa = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true; } catch (e) {}
    var m = ua.match(/OS (\d+)[_.](\d+)/), v = ua.match(/Version\/(\d+)(?:\.(\d+))?/);
    var ver = m ? parseFloat(m[1] + "." + m[2]) : v ? parseFloat(v[1] + "." + (v[2] || 0)) : null;
    var inApp = /FBAN|FBAV|FB_IAB|Instagram|Line\/|Twitter|LinkedInApp|Snapchat|TikTok|musical_ly|GSA\//.test(ua);
    var api = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && window.isSecureContext;
    return { ios: ios, standalone: sa, ver: ver, inApp: inApp, api: api, android: /Android/i.test(ua),
             mobile: ios || /Android|Mobi/i.test(ua) };
  }
  var E = env();

  var cfgP = null;
  function getCfg() {
    if (!cfgP) cfgP = fetch("/api/alerts/config", { cache: "no-store" }).then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .catch(function () { cfgP = null; return { vapid_public_key: "", live: false, max_per_hour: 6, categories: [] }; });
    return cfgP;
  }
  var regP = null;
  function getReg() {
    if (!E.api) return Promise.reject(new Error("unsupported"));
    if (!regP) regP = navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function () { return navigator.serviceWorker.ready; })
      .catch(function (e) { regP = null; throw e; });
    return regP;
  }
  function u8(b64) {
    var p = "=".repeat((4 - b64.length % 4) % 4), s = atob((b64 + p).replace(/-/g, "+").replace(/_/g, "/")), a = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);
    return a;
  }
  function post(path, body) {
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw new Error(j.error || ("HTTP " + r.status)); return j; }); });
  }

  BN.alertsStatus = function () {
    var base = { supported: E.api, ios: E.ios, standalone: E.standalone, permission: E.api ? Notification.permission : "unsupported" };
    var s = st();
    if (!E.api || Notification.permission !== "granted" || !s.on) return Promise.resolve(Object.assign(base, { on: false }));
    return getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { save(null); return Object.assign(base, { on: false }); }
      return Object.assign(base, { on: true, level: s.level, cats: s.cats || [] });
    }).catch(function () { return Object.assign(base, { on: false }); });
  };

  // ---------------- icons ----------------
  var BELL = '<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.6 1.8H4.4z"/><path fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" d="M10 20.6a2.2 2.2 0 0 0 4 0"/></svg>';
  var X = '<svg aria-hidden="true" focusable="false" width="20" height="20" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var SHARE = '<svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="-10 -10 20 20"><path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" d="M0 -9v11M-4 -5l4-4 4 4M-6 -2h-1.5v10h15v-10h-1.5"/></svg>';
  function meter(r) {
    if (window.bnMeter) return window.bnMeter(r, "s");
    return '<span class="bn-meter bn-meter-s bn-r' + r + '" role="img" aria-label="Rank ' + r + ' of 10"><span class="bn-segs" aria-hidden="true">' + new Array(11).join("<i></i>") + '</span><b class="bn-num" aria-hidden="true">' + r + '<small>/10</small></b></span>';
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // ---------------- bell buttons (top bar + menu row) ----------------
  function addButtons() {
    var acts = document.querySelector(".bn-top .bn-acts");
    if (acts && !acts.querySelector(".bnal-bell")) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "bn-ib bnal-bell"; b.setAttribute("data-bn-alerts", ""); b.setAttribute("aria-haspopup", "dialog");
      b.setAttribute("aria-label", "Alerts"); b.title = "Alerts";
      b.innerHTML = BELL + '<span class="bnal-bl">Alerts</span><i class="bnal-dot" aria-hidden="true"></i>';
      var before = acts.querySelector(".bn-searchbtn") || acts.querySelector(".bn-burger");
      acts.insertBefore(b, before); document.documentElement.classList.add("bnal-has");
    }
    var tools = document.querySelector(".bn-drawer .bn-dtools");
    if (tools && !tools.querySelector(".bnal-row")) {
      var r = document.createElement("button");
      r.type = "button"; r.className = "bn-mrow bnal-row"; r.setAttribute("data-bn-alerts", "");
      r.innerHTML = BELL + '<span>Alerts <small class="bnal-rs">Off</small></span>';
      tools.insertBefore(r, tools.firstChild);
    }
    paintBell();
  }
  function paintBell() {
    var on = !!st().on, lvl = st().level === "all" ? "All ranked alerts" : "Major alerts only";
    [].forEach.call(document.querySelectorAll(".bnal-bell"), function (b) {
      b.classList.toggle("bnal-on", on); b.setAttribute("aria-label", on ? "Alerts are on (" + lvl + ")" : "Turn on alerts");
    });
    [].forEach.call(document.querySelectorAll(".bnal-rs"), function (s) { s.textContent = on ? "On · " + lvl : "Off"; });
  }

  // ---------------- panel ----------------
  var el = null, lastFocus = null, opened = 0;
  function closePanel() {
    if (!el) return; el.classList.remove("bnal-open"); document.documentElement.classList.remove("bnal-lock");
    var x = el; setTimeout(function () { x.hidden = true; }, 200);
    if (lastFocus && lastFocus.focus) try { lastFocus.focus(); } catch (e) {}
  }
  function shell() {
    if (el) return el;
    el = document.createElement("div"); el.className = "bnal"; el.hidden = true;
    el.innerHTML = '<div class="bnal-scrim" data-x></div><section class="bnal-card" role="dialog" aria-modal="true" aria-labelledby="bnal_h" tabindex="-1">'
      + '<div class="bnal-head"><span class="bnal-hi">' + BELL + '</span><h2 id="bnal_h">Get alerts</h2><button type="button" class="bnal-x" data-x aria-label="Close">' + X + '</button></div>'
      + '<div class="bnal-body"></div></section>';
    document.body.appendChild(el);
    el.addEventListener("click", function (e) { if (e.target.closest("[data-x]")) { e.preventDefault(); closePanel(); } });
    el.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); closePanel(); return; }
      if (e.key !== "Tab") return;
      var f = [].filter.call(el.querySelectorAll("button,a[href],input,summary"), function (n) { return n.offsetParent !== null && !n.disabled; });
      if (!f.length) return; var a = f[0], z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    });
    return el;
  }
  function body(h) { shell().querySelector(".bnal-body").innerHTML = h; }
  function say(msg, kind) { var n = el && el.querySelector(".bnal-msg"); if (n) { n.className = "bnal-msg" + (kind ? " bnal-" + kind : ""); n.textContent = msg; } }

  function choices(c, s) {
    var lvl = s.level || "major", cats = s.cats || [];
    var allOn = !cats.length;
    var opt = function (k, title, r, sub) {
      return '<label class="bnal-opt"><input type="radio" name="bnal_lvl" value="' + k + '"' + (lvl === k ? " checked" : "") + '>'
        + '<span class="bnal-ot"><b>' + title + '</b><span class="bnal-om">' + meter(r) + '<span>' + sub + '</span></span></span></label>';
    };
    var cl = (c.categories || []).map(function (x) {
      return '<label class="bnal-cat"><input type="checkbox" value="' + esc(x.key) + '"' + (allOn || cats.indexOf(x.key) >= 0 ? " checked" : "") + '><span>' + esc(x.label) + '</span></label>';
    }).join("");
    return '<fieldset class="bnal-lv"><legend class="bnal-sr">How many alerts</legend>'
      + opt("major", "Major alerts only", 7, "Rank 7+ · usually a few a week")
      + opt("all", "All ranked alerts", 5, "Rank 5+ · usually several a day") + '</fieldset>'
      + (cl ? '<details class="bnal-more"><summary>More options</summary><p class="bnal-note">Alert me about:</p><div class="bnal-cats">' + cl + '</div></details>' : "");
  }
  function readChoices() {
    var r = el.querySelector('input[name="bnal_lvl"]:checked');
    var boxes = el.querySelectorAll(".bnal-cats input"), cats = [];
    [].forEach.call(boxes, function (b) { if (b.checked) cats.push(b.value); });
    if (cats.length === boxes.length) cats = [];
    return { level: r ? r.value : "major", cats: cats, none: boxes.length > 0 && !cats.length && [].every.call(boxes, function (b) { return !b.checked; }) };
  }
  function soon(c) {
    return c.live ? "" : '<p class="bnal-soon"><b>Launching soon.</b> Sign up now and alerts start automatically when we switch them on. Nothing else to do.</p>';
  }

  function render(opts) {
    opts = opts || {};
    var c = { categories: [], live: false };
    var s = st();
    if (E.inApp) return body('<p class="bnal-lead">This in-app browser can’t show alerts.</p><p class="bnal-note">Open <b>blackout.network</b> in Safari or Chrome, then tap the bell.</p>');
    if (E.ios && !E.standalone) {
      var old = E.ver && E.ver < 16.4;
      return body('<p class="bnal-lead">On iPhone and iPad, alerts work from the Home Screen app.</p>'
        + (old ? '<p class="bnal-note bnal-warn">This needs iOS 16.4 or newer. Update iOS in Settings first.</p>' : "")
        + '<ol class="bnal-steps"><li><span class="bnal-n">1</span><span>Tap <b>Share</b> <span class="bnal-ki">' + SHARE + '</span> in Safari (on newer iPhones it’s under <b>•••</b>)</span></li>'
        + '<li><span class="bnal-n">2</span><span>Tap <b>Add to Home Screen</b></span></li>'
        + '<li><span class="bnal-n">3</span><span>Open <b>BLACKOUT</b> from your Home Screen and tap the bell ' + '<span class="bnal-ki">' + BELL + '</span></span></li></ol>'
        + (typeof BN.showInstallGuide === "function" ? '<div class="bnal-acts"><button type="button" class="bnal-go" data-bnal="install">Show me how</button></div>' : ""));
    }
    if (!E.api) return body('<p class="bnal-lead">This browser can’t show alerts.</p><p class="bnal-note">Use a current version of Chrome, Edge, Firefox, Samsung Internet or Safari.</p>');
    if (Notification.permission === "denied") {
      return body('<p class="bnal-lead">Notifications are blocked for this site.</p><p class="bnal-note">'
        + (E.android ? "Open your phone’s <b>Settings › Apps › " + (E.standalone ? "BLACKOUT" : "your browser") + " › Notifications</b>, allow them for blackout.network, then come back."
           : E.ios ? "Open <b>Settings › Notifications › BLACKOUT</b> and turn on <b>Allow Notifications</b>, then come back."
           : "Click the icon to the left of the address bar, set <b>Notifications</b> to <b>Allow</b>, then reload this page.")
        + '</p>');
    }
    getCfg().then(function (cf) {
      c = cf;
      var on = !!s.on && Notification.permission === "granted";
      var intro = opts.from === "install" ? '<p class="bnal-ok">You’re all set on your Home Screen. One more step:</p>' : "";
      if (on) {
        body('<p class="bnal-lead"><span class="bnal-pill">● On</span> You’ll get ' + (s.level === "all" ? "all ranked alerts (rank 5+)" : "major alerts (rank 7+)") + '.</p>'
          + soon(c) + choices(c, s)
          + '<div class="bnal-acts"><button type="button" class="bnal-go" data-bnal="save">Save changes</button>'
          + '<button type="button" class="bnal-2" data-bnal="sample">Show a sample</button>'
          + '<button type="button" class="bnal-off" data-bnal="off">Turn off alerts</button></div><p class="bnal-msg" role="status" aria-live="polite"></p>');
      } else {
        body(intro + '<p class="bnal-lead">Major threats, the moment they’re confirmed. Free. Turn off any time.</p>' + soon(c) + choices(c, s)
          + '<div class="bnal-acts"><button type="button" class="bnal-go bnal-big" data-bnal="on">' + BELL + '<span>Turn on alerts</span></button></div>'
          + '<p class="bnal-note">Your browser will ask to allow notifications. Tap <b>Allow</b>. Never more than ' + (c.max_per_hour || 6) + ' an hour.</p>'
          + '<p class="bnal-msg" role="status" aria-live="polite"></p>');
      }
    });
  }

  function turnOn(btn) {
    var ch = readChoices();
    if (ch.none) { say("Pick at least one category under More options.", "err"); return; }
    btn.disabled = true; say("Asking your browser…");
    // requestPermission runs first, directly inside the tap (Safari requires a user gesture)
    var permP = Notification.permission === "granted" ? Promise.resolve("granted") : new Promise(function (res) {
      var p = Notification.requestPermission(res); if (p && p.then) p.then(res);
    });
    permP.then(function (perm) {
      if (perm !== "granted") { btn.disabled = false; if (perm === "denied") render(); else say("Alerts stay off. Tap the button again whenever you’re ready."); throw null; }
      say("Turning on alerts…");
      return Promise.all([getReg(), getCfg()]);
    }).then(function (rc) {
      var reg = rc[0], cf = rc[1];
      if (!cf.vapid_public_key) throw new Error("Alerts are not available right now. Please try again later.");
      return reg.pushManager.getSubscription().then(function (sub) {
        return sub || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(cf.vapid_public_key) });
      });
    }).then(function (sub) {
      return post("/api/alerts/subscribe", { sub: sub.toJSON(), level: ch.level, cats: ch.cats, test: isTest() }).then(function (j) {
        save({ on: true, level: j.level, cats: j.cats, endpoint: sub.endpoint, test: !!j.test, since: new Date().toISOString() });
        render(); setTimeout(function () { say(j.live ? "Alerts are on." : "You’re signed up. Alerts start soon.", "ok"); }, 50);
      });
    }).catch(function (e) { if (e === null) return; btn.disabled = false; say((e && e.message) || "Something went wrong. Please try again.", "err"); });
  }
  function saveChanges(btn) {
    var ch = readChoices();
    if (ch.none) { say("Pick at least one category under More options.", "err"); return; }
    btn.disabled = true;
    getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { save(null); render(); throw null; }
      return post("/api/alerts/subscribe", { sub: sub.toJSON(), level: ch.level, cats: ch.cats, test: isTest() });
    }).then(function (j) { var s = st(); s.level = j.level; s.cats = j.cats; save(s); btn.disabled = false; say("Saved.", "ok"); })
      .catch(function (e) { btn.disabled = false; if (e !== null) say((e && e.message) || "Couldn’t save. Please try again.", "err"); });
  }
  function turnOff(btn) {
    btn.disabled = true;
    getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) return;
      var ep = sub.endpoint;
      return post("/api/alerts/unsubscribe", { endpoint: ep }).catch(function () {}).then(function () { return sub.unsubscribe(); });
    }).catch(function () {}).then(function () { save(null); render(); setTimeout(function () { say("Alerts are off.", "ok"); }, 50); });
  }
  function sample() {
    getReg().then(function (r) {
      return r.showNotification("7/10 · SAMPLE", { body: "This is what an alert looks like. Tap it to open the story.", icon: "/icons/icon-192.png",
        badge: "/alerts/badge.png", tag: "bn-sample", data: { url: location.origin + "/#wire" } });
    }).then(function () { say("Sample sent. Check your notifications.", "ok"); }, function () { say("Couldn’t show a sample.", "err"); });
  }

  BN.enableAlerts = function (opts) {
    opts = opts || {};
    shell(); lastFocus = document.activeElement; render(opts);
    if (E.api && !(E.ios && !E.standalone)) { getReg().catch(function () {}); getCfg(); }   // warm up so the tap goes straight to the permission prompt
    el.hidden = false; document.documentElement.classList.add("bnal-lock");
    requestAnimationFrame(function () { el.classList.add("bnal-open"); var c = el.querySelector(".bnal-card"); if (c) c.focus(); });
    opened++;
    return BN.alertsStatus();
  };
  BN.closeAlerts = closePanel;

  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-bn-alerts],[data-bnal]");
    if (!t) return;
    if (t.hasAttribute("data-bn-alerts")) {
      e.preventDefault();
      try { if (t.closest(".bn-drawer")) { var cx = document.querySelector(".bn-drawer .bn-close"); if (cx) cx.click(); } } catch (er) {}
      BN.enableAlerts({ from: t.getAttribute("data-bn-alerts") || "" }); return;
    }
    var a = t.getAttribute("data-bnal");
    if (a === "on") turnOn(t); else if (a === "save") saveChanges(t); else if (a === "off") turnOff(t); else if (a === "sample") sample();
    else if (a === "install") { closePanel(); try { BN.showInstallGuide(); } catch (er) {} }
  });
  if (navigator.serviceWorker) navigator.serviceWorker.addEventListener("message", function (e) {
    if (e.data && e.data.type === "bn-push") { window.__bnLastPush = e.data; try { document.dispatchEvent(new CustomEvent("bn:push", { detail: e.data })); } catch (er) {} }
  });

  function init() {
    addButtons();
    if (st().on) BN.alertsStatus().then(paintBell);
    // the top bar may be re-rendered by the dashboard; re-add the bell if it disappears
    try { new MutationObserver(function () { if (!document.querySelector(".bn-top .bnal-bell") && document.querySelector(".bn-top .bn-acts")) addButtons(); })
      .observe(document.body, { childList: true, subtree: false }); } catch (e) {}
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
