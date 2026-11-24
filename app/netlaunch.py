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
PAST_DAYS = 14; NEXT_DAYS = 45   # one call, limit 100 (LL2 maximum page)
EARTH_R = 6371.0088
_L = threading.Lock(); _ST = {"err": None, "err_t": 0}; _MEM = {}

def _dir():
    d = os.path.join(os.environ.get("BN_STATE_DIR") or "/tmp", "bn_launch")
    os.makedirs(d, mode=0o700, exist_ok=True); return d

def _url(now):
    a = (now - timedelta(days=PAST_DAYS)).strftime("%Y-%m-%dT%H:00:00Z")
    b = (now + timedelta(days=NEXT_DAYS)).strftime("%Y-%m-%dT%H:00:00Z")
    return LL2 + "?" + urllib.parse.urlencode({"net__gte": a, "net__lte": b, "ordering": "net", "mode": "detailed", "limit": "100"})


def _fetch_ll2(timeout):
    req = urllib.request.Request(_url(datetime.now(timezone.utc)), headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: b = r.read()
    j = json.loads(b)
    if not isinstance(j.get("results"), list): raise ValueError("no results")
    return j, b

def _save(p, b):
    tmp = p + ".tmp"
    with open(tmp, "wb") as f: f.write(b)
    os.replace(tmp, p)

def _kick_bg(p):
    if _ST.get("bg"): return
    _ST["bg"] = True
    def run():
        try:
            j, b = _fetch_ll2(45)
            _save(p, b); _ST["err"] = None; _ST["err_t"] = 0; _MEM.pop("b", None)
        except Exception as e:
            _ST["err"] = getattr(e, "code", None) and f"HTTP {e.code}" or type(e).__name__
            _ST["err_t"] = time.time()
        finally:
            _ST["bg"] = False
    threading.Thread(target=run, daemon=True).start()

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
        cached = disk()
        wait = BACKOFF if cached else 15
        if time.time() - _ST["err_t"] < wait:
            if not cached: _kick_bg(p)
            return cached, mt, _ST["err"]
        try:
            j, b = _fetch_ll2(28)
            _save(p, b); _ST["err"] = None; _ST["err_t"] = 0
            return j, os.path.getmtime(p), None
        except Exception as e:
            _ST["err"] = getattr(e, "code", None) and f"HTTP {e.code}" or type(e).__name__; _ST["err_t"] = time.time()
            if not disk(): _kick_bg(p)
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
    payload = launches()
    b = json.dumps(payload, separators=(",", ":")).encode()
    if payload.get("count") or not payload.get("error"):
        _MEM["b"] = (time.time(), b)
    return b


# ---------- details sheet (pt1834u): every published LL2 field for one launch; images only with a commercial-use licence ----------
_OK_LIC = re.compile(r"^(public domain|cc0\b|cc[- ]by(-sa)?[- ]\d|nasa image and media guidelines|us government work)", re.I)

def image_ok(im):
    """LL2 image object -> dict for display, or None. Allowed: public domain, CC0, CC BY, CC BY-SA, NASA media guidelines.
    Refused: any NC or ND licence, 'Unknown', agency-specific policies (SpaceX CC BY-NC, ESA Standard Licence, Roscosmos)."""
    if not isinstance(im, dict) or not im.get("image_url"): return None
    lic = (im.get("license") or {}); name = (lic.get("name") or "").strip()
    if not name or re.search(r"\bNC\b|\bND\b|non-?commercial|unknown", name, re.I) or not _OK_LIC.search(name): return None
    return dict(url=im.get("thumbnail_url") or im["image_url"], full=im["image_url"], credit=im.get("credit") or "", license=name, license_url=lic.get("link"))

def _n(v):
    return v if v not in (None, "", []) else None

# ---------- one licensed photo per rocket type (follow-up to pt1834u): files in netmap_static/rockets/, credits in rockets.json ----------
# Sources: Wikimedia Commons only, licence public domain / CC0 / CC BY / CC BY-SA (never NC/ND). Rockets with no usable photo show none.
_ROCKET_KEYS = [  # (regex on vehicle full name + families, key) - first match wins
    (r"falcon heavy", "falconheavy"), (r"falcon 9|falcon9", "falcon9"), (r"starship|super heavy", "starship"),
    (r"\bhaste\b", "haste"), (r"electron", "electron"), (r"vulcan", "vulcan"), (r"atlas v|atlas 5", "atlasv"),
    (r"new glenn", "newglenn"), (r"long march 5|\bcz-5", "lm5"), (r"long march 7|\bcz-7", "lm7"),
    (r"long march|changzheng|\bcz-", "longmarch"), (r"soyuz[- ]?2", "soyuz2"), (r"soyuz", "soyuz"), (r"minotaur", "minotaur"),
    (r"space launch system|\bsls\b", "sls"), (r"firefly alpha|^alpha\b", "firefly"), (r"proton", "proton"), (r"h-iia|h-2a", "h2a"),
    (r"gslv", "gslv"), (r"angara", "angara"),
    (r"antares", "antares"), (r"\bvega\b", "vega"), (r"epsilon", "epsilon"), (r"\bh3\b|\bh-3\b|\bh-iii\b", "h3"), (r"\bpslv\b", "pslv"), (r"\bnuri\b|kslv-ii", "nuri"),
]
_ROCKETS = None
def _rockets():
    global _ROCKETS
    if _ROCKETS is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "netmap_static", "rockets", "rockets.json")) as fh: _ROCKETS = json.load(fh)
        except Exception: _ROCKETS = {}
    return _ROCKETS

def rocket_photo(*names):
    hay = " | ".join(n for n in names if n).lower()
    for rx, key in _ROCKET_KEYS:
        if re.search(rx, hay):
            m = _rockets().get(key)
            if not m or not _OK_LIC.match(m.get("license") or ""): return None
            return dict(key=key, url=f"/api/netmap/rockets/{m['file']}", pictured=m.get("pictured"), author=m.get("author"),
                        license=m.get("license"), license_url=m.get("license_url"), source_url=m.get("source_url"), w=m.get("w"), h=m.get("h"))
    return None

def details(r):
    cfg = ((r.get("rocket") or {}).get("configuration") or {}); mis = r.get("mission") or {}; pad = r.get("pad") or {}
    lsp = r.get("launch_service_provider") or {}; st = r.get("status") or {}
    boosters = []
    for s in (r.get("rocket") or {}).get("launcher_stage") or []:
        L = s.get("launcher") or {}; ld = s.get("landing") or {}; ll = ld.get("landing_location") or {}
        boosters.append(dict(type=s.get("type"), serial=_n(L.get("serial_number")), flight_number=s.get("launcher_flight_number"), flights_total=L.get("flights"),
                             reused=s.get("reused"), previous_flight=_n(s.get("previous_flight_date")), turnaround=_n(s.get("turn_around_time")),
                             first_launch=_n(L.get("first_launch_date")), status=((L.get("status") or {}).get("name")),
                             landings=dict(attempted=L.get("attempted_landings"), successful=L.get("successful_landings")),
                             landing=dict(attempt=ld.get("attempt"), success=ld.get("success"), description=_n(ld.get("description")),
                                          location=_n(ll.get("name")), abbrev=_n(ll.get("abbrev")), type=((ld.get("type") or {}).get("name")),
                                          downrange_km=ld.get("downrange_distance")) if ld else None))
    sc = []
    for s in [(r.get("rocket") or {}).get("spacecraft_stage")] if isinstance((r.get("rocket") or {}).get("spacecraft_stage"), dict) else ((r.get("rocket") or {}).get("spacecraft_stage") or []):
        if not s: continue
        c = s.get("spacecraft") or {}
        sc.append(dict(name=_n(c.get("name")), serial=_n(c.get("serial_number")), destination=_n(s.get("destination")), flights=((c.get("spacecraft_config") or {}).get("name"))))
    vids = [dict(url=v.get("url"), title=v.get("title") or v.get("publisher") or "Webcast", publisher=v.get("publisher"), live=v.get("live"))
            for v in (r.get("vid_urls") or []) if v.get("url", "").startswith("https://")][:4]
    infos = [dict(url=v.get("url"), title=v.get("title") or v.get("source") or "Info") for v in (r.get("info_urls") or []) if str(v.get("url", "")).startswith("https://")][:4]
    patches = [dict(name=p.get("name"), agency=((p.get("agency") or {}).get("name"))) for p in (r.get("mission_patches") or [])]
    cost = cfg.get("launch_cost")
    try: cost = int(float(cost)) if cost not in (None, "") else None
    except Exception: cost = None
    img = image_ok(r.get("image")) or image_ok(cfg.get("image"))
    photo = rocket_photo(cfg.get("full_name") or cfg.get("name"), cfg.get("name"), *[f.get("name") for f in (cfg.get("families") or []) if isinstance(f, dict)])
    return dict(id=r.get("id"), name=r.get("name"),
        mission=dict(name=_n(mis.get("name")), type=_n(mis.get("type")), description=_n(mis.get("description")),
                     orbit=_n(((mis.get("orbit") or {}).get("name"))),
                     agencies=[dict(name=a.get("name"), type=((a.get("type") or {}).get("name"))) for a in (mis.get("agencies") or [])]),
        status=dict(name=st.get("name"), abbrev=st.get("abbrev"), description=_n(st.get("description"))), failreason=_n(r.get("failreason")),
        net=r.get("net"), net_precision=((r.get("net_precision") or {}).get("name")), window_start=r.get("window_start"), window_end=r.get("window_end"),
        probability=r.get("probability"), weather_concerns=_n(r.get("weather_concerns")),
        provider=dict(name=_n(lsp.get("name")), type=((lsp.get("type") or {}).get("name")), country=", ".join(c.get("name", "") for c in (lsp.get("country") or []) if isinstance(c, dict)) or None),
        rocket=dict(name=_n(cfg.get("full_name") or cfg.get("name")), families=[f.get("name") for f in (cfg.get("families") or []) if isinstance(f, dict)] or None,
                    variant=_n(cfg.get("variant")), manufacturer=_n(((cfg.get("manufacturer") or {}).get("name"))),
                    launch_cost_usd=cost, length_m=cfg.get("length"), diameter_m=cfg.get("diameter"), launch_mass_t=cfg.get("launch_mass"),
                    leo_capacity_kg=cfg.get("leo_capacity"), gto_capacity_kg=cfg.get("gto_capacity"), liftoff_thrust_kn=cfg.get("to_thrust"),
                    maiden_flight=_n(cfg.get("maiden_flight")), total_launches=cfg.get("total_launch_count"), successful_launches=cfg.get("successful_launches"),
                    failed_launches=cfg.get("failed_launches"), reusable=cfg.get("reusable"), wiki_url=_n(cfg.get("wiki_url"))),
        pad=dict(name=_n(pad.get("name")), location=_n(((pad.get("location") or {}).get("name"))), lat=pad.get("latitude"), lon=pad.get("longitude"),
                 map_url=_n(pad.get("map_url")), launches_from_pad=pad.get("total_launch_count")),
        boosters=boosters, spacecraft=sc, webcasts=vids, info=infos, patches=patches, flightclub_url=_n(r.get("flightclub_url")),
        counts=dict(orbital_attempt=r.get("orbital_launch_attempt_count"), orbital_attempt_year=r.get("orbital_launch_attempt_count_year"),
                    pad_attempt=r.get("pad_launch_attempt_count"), agency_attempt=r.get("agency_launch_attempt_count")),
        rocket_photo=photo,
        image=img, image_note=None if img else "No image with a commercial-use licence in Launch Library 2 for this launch.",
        source="The Space Devs Launch Library 2", source_url="https://thespacedevs.com/llapi")

def detail(lid):
    j, mt, err = _raw()
    for r in (j or {}).get("results") or []:
        if str(r.get("id")) == str(lid): return details(r)
    return None
