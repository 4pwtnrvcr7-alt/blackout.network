"""/water: Water treatment status tracker (Matt, Nov 27 2026). Preview build.

Read-only, keyless, free public data only. Every item carries a link to its source record. Nothing is invented: a source that
fails is shown as unavailable (its last good copy is kept), never filled in.

Layers (each its own kind):
  advisory   active boil-water / do-not-drink notices published as official open data by a state or province:
             Alaska DEC (ArcGIS), Manitoba Office of Drinking Water (two ArcGIS layers), Newfoundland and Labrador (ArcGIS).
             Points come from the agency's own coordinates.
  violation  U.S. community water systems serving more than 3,300 people that EPA's SDWIS (via ECHO) lists with a CURRENT
             health-based violation. EPA publishes no coordinates for these, so the dot sits at the centre of the county served
             (U.S. Census Gazetteer, public domain) and is labelled that way. A violation is a compliance finding, not a boil notice.
  wastewater U.S. major sewage treatment plants in significant noncompliance (EPA ICIS-NPDES via ECHO), with EPA's own plant coordinates.
  news       news reports of water-plant failures and boil notices (Google News RSS); listed, never pinned (no reliable place).
Cache: in memory per source, stale-while-revalidate. Refresh (?fresh=1) re-pulls every source older than 60 s, in parallel.
Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py, config.json, blackout.db, the newsletter or the QA gate.
Routes: /water (page), /api/water/data, /api/water/app.js, /api/water/app.css."""
import os, re, json, time, html as _html, hashlib, threading, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import email.utils
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "water_static")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
UA = "BlackoutNetwork-water/1.0 (+https://blackout.network/water; cached, polite)"
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
ECHO = "https://echodata.epa.gov/echo"
NEWS_MAX_AGE_D = 5
MIN_POP = 3301            # EPA size bands: 3,301 and up (medium and large systems)
MIN_REFRESH_S = 60        # one real upstream pull per source per minute, however many taps

AK = "https://dec.alaska.gov/arcgis/rest/services/EH/BWN_DND/FeatureServer/0"
MB1 = "https://services.arcgis.com/mMUesHYPkXjaFGfS/arcgis/rest/services/Current_BWAPWS/FeatureServer/0"
MB2 = "https://services.arcgis.com/mMUesHYPkXjaFGfS/arcgis/rest/services/Current_BWA_SPWS/FeatureServer/0"
NL = "https://maps.gov.nl.ca/gsdw/rest/services/water/BoilAdvisories/FeatureServer/0"

# id, label, kind, free/paid, publisher URL, TTL seconds
SOURCES = [
    ("ak", "Alaska DEC boil water and do-not-drink notices", "advisory", "https://dec.alaska.gov/eh/dw/", 600),
    ("mb", "Manitoba Office of Drinking Water boil water advisories", "advisory", "https://geoportal.gov.mb.ca/datasets/manitoba::current-bwapws", 600),
    ("nl", "Newfoundland and Labrador boil water advisories", "advisory", "https://www.gov.nl.ca/ecc/waterres/cwq/drinking-water-advisories/", 600),
    ("sdw", "EPA ECHO: drinking water systems with a current health-based violation", "violation", "https://echo.epa.gov/", 21600),
    ("cwa", "EPA ECHO: major sewage plants in significant noncompliance", "wastewater", "https://echo.epa.gov/", 21600),
    ("news", "News reports (Google News RSS)", "news", "https://news.google.com/", 1200),
]
SRC = {s[0]: s for s in SOURCES}

def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def _ms(v):
    try: return iso(datetime.fromtimestamp(int(v) / 1000, timezone.utc)) if v else None
    except Exception: return None

def _get(url, timeout=20, cap=12_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read(cap + 1)
    if len(b) > cap: raise OSError("response too large")
    return b
def _json(url, timeout=20): return json.loads(_get(url, timeout))
def _arc(layer, where="1=1"):
    """All features of an ArcGIS layer as WGS84 points (paged; the layers here have under 1,000 rows)."""
    out, off = [], 0
    while True:
        q = urllib.parse.urlencode({"where": where, "outFields": "*", "outSR": "4326", "f": "json", "resultOffset": off, "resultRecordCount": 1000})
        d = _json(layer + "/query?" + q)
        if "error" in d: raise OSError("ArcGIS error")
        fs = d.get("features") or []; out += fs
        if not d.get("exceededTransferLimit") or not fs: break
        off += len(fs)
        if off > 5000: break
    return out
def _clean(s, n=300):
    s = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()
    return s[:n]
def _title(s):
    s = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", _clean(s, 120)))
    if not s.isupper(): return s
    t = re.sub(r"(^|[\s(/-])([a-z])", lambda m: m.group(1) + m.group(2).upper(), s.lower())
    return re.sub(r"(?<=\s)(Of|The|And|At|In|On|For|To|A|An|By|Or)(?=\s)", lambda m: m.group(1).lower(), t)
def _id(*p): return hashlib.md5("|".join(str(x) for x in p).encode()).hexdigest()[:10]
def _pt(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except Exception: return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): return None
    return round(lat, 4), round(lon, 4)

# ---------------------------------------------------------------- official advisories
def fetch_ak():
    out = []
    for f in _arc(AK):
        a = f.get("attributes") or {}; g = f.get("geometry") or {}
        if a.get("CLOSED_DATE"): continue                       # the layer is "open notices"; a closed one is never shown
        p = _pt(g.get("y"), g.get("x"))
        if not p: continue
        dnd = (a.get("TYPE_CODE_CV") or "").strip().upper() == "DNDU"
        oid = a.get("ESRI_OID")
        out.append(dict(id="ak" + _id(a.get("PWSID")), kind="advisory", level="dnd" if dnd else "boil", label="Do not drink or use" if dnd else "Boil water notice",
                        name=_title(a.get("TINWSYS_NAME")), place="Alaska", cc="US", lat=p[0], lon=p[1], precision="point", pop=a.get("D_POPULATION_COUNT"),
                        since=_ms(a.get("BWN_Issue_Date")), note=_clean(a.get("Comments"), 320) or None,
                        by="Alaska Department of Environmental Conservation", src="Alaska DEC (open data)",
                        url=f"{AK}/{oid}?f=html" if oid else AK))
    return out

def fetch_mb():
    out = []
    for layer, kind in ((MB1, "public"), (MB2, "semi-public")):
        for f in _arc(layer):
            a = f.get("attributes") or {}; g = f.get("geometry") or {}
            p = _pt(a.get("Lat") or g.get("y"), a.get("Long") or g.get("x"))
            if not p: continue
            oid = a.get("ObjectId")
            pop = a.get("Population_Range")
            note = "Timeframe to resolve: " + a["Timeframe_to_Resolve"] if a.get("Timeframe_to_Resolve") else None
            cat = a.get("Advisory_Category") or ("Semi-public water system" if kind == "semi-public" else "Public water system")
            out.append(dict(id="mb" + _id(kind, a.get("System_Name"), oid), kind="advisory", level="boil", label="Boil water advisory",
                            name=_title(re.sub(r"\s*-\s*(PWS|SPWS)$", "", str(a.get("System_Name") or ""))), place=f"Manitoba, {a.get('Regional_Health_Authority') or ''}".strip(", "), cc="CA",
                            lat=p[0], lon=p[1], precision="point", pop=None, pop_text=(str(pop) + " people") if pop else None, since=_ms(a.get("Issue_Date")),
                            note=("; ".join(x for x in (cat, note) if x)) or None, by="Government of Manitoba, Office of Drinking Water",
                            src="Manitoba open data", url=f"{layer}/{oid}?f=html" if oid else layer))
    return out

def fetch_nl():
    out = []
    for f in _arc(NL):
        a = f.get("attributes") or {}; g = f.get("geometry") or {}
        p = _pt(g.get("y"), g.get("x"))
        if not p: continue
        oid = a.get("OBJECTID")
        out.append(dict(id="nl" + _id(a.get("WS_NUM"), a.get("SA_NUM"), oid), kind="advisory", level="boil", label="Boil water advisory",
                        name=_title(a.get("COMMUNITY_NAME") or a.get("SERVICED_AREA")), place="Newfoundland and Labrador", cc="CA", lat=p[0], lon=p[1], precision="point",
                        pop=a.get("POPULATION_SERVICED"), since=_ms(a.get("BOIL_ADVISORY_ISSUE_DATE")), note=_clean(a.get("BOIL_ADVISORY_REASON"), 320) or None,
                        by="Government of Newfoundland and Labrador, Water Resources Management", src="Newfoundland and Labrador open data",
                        url=f"{NL}/{oid}?f=html" if oid else NL))
    return out

# ---------------------------------------------------------------- EPA ECHO
_CENT = None
def centroids():
    global _CENT
    if _CENT is None:
        with open(os.path.join(STATIC, "county_centroids.json")) as fh: _CENT = json.load(fh)
    return _CENT

def _echo_rows(first_url, key, cols):
    """Run an ECHO search, then page its results (qid) until every row is read."""
    r = _json(first_url, 40)["Results"]
    if r.get("Message") not in ("Success", "Working"): raise OSError("ECHO: " + str(r.get("Message")))
    qid, total = r["QueryID"], int(r.get("QueryRows") or 0)
    rows, page = [], 1
    while len(rows) < total and page <= 6:
        d = _json(f"{ECHO}/{key}.get_qid?output=JSON&qid={qid}&pageno={page}&qcolumns={cols}", 40)["Results"]
        part = d.get("WaterSystems") or d.get("Facilities") or []
        if not part: break
        rows += part; page += 1
    if total and len(rows) < total * 0.9: raise OSError("ECHO returned a partial result")
    return rows

def _num(v):
    try: return int(float(str(v).replace(",", "")))
    except Exception: return None

def fetch_sdw():
    cent = centroids(); out = []
    u = (f"{ECHO}/sdw_rest_services.get_systems?output=JSON&p_act=Y&p_systyp=CWS&p_cs=H&p_popsv=IN3K_10K,IN10K_100K,IN100K_1M,GT1M&responseset=1000")
    for w in _echo_rows(u, "sdw_rest_services", "1,2,3,4,6,14,18,19,21,22,43,47,48,62"):
        pop = _num(w.get("PopulationServedCount"))
        if not pop or pop < MIN_POP: continue
        fips = str(w.get("FIPSCodes") or "").split(",")[0].strip()
        c = cent.get(fips)
        if not c: continue                                   # no county to place it in: not drawn, never guessed
        cont = [re.sub(r"^\d+=", "", x.strip()).strip() for x in re.split(r";|,(?=\s*\d{3,4}=)", str(w.get("SDWAContaminantsInCurViol") or ""))]
        cont = [x for x in cont if x and not re.match(r"(?i)public notice|other|consumer confidence", x)]
        serious = str(w.get("SeriousViolator") or "").lower() == "yes"
        q = _num(w.get("QtrsWithVio"))
        bits = []
        if cont: bits.append("Rules or contaminants in current violation: " + ", ".join(cont[:5]) + ".")
        if q: bits.append(f"Violations in {q} of the last 12 quarters.")
        if serious: bits.append("Flagged by EPA as a serious violator.")
        place = ", ".join(x for x in (_title(re.sub(r"\s*\([A-Z]{1,3}\)", "", str(w.get("CitiesServed") or "").split(",")[0])), c[2], w.get("StateCode")) if x)
        out.append(dict(id="sd" + str(w.get("PWSId")), kind="violation", level="serious" if serious else "viol", label="Serious violator" if serious else "Health-based violation",
                        name=_title(w.get("PWSName")), place=place, cc="US", lat=c[0], lon=c[1], precision="county", pop=pop, since=None, note=" ".join(bits),
                        by="U.S. EPA, Safe Drinking Water Information System (SDWIS)", src="EPA ECHO, SDWIS", url=w.get("DfrUrl") or "https://echo.epa.gov/"))
    out.sort(key=lambda x: (-(x["level"] == "serious"), -(x["pop"] or 0)))
    return out

def fetch_cwa():
    out = []
    u = (f"{ECHO}/cwa_rest_services.get_facilities?output=JSON&p_sic2=4952&p_maj=Y&p_act=Y&p_ptype=NPD&p_psncq=GE8&responseset=1000")
    for w in _echo_rows(u, "cwa_rest_services", "1,4,5,26,27,28,100,102,105"):
        p = _pt(w.get("FacLat"), w.get("FacLong"))
        if not p or not w.get("CWPSNCStatus"): continue
        q = _num(w.get("CWPQtrsWithSNC")); flow = w.get("CWPTotalDesignFlowNmbr")
        rid = w.get("RegistryID")
        bits = [f"Major sewage treatment plant in significant noncompliance for {q} of the last 12 quarters." if q else "Major sewage treatment plant in significant noncompliance.",
                f"Latest status: {_clean(w.get('CWPSNCStatus'), 80)}."]
        try:
            if flow and float(flow) > 0: bits.append(f"Design flow {float(flow):g} million gallons per day.")
        except Exception: pass
        m = re.match(r"(\d\d)/(\d\d)/(\d{4})", str(w.get("CWPSNCStatusDate") or ""))
        out.append(dict(id="cw" + _id(w.get("SourceID")), kind="wastewater", level="snc", label="Significant noncompliance", name=_title(w.get("CWPName")),
                        place=", ".join(x for x in (_title(w.get("CWPCity")), w.get("CWPState")) if x), cc="US", lat=p[0], lon=p[1], precision="point", pop=None,
                        since=f"{m.group(3)}-{m.group(1)}-{m.group(2)}T00:00:00Z" if m else None, note=" ".join(bits), by="U.S. EPA, ICIS-NPDES", src="EPA ECHO, ICIS-NPDES",
                        url=f"https://echo.epa.gov/detailed-facility-report?fid={rid}&sys=ICIS" if rid else "https://echo.epa.gov/", q=q or 0))
    out.sort(key=lambda x: -x.get("q", 0))
    for x in out: x.pop("q", None)
    return out

# ---------------------------------------------------------------- news
NEWS_Q = ['("boil water" OR "boil advisory" OR "do not drink") (notice OR advisory OR order OR lifted OR issued)',
          '("water treatment plant" OR "water plant" OR "wastewater treatment plant" OR "sewage treatment plant") (failure OR outage OR contamination OR shutdown OR flooded OR offline OR "boil water")']
NEWS_OK = re.compile(r"\b(boil(?:ing)? (?:water )?(?:notice|advisory|order|alert)|boil[- ]water|do[- ]not[- ](?:drink|use)|(?:water|wastewater|sewage) (?:treatment )?plant|water treatment|water system|water main)\b", re.I)
NEWS_BAD = re.compile(r"\b(recipe|how to|stock|shares|earnings|price target|podcast|opinion|editorial|obituary|horoscope|webinar|conference|grant|ribbon|groundbreaking|hiring|job)\b", re.I)

def fetch_news():
    seen, out, ok = set(), [], 0
    for q in NEWS_Q:
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f"{q} when:{NEWS_MAX_AGE_D}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try: root = ET.fromstring(_get(u, 15)); ok += 1
        except Exception: continue
        for it in root.iter("item"):
            t = _clean(it.findtext("title"), 220); src = _clean(it.findtext("source"), 60)
            if src and t.endswith(" - " + src): t = t[: -len(src) - 3]
            link = (it.findtext("link") or "").strip()
            try: pd = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
            except Exception: pd = None
            if pd and pd.tzinfo is None: pd = pd.replace(tzinfo=timezone.utc)
            if not t or not link.startswith("https://") or not pd: continue
            if (now() - pd).days >= NEWS_MAX_AGE_D or pd > now(): continue
            if not NEWS_OK.search(t) or NEWS_BAD.search(t): continue
            k = re.sub(r"\W+", " ", t.lower())[:70]
            if k in seen: continue
            seen.add(k)
            out.append(dict(id="nw" + _id(link), kind="news", level="news", label="News report", name=t, place=src or "News", cc=None, lat=None, lon=None, precision=None,
                            pop=None, since=iso(pd), note=None, by=src or "News outlet", src=src or "News", url=link))
    if not ok: raise OSError("news feed unavailable")
    out.sort(key=lambda x: x["since"], reverse=True)
    return out[:40]

FETCH = {"ak": fetch_ak, "mb": fetch_mb, "nl": fetch_nl, "sdw": fetch_sdw, "cwa": fetch_cwa, "news": fetch_news}

# ---------------------------------------------------------------- cache (stale-while-revalidate, one refresh per source at a time)
_C = {}            # source id -> {"t": last attempt, "ok_t": last success, "items": [...], "err": str|None, "busy": bool}
_L = threading.Lock()
def _run(sid):
    t0 = time.time()
    try:
        items = FETCH[sid]()
        with _L: _C[sid] = {"t": time.time(), "ok_t": time.time(), "items": items, "err": None, "busy": False, "ms": int((time.time() - t0) * 1000)}
    except Exception as ex:
        with _L:
            old = _C.get(sid) or {}
            _C[sid] = {"t": time.time(), "ok_t": old.get("ok_t"), "items": old.get("items") or [], "err": type(ex).__name__, "busy": False, "ms": int((time.time() - t0) * 1000)}

def _kick(ids):
    """Start a background pull for each source that is not already being pulled. Returns the started thread list."""
    th = []
    for sid in ids:
        with _L:
            e = _C.setdefault(sid, {"t": 0, "ok_t": None, "items": [], "err": None, "busy": False})
            if e["busy"]: continue
            e["busy"] = True
        t = threading.Thread(target=_run, args=(sid,), daemon=True, name="water-" + sid); t.start(); th.append(t)
    return th

def data(force=False, budget=18.0):
    due = []
    for sid, _l, _k, _u, ttl in SOURCES:
        e = _C.get(sid); age = time.time() - (e["t"] if e else 0)
        if not e or not e["t"] or age > ttl or (force and age > MIN_REFRESH_S): due.append(sid)
    threads = _kick(due)
    cold = [sid for sid in due if not (_C.get(sid) or {}).get("ok_t")]
    if threads and (force or cold):                      # first load or a Refresh tap waits for the pull; a routine expiry serves the stale copy
        end = time.time() + budget
        for t in threads:
            t.join(max(0.1, end - time.time()))
    r = snapshot(); r["pulled"] = [t.name[6:] for t in threads]
    return r

def snapshot():
    items, srcs = [], []
    for sid, label, kind, url, ttl in SOURCES:
        e = _C.get(sid) or {"items": [], "ok_t": None, "err": None, "busy": False}
        items += e["items"]
        srcs.append(dict(id=sid, label=label, kind=kind, url=url, count=len(e["items"]), updated=iso(datetime.fromtimestamp(e["ok_t"], timezone.utc)) if e.get("ok_t") else None,
                         ok=bool(e.get("ok_t")) and not e.get("err"), loading=bool(e.get("busy")) and not e.get("ok_t"), error=e.get("err")))
    counts, pubs, slim = {}, {}, []
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
        pubs[it["src"]] = it.get("by")
        slim.append({k: v for k, v in it.items() if v is not None and k != "by"})     # the page needs only what is set; publisher sits once per source
    return dict(generated=iso(now()), counts=counts, sources=srcs, pubs=pubs, items=slim)

# ---------------------------------------------------------------- page
CREDITS = ('<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">© OpenMapTiles</a> '
           '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a> · U.S. EPA ECHO · U.S. Census Bureau Gazetteer · '
           'Alaska DEC · Government of Manitoba (OpenMB licence) · Government of Newfoundland and Labrador')

_V = {}
def _v(name):
    p = os.path.join(STATIC, name)
    try:
        st = os.stat(p); k = (st.st_mtime_ns, st.st_size); h = _V.get(name)
        if h and h[0] == k: return h[1]
        with open(p, "rb") as f: v = hashlib.md5(f.read()).hexdigest()[:12]
        _V[name] = (k, v); return v
    except OSError: return "0"

def page():
    import sitenav, sitenav_ui
    try:
        import signal_map
        mlv, mlc = signal_map._v("maplibre-gl.js"), signal_map._v("maplibre-gl.css")
    except Exception: mlv = mlc = "0"
    title = "Water treatment status | BLACKOUT.NETWORK"
    desc = ("Active boil-water and do-not-drink notices from state and provincial agencies, U.S. drinking water systems with current EPA health-based violations, "
            "sewage plants in significant noncompliance, and news reports. Every item links to its source.")
    chips = [("advisory", "Boil and do-not-drink notices"), ("violation", "EPA health violations"), ("wastewater", "Sewage plant noncompliance"), ("news", "In the news")]
    chip_html = "".join(f'<button type="button" class="wt-chip" data-k="{k}" aria-pressed="true"><i class="wt-dot wt-{k}"></i><span>{E(t)}</span><b data-n="{k}">0</b></button>' for k, t in chips)
    return f'''<!doctype html><html lang="en" class="wt-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{sitenav_ui.THEME_SCRIPT}
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="https://blackout.network/water">
<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#05060a">
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin><link rel="preload" href="/api/water/data" as="fetch" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/bn-refresh.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={mlc}"><link rel="stylesheet" href="/api/water/app.css?v={_v("app.css")}">
<script src="/sitenav.js" defer></script><script src="/bn-refresh.js" defer></script>
<link rel="icon" href="/favicon.ico?v=5" sizes="any"></head>
<body class="wt bn-has-ref"><a class="skip" href="#wt_list">Skip to the list</a>
{sitenav.header_html("")}
<div id="wt_main" role="main">
<section class="wt-map-wrap" aria-label="Map of water treatment status"><div id="wt_map" class="wt-map" role="region" aria-label="Map of boil notices, violations and plant noncompliance. Drag to pan, pinch or scroll to zoom, tap a point for details."></div>
<div class="wt-leg" aria-hidden="true"><span><i class="wt-dot wt-dnd"></i>Do not drink</span><span><i class="wt-dot wt-boil"></i>Boil notice</span><span><i class="wt-dot wt-viol"></i>EPA violation, county</span><span><i class="wt-dot wt-snc"></i>Sewage plant</span></div></section>
<section class="wt-panel" aria-label="Status list">
<div class="wt-head"><div><h1>Water treatment status</h1><p class="wt-sub" id="wt_sub">Loading live data</p></div>{sitenav_ui.refresh_fill_btn("wt_ref")}</div>
<div class="wt-chips" id="wt_chips" role="group" aria-label="Show">{chip_html}</div>
<label class="wt-search"><span class="wt-vh">Search by system, place or state</span><input id="wt_q" type="search" placeholder="Search system, place or state" autocomplete="off" enterkeyhint="search"></label>
<div id="wt_list" class="wt-list" aria-live="polite"><p class="wt-empty">Loading</p></div>
<button type="button" class="wt-more" id="wt_more" hidden>Show more</button>
<div class="wt-src" id="wt_src"></div>
<p class="wt-foot">Research only. BLACKOUT.NETWORK is not an official warning service. Follow your local water utility and health department. Notices come from the agencies named on each item and can change faster than this page updates. "EPA violation" means a compliance finding in EPA's records, not that the water is unsafe to drink today.</p>
<p class="wt-foot wt-credit">{CREDITS}</p>
</section></div>
<script src="/api/signal/maplibre-gl.js?v={mlv}" defer></script><script src="/api/water/app.js?v={_v("app.js")}" defer></script>
</body></html>'''

def handle_get(path, qs=None, headers=None):
    p = (path or "").rstrip("/") or "/"
    if p == "/water": return 200, page(), "text/html"
    if p == "/api/water/data":
        try:
            f = str(((qs or {}).get("fresh") or [""])[0] if isinstance((qs or {}).get("fresh"), list) else (qs or {}).get("fresh") or "").lower() in ("1", "true", "yes")
            return 200, data(force=f), "application/json"
        except Exception as ex: return 503, {"error": "water data unavailable", "detail": type(ex).__name__}
    if p.startswith("/api/water/"):
        n = p[len("/api/water/"):]
        if n in FILES:
            with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}
