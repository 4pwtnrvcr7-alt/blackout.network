/* Shared Refresh fill button (PR #293). Progress is 0–100% from real stages the
   page reports; it never sits at 99 (it jumps to 100 when the work is done).
   Single tap. prefers-reduced-motion disables the sheen and width easing but
   still shows the percentage. */
(function (W) {
  var RM = !!(W.matchMedia && W.matchMedia("(prefers-reduced-motion: reduce)").matches);
  function st(btn) {
    return btn._bnRef || (btn._bnRef = { p: 0, tgt: 0, raf: 0, busy: 0 });
  }
  function labs(btn) {
    return {
      a: btn.querySelector(".bn-ref-lab-a, .tl-ref-lab-a"),
      b: btn.querySelector(".bn-ref-lab-b, .tl-ref-lab-b")
    };
  }
  function apply(btn, p) {
    if (!btn) return;
    var s = st(btn);
    p = Math.max(0, Math.min(100, p));
    if (s.tgt >= 100 && p >= 99) p = 100;
    s.p = p;
    var shown = Math.round(p);
    if (s.tgt >= 100 && shown >= 99) shown = 100;
    var pct = shown + "%";
    btn.style.setProperty("--tl-ref-p", pct);
    btn.style.setProperty("--bn-ref-p", pct);
    var lab = (s.busy && shown < 100) ? ("Refresh " + shown + "%") : "Refresh";
    var L = labs(btn);
    if (L.a) L.a.textContent = lab;
    if (L.b) L.b.textContent = lab;
    if (s.busy) {
      btn.setAttribute("aria-label", "Refreshing, " + shown + " percent");
      btn.setAttribute("aria-valuenow", String(shown));
    }
  }
  function tick(btn) {
    var s = st(btn);
    s.raf = 0;
    var d = s.tgt - s.p;
    if (Math.abs(d) < 0.4) { apply(btn, s.tgt); return; }
    var step = RM ? d : (s.tgt >= 100 ? Math.max(4, d * 0.4) : Math.max(0.6, d * 0.22));
    apply(btn, s.p + step);
    s.raf = W.requestAnimationFrame(function () { tick(btn); });
  }
  function stage(btn, p) {
    if (!btn) return;
    var s = st(btn);
    s.tgt = Math.max(s.tgt, Math.min(100, p));
    if (s.tgt >= 100) s.tgt = 100;
    if (RM) { apply(btn, s.tgt); return; }
    if (!s.raf) s.raf = W.requestAnimationFrame(function () { tick(btn); });
  }
  function busy(btn, on) {
    if (!btn) return;
    var s = st(btn);
    if (on) {
      s.busy = 1; s.p = 0; s.tgt = 0;
      if (s.raf) { W.cancelAnimationFrame(s.raf); s.raf = 0; }
      apply(btn, 0);
      btn.classList.remove("is-result");
      btn.classList.add("is-filling");
      btn.setAttribute("role", "progressbar");
      btn.setAttribute("aria-valuemin", "0");
      btn.setAttribute("aria-valuemax", "100");
      btn.setAttribute("aria-label", "Refreshing, 0 percent");
    } else {
      s.busy = 0;
      if (s.raf) { W.cancelAnimationFrame(s.raf); s.raf = 0; }
      btn.classList.remove("is-filling");
      btn.removeAttribute("role");
      btn.removeAttribute("aria-valuemin");
      btn.removeAttribute("aria-valuemax");
      btn.removeAttribute("aria-valuenow");
      btn.style.removeProperty("--tl-ref-p");
      btn.style.removeProperty("--bn-ref-p");
    }
    btn.classList.toggle("busy", !!on);
    btn.setAttribute("aria-busy", on ? "true" : "false");
  }
  function done(btn, lab) {
    if (!btn) return;
    var L = labs(btn);
    clearTimeout(btn._doneT);
    if (!lab) {
      btn.classList.remove("is-result");
      if (L.a) L.a.textContent = "Refresh";
      if (L.b) L.b.textContent = "Refresh";
      btn.setAttribute("aria-label", "Refresh");
      return;
    }
    btn.classList.add("is-result");
    if (L.a) L.a.textContent = lab;
    if (L.b) L.b.textContent = lab;
    btn.setAttribute("aria-label", lab);
    btn._doneT = setTimeout(function () { done(btn, ""); }, 2600);
  }
  function isBusy(btn) {
    return !!(btn && (btn.classList.contains("busy") || (btn._bnRef && btn._bnRef.busy)));
  }
  function bind(btn, run) {
    if (!btn || btn._bnRefBound) return btn;
    btn._bnRefBound = 1;
    btn.addEventListener("click", function () {
      if (isBusy(btn)) return;
      try {
        var p = run(btn);
        if (p && typeof p.then === "function") p.catch(function () {});
      } catch (e) {}
    });
    return btn;
  }
  W.BNRefresh = { apply: apply, stage: stage, busy: busy, done: done, isBusy: isBusy, bind: bind };
})(window);
