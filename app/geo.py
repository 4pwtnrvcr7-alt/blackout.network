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
VERSION = 12                # bump to re-geocode everything after rule changes (9: Nov 21 2026 contextual rules, pt1682u; 10: weak-town and headline-country guards, pt1686u; 11: headline place + state, reject mayor surnames such as Depew, pt1761u; 12: corpus-common must not drop Iowa/Alaska/Kyiv, Census places/counties, Nov 23 pt1767u)
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
           "east coast", "west coast", "gulf coast", "north coast", "south coast", "middle", "upper", "lower", "interior", "highlands", "lakes", "mountain", "mountains", "river", "valley", "plains", "metro", "region", "district",
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
               "mass", "miss", "wash", "ind", "ill", "ore", "conn", "penn", "tenn", "minn", "wis", "neb", "colo", "okla", "ariz", "nev", "ala", "fla", "said", "says", "news", "live", "breaking", "update", "alert", "watch", "warning", "drone", "drones", "flood", "storm", "fire", "tornado"}
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
INSTITUTION_PLACES = {"white house", "the white house", "pentagon", "the pentagon", "kremlin", "the kremlin",
                     "downing street", "elysee", "elysée", "capitol", "capitol hill", "langley", "foggy bottom"}
FLAG_RE = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
_STRIP_NWS_OFFICE = re.compile(r"\s+by\s+NWS\s+[A-Za-z./' -]+?\s+[A-Z]{2}\b", re.I)
def strip_nws_office(text):
    """Drop the issuing office ('by NWS Seattle WA') so it is never treated as the event place."""
    return _STRIP_NWS_OFFICE.sub("", text or "").strip()
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
        # v12: lowercase words that appear often in the live alert corpus ("in alaska", "from iowa")
        # must not drop real states, countries, capitals, or special cities from the gazetteer or
        # from extract(). That is what made the Aleutian pin lose cc=US, hid "Iowa deputy…", and
        # treated "strikes on Kyiv … embassies of Austria and the Netherlands" as no location.
        self.protected = self._protected_keys()
        self.common = (set(COMMON_HARD) | self._corpus_common()) - self.protected
        self.common |= set(COMMON_HARD)  # Mobile, Nice, Reading, Bath and other COMMON_HARD names still need context
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
                if len(k) < 4 or k in GENERIC: continue
                if k in self.common and k not in self.protected: continue
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

    def _protected_keys(self):
        """Place names that a busy lowercase news corpus must never knock out of the gazetteer."""
        keys = set()
        for iso2, c in self.countries.items():
            for n in {c.get("name") or "", *c.get("ne_names", []), *COUNTRY_ALIASES.get(iso2, [])}:
                k = key_of(n)
                if k:
                    keys.add(k)
        for code, a in self.admin1.items():
            for n in {a.get("name") or "", a.get("ascii") or "", *a.get("alts", [])}:
                k = key_of(n)
                if len(k) >= 3:
                    keys.add(k)
        for c in self.cities:
            if (c[6] or 0) >= 250000 or (c[7] or "") in ("PPLC", "PPLA", "PPLA2"):
                keys.add(key_of(c[0]))
                if c[1]:
                    keys.add(key_of(c[1]))
        for k, rec in SPECIAL_CITY.items():
            if rec:
                keys.add(k)
                keys.add(key_of(rec[0]))
        # Short AP abbreviations and other COMMON_HARD words ("Mass Protests", "Nice")
        # must stay out of the gazetteer index; "Massachusetts" and "Mass." still work.
        keys -= set(COMMON_HARD)
        return keys

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

    def nearest_city_cc(self, lat, lon, cc, max_km=300):
        """Is there a town of country cc within max_km of the point? (quake feeds say '107 km E of Ollague, Chile' for a point in Bolivia)"""
        r = int(max_km // 100) + 1
        for dx in range(-r, r + 1):
            for dy in range(-r - 1, r + 2):
                for i in self.grid.get((int(lat // 1) + dx, int(lon // 1) + dy), []):
                    c = self.cities[i]
                    if c[4] == cc and hav(lat, lon, c[2], c[3]) <= max_km: return True
        return False

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
_INCIDENTAL_COUNTRY = re.compile(
    r"\b(?:embass(?:y|ies)|consulate[s]?|ambassador[s]?)\s+(?:of|to|in)\b", re.I)

def _incidental_country_mention(raw, start, end):
    """True when a country is mentioned only as an embassy, consulate, or ambassador, not as the event place."""
    window = (raw or "")[max(0, start - 48):min(len(raw or ""), end + 16)]
    return bool(_INCIDENTAL_COUNTRY.search(window))

def admin_centroid(a1=None, name=None, cc=None):
    """State/province or country label coordinates from the offline gazetteer, or None."""
    G = gaz()
    if a1 and a1 in G.admin1 and G.admin1[a1].get("label"):
        rec = G.admin1[a1]
        return {"lat": rec["label"][0], "lon": rec["label"][1], "cc": a1.split(".")[0], "a1": a1,
                "name": rec.get("name") or a1, "precision": "state"}
    if name:
        k = key_of(name)
        for kind, ref in (G.idx.get(k) or []):
            if kind == "admin1" and (not cc or ref.split(".")[0] == cc) and G.admin1.get(ref, {}).get("label"):
                rec = G.admin1[ref]
                return {"lat": rec["label"][0], "lon": rec["label"][1], "cc": ref.split(".")[0], "a1": ref,
                        "name": rec.get("name") or name, "precision": "state"}
            if kind == "country" and G.countries.get(ref, {}).get("label"):
                rec = G.countries[ref]
                return {"lat": rec["label"][0], "lon": rec["label"][1], "cc": ref, "a1": None,
                        "name": rec.get("name") or name, "precision": "country"}
    if cc and cc in G.countries and G.countries[cc].get("label"):
        rec = G.countries[cc]
        return {"lat": rec["label"][0], "lon": rec["label"][1], "cc": cc, "a1": None,
                "name": rec.get("name") or cc, "precision": "country"}
    return None

def _hyph(t, toks, i, n):
    """v11: the name is one half of a hyphenated name ("Loire-Atlantique")."""
    return (i > 0 and t[toks[i - 1][2]:toks[i][1]] == "-") or (i + n < len(toks) and t[toks[i + n - 1][2]:toks[i + n][1]] == "-")

def extract(text, ctx_cc=None, trust=False):
    """Find place mentions in free text. Returns dict with accepted matches, context countries, rejected/ambiguous info, unmatched locative spans.
    trust=True for a location field (every capitalised span there is meant to be a place)."""
    G = gaz(); raw = strip_nws_office(text or "") if not trust else (text or "")
    people = honorific_surnames(raw) if not trust else set()
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
            if n > 1 and any(nw(s) in CONNECT for s in (seg[0], seg[-1])) and not any(r[0] == "country" for r in G.idx.get(" ".join(nw(x) for x in seg), [])): continue   # but "El Salvador"
            k = " ".join(nw(s) for s in seg)
            if n > 1 and any(_sent_start(t, toks, i + j) for j in range(1, n)): continue     # "NEW: Britain ..." is not New Britain
            if k in G.idx or k in SPECIAL_CITY:
                # sentence position: first word of the text or after . ! ? : is "sentence start"
                if not (caps[i] or (i > 0 and nw(words[i - 1]) in STRONG_CUES and not trust and k not in LOCATIONAL and k not in G.common and k not in GENERIC
                                    and len(k) >= 4 and any(r[0] in ("country", "admin1") for r in G.idx.get(k, [])))): continue   # v10: no lower-case towns
                # v10: one half of a hyphenated name ("Miami-Dade") is not a place of its own
                if n == 1 and not trust and not any(r[0] in ("country", "admin1", "demonym") for r in G.idx.get(k, [])) and (
                        (i > 0 and t[toks[i - 1][2]:toks[i][1]] == "-" and caps[i - 1] and nw(words[i - 1]) not in HYPHEN_OK) or
                        (i + 1 < len(toks) and t[toks[i][2]:toks[i + 1][1]] == "-" and caps[i + 1] and nw(words[i + 1]) not in HYPHEN_OK)): continue
                # v10: "Macon County" is the county, not the city of Macon
                if not trust and i + n < len(words) and nw(words[i + n]) in ("county", "parish") and not any(r[0] in ("country", "admin1") for r in G.idx.get(k, [])): continue
                if n == 1 and k in G.common and trust and len(k) <= 3: continue
                if n == 1 and words[i].replace(".", "").isupper() and len(words[i].replace(".", "")) <= 4 and k not in CAPS_ONLY and not trust and k not in SPECIAL_CITY: continue   # acronyms (NIS, SEC, WHO)
                if n == 1 and k in CAPS_ONLY and not (words[i].replace(".", "").isupper() and not shouting): continue
                if (k in CAPS_ONLY or k.replace(" ", "") in CAPS_ONLY) and not words[i][0].isupper(): continue
                if n == 1 and k in ORG_WORDS and not trust: continue
                if n == 1 and not trust and k in people: continue   # v11: "Mayor Diezel Depew" is not Depew, NY
                hit = (i, n, k, list(G.idx.get(k, [])))
                break
        if hit: found.append(hit); i += hit[1]
        else: i += 1
    ctx = {}                                   # country -> weight of evidence (names, demonyms, flags)
    def bump(cc, w):
        if cc: ctx[cc] = ctx.get(cc, 0) + w
    for cc in flags: bump(cc, 0.5)
    if ctx_cc: bump(ctx_cc, 1)
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
        elif _AP_ADMIN.get(b.lower().rstrip(".")) and _AP_ADMIN[b.lower().rstrip(".")] in US_POSTAL:
            val = ("US", US_POSTAL[_AP_ADMIN[b.lower().rstrip(".")]]); bump("US", 1)
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
    rejected_people = []
    for (i, n, k, refs) in found:
        prev = nw(words[i - 1]) if i > 0 else ""
        cue = prev in LOC_CUES
        strong_cue = prev in STRONG_CUES
        before_cap = i > 0 and caps[i - 1] and prev not in CONNECT and not cue and not _sent_start(t, toks, i) and not (prev in ("a", "an") and _sent_start(t, toks, i - 1))   # v11: "A Krasnoyarsk apartment"
        after_cap = i + n < len(words) and caps[i + n] and nw(words[i + n]) not in CONNECT and not _sent_start(t, toks, i + n)
        person_like = (before_cap or after_cap) and not title_case and not trust
        prev2 = nw(words[i - 2]) if i > 1 else ""
        if i > 0 and not trust and caps[i - 1] and nw(words[i - 1]) not in STRONG_CUES and (
                nw(words[i - 1]) in GIVEN_NAMES or nw(words[i - 1]) in HONORIFICS or prev2 in HONORIFICS):
            rejected_people.append(" ".join(words[max(0, i - 2):i + n])); continue
        if not trust and k in people:
            rejected_people.append(words[i]); continue
        if not trust and k in INSTITUTION_PLACES:
            continue  # "White House says…" is the speaker, not White House, Morocco
        common = k in G.common and k not in getattr(G, "protected", set())
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
            elif (not trust) and _incidental_country_mention(raw, toks[i][1], toks[i + n - 1][2]):
                pass  # "embassies of Austria and the Netherlands" is not the event country
            else:
                acc.append({"level": "country", "cc": cc, "a1": None, "i": i, "k": k, "text": " ".join(words[i:i + n]), "conf": "high" if trust else "medium", "cue": strong_cue}); continue
        if a1s:
            # prefer admin1 in a context country; US states win by default only with US context or when unique
            pick = [a for a in a1s if a.split(".")[0] in ctx] or ([a for a in a1s if a.startswith("US.")] if "US" in ctx else []) or (a1s if len(a1s) == 1 and (trust or k in ADMIN_OK or (strong_cue and not common and len(k) >= 5 and nxt != "of")
                                                                                                                                       or (not common and not person_like and not org_next and not cities and len(k) >= 8 and k not in GENERIC and nxt != "of" and not trust
                                                                                                                                           and (n >= 2 or _sent_start(t, toks, i) or i == 0) and not _hyph(t, toks, i, n) and not BROAD_RE.fullmatch(" ".join(words[i:i + n])))) else [])   # v11: "Canary Islands state of emergency", "in ... Saskatchewan"
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
        if cities and n == 1 and k in GENERIC and not trust and not pair: cities = []     # v10: "Central Florida" is not Central, Louisiana
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
    if ex.get("trust"):     # a location field ending in a country ("Off East Coast of Honshu, Japan"): everything else must be in that country
        cl = [a["cc"] for a in acc if a["level"] == "country"]
        if len(set(cl)) == 1:
            acc = [a for a in acc if a["cc"] == cl[0]]
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
        if lvl == "city" and not ex.get("trust"):
            dist = []
            for x in sorted(L, key=lambda a: a["i"]):
                if not any(hav(x["city"]["lat"], x["city"]["lon"], d["city"]["lat"], d["city"]["lon"]) < 60 for d in dist): dist.append(x)
            if len(dist) >= 2:
                a1s = {x["a1"] for x in dist}
                names = ", ".join(x["text"] for x in dist[:4])
                if len(a1s) == 1 and next(iter(a1s)) in G.admin1 and G.admin1[next(iter(a1s))].get("label"):
                    return dict(a, level="state", a1=next(iter(a1s)), conf="medium", text=names, others=[]), None, None, None
                return dict(a, level="country", a1=None, conf="medium", text=names, others=[]), None, None, None
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

# ------------------------------------------------------------------ context rules (v9, Nov 21 2026, Matt pt1682u)
# Regions abroad that headlines name on their own and that are unambiguous (other foreign states/provinces need "in/near ..." or context).
ADMIN_OK = {"crimea", "donetsk", "luhansk", "kherson", "zaporizhzhia", "zaporizhia", "kharkiv", "kursk", "belgorod", "bryansk", "kashmir", "xinjiang",
            "tibet", "chechnya", "dagestan", "balochistan", "baluchistan", "khyber pakhtunkhwa", "darfur", "tigray", "amhara", "kurdistan", "sinai",
            "quebec", "ontario", "alberta", "british columbia", "queensland", "new south wales", "tasmania", "western australia", "south australia",
            "northern territory", "bavaria", "catalonia", "sicily", "sardinia", "lombardy", "andalusia", "kerala", "tamil nadu", "uttar pradesh",
            "maharashtra", "west bengal", "manipur", "assam", "sindh", "mindanao", "papua", "aceh", "okinawa", "hokkaido", "kyushu", "zhejiang",
            "guangdong", "sichuan", "yunnan", "hebei", "shandong", "jalisco", "sinaloa", "chihuahua", "guerrero", "michoacan", "tamaulipas",
            "oaxaca", "chiapas", "sonora", "borno", "zamfara", "kaduna", "kano", "kwara", "north kivu", "south kivu", "ituri", "kivu", "cabo delgado"}
ORG_WORDS = {"university", "college", "school", "hospital", "airport", "police", "union", "city", "port", "harbor", "station", "church", "temple", "mission", "embassy", "parliament", "congress", "senate", "court", "palace", "academy", "institute", "center", "centre"}
# People are not places: "Joe Wilson", "Ben Norton", "Rep. Lincoln". A capitalised given name or honorific right before a place name
# makes it a person.
GIVEN_NAMES = set("""joe john james robert michael william david richard joseph thomas charles chris christopher daniel matthew anthony mark donald steven
paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeffrey ryan jacob gary nicholas eric jonathan stephen larry justin scott brandon
benjamin ben samuel gregory alexander frank patrick raymond jack dennis jerry tyler aaron jose adam nathan henry douglas zachary peter kyle ethan walter
noah jeremy christian keith roger terry gerald harold sean austin carl arthur lawrence dylan jesse jordan bryan billy bruce gabriel logan albert willie
alan juan wayne elijah randy roy vincent ralph eugene russell bobby mason philip louis mary patricia jennifer linda elizabeth barbara susan jessica sarah
karen lisa nancy betty margaret sandra ashley kimberly emily donna michelle carol amanda dorothy melissa deborah stephanie rebecca sharon laura cynthia
kathleen amy angela shirley anna brenda pamela emma nicole helen samantha katherine christine debra rachel carolyn janet catherine maria heather diane
ruth julie olivia joyce virginia victoria kelly lauren christina joan evelyn judith megan andrea cheryl hannah jacqueline martha gloria teresa ann sara
madison frances kathryn janice jean abigail alice judy sophia grace denise amber doris marilyn danielle beverly isabella theresa diana natalie brittany
charlotte marie kayla alexis lori kamala hillary nancy marco ted rand mitch chuck kash pete tulsi marjorie lindsey elon vladimir volodymyr benjamin
emmanuel keir rishi justin narendra recep xi kim shinzo fumio jair javier claudia gustavo nicolas luiz""".split())
HONORIFICS = {"mr", "mrs", "ms", "dr", "sen", "senator", "rep", "representative", "gov", "governor", "president", "minister", "gen", "general", "judge",
              "justice", "secretary", "mayor", "sir", "lord", "lady", "prince", "princess", "king", "queen", "pope", "rev", "father", "officer", "sheriff",
              "commissioner", "chairman", "speaker", "professor", "prof", "coach", "captain", "capt", "sgt", "lt", "col", "councilman", "councilwoman", "councillor"}

# "Mayor Diezel Depew" / "Gov. Katie Hobbs": the last name is a person, not a town (Depew, NY).
_HONOR_RE = re.compile(
    r"\b(?:Mayor|Governor|Gov\.|Senator|Sen\.|Representative|Rep\.|President|Minister|Judge|"
    r"Dr\.|Mr\.|Mrs\.|Ms\.|Gen\.|General|Col\.|Capt\.|Commissioner|Chairman|Chairwoman|"
    r"Sheriff|Secretary|Councilman|Councilwoman|Councillor)\s+"
    r"([A-Z][a-zA-Z.'\-]+)(?:\s+([A-Z][a-zA-Z.'\-]+))?"
)
def honorific_surnames(text):
    """Normalized last (and first) names introduced by a title in the text."""
    out = set()
    for m in _HONOR_RE.finditer(text or ""):
        for g in m.groups():
            if g:
                k = key_of(g)
                if k and k not in GENERIC:
                    out.add(k)
    return out

# Where a source is published is a prior, not proof: it only breaks ties between same-named places and limits online lookups.
SOURCE_CC = [
    (r"\.com\.au\b|\.net\.au\b|\.gov\.au\b|\.org\.au\b|\babc\.net\.au|\bSMH\b|\bThe Age\b|The Australian\b|news\.com\.au|9news|7news|Sky News Australia|\bSBS\b|Guardian Australia|Geoscience Australia|\bBoM\b|Bureau of Meteorology|Brisbane Times|WAtoday|Perth Now|PerthNow|Courier[- ]Mail|Herald Sun|Daily Telegraph \(AU\)|\bABC \(AU\)|#auspol", "AU"),
    (r"\.co\.nz\b|\.govt\.nz\b|\.org\.nz\b|\bGeoNet\b|\bRNZ\b|NZ Herald|nzherald|Stuff\.co|1News|Newshub|#eqnz|nzquake|MetService", "NZ"),
    (r"\.co\.uk\b|\.gov\.uk\b|\.org\.uk\b|\bBBC\b|Met Office|Sky News(?! Australia)|\bITV\b|Evening Standard|Manchester Evening|Liverpool Echo|Wales Online|The Scotsman|Daily Record|Belfast Telegraph", "GB"),
    (r"\.ca/|\.ca\b|\bCBC\b|\bCTV\b|Global News|Toronto Star|Globe and Mail|National Post|Environment Canada|EarthquakesCanada|Earthquakes Canada", "CA"),
    (r"\.ie\b|\bRT[EÉ]\b|Irish Times|Irish Independent|TheJournal\.ie|Met [EÉ]ireann", "IE"),
    (r"\.co\.za\b|News24|\bSABC\b|Daily Maverick|IOL\b", "ZA"),
    (r"\.co\.in\b|\.gov\.in\b|Times of India|Hindustan Times|NDTV|The Hindu\b|Indian Express|\bANI\b|\bPTI\b|\bIMD\b", "IN"),
    (r"\.com\.ng\b|\.ng\b|Punch Newspapers|Vanguard News|Premium Times|Channels TV|\bTheCable\b|Daily Trust|Sahara Reporters", "NG"),
    (r"\.ph\b|Inquirer\.net|Rappler|GMA News|ABS-CBN|PHIVOLCS|PAGASA", "PH"),
    (r"\bJMA\b|NHK|Japan Times|Kyodo|Mainichi|Asahi|緊急地震速報", "JP"),
    (r"\bBMKG\b|\.co\.id\b|\.go\.id\b|Jakarta Post|Antara|Tempo\.co", "ID"),
    (r"\bINGV\b|\.it/|ANSA", "IT"),
    (r"\bAFAD\b|\bKandilli\b|Daily Sabah|Hurriyet|\.com\.tr\b", "TR"),
    (r"Times of Israel|Haaretz|Jerusalem Post|\bYnet\b|i24NEWS|\.co\.il\b", "IL"),
    (r"Kyiv Independent|Ukrainska Pravda|Ukrinform|\.ua\b", "UA"),
    (r"\bNWS\b|api\.weather\.gov|National Weather Service|\bUSGS\b|\.gov/|\bFEMA\b|\bCDC\b|\bNOAA\b", "US"),
    (r"Google News: (?!WION\b)[KW][A-Z]{2,3}(?:-TV)?\b(?![a-z])|@(?!wion|kyiv)[kw][a-z]{2,3}\d{0,2}(?:tv|news)?\.bsky\.social|@\d{3,4}[kw][a-z]{2,3}\.bsky", "US"),   # v10: US local TV/radio call letters (KETV, WGME, @wmur9)
]
SOURCE_CC_RE = [(re.compile(rx), cc) for rx, cc in SOURCE_CC]
def source_cc(members=(), extra=""):
    """Most common publishing country of a story's sources (None when unknown or split)."""
    votes = {}
    for m in list(members) + ([{"source": extra}] if extra else []):
        s = " ".join(str(m.get(k) or "") for k in ("source", "source_url", "url"))
        for rx, cc in SOURCE_CC_RE:
            if rx.search(s): votes[cc] = votes.get(cc, 0) + 1; break
    if not votes: return None
    best = sorted(votes.items(), key=lambda kv: -kv[1])
    return best[0][0] if len(best) == 1 or best[0][1] > best[1][1] else None

# ------------------------------------------------------------------ NWS / CAP zone lists (offline NWS zone, county and marine tables)
FE_NAMES = {"n": "North", "s": "South", "e": "East", "w": "West", "c": "Central", "nc": "North Central", "sc": "South Central", "ec": "East Central",
            "wc": "West Central", "ne": "Northeast", "nw": "Northwest", "se": "Southeast", "sw": "Southwest", "pa": "Panhandle", "pd": "Panhandle",
            "bb": "Big Bend", "mi": "Middle", "ee": "Eastern", "er": "East", "su": "Upper", "uc": "Upper", "cc": "Central"}
NWS_URL = "https://raw.githubusercontent.com/4pwtnrvcr7-alt/blackout.network/main/app/heatmap_data/nws_zones.json"
_NWS_TRY = [0.0]
def _nws_load():
    """The NWS zone table ships in heatmap_data/. A Mac install that only copied geo.py fetches the same public file once and keeps it."""
    for p in (os.path.join(DATA, "nws_zones.json"), os.path.join(BASE, "nws_zones.json")):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    if time.time() - _NWS_TRY[0] < 3600: return None
    _NWS_TRY[0] = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(NWS_URL, headers={"User-Agent": UA}), timeout=30) as r: raw = r.read()
        d = json.loads(raw.decode())
        if not d.get("zones"): return None
        for p in (os.path.join(DATA, "nws_zones.json"), os.path.join(BASE, "nws_zones.json")):
            try:
                with open(p + ".tmp", "wb") as f: f.write(raw)
                os.replace(p + ".tmp", p); break
            except Exception: continue
        return d
    except Exception:
        return None

_NWS = {}
def nws_data():
    if not _NWS:
        d = _nws_load()
        if not d: return {}
        off = {}
        for cwa, nm in d["offices"].items():
            k = key_of(nm.replace(",", " ")); off[k] = cwa
            off[key_of(nm.split(",")[0])] = off.get(key_of(nm.split(",")[0]), cwa)
        byname, bycode = {}, {}
        for cwa, L in d["zones"].items():
            for name, st, lat, lon, code, fe in L:
                z = {"name": name, "st": st, "lat": lat, "lon": lon, "code": code, "fe": fe, "cwa": cwa}
                byname.setdefault((cwa, key_of(name)), []).append(z)
                byname.setdefault(("*", key_of(name)), []).append(z)
                if code.startswith("Z"): bycode[f"{st}Z{code[-3:]}"] = z
                elif code.startswith("C"): bycode.setdefault(f"{st}C{code[-3:]}", z)
                else: bycode[code[1:]] = z
        _NWS.update(off=off, byname=byname, bycode=bycode)
    return _NWS

NWS_OFFICE_RE = re.compile(r"\bNWS ([A-Z][A-Za-z.'/ -]+?),? ([A-Z]{2})\b")
UGC_RE = re.compile(r"\b([A-Z]{2})([CZ])(\d{3})\b")
_ZPRE = re.compile(r"^(Coastal|Inland|Mainland|Northern|Southern|Eastern|Western|Central|North|South|East|West|Northwest|Northeast|Southwest|Southeast|Upper|Lower|Interior|Greater)\s+", re.I)
def nws_resolve(title, loc):
    """NWS / CAP alerts: the issuing office + the zone or county list (or UGC codes) -> the real counties and their state.
    Returns dict(lat, lon, states, n, matched, total, fe, office, spread_km, zones) or None."""
    N = nws_data(); gaz()
    if not N.get("byname"): return None
    m = NWS_OFFICE_RE.search(title or "")
    cwa = None
    if m:
        cwa = N["off"].get(key_of(f"{m.group(1)} {m.group(2)}")) or N["off"].get(key_of(m.group(1)))
    pts, seen = [], set()
    for st, kind, num in UGC_RE.findall(f"{title or ''} {loc or ''}"):
        z = N["bycode"].get(f"{st}{kind}{num}")
        if z and z["code"] not in seen: seen.add(z["code"]); pts.append(z)
    parts = [x.strip() for x in re.split(r";", loc or "") if x.strip()]
    if not pts and not m: return None
    off_st = m.group(2) if m else None
    total = 0
    for part in parts:
        pm = re.match(r"^(.*?),\s*([A-Z]{2})$", part)
        name, st = (pm.group(1), pm.group(2)) if pm else (part, None)
        name = re.sub(r"\s+(County|Parish|Borough|Census Area|Municipality)$", "", name.strip())
        if len(key_of(name)) < 3: continue          # a list cut off mid-word ("Inland ")
        total += 1
        cands = []
        for scope in ([cwa] if cwa else []) + ["*"]:
            cands = N["byname"].get((scope, key_of(name))) or []
            if st: cands = [z for z in cands if z["st"] == st] or ([] if scope == "*" else cands)
            if scope == "*" and not st and off_st: cands = [z for z in cands if z["st"] == off_st or z["cwa"] == cwa]
            if cands: break
        if not cands and part is parts[-1] and cwa and len(key_of(name)) >= 6:   # the stored list was cut off mid-name ("Coastal Indian Riv")
            pre = [z for (sc, kk), L in N["byname"].items() if sc == cwa and kk.startswith(key_of(name)) for z in L]
            if len({z["code"] for z in pre}) == 1: cands = pre
        if not cands:
            nm2 = _ZPRE.sub("", name)
            if nm2 != name:
                cands = [z for z in (N["byname"].get((cwa or "*", key_of(nm2))) or []) if not st or z["st"] == st]
        if not cands: continue
        # one row per real place: prefer the forecast zone over the county row with the same name, and the issuing office's state
        cands.sort(key=lambda z: (z["code"][0] != "Z", z["st"] != (st or off_st)))
        z = cands[0]
        if z["code"] not in seen: seen.add(z["code"]); pts.append(z)
    if not pts: return None
    lat = sum(z["lat"] for z in pts) / len(pts); lon = sum(z["lon"] for z in pts) / len(pts)
    spread = max(hav(lat, lon, z["lat"], z["lon"]) for z in pts)
    states = [s for s in dict.fromkeys(z["st"] for z in pts) if s in US_POSTAL]
    if not states and off_st in US_POSTAL: states = [off_st]
    fe = {}
    for z in pts:
        if z["fe"]: fe[z["fe"]] = fe.get(z["fe"], 0) + 1
    return {"lat": lat, "lon": lon, "states": states, "n": len(pts), "matched": len(pts), "total": max(total, len(pts)), "fe": fe,
            "office": (f"{m.group(1)} {m.group(2)}" if m else None), "spread_km": round(spread), "zones": [z["name"] for z in pts], "marine": all(z["code"].startswith("M") for z in pts)}

def nws_area_label(res, state_name=None):
    """'Central and East Central Florida' style label from the NWS forecast-area codes of the matched zones."""
    if not res: return ""
    stn = state_name or ""
    fe = [FE_NAMES.get(k) for k, _ in sorted(res["fe"].items(), key=lambda kv: -kv[1]) if FE_NAMES.get(k)]
    fe = list(dict.fromkeys(fe))[:2]
    if res.get("marine"): return f"coastal waters off {stn}".strip()
    return (" and ".join(fe) + " " + stn).strip() if fe and stn else stn

def _named_countries(text):
    """Countries the text names outright (a country, or a state/province that belongs to exactly one country). Lower-case words never count."""
    if not text: return set()
    try: ex = extract(text)
    except Exception: return set()
    return {a["cc"] for a in ex["acc"] if a["level"] in ("country", "state") and a["cc"]}

def brief_where(brief):
    """The scanner's own summary of the story: its WHERE line first, then the first part of WHAT."""
    b = brief or ""
    if not b.strip(): return ""
    out = []
    for k in ("WHERE", "WHAT"):
        m = re.search(k + r":\s*(.+?)(?=\s+(?:WHAT|WHERE|WHEN|CONFIDENCE|VERIFY):|$)", b, re.S)
        if m: out.append(m.group(1).strip()[:300])
    return ". ".join(out) if out else b.strip()[:300]

def agree(ch, ex, prior, named):
    """Country agreement: a place in a country the story never names (and its sources are not from) is only an approximate spot."""
    if not ch or ch["level"] == "country": return ch
    if ch.get("conf") == "high": return ch
    others = named - {ch["cc"]}
    big = ch["level"] == "city" and ((ch.get("city") or {}).get("pop", 0) >= 200000 or ch.get("k") in SPECIAL_CITY)
    if big or ch.get("cue"): return ch
    if named and ch["cc"] not in named and others:
        return dict(ch, conf="low", why=f"names {', '.join(sorted(others))}, not {ch['cc']}")
    if prior and ch["level"] == "city" and ch["cc"] != prior and ch["cc"] not in named:
        return dict(ch, conf="low", why=f"sources are from {prior}")
    return ch

HYPHEN_OK = {"based", "born", "area", "bound", "led", "backed", "made", "style", "era", "ex", "pro", "anti", "post", "pre", "region", "wide"}

def _better_than_weak(ch, ex, prior, named):
    """v10 (Matt pt1686u, "never again"): a low-confidence town ("Abu" for "Abu Sharkh roundabout, Gaza Strip", "Grey Eagle" -> Eagle, Idaho,
    "Town of Lyons" -> Lyon, France) is not used when the story names another country or its sources are from another country, . Returns a reduced ex, else None."""
    if not ch or ch.get("level") != "city" or ch.get("conf") != "low": return None
    acc = ex["acc"]; G = gaz()
    neigh = set((G.countries.get(ch["cc"]) or {}).get("neighbours") or [])
    weak_word = ch.get("k") in G.common or ch.get("k") in GIVEN_NAMES
    c = ch.get("city") or {}
    small = c.get("pop", 0) < 200000
    alt = key_of(c.get("name") or "") != ch.get("k")          # matched through an alternate spelling ("Lyons" for Lyon)
    if (named and ch["cc"] not in named and not (named & neigh) and small) or \
            (prior and ch["cc"] != prior and ch["cc"] not in named and prior not in neigh and (small or alt) and not (prior == "US" and ch["cc"] in ("PR", "GU", "VI", "AS", "MP", "UM"))) or (not named and not prior and weak_word):
        rest = [a for a in acc if not (a["level"] == "city" and a["k"] == ch.get("k") and a["cc"] == ch["cc"])]
        spans = list(ex.get("spans") or [])
        if prior and ch.get("cue") is not None and ch.get("text") and ch["text"] not in spans and (ch.get("cue") or len(ch["text"]) >= 4):
            spans = [ch["text"]] + spans      # ask the online geocoder inside the sources' country instead ("Palo" -> Palo, Iowa)
        return dict(ex, acc=rest, spans=spans[:2])
    return None

COUNTY_RE = re.compile(r"\b((?:St\.? |Saint |De |La |Le |Prince )?[A-Z][a-z]+(?:[ -][A-Z][a-z]+){0,2}) (County|Parish)\b")
POSTAL_RE = re.compile(r"(?:,\s*|\b)(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b")
def county_place(text, prior=None):
    """'Bernalillo County', 'Baltimore County ... Dundalk' -> the US county (NWS county table), only when the county name is unique
    or the text names its state."""
    if prior and prior != "US": return None
    N = nws_data(); G = gaz()
    if not N.get("byname"): return None
    for m in COUNTY_RE.finditer(text or ""):
        nm = re.sub(r"^Saint ", "St ", m.group(1))
        rows = {z["code"]: z for z in (N["byname"].get(("*", key_of(nm))) or []) if z["code"].startswith("C")}
        if not rows: continue
        L = list(rows.values())
        if len({z["st"] for z in L}) > 1:
            sts = {a["a1"].split(".")[1] for a in extract(text)["acc"] if a["level"] == "state" and (a.get("a1") or "").startswith("US.")}
            sts |= {x for x in POSTAL_RE.findall(text[m.end():m.end() + 40]) if x in US_POSTAL}
            L = [z for z in L if z["st"] in sts]
        if len(L) == 1:
            z = L[0]
            return {"lat": z["lat"], "lon": z["lon"], "st": z["st"], "name": f"{z['name']} County", "text": m.group(0)}
    return None

def us_county_any(text):
    """'Santa Cruz County' when that county name exists in the NWS county table (any state), else None."""
    N = nws_data()
    if not N.get("byname"): return None
    for m in COUNTY_RE.finditer(text or ""):
        nm = re.sub(r"^Saint ", "St ", m.group(1))
        if any(z["code"].startswith("C") for z in (N["byname"].get(("*", key_of(nm))) or [])): return m.group(0)
    return None

def nws_counties(res):
    """Distinct counties behind a zone list ('Inland Volusia' + 'Coastal Volusia' = Volusia)."""
    out = []
    for z in (res or {}).get("zones") or []:
        c = _ZPRE.sub("", z)
        c = re.sub(r"\s+(County|Parish|Barrier Islands|Plains|Mountains|Mtns|Coast|Valley|Lowlands|Highlands|Foothills|Beaches)$", "", c)
        c = _ZPRE.sub("", c)
        if c and c not in out: out.append(c)
    return out

_MON = {m: m[:3] for m in ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")}
def _nws_time(s):
    m = re.match(r"(\w+) (\d+) at (\d+):(\d+)\s*([AP]M) ?([A-Z]{3,4})?", s or "")
    if not m: return (s or "").strip()
    mo, d, h, mi, ap, tz = m.groups()
    return f"{_MON.get(mo, mo)} {d} at {int(h)}{'' if mi == '00' else ':' + mi} {ap}" + (f" {tz}" if tz else "")

def nws_sentence(title, loc):
    """'Flood Watch for 9 East Central Florida counties from NWS Melbourne, through Nov 20 at 7 PM EST.' (None when not an NWS alert)."""
    m = re.match(r"^(.+?) issued (.+?)(?: until (.+?))? by NWS (.+?),? ([A-Z]{2})$", (title or "").strip())
    if not m: return None
    ev, _iss, until, office, st = m.groups()
    res = nws_resolve(title, loc)
    G = gaz()
    stn = G.admin1.get(US_POSTAL.get((res or {}).get("states", [st])[0] if res and res.get("states") else st, ""), {}).get("name") or st
    if res and res["states"] and len(res["states"]) > 1:
        stn = " and ".join(G.admin1[US_POSTAL[x]]["name"] for x in res["states"][:2] if x in US_POSTAL)
    where = ""
    if res:
        lab = nws_area_label(res, stn)
        if res.get("marine"): where = f"the {lab}" if lab else f"coastal waters off {stn}"
        else:
            cs = nws_counties(res)
            where = (f"{cs[0]} County, {stn}" if len(cs) == 1 else
                     (", ".join(cs[:-1]) + " and " + cs[-1] + f" counties in {lab or stn}") if len(cs) <= 3 else f"{len(cs)} {lab or stn} counties")
    else: where = stn
    return f"{ev} for {where} from NWS {office}" + (f", through {_nws_time(until)}" if until else "") + "."

def place_label(title, loc, max_len=90):
    """A readable place for story pages: never a raw NWS zone dump ('Inland Volusia; Orange; ...')."""
    loc = (loc or "").strip()
    if not loc: return ""
    # v10 (pt1686u): the headline names one country and the location field another (a merged GDACS cluster: "Forest fire in Australia",
    # location "Brazil") -> the headline's country
    if ";" not in loc and "," not in loc:
        try:
            tn = {a["cc"] for a in extract(title)["acc"] if a["level"] == "country" and a.get("cue")}     # "... in Australia"
            ln = _named_countries(loc)
            if len(tn) == 1 and ln and not (tn & ln):
                G = gaz(); tc = next(iter(tn))
                if not (set((G.countries.get(tc) or {}).get("neighbours") or []) & ln): return G.countries.get(tc, {}).get("name") or loc
        except Exception: pass
    if ";" not in loc and len(loc) <= max_len: return loc
    res = nws_resolve(title, loc)
    if res and res["states"]:
        G = gaz(); stn = " and ".join(G.admin1[US_POSTAL[x]]["name"] for x in res["states"][:2] if x in US_POSTAL)
        if res.get("marine"): return f"coastal waters off {stn}"
        cs = nws_counties(res); lab = nws_area_label(res, stn)
        return f"{cs[0]} County, {stn}" if len(cs) == 1 else f"{len(cs)} counties in {lab or stn}"
    parts = [p.strip() for p in loc.split(";") if len(p.strip()) > 2]
    if len(parts) > 2: return f"{parts[0]}, {parts[1]} and {len(parts) - 2} other areas"
    return " and ".join(parts)[:max_len]

def story_place(title, loc):
    """(cc, admin1) the story is about, or (None, None): NWS zones, then the location field, then the headline."""
    G = gaz()
    res = nws_resolve(title, loc)
    if res and res["states"]: return "US", (US_POSTAL.get(res["states"][0]) if len(res["states"]) == 1 else None)
    for tx, tr in ((loc, True), (title, False)):
        if not tx or BROAD_RE.fullmatch(fold(tx).strip()): continue
        try: ch, *_ = choose(extract(tx, trust=tr))
        except Exception: ch = None
        if ch: return ch["cc"], ch.get("a1")
    return None, None

def photo_place(name):
    """(cc, admin1) of a file photo's subject when it is a place, else (None, None) (topics such as 'martial law')."""
    G = gaz(); k = key_of(name or "")
    if not k: return None, None
    refs = G.idx.get(k) or []
    for r in refs:
        if r[0] == "country": return r[1], None
    a1 = [r[1] for r in refs if r[0] == "admin1"]
    cities = sorted((G.city(r[1]) for r in refs if r[0] == "city"), key=lambda c: -c["pop"])
    if cities and (not a1 or cities[0]["pop"] >= 100000): return cities[0]["cc"], cities[0]["a1"]
    if len(a1) == 1: return a1[0].split(".")[0], a1[0]
    try: ch, *_ = choose(extract(name, trust=True))
    except Exception: ch = None
    return (ch["cc"], ch.get("a1")) if ch else (None, None)

def story_ccs(title, loc):
    """Every country the headline or location names, including through demonyms and flags ('Palestinian' -> PS)."""
    out = set()
    for tx, tr in ((loc, True), (title, False)):
        if not tx: continue
        try: ex = extract(tx, trust=tr)
        except Exception: continue
        out |= {a["cc"] for a in ex["acc"] if a.get("cc")} | set(ex["flags"])
        for (d) in ex["demonyms"]:
            cc = DEMONYMS.get(nw(d)) or DEMONYMS.get(d.lower())
            if cc: out.add(cc)
    return out

def photo_matches(name, title, loc):
    """A file photo of a place may lead a story only when it is the story's own country (and, inside one country, the same state)."""
    pc, pa = photo_place(name)
    if not pc: return True             # not a place (a topic photo): no location claim
    sc, sa = story_place(title, loc)
    if not sc:     # no single place: a country-level photo of a country the story names is fine (a Palestine photo for "Palestinian ...")
        return pa is None and pc in story_ccs(title, loc)
    if pc != sc: return False
    if pa and sa and pa != sa: return False
    if pc == "US" and pa and not sa: return False
    return True

def supplemental_texts(cl, members=()):
    """Factual prose only. Do not geocode advice, source URLs, analysis or HQ guesses."""
    out = []
    for key in ("writeup", "summary", "body"):
        tx = cl.get(key)
        if isinstance(tx, str) and tx.strip(): out.append(tx.strip()[:6000])
    for m in members:
        for key in ("summary", "body"):
            tx = m.get(key)
            if isinstance(tx, str) and tx.strip(): out.append(tx.strip()[:6000])
    return out

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
        nc = G.nearest_city(lat, lon)
        named = _named_countries(loc) or _named_countries(title)
        if not cc:              # coast or offshore (the simplified borders miss it): the country named in the place text, else the nearest town's
            if len(named) == 1: cc = next(iter(named))
            else:
                far = nc or G.nearest_city(lat, lon, 250)
                if far: cc = far["cc"]
        conf, extra = "high", ""
        tnamed = _named_countries(title)
        if cc and named and cc not in named and not (cc == "US" and named & {"PR", "GU", "VI", "AS", "MP"}) and not any(G.nearest_city_cc(lat, lon, x, 300) for x in named):
            # the coordinates and the story disagree about the country (e.g. a merged GDACS fire: "in Australia" at a point in Brazil)
            conf, extra = "low", f"; text names {', '.join(sorted(named))} but the coordinates are in {cc}"
        # v10 (pt1686u): the headline names one country and the coordinates are far outside it -> the headline wins (country-level pin there)
        if cc and len(tnamed) == 1 and cc not in tnamed and not (cc == "US" and tnamed & {"PR", "GU", "VI", "AS", "MP"}):
            tc = next(iter(tnamed)); lab = (G.countries.get(tc) or {}).get("label")
            if lab and not G.nearest_city_cc(lat, lon, tc, 300):
                return fill(lab[0], lab[1], tc, None, "country", "gazetteer", f"title names {tc}; {det} coordinates ({lat:.2f}, {lon:.2f}) are in {cc}", "medium",
                            G.countries[tc].get("name", tc), evidence=f"headline country {tc} overrides source coordinates in {cc}")
            if lab: cc, a1, conf = tc, None, "high"      # next to the border (MeteoAlarm "Israel: ..." at a West Bank point): the named country
        place = loc if loc and not loc.startswith("Global") else (title[:120])
        return fill(lat, lon, cc, a1, "point", "source_coords", det, conf, place, city=nc["name"] if nc else None, evidence=f"{det} lat/lon {lat:.3f}, {lon:.3f}{extra}")
    # brief "WHERE: ... (approx. lat, lon)" written by the scanner from source data
    m = re.search(r"WHERE: (.+?) \(approx\. (-?\d+\.\d+), (-?\d+\.\d+)\)", cl.get("brief") or "")
    if m:
        la, lo = float(m.group(2)), float(m.group(3))
        nc = G.nearest_city(la, lo)
        pc, _pa = G.pip(la, lo)
        return fill(la, lo, pc or (nc or {}).get("cc"), None, "point", "source_coords", "scanner brief (source coordinates)", "high", m.group(1), city=nc["name"] if nc else None, evidence=m.group(0)[:200])
    # 2a) the alert's existing location field
    for loc in locs:
        if loc.startswith("Global"):
            out.update(reason_code="global", reason_unlocated=f"Source marks the location as \"{loc}\", not a place on the map"); return out
    nres = nws_resolve(title, locs[0] if locs else "")
    if nres and nres["states"]:
        sts = nres["states"]; a1 = US_POSTAL[sts[0]] if len(sts) == 1 else None
        stn = " and ".join(G.admin1[US_POSTAL[x]]["name"] for x in sts[:2] if x in US_POSTAL)
        prec = "county" if nres["spread_km"] <= 150 else "state"
        lab = nws_area_label(nres, stn)
        place = place_label(title, locs[0] if locs else "") or f"{nres['n']} NWS zones in {lab or stn}"
        return fill(nres["lat"], nres["lon"], "US", a1, prec, "location_field",
                    f"NWS zone list (offline NWS zone tables): {nres['matched']} of {nres['total']} zones" + (f", NWS {nres['office']}" if nres["office"] else ""),
                    "high" if nres["matched"] >= max(1, nres["total"] // 2) else "medium", place,
                    evidence="zones: " + "; ".join(nres["zones"][:8]) + (f" (+{nres['n'] - 8})" if nres["n"] > 8 else ""))
    locs = [l for l in locs if not BROAD_RE.fullmatch(fold(l).strip())]
    # v11 (pt1761u): the headline's city, disambiguated by a state or county the story names, beats a
    # location field that picked up a person's surname (Depew, NY for Edgewater, Florida).
    early_texts = [title] + [m["title"] for m in sorted(members, key=lambda m: -(m.get("official") or 0)) if m.get("title") and m["title"] != title][:5]
    for tx in supplemental_texts(cl, members):
        if tx and tx not in early_texts: early_texts.append(tx)
    if cl.get("brief") and cl.get("brief") not in early_texts: early_texts.append(cl.get("brief"))
    early_prior = source_cc(members, cl.get("source_hint") or "")
    hit = resolve_headline_city(title, early_texts + locs, early_prior)
    if hit:
        a1 = hit["a1"] if hit.get("a1") in G.admin1 else None
        stn = (G.admin1.get(a1) or {}).get("name", "")
        cn = (G.countries.get(hit["cc"]) or {}).get("name", hit["cc"])
        place = ", ".join(p for p in (hit["name"], stn, cn) if p)
        return fill(hit["lat"], hit["lon"], hit["cc"], a1, "city", "gazetteer",
                    "headline place + state or county", "high" if a1 else "medium", place, city=hit["name"],
                    evidence=f"headline place \"{hit['name']}\"" + (f" in {stn}" if stn else ""))
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
        if ch:
            a1 = ((ch.get("city") or {}).get("a1") if ch.get("level") == "city" else ch.get("a1"))
            pl = ((ch.get("city") or {}).get("name") if ch.get("level") == "city" else None) or ch.get("text") or loc
            if place_contradicts_headline(title, pl, ch.get("level"), a1, early_texts + locs):
                ch = None
            else:
                return place_from(ch, out, fill, "location_field", f"location field \"{loc[:80]}\"", loc)
        subj = headline_subject(title)
        if subj and key_of(subj) != key_of((loc or "").split(",")[0]):
            continue     # do not Nominatim a location field that is a different city than the headline
        st, res = nominatim(loc[:120], None, budget)
        if st == "skipped": return dict(out, reason_code="pending", reason_unlocated=f"Location field \"{loc[:60]}\" queued for the online geocoder")
        r = nom_pick(res, None, 0.3)
        if r:
            g = nom_to_geo(r)
            return fill(g["lat"], g["lon"], g["cc"], g["a1"], g["prec"], "nominatim", f"location field → Nominatim \"{loc[:60]}\"", "medium", g["place"], city=g["city"], evidence=loc)
    # 2b) place names in the title (then the other source titles in the story)
    texts = [title] + [m["title"] for m in sorted(members, key=lambda m: -(m.get("official") or 0)) if m.get("title") and m["title"] != title][:5]
    bw = brief_where(cl.get("brief"))
    # v11: published write-ups and source summaries are evidence, not just titles.
    # Keep these separate: concatenating unrelated paragraphs can make equal-country
    # conflicts and the source's home country must never move a venue overseas.
    for tx in supplemental_texts(cl, members):
        if tx and tx not in texts: texts.append(tx)
    if bw and bw not in texts: texts.append(bw)
    prior = source_cc(members, cl.get("source_hint") or "")
    allnamed = set()
    for tx in texts: allnamed |= _named_countries(tx)
    first_fail = None; spans_all = []; quals = []; demonyms = set(); flags = set(); rejected = []
    tnamed0 = {c for c in _named_countries(title) if c}
    for n, tx in enumerate(texts):
        cp = county_place(tx, prior)
        if cp and not (allnamed - {"US"}):
            a1 = US_POSTAL.get(cp["st"])
            return fill(cp["lat"], cp["lon"], "US", a1, "county", "gazetteer", ("title" if n == 0 else "the story's text") + " (US county, NWS county table)", "high",
                        f"{cp['name']}, {G.admin1.get(a1, {}).get('name', cp['st'])}", evidence=f"matched \"{cp['text']}\"")
        ex = extract(tx, ctx_cc=prior)
        if bw and tx == bw and n > 0: ex = dict(ex, acc=[a for a in ex["acc"] if a["level"] != "city" or a.get("cue")])
        ch, rc, rt, cands = choose(ex)
        for _try in range(4):
            if not ch: break
            ch = agree(ch, ex, prior, allnamed)
            alt = _better_than_weak(ch, ex, prior, allnamed)
            if alt is None: break
            ex = alt; ch, rc, rt, cands = choose(ex)
        if ch and n > 0 and tnamed0 and ch["cc"] not in tnamed0:
            ch = None     # v10: the headline names its countries; a later text may not move the story to a country the headline never names
        if ch and ch.get("level") == "city":
            same = {x for x in named_admin1_codes(texts + locs) if x.split(".")[0] == ch["cc"]}
            a1 = (ch.get("city") or {}).get("a1")
            if same and a1 not in same: ch = None
            pl = (ch.get("city") or {}).get("name") if ch else None
            if ch and place_contradicts_headline(title, pl, "city", a1, texts + locs): ch = None
        if ch:
            if ch: return place_from(ch, out, fill, "gazetteer", ("title" if n == 0 else "the story's summary" if bw and tx == bw else "another source's title in this story")
                                     + (f" (source country prior {prior})" if prior else ""), tx)
        if rc and not first_fail: first_fail = (rc, rt, cands)
        rejected += ex["rejected"]; spans_all += [(s, ex["ctx"]) for s in ex["spans"]]; quals += ex["qual"]; demonyms |= set(ex["demonyms"]); flags |= set(ex["flags"])
    if not first_fail and not quals and not (allnamed - {"US"}) and prior in (None, "US"):
        cty = next((us_county_any(tx) for tx in texts if us_county_any(tx)), None)
        lab = G.countries.get("US", {}).get("label")
        if cty and lab:   # v10: "Santa Cruz County", "El Paso County": a US county name found in several states -> the US, approximate
            return fill(lab[0], lab[1], "US", None, "country", "gazetteer", f"US county name in several states ({cty})", "medium", f"{cty}, United States",
                        evidence=f"matched \"{cty}\" (NWS county table, more than one state)")
    # v12: a clearly named state or country in the title must never show as no location
    # (Matt Nov 20). "Explosion in Ward, Ala." pins Alabama when Ward is not in the AL gazetteer;
    # "Iowa deputy…" pins Iowa. Only when nothing finer was resolved.
    named_a1 = named_admin1_codes([title] + texts[:1] + locs)
    if len(named_a1) == 1:
        rec = admin_centroid(a1=next(iter(named_a1)))
        if rec:
            cn = (G.countries.get(rec["cc"]) or {}).get("name", rec["cc"])
            return fill(rec["lat"], rec["lon"], rec["cc"], rec["a1"], "state", "gazetteer",
                        "headline names this state", "high", f"{rec['name']}, {cn}",
                        evidence="named admin1 " + rec["a1"])
    tnamed = {c for c in _named_countries(title) if c}
    if len(tnamed) == 1 and not first_fail:
        rec = admin_centroid(cc=next(iter(tnamed)))
        if rec:
            return fill(rec["lat"], rec["lon"], rec["cc"], None, "country", "gazetteer",
                        "headline names this country", "medium", rec["name"],
                        evidence="named country " + rec["cc"])
    if first_fail and not quals:
        # Same rule: a named state still wins over an equal-weight country conflict.
        if len(named_a1) == 1:
            rec = admin_centroid(a1=next(iter(named_a1)))
            if rec:
                cn = (G.countries.get(rec["cc"]) or {}).get("name", rec["cc"])
                return fill(rec["lat"], rec["lon"], rec["cc"], rec["a1"], "state", "gazetteer",
                            "headline names this state", "high", f"{rec['name']}, {cn}",
                            evidence="named admin1 " + rec["a1"])
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
        cc = max(ctx, key=ctx.get) if ctx else prior
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

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u201c\"])")
def lead_sentences(text, n=3):
    """The first sentences of a write-up, one per item: the lede says where the event or remarks happened."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t: return []
    t = re.sub(r"\b(Nov|Dec|Jan|Feb|Mar|Apr|Aug|Sept?|Oct|Gov|Sen|Rep|Gen|Lt|Col|St|Mt|Dr|Mr|Mrs|Ms|U\.S|U\.K|No)\.\s", lambda m: m.group(1) + "\u2024 ", t)
    return [x.replace("\u2024", ".").strip() for x in _SENT.split(t) if x.strip()][:n]

def locate_texts(cl, texts, members=(), method="writeup", what="the story's write-up", span_texts=(), cue_only=False, refine=False):
    """v11 (Matt pt1718u): offline only, no Nominatim, no database. Places a story from prose the scanner title never carried
    (desk / API write-up, source summaries). Texts are tried in order, lede sentence first; the first confident place wins.
    Keeps the v10 guards: weak towns yield to the story's context, and a place in a country the headline never names
    (when the headline names one) is never used. Returns a geo.db-shaped row (located=1) or None."""
    G = gaz(); title = cl.get("title") or ""
    texts = [t for t in texts if isinstance(t, str) and t.strip()]
    if not texts and not span_texts: return None
    out = {"id": cl.get("cluster_id"), "lat": None, "lon": None, "place": None, "country": None, "country_name": None, "admin1": None, "admin1_code": None,
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
    prior = source_cc(members, cl.get("source_hint") or "")
    tnamed0 = {c for c in _named_countries(title) if c}
    allnamed = set(tnamed0)
    for tx in texts: allnamed |= _named_countries(tx)
    # states / provinces the texts name ("Florida's health department ... Hillsborough"): a town in another state of that country is not it
    nstates = set()
    for tx in [title] + texts:
        for a in extract(tx)["acc"]:
            if a["level"] == "state" and a.get("a1"): nstates.add(a["a1"])
    spans_all = []; multi = False
    hit = resolve_headline_city(title, list(texts) + [t for t in span_texts if isinstance(t, str)], prior)
    if hit and not refine:
        a1 = hit["a1"] if hit.get("a1") in G.admin1 else None
        stn = (G.admin1.get(a1) or {}).get("name", "")
        cn = (G.countries.get(hit["cc"]) or {}).get("name", hit["cc"])
        place = ", ".join(p for p in (hit["name"], stn, cn) if p)
        return fill(hit["lat"], hit["lon"], hit["cc"], a1, "city", method,
                    what + " (headline place + state or county)", "high" if a1 else "medium", place, city=hit["name"],
                    evidence=f"headline place \"{hit['name']}\"" + (f" in {stn}" if stn else ""))
    for i, tx in enumerate(texts):
        if refine and i > 0 and not cue_only: break     # refining a country pin: the lede only ("Two days earlier ... in Khan Younis" is not this strike)
        cp = county_place(tx, prior)
        if cp and not (allnamed - {"US"}):
            a1 = US_POSTAL.get(cp["st"])
            return fill(cp["lat"], cp["lon"], "US", a1, "county", method, what + " (US county, NWS county table)", "high",
                        f"{cp['name']}, {G.admin1.get(a1, {}).get('name', cp['st'])}", evidence=f"matched \"{cp['text']}\" in: {tx[:200]}")
        ex = extract(tx, ctx_cc=prior)
        if i > 0 or cue_only:     # after the lede only a place the sentence marks as one ("in Rakhine State"): "Canada's cyber centre also warned" is who, not where
            ex = dict(ex, acc=[a for a in ex["acc"] if a.get("cue")])
        ch = choose(ex)[0]
        for _try in range(4):
            if not ch: break
            ch = agree(ch, ex, prior, allnamed)
            alt = _better_than_weak(ch, ex, prior, allnamed)
            if alt is None: break
            ex = alt; ch = choose(ex)[0]
        if ch and tnamed0 and ch["cc"] not in tnamed0:
            ch = None
        if ch and ch["level"] == "city":
            same = {x for x in nstates if x.split(".")[0] == ch["cc"]}
            if same and (ch.get("city") or {}).get("a1") not in same: ch = None
        if ch and refine and ch.get("others"):
            own = (ch.get("city") or {}).get("a1") or ch.get("a1")
            own_names = {key_of(G.admin1.get(own, {}).get("name") or ""), key_of(G.countries.get(ch["cc"], {}).get("name") or "")}
            if [o for o in ch["others"] if key_of(o) not in own_names]: ch = None; multi = True     # "Moose Jaw, Saskatchewan" is one place     # "struck Saada, Taiz, Lahj and al-Jawf": several places, keep the country
        if ch and refine and ch["level"] in ("city", "state"):
            ks = {a["k"] for a in ex["acc"] if a["level"] in ("city", "state") and a["cc"] == ch["cc"]}
            own = (ch.get("city") or {}).get("a1") or ch.get("a1")
            ks -= {a["k"] for a in ex["acc"] if a["level"] == "state" and a.get("a1") == own}
            if len(ks) > 1: ch = None; multi = True     # "five in Rogaland, one in Vennesla ... one in Vestby": no single spot, keep the country
        if ch and ch["level"] == "city" and re.search(r"\b" + re.escape(ch.get("text") or "~~") + r"\s+(?:Oblast|Province|Region|Governorate|Prefecture|Voivodeship|Krai|Raion|District|region|province|oblast)\b", tx):
            # "the city of Hlukhiv in Sumy Oblast": the oblast, not its capital; a town the sentence names inside it wins
            a1 = (ch.get("city") or {}).get("a1")
            for sp in (ex.get("spans") or []) + re.findall(r"\b(?:city|town|village|settlement) of ([A-Z][\w'\-]+(?: [A-Z][\w'\-]+)?)", tx):
                hit = small_place(sp, {ch["cc"]}) or next((dict(name=c[0], lat=c[2], lon=c[3], cc=c[4], a1=c[5], pop=c[6]) for c in G.cities
                                                           if c[4] == ch["cc"] and c[5] == a1 and key_of(c[0]) == key_of(sp)), None)
                if hit and (not a1 or hit["a1"] == a1):
                    return fill(hit["lat"], hit["lon"], hit["cc"], hit["a1"] if hit["a1"] in G.admin1 else None, "city", method, what, "medium",
                                f"{hit['name']}, {G.admin1.get(hit['a1'], {}).get('name', '')}, {G.countries.get(hit['cc'], {}).get('name', hit['cc'])}".replace(", ,", ","),
                                city=hit["name"], evidence=f"matched \"{sp}\" in {ch['text']} region in: \u201c{tx[:200]}\u201d")
            if a1 in G.admin1: ch = dict(ch, level="state", a1=a1)
        if ch:
            r = place_from(ch, out, fill, method, what + (f" (source country prior {prior})" if prior else ""), tx)
            if r and r.get("located"):
                r["evidence"] = ((r.get("evidence") or "") + f" in: \u201c{tx[:200]}\u201d")[:300]
                return r
            out.update(located=0)
        spans_all += [x for x in (ex.get("spans") or []) if x not in spans_all]
    for tx in list(texts) + [t for t in span_texts if isinstance(t, str)]:
        if tx not in texts:
            spans_all += [x for x in (extract(tx, ctx_cc=prior).get("spans") or []) if x not in spans_all]
        m = _SOE.match(tx.strip())
        if m and m.group(1) not in spans_all: spans_all.append(m.group(1))
    # Small towns the 34k-city gazetteer lacks ("in Riverhead", "Ocean Shores declares a state of emergency"): the offline GeoNames
    # 500+ table, only for a capitalised name the text itself marks as a place, inside a country the story names or its sources are from.
    alltx = " ".join(list(texts) + [t for t in span_texts if isinstance(t, str)])
    for sp in ([] if multi else spans_all[:4]):
        if not re.search(r"\b(?:in|near|outside|at|of|from)\s+(?:the\s+)?" + re.escape(sp) + r"\b", alltx) and not any(_SOE.match(t.strip() or "") and _SOE.match(t.strip()).group(1) == sp for t in alltx.split("\n")): continue
        ccs = (allnamed - {None}) or ({prior} if prior else set())
        hit = small_place(sp, ccs)
        if hit:
            return fill(hit["lat"], hit["lon"], hit["cc"], hit["a1"] if hit["a1"] in G.admin1 else None, "city", method,
                        what + " (offline GeoNames town table)", "medium" if ccs else "low",
                        f"{hit['name']}, {G.admin1.get(hit['a1'], {}).get('name', '')}, {G.countries.get(hit['cc'], {}).get('name', hit['cc'])}".replace(", ,", ","),
                        city=hit["name"], evidence=f"matched \"{sp}\"")
    return None

_SOE = re.compile(r"^([A-Z][A-Za-z.'\- ]{2,40}?) (?:declares|declared|extends|issues|issued) (?:a |an )?(?:local )?(?:state of emergency|emergency declaration)")
_SP = {"db": None}
_SP_LOCK = threading.Lock()
def _small_db():
    """heatmap_data/small_places_*.tsv (GeoNames cities500 towns of 1,000+ towns missing from cities.json, CC BY 4.0) -> an indexed SQLite copy in the
    temp dir, built once per process (about a second). Never written next to the app's databases; read-only after it is built."""
    import glob
    srcs = sorted(glob.glob(os.path.join(DATA, "small_places_*.tsv")))     # sharded (each file under 1 MB)
    srcs += sorted(glob.glob(os.path.join(DATA, "us_census_places_*.tsv")))
    srcs += sorted(glob.glob(os.path.join(DATA, "us_counties.tsv")))
    if not srcs: return None
    if _SP["db"] and os.path.exists(_SP["db"]): return _SP["db"]
    with _SP_LOCK:
        if _SP["db"] and os.path.exists(_SP["db"]): return _SP["db"]
        import tempfile
        mt = max(int(os.path.getmtime(x)) for x in srcs); dst = os.path.join(tempfile.gettempdir(), f"bn_small_places_{sum(os.path.getsize(x) for x in srcs)}_{mt}.db")
        if not os.path.exists(dst):
            tmp = dst + f".{os.getpid()}.tmp"
            try:
                c = sqlite3.connect(tmp); c.execute("CREATE TABLE p(k TEXT, name TEXT, lat REAL, lon REAL, cc TEXT, a1 TEXT, pop INTEGER)")
                rows = []
                for line in (ln for src in srcs for ln in open(src, encoding="utf-8")):
                    if True:
                        f = line.rstrip("\n").split("\t")
                        if len(f) < 7: continue
                        a1 = f"{f[4]}.{f[5]}"
                        for nm in {f[0], f[1] or f[0]}:
                            k = key_of(nm)
                            if len(k) >= 4: rows.append((k, f[0], float(f[2]), float(f[3]), f[4], a1, int(f[6] or 0)))
                c.executemany("INSERT INTO p VALUES(?,?,?,?,?,?,?)", rows); c.execute("CREATE INDEX pk ON p(k)"); c.commit(); c.close()
                os.replace(tmp, dst)
            except Exception as ex:
                print("geo small_places build failed:", str(ex)[:120], flush=True)
                try: os.remove(tmp)
                except OSError: pass
                return None
        _SP["db"] = dst
        return dst
SMALL_STOP = {"congress", "parliament", "senate", "house", "white house", "court", "government", "police", "army", "navy", "state", "city", "county", "union",
              "republic", "kingdom", "ministry", "capitol", "pentagon", "kremlin", "democrats", "republicans", "america", "media", "europe", "office",
              "department", "embassy", "consulate", "headquarters", "downtown", "midtown", "uptown", "camp", "center", "centre", "market", "station",
              "national", "federal", "global", "international", "breaking", "update", "live", "video", "watch", "read more", "news", "today", "tonight"}
def small_place(name, ccs):
    """name -> {name, lat, lon, cc, a1, pop} from heatmap_data/small_places.db (GeoNames cities500 minus the main gazetteer), or None.
    ccs: allowed countries (named in the story or the sources' country). With none, only a name that exists in a single country."""
    k = key_of(re.sub(r"^(?:the|in|near|at)\s+", "", (name or "").strip(), flags=re.I))
    G = gaz()
    if k in SMALL_STOP or k.split(" ")[-1] in {"county", "parish", "university", "college", "hospital", "airport", "base", "school", "court", "street", "road"}: return None
    if len(k) < 4 or k in GENERIC or k in G.common or k in GIVEN_NAMES or len(k.split()) > 4: return None
    p = _small_db()
    if not p: return None
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
        try: rows = c.execute("SELECT name, lat, lon, cc, a1, pop FROM p WHERE k=? ORDER BY pop DESC", (k,)).fetchall()
        finally: c.close()
    except sqlite3.Error: return None
    if not rows: return None
    L = [dict(zip(("name", "lat", "lon", "cc", "a1", "pop"), r)) for r in rows]
    if ccs:
        L = [x for x in L if x["cc"] in ccs]
        if not L: return None
    elif len({x["cc"] for x in L}) > 1 and not (L[0]["pop"] >= 5000 and L[1]["pop"] * 3 <= L[0]["pop"]): return None

    if len(L) > 1:
        a, b = int(L[0].get("pop") or 0), int(L[1].get("pop") or 0)
        if a <= 0 or b <= 0 or b * 3 > a:
            return None       # two towns of that name: not guessed (unknown census pop counts as ambiguous)
    return L[0]

# v11 (Matt pt1761u, Nov 23 2026): prefer the headline's place plus a state or county the story
# actually names; reject a match whose state contradicts the text; leave the story unlocated
# rather than guess. "Edgewater declares ... amid flooding" + "Volusia County, Fla." is
# Edgewater, Florida, not Depew, NY (the mayor's last name).

# Compact AP / dateline abbreviations the extract() pass does not always treat as a state.
_AP_ADMIN = {"fla": "FL", "calif": "CA", "colo": "CO", "conn": "CT", "del": "DE", "ga": "GA",
             "ill": "IL", "ind": "IN", "kan": "KS", "ky": "KY", "la": "LA", "mass": "MA",
             "md": "MD", "mich": "MI", "minn": "MN", "miss": "MS", "mo": "MO", "mont": "MT",
             "neb": "NE", "nev": "NV", "okla": "OK", "ore": "OR", "pa": "PA", "tenn": "TN",
             "tex": "TX", "vt": "VT", "va": "VA", "wash": "WA", "wis": "WI", "wyo": "WY",
             "ariz": "AZ", "ark": "AR", "ala": "AL"}

def headline_subject(title):
    """The place a 'declares a state of emergency' headline is about, or None if that subject looks like a person."""
    m = _SOE.match((title or "").strip())
    if not m:
        return None
    s = m.group(1).strip()
    s = re.sub(
        r"^(?:Mayor|Governor|Gov\.|Senator|Sen\.|Representative|Rep\.|President|Minister|Judge|"
        r"Dr\.|Mr\.|Mrs\.|Ms\.)\s+",
        "",
        s,
    ).strip()
    if not s:
        return None
    parts = s.split()
    if parts and key_of(parts[0]) in GIVEN_NAMES:
        return None
    if parts and key_of(parts[0]) in HONORIFICS:
        return None
    return s

def named_admin1_codes(texts):
    """Admin1 codes (US.FL, …) actually written in the texts, including 'Fla.' datelines and unique US counties."""
    found = set()
    for tx in texts or []:
        if not tx:
            continue
        try:
            for a in extract(tx)["acc"]:
                if a.get("level") == "state" and a.get("a1"):
                    found.add(a["a1"])
        except Exception:
            pass
        for m in re.finditer(r"\b([A-Za-z]{2,5})\.(?:\s|$)", tx):
            st = _AP_ADMIN.get(m.group(1).lower())
            if st and st in US_POSTAL:
                found.add(US_POSTAL[st])
        cp = county_place(tx)
        if cp and cp.get("st") in US_POSTAL:
            found.add(US_POSTAL[cp["st"]])
        for st in POSTAL_RE.findall(tx):
            if st in US_POSTAL:
                found.add(US_POSTAL[st])
    return found

def cities_named(name, ccs=None, a1s=None):
    """Unique gazetteer or small-places city for this name, filtered by country and/or admin1. None if ambiguous."""
    k = key_of(re.sub(r"^(?:the|in|near|at)\s+", "", (name or "").strip(), flags=re.I))
    if not k or len(k) < 4 or k in SMALL_STOP or k in GENERIC or k in GIVEN_NAMES:
        return None
    G = gaz()
    L = []
    seen = set()
    for kind, idx in (G.idx.get(k) or []):
        if kind != "city":
            continue
        c = G.city(idx)
        key = (round(c["lat"], 4), round(c["lon"], 4), c.get("a1") or "")
        if key in seen:
            continue
        seen.add(key)
        L.append({"name": c["name"], "lat": c["lat"], "lon": c["lon"], "cc": c["cc"], "a1": c["a1"], "pop": c.get("pop") or 0})
    # towns the 34k list lacks
    sp = small_place(name, ccs or set())
    if not sp and not ccs:
        # small_place with no country filter may already have refused; try unfiltered rows through _small_db
        sp = None
    if sp:
        key = (round(sp["lat"], 4), round(sp["lon"], 4), sp.get("a1") or "")
        if key not in seen:
            L.append(sp)
    if ccs:
        L = [x for x in L if x.get("cc") in ccs]
    if a1s:
        L = [x for x in L if x.get("a1") in a1s]
    if not L:
        return None
    L.sort(key=lambda x: -int(x.get("pop") or 0))
    if len(L) > 1:
        a, b = int(L[0].get("pop") or 0), int(L[1].get("pop") or 0)
        if a <= 0 or b <= 0 or b * 3 > a:
            return None
    return L[0]

def resolve_headline_city(title, texts=(), prior=None):
    """Headline place + a state or county the story names. None when that would be a guess."""
    subj = headline_subject(title)
    if not subj:
        return None
    texts = [t for t in ([title] + list(texts or [])) if t]
    a1s = named_admin1_codes(texts)
    ccs = set()
    if prior:
        ccs.add(prior)
    for tx in texts:
        ccs |= {c for c in _named_countries(tx) if c}
    # A unique US county mentioned in the body pins the city to that state.
    for tx in texts:
        cp = county_place(tx, prior)
        if cp and cp.get("st") in US_POSTAL:
            a1s.add(US_POSTAL[cp["st"]])
    hit = cities_named(subj, ccs or None, a1s or None)
    if hit:
        return hit
    # State named, no country named: still try the state filter alone.
    if a1s:
        hit = cities_named(subj, None, a1s)
        if hit:
            return hit
    # Unique town of that name (Ocean Shores): only when no conflicting state was named.
    if not a1s:
        hit = cities_named(subj, ccs or None, None)
        if hit:
            return hit
        hit = small_place(subj, ccs or set())
        if hit:
            return hit
    return None

def place_contradicts_headline(title, place, precision=None, a1=None, texts=()):
    """True when a stored or location-field pin is a different city, or its state contradicts the text."""
    subj = headline_subject(title)
    city = (place or "").split(",")[0].strip()
    prec = (precision or "").lower()
    if subj and city and key_of(city) != key_of(subj):
        if prec not in ("county", "state", "country", "region"):
            # "LA County declares a state of emergency at Castaic's landfill": the county declares, the city it names is where it is.
            if re.search(r"\b(?:county|parish|borough)$", subj, re.I) and re.search(r"(?<![A-Za-z])" + re.escape(city) + r"(?![A-Za-z])", title or "", re.I):
                return False
            return True
    named = named_admin1_codes([title] + list(texts or []))
    if a1 and named:
        same = {x for x in named if x.split(".")[0] == str(a1).split(".")[0]}
        if same and a1 not in same:
            return True
    return False

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
        # Nov 20 2026 (pt1672u): also every cluster the Wire shows for the window (last activity = COALESCE(updated, first_seen)), so the map's set matches the Wire's
        cls = [dict(r) for r in b.execute("SELECT cluster_id, title, category, location, lat, lon, n_items, brief, event_time, first_seen FROM clusters WHERE watchlist IN (0,1) AND (COALESCE(event_time, first_seen)>=? OR first_seen>=? OR COALESCE(updated, first_seen)>=?)", (cut, cut, cut))]
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
