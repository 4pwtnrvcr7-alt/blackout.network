"""Launches on the /grid Sky view (Nov 24 2026, pt1824u).

Real data: The Space Devs Launch Library 2 (keyless free tier, about 15 calls an hour). One call at most every 15 min
(30 min back-off after an error), disk cached so restarts and workers share it. Fields used: time, status, vehicle,
mission, orbit, pad coordinates, LL2 mission timeline (MECO, stage separation, landing, SECO), booster landing
location / type / downrange distance / outcome, failure reason.

Modeled (not telemetry): every path point. The ascent ground track follows a great circle from the pad at an azimuth
derived from the orbit type and pad latitude; altitude and downrange follow a generic two-stage profile scaled to the
LL2 timeline. The booster arc runs from staging to the LL2 landing site (land zones have coordinates; droneships are
placed at LL2's downrange distance along the azimuth). No imagery is used."""
import os, json, math, time, threading, urllib.request, urllib.parse, re
from datetime import datetime, timezone, timedelta

UA = "BlackoutNetwork-status/2.0 (+https://blackout.network/grid; cached 15 min)"
LL2 = "https://ll.thespacedevs.com/2.3.0/launches/"
MAX_AGE = 15 * 60; BACKOFF = 30 * 60
PAST_DAYS = 7; NEXT_DAYS = 14
EARTH_R = 6371.0088
_L = threading.Lock(); _ST = {"err": None, "err_t": 0}; _MEM = {}

def _dir():
    d = os.path.join(os.environ.get("BN_STATE_DIR") or "/tmp", "bn_launch")
    os.makedirs(d, mode=0o700, exist_ok=True); return d

def _url(now):
    a = (now - timedelta(days=PAST_DAYS)).strftime("%Y-%m-%dT%H:00:00Z")
    b = (now + timedelta(days=NEXT_DAYS)).strftime("%Y-%m-%dT%H:00:00Z")
    return LL2 + "?" + urllib.parse.urlencode({"net__gte": a, "net__lte": b, "ordering": "net", "mode": "detailed", "limit": "40"})

def _raw():
    """LL2 window JSON, from disk if fresh; otherwise one polite call. Returns (dict or None, fetched_unix, error)."""
    p = os.path.join(_dir(), "ll2_window.json")
    mt = os.path.getmtime(p) if os.path.exists(p) else 0
    def disk():
        try:
            with open(p) as f: return json.load(f)
        except Exception: return None
    if mt and time.time() - mt < MAX_AGE: return disk(), mt, None
    with _L:
        mt = os.path.getmtime(p) if os.path.exists(p) else 0
        if mt and time.time() - mt < MAX_AGE: return disk(), mt, None
        if time.time() - _ST["err_t"] < BACKOFF: return disk(), mt, _ST["err"]
        try:
            req = urllib.request.Request(_url(datetime.now(timezone.utc)), headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r: b = r.read()
            j = json.loads(b)
            if not isinstance(j.get("results"), list): raise ValueError("no results")
            tmp = p + ".tmp"
            with open(tmp, "wb") as f: f.write(b)
            os.replace(tmp, p); _ST["err"] = None
            return j, os.path.getmtime(p), None
        except Exception as e:
            _ST["err"] = getattr(e, "code", None) and f"HTTP {e.code}" or type(e).__name__; _ST["err_t"] = time.time()
            return disk(), mt, _ST["err"]

def _dur(s):
    """ISO 8601 duration like PT2M26S / -PT3S / P0D / PT1H6M -> seconds."""
    if not s: return None
    m = re.fullmatch(r"(-)?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", s.strip())
    if not m: return None
    v = int(m.group(2) or 0) * 86400 + int(m.group(3) or 0) * 3600 + int(m.group(4) or 0) * 60 + float(m.group(5) or 0)
    return -v if m.group(1) else v

def _dest(lat, lon, az, km):
    """Great-circle destination point."""
    d = km / EARTH_R; la, lo, a = math.radians(lat), math.radians(lon), math.radians(az)
    la2 = math.asin(math.sin(la) * math.cos(d) + math.cos(la) * math.sin(d) * math.cos(a))
    lo2 = lo + math.atan2(math.sin(a) * math.sin(d) * math.cos(la), math.cos(d) - math.sin(la) * math.sin(la2))
    return math.degrees(la2), (math.degrees(lo2) + 540) % 360 - 180

def _lerp_ll(a, b, u):
    """Spherical interpolation between (lat, lon) points."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    v1 = (math.cos(la1) * math.cos(lo1), math.cos(la1) * math.sin(lo1), math.sin(la1))
    v2 = (math.cos(la2) * math.cos(lo2), math.cos(la2) * math.sin(lo2), math.sin(la2))
    dot = max(-1, min(1, sum(x * y for x, y in zip(v1, v2)))); om = math.acos(dot)
    if om < 1e-9: return a
    s1, s2 = math.sin((1 - u) * om) / math.sin(om), math.sin(u * om) / math.sin(om)
    x, y, z = (s1 * p + s2 * q for p, q in zip(v1, v2))
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))

ISS_WORDS = ("dragon", "crew-", "crs", "cygnus", "progress", "soyuz ms", "axiom", "ax-", "starliner", "htv", "iss")
CSS_WORDS = ("shenzhou", "tianzhou")

def inclination(r):
    name = (r.get("name") or "").lower(); orb = (((r.get("mission") or {}).get("orbit") or {}).get("abbrev") or "").upper()
    lat = abs(float(r["pad"]["latitude"]))
    if any(w in name for w in ISS_WORDS): return 51.64
    if any(w in name for w in CSS_WORDS): return 41.47
    if orb in ("SSO",): return 97.6
    if orb in ("PO",): return 90.0
    if orb in ("GTO", "GEO", "GSO", "MEO", "HEO", "TLI", "HCO", "L1", "L2", "SUB"): return lat
    if "starship" in name: return lat
    if abs(float(r["pad"]["longitude"]) + 120.6) < 0.5 and abs(lat - 34.6) < 0.5: return 70.0   # Vandenberg LEO default
    return max(53.0, lat + 1)

def azimuth(lat, lon, inc):
    """Launch azimuth (deg from north) for an inclination from this pad. Southward branch from Vandenberg and for
    retrograde orbits outside the equatorial band; the generic northeast branch elsewhere."""
    c = math.cos(math.radians(inc)) / max(1e-6, math.cos(math.radians(lat)))
    a = math.degrees(math.asin(max(-1.0, min(1.0, c))))
    vandenberg = abs(lon + 120.6) < 0.6 and abs(lat - 34.6) < 0.6
    if inc >= 90 and not (0 <= lat <= 10): return (180 - a) % 360
    if inc >= 90: return (360 + a) % 360
    if vandenberg or lat < 0: return (180 - a) % 360
    return a % 360

def _events(r):
    ev = {}
    for t in r.get("timeline") or []:
        k = ((t.get("type") or {}).get("abbrev") or "").strip(); s = _dur(t.get("relative_time"))
        if s is None or s < 0 or not k: continue
        ev.setdefault(k, s)
    return ev

def _fmt_t(s):
    s = int(round(s)); return f"T+{s // 60}:{s % 60:02d}" if s < 3600 else f"T+{s // 3600}h{(s % 3600) // 60:02d}m"

def model(r):
    """Modeled ascent / booster paths and labelled event points for one LL2 launch."""
    pad = r.get("pad") or {}
    lat, lon = float(pad["latitude"]), float(pad["longitude"])
    ev = _events(r); name = (r.get("name") or "")
    inc = inclination(r); az = azimuth(lat, lon, inc)
    orb = (((r.get("mission") or {}).get("orbit") or {}).get("abbrev") or "")
    t_m = ev.get("MECO") or ev.get("Booster Separation") or 150.0
    t_sep = ev.get("Stage 2 Separation") if ev.get("Stage 2 Separation") and ev["Stage 2 Separation"] - t_m < 30 else t_m + 3
    t_seco = ev.get("SECO-1") or ev.get("SECO") or max(t_m + 330, 510.0)
    if t_seco <= t_sep + 60: t_seco = t_sep + 360
    h_orb = 210.0
    stages = (r.get("rocket") or {}).get("launcher_stage") or []
    land = None
    for s in stages:
        L = s.get("landing") or {}
        if L.get("attempt"): land = L; break
    rtls = bool(land and ((land.get("type") or {}).get("abbrev") == "RTLS" or (land.get("downrange_distance") or 999) < 20))
    dr_m = 62.0 if rtls else 85.0
    up = []
    def put(t, dr, alt, lst, drift=True):
        la, lo = _dest(lat, lon, az, dr)
        if drift and t > t_seco: lo = (lo - 360.0 / 86164.0 * (t - t_seco) + 540) % 360 - 180   # Earth turns under the coasting stage
        lst.append([round(lo, 4), round(la, 4), round(alt * 1000), round(t, 1)])
    n1 = 18
    for i in range(n1 + 1):
        u = i / n1; t = t_sep * u
        put(t, dr_m * u ** 2.3, 68.0 * u ** 1.7, up)
    n2 = 30
    for i in range(1, n2 + 1):
        u = i / n2; t = t_sep + (t_seco - t_sep) * u
        put(t, dr_m + (t_seco - t_sep) * (2.0 * u + 2.8 * u * u), 68.0 + (h_orb - 68.0) * math.sin(math.pi / 2 * u) ** 0.8, up)
    dr_seco = dr_m + (t_seco - t_sep) * 4.8
    coast = 1500.0
    for i in range(1, 16):
        t = t_seco + coast * i / 15
        put(t, dr_seco + 7.75 * (t - t_seco), h_orb, up)
    labels = [dict(t=0, k="liftoff", text="Liftoff", at=up[0][:3])]
    st = (r.get("status") or {}).get("abbrev") or ""
    def at_t(tt):
        best = min(up, key=lambda p: abs(p[3] - tt)); return best[:3]
    if ev.get("Max-Q"): labels.append(dict(t=ev["Max-Q"], k="maxq", text="Max-Q " + _fmt_t(ev["Max-Q"]), at=at_t(ev["Max-Q"])))
    labels.append(dict(t=t_sep, k="sep", text="Stage separation " + _fmt_t(t_sep) + ("" if "Stage 2 Separation" in ev else " (est.)"), at=at_t(t_sep)))
    labels.append(dict(t=t_seco, k="seco", text=("Engine cutoff " + _fmt_t(t_seco)) + ("" if ("SECO-1" in ev or "SECO" in ev) else " (est.)"), at=at_t(t_seco)))
    orbit_name = (((r.get("mission") or {}).get("orbit") or {}).get("name") or "Orbit")
    labels.append(dict(t=up[-1][3], k="orbit", text=orbit_name + " (planned)", at=up[-1][:3]))
    booster = []; land_out = None
    if land:
        t_l = ev.get("Stage 1 Landing") or (t_m + (310 if rtls else 340))
        ll = land.get("landing_location") or {}
        if rtls and ll.get("latitude") is not None:
            end = (float(ll["latitude"]), float(ll["longitude"]))
        else:
            end = _dest(lat, lon, az, float(land.get("downrange_distance") or 600))
        sep_ll = _dest(lat, lon, az, dr_m)
        over = _dest(lat, lon, az, dr_m + (18 if rtls else 25))
        nb = 28
        for i in range(nb + 1):
            u = i / nb; t = t_sep + (t_l - t_sep) * u
            if rtls:
                p = _lerp_ll(sep_ll, over, u / 0.25) if u < 0.25 else _lerp_ll(over, end, (u - 0.25) / 0.75)
                apo = 110.0
            else:
                p = _lerp_ll(sep_ll, end, 1 - (1 - u) ** 1.6); apo = 125.0
            alt = 68 + (apo - 68) * math.sin(math.pi * u / 0.6) if u < 0.3 else apo * (1 - ((u - 0.3) / 0.7) ** 1.6)
            booster.append([round(p[1], 4), round(p[0], 4), round(max(0.0, alt) * 1000), round(t, 1)])
        ok = land.get("success")
        where = ll.get("abbrev") or ll.get("name") or "landing site"
        kind = (land.get("type") or {}).get("abbrev") or ""
        res = "landed" if ok is True else "landing failed" if ok is False else "planned"
        land_out = dict(where=where, name=ll.get("name"), type=kind, success=ok, t=t_l, downrange_km=land.get("downrange_distance"))
        labels.append(dict(t=t_l, k="land" if ok is not False else "landfail",
                           text=f"Booster {'lands' if ok is None else res}: {where} ({'droneship' if kind == 'ASDS' else 'land zone' if kind == 'RTLS' else kind or 'site'}) " + _fmt_t(t_l),
                           at=booster[-1][:3]))
    fail = None
    if st in ("Failure", "Partial Failure"):
        fail = dict(status=st, reason=(r.get("failreason") or "").strip() or None)
        labels.append(dict(t=t_seco, k="fail", text=("Launch failure" if st == "Failure" else "Partial failure") + (": " + fail["reason"] if fail["reason"] else " (point of failure not published in LL2; marked at planned engine cutoff)"), at=at_t(t_seco)))
    labels.sort(key=lambda x: x["t"])
    return dict(azimuth=round(az, 1), inclination=round(inc, 2), ascent=up, booster=booster, landing=land_out, failure=fail, labels=labels,
                timeline_source="LL2 mission timeline" if ev else "generic profile (no LL2 timeline)")

def launches():
    j, mt, err = _raw()
    out = []
    for r in (j or {}).get("results") or []:
        try:
            pad = r.get("pad") or {}
            if pad.get("latitude") is None or pad.get("longitude") is None: continue
            cfg = ((r.get("rocket") or {}).get("configuration") or {})
            mis = r.get("mission") or {}
            m = model(r)
            out.append(dict(id=r.get("id"), name=r.get("name"), net=r.get("net"), net_precision=((r.get("net_precision") or {}).get("name")),
                            window_start=r.get("window_start"), window_end=r.get("window_end"),
                            status=(r.get("status") or {}).get("abbrev"), status_name=(r.get("status") or {}).get("name"),
                            vehicle=cfg.get("full_name") or cfg.get("name"), provider=((r.get("launch_service_provider") or {}).get("name")),
                            mission=mis.get("name"), orbit=((mis.get("orbit") or {}).get("abbrev")), orbit_name=((mis.get("orbit") or {}).get("name")),
                            pad=pad.get("name"), location=((pad.get("location") or {}).get("name")),
                            pad_lat=float(pad["latitude"]), pad_lon=float(pad["longitude"]),
                            webcast_live=bool(r.get("webcast_live")),
                            ll2_url="https://thespacedevs.com/llapi" if not r.get("slug") else f"https://ll.thespacedevs.com/2.3.0/launches/{r.get('id')}/",
                            **m))
        except Exception:
            continue
    return dict(launches=out, count=len(out), fetched=datetime.fromtimestamp(mt, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt else None,
                error=err, window_days=[PAST_DAYS, NEXT_DAYS],
                source="The Space Devs Launch Library 2", source_url="https://thespacedevs.com/llapi",
                modeled="Paths are modeled from pad, orbit type and the LL2 mission timeline; not telemetry.")

def launches_cached():
    hit = _MEM.get("b")
    if hit and time.time() - hit[0] < 120: return hit[1]
    b = json.dumps(launches(), separators=(",", ":")).encode()
    _MEM["b"] = (time.time(), b); return b
