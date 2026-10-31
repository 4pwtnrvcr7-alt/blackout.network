"""Radio add-on (tab "📻 Radio", deep link #radio): number stations, military HF and live radio, playable on the page.
 - Direct HTTPS audio streams play in the browser straight from the source (HTML5 <audio>, hls.js for HLS); live/offline is
   checked server-side every 5 min (small ranged GET, 8 s timeout).
 - Two shortwave channels are relayed from a public KiwiSDR by radio_archive.py (box only) as short HLS windows.
 - Priyom.org's public schedule calendar gives the next number-station transmissions.
 - Archive: rolling 15-min MP3 segments written by radio_archive.py; browse/play/download here (Range requests supported).
Read-only research monitoring. Never touches scanner.py, scoring, push.py, jets.py, config.json or blackout.db."""
import builtins, json, os, re, subprocess, threading, time, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone, timedelta
import radio_common as RC
import importlib as _il; _il.reload(RC)   # pick up radio_common edits on add-on hot-reload

STATIC = os.path.join(RC.BASE, "radio_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css", "hls.min.js": "application/javascript"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) blackout.network radio monitor"}
CHECK_S = 300
EVENTS = os.path.join(RC.BASE, "logs", "priyom_events.json")
S = getattr(builtins, "_bn_radio", None)
if S is None: S = builtins._bn_radio = {"status": {}, "checked": None, "lock": threading.Lock(), "started": False, "events": [], "events_at": 0}

def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

# Reference: well-known stations (facts as published on Priyom.org station pages).
STATIONS = [
    {"code": "S28", "name": "UVB-76 “The Buzzer”", "freq": "4625 kHz USB", "loc": "Controlled from St Petersburg (60th Communication Hub); transmitters near St Petersburg and Moscow", "url": "https://priyom.org/military-stations/russia/the-buzzer", "tune": (4625, "usb")},
    {"code": "S30", "name": "“The Pip”", "freq": "5448 kHz day / 3756 kHz night USB", "loc": "Rostov-on-Don, Russia (72nd Communication Hub)", "url": "https://priyom.org/military-stations/russia/the-pip", "tune": (5448, "usb")},
    {"code": "S32", "name": "“The Squeaky Wheel”", "freq": "5367 kHz day / 3363.5 kHz night USB", "loc": "Rostov-on-Don, Russia (not confirmed)", "url": "https://priyom.org/military-stations/russia/the-squeaky-wheel", "tune": (5367, "usb")},
    {"code": "E11", "name": "“Oblique”", "freq": "varies (see schedule) USB", "loc": "Warsaw, Poland", "url": "https://priyom.org/number-stations/english/e11", "tune": None},
    {"code": "S06", "name": "“Russian Man”", "freq": "varies USB + carrier", "loc": "Moscow, Orenburg and Chita, Russia", "url": "https://priyom.org/number-stations/slavic/s06", "tune": None},
    {"code": "M12", "name": "Russian Morse numbers", "freq": "varies CW", "loc": "Moscow and Khabarovsk, Russia", "url": "https://priyom.org/number-stations/morse/m12", "tune": None},
    {"code": "V07", "name": "“Spanish Lady”", "freq": "varies USB", "loc": "Khabarovsk, Russia (Spanish mode of the Russian 7 operator)", "url": "https://priyom.org/number-stations/other/v07", "tune": None},
    {"code": "V13", "name": "“New Star Broadcasting Station”", "freq": "varies USB + carrier", "loc": "Taiwan (Mandarin numbers)", "url": "https://priyom.org/number-stations/other/v13", "tune": None},
    {"code": "HM01", "name": "Cuban hybrid numbers", "freq": "9065–17480 kHz AM + OFDM", "loc": "Bejucal, Cuba (Priyom status: hibernated)", "url": "https://priyom.org/number-stations/digital/hm01", "tune": None},
    {"code": "XPA2", "name": "Russian digital (MFSK)", "freq": "varies USB", "loc": "Moscow, Russia", "url": "https://priyom.org/number-stations/digital/xpa2", "tune": None},
]
LINKS = [
    {"group": "Shortwave receivers (open the receiver tuned for you)", "items": [
        {"name": "UVB-76 4625 kHz on the Twente WebSDR (Netherlands)", "url": RC.twente(4625, "usb")},
        {"name": "HFGCS 8992 kHz on Twente WebSDR", "url": RC.twente(8992, "usb")},
        {"name": "HFGCS 11175 kHz on Twente WebSDR", "url": RC.twente(11175, "usb")},
        {"name": "The Pip 5448 kHz on Twente WebSDR", "url": RC.twente(5448, "usb")},
        {"name": "WWV / WWVH time signal 10 MHz (AM)", "url": RC.twente(10000, "am")},
        {"name": "WWV 15 MHz (AM)", "url": RC.twente(15000, "am")},
        {"name": "Public KiwiSDR receivers worldwide (map)", "url": "http://rx.linkfanel.net/"},
        {"name": "Priyom number-station schedule", "url": "https://priyom.org/number-stations/station-schedule"}]},
    {"group": "Scanner feeds (Broadcastify player; short ad first) · pick a location above for local feeds", "items": [
        {"name": "Top live scanner feeds right now", "url": "https://www.broadcastify.com/listen/top"},
        {"name": "Browse all feeds by country / state / county", "url": "https://www.broadcastify.com/listen/"}]},
    {"group": "Air traffic control (LiveATC player) · pick a location above for the nearest airports", "items": [
        {"name": "LiveATC: top feeds and airport search", "url": "https://www.liveatc.net/"},
        {"name": "LiveATC HF / oceanic feeds", "url": "https://www.liveatc.net/hf/"}]},
]

# ---------------- direct stream checks ----------------
def _get(url, n=16384, t=8):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={**UA, "Range": f"bytes=0-{n - 1}"} if not url.endswith(".m3u8") else UA), timeout=t)
    ct = r.headers.get("Content-Type", ""); b = b""
    while len(b) < n:
        c = r.read(n - len(b))
        if not c: break
        b += c
    r.close(); return ct, b

def _abs(base, ref): return ref if ref.startswith("http") else base.rsplit("/", 1)[0] + "/" + ref

def check_one(s):
    t0 = time.time()
    try:
        if s["kind"] == "hls":
            _, pl = _get(s["url"], 65536)
            lines = [l.strip() for l in pl.decode("utf-8", "ignore").splitlines() if l.strip() and not l.startswith("#")]
            url = s["url"]
            if lines and lines[0].split("?")[0].endswith(".m3u8"):
                url = _abs(url, lines[0]); _, pl = _get(url, 65536)
                lines = [l.strip() for l in pl.decode("utf-8", "ignore").splitlines() if l.strip() and not l.startswith("#")]
            if not lines: return {"ok": False, "err": "empty playlist"}
            _, b = _get(_abs(url, lines[-1]), 8192)
        else:
            ct, b = _get(s["url"])
            if "html" in ct.lower(): return {"ok": False, "err": "returned a web page, not audio"}
        ok = len(b) >= 4096
        return {"ok": ok, "bytes": len(b), "ms": int((time.time() - t0) * 1000), **({} if ok else {"err": "too few bytes"})}
    except Exception as ex: return {"ok": False, "err": f"{type(ex).__name__}: {str(ex)[:100]}", "ms": int((time.time() - t0) * 1000)}

def check_all():
    with cf.ThreadPoolExecutor(4) as ex: res = dict(zip([s["id"] for s in RC.DIRECT], ex.map(check_one, RC.DIRECT)))
    now = iso()
    with S["lock"]:
        for k, v in res.items(): S["status"][k] = {**v, "checked": now}
        S["checked"] = now
        try:
            tmp = os.path.join(RC.BASE, "logs", "radio_check.json.tmp"); json.dump({"checked": now, "status": S["status"]}, open(tmp, "w"))
            os.replace(tmp, os.path.join(RC.BASE, "logs", "radio_check.json"))
        except Exception: pass

def _loop():
    while True:
        try: check_all()
        except Exception as ex: print("radio check:", ex, flush=True)
        time.sleep(CHECK_S)

# ---------------- worker ----------------
def _worker_alive():
    try:
        pid = int(open(RC.PIDF).read().strip()); return "radio_archive" in open(f"/proc/{pid}/cmdline").read()
    except Exception: return False
def ensure_worker():
    if os.environ.get("BN_WEB_ONLY") or os.environ.get("BN_NO_RADIO_ARCHIVE") or _worker_alive(): return
    os.makedirs(os.path.join(RC.BASE, "logs"), exist_ok=True)
    log = open(os.path.join(RC.BASE, "logs", "radio_archive.log"), "a")
    subprocess.Popen(["python3", os.path.join(RC.BASE, "radio_archive.py")], cwd=RC.BASE, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)

if not S["started"]:
    S["started"] = True; threading.Thread(target=_loop, daemon=True, name="radio-check").start()
ensure_worker()

# ---------------- Priyom schedule ----------------
def events():
    try:
        if time.time() - os.stat(EVENTS).st_mtime < 3600: return json.load(open(EVENTS))
    except Exception: pass
    if time.time() - S["events_at"] < 1800: return S["events"]
    try:
        u = "https://calendar2.priyom.org/events?timeMin=" + iso(datetime.now(timezone.utc) - timedelta(hours=1)) + "&maxResults=250"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=12).read()); ev = []
        for e in d.get("items", []):
            m = re.match(r"^([\w /-]+?) (\d+) ?kHz(?: ([A-Z/]+))?", e.get("summary", ""))
            if m: ev.append({"station": m.group(1), "khz": int(m.group(2)), "mode": m.group(3) or "USB", "start": e["start"]["dateTime"], "summary": e["summary"]})
        S["events"], S["events_at"] = ev, time.time()
    except Exception as ex: print("radio priyom:", ex, flush=True); S["events_at"] = time.time()
    return S["events"]

def schedule():
    now = datetime.now(timezone.utc); out = []
    for e in events():
        st = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        if st < now - timedelta(minutes=10): continue
        m = e["mode"].split("/")[0].lower()
        out.append({**e, "start": iso(st), "tune_url": RC.twente(e["khz"], m if m in ("usb", "lsb", "am", "cw") else "usb") if e["khz"] <= 29160 else None})
    out.sort(key=lambda x: x["start"])
    return out

# ---------------- archive ----------------
SID = re.compile(r"^[a-z0-9_]{2,32}$"); DAY = re.compile(r"^\d{8}$"); FN = re.compile(r"^\d{6}\.mp3$")
NAMES = {**{s["id"]: s["name"] for s in RC.DIRECT}, **{r["id"]: r["name"] for r in RC.RELAYS}, "priyom": "Priyom-scheduled number-station transmissions"}

def archive_index(station=None, day=None):
    out = {"root_exists": os.path.isdir(RC.ARCHIVE), "stations": [], "files": [], "retention": {"days": RC.RETAIN_DAYS, "cap_bytes": RC.RETAIN_BYTES, "segment_s": RC.SEGMENT_S, "kbps": RC.ARCHIVE_KBPS}}
    if not out["root_exists"]: return out
    total = 0
    for sid in sorted(os.listdir(RC.ARCHIVE)):
        p = os.path.join(RC.ARCHIVE, sid)
        if not SID.match(sid) or not os.path.isdir(p): continue
        days = []
        for d in sorted(os.listdir(p), reverse=True):
            dp = os.path.join(p, d)
            if not DAY.match(d) or not os.path.isdir(dp): continue
            fs = [f for f in os.listdir(dp) if FN.match(f)]
            if not fs: continue
            sz = sum(os.path.getsize(os.path.join(dp, f)) for f in fs); total += sz
            days.append({"date": d, "files": len(fs), "bytes": sz})
        out["stations"].append({"id": sid, "name": NAMES.get(sid, sid), "days": days})
    out["total_bytes"] = total
    if station and day and SID.match(station) and DAY.match(day):
        dp = os.path.join(RC.ARCHIVE, station, day); now = time.time()
        if os.path.isdir(dp):
            for f in sorted(os.listdir(dp)):
                if not FN.match(f): continue
                fp = os.path.join(dp, f); st = os.stat(fp)
                if st.st_size < 4096: continue          # segment just opened, nothing playable yet
                start = datetime.strptime(day + f[:6], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                out["files"].append({"name": f, "start": iso(start), "end": iso(datetime.fromtimestamp(st.st_mtime, timezone.utc)), "bytes": st.st_size,
                                     "recording": now - st.st_mtime < 30, "url": f"api/radio/file/{station}/{day}/{f}"})
    return out

def api():
    rs = RC.read_status(); fresh = False
    try: fresh = (datetime.now(timezone.utc) - datetime.fromisoformat(rs["updated"].replace("Z", "+00:00"))).total_seconds() < 60
    except Exception: pass
    with S["lock"]: st = dict(S["status"]); checked = S["checked"]
    direct = [{**{k: v for k, v in s.items()}, "status": st.get(s["id"]), "recording": bool(fresh and (rs.get("streams", {}).get(s["id"]) or {}).get("running"))} for s in RC.DIRECT]
    relays = []
    for r in RC.RELAYS:
        w = (rs.get("streams") or {}).get(r["id"]) or {}
        live_ok = fresh and w.get("running") and os.path.exists(os.path.join(RC.LIVE, r["id"], "index.m3u8")) and \
                  time.time() - os.path.getmtime(os.path.join(RC.LIVE, r["id"], "index.m3u8")) < 30
        relays.append({**r, "tune_url": RC.twente(r["freq_khz"], r["mode"]), "live": bool(live_ok), "hls": f"api/radio/live/{r['id']}/index.m3u8",
                       "tuned": w.get("tuned"), "until": w.get("until"), "receiver": w.get("receiver"), "since": w.get("since"), "next_try": w.get("next_try"),
                       "worker": "running" if fresh else ("web-only node" if os.environ.get("BN_WEB_ONLY") else "not running")})
    sched = schedule(); nxt = {}
    for e in sched:
        nxt.setdefault(e["station"].upper(), e)
    stations = [{**{k: v for k, v in s.items() if k != "tune"}, "next": nxt.get(s["code"]), "tune_url": RC.twente(*s["tune"]) if s["tune"] else None} for s in STATIONS]
    return {"generated": iso(), "checked": checked, "direct": direct, "relays": relays, "schedule": sched[:40], "stations": stations, "links": LINKS,
            "retention": rs.get("retention"), "worker_fresh": fresh, "web_only": bool(os.environ.get("BN_WEB_ONLY"))}

def handle_get(path, qs):
    if path.startswith("/api/radio/") and path[len("/api/radio/"):] in FILES:
        n = path[len("/api/radio/"):]
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/radio": return 200, api()
    if path == "/api/radio/local": return local(qs)
    if path == "/api/radio/archive":
        g = lambda k: ((qs.get(k) or [""])[0] or "").strip()
        return 200, archive_index(g("station") or None, g("date") or None)
    m = re.match(r"^/api/radio/live/([a-z0-9_]+)/(index\.m3u8|s\d{6}\.ts)$", path)
    if m:
        p = os.path.join(RC.LIVE, m.group(1), m.group(2))
        if not os.path.isfile(p): return 404, {"error": "relay not live"}
        with open(p, "rb") as fh: return 200, fh.read(), "application/vnd.apple.mpegurl" if p.endswith(".m3u8") else "video/mp2t"
    return 404, {"error": "not found"}

def handle_stream(path, qs, h):
    """Archive MP3 files with HTTP Range support (so the player can seek); everything else goes through handle_get."""
    m = re.match(r"^/api/radio/file/([a-z0-9_]{2,32})/(\d{8})/(\d{6}\.mp3)$", path)
    if not m: return h.send(*handle_get(path, qs))
    p = os.path.join(RC.ARCHIVE, *m.groups())
    if not os.path.isfile(p): return h.send(404, {"error": "not in archive (deleted by retention?)"})
    size = os.path.getsize(p); start, end = 0, size - 1; code = 200
    rg = re.match(r"bytes=(\d*)-(\d*)", h.headers.get("Range") or "")
    if rg and (rg.group(1) or rg.group(2)):
        if rg.group(1): start = int(rg.group(1)); end = int(rg.group(2)) if rg.group(2) else size - 1
        else: start = max(0, size - int(rg.group(2)))
        end = min(end, size - 1); code = 206
        if start > end: h.send_response(416); h.send_header("Content-Range", f"bytes */{size}"); h.end_headers(); return
    h.send_response(code); h.send_header("Content-Type", "audio/mpeg"); h.send_header("Accept-Ranges", "bytes")
    h.send_header("Content-Length", str(end - start + 1)); h.send_header("Cache-Control", "no-store")
    if code == 206: h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    if (qs.get("dl") or [""])[0] == "1": h.send_header("Content-Disposition", f'attachment; filename="{m.group(1)}_{m.group(2)}_{m.group(3)}"')
    h.end_headers()
    with open(p, "rb") as f:
        f.seek(start); left = end - start + 1
        while left > 0:
            b = f.read(min(65536, left))
            if not b: break
            h.wfile.write(b); left -= len(b)

# ---------------- visitor-chosen location: local channels (no default location; nothing logged or stored) ----------------
import math, urllib.parse
RB = ["https://de2.api.radio-browser.info", "https://de1.api.radio-browser.info"]
LC = getattr(builtins, "_bn_radio_local2", None)
if LC is None: LC = builtins._bn_radio_local2 = {"chk": {}, "rb": {}}

def _verify(url, kind):
    """Verified-playable cache (10 min) for streams offered inline on the location panel."""
    hit = LC["chk"].get(url)
    if hit and time.time() - hit[0] < 600: return hit[1]
    r = check_one({"url": url, "kind": kind}); LC["chk"][url] = (time.time(), r); return r

CURATED = {   # national public broadcasters with known HTTPS streams (verified live before being offered inline)
    "GB": [("BBC World Service", "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service"), ("BBC Radio 4", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_fourfm"),
           ("BBC Radio 5 Live", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_five_live")],
    "US": [("NPR live news", "https://npr-ice.streamguys1.com/live.mp3"), ("VOA Learning English", "https://voa-ingest.akamaized.net/hls/live/2035234/160_342L/playlist.m3u8")],
    "FR": [("franceinfo (Radio France)", "https://icecast.radiofrance.fr/franceinfo-midfi.mp3"), ("RFI English", "https://rfienglish.ice.infomaniak.ch/rfienglish-64.mp3")],
    "DE": [("Deutschlandfunk", "https://st01.sslstream.dlf.de/dlf/01/128/mp3/stream.mp3")],
    "CA": [("CBC Radio One (Toronto)", "https://cbcradiolive.akamaized.net/hls/live/2041057/ES_R1ETR/master.m3u8")],
    "JP": [("NHK World Radio Japan", "https://nhkworld-radio.nhkworld.jp/hls/live/nhkworld-radio-media2/index.m3u8")],
}

def _rb_q(q):
    for host in RB + RB:
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(host + "/json/stations/search?" + urllib.parse.urlencode(q), headers=UA), timeout=10).read())
            if isinstance(r, list): return r
        except Exception: time.sleep(0.3)
    return []

def _rb(cc, stname):
    """Public/news broadcasters for a country (or US state): public-service tags first, then news."""
    key = (cc, stname or "")
    hit = LC["rb"].get(key)
    if hit and time.time() - hit[0] < (3600 if hit[1] else 300): return hit[1]
    rows = []
    for tag in ("public radio", "public service", "news"):
        q = {"countrycode": cc, "tag": tag, "hidebroken": "true", "order": "clickcount", "reverse": "true", "limit": "25"}
        if stname: q["state"] = stname
        rows += _rb_q(q)
        if len(rows) >= 25: break
    out, seen = [], set()
    for s in rows:
        u = (s.get("url_resolved") or s.get("url") or "").strip(); n = (s.get("name") or "").strip()
        if not u or not n or n.lower() in seen or (s.get("codec") or "").upper() not in ("MP3", "AAC", "AAC+", "UNKNOWN", ""): continue
        if u.startswith("http://"): u = "https://" + u[7:]      # the box only reaches HTTPS; the https variant must verify below
        seen.add(n.lower()); out.append({"name": n[:60], "url": u, "kind": "hls" if ".m3u8" in u else "mp3", "homepage": s.get("homepage") or "",
                                         "codec": s.get("codec"), "state": s.get("state") or "", "tags": (s.get("tags") or "")[:80]})
        if len(out) >= 10: break
    LC["rb"][key] = (time.time(), out); return out

def local(qs):
    import visitor_geo as VG
    g = lambda k: ((qs.get(k) or [""])[0] or "").strip()
    cc = re.sub(r"[^A-Z]", "", g("cc").upper())[:2]; st = re.sub(r"[^A-Z]", "", g("st").upper())[:2]
    lat = lon = None
    try: lat, lon = float(g("lat")), float(g("lon"))
    except ValueError: pass
    d = VG.data()
    if lat is not None:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): return 400, {"error": "lat/lon out of range"}
        w = VG.where(lat, lon); cc = cc or w["cc"]; st = st or w["st"]; label = w["label"]; exact = True
    elif cc:
        c = VG.center(cc, st if cc == "US" else "")
        if not c: return 404, {"error": "unknown location"}
        lat, lon = c; exact = False
        label = (d["_states"].get(st, {}).get("name", st) + ", United States") if st else d["_cc"].get(cc, cc)
    else: return 200, {"global": True}
    stname = d["_states"].get(st, {}).get("name", "") if cc == "US" and st else ""
    km = lambda a: round(VG.km(lat, lon, a["lat"], a["lon"]))
    # NOAA Weather Radio (US and territories): state list, or nearest transmitters to the chosen point
    nwr = []
    if cc in ("US", "PR", "GU", "VI", "AS", "MP"):
        pool = [n for n in d["nwr"] if n["st"] == st] if (st and not exact) else d["nwr"]
        pool = sorted(pool, key=km)[:8] if exact or not st else sorted(pool, key=lambda n: (("wx" not in n), km(n)))[:10]
        with cf.ThreadPoolExecutor(4) as ex: ver = dict(zip([n["cs"] for n in pool], ex.map(lambda n: _verify(n["wx"], "mp3") if n.get("wx") else None, pool)))
        for n in pool:
            v = ver.get(n["cs"]); nwr.append({"cs": n["cs"], "freq": n["f"], "site": n["site"], "st": n["st"], "km": km(n), "status": n["status"], "wfo": n["wfo"],
                                             "counties": n["counties"], "stream": n.get("wx") if v and v.get("ok") else None, "stream_checked": bool(n.get("wx"))})
    # Scanner feeds (Broadcastify: links only; its stream servers are unreachable from this box)
    st_info = d["_states"].get(st) if st else None
    bcfy = [{"name": f"All {stname} scanner feeds (Broadcastify)", "url": f"https://www.broadcastify.com/listen/stid/{int(st_info['fips'])}"}] if st_info else []
    bcfy.append({"name": "Top live scanner feeds right now (Broadcastify)", "url": "https://www.broadcastify.com/listen/top"})
    if cc != "US": bcfy.append({"name": "Browse Broadcastify feeds by country", "url": "https://www.broadcastify.com/listen/"})
    # Air traffic: nearest airports (or the state's / country's biggest) -> LiveATC search
    if exact: aps = sorted(d["airports"], key=km)[:6]
    else:
        aps = [a for a in d["airports"] if (a["rg"] == f"US-{st}" if st else a["cc"] == cc)]
        aps = sorted(aps, key=lambda a: (not a["big"], km(a)))[:6]
    atc = [{"icao": a["icao"], "name": a["name"], "city": a["city"], "km": km(a), "url": f"https://www.liveatc.net/search/?icao={a['icao']}"} for a in aps]
    # Nearest public KiwiSDR receivers (open in the visitor's browser)
    kiwis = [{"label": k["label"], "url": k["url"], "km": km(k)} for k in sorted(d["kiwis"], key=km)[:6]]
    # Broadcasters for the country (and US state): radio-browser.info, news-tagged, HTTPS only, verified before inline play
    cur = [{"name": n, "url": u, "kind": "hls" if ".m3u8" in u else "mp3", "homepage": "", "curated": True} for n, u in CURATED.get(cc, [])]
    rb = cur + [x for x in (_rb(cc, stname) or (_rb(cc, "") if stname else [])) if x["url"] not in {c["url"] for c in cur}]
    with cf.ThreadPoolExecutor(5) as ex: vs = list(ex.map(lambda s: _verify(s["url"], s["kind"]), rb[:8]))
    bc = [{**s, "playable": bool(v and v.get("ok"))} for s, v in zip(rb[:8], vs)]
    bc = sorted(bc, key=lambda s: not s["playable"])
    return 200, {"label": label, "cc": cc, "st": st, "stname": stname, "point": "your position (rounded)" if exact else "centre of the selected area",
                 "nwr": nwr, "scanners": bcfy, "atc": atc, "kiwis": kiwis, "broadcasters": bc,
                 "sources": {"nwr": "NOAA NWR station list (weather.gov) + WXRadio.org relays", "kiwis": "receiverbook.de KiwiSDR list", "atc": "OurAirports + LiveATC",
                             "broadcasters": "radio-browser.info (community directory)", "scanners": "Broadcastify"}}
