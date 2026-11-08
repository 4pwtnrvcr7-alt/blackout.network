"""Offline place inference for the signal map.

Reads the bundled gazetteer already shipped with the heat map (heatmap_data/: countries,
admin1, cities). No network calls, no API keys, no database writes. A story is placed only
when one place wins cleanly. Ambiguous names (Georgia, Turkey-the-bird, person names) are skipped.
"""
import re
import geo

# Food and other non-place uses of "Turkey". Whole words, checked around the match.
_TURKEY_FOOD = {"roast", "roasted", "dinner", "sandwich", "leftover", "leftovers", "gravy", "stuffing",
                "breast", "drumstick", "thanksgiving", "gobble", "carving", "gravy", "stuffed"}
# Named areas that are one place, used only when no country, state or city wins.
_REGIONS = {
    "gulf of mexico": (25.0, -90.0, "Gulf of Mexico"),
    "persian gulf": (27.0, 51.5, "Persian Gulf"),
    "red sea": (20.0, 38.5, "Red Sea"),
    "black sea": (43.5, 34.5, "Black Sea"),
    "south china sea": (12.0, 114.0, "South China Sea"),
    "taiwan strait": (24.5, 119.5, "Taiwan Strait"),
    "korean peninsula": (38.3, 127.0, "Korean Peninsula"),
    "horn of africa": (8.5, 47.0, "Horn of Africa"),
    "strait of hormuz": (26.6, 56.3, "Strait of Hormuz"),
    "gulf of aden": (12.0, 48.0, "Gulf of Aden"),
}
_COAST = re.compile(r"\b(?:off the coast of|off the coast|near the coast of|coast of)\s+", re.I)
_NWS = re.compile(r"\bby NWS ([A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){0,3})\s+([A-Z]{2})\b")
_NOT_A_PLACE = re.compile(r"location not (specified|reported|recorded)|unknown location|^global\b", re.I)
_OUTLET = re.compile(r"\b(?:FRANCE\s*24|BBC News|BBC|CNN Indonesia|CNN|Reuters|Al Jazeera|Sky News|New York Times|Washington Post|Wall Street Journal)\b", re.I)
# City names that are also ordinary or product words. A bare hit is not enough.
_CITY_BLOCK = {"university", "college", "center", "centre", "dongfeng", "normal", "memorial", "hope", "enterprise",
               "africa", "asia", "europe", "america", "pacific", "atlantic", "arctic", "caribbean", "midwest"}
_MASS = re.compile(r"\bMass(?=\s+(?:protests?|shootings?|casualt\w*|graves?|arrests?|demonstrations?|layoffs?|exodus|migration|killings?|deaths?|funerals?|graves?))", re.I)
_PLACE_WORD = {"county", "parish", "city", "state", "province", "region", "river", "island", "islands", "bay", "gulf",
               "coast", "valley", "oblast", "prefecture", "district", "beach", "mountains", "mountain"}
_TITLE_WORD = {"gov", "governor", "gen", "sen", "senator", "rep", "dr", "mr", "mrs", "ms", "pm", "president", "mayor", "minister", "judge"}


def _pack(lat, lon, precision, place):
    if lat is None or lon is None: return None
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): return None
    return {"lat": round(lat, 4), "lon": round(lon, 4), "precision": precision, "place": place}


def _turkey_food(text):
    words = [geo.nw(w) for w in geo.TOK.findall(text or "")]
    for i, w in enumerate(words):
        if w != "turkey": continue
        window = words[max(0, i - 3):i + 4]
        if any(x in _TURKEY_FOOD for x in window): return True
    return False


def _centroid(ch):
    G = geo.gaz()
    if ch.get("level") == "city":
        c = ch.get("city") or {}
        name = c.get("name") or ch.get("text") or ""
        st = (G.admin1.get(c.get("a1") or "") or {}).get("name")
        label = name + (", " + st if st else "")
        return _pack(c.get("lat"), c.get("lon"), "city", label.strip(", "))
    if ch.get("level") == "state":
        a = G.admin1.get(ch.get("a1") or "") or {}
        lab = a.get("label")
        if not lab: return None
        cc = (G.countries.get(ch.get("cc") or "") or {}).get("name")
        label = a.get("name") or ch.get("text") or ""
        if cc and cc not in label: label = f"{label}, {cc}"
        return _pack(lab[0], lab[1], "state", label)
    ctry = G.countries.get(ch.get("cc") or "") or {}
    lab = ctry.get("label")
    if not lab: return None
    return _pack(lab[0], lab[1], "country", ctry.get("name") or ch.get("text") or "")


def _prep(text):
    text = _OUTLET.sub(" ", text)
    text = _MASS.sub(" ", text)
    text = _NWS.sub(" ", text)          # the office city is not the event; the state fallback handles it
    text = _COAST.sub("in ", text)
    if _turkey_food(text): text = re.sub(r"\b[Tt]urkey\b", " ", text)
    return text


def _neighbor_person(name, text):
    """'Tucker Carlson' or 'Katie Hobbs': a one-word city beside another capitalized word."""
    if not name or " " in name.strip(): return False
    m = re.search(r"(?<![A-Za-z])([A-Z][a-zA-Z.'\-]*)\s+" + re.escape(name) + r"(?:\s+([A-Z][a-zA-Z.'\-]*))?", text)
    if not m:
        m = re.search(re.escape(name) + r"\s+([A-Z][a-zA-Z.'\-]*)", text)
        if not m: return False
        other = m.group(1)
        return geo.nw(other) not in _PLACE_WORD
    before, after = m.group(1), m.group(2)
    if before and geo.nw(before) == geo.nw(name): before = None
    for word in (before, after):
        if not word: continue
        if geo.nw(word) in _PLACE_WORD or geo.nw(word) in _TITLE_WORD: continue
        if word[0].isupper() and word.lower() != name.lower(): return True
    return False


def _named_us_states(text):
    """Full state names actually written in the text. 'Washington' only with State or County."""
    G = geo.gaz()
    found = set()
    for code, a in G.admin1.items():
        if not code.startswith("US.") or not a.get("label"): continue
        name = a.get("name") or ""
        if len(name) < 5: continue
        if name == "Washington":
            if re.search(r"\bWashington\s+State\b|\bstate of Washington\b|\bCounty,\s+Washington\b", text): found.add(code)
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", text): found.add(code)
    return found


def _from_gazetteer(text):
    primed = _prep(text)
    ex = geo.extract(primed)
    states = _named_us_states(text)
    acc = []
    for a in ex.get("acc") or []:
        if a.get("level") == "city" and geo.key_of(a.get("text") or "") in ("white house",): continue
        if a.get("level") == "city" and geo.nw(a.get("text") or "") in _CITY_BLOCK: continue
        if a.get("level") == "city" and _neighbor_person(a.get("text") or "", text): continue
        if a.get("level") == "city" and states:
            a1 = (a.get("city") or {}).get("a1")
            if a1 and a1 not in states and any(s.startswith("US.") for s in states): continue
        acc.append(a)
    ex = dict(ex, acc=acc)
    countries = {a.get("cc") for a in acc if a.get("cc")}
    if len(countries) >= 3: return None
    ch, _rc, _rt, _cands = geo.choose(ex)
    if not ch or ch.get("conf") == "low": return None
    if (ch.get("k") == "turkey") and not ch.get("cue"): return None
    if ch.get("level") == "city" and _neighbor_person(ch.get("text") or "", text): return None
    return _centroid(ch)


def _nws(text):
    """Issuing office, e.g. 'by NWS Norman OK'. City if that office city is unique in the state, else the state centroid."""
    m = _NWS.search(text or "")
    if not m: return None
    geo.gaz()
    postal = m.group(2)
    if postal not in geo.US_POSTAL: return None
    a1 = geo.US_POSTAL[postal]
    G = geo.gaz()
    office = m.group(1).strip()
    refs = G.idx.get(geo.key_of(office)) or []
    cities = []
    for kind, idx in refs:
        if kind != "city": continue
        c = G.city(idx)
        if c.get("a1") == a1: cities.append(c)
    state = (G.admin1.get(a1) or {}).get("name") or postal
    if len(cities) == 1 and cities[0].get("pop", 0) >= 20000:
        c = cities[0]
        return _pack(c["lat"], c["lon"], "city", f"{c['name']}, {state}")
    lab = (G.admin1.get(a1) or {}).get("label")
    if not lab: return None
    return _pack(lab[0], lab[1], "state", state)


def _region(text):
    folded = geo.fold(text or "").lower()
    hits = []
    for name, (lat, lon, label) in _REGIONS.items():
        if re.search(r"\b" + re.escape(name) + r"\b", folded): hits.append((name, lat, lon, label))
    if len(hits) != 1: return None
    _name, lat, lon, label = hits[0]
    return _pack(lat, lon, "region", label)


def infer(text):
    """-> {lat, lon, precision, place} or None. None means we are not sure."""
    text = (text or "").strip()
    if not text or _NOT_A_PLACE.search(text) and len(text) < 48: return None
    hit = _from_gazetteer(text)
    if hit: return hit
    hit = _nws(text)
    if hit: return hit
    if re.search(r"\bWhite House\b", text):
        return _pack(38.8977, -77.0365, "city", "Washington, District of Columbia")
    if re.search(r"\bWashington\s+State\b|\bstate of Washington\b|\bCounty,\s+Washington\b", text):
        geo.gaz()
        a1 = geo.US_POSTAL.get("WA")
        lab = (geo.gaz().admin1.get(a1) or {}).get("label") if a1 else None
        if lab: return _pack(lab[0], lab[1], "state", "Washington, United States")
    return _region(text)


def story_text(title, location="", brief=""):
    """The words worth reading: headline, a real location field, and a WHERE line that names a place."""
    parts = []
    if title: parts.append(title)
    loc = (location or "").strip()
    if loc.count(";") >= 2: loc = ""
    if loc and not _NOT_A_PLACE.search(loc): parts.append(loc)
    m = re.search(r"WHERE:\s*(.+?)(?:\s+WHEN:|$)", brief or "", re.S)
    if m:
        where = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        # NWS zone lists ("Orange; Washington; Scott; ...") are county names, not a sentence.
        if where.count(";") >= 2: where = ""
        if where and not _NOT_A_PLACE.search(where): parts.append(where)
    return "\n".join(parts)
