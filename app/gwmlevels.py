"""Satellite reservoir levels for hydro dams worldwide (pt1815u, Nov 24 2026): NASA GSFC Global Water Monitor (G-REALM, formerly
USDA FAS; U.S. government work, no account or key). The HEP bundle covers ~340 hydropower reservoirs:
  https://har.gsfc.nasa.gov/pub/danu/power/Reservoir_data/GWM_HEP_reservoirs.tgz   (product page https://earth.gsfc.nasa.gov/gwm/lake/Index)
Each file is a radar-altimetry series of height variation (m) relative to the reservoir's own reference mean; there is no absolute
power-pool threshold, so the rating is relative to the usual level for this time of year:
  same-season values = every past year's readings within 20 days of the latest reading's day of year (ice-flagged readings skipped);
  red   = latest below the 5th percentile of those values and 1 m+ below their median (well below normal),
  amber = below the 20th percentile and 0.5 m+ below the median, green otherwise;
  grey  = latest reading older than 60 days or fewer than 5 seasonal years.
Only reservoirs whose GWM name matches a WRI hydro plant (gwm_match.json, built by tools/build_gwm_match.py) are used.
"""
import io, json, os, tarfile, time, functools
from datetime import date

URL = "https://har.gsfc.nasa.gov/pub/danu/power/Reservoir_data/GWM_HEP_reservoirs.tgz"
PAGE = "https://earth.gsfc.nasa.gov/gwm/lake/Index"

def parse(text):
    lines = text.splitlines(); name = lines[1].split(":")[0].split(None, 1)[1].strip() if len(lines) > 1 else ""
    pts = []
    for l in lines:
        f = l.split()
        if len(f) < 16 or not f[2].isdigit() or f[2] == "99999999": continue
        try: h = float(f[5]); ice = f[13] == "1"
        except ValueError: continue
        if h > 900 or ice: continue
        d = f[2]; pts.append((date(int(d[:4]), int(d[4:6]), int(d[6:8])), h))
    return name, pts

def pct(vals, q):
    v = sorted(vals); k = (len(v) - 1) * q; i = int(k); return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i)

def rate(pts, today=None):
    today = today or date.today()
    if not pts: return {"status": "na", "err": "no readings"}
    pts.sort(); d0, h0 = pts[-1]
    if (today - d0).days > 60: return {"status": "na", "err": "latest reading is older than 60 days", "date": d0.isoformat()}
    doy = d0.timetuple().tm_yday
    by = {}
    for d, h in pts:
        if d.year == d0.year: continue
        dd = abs(d.timetuple().tm_yday - doy); dd = min(dd, 365 - dd)
        if dd <= 20: by.setdefault(d.year, []).append(h)
    vals = [x for v in by.values() for x in v]
    if len(by) < 5: return {"status": "na", "err": "too few past years for this season", "date": d0.isoformat()}
    p5, p20, p50 = pct(vals, .05), pct(vals, .20), pct(vals, .50)
    dev = h0 - p50   # a tiny dip in a tightly regulated pool is not "well below normal": amber also needs 0.5 m below the median, red 1 m
    st = "out" if h0 < p5 and dev <= -1.0 else "low" if h0 < p20 and dev <= -0.5 else "ok"
    return {"status": st, "date": d0.isoformat(), "dev_m": round(h0 - p50, 2), "p20_m": round(p20 - p50, 2), "p5_m": round(p5 - p50, 2), "years": len(by), "since": pts[0][0].year}

@functools.lru_cache(maxsize=1)
def match(static):
    return json.load(open(os.path.join(static, "gwm_match.json")))

def build(http, static):
    m = match(static); raw = http(URL, timeout=90)
    tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz"); out = {}
    for mem in tf.getmembers():
        lid = mem.name.split("/")[-1][4:10]
        if lid not in m["lakes"]: continue
        name, pts = parse(tf.extractfile(mem).read().decode("latin-1"))
        r = rate(pts); r.update({"lake": name.replace("_", " "), "lake_id": lid, "url": PAGE, "src": "NASA GSFC Global Water Monitor (G-REALM), satellite radar altimetry",
                                 "method": "satellite, relative to usual level"})
        out[m["lakes"][lid]] = r
    return out

def snapshot(static):
    """Ratings computed at build time (tools/build_gwm_match.py), served until the live bundle is fetched; reading dates stay honest."""
    return dict(match(static).get("snap") or {})
