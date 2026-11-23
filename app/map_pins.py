"""Which stories may appear as pins on the homepage map, /map, and any other story map.

Nov 23 2026 (pt1761u, pt1762u): only a verified, specific location is a pin. Stories with no
location, a country-centroid-only location, a low-confidence or ambiguous match, a pin on
water, or a location that contradicts the headline stay in the lists, not on the map.

Does not geocode, write a database, or touch scanner scoring.
"""
import re, unicodedata

SPECIFIC = {"point", "city", "county", "facility", "state"}
DROP_PREC = {"country", "region"}
DROP_TIER = {"global", "region", "approx"}
LOW_CONF = {"low", "weak", "ambiguous"}
HOW_BAD = ("several", "ambiguous", "nationality", "pending", "fallback", "country centre",
           "country center", "country-level", "spread", "place_in_country")
STOP = {"united", "states", "usa", "us", "uk", "the", "of", "and", "county", "parish", "city",
        "province", "region", "state", "district", "republic", "kingdom", "north", "south",
        "east", "west", "northern", "southern", "eastern", "western"}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _has(text, phrase):
    t, p = _norm(text), _norm(phrase)
    if not p or len(p) < 2:
        return False
    return f" {p} " in f" {t} "


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


def headline_agrees(title, place, precision=""):
    """The pin's place must be named in the headline (or be source coordinates with no label)."""
    prec = (precision or "").lower()
    if not (place or "").strip():
        return prec == "point"
    title = title or ""
    nt = f" {_norm(title)} "
    if any(f" {t} " in nt for t in place_tokens(place)):
        return True
    city = _norm((place or "").split(",")[0])
    return bool(city and f" {city} " in nt)


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


def eligible(*, title="", place="", precision="", tier="", lat=None, lon=None, cc="", how="", confidence=""):
    """True only when this story should be drawn as a map pin."""
    coord = _coord(lat, lon)
    if not coord:
        return False
    prec = (precision or "").lower().strip()
    tier = (tier or "").lower().strip()
    how = (how or "").lower()
    conf = (confidence or "").lower().strip()
    if tier in DROP_TIER:
        return False
    if prec in DROP_PREC:
        return False
    if prec and prec not in SPECIFIC:
        return False
    if conf in LOW_CONF:
        return False
    if any(s in how for s in HOW_BAD):
        return False
    if not headline_agrees(title, place, prec):
        return False
    if on_water(*coord):
        return False
    return True


def filter_points(points):
    """Keep only eligible pins from a /api/signal/points-style list. Returns (kept, dropped)."""
    kept, dropped = [], 0
    for p in points or []:
        prec = p.get("precision") or ""
        # heat_all "approx" means country/fallback; points.approximate alone is not enough to drop a named city.
        tier = p.get("tier") or ("approx" if prec in ("country", "region") else "")
        if eligible(title=p.get("title") or "", place=p.get("place") or "",
                    precision=prec, tier=tier,
                    lat=p.get("lat"), lon=p.get("lon"), cc=p.get("cc") or "",
                    how=p.get("how") or "", confidence=p.get("confidence") or ""):
            kept.append(p)
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


def filter_heat_rows(rows, cols):
    """Leave every story in the list; strip coordinates from pins that are not verified and specific."""
    out, dropped = [], 0
    for row in rows or []:
        if row_eligible(row, cols):
            out.append(row)
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
