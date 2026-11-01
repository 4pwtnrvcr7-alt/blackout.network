"""U.S. Energy Grid status add-on for blackout.network (t234). Extends the ⚡ U.S. Energy Grid tab (#grid, gridwatch.py + tabfeeds.py, which
lists scored scanner grid threats and the CISA / SWPC / ERCOT feeds) with three status panels, served under /api/gridstatus:
Three parts, all from free public data (no API keys), nothing generated:
 1. Grid sections map: the U.S. split into grid-operator sections (CAISO, ERCOT, ISO-NE, MISO, NYISO, PJM, SPP, Southeast non-ISO, West non-ISO,
    Alaska, Hawaii; boundaries from CommonGrid, ODbL, derived from EIA/HIFLD). Each section is colored online / watch / degraded / offline / no data
    by blackout.network from: EIA-930 hourly demand vs EIA day-ahead forecast and vs the same hour yesterday (www.eia.gov/electricity/930-api,
    keyless), DOE/ORNL ODIN utility outage reports (odin.ornl.gov/odi/status), NWS active Severe/Extreme alerts (api.weather.gov),
    NOAA SWPC geomagnetic scale and scanner grid alerts. It is a derived status, not an official operator status; every input shows its age.
 2. Local outage view: per state (all 50 + DC) the ODIN utilities reporting outages, NWS warnings with their county lists, the state's largest
    utilities with links to their own outage maps (street-level detail lives there), FEMA open shelters and unconfirmed social reports the
    scanner already collected. No outage polygons are drawn: ODIN publishes polygons only to signed-in partners.
 3. Weather-triggered infrastructure check: every scanner natural-disaster alert ranked 5+ (4+ in the U.S.) in the last 72 h, anywhere in the
    world, gets an automatic check: nearby scanner reports on power, water, telecom, roads, police, rescue and evacuations; for U.S. points the NWS
    alerts at that point, the grid section status, ODIN outages and FEMA open shelters; and official resource links (GDACS, ReliefWeb, FEMA,
    Ready.gov, Red Cross, 211, emergency numbers).
The threat list itself stays in gridwatch.py; a scanner grid alert ranked 5+ inside a section only nudges that section's status here.
Box: `python3 gridstatus.py loop` (run_gridstatus.sh) writes only gridstatus.db; the public node (BN_WEB_ONLY=1) reads the synced copy. Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py,
config.json or blackout.db writes."""
import os, re, sys, json, time, math, sqlite3, threading, gzip, html, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
GDB = os.path.join(BASE, "gridstatus.db")
STATIC = os.path.join(BASE, "gridstatus_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css", "sections.geojson": "application/geo+json", "utilities.json": "application/json"}
WEB_ONLY = os.environ.get("BN_WEB_ONLY") == "1"
UA = "Mozilla/5.0 (compatible; blackout.network research monitor; hello@blackout.network)"
NWS_UA = "blackout.network research monitor (hello@blackout.network)"
LIST = {0: "wire", 1: "watchlist", 2: "suppressed"}
TTL = 60

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
          "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
          "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
          "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
          "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
          "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
# Sections. eia = EIA-930 respondents summed for the section's demand line. states = the states mostly inside the section (one section per state,
# used to route state-level inputs: ODIN utilities without a BA code, NWS alerts, shelters). Many states are split between operators; the
# drill-down always lists the whole state.
SECTIONS = {
    "CAISO": {"name": "California ISO", "eia": ["CISO"], "states": ["CA"], "site": "https://www.caiso.com/todays-outlook"},
    "ERCOT": {"name": "ERCOT (Texas)", "eia": ["ERCO"], "states": ["TX"], "site": "https://www.ercot.com/gridmktinfo/dashboards"},
    "ISO-NE": {"name": "ISO New England", "eia": ["ISNE"], "states": ["CT", "MA", "ME", "NH", "RI", "VT"], "site": "https://www.iso-ne.com/isoexpress/"},
    "NYISO": {"name": "New York ISO", "eia": ["NYIS"], "states": ["NY"], "site": "https://www.nyiso.com/real-time-dashboard"},
    "PJM": {"name": "PJM Interconnection", "eia": ["PJM"], "states": ["PA", "NJ", "MD", "DE", "DC", "VA", "WV", "OH"], "site": "https://www.pjm.com/markets-and-operations"},
    "MISO": {"name": "Midcontinent ISO", "eia": ["MISO"], "states": ["MN", "WI", "MI", "IA", "IL", "IN", "MO", "AR", "LA", "MS", "ND"], "site": "https://www.misoenergy.org/markets-and-operations/real-time--market-data/"},
    "SPP": {"name": "Southwest Power Pool", "eia": ["SWPP"], "states": ["KS", "OK", "NE", "SD"], "site": "https://www.spp.org/markets-operations/"},
    "SE": {"name": "Southeast (non-ISO utilities)", "eia": ["SE", "FLA", "CAR", "TEN"], "states": ["AL", "GA", "FL", "SC", "NC", "TN", "KY"], "site": "https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48"},
    "WEST": {"name": "West (non-ISO utilities)", "eia": ["NW", "SW"], "states": ["WA", "OR", "ID", "MT", "NV", "UT", "AZ", "NM", "CO", "WY"], "site": "https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48"},
    "AK": {"name": "Alaska (non-ISO)", "eia": [], "states": ["AK"], "site": None},
    "HI": {"name": "Hawaii (non-ISO)", "eia": [], "states": ["HI"], "site": None},
}
STATE_SEC = {st: k for k, v in SECTIONS.items() for st in v["states"]}
BA_SEC = {"CISO": "CAISO", "ERCO": "ERCOT", "ISNE": "ISO-NE", "NYIS": "NYISO", "PJM": "PJM", "MISO": "MISO", "SWPP": "SPP", "SPA": "SPP"}
EIA_RESP = sorted({r for v in SECTIONS.values() for r in v["eia"]} | {"US48"})
POWER_EVENTS = re.compile(r"Hurricane|Tropical Storm|Typhoon|Tornado|Ice Storm|Winter Storm|Blizzard|High Wind|Extreme Wind|Excessive Heat|Extreme Heat|"
                          r"Red Flag|Fire Weather|Severe Thunderstorm|Derecho|Storm Surge|Extreme Cold|Wind Chill Warning|Flash Flood|Dust Storm|Avalanche|Tsunami|Fire Warning", re.I)
BIG_EVENTS = re.compile(r"Hurricane Warning|Typhoon Warning|Ice Storm Warning|Blizzard Warning|Extreme Wind Warning|Storm Surge Warning|Tsunami Warning|Tornado Emergency|Extreme Heat Warning", re.I)

def now(): return datetime.now(timezone.utc)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(m): print(time.strftime("[%Y-%m-%d %H:%M:%S] "), m, flush=True)
def http(url, timeout=40, ua=UA, accept="application/json", limit=30_000_000):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua, "Accept": accept, "Accept-Encoding": "gzip"}), timeout=timeout)
    b = r.read(limit)
    return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
def getjson(url, **kw): return json.loads(http(url, **kw))

# ---------------------------------------------------------------- geometry
_GEO = None
def sections_geo():
    global _GEO
    if _GEO is None:
        _GEO = json.load(open(os.path.join(STATIC, "sections.geojson")))
    return _GEO
def _inring(x, y, ring):
    ins = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi: ins = not ins
        j = i
    return ins
def section_at(lat, lon):
    if lat is None or lon is None: return None
    for f in sections_geo()["features"]:
        for poly in f["geometry"]["coordinates"]:
            if poly and _inring(lon, lat, poly[0]) and not any(_inring(lon, lat, h) for h in poly[1:]): return f["properties"]["id"]
    return None
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

# ---------------------------------------------------------------- storage
SCHEMA = """CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS history(ts TEXT, section TEXT, status TEXT, demand REAL, forecast REAL, PRIMARY KEY(ts, section));
CREATE TABLE IF NOT EXISTS geocache(k TEXT PRIMARY KEY, v TEXT, ts TEXT);"""
def gdb(ro=False):
    if ro: c = sqlite3.connect(f"file:{GDB}?mode=ro", uri=True, timeout=10)
    else: c = sqlite3.connect(GDB, timeout=30); c.executescript(SCHEMA)
    c.row_factory = sqlite3.Row; return c
def sput(c, k, v): c.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (k, json.dumps(v), iso())); c.commit()
def sget(c, k, d=None):
    r = c.execute("SELECT v, ts FROM state WHERE k=?", (k,)).fetchone()
    return (json.loads(r[0]), r[1]) if r else (d, None)

# ---------------------------------------------------------------- collectors
def fetch_eia():
    end = now() + timedelta(hours=2); start = now() - timedelta(hours=40)
    f = lambda d: d.strftime("%m%d%Y %H:00:00")
    q = [("type[0]", "D"), ("type[1]", "DF"), ("type[2]", "NG")] + [(f"respondent[{i}]", r) for i, r in enumerate(EIA_RESP)] + \
        [("frequency", "hourly"), ("timezone", "UTC"), ("limit", "10000"), ("offset", "0"), ("start", f(start)), ("end", f(end))]
    j = getjson("https://www.eia.gov/electricity/930-api/region_data/series_data?" + urllib.parse.urlencode(q))
    out = {}
    for blk in j:
        for s in blk.get("data", []):
            dates = s["VALUES"]["DATES"]; vals = s["VALUES"]["DATA"]
            ser = {}
            for d, v in zip(dates, vals):
                if v is None: continue
                t = datetime.strptime(d, "%m/%d/%Y %H:%M:%S").replace(tzinfo=timezone.utc)
                ser[iso(t)] = float(v)
            out.setdefault(s["RESPONDENT_ID"], {})[s["TYPE_ID"]] = ser
    return out
def fetch_odin():
    return getjson("https://odin.ornl.gov/odi/status", timeout=40)
def fetch_nws():
    j = getjson("https://api.weather.gov/alerts/active?status=actual&severity=Extreme,Severe", ua=NWS_UA, accept="application/geo+json", timeout=60)
    out = []
    for f in j.get("features", []):
        p = f.get("properties", {})
        ugc = (p.get("geocode") or {}).get("UGC") or []
        sts = sorted({u[:2] for u in ugc if u[:2] in STATES})
        if not sts: continue
        out.append({"id": p.get("id"), "url": p.get("@id") or f.get("id"), "event": p.get("event"), "severity": p.get("severity"), "urgency": p.get("urgency"),
                    "headline": (p.get("headline") or "")[:220], "area": (p.get("areaDesc") or "")[:400], "sent": p.get("sent"), "expires": p.get("expires") or p.get("ends"),
                    "sender": p.get("senderName"), "states": sts, "power": bool(POWER_EVENTS.search(p.get("event") or "")),
                    "big": bool(BIG_EVENTS.search(p.get("event") or ""))})
    return out
def fetch_swpc():
    j = getjson("https://services.swpc.noaa.gov/products/noaa-scales.json", timeout=30)
    cur = j.get("0") or {}
    g = cur.get("G") or {}; r = cur.get("R") or {}; s = cur.get("S") or {}
    fc = [{"date": (j.get(k) or {}).get("DateStamp"), "g": ((j.get(k) or {}).get("G") or {}).get("Scale")} for k in ("1", "2", "3")]
    return {"time": f'{cur.get("DateStamp")}T{cur.get("TimeStamp")}Z' if cur.get("DateStamp") else None, "g": int(g.get("Scale") or 0), "g_text": g.get("Text"),
            "r": int(r.get("Scale") or 0), "s": int(s.get("Scale") or 0), "forecast": fc, "url": "https://www.swpc.noaa.gov/noaa-scales-explanation"}
def fetch_shelters():
    j = getjson("https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/MapServer/0/query?" + urllib.parse.urlencode(
        {"where": "1=1", "outFields": "shelter_name,address,city,state,zip,shelter_status,org_name,evacuation_capacity,total_population,pet_accommodations_code,ada_compliant",
         "returnGeometry": "true", "outSR": "4326", "f": "json", "resultRecordCount": "2000"}), timeout=40)
    out = []
    for f in j.get("features", []):
        a = f.get("attributes", {}); g = f.get("geometry") or {}
        out.append({"name": a.get("shelter_name"), "address": a.get("address"), "city": a.get("city"), "state": a.get("state"), "zip": a.get("zip"),
                    "status": a.get("shelter_status"), "org": a.get("org_name"), "capacity": a.get("evacuation_capacity"), "population": a.get("total_population"),
                    "pets": a.get("pet_accommodations_code"), "ada": a.get("ada_compliant"), "lat": g.get("y"), "lon": g.get("x")})
    return out

# ---------------------------------------------------------------- section status
def _sum_series(eia, resps, typ):
    tot = {}
    for r in resps:
        ser = (eia.get(r) or {}).get(typ) or {}
        for t, v in ser.items(): tot.setdefault(t, [0.0, 0]); tot[t][0] += v; tot[t][1] += 1
    return {t: v for t, (v, n) in tot.items() if n == len(resps)}
def compute_sections(eia, odin, nws, swpc, util_map, grid_alerts):
    res = {}; nowt = now()
    # ODIN per section
    odin_sec = {}
    for u in odin or []:
        meta = util_map.get(str(u.get("eiaId"))) or {}
        sec = BA_SEC.get(meta.get("ba") or "") or next((STATE_SEC.get(s) for s in meta.get("st", []) if STATE_SEC.get(s)), None)
        if not sec: continue
        d = odin_sec.setdefault(sec, {"utilities": 0, "reporting_outages": 0, "outages": 0, "latest": None})
        d["utilities"] += 1; n = int(u.get("totalOutages") or 0); d["outages"] += n; d["reporting_outages"] += 1 if n else 0
        d["latest"] = max(d["latest"] or "", u.get("receivedDate") or "")
    for k, sec in SECTIONS.items():
        reasons, level = [], 0   # 0 online, 1 watch, 2 degraded, 3 offline ; -1 no data
        info = {"id": k, "name": sec["name"], "states": sec["states"], "site": sec["site"], "eia_respondents": sec["eia"]}
        if sec["eia"]:
            D = _sum_series(eia, sec["eia"], "D"); DF = _sum_series(eia, sec["eia"], "DF"); NG = _sum_series(eia, sec["eia"], "NG")
            hrs = sorted(D)
            if hrs:
                last = hrs[-1]; lt = datetime.fromisoformat(last.replace("Z", "+00:00")); age_h = (nowt - lt).total_seconds() / 3600
                d = D[last]; fc = DF.get(last); y = D.get(iso(lt - timedelta(days=1)))
                info.update({"eia_hour": last, "eia_age_h": round(age_h, 1), "demand_mw": round(d), "forecast_mw": round(fc) if fc else None,
                             "yesterday_mw": round(y) if y else None, "generation_mw": round(NG[last]) if NG.get(last) else None,
                             "series": [[t, round(D[t]), round(DF[t]) if DF.get(t) else None] for t in hrs[-36:]]})
                vf = (d - fc) / fc * 100 if fc else None; vy = (d - y) / y * 100 if y else None
                info["vs_forecast_pct"] = round(vf, 1) if vf is not None else None; info["vs_yesterday_pct"] = round(vy, 1) if vy is not None else None
                if d <= 0 or (vy is not None and vy <= -50): level = max(level, 3); reasons.append(f"Reported demand collapsed ({vy:+.0f}% vs the same hour yesterday)" if vy is not None else "Reported demand is zero")
                elif vf is not None and vf <= -15 and vy is not None and vy <= -15: level = max(level, 2); reasons.append(f"Demand {vf:+.0f}% vs forecast and {vy:+.0f}% vs yesterday: possible load loss")
                elif vf is not None and vf <= -8 and vy is not None and vy <= -8: level = max(level, 1); reasons.append(f"Demand {vf:+.0f}% vs forecast and {vy:+.0f}% vs yesterday")
                if age_h > 6: level = max(level, 1); reasons.append(f"EIA-930 data is {age_h:.0f} h old")
            else:
                info["eia_hour"] = None; level = -1; reasons.append("No EIA-930 hourly data returned")
        else:
            info["eia_hour"] = None; info["no_eia"] = "EIA-930 covers the Lower 48 only"
        od = odin_sec.get(k)
        info["odin"] = od
        if od and od["outages"] >= 5000: level = max(level, 2); reasons.append(f"{od['outages']:,} outages reported to ODIN by {od['reporting_outages']} utilities")
        elif od and od["outages"] >= 1500: level = max(level, 1); reasons.append(f"{od['outages']:,} outages reported to ODIN")
        al = [a for a in nws or [] if a["power"] and any(STATE_SEC.get(s) == k for s in a["states"])]
        big = [a for a in al if a["big"] or a["severity"] == "Extreme"]
        warn = [a for a in al if "Warning" in (a["event"] or "")]
        info["nws"] = {"power_alerts": len(al), "extreme": len(big), "warnings": len(warn), "events": sorted({a["event"] for a in al})[:8]}
        if big: level = max(level, 2); reasons.append(f"{len(big)} extreme NWS alert(s): " + ", ".join(sorted({a['event'] for a in big})[:3]))
        elif len(warn) >= 5: level = max(level, 1); reasons.append(f"{len(warn)} power-relevant NWS warnings")
        ga = [g for g in grid_alerts if g.get("section") == k]
        info["scanner"] = {"alerts_12h": len(ga), "max_rank": max((g["rank"] or 0 for g in ga), default=None)}
        if any((g["rank"] or 0) >= 6 and not g["unconfirmed"] for g in ga): level = max(level, 2); reasons.append("Confirmed scanner grid alert ranked 6+ in the last 12 h")
        elif any((g["rank"] or 0) >= 5 for g in ga): level = max(level, 1); reasons.append("Scanner grid alert ranked 5+ in the last 12 h")
        if swpc and swpc.get("g", 0) >= 4: level = max(level, 2); reasons.append(f"NOAA G{swpc['g']} geomagnetic storm in progress")
        elif swpc and swpc.get("g", 0) == 3: level = max(level, 1); reasons.append("NOAA G3 geomagnetic storm in progress")
        if level == -1 and not reasons[1:]: status = "nodata"
        else: status = ["online", "watch", "degraded", "offline"][max(level, 0)]
        if not sec["eia"] and level <= 0 and not reasons: status = "nodata_ok"
        info["status"] = status; info["reasons"] = reasons
        res[k] = info
    return res

# ---------------------------------------------------------------- scanner classifiers (read-only blackout.db)
GRID_RX = re.compile(r"\b(?:power grids?|electric(?:al|ity)? grids?|the grid|grid (?:operator|emergency|failure|collapse|attack|stress|reliability|outage)s?|substations?|"
                     r"transformers? (?:fire|explosion|blew|blown|failure)|transmission (?:lines?|towers?)|power lines?|high[- ]voltage|power outages?|outages? (?:hit|affect|leave|left)|"
                     r"without (?:power|electricity)|lost power|power (?:is )?(?:out|restored|cut)|blackouts?|brownouts?|rolling (?:blackouts|outages)|load[- ]shed\w*|"
                     r"power plants?|nuclear (?:power )?plants?|reactors?|electric (?:utility|utilities|cooperative|co-?op)s?|power utilit(?:y|ies)|"
                     r"NERC|FERC|ERCOT|PJM|CAISO|MISO|NYISO|ISO[- ]NE|ISO New England|Southwest Power Pool|Tennessee Valley Authority|TVA|Bonneville Power|"
                     r"Duke Energy|PG&E|Con ?Ed(?:ison)?|Dominion Energy|Entergy|Xcel Energy|Southern California Edison|Florida Power|CenterPoint|Oncor|"
                     r"Volt Typhoon|energy emergency alert|EEA ?[123]|SCADA|industrial control systems?|geomagnetic storms?|GIC)\b", re.I)
US_RX = re.compile(r"\b(?:U\.S\.A?|USA|United States|America|American|Americans|NERC|FERC|ERCOT|PJM|CAISO|MISO|NYISO|ISO New England|TVA|CISA|DOE|FBI|DHS|"
                   r"PG&E|Con ?Edison|Duke Energy|Entergy|Xcel|Oncor|CenterPoint|NYC|Los Angeles|Las Vegas|Chicago|Houston|Dallas|Austin|San Antonio|Phoenix|"
                   r"Atlanta|Miami|New Orleans|Seattle|Portland|Denver|Boston|Philadelphia|Detroit|Minneapolis|San Francisco|San Diego|San Jose|Puerto Rico|"
                   + "|".join(re.escape(v) for v in STATES.values()) + r")\b")
US_CS = re.compile(r"(?<![A-Za-z])US(?![A-Za-z])|,\s?(?:" + "|".join(STATES) + r")\b")
NON_US = re.compile(r"\b(?:Ukrain\w*|Kyiv|Kiev|Dnipro|Kharkiv|Odesa|Russia\w*|Moscow|Gaza|Israel\w*|Iran\w*|Pakistan\w*|India\w*|Cuba\w*|Venezuela\w*|South Africa\w*|"
                    r"Nigeria\w*|Lebanon|Syria\w*|Iraq\w*|Yemen\w*|Bangladesh|Philippines|Australia\w*|Brazil\w*|Mexico|Canada|Europe\w*|Spain|Portugal|Chile\w*|Ecuador|Kenya)\b")
GSUB = [("physical", "Physical attack / sabotage", re.compile(r"shoot|shot|gunfire|sabotag|vandal|arson|explosive|bomb|drone|attack(?:ed|s)? (?:on )?(?:a |the )?(?:power|substation|grid)|physical (?:attack|security)", re.I)),
        ("cyber", "Cyber threat", re.compile(r"cyber|hack|malware|ransomware|Volt Typhoon|SCADA|industrial control|ICS\b|CVE-|vulnerab|zero[- ]day|exploit", re.I)),
        ("space", "Space weather", re.compile(r"geomagnetic|solar storm|CME|coronal|GIC|K-index|Kp", re.I)),
        ("weather", "Weather / disaster", re.compile(r"storm|hurricane|tornado|wildfire|fire|ice|snow|heat|flood|wind|hail|earthquake|quake", re.I)),
        ("outage", "Outage / blackout", re.compile(r"outage|without power|lost power|blackout|brownout|load[- ]shed|power (?:is )?out", re.I)),
        ("reliability", "Reliability / grid emergency", re.compile(r".", re.I))]
GSUBS = {k: lab for k, lab, _ in GSUB}
_C = getattr(sys, "_bn_gridstatus_cache", None)
if _C is None: _C = sys._bn_gridstatus_cache = {}
_LK = getattr(sys, "_bn_gridstatus_lock", None)
if _LK is None: _LK = sys._bn_gridstatus_lock = threading.Lock()
def _j(s):
    try: return json.loads(s or "[]")
    except Exception: return []
def classify_grid(title, brief, category, lat, lon):
    t = f"{title or ''}\n{brief or ''}"; t = re.sub(r"blackout\.network", "", t, flags=re.I)
    if category in ("ufo/uap", "spiritual/religious"): return False, None, None
    m = GRID_RX.search(t)
    if not m: return False, None, None
    if re.search(r"#\s?power outage", t, re.I) and not US_RX.search(t): return False, None, None
    sec = section_at(lat, lon) if lat is not None else None
    if category == "space weather" or re.search(r"geomagnetic", m.group(0), re.I):
        if not re.search(r"\bG[1-5]\b|geomagnetic", t): return False, None, None
        return True, "space", sec
    us = bool(sec) or bool(US_RX.search(t)) or bool(US_CS.search(t))
    if not us: return False, None, None
    if NON_US.search(t[:400]) and not (sec or US_RX.search(t[:400]) or US_CS.search(t[:400])): return False, None, None
    sub = next(k for k, _, rx in GSUB if rx.search(t))
    return True, sub, sec
def grid_matches():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
    try:
        key = tuple(c.execute("SELECT (SELECT MAX(id) FROM scans), (SELECT MAX(updated) FROM clusters)").fetchone())
        with _LK:
            hit = _C.get("g")
            if hit and hit[0] == key and time.time() - hit[1] < TTL: return hit[2]
        out = []
        for r in c.execute("""SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated, score, confidence, n_items, n_families,
                                     families, links, watchlist, brief, rank FROM clusters ORDER BY first_seen DESC"""):
            ok, sub, sec = classify_grid(r["title"], r["brief"], r["category"], r["lat"], r["lon"])
            if not ok: continue
            d = dict(r); d["families"] = _j(d["families"])
            d["links"] = [{"source": l.get("source", ""), "url": l.get("url", "")} for l in _j(d["links"])[:6] if isinstance(l, dict) and l.get("url")]
            d["list"] = LIST.get(d["watchlist"], "suppressed"); d["unconfirmed"] = d["watchlist"] != 0
            d["sub"] = sub; d["sub_label"] = GSUBS[sub]; d["section"] = sec
            if d["brief"] and len(d["brief"]) > 600: d["brief"] = d["brief"][:600] + "…"
            out.append(d)
        with _LK: _C["g"] = (key, time.time(), out)
        return out
    finally: c.close()

# ---------------------------------------------------------------- weather-triggered infrastructure check
INFRA = [("power", "Power / utilities", re.compile(r"power outages?|without (?:power|electricity)|lost power|blackouts?|power lines?|substations?|electricity|grid|utility|utilities|power (?:cut|restored)", re.I)),
         ("water", "Water / sanitation", re.compile(r"water (?:supply|main|treatment|shortage|outage)|boil[- ]water|drinking water|sewage|dam\b|levee", re.I)),
         ("telecom", "Telecom / internet", re.compile(r"internet|mobile network|cell(?:ular)? (?:service|towers?)|telecom|phone lines?|communications? (?:down|outage|cut)|connectivity", re.I)),
         ("transport", "Roads / transport", re.compile(r"roads? (?:closed|blocked|washed)|highway|bridges?|airports?|flights? (?:cancel|suspend|ground)|ground stop|rail|train|port (?:closed|shut)|landslides?", re.I)),
         ("police", "Police / security", re.compile(r"police|curfew|looting|state of emergency|martial|national guard|army deployed|troops", re.I)),
         ("rescue", "Rescue / evacuation", re.compile(r"rescue[sd]?|rescuers|evacuat\w+|missing|trapped|search and rescue|firefighters|emergency (?:services|crews|teams)|coast guard|shelters?|displaced|relief", re.I)),
         ("health", "Hospitals / health", re.compile(r"hospitals?|clinics?|medical|casualt\w+|injured|deaths?|killed|dead\b", re.I))]
def _country(loc):
    if not loc: return None
    return loc.split(",")[-1].strip() if "," in loc else loc.strip()
def weather_events(nws, shelters, sections, odin_by_state):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
    cut = iso(now() - timedelta(hours=72))
    try:
        rows = [dict(r) for r in c.execute("""SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated, score, rank, confidence,
                                                n_items, n_families, links, watchlist FROM clusters WHERE category='natural disaster' AND updated>=? AND rank>=4
                                                ORDER BY rank DESC, updated DESC LIMIT 300""", (cut,))]
        near_pool = [dict(r) for r in c.execute("""SELECT cluster_id, title, category, location, lat, lon, first_seen, score, rank, watchlist, links, brief
                                                  FROM clusters WHERE updated>=?""", (cut,))]
    finally: c.close()
    evs, seen = [], set()
    for r in rows:
        if re.search(r"\bdrought\b", r["title"] or "", re.I): continue
        sec = section_at(r["lat"], r["lon"]) if r["lat"] is not None else None
        us = bool(sec)
        if (r["rank"] or 0) < 5 and not us: continue
        k = re.sub(r"[^a-z]+", " ", (r["title"] or "").lower())[:50]
        if k in seen: continue
        if r["lat"] is not None and any(e["lat"] is not None and hav(r["lat"], r["lon"], e["lat"], e["lon"]) < 150 for e in evs): continue
        seen.add(k)
        ev = {"cluster_id": r["cluster_id"], "title": (r["title"] or "").split("\n")[0][:220], "location": r["location"], "lat": r["lat"], "lon": r["lon"],
              "rank": r["rank"], "score": r["score"], "confidence": r["confidence"], "first_seen": r["first_seen"], "updated": r["updated"],
              "unconfirmed": r["watchlist"] != 0, "links": [{"source": l.get("source"), "url": l.get("url")} for l in _j(r["links"])[:4] if isinstance(l, dict) and l.get("url")],
              "us": us, "section": sec}
        # nearby scanner reports about infrastructure / safety (real items, with their own links)
        checks = {k2: [] for k2, _, _ in INFRA}
        names = {re.sub(r"-\d+$", "", n) for n in re.findall(r"(?i:cyclone|typhoon|hurricane|tropical storm|storm)\s+([A-Z][A-Za-z]+(?:-[A-Za-z]+)?(?:-\d+)?)", r["title"] or "")}
        names = {n for n in names if len(n) >= 4 and n.lower() not in ("category", "warning", "watch", "surge", "notification")}
        nrx = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b", re.I) if names else None
        cn0 = _country(r["location"]) if r["location"] and "," not in (r["location"] or "")[:60] else None
        crx = re.compile(r"\b" + re.escape(cn0) + r"\b") if cn0 and len(cn0) > 3 and not section_at(r["lat"], r["lon"]) else None
        for x in near_pool:
            if x["cluster_id"] == r["cluster_id"]: continue
            t = (x["title"] or "") + " " + (x["brief"] or "")
            if r["lat"] is not None and x["lat"] is not None: dkm = hav(r["lat"], r["lon"], x["lat"], x["lon"])
            else: dkm = None
            byname = bool(nrx and nrx.search(t)) or bool(crx and x["category"] == "natural disaster" and crx.search(t))
            if not ((dkm is not None and dkm <= 350) or byname): continue
            if True:
                for k2, _, rx in INFRA:
                    if rx.search(t) and len(checks[k2]) < 4:
                        lk = next((l for l in _j(x["links"]) if isinstance(l, dict) and l.get("url")), None)
                        checks[k2].append({"title": (x["title"] or "").split("\n")[0][:160], "km": round(dkm) if dkm is not None else None, "rank": x["rank"], "unconfirmed": x["watchlist"] != 0,
                                           "url": lk and lk.get("url"), "source": lk and lk.get("source"), "time": x["first_seen"]})
        # the event's own text often states impacts
        t0 = r["title"] or ""
        ev["own_impacts"] = [lab for k2, lab, rx in INFRA if rx.search(t0)]
        ev["checks"] = [{"key": k2, "label": lab, "items": checks[k2]} for k2, lab, _ in INFRA]
        res = []
        if us:
            st = None
            try: st = point_state(r["lat"], r["lon"])
            except Exception: st = None
            ev["state"] = st
            ev["section_status"] = (sections.get(sec) or {}).get("status")
            pt = [a for a in nws if st and st in a["states"]]
            ev["nws"] = [{"event": a["event"], "headline": a["headline"], "url": a["url"], "expires": a["expires"], "area": a["area"][:200]} for a in pt][:8]
            if st: ev["odin"] = odin_by_state.get(st, [])[:8]
            sh = [dict(s, km=round(hav(r["lat"], r["lon"], s["lat"], s["lon"]))) for s in shelters if s.get("lat") is not None]
            sh = [s for s in sh if s["km"] <= 250 or (st and s.get("state") == st)]
            ev["shelters"] = sorted(sh, key=lambda s: s["km"])[:8]
            res += [("FEMA open shelters (live map)", "https://www.fema.gov/disaster/current"), ("Red Cross: find an open shelter", "https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html"),
                    ("DisasterAssistance.gov (apply for aid)", "https://www.disasterassistance.gov/"), ("211: local help line (dial 2-1-1)", "https://www.211.org/"),
                    ("Ready.gov: power outages", "https://www.ready.gov/power-outages"), ("NWS forecast for this point", f"https://forecast.weather.gov/MapClick.php?lat={r['lat']:.3f}&lon={r['lon']:.3f}"),
                    ("Emergency: dial 9-1-1", "https://www.911.gov/")]
            if st: res.insert(0, (f"Power outage maps for {STATES.get(st, st)} utilities", f"#grid/state/{st}"))
        else:
            cn = _country(r["location"])
            ev["country"] = cn
            q = urllib.parse.quote(cn or (r["title"] or "")[:60])
            res += [("ReliefWeb: situation reports", f"https://reliefweb.int/updates?search={q}"), ("GDACS: global disaster alerts", "https://www.gdacs.org/"),
                    ("IODA: internet outages by country", "https://ioda.inetintel.cc.gatech.edu/"),
                    ("Emergency phone numbers by country", "https://en.wikipedia.org/wiki/List_of_emergency_telephone_numbers")]
        for l in ev["links"]:
            if "gdacs" in (l.get("url") or ""): res.insert(0, ("GDACS event report", l["url"]))
        ev["resources"] = [{"label": a, "url": b} for a, b in res]
        evs.append(ev)
        if len(evs) >= 15: break
    return evs
def point_state(lat, lon):
    k = f"{lat:.2f},{lon:.2f}"
    c = gdb()
    try:
        r = c.execute("SELECT v FROM geocache WHERE k=?", (k,)).fetchone()
        if r: return json.loads(r[0])
        if WEB_ONLY: return None
        st = None
        try:
            j = getjson(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", ua=NWS_UA, accept="application/geo+json", timeout=20)
            st = (((j.get("properties") or {}).get("relativeLocation") or {}).get("properties") or {}).get("state")
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
        c.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?)", (k, json.dumps(st), iso())); c.commit()
        return st
    finally: c.close()

# ---------------------------------------------------------------- cycle
def util_meta():
    try: return json.load(open(os.path.join(STATIC, "utilities.json")))
    except Exception: return {"by_state": {}, "odin_eia": {}}
def odin_by_state(odin, um):
    out = {}
    for u in odin or []:
        meta = um.get(str(u.get("eiaId"))) or {}
        for st in meta.get("st", []) or []:
            out.setdefault(st, []).append({"name": u.get("name"), "eia": u.get("eiaId"), "outages": int(u.get("totalOutages") or 0), "resolution": u.get("dataResolution"),
                                           "received": u.get("receivedDate"), "error": bool(u.get("hasError")), "web": meta.get("web"), "ba": meta.get("ba")})
    for st in out: out[st].sort(key=lambda x: -x["outages"])
    return out
def cycle():
    c = gdb(); stats = {}
    def run(name, fn, every_s):
        v, ts = sget(c, name)
        if ts and (now() - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() < every_s - 30 and v is not None: return v
        try:
            v = fn(); sput(c, name, v); stats[name] = "ok"; return v
        except Exception as e:
            stats[name] = "error: " + repr(e)[:160]; sput(c, name + "_error", {"error": repr(e)[:300]})
            return sget(c, name)[0]
    eia = run("eia", fetch_eia, 600) or {}
    odin = run("odin", fetch_odin, 600) or []
    nws = run("nws", fetch_nws, 300) or []
    swpc = run("swpc", fetch_swpc, 600) or {}
    shelters = run("shelters", fetch_shelters, 900) or []
    um = util_meta()["odin_eia"]
    cut = iso(now() - timedelta(hours=12))
    ga = [g for g in grid_matches() if (g["first_seen"] or "") >= cut]
    secs = compute_sections(eia, odin, nws, swpc, um, ga)
    sput(c, "sections", secs)
    obs = odin_by_state(odin, um); sput(c, "odin_by_state", obs)
    hr = iso(now().replace(minute=0, second=0, microsecond=0))
    for k, s in secs.items():
        c.execute("INSERT OR REPLACE INTO history VALUES(?,?,?,?,?)", (hr, k, s["status"], s.get("demand_mw"), s.get("forecast_mw")))
    c.execute("DELETE FROM history WHERE ts<?", (iso(now() - timedelta(days=14)),)); c.commit()
    try: sput(c, "weather", weather_events(nws, shelters, secs, obs)); stats["weather"] = "ok"
    except Exception as e: stats["weather"] = "error: " + repr(e)[:160]
    sput(c, "last_cycle", {"ts": iso(), "stats": stats}); c.close()
    return stats
def loop():
    if WEB_ONLY: return
    while True:
        t0 = time.time()
        try: log(json.dumps(cycle()))
        except Exception as e: log("cycle error: " + repr(e)[:300])
        time.sleep(max(120, 300 - (time.time() - t0)))

# ---------------------------------------------------------------- public API
def _age(ts):
    try: return round((now() - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60)
    except Exception: return None
def summary(qs):
    g = lambda k, d="": ((qs.get(k) or [d])[0] or d)
    try: c = gdb(ro=True)
    except Exception: c = None
    secs = sw = wx = last = None; fresh = {}
    if c:
        try:
            secs, ts = sget(c, "sections"); fresh["sections"] = ts
            for k in ("eia", "odin", "nws", "swpc", "shelters", "weather"):
                r = c.execute("SELECT ts FROM state WHERE k=?", (k,)).fetchone(); fresh[k] = r[0] if r else None
            sw, _ = sget(c, "swpc"); wx, _ = sget(c, "weather"); last, _ = sget(c, "last_cycle")
        except sqlite3.Error: pass
        finally: c.close()
    return 200, {"sections": secs, "freshness": {k: {"ts": v, "age_min": _age(v)} for k, v in fresh.items()}, "swpc": sw,
                 "weather": wx, "last_cycle": last, "generated": iso(),
                 "sources": [{"name": "EIA Hourly Electric Grid Monitor (EIA-930)", "url": "https://www.eia.gov/electricity/gridmonitor/"},
                             {"name": "DOE / ORNL ODIN outage data", "url": "https://odin.ornl.gov/"}, {"name": "NWS active alerts", "url": "https://www.weather.gov/"},
                             {"name": "NOAA SWPC space weather scales", "url": "https://www.swpc.noaa.gov/noaa-scales-explanation"},
                             {"name": "FEMA open shelters (NSS)", "url": "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/MapServer/0"},
                             {"name": "Grid operator boundaries: CommonGrid (ODbL), from EIA/HIFLD", "url": "https://commongrid.info/"}]}
SOCIAL_RX = re.compile(r"power (?:is )?out|power outages?|without power|no power|lost power|blackouts?|power cut|lights (?:are )?out|power (?:just )?went out", re.I)
def state_view(st):
    st = (st or "").upper()
    if st not in STATES: return 400, {"error": "unknown state"}
    um = util_meta()
    out = {"state": st, "name": STATES[st], "section": STATE_SEC.get(st), "utilities": um["by_state"].get(st, [])}
    try:
        c = gdb(ro=True)
        try:
            obs, ts = sget(c, "odin_by_state", {}); out["odin"] = (obs or {}).get(st, []); out["odin_ts"] = ts
            nws, ts2 = sget(c, "nws", []); out["nws"] = [a for a in nws or [] if st in a["states"]]; out["nws_ts"] = ts2
            sh, ts3 = sget(c, "shelters", []); out["shelters"] = [s for s in sh or [] if s.get("state") == st]; out["shelters_ts"] = ts3
            secs, _ = sget(c, "sections", {}); out["section_info"] = (secs or {}).get(STATE_SEC.get(st))
        finally: c.close()
    except Exception: out.update({"odin": [], "nws": [], "shelters": []})
    # unconfirmed social / news reports the scanner already holds (last 48 h) that mention a power outage and this state
    name = STATES[st]; srx = re.compile(r"\b" + re.escape(name) + r"\b|,\s?" + st + r"\b")
    rep = []
    try:
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
        try:
            for r in c.execute("SELECT title, source, family, source_url, first_seen, location FROM alerts WHERE first_seen>=? ORDER BY first_seen DESC LIMIT 20000",
                               (iso(now() - timedelta(hours=48)),)):
                t = (r["title"] or "") + " " + (r["location"] or "")
                if SOCIAL_RX.search(t) and srx.search(t) and re.match(r"^https?://", r["source_url"] or ""):
                    rep.append({"title": (r["title"] or "").split("\n")[0][:200], "source": r["source"], "url": r["source_url"], "time": r["first_seen"]})
                    if len(rep) >= 12: break
        finally: c.close()
    except sqlite3.Error: pass
    out["reports"] = rep
    return 200, out

def handle_get(path, qs):
    if path.startswith("/api/gridstatus/"):
        n = path[len("/api/gridstatus/"):]
        if n in FILES:
            with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
        if n == "state": return state_view((qs.get("st") or [""])[0])
        if n == "history":
            try:
                c = gdb(ro=True)
                try: rows = [dict(r) for r in c.execute("SELECT ts, section, status, demand, forecast FROM history ORDER BY ts")]
                finally: c.close()
            except Exception: rows = []
            return 200, {"history": rows}
        return 404, {"error": "not found"}
    if path == "/api/gridstatus":
        try: return summary(qs)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:200]}
    return 404, {"error": "not found"}

if __name__ == "__main__":
    a = sys.argv[1:] or ["once"]
    if a[0] == "loop": loop()
    elif a[0] == "once": print(json.dumps(cycle(), indent=1))
    elif a[0] == "scanner":
        for x in grid_matches(): print(x["rank"], x["sub"], x["section"], x["list"], "|", (x["title"] or "")[:110].replace("\n", " "))
