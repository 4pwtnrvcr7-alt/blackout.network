"""Reservoir water level vs. minimum power pool for hydro dams (pt1815u stage 2). Keyless, public-domain U.S. Bureau of Reclamation
HDB daily elevations. Only reservoirs with a published minimum power pool are rated; every other dam on the map stays grey
("no level data"), never green by default.
  Lake Mead / Hoover Dam: minimum power pool 950 ft (Reclamation). Amber at or below 1,050 ft (output already reduced; Tier 2 shortage
    line), red at or below 975 ft (within 25 ft of minimum power pool).
  Lake Powell / Glen Canyon Dam: minimum power pool 3,490 ft (Reclamation). Amber at or below 3,575 ft, red at or below 3,525 ft
    (Reclamation's 35 ft protection buffer above minimum power pool).
Nov 24 2026 expansion (pt1815u): U.S. Army Corps of Engineers CWMS Data API (keyless, public domain) pool elevations vs. the project's
official minimum operating / power pool location level ("Bottom of Normal" NWDP, "Bottom of Power" LRN), with the conservation/power band
top from the same CWMS levels. Red when the pool is within 10% of the band above the minimum (or below it), amber within 25%.
Worldwide satellite levels (relative to each reservoir's usual level for the season) come from gwmlevels.py and are merged in netmap.py.
"""
import time
from datetime import datetime, timedelta, timezone

RES = [
    {"id": "USA-HOOVER", "dam": "Hoover Dam", "lake": "Lake Mead", "svr": "lchdb", "sdi": 1930, "min_pool": 950, "amber": 1050, "red": 975,
     "url": "https://www.usbr.gov/lc/region/g4000/hourly/levels.html"},
    {"id": "USA0000153", "dam": "Glen Canyon Dam", "lake": "Lake Powell", "svr": "uchdb2", "sdi": 1928, "min_pool": 3490, "amber": 3575, "red": 3525,
     "url": "https://www.usbr.gov/uc/water/crsp/cs/gcd.html"},
]
SRC = "U.S. Bureau of Reclamation HDB (public domain)"
CWMS = "https://cwms-data.usace.army.mil/cwms-data/timeseries"
CSRC = "U.S. Army Corps of Engineers CWMS Data API (public domain)"
# (gppd id, dam, lake, office, time series, minimum pool ft, top of band ft, min-pool level name, page)
CW = [
    ("USA0006163", "Grand Coulee Dam", "Lake Roosevelt", "NWDP", "GCL.Elev-Forebay.Inst.1Hour.0.CBT-REV", 1208, 1290, "Bottom of Normal", "https://www.nwd-wc.usace.army.mil/dd/common/projects/www/gcl.html"),
    ("USA0006172", "Libby Dam", "Lake Koocanusa", "NWDP", "LIB.Elev-Forebay.Ave.1Hour.1Hour.IRIDIUM-REV", 2287, 2459, "Bottom of Normal", "https://www.nwd-wc.usace.army.mil/dd/common/projects/www/lib.html"),
    ("USA0002203", "Hungry Horse Dam", "Hungry Horse Reservoir", "NWDP", "HGH.Elev-Forebay.Inst.1Hour.0.CBT-REV", 3336, 3560, "Bottom of Normal", "https://www.nwd-wc.usace.army.mil/dd/common/projects/www/hgh.html"),
    ("USA0000840", "Dworshak Dam", "Dworshak Reservoir", "NWDP", "DWR.Elev-Forebay.Inst.1Hour.0.Best", 1445, 1600, "Bottom of Normal", "https://www.nwd-wc.usace.army.mil/dd/common/projects/www/dwr.html"),
    ("USA0001380", "Wolf Creek Dam", "Lake Cumberland", "LRN", "WLCK2-WOLF_CREEK.Elev-Pool.Inst.1Hour.0.dcp-rev", 673, 723, "Bottom of Power", "https://www.lrn-wc.usace.army.mil/"),
    ("USA0003424", "Dale Hollow Dam", "Dale Hollow Lake", "LRN", "DLHT1-DALE_HOLLOW.Elev-Pool.Inst.1Hour.0.dcp-rev", 631, 651, "Bottom of Power", "https://www.lrn-wc.usace.army.mil/"),
    ("USA0006417", "Center Hill Dam", "Center Hill Lake", "LRN", "CEHT1-CENTER_HILL.Elev-Pool.Inst.1Hour.0.dcp-rev", 618, 648, "Bottom of Power", "https://www.lrn-wc.usace.army.mil/"),
    ("USA0006171", "Laurel Dam", "Laurel River Lake", "LRN", "LAPK2-LAUREL.Elev-Pool.Inst.1Hour.0.dcp-rev", 982, 1018.5, "Bottom of Power", "https://www.lrn-wc.usace.army.mil/"),
]

def band(mn, top):
    """Amber / red elevations for a CWMS project: within 25% / 10% of the min-to-top band above the minimum pool."""
    return round(mn + .25 * (top - mn), 1), round(mn + .10 * (top - mn), 1)

def cwms_one(jget, c, now):
    import urllib.parse
    q = urllib.parse.urlencode({"name": c[4], "office": c[3], "begin": (now - timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%SZ"), "unit": "EN"})
    d = jget(CWMS + "?" + q, timeout=25)
    pts = sorted((datetime.fromtimestamp(v[0] / 1000, timezone.utc).replace(tzinfo=None), float(v[1])) for v in d.get("values") or [] if v and v[1] is not None)
    if not pts: return {"status": "na", "err": "no data"}
    last_t, ft = pts[-1]
    if (now - last_t).days > 3: return {"status": "na", "err": "data is stale", "date": last_t.strftime("%Y-%m-%d")}
    wk = [v for t, v in pts if (last_t - t).total_seconds() >= 7 * 86400]
    return {"ft": round(ft, 2), "date": last_t.strftime("%Y-%m-%d"), "chg7": round(ft - wk[-1], 2) if wk else None, "above_min": round(ft - c[5], 1)}

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
        v.update({k: r[k] for k in ("dam", "lake", "min_pool", "amber", "red", "url")}); v.update(src=SRC, method="pool", min_name="minimum power pool")
        out[r["id"]] = v
    for c in CW:
        amber, red = band(c[5], c[6])
        try: v = cwms_one(jget, c, now)
        except Exception as ex: v = {"status": "na", "err": type(ex).__name__}
        if "ft" in v: v["status"] = "out" if v["ft"] <= red else "low" if v["ft"] <= amber else "ok"
        v.update(dam=c[1], lake=c[2], min_pool=c[5], top=c[6], amber=amber, red=red, url=c[8], src=CSRC, method="pool",
                 min_name="minimum power pool" if c[7] == "Bottom of Power" else "minimum operating pool", level=c[7])
        out[c[0]] = v
    return {"levels": out, "checked": int(time.time()),
            "method": "U.S.: lake elevation vs. the dam's published minimum power or operating pool (Reclamation HDB, USACE CWMS). Worldwide: satellite level relative to the reservoir's usual level for the season (NASA GSFC G-REALM). Grey: no level data."}
