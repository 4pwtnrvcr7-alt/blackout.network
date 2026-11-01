"""Wire history (t246): a scrollable, cursor-paginated timeline on The Wire tab that merges
  (a) every stored scanner story in blackout.db (clusters; opened read-only with file:blackout.db?mode=ro), and
  (b) real archived source items from trends_history.db (built on the box by trends_backfill.py / t226 from public archive APIs:
      USGS FDSN, GDACS event API, NASA EONET, WHO DON API, CISA KEV, GFZ Kp, NOAA SWPC alerts, NWS, CIDRAP, CISA advisories,
      ReliefWeb RSS). Opened read-only too; this module never fetches anything and never writes any database.
Archive items are returned with archive=true and origin='archive backfill'. They exist only in trends_history.db, which the live
Wire (/api/state), alert bar, briefs, push notifications and newsletters never read, so they can't reach those surfaces.
Archive ranks were computed by t226 with the scanner's own scoring code (scanner.rebuild_cluster/rank_cluster on a scratch DB), so
they use the same 0-10 display scale; they are labelled 'archive rank' and never feed live alerting.
Endpoints: /api/wire_history?before=<cursor>&limit=<1..100>&cats=a,b&lists=wire,watch,bg&archive=1|0|only, /api/wire_history/meta,
/api/wire_history/app.js|app.css. Never touches scanner.py, scoring, push.py, jets.py or config.json."""
import os, re, json, sqlite3, time, threading
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db"); HDB = os.path.join(BASE, "trends_history.db")
STATIC = os.path.join(BASE, "wire_history_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
MAXL = 100
LISTS = {"wire": 0, "watch": 1, "bg": 2}
_CUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z(\|[A-Za-z0-9_.:\-|]{1,120})?$")
_CAT = re.compile(r"^[a-z/ ]{1,40}$")
_M = {"t": 0, "key": None, "data": None}; _LK = threading.Lock()

def _ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c
def _hdb():
    if not os.path.exists(HDB): return None
    try:
        h = _ro(HDB); h.execute("SELECT 1 FROM stories LIMIT 1"); return h
    except sqlite3.Error: return None
def _j(s, d):
    try: return json.loads(s or "") if s else d
    except Exception: return d
def _links(js):
    out = []
    for x in _j(js, []):
        u = (x or {}).get("url") or ""
        if re.match(r"^https?://", u): out.append({"source": str(x.get("source") or "")[:60], "url": u[:500]})
        if len(out) >= 4: break
    return out

def page(before=None, limit=50, cats=None, lists=(0, 1), archive="1"):
    limit = max(1, min(MAXL, int(limit)))
    if before:
        bt, _, bid = before.partition("|"); bid = bid or "~"
    else: bt, bid = "9999-12-31T23:59:59Z", "~"
    cw = (" AND category IN (%s)" % ",".join("?" * len(cats))) if cats else ""
    lw = " AND watchlist IN (%s)" % ",".join("?" * len(lists))
    args = [bt, bt, bid] + list(cats or []) + list(lists) + [limit + 1]
    out = []
    if archive != "only":
        c = _ro(DB)
        try:
            for r in c.execute(f"""SELECT cluster_id id, first_seen t, event_time, title, category, location, score, rank, confidence, watchlist,
                                  n_items, n_families, families, links FROM clusters WHERE (first_seen<? OR (first_seen=? AND cluster_id<?)){cw}{lw}
                                  ORDER BY first_seen DESC, cluster_id DESC LIMIT ?""", args):
                out.append({"id": r["id"], "t": r["t"], "event_time": r["event_time"], "title": r["title"], "category": r["category"] or "other",
                            "location": r["location"], "score": r["score"], "rank": r["rank"], "confidence": r["confidence"], "watchlist": r["watchlist"],
                            "n_items": r["n_items"], "families": _j(r["families"], [])[:6], "links": _links(r["links"]), "archive": False, "origin": "live scanner"})
        finally: c.close()
    h = _hdb() if archive in ("1", "only") else None
    if h is not None:
        try:
            for r in h.execute(f"""SELECT id, t, title, category, location, score, rank, confidence, watchlist, n_items, families, links, sources
                                  FROM stories WHERE (t<? OR (t=? AND id<?)){cw}{lw} ORDER BY t DESC, id DESC LIMIT ?""", args):
                out.append({"id": r["id"], "t": r["t"], "event_time": r["t"], "title": r["title"], "category": r["category"] or "other",
                            "location": r["location"], "score": r["score"], "rank": r["rank"], "confidence": r["confidence"], "watchlist": r["watchlist"],
                            "n_items": r["n_items"], "families": _j(r["families"], [])[:6], "sources": _j(r["sources"], [])[:4],
                            "links": _links(r["links"]), "archive": True, "origin": "archive backfill"})
        finally: h.close()
    out.sort(key=lambda x: (x["t"] or "", x["id"]), reverse=True)
    more = len(out) > limit
    pg = out[:limit]
    nxt = f"{pg[-1]['t']}|{pg[-1]['id']}" if pg and more else None
    return {"items": pg, "next": nxt, "end": nxt is None, "limit": limit}

def _stamp():
    try: a = os.path.getmtime(DB)
    except OSError: a = 0
    try: b = os.path.getmtime(HDB)
    except OSError: b = 0
    return (a, b)

def meta():
    st = _stamp()
    with _LK:
        if _M["data"] and _M["key"] == st and time.time() - _M["t"] < 300: return _M["data"]
    c = _ro(DB)
    try:
        lv = c.execute("SELECT COUNT(*) n, MIN(first_seen) a, MAX(first_seen) b, SUM(watchlist=0) w, SUM(watchlist=1) wl, SUM(watchlist=2) bg FROM clusters").fetchone()
        cats = {r["category"] or "other": r["n"] for r in c.execute("SELECT category, COUNT(*) n FROM clusters GROUP BY category")}
        lsrc = [{"name": r["source"], "earliest": r["a"], "items": r["n"]} for r in
                c.execute("SELECT source, MIN(first_seen) a, COUNT(*) n FROM alerts GROUP BY source ORDER BY a, source")]
        first_scan = c.execute("SELECT MIN(started) FROM scans").fetchone()[0]
    finally: c.close()
    out = {"live": {"stories": lv["n"], "wire": lv["w"] or 0, "watch": lv["wl"] or 0, "bg": lv["bg"] or 0, "earliest": lv["a"], "latest": lv["b"],
                    "first_scan": first_scan, "sources": lsrc},
           "archive": None, "categories": dict(cats)}
    h = _hdb()
    if h is not None:
        try:
            m = {r["k"]: r["v"] for r in h.execute("SELECT k, v FROM meta")}
            ar = h.execute("SELECT COUNT(*) n, MIN(t) a, MAX(t) b, SUM(watchlist=0) w, SUM(watchlist=1) wl, SUM(watchlist=2) bg FROM stories").fetchone()
            for r in h.execute("SELECT category, COUNT(*) n FROM stories GROUP BY category"):
                k = r["category"] or "other"; out["categories"][k] = out["categories"].get(k, 0) + r["n"]
            srcs = [dict(r) for r in h.execute("SELECT name, url, status, fetched, kept, kept_earliest earliest, note FROM sources ORDER BY (kept_earliest IS NULL), kept_earliest, name")]
            out["archive"] = {"stories": ar["n"], "wire": ar["w"] or 0, "watch": ar["wl"] or 0, "bg": ar["bg"] or 0, "earliest": ar["a"], "latest": ar["b"],
                              "seam": m.get("seam"), "built": m.get("built"), "method": m.get("method"), "items": m.get("items"), "sources": srcs,
                              "db_bytes": os.path.getsize(HDB)}
        finally: h.close()
    e = [x for x in (out["live"]["earliest"], (out["archive"] or {}).get("earliest")) if x]
    out["earliest"] = min(e) if e else None
    with _LK: _M.update(t=time.time(), key=st, data=out)
    return out

def handle_get(path, qs):
    if path.startswith("/api/wire_history/"):
        n = path[len("/api/wire_history/"):]
        if n in FILES:
            with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
        if n == "meta":
            try: return 200, meta()
            except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
        return 404, {"error": "not found"}
    if path == "/api/wire_history":
        g = lambda k, d=None: ((qs.get(k) or [d])[0] or d)
        before = g("before")
        if before and not _CUR.match(before): return 400, {"error": "before must be an ISO UTC time like 2025-06-01T00:00:00Z or a cursor"}
        try: lim = int(g("limit", "50"))
        except ValueError: return 400, {"error": "limit must be a number"}
        if not 1 <= lim <= MAXL: return 400, {"error": f"limit must be 1..{MAXL}"}
        cats = [x for x in (g("cats", "") or "").split(",") if x][:20]
        if any(not _CAT.match(x) for x in cats): return 400, {"error": "bad category"}
        ls = [x for x in (g("lists", "wire,watch") or "").split(",") if x]
        if not ls or any(x not in LISTS for x in ls): return 400, {"error": "lists must be wire, watch and/or bg"}
        arch = g("archive", "1")
        if arch not in ("0", "1", "only"): return 400, {"error": "archive must be 0, 1 or only"}
        try: return 200, page(before, lim, cats, [LISTS[x] for x in ls], arch)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
    return 404, {"error": "not found"}
