"""Reservoir water level vs. minimum power pool for hydro dams (pt1815u stage 2). Keyless, public-domain U.S. Bureau of Reclamation
HDB daily elevations. Only reservoirs with a published minimum power pool are rated; every other dam on the map stays grey
("no level data"), never green by default.
  Lake Mead / Hoover Dam: minimum power pool 950 ft (Reclamation). Amber at or below 1,050 ft (output already reduced; Tier 2 shortage
    line), red at or below 975 ft (within 25 ft of minimum power pool).
  Lake Powell / Glen Canyon Dam: minimum power pool 3,490 ft (Reclamation). Amber at or below 3,575 ft, red at or below 3,525 ft
    (Reclamation's 35 ft protection buffer above minimum power pool).
No satellite altimetry is used: DAHITI and Hydroweb need accounts/keys; G-REALM is keyless but gives relative heights with no power-pool
thresholds, so it cannot rate risk honestly.
"""
import time
from datetime import datetime, timedelta

RES = [
    {"id": "USA-HOOVER", "dam": "Hoover Dam", "lake": "Lake Mead", "svr": "lchdb", "sdi": 1930, "min_pool": 950, "amber": 1050, "red": 975,
     "url": "https://www.usbr.gov/lc/region/g4000/hourly/levels.html"},
    {"id": "USA0000153", "dam": "Glen Canyon Dam", "lake": "Lake Powell", "svr": "uchdb2", "sdi": 1928, "min_pool": 3490, "amber": 3575, "red": 3525,
     "url": "https://www.usbr.gov/uc/water/crsp/cs/gcd.html"},
]
SRC = "U.S. Bureau of Reclamation HDB (public domain)"

def rate(r, ft):
    if ft is None: return "na"
    return "out" if ft <= r["red"] else "low" if ft <= r["amber"] else "ok"

def one(jget, r, now):
    t1 = (now - timedelta(days=12)).strftime("%Y-%m-%dT00:00"); t2 = now.strftime("%Y-%m-%dT00:00")
    d = jget(f"https://www.usbr.gov/pn-bin/hdb/hdb.pl?svr={r['svr']}&sdi={r['sdi']}&tstp=DY&t1={t1}&t2={t2}&table=R&mrid=0&format=json", timeout=25)
    pts = []
    for x in (d.get("Series") or [{}])[0].get("Data") or []:
        try: pts.append((datetime.strptime(x["t"], "%m/%d/%Y %I:%M:%S %p"), float(x["v"])))
        except (ValueError, KeyError, TypeError): pass
    if not pts: return {"status": "na", "err": "no data"}
    pts.sort(); last_t, ft = pts[-1]
    if (now - last_t).days > 5: return {"status": "na", "err": "data is stale", "date": last_t.strftime("%Y-%m-%d")}
    wk = [v for t, v in pts if (last_t - t).days >= 7]
    return {"status": rate(r, ft), "ft": round(ft, 2), "date": last_t.strftime("%Y-%m-%d"), "chg7": round(ft - wk[-1], 2) if wk else None,
            "above_min": round(ft - r["min_pool"], 1)}

def build(jget):
    now = datetime.utcnow(); out = {}
    for r in RES:
        try: v = one(jget, r, now)
        except Exception as ex: v = {"status": "na", "err": type(ex).__name__}
        v.update({k: r[k] for k in ("dam", "lake", "min_pool", "amber", "red", "url")}); v["src"] = SRC
        out[r["id"]] = v
    return {"levels": out, "checked": int(time.time()),
            "method": "Lake elevation vs. the dam's published minimum power pool. Green normal, amber low (output reduced), red near or below minimum power pool, grey no level data."}
