"""Background Noise add-on (tab "🔉 Background Noise", deep link #noise): every stored alert whose final displayed rank is 0-6.
No further filtering: The Wire (watchlist=0), Watchlist / unconfirmed (watchlist=1) and suppressed low-signal items (watchlist=2)
all come in automatically. Newest first (first_seen DESC), paged server-side so the tab stays fast.
Read-only: opens blackout.db with the sqlite URI file:blackout.db?mode=ro (blackout.db already reaches Render through the box->Render sync).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json or any write path."""
import os, sqlite3, json, sys, threading, time

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
STATIC = os.path.join(BASE, "bnoise_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
RMIN, RMAX = 0, 6
LIST = {0: "wire", 1: "watchlist", 2: "suppressed"}
TTL = 60

_C = getattr(sys, "_bn_noise_cache", None)
if _C is None: _C = sys._bn_noise_cache = {}
_LK = getattr(sys, "_bn_noise_lock", None)
if _LK is None: _LK = sys._bn_noise_lock = threading.Lock()

def _db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def _j(s):
    try: return json.loads(s or "[]")
    except Exception: return []

def _summary(c):
    st = c.execute("SELECT (SELECT MAX(id) FROM scans) s, (SELECT MAX(updated) FROM clusters) u").fetchone()
    key = (st["s"], st["u"])
    with _LK:
        hit = _C.get("sum")
        if hit and hit[0] == key and time.time() - hit[1] < TTL: return hit[2]
    by_rank = {str(r): 0 for r in range(RMIN, RMAX + 1)}
    by_list = {v: 0 for v in LIST.values()}
    for r in c.execute("SELECT rank, watchlist w, COUNT(*) n FROM clusters WHERE rank BETWEEN ? AND ? GROUP BY rank, w", (RMIN, RMAX)):
        by_rank[str(r["rank"])] = by_rank.get(str(r["rank"]), 0) + r["n"]
        k = LIST.get(r["w"], "suppressed"); by_list[k] = by_list.get(k, 0) + r["n"]
    a = c.execute("SELECT COUNT(*) n, MIN(rank) lo, MAX(rank) hi, MIN(first_seen) a, MAX(first_seen) b FROM clusters WHERE rank BETWEEN ? AND ?",
                  (RMIN, RMAX)).fetchone()
    s = {"total": a["n"], "rank_min": a["lo"], "rank_max": a["hi"], "oldest": a["a"], "newest": a["b"], "by_rank": by_rank, "by_list": by_list}
    with _LK: _C["sum"] = (key, time.time(), s)
    return s

def page(offset=0, limit=100, rank=None):
    c = _db()
    try:
        summ = _summary(c)
        where, args = "rank BETWEEN ? AND ?", [RMIN, RMAX]
        if rank is not None: where, args = "rank=?", [rank]
        narrowed = rank is not None
        n = c.execute(f"SELECT COUNT(*) n FROM clusters WHERE {where}", args).fetchone()["n"] if narrowed else summ["total"]
        rows = c.execute(f"""SELECT cluster_id, title, category, location, event_time, first_seen, updated, score, confidence, n_items, n_families,
                              families, links, watchlist, brief, rank FROM clusters WHERE {where}
                              ORDER BY first_seen DESC, cluster_id LIMIT ? OFFSET ?""", args + [limit, offset]).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d["families"] = _j(d["families"])
            d["links"] = [{"source": l.get("source", ""), "url": l.get("url", "")} for l in _j(d["links"])[:6] if isinstance(l, dict)]
            d["list"] = LIST.get(d["watchlist"], "suppressed")
            d["unconfirmed"] = d["watchlist"] != 0
            items.append(d)
        return {"rank_band": [RMIN, RMAX], "summary": summ, "matching": n, "offset": offset, "limit": limit, "rank_filter": rank,
                "items": items, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    finally:
        c.close()

def handle_get(path, qs):
    if path.startswith("/api/noise/"):
        name = path[len("/api/noise/"):]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
        return 404, {"error": "not found"}
    if path == "/api/noise":
        g = lambda k, d: ((qs.get(k) or [d])[0] or d)
        try:
            off = max(0, min(10_000_000, int(g("offset", "0")))); lim = max(1, min(200, int(g("limit", "100"))))
            rk = g("rank", "")
            rk = int(rk) if rk != "" else None
        except ValueError: return 400, {"error": "offset, limit and rank must be integers"}
        if rk is not None and not RMIN <= rk <= RMAX: return 400, {"error": "rank must be 0-6"}
        try: return 200, page(off, lim, rk)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    return 404, {"error": "not found"}
