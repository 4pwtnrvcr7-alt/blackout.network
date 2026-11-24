import json, re, sys, shapely.wkb as W
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); import build_infra as B
seen = set(); nl = ns = 0; ncab = 0
o = open("grid.geojsonseq", "w")
for l in open("raw.jsonl"):
    c, t, g = json.loads(l)
    if c not in ("power_line", "cable", "substation"): continue
    v = B.kv(t)
    if v < 220 or v > 1200: continue
    nm = (t.get("name:en") or t.get("name") or t.get("ref") or "").replace(";", " · ")[:80]; op = (t.get("operator") or "").replace(";", " · ")[:60]
    geo = W.loads(bytes.fromhex(g)).__geo_interface__
    if c == "substation":
        cc = B.r3(B.center(geo)) if geo["type"] != "Point" else B.r3(geo["coordinates"])
        if ("s", tuple(cc)) in seen: continue
        seen.add(("s", tuple(cc))); ns += 1
        o.write(json.dumps({"type": "Feature", "tippecanoe": {"minzoom": 5}, "geometry": {"type": "Point", "coordinates": cc}, "properties": {"v": v, "vt": B.kvs(t), "n": nm, "op": op}}, separators=(",", ":")) + "\n")
    else:
        for ln in B.lines({"type": geo["type"], "coordinates": geo["coordinates"]}):
            ln = [B.r3(p) for p in B.rdp([list(p) for p in ln], 0.007)]
            k = tuple(map(tuple, ln))
            if len(ln) < 2 or k in seen: continue
            seen.add(k); nl += 1; ncab += c == "cable"
            mz = 0 if v >= 450 else 2 if v >= 300 else 4
            p = {"v": v, "n": nm, "op": op}
            if c == "cable": p["u"] = 1
            o.write(json.dumps({"type": "Feature", "tippecanoe": {"minzoom": mz}, "geometry": {"type": "LineString", "coordinates": ln}, "properties": p}, separators=(",", ":")) + "\n")
print("lines", nl, "cables", ncab, "subs", ns)
