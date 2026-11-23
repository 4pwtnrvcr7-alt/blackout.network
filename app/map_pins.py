"""Which stories may appear as pins on the homepage map, /map, and any other story map.

Nov 23 2026 (pt1761u, pt1762u): only a specific, named location is a pin. Stories with no
location, a country-centroid-only location, a low-confidence or ambiguous match, a pin on
water, or a location that contradicts the headline stay in the lists, not on the map.

A city, point, or facility pin stays at that level only when the headline names the city
(including offset forms like "38 km NE of Calama" and close spelling or transliteration).
If the city is not named but the headline names a consistent containing county or state
(or equivalent admin-1 place), the pin is moved to that level. A country name alone is
not enough: country centroids stay off the map.

Does not geocode, write a database, or touch scanner scoring.
"""
import re, unicodedata
from difflib import SequenceMatcher

SPECIFIC = {"point", "city", "county", "facility", "state"}
CITY_PREC = {"point", "city", "facility"}
DROP_PREC = {"country", "region"}
DROP_TIER = {"global", "region", "approx"}
LOW_CONF = {"low", "weak", "ambiguous"}
HOW_BAD = ("several", "ambiguous", "nationality", "pending", "fallback", "country centre",
           "country center", "country-level", "spread", "place_in_country")
STOP = {"united", "states", "usa", "us", "uk", "the", "of", "and", "county", "parish", "city",
        "province", "region", "state", "district", "republic", "kingdom", "north", "south",
        "east", "west", "northern", "southern", "eastern", "western"}
ADMIN_SUFFIX = {"county", "parish", "borough", "oblast", "governorate", "prefecture",
                "province", "region", "state", "territory", "republic", "emirate",
                "department", "prefecture", "municipality", "district", "strip"}
# Too generic to count as evidence that a particular admin was named.
ADMIN_GENERIC = ADMIN_SUFFIX | STOP | {
    "more", "costa", "litoral", "littoral", "coast", "coastal", "area", "areas",
    "zone", "zones", "warning", "channel", "central", "orange", "yellow", "red",
    "green", "event", "events", "north", "south", "east", "west", "northern",
    "southern", "eastern", "western", "upper", "lower", "inner", "outer",
}

# "38 km NE of Calama" / "33 km al NE de Calama" / "9 km NNE of Carhuamayo"
_OFFSET = re.compile(
    r"^\s*\d+(?:[.,]\d+)?\s*(?:km|mi|miles?)\s+"
    r"(?:al\s+)?(?:nne|nnw|sse|ssw|ene|ese|wnw|wsw|ne|nw|se|sw|n|s|e|w)\s+"
    r"(?:de\s+|of\s+|del?\s+)?(.+)$",
    re.I,
)
_MORE = re.compile(r"\s*\+\d+\s*more\s*$", re.I)

_GAZ = {"ok": False, "tried": False, "admin": [], "country_names": set(), "cc_by_name": {},
        "postal": {}, "name": {}}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for a, b in (("’", "'"), ("‘", "'"), ("ʻ", "'"), ("ʼ", "'"), ("`", "'")):
        s = s.replace(a, b)
    s = re.sub(r"'s\b", " ", s, flags=re.I)
    s = s.replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _fold_spell(s):
    """Light transliteration folds (Kryvyy/Kryvyi, Khan Younis/Yunis, Kiev/Kyiv, Jazan/Jizan)."""
    s = _norm(s)
    s = s.replace("yy", "yi")
    s = s.replace("younis", "yunis")
    s = s.replace("jabalia", "jabalya")
    s = s.replace("kiev", "kyiv")
    s = s.replace("jizan", "jazan")
    s = s.replace("basrah", "basra")
    return s


def _edits(a, b):
    if a == b:
        return 0
    if not a or not b or abs(len(a) - len(b)) > 1:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _has(text, phrase):
    t, p = _norm(text), _norm(phrase)
    if not p or len(p) < 2:
        return False
    return f" {p} " in f" {t} "


def _names_close(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b or _fold_spell(a) == _fold_spell(b):
        return True
    fa, fb = _fold_spell(a), _fold_spell(b)
    if fa == fb:
        return True
    if min(len(fa), len(fb)) >= 5 and _edits(fa, fb) <= 1:
        return True
    if min(len(a), len(b)) < 6:
        return False
    return SequenceMatcher(None, fa, fb).ratio() >= 0.85


def phrase_in_text(name, text):
    """True when a place name appears in text, allowing close spelling and a truncated tail."""
    nn, nt = _norm(name), _norm(text)
    if not nn or not nt:
        return False
    if len(nn) >= 3 and (f" {nn} " in f" {nt} " or f" {_fold_spell(nn)} " in f" {_fold_spell(nt)} "):
        return True
    ntoks, ttoks = nn.split(), nt.split()
    n = len(ntoks)
    if not n or not ttoks:
        return False
    # 2-letter postal / short codes: exact token only
    if n == 1 and len(nn) <= 3:
        return nn in ttoks
    for i in range(len(ttoks) - n + 1):
        window = " ".join(ttoks[i:i + n])
        if _names_close(nn, window):
            return True
    if n == 1 and len(nn) >= 6:
        if any(_names_close(nn, t) for t in ttoks if len(t) >= 6):
            return True
    # Truncated headline (e.g. "Fort Lauder" for "Fort Lauderdale")
    if n >= 1 and len(ttoks) >= n and len(ntoks[-1]) >= 5:
        head_ok = n == 1 or ttoks[-(n):-(1)] == ntoks[:-1] or _norm(" ".join(ttoks[-(n):-1])) == _norm(" ".join(ntoks[:-1]))
        last = ttoks[-1]
        if head_ok and 5 <= len(last) < len(ntoks[-1]) and ntoks[-1].startswith(last):
            return True
        # also search earlier windows that end mid-word
        for i in range(len(ttoks) - n + 1):
            if n > 1 and ttoks[i:i + n - 1] != ntoks[:-1]:
                continue
            last = ttoks[i + n - 1]
            if 5 <= len(last) < len(ntoks[-1]) and ntoks[-1].startswith(last):
                return True
    return False


def _locality_head(part):
    p = (part or "").strip()
    p = _MORE.sub("", p).strip()
    if ":" in p and not p.lower().startswith("http"):
        after = p.split(":", 1)[1].strip()
        if after:
            p = after
    m = _OFFSET.match(p)
    if m:
        p = m.group(1).strip()
    return p


def _groups(place):
    return [g.strip() for g in (place or "").split(";") if g.strip()]


def _parts(group):
    out = []
    for p in group.split(","):
        p = _MORE.sub("", p).strip()
        if p:
            out.append(p)
    return out


def _leading_phrases(name):
    """Full locality, then trailing tokens dropped, so 'San Francisco Bay ...' can match 'San Francisco'."""
    toks = _norm(name).split()
    out = []
    for i in range(len(toks), 0, -1):
        phrase = " ".join(toks[:i])
        significant = [t for t in toks[:i] if t not in STOP and len(t) >= 4]
        if not significant:
            continue
        if i == len(toks) or i >= 2 or (i == 1 and len(toks[0]) >= 8):
            out.append(phrase)
    return out


def _admin_short_names(name):
    """Significant tokens of an admin label, e.g. 'Gaza' from 'Gaza Strip'."""
    toks = _norm(name).split()
    out = []
    for t in toks:
        if t not in ADMIN_GENERIC and len(t) >= 4:
            out.append(t)
    return out


def locality_names(place):
    """City / locality strings that count as 'the city' for a pin."""
    names = []
    for group in _groups(place):
        parts = _parts(group)
        if not parts:
            continue
        head = _locality_head(parts[0])
        if head:
            names.append(head)
            # Multi-area lists after a leading colon: "Vrancea, Vâlcea, Sibiu"
            if ":" in parts[0]:
                for p in parts[1:]:
                    p = _MORE.sub("", p).strip()
                    if p:
                        names.append(p)
        # Alternate spelling sitting in the next field (Zaporizhzhya, Zaporizhzhia, Ukraine)
        if len(parts) >= 3:
            mid = parts[1].strip()
            if mid and _names_close(_locality_head(parts[0]), mid):
                names.append(mid)
    seen, out = set(), []
    for n in names:
        k = _norm(n)
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def place_tokens(place):
    tokens = []
    for part in (place or "").split(","):
        p = _norm(part)
        if not p:
            continue
        for w in p.split():
            if w not in STOP and len(w) >= 4:
                tokens.append(w)
        if p not in STOP and len(p) >= 3:
            tokens.append(p)
    return tokens


def city_named_in_headline(title, place):
    title = title or ""
    for name in locality_names(place):
        if phrase_in_text(name, title):
            return True
        for phrase in _leading_phrases(name):
            if phrase != _norm(name) and phrase_in_text(phrase, title):
                return True
    return False


def _load_gaz():
    if _GAZ["tried"]:
        return _GAZ
    _GAZ["tried"] = True
    try:
        import geo
        G = geo.gaz()
    except Exception:
        return _GAZ
    admin = []
    postal = {}
    by_name = {}
    for code, a in (G.admin1 or {}).items():
        lab = a.get("label")
        if not (isinstance(lab, (list, tuple)) and len(lab) >= 2):
            continue
        cc = (code.split(".", 1)[0] if "." in code else "") or ""
        names = [a.get("name"), a.get("ascii"), a.get("postal")] + list(a.get("alts") or [])
        rec = {"code": code, "cc": cc, "name": a.get("name") or "", "lat": float(lab[0]),
               "lon": float(lab[1]), "type": (a.get("type") or ""), "postal": (a.get("postal") or ""),
               "alts": [n for n in names if n]}
        admin.append(rec)
        for n in names:
            k = _norm(n)
            if not k:
                continue
            by_name.setdefault(k, []).append(rec)
            if rec["postal"] and cc == "US":
                postal[_norm(rec["postal"])] = rec
    country_names, cc_by_name = set(), {}
    for code, c in (G.countries or {}).items():
        names = [c.get("name"), c.get("ascii")] + list(c.get("ne_names") or []) + list(c.get("alts") or [])
        for n in names:
            k = _norm(n)
            if k:
                country_names.add(k)
                cc_by_name.setdefault(k, set()).add(code)
    _GAZ.update(ok=True, admin=admin, country_names=country_names, cc_by_name=cc_by_name,
                postal=postal, name=by_name)
    return _GAZ


def _looks_like_country(part, cc=""):
    k = _norm(part)
    if not k:
        return False
    if k in {"united states", "usa", "u s", "uk", "united kingdom", "great britain",
             "palestinian territory", "palestine", "russia", "iran", "ukraine", "china",
             "germany", "france", "libya", "chile", "peru", "saudi arabia", "north korea",
             "south korea", "syria", "iraq", "israel", "egypt", "turkey", "pakistan",
             "india", "japan", "mexico", "canada", "brazil", "australia", "italy", "spain",
             "poland", "sweden", "switzerland", "romania", "the gambia", "gambia"}:
        return True
    gaz = _load_gaz()
    if k in gaz["country_names"]:
        # "Georgia" is a country and a US state. Not a country when the row is US and a later
        # part already says United States, or when cc is US and this is the middle part.
        if k == "georgia" and (cc or "").upper() == "US":
            return False
        return True
    return False


def _looks_like_admin(part):
    toks = _norm(part).split()
    if not toks:
        return False
    if toks[-1] in ADMIN_SUFFIX:
        return True
    if len(toks) >= 2 and toks[-1] in {"of"}:  # "Republic of Tatarstan" handled via gaz
        return False
    return False


def _admin_precision(rec):
    typ = (rec.get("type") or "").lower()
    if any(s in typ for s in ("county", "parish", "borough")):
        return "county"
    return "state"


def _country_label(cc):
    gaz = _load_gaz()
    if not gaz["ok"] or not cc:
        return ""
    try:
        import geo
        nm = (geo.gaz().countries.get(cc) or {}).get("name") or ""
        return nm
    except Exception:
        return ""


def _lookup_admin(part, cc=""):
    gaz = _load_gaz()
    if not gaz["ok"]:
        return None
    k = _norm(part)
    if not k:
        return None
    cc = (cc or "").upper()
    hits = list(gaz["name"].get(k) or [])
    if len(k) <= 3 and k in gaz["postal"]:
        hits = [gaz["postal"][k]] + hits
    if cc:
        scoped = [h for h in hits if h["cc"] == cc]
        if scoped:
            hits = scoped
    # unique by code
    uniq = {}
    for h in hits:
        uniq[h["code"]] = h
    hits = list(uniq.values())
    if len(hits) == 1:
        return hits[0]
    return None


def _place_cc(place, cc=""):
    if cc:
        return (cc or "").upper()
    gaz = _load_gaz()
    for group in _groups(place):
        parts = _parts(group)
        if not parts:
            continue
        last = _norm(parts[-1])
        codes = gaz["cc_by_name"].get(last) or set()
        if len(codes) == 1:
            return next(iter(codes))
        if last in {"united states", "usa", "u s"}:
            return "US"
    return ""


def _admin_mentioned(part, title, cc=""):
    """True when this county/state (or a short form / postal / alias) is named in the headline."""
    if not part or not title:
        return False
    if phrase_in_text(part, title):
        return True
    if len(_norm(part)) <= 3 and _norm(part) in _norm(title).split():
        return True
    for phrase in _leading_phrases(part) + _admin_short_names(part):
        if phrase and phrase_in_text(phrase, title):
            return True
    rec = _lookup_admin(part, cc)
    if not rec:
        return False
    for alt in rec.get("alts") or []:
        if not alt:
            continue
        if phrase_in_text(alt, title):
            return True
        k = _norm(alt)
        if len(k) <= 3 and k in _norm(title).split():
            return True
        # 2-letter USPS as a stand-alone capital token (NWS Miami FL), not "in"/"or".
        postal = (rec.get("postal") or "")
        if postal and len(postal) <= 3 and re.search(
                rf'(?:^|[\s,;(/]){re.escape(postal)}(?:$|[\s,;)/])', title or ""):
            return True
        for phrase in _leading_phrases(alt) + _admin_short_names(alt):
            if phrase and phrase_in_text(phrase, title):
                return True
    return False


def _alt_in_title(alt, title):
    """True when this gazetteer alias is actually written in the headline.

    Short abbreviations such as 'Ill.' or 'Ala.' must appear in that form
    (or as a capital postal), not as a common lowercase word like 'ill'.
    """
    raw = (alt or "").strip()
    if not raw or not title:
        return False
    k = _norm(raw)
    # Capital postals and dotted abbreviations: match the original spelling.
    if raw.endswith(".") or (len(k) <= 3 and raw[:1].isupper() and raw[1:].isupper() is False and "." in raw):
        stem = re.escape(raw.rstrip("."))
        return bool(re.search(rf'(?<![A-Za-z]){stem}\.?(?![A-Za-z])', title))
    if len(k) <= 2:
        postal = raw.upper() if raw.isalpha() and raw.isupper() else ""
        if not postal:
            return False
        return bool(re.search(rf'(?:^|[\s,;(/]){re.escape(postal)}(?:$|[\s,;)/])', title))
    if f" {k} " in f" {_norm(title)} ":
        return True
    if f" {_fold_spell(k)} " in f" {_fold_spell(title)} ":
        return True
    return False


def _title_admin_codes(title, cc=""):
    """Gazetteer admin-1 codes clearly named in the headline."""
    gaz = _load_gaz()
    if not gaz["ok"] or not title:
        return set()
    found = set()
    cc = (cc or "").upper()
    for rec in gaz["admin"]:
        if cc and rec["cc"] != cc:
            continue
        for alt in rec.get("alts") or [rec["name"]]:
            if _alt_in_title(alt, title):
                found.add(rec["code"])
                break
    return found


def _prefix_country(text):
    """MeteoAlarm-style 'Croatia: ...' country prefix, else empty."""
    raw = (text or "").strip()
    if ":" not in raw[:48]:
        return ""
    head = raw.split(":", 1)[0].strip()
    if head and _looks_like_country(head):
        return _norm(head)
    return ""


def _admin_conflict(title, place, cc=""):
    """True when the pin's state/province is not the one the headline names."""
    place_codes = set()
    cc = (cc or "").upper()
    for group in _groups(place):
        for part in _parts(group):
            rec = _lookup_admin(part, cc)
            if rec:
                place_codes.add(rec["code"])
    if not place_codes:
        return False
    pin_ccs = {c.split(".")[0] for c in place_codes}
    named = set()
    for pcc in pin_ccs:
        named |= _title_admin_codes(title, pcc)
    if named and named.isdisjoint(place_codes):
        return True
    return False


def container_named_in_headline(title, place, cc=""):
    """A county, state, or equivalent admin-1 named in the headline and consistent with the pin.

    Returns a pin dict {place, precision, lat, lon, cc} or None. Country names are not used.
    """
    title = title or ""
    cc = _place_cc(place, cc)
    cands = []
    for group in _groups(place):
        parts = _parts(group)
        if not parts:
            continue
        # Everything after the locality can be a container; the last part is usually the country.
        tails = parts[1:] if len(parts) > 1 else []
        for i, part in enumerate(tails):
            is_last = i == len(tails) - 1
            if is_last and _looks_like_country(part, cc):
                continue
            if not _admin_mentioned(part, title, cc):
                continue
            rec = _lookup_admin(part, cc)
            if rec:
                cname = rec["name"]
                ctry = _country_label(rec["cc"]) or (parts[-1] if is_last and _looks_like_country(parts[-1], cc) else "")
                # If the last part of this group was a country we skipped, use it as the label suffix.
                if not ctry and parts and _looks_like_country(parts[-1], cc):
                    ctry = parts[-1]
                label = ", ".join(x for x in (cname, ctry) if x)
                cands.append({"place": label, "precision": _admin_precision(rec),
                              "lat": rec["lat"], "lon": rec["lon"], "cc": rec["cc"]})
                continue
            # Named container with no gazetteer centroid: keep the original point, relabel.
            suffix = list(tails[i + 1:])
            label = ", ".join([part] + suffix)
            prec = "county" if _looks_like_admin(part) else "state"
            cands.append({"place": label, "precision": prec, "lat": None, "lon": None, "cc": cc,
                          "reuse_coords": True, "label": part})
    if not cands:
        return None
    # Prefer a county over a state when both are named.
    cands.sort(key=lambda c: 0 if c["precision"] == "county" else 1)
    return cands[0]


def headline_pin(title, place, precision="", cc="", lat=None, lon=None):
    """Return pin fields the headline supports, or None.

    May demote a city/point/facility pin to a named containing county or state.
    """
    prec = (precision or "").lower().strip()
    coord = _coord(lat, lon)
    if not (place or "").strip():
        if prec == "point" and coord:
            return {"place": "", "precision": "point", "lat": coord[0], "lon": coord[1], "cc": cc or ""}
        return None
    if _admin_conflict(title, place, cc):
        return None
    pa, ta = _prefix_country(place), _prefix_country(title)
    if pa and ta and pa != ta:
        return None
    if city_named_in_headline(title, place):
        if not coord:
            return None
        return {"place": place, "precision": prec or "city", "lat": coord[0], "lon": coord[1], "cc": cc or ""}
    # State / county / admin-labelled pins: keep when that admin is named (Bayelsa, Jazan, FL).
    head = (place or "").split(",")[0].strip()
    if prec in ("state", "county") or _looks_like_admin(head):
        if _admin_mentioned(head, title, cc):
            if not coord:
                return None
            return {"place": place, "precision": prec or "state", "lat": coord[0], "lon": coord[1], "cc": cc or ""}
    cont = container_named_in_headline(title, place, cc)
    if not cont:
        return None
    if cont.get("reuse_coords"):
        if not coord:
            return None
        cont = dict(cont, lat=coord[0], lon=coord[1])
        cont.pop("reuse_coords", None)
        cont.pop("label", None)
    return cont


def headline_agrees(title, place, precision=""):
    """The pin's place must be named in the headline (or be source coordinates with no label).

    A city pin may instead be supported by a consistent county or state named in the headline.
    A country name alone does not count.
    """
    prec = (precision or "").lower()
    if not (place or "").strip():
        return prec == "point"
    return headline_pin(title, place, prec, lat=1, lon=1) is not None


def on_water(lat, lon):
    """True when Natural Earth admin-0 has no country at this point (open water). False if PIP is unavailable."""
    if lat is None or lon is None:
        return False
    try:
        import geo
        cc, _a1 = geo.gaz().pip(float(lat), float(lon))
        return not cc
    except Exception:
        return False


def _coord(lat, lon):
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if la == 0 and lo == 0:
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return la, lo


def resolve_pin(*, title="", place="", precision="", tier="", lat=None, lon=None, cc="", how="", confidence=""):
    """Pin fields if this story should be drawn, else None. May demote city pins to county/state."""
    coord = _coord(lat, lon)
    if not coord:
        return None
    prec = (precision or "").lower().strip()
    tier = (tier or "").lower().strip()
    how = (how or "").lower()
    conf = (confidence or "").lower().strip()
    if tier in DROP_TIER:
        return None
    if prec in DROP_PREC:
        return None
    if prec and prec not in SPECIFIC:
        return None
    if conf in LOW_CONF:
        return None
    if any(s in how for s in HOW_BAD):
        return None
    pin = headline_pin(title, place, prec, cc, coord[0], coord[1])
    if not pin:
        return None
    if on_water(pin["lat"], pin["lon"]):
        return None
    return pin


def eligible(*, title="", place="", precision="", tier="", lat=None, lon=None, cc="", how="", confidence=""):
    """True only when this story should be drawn as a map pin."""
    return resolve_pin(title=title, place=place, precision=precision, tier=tier,
                       lat=lat, lon=lon, cc=cc, how=how, confidence=confidence) is not None


def filter_points(points):
    """Keep only eligible pins from a /api/signal/points-style list. Returns (kept, dropped).

    City pins whose city is not in the headline are dropped, or rewritten at a named county/state.
    """
    kept, dropped = [], 0
    for p in points or []:
        prec = p.get("precision") or ""
        # heat_all "approx" means country/fallback; points.approximate alone is not enough to drop a named city.
        tier = p.get("tier") or ("approx" if prec in ("country", "region") else "")
        pin = resolve_pin(title=p.get("title") or "", place=p.get("place") or "",
                          precision=prec, tier=tier,
                          lat=p.get("lat"), lon=p.get("lon"), cc=p.get("cc") or "",
                          how=p.get("how") or "", confidence=p.get("confidence") or "")
        if pin:
            q = dict(p)
            q["lat"], q["lon"] = pin["lat"], pin["lon"]
            q["place"] = pin.get("place") if pin.get("place") is not None else q.get("place")
            q["precision"] = pin.get("precision") or q.get("precision")
            if pin.get("cc"):
                q["cc"] = pin["cc"]
            kept.append(q)
        else:
            dropped += 1
    return kept, dropped


def _ix(cols):
    return {c: i for i, c in enumerate(cols or [])}


def _cell(row, ix, key, default=""):
    i = ix.get(key)
    if i is None or i >= len(row):
        return default
    v = row[i]
    return default if v is None else v


def row_eligible(row, cols):
    ix = _ix(cols)
    return eligible(title=_cell(row, ix, "title"), place=_cell(row, ix, "place"),
                    precision=_cell(row, ix, "prec"), tier=_cell(row, ix, "tier"),
                    lat=_cell(row, ix, "lat", None), lon=_cell(row, ix, "lon", None),
                    cc=_cell(row, ix, "cc"), how=_cell(row, ix, "how"),
                    confidence=_cell(row, ix, "confidence"))


def _hide_row(row, cols):
    """Same list item, but no pin: coords cleared, tier set to global."""
    ix = _ix(cols)
    r = list(row)
    if "lat" in ix and ix["lat"] < len(r):
        r[ix["lat"]] = None
    if "lon" in ix and ix["lon"] < len(r):
        r[ix["lon"]] = None
    if "tier" in ix and ix["tier"] < len(r):
        r[ix["tier"]] = "global"
    if "how" in ix and ix["how"] < len(r):
        prev = (r[ix["how"]] or "").strip()
        if not prev or prev == "geo":
            r[ix["how"]] = "no verified location"
    return r


def _apply_pin(row, cols, pin):
    ix = _ix(cols)
    r = list(row)
    if "lat" in ix and ix["lat"] < len(r):
        r[ix["lat"]] = pin["lat"]
    if "lon" in ix and ix["lon"] < len(r):
        r[ix["lon"]] = pin["lon"]
    if pin.get("place") and "place" in ix and ix["place"] < len(r):
        r[ix["place"]] = pin["place"]
    if pin.get("precision") and "prec" in ix and ix["prec"] < len(r):
        r[ix["prec"]] = pin["precision"]
    if pin.get("cc") and "cc" in ix and ix["cc"] < len(r):
        r[ix["cc"]] = pin["cc"]
    return r


def filter_heat_rows(rows, cols):
    """Leave every story in the list; strip coordinates from pins that are not specific and named.

    City pins may be rewritten at a named county or state centroid.
    """
    out, dropped = [], 0
    ix = _ix(cols)
    for row in rows or []:
        pin = resolve_pin(title=_cell(row, ix, "title"), place=_cell(row, ix, "place"),
                          precision=_cell(row, ix, "prec"), tier=_cell(row, ix, "tier"),
                          lat=_cell(row, ix, "lat", None), lon=_cell(row, ix, "lon", None),
                          cc=_cell(row, ix, "cc"), how=_cell(row, ix, "how"),
                          confidence=_cell(row, ix, "confidence"))
        if pin:
            out.append(_apply_pin(row, cols, pin))
        else:
            out.append(_hide_row(row, cols))
            dropped += 1
    return out, dropped


def filter_heat_body(body):
    if not body:
        return body
    cols = body.get("cols") or []
    rows, dropped = filter_heat_rows(body.get("rows") or [], cols)
    body = dict(body)
    body["rows"] = rows
    cov = dict(body.get("coverage") or {})
    pinned = sum(1 for r in rows if row_eligible(r, cols))
    cov["located"] = pinned
    cov["unverified_pins"] = dropped
    if cov.get("total"):
        cov["pct"] = round(100 * pinned / cov["total"], 1)
    body["coverage"] = cov
    return body
