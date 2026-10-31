"""Geolocation sidecar for the Regional Heat Map tab (served by heatmap.py; never edits scanner.py / scoring / push.py / jets.py).
Reads blackout.db READ-ONLY (mode=ro) and writes one row per alert (cluster_id) into geo.db:
  lat, lon, place, country, admin1, city, precision (point/city/county/state/country), method, confidence, located, reason_unlocated.
Method order: 1) coordinates already in the source data (USGS, GDACS, NWS, tsunami.gov; cluster or member-alert lat/lon)
              2) the alert's existing location field / NWS zone list, then place names in the title, matched against an offline
                 gazetteer (GeoNames cities15000 + countries + admin1 / US states, Natural Earth labels) with disambiguation rules
              3) OpenStreetMap Nominatim as a fallback (1 request/s, identified User-Agent, every answer cached in geo.db).
Nothing is guessed: when no rule fires, the alert is stored as unlocated with a specific reason."""
import os, re, json, time, sqlite3, threading, unicodedata, hashlib, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
GDB = os.path.join(BASE, "geo.db")
BDB = "file:" + os.path.join(BASE, "blackout.db") + "?mode=ro"
DATA = os.path.join(BASE, "heatmap_data")
STATIC = os.path.join(BASE, "heatmap_static")
UA = "blackout.network-heatmap/1.0 (+https://blackout.network; research dashboard geocoding sidecar; max 1 req/s, cached)"
NOM_URL = "https://nominatim.openstreetmap.org/search"
NOM_BUDGET = 150            # max Nominatim requests per worker pass (cached forever, so each query is asked once)
WINDOW_DAYS = 7
VERSION = 8                 # bump to re-geocode everything after rule changes
_lock = threading.RLock()
_nom_lock = threading.Lock()
_last_nom = [0.0]

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")

# ------------------------------------------------------------------ geo.db
def gdb():
    c = sqlite3.connect(GDB, timeout=30); c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS geo(
      id TEXT PRIMARY KEY,            -- cluster_id in blackout.db (the alert/story the dashboard shows)
      lat REAL, lon REAL, place TEXT, country TEXT, country_name TEXT, admin1 TEXT, admin1_code TEXT, city TEXT,
      precision TEXT,                 -- point | city | county | state | country
      method TEXT,                    -- source_coords | location_field | gazetteer | nominatim
      method_detail TEXT, confidence TEXT, located INTEGER, reason_code TEXT, reason_unlocated TEXT, candidates TEXT,
      evidence TEXT, sig TEXT, version INTEGER, geocoded_at TEXT, attempts INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS ix_geo_loc ON geo(located);
    CREATE TABLE IF NOT EXISTS nominatim_cache(q TEXT PRIMARY KEY, status TEXT, result TEXT, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, trigger TEXT,
      scanned INTEGER, geocoded INTEGER, located INTEGER, nominatim_calls INTEGER, error TEXT);
    """)
    return c

def bdb():
    c = sqlite3.connect(BDB, uri=True, timeout=30); c.row_factory = sqlite3.Row
    return c

# ------------------------------------------------------------------ text helpers
def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).replace("’", "'").replace("‘", "'").replace("ʻ", "'").replace("ʼ", "'")
TOK = re.compile(r"[A-Za-z][A-Za-z'.]*[A-Za-z]|[A-Za-z]")
def nw(w):
    w = w.lower()
    if w.endswith("'s"): w = w[:-2]
    return w.replace("'", "").replace(".", "")
def key_of(name): return " ".join(nw(t) for t in TOK.findall(fold(name)))

LOC_CUES = {"in", "near", "at", "outside", "across", "over", "into", "toward", "towards", "around", "off", "from", "of", "on", "inside", "throughout", "hits", "hit", "struck", "rocks", "shakes"}
LOCATIONAL = {"county", "city", "province", "region", "state", "oblast", "district", "airport", "port", "harbor", "harbour", "bay", "island", "islands", "valley",
              "beach", "area", "suburbs", "outskirts", "metro", "governorate", "prefecture", "municipality", "village", "town", "camp", "strip", "border", "coast", "river"}
STRONG_CUES = {"in", "near", "outside", "across", "into", "toward", "towards", "around", "inside", "throughout", "off"}
CONNECT = {"of", "de", "del", "la", "le", "el", "al", "an", "and", "the", "upon", "da", "do", "dos", "das", "di", "du", "des", "on", "sur", "am", "im", "bin", "ul", "ad"}
MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
          "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "tonight", "yesterday", "tomorrow"}
GENERIC = {"central", "north", "south", "east", "west", "northern", "southern", "eastern", "western", "centre", "center", "capital", "national", "federal",
           "city", "islands", "island", "coast", "north east", "north west", "south east", "south west", "northeast", "northwest", "southeast", "southwest",
           "middle", "upper", "lower", "interior", "highlands", "lakes", "mountain", "mountains", "river", "valley", "plains", "metro", "region", "district",
           "border", "frontier", "littoral", "orient", "oriental", "occidental", "sud", "nord", "est", "ouest", "centro", "norte", "sur", "oeste", "leste"}
COMMON_HARD = {"police", "most", "split", "nice", "mobile", "deal", "bar", "hit", "hope", "reading", "bath", "of", "san", "university", "union", "independence",
               "liberty", "victoria", "florence", "lincoln", "jackson", "hamilton", "marion", "warren", "clinton", "douglas", "lawrence", "madison", "franklin",
               "jefferson", "washington", "trump", "biden", "obama", "harris", "musk", "vance", "putin", "zelensky", "netanyahu", "xi", "modi", "erdogan",
               "march", "may", "june", "august", "april", "christmas", "easter", "orange", "temple", "eagle", "phoenix", "mercury", "sun", "moon", "mars",
               "venus", "earth", "progress", "harmony", "concord", "unity", "justice", "freedom", "trinidad", "santa", "salt", "gold", "silver", "stone",
               "bristol", "kent", "york", "derby", "chester", "worth", "lynn", "page", "price", "young", "king", "brown", "green", "white", "black", "gray",
               "grey", "rich", "long", "short", "best", "good", "fair", "mission", "pace", "rush", "nation", "dawn", "venture", "cobra", "hermes", "apollo",
               "athena", "zion", "bethel", "eden", "goshen", "canaan", "galilee", "babylon", "bethlehem", "nazareth", "salem", "sharon", "carmel", "hebron",
               "sanders", "adams", "lafayette", "austin", "charlotte", "elizabeth", "tyler", "dallas", "houston", "aurora", "columbia", "cleveland", "mesa",
               "nato", "isis", "hamas", "hezbollah", "houthi", "houthis", "idf", "un", "eu", "who", "cia", "fbi", "nsa", "kgb", "ira", "fed", "sec", "x",
               "ai", "gaming", "cruz", "chicago fire", "brent", "wti", "ukrainian-", "banda", "batman", "superman", "bolt", "mosquito", "sabotage", "kansas city chiefs", "patriot", "patriots",
               "said", "says", "news", "live", "breaking", "update", "alert", "watch", "warning", "drone", "drones", "flood", "storm", "fire", "tornado"}
COUNTRY_ALIASES = {"US": ["United States", "USA", "U.S", "US", "U.S.A", "United States of America", "the States"], "GB": ["UK", "U.K", "Britain", "Great Britain", "England", "Scotland", "Wales", "Northern Ireland", "United Kingdom"],
                   "RU": ["Russia", "Russian Federation"], "KR": ["South Korea", "Republic of Korea", "ROK"], "KP": ["North Korea", "DPRK"], "IR": ["Iran"], "SY": ["Syria"],
                   "CD": ["DRC", "DR Congo", "Democratic Republic of the Congo", "Democratic Republic of Congo", "Congo-Kinshasa", "Congo"], "CG": ["Republic of the Congo", "Congo-Brazzaville"],
                   "CI": ["Ivory Coast", "Cote d'Ivoire"], "TR": ["Turkey", "Turkiye"], "MM": ["Myanmar", "Burma"], "AE": ["UAE", "United Arab Emirates", "Emirates"],
                   "PS": ["Palestine", "Palestinian Territories", "Gaza Strip", "West Bank", "Occupied Palestinian Territory"], "CZ": ["Czechia", "Czech Republic"],
                   "VN": ["Vietnam", "Viet Nam"], "LA": ["Laos"], "TW": ["Taiwan"], "TZ": ["Tanzania"], "VE": ["Venezuela"], "BO": ["Bolivia"], "MD": ["Moldova"],
                   "MK": ["North Macedonia", "Macedonia"], "TL": ["East Timor", "Timor-Leste"], "SZ": ["Eswatini", "Swaziland"], "CV": ["Cape Verde", "Cabo Verde"],
                   "VA": ["Vatican", "Vatican City", "Holy See"], "NL": ["Netherlands", "Holland"], "BS": ["Bahamas", "The Bahamas"], "GM": ["Gambia", "The Gambia"],
                   "SA": ["Saudi Arabia", "KSA"], "BA": ["Bosnia", "Bosnia and Herzegovina"], "FM": ["Micronesia"], "PH": ["Philippines", "the Philippines"],
                   "CN": ["China", "PRC", "Mainland China"], "IL": ["Israel"], "UA": ["Ukraine"], "XK": ["Kosovo"], "SS": ["South Sudan"], "ZA": ["South Africa"]}
CAPS_ONLY = {"us", "usa", "uk", "uae", "drc", "prc", "rok", "dprk", "ksa", "u s", "u k"}
NEEDS_CTX_COUNTRY = {"chad", "jordan", "niger", "guinea", "jersey", "georgia", "turkey", "china", "chile", "togo", "mali", "oman", "peru", "cuba", "iran"} - {"china", "iran", "cuba", "peru", "mali", "oman", "chile"}
DEMONYMS = {"american": "US", "americans": "US", "russian": "RU", "russians": "RU", "ukrainian": "UA", "ukrainians": "UA", "israeli": "IL", "israelis": "IL",
            "iranian": "IR", "iranians": "IR", "chinese": "CN", "palestinian": "PS", "palestinians": "PS", "lebanese": "LB", "syrian": "SY", "iraqi": "IQ",
            "saudi": "SA", "saudis": "SA", "yemeni": "YE", "houthi": "YE", "houthis": "YE", "turkish": "TR", "indian": "IN", "pakistani": "PK", "afghan": "AF",
            "japanese": "JP", "north korean": "KP", "south korean": "KR", "taiwanese": "TW", "british": "GB", "french": "FR", "german": "DE", "polish": "PL",
            "italian": "IT", "spanish": "ES", "mexican": "MX", "canadian": "CA", "brazilian": "BR", "venezuelan": "VE", "colombian": "CO", "cuban": "CU",
            "haitian": "HT", "egyptian": "EG", "sudanese": "SD", "ethiopian": "ET", "somali": "SO", "kenyan": "KE", "nigerian": "NG", "congolese": "CD",
            "south african": "ZA", "australian": "AU", "filipino": "PH", "philippine": "PH", "indonesian": "ID", "vietnamese": "VN", "thai": "TH", "burmese": "MM",
            "bangladeshi": "BD", "nepali": "NP", "greek": "GR", "serbian": "RS", "hungarian": "HU", "romanian": "RO", "belarusian": "BY", "georgian": "GE",
            "armenian": "AM", "azerbaijani": "AZ", "kazakh": "KZ", "qatari": "QA", "emirati": "AE", "jordanian": "JO", "libyan": "LY", "tunisian": "TN",
            "algerian": "DZ", "moroccan": "MA", "malian": "ML", "gazan": "PS", "swedish": "SE", "norwegian": "NO", "finnish": "FI", "danish": "DK", "dutch": "NL",
            "belgian": "BE", "swiss": "CH", "austrian": "AT", "czech": "CZ", "slovak": "SK", "irish": "IE", "portuguese": "PT", "argentine": "AR",
            "argentinian": "AR", "chilean": "CL", "peruvian": "PE", "ecuadorian": "EC", "bolivian": "BO", "kremlin": "RU", "pentagon": "US", "idf": "IL", "ukrainian-": "UA"}
SPECIAL_CITY = {"washington": ("Washington", "US"), "washington dc": ("Washington", "US"), "washington d c": ("Washington", "US"), "dc": ("Washington", "US"),
                "gaza": ("Gaza", "PS"), "kyiv": ("Kyiv", "UA"), "kiev": ("Kyiv", "UA"), "new york": ("New York City", "US"), "new york city": ("New York City", "US"),
                "nyc": ("New York City", "US"), "mexico city": ("Mexico City", "MX"), "tehran": ("Tehran", "IR"), "moscow": ("Moscow", "RU"),
                "beirut": ("Beirut", "LB"), "jerusalem": ("Jerusalem", "IL"), "la": None}
BROAD_REGIONS = ["Middle East", "Europe", "European Union", "Africa", "Asia", "Latin America", "South America", "North America", "Central America", "Caribbean",
                 "Balkans", "Sahel", "Horn of Africa", "Persian Gulf", "the Gulf", "Gulf states", "Southeast Asia", "East Asia", "Central Asia", "South Asia",
                 "Scandinavia", "Baltics", "Baltic states", "Eastern Europe", "Western Europe", "West Africa", "East Africa", "Southern Africa", "Central Africa",
                 "North Africa", "Pacific", "Indo-Pacific", "Arctic", "Antarctica", "Midwest", "Midwestern", "West Coast", "East Coast", "Gulf Coast", "Red Sea", "Black Sea"]
BROAD_RE = re.compile(r"\b(" + "|".join(re.escape(x) for x in sorted(BROAD_REGIONS, key=len, reverse=True)) + r")\b")
NONGEO_CATS = {"cyber", "financial", "ufo/uap", "spiritual/religious", "other"}
FLAG_RE = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
US_POSTAL = {}
US_POSTAL_KEYS = set()
METHOD_LABEL = {"source_coords": "Coordinates in the source data", "location_field": "Alert's location field", "gazetteer": "Place name in the text (offline gazetteer)",
                "nominatim": "OpenStreetMap Nominatim lookup"}
REASON_LABEL = {"no_place": "No place mentioned", "nationality_only": "Only nationality words or flags, no place named", "ambiguous": "Ambiguous place name",
                "multi_place": "Several equally weighted places", "non_geo": "Non-geographic topic", "global": "Source marks it as global",
                "not_found": "Place not found in gazetteer or geocoder", "broad_region": "Only a multi-country or very broad region named", "geocoder_error": "Geocoder error (will retry)", "pending": "Waiting for online geocoder (next pass)"}

# ------------------------------------------------------------------ gazetteer
class Gaz:
    def __init__(self):
        t = time.time()
        self.countries = json.load(open(os.path.join(DATA, "countries.json")))
        self.admin1 = json.load(open(os.path.join(DATA, "admin1.json")))
        self.cities = json.load(open(os.path.join(DATA, "cities.json")))     # [name, ascii, lat, lon, cc, a1code, pop, fcode, alts]
        self.common = set(COMMON_HARD) | self._corpus_common()
        self.idx = {}
        def add(k, ref):
            if not k or k in MONTHS: return
            L = self.idx.setdefault(k, [])
            if ref not in L: L.append(ref)
        for iso2, c in self.countries.items():
            for n in {c["name"], *c.get("ne_names", []), *COUNTRY_ALIASES.get(iso2, [])}:
                add(key_of(n), ("country", iso2))
        for code, a in self.admin1.items():
            cc = code.split(".")[0]
            names = {a["name"], a["ascii"], *a.get("alts", [])}
            if cc == "US" and a.get("postal"): US_POSTAL[a["postal"]] = code
            for n in names:
                k = key_of(n)
                if len(k) < 4 or k in GENERIC or k in self.common: continue
                if cc != "US" and len(n) <= 3: continue
                add(k, ("admin1", code))
        self.by_name_cc = {}
        for i, c in enumerate(self.cities):
            for n in {c[0], c[1]}:
                add(key_of(n), ("city", i)); self.by_name_cc.setdefault((key_of(n), c[4]), i)
            if c[6] >= 50000:
                for n in c[8]:
                    k = key_of(n)
                    if len(k) >= 5 and k not in self.common: add(k, ("cityalt", i))
        for d, cc in DEMONYMS.items(): self.idx.setdefault(key_of(d), []).insert(0, ("demonym", cc))
        # spatial grid for nearest-city lookups
        self.grid = {}
        for i, c in enumerate(self.cities): self.grid.setdefault((int(c[2] // 1), int(c[3] // 1)), []).append(i)
        self.a1_by_name = {}
        for code, a in self.admin1.items():
            for n in {a["name"], a["ascii"], *a.get("alts", [])}: self.a1_by_name.setdefault((code.split(".")[0], key_of(n)), code)
        self.load_s = round(time.time() - t, 2)
        self.polys = None

    def _corpus_common(self):
        """Words the alert corpus itself uses in lower case (e.g. 'police', 'deal'): such place names need extra context."""
        cnt = {}
        try:
            c = bdb()
            for (t,) in c.execute("SELECT title FROM alerts ORDER BY first_seen DESC LIMIT 20000"):
                t = re.sub(r"https?://\S+|www\.\S+|[#@]\w+|\S+\.(com|org|net|io|co|gov)\S*", " ", t or "")
                for w in TOK.findall(fold(t)):
                    if w.islower() and len(w) > 2: cnt[w] = cnt.get(w, 0) + 1
            c.close()
        except Exception: pass
        return {w for w, n in cnt.items() if n >= 5}

    def city(self, i):
        c = self.cities[i]
        return {"name": c[0], "lat": c[2], "lon": c[3], "cc": c[4], "a1": c[5], "pop": c[6], "fcode": c[7]}

    def nearest_city(self, lat, lon, max_km=30):
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self.grid.get((int(lat // 1) + dx, int(lon // 1) + dy), []):
                    c = self.cities[i]; d = hav(lat, lon, c[2], c[3])
                    if d <= max_km and (best is None or d < best[0]): best = (d, i)
        return self.city(best[1]) if best else None

    # ---- point in polygon (Natural Earth, simplified) for coordinates
    def _load_polys(self):
        P = {"a0": [], "a1": []}
        for lvl, fn in (("a0", "admin0.geojson"), ("a1", "admin1.geojson")):
            d = json.load(open(os.path.join(STATIC, fn)))
            for f in d["features"]:
                pr = f["properties"]; g = f["geometry"]
                if not g: continue
                polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
                for poly in polys:
                    xs = [p[0] for p in poly[0]]; ys = [p[1] for p in poly[0]]
                    P[lvl].append(((min(xs), min(ys), max(xs), max(ys)), poly, pr))
        self.polys = P

    def pip(self, lat, lon):
        if self.polys is None: self._load_polys()
        out = {}
        for lvl in ("a1", "a0"):
            for (x0, y0, x1, y1), poly, pr in self.polys[lvl]:
                if x0 <= lon <= x1 and y0 <= lat <= y1 and inpoly(lon, lat, poly[0]) and not any(inpoly(lon, lat, h) for h in poly[1:]):
                    out[lvl] = pr; break
        cc = None; a1 = None
        if "a1" in out:
            cc = out["a1"].get("iso_a2"); a1 = out["a1"].get("gn_a1_code")
        if "a0" in out and (not cc or cc == "-1"): cc = out["a0"].get("ISO_A2_EH")
        if cc in (None, "-1", "-99"): cc = None
        if a1 and a1 not in self.admin1: a1 = None
        return cc, a1

def inpoly(x, y, ring):
    ins = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi: ins = not ins
        j = i
    return ins

def hav(a, b, c, d):
    import math
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))

_GAZ = [None]
def gaz():
    if _GAZ[0] is None:
        with _lock:
            if _GAZ[0] is None: _GAZ[0] = Gaz()
    return _GAZ[0]

# ------------------------------------------------------------------ text extraction
def extract(text, ctx_cc=None, trust=False):
    """Find place mentions in free text. Returns dict with accepted matches, context countries, rejected/ambiguous info, unmatched locative spans.
    trust=True for a location field (every capitalised span there is meant to be a place)."""
    G = gaz(); raw = text or ""
    flags = []
    for f in FLAG_RE.findall(raw):
        cc = "".join(chr(ord(ch) - 0x1F1E6 + 65) for ch in f)
        if cc in G.countries: flags.append(cc)
    t = fold(raw)
    toks = [(re.sub(r"'s$", "", m.group(0)), m.start(), m.end()) for m in TOK.finditer(t)]
    words = [w for w, _, _ in toks]
    caps = [w[0].isupper() for w in words]
    letters = [ch for ch in t if ch.isalpha()]
    upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
    title_case = len(words) >= 4 and sum(caps) / len(words) > 0.7
    shouting = upper_ratio > 0.6
    found = []          # (i, n, key, refs)
    i = 0
    while i < len(words):
        hit = None
        for n in (5, 4, 3, 2, 1):
            if i + n > len(words): continue
            seg = words[i:i + n]
            if n > 1 and any(nw(s) in CONNECT for s in (seg[0], seg[-1])): continue
            k = " ".join(nw(s) for s in seg)
            if k in G.idx or k in SPECIAL_CITY:
                # sentence position: first word of the text or after . ! ? : is "sentence start"
                if not (caps[i] or trust or (i > 0 and nw(words[i - 1]) in STRONG_CUES)): continue
                if n == 1 and words[i].replace(".", "").isupper() and len(words[i].replace(".", "")) <= 4 and k not in CAPS_ONLY and not trust and k not in SPECIAL_CITY: continue   # acronyms (NIS, SEC, WHO)
                if n == 1 and k in CAPS_ONLY and not (words[i].replace(".", "").isupper() and not shouting): continue
                if (k in CAPS_ONLY or k.replace(" ", "") in CAPS_ONLY) and not words[i][0].isupper(): continue
                hit = (i, n, k, list(G.idx.get(k, [])))
                break
        if hit: found.append(hit); i += hit[1]
        else: i += 1
    ctx = {}                                   # country -> weight of evidence (names, demonyms, flags)
    def bump(cc, w):
        if cc: ctx[cc] = ctx.get(cc, 0) + w
    for cc in flags: bump(cc, 0.5)
    if ctx_cc: bump(ctx_cc, 2)
    demonyms = []
    for (i, n, k, refs) in found:
        kinds = {r[0] for r in refs}
        if "demonym" in kinds: demonyms.append(words[i]); bump([r for r in refs if r[0] == "demonym"][0][1], 0.5)
        for r in refs:
            if r[0] == "country" and k not in NEEDS_CTX_COUNTRY and k not in COMMON_HARD: bump(r[1], 1)
            if r[0] == "admin1" and r[1].startswith("US.") and len(k) > 3 and k not in NEEDS_CTX_COUNTRY and not any(x[0] == "country" for x in refs): bump("US", 0.6)
    # "City, ST" / "City, State" / "City, Country" patterns
    pairs = {}
    for m in re.finditer(r"([A-Z][A-Za-z.'\- ]{1,40}?),\s*([A-Z]{2}|[A-Z][a-z]+(?: [A-Z][a-z]+)?)\b", t):
        a, b = m.group(1).strip(), m.group(2)
        aw = a.split()
        keys = [key_of(" ".join(aw[-n:])) for n in (1, 2, 3) if len(aw) >= n]
        val = None
        if len(b) == 2 and b in US_POSTAL: val = ("US", US_POSTAL[b]); bump("US", 1)
        elif key_of(b) in G.idx:
            for r in G.idx[key_of(b)]:
                if r[0] == "country": val = (r[1], None); break
                if r[0] == "admin1": val = (r[1].split(".")[0], r[1]); break
        if val:
            for k2 in keys: pairs[k2] = val
    m = re.search(r"\bNWS [A-Za-z./ -]+? ([A-Z]{2})\b", t)
    if m and m.group(1) in US_POSTAL: bump("US", 2); pairs["__nws__"] = ("US", US_POSTAL[m.group(1)])
    ctx_a1 = {v[1] for v in pairs.values() if v[1]}
    acc, rejected, qual = [], [], []
    for (i, n, k, refs) in found:
        prev = nw(words[i - 1]) if i > 0 else ""
        cue = prev in LOC_CUES
        strong_cue = prev in STRONG_CUES
        before_cap = i > 0 and caps[i - 1] and prev not in CONNECT and not cue and not _sent_start(t, toks, i)
        after_cap = i + n < len(words) and caps[i + n] and nw(words[i + n]) not in CONNECT and not _sent_start(t, toks, i + n)
        person_like = (before_cap or after_cap) and not title_case and not trust
        common = k in G.common
        pair = pairs.get(k)
        cands = []
        if k in SPECIAL_CITY and SPECIAL_CITY[k]:
            nm, cc = SPECIAL_CITY[k]; ci = G.by_name_cc.get((key_of(nm), cc))
            if ci is not None and not (k == "washington" and i + 1 < len(words) and nw(words[i + 1]) == "state"):
                refs = [("city", ci)] + [r for r in refs if r[0] == "country"]
        countries = [r[1] for r in refs if r[0] == "country"]
        a1s = [r[1] for r in refs if r[0] == "admin1"]
        cities = [r[1] for r in refs if r[0] == "city"]
        alt_only = not cities and any(r[0] == "cityalt" for r in refs)
        if alt_only: cities = [r[1] for r in refs if r[0] == "cityalt"]
        nxt = nw(words[i + n]) if i + n < len(words) else ""
        org_next = after_cap and nxt in G.common and nxt not in LOCATIONAL     # "Ariel School", "Chicago Fire"
        if countries and not (k in NEEDS_CTX_COUNTRY and not (strong_cue or trust)):
            cc = countries[0]
            if k == "georgia" or (a1s and k in NEEDS_CTX_COUNTRY):
                pass
            else:
                acc.append({"level": "country", "cc": cc, "a1": None, "i": i, "k": k, "text": " ".join(words[i:i + n]), "conf": "high" if trust else "medium", "cue": strong_cue}); continue
        if a1s:
            # prefer admin1 in a context country; US states win by default only with US context or when unique
            pick = [a for a in a1s if a.split(".")[0] in ctx] or ([a for a in a1s if a.startswith("US.")] if "US" in ctx or len(a1s) == 1 else [])
            if k == "georgia":
                if "GE" in ctx and "US" not in ctx: acc.append({"level": "country", "cc": "GE", "a1": None, "i": i, "k": k, "text": "Georgia", "conf": "medium"}); continue
                if "US" not in ctx: rejected.append({"text": "Georgia", "why": "ambiguous", "cands": ["Georgia (US state)", "Georgia (country)"]}); continue
                pick = ["US.GA"]
            big_city = [c for c in cities if G.cities[c][6] >= 500000 and G.cities[c][5] in a1s]
            if big_city and not pair:
                cities = big_city   # e.g. Kyiv / New York: the city, not the province
            elif pick and len({p.split(".")[0] for p in pick}) == 1 and not (common and not (trust or strong_cue or pick[0].split(".")[0] in ctx)):
                if len(pick) == 1 or trust:
                    acc.append({"level": "state", "cc": pick[0].split(".")[0], "a1": pick[0], "i": i, "k": k, "text": " ".join(words[i:i + n]), "conf": "high" if trust else "medium", "cue": strong_cue}); continue
            elif len(a1s) > 1 and not cities:
                rejected.append({"text": " ".join(words[i:i + n]), "why": "ambiguous", "cands": [f"{G.admin1[a]['name']} ({a.split('.')[0]})" for a in a1s[:5]]}); continue
        if cities:
            C = [G.city(c) | {"i": c} for c in cities]
            if pair and pair[0]:
                f = [c for c in C if c["cc"] == pair[0] and (not pair[1] or c["a1"] == pair[1])]
                if not f:   # "Hamilton, TN": the gazetteer's Hamiltons are elsewhere, so ask the geocoder with the qualifier
                    nm = " ".join(words[i:i + n]); st = G.admin1.get(pair[1], {}).get("name") if pair[1] else G.countries.get(pair[0], {}).get("name")
                    qual.append((f"{nm}, {st}", pair[0], pair[1])); continue
                C = f
            elif ctx:
                f = [c for c in C if c["cc"] in ctx]
                if f:
                    top = max(ctx[c["cc"]] for c in f); C = [c for c in f if ctx[c["cc"]] == top]
                if ctx_a1:
                    f2 = [c for c in C if c["a1"] in ctx_a1]
                    if f2: C = f2
            C.sort(key=lambda c: -c["pop"])
            uniq = []
            for c in C:
                if not any(u["cc"] == c["cc"] and u["a1"] == c["a1"] and hav(u["lat"], u["lon"], c["lat"], c["lon"]) < 40 for u in uniq): uniq.append(c)
            if len(uniq) > 1 and uniq[0]["pop"] < 3 * uniq[1]["pop"]:
                if (strong_cue or trust or (not common and not person_like)) and uniq[0]["pop"] >= 15000:
                    rejected.append({"text": " ".join(words[i:i + n]), "why": "ambiguous",
                                     "cands": [f"{u['name']} ({G.admin1.get(u['a1'], {}).get('name', '?')}, {u['cc']})" for u in uniq[:5]]})
                continue
            c = uniq[0]
            ctx_ok = bool(pair) or c["cc"] in ctx or c["a1"] in ctx_a1
            ok, conf = False, "low"
            if trust: ok, conf = True, ("high" if ctx_ok or len(uniq) == 1 else "medium")
            elif ctx_ok and not (common and not strong_cue and c["cc"] not in ctx): ok, conf = True, "high" if (pair or strong_cue) else "medium"
            elif strong_cue and not common and not org_next: ok, conf = True, "medium" if c["pop"] >= 50000 else "low"
            elif alt_only and (after_cap or before_cap): ok = False
            elif cue and not common and not person_like and not org_next and c["pop"] >= 40000: ok, conf = True, "low"     # alternate spellings next to other names ("Kash Patel") need context
            elif not common and not person_like and not org_next and c["pop"] >= (500000 if title_case else 250000): ok, conf = True, "medium" if c["pop"] >= 1000000 else "low"
            elif not common and not person_like and not org_next and n >= 2 and c["pop"] >= 50000 and not alt_only: ok, conf = True, "low"
            if ok:
                acc.append({"level": "city", "cc": c["cc"], "a1": c["a1"], "i": i, "k": k, "city": c, "text": " ".join(words[i:i + n]), "conf": conf, "cue": strong_cue})
    # unmatched capitalised spans right after a strong locative cue (candidates for the online geocoder)
    spans = []
    matched_pos = {j for (i, n, k, r) in found for j in range(i, i + n)}
    for j, w in enumerate(words):
        j0 = j + 2 if j + 2 < len(words) and nw(words[j + 1]) == "the" else j + 1
        if nw(w) in STRONG_CUES and j0 < len(words) and caps[j0] and j0 not in matched_pos:
            seg = []
            for q in range(j0, min(j0 + 4, len(words))):
                if re.search(r"[a-z][A-Z]", words[q]): break      # CamelCase hashtags such as WhiteHouse
                if caps[q] and q not in matched_pos and (not seg or nw(words[q]) not in G.common or nw(words[q]) in LOCATIONAL or nw(words[q]) in ("strait", "gulf", "sea")): seg.append(words[q])
                elif seg and nw(words[q]) in ("al", "el", "de", "of") and q + 1 < len(words) and caps[q + 1]: seg.append(words[q])
                else: break
            while seg and nw(seg[-1]) in CONNECT | G.common - LOCATIONAL: seg.pop()
            s = " ".join(seg)
            ks = key_of(s)
            first_ok = nw(seg[0]) not in G.common or nw(seg[0]) in ("strait", "gulf", "sea") if seg else False
            if seg and len(ks) >= 4 and ks not in G.common and nw(seg[0]) not in MONTHS and first_ok and not shouting and not s.isupper():
                spans.append(s)
    return {"acc": acc, "ctx": ctx, "ctx_a1": ctx_a1, "rejected": rejected, "demonyms": demonyms, "flags": flags, "spans": spans[:2], "pairs": pairs, "qual": qual[:2], "trust": trust}

def _sent_start(t, toks, i):
    if i == 0: return True
    gap = t[toks[i - 1][2]:toks[i][1]]
    return bool(re.search(r"[.!?:|\n\-–—\"“(\[]", gap))

def choose(ex):
    """Pick the most specific consistent place. Returns (result_dict | None, reason_code, reason_text, candidates)."""
    G = gaz(); acc = ex["acc"]
    if not acc: return None, None, None, None
    for lvl in ("city", "state", "country"):
        L = [a for a in acc if a["level"] == lvl]
        if not L: continue
        bycc = {}
        for a in L: bycc.setdefault(a["cc"], []).append(a)
        if len(bycc) > 1 and ex.get("trust"):
            first = sorted(L, key=lambda a: a["i"])[0]
            return dict(first, conf="medium", others=sorted({x["text"] for x in L if x["cc"] != first["cc"]})), None, None, None
        if len(bycc) > 1:
            # weigh by every mention of that country (its cities, states, name, demonyms, flags)
            w = {cc: len(v) + 0.5 * sum(1 for a in v if a.get("cue")) + ex["ctx"].get(cc, 0) + 0.3 * sum(1 for a in acc if a["cc"] == cc and a["level"] != lvl) for cc, v in bycc.items()}
            best = sorted(w.items(), key=lambda x: -x[1])
            if best[0][1] - best[1][1] < 0.75:
                names = [f"{a['text']} ({G.countries.get(a['cc'], {}).get('name', a['cc'])})" for cc in bycc for a in bycc[cc][:1]]
                return None, "multi_place", "Several places in different countries carry equal weight: " + ", ".join(names[:5]), names[:6]
            L = bycc[best[0][0]]
        else: L = list(bycc.values())[0]
        a = sorted(L, key=lambda a: a["i"])[0]
        if lvl == "city" and len({x["a1"] for x in L}) > 1 and a["conf"] == "high": a = dict(a, conf="medium")
        others = sorted({x["text"] for x in acc if x is not a and x["cc"] == a["cc"]})
        return dict(a, others=others), None, None, None
    return None, None, None, None

# ------------------------------------------------------------------ Nominatim (cached, 1 req/s)
NOM_NATURAL = {"strait", "bay", "sea", "gulf", "peninsula", "cape", "island", "archipelago", "lake", "volcano", "mountain_range", "water", "reef", "channel"}
NOM_OK_TYPES = {"city", "town", "village", "municipality", "county", "state", "province", "region", "district", "borough", "suburb", "island", "archipelago",
                "country", "state_district", "city_district", "neighbourhood", "quarter", "hamlet", "administrative", "locality", "territory", "islet"}
class NomBudget:
    def __init__(self, n): self.left = n; self.calls = 0

def nominatim(q, cc=None, budget=None):
    """Returns (status, list_of_results). status: ok | empty | error | skipped (no budget)."""
    key = (q.strip().lower() + ("|" + cc.lower() if cc else ""))[:300]
    with _lock:
        c = gdb(); r = c.execute("SELECT status, result, fetched_at FROM nominatim_cache WHERE q=?", (key,)).fetchone(); c.close()
    if r and not (r["status"] == "error" and time.time() - datetime.strptime(r["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() > 3600):
        return r["status"], json.loads(r["result"] or "[]")
    if budget is None or budget.left <= 0: return "skipped", []
    budget.left -= 1; budget.calls += 1
    params = {"q": q, "format": "jsonv2", "limit": 3, "addressdetails": 1, "accept-language": "en"}
    if cc: params["countrycodes"] = cc.lower()
    with _nom_lock:
        wait = 1.1 - (time.time() - _last_nom[0])
        if wait > 0: time.sleep(wait)
        try:
            req = urllib.request.Request(NOM_URL + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp: res = json.loads(resp.read().decode())
            st = "ok" if res else "empty"
        except Exception as ex:
            res, st = [{"error": str(ex)[:200]}], "error"
        _last_nom[0] = time.time()
    with _lock:
        c = gdb(); c.execute("INSERT OR REPLACE INTO nominatim_cache VALUES(?,?,?,?)", (key, st, json.dumps(res), iso(now()))); c.commit(); c.close()
    return st, res

def nom_pick(res, cc=None, min_imp=0.45, a1=None):
    for r in res or []:
        if "error" in r: continue
        cat = r.get("category") or r.get("class"); typ = r.get("addresstype") or r.get("type")
        if cat == "natural" and (r.get("type") in NOM_NATURAL or typ in NOM_NATURAL): pass
        elif cat not in ("place", "boundary") or typ not in NOM_OK_TYPES: continue
        ad = r.get("address") or {}; rcc = (ad.get("country_code") or "").upper()
        if cc and rcc != cc: continue
        imp = r.get("importance") or 0
        town = typ in ("city", "town", "village", "hamlet", "municipality")
        if imp < min_imp and not (town and imp >= min(min_imp, 0.35) and sum(1 for x in res if (x.get("category") or x.get("class")) in ("place", "boundary")) == 1): continue
        if a1:
            lvl4 = ad.get("ISO3166-2-lvl4") or ""
            G = gaz(); want = G.admin1.get(a1, {}).get("postal")
            if want and lvl4 and lvl4 != f"US-{want}": continue
        return r
    return None

def nom_to_geo(r):
    G = gaz(); ad = r.get("address") or {}; cc = (ad.get("country_code") or "").upper() or None
    typ = r.get("addresstype") or r.get("type")
    if (r.get("category") or r.get("class")) == "natural":
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "cc": cc, "a1": None, "prec": "state", "place": r.get("display_name", "")[:160], "city": None}
    prec = {"country": "country", "state": "state", "province": "state", "region": "state", "territory": "state", "county": "county",
            "state_district": "county", "district": "county", "archipelago": "state"}.get(typ, "city")
    st = ad.get("state") or ad.get("province") or ad.get("region")
    a1 = G.a1_by_name.get((cc, key_of(st))) if st and cc else None
    lvl4 = ad.get("ISO3166-2-lvl4") or ""
    if not a1 and lvl4.startswith("US-"): a1 = US_POSTAL.get(lvl4[3:])
    city = ad.get("city") or ad.get("town") or ad.get("village") or ad.get("municipality")
    return {"lat": float(r["lat"]), "lon": float(r["lon"]), "cc": cc, "a1": a1, "prec": prec, "place": r.get("display_name", "")[:160], "city": city}

# ------------------------------------------------------------------ one alert
def geocode(cl, members, budget):
    """cl: cluster row (dict). members: member alert rows. Returns dict for geo.db."""
    G = gaz()
    out = {"id": cl["cluster_id"], "lat": None, "lon": None, "place": None, "country": None, "country_name": None, "admin1": None, "admin1_code": None,
           "city": None, "precision": None, "method": None, "method_detail": None, "confidence": None, "located": 0, "reason_code": None,
           "reason_unlocated": None, "candidates": None, "evidence": None}
    def fill(lat, lon, cc, a1, prec, method, detail, conf, place, city=None, evidence=None):
        if (cc is None or a1 is None) and lat is not None and prec in ("point", "city", "county"):
            pc, pa = G.pip(lat, lon)
            cc = cc or pc; a1 = a1 or (pa if (pa or "").split(".")[0] == cc else None)
        if a1 and not cc: cc = a1.split(".")[0]
        out.update(lat=round(lat, 5), lon=round(lon, 5), country=cc, country_name=G.countries.get(cc, {}).get("name") if cc else None,
                   admin1_code=a1, admin1=G.admin1.get(a1, {}).get("name") if a1 else None, city=city, precision=prec, method=method,
                   method_detail=detail, confidence=conf, place=(place or "")[:200], located=1, evidence=(evidence or "")[:300])
        return out
    title = cl.get("title") or ""
    locs = [x for x in [cl.get("location")] + [m.get("location") for m in members] if x]
    # 1) coordinates already in the source data
    srcs = sorted([m for m in members if m.get("lat") is not None and m.get("lon") is not None], key=lambda m: {"USGS": 0, "GDACS": 1, "tsunami.gov": 2}.get(m["source"], 3))
    lat, lon, det = None, None, None
    if cl.get("lat") is not None and cl.get("lon") is not None: lat, lon, det = cl["lat"], cl["lon"], (srcs[0]["source"] if srcs else "scanner cluster")
    elif srcs: lat, lon, det = srcs[0]["lat"], srcs[0]["lon"], srcs[0]["source"]
    if lat is not None and -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
        loc = (srcs[0].get("location") if srcs else None) or cl.get("location") or ""
        pc, pa = G.pip(lat, lon)
        cc, a1 = pc, pa
        if not cc and loc:      # offshore: take the country named in the location text
            ex = extract(loc, trust=True); ch, *_ = choose(ex)
            if ch: cc = ch["cc"]
        nc = G.nearest_city(lat, lon)
        place = loc if loc and not loc.startswith("Global") else (title[:120])
        return fill(lat, lon, cc, a1, "point", "source_coords", det, "high", place, city=nc["name"] if nc else None, evidence=f"{det} lat/lon {lat:.3f}, {lon:.3f}")
    # brief "WHERE: ... (approx. lat, lon)" written by the scanner from source data
    m = re.search(r"WHERE: (.+?) \(approx\. (-?\d+\.\d+), (-?\d+\.\d+)\)", cl.get("brief") or "")
    if m:
        la, lo = float(m.group(2)), float(m.group(3))
        nc = G.nearest_city(la, lo)
        return fill(la, lo, None, None, "point", "source_coords", "scanner brief (source coordinates)", "high", m.group(1), city=nc["name"] if nc else None, evidence=m.group(0)[:200])
    # 2a) the alert's existing location field
    for loc in locs:
        if loc.startswith("Global"):
            out.update(reason_code="global", reason_unlocated=f"Source marks the location as \"{loc}\", not a place on the map"); return out
    for loc in locs:
        nws = re.search(r"\bby NWS ([A-Za-z./ -]+?) ([A-Z]{2})\b", title)
        zones = [z.strip() for z in loc.split(";") if z.strip()]
        if nws and nws.group(2) in US_POSTAL:
            a1 = US_POSTAL[nws.group(2)]; stn = G.admin1[a1]["name"]
            pts = []
            for z in zones[:3]:
                zc = re.sub(r"^(Coastal|Inland|Mainland|Northern|Southern|Eastern|Western|Central|North|South|East|West|Northwest|Northeast|Southwest|Southeast|Upper|Lower|Interior|Greater)\s+", "", z)
                zc = re.sub(r"\s+(County|Parish|Barrier Islands|Plains|Mountains|Mtns|Coast|Valley|Lowlands|Highlands|Foothills)$", "", zc)
                if len(zc) < 3: continue
                for q in (f"{zc} County, {stn}", f"{zc}, {stn}"):
                    st, res = nominatim(q, "US", budget)
                    if st == "skipped": return dict(out, reason_code="pending", reason_unlocated="NWS zones queued for the online geocoder (next pass)")
                    r = nom_pick(res, "US", 0.0, a1)
                    if r: pts.append((nom_to_geo(r), z)); break
            if pts:
                la = sum(p[0]["lat"] for p in pts) / len(pts); lo = sum(p[0]["lon"] for p in pts) / len(pts)
                place = ", ".join(zones[:3]) + (f" +{len(zones) - 3} more zones" if len(zones) > 3 else "") + f" ({stn})"
                return fill(la, lo, "US", a1, "county", "location_field", f"NWS zone list → Nominatim ({len(pts)} of {min(3, len(zones))} zones)", "medium", place,
                            evidence=f"zones: {'; '.join(p[1] for p in pts)}")
            lab = G.admin1[a1].get("label")
            if lab:
                return fill(lab[0], lab[1], "US", a1, "state", "location_field", "NWS issuing office state (zones not resolvable)", "medium",
                            f"{', '.join(zones[:3])} ({stn})", evidence=nws.group(0))
        ex = extract(loc, trust=True)
        ch, rc, rt, cands = choose(ex)
        if ch: return place_from(ch, out, fill, "location_field", f"location field \"{loc[:80]}\"", loc)
        st, res = nominatim(loc[:120], None, budget)
        if st == "skipped": return dict(out, reason_code="pending", reason_unlocated=f"Location field \"{loc[:60]}\" queued for the online geocoder")
        r = nom_pick(res, None, 0.3)
        if r:
            g = nom_to_geo(r)
            return fill(g["lat"], g["lon"], g["cc"], g["a1"], g["prec"], "nominatim", f"location field → Nominatim \"{loc[:60]}\"", "medium", g["place"], city=g["city"], evidence=loc)
    # 2b) place names in the title (then the other source titles in the story)
    texts = [title] + [m["title"] for m in sorted(members, key=lambda m: -(m.get("official") or 0)) if m.get("title") and m["title"] != title][:5]
    first_fail = None; spans_all = []; quals = []; demonyms = set(); flags = set(); rejected = []
    for n, tx in enumerate(texts):
        ex = extract(tx)
        ch, rc, rt, cands = choose(ex)
        if ch: return place_from(ch, out, fill, "gazetteer", "title" if n == 0 else "another source's title in this story", tx)
        if rc and not first_fail: first_fail = (rc, rt, cands)
        rejected += ex["rejected"]; spans_all += [(s, ex["ctx"]) for s in ex["spans"]]; quals += ex["qual"]; demonyms |= set(ex["demonyms"]); flags |= set(ex["flags"])
    if first_fail and not quals:
        return dict(out, reason_code=first_fail[0], reason_unlocated=first_fail[1], candidates=json.dumps(first_fail[2]))
    if rejected and not quals:
        r = rejected[0]
        return dict(out, reason_code="ambiguous", reason_unlocated=f"\"{r['text']}\" matches several places: " + "; ".join(r["cands"]), candidates=json.dumps(r["cands"]))
    broad = []
    for tx in texts:
        broad += [m.group(1) for m in BROAD_RE.finditer(fold(tx))]
    if broad and not rejected and not first_fail:
        b0 = list(dict.fromkeys(broad))
        return dict(out, reason_code="broad_region", reason_unlocated="Names only a broad region (" + ", ".join(b0[:3]) + "), too large to place as one spot on the map")
    # 3) Nominatim fallback: first "Name, ST" pairs the gazetteer could not resolve, then a capitalised name right after "in / near / outside …"
    tried = []
    for q, cc, a1 in quals[:2]:
        st, res = nominatim(q, cc, budget)
        if st == "skipped": return dict(out, reason_code="pending", reason_unlocated=f"\"{q}\" queued for the online geocoder")
        if st == "error": return dict(out, reason_code="geocoder_error", reason_unlocated=f"Nominatim error for \"{q}\": {(res[0].get('error') if res else '')[:80]}")
        r = nom_pick(res, cc, 0.0, a1)
        if r:
            g = nom_to_geo(r)
            return fill(g["lat"], g["lon"], g["cc"], g["a1"], g["prec"], "nominatim", f"\"{q}\" → Nominatim", "medium", g["place"], city=g["city"], evidence=q)
        tried.append(q)
    for s, ctx in spans_all[:2]:
        cc = max(ctx, key=ctx.get) if ctx else None
        st, res = nominatim(s, cc, budget)
        if st == "skipped": return dict(out, reason_code="pending", reason_unlocated=f"\"{s}\" queued for the online geocoder")
        if st == "error": return dict(out, reason_code="geocoder_error", reason_unlocated=f"Nominatim error for \"{s}\": {(res[0].get('error') if res else '')[:80]}")
        r = nom_pick(res, cc, 0.3 if cc else 0.5)
        if r:
            g = nom_to_geo(r)
            return fill(g["lat"], g["lon"], g["cc"], g["a1"], g["prec"], "nominatim", f"\"{s}\" → Nominatim" + (f" (limited to {cc})" if cc else ""), "low" if not cc else "medium",
                        g["place"], city=g["city"], evidence=s)
        tried.append(s)
    if tried:
        return dict(out, reason_code="not_found", reason_unlocated="A capitalised name after \"in / near …\" was not found as a place in the offline gazetteer or by a confident Nominatim match: " + ", ".join(f"\"{s}\"" for s in dict.fromkeys(tried)))
    cat = (cl.get("category") or "").lower()
    if demonyms or flags:
        bits = sorted(demonyms) + [f"flag {f}" for f in sorted(flags)]
        return dict(out, reason_code="nationality_only", reason_unlocated="No place named, only nationality words or flags: " + ", ".join(bits[:6]) + " (these say who, not where)")
    if cat in NONGEO_CATS:
        return dict(out, reason_code="non_geo", reason_unlocated=f"Non-geographic topic ({cat}) and no place named")
    return dict(out, reason_code="no_place", reason_unlocated="The source text names no place")

def place_from(ch, out, fill, method, detail, text):
    G = gaz(); cc, a1 = ch["cc"], ch.get("a1")
    if ch["level"] == "city":
        c = ch["city"]
        return fill(c["lat"], c["lon"], c["cc"], c["a1"] if c["a1"] in G.admin1 else None, "city", method, detail, ch["conf"],
                    f"{c['name']}, {G.admin1.get(c['a1'], {}).get('name', '')}, {G.countries.get(c['cc'], {}).get('name', c['cc'])}".replace(", ,", ","),
                    city=c["name"], evidence=f"matched \"{ch['text']}\"" + (f"; also mentions {', '.join(ch['others'][:4])}" if ch.get("others") else ""))
    if ch["level"] == "state":
        a = G.admin1[a1]; lab = a.get("label") or G.countries.get(cc, {}).get("label")
        if not lab: return dict(out, reason_code="not_found", reason_unlocated=f"\"{ch['text']}\" matched {a['name']} but the gazetteer has no centroid for it")
        return fill(lab[0], lab[1], cc, a1, "state", method, detail, ch["conf"], f"{a['name']}, {G.countries.get(cc, {}).get('name', cc)}", evidence=f"matched \"{ch['text']}\"")
    c = G.countries.get(cc) or {}; lab = c.get("label")
    if not lab: return dict(out, reason_code="not_found", reason_unlocated=f"\"{ch['text']}\" matched {cc} but no centroid is available")
    return fill(lab[0], lab[1], cc, None, "country", method, detail, ch["conf"], c.get("name", cc), evidence=f"matched \"{ch['text']}\"" + (f"; also mentions {', '.join(ch['others'][:4])}" if ch.get("others") else ""))

# ------------------------------------------------------------------ batch pass
def sig_of(cl): return hashlib.sha1(json.dumps([VERSION, cl.get("title"), cl.get("location"), cl.get("lat"), cl.get("lon"), cl.get("n_items"), bool(cl.get("brief"))]).encode()).hexdigest()[:16]

STATUS = {"running": False, "last": None, "last_trigger": None, "next_at": None, "runs": 0}
def run(trigger="timer", nom_budget=NOM_BUDGET, max_seconds=600):
    if STATUS["running"]: return {"skipped": "already running"}
    STATUS["running"] = True; t0 = time.time(); started = iso(now()); stats = {"scanned": 0, "geocoded": 0, "located": 0}; budget = NomBudget(nom_budget); err = None
    try:
        b = bdb()
        cut = iso(now() - timedelta(days=WINDOW_DAYS))
        cls = [dict(r) for r in b.execute("SELECT cluster_id, title, category, location, lat, lon, n_items, brief, event_time, first_seen FROM clusters WHERE watchlist IN (0,1) AND (COALESCE(event_time, first_seen)>=? OR first_seen>=?)", (cut, cut))]
        with _lock:
            g = gdb(); have = {r["id"]: (r["sig"], r["reason_code"], r["version"]) for r in g.execute("SELECT id, sig, reason_code, version FROM geo")}; g.close()
        todo = [c for c in cls if c["cluster_id"] not in have or have[c["cluster_id"]][0] != sig_of(c) or have[c["cluster_id"]][1] in ("pending", "geocoder_error")]
        stats["scanned"] = len(cls)
        # new alerts first, then the backfill (newest to oldest)
        todo.sort(key=lambda c: (c["cluster_id"] in have, -(datetime.strptime(c["first_seen"], "%Y-%m-%dT%H:%M:%SZ").timestamp() if c.get("first_seen") else 0)))
        mem = {}
        if todo:
            ids = [c["cluster_id"] for c in todo]
            for k in range(0, len(ids), 500):
                q = ids[k:k + 500]
                for r in b.execute(f"SELECT cluster_id, source, title, lat, lon, location, official FROM alerts WHERE cluster_id IN ({','.join('?' * len(q))})", q):
                    mem.setdefault(r["cluster_id"], []).append(dict(r))
        b.close()
        rows = []
        for c in todo:
            if time.time() - t0 > max_seconds: break
            try: r = geocode(c, mem.get(c["cluster_id"], []), budget)
            except Exception as ex: r = {"id": c["cluster_id"], "located": 0, "reason_code": "geocoder_error", "reason_unlocated": f"Geocoder error: {str(ex)[:120]}"}
            r["sig"] = sig_of(c); r["version"] = VERSION; r["geocoded_at"] = iso(now())
            rows.append(r); stats["geocoded"] += 1; stats["located"] += 1 if r.get("located") else 0
            if len(rows) >= 100: _save(rows); rows = []
        _save(rows)
    except Exception as ex:
        err = str(ex)[:300]
    finally:
        STATUS["running"] = False; STATUS["last"] = iso(now()); STATUS["last_trigger"] = trigger; STATUS["runs"] += 1
        with _lock:
            g = gdb(); g.execute("INSERT INTO runs(started, finished, trigger, scanned, geocoded, located, nominatim_calls, error) VALUES(?,?,?,?,?,?,?,?)",
                                 (started, iso(now()), trigger, stats["scanned"], stats["geocoded"], stats["located"], budget.calls, err)); g.commit(); g.close()
    return dict(stats, nominatim_calls=budget.calls, error=err, seconds=round(time.time() - t0, 1))

COLS = ["id", "lat", "lon", "place", "country", "country_name", "admin1", "admin1_code", "city", "precision", "method", "method_detail", "confidence", "located",
        "reason_code", "reason_unlocated", "candidates", "evidence", "sig", "version", "geocoded_at"]
def _save(rows):
    if not rows: return
    with _lock:
        g = gdb()
        g.executemany(f"INSERT INTO geo({','.join(COLS)}, attempts) VALUES({','.join('?' * len(COLS))}, 1) ON CONFLICT(id) DO UPDATE SET "
                      + ",".join(f"{k}=excluded.{k}" for k in COLS[1:]) + ", attempts=attempts+1", [tuple(r.get(k) for k in COLS) for r in rows])
        g.commit(); g.close()
