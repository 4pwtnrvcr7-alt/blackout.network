"""Build app/netmap_static/gwm_match.json (pt1815u, Nov 24 2026): match NASA GSFC Global Water Monitor (G-REALM) hydropower reservoirs to
WRI Global Power Plant Database hydro plants in hydro.json. Only NAME matches are kept (a GWM name token of 4+ letters appears in the
plant name, plant within 200 km of the lake mid-point); nearest-plant guesses are dropped so no dam gets another lake's level.
Also stores a snapshot of the ratings so the map has satellite levels before the server's first live fetch.
Usage: python3 tools/build_gwm_match.py /path/to/GWM_HEP_reservoirs.tgz"""
import io, json, math, os, re, sys, tarfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import gwmlevels
ST = os.path.join(os.path.dirname(__file__), "..", "app", "netmap_static")
STOP = {"lake", "dam", "reservoir", "hydro", "power", "station", "plant", "river", "parte", "brasileira", "part", "project", "hydroelectric",
        "antiga", "binacional", "paraguay", "brazil", "upper", "lower", "north", "south", "east", "west", "nueva", "grande", "small"}
def toks(s): return {t for t in re.findall(r"[a-z]{4,}", s.lower()) if t not in STOP}
NUM = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "1": "1", "2": "2", "3": "3", "4": "4", "3a": "3"}
def nums(s): return {NUM[t] for t in re.findall(r"\b(iv|iii|ii|i|[1-4]a?)\b", s.lower()) if t in NUM}
def same_dam(lake, plant):
    """Reject Gilgel Gibe III -> Gibe II, Nam Ngum 1 -> Nam Ngum 2, Upper Paunglaung -> Paunglaung style mismatches."""
    a, b = nums(lake), nums(plant)
    if a and b and not a & b: return False
    if a - {"1"} and not b: return False
    if b - {"1"} and not a: return False
    if "upper" in lake.lower() and "upper" not in plant.lower(): return False
    return True
SKIP = {"004107"}   # Kinda: lake mid-point 107 km from the plant, checked by hand and not the same reservoir with confidence
def km(a, b, c, e): return math.hypot((e - c) * math.cos(math.radians((a + b) / 2)), b - a) * 111.2
hyd = json.load(open(os.path.join(ST, "hydro.json")))["p"]
tf = tarfile.open(sys.argv[1], "r:gz"); lakes = {}; snap = {}; rows = []
for m in tf.getmembers():
    if not m.isfile(): continue
    txt = tf.extractfile(m).read().decode("latin-1"); ln = txt.splitlines()
    lid = m.name.split("/")[-1][4:10]; nm = ln[1].split(":")[0].split(None, 1)[1].strip().replace("_", " ")
    la, lo = map(float, ln[2].split(":")[0].split()[:2]); lo = lo - 360 if lo > 180 else lo
    if lid in SKIP: continue
    nt = toks(nm); best = None
    for r in hyd:
        k = km(la, r[1], lo, r[0])
        if k < 200 and nt & toks(r[2]) and same_dam(nm, r[2]) and (best is None or k < best[0]): best = (k, r)
    if not best: continue
    pid = best[1][7]
    if pid in snap: continue   # one lake per plant
    lakes[lid] = pid
    _, pts = gwmlevels.parse(txt); r = gwmlevels.rate(pts)
    r.update({"lake": nm, "lake_id": lid, "url": gwmlevels.PAGE, "src": "NASA GSFC Global Water Monitor (G-REALM), satellite radar altimetry", "method": "satellite, relative to usual level"})
    snap[pid] = r; rows.append((lid, nm, pid, best[1][2], best[1][6], round(best[0]), r["status"]))
json.dump({"credit": "NASA GSFC Global Water Monitor / G-REALM (U.S. Government work), matched to WRI GPPD hydro plants by name",
           "built": "2026-11-24", "lakes": lakes, "snap": snap}, open(os.path.join(ST, "gwm_match.json"), "w"), separators=(",", ":"))
for x in sorted(rows, key=lambda x: x[4]): print(*x, sep=" | ")
from collections import Counter; print(len(lakes), Counter(v["status"] for v in snap.values()))
