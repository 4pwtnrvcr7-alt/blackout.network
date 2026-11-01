#!/usr/bin/env python3
"""Trends archive backfill (t226). Builds trends_history.db: REAL historical items from public archive APIs, for the Trends tab only.

* Never writes blackout.db (opened read-only with file:blackout.db?mode=ro only to find the live-history start and dedupe).
* Never modifies scanner.py: it is imported read-only. Its own fetchers (f_usgs, f_who, f_cisa_kev, f_eonet, f_nws, f_swpc) are run
  in THIS process with scanner.get pointed at each source's archive endpoint (same JSON format as the live feed) and HISTORY_D widened,
  so items, base scores and ids are exactly what the live scanner would have produced. GDACS and GFZ Kp (different archive formats)
  use small converters that copy the scanner's base formulas. RSS sources reuse scanner.rss_generic with the scanner's own arguments.
* Items are clustered with scanner.matches (same 12 h window idea as assign_clusters) and every story is scored and ranked by running
  scanner.rebuild_cluster -> rank_cluster on a scratch database built with scanner's own schema (scanner.db() against a temp file).
* Everything stored here is flagged origin='archive backfill'. Only stories BEFORE the live scanner's first story (the seam) are kept,
  and any item the live scanner already holds (same id / same GDACS event / CVE / WHO DON / EONET id) is dropped, so nothing is
  counted twice. Nothing here reaches The Wire, the alert bar, pushes or newsletters: only trends.py reads this DB.
Usage: python3 trends_backfill.py [--days 730]"""
import os, sys, json, time, sqlite3, tempfile, argparse, traceback, types
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
OUT = os.path.join(BASE, "trends_history.db")
import scanner as S          # read-only import; module globals are patched only inside this process

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def months(a, b, step_days=30):
    t = a
    while t < b:
        u = min(b, t + timedelta(days=step_days)); yield t, u; t = u

class Resp:
    def __init__(self, obj=None, text=None): self._o = obj; self.text = text if text is not None else json.dumps(obj); self.content = self.text.encode()
    def json(self): return self._o if self._o is not None else json.loads(self.text)
ORIG_GET = S.get
CACHE = os.environ.get("BN_BF_CACHE", "/tmp/bn_backfill_cache"); os.makedirs(CACHE, exist_ok=True)
def fetch(url, **kw):
    """GET with retries and a local response cache (so reruns don't re-download the same archive pages)."""
    import hashlib
    cf = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(cf) and time.time() - os.path.getmtime(cf) < 86400:
        return Resp(text=open(cf, encoding="utf-8").read())
    to = kw.pop("timeout", 90)
    for i in range(3):
        try:   # curl: some archive hosts (GDACS) drop python-requests TLS handshakes with SSL EOF; curl to the same URL works
            import subprocess
            hd = sum((["-H", f"{k}: {v}"] for k, v in {**S.UA, **kw.get("headers", {})}.items()), [])
            p = subprocess.run(["curl", "-sS", "-L", "--fail", "-m", str(to), "--compressed", *hd, url], capture_output=True, timeout=to + 10)
            if p.returncode != 0: raise RuntimeError(f"curl exit {p.returncode}: {p.stderr.decode(errors='replace')[:150]}")
            txt = p.stdout.decode("utf-8", errors="replace")
            with open(cf, "w", encoding="utf-8") as f: f.write(txt)
            return Resp(text=txt)
        except Exception as ex:
            if i == 2: raise
            log("retry", url[:100], str(ex)[:120]); time.sleep(5 * (i + 1))

SRC = {}   # name -> dict(status, url, items, earliest, latest, note)
def note(name, url, items, status="ok", msg=""):
    ts = sorted(i["event_time"] for i in items if i.get("event_time"))
    SRC[name] = {"url": url, "status": status, "items": len(items), "earliest": ts[0] if ts else None, "latest": ts[-1] if ts else None, "note": msg}
    log(f"{name}: {status} {len(items)} items {ts[0] if ts else ''} .. {ts[-1] if ts else ''} {msg}")

def run(name, url, fn):
    try:
        items = fn(); note(name, url, items); return items
    except Exception as ex:
        traceback.print_exc(); note(name, url, [], "failed", f"{type(ex).__name__}: {str(ex)[:200]}"); return []

# ---------------------------------------------------------------- sources
def usgs(a, b):
    out = []
    for t0, t1 in months(a, b, 30):
        q = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={iso(t0)}&endtime={iso(t1)}&orderby=time-asc"
        big = fetch(q + "&minmagnitude=4.5").json()
        sig = fetch(q + "&maxmagnitude=4.4999&minsig=600").json()   # the live significant_day feed's sub-4.5 quakes (sig >= 600)
        def g(url, **kw): return Resp(sig if "significant" in url else big)
        S.get = g
        try: out += S.f_usgs()
        finally: S.get = ORIG_GET
    return out

def who(a, b):
    vals = []
    for skip in range(0, 2000, 100):        # the API caps $top at 100; page back until we pass the start date
        v = fetch(f"https://www.who.int/api/news/diseaseoutbreaknews?$orderby=PublicationDate%20desc&$top=100&$skip={skip}").json().get("value") or []
        vals += v
        if not v or (S.parse_t(v[-1].get("PublicationDate")) or a) < a: break
    j = {"value": vals}
    S.get = lambda url, **kw: Resp(j)
    try: return S.f_who()
    finally: S.get = ORIG_GET

def kev(a, b):
    j = fetch("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json").json()
    S.get = lambda url, **kw: Resp(j)
    try: return S.f_cisa_kev()
    finally: S.get = ORIG_GET

def eonet(a, b):
    out, seen = [], set()
    for t0, t1 in months(a, b, 30):
        j = fetch(f"https://eonet.gsfc.nasa.gov/api/v3/events?status=all&start={t0:%Y-%m-%d}&end={t1:%Y-%m-%d}").json()
        S.get = lambda url, **kw: Resp(j)
        try:
            for it in S.f_eonet():
                if it["id"] not in seen: seen.add(it["id"]); out.append(it)
        finally: S.get = ORIG_GET
    return out

def nws(a, b):
    # api.weather.gov keeps only about a week of issued alerts; take whatever it still serves
    feats, url = [], f"https://api.weather.gov/alerts?start={iso(a)}&end={iso(b)}&severity=Extreme,Severe&limit=500"
    for _ in range(40):
        j = fetch(url, headers={"Accept": "application/geo+json"}).json()
        feats += j.get("features") or []
        nxt = ((j.get("pagination") or {}).get("next"))
        if not nxt or not j.get("features"): break
        url = nxt
    S.get = lambda url, **kw: Resp({"features": feats})
    try: return S.f_nws()
    finally: S.get = ORIG_GET

def swpc(a, b):
    j = fetch("https://services.swpc.noaa.gov/products/alerts.json").json()
    S.get = lambda url, **kw: Resp(j if "alerts" in url else [])
    try: return S.f_swpc()[0]
    finally: S.get = ORIG_GET

def gfz_kp(a, b):
    """GFZ Potsdam definitive/nowcast Kp (3-hourly). Same item the scanner's f_swpc emits when Kp >= 5 (one per 3-hour Kp value)."""
    out = []
    for t0, t1 in months(a, b, 180):
        j = fetch(f"https://kp.gfz.de/app/json/?start={iso(t0)}&end={iso(t1)}&index=Kp").json()
        for tt, kp in zip(j.get("datetime") or [], j.get("Kp") or []):
            if kp is None or kp < 5: continue
            g = int(min(5, kp - 4)); kp = round(kp, 2)
            out.append(S.item("NOAA SWPC Kp", "NOAA", f"kp|{tt}", f"Planetary Kp index {kp} (G{g} storm level)", "space weather",
                              "https://kp.gfz.de/en/data", S.parse_t(tt), None, None, "Global (Earth)", 15 + g * 15,
                              extra={"kp": kp, "archive": "GFZ Potsdam Kp"}))
    return out

def gdacs(a, b):
    """GDACS event archive API (geteventlist/SEARCH). Base score copied from scanner.f_gdacs (alert level; the population bump needs a
    per-event call and is not applied). Same id format as the live RSS items."""
    out, seen = [], set()
    for t0, t1 in months(a, b, 15):
        for page in range(1, 40):
            txt = fetch(f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=EQ;TC;FL;VO;DR;WF&fromDate={t0:%Y-%m-%d}"
                        f"&toDate={t1:%Y-%m-%d}&alertlevel=green;orange;red&pagesize=100&pagenumber={page}").text
            if not txt.strip(): break                     # GDACS answers past the last page with an empty body
            fs = json.loads(txt).get("features") or []
            before = len(seen)
            for f in fs:
                p = f["properties"]; key = f"{p.get('eventtype')}{p.get('eventid')}"
                t = S.parse_t((p.get("fromdate") or "") + "Z")
                if key in seen or not t or not (a <= t < b): continue
                seen.add(key)
                lvl = (p.get("alertlevel") or "").lower()
                base = {"green": 15, "orange": 50, "red": 75}.get(lvl, 15)
                lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
                sev = (p.get("severitydata") or {}).get("severity")
                et = p.get("eventtype")
                title = f"{lvl.title() or 'Green'} alert: {p.get('name') or p.get('eventname')}" + (f" ({(p.get('severitydata') or {}).get('severitytext')})" if (p.get('severitydata') or {}).get('severitytext') else "")
                out.append(S.item("GDACS", "GDACS", f"{et}{p.get('eventid')}|{p.get('episodeid')}", title, "natural disaster",
                                  (p.get("url") or {}).get("report"), t, lat, lon, p.get("country"), base,
                                  extra={"alertlevel": lvl, "eventtype": et, "eventid": str(p.get("eventid")),
                                         "mag": float(sev) if (sev and et == "EQ") else None, "population": None, "archive": "GDACS event API"}))
            if len(fs) < 100 or len(seen) == before and page > 1: break
    log("GDACS window", t1.date(), len(out))
    return out

def rss(name, fam, url, cat, base, official, force_cat=False, kwboost=None):
    return lambda a, b: S.rss_generic(name, fam, url, cat, base, official, maxage_d=4000, force_cat=force_cat, kwboost=kwboost)

def cidrap(a, b):
    out, seen = [], set()
    for nm, tid in S.CIDRAP_TOPICS.items():
        for it in S.rss_generic("CIDRAP News", "CIDRAP", f"https://www.cidrap.umn.edu/news/{tid}/rss", "disease", 20, True, maxage_d=4000, force_cat=True,
                                kwboost=r"ebola|marburg|bundibugyo|h5n1|avian flu|outbreak|novel|pandemic|nipah|mpox"):
            if it["id"] not in seen: seen.add(it["id"]); out.append(it)
    return out

def donki_flares(a, b):
    raise RuntimeError("not attempted")

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=730); args = ap.parse_args()
    lc = sqlite3.connect(f"file:{os.path.join(BASE, 'blackout.db')}?mode=ro", uri=True, timeout=30)
    seam = S.parse_t(lc.execute("SELECT MIN(first_seen) FROM clusters").fetchone()[0])
    live_ids = {r[0] for r in lc.execute("SELECT id FROM alerts")}
    live_keys = set()
    for src, ex, title in lc.execute("SELECT source, extra, title FROM alerts"):
        try: e = json.loads(ex or "{}")
        except Exception: e = {}
        if e.get("eventid"): live_keys.add(("GDACS", str(e.get("eventtype")) + str(e["eventid"])))
        if e.get("don_id"): live_keys.add(("WHO", str(e["don_id"])))
    lc.close()
    start = (seam - timedelta(days=args.days)).replace(hour=0, minute=0, second=0, microsecond=0)
    S.HISTORY_D = (datetime.now(timezone.utc) - start).days + 2      # widen the fetchers' recency filters (this process only)
    log("seam", iso(seam), "start", iso(start))
    plan = [
        ("USGS earthquakes (FDSN event archive, M4.5+ and significant)", "https://earthquake.usgs.gov/fdsnws/event/1/", usgs),
        ("GDACS event archive", "https://www.gdacs.org/gdacsapi/", gdacs),
        ("NASA EONET v3 (open + closed events)", "https://eonet.gsfc.nasa.gov/api/v3/events", eonet),
        ("WHO Disease Outbreak News API", "https://www.who.int/api/news/diseaseoutbreaknews", who),
        ("CISA KEV catalog (dateAdded)", "https://www.cisa.gov/known-exploited-vulnerabilities-catalog", kev),
        ("GFZ Potsdam Kp index (Kp >= 5)", "https://kp.gfz.de/en/data", gfz_kp),
        ("NOAA SWPC alerts archive (alerts.json)", "https://services.swpc.noaa.gov/products/alerts.json", swpc),
        ("NWS alerts API (Severe/Extreme)", "https://api.weather.gov/alerts", nws),
        ("CIDRAP topic RSS", "https://www.cidrap.umn.edu/rss-feeds", cidrap),
        ("CISA Advisories RSS", "https://www.cisa.gov/cybersecurity-advisories/all.xml",
         rss("CISA Advisories", "CISA", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "cyber", 20, True, True,
             r"emergency directive|actively exploited|critical infrastructure|nation-state|ransomware")),
        ("ReliefWeb Disasters RSS", "https://reliefweb.int/disasters/rss.xml",
         rss("ReliefWeb Disasters", "ReliefWeb", "https://reliefweb.int/disasters/rss.xml", "natural disaster", 35, True)),
    ]
    allit = []
    for name, url, fn in plan:
        items = run(name, url, lambda fn=fn: fn(start, seam))
        kept = []
        for it in items:
            t = S.parse_t(it.get("event_time"))
            if not t or not (start <= t < seam): continue
            if it["id"] in live_ids: continue
            e = json.loads(it["extra"] or "{}")
            if it["family"] == "GDACS" and ("GDACS", str(e.get("eventtype")) + str(e.get("eventid"))) in live_keys: continue
            if it["family"] == "WHO" and ("WHO", str(e.get("don_id"))) in live_keys: continue
            kept.append(it)
        SRC[name]["kept"] = len(kept)
        ts = sorted(i["event_time"] for i in kept)
        SRC[name]["kept_earliest"] = ts[0] if ts else None
        allit += kept
    for name, url, msg in [
        ("ProMED", "https://promedmail.org/", "subscription platform; no public archive API or feed (also in scanner FAILED_SOURCES)"),
        ("EpiWatch", "https://www.epiwatch.org/", "JavaScript app, no public machine-readable archive"),
        ("ReliefWeb API v2", "https://api.reliefweb.int/v2/", "HTTP 403: requires a registered appname (registration not allowed for this job)"),
        ("NASA DONKI solar flares", "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR", "kauai.ccmc.gsfc.nasa.gov unreachable from the box (egress); api.nasa.gov DEMO_KEY returned 503"),
        ("Telegram / news / social history", "https://t.me/s/", "not backfilled: no archive API; war/conflict, political, UFO, financial and religious categories start with the live scanner")]:
        SRC[name] = {"url": url, "status": "unavailable", "items": 0, "kept": 0, "earliest": None, "latest": None, "kept_earliest": None, "note": msg}
    # dedupe ids across sources
    uniq = {}
    for it in allit: uniq.setdefault(it["id"], it)
    allit = sorted(uniq.values(), key=lambda x: x["event_time"])
    log("items kept", len(allit))

    # ---- cluster + score with the scanner's own code on a scratch DB
    tmpd = tempfile.mkdtemp(prefix="bn_bf_"); scratch = os.path.join(tmpd, "scratch.db")
    S.DB = scratch; c = S.db(); c.execute("PRAGMA journal_mode=OFF"); c.execute("PRAGMA synchronous=OFF")
    for it in allit:
        c.execute("INSERT INTO alerts VALUES(:id,:source,:family,:title,:category,:source_url,:event_time,:lat,:lon,:location,:base,:official,:extra,:event_time,:event_time,NULL)", it)
    # assign clusters like scanner.assign_clusters, with a pool limited to the matching window around each item's own time
    rows = [dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY event_time")]
    win = timedelta(hours=S.WINDOW_H * 2 + 24); pool = []; j0 = 0; cid_of = {}
    for n in rows:
        tn = S.parse_t(n["event_time"])
        while j0 < len(pool) and S.parse_t(pool[j0]["event_time"]) < tn - win: j0 += 1
        cid = None
        for o in pool[j0:]:
            if S.matches(n, o): cid = cid_of[o["id"]]; break
        cid_of[n["id"]] = cid or n["id"]; pool.append(n)
    c.executemany("UPDATE alerts SET cluster_id=? WHERE id=?", [(v, k) for k, v in cid_of.items()])
    cids = sorted(set(cid_of.values())); log("stories", len(cids))
    for i, cid in enumerate(cids):
        S.rebuild_cluster(c, cid)
        if i % 5000 == 0: log("scored", i)
    c.commit()

    # ---- write trends_history.db atomically
    tmp = OUT + ".tmp"
    if os.path.exists(tmp): os.unlink(tmp)
    o = sqlite3.connect(tmp)
    o.executescript("""
    CREATE TABLE stories(id TEXT PRIMARY KEY, t TEXT NOT NULL, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL,
      score INTEGER, rank INTEGER, confidence TEXT, watchlist INTEGER, n_items INTEGER, families TEXT, links TEXT, sources TEXT,
      origin TEXT NOT NULL DEFAULT 'archive backfill');
    CREATE INDEX ix_st_t ON stories(t, id);
    CREATE TABLE sources(name TEXT PRIMARY KEY, url TEXT, status TEXT, fetched INTEGER, kept INTEGER, earliest TEXT, latest TEXT, kept_earliest TEXT, note TEXT);
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);""")
    n = 0
    for r in c.execute("SELECT * FROM clusters"):
        srcs = sorted({x[0] for x in c.execute("SELECT DISTINCT source FROM alerts WHERE cluster_id=?", (r["cluster_id"],))})
        o.execute("INSERT INTO stories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'archive backfill')",
                  (r["cluster_id"], r["event_time"] or r["first_seen"], r["title"], r["category"], r["location"], r["lat"], r["lon"], r["score"], r["rank"],
                   r["confidence"], r["watchlist"], r["n_items"], r["families"], r["links"], json.dumps(srcs)))
        n += 1
    for k, v in SRC.items():
        o.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)", (k, v["url"], v["status"], v["items"], v.get("kept", 0), v["earliest"], v["latest"], v.get("kept_earliest"), v["note"]))
    for k, v in {"seam": iso(seam), "start": iso(start), "built": iso(datetime.now(timezone.utc)), "items": str(len(allit)), "stories": str(n),
                 "method": "scanner.py fetchers/rss_generic + scanner.matches clustering + scanner.rebuild_cluster/rank_cluster on a scratch DB"}.items():
        o.execute("INSERT INTO meta VALUES(?,?)", (k, v))
    o.commit(); o.execute("VACUUM"); o.close(); c.close()
    os.replace(tmp, OUT)
    for f in os.listdir(tmpd): os.unlink(os.path.join(tmpd, f))
    os.rmdir(tmpd)
    log("wrote", OUT, n, "stories", os.path.getsize(OUT), "bytes")

if __name__ == "__main__": main()
