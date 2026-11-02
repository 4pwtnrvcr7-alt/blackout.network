"""Network Status: keyless official status feeds + this box's own DNS/HTTPS probes, polled every 5 min into netstatus.db.
Read-only corroboration from blackout.db / broadcasts.db. Never touches the scanner, scoring or push.
ISPs come from IODA (Georgia Tech's public internet-outage API, per-ASN alerts), polled every 15 min. Downdetector is no longer used
(it blocks automated readers and we don't get around bot protection). Visitors never see raw HTTP codes or exception text: see plain()."""
import builtins, json, os, re, socket, sqlite3, ssl, struct, threading, time, random, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
BASE = os.path.dirname(os.path.abspath(__file__)); NDB = os.path.join(BASE, "netstatus.db")
UA = "BlackoutNetwork-dashboard/1.0 (private personal dashboard; polite 5-minute poll)"
POLL = 300; ISP_EVERY = 900
LV = {0: "operational", 1: "notice", 2: "degraded", 3: "major outage", -1: "unreachable", -2: "blocked"}
SP = [("GitHub", "Dev & cloud", "https://www.githubstatus.com"), ("Cloudflare (CDN, DNS 1.1.1.1)", "DNS & CDN", "https://www.cloudflarestatus.com"),
      ("Akamai", "DNS & CDN", "https://www.akamaistatus.com"), ("DigitalOcean", "Dev & cloud", "https://status.digitalocean.com"),
      ("Discord", "Apps & social", "https://discordstatus.com"), ("Reddit", "Apps & social", "https://www.redditstatus.com"),
      ("Zoom", "Apps & social", "https://www.zoomstatus.com"), ("Dropbox", "Apps & social", "https://status.dropbox.com"), ("OpenAI", "Apps & social", "https://status.openai.com")]
# ISPs: each provider's own outage pages need a login or a service address and publish no public machine-readable feed, so the
# signal is IODA's per-network (ASN) outage alerts. First ASN = the provider's main network (it is the source link). An ISP with
# an empty ASN list shows a neutral "No public status feed" row.
IODA = "https://api.ioda.inetintel.cc.gatech.edu/v2"; IODA_UI = "https://ioda.inetintel.cc.gatech.edu/asn/"
ISPS = [("Spectrum", [(20115, "Charter"), (33363, "Bright House, Florida"), (7843, "Time Warner Cable"), (11427, "Texas"), (20001, "Pacific West"),
                      (10796, "Midwest"), (12271, "New York City"), (11351, "Northeast")]),
        ("Xfinity / Comcast", [(7922, "Comcast"), (7015, "Comcast"), (21508, "Comcast"), (33651, "Comcast")]),
        ("AT&T", [(7018, "AT&T Internet"), (20057, "AT&T Mobility")]),
        ("Verizon", [(701, "Verizon Business / Fios"), (22394, "Verizon Wireless"), (6167, "Verizon Wireless")]),
        ("T-Mobile", [(21928, "T-Mobile US")])]
IODA_DS = {"bgp": "routing (BGP)", "ping-slash24": "active probing", "merit-nt": "network telescope"}
PROBE_HOSTS = ["google.com", "youtube.com", "x.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com", "cloudflare.com", "netflix.com", "floridadisaster.org", "weather.gov"]
RESOLVERS = [("Cloudflare 1.1.1.1", "1.1.1.1"), ("Google 8.8.8.8", "8.8.8.8"), ("Quad9 9.9.9.9", "9.9.9.9")]
OUT_RE = re.compile(r"\b(outages?|down for|went down|is down|service (?:disruption|interruption)|internet (?:down|outage|disruption)|connectivity|ddos|dns|cloudflare|aws|azure|google cloud|microsoft 365|starlink|verizon|at&t|spectrum|comcast|xfinity|t-mobile|cell(?:ular)? service|911 (?:outage|down)|fiber cut|submarine cable|undersea cable)\b", re.I)
def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def db():
    c = sqlite3.connect(NDB, timeout=20); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS checks(ts TEXT, src TEXT, grp TEXT, kind TEXT, level INTEGER, status TEXT, detail TEXT, ms INTEGER, url TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ck ON checks(src, ts)"); c.execute("CREATE INDEX IF NOT EXISTS ix_ts ON checks(ts)")
    c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)"); return c
def get(url, timeout=12, raw=False):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/xml,*/*"}), timeout=timeout)
    b = r.read(3_000_000)
    if raw: return b
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"): return b.decode("utf-16")
    return b.decode("utf-8-sig", "replace")
def R(src, grp, level, status, detail="", url="", kind="feed", ms=None): return dict(src=src, grp=grp, level=level, status=status, detail=detail[:600], url=url, kind=kind, ms=ms)
# Global scope: ~30 of Cloudflare's largest edge hubs across all regions (IATA codes from cloudflarestatus.com component names)
MAJOR_HUBS = ("IAD", "ORD", "DFW", "LAX", "SJC", "SEA", "EWR", "ATL", "MIA", "YYZ", "GRU", "SCL", "BOG", "MEX",
              "LHR", "AMS", "FRA", "CDG", "MAD", "MXP", "ARN", "WAW", "DXB", "JNB", "BOM", "SIN", "HKG", "NRT", "ICN", "SYD")
MASS_OUTAGE_N = 60   # PoPs simultaneously in major_outage (routine is ~10-25)
def statuspage(name, grp, base):
    d = json.loads(get(base + "/api/v2/summary.json")); ind = d.get("status", {}).get("indicator", "none")
    inc = [i["name"] for i in d.get("incidents", []) if i.get("status") not in ("resolved", "postmortem")]
    lvl = {"none": 0, "minor": 1, "major": 2, "critical": 3, "maintenance": 1}.get(ind, 1)
    if inc and lvl == 0: lvl = 1
    comp = [x for x in d.get("components", []) if x.get("status") not in ("operational", None) and not x.get("group")]
    dc = [x for x in comp if re.search(r" - \([A-Z]{3}\)$", x["name"])]          # individual edge data centers (e.g. Cloudflare's ~330 PoPs)
    near = [x for x in dc if x["name"][-4:-1] in ("MIA", "TPA", "MCO", "JAX", "ATL") and x.get("status") != "under_maintenance"]   # FL + Atlanta PoPs; planned maintenance does not count
    if dc and not inc:   # a few PoPs out worldwide is normal and traffic re-routes (~50 degraded at any time is routine)
        # global scope: a major hub PoP fully out, 3+ major hubs degraded, or a mass outage raises it; near-Florida PoPs still raise it and are labelled
        act = [x for x in dc if x.get("status") != "under_maintenance"]
        hubs = [x for x in act if x["name"][-4:-1] in MAJOR_HUBS]
        hub_out = [x for x in hubs if x.get("status") == "major_outage"]
        n_out = sum(1 for x in act if x.get("status") == "major_outage")
        major = bool(hub_out) or len(hubs) >= 3 or n_out >= MASS_OUTAGE_N
        lvl = 2 if (major or near) else 1
        comp = near + [x for x in comp if x not in dc]
        why = []
        if hub_out: why.append(f"major hub(s) out: {', '.join(x['name'] for x in hub_out[:4])}")
        elif len(hubs) >= 3: why.append(f"{len(hubs)} major hubs degraded")
        if n_out >= MASS_OUTAGE_N: why.append(f"mass outage: {n_out} PoPs in major outage")
        shown, _seen = [], set()
        for x in hub_out + near + hubs + dc:   # de-duplicated, priority order
            if x["name"] not in _seen: _seen.add(x["name"]); shown.append(x)
        return R(name, grp, lvl, f"{len(dc)} edge data center(s) degraded or re-routed worldwide" + (f" ({'; '.join(why)})" if why else "") +
                 (f", incl. near Florida: {', '.join(x['name'] for x in near)}" if near else ", none near Florida"),
                 ", ".join(f'{x["name"]} ({x["status"].replace("_", " ")})' for x in shown[:6]), base)
    cd = (f"{len(comp)} component(s) not operational: " + ", ".join(f'{x["name"]} ({x["status"].replace("_", " ")})' for x in comp[:5])) if comp else ""
    return R(name, grp, lvl, d.get("status", {}).get("description", ind), "; ".join(inc[:4] + ([cd] if cd else [])), base)
def slack():
    d = json.loads(get("https://slack-status.com/api/v2.0.0/current")); a = d.get("active_incidents") or []
    lvl = 0 if d.get("status") == "ok" and not a else (3 if any(i.get("type") == "outage" for i in a) else 2)
    return R("Slack", "Apps & social", lvl, "All systems operational" if lvl == 0 else f"{len(a)} active incident(s)", "; ".join(i.get("title", "") for i in a[:3]), "https://slack-status.com")
def aws():
    d = json.loads(get("https://health.aws.amazon.com/public/currentevents")); now = time.time()
    fresh = [e for e in d if now - int(e.get("date", 0)) < 72 * 3600]; old = [e for e in d if e not in fresh]
    lvl = (3 if any(e.get("status") == "3" for e in fresh) else 2) if fresh else (1 if old else 0)
    det = "; ".join(f'{e.get("service_name")} ({e.get("region_name")}): {e.get("summary")}' + (" (open since " + time.strftime("%b %d", time.gmtime(int(e["date"]))) + ")" if e in old else "") for e in (fresh + old)[:4])
    return R("AWS", "Big cloud", lvl, "No current events" if not d else f"{len(fresh)} new, {len(old)} long-running event(s)", det, "https://health.aws.amazon.com/health/status")
def gstyle(name, grp, url, page):
    d = json.loads(get(url)); act = [i for i in d if not i.get("end")]
    sev = {"low": 1, "medium": 2, "high": 3}; lvl = max([sev.get(i.get("severity"), 2) for i in act] or [0])
    return R(name, grp, lvl, "No active incidents" if not act else f"{len(act)} active incident(s)", "; ".join(f'{i.get("service_name")}: {(i.get("external_desc") or "").replace("**", "").splitlines()[0][:140]}' for i in act[:3]), page)
def azure():
    root = ET.fromstring(get("https://azure.status.microsoft/en-us/status/feed/")); items = root.findall("./channel/item")
    return R("Microsoft Azure", "Big cloud", 2 if items else 0, "No active incidents" if not items else f"{len(items)} active item(s)", "; ".join((i.findtext("title") or "") for i in items[:3]), "https://azure.status.microsoft/en-us/status")
def apple():
    t = get("https://www.apple.com/support/systemstatus/data/system_status_en_US.js"); d = json.loads(t[t.find("{"): t.rfind("}") + 1])
    act = [(s["serviceName"], e) for s in d.get("services", []) for e in s.get("events", []) if (e.get("eventStatus") or "").lower() not in ("resolved", "completed")]
    lvl = max([3 if e.get("statusType") == "Outage" else 2 if e.get("statusType") in ("Issue", "Performance") else 1 for _, e in act] or [0])
    return R("Apple services", "Apps & social", lvl, "All services available" if not act else f"{len(act)} active event(s)", "; ".join(f"{n}: {e.get('statusType', '')}" for n, e in act[:4]), "https://www.apple.com/support/systemstatus/")
def m365():
    d = json.loads(get("https://status.cloud.microsoft/api/posts/m365Consumer")); bad = [x for x in d if x.get("Status") != "Operational"]
    return R("Microsoft 365 / Outlook / Teams (consumer)", "Big cloud", 2 if bad else 0, "Operational" if not bad else f"{len(bad)} service(s) affected", "; ".join(f'{x["ServiceDisplayName"]}: {x.get("Status")} {x.get("Title", "")}' for x in bad[:3]), "https://status.cloud.microsoft")
def meta():
    d = json.loads(get("https://metastatus.com/data/orgs.json")); bad = [(o["name"], s) for o in d for s in o.get("services", []) if s.get("status") not in (None, "No known issues")]
    lvl = max([3 if "outage" in s["status"].lower() or "major" in s["status"].lower() else 2 for _, s in bad] or [0])
    return R("Meta (Facebook, Instagram, WhatsApp, Messenger)", "Apps & social", lvl, "No known issues" if not bad else f"{len(bad)} service(s) with issues", "; ".join(f'{o}/{s["name"]}: {s["status"]}' for o, s in bad[:4]), "https://metastatus.com")
def ioda_isp(name, asns, hours=24):
    """Normal / Degraded / Outage from IODA per-ASN alerts. IODA alerts are state changes (critical, then normal on recovery), so an
    ASN counts as affected while its latest alert on a data source in the last `hours` is still critical."""
    if not asns: return R(name, "ISPs", -1, "No public status feed", "", "", "isp")
    src = "Source: IODA, Georgia Tech"
    url = IODA_UI + str(asns[0][0]); now = int(time.time()); hit = []; ok = 0
    for asn, lab in asns:
        try: d = json.loads(get(f"{IODA}/outages/alerts?from={now - hours * 3600}&until={now}&entityType=asn&entityCode={asn}", timeout=15)).get("data") or []
        except Exception: continue
        ok += 1; last = {}
        for x in d:
            if x.get("datasource") in IODA_DS and (x["datasource"] not in last or x.get("time", 0) >= last[x["datasource"]].get("time", 0)): last[x["datasource"]] = x
        bad = [x for x in last.values() if x.get("level") == "critical"]
        if bad: hit.append((asn, lab, bad))
    if not ok: return R(name, "ISPs", -1, "Status temporarily unavailable", "Shown in grey until IODA answers again · " + src, url, "isp")
    net = f"{len(asns)} network{'s' if len(asns) > 1 else ''} checked" if ok == len(asns) else f"{ok} of {len(asns)} networks checked"
    if not hit: return R(name, "ISPs", 0, "Normal", f"{net} · {src}", url, "isp")
    def pct(x):
        try: return round(100 * x["value"] / x["historyValue"])
        except Exception: return None
    deep = any(len(b) >= 2 or any((pct(x) or 100) < 50 for x in b) for _, _, b in hit)
    lvl = 3 if deep or len(hit) >= 2 else 2
    why = "; ".join(f"{lab} (AS{asn}): " + ", ".join(IODA_DS[x["datasource"]] + (f" at {pct(x)}% of normal" if pct(x) is not None else " below normal") for x in b) for asn, lab, b in hit[:3])
    return R(name, "ISPs", lvl, "Outage" if lvl == 3 else "Degraded", f"{why} · {src} · {net}", IODA_UI + str(hit[0][0]), "isp")
def dnsq(server, name="example.com", timeout=3):
    qid = random.randint(0, 65535); q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(timeout); t0 = time.time()
    try:
        s.sendto(q, (server, 53)); r, _ = s.recvfrom(2048); ms = int((time.time() - t0) * 1000)
        rc = r[3] & 15; an = struct.unpack(">H", r[6:8])[0]
        return (rc == 0 and an > 0), ms, f"rcode {rc}, {an} answer(s)"
    finally: s.close()
def resolver(label, ip):
    try:
        try: ok, ms, det = dnsq(ip)
        except socket.timeout: ok, ms, det = dnsq(ip, timeout=4)   # one retry before calling it down
        return R(label, "Box probes: DNS resolvers", 0 if ok and ms < 500 else 1 if ok else 2, f"Answered in {ms} ms" if ok else "Answered with an error", det, "", "probe", ms)
    except Exception as e: return R(label, "Box probes: DNS resolvers", 3, "No answer", str(e)[:120], "", "probe")
def hprobe(host):
    t0 = time.time()
    try: socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP); dms = int((time.time() - t0) * 1000)
    except Exception as e: return R(host, "Box probes: HTTPS", 3, "DNS lookup failed", str(e)[:120], "https://" + host, "probe")
    t1 = time.time()
    try:
        req = urllib.request.Request("https://" + host + "/", method="HEAD", headers={"User-Agent": UA})
        try: code = urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e: code = e.code
        ms = int((time.time() - t1) * 1000)
        lvl = 0 if code < 500 and ms < 3000 else 1 if code < 500 else 2
        return R(host, "Box probes: HTTPS", lvl, (f"Responded in {ms} ms" if code < 500 else f"Server error after {ms} ms"), f"DNS lookup {dms} ms", "https://" + host, "probe", ms)
    except Exception as e: return R(host, "Box probes: HTTPS", 3, "HTTPS failed", str(e)[:120], "https://" + host, "probe")
def jobs(with_dd):
    J = [lambda a=a: statuspage(*a) for a in SP] + [slack, aws, azure, apple, m365, meta,
         lambda: gstyle("Google Cloud", "Big cloud", "https://status.cloud.google.com/incidents.json", "https://status.cloud.google.com"),
         lambda: gstyle("Google Workspace (Gmail, Drive, Meet)", "Big cloud", "https://www.google.com/appsstatus/dashboard/incidents.json", "https://www.google.com/appsstatus/dashboard/")]
    J += [lambda a=a: resolver(*a) for a in RESOLVERS] + [lambda h=h: hprobe(h) for h in PROBE_HOSTS]
    if with_dd: J += [lambda a=a: ioda_isp(*a) for a in ISPS]
    return J
NAMES = {}
def safe(f):
    try: return f()
    except Exception as e:
        n = getattr(f, "__defaults__", None); n = n[0] if n else None
        lab = (n[0] if isinstance(n, tuple) else n) or getattr(f, "__name__", "?")
        return R(str(lab), "Feed errors", -1, "Status feed temporarily unavailable", f"{type(e).__name__}: {str(e)[:140]}")   # detail is internal; plain() hides it
def alerts_from(rows):
    return [r for r in rows if r["level"] >= 2 and not (r["kind"] in ("probe", "isp") and r.get("streak", 1) < 2)]   # probes and ISPs alert on 2 readings in a row
def poll_once():
    c = db()
    try:
        last_isp = float((c.execute("SELECT v FROM meta WHERE k='isp'").fetchone() or ["0"])[0])
        with_dd = time.time() - last_isp >= ISP_EVERY
        with ThreadPoolExecutor(8) as ex: rows = list(ex.map(safe, jobs(with_dd)))
        ts = iso()
        for r in rows:   # a resolver/host this box has NEVER reached is a property of this network (egress filtering), not an outage
            if r["kind"] == "probe" and r["level"] == 3 and not c.execute("SELECT 1 FROM checks WHERE src=? AND level IN (0,1) LIMIT 1", (r["src"],)).fetchone():
                r["level"] = -1; r["status"] = NEVER
        c.executemany("INSERT INTO checks VALUES(?,?,?,?,?,?,?,?,?)", [(ts, r["src"], r["grp"], r["kind"], r["level"], r["status"], r["detail"], r["ms"], r["url"]) for r in rows])
        if with_dd: c.execute("INSERT OR REPLACE INTO meta VALUES('isp',?)", (str(time.time()),))
        c.execute("INSERT OR REPLACE INTO meta VALUES('last_poll',?)", (ts,))
        c.execute("DELETE FROM checks WHERE ts<?", (iso(datetime.now(timezone.utc) - timedelta(days=8)),)); c.commit()
    finally: c.close()
    try:
        a = alerts()
        key = json.dumps(sorted(x["src"] for x in a["alerts"]))
        if getattr(builtins, "_bn_live", None) and key != ST.get("akey"):
            import livepush; livepush.broadcast("netstatus", {"count": a["count"], "alerts": [x["src"] for x in a["alerts"]]})
        ST["akey"] = key
    except Exception: pass
ST = getattr(builtins, "_bn_net", None)
if ST is None: ST = builtins._bn_net = {"started": False}
def loop():
    while True:
        t0 = time.time()
        try: poll_once(); ST["err"] = None
        except Exception as e: ST["err"] = repr(e)[:200]
        ST["last"] = iso(); time.sleep(max(30, POLL - (time.time() - t0)))
if not ST["started"]:
    ST["started"] = True; threading.Thread(target=lambda: loop(), daemon=True, name="netstatus").start()
NEVER = "Not reachable from our server"
HTTP_RE = re.compile(r"^HTTP (\d{3}) in (\d+) ms$"); DNS_RE = re.compile(r"^rcode (\d+), (\d+) answer")
def plain(r):
    """What visitors see: no HTTP status codes, exception text or resolver internals. Applied on read, so older rows are cleaned too."""
    st, det, k = r.get("status") or "", r.get("detail") or "", r.get("kind")
    if r.get("grp") == "Feed errors":
        r["grp"] = "Status feeds unavailable"; st = "Status feed temporarily unavailable"; det = "Shown in grey until the provider's feed answers again."
    elif k == "probe":
        m = HTTP_RE.match(st)
        if m: st = f"Responded in {m.group(2)} ms" if int(m.group(1)) < 500 else f"Server error after {m.group(2)} ms"
        if st.startswith("answered in"): st = "A" + st[1:]
        if st.startswith("never reachable") or st == NEVER:
            st = NEVER; det = "Our server's network doesn't allow this check. It isn't an outage."
        elif r.get("level", 0) >= 2 or st in ("no answer", "No answer", "HTTPS failed", "DNS lookup failed", "bad answer"):
            st = {"no answer": "No answer", "bad answer": "Answered with an error"}.get(st, st)
            low = det.lower()
            det = ("No reply in time" if "timed out" in low or "timeout" in low else "Connection refused" if "refused" in low
                   else "Name not found" if "name or service" in low or "nodename" in low or "getaddrinfo" in low else "")
        else:
            d = DNS_RE.match(det)
            if d: det = "" if d.group(1) == "0" else "Answered with an error"
            if det.startswith("DNS ") and not det.startswith("DNS lookup"): det = "DNS lookup " + det[4:]
    r["status"], r["detail"] = st, det
    return r
def latest(c):
    lp = (c.execute("SELECT v FROM meta WHERE k='last_poll'").fetchone() or [None])[0]
    if not lp: return None, []
    rows = [dict(r) for r in c.execute("SELECT * FROM checks WHERE ts=? AND NOT (kind='isp' AND grp!='ISPs')", (lp,))]
    # latest ISP rows come from the last poll that included them (rows from the retired Downdetector check are ignored)
    if not any(r["kind"] == "isp" for r in rows):
        t = c.execute("SELECT MAX(ts) FROM checks WHERE kind='isp' AND grp='ISPs'").fetchone()[0]
        if t: rows += [dict(r) for r in c.execute("SELECT * FROM checks WHERE ts=? AND kind='isp' AND grp='ISPs'", (t,))]
    for r in rows:
        prev = c.execute("SELECT level FROM checks WHERE src=? AND ts<? ORDER BY ts DESC LIMIT 1", (r["src"], r["ts"])).fetchone()
        r["streak"] = 2 if prev and prev[0] >= 2 else 1
    return lp, [plain(r) for r in rows]
def alerts():
    c = db()
    try: lp, rows = latest(c)
    finally: c.close()
    a = alerts_from(rows)
    return {"polled": lp, "count": len(a), "alerts": [{k: r[k] for k in ("src", "grp", "level", "status", "detail", "url")} for r in a]}
def corroborate():
    since = iso(datetime.now(timezone.utc) - timedelta(hours=24)); out = {"wire": [], "broadcasts": []}
    try:
        c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
        for r in c.execute("SELECT cluster_id,title,score,rank,first_seen,links FROM clusters WHERE first_seen>=? ORDER BY score DESC LIMIT 600", (since,)):
            if OUT_RE.search(r["title"] or ""):
                l = (json.loads(r["links"] or "[]") or [{}])[0].get("url", "")
                out["wire"].append({"id": r["cluster_id"], "title": r["title"], "score": r["score"], "rank": r["rank"], "first_seen": r["first_seen"], "url": l})
        c.close()
    except Exception as e: out["wire_err"] = str(e)[:120]
    try:
        c = sqlite3.connect(f"file:{BASE}/broadcasts.db?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
        for r in c.execute("SELECT id,source,title,text,link,published FROM clips WHERE published>=? ORDER BY published DESC LIMIT 800", (since,)):
            if OUT_RE.search((r["title"] or "") + " " + (r["text"] or "")[:400]): out["broadcasts"].append({"id": r["id"], "source": r["source"], "title": r["title"], "url": r["link"], "published": r["published"]})
        c.close()
    except Exception as e: out["bc_err"] = str(e)[:120]
    out["wire"] = out["wire"][:15]; out["broadcasts"] = out["broadcasts"][:15]; return out
def status(qs):
    win = (qs.get("window") or ["24h"])[0]; hrs, nb = (168, 84) if win == "7d" else (24, 48)
    start = datetime.now(timezone.utc) - timedelta(hours=hrs); bsec = hrs * 3600 / nb
    c = db()
    try:
        lp, rows = latest(c)
        hist = {}
        for src, ts, lvl in c.execute("SELECT src, ts, level FROM checks WHERE ts>=? AND NOT (kind='isp' AND grp!='ISPs')", (iso(start),)):
            i = int((datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) - start).total_seconds() // bsec)
            h = hist.setdefault(src, [None] * nb)
            if 0 <= i < nb: h[i] = lvl if h[i] is None else (max(h[i], lvl) if lvl >= 0 or h[i] < 0 else lvl)
        n = c.execute("SELECT COUNT(DISTINCT ts) FROM checks").fetchone()[0]
    finally: c.close()
    for r in rows: r["hist"] = hist.get(r["src"], [None] * nb)
    a = alerts_from(rows)
    return {"polled": lp, "polls_stored": n, "window": win, "bucket_minutes": int(bsec // 60), "start": iso(start), "poll_seconds": POLL, "levels": LV,
            "sources": rows, "alerts": [r["src"] for r in a], "corroboration": corroborate(), "worker_error": ST.get("err"),
            "note": "Box probes measure this computer's own network path, not conditions in Florida."}
def handle_get(path, qs):
    if path == "/api/netstatus/alerts": return 200, alerts()
    if path == "/api/netstatus": return 200, status(qs)
    return 404, {"error": "not found"}
