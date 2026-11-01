"""⚡ U.S. Energy Grid tab (listed in the main nav since t233; deep link blackout.network/#grid). 2026-10-31, t231.
Status map, local outage view and weather-triggered infrastructure check: gridstatus.py (/api/gridstatus, t234).
Threats to the U.S. power grid: physical attacks on substations/lines, cyber attacks on utilities and ICS/SCADA, energy-sector
vulnerabilities (CISA ICS advisories), blackout risk (ERCOT grid conditions / EEA, large outages, load shedding), and geomagnetic
storms strong enough to stress the grid (NOAA SWPC G3+). Scanner clusters (blackout.db, read-only) are kept when the classifier finds a
power-grid term AND a U.S. anchor (U.S. place / U.S. grid operator / U.S. utility / U.S. coordinates) with no stronger foreign anchor.
Ranks/scores are the scanner's own. Extra feeds (box -> tabfeeds.db): CISA ICS advisories (Energy sector only), NOAA SWPC alerts
(G3+ only), ERCOT grid conditions, The Hacker News (grid-filtered). Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json."""
import re, json
import tabfeeds as T

TAB = "grid"; TITLE = "U.S. Energy Grid"
BRAND = re.compile(r"blackout\.network|blackout network", re.I)
US_GRID = (r"ERCOT|PJM|CAISO|MISO|NYISO|ISO[- ]NE|ISO New England|SPP|Southwest Power Pool|NERC|FERC|TVA|Tennessee Valley Authority|"
    r"Bonneville Power|BPA|WECC|PG&E|PG&amp;E|Pacific Gas (?:and|&) Electric|Con ?Ed(?:ison)?|Duke Energy|Dominion Energy|Xcel Energy|Entergy|"
    r"Southern California Edison|SCE|San Diego Gas|SDG&E|FirstEnergy|Exelon|ComEd|Pepco|BGE|PECO|DTE Energy|DTE|Consumers Energy|CenterPoint|"
    r"Oncor|Georgia Power|Alabama Power|Florida Power|FPL|Duke|AEP|American Electric Power|Ameren|Evergy|PSEG|PPL|Eversource|National Grid US|"
    r"Avangrid|Puget Sound Energy|Portland General|PacifiCorp|Rocky Mountain Power|NV Energy|APS|Arizona Public Service|SRP|Salt River Project|"
    r"LADWP|Austin Energy|CPS Energy|Hawaiian Electric|HECO|Hawaiian Electric|Southern Company|NextEra|Vistra|Constellation|LUMA Energy|PREPA|"
    r"DOE|Department of Energy|CISA|FEMA|Volt Typhoon")
US_GRID_RE = re.compile(r"\b(?:" + US_GRID + r")\b")
STATES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|"
    "Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|"
    "New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
    "Virginia|Washington State|West Virginia|Wisconsin|Wyoming|Puerto Rico|District of Columbia|Washington,? D\\.?C\\.?")
US_CS = re.compile(r"\b(?:U\.S\.A?\.?|USA|US)\b")
US_RE = re.compile(r"\b(?:United States|American|Americans|" + STATES +
    r"|NYC|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|Austin|Seattle|Denver|Atlanta|Miami|Boston|Detroit|"
    r"New Orleans|Las Vegas|Portland|Minneapolis|Baltimore|Charlotte|Nashville|Memphis|Tampa|Orlando|Sacramento|San Francisco|Bay Area|"
    r"Pittsburgh|Cleveland|St\. Louis|Kansas City|Salt Lake|Albuquerque|Tucson|Raleigh|Richmond|Honolulu|Anchorage|Moore County|"
    r"Pentagon|White House|Roosevelt Island|Long Island|Brooklyn|Queens|Bronx|Manhattan|Midwest|Gulf Coast|Pacific Northwest|New England|Appalachia)\b", re.I)
LOC_ABBR = re.compile(r",\s*(?:A[LKZR]|C[AOT]|D[EC]|FL|GA|HI|I[DLNA]|K[SY]|LA|M[EDAINSOT]|N[EVHJMYCD]|O[HKR]|PA|PR|RI|S[CD]|T[NX]|UT|V[TA]|W[AVIY])\b|\bUSA?\b|United States")
FOREIGN = re.compile(r"\b(?:Ukrain\w*|Kyiv|Kiev|Kharkiv|Dnipro|Odesa|Odessa|Zaporizh\w*|Lviv|Russia\w*|Moscow|Belgorod|Gaza|Israel\w*|Lebanon|Iran\w*|"
    r"Cuba\w*|Venezuela\w*|Pakistan\w*|India\w*|Bangladesh\w*|Nigeria\w*|South Africa\w*|Eskom|Iraq\w*|Syria\w*|Yemen\w*|Chile\w*|Ecuador\w*|"
    r"Spain|Spanish|Portugal|France|French|Germany|German|Britain|British|UK|England|Australia\w*|Japan\w*|China|Chinese|Taiwan\w*|Korea\w*|"
    r"Philippin\w*|Vietnam\w*|Indonesia\w*|Andhra|Kenya\w*|Mexic\w*|Canada|Canadian|Ontario|Quebec|Brazil\w*|Argentin\w*|Europe\w*|Baltic|"
    r"Moldova\w*|Poland|Polish|Kosovo|Serbia\w*|Novokuybyshevsk|Samara|Crimea\w*|Donetsk|Luhansk|Kherson|Sumy|Mykolaiv|Belarus\w*)\b")
GRID = re.compile(r"\b(?:power grids?|electric(?:al|ity)? grids?|energy grids?|national grid|grid (?:attack\w*|emergenc\w*|operators?|stress\w*|failures?|"
    r"collapse|reliability|security|conditions|alert|warning|strain\w*|outage\w*|infrastructure)|substations?|power (?:outages?|cuts?|failures?|"
    r"lines?|plants?|stations?|supply|infrastructure|compan\w*|utilit\w*|restored|knocked out)|without (?:power|electricity)|lost power|loss of power|"
    r"customers? (?:without|lost)|blackouts?|brownouts?|rolling (?:blackouts?|outages?)|load[- ]shed\w*|electric(?:al|ity)? (?:utilit\w*|cooperatives?|"
    r"co-?ops?|infrastructure|supply|service|system)|(?:electric|power|energy) utilit\w*|transmission (?:lines?|towers?|grid|system)|high[- ]voltage|"
    r"power transformers?|transformers? (?:fire|explosion|blew|blown|station|failure)|nuclear (?:power )?(?:plants?|reactors?|stations?)|power reactors?|"
    r"hydroelectric|energy emergency alert|EEA\s?[123]|conservation (?:appeal|alert|notice)|energy sector|SCADA|industrial control systems?|"
    r"geomagnetic (?:storm|storms|disturbance)|induced currents|grid fluctuations|utility poles?|power poles?|downed (?:power )?lines|outage map|"
    r"electricity (?:supply|demand|shortage|rationing)|power shortage|without outside (?:power|electricity)|grid power|grid[- ]down)\b", re.I)
G_STRONG = re.compile(r"\b(?:G[345]\b|Kp\s?(?:index )?(?:of )?[789]|K-index of [789]|severe geomagnetic|strong geomagnetic|extreme geomagnetic)", re.I)
KINDS = [
    ("space", "Space weather (G3+)", re.compile(r"geomagnetic|\bG[345]\b|K-index|solar storm|\bCME\b|coronal mass", re.I)),
    ("physical", "Physical attacks on grid assets", re.compile(r"shot|shooting|gunfire|gunshots?|vandal|sabotag|arson|bomb|explosive|intrud|attack\w* on (?:a |the )?(?:power|substation|grid|transformer)|(?:substation|grid|power) attack|drone", re.I)),
    ("cyber", "Cyber & ICS threats to utilities", re.compile(r"cyber|hack|ransomware|malware|SCADA|\bICS\b|industrial control|CVE-|vulnerab|Volt Typhoon|advisory|exploit|intrusion", re.I)),
    ("risk", "Grid emergency & blackout risk", re.compile(r"\bEEA\b|energy emergency|load[- ]shed|rolling|conservation|grid (?:emergency|stress|strain|conditions|alert|warning|reliability)|NERC|ERCOT|PJM|CAISO|MISO|heat ?wave|record demand|shortage", re.I)),
    ("outage", "Major power outages", re.compile(r"outage|without (?:power|electricity)|lost power|blackout|knocked out|downed", re.I)),
]
KIND_LABEL = {k: l for k, l, _ in KINDS}; KIND_LABEL["infra"] = "Grid infrastructure"
US_BOX = [(24.4, 49.5, -125.0, -66.8), (51.0, 71.6, -170.0, -129.9), (18.8, 22.4, -160.5, -154.7), (17.8, 18.6, -67.4, -65.2)]
def _in_us(lat, lon):
    return lat is not None and lon is not None and any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOX)

def _kind(text):
    for k, _, rx in KINDS:
        if rx.search(text): return k
    return "infra"

def classify_text(text, category="", lat=None, lon=None, location="", sources=()):
    t = BRAND.sub(" ", text or "")
    g = [m.group(0) for m in GRID.finditer(t)]
    space = category == "space weather" or "SWPC" in " ".join(sources) or re.search(r"geomagnetic|K-index", t, re.I)
    if space:   # space weather counts only at G3+ (the SWPC G1/G2 boilerplate also says "weak power grid fluctuations")
        s = [m.group(0) for m in G_STRONG.finditer(t)]
        return {"kind": "space", "why": s + ["NOAA SWPC (U.S. grid impact scale)"], "us": "SWPC / U.S."} if s else None
    if not g: return None
    ug = [m.group(0) for m in US_GRID_RE.finditer(t)]
    us = ug + [m.group(0) for r in (US_CS, US_RE) for m in r.finditer(t)] + ([location] if location and LOC_ABBR.search(location) else [])
    fr = [m.group(0) for m in FOREIGN.finditer(t + " " + (location or ""))]
    geo_us = _in_us(lat, lon); geo_far = lat is not None and lon is not None and not geo_us
    adj = re.search(r"\b(?:U\.?S\.?|USA|America'?s?|American|nation'?s|Texas|California)\s+(?:power |electric(?:al)? |energy )?grid", t, re.I)
    if ug or adj: pass                                    # a U.S. grid operator / utility / agency named: U.S. by definition
    elif geo_far: return None                      # coordinates outside the U.S.
    elif fr and not geo_us and len(set(fr)) > len(set(us)): return None   # foreign grid story that merely mentions the U.S.
    elif not us and not geo_us: return None
    return {"kind": _kind(t), "why": list(dict.fromkeys(g + ug + ([adj.group(0)] if adj else []) + us))[:8], "us": (ug or ([adj.group(0)] if adj else []) or us or ["U.S. coordinates"])[0]}

def _snip(text, words, n=220):
    t = re.sub(r"\s+", " ", text or "").strip()
    i = min([j for j in (t.find(w) for w in words) if j >= 0] or [0]); a = max(0, i - n // 3)
    return ("…" if a else "") + t[a:a + n] + ("…" if a + n < len(t) else "")

def classify(d):
    head = (d["title"] or "") + "\n" + (d["brief"] or "")
    m = classify_text(head, d["category"], d["lat"], d["lon"], d["location"] or "", d["_srcs"])
    if m: m["match"] = _snip(head, m["why"]); return m
    for u in d["_text"].split("\n")[2:]:      # member posts: each must stand on its own (grid term + U.S. anchor in the same post)
        m = classify_text(u, d["category"], None, None, d["location"] or "", d["_srcs"])
        if m and m["kind"] != "space": m["match"] = _snip(u, m["why"]); return m
    return None

# ------------------------------------------------------------------ extra feeds (box)
def f_cisa_ics():
    raw = T.rss("https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml", limit=400)
    out = []
    for x in raw:
        body = T.clean(x["summary"], 20000)
        sec = re.search(r"CRITICAL INFRASTRUCTURE SECTORS?:?\s*([^\n]{0,200}?)(?:COUNTRIES|DEPLOYED|COMPANY HEADQUARTERS|$)", body, re.I)
        sectors = sec.group(1).strip(" :") if sec else ""
        if not re.search(r"\bEnergy\b", sectors, re.I): continue
        dep = re.search(r"COUNTRIES/AREAS DEPLOYED:?\s*([^\n]{0,80}?)(?:COMPANY HEADQUARTERS|$)", body, re.I)
        cvss = re.search(r"CVSS v[34][^0-9]{0,30}(\d{1,2}\.\d)", body)
        summ = (f"Sectors: {sectors[:120]}" + (f" · Deployed: {dep.group(1).strip()[:60]}" if dep else "") + (f" · CVSS {cvss.group(1)}" if cvss else "")
                + " · " + re.sub(r"^.*?(?:EXECUTIVE SUMMARY|OVERVIEW)\s*", "", body, flags=re.I)[:300])
        out.append(dict(x, summary=summ, kind="cyber", why=["CISA ICS advisory", "Energy sector"], extra={"location": "U.S. energy sector (CISA)"}))
    return out, f"{len(raw)} advisories in feed; {len(out)} list the Energy sector"
def f_swpc():
    data = json.loads(T.http("https://services.swpc.noaa.gov/products/alerts.json"))
    out = []
    for a in data:
        msg = a.get("message") or ""
        m = re.search(r"NOAA Scale:\s*(G[345])\b[^\r\n]*", msg) or re.search(r"K-index of ([789])", msg)
        if not m: continue
        head = next((ln.strip() for ln in msg.splitlines() if re.match(r"(ALERT|WARNING|WATCH|SUMMARY|EXTENDED WARNING|CANCEL)", ln.strip())), a.get("product_id", ""))
        sc = re.search(r"NOAA Scale:\s*(G[1-5][^\r\n]*)", msg)
        imp = re.search(r"Induced Currents\s*-\s*([^\r\n]+)", msg)
        t = T.pdate((a.get("issue_datetime") or "").replace(" ", "T")[:19] + "Z")
        out.append({"id": f"{a.get('product_id')}|{a.get('issue_datetime')}", "title": f"NOAA SWPC: {head}" + (f" ({sc.group(1).strip()})" if sc else ""),
                    "url": "https://www.swpc.noaa.gov/products/alerts-watches-and-warnings", "summary": (imp.group(1) if imp else msg[:300]),
                    "published": t, "kind": "space", "why": [m.group(0)], "extra": {"location": "U.S. grid (geomagnetic)"}})
    return out, f"{len(data)} SWPC products in feed; {len(out)} at G3 or stronger"
def f_ercot():
    d = json.loads(T.http("https://www.ercot.com/api/1/services/read/dashboards/daily-prc.json"))
    cc = d.get("current_condition") or {}
    lvl, state = int(cc.get("eea_level") or 0), (cc.get("state") or "").lower()
    note = f"now: {cc.get('title', '?')} (EEA {lvl}, reserves {cc.get('prc_value', '?')} MW, updated {d.get('lastUpdated', '?')})"
    if lvl == 0 and state in ("normal", ""): return [], note
    t = T.pdate((d.get("lastUpdated") or "").replace(" ", "T"))
    return [{"id": f"ercot|{(t or '')[:13]}|{lvl}|{state}", "title": f"ERCOT grid: {cc.get('title', state)} (EEA level {lvl})",
             "url": "https://www.ercot.com/gridmktinfo/dashboards", "summary": f"{cc.get('condition_note', '')} Physical responsive capability {cc.get('prc_value', '?')} MW.",
             "published": t, "kind": "risk", "why": [f"EEA {lvl}", state], "extra": {"location": "Texas (ERCOT)"}}], note
def f_thn():
    raw = T.rss("https://feeds.feedburner.com/TheHackersNews")
    out = []
    for x in raw:
        txt = x["title"] + "\n" + T.clean(x["summary"], 2000)
        m = classify_text(txt)
        if m and m["kind"] != "space": out.append(dict(x, kind=m["kind"], why=m["why"]))
    return out, f"{len(raw)} in feed; {len(out)} matched the U.S. grid classifier"

FEEDS = {
    "cisa_ics": {"label": "CISA ICS advisories (Energy sector)", "url": "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml", "fn": f_cisa_ics, "official": True, "category": "cyber"},
    "swpc": {"label": "NOAA SWPC alerts (G3+)", "url": "https://services.swpc.noaa.gov/products/alerts.json", "fn": f_swpc, "official": True, "category": "space weather"},
    "ercot": {"label": "ERCOT grid conditions", "url": "https://www.ercot.com/api/1/services/read/dashboards/daily-prc.json", "fn": f_ercot, "official": True, "category": "grid"},
    "thn": {"label": "The Hacker News (grid-filtered)", "url": "https://feeds.feedburner.com/TheHackersNews", "fn": f_thn, "official": False, "category": "cyber"},
}

def handle_get(path, qs):
    if path.startswith("/api/grid/"): return T.serve_static(path[len("/api/grid/"):])
    if path == "/api/grid":
        code, body = T.page(TAB, classify, FEEDS, qs, TITLE)
        if code == 200: body["kinds"] = KIND_LABEL
        return code, body
    return 404, {"error": "not found"}
