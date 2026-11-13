"""Site-wide "Refresh data" (Nov 13, Matt): one tap on the refresh icon in the top bar pulls fresh data from every live source
this node reads, so every "last scanned / last updated / last reported" time on the page moves forward after the page reloads.

POST /api/refresh-all   run (or join) one shared refresh; returns what was refreshed and when.
GET  /api/refresh-all   status only (last run, whether one is running, seconds until the next real run). Never starts work.

Taps share a scan: at most ONE real backend refresh per BN_REFRESH_WINDOW_S (default 60 s) for the whole process. A tap while a
refresh is running waits for that run and gets its result; a tap inside the window after it finished gets the last result
("coalesced": true). Nothing here touches the scanner core (scanner.py scoring, push.py, jets.py, config.json scan settings,
aviation_watch.py): the box scanner keeps its own schedule and its scans still arrive over the sync channel. On this node a run
  1. re-reads the newest synced scanner state (render_app._refresh_state, when running as the public node),
  2. marks every known short-TTL upstream cache as stale, so the next page load re-fetches it (values are kept, so a failing
     upstream still serves its last good copy; Trends and Key Figures rebuild this way),
  3. re-fetches the main live feeds in parallel (one thread per feed, BN_REFRESH_BUDGET_S overall, default 10 s); a slow feed keeps
     running in the background and is skipped by the next run until it finishes.
Kill switches: BN_REFRESH_ALL=0 (no button, endpoint 404), BN_REFRESH_WARM=0 (steps 1-2 only, no upstream calls from the run)."""
import os, sys, time, threading, traceback
from concurrent.futures import ThreadPoolExecutor, wait

def enabled(): return os.environ.get("BN_REFRESH_ALL", "1") != "0"
def window_s():
    try: return max(5.0, float(os.environ.get("BN_REFRESH_WINDOW_S", "60")))
    except ValueError: return 60.0
def budget_s():
    try: return max(1.0, float(os.environ.get("BN_REFRESH_BUDGET_S", "10")))
    except ValueError: return 10.0

# state lives on sys so a hot reload of this module (server._addon_mod) never resets the shared window or lock
_S = getattr(sys, "_bn_refresh_all", None)
if _S is None:
    _S = sys._bn_refresh_all = {"busy": False, "started": 0.0, "finished": 0.0, "result": None, "runs": 0, "taps": 0,
                                "inflight": set(), "cv": threading.Condition(threading.Lock())}

def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)) if t else None

# ---------------------------------------------------------------- step 2: stale-mark short-TTL caches
# (module, attribute, kind). "tdict": {key: (fetched_at, value, ...)} -> fetched_at = 0. "tdd": {key: {"t": fetched_at, ...}} -> t = 0.
# "tv": {"t": .., "v": ..} -> t = 0. Only time-based caches are listed: caches keyed on the synced DB (tabfeeds, bnoise, grid,
# scoring) or on file mtimes already change as soon as new data lands.
CACHES = [("weather", "_C", "tdict"), ("trends", "_C", "tdict"), ("netpages", "_C", "tdict"),
          ("solar_live", "_cache", "tdd"), ("solar_live", "_memo", "tv"),
          ("apple_v1", "_cache", "tv"), ("apple_v1", "_dcache", "tv"), ("unrest_feeds", "_C", "tv"),
          ("figures", "_C", "tv")]

def _mod(name):
    m = sys.modules.get(name)
    if m is not None: return m
    try:
        import server
        return server._addon_mod(name)
    except Exception:
        return None

def stale_caches():
    n = 0
    for name, attr, kind in CACHES:
        m = sys.modules.get(name)      # only modules this process has already loaded; nothing cached = nothing to mark
        c = getattr(m, attr, None) if m else None
        if not isinstance(c, dict): continue
        try:
            if kind == "tv":
                if "t" in c and c.get("t"): c["t"] = 0; n += 1
            elif kind == "tdd":
                for v in list(c.values()):
                    if isinstance(v, dict) and v.get("t"): v["t"] = 0; n += 1
            else:
                for k, v in list(c.items()):
                    if isinstance(v, tuple) and len(v) >= 2 and isinstance(v[0], (int, float)) and not isinstance(v[0], bool):
                        c[k] = (0.0,) + tuple(v[1:]); n += 1
        except Exception: traceback.print_exc()
    return n

# ---------------------------------------------------------------- step 3: re-fetch the main live feeds
def _w(mod, fn, *a, **k):
    def go():
        m = _mod(mod)
        if m is None: raise RuntimeError("module unavailable")
        return getattr(m, fn)(*a, **k)
    return go

WARM = [("solar_seismic", "Space weather + earthquakes (NOAA SWPC, USGS)", _w("solar_seismic", "collect", force=True)),
        ("solar_live", "Live sun imagery + SWPC status", _w("solar_live", "collect")),
        ("finance", "Markets", _w("finance", "summary", force=True)),
        ("spacex", "SpaceX launches", _w("spacex", "summary", force=True)),
        ("elon", "Key figure feeds", _w("elon", "summary", force=True)),
        ("figures", "Key Figures headlines", _w("figures", "summary", True)),
        ("politics", "Politics markets", _w("politics", "data", "24h", True)),
        ("home", "Homepage cards", _w("apple_v1", "home_data")),
        ("dash", "Homepage dashboard", _w("apple_v1", "dash_data"))]

def _state_hook():
    """The public node (render_app as __main__) re-reads the newest synced scan; the box dashboard has nothing to re-read."""
    f = getattr(sys.modules.get("__main__"), "_refresh_state", None)
    if callable(f): f()

def _one(key, fn):
    t0 = time.time()
    try:
        fn(); return {"id": key, "ok": True, "ms": int((time.time() - t0) * 1000)}
    except Exception as ex:
        return {"id": key, "ok": False, "ms": int((time.time() - t0) * 1000), "error": type(ex).__name__}
    finally:
        with _S["cv"]: _S["inflight"].discard(key)

def run():
    t0 = time.time(); out = {"sources": []}
    try: _state_hook(); out["synced_state"] = True
    except Exception: traceback.print_exc(); out["synced_state"] = False
    out["stale_marked"] = stale_caches()
    if os.environ.get("BN_REFRESH_WARM", "1") != "0":
        todo = []
        with _S["cv"]:
            for key, label, fn in WARM:
                if key in _S["inflight"]: out["sources"].append({"id": key, "label": label, "ok": None, "skipped": "still running"}); continue
                _S["inflight"].add(key); todo.append((key, label, fn))
        ex = ThreadPoolExecutor(max_workers=max(1, min(9, len(todo))), thread_name_prefix="bn-refresh")
        futs = {ex.submit(_one, key, fn): (key, label) for key, label, fn in todo}
        done, pending = wait(futs, timeout=budget_s())
        ex.shutdown(wait=False)
        for f in done: r = f.result(); r["label"] = futs[f][1]; out["sources"].append(r)
        for f in pending: out["sources"].append({"id": futs[f][0], "label": futs[f][1], "ok": None, "pending": True})
    out["took_s"] = round(time.time() - t0, 2)
    return out

def _scan_info():
    try:
        import server
        ls = server.state.get("last_scan")
        return {"last_scan": iso(ls) if ls else None}
    except Exception:
        return {}

def request(now=None):
    """Run one shared refresh, or join/reuse the current one. Thread-safe; at most one real run per window."""
    cv = _S["cv"]; w = window_s()
    with cv:
        _S["taps"] += 1
        now = now or time.time()
        if _S["busy"]:
            cv.wait_for(lambda: not _S["busy"], timeout=budget_s() + 10)
            if _S["result"]: return dict(_S["result"], coalesced=True, next_in_s=max(0, int(_S["started"] + w - time.time())))
        elif _S["result"] and now - _S["started"] < w:
            return dict(_S["result"], coalesced=True, next_in_s=max(0, int(_S["started"] + w - now)))
        _S["busy"] = True; _S["started"] = time.time()
    res = None
    try:
        res = run()
    except Exception:
        traceback.print_exc(); res = {"sources": [], "error": "refresh failed"}
    finally:
        with cv:
            fin = time.time()
            res = dict(res or {}, ok=True, refreshed_at=iso(fin), started_at=iso(_S["started"]), window_s=int(w), **_scan_info())
            _S["busy"] = False; _S["finished"] = fin; _S["result"] = res; _S["runs"] += 1
            cv.notify_all()
    return dict(res, coalesced=False, next_in_s=int(w))

def status():
    w = window_s(); r = _S["result"] or {}
    return {"enabled": enabled(), "busy": _S["busy"], "runs": _S["runs"], "window_s": int(w), "refreshed_at": r.get("refreshed_at"),
            "next_in_s": max(0, int(_S["started"] + w - time.time())) if _S["started"] else 0, **_scan_info()}

def handle_get(path, qs):
    if path != "/api/refresh-all" or not enabled(): return 404, {"error": "not found"}
    return 200, status()

def handle_post(path, data):
    if path != "/api/refresh-all" or not enabled(): return 404, {"error": "not found"}
    return 200, request()
