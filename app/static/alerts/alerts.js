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
  // subscribe/unsubscribe are idempotent, so a dropped request (Render free tier 502/504, network blip) is retried twice
  function post(path, body, n) {
    n = n || 0;
    var again = function () { return new Promise(function (res) { setTimeout(res, 800 * (n + 1)); }).then(function () { return post(path, body, n + 1); }); };
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        if ((r.status === 502 || r.status === 504) && n < 2) return again();
        return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw new Error(j.error || "Something went wrong (HTTP " + r.status + "). Please try again."); return j; });
      }, function (e) { if (n < 2) return again(); throw new Error("Can’t reach blackout.network. Check your connection and try again."); });
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
  var X = '<span class="bnal-xb"><svg aria-hidden="true" focusable="false" viewBox="0 0 12 12"><path d="M2.2 2.2l7.6 7.6M9.8 2.2L2.2 9.8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg></span>';
  var CHECK = '<svg class="bnal-check" aria-hidden="true" focusable="false" viewBox="0 0 20 20"><path d="M4.2 10.4l3.6 3.6 8-8.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHEV = '<svg class="bnal-chev" aria-hidden="true" focusable="false" viewBox="0 0 8 14"><path d="M1 1l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var PAGEMENU = '<svg aria-hidden="true" focusable="false" width="18" height="18" viewBox="-10 -10 20 20"><path fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" d="M-6.5 -4.5h13M-6.5 0h13M-6.5 4.5h8"/></svg>';
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
  var el = null, lastFocus = null, opened = 0, saveSeq = 0;
  function closePanel() {
    if (!el) return; el.classList.remove("bnal-open"); document.documentElement.classList.remove("bnal-lock");
    var x = el;
    var delay = 340; try { if (matchMedia("(prefers-reduced-motion: reduce)").matches) delay = 0; } catch (e) {}
    setTimeout(function () {
      if (x.classList.contains("bnal-open")) return;
      x.hidden = true;
      var c = x.querySelector(".bnal-card"); if (c) c.style.transform = "";
    }, delay);
    if (lastFocus && lastFocus.focus) try { lastFocus.focus(); } catch (e) {}
  }
  function setStatus(t) {
    var n = el && el.querySelector(".bnal-status"); if (n) n.textContent = t || "";
  }
  function bindDrag(card) {
    if (card.dataset.drag) return; card.dataset.drag = "1";
    var sy = 0, y = 0, stt = 0, mode = 0, pid = 0;
    function bodyEl() { return card.querySelector(".bnal-body"); }
    card.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      if (e.target.closest("button, a, input, summary, textarea, select")) return;
      var b = bodyEl(), chrome = e.target.closest(".bnal-grab, .bnal-head");
      if (!chrome && b && b.scrollTop > 2) return;
      mode = 1; pid = e.pointerId; sy = y = e.clientY; stt = Date.now();
    });
    card.addEventListener("pointermove", function (e) {
      if (!mode || e.pointerId !== pid) return;
      var dy = e.clientY - sy;
      if (mode === 1) {
        if (Math.abs(dy) < 8) return;
        var b = bodyEl();
        if (dy <= 0 || (!e.target.closest(".bnal-grab, .bnal-head") && b && b.scrollTop > 2)) { mode = 0; return; }
        mode = 2; card.dataset.dragged = "1"; card.classList.add("bnal-dragging");
        try { card.setPointerCapture(pid); } catch (err) {}
      }
      if (mode !== 2) return;
      y = e.clientY; card.style.transform = "translateY(" + Math.max(0, dy) + "px)";
      e.preventDefault();
    }, { passive: false });
    function end(e) {
      if (!mode || (e && e.pointerId !== pid)) return;
      var dy = y - sy, dt = Math.max(1, Date.now() - stt), was = mode; mode = 0;
      if (was !== 2) return;
      var dismiss = dy > 90 || (dy > 40 && dy / dt > 0.65);
      card.classList.remove("bnal-dragging");
      requestAnimationFrame(function () {
        card.style.transform = "";
        if (dismiss) closePanel();
        setTimeout(function () { card.dataset.dragged = ""; }, 0);
      });
    }
    card.addEventListener("pointerup", end);
    card.addEventListener("pointercancel", end);
    card.addEventListener("click", function (e) {
      if (card.dataset.dragged === "1") { card.dataset.dragged = ""; e.preventDefault(); e.stopPropagation(); }
    }, true);
  }
  function shell() {
    if (el) return el;
    el = document.createElement("div"); el.className = "bnal"; el.hidden = true;
    el.innerHTML = '<div class="bnal-scrim" data-x></div><section class="bnal-card" role="dialog" aria-modal="true" aria-labelledby="bnal_h" aria-describedby="bnal_st" tabindex="-1">'
      + '<div class="bnal-grab" aria-hidden="true"></div>'
      + '<div class="bnal-head"><div class="bnal-titles"><h2 id="bnal_h">Alerts</h2><p class="bnal-status" id="bnal_st"></p></div><button type="button" class="bnal-x" data-x aria-label="Close">' + X + '</button></div>'
      + '<div class="bnal-body"></div></section>';
    document.body.appendChild(el);
    bindDrag(el.querySelector(".bnal-card"));
    el.addEventListener("click", function (e) { if (e.target.closest("[data-x]")) { e.preventDefault(); closePanel(); } });
    el.addEventListener("change", function (e) {
      var t = e.target; if (!t || !el.querySelector(".bnal-lv")) return;
      if (t.name !== "bnal_lvl" && !(t.closest && t.closest(".bnal-cats"))) return;
      if (el.querySelector("[data-bnal=on]")) return;   // not subscribed yet: Turn on alerts sends the choice
      var ch = readChoices();
      if (ch.none) {
        say("Pick at least one category under More options.", "err");
        if (t.type === "checkbox") t.checked = true;
        return;
      }
      if (t.name === "bnal_lvl") setStatus(t.value === "all" ? "On, all ranked alerts" : "On, major alerts only");
      saveChanges(null);
    });
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
    var opt = function (k, title, sub) {
      return '<label class="bnal-opt"><input type="radio" name="bnal_lvl" value="' + k + '"' + (lvl === k ? " checked" : "") + '>'
        + '<span class="bnal-ot"><b>' + title + '</b><span class="bnal-om">' + sub + '</span></span>' + CHECK + '</label>';
    };
    var cl = (c.categories || []).map(function (x) {
      return '<label class="bnal-cat"><input type="checkbox" value="' + esc(x.key) + '"' + (allOn || cats.indexOf(x.key) >= 0 ? " checked" : "") + '><span>' + esc(x.label) + '</span></label>';
    }).join("");
    return '<fieldset class="bnal-lv"><legend class="bnal-sr">How many alerts</legend>'
      + opt("major", "Major alerts only", "Rank 7+, a few a week")
      + opt("all", "All ranked alerts", "Rank 5+, several a day") + '</fieldset>'
      + (cl ? '<details class="bnal-more"><summary><span>More options</span>' + CHEV + '</summary><div class="bnal-moreb"><p class="bnal-note">Alert me about</p><div class="bnal-cats">' + cl + '</div></div></details>' : "");
  }
  function linkRow(kind, label) {
    return '<button type="button" class="bnal-link' + (kind === "off" ? " bnal-stop" : "") + '" data-bnal="' + kind + '"'
      + (kind === "sample" ? ' aria-expanded="false"' : "") + '>' + label + '</button>';
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
    var msg = '<p class="bnal-msg" role="status" aria-live="polite"></p>' + SAMPLE_BOX;
    if (E.inApp) { setStatus("Open in Safari or Chrome"); return body('<p class="bnal-lead">This in-app browser can’t show alerts.</p><p class="bnal-note">Open <b>blackout.network</b> in Safari or Chrome, then tap the bell.</p>'); }
    if (E.ios && !E.standalone) {
      var old = E.ver && E.ver < 16.4;
      setStatus(old ? "Needs iOS 16.4 or newer" : "Home Screen app");
      return body('<p class="bnal-lead">On iPhone and iPad, alerts work from the Home Screen app.</p>'
        + (old ? '<p class="bnal-note bnal-warn">This needs iOS 16.4 or newer. Update iOS in Settings first.</p>' : "")
        + '<ol class="bnal-steps"><li><span class="bnal-n">1</span><span>Tap <b>Share</b> <span class="bnal-ki">' + SHARE + '</span> in Safari (on iOS 26, tap <span class="bnal-ki">' + PAGEMENU + '</span> at the left of the address bar first)</span></li>'
        + '<li><span class="bnal-n">2</span><span>Tap <b>Add to Home Screen</b></span></li>'
        + '<li><span class="bnal-n">3</span><span>Open <b>BLACKOUT</b> from your Home Screen and tap the bell ' + '<span class="bnal-ki">' + BELL + '</span></span></li></ol>'
        + IOS_ART
        + (typeof BN.showInstallGuide === "function" ? '<button type="button" class="bnal-go" data-bnal="install">Show me how</button>' : "")
        + '<div class="bnal-group">' + linkRow("sample", "See a sample") + '</div>' + msg);
    }
    if (!E.api) { setStatus("Not available in this browser"); return body('<p class="bnal-lead">This browser can’t show alerts.</p><p class="bnal-note">Use a current version of Chrome, Edge, Firefox, Samsung Internet or Safari.</p>' + '<div class="bnal-group">' + linkRow("sample", "See a sample") + '</div>' + msg); }
    if (Notification.permission === "denied") {
      setStatus("Notifications are blocked");
      return body('<p class="bnal-lead">Notifications are blocked for this site.</p><p class="bnal-note">'
        + (E.android ? "Open your phone’s <b>Settings › Apps › " + (E.standalone ? "BLACKOUT" : "your browser") + " › Notifications</b>, allow them for blackout.network, then come back."
           : E.ios ? "Open <b>Settings › Notifications › BLACKOUT</b> and turn on <b>Allow Notifications</b>, then come back."
           : "Click the icon to the left of the address bar, set <b>Notifications</b> to <b>Allow</b>, then reload this page.")
        + '</p>' + '<div class="bnal-group">' + linkRow("sample", "See a sample") + '</div>' + msg);
    }
    getCfg().then(function (cf) {
      c = cf;
      var on = !!s.on && Notification.permission === "granted";
      var intro = opts.from === "install" ? '<p class="bnal-ok">You’re all set on your Home Screen. One more step:</p>' : "";
      if (on) {
        setStatus(s.level === "all" ? "On, all ranked alerts" : "On, major alerts only");
        body(soon(c) + choices(c, s)
          + '<div class="bnal-group">' + linkRow("testpush", "Send a test alert") + linkRow("sample", "See a sample") + '</div>'
          + '<div class="bnal-group">' + linkRow("off", "Turn off alerts") + '</div>' + msg);
      } else {
        setStatus("Off");
        body(intro + '<p class="bnal-lead">Major threats, the moment they’re confirmed. Free. Turn off any time.</p>' + soon(c) + choices(c, s)
          + '<button type="button" class="bnal-go" data-bnal="on">Turn on alerts</button>'
          + '<p class="bnal-note">Your browser will ask to allow notifications. Tap <b>Allow</b>. Never more than ' + (c.max_per_hour || 6) + ' an hour.</p>'
          + '<p class="bnal-msg" role="status" aria-live="polite"></p>'
          + '<div class="bnal-group">' + linkRow("sample", "See a sample") + '</div>' + SAMPLE_BOX);
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
  // For the Home Screen soft-ask card (install-guide.js). Call it straight from the tap handler: requestPermission runs synchronously
  // here, inside the user gesture. Resolves {perm, ok, live, error}; never rejects. Uses the same subscribe path as the panel.
  BN.turnOnAlerts = function (opts) {
    opts = opts || {}; var level = opts.level === "all" ? "all" : "major";
    if (!E.api) return Promise.resolve({ perm: "unsupported", ok: false });
    var permP = Notification.permission === "granted" ? Promise.resolve("granted") : new Promise(function (res) {
      var p = Notification.requestPermission(res); if (p && p.then) p.then(res);
    });
    return permP.then(function (perm) {
      if (perm !== "granted") return { perm: perm, ok: false };
      return Promise.all([getReg(), getCfg()]).then(function (rc) {
        var reg = rc[0], cf = rc[1];
        if (!cf.vapid_public_key) throw new Error("Alerts are not available right now. Please try again later.");
        return reg.pushManager.getSubscription().then(function (sub) {
          return sub || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(cf.vapid_public_key) });
        });
      }).then(function (sub) {
        return post("/api/alerts/subscribe", { sub: sub.toJSON(), level: level, cats: [], test: isTest() }).then(function (j) {
          save({ on: true, level: j.level, cats: j.cats, endpoint: sub.endpoint, test: !!j.test, since: new Date().toISOString() });
          return { perm: "granted", ok: true, live: !!j.live, level: j.level };
        });
      }).catch(function (e) { return { perm: "granted", ok: false, error: (e && e.message) || "Something went wrong. Please try again." }; });
    });
  };
  function restoreChoices() {
    var s = st(), lvl = s.level === "all" ? "all" : "major", cats = s.cats || [], all = !cats.length;
    [].forEach.call(el.querySelectorAll('input[name="bnal_lvl"]'), function (r) { r.checked = r.value === lvl; });
    [].forEach.call(el.querySelectorAll(".bnal-cats input"), function (b) { b.checked = all || cats.indexOf(b.value) >= 0; });
    if (s.on) setStatus(lvl === "all" ? "On, all ranked alerts" : "On, major alerts only");
  }
  function saveChanges(btn) {
    var ch = readChoices();
    if (ch.none) { say("Pick at least one category under More options.", "err"); return; }
    if (btn) btn.disabled = true;
    var seq = ++saveSeq;
    getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (seq !== saveSeq) return null;
      if (!sub) { save(null); render(); throw null; }
      return post("/api/alerts/subscribe", { sub: sub.toJSON(), level: ch.level, cats: ch.cats, test: isTest() });
    }).then(function (j) {
      if (!j || seq !== saveSeq) return;
      var s = st(); s.level = j.level; s.cats = j.cats; save(s);
      if (btn) btn.disabled = false;
      setStatus(j.level === "all" ? "On, all ranked alerts" : "On, major alerts only");
      say("Saved.", "ok");
    }).catch(function (e) {
      if (seq !== saveSeq) return;
      if (btn) btn.disabled = false;
      if (e !== null) { say((e && e.message) || "Couldn’t save. Please try again.", "err"); restoreChoices(); }
    });
  }
  function turnOff(btn) {
    btn.disabled = true;
    getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) return;
      var ep = sub.endpoint;
      return post("/api/alerts/unsubscribe", { endpoint: ep }).catch(function () {}).then(function () { return sub.unsubscribe(); });
    }).catch(function () {}).then(function () { save(null); render(); setTimeout(function () { say("Alerts are off.", "ok"); }, 50); });
  }
  // ---------------- sample alert (t399): an in-panel preview built from a real recent rank 7+ alert, plus a local notification if allowed ----------------
  var SAMPLE_BOX = '<div class="bnal-sample" hidden></div>';
  var SOC = /^(Telegram|X |X:|Mastodon|Reddit|YouTube|Bluesky|social)/i;
  function cleanT(t) { return String(t || "").replace(/^[^\w"'(\[]+/, "").replace(/^(breaking( news)?|urgent|just in|alert)\s*[:\-–—|]\s*/i, "").replace(/\s*@\w+\s*$/, "").replace(/\s+\./g, ".").trim(); }
  function catLabel(c) { return ({ "war/conflict": "War & conflict", "natural disaster": "Natural disaster", political: "Politics", disease: "Disease", cyber: "Cyber",
    financial: "Financial", "space weather": "Space weather", "ufo/uap": "UFO / UAP", "spiritual/religious": "Religious" })[(c || "").toLowerCase()] || "Alert"; }
  function etTime(iso) {
    try { return new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " ET"; }
    catch (e) { return ""; }
  }
  var EXAMPLE = { cluster_id: "", rank: 8, category: "natural disaster", confidence: "High", eff_families: 3, families: ["NOAA", "USGS", "AP"], location: "Example City",
    title: "EXAMPLE: Major hurricane makes landfall; storm surge warnings in effect", high_at: new Date().toISOString(), links: [], example: true };
  var sampleP = null;
  function getSample() {
    if (!sampleP) sampleP = fetch("/api/new_high?mode=alert&since=" + new Date(Date.now() - 14 * 864e5).toISOString().slice(0, 19) + "Z", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) {
        var it = (j.items || []).filter(function (x) { return x.rank >= 7 && x.title; })
          .sort(function (a, b) { return (b.high_at || "").localeCompare(a.high_at || ""); })[0];
        if (!it) throw 0; return it;
      }).catch(function () { sampleP = null; return EXAMPLE; });
    return sampleP;
  }
  function asList(v) {
    if (typeof v === "string") { try { v = JSON.parse(v); } catch (e) { v = []; } }
    return Array.isArray(v) ? v : [];
  }
  function brief(it) {
    var seen = {}, fam = asList(it && it.families).filter(function (f) {
      if (f && typeof f === "object") f = f.name || f.label || "";
      var k = String(f || "").toLowerCase().replace(/^www\./, "").split(".")[0]; if (!f || f === "social" || seen[k]) return false; seen[k] = 1; return true; }).slice(0, 3);
    fam = fam.map(function (f) { return (f && typeof f === "object") ? (f.name || f.label || "") : String(f); });
    var n = (it && it.eff_families) || fam.length;
    return (it && it.location ? "Where: " + it.location + ". " : "")
      + (n ? "Confirmed by " + n + " independent source" + (n === 1 ? "" : "s") + (fam.length ? ", including " + fam.join(", ") : "") + ". " : "")
      + (it && it.score != null ? "Severity " + it.score + "/100. " : "")
      + "Open the alert page for the full brief and every source.";
  }
  function linkOf(x) {
    if (!x) return null;
    if (typeof x === "string") return /^https?:\/\//i.test(x) ? { url: x, source: "" } : null;
    if (typeof x === "object" && x.url) return x;
    return null;
  }
  function srcLink(it) {
    var ls = asList(it && it.links), l = null, i, y;
    for (i = 0; i < ls.length; i++) { y = linkOf(ls[i]); if (y && !SOC.test(y.source || "")) { l = y; break; } }
    if (!l) { for (i = 0; i < ls.length; i++) { y = linkOf(ls[i]); if (y) { l = y; break; } } }
    if (!l || !l.url) return "";
    var h = ""; try { h = new URL(l.url).hostname.replace(/^www\./, ""); } catch (e) {}
    return '<a class="bnal-src" href="' + esc(l.url) + '" target="_blank" rel="noopener nofollow">Source: ' + esc(l.source && !/^https?:/.test(l.source) ? l.source : h) + ' ↗</a>';
  }
  function sampleHTML(it) {
    var url = it.cluster_id ? "/wire/" + encodeURIComponent(it.cluster_id) : "/#wire", cat = catLabel(it.category), r = Math.max(0, Math.min(10, it.rank | 0));
    var head = cleanT(it.title);
    return '<div class="bnal-sh"><span class="bnal-tagS">SAMPLE</span><span>' + (it.example ? "Illustrative example (not a real event)" : "Based on a real alert from " + esc(etTime(it.high_at).replace(/,? \d+:\d\d [AP]M ET$/, ""))) + '</span></div>'
      + '<div class="bnal-notif" aria-label="How the notification looks on your lock screen"><img src="/icons/icon-192.png" alt="" width="38" height="38">'
      + '<div><div class="bnal-nt"><b>BLACKOUT</b><span>now</span></div><div class="bnal-nh">' + r + '/10 · ' + esc(cat.toUpperCase()) + '</div><div class="bnal-nb">' + esc(head) + '</div></div></div>'
      + '<article class="bnal-card2"><div class="bnal-cb"><img class="bnal-logo" src="/icons/icon-192.png" alt="BLACKOUT.NETWORK" width="28" height="28">'
      + '<span class="bnal-brand">BLACKOUT.<b>NETWORK</b></span><span class="bnal-rk bnal-rk' + (r >= 8 ? "h" : "m") + '">RANK ' + r + '</span></div>'
      + '<div class="bnal-mt">' + meter(r) + '<span class="bnal-ct">' + esc(cat) + '</span></div>'
      + '<h3 class="bnal-t">' + esc(head) + '</h3><p class="bnal-p">' + esc(brief(it)) + '</p>'
      + '<dl class="bnal-meta"><div><dt>Time</dt><dd>' + esc(etTime(it.high_at)) + '</dd></div><div><dt>Confidence</dt><dd>' + esc(it.confidence || "—") + '</dd></div></dl>'
      + '<div class="bnal-lk">' + srcLink(it) + (it.example ? "" : '<a class="bnal-open" href="' + url + '">Open the alert page →</a>') + '</div></article>'
      + '<p class="bnal-note">Real alerts arrive as a phone or desktop notification (top). Tap it to open the alert page.</p>';
  }
  function showSample(box, it) {
    var html; try { html = sampleHTML(it); } catch (err) { it = EXAMPLE; html = sampleHTML(EXAMPLE); }
    box.innerHTML = html; box.setAttribute("data-ready", "1");
    try {
      var sc = box.closest(".bnal-body");
      if (sc) sc.scrollTo({ top: Math.max(0, box.offsetTop - 8), behavior: "smooth" });
    } catch (e) {}
    return it;
  }
  function sample(btn) {
    var box = el && el.querySelector(".bnal-sample"); if (!box) return;
    if (!box.hidden && box.getAttribute("data-ready") === "1") { box.hidden = true; box.setAttribute("data-ready", ""); if (btn) btn.setAttribute("aria-expanded", "false"); return; }
    box.hidden = false; box.setAttribute("data-ready", ""); box.innerHTML = '<p class="bnal-note">Loading a sample…</p>'; if (btn) btn.setAttribute("aria-expanded", "true");
    getSample().then(function (it) {
      it = showSample(box, it);
      if (E.api && Notification.permission === "granted" && !(E.ios && !E.standalone)) {
        getReg().then(function (r) {
          return r.showNotification("SAMPLE · " + (it.rank | 0) + "/10 · " + catLabel(it.category).toUpperCase(), { body: cleanT(it.title).slice(0, 180),
            icon: "/icons/icon-192.png", badge: "/alerts/badge.png", tag: "bn-sample",
            data: { url: location.origin + (it.cluster_id ? "/wire/" + encodeURIComponent(it.cluster_id) : "/#wire") } });
        }).then(function () { say("Sample shown below and sent to your notifications.", "ok"); }, function () { say("Sample shown below.", "ok"); });
      } else say("Sample shown below.", "ok");
    }).catch(function () { showSample(box, EXAMPLE); say("Sample shown below.", "ok"); });
  }
  // "Send me a test push": a real push from our server through your browser's push service (Apple, Google, Mozilla, Microsoft)
  function testPush(btn) {
    btn.disabled = true; say("Requesting a test push…");
    getReg().then(function (r) { return r.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { save(null); render(); throw null; }
      return post("/api/alerts/testpush", { endpoint: sub.endpoint });
    }).then(function (j) {
      say(j.queued === false ? "A test push is already on its way. It arrives within about 2 minutes." :
        "Test push requested. It arrives within about 2 minutes, even if you close this page.", "ok");
      setTimeout(function () { btn.disabled = false; }, 30000);
    }).catch(function (e) { btn.disabled = false; if (e !== null) say((e && e.message) || "Couldn’t request a test push. Please try again.", "err"); });
  }
  var IOS_ART = '<figure class="bnal-ios" aria-label="Three steps: tap Share, tap Add to Home Screen, open BLACKOUT and tap the bell">'
    + '<svg viewBox="0 0 330 150" role="img" aria-hidden="true" focusable="false">'
    + '<defs><linearGradient id="bnalm" x1="0" x2="1"><stop offset=".333" stop-color="#2BB673"/><stop offset=".333" stop-color="#F5A524"/><stop offset=".666" stop-color="#F5A524"/><stop offset=".666" stop-color="#FF4D4F"/></linearGradient></defs>'
    + [0, 1, 2].map(function (k) { return '<rect x="' + (14 + k * 108) + '" y="6" width="86" height="138" rx="14" fill="#14181D" stroke="#2f3742" stroke-width="2"/>'; }).join("")
    // 1: Safari bar with Share highlighted
    + '<rect x="22" y="112" width="70" height="22" rx="7" fill="#1d232b"/><circle cx="57" cy="123" r="10" fill="#FF4D4F" fill-opacity=".2" stroke="#FF4D4F" stroke-width="1.6"/>'
    + '<path d="M57 117v9M53.5 120.5l3.5-3.5 3.5 3.5M52.5 123.5h-1.5v6h12v-6h-1.5" fill="none" stroke="#E6E9EE" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    + '<rect x="24" y="22" width="66" height="8" rx="3" fill="#252B33"/><rect x="24" y="38" width="50" height="6" rx="3" fill="#252B33"/><rect x="24" y="50" width="58" height="6" rx="3" fill="#252B33"/>'
    // 2: share sheet row "Add to Home Screen"
    + '<rect x="130" y="70" width="70" height="66" rx="8" fill="#1d232b"/><rect x="134" y="78" width="62" height="18" rx="5" fill="#FF4D4F" fill-opacity=".18" stroke="#FF4D4F" stroke-width="1.4"/>'
    + '<rect x="138" y="81" width="12" height="12" rx="3" fill="none" stroke="#E6E9EE" stroke-width="1.4"/><path d="M144 84v6M141 87h6" stroke="#E6E9EE" stroke-width="1.4" stroke-linecap="round"/>'
    + '<text x="154" y="90.5" fill="#E6E9EE" font-size="7.4" font-family="Inter,system-ui" font-weight="700">Add to Home</text>'
    + '<rect x="136" y="102" width="50" height="6" rx="3" fill="#252B33"/><rect x="136" y="114" width="40" height="6" rx="3" fill="#252B33"/>'
    // 3: home screen with BN app + notification badge
    + '<rect x="248" y="44" width="38" height="38" rx="9" fill="#0B0D10" stroke="#3a4350"/><text x="267" y="69" text-anchor="middle" fill="#fff" font-size="15" font-family="Montserrat,Inter,system-ui" font-weight="800">BN</text>'
    + '<rect x="254" y="74" width="26" height="3" rx="1.5" fill="url(#bnalm)"/><circle cx="285" cy="45" r="7" fill="#FF4D4F"/><text x="285" y="48.5" text-anchor="middle" fill="#fff" font-size="9" font-weight="800" font-family="Inter,system-ui">1</text>'
    + '<text x="267" y="96" text-anchor="middle" fill="#c9d0d9" font-size="8" font-family="Inter,system-ui" font-weight="600">BLACKOUT</text>'
    + [[228, 22], [292, 22], [228, 104], [292, 104]].map(function (q) { return '<rect x="' + (q[0] - 8) + '" y="' + q[1] + '" width="16" height="16" rx="4" fill="#252B33"/>'; }).join("")
    + [0, 1, 2].map(function (k) { return '<circle cx="' + (57 + k * 108) + '" cy="6" r="10" fill="#FF4D4F"/><text x="' + (57 + k * 108) + '" y="10" text-anchor="middle" fill="#0B0D10" font-size="11" font-weight="800" font-family="Inter,system-ui">' + (k + 1) + '</text>'; }).join("")
    + '<path d="M103 75h8M211 75h8" stroke="#8B95A3" stroke-width="2" stroke-linecap="round"/><path d="M108 71l4 4-4 4M216 71l4 4-4 4" fill="none" stroke="#8B95A3" stroke-width="2" stroke-linecap="round"/>'
    + '</svg><figcaption>Add to Home Screen to get alerts</figcaption></figure>';

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
    if (a === "on") turnOn(t); else if (a === "save") saveChanges(t); else if (a === "off") turnOff(t); else if (a === "sample") sample(t); else if (a === "testpush") testPush(t);
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
