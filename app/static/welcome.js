/* BLACKOUT.NETWORK /welcome onboarding (t1305u). First-party only. */
(function () {
  if (window.__bnWelcome) return; window.__bnWelcome = 1;
  var STEPS = ["hero", "interests", "brief", "inbox", "install", "follow", "tools"];
  var PREF = "bn_welcome_prefs";
  var root = document.documentElement;
  root.classList.add("wel-js");
  try { localStorage.setItem("bn_welcome_seen", "1"); } catch (e) {}

  function prefs() { try { return JSON.parse(localStorage.getItem(PREF) || "{}") || {}; } catch (e) { return {}; } }
  function save(p) { try { localStorage.setItem(PREF, JSON.stringify(Object.assign(prefs(), p))); } catch (e) {} }
  function cur() { var s = document.querySelector(".wel-step.is-on"); return s ? s.getAttribute("data-step") : "hero"; }
  function track(step) { if (typeof window.T === "function") { try { T("welcome_step", { step: step }); } catch (e) {} } }

  function go(id, user) {
    if (STEPS.indexOf(id) < 0) id = "hero";
    document.querySelectorAll(".wel-step").forEach(function (s) {
      var on = s.getAttribute("data-step") === id;
      s.classList.toggle("is-on", on);
      if (on) s.removeAttribute("hidden"); else s.setAttribute("hidden", "");
    });
    document.querySelectorAll(".wel-dots a, .wel-dot").forEach(function (d) {
      var sid = d.getAttribute("data-step") || (d.getAttribute("href") || "").replace("#", "");
      var on = sid === id;
      d.classList.toggle("on", on);
      if (on) d.setAttribute("aria-current", "step"); else d.removeAttribute("aria-current");
    });
    var n = STEPS.indexOf(id);
    document.querySelectorAll("[data-back]").forEach(function (b) { b.hidden = n <= 0; });
    if (user) { try { history.replaceState(null, "", "#" + id); } catch (e) {} }
    save({ step: id });
    track(id);
    if (id === "install") refreshAlerts();
    var stage = document.querySelector(".wel-stage");
    if (stage) stage.scrollTop = 0;
    try { window.scrollTo(0, 0); } catch (e) {}
  }

  var start = (location.hash || "").replace(/^#/, "");
  var fromHash = STEPS.indexOf(start) >= 0;
  if (!fromHash) start = prefs().step && STEPS.indexOf(prefs().step) >= 0 ? prefs().step : "hero";
  go(start);

  window.addEventListener("hashchange", function () {
    var h = (location.hash || "").replace(/^#/, "");
    if (STEPS.indexOf(h) >= 0) go(h);
  });

  document.addEventListener("click", function (e) {
    var nx = e.target.closest("[data-next]");
    if (nx) { e.preventDefault(); var i = STEPS.indexOf(cur()); go(STEPS[Math.min(i + 1, STEPS.length - 1)], true); return; }
    var bk = e.target.closest("[data-back]");
    if (bk) { e.preventDefault(); var j = STEPS.indexOf(cur()); go(STEPS[Math.max(j - 1, 0)], true); return; }
    var jmp = e.target.closest(".wel-dots a, a.wel-dot, [data-go]");
    if (jmp) {
      var sid = jmp.getAttribute("data-step") || (jmp.getAttribute("href") || "").replace("#", "");
      if (STEPS.indexOf(sid) >= 0) { e.preventDefault(); go(sid, true); }
    }
  });

  /* ---- interests + extras + location ---- */
  function syncChips() {
    var p = prefs();
    var picked = p.interests || [];
    document.querySelectorAll(".wel-chip[data-cat]").forEach(function (c) {
      var on = picked.indexOf(c.getAttribute("data-cat")) >= 0;
      c.classList.toggle("on", on);
      c.setAttribute("aria-pressed", on ? "true" : "false");
      var box = document.querySelector('input[name=interests][value="' + c.getAttribute("data-cat") + '"]');
      if (box) box.checked = on;
    });
    document.querySelectorAll(".wel-chip[data-extra]").forEach(function (c) {
      var on = (p.extras || []).indexOf(c.getAttribute("data-extra")) >= 0;
      c.classList.toggle("on", on);
      c.setAttribute("aria-pressed", on ? "true" : "false");
    });
    var loc = document.querySelector('input[name=location]');
    if (loc && p.location && !loc.value) loc.value = p.location;
    var locChip = document.querySelector(".wel-chip[data-loc]");
    if (locChip && loc) {
      var on = (loc.value || "") === locChip.getAttribute("data-loc");
      locChip.classList.toggle("on", on);
      locChip.setAttribute("aria-pressed", on ? "true" : "false");
    }
    var crime = document.querySelector(".wel-crime");
    if (crime) crime.hidden = !(loc && loc.value.trim());
    var freq = p.frequency || "twice";
    document.querySelectorAll('input[name=frequency]').forEach(function (r) { if (r.value === freq) r.checked = true; });
  }
  syncChips();

  document.addEventListener("click", function (e) {
    var c = e.target.closest(".wel-chip[data-cat]");
    if (c) {
      var cat = c.getAttribute("data-cat");
      var p = prefs(); var list = (p.interests || []).slice();
      var i = list.indexOf(cat); if (i >= 0) list.splice(i, 1); else list.push(cat);
      save({ interests: list }); syncChips(); return;
    }
    var x = e.target.closest(".wel-chip[data-extra]");
    if (x) {
      var ex = x.getAttribute("data-extra");
      var p2 = prefs(); var list2 = (p2.extras || []).slice();
      var k = list2.indexOf(ex); if (k >= 0) list2.splice(k, 1); else list2.push(ex);
      save({ extras: list2 }); syncChips(); return;
    }
    var lc = e.target.closest(".wel-chip[data-loc]");
    if (lc) {
      var loc = document.querySelector('input[name=location]');
      var val = lc.getAttribute("data-loc");
      if (loc) {
        if (loc.value === val) { loc.value = ""; save({ location: "" }); }
        else { loc.value = val; save({ location: val }); }
      }
      syncChips();
    }
  });
  var locIn = document.querySelector('input[name=location]');
  if (locIn) locIn.addEventListener("input", function () { save({ location: locIn.value.trim() }); syncChips(); });
  document.querySelectorAll('input[name=frequency]').forEach(function (r) {
    r.addEventListener("change", function () { if (r.checked) save({ frequency: r.value }); });
  });

  /* ---- newsletter signup (same endpoint and fields as /newsletter) ---- */
  var form = document.querySelector("form.wel-form");
  if (form) {
    var trk = form.querySelector(".nl-trk, .wel-trk");
    if (trk && window.BN_GA_REGION !== "ok") trk.hidden = false;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var em = form.querySelector('input[name=email]');
      var msg = form.querySelector(".wel-msg");
      var btn = form.querySelector('button[type=submit]');
      var v = (em.value || "").trim();
      function say(t, ok) { if (!msg) return; msg.textContent = t; msg.className = "wel-msg" + (ok ? " ok" : t ? " err" : ""); }
      if (!v) { say("Enter your email address."); em.setAttribute("aria-invalid", "true"); em.focus(); return; }
      var RE = /^[^\s@"<>(),;:\\[\]]{1,64}@[^\s@"<>(),;:\\[\]]+\.[A-Za-z]{2,63}$/;
      if (v.length > 254 || !RE.test(v)) { say("That doesn't look like a valid email address."); em.setAttribute("aria-invalid", "true"); em.focus(); return; }
      var fd = new FormData(form);
      var cats = [].slice.call(form.querySelectorAll("input[name=interests]"));
      var picked = cats.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
      var body = {
        email: v,
        frequency: fd.get("frequency") || "twice",
        interests: (!picked.length || picked.length === cats.length) ? ["all"] : picked,
        csrf: fd.get("csrf"),
        website: fd.get("website") || "",
        source: "welcome",
        location: (fd.get("location") || "").trim(),
        crime_brief: fd.get("crime_brief") ? 1 : 0,
        crime_alerts: fd.get("crime_alerts") ? 1 : 0,
        track_consent: fd.get("track_consent") ? 1 : 0,
        trk_shown: (trk && !trk.hidden) ? 1 : 0
      };
      btn.disabled = true; var old = btn.textContent; btn.textContent = "Sending…"; say("", true);
      function post(b) {
        return fetch("/api/newsletter/subscribe", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b), credentials: "same-origin" })
          .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j }; }); });
      }
      post(body).then(function (r) {
        if (r.status === 403) {
          return fetch("/api/newsletter/meta", { cache: "no-store" }).then(function (m) { return m.json(); }).then(function (m) {
            body.csrf = m.csrf; var h = form.querySelector('input[name=csrf]'); if (h) h.value = m.csrf;
            return post(body);
          });
        }
        return r;
      }).then(function (r) {
        say((r.j && r.j.message) || ("Something went wrong (" + r.status + "). Please try again."), r.ok);
        if (r.ok) { save({ signed: 1, email: v, frequency: body.frequency }); go("inbox", true); }
        else if (r.j && r.j.field === "email") { em.setAttribute("aria-invalid", "true"); em.focus(); }
      }).catch(function () { say("Network error. Please try again."); })
        .then(function () { btn.disabled = false; btn.textContent = old; });
    });
  }

  /* ---- device picker + alerts ---- */
  function detectDevice() {
    var ua = navigator.userAgent || "";
    if (/iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && (navigator.maxTouchPoints || 0) > 1 && /Mobile/.test(ua))) return "iphone";
    if (/iPad/.test(ua) || (/Macintosh/.test(ua) && (navigator.maxTouchPoints || 0) > 1)) return "iphone";
    if (/Android/i.test(ua)) return "android";
    return "desktop";
  }
  function setDevice(id) {
    var box = document.querySelector(".wel-install");
    if (box) box.setAttribute("data-device", id);
    document.querySelectorAll(".wel-dev").forEach(function (b) {
      var on = b.getAttribute("data-device") === id;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll(".wel-guide").forEach(function (g) {
      var on = g.getAttribute("data-for") === id;
      g.hidden = !on;
    });
    save({ device: id });
  }
  setDevice(prefs().device || detectDevice());
  document.addEventListener("click", function (e) {
    var d = e.target.closest(".wel-dev[data-device]");
    if (d) { e.preventDefault(); setDevice(d.getAttribute("data-device")); }
    if (e.target.closest("[data-install-guide]")) {
      e.preventDefault();
      if (window.BN && BN.showInstallGuide) BN.showInstallGuide();
    }
    if (e.target.closest("[data-bn-alerts], .wel-alerts-btn")) {
      /* alerts.js also listens for data-bn-alerts; we just refresh status after a beat */
      setTimeout(refreshAlerts, 800);
      setTimeout(refreshAlerts, 2500);
    }
  });

  function refreshAlerts() {
    var st = document.querySelector(".wel-alerts-status");
    var btn = document.querySelector(".wel-alerts-btn");
    function paint(t, kind) { if (st) { st.textContent = t; st.className = "wel-alerts-status" + (kind ? " " + kind : ""); } }
    var env = (window.BN && BN.alertsStatus) ? null : null;
    var run = window.BN && BN.alertsStatus ? BN.alertsStatus() : Promise.resolve(null);
    Promise.resolve(run).then(function (s) {
      if (!s) {
        if (!("Notification" in window)) { paint("Notifications are not available in this browser.", "muted"); if (btn) btn.hidden = true; return; }
        s = { ios: /iPhone|iPad|iPod/.test(navigator.userAgent), standalone: (matchMedia("(display-mode: standalone)").matches || navigator.standalone === true), permission: Notification.permission, on: Notification.permission === "granted", supported: true };
      }
      if (s.on || s.permission === "granted" && !(s.ios && !s.standalone)) { paint("Alerts are on in this browser.", "ok"); if (btn) btn.textContent = "Alerts are on"; return; }
      if (s.permission === "denied") { paint("Notifications are blocked. You can allow them in your browser or phone settings, then come back.", "muted"); return; }
      if (s.ios && !s.standalone) {
        paint("On iPhone, add BLACKOUT to your Home Screen first, then open it from there and turn on alerts. This needs iOS 16.4 or newer.", "muted");
        return;
      }
      paint("You can turn on alerts for rank 7+ stories, once you allow notifications.", "");
    }).catch(function () {});
  }
  refreshAlerts();

  /* ---- gentle parallax (off when the user prefers reduced motion) ---- */
  var reduce = false;
  try { reduce = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  if (!reduce) {
    var layers = [].slice.call(document.querySelectorAll("[data-depth]"));
    var tx = 0, ty = 0, cx = 0, cy = 0, raf = 0;
    function tick() {
      raf = 0;
      cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
      layers.forEach(function (el) {
        var d = parseFloat(el.getAttribute("data-depth") || "0.1");
        el.style.transform = "translate3d(" + (cx * d) + "px," + (cy * d) + "px,0)";
      });
      if (Math.abs(tx - cx) > 0.1 || Math.abs(ty - cy) > 0.1) raf = requestAnimationFrame(tick);
    }
    function move(x, y) {
      var w = window.innerWidth || 1, h = window.innerHeight || 1;
      tx = (x / w - 0.5) * 24; ty = (y / h - 0.5) * 16;
      if (!raf) raf = requestAnimationFrame(tick);
    }
    window.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse") move(e.clientX, e.clientY); }, { passive: true });
  }
})();
