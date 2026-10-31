"""User threat-level votes (0-10). Separate votes.db; never touches blackout.db scores, ranks or The Wire's ordering.
No accounts: each browser sends a random anonymous voter id (localStorage). One vote per item per voter (re-voting updates it).
Per-IP rate limiting is in memory only; IPs are never written to disk or logs."""
import json, os, re, sqlite3, threading, time
from datetime import datetime, timezone, timedelta
BASE = os.path.dirname(os.path.abspath(__file__)); VDB = os.path.join(BASE, "votes.db")
TYPES = ("cluster", "arc", "bcast", "stream"); C_PRIOR = 3
_rl = {}; _lock = threading.Lock()
def db():
    c = sqlite3.connect(VDB, timeout=20); c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS votes(item_type TEXT, item_id TEXT, voter TEXT, rating INTEGER, ts TEXT, title TEXT, url TEXT,
                 PRIMARY KEY(item_type, item_id, voter))"""); c.execute("CREATE INDEX IF NOT EXISTS ix_v_ts ON votes(ts)"); return c
def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def limited(ip):
    t = time.time()
    with _lock:
        h = [x for x in _rl.get(ip, []) if t - x < 60]; _rl[ip] = h
        if len(h) >= 30: return True
        h.append(t); return False
def clean(s, n): return re.sub(r"[\x00-\x1f]", " ", str(s or ""))[:n].strip()
def cluster_meta(ids):
    if not ids: return {}
    c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row
    try: return {r["cluster_id"]: dict(r) for r in c.execute(f"SELECT cluster_id,title,score,rank,links,watchlist,first_seen,category FROM clusters WHERE cluster_id IN ({','.join('?'*len(ids))})", list(ids))}
    finally: c.close()
def agg(c, typ, ids, voter=None):
    out = {}
    for i in ids:
        r = c.execute("SELECT COUNT(*) n, AVG(rating) a FROM votes WHERE item_type=? AND item_id=?", (typ, i)).fetchone()
        m = c.execute("SELECT rating FROM votes WHERE item_type=? AND item_id=? AND voter=?", (typ, i, voter)).fetchone() if voter else None
        out[i] = {"n": r["n"], "avg": round(r["a"], 1) if r["a"] is not None else None, "mine": m["rating"] if m else None}
    return out
def handle_post(path, d, ip=None):
    if path != "/api/vote": return 404, {"error": "not found"}
    typ = d.get("item_type"); iid = str(d.get("item_id") or ""); voter = str(d.get("voter") or "")
    try: rating = int(d.get("rating"))
    except Exception: rating = None
    if typ not in TYPES: return 400, {"error": f"item_type must be one of {TYPES}"}
    if not re.fullmatch(r"[A-Za-z0-9_:\-]{1,80}", iid): return 400, {"error": "bad item_id"}
    if not re.fullmatch(r"[a-f0-9]{32}", voter): return 400, {"error": "bad voter id"}
    if rating is None or not 0 <= rating <= 10: return 400, {"error": "rating must be an integer 0-10"}
    if limited(ip or "?"): return 429, {"error": "too many votes, slow down"}
    title, url = clean(d.get("title"), 300), clean(d.get("url"), 600)
    if typ == "cluster":
        m = cluster_meta([iid]).get(iid)
        if not m: return 404, {"error": "unknown item"}
        title = m["title"]; url = (json.loads(m["links"] or "[]") or [{}])[0].get("url", "")
    if url and not re.match(r"https?://", url): url = ""
    c = db()
    try:
        c.execute("INSERT INTO votes VALUES(?,?,?,?,?,?,?) ON CONFLICT(item_type,item_id,voter) DO UPDATE SET rating=excluded.rating, ts=excluded.ts", (typ, iid, voter, rating, iso(), title, url))
        c.commit(); a = agg(c, typ, [iid], voter)[iid]
    finally: c.close()
    try:
        import builtins
        if getattr(builtins, "_bn_live", None):
            import livepush; livepush.broadcast("vote", {"item_type": typ, "item_id": iid, "rating": rating, "title": title[:140], "avg": a["avg"], "n": a["n"], "ts": iso()})
    except Exception: pass
    return 200, {"status": "ok", **a}
def ranked(qs):
    win = (qs.get("window") or ["7d"])[0]; mn = max(1, int((qs.get("min") or ["1"])[0] or 1)); sort = (qs.get("sort") or ["bayes"])[0]
    hrs = {"24h": 24, "7d": 168, "30d": 720}.get(win); since = iso(datetime.now(timezone.utc) - timedelta(hours=hrs)) if hrs else "0000"
    c = db()
    try:
        g = c.execute("SELECT AVG(rating) FROM votes").fetchone()[0]; m = g if g is not None else 5.0
        rows = [dict(r) for r in c.execute("""SELECT item_type, item_id, COUNT(*) n, AVG(rating) a, SUM(rating) s, MAX(ts) last, MAX(title) title, MAX(url) url
                                               FROM votes GROUP BY item_type, item_id HAVING n>=? AND MAX(ts)>=?""", (mn, since))]
    finally: c.close()
    meta = cluster_meta([r["item_id"] for r in rows if r["item_type"] == "cluster"])
    for r in rows:
        r["avg"] = round(r.pop("a"), 2); r["bayes"] = round((C_PRIOR * m + r.pop("s")) / (C_PRIOR + r["n"]), 2)
        mm = meta.get(r["item_id"]) if r["item_type"] == "cluster" else None
        r["bot_rank"] = mm["rank"] if mm else None; r["bot_score"] = mm["score"] if mm else None
        if mm: r["title"] = mm["title"]; r["category"] = mm["category"]
        r["diff"] = round(r["avg"] - r["bot_rank"], 1) if r["bot_rank"] is not None else None
    key = {"votes": lambda r: (-r["n"], -r["bayes"]), "avg": lambda r: (-r["avg"], -r["n"])}.get(sort, lambda r: (-r["bayes"], -r["n"]))
    rows.sort(key=key)
    return {"window": win, "min_votes": mn, "sort": sort, "prior_mean": round(m, 2), "prior_weight": C_PRIOR, "items": rows[:200],
            "note": "User ratings never change the bot's scores, ranks or The Wire's ordering."}
def handle_get(path, qs):
    if path == "/api/user_ranked": return 200, ranked(qs)
    if path == "/api/votes/recent":
        c = db()
        try: rows = [dict(r) for r in c.execute("SELECT item_type,item_id,rating,ts,title FROM votes ORDER BY ts DESC LIMIT 25")]
        finally: c.close()
        return 200, {"items": rows}
    if path == "/api/votes":
        typ = (qs.get("type") or [""])[0]; ids = [i for i in (qs.get("ids") or [""])[0].split(",") if re.fullmatch(r"[A-Za-z0-9_:\-]{1,80}", i)][:300]
        voter = (qs.get("voter") or [""])[0]
        if typ not in TYPES: return 400, {"error": "bad type"}
        c = db()
        try: return 200, {"type": typ, "votes": agg(c, typ, ids, voter if re.fullmatch(r"[a-f0-9]{32}", voter) else None)}
        finally: c.close()
    return 404, {"error": "not found"}
