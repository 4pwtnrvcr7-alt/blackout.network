"""Regional Heat Map add-on (tab "Heat Map"). Read-only against blackout.db (mode=ro); geolocation lives in geo.db (see geo.py).
Routes: /api/heatmap (data; ?run=1 runs a quick offline geocoding pass first), /api/heatmap/<static file>, /api/heatmap/unlocated.csv, /api/heatmap/geo.csv.
A background worker (one thread, guarded across hot reloads) geocodes new alerts and backfills the last 7 days every 5 minutes,
and is woken early by each dashboard refresh. Nothing here changes scores, ranks or the scanner."""
import os, sys, json, time, threading, importlib, sqlite3, csv, io
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path: sys.path.insert(0, BASE)
import geo
_geo_mt = [os.path.getmtime(os.path.join(BASE, "geo.py"))]
def G():
    """Hot-reload geo.py when it changes (the add-on loader only watches heatmap.py itself)."""
    global geo
    mt = os.path.getmtime(os.path.join(BASE, "geo.py"))
    if mt != _geo_mt[0] and not geo.STATUS.get("running"):
        geo = importlib.reload(geo); _geo_mt[0] = mt
    return geo

STATIC = os.path.join(BASE, "heatmap_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css", "leaflet-heat.js": "application/javascript", "leaflet.markercluster.js": "application/javascript",
         "MarkerCluster.css": "text/css", "MarkerCluster.Default.css": "text/css", "admin0.geojson": "application/json", "admin1.geojson": "application/json"}
INTERVAL = 300
GROUP = {"war/conflict": "violence", "disease": "disease", "natural disaster": "infra", "space weather": "infra", "cyber": "cyber", "political": "unrest"}

def _wake():
    w = getattr(sys, "_bn_heatmap_wake", None)
    if w is None: w = threading.Event(); sys._bn_heatmap_wake = w
    return w

def _loop():
    time.sleep(15)
    while True:
        try:
            mod = sys.modules.get("heatmap") or sys.modules.get(__name__)
            g = mod.G(); st = g.STATUS; st["next_at"] = None
            g.run("worker" if not _wake().is_set() else "dashboard refresh")
        except Exception as ex: print("heatmap geocoder:", ex, flush=True)
        _wake().clear()
        try: (sys.modules.get("heatmap") or sys.modules.get(__name__)).G().STATUS["next_at"] = time.time() + INTERVAL
        except Exception: pass
        _wake().wait(INTERVAL)

def _ensure_worker():
    if any(t.name == "heatmap_geocoder" and t.is_alive() for t in threading.enumerate()): return
    threading.Thread(target=_loop, name="heatmap_geocoder", daemon=True).start()
_ensure_worker()

def et(s):
    if not s: return None
    try: d = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception: return s
    try:
        from zoneinfo import ZoneInfo
        x = d.astimezone(ZoneInfo("America/New_York")); return x.strftime("%b %-d, %-I:%M %p ") + x.tzname()
    except Exception: return s

def data():
    g = G()
    b = sqlite3.connect(g.BDB, uri=True, timeout=30); b.row_factory = sqlite3.Row
    cut = g.iso(g.now() - timedelta(days=g.WINDOW_DAYS))
    cls = [dict(r) for r in b.execute("""SELECT cluster_id, title, category, score, rank, confidence, watchlist, links, n_items, n_families, eff_families,
            event_time, first_seen, updated FROM clusters WHERE watchlist IN (0,1) AND (COALESCE(event_time, first_seen)>=? OR first_seen>=?)""", (cut, cut))]
    b.close()
    with g._lock:
        c = g.gdb()
        geo_rows = {r["id"]: dict(r) for r in c.execute("SELECT * FROM geo")}
        last = c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        last_work = c.execute("SELECT * FROM runs WHERE geocoded>0 ORDER BY id DESC LIMIT 1").fetchone()
        nom_n = c.execute("SELECT COUNT(*) FROM nominatim_cache").fetchone()[0]
        nom_calls = c.execute("SELECT COALESCE(SUM(nominatim_calls),0) FROM runs").fetchone()[0]
        c.close()
    items, unl = [], []
    for cl in cls:
        r = geo_rows.get(cl["cluster_id"])
        try: links = json.loads(cl["links"] or "[]")
        except Exception: links = []
        t = cl["event_time"] or cl["first_seen"]
        if cl["first_seen"] and t and t > cl["first_seen"]: t = cl["first_seen"]
        base = {"id": cl["cluster_id"], "t": t, "title": (cl["title"] or "").replace("\n", " ")[:260], "cat": cl["category"], "grp": GROUP.get(cl["category"], "other"),
                "rank": cl["rank"] or 0, "score": cl["score"] or 0, "conf": cl["confidence"], "watch": cl["watchlist"], "n": cl["n_items"], "fam": cl["eff_families"] or cl["n_families"],
                "links": [{"s": l.get("source"), "u": l.get("url")} for l in links[:5]], "nlinks": len(links)}
        if r and r["located"]:
            base.update(lat=r["lat"], lon=r["lon"], prec=r["precision"], place=r["place"], cc=r["country"], cn=r["country_name"], a1=r["admin1_code"], a1n=r["admin1"],
                        city=r["city"], m=r["method"], md=r["method_detail"], gc=r["confidence"], ev=r["evidence"], gat=r["geocoded_at"])
            items.append(base)
        else:
            base.update(rc=(r or {}).get("reason_code") or "pending", reason=(r or {}).get("reason_unlocated") or "Not geocoded yet (new alert, next pass)",
                        cands=json.loads(r["candidates"]) if r and r.get("candidates") else None, gat=(r or {}).get("geocoded_at"))
            unl.append(base)
    tot = len(items) + len(unl)
    def cnt(L, k):
        o = {}
        for x in L: o[x.get(k)] = o.get(x.get(k), 0) + 1
        return dict(sorted(o.items(), key=lambda kv: -kv[1]))
    st = g.STATUS
    nxt = st.get("next_at")
    return {"generated": g.iso(g.now()), "generated_et": et(g.iso(g.now())), "window_days": g.WINDOW_DAYS,
            "coverage": {"total": tot, "located": len(items), "unlocated": len(unl), "pct": round(100 * len(items) / tot, 1) if tot else 0,
                         "by_method": cnt(items, "m"), "by_precision": cnt(items, "prec"), "by_gconf": cnt(items, "gc"), "by_reason": cnt(unl, "rc")},
            "labels": {"method": g.METHOD_LABEL, "reason": g.REASON_LABEL},
            "worker": {"running": st.get("running"), "last_run_et": et(last["finished"]) if last else None, "last_trigger": last["trigger"] if last else None,
                       "last_work_et": et(last_work["finished"]) if last_work else None, "next_in_s": max(0, int(nxt - time.time())) if nxt else None,
                       "interval_s": INTERVAL, "nominatim_cached": nom_n, "nominatim_calls_total": nom_calls, "gazetteer_load_s": g._GAZ[0].load_s if g._GAZ[0] else None},
            "items": items, "unlocated": unl}

def handle_get(path, qs):
    if path.startswith("/api/heatmap/"):
        name = path[len("/api/heatmap/"):]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
        if name in ("unlocated.csv", "geo.csv"):
            d = data(); buf = io.StringIO(); w = csv.writer(buf)
            if name == "unlocated.csv":
                w.writerow(["cluster_id", "time_utc", "category", "rank", "title", "reason_code", "reason", "candidates"])
                for x in d["unlocated"]: w.writerow([x["id"], x["t"], x["cat"], x["rank"], x["title"], x["rc"], x["reason"], "; ".join(x["cands"] or [])])
            else:
                w.writerow(["cluster_id", "time_utc", "category", "rank", "title", "lat", "lon", "precision", "place", "country", "admin1", "city", "method", "method_detail", "geo_confidence"])
                for x in d["items"]: w.writerow([x["id"], x["t"], x["cat"], x["rank"], x["title"], x["lat"], x["lon"], x["prec"], x["place"], x["cc"], x["a1n"], x["city"], x["m"], x["md"], x["gc"]])
            return 200, buf.getvalue(), "text/csv"
        return 404, {"error": "not found"}
    if path == "/api/heatmap":
        ran = None
        if (qs.get("run") or ["0"])[0] == "1":
            g = G()
            if not g.STATUS.get("running"): ran = g.run("dashboard refresh (offline pass)", nom_budget=0, max_seconds=20)
            _wake().set()     # let the worker do the online (Nominatim) part right away
        d = data(); d["quick_pass"] = ran
        return 200, d
    return 404, {"error": "not found"}
