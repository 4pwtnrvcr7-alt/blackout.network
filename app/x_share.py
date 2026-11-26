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
GENERIC_TAGS = ["#News", "#WorldNews", "#Breaking"]

# Combat wording only — "nuclear bomb test", "nuclear weapons testing", and a stored
# conflict category are not enough. #War / #Conflict are treated as generic otherwise.
_ARMED_RX = re.compile(
    r"\b(missile strikes?|missile attacks?|airstrikes?|air strikes?|artillery|shelling|invasion|"
    r"drone (?:attack|strike)s?|ballistic(?:\s+missile)?\s+(?:strikes?|attacks?|hits?)|"
    r"combat|bombard(?:ment)?|offensive|warship|aerial attacks?|ground assault|"
    r"ceasefire|battlefield|front lines?|troop(?:s)? (?:advance|attack)|ukraine war|"
    r"declaration of war|invades?|invaded|struck in (?:an?\s+)?(?:aerial |air )?attack)\b",
    re.I,
)
_NOT_ARMED_RX = re.compile(
    r"\bnuclear\s+(?:bomb\s+|weapons?\s+)?tests?\b|\bbomb\s+tests?\b|"
    r"\btest\s+veterans?\b|\bweapons?\s+testing\b",
    re.I,
)
_ARMS_PACKAGE_RX = re.compile(
    r"\b(arms package|weapons? package|military aid|weapons? aid|air[- ]defense systems?|"
    r"anti-ballistic|interceptors?|missiles? for\b|export approval|not yet approved a new arms)\b",
    re.I,
)
SOFT_GENERICS = {"#War", "#Conflict"}


def _location_value(item):
    return item.get("location") or item.get("loc") or ""


def _item_text(item, headline=None):
    """Title, brief/body, location, and source titles — what the extractor may read."""
    parts = [
        headline or item.get("headline") or "",
        item.get("title") or item.get("h") or "",
        _strip_related(_as_text(item.get("brief"), item.get("d"))),
        _strip_related(_as_text(item.get("body"), item.get("text"))),
        _location_value(item),
    ]
    for L in item.get("links") or item.get("l") or item.get("sources") or []:
        if isinstance(L, dict):
            parts.append(str(L.get("title") or L.get("s") or L.get("source") or L.get("name") or ""))
        elif isinstance(L, str):
            parts.append(L)
    out = " ".join(str(p) for p in parts if p)
    try:   # Nov 25 2026 9:27 PM: "forces storm a building" must not earn #Storm/#Weather
        import storm_verb
        out = storm_verb.strip(out)
    except Exception:
        pass
    return out


def armed_conflict(item, headline=None):
    """True only when the story text is about armed conflict, not a stored category."""
    text = _item_text(item, headline=headline)
    # An arms/aid package that merely names missiles (Patriot, NASAMS, F-16) is not a strike.
    if _ARMS_PACKAGE_RX.search(text) and not re.search(
            r"\b(struck|were hit|was hit|missile strike|airstrike|air strike|drone strike|shelling|invasion)\b", text, re.I):
        return False
    if _NOT_ARMED_RX.search(text) and not _ARMED_RX.search(text):
        return False
    return bool(_ARMED_RX.search(text))


def _as_text(*vals):
    """First string value; ignore dicts (a timeline bug once passed the item itself as `d`)."""
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _strip_related(s):
    """Related-story titles are appended to some write-ups; they must not feed this story's tags."""
    if not s or not isinstance(s, str):
        return s or ""
    return re.split(r"Related stories we are also tracking\s*:", s, maxsplit=1, flags=re.I)[0].strip()


def _normalize_item(item):
    it = dict(item or {})
    if not _as_text(it.get("title")):
        it["title"] = _as_text(it.get("h"), it.get("headline"))
    if not _as_text(it.get("location")):
        it["location"] = _as_text(it.get("loc"))
    if not _as_text(it.get("category")):
        it["category"] = _as_text(it.get("k"), it.get("cat"))
    if not _as_text(it.get("brief")):
        it["brief"] = _strip_related(_as_text(it.get("d"), it.get("body"), it.get("text")))
    if isinstance(it.get("body"), str):
        it["body"] = _strip_related(it["body"])
    if isinstance(it.get("d"), str):
        it["d"] = _strip_related(it["d"])
    elif it.get("d") is not None and not isinstance(it.get("d"), str):
        it["d"] = ""
    try:   # a raid misfiled as natural disaster is war/conflict for tags too
        import storm_verb
        it["category"] = storm_verb.fix_category(it.get("category") or "", it.get("title") or "")
    except Exception:
        pass
    return it


def specific_tags(tags, item=None, headline=None):
    """Tags that name a person, place, or topic — not generic fillers or unearned #War/#Conflict."""
    gen = set(GENERICS) if "GENERICS" in globals() else {"#News", "#WorldNews", "#Breaking", "#BreakingNews"}
    gen |= {"#News", "#WorldNews", "#Breaking", "#BreakingNews", "#BlackoutNetwork", "#Alerts"}
    if item is None or not armed_conflict(item, headline=headline):
        gen |= SOFT_GENERICS
    return [t for t in (tags or []) if t not in gen]


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
    "uk": "UK",
    "u.k.": "UK",
    "u.k": "UK",
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
    "czechia": "Czechia",
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
    "manchester": ("Manchester", "UK"),
    "greater manchester": ("Manchester", "UK"),
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
    loc = _norm(_location_value(item))
    title = _norm(item.get("title") or item.get("h") or "")
    display = _norm(headline or item.get("headline") or "") or title
    brief = " ".join(_strip_related(_as_text(x)) for x in (
        item.get("brief"), item.get("d"), item.get("body"), item.get("text"),
    ) if _as_text(x))
    where = ""
    if brief:
        m = re.search(r"WHERE:\s*(.+?)(?=\s+(?:WHAT|WHERE|WHEN|CONFIDENCE|VERIFY):|$)", brief, re.S)
        if m:
            where = _norm(re.sub(r"\(approx\.[^)]*\)", "", m.group(1)))
    # Include the brief/body so a missing location field can still yield a place (#UK from "UK sets up…").
    parts = [display, title, loc, where, _norm(brief[:800]) if brief else ""]
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
        if alias in ("us", "u.s.", "u.s", "usa", "u.s.a.", "america"):
            # "US Secretary of War" / "US President" is a role, not the story's location
            if re.search(r"\b(?:us|u\.s\.?|usa|u\.s\.a\.)\s+(secretary|president|defense|defence|officials?|military|pentagon|state department)\b", low):
                if not re.search(r"\bin the (?:us|u\.s\.?|united states)\b|\bunited states of america\b|\bunited states\b", low):
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
        # "US Secretary of War" is a role, not the story location
        role_only = re.search(r"\b(?:US|U\.S\.?|USA)\s+(Secretary|President|Defense|Defence|officials?|military|Pentagon)\b", raw) and not re.search(
            r"\bin the (?:US|U\.S\.?|United States)\b|\bUnited States\b", raw)
        if not re.search(r"\bUSGS\b|\bUSB\b|\bUSC\b|\bUSD\b|\bUSP\b", raw) and not role_only:
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
    # "Hurricane Ian record" is a historical comparison, not the current event
    (r"(?<!record )\bhurricanes?\b(?!\s+[A-Z][a-z]+(?:\s+record)?)", "Hurricane"),
    (r"\btyphoons?\b", "Typhoon"),
    (r"\b(tropical )?cyclones?\b", "Cyclone"),
    (r"\bwildfires?\b|\bforest fires?\b", "Wildfire"),
    (r"\bearthquakes?\b|\bquakes?\b|\bM\s*\d+\.\d+\b", "Earthquake"),
    (r"\btsunamis?\b", "Tsunami"),
    (r"\btornado(?:es|s)?\b", "Tornado"),
    (r"\bflash floods?\b|\bflood(?:ing|s|ed)?\b", "Flood"),
    (r"\bhigh winds?\b|\bhigh wind warning\b", "HighWind"),
    (r"\bvolcan(?:o|ic|oes)\b|\beruption\b", "Volcano"),
    (r"\bblizzard\b|\bsnowstorm\b|\bsnow[\s-]?ice\b|\bice warning\b|\bheavy snow\b|\bsnowfall\b|\bwintry\b", "WinterStorm"),
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

    # Conflict — only when the text is about armed conflict (not a stored category or a nuclear test inquiry)
    conflictish = armed_conflict(item, headline=headline)
    if conflictish:
        _tl = ((title or "") + " " + str(item.get("location") or "")).lower()
        if re.search(r"\bukrain|\bkyiv\b|\bkiev\b|\bkharkiv\b|\bkryvyi\b|\bzaporizh|\bodesa\b|\bodessa\b|\bdnipro\b|\bdonetsk\b|\bkherson\b", _tl) or \
                len(re.findall(r"\bukrain", low)) >= 3:
            add("UkraineWar")
        # Strike type next so it keeps a topic slot when the title actually says so
        if re.search(r"\bdrone(?:\s+and\s+missile)?\s+(?:strike|attack|assault)s?\b|\buav\b", lead, re.I):
            add("DroneStrike")
        elif re.search(r"\banti-ballistic\b|\binterceptors?\b|\barms package\b|\bmissiles? for\b", lead, re.I):
            pass  # defensive munitions / aid, not a strike in this story
        elif re.search(r"\b(?:ballistic\s+)?missiles?\s+(?:strike|attack|hits?|hit)\b|"
                       r"\b(?:strike|attack)\s+[^.]{0,40}missiles?\b", lead, re.I):
            add("MissileStrike")
        elif re.search(r"\bairstrikes?\b|\bair strikes?\b", lead, re.I):
            add("Airstrike")
        if re.search(r"\brussia(?:n)?\b|\bkremlin\b|\bmoscow\b", (title or "").lower()):
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
        if re.search(r"\bdata breach\b|\bbreach(?:ed|es)?\b|\bleak(?:ed|s)?\b", low):
            add("DataBreach")
        elif re.search(r"\bransomware\b", low):
            add("Ransomware")
        else:
            add("Cybersecurity")

    # Policy / finance topics named in the title
    if re.search(r"\bsanctions?\b", title or "", re.I):
        add("Sanctions")

    # Lowercase topic noun phrases ("nuclear bomb test veterans" → #NuclearTestVeterans)
    for lab in _topic_noun_phrases(title, _item_text(item, headline=headline)):
        add(lab)

    return tags


_STOCK_RX = re.compile(r"\b(shares?|stocks?|trading (?:halt\w*|halted)|halts? trading|penny stock|nasdaq|nyse|delist\w*|ipo|earnings|equities|sec filing)\b", re.I)


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
        add("Cyberattack" if re.search(r"\b(attack\w*|breach\w*|ransomware|hack\w*|exploit\w*|leak\w*|vulnerab\w*|cve-\d|malware|ddos)\b", title or "", re.I) else "Cybersecurity")
    elif armed_conflict(item, headline=headline):
        add("War")
    elif re.search(r"\b(earthquakes?|quakes?|volcan\w+|tsunamis?|wildfires?|forest fires?)\b|\bM\s*\d+\.\d+\b", title or "", re.I):
        return []   # the hazard topic tag (#Earthquake, #Wildfire) is the sector tag; never #Weather
    elif _STOCK_RX.search(title or "") or _STOCK_RX.search(blob if cat in ("markets", "business", "economy") else ""):
        add("Stocks")
    elif cat in ("markets", "economy", "business") or re.search(r"\b(federal reserve|inflation|interest rates?|treasury yields?)\b", title or "", re.I):
        add("Markets")
    elif re.search(r"\b(biotech|pharma\w*|therapeutics|biologics|clinical trial|fda approv\w*)\b", title or "", re.I):
        add("Biotech")
    elif cat in ("weather", "natural disaster") or re.search(
            r"\b(hurricanes?|typhoons?|cyclones?|tornado(?:es|s)?|flood(?:ing|s|ed)?|"
            r"storms?|blizzards?|wildfires?|heat ?waves?|severe rain|heavy rain|rains?|"
            r"high winds?|snow[\s-]?ice|ice warning|snowfall|wintry)\b",
            blob, re.I):
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


def _hashtags_base(item, headline=None):
    """1–2 location, 1–2 topic, 1 engagement. Always 3–5 tags (held: location + 2 generic)."""
    loc = location_tags(item, headline=headline)
    if is_held(item):
        return finalize_tags(loc[:2], item, headline, topics=False)
    topics = topic_tags(item, headline=headline)
    eng = engagement_tags(item, headline=headline)
    tags = _dedupe(loc[:2] + topics[:2] + eng[:1], MAX_TAGS)
    extras = loc[2:] + topics[2:]
    for e in extras:
        if len(tags) >= MIN_TAGS:
            break
        if e not in tags:
            tags.append(e)
    return finalize_tags(_dedupe(tags, MAX_TAGS), item, headline)



# --------------------------------------------------------------------------- entity-first layer (Nov 25 2026, Matt pt1873u)
GENERICS = {"#News", "#WorldNews", "#Breaking", "#BreakingNews"}
SECTORS = {"#Biotech", "#Stocks", "#Markets", "#Cybersecurity", "#Cyberattack", "#War", "#Outbreak", "#Weather", "#Economy", "#Energy"}
_EXCHANGES = [
    (r"\bNYSE American\b", "NYSEAmerican"), (r"\bNYSE Arca\b", "NYSEArca"), (r"\bNew York Stock Exchange\b|\bNYSE\b", "NYSE"),
    (r"\bNasdaq\b|\bNASDAQ\b", "Nasdaq"), (r"\bLondon Stock Exchange\b|\bLSE\b", "LSE"), (r"\bTokyo Stock Exchange\b", "TSE"),
    (r"\bCboe\b|\bCBOE\b", "Cboe"), (r"\bTSX\b", "TSX"), (r"\bHang Seng\b", "HangSeng"),
]
_AGENCIES = [
    "CDC", "WHO", "FAA", "FBI", "CIA", "NSA", "CISA", "FEMA", "NOAA", "NWS", "USGS", "NASA", "NATO", "OPEC", "IMF", "SEC", "FDA", "EPA",
    "DHS", "DOJ", "FCC", "FTC", "TSA", "NTSB", "NRC", "DOE", "IDF", "IAEA", "UN", "EU", "Pentagon", "Kremlin", "Hamas", "Hezbollah",
    "Houthis", "SpaceX", "NHC", "UNICEF", "Interpol", "Europol", "Treasury",
]
_AGENCY_RX = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(sorted(map(re.escape, _AGENCIES), key=len, reverse=True)) + r")(?![A-Za-z0-9])")
_TICKERS = {"TherivaBiologics": "TOVX", "Tesla": "TSLA", "Nvidia": "NVDA", "Apple": "AAPL", "Microsoft": "MSFT", "Boeing": "BA", "Intel": "INTC",
            "Pfizer": "PFE", "Moderna": "MRNA", "Rakuten": "4755"}
_TICKER_TEXT = re.compile(r"\b(?:NYSE(?: American)?|Nasdaq|NASDAQ|OTC|TSX)\s*[:\-]\s*([A-Z]{1,5})\b|\(\s*([A-Z]{2,5})\s*\)|\bticker\s+([A-Z]{2,5})\b")
_CO_SUFFIX = r"(?:Inc|Corp|Corporation|Co|Ltd|LLC|PLC|Group|Holdings|Bank|Airlines|Air Lines|Biologics|Therapeutics|Pharma|Pharmaceuticals|Biosciences|Bio|Technologies|Energy|Motors|Systems|Networks|Labs|Capital|Securities|Insurance|Foods|Brands|Entertainment|Communications|Software)"
_NOT_ENTITY = {
    "breaking news", "quick takes", "high wind", "high wind warning", "flood watch", "flood warning", "flash flood", "tornado watch", "tornado warning",
    "heat advisory", "winter storm", "winter weather", "severe thunderstorm", "red flag", "dense fog", "special weather", "the wire", "red alert",
    "orange alert", "green alert", "yellow alert", "state of emergency", "known exploited", "security advisory", "read more", "live updates",
    "united states", "new york", "los angeles", "san francisco", "las vegas", "new orleans", "south africa", "north korea", "south korea",
    "south sudan", "new zealand", "saudi arabia", "sri lanka", "costa rica", "puerto rico", "hong kong", "west bank", "gaza strip", "central florida",
    "south florida", "north florida", "west coast", "east coast", "middle east", "south china sea", "black sea", "red sea", "persian gulf",
}
_STOP_START = {"the", "a", "an", "this", "that", "these", "those", "in", "on", "at", "by", "for", "as", "with", "after", "amid", "over", "new", "why", "how",
               "what", "when", "where", "who", "update", "alert", "report", "reports", "breaking", "watch", "warning", "advisory", "some", "more", "days",
               "overnight", "heavy", "severe", "major", "small", "large", "russian", "ukrainian", "chinese", "israeli", "american", "iranian", "syrian",
               "turkish", "indian", "european", "african", "asian", "british", "french", "german", "japanese", "korean", "libyan", "congolese"}
_MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
           "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "est", "edt", "pst", "pdt", "cst", "cdt", "utc", "gmt"}
_CAP = r"[A-Z][A-Za-z0-9&\-]*"
_PHRASE_RX = re.compile(r"(?<![A-Za-z0-9’'])(" + _CAP + r"(?:\s+" + _CAP + r"){0,3})(?![’'A-Za-z0-9])")


_PEOPLE = [   # distinctive officials: tag the person and, when the role is unambiguous, their agency
    (r"\bScott Bessent\b|\bBessent\b", "ScottBessent", "Treasury"),
    (r"\bJerome Powell\b", "JeromePowell", "FederalReserve"),
    (r"\bJanet Yellen\b", "JanetYellen", "Treasury"),
    (r"\bAntony Blinken\b|\bAnthony Blinken\b", "AntonyBlinken", "StateDepartment"),
    (r"\bMarco Rubio\b", "MarcoRubio", None),
    (r"\bVladimir Putin\b", "VladimirPutin", "Kremlin"),
    (r"\b(?:Volodymyr\s+)?Zelensky(?:y|i)?\b", "Zelensky", None),
    (r"\bPete Hegseth\b|\bHegseth\b", "PeteHegseth", None),
    (r"\bBenjamin Netanyahu\b|\bNetanyahu\b", "Netanyahu", None),
    (r"\bXi Jinping\b", "XiJinping", None),
    (r"\bVitali Klitschko\b", "VitaliKlitschko", None),
    (r"\bJensen Huang\b", "JensenHuang", None),
]
# Full names for Commons title matching; tags stay camel-case for #PeteHegseth etc.
_PEOPLE_FULL = {
    "ScottBessent": "Scott Bessent",
    "JeromePowell": "Jerome Powell",
    "JanetYellen": "Janet Yellen",
    "AntonyBlinken": "Antony Blinken",
    "MarcoRubio": "Marco Rubio",
    "VladimirPutin": "Vladimir Putin",
    "Zelensky": "Volodymyr Zelensky",
    "PeteHegseth": "Pete Hegseth",
    "Netanyahu": "Benjamin Netanyahu",
    "XiJinping": "Xi Jinping",
    "VitaliKlitschko": "Vitali Klitschko",
    "JensenHuang": "Jensen Huang",
}
_ORG_TITLE_WORDS = re.compile(
    r"\b(ministr(?:y|ies)|departments?|governments?|agenc(?:y|ies)|offices?|"
    r"councils?|health|police|arm(?:y|ies)|authorit(?:y|ies)|commissions?|"
    r"bureaus?|administrations?|forces?|commands?|services?|institutes?|"
    r"universit(?:y|ies)|hospitals?|secretariats?|parliaments?|congress|"
    r"senate|cabinets?|tribunals?|courts?|federations?|committees?|"
    r"organi[sz]ations?|corps|navy|navies|marines?|guards?|customs|"
    r"intelligence|security)\b",
    re.I,
)
_ROLE_AGENCY = [
    (r"\b(?:U\.?S\.?\s+)?Treasury Secretary\b|\bSecretary of (?:the )?Treasury\b|\bU\.?S\.? Treasury\b", "Treasury"),
    (r"\bSecretary of State\b|\bState Department\b", "StateDepartment"),
    (r"\b(?:Defense Secretary|Secretary of Defense)\b", "Pentagon"),
    (r"\bAttorney General\b|\bJustice Department\b", "DOJ"),
    (r"\bFederal Reserve\b|\bFed Chair\b", "FederalReserve"),
]
_NAME_VERBS = re.compile(
    r"^(?:Unleashes|Says|Said|Warns|Warned|Imposes|Imposed|Announces|Announced|Orders|Ordered|"
    r"Calls|Called|Blames|Blamed|Accuses|Accused|Declares|Declared|Signs|Signed|Vetoes|Vetoed|"
    r"Fires|Fired|Names|Named|Taps|Tapped|Nominates|Nominated|Rejects|Rejected|Defends|Defended|"
    r"Slams|Slammed|Backs|Backed|Visits|Visited|Meets|Met|Urges|Urged|Tells|Told|Asks|Asked|"
    r"Seeks|Sought|Blocks|Blocked|Halts|Halted|Targets|Targeted|Hits|Struck|Strikes|"
    r"Launches|Launched|Opens|Opened|Starts|Started|Begins|Began|Proposes|Proposed|"
    r"Introduces|Introduced|Inquires|Inquiry)\b",
    re.I,
)


def _clean_title(title):
    s = _norm(title or "")
    s = re.sub(r"^[\s\-—–−‐-]+", "", s)
    s = re.sub(r"\s+(?:By|via)\s+(?:Investing\.com|Reuters|AP|Bloomberg|Yahoo Finance|MarketWatch|Benzinga|GlobeNewswire|PR Newswire|Business Wire)\b.*$", "", s)
    s = re.sub(r"^\s*(?:Breaking News|BREAKING|Quick takes:)\s*[:\-—]?\s*", "", s, flags=re.I)
    return s



_TOPIC_STOP = {
    "the", "a", "an", "this", "that", "these", "those", "in", "on", "at", "by", "for", "as", "with", "after",
    "amid", "over", "into", "from", "about", "to", "of", "and", "or", "its", "their", "his", "her", "than",
    "inquiry", "inquiries", "record", "records", "report", "reports", "panel", "announcement", "announces",
    "announced", "launch", "launches", "launched", "said", "says", "issue", "issues", "case", "cases",
    "plan", "plans", "bill", "question", "questions", "statement", "review",
}
_TOPIC_ALIASES = [
    (re.compile(r"nuclear\s+(?:bomb\s+|weapons?\s+)?tests?\s+veterans?", re.I), "NuclearTestVeterans"),
    (re.compile(r"nuclear\s+(?:bomb\s+|weapons?\s+)?tests?", re.I), "NuclearTests"),
]


_TOPIC_SKIP_WORDS = {
    "has", "have", "had", "not", "yet", "approved", "approve", "says", "said", "say", "including",
    "expects", "expect", "expected", "also", "new", "been", "being", "was", "were", "will", "would",
    "could", "should", "may", "might", "can", "cannot", "no", "yes", "still", "already", "just",
    "missile", "missiles", "strike", "strikes", "ballistic", "attack", "attacks", "aerial",
    "injures", "injured", "killing", "killed", "hits", "hit", "package",
}


def _topic_noun_phrases(title, blob=""):
    """Key lowercase (or mid-title) topic noun phrases → CamelCase labels, most specific first."""
    text = _norm(f"{title or ''} {blob or ''}")
    out = []
    for rx, lab in _TOPIC_ALIASES:
        if rx.search(text) and lab not in out:
            out.append(lab)
    # "inquiry into nuclear bomb test veterans' records" — noun chunk after into/on/for/about/over/amid
    src = _norm(title or "")
    for m in re.finditer(r"\b(?:into|on|about|amid|regarding)\s+(.+)$", src, re.I):
        raw = re.sub(r"[’']s\b", "s", m.group(1))
        raw = re.sub(r"[’']", "", raw)
        words = [w for w in re.findall(r"[A-Za-z]+", raw)
                 if w.lower() not in _TOPIC_STOP and w.lower() not in _TOPIC_SKIP_WORDS]
        if any(w.lower() in _TOPIC_SKIP_WORDS for w in re.findall(r"[A-Za-z]+", raw)[:2]):
            continue
        if 2 <= len(words) <= 5:
            lab = "".join(w[:1].upper() + w[1:].lower() for w in words)
            if 8 <= len(lab) <= 28 and lab not in out and lab.lower() not in {"inquiryinto", "records"}:
                out.append(lab)
    return out[:3]


def _resolve_surname(title, blob):
    """If the title leads with a surname-only ('Burnham launches…'), return the full name from the body."""
    title = _norm(title or "")
    blob = blob or ""
    m = re.match(r"^(" + _CAP + r")\s+(.+)$", title)
    if not m or not _NAME_VERBS.match(m.group(2) or ""):
        return None
    last = m.group(1)
    low = last.lower()
    if (last.isupper() or low in _STOP_START or low in _MONTHS or last in _COMMON_CAPS
            or low in _PLACE_WORDS or _is_place(last) or len(last) < 3):
        return None
    # Already a First Last title? handled elsewhere.
    rx = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+" + re.escape(last) + r"\b")
    hit = rx.search(blob) or rx.search(title)
    if not hit:
        return None
    firsts = hit.group(1).strip()
    firsts = _strip_role_prefix(firsts)
    bits = [b for b in firsts.split() if b.lower() not in _HONORIFICS and b.lower() not in {"prime", "uk", "us", "of", "the", "united", "states"}]
    if not bits:
        return None
    firsts = " ".join(bits[-2:]) if len(bits) > 2 else " ".join(bits)
    full = firsts + " " + last
    if _is_place(full) or full.lower() in _NOT_ENTITY:
        return None
    return full


_ROLE_PREFIX_RX = re.compile(
    r"^(?:(?:US|U\.S\.?|United States|UK|U\.K\.?)\s+)?"
    r"(?:Secretary(?:\s+of(?:\s+(?:War|Defense|Defence|State|the\s+Treasury|Energy|Labor|Transportation|Education|Commerce|the\s+Interior|Homeland\s+Security|Veterans\s+Affairs))?)?|"
    r"Defense\s+Secretary|Defence\s+Secretary|Press\s+Secretary|Attorney\s+General|"
    r"President|Vice\s+President|Prime\s+Minister|Deputy\s+Prime\s+Minister|"
    r"Minister(?:\s+of(?:\s+[A-Z][A-Za-z]+)?)?|Mayor|Governor|Senator|Ambassador|"
    r"General|Admiral|Colonel|Chairman|Chairwoman|Chancellor|Premier)\s+",
    re.I,
)
_ROLE_BEFORE_RX = re.compile(
    r"(?:Secretary\s+of(?:\s+(?:War|Defense|Defence|State|the\s+Treasury))?|Prime\s+Minister|"
    r"President|Minister|Mayor|Governor|Senator|Defense\s+Secretary|Defence\s+Secretary)\s+$",
    re.I,
)


def _strip_role_prefix(ph, preceding=""):
    """Drop titles/roles so 'Secretary of War Pete Hegseth' and 'War Pete Hegseth' become 'Pete Hegseth'."""
    s = _norm(ph or "")
    if preceding and _ROLE_BEFORE_RX.search(preceding):
        # 'Secretary of ' was just before a capitalized phrase that started at 'War'
        s = _ROLE_PREFIX_RX.sub("", _norm(preceding + s)).strip() or s
    for _ in range(3):
        nxt = _ROLE_PREFIX_RX.sub("", s).strip()
        if nxt == s:
            break
        s = nxt
    # leftover 'War Pete Hegseth' when 'War' is the office, not a name
    s = re.sub(r"^(?:War|Defense|Defence|State|Treasury)\s+(?=[A-Z][a-z]+\s+[A-Z])", "", s)
    return s


def entity_tags(item, headline=None):
    """Specific named things in the story: company, ticker, exchange, agency/org, person-like proper-noun phrases, plus 'in/of <Place>' places.
    Returns (tags_in_priority_order). Place names found here are only used when the place dictionaries missed them."""
    title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
    blob = _item_text(item, headline=headline)[:2000]
    out, seen = [], set()
    known_loc = {x.lower() for x in location_tags(item, headline=headline)}

    def add(label, tag=None):
        tg = tag or to_tag(label)
        if tg and len(tg) > 2 and tg.lower() not in seen and tg.lower() not in known_loc:
            seen.add(tg.lower()); out.append(tg)

    # Named people in the title, then their agency/role when it is clear (dictionary or wording in the title).
    for rx, tag, agency in _PEOPLE:
        if re.search(rx, title) or re.search(rx, _item_text(item, headline=headline)):
            add(tag, "#" + tag)
            if agency:
                add(agency, "#" + agency)
            if len(out) >= 4:
                break
    if not any(x.lstrip("#") in {p[1] for p in _PEOPLE} for x in out):
        # "Scott Bessent Unleashes …": First Last at the start of the title, followed by a finite verb
        m = re.match(r"^(" + _CAP + r")\s+(" + _CAP + r")\s+(.+)$", title)
        if m and _NAME_VERBS.match(m.group(3) or ""):
            first, last = m.group(1), m.group(2)
            low_f, low_l = first.lower(), last.lower()
            if (not first.isupper() and not last.isupper()
                    and low_f not in _STOP_START and low_l not in _STOP_START
                    and low_f not in _MONTHS and low_l not in _MONTHS
                    and first not in _COMMON_CAPS and last not in _COMMON_CAPS
                    and low_f not in _PLACE_WORDS and low_l not in _PLACE_WORDS
                    and (first + " " + last).lower() not in _NOT_ENTITY
                    and not _is_place(first + " " + last)):
                add(first + " " + last)
    if not any(x.lstrip("#") in {p[1] for p in _PEOPLE} for x in out) and not any(
            re.fullmatch(r"#[A-Z][a-z]+[A-Z][A-Za-z]+", x) for x in out):
        # Surname-only lead ("Burnham launches…") — resolve to the full name from the brief/body
        full = _resolve_surname(title, _item_text(item, headline=headline))
        if full:
            add(full)
    # Role / agency wording in the title (Treasury Secretary, Secretary of State, …)
    for rx, lab in _ROLE_AGENCY:
        if re.search(rx, title):
            add(lab, "#" + lab)
            break

    # Quoted proper names in the title (e.g. 'PIF Tower')
    for m in re.finditer(r"[\'‘’\"“”]([A-Z][^\'‘’\"“”]{1,40})[\'‘’\"“”]", title):
        ph = m.group(1).strip()
        if ph and ph.lower() not in _NOT_ENTITY and not _is_place(ph):
            add(ph)

    # companies first: capitalized phrase ending in a company suffix, or followed by an exchange mention
    for m in re.finditer(r"(" + _CAP + r"(?:\s+" + _CAP + r"){0,3}\s+" + _CO_SUFFIX + r")\b\.?", title):
        ph = m.group(1)
        if ph.split()[0].lower() in _STOP_START:
            ph = " ".join(ph.split()[1:])
        ws = ph.split()
        while len(ws) > 1 and ws[-1].rstrip(".").lower() in {"inc", "corp", "corporation", "co", "ltd", "llc", "plc", "group", "holdings"}:
            ws = ws[:-1]
        ph = " ".join(ws)
        if ph and ph.lower() not in _NOT_ENTITY and not _is_place(ph):
            add(ph)
    company = out[0] if out else None
    # exchange / market
    for rx, lab in _EXCHANGES:
        if re.search(rx, blob):
            add(lab, "#" + lab)
            break
    # ticker, only when stated in the text or well known for the company
    tk = None
    mt = _TICKER_TEXT.search(blob)
    if mt:
        tk = next((g for g in mt.groups() if g), None)
        if tk and tk.upper() in {"US", "UK", "EU", "UN", "AI", "CEO", "CFO", "FAQ", "II", "IV", "TV"}:
            tk = None
    if not tk and company:
        tk = _TICKERS.get(company.lstrip("#"))
    if tk:
        add(tk, "#" + tk.upper())
    # agencies / organizations (all-caps dictionary)
    for m in _AGENCY_RX.finditer(title):   # title only: a brief that name-drops USGS must not tag a GEOFON story #USGS
        add(m.group(1))
        if len(out) >= 6:
            break
    # proper-noun phrases from the title that are not places we already know, months, or generic event words
    first_pos = 0
    for m in _PHRASE_RX.finditer(title):
        ph = m.group(1).strip()
        words = ph.replace("&", " ").split()
        if m.start() == first_pos and words and words[0].lower() in _STOP_START:
            words = words[1:]
        while words and (words[0].lower() in _STOP_START and len(words) > 1):
            words = words[1:]
        while words and words[0].lower().rstrip(".") in _HONORIFICS and len(words) > 1:
            words = words[1:]
        ph = " ".join(words)
        ph = _strip_role_prefix(ph, title[:m.start()])
        words = ph.split()
        low = ph.lower()
        if not words:
            continue
        if any(w.lower() in _PLACE_WORDS for w in words) or _is_place(ph):
            continue
        if not ph or low in _NOT_ENTITY or low in _MONTHS or ph.isupper() or len(ph) < 4:
            continue
        if any(w.lower() in _MONTHS for w in words) or re.search(r"\d", ph):
            continue
        if len(words) < 2 or any(w.isupper() and len(w) > 1 for w in words):
            continue   # single words and acronym-bearing phrases are handled by the dictionaries
        if m.start() == 0 and low not in _KNOWN_ORGS:
            continue   # a sentence-initial capital phrase is ambiguous ("Satellites Have"); only the known-org list or a company suffix counts there
        tg = to_tag(ph)
        if tg and len(tg) <= 22 and len(words) <= 3 and tg.lower() not in known_loc:
            add(ph)
        if len(out) >= 6:
            break
    # Named systems / hardware in the title or brief (NASAMS, F-16)
    blob_hw = _item_text(item, headline=headline)
    for rx, lab in ((r"\bNASAMS\b", "NASAMS"), (r"\bF-?16s?\b", "F16")):
        if re.search(rx, blob_hw, re.I):
            add(lab, "#" + lab)
    # "in/of/near <Place>" for places our dictionaries do not know (e.g. 'km SE of Severo-Kuril’sk')
    for m in re.finditer(r"\b(?:of|near|in|at)\s+(" + _CAP + r")(?:,|\b)", title):
        ph = m.group(1)
        if len(ph) >= 5 and ph.lower() not in _MONTHS and ph.lower() not in {x.lower() for x in _COMMON_CAPS} and ph.lower() not in _NOT_ENTITY and ph.lower() not in _PLACE_WORDS and not _is_place(ph):
            add(ph)
    return out[:6]


def is_org_title_name(name):
    """True if a putative person name contains an org/title word (Ministry, Health, Police, …)."""
    return bool(name and _ORG_TITLE_WORDS.search(name))


def people_from_entities(title, text=""):
    """People named in the headline, from the same PEOPLE list/extractor that produces #PeteHegseth.

    Does not invent names from capitalized bigrams. Rejects any name containing org/title
    words (Ministry, Department, Government, Agency, Office, Council, Health, Police, Army, …).
    """
    title = _clean_title(title or "")
    out, seen = [], set()

    def add(name):
        name = " ".join((name or "").split())
        if not name or is_org_title_name(name):
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(name)

    for rx, tag, _agency in _PEOPLE:
        if title and re.search(rx, title):
            full = _PEOPLE_FULL.get(tag) or re.sub(r"([a-z])([A-Z])", r"\1 \2", tag)
            add(full)
    if not out:
        m = re.match(r"^(" + _CAP + r")\s+(" + _CAP + r")\s+(.+)$", title)
        if m and _NAME_VERBS.match(m.group(3) or ""):
            first, last = m.group(1), m.group(2)
            low_f, low_l = first.lower(), last.lower()
            if (not first.isupper() and not last.isupper()
                    and low_f not in _STOP_START and low_l not in _STOP_START
                    and low_f not in _MONTHS and low_l not in _MONTHS
                    and first not in _COMMON_CAPS and last not in _COMMON_CAPS
                    and low_f not in _PLACE_WORDS and low_l not in _PLACE_WORDS
                    and (first + " " + last).lower() not in _NOT_ENTITY
                    and not _is_place(first + " " + last)):
                add(first + " " + last)
    if not out:
        full = _resolve_surname(title, text or title)
        if full:
            add(full)
    return out


_HONORIFICS = {"mayor", "president", "prime", "minister", "gen", "general", "sen", "senator", "rep", "dr", "gov", "governor", "king", "queen", "pope", "chief", "sheikh", "judge", "secretary", "ceo", "chairman", "mr", "mrs", "ms"}
_PLACE_WORDS = {"republic", "states", "america", "kingdom", "river", "mountains", "islands", "island", "sea", "ocean", "bay", "county", "city", "lake", "gulf", "strait", "peninsula", "valley", "coast", "desert"}


def _is_place(ph):
    try:
        a, b = _find_places(ph, "")
        return bool(a or b)
    except Exception:
        return False


_KNOWN_ORGS = {"federal reserve", "white house", "supreme court", "red cross", "european union", "world bank", "european central bank", "bank of england",
               "bank of japan", "red crescent", "state department", "national guard", "coast guard", "air force", "space force", "national weather service"}
_COMMON_CAPS = {"Friday", "Monday", "Tuesday", "Wednesday", "Thursday", "Saturday", "Sunday", "Israel", "Russia", "Ukraine", "Iran", "China", "Africa",
                "Europe", "Asia", "Congo", "Kenya", "Nigeria", "Uganda", "India", "Turkey", "Brazil", "Florida", "Texas", "Oregon", "Hollywood", "Kuril",
                "Breaking", "Officials", "President", "Police", "Government", "Minister", "Reuters", "Investing", "Yahoo", "Update", "Report", "Earthquake",
                "Tornado", "Hurricane", "Wildfire", "Flood", "Storm", "Warning", "Watch", "Advisory", "Alert", "Fire", "Forest", "Satellites", "Aliens",
                "Federal", "Society", "Data", "Minutes", "Days", "Overnight", "Central", "South", "North", "East", "West"}


def _cap_one(tags, group, limit=1):
    """Keep at most `limit` tags from `group` (a set), preserving order."""
    out, n = [], 0
    for t in tags:
        if t in group:
            if n >= limit:
                continue
            n += 1
        out.append(t)
    return out


_CAT_FILL = {"politics": "Politics", "markets": "Markets", "uap": "UAP", "hazard": "Hazard", "space": "Space", "cyber": "Cybersecurity", "conflict": "Conflict",
             "weather": "Weather", "disease": "Health", "crime": "Crime", "health": "Health", "science": "Science", "energy": "Energy", "tech": "Tech",
             "natural disaster": "Disaster", "war/conflict": "Conflict", "infrastructure": "Infrastructure", "aviation": "Aviation", "transport": "Transport"}


def _cat_fill(item, headline=None):
    c = (_cat(item, headline=headline) or str(item.get("category") or item.get("k") or "")).lower().strip()
    lab = _CAT_FILL.get(c)
    if lab in ("Conflict", "War") and not armed_conflict(item, headline=headline):
        return ["#Politics"] if c in ("war/conflict", "conflict", "politics") else []
    return ["#" + lab] if lab else []


def _entity_first(item, headline=None):
    """Entity-first rule-based tags. Priority: entity, location, topic, entity, sector, location, topic, entity; generics only as a last resort (max 1)."""
    item = _normalize_item(item)
    ents = entity_tags(item, headline=headline)
    loc = location_tags(item, headline=headline)
    topics = topic_tags(item, headline=headline)
    sec = [t for t in engagement_tags(item, headline=headline)]
    sector = [t for t in sec if t not in GENERICS]
    generic = [t for t in sec if t in GENERICS]
    topics = [t for t in topics if t not in SECTORS]
    # a topic that is itself a cyber/sector word should not double up with the sector tag
    if sector and "#Cybersecurity" in topics and sector[0] in ("#Cyberattack",):
        sector = []
    order = []
    def take(lst, i):
        if i < len(lst):
            order.append(lst[i])
    take(ents, 0); take(loc, 0); take(topics, 0); take(loc, 1); take(sector, 0); take(ents, 1); take(topics, 1); take(ents, 2)
    tags = _dedupe(order, MAX_TAGS)
    if len(tags) < MAX_TAGS:
        for e in ents + loc + topics:
            if len(tags) >= MAX_TAGS:
                break
            if e not in tags:
                tags.append(e)
    unearned = SOFT_GENERICS if not armed_conflict(item, headline=headline) else set()
    if len(tags) < MIN_TAGS:
        for g in generic + [x for x in GENERIC_TAGS if x not in GENERICS or True]:
            if len(tags) >= MIN_TAGS:
                break
            if g in unearned:
                continue
            if g not in tags and (not any(x in GENERICS for x in tags)):
                tags.append(g)   # at most ONE generic filler
    if len(tags) < MIN_TAGS:   # nothing more nameable: category word, then the site brand (never a second generic filler)
        for g in _cat_fill(item, headline) + ["#News", "#BlackoutNetwork", "#Alerts"]:
            if len(tags) >= MIN_TAGS:
                break
            if g in unearned:
                continue
            if g not in tags:
                tags.append(g)
    return finalize_tags(_cap_one(_dedupe(tags, MAX_TAGS), SECTORS, 1), item, headline)



def person_tags(item, headline=None):
    """People only: dictionary names, First Last in the title, and a surname resolved from the brief/body."""
    item = _normalize_item(item)
    title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
    text = _item_text(item, headline=headline)
    out, seen = [], set()
    def add(label, tag=None):
        tg = tag or to_tag(label)
        if tg and len(tg) > 2 and tg.lower() not in seen:
            seen.add(tg.lower()); out.append(tg)
    for rx, tag, _agency in _PEOPLE:
        if re.search(rx, title) or re.search(rx, text):
            add(tag, "#" + tag)
    m = re.match(r"^(" + _CAP + r")\s+(" + _CAP + r")\s+(.+)$", title)
    if m and _NAME_VERBS.match(m.group(3) or ""):
        first, last = m.group(1), m.group(2)
        low_f, low_l = first.lower(), last.lower()
        if (not first.isupper() and not last.isupper()
                and low_f not in _STOP_START and low_l not in _STOP_START
                and low_f not in _MONTHS and low_l not in _MONTHS
                and first not in _COMMON_CAPS and last not in _COMMON_CAPS
                and low_f not in _PLACE_WORDS and low_l not in _PLACE_WORDS
                and (first + " " + last).lower() not in _NOT_ENTITY
                and not _is_place(first + " " + last)):
            add(first + " " + last)
    full = _resolve_surname(title, text)
    if full:
        add(full)
    return out


def _note_text(n, limit=2000):
    """Flatten a stored write-up / desk note into plain text the extractor can read."""
    if not n:
        return ""
    if isinstance(n, str):
        return n.strip()
    if isinstance(n, (list, tuple)):
        return " ".join(x for x in (_note_text(i, limit) for i in n) if x)
    if not isinstance(n, dict):
        return ""
    parts = []
    for k in ("headline", "title", "dek", "lede", "what_happened", "what", "where", "place",
              "summary", "body", "text", "why_it_matters", "analysis"):
        v = n.get(k)
        if v:
            parts.append(v if isinstance(v, str) else _note_text(v, limit))
    st = n.get("story")
    if isinstance(st, dict):
        parts.append(_note_text(st, limit))
    secs = n.get("sections")
    if isinstance(secs, dict):
        parts.extend(v if isinstance(v, str) else _note_text(v, limit) for v in secs.values())
    elif isinstance(secs, list):
        parts.append(_note_text(secs, limit))
    return " ".join(p for p in parts if p)[:limit]


def writeup_text(cid):
    """Stored write-up for a cluster (v3 / desk note / template). Local files and DBs only; never assembles or fetches."""
    if not cid:
        return ""
    try:
        import story_v3 as V3
        return _note_text(V3.note_for(cid))
    except Exception:
        try:
            import story_writer as SW
            return _note_text(SW.note_for(cid))
        except Exception:
            return ""


def with_body(item, alerts=None, extra=""):
    """Attach write-up, source titles and extra prose so surname/place extraction can run on the full story."""
    it = dict(item or {})
    cid = it.get("cluster_id") or it.get("id") or ""
    parts = [it.get("body") or "", extra or "", writeup_text(cid)]
    for a in alerts or []:
        if isinstance(a, dict):
            parts.append(str(a.get("title") or a.get("s") or a.get("source") or ""))
        elif isinstance(a, str):
            parts.append(a)
    for L in it.get("links") or it.get("l") or it.get("sources") or []:
        if isinstance(L, dict):
            parts.append(str(L.get("title") or L.get("s") or L.get("source") or L.get("name") or ""))
        elif isinstance(L, str):
            parts.append(L)
    body = " ".join(str(p) for p in parts if p)
    if body:
        it["body"] = body
    return it


# --------------------------------------------------------------------------- final tag rule (Nov 25 2026, 1:03 PM ET — Matt: short popular tags for engagement)
# Hashtags are for social search. Prefer short, popular one-word tags people actually type
# (#War, #Nuclear, #Ebola, #Iran, #Earthquake, #Wildfire, #Hurricane, #Gaza, #Ukraine, #Tesla, #NVIDIA)
# plus common short entity names. Never long run-together strings. Popular topic words are good.
# Still banned: #News, #WorldNews, #Breaking, #BlackoutNetwork, #Alerts, #Update and similar fluff.
# 3-5 tags, each at most ~12 characters or one well-known name, topic word first, then place/person/company.
FILLER = {t.lower() for t in (
    "News", "WorldNews", "Breaking", "BreakingNews", "BlackoutNetwork", "Alerts", "Alert", "Wire", "Live",
    "Update", "Updates", "Latest", "Headlines", "Trending", "World", "Global", "Today", "Now", "Urgent",
    "Watch", "Warning", "Advisory", "Report", "Reports", "Source", "Sources",
    "Disaster", "Hazard", "Infrastructure", "Aviation", "Transport", "Safety", "Government",
    "Incident", "Event", "Story", "Signal", "Signals", "Intel", "Monitor", "Monitoring",
    "Threat", "Threats", "Risk", "Crisis", "Social", "Media", "Video", "Photo",
    "Orange", "Red", "Yellow", "Green", "Level", "Research", "Releases", "Full", "Guests", "Footage",
    "Forces", "Affairs", "Category", "Guide", "Minutes",
    "EST", "EDT", "CST", "CDT", "MST", "MDT", "PST", "PDT", "AKST", "AKDT", "HST", "ET", "PT", "PM", "AM", "UTC", "GMT", "IP", "MMI", "AV", "ID",
    "WHAT", "WHY", "WHERE", "WHEN", "HOW", "Some", "Several", "Many", "Another", "Other")}
# Popular topic/search words people actually type (slightly over 12 chars is ok for these).
POPULAR = {t.lower() for t in (
    "War", "Nuclear", "Ebola", "Iran", "Earthquake", "Wildfire", "Hurricane", "Gaza", "Ukraine", "Tesla", "Nvidia", "NVIDIA",
    "Storm", "Cybersecurity", "Outbreak", "Flood", "Tornado", "Cyclone", "Typhoon", "Volcano", "Drought",
    "Measles", "Cholera", "Polio", "Influenza", "Missile", "Sanctions", "Ransomware", "Cyberattack", "Cyber",
    "Conflict", "Weather", "Health", "Politics", "Stocks", "Markets", "Economy", "Energy", "Crime", "Space",
    "Fire", "Quake", "Rain", "Snow", "Blizzard", "Tsunami", "Eruption", "Landslide", "Heatwave", "Freeze",
    "Airstrike", "Drone", "Israel", "Hamas", "Hezbollah", "Houthis", "Russia", "China", "Taiwan", "Korea",
    "CVE", "Breach", "Covid", "Mpox", "Vaccine", "NATO", "UN", "WHO", "FEMA", "NWS", "USGS", "NASA", "NOAA",
    "Military", "Defense", "Climate", "Finance", "Business", "Science", "Tech", "Technology", "Environment",
    "Security", "Ice", "Hail", "Flooding")}
_ID_RX = re.compile(r"\b([A-Z]{2,5}\d{0,2}-\d{2,4}(?:-\d{2,5})?)\b")
_FILL_STOP = {w for w in (
    "the a an this that these those in on at by for as with after amid over into from about to of and or its their his her than is are was were "
    "has have had be been will would could should may might can says said say new more most less very just also not but if then so such "
    "now today tonight monday tuesday wednesday thursday friday saturday sunday january february march april may june july august september "
    "declares announces issues warns launches opens releases adds leaves suspects signals unleashes convicted indicted october november december officials official authorities reports report media sources source first last next latest top big major minor "
    "news live update updates breaking watch warning alert advisory guide minutes meeting meetings board urgent action needed bizarre "
    "mockup special general national international local regional state states city county toward predicted potential possible official various".split())}
_TINY_STOP = set("the and for with from that this into over after amid about than are was were its their his her has have not but".split())
_FILL_BADWORDS = {"stop", "it", "special", "october", "november", "december", "january", "february", "march", "april", "june", "july", "august", "september"}
_JUNK_WORDS = {"multiple", 
    "category", "media", "reports", "report", "victims", "guide", "women", "men", "youth", "safeguard", "internet",
    "army", "concerns", "toward", "predicted", "effectiveness", "central", "minutes", "liability", "director",
    "update", "updates", "latest", "breaking", "says", "amid", "watch", "warning", "potential", "possible",
    "official", "national", "international", "federal", "various", "several", "another", "major", "minor",
    "severe", "heavy", "coastal", "tropical", "ongoing", "according", "including", "related", "current",
    "recent", "additional", "important", "significant", "high", "low", "mid", "small", "large", "big",
}
# Isolated gentilics are adjectives, not search tags (#Canadian → use #Canada from the place extractor).
_GENTILIC = {
    "canadian", "british", "american", "russian", "chinese", "french", "german", "italian", "japanese", "korean",
    "mexican", "australian", "indian", "irish", "scottish", "spanish", "turkish", "ukrainian", "israeli", "iranian",
    "saudi", "egyptian", "nigerian", "brazilian", "argentine", "polish", "swedish", "norwegian", "danish", "dutch",
    "swiss", "austrian", "portuguese", "greek", "thai", "vietnamese", "indonesian", "filipino", "pakistani",
    "afghan", "iraqi", "syrian", "lebanese", "jordanian", "yemeni", "sudanese", "kenyan", "ethiopian", "somali",
}


def _camel_words(tag):
    s = (tag or "").lstrip("#")
    # Compact ids and strain names stay one token (#D33B, #H5N1, #AV261193, #TOVX).
    if re.fullmatch(r"H\d+N\d+", s, re.I) or re.fullmatch(r"[A-Za-z]{1,6}\d+[A-Za-z]{0,5}\d*", s) or (re.fullmatch(r"[A-Za-z]{2,6}", s) and s.isupper()):
        return [s]
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z][a-z]+|[a-z]+|[0-9]+", s) or ([s] if s else [])
    # Glue a trailing compact id: Iceberg + D + 33 + B -> Iceberg, D33B
    if len(words) >= 2:
        for i in range(1, len(words)):
            rest = "".join(words[i:])
            if re.fullmatch(r"[A-Za-z]{0,4}\d+[A-Za-z]{0,4}", rest) and 2 <= len(rest) <= 10:
                return words[:i] + [rest]
    return words


_ACRO_OK = {"NVIDIA", "NASDAQ", "COVID", "UNICEF", "INTERPOL", "NOAA", "FEMA", "NATO", "NASA", "OPEC", "USGS", "GDACS", "SPACEX", "OPENAI"}

def _shorten_tag(tag):
    """Drop long run-togethers; reduce #NuclearThreat to #Nuclear. Keep short tags and well-known names."""
    if not tag:
        return None
    t = "#" + str(tag).lstrip("#")
    s = t.lstrip("#")
    if not s:
        return None
    # Nov 25 2026 (Matt 9:09 PM): obscure all-caps acronyms (#HKCERT) are not tags people follow; #edge -> #Edge
    if s.isalnum() and s.isupper() and len(s) >= 5 and s.lower() not in POPULAR and s not in _ACRO_OK:
        return None
    if s[0].islower():
        s = s[0].upper() + s[1:]; t = "#" + s
    words = _camel_words(s)
    for w in words:
        if w.lower() in POPULAR:
            return to_tag(w) or ("#" + w[0].upper() + w[1:] if w else None)
    if s.lower() in _GENTILIC or s.lower() in _JUNK_WORDS:
        return None
    if len(words) >= 3:
        return None      # #ChiquitaCanyonLandfill, #WarInTheMiddleEast
    if len(s) <= 12 and len(words) <= 2:
        return t
    if len(words) == 1 and len(s) <= 16:
        return t
    if len(words) == 2 and s[0].isupper():
        if len(s) <= 16:
            return t     # #JensenHuang, #TherivaBiologics (well-known names slightly over 12)
        first = to_tag(words[0])
        if first and first.lstrip("#").lower() not in _JUNK_WORDS | _GENTILIC | {"democratic", "republic", "united", "federal", "national", "state", "department", "ministry"}:
            return first
        return None
    return None


def _is_filler(tag):
    t = (tag or "").lstrip("#").lower()
    if not t or t in FILLER:
        return True
    words = [w.lower() for w in _camel_words(tag)]
    if len(words) == 2 and words[0] == words[1]:
        return True      # #OctoberOctober
    if len(t) < 2 or t.isdigit():
        return True
    if t in _GENTILIC or t in _JUNK_WORDS or t in _FILL_BADWORDS:
        return True
    if any(w in _FILL_BADWORDS for w in words):
        return True
    if re.match(r"^(?i:some|several|many|another|other|the|this|these)[A-Z]", (tag or "").lstrip("#")):
        return True      # #SomeCentralFlorida, #TheWhite...
    if any(w in _JUNK_WORDS or w in _FILL_STOP for w in words):
        # allow a popular topic next to a junk modifier (#SevereRain already shortened; leftover #TowardX)
        if not any(w in POPULAR for w in words):
            return True
    if re.match(r"^(?:AM|PM)?[ECMPHA][KS]?[SD]?T$", (tag or "").lstrip("#")):
        return True      # time zones: #EST #AMET #AKST
    if _shorten_tag(tag) is None:
        return True
    return False


def _source_orgs(item):
    out = []
    for L in item.get("links") or item.get("l") or []:
        nm = (L.get("s") or L.get("source") or L.get("name") or "") if isinstance(L, dict) else str(L)
        nm = re.sub(r"^(?:Google News|Bing News)\s*:\s*", "", nm).strip()
        if not nm or re.search(r"@|youtube|telegram|bluesky|reddit|twitter|facebook|rss|http|\.", nm, re.I):
            continue
        m = re.match(r"^([A-Z]{3,8})(?:\b|\s)", nm)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _proper_noun_fill(item, headline=None):
    """Capitalised names from the headline, then the body: acronyms, 1-3 word proper-noun runs. Order of appearance."""
    title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
    body = _strip_related(_as_text(item.get("brief"), item.get("d"), item.get("body")))[:900]
    out, seen = [], set()

    def add(label):
        label = (label or "").strip(" -&")
        tg = to_tag(label)
        if not tg or _is_filler(tg):
            return
        words = [w for w in re.split(r"\s+", label) if w]
        low = [w.lower().strip(".,:;!?") for w in words]
        if low and (low[0] in _FILL_STOP and len(words) == 1):
            return
        if len(words) == 1 and (low[0] in _FILL_STOP or low[0] in _FILL_BADWORDS or label in _COMMON_CAPS or re.search(r"(?:ed|ing|ly)$", low[0])):
            return
        if all(w in _FILL_STOP or w in _FILL_BADWORDS for w in low):
            return
        k = tg.lower()
        if k in seen or any((k in x or x in k) and min(len(k), len(x)) >= 4 for x in seen):
            return
        seen.add(k); out.append(tg)

    for src, first_is_sentence_start in ((title, True), (body, True)):
        for m in re.finditer(r"\b[A-Z]{2,6}\b", src):          # acronyms: WHO, USGS, NASDAQ, DRC
            a = m.group(0)
            if a in ("LIVE", "WATCH", "NEWS", "BREAKING", "UPDATE", "ALERT", "URGENT", "VIDEO", "THE", "AND", "FOR", "NOT", "NEW", "US", "OK"):
                continue
            add(a)
        for m in _PHRASE_RX.finditer(src):
            ph = m.group(1)
            words = ph.split()
            while words and words[0].lower() in _FILL_STOP:    # sentence-start words ("The", "After")
                words = words[1:]
            while words and words[-1].lower() in _FILL_STOP:
                words = words[:-1]
            if not words:
                continue
            if len(words) == 1 and (words[0].isupper() or len(words[0]) < 4):
                continue
            add(" ".join(words[:3]))
    return out


def _word_fill(item, headline=None):
    """Last resort: distinctive long words from the headline as CamelCase topic tags (#Assassination, #BankFailure)."""
    title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{5,}", title) if w.lower() not in _FILL_STOP and w.lower() not in FILLER]
    out = []
    for w in words:
        tg = to_tag(w)
        if tg and not _is_filler(tg) and tg not in out:
            out.append(tg)
    return out


def _bigram_fill(item, headline=None):
    """Very last resort: advisory/report ids, then adjacent content-word pairs from the headline (#DiscountRate)."""
    title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
    out = []
    for m in _ID_RX.finditer(title):
        tg = to_tag(m.group(1).replace("-", ""))
        if tg and tg not in out and not _is_filler(tg):
            out.append(tg)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z']{3,}", title) if w.lower().strip("'s") not in _FILL_STOP]
    for a, b in zip(words, words[1:]):
        tg = to_tag(a + " " + b)
        if tg and not _is_filler(tg) and tg not in out:
            out.append(tg)
    for w in words:
        tg = to_tag(w)
        if tg and not _is_filler(tg) and tg not in out:
            out.append(tg)
    return out


def entity_fill(item, headline=None, topics=True):
    """Entity and popular-topic candidates for padding a short tag list."""
    item = _normalize_item(item)
    out = []
    for fn in (person_tags, entity_tags, location_tags):
        try:
            out += fn(item, headline=headline)
        except Exception:
            pass
    out += _source_orgs(item) and ["#" + o for o in _source_orgs(item)][:2] or []
    try:
        out += ["#" + t.lstrip("#") for t in _proper_noun_fill(item, headline=headline)]
    except Exception:
        pass
    txt0 = _item_text(item, headline=headline)
    if re.search(r"discount rate|federal reserve|\bFOMC\b|the Fed\b", txt0, re.I):
        out.append("#Fed")
        out.append("#Markets")
    if not topics:                      # held rows may be false positives: names and places only, never the topic
        try:
            ban = {t.lower() for t in topic_tags(item, headline=headline)} | {"#ebola", "#outbreak", "#measles", "#cholera", "#h5n1", "#birdflu", "#war", "#conflict"}
        except Exception:
            ban = {"#ebola", "#outbreak", "#war"}
        return [t for t in out if t.lower() not in ban]
    try:
        out += topic_tags(item, headline=headline)
    except Exception:
        pass
    for m in re.finditer(r"\b((?:severe|heavy|extreme|flash|record|winter|coastal|freezing|tropical|major|strong)\s+)?"
                         r"(rain(?:fall)?|flood(?:ing)?|snow(?:fall)?|ice storm|wind|heat ?wave|tornado|hurricane|cyclone|typhoon|wildfire|drought|blizzard|hail|dust storm|storm surge)\b",
                         _item_text(item, headline=headline), re.I):
        tg = to_tag(m.group(0))
        if tg:
            out.append(tg)
    out += ["#" + t.lstrip("#") for t in _word_fill(item, headline=headline)]
    out += ["#" + t.lstrip("#") for t in _bigram_fill(item, headline=headline)]
    txt = _item_text(item, headline=headline)
    if re.search(r"vulnerab|security advisory|\bCVE-\d", txt, re.I):
        out.append("#Cybersecurity")
    if re.search(r"\bpatch(?:es|ed)?\b|\bzero[- ]day\b", txt, re.I):
        out.append("#Cyber")
    if re.search(r"antibiotic|outbreak|malaria|measles|ebola|influenza|vaccine|virus|disease", txt, re.I):
        out.append("#Health")
    if re.search(r"discount rate|federal reserve|\bFOMC\b|the Fed\b", txt, re.I):
        out.append("#Fed")
        out.append("#Markets")
    return out


def _order_tags(tags, item=None, headline=None):
    """Topic word first, then the main place, then person or company."""
    places, people = set(), set()
    try:
        places = {t.lower() for t in location_tags(item or {}, headline=headline)}
    except Exception:
        pass
    try:
        people = {t.lower() for t in person_tags(item or {}, headline=headline)}
    except Exception:
        pass

    def key(t):
        k = (t or "").lstrip("#").lower()
        if k in POPULAR:
            return (0, tags.index(t) if t in tags else 0)
        if t.lower() in places:
            return (1, tags.index(t) if t in tags else 0)
        if t.lower() in people:
            return (2, tags.index(t) if t in tags else 0)
        return (3, tags.index(t) if t in tags else 0)

    return sorted(tags, key=key)



_TOPIC_HINTS = {
    "earthquake": ("earthquake", "quake", "seismic", "magnitude"),
    "wildfire": ("wildfire", "forest fire", "bushfire", "wild fire", "fire"),
    "weather": ("weather", "rain", "snow", "storm", "wind", "flood", "tornado", "hurricane", "blizzard", "ice", "hail"),
    "war": ("war", "missile", "airstrike", "air strike", "combat", "invasion", "battlefield", "shelling", "offensive", "drone strike"),
    "flood": ("flood", "flooding"),
    "storm": ("storm", "blizzard", "cyclone", "hurricane", "typhoon", "geomagnetic"),
    "stocks": ("stock", "shares", "trading", "nyse", "nasdaq", "market"),
    "markets": ("market", "trading", "nyse", "nasdaq", "shares", "stock"),
    "health": ("health", "hospital", "disease", "outbreak", "virus", "vaccine", "malaria", "measles", "ebola", "influenza", "antibiotic", "antibiotics"),
    "cybersecurity": ("cybersecurity", "cyber", "vulnerab", "cve", "ransomware", "breach", "advisory", "exploited"),
    "cyberattack": ("cyberattack", "cyber attack", "cyber", "exploited", "ransomware", "breach"),
    "cyber": ("cyber", "vulnerab", "cve", "ransomware", "breach"),
}

def _topic_earned(tag, item, headline=None, allowed=None):
    k = (tag or "").lstrip("#").lower()
    if k not in POPULAR:
        return True
    if allowed and tag.lower() in {t.lower() for t in allowed}:
        return True
    text = _item_text(item, headline).lower()
    if k == "war":
        text = re.sub(r"secretary of war|department of war|minister of war", " ", text)
    if k == "hurricane" and re.search(r"hurricane \w+ record", text) and not re.search(r"hurricane (watch|warning|landfall|makes landfall)", text):
        return False
    for h in _TOPIC_HINTS.get(k, (k,)):
        if re.search(r"(?<![a-z])" + re.escape(h) + r"(?:i|is|s|ian|ians)?(?![a-z])", text):   # #Israel from "Israeli"
            return True
    return False


def finalize_tags(tags, item=None, headline=None, topics=True):
    """The one rule for every row: 3-5 short popular tags, topic first, no fluff, no long run-togethers."""
    item = _normalize_item(item or {})
    unearned = set()
    if not armed_conflict(item, headline=headline):
        unearned = {g for g in SOFT_GENERICS if not _topic_earned(g, item, headline)}
    try:   # Nov 25 2026 9:27 PM: a raid ("forces storm a building") never earns weather tags
        import storm_verb
        if storm_verb.is_raid(" ".join(str(x or "") for x in (headline, item.get("title"), item.get("headline")))):
            unearned |= {"#Storm", "#Storms", "#Weather", "#Hurricane", "#Disaster"}
    except Exception:
        pass
    allowed = []
    try:
        allowed = topic_tags(item, headline=headline) if topics else []
    except Exception:
        allowed = []
    keep = []
    for t in tags or []:
        if not t:
            continue
        t = _shorten_tag("#" + str(t).lstrip("#"))
        if not t or _is_filler(t) or t in unearned or any(t.lower() == k.lower() for k in keep):
            continue
        if re.search(r"\b" + re.escape(t[1:]) + r"\s+(?:al|el|ad|an|as|ash|at|az|ar)-", _item_text(item, headline), re.I):
            continue      # fragment of a longer name: #Khallet from "Khallet al-Iman"
        if t == "#Outbreak" and not re.search(r"outbreak|epidemic|pandemic|infect|cases|deaths|virus|disease|fever|flu\b|measles|cholera|ebola", _item_text(item, headline=headline), re.I):
            continue
        if not _topic_earned(t, item, headline, allowed):
            continue
        keep.append(t)
    keep = _cap_one(keep, SECTORS, 1)
    if len(keep) < MIN_TAGS:
        for t in entity_fill(item, headline=headline, topics=topics):
            if len(keep) >= MAX_TAGS:
                break
            t = _shorten_tag(t)
            if not t or _is_filler(t) or t in unearned:
                continue
            if not _topic_earned(t, item, headline, allowed):
                continue
            tl = t.lower()
            if any(tl == k.lower() or (len(tl) >= 5 and (tl in k.lower() or k.lower() in tl) and min(len(tl), len(k)) >= 5) for k in keep):
                continue
            keep.append(t)
            if len(keep) >= MIN_TAGS:
                break
    if len(keep) < MIN_TAGS:          # nothing distinctive left: allow overlapping pieces (#Iceberg next to #IcebergD33B)
        title = _clean_title(headline or item.get("headline") or item.get("title") or item.get("h") or "")
        hold_ban = set()
        if not topics:
            try:
                hold_ban = {t.lower() for t in topic_tags(item, headline=headline)} | {"#ebola", "#outbreak", "#measles", "#cholera", "#h5n1", "#birdflu", "#war", "#conflict"}
            except Exception:
                hold_ban = {"#ebola", "#outbreak", "#war"}
        for w in [title] + re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{2,}", title):
            tg = _shorten_tag(to_tag(w))
            if tg and not _is_filler(tg) and w.lower() not in _TINY_STOP and tg.lower() not in hold_ban and all(tg.lower() != k.lower() for k in keep):
                keep.append(tg)
            if len(keep) >= MIN_TAGS:
                break
    # Prefer a popular topic in the set (search/engagement) when one is earned; pad short lists from the item's category.
    _CAT_TOPIC = {"markets": "#Markets", "financial": "#Finance", "cyber": "#Cybersecurity",
                  "weather": "#Weather", "disease": "#Health", "war/conflict": "#War",
                  "space": "#Space", "political": "#Politics", "business": "#Business"}
    if topics:
        if not any((t or "").lstrip("#").lower() in POPULAR for t in keep):
            for t in entity_fill(item, headline=headline, topics=True):
                st = _shorten_tag(t)
                if st and st.lstrip("#").lower() in POPULAR and not _is_filler(st) and st not in unearned and _topic_earned(st, item, headline, allowed) and all(st.lower() != k.lower() for k in keep):
                    keep.insert(0, st)
                    break
        if len(keep) < MIN_TAGS:
            try:
                cat = _cat(item, headline=headline)
            except Exception:
                cat = ""
            g = _CAT_TOPIC.get(cat)
            if g and g not in unearned and all(g.lower() != k.lower() for k in keep) and _topic_earned(g, item, headline, allowed + [g]):
                keep.append(g)
    try:
        main_places = [t for t in (location_tags(item, headline=headline) or []) if t and not _is_filler(t)]
    except Exception:
        main_places = []
    for p_ in main_places[:2]:
        p_ = _shorten_tag(p_) or p_
        if p_ and all(p_.lower() != k.lower() for k in keep):
            if len(keep) < MAX_TAGS:
                keep.append(p_)
            else:
                # drop the lowest-priority non-topic to make room for the main place
                for i in range(len(keep) - 1, -1, -1):
                    if keep[i].lstrip("#").lower() not in POPULAR:
                        keep[i] = p_
                        break
            break
    keep = _order_tags(keep[:MAX_TAGS], item, headline)
    return keep[:MAX_TAGS]


def hashtags(item, headline=None):
    """xAI-generated tags (validated, cached) are primary; the rule-based extractor is the fallback.
    Held / false-positive items keep location + generic only."""
    item = _normalize_item(item)
    if is_held(item):
        return finalize_tags(location_tags(item, headline=headline)[:2], item, headline, topics=False)
    rule = _entity_first(item, headline=headline)
    chosen = rule
    try:
        import x_tags_llm
        cid = str(item.get("cluster_id") or item.get("id") or "")
        title = headline or item.get("headline") or item.get("title") or ""
        got = x_tags_llm.lookup(cid, item.get("title") or title, item.get("brief") or "", item.get("location") or "", rule, rank=_rank(item))
        if got and len(specific_tags(got, item, headline)) >= 2:
            chosen = got
    except Exception:
        pass
    # Person and place tags from the full extractor always appear, even when the xAI set is used.
    people = person_tags(item, headline=headline)
    places = location_tags(item, headline=headline)
    return finalize_tags(_dedupe(people + places[:2] + [t for t in chosen if t not in people], MAX_TAGS + 3), item, headline)


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
    h = re.sub(r"(?:^|\s)#\w+", " ", h)   # scanner titles can carry their own hashtags; the generator owns the tags
    h = re.sub(r"\s{2,}", " ", h).strip()
    # drop leading emoji / decorative symbols so the composer starts on words
    h = re.sub(r"^[\W_\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\-—–]+", "", h, flags=re.U).strip()
    return h


def story_url(item):
    """Permalink used in the Post on X button. ?s=x is a new URL for X's card cache, so a fresh share is recrawled (the image itself is also busted with og.image_url ?v=)."""
    cid = item.get("cluster_id") or item.get("id") or ""
    if not cid:
        return SITE + "/wire"
    return f"{SITE}/wire/{cid}?s=x"


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


def share_text(item, url=None, headline=None, tags=None):
    """Headline + hashtags, trimmed so headline + tags + t.co link fit in 280.

    Drops the lowest-priority tag first when over budget, but never below MIN_TAGS;
    the headline is shortened instead.
    """
    url = url if url is not None else story_url(item)
    h = _headline(item, headline)
    # Always apply the public tag rule, including when a caller passes stored tags.
    tags = finalize_tags(list(tags) if tags else hashtags(item, headline=headline), item, headline)
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


def intent_url(item, url=None, headline=None, tags=None):
    page = url if url is not None else story_url(item)
    text = share_text(item, url=page, headline=headline, tags=tags)
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
