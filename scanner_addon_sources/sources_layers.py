"""BLACKOUT.NETWORK layer sources (2026-11-18, pt1661u + follow-ups): rare signals, finance alerts, people.

Three layers, each adapter its own scanner source (own source_health row), names prefixed [rare] / [fin] / [people].
Rails, same pattern as sources_wide.py:
  * static URLs prefetched in parallel once per scan window (15 s timeout, no retry);
  * every adapter raises on failure -> scanner.scan() catches it per source; nothing here can crash a scan;
  * per-source item cap (CAP, default 8), max age, low base scores (a lone item never reaches push rank);
  * finance items are ALERTS ONLY: they fire on threshold breaks (index >=2%/day, VIX >30 or +20%, metals >=3%, BTC/ETH >=7%,
    stablecoin <0.98, curve inversion flips, HY spread spikes, each new $100B of national debt, circuit breakers);
  * kill switches: env BN_SOURCES_LAYERS=0 or file `sources_layers_off` next to this module (all off);
    keys in `sources_layers_disabled.json` (single adapters off, read every scan).
No keys, no logins, nothing behind bot checks. Public JSON/CSV/RSS only.
"""
import re, json, os, time, csv, io, gzip, math, urllib.parse
from datetime import timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import scanner as S

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (BlackoutNetwork early-warning research monitor; +https://blackout.network)"}
TIMEOUT = 15
CAP = 8
_CACHE = {"t": 0, "data": {}}
PV_CACHE = os.path.join(HERE, "sources_layers_pv_cache.json")

def enabled():
    return os.environ.get("BN_SOURCES_LAYERS", "1") != "0" and not os.path.exists(os.path.join(HERE, "sources_layers_off"))
def disabled_keys():
    try: return set(json.load(open(os.path.join(HERE, "sources_layers_disabled.json"))))
    except Exception: return set()

def _get(url, timeout=TIMEOUT, headers=None):
    r = requests.get(url, headers=headers or UA, timeout=timeout)
    r.raise_for_status()
    return r.content

def _fetch_one(url):
    try: return ("ok", _get(url, timeout=35 if "treasury.gov" in url else TIMEOUT))
    except Exception as ex: return ("err", f"{type(ex).__name__}: {str(ex)[:200]}")

def _urls(sp):
    u = sp.get("urls") or []
    return u() if callable(u) else u

def _prefetch():
    if time.time() - _CACHE["t"] < 240: return
    off = disabled_keys()
    urls = sorted({u for sp in SPECS if sp["key"] not in off for u in _urls(sp)})
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = dict(zip(urls, ex.map(_fetch_one, urls)))
    _CACHE.update(t=time.time(), data=res)

def fetch(url):
    _prefetch()
    st, v = _CACHE["data"].get(url) or _fetch_one(url)
    if st != "ok": raise RuntimeError(v)
    return v

def J(url): return json.loads(fetch(url))
def today(): return S.now().strftime("%Y-%m-%d")
def _f(x):
    try: return float(x)
    except Exception: return None

# =====================================================================================  A. RARE SIGNALS
def p_safecast(sp):
    """Safecast open radiation sensors: readings >= 350 CPM (~1 uSv/h, roughly 10x normal background) in the last 24 h."""
    out, seen = [], set()
    for m in J(sp["urls"][0]):
        if (m.get("unit") or "").lower() != "cpm": continue
        v = _f(m.get("value")) or 0
        if v < 350 or v > 100000: continue   # >100k CPM is a sensor fault / test source
        t = S.parse_t(m.get("captured_at"))
        if not t or t < S.now() - timedelta(hours=24): continue
        lat, lon = _f(m.get("latitude")), _f(m.get("longitude"))
        if lat is None or lon is None: continue
        cell = (round(lat, 1), round(lon, 1))
        if cell in seen: continue
        seen.add(cell)
        usv = v / 334.0
        out.append(S.item(sp["name"], "Safecast", f"{cell}|{t:%Y-%m-%d}", f"Elevated radiation reading: {v:.0f} CPM (~{usv:.1f} µSv/h) on a Safecast sensor near {lat:.2f}, {lon:.2f}",
                          "natural disaster", f"https://map.safecast.org/?y={lat}&x={lon}&z=12", t, lat, lon, None, 6 + min(20, usv * 2), official=False,
                          extra={"cpm": v, "usv_h": round(usv, 2), "layer": "rare", "kind": "radiation", "note": "crowd-sourced sensor; single readings can be faulty"}))
    return out

def _usgs_expl_url():
    d = (S.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    return ["https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=nuclear%20explosion,explosion,chemical%20explosion,"
            f"mine%20collapse,sonic%20boom,rock%20burst&starttime={d}"]
def p_usgs_expl(sp):
    """USGS events typed as explosions (nuclear/chemical/other), mine collapses, sonic booms. Quarry blasts excluded."""
    out = []
    for f in J(_urls(sp)[0]).get("features", []):
        p = f["properties"]; lon, lat, _d = f["geometry"]["coordinates"]; typ = p.get("type") or "explosion"
        m = p.get("mag") or 0
        base = 60 if typ == "nuclear explosion" else 8 + max(0, m - 2) * 6
        cat = "war/conflict" if typ == "nuclear explosion" else "natural disaster"
        out.append(S.item(sp["name"], "USGS", f["id"], f"USGS seismic event typed '{typ}': M{m} {p.get('place') or ''}".strip(), cat, p.get("url"),
                          datetime.fromtimestamp(p["time"] / 1000, timezone.utc), lat, lon, p.get("place"), base,
                          extra={"mag": m, "etype": typ, "layer": "rare", "kind": "explosion"}))
    return out

SQK = {"7500": ("hijack (unlawful interference)", 30), "7600": ("radio failure", 5), "7700": ("general emergency", 12)}
def p_squawk(sp):
    """adsb.lol open ADS-B API: aircraft currently squawking 7500 / 7600 / 7700."""
    out = []
    for url in sp["urls"]:
        code = url.rsplit("/", 1)[1]; what, base = SQK[code]
        for a in J(url).get("ac", []):
            fl = (a.get("flight") or "").strip() or a.get("r") or a.get("hex")
            lat, lon = a.get("lat"), a.get("lon")
            alt = a.get("alt_baro")
            out.append(S.item(sp["name"], "ADS-B", f"{a.get('hex')}|{code}|{today()}", f"Aircraft {fl} ({a.get('t') or 'type n/a'}) squawking {code}: {what}",
                              "natural disaster", f"https://globe.adsb.lol/?icao={a.get('hex')}", S.now(), lat, lon, None, base, official=False,
                              extra={"squawk": code, "alt_baro": alt, "reg": a.get("r"), "type": a.get("t"), "layer": "rare", "kind": "aviation emergency"}))
    return out

MIL_TYPES = {"E4": "E-4B 'Nightwatch' doomsday plane", "E6": "E-6B Mercury (TACAMO nuclear command relay)", "B52": "B-52 bomber",
             "B1": "B-1B bomber", "B2": "B-2 stealth bomber", "RC35": "RC-135 reconnaissance", "R135": "RC-135 reconnaissance",
             "E3TF": "E-3 AWACS", "E3CF": "E-3 AWACS", "U2": "U-2 spy plane", "RQ4": "RQ-4 Global Hawk drone", "Q4": "RQ-4 Global Hawk drone",
             "MQ9": "MQ-9 Reaper drone", "P8": "P-8 Poseidon sub hunter", "E8": "E-8 JSTARS", "C32": "C-32 (VIP/Air Force Two class)",
             "VC25": "VC-25 (Air Force One class)", "WC35": "WC-135 'nuke sniffer'", "KE3": "KE-3 tanker", "A400": "A400M airlifter"}
def p_mil(sp):
    """adsb.lol open ADS-B API: notable military aircraft currently broadcasting (bombers, nuclear C2, ISR). One item per tail per day."""
    out = []
    for a in J(sp["urls"][0]).get("ac", []):
        t = (a.get("t") or "").upper()
        if t not in MIL_TYPES: continue
        if a.get("lat") is None: continue
        fl = (a.get("flight") or "").strip() or a.get("r") or a.get("hex")
        base = 14 if t in ("E4", "E6", "WC35", "VC25") else 6
        out.append(S.item(sp["name"], "ADS-B", f"{a.get('hex')}|{today()}", f"Military flight tracked: {MIL_TYPES[t]} {fl} airborne",
                          "war/conflict", f"https://globe.adsb.lol/?icao={a.get('hex')}", S.now(), a.get("lat"), a.get("lon"), None, base, official=False,
                          extra={"type": t, "reg": a.get("r"), "alt_baro": a.get("alt_baro"), "layer": "rare", "kind": "military flight"}))
    return out

def p_gpsjam(sp):
    """GPSJam (ADS-B derived GNSS interference): daily count of high-interference hexes; flags surges vs the 7-day median."""
    raw = fetch(sp["urls"][0])
    try: raw = gzip.decompress(raw)
    except Exception: pass
    rows = [r for r in csv.reader(io.StringIO(raw.decode("utf-8", "replace"))) if r and re.match(r"\d{4}-\d\d-\d\d", r[0])]
    rows = rows[-8:]
    if len(rows) < 3: return []
    d, _sus, n = rows[-1][0], rows[-1][1], int(rows[-1][2] or 0)
    prev = sorted(int(r[2] or 0) for r in rows[:-1]); med = prev[len(prev) // 2] or 1
    surge = n >= med * 1.3
    title = (f"GNSS jamming surge: {n} high-interference zones on {d} vs {med} typical (GPSJam)" if surge
             else f"GNSS interference daily: {n} high-interference zones worldwide on {d} (GPSJam)")
    return [S.item(sp["name"], "GPSJam", d, title, "war/conflict", f"https://gpsjam.org/?date={d}", S.parse_t(d + "T23:59:00Z"),
                   location="Global", base=12 if surge else 3, official=False, extra={"hexes": n, "median7": med, "layer": "rare", "kind": "gnss interference"})]

def p_ndbc(sp):
    """NOAA NDBC buoys (latest obs): wave height >= 9 m or pressure <= 965 hPa (hurricane-strength)."""
    out = []
    for line in fetch(sp["urls"][0]).decode("utf-8", "replace").splitlines():
        if line.startswith("#"): continue
        c = line.split()
        if len(c) < 16: continue
        try:
            stn, lat, lon = c[0], float(c[1]), float(c[2])
            t = datetime(int(c[3]), int(c[4]), int(c[5]), int(c[6]), int(c[7]), tzinfo=timezone.utc)
        except Exception: continue
        if t < S.now() - timedelta(hours=6): continue
        wv, pr = _f(c[11]) if c[11] != "MM" else None, _f(c[15]) if c[15] != "MM" else None
        if (wv or 0) >= 9 or (pr and pr <= 965):
            bits = ([f"waves {wv:.1f} m"] if wv else []) + ([f"pressure {pr:.0f} hPa"] if pr else [])
            out.append(S.item(sp["name"], "NOAA", f"{stn}|{t:%Y%m%d%H}", f"NOAA buoy {stn} extreme reading: {', '.join(bits)}", "natural disaster",
                              f"https://www.ndbc.noaa.gov/station_page.php?station={stn}", t, lat, lon, None, 8 + (8 if (wv or 0) >= 12 or (pr and pr <= 950) else 0),
                              extra={"wvht_m": wv, "pres_hpa": pr, "layer": "rare", "kind": "ocean buoy"}))
    return out

def p_vaac(sp):
    """Volcanic ash SIGMETs (international, via aviationweather.gov): ash clouds that affect flights."""
    out = []
    for s in J(sp["urls"][0]):
        if s.get("hazard") != "VA": continue
        pts = s.get("coords") or []
        lat = sum(p["lat"] for p in pts) / len(pts) if pts else None; lon = sum(p["lon"] for p in pts) / len(pts) if pts else None
        volc = (s.get("qualifier") or "unnamed volcano").title()
        top = s.get("top")
        out.append(S.item(sp["name"], "VAAC", f"{volc}|{today()}",
                          f"Volcanic ash advisory: {volc} ash cloud{f' up to {top:,} ft' if top else ''} ({s.get('firName') or s.get('firId')})",
                          "natural disaster", "https://aviationweather.gov/gfa/#sigmet", datetime.fromtimestamp(s.get("validTimeFrom") or time.time(), timezone.utc),
                          lat, lon, s.get("firName"), 10 + (8 if (top or 0) >= 30000 else 0), extra={"top_ft": top, "layer": "rare", "kind": "volcanic ash"}))
    return out

def p_decay(sp):
    """CelesTrak 'decaying' catalog: objects with mean motion >= 16.2 rev/day are days from re-entry."""
    out = []
    for o in J(sp["urls"][0]):
        mm = _f(o.get("MEAN_MOTION")) or 0
        if mm < 16.2: continue
        nm = o.get("OBJECT_NAME") or "object"
        alt = (398600.4418 / ((mm * 2 * math.pi / 86400) ** 2)) ** (1 / 3) - 6378.137
        out.append(S.item(sp["name"], "CelesTrak", f"{o.get('NORAD_CAT_ID')}", f"Re-entry watch: {nm} ({o.get('OBJECT_ID')}) down to ~{alt:.0f} km, re-entry expected within days",
                          "other", f"https://celestrak.org/satcat/table-satcat.php?CATNR={o.get('NORAD_CAT_ID')}", S.parse_t(o.get("EPOCH")), location="Low Earth orbit",
                          base=4 + (6 if re.search(r"R/B|ROCKET|CZ-|FALCON|STARSHIP|STATION|TIANGONG", nm, re.I) else 0), official=False,
                          extra={"mean_motion": mm, "alt_km": round(alt), "layer": "rare", "kind": "reentry"}))
    return out

# =====================================================================================  B. FINANCE (alerts only)
YSYM = [  # symbol, label, kind, threshold %
    ("^GSPC", "S&P 500", "idx", 2), ("^DJI", "Dow Jones", "idx", 2), ("^IXIC", "Nasdaq", "idx", 2), ("^RUT", "Russell 2000", "idx", 2.5),
    ("^N225", "Nikkei 225", "idx", 2.5), ("^FTSE", "FTSE 100", "idx", 2), ("^GDAXI", "DAX", "idx", 2), ("^FCHI", "CAC 40", "idx", 2),
    ("^HSI", "Hang Seng", "idx", 2.5), ("000001.SS", "Shanghai Composite", "idx", 2.5), ("^STOXX50E", "Euro Stoxx 50", "idx", 2),
    ("^KS11", "KOSPI", "idx", 2.5), ("^BSESN", "Sensex", "idx", 2.5), ("^BVSP", "Bovespa", "idx", 2.5),
    ("GC=F", "Gold", "metal", 3), ("SI=F", "Silver", "metal", 3), ("PL=F", "Platinum", "metal", 4), ("HG=F", "Copper", "metal", 4),
    ("CL=F", "WTI crude", "energy", 5), ("BZ=F", "Brent crude", "energy", 5), ("NG=F", "Natural gas", "energy", 8),
    ("DX-Y.NYB", "US Dollar Index", "fx", 1.2), ("JPY=X", "USD/JPY", "fx", 1.5), ("EURUSD=X", "EUR/USD", "fx", 1.2), ("CNY=X", "USD/CNY", "fx", 0.8),
    ("^VIX", "VIX", "vol", 20), ("^MOVE", "MOVE bond volatility", "vol", 15),
]
def _yurl(): return ["https://query2.finance.yahoo.com/v7/finance/spark?" + urllib.parse.urlencode({"symbols": ",".join(s for s, *_ in YSYM[i:i + 20]), "range": "5d", "interval": "1d"})
                     for i in range(0, len(YSYM), 20)]
def p_ymoves(sp):
    """Daily moves on indices, metals, energy, FX, VIX, MOVE (Yahoo spark, delayed). Fires only past each symbol's threshold."""
    meta = {s: (l, k, th) for s, l, k, th in YSYM}; out = []
    for url in _urls(sp):
        for r in J(url).get("spark", {}).get("result", []):
            sym = r.get("symbol"); resp = (r.get("response") or [{}])[0]; m = resp.get("meta") or {}
            closes = [c for c in (((resp.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if c is not None]
            px = m.get("regularMarketPrice") or (closes[-1] if closes else None)
            prev = m.get("chartPreviousClose") if len(closes) < 2 else closes[-2]
            if sym not in meta or not px or not prev: continue
            lab, kind, th = meta[sym]; pct = (px / prev - 1) * 100
            mt = datetime.fromtimestamp(m.get("regularMarketTime") or time.time(), timezone.utc)
            day = mt.astimezone(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d")
            fire, why = abs(pct) >= th, ""
            if sym == "^VIX" and px >= 30: fire, why = True, " (above 30: fear zone)"
            if sym == "^MOVE" and px >= 140: fire, why = True, " (above 140: bond stress)"
            if not fire: continue
            word = ("surges" if pct > 0 else "plunges") if abs(pct) >= th * 1.5 else ("jumps" if pct > 0 else "falls")
            lvl = f"{px:,.2f}" if px < 1000 else f"{px:,.0f}"
            base = 6 + min(14, abs(pct) / th * 4)
            out.append(S.item(sp["name"], "Markets", f"{sym}|{day}|{'up' if pct > 0 else 'dn'}", f"{lab} {word} {pct:+.1f}% to {lvl}{why}", "financial",
                              f"https://blackout.network/markets", mt, location="Global markets", base=base, official=False,
                              extra={"sym": sym, "pct": round(pct, 2), "price": px, "layer": "finance", "kind": kind, "threshold_pct": th, "delayed": True}))
    return out

STABLES = {"tether", "usd-coin", "dai", "ethena-usde", "first-digital-usd", "paypal-usd", "usds", "true-usd", "frax", "usdd"}
def p_crypto(sp):
    """CoinGecko top 50: BTC/ETH +-7%/24h, other top-20 coins +-15%, any stablecoin under $0.98 or over $1.02 (depeg)."""
    out = []
    for i, c in enumerate(J(sp["urls"][0])):
        pct = c.get("price_change_percentage_24h") or 0; px = c.get("current_price") or 0; cid = c.get("id")
        t = S.parse_t(c.get("last_updated")) or S.now()
        if cid in STABLES or (c.get("symbol") or "").lower() in ("usdt", "usdc", "dai", "usde", "fdusd", "pyusd", "usds", "tusd"):
            if 0 < px < 0.98 or px > 1.02:
                out.append(S.item(sp["name"], "CoinGecko", f"depeg|{cid}|{today()}", f"Stablecoin depeg: {c.get('name')} trading at ${px:.4f}", "financial",
                                  f"https://www.coingecko.com/en/coins/{cid}", t, location="Global (crypto)", base=20 if px < 0.95 else 10, official=False,
                                  extra={"price": px, "layer": "finance", "kind": "stablecoin"}))
            continue
        th = 7 if cid in ("bitcoin", "ethereum") else 15
        if i >= 25 or abs(pct) < th: continue
        out.append(S.item(sp["name"], "CoinGecko", f"{cid}|{today()}|{'up' if pct > 0 else 'dn'}", f"{c.get('name')} {'surges' if pct > 0 else 'plunges'} {pct:+.1f}% in 24h to ${px:,.2f}",
                          "financial", f"https://www.coingecko.com/en/coins/{cid}", t, location="Global (crypto)", base=6 + min(12, abs(pct) / th * 4), official=False,
                          extra={"pct": round(pct, 2), "price": px, "layer": "finance", "kind": "crypto"}))
    return out

def _ust_url():
    y = S.now().year
    return [f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv"]
def p_curve(sp):
    """US Treasury daily par yield curve (official, end of day): 10y-2y / 10y-3m inversion flips, 10y moves >= 20 bp."""
    rows = list(csv.DictReader(io.StringIO(fetch(_urls(sp)[0]).decode("utf-8", "replace"))))
    if len(rows) < 2: return []
    a, b = rows[0], rows[1]   # newest first
    g = lambda r, k: _f(r.get(k))
    out = []; d = datetime.strptime(a["Date"], "%m/%d/%Y").replace(hour=21, tzinfo=timezone.utc)
    for short, lab in (("2 Yr", "10y-2y"), ("3 Mo", "10y-3m")):
        s0, s1 = (g(a, "10 Yr") or 0) - (g(a, short) or 0), (g(b, "10 Yr") or 0) - (g(b, short) or 0)
        if (s0 < 0) != (s1 < 0):
            out.append(S.item(sp["name"], "US Treasury", f"{lab}|{a['Date']}", f"Yield curve {'INVERTS' if s0 < 0 else 'un-inverts'}: {lab} spread {s1*100:+.0f} bp -> {s0*100:+.0f} bp",
                              "financial", "https://home.treasury.gov/resource-center/data-chart-center/interest-rates", d, location="United States", base=12,
                              extra={"spread_bp": round(s0 * 100), "layer": "finance", "kind": "yield curve"}))
    dy = ((g(a, "10 Yr") or 0) - (g(b, "10 Yr") or 0)) * 100
    if abs(dy) >= 20:
        out.append(S.item(sp["name"], "US Treasury", f"10y|{a['Date']}", f"US 10-year Treasury yield {'spikes' if dy > 0 else 'drops'} {dy:+.0f} bp to {g(a, '10 Yr'):.2f}%",
                          "financial", "https://home.treasury.gov/resource-center/data-chart-center/interest-rates", d, location="United States", base=10,
                          extra={"move_bp": round(dy), "layer": "finance", "kind": "yields"}))
    return out

def p_debt(sp):
    """Treasury Debt to the Penny (official, daily): one item each time total public debt crosses a new $100B milestone."""
    rows = J(sp["urls"][0]).get("data", [])
    if len(rows) < 2: return []
    a, b = float(rows[0]["tot_pub_debt_out_amt"]), float(rows[1]["tot_pub_debt_out_amt"])
    out = []; step = 1e11
    for k in range(int(b // step) + 1, int(a // step) + 1):
        lvl = k * step
        out.append(S.item(sp["name"], "US Treasury", f"debt|{k}", f"U.S. national debt crosses ${lvl/1e12:.1f} trillion (official total ${a/1e12:,.3f}T on {rows[0]['record_date']})",
                          "financial", "https://blackout.network/markets#debt", S.parse_t(rows[0]["record_date"] + "T20:00:00Z"), location="United States", base=6,
                          extra={"debt": a, "prev": b, "day_change": a - b, "layer": "finance", "kind": "national debt"}))
    return out

def p_hy(sp):
    """ICE BofA US High Yield spread (FRED public CSV, keyless graph export): >= 6.0% or +40 bp in a day = credit stress."""
    rows = [r for r in csv.reader(io.StringIO(fetch(sp["urls"][0]).decode())) if r and r[0][:2] == "20" and r[1] not in (".", "")]
    if len(rows) < 2: return []
    d, v = rows[-1][0], float(rows[-1][1]); dv = (v - float(rows[-2][1])) * 100
    if v < 6.0 and dv < 40: return []
    return [S.item(sp["name"], "FRED", f"hy|{d}", f"Credit stress: US junk-bond spread at {v:.2f}% ({dv:+.0f} bp on the day)", "financial",
                   "https://fred.stlouisfed.org/series/BAMLH0A0HYM2", S.parse_t(d + "T21:00:00Z"), location="United States", base=8 + (8 if v >= 8 else 0),
                   extra={"spread_pct": v, "move_bp": round(dv), "layer": "finance", "kind": "credit spreads"})]

def p_halts(sp):
    """Nasdaq Trader trading halts RSS: market-wide circuit breakers (MWCB levels 1-3) always; single-stock halts only for news/volatility on big caps."""
    out = []
    raw = fetch(sp["urls"][0]).decode("utf-8", "replace")
    for e in S.rss_items(raw):
        txt = S.strip((e.get("title") or "") + " " + (e.get("description") or ""))
        mw = re.search(r"\bMWC[123]\b|market[- ]wide circuit", txt, re.I)
        if not mw: continue
        out.append(S.item(sp["name"], "Nasdaq", e.get("guid") or txt[:80], f"Market-wide circuit breaker: {txt[:180]}", "financial",
                          "https://www.nasdaqtrader.com/trader.aspx?id=TradeHalts", S.parse_t(e.get("pubDate")) or S.now(), location="United States", base=40,
                          extra={"layer": "finance", "kind": "circuit breaker"}))
    return out

# =====================================================================================  C. PEOPLE
ROLE = (r"\b(president|prime minister|premier|chancellor|vice president|king|queen|prince|princess|crown prince|emperor|pope|cardinal|ayatollah|"
        r"supreme leader|dictator|monarch|sultan|emir|senator|congressman|congresswoman|representative|governor|mayor of|minister|secretary of|"
        r"speaker|chief justice|justice|judge|general|admiral|commander|chief of staff|ceo|founder|billionaire|tycoon|oligarch|leader|"
        r"opposition leader|head of state|ambassador|attorney general|director of|nobel|former (president|prime minister|leader|senator|governor))\b")
EVENT = (r"\b(assassinat\w*|assassination attempt|shot|stabbed|attacked|killed|murdered|dies|died|dead at|death of|passes away|"
         r"arrested|detained|indicted|charged|convicted|sentenced|extradited|impeach\w*|resigns?|resignation|steps down|ousted|deposed|coup|"
         r"hospitali[sz]ed|in intensive care|critical condition|health scare|surgery|threat(?:s|ened)? (?:to|against)|plot to (?:kill|kidnap)|kidnapp\w*|"
         r"marries|married|divorc\w*|abdicat\w*|sworn in|exiled|flees|defects?)\b")
FLUFF = (r"\b(outfit|fashion|dress(?:es)?|red carpet|look(?:s)? stunning|dating|boyfriend|girlfriend|rumou?red romance|engagement ring|mansion|"
         r"buys|bought|net worth|tiktok|instagram post|selfie|reality (?:tv|show)|bachelor|kardashian|album|tour dates|box office|trailer|"
         r"recipe|horoscope|celebrity|grammy|oscars?|emmy|fans react|viral|meme|podcast|quiz|sport|nfl|nba|mlb|nhl|fifa|transfer)\b")
MARRIAGE_OK = r"\b(president|prime minister|king|queen|prince|princess|crown prince|pope|emperor|billionaire|head of state)\b"

def people_ok(t):
    if re.search(FLUFF, t, re.I): return False
    if not (re.search(ROLE, t, re.I) and re.search(EVENT, t, re.I)): return False
    if re.search(r"\b(marries|married|divorc\w*)\b", t, re.I) and not re.search(MARRIAGE_OK, t, re.I): return False
    return True

def _pv_load():
    try: return json.load(open(PV_CACHE))
    except Exception: return {}
def pageviews(title, cache):
    """Max daily views (last 4 days) of an English Wikipedia article; cached 6 h on disk. Wikimedia REST API, keyless."""
    k = title.replace(" ", "_"); c = cache.get(k)
    if c and time.time() - c[1] < 6 * 3600: return c[0]
    e = S.now() - timedelta(days=1); s = e - timedelta(days=4)
    try:
        j = json.loads(_get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{urllib.parse.quote(k, safe='')}"
                            f"/daily/{s:%Y%m%d}/{e:%Y%m%d}", timeout=8))
        v = max((x.get("views") or 0) for x in j.get("items", [])) if j.get("items") else 0
    except Exception: v = 0
    cache[k] = [v, time.time()]
    return v

def _deaths_url(): return [f"https://en.wikipedia.org/w/api.php?action=parse&page=Deaths_in_{S.now():%Y}&prop=wikitext&format=json&formatversion=2&section=" + ""]
def p_deaths(sp):
    """Wikipedia 'Deaths in <year>' (current month section): deaths in the last 3 days; notability gate = article pageviews >= 25,000/day."""
    url = f"https://en.wikipedia.org/w/api.php?action=parse&page=Deaths_in_{S.now():%B}_{S.now():%Y}&prop=wikitext&format=json&formatversion=2&redirects=1"
    wt = json.loads(_get(url, timeout=TIMEOUT)).get("parse", {}).get("wikitext") or ""
    mon = S.now().strftime("%B")
    m = re.search(r"==\s*" + mon + r"\s*==(.*?)(\n==[^=]|\Z)", wt, re.S)
    sec = m.group(1) if m else wt
    days = {(S.now() - timedelta(days=i)).day for i in range(3)}
    out, cache, n = [], _pv_load(), 0
    for dm in re.finditer(r"===\s*(\d{1,2})\s*===(.*?)(?====|\Z)", sec, re.S):
        day = int(dm.group(1))
        if day not in days: continue
        for line in dm.group(2).splitlines():
            lm = re.match(r"\*\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\],\s*(\d+)?,?\s*(.*)", line.strip())
            if not lm: continue
            if n >= 60: break
            art, nm, age, desc = lm.group(1), lm.group(2) or lm.group(1), lm.group(3), re.sub(r"<ref.*?(</ref>|/>)|\{\{.*?\}\}|\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", lambda x: x.group(2) or "", lm.group(4)).strip(" .")
            n += 1
            pv = pageviews(art, cache)
            if pv < 25000: continue
            nm = re.sub(r"\s*\(.*?\)", "", nm)
            t = datetime(S.now().year, S.now().month, day, 12, tzinfo=timezone.utc)
            out.append(S.item(sp["name"], "Wikipedia", art, f"Death: {nm}{f', {age},' if age else ''} {desc[:140]}".strip(", "), "people",
                              "https://en.wikipedia.org/wiki/" + urllib.parse.quote(art.replace(" ", "_")), t, location=None,
                              base=6 + min(14, pv / 50000), official=False, extra={"pageviews_day": pv, "layer": "people", "kind": "death"}))
    try: json.dump(cache, open(PV_CACHE, "w"))
    except Exception: pass
    return out

def p_portal(sp):
    """Wikipedia Current Events portal (today + yesterday): bullets about notable people (attacks, arrests, resignations, deaths, coups, health)."""
    out = []
    for i in range(2):
        d = S.now() - timedelta(days=i)
        url = f"https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events/{d:%Y}_{d:%B}_{d.day}&prop=wikitext&format=json&formatversion=2"
        try: wt = json.loads(_get(url, timeout=TIMEOUT)).get("parse", {}).get("wikitext") or ""
        except Exception: continue
        for line in wt.splitlines():
            if not line.startswith("*"): continue
            txt = re.sub(r"\[https?://\S+ \(([^)]*)\)\]", "", line.lstrip("* "))
            txt = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", txt); txt = re.sub(r"'''?|\{\{.*?\}\}|<.*?>", "", txt).strip()
            if len(txt) < 40 or not people_ok(txt): continue
            src = re.search(r"\[(https?://\S+) \(", line)
            out.append(S.item(sp["name"], "Wikipedia", f"{d:%Y%m%d}|{txt[:80]}", txt[:300], "people", src.group(1) if src else
                              f"https://en.wikipedia.org/wiki/Portal:Current_events/{d:%Y}_{d:%B}_{d.day}", d, base=8, official=False,
                              extra={"layer": "people", "kind": "current events"}))
    return out

PQ = ['"assassination attempt" OR assassinated OR "plot to kill"',
      '(president OR "prime minister" OR senator OR governor OR minister OR judge) (arrested OR indicted OR charged OR sentenced)',
      '(president OR "prime minister" OR minister OR governor OR CEO OR "chief executive") (resigns OR "steps down" OR ousted OR impeached)',
      '(president OR "prime minister" OR king OR queen OR pope OR "supreme leader") (hospitalized OR "intensive care" OR "health scare" OR dies)',
      '(threat OR threatened OR attack) (senator OR congressman OR congresswoman OR judge OR governor OR mayor) arrested']
def _pq_urls(): return ["https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"}) for q in PQ]
def p_gnews_people(sp):
    """Google News RSS keyword searches, kept only when the headline names a prominent role AND a high-impact event; pop-culture fluff dropped."""
    out, seen = [], set()
    for url in _urls(sp):
        for e in S.rss_items(fetch(url))[:30]:
            title = S.strip(e.get("title")); t = S.parse_t(e.get("pubDate"))
            if not title or not t or t < S.now() - timedelta(hours=36): continue
            core = re.sub(r"\s+-\s+[^-]+$", "", title)
            k = re.sub(r"[^a-z0-9 ]", "", core.lower())[:70]
            if k in seen or not people_ok(core): continue
            seen.add(k)
            assas = re.search(r"assassinat|plot to kill|shot|stabbed", core, re.I)
            out.append(S.item(sp["name"], "Google News", e.get("link") or core, title, "people", e.get("link"), t, base=10 if assas else 6, official=False,
                              extra={"layer": "people", "kind": "news", "tier": "news"}))
    return out

def p_protect(sp):
    """US Secret Service + US Capitol Police press: threats/attacks on officials and protectees, arrests."""
    out = []
    for url in sp["urls"]:
        for e in S.rss_items(fetch(url)):
            t = S.parse_t(e.get("pubDate")); title = S.strip(e.get("title")); desc = S.strip(e.get("description"))[:400]
            if not t or t < S.now() - timedelta(days=4) or not title: continue
            if not re.search(r"threat|arrest|charged|assault|attack|shooting|weapon|gun|protectee|sentenced|plead|indict|security incident|breach", title + " " + desc, re.I): continue
            out.append(S.item(sp["name"], "USSS" if "secretservice" in url else "USCP", e.get("guid") or e.get("link") or title, title, "people",
                              e.get("link") or url, t, location="United States", base=8, extra={"desc": desc[:300], "layer": "people", "kind": "protective"}))
    return out

# =====================================================================================  registry
def R(key, name, parse, urls, cap=CAP, layer="rare"): return dict(key=key, name=name, parse=parse, urls=urls, cap=cap, layer=layer)
TAG = {"rare": "[rare]", "finance": "[fin]", "people": "[people]"}
SPECS = [
    R("safecast", "Safecast radiation sensors", p_safecast, ["https://api.safecast.org/measurements.json?order=created_at+desc&per_page=500"], 5),
    R("usgs_expl", "USGS explosion-type seismic events", p_usgs_expl, _usgs_expl_url),
    R("adsb_squawk", "ADS-B emergency squawks 7500/7600/7700 (adsb.lol)", p_squawk, ["https://api.adsb.lol/v2/sqk/7500", "https://api.adsb.lol/v2/sqk/7600", "https://api.adsb.lol/v2/sqk/7700"], 10),
    R("adsb_mil", "ADS-B notable military aircraft (adsb.lol)", p_mil, ["https://api.adsb.lol/v2/mil"], 10),
    R("gpsjam", "GPSJam GNSS interference (daily)", p_gpsjam, ["https://gpsjam.org/data/manifest.csv"], 1),
    R("ndbc", "NOAA NDBC ocean buoys (extremes)", p_ndbc, ["https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"]),
    R("vaac", "Volcanic ash SIGMETs (VAAC, aviationweather.gov)", p_vaac, ["https://aviationweather.gov/api/data/isigmet?format=json"]),
    R("celestrak_decay", "CelesTrak decaying objects (re-entry watch)", p_decay, ["https://celestrak.org/NORAD/elements/gp.php?SPECIAL=DECAYING&FORMAT=json"], 5),
    R("fin_moves", "Market moves: indices, metals, energy, FX, VIX, MOVE", p_ymoves, _yurl, 12, "finance"),
    R("fin_crypto", "Crypto moves + stablecoin depegs (CoinGecko)", p_crypto, ["https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&price_change_percentage=24h"], 8, "finance"),
    R("fin_curve", "US Treasury yield curve (inversions, 10y moves)", p_curve, _ust_url, 4, "finance"),
    R("fin_debt", "US national debt milestones (Debt to the Penny)", p_debt, ["https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?sort=-record_date&page%5Bsize%5D=5"], 3, "finance"),
    R("fin_hy", "US high-yield credit spread (FRED CSV)", p_hy, ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"], 1, "finance"),
    R("fin_halts", "Market-wide circuit breakers (Nasdaq Trader halts)", p_halts, ["https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"], 3, "finance"),
    R("people_deaths", "Notable deaths (Wikipedia + pageviews gate)", p_deaths, [], 8, "people"),
    R("people_portal", "Wikipedia Current Events: people", p_portal, [], 8, "people"),
    R("people_news", "People: high-impact news (Google News, filtered)", p_gnews_people, _pq_urls, 10, "people"),
    R("people_protect", "Secret Service + Capitol Police press", p_protect, ["https://www.secretservice.gov/rss.xml", "https://www.uscp.gov/rss.xml"], 6, "people"),
]

def make(sp):
    def fn():
        if sp["key"] in disabled_keys(): return [], {"disabled": True}
        items = sp["parse"](sp)
        seen, out = set(), []
        items.sort(key=lambda x: (x.get("base") or 0, x.get("event_time") or ""), reverse=True)
        for it in items:
            if it["id"] in seen: continue
            seen.add(it["id"]); out.append(it)
            if len(out) >= sp["cap"]: break
        return out, ({"fetched": len(items), "kept": len(out)} if len(items) != len(out) else {})
    return fn

def sources():
    if not enabled(): return []
    return [(f"{TAG[sp['layer']]} {sp['name']}", (_urls(sp) or ["https://blackout.network/sources"])[0], make(sp)) for sp in SPECS]

LAYER_SOURCES = sources()
