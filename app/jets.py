#!/usr/bin/env python3
"""Blackout Network - private/business jet tracker + takeoff spike detector (research/display only).

Jets are informational: nothing here reads or writes threat ranks/scores. This module writes ONLY to jets.db
and reads blackout.db read-only (to list coinciding threat clusters in spike alerts).

Source: adsb.lol open API (free, no key): /v2/type/<ICAO types, comma-separated>, /v2/ladd, /v2/pia.
Aircraft are deduplicated by ICAO 24-bit hex across all requests.
Run one pass by hand:  python3 jets.py   (prints a summary)
"""
import os, json, csv, math, sqlite3, time, statistics, re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests

BASE = "/workspace/blackout"
DB = f"{BASE}/jets.db"
THREAT_DB = f"{BASE}/blackout.db"
DATA = f"{BASE}/jetdata"
AIRPORTS_CSV = f"{DATA}/airports.csv"
AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "BlackoutNetwork-research/1.0 (personal, non-commercial; hourly-ish polling)"}
ADSBLOL = "https://api.adsb.lol/v2"
DEFAULTS = {"jet_spike_k": 2.0, "jet_spike_alerts_enabled": True, "jet_sample_minutes": 5}
K_MIN, K_MAX = 1.5, 4.0
MIN_BASELINE_HOURS = 24          # valid hours of history before any alert can fire
MIN_SAME_HOUR_SAMPLES = 2        # same UTC hour-of-day samples needed (=> ~48h of data) before alerts
MIN_HOW_SAMPLES = 3              # same hour-of-week samples (=> 3 weeks) before switching to hour-of-week baseline
DEDUP_DEPARTURE_H = 2

# ---- business jet ICAO type designators -> manufacturer -----------------------------------------------------
MFR = {
 "Gulfstream": "GLF2 GLF3 GLF4 GLF5 GLF6 GA5C GA6C GA7C GA8C G280 G150 GALX ASTR",
 "Bombardier Challenger/Global": "CL30 CL35 CL60 GLEX GL5T GL7T GL8T",
 "Learjet": "LJ23 LJ24 LJ25 LJ28 LJ31 LJ35 LJ36 LJ40 LJ45 LJ55 LJ60 LJ70 LJ75 LJ85",
 "Dassault Falcon": "F2TH F900 FA7X FA8X FA50 FA10 FA20 FA6X",
 "Cessna Citation": "C500 C501 C510 C525 C25A C25B C25C C25M C526 C550 C551 C55B C560 C56X C650 C680 C68A C700 C750",
 "Embraer business": "E50P E55P E545 E550 E35L",
 "Hawker/Beechcraft": "H25A H25B H25C HA4T BE40 PRM1 MU30",
 "Pilatus PC-24": "PC24",
 "HondaJet": "HDJT",
 "Other light jets": "SF50 EA50 SJ30 WW24 FA02",
}
TYPE_MFR = {t: m for m, ts in MFR.items() for t in ts.split()}
BIZ_TYPES = list(TYPE_MFR)
# Airliner types used as BBJ/ACJ/VIP: only counted when callsign == registration (private ops, not an airline flight).
VIP_TYPES = "B737 B738 B752 B763 B748 A318 A319 A332".split()
VIP_MFR = "Boeing BBJ / Airbus ACJ (heuristic)"

# ---- regions (ordered lat/lon boxes, first match wins) -------------------------------------------------------
REGIONS = [
 ("Central America & Caribbean", 5, 24.4, -118, -58),
 ("North America", 15, 85, -170, -50),
 ("South America", -60, 12.5, -92, -30),
 ("Middle East", 12, 42, 34, 63),
 ("Europe", 34, 72, -25, 45),
 ("Africa", -36, 37.5, -20, 52),
 ("South Asia", 5, 37, 60, 92),
 ("East Asia", 18, 55, 92, 150),
 ("Southeast Asia", -11, 23, 92, 141),
 ("Oceania", -50, -11, 110, 180),
 ("Russia & Central Asia", 35, 80, 45, 180),
]
def region(lat, lon):
    if lat is None or lon is None: return "Unknown"
    for n, a, b, c, d in REGIONS:
        if a <= lat <= b and c <= lon <= d: return n
    return "Oceanic / other"

REG_PREFIX = [("VP-C","Cayman Islands"),("VP-B","Bermuda"),("VQ-B","Bermuda"),("A9C-","Bahrain"),("A4O-","Oman"),("B-H","Hong Kong"),("B-K","Hong Kong"),("B-L","Hong Kong"),("B-M","Macau"),
 ("XA-","Mexico"),("XB-","Mexico"),("XC-","Mexico"),("EC-","Spain"),("HB-","Switzerland"),("OE-","Austria"),("PH-","Netherlands"),("OO-","Belgium"),("LX-","Luxembourg"),("SE-","Sweden"),
 ("OY-","Denmark"),("LN-","Norway"),("OH-","Finland"),("SP-","Poland"),("OK-","Czechia"),("OM-","Slovakia"),("HA-","Hungary"),("YR-","Romania"),("LZ-","Bulgaria"),("SX-","Greece"),
 ("TC-","Turkey"),("9H-","Malta"),("EI-","Ireland"),("CS-","Portugal"),("RA-","Russia"),("UR-","Ukraine"),("4K-","Azerbaijan"),("UP-","Kazakhstan"),("A6-","UAE"),("A7-","Qatar"),
 ("HZ-","Saudi Arabia"),("9K-","Kuwait"),("4X-","Israel"),("SU-","Egypt"),("5N-","Nigeria"),("ZS-","South Africa"),("5Y-","Kenya"),("CN-","Morocco"),("VT-","India"),("AP-","Pakistan"),
 ("9V-","Singapore"),("9M-","Malaysia"),("PK-","Indonesia"),("HS-","Thailand"),("RP-","Philippines"),("VH-","Australia"),("ZK-","New Zealand"),("PP-","Brazil"),("PR-","Brazil"),
 ("PT-","Brazil"),("PS-","Brazil"),("PU-","Brazil"),("LV-","Argentina"),("CC-","Chile"),("HK-","Colombia"),("YV-","Venezuela"),("OB-","Peru"),("HP-","Panama"),("TG-","Guatemala"),
 ("C6-","Bahamas"),("T7-","San Marino"),("9A-","Croatia"),("S5-","Slovenia"),("YU-","Serbia"),("ES-","Estonia"),("YL-","Latvia"),("LY-","Lithuania"),("4L-","Georgia"),("EW-","Belarus"),
 ("P4-","Aruba"),("C-","Canada"),("G-","United Kingdom"),("D-","Germany"),("F-","France"),("I-","Italy"),("M-","Isle of Man"),("2-","Guernsey"),("B-","China/Taiwan"),("JA","Japan"),("HL","South Korea")]
def reg_country(r):
    r = (r or "").upper().strip()
    if not r: return "Unknown"
    if re.match(r"^N\d", r): return "United States"
    for p, c in REG_PREFIX:
        if r.startswith(p): return c
    return "Other"

# ---- helpers -----------------------------------------------------------------------------------------------
def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def parse(s):
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: return None
def hour_of(d): return d.replace(minute=0, second=0, microsecond=0)
def et(d, f="%a %b %-d, %-I:%M %p ET"): return d.astimezone(ET).strftime(f)

def db():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=30000")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS snapshots(ts TEXT PRIMARY KEY, ok INTEGER, partial INTEGER, airborne INTEGER, on_ground INTEGER, privacy INTEGER,
        by_region TEXT, by_mfr TEXT, by_status TEXT, by_country TEXT, by_type TEXT, departures INTEGER, sources TEXT);
    CREATE TABLE IF NOT EXISTS seen(hex TEXT PRIMARY KEY, last_ts TEXT, ground INTEGER, alt INTEGER, lat REAL, lon REAL);
    CREATE TABLE IF NOT EXISTS departures(id INTEGER PRIMARY KEY AUTOINCREMENT, hex TEXT, ts TEXT, hour TEXT, type TEXT, mfr TEXT, reg TEXT,
        callsign TEXT, lat REAL, lon REAL, alt INTEGER, airport TEXT, airport_name TEXT, airport_country TEXT, airport_km REAL, region TEXT, method TEXT);
    CREATE INDEX IF NOT EXISTS dep_hour ON departures(hour); CREATE INDEX IF NOT EXISTS dep_hex ON departures(hex, ts);
    CREATE TABLE IF NOT EXISTS hours(hour TEXT PRIMARY KEY, count INTEGER, samples INTEGER, valid INTEGER, basis TEXT, n_base INTEGER,
        mean REAL, std REAL, std_eff REAL, k REAL, threshold REAL, spike INTEGER, status TEXT, evaluated_at TEXT);
    CREATE TABLE IF NOT EXISTS spikes(id INTEGER PRIMARY KEY AUTOINCREMENT, hour TEXT UNIQUE, count INTEGER, mean REAL, std REAL, threshold REAL, k REAL,
        pct_above REAL, basis TEXT, n_base INTEGER, top_regions TEXT, top_airports TEXT, coinciding TEXT, recurring INTEGER, recurring_note TEXT,
        paragraph TEXT, created_at TEXT, alerted_at TEXT, suppressed TEXT, pushed_at TEXT);
    CREATE TABLE IF NOT EXISTS source_status(name TEXT PRIMARY KEY, url TEXT, ok INTEGER, items INTEGER, last_checked TEXT, last_ok TEXT, error TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    """)
    return c
def meta_get(c, k):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone(); return r[0] if r else None
def meta_set(c, k, v): c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))

def settings(cfg):
    s = {**DEFAULTS, **{k: cfg[k] for k in DEFAULTS if k in cfg}}
    s["jet_spike_k"] = min(K_MAX, max(K_MIN, float(s["jet_spike_k"])))
    s["jet_spike_alerts_enabled"] = bool(s["jet_spike_alerts_enabled"])
    s["sample_minutes"] = max(2, min(int(s["jet_sample_minutes"]), int(cfg.get("interval_minutes", 60))))
    return s

# ---- airports (OurAirports, cached) -----------------------------------------------------------------------
_AP = None
def airports():
    global _AP
    if _AP is not None: return _AP
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(AIRPORTS_CSV) or time.time() - os.path.getmtime(AIRPORTS_CSV) > 30 * 86400:
        try:
            r = requests.get(AIRPORTS_URL, timeout=60, headers=UA); r.raise_for_status()
            open(AIRPORTS_CSV + ".tmp", "wb").write(r.content); os.replace(AIRPORTS_CSV + ".tmp", AIRPORTS_CSV)
        except Exception: pass
    grid = {}
    if os.path.exists(AIRPORTS_CSV):
        for a in csv.DictReader(open(AIRPORTS_CSV, encoding="utf-8")):
            t = a["type"]
            if t not in ("large_airport", "medium_airport") and not (t == "small_airport" and (a["icao_code"] or "").strip()): continue
            try: la, lo = float(a["latitude_deg"]), float(a["longitude_deg"])
            except Exception: continue
            w = {"large_airport": 0, "medium_airport": 1}.get(t, 2)
            grid.setdefault((math.floor(la), math.floor(lo)), []).append((la, lo, a["icao_code"] or a["gps_code"] or a["ident"], a["name"], a["iso_country"], w))
    _AP = grid; return grid

def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(x)))

def nearest_airport(lat, lon, max_km=60):
    if lat is None or lon is None: return None
    g = airports(); best = None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ck = (math.floor(lat) + dy, ((math.floor(lon) + dx + 180) % 360) - 180)
            for a in g.get(ck, []):
                km = hav(lat, lon, a[0], a[1])
                # prefer larger airports slightly (bizjets rarely use tiny strips)
                adj = km + a[5] * 3
                if km <= max_km and (best is None or adj < best[0]): best = (adj, km, a)
    if not best: return None
    _, km, a = best
    return {"ident": a[2], "name": a[3], "country": a[4], "km": round(km, 1)}

# ---- fetch ---------------------------------------------------------------------------------------------------
def _get(c, name, url, note=""):
    t = iso(now())
    try:
        r = requests.get(url, timeout=25, headers=UA)
        if r.status_code != 200: raise RuntimeError(f"HTTP {r.status_code}")
        ac = r.json().get("ac") or []
        c.execute("""INSERT INTO source_status(name,url,ok,items,last_checked,last_ok,error,note) VALUES(?,?,1,?,?,?,NULL,?)
                     ON CONFLICT(name) DO UPDATE SET url=excluded.url, ok=1, items=excluded.items, last_checked=excluded.last_checked,
                     last_ok=excluded.last_ok, error=NULL, note=excluded.note""", (name, url, len(ac), t, t, note))
        return ac
    except Exception as ex:
        c.execute("""INSERT INTO source_status(name,url,ok,items,last_checked,last_ok,error,note) VALUES(?,?,0,0,?,NULL,?,?)
                     ON CONFLICT(name) DO UPDATE SET ok=0, items=0, last_checked=excluded.last_checked, error=excluded.error""",
                  (name, url, t, str(ex)[:200], note))
        return None

def fetch(c):
    chunks = [BIZ_TYPES[i:i + 45] for i in range(0, len(BIZ_TYPES), 45)]
    merged, privacy, okc, failc = {}, set(), 0, 0
    reqs = [(f"adsb.lol business-jet types #{i+1}", f"{ADSBLOL}/type/{','.join(ch)}", "business") for i, ch in enumerate(chunks)]
    reqs += [("adsb.lol VIP airliner types (BBJ/ACJ)", f"{ADSBLOL}/type/{','.join(VIP_TYPES)}", "vip"),
             ("adsb.lol LADD-flagged aircraft", f"{ADSBLOL}/ladd", "privacy"),
             ("adsb.lol PIA (privacy ICAO) aircraft", f"{ADSBLOL}/pia", "privacy")]
    for name, url, kind in reqs:
        ac = _get(c, name, url, "free, no key")
        time.sleep(0.5)
        if ac is None:
            if kind == "business": failc += 1
            continue
        if kind == "business": okc += 1
        for a in ac:
            hx = (a.get("hex") or "").lower().lstrip("~")
            if not hx or a.get("lat") is None: continue
            if (a.get("dbFlags") or 0) & 1: continue                     # military
            t = (a.get("t") or "").upper(); cs = (a.get("flight") or "").strip().replace("-", ""); rg = (a.get("r") or "").replace("-", "")
            if t in TYPE_MFR: mfr = TYPE_MFR[t]
            elif t in VIP_TYPES and cs and rg and cs.upper() == rg.upper(): mfr = VIP_MFR
            else: continue
            if kind == "privacy" or (a.get("dbFlags") or 0) & 12: privacy.add(hx)   # dbFlags 4=PIA, 8=LADD
            prev = merged.get(hx)
            if prev is None or (a.get("seen_pos") or 99) < (prev.get("seen_pos") or 99): merged[hx] = {**a, "_mfr": mfr}
    return merged, privacy, okc, failc

def status_of(a):
    if a.get("alt_baro") == "ground": return "On ground"
    alt = a.get("alt_baro") if isinstance(a.get("alt_baro"), (int, float)) else a.get("alt_geom") or 0
    rate = a.get("baro_rate", a.get("geom_rate")) or 0
    if rate >= 500: return "Climbing"
    if rate <= -500: return "Descending"
    return "Cruise (FL250+)" if alt >= 25000 else "Level, below FL250"

def top(d, n=None):
    return dict(sorted(d.items(), key=lambda x: -x[1])[:n] if n else sorted(d.items(), key=lambda x: -x[1]))

# ---- one sampler pass --------------------------------------------------------------------------------------
def run_pass(cfg=None):
    cfg = cfg or {}; st = settings(cfg); t0 = now(); ts = iso(t0)
    c = db()
    try:
        merged, privacy, okc, failc = fetch(c)
        if okc == 0:
            c.execute("INSERT OR REPLACE INTO snapshots(ts,ok,partial) VALUES(?,0,0)", (ts,)); meta_set(c, "last_attempt", ts); c.commit()
            return {"status": "source_unreachable", "ts": ts}
        last_ok = parse(meta_get(c, "last_ok_pass") or "")
        detect = bool(last_ok and (t0 - last_ok) <= timedelta(minutes=3 * st["sample_minutes"]))
        by_r, by_m, by_s, by_c, by_t = {}, {}, {}, {}, {}
        air = gnd = 0; deps = []
        seen = {r["hex"]: dict(r) for r in c.execute("SELECT * FROM seen")}
        recent_dep = {r[0] for r in c.execute("SELECT DISTINCT hex FROM departures WHERE ts>=?", (iso(t0 - timedelta(hours=DEDUP_DEPARTURE_H)),))}
        for hx, a in merged.items():
            s = status_of(a); ground = s == "On ground"
            lat, lon = a.get("lat"), a.get("lon")
            alt = 0 if ground else (a.get("alt_baro") if isinstance(a.get("alt_baro"), (int, float)) else (a.get("alt_geom") or 0))
            if ground: gnd += 1
            else:
                air += 1; rg = region(lat, lon)
                for d, k in ((by_r, rg), (by_m, a["_mfr"]), (by_s, s), (by_c, reg_country(a.get("r"))), (by_t, a.get("t") or "?")): d[k] = d.get(k, 0) + 1
            # departure detection
            if detect and not ground and hx not in recent_dep:
                p = seen.get(hx); method = None; plat, plon = lat, lon
                rate = a.get("baro_rate", a.get("geom_rate")) or 0
                if p and p["ground"] and (t0 - parse(p["last_ts"])) <= timedelta(minutes=max(20, 3 * st["sample_minutes"])):
                    method = "ground->airborne"; plat, plon = p["lat"], p["lon"]
                elif (not p or (t0 - parse(p["last_ts"])) > timedelta(minutes=30)) and alt < 10000 and rate >= 300:
                    method = "new low climb"
                if method:
                    ap = nearest_airport(plat, plon, 60 if method == "new low climb" else 15)
                    if method == "new low climb" and not ap: method = None    # climbing far from any airport: probably a coverage edge
                if method:
                    deps.append((hx, ts, iso(hour_of(t0)), a.get("t"), a["_mfr"], a.get("r"), (a.get("flight") or "").strip(), lat, lon, alt,
                                 ap and ap["ident"], ap and ap["name"], ap and ap["country"], ap and ap["km"], region(plat, plon), method))
            c.execute("INSERT OR REPLACE INTO seen VALUES(?,?,?,?,?,?)", (hx, ts, int(ground), int(alt or 0), lat, lon))
        c.executemany("""INSERT INTO departures(hex,ts,hour,type,mfr,reg,callsign,lat,lon,alt,airport,airport_name,airport_country,airport_km,region,method)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", deps)
        srcs = [dict(r) for r in c.execute("SELECT name, ok, items, last_ok, error FROM source_status")]
        c.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (ts, 1, int(failc > 0), air, gnd, len(privacy), json.dumps(top(by_r)), json.dumps(top(by_m)), json.dumps(top(by_s)),
                   json.dumps(top(by_c, 25)), json.dumps(top(by_t, 25)), len(deps), json.dumps(srcs)))
        meta_set(c, "last_ok_pass", ts); meta_set(c, "last_attempt", ts)
        # housekeeping
        c.execute("DELETE FROM seen WHERE last_ts<?", (iso(t0 - timedelta(days=1)),))
        c.execute("DELETE FROM snapshots WHERE ts<?", (iso(t0 - timedelta(days=60)),))
        c.commit()
        new_spikes = evaluate_hours(c, st)
        c.commit()
        return {"status": "ok" if not failc else "partial", "ts": ts, "airborne": air, "on_ground": gnd, "departures_this_pass": len(deps),
                "detect": detect, "new_spikes": new_spikes}
    finally:
        c.close()

# ---- hourly baseline + spike evaluation -------------------------------------------------------------------
def hour_counts(c, h):
    hs, he = iso(h), iso(h + timedelta(hours=1))
    n = c.execute("SELECT COUNT(*) FROM departures WHERE hour=?", (hs,)).fetchone()[0]
    # samples that could detect departures = ok passes in the hour (the first pass after a gap can't detect)
    samples = c.execute("SELECT COUNT(*) FROM snapshots WHERE ok=1 AND ts>=? AND ts<?", (hs, he)).fetchone()[0]
    return n, samples

def baseline(c, h):
    """Rows of valid past hours. Returns (basis, n, mean, std, flat_mean, flat_std)."""
    rows = [(parse(r["hour"]), r["count"]) for r in c.execute("SELECT hour, count FROM hours WHERE valid=1 AND hour<? AND hour>=?",
                                                                (iso(h), iso(h - timedelta(weeks=8))))]
    week = [n for d, n in rows if d >= h - timedelta(days=7)]
    how = [n for d, n in rows if d.weekday() == h.weekday() and d.hour == h.hour]
    hod = [n for d, n in rows if d >= h - timedelta(days=7) and d.hour == h.hour]
    fm = statistics.mean(week) if week else None; fs = statistics.stdev(week) if len(week) >= 2 else None
    if len(how) >= MIN_HOW_SAMPLES: sel, basis = how, "hour-of-week (same weekday+hour, up to 8 weeks)"
    elif len(week) >= MIN_BASELINE_HOURS and len(hod) >= MIN_SAME_HOUR_SAMPLES: sel, basis = hod, "hour-of-day (same UTC hour, past 7 days)"
    else: return "warming_up", len(week), fm, fs, fm, fs
    return basis, len(sel), statistics.mean(sel), statistics.stdev(sel) if len(sel) >= 2 else 0.0, fm, fs

def evaluate_hours(c, st):
    cur = hour_of(now()); last = meta_get(c, "last_eval_hour")
    first_snap = c.execute("SELECT MIN(ts) FROM snapshots WHERE ok=1").fetchone()[0]
    if not first_snap: return []
    h = parse(last) + timedelta(hours=1) if last else hour_of(parse(first_snap))
    h = max(h, cur - timedelta(hours=48)); out = []
    need = 0.6 * 60 / st["sample_minutes"]
    while h < cur:
        n, samples = hour_counts(c, h); valid = int(samples >= need)
        basis, nb, mean, std, fm, fs = baseline(c, h); k = st["jet_spike_k"]
        if not valid:
            status, std_eff, thr, spike = "insufficient samples", None, None, 0
        elif basis == "warming_up":
            status, std_eff, thr, spike = "warming up", None, None, 0
        else:
            std_eff = max(std, math.sqrt(max(mean, 0)), 1.0)     # Poisson floor so a quiet, flat history can't make tiny thresholds
            thr = mean + k * std_eff; spike = int(n > thr); status = "spike" if spike else "normal"
        c.execute("INSERT OR REPLACE INTO hours VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (iso(h), n, samples, valid, basis, nb, mean, std, std_eff, k, thr, spike, status, iso(now())))
        if spike: out.append(make_spike(c, h, n, mean, std_eff, thr, k, basis, nb, st))
        meta_set(c, "last_eval_hour", iso(h)); h += timedelta(hours=1)
    return out

def coinciding(h, regions):
    """Read-only: main-feed threat clusters rank>=5 from 6h before to 1h after the spike hour in the spike's top regions."""
    try:
        t = sqlite3.connect(f"file:{THREAT_DB}?mode=ro", uri=True, timeout=10); t.row_factory = sqlite3.Row
        rows = [dict(r) for r in t.execute("""SELECT title, rank, location, lat, lon, category, COALESCE(event_time, first_seen) t, links FROM clusters
               WHERE watchlist=0 AND rank>=5 AND COALESCE(event_time, first_seen) BETWEEN ? AND ? ORDER BY rank DESC LIMIT 200""",
               (iso(h - timedelta(hours=6)), iso(h + timedelta(hours=1))))]
        t.close()
    except Exception: return []
    out = []
    for r in rows:
        rg = region(r["lat"], r["lon"])
        if rg in regions:
            links = [l.get("url") for l in json.loads(r["links"] or "[]")][:2]
            out.append({"rank": r["rank"], "title": r["title"], "location": r["location"], "region": rg, "category": r["category"], "time": r["t"], "links": links})
    return out[:5]

def make_spike(c, h, n, mean, std, thr, k, basis, nb, st):
    hs = iso(h)
    reg = top({r[0]: r[1] for r in c.execute("SELECT region, COUNT(*) FROM departures WHERE hour=? GROUP BY region", (hs,))}, 3)
    aps = [dict(ident=r[0], name=r[1], country=r[2], n=r[3]) for r in c.execute(
        "SELECT airport, airport_name, airport_country, COUNT(*) n FROM departures WHERE hour=? AND airport IS NOT NULL GROUP BY airport ORDER BY n DESC LIMIT 5", (hs,))]
    pct = round(100 * (n - mean) / mean) if mean > 0 else None
    prior = [parse(r[0]) for r in c.execute("SELECT hour FROM hours WHERE spike=1 AND hour<? AND hour>=?", (hs, iso(h - timedelta(weeks=8))))]
    same = [d for d in prior if d.weekday() == h.weekday() and d.hour == h.hour]
    rec = len(same)
    rnote = (f"Recurring pattern: this same hour of the week ({et(h, '%A %-I %p ET')}) also spiked in {rec} earlier week(s); likely a routine schedule peak, not an anomaly."
             if rec else "")
    co = coinciding(h, list(reg))
    he = h + timedelta(hours=1)
    para = (f"Private-jet takeoff spike, {et(h, '%a %b %-d, %-I:%M')}–{et(he, '%-I:%M %p ET')}: {n} business-jet departures detected versus a baseline of "
            f"{mean:.1f} (std {std:.1f}, {basis}, n={nb}); that is {pct if pct is not None else 'n/a'}% above baseline and over the k={k:g} threshold of {thr:.1f}. "
            f"Top regions: {', '.join(f'{r} ({v})' for r, v in reg.items()) or 'n/a'}. "
            f"Top airports: {', '.join(f'{a['ident']} {a['name']} ({a['n']})' for a in aps) or 'n/a'}. "
            + (f"Coinciding threat-feed items (rank 5+, same regions, 6h window): {'; '.join(f'[{x['rank']}] {x['title']}' for x in co)}. " if co else "No coinciding rank 5+ threat-feed items in those regions. ")
            + (rnote + " " if rnote else "")
            + "Informational only; counts transponding aircraft and do not affect threat ranks.")
    enabled = st["jet_spike_alerts_enabled"]
    t = iso(now())
    c.execute("""INSERT OR IGNORE INTO spikes(hour,count,mean,std,threshold,k,pct_above,basis,n_base,top_regions,top_airports,coinciding,recurring,recurring_note,
                 paragraph,created_at,alerted_at,suppressed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (hs, n, mean, std, thr, k, pct, basis, nb, json.dumps(reg), json.dumps(aps), json.dumps(co), rec, rnote, para, t,
               t if enabled else None, None if enabled else "alerts disabled"))
    c.commit()
    if enabled:
        try:
            import push
            r = push.push_jet_spike({"type": "jet_spike", "hour": hs, "count": n, "pct_above": pct, "paragraph": para})
            if r.get("status") == "sent": c.execute("UPDATE spikes SET pushed_at=? WHERE hour=?", (iso(now()), hs))
        except Exception: pass
    return hs

# ---- API views ---------------------------------------------------------------------------------------------
def spike_row(r):
    d = dict(r)
    for k in ("top_regions", "top_airports", "coinciding"): d[k] = json.loads(d[k] or "null")
    h = parse(d["hour"]); d["hour_et"] = f"{et(h, '%a %b %-d, %-I:%M')}–{et(h + timedelta(hours=1), '%-I:%M %p ET')}"
    return d

def new_spikes(since):
    c = db()
    try: return [spike_row(r) for r in c.execute("SELECT * FROM spikes WHERE alerted_at IS NOT NULL AND alerted_at>=? ORDER BY hour", (iso(since),))]
    finally: c.close()

NOTE = ("Counts only business/private jets that are transmitting ADS-B/MLAT and are currently received by the volunteer adsb.lol network. "
        "Jets flying under privacy programs (FAA LADD/PIA) may still appear but often without owner details; many fly with transponders "
        "filtered, outside receiver coverage (oceans, much of Africa, Russia, China), or are not in our type list. Treat every number as a lower bound, not a true total. "
        "BBJ/ACJ airliner-type VIP jets are a heuristic (callsign = registration). Jet data is informational and never affects threat ranks or pushes.")

def api_state(cfg):
    st = settings(cfg); c = db(); t = now()
    try:
        last = c.execute("SELECT * FROM snapshots WHERE ok=1 ORDER BY ts DESC LIMIT 1").fetchone()
        last_attempt = meta_get(c, "last_attempt")
        snap = None
        if last:
            snap = dict(last)
            for k in ("by_region", "by_mfr", "by_status", "by_country", "by_type", "sources"): snap[k] = json.loads(snap[k] or "null")
            age = (t - parse(snap["ts"])).total_seconds() / 60
            snap["age_minutes"] = round(age, 1)
            snap["stale"] = age > 2.5 * st["sample_minutes"]
        hrs = []
        for i in range(24, -1, -1):
            h = hour_of(t) - timedelta(hours=i); hs, he = iso(h), iso(h + timedelta(hours=1))
            a = c.execute("SELECT AVG(airborne), COUNT(*) FROM snapshots WHERE ok=1 AND ts>=? AND ts<?", (hs, he)).fetchone()
            ev = c.execute("SELECT * FROM hours WHERE hour=?", (hs,)).fetchone()
            dep = c.execute("SELECT COUNT(*) FROM departures WHERE hour=?", (hs,)).fetchone()[0]
            hrs.append({"hour": hs, "label": et(h, "%-I %p"), "avg_airborne": round(a[0]) if a[0] is not None else None, "samples": a[1],
                        "departures": dep, "threshold": ev["threshold"] if ev else None, "status": ev["status"] if ev else ("in progress" if i == 0 else None)})
        last_ev = c.execute("SELECT * FROM hours ORDER BY hour DESC LIMIT 1").fetchone()
        valid_hours = c.execute("SELECT COUNT(*) FROM hours WHERE valid=1 AND hour>=?", (iso(t - timedelta(days=7)),)).fetchone()[0]
        cur_basis = baseline(c, hour_of(t))
        top_ap = [dict(r) for r in c.execute("""SELECT airport, airport_name, airport_country, region, COUNT(*) n FROM departures WHERE ts>=? AND airport IS NOT NULL
                   GROUP BY airport ORDER BY n DESC LIMIT 10""", (iso(t - timedelta(hours=3)),))]
        dep_reg = {r[0]: r[1] for r in c.execute("SELECT region, COUNT(*) FROM departures WHERE ts>=? GROUP BY region ORDER BY 2 DESC", (iso(t - timedelta(hours=3)),))}
        spikes = [spike_row(r) for r in c.execute("SELECT * FROM spikes ORDER BY hour DESC LIMIT 50")]
        recurring = [dict(r) for r in c.execute("""SELECT hour FROM hours WHERE spike=1 AND hour>=?""", (iso(t - timedelta(weeks=8)),))]
        how = {}
        for r in recurring:
            d = parse(r["hour"]); key = et(d, "%A %-I %p ET"); how[key] = how.get(key, 0) + 1
        sources = [dict(r) for r in c.execute("SELECT * FROM source_status ORDER BY name")]
        return {"generated": iso(t), "settings": {"k": st["jet_spike_k"], "enabled": st["jet_spike_alerts_enabled"], "k_min": K_MIN, "k_max": K_MAX,
                "sample_minutes": st["sample_minutes"], "scan_interval_minutes": cfg.get("interval_minutes", 60)},
                "snapshot": snap, "last_attempt": last_attempt, "last_attempt_failed": bool(last_attempt and (not last or last_attempt != snap["ts"])),
                "trend24": hrs, "last_eval": dict(last_ev) if last_ev else None,
                "baseline": {"valid_hours_7d": valid_hours, "basis_for_current_hour": cur_basis[0], "n": cur_basis[1],
                             "mean": cur_basis[2], "std": cur_basis[3], "flat_7d_mean": cur_basis[4], "flat_7d_std": cur_basis[5],
                             "warmup_rule": f"no alerts until >= {MIN_BASELINE_HOURS} valid hours AND >= {MIN_SAME_HOUR_SAMPLES} prior samples of the same UTC hour (~48h)"},
                "departures_3h": {"by_region": dep_reg, "top_airports": top_ap},
                "spikes": spikes, "recurring_hours": {k: v for k, v in how.items() if v >= 2},
                "sources": sources, "note": NOTE,
                "source_links": [{"name": "adsb.lol (used, free, no key)", "url": "https://www.adsb.lol/"},
                                 {"name": "adsb.lol API docs", "url": "https://api.adsb.lol/docs"},
                                 {"name": "OurAirports data (airport lookup)", "url": "https://ourairports.com/data/"},
                                 {"name": "OpenSky Network (not used: unreachable from this box)", "url": "https://opensky-network.org/"},
                                 {"name": "airplanes.live (not used: API returns 403 without approval)", "url": "https://airplanes.live/"},
                                 {"name": "adsb.fi (not used: no type query)", "url": "https://adsb.fi/"},
                                 {"name": "ADS-B Exchange (not used: paid RapidAPI key)", "url": "https://www.adsbexchange.com/"},
                                 {"name": "Flightradar24 / FlightAware (not used: paid keys)", "url": "https://www.flightradar24.com/"}]}
    finally:
        c.close()

if __name__ == "__main__":
    cfg = json.load(open(f"{BASE}/config.json"))
    print(json.dumps(run_pass(cfg), indent=1, default=str))
