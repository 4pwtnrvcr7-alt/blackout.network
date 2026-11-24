"""Build app/netmap_static/syncareas.json (pt1815u): one outline per synchronous grid area with a keyless live frequency feed.
Countries from app/netmap_static/inet.json (Natural Earth), unioned (no internal borders, so cross-border lines keep the colour),
buffered 0.1 deg so lines that touch the simplified coastline still count as inside, then simplified. Needs shapely (build step only).
Usage: python3 tools/build_syncareas.py > app/netmap_static/syncareas.json"""
import json, os, sys
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "app"))
import gridfreq
d = json.load(open(os.path.join(HERE, "..", "app", "netmap_static", "inet.json")))
by = {f["properties"]["k"][2:]: f["geometry"] for f in d["features"] if f["properties"]["k"].startswith("C:")}
out = {}
for a in gridfreq.AREAS:
    gs = []
    for cc in a["cc"]:
        if cc not in by: continue
        g = shape(by[cc])
        if cc == "GB":   # Northern Ireland is on the all-island Irish grid, not GB's
            g = unary_union([p for p in getattr(g, "geoms", [g]) if not (-8.3 < p.centroid.x < -5.3 and 54 < p.centroid.y < 55.4)])
        gs.append(g.buffer(0))
    u = unary_union(gs).buffer(0.1, 4).simplify(0.03)
    m = mapping(u); m = {"type": "MultiPolygon", "coordinates": [m["coordinates"]] if m["type"] == "Polygon" else m["coordinates"]}
    m["coordinates"] = [[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in poly] for poly in m["coordinates"]]
    out[a["id"]] = m
json.dump(out, sys.stdout, separators=(",", ":"))
