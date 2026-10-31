"""Shared helpers for the SpaceX and Elon Musk add-on tabs (spacex.py, elon.py): polite HTTP, a TTL cache that keeps the last good
payload in a sidecar SQLite file, Google News / RSS parsing, and a read-only keyword search of the scanner's alerts (blackout.db, mode=ro).
Never writes blackout.db and never changes scores."""
import builtins, gzip, json, os, re, sqlite3, threading, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET_XML
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__)); BDB = "file:" + os.path.join(BASE, "blackout.db") + "?mode=ro"
UA = "Mozilla/5.0 (compatible; blackout.network dashboard; cached polite poll)"
ST = getattr(builtins, "_bn_feeds", None)
if ST is None: ST = builtins._bn_feeds = {"mem": {}, "locks": {}, "err": {}}
_g = threading.Lock()

def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

def http(url, timeout=25, accept="application/json", limit=20_000_000):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"}), timeout=timeout)
    b = r.read(limit)
    return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b

def getjson(url, timeout=25): return json.loads(http(url, timeout))

def _db(path):
    c = sqlite3.connect(path, timeout=15); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY, ts REAL, payload TEXT)"); return c

def cached(dbpath, key, ttl, fn, force=False):
    mk = dbpath + "|" + key; m = ST["mem"].get(mk)
    if m and not force and time.time() - m[0] < ttl: return m[1]
    with _g: lk = ST["locks"].setdefault(mk, threading.Lock())
    with lk:
        m = ST["mem"].get(mk)
        if m and not force and time.time() - m[0] < ttl: return m[1]
        if not m:
            try:
                c = _db(dbpath); r = c.execute("SELECT ts, payload FROM cache WHERE k=?", (key,)).fetchone(); c.close()
                if r: m = (r["ts"], json.loads(r["payload"])); ST["mem"][mk] = m
                if m and not force and time.time() - m[0] < ttl: return m[1]
            except Exception: pass
        fl = ST.setdefault("fail", {}).get(mk)
        if not force and fl and time.time() - fl < min(ttl, 900):     # back off after a failure (no hammering a down/403ing source)
            return (dict(m[1], stale=True) if m and isinstance(m[1], dict) else (m[1] if m else None))
        try:
            v = fn(); now = time.time(); ST["fail"].pop(mk, None); ST["mem"][mk] = (now, v); ST["err"].pop(mk, None)
            try: c = _db(dbpath); c.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, now, json.dumps(v))); c.commit(); c.close()
            except Exception: pass
            return v
        except Exception as ex:
            ST["fail"][mk] = time.time()
            ST["err"][mk] = f"{type(ex).__name__}: {str(ex)[:160]}"
            if m:
                v = m[1]
                return dict(v, stale=True, stale_since=iso(datetime.fromtimestamp(m[0], timezone.utc))) if isinstance(v, dict) else v
            return None

def errors(dbpath): return {k.split("|", 1)[1]: v for k, v in ST["err"].items() if k.startswith(dbpath + "|")}

TAG = re.compile(r"<[^>]+>")
def rss(url, limit=40):
    root = ET_XML.fromstring(http(url, accept="application/rss+xml, application/xml"))
    out = []
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip(); src = it.find("source")
        pub = it.findtext("pubDate")
        try: ts = iso(parsedate_to_datetime(pub).astimezone(timezone.utc)) if pub else None
        except Exception: ts = None
        sname = (src.text or "").strip() if src is not None else ""
        if sname and t.endswith(" - " + sname): t = t[: -len(sname) - 3]
        summ = TAG.sub(" ", it.findtext("description") or "").replace("&nbsp;", " ").strip()
        if summ.startswith(t[:40]): summ = ""
        out.append({"title": t, "url": (it.findtext("link") or "").strip(), "source": sname, "time": ts, "summary": summ[:300]})
        if len(out) >= limit: break
    return out

def gnews(q, limit=40):
    return rss("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}), limit)

def dedupe(items):
    seen = set(); out = []
    for x in items:
        k = re.sub(r"[^a-z0-9]+", " ", (x.get("title") or "").lower()).strip()[:70]
        if not k or k in seen: continue
        seen.add(k); out.append(x)
    return out

def scanner_mentions(pattern, days=14, limit=30):
    """Read-only: The Wire (watchlist=0) and Watchlist (watchlist=1) clusters whose title or brief matches a regex."""
    rx = re.compile(pattern, re.I); cut = iso(datetime.now(timezone.utc) - timedelta(days=days))
    try:
        c = sqlite3.connect(BDB, uri=True, timeout=10); c.row_factory = sqlite3.Row
        rows = c.execute("SELECT cluster_id, title, category, location, event_time, first_seen, updated, score, rank, confidence, n_families, links, watchlist, brief "
                         "FROM clusters WHERE watchlist IN (0,1) AND COALESCE(updated, first_seen)>=? ORDER BY COALESCE(updated, first_seen) DESC LIMIT 4000", (cut,)).fetchall()
        c.close()
    except Exception as ex: return {"error": str(ex)[:160], "items": []}
    out = []
    for r in rows:
        if not rx.search((r["title"] or "") + " " + (r["brief"] or "")): continue
        try: links = json.loads(r["links"] or "[]")
        except Exception: links = []
        url = (links[0].get("url") if links and isinstance(links[0], dict) else (links[0] if links and isinstance(links[0], str) else None))
        out.append({"cid": r["cluster_id"], "title": r["title"], "category": r["category"], "location": r["location"], "time": r["event_time"] or r["first_seen"],
                    "updated": r["updated"], "score": r["score"], "rank": r["rank"], "confidence": r["confidence"], "sources": r["n_families"],
                    "list": "Watchlist" if r["watchlist"] == 1 else "The Wire", "url": url})
        if len(out) >= limit: break
    return {"items": out, "days": days}
