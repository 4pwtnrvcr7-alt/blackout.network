"""/weather: full-screen Weather map (Matt pt1742u, Nov 22 2026). Same map stack and design language as /grid and /map
(MapLibre GL + OpenFreeMap). Replaces the menu link to the old /live#weather dashboard tab (that tab and /api/weather stay as they were;
the location card on this page reuses /api/weather and /api/weather/geocode).

Free, keyless public sources only. Radar and model tiles load straight from the providers in the browser as map-native raster layers;
this module only builds frame lists and re-serves small, cached JSON so visitors never each hit an upstream:
  - Past radar: Iowa Environmental Mesonet (IEM) archive of the NWS NEXRAD composite (ridge::USCOMP-N0Q), 5-minute stamps.
  - Forecast radar: NOAA HRRR simulated reflectivity with precip type, via IEM tiles (hrrr::REFP), latest run + latest 48-hour run.
  - Temperature / rain / snow: Open-Meteo forecast API on a 1.5-degree grid over the lower 48 (past 24 h + 7 days, 3-hourly), one
    pull every 6 hours, drawn in the browser.
  - Warnings and watches: NWS api.weather.gov active alerts (storm-based polygons, plus forecast-zone / county shapes, cached).
  - Storm reports (72 h): NWS Local Storm Reports via IEM. Tornado tracks (90 days): NWS Damage Assessment Toolkit.
  - Severe outlook: NOAA SPC Day 1-3 categorical outlooks. Hurricanes: NHC active storms (cone, track) + IBTrACS season tracks (NOAA NCEI).
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json, blackout.db, the newsletter or geo code.
Routes: /weather (page), /api/wxmap/frames|grid|alerts|storms|tropical|status, /api/wxmap/<static file>."""
import os, io, csv, json, re, time, threading, urllib.parse, urllib.request, html as _html
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "wxmap_static")
FILES = {"wx.js": "application/javascript", "wx.css": "text/css"}
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
PAST_H, PAST_STEP = 6, 10          # past radar: 6 hours at 10-minute steps

def _floor5(d): return d.replace(minute=d.minute - d.minute % 5, second=0, microsecond=0)

def _hrrr_init(fname):
    d = jget(f"https://mesonet.agron.iastate.edu/data/gis/images/4326/hrrr/{fname}", timeout=10)
    return datetime.strptime(d["model_init_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def frames():
    def go():
        out = {"generated": iso(now()), "past": [], "forecast": [], "sources": {}}
        # past: MRMS SeamlessHSR (NOAA's quality-controlled radar mosaic; 2-minute archive at IEM), else the raw NEXRAD composite
        n = PAST_H * 60 // PAST_STEP
        try:
            m = jget("https://mesonet.agron.iastate.edu/data/gis/images/4326/mrms/lcref.json", timeout=10)
            latest = datetime.strptime(m["meta"]["end_valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            latest = latest.replace(minute=latest.minute - latest.minute % 2, second=0, microsecond=0)
            for i in range(n, -1, -1):
                d = latest - timedelta(minutes=PAST_STEP * i)
                if i: d = d.replace(minute=d.minute - d.minute % PAST_STEP)
                out["past"].append({"t": iso(d), "layer": "mrms::lcref-" + d.strftime("%Y%m%d%H%M")})
            out["sources"]["past"] = {"ok": True, "label": "NOAA MRMS radar mosaic (IEM archive)", "latest": iso(latest)}
        except Exception as ex1:
            try:
                t = jget("https://mesonet.agron.iastate.edu/json/tms.json", timeout=10)
                lay = next((s for s in t.get("services", []) if s.get("id") == "ridge_uscomp_n0q"), None)
                latest = _floor5(datetime.strptime(lay["utc_valid"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
                for i in range(n, -1, -1):
                    d = latest - timedelta(minutes=PAST_STEP * i)
                    if i: d = d.replace(minute=d.minute - d.minute % PAST_STEP)
                    out["past"].append({"t": iso(d), "layer": "ridge::USCOMP-N0Q-" + d.strftime("%Y%m%d%H%M")})
                out["sources"]["past"] = {"ok": True, "label": "NWS NEXRAD composite (IEM archive)", "latest": iso(latest)}
            except Exception as ex:
                out["sources"]["past"] = {"ok": False, "label": "NOAA MRMS / NWS NEXRAD radar (IEM archive)", "reason": "Past radar is unavailable: " + why(ex)}
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
                if fm >= 0:
                    out["forecast"].append({"t": iso(d), "layer": f"hrrr::REFP-F{fm:04d}-{run.strftime('%Y%m%d%H%M')}", "run": iso(run)})
                d += timedelta(hours=1)
            out["sources"]["forecast"] = {"ok": bool(out["forecast"]), "label": "NOAA HRRR model radar forecast (IEM)", "run": iso(ini), "long_run": iso(ext) if ext else None,
                                          "reason": None if out["forecast"] else "No HRRR forecast frames are published right now"}
        except Exception as ex:
            out["sources"]["forecast"] = {"ok": False, "label": "NOAA HRRR model radar forecast (IEM)", "reason": "Radar forecast is unavailable: " + why(ex)}
        out["tile"] = IEM_TILE
        return out
    return cached(("frames",), 180, go)

# ---------------------------------------------------------------- model grid (temperature / rain / snow)
G_LAT0, G_LON0, G_STEP, G_NY, G_NX = 23.0, -126.0, 1.5, 19, 41
GRID_TTL = 6 * 3600
OM = "https://api.open-meteo.com/v1/forecast"

def grid():
    def go():
        pts = [(round(G_LAT0 + G_STEP * j, 2), round(G_LON0 + G_STEP * i, 2)) for j in range(G_NY) for i in range(G_NX)]
        def pull(chunk):
            q = {"latitude": ",".join(str(a) for a, _ in chunk), "longitude": ",".join(str(b) for _, b in chunk),
                 "hourly": "temperature_2m,precipitation,snowfall", "past_days": 1, "forecast_days": 7, "timezone": "GMT", "temporal_resolution": "hourly_3"}
            u = OM + "?" + urllib.parse.urlencode(q, safe=",")
            try: d = jget(u, timeout=40)
            except Exception:
                time.sleep(2); d = jget(u, timeout=40)   # one retry: the upstream occasionally drops a TLS handshake
            return d if isinstance(d, list) else [d]
        chunks = [pts[k:k + 400] for k in range(0, len(pts), 400)]
        with ThreadPoolExecutor(2) as ex: res = [r for part in ex.map(pull, chunks) for r in part]
        if len(res) != len(pts): raise ValueError("grid size mismatch")
        times = res[0]["hourly"]["time"]
        nt = len(times)
        T, P, S = [], [], []
        for k in range(nt):
            for r in res:
                h = r["hourly"]
                t, p, s = h["temperature_2m"][k], h["precipitation"][k], h["snowfall"][k]
                T.append(None if t is None else round(t * 9 / 5 + 32))
                P.append(None if p is None else round(p * 10))
                S.append(None if s is None else round(s * 10))
        return {"generated": iso(now()), "lat0": G_LAT0, "lon0": G_LON0, "step": G_STEP, "ny": G_NY, "nx": G_NX,
                "times": [x + ":00Z" for x in times], "step_h": 3, "temp": T, "precip": P, "snow": S,
                "units": {"temp": "F", "precip": "0.1 mm per 3 h", "snow": "0.1 cm per 3 h"},
                "source": "Open-Meteo forecast API (NOAA GFS / HRRR and other national models), 1.5-degree grid"}
    return cached(("grid",), GRID_TTL, go)

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
        for fn in (frames, alerts, storms, tropical, grid):
            try: fn()
            except Exception: pass
    threading.Thread(target=run, name="wxmap-warm", daemon=True).start()

# ---------------------------------------------------------------- page
LOADER = ('<div class="wx-ld" id="wx_ld" role="status" aria-label="Loading the weather map">'
  '<div class="wx-flash" aria-hidden="true"></div>'
  '<svg class="wx-ldsvg" viewBox="0 0 240 200" aria-hidden="true" focusable="false">'
  '<path class="wx-cloud" d="M62 104a30 30 0 0 1 6-59 42 42 0 0 1 80-8 34 34 0 0 1 32 67z"/>'
  '<g class="wx-rain"><path d="M70 120l-8 22"/><path d="M96 120l-8 22"/><path d="M150 120l-8 22"/><path d="M176 120l-8 22"/><path d="M83 150l-8 22"/><path d="M163 150l-8 22"/></g>'
  '<path class="wx-bolt" d="M128 92l-26 46h20l-12 44 36-56h-21l15-34z"/>'
  '<path class="wx-bolt2" d="M178 98l-10 18h8l-5 16 14-22h-8l6-12z"/>'
  '</svg>'
  '<p class="wx-ldk"><span>Charging the radar</span><b id="wx_ldn">00%</b></p>'
  '<ol class="wx-lds" aria-hidden="true"><li data-s="map">Map</li><li data-s="radar">Radar</li><li data-s="storms">Storms</li></ol>'
  '<p class="wx-ldmsg" id="wx_ldmsg" hidden></p></div>')

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
    desc = ("Full-screen live weather map: radar you can scrub back six hours and forward up to two days, temperature, rain and snow outlooks, "
            "NWS warnings, tornado tracks, storm reports and hurricane paths.")
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
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin><link rel="preconnect" href="https://mesonet.agron.iastate.edu" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={mlc}"><link rel="stylesheet" href="/api/wxmap/wx.css?v={_v("wx.css")}">
<script src="/sitenav.js" defer></script>
</head><body class="wx">
<a class="skip" href="#wx_tl">Skip to the timeline</a>
<div class="wx-head">{top}</div>
<script>(function(){{var m=document.getElementById("bn-menu");if(m&&m.parentNode!==document.body)document.body.appendChild(m)}})()</script>
<main id="wx_main" data-bnt-skip>
<h1 class="wx-vh">Weather: live radar, forecast and storms</h1>
<div id="wx_map" class="wx-map" role="region" aria-label="Weather map. Drag to pan, pinch or scroll to zoom, tap for details."></div>
{LOADER}
<div class="wx-top">
<form class="wx-search" id="wx_search" role="search" autocomplete="off"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
<input id="wx_q" type="search" inputmode="search" placeholder="City or ZIP code" aria-label="Search a city or ZIP code" enterkeyhint="search"><ul id="wx_hits" role="listbox" hidden></ul></form>
<div class="wx-modes" id="wx_modes" role="group" aria-label="Map layer"><button type="button" data-m="radar" aria-pressed="true">Radar</button><button type="button" data-m="temp" aria-pressed="false">Temp</button><button type="button" data-m="rain" aria-pressed="false">Rain</button><button type="button" data-m="snow" aria-pressed="false">Snow</button></div>
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
{lay("warn", "Warnings and watches", "NWS")}
{lay("reports", "Storm reports", "Last 72 hours")}
{lay("tracks", "Tornado tracks", "Last 90 days")}
{lay("trop", "Hurricane season tracks", "This year, worldwide")}
{lay("outlook", "Severe outlook", "SPC, follows the timeline")}
{lay("labels", "City values", "Temperature, rain and snow")}
<p class="wx-src" id="wx_src"></p>
</section>
<aside class="wx-card" id="wx_card" hidden aria-live="polite"></aside>
<div class="wx-dock" id="wx_dock">
<div class="wx-leg" id="wx_leg" aria-label="Legend"></div>
<div class="wx-tl" id="wx_tl">
<button type="button" class="wx-play" id="wx_play" aria-label="Play">{_ico('<path class="i-play" d="M8 5.5v13l10.5-6.5z"/><path class="i-pause" d="M8 5h3v14H8zM13 5h3v14h-3z"/>')}</button>
<div class="wx-tbody"><div class="wx-trow"><span class="wx-when" id="wx_when">Loading…</span><span class="wx-rel" id="wx_rel"></span></div>
<div class="wx-track" id="wx_track"><div class="wx-fill" id="wx_fill"></div><div class="wx-ticks" id="wx_ticks"></div><i class="wx-now" id="wx_nowm"></i>
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
        c, b = _j(grid, "model grid")
        return (c, json.dumps(b, separators=(",", ":")).encode(), "application/json") if c == 200 else (c, b)
    if path == "/api/wxmap/alerts": return _j(alerts, "NWS alerts")
    if path == "/api/wxmap/storms": return _j(storms, "storm data")
    if path == "/api/wxmap/tropical": return _j(tropical, "tropical data")
    if path.startswith("/api/wxmap/"):
        n = path[len("/api/wxmap/"):]
        if n not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}
