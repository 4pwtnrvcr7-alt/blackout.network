"""Trends add-on (tab "📈 Trends", deep link #trends): historical charts of what the scanner has cataloged, plus archive backfill.
Read-only: opens blackout.db with the sqlite URI file:blackout.db?mode=ro and, if present, trends_history.db (mode=ro), which
trends_backfill.py builds on the box from public archive APIs (USGS, GDACS, EONET, WHO DON, CISA KEV, GFZ Kp, ...), scored with the
scanner's own code and flagged origin='archive backfill'. Backfill only covers the time BEFORE the live scanner's first story, so
nothing is counted twice; it never reaches The Wire, the alert bar, pushes or newsletters (only this module reads it).
Ranges up to 30 days come back as UTC hour buckets (the browser groups them into ET 6-hour / day buckets); 90 days, 1 year and All
come back as Eastern-Time day buckets. /api/trends/stream is a cursor-paginated (limit <= 100) newest-first list of stories for the
infinite-scroll stream. Answers are cached in memory and recomputed after a new scan or history rebuild (or after 120 s).
Never touches scanner.py, scoring, push.py, jets.py, config.json or any write path."""
import os, sqlite3, sys, threading, time, json, re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
HDB = os.path.join(BASE, "trends_history.db")
STATIC = os.path.join(BASE, "trends_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
RANGES = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "90d": 24 * 90, "1y": 24 * 365, "all": None}
DAY_RANGES = {"90d", "1y", "all"}
TTL = 120
WATCH = {0: "wire", 1: "watch", 2: "supp"}
ET = ZoneInfo("America/New_York")
GEO_MAX = 6000
STREAM_MAX = 100

_C = getattr(sys, "_bn_trends_cache", None)
if _C is None: _C = sys._bn_trends_cache = {}
_LK = getattr(sys, "_bn_trends_lock", None)
if _LK is None: _LK = sys._bn_trends_lock = threading.Lock()

def _iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def _pt(s):
    try: return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception: return None

def _db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def _hdb():
    if not os.path.exists(HDB): return None
    try:
        h = sqlite3.connect(f"file:{HDB}?mode=ro", uri=True, timeout=10); h.row_factory = sqlite3.Row
        h.execute("SELECT 1 FROM stories LIMIT 1"); return h
    except sqlite3.Error: return None

def _stamp(c):
    r = c.execute("SELECT (SELECT MAX(id) FROM scans) s, (SELECT MAX(updated) FROM clusters) u, (SELECT MAX(finished) FROM scans) f").fetchone()
    try: hm = os.path.getmtime(HDB)
    except OSError: hm = 0
    return (r["s"], r["u"], r["f"], hm)

def _hist_meta(h):
    if h is None: return {}, [], None
    meta = {r["k"]: r["v"] for r in h.execute("SELECT k, v FROM meta")}
    srcs = [dict(r) for r in h.execute("SELECT name, url, status, fetched, kept, earliest, latest, kept_earliest, note FROM sources ORDER BY kept DESC, name")]
    first = h.execute("SELECT MIN(t) a FROM stories").fetchone()["a"]
    return meta, srcs, first

def _build(c, h, rng):
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    live_first = c.execute("SELECT MIN(first_seen) a FROM clusters").fetchone()["a"]
    meta, hsrc, arch_first = _hist_meta(h)
    firsts = [x for x in (live_first, arch_first) if x]
    history_since = min(firsts) if firsts else None
    hours = RANGES[rng]
    req_start = (end - timedelta(hours=hours)) if hours else None
    hs = _pt(history_since).replace(minute=0, second=0) if history_since else end - timedelta(hours=24)
    start = max(req_start, hs) if req_start else hs                      # never draw empty pre-history as zeros
    day = rng in DAY_RANGES
    if day:   # Eastern-Time calendar days
        d0 = start.astimezone(ET).date(); d1 = (end - timedelta(seconds=1)).astimezone(ET).date()
        keys = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
        start = datetime(d0.year, d0.month, d0.day, tzinfo=ET).astimezone(timezone.utc)
        def kf(hkey):
            return datetime.strptime(hkey, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc).astimezone(ET).date().isoformat()
    else:
        nh = int((end - start).total_seconds() // 3600)
        keys = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(nh)]
        kf = lambda hkey: hkey
    cut = _iso(start)
    idx = {k: i for i, k in enumerate(keys)}; n = len(keys)
    z = lambda: [0] * n
    cats, by = {}, {"wire": z(), "watch": z(), "supp": z(), "archive": z()}
    sev = {"sum": z(), "n": z(), "max": [None] * n, "r7": z(), "r7_all": z(), "high": z()}
    def add(i, cat, k, cnt, s, mx, r7, hi, arch):
        by[k][i] += cnt
        if arch: by["archive"][i] += cnt
        cc = cats.setdefault(cat or "other", {"vis": z(), "supp": z(), "archive": z()})
        cc["supp" if k == "supp" else "vis"][i] += cnt
        if arch: cc["archive"][i] += cnt
        sev["r7_all"][i] += r7 or 0
        if k == "wire":
            sev["sum"][i] += s or 0; sev["n"][i] += cnt
            sev["max"][i] = max(sev["max"][i] or 0, mx or 0)
            sev["r7"][i] += r7 or 0; sev["high"][i] += hi or 0
    q = """SELECT substr({t},1,13) h, category, {w} w, COUNT(*) n, SUM(score) s, MAX(score) mx, SUM(rank>=7) r7, SUM(score>=60) hi
           FROM {tb} WHERE {t}>=? GROUP BY h, category, w"""
    for r in c.execute(q.format(t="first_seen", w="watchlist", tb="clusters"), (cut,)):
        i = idx.get(kf(r["h"]))
        if i is not None: add(i, r["category"], WATCH.get(r["w"], "supp"), r["n"], r["s"], r["mx"], r["r7"], r["hi"], False)
    if h is not None:
        for r in h.execute(q.format(t="t", w="watchlist", tb="stories"), (cut,)):
            i = idx.get(kf(r["h"]))
            if i is not None: add(i, r["category"], WATCH.get(r["w"], "supp"), r["n"], r["s"], r["mx"], r["r7"], r["hi"], True)
    scans = [dict(r) for r in c.execute("""SELECT id, started, finished, trigger, fetched, new_items, ok_sources, failed_sources,
                                           CASE WHEN error IS NULL OR error='' THEN 0 ELSE 1 END err FROM scans WHERE started>=? ORDER BY id""", (cut,))]
    if len(scans) > 1500: scans = scans[-1500:]
    first_scan = c.execute("SELECT MIN(started) a FROM scans").fetchone()["a"]
    raw = c.execute("SELECT COUNT(*) n FROM alerts WHERE first_seen>=?", (cut,)).fetchone()["n"]
    hist_h = round((now - _pt(history_since)).total_seconds() / 3600, 1) if history_since else 0.0
    health = [dict(r) for r in c.execute("SELECT name, ok, items FROM source_health")]
    # geographic heat map: located stories in range, 1-degree grid (live: Wire + Watchlist; archive: all, all official)
    grid = {}
    def gadd(lat, lon, cnt, rk, arch):
        if lat is None or lon is None: return
        k = (round(lat), round(lon)); g = grid.setdefault(k, [0, 0, 0])
        g[0] += cnt; g[1] = max(g[1], rk or 0); g[2] += cnt if arch else 0
    for r in c.execute("""SELECT ROUND(lat) la, ROUND(lon) lo, COUNT(*) n, MAX(rank) rk FROM clusters WHERE first_seen>=? AND watchlist IN (0,1)
                          AND lat IS NOT NULL AND lon IS NOT NULL GROUP BY la, lo""", (cut,)): gadd(r["la"], r["lo"], r["n"], r["rk"], False)
    geo_first_live = c.execute("SELECT MIN(first_seen) a FROM clusters WHERE lat IS NOT NULL AND watchlist IN (0,1)").fetchone()["a"]
    geo_first_arch = None
    if h is not None:
        for r in h.execute("""SELECT ROUND(lat) la, ROUND(lon) lo, COUNT(*) n, MAX(rank) rk FROM stories WHERE t>=? AND lat IS NOT NULL AND lon IS NOT NULL
                              GROUP BY la, lo""", (cut,)): gadd(r["la"], r["lo"], r["n"], r["rk"], True)
        geo_first_arch = h.execute("SELECT MIN(t) a FROM stories WHERE lat IS NOT NULL").fetchone()["a"]
    geo = sorted(([k[0], k[1], v[0], v[1], v[2]] for k, v in grid.items()), key=lambda x: -x[2])[:GEO_MAX]
    # earliest date per category / graph
    cov = {}
    for r in c.execute("SELECT category, MIN(first_seen) a, COUNT(*) n FROM clusters GROUP BY category"):
        cov.setdefault(r["category"] or "other", {})["live_since"] = r["a"]; cov[r["category"] or "other"]["live_n"] = r["n"]
    if h is not None:
        for r in h.execute("SELECT category, MIN(t) a, COUNT(*) n FROM stories GROUP BY category"):
            cov.setdefault(r["category"] or "other", {})["archive_since"] = r["a"]; cov[r["category"] or "other"]["archive_n"] = r["n"]
    for v in cov.values(): v["since"] = min(x for x in (v.get("live_since"), v.get("archive_since")) if x)
    graphs = {"volume": history_since, "severity": history_since, "wire_watch": history_since,
              "geo": min([x for x in (geo_first_live, geo_first_arch) if x] or [None]) if (geo_first_live or geo_first_arch) else None,
              "scans": first_scan, "stream": history_since}
    return {"bucket": "day" if day else "hour", "hours": keys, "start": cut, "end": _iso(end), "range_hours": hours, "categories": cats, "by_list": by,
            "severity": sev, "scans": scans, "raw_items": raw, "history_since": history_since, "live_since": live_first, "archive_since": arch_first,
            "seam": meta.get("seam") or live_first, "first_scan": first_scan, "history_hours": hist_h,
            "partial": bool(req_start is None or (history_since and _pt(history_since) > req_start)),
            "sources_ok": sum(1 for x in health if x["ok"] == 1), "sources_failed": sum(1 for x in health if x["ok"] == 0), "sources_total": len(health),
            "high_threshold": 60, "geo": geo, "coverage": {"categories": cov, "graphs": graphs, "archive_sources": hsrc,
            "archive_built": meta.get("built"), "archive_method": meta.get("method")}}

def report(rng, force=False):
    c = _db(); h = _hdb()
    try:
        st = _stamp(c)
        key = (rng,)
        with _LK:
            hit = _C.get(key)
            if hit and not force and hit[1] == st and time.time() - hit[0] < TTL:
                out = dict(hit[2]); out["cached"] = True; return out
        t0 = time.time()
        data = _build(c, h, rng)
    finally:
        c.close()
        if h is not None: h.close()
    data.update(range=rng, generated=_iso(datetime.now(timezone.utc)), last_scan_id=st[0], last_scan_finished=st[2],
                compute_ms=round((time.time() - t0) * 1000), cached=False)
    with _LK: _C[key] = (time.time(), st, data)
    return data

# ---------------------------------------------------------------- infinite-scroll stream
_CUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z(\|[A-Za-z0-9_.:\-]{1,80})?$")
def _links(js):
    try: L = json.loads(js or "[]")
    except Exception: return []
    out = []
    for x in L:
        u = (x or {}).get("url") or ""
        if re.match(r"^https?://", u): out.append({"source": str(x.get("source") or "")[:60], "url": u[:500]})
        if len(out) >= 3: break
    return out

def stream(before=None, limit=50, cat=None, origin=None):
    limit = max(1, min(STREAM_MAX, int(limit)))
    bt, bid = (before.split("|", 1) + [""])[:2] if before else ("9999-12-31T23:59:59Z", "~")
    if before and "|" not in before: bid = "~"
    out = []
    c = _db(); h = _hdb()
    try:
        cw = " AND category=?" if cat else ""
        args = [bt, bt, bid] + ([cat] if cat else []) + [limit]
        if origin in (None, "", "live"):
            for r in c.execute(f"""SELECT cluster_id id, first_seen t, event_time, title, category, location, score, rank, confidence, watchlist, n_items,
                                   n_families, links FROM clusters WHERE watchlist IN (0,1) AND (first_seen<? OR (first_seen=? AND cluster_id<?)){cw}
                                   ORDER BY first_seen DESC, cluster_id DESC LIMIT ?""", args):
                out.append({"id": r["id"], "t": r["t"], "event_time": r["event_time"], "title": r["title"], "category": r["category"] or "other",
                            "location": r["location"], "score": r["score"], "rank": r["rank"], "confidence": r["confidence"],
                            "list": "watch" if r["watchlist"] == 1 else "wire", "n_items": r["n_items"], "sources_n": r["n_families"],
                            "links": _links(r["links"]), "origin": "live"})
        if h is not None and origin in (None, "", "archive"):
            for r in h.execute(f"""SELECT id, t, title, category, location, score, rank, confidence, watchlist, n_items, families, links FROM stories
                                  WHERE (t<? OR (t=? AND id<?)){cw} ORDER BY t DESC, id DESC LIMIT ?""", args):
                try: nf = len(json.loads(r["families"] or "[]"))
                except Exception: nf = 1
                out.append({"id": r["id"], "t": r["t"], "event_time": r["t"], "title": r["title"], "category": r["category"] or "other",
                            "location": r["location"], "score": r["score"], "rank": r["rank"], "confidence": r["confidence"],
                            "list": "watch" if r["watchlist"] == 1 else "wire", "n_items": r["n_items"], "sources_n": nf,
                            "links": _links(r["links"]), "origin": "archive backfill"})
    finally:
        c.close()
        if h is not None: h.close()
    out.sort(key=lambda x: (x["t"] or "", x["id"]), reverse=True)
    page = out[:limit]
    more = len(out) > limit or len(page) == limit
    nxt = f"{page[-1]['t']}|{page[-1]['id']}" if page and more else None
    return {"items": page, "next": nxt, "limit": limit, "end": nxt is None}

def handle_get(path, qs):
    if path == "/api/trends/stream":
        g = lambda k, d=None: ((qs.get(k) or [d])[0] or d)
        before = g("before")
        if before and not _CUR.match(before): return 400, {"error": "before must be a cursor from a previous page"}
        try: lim = int(g("limit", "50"))
        except ValueError: return 400, {"error": "limit must be a number"}
        if lim < 1 or lim > STREAM_MAX: return 400, {"error": f"limit must be 1..{STREAM_MAX}"}
        cat = g("cat")
        if cat and (len(cat) > 40 or not re.match(r"^[a-z/ ]+$", cat)): return 400, {"error": "bad category"}
        origin = g("origin")
        if origin not in (None, "live", "archive"): return 400, {"error": "origin must be live or archive"}
        try: return 200, stream(before, lim, cat, origin)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    if path.startswith("/api/trends/"):
        name = path[len("/api/trends/"):]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
        return 404, {"error": "not found"}
    if path == "/api/trends":
        rng = ((qs.get("range") or ["7d"])[0] or "7d")
        if rng not in RANGES: return 400, {"error": "range must be 24h, 7d, 30d, 90d, 1y or all"}
        try: return 200, report(rng)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    return 404, {"error": "not found"}
