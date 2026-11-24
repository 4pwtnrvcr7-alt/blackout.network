"""Sky view data for /grid (Nov 23 2026, pt1755u): satellite constellations and space weather, keyless and cached.
Orbital elements: CelesTrak GP data (CSV), one download per group at most every 6 h, 2 h back-off after an error (CelesTrak's
published usage rules); Starlink reuses the Starlink page's cached copy. Propagation happens in the browser (satellite.js SGP4).
Space weather: NOAA SWPC scales (R/S/G) and planetary Kp, cached 10 min. Read-only; no keys; nothing estimated."""
import os, csv, io, json, time, threading, urllib.request
from datetime import datetime, timezone

UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/grid; cached 6 h per group)"
CT = "https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=csv"
MAX_AGE = 6 * 3600; BACKOFF = 2 * 3600 + 300
# id, label, CelesTrak group, what it is
GROUPS = [("starlink", "Starlink", "starlink", "SpaceX broadband, low Earth orbit"),
          ("gps", "GPS", "gps-ops", "U.S. navigation, medium Earth orbit"),
          ("glonass", "GLONASS", "glo-ops", "Russian navigation, medium Earth orbit"),
          ("galileo", "Galileo", "galileo", "European navigation, medium Earth orbit"),
          ("beidou", "BeiDou", "beidou", "Chinese navigation, medium and geosynchronous orbits"),
          ("iridium", "Iridium", "iridium-NEXT", "Satellite phones and messaging, low Earth orbit"),
          ("oneweb", "OneWeb", "oneweb", "Eutelsat OneWeb broadband, low Earth orbit"),
          ("goes", "GOES", "goes", "NOAA weather satellites, geostationary"),
          ("iss", "ISS", "stations", "International Space Station, low Earth orbit")]
ISS_NORAD = 25544
_L = threading.Lock(); _KL = {}; _BO = {}; _ERR = {}; _MEM = {}

SUP_STARLINK = "https://celestrak.org/NORAD/elements/supplemental/sup-gp.php?FILE=starlink&FORMAT=csv"

def _dir():
    d = os.environ.get("BN_STARLINK_CACHE_DIR") or os.path.join(os.environ.get("BN_STATE_DIR") or "/tmp", "bn_starlink")
    os.makedirs(d, mode=0o700, exist_ok=True); return d

def _file(gid, group):
    if gid == "starlink":
        try:
            import netstarlink as SL
            p, mt, err = SL.celestrak_file("gp.csv", SL.GP_URL, SL.GP_MAX_AGE)
            if p: return p, mt, err
        except Exception as e:
            err = type(e).__name__
        # GROUP=starlink refused (CelesTrak 403s repeat/shared-IP downloads): use CelesTrak's supplemental
        # SpaceX-ephemeris GP file instead (same CSV columns), on the same polite 6 h / 2 h schedule.
        return _fetch("starlink_sup", SUP_STARLINK)
    return _fetch(gid, CT.format(g=group))

def _fetch(gid, url):
    p = os.path.join(_dir(), f"sky_{gid}.csv")
    have = lambda: (p, os.path.getmtime(p)) if os.path.exists(p) else (None, None)
    fp, mt = have()
    if mt and time.time() - mt < MAX_AGE: return fp, mt, None
    if time.time() < _BO.get(gid, 0): return fp, mt, _ERR.get(gid)
    with _L: kl = _KL.setdefault(gid, threading.Lock())
    with kl:
        fp, mt = have()
        if mt and time.time() - mt < MAX_AGE: return fp, mt, None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"}), timeout=30) as r:
                b = r.read(8_000_000)
            if not b.startswith(b"OBJECT_NAME") or b.count(b"\n") < 3: raise RuntimeError("unexpected response")
            with open(p + ".tmp", "wb") as f: f.write(b)
            os.replace(p + ".tmp", p); _ERR.pop(gid, None)
            return p, os.path.getmtime(p), None
        except Exception as e:
            _BO[gid] = time.time() + BACKOFF; _ERR[gid] = type(e).__name__
            return fp, mt, _ERR[gid]

def _rows(p, gi):
    out = []
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                e = r["EPOCH"]
                ep = datetime.strptime(e[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() + (float("0" + e[19:26]) if len(e) > 20 else 0)
                out.append([gi, int(r["NORAD_CAT_ID"]), round(ep, 3), round(float(r["MEAN_MOTION"]), 8), round(float(r["ECCENTRICITY"]), 7), round(float(r["INCLINATION"]), 4),
                            round(float(r["RA_OF_ASC_NODE"]), 4), round(float(r["ARG_OF_PERICENTER"]), 4), round(float(r["MEAN_ANOMALY"]), 4), float(f"{float(r['BSTAR'] or 0):.5g}"),
                            (r.get("OBJECT_NAME") or "").strip()[:28]])
            except Exception:
                continue
    return out

def sky(lite=False):
    """One payload for every constellation. lite = phones: Starlink thinned to every 3rd satellite (still ~3,000)."""
    files = [_file(g, grp) for g, _, grp, _ in GROUPS]
    key = (lite, tuple(f[1] for f in files))
    hit = _MEM.get("sky_lite" if lite else "sky_full")
    if hit and hit[0] == key: return hit[1]
    sats = []; groups = []; newest = 0
    for gi, ((gid, label, grp, what), (p, mt, err)) in enumerate(zip(GROUPS, files)):
        rows = _rows(p, gi) if p else []
        if gid == "iss":
            rows = [r for r in rows if r[1] == ISS_NORAD]
        total = len(rows)
        if lite and gid == "starlink": rows = rows[::3]
        sats += rows; newest = max(newest, mt or 0)
        groups.append(dict(id=gid, name=label, what=what, total=total, shown=len(rows), fetched=datetime.fromtimestamp(mt, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt else None,
                           error=None if p else (err or "not loaded yet")))
    b = json.dumps({"groups": groups, "fields": ["g", "norad", "epoch_unix", "mean_motion", "ecc", "inc", "raan", "argp", "ma", "bstar", "name"], "sats": sats,
                    "source": "CelesTrak GP data", "source_url": "https://celestrak.org/NORAD/elements/"}, separators=(",", ":")).encode()
    _MEM["sky_lite" if lite else "sky_full"] = (key, b)
    return b

def sky_cached(lite=False):
    k = "sky_lite" if lite else "sky_full"; hit = _MEM.get(k)
    if hit and time.time() - _MEM.get(k + "_t", 0) < 600: return hit[1]
    b = sky(lite); _MEM[k + "_t"] = time.time(); return b

def _j(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=12) as r:
        return json.loads(r.read(2_000_000).decode("utf-8", "replace"))

IMPACT = {  # NOAA scale -> plain impact on satellite navigation and radio (from NOAA's own scale descriptions)
 "G": {3: "GPS position errors and loss of lock possible for hours", 4: "GPS degraded for hours, satellite navigation unreliable", 5: "GPS degraded for days, satellite navigation unreliable"},
 "R": {2: "Short HF radio and GPS fades on the sunlit side", 3: "HF radio blackouts and GPS errors on the sunlit side for about an hour", 4: "HF radio blackout and GPS errors on the sunlit side for hours", 5: "Complete HF blackout on the sunlit side, GPS errors"},
 "S": {2: "HF radio degraded near the poles", 3: "Satellite and HF radio problems near the poles", 4: "Satellite operations and polar radio badly affected", 5: "Satellite outages possible, polar radio blackout"},
}
def space():
    hit = _MEM.get("space")
    if hit and time.time() - hit[0] < 600: return hit[1]
    out = {"ok": False}
    try:
        sc = _j("https://services.swpc.noaa.gov/products/noaa-scales.json").get("0") or {}
        cur = {k: int((sc.get(k) or {}).get("Scale") or 0) for k in ("R", "S", "G")}
        kp = None; kp_t = None
        try:
            kk = _j("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
            last = kk[-1]
            if isinstance(last, dict): kp, kp_t = last.get("Kp"), last.get("time_tag")
            else: kp, kp_t = float(last[1]), last[0]
        except Exception: pass
        imp = [IMPACT[k][v] for k, v in (("G", cur["G"]), ("R", cur["R"]), ("S", cur["S"])) if v in IMPACT[k]]
        gnss = "Degraded" if cur["G"] >= 4 or cur["R"] >= 4 or cur["S"] >= 4 else "Watch" if cur["G"] >= 2 or cur["R"] >= 2 or cur["S"] >= 2 else "Normal"
        out = dict(ok=True, scales=cur, kp=kp, kp_time=kp_t, gnss=gnss, impacts=imp or ["No space-weather impact on GPS or satellite links expected right now"],
                   updated=f"{sc.get('DateStamp', '')}T{sc.get('TimeStamp', '')}Z", source="NOAA Space Weather Prediction Center", source_url="https://www.swpc.noaa.gov/",
                   jamming=dict(name="GPSJam (daily GPS interference map from aircraft reports)", url="https://gpsjam.org/"))
    except Exception as e:
        out = {"ok": False, "error": type(e).__name__}
        if hit: return dict(hit[1], stale=True)
    _MEM["space"] = (time.time(), out)
    return out


# Tracked debris groups published by CelesTrak (keyless GP CSV). Cosmos 1408 may be a short residual catalog.
DEBRIS_GROUPS = (("fengyun-1c-debris", "Fengyun-1C debris"),
                 ("iridium-33-debris", "Iridium 33 debris"),
                 ("cosmos-2251-debris", "Cosmos 2251 debris"),
                 ("cosmos-1408-debris", "Cosmos 1408 debris"))

def debris(lite=False):
    """TLE payload for the toggleable debris layer. Decimated on the server (heavier on phones)."""
    files = [_fetch(gid, CT.format(g=gid)) for gid, _ in DEBRIS_GROUPS]
    key = (lite, tuple(f[1] for f in files))
    hit = _MEM.get("debris_lite" if lite else "debris_full")
    if hit and hit[0] == key: return hit[1]
    sats, groups, newest, total_all = [], [], 0, 0
    step = 6 if lite else 2
    for gi, ((gid, label), (p, mt, err)) in enumerate(zip(DEBRIS_GROUPS, files)):
        rows = _rows(p, gi) if p else []
        total = len(rows); total_all += total
        rows = rows[::step]
        sats += rows; newest = max(newest, mt or 0)
        groups.append(dict(id=gid, name=label, total=total, shown=len(rows),
                           fetched=datetime.fromtimestamp(mt, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt else None,
                           error=None if p else (err or "not loaded yet")))
    b = json.dumps({"groups": groups, "fields": ["g", "norad", "epoch_unix", "mean_motion", "ecc", "inc", "raan", "argp", "ma", "bstar", "name"],
                    "sats": sats, "total": total_all, "shown": len(sats), "lite": lite, "step": step,
                    "source": "CelesTrak GP data (debris groups)", "source_url": "https://celestrak.org/NORAD/elements/"}, separators=(",", ":")).encode()
    _MEM["debris_lite" if lite else "debris_full"] = (key, b)
    return b

def debris_cached(lite=False):
    k = "debris_lite" if lite else "debris_full"; hit = _MEM.get(k)
    if hit and time.time() - _MEM.get(k + "_t", 0) < 600: return hit[1]
    b = debris(lite); _MEM[k + "_t"] = time.time(); return b

AU_KM = 149597870.7
LD_KM = 384400.0  # conventional mean lunar distance used with close-approach distances
CNEOS_H_SIZE = "https://cneos.jpl.nasa.gov/tools/ast_size_est.html"
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
CAD_API = "https://ssd-api.jpl.nasa.gov/cad.api"
SBDB_LOOKUP = "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr="

# Launch dates and mission status are NASA (or JPL Horizons) published facts, not derived from the ephemeris.
SS_BODIES = (
    dict(id="roadster", name="Tesla Roadster / Starman", command="-143205",
         launch="2018-02-06", launch_label="6 February 2018 (SpaceX Falcon Heavy test flight)",
         status="Heliocentric orbit around the Sun. Derelict payload. Tracked by NASA/JPL Horizons as target -143205.",
         source_name="NASA/JPL Horizons", source_url="https://ssd.jpl.nasa.gov/horizons/app.html#/"),
    dict(id="voyager1", name="Voyager 1", command="-31",
         launch="1977-09-05", launch_label="5 September 1977",
         status="Operational. In interstellar space since 25 August 2012.",
         source_name="NASA Voyager 1", source_url="https://science.nasa.gov/mission/voyager/voyager-1/"),
    dict(id="voyager2", name="Voyager 2", command="-32",
         launch="1977-08-20", launch_label="20 August 1977",
         status="Operational. In interstellar space since 5 November 2018.",
         source_name="NASA Voyager 2", source_url="https://science.nasa.gov/mission/voyager/voyager-2/"),
)

def _horizons_observer(command, center, when):
    """One Horizons observer row: range (AU), range-rate (km/s), one-way light-time (minutes). when is UTC datetime."""
    import urllib.parse
    start = when.strftime("%Y-%m-%d %H:%M")
    stop = datetime.fromtimestamp(when.timestamp() + 3600, timezone.utc).strftime("%Y-%m-%d %H:%M")
    q = dict(format="json", COMMAND=str(command), OBJ_DATA="NO", MAKE_EPHEM="YES", EPHEM_TYPE="OBSERVER",
             CENTER=str(center), QUANTITIES="20,21", CSV_FORMAT="YES", CAL_FORMAT="CAL",
             START_TIME=start, STOP_TIME=stop, STEP_SIZE="1 h")
    url = HORIZONS_API + "?" + urllib.parse.urlencode(q)
    j = _j(url)
    if j.get("error"):
        raise RuntimeError(str(j["error"])[:200])
    res = j.get("result") or ""
    a, b = res.find("$SOE"), res.find("$$EOE")
    if a < 0 or b < a:
        raise RuntimeError("no Horizons ephemeris table")
    for line in res[a + 4:b].splitlines():
        line = line.strip()
        if not line or line.startswith("$"):
            continue
        parts = [x.strip() for x in line.split(",")]
        nums = []
        for x in parts[1:]:
            if not x or x in (".", "n.a.", "n.a"):
                continue
            try:
                nums.append(float(x))
            except ValueError:
                continue
        if len(nums) >= 3:
            return {"delta_au": nums[0], "deldot_km_s": nums[1], "light_min": nums[2], "time": parts[0]}
        if len(nums) >= 1:
            return {"delta_au": nums[0], "deldot_km_s": nums[1] if len(nums) > 1 else None, "light_min": None, "time": parts[0]}
    raise RuntimeError("Horizons table had no numeric row")

def _gmst_deg(dt):
    jd = dt.timestamp() / 86400.0 + 2440587.5
    t = (jd - 2451545.0) / 36525.0
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - t * t * t / 38710000.0) % 360.0

def _horizons_dir(command, when):
    """Geocentric J2000 vector -> geographic lon/lat of the direction from Earth (approx, GMST)."""
    import math, urllib.parse
    start = when.strftime("%Y-%m-%d %H:%M")
    stop = datetime.fromtimestamp(when.timestamp() + 3600, timezone.utc).strftime("%Y-%m-%d %H:%M")
    q = dict(format="json", COMMAND=str(command), OBJ_DATA="NO", MAKE_EPHEM="YES", EPHEM_TYPE="VECTORS",
             CENTER="500@399", REF_PLANE="FRAME", OUT_UNITS="KM", VEC_TABLE="1", CSV_FORMAT="YES",
             START_TIME=start, STOP_TIME=stop, STEP_SIZE="1 h")
    j = _j(HORIZONS_API + "?" + urllib.parse.urlencode(q))
    if j.get("error"):
        raise RuntimeError(str(j["error"])[:200])
    res = j.get("result") or ""
    a, b = res.find("$$SOE"), res.find("$$EOE")
    if a < 0 or b < a:
        raise RuntimeError("no Horizons vector table")
    for line in res[a + 5:b].splitlines():
        line = line.strip()
        if not line or line.startswith("$"):
            continue
        nums = []
        for x in line.split(","):
            x = x.strip()
            try:
                nums.append(float(x))
            except ValueError:
                continue
        # skip JD; take first X Y Z
        if len(nums) >= 4:
            x, y, z = nums[1], nums[2], nums[3]
        elif len(nums) >= 3:
            x, y, z = nums[0], nums[1], nums[2]
        else:
            continue
        lon = (math.degrees(math.atan2(y, x)) - _gmst_deg(when) + 540.0) % 360.0 - 180.0
        lat = math.degrees(math.atan2(z, math.hypot(x, y)))
        return {"lon": round(lon, 3), "lat": round(lat, 3)}
    raise RuntimeError("Horizons vector table had no numeric row")

def _au_fields(row):
    if not row or row.get("delta_au") is None:
        return None
    au = float(row["delta_au"])
    km = au * AU_KM
    out = {"au": round(au, 6), "km": int(round(km))}
    if row.get("light_min") is not None:
        out["light_min"] = round(float(row["light_min"]), 4)
    if row.get("deldot_km_s") is not None:
        out["deldot_km_s"] = round(float(row["deldot_km_s"]), 4)
    if row.get("time"):
        out["time"] = row["time"]
    return out

def solar_system():
    """Heliocentric inset data: Roadster, Voyager 1, Voyager 2. Distances from JPL Horizons (keyless). Cached 1 h."""
    hit = _MEM.get("ss2")
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    when = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    objs, errors = [], []
    for meta in SS_BODIES:
        rec = {k: meta[k] for k in ("id", "name", "command", "launch", "launch_label", "status", "source_name", "source_url")}
        rec["ok"] = False
        try:
            earth = _horizons_observer(meta["command"], "500@399", when)
            sun = _horizons_observer(meta["command"], "500@10", when)
            rec["earth"] = _au_fields(earth)
            rec["sun"] = _au_fields(sun)
            try:
                d = _horizons_dir(meta["command"], when)
                if rec["earth"] is not None and d:
                    rec["earth"]["lon"], rec["earth"]["lat"] = d["lon"], d["lat"]
            except Exception:
                pass
            rec["ok"] = rec["earth"] is not None and rec["sun"] is not None
            rec["epoch"] = (earth or {}).get("time") or when.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as e:
            rec["error"] = type(e).__name__
            errors.append(f"{meta['id']}:{type(e).__name__}")
        objs.append(rec)
    out = dict(ok=any(o.get("ok") for o in objs), objects=objs, epoch=when.strftime("%Y-%m-%dT%H:%M:%SZ"),
               source="NASA/JPL Horizons", source_url="https://ssd.jpl.nasa.gov/horizons/",
               errors=errors or None)
    if not out["ok"] and hit:
        return dict(hit[1], stale=True, error="horizons_failed")
    _MEM["ss2"] = (time.time(), out)
    return out

def size_from_h(h, albedo=0.14):
    """Nominal diameter in km from absolute magnitude H (CNEOS convention, default albedo 0.14)."""
    if h is None:
        return None
    return 1329.0 * (10 ** (-float(h) / 5.0)) / (float(albedo) ** 0.5)

def cad():
    """JPL SBDB close approaches to Earth, next 60 days, dist-max 0.05 AU. Cached 6 h."""
    hit = _MEM.get("cad")
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    start = datetime.now(timezone.utc).date()
    from datetime import timedelta
    end = start + timedelta(days=60)
    import urllib.parse
    q = urllib.parse.urlencode({"date-min": str(start), "date-max": str(end), "dist-max": "0.05",
                                "diameter": "true", "fullname": "true"})
    try:
        j = _j(CAD_API + "?" + q)
    except Exception as e:
        if hit:
            return dict(hit[1], stale=True, error=type(e).__name__)
        return {"ok": False, "error": type(e).__name__, "objects": []}
    fields = j.get("fields") or []
    idx = {n: i for i, n in enumerate(fields)}
    objs = []
    for row in j.get("data") or []:
        def cell(name):
            i = idx.get(name)
            return None if i is None or i >= len(row) else row[i]
        dist = cell("dist")
        try:
            dist_au = float(dist)
        except (TypeError, ValueError):
            continue
        dist_km = dist_au * AU_KM
        dist_ld = dist_km / LD_KM
        h = cell("h")
        try:
            h = float(h) if h is not None else None
        except (TypeError, ValueError):
            h = None
        diam = cell("diameter")
        try:
            diam = float(diam) if diam not in (None, "") else None
        except (TypeError, ValueError):
            diam = None
        est = None if diam is not None else (size_from_h(h) if h is not None else None)
        des = (cell("des") or "").strip()
        full = (cell("fullname") or "").strip() or des
        objs.append(dict(des=des, name=full.strip(), cd=cell("cd"), jd=cell("jd"),
                         dist_au=round(dist_au, 8), dist_km=int(round(dist_km)), dist_ld=round(dist_ld, 3),
                         h=h, diameter_km=diam, size_est_km=None if est is None else round(est, 4),
                         size_note=None if diam is not None else ("Nominal diameter from H at albedo 0.14 (CNEOS)." if est is not None else None),
                         v_rel=cell("v_rel"), source_url=SBDB_LOOKUP + urllib.parse.quote(des)))
    out = dict(ok=True, count=len(objs), date_min=str(start), date_max=str(end), dist_max_au=0.05,
               objects=objs, source="NASA/JPL SBDB Close-Approach Data API",
               source_url="https://ssd-api.jpl.nasa.gov/doc/cad.html",
               size_ref=CNEOS_H_SIZE)
    _MEM["cad"] = (time.time(), out)
    return out
