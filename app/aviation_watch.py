#!/usr/bin/env python3
"""blackout.network - global "Aviation" section (research/display only; never posts anything).

Replaces the hourly report's private-jets line with: military snapshot (count by type/region), notable watchlist
aircraft (Air Force One airframes, E-4B, E-6B, VIP/head-of-state jets, billionaire jets), emergency squawks, and
unusual military concentrations at hotspots vs a rolling baseline (aviation_state.db).

Data: public ADS-B aggregators, free & keyless: api.adsb.lol/v2 (primary), opendata.adsb.fi/api/v2 (fallback).
ADS-B positions are OBSERVED data; anything about purpose or passengers is INFERENCE and labelled as such.
Volunteer receiver coverage is thin over Russia, China, Iran, much of Africa and open ocean, and many military/VIP
aircraft fly with ADS-B off or position-suppressed, so "not seen" never means "not flying".

Usage:  python3 aviation_watch.py --report   # concise markdown section (<=8 lines)
        python3 aviation_watch.py --json     # machine-readable result
Writes ONLY aviation_state.db (and caches under aviationdata/). ~7 API calls per run.
"""
import os, sys, json, csv, math, sqlite3, time, statistics, argparse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests

BASE = "/workspace/blackout"
DB = f"{BASE}/aviation_state.db"
WATCHLIST = f"{BASE}/aviation_watchlist.json"
DATA = f"{BASE}/aviationdata"
AIRPORTS_CSV = f"{BASE}/jetdata/airports.csv"           # OurAirports cache shared with jets.py (read-only here)
COUNTRIES_CSV = f"{DATA}/countries.csv"
COUNTRIES_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "BlackoutNetwork-research/1.0 (personal, non-commercial; hourly polling)"}
PRIMARY = ("adsb.lol", "https://api.adsb.lol/v2")
FALLBACK = ("adsb.fi", "https://opendata.adsb.fi/api/v2")
GLOBE = "https://globe.adsb.lol/?icao="
CALL_GAP_S = 1.1                         # be polite: >=1 s between calls (adsb.fi limit is 1 req/s)
NEW_FLIGHT_GAP_H = 3                     # a watchlist aircraft unseen this long = new flight (resets "origin")

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def et(d): return d.astimezone(ET).strftime("%-I:%M %p ET")

# ---- regions (same boxes as jets.py) + hotspots ------------------------------------------------------------
REGIONS = [
 ("Central America & Caribbean", 5, 24.4, -118, -58), ("North America", 15, 85, -170, -50),
 ("South America", -60, 12.5, -92, -30), ("Middle East", 12, 42, 34, 63), ("Europe", 34, 72, -25, 45),
 ("Africa", -36, 37.5, -20, 52), ("South Asia", 5, 37, 60, 92), ("East Asia", 18, 55, 92, 150),
 ("Southeast Asia", -11, 23, 92, 141), ("Oceania", -50, -11, 110, 180), ("Russia & Central Asia", 35, 80, 45, 180),
]
def region(lat, lon):
    if lat is None or lon is None: return "No position"
    for n, a, b, c, d in REGIONS:
        if a <= lat <= b and c <= lon <= d: return n
    return "Oceanic / other"

HOTSPOTS = [  # name, lat_min, lat_max, lon_min, lon_max
 ("Persian Gulf & Strait of Hormuz", 22, 31, 47, 60),
 ("Red Sea & Yemen", 11, 22, 36, 46),
 ("Israel, Levant & E. Med", 29, 37.5, 30, 39),
 ("Iraq & Syria", 29, 37.5, 39, 48.5),
 ("Black Sea", 40.5, 47.5, 27, 42),
 ("Poland-Romania (Ukraine border)", 44, 55, 14, 27),
 ("Baltic Sea", 53, 66, 9, 30),
 ("Taiwan Strait & S. China Sea", 8, 27, 105, 125),
 ("Korean Peninsula", 33, 43, 124, 132),
 ("Caribbean & Venezuela", 8, 20, -76, -59),
]
def hotspot(lat, lon):
    if lat is None or lon is None: return None
    for n, a, b, c, d in HOTSPOTS:
        if a <= lat <= b and c <= lon <= d: return n
    return None

# ---- ICAO 24-bit address -> registering state (major blocks only; ICAO Annex 10 allocations) ----------------
HEX_COUNTRY = [
 (0xA00000, 0xAFFFFF, "US"), (0x400000, 0x43FFFF, "UK"), (0x3C0000, 0x3FFFFF, "Germany"), (0x380000, 0x3BFFFF, "France"),
 (0x300000, 0x33FFFF, "Italy"), (0x340000, 0x37FFFF, "Spain"), (0x480000, 0x487FFF, "Netherlands"), (0x448000, 0x44FFFF, "Belgium"),
 (0x4B8000, 0x4BFFFF, "Turkey"), (0x468000, 0x46FFFF, "Greece"), (0x488000, 0x48FFFF, "Poland"), (0x4A0000, 0x4A7FFF, "Romania"),
 (0x4A8000, 0x4AFFFF, "Sweden"), (0x478000, 0x47FFFF, "Norway"), (0x458000, 0x45FFFF, "Denmark"), (0x460000, 0x467FFF, "Finland"),
 (0x508000, 0x50FFFF, "Ukraine"), (0x100000, 0x1FFFFF, "Russia"), (0x780000, 0x7BFFFF, "China"), (0x738000, 0x73FFFF, "Israel"),
 (0x730000, 0x737FFF, "Iran"), (0x710000, 0x717FFF, "Saudi Arabia"), (0x896000, 0x896FFF, "UAE"), (0x06A000, 0x06A3FF, "Qatar"),
 (0x706000, 0x706FFF, "Kuwait"), (0x894000, 0x894FFF, "Bahrain"), (0x70C000, 0x70C3FF, "Oman"), (0x740000, 0x747FFF, "Jordan"),
 (0x010000, 0x017FFF, "Egypt"), (0x840000, 0x87FFFF, "Japan"), (0x718000, 0x71FFFF, "South Korea"), (0x899000, 0x8993FF, "Taiwan"),
 (0x800000, 0x83FFFF, "India"), (0x760000, 0x767FFF, "Pakistan"), (0x7C0000, 0x7FFFFF, "Australia"), (0xC80000, 0xC87FFF, "New Zealand"),
 (0xC00000, 0xC3FFFF, "Canada"), (0xE40000, 0xE7FFFF, "Brazil"), (0x0D0000, 0x0D7FFF, "Mexico"), (0xE00000, 0xE3FFFF, "Argentina"),
 (0xE80000, 0xE80FFF, "Chile"), (0x0AC000, 0x0ACFFF, "Colombia"), (0x0D8000, 0x0DFFFF, "Venezuela"), (0x008000, 0x00FFFF, "South Africa"),
 (0x4C8000, 0x4C83FF, "Cyprus"), (0x500000, 0x5003FF, "San Marino"), (0x440000, 0x447FFF, "Austria"), (0x4B0000, 0x4B7FFF, "Switzerland"),
 (0x490000, 0x497FFF, "Czechia"), (0x470000, 0x477FFF, "Hungary"), (0x450000, 0x457FFF, "Bulgaria"), (0x4CA000, 0x4CAFFF, "Ireland"),
 (0x490000, 0x497FFF, "Czechia"), (0x4D0000, 0x4D03FF, "Luxembourg"), (0x510000, 0x5103FF, "Belarus"), (0x0C0000, 0x0C0FFF, "Bahamas"),
 (0x750000, 0x757FFF, "Malaysia"), (0x768000, 0x76FFFF, "Singapore"), (0x880000, 0x887FFF, "Thailand"), (0x758000, 0x75FFFF, "Philippines"),
 (0x8A0000, 0x8A7FFF, "Indonesia"), (0x720000, 0x727FFF, "North Korea"),
]
def hex_country(h):
    try: v = int(h.strip("~"), 16)
    except Exception: return "?"
    for a, b, n in HEX_COUNTRY:
        if a <= v <= b: return n
    return "Other"

# ---- classification -------------------------------------------------------------------------------------------
TYPE_NAME = {"B52": "B-52H", "B1": "B-1B", "B2": "B-2", "K35R": "KC-135", "K35E": "KC-135E", "R135": "RC-135", "E3TF": "E-3",
 "E3CF": "E-3", "E6": "E-6B", "P8": "P-8", "Q4": "RQ-4", "U2": "U-2", "E737": "E-7", "Q9": "MQ-9", "C17": "C-17", "C5M": "C-5M",
 "C30J": "C-130J", "C130": "C-130", "E2": "E-2", "B742": "747-200 (E-4B/VC-25)", "H60": "H-60", "EC45": "UH-72/EC145",
 "CN35": "CN-235", "A332": "A330 (mil/MRTT)", "B762": "767 (KC-46/mil)", "A400": "A400M", "GLF5": "Gulfstream V (C-37)", "GLF4": "Gulfstream IV (C-20)", "B737": "737 (C-40/P-8 trainer)", "C295": "C295", "TEX2": "T-6", "BE20": "C-12/King Air", "IL76": "Il-76", "IL78": "Il-78", "TU95": "Tu-95",
 "T160": "Tu-160", "TU22": "Tu-22M", "A50": "A-50", "IL20": "Il-20", "C27J": "C-27J", "H47": "CH-47", "V22": "V-22"}
BOMBER = {"B52", "B1", "B2", "TU95", "T160", "TU22", "H6"}
ISR = {"R135", "E3TF", "E3CF", "E6", "P8", "Q4", "U2", "E737", "Q9", "E8", "E2", "A50", "IL20", "P3"}
AIRLIFT = {"C17", "C5M", "C30J", "C130", "A400", "IL76", "Y20", "C2", "C295", "CN35", "C27J"}
TANKER_T = {"K35R", "K35E", "IL78", "KC10"}
def tname(t): return TYPE_NAME.get(t or "", t or "untyped")

def classify(a):
    t = (a.get("t") or "").upper(); desc = (a.get("desc") or "").upper(); mil = bool((a.get("dbFlags") or 0) & 1)
    cs = (a.get("flight") or "").strip().upper()
    if t in BOMBER: return "bomber"
    if t in ISR or "RIVET JOINT" in desc or "SENTRY" in desc: return "isr"
    if t in TANKER_T or "KC-46" in desc or "MRTT" in desc or "VOYAGER" in desc or "KC-30" in desc or "TANKER" in desc: return "tanker"
    if mil and t in ("A332", "A310", "DC10") : return "tanker"     # military A330/A310/DC-10 are almost all MRTT/KC variants
    if t in AIRLIFT or cs.startswith("RCH"): return "airlift"
    return "other"

def num(x):
    return x if isinstance(x, (int, float)) else None

def alt_str(a):
    v = a.get("alt_baro")
    if v == "ground": return "on the ground"
    v = num(v) if v is not None else num(a.get("alt_geom"))
    if v is None: return "altitude n/a"
    return f"FL{int(round(v/100)):03d}" if v >= 18000 else f"{int(v):,} ft"

def compass(deg):
    if deg is None: return None
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((deg % 360) + 22.5) // 45) % 8]

# ---- places (OurAirports) -------------------------------------------------------------------------------------
_AP = None; _CC = None
def countries():
    global _CC
    if _CC is not None: return _CC
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(COUNTRIES_CSV):
        try:
            r = requests.get(COUNTRIES_URL, timeout=30, headers=UA); r.raise_for_status(); open(COUNTRIES_CSV, "wb").write(r.content)
        except Exception: pass
    _CC = {}
    if os.path.exists(COUNTRIES_CSV):
        for c in csv.DictReader(open(COUNTRIES_CSV, encoding="utf-8")): _CC[c["code"]] = c["name"]
    return _CC

def airports():
    global _AP
    if _AP is not None: return _AP
    grid = {}
    if os.path.exists(AIRPORTS_CSV):
        for a in csv.DictReader(open(AIRPORTS_CSV, encoding="utf-8")):
            t = a["type"]
            if t not in ("large_airport", "medium_airport") and not (t == "small_airport" and (a["icao_code"] or "").strip()): continue
            try: la, lo = float(a["latitude_deg"]), float(a["longitude_deg"])
            except Exception: continue
            w = {"large_airport": 0, "medium_airport": 1}.get(t, 2)
            grid.setdefault((math.floor(la), math.floor(lo)), []).append(
                (la, lo, a["icao_code"] or a["gps_code"] or a["ident"], a["name"], a["iso_country"], w, a["municipality"]))
    _AP = grid; return grid

def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(x)))

def nearest_place(lat, lon, ground=False):
    """Nearest airport (prefers big ones when airborne). Searches growing rings up to ~600 km."""
    if lat is None or lon is None: return None
    g = airports(); best = None
    for ring in (1, 3, 6):
        for dy in range(-ring, ring + 1):
            for dx in range(-ring, ring + 1):
                ck = (math.floor(lat) + dy, ((math.floor(lon) + dx + 180) % 360) - 180)
                for a in g.get(ck, []):
                    if not ground and a[5] == 2: continue
                    km = hav(lat, lon, a[0], a[1]); adj = km + a[5] * (3 if ground else 25)
                    if best is None or adj < best[0]: best = (adj, km, a)
        if best and best[1] < ring * 90: break
    if not best: return None
    _, km, a = best
    return {"ident": a[2], "name": a[3], "city": a[6], "country": countries().get(a[4], a[4]), "km": round(km)}

def place_str(p, ground=False):
    if not p: return "position over open water/unknown area"
    town = p["city"] or p["name"]
    if ground or p["km"] <= 15: return f"at/near {p['name']} ({p['ident']}), {town}, {p['country']}"
    return f"~{p['km']} km from {town}, {p['country']} ({p['ident']})"

# ---- fetch ------------------------------------------------------------------------------------------------------
class Fetcher:
    def __init__(self):
        self.calls = 0; self.log = []; self._last = 0
    def get(self, path, fallback_ok=True):
        for name, base in ([PRIMARY, FALLBACK] if fallback_ok else [PRIMARY]):
            wait = CALL_GAP_S - (time.time() - self._last)
            if wait > 0: time.sleep(wait)
            self._last = time.time(); self.calls += 1
            try:
                r = requests.get(base + path, timeout=25, headers=UA)
                if r.status_code != 200: raise RuntimeError(f"HTTP {r.status_code}")
                j = r.json(); ac = j.get("ac") or j.get("aircraft") or []
                self.log.append({"path": path, "source": name, "ok": True, "n": len(ac)})
                return ac, name
            except Exception as e:
                self.log.append({"path": path, "source": name, "ok": False, "error": str(e)[:120]})
        return None, None

# ---- state DB ---------------------------------------------------------------------------------------------------
def db():
    c = sqlite3.connect(DB, timeout=30)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS runs(ts TEXT PRIMARY KEY, ok INTEGER, source TEXT, mil_total INTEGER, calls INTEGER, summary TEXT);
    CREATE TABLE IF NOT EXISTS hotspot_counts(ts TEXT, hotspot TEXT, cat TEXT, n INTEGER, PRIMARY KEY(ts, hotspot, cat));
    CREATE TABLE IF NOT EXISTS sightings(hex TEXT PRIMARY KEY, label TEXT, flight_start TEXT, first_lat REAL, first_lon REAL,
        first_alt TEXT, first_place TEXT, last_seen TEXT, last_lat REAL, last_lon REAL, last_alt TEXT, callsign TEXT);
    CREATE TABLE IF NOT EXISTS notable_log(ts TEXT, hex TEXT, label TEXT, category TEXT, lat REAL, lon REAL, alt TEXT, callsign TEXT,
        place TEXT, PRIMARY KEY(ts, hex));
    """)
    return c

def baseline(c, hs, cat, ts):
    """Median/MAD of past counts for this hotspot+category. Prefers same hour-of-day (+/-2h) over last 14 days."""
    rows = c.execute("SELECT r.ts, COALESCE(h.n,0) FROM runs r LEFT JOIN hotspot_counts h ON h.ts=r.ts AND h.hotspot=? AND h.cat=? "
                     "WHERE r.ok=1 AND r.ts<? AND r.ts>=? ORDER BY r.ts", (hs, cat, iso(ts), iso(ts - timedelta(days=14)))).fetchall()
    if not rows: return None
    hr = ts.hour
    same = [n for t, n in rows if min(abs(int(t[11:13]) - hr), 24 - abs(int(t[11:13]) - hr)) <= 2]
    vals, basis = (same, "same time of day") if len(same) >= 4 else ([n for _, n in rows], "all hours")
    if len(vals) < 6: return {"n": len(vals), "ready": False}
    med = statistics.median(vals); mad = statistics.median([abs(v - med) for v in vals]) or 0.5
    return {"n": len(vals), "ready": True, "median": med, "mad": mad, "basis": basis}

# ---- main run ---------------------------------------------------------------------------------------------------
def run():
    t0 = now(); wl = json.load(open(WATCHLIST)); f = Fetcher()
    W = {a["hex"].lower(): a for a in wl["aircraft"]}
    seen, src = {}, None
    def add(ac, tag):
        for a in ac or []:
            h = (a.get("hex") or "").lower()
            if not h: continue
            b = seen.setdefault(h, dict(a)); b.setdefault("_via", set()).add(tag)
            for k, v in a.items():
                if b.get(k) in (None, "") and v not in (None, ""): b[k] = v
    mil, src = f.get("/mil"); add(mil, "mil")
    types, _ = f.get("/type/" + ",".join(wl["types"]["query_types"]), fallback_ok=False); add(types, "type")
    wlac, _ = f.get("/hex/" + ",".join(W)); add(wlac, "watch")
    emerg = []
    for sq in ("7500", "7600", "7700"):
        ac, _ = f.get(f"/sqk/{sq}"); add(ac, "sqk")
        for a in ac or []:
            if a.get("squawk") == sq: emerg.append((sq, a))
    ok = mil is not None
    # military set = mil-flagged OR returned by the military type query and mil-flagged/DB-desc military
    def junk(a):   # stratospheric balloons, ground stations/towers and ground vehicles carry the military flag but aren't aircraft
        cs = (a.get("flight") or "").strip().upper(); t = (a.get("t") or "").upper()
        return cs.startswith("HBAL") or t in ("TWR", "GND", "BALL") or a.get("category") in ("C1", "C2", "C3", "B2")
    milset = {h: a for h, a in seen.items() if not junk(a) and (((a.get("dbFlags") or 0) & 1) or ("type" in a["_via"] and (a.get("t") in BOMBER | ISR | TANKER_T | {"C17", "C5M"})))}
    excluded = sum(1 for a in seen.values() if junk(a) and ((a.get("dbFlags") or 0) & 1))
    by_type, by_region, by_country, hs_counts = {}, {}, {}, {}
    for h, a in milset.items():
        lat, lon = num(a.get("lat")), num(a.get("lon"))
        by_type[tname(a.get("t"))] = by_type.get(tname(a.get("t")), 0) + 1
        by_region[region(lat, lon)] = by_region.get(region(lat, lon), 0) + 1
        by_country[hex_country(h)] = by_country.get(hex_country(h), 0) + 1
        hs = hotspot(lat, lon); cat = classify(a)
        if hs:
            d = hs_counts.setdefault(hs, {"total": 0, "tanker": 0, "isr": 0, "bomber": 0, "airlift": 0, "other": 0, "ac": []})
            d["total"] += 1; d[cat] += 1; d["ac"].append(h)
    c = db(); ts = t0.replace(microsecond=0)
    # hotspot anomalies vs baseline (baseline excludes this run)
    anomalies, hotspot_out, building = [], {}, None
    for hs, *_ in HOTSPOTS:
        d = hs_counts.get(hs, {"total": 0, "tanker": 0, "isr": 0, "bomber": 0, "airlift": 0, "other": 0, "ac": []})
        hotspot_out[hs] = {k: v for k, v in d.items() if k != "ac"}; hotspot_out[hs]["aircraft"] = d["ac"]
        for cat in ("total", "tanker", "isr", "bomber"):
            b = baseline(c, hs, cat, ts); n = d[cat]
            if b and not b["ready"]: building = b["n"]
            if b is None: building = 0
            if b and b["ready"]:
                thr = max(3 if cat != "total" else 6, b["median"] * 2, b["median"] + 4 * b["mad"])
                if n >= thr and n > b["median"]:
                    anomalies.append({"hotspot": hs, "cat": cat, "n": n, "median": b["median"], "basis": b["basis"], "samples": b["n"], "aircraft": d["ac"]})
    # notable aircraft
    notable = []
    def mk(h, a, why, cat, label=None):
        lat, lon = num(a.get("lat")), num(a.get("lon")); ground = a.get("alt_baro") == "ground"
        p = nearest_place(lat, lon, ground)
        return {"hex": h, "label": label or f"{hex_country(h)} {tname(a.get('t'))}", "category": cat, "why": why,
                "callsign": (a.get("flight") or "").strip() or None, "reg": a.get("r"), "type": a.get("t"),
                "lat": lat, "lon": lon, "has_position": lat is not None, "alt": alt_str(a), "ground": ground,
                "speed_kt": num(a.get("gs")), "heading": compass(num(a.get("track"))), "squawk": a.get("squawk"),
                "place": place_str(p, ground) if lat is not None else "transmitting, but no position broadcast (Mode-S only)",
                "hotspot": hotspot(lat, lon), "region": region(lat, lon), "seen_s": num(a.get("seen")), "link": GLOBE + h.strip("~"),
                "mlat": bool(a.get("mlat"))}
    for h, a in seen.items():
        if h in W:
            w = W[h]; notable.append(mk(h, a, "watchlist", w["category"], w["label"])); notable[-1]["key"] = w.get("key")
    vipcs = wl.get("vip_callsigns", {})
    for h, a in seen.items():
        cs = (a.get("flight") or "").strip().upper()
        if h in W or not cs: continue
        if cs in vipcs.get("exact", {}) or cs.startswith("SAM") and cs[3:].isdigit():
            n = mk(h, a, f"VIP callsign {cs}: {vipcs['exact'].get(cs) or vipcs['prefix']['SAM']}", "gov_vip"); n["key"] = "vipcs"; notable.append(n)
    for h, a in milset.items():
        if h in W: continue
        cat = classify(a); lat, lon = num(a.get("lat")), num(a.get("lon"))
        if cat == "bomber": notable.append(mk(h, a, "strategic bomber airborne", "military_strategic"))
        elif cat == "isr" and hotspot(lat, lon): notable.append(mk(h, a, f"ISR aircraft near {hotspot(lat, lon)}", "isr"))
        elif cat == "tanker" and hotspot(lat, lon): notable.append(mk(h, a, f"tanker near {hotspot(lat, lon)}", "tanker"))
    emerg_out = []
    for sq, a in emerg:
        h = a["hex"].lower(); meaning = {"7500": "hijack code", "7600": "radio failure", "7700": "general emergency"}[sq]
        e = mk(h, a, f"squawking {sq} ({meaning})", "emergency", f"{a.get('flight','').strip() or a.get('r') or h} ({a.get('desc') or tname(a.get('t'))})")
        emerg_out.append(e)
    # origin tracking for notable aircraft (observed across runs)
    for n in notable + emerg_out:
        r = c.execute("SELECT flight_start, first_place, first_alt, last_seen FROM sightings WHERE hex=?", (n["hex"],)).fetchone()
        fresh = (r is None) or (datetime.fromisoformat(r[3].replace("Z", "+00:00")) < ts - timedelta(hours=NEW_FLIGHT_GAP_H))
        if fresh:
            c.execute("INSERT OR REPLACE INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (n["hex"], n["label"], iso(ts), n["lat"], n["lon"], n["alt"],
                      n["place"], iso(ts), n["lat"], n["lon"], n["alt"], n["callsign"]))
            n["origin"] = None; n["first_seen_this_flight"] = iso(ts)
        else:
            c.execute("UPDATE sightings SET last_seen=?, last_lat=?, last_lon=?, last_alt=?, callsign=? WHERE hex=?", (iso(ts), n["lat"], n["lon"], n["alt"], n["callsign"], n["hex"]))
            n["first_seen_this_flight"] = r[0]
            low = r[2] in ("on the ground",) or (r[2] or "").endswith(" ft")
            n["origin"] = (f"observed departing {r[1]}" if low else f"first seen {et(datetime.fromisoformat(r[0].replace('Z','+00:00')))} {r[1]}, {r[2]} (departure not observed)")
        if n["category"] != "emergency":
            c.execute("INSERT OR IGNORE INTO notable_log VALUES(?,?,?,?,?,?,?,?,?)", (iso(ts), n["hex"], n["label"], n["category"], n["lat"], n["lon"], n["alt"], n["callsign"], n["place"]))
    # watch-key status (for honest "not seen" lines)
    keys_seen = {n.get("key") for n in notable}
    status = {}
    for k, lab in (("af1", "Air Force One airframes (VC-25A 82-8000/92-9000)"), ("e4b", "E-4B 'Doomsday' fleet"), ("e6b", "E-6B TACAMO fleet"),
                   ("c32", "C-32A/B VIP 757s (Air Force Two etc.)"), ("musk", "Elon Musk jets")):
        status[k] = {"label": lab, "seen": k in keys_seen}
    # persist run
    if ok:
        c.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?)", (iso(ts), 1, src, len(milset), f.calls, json.dumps({"by_region": by_region})))
        for hs, d in hs_counts.items():
            for cat in ("total", "tanker", "isr", "bomber", "airlift"):
                c.execute("INSERT OR REPLACE INTO hotspot_counts VALUES(?,?,?,?)", (iso(ts), hs, cat, d[cat]))
    else:
        c.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?)", (iso(ts), 0, None, 0, f.calls, "fetch failed"))
    c.execute("DELETE FROM hotspot_counts WHERE ts < ?", (iso(ts - timedelta(days=30)),))
    c.execute("DELETE FROM notable_log WHERE ts < ?", (iso(ts - timedelta(days=90)),))
    n_runs = c.execute("SELECT COUNT(*) FROM runs WHERE ok=1").fetchone()[0]
    c.commit(); c.close()
    srt = lambda d: dict(sorted(d.items(), key=lambda x: -x[1]))
    return {"generated_at": iso(ts), "generated_at_et": ts.astimezone(ET).strftime("%b %-d, %Y %-I:%M %p ET"), "ok": ok, "source": src,
            "api_calls": f.calls, "fetch_log": f.log, "military_total": len(milset), "military_with_position": sum(1 for a in milset.values() if num(a.get("lat")) is not None),
            "excluded_non_aircraft": excluded, "by_type": srt(by_type), "by_region": srt(by_region),
            "by_country": srt(by_country), "hotspots": hotspot_out, "anomalies": anomalies, "baseline_runs": n_runs,
            "baseline_building": building is not None and not anomalies and n_runs < 7, "notable": notable, "emergencies": emerg_out,
            "watch_status": status,
            "caveats": ["ADS-B positions are observed data from volunteer receivers (adsb.lol / adsb.fi).",
                        "Coverage is thin over Russia, China, Iran, much of Africa and open ocean; many military/VIP aircraft fly with ADS-B off or position hidden.",
                        "Not seen on ADS-B never means not flying. Purpose/passenger statements are inference."]}

# ---- report -----------------------------------------------------------------------------------------------------
def fmt_ac(n, with_why=True):
    bits = [n["label"]]
    if n.get("callsign"): bits.append(f"callsign {n['callsign']}")
    loc = n["place"] if n["has_position"] else n["place"]
    mv = f"{n['alt']}" + (f", heading {n['heading']}" if n.get("heading") and not n["ground"] else "") + (f", {int(n['speed_kt'])} kt" if n.get("speed_kt") and not n["ground"] else "")
    s = f"{', '.join(bits)}: {loc}, {mv}" if n["has_position"] else f"{', '.join(bits)}: {loc}"
    if n.get("origin"): s += f"; {n['origin']}"
    return s + f" ([track]({n['link']}))"

def report(r):
    if not r["ok"]:
        return ("**Aviation**\nADS-B feeds (adsb.lol and adsb.fi) did not respond this run, so there is no aviation snapshot this hour. "
                "This is a data outage, not a sign that nothing is flying.")
    N = r["notable"]; lines = []
    hijack = [e for e in r["emergencies"] if e["squawk"] == "7500"]
    af1 = [n for n in N if n.get("key") == "af1"]; af1cs = [n for n in N if (n.get("callsign") or "").upper() == "AF1"]
    e4 = [n for n in N if n.get("key") == "e4b"]; e6 = [n for n in N if n.get("key") == "e6b"]
    c32 = [n for n in N if n.get("key") in ("c32", "c40", "vipcs")]
    hos = [n for n in N if n["category"] == "head_of_state"]
    bil = [n for n in N if n["category"] in ("billionaire", "corporate")]
    bomb = [n for n in N if n["category"] == "military_strategic" and n.get("key") not in ("e4b", "e6b")]
    isr = [n for n in N if n["category"] == "isr"]; tank = [n for n in N if n["category"] == "tanker"]
    an, _hs = [], set()
    for a in sorted(r["anomalies"], key=lambda a: (a["cat"] == "total", -(a["n"] - a["median"]))):   # one line per hotspot, specific category first
        if a["hotspot"] not in _hs: an.append(a); _hs.add(a["hotspot"])
    # headline
    tops = ", ".join(f"{k} {v}" for k, v in list(r["by_type"].items())[:4] if k != "untyped")
    if hijack: head = f"Hijack code 7500 being squawked by {hijack[0]['label']} (unconfirmed; codes are sometimes set in error)."
    elif af1cs: head = "A jet using callsign AF1 is on ADS-B. Inference: the President is likely aboard, since that callsign is used only when he is."
    elif an: head = f"Unusual military concentration: {an[0]['n']} {an[0]['cat'] if an[0]['cat']!='total' else 'military'} aircraft near {an[0]['hotspot']} vs a typical {an[0]['median']:g}."
    elif af1: head = "An Air Force One airframe (VC-25A) is visible on ADS-B; whether the President is aboard is not known from this data."
    elif e4: head = f"{len(e4)} E-4B 'Doomsday plane' visible on ADS-B; these fly routine training sorties, so on its own this is not a warning sign."
    elif bomb: head = f"{len(bomb)} strategic bomber(s) visible on public ADS-B, plus {r['military_total']} military aircraft worldwide."
    else: head = f"{r['military_total']} military aircraft visible on public ADS-B worldwide; no unusual concentrations or emergency codes this hour."
    lines.append(f"**Aviation** ({r['generated_at_et']}): {head}")
    # emergencies
    if r["emergencies"]:
        e = r["emergencies"][:2]
        lines.append("- **Emergency squawks (observed):** " + "; ".join(f"{x['label']} {x['why']}, {x['place']}, {x['alt']} ([track]({x['link']}))" for x in e)
                     + (f"; +{len(r['emergencies'])-2} more" if len(r["emergencies"]) > 2 else ""))
    # presidential / doomsday
    if af1:
        inf = " Inference: presidential travel is possible, but VC-25As also fly training and positioning flights without him; callsign AF1 would mean he is aboard."
        if af1cs: inf = " Inference: callsign AF1 means the President is very likely aboard."
        lines.append("- **Presidential jet (observed):** " + fmt_ac(af1[0]) + inf)
    gov = []
    if e4: gov.append("E-4B " + fmt_ac(e4[0]))
    if e6: gov.append(f"{len(e6)} E-6B TACAMO (" + fmt_ac(e6[0]) + ")")
    if c32: gov.append(fmt_ac(c32[0]))
    if gov: lines.append("- **US VIP / nuclear command (observed):** " + "; ".join(gov[:2]))
    if not af1:
        miss = ["Air Force One (VC-25A)"] + ([] if e4 else ["E-4B"]) + ([] if e6 else ["E-6B"])
        lines.append(f"- **Not seen on public ADS-B:** {', '.join(miss)}. These often fly with position hidden or transponders off, so this does not mean they are on the ground.")
    # anomalies / hotspots
    if an:
        lines.append("- **Unusual concentrations (vs rolling baseline):** " + "; ".join(
            f"{a['hotspot']}: {a['n']} {a['cat'] if a['cat']!='total' else 'military'} aircraft vs typical {a['median']:g} ({a['basis']}, {a['samples']} samples) ([example]({GLOBE}{a['aircraft'][0].strip('~')}))" for a in an[:2]))
    hot = bomb + isr + tank
    if hot:
        lines.append("- **Strategic, ISR and tankers (observed):** " + "; ".join(f"{n['why']}: " + fmt_ac(n) for n in hot[:2]) + (f"; +{len(hot)-2} more" if len(hot) > 2 else ""))
    if hos: lines.append("- **Heads-of-state jets (observed):** " + "; ".join(fmt_ac(n) for n in hos[:2]))
    if bil: lines.append("- **Billionaire / corporate jets (observed):** " + "; ".join(fmt_ac(n) for n in bil[:2]) + (f"; +{len(bil)-2} more" if len(bil) > 2 else ""))
    else: lines.append("- **Billionaire jets:** none of the watched jets (Musk, Bezos, Gates, Zuckerberg, Trump 757, Swift, Abramovich) seen on ADS-B this hour; owners can use privacy hexes, so this doesn't mean they're grounded.")
    regs = ", ".join(f"{k} {v}" for k, v in [x for x in r["by_region"].items() if x[0] != "No position"][:4])
    ctry = ", ".join(f"{k} {v}" for k, v in list(r["by_country"].items())[:3])
    base = " Concentration baseline still building." if r["baseline_building"] else ""
    lines.append(f"- **Snapshot:** {r['military_total']} military aircraft on public ADS-B, {r['military_with_position']} with a position (by region: {regs}; by registry: {ctry}; top types: {tops or 'n/a'}). "
                 f"Emergency squawks: {len(r['emergencies']) or 'none'}.{base}")
    if len(lines) > 8:   # keep to 8 lines: drop lowest-priority bullets (billionaire 'none', not-seen) first
        for pref in ("- **Billionaire jets:**", "- **Not seen", "- **Heads-of-state"):
            if len(lines) <= 8: break
            lines = [l for l in lines if not l.startswith(pref)]
        lines = lines[:8]
    return "\n".join(lines)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--report", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(); r = run()
    if a.json: print(json.dumps(r, indent=1, default=list))
    if a.report or not a.json: print(report(r))
