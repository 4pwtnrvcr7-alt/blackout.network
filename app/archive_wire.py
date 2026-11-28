"""Wire archive (Nov 27 2026, Matt pt1974u: history back to January 1, 2000).

Real records from free authoritative datasets, one Wire row each, dated 2000-01-01 .. 2024-10-28 (the day before trends_history.db,
the earlier archive backfill, starts). They have NO write-up page: each row links straight to its own record (USGS event page, NHC
report, FEMA declaration page, WHO Disease Outbreak News item) and carries the archive label.

Storage design (Render has 512 MB of RAM and the deploy handoff copies the Render-owned databases to the new node):
  * The data is committed as gzipped NDJSON shards (archive_wire_data/<year>.ndjson.gz.b64, ~3.5 MB in total, built by tools/build_wire_archive.py).
  * `python3 archive_wire.py --build` loads them into a READ-ONLY SQLite file, archive_wire/wire_archive.db, at Docker build time
    (same pattern as sources_dir/directory.db). The file lives in the image, in a subdirectory: it is not a top-level *.db, it is not in
    RENDER_OWNED, and nothing copies it during the handoff. If it is missing (box, Mac), a background thread builds it from the shards.
  * wire_timeline.py reads it with mode=ro as a third source next to blackout.db and trends_history.db. Paging, date filter, search,
    category / region / rank filters are SQL on indexed columns, so a request touches one page of rows, never the whole archive.
Never writes any other database, never fetches anything at runtime, never touches scanner.py, scoring, push.py or config.json."""
import os, sys, json, glob, gzip, base64, sqlite3, threading, time, hashlib
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "archive_wire_data")
DBDIR = os.path.join(BASE, "archive_wire")
DBF = os.path.join(DBDIR, "wire_archive.db")
_lock = getattr(sys, "_bn_archwire_lock", None)
if _lock is None: _lock = sys._bn_archwire_lock = threading.Lock()
STATE = getattr(sys, "_bn_archwire_state", None)
if STATE is None: STATE = sys._bn_archwire_state = {"building": False, "error": None}

def data_id():
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(DATA, "*.ndjson.gz.b64"))): h.update(os.path.basename(f).encode()); h.update(str(os.path.getsize(f)).encode())
    return h.hexdigest()[:16]

def build(quiet=False):
    """shard rows: [id, t, title, category, location, lat, lon, score, rank, confidence, tags, source, url, kind]"""
    import wire_timeline as W
    os.makedirs(DBDIR, exist_ok=True)
    tmp = DBF + ".building"
    for f in (tmp, tmp + "-journal"):
        if os.path.exists(f): os.unlink(f)
    c = sqlite3.connect(tmp)
    c.executescript("""PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE stories(id TEXT PRIMARY KEY, t TEXT NOT NULL, title TEXT, category TEXT, location TEXT, lat REAL, lon REAL, score INTEGER, rank INTEGER,
        confidence TEXT, watchlist INTEGER, n_items INTEGER, families TEXT, links TEXT, sources TEXT, tags TEXT, kind TEXT, k TEXT, g TEXT);
      CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);""")
    n = 0
    for fn in sorted(glob.glob(os.path.join(DATA, "*.ndjson.gz.b64"))):
        rows = []
        if True:
            for line in gzip.decompress(base64.b64decode(open(fn, "rb").read())).decode("utf-8").splitlines():
                r = json.loads(line)
                if not str(r[12]).startswith(("http://", "https://")): continue      # no working source link, no row
                fam = {"USGS ComCat": "USGS", "NOAA NHC HURDAT2": "NOAA", "OpenFEMA": "FEMA", "WHO Disease Outbreak News": "WHO"}.get(r[11], r[11])
                k = W.cat_key(r[3], r[2], True); g = W.region_key(r[4], r[2], r[5], r[6])
                rows.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], 0, 1, json.dumps([fam]),
                             json.dumps([{"source": r[11], "url": r[12]}]), json.dumps([r[11]]), json.dumps(r[10]), r[13], k, g))
        c.executemany("INSERT OR REPLACE INTO stories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows); n += len(rows)
    c.executescript("CREATE INDEX ix_a_t ON stories(t, id); CREATE INDEX ix_a_k ON stories(k, t); CREATE INDEX ix_a_g ON stories(g, t); CREATE INDEX ix_a_r ON stories(rank, t);")
    c.execute("INSERT INTO meta VALUES('data_id',?)", (data_id(),)); c.execute("INSERT INTO meta VALUES('rows',?)", (str(n),))
    c.commit(); c.execute("VACUUM"); c.close()
    os.replace(tmp, DBF)
    if not quiet: print("archive_wire: built", n, "rows,", os.path.getsize(DBF), "bytes ->", DBF)
    return n

def path():
    """Path of the read-only archive DB, or None (a missing file starts one background build from the shards)."""
    if os.path.exists(DBF): return DBF
    if os.path.isdir(DATA) and glob.glob(os.path.join(DATA, "*.ndjson.gz.b64")): _kick()
    return None

def _kick():
    with _lock:
        if STATE["building"]: return
        STATE["building"] = True
    def run():
        try: build(quiet=True)
        except Exception as ex: STATE["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
        finally: STATE["building"] = False
    threading.Thread(target=run, name="bn-archwire-build", daemon=True).start()

if __name__ == "__main__":
    if "--build" in sys.argv: build()
    else: print(json.dumps({"db": DBF, "exists": os.path.exists(DBF), "data_id": data_id()}))
