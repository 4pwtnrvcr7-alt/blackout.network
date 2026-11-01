"""Live Sun + flares/CME + USGS proxy for the Solar & Seismic tab (t239-t241). Imported by solar_seismic.handle_get for
/api/solar_seismic/live, /api/solar_seismic/img/<key> and /api/solar_seismic/usgs/<feed>.
Free public feeds only (NOAA SWPC, NASA CCMC DONKI kauai host, NASA SDO, ESA/NASA SOHO, USGS); no keys, a real User-Agent,
in-memory caching with stale-on-error. Never touches scanner.py, scoring, push.py, jets.py or config.json. Never invents events:
countdowns only come from an official estimate (NOAA text/watches, CCMC WSA-ENLIL) or, failing that, a clearly labeled rough
physics estimate for a CME that NOAA or DONKI actually reported."""
import json, math, re, threading, time, urllib.request, gzip
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

UA = "blackout.network-SolarLive/1.0 (+https://blackout.network; public dashboard)"
SW = "https://services.swpc.noaa.gov"
DK = "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get"
AU_KM = 1.496e8
FEEDS = {  # key: (url, ttl seconds)
    "regions": (f"{SW}/json/solar_regions.json", 900),
    "probs": (f"{SW}/json/solar_probabilities.json", 900),
    "fl_latest": (f"{SW}/json/goes/primary/xray-flares-latest.json", 120),
    "fl_7d": (f"{SW}/json/goes/primary/xray-flares-7-day.json", 300),
    "xray1d": (f"{SW}/json/goes/primary/xrays-1-day.json", 180),
    "kpf": (f"{SW}/products/noaa-planetary-k-index-forecast.json", 600),
    "kp1m": (f"{SW}/json/planetary_k_index_1m.json", 120),
    "scales": (f"{SW}/products/noaa-scales.json", 300),
    "alerts": (f"{SW}/products/alerts.json", 120),
    "wind": (f"{SW}/products/summary/solar-wind-speed.json", 120),
    "mag": (f"{SW}/products/summary/solar-wind-mag-field.json", 120),
    "plasma": (f"{SW}/json/rtsw/rtsw_wind_1m.json", 180),
    "f3day": (f"{SW}/text/3-day-forecast.txt", 900),
    "disc": (f"{SW}/text/discussion.txt", 900),
    "dk_cme": (None, 1200), "dk_enlil": (None, 1200), "dk_ips": (None, 1200),
}
IMGS = {  # key: (label, url)
    "sdo_0193": ("NASA SDO AIA 193 Å (corona, coronal holes)", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg"),
    "sdo_0171": ("NASA SDO AIA 171 Å (quiet corona, loops)", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0171.jpg"),
    "sdo_0304": ("NASA SDO AIA 304 Å (chromosphere, prominences)", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0304.jpg"),
    "sdo_0131": ("NASA SDO AIA 131 Å (flaring regions)", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0131.jpg"),
    "sdo_hmiic": ("NASA SDO HMI intensitygram (sunspots)", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIIC.jpg"),
    "sdo_hmib": ("NASA SDO HMI magnetogram", "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_HMIB.jpg"),
    "soho_c2": ("ESA/NASA SOHO LASCO C2 coronagraph", "https://soho.nascom.nasa.gov/data/realtime/c2/1024/latest.jpg"),
    "soho_c3": ("ESA/NASA SOHO LASCO C3 coronagraph", "https://soho.nascom.nasa.gov/data/realtime/c3/1024/latest.jpg"),
    "soho_eit195": ("ESA/NASA SOHO EIT 195 Å", "https://soho.nascom.nasa.gov/data/realtime/eit_195/1024/latest.jpg"),
}
USGS = {f: f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{f}.geojson"
        for f in ("all_hour", "all_day", "2.5_day", "4.5_day", "2.5_week", "4.5_week", "significant_week", "significant_month")}
_cache = {}; _lock = threading.Lock(); _memo = {"t": 0, "p": None}

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def et(d):
    if not d: return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("America/New_York")).strftime("%a %b %-d, %-I:%M %p ET")
    except Exception: return iso(d)
def pt(s):
    if not s: return None
    s = str(s).strip().replace(" ", "T").rstrip("Z").split(".")[0]
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try: return datetime.strptime(s[:19] if "S" in f else s[:16], f).replace(tzinfo=timezone.utc)
        except Exception: pass
    return None
def fnum(x):
    try: v = float(x); return v if math.isfinite(v) else None
    except Exception: return None

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read(); ct = r.headers.get("Content-Type", "")
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
        return b, ct

def cached(key, url, ttl, timeout=20):
    """(body|None, meta). Serves the last good copy if a refresh fails (stale-on-error)."""
    t = time.time(); c = _cache.get(key)
    if c and t - c["t"] < ttl: return c["b"], c
    try:
        b, ct = _get(url, timeout); c = {"t": t, "ok_t": t, "b": b, "ct": ct, "err": None}
    except Exception as ex:
        err = f"{type(ex).__name__}: {ex}"[:160]
        c = {"t": t, "ok_t": (c or {}).get("ok_t"), "b": (c or {}).get("b"), "ct": (c or {}).get("ct"), "err": err}
    with _lock: _cache[key] = c
    return c["b"], c

def _url(k):
    d = now()
    if k == "dk_cme": return f"{DK}/CMEAnalysis?startDate={(d - timedelta(days=10)).date()}&endDate={d.date()}&mostAccurateOnly=true&speed=300&halfAngle=15&catalog=ALL"
    if k == "dk_enlil": return f"{DK}/WSAEnlilSimulations?startDate={(d - timedelta(days=7)).date()}&endDate={d.date()}"
    if k == "dk_ips": return f"{DK}/IPS?startDate={(d - timedelta(days=45)).date()}&endDate={d.date()}&location=Earth&catalog=ALL"
    return FEEDS[k][0]

def fetch():
    def one(k):
        b, m = cached(k, _url(k), FEEDS[k][1], timeout=12 if k.startswith("dk_") else 20)
        return k, b, m
    with ThreadPoolExecutor(max_workers=8) as ex: res = list(ex.map(one, FEEDS))
    return {k: (b, m) for k, b, m in res}

def J(raw, k):
    b = raw.get(k, (None,))[0]
    try: return json.loads(b) if b else None
    except Exception: return None
def T(raw, k):
    b = raw.get(k, (None,))[0]
    return b.decode("utf-8", "ignore").replace("\r", "") if b else ""

def fl_class_ok(c): return bool(c) and c[0] in "ABCMX"

def build(raw):
    N = now(); out = {"generated": iso(N), "generated_et": et(N)}
    # ---- sources/freshness
    src = {}
    for k in FEEDS:
        b, m = raw.get(k, (None, {}))
        src[k] = {"url": _url(k).split("?")[0] if k.startswith("dk_") else _url(k), "ok": bool(m and not m.get("err")), "has_data": b is not None,
                  "error": (m or {}).get("err"), "fetched_et": et(datetime.fromtimestamp(m["ok_t"], timezone.utc)) if m and m.get("ok_t") else None}
    out["sources"] = src
    # ---- solar wind / Kp now
    w = (J(raw, "wind") or [{}]); w = w[0] if isinstance(w, list) and w else {}
    mg = (J(raw, "mag") or [{}]); mg = mg[0] if isinstance(mg, list) and mg else {}
    pl = [r for r in (J(raw, "plasma") or []) if r.get("active") and fnum(r.get("proton_density")) is not None]
    pl.sort(key=lambda r: r.get("time_tag") or "")
    k1 = [r for r in (J(raw, "kp1m") or []) if fnum(r.get("estimated_kp")) is not None]
    out["wind"] = {"speed": fnum(w.get("proton_speed")), "t_et": et(pt(w.get("time_tag"))),
                   "density": fnum(pl[-1]["proton_density"]) if pl else None, "density_t_et": et(pt(pl[-1]["time_tag"])) if pl else None,
                   "bz": fnum(mg.get("bz_gsm")), "bt": fnum(mg.get("bt")), "mag_t_et": et(pt(mg.get("time_tag")))}
    out["kp_now"] = {"est": fnum(k1[-1]["estimated_kp"]) if k1 else None, "kp": fnum(k1[-1].get("kp_index")) if k1 else None,
                     "t_et": et(pt(k1[-1]["time_tag"])) if k1 else None}
    sc = J(raw, "scales") or {}
    def scl(d):
        d = d or {}
        g = lambda L: {"scale": (d.get(L) or {}).get("Scale"), "text": (d.get(L) or {}).get("Text")}
        return {"date": d.get("DateStamp"), "R": g("R"), "S": g("S"), "G": g("G"),
                "R_minor": (d.get("R") or {}).get("MinorProb"), "R_major": (d.get("R") or {}).get("MajorProb"), "S_prob": (d.get("S") or {}).get("Prob")}
    out["scales"] = {"now": scl(sc.get("0")), "max24": scl(sc.get("-1")), "forecast": [scl(sc.get(str(i))) for i in (1, 2, 3) if sc.get(str(i))]}
    # ---- alerts (active = issued in the last 24 h, or a warning whose Valid To is still ahead)
    al = []
    for a in J(raw, "alerts") or []:
        msg = (a.get("message") or "").replace("\r", ""); t = pt(a.get("issue_datetime"))
        head = next((l.strip() for l in msg.splitlines() if re.match(r"^(ALERT|WARNING|WATCH|SUMMARY|EXTENDED WARNING|CANCEL|CONTINUED ALERT)", l.strip())), "")
        vt = re.search(r"(?:Valid To|Now Valid Until):\s*(\d{4}) (\w{3}) (\d{2}) (\d{4}) UTC", msg)
        vto = None
        if vt:
            try: vto = datetime.strptime(" ".join(vt.groups()), "%Y %b %d %H%M").replace(tzinfo=timezone.utc)
            except Exception: pass
        lv = (re.search(r"\b([GSR][1-5])\b", msg) or [None])[0]
        active = (vto and vto > N) or (t and N - t < timedelta(hours=24))
        al.append({"pid": a.get("product_id"), "t": iso(t), "t_et": et(t), "head": head[:200], "scale": lv, "valid_to_et": et(vto),
                   "active": bool(active), "msg": msg[:1500]})
    al.sort(key=lambda a: a["t"] or "", reverse=True)
    out["alerts"] = {"active": [a for a in al if a["active"]][:25], "n_active": sum(1 for a in al if a["active"]), "n": len(al)}
    # ---- regions (latest observed date)
    rg = J(raw, "regions") or []
    last = max((r.get("observed_date") or "" for r in rg), default="")
    regs = [r for r in rg if r.get("observed_date") == last and r.get("region")]
    out["regions"] = {"date": last, "list": sorted([{k: r.get(k) for k in ("region", "location", "latitude", "longitude", "area", "spot_class", "mag_class", "number_spots",
        "c_flare_probability", "m_flare_probability", "x_flare_probability", "c_xray_events", "m_xray_events", "x_xray_events", "status", "first_date")} for r in regs],
        key=lambda r: -((r.get("m_flare_probability") or 0) * 10 + (r.get("c_flare_probability") or 0)))}
    pr = J(raw, "probs") or []
    p = max(pr, key=lambda x: x.get("date") or "") if pr else {}
    out["probs"] = {"date": (p.get("date") or "")[:10], **{f"{c}{d}": p.get(f"{c}_class_{d}_day") for c in "cmx" for d in (1, 2, 3)},
                    "p10": p.get("10mev_protons_1_day")}
    # ---- flares
    def fl(f):
        t = pt(f.get("max_time") or f.get("begin_time"))
        return {"class": f.get("max_class"), "t": iso(t), "t_et": et(t), "begin_et": et(pt(f.get("begin_time"))), "end_et": et(pt(f.get("end_time"))) if f.get("end_time") not in (None, "Unk") else None,
                "flux": fnum(f.get("max_xrlong"))}
    f7 = [fl(f) for f in (J(raw, "fl_7d") or []) if fl_class_ok(f.get("max_class"))]
    fla = [fl(f) for f in (J(raw, "fl_latest") or []) if fl_class_ok(f.get("max_class"))]
    seen = {x["t"] for x in f7}; f7 += [x for x in fla if x["t"] not in seen]
    f7.sort(key=lambda x: x["t"] or "", reverse=True)
    cnt = {L: sum(1 for x in f7 if x["class"].startswith(L)) for L in "ABCMX"}
    cur = (J(raw, "fl_latest") or [{}]); cur = cur[0] if cur else {}
    out["flares"] = {"list": f7[:60], "count7": cnt, "latest": f7[0] if f7 else None,
                     "biggest": max(f7, key=lambda x: x["flux"] or 0) if f7 else None, "current_class": cur.get("current_class"),
                     "current_t_et": et(pt(cur.get("time_tag")))}
    # ---- X-ray flux, 1 day, long channel, 10-minute maxima
    xr = {}
    for r in J(raw, "xray1d") or []:
        if r.get("energy") != "0.1-0.8nm": continue
        t = pt(r.get("time_tag")); v = fnum(r.get("flux"))
        if not t or not v or v <= 0: continue
        k = t.replace(minute=t.minute - t.minute % 10, second=0); xr[k] = max(xr.get(k, 0), v)
    out["xray"] = [[iso(k), v] for k, v in sorted(xr.items())]
    # ---- Kp forecast (observed / estimated / predicted 3-hour)
    kf = J(raw, "kpf") or []
    if kf and isinstance(kf[0], list): kf = [dict(zip(kf[0], r)) for r in kf[1:]]
    out["kp_forecast"] = [{"t": iso(pt(r.get("time_tag"))), "kp": fnum(r.get("kp")), "kind": r.get("observed"), "g": r.get("noaa_scale")} for r in kf if pt(r.get("time_tag"))]
    fut = [x for x in out["kp_forecast"] if x["kind"] != "observed" and x["kp"] is not None and pt(x["t"]) >= N - timedelta(hours=3)]
    out["kp_forecast_max"] = max(fut, key=lambda x: x["kp"]) if fut else None
    # ---- NOAA text products
    f3, ds = T(raw, "f3day"), T(raw, "disc")
    iss = lambda s: (re.search(r":Issued:\s*([^\n]+)", s) or [None, None])[1]
    rat = (re.search(r"A\. NOAA Geomagnetic.*?Rationale:\s*(.+?)\n\n", f3, re.S) or [None, ""])[1]
    gx = (re.search(r"greatest expected 3 hr Kp for ([^\n]+?) is ([0-9.]+)\s*\(NOAA Scale\s*\n?\s*(G\d)\)", f3) or [None])
    out["forecast3"] = {"issued": iss(f3), "rationale": re.sub(r"\s+", " ", rat).strip(),
                        "kp_max": fnum(gx[2]) if gx[0] else None, "g_max": gx[3] if gx[0] else None, "url": FEEDS["f3day"][0]}
    sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", ds))
    cme_s = [s.strip() for s in sents if re.search(r"\bCMEs?\b", s)]
    out["discussion"] = {"issued": iss(ds), "cme_sentences": cme_s[:8], "url": FEEDS["disc"][0]}
    # ---- CME / impact countdown (official first, never invented)
    cme = {"events": [], "last_arrival": None, "watches": [], "note": None}
    for a in al:   # NOAA watches (official CME-driven storm watches with day-by-day levels)
        if a["head"].startswith("WATCH") and a["t"] and N - pt(a["t"]) < timedelta(days=4):
            days = re.findall(r"(\w{3} \d{2}):\s*(G\d) \(([^)]+)\)", a["msg"])
            cme["watches"].append({"head": a["head"], "t_et": a["t_et"], "days": [{"day": d, "g": g, "label": l} for d, g, l in days],
                                   "cme": bool(re.search(r"\bCME\b|coronal mass ejection", a["msg"], re.I)), "text": a["msg"][:900]})
    cme["watches"] = cme["watches"][:1]   # each NOAA watch supersedes the prior ones
    for a in al:   # last observed arrival: NOAA sudden impulse summaries / warnings
        if re.search(r"Sudden Impulse", a["msg"], re.I) and re.search(r"SUMMARY", a["head"]):
            ob = re.search(r"Observed:\s*(\d{4}) (\w{3}) (\d{2}) (\d{4}) UTC", a["msg"]); ot = None
            if ob:
                try: ot = datetime.strptime(" ".join(ob.groups()), "%Y %b %d %H%M").replace(tzinfo=timezone.utc)
                except Exception: pass
            cme["last_arrival"] = {"source": "NOAA SWPC sudden impulse summary", "t": iso(ot or pt(a["t"])), "t_et": et(ot or pt(a["t"])), "text": a["head"]}
            break
    ips = J(raw, "dk_ips") or []
    if isinstance(ips, list) and ips:
        li = max(ips, key=lambda x: x.get("eventTime") or "")
        lt = pt(li.get("eventTime"))
        if lt and (not cme["last_arrival"] or iso(lt) > (cme["last_arrival"]["t"] or "")):
            cme["last_arrival"] = {"source": "NASA CCMC DONKI interplanetary shock (IPS) at Earth", "t": iso(lt), "t_et": et(lt),
                                   "text": f"IPS at Earth, {li.get('instruments') and ', '.join(i.get('displayName', '') for i in li['instruments'][:2]) or ''}".strip(", "), "link": li.get("link")}
    enl = J(raw, "dk_enlil") or []
    for s in enl if isinstance(enl, list) else []:
        at = pt(s.get("estimatedShockArrivalTime"))
        if at and at > N - timedelta(hours=12):
            ci = (s.get("cmeInputs") or [{}])[0]
            cme["events"].append({"kind": "official", "source": "NASA CCMC WSA-ENLIL model run (DONKI)", "arrival": iso(at), "arrival_et": et(at),
                                  "kp_range": [s.get("kp_18"), s.get("kp_90"), s.get("kp_135"), s.get("kp_180")], "duration_h": s.get("estimatedDuration"),
                                  "cme_start_et": et(pt(ci.get("cmeStartTime"))), "speed": fnum(ci.get("speed")), "link": s.get("link"), "glancing": bool(s.get("isEarthGB"))})
    # NOAA's discussion says whether an Earth-directed CME was seen; only then may a rough estimate be shown
    earth_cme = any(re.search(r"Earth[- ]directed", s, re.I) and not re.search(r"\bNo\b|\bnot\b", s) for s in cme_s) or any(w["cme"] for w in cme["watches"])
    if not cme["events"]:
        an = J(raw, "dk_cme") or []
        cand = []
        for c in an if isinstance(an, list) else []:
            st = pt(c.get("time21_5")); sp = fnum(c.get("speed")); lon = fnum(c.get("longitude")); lat = fnum(c.get("latitude")); ha = fnum(c.get("halfAngle")) or 0
            if not (st and sp) or N - st > timedelta(days=5): continue
            earthward = lon is not None and abs(lon) <= max(30, ha) and (lat is None or abs(lat) <= max(30, ha))
            if earthward or earth_cme: cand.append((st, sp, c, earthward))
        for st, sp, c, ew in sorted(cand, key=lambda x: x[0], reverse=True)[:2]:
            sec = AU_KM / sp; arr = st + timedelta(seconds=sec)
            lo = st + timedelta(seconds=AU_KM / 800); hi = st + timedelta(seconds=AU_KM / 400)
            if hi < N - timedelta(hours=12): continue
            cme["events"].append({"kind": "rough", "source": "Rough estimate, not an official forecast", "arrival": iso(arr), "arrival_et": et(arr),
                                  "window": [iso(lo), iso(hi)], "window_et": [et(lo), et(hi)], "speed": sp, "cme_start_et": et(st), "link": c.get("link"),
                                  "assumptions": f"Constant speed {sp:.0f} km/s (DONKI CME analysis, at 21.5 solar radii) over 1 AU ≈ 1.496e8 km; window uses 400–800 km/s. "
                                                 "Real CMEs speed up or slow down in the solar wind, and many miss Earth or only glance it."})
    if not cme["events"]:
        cme["note"] = ("NOAA SWPC's latest forecast discussion reports no Earth-directed CME." if any(re.search(r"No Earth-directed CMEs?", s, re.I) for s in cme_s)
                       else "No Earth-directed CME with an arrival estimate is in NOAA SWPC or NASA CCMC data right now.")
    nxt = None   # next predicted elevated window from NOAA's own 3-hour Kp forecast
    for x in fut:
        if x["kp"] >= 4.67: nxt = x; break
    cme["next_window"] = {"t": nxt["t"], "t_et": et(pt(nxt["t"])), "kp": nxt["kp"], "g": nxt["g"]} if nxt else None
    cme["donki_ok"] = all(src[k]["ok"] for k in ("dk_cme", "dk_enlil", "dk_ips"))
    out["cme"] = cme
    out["images"] = [{"key": k, "label": l, "url": u} for k, (l, u) in IMGS.items()]
    return out

MOVIES = {w: f"https://sdo.gsfc.nasa.gov/assets/img/latest/mpeg/latest_512_{w}.mp4" for w in ("0171", "0304", "0193", "0131", "HMIIC")}
def movies():
    """Last-Modified of NASA SDO's latest-48h MP4s (HEAD only, cached 15 min): shows when NASA last rebuilt each movie."""
    out = {}
    for w, u in MOVIES.items():
        c = _cache.get("mv_" + w); t = time.time()
        if not c or t - c["t"] > 900:
            lm = None
            try:
                with urllib.request.urlopen(urllib.request.Request(u, method="HEAD", headers={"User-Agent": UA}), timeout=10) as r:
                    from email.utils import parsedate_to_datetime
                    lm = parsedate_to_datetime(r.headers.get("Last-Modified")).astimezone(timezone.utc); size = int(r.headers.get("Content-Length") or 0)
                c = {"t": t, "lm": lm, "size": size}
            except Exception:
                c = {"t": t, "lm": (c or {}).get("lm"), "size": (c or {}).get("size")}
            _cache["mv_" + w] = c
        out[w] = {"url": u, "url1024": u.replace("_512_", "_1024_"), "updated": iso(c["lm"]), "updated_et": et(c["lm"]), "mb": round((c.get("size") or 0) / 1e6, 1)}
    return out

def collect():
    if _memo["p"] and time.time() - _memo["t"] < 60: return _memo["p"]
    p = build(fetch())
    try: p["movies"] = movies()
    except Exception: p["movies"] = {}
    _memo.update(t=time.time(), p=p); return p

def handle_get(path, qs):
    if path == "/api/solar_seismic/live": return 200, collect()
    m = re.match(r"^/api/solar_seismic/img/([a-z0-9_]+)$", path)
    if m and m.group(1) in IMGS:
        b, meta = cached("img_" + m.group(1), IMGS[m.group(1)][1], 300, timeout=25)
        if not b: return 503, {"error": "source temporarily unavailable", "source": IMGS[m.group(1)][1]}
        return 200, b, "image/jpeg"
    m = re.match(r"^/api/solar_seismic/usgs/([a-z0-9_.]+)$", path)
    if m and m.group(1) in USGS:
        b, meta = cached("usgs_" + m.group(1), USGS[m.group(1)], 55)
        if not b: return 503, {"error": "source temporarily unavailable", "source": USGS[m.group(1)]}
        return 200, b, "application/json"
    return 404, {"error": "not found"}
