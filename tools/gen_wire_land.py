"""Builds the 1-degree land grid embedded in app/wire_timeline_static/loader.js (the /wire loading screen globe).
Source: app/signal_map_static/world.geojson (Natural Earth 110m countries, public domain). Antarctica is left out.
Run: python3 tools/gen_wire_land.py  -> prints the compact JSON to paste between the LAND markers in loader.js."""
import json, os, sys
import numpy as np
from matplotlib.path import Path
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
d = json.load(open(os.path.join(ROOT, "signal_map_static", "world.geojson")))
STEP = 1.0
lons = np.arange(-179.5, 180, STEP); lats = np.arange(-84.5, 84.6, STEP)
LL = np.array([(x, y) for y in lats for x in lons]); inside = np.zeros(len(LL), bool)
for f in d["features"]:
    if f["properties"].get("name") == "Antarctica": continue
    g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        m = Path(np.array(poly[0])).contains_points(LL)
        for hole in poly[1:]: m &= ~Path(np.array(hole)).contains_points(LL)
        inside |= m
rows = {}
for (x, y), i in zip(LL, inside):
    if i: rows.setdefault(round(float(y), 1), []).append(round(float(x), 1))
out = []
for y in sorted(rows):
    xs = rows[y]; runs = []; s = xs[0]; c = 1
    for a, b in zip(xs, xs[1:]):
        if abs(b - a - STEP) < 1e-6: c += 1
        else: runs.append([s, c]); s = b; c = 1
    runs.append([s, c]); out.append([y, runs])
sys.stdout.write(json.dumps({"step": STEP, "rows": out}, separators=(",", ":")))
