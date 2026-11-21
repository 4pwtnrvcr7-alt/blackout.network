/* BLACKOUT.NETWORK realtime helper (Nov 21 2026, pt1688u). One live connection per page: Server-Sent Events from /api/rt/stream,
   falling back to polling /api/rt/since every 20 s when SSE is unavailable or the server is at its connection cap.
   BNRT.on(fn)        fn(ev) for each 'rt' event {seq, items, new, heat:{cols,rows,reload}, wire_counts, last_scan}
   BNRT.onStatus(fn)  fn({last_scan}) when a scan lands; BNRT.onMode(fn) fn("live"|"polling"|"off")
   BNRT.refresh()     Promise of the server's refresh result (drops caches, asks the scanner for anything newer). */
(function () {
  "use strict";
  if (window.BNRT) return;
  var W = window, d = document, subs = [], ssubs = [], msubs = [], es = null, seq = 0, mode = "off", fails = 0, pollT = 0, retryT = 0, hideT = 0, seen = {};
  function emit(L, x) { L.forEach(function (f) { try { f(x); } catch (e) { if (W.console) console.error(e); } }); }
  function setMode(m) { if (m !== mode) { mode = m; emit(msubs, m); } }
  function take(ev) {
    if (!ev || !ev.seq || seen[ev.seq]) return; seen[ev.seq] = 1; if (ev.seq > seq) seq = ev.seq;
    emit(subs, ev); if (ev.last_scan) emit(ssubs, { last_scan: ev.last_scan });
  }
  function poll() {
    clearTimeout(pollT);
    if (d.hidden) { pollT = setTimeout(poll, 20000); return; }
    fetch("/api/rt/since?seq=" + seq + "&_=" + Date.now(), { cache: "no-store" }).then(function (r) { if (r.status === 404) throw 404; return r.json(); }).then(function (j) {
      if (j.reset) { seq = j.seq || 0; emit(subs, { seq: 0, reset: true, items: [], new: [], heat: { rows: [], reload: true } }); }
      (j.events || []).forEach(take); if (!seq && j.seq) seq = j.seq;
      if (j.last_scan) emit(ssubs, { last_scan: j.last_scan });
      if (mode !== "live") setMode("polling");
    }).catch(function (e) { if (e === 404) { setMode("off"); return; } }).then(function () {
      if (mode !== "off" && mode !== "live") pollT = setTimeout(poll, 20000 + Math.random() * 5000);
    });
  }
  function close() { if (es) { try { es.close(); } catch (e) {} es = null; } }
  function open() {
    clearTimeout(retryT); close();
    if (!W.EventSource) { setMode("polling"); poll(); return; }
    try { es = new EventSource("/api/rt/stream"); } catch (e) { setMode("polling"); poll(); return; }
    es.addEventListener("hello", function (m) { fails = 0; clearTimeout(pollT); var h = {}; try { h = JSON.parse(m.data); } catch (e) {}
      var behind = seq && h.seq > seq; if (!seq) seq = h.seq || 0; setMode("live"); if (h.last_scan) emit(ssubs, { last_scan: h.last_scan });
      if (behind) { fetch("/api/rt/since?seq=" + seq, { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) { (j.events || []).forEach(take); }).catch(function () {}); } });
    es.addEventListener("rt", function (m) { try { take(JSON.parse(m.data)); } catch (e) {} });
    es.addEventListener("status", function (m) { try { emit(ssubs, JSON.parse(m.data)); } catch (e) {} });
    es.onerror = function () {
      fails++;
      if (fails >= 3 || (es && es.readyState === 2)) {   /* closed or flapping: poll, try live again in 2 minutes */
        close(); setMode("polling"); poll(); retryT = setTimeout(open, 120000);
      }
    };
  }
  d.addEventListener("visibilitychange", function () {
    clearTimeout(hideT);
    if (d.hidden) hideT = setTimeout(function () { close(); clearTimeout(pollT); if (mode === "live") mode = "paused"; }, 60000);   /* free the server slot */
    else if (!es && mode !== "off") { open(); }
  });
  W.BNRT = {
    on: function (f) { subs.push(f); }, onStatus: function (f) { ssubs.push(f); }, onMode: function (f) { msubs.push(f); f(mode); },
    mode: function () { return mode; }, seq: function () { return seq; },
    refresh: function () {
      return fetch("/api/rt/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", cache: "no-store" })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j.http = r.status; return j; }); })
        .catch(function () { return { ok: false }; });
    }
  };
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", open); else open();
})();
