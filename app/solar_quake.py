"""Solar–Earthquake Correlation Lab (blackout.network, Solar & Seismic tab).

EXPLORATORY ANALYSIS, NOT ESTABLISHED SCIENCE. Serves the precomputed results written by tools/solar_quake_build.py
(GFZ Kp, NOAA NCEI/SWPC GOES flare lists, USGS ComCat M4.5+). No upstream fetches at request time, no background jobs.
Never touches scanner.py, scoring, push.py, jets.py or config.json."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "solar_quake_data")
STATIC = os.path.join(BASE, "solar_quake_static")
FILES = {"/api/solar_quake": (DATA, "solar_quake.json", "application/json"),
         "/api/solar_quake/map": (DATA, "solar_quake_map.json", "application/json"),
         "/api/solar_quake/app.js": (STATIC, "app.js", "application/javascript"),
         "/api/solar_quake/app.css": (STATIC, "app.css", "text/css")}
_cache = {}

def _read(d, f):
    p = os.path.join(d, f)
    mt = os.path.getmtime(p)
    c = _cache.get(p)
    if not c or c[0] != mt:
        with open(p, "rb") as fh: c = _cache[p] = (mt, fh.read())
    return c[1]

def handle_get(path, qs):
    hit = FILES.get(path.rstrip("/") or path)
    if not hit: return 404, {"error": "not found"}
    try: return 200, _read(hit[0], hit[1]), hit[2]
    except FileNotFoundError: return 503, {"error": "analysis not built yet"}
