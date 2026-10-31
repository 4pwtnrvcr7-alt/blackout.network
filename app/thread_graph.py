#!/usr/bin/env python3
"""The Thread -- full connected graph (blackout.network).

Read-only builder: collects nodes from every dataset the site already ingests (alerts/clusters, heat-map geocodes, story arcs,
broadcasts, live-stream segments, aviation watch, private-jet airports, solar & seismic, political markets, network status,
sources registry) plus a broader pull of free public feeds over 30 days (USGS, tsunami.gov, NOAA SWPC, GDACS, NASA EONET,
ReliefWeb, NWS CAP, WHO DON, CDC outbreaks, CIDRAP, CISA KEV + advisories, configured Telegram public previews).
External items live only in thread_cache/ (never injected into the scanner's alerts or The Wire). Output: thread_graph.json.

Every edge is grounded and carries a type + detail string (the reason shown on hover/click):
  item->source, item->category, item->entity (exact dictionary match in the item's own text, or the heat-map geocoder's result),
  place->country (GeoNames), country<->country (GeoNames neighbours), item->story (The Thread's story arcs), story<->story (arcs.py
  shared terms), item<->item same story (title overlap, different sources, <=48 h), quake<->quake (<=300 km and <=7 days),
  item<->item nearby (geolocated, <=100 km and <=72 h). Orphans are dropped. Mirror copies (same URL) are merged.
Never modifies scanner.py / scoring / push.py / jets.py / aviation_watch.py, never writes any *.db (all opened mode=ro).

Usage: python3 thread_graph.py build | loop | stats      (HTTP: /api/thread_graph, /api/thread_graph/app.js|app.css)"""
import os, re, sys, json, time, math, sqlite3, hashlib, html, urllib.request, urllib.error, gzip
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "thread_graph.json")
CACHE = os.path.join(BASE, "thread_cache")
STATIC = os.path.join(BASE, "thread_static")
WINDOW_D = 30
UA = "blackout.network thread-graph/1.0 (+https://blackout.network; read-only, cached)"
LOOP_S = int(os.environ.get("BN_THREAD_GRAPH_S", "1800"))
FILES = {"app.js": "application/javascript", "app.css": "text/css"}

# ------------------------------------------------------------------ HTTP (box + Render): serve the prebuilt graph and the front end
def handle_get(path, qs):
    if path == "/api/thread_graph":
        if not os.path.exists(OUT): return 503, {"error": "graph not built yet"}
        with open(OUT, "rb") as f: return 200, f.read()
    if path.startswith("/api/thread_graph/"):
        name = path.rsplit("/", 1)[-1]
        if name in FILES:
            with open(os.path.join(STATIC, name), "rb") as f: return 200, f.read(), FILES[name]
    return 404, {"error": "not found"}

# ------------------------------------------------------------------ helpers
def now(): return datetime.now(timezone.utc)
def parse_t(s):
    if s is None or s == "": return None
    if isinstance(s, (int, float)): return datetime.fromtimestamp(s / (1000 if s > 1e11 else 1), timezone.utc)
    s = str(s).strip()
    if re.fullmatch(r"\d{9,13}", s): return parse_t(int(s))
    for f in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M %z"):
        try:
            d = datetime.strptime(s, f); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception: pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00")); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: return None
def strip(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
def ro(name):
    c = sqlite3.connect(f"file:{os.path.join(BASE, name)}?mode=ro", uri=True, timeout=20); c.row_factory = sqlite3.Row; return c
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(x)))
def norm_url(u):
    u = (u or "").strip()
    return re.sub(r"^https?://(www\.)?", "", u).split("#")[0].rstrip("/").lower()
STATS = {"fetch": {}}
def _log(k, **v): STATS["fetch"].setdefault(k, {}).update(v)

def fetch(key, url, ttl_s, binary=False, timeout=40):
    """GET with an on-disk cache (thread_cache/raw_<key>); stale cache is used if a refresh fails."""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "raw_" + re.sub(r"[^A-Za-z0-9_.-]", "_", key))
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl_s:
        b = open(p, "rb").read()
    else:
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}), timeout=timeout)
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
            open(p + ".tmp", "wb").write(b); os.replace(p + ".tmp", p)
        except Exception as ex:
            if os.path.exists(p): b = open(p, "rb").read(); STATS.setdefault("stale", []).append(f"{key}: {str(ex)[:80]}")
            else: raise
    return b if binary else b.decode("utf-8", "replace")

def local(tag): return tag.rsplit("}", 1)[-1]
def rss_items(text):
    raw = text.encode() if isinstance(text, str) else text
    if raw.startswith(b"\xef\xbb\xbf"): raw = raw[3:]
    out = []
    for el in ET.fromstring(raw).iter():
        if local(el.tag) in ("item", "entry"):
            d = {}
            for c in el.iter():
                if c is el: continue
                k = local(c.tag)
                if k == "link" and c.get("href"): d.setdefault("link", c.get("href"))
                else:
                    d.setdefault(k, ((c.text or "") if len(c) == 0 else "".join(c.itertext())).strip())
            out.append(d)
    return out

# ------------------------------------------------------------------ privacy: the same scrub rules render_sync applies, plus no home-area local items
try:
    sys.path.insert(0, BASE); import render_rules as _R
    SCRUB_ROW_RE, SCRUB_REPLACE = _R.SCRUB_ROW_RE, _R.SCRUB_REPLACE
except Exception:
    SCRUB_ROW_RE, SCRUB_REPLACE = re.compile(r"Lake Mary|\b3277[1-3]\b|\b32746\b|Sanford|near_matt", re.I), []
LOCAL_RE = re.compile(r"Lake Mary|Sanford|Seminole County|Volusia|Orange County,? (FL|Fla)|Osceola|Orlando|Central Florida|Kissimmee|Daytona|Deltona|"
                      r"Altamonte|Oviedo|Winter Park|Apopka|DeLand|WESH|WKMG|Spectrum (News )?13|WFTV|FOX 35|Lake County,? (FL|Fla)", re.I)
def private(*texts):
    s = " ".join(str(t) for t in texts if t)
    return bool(SCRUB_ROW_RE.search(s) or LOCAL_RE.search(s))
def clean(s):
    s = s or ""
    for a, b in SCRUB_REPLACE: s = s.replace(a, b)
    return s

# ------------------------------------------------------------------ entity dictionaries (deterministic regex matches on the item's own text)
HAZARDS = {
 "earthquake": r"earthquakes?|quakes?|seismic|aftershocks?|tremors?", "tsunami": r"tsunamis?", "volcano": r"volcan\w*|eruptions?|erupt\w*|ash plume",
 "flood": r"floods?|flooding|flash floods?", "wildfire": r"wildfires?|bushfires?|forest fires?|red flag warning",
 "tropical cyclone": r"hurricanes?|typhoons?|tropical (storm|cyclone|depression)s?|cyclones?",
 "severe storm": r"thunderstorms?|severe storms?|blizzards?|winter storms?|ice storms?|storm warning|gale warning|hail", "tornado": r"tornado(es)?",
 "landslide": r"landslides?|mudslides?", "drought": r"droughts?", "extreme heat": r"heat ?waves?|excessive heat|extreme heat", "extreme cold": r"extreme cold|freeze warning|wind chill",
 "geomagnetic storm": r"geomagnetic|k-index|g[1-5] storm|aurora", "solar flare": r"solar flares?|x-ray (flux|event)|radio blackout",
 "solar radiation": r"proton (event|flux)|radiation storm", "cme": r"coronal mass ejection|cmes?",
 "disease outbreak": r"outbreaks?|epidemic|pandemic", "cyberattack": r"cyber ?attacks?|hack(ed|ers?|ing)?|data breach(es)?|ddos|malware|phishing",
 "ransomware": r"ransomware", "software vulnerability": r"cve-\d{4}-\d+|vulnerabilit(y|ies)|zero-day|0-day|exploited",
 "airstrike": r"air ?strikes?|bombing|bombard\w*", "missile attack": r"missiles?|ballistic|icbm", "drone attack": r"drones?|uavs?|shahed",
 "explosion": r"explosions?|blasts?|exploded", "shooting": r"shootings?|gunman|gunfire|shot dead", "terrorism": r"terror\w*|suicide bomb\w*",
 "protest / unrest": r"protests?|protesters?|riots?|unrest", "coup": r"coups?|junta", "nuclear": r"nuclear|radioactive|uranium|enrichment",
 "chemical": r"chemical (attack|leak|spill)|toxic (gas|spill)|hazmat", "power outage": r"power outages?|blackouts?|power cuts?|grid failure|load.?shedding",
 "internet outage": r"internet (outage|shutdown|blackout)|outages?", "aviation incident": r"plane crash|air ?crash|emergency landing|mayday|squawk ?7700",
 "maritime incident": r"tankers?|cargo ships?|shipping lanes?|vessels? (seized|attacked|sank|hit)", "evacuation": r"evacuat\w+", "ceasefire": r"cease-?fire|truce",
 "sanctions": r"sanctions?", "election": r"elections?|ballots?", "ufo / uap": r"ufos?|uaps?|unidentified (aerial|anomalous)",
 "famine / food crisis": r"famine|food (crisis|insecurity)", "displacement": r"refugees?|displaced|displacement",
}
PATHOGENS = {
 "Ebola": r"ebola|bundibugyo|sudan virus", "Marburg": r"marburg", "H5N1 avian influenza": r"h5n\d|bird flu|avian (influenza|flu)", "Mpox": r"mpox|monkeypox",
 "Measles": r"measles", "Cholera": r"cholera", "Dengue": r"dengue", "Nipah": r"nipah", "Polio": r"polio|poliovirus", "Anthrax": r"anthrax", "Plague": r"plague",
 "COVID-19": r"covid(-19)?|sars-cov-2|coronavirus", "MERS": r"mers|mers-cov", "Rift Valley fever": r"rift valley fever", "Yellow fever": r"yellow fever", "Lassa fever": r"lassa( fever)?",
 "Chikungunya": r"chikungunya", "Zika": r"zika", "Oropouche": r"oropouche", "Diphtheria": r"diphtheria", "Meningitis": r"meningitis|meningococcal",
 "Hepatitis": r"hepatitis", "Legionnaires' disease": r"legionella|legionnaires'?", "Salmonella": r"salmonella", "E. coli": r"e\. ?coli|stec", "Rabies": r"rabies",
 "West Nile virus": r"west nile", "CCHF": r"crimean-congo|cchf", "Tuberculosis": r"tuberculosis", "Malaria": r"malaria", "Influenza": r"influenza|flu",
 "Listeria": r"listeria", "Hantavirus": r"hantavirus", "Pertussis": r"pertussis|whooping cough", "Candida auris": r"candida auris|c\. auris",
 "Unknown illness": r"mystery (illness|disease)|unknown (illness|disease)|undiagnosed illness", "Botulism": r"botulism", "Typhoid": r"typhoid", "Leptospirosis": r"leptospirosis",
}
ACTORS = {
 "NATO": r"nato", "United Nations": r"united nations|unsc|unhcr|unicef|ocha|un security council|un chief", "World Health Organization": r"world health organi[sz]ation",
 "IAEA": r"iaea", "European Union": r"european union|european commission", "Hamas": r"hamas", "Hezbollah": r"hezbollah|hizbullah", "Houthis": r"houthis?|ansar allah",
 "IDF": r"idf|israel defen[cs]e forces", "IRGC": r"irgc|revolutionary guards?", "Wagner / Africa Corps": r"wagner group|africa corps", "Taliban": r"taliban", "ISIS": r"isis|islamic state|isil|daesh",
 "al-Shabaab": r"al-?shabaab", "Boko Haram": r"boko haram|iswap", "RSF (Sudan)": r"rapid support forces", "M23": r"m23", "Kremlin": r"kremlin", "Pentagon": r"pentagon",
 "FBI": r"fbi", "CIA": r"cia", "DHS": r"dhs|homeland security", "FEMA": r"fema", "CDC": r"cdc", "NOAA": r"noaa", "NASA": r"nasa", "SpaceX": r"spacex|starlink",
 "IMF": r"imf", "OPEC": r"opec\+?", "Federal Reserve": r"federal reserve", "ECB": r"ecb", "White House": r"white house", "US Congress": r"congress|senate|house of representatives",
 "Donald Trump": r"trump", "Vladimir Putin": r"putin", "Volodymyr Zelensky": r"zelensk[yi]+", "Benjamin Netanyahu": r"netanyahu", "Xi Jinping": r"xi jinping", "Ali Khamenei": r"khamenei",
 "Kim Jong Un": r"kim jong[- ]un", "Narendra Modi": r"modi", "Recep Tayyip Erdogan": r"erdo[gğ]an", "Elon Musk": r"musk", "JD Vance": r"vance", "Pete Hegseth": r"hegseth", "Marco Rubio": r"rubio",
 "Microsoft": r"microsoft", "Google": r"google", "Apple": r"apple", "Cisco": r"cisco", "Fortinet": r"fortinet|fortigate|fortios", "Ivanti": r"ivanti",
 "Palo Alto Networks": r"palo alto networks|pan-os", "Citrix": r"citrix|netscaler", "Oracle": r"oracle", "VMware": r"vmware", "Cloudflare": r"cloudflare", "AWS": r"aws|amazon web services",
 "Red Cross / Red Crescent": r"red cross|red crescent|ifrc|icrc", "Africa CDC": r"africa cdc",
}
INFRA = {
 "Strait of Hormuz": r"hormuz", "Red Sea": r"red sea", "Bab el-Mandeb": r"bab[- ]el[- ]mandeb", "Suez Canal": r"suez", "Black Sea": r"black sea", "Taiwan Strait": r"taiwan strait",
 "South China Sea": r"south china sea", "Panama Canal": r"panama canal", "Zaporizhzhia NPP": r"zaporizh\w+ (nuclear|npp|plant)|znpp", "Chernobyl": r"chornobyl|chernobyl", "Fukushima": r"fukushima",
 "Power grid": r"power grid|substations?|power plants?|power stations?", "Pipelines": r"pipelines?|nord stream", "Undersea cables": r"(undersea|subsea|submarine) cables?",
 "Ports": r"ports?|harbou?rs?", "Airports": r"airports?", "Dams": r"dams?", "Railways": r"railways?|derail\w+", "Refineries / oil": r"refiner(y|ies)|oil (field|depot|terminal|facility)",
 "Satellites / GPS": r"satellites?|gps (jamming|outage|interference)|gnss", "Bridges": r"bridges?", "Hospitals": r"hospitals?", "Water supply": r"water (supply|treatment|shortage)",
 "Kerch Bridge": r"kerch|crimean bridge", "Strategic bombers": r"b-52s?|b-2s?|tu-95s?|tu-160s?", "Aircraft carriers": r"aircraft carriers?|carrier strike group",
}
# Case-sensitive acronyms (avoid "who"/"us"/"cia" in ordinary words): matched against the original text without re.I
CASED = {"actor": {"World Health Organization": r"WHO", "United Nations": r"UN", "European Union": r"EU", "CIA": r"CIA", "IMF": r"IMF", "ECB": r"ECB", "M23": r"M23", "DHS": r"DHS",
                   "FBI": r"FBI", "CDC": r"CDC", "NASA": r"NASA", "NOAA": r"NOAA", "FEMA": r"FEMA", "AWS": r"AWS", "IDF": r"IDF", "IRGC": r"IRGC", "NATO": r"NATO", "Federal Reserve": r"Fed"},
         "pathogen": {"MERS": r"MERS", "Tuberculosis": r"TB"}, "hazard": {"cme": r"CMEs?"}}
UNCASED_SKIP = {("actor", "CIA"), ("actor", "IMF"), ("actor", "ECB"), ("actor", "M23"), ("actor", "DHS"), ("actor", "FBI"), ("actor", "CDC"), ("actor", "NASA"),
                ("actor", "NOAA"), ("actor", "FEMA"), ("actor", "AWS"), ("actor", "IDF"), ("actor", "IRGC"), ("actor", "NATO"), ("pathogen", "MERS"), ("hazard", "cme"),
                ("actor", "Apple"), ("actor", "Oracle"), ("actor", "Narendra Modi"), ("actor", "JD Vance"), ("actor", "Elon Musk")}
CASED["actor"].update({"Apple": r"Apple", "Oracle": r"Oracle", "Narendra Modi": r"Modi", "JD Vance": r"Vance", "Elon Musk": r"Musk"})
B0, B1 = r"(?<![\w-])(?:", r")(?![\w-])"

class Dict:
    """Entity dictionary: match(text) -> [(kind, name, matched text)], first hit per entity; geography from the site's GeoNames data (heatmap_data/)."""
    def __init__(self):
        self.groups = []
        for kind, d in (("hazard", HAZARDS), ("pathogen", PATHOGENS), ("actor", ACTORS), ("infrastructure", INFRA)):
            for name, rx in d.items():
                if (kind, name) not in UNCASED_SKIP: self.groups.append((kind, name, re.compile(B0 + rx + B1, re.I)))
        for kind, d in CASED.items():
            for name, rx in d.items(): self.groups.append((kind, name, re.compile(B0 + rx + B1)))
        hd = os.path.join(BASE, "heatmap_data")
        self.countries = json.load(open(os.path.join(hd, "countries.json")))
        AMBIG = {"Georgia", "Jordan", "Chad", "Guinea", "Niger", "Congo", "Dominica", "Turkey", "Mali", "Oman", "Peru", "Cuba", "Togo", "Jersey"}
        names = {}
        for cc, c in self.countries.items():
            for n in [c["name"]] + (c.get("ne_names") or []):
                if n and len(n) >= 4 and n not in AMBIG: names[n] = cc
        extra = {"US": ["U.S.", "USA", "United States", "American", "Americans"], "GB": ["UK", "U.K.", "Britain", "British"], "RU": ["Russia", "Russian", "Russians", "Moscow"],
                 "UA": ["Ukraine", "Ukrainian", "Ukrainians", "Kyiv", "Kiev"], "IL": ["Israel", "Israeli", "Israelis"], "IR": ["Iran", "Iranian", "Tehran"], "CN": ["China", "Chinese", "Beijing"],
                 "PS": ["Gaza", "Palestinian", "Palestinians", "West Bank"], "LB": ["Lebanon", "Lebanese", "Beirut"], "SY": ["Syria", "Syrian", "Damascus"], "YE": ["Yemen", "Yemeni"],
                 "IQ": ["Iraq", "Iraqi", "Baghdad"], "TR": ["Türkiye", "Turkish", "Ankara", "Istanbul"], "IN": ["India", "Indian"], "PK": ["Pakistan", "Pakistani"], "AF": ["Afghanistan", "Afghan", "Kabul"],
                 "KP": ["North Korea", "North Korean", "Pyongyang", "DPRK"], "KR": ["South Korea", "South Korean", "Seoul"], "TW": ["Taiwan", "Taiwanese", "Taipei"], "JP": ["Japan", "Japanese", "Tokyo"],
                 "VE": ["Venezuela", "Venezuelan", "Caracas"], "MX": ["Mexico", "Mexican"], "CD": ["DR Congo", "DRC", "Democratic Republic of the Congo", "Congolese", "Kinshasa"],
                 "SD": ["Sudan", "Sudanese", "Khartoum", "Darfur", "El Fasher"], "SS": ["South Sudan"], "ET": ["Ethiopia", "Ethiopian"], "SO": ["Somalia", "Somali"], "NG": ["Nigeria", "Nigerian"],
                 "FR": ["France", "French", "Paris"], "DE": ["Germany", "German", "Berlin"], "PL": ["Poland", "Polish", "Warsaw"], "SA": ["Saudi Arabia", "Saudi"], "EG": ["Egypt", "Egyptian", "Cairo"],
                 "PH": ["Philippines", "Philippine", "Filipino", "Manila"], "ID": ["Indonesia", "Indonesian", "Jakarta"], "BR": ["Brazil", "Brazilian"], "CA": ["Canada", "Canadian"], "AU": ["Australia", "Australian"],
                 "BY": ["Belarus", "Belarusian", "Minsk"], "QA": ["Qatar", "Qatari", "Doha"], "AE": ["UAE", "Emirati", "Dubai", "Abu Dhabi"], "CO": ["Colombia", "Colombian"], "HT": ["Haiti", "Haitian"],
                 "MM": ["Myanmar", "Burma"], "CU": ["Cuban", "Havana"], "PE": ["Peruvian"], "ML": ["Malian", "Bamako"], "NE": ["Nigerien", "Niamey"], "CL": ["Chilean", "Santiago de Chile"],
                 "TD": ["Chadian", "N'Djamena"], "JO": ["Jordanian", "Amman"], "GE": ["Tbilisi", "Republic of Georgia"], "OM": ["Omani", "Muscat"]}
        for cc, ns in extra.items():
            if cc in self.countries:
                for n in ns: names[n] = cc
        STOP = {"Mobile", "Reading", "Split", "Nice", "Bath", "Bar", "Male", "Lima", "Santiago", "Most", "Kota", "Puebla", "Valencia", "Victoria", "Hamilton", "Birmingham", "Columbus", "Phoenix"}
        self.cities = {}
        for r in json.load(open(os.path.join(hd, "cities.json"))):
            nm, la, lo, cc, a1, pop = r[0], r[2], r[3], r[4], r[5], r[6]
            if pop and pop >= 1_000_000 and len(nm) >= 4 and nm not in STOP and nm not in names and nm.isascii():
                self.cities.setdefault(nm, (cc, la, lo, a1))
        allg = [(n, ("country", cc)) for n, cc in names.items()] + [(n, ("city", n)) for n in self.cities]
        allg.sort(key=lambda x: -len(x[0]))
        self.geo_map = {n: v for n, v in allg}
        self.geo_rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n, _ in allg) + r")(?![\w-])")   # case-sensitive: proper nouns only
    def match(self, text):
        out, seen = [], set()
        if not text: return out
        for m in self.geo_rx.finditer(text):
            s = m.group(1); kind, v = self.geo_map.get(s, (None, None))
            if kind and (kind, v) not in seen: seen.add((kind, v)); out.append((kind, v, s))
        for kind, name, rx in self.groups:
            if (kind, name) in seen: continue
            m = rx.search(text)
            if m: seen.add((kind, name)); out.append((kind, name, m.group(0)))
        return out

# ------------------------------------------------------------------ graph container
class G:
    def __init__(self): self.nodes = {}; self.edges = {}; self.url_ix = {}
    def node(self, key, typ, label, **kw):
        n = self.nodes.get(key)
        if n is None: n = {"k": key, "y": typ, "l": (label or "")[:220]}; self.nodes[key] = n
        for a, b in kw.items():
            if b not in (None, "", [], {}): n.setdefault(a, b)
        return n
    def edge(self, a, b, typ, detail=""):
        if a == b or a not in self.nodes or b not in self.nodes: return
        k = (a, b, typ) if a < b else (b, a, typ)
        if k not in self.edges: self.edges[k] = (a, b, typ, (detail or "")[:160])
    def has_url(self, u): return self.url_ix.get(norm_url(u)) if u else None
    def reg_url(self, u, key):
        if u and len(norm_url(u)) > 12: self.url_ix.setdefault(norm_url(u), key)

def ts(d): return int(d.timestamp()) if d else None
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def src_key(name): return "src:" + name.lower()
def add_source(g, name, group, url=None): return g.node(src_key(name), "source", name, d=group, u=url)["k"]
def cat_key(c): return "cat:" + (c or "other")
def add_cat(g, k, c):
    if c: g.edge(k, g.node(cat_key(c), "category", c)["k"], "category", c)

def ent(g, D, kind, name):
    if kind == "country":
        c = D.countries.get(name) or {}; lab = c.get("label") or [None, None]
        return g.node("cc:" + name, "country", c.get("name") or name, lat=lab[0], lon=lab[1])["k"]
    if kind == "city":
        cc, la, lo, a1 = D.cities[name]
        k = g.node("city:" + name, "city", name, lat=la, lon=lo)["k"]
        if cc in D.countries: g.edge(k, ent(g, D, "country", cc), "located_in", f"GeoNames: {name} is in {D.countries[cc]['name']}")
        return k
    return g.node(kind[:3] + ":" + name.lower(), kind, name)["k"]

def link_text(g, D, k, text):
    hits = D.match(text)
    for kind, name, hit in hits: g.edge(k, ent(g, D, kind, name), "mentions", hit)
    return hits

# ------------------------------------------------------------------ site datasets (all read-only)
def site_alerts(g, D, cutoff):
    db = ro("blackout.db"); n = 0
    geo = {r["id"]: r for r in ro("geo.db").execute("SELECT * FROM geo WHERE located=1")}
    al = {}
    for r in db.execute("SELECT cluster_id, source, family, source_url, title FROM alerts"): al.setdefault(r["cluster_id"], []).append(r)
    for r in db.execute("SELECT * FROM clusters WHERE first_seen >= ? ORDER BY first_seen DESC", (iso(cutoff),)):
        title = clean(r["title"]); mem = al.get(r["cluster_id"], [])
        if private(title, r["location"], r["brief"], " ".join(m["title"] or "" for m in mem[:6])): continue
        t = parse_t(r["event_time"]) or parse_t(r["first_seen"])
        if not t or t > now() + timedelta(hours=6) or t < cutoff - timedelta(days=5): t = parse_t(r["first_seen"])
        try: links = json.loads(r["links"] or "[]")
        except Exception: links = []
        url = (links[0].get("url") if links else None) or (mem[0]["source_url"] if mem else None)
        k = "c:" + r["cluster_id"]; gg = geo.get(r["cluster_id"])
        g.node(k, "item", title, d="The Wire (alerts)", c=r["category"], t=ts(t), u=url, rank=r["rank"], nsrc=r["n_families"],
               lat=(gg["lat"] if gg else r["lat"]), lon=(gg["lon"] if gg else r["lon"])); n += 1
        for m in mem: g.reg_url(m["source_url"], k)
        for l in links: g.reg_url(l.get("url"), k)
        add_cat(g, k, r["category"])
        seen = set()
        for m in mem:
            s = m["source"] or "?"
            if s.startswith("Google News") and m["family"]: s = m["family"]
            if s not in seen: seen.add(s); g.edge(k, add_source(g, s, "The Wire sources"), "source", "")
        link_text(g, D, k, " | ".join([title] + [m["title"] for m in mem[:8] if m["title"] and not private(m["title"])]))
        if gg and not private(gg["place"]):   # heat-map geocoder (geo.db, GeoNames gazetteer)
            det = f'{gg["place"]} · {gg["method"]}, {gg["confidence"]} confidence'
            ck = ent(g, D, "country", gg["country"]) if gg["country"] in D.countries else None
            if ck: g.edge(k, ck, "geocoded", det)
            if gg["admin1_code"] and gg["admin1"] and gg["precision"] != "country":
                ak = g.node("a1:" + gg["admin1_code"], "region", f'{gg["admin1"]}, {gg["country_name"] or gg["country"]}')["k"]
                g.edge(k, ak, "geocoded", det)
                if ck: g.edge(ak, ck, "located_in", "GeoNames admin-1 " + gg["admin1_code"])
    _log("site: The Wire alert clusters (blackout.db) + heat-map geocodes (geo.db)", items=n, geocoded=len(geo))

def site_arcs(g):
    try: A = json.load(urllib.request.urlopen("http://127.0.0.1:8787/api/arcs?window=30d", timeout=120))["arcs"]
    except Exception as ex: _log("site: The Thread story arcs (arcs.py)", error=str(ex)[:120]); return
    n = 0
    for a in A:
        mem = [u["cluster_id"] for u in a.get("updates", []) if "c:" + u["cluster_id"] in g.nodes]
        if not mem or private(a["title"]): continue
        k = "arc:" + a["id"]
        g.node(k, "story", clean(a["title"]), d="The Thread stories", c=a.get("category"), t=ts(parse_t(a.get("latest"))), u="#thread/" + a["id"],
               sev=a.get("severity"), nsrc=a.get("n_sources")); n += 1
        for c in mem: g.edge("c:" + c, k, "story", f'{a["n_updates"]} updates · {a["n_sources"]} sources')
    for a in A:
        for c in a.get("connections") or []: g.edge("arc:" + a["id"], "arc:" + c["arc"], "story_link", "shared: " + ", ".join(c.get("shared") or []))
    _log("site: The Thread story arcs (arcs.py, 30d)", items=n)

def site_quakes(g, D):
    n = 0
    for r in ro("solar_seismic.db").execute("SELECT * FROM quakes"):
        if g.has_url(r["url"]):
            k0 = g.has_url(r["url"]); g.nodes[k0].setdefault("mag", r["mag"]); g.nodes[k0].setdefault("lat", r["lat"]); g.nodes[k0].setdefault("lon", r["lon"]); continue
        if private(r["place"]): continue
        k = "q:" + r["id"]
        g.node(k, "item", f'M{r["mag"]} – {r["place"]}', d="Solar & Seismic", c="natural disaster", t=ts(parse_t(r["t"])), u=r["url"], lat=r["lat"], lon=r["lon"], mag=r["mag"])
        g.reg_url(r["url"], k); g.edge(k, add_source(g, "USGS", "USGS earthquakes"), "source", ""); add_cat(g, k, "natural disaster")
        g.edge(k, ent(g, D, "hazard", "earthquake"), "mentions", "USGS earthquake event"); link_text(g, D, k, r["place"] or "")
        if r["tsunami"]: g.edge(k, ent(g, D, "hazard", "tsunami"), "mentions", "USGS tsunami flag = 1")
        n += 1
    _log("site: Solar & Seismic quakes (solar_seismic.db)", items=n)

SWPC_RX = re.compile(r"(EXTENDED WARNING|WARNING|ALERT|WATCH|SUMMARY|CANCEL \w+)[:\s]+([^\n]+)")
def swpc_title(msg, pid):
    m = SWPC_RX.search(msg or "")
    return ("SWPC " + m.group(1).title() + ": " + m.group(2).strip()) if m else "SWPC product " + (pid or "")
def site_swpc(g, D):
    n = 0
    for r in ro("solar_seismic.db").execute("SELECT * FROM swpc_alerts"):
        t = parse_t(r["issued"]); k = "sw:" + (r["product_id"] or "") + ":" + (iso(t) if t else r["id"])
        g.node(k, "item", swpc_title(r["message"], r["product_id"]), d="Solar & Seismic", c="space weather", t=ts(t),
               u="https://www.swpc.noaa.gov/products/alerts-watches-and-warnings", text=(r["message"] or "")[:500])
        g.edge(k, add_source(g, "NOAA SWPC", "NOAA SWPC"), "source", ""); add_cat(g, k, "space weather"); link_text(g, D, k, r["message"] or ""); n += 1
    _log("site: Solar & Seismic SWPC alerts (solar_seismic.db)", items=n)

def site_broadcasts(g, D, cutoff):
    n = 0
    for r in ro("broadcasts.db").execute("SELECT * FROM clips WHERE published >= ?", (iso(cutoff),)):
        if private(r["source"], r["title"], r["text"]) or "local" in (r["source"] or "").lower(): continue
        txt = (r["title"] or "") + " | " + (r["text"] or "")
        if not D.match(txt): continue
        lab = r["title"] if r["kind"] == "text" else f'{r["source"]}: “{(r["text"] or "")[:90]}…”'
        k = "b:" + r["id"]
        g.node(k, "item", clean(lab), d="Live Broadcasts", t=ts(parse_t(r["published"])), u=r["link"], text=clean(r["text"] or "")[:300])
        g.edge(k, add_source(g, r["source"], "Live Broadcasts"), "source", ""); link_text(g, D, k, txt); n += 1
    _log("site: Live Broadcasts clips with entity matches (broadcasts.db)", items=n)

def site_streams(g, D, cutoff):
    db = ro("streams.db"); names = {r["channel_id"]: r["title"] for r in db.execute("SELECT channel_id, title FROM live")}
    try:
        yc = json.load(open(os.path.join(BASE, "youtube_channels.json")))
        for c in (yc.get("channels", []) if isinstance(yc, dict) else yc):
            if isinstance(c, dict) and (c.get("id") or c.get("channel_id")): names[c.get("id") or c.get("channel_id")] = c.get("name") or c.get("title")
    except Exception: pass
    n = 0
    for r in db.execute("SELECT * FROM segments WHERE rank >= 3 AND t_start >= ?", (iso(cutoff),)):
        ch = re.split(r"[|:]| - ", names.get(r["channel_id"]) or "YouTube live")[0].replace("LIVE", "").strip()[:60] or "YouTube live"
        if private(r["text"], ch, names.get(r["channel_id"])): continue
        if not D.match(r["text"]): continue
        k = "s:" + str(r["id"])
        g.node(k, "item", f'{ch}: “{r["text"][:90]}…”', d="Live Streams", t=ts(parse_t(r["t_start"])), u=f'https://www.youtube.com/watch?v={r["video_id"]}', rank=r["rank"], text=r["text"][:300])
        g.edge(k, add_source(g, "YouTube live: " + ch, "Live Streams"), "source", ""); link_text(g, D, k, r["text"]); n += 1
    _log("site: Live Streams scored transcript segments (streams.db, rank>=3)", items=n)

def site_aviation(g, D):
    db = ro("aviation_state.db"); n = 0
    rows = [("av:" + r["hex"] + ":" + r["ts"], r["label"], r["callsign"], r["hex"], r["place"], r["ts"], r["lat"], r["lon"], r["category"]) for r in db.execute("SELECT * FROM notable_log")]
    rows += [("avs:" + r["hex"] + ":" + r["flight_start"], r["label"], r["callsign"], r["hex"], r["first_place"], r["flight_start"], r["first_lat"], r["first_lon"], None) for r in db.execute("SELECT * FROM sightings")]
    for k, label, cs, hx, place, t, la, lo, cat in rows:
        if private(place): continue
        g.node(k, "item", f'{label} ({cs or hx}) {place}', d="Aviation watch", c="aviation", t=ts(parse_t(t)), u=f"https://globe.adsbexchange.com/?icao={hx}", lat=la, lon=lo)
        g.edge(k, add_source(g, "ADS-B (aviation watch)", "Aviation watch"), "source", ""); add_cat(g, k, "aviation")
        if cat: g.edge(k, g.node("inf:aircraft: " + cat, "infrastructure", "Aircraft: " + cat.replace("_", " "))["k"], "aircraft_type", label)
        link_text(g, D, k, f"{label} {place}"); n += 1
    _log("site: Aviation watch notable/military sightings (aviation_state.db)", items=n)

def site_jets(g, D, cutoff):
    n = 0
    for r in ro("jets.db").execute("SELECT airport, airport_name, airport_country, COUNT(*) n, AVG(lat) la, AVG(lon) lo, MAX(ts) last FROM departures "
                                   "WHERE ts >= ? AND airport IS NOT NULL GROUP BY airport HAVING n >= 2", (iso(cutoff),)):
        if private(r["airport_name"]) or r["airport"] in ("KSFB", "KMCO", "KORL", "KDAB", "KISM", "KLEE", "KDED", "KEVB", "KOCF", "KTIX", "KMLB"): continue
        k = "ap:" + r["airport"]
        g.node(k, "item", f'{r["airport"]} {r["airport_name"]}: {r["n"]} private-jet departures (30 d)', d="Private jets", c="aviation", t=ts(parse_t(r["last"])),
               u=f'https://ourairports.com/airports/{r["airport"]}/', lat=r["la"], lon=r["lo"])
        g.edge(k, add_source(g, "ADS-B (private jets)", "Private jets"), "source", ""); add_cat(g, k, "aviation")
        if r["airport_country"] in D.countries: g.edge(k, ent(g, D, "country", r["airport_country"]), "located_in", "airport country code " + r["airport_country"])
        g.edge(k, ent(g, D, "infrastructure", "Airports"), "is_a", "airport (ICAO " + r["airport"] + ")"); n += 1
    _log("site: Private jets departures, aggregated per airport (jets.db)", items=n)

def site_politics(g, D):
    n = 0
    for r in ro("politics.db").execute("SELECT * FROM hist_events"):
        if private(r["title"]) or not D.match(r["title"]): continue
        k = "pm:" + r["platform"] + ":" + r["event_id"]
        g.node(k, "item", f'{r["title"]} → {r["winner"] or "open"}', d="Politics markets", c="political", t=ts(parse_t(r["decided_ts"] or r["close_ts"])), u=r["url"])
        g.edge(k, add_source(g, r["platform"], "Politics markets"), "source", ""); add_cat(g, k, "political"); link_text(g, D, k, r["title"]); n += 1
    _log("site: Politics prediction-market history (politics.db hist_events)", items=n)

def site_netstatus(g, D, cutoff):
    n = 0
    for r in ro("netstatus.db").execute("SELECT src, grp, status, url, MAX(level) lv, MAX(ts) last FROM checks WHERE level >= 2 AND ts >= ? AND grp NOT LIKE 'Box probes%' "
                                        "GROUP BY src, status", (iso(cutoff),)):
        st = clean(r["status"])
        if private(st): continue
        k = "ns:" + hashlib.sha1((r["src"] + st).encode()).hexdigest()[:12]
        g.node(k, "item", f'{r["src"]}: {st}', d="Network Status", c="infrastructure", t=ts(parse_t(r["last"])), u=r["url"])
        g.edge(k, add_source(g, r["src"] + " status page", "Network Status"), "source", ""); add_cat(g, k, "infrastructure")
        g.edge(k, ent(g, D, "hazard", "internet outage"), "mentions", f"status level {r['lv']}"); link_text(g, D, k, st); n += 1
    _log("site: Network Status provider incidents (netstatus.db, level>=2)", items=n)

def enrich_sources(g):
    try: rows = {r["key"].lower(): r for r in ro("sources.db").execute("SELECT key, type, link, rating FROM sources")}
    except Exception: return
    n = 0
    for nd in g.nodes.values():
        if nd["y"] == "source":
            r = rows.get(nd["l"].lower())
            if r:
                nd["rating"] = r["rating"]; nd["stype"] = r["type"]
                if r["link"] and not private(r["link"]): nd.setdefault("u", r["link"])
                n += 1
    _log("site: Sources registry (sources.db) ratings attached", items=n)

# ------------------------------------------------------------------ external public feeds (30 days; raw responses cached in thread_cache/)
def ext_item(g, D, key, label, dataset, source, cat, t, url, text="", lat=None, lon=None, **kw):
    if t is None or t < now() - timedelta(days=WINDOW_D) or t > now() + timedelta(days=3) or private(label, text): return None
    if g.has_url(url):   # mirror copy of an item already on the site: attach this source to it instead of duplicating
        g.edge(g.has_url(url), add_source(g, source, dataset), "source", "same URL"); return None
    k = "x:" + key; label = clean(strip(label))
    if k in g.nodes: return None
    g.node(k, "item", label, d=dataset, c=cat, t=ts(t), u=url, lat=lat, lon=lon, text=clean(strip(text))[:400] or None, **kw)
    g.reg_url(url, k); g.edge(k, add_source(g, source, dataset), "source", ""); add_cat(g, k, cat)
    link_text(g, D, k, label + " | " + strip(text)[:800])
    return k

def run_ext(name, fn, *a):
    try: _log(name, items=fn(*a) or 0)
    except Exception as ex: _log(name, error=f"{type(ex).__name__}: {str(ex)[:160]}")

def x_usgs(g, D):
    j = json.loads(fetch("usgs_2.5_month", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_month.geojson", 3600)); n = 0
    for f in j["features"]:
        p = f["properties"]; lo, la = f["geometry"]["coordinates"][:2]
        if g.has_url(p["url"]):
            k0 = g.has_url(p["url"]); nd = g.nodes[k0]
            for a, b in (("lat", la), ("lon", lo), ("mag", p["mag"])): nd.setdefault(a, b)
            g.edge(k0, add_source(g, "USGS", "USGS earthquakes"), "source", "same USGS event page"); continue
        k = ext_item(g, D, "usgs:" + f["id"], p["title"] or f"M{p['mag']} {p['place']}", "USGS earthquakes", "USGS", "natural disaster", parse_t(p["time"]), p["url"],
                     p.get("place") or "", lat=la, lon=lo, mag=p["mag"])
        if k:
            n += 1; g.edge(k, ent(g, D, "hazard", "earthquake"), "mentions", "USGS event type: " + (p.get("type") or "earthquake"))
            if p.get("tsunami"): g.edge(k, ent(g, D, "hazard", "tsunami"), "mentions", "USGS tsunami flag = 1")
    return n

def x_tsunami(g, D):
    n = 0
    for code in ("PAAQ", "PHEB"):
        for e in rss_items(fetch("tsunami_" + code, f"https://www.tsunami.gov/events/xml/{code}Atom.xml", 1800)):
            k = ext_item(g, D, "tsu:" + hashlib.sha1((e.get("id") or e.get("title") or "").encode()).hexdigest()[:14], f'tsunami.gov {code}: {e.get("title")}', "tsunami.gov",
                         f"NOAA tsunami.gov ({code})", "natural disaster", parse_t(e.get("updated")), e.get("link") or f"https://www.tsunami.gov/", e.get("summary", ""))
            if k: n += 1; g.edge(k, ent(g, D, "hazard", "tsunami"), "mentions", "tsunami.gov bulletin")
    return n

def x_swpc(g, D):
    n = 0
    for a in json.loads(fetch("swpc_alerts", "https://services.swpc.noaa.gov/products/alerts.json", 1800)):
        t = parse_t((a.get("issue_datetime") or "").replace(" ", "T")[:19] + "Z")
        if t and ("sw:" + a.get("product_id", "") + ":" + iso(t)) in g.nodes: continue     # already on the site (solar_seismic.db)
        k = ext_item(g, D, "swpc:" + a.get("product_id", "") + ":" + (a.get("issue_datetime") or ""), swpc_title(a.get("message"), a.get("product_id")), "NOAA SWPC", "NOAA SWPC",
                     "space weather", t, "https://www.swpc.noaa.gov/products/alerts-watches-and-warnings", a.get("message", "")[:600])
        if k: n += 1
    for f in json.loads(fetch("swpc_flares", "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json", 1800)):
        cl = f.get("max_class") or ""
        if not re.match(r"[MX]|C[5-9]", cl): continue
        mt = (f.get("max_time") or f.get("begin_time") or "")
        k = ext_item(g, D, "flare:" + (f.get("begin_time") or ""), f"{cl} solar flare (GOES X-ray peak {mt[:16].replace('T', ' ')} UTC)", "NOAA SWPC", "NOAA SWPC (GOES X-ray)",
                     "space weather", parse_t(mt), "https://www.swpc.noaa.gov/products/goes-x-ray-flux#" + mt)
        if k: n += 1; g.edge(k, ent(g, D, "hazard", "solar flare"), "mentions", "GOES X-ray class " + cl)
    for r in json.loads(fetch("swpc_kp", "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", 1800)):
        if isinstance(r, dict) and float(r.get("Kp") or 0) >= 5:
            kp = float(r["Kp"]); lvl = min(5, int(kp) - 4)
            k = ext_item(g, D, "kp:" + r["time_tag"], f'Planetary Kp {kp:.2f} (G{lvl} storm level) at {r["time_tag"][:16].replace("T", " ")} UTC', "NOAA SWPC",
                         "NOAA SWPC (planetary K-index)", "space weather", parse_t(r["time_tag"] + "Z"), "https://www.swpc.noaa.gov/products/planetary-k-index#" + r["time_tag"])
            if k: n += 1; g.edge(k, ent(g, D, "hazard", "geomagnetic storm"), "mentions", f"Kp {kp:.2f} ≥ 5")
    return n

def x_gdacs(g, D):
    to = now(); fr = to - timedelta(days=WINDOW_D); n = 0
    j = json.loads(fetch("gdacs_30d", f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?fromDate={fr:%Y-%m-%d}&toDate={to:%Y-%m-%d}&alertlevel=Green;Orange;Red", 3600))
    TY = {"EQ": "earthquake", "TC": "tropical cyclone", "FL": "flood", "VO": "volcano", "WF": "wildfire", "DR": "drought", "TS": "tsunami"}
    iso3 = {v.get("iso3"): c for c, v in D.countries.items()}
    for f in j.get("features", []):
        p = f["properties"]; co = (f.get("geometry") or {}).get("coordinates") or [None, None]
        url = (p.get("url") or {}).get("report") or f'https://www.gdacs.org/report.aspx?eventtype={p.get("eventtype")}&eventid={p.get("eventid")}'
        k = ext_item(g, D, f'gdacs:{p.get("eventtype")}{p.get("eventid")}', f'GDACS {p.get("alertlevel")}: {p.get("name") or p.get("description")}', "GDACS", "GDACS", "natural disaster",
                     parse_t(p.get("todate") or p.get("fromdate")), url, (p.get("description") or "") + " | " + (p.get("country") or ""), lat=co[1] if len(co) > 1 else None, lon=co[0])
        if k:
            n += 1
            if TY.get(p.get("eventtype")): g.edge(k, ent(g, D, "hazard", TY[p["eventtype"]]), "mentions", "GDACS event type " + p["eventtype"])
            for c3 in re.findall(r"[A-Z]{3}", p.get("iso3") or ""):
                if c3 in iso3: g.edge(k, ent(g, D, "country", iso3[c3]), "mentions", "GDACS affected country " + c3)
    return n

def x_eonet(g, D):
    j = json.loads(fetch("eonet_30d", f"https://eonet.gsfc.nasa.gov/api/v3/events?status=all&days={WINDOW_D}", 3600)); n = 0
    MAP = {"wildfires": "wildfire", "severeStorms": "tropical cyclone", "volcanoes": "volcano", "floods": "flood", "earthquakes": "earthquake", "drought": "drought",
           "landslides": "landslide", "snow": "severe storm", "tempExtremes": "extreme heat"}
    for ev in j.get("events", []):
        geo = (ev.get("geometry") or [{}])[-1]; co = geo.get("coordinates") or [None, None]
        while co and isinstance(co[0], list): co = co[0]
        src = (ev.get("sources") or [{}])[0]
        k = ext_item(g, D, "eonet:" + ev["id"], ev["title"], "NASA EONET", "NASA EONET" + (" / " + src["id"] if src.get("id") else ""), "natural disaster", parse_t(geo.get("date")),
                     ev.get("link") or src.get("url"), "", lat=co[1] if len(co) > 1 else None, lon=co[0])
        if k:
            n += 1
            for c in ev.get("categories") or []:
                if MAP.get(c.get("id")): g.edge(k, ent(g, D, "hazard", MAP[c["id"]]), "mentions", "EONET category " + c.get("title", ""))
    return n

def x_rss(g, D, key, url, dataset, source, cat, ttl, extra_hazard=None):
    n = 0
    for e in rss_items(fetch(key, url, ttl, binary=True)):
        title = strip(e.get("title")); t = parse_t(e.get("pubDate") or e.get("updated") or e.get("published") or e.get("date"))
        link = e.get("link") or e.get("id")
        if key.startswith("cdc") and (e.get("id") or "").startswith("http"): link = e.get("id")
        k = ext_item(g, D, key + ":" + hashlib.sha1((e.get("guid") or e.get("id") or link or title).encode()).hexdigest()[:14], title, dataset, source, cat, t, link,
                     e.get("description") or e.get("summary") or "")
        if k:
            n += 1
            if extra_hazard: g.edge(k, ent(g, D, "hazard", extra_hazard), "mentions", source + " outbreak feed")
    return n

def x_nws(g, D):
    j = json.loads(fetch("nws_active", "https://api.weather.gov/alerts/active?severity=Extreme,Severe", 1800)); n = 0; seen = set()
    for f in j.get("features", []):
        p = f["properties"]; key = (p.get("event"), p.get("senderName"), p.get("areaDesc"))
        if key in seen: continue
        seen.add(key); la = lo = None
        try: ring = f["geometry"]["coordinates"][0]; lo = sum(c[0] for c in ring) / len(ring); la = sum(c[1] for c in ring) / len(ring)
        except Exception: pass
        k = ext_item(g, D, "nws:" + p["id"][-48:], p.get("headline") or p.get("event"), "NWS CAP alerts", "NWS (api.weather.gov)", "natural disaster", parse_t(p.get("sent")),
                     p.get("@id") or p.get("id"), (p.get("event") or "") + " | " + (p.get("areaDesc") or "")[:200], lat=la, lon=lo)
        if k: n += 1; g.edge(k, ent(g, D, "country", "US"), "mentions", "US National Weather Service area")
    return n

def x_who(g, D):
    j = json.loads(fetch("who_don", "https://www.who.int/api/news/diseaseoutbreaknews?$orderby=PublicationDate%20desc&$top=60", 10800)); n = 0
    for v in j.get("value", []):
        k = ext_item(g, D, "who:" + str(v.get("Id") or v.get("UrlName")), "WHO DON: " + (v.get("OverrideTitle") or v.get("Title") or ""), "WHO outbreak news", "WHO Disease Outbreak News",
                     "disease", parse_t(v.get("PublicationDate")), "https://www.who.int/emergencies/disease-outbreak-news/item/" + (v.get("UrlName") or ""), strip(v.get("Summary") or "")[:600])
        if k: n += 1; g.edge(k, ent(g, D, "hazard", "disease outbreak"), "mentions", "WHO Disease Outbreak News")
    return n

def x_kev(g, D):
    j = json.loads(fetch("cisa_kev", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", 21600)); n = 0
    for v in j.get("vulnerabilities", []):
        k = ext_item(g, D, "kev:" + v["cveID"], f'{v["cveID"]} added to CISA KEV: {v.get("vendorProject")} {v.get("product")} – {v.get("vulnerabilityName")}', "CISA (cyber)", "CISA KEV",
                     "cyber", parse_t(v.get("dateAdded")), f'https://nvd.nist.gov/vuln/detail/{v["cveID"]}', v.get("shortDescription", ""))
        if k:
            n += 1; g.edge(k, g.node("act:" + v["vendorProject"].lower(), "actor", v["vendorProject"])["k"], "vendor", "KEV vendorProject: " + v["vendorProject"])
            g.edge(k, ent(g, D, "hazard", "software vulnerability"), "mentions", v["cveID"])
            if (v.get("knownRansomwareCampaignUse") or "").lower() == "known": g.edge(k, ent(g, D, "hazard", "ransomware"), "mentions", "KEV: known ransomware campaign use")
    return n

def x_cisa_adv(g, D):
    n = 0
    for e in rss_items(fetch("cisa_adv", "https://www.cisa.gov/cybersecurity-advisories/all.xml", 21600, binary=True)):
        k = ext_item(g, D, "cisaadv:" + hashlib.sha1((e.get("link") or e.get("title") or "").encode()).hexdigest()[:14], strip(e.get("title")), "CISA (cyber)", "CISA Advisories",
                     "cyber", parse_t(e.get("pubDate")), e.get("link"), strip(e.get("description", ""))[:600])
        if k: n += 1
    return n

TG = ["OSINTdefender", "ClashReport", "warmonitors", "intelslava", "Middle_East_Spectator", "rnintel", "BellumActaNews", "CIG_telegram", "AuroraIntel", "insiderpaper",
      "disclosetv", "spectatorindex", "TheIslanderNews", "nexta_live", "QudsNen"]   # = scanner.py TG_CHANNELS + TG_EXTRA (already-configured public previews)
def x_telegram(g, D):
    n = 0; errs = []
    for ch in TG:
        before = None
        for page in range(2):
            fresh = not os.path.exists(os.path.join(CACHE, f"raw_tg_{ch}_{page}")) or time.time() - os.path.getmtime(os.path.join(CACHE, f"raw_tg_{ch}_{page}")) > 7200
            try: h = fetch(f"tg_{ch}_{page}", f"https://t.me/s/{ch}" + (f"?before={before}" if before else ""), 7200)
            except Exception as ex: errs.append(f"{ch}: {str(ex)[:60]}"); break
            if fresh: time.sleep(1.5)   # polite pacing
            ids = []
            for blk in re.split(r'<div class="tgme_widget_message_wrap', h)[1:]:
                post = re.search(r'data-post="([^"]+)"', blk); txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S); tm = re.search(r'datetime="([^"]+)"', blk)
                if not post: continue
                try: ids.append(int(post.group(1).split("/")[-1]))
                except Exception: pass
                if not txt: continue
                text = re.split(r"💧|Rainbet|Use our affiliate|Join us|Follow us", strip(txt.group(1)))[0].strip()
                if len(text) < 25 or re.search(r"casino|sportsbook|affiliate|promo code", text, re.I): continue
                k = ext_item(g, D, "tg:" + post.group(1), text[:200], "Telegram (public previews)", "Telegram @" + ch, None, parse_t(tm.group(1)) if tm else None,
                             f"https://t.me/{post.group(1)}", text)
                if k: n += 1
            if not ids: break
            before = min(ids)
    if errs: _log("feed: Telegram public previews (15 configured channels, 2 pages each)", channel_errors=errs)
    return n

# ------------------------------------------------------------------ item <-> item edges (grounded rules only)
STOPW = set("the a an and or of to in on for with at by from as is are was were be been it its this that over after amid into new says said live update updates breaking video "
            "about more than not near has have had will would can could may might up out off his her their they he she we you our who what when where why how all just news "
            "report reports today latest world day week month year two one three first last km utc issued until warning watch alert advisory gdacs swpc nws telegram".split())
def toks(s): return {w for w in re.findall(r"[a-z][a-z0-9'-]{2,}", (s or "").lower()) if w not in STOPW}

def item_edges(g):
    items = [n for n in g.nodes.values() if n["y"] == "item" and n.get("t")]
    srcs = {}
    for a, b, typ, _ in g.edges.values():
        if typ == "source": srcs.setdefault(a, set()).add(b); srcs.setdefault(b, set()).add(a)
    # 1) same story across different sources: >=3 shared title words (each in <=60 titles), Jaccard >= 0.34, <= 48 h apart
    T = {n["k"]: toks(n["l"]) for n in items}; df = {}
    for s in T.values():
        for w in s: df[w] = df.get(w, 0) + 1
    ix = {}
    for k, s in T.items():
        for w in s:
            if 2 <= df[w] <= 60: ix.setdefault(w, []).append(k)
    cand = {}
    for w, ks in ix.items():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                p = (ks[i], ks[j]) if ks[i] < ks[j] else (ks[j], ks[i]); cand[p] = cand.get(p, 0) + 1
    n_same = 0; per = {}
    for (a, b), c in sorted(cand.items(), key=lambda x: -x[1]):
        if c < 3: break
        A, B = g.nodes[a], g.nodes[b]; dt = abs(A["t"] - B["t"]) / 3600
        if dt > 48 or (srcs.get(a, set()) & srcs.get(b, set())) or per.get(a, 0) >= 4 or per.get(b, 0) >= 4: continue
        sa, sb = T[a], T[b]; jac = len(sa & sb) / max(1, len(sa | sb))
        if jac < 0.34: continue
        sh = sorted(sa & sb, key=lambda w: df[w])[:5]
        g.edge(a, b, "same_story", f'{round(jac * 100)}% title overlap ({", ".join(sh)}), {dt:.1f} h apart'); n_same += 1
        per[a] = per.get(a, 0) + 1; per[b] = per.get(b, 0) + 1
    # 2) geographic proximity (3° grid buckets): quake<->quake <=300 km & <=7 d; other geolocated items <=100 km & <=72 h; <=4 nearest per node
    geo = []
    for n in items:
        try:
            la, lo = float(n.get("lat")), float(n.get("lon"))
            if -90 <= la <= 90 and -180 <= lo <= 180 and not (la == 0 and lo == 0): geo.append((n, la, lo, n.get("mag") is not None))
        except (TypeError, ValueError): pass
    grid = {}
    for e in geo: grid.setdefault((int((e[1] + 90) // 3), int((e[2] + 180) // 3)), []).append(e)
    n_q = n_near = 0; deg = {}
    for (gx, gy), lst in grid.items():
        for n, la, lo, isq in lst:
            best = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for m, la2, lo2, isq2 in grid.get((gx + dx, (gy + dy) % 120), []):
                        if m["k"] <= n["k"]: continue
                        q = isq and isq2; maxd, maxt = (300, 168) if q else (100, 72)
                        dt = abs(n["t"] - m["t"]) / 3600
                        if dt > maxt: continue
                        d = hav(la, lo, la2, lo2)
                        if d <= maxd: best.append((d, dt, m, q))
            best.sort(key=lambda x: x[0])
            for d, dt, m, q in best[:4]:
                if deg.get(m["k"], 0) >= 8: continue
                if q: g.edge(n["k"], m["k"], "quake_seq", f"{d:.0f} km and {dt / 24:.1f} days apart (M{n.get('mag')} / M{m.get('mag')})"); n_q += 1
                else: g.edge(n["k"], m["k"], "nearby", f"{d:.0f} km and {dt:.0f} h apart"); n_near += 1
                deg[m["k"]] = deg.get(m["k"], 0) + 1
    STATS["item_edges"] = {"same_story": n_same, "quake_seq": n_q, "nearby": n_near}

def country_links(g, D):
    for k, n in list(g.nodes.items()):
        if n["y"] == "country":
            for nb in (D.countries.get(k[3:]) or {}).get("neighbours") or []:
                if "cc:" + nb in g.nodes: g.edge(k, "cc:" + nb, "borders", "GeoNames neighbours")

# ------------------------------------------------------------------ layout: numpy force-directed, precomputed on the box so browsers only draw
def layout(nodes, edges, iters=140):
    import numpy as np
    N = len(nodes); ix = {n["k"]: i for i, n in enumerate(nodes)}; rng = np.random.default_rng(7)
    E = np.array([(ix[a], ix[b]) for a, b, t, _ in edges], dtype=np.int64).reshape(-1, 2)
    W = {"source": .3, "category": .02, "mentions": .35, "geocoded": .5, "located_in": .6, "story": 1.2, "story_link": .6, "same_story": 1.2, "quake_seq": .9,
         "nearby": .8, "borders": .3, "vendor": .7, "is_a": .05, "aircraft_type": .3}
    w = np.array([W.get(t, .4) for a, b, t, _ in edges], dtype=np.float32)
    deg = np.bincount(E.ravel(), minlength=N).astype(np.float32) + 1
    w = w / np.sqrt(np.minimum(deg[E[:, 0]], deg[E[:, 1]]))
    P = rng.normal(0, 900, (N, 2)).astype(np.float32)
    geo = np.zeros(N, bool)
    for i, n in enumerate(nodes):   # seed: countries/cities at their map position, so geography stays roughly recognisable
        if n["y"] in ("country", "city") and n.get("lat") is not None: P[i] = [float(n["lon"]) * 9, -float(n["lat"]) * 11]; geo[i] = True
    for _ in range(2):
        S = np.zeros((N, 2), np.float32); C = np.zeros(N, np.float32)
        np.add.at(S, E[:, 0], P[E[:, 1]]); np.add.at(S, E[:, 1], P[E[:, 0]]); np.add.at(C, E[:, 0], 1); np.add.at(C, E[:, 1], 1)
        P = np.where(geo[:, None], P, S / np.maximum(C, 1)[:, None] + rng.normal(0, 60, (N, 2)).astype(np.float32))
    mass = np.sqrt(deg); temp = 120.0; M = min(N, 900)
    for it in range(iters):
        F = np.zeros((N, 2), np.float32); J = rng.choice(N, M, replace=False)
        for s in range(0, N, 1200):
            d = P[s:s + 1200, None, :] - P[None, J, :]; r2 = (d ** 2).sum(-1) + 100.0
            F[s:s + 1200] += (d * (mass[None, J] / r2)[..., None]).sum(1) * (N / M) * 300.0
        d = P[E[:, 1]] - P[E[:, 0]]; L = np.sqrt((d ** 2).sum(1)) + 1e-3
        f = d * (w * L / 40.0)[:, None]; np.add.at(F, E[:, 0], f); np.add.at(F, E[:, 1], -f)
        F -= P * 0.004 * mass[:, None]; F /= mass[:, None]
        ln = np.sqrt((F ** 2).sum(1)) + 1e-6
        P += F / ln[:, None] * np.minimum(ln, temp)[:, None]; temp = max(1.5, temp * 0.97)
    return P - np.median(P, 0)

# ------------------------------------------------------------------ build
TYPES = ["item", "story", "source", "category", "country", "region", "city", "hazard", "pathogen", "actor", "infrastructure"]
ETYPES = {"source": "reported by", "category": "scanner category", "mentions": "text mentions", "geocoded": "heat-map geocoder placed it in", "located_in": "located in",
          "borders": "borders (GeoNames)", "story": "update in Thread story", "story_link": "related Thread stories", "same_story": "same story, different source",
          "quake_seq": "earthquake sequence (≤300 km, ≤7 days)", "nearby": "nearby event (≤100 km, ≤72 h)", "vendor": "affected vendor (CISA KEV)", "is_a": "is a",
          "aircraft_type": "aircraft category"}
CIDRAP = {"Ebola": 64, "Avian Influenza": 49, "Marburg": 77, "Measles": 78, "Mpox": 230556, "Nipah": 232665, "Cholera": 58, "Misc Emerging Topics": 31175, "Pandemic Influenza": 86}

def build():
    t0 = time.time(); STATS.clear(); STATS["fetch"] = {}
    g = G(); D = Dict(); cutoff = now() - timedelta(days=WINDOW_D)
    for name, fn in (("site: alerts", lambda: site_alerts(g, D, cutoff)), ("site: arcs", lambda: site_arcs(g)), ("site: quakes", lambda: site_quakes(g, D)),
                     ("site: swpc", lambda: site_swpc(g, D)), ("site: broadcasts", lambda: site_broadcasts(g, D, cutoff)), ("site: streams", lambda: site_streams(g, D, cutoff)),
                     ("site: aviation", lambda: site_aviation(g, D)), ("site: jets", lambda: site_jets(g, D, cutoff)), ("site: politics", lambda: site_politics(g, D)),
                     ("site: netstatus", lambda: site_netstatus(g, D, cutoff))):
        try: fn()
        except Exception as ex: _log(name, error=f"{type(ex).__name__}: {str(ex)[:160]}")
    run_ext("feed: USGS earthquakes M2.5+ (2.5_month GeoJSON)", x_usgs, g, D)
    run_ext("feed: tsunami.gov NTWC/PTWC (Atom)", x_tsunami, g, D)
    run_ext("feed: NOAA SWPC (alerts, GOES flares C5+, Kp>=5)", x_swpc, g, D)
    run_ext("feed: GDACS (30-day event API)", x_gdacs, g, D)
    run_ext("feed: NASA EONET (30 days, open+closed)", x_eonet, g, D)
    run_ext("feed: ReliefWeb disasters RSS", x_rss, g, D, "reliefweb_dis", "https://reliefweb.int/disasters/rss.xml", "ReliefWeb", "ReliefWeb", "natural disaster", 7200)
    run_ext("feed: ReliefWeb updates RSS", x_rss, g, D, "reliefweb_upd", "https://reliefweb.int/updates/rss.xml", "ReliefWeb", "ReliefWeb", "other", 7200)
    run_ext("feed: NWS CAP alerts (Severe/Extreme, active)", x_nws, g, D)
    run_ext("feed: WHO Disease Outbreak News (API)", x_who, g, D)
    run_ext("feed: CDC HAN (managed feed 413690)", x_rss, g, D, "cdc_han", "https://tools.cdc.gov/api/v2/resources/media/413690.rss", "CDC", "CDC HAN", "disease", 21600, "disease outbreak")
    run_ext("feed: CDC US outbreaks (feed 513)", x_rss, g, D, "cdc_outbreaks", "https://tools.cdc.gov/podcasts/feed.asp?feedid=513", "CDC", "CDC outbreaks", "disease", 21600, "disease outbreak")
    for nm, tid in CIDRAP.items():
        run_ext(f"feed: CIDRAP topic RSS ({nm})", x_rss, g, D, f"cidrap_{tid}", f"https://www.cidrap.umn.edu/news/{tid}/rss", "CIDRAP", "CIDRAP News", "disease", 10800)
    run_ext("feed: CISA KEV (added in last 30 days)", x_kev, g, D)
    run_ext("feed: CISA advisories RSS (last 30 days)", x_cisa_adv, g, D)
    run_ext("feed: Telegram public previews (15 configured channels, 2 pages each)", x_telegram, g, D)
    for nm, why in (("feed: ProMED", "skipped: promedmail.org/feed answers 308 -> 404; no public no-login feed"),
                    ("feed: EpiWatch", "skipped: JavaScript single-page app; no public machine-readable feed"),
                    ("feed: NASA DONKI CMEs", "skipped: kauai.ccmc.gsfc.nasa.gov timed out; api.nasa.gov DEMO_KEY returned 503 (CME warnings still arrive via SWPC alerts)"),
                    ("feed: Discord analyst channels", "skipped: no public no-login Discord feed exists in the code (sources_ext.py)")):
        _log(nm, skipped=why)
    enrich_sources(g); country_links(g, D); item_edges(g)
    while True:   # every node must have >= 1 edge
        deg = {}
        for a, b, t, _d in g.edges.values(): deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
        orph = [k for k in g.nodes if not deg.get(k)]
        if not orph: break
        for k in orph: del g.nodes[k]
        g.edges = {k: e for k, e in g.edges.items() if e[0] in g.nodes and e[1] in g.nodes}
    STATS["orphans_dropped"] = 0
    nodes = sorted(g.nodes.values(), key=lambda n: (TYPES.index(n["y"]), n["k"])); edges = list(g.edges.values())
    P = layout(nodes, edges); ix = {n["k"]: i for i, n in enumerate(nodes)}
    ds = sorted({n.get("d") or "" for n in nodes}); cats = sorted({n.get("c") or "" for n in nodes}); et = list(ETYPES)
    dg = [0] * len(nodes)
    for a, b, t, d in edges: dg[ix[a]] += 1; dg[ix[b]] += 1
    out_nodes = []
    for i, n in enumerate(nodes):
        row = [n["l"], TYPES.index(n["y"]), ds.index(n.get("d") or ""), cats.index(n.get("c") or ""), n.get("t") or 0, n.get("u") or "", round(float(P[i, 0]), 1), round(float(P[i, 1]), 1), dg[i]]
        info = {k: n[k] for k in ("rank", "nsrc", "sev", "mag", "rating", "stype", "text") if n.get(k) not in (None, "")}
        if info: row.append(info)
        out_nodes.append(row)
    by_type, by_et, by_ds = {}, {}, {}
    for n in nodes: by_type[n["y"]] = by_type.get(n["y"], 0) + 1
    for e in edges: by_et[e[2]] = by_et.get(e[2], 0) + 1
    for n in nodes:
        if n["y"] in ("item", "story"): by_ds[n.get("d")] = by_ds.get(n.get("d"), 0) + 1
    res = {"generated": iso(now()), "window_days": WINDOW_D, "build_s": round(time.time() - t0, 1),
           "counts": {"nodes": len(nodes), "edges": len(edges), "labels": len(nodes) - by_type.get("item", 0), "by_type": by_type, "by_edge_type": by_et, "items_by_dataset": by_ds},
           "types": TYPES, "datasets": ds, "categories": cats, "edge_types": [[k, ETYPES[k]] for k in et], "feeds": STATS["fetch"], "item_edges": STATS.get("item_edges"),
           "note": "Read-only: nodes come from the site's own datasets plus cached free public feeds; every string is a dictionary match, geocode, shared story, or time+distance rule (the reason is on each string). It never changes scanner scores or ranks.",
           "nodes": out_nodes, "edges": [[ix[a], ix[b], et.index(t), d] for a, b, t, d in edges]}
    txt = json.dumps(res, ensure_ascii=False, separators=(",", ":"))
    if SCRUB_ROW_RE.search(txt): raise RuntimeError("scrub check failed: a private string reached the output; not written")
    tmp = OUT + ".tmp"; open(tmp, "w").write(txt); os.replace(tmp, OUT)
    return res

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        r = build(); print(json.dumps({k: r[k] for k in ("generated", "build_s", "counts", "item_edges", "feeds")}, indent=1, ensure_ascii=False))
    elif cmd == "stats":
        r = json.load(open(OUT)); print(json.dumps({k: r.get(k) for k in ("generated", "build_s", "counts", "item_edges", "feeds")}, indent=1, ensure_ascii=False))
    elif cmd == "loop":
        while True:
            try: r = build(); print(time.strftime("%FT%T"), "built", r["counts"]["nodes"], "nodes", r["counts"]["edges"], "edges in", r["build_s"], "s", flush=True)
            except Exception as ex: print(time.strftime("%FT%T"), "build failed:", repr(ex)[:300], flush=True)
            time.sleep(LOOP_S)

if __name__ == "__main__":
    main()
