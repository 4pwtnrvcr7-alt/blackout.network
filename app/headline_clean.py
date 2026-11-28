"""Display and Share-to-X headline cleanup (display only; scanner data untouched).

Strips bracketed agency region codes like [Sea] and [Land], zero-width and other
format Unicode, and leading source-agency prefixes (INGV:, JMA:, …). Renders
telegraphic quake titles as clean English using only places the source already
gave — never invents a country, coast, or city.
"""
import re
import unicodedata

# Leading "AGENCY:" prefixes on feed titles. Same names as x_share.SOURCE_FEEDS.
_SOURCE_FEEDS = (
    "INGV", "JMA", "EMSC", "USGS", "GFZ", "GDACS", "GEOFON", "HANS", "IODA",
    "PTWC", "FDSN", "NEIC", "GCMT", "IRIS", "CESMD", "GeoNet", "GEONET",
    "LastQuake", "MeteoAlarm", "Meteoalarm", "BMKG", "PHIVOLCS", "PAGASA",
    "SWPC", "SDO", "SOHO", "EONET", "PAGER",
)
_AGENCY_PREFIX = re.compile(
    r"^(?:" + "|".join(sorted(map(re.escape, _SOURCE_FEEDS), key=len, reverse=True)) + r")\s*:\s*",
    re.I,
)

# USGS / EMSC / INGV region tags, and any trailing [Word] region code (no colon).
_REGION_CODE = re.compile(
    r"\s*\[(?:Sea|Land|Ocean|Inland|Coast|Coastal|Lake|Ground|Air|IntSea|TerrSea|Region)\]",
    re.I,
)
_TRAIL_REGION = re.compile(r"\s*\[[A-Za-z]{2,16}\]\s*$")
_SEA_MARK = re.compile(r"\[Sea\]", re.I)

_INTENSITY = re.compile(
    r",?\s*(?:max(?:imum)?\s+)?(?:seismic\s+)?intensity\s+\d+\s*$",
    re.I,
)

_QUAKE = re.compile(
    r"^M\s*(?P<mag>\d+(?:\.\d+)?)\s+(?P<kind>earthquakes?|quakes?)\b\s*(?P<rest>.*)$",
    re.I,
)

_ADJ_SEA = re.compile(r"^(?:the\s+)?adjacent\s+sea\s+of\s+(.+)$", re.I)
_OFF_COAST = re.compile(
    r"^off\s+(?:the\s+)?(?:(?P<dir>east|west|north|south)\s+)?coast\s+of\s+(?:the\s+)?(?P<place>.+)$",
    re.I,
)
_OF_DIR = re.compile(
    r"^(?P<dir>north(?:west|east)?|south(?:west|east)?|east|west|offshore)\s+of\s+(?:the\s+)?(?P<place>.+)$",
    re.I,
)
_REL = re.compile(
    r"^(?P<rel>off|near|in|at|around|by)\s+(?:the\s+)?(?P<place>.+)$",
    re.I,
)

_NEWS = re.compile(
    r"\b(warning|watch|advisory|issued|reported|kills?|killed|injure[ds]?|dead|deaths?|tsunami|felt)\b",
    re.I,
)

_KEEP_ISLAND = {
    "rhode island", "long island", "cape verde", "prince edward island",
    "vancouver island", "big island", "north island", "south island",
    "christmas island", "norfolk island", "cockburn island",
}

_THE_PLACE = re.compile(
    r"(?i)\b(islands|sea|ocean|republic|united\s+states|united\s+kingdom|"
    r"netherlands|philippines|maldives|bahamas|uae|united\s+arab\s+emirates)\b"
)

# Odd width / line-break spaces → a normal space.
_SPACEY = dict.fromkeys(map(ord, (
    "\u00a0\u202f\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u3000\u205f\u1680"
)), " ")


def tidy_text(t):
    """Strip zero-width / format / control characters and normalize whitespace.

    Keeps combining marks (accents on place names). Does not strip [Sea] tags.
    """
    t = unicodedata.normalize("NFC", str(t or "")).translate(_SPACEY)
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat in {"Cf", "Cc"} and ch not in "\n\t":
            continue
        if ch in {"\ufffd", "\ufffc"}:
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _trim_island(place):
    p = place.strip().rstrip(" ,;:-")
    if p.lower() not in _KEEP_ISLAND:
        p = re.sub(r"(?i)\s+Island$", "", p).strip()
    return p


def _the(place):
    p = place.strip()
    if re.match(r"(?i)^the\s+", p):
        return p
    if _THE_PLACE.search(p):
        return "the " + p
    return p


# Leading agency-style geography on a location field ("Adjacent Sea of X",
# "Northwest of X", "off the coast of X"). Reduced to the core place before
# appending so a second display_headline pass does not glue the raw phrase
# back onto an already-clean title.
_LOC_PREFIX = re.compile(
    r"^(?:the\s+)?(?:"
    r"adjacent\s+sea\s+of|"
    r"off\s+(?:the\s+)?(?:east|west|north|south)\s+coast\s+of|"
    r"off\s+(?:the\s+)?coast\s+of|"
    r"(?:north(?:west|east)?|south(?:west|east)?|east|west|offshore)\s+of|"
    r"near|in|at|around|by"
    r")\s+(?:the\s+)?",
    re.I,
)


def _loc_cores(location):
    """Bare place names from a source location, minus region codes and raw phrases."""
    loc = tidy_text(location or "")
    loc = _REGION_CODE.sub("", loc)
    loc = _TRAIL_REGION.sub("", loc)
    loc = loc.split(";")[0].strip()
    if not loc or len(loc) > 60:
        return []
    if re.fullmatch(r"[A-Z]{3}(?:,\s*US[A]?)?", loc):
        return []
    cores = []
    for part in loc.split(","):
        part = _LOC_PREFIX.sub("", part.strip()).strip()
        part = _trim_island(part)
        if part:
            cores.append(part)
    return cores


def _with_loc(place, location):
    """Append a source location (usually a country) if it is not already named."""
    cores = _loc_cores(location)
    if not cores:
        return place
    pl = place.lower()
    missing = [p for p in cores if p.lower() not in pl and pl not in p.lower()]
    if not missing:
        return place
    return f"{place}, {', '.join(missing)}"


def _split_news(rest):
    """Peel a trailing news clause ('tsunami warning issued') off the place phrase."""
    rest = (rest or "").strip(" -–,;:")
    if not rest or "," not in rest:
        return rest, ""
    bits = [b.strip() for b in rest.split(",") if b.strip()]
    if len(bits) < 2:
        return rest, ""
    news_i = next((i for i, b in enumerate(bits) if _NEWS.search(b)), None)
    if news_i is None or news_i == 0:
        return rest, ""
    return ", ".join(bits[:news_i]), ", " + ", ".join(bits[news_i:])


def _place_phrase(rest, location, sea):
    """Turn a telegraphic place remainder into an English prepositional phrase."""
    rest, news = _split_news(rest)
    rest = rest.strip(" -–,;:")
    if not rest:
        loc = _with_loc("", location).lstrip(", ").strip()
        if not loc:
            return news
        rel = "off the coast of" if sea else "in"
        return f" {rel} {_the(loc)}{news}"

    m = _ADJ_SEA.match(rest)
    if m:
        place = _with_loc(_trim_island(m.group(1)), location)
        return f" near {place}{news}"

    m = _OFF_COAST.match(rest)
    if m:
        d = (m.group("dir") or "").strip().lower()
        place = _with_loc(_trim_island(m.group("place")), location)
        rel = f"off the {d} coast of" if d else "off the coast of"
        return f" {rel} {_the(place)}{news}"

    m = _OF_DIR.match(rest)
    if m:
        d = m.group("dir").lower()
        place = _with_loc(_trim_island(m.group("place")), location)
        return f" {d} of {_the(place)}{news}"

    m = _REL.match(rest)
    if m:
        rel = m.group("rel").lower()
        place = _with_loc(_trim_island(m.group("place")), location)
        return f" {rel} {_the(place)}{news}"

    place = _with_loc(_trim_island(rest), location)
    # "Central Peru" / bare country or region: "in" on land, "off the coast of" when [Sea].
    rel = "off the coast of" if sea else "in"
    # Already a preposition-led phrase we didn't match (e.g. "between X and Y"): keep it.
    if re.match(r"(?i)^(between|along|across|from)\b", place):
        return f" {place}{news}"
    return f" {rel} {_the(place)}{news}"


def display_headline(title, location=None):
    """Clean a story headline for the page H1 and the Share to X text.

    Idempotent. Does not invent geography: [Sea] is the only cue for
    'off the coast of', and a country is appended only when `location`
    already names it.
    """
    raw = str(title or "")
    sea = bool(_SEA_MARK.search(raw))
    t = tidy_text(raw)
    t = _REGION_CODE.sub("", t)
    t = _TRAIL_REGION.sub("", t)
    t = _AGENCY_PREFIX.sub("", t)
    t = _INTENSITY.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" -–,;:")
    q = _QUAKE.match(t)
    if q:
        mag = q.group("mag")
        kind = q.group("kind").lower()
        if kind.startswith("earthquake"):
            kind = "earthquake"
        elif kind.startswith("quake"):
            kind = "quake"
        phrase = _place_phrase(q.group("rest") or "", location, sea)
        t = f"M{mag} {kind}{phrase}".strip()
    return t or tidy_text(raw)
