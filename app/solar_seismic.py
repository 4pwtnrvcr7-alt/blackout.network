"""Solar & Seismic add-on: NOAA SWPC space weather + USGS earthquakes + tsunami.gov bulletins, and a 'correlation lab'.
Read-only against blackout.db (mode=ro). Its own evidence log lives in solar_seismic.db (3-hour bins, quakes, SWPC alerts, fetch log).
Upstream fetches are cached and refreshed at most once every 5 minutes; a background logger keeps bins growing every 30 minutes.
Never touches scanner.py, scoring, push.py, jets.py or config.json. Observed patterns only: nothing here claims causation."""
import hashlib, json, math, os, re, sqlite3, sys, threading, time, zlib
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
SDB = os.path.join(BASE, "solar_seismic.db")
STATIC = os.path.join(BASE, "solar_seismic_static")
TTL = 300                    # seconds: upstream fetched at most once every 5 minutes
STORM_KP = 4.67              # Kp 5- : NOAA G1 threshold
UA = "BlackoutNetwork-SolarSeismic/1.0 (private research dashboard)"
SW = "https://services.swpc.noaa.gov"
EQ = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
SOURCES = {  # key: (label, url, max_bytes)
    "alerts":   ("NOAA SWPC alerts, watches & warnings", f"{SW}/products/alerts.json"),
    "kp":       ("NOAA planetary K index (3-hour, 7 days)", f"{SW}/products/noaa-planetary-k-index.json"),
    "kp1m":     ("NOAA estimated Kp (1-minute)", f"{SW}/json/planetary_k_index_1m.json"),
    "scales":   ("NOAA space weather scales (R/S/G)", f"{SW}/products/noaa-scales.json"),
    "xray":     ("GOES X-ray flux (7 days)", f"{SW}/json/goes/primary/xrays-7-day.json"),
    "flares":   ("GOES X-ray flare list (7 days)", f"{SW}/json/goes/primary/xray-flares-7-day.json"),
    "wind_now": ("Solar wind speed (summary)", f"{SW}/products/summary/solar-wind-speed.json"),
    "mag_now":  ("Interplanetary magnetic field Bt/Bz (summary)", f"{SW}/products/summary/solar-wind-mag-field.json"),
    "wind1m":   ("Real-time solar wind plasma (1-minute, 24 h)", f"{SW}/json/rtsw/rtsw_wind_1m.json"),
    "mag1m":    ("Real-time solar wind magnetic field (1-minute, 24 h)", f"{SW}/json/rtsw/rtsw_mag_1m.json"),
    "eq":       ("USGS earthquakes M2.5+, past week", f"{EQ}/2.5_week.geojson"),
    "eq_sig":   ("USGS significant earthquakes, past week", f"{EQ}/significant_week.geojson"),
    "tsu_ntwc": ("tsunami.gov NTWC (Palmer, AK) latest bulletin", "https://www.tsunami.gov/events/xml/PAAQAtom.xml"),
    "tsu_ptwc": ("tsunami.gov PTWC (Honolulu, HI) latest bulletin", "https://www.tsunami.gov/events/xml/PHEBAtom.xml"),
}
_lock = threading.Lock()
_memo = {"key": None, "payload": None}

# ------------------------------------------------------------------ helpers
def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def et(d):
    if not d: return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %-I:%M %p ET")
    except Exception: return iso(d)
def pt(s):
    if s is None: return None
    if isinstance(s, (int, float)): return datetime.fromtimestamp(s / 1000, timezone.utc)
    s = str(s).strip().replace(" ", "T")
    if not s: return None
    if s.endswith("Z"): s = s[:-1]
    s = s.split(".")[0]
    try: return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        try: return datetime.strptime(s[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except Exception: return None
def fnum(x):
    try:
        v = float(x); return v if math.isfinite(v) else None
    except Exception: return None
def bin_of(d): return d.replace(hour=d.hour - d.hour % 3, minute=0, second=0, microsecond=0)
def xclass(f):
    if not f or f <= 0: return None
    for L, base in (("X", 1e-4), ("M", 1e-5), ("C", 1e-6), ("B", 1e-7), ("A", 1e-8)):
        if f >= base: return f"{L}{f / base:.1f}"
    return f"A{f / 1e-8:.1f}"
def g_of(kp):
    if kp is None or kp < STORM_KP: return 0
    return int(min(5, max(1, math.floor(kp + 0.34) - 4)))

def db():
    c = sqlite3.connect(SDB, timeout=20); c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, fetched REAL, ok INTEGER, body BLOB, error TEXT, ms INTEGER, last_ok REAL);
    CREATE TABLE IF NOT EXISTS bins(bin_start TEXT PRIMARY KEY, kp REAL, kp_est INTEGER, xray_max REAL, flares_c INTEGER, flares_m INTEGER,
        flares_x INTEGER, q25 INTEGER, q45 INTEGER, max_mag REAL, storm INTEGER, partial INTEGER, first_logged TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS quakes(id TEXT PRIMARY KEY, t TEXT, mag REAL, lat REAL, lon REAL, depth REAL, place TEXT, url TEXT,
        tsunami INTEGER, alert TEXT, kp REAL, storm INTEGER, first_logged TEXT, updated TEXT);
    CREATE INDEX IF NOT EXISTS ix_q_t ON quakes(t);
    CREATE TABLE IF NOT EXISTS swpc_alerts(id TEXT PRIMARY KEY, product_id TEXT, issued TEXT, message TEXT, first_logged TEXT);
    CREATE TABLE IF NOT EXISTS fetch_log(ts TEXT, key TEXT, ok INTEGER, ms INTEGER, bytes INTEGER, error TEXT);
    """)
    return c

def ro_main():
    return sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20)

# ------------------------------------------------------------------ fetching with a 5-minute cache
def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=25) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip; b = gzip.decompress(b)
        return b

def fetch_all(force=False):
    """Return {key: (bytes|None, meta)}; refresh entries older than TTL (force still honours a 60 s floor)."""
    c = db(); t0 = time.time(); out = {}; todo = []
    rows = {r["key"]: r for r in c.execute("SELECT * FROM cache")}
    for k in SOURCES:
        r = rows.get(k); age = t0 - r["fetched"] if r else 1e9
        if age >= TTL or (force and age >= 60): todo.append(k)
    def one(k):
        s = time.time()
        try: b = _get(SOURCES[k][1]); return k, b, None, int((time.time() - s) * 1000)
        except Exception as ex: return k, None, f"{type(ex).__name__}: {ex}"[:200], int((time.time() - s) * 1000)
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            res = list(ex.map(one, todo))
        ts = iso(now())
        for k, b, err, ms in res:
            if b is not None:
                c.execute("INSERT INTO cache(key,fetched,ok,body,error,ms,last_ok) VALUES(?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET fetched=excluded.fetched,ok=1,body=excluded.body,error=NULL,ms=excluded.ms,last_ok=excluded.last_ok",
                          (k, t0, 1, zlib.compress(b, 6), None, ms, t0))
            else:
                c.execute("INSERT INTO cache(key,fetched,ok,error,ms) VALUES(?,?,0,?,?) ON CONFLICT(key) DO UPDATE SET fetched=excluded.fetched,ok=0,error=excluded.error,ms=excluded.ms",
                          (k, t0, err, ms))
            c.execute("INSERT INTO fetch_log VALUES(?,?,?,?,?,?)", (ts, k, 1 if b is not None else 0, ms, len(b) if b else 0, err))
        c.execute("DELETE FROM fetch_log WHERE ts < ?", (iso(now() - timedelta(days=14)),))
        c.commit()
    for r in c.execute("SELECT * FROM cache"):
        out[r["key"]] = (zlib.decompress(r["body"]) if r["body"] else None,
                         {"ok": r["ok"], "fetched": r["fetched"], "error": r["error"], "ms": r["ms"], "last_ok": r["last_ok"]})
    c.close()
    return out

def J(raw, k):
    b = raw.get(k, (None,))[0]
    if not b: return None
    try: return json.loads(b)
    except Exception: return None

# ------------------------------------------------------------------ parsing
def parse_kp(j):
    out = []
    if not j: return out
    if isinstance(j[0], list):  # legacy array-of-arrays format
        hdr = j[0]; j = [dict(zip(hdr, r)) for r in j[1:]]
    for r in j:
        t = pt(r.get("time_tag")); v = fnum(r.get("Kp", r.get("kp_index")))
        if t and v is not None: out.append((t, v))
    return out

def parse_alerts(j):
    out = []
    for a in j or []:
        msg = (a.get("message") or "").replace("\r", "")
        t = pt(a.get("issue_datetime"))
        lines = [l.strip() for l in msg.splitlines()]
        head = next((l for l in lines if re.match(r"^(ALERT|WARNING|WATCH|SUMMARY|EXTENDED WARNING|CANCEL|CONTINUED ALERT)", l)), None) or next((l for l in lines if l), "")
        lv = [int(x) for x in re.findall(r"\b[GSR]([1-5])\b", msg)]
        kind = (re.match(r"^(EXTENDED WARNING|CONTINUED ALERT|ALERT|WARNING|WATCH|SUMMARY|CANCEL)", head) or [None])[0] if head else None
        out.append({"id": hashlib.sha1(f"{a.get('product_id')}|{a.get('issue_datetime')}".encode()).hexdigest()[:16],
                    "product_id": a.get("product_id"), "t": iso(t), "t_et": et(t), "head": head[:220], "kind": (kind or "MESSAGE").title(),
                    "level": max(lv) if lv else 0, "scale": (re.search(r"\b([GSR][1-5])\b", msg) or [None])[0], "message": msg[:4000]})
    return out

def parse_tsu(raw, k):
    b = raw.get(k, (None,))[0]
    if not b: return None
    try:
        ns = {"a": "http://www.w3.org/2005/Atom", "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
        r = ET.fromstring(b); e = r.find("a:entry", ns)
        title = (r.findtext("a:title", "", ns) or "").strip(); upd = pt(r.findtext("a:updated", "", ns))
        if e is None: return {"center": k, "title": re.sub(r"\s+", " ", title), "t": iso(upd), "t_et": et(upd)}
        summ = ET.tostring(e.find("a:summary", ns), encoding="unicode", method="text") if e.find("a:summary", ns) is not None else ""
        cat = (re.search(r"Category:\s*([^\n]+?)\s*(Bulletin|$)", summ) or [None, ""])[1].strip()
        mag = (re.search(r"Preliminary Magnitude:\s*([0-9.]+)", summ) or [None, None])[1]
        link = None
        for l in e.findall("a:link", ns):
            if l.get("href"): link = l.get("href"); break
        m = re.search(r'href="(https://www\.tsunami\.gov/events/[^"]+\.txt)"', b.decode("utf-8", "ignore"))
        return {"center": k, "title": re.sub(r"\s+", " ", title).title(), "region": re.sub(r"\s+", " ", e.findtext("a:title", "", ns)).strip(),
                "category": cat or "Information", "mag": fnum(mag), "lat": fnum(e.findtext("geo:lat", "", ns)), "lon": fnum(e.findtext("geo:long", "", ns)),
                "t": iso(upd), "t_et": et(upd), "bulletin": m.group(1) if m else link, "feed": SOURCES[k][1]}
    except Exception as ex:
        return {"center": k, "error": str(ex)[:120]}

def quake_rows(j):
    out = []
    for f in (j or {}).get("features", []):
        p = f.get("properties") or {}; g = (f.get("geometry") or {}).get("coordinates") or [None, None, None]
        t = pt(p.get("time"))
        if not t or p.get("mag") is None: continue
        out.append({"id": f.get("id"), "t": iso(t), "dt": t, "t_et": et(t), "mag": round(float(p["mag"]), 1), "place": p.get("place") or p.get("title"),
                    "lat": g[1], "lon": g[0], "depth": g[2], "url": p.get("url"), "detail": p.get("detail"), "tsunami": int(p.get("tsunami") or 0),
                    "alert": p.get("alert"), "felt": p.get("felt"), "sig": p.get("sig"), "type": p.get("type"), "magType": p.get("magType"), "status": p.get("status")})
    return out

# ------------------------------------------------------------------ statistics
def pearson(x, y):
    n = len(x)
    if n < 3: return None
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x)); sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0: return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r
def spearman(x, y): return pearson(ranks(x), ranks(y)) if len(x) >= 3 else None
def rnd(v, n=3): return None if v is None else round(v, n)

def stats_for(bins, label):
    b = [x for x in bins if x["kp"] is not None and not x.get("partial")]
    kp = [x["kp"] for x in b]; q25 = [x["q25"] for x in b]; q45 = [x["q45"] for x in b]
    lx = [math.log10(x["xray_max"]) for x in b if x["xray_max"]]; lq = [x["q25"] for x in b if x["xray_max"]]
    def grp(f):
        s = [x for x in b if f(x["kp"])]
        n = len(s)
        return {"bins": n, "hours": n * 3, "q25": sum(x["q25"] for x in s), "q45": sum(x["q45"] for x in s),
                "rate25": rnd(sum(x["q25"] for x in s) / n, 2) if n else None, "rate45": rnd(sum(x["q45"] for x in s) / n, 2) if n else None}
    storm, active, quiet = grp(lambda k: k >= STORM_KP), grp(lambda k: 3.67 <= k < STORM_KP), grp(lambda k: k < 3.67)
    nonstorm = grp(lambda k: k < STORM_KP)
    lags = []
    for L in range(0, 9):   # Kp leads quakes by L bins (0-24 h)
        xs = kp[:len(kp) - L] if L else kp; ys = q25[L:]
        lags.append({"lag_h": L * 3, "r": rnd(pearson(xs, ys))})
    n = len(b)
    return {"label": label, "n": n, "from": b[0]["bin_start"] if b else None, "to": b[-1]["bin_start"] if b else None,
            "pearson_kp_q25": rnd(pearson(kp, q25)), "spearman_kp_q25": rnd(spearman(kp, q25)),
            "pearson_kp_q45": rnd(pearson(kp, q45)), "spearman_kp_q45": rnd(spearman(kp, q45)),
            "pearson_xray_q25": rnd(pearson(lx, lq)), "spearman_xray_q25": rnd(spearman(lx, lq)),
            "noise_r": rnd(1.96 / math.sqrt(n), 2) if n > 3 else None,
            "storm": storm, "active": active, "quiet": quiet, "nonstorm": nonstorm,
            "ratio25": rnd(storm["rate25"] / nonstorm["rate25"], 2) if storm["rate25"] is not None and nonstorm["rate25"] else None,
            "ratio45": rnd(storm["rate45"] / nonstorm["rate45"], 2) if storm["rate45"] is not None and nonstorm["rate45"] else None,
            "lags": lags}

# ------------------------------------------------------------------ main build
def collect(force=False):
    with _lock:
        raw = fetch_all(force)
        key = tuple(sorted((k, m["fetched"]) for k, (_, m) in raw.items()))
        if not force and _memo["key"] == key and _memo["payload"]: return _memo["payload"]
        p = build(raw); _memo["key"] = key; _memo["payload"] = p
        return p

def build(raw):
    T = now(); start = bin_of(T - timedelta(days=7)) + timedelta(hours=3)  # first bin fully inside the USGS week feed
    kp = parse_kp(J(raw, "kp")); kpd = {iso(t): v for t, v in kp}
    k1 = [(pt(r.get("time_tag")), fnum(r.get("estimated_kp"))) for r in (J(raw, "kp1m") or [])]
    k1 = [(t, v) for t, v in k1 if t and v is not None]
    # X-ray long channel (0.1-0.8 nm)
    xr = [(pt(r.get("time_tag")), fnum(r.get("flux"))) for r in (J(raw, "xray") or []) if r.get("energy") == "0.1-0.8nm"]
    xr = [(t, v) for t, v in xr if t and v and v > 0]
    flares = []
    for f in J(raw, "flares") or []:
        mc = f.get("max_class"); t = pt(f.get("max_time") or f.get("begin_time"))
        if mc and t: flares.append({"t": iso(t), "t_et": et(t), "class": mc, "begin": et(pt(f.get("begin_time"))), "end": et(pt(f.get("end_time"))), "flux": fnum(f.get("max_xrlong")), "dt": t})
    quakes = quake_rows(J(raw, "eq")); sig = quake_rows(J(raw, "eq_sig"))
    sig_ids = {q["id"] for q in sig}
    qd = {q["id"]: q for q in quakes}
    for q in sig: qd.setdefault(q["id"], q)
    quakes = sorted(qd.values(), key=lambda q: q["t"])
    # bins for the last 7 days
    bins = []; t = start; cur = bin_of(T)
    while t <= cur:
        s = iso(t); e = t + timedelta(hours=3)
        kv = kpd.get(s); est = 0
        if kv is None:
            vs = [v for tt, v in k1 if t <= tt < e]
            if vs: kv = max(vs); est = 1
        xv = [v for tt, v in xr if t <= tt < e]
        fl = [f["class"][0] for f in flares if t <= f["dt"] < e]
        qs = [q for q in quakes if t <= q["dt"] < e]
        bins.append({"bin_start": s, "label": et(t), "kp": kv, "kp_est": est, "xray_max": max(xv) if xv else None,
                     "flares_c": fl.count("C"), "flares_m": fl.count("M"), "flares_x": fl.count("X"),
                     "q25": sum(1 for q in qs if q["mag"] >= 2.5), "q45": sum(1 for q in qs if q["mag"] >= 4.5),
                     "max_mag": max((q["mag"] for q in qs), default=None), "storm": 1 if (kv is not None and kv >= STORM_KP) else 0,
                     "partial": 1 if (e > T or est) else 0})
        t = e
    bmap = {b["bin_start"]: b for b in bins}
    def kp_at(dt):
        b = bmap.get(iso(bin_of(dt)))
        if b: return b["kp"]
        return kpd.get(iso(bin_of(dt)))
    for q in quakes:
        q["kp"] = kp_at(q["dt"]); q["storm"] = 1 if (q["kp"] is not None and q["kp"] >= STORM_KP) else 0; q["sig"] = 1 if q["id"] in sig_ids else 0
    # ---------------- persist the evidence log
    c = db(); ts = iso(T)
    usgs_ok = raw.get("eq", (None, {}))[1].get("ok") and raw["eq"][0]
    kp_ok = bool(kp)
    for b in bins:
        if not (usgs_ok and kp_ok): break
        c.execute("""INSERT INTO bins VALUES(:bin_start,:kp,:kp_est,:xray_max,:flares_c,:flares_m,:flares_x,:q25,:q45,:max_mag,:storm,:partial,:ts,:ts)
                     ON CONFLICT(bin_start) DO UPDATE SET kp=excluded.kp,kp_est=excluded.kp_est,xray_max=COALESCE(excluded.xray_max,bins.xray_max),
                     flares_c=excluded.flares_c,flares_m=excluded.flares_m,flares_x=excluded.flares_x,q25=excluded.q25,q45=excluded.q45,
                     max_mag=excluded.max_mag,storm=excluded.storm,partial=excluded.partial,updated=excluded.updated""", {**b, "ts": ts})
    for q in quakes:
        c.execute("""INSERT INTO quakes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET t=excluded.t,mag=excluded.mag,lat=excluded.lat,
                     lon=excluded.lon,depth=excluded.depth,place=excluded.place,tsunami=excluded.tsunami,alert=excluded.alert,kp=excluded.kp,storm=excluded.storm,updated=excluded.updated""",
                  (q["id"], q["t"], q["mag"], q["lat"], q["lon"], q["depth"], q["place"], q["url"], q["tsunami"], q["alert"], q["kp"], q["storm"], ts, ts))
    live_alerts = parse_alerts(J(raw, "alerts"))
    for a in live_alerts:
        c.execute("INSERT OR IGNORE INTO swpc_alerts VALUES(?,?,?,?,?)", (a["id"], a["product_id"], a["t"], a["message"], ts))
    c.commit()
    logged = [dict(r) for r in c.execute("SELECT * FROM bins ORDER BY bin_start")]
    log_info = {"bins": c.execute("SELECT COUNT(*) FROM bins WHERE partial=0").fetchone()[0],
                "since": c.execute("SELECT MIN(first_logged) FROM bins").fetchone()[0],
                "first_bin": c.execute("SELECT MIN(bin_start) FROM bins").fetchone()[0],
                "quakes": c.execute("SELECT COUNT(*) FROM quakes").fetchone()[0],
                "storm_quakes": c.execute("SELECT COUNT(*) FROM quakes WHERE storm=1").fetchone()[0],
                "alerts": c.execute("SELECT COUNT(*) FROM swpc_alerts").fetchone()[0],
                "storm_bins": c.execute("SELECT COUNT(*) FROM bins WHERE partial=0 AND storm=1").fetchone()[0]}
    hist_alerts = [dict(r) for r in c.execute("SELECT * FROM swpc_alerts WHERE issued >= ? ORDER BY issued DESC", (iso(T - timedelta(days=30)),))]
    older_q = [dict(r) for r in c.execute("SELECT id,t,mag,lat,lon,depth,place,url,tsunami,alert,kp,storm FROM quakes WHERE t < ? ORDER BY t", (iso(start),))]
    fl = [dict(r) for r in c.execute("SELECT key, MAX(ts) ts, SUM(ok) ok, COUNT(*) n FROM fetch_log WHERE ts >= ? GROUP BY key", (iso(T - timedelta(hours=24)),))]
    c.close()
    fl24 = {r["key"]: r for r in fl}
    # merge alert history (live + logged + scanner-captured in blackout.db)
    amap = {a["id"]: a for a in live_alerts}
    for r in hist_alerts:
        if r["id"] not in amap:
            a = parse_alerts([{"product_id": r["product_id"], "issue_datetime": (r["issued"] or "").replace("T", " ").rstrip("Z"), "message": r["message"]}])[0]
            amap[a["id"]] = a
    bot_alert_ids = {}; bot_quake = {}
    try:
        m = ro_main()
        for aid, title, etime, cid in m.execute("SELECT id,title,event_time,cluster_id FROM alerts WHERE source='NOAA SWPC' AND event_time >= ?", (iso(T - timedelta(days=30)),)):
            bot_alert_ids[aid] = cid
        cl = {}
        for q in quakes:
            hid = hashlib.sha1(f"USGS|{q['id']}".encode()).hexdigest()[:16]; bot_quake[hid] = q["id"]
        for aid, cid in m.execute(f"SELECT id,cluster_id FROM alerts WHERE source='USGS' AND id IN ({','.join('?' * len(bot_quake))})", list(bot_quake)) if bot_quake else []:
            cl[bot_quake[aid]] = cid
        ranks_ = {}
        if cl:
            for cid, rk, sc in m.execute(f"SELECT cluster_id,rank,score FROM clusters WHERE cluster_id IN ({','.join('?' * len(set(cl.values())))})", list(set(cl.values()))):
                ranks_[cid] = (rk, sc)
        for q in quakes:
            if q["id"] in cl:
                q["bot"] = {"cluster_id": cl[q["id"]], "rank": (ranks_.get(cl[q["id"]]) or (None, None))[0], "score": (ranks_.get(cl[q["id"]]) or (None, None))[1]}
        bot_counts = {"swpc": m.execute("SELECT COUNT(*) FROM alerts WHERE source LIKE 'NOAA SWPC%'").fetchone()[0],
                      "usgs": m.execute("SELECT COUNT(*) FROM alerts WHERE source='USGS'").fetchone()[0],
                      "swpc_since": m.execute("SELECT MIN(first_seen) FROM alerts WHERE source LIKE 'NOAA SWPC%'").fetchone()[0],
                      "usgs_since": m.execute("SELECT MIN(first_seen) FROM alerts WHERE source='USGS'").fetchone()[0]}
        sh = {r[0]: r for r in m.execute("SELECT name,ok,items,last_checked,error FROM source_health WHERE name LIKE '%SWPC%' OR name LIKE 'USGS%'")}
        m.close()
    except Exception as ex:
        bot_counts = {"error": str(ex)[:120]}; sh = {}
    for a in amap.values():
        hid = hashlib.sha1(f"NOAA SWPC|{a['product_id']}|{(a['t'] or '').replace('T', ' ').rstrip('Z')}".encode()).hexdigest()[:16]
        a["bot"] = 1 if hid in bot_alert_ids else 0
    alerts = sorted(amap.values(), key=lambda a: a["t"] or "", reverse=True)
    # ---------------- current conditions
    kp_last = kp[-1] if kp else (None, None); k1_last = k1[-1] if k1 else (None, None)
    sc = J(raw, "scales") or {}
    def scl(d):
        d = d or {}
        return {"date": d.get("DateStamp"), "R": (d.get("R") or {}).get("Scale"), "S": (d.get("S") or {}).get("Scale"), "G": (d.get("G") or {}).get("Scale"),
                "R_text": (d.get("R") or {}).get("Text"), "S_text": (d.get("S") or {}).get("Text"), "G_text": (d.get("G") or {}).get("Text"),
                "R_minor": (d.get("R") or {}).get("MinorProb"), "R_major": (d.get("R") or {}).get("MajorProb"), "S_prob": (d.get("S") or {}).get("Prob")}
    wn = (J(raw, "wind_now") or [{}])[0]; mn = (J(raw, "mag_now") or [{}])[0]
    w1 = [r for r in (J(raw, "wind1m") or []) if r.get("active")]; m1 = [r for r in (J(raw, "mag1m") or []) if r.get("active")]
    def ds(rows, fields, step=10):
        agg = {}
        for r in rows:
            t = pt(r.get("time_tag"))
            if not t: continue
            k = t.replace(minute=t.minute - t.minute % step, second=0)
            a = agg.setdefault(k, {f: [] for f in fields})
            for f in fields:
                v = fnum(r.get(f))
                if v is not None: a[f].append(v)
        return [{"t": iso(k), **{f: (rnd(sum(v) / len(v), 2) if v else None) for f, v in a.items()}} for k, a in sorted(agg.items())]
    wind24 = ds(w1, ["proton_speed", "proton_density"]); mag24 = ds(m1, ["bt", "bz_gsm"])
    dens = next((fnum(r.get("proton_density")) for r in sorted(w1, key=lambda r: r.get("time_tag") or "", reverse=True) if fnum(r.get("proton_density")) is not None), None)
    xr_last = xr[-1] if xr else (None, None)
    fl7 = sorted(flares, key=lambda f: f["flux"] or 0, reverse=True)
    notable = [q for q in quakes if q["mag"] >= 5 or q["sig"] or q["tsunami"] or q.get("bot")]
    notable = sorted(notable, key=lambda q: q["t"], reverse=True)[:60]
    latest_notable = next((q for q in notable if q["mag"] >= 4.5 or q["sig"]), notable[0] if notable else None)
    biggest = max(quakes, key=lambda q: q["mag"]) if quakes else None
    tsu = [x for x in (parse_tsu(raw, "tsu_ntwc"), parse_tsu(raw, "tsu_ptwc")) if x]
    cur = {"kp": {"value": kp_last[1], "t": iso(kp_last[0]), "t_et": et(kp_last[0] + timedelta(hours=3)) if kp_last[0] else None, "g": g_of(kp_last[1]),
                  "est": k1_last[1], "est_t_et": et(k1_last[0]), "max24": max((v for t, v in kp if t >= T - timedelta(hours=24)), default=None),
                  "max7": max((v for t, v in kp), default=None)},
           "scales": {"now": scl(sc.get("0")), "max24": scl(sc.get("-1")), "forecast": [scl(sc.get(str(i))) for i in (1, 2, 3) if sc.get(str(i))]},
           "xray": {"flux": xr_last[1], "class": xclass(xr_last[1]), "t_et": et(xr_last[0])},
           "flare": {"latest": {k: v for k, v in flares[-1].items() if k != "dt"} if flares else None, "biggest": {k: v for k, v in fl7[0].items() if k != "dt"} if fl7 else None,
                     "count": {L: sum(1 for f in flares if f["class"].startswith(L)) for L in "BCMX"}},
           "wind": {"speed": fnum(wn.get("proton_speed")), "bz": fnum(mn.get("bz_gsm")), "bt": fnum(mn.get("bt")), "density": dens, "t_et": et(pt(wn.get("time_tag") or mn.get("time_tag")))},
           "quake": {"latest": strip(latest_notable), "biggest": strip(biggest), "count": len(quakes), "m45": sum(1 for q in quakes if q["mag"] >= 4.5),
                     "tsunami_flagged": sum(1 for q in quakes if q["tsunami"]), "storm_quakes": sum(1 for q in quakes if q["storm"])},
           "tsunami": tsu}
    # ---------------- sources status
    srcs = []
    for k, (lab, url) in SOURCES.items():
        b, mt = raw.get(k, (None, {}))
        srcs.append({"key": k, "name": lab, "url": url, "ok": bool(mt.get("ok")), "has_data": b is not None, "error": mt.get("error"),
                     "fetched_et": et(datetime.fromtimestamp(mt["fetched"], timezone.utc)) if mt.get("fetched") else None,
                     "last_ok_et": et(datetime.fromtimestamp(mt["last_ok"], timezone.utc)) if mt.get("last_ok") else None,
                     "age_s": int(time.time() - mt["fetched"]) if mt.get("fetched") else None, "ms": mt.get("ms"),
                     "fetches24": (fl24.get(k) or {}).get("n", 0), "ok24": (fl24.get(k) or {}).get("ok", 0)})
    oldest = min((s["age_s"] for s in srcs if s["age_s"] is not None), default=0)
    complete = [b for b in logged if not b["partial"] and b["kp"] is not None]
    return {"generated": iso(T), "generated_et": et(T), "ttl_s": TTL, "next_fetch_s": max(0, TTL - oldest), "storm_kp": STORM_KP,
            "sources": srcs, "scanner": {"counts": bot_counts, "health": [{"name": r[0], "ok": r[1], "items": r[2], "checked_et": et(pt(r[3])), "error": r[4]} for r in sh.values()]},
            "now": cur, "alerts": alerts[:200], "quakes_notable": [strip(q) for q in notable],
            "bins": [{k: v for k, v in b.items()} for b in bins], "wind24": wind24, "mag24": mag24,
            "flares": [{k: v for k, v in f.items() if k != "dt"} for f in flares if f["class"][0] in "CMX"],
            "map": [strip(q) for q in quakes], "map_hist": older_q,
            "stats": {"week": stats_for(bins, "Past 7 days (live feeds)"), "all": stats_for(complete, "Everything logged so far")},
            "log": log_info, "window": {"from": iso(start), "to": iso(T)}}

def strip(q):
    if not q: return None
    return {k: v for k, v in q.items() if k != "dt"}

# ------------------------------------------------------------------ background logger (keeps the evidence log growing)
def _loop():
    time.sleep(20)
    while True:
        try: sys.modules.get(__name__, sys.modules.get("solar_seismic")).collect()
        except Exception as ex: print("solar_seismic logger:", ex, flush=True)
        time.sleep(1800)
def _ensure_logger():
    if any(t.name == "solar_seismic_logger" and t.is_alive() for t in threading.enumerate()): return
    threading.Thread(target=_loop, name="solar_seismic_logger", daemon=True).start()
_ensure_logger()

# ------------------------------------------------------------------ HTTP
def handle_get(path, qs):
    if path == "/api/solar_seismic/live" or path.startswith(("/api/solar_seismic/img/", "/api/solar_seismic/usgs/")):
        import importlib, solar_live   # t239-t241: live Sun imagery, flares/CME countdown, USGS proxy fallback
        mt = os.path.getmtime(solar_live.__file__)
        if getattr(solar_live, "_bn_mt", None) != mt: solar_live = importlib.reload(solar_live)
        solar_live._bn_mt = mt
        return solar_live.handle_get(path, qs)
    if path in ("/api/solar_seismic/app.js", "/api/solar_seismic/app.css", "/api/solar_seismic/live.js", "/api/solar_seismic/live.css"):
        f = os.path.join(STATIC, os.path.basename(path))
        with open(f, "rb") as fh:
            return 200, fh.read(), "application/javascript" if f.endswith(".js") else "text/css"
    if path in ("/api/solar_seismic/bins.csv", "/api/solar_seismic/quakes.csv"):
        import csv, io
        c = db(); buf = io.StringIO(); w = csv.writer(buf)
        if path.endswith("bins.csv"):
            cols = ["bin_start", "kp", "kp_est", "xray_max", "flares_c", "flares_m", "flares_x", "q25", "q45", "max_mag", "storm", "partial", "first_logged", "updated"]
            rows = c.execute(f"SELECT {','.join(cols)} FROM bins ORDER BY bin_start").fetchall()
        else:
            cols = ["id", "t", "mag", "lat", "lon", "depth", "place", "url", "tsunami", "alert", "kp", "storm", "first_logged"]
            rows = c.execute(f"SELECT {','.join(cols)} FROM quakes ORDER BY t").fetchall()
        c.close(); w.writerow(cols); w.writerows([tuple(r) for r in rows])
        return 200, buf.getvalue(), "text/csv"
    if path == "/api/solar_seismic":
        force = (qs.get("force") or ["0"])[0] == "1"
        return 200, collect(force)
    return 404, {"error": "not found"}
