"""Global search add-on (header search bar on every page; routes /api/search*).
 - 'From the database': SQLite FTS5 index in search.db, built from blackout.db opened READ-ONLY (file:blackout.db?mode=ro),
   refreshed incrementally (clusters.updated) every 30 s / after each scan. Parameterized MATCH queries only.
 - 'Live scan': fixed-template keyword queries (URL-encoded) to sources that support search, plus keyword filtering of the
   scanner's own feeds (fetched with scanner.py's own fetchers, cached 10 min, single-flight). Streams over SSE.
 - Scoring/dedupe: live items are built with the scanner's own item()/news_item()/social_item() constructors and run through
   scanner.ingest_items() -> assign_clusters()/rebuild_cluster()/rank_cluster() on a PRIVATE in-memory SQLite copy seeded
   with the matching database clusters. So ranks/scores are the scanner's exact 0-10 / 0-100 values, and nothing is ever
   written to blackout.db (no feed pollution, no push, no dedupe side effects). Live results are ephemeral.
Never modifies scanner.py, scoring, push.py, jets.py or config.json."""
import builtins, json, os, re, sqlite3, threading, time, traceback, html as _html
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import requests
import scanner as S
import sources_ext as X

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = f"file:{os.path.join(BASE, 'blackout.db')}?mode=ro"
SDB = os.path.join(BASE, "search.db")
STATIC = os.path.join(BASE, "search_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
MAXQ = 200; SRC_TIMEOUT = 8; FEED_WAIT = 8; CACHE_TTL = 600; FEED_TTL = 600
CLIENT_LIVE_PER_MIN = 6; MAX_LIVE = 3; DB_LIMIT = 60; SEED_LIMIT = 200; LIVE_CAP = 40
COLORS = ["#3a4250", "#4b5563", "#2f7d4f", "#52c41a", "#a0d911", "#fadb14", "#faad14", "#fa8c16", "#ff4d4f", "#cf1322", "#8b0000"]  # same as /scoring

ST = getattr(builtins, "_bn_search", None)
if ST is None:
    ST = builtins._bn_search = {"idx_lock": threading.Lock(), "idx_stamp": None, "idx_last": 0, "idx_n": 0, "started": False,
                                "clients": {}, "cl_lock": threading.Lock(), "cool": {}, "cool_lock": threading.Lock(),
                                "feeds": {}, "feed_locks": {}, "fl_lock": threading.Lock(), "cache": {}, "live_sem": threading.Semaphore(MAX_LIVE),
                                "pool": ThreadPoolExecutor(max_workers=8, thread_name_prefix="bn-search"), "streams": 0, "last_search": 0,
                                "schema": None, "backoff": {}}

def _iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _src():
    c = sqlite3.connect(SRC, uri=True, timeout=15); c.row_factory = sqlite3.Row; return c
def _sdb():
    c = sqlite3.connect(SDB, timeout=15); c.row_factory = sqlite3.Row
    c.executescript("""PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, cluster_id TEXT UNIQUE, updated TEXT, data TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, body, sources, location, tokenize='porter unicode61 remove_diacritics 2');
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS cache(qkey TEXT PRIMARY KEY, created REAL, payload TEXT);
    CREATE TABLE IF NOT EXISTS log(t REAL, q TEXT, db_ms REAL, live_ms REAL, n_db INTEGER, n_live INTEGER, cached INTEGER);""")
    return c

# ---------------------------------------------------------------- index (search.db, built from read-only blackout.db)
def _doc(r, members):
    links = json.loads(r["links"] or "[]")
    return {"cluster_id": r["cluster_id"], "title": r["title"], "category": r["category"], "location": r["location"],
            "event_time": r["event_time"], "first_seen": r["first_seen"], "updated": r["updated"], "score": r["score"], "rank": r["rank"],
            "confidence": r["confidence"], "watchlist": r["watchlist"], "n_items": r["n_items"], "eff_families": r["eff_families"],
            "families": json.loads(r["families"] or "[]"), "links": links[:6], "sources": sorted({m["source"] for m in members})[:8],
            "lat": r["lat"], "lon": r["lon"]}
def refresh_index(force=False):
    with ST["idx_lock"]:
        s = _src()
        try:
            stamp = tuple(s.execute("SELECT (SELECT MAX(id) FROM scans),(SELECT MAX(updated) FROM clusters),(SELECT COUNT(*) FROM clusters)").fetchone())
            if not force and stamp == ST["idx_stamp"]: return {"changed": 0}
            c = _sdb()
            try:
                last = (c.execute("SELECT v FROM meta WHERE k='last_updated'").fetchone() or [""])[0]
                rows = s.execute("SELECT * FROM clusters WHERE updated>=? ORDER BY updated", (last,)).fetchall()
                n = 0
                for r in rows:
                    mem = s.execute("SELECT source, family, title, extra, location FROM alerts WHERE cluster_id=?", (r["cluster_id"],)).fetchall()
                    body = [r["brief"] or ""]
                    for m in mem[:25]:
                        body.append(m["title"] or "")
                        try:
                            ex = json.loads(m["extra"] or "{}")
                            body += [str(ex.get(k))[:400] for k in ("desc", "summary", "text", "event", "eventtype", "publisher_name") if ex.get(k)]
                        except Exception: pass
                    srcs = " ".join(sorted({m["source"] or "" for m in mem} | {m["family"] or "" for m in mem}))
                    old = c.execute("SELECT id FROM docs WHERE cluster_id=?", (r["cluster_id"],)).fetchone()
                    if old: c.execute("DELETE FROM fts WHERE rowid=?", (old[0],)); c.execute("DELETE FROM docs WHERE id=?", (old[0],))
                    rid = c.execute("INSERT INTO docs(cluster_id, updated, data) VALUES(?,?,?)", (r["cluster_id"], r["updated"], json.dumps(_doc(r, mem)))).lastrowid
                    c.execute("INSERT INTO fts(rowid, title, body, sources, location) VALUES(?,?,?,?,?)",
                              (rid, r["title"] or "", " ".join(body)[:6000], srcs, (r["location"] or "") + " " + (r["category"] or "")))
                    n += 1
                live = {x[0] for x in s.execute("SELECT cluster_id FROM clusters")}
                gone = [(i,) for i, cid in c.execute("SELECT id, cluster_id FROM docs") if cid not in live]
                c.executemany("DELETE FROM fts WHERE rowid=?", gone); c.executemany("DELETE FROM docs WHERE id=?", gone)
                if rows: c.execute("INSERT OR REPLACE INTO meta VALUES('last_updated', ?)", (rows[-1]["updated"],))
                c.execute("DELETE FROM cache WHERE created<?", (time.time() - CACHE_TTL,))
                c.commit()
                ST["idx_n"] = c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            finally: c.close()
            ST["idx_stamp"] = stamp; ST["idx_last"] = time.time()
            return {"changed": n, "removed": len(gone)}
        finally: s.close()
def _indexer():
    while True:
        try: refresh_index()
        except Exception: traceback.print_exc()
        time.sleep(30)

# ---------------------------------------------------------------- query parsing (text only)
STOPQ = set("the a an of in on at to for and or with by from is are was were be this that as near about what any latest news".split())
SYN = {"quake": ["earthquake", "seismic"], "earthquake": ["quake", "seismic"], "earthquakes": ["earthquake", "quake"],
       "flare": ["x-ray", "radio blackout", "xray"], "flares": ["flare", "x-ray"], "solar": ["sun", "space weather", "geomagnetic"],
       "cyberattack": ["cyber", "ransomware", "hack", "hacked", "ddos", "breach", "malware"], "cyberattacks": ["cyberattack", "cyber", "ransomware", "hack"],
       "cyber": ["cyberattack", "ransomware", "hack"], "hurricane": ["cyclone", "typhoon", "tropical storm"], "typhoon": ["cyclone", "hurricane"],
       "cyclone": ["typhoon", "hurricane"], "houthi": ["houthis", "ansar allah", "ansarallah"], "houthis": ["houthi", "ansar allah"],
       "flu": ["influenza", "h5n1"], "bird": ["avian"], "covid": ["coronavirus", "sars-cov-2"], "volcano": ["eruption", "volcanic"],
       "tsunami": ["tidal wave"], "nuke": ["nuclear"], "missile": ["missiles", "rocket"]}
def clean_q(q):
    q = re.sub(r"[\x00-\x1f\x7f]", " ", str(q or ""))[:MAXQ]
    return re.sub(r"\s+", " ", q).strip()
def tokens(q):
    t = [w.strip("-'’") for w in re.findall(r"[\w][\w\-'’]*", q.lower(), re.U)]
    t = [w for w in t if w and len(w) <= 40]
    k = [w for w in t if w not in STOPQ]
    return (k or t)[:8]
def _ph(v): return '"' + v.replace('"', '""') + '"'
def fts_query(toks, mode="and"):
    groups = []
    for i, t in enumerate(toks):
        vs = [t] + SYN.get(t, [])
        alts = [_ph(v) + ("*" if (i == len(toks) - 1 and len(v) >= 3 and " " not in v) else "") for v in vs]
        groups.append("(" + " OR ".join(alts) + ")")
    return (" AND " if mode == "and" else " OR ").join(groups)
def _variants(t):
    out = [t] + SYN.get(t, [])
    if len(t) > 4 and t.endswith("s"): out.append(t[:-1])
    return out
def text_match(toks, hay, need_all=True):
    hay = hay.lower()
    hits = [any(re.search(r"(?<![\w])" + re.escape(v), hay) for v in _variants(t)) for t in toks]
    return all(hits) if need_all else any(hits)

# ---------------------------------------------------------------- database search
def _recency(d):
    t = S.parse_t(d.get("event_time") or d.get("first_seen"))
    if not t: return 0.5
    return 1 / (1 + max(0, (S.now() - t).total_seconds()) / 86400 / 3)
def db_search(q, limit=DB_LIMIT, seed=False):
    t0 = time.perf_counter()
    if ST["idx_stamp"] is None:
        try: refresh_index()
        except Exception: traceback.print_exc()
    toks = tokens(q)
    if not toks: return {"results": [], "ms": 0, "mode": "empty", "hidden_noise": 0, "total": 0}
    c = _sdb()
    try:
        mode = "and"; rows = []
        for mode in ("and", "or"):
            try:
                rows = c.execute("SELECT d.data, bm25(fts, 10.0, 2.0, 3.0, 4.0) b FROM fts JOIN docs d ON d.id=fts.rowid WHERE fts MATCH ? ORDER BY b LIMIT 400",
                                 (fts_query(toks, mode),)).fetchall()
            except sqlite3.OperationalError: rows = []
            if rows or len(toks) == 1: break
        if rows and mode == "or" and len(toks) > 1:   # partial match: keep only the docs that match the most query words
            cnt = {}
            for t in toks:
                try:
                    for (rid,) in c.execute("SELECT rowid FROM fts WHERE fts MATCH ?", (fts_query([t]),)): cnt[rid] = cnt.get(rid, 0) + 1
                except sqlite3.OperationalError: pass
            best = max(cnt.values(), default=0)
            keep = {rid for rid, n in cnt.items() if n == best}
            rows = c.execute("SELECT d.id, d.data, bm25(fts, 10.0, 2.0, 3.0, 4.0) b FROM fts JOIN docs d ON d.id=fts.rowid WHERE fts MATCH ? ORDER BY b LIMIT 400",
                             (fts_query(toks, "or"),)).fetchall()
            rows = [r for r in rows if r["id"] in keep]
    finally: c.close()
    out, hidden = [], 0
    for r in rows:
        d = json.loads(r["data"]); d["relevance"] = round(-r["b"], 3)
        if d["watchlist"] == 2: hidden += 1; continue
        d["_sort"] = d["relevance"] * (1 + 0.08 * (d["rank"] or 0)) * (0.5 + _recency(d))
        out.append(d)
    out.sort(key=lambda d: -d["_sort"])
    for d in out: d.pop("_sort", None); d["origin"] = "db"
    return {"results": out[:(SEED_LIMIT if seed else limit)], "total": len(out), "hidden_noise": hidden, "mode": mode if rows else "none",
            "ms": round((time.perf_counter() - t0) * 1000, 1), "tokens": toks}

# ---------------------------------------------------------------- live sources
UA = S.UA
def _get(url, **kw):
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=(4, SRC_TIMEOUT), **kw)
    if r.status_code == 429: raise RateLimited("HTTP 429")
    r.raise_for_status(); return r
class RateLimited(Exception): pass
class Deferred(Exception): pass
def _cool(key, gap):
    """Global per-source cooldown shared by all visitors. Raises RateLimited if the source was hit < gap s ago."""
    with ST["cool_lock"]:
        bo = ST["backoff"].get(key, 0)
        if bo > time.time(): raise RateLimited(f"backing off after a 429, {int(bo - time.time())} s left")
        last = ST["cool"].get(key, 0); left = gap - (time.time() - last)
        if left > 3: raise RateLimited(f"source cooldown, retry in {int(left) + 1} s")
        ST["cool"][key] = max(time.time(), last + gap)
    if left > 0: time.sleep(left)
def _backoff(key, s=900): ST["backoff"][key] = time.time() + s

def _rss(src, fam, content, default_cat, base, official, maxage_d, force_cat=False, kwboost=None):
    # same item construction as scanner.rss_generic (fetched here with an 8 s timeout instead of 30 s)
    out = []
    for e in S.rss_items(content):
        t = S.parse_t(e.get("pubDate") or e.get("updated") or e.get("published") or e.get("date"))
        if t and t < S.now() - timedelta(days=maxage_d): continue
        title = S.strip(e.get("title")); desc = S.strip(e.get("description") or e.get("summary"))
        cat = default_cat if force_cat else S.classify(title + " " + desc, default_cat)
        b = base
        if kwboost and re.search(kwboost, title, re.I): b += 20
        out.append(S.item(src, fam, e.get("guid") or e.get("id") or e.get("link") or title, title, cat, e.get("link"), t,
                          base=b, official=official, extra={"desc": desc[:400]}))
    return out

def s_gdelt(q, toks):
    if S.SCAN_LOCK.locked(): raise Deferred("scheduled scan running (shares GDELT's rate limit), skipped")
    if time.time() - X._last_gdelt[0] < 10: raise RateLimited("GDELT allows about 1 request per 5-10 s and it was queried moments ago")
    _cool("gdelt", 60)
    X._last_gdelt[0] = time.time()
    try: r = _get("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote(q + " sourcelang:english") + "&mode=artlist&format=json&maxrecords=50&timespan=3d&sort=datedesc")
    except RateLimited: _backoff("gdelt"); raise
    if r.text.startswith("Please limit"): _backoff("gdelt"); raise RateLimited("GDELT rate limit")
    j = r.json() if r.text.strip() else {}
    out = []
    for a in j.get("articles", []):
        t = S.parse_t(re.sub(r"^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$", r"\1-\2-\3T\4:\5:\6Z", a.get("seendate", "")))
        n = X.news_item(f"GDELT: {a.get('domain')}", a.get("domain"), a["url"], a.get("title", ""), a["url"], t, base=15,
                        extra={"sourcecountry": a.get("sourcecountry"), "query": q})
        if n: out.append(n)
    return out
def s_gnews(q, toks):
    _cool("gnews", 3)
    txt = _get(f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=en-US&gl=US&ceid=US:en").text
    out = []
    for it in re.findall(r"<item>(.*?)</item>", txt, re.S)[:60]:
        title = S.strip(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
        link = S.strip(re.search(r"<link>(.*?)</link>", it, re.S).group(1))
        src = re.search(r'<source url="([^"]+)">(.*?)</source>', it, re.S)
        pub = S.strip(src.group(2)) if src else ""; pd = X.domain(src.group(1)) if src else ""
        if pub and title.endswith(" - " + pub): title = title[: -len(pub) - 3]
        t = S.parse_t((re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, None])[1])
        if t and t < S.now() - timedelta(days=7): continue
        n = X.news_item(f"Google News: {pub or pd}", pd, link, title, link, t, extra={"publisher_name": pub, "query": q})
        if n: out.append(n)
    return out
def s_reddit(q, toks):
    if S.SCAN_LOCK.locked(): raise Deferred("scheduled scan running (Reddit rate-limits this box), skipped")
    _cool("reddit", 10)
    try: txt = _get(f"https://www.reddit.com/search.rss?q={quote(q)}&sort=new&t=week&limit=50").text
    except RateLimited: _backoff("reddit", 300); raise
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", txt, re.S):
        tm = re.search(r"<title>(.*?)</title>", e, re.S); lm = re.search(r'<link href="([^"]+)"', e)
        if not tm or not lm: continue
        title = S.strip(tm.group(1)); link = lm.group(1)
        sub = (re.search(r'label="(r/[^"]+)"', e) or [None, "r/?"])[1]
        t = S.parse_t((re.search(r"<published>(.*?)</published>", e) or [None, None])[1])
        content = _html.unescape((re.search(r'<content type="html">(.*?)</content>', e, re.S) or [None, ""])[1])
        linkm = re.search(r'<a href="([^"]+)">\[link\]</a>', content)
        urls = [linkm.group(1)] if linkm else []
        it = X.social_item(f"Reddit {sub}", link, title, link, t, urls, S.strip(content)[:300], extra={"subreddit": sub, "linked": urls[:1], "query": q})
        if it: out.append(it)
    return out
def s_bluesky(q, toks):
    _cool("bluesky", 2)
    j = _get(f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote(q)}&limit=40&sort=latest").json()
    out = []
    for p in j.get("posts", []) or []:
        r = p.get("record") or {}; text = r.get("text") or ""; urls = []
        emb = r.get("embed") or {}
        if ((emb.get("external") or {}).get("uri")): urls.append(emb["external"]["uri"])
        for f in r.get("facets") or []:
            for ft in (f or {}).get("features") or []:
                if (ft or {}).get("uri"): urls.append(ft["uri"])
        if not p.get("author") or not p.get("uri"): continue
        media = "images" in json.dumps(emb) or "video" in json.dumps(emb)
        web = f"https://bsky.app/profile/{p['author']['handle']}/post/{p['uri'].rsplit('/', 1)[-1]}"
        it = X.social_item(f"Bluesky @{p['author']['handle']}", p["uri"], text[:280], web, S.parse_t(r.get("createdAt")), urls, text,
                           extra={"query": q}, media_flag=media)
        if it: out.append(it)
    return out
def s_mastodon(q, toks):
    tags = [re.sub(r"[^a-z0-9_]", "", t) for t in sorted(toks, key=len, reverse=True)]
    tags = [t for t in tags if len(t) >= 3][:2]
    if not tags: return []
    out = []
    for tag in tags:
        _cool("mastodon", 2)
        for st in _get(f"https://mastodon.social/api/v1/timelines/tag/{quote(tag)}?limit=40").json():
            text = S.strip(st.get("content"))
            if not text_match(toks, text): continue
            urls = [u for u in re.findall(r'href="([^"]+)"', st.get("content") or "") if "/tags/" not in u and "/@" not in u]
            if st.get("card") and st["card"].get("url"): urls.insert(0, st["card"]["url"])
            ct = S.parse_t(st.get("created_at"))
            if ct and ct < S.now() - timedelta(days=2): continue
            it = X.social_item(f"Mastodon @{st['account']['acct']}", st["id"], text[:280], st.get("url") or st.get("uri"), ct, urls, text,
                               extra={"tag": tag, "query": q}, media_flag=bool(st.get("media_attachments")))
            if it: out.append(it)
    return out
def s_reliefweb(q, toks):
    _cool("reliefweb", 2)
    r = _get(f"https://reliefweb.int/updates/rss.xml?search={quote(q)}")
    return _rss("ReliefWeb Updates", "ReliefWeb", r.content, "other", 12, False, 30, kwboost=r"flash update|emergency|outbreak|earthquake|cyclone|displac")
def s_who(q, toks):
    # fixed URL (no user text sent); same item rules as scanner.f_who, but a 180-day window and keyword filter
    j = _feed("who_api", lambda: _get("https://www.who.int/api/news/diseaseoutbreaknews?$orderby=PublicationDate%20desc&$top=60").json())
    out = []
    for v in j.get("value", []):
        t = S.parse_t(v.get("PublicationDate"))
        if t and t < S.now() - timedelta(days=60): continue
        title = v.get("OverrideTitle") or v.get("Title") or ""
        if not text_match(toks, title + " " + S.strip(v.get("Summary"))[:800]): continue
        base = 45
        if re.search(r"ebola|marburg|bundibugyo|novel|h5n1|avian|mers|plague|nipah|pandemic|lassa|sars", title, re.I): base += 20
        countries = re.split(r",| and | - ", title.split(",", 1)[-1]) if "," in title or " - " in title else []
        if len(countries) >= 2: base += 10
        out.append(S.item("WHO Disease Outbreak News", "WHO", v.get("Id"), title, "disease",
                          "https://www.who.int/emergencies/disease-outbreak-news/item/" + (v.get("UrlName") or ""), t,
                          location=(title.split(" - ", 1)[-1].strip() if " - " in title else (title.split(",", 1)[-1].strip() if "," in title else None)),
                          base=base, extra={"summary": S.strip(v.get("Summary"))[:500], "don_id": v.get("DonId")}))
    return out

def _feed(key, fn):
    """Single-flight 10-minute cache of a whole feed (shared by every query). Uses the scanner's own fetcher functions."""
    with ST["fl_lock"]: lk = ST["feed_locks"].setdefault(key, threading.Lock())
    with lk:
        hit = ST["feeds"].get(key)
        if hit and time.time() - hit[0] < FEED_TTL: return hit[1]
        if S.SCAN_LOCK.locked() and hit and time.time() - hit[0] < 3 * FEED_TTL: return hit[1]   # don't double-fetch during a scan
        if S.SCAN_LOCK.locked() and not hit: raise Deferred("scheduled scan running; feed is re-read after it finishes")
        res = fn()
        if isinstance(res, tuple): res = res[0]
        ST["feeds"][key] = (time.time(), res)
        return res
EQ_TYPES = {"EQ": "earthquake quake seismic", "TC": "tropical cyclone typhoon hurricane storm", "FL": "flood flooding", "VO": "volcano eruption volcanic",
            "DR": "drought", "WF": "wildfire fire"}
def _hay(it):
    ex = json.loads(it.get("extra") or "{}")
    h = [it.get("title") or "", it.get("location") or "", it.get("category") or "", it.get("source") or ""]
    h += [str(ex.get(k)) for k in ("desc", "summary", "text", "event", "areaDesc", "channel", "eonet_category") if ex.get(k)]
    if ex.get("mag"): h.append("earthquake quake seismic")
    if ex.get("eventtype"): h.append(EQ_TYPES.get(ex["eventtype"], ""))
    if it.get("category") == "space weather":
        h.append("space weather solar sun geomagnetic")
        if re.search(r"x-ray|radio blackout", it.get("title") or "", re.I): h.append("solar flare")
        if re.search(r"geomagnetic|kp", it.get("title") or "", re.I): h.append("geomagnetic storm aurora")
    if it.get("category") == "cyber": h.append("cyber cyberattack vulnerability")
    return " ".join(h)
def feed_source(key, fn):
    def run(q, toks):
        return [it for it in _feed(key, fn) if text_match(toks, _hay(it))]
    return run
SOURCES = [  # key, label, kind, fn, note
    ("gdelt", "GDELT DOC API", "keyword", s_gdelt, "keyword search, worldwide news, 3 days"),
    ("gnews", "Google News", "keyword", s_gnews, "keyword RSS search, 7 days"),
    ("reddit", "Reddit", "keyword", s_reddit, "keyword search RSS, 1 week"),
    ("bluesky", "Bluesky", "keyword", s_bluesky, "searchPosts, latest"),
    ("mastodon", "Mastodon", "keyword", s_mastodon, "hashtag timeline + keyword filter (no-login search returns no posts)"),
    ("reliefweb", "ReliefWeb", "keyword", s_reliefweb, "RSS search, 30 days"),
    ("who", "WHO Outbreak News", "filter", s_who, "latest DONs (60 days), keyword filter"),
    ("cidrap", "CIDRAP", "filter", feed_source("cidrap", S.f_cidrap), "topic feeds, keyword filter"),
    ("usgs", "USGS quakes", "filter", feed_source("usgs", S.f_usgs), "M4.5+ day feed, place/region match"),
    ("gdacs", "GDACS", "filter", feed_source("gdacs", S.f_gdacs), "event name/country match"),
    ("swpc", "NOAA SWPC", "filter", feed_source("swpc", S.f_swpc), "alerts + Kp, keyword match"),
    ("nws", "NWS alerts", "filter", feed_source("nws", S.f_nws), "Severe/Extreme US alerts, keyword match"),
    ("tsunami", "tsunami.gov", "filter", feed_source("tsunami", S.f_tsunami), "NTWC/PTWC messages"),
    ("eonet", "NASA EONET", "filter", feed_source("eonet", S.f_eonet), "open natural events"),
    ("cisa", "CISA", "filter", feed_source("cisa", lambda: S.f_cisa_kev() + S.f_cisa_adv()), "KEV + advisories"),
    ("telegram", "Telegram channels", "filter", feed_source("telegram", S.f_telegram), f"{len(S.TG_CHANNELS + S.TG_EXTRA)} public channels the scanner monitors"),
]
UNAVAILABLE = [
    ("promed", "ProMED", "no public feed (moved to a subscription platform; /feed is 404). Database only, if ever ingested."),
    ("epiwatch", "EpiWatch", "JavaScript-only app with no public machine-readable feed."),
    ("discord", "Discord", "no public no-login read access; the scanner ingests no Discord channels."),
    ("x", "X / Twitter", "not searchable without a login; X items reach the database only via the hourly chat check."),
]
def warm_feeds():
    def go():
        for key, label, kind, fn, note in SOURCES:
            if kind == "filter":
                try: fn("", ["__warm__"])
                except Exception: pass
    ST["pool"].submit(go)

# ---------------------------------------------------------------- private scoring session (in-memory copy, never blackout.db)
def _schema():
    if ST["schema"] is None:
        s = _src()
        try: ST["schema"] = [r[0] for r in s.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('alerts','clusters')")]
        finally: s.close()
    return ST["schema"]
class Session:
    def __init__(self):
        self.c = sqlite3.connect(":memory:", check_same_thread=False); self.c.row_factory = sqlite3.Row
        for sql in _schema(): self.c.execute(sql)
        self.c.execute("CREATE INDEX ix_c ON alerts(cluster_id)")
        self.lock = threading.Lock(); self.seeded = set(); self.live_src = {}
    def seed(self, cids):
        cids = [c for c in cids if c not in self.seeded]
        if not cids: return
        s = _src()
        try:
            for i in range(0, len(cids), 200):
                part = cids[i:i + 200]; qm = ",".join("?" * len(part))
                for r in s.execute(f"SELECT * FROM clusters WHERE cluster_id IN ({qm})", part):
                    self.c.execute(f"INSERT OR REPLACE INTO clusters VALUES({','.join('?' * len(r.keys()))})", tuple(r))
                for r in s.execute(f"SELECT * FROM alerts WHERE cluster_id IN ({qm})", part):
                    self.c.execute(f"INSERT OR REPLACE INTO alerts VALUES({','.join('?' * len(r.keys()))})", tuple(r))
        finally: s.close()
        self.seeded |= set(cids)
    def add(self, items, label):
        with self.lock:
            ids = [it["id"] for it in items]
            if ids:   # live items the scanner already stored: pull their database clusters in, so they merge instead of duplicating
                s = _src()
                try: known = [r[0] for r in s.execute(f"SELECT DISTINCT cluster_id FROM alerts WHERE id IN ({','.join('?' * len(ids))}) AND cluster_id IS NOT NULL", ids)]
                finally: s.close()
                self.seed(known)
            ts = S.iso(S.now())
            S.ingest_items(self.c, items)    # scanner's own dedupe + clustering + scoring, on the private in-memory copy
            for it in items:
                cid = self.c.execute("SELECT cluster_id FROM alerts WHERE id=?", (it["id"],)).fetchone()
                if cid: self.live_src.setdefault(cid[0], set()).add(label)
            return [self.out(r) for r in self.c.execute("SELECT * FROM clusters WHERE updated>=?", (ts,))]
    def out(self, r):
        cid = r["cluster_id"]
        mem = self.c.execute("SELECT source FROM alerts WHERE cluster_id=?", (cid,)).fetchall()
        d = _doc(r, mem)
        d["origin"] = ("db+live" if cid in self.live_src else "db") if cid in self.seeded else "live"
        d["live_sources"] = sorted(self.live_src.get(cid, ()))
        return d

# ---------------------------------------------------------------- SSE search
def _ip_ok(ip):
    with ST["cl_lock"]:
        dq = ST["clients"].setdefault(ip, deque())
        while dq and time.time() - dq[0] > 60: dq.popleft()
        if len(dq) >= CLIENT_LIVE_PER_MIN: return False, int(60 - (time.time() - dq[0])) + 1
        dq.append(time.time())
        if len(ST["clients"]) > 5000: ST["clients"].clear()
        return True, 0
def _qkey(q): return " ".join(tokens(q)) + "|" + q.lower()
def _cache_get(k):
    hit = ST["cache"].get(k)
    if hit and time.time() - hit[0] < CACHE_TTL: return hit
    try:
        c = _sdb()
        try: r = c.execute("SELECT created, payload FROM cache WHERE qkey=?", (k,)).fetchone()
        finally: c.close()
        if r and time.time() - r[0] < CACHE_TTL: ST["cache"][k] = (r[0], json.loads(r[1])); return ST["cache"][k]
    except Exception: pass
    return None
def _cache_put(k, payload):
    ST["cache"][k] = (time.time(), payload)
    if len(ST["cache"]) > 300:
        for kk in sorted(ST["cache"], key=lambda x: ST["cache"][x][0])[:100]: ST["cache"].pop(kk, None)
    try:
        c = _sdb()
        try: c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (k, time.time(), json.dumps(payload, default=str))); c.commit()
        finally: c.close()
    except Exception: traceback.print_exc()
def _log(q, db_ms, live_ms, n_db, n_live, cached):
    try:
        c = _sdb()
        try: c.execute("INSERT INTO log VALUES(?,?,?,?,?,?,?)", (time.time(), q[:200], db_ms, live_ms, n_db, n_live, 1 if cached else 0)); c.commit()
        finally: c.close()
    except Exception: pass

def run_search(q, emit, ip="?", live=True):
    """Core search; emit(event, data). Used by the SSE handler and the CLI test."""
    t0 = time.perf_counter()
    q = clean_q(q); toks = tokens(q)
    emit("hello", {"q": q, "tokens": toks, "colors": COLORS, "scan_running": S.SCAN_LOCK.locked(),
                   "sources": [{"key": k, "label": l, "kind": kd, "note": n} for k, l, kd, f, n in SOURCES],
                   "unavailable": [{"key": k, "label": l, "why": w} for k, l, w in UNAVAILABLE]})
    if not toks: emit("done", {"error": "empty query"}); return
    ST["last_search"] = time.time()
    dbr = db_search(q, seed=True)
    shown = dbr["results"][:DB_LIMIT]
    emit("db", {**dbr, "results": shown})
    if not live: emit("done", {"db_ms": dbr["ms"], "live": False}); return
    k = _qkey(q); hit = _cache_get(k)
    if hit:
        p = hit[1]
        for s in p["sources"]: emit("source", {**s, "cached": True})
        emit("results", {"items": p["items"], "cached": True, "age_s": int(time.time() - hit[0])})
        emit("done", {**p["stats"], "cached": True, "age_s": int(time.time() - hit[0]), "db_ms": dbr["ms"]})
        _log(q, dbr["ms"], 0, len(shown), len(p["items"]), True); return
    ok, wait_s = _ip_ok(ip)
    if not ok:
        emit("limited", {"reason": f"Live scan limit is {CLIENT_LIVE_PER_MIN} per minute per visitor. Database results are shown; try the live scan again in {wait_s} s."})
        emit("done", {"db_ms": dbr["ms"], "live": False, "limited": True}); return
    got = ST["live_sem"].acquire(timeout=0.1)
    if not got:
        emit("queued", {"reason": "Other live scans are running; this one is queued."})
        got = ST["live_sem"].acquire(timeout=20)
        if not got:
            emit("limited", {"reason": "The live scanner is busy. Database results are shown; try again in a minute."})
            emit("done", {"db_ms": dbr["ms"], "live": False, "limited": True}); return
    try:
        sess = Session(); sess.seed([d["cluster_id"] for d in dbr["results"]])
        scanning = S.SCAN_LOCK.locked()
        workers = 2 if scanning else 5
        if scanning: emit("notice", {"text": "A scheduled scan is running, so the live part is limited: GDELT and Reddit are skipped and feeds use their last cached copy."})
        tl = time.perf_counter(); statuses = {}; items_out = {}
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bn-sq") as ex:
            futs = {}
            for key, label, kind, fn, note in SOURCES:
                emit("source", {"key": key, "label": label, "status": "searching"})
                futs[ex.submit(_timed, fn, q, toks)] = (key, label, kind)
            pending = set(futs); deadline = time.time() + SRC_TIMEOUT + 6
            while pending:
                done, pending = wait(pending, timeout=max(0.1, deadline - time.time()), return_when=FIRST_COMPLETED)
                for f in done:
                    key, label, kind = futs[f]
                    try: st, res, ms = f.result()
                    except Exception as e: st, res, ms = "failed", f"{type(e).__name__}", None
                    if st == "ok":
                        res = [it for it in res if kind == "filter" or text_match(toks, _hay(it), need_all=False)][:LIVE_CAP]
                        try: changed = sess.add(res, label) if res else []
                        except Exception as e: traceback.print_exc(); changed = []; st = "failed"
                        for d in changed: items_out[d["cluster_id"]] = d
                        s = {"key": key, "label": label, "status": "ok", "n": len(res), "ms": ms}
                        if changed: emit("results", {"items": changed})
                    else:
                        s = {"key": key, "label": label, "status": st, "error": res, "ms": ms}
                    statuses[key] = s; emit("source", s)
                if time.time() >= deadline:
                    for f in pending:
                        key, label, kind = futs[f]; f.cancel()
                        s = {"key": key, "label": label, "status": "timeout", "error": f"no answer within {SRC_TIMEOUT} s (feeds keep loading in the background for the next search)", "ms": None}
                        statuses[key] = s; emit("source", s)
                    break
            ex.shutdown(wait=False, cancel_futures=True)
        live_ms = round((time.perf_counter() - tl) * 1000)
        items = list(items_out.values())
        stats = {"live_ms": live_ms, "db_ms": dbr["ms"], "n_live_clusters": sum(1 for d in items if d["origin"] == "live" and d["watchlist"] != 2),
                 "n_merged": sum(1 for d in items if d["origin"] == "db+live"), "hidden_noise": sum(1 for d in items if d["watchlist"] == 2),
                 "sources_ok": sum(1 for s in statuses.values() if s["status"] == "ok"), "total_ms": round((time.perf_counter() - t0) * 1000)}
        if not scanning: _cache_put(k, {"items": items, "sources": list(statuses.values()), "stats": stats})   # partial (scan-limited) runs are not cached
        emit("done", stats)
        _log(q, dbr["ms"], live_ms, len(shown), len(items), False)
    finally:
        ST["live_sem"].release()
def _timed(fn, q, toks):
    t = time.perf_counter()
    try: return "ok", fn(q, toks), round((time.perf_counter() - t) * 1000)
    except RateLimited as e: return "rate-limited", str(e)[:160], round((time.perf_counter() - t) * 1000)
    except Deferred as e: return "deferred", str(e)[:160], round((time.perf_counter() - t) * 1000)
    except requests.ConnectTimeout: return "timeout", "could not connect within 4 s (source unreachable from this box right now)", round((time.perf_counter() - t) * 1000)
    except requests.Timeout: return "timeout", f"no answer within {SRC_TIMEOUT} s", round((time.perf_counter() - t) * 1000)
    except Exception as e: return "failed", f"{type(e).__name__}: {str(e)[:140]}", round((time.perf_counter() - t) * 1000)

# ---------------------------------------------------------------- HTTP
if not ST["started"]:
    ST["started"] = True
    threading.Thread(target=_indexer, daemon=True, name="bn-search-index").start()
    warm_feeds()

def handle_get(path, qs):
    if path.startswith("/api/search/") and path.rsplit("/", 1)[-1] in FILES:
        name = path.rsplit("/", 1)[-1]
        with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
    if path == "/api/search/db":
        q = clean_q((qs.get("q") or [""])[0])
        if not q: return 400, {"error": "q required"}
        try: lim = max(1, min(DB_LIMIT, int((qs.get("limit") or [DB_LIMIT])[0])))
        except Exception: lim = DB_LIMIT
        r = db_search(q, lim); return 200, {"q": q, **r}
    if path == "/api/search":
        return 200, {"index_docs": ST["idx_n"], "index_refreshed": _iso(datetime.fromtimestamp(ST["idx_last"], timezone.utc)) if ST["idx_last"] else None,
                     "live_sources": [{"key": k, "label": l, "kind": kd, "note": n} for k, l, kd, f, n in SOURCES],
                     "unavailable": [{"key": k, "label": l, "why": w} for k, l, w in UNAVAILABLE],
                     "limits": {"max_query": MAXQ, "live_scans_per_minute_per_client": CLIENT_LIVE_PER_MIN, "cache_s": CACHE_TTL,
                                "per_source_timeout_s": SRC_TIMEOUT, "max_concurrent_live": MAX_LIVE}, "scan_running": S.SCAN_LOCK.locked(), "open_streams": ST["streams"]}
    return 404, {"error": "not found"}

def handle_stream(path, qs, h):
    if path != "/api/search/stream": return h.send(*handle_get(path, qs))
    if ST["streams"] >= 30: return h.send(503, {"error": "too many open searches"})
    q = clean_q((qs.get("q") or [""])[0])
    live = (qs.get("live") or ["1"])[0] != "0"
    h.send_response(200); h.send_header("Content-Type", "text/event-stream; charset=utf-8"); h.send_header("Cache-Control", "no-store")
    h.send_header("X-Accel-Buffering", "no"); h.send_header("X-Content-Type-Options", "nosniff"); h.end_headers()
    ST["streams"] += 1
    wl = threading.Lock()
    def emit(ev, data):
        with wl:
            h.wfile.write(f"event: {ev}\ndata: {json.dumps(data, default=str)}\n\n".encode()); h.wfile.flush()
    try:
        h.wfile.write(b"retry: 600000\n\n"); h.wfile.flush()
        run_search(q, emit, ip=h.ip(), live=live)
    except (BrokenPipeError, ConnectionResetError, OSError): pass
    except Exception as ex:
        traceback.print_exc()
        try: emit("done", {"error": f"{type(ex).__name__}"})
        except Exception: pass
    finally:
        ST["streams"] -= 1; h.close_connection = True
