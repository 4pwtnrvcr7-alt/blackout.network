"""Sky view data for /network (Nov 23 2026, pt1755u): satellite constellations and space weather, keyless and cached.
Orbital elements: CelesTrak GP data (CSV), one download per group at most every 6 h, 2 h back-off after an error (CelesTrak's
published usage rules); Starlink reuses the Starlink page's cached copy. Propagation happens in the browser (satellite.js SGP4).
Space weather: NOAA SWPC scales (R/S/G) and planetary Kp, cached 10 min. Read-only; no keys; nothing estimated."""
import os, csv, io, json, time, threading, urllib.request
from datetime import datetime, timezone

UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/network; cached 6 h per group)"
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
          ("goes", "GOES", "goes", "NOAA weather satellites, geostationary")]
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
