"""Hashtags for the manual Share-to-X button on The Wire and story pages.

Tags are added only to the prefilled composer text (x.com/intent/post). They are
never printed on the page. This module does not post, schedule, or call any
social API.
"""
from __future__ import annotations
import html
import re
from urllib.parse import quote

SITE = "https://blackout.network"
TCO = 23  # X counts a link as 23 characters
MAX_TAGS = 5
MIN_TAGS = 3
GENERIC_TAGS = ["#News", "#WorldNews"]
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

# --------------------------------------------------------------------------- tags
def to_tag(label):
    """CamelCase multi-word tag, no punctuation. None if empty."""
    raw = (label or "").strip()
    if not raw:
        return None
    raw = raw.lstrip("#")
    if re.fullmatch(r"H\d+N\d+", raw, re.I):
        return "#" + raw.upper()
    keep = {
        "US": "US", "USA": "US", "UK": "UK", "DRC": "DRC", "UAE": "UAE",
        "IDF": "IDF", "IRGC": "IRGC", "CVE": "CVE",
    }
    if raw.upper() in keep:
        return "#" + keep[raw.upper()]
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", raw) if p]
    if not parts:
        return None
    if len(parts) == 1 and re.fullmatch(r"H\d+N\d+", parts[0], re.I):
        return "#" + parts[0].upper()
    out = "".join(p[0].upper() + p[1:] for p in parts)
    if len(out) < 2:
        return None
    return "#" + out


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


# --------------------------------------------------------------------------- places
_US_STATES = {
    "alabama": "Alabama", "alaska": "Alaska", "arizona": "Arizona", "arkansas": "Arkansas",
    "california": "California", "colorado": "Colorado", "connecticut": "Connecticut",
    "delaware": "Delaware", "florida": "Florida", "georgia": "Georgia", "hawaii": "Hawaii",
    "idaho": "Idaho", "illinois": "Illinois", "indiana": "Indiana", "iowa": "Iowa",
    "kansas": "Kansas", "kentucky": "Kentucky", "louisiana": "Louisiana", "maine": "Maine",
    "maryland": "Maryland", "massachusetts": "Massachusetts", "michigan": "Michigan",
    "minnesota": "Minnesota", "mississippi": "Mississippi", "missouri": "Missouri",
    "montana": "Montana", "nebraska": "Nebraska", "nevada": "Nevada", "new hampshire": "New Hampshire",
    "new jersey": "New Jersey", "new mexico": "New Mexico", "new york": "New York",
    "north carolina": "North Carolina", "north dakota": "North Dakota", "ohio": "Ohio",
    "oklahoma": "Oklahoma", "oregon": "Oregon", "pennsylvania": "Pennsylvania",
    "rhode island": "Rhode Island", "south carolina": "South Carolina", "south dakota": "South Dakota",
    "tennessee": "Tennessee", "texas": "Texas", "utah": "Utah", "vermont": "Vermont",
    "virginia": "Virginia", "washington": "Washington", "west virginia": "West Virginia",
    "wisconsin": "Wisconsin", "wyoming": "Wyoming", "district of columbia": "District of Columbia",
    "puerto rico": "Puerto Rico", "washington dc": "District of Columbia", "washington, d.c.": "District of Columbia",
    "washington, dc": "District of Columbia",
}
_US_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "PR": "Puerto Rico",
}
# (alias, canonical label, parent label or None). Longest aliases first at runtime.
_COUNTRIES = {
    "democratic republic of the congo": "DRC",
    "the democratic republic of the congo": "DRC",
    "dr congo": "DRC",
    "d.r. congo": "DRC",
    "congo-kinshasa": "DRC",
    "drc": "DRC",
    "congo's": "DRC",
    "congos": "DRC",
    "united states of america": "US",
    "united states": "US",
    "u.s.a.": "US",
    "u.s.": "US",
    "usa": "US",
    "america": "US",  # only as a standalone place, gated below
    "united kingdom": "UK",
    "great britain": "UK",
    "britain": "UK",
    "south sudan": "SouthSudan",
    "south korea": "SouthKorea",
    "north korea": "NorthKorea",
    "saudi arabia": "SaudiArabia",
    "cook islands": "CookIslands",
    "new zealand": "NewZealand",
    "papua new guinea": "PapuaNewGuinea",
    "sri lanka": "SriLanka",
    "el salvador": "ElSalvador",
    "costa rica": "CostaRica",
    "czech republic": "Czechia",
    "united arab emirates": "UAE",
    "burkina faso": "BurkinaFaso",
    "sierra leone": "SierraLeone",
    "ivory coast": "IvoryCoast",
    "cote d'ivoire": "IvoryCoast",
    "côte d'ivoire": "IvoryCoast",
    "central african republic": "CentralAfricanRepublic",
    "republic of the congo": "RepublicOfTheCongo",
    "syria": "Syria",
    "syrian arab republic": "Syria",
    "iran": "Iran",
    "iraq": "Iraq",
    "israel": "Israel",
    "ukraine": "Ukraine",
    "russia": "Russia",
    "russian federation": "Russia",
    "china": "China",
    "taiwan": "Taiwan",
    "japan": "Japan",
    "india": "India",
    "pakistan": "Pakistan",
    "afghanistan": "Afghanistan",
    "mexico": "Mexico",
    "canada": "Canada",
    "brazil": "Brazil",
    "argentina": "Argentina",
    "peru": "Peru",
    "chile": "Chile",
    "colombia": "Colombia",
    "venezuela": "Venezuela",
    "kenya": "Kenya",
    "nigeria": "Nigeria",
    "uganda": "Uganda",
    "ethiopia": "Ethiopia",
    "somalia": "Somalia",
    "sudan": "Sudan",
    "libya": "Libya",
    "egypt": "Egypt",
    "yemen": "Yemen",
    "lebanon": "Lebanon",
    "jordan": "Jordan",
    "turkey": "Turkey",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "france": "France",
    "germany": "Germany",
    "spain": "Spain",
    "italy": "Italy",
    "poland": "Poland",
    "greece": "Greece",
    "australia": "Australia",
    "indonesia": "Indonesia",
    "philippines": "Philippines",
    "vietnam": "Vietnam",
    "thailand": "Thailand",
    "myanmar": "Myanmar",
    "bangladesh": "Bangladesh",
    "haiti": "Haiti",
    "cuba": "Cuba",
    "jamaica": "Jamaica",
    "bahamas": "Bahamas",
    "vanuatu": "Vanuatu",
    "fiji": "Fiji",
    "tonga": "Tonga",
    "samoa": "Samoa",
    "mauritius": "Mauritius",
    "reunion": "Reunion",
    "madagascar": "Madagascar",
    "mozambique": "Mozambique",
    "tanzania": "Tanzania",
    "rwanda": "Rwanda",
    "burundi": "Burundi",
    "angola": "Angola",
    "ghana": "Ghana",
    "mali": "Mali",
    "niger": "Niger",
    "chad": "Chad",
    "cameroon": "Cameroon",
    "morocco": "Morocco",
    "algeria": "Algeria",
    "tunisia": "Tunisia",
    "denmark": "Denmark",
    "sweden": "Sweden",
    "norway": "Norway",
    "finland": "Finland",
    "ireland": "Ireland",
    "netherlands": "Netherlands",
    "belgium": "Belgium",
    "switzerland": "Switzerland",
    "austria": "Austria",
    "hungary": "Hungary",
    "romania": "Romania",
    "bulgaria": "Bulgaria",
    "serbia": "Serbia",
    "croatia": "Croatia",
    "moldova": "Moldova",
    "belarus": "Belarus",
    "lithuania": "Lithuania",
    "latvia": "Latvia",
    "estonia": "Estonia",
    "georgia": "GeorgiaCountry",  # disambiguated below
    "armenia": "Armenia",
    "azerbaijan": "Azerbaijan",
    "kazakhstan": "Kazakhstan",
    "uzbekistan": "Uzbekistan",
    "mongolia": "Mongolia",
    "nepal": "Nepal",
    "bhutan": "Bhutan",
    "cambodia": "Cambodia",
    "laos": "Laos",
    "malaysia": "Malaysia",
    "singapore": "Singapore",
    "brunei": "Brunei",
    "timor-leste": "TimorLeste",
    "east timor": "TimorLeste",
    "qatar": "Qatar",
    "bahrain": "Bahrain",
    "kuwait": "Kuwait",
    "oman": "Oman",
    "palestine": "Palestine",
    "west bank": "WestBank",
    "gaza strip": "Gaza",
    "gaza": "Gaza",
    "crimea": "Crimea",
    "taiwan": "Taiwan",
    "hong kong": "HongKong",
    "paraguay": "Paraguay",
    "uruguay": "Uruguay",
    "bolivia": "Bolivia",
    "ecuador": "Ecuador",
    "panama": "Panama",
    "nicaragua": "Nicaragua",
    "honduras": "Honduras",
    "guatemala": "Guatemala",
    "belize": "Belize",
    "dominican republic": "DominicanRepublic",
    "south africa": "SouthAfrica",
    "namibia": "Namibia",
    "botswana": "Botswana",
    "zimbabwe": "Zimbabwe",
    "zambia": "Zambia",
    "malawi": "Malawi",
    "liberia": "Liberia",
    "guinea": "Guinea",
    "senegal": "Senegal",
    "mauritania": "Mauritania",
    "eritrea": "Eritrea",
    "djibouti": "Djibouti",
    "solomon islands": "SolomonIslands",
    "new caledonia": "NewCaledonia",
    "french guiana": "FrenchGuiana",
    "greenland": "Greenland",
    "iceland": "Iceland",
    "cyprus": "Cyprus",
    "malta": "Malta",
    "albania": "Albania",
    "kosovo": "Kosovo",
    "montenegro": "Montenegro",
    "north macedonia": "NorthMacedonia",
    "macedonia": "NorthMacedonia",
    "slovakia": "Slovakia",
    "slovenia": "Slovenia",
    "bosnia": "Bosnia",
    "bosnia and herzegovina": "Bosnia",
}
# Major cities only: alias -> (city label, parent country/state label)
_CITIES = {
    "kyiv": ("Kyiv", "Ukraine"),
    "kiev": ("Kyiv", "Ukraine"),
    "kharkiv": ("Kharkiv", "Ukraine"),
    "kharkov": ("Kharkiv", "Ukraine"),
    "kryvyi rih": ("KryvyiRih", "Ukraine"),
    "kryvyi rig": ("KryvyiRih", "Ukraine"),
    "krivoy rog": ("KryvyiRih", "Ukraine"),
    "odesa": ("Odesa", "Ukraine"),
    "odessa": ("Odesa", "Ukraine"),
    "lviv": ("Lviv", "Ukraine"),
    "dnipro": ("Dnipro", "Ukraine"),
    "dnipropetrovsk": ("Dnipro", "Ukraine"),
    "mariupol": ("Mariupol", "Ukraine"),
    "donetsk": ("Donetsk", "Ukraine"),
    "luhansk": ("Luhansk", "Ukraine"),
    "zaporizhzhia": ("Zaporizhzhia", "Ukraine"),
    "kherson": ("Kherson", "Ukraine"),
    "miami": ("Miami", "Florida"),
    "miami-dade": ("Miami", "Florida"),
    "tampa": ("Tampa", "Florida"),
    "orlando": ("Orlando", "Florida"),
    "jacksonville": ("Jacksonville", "Florida"),
    "tallahassee": ("Tallahassee", "Florida"),
    "fort lauderdale": ("FortLauderdale", "Florida"),
    "west palm beach": ("WestPalmBeach", "Florida"),
    "los angeles": ("LosAngeles", "California"),
    "san francisco": ("SanFrancisco", "California"),
    "san diego": ("SanDiego", "California"),
    "san jose": ("SanJose", "California"),
    "sacramento": ("Sacramento", "California"),
    "oakland": ("Oakland", "California"),
    "new york city": ("NewYorkCity", "New York"),
    "new york": ("NewYorkCity", "New York"),  # gated: only if not the state alone
    "chicago": ("Chicago", "Illinois"),
    "houston": ("Houston", "Texas"),
    "dallas": ("Dallas", "Texas"),
    "austin": ("Austin", "Texas"),
    "san antonio": ("SanAntonio", "Texas"),
    "seattle": ("Seattle", "Washington"),
    "boston": ("Boston", "Massachusetts"),
    "atlanta": ("Atlanta", "Georgia"),
    "denver": ("Denver", "Colorado"),
    "phoenix": ("Phoenix", "Arizona"),
    "portland": ("Portland", "Oregon"),
    "detroit": ("Detroit", "Michigan"),
    "philadelphia": ("Philadelphia", "Pennsylvania"),
    "pittsburgh": ("Pittsburgh", "Pennsylvania"),
    "baltimore": ("Baltimore", "Maryland"),
    "new orleans": ("NewOrleans", "Louisiana"),
    "nashville": ("Nashville", "Tennessee"),
    "charlotte": ("Charlotte", "North Carolina"),
    "raleigh": ("Raleigh", "North Carolina"),
    "minneapolis": ("Minneapolis", "Minnesota"),
    "las vegas": ("LasVegas", "Nevada"),
    "salt lake city": ("SaltLakeCity", "Utah"),
    "honolulu": ("Honolulu", "Hawaii"),
    "london": ("London", "UK"),
    "paris": ("Paris", "France"),
    "berlin": ("Berlin", "Germany"),
    "moscow": ("Moscow", "Russia"),
    "tehran": ("Tehran", "Iran"),
    "jerusalem": ("Jerusalem", "Israel"),
    "tel aviv": ("TelAviv", "Israel"),
    "beirut": ("Beirut", "Lebanon"),
    "damascus": ("Damascus", "Syria"),
    "baghdad": ("Baghdad", "Iraq"),
    "sanaa": ("Sanaa", "Yemen"),
    "sana'a": ("Sanaa", "Yemen"),
    "riyadh": ("Riyadh", "SaudiArabia"),
    "dubai": ("Dubai", "UAE"),
    "cairo": ("Cairo", "Egypt"),
    "nairobi": ("Nairobi", "Kenya"),
    "lagos": ("Lagos", "Nigeria"),
    "kampala": ("Kampala", "Uganda"),
    "kinshasa": ("Kinshasa", "DRC"),
    "goma": ("Goma", "DRC"),
    "ituri": ("Ituri", "DRC"),
    "north kivu": ("NorthKivu", "DRC"),
    "south kivu": ("SouthKivu", "DRC"),
    "juba": ("Juba", "SouthSudan"),
    "taipei": ("Taipei", "Taiwan"),
    "beijing": ("Beijing", "China"),
    "shanghai": ("Shanghai", "China"),
    "tokyo": ("Tokyo", "Japan"),
    "seoul": ("Seoul", "SouthKorea"),
    "pyongyang": ("Pyongyang", "NorthKorea"),
    "mexico city": ("MexicoCity", "Mexico"),
    "lima": ("Lima", "Peru"),
    "bogota": ("Bogota", "Colombia"),
    "bogotá": ("Bogota", "Colombia"),
    "caracas": ("Caracas", "Venezuela"),
    "havana": ("Havana", "Cuba"),
    "port-au-prince": ("PortAuPrince", "Haiti"),
    "sydney": ("Sydney", "Australia"),
    "melbourne": ("Melbourne", "Australia"),  # skipped when a US state is also present
}

_SKIP_LOC = re.compile(
    r"^\s*(global(?:\s*\([^)]*\))?|worldwide|earth|software|internet|international|"
    r"location not specified(?: by source)?|not specified|unknown|n/?a)\s*$",
    re.I,
)
_VAGUE_GEO = re.compile(
    r"\b(ridge|rise|trench|fracture zone|pacific-antarctic|mid-atlantic|"
    r"indian ocean|southern ocean|arctic ocean|antarctica|antarctic)\b",
    re.I,
)
_DIR_OF = re.compile(r"\b(?:[NS][EW]?|north|south|east|west|northeast|northwest|southeast|southwest)\s+of\b", re.I)
_ABBR_RX = re.compile(
    r"(?:^|[,;/(]|\s)(?<!\d )(?<!\d)(" + "|".join(sorted(_US_ABBR, key=len, reverse=True)) + r")\b"
)


def _corpus(item, headline=None):
    """Location, title, brief WHERE, and brief text — the fields the generator may read."""
    loc = _norm(item.get("location") or "")
    title = _norm(item.get("title") or item.get("h") or "")
    display = _norm(headline or item.get("headline") or "") or title
    brief = item.get("brief") or ""
    where = ""
    if brief:
        m = re.search(r"WHERE:\s*(.+?)(?=\s+(?:WHAT|WHERE|WHEN|CONFIDENCE|VERIFY):|$)", brief, re.S)
        if m:
            where = _norm(re.sub(r"\(approx\.[^)]*\)", "", m.group(1)))
    parts = [display, title, loc, where]
    # named entities if a brief or cluster already extracted them
    ents = item.get("entities") or item.get("places") or []
    if isinstance(ents, dict):
        ents = list(ents.values()) if not any(isinstance(v, (list, tuple)) for v in ents.values()) else [
            x for v in ents.values() for x in (v if isinstance(v, (list, tuple)) else [v])
        ]
    for e in ents:
        if isinstance(e, str) and e.strip():
            parts.append(e.strip())
        elif isinstance(e, dict):
            n = e.get("name") or e.get("text") or e.get("label") or ""
            if n:
                parts.append(str(n))
    return loc, title, where, " \n ".join(p for p in parts if p), display


def _find_places(text, loc):
    """Return (parent_tags, city_tags) as canonical labels, order preserved, no dups."""
    if not text or _SKIP_LOC.match(loc or ""):
        # still allow title/brief places when the stored location is empty
        if not text:
            return [], []
        if loc and _SKIP_LOC.match(loc) and not (text or "").replace(loc, "").strip():
            return [], []
    raw = _DIR_OF.sub(" ", text)
    low = raw.lower()
    parents, cities = [], []

    def add(bucket, label):
        if label and label not in bucket:
            bucket.append(label)

    # Countries / regions, longest alias first
    for alias in sorted(_COUNTRIES, key=len, reverse=True):
        if alias == "america":
            if not re.search(r"\b(?:united states of )?america\b", low):
                continue
            if re.search(r"\b(?:latin|south|central|north)\s+america\b", low):
                continue
        if alias == "georgia":
            # US state wins when a US city/state cue is present; otherwise skip (ambiguous)
            continue
        if alias == "guinea" and re.search(r"\bpapua new guinea\b|\bequatorial guinea\b|\bguinea-bissau\b", low):
            continue
        if alias == "sudan" and re.search(r"\bsouth sudan\b", low):
            continue
        if alias == "congo" or alias == "republic of the congo":
            if re.search(r"\b(?:democratic republic|dr congo|d\.r\. congo|drc|congo-kinshasa)\b", low):
                continue
        if not re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
            continue
        add(parents, _COUNTRIES[alias])

    # US states by name
    for alias in sorted(_US_STATES, key=len, reverse=True):
        if alias == "washington":
            if not re.search(r"\bwashington\s+(state|county)\b|\bstate of washington\b", raw, re.I):
                # bare "Washington" is too often the city / DC / the person
                if not re.search(r"\bWashington\b", raw):
                    continue
                continue
        if not re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
            continue
        add(parents, _US_STATES[alias])

    # US state abbreviations (comma/segment form; not "20 NM" or "NE of")
    for m in _ABBR_RX.finditer(raw):
        abbr = m.group(1)
        # skip direction "NE of" already stripped; still skip trailing "NM" after a number handled by lookbehind
        after = raw[m.end():m.end() + 4]
        if re.match(r"\s+of\b", after, re.I):
            continue
        add(parents, _US_ABBR[abbr])

    # Cities
    us_present = any(p in _US_STATES.values() or p in ("US",) for p in parents)
    for alias in sorted(_CITIES, key=len, reverse=True):
        if not re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
            continue
        city, parent = _CITIES[alias]
        if alias == "melbourne" and us_present:
            continue  # Melbourne, FL vs Australia
        if alias == "nassau" or city == "Nassau":
            continue
        if alias == "new york":
            # "New York" as the state: only treat as the city with a city cue
            if not re.search(r"\bnew york city\b|\bnyc\b|\bmanhattan\b|\bbrooklyn\b", low):
                if re.search(r"\bnew york\b", low) and "New York" not in parents:
                    add(parents, "New York")
                continue
        # "Dnipro River" / "Kyiv Oblast" are not the city itself
        m = re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low)
        if m:
            rest = low[m.end():m.end()+16]
            if re.match(r"\s+(river|oblast|region|province|district|bay|sea|ocean|county)\b", rest):
                continue
        add(cities, city)
        add(parents, parent)

    # Bare "US" / "U.S." in a title (avoid the pronoun "us" by requiring capitals or punctuation)
    if re.search(r"(?<![A-Za-z])U\.S\.?s?\b|(?<![A-Za-z])US\b(?![A-Za-z])", raw) and "US" not in parents:
        # skip USGS / USA / USB etc. — USA already mapped; USGS is US + GS so need not letter after
        if not re.search(r"\bUSGS\b|\bUSB\b|\bUSC\b|\bUSD\b|\bUSP\b", raw):
            add(parents, "US")

    # Bare "Congo" / "Congo's" as DRC when the story is clearly about the DRC, not Brazzaville
    if re.search(r"\bcongo'?s?\b", raw, re.I) and "DRC" not in parents and "RepublicOfTheCongo" not in parents:
        if re.search(r"\b(ebola|ituri|kinshasa|goma|kivu|bundibugyo|m23|drc)\b", raw, re.I) or re.search(
                r"\bdemocratic republic\b|\bdr congo\b", raw, re.I):
            add(parents, "DRC")

    # Drop "GeorgiaCountry" unless clearly the country
    if "GeorgiaCountry" in parents:
        parents = [p for p in parents if p != "GeorgiaCountry"]
        if re.search(r"\btbilisi\b|\babkhazia\b|\bsouth ossetia\b|georgia \(country\)", low):
            add(parents, "Georgia")

    # Vague ocean / ridge text should not produce a place tag on its own
    if not parents and not cities and _VAGUE_GEO.search(low):
        return [], []

    # "Global (software)" etc.
    if loc and _SKIP_LOC.match(loc):
        # keep places found in the title/brief, but not "Global"
        pass

    return parents, cities


def _first_pos(blob, label, aliases):
    """Index of the earliest alias for this label in blob, or a large number."""
    low = (blob or "").lower()
    best = 10**9
    for a in aliases:
        m = re.search(r"(?<![a-z])" + re.escape(a) + r"(?![a-z])", low)
        if m and m.start() < best:
            best = m.start()
    return best


def _alias_map():
    alias_of = {}
    for a, lab in _COUNTRIES.items():
        alias_of.setdefault(lab, []).append(a)
    for a, lab in _US_STATES.items():
        alias_of.setdefault(lab, []).append(a)
    for a, lab in _US_ABBR.items():
        alias_of.setdefault(lab, []).append(a.lower())
    for a, (city, parent) in _CITIES.items():
        alias_of.setdefault(city, []).append(a)
        alias_of.setdefault(parent, []).append(a)
    alias_of.setdefault("DRC", []).extend(["congo", "congo's", "congos"])
    alias_of.setdefault("US", []).extend(["us", "u.s.", "u.s", "u.s.a."])
    return alias_of


def _city_parent(city):
    for _a, (c, parent) in _CITIES.items():
        if c == city:
            return parent
    return None


def location_tags(item, headline=None):
    """1–2 location tags: primary country/state, then a city or region.

    Prefers the place named in the headline over secondary countries on the
    cluster (e.g. DRC Ebola should not pick up Kenya/Nigeria from a WHO byline).
    """
    loc, title, where, blob, display = _corpus(item, headline=headline)
    if loc and _SKIP_LOC.match(loc) and not title and not where and not display:
        return []
    parents, cities = _find_places(blob, loc)
    hl_parents, hl_cities = _find_places(" ".join(x for x in (display, title) if x), "")
    alias_of = _alias_map()
    hl_blob = " ".join(x for x in (display, title) if x)

    def pos(lab, text):
        return _first_pos(text, lab, alias_of.get(lab, [lab.lower()]))

    # If the headline/title names a country, drop cluster countries that it does not name.
    if hl_parents:
        parents = [p for p in parents if p in hl_parents] or hl_parents[:]
        keep_cities = []
        for c in hl_cities + cities:
            parent = _city_parent(c)
            if c in hl_cities or (parent and parent in parents):
                if c not in keep_cities:
                    keep_cities.append(c)
        cities = keep_cities

    # Primary country: preposition + event ("amid DR Congo outbreak"), possessive
    # ("Congo's Ebola", "Ukraine's Kryvyi Rih"), else first country in the headline.
    primary = None
    ev = re.search(
        r"\b(?:amid|in|inside|across|near|from|of)\s+(.{2,40}?\s+)?(outbreak|war|invasion|strike|conflict|epidemic)\b",
        hl_blob, re.I)
    if ev:
        window = ev.group(0)
        wp, _ = _find_places(window, "")
        if wp:
            primary = wp[0]
    if not primary:
        # "Congo's Ebola" / "Ukraine's Kryvyi Rih"
        poss, _ = _find_places(hl_blob, "")
        m = re.search(r"\b([A-Z][^.]{1,40}?)(?:'s|’s)\s", display or title or "")
        if m:
            pp, _ = _find_places(m.group(1), "")
            if pp:
                primary = pp[0]
    if not primary and hl_parents:
        # first country as it appears in the headline
        primary = sorted(hl_parents, key=lambda lab: (pos(lab, hl_blob), hl_parents.index(lab)))[0]
    if not primary and parents:
        primary = parents[0]

    # Trailing list after the primary ("DRC, Kenya and Nigeria") stays dropped.
    second_countries = []
    if primary:
        ppos = pos(primary, hl_blob)
        for p in hl_parents:
            if p == primary:
                continue
            if pos(p, hl_blob) < ppos:
                second_countries.append(p)  # mentioned before the primary (Uganda ... amid DRC outbreak)
        second_countries.sort(key=lambda p: pos(p, hl_blob))
        parents = [primary] + [p for p in second_countries if p != primary]
    else:
        parents = parents[:1]

    # City/region of the primary, from the headline when possible
    cities = [c for c in (hl_cities + cities) if (not primary) or _city_parent(c) in (primary, None) or c in hl_cities]
    # De-dupe cities
    seen_c = []
    for c in cities:
        if c not in seen_c:
            seen_c.append(c)
    cities = seen_c

    labels = []
    if primary:
        labels.append(primary)
    for c in cities:
        if c not in labels:
            labels.append(c)
            break  # one city/region only
    if len(labels) < 2:
        for p in parents:
            if p not in labels:
                labels.append(p)
                break
    tags = []
    for lab in labels[:2]:
        tg = to_tag(lab)
        if tg and tg not in tags:
            tags.append(tg)
    return tags


# --------------------------------------------------------------------------- topics (any rank)
_DISEASES = [
    # (regex, tag label) — more specific first
    (r"\bh5n1\b", "H5N1"),
    (r"\bh5n9\b", "H5N9"),
    (r"\bh5n\d\b|\bavian flu\b|\bbird flu\b|\binfluenza a\b", "BirdFlu"),
    (r"\bebola\b", "Ebola"),
    (r"\bmarburg\b", "Marburg"),
    (r"\bmeasles\b", "Measles"),
    (r"\bmpox\b|\bmonkeypox\b", "Mpox"),
    (r"\bcholera\b", "Cholera"),
    (r"\bdengue\b", "Dengue"),
    (r"\bpolio\b|\bpoliovirus\b", "Polio"),
    (r"\bcovid-?19\b|\bsars-cov-2\b", "Covid19"),
    (r"\bnipah\b", "Nipah"),
    (r"\banthrax\b", "Anthrax"),
    (r"\bplague\b", "Plague"),
    (r"\btuberculosis\b|\b\btb treatment\b", "Tuberculosis"),
]
_HAZARDS = [
    (r"\bhurricanes?\b", "Hurricane"),
    (r"\btyphoons?\b", "Typhoon"),
    (r"\b(tropical )?cyclones?\b", "Cyclone"),
    (r"\bwildfires?\b|\bforest fires?\b", "Wildfire"),
    (r"\bearthquakes?\b|\bquakes?\b|\bM\s*\d+\.\d+\b", "Earthquake"),
    (r"\btsunamis?\b", "Tsunami"),
    (r"\btornado(?:es|s)?\b", "Tornado"),
    (r"\bflash floods?\b|\bflood(?:ing|s|ed)?\b", "Flood"),
    (r"\bhigh winds?\b|\bhigh wind warning\b", "HighWind"),
    (r"\bvolcan(?:o|ic|oes)\b|\beruption\b", "Volcano"),
    (r"\bblizzard\b|\bsnowstorm\b", "Blizzard"),
    (r"\bheat ?wave\b", "HeatWave"),
    (r"\bsevere rain\b|\bheavy rain\b|\bstorms?\b|\brains?\b", "Storm"),
]
_TEST_EVT = re.compile(r"\bTEST\b.*\b(warning|watch|advisory|issued)\b|\b(warning|watch|advisory)\b.*\bTEST\b", re.I)


def _text_for_topic(item, headline=None):
    loc, title, where, blob, display = _corpus(item, headline=headline)
    return f"{display}\n{title}\n{blob}"


def _cat(item, headline=None):
    title = headline or item.get("headline") or item.get("title") or ""
    try:
        import story_display as SD
        return (SD.display_category(title, item.get("category") or "") or "").lower()
    except Exception:
        return (item.get("category") or "").lower()


def topic_tags(item, headline=None):
    """Specific topic tags (disease name, strike type, hazard, cyber)."""
    title = headline or item.get("headline") or item.get("title") or item.get("h") or ""
    blob = _text_for_topic(item, headline=headline)
    # Prefer the title/headline for strike type so we do not invent tags from a brief
    lead = title or blob
    low = blob.lower()
    cat = _cat(item, headline=headline)
    tags = []

    def add(label):
        t = to_tag(label)
        if t and t not in tags:
            tags.append(t)

    if _TEST_EVT.search(title or ""):
        add("Test")
        return tags

    # Disease names
    if cat == "disease" or any(re.search(p, blob, re.I) for p, _ in _DISEASES):
        quick = bool(re.match(r"\s*quick takes:", title or "", re.I))
        for pat, lab in _DISEASES:
            if re.search(pat, blob, re.I):
                add(lab)
                if quick:
                    break
        if any(x in tags for x in ("#H5N1", "#H5N9")) and "#BirdFlu" in tags:
            tags.remove("#BirdFlu")

    # Hazards
    if cat in ("natural disaster",) or any(re.search(p, blob, re.I) for p, _ in _HAZARDS):
        for pat, lab in _HAZARDS:
            if re.search(pat, blob, re.I):
                add(lab)
                break  # one primary hazard

    # Conflict
    conflictish = cat in ("war/conflict", "conflict") or re.search(
        r"\b(missile|airstrike|air strike|artillery|shelling|invasion|drone attack|"
        r"ballistic|combat|bombard|offensive|warship)\b", blob, re.I)
    if conflictish:
        if re.search(r"\bukraine\b|\bkyiv\b|\bkiev\b|\bkharkiv\b|\bkryvyi\b", low):
            add("UkraineWar")
        # Strike type next so it keeps a topic slot when the title actually says so
        if re.search(r"\bdrone(?:\s+and\s+missile)?\s+(?:strike|attack|assault)s?\b|\buav\b", lead, re.I):
            add("DroneStrike")
        elif re.search(r"\b(?:ballistic\s+)?missiles?\s+(?:strike|attack|hits?|hit|launches?)\b|"
                       r"\b(?:strike|attack)\s+[^.]{0,40}missiles?\b|"
                       r"\bballistic missile", lead, re.I):
            add("MissileStrike")
        elif re.search(r"\bairstrikes?\b|\bair strikes?\b", lead, re.I):
            add("Airstrike")
        if re.search(r"\brussia(?:n)?\b|\bkremlin\b|\bmoscow\b", low) and re.search(
                r"\b(ukraine|kyiv|kiev|missile|strike|invasion|war)\b", low):
            add("Russia")
        if re.search(r"\bgaza\b|\bhamas\b", low):
            add("Gaza")
        if re.search(r"\bisrael(?:i)?\b|\bidf\b", low) and re.search(r"\b(gaza|hamas|hezbollah|airstrike|strike)\b", low):
            add("Israel")
        if re.search(r"\bhouthi|\bansarallah\b", low):
            add("Houthis")

    # Cyber
    if cat == "cyber" or re.search(r"\b(data breach|ransomware|cve-\d|remote code execution|cyber ?attack)\b", low):
        if re.search(r"\bcve-\d", low):
            add("CVE")
        if re.search(r"\bdata breach\b|\bbreached\b", low):
            add("DataBreach")
        elif re.search(r"\bransomware\b", low):
            add("Ransomware")
        else:
            add("Cybersecurity")

    return tags


def engagement_tags(item, headline=None):
    """One high-engagement category tag, at any rank."""
    cat = _cat(item, headline=headline)
    title = headline or item.get("headline") or item.get("title") or ""
    blob = _text_for_topic(item, headline=headline)
    tags = []

    def add(label):
        t = to_tag(label)
        if t and t not in tags:
            tags.append(t)

    if _TEST_EVT.search(title or ""):
        add("News")
        return tags[:1]
    if cat == "disease" or any(re.search(p, blob, re.I) for p, _ in _DISEASES):
        add("Outbreak")
    elif cat == "cyber" or re.search(r"\b(cve-\d|data breach|ransomware|remote code execution|cyber ?attack)\b", blob, re.I):
        add("Cyberattack")
    elif cat in ("war/conflict", "conflict") or re.search(
            r"\b(missile|airstrike|invasion|artillery|shelling|ukraine war|drone strike)\b", blob, re.I):
        add("War")
    elif re.search(
            r"\b(hurricanes?|typhoons?|cyclones?|tornado(?:es|s)?|flood(?:ing|s|ed)?|"
            r"storms?|blizzards?|wildfires?|heat ?waves?|severe rain|heavy rain|rains?|"
            r"high winds?)\b",
            blob, re.I) or (
            cat in ("natural disaster",) and re.search(r"\b(rain|storms?|flood(?:ing|s)?|weather|wind)\b", blob, re.I)
    ):
        add("Weather")
    else:
        add("BreakingNews" if _rank(item) >= 8 else "News")
    return tags[:1]


# --------------------------------------------------------------------------- held / false-positive
def is_held(item):
    if item.get("hidden"):
        return True
    wl = item.get("watchlist")
    if wl in (1, True, "1"):
        return True
    cid = str(item.get("cluster_id") or item.get("id") or "")
    if not cid:
        return False
    try:
        import home_feed
        if cid in getattr(home_feed, "ROW_BLOCK", set()):
            return True
    except Exception:
        pass
    return False


def _rank(item):
    try:
        r = item.get("rank")
        if r is None and item.get("r") is not None:
            r = item.get("r")
        return int(r) if r is not None and r != "" else 0
    except (TypeError, ValueError):
        return 0


def _dedupe(tags, limit=MAX_TAGS):
    out = []
    for t in tags:
        if t and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def hashtags(item, headline=None):
    """1–2 location, 1–2 topic, 1 engagement. Always 3–5 tags (held: location + 2 generic)."""
    loc = location_tags(item, headline=headline)
    if is_held(item):
        tags = loc[:2] + [g for g in GENERIC_TAGS]
        return _dedupe(tags + GENERIC_TAGS, MAX_TAGS) if len(_dedupe(tags)) < MIN_TAGS else _dedupe(tags)
    topics = topic_tags(item, headline=headline)
    eng = engagement_tags(item, headline=headline)
    tags = _dedupe(loc[:2] + topics[:2] + eng[:1], MAX_TAGS)
    extras = loc[2:] + topics[2:]
    for e in extras + GENERIC_TAGS:
        if len(tags) >= MIN_TAGS:
            break
        if e not in tags:
            tags.append(e)
    return _dedupe(tags, MAX_TAGS)


# --------------------------------------------------------------------------- compose / intent
def _headline(item, headline=None):
    h = headline or item.get("headline") or item.get("h")
    if not h:
        raw = item.get("title") or ""
        try:
            import theme
            h = theme._headline(raw)
        except Exception:
            h = raw
    h = _norm(h or item.get("title") or "")
    # drop leading emoji / decorative symbols so the composer starts on words
    h = re.sub(r"^[\W_\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\-—–]+", "", h, flags=re.U).strip()
    return h


def story_url(item):
    cid = item.get("cluster_id") or item.get("id") or ""
    if not cid:
        return SITE + "/wire"
    return f"{SITE}/wire/{cid}"


def _join(headline, tags):
    bits = [headline] if headline else []
    if tags:
        bits.append(" ".join(tags))
    return " ".join(bits).strip()


def weighted_len(text, url):
    """X's length: the url param is a t.co link (23 chars) plus a separating space."""
    n = len(text or "")
    if url:
        n += 1 + TCO
    return n


def share_text(item, url=None, headline=None):
    """Headline + hashtags, trimmed so headline + tags + t.co link fit in 280.

    Drops the lowest-priority tag first when over budget, but never below MIN_TAGS;
    the headline is shortened instead.
    """
    url = url if url is not None else story_url(item)
    h = _headline(item, headline)
    tags = hashtags(item, headline=headline)
    text = _join(h, tags)
    while len(tags) > MIN_TAGS and weighted_len(text, url) > 280:
        tags = tags[:-1]
        text = _join(h, tags)
    if weighted_len(text, url) > 280:
        budget = 280 - (1 + TCO if url else 0)
        if tags:
            tail = " " + " ".join(tags)
            budget -= len(tail)
        else:
            tail = ""
        budget = max(8, budget)
        cut = h[: budget - 1].rsplit(" ", 1)[0].rstrip(",;:-—– ") if " " in h[:budget] else h[: budget - 1]
        h = cut + "…"
        text = _join(h, tags)
    return text


def intent_url(item, url=None, headline=None):
    page = url if url is not None else story_url(item)
    text = share_text(item, url=page, headline=headline)
    return f"https://x.com/intent/post?text={quote(text, safe='')}&url={quote(page, safe='')}"


def button_html(item, headline=None, cls="w2-btn-s", label="Post on X"):
    """Compact Post on X control in the existing Wire button style. Tags live only in href."""
    href = intent_url(item, headline=headline)
    klass = "w2-btn " + (cls or "")
    return (
        f'<a class="{E(klass.strip())}" href="{E(href)}" target="_blank" rel="noopener">'
        f"{E(label)}"
        f'<svg viewBox="0 0 20 10" aria-hidden="true"><path d="M0 5h18M14 1l4 4-4 4" fill="none" stroke="currentColor"/></svg>'
        f"</a>"
    )


def timeline_button_html(item, cls="w2-btn tl-go"):
    """Timeline drawer button (no decorative svg; matches Full story)."""
    href = item.get("xu") or intent_url(item)
    if not href:
        return ""
    return (
        f'<a class="{E(cls)}" href="{E(href)}" target="_blank" rel="noopener">Post on X</a>'
    )
