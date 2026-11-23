"""Build app/netmap_static/cables.json for the Network map's undersea cable layer (pt1785u, Stage 2).

Sources (both allow commercial use; TeleGeography's free map data is CC BY-NC-SA, so it is NOT used):
  - OpenStreetMap contributors, ODbL 1.0: ways tagged communication=line or telecom=line with submarine=yes
    (power cables excluded), and telecom=cable_landing_station. Attribution: "(c) OpenStreetMap contributors".
  - NOAA Office for Coastal Management, Submarine Cables (U.S. waters, general location; U.S. government work,
    public domain): https://coast.noaa.gov/arcgis/rest/services/Hosted/SubmarineCables/FeatureServer/0
Usage: python3 tools/build_cables.py OSM_CABLES.json OSM_LANDING.json NOAA.geojson > app/netmap_static/cables.json
The OSM inputs are Overpass "out tags geom" / "out tags center" JSON; NOAA is the FeatureServer query as GeoJSON.
"""
import json, re, sys

RETIRED = re.compile(r"^(TAT|PTAT|CANTAT)[\s-]?\d|\bTAT\s?\d|\bPTAT\b|CANTAT", re.I)   # first-generation Atlantic systems, retired years ago but still drawn in OSM
POWER = re.compile(r"wind|energy|hvdc|power|electric|interconnector|neptune regional|transmission", re.I)

def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; dx, dy = b[0] - a[0], b[1] - a[1]; L = (dx * dx + dy * dy) or 1e-12
    i, dm = 0, -1
    for k in range(1, len(pts) - 1):
        p = pts[k]; t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)); qx, qy = a[0] + t * dx - p[0], a[1] + t * dy - p[1]
        d = qx * qx + qy * qy
        if d > dm: i, dm = k, d
    if dm ** 0.5 <= eps: return [a, b]
    return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)

def r4(p): return [round(p[0], 3), round(p[1], 3)]

def main(osm_c, osm_l, noaa):
    out = []
    for e in json.load(open(osm_c))["elements"]:
        t = e.get("tags", {}); nm = (t.get("name") or t.get("seamark:name") or "").strip()
        if t.get("seamark:cable_submarine:category") == "power" or t.get("power") or "voltage" in t: continue
        if t.get("disused") == "yes" or t.get("abandoned") == "yes" or (nm and RETIRED.search(nm)): continue
        g = [[p["lon"], p["lat"]] for p in e.get("geometry") or [] if p]
        g = [r4(p) for p in rdp(g, 0.02)]
        if len(g) < 2: continue
        out.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": g},
                    "properties": {"n": nm[:80], "op": (t.get("operator") or "")[:80], "s": "osm", "id": f"w{e['id']}"}})
    for f in json.load(open(noaa))["features"]:
        p = f.get("properties") or {}; nm = (p.get("cablesystem") or "").strip()
        if not nm or nm == "<Null>" or POWER.search(nm) or (p.get("status") or "") in ("Abandoned", "Out of Service"): continue
        geo = f.get("geometry") or {}; polys = geo.get("coordinates") or []
        if geo.get("type") == "Polygon": polys = [polys]
        for poly in polys:
            ring = [r4(q) for q in rdp([list(q[:2]) for q in poly[0]], 0.01)]
            if len(ring) < 3: continue
            out.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": ring},
                        "properties": {"n": nm[:80], "op": (p.get("owner") or "")[:80], "s": "noaa", "st": p.get("status") or ""}})
    ls = []
    for e in json.load(open(osm_l))["elements"]:
        t = e.get("tags", {})
        if t.get("telecom") != "cable_landing_station": continue
        c = e.get("center") or ({"lat": e.get("lat"), "lon": e.get("lon")} if "lat" in e else None)
        if not c: continue
        ls.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": r4([c["lon"], c["lat"]])},
                   "properties": {"n": (t.get("name") or "Cable landing station")[:80], "op": (t.get("operator") or "")[:60], "s": "osm"}})
    json.dump({"type": "FeatureCollection", "features": out + ls,
               "credit": "Routes and landing stations (c) OpenStreetMap contributors (ODbL); U.S. cable areas: NOAA Office for Coastal Management"},
              sys.stdout, separators=(",", ":"))

if __name__ == "__main__": main(*sys.argv[1:4])
