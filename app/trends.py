"""Trends add-on (tab "📈 Trends", deep link #trends): historical charts of what the scanner has cataloged.
Read-only: opens blackout.db with the sqlite URI file:blackout.db?mode=ro, aggregates server-side into UTC hour buckets
(the browser rolls hours up into ET 6-hour / day buckets and draws them with the dashboard's existing Chart.js).
Answers are cached in memory and recomputed when a new scan lands (max scans.id / clusters.updated change) or after 120 s.
Never touches scanner.py, scoring, push.py, jets.py, config.json or any write path."""
import os, sqlite3, sys, threading, time
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
STATIC = os.path.join(BASE, "trends_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
RANGES = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
TTL = 120
WATCH = {0: "wire", 1: "watch", 2: "supp"}

_C = getattr(sys, "_bn_trends_cache", None)
if _C is None: _C = sys._bn_trends_cache = {}
_LK = getattr(sys, "_bn_trends_lock", None)
if _LK is None: _LK = sys._bn_trends_lock = threading.Lock()

def _iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")

def _db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def _stamp(c):
    r = c.execute("SELECT (SELECT MAX(id) FROM scans) s, (SELECT MAX(updated) FROM clusters) u, (SELECT MAX(finished) FROM scans) f").fetchone()
    return (r["s"], r["u"], r["f"])

def _build(c, hours):
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(hours=hours)
    cut = _iso(start)
    hrs = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(hours)]
    idx = {h: i for i, h in enumerate(hrs)}
    z = lambda: [0] * hours
    cats, by = {}, {"wire": z(), "watch": z(), "supp": z()}
    sev = {"sum": z(), "n": z(), "max": [None] * hours, "r7": z(), "r7_all": z(), "high": z()}
    # stories (clusters) by the hour the scanner first saw them; score/rank are each story's current values
    for r in c.execute("""SELECT substr(first_seen,1,13) h, category, watchlist w, COUNT(*) n, SUM(score) s, MAX(score) mx,
                          SUM(rank>=7) r7, SUM(score>=60) hi FROM clusters WHERE first_seen>=? GROUP BY h, category, w""", (cut,)):
        i = idx.get(r["h"])
        if i is None: continue
        k = WATCH.get(r["w"], "supp")
        by[k][i] += r["n"]
        cat = r["category"] or "other"
        cc = cats.setdefault(cat, {"vis": z(), "supp": z()})
        cc["supp" if k == "supp" else "vis"][i] += r["n"]
        sev["r7_all"][i] += r["r7"] or 0
        if k == "wire":
            sev["sum"][i] += r["s"] or 0; sev["n"][i] += r["n"]
            sev["max"][i] = max(sev["max"][i] or 0, r["mx"] or 0)
            sev["r7"][i] += r["r7"] or 0; sev["high"][i] += r["hi"] or 0
    scans = [dict(r) for r in c.execute("""SELECT id, started, finished, trigger, fetched, new_items, ok_sources, failed_sources,
                                           CASE WHEN error IS NULL OR error='' THEN 0 ELSE 1 END err FROM scans WHERE started>=? ORDER BY id""", (cut,))]
    first = c.execute("SELECT MIN(first_seen) a FROM clusters").fetchone()["a"]
    first_scan = c.execute("SELECT MIN(started) a FROM scans").fetchone()["a"]
    raw = c.execute("SELECT COUNT(*) n FROM alerts WHERE first_seen>=?", (cut,)).fetchone()["n"]
    hist_h = 0.0
    if first:
        try: hist_h = round((now - datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
        except Exception: pass
    health = [dict(r) for r in c.execute("SELECT name, ok, items, last_checked FROM source_health ORDER BY name")]
    return {"hours": hrs, "start": cut, "end": _iso(end), "range_hours": hours, "categories": cats, "by_list": by, "severity": sev,
            "scans": scans, "raw_items": raw, "history_since": first, "first_scan": first_scan, "history_hours": hist_h,
            "partial": hist_h < hours, "sources_ok": sum(1 for h in health if h["ok"] == 1), "sources_failed": sum(1 for h in health if h["ok"] == 0),
            "sources_total": len(health), "high_threshold": 60}

def report(rng, force=False):
    hours = RANGES.get(rng, RANGES["7d"])
    c = _db()
    try:
        st = _stamp(c)
        key = (rng,)
        with _LK:
            hit = _C.get(key)
            if hit and not force and hit[1] == st and time.time() - hit[0] < TTL:
                out = dict(hit[2]); out["cached"] = True; return out
        t0 = time.time()
        data = _build(c, hours)
    finally:
        c.close()
    data.update(range=rng, generated=_iso(datetime.now(timezone.utc)), last_scan_id=st[0], last_scan_finished=st[2],
                compute_ms=round((time.time() - t0) * 1000), cached=False)
    with _LK: _C[key] = (time.time(), st, data)
    return data

def handle_get(path, qs):
    if path.startswith("/api/trends/"):
        name = path[len("/api/trends/"):]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
        return 404, {"error": "not found"}
    if path == "/api/trends":
        rng = ((qs.get("range") or ["7d"])[0] or "7d")
        if rng not in RANGES: return 400, {"error": "range must be 24h, 7d or 30d"}
        try: return 200, report(rng)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    return 404, {"error": "not found"}
