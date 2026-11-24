"""Builds app/netmap_static/gridops.json: simplified U.S. operator/BA outlines (from gridstatus_static/sections.geojson) used to colour
the OSM 230 kV+ lines by the live status of the operator region each line sits in (Nov 24 2026, Matt). Douglas-Peucker, 0.06 deg, islands under 0.05 sq deg dropped."""
import json, os
B = os.path.join(os.path.dirname(__file__), "..", "..", "app")
def dp(pts, tol):
    if len(pts) < 3: return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]; dx, dy = x2 - x1, y2 - y1; L = (dx * dx + dy * dy) ** .5 or 1e-12
    i, dm = 0, -1
    for k in range(1, len(pts) - 1):
        d = abs(dy * pts[k][0] - dx * pts[k][1] + x2 * y1 - y2 * x1) / L if (dx or dy) else ((pts[k][0] - x1) ** 2 + (pts[k][1] - y1) ** 2) ** .5
        if d > dm: i, dm = k, d
    if dm <= tol: return [pts[0], pts[-1]]
    return dp(pts[:i + 1], tol)[:-1] + dp(pts[i:], tol)
g = json.load(open(os.path.join(B, "gridstatus_static", "sections.geojson")))
out = []
for f in g["features"]:
    if f["properties"]["id"] in ("AK", "HI"): continue
    geo = f["geometry"]; polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    mp = []
    for p in polys:
        rings = [[[round(x, 3), round(y, 3)] for x, y in dp(r, 0.06)] for r in p]
        rings = [r for r in rings if len(r) >= 4]
        a = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(rings[0], rings[0][1:]))) / 2 if rings else 0
        if rings and a >= 0.05: mp.append(rings)
    out.append({"id": f["properties"]["id"], "name": f["properties"]["name"], "g": {"type": "MultiPolygon", "coordinates": mp}})
s = json.dumps({"src": "EIA balancing-authority outlines (sections.geojson), simplified", "ops": out}, separators=(",", ":"))
open(os.path.join(B, "netmap_static", "gridops.json"), "w").write(s); print(len(s), [(o["id"], sum(len(r) for p in o["g"]["coordinates"] for r in p)) for o in out])
