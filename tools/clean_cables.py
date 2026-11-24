"""pt1787u: keep only undersea cable routes that run landing-to-landing; join split pieces; drop dead ends at sea.

Usage: python3 tools/clean_cables.py IN_cables.json ne_10m_coastline.geojson > app/netmap_static/cables.json
Natural Earth 10m coastline (public domain) is a build-time input only; it is not shipped.
Rules: a route end must be within ANCHOR_KM of a cable landing station or the coastline, or meet another kept
piece. Pieces are snapped at SNAP_KM and pruned until no piece has a free end at sea; chains of pieces that
meet end to end with the same name and source are joined into one line.
"""
import json, math, sys
import numpy as np
from scipy.spatial import cKDTree

R = 6371.0; ANCHOR_KM = 25.0; SNAP_KM = 2.0

def xyz(pts):
    a = np.radians(np.asarray(pts, float)); lo, la = a[:, 0], a[:, 1]
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]

def densify(line, step_km=2.0):
    out = []
    for (x0, y0), (x1, y1) in zip(line, line[1:]):
        d = math.hypot((x1 - x0) * math.cos(math.radians((y0 + y1) / 2)), y1 - y0) * 111.2
        n = max(1, int(d / step_km))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    out.append(tuple(line[-1])); return out

def main(src, coast):
    d = json.load(open(src)); feats = d["features"]
    pts = [f for f in feats if f["geometry"]["type"] == "Point"]
    lines = [f for f in feats if f["geometry"]["type"] == "LineString" and len(f["geometry"]["coordinates"]) >= 2]
    cp = []
    for f in json.load(open(coast))["features"]:
        g = f["geometry"]; parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        for p in parts: cp += densify(p)
    cp += [tuple(f["geometry"]["coordinates"]) for f in pts]
    anchor = cKDTree(xyz(cp)); lim = ANCHOR_KM / R
    # Closed outlines (NOAA cable areas are polygons; a few OSM ways loop) have no ends: keep one only if every
    # vertex is within ANCHOR_KM of the coast or a landing station, i.e. it never reaches open ocean.
    rings = [f for f in lines if f["geometry"]["coordinates"][0] == f["geometry"]["coordinates"][-1]]
    ring_keep = [f for f in rings if anchor.query(xyz(f["geometry"]["coordinates"]))[0].max() <= lim]
    lines = [f for f in lines if f["geometry"]["coordinates"][0] != f["geometry"]["coordinates"][-1]]
    # snap end nodes
    ends = [c for f in lines for c in (f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][-1])]
    E = xyz(ends); tr = cKDTree(E); node = list(range(len(ends)))
    def find(i):
        while node[i] != i: node[i] = node[node[i]]; i = node[i]
        return i
    for i, j in tr.query_pairs(SNAP_KM / R): node[find(i)] = find(j)
    nid = [find(i) for i in range(len(ends))]
    anch = {n: False for n in nid}
    dist, _ = anchor.query(E)
    for i, n in enumerate(nid):
        if dist[i] <= lim: anch[n] = True
    seg = {k: (nid[2 * k], nid[2 * k + 1]) for k in range(len(lines))}
    alive = set(seg)
    while True:
        deg = {}
        for k in alive:
            for n in seg[k]: deg[n] = deg.get(n, 0) + 1
        bad = {k for k in alive if any(deg[n] == 1 and not anch[n] for n in seg[k]) or (seg[k][0] == seg[k][1] and not anch[seg[k][0]])}
        if not bad: break
        alive -= bad
    # drop components with no anchored node (loops at sea)
    adj = {}
    for k in alive:
        for n in seg[k]: adj.setdefault(n, set()).add(k)
    seen, keep = set(), set()
    for k0 in alive:
        if k0 in seen: continue
        comp, st = set(), [k0]
        while st:
            k = st.pop()
            if k in comp: continue
            comp.add(k); st += [j for n in seg[k] for j in adj[n]]
        seen |= comp
        if any(anch[n] for k in comp for n in seg[k]): keep |= comp
    # join end-to-end chains of the same cable
    def key(k): p = lines[k]["properties"]; return (p.get("n") or "", p.get("s"))
    deg = {}
    for k in keep:
        for n in seg[k]: deg[n] = deg.get(n, 0) + 1
    used, out_lines, joins = set(), [], 0
    def other(k, n): a, b = seg[k]; return b if a == n else a
    for k0 in sorted(keep):
        if k0 in used: continue
        used.add(k0); co = list(lines[k0]["geometry"]["coordinates"]); a, b = seg[k0]
        for side in (1, 0):
            n = b if side else a
            while deg.get(n) == 2:
                nxt = [j for j in adj[n] if j in keep and j not in used and key(j) == key(k0)]
                if not nxt: break
                j = nxt[0]; used.add(j); joins += 1
                c2 = list(lines[j]["geometry"]["coordinates"])
                if seg[j][0] != n: c2 = c2[::-1]          # c2 now starts at node n
                co = co + c2[1:] if side else c2[::-1] + co[1:]
                n = other(j, n)
        out_lines.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": co}, "properties": dict(lines[k0]["properties"])})
    names_all = sorted({f["properties"]["n"] for f in lines + rings if f["properties"].get("n")})
    allin = [lines[k] for k in seg] + rings; allout = [lines[k] for k in keep] + ring_keep
    nk = lambda f: (f["properties"].get("n") or "", f["properties"].get("s"))
    stats = dict(pieces_in=len(allin), open_pieces_in=len(lines), open_pieces_kept=len(keep), joins=joins, open_lines_out=len(out_lines),
                 closed_outlines_in=len(rings), closed_outlines_kept=len(ring_keep), pieces_dropped=len(allin) - len(allout),
                 named_cables_in=len({f["properties"]["n"] for f in allin if f["properties"].get("n")}), named_cables_kept=len({f["properties"]["n"] for f in allout if f["properties"].get("n")}),
                 by_src={s: [sum(1 for f in allin if nk(f)[1] == s), sum(1 for f in allout if nk(f)[1] == s)] for s in ("osm", "noaa")})
    out_lines += ring_keep
    print(json.dumps(stats), file=sys.stderr)
    d2 = {"type": "FeatureCollection", "credit": d.get("credit"), "names": names_all,
          "note": "Only routes that run from landing point to landing point (ends within 25 km of a landing station or the coast); pieces ending at sea are not drawn.",
          "features": out_lines + pts}
    json.dump(d2, sys.stdout, separators=(",", ":"), ensure_ascii=False)

if __name__ == "__main__": main(*sys.argv[1:3])
