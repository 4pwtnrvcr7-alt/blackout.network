"""Read-only plant store for the Grid Water layer.

The plant inventory (EPA ECHO/FRS, EEA UWWTD, OpenStreetMap; every row cites a source) lives in one SQLite file that ships as
zipped base64 text parts (water.db.b64.N, like gridtiles.b64.N). It is decoded ONCE to a temp file on disk and opened read-only,
so the process never holds the dataset in RAM: each request reads only the pages for its viewport. Responses are small:
precomputed clusters when zoomed out, capped points when zoomed in, and a one-row detail lookup on tap.
"""
import base64
import io
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from collections import OrderedDict

TIERS = [8.0, 2.0, 0.5, 0.125]          # must match tools/build_water_db.py
POINT_Z = 9.0                           # below this zoom: clusters
POINT_CAP = 2500
CLUSTER_CAP = 3000
_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{3,40}")
_lock = threading.Lock()
_conn = None
_cache = OrderedDict()                  # LRU of encoded responses (bytes), keyed by quantized viewport
_CACHE_BYTES = 12 * 1024 * 1024         # byte-bounded: the LRU never holds more than ~12 MB
_cache_n = [0]


def _static_dir():
    return os.path.join(os.path.dirname(__file__), "netmap_static")


def _db_path():
    st = _static_dir()
    parts = sorted((int(m.group(1)), f) for f in os.listdir(st) for m in [re.fullmatch(r"water\.db\.b64\.(\d+)", f)] if m)
    if not parts:
        return None
    sig = "%d-%d" % (len(parts), sum(os.path.getsize(os.path.join(st, f)) for _, f in parts))
    dest = os.path.join(tempfile.gettempdir(), "bn_water_%s.sqlite" % sig)
    if os.path.isfile(dest) and os.path.getsize(dest) > 4096:
        return dest
    tmp = dest + ".%d.tmp" % os.getpid()
    zpath = tmp + ".zip"
    with open(zpath, "wb") as zf:             # decode part by part straight to disk: peak RSS stays a few MB
        for _, f in parts:
            with open(os.path.join(st, f), "rb") as fh:
                zf.write(base64.b64decode(fh.read()))
    with zipfile.ZipFile(zpath) as z, z.open("water.sqlite") as src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out, 1 << 20)
    os.remove(zpath)
    os.replace(tmp, dest)
    return dest


def conn():
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is None:
            p = _db_path()
            if not p:
                return None
            c = sqlite3.connect("file:%s?mode=ro&immutable=1" % p, uri=True, check_same_thread=False)
            c.execute("PRAGMA cache_size=-3000")
            c.execute("PRAGMA mmap_size=0")
            _conn = c
    return _conn


def _f(v, lo, hi, d):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return d
    return max(lo, min(hi, x))


def _q(qs, k):
    v = (qs or {}).get(k)
    if isinstance(v, list):
        v = v[0] if v else None
    return v


def _cached(key, build):
    with _lock:
        v = _cache.get(key)
        if v is not None:
            _cache.move_to_end(key)
            return v
    v = build()
    with _lock:
        if key not in _cache:
            _cache[key] = v
            _cache_n[0] += len(v)
        while _cache_n[0] > _CACHE_BYTES and len(_cache) > 1:
            _, old = _cache.popitem(last=False)
            _cache_n[0] -= len(old)
    return v


_TOT = []
def _total(c):
    if not _TOT:
        g = lambda k: int(c.execute("SELECT v FROM m WHERE k=?", (k,)).fetchone()[0])
        _TOT.append([g("rows"), g("countries")])
    return _TOT[0]


def tier_for(z):
    return 0 if z < 3 else 1 if z < 5 else 2 if z < 7 else 3


def view(qs):
    """GET /api/netmap/water?w=&s=&e=&n=&z=  ->  (200, bytes, ctype). Clusters below zoom 9, points at 9+."""
    c = conn()
    if c is None:
        return 503, {"error": "plant inventory unavailable"}
    z = _f(_q(qs, "z"), 0, 22, 2)
    w = _f(_q(qs, "w"), -180, 180, -180); e = _f(_q(qs, "e"), -180, 180, 180)
    s = _f(_q(qs, "s"), -90, 90, -90); n = _f(_q(qs, "n"), -90, 90, 90)
    if e < w:
        w, e = -180.0, 180.0
    ptmode = z >= POINT_Z
    t = tier_for(z)
    q = 0.125 if ptmode else TIERS[t]
    # snap the box outward to the grid so neighbouring pans hit the same cache entry
    w0 = int((w + 180) / q) * q - 180; e0 = (int((e + 180) / q) + 1) * q - 180
    s0 = int((s + 90) / q) * q - 90; n0 = (int((n + 90) / q) + 1) * q - 90
    key = ("p" if ptmode else "c%d" % t, round(w0, 3), round(e0, 3), round(s0, 3), round(n0, 3))

    def build():
        import json
        cur = c.cursor()
        if ptmode:
            rows = cur.execute(
                "SELECT lon,lat,k,uid,name FROM p WHERE cy BETWEEN ? AND ? AND cx BETWEEN ? AND ? LIMIT ?",
                (int((s0 + 90) * 8), int((n0 + 90) * 8), int((w0 + 180) * 8), int((e0 + 180) * 8), POINT_CAP + 1)).fetchall()
            more = len(rows) > POINT_CAP
            r = [[round(a, 5), round(b, 5), k, u, nm] for a, b, k, u, nm in rows[:POINT_CAP]]
            out = {"t": "p", "r": r, "more": more, "total": _total(c)}
        else:
            sz = TIERS[t]
            rows = cur.execute(
                "SELECT lon,lat,n,nw FROM cl WHERE t=? AND gy BETWEEN ? AND ? AND gx BETWEEN ? AND ? LIMIT ?",
                (t, int((s0 + 90) / sz), int((n0 + 90) / sz), int((w0 + 180) / sz), int((e0 + 180) / sz), CLUSTER_CAP)).fetchall()
            out = {"t": "c", "r": [[round(a, 3), round(b, 3), n_, nw_] for a, b, n_, nw_ in rows], "total": _total(c)}
        return json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode()

    return 200, _cached(key, build), "application/json", {"Cache-Control": "public, max-age=600"}


def detail(qs):
    """GET /api/netmap/water_plant?id=<uid>  ->  full row with a cited source."""
    c = conn()
    if c is None:
        return 503, {"error": "plant inventory unavailable"}
    uid = str(_q(qs, "id") or "")
    if not _ID_RE.fullmatch(uid):
        return 404, {"error": "not found"}
    r = c.execute("SELECT p.lon,p.lat,p.name,p.k,p.cc,p.st,s.label,s.tpl,p.ref,p.note FROM p JOIN s ON s.id=p.src WHERE p.uid=?", (uid,)).fetchone()
    if not r:
        return 404, {"error": "not found"}
    lon, lat, name, k, cc, st, label, tpl, ref, note = r
    return 200, {"id": uid, "lon": lon, "lat": lat, "name": name, "kind": "ww" if k else "dw", "cc": cc, "st": st,
                 "src": label, "url": tpl.replace("{ref}", ref) if tpl else "", "note": note}, "application/json", {"Cache-Control": "public, max-age=600"}


def stats():
    c = conn()
    if c is None:
        return None
    t = _total(c)
    return {"plants": t[0], "countries": t[1]}
