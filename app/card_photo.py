"""Deterministic, always-relevant licensed photo for a story card (share_card v3).

Order:
  1. A person named in the headline, from the hashtag entity extractor's PEOPLE list.
     Their Wikidata P18 portrait, matched by QID (never a text search for the image).
  2. Otherwise the story's own place (the same location the Wire map uses): the Wikidata P18 image of
     that place's QID. City, else region, else country (a country falls back to its capital's image).
  3. Otherwise a topic photo from a public-domain agency library keyed by hazard type
     (CDC PHIL, NOAA/NWS, USGS, USFS/NIFC, FEMA, and a generic server photo for cyber).

Only PD, CC0, CC BY and CC BY-SA files are used, always with credit. Nothing is generated or edited:
every image is a real archive photo and the card labels it "File photo; not taken at this event."
"""
import hashlib
import json
import math
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

UA = "BLACKOUTNETWORK-cards/3.0 (https://blackout.network/; hello@blackout.network)"
LABEL_TAIL = "File photo; not taken at this event."

# Wikidata QIDs for the extractor's PEOPLE list (x_share._PEOPLE_FULL values -> QID).
PEOPLE_QID = {
    "Scott Bessent": "Q7435987",
    "Jerome Powell": "Q6182718",
    "Janet Yellen": "Q263725",
    "Antony Blinken": "Q7821917",
    "Marco Rubio": "Q324546",
    "Vladimir Putin": "Q7747",
    "Volodymyr Zelensky": "Q3874799",
    "Pete Hegseth": "Q7172014",
    "Benjamin Netanyahu": "Q43723",
    "Xi Jinping": "Q15031",
    "Vitali Klitschko": "Q31919",
    "Jensen Huang": "Q305177",
}

_LIC_OK = re.compile(r"^(public domain|pd\b|cc0|cc[ -]by(?:[ -]sa)?(?:[ -]\d(?:\.\d)?)?(?:\s|$)|attribution)", re.I)
_LIC_BAD = re.compile(r"\b(nc|nd|noncommercial|no derivatives|gfdl only|fair use|all rights)\b", re.I)
_NOT_SCENE = re.compile(r"(flag|coat[ _]of|locator|location|map|logo|seal|emblem|blank|\bsvg\b|shield|banner|wordmark)", re.I)


# Relief / satellite / map-like views are not a ground-level place photo (Matt, Nov 25 2026 5:24 PM ET).
# Filenames like New_Zealand_NASA.jpg often omit the word "map", so this also reads credit and description.
_MAPLIKE = re.compile(
    r"(shaded[ _-]?relief|relief[ _-]?(map|render|shading|image|of)|"
    r"topograph(?:ic|y)[ _-]?(map|render|view|of)?|"
    r"\b(srtm|gtopo|etopo|aster|modis|landsat|viirs|envisat|copernicus)\b|"
    r"sentinel[- ]?[123]|"
    r"satellite[ _-]?(image|imagery|view|photo|photograph|map|of)|"
    r"(?:image|view|photo|photograph)[ _-]?from[ _-]?(?:space|orbit)|"
    r"from[ _-]?(?:space|orbit)|as[ _-]seen[ _-]from[ _-](?:space|orbit|satellite)|"
    r"blue[ _-]marble|visible[ _-]earth|earth[ _-]observatory|"
    r"nasa[ /._-]*(?:jpl|nima|topography|relief|srtm)|"
    r"\bnima\b|world[ _-]wind|"
    r"esa[ /._-]*(?:satellite|envisat|sentinel|copernicus|earth)|"
    r"false[ _-]colou?r|spaceborne|orbital[ _-](?:image|view|photo)|"
    r"\biss\d{2,3}[ _-]?[a-z]?[ _-]\d{3,}|remote[ _-]sensing|astronaut[ _-]photograph\w*|"
    r"digital[ _-]?elevation|\bdem\b|bathymetr\w*)",
    re.I,
)


def is_map_like(filename="", title="", credit="", desc="", categories="", src=""):
    """True for relief renderings, satellite country views, and other map-like imagery."""
    blob = " ".join(
        str(x).replace("_", " ").replace("%20", " ").replace("/", " ")
        for x in (filename, title, credit, desc, categories, src) if x
    )
    return bool(blob and _MAPLIKE.search(blob))


# Curated Commons files per hazard (public-domain agency libraries; the generic server photo is CC).
TOPICS = {
    "measles": ("CDC PHIL", ["File:Morbillivirus measles infection.jpg"], "Measles virus"),
    "ebola": ("CDC PHIL", ["File:Ebola virus virion.jpg"], "Ebola virus"),
    "flu": ("CDC PHIL", ["File:Influenza virus particle color.jpg"], "Influenza virus"),
    "outbreak": ("CDC PHIL", ["File:Influenza virus particle color.jpg"], "Virus"),
    # Nov 25 2026 (pt1925u): no satellite imagery on cards; a ground-level FEMA storm-damage photo instead of the Katrina satellite shot.
    "storm": ("FEMA", ["File:FEMA - 38737 - Boats moved on shore and damaged by Hurricane Ike.jpg"], "Storm damage"),
    "freeze": ("NOAA/NWS", ["File:Early February 2022 North American winter storm 2022-02-03.jpg"], "Winter storm"),
    "quake": ("USGS", ["File:1933 Long Beach earthquake damage 1.jpg"], "Earthquake damage"),
    "volcano": ("USGS", ["File:Eruption at the summit of Kilauea volcano (118574).jpeg"], "Volcanic eruption"),
    "wildfire": ("USFS", ["File:Frog Fire with Mt Shasta USFS 2015 08 04.jpeg"], "Wildfire"),
    "flood": ("FEMA", ["File:FEMA - 34508 - Flooded street in Missouri.jpg"], "Flooding"),
    "cyber": ("Server racks", ["File:BalticServers data center.jpg"], "Server racks"),
    # Category / subject fallbacks (Nov 25 2026, 4:47 PM ET): every story gets a real licensed photo, never a map.
    "military": ("U.S. Air Force", ["File:B-2 Spirit original.jpg", "File:F-35A flight (cropped).jpg"], "Military aircraft"),
    "aviation": ("NASA", ["File:B747 with Space Shuttle on it from above.jpg"], "Aircraft in flight"),
    "grid": ("Power lines", ["File:Transmission Lines at Sunset.jpg"], "Power transmission lines"),
    "economy": ("U.S. Treasury Building", ["File:US Treasury Building.jpg"], "U.S. Treasury Building"),
    "spaceweather": ("NASA/SDO", ["File:The Sun by the Atmospheric Imaging Assembly of NASA's Solar Dynamics Observatory - 20100819.jpg"], "The Sun"),
    "government": ("U.S. Capitol", ["File:United States Capitol - west front.jpg"], "U.S. Capitol"),
    "general": ("NASA", ["File:The Earth seen from Apollo 17.jpg"], "Earth from space"),
}
# Fallback keys: a curated file for one of these is allowed on any story the chooser sent it to.
FALLBACK_KEYS = frozenset({"military", "aviation", "grid", "economy", "spaceweather", "government", "general"})
# Story category (Wire "k") -> fallback key when the headline names no hazard or place.
# Wire keys (conflict, quake, ...) and story categories ("war/conflict", "natural disaster", ...) both match by substring.
CATEGORY_KEY = (("conflict", "military"), ("war", "military"), ("cyber", "cyber"), ("weather", "storm"), ("storm", "storm"),
                ("disease", "outbreak"), ("health", "outbreak"), ("outbreak", "outbreak"), ("quake", "quake"), ("seismic", "quake"),
                ("politic", "government"), ("government", "government"), ("market", "economy"), ("econom", "economy"), ("financ", "economy"))
_US_POLITICS = re.compile(r"\b(congress|senate|senator|house (?:speaker|republicans?|democrats?)|white house|capitol|u\.?s\.?|trump|biden|vance|republican|democrat|washington|pentagon|supreme court)\b", re.I)
_HAZARDS = [
    ("cyber", r"\b(cyber|ransomware|malware|vulnerabilit(?:y|ies)|cve-?\d|(?:security|cisa|vendor) advisory|zero-day|hack(?:ed|ers?)?|data breach|phishing|botnet|ddos|exploit)"),
    ("quake", r"\b(earthquake|quake|tremor|aftershock|seismic|magnitude|\bM ?\d\.\d)"),
    ("volcano", r"\b(volcano|volcanic|eruption|erupts?)\b"),
    ("tsunami", r"\btsunamis?\b"),
    ("wildfire", r"\b(wildfires?|forest fires?|bush ?fires?|brush fire|fire weather|burn(?:ing)? acres)"),
    ("flood", r"\b(flood(?:s|ing|ed)?|flash flood|inundat)"),
    ("freeze", r"\b(freeze|freezing|frost|blizzard|winter storm|snow|ice storm|cold wave|wind chill)"),
    ("storm", r"\b(hurricane|typhoon|cyclone|tropical storm|tornado|storm|thunderstorm|gale)"),
    ("ebola", r"\bebola|marburg"),
    ("measles", r"\bmeasles"),
    ("flu", r"\b(influenza|flu|h5n1|bird flu|avian)\b"),
    ("outbreak", r"\b(outbreak|epidemic|meningitis|cholera|disease|virus|mpox|dengue|polio|pandemic)"),
    ("spaceweather", r"\b(solar flare|geomagnetic|solar storm|coronal mass|sunspot|aurora|space weather|solar wind)"),
    ("grid", r"\b(power outage|power grid|electric grid|transmission line|substation|grid operator|load shedding|blackouts?)\b"),
    ("aviation", r"\b(airlines?|airports?|flights?|aircraft|airliner|airspace|air traffic|FAA|jetliner)\b"),
    ("military", r"\b(missiles?|military|army|navy|air force|troops?|airstrikes?|drones?|ceasefire|offensive|artillery|nato|soldiers?|warship|fighter jets?)\b"),
    ("economy", r"\b(stocks?|stock market|inflation|tariffs?|federal reserve|treasury|nasdaq|gdp|jobs report|oil prices?|wall street)\b"),
]


def cache_dir():
    d = Path(os.environ.get("BN_CARD_PHOTO_DIR") or (Path(tempfile.gettempdir()) / "bn_card_photo"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# Source thumbs (iiurlwidth=1600) and API JSON are far smaller; never slurp a huge body.
_MAX_GET = 6 * 1024 * 1024


def _get(url, timeout=25, tries=3, max_bytes=_MAX_GET):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Api-User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                cl = r.headers.get("Content-Length")
                if cl and int(cl) > max_bytes:
                    raise ValueError("payload too large")
                chunks, n = [], 0
                while True:
                    buf = r.read(64 * 1024)
                    if not buf:
                        break
                    n += len(buf)
                    if n > max_bytes:
                        raise ValueError("payload too large")
                    chunks.append(buf)
                return b"".join(chunks)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


def _api(host, **p):
    p["format"] = "json"
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(p)
    key = cache_dir() / ("api_" + hashlib.sha1(url.encode()).hexdigest() + ".json")
    if key.exists() and time.time() - key.stat().st_mtime < 86400:
        try:
            return json.loads(key.read_text())
        except Exception:  # noqa: BLE001
            pass
    d = json.loads(_get(url))
    try:
        key.write_text(json.dumps(d))
    except Exception:  # noqa: BLE001
        pass
    return d


def _strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&amp;", "&", s)
    return " ".join(s.split())


def license_allowed(lic):
    lic = (lic or "").strip()
    return bool(lic) and bool(_LIC_OK.search(lic)) and not _LIC_BAD.search(lic)


def commons_image(filename, width=1600, min_w=700):
    """Commons file -> {src,path,credit,license,title,page,w,h} or None when not an allowed real photo."""
    fn = filename if filename.startswith("File:") else "File:" + filename
    d = _api("commons.wikimedia.org", action="query", titles=fn, prop="imageinfo",
             iiprop="url|size|mime|extmetadata", iiurlwidth=width,
             iiextmetadatafilter="LicenseShortName|Artist|Credit|ImageDescription|Categories")
    pages = (d.get("query") or {}).get("pages") or {}
    for p in pages.values():
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        mime = (ii.get("mime") or "").lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        em = ii.get("extmetadata") or {}
        lic = _strip((em.get("LicenseShortName") or {}).get("value"))
        if not license_allowed(lic):
            continue
        if int(ii.get("width") or 0) < min_w:
            continue
        artist = _strip((em.get("Artist") or {}).get("value")) or _strip((em.get("Credit") or {}).get("value"))
        artist = re.sub(r"\s*(Photo Credit|Content Providers?\(s\)):?", "", artist, flags=re.I).strip(" :;,")
        desc = _strip((em.get("ImageDescription") or {}).get("value"))
        cats = _strip((em.get("Categories") or {}).get("value"))
        fn_title = p.get("title", fn).replace("File:", "")
        if is_map_like(filename=fn, title=fn_title, credit=artist, desc=desc, categories=cats,
                       src=" ".join(str(x or "") for x in (ii.get("thumburl"), ii.get("url")))):
            continue
        if len(artist) > 60:
            artist = artist[:60].rsplit(" ", 1)[0]
        credit = (artist + " / " if artist else "") + "Wikimedia Commons"
        return {"src": ii.get("thumburl") or ii.get("url"), "credit": credit, "license": lic,
                "title": p.get("title", fn).replace("File:", ""), "page": ii.get("descriptionurl", ""), "link": ii.get("descriptionurl", ""),
                "w": int(ii.get("width") or 0), "h": int(ii.get("height") or 0)}
    return None


def fetch(info):
    """Download the thumb once into the cache; returns the local path."""
    src = info["src"]
    ext = ".png" if src.lower().split("?")[0].endswith(".png") else ".jpg"
    p = cache_dir() / (hashlib.sha1(src.encode()).hexdigest() + ext)
    if not p.exists() or p.stat().st_size < 4000:
        p.write_bytes(_get(src, timeout=40))
    return str(p)


def _claims(qid):
    d = _api("www.wikidata.org", action="wbgetentities", ids=qid, props="claims|labels|descriptions", languages="en")
    return (d.get("entities") or {}).get(qid) or {}


def _p18_files(ent):
    out, pref = [], []
    for c in (ent.get("claims") or {}).get("P18", []):
        try:
            v = c["mainsnak"]["datavalue"]["value"]
        except Exception:  # noqa: BLE001
            continue
        (pref if c.get("rank") == "preferred" else out).append(v)
    return pref + out


def qid_image(qid, allow_nonscene=False):
    """First allowed real photo from the item's P18 (preferred rank first), matched by QID."""
    ent = _claims(qid)
    for fn in _p18_files(ent):
        if not allow_nonscene and (_NOT_SCENE.search(fn) or is_map_like(filename=fn)):
            continue
        im = commons_image(fn)
        if im:
            im["qid"] = qid
            im["label_en"] = ((ent.get("labels") or {}).get("en") or {}).get("value", "")
            return im
    return None


# ------------------------------------------------------------------ tier 1: person
def person_photo(title, text=""):
    try:
        import x_share
        names = x_share.people_from_entities(title or "", text or "")
    except Exception:  # noqa: BLE001
        names = []
    names = [n for n in names if n in PEOPLE_QID]
    if not names:
        return None

    def pos(n):
        last = n.split()[-1]
        m = re.search(r"\b" + re.escape(last) + r"\b", title or "", re.I)
        return m.start() if m else 10 ** 6
    names.sort(key=pos)
    for n in names:
        im = qid_image(PEOPLE_QID[n], allow_nonscene=True)
        if im:
            im.update(kind="person", tier=1, subject=n, label=f"{n}. {LABEL_TAIL}")
            return im
    return None


# ------------------------------------------------------------------ tier 2: place
def _km(a, b, c, d):
    r = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(h)))


def _coord(ent):
    for c in (ent.get("claims") or {}).get("P625", []):
        try:
            v = c["mainsnak"]["datavalue"]["value"]
            return float(v["latitude"]), float(v["longitude"])
        except Exception:  # noqa: BLE001
            continue
    return None


def _first_val(ent, prop):
    for c in (ent.get("claims") or {}).get(prop, []):
        try:
            return c["mainsnak"]["datavalue"]["value"]
        except Exception:  # noqa: BLE001
            continue
    return None


def place_qid(name, lat, lon, cc, precision):
    """QID of the place, verified by coordinates (and ISO code for a country). Never an unverified text hit."""
    name = (name or "").split(",")[0].strip()
    if not name:
        return None
    d = _api("www.wikidata.org", action="wbsearchentities", search=name, language="en", type="item", limit=10)
    ids = [x["id"] for x in d.get("search", [])]
    if not ids:
        return None
    ents = _api("www.wikidata.org", action="wbgetentities", ids="|".join(ids), props="claims|labels", languages="en").get("entities", {})
    country = precision == "country" or (cc and "," not in name and precision in (None, "", "country"))
    maxkm = 90 if precision == "city" else 450
    best = None
    for q in ids:
        e = ents.get(q) or {}
        inst = {(c.get("mainsnak", {}).get("datavalue", {}).get("value") or {}).get("id") for c in (e.get("claims") or {}).get("P31", [])}
        if "Q5" in inst:
            continue
        iso = _first_val(e, "P297")
        xy = _coord(e)
        if country and cc:
            if iso and str(iso).upper() == str(cc).upper():
                return q
            continue
        if xy and lat is not None and lon is not None:
            km = _km(lat, lon, xy[0], xy[1])
            if km <= maxkm:
                score = (0 if _p18_files(e) else 1, km)
                if best is None or score < best[0]:
                    best = (score, q)
    return best[1] if best else None


def place_photo(hit):
    """hit: {place, lat, lon, cc, precision}. City -> parent region -> country (capital image for a country)."""
    if not hit or not hit.get("place"):
        return None
    place = hit["place"]
    q = place_qid(place, hit.get("lat"), hit.get("lon"), hit.get("cc"), hit.get("precision"))
    if not q:
        return None
    seen, queue, tries = set(), [q], 0
    while queue and tries < 5:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        tries += 1
        im = qid_image(cur)
        if im:
            im.update(kind="place", tier=2, subject=place, label=f"{place}. {LABEL_TAIL}")
            return im
        ent = _claims(cur)
        cap = _first_val(ent, "P36")          # capital (country / region)
        if isinstance(cap, dict) and cap.get("id"):
            queue.append(cap["id"])
        par = _first_val(ent, "P131")          # located in
        if isinstance(par, dict) and par.get("id"):
            queue.append(par["id"])
    return None


# ------------------------------------------------------------------ tier 3: topic
def hazard_for(text):
    t = text or ""
    try:   # storm-as-verb (a raid) is not a hurricane
        import storm_verb
        t = storm_verb.strip(t)
    except Exception:
        pass
    for key, rx in _HAZARDS:
        if re.search(rx, t, re.I):
            return key
    return None


_NO_AGENCY = frozenset({"Server racks", "Power lines", "U.S. Treasury Building", "U.S. Capitol"})


# tsunami uses the curated flood photo (no separate Commons file).
_TOPIC_ALIAS = {"tsunami": "flood"}


def fallback_key(title, text="", category=""):
    """Curated topic key for a story with no matched person or place: its hazard, else its category, else general."""
    k = hazard_for((title or "") + " " + (text or ""))
    if k:
        return _TOPIC_ALIAS.get(k, k)
    cat = (category or "").strip().lower()
    k = next((v for sub, v in CATEGORY_KEY if sub in cat), None)
    if k == "government" and not _US_POLITICS.search((title or "") + " " + (text or "")):
        k = "general"
    return k or "general"


def topic_photo(text, seed="", key=None):
    key = key or hazard_for(text)
    key = _TOPIC_ALIAS.get(key, key)
    if not key or key not in TOPICS:
        return None
    agency, files, noun = TOPICS[key]
    order = list(files)
    if len(order) > 1:
        k = zlib.crc32(str(seed).encode()) % len(order)
        order = order[k:] + order[:k]
    for fn in order:
        im = commons_image(fn)
        if im:
            im.update(kind="topic", tier=3, subject=noun, hazard=key,
                      label=f"{noun} ({agency}). {LABEL_TAIL}" if agency not in _NO_AGENCY else f"{noun}. {LABEL_TAIL}")
            return im
    return None


# Disease/wildfire/storm topic files may stand in for each other in photo_rule.
TOPIC_BEFORE_PLACE = frozenset({"measles", "ebola", "flu", "outbreak", "wildfire", "storm", "freeze", "flood"})
# Natural-disaster and outbreak stories skip place photos (people, culture, country scenery)
# and use the curated agency topic / category hazard photo instead (Matt, Nov 25 2026 5:46 PM ET).
HAZARD_SKIP_PLACE = TOPIC_BEFORE_PLACE | {"quake", "volcano", "tsunami", "spaceweather"}
_HAZARD_CAT = re.compile(
    r"(natural\s*disaster|earthquake|\bquake\b|volcano|storm|hurricane|flood|wildfire|"
    r"tsunami|space\s*weather|outbreak|\bdisease\b|seismic)",
    re.I,
)


def skip_place_photo(title="", text="", category=""):
    """True for hazard / outbreak stories: do not use a generic place or country photo."""
    blob = " ".join(x for x in (title, text) if x)
    k = hazard_for(blob)
    if k in HAZARD_SKIP_PLACE:
        return True
    cat = (category or "").strip()
    if cat.lower() in HAZARD_SKIP_PLACE or cat.lower() in ("quake", "seismic"):
        return True
    if cat and _HAZARD_CAT.search(cat):
        return True
    return False


def enabled():
    """Licensed person/place/topic photo cards. On by default; BN_CARD_PHOTO=0 turns them off."""
    return os.environ.get("BN_CARD_PHOTO", "1") != "0"


def choose_order(title, text="", category=""):
    """('person', 'topic') for hazard/outbreak stories (no place photo); else person, place, topic."""
    if skip_place_photo(title, text, category):
        return ("person", "topic")
    return ("person", "place", "topic")


def topic_file_titles():
    """Lowercased Commons file titles of the curated agency topic photos (no 'File:' prefix)."""
    out = {}
    for key, (_agency, files, _noun) in TOPICS.items():
        for fn in files:
            out[fn.replace("File:", "").replace("_", " ").strip().lower()] = key
    return out


def choose(cid, title, hit=None, text="", category=""):
    """Person, then topic-or-place per choose_order, then a curated category photo so no story is left with a map.
    Returns a photo dict ready for share_card._lay_story, or None only if Commons cannot be reached."""
    steps = {
        "person": lambda: person_photo(title, text),
        "place": lambda: place_photo(hit),
        "topic": lambda: topic_photo(title + " " + (text or ""), cid),
        "category": lambda: topic_photo("", cid, key=fallback_key(title, text, category)),
    }
    for tier in choose_order(title, text, category) + ("category",):
        try:
            im = steps[tier]()
        except Exception as e:  # noqa: BLE001
            print(f"card_photo: tier error {type(e).__name__}: {e}", flush=True)
            im = None
        if im:
            try:
                im["path"] = fetch(im)
            except Exception as e:  # noqa: BLE001
                print(f"card_photo: fetch failed {type(e).__name__}", flush=True)
                continue
            return im
    return None
