"""Weather add-on (tab "🌦 Weather", deep link #weather). Free public sources only, no keys, nothing stored about the viewer:
the chosen location lives in the browser (localStorage + cookie); this module only caches upstream answers in memory for ~10 minutes.
  - Location search: Open-Meteo geocoding API (proxied).  Reverse lookup for "use my location": OpenStreetMap Nominatim (cached, 1 req/s).
  - Forecast / current conditions everywhere: Open-Meteo forecast API (current, 48 h hourly, 7-day daily).
  - US: National Weather Service api.weather.gov (/points -> forecast, forecastHourly, nearest station observation, /alerts/active?point=).
  - Europe: MeteoAlarm (EUMETNET) official warnings feed per country, matched to the point by polygon or area name.
  - Everywhere: GDACS (UN/EC) current disaster events within a radius (cyclones, floods, quakes, volcanoes, drought, wildfire).
Never touches scanner.py, scoring, push.py, jets.py, config.json or blackout.db."""
import json, math, os, re, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "weather_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
TTL = 600                      # per-location upstream cache (seconds)
UA = "blackout.network-weather/1.0 (private research dashboard; contact via blackout.network)"
OM_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OM_FC = "https://api.open-meteo.com/v1/forecast"
NWS = "https://api.weather.gov"
MA = "https://feeds.meteoalarm.org/api/v1/warnings/feeds-"
GDACS = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
NOMI = "https://nominatim.openstreetmap.org/reverse"
# MeteoAlarm member feeds (ISO 3166-1 alpha-2 -> feed slug)
MA_SLUG = {"AT": "austria", "BE": "belgium", "BA": "bosnia-herzegovina", "BG": "bulgaria", "HR": "croatia", "CY": "cyprus", "CZ": "czechia",
           "DK": "denmark", "EE": "estonia", "FI": "finland", "FR": "france", "DE": "germany", "GR": "greece", "HU": "hungary", "IS": "iceland",
           "IE": "ireland", "IL": "israel", "IT": "italy", "LV": "latvia", "LT": "lithuania", "LU": "luxembourg", "MT": "malta", "MD": "moldova",
           "ME": "montenegro", "NL": "netherlands", "MK": "republic-of-north-macedonia", "NO": "norway", "PL": "poland", "PT": "portugal", "RO": "romania",
           "RS": "serbia", "SK": "slovakia", "SI": "slovenia", "ES": "spain", "SE": "sweden", "CH": "switzerland", "GB": "united-kingdom", "UA": "ukraine"}
US_LIKE = {"US", "PR", "GU", "VI", "AS", "MP"}
GDACS_TYPES = {"TC": ("Tropical cyclone", 1200), "FL": ("Flood", 400), "EQ": ("Earthquake", 400), "VO": ("Volcano", 300), "DR": ("Drought", 600), "WF": ("Wildfire", 250)}

_C = getattr(sys, "_bn_weather_cache", None)
if _C is None: _C = sys._bn_weather_cache = {}
_LK = getattr(sys, "_bn_weather_lock", None)
if _LK is None: _LK = sys._bn_weather_lock = threading.Lock()
_NOMI_T = [0.0]

def now(): return datetime.now(timezone.utc)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch(url, accept="application/json", timeout=15):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(12_000_000)
    return json.loads(body.decode("utf-8", "replace")), round(time.time() - t0, 2)

def cached(key, ttl, fn, force=False):
    with _LK:
        hit = _C.get(key)
        if hit and not force and time.time() - hit[0] < ttl: return hit[1], True
    val = fn()
    with _LK:
        _C[key] = (time.time(), val)
        if len(_C) > 400:   # keep memory small
            for k, _ in sorted(_C.items(), key=lambda kv: kv[1][0])[:100]: _C.pop(k, None)
    return val, False

def src(label, url, fn):
    """Run one upstream call; never raise. Returns {ok, label, url, fetched, secs, data|error}."""
    out = {"label": label, "url": url, "fetched": iso()}
    try:
        data, secs = fn()
        out.update(ok=True, secs=secs, data=data)
    except Exception as ex:
        msg = str(ex)
        if isinstance(ex, urllib.error.HTTPError): msg = f"HTTP {ex.code} {ex.reason}"
        out.update(ok=False, error=msg[:300])
    return out

def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

def pip(lat, lon, poly):
    inside, n = False, len(poly)
    for i in range(n):
        y1, x1 = poly[i]; y2, x2 = poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1: inside = not inside
    return inside

# ---------------- location search ----------------
def geocode(q):
    q = (q or "").strip()[:80]
    if len(q) < 2: return 200, {"results": []}
    url = OM_GEO + "?" + urllib.parse.urlencode({"name": q, "count": 10, "language": "en", "format": "json"})
    def go():
        d, _ = fetch(url)
        res = []
        for r in d.get("results") or []:
            res.append({"name": r.get("name"), "admin1": r.get("admin1"), "admin2": r.get("admin2"), "country": r.get("country"), "cc": r.get("country_code"),
                        "lat": r.get("latitude"), "lon": r.get("longitude"), "tz": r.get("timezone"), "pop": r.get("population"), "fc": r.get("feature_code")})
        return res
    try:
        res, hit = cached(("geo", q.lower()), 3600, go)
        return 200, {"results": res, "source": "Open-Meteo geocoding (GeoNames)", "cached": hit}
    except Exception as ex:
        return 502, {"error": f"location search unavailable: {ex}"[:300], "results": []}

def reverse(lat, lon):
    key = ("rev", round(lat, 3), round(lon, 3))
    def go():
        wait = 1.1 - (time.time() - _NOMI_T[0])
        if wait > 0: time.sleep(wait)
        _NOMI_T[0] = time.time()
        d, _ = fetch(NOMI + "?" + urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "en"}))
        a = d.get("address") or {}
        return {"name": a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("county") or d.get("name") or "My location",
                "admin1": a.get("state") or a.get("region"), "admin2": a.get("county"), "country": a.get("country"),
                "cc": (a.get("country_code") or "").upper() or None, "lat": lat, "lon": lon}
    try:
        r, _ = cached(key, 86400, go)
        return 200, {"result": r, "source": "OpenStreetMap Nominatim"}
    except Exception as ex:
        return 200, {"result": {"name": "My location", "lat": lat, "lon": lon, "cc": None}, "error": f"reverse lookup unavailable: {ex}"[:200]}

# ---------------- upstream sources ----------------
def open_meteo(lat, lon):
    q = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7, "forecast_hours": 48,
         "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,is_day",
         "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,relative_humidity_2m,uv_index",
         "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max,sunrise,sunset"}
    url = OM_FC + "?" + urllib.parse.urlencode(q)
    label = "Open-Meteo forecast (ECMWF / GFS / national models)"
    # Nov 22 2026 (pt1745u): shared Open-Meteo budget with the map grids; never call while backing off after a 429
    try: import om_budget as OMB
    except Exception: OMB = None
    if OMB:
        n = OMB.weight(33, 7)   # 12 current + 9 hourly + 12 daily variables
        lim, why_, until = OMB.limited()
        if lim or OMB.wait_s(n, "card") > 0:
            return {"label": label, "url": url, "fetched": iso(), "ok": False, "limited": True,
                    "error": "skipped: Open-Meteo is rate-limited right now" if lim else "skipped: the Open-Meteo budget for this hour is used up"}
        OMB.note(n, "card")
    def go():
        try: return fetch(url)
        except urllib.error.HTTPError as ex:
            if ex.code == 429 and OMB: OMB.on_429(ex)
            raise
    return src(label, url, go)

# ---------------- fallback forecast when Open-Meteo is limited (Nov 22 2026, pt1745u): NWS in the US, NOAA GFS elsewhere ----------------
def _wmo_text(t):
    t = (t or "").lower()
    if t.startswith("slight chance") or t.startswith("isolated"):   # a 10-20% chance is not a showery day: describe the sky instead
        t = t.split(" then ")[-1] if " then " in t else ("partly cloudy" if "thunder" not in t else "chance thunder")
    if "thunder" in t: return 95
    if "freezing" in t or "sleet" in t or "ice" in t: return 66
    if "snow" in t or "flurr" in t or "blizzard" in t: return 73 if "heavy" in t else 71
    if "drizzle" in t: return 51
    if "shower" in t: return 80
    if "rain" in t: return 63 if "heavy" in t else 61
    if "fog" in t or "haze" in t or "smoke" in t: return 45
    if "mostly cloudy" in t or "considerable cloud" in t: return 3
    if "partly" in t: return 2
    if "cloudy" in t or "overcast" in t: return 3
    if "mostly sunny" in t or "mostly clear" in t: return 1
    if "sunny" in t or "clear" in t or "fair" in t: return 0
    return 2

def _mph_kmh(v):
    try:
        if isinstance(v, (int, float)): return v * 1.609344
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(v or ""))]
        return max(nums) * 1.609344 if nums else None
    except Exception: return None

def _f2c(f): return None if f is None else round((f - 32) * 5 / 9, 1)

def _blank(n): return [None] * n

def fallback_nws(hourly, daily, obs):
    """Open-Meteo-shaped forecast (the fields the map card reads) from the NWS hourly and 12-hour forecasts."""
    H = (hourly or {}).get("periods") or []
    if not H: return None
    tl = [p["startTime"][:16] for p in H]
    tc = [_f2c(p.get("temperature")) if (p.get("temperatureUnit") or "F") == "F" else p.get("temperature") for p in H]
    pop = [p.get("probabilityOfPrecipitation") for p in H]
    wind = [_mph_kmh(p.get("windSpeed")) for p in H]
    cur = {"time": tl[0], "temperature_2m": tc[0], "apparent_temperature": None, "weather_code": _wmo_text(H[0].get("shortForecast")),
           "wind_speed_10m": wind[0], "wind_gusts_10m": None, "relative_humidity_2m": None, "is_day": 1 if H[0].get("isDaytime") else 0}
    if obs:
        if obs.get("temp_c") is not None: cur["temperature_2m"] = round(obs["temp_c"], 1)
        cur["relative_humidity_2m"] = obs.get("rh"); cur["wind_speed_10m"] = obs.get("wind_kmh") if obs.get("wind_kmh") is not None else cur["wind_speed_10m"]
        cur["wind_gusts_10m"] = obs.get("gust_kmh")
        hc, hk = obs.get("heat_c"), obs.get("chill_c")
        cur["apparent_temperature"] = hc if hc is not None else hk
    days = {}
    for p in (daily or {}).get("periods") or []:
        d = (p.get("startTime") or "")[:10]
        if not d: continue
        e = days.setdefault(d, {"max": None, "min": None, "pop": 0, "code": None})
        t = _f2c(p.get("temperature"))
        if p.get("isDaytime"): e["max"] = t; e["code"] = _wmo_text(p.get("shortForecast"))
        else:
            e["min"] = t
            if e["code"] is None: e["code"] = _wmo_text(p.get("shortForecast"))
        e["pop"] = max(e["pop"], p.get("probabilityOfPrecipitation") or 0)
    dk = sorted(days)[:7]
    return {"current": cur,
            "hourly": {"time": tl, "temperature_2m": tc, "precipitation_probability": pop, "wind_speed_10m": wind},
            "daily": {"time": dk, "weather_code": [days[d]["code"] for d in dk], "precipitation_probability_max": [days[d]["pop"] for d in dk],
                      "temperature_2m_max": [days[d]["max"] for d in dk], "temperature_2m_min": [days[d]["min"] for d in dk]}}

def _gfs_code(p, s, c):
    if p >= 0.3: return (73 if p >= 3 else 71) if s else (63 if p >= 3 else 61)
    return 3 if c >= 85 else 2 if c >= 50 else 1 if c >= 20 else 0

def fallback_gfs(lat, lon):
    """Open-Meteo-shaped forecast from the nearest 1-degree NOAA GFS point (3-hourly; local time approximated from the longitude)."""
    try: import wxgfs; ser = wxgfs.point_series(lat, lon)
    except Exception: ser = None
    if not ser: return None
    off = timedelta(hours=round(lon / 15))
    rows = []
    for t, f, p, sflag, c in ser:
        u = datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        rows.append((u, (u + off).strftime("%Y-%m-%dT%H:%M"), _f2c(f), p, sflag, c))
    nowu = now()
    fut = [r for r in rows if r[0] >= nowu - timedelta(hours=1, minutes=30)] or rows
    cur = fut[0]
    hrs = fut[:17]
    days = {}
    for u, lt, tc, p, sflag, c in rows:
        d = lt[:10]
        if (u + off).date() < (nowu + off).date(): continue
        e = days.setdefault(d, {"max": None, "min": None, "p": 0.0, "s": 0, "c": 0})
        if tc is not None:
            e["max"] = tc if e["max"] is None else max(e["max"], tc); e["min"] = tc if e["min"] is None else min(e["min"], tc)
        e["p"] = max(e["p"], p); e["s"] = max(e["s"], sflag if p >= 0.3 else 0); e["c"] = max(e["c"], c)
    dk = sorted(days)[:7]
    return {"current": {"time": cur[1], "temperature_2m": cur[2], "apparent_temperature": None, "weather_code": _gfs_code(cur[3], cur[4], cur[5]),
                        "wind_speed_10m": None, "wind_gusts_10m": None, "relative_humidity_2m": None},
            "hourly": {"time": [r[1] for r in hrs], "temperature_2m": [r[2] for r in hrs], "precipitation_probability": _blank(len(hrs))},
            "daily": {"time": dk, "weather_code": [_gfs_code(days[d]["p"], days[d]["s"], days[d]["c"]) for d in dk], "precipitation_probability_max": _blank(len(dk)),
                      "temperature_2m_max": [days[d]["max"] for d in dk], "temperature_2m_min": [days[d]["min"] for d in dk]}}

def nws(lat, lon):
    """Returns (points_src, forecast_src, hourly_src, obs_src, alerts_src)."""
    pu = f"{NWS}/points/{lat:.4f},{lon:.4f}"
    pts = src("NWS points (grid lookup)", pu, lambda: fetch(pu, "application/geo+json"))
    au = f"{NWS}/alerts/active?point={lat:.4f},{lon:.4f}"
    def alerts():
        d, s = fetch(au, "application/geo+json")
        out = []
        for f in d.get("features") or []:
            p = f.get("properties") or {}
            out.append({"id": p.get("id") or f.get("id"), "event": p.get("event"), "severity": p.get("severity"), "certainty": p.get("certainty"), "urgency": p.get("urgency"),
                        "headline": p.get("headline"), "description": p.get("description"), "instruction": p.get("instruction"), "area": p.get("areaDesc"),
                        "sender": p.get("senderName"), "sent": p.get("sent"), "onset": p.get("onset") or p.get("effective"), "expires": p.get("ends") or p.get("expires"),
                        "msgtype": p.get("messageType"), "status": p.get("status"), "url": f.get("id"), "match": "point inside the alert's zones (NWS)",
                        "link": f"https://forecast.weather.gov/MapClick.php?lat={lat:.4f}&lon={lon:.4f}"})
        rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
        out.sort(key=lambda a: (rank.get(a["severity"], 4), a["onset"] or ""))
        return out, s
    al = src("NWS active alerts for this point", au, alerts)
    if not pts.get("ok"):
        bad = {"label": "NWS forecast", "url": None, "ok": False, "error": "skipped: NWS grid lookup failed"}
        return pts, dict(bad), dict(bad, label="NWS hourly forecast"), dict(bad, label="NWS latest observation"), al
    P = pts["data"].get("properties") or {}
    rl = (P.get("relativeLocation") or {}).get("properties") or {}
    pts["data"] = {"grid": f'{P.get("gridId")} {P.get("gridX")},{P.get("gridY")}', "office": P.get("cwa"), "city": rl.get("city"), "state": rl.get("state"),
                   "zone": (P.get("forecastZone") or "").rsplit("/", 1)[-1], "county": (P.get("county") or "").rsplit("/", 1)[-1], "radar": P.get("radarStation"),
                   "tz": P.get("timeZone"), "forecast": P.get("forecast"), "hourly": P.get("forecastHourly"), "stations": P.get("observationStations")}
    def per(u, n):
        d, s = fetch(u, "application/geo+json")
        pr = d.get("properties") or {}
        keep = ("name", "startTime", "endTime", "isDaytime", "temperature", "temperatureUnit", "probabilityOfPrecipitation", "windSpeed", "windDirection", "shortForecast", "detailedForecast", "icon")
        ps = [{k: (x.get(k)["value"] if isinstance(x.get(k), dict) and "value" in x.get(k) else x.get(k)) for k in keep} for x in (pr.get("periods") or [])[:n]]
        return {"updated": pr.get("updateTime") or pr.get("generatedAt"), "periods": ps}, s
    def obs():
        su = pts["data"]["stations"]
        d, s1 = fetch(su, "application/geo+json")
        feats = d.get("features") or []
        if not feats: raise RuntimeError("no observation stations listed")
        st = feats[0].get("properties") or {}
        g = (feats[0].get("geometry") or {}).get("coordinates") or [None, None]
        o, s2 = fetch(f'{NWS}/stations/{st.get("stationIdentifier")}/observations/latest', "application/geo+json")
        op = o.get("properties") or {}
        v = lambda k: (op.get(k) or {}).get("value")
        return {"station": st.get("stationIdentifier"), "station_name": st.get("name"), "dist_km": round(hav(lat, lon, g[1], g[0]), 1) if g[0] is not None else None,
                "time": op.get("timestamp"), "text": op.get("textDescription"), "temp_c": v("temperature"), "dew_c": v("dewpoint"), "rh": v("relativeHumidity"),
                "wind_kmh": v("windSpeed"), "gust_kmh": v("windGust"), "wind_dir": v("windDirection"), "pressure_pa": v("barometricPressure"),
                "vis_m": v("visibility"), "heat_c": v("heatIndex"), "chill_c": v("windChill"),
                "link": f'https://www.weather.gov/wrh/timeseries?site={st.get("stationIdentifier")}'}, round(s1 + s2, 2)
    with ThreadPoolExecutor(3) as ex:
        f1 = ex.submit(src, "NWS forecast (12-hour periods)", P.get("forecast"), lambda: per(P.get("forecast"), 14))
        f2 = ex.submit(src, "NWS hourly forecast", P.get("forecastHourly"), lambda: per(P.get("forecastHourly"), 48))
        f3 = ex.submit(src, "NWS latest station observation", P.get("observationStations"), obs)
        return pts, f1.result(), f2.result(), f3.result(), al

def meteoalarm(lat, lon, cc, names):
    slug = MA_SLUG.get(cc or "")
    if not slug: return None
    url = MA + slug
    def go():
        d, s = fetch(url, timeout=25)
        t = now(); here, elsewhere = [], {}
        nm = [n.lower() for n in names if n and len(n) > 2]
        for w in d.get("warnings") or []:
            a = w.get("alert") or {}
            if (a.get("msgType") or "").lower() == "cancel" or (a.get("status") or "").lower() != "actual": continue
            infos = a.get("info") or []
            if not infos: continue
            info = next((i for i in infos if (i.get("language") or "").lower().startswith("en")), infos[0])
            try: exp = datetime.fromisoformat((info.get("expires") or "").replace("Z", "+00:00"))
            except Exception: exp = None
            if exp and exp < t: continue
            hit, how = False, None
            for ar in info.get("area") or []:
                for pg in ar.get("polygon") or []:
                    try:
                        poly = [tuple(map(float, p.split(","))) for p in pg.split()]
                        if len(poly) >= 3 and pip(lat, lon, poly): hit, how = True, "point inside the warning polygon"
                    except Exception: pass
                desc = (ar.get("areaDesc") or "").lower()
                if not hit and nm and any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", desc) for n in nm):
                    hit, how = True, "warning area name matches this location (" + (ar.get("areaDesc") or "")[:80] + ")"
                if hit: break
            lvl = next((p.get("value") for p in info.get("parameter") or [] if p.get("valueName") == "awareness_level"), None)
            item = {"id": a.get("identifier"), "event": info.get("event"), "severity": info.get("severity"), "certainty": info.get("certainty"), "urgency": info.get("urgency"),
                    "headline": info.get("headline"), "description": info.get("description"), "instruction": info.get("instruction"),
                    "area": " | ".join((ar.get("areaDesc") or "") for ar in info.get("area") or [])[:400], "sender": info.get("senderName") or a.get("sender"),
                    "sent": a.get("sent"), "onset": info.get("onset") or info.get("effective"), "expires": info.get("expires"), "level": lvl, "lang": info.get("language"),
                    "url": info.get("web") or f"https://meteoalarm.org/en/live/region/{(cc or '').upper()}", "link": "https://meteoalarm.org/en/live/", "match": how}
            if hit: here.append(item)
            else:
                k = info.get("event") or "warning"; elsewhere[k] = elsewhere.get(k, 0) + 1
        rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
        here.sort(key=lambda x: (rank.get(x["severity"], 4), x["onset"] or ""))
        # identical warnings repeat once per region: collapse by (event, onset, expires, headline)
        seen, uniq = set(), []
        for x in here:
            k = (x["event"], x["onset"], x["expires"], x["headline"])
            if k in seen: continue
            seen.add(k); uniq.append(x)
        return {"alerts": uniq, "elsewhere": elsewhere, "country_page": f"https://meteoalarm.org/en/live/region/{(cc or '').upper()}"}, s
    return src(f"MeteoAlarm official warnings ({slug.replace('-', ' ').title()})", url, go)

def gdacs(lat, lon):
    t = now()
    q = {"eventlist": ";".join(GDACS_TYPES), "alertlevel": "Green;Orange;Red", "fromDate": (t - timedelta(days=10)).strftime("%Y-%m-%d"), "toDate": t.strftime("%Y-%m-%d")}
    url = GDACS + "?" + urllib.parse.urlencode(q, safe=";")
    def go():
        d, s = cached(("gdacs",), TTL, lambda: fetch(url, timeout=25))[0]
        out = []
        for f in d.get("features") or []:
            p = f.get("properties") or {}; g = f.get("geometry") or {}
            if str(p.get("iscurrent")).lower() != "true" or g.get("type") != "Point": continue
            et = p.get("eventtype"); lbl, rad = GDACS_TYPES.get(et, (et, 300))
            if et == "EQ" and p.get("alertlevel") == "Green": rad = 150
            lo, la = g["coordinates"][:2]
            dk = hav(lat, lon, la, lo)
            if dk > rad: continue
            out.append({"type": lbl, "name": p.get("name") or p.get("description"), "level": p.get("alertlevel"), "dist_km": round(dk), "from": p.get("fromdate"),
                        "to": p.get("todate"), "country": p.get("country"), "url": (p.get("url") or {}).get("report"), "radius_km": rad,
                        "summary": re.sub(r"<[^>]+>", "", p.get("htmldescription") or "")[:300]})
        out.sort(key=lambda x: ({"Red": 0, "Orange": 1}.get(x["level"], 2), x["dist_km"]))
        return out, s
    return src("GDACS (UN / EU) current disaster events nearby", url, go)

# ---------------- combined ----------------
def report(lat, lon, cc, names, force=False):
    lat, lon = round(lat, 4), round(lon, 4)
    cc = (cc or "").upper() or None
    key = ("wx", round(lat, 2), round(lon, 2), cc)
    def go():
        us = cc in US_LIKE if cc else (18 <= lat <= 72 and -180 <= lon <= -64)   # unknown country: try NWS for anything in the US box
        with ThreadPoolExecutor(4) as ex:
            fo = ex.submit(open_meteo, lat, lon)
            fn = ex.submit(nws, lat, lon) if us else None
            fm = ex.submit(meteoalarm, lat, lon, cc, names) if not us else None
            fg = ex.submit(gdacs, lat, lon)
            om = fo.result(); nw = fn.result() if fn else None; ma = fm.result() if fm else None; gd = fg.result()
        srcs = {"open_meteo": om, "gdacs": gd}
        alerts_note = None
        if nw:
            for k, v in zip(("nws_points", "nws_forecast", "nws_hourly", "nws_obs", "nws_alerts"), nw): srcs[k] = v
            if not nw[0].get("ok") and not cc: us = False      # outside NWS coverage after all
        if ma: srcs["meteoalarm"] = ma
        if not om.get("ok"):   # Open-Meteo limited or down: the card still gets a forecast
            fbd, lab = None, None
            if nw and nw[2].get("ok"):
                try: fbd = fallback_nws(nw[2].get("data"), (nw[1] or {}).get("data") if nw[1].get("ok") else None, nw[3].get("data") if nw[3].get("ok") else None); lab = "National Weather Service forecast (Open-Meteo is unavailable right now)"
                except Exception: fbd = None
            if not fbd:
                try: fbd = fallback_gfs(lat, lon); lab = "NOAA GFS 1° model (Open-Meteo is unavailable right now)"
                except Exception: fbd = None
            srcs["fallback"] = {"ok": bool(fbd), "label": lab or "Fallback forecast", "fetched": iso(), "data": fbd} if fbd else {"ok": False, "label": "Fallback forecast", "error": "no fallback forecast yet"}
        if not nw and not ma:
            alerts_note = ("No free official weather-warning feed is wired up for this country yet. Official alerts here cover the US (National Weather Service) "
                           "and the 38 MeteoAlarm countries in Europe; elsewhere only GDACS major-disaster events and the forecast are shown. Check the national weather service.")
        return {"generated": iso(), "lat": lat, "lon": lon, "cc": cc, "us": bool(nw), "sources": srcs, "alerts_note": alerts_note, "ttl_s": TTL}
    d, hit = cached(key, TTL, go, force=force)
    d = dict(d); d["cached"] = hit
    return d

# ---------------- t244: live radar frame lists (tiles themselves load straight from the providers in the browser) ----------------
RV_JSON = "https://api.rainviewer.com/public/weather-maps.json"   # RainViewer public Weather Maps API: free, no key, personal/educational/small community use, credit required
NOAA_WMS = "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows"   # NOAA/NWS NCEP MRMS QC base reflectivity (CONUS), public domain, no fees/constraints
NOAA_LAYER = "conus_bref_qcd"

def _noaa_times():
    t0 = time.time()
    req = urllib.request.Request(NOAA_WMS + "?service=WMS&request=GetCapabilities&version=1.3.0", headers={"User-Agent": UA, "Accept": "text/xml"})
    with urllib.request.urlopen(req, timeout=15) as r: xml = r.read(2_000_000).decode("utf-8", "replace")
    m = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]+)</Dimension>', xml)
    if not m: raise ValueError("no time dimension in NOAA WMS capabilities")
    ts = sorted(t.strip() for t in m.group(1).split(",") if t.strip())
    # ~2-minute scans over the last 2 h -> one frame about every 10 min, newest always included
    out, last = [], None
    for t in reversed(ts):
        d = datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        if last is None or (last - d).total_seconds() >= 570: out.append(t); last = d
        if len(out) >= 12: break
    return list(reversed(out)), round(time.time() - t0, 2)

def _rv_frames():
    d, secs = fetch(RV_JSON)
    fr = [{"time": f["time"], "path": f["path"]} for f in ((d.get("radar") or {}).get("past") or []) if f.get("path")]
    return {"host": d.get("host") or "https://tilecache.rainviewer.com", "frames": fr[-12:], "generated": d.get("generated")}, secs

def radar():
    """Frame timelines for both radar sources, cached 2 min so visitors don't each hit the upstreams."""
    def go():
        with ThreadPoolExecutor(2) as ex:
            a = ex.submit(src, "NOAA/NWS MRMS radar (WMS)", NOAA_WMS + "?service=WMS&request=GetCapabilities", _noaa_times)
            b = ex.submit(src, "RainViewer radar", RV_JSON, _rv_frames)
            return {"noaa": a.result(), "rainviewer": b.result()}
    r, hit = cached(("radar",), 120, go)
    return 200, dict(r, generated=iso(), cached=hit, noaa_wms=NOAA_WMS, noaa_layer=NOAA_LAYER)

def _f(qs, k, default=None):
    v = (qs.get(k) or [default])[0]
    return v

def handle_get(path, qs):
    if path.startswith("/api/weather/"):
        name = path[len("/api/weather/"):]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as fh: return 200, fh.read(), FILES[name]
        if name == "geocode": return geocode(_f(qs, "q", ""))
        if name == "radar": return radar()
        if name == "reverse":
            try: lat, lon = float(_f(qs, "lat")), float(_f(qs, "lon"))
            except Exception: return 400, {"error": "lat and lon required"}
            if not (-90 <= lat <= 90 and -180 <= lon <= 180): return 400, {"error": "lat/lon out of range"}
            return reverse(lat, lon)
        return 404, {"error": "not found"}
    if path == "/api/weather":
        try: lat, lon = float(_f(qs, "lat")), float(_f(qs, "lon"))
        except Exception: return 400, {"error": "lat and lon required (no default location)"}
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): return 400, {"error": "lat/lon out of range"}
        cc = re.sub(r"[^A-Za-z]", "", _f(qs, "cc", "") or "")[:2]
        names = [re.sub(r"[^\w .'-]", "", _f(qs, k, "") or "", flags=re.U)[:60] for k in ("name", "admin1", "admin2")]
        force = _f(qs, "force", "0") == "1"
        if force:   # manual refresh: allow a fresh upstream pull at most once a minute per location
            with _LK:
                hit = _C.get(("wx", round(lat, 2), round(lon, 2), (cc or "").upper() or None))
            if hit and time.time() - hit[0] < 60: force = False
        return 200, report(lat, lon, cc, names, force)
    return 404, {"error": "not found"}
