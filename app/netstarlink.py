"""Starlink page (/network/starlink) and "Networks near me" (/network/near) for the network status pages (t479, Nov 1 2026).
Called from netpages.py (routes /network/starlink, /network/near, /api/network/starlink*, /api/network/near); never imported elsewhere
except spacex.py, which reuses the shared CelesTrak Starlink file so this host downloads GROUP=starlink once per refresh, not twice.

Data (all free; nothing about the visitor is stored; a searched place is only kept as rounded coordinates in a 10-minute memory cache):
  CelesTrak GP (OMM CSV, GROUP=starlink): orbital elements, downloaded at most every 6 h (CelesTrak updates every 2 h and allows
      one download per update); after ANY error we wait 2 h before trying again (CelesTrak firewalls IPs that repeat errors).
      Positions are propagated in the visitor's browser with satellite.js (SGP4); the server only sends a capped sample.
  CelesTrak SATCAT (NAME=STARLINK, CSV): operational status, launch and re-entry dates; downloaded at most every 12 h.
  IODA (Georgia Tech Internet Intelligence Lab) API v2: outage alerts, events and signals for Starlink's network AS14593,
      for regions/countries and a few large US ISPs; cached 10-60 min.
  Cloudflare Radar API (optional, only if BN_CF_RADAR_TOKEN is set): AS14593 speed summary + outage annotations.
      Without a token the page shows a dated snapshot pulled on Nov 1 2026.
  Published speed figures (Ookla) are constants with source and date. Weather comes from weather.py (NWS, MeteoAlarm,
  Open-Meteo, GDACS). Location search: newsletter_zip.json (US Census ZCTA centroids) for ZIP codes, Open-Meteo geocoding
  for places, US Census geocoder for street addresses (the street is never echoed or logged).
Memory: bounded caches only (<= 300 keys); the satellite sample is pre-serialized (~120 KB and ~330 KB); no server-side propagation.
Never touches scanner.py, push.py, jets.py, config.json or aviation_watch.py."""
import csv, json, math, os, re, sys, threading, time, unicodedata, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__)); SITE = "https://blackout.network"
UA = "BlackoutNetwork-status/1.0 (+https://blackout.network/network/starlink; cached, polite)"
GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv"
SATCAT_URL = "https://celestrak.org/satcat/records.php?NAME=STARLINK&FORMAT=CSV"
GP_MAX_AGE = 6 * 3600; SATCAT_MAX_AGE = 12 * 3600; ERR_BACKOFF = 2 * 3600 + 300
IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; IODA_WEB = "https://ioda.inetintel.cc.gatech.edu"
RADAR = "https://api.cloudflare.com/client/v4/radar"
ASN = 14593
SATJS = ("https://cdn.jsdelivr.net/npm/satellite.js@6.0.1/dist/satellite.min.js", "sha384-ks/q8WwP74/nmNCaw/3Kj9Iv2xK5DsfHUJx18wEND2nHyRN7wjPfXjJF1Ejyj1lH")
SAMPLES = (1500, 4000)
WX_HELP = "https://www.starlink.com/support/article/d95f8988-53bb-98d5-badc-604b4f609638"

_S = getattr(sys, "_bn_netsl", None)
if _S is None:
    _S = sys._bn_netsl = {"c": {}, "lk": threading.Lock(), "kl": {}, "bo": {}, "err": {}, "gp": None, "sc": None, "sem": threading.BoundedSemaphore(3)}

def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def _klock(key):
    with _S["lk"]:
        kl = _S["kl"]
        if len(kl) > 800:
            for k in [k for k, v in kl.items() if not v.locked()][:400]: kl.pop(k, None)
        return kl.setdefault(key, threading.Lock())
def cached(key, ttl, fn, maxn=300):
    c = _S["c"]; hit = c.get(key)
    if hit and time.time() - hit[0] < ttl: return hit[1]
    with _klock(key):
        hit = c.get(key)
        if hit and time.time() - hit[0] < ttl: return hit[1]
        try: v = fn()
        except Exception:
            if hit: c[key] = (time.time() - ttl + 120, hit[1]); return hit[1]   # serve the last good copy, retry in 2 min
            raise
        c[key] = (time.time(), v)
        if len(c) > maxn:
            for k, _ in sorted(c.items(), key=lambda kv: kv[1][0])[:maxn // 4]: c.pop(k, None)
        return v
def http(url, timeout=12, accept="application/json", headers=None, cap=8_000_000):
    h = {"User-Agent": UA, "Accept": accept}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        if getattr(r, "status", 200) != 200: raise RuntimeError(f"HTTP {r.status}")
        return r.read(cap)
def jget(url, **k): return json.loads(http(url, **k).decode("utf-8", "replace"))
def ioda_jget(url, **k):
    """IODA JSON. Keeps Georgia Tech's copyright string exactly as returned, for same-origin responses."""
    d = jget(url, **k)
    c = d.get("copyright") if isinstance(d, dict) else None
    if isinstance(c, str) and c.strip(): _S["ioda_copyright"] = c
    return d
def _errname(e): return f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else type(e).__name__

# ---------------------------------------------------------------- CelesTrak files (shared on disk, polite refresh)
def cache_dir():
    d = os.environ.get("BN_STARLINK_CACHE_DIR") or os.path.join(os.environ.get("BN_STATE_DIR") or "/tmp", "bn_starlink")
    os.makedirs(d, mode=0o700, exist_ok=True); return d
def celestrak_file(name, url, max_age):
    """(path or None, mtime or None, error or None). Downloads only when the copy is older than max_age; after any error, waits 2 h."""
    p = os.path.join(cache_dir(), name)
    def have(): return (p, os.path.getmtime(p)) if os.path.exists(p) else (None, None)
    fp, mt = have()
    if mt and time.time() - mt < max_age: return fp, mt, None
    if time.time() < _S["bo"].get(name, 0): return fp, mt, _S["err"].get(name)
    with _klock("ct:" + name):
        fp, mt = have()
        if mt and time.time() - mt < max_age: return fp, mt, None
        if time.time() < _S["bo"].get(name, 0): return fp, mt, _S["err"].get(name)
        try:
            b = http(url, timeout=45, accept="text/csv", cap=16_000_000)
            if not b.startswith(b"OBJECT_NAME") or b.count(b"\n") < 1000: raise RuntimeError("unexpected response, not the CSV")
            tmp = p + ".tmp"
            with open(tmp, "wb") as f: f.write(b)
            os.replace(tmp, p); _S["err"].pop(name, None)
            return p, os.path.getmtime(p), None
        except Exception as e:
            _S["bo"][name] = time.time() + ERR_BACKOFF; _S["err"][name] = _errname(e)
            return fp, mt, _S["err"][name]
def gp_csv_text():
    """For spacex.py: the shared Starlink GP CSV (same file, same refresh rule), or None."""
    p, mt, err = celestrak_file("gp.csv", GP_URL, GP_MAX_AGE)
    if not p: return None
    with open(p, encoding="utf-8", errors="replace") as f: return f.read()

OPS = {"+": "Operational", "P": "Partially operational", "B": "Backup", "S": "Spare", "X": "Extended mission", "-": "Non-operational", "?": "Unknown"}
def satcat():
    p, mt, err = celestrak_file("satcat.csv", SATCAT_URL, SATCAT_MAX_AGE)
    st = _S.get("sc")
    if not p: return {"ok": False, "error": err or "not loaded yet"}
    if st and st["mt"] == mt: return dict(st, error=err)
    with _klock("parse:satcat"):
        st = _S.get("sc")
        if st and st["mt"] == mt: return dict(st, error=err)
        t = now(); ym = t.strftime("%Y-%m"); pm = (t.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"); yy = t.strftime("%Y")
        d30 = (t - timedelta(days=30)).strftime("%Y-%m-%d")
        s = dict(ok=True, mt=mt, fetched=iso(datetime.fromtimestamp(mt, timezone.utc)), total=0, in_orbit=0, decayed=0, decayed_30d=0, status={},
                 month=ym, prev_month=pm, year=yy, sats_month=0, sats_prev=0, sats_year=0, last_launch=None, nonplus={})
        lm, lp, ly = set(), set(), set()
        with open(p, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                if r.get("OBJECT_TYPE") != "PAY": continue
                s["total"] += 1; dec = r.get("DECAY_DATE") or ""; code = r.get("OPS_STATUS_CODE") or "?"; ld = r.get("LAUNCH_DATE") or ""; lid = (r.get("OBJECT_ID") or "")[:8]
                if dec:
                    s["decayed"] += 1
                    if dec >= d30: s["decayed_30d"] += 1
                else:
                    s["in_orbit"] += 1; s["status"][code] = s["status"].get(code, 0) + 1
                    if code != "+":
                        try: s["nonplus"][int(r["NORAD_CAT_ID"])] = code
                        except Exception: pass
                if ld.startswith(ym): s["sats_month"] += 1; lm.add(lid)
                if ld.startswith(pm): s["sats_prev"] += 1; lp.add(lid)
                if ld.startswith(yy): s["sats_year"] += 1; ly.add(lid)
                if ld and (not s["last_launch"] or ld > s["last_launch"]): s["last_launch"] = ld
        s.update(launches_month=len(lm), launches_prev=len(lp), launches_year=len(ly))
        _S["sc"] = s
        return dict(s, error=err)

MU = 398600.4418; RE = 6378.137
def _alt(mm):
    n = mm * 2 * math.pi / 86400.0
    return (MU / (n * n)) ** (1 / 3) - RE if n > 0 else None
def gp():
    """Parsed GP summary + pre-serialized samples. Re-parsed only when the file (or the SATCAT status join) changes."""
    p, mt, err = celestrak_file("gp.csv", GP_URL, GP_MAX_AGE)
    if not p: return {"ok": False, "error": err or "not loaded yet"}
    sc = satcat(); sck = sc.get("mt")
    st = _S.get("gp")
    if st and st["mt"] == mt and st["sck"] == sck: return dict(st, error=err)
    with _klock("parse:gp"):
        st = _S.get("gp")
        if st and st["mt"] == mt and st["sck"] == sck: return dict(st, error=err)
        rows = []; nonplus = sc.get("nonplus") or {}
        with open(p, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                try:
                    e = r["EPOCH"]; ep = datetime.strptime(e[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() + (float("0" + e[19:26]) if len(e) > 20 else 0)
                    mm = float(r["MEAN_MOTION"]); no = int(r["NORAD_CAT_ID"])
                    rows.append((no, round(ep, 3), mm, float(r["ECCENTRICITY"]), float(r["INCLINATION"]), float(r["RA_OF_ASC_NODE"]), float(r["ARG_OF_PERICENTER"]),
                                 float(r["MEAN_ANOMALY"]), float(r["BSTAR"] or 0), _alt(mm)))
                except Exception: continue
        rows.sort()
        tnow = time.time(); alts = sorted(x[9] for x in rows if x[9])
        shells = {}
        for x in rows:
            k = int(round(x[4])); shells[k] = shells.get(k, 0) + 1
        shells = sorted(((k, v) for k, v in shells.items() if v >= 50), key=lambda kv: -kv[1])[:6]
        ages = sorted((tnow - x[1]) / 3600 for x in rows)
        def code(no):
            if not sc.get("ok"): return None
            c = nonplus.get(no)
            return 0 if c is None else (1 if c == "P" else 2)
        payloads = {}
        for n in SAMPLES:
            step = max(1.0, len(rows) / n); pick = [rows[int(i * step)] for i in range(min(n, len(rows)))]
            sats = [[x[0], x[1], round(x[2], 8), round(x[3], 7), round(x[4], 4), round(x[5], 4), round(x[6], 4), round(x[7], 4), float(f"{x[8]:.5g}"), code(x[0])] for x in pick]
            payloads[n] = json.dumps({"fetched": iso(datetime.fromtimestamp(mt, timezone.utc)), "total": len(rows), "n": len(sats), "source": GP_URL,
                                      "fields": ["norad", "epoch_unix", "mean_motion", "ecc", "inc", "raan", "argp", "ma", "bstar", "status"],
                                      "status_codes": {"0": "operational", "1": "partially operational", "2": "other (backup, spare, non-operational)", "null": "unknown"},
                                      "sats": sats}, separators=(",", ":")).encode()
        st = dict(ok=True, mt=mt, sck=sck, fetched=iso(datetime.fromtimestamp(mt, timezone.utc)), total=len(rows),
                  alt_median=round(alts[len(alts) // 2]) if alts else None, below_400=sum(1 for a in alts if a < 400), above_400=sum(1 for a in alts if a >= 400),
                  shells=shells, age_median_h=round(ages[len(ages) // 2], 1) if ages else None, payloads=payloads)
        _S["gp"] = st
        return dict(st, error=err)
def gp_payload(n):
    g = gp()
    if not g.get("ok"): return 503, {"error": "orbital data not available right now", "detail": g.get("error")}
    n = min(SAMPLES, key=lambda s: abs(s - n))
    return 200, g["payloads"][n], "application/json"

# ---------------------------------------------------------------- IODA (Georgia Tech) measurements
DS = {"bgp": "BGP (routes visible)", "ping-slash24": "Active probing", "merit-nt": "Network telescope", "gtr": "Google traffic", "gtr-norm": "Google traffic"}
STRONG = {"bgp", "ping-slash24", "gtr", "gtr-norm"}
def ioda_alerts(etype, code, hours=24):
    def f():
        t = int(time.time()); u = f"{IODA}/outages/alerts?" + urllib.parse.urlencode({"entityType": etype, "entityCode": code, "from": t - hours * 3600, "until": t, "limit": 200})
        return [dict(ds=a.get("datasource"), level=a.get("level"), time=a.get("time"), value=a.get("value"), hist=a.get("historyValue")) for a in (ioda_jget(u).get("data") or [])]
    return cached(("ia", etype, str(code), hours), 600, f)
def ioda_events(etype, code, days=91):
    def f():
        t = int(time.time()); u = f"{IODA}/outages/events?" + urllib.parse.urlencode({"entityType": etype, "entityCode": code, "from": t - days * 86400, "until": t, "limit": 300})
        return [dict(start=e.get("start"), dur=e.get("duration"), ds=e.get("datasource"), score=e.get("score")) for e in (ioda_jget(u).get("data") or [])]
    return cached(("ie", etype, str(code), days), 3600, f)
def ioda_signals(code):
    def f():
        t = int(time.time()); u = f"{IODA}/signals/raw/asn/{code}?" + urllib.parse.urlencode({"from": t - 86400, "until": t})
        d = ioda_jget(u).get("data") or []
        if d and isinstance(d[0], list): d = d[0]
        out = []
        for s in d:
            if s.get("datasource") not in ("bgp", "ping-slash24", "merit-nt", "gtr", "gtr-norm"): continue   # skip loss/latency series (nested objects)
            v = [x if isinstance(x, (int, float)) else None for x in (s.get("values") or [])]; k = max(1, len(v) // 96)
            pts = []
            for i in range(0, len(v), k):
                seg = [x for x in v[i:i + k] if x is not None]; pts.append(round(sum(seg) / len(seg), 2) if seg else None)
            out.append(dict(ds=s.get("datasource"), start=s.get("from"), step=(s.get("step") or 300) * k, values=pts))
        return out
    return cached(("is", str(code)), 900, f)
def _norm(s): return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower())
def ioda_region_code(cc, admin1):
    if not cc or not admin1: return None
    def f():
        u = f"{IODA}/entities/query?" + urllib.parse.urlencode({"entityType": "region", "relatedTo": f"country/{cc}", "limit": 400})
        return {_norm(e.get("name")): (e.get("code"), e.get("name")) for e in (ioda_jget(u).get("data") or [])}
    try: m = cached(("ir", cc), 86400, f)
    except Exception: return None
    return m.get(_norm(admin1))
def health(alerts, hours=2):
    """Level from the latest alert per datasource: a fresh critical drop in BGP/probing/Google traffic = degraded; telescope-only = minor."""
    last = {}
    for a in alerts or []:
        if a["ds"] and (a["ds"] not in last or (a["time"] or 0) > (last[a["ds"]]["time"] or 0)): last[a["ds"]] = a
    fresh = [a for a in last.values() if a["level"] in ("critical", "warning") and time.time() - (a["time"] or 0) < hours * 3600]
    strong = [a for a in fresh if a["ds"] in STRONG]
    lv = 2 if any(a["level"] == "critical" for a in strong) else (1 if strong or fresh else 0)
    names = sorted({DS.get(a["ds"], a["ds"]) for a in fresh})
    n24 = sum(1 for a in alerts or [] if a["level"] in ("critical", "warning"))
    if lv == 0: txt = "No outage signals right now" + (f" ({n24} brief alert(s) in the last 24 h, since cleared)" if n24 else " and none in the last 24 h")
    elif lv == 1 and not strong: txt = "Minor: one noisy signal (" + ", ".join(names) + ") dipped; not confirmed by other measurements"
    else: txt = ("Drop detected in " if lv == 2 else "Possible drop in ") + ", ".join(names) + " in the last 2 h"
    return lv, txt, fresh

# ---------------------------------------------------------------- Cloudflare Radar (optional token; never printed)
RADAR_SNAPSHOT = dict(pulled="Nov 1, 2026", window="Aug 3 to Nov 1, 2026", down=62.1, up=9.4, lat_idle=62.3, lat_loaded=118.1, jitter_idle=29.6, loss=1.13, tests=100874,
                      outages_note="Cloudflare Radar listed no Starlink (AS14593) outage annotations in the 52 weeks to Nov 1, 2026 (checked Nov 1, 2026).")
def radar_token(): return (os.environ.get("BN_CF_RADAR_TOKEN") or "").strip()
def radar(path, params, ttl):
    tok = radar_token()
    if not tok: return None
    def f():
        return jget(f"{RADAR}{path}?" + urllib.parse.urlencode(dict(params, format="json")), headers={"Authorization": "Bearer " + tok}, timeout=12).get("result")
    try: return cached(("radar", path, json.dumps(params, sort_keys=True)), ttl, f)
    except Exception: return None
def radar_speed():
    r = radar("/quality/speed/summary", {"asn": ASN}, 6 * 3600)
    try:
        s = r["summary_0"]; m = r["meta"]; dr = (m.get("dateRange") or [{}])[0]
        fd = lambda x: datetime.strptime(x[:10], "%Y-%m-%d").strftime("%b %-d, %Y")
        return dict(live=True, window=f'{fd(dr["startTime"])} to {fd(dr["endTime"])}', down=round(float(s["bandwidthDownload"]), 1), up=round(float(s["bandwidthUpload"]), 1),
                    lat_idle=round(float(s["latencyIdle"]), 1), lat_loaded=round(float(s["latencyLoaded"]), 1), jitter_idle=round(float(s["jitterIdle"]), 1),
                    loss=round(float(s["packetLoss"]), 2), tests=(m.get("totalTests") or [None])[0], pulled=m.get("lastUpdated"))
    except Exception: return dict(RADAR_SNAPSHOT, live=False)
def radar_outages():
    r = radar("/annotations/outages", {"asn": ASN, "dateRange": "52w", "limit": 20}, 1800)
    if r is None: return None
    return [dict(start=a.get("startDate"), end=a.get("endDate"), cause=(a.get("outage") or {}).get("outageCause"), kind=(a.get("outage") or {}).get("outageType"),
                 desc=a.get("description"), url=a.get("linkedUrl")) for a in (r.get("annotations") or [])]

# ---------------------------------------------------------------- attribution (Compliance, 2026-11-01). Exact wording. No Radar token: dated snapshot unless one is already set.
def _radar_retrieved(spd):
    p = (spd or {}).get("pulled") or RADAR_SNAPSHOT["pulled"]
    if isinstance(p, str) and "T" in p[:22]:
        try: return datetime.strptime(p[:10], "%Y-%m-%d").strftime("%b %-d, %Y")
        except Exception: return p
    return str(p)
def ioda_credit_text(when):
    return ("Outage data: IODA (Internet Outage Detection and Analysis), Internet Intelligence Lab, Georgia Institute of Technology, "
            f"{IODA_WEB}/asn/{ASN} · © Georgia Tech Research Corporation. Charts drawn by BLACKOUT.NETWORK from IODA's API, retrieved {when}. "
            "Automated measurements, not a Starlink statement. IODA does not endorse BLACKOUT.NETWORK.")
def ioda_credit_html(np, when):
    return ('<p class="np-attr">Outage data: <b>IODA</b> (Internet Outage Detection and Analysis), Internet Intelligence Lab, Georgia Institute of Technology, '
            f'<a href="{IODA_WEB}/asn/{ASN}" target="_blank" rel="noopener">{IODA_WEB}/asn/{ASN}</a> · © Georgia Tech Research Corporation. '
            f'Charts drawn by BLACKOUT.NETWORK from IODA\'s API, retrieved {np.E(when)}. Automated measurements, not a Starlink statement. IODA does not endorse BLACKOUT.NETWORK.</p>')
def radar_credit_text(spd):
    window = (spd or {}).get("window") or RADAR_SNAPSHOT["window"]; pulled = _radar_retrieved(spd)
    return (f"Speed and outage figures: Cloudflare Radar, AS{ASN} (Starlink), {window}, retrieved {pulled}, "
            f"https://radar.cloudflare.com/as{ASN} · Licensed under CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/). "
            "Values rounded and reformatted by BLACKOUT.NETWORK. Cloudflare does not endorse BLACKOUT.NETWORK.")
def radar_credit_html(np, spd):
    window = (spd or {}).get("window") or RADAR_SNAPSHOT["window"]; pulled = _radar_retrieved(spd)
    return (f'<p class="np-attr">Speed and outage figures: <b>Cloudflare Radar</b>, AS{ASN} (Starlink), {np.E(window)}, retrieved {np.E(pulled)}, '
            f'<a href="https://radar.cloudflare.com/as{ASN}" target="_blank" rel="noopener">https://radar.cloudflare.com/as{ASN}</a> · '
            'Licensed under <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" rel="noopener">CC BY-NC 4.0</a>. '
            'Values rounded and reformatted by BLACKOUT.NETWORK. Cloudflare does not endorse BLACKOUT.NETWORK.</p>')
def same_origin(headers):
    """True only for a browser request from one of our own pages. Curl and other sites get the stripped payload."""
    h = {str(k).lower(): (v or "") for k, v in (headers or {}).items()}
    sfs = h.get("sec-fetch-site", "").strip().lower()
    if sfs == "cross-site": return False
    if sfs == "same-origin": return True
    host = h.get("host", "").split(",")[0].strip().lower()
    def netloc(url):
        try:
            u = urllib.parse.urlparse(url)
            return u.netloc.lower() if u.scheme in ("http", "https") and u.netloc else ""
        except Exception: return ""
    if host and netloc(h.get("origin", "")) == host: return True
    if host and sfs != "cross-site" and netloc(h.get("referer") or h.get("referrer") or "") == host: return True
    return False
IODA_GROUPS = {"satellite", "local", "isp"}
def _ioda_meta(d, np, when):
    d["attribution"] = ioda_credit_text(when)
    d["license"] = "All Rights Reserved"
    d["attribution_html"] = ioda_credit_html(np, when)
    c = _S.get("ioda_copyright")
    if isinstance(c, str) and c: d["copyright"] = c   # IODA's own string, unchanged
    return d
def brief_out(np, headers):
    if not same_origin(headers):
        return {"slug": "starlink", "name": "Starlink", "page": "/network/starlink",
                "note": "IODA outage measurements are shown on the Starlink page and are not included in this response."}
    b = brief(np)
    return _ioda_meta(b, np, b.get("fetched_et") or np.fmt_et(now()))
def near_out(body, np, headers):
    if not isinstance(body, dict) or not same_origin(headers):
        out = dict(body or {})
        names = {n.get("name") for n in (out.get("networks") or []) if n.get("group") in IODA_GROUPS}
        out["networks"] = [n for n in (out.get("networks") or []) if n.get("group") not in IODA_GROUPS]
        out["impact"] = [x for x in (out.get("impact") or []) if not any(nm and nm in x and ("our checks" in x.lower() or "at the same time" in x.lower()) for nm in names)]
        out.pop("attribution", None); out.pop("attribution_html", None); out.pop("copyright", None); out.pop("license", None)
        out["note"] = "IODA network measurements are shown on the page and are not included in this response."
        return out
    return _ioda_meta(dict(body), np, np.fmt_et(now()))

# ---------------------------------------------------------------- published speed figures (constants: always with source and date)
SPEEDS = [dict(who="Ookla Speedtest Intelligence", scope="United States, Q1 2026 median of Speedtest users on Starlink", down=127.39, up=21.46, lat=39, latk="median multi-server latency",
               published="May 5, 2026", title="Starlink Hits New U.S. Highs", url="https://www.ookla.com/articles/starlink-hits-new-us-highs", checked="Nov 1, 2026")]

# ---------------------------------------------------------------- Starlink availability (country level only; honest about limits)
STARLINK_MAP = "https://www.starlink.com/map"
NOT_OFFERED = {"CN": "China", "RU": "Russia", "KP": "North Korea", "SY": "Syria", "AF": "Afghanistan", "HK": "Hong Kong", "MO": "Macao", "BY": "Belarus"}
NOT_OFFERED_SRC = ("Mappr summary of Starlink's own availability data, May 2026", "https://www.mappr.co/starlink-availability-by-country/")
def starlink_avail(cc):
    cc = (cc or "").upper()
    if cc in ("US", "PR", "GU", "VI", "AS", "MP"):
        return dict(level="yes", text="Starlink sells service across the United States. Some areas are waitlisted or sold out at times, so check your exact address on Starlink's map.",
                    url=STARLINK_MAP)
    if cc in NOT_OFFERED:
        return dict(level="no", text=f"Starlink does not offer service in {NOT_OFFERED[cc]}, according to Starlink's own availability data (as summarized in May 2026).",
                    url=NOT_OFFERED_SRC[1], src=NOT_OFFERED_SRC[0])
    return dict(level="unknown", text="Starlink says it is available in 150+ countries and markets. We don't check your country automatically yet, so confirm it on Starlink's map.", url=STARLINK_MAP)

# ---------------------------------------------------------------- Starlink brief (accordion + hub card)
def _ev_inc(e):
    st = datetime.fromtimestamp(e["start"], timezone.utc) if e.get("start") else None
    en = st + timedelta(seconds=e["dur"]) if st and e.get("dur") else None
    return dict(start=st, end=en, sev=2 if e.get("ds") in STRONG else 1, title=f'Outage signal on Starlink\'s network: {DS.get(e.get("ds"), e.get("ds"))}',
                url=f"{IODA_WEB}/asn/{ASN}", src="IODA (Georgia Tech)", summary="Detected automatically by IODA's internet measurements. Starlink has not confirmed a cause.", regions=[], services=[])
def starlink_status():
    out = dict(level=-1, text="Measurements unavailable right now", fresh=[], events=[], error=None, fetched=iso(now()))
    try:
        al = ioda_alerts("asn", ASN, 24); lv, txt, fresh = health(al); out.update(level=lv, text=txt, fresh=fresh)
    except Exception as e: out["error"] = _errname(e)
    try: out["events"] = ioda_events("asn", ASN, 91)
    except Exception as e: out["error"] = out["error"] or _errname(e)
    return out
def brief(np):
    s = starlink_status(); incs = [_ev_inc(e) for e in s["events"] if e.get("start")]; incs.sort(key=lambda i: i["start"], reverse=True)
    lt = incs[0] if incs else None; lv = s["level"]
    return dict(slug="starlink", name="Starlink", level=lv, level_name=np.LVN.get(lv, ""), status=s["text"], active=1 if lv > 0 else 0,
                latest=np.jsonable(lt) if lt else None, weeks=np.weekly(incs), uptime7=[], uptime_pct=None, page="/network/starlink",
                tips=["Open the Starlink app: it shows outages, obstructions and dish status", "Restart the dish and router by unplugging power for a minute", "Heavy rain or snow can slow Starlink; check the weather where the dish is"],
                status_url=f"{IODA_WEB}/asn/{ASN}", status_name="IODA: Starlink AS14593", console=["Starlink support", "https://www.starlink.com/support"],
                coverage="IODA outage events for AS14593 over the last 13 weeks. Starlink publishes no public status feed", latest_label="Latest outage signal (IODA)", source_label="IODA event",
                weeks_note="From IODA (Georgia Tech) internet measurements of AS14593.", error=s["error"], stale=None, fetched=s["fetched"], fetched_et=np.fmt_et(now()))

# ---------------------------------------------------------------- page graphics
IC_EXTRA = {
 "satellite": '<path d="M13 7 9 3 5 7l4 4M17 11l4 4-4 4-4-4M8 12l4 4M16 8l-4-4"/><path d="m9.5 9.5 5 5"/><path d="M4 20a6 6 0 0 0 6-6"/>',
 "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
 "storm": '<path d="M7 15h9a4 4 0 0 0 .5-7.97A6 6 0 0 0 5.1 8.2 4 4 0 0 0 7 15z"/><path d="m12 15-2 4h3l-2 4"/>',
 "speed": '<path d="M4 15a8 8 0 1 1 16 0"/><path d="m12 15 4-5"/>',
 "search": '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.3-4.3"/>',
}
def _ic(np, n, cls="np-ic"):
    body = IC_EXTRA.get(n) or np.IC.get(n, np.IC["unknown"])
    return f'<svg class="{cls} icon-{n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'
def _day(d):
    try: return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception: return d or "—"
def _fmt(n): return "—" if n is None else (f"{n:,}" if isinstance(n, int) else str(n))
def _pct(a, b): return f"{100 * a / b:.1f}%" if a is not None and b else "—"
def _spark(sig):
    if not sig: return '<p class="np-mu">IODA signals unavailable right now.</p>'
    cols = {"bgp": "#4aa3ff", "ping-slash24": "#2BB673", "merit-nt": "#8a94a3", "gtr": "#F5A524", "gtr-norm": "#F5A524"}
    W, H = 600, 120; lines, leg = [], []; band = H / max(1, len(sig))
    for i, s in enumerate(sig):
        v = [x for x in s["values"] if x is not None]
        if not v: continue
        mx = max(v) or 1; n = len(s["values"]); y0 = band * (i + 1) - 6
        pts = " ".join(f'{W * j / max(1, n - 1):.1f},{y0 - (band - 14) * (x / mx):.1f}' for j, x in enumerate(s["values"]) if x is not None)
        c = cols.get(s["ds"], "#c9d1db"); lines.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.6"><title>{DS.get(s["ds"], s["ds"])}</title></polyline>')
        leg.append(f'<span><i style="background:{c}"></i>{DS.get(s["ds"], s["ds"])}</span>')
    return (f'<svg class="np-months" viewBox="0 0 {W} {H + 14}" role="img" aria-label="IODA signals for Starlink, last 24 hours">{"".join(lines)}'
            f'<text x="0" y="{H + 12}" font-size="10" fill="#8a94a3">24 h ago</text><text x="{W}" y="{H + 12}" font-size="10" fill="#8a94a3" text-anchor="end">now</text></svg>'
            f'<div class="np-legend">{"".join(leg)}<span>Each line is scaled to its own 24 h peak; a sharp dip is what matters.</span></div>')

SL_CSS = """
.sl-globe{position:relative;border:1px solid var(--line);border-radius:14px;background:radial-gradient(80% 80% at 50% 45%,#121a24,#07090c);aspect-ratio:16/10;min-height:260px;overflow:hidden}
.sl-globe canvas{width:100%;height:100%;display:block;touch-action:pan-y;cursor:grab}.sl-globe canvas:active{cursor:grabbing}
.sl-ph{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:#c9d1db;font-size:13px;text-align:center;padding:16px}.sl-ph .np-ic{width:34px;height:34px;color:#ff6b6e}
.sl-ctl{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}.sl-ctl .np-btn[aria-pressed=true]{border-color:#c8102e;background:rgba(200,16,46,.22)}
.sl-meta{font-size:12px;color:var(--mu,#8a94a3);margin-top:8px}.sl-key{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--mu,#8a94a3);margin-top:8px}.sl-key i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.sl-spd{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr));gap:12px}
.sl-num{display:flex;flex-wrap:wrap;gap:14px;margin:6px 0}.sl-num div{min-width:88px}.sl-num b{display:block;font:800 22px/1.1 var(--bn-font-ui,Montserrat,sans-serif)}.sl-num span{font-size:12px;color:var(--mu,#8a94a3)}
.sl-tv{font:800 20px/1.15 var(--bn-font-ui,Montserrat,sans-serif);display:block;margin:2px 0;overflow-wrap:anywhere}
.nm-form{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 0;position:relative;z-index:1}.nm-form input{flex:1 1 220px;min-width:0;font:500 15px/1.2 var(--bn-font-body,Inter,sans-serif);padding:11px 12px;border-radius:10px;border:1px solid var(--bd2,#2f3742);background:var(--bn-surface,#161b21);color:var(--tx,#e6e9ee)}
.nm-form input:focus-visible{outline:2px solid #c8102e;outline-offset:1px}
.nm-alts{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.nm-alts button{font:600 12px/1 var(--bn-font-ui,Montserrat,sans-serif);border:1px solid var(--line);background:transparent;color:var(--tx,#e6e9ee);border-radius:999px;padding:7px 10px;cursor:pointer}
.nm-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px;align-items:start}.nm-grid>.np-sec{margin-bottom:0}
.nm-net{border:1px solid var(--line);border-left:4px solid var(--c);border-radius:10px;padding:10px 12px;margin:0 0 8px;background:var(--bn-surface,#161b21);overflow-wrap:anywhere}
.nm-net h3{font-size:14.5px;margin:0 0 3px;display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}.nm-net p{font-size:13px;margin:4px 0 0;color:var(--bn-text-2,#c9d1db)}.nm-net small{display:block;font-size:12px;color:var(--mu,#8a94a3);margin-top:4px}
.nm-imp{position:relative;border:1px solid rgba(200,16,46,.55);background:linear-gradient(90deg,rgba(200,16,46,.18),rgba(22,27,33,.6));border-radius:14px;padding:14px 16px;margin:0 0 14px}
.nm-imp h2{font-size:17px;margin:0 0 6px;display:flex;gap:8px;align-items:center}.nm-imp h2 .np-ic{color:#ff6b6e}.nm-imp ul{margin:0;padding-left:18px}.nm-imp li{font-size:14px;margin:5px 0}
.nm-wx{border:1px solid var(--line);border-left:4px solid var(--c);border-radius:10px;padding:9px 12px;margin:0 0 8px;background:var(--bn-surface,#161b21);overflow-wrap:anywhere}.nm-wx b{font-size:14px}.nm-wx p{font-size:12.5px;margin:4px 0 0;color:var(--bn-text-2,#c9d1db)}
.nm-sub{font:700 11px/1.2 var(--bn-font-ui,Montserrat,sans-serif);letter-spacing:.1em;text-transform:uppercase;color:var(--mu,#8a94a3);margin:14px 0 6px}
.np-hubq{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:0 0 14px;background:var(--pn,#12161b)}
.np-hubq form{display:flex;gap:8px;flex:1 1 320px;margin:0}.np-hubq b{font-family:var(--bn-font-ui,Montserrat,sans-serif);font-size:15px;display:flex;gap:8px;align-items:center}
@media(max-width:900px){.nm-grid{grid-template-columns:1fr}.nm-grid>.np-sec{margin-bottom:14px}}
@media(max-width:560px){.sl-globe{aspect-ratio:1/1}.nm-form .np-btn{flex:1 1 100%;justify-content:center}.np-hubq form{flex-wrap:wrap}.np-hubq .np-btn{flex:1 1 100%;justify-content:center}}
html[data-theme=light] .nm-net,html[data-theme=light] .nm-wx,html[data-theme=light] .np-hubq{background:#fff}html[data-theme=light] .nm-imp{background:linear-gradient(90deg,rgba(200,16,46,.12),#fff)}
.np-attr{font-size:12.5px;line-height:1.45;color:var(--mu,#8a94a3);margin:8px 0 0}.np-attr b{color:var(--tx,#e6e9ee)}
"""

GLOBE_JS = r"""<script>(function(){
var box=document.getElementById("sl_globe");if(!box)return;var started=false,ph=box.querySelector(".sl-ph");
function ga(n,p){try{if(window.gtag)gtag("event",n,p)}catch(e){}}
ga("starlink_view",{section:"page"});
function loadScript(u,i){return new Promise(function(ok,no){if(window.satellite)return ok();var s=document.createElement("script");s.src=u;s.integrity=i;s.crossOrigin="anonymous";s.onload=ok;s.onerror=function(){no(new Error("satellite.js did not load"))};document.head.appendChild(s)})}
function topo(t){var tr=t.transform,arcs=t.arcs.map(function(a){var x=0,y=0;return a.map(function(p){if(!tr)return p;x+=p[0];y+=p[1];return [x*tr.scale[0]+tr.translate[0],y*tr.scale[1]+tr.translate[1]]})});
 function ring(ix){var out=[];ix.forEach(function(i){var a=i<0?arcs[~i].slice().reverse():arcs[i];out=out.concat(out.length?a.slice(1):a)});return out}
 var rings=[];t.objects.countries.geometries.forEach(function(g){if(g.type==="Polygon")g.arcs.forEach(function(r){rings.push(ring(r))});else if(g.type==="MultiPolygon")g.arcs.forEach(function(p){p.forEach(function(r){rings.push(ring(r))})})});return rings}
function start(){if(started)return;started=true;var msg=ph.querySelector("p");msg.textContent="Loading orbital data…";var bt=document.getElementById("sl_start");if(bt)bt.remove();
 var small=matchMedia("(max-width:640px)").matches||(navigator.hardwareConcurrency||4)<=4,N=small?1500:4000;
 Promise.all([loadScript(%SATJS%),fetch("/api/network/starlink/gp?n="+N).then(function(r){if(!r.ok)throw new Error("orbital data unavailable right now");return r.json()}),
   fetch("/api/crime/static/countries-110m.json").then(function(r){return r.ok?r.json():null}).catch(function(){return null})])
 .then(function(r){run(r[1],r[2]?topo(r[2]):[],small);ga("starlink_view",{section:"constellation",points:r[1].n})})
 .catch(function(e){msg.textContent="The live view could not load ("+(e&&e.message||"error")+"). The numbers below come from the same data."})}
function run(D,land,small){var sat=window.satellite,cv=document.createElement("canvas"),cx=cv.getContext("2d");cv.setAttribute("role","img");cv.setAttribute("aria-label","Live positions of "+D.n+" Starlink satellites");box.appendChild(cv);ph.remove();
 var recs=[];D.sats.forEach(function(s){try{recs.push({r:sat.json2satrec({OBJECT_NAME:"STARLINK",OBJECT_ID:"",EPOCH:new Date(s[1]*1000).toISOString().replace("Z",""),MEAN_MOTION:s[2],ECCENTRICITY:s[3],INCLINATION:s[4],RA_OF_ASC_NODE:s[5],ARG_OF_PERICENTER:s[6],MEAN_ANOMALY:s[7],EPHEMERIS_TYPE:0,CLASSIFICATION_TYPE:"U",NORAD_CAT_ID:s[0],ELEMENT_SET_NO:999,REV_AT_EPOCH:0,BSTAR:s[8],MEAN_MOTION_DOT:0,MEAN_MOTION_DDOT:0}),st:s[9],p:null})}catch(e){}});
 var mode="globe",lon0=-80,lat0=22,paused=matchMedia("(prefers-reduced-motion: reduce)").matches,vis=true,W=0,H=0,dpr=Math.min(2,window.devicePixelRatio||1),last=0,lastProp=-1e9,drag=null,drawn=0;
 var meta=document.getElementById("sl_meta"),bP=document.getElementById("sl_pause");if(bP){bP.setAttribute("aria-pressed",paused?"true":"false");bP.textContent=paused?"Rotate":"Pause"}
 function size(){var b=box.getBoundingClientRect();W=b.width;H=b.height;cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);cx.setTransform(dpr,0,0,dpr,0,0);force=1}var force=1;size();addEventListener("resize",size);
 function prop(){var d=new Date(),g=sat.gstime(d);drawn=0;recs.forEach(function(o){try{var pv=sat.propagate(o.r,d);if(!pv||!pv.position){o.p=null;return}var gd=sat.eciToGeodetic(pv.position,g);o.p=[gd.latitude,gd.longitude,gd.height];drawn++}catch(e){o.p=null}});
  if(meta)meta.textContent="Showing "+drawn.toLocaleString()+" of "+D.total.toLocaleString()+" Starlink satellites with current orbital data (an even sample, so phones stay fast). Positions computed in your browser at "+d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit",second:"2-digit",timeZoneName:"short"})+" from CelesTrak data updated "+new Date(D.fetched).toLocaleString([],{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/New_York",timeZoneName:"short"})+"."}
 var R=Math.PI/180;
 function proj(la,lo,h){if(mode==="flat"){var x=((lo/R+540)%360)/360*W;return [x,(90-la/R)/180*H,1]}
  var R0=Math.min(W,H)*0.42,r=R0*(1+(h||0)/6371),l=lo-lon0*R,p0=lat0*R,cl=Math.cos(la),x=r*cl*Math.sin(l),y=r*(Math.cos(p0)*Math.sin(la)-Math.sin(p0)*cl*Math.cos(l)),z=Math.sin(p0)*Math.sin(la)+Math.cos(p0)*cl*Math.cos(l);
  if(z<0&&(x*x+y*y)<R0*R0)return null;return [W/2+x,H/2-y,z]}
 var cols=["#ff4d4f","#F5A524","#8a94a3"];
 function draw(t){requestAnimationFrame(draw);if(!vis&&!force)return;if(!force&&t-last<(small?66:33))return;force=0;var dt=Math.min(100,t-last);last=t;if(!paused&&!drag&&mode==="globe")lon0+=dt*0.004;
  if(t-lastProp>2000){prop();lastProp=t}
  cx.clearRect(0,0,W,H);var R0=Math.min(W,H)*0.42;
  if(mode==="globe"){var gr=cx.createRadialGradient(W/2-R0*.3,H/2-R0*.3,R0*.1,W/2,H/2,R0);gr.addColorStop(0,"#1b2735");gr.addColorStop(1,"#0c1219");cx.fillStyle=gr;cx.beginPath();cx.arc(W/2,H/2,R0,0,7);cx.fill();cx.strokeStyle="rgba(255,255,255,.14)";cx.lineWidth=1;cx.stroke()}
  else{cx.fillStyle="#0c1219";cx.fillRect(0,0,W,H)}
  cx.strokeStyle="rgba(201,209,219,.42)";cx.lineWidth=.7;cx.beginPath();
  land.forEach(function(rg){var pen=false,pl=null;for(var i=0;i<rg.length;i++){var la=rg[i][1]*R,lo=rg[i][0]*R,q;
    if(mode==="globe"){var l=lo-lon0*R,p0=lat0*R,z=Math.sin(p0)*Math.sin(la)+Math.cos(p0)*Math.cos(la)*Math.cos(l);if(z<0){pen=false;continue}}
    q=proj(la,lo,0);if(!q){pen=false;continue}if(mode==="flat"&&pl&&Math.abs(q[0]-pl[0])>W/2)pen=false;if(pen)cx.lineTo(q[0],q[1]);else cx.moveTo(q[0],q[1]);pen=true;pl=q}});cx.stroke();
  var sz=small?2:2.2;recs.forEach(function(o){if(!o.p)return;var q=proj(o.p[0],o.p[1],o.p[2]);if(!q)return;cx.fillStyle=o.p[2]<400?"#4aa3ff":(o.st==null?"#ff4d4f":cols[o.st]);cx.globalAlpha=q[2]<0?.35:.95;cx.fillRect(q[0]-1,q[1]-1,sz,sz)});cx.globalAlpha=1}
 cv.addEventListener("pointerdown",function(e){if(mode!=="globe")return;drag={x:e.clientX,y:e.clientY,l:lon0,a:lat0};try{cv.setPointerCapture(e.pointerId)}catch(_){}});
 cv.addEventListener("pointermove",function(e){if(!drag)return;lon0=drag.l-(e.clientX-drag.x)*0.3;lat0=Math.max(-80,Math.min(80,drag.a+(e.clientY-drag.y)*0.3))});
 cv.addEventListener("pointerup",function(){drag=null});cv.addEventListener("pointercancel",function(){drag=null});
 document.querySelectorAll("[data-sl-mode]").forEach(function(b){b.addEventListener("click",function(){mode=b.dataset.slMode;document.querySelectorAll("[data-sl-mode]").forEach(function(x){x.setAttribute("aria-pressed",x===b?"true":"false")})})});
 if(bP)bP.addEventListener("click",function(){paused=!paused;bP.setAttribute("aria-pressed",paused?"true":"false");bP.textContent=paused?"Rotate":"Pause"});
 if("IntersectionObserver" in window)new IntersectionObserver(function(es){vis=es[0].isIntersecting&&!document.hidden}).observe(box);
 document.addEventListener("visibilitychange",function(){vis=!document.hidden});requestAnimationFrame(draw)}
var b=document.getElementById("sl_start");if(b)b.addEventListener("click",start);
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){if(es[0].isIntersecting){io.disconnect();start()}},{rootMargin:"200px"});io.observe(box)}
})();</script>""".replace("%SATJS%", json.dumps(SATJS[0]) + "," + json.dumps(SATJS[1]))

# ---------------------------------------------------------------- Starlink page
def render(np):
    E = np.E; t = now(); sc = satcat(); g = gp(); stt = starlink_status()
    try: sig = ioda_signals(ASN)
    except Exception: sig = None
    spd = radar_speed(); outs = radar_outages(); lv = stt["level"]; ok = sc.get("ok")
    st = sc.get("status") or {}; ino = sc.get("in_orbit") if ok else None; op = st.get("+") if ok else None
    part = st.get("P", 0) if ok else None; other = sum(v for k, v in st.items() if k not in ("+", "P")) if ok else None
    mon = datetime.strptime(sc["month"], "%Y-%m").strftime("%B") if ok else ""; pmon = datetime.strptime(sc["prev_month"], "%Y-%m").strftime("%B") if ok else ""
    f_sc = np.fmt_et(np.pdt(sc.get("fetched"))) if ok else "—"; f_gp = np.fmt_et(np.pdt(g.get("fetched"))) if g.get("ok") else "—"
    ic = lambda n, c="np-ic": _ic(np, n, c)
    when = np.fmt_et(t); ioda_html = ioda_credit_html(np, when); radar_html = radar_credit_html(np, spd)
    hero = (f'<section class="np-hero page-header-band"><div class="np-hrow">{np.TILE}<div style="min-width:0"><div class="np-kick"><i></i>BLACKOUT.NETWORK · NETWORK STATUS</div>'
            f'<h1>Starlink status <em>and constellation</em></h1><p>SpaceX\'s satellite internet: the satellites in orbit right now, network health from independent internet measurements, '
            'speeds from published tests, and what the weather does to it.</p></div>' + np.gauge(lv) + '</div>'
            f'<div class="np-kpis"><div class="np-kpi">{np.lvchip(lv)}<span>{E(stt["text"])}</span><span>IODA measurements of AS14593</span></div>'
            f'<div class="np-kpi"><b>{_fmt(ino)}</b><span>satellites in orbit (CelesTrak catalog)</span></div>'
            f'<div class="np-kpi"><b>{_fmt(op)}</b><span>operational ({_pct(op, ino)} of those in orbit)</span></div>'
            f'<div class="np-kpi"><b>{_fmt(sc.get("launches_month"))}</b><span>Starlink launches in {E(mon)} so far ({_fmt(sc.get("sats_month"))} satellites). {E(pmon)}: {_fmt(sc.get("launches_prev"))} launches, {_fmt(sc.get("sats_prev"))} satellites.</span></div></div>'
            + ioda_html +
            f'<div class="np-btns"><a class="np-btn p" href="#constellation">{ic("satellite", "np-ic sm")}See the constellation</a><a class="np-btn" href="/network/near">{ic("pin", "np-ic sm")}Networks and weather near you</a>'
            f'<a class="np-btn" href="https://www.starlink.com/support" target="_blank" rel="noopener">{ic("link", "np-ic sm")}Starlink support</a></div>'
            + (f'<p class="np-note">The satellite catalog is not available right now ({E(sc.get("error"))}). Counts show as dashes until it loads; we don\'t guess them.</p>' if not ok else "")
            + (f'<p class="np-note">Showing the last good catalog copy (refresh failed: {E(sc.get("error"))}). As CelesTrak asks, we wait 2 hours before trying again.</p>' if ok and sc.get("error") else "") + '</section>')
    sec_glb = (f'<section class="np-sec" id="constellation"><h2>{ic("satellite")}The constellation, live</h2><p class="np-sub">Each dot is a Starlink satellite where it is right now, computed in your browser from public orbital data. Drag the globe to turn it.</p>'
               f'<div class="sl-globe" id="sl_globe"><div class="sl-ph">{ic("satellite")}<p>The live view loads when you scroll here.</p><button class="np-btn" type="button" id="sl_start">Load it now</button></div></div>'
               '<div class="sl-ctl"><button class="np-btn" type="button" data-sl-mode="globe" aria-pressed="true">Globe</button><button class="np-btn" type="button" data-sl-mode="flat" aria-pressed="false">Flat map</button><button class="np-btn" type="button" id="sl_pause" aria-pressed="false">Pause</button></div>'
               '<div class="sl-key"><span><i style="background:#ff4d4f"></i>Operational</span><span><i style="background:#F5A524"></i>Partially operational</span><span><i style="background:#8a94a3"></i>Backup, spare or non-operational</span><span><i style="background:#4aa3ff"></i>Below 400 km (raising or lowering its orbit)</span></div>'
               f'<p class="sl-meta" id="sl_meta">Orbital data: CelesTrak, updated {E(f_gp)}.</p></section>')
    shells = ", ".join(f"{k}° ({v:,})" for k, v in (g.get("shells") or [])[:4]) or "—"
    tiles = [("In orbit", _fmt(ino), f"Starlink satellites not yet re-entered, of {_fmt(sc.get('total'))} launched"),
             ("Operational", _fmt(op), "CelesTrak status: operational"), ("Partially operational", _fmt(part), "CelesTrak status: partially operational"),
             ("Other status", _fmt(other), "Backup, spare, non-operational or unknown"), ("Re-entered, last 30 days", _fmt(sc.get("decayed_30d")), f"{_fmt(sc.get('decayed'))} re-entered in all"),
             (f"Launched in {sc.get('year', '')}", _fmt(sc.get("sats_year")), f"satellites on {_fmt(sc.get('launches_year'))} launches"),
             ("With current orbital data", _fmt(g.get("total")), f"median data age {_fmt(g.get('age_median_h'))} h"),
             ("Below 400 km", _fmt(g.get("below_400")), f"newly launched or being lowered; median altitude {_fmt(g.get('alt_median'))} km"),
             ("Main orbital groups", f"{len(g.get('shells') or [])}" if g.get("shells") else "—", "by inclination: " + (" · ".join(f"{k}° {v:,}" for k, v in (g.get("shells") or [])[:4]) or "—"))]
    sec_st = (f'<section class="np-sec"><h2>{ic("chart")}Satellites by status</h2><p class="np-sub">From CelesTrak\'s satellite catalog (updated {E(f_sc)}) and orbital data (updated {E(f_gp)}). '
              f'New satellites can take a few days to appear. Latest Starlink launch in the catalog: {E(_day(sc.get("last_launch")))}.</p><div class="np-tiles">'
              + "".join(f'<div class="np-t"><small>{E(a)}</small><span class="sl-tv">{E(b)}</span><small>{E(c)}</small></div>' for a, b, c in tiles) + '</div></section>')
    evs = sorted([e for e in stt.get("events") or [] if e.get("start")], key=lambda e: -e["start"])[:8]
    evl = "".join(f'<li style="--c:{np.LVC[2 if e.get("ds") in STRONG else 1]}"><div class="w">{E(np.fmt_et(datetime.fromtimestamp(e["start"], timezone.utc)))} · about {max(1, round((e.get("dur") or 0) / 60))} min</div>'
                  f'<h3>{E(DS.get(e.get("ds"), e.get("ds")))} dropped</h3></li>' for e in evs)
    if outs is None: rad = f'<p class="np-mu">{E(RADAR_SNAPSHOT["outages_note"])}</p>'
    elif outs: rad = "<ul class='np-tl'>" + "".join(f'<li style="--c:#FF7A1A"><div class="w">{E(o["start"] or "")} → {E(o["end"] or "ongoing")}</div><h3>{E(o["cause"] or "Outage")}</h3><p>{E((o["desc"] or "")[:240])}</p></li>' for o in outs[:6]) + "</ul>"
    else: rad = '<p class="np-mu">Cloudflare Radar lists no Starlink (AS14593) outages in the last 52 weeks.</p>'
    sec_h = (f'<section class="np-sec"><h2>{ic("eye")}Network health</h2><p class="np-sub">Starlink publishes no public status feed, so we use independent measurements of its network (AS14593) by IODA at Georgia Tech. '
             'A drop means fewer Starlink addresses were reachable or announced; it does not tell us why.</p>'
             + (f'<p class="np-note">IODA could not be reached just now ({E(stt["error"])}).</p>' if stt.get("error") else "")
             + f'<h3 class="np-h3">Last 24 hours</h3>{_spark(sig)}{ioda_html}'
             + (f'<h3 class="np-h3">Outage signals in the last 13 weeks</h3><ul class="np-tl">{evl}</ul>' if evl else '<p class="np-mu" style="margin-top:10px">IODA recorded no outage events for Starlink in the last 13 weeks.</p>')
             + ioda_html
             + f'<h3 class="np-h3">Cloudflare Radar</h3>{rad}{radar_html}<p class="np-mu">Sources: <a href="{IODA_WEB}/asn/{ASN}" target="_blank" rel="noopener">IODA, AS14593</a> · <a href="https://radar.cloudflare.com/as14593" target="_blank" rel="noopener">Cloudflare Radar, AS14593</a>.</p></section>')
    ook = SPEEDS[0]
    cards = (f'<article class="np-card"><span class="d">{E(ook["who"])} · published {E(ook["published"])}</span><h3>{E(ook["scope"])}</h3>'
             f'<div class="sl-num"><div><b>{ook["down"]}</b><span>Mbps download</span></div><div><b>{ook["up"]}</b><span>Mbps upload</span></div><div><b>{ook["lat"]} ms</b><span>{E(ook["latk"])}</span></div></div>'
             f'<a class="s" href="{E(ook["url"])}" target="_blank" rel="noopener">{ic("link", "np-ic sm")}{E(ook["title"])} (Ookla)</a></article>')
    lab = "updated automatically" if spd.get("live") else f"snapshot pulled {spd['pulled']}"
    cards += (f'<article class="np-card"><span class="d">Cloudflare Radar · {E(lab)}</span><h3>Worldwide speed tests on Starlink\'s network, {E(spd["window"])}</h3>'
              f'<div class="sl-num"><div><b>{spd["down"]}</b><span>Mbps download</span></div><div><b>{spd["up"]}</b><span>Mbps upload</span></div><div><b>{spd["lat_idle"]} ms</b><span>idle latency ({spd["lat_loaded"]} ms under load)</span></div><div><b>{spd["loss"]}%</b><span>packet loss</span></div></div>'
              f'<p>Median of {_fmt(spd.get("tests"))} tests at speed.cloudflare.com, worldwide. Different method and users from Ookla\'s US figure, so the numbers differ.</p>'
              f'<a class="s" href="https://radar.cloudflare.com/quality/as14593" target="_blank" rel="noopener">{ic("link", "np-ic sm")}Cloudflare Radar (CC BY-NC 4.0)</a></article>')
    sec_sp = (f'<section class="np-sec"><h2>{ic("speed")}Speeds</h2><p class="np-sub">Typical speeds from published measurements, each with its source and date. We don\'t know the speed at your address; these are medians.</p><div class="sl-spd">{cards}</div>{radar_html}</section>')
    sec_wx = (f'<section class="np-sec" id="weather"><h2>{ic("storm")}Weather and Starlink</h2><p class="np-sub">Starlink says its dish handles snow, sleet, heavy rain and strong wind, but heavy rain or wind can still cause slower speeds or a rare outage, '
              f'and snow piling up around the dish can block its view (<a href="{WX_HELP}" target="_blank" rel="noopener">Starlink Help Center</a>). Storms also cut power, and the dish and router need power.</p>'
              f'<form class="nm-form" action="/network/near" method="get" role="search"><label class="np-mu" for="sl_q" style="flex-basis:100%">See weather alerts and network status for a place</label>'
              f'<input id="sl_q" name="where" placeholder="ZIP code or city, e.g. 32771 or Mumbai" maxlength="120"><button class="np-btn p" type="submit">{ic("search", "np-ic sm")}Check this place</button></form></section>')
    steps = ["Open the Starlink app: it reports known outages, obstructions and the dish's status.", "Check the sky view: the app's obstruction check shows trees or buildings in the way.",
             "Restart the dish and router by unplugging power for about a minute.", "Look at the weather where the dish is; heavy rain, snow or strong wind can slow it.",
             "Compare with the outage signals above. If they show a drop, the problem is probably not only yours."]
    sec_ck = (f'<section class="np-sec" id="checklist"><h2>{ic("check")}If Starlink seems down</h2><ol class="np-steps">' + "".join(f'<li>{E(s)}</li>' for s in steps) + '</ol></section>')
    links = [("Starlink support", "https://www.starlink.com/support", "Help articles and outage guidance"), ("Starlink availability map", STARLINK_MAP, "Availability by address"),
             ("@Starlink on X", "https://x.com/Starlink", "Official account"), ("IODA: Starlink AS14593", f"{IODA_WEB}/asn/{ASN}", "Independent outage signals"),
             ("CelesTrak Starlink table", "https://celestrak.org/NORAD/elements/supplemental/table.php?FILE=starlink&SHOW-OPS", "Orbital data and status")]
    sec_ln = (f'<section class="np-sec"><h2>{ic("link")}Official links and sources</h2><ul class="np-links">' + "".join(f'<li>{ic("link")}<div>{np.ext(u, a)}<small>{E(n)}</small></div></li>' for a, u, n in links) + '</ul>'
              '<p class="np-mu" style="margin-top:10px">Satellite data: CelesTrak (celestrak.org), from US Space Force tracking; refreshed at most every 6 hours (catalog every 12). '
              'Network measurements: IODA, Internet Intelligence Lab, Georgia Tech. Speeds: Ookla (published report) and Cloudflare Radar (CC BY-NC 4.0). Not affiliated with SpaceX or Starlink.</p>'
              + ioda_html + radar_html + '</section>')
    others = " · ".join(f'<a href="/network/{s}">{E(np.P[s]["name"])}</a>' for s in np.ORDER)
    nl = ('<div class="np-nl"><div><b>Know about the next big outage first</b><div class="np-mu">The free BLACKOUT.NETWORK newsletter: major outages, threats and what to do. Follow us on YouTube and X too.</div></div>'
          '<a class="np-btn p" href="/newsletter?utm_source=site&amp;utm_medium=network_page&amp;utm_campaign=starlink">Get the free newsletter</a></div>')
    body = (f'<div class="np"><p class="np-crumb"><a href="/">BLACKOUT.NETWORK</a> › <a href="/#net">Network Status</a> › <a href="/network">Providers</a> › Starlink</p>'
            + hero + sec_glb + f'<div class="np-grid2 np-gap">{sec_st}{sec_h}</div>' + sec_sp + sec_wx + nl + sec_ck + sec_ln
            + f'<p class="np-mu">Other providers: {others} · <a href="/network/near">Networks near me</a>. Research only; not affiliated with SpaceX. Names identify services only.</p></div>'
            f'<style>{np.CSS}{SL_CSS}</style>{GLOBE_JS}')
    title = "Is Starlink down? Live status, satellites in orbit and speeds"
    desc = "Starlink network status from independent measurements, a live map of Starlink satellites, operational counts, launches, published speeds and how weather affects Starlink."
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "url": f"{SITE}/network/starlink", "dateModified": iso(t),
           "isPartOf": {"@type": "WebSite", "name": "BLACKOUT.NETWORK", "url": SITE}, "about": {"@type": "Organization", "name": "Starlink (SpaceX)", "url": "https://www.starlink.com"}},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "BLACKOUT.NETWORK", "item": SITE + "/"}, {"@type": "ListItem", "position": 2, "name": "Network providers", "item": SITE + "/network"},
              {"@type": "ListItem", "position": 3, "name": "Starlink", "item": f"{SITE}/network/starlink"}]}]
    return np.site_page.page(title, desc, body, "/network/starlink", active="net", jsonld=ld, og_type="website")

# ---------------------------------------------------------------- Networks near me
US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
             "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
             "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
             "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
             "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
             "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico"}
US_ISPS = [("AT&T", 7018), ("Verizon", 701), ("Comcast Xfinity", 7922), ("Charter Spectrum", 20115), ("T-Mobile", 21928), ("Cox", 22773)]
FCC_NOTE = ("Which home internet providers serve an exact address is in the FCC National Broadband Map. Its data API needs an FCC account and key, "
            "which we have not set up, so we list large national networks here instead. Check your address on the FCC map.")
def zip_lookup(z):
    def f():
        with open(os.path.join(BASE, "newsletter_zip.json"), encoding="utf-8") as fh: t = fh.read()
        m = re.search(r'"' + z + r'":\s*(\[[^\]]*\])', t)
        return json.loads(m.group(1)) if m else False
    try: v = cached(("zip", z), 86400, f)
    except Exception: return None
    if not v: return None
    sa = v[3] if len(v) > 3 else ""; town = (v[2] or "").split(",")[0]
    return dict(label=(f"{v[2]} {z}" if not (v[2] or "").startswith("ZIP") else f"ZIP {z}, {US_STATES.get(sa, sa)}"), lat=v[0], lon=v[1], cc="US",
                admin1=US_STATES.get(sa, sa), name=town, kind="zip")
def census(q):
    def f():
        u = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode({"address": q, "benchmark": "Public_AR_Current", "format": "json"})
        m = (jget(u, timeout=15).get("result") or {}).get("addressMatches") or []
        if not m: return False
        c = m[0]["coordinates"]; a = m[0].get("addressComponents") or {}
        return dict(lat=round(c["y"], 2), lon=round(c["x"], 2), city=(a.get("city") or "").title(), state=a.get("state") or "", zip=a.get("zip") or "")
    r = cached(("census", q.lower()), 3600, f)
    if not r: return None
    return dict(label=f'{r["city"]}, {r["state"]} {r["zip"]}'.strip(", "), lat=r["lat"], lon=r["lon"], cc="US", admin1=US_STATES.get(r["state"], r["state"]), name=r["city"], kind="address")
def resolve(qs):
    g = lambda k: ((qs.get(k) or [""])[0] or "").strip()
    try:
        lat, lon = float(g("lat")), float(g("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            cc = re.sub(r"[^A-Za-z]", "", g("cc"))[:2].upper(); nm = re.sub(r"[^\w .,'-]", "", g("name"), flags=re.U)[:60]; a1 = re.sub(r"[^\w .'-]", "", g("admin1"), flags=re.U)[:60]
            return dict(label=", ".join(x for x in (nm, a1, cc) if x) or f"{lat:.2f}, {lon:.2f}", lat=round(lat, 2), lon=round(lon, 2), cc=cc, admin1=a1, name=nm, kind="pick"), []
    except Exception: pass
    q = re.sub(r"\s+", " ", g("q") or g("where") or g("zip"))[:120]
    if len(q) < 2: return None, []
    m = re.fullmatch(r"(\d{5})(?:-\d{4})?", q)
    if m: return zip_lookup(m.group(1)), []
    if re.match(r"^\d+ \S+", q) and ("," in q or re.search(r"\b\d{5}\b", q)):
        try:
            r = census(q)
            if r: return r, []
        except Exception: pass
    import weather
    code, d = weather.geocode(re.sub(r",?\s*\d{5}(-\d{4})?$", "", q))
    res = d.get("results") or []
    if not res: return None, []
    pick = lambda r: dict(label=", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x), lat=round(r["lat"], 2), lon=round(r["lon"], 2), cc=(r.get("cc") or "").upper(),
                          admin1=r.get("admin1") or "", admin2=r.get("admin2") or "", name=r.get("name") or "", country=r.get("country") or "", kind="place")
    return pick(res[0]), [pick(r) for r in res[1:5]]

IMPACT = [
 (r"hurricane|tropical storm|typhoon|cyclone", "A {ev} is in effect here. These storms often cut power and damage cell sites and cables, which takes down home internet and mobile data. Satellite internet like Starlink also needs power for its dish and router, and heavy rain and wind can slow it."),
 (r"tornado|thunderstorm", "A {ev} is in effect here. Heavy rain and storms can slow satellite internet like Starlink or briefly cut it, and storm power cuts take down home internet and Wi-Fi."),
 (r"flood", "A {ev} is in effect here. Flooding can cut power and damage street-level network equipment, which can take down home internet in the flooded area."),
 (r"winter storm|blizzard|ice storm|snow|freez|sleet", "A {ev} is in effect here. Snow and ice can bring down power lines. Starlink melts snow that falls on its dish, but snow piling up around it can block its view of the sky."),
 (r"wind|gale", "A {ev} is in effect here. Strong wind can bring down lines and cause power cuts, and Starlink says strong wind can slow it or cause a rare outage."),
 (r"heat", "A {ev} is in effect here. Extreme heat raises power demand, and power cuts take down home internet and Wi-Fi."),
 (r"fire|red flag", "A {ev} is in effect here. Wildfires can burn through power lines, fiber and cell sites in their path."),
]
def impact(alerts, gd, cur, nets):
    out, seen = [], set()
    for a in alerts:
        ev = a.get("event") or ""
        for rx, txt in IMPACT:
            if re.search(rx, ev, re.I):
                if rx not in seen: seen.add(rx); out.append(txt.format(ev=ev))
                break
    for e in (gd or [])[:2]:
        out.append(f'GDACS lists a {(e.get("type") or "disaster").lower()} ({e.get("level") or "unrated"} alert) about {e.get("dist_km")} km from here' + (f': {e["name"]}.' if e.get("name") else "."))
    wc = (cur or {}).get("weather_code"); pr = (cur or {}).get("precipitation") or 0; gu = (cur or {}).get("wind_gusts_10m") or 0
    if wc in (95, 96, 99) and r"tornado|thunderstorm" not in seen: out.append("Thunderstorms are reported here right now. Heavy rain can slow satellite internet like Starlink, and lightning can cause power cuts.")
    elif pr >= 4: out.append(f"Heavy rain right now ({pr} mm in the last hour). Heavy rain can slow satellite internet like Starlink.")
    if gu >= 75 and r"wind|gale" not in seen: out.append(f"Wind gusts of {round(gu)} km/h right now. Strong wind can bring down lines and cause power cuts.")
    bad = [n["name"] for n in nets if (n.get("level") or 0) >= 2]
    if out and bad: out.append("At the same time, our checks show a problem on " + ", ".join(bad[:4]) + ". We can't confirm the weather is the cause.")
    elif bad: out.append("Our checks show a problem on " + ", ".join(bad[:4]) + ". No weather alert here points to the weather as the cause.")
    return out

def _wx(loc):
    import weather
    w = weather.report(loc["lat"], loc["lon"], loc.get("cc"), [loc.get("name"), loc.get("admin1"), loc.get("admin2")])
    s = w.get("sources") or {}; alerts = []; srcs = []
    na = s.get("nws_alerts")
    if na is not None:
        srcs.append(("National Weather Service", "https://www.weather.gov", na.get("ok")))
        for a in (na.get("data") or []) if na.get("ok") else []:
            alerts.append(dict(event=a.get("event"), severity=a.get("severity"), headline=a.get("headline"), area=(a.get("area") or "")[:160], onset=a.get("onset"), expires=a.get("expires"), url=a.get("link"), src="National Weather Service"))
    ma = s.get("meteoalarm")
    if ma is not None:
        srcs.append(("MeteoAlarm", "https://meteoalarm.org", ma.get("ok")))
        for a in ((ma.get("data") or {}).get("alerts") or []) if ma.get("ok") else []:
            alerts.append(dict(event=a.get("event"), severity=a.get("severity"), headline=a.get("headline"), area=(a.get("area") or "")[:160], onset=a.get("onset"), expires=a.get("expires"), url=a.get("url"), src=a.get("sender") or "MeteoAlarm"))
    gs = s.get("gdacs") or {}; gd = gs.get("data") if gs.get("ok") else []
    srcs.append(("GDACS (UN / EU)", "https://www.gdacs.org", gs.get("ok")))
    om = s.get("open_meteo") or {}; cur = ((om.get("data") or {}).get("current") or {}) if om.get("ok") else {}
    srcs.append(("Open-Meteo", "https://open-meteo.com", om.get("ok")))
    return dict(alerts=alerts[:8], gdacs=[dict(type=e.get("type"), name=e.get("name"), level=e.get("level"), dist_km=e.get("dist_km"), url=e.get("url")) for e in (gd or [])[:4]],
                current={k: cur.get(k) for k in ("time", "temperature_2m", "precipitation", "weather_code", "wind_speed_10m", "wind_gusts_10m")} if cur else None,
                note=w.get("alerts_note"), sources=[dict(name=a, url=b, ok=bool(c)) for a, b, c in srcs], generated=w.get("generated"))

def near(qs, np):
    loc, alts = resolve(qs)
    if not loc: return 404, {"error": "We couldn't find that place. Try a 5-digit US ZIP code or a city name."}
    key = ("near", round(loc["lat"], 1), round(loc["lon"], 1), loc.get("cc"), _norm(loc.get("admin1")))
    if not _S["sem"].acquire(timeout=8): return 503, {"error": "Busy right now, please try again in a few seconds."}
    try: res = cached(key, 600, lambda: _near_build(loc, np), maxn=200)
    finally: _S["sem"].release()
    out = dict(res); out["location"] = {k: loc.get(k) for k in ("label", "lat", "lon", "cc", "admin1", "kind")}; out["alternatives"] = alts
    out["ga"] = {"search_type": loc["kind"], "region": (loc.get("admin1") or "")[:40], "country": loc.get("cc") or ""}   # coarse only: never the query or coordinates
    return 200, out
def _near_build(loc, np):
    cc = loc.get("cc") or ""; a1 = loc.get("admin1") or ""; nets = []
    rc = ioda_region_code(cc, a1)
    def res(f):
        try: return f.result(timeout=30), None
        except Exception as e: return None, _errname(e)
    def hl(al): return health(al) if al is not None else (-1, "IODA could not be reached right now", [])
    with ThreadPoolExecutor(6) as ex:
        f_sl = ex.submit(starlink_status); f_wx = ex.submit(_wx, loc)
        f_rg = ex.submit(ioda_alerts, "region", rc[0], 24) if rc else None
        f_cc = ex.submit(ioda_alerts, "country", cc, 24) if cc else None
        f_isp = [(n, a, ex.submit(ioda_alerts, "asn", a, 24)) for n, a in US_ISPS] if cc == "US" else []
        f_cl = [(s, ex.submit(np.brief, s)) for s in np.ORDER]
        sl, _ = res(f_sl); av = starlink_avail(cc)
        nets.append(dict(id="starlink", group="satellite", name="Starlink (satellite internet)", level=sl["level"] if sl else -1, status=sl["text"] if sl else "Measurements unavailable",
                         avail=av, why="Network-wide signal for Starlink's AS14593 (IODA). Starlink has no public status feed.", page="/network/starlink"))
        if f_rg:
            al, _ = res(f_rg); lv, txt, _ = hl(al)
            nets.append(dict(id="region", group="local", name=f"All internet in {rc[1]}", level=lv, status=txt, why="Every provider in this state or region together, measured by IODA (Georgia Tech).", url=f"{IODA_WEB}/region/{rc[0]}"))
        if f_cc:
            al, _ = res(f_cc); lv, txt, _ = hl(al)
            nets.append(dict(id="country", group="local", name="All internet in the United States" if cc == "US" else f"All internet in {loc.get('country') or cc}", level=lv, status=txt,
                             why="Country-wide measurement (IODA). Small local outages don't show up at this level.", url=f"{IODA_WEB}/country/{cc}"))
        for n, a, f in f_isp:
            al, _ = res(f); lv, txt, _ = hl(al)
            nets.append(dict(id=f"as{a}", group="isp", name=n, level=lv, status=txt, why=f"National network AS{a} (IODA). A local outage may not show at this level.", url=f"{IODA_WEB}/asn/{a}"))
        for s, f in f_cl:
            b, _ = res(f)
            nets.append(dict(id=s, group="cloud", name=np.P[s]["name"], level=b["level"] if b else -1, status=b["status"] if b else "Feed unreachable", page=f"/network/{s}",
                             why="Runs apps and websites used everywhere, so it applies wherever you are."))
        wx, _ = res(f_wx)
    wx = wx or dict(alerts=[], gdacs=[], current=None, note="Weather data is unavailable right now.", sources=[], generated=None)
    imp = impact(wx["alerts"], wx["gdacs"], wx["current"], nets)
    return dict(generated=iso(now()), networks=nets, weather=wx, impact=imp, fcc=dict(note=FCC_NOTE, url="https://broadbandmap.fcc.gov/home") if cc == "US" else None,
                outside_us=None if cc == "US" else ("Outside the US we can't list which home internet providers serve a place. We show the country and region measured "
                                                    "by IODA where it has data, Starlink's country status, and the global services everyone uses."))

NEAR_JS = r"""<script>(function(){
var f=document.getElementById("nm_form"),q=document.getElementById("nm_q"),out=document.getElementById("nm_out"),C={0:"#2BB673",1:"#F5A524",2:"#FF7A1A",3:"#FF4D4F","-1":"#5b6573"},L={0:"Operational",1:"Minor issue",2:"Degraded",3:"Major outage","-1":"No data"};
var PIN='<svg class="np-ic icon-pin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>';
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function url(u){u=String(u||"");return /^(https?:\/\/|\/)/.test(u)?u:"#"}
function chip(l){return'<span class="np-lv" style="--c:'+(C[l]||C[-1])+'"><i></i>'+esc(L[l]||"")+'</span>'}
function t(s){if(!s)return"";var d=new Date(s);return isNaN(d)?esc(s):esc(d.toLocaleString([],{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZone:"America/New_York",timeZoneName:"short"}))}
function net(n){var link=n.page?' <a href="'+esc(url(n.page))+'">Details</a>':(n.url?' <a href="'+esc(url(n.url))+'" target="_blank" rel="noopener">Source</a>':"");
 var av=n.avail?'<p><b>'+(n.avail.level==="yes"?"Available here":n.avail.level==="no"?"Not offered here":"Availability")+':</b> '+esc(n.avail.text)+' <a href="'+esc(url(n.avail.url))+'" target="_blank" rel="noopener">'+(n.avail.src?"Source":"Starlink map")+'</a></p>':"";
 return'<div class="nm-net" style="--c:'+(C[n.level]||C[-1])+'"><h3><span>'+esc(n.name)+'</span>'+chip(n.level)+'</h3><p>'+esc(n.status)+'</p>'+av+'<small>'+esc(n.why)+link+'</small></div>'}
function render(d){var loc=d.location,w=d.weather,h="";
 h+='<section class="nm-imp page-header-band" aria-live="polite"><h2>'+PIN+esc(loc.label)+'</h2>';
 h+=d.impact.length?'<ul>'+d.impact.map(function(x){return"<li>"+esc(x)+"</li>"}).join("")+'</ul>':'<p style="margin:0">No active weather alerts here and no network problems in our checks right now.</p>';
 h+='<p class="np-mu" style="margin:8px 0 0">Checked '+t(d.generated)+'. We use the center of the ZIP code or town, never an exact address.</p>';
 if(d.alternatives&&d.alternatives.length)h+='<div class="nm-alts" style="margin-top:10px"><span class="np-mu">Not the right place?</span>'+d.alternatives.map(function(a,i){return'<button type="button" data-alt="'+i+'">'+esc(a.label)+'</button>'}).join("")+'</div>';
 h+='</section>';
 var g={satellite:[],local:[],isp:[],cloud:[]};d.networks.forEach(function(n){(g[n.group]=g[n.group]||[]).push(n)});
 h+='<div class="nm-grid"><section class="np-sec"><h2>Networks here</h2><p class="np-sub">Each with its status right now. National networks are listed where they operate, but may not reach every address.</p>';
 h+='<div class="nm-sub">Satellite</div>'+g.satellite.map(net).join("");
 if(g.local.length)h+='<div class="nm-sub">Local internet, all providers</div>'+g.local.map(net).join("");
 if(g.isp.length)h+='<div class="nm-sub">Large US networks</div>'+g.isp.map(net).join("");
 if(d.fcc)h+='<p class="np-note">'+esc(d.fcc.note)+' <a href="'+esc(url(d.fcc.url))+'" target="_blank" rel="noopener">FCC National Broadband Map</a></p>';
 if(d.outside_us)h+='<p class="np-note">'+esc(d.outside_us)+'</p>';
 if(d.attribution_html)h+=d.attribution_html;
 h+='<div class="nm-sub">Services everyone uses</div>'+g.cloud.map(net).join("")+'</section>';
 h+='<section class="np-sec"><h2>Weather here</h2><p class="np-sub">Official alerts for this point, plus major disasters nearby.</p>';
 h+=w.alerts.length?w.alerts.map(function(a){var c=/extreme|severe/i.test(a.severity||"")?C[3]:/moderate/i.test(a.severity||"")?C[2]:C[1];return'<div class="nm-wx" style="--c:'+c+'"><b>'+esc(a.event)+'</b> <span class="np-mu">· '+esc(a.severity||"")+' · '+esc(a.src)+'</span><p>'+esc(a.headline||a.area)+'</p><p class="np-mu">Until '+t(a.expires)+(a.url?' · <a href="'+esc(url(a.url))+'" target="_blank" rel="noopener">Official alert</a>':"")+'</p></div>'}).join("")
  :'<div class="nm-wx" style="--c:'+C[0]+'"><b>No active weather alerts</b><p>'+esc(w.note||"From the official alert feeds listed below.")+'</p></div>';
 if(w.gdacs.length)h+=w.gdacs.map(function(e){return'<div class="nm-wx" style="--c:'+(e.level==="Red"?C[3]:e.level==="Orange"?C[2]:C[1])+'"><b>'+esc(e.type)+': '+esc(e.name)+'</b><p>'+esc(e.level)+' alert, about '+esc(e.dist_km)+' km away'+(e.url?' · <a href="'+esc(url(e.url))+'" target="_blank" rel="noopener">GDACS report</a>':"")+'</p></div>'}).join("");
 if(w.current){var c=w.current;h+='<p class="np-mu">Right now: '+(c.temperature_2m!=null?esc(Math.round(c.temperature_2m))+' °C, ':"")+'rain '+esc(c.precipitation)+' mm/h, gusts '+esc(Math.round(c.wind_gusts_10m||0))+' km/h (Open-Meteo).</p>'}
 h+='<p class="np-mu">Sources: '+w.sources.map(function(s){return'<a href="'+esc(url(s.url))+'" target="_blank" rel="noopener">'+esc(s.name)+'</a>'+(s.ok?"":" (unavailable)")}).join(" · ")+'. <a href="/#weather">Full forecast</a>.</p></section></div>';
 out.innerHTML=h;out.querySelectorAll("[data-alt]").forEach(function(b){b.onclick=function(){var a=d.alternatives[+b.dataset.alt];go("lat="+a.lat+"&lon="+a.lon+"&cc="+encodeURIComponent(a.cc||"")+"&name="+encodeURIComponent(a.name||"")+"&admin1="+encodeURIComponent(a.admin1||""),a.label)}})}
function go(qstr,label){out.innerHTML='<p class="np-mu">Checking networks and weather'+(label?' for '+esc(label):'')+'…</p>';
 fetch("/api/network/near?"+qstr).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.error||"error");return j})}).then(function(d){render(d);
  try{if(window.gtag)gtag("event","network_search",{search_type:d.ga.search_type,region:d.ga.region,country:d.ga.country})}catch(e){}})
 .catch(function(e){out.innerHTML='<p class="np-note">'+esc(e.message||"Could not check right now.")+'</p>'})}
f.addEventListener("submit",function(e){e.preventDefault();var v=q.value.trim();if(v.length<2)return;try{history.replaceState(null,"","/network/near?where="+encodeURIComponent(v))}catch(_){}go("q="+encodeURIComponent(v))});
var qs=new URLSearchParams(location.search),p=qs.get("where")||qs.get("zip")||qs.get("q");if(p){q.value=p;go("q="+encodeURIComponent(p))}
})();</script>"""

def render_near(np):
    ic = lambda n, c="np-ic": _ic(np, n, c)
    body = (f'<div class="np"><p class="np-crumb"><a href="/">BLACKOUT.NETWORK</a> › <a href="/#net">Network Status</a> › <a href="/network">Providers</a> › Networks near me</p>'
            f'<section class="np-hero page-header-band"><div class="np-hrow">{np.TILE}<div style="min-width:0"><div class="np-kick"><i></i>BLACKOUT.NETWORK · NETWORK STATUS</div>'
            '<h1>Networks near me, <em>with the weather</em></h1><p>Type a ZIP code, city or address. We show the networks that serve that place and their status right now, '
            'active weather alerts there, and a plain note on how that weather can affect your connection.</p></div></div>'
            f'<form class="nm-form" id="nm_form" role="search"><label for="nm_q" class="np-mu" style="flex-basis:100%">ZIP code, city or address</label>'
            f'<input id="nm_q" name="where" placeholder="e.g. 32771, Denver or Mumbai" maxlength="120" required>'
            f'<button class="np-btn p" type="submit">{ic("search", "np-ic sm")}Check</button></form></section>'
            '<div id="nm_out"><p class="np-mu">Nothing about your search is stored. We look up the center of the ZIP code or town and keep the result in memory for 10 minutes so repeat checks are fast.</p></div>'
            '<p class="np-mu" style="margin-top:14px">Sources: IODA (Georgia Tech) internet measurements, official provider status feeds, National Weather Service, MeteoAlarm, Open-Meteo, GDACS. '
            'Places: US Census ZIP centroids, Open-Meteo geocoding (GeoNames), US Census geocoder. Research only.</p>'
            + ioda_credit_html(np, np.fmt_et(now())) + '</div>'
            f'<style>{np.CSS}{SL_CSS}</style>{NEAR_JS}')
    desc = "Type a ZIP code or city to see the internet networks that serve it, their status right now, and active weather alerts that can affect them, including Starlink."
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": "Networks near me: internet status and weather", "url": f"{SITE}/network/near", "description": desc}
    return np.site_page.page("Is the internet down near me? Network status and weather by ZIP code", desc, body, "/network/near", active="net", jsonld=ld, og_type="website")

def handle_get(path, qs, np, headers=None):
    """Returns a response tuple, or None when the path is not ours.
    /api/network/starlink/brief and /api/network/near include IODA measurements only for same-origin requests from our pages."""
    p = path.rstrip("/")
    if p == "/network/starlink": return 200, render(np), "text/html"
    if p == "/network/near": return 200, render_near(np), "text/html"
    if p == "/api/network/starlink/brief": return 200, brief_out(np, headers)
    if p == "/api/network/starlink/gp":
        try: n = int((qs.get("n") or ["1500"])[0])
        except Exception: n = 1500
        return gp_payload(n)
    if p == "/api/network/starlink":
        sc = satcat(); g = gp(); spd = radar_speed()
        body = {"satcat": {k: v for k, v in sc.items() if k not in ("nonplus", "mt")},
                "orbits": {k: v for k, v in g.items() if k not in ("payloads", "mt", "sck")},
                "speeds": {"published": SPEEDS, "cloudflare_radar": spd},
                "attribution": radar_credit_text(spd), "license": "CC BY-NC 4.0",
                "license_url": "https://creativecommons.org/licenses/by-nc/4.0/"}
        if same_origin(headers):
            s = starlink_status()
            body["health"] = {k: s[k] for k in ("level", "text", "error", "fetched")}
            body["ioda_attribution"] = ioda_credit_text(np.fmt_et(now()))
            body["ioda_license"] = "All Rights Reserved"
            if _S.get("ioda_copyright"): body["copyright"] = _S["ioda_copyright"]
        return 200, body
    if p == "/api/network/near":
        code, body = near(qs, np)
        if code == 200: body = near_out(body, np, headers)
        return code, body
    return None
