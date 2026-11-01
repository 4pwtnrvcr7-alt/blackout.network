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
        + IOS_ART
        + '<div class="bnal-acts">' + (typeof BN.showInstallGuide === "function" ? '<button type="button" class="bnal-go" data-bnal="install">Show me how</button>' : "")
        + '<button type="button" class="bnal-2" data-bnal="sample">Show a sample alert</button></div><p class="bnal-msg" role="status" aria-live="polite"></p>' + SAMPLE_BOX);
    }
    if (!E.api) return body('<p class="bnal-lead">This browser can’t show alerts.</p><p class="bnal-note">Use a current version of Chrome, Edge, Firefox, Samsung Internet or Safari.</p>' + '<div class="bnal-acts"><button type="button" class="bnal-2" data-bnal="sample">Show a sample alert</button></div><p class="bnal-msg" role="status" aria-live="polite"></p>' + SAMPLE_BOX);
    if (Notification.permission === "denied") {
      return body('<p class="bnal-lead">Notifications are blocked for this site.</p><p class="bnal-note">'
        + (E.android ? "Open your phone’s <b>Settings › Apps › " + (E.standalone ? "BLACKOUT" : "your browser") + " › Notifications</b>, allow them for blackout.network, then come back."
           : E.ios ? "Open <b>Settings › Notifications › BLACKOUT</b> and turn on <b>Allow Notifications</b>, then come back."
           : "Click the icon to the left of the address bar, set <b>Notifications</b> to <b>Allow</b>, then reload this page.")
        + '</p>' + '<div class="bnal-acts"><button type="button" class="bnal-2" data-bnal="sample">Show a sample alert</button></div><p class="bnal-msg" role="status" aria-live="polite"></p>' + SAMPLE_BOX);
    }
    getCfg().then(function (cf) {
      c = cf;
      var on = !!s.on && Notification.permission === "granted";
      var intro = opts.from === "install" ? '<p class="bnal-ok">You’re all set on your Home Screen. One more step:</p>' : "";
      if (on) {
        body('<p class="bnal-lead"><span class="bnal-pill">● On</span> You’ll get ' + (s.level === "all" ? "all ranked alerts (rank 5+)" : "major alerts (rank 7+)") + '.</p>'
          + soon(c) + choices(c, s)
          + '<div class="bnal-acts"><button type="button" class="bnal-go" data-bnal="save">Save changes</button>'
          + '<button type="button" class="bnal-2" data-bnal="testpush">Send me a test push</button>'
          + '<button type="button" class="bnal-2" data-bnal="sample">Show a sample</button>'
          + '<button type="button" class="bnal-off" data-bnal="off">Turn off alerts</button></div><p class="bnal-msg" role="status" aria-live="polite"></p>' + SAMPLE_BOX);
      } else {
        body(intro + '<p class="bnal-lead">Major threats, the moment they’re confirmed. Free. Turn off any time.</p>' + soon(c) + choices(c, s)
          + '<div class="bnal-acts"><button type="button" class="bnal-go bnal-big" data-bnal="on">' + BELL + '<span>Turn on alerts</span></button></div>'
          + '<p class="bnal-note">Your browser will ask to allow notifications. Tap <b>Allow</b>. Never more than ' + (c.max_per_hour || 6) + ' an hour.</p>'
          + '<p class="bnal-msg" role="status" aria-live="polite"></p>'
          + '<div class="bnal-acts bnal-acts-2"><button type="button" class="bnal-2" data-bnal="sample">Show a sample alert</button></div>' + SAMPLE_BOX);
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
  function brief(it) {
    var seen = {}, fam = (it.families || []).filter(function (f) {
      var k = String(f || "").toLowerCase().replace(/^www\./, "").split(".")[0]; if (!f || f === "social" || seen[k]) return false; seen[k] = 1; return true; }).slice(0, 3);
    var n = it.eff_families || fam.length;
    return (it.location ? "Where: " + it.location + ". " : "")
      + (n ? "Confirmed by " + n + " independent source" + (n === 1 ? "" : "s") + (fam.length ? ", including " + fam.join(", ") : "") + ". " : "")
      + (it.score != null ? "Severity " + it.score + "/100. " : "")
      + "Open the alert page for the full brief and every source.";
  }
  function srcLink(it) {
    var ls = it.links || [], l = ls.filter(function (x) { return x.url && !SOC.test(x.source || ""); })[0] || ls[0];
    if (!l) return "";
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
  function sample(btn) {
    var box = el && el.querySelector(".bnal-sample"); if (!box) return;
    if (!box.hidden && box.innerHTML) { box.hidden = true; if (btn) btn.setAttribute("aria-expanded", "false"); return; }
    box.hidden = false; box.innerHTML = '<p class="bnal-note">Loading a sample…</p>'; if (btn) btn.setAttribute("aria-expanded", "true");
    getSample().then(function (it) {
      box.innerHTML = sampleHTML(it);
      try { box.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) {}
      if (E.api && Notification.permission === "granted" && !(E.ios && !E.standalone)) {
        getReg().then(function (r) {
          return r.showNotification("SAMPLE · " + (it.rank | 0) + "/10 · " + catLabel(it.category).toUpperCase(), { body: cleanT(it.title).slice(0, 180),
            icon: "/icons/icon-192.png", badge: "/alerts/badge.png", tag: "bn-sample",
            data: { url: location.origin + (it.cluster_id ? "/wire/" + encodeURIComponent(it.cluster_id) : "/#wire") } });
        }).then(function () { say("Sample shown below and sent to your notifications.", "ok"); }, function () { say("Sample shown below.", "ok"); });
      } else say("Sample shown below.", "ok");
    });
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
