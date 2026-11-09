"""Offline place inference for the signal map.

Reads the bundled gazetteer already shipped with the heat map (heatmap_data/: countries,
admin1, cities). No network calls, no API keys, no database writes. A story is placed only
when one place wins cleanly. Ambiguous names (Georgia, Turkey-the-bird, person names) are skipped.
"""
import os, re
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
               "africa", "asia", "europe", "america", "pacific", "atlantic", "arctic", "caribbean", "midwest",
               "bank", "senate", "congress", "parliament", "ministry", "police", "army", "navy", "airport",
               "hospital", "clinic", "school", "church", "prison", "jail", "market", "station", "bridge",
               "failure", "collapse", "protest", "protests", "arrest", "impeach", "impeaches", "impeached"}
_MASS = re.compile(r"\bMass(?=\s+(?:protests?|shootings?|casualt\w*|graves?|arrests?|demonstrations?|layoffs?|exodus|migration|killings?|deaths?|funerals?|graves?))", re.I)
_PLACE_WORD = {"county", "parish", "city", "state", "province", "region", "river", "island", "islands", "bay", "gulf",
               "coast", "valley", "oblast", "prefecture", "district", "beach", "mountains", "mountain"}
_TITLE_WORD = {"gov", "governor", "gen", "sen", "senator", "rep", "dr", "mr", "mrs", "ms", "pm", "president", "mayor", "minister", "judge"}


def _pack(lat, lon, precision, place, cc=""):
    if lat is None or lon is None: return None
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): return None
    # Country and broad-region centroids are approximate. A city, base or state is the place named.
    approximate = precision in ("country", "region")
    return {"lat": round(lat, 4), "lon": round(lon, 4), "precision": precision, "place": place,
            "cc": cc or "", "approximate": approximate}


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
        return _pack(c.get("lat"), c.get("lon"), "city", label.strip(", "), c.get("cc") or ch.get("cc") or "")
    if ch.get("level") == "state":
        a = G.admin1.get(ch.get("a1") or "") or {}
        lab = a.get("label")
        if not lab: return None
        iso = ch.get("cc") or (ch.get("a1") or "").split(".")[0]
        cname = (G.countries.get(iso) or {}).get("name")
        label = a.get("name") or ch.get("text") or ""
        if cname and cname not in label: label = f"{label}, {cname}"
        return _pack(lab[0], lab[1], "state", label, iso or "")
    iso = ch.get("cc") or ""
    ctry = G.countries.get(iso) or {}
    lab = ctry.get("label")
    if not lab: return None
    return _pack(lab[0], lab[1], "country", ctry.get("name") or ch.get("text") or "", iso)


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
        return _pack(c["lat"], c["lon"], "city", f"{c['name']}, {state}", "US")
    lab = (G.admin1.get(a1) or {}).get("label")
    if not lab: return None
    return _pack(lab[0], lab[1], "state", state, "US")


def _region(text):
    folded = geo.fold(text or "").lower()
    hits = []
    for name, (lat, lon, label) in _REGIONS.items():
        if re.search(r"\b" + re.escape(name) + r"\b", folded): hits.append((name, lat, lon, label))
    if len(hits) != 1: return None
    _name, lat, lon, label = hits[0]
    return _pack(lat, lon, "region", label)


# Conflict and military places, including spellings the GeoNames extract misses.
# level, lat, lon, cc, label. These win over a same-name city in the wrong country (Odessa, Texas).
_CURATED = {
    "kyiv": ("city", 50.4547, 30.5238, "UA", "Kyiv"),
    "kiev": ("city", 50.4547, 30.5238, "UA", "Kyiv"),
    "kharkiv": ("city", 49.9818, 36.2548, "UA", "Kharkiv"),
    "odesa": ("city", 46.4857, 30.7438, "UA", "Odesa"),
    "odessa": ("city", 46.4857, 30.7438, "UA", "Odesa"),
    "donetsk": ("city", 48.023, 37.8022, "UA", "Donetsk"),
    "kursk": ("city", 51.7269, 36.1846, "RU", "Kursk"),
    "zaporizhzhia": ("city", 47.8517, 35.1171, "UA", "Zaporizhzhia"),
    "zaporizhzhya": ("city", 47.8517, 35.1171, "UA", "Zaporizhzhia"),
    "zaporizhia": ("city", 47.8517, 35.1171, "UA", "Zaporizhzhia"),
    "zaporizhzhia npp": ("facility", 47.5062, 34.5856, "UA", "Zaporizhzhia NPP"),
    "zaporizhzhia nuclear power plant": ("facility", 47.5062, 34.5856, "UA", "Zaporizhzhia NPP"),
    "enerhodar": ("city", 47.4905, 34.662, "UA", "Enerhodar"),
    "gaza": ("city", 31.5016, 34.4667, "PS", "Gaza"),
    "gaza city": ("city", 31.5016, 34.4667, "PS", "Gaza City"),
    "rafah": ("city", 31.2972, 34.2436, "PS", "Rafah"),
    "khan younis": ("city", 31.3402, 34.3063, "PS", "Khan Younis"),
    "khan yunis": ("city", 31.3402, 34.3063, "PS", "Khan Younis"),
    "beirut": ("city", 33.8933, 35.5016, "LB", "Beirut"),
    "tehran": ("city", 35.6944, 51.4215, "IR", "Tehran"),
    "tel aviv": ("city", 32.0809, 34.7806, "IL", "Tel Aviv"),
    "bandar abbas": ("city", 27.1865, 56.2808, "IR", "Bandar Abbas"),
    "hodeidah": ("city", 14.7978, 42.9545, "YE", "Hodeidah"),
    "al hudaydah": ("city", 14.7978, 42.9545, "YE", "Hodeidah"),
    "strait of hormuz": ("region", 26.6, 56.3, "", "Strait of Hormuz"),
    "taiwan strait": ("region", 24.5, 119.5, "", "Taiwan Strait"),
    "red sea": ("region", 20.0, 38.5, "", "Red Sea"),
    "south lebanon": ("region", 33.27, 35.38, "LB", "South Lebanon"),
    "golan": ("region", 33.0, 35.75, "", "Golan"),
    "golan heights": ("region", 33.0, 35.75, "", "Golan Heights"),
    "gulf of oman": ("region", 24.5, 58.5, "", "Gulf of Oman"),
    "komyshuvakha": ("city", 47.48, 35.53, "UA", "Komyshuvakha"),
}
# A demonym plus a base, territory or waters is the country, when no city was named.
_DEMONYM_PLACE = {
    "colombian": ("CO", "Colombia", 4.5709, -74.2973),
    "brazilian": ("BR", "Brazil", -14.235, -51.9253),
    "french": ("FR", "France", 46.2276, 2.2137),
    "polish": ("PL", "Poland", 51.9194, 19.1451),
    "lebanese": ("LB", "Lebanon", 33.8547, 35.8623),
    "yemeni": ("YE", "Yemen", 15.5527, 48.5164),
    "syrian": ("SY", "Syria", 34.8021, 38.9968),
    "iraqi": ("IQ", "Iraq", 33.2232, 43.6793),
    "paraguayan": ("PY", "Paraguay", -23.4425, -58.4438),
    "chilean": ("CL", "Chile", -35.6751, -71.543),
    "argentine": ("AR", "Argentina", -38.4161, -63.6167),
    "argentinian": ("AR", "Argentina", -38.4161, -63.6167),
    "ukrainian": ("UA", "Ukraine", 48.3794, 31.1656),
    "russian": ("RU", "Russia", 61.524, 105.3188),
    "israeli": ("IL", "Israel", 31.0461, 34.8516),
    "palestinian": ("PS", "Palestine", 31.9522, 35.2332),
    "iranian": ("IR", "Iran", 32.4279, 53.688),
}
# Country names that are also people or US states. A bare mention is not a place.
_AMBIG_COUNTRY = {"georgia", "jordan", "chad", "turkey", "guinea", "niger"}
_CUES = {"in", "on", "at", "near", "outside", "into", "over", "around", "from",
         "strikes", "struck", "strike", "attacks", "attack", "attacked", "bombed", "bombing"}
_DIR = {"southern", "northern", "eastern", "western", "central", "south", "north", "east", "west"}
_PLACES = {"t": 0.0, "v": None}

def _gazetteer():
    """Compact GeoNames extract (signal_places.json.gz) plus the curated list."""
    import gzip, json, time
    now = time.time()
    if _PLACES["v"] is not None and now - _PLACES["t"] < 3600: return _PLACES["v"]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal_places.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    _PLACES.update(t=now, v=data)
    return data

def _tokens(text):
    text = geo.fold(text or "")
    out = []
    for m in geo.TOK.finditer(text):
        raw = m.group(0)
        out.append((geo.nw(raw), raw[0].isupper() or raw.isupper()))
    return out

def _from_text(text, prefer_cc=None):
    """Most specific place the story actually names. City and base beat a country mention."""
    raw = _OUTLET.sub(" ", text or "")
    raw = _COAST.sub("in ", raw)
    if _turkey_food(raw): raw = re.sub(r"\b[Tt]urkey\b", " ", raw)
    if re.search(r"\bTexas\b|\bTX\b", raw) and re.search(r"\bOdessa\b", raw):
        return _pack(31.8457, -102.3676, "city", "Odessa, Texas", "US")
    toks = _tokens(raw)
    if not toks: return None
    G = _gazetteer()
    cities, admin, countries = G["c"], G["a"], G["k"]
    norms = [t[0] for t in toks]
    caps = [t[1] for t in toks]
    # Countries / demonyms named in the story — used to keep city hits inside the right border.
    named_cc = set(prefer_cc or []) if isinstance(prefer_cc, (list, set, tuple)) else ({prefer_cc} if prefer_cc else set())
    named_cc |= {countries[k][2] for k in countries if k in norms}
    for word, d in _DEMONYM_PLACE.items():
        if re.search(r"\b" + word + r"\w*\b", raw, re.I):
            named_cc.add(d[0])
    hits = []
    i = 0
    while i < len(norms):
        found = None
        for n in (6, 5, 4, 3, 2, 1):
            if i + n > len(norms): continue
            key = " ".join(norms[i:i + n])
            if key in _CURATED or key in cities or key in admin or key in countries:
                prev = norms[i - 1] if i else ""
                cue = prev in _CUES
                if not (caps[i] or cue): continue
                found = (n, key, cue)
                break
        if not found:
            i += 1
            continue
        n, key, cue = found
        i += n
        if key in _CITY_BLOCK: continue
        if key in _AMBIG_COUNTRY and not cue and key not in _CURATED: continue
        if key == "georgia" and not re.search(r"\b(?:Tbilisi|state of Georgia|Georgia,? USA|US state)\b", raw): continue
        level = lat = lon = cc = label = pop = None
        if key in _CURATED and not (key == "odessa" and re.search(r"\bTexas\b", raw)):
            level, lat, lon, cc, label = _CURATED[key]
            pop = 5000000
        elif key in cities:
            cands = cities[key]
            if key == "rafah":
                cands = [c for c in cands if c[2] == "PS"] or cands
            ctx = set(named_cc) or {countries[k][2] for k in countries if k in norms}
            pool = [c for c in cands if c[2] in ctx] if ctx else list(cands)
            if not pool and named_cc:
                # City name exists, but not inside the story's country — skip, do not plot abroad.
                continue
            if not pool: pool = list(cands)
            pool = sorted(pool, key=lambda c: -c[3])
            if len(pool) > 1 and not (pool[0][3] >= max(200000, 3 * pool[1][3])): continue
            lat, lon, cc, pop, label = pool[0]
            if key in admin and pop < 80000 and admin[key][2] == "US" and cc != "US":
                lat, lon, cc, label = admin[key]
                level, pop = "state", 0
            else:
                level = "city"
        elif key in admin:
            lat, lon, cc, label = admin[key]
            level, pop = "state", 0
            if key in countries and key in _AMBIG_COUNTRY: continue
            if named_cc and cc and cc not in named_cc: continue
        elif key in countries:
            lat, lon, cc, label = countries[key]
            level, pop = "country", 0
        if level is None: continue
        # Person names ("President Santiago Peña") are not cities.
        if level == "city" and _neighbor_person(label or key, raw): continue
        if level == "city" and _neighbor_person(key.title(), raw): continue
        prev = norms[i - n - 1] if i - n - 1 >= 0 else ""
        if level == "city" and prev and prev not in _CUES and prev not in _DIR and prev not in _PLACE_WORD and prev not in _TITLE_WORD:
            if i - n - 1 >= 0 and caps[i - n - 1] and prev not in countries and prev not in cities and prev not in admin:
                continue
        hits.append({"level": level, "lat": lat, "lon": lon, "cc": cc, "place": label, "pop": pop or 0, "cue": cue, "key": key})
    if not hits:
        for word, d in _DEMONYM_PLACE.items():
            if re.search(r"\b" + word + r"\w*\s+(?:\w+\s+){0,2}(?:military\s+)?(?:base|territory|soil|waters|president|leader|government)\b", raw, re.I):
                return _pack(d[2], d[3], "country", d[1], d[0])
        return None
    rank = {"facility": 5, "city": 4, "state": 3, "region": 2, "country": 1}
    # Prefer a city/state inside a named country when one exists (Paraguay ≠ Santiago, Chile).
    # Do NOT drop a clearly named foreign city when the other country is only an actor
    # ("Russia struck Kyiv" must stay Kyiv).
    specific = [h for h in hits if rank[h["level"]] >= 2]
    if named_cc:
        in_named = [h for h in specific if h.get("cc") in named_cc]
        if in_named: specific = in_named
    if specific:
        specific.sort(key=lambda h: (rank[h["level"]] + (3 if h["cue"] else 0), h["pop"]), reverse=True)
        best = specific[0]
        return _pack(best["lat"], best["lon"], best["level"], best["place"], best["cc"])
    # Two+ countries and no city/state → do not guess which one (Russia and Ukraine …).
    country_hits = [h for h in hits if h["level"] == "country"]
    if named_cc:
        country_hits = [h for h in country_hits if h.get("cc") in named_cc] or country_hits
    country_ccs = {h.get("cc") for h in country_hits if h.get("cc")}
    if len(country_ccs) > 1:
        cued = [h for h in country_hits if h["cue"]]
        cued_cc = {h["cc"] for h in cued if h.get("cc")}
        if len(cued_cc) != 1: return None
        h = cued[0]
        if h["key"] in _AMBIG_COUNTRY and not h["cue"]: return None
        return _pack(h["lat"], h["lon"], "country", h["place"], h["cc"])
    if len(country_ccs) == 1:
        h = country_hits[0]
        if h["key"] in _AMBIG_COUNTRY and not h["cue"]: return None
        return _pack(h["lat"], h["lon"], "country", h["place"], h["cc"])
    ccs = {}
    for h in hits:
        ccs.setdefault(h["cc"] or h["key"], []).append(h)
    if len(ccs) != 1:
        cued = [h for h in hits if h["cue"]]
        cued_cc = {h["cc"] for h in cued}
        if len(cued_cc) != 1: return None
        h = cued[0]
        if h["key"] in _AMBIG_COUNTRY and not h["cue"]: return None
        return _pack(h["lat"], h["lon"], h["level"] if h["level"] != "city" else "country", h["place"], h["cc"])
    h = hits[0]
    if h["key"] in _AMBIG_COUNTRY and not h["cue"]: return None
    return _pack(h["lat"], h["lon"], "country", h["place"], h["cc"])


def named_countries(text):
    """ISO2 codes the story clearly names (multi-word countries + demonyms). Empty if none."""
    raw = _OUTLET.sub(" ", text or "")
    if _turkey_food(raw): raw = re.sub(r"\b[Tt]urkey\b", " ", raw)
    G = _gazetteer()
    countries = G["k"]
    toks = _tokens(raw)
    norms = [t[0] for t in toks]
    caps = [t[1] for t in toks]
    out = []
    seen = set()
    i = 0
    while i < len(norms):
        found = None
        for n in (6, 5, 4, 3, 2, 1):
            if i + n > len(norms): continue
            key = " ".join(norms[i:i + n])
            if key not in countries: continue
            prev = norms[i - 1] if i else ""
            cue = prev in _CUES
            if not (caps[i] or cue): continue
            if key in _AMBIG_COUNTRY and not cue:
                if key == "georgia" and not re.search(r"\b(?:Tbilisi|state of Georgia|Georgia,? USA|US state)\b", raw):
                    continue
                if key != "georgia":
                    continue
            found = (n, key)
            break
        if not found:
            i += 1
            continue
        n, key = found
        i += n
        cc = countries[key][2]
        if cc and cc not in seen:
            seen.add(cc); out.append(cc)
    for word, d in _DEMONYM_PLACE.items():
        if re.search(r"\b" + word + r"\w*\b", raw, re.I) and d[0] not in seen:
            seen.add(d[0]); out.append(d[0])
    return out



def pip_country(lat, lon):
    """Natural Earth admin-0 ISO2 for a coordinate, or None."""
    try:
        cc, _a1 = geo.gaz().pip(float(lat), float(lon))
        return cc
    except Exception:
        return None


# Natural Earth admin-0 assigns some disputed places to a neighbour (Gaza→IL).
_PIP_ACCEPT = {
    "PS": {"PS", "IL"}, "IL": {"IL", "PS"},
    "TW": {"TW", "CN"}, "CN": {"CN", "TW"},
    "XK": {"XK", "RS"}, "RS": {"RS", "XK"},
    "EH": {"EH", "MA"}, "MA": {"MA", "EH"},
}

def in_country(lat, lon, cc):
    if not cc: return True
    got = pip_country(lat, lon)
    if not got: return True   # ocean / missing poly: do not reject
    got, cc = got.upper(), cc.upper()
    if got == cc: return True
    return got in _PIP_ACCEPT.get(cc, ())


_CAP_CACHE = {}

def capital_of(cc):
    """Capital city pack for a country, else the country centroid pack, else None."""
    cc = (cc or "").upper()
    if not cc: return None
    if cc in _CAP_CACHE: return _CAP_CACHE[cc]
    G = geo.gaz()
    ctry = G.countries.get(cc) or {}
    name = (ctry.get("capital") or "").strip()
    hit = None
    if name:
        key = geo.key_of(name)
        # Prefer PPLC from heatmap cities.json
        for row in G.cities:
            if row[4] != cc: continue
            if geo.key_of(row[0]) == key or geo.key_of(row[1] or "") == key or key in {geo.key_of(a) for a in (row[8] or [])}:
                if row[7] == "PPLC" or hit is None:
                    hit = _pack(row[2], row[3], "city", f"{row[0]}, {ctry.get('name') or cc}", cc)
                    if row[7] == "PPLC": break
    if hit is None:
        lab = ctry.get("label")
        if lab:
            hit = _pack(lab[0], lab[1], "country", ctry.get("name") or cc, cc)
    _CAP_CACHE[cc] = hit
    return hit


_CITIES_CACHE = {}

def cities_of(cc, min_pop=25000, limit=25):
    """Largest populated places inside a country (offline GeoNames extract).

    Drops cities Natural Earth admin-0 puts outside the border (Crimea/Sevastopol,
    El Paso edge cases) so country-only distribution never plots abroad.
    """
    cc = (cc or "").upper()
    if not cc: return []
    key = (cc, int(min_pop), int(limit))
    if key in _CITIES_CACHE: return _CITIES_CACHE[key]
    G = geo.gaz()
    cand = []
    for row in G.cities:
        if row[4] != cc: continue
        pop = int(row[6] or 0)
        if pop < min_pop: continue
        cand.append((pop, float(row[2]), float(row[3]), row[0]))
    cand.sort(reverse=True)
    # PIP only the largest candidates until we have `limit` keepers (border/disputed drops are rare).
    keep = []
    for pop, lat, lon, name in cand:
        if not in_country(lat, lon, cc): continue
        keep.append({"lat": lat, "lon": lon, "place": name, "pop": pop, "cc": cc})
        if len(keep) >= limit: break
    _CITIES_CACHE[key] = keep
    return keep


def place_in_country(cc, story_id="", index=0, total=1):
    """Country-only placement: capital when alone; otherwise a distinct real city (deterministic)."""
    cc = (cc or "").upper()
    if not cc: return None
    cities = cities_of(cc, min_pop=15000, limit=40)
    if not cities:
        return capital_of(cc)
    if total <= 1:
        cap = capital_of(cc)
        if cap and cap.get("precision") == "city":
            return dict(cap, approximate=True, precision="country")
        c0 = cities[0]
        return _pack(c0["lat"], c0["lon"], "country", f"{c0['place']}, {cc}", cc)
    import hashlib
    # Round-robin by index so N stories get N distinct cities when the pool allows it.
    pool_n = min(len(cities), max(int(total), 8))
    pool = cities[:pool_n]
    slot = int(index) % len(pool)
    if int(total) > len(pool):
        digest = hashlib.sha1(f"{cc}:{story_id}:{index}".encode()).hexdigest()
        slot = int(digest[:8], 16) % len(pool)
    c0 = pool[slot]
    return _pack(c0["lat"], c0["lon"], "country", f"{c0['place']}, {cc}", cc)


def _verify_or_repair(hit, text, prefer_cc=None):
    """PIP-check the hit against the country that owns the place. Re-geocode on failure; else None."""
    if not hit: return None
    if hit.get("precision") == "region" and not hit.get("cc"):
        return hit
    named = named_countries(text)
    # Specific places keep their own country (Kyiv stays UA even when Russia is named).
    # Country-only hits, or ambiguous ones, use the story's named country.
    if hit.get("precision") in ("city", "facility", "state") and hit.get("cc"):
        expected = hit["cc"]
    elif prefer_cc:
        expected = prefer_cc
    elif hit.get("cc") and (not named or hit["cc"] in named):
        expected = hit["cc"]
    elif len(named) == 1:
        expected = named[0]
    else:
        expected = hit.get("cc")
    if not expected:
        if hit.get("precision") in ("city", "facility", "state"):
            if hit.get("cc"):
                return hit if in_country(hit["lat"], hit["lon"], hit["cc"]) else None
            # NWS / gazetteer hits with no ISO yet: keep and fill cc from Natural Earth when possible.
            pip = pip_country(hit["lat"], hit["lon"])
            return dict(hit, cc=pip or "") if pip or hit.get("precision") in ("city", "state") else None
        return hit if hit.get("precision") == "region" else None
    if in_country(hit["lat"], hit["lon"], expected):
        if not hit.get("cc"): hit = dict(hit, cc=expected)
        return hit
    # Wrong country for this hit: if the story names one country, snap to that country's capital.
    # If the hit was a specific place that PIP rejected, drop it (do not silently move Kyiv to Russia).
    if hit.get("precision") in ("city", "facility", "state"):
        # One more try: a same-name place inside expected / prefer / named.
        target = prefer_cc or (named[0] if len(named) == 1 else None)
        if target and target != expected:
            retry = _from_text(text, prefer_cc=target)
            if retry and in_country(retry["lat"], retry["lon"], retry.get("cc") or target):
                # Keep the place's own cc (Gaza stays PS even when Israel is the actor).
                return retry
        return None
    target = prefer_cc or (named[0] if len(named) == 1 else expected)
    retry = _from_text(text, prefer_cc=target)
    if retry and in_country(retry["lat"], retry["lon"], target):
        return dict(retry, cc=target)
    cap = capital_of(target)
    if cap and in_country(cap["lat"], cap["lon"], target):
        label = (geo.gaz().countries.get(target) or {}).get("name") or target
        return _pack(cap["lat"], cap["lon"], "country", label, target)
    return None


def infer(text, prefer_cc=None):
    """-> {lat, lon, precision, place, cc, approximate} or None. None means we are not sure."""
    text = (text or "").strip()
    if not text or _NOT_A_PLACE.search(text) and len(text) < 48: return None
    hit = _nws(text)
    if hit: return _verify_or_repair(hit, text, prefer_cc)
    hit = _from_text(text, prefer_cc=prefer_cc)
    if hit:
        fixed = _verify_or_repair(hit, text, prefer_cc)
        if fixed: return fixed
    hit = _from_gazetteer(text)
    if hit:
        fixed = _verify_or_repair(hit, text, prefer_cc)
        if fixed: return fixed
    if re.search(r"\bWhite House\b", text):
        hit = _pack(38.8977, -77.0365, "city", "Washington, District of Columbia", "US")
        return _verify_or_repair(hit, text, prefer_cc) or hit
    if re.search(r"\bWashington\s+State\b|\bstate of Washington\b|\bCounty,\s+Washington\b", text):
        geo.gaz()
        a1 = geo.US_POSTAL.get("WA")
        lab = (geo.gaz().admin1.get(a1) or {}).get("label") if a1 else None
        if lab:
            hit = _pack(lab[0], lab[1], "state", "Washington, United States", "US")
            return _verify_or_repair(hit, text, prefer_cc) or hit
    hit = _region(text)
    if hit: return hit
    # Last resort: a single named country → capital (still PIP-checked).
    named = named_countries(text)
    if len(named) == 1:
        cap = capital_of(named[0])
        if cap: return dict(cap, approximate=True, precision="country")
    return None


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
