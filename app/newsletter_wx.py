"""Weather forecast + major weather alerts for the 7 AM / 7 PM brief (Matt, pt1754u, Nov 22 2026).

for_sub(sub) -> dict or None. Local when the reader saved an area (loc_lat/loc_lon), otherwise a US national overview.
Sources (free, public, same family as /weather): NWS api.weather.gov (forecast, alerts), NHC CurrentStorms.json,
Open-Meteo (budgeted via weather.open_meteo) then NOAA GFS outside the US.
Never raises: any failure drops only the part that failed; an empty result returns None so the issue shows no section.
Kill switch: env BN_NL_WEATHER=0 or newsletter_config.json "weather_section": false."""
import json, os, re, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone, timedelta

UA = "blackout.network-newsletter/1.0 (weather section; contact via blackout.network)"
NWS = "https://api.weather.gov"
NHC_JSON = "https://www.nhc.noaa.gov/CurrentStorms.json"
NWS_ALERTS_PAGE = "https://www.weather.gov/alerts"
NHC_PAGE = "https://www.nhc.noaa.gov/"
US_LIKE = {"US", "PR", "GU", "VI", "AS", "MP"}
CITIES = [("New York", 40.7128, -74.0060), ("Chicago", 41.8781, -87.6298), ("Miami", 25.7617, -80.1918),
          ("Dallas", 32.7767, -96.7970), ("Denver", 39.7392, -104.9903), ("Los Angeles", 34.0522, -118.2437)]
# Major alert types, most serious first. Everything else (advisories, statements, routine watches) is left out.
MAJOR = ["Tsunami Warning", "Tornado Warning", "Extreme Wind Warning", "Hurricane Warning", "Storm Surge Warning", "Typhoon Warning",
         "Flash Flood Warning", "Blizzard Warning", "Ice Storm Warning", "Hurricane Watch", "Tropical Storm Warning", "Winter Storm Warning",
         "Extreme Heat Warning", "Excessive Heat Warning", "Extreme Cold Warning", "Tornado Watch", "Storm Surge Watch", "Tropical Storm Watch",
         "Winter Storm Watch", "Blizzard Watch", "High Wind Warning", "Fire Weather Watch"]
NATIONAL_MAJOR = set(MAJOR[:15])          # the national list keeps only the big ones
RED_EVENTS = {"Tsunami Warning", "Tornado Warning", "Extreme Wind Warning", "Hurricane Warning", "Storm Surge Warning", "Typhoon Warning"}
TIMEOUT = 8
_C = {}; _LK = threading.Lock()

def _on(c=None):
    if os.environ.get("BN_NL_WEATHER", "").strip() == "0": return False
    return (c or {}).get("weather_section", True) is not False

def _get(url, accept="application/geo+json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read(15_000_000).decode("utf-8", "replace"))

def _cached(key, ttl, fn):
    with _LK:
        hit = _C.get(key)
        if hit and time.time() - hit[0] < ttl: return hit[1]
    try: val = fn()
    except Exception:
        with _LK: hit = _C.get(key)
        if hit and time.time() - hit[0] < 6 * 3600: return hit[1]   # stale but recent beats nothing
        return None
    if val is not None:
        with _LK:
            _C[key] = (time.time(), val)
            if len(_C) > 300:
                for k, _ in sorted(_C.items(), key=lambda kv: kv[1][0])[:80]: _C.pop(k, None)
    return val

def _pt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _et_str(s, tz_label="ET"):
    d = _pt(s)
    if not d: return ""
    try:
        from zoneinfo import ZoneInfo
        d = d.astimezone(ZoneInfo("America/New_York"))
    except Exception: pass
    return d.strftime("%a %-I:%M %p").replace(":00 ", " ") + " " + tz_label

def _first_sentences(t, n=200):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if len(t) <= n: return t
    parts = re.split(r"(?<=\.)\s", t); out = ""
    for p in parts:
        if len(out) + len(p) + 1 > n: break
        out = (out + " " + p).strip()
    return out or t[:n].rsplit(" ", 1)[0] + "."

# ---------------------------------------------------------------- NWS forecast
def _nws_points(lat, lon):
    def go():
        P = (_get(f"{NWS}/points/{lat:.4f},{lon:.4f}").get("properties") or {})
        if not P.get("forecast"): return None
        return {"forecast": P["forecast"], "tz": P.get("timeZone")}
    return _cached(("pts", round(lat, 3), round(lon, 3)), 7 * 86400, go)

def _nws_days(lat, lon, n=4):
    pts = _nws_points(lat, lon)
    if not pts: return None
    def go():
        per = (_get(pts["forecast"]).get("properties") or {}).get("periods") or []
        if not per: return None
        days, cur = [], None
        for p in per:
            t = p.get("temperature")
            if p.get("isDaytime"):
                cur = {"name": "Today" if not days else (p.get("name") or "")[:3], "hi": t, "lo": None, "pop": (p.get("probabilityOfPrecipitation") or {}).get("value"),
                       "text": p.get("shortForecast") or ""}
                days.append(cur)
            else:
                if cur is None:   # forecast starts at night: tonight first
                    cur = {"name": "Tonight", "hi": None, "lo": t, "pop": (p.get("probabilityOfPrecipitation") or {}).get("value"), "text": p.get("shortForecast") or ""}
                    days.append(cur)
                else:
                    cur["lo"] = t
                    pp = (p.get("probabilityOfPrecipitation") or {}).get("value")
                    if pp is not None: cur["pop"] = max(cur["pop"] or 0, pp)
                cur = None if cur.get("lo") is not None else cur
        return {"days": days[:n], "detail": _first_sentences(per[0].get("detailedForecast"), 220), "detail_name": per[0].get("name") or "", "unit": "F",
                "src": "National Weather Service", "url": f"https://forecast.weather.gov/MapClick.php?lat={lat:.4f}&lon={lon:.4f}"}
    return _cached(("fc", round(lat, 3), round(lon, 3)), 3600, go)

_WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 61: "Light rain",
        63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow",
        80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers", 95: "Thunderstorms", 96: "Thunderstorms", 99: "Thunderstorms"}

def _intl_days(lat, lon, n=4):
    """Outside the US: Open-Meteo (shared budget, may be skipped) then NOAA GFS."""
    def go():
        import weather as W
        d, src_, url = None, None, None
        try:
            om = W.open_meteo(lat, lon)
            if om.get("ok"): d, src_, url = (om.get("data") or {}).get("daily"), "Open-Meteo", "https://open-meteo.com/"
        except Exception: d = None
        if not d:
            try:
                g = W.fallback_gfs(lat, lon)
                if g: d, src_, url = g.get("daily"), "NOAA GFS model", "https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast"
            except Exception: d = None
        if not d or not d.get("time"): return None
        days = []
        for i, t in enumerate(d["time"][:n]):
            g = lambda k: (d.get(k) or [None] * 9)[i] if i < len(d.get(k) or []) else None
            hi, lo = g("temperature_2m_max"), g("temperature_2m_min")
            code = g("weather_code")
            days.append({"name": "Today" if i == 0 else datetime.strptime(t[:10], "%Y-%m-%d").strftime("%a"), "hi": None if hi is None else round(hi),
                         "lo": None if lo is None else round(lo), "pop": g("precipitation_probability_max"), "text": _WMO.get(code, "") if isinstance(code, int) else ""})
        if not any(x["hi"] is not None for x in days): return None
        return {"days": days, "detail": "", "unit": "C", "src": src_, "url": url}
    return _cached(("intl", round(lat, 2), round(lon, 2)), 3 * 3600, go)

# ---------------------------------------------------------------- alerts
def _alert(p, url=None):
    return {"event": p.get("event") or "", "area": p.get("areaDesc") or "", "until": p.get("ends") or p.get("expires"), "severity": p.get("severity") or "",
            "headline": p.get("headline") or "", "url": url, "red": (p.get("event") or "") in RED_EVENTS or p.get("severity") == "Extreme"}

def _local_alerts(lat, lon):
    def go():
        out = []
        for f in _get(f"{NWS}/alerts/active?status=actual&point={lat:.4f},{lon:.4f}").get("features") or []:
            p = f.get("properties") or {}
            if p.get("messageType") == "Cancel" or p.get("severity") in ("Minor", "Unknown"): continue
            if p.get("event") not in MAJOR and p.get("severity") not in ("Extreme", "Severe"): continue
            out.append(_alert(p, f"https://forecast.weather.gov/MapClick.php?lat={lat:.4f}&lon={lon:.4f}"))
        rank = {e: i for i, e in enumerate(MAJOR)}
        seen, uniq = set(), []
        for a in sorted(out, key=lambda a: (rank.get(a["event"], 99), a["until"] or "")):
            if a["event"] in seen: continue
            seen.add(a["event"]); uniq.append(a)
        return uniq[:3]
    return _cached(("la", round(lat, 3), round(lon, 3)), 900, go)

_ST = re.compile(r",\s*([A-Z]{2})\b")
def _national_alerts():
    def go():
        feats = _get(f"{NWS}/alerts/active?status=actual&message_type=alert,update&severity=Extreme,Severe").get("features") or []
        G = {}
        for f in feats:
            p = f.get("properties") or {}; ev = p.get("event") or ""
            if ev not in NATIONAL_MAJOR: continue
            g = G.setdefault(ev, {"event": ev, "n": 0, "states": set(), "until": None, "red": ev in RED_EVENTS})
            g["n"] += 1; g["states"].update(_ST.findall(p.get("areaDesc") or ""))
            u = p.get("ends") or p.get("expires")
            if u and (g["until"] is None or u > g["until"]): g["until"] = u
        rank = {e: i for i, e in enumerate(MAJOR)}
        out = sorted(G.values(), key=lambda g: rank.get(g["event"], 99))[:4]
        for g in out: g["states"] = sorted(g["states"])
        return out
    return _cached(("na",), 900, go)

def _storms():
    def go():
        S = _get(NHC_JSON, "application/json").get("activeStorms") or []
        kind = {"HU": "Hurricane", "TS": "Tropical Storm", "TD": "Tropical Depression", "STS": "Subtropical Storm", "STD": "Subtropical Depression", "PTC": "Potential Tropical Cyclone"}
        out = []
        for s in S[:4]:
            k = kind.get(str(s.get("classification") or "").upper(), "Tropical cyclone")
            try: mph = round(int(s.get("intensity")) * 1.15078 / 5) * 5
            except Exception: mph = None
            out.append({"name": f"{k} {s.get('name') or ''}".strip(), "mph": mph, "url": ((s.get("publicAdvisory") or {}).get("url")) or NHC_PAGE})
        return out
    return _cached(("nhc",), 1800, go)

# ---------------------------------------------------------------- national forecast
def _cities():
    with ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(_nws_days, la, lo, 1): name for name, la, lo in CITIES}
        done, _ = wait(futs, timeout=TIMEOUT * 2 + 2)
        out = []
        for name, la, lo in CITIES:
            f = next((k for k, v in futs.items() if v == name), None)
            r = f.result() if f in done else None
            if r and r.get("days"):
                d = r["days"][0]; out.append({"name": name, "hi": d.get("hi"), "lo": d.get("lo"), "text": d.get("text") or "", "url": r["url"]})
        return out

# ---------------------------------------------------------------- entry point
def for_sub(sub, c=None):
    """-> {"scope","label","fc"|None,"cities"|None,"alerts","nat_alerts","storms","unit"} or None (nothing usable)."""
    if not _on(c): return None
    try:
        sub = dict(sub or {})
        lat, lon = sub.get("loc_lat"), sub.get("loc_lon")
        cc = str(sub.get("loc_cc") or "").upper()
        label = str(sub.get("loc_label") or "").strip()
        out = {"scope": "national", "label": "United States", "fc": None, "cities": None, "alerts": [], "nat_alerts": [], "storms": []}
        with ThreadPoolExecutor(4) as ex:
            if lat is not None and lon is not None and label:
                lat, lon = float(lat), float(lon)
                us = cc in US_LIKE if cc else (18 <= lat <= 72 and -180 <= lon <= -64)
                out.update(scope="local", label=label)
                f_fc = ex.submit(_nws_days, lat, lon) if us else ex.submit(_intl_days, lat, lon)
                f_al = ex.submit(_local_alerts, lat, lon) if us else None
                f_na = ex.submit(_national_alerts) if us else None
                f_ct = None
            else:
                f_fc = None; f_al = None
                f_na = ex.submit(_national_alerts); f_ct = ex.submit(_cities)
            f_st = ex.submit(_storms)
            res = lambda f: (f.result(timeout=TIMEOUT * 3) if f else None)
            for key, f in (("fc", f_fc), ("alerts", f_al), ("nat_alerts", f_na), ("cities", f_ct), ("storms", f_st)):
                try: v = res(f)
                except Exception: v = None
                if v is not None: out[key] = v
                if key in ("alerts", "nat_alerts") and f is not None: out[key + "_ok"] = v is not None
        out["alerts"] = out["alerts"] or []; out["nat_alerts"] = out["nat_alerts"] or []; out["storms"] = out["storms"] or []
        # local reader: national list only for events not already listed locally
        have = {a["event"] for a in out["alerts"]}
        out["nat_alerts"] = [g for g in out["nat_alerts"] if g["event"] not in have]
        if out["fc"] and not out["fc"].get("days"): out["fc"] = None
        if not out["fc"] and not out["cities"] and not out["alerts"] and not out["nat_alerts"] and not out["storms"]: return None
        return out
    except Exception:
        return None

def has_forecast(w): return bool(w and (w.get("fc") or w.get("cities")))
def has_alerts(w): return bool(w and (w.get("alerts") or w.get("nat_alerts") or w.get("storms")))
def alerts_quiet(w):
    """No major alerts, and the alert feeds actually answered (a failed feed never claims 'all quiet')."""
    return bool(w) and not has_alerts(w) and bool(w.get("alerts_ok") or w.get("nat_alerts_ok")) and (w.get("scope") == "national" or w.get("alerts_ok"))
def quiet_text(w):
    return ("No major weather warnings for your area right now." if w.get("scope") == "local" else "No major weather warnings in the US right now.")
def temps(d):
    if d.get("hi") is None and d.get("lo") is not None: return f"low {deg(d['lo'])}"
    if d.get("lo") is None and d.get("hi") is not None: return f"high {deg(d['hi'])}"
    return f"{deg(d.get('hi'))} / {deg(d.get('lo'))}"

def deg(v, unit="F"):
    return "–" if v is None else f"{int(round(v))}°"

def alert_meta(a):
    bits = []
    if a.get("until"): bits.append("until " + _et_str(a["until"]))
    return " · ".join(bits)

def nat_line(g):
    st = g.get("states") or []
    where = (", ".join(st[:6]) + (f" +{len(st) - 6} more" if len(st) > 6 else "")) if st else ""
    n = g.get("n") or 0
    return f"{n} active" + (f" in {where}" if where else "") + (f", until {_et_str(g['until'])}" if g.get("until") else "")

def text_lines(w):
    """Plain-text part."""
    if not w: return []
    T = []
    if has_forecast(w):
        if w.get("fc"):
            fc = w["fc"]; T += [f"WEATHER · {w['label'].upper()}"]
            for d in fc["days"]:
                T.append(f"- {d['name']}: {temps(d)}" + (f", {d['pop']}% rain" if d.get("pop") else "") + (f", {d['text']}" if d.get("text") else ""))
            if fc.get("detail"): T.append(f"{fc.get('detail_name') or 'Now'}: {fc['detail']}")
            T += [f"Forecast: {fc['src']} {fc['url']}", ""]
        else:
            T += ["WEATHER · ACROSS THE US"]
            for x in w["cities"]: T.append(f"- {x['name']}: {temps(x)}, {x['text']}")
            T += ["Forecasts: National Weather Service https://www.weather.gov/", ""]
    if has_alerts(w):
        T += ["MAJOR WEATHER ALERTS"]
        for a in w["alerts"]: T.append(f"- {a['event']} for your area" + (f" ({alert_meta(a)})" if alert_meta(a) else "") + f" {a['url']}")
        for g in w["nat_alerts"]: T.append(f"- {g['event']}: {nat_line(g)}")
        for s in w["storms"]: T.append(f"- {s['name']}" + (f", {s['mph']} mph winds" if s.get("mph") else "") + f" {s['url']}")
        T += [f"All active alerts: National Weather Service {NWS_ALERTS_PAGE}" + (f" · National Hurricane Center {NHC_PAGE}" if w["storms"] else ""), ""]
    elif alerts_quiet(w):
        T += ["MAJOR WEATHER ALERTS", quiet_text(w) + f" Source: National Weather Service {NWS_ALERTS_PAGE}", ""]
    return T
