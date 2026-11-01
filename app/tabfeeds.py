"""Shared engine for the two unlisted watch tabs (2026-10-31, t231): 🤖 AI Threats (aithreats.py, #ai) and ⚡ U.S. Energy Grid (gridwatch.py, #grid).
Both tabs are UNPUBLISHED: reachable only by direct link (blackout.network/#ai, /#grid), never added to the nav, no sitemap entry, noindex.

Data:
  1. Scanner alerts: every stored cluster in blackout.db (opened read-only, file:blackout.db?mode=ro), including the Telegram / Discord /
     Mastodon / Bluesky analyst channels the scanner already ingests, filtered by each tab's keyword classifier. Rank (0-10), score (0-100),
     watchlist status and source links are the scanner's own stored values; nothing is re-scored.
  2. Extra feeds: a few real public feeds per tab (live-checked), collected on the box by `python3 tabfeeds.py loop` (run_tabfeeds.sh) into
     tabfeeds.db, which reaches Render through the normal box->Render DB sync. A feed item whose URL matches a scanner alert inherits that
     cluster's stored rank; every other feed item is shown as "unscored" (ranks are never invented).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json or blackout.db (read-only)."""
import os, re, sys, json, time, sqlite3, hashlib, html, threading, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
FDB = os.path.join(BASE, "tabfeeds.db")
STATIC = os.path.join(BASE, "tabfeeds_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
UA = "Mozilla/5.0 (compatible; blackout.network research monitor; hello@blackout.network)"
TTL = 60
LIST = {0: "wire", 1: "watchlist", 2: "suppressed"}
KEEP_DAYS = 120

_C = getattr(sys, "_bn_tabfeeds_cache", None)
if _C is None: _C = sys._bn_tabfeeds_cache = {}
_LK = getattr(sys, "_bn_tabfeeds_lock", None)
if _LK is None: _LK = sys._bn_tabfeeds_lock = threading.Lock()

def iso(t=None): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
def log(m): print(time.strftime("[%Y-%m-%d %H:%M:%S] "), m, flush=True)
def _j(s, d=None):
    try: return json.loads(s) if s else (d if d is not None else [])
    except Exception: return d if d is not None else []
TAG = re.compile(r"<[^>]+>")
def clean(s, n=500): return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()[:n]
def norm_url(u):
    u = (u or "").strip().lower().split("#")[0]
    u = re.sub(r"^https?://(www\.)?", "", u).rstrip("/")
    return u

# ------------------------------------------------------------------ scanner side (read-only)
def _ro(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c

def _corpus(c):
    """All clusters with their member alert titles/sources, cached per scanner state."""
    st = c.execute("SELECT (SELECT MAX(id) FROM scans) s, (SELECT MAX(updated) FROM clusters) u, (SELECT COUNT(*) FROM clusters) n").fetchone()
    key = (st["s"], st["u"], st["n"])
    with _LK:
        hit = _C.get("corpus")
        if hit and hit[0] == key: return key, hit[1]
    al = {}
    for r in c.execute("SELECT cluster_id, source, title, source_url FROM alerts WHERE cluster_id IS NOT NULL"):
        a = al.setdefault(r["cluster_id"], {"titles": [], "sources": set(), "urls": set()})
        if len(a["titles"]) < 12: a["titles"].append(r["title"] or "")
        a["sources"].add(r["source"] or ""); a["urls"].add(norm_url(r["source_url"]))
    out = []
    for r in c.execute("""SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated, score, confidence,
                          n_items, n_families, families, links, watchlist, brief, rank FROM clusters"""):
        d = dict(r); a = al.get(d["cluster_id"], {"titles": [], "sources": set(), "urls": set()})
        d["links"] = [l for l in _j(d["links"]) if isinstance(l, dict)]
        d["_srcs"] = a["sources"]; d["_urls"] = a["urls"] | {norm_url(l.get("url")) for l in d["links"]}
        d["_text"] = "\n".join([d["title"] or "", d["brief"] or ""] + a["titles"])
        out.append(d)
    with _LK: _C["corpus"] = (key, out)
    return key, out

def _feed_rows(tab):
    if not os.path.exists(FDB): return [], []
    try:
        c = _ro(FDB)
        try:
            items = [dict(r) for r in c.execute("SELECT * FROM feed_items WHERE tab=? ORDER BY published DESC LIMIT 2000", (tab,))]
            stat = [dict(r) for r in c.execute("SELECT * FROM feed_status WHERE tab=? ORDER BY feed", (tab,))]
            return items, stat
        finally: c.close()
    except sqlite3.Error: return [], []

def build(tab, classify, feed_meta):
    """-> (items, feed_status). classify(cluster_dict) -> None | {"kind":..., "why":[...]} ."""
    c = _ro(DB)
    try: key, corpus = _corpus(c)
    finally: c.close()
    fitems, fstat = _feed_rows(tab)
    fkey = (len(fitems), fitems[0]["fetched"] if fitems else None, max([s.get("last_checked") or "" for s in fstat] or [""]))
    with _LK:
        hit = _C.get("tab_" + tab)
        if hit and hit[0] == (key, fkey) and time.time() - hit[1] < TTL: return hit[2], fstat
    byurl = {}
    for d in corpus:
        for u in d["_urls"]:
            if u: byurl.setdefault(u, d)
    items, seen = [], set()
    for d in corpus:
        m = classify(d)
        if not m: continue
        seen.add(d["cluster_id"])
        items.append({"id": d["cluster_id"], "origin": "scanner", "title": d["title"], "category": d["category"], "location": d["location"],
                      "event_time": d["event_time"], "first_seen": d["first_seen"], "updated": d["updated"], "score": d["score"], "rank": d["rank"],
                      "confidence": d["confidence"], "n_items": d["n_items"], "n_families": d["n_families"], "watchlist": d["watchlist"],
                      "list": LIST.get(d["watchlist"], "suppressed"), "unconfirmed": d["watchlist"] != 0, "brief": d["brief"],
                      "links": [{"source": l.get("source", ""), "url": l.get("url", "")} for l in d["links"][:6]],
                      "kind": m["kind"], "why": m["why"][:6], "match": m.get("match"), "sources": sorted(s for s in d["_srcs"] if s)[:6]})
    for f in fitems:
        cl = byurl.get(norm_url(f["url"]))
        if cl is not None and cl["cluster_id"] in seen: continue      # already shown as the scanner's own scored cluster
        meta = feed_meta.get(f["feed"], {})
        ex = _j(f["extra"], {})
        it = {"id": "f_" + f["id"], "origin": "feed", "feed": f["feed"], "title": f["title"], "category": meta.get("category", ""),
              "location": ex.get("location"), "event_time": f["published"], "first_seen": f["published"] or f["fetched"], "updated": f["fetched"],
              "score": None, "rank": None, "watchlist": None, "list": "feed", "unconfirmed": not meta.get("official"), "brief": f["summary"],
              "links": [{"source": meta.get("label", f["feed"]), "url": f["url"]}] + [l for l in ex.get("links", []) if isinstance(l, dict)][:3],
              "kind": f["kind"], "why": _j(f["why"]), "sources": [meta.get("label", f["feed"])], "official": bool(meta.get("official")),
              "n_items": 1, "n_families": 1}
        if cl is not None:   # same URL as a scanner alert: inherit the scanner's stored rank (never invented)
            it.update(score=cl["score"], rank=cl["rank"], watchlist=cl["watchlist"], list=LIST.get(cl["watchlist"], "suppressed"),
                      unconfirmed=cl["watchlist"] != 0, scanner_cluster=cl["cluster_id"])
        items.append(it)
    items.sort(key=lambda x: (x["first_seen"] or ""), reverse=True)
    with _LK: _C["tab_" + tab] = ((key, fkey), time.time(), items)
    return items, fstat

def summarize(items):
    by_rank = {str(r): 0 for r in range(11)}; by_rank["unscored"] = 0
    by_kind, by_list = {}, {"wire": 0, "watchlist": 0, "suppressed": 0, "feed": 0}
    for x in items:
        by_rank["unscored" if x["rank"] is None else str(x["rank"])] += 1
        by_kind[x["kind"]] = by_kind.get(x["kind"], 0) + 1
        by_list[x["list"]] = by_list.get(x["list"], 0) + 1
    ts = [x["first_seen"] for x in items if x["first_seen"]]
    return {"total": len(items), "by_rank": by_rank, "by_kind": by_kind, "by_list": by_list,
            "oldest": min(ts) if ts else None, "newest": max(ts) if ts else None}

def page(tab, classify, feed_meta, qs, title):
    g = lambda k, d="": ((qs.get(k) or [d])[0] or d)
    try:
        off = max(0, min(1_000_000, int(g("offset", "0")))); lim = max(1, min(200, int(g("limit", "60"))))
    except ValueError: return 400, {"error": "offset and limit must be integers"}
    rk, kind, src, sort, q = g("rank"), g("kind"), g("origin"), g("sort", "new"), g("q").lower()[:80]
    try: items, fstat = build(tab, classify, feed_meta)
    except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    summ = summarize(items)
    sel = items
    if rk == "unscored": sel = [x for x in sel if x["rank"] is None]
    elif rk == "7+": sel = [x for x in sel if (x["rank"] or 0) >= 7]
    elif rk.isdigit(): sel = [x for x in sel if x["rank"] == int(rk)]
    if kind: sel = [x for x in sel if x["kind"] == kind]
    if src in ("scanner", "feed"): sel = [x for x in sel if x["origin"] == src]
    if g("confirmed") == "1": sel = [x for x in sel if not x["unconfirmed"]]
    if q: sel = [x for x in sel if q in ((x["title"] or "") + " " + (x["brief"] or "")).lower()]
    if sort == "rank": sel = sorted(sel, key=lambda x: (-1 if x["rank"] is None else x["rank"], x["score"] or 0, x["first_seen"] or ""), reverse=True)
    return 200, {"tab": tab, "title": title, "summary": summ, "matching": len(sel), "offset": off, "limit": lim,
                 "items": sel[off:off + lim], "feeds": fstat, "unlisted": True, "generated": iso()}

def serve_static(name):
    if name in FILES:
        with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
    return 404, {"error": "not found"}

# ------------------------------------------------------------------ extra feeds (box collector)
SCHEMA = """CREATE TABLE IF NOT EXISTS feed_items(id TEXT PRIMARY KEY, tab TEXT, feed TEXT, title TEXT, url TEXT, summary TEXT,
  published TEXT, fetched TEXT, kind TEXT, why TEXT, extra TEXT);
CREATE INDEX IF NOT EXISTS ix_fi_tab ON feed_items(tab, published);
CREATE TABLE IF NOT EXISTS feed_status(tab TEXT, feed TEXT, label TEXT, url TEXT, ok INTEGER, items INTEGER, kept INTEGER,
  last_checked TEXT, last_ok TEXT, error TEXT, note TEXT, PRIMARY KEY(tab, feed));"""

def http(url, timeout=30, limit=12_000_000):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(r, timeout=timeout) as resp: return resp.read(limit)

def pdate(s):
    if not s: return None
    s = s.strip()
    try: return parsedate_to_datetime(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: pass
    try: return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: return None

def rss(url, limit=200):
    root = ET.fromstring(http(url)); out = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.iter("item"):
        out.append({"title": clean(it.findtext("title"), 300), "url": (it.findtext("link") or "").strip(),
                    "summary": it.findtext("description") or "", "published": pdate(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))})
    for it in root.findall("a:entry", ns):
        ln = it.find("a:link", ns)
        out.append({"title": clean(it.findtext("a:title", "", ns), 300), "url": ln.get("href") if ln is not None else "",
                    "summary": it.findtext("a:summary", "", ns) or it.findtext("a:content", "", ns), "published": pdate(it.findtext("a:updated", "", ns))})
    return out[:limit]

def fdb():
    c = sqlite3.connect(FDB, timeout=30); c.executescript(SCHEMA); return c

def store(tab, feed, label, url, items, note=""):
    """items: dicts with title,url,summary,published,kind,why,extra (already filtered by the tab's rules)."""
    c = fdb(); t = iso()
    try:
        for x in items:
            iid = hashlib.sha1(f"{tab}|{feed}|{x.get('id') or x['url'] or x['title']}".encode()).hexdigest()[:16]
            c.execute("""INSERT INTO feed_items(id,tab,feed,title,url,summary,published,fetched,kind,why,extra) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET title=excluded.title, summary=excluded.summary, kind=excluded.kind, why=excluded.why, extra=excluded.extra""",
                      (iid, tab, feed, x["title"], x["url"], clean(x.get("summary"), 600), x.get("published") or t, t, x["kind"],
                       json.dumps(x.get("why", [])), json.dumps(x.get("extra", {}))))
        c.execute("""INSERT INTO feed_status(tab,feed,label,url,ok,items,kept,last_checked,last_ok,error,note) VALUES(?,?,?,?,1,?,?,?,?,NULL,?)
                     ON CONFLICT(tab,feed) DO UPDATE SET label=excluded.label,url=excluded.url,ok=1,items=excluded.items,kept=excluded.kept,
                     last_checked=excluded.last_checked,last_ok=excluded.last_ok,error=NULL,note=excluded.note""",
                  (tab, feed, label, url, x_n(items), len(items), t, t, note))
        c.execute("DELETE FROM feed_items WHERE fetched < ? AND published < ?", (iso(time.time() - KEEP_DAYS * 86400),) * 2)
        c.commit()
    finally: c.close()
def x_n(items): return len(items)

def fail(tab, feed, label, url, err):
    c = fdb()
    try:
        c.execute("""INSERT INTO feed_status(tab,feed,label,url,ok,items,kept,last_checked,error) VALUES(?,?,?,?,0,0,0,?,?)
                     ON CONFLICT(tab,feed) DO UPDATE SET ok=0,last_checked=excluded.last_checked,error=excluded.error""",
                  (tab, feed, label, url, iso(), str(err)[:300]))
        c.commit()
    finally: c.close()

def collect_all():
    import aithreats, gridwatch
    for mod in (aithreats, gridwatch):
        for name, meta in mod.FEEDS.items():
            try:
                items, note = meta["fn"]()
                store(mod.TAB, name, meta["label"], meta["url"], items, note)
                log(f"{mod.TAB}/{name}: {len(items)} kept {note}")
            except Exception as ex:
                fail(mod.TAB, name, meta["label"], meta["url"], f"{type(ex).__name__}: {ex}")
                log(f"{mod.TAB}/{name}: FAILED {type(ex).__name__}: {ex}")

def loop(every_s=900):
    while True:
        t0 = time.time()
        try: collect_all()
        except Exception as ex: log(f"cycle error {ex}")
        time.sleep(max(60, every_s - (time.time() - t0)))

if __name__ == "__main__":
    sys.path.insert(0, BASE)
    cmd = (sys.argv[1:] or ["once"])[0]
    if cmd == "loop": loop()
    else: collect_all()
