"""Wire pre-publish validator (Nov 25 2026, Matt 9:28 PM ET, pt1925u): one check every live item passes before it shows on
the Wire or gets a share card.

check(row) -> verdict dict:
  k      corrected display category (deterministic recategorize when the stored tag has no support in the headline/text)
  tags   3-5 validated tags (short popular words, places, known people/orgs, properly cased; no verbs, fragments,
         obscure acronyms, filler or long run-togethers), topped up from the category and the place
  loc/lat/lon  location after the sanity check (agency codes and default coordinates are dropped, so the story comes off maps)
  h      headline with a dangling trailing word removed
  photo  "ok" | "bad:<why>" | "none"  (bad = wrong for the category: satellite/relief imagery, a weather photo on non-weather,
         a hazard photo on another hazard, a country/culture photo on a hazard or conflict story)
  ok     True when the item may be public now; reasons lists what holds it

Pure functions except photo_state() (reads story_photo's stored choice; no network). Display-only: nothing is written to
blackout.db. Never touches scanner.py, push.py, jets.py, config.json, aviation_watch.py, the QA gates or the brief gate.
BN_WIRE_VALIDATE=0 turns the whole check off (items then follow the previous gate only).
"""
import os, re

def on(): return os.environ.get("BN_WIRE_VALIDATE", "1") != "0"

# ------------------------------------------------------------------ category / text consistency
_W = lambda s: re.compile(s, re.I)
EV = {
    "conflict": _W(r"\b(wars?|warfare|missiles?|rockets?|drones?|air ?strikes?|strikes? (?:on|in|at|hit)|shell(?:ing|ed)|artillery|troops?|soldiers?|army|armies|military|navy|naval|warships?|militants?|insurgents?|rebels?|jihadists?|isis|isil|al[- ]?shabaab|hamas|hezbollah|houthis?|\bidf\b|occupation forces|security forces|ceasefire|truce|invasion|invade\w*|offensive|front ?line|bomb\w*|blast|explosions?|attack\w*|hostages?|gunmen|ambush\w*|raid\w*|nato|nuclear|ballistic|intercept\w*|air defen[cs]e|occupied|annex\w*|genocide|refugees?|displaced|shot down|casualt\w*|killed|kills|deadly|clashes|combat|battle\w*|weapons?|arms|tanker attacked|naval incident|mass[_ ]casualty|sirens?|shelter in place|evacuat\w*|displace\w*|gaza|west bank|donbas|frontline|isil|al-qaeda)\b"),
    "quake": _W(r"\b(earthquakes?|quakes?|tsunamis?|seismic|aftershocks?|tremors?|volcan\w*|eruptions?|erupt\w*|ash (?:cloud|plume|advisory)|magnitude)\b|\bM\s?\d(?:\.\d+)?\b"),
    "weather": _W(r"\b(cyclones?|hurricanes?|typhoons?|tropical (?:storm|depression)|floods?|flooding|flash flood|rain\w*|tornado\w*|wild ?fires?|forest ?fires?|bush ?fires?|brush ?fires?|fire weather|red flag|drought|heat ?wave|excessive heat|heat (?:advisory|warning)|snow\w*|blizzard|ice storm|winter (?:storm|weather)|freez\w+|frost|winds?|gale|monsoon|landslides?|mudslides?|avalanche|dust storm|fog|weather|cold wave|thunderstorms?|(?:storm|flood|wind|gale|surf|frost|freeze|heat|fire|tsunami) (?:warning|watch|advisory)|storms?|nor'?easter|surf|tides?|swells?|storm surge|nws|noaa)\b"),
    "disease": _W(r"\b(outbreaks?|cholera|ebola|marburg|mpox|monkeypox|measles|dengue|malaria|influenza|flu|avian|h5n\d|bird flu|covid\w*|virus\w*|polio|yellow fever|epidemic|pandemic|meningitis|anthrax|plague|diphtheria|nipah|mers|lassa|hepatitis|norovirus|infections?|vaccin\w*|cases|disease|pathogen|screwworm|tuberculosis|health (?:alert|emergency))\b"),
    "cyber": _W(r"\b(cyber\w*|ransomware|malware|vulnerabilit\w*|cve-?\d*|security (?:advisory|update|flaw|breach)|advisory \(av\d|zero[- ]day|hack\w*|data breach|breach\w*|phishing|botnet|ddos|exploit\w*|spyware|leak\w*|outage|outages|internet|software|patch\w*|encrypt\w*|credentials|passwords?|intrusion|threat actors?|apt\d*|infosec|ioda)\b"),
    "politics": _W(r"\b(president|presidential|prime minister|minister\w*|ministry|parliament\w*|congress\w*|senat\w*|lawmakers?|legislat\w*|election\w*|vote\w*|voters?|ballot|campaign|governor|mayor|government|cabinet|party|parties|opposition|coup|diplomat\w*|summit|treaty|policy|bill|law|court|judge|ruling|white house|kremlin|trump|biden|vance|putin|zelensk\w*|netanyahu|kushner|rubio|hegseth|labor|labour|tory|republican\w*|democrat\w*|officials?|state of emergency|sanctions?|tariffs?|bundestag|referendum|protest\w*|ouster|ousted|purge\w*|politburo|communist party|xi jinping|xi)\b"),
    "markets": _W(r"\b(stocks?|shares|markets?|crude|brent|oil prices?|gas prices?|inflation|interest rates?|fed\b|federal reserve|treasury|bonds?|yields?|nasdaq|dow|s&p|gdp|recession|bank\w*|financ\w*|earnings|investors?|currency|dollar|euro|yen|bitcoin|crypto\w*|tariffs?|economy|economic|fincen|lending|loans?|mortgage|price\w*)\b"),
    "crime": _W(r"\b(homicides?|murder\w*|manslaughter|shooting|shot|stabb\w*|robbery|burglar\w*|carjack\w*|kidnapp\w*|arrest\w*|charged|charges|police|suspects?|sheriff|indicted|convicted|sentenced|prison|jail\w*|gangs?|assault\w*|fraud|trafficking|smuggl\w*|crime\w*|criminal\w*|curfew)\b"),
    "unrest": _W(r"\b(unrest|riot\w*|protest\w*|demonstrat\w*|looting|curfew|martial law|clashes|tear gas|anti-government|march\w*|rally|rallies|vigil|gathering|strike action|walkout)\b"),
    "wreck": _W(r"\b(crash\w*|collision|collided|derail\w*|shipwreck|capsiz\w*|sank|sinking|sunk|pile-?up|overturn\w*|plane|aircraft|flight|ferry|bus|train|truck|tanker|highway|road|vehicle|accident\w*|emergency landing|ground stop|runway|explosion|fire)\b"),
    "infra": _W(r"\b(power|outages?|blackouts?|grid|substation|water main|boil[- ]water|pipeline|bridge|dam|internet|fiber|gas leak|sewage|runway|ports?|rail|transformer|nuclear (?:plant|power)|reactor|electric\w*|utility|utilities|telecom|cable|ioda)\b"),
    "space": _W(r"\b(solar|geomagnetic|cme|coronal|sunspot|aurora|space weather|kp ?\d|radio blackout|swpc|flare)\b"),
    "deaths": _W(r"\b(dies|died|death|dead|obituar\w*|passed away|funeral)\b"),
    "uap": _W(r"\b(ufo|uap|unidentified|alien\w*|sighting\w*)\b"),
    "faith": _W(r"\b(church\w*|pope|vatican|mosque|temple|synagogue|bishop|priest|religio\w*|faith|christian\w*|muslim\w*|jewish|hindu|catholic\w*|clergy)\b"),
    "people": _W(r"."),
    "hazard": _W(r"\b(hazard\w*|chemical|spill\w*|leak\w*|toxic|radiation|explosion|fire|evacuat\w*|warning|emergency|disaster|collapse\w*|recall\w*|contamina\w*|alert)\b"),
    "scandal": _W(r"\b(scandal|corruption|embezzl\w*|brib\w*|kickback|impeach\w*|ethics|cover-?up|resign\w*|probe|investigation|fraud)\b"),
    "other": _W(r"."),
}
# a word used as a verb or a figure of speech never decides a category on its own
_FIG = [
    (re.compile(r"[\"'\u2018\u2019\u201c\u201d](?:political )?(earthquake|tsunami|storm|firestorm|eruption|explosion|war|bomb\w*|meltdown)[\"'\u2018\u2019\u201c\u201d]", re.I), " "),
    (re.compile(r"\b(political|diplomatic|media|social media|perfect|economic|price|trade|culture|legal|twitter|shit|pr|financial)\s+(earthquake|tsunami|storm|firestorm|explosion|war|wars|bomb|meltdown|eruption)s?\b", re.I), " "),
    (re.compile(r"\b(storm(?:s|ed|ing)?)\s+(?:a|an|the|into|through|out|off|in|onto|past)\b", re.I), " "),
    (re.compile(r"\b(lead explosion|explosion of|exploded in popularity|price war|bidding war|culture war|war of words|war on drugs|war chest|war room|star wars)\b", re.I), " "),
]
_ACCIDENT = _W(r"\b(fuel (?:truck|tanker)|tanker (?:truck|lorry)|petroleum products|overturn\w*|highway fire|road (?:accident|crash)|traffic (?:accident|crash)|collision|derail\w*|bus (?:crash|plunge)|car crash|plane crash|ferry (?:capsiz|sink)\w*|gas (?:cylinder|explosion)|industrial (?:accident|fire|explosion))")
_HARD_MIL = _W(r"\b(missiles?|rockets?|drones?|air ?strikes?|shell(?:ing|ed)|artillery|troops?|soldiers?|army|military|militants?|hamas|hezbollah|houthis?|idf|occupation forces|invasion|ballistic|bomb(?:ing|ed|s)?|warships?)\b")
_SPORT = _W(r"\b(league|football|soccer|nba|nfl|nhl|mlb|f1|formula (?:1|one)|grand prix|olympic\w*|world cup|cup final|match|matches|bayern|losc|premier league|champions league|tennis|golf|cricket|rugby|boxing|ufc|coach|quarterback|playoffs?|tournament|cost cap)\b")
_RESCUE_ORDER = ("quake", "weather", "disease", "conflict", "space", "cyber", "wreck", "crime", "unrest", "markets", "politics", "faith", "uap")

def _defig(text):
    for rx, rep in _FIG:
        text = rx.sub(rep, text)
    return text

def _has(k, text):
    rx = EV.get(k)
    return bool(rx and rx.search(text))

def category(k, title, text=""):
    """Corrected display key. Only changes a key whose own evidence is missing from the headline (and lead text)."""
    t = _defig(title or ""); full = _defig(((title or "") + " " + (text or ""))[:1500])
    k = k or "other"
    if _SPORT.search(t) and not _HARD_MIL.search(t) and k not in ("crime", "wreck", "deaths"):
        return "other"
    if k == "conflict" and _ACCIDENT.search(t) and not _HARD_MIL.search(full):
        return "wreck"
    if k in ("people", "other", "deaths", "scandal", "hazard", "infra"):
        return k
    if _has(k, t) or (k not in ("quake", "weather", "disease", "cyber") and _has(k, full)):
        return k
    for c in _RESCUE_ORDER:
        if c != k and _has(c, t):
            return c
    if k in ("conflict", "quake", "weather", "disease", "cyber", "space"):
        return "politics" if _has("politics", full) else "other"
    return k

# ------------------------------------------------------------------ photo / category consistency
_SAT = re.compile(r"(satellite|imaged by|avhrr|modis|goes-\d|viirs|landsat|sentinel-\d|blue marble|iss0\d|shaded relief|relief map|topograph|terrain map|\bmap\b|locator|orthographic)", re.I)
_PHOTO_OK = {   # topic photo hazard keys a display category may carry
    "weather": {"storm", "freeze", "flood", "wildfire", "tsunami"},
    "quake": {"quake", "volcano", "tsunami"},
    "disease": {"measles", "ebola", "flu", "outbreak"},
    "space": {"spaceweather"},
    "cyber": {"cyber"},
    "conflict": {"military", "aviation"},
    "unrest": {"military", "government"},
    "politics": {"government", "military", "economy"},
    "markets": {"economy"},
    "infra": {"grid", "aviation", "cyber"},
    "wreck": {"aviation"},
    "hazard": {"wildfire", "flood", "grid"},
    "crime": set(), "deaths": set(), "people": set(), "faith": set(), "uap": set(), "scandal": {"government"}, "other": {"economy", "aviation"},
}
_HAZ_K = {"weather", "quake", "disease", "space", "hazard"}

def photo_verdict(k, choice, country_names=()):
    """choice: story_photo's stored candidate dict. Returns 'ok', 'none' or 'bad:<why>'."""
    if not choice or choice.get("none") or not choice.get("src"):
        return "none"
    blob = " ".join(str(choice.get(x) or "") for x in ("src", "title", "label", "caption", "subject", "categories", "alt"))
    if _SAT.search(blob):
        return "bad:satellite"
    kind = (choice.get("kind") or "").lower()
    hz = (choice.get("hazard") or "").lower()
    if kind == "topic" or hz:
        try:
            import card_photo as CP
            hz = CP._TOPIC_ALIAS.get(hz, hz)
        except Exception:
            pass
        if hz and hz not in _PHOTO_OK.get(k, set()) and hz != "general":
            return f"bad:topic-{hz}-on-{k}"
    if kind == "place":
        if k in _HAZ_K:
            return "bad:place-on-hazard"
        subj = (choice.get("subject") or "").strip().lower()
        if k in ("conflict", "unrest", "crime", "wreck") and subj and subj in country_names:
            return "bad:country-photo-on-" + k
    return "ok"

def photo_state(cid):
    try:
        import story_photo as SP
        c = SP.db_choice(cid)
        # the finished PNG must be the photo card, not the text fallback (src only: never load the PNG blob here)
        row = SP._read(lambda k: k.execute("SELECT src FROM story_cards WHERE cid=?", (cid,)).fetchone())
        has = bool(row and (row[0] or "").startswith("https://"))
        if has:
            # same subject/licence checks as story_photo.has_photo, minus "the JPEG bytes are on hand": after a restart the
            # JPEG cache is rebuilt slowly while the finished photo PNG is already stored (116 of 161 rows were held for it)
            ok = bool(c and not c.get("none") and c.get("src") and SP.license_ok(c.get("license") or "")
                      and not SP.is_non_photo_candidate(c) and SP.stored_photo_matches(cid) is not False
                      and not SP.photo_is_wrong_subject(cid, c.get("src") or "", " ".join((c.get("credit") or "", c.get("caption") or "", c.get("label") or "", c.get("alt") or "")))
                      and (row[0] or "") == (c.get("src") or ""))
            has = ok
    except Exception:
        return None, None            # unknown (cards.db problem): the caller must not read this as "no photo"
    return c, has

# ------------------------------------------------------------------ location sanity
_AGENCY_LOC = re.compile(r"^\s*(?:[A-Z]{4}\s+)?(?:VAAC|WAAF|RJTD|SCEZ|RPHI|MHCC|WSSS|KNES|EGRR|LFPW|SABM|ADRM|YMMC|NZKL|CWAO|PAWU|FMEE|VABB)\b|\b(?:VAAC)\b", re.I)
_DEFAULT_LL = [(0.0, 0.0), (39.8283, -98.5795), (38.0, -97.0), (39.5, -98.35), (37.0902, -95.7129), (20.0, 0.0)]

def location(loc, lat, lon):
    """(loc, lat, lon, note). Drops agency codes as place text and default/placeholder coordinates."""
    note = ""
    if loc and _AGENCY_LOC.search(loc):
        loc, note = "", "agency-code"
    try:
        la, lo = float(lat), float(lon)
        if any(abs(la - a) < 0.05 and abs(lo - b) < 0.05 for a, b in _DEFAULT_LL) or not (-90 <= la <= 90 and -180 <= lo <= 180):
            lat = lon = None; note = note or "default-coords"
    except (TypeError, ValueError):
        lat = lon = None
    return loc, lat, lon, note

# ------------------------------------------------------------------ tags
_ACRO = {"NATO", "UN", "EU", "US", "UK", "WHO", "CDC", "FBI", "CIA", "NSA", "DHS", "FEMA", "NOAA", "NWS", "USGS", "NASA", "FAA", "IDF", "ISIS",
         "OPEC", "IAEA", "CISA", "UAE", "DRC", "GOP", "SEC", "IMF", "ICE", "ATF", "DOJ", "DOD", "UAP", "UFO", "AI", "CVE", "H5N1", "MPOX",
         "NVIDIA", "NASDAQ", "COVID", "UNICEF", "INTERPOL", "SPACEX", "OPENAI", "BBC", "CNN", "NYC", "LA", "DC", "EV", "FIFA", "NFL", "NBA", "F1", "BNP"}
_EXTRA = {"Alberta", "Ontario", "Quebec", "Manitoba", "Saskatchewan", "NovaScotia", "NewBrunswick", "Newfoundland", "Yukon", "Nunavut",
          "Queensland", "Victoria", "Tasmania", "NewSouthWales", "WesternAustralia", "SouthAustralia", "Scotland", "Wales", "England",
          "Earthquake", "Volcano", "Eruption", "VolcanicAsh", "Tsunami", "Flood", "Flooding", "Storm", "WinterStorm", "Hurricane", "Typhoon", "Cyclone", "Tornado",
          "Wildfire", "Weather", "Snow", "Rain", "Heatwave", "HeatWave", "Drought", "Landslide", "Avalanche", "Blizzard", "HighWind",
          "Cybersecurity", "Cyberattack", "Ransomware", "Hacking", "Hackers", "DataBreach", "Malware", "Vulnerability", "Phishing", "Breach",
          "War", "Military", "Conflict", "Missile", "Missiles", "Drone", "Drones", "Airstrike", "Navy", "Army", "Ceasefire", "Nuclear", "Terrorism",
          "Health", "Outbreak", "Vaccine", "Measles", "Ebola", "Mpox", "Cholera", "Dengue", "Polio", "BirdFlu", "Influenza", "Flu", "Norovirus",
          "Covid19", "Screwworm", "Politics", "Election", "Elections", "Congress", "Senate", "WhiteHouse", "Kremlin", "Pentagon", "Parliament",
          "Protest", "Protests", "Crime", "Police", "Shooting", "Accident", "Crash", "Aviation", "Outage", "PowerOutage", "Internet", "Markets",
          "Stocks", "Oil", "Economy", "Inflation", "Tariffs", "Banking", "Crypto", "Bitcoin", "SpaceWeather", "Solar", "Aurora", "UAP", "Religion",
          "Obituary", "Evacuation", "Emergency", "Refugees", "Sanctions", "Energy", "Space", "Science", "Climate", "Disaster", "Trump", "Putin",
          "Zelensky", "Netanyahu", "Kushner", "Xi", "Microsoft", "Google", "Apple", "Amazon", "Meta", "Tesla", "Nvidia", "GitLab", "GitHub",
          "Cisco", "Fortinet", "Juniper", "Drupal", "Hitachi", "Siemens", "Boeing", "Airbus", "OpenAI", "Gaza", "Hamas", "Hezbollah", "Houthis",
          "Israel", "Iran", "Ukraine", "Russia", "China", "Taiwan", "MicrosoftEdge", "Chrome", "Android", "iOS", "Windows", "Linux", "Telegram",
          "Ethereum", "Seismic", "ISIL", "FinCEN", "Cybercrime", "GeoNet", "Interpol", "Europol", "Hezbollah", "Vatican", "Pope", "Moscow", "Kyiv", "Tehran", "Beijing", "Jerusalem", "Sanaa", "Cairo", "RedSea", "Hormuz", "Strait"}
_CAT_TAG = {"conflict": "Conflict", "weather": "Weather", "quake": "Earthquake", "disease": "Health", "cyber": "Cybersecurity",
            "politics": "Politics", "markets": "Markets", "crime": "Crime", "unrest": "Protest", "wreck": "Accident", "infra": "Outage",
            "space": "SpaceWeather", "hazard": "Emergency", "deaths": "Obituary", "uap": "UAP", "faith": "Religion", "scandal": "Politics"}
_BAD = {"news", "worldnews", "breaking", "breakingnews", "blackoutnetwork", "blackout", "update", "updates", "live", "watch", "read", "video",
        "maybe", "mass", "gentlemen", "princess", "fascist", "stagecoup", "alert", "alerts", "report", "reports", "warning", "advisory",
        "today", "now", "urgent", "world", "global", "latest", "developing", "story", "storm" + "ing", "storms" + "ed", "storm" + "ed"}
_known = None
_COMMON = set("""maybe what happened two three four five one six seven ten audio video ouster indicate indicates fuel perfect explosion
disrupted fascist children pitcher coup near incident naval ballistic volcanic satellite security hacker gentlemen princess mass watch
read live update breaking report says new latest funniest scariest reactions weird lead join today tonight special first last big
good bad more most many some several another other people man woman men women police officials official president minister city
state county region area north south east west central western eastern northern southern upper lower total about after
later which what who whom whose where when why how this that these those then now soon still just also only very here there
logged posted updated reported confirmed blamed according amid during while before since until again even yet already
happened happening whathappened jan feb mar apr jun jul aug sep sept oct nov dec january february march april june july
august september october november december monday tuesday wednesday thursday friday saturday sunday morning evening night
week weekend month year yesterday tomorrow thanks thanksgiving holiday treaty vulnerabilities vulnerability""".split())

def _known_set():
    global _known
    if _known is not None:
        return _known
    s = {x.lower() for x in _EXTRA} | {x.lower() for x in _ACRO}
    try:
        import x_share as X
        s |= {str(v).lower() for v in X.POPULAR}
        s |= {str(v).lower().replace(" ", "") for v in X._COUNTRIES.values()}
        s |= {str(v[0]).lower() for v in X._CITIES.values()} | {str(v[1]).lower() for v in X._CITIES.values()}
        s |= {str(v).lower().replace(" ", "") for v in X._US_STATES.values()}
        s |= {str(k).lower() for k in X._PEOPLE_FULL}
        s |= {re.sub(r"\s+", "", o.title()).lower() for o in X._KNOWN_ORGS}
        s |= {lab.lower() for _rx, lab in X._DISEASES} | {lab.lower() for _rx, lab in X._HAZARDS}
    except Exception:
        pass
    s -= _BAD
    _known = s
    return s

def _title_case(title):
    w = [x for x in re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", title or "") if len(x) > 3]
    return bool(w) and sum(1 for x in w if x[0].isupper()) / len(w) > 0.6

def tag_ok(tag, title="", known=()):
    """known: extra known entities for this story (x_share.location_tags: geocoded places)."""
    t = (tag or "").lstrip("#")
    if not t or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,24}", t):
        return False
    lo = t.lower()
    if lo in _BAD:
        return False
    if lo in _known_set() or lo in {str(x).lstrip("#").lower() for x in (known or ())}:
        return True
    # function words and run-togethers of them (#Later, #Which, #WhatHappened, #LoggedNov) are never tags
    hump = [p.lower() for p in re.findall(r"[A-Z][a-z0-9]*", t)]
    if lo in _COMMON or (hump and all(p in _COMMON for p in hump)) or (len(hump) == 2 and hump[1] in _COMMON):
        return False
    if t.isupper():                       # obscure acronyms (#WAAF, #HKCERT, #READ) are not tags people search
        return False
    if t[0].islower():
        return False
    parts = re.findall(r"[A-Z][a-z0-9]*", t)
    if len(t) > 14 or len(parts) > 2:     # long run-togethers are never tags unless a known name
        return False
    if len(parts) == 2:                   # a two-word proper name written that way in the headline (#AlJazeera, #TeAraroa)
        if any(p.lower() in _COMMON for p in parts):
            return False
        return bool(re.search(r"\b" + parts[0] + r"[\s-]+" + parts[1] + r"\b", title or ""))
    # an unknown single word is not a known entity: never a tag (Nov 25 10:40 PM: #Hicks, #Zealand, #Later)
    if os.environ.get("BN_WIRE_TAG_STRICT", "1") != "0":
        return False
    if _title_case(title):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z0-9'\u2019]*", title or "")
    if lo in _COMMON:
        return False
    for m in re.finditer(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", title or ""):
        before = (title or "")[:m.start()].rstrip(); after = (title or "")[m.end():].lstrip()
        if not before or re.search(r"[.:!?|\u2022\n-]$", before):
            continue                     # sentence-initial capital proves nothing
        if re.match(r"[A-Z][a-z]", after) or re.search(r"(?:^|\s)[A-Z][a-z]+$", before):
            continue                     # part of a longer name (#Hicks of Hicks Bay, #Zealand of New Zealand)
        return True
    return False

def _case(tag):
    t = tag.lstrip("#"); lo = t.lower()
    for x in _EXTRA | _ACRO:
        if x.lower() == lo:
            return x
    if t.islower():
        return t[:1].upper() + t[1:]
    return t

def tags(raw, k, title="", loc_tags=()):
    """3-5 validated tags. raw: the generator's tags; loc_tags: place tags from x_share.location_tags."""
    out = []
    for t in list(raw or []) + list(loc_tags or []):
        t = "#" + _case(str(t).lstrip("#"))
        if tag_ok(t, title, loc_tags) and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    have = lambda t: t.lower() in {x.lower() for x in out}
    ct = _CAT_TAG.get(k)
    if k == "quake" and re.search(r"volcan|erupt|ash cloud", title or "", re.I):
        ct = "Volcano" if not have("#Volcano") else "Eruption"
    if ct and len(out) < 3 and not have("#" + ct):
        out.append("#" + ct)
    if len(out) < 3:   # top up from the headline itself: places, known names and popular topic words it contains
        words = re.findall(r"[A-Za-z][A-Za-z0-9]*", title or "")
        known = _known_set()
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                cand = "".join(w[:1].upper() + w[1:] for w in words[i:i + n])
                if cand.lower() in known and not have("#" + _case(cand)) and len(out) < 3:
                    if n == 1 and (cand.lower() in _COMMON or (cand.upper() in _ACRO and not words[i].isupper())):
                        continue
                    out.append("#" + _case(cand))
    volc = k == "quake" and re.search(r"volcan|erupt|ash cloud|ash advisory", title or "", re.I)
    for extra in (("Volcano", "Eruption", "VolcanicAsh") if volc else _CAT_TAG2.get(k, ())):
        if len(out) >= 3:
            break
        if extra == "Military" and not _HARD_MIL.search(title or ""):
            continue
        if not have("#" + extra):
            out.append("#" + extra)
    return out[:5]

_CAT_TAG2 = {"quake": ("Earthquake", "Seismic"), "weather": ("Weather", "Storm"), "cyber": ("Cybersecurity", "Hacking"),
             "markets": ("Markets", "Economy"), "disease": ("Health", "Outbreak"), "politics": ("Politics",),
             "conflict": ("Conflict", "Military"), "space": ("SpaceWeather", "Solar"), "wreck": ("Accident",), "unrest": ("Protest",)}

# ------------------------------------------------------------------ headline
_DANGLE = re.compile(r"(?:[\s,;:\-\u2013\u2014]+(?:[Tt]he|[Aa]n?|at|of|to|and|or|in|on|for|with|by|from|as|into|over|after|amid|about|than|that|its|his|her|their|our|is|are|was|were|be|has|have|had|but|nor|via))+\s*(\u2026|\.\.\.)?$")

def headline(h):
    h0 = (h or "").strip()
    ell = h0.endswith(("\u2026", "..."))
    core = h0.rstrip("\u2026.").rstrip() if ell else h0
    fixed = _DANGLE.sub("", core).rstrip(",;:-\u2013\u2014 ")
    if fixed != core:
        return fixed + ("\u2026" if ell else ""), True
    return h0, False

def thin_headline(h):
    w = re.findall(r"[A-Za-z0-9]+", h or "")
    return len(w) < 4

# ------------------------------------------------------------------ one call
def check(it, raw_tags=None, loc_tags=(), choice=None, has_photo=None, country_names=()):
    """it: a /api/wire_tl item dict (h, d, k, loc, lat, lon). Returns the verdict; never raises."""
    v = {"ok": True, "reasons": [], "fixes": []}
    try:
        title = it.get("h") or ""; text = it.get("d") or ""
        k = category(it.get("k"), title, text)
        if k != it.get("k"):
            v["fixes"].append(f"cat:{it.get('k')}->{k}")
        v["k"] = k
        h, cut = headline(title)
        if cut:
            v["fixes"].append("headline")
        v["h"] = h
        if thin_headline(h):
            v["ok"] = False; v["reasons"].append("thin-headline")
        loc, lat, lon, note = location(it.get("loc") or "", it.get("lat"), it.get("lon"))
        if note:
            v["fixes"].append("loc:" + note)
        v.update(loc=loc, lat=lat, lon=lon)
        if raw_tags is not None:
            tg = tags(raw_tags, k, title, loc_tags)
            v["tags"] = tg
            if len(tg) < 3:
                v["ok"] = False; v["reasons"].append(f"tags<{len(tg)}>")
        if has_photo is None:
            v["ok"] = False; v["reasons"].append("photo-check-error")
        else:
            pv = photo_verdict(k, choice, country_names)
            v["photo"] = pv
            if not has_photo:
                v["ok"] = False; v["reasons"].append("no-photo-card")
            elif pv.startswith("bad"):
                v["ok"] = False; v["reasons"].append("photo-" + pv)
    except Exception as ex:   # a validator bug must not hide the whole Wire: report it, keep the item's previous state
        v["error"] = f"{type(ex).__name__}: {ex}"[:160]
    return v

# ------------------------------------------------------------------ share-card hooks
def photo_category(stored, title, text=""):
    """The display key the card photo should follow (stored scanner category in, validated Wire key out)."""
    try:
        import wire_timeline as WT
        k0 = WT.cat_key(stored, title, False)
    except Exception:
        k0 = "other"
    return category(k0, title, text)

def no_country_photo(k):
    return k in ("conflict", "unrest", "crime", "wreck", "weather", "quake", "disease", "space", "hazard")
