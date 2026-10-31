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
    if path == "/api/vote/source": return source_vote(d, ip)
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
    if path == "/api/votes/source":
        ids = [i for i in (qs.get("ids") or [""])[0].split(",") if SID_RE.fullmatch(i)][:200]
        voter = (qs.get("voter") or [""])[0]
        return 200, {"grades": source_grades(ids, voter if re.fullmatch(r"[a-f0-9]{32}", voter) else None), "rules": GRADE_RULES}
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


# ---------------------------------------------------------------- source reliability grades (2026-10-31, Sources page)
# Visitors rate a SOURCE 1-5 stars. Stored in votes.db table source_votes (same Render-owned DB as alert votes, so it survives
# redeploys the same way: the box mirrors votes.db and restores it after a restart). Never read by the scanner: no effect on
# alert scores, ranks or The Wire. No personal data: the voter id is a random per-browser token; the per-IP limiter keeps only a
# salted SHA-256 hash in memory (never written to disk or logs).
import hashlib, secrets as _secrets
SID_RE = re.compile(r"[cd]:[A-Za-z0-9_:.@\-]{1,180}")
GRADE_C = 5            # prior weight, in votes
GRADE_MIN = 3          # votes needed before a letter grade is shown
GRADE_CUTS = [(80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "F")]
SRC_LIMITS = {"ip_min": 20, "ip_day": 300, "voter_day": 300, "all_day": 20000}
_salt = _secrets.token_hex(16); _srl = {}
GRADE_RULES = {"scale": "1-5 stars", "prior_weight": GRADE_C, "min_votes": GRADE_MIN, "cuts": GRADE_CUTS,
               "formula": "score = (prior_weight x prior + sum of stars) / (prior_weight + votes); shown as 0-100 = (score - 1) / 4 x 100"}
def _sdb():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS source_votes(sid TEXT, voter TEXT, stars INTEGER, ts TEXT, PRIMARY KEY(sid, voter))""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_sv_ts ON source_votes(ts)"); c.execute("CREATE INDEX IF NOT EXISTS ix_sv_voter ON source_votes(voter, ts)")
    return c
def _src_limited(ip):
    k = hashlib.sha256((_salt + (ip or "?")).encode()).hexdigest()[:24]; t = time.time()
    with _lock:
        h = [x for x in _srl.get(k, []) if t - x < 86400]; _srl[k] = h
        if len(_srl) > 50000:
            for kk in list(_srl)[:10000]: _srl.pop(kk, None)
        if sum(1 for x in h if t - x < 60) >= SRC_LIMITS["ip_min"] or len(h) >= SRC_LIMITS["ip_day"]: return True
        h.append(t); return False
def source_prior(sid):
    """Prior mean (1-5) from the source's registry/type, so unrated sources start neutral-to-official, not extreme."""
    try:
        if sid.startswith("c:"):
            import sources_directory as SD; r = SD.catalog_rating(sid)
            return round(1 + 0.4 * r, 2) if r is not None else 3.5
        import sources_directory as SD; return SD.prior_for(sid)
    except Exception: return 3.5
def grade_of(n, s, prior):
    score = (GRADE_C * prior + s) / (GRADE_C + n); pct = round((score - 1) / 4 * 100)
    letter = next(g for cut, g in GRADE_CUTS if pct >= cut)
    return {"n": n, "avg": round(s / n, 2) if n else None, "score": pct, "prior": round((prior - 1) / 4 * 100),
            "grade": letter if n >= GRADE_MIN else None, "label": f"{letter} ({pct}/100, {n} vote{'s' if n != 1 else ''})" if n >= GRADE_MIN else
            ("Not yet rated" if n == 0 else f"Not yet rated ({n} of {GRADE_MIN} votes)")}
def source_grades(ids, voter=None):
    out = {}
    if not ids: return out
    c = _sdb()
    try:
        q = ",".join("?" * len(ids))
        agg_ = {r["sid"]: (r["n"], r["s"]) for r in c.execute(f"SELECT sid, COUNT(*) n, SUM(stars) s FROM source_votes WHERE sid IN ({q}) GROUP BY sid", ids)}
        mine = {r["sid"]: r["stars"] for r in c.execute(f"SELECT sid, stars FROM source_votes WHERE voter=? AND sid IN ({q})", [voter] + ids)} if voter else {}
    finally: c.close()
    for i in ids:
        n, s = agg_.get(i, (0, 0)); g = grade_of(n, s or 0, source_prior(i)); g["mine"] = mine.get(i); out[i] = g
    return out
def rated_ids(min_votes=GRADE_MIN, limit=2000):
    c = _sdb()
    try: return [(r["sid"], r["n"], r["s"]) for r in c.execute("SELECT sid, COUNT(*) n, SUM(stars) s FROM source_votes GROUP BY sid HAVING n>=? ORDER BY n DESC LIMIT ?", (min_votes, limit))]
    finally: c.close()
def source_vote(d, ip):
    sid = str(d.get("sid") or ""); voter = str(d.get("voter") or "")
    try: stars = int(d.get("stars"))
    except Exception: stars = None
    if not SID_RE.fullmatch(sid): return 400, {"error": "bad source id"}
    if not re.fullmatch(r"[a-f0-9]{32}", voter): return 400, {"error": "bad voter id"}
    if stars is None or not 1 <= stars <= 5: return 400, {"error": "stars must be an integer 1-5"}
    try:
        import sources_directory as SD
        if not SD.source_exists(sid): return 404, {"error": "unknown source"}
    except Exception as ex: return 503, {"error": "source list is loading, try again shortly"}
    if _src_limited(ip): return 429, {"error": "Too many ratings from this connection. Please slow down."}
    c = _sdb()
    try:
        day = iso(datetime.now(timezone.utc) - timedelta(days=1))
        if c.execute("SELECT COUNT(*) FROM source_votes WHERE voter=? AND ts>=?", (voter, day)).fetchone()[0] >= SRC_LIMITS["voter_day"] or \
           c.execute("SELECT COUNT(*) FROM source_votes WHERE ts>=?", (day,)).fetchone()[0] >= SRC_LIMITS["all_day"]:
            return 429, {"error": "Daily rating limit reached. Please try again tomorrow."}
        c.execute("INSERT INTO source_votes VALUES(?,?,?,?) ON CONFLICT(sid,voter) DO UPDATE SET stars=excluded.stars, ts=excluded.ts", (sid, voter, stars, iso()))
        c.commit()
    finally: c.close()
    g = source_grades([sid], voter)[sid]
    return 200, {"status": "ok", "sid": sid, **g}
