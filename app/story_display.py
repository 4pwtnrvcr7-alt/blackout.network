"""Display-time story classifier and list filters (Nov 10 2026).

The scanner stores cluster category from the first matching keyword in scanner.classify()
(war/conflict is checked before disease, and strike[sd]? is a conflict keyword). This
module is a post-filter: it does not edit scanner.py or scoring, and it does not delete
rows. Call apply() on clusters as they leave the API / story page / homepage so The Wire
filter chips, the map tag, the carousel and /wire/<id> all show the same label.

Also:
  - entertainment / movie-review posts are marked hidden so lists can drop them
  - a brief that says "WHERE: location not specified by source" falls back to a
    place named in the headline (e.g. California)
"""
import re

# Disease / outbreak cues, including "illness" (scanner.KW["disease"] does not have it).
_DISEASE = re.compile(
    r"\b(mystery illness|unknown disease|illness|outbreak|virus|ebola|marburg|cholera|measles|"
    r"influenza|h5n1|avian|bird flu|mpox|dengue|plague|pathogen|epidemic|pandemic|disease|"
    r"infection|infections|infected|cases|quarantine|foodborne|botulism|meningitis|polio|"
    r"tuberculosis|anthrax|nipah|h9n2)\b", re.I)

# Real conflict / combat wording. Bare verbs "strikes" / "hits" / "attack" are NOT enough.
_STRONG_CONFLICT = re.compile(
    r"\b(missile|airstrike|air strike|drone|shelling|artillery|invasion|troops|military|"
    r"ceasefire|battlefield|warship|warplane|idf|hamas|hezbollah|houthi|rocket|gunfire|"
    r"offensive|bombard|airstrikes|troops|soldiers|battalion|artillery|warhead|icbm|"
    r"nuclear (strike|attack|war)|declaration of war|invades?|invaded)\b", re.I)

_ENT_STRONG = re.compile(
    r"\b(watched this|loved it|dark comedy|stellar cast|movie review|film review|"
    r"great script|box office|#filmsky|#moviesky|rotten tomatoes|imdb)\b", re.I)
_ENT_WORD = re.compile(
    r"\b(movie|film|series|cast|trailer|season|episode|review|watched|comedy|actors?)\b", re.I)
# News-like uses of the same words — do not hide these.
_ENT_NEWS = re.compile(
    r"\b((flu|hurricane|storm|wildfire|fire|rainy|dry|monsoon|earnings|tv) season|"
    r"season of (storms|fires|rains)|series of (attacks?|explosions?|strikes?|earthquakes?|protests?)|"
    r"under review|in review|judicial review|review of (sanctions?|policy|the)|"
    r"cast (a |their |his |her )?(vote|ballot|ballots)|casting votes?|"
    r"film (footage|crew|crews|at the scene)|bodycam|dashcam|"
    r"trailer (park|home|hitch)|semitrailer|tractor[- ]trailer)\b", re.I)

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
    "puerto rico": "Puerto Rico",
}
_PLACES = {
    "los angeles": "Los Angeles", "san francisco": "San Francisco", "san diego": "San Diego",
    "new york city": "New York City", "chicago": "Chicago", "houston": "Houston",
    "seattle": "Seattle", "miami": "Miami", "boston": "Boston", "london": "London",
    "paris": "Paris", "kyiv": "Kyiv", "kiev": "Kyiv", "tehran": "Tehran", "gaza": "Gaza",
    "ukraine": "Ukraine", "russia": "Russia", "iran": "Iran", "israel": "Israel",
    "china": "China", "taiwan": "Taiwan", "mexico": "Mexico", "canada": "Canada",
    "united states": "United States", "u.s.": "United States", "usa": "United States",
}

_WHERE_NONE = re.compile(r"(WHERE:\s*)location not specified by source", re.I)


def display_category(title, category=""):
    """If disease/outbreak words are present and the only conflict cue is a verb like
    'strikes' or 'hits', show disease — even when the stored category is war/conflict."""
    cat = (category or "").strip() or "other"
    t = title or ""
    if _DISEASE.search(t) and not _STRONG_CONFLICT.search(t):
        return "disease"
    return cat


def is_entertainment_junk(title):
    """True for movie / series / review posts (e.g. a Bluesky film rec), not news."""
    t = title or ""
    if not t: return False
    if _ENT_NEWS.search(t) and not _ENT_STRONG.search(t):
        return False
    if _ENT_STRONG.search(t):
        return True
    return len(_ENT_WORD.findall(t)) >= 2


def place_from_headline(title):
    """A place actually written in the headline, longest match first. None if none."""
    t = title or ""
    if not t: return None
    low = t.lower()
    keys = sorted(list(_PLACES) + list(_US_STATES), key=len, reverse=True)
    labels = {**_PLACES, **_US_STATES}
    for k in keys:
        if k == "washington" and not re.search(r"\bWashington\s+(State|County)\b|\bstate of Washington\b", t, re.I):
            continue
        if re.search(r"\b" + re.escape(k) + r"\b", low, re.I):
            return labels[k]
    return None


def rewrite_brief(brief, title, location=None):
    """Replace 'location not specified by source' with a headline (or stored) place."""
    brief = brief or ""
    if not _WHERE_NONE.search(brief):
        return brief
    place = (location or "").strip() or place_from_headline(title)
    if not place:
        return brief
    return _WHERE_NONE.sub(r"\1" + place, brief)


def apply(row):
    """Return a shallow copy with display category, rewritten brief, and hidden flag.
    Does not write to the database."""
    if not row:
        return row
    out = dict(row)
    title = out.get("title") or ""
    out["category"] = display_category(title, out.get("category"))
    out["brief"] = rewrite_brief(out.get("brief") or "", title, out.get("location"))
    if (not (out.get("location") or "").strip()) and place_from_headline(title):
        out["location"] = place_from_headline(title)
    out["hidden"] = bool(is_entertainment_junk(title))
    return out


def visible(row):
    if not row: return False
    if row.get("hidden") or is_entertainment_junk(row.get("title") or ""):
        return False
    return True
