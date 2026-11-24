"""Build the Network map's U.S. infrastructure layers (pt1785u, Stage 3): towers.json, grid.json, fiber.json in app/netmap_static/.

Sources (all allow commercial use with credit; nothing here needs an account or API key):
  - Cell towers: FCC Antenna Structure Registration (ASR) complete file, https://data.fcc.gov/download/pub/uls/complete/r_tower.zip
    (U.S. government data, no copyright). Constructed, not dismantled, tower-type structures only. OpenCelliD is NOT used:
    it needs an API key and its data is CC BY-SA.
  - Power grid: OpenStreetMap contributors, ODbL 1.0. power=line ways and power=substation features of 230 kV and up.
  - Long-haul fiber: OpenStreetMap contributors, ODbL 1.0. telecom=line / communication=line ways on land (submarine excluded),
    joined per operator/name, kept only when the joined route is at least MIN_FIBER_KM long. Street-level fiber is not public.
    NOT shipped (Nov 23 2026): OSM has almost no U.S. land long-haul fiber, so the map has no fiber layer.
Usage:
  python3 tools/build_infra.py towers ASR_DIR > app/netmap_static/towers.json
  python3 tools/build_infra.py grid REGION1.geojsonseq [REGION2 ...] > app/netmap_static/grid.json
  python3 tools/build_infra.py fiber TELECOM.geojsonseq > app/netmap_static/fiber.json
The .geojsonseq inputs come from Geofabrik U.S. extracts filtered with osmium (see the PR notes); geometry is simplified with RDP.
"""
import collections, json, math, os, re, sys

def rdp(pts, eps):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]
    while st:
        i0, i1 = st.pop(); a, b = pts[i0], pts[i1]; dx, dy = b[0] - a[0], b[1] - a[1]; L = (dx * dx + dy * dy) or 1e-12; im, dm = -1, -1
        for k in range(i0 + 1, i1):
            p = pts[k]; t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)); qx, qy = a[0] + t * dx - p[0], a[1] + t * dy - p[1]; d = qx * qx + qy * qy
            if d > dm: im, dm = k, d
        if im > 0 and dm ** 0.5 > eps: keep[im] = True; st += [(i0, im), (im, i1)]
    return [p for p, k in zip(pts, keep) if k]

def km(g):
    s = 0
    for (x1, y1), (x2, y2) in zip(g, g[1:]):
        s += math.hypot((x2 - x1) * math.cos(math.radians((y1 + y2) / 2)), y2 - y1) * 111.2
    return s

def r3(p): return [round(p[0], 3), round(p[1], 3)]

# ---------- towers (FCC ASR) ----------
KEEP = {"TOWER": "Tower", "LTOWER": "Lattice tower", "MTOWER": "Monopole", "GTOWER": "Guyed tower", "POLE": "Pole", "MAST": "Mast", "2TOWER": "Two towers", "UPOLE": "Utility pole"}
OWN = [("AMERICAN TOWER", "American Tower"), ("CROWN CASTLE", "Crown Castle"), ("CCATT", "Crown Castle"), ("CROWN COMMUNICATION", "Crown Castle"), ("PINNACLE TOWERS", "Crown Castle"),
       ("GLOBAL SIGNAL", "Crown Castle"), ("SBA ", "SBA Communications"), ("VERTICAL BRIDGE", "Vertical Bridge"), ("VB-S1", "Vertical Bridge"), ("T-MOBILE", "T-Mobile"),
       ("CELLCO", "Verizon"), ("VERIZON", "Verizon"), ("NEW CINGULAR", "AT&T"), ("AT&T", "AT&T"), ("UNITED STATES CELLULAR", "UScellular"), ("ARRAY DIGITAL", "Array Digital Infrastructure"),
       ("TILLMAN", "Tillman Infrastructure"), ("PHOENIX TOWER", "Phoenix Tower International"), ("DIAMOND COMMUNICATIONS", "Diamond Communications"), ("INSITE", "InSite Wireless")]

def owner(n):
    u = n.upper()
    for k, v in OWN:
        if k in u: return v
    t = re.sub(r"\b(Llc|Inc|Lp|Llp|Ltd|Co|Corp)\b\.?", lambda m: {"Llc": "LLC", "Lp": "LP", "Llp": "LLP"}.get(m.group(1), m.group(1) + "."), n.title())
    t = re.sub(r"\b([B-DF-HJ-NP-TV-Z]{2,4})\b", lambda m: m.group(1).upper(), re.sub(r"\b(\w)(\w*)\b", lambda m: m.group(0) if len(m.group(0)) > 3 or m.group(0).lower() in ("of", "and", "the") else m.group(0).upper() if not re.search("[aeiouy]", m.group(0).lower()) else m.group(0), t))
    t = re.sub(r"\b(Ii|Iii|Iv|Vi|Vii|Bnsf|Smsa|Cti|Eip|Us|Usa|Tv|Fm|Am|Pcs|Rsa|Msa)\b", lambda m: m.group(1).upper(), t)
    return t.replace("'S ", "'s ")[:40] or "Unknown"

def towers(d):
    ra = {}
    for l in open(os.path.join(d, "RA.dat"), encoding="latin-1"):
        f = l.rstrip("\n").split("|")
        if len(f) > 32 and f[8] == "C" and not f[13] and f[32] in KEEP: ra[f[4]] = f   # constructed, no dismantle date
    co = {}
    for l in open(os.path.join(d, "CO.dat"), encoding="latin-1"):
        f = l.rstrip("\n").split("|")
        if len(f) < 15 or f[5] != "T" or f[4] not in ra: continue
        try:
            la = float(f[6]) + float(f[7] or 0) / 60 + float(f[8] or 0) / 3600; lo = float(f[11]) + float(f[12] or 0) / 60 + float(f[13] or 0) / 3600
        except ValueError: continue
        co[f[4]] = (-lo if f[14] == "W" else lo, -la if f[9] == "S" else la)
    own = {}
    for l in open(os.path.join(d, "EN.dat"), encoding="latin-1"):
        f = l.rstrip("\n").split("|")
        if len(f) > 9 and f[5] == "O" and f[4] in ra: own[f[4]] = owner(f[9].strip())
    rows, cnt = [], collections.Counter()
    for k, f in ra.items():
        if k not in co: continue
        lo, la = co[k]
        if not (-180 < lo < -60 and 13 < la < 72): continue
        o = own.get(k, "Unknown"); cnt[o] += 1
        try: h = round(float(f[30] or f[28]))
        except ValueError: h = 0
        rows.append((lo, la, o, h, f[32], f[3], k))
    top = [o for o, n in cnt.most_common() if n >= 50]; oi = {o: i for i, o in enumerate(top)}; ty = sorted(KEEP); ti = {t: i for i, t in enumerate(ty)}
    asof = ""
    try:
        import datetime
        m = re.search(r"(\w{3}) (\w{3}) +(\d+) [\d:]+ \w+ (\d{4})", open(os.path.join(d, "counts")).read())
        if m: asof = datetime.datetime.strptime(" ".join(m.group(2, 3, 4)), "%b %d %Y").strftime("%b %-d, %Y")
    except OSError: pass
    return {"credit": "FCC Antenna Structure Registration (ASR); U.S. government data", "asof": asof, "owners": top + ["Other owner"], "types": ty, "tnames": KEEP,
            "p": [[round(lo, 4), round(la, 4), oi.get(o, len(top)), h, ti[t], int(u)] for lo, la, o, h, t, r, u in rows]}

# ---------- OSM helpers ----------
def feats(path):
    for l in open(path, encoding="utf-8"):
        l = l.strip().lstrip("\x1e")
        if l: yield json.loads(l)

def kv(t):
    vs = []
    for x in re.split(r"[;,]", t.get("voltage") or ""):
        try: vs.append(int(float(x.strip())) // 1000)
        except ValueError: pass
    return max(vs) if vs else 0

def kvs(t):
    vs = []
    for x in re.split(r"[;,]", t.get("voltage") or ""):
        try: k = int(float(x.strip())) // 1000
        except ValueError: continue
        if k and k not in vs: vs.append(k)
    return " / ".join(map(str, sorted(vs, reverse=True))) + " kV" if vs else ""

def lines(g):
    if g["type"] == "LineString": return [g["coordinates"]]
    if g["type"] == "MultiLineString": return g["coordinates"]
    return []

def center(g):
    c = g["coordinates"]
    if g["type"] == "Point": return c
    ring = c[0] if g["type"] == "Polygon" else c[0][0] if g["type"] == "MultiPolygon" else c
    return [sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)]

def grid(*paths):
    out, ss, seen = [], [], set()   # Geofabrik regions overlap at their edges: drop exact duplicates
    for f in (f for p in paths for f in feats(p)):
        t = f.get("properties") or {}; v = kv(t)
        if v < 230: continue
        nm = (t.get("name") or t.get("ref") or "").replace(";", " · ")[:80]; op = (t.get("operator") or "").replace(";", " · ")[:60]
        if t.get("power") == "substation":
            c = r3(center(f["geometry"]))
            if ("s", tuple(c)) in seen: continue
            seen.add(("s", tuple(c)))
            ss.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": c}, "properties": {"v": v, "vt": kvs(t), "n": nm, "op": op}})
        elif t.get("power") == "line":
            for g in lines(f["geometry"]):
                g = [r3(p) for p in rdp(g, 0.007)]
                k = tuple(map(tuple, g))
                if k in seen: continue
                seen.add(k)
                if len(g) >= 2 and g[0] != g[-1] or len(g) > 2:
                    out.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": g}, "properties": {"v": v, "n": nm, "op": op}})
    return {"type": "FeatureCollection", "features": out + ss, "credit": "Power lines and substations (c) OpenStreetMap contributors (ODbL), 230 kV and up"}

MIN_FIBER_KM = 15
BOX = ((-125.0, 24.3, -66.8, 49.5), (-170.0, 51.0, -129.0, 71.5))   # CONUS, Alaska

def onland(q): return any(b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3] for b in BOX)

def fiber(path):
    groups = collections.defaultdict(list)
    for f in feats(path):
        t = f.get("properties") or {}
        if t.get("location") in ("underwater", "submarine") or t.get("submarine") == "yes" or t.get("seamark:type") or t.get("power"): continue
        if (t.get("telecom") or t.get("communication")) != "line": continue
        key = ((t.get("operator") or "").strip(), (t.get("name") or "").strip())
        for g in lines(f["geometry"]):
            if all(onland(q) for q in g): groups[key].append(g)   # transoceanic cables often lack location tags; keep land routes only
    out, tot = [], 0
    for (op, nm), gs in groups.items():
        L = sum(km(g) for g in gs)
        if L < MIN_FIBER_KM: continue
        tot += L
        for g in gs:
            g = [r3(p) for p in rdp(g, 0.003)]
            if len(g) >= 2: out.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": g}, "properties": {"op": op[:60], "n": nm[:80], "km": round(L)}})
    return {"type": "FeatureCollection", "features": out, "km": round(tot), "credit": "Fiber routes (c) OpenStreetMap contributors (ODbL); publicly mapped long-haul routes only"}

if __name__ == "__main__":
    kind, src = sys.argv[1], sys.argv[2:]
    json.dump({"towers": towers, "grid": grid, "fiber": fiber}[kind](*src), sys.stdout, separators=(",", ":"))
