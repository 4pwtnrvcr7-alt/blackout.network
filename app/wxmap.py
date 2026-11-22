"""/weather: full-screen Weather map (Matt pt1742u, Nov 22 2026). Same map stack and design language as /grid and /map
(MapLibre GL + OpenFreeMap). Replaces the menu link to the old /live#weather dashboard tab (that tab and /api/weather stay as they were;
the location card on this page reuses /api/weather and /api/weather/geocode).

Free, keyless public sources only. Radar and model tiles load straight from the providers in the browser as map-native raster layers;
this module only builds frame lists and re-serves small, cached JSON so visitors never each hit an upstream:
  - Past radar (U.S.): NOAA MRMS mosaic via the Iowa Environmental Mesonet (IEM) archive (NEXRAD composite as the fallback).
  - Forecast radar (U.S.): NOAA HRRR simulated reflectivity with precip type, via IEM tiles (hrrr::REFP), latest run + latest 48-hour run.
  - Worldwide, past (Nov 22 pt1744u): geostationary infrared clouds (NASA GIBS: GOES-East, GOES-West, Himawari; EUMETSAT EUMETView:
    Meteosat 0 degrees and Indian Ocean, hourly "Core" images, CC BY 4.0) and NASA IMERG satellite rainfall (GIBS, public domain).
  - Worldwide, forecast: NOAA GFS 1-degree rain rate and cloud cover from NOMADS, every 3 hours to 7 days (wxgfs.py).
  - Temperature / rain / snow: Open-Meteo forecast API on a 1.5-degree grid over the lower 48 (past 24 h + 7 days, 3-hourly), one
    pull every 6 hours, drawn in the browser.
  - Warnings and watches: NWS api.weather.gov active alerts (storm-based polygons, plus forecast-zone / county shapes, cached).
  - Storm reports (72 h): NWS Local Storm Reports via IEM. Tornado tracks (90 days): NWS Damage Assessment Toolkit.
  - Severe outlook: NOAA SPC Day 1-3 categorical outlooks. Hurricanes: NHC active storms (cone, track) + IBTrACS season tracks (NOAA NCEI).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json, blackout.db, the newsletter or geo code.
Routes: /weather (page), /api/wxmap/frames|grid|gfs|alerts|storms|tropical|global, /api/wxmap/<static file>."""
import os, io, csv, json, re, time, threading, urllib.parse, urllib.request, html as _html
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import wxgfs

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "wxmap_static")
FILES = {"wx.js": "application/javascript", "wx.css": "text/css", "wxw.js": "application/javascript"}
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
UA = "Mozilla/5.0 (compatible; blackout.network weather map; +https://blackout.network/weather)"
IEM_TILE = "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/{layer}/{z}/{x}/{y}.png"

_C = {}
_L = threading.Lock()
_BUSY = {}

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def _v(name):
    try: return str(int(os.path.getmtime(os.path.join(STATIC, name))))
    except OSError: return "0"

def get(url, accept="application/json", timeout=15, limit=20_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit)

def jget(url, **kw): return json.loads(get(url, **kw).decode("utf-8", "replace"))

def cached(key, ttl, fn, stale_ok=True):
    """Value cached for ttl seconds. One refresh at a time per key; while one runs (or if it fails) others get the last good value."""
    with _L:
        hit = _C.get(key)
        if hit and time.time() - hit[0] < ttl: return hit[1]
        if hit and _BUSY.get(key) and stale_ok: return hit[1]
        _BUSY[key] = True
    try:
        val = fn()
        with _L: _C[key] = (time.time(), val)
        return val
    except Exception:
        if hit and stale_ok: return hit[1]
        raise
    finally:
        with _L: _BUSY[key] = False

def why(ex):
    if isinstance(ex, urllib.error.HTTPError): return f"the source answered HTTP {ex.code}"
    if isinstance(ex, (TimeoutError,)) or "timed out" in str(ex): return "the source did not answer in time"
    return "the source could not be reached just now"

# ---------------------------------------------------------------- radar frames
# Timeline: the last 12 hours (every 30 minutes, then every 10 minutes for the last 6 hours), then the forecast out to 7 days.
PAST_H, PAST_STEP = 6, 10          # recent past: 6 hours at 10-minute steps
OLD_H, OLD_STEP = 6, 30            # before that: 6 more hours at 30-minute steps (NASA IMERG rain arrives ~4-6 h late)

def _floor5(d): return d.replace(minute=d.minute - d.minute % 5, second=0, microsecond=0)
def _pt(s): return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

def _hrrr_init(fname):
    d = jget(f"https://mesonet.agron.iastate.edu/data/gis/images/4326/hrrr/{fname}", timeout=10)
    return datetime.strptime(d["model_init_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

# Worldwide past layers (free, no key, fine for a public site):
#  - NASA GIBS (public domain): geostationary infrared clouds every 10 minutes (GOES-East, GOES-West, Himawari) and
#    NASA IMERG satellite rainfall every 30 minutes;
#  - EUMETSAT EUMETView (Meteosat hourly images are EUMETSAT "Core" data, CC BY 4.0): Meteosat 0 degrees and Indian Ocean.
GIBS_DOM = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/{layer}/default/GoogleMapsCompatible_Level6/all/{a}--{b}.xml"
SATS = {"ge": "GOES-East_ABI_Band13_Clean_Infrared", "gw": "GOES-West_ABI_Band13_Clean_Infrared", "hi": "Himawari_AHI_Band13_Clean_Infrared"}
IMERG = "IMERG_Precipitation_Rate_30min"
EUM = {"ms": "msg_fes/ir108", "io": "msg_iodc/ir108"}

def _gibs_times(layer, a, b):
    """Available times for one GIBS layer between a and b (DescribeDomains), as a sorted list of datetimes."""
    x = get(GIBS_DOM.format(layer=layer, a=iso(a), b=iso(b)), accept="text/xml", timeout=12).decode("utf-8", "replace")
    m = re.search(r"<Domain>([^<]*)</Domain>", x)
    out = set()
    for part in (m.group(1).split(",") if m else []):
        bits = part.split("/")
        if len(bits) == 3:
            s_, e_, per = bits
            if len(s_) == 10: s_ += "T00:00:00Z"
            mm = re.match(r"PT(\d+)M", per); step = timedelta(minutes=int(mm.group(1)) if mm else 10)
            t, e2 = _pt(s_), _pt(e_)
            if t < a: t = t + ((a - t) // step) * step
            while t <= e2 and len(out) < 2000:
                if t >= a: out.add(t)
                t += step
        elif len(bits) == 1 and len(part) >= 19: out.add(_pt(part))
    return sorted(out)

def _eum_latest(layer):
    x = get(f"https://view.eumetsat.int/geoserver/{layer}/ows?service=WMS&version=1.3.0&request=GetCapabilities", accept="text/xml", timeout=12).decode("utf-8", "replace")
    m = re.search(r'<Dimension name="time"[^>]*>[^<]*?/([0-9T:\-.]+Z)/PT', x)
    if not m: raise ValueError("no time dimension")
    return _pt(m.group(1))

_SAT_OK = set()  # (sector, time) infrared images whose tiles have answered once
SATP = {"ge": "0/0", "gw": "0/0", "hi": "0/1"}   # one zoom-1 tile (row/col) inside each satellite disc
_IM_OK = set()   # IMERG half-hours whose tiles have answered once (probed only once each)

def satellite(a, b):
    """{"ge": [times], ..., "im": [times], "ms": latest, "io": latest, "status": {key: reason or None}} for the window a..b."""
    def go():
        out, st = {}, {}
        for k, layer in list(SATS.items()) + [("im", IMERG)]:
            try: out[k] = _gibs_times(layer, a - timedelta(hours=1), b); st[k] = None if out[k] else "no images in this window"
            except Exception as ex: out[k] = []; st[k] = why(ex)
        # GIBS sometimes lists an IMERG half-hour whose tiles are not there (yet): keep only times whose tiles answer
        def ok(t):
            if t in _IM_OK: return t
            try: get(f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{IMERG}/default/{iso(t)}/GoogleMapsCompatible_Level6/3/4/3.png", accept="image/png", timeout=8)
            except Exception: return None
            if len(_IM_OK) > 500: _IM_OK.clear()
            _IM_OK.add(t); return t
        if out.get("im"):
            with ThreadPoolExecutor(max_workers=6) as ex: out["im"] = [t for t in ex.map(ok, out["im"]) if t]
        # the newest infrared images can be listed 30-60 minutes before their tiles exist (Himawari most of all): probe the last 2 hours once each
        def sok(kt):
            k, t = kt
            if (k, t) in _SAT_OK: return True
            try: get(f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{SATS[k]}/default/{iso(t)}/GoogleMapsCompatible_Level6/1/{SATP[k]}.png", accept="image/png", timeout=8)
            except Exception: return False
            if len(_SAT_OK) > 1500: _SAT_OK.clear()
            _SAT_OK.add((k, t)); return True
        edge = now() - timedelta(hours=2)
        todo = [(k, t) for k in SATS for t in (out.get(k) or []) if t >= edge]
        if todo:
            with ThreadPoolExecutor(max_workers=8) as ex: bad = {kt for kt, good in zip(todo, ex.map(sok, todo)) if not good}
            for k in SATS: out[k] = [t for t in (out.get(k) or []) if (k, t) not in bad]
        for k, layer in EUM.items():
            try: out[k] = _eum_latest(layer); st[k] = None
            except Exception as ex: out[k] = None; st[k] = why(ex)
        out["status"] = st
        return out
    return cached(("sat", a.strftime("%Y%m%d%H"), b.strftime("%Y%m%d%H%M")[:11]), 240, go)

def _pick(ts, t, max_age):
    """Newest time in sorted list ts that is <= t and no older than max_age."""
    best = None
    for x in ts:
        if x <= t: best = x
        else: break
    return best if best is not None and t - best <= max_age else None

def frames():
    def go():
        out = {"generated": iso(now()), "past": [], "forecast": [], "sources": {}}
        # past: MRMS SeamlessHSR (NOAA's quality-controlled radar mosaic; 2-minute archive at IEM), else the raw NEXRAD composite
        def times_back(latest):
            ts = []
            n = PAST_H * 60 // PAST_STEP
            old0 = latest - timedelta(hours=PAST_H)
            old0 = old0.replace(minute=old0.minute - old0.minute % OLD_STEP, second=0, microsecond=0)
            recent0 = latest - timedelta(minutes=PAST_STEP * n); recent0 = recent0.replace(minute=recent0.minute - recent0.minute % PAST_STEP)
            for k in range(OLD_H * 60 // OLD_STEP, -1, -1):
                d = old0 - timedelta(minutes=OLD_STEP * k)
                if d < recent0: ts.append(d)
            for i in range(n, -1, -1):
                d = latest - timedelta(minutes=PAST_STEP * i)
                if i: d = d.replace(minute=d.minute - d.minute % PAST_STEP)
                ts.append(d)
            return sorted(set(ts))
        latest = None
        try:
            m = jget("https://mesonet.agron.iastate.edu/data/gis/images/4326/mrms/lcref.json", timeout=10)
            latest = datetime.strptime(m["meta"]["end_valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            latest = latest.replace(minute=latest.minute - latest.minute % 2, second=0, microsecond=0)
            for d in times_back(latest): out["past"].append({"t": iso(d), "layer": "mrms::lcref-" + d.strftime("%Y%m%d%H%M")})
            out["sources"]["past"] = {"ok": True, "label": "NOAA MRMS radar mosaic (IEM archive)", "latest": iso(latest)}
        except Exception as ex1:
            try:
                t = jget("https://mesonet.agron.iastate.edu/json/tms.json", timeout=10)
                lay = next((s for s in t.get("services", []) if s.get("id") == "ridge_uscomp_n0q"), None)
                latest = _floor5(datetime.strptime(lay["utc_valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
                for d in times_back(latest): out["past"].append({"t": iso(d), "layer": "ridge::USCOMP-N0Q-" + d.strftime("%Y%m%d%H%M")})
                out["sources"]["past"] = {"ok": True, "label": "NWS NEXRAD composite (IEM archive)", "latest": iso(latest)}
            except Exception as ex:
                out["sources"]["past"] = {"ok": False, "label": "NOAA MRMS / NWS NEXRAD radar (IEM archive)", "reason": "Past U.S. radar is unavailable: " + why(ex)}
        if not out["past"]:   # the U.S. radar is down: keep the worldwide satellite timeline anyway
            latest = now() - timedelta(minutes=20); latest = latest.replace(minute=latest.minute - latest.minute % 10, second=0, microsecond=0)
            for d in times_back(latest): out["past"].append({"t": iso(d), "layer": None})
        # worldwide past: infrared clouds + IMERG rain, matched to each past frame
        a, b = _pt(out["past"][0]["t"]), _pt(out["past"][-1]["t"])
        try:
            sat = satellite(a, b)
        except Exception as ex:
            sat = {"status": {k: why(ex) for k in ("ge", "gw", "hi", "im", "ms", "io")}}
        ripe = now() - timedelta(minutes=35)   # GIBS lists a new image before all of its tiles exist: skip the last ~35 minutes
        for k in SATS: sat[k] = [x for x in (sat.get(k) or []) if x <= ripe]
        for f in out["past"]:
            t = _pt(f["t"]); s_ = {}
            t30 = t if f is out["past"][-1] else t.replace(minute=t.minute - t.minute % 30, second=0, microsecond=0)   # infrared every 30 minutes: clouds move slowly, and it is a third of the downloads
            for k in SATS:
                x = _pick(sat.get(k) or [], t30, timedelta(minutes=40)) or _pick(sat.get(k) or [], t, timedelta(minutes=60))
                if x: s_[k] = iso(x)
            for k in EUM:
                L = sat.get(k)
                if L:
                    h = min(t, L).replace(minute=0, second=0, microsecond=0)   # hourly images only (the CC BY 4.0 "Core" set)
                    if t - h <= timedelta(minutes=90): s_[k] = iso(h)
            f["sat"] = s_
            x = _pick(sat.get("im") or [], t, timedelta(minutes=30))
            if x: f["im"] = iso(x)
        st = sat.get("status", {})
        im_ts = sat.get("im") or []
        out["sources"]["sat"] = {"ok": any(st.get(k) is None for k in ("ge", "gw", "hi", "ms", "io")), "label": "Satellite clouds (NASA GIBS, EUMETSAT)",
                                 "down": {k: v for k, v in st.items() if v and k != "im"},
                                 "reason": None if any(st.get(k) is None for k in ("ge", "gw", "hi", "ms", "io")) else "Satellite images are unavailable: " + (st.get("ge") or "no images")}
        out["sources"]["imerg"] = {"ok": bool(im_ts), "label": "NASA IMERG satellite rainfall", "latest": iso(im_ts[-1]) if im_ts else None,
                                   "reason": None if im_ts else "NASA IMERG is unavailable: " + (st.get("im") or "no images in the last 12 hours")}
        # forecast: HRRR reflectivity with precip type. Latest hourly run (18 h), then the latest synoptic run out to 48 h.
        try:
            t0 = now()
            ini = _hrrr_init("refp_0000.json")
            try: ext = _hrrr_init("refp_2880.json")
            except Exception: ext = None
            start = (t0 + timedelta(minutes=59)).replace(minute=0, second=0, microsecond=0)
            end1 = ini + timedelta(hours=18)
            end2 = ext + timedelta(hours=48) if ext else end1
            d = start
            while d <= max(end1, end2):
                run = ini if d <= end1 else ext
                fm = int((d - run).total_seconds() // 60)
                if fm >= 0 and (d <= start + timedelta(hours=18) or d.hour % 3 == 0):   # hourly for 18 h, then every 3 h (fewer frames to preload)
                    out["forecast"].append({"t": iso(d), "layer": f"hrrr::REFP-F{fm:04d}-{run.strftime('%Y%m%d%H%M')}", "run": iso(run)})
                d += timedelta(hours=1)
            out["sources"]["forecast"] = {"ok": bool(out["forecast"]), "label": "NOAA HRRR model radar forecast (IEM)", "run": iso(ini), "long_run": iso(ext) if ext else None,
                                          "reason": None if out["forecast"] else "No HRRR forecast frames are published right now"}
        except Exception as ex:
            out["sources"]["forecast"] = {"ok": False, "label": "NOAA HRRR model radar forecast (IEM)", "reason": "U.S. radar forecast is unavailable: " + why(ex)}
        # worldwide forecast: GFS rain and cloud cover every 3 hours to 7 days (built in the background, see wxgfs.py)
        gm, gerr = wxgfs.meta()
        if gm:
            out["gfs"] = {k: gm[k] for k in ("run", "times", "p", "c", "rate", "generated")}
            out["sources"]["gfs"] = {"ok": True, "label": "NOAA GFS model (rain and clouds)", "run": gm["run"]}
        else:
            out["gfs"] = None
            out["sources"]["gfs"] = {"ok": False, "label": "NOAA GFS model (rain and clouds)", "reason": ("Worldwide forecast is unavailable: " + gerr) if gerr else "The worldwide forecast is still loading"}
        out["tile"] = IEM_TILE
        return out
    return cached(("frames",), 180, go)

# ---------------------------------------------------------------- model grid (temperature / rain / snow)
OM = "https://api.open-meteo.com/v1/forecast"
# Two grids. "us": 1.5 degrees over the lower 48 (779 points, every 8 h). "world": 4 degrees worldwide, only points that touch land
# (1,732 points, every 12 h; oceans are masked on the map anyway). Open-Meteo free tier: 10,000 location-calls a day, 600 a minute,
# so the pulls go out in chunks of <= 300 points spaced 40 s apart, US first. A restart costs about 2,500 calls.
GRIDS = {
    "us":    {"lat0": 23.0, "lon0": -126.0, "step": 1.5, "ny": 19, "nx": 41, "ttl": 8 * 3600, "wrap": False, "mask": None},
    "world": {"lat0": -56.0, "lon0": -180.0, "step": 4.0, "ny": 34, "nx": 90, "ttl": 12 * 3600, "wrap": True,
              "mask": "AAAAPx8AAAGAAAAAAAAPxwAAAOAAAMwAAAPwAAAAMAAAOwAAAPgAAAAAAAPPwAAAPwAAAAAAAfHgAAA/8AAfAAAf/jAAAA/8AA/gAAf/jAAAAH+AA/8AAf/gBhgAH/AA//gAf/+x/gAP/gZ//gAf/f8eAAf/gZ/+AAP/P8DAAf/wZ/+AA//9ADAA//wB//AD//8AAAD//wB/7AH//wBgAD//gD/8AP//jBgAD/8B//+Dv/wDAAAB/8D//+Hv/wAAAAP/wH///Hv/AABwB//gP///n//AABwB//gP/////+AABwD/+AD//////gAAAH/8AD//////gAAAP/8AD//////8AAAf/8Af//////8AAAf//Ac//////+AAAf//4A///////AwA///4A///////x/h///4A////////v/////A/////////////vHf/////////////////////////////x///////3//////w///////AAf////B/H////AA="},
}
CHUNK, CHUNK_GAP = 300, 40
_OM_LOCK = threading.Lock()   # one Open-Meteo pull at a time, so the two grids never burst together
# Nov 22 2026 (pt1745u): deploys used to refill both grids from scratch and ran Open-Meteo's daily quota out (HTTP 429, Temp/Rain/Snow greyed).
# Now: the grids are refreshed less often (US 12 h, world 18 h) and only within om_budget's share; a 429 backs off (Retry-After, else the
# reason's hour/day); a half-done refresh resumes where it stopped; the last good grid is saved to disk and handed to the next deploy
# (a new instance asks the still-running old one over the public URL before it calls Open-Meteo at all); and while there is no
# Open-Meteo grid, Temp/Rain/Snow are drawn from the NOAA GFS run the map already downloads.
import gzip, tempfile, om_budget as OMB
GRIDS["us"]["ttl"], GRIDS["world"]["ttl"] = 12 * 3600, 18 * 3600
MAX_AGE = 40 * 3600          # older than this, a GFS-based grid (if there is one) is better than the old Open-Meteo one
PEER_WAIT = 480              # seconds a fresh instance waits for the old one's grids before it would call Open-Meteo itself
BOOT = time.time()
PEER = (os.environ.get("BN_HANDOFF_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
if os.environ.get("BN_WX_PEER", "1") == "0": PEER = ""
def _pdir():
    for d in (os.environ.get("BN_PERSIST_DIR"), "/var/data"):
        if d and os.path.isdir(d) and os.access(d, os.W_OK): return os.path.join(d, "bn_wxcache")
    return os.path.join(tempfile.gettempdir(), "bn_wxcache")
PDIR = _pdir()
_PEER_ST = {"state": "off" if not PEER else "pending", "got": []}
_PART = {}                   # region -> {"day": UTC date, "res": [...]} of a refresh that stopped early
_GERR = {}

def _gts(g):
    try: return datetime.strptime(g["generated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return 0.0

def _save(name, obj):
    try:
        os.makedirs(PDIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=PDIR, prefix=".w_")
        with os.fdopen(fd, "wb") as f: f.write(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), 5))
        os.replace(tmp, os.path.join(PDIR, name))
    except Exception: pass

def _load(name):
    try:
        with open(os.path.join(PDIR, name), "rb") as f: return json.loads(gzip.decompress(f.read()))
    except Exception: return None

def _put_grid(region, g, persist=True):
    with _L:
        cur = _C.get(("grid", region))
        if cur and _gts(cur[1]) >= _gts(g) and not cur[1].get("fallback"): return False
        _C[("grid", region)] = (_gts(g) or time.time(), g)
    if persist: _save(f"grid_{region}.json.gz", g); _save("om_state.json.gz", OMB.state())
    return True

def _restore():
    """At import: the grids and the Open-Meteo budget this disk already has (same instance restarting, or a persistent disk)."""
    st = _load("om_state.json.gz")
    if st: OMB.adopt(st)
    for r in GRIDS:
        g = _load(f"grid_{r}.json.gz")
        if g and g.get("temp") and not g.get("fallback"): _put_grid(r, g, persist=False)
_restore()

def _cells(g):
    n = g["nx"] * g["ny"]
    if not g["mask"]: return list(range(n))
    import base64
    bits = base64.b64decode(g["mask"])
    return [k for k in range(n) if bits[k >> 3] >> (7 - (k & 7)) & 1]

def _pull(pts):
    q = {"latitude": ",".join(str(a) for a, _ in pts), "longitude": ",".join(str(b) for _, b in pts),
         "hourly": "temperature_2m,precipitation,snowfall", "past_days": 1, "forecast_days": 7, "timezone": "GMT", "temporal_resolution": "hourly_3"}
    u = OM + "?" + urllib.parse.urlencode(q, safe=",")
    OMB.note(len(pts), "grid")
    try: d = jget(u, timeout=60)
    except urllib.error.HTTPError as ex:
        if ex.code == 429: OMB.on_429(ex)
        raise
    except Exception:
        time.sleep(3); d = jget(u, timeout=60)   # one retry: the upstream occasionally drops a TLS handshake
    return d if isinstance(d, list) else [d]

class Limited(Exception): pass

def _refresh(region):
    g = GRIDS[region]
    wait = BOOT + PEER_WAIT - time.time()
    if PEER and _PEER_ST["state"] == "pending" and wait > 0: time.sleep(wait)   # the old instance may still hand its grid over
    cur = grid_peek(region)
    if cur and not cur.get("fallback") and time.time() - _gts(cur) < g["ttl"]: return cur
    cells = _cells(g)
    pts = [(round(g["lat0"] + g["step"] * (k // g["nx"]), 2), round(((g["lon0"] + g["step"] * (k % g["nx"]) + 180) % 360) - 180, 2)) for k in cells]
    day = now().strftime("%Y-%m-%d")
    part = _PART.get(region)
    res = list(part["res"]) if part and part["day"] == day else []
    with _OM_LOCK:
        c = len(res)
        while c < len(pts):
            chunk = pts[c:c + CHUNK]
            w = OMB.wait_s(len(chunk), "grid")
            if w > 600:
                _PART[region] = {"day": day, "res": res}
                lim, why_, until = OMB.limited()
                raise Limited(("Open-Meteo is rate-limited" if lim else "the Open-Meteo share for the map is used up") + ", next try " + _et(time.time() + w))
            if w > 0: time.sleep(w)
            try: res += _pull(chunk)
            except Exception:
                _PART[region] = {"day": day, "res": res}; raise
            c += len(chunk)
            if c < len(pts): time.sleep(CHUNK_GAP)
    _PART.pop(region, None)
    if len(res) != len(pts): raise ValueError("grid size mismatch")
    times = res[0]["hourly"]["time"]
    if any(r_["hourly"]["time"] != times for r_ in res): raise ValueError("grid chunks disagree on times")
    T, P, S = [], [], []
    for k in range(len(times)):
        for r in res:
            h = r["hourly"]
            t, p, s_ = h["temperature_2m"][k], h["precipitation"][k], h["snowfall"][k]
            T.append(None if t is None else round(t * 9 / 5 + 32))
            P.append(None if p is None else round(p * 10))
            S.append(None if s_ is None else round(s_ * 10))
    out = {"generated": iso(now()), "region": region, "lat0": g["lat0"], "lon0": g["lon0"], "step": g["step"], "ny": g["ny"], "nx": g["nx"], "wrap": g["wrap"],
           "cells": cells if g["mask"] else None, "times": [x + ":00Z" for x in times], "step_h": 3, "temp": T, "precip": P, "snow": S,
           "units": {"temp": "F", "precip": "0.1 mm per 3 h", "snow": "0.1 cm per 3 h"},
           "source": f"Open-Meteo forecast API (national weather models), {g['step']:g}-degree grid"}
    _put_grid(region, out)
    return out

def _et(ts):
    d = datetime.fromtimestamp(ts, timezone.utc) - timedelta(hours=5)   # the page and the owner use Eastern time (UTC-5 in winter)
    return d.strftime("%-I:%M %p ET")

def grid(region="us"):
    """Refresh now if stale (blocking; background threads only). Returns the grid."""
    g = GRIDS.get(region) or GRIDS["us"]
    try:
        out = _refresh(region if region in GRIDS else "us")
        _GERR.pop(region, None); return out
    except Exception as ex:
        _GERR[region] = (time.time(), str(ex) if isinstance(ex, Limited) else why(ex))
        with _L: _C[("griderr", region)] = _GERR[region]
        raise

def _gfs_grid(region):
    """Temp/Rain/Snow from NOAA GFS in the grid format, cached per GFS run (fallback while there is no Open-Meteo grid)."""
    g = GRIDS[region]; m, _ = wxgfs.meta()
    if not m: return None
    key = ("gfsgrid", region, m.get("run"))
    with _L:
        hit = _C.get(key)
    if hit: return hit[1]
    cells = _cells(g)
    d = wxgfs.grid_like(g, cells, region)
    if not d: return None
    out = {"generated": m.get("generated") or iso(now()), "region": region, "lat0": g["lat0"], "lon0": g["lon0"], "step": g["step"], "ny": g["ny"], "nx": g["nx"], "wrap": g["wrap"],
           "cells": cells if g["mask"] else None, "times": d["times"], "step_h": 3, "temp": d["temp"], "precip": d["precip"], "snow": d["snow"],
           "units": {"temp": "F", "precip": "0.1 mm per 3 h", "snow": "0.1 cm per 3 h"}, "fallback": "gfs",
           "source": "NOAA GFS 1-degree forecast (used while Open-Meteo is unavailable)"}
    with _L:
        for k in [k for k in _C if k[0] == "gfsgrid" and k[1] == region]: _C.pop(k, None)
        _C[key] = (time.time(), out)
    return out

def grid_bytes(region):
    """Compact JSON for the page: the best grid there is, with an 'as of' note when it is old or a fallback."""
    g = grid_nowait(region)
    if g is None: return None
    lim, why_, until = OMB.limited()
    age = time.time() - _gts(g)
    note = None
    if g.get("fallback"): note = "From NOAA GFS while Open-Meteo is " + ("rate-limited" if lim else "unavailable") + "; next 7 days, every 3 hours"
    elif age > GRIDS[region]["ttl"] or lim: note = "Last good grid, as of " + _et(_gts(g)) + ("; Open-Meteo is rate-limited" if lim else "")
    key = ("gridb", region, g["generated"], g.get("fallback"), note)
    with _L:
        hit = _C.get(key)
    if hit: return hit[1]
    b = json.dumps(dict(g, as_of=g["generated"], note=note, label=("NOAA GFS 1°" if g.get("fallback") else f"Open-Meteo {g['step']:g}°")), separators=(",", ":")).encode()
    with _L:
        for k in [k for k in _C if k[0] == "gridb" and k[1] == region]: _C.pop(k, None)
        _C[key] = (time.time(), b)
    return b

_GRID_BG = {}
def grid_nowait(region):
    """Never blocks a request on Open-Meteo: returns the best grid on hand (Open-Meteo, possibly old; else GFS) and refreshes in the background."""
    g = GRIDS.get(region) or GRIDS["us"]
    with _L:
        hit = _C.get(("grid", region))
        fresh = hit and time.time() - hit[0] < g["ttl"]
        th = _GRID_BG.get(region)
        err = _GERR.get(region)
        retry_ok = not err or time.time() - err[0] > 300
        start = not fresh and not (th and th.is_alive()) and retry_ok
        if start:
            th = threading.Thread(target=lambda: _quiet(grid, region), name=f"wxmap-grid-{region}", daemon=True); _GRID_BG[region] = th
    if start: th.start()
    if hit and time.time() - hit[0] < MAX_AGE: return hit[1]
    fb = _gfs_grid(region) if region in GRIDS else None
    return fb or (hit[1] if hit else None)

def _quiet(fn, *a):
    try: fn(*a)
    except Exception as ex:
        with _L: _C[("griderr", a[0] if a else "")] = (time.time(), str(ex) if isinstance(ex, Limited) else why(ex))

def grid_peek(region):
    """The cached Open-Meteo grid if there is one (never starts a pull)."""
    with _L:
        hit = _C.get(("grid", region))
    return hit[1] if hit else None

def _peer_seed():
    """A fresh deploy asks the still-running old instance (public URL) for its grids and Open-Meteo budget before calling Open-Meteo."""
    if not PEER: return
    t0 = time.time(); got_state = False; old_peer = False; asked = {}
    try:
        while time.time() - t0 < PEER_WAIT - 20:
            if not got_state:
                try: got_state = OMB.adopt(json.loads(get(PEER + "/api/wxmap/omstate", timeout=15).decode("utf-8", "replace")))
                except urllib.error.HTTPError as ex: old_peer = ex.code == 404   # an instance from before this change
                except Exception: pass
            # an older instance starts an Open-Meteo pull whenever its grid is asked for and missing: ask it at most twice per grid
            need = [r for r in GRIDS if not ((grid_peek(r) or {}).get("generated") and time.time() - _gts(grid_peek(r)) < GRIDS[r]["ttl"]) and not (old_peer and asked.get(r, 0) >= 2)]
            if old_peer and not need: break
            for r in need:
                asked[r] = asked.get(r, 0) + 1
                try:
                    b = get(PEER + "/api/wxmap/grid?r=" + r + "&peer=1", timeout=20)
                    g = json.loads(b.decode("utf-8", "replace"))
                    if g.get("temp") and not g.get("fallback") and g.get("region") == r:
                        for k in ("as_of", "note", "label"): g.pop(k, None)
                        if _put_grid(r, g): _PEER_ST["got"].append(r)
                except Exception: pass
            if got_state and all((grid_peek(r) or {}).get("generated") for r in GRIDS): break
            time.sleep(15)
    finally:
        _PEER_ST["state"] = "done"

# ---------------------------------------------------------------- NWS warnings and watches
NWS = "https://api.weather.gov"
EVENTS = {   # event -> group (colour on the page)
    "Tornado Warning": "tor", "Tornado Watch": "tor", "Tornado Emergency": "tor",
    "Severe Thunderstorm Warning": "svr", "Severe Thunderstorm Watch": "svr", "Extreme Wind Warning": "svr",
    "Flash Flood Warning": "flood", "Flash Flood Emergency": "flood", "Flood Warning": "flood", "Flash Flood Watch": "flood",
    "Hurricane Warning": "trop", "Hurricane Watch": "trop", "Tropical Storm Warning": "trop", "Tropical Storm Watch": "trop",
    "Storm Surge Warning": "trop", "Storm Surge Watch": "trop", "Typhoon Warning": "trop",
    "Blizzard Warning": "winter", "Winter Storm Warning": "winter", "Ice Storm Warning": "winter", "Winter Storm Watch": "winter",
    "Lake Effect Snow Warning": "winter", "Snow Squall Warning": "winter",
    "High Wind Warning": "wind", "Dust Storm Warning": "wind",
    "Extreme Cold Warning": "cold", "Extreme Cold Watch": "cold", "Wind Chill Warning": "cold", "Hard Freeze Warning": "cold",
    "Extreme Heat Warning": "heat", "Excessive Heat Warning": "heat", "Red Flag Warning": "heat", "Fire Weather Watch": "heat"}
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR VI GU AS MP".split())
_ZONES = {}            # zone url -> (time, geometry or None)
ZONE_TTL = 7 * 86400

def _round_geom(g, nd=3, keep=1):
    if not g: return None
    def ring(r):
        r = [[round(x, nd), round(y, nd)] for x, y, *_ in r]
        if keep > 1 and len(r) > 40: r = r[:-1:keep] + [r[-1]]
        return r
    t = g.get("type")
    if t == "Polygon": return {"type": t, "coordinates": [ring(r) for r in g["coordinates"]]}
    if t == "MultiPolygon": return {"type": t, "coordinates": [[ring(r) for r in p] for p in g["coordinates"]]}
    return None

def _zone(url):
    hit = _ZONES.get(url)
    if hit and time.time() - hit[0] < ZONE_TTL: return hit[1]
    try:
        d = jget(url, accept="application/geo+json", timeout=12)
        g = _round_geom(d.get("geometry"), 3, 2)
    except Exception:
        g = hit[1] if hit else None
        if not hit: _ZONES[url] = (time.time() - ZONE_TTL + 1800, None); return None   # retry a failed zone after 30 min
    _ZONES[url] = (time.time(), g)
    return g

def alerts():
    def go():
        d = jget(NWS + "/alerts/active?status=actual&message_type=alert,update", accept="application/geo+json", timeout=20)
        feats, need = [], []
        for f in d.get("features") or []:
            p = f.get("properties") or {}
            ev = p.get("event") or ""
            grp = EVENTS.get(ev)
            if not grp: continue
            pr = {"id": (p.get("id") or "")[-60:], "event": ev, "g": grp, "watch": ev.endswith("Watch"), "headline": (p.get("headline") or "")[:220],
                  "area": (p.get("areaDesc") or "")[:240], "sender": p.get("senderName"), "onset": p.get("onset") or p.get("effective"), "ends": p.get("ends") or p.get("expires"),
                  "severity": p.get("severity"), "url": "https://alerts.weather.gov/search?id=" + urllib.parse.quote(p.get("id") or "") if p.get("id") else None}
            if f.get("geometry"):
                feats.append({"type": "Feature", "geometry": _round_geom(f["geometry"], 3), "properties": pr})
            else:
                zs = [z for z in (p.get("affectedZones") or []) if z.rsplit("/", 1)[-1][:2] in STATES]
                if zs: need.append((pr, zs[:60]))
        todo = list({z for _, zs in need for z in zs if not (_ZONES.get(z) and time.time() - _ZONES[z][0] < ZONE_TTL)})[:220]
        if todo:
            with ThreadPoolExecutor(8) as ex: list(ex.map(_zone, todo))
        for pr, zs in need:
            polys = []
            for z in zs:
                g = (_ZONES.get(z) or (0, None))[1]
                if not g: continue
                polys.extend([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"])
            if polys: feats.append({"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": polys}, "properties": pr})
        order = {"tor": 0, "svr": 1, "trop": 2, "flood": 3, "winter": 4, "wind": 5, "cold": 6, "heat": 7}
        feats.sort(key=lambda f: (not f["properties"]["watch"], -order.get(f["properties"]["g"], 9)))   # watches drawn first, tornado warnings on top
        counts = {}
        for f in feats: counts[f["properties"]["event"]] = counts.get(f["properties"]["event"], 0) + 1
        return {"generated": iso(now()), "type": "FeatureCollection", "features": feats, "counts": counts, "source": "NWS active alerts (api.weather.gov)"}
    return cached(("alerts",), 120, go)

# ---------------------------------------------------------------- storm reports, tornado tracks, SPC outlooks
LSR = {"TORNADO": "tor", "FUNNEL CLOUD": "tor", "WATERSPOUT": "tor", "HAIL": "hail", "TSTM WND DMG": "wind", "TSTM WND GST": "wind",
       "FLASH FLOOD": "flood", "SNOW": "snow", "HEAVY SNOW": "snow", "BLIZZARD": "snow", "ICE STORM": "snow", "FREEZING RAIN": "snow", "SNOW SQUALL": "snow"}
SPC_CAT = ("TSTM", "MRGL", "SLGT", "ENH", "MDT", "HIGH")

def _reports():
    d = jget("https://mesonet.agron.iastate.edu/geojson/lsr.php?hours=72", timeout=20)
    out = []
    for f in d.get("features") or []:
        p = f.get("properties") or {}
        k = LSR.get((p.get("typetext") or "").upper())
        if not k or p.get("lat") is None: continue
        try: tt = int(datetime.strptime(p["valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
        except Exception: continue
        mag = p.get("magnitude")
        out.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(p["lon"], 3), round(p["lat"], 3)]},
                    "properties": {"k": k, "type": (p.get("typetext") or "").title(), "mag": mag, "unit": p.get("unit"), "t": tt, "valid": p.get("valid"),
                                   "place": ", ".join(x for x in (p.get("city"), p.get("st") or p.get("state")) if x), "remark": (p.get("remark") or "")[:240], "src": p.get("source"), "wfo": p.get("wfo")}})
    return {"type": "FeatureCollection", "features": out}

def _tracks():
    since = (now() - timedelta(days=90)).strftime("%Y-%m-%d")
    q = {"where": f"stormdate >= DATE '{since}'", "outFields": "efscale,stormdate,wfo,length,width,injuries,fatalities,maxwind,event_id",
         "outSR": 4326, "maxAllowableOffset": 0.002, "f": "geojson", "resultRecordCount": 2000}
    d = jget("https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/1/query?" + urllib.parse.urlencode(q), timeout=25)
    out = []
    for f in d.get("features") or []:
        p, g = f.get("properties") or {}, f.get("geometry")
        if not g: continue
        ef = str(p.get("efscale") or "").upper()
        n = int(ef[2]) if len(ef) == 3 and ef[:2] == "EF" and ef[2].isdigit() else -1
        dt = datetime.fromtimestamp((p.get("stormdate") or 0) / 1000, timezone.utc)
        out.append({"type": "Feature", "geometry": g, "properties": {"ef": ef or "EFU", "n": n, "date": iso(dt), "wfo": p.get("wfo"), "name": (p.get("event_id") or "")[:80],
                    "len_mi": p.get("length"), "width_yd": p.get("width"), "inj": p.get("injuries"), "fat": p.get("fatalities"), "wind": p.get("maxwind")}})
    return {"type": "FeatureCollection", "features": out}

def _outlooks():
    out = []
    for day in (1, 2, 3):
        d = jget(f"https://www.spc.noaa.gov/products/outlook/day{day}otlk_cat.nolyr.geojson", timeout=15)
        for f in d.get("features") or []:
            p = f.get("properties") or {}
            if p.get("LABEL") not in SPC_CAT or not f.get("geometry"): continue
            out.append({"type": "Feature", "geometry": _round_geom(f["geometry"], 2),
                        "properties": {"day": day, "cat": p["LABEL"], "lvl": SPC_CAT.index(p["LABEL"]), "label": p.get("LABEL2"), "valid": p.get("VALID_ISO"), "expire": p.get("EXPIRE_ISO"), "issued": p.get("ISSUE_ISO")}})
    out.sort(key=lambda f: f["properties"]["lvl"])
    return {"type": "FeatureCollection", "features": out}

def storms():
    def part(name, fn, ttl):
        try: return cached(("st", name), ttl, fn), None
        except Exception as ex: return None, why(ex)
    with ThreadPoolExecutor(3) as ex:
        a = ex.submit(part, "reports", _reports, 300); b = ex.submit(part, "tracks", _tracks, 3600); c = ex.submit(part, "outlook", _outlooks, 900)
        (rp, re_), (tr, te), (ol, oe) = a.result(), b.result(), c.result()
    return {"generated": iso(now()), "reports": rp, "tracks": tr, "outlook": ol,
            "status": {"reports": {"ok": rp is not None, "reason": None if rp is not None else "Storm reports are unavailable: " + re_, "label": "NWS Local Storm Reports (IEM), 72 h"},
                       "tracks": {"ok": tr is not None, "reason": None if tr is not None else "Tornado tracks are unavailable: " + te, "label": "NWS Damage Assessment Toolkit, 90 days"},
                       "outlook": {"ok": ol is not None, "reason": None if ol is not None else "Severe outlook is unavailable: " + oe, "label": "NOAA SPC Day 1-3 outlooks"}}}

# ---------------------------------------------------------------- tropical: NHC active storms + this season's tracks (IBTrACS)
NHC_MS = "https://mapservices.weather.noaa.gov/tropical/rest/services/tropical/NHC_tropical_weather/MapServer"
BINS = [f"{b}{i}" for b in ("AT", "EP", "CP") for i in range(1, 6)]

def _nhc():
    d = jget("https://www.nhc.noaa.gov/CurrentStorms.json", timeout=15)
    storms_, feats = d.get("activeStorms") or [], []
    for s in storms_[:10]:
        b = (s.get("binNumber") or "").upper()
        if b not in BINS: continue
        base = 6 + 26 * BINS.index(b)
        for lid, kind in ((base + 2, "cone"), (base + 1, "track"), (base, "point"), (base + 6, "past")):
            try:
                q = {"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson", "maxAllowableOffset": 0.01}
                g = jget(f"{NHC_MS}/{lid}/query?" + urllib.parse.urlencode(q), timeout=15)
                for f in g.get("features") or []:
                    p = f.get("properties") or {}
                    f["properties"] = {"kind": kind, "name": s.get("name"), "cls": s.get("classification"), "wind_kt": s.get("intensity"), "pressure": s.get("pressure"),
                                       "move": f'{s.get("movementDir") or ""} deg {s.get("movementSpeed") or ""} mph'.strip(), "adv": s.get("lastUpdate"),
                                       "tau": p.get("tau") or p.get("TAU"), "label": p.get("datelbl") or p.get("fldatelbl") or p.get("DATELBL"),
                                       "url": f"https://www.nhc.noaa.gov/refresh/graphics_{b.lower()}+shtml/" }
                    feats.append(f)
            except Exception:
                continue
    return {"active": [{"name": s.get("name"), "cls": s.get("classification"), "wind_kt": s.get("intensity"), "lat": s.get("latitudeNumeric"), "lon": s.get("longitudeNumeric"), "bin": s.get("binNumber")} for s in storms_],
            "type": "FeatureCollection", "features": feats}

def _season():
    """This year's tracks worldwide from IBTrACS 'last3years' (NOAA NCEI), thinned to 6-hourly points. Refreshed every 12 hours."""
    raw = get("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.last3years.list.v04r01.csv",
              accept="text/csv", timeout=60, limit=40_000_000).decode("utf-8", "replace")
    yr = str(now().year)
    st = {}
    rd = csv.reader(io.StringIO(raw))
    hdr = next(rd); next(rd, None)
    ix = {k: hdr.index(k) for k in ("SID", "SEASON", "BASIN", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND", "WMO_WIND", "USA_SSHS")}
    for row in rd:
        if row[ix["SEASON"]] != yr and not (row[ix["ISO_TIME"]][:4] == yr): continue
        tm = row[ix["ISO_TIME"]]
        if tm[11:13] not in ("00", "06", "12", "18") or tm[14:16] != "00": continue
        try: la, lo = float(row[ix["LAT"]]), float(row[ix["LON"]])
        except ValueError: continue
        w = row[ix["USA_WIND"]].strip() or row[ix["WMO_WIND"]].strip()
        try: w = int(float(w))
        except ValueError: w = None
        s = st.setdefault(row[ix["SID"]], {"name": row[ix["NAME"]].title(), "basin": row[ix["BASIN"]], "pts": [], "max": 0, "first": tm, "last": tm})
        s["pts"].append([round(lo, 2), round(la, 2), w]); s["last"] = tm
        if w and w > s["max"]: s["max"] = w
    feats = []
    for sid, s in st.items():
        if len(s["pts"]) < 2: continue
        co = [[p[0], p[1]] for p in s["pts"]]
        for i in range(1, len(co)):   # keep lines continuous across the antimeridian
            while co[i][0] - co[i - 1][0] > 180: co[i][0] -= 360
            while co[i][0] - co[i - 1][0] < -180: co[i][0] += 360
        cat = 5 if s["max"] >= 137 else 4 if s["max"] >= 113 else 3 if s["max"] >= 96 else 2 if s["max"] >= 83 else 1 if s["max"] >= 64 else 0 if s["max"] >= 34 else -1
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": co},
                      "properties": {"sid": sid, "name": s["name"] if s["name"] not in ("Not_Named", "Unnamed") else "Unnamed", "basin": s["basin"], "max_kt": s["max"], "cat": cat,
                                     "first": s["first"][:10], "last": s["last"][:10]}})
    feats.sort(key=lambda f: f["properties"]["max_kt"])
    return {"type": "FeatureCollection", "features": feats, "season": yr}

# ---------------------------------------------------------------- worldwide: GDACS (UN / European Commission) cyclones, floods, droughts
GDACS = "https://www.gdacs.org/gdacsapi/api"
GD_LBL = {"TC": "Tropical cyclone", "FL": "Flood", "DR": "Drought"}

def _gd_tc(ev):
    """Track (lines), forecast cone and current position for one GDACS cyclone."""
    p = ev["properties"]
    g = jget(f"{GDACS}/polygons/getgeometry?eventtype=TC&eventid={p['eventid']}&episodeid={p['episodeid']}", timeout=20)
    name = (p.get("eventname") or p.get("name") or "").title()
    out, segs = [], []
    for f in g.get("features") or []:
        c = (f.get("properties") or {}).get("Class") or ""; geo = f.get("geometry") or {}
        if c.startswith("Line_") and geo.get("type") == "LineString": segs.append(geo["coordinates"])
        elif c == "Poly_Cones": out.append({"type": "Feature", "geometry": _round_geom(geo, 2), "properties": {"kind": "cone", "name": name, "src": "gdacs"}})
        elif c == "Point_Centroid": out.append({"type": "Feature", "geometry": geo, "properties": {"kind": "point", "name": name, "src": "gdacs"}})
    if segs: out.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [[[round(x, 2), round(y, 2)] for x, y in s_] for s_ in segs]}, "properties": {"kind": "track", "name": name, "src": "gdacs"}})
    for f in out:
        f["properties"].update({"cls": (p.get("severitydata") or {}).get("severitytext"), "alert": p.get("alertlevel"), "country": p.get("country"),
                                "url": (p.get("url") or {}).get("report"), "source": p.get("source")})
    return out

def gdacs():
    def go():
        frm = (now() - timedelta(days=14)).strftime("%Y-%m-%d")
        d = jget(f"{GDACS}/events/geteventlist/SEARCH?eventlist=TC;FL;DR&alertlevel=green;orange;red&fromDate={frm}&toDate={now().strftime('%Y-%m-%d')}", timeout=25)
        pts, tcs = [], []
        for f in d.get("features") or []:
            p = f.get("properties") or {}
            if str(p.get("iscurrent")).lower() != "true": continue
            et = p.get("eventtype")
            g = f.get("geometry") or {}
            if g.get("type") != "Point": continue
            pts.append({"type": "Feature", "geometry": g, "properties": {"et": et, "kind": GD_LBL.get(et, et), "name": p.get("name"), "alert": (p.get("alertlevel") or "").lower(),
                        "country": p.get("country"), "from": p.get("fromdate"), "to": p.get("todate"), "sev": (p.get("severitydata") or {}).get("severitytext"),
                        "url": (p.get("url") or {}).get("report")}})
            if et == "TC": tcs.append(f)
        tracks = []
        for f in tcs[:8]:
            try: tracks += _gd_tc(f)
            except Exception: continue
        return {"generated": iso(now()), "events": {"type": "FeatureCollection", "features": pts}, "cyclones": {"type": "FeatureCollection", "features": tracks},
                "source": "GDACS (Global Disaster Alert and Coordination System, UN / European Commission)"}
    return cached(("gdacs",), 1800, go)

def tropical():
    out = {"generated": iso(now())}
    try: out["active"] = cached(("nhc",), 900, _nhc); out["active_status"] = {"ok": True}
    except Exception as ex: out["active"] = None; out["active_status"] = {"ok": False, "reason": "NHC active storms are unavailable: " + why(ex)}
    try: out["season"] = cached(("season",), 12 * 3600, _season); out["season_status"] = {"ok": True}
    except Exception as ex: out["season"] = None; out["season_status"] = {"ok": False, "reason": "Season tracks are unavailable: " + why(ex)}
    return out

def warm():
    """Fill the slow caches in the background so the first visitor doesn't wait (season tracks: ~12 MB CSV)."""
    def run():
        wxgfs.kick()   # worldwide model rain + clouds (~1 minute, NOMADS)
        for fn in (frames, alerts, storms, tropical, gdacs):
            try: fn()
            except Exception: pass
        _peer_seed()                # take the old instance's grids before anything else (deploys never refill from Open-Meteo)
        for r in ("us", "world"):   # one after the other (Open-Meteo per-minute limit), only if still needed
            if not (grid_peek(r) and time.time() - _gts(grid_peek(r)) < GRIDS[r]["ttl"]): _quiet(grid, r)
    threading.Thread(target=run, name="wxmap-warm", daemon=True).start()

# ---------------------------------------------------------------- page
LOADER = ('<div class="wx-ld" id="wx_ld" role="status" aria-label="Loading the weather map"><div class="wx-ldc">'
  '<canvas class="wx-ldg" id="wx_ldg" width="260" height="260" aria-hidden="true"></canvas>'
  '<p class="wx-ldt"><span>BLACKOUT.NETWORK</span><i></i><span>WEATHER</span></p>'
  '<ul class="wx-ldl" aria-hidden="true">'
  '<li data-s="map"><span>Map engine</span><b>Standby</b></li>'
  '<li data-s="radar"><span>Radar frames</span><b>Standby</b></li>'
  '<li data-s="alerts"><span>Warnings and storms</span><b>Standby</b></li></ul>'
  '<div class="wx-ldbar"><i id="wx_ldfill"></i></div>'
  '<p class="wx-ldp"><span id="wx_ldphase">Initializing</span><b><span id="wx_ldn">000</span>%</b></p>'
  '<p class="wx-ldmsg" id="wx_ldmsg" hidden></p></div></div>')

def _ico(p): return f'<svg viewBox="0 0 24 24" aria-hidden="true">{p}</svg>'

def page(qs=None):
    try:
        import sitenav, sitenav_ui
        top = sitenav.header_html("weather"); theme = sitenav_ui.THEME_SCRIPT
    except Exception:
        top = '<header class="bn-top"><div class="bn-tbar"><a class="bn-logo" href="/"><span class="bnt-wm">blackout.network</span></a></div></header>'; theme = ""
    try:
        import signal_map
        mlv = signal_map._v("maplibre-gl.js"); mlc = signal_map._v("maplibre-gl.css")
    except Exception:
        mlv = mlc = "0"
    warm_once()
    title = "Weather: live radar, forecast and storms | BLACKOUT.NETWORK"
    desc = ("Full-screen live weather map, worldwide: radar you can scrub back and forward, temperature, rain and snow for the next 7 days, "
            "NWS warnings, tornado tracks, storm reports, cyclone paths and global disaster alerts.")
    lay = lambda k, name, sub: (f'<label class="wx-lay" data-k="{k}"><input type="checkbox" data-lay="{k}"><span class="wx-sw" aria-hidden="true"></span>'
                                f'<span class="wx-lt"><b>{E(name)}</b><small data-st="{k}">{E(sub)}</small></span></label>')
    return f'''<!doctype html><html lang="en" class="wx-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{theme}
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="https://blackout.network/weather">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="https://blackout.network/weather"><meta property="og:type" content="website"><meta property="og:image" content="https://blackout.network/og/weather.png">
<meta name="theme-color" content="#05060a">
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin><link rel="preconnect" href="https://mesonet.agron.iastate.edu" crossorigin><link rel="preconnect" href="https://gibs.earthdata.nasa.gov" crossorigin><link rel="preconnect" href="https://view.eumetsat.int" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={mlc}"><link rel="stylesheet" href="/api/wxmap/wx.css?v={_v("wx.css")}">
<script src="/sitenav.js" defer></script>
</head><body class="wx">
<a class="skip" href="#wx_tl">Skip to the timeline</a>
<div class="wx-head">{top}</div>
<script>(function(){{var m=document.getElementById("bn-menu");if(m&&m.parentNode!==document.body)document.body.appendChild(m)}})()</script>
<main id="wx_main" data-bnt-skip data-wxw="{_v("wxw.js")}">
<h1 class="wx-vh">Weather: live radar, forecast and storms</h1>
<div id="wx_map" class="wx-map" role="region" aria-label="Weather map. Drag to pan, pinch or scroll to zoom, tap for details."></div>
{LOADER}
<div class="wx-top">
<form class="wx-search" id="wx_search" role="search" autocomplete="off"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
<input id="wx_q" type="search" inputmode="search" placeholder="City or ZIP code" aria-label="Search a city or ZIP code" enterkeyhint="search"><ul id="wx_hits" role="listbox" hidden></ul></form>
<div class="wx-modes" id="wx_modes" role="group" aria-label="Map layer"><button type="button" data-m="radar" aria-pressed="true">Radar</button><button type="button" data-m="temp" aria-pressed="false">Temp</button><button type="button" data-m="rain" aria-pressed="false">Rain</button><button type="button" data-m="snow" aria-pressed="false">Snow</button></div>
<div class="wx-reg" id="wx_reg" role="group" aria-label="Region"><button type="button" data-r="us" aria-pressed="true">U.S.</button><button type="button" data-r="eu" aria-pressed="false">Europe</button><button type="button" data-r="apac" aria-pressed="false">Asia-Pacific</button><button type="button" data-r="world" aria-pressed="false">World</button></div>
<button type="button" class="wx-pill" id="wx_pill" hidden></button>
</div>
<div class="wx-ctl">
<button type="button" class="wx-b" id="wx_lay_btn" aria-label="Overlays" aria-controls="wx_lays" aria-expanded="false">{_ico('<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>')}</button>
<button type="button" class="wx-b" id="wx_loc" aria-label="Show my location">{_ico('<circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="7"/>')}</button>
<button type="button" class="wx-b" id="wx_zin" aria-label="Zoom in">{_ico('<path d="M12 6v12M6 12h12"/>')}</button>
<button type="button" class="wx-b" id="wx_zout" aria-label="Zoom out">{_ico('<path d="M6 12h12"/>')}</button>
<button type="button" class="wx-b" id="wx_home" aria-label="Show the whole U.S.">{_ico('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>')}</button>
</div>
<section class="wx-lays" id="wx_lays" aria-label="Overlays" hidden>
<div class="wx-lh"><p class="wx-k">Overlays</p><button type="button" class="wx-x" id="wx_lays_x" aria-label="Close">{_ico('<path d="M6 6l12 12M18 6L6 18"/>')}</button></div>
{lay("clouds", "Satellite clouds", "Infrared worldwide; model cloud cover ahead")}
{lay("global", "Global alerts", "Cyclones, floods and droughts worldwide")}
{lay("warn", "U.S. warnings and watches", "NWS")}
{lay("reports", "U.S. storm reports", "Last 72 hours")}
{lay("tracks", "U.S. tornado tracks", "Last 90 days")}
{lay("trop", "Hurricane season tracks", "This year, worldwide")}
{lay("outlook", "U.S. severe outlook", "SPC, follows the timeline")}
{lay("labels", "City values", "Temperature, rain and snow")}
<p class="wx-k wx-k2">Data sources</p><ul class="wx-srcs" id="wx_srcs"></ul>
<p class="wx-src" id="wx_src"></p>
</section>
<aside class="wx-card" id="wx_card" hidden aria-live="polite"></aside>
<div class="wx-dock" id="wx_dock">
<div class="wx-leg" id="wx_leg" aria-label="Legend"></div>
<div class="wx-tl" id="wx_tl">
<button type="button" class="wx-play" id="wx_play" aria-label="Play">{_ico('<path class="i-play" d="M8 5.5v13l10.5-6.5z"/><path class="i-pause" d="M8 5h3v14H8zM13 5h3v14h-3z"/>')}</button>
<div class="wx-tbody"><div class="wx-trow"><span class="wx-when" id="wx_when">Loading…</span><span class="wx-rel" id="wx_rel"></span></div>
<div class="wx-track" id="wx_track"><div class="wx-buf" id="wx_buf"></div><div class="wx-fill" id="wx_fill"></div><div class="wx-ticks" id="wx_ticks"></div><i class="wx-now" id="wx_nowm"></i>
<input type="range" id="wx_range" min="0" max="0" value="0" step="1" aria-label="Time"></div></div>
</div></div>
<noscript><p class="wx-nojs">The weather map needs JavaScript. <a href="/live#weather">Text forecast</a></p></noscript>
</main>
<script src="/api/signal/maplibre-gl.js?v={mlv}" defer></script><script src="/api/wxmap/wx.js?v={_v("wx.js")}" defer></script>
</body></html>'''

_WARMED = [False]
def warm_once():
    if not _WARMED[0]:
        _WARMED[0] = True; warm()

def _j(fn, label):
    try: return 200, fn()
    except Exception as ex: return 503, {"error": f"{label} unavailable", "reason": why(ex)}

def handle_get(path, qs):
    if path in ("/weather", "/weather/"):
        return 200, page(qs or {}), "text/html"
    if path == "/api/wxmap/frames": return _j(frames, "radar frames")
    if path == "/api/wxmap/grid":
        r = (qs or {}).get("r", "us")
        r = (r[0] if isinstance(r, list) else r) if r else "us"
        if r not in GRIDS: return 404, {"error": "unknown region"}
        b = grid_bytes(r)
        if b is None:
            with _L: err = _C.get(("griderr", r))
            reason = ("the forecast source did not answer (" + err[1] + "); retrying") if err else "the forecast grid is loading; it takes a few minutes after a restart"
            return 503, {"error": "model grid unavailable", "reason": reason, "retry": 30}
        return 200, b, "application/json"
    if path == "/api/wxmap/omstate":   # deploy handoff of the Open-Meteo budget (counts and back-off time only)
        return 200, dict(OMB.state(), summary=OMB.summary(), peer=_PEER_ST["state"])
    if path == "/api/wxmap/gfs":
        k = (qs or {}).get("f", "p"); k = (k[0] if isinstance(k, list) else k) or "p"
        if k not in ("p", "c"): return 404, {"error": "unknown field"}
        b = wxgfs.png(k)
        if not b:
            m, err = wxgfs.meta()
            return 503, {"error": "worldwide forecast unavailable", "reason": err or "the worldwide forecast is still loading", "retry": 60}
        return 200, b, "image/png"
    if path == "/api/wxmap/global": return _j(gdacs, "GDACS alerts")
    if path == "/api/wxmap/alerts": return _j(alerts, "NWS alerts")
    if path == "/api/wxmap/storms": return _j(storms, "storm data")
    if path == "/api/wxmap/tropical": return _j(tropical, "tropical data")
    if path.startswith("/api/wxmap/"):
        n = path[len("/api/wxmap/"):]
        if n not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}
