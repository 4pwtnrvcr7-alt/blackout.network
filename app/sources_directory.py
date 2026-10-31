#!/usr/bin/env python3
"""blackout.network global Sources directory (2026-10-31).
Hundreds of thousands of REAL reference sources imported from published registries (ROR, Wikidata, WMO OSCAR, FDSN station services,
CelesTrak SATCAT, NOAA NDBC/NCEI radar list, USGS Water Services, FIRST.org, Radio Browser, data.europa.eu). Each row keeps its real URL and
the registry it came from. These are DIRECTORY / REFERENCE entries: the scanner does not read them (scanner.py, scoring, config.json untouched).
Data ships as gzipped NDJSON shards in sources_dir_data/ (built offline by the box from open downloads) and is loaded into a local SQLite + FTS5
index at sources_dir/directory.db (built at Docker build time, or lazily in the background on first use). Read-only for the public.
Row format: [sid, name, url, category, kind, country_iso2, registry, detail(, link_checked_date)]."""
import os, sys, json, glob, gzip, sqlite3, threading, time, hashlib, re
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "sources_dir_data")
DBDIR = os.path.join(BASE, "sources_dir")
DBF = os.path.join(DBDIR, "directory.db")
_lock = getattr(sys, "_bn_srcdir_lock", None)
if _lock is None: _lock = sys._bn_srcdir_lock = threading.Lock()
STATE = getattr(sys, "_bn_srcdir_state", None)
if STATE is None: STATE = sys._bn_srcdir_state = {"building": False, "error": None}

# Prior mean (1-5 stars) for the reliability grade, by registry/category. Official observing networks and registries start higher.
PRIOR_REG = {"WMO OSCAR/Surface": 4.2, "NOAA NDBC": 4.2, "NOAA NCEI HOMR (NEXRAD/TDWR)": 4.3, "USGS Water Services": 4.2, "CelesTrak SATCAT": 4.0,
             "FIRST.org": 4.0, "data.europa.eu": 3.9, "ROR": 3.8, "Radio Browser": 3.0, "RIPE Atlas": 4.0, "NOAA CO-OPS": 4.3, "EUMETNET OPERA": 4.3, "blackout.network curated (verified link)": 3.6}
PRIOR_CAT = {"Government & public agencies": 3.9, "Police & law enforcement": 3.8, "Emergency management": 3.9, "Security & cyber": 3.7,
             "Weather, radar & ocean": 4.0, "Satellites & space": 3.9, "Seismic, volcanic & geophysical": 4.0, "Research & academia": 3.8,
             "News & media": 3.3, "Scanner & public-safety audio": 3.0, "Health & medical institutions": 3.8, "Local government": 3.7, "Government data feeds": 3.9, "Internet outage sensors": 4.0}
def prior_registry(reg, cat):
    if reg.startswith("FDSN"): return 3.4 if "raspberryshake" in reg else 4.1
    return PRIOR_REG.get(reg) or PRIOR_CAT.get(cat, 3.5)

def data_id():
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(DATA, "part-*.ndjson.gz"))): h.update(os.path.basename(f).encode()); h.update(str(os.path.getsize(f)).encode())
    mf = os.path.join(DATA, "meta.json")
    if os.path.exists(mf): h.update(open(mf, "rb").read())
    return h.hexdigest()[:16]

def build(quiet=False):
    os.makedirs(DBDIR, exist_ok=True)
    tmp = DBF + ".building"
    for f in (tmp, tmp + "-journal"):
        if os.path.exists(f): os.unlink(f)
    c = sqlite3.connect(tmp); t0 = time.time()
    c.executescript("""PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA page_size=4096;
      CREATE TABLE d(id INTEGER PRIMARY KEY, sid TEXT UNIQUE, name TEXT, url TEXT, cat TEXT, kind TEXT, cc TEXT, reg TEXT, detail TEXT, checked TEXT);
      CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);""")
    n = 0
    for f in sorted(glob.glob(os.path.join(DATA, "part-*.ndjson.gz"))):
        with gzip.open(f, "rt", encoding="utf-8") as g:
            batch = []
            for line in g:
                r = json.loads(line); batch.append((r + [None])[:9])
                if len(batch) >= 20000: c.executemany("INSERT OR IGNORE INTO d(sid,name,url,cat,kind,cc,reg,detail,checked) VALUES(?,?,?,?,?,?,?,?,?)", batch); n += len(batch); batch = []
            if batch: c.executemany("INSERT OR IGNORE INTO d(sid,name,url,cat,kind,cc,reg,detail,checked) VALUES(?,?,?,?,?,?,?,?,?)", batch); n += len(batch)
    c.executescript("""CREATE INDEX ix_cat ON d(cat, name COLLATE NOCASE); CREATE INDEX ix_cc ON d(cc); CREATE INDEX ix_reg ON d(reg); CREATE INDEX ix_name ON d(name COLLATE NOCASE);
      CREATE VIRTUAL TABLE f USING fts5(name, url, kind, detail, content='d', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
      INSERT INTO f(rowid, name, url, kind, detail) SELECT id, name, url, kind, detail FROM d;""")
    fac = {"cat": c.execute("SELECT cat, COUNT(*) FROM d GROUP BY cat ORDER BY 2 DESC").fetchall(),
           "reg": c.execute("SELECT reg, COUNT(*) FROM d GROUP BY reg ORDER BY 2 DESC").fetchall(),
           "cc": c.execute("SELECT cc, COUNT(*) FROM d WHERE cc!='' GROUP BY cc ORDER BY 2 DESC").fetchall()}
    meta = {}
    try: meta = json.load(open(os.path.join(DATA, "meta.json")))
    except Exception: pass
    total = c.execute("SELECT COUNT(*) FROM d").fetchone()[0]
    c.executemany("INSERT INTO meta VALUES(?,?)", [("data_id", data_id()), ("facets", json.dumps(fac)), ("total", str(total)), ("built", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                                                    ("source_meta", json.dumps(meta))])
    c.commit(); c.execute("PRAGMA optimize"); c.close()
    os.replace(tmp, DBF)
    if not quiet: print(f"directory.db: {total:,} rows in {time.time() - t0:.0f}s, {os.path.getsize(DBF) / 1e6:.0f} MB")
    return total

def ready():
    if not os.path.exists(DBF): return False
    try:
        c = sqlite3.connect(f"file:{DBF}?mode=ro", uri=True); v = c.execute("SELECT v FROM meta WHERE k='data_id'").fetchone(); c.close()
        return bool(v) and v[0] == _data_id_cached()
    except Exception: return False
_did = {}
def _data_id_cached():
    t = time.time()
    if not _did or t - _did["t"] > 300: _did.update(v=data_id(), t=t)
    return _did["v"]

def _build_dir():
    try: build(quiet=True); STATE["error"] = None
    except Exception as ex: STATE["error"] = str(ex)[:200]; print("sources directory build failed:", ex, flush=True)
    finally: STATE["building"] = False; _lock.release()

def ensure():
    """True when the index is usable; otherwise starts a background build (once) and returns False."""
    if ready(): return True
    if os.path.exists(DBF) and STATE["building"]: return True   # stale but usable while the new one builds
    if _lock.acquire(blocking=False):
        STATE["building"] = True
        threading.Thread(target=_build_dir, name="srcdir-build", daemon=True).start()
    return os.path.exists(DBF)

def con():
    c = sqlite3.connect(f"file:{DBF}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c

def _meta():
    c = con()
    try: m = dict(c.execute("SELECT k, v FROM meta").fetchall())
    finally: c.close()
    return {"total": int(m.get("total") or 0), "facets": json.loads(m.get("facets") or "{}"), "built": m.get("built"), "source_meta": json.loads(m.get("source_meta") or "{}")}
_mc = {}
def meta():
    if not ensure(): return None
    t = time.time()
    if not _mc or t - _mc["t"] > 120: _mc.update(v=_meta(), t=t)
    return _mc["v"]

# ---------------------------------------------------------------- helpers used by votes.py (grades)
_cat_cache = {}
def _catalog_map():
    t = time.time()
    if not _cat_cache or t - _cat_cache["t"] > 120:
        m = {}
        try:
            c = sqlite3.connect(f"file:{os.path.join(BASE, 'sources.db')}?mode=ro", uri=True, timeout=10)
            for key, rating in c.execute("SELECT key, rating FROM sources"): m["c:" + hashlib.sha1(key.encode()).hexdigest()[:16]] = rating
            c.close()
        except Exception: pass
        _cat_cache.update(v=m, t=t)
    return _cat_cache["v"]
def catalog_sid(key): return "c:" + hashlib.sha1(key.encode()).hexdigest()[:16]
def catalog_rating(sid): return _catalog_map().get(sid)
def source_exists(sid):
    if sid.startswith("c:"): return sid in _catalog_map()
    if not ensure(): raise RuntimeError("loading")
    c = con()
    try: return c.execute("SELECT 1 FROM d WHERE sid=?", (sid[2:],)).fetchone() is not None
    finally: c.close()
def prior_for(sid):
    c = con()
    try: r = c.execute("SELECT reg, cat FROM d WHERE sid=?", (sid[2:],)).fetchone()
    finally: c.close()
    return prior_registry(r["reg"], r["cat"]) if r else 3.5

def votes_mod():
    """votes.py (owner of votes.db); reloaded if an older copy without source grades is still in memory (hot-reload servers)."""
    import importlib, votes as V
    if not hasattr(V, "source_grades"): V = importlib.reload(V)
    return V

# ---------------------------------------------------------------- public query API: GET /api/sources/directory
def fts_query(q):
    toks = re.findall(r"[\w][\w.\-']*", q, re.U)[:8]
    return " ".join('"' + t.replace('"', "") + '"*' for t in toks)
def query(qs):
    g = lambda k, d="": ((qs.get(k) or [d])[0] or d)
    if not ensure(): return 503, {"error": "The global directory is being prepared. Try again in a minute.", "building": True}
    V = votes_mod()
    where, args = [], []
    q = g("q").strip()[:80]
    for k, col in (("cat", "cat"), ("cc", "cc"), ("reg", "reg")):
        v = g(k).strip()[:120]
        if v: where.append(f"d.{col}=?"); args.append(v)
    try: page = max(1, min(100000, int(g("page", "1"))))
    except Exception: page = 1
    try: per = max(10, min(100, int(g("per", "50"))))
    except Exception: per = 50
    rated = g("rated") == "1"
    c = con()
    try:
        if rated:
            rid = V.rated_ids()
            sids = [s[2:] for s, n, sm in rid if s.startswith("d:")]
            if not sids: total, rows = 0, []
            else:
                w = " AND ".join(where + [f"d.sid IN ({','.join('?' * len(sids))})"])
                if q: w += " AND d.id IN (SELECT rowid FROM f WHERE f MATCH ?)"
                a = args + sids + ([fts_query(q)] if q else [])
                total = c.execute(f"SELECT COUNT(*) FROM d WHERE {w}", a).fetchone()[0]
                rows = c.execute(f"SELECT d.* FROM d WHERE {w} ORDER BY d.name COLLATE NOCASE LIMIT ? OFFSET ?", a + [per, (page - 1) * per]).fetchall()
        elif q and fts_query(q):
            w = " AND ".join(["f MATCH ?"] + where)
            a = [fts_query(q)] + args
            total = c.execute(f"SELECT COUNT(*) FROM f JOIN d ON d.id=f.rowid WHERE {w}", a).fetchone()[0]
            rows = c.execute(f"SELECT d.* FROM f JOIN d ON d.id=f.rowid WHERE {w} ORDER BY rank LIMIT ? OFFSET ?", a + [per, (page - 1) * per]).fetchall()
        else:
            w = (" WHERE " + " AND ".join(where)) if where else ""
            m = meta()
            if not where: total = m["total"]
            elif len(where) == 1 and g("cat"): total = dict((k, v) for k, v in m["facets"].get("cat", [])).get(g("cat"), 0)
            elif len(where) == 1 and g("reg"): total = dict((k, v) for k, v in m["facets"].get("reg", [])).get(g("reg"), 0)
            elif len(where) == 1 and g("cc"): total = dict((k, v) for k, v in m["facets"].get("cc", [])).get(g("cc"), 0)
            else: total = c.execute(f"SELECT COUNT(*) FROM d{w}", args).fetchone()[0]
            order = "d.cat, d.name COLLATE NOCASE" if not where else "d.name COLLATE NOCASE"
            if g("cat") and len(where) == 1: order = "d.cat, d.name COLLATE NOCASE"
            rows = c.execute(f"SELECT d.* FROM d{w} ORDER BY {order} LIMIT ? OFFSET ?", args + [per, (page - 1) * per]).fetchall()
    finally: c.close()
    voter = g("voter"); voter = voter if re.fullmatch(r"[a-f0-9]{32}", voter) else None
    items = [{"sid": "d:" + r["sid"], "name": r["name"], "url": r["url"], "cat": r["cat"], "kind": r["kind"], "cc": r["cc"], "reg": r["reg"], "detail": r["detail"],
              "checked": r["checked"], "monitored": False} for r in rows]
    grades = V.source_grades([i["sid"] for i in items], voter)
    for i in items: i["grade"] = grades.get(i["sid"])
    return 200, {"total": total, "page": page, "per": per, "pages": max(1, -(-total // per)), "items": items}

def summary():
    m = meta()
    if not m: return {"ready": False, "building": STATE["building"]}
    return {"ready": True, "total": m["total"], "by_category": m["facets"].get("cat", []), "by_registry": m["facets"].get("reg", []),
            "countries": m["facets"].get("cc", []), "built": m["built"], "registries": m["source_meta"].get("registries", {}),
            "checked": m["source_meta"].get("liveness", {})}

if __name__ == "__main__":
    if "--build" in sys.argv: build()
    else: print(json.dumps(summary(), indent=1)[:3000])
