"""Editorial gates for the newsletter brief and social story selection.

Keep this file in sync in:
  - app/story_gates.py  (site / newsletter brief)
  - /workspace/launch/social/story_gates.py  (box social pipeline)

Nov 10 2026 (Matt): never cover the French SMIC / minimum-wage union story again
(hard block by cluster id and headline). Non-English headlines are dropped, not
shown untranslated. Template-filler analysis (headline/rank restated, no facts)
is dropped. Foreign domestic politics that is not a threat to the US or
civilization (French minimum wage, union disputes and similar) stays out of the
brief and out of social picks. This is a selection filter; it does not change
scanner scoring.
"""
from __future__ import annotations

import re
import unicodedata

# The Nov 10 evening-brief cluster, plus any retitle of the same story.
BLOCKED_CLUSTER_IDS = frozenset({"d4c11e75bf8722e0"})

# Headline / body match for this story or cluster. \bsmic\b does not match "seismic".
_SMIC_HEAD = re.compile(
    r"coup\s+de\s+pouce\s+au\s+smic|"
    r"\bintersyndicale\b|"
    r"\bsmic\b|"
    r"french\s+minimum\s+wage|"
    r"france'?s?\s+minimum\s+wage|"
    r"minimum\s+wage\s+(?:in|for)\s+france|"
    r"minimum\s+wage.{0,40}\bfrance\b|"
    r"\bfrance\b.{0,40}minimum\s+wage",
    re.I,
)

_US = re.compile(
    r"\b(?:U\.?S\.?A?|United States|(?<!Latin )(?<!South )(?<!Central )America|Americans?|"
    r"US-(?:led|backed|made|based)|Pentagon|White House|Capitol Hill|Trump|Vance|"
    r"FBI|CIA|NSA|DHS|FEMA|CISA|FAA|FDA|CDC|ICE|Wall Street|S&P ?500|Nasdaq|Federal Reserve|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Hawaii|"
    r"Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|"
    r"Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|"
    r"New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|"
    r"Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
    r"Virginia|Washington state|Washington, D\.?C\.?|West Virginia|Wisconsin|Wyoming|"
    r"Puerto Rico|Guam|Chicago|Los Angeles|Houston|Philadelphia|Phoenix|Atlanta|Miami|"
    r"Seattle|Boston|Denver)\b",
    re.I,
)
_US_WEAK = re.compile(
    r"\b(?:Congress|congressional|Senate|senators?|House (?:Republicans|Democrats|Speaker)|"
    r"Supreme Court|National Guard|Treasury|Dow|the Fed|Georgia|"
    r"federal (?:judge|government|agents?|court))\b",
    re.I,
)

# Labor / wage / union disputes and similar domestic political rows that are
# not a threat to the US or civilization.
_LABOR_DOMESTIC = re.compile(
    r"\b(?:minimum wage|min(?:imum)?-wage|\bsmic\b|coup de pouce|intersyndicale|"
    r"syndicat\w*|trade unions?|union (?:dispute|talks|negotiat\w*|walkouts?|federation|coalition)|"
    r"collective bargaining|wage (?:talks|dispute|rise|hike|increase|boost|deal|agreement)|"
    r"labor (?:dispute|talks|reform|law|unions?)|labour (?:dispute|talks|reform|law|unions?)|"
    r"walkouts? over (?:pay|wages|pensions?)|strike over (?:pay|wages|pensions?))|"
    r"fracture l['\u2019]intersyndicale",
    re.I,
)

# International / civilizational threat angle. "coup de pouce" is stripped first
# so the French idiom cannot count as a coup d'etat.
_THREAT = re.compile(
    r"\b(?:war|wartime|invasion|invade[sd]?|troops?|missiles?|airstrikes?|air ?strikes?|"
    r"nuclear|warheads?|terror\w*|bombings?|hostages?|assassinat\w*|martial law|"
    r"cyber ?attacks?|ransomware|power grid|outbreak|epidemic|pandemic|"
    r"riots?|unrest|uprising|mass protests?|censor\w*|surveillance|"
    r"sanctions?|blockade|troops?|airstrike|drone strikes?|"
    r"coup d['\u2019]?etat|\bcoup\b|impeach\w*|martial law|"
    r"bank (?:collapse|failure|run)|market crash|currency crisis|hyperinflation|"
    r"election interference|state of emergency)\b",
    re.I,
)

_EN_FUNC = set("""the a an of to in on for and is are as at by with from after says said
over than that this its was were be been has have had will would can could should
may might not only also just still yet but or if when while because so such very
more most less about around across between among against via into off up out
us they their he she it we our you your who which what new first after amid""".split())

_FOREIGN_FUNC = {
    # French (skip words that are also common English: or, son, plus, car, an, a, on)
    "le", "la", "les", "des", "du", "au", "aux", "une", "et", "en", "dans", "pour",
    "sur", "avec", "pas", "que", "qui", "est", "sont", "cette", "ces", "leur",
    "leurs", "nos", "vos", "mais", "donc", "elle", "ils", "elles", "nous", "vous",
    "gouvernement", "mobilisation", "sociale", "syndicale", "intersyndicale",
    "pouce", "fracture",
    # Spanish
    "el", "los", "las", "del", "una", "por", "para", "con", "como", "esta", "está",
    "según", "tambien", "también",
    # German
    "der", "die", "das", "und", "für", "nicht", "ist", "im", "den", "dem", "auf",
    "von", "mit", "sich", "ein", "eine",
    # Italian / Portuguese (distinctive)
    "il", "della", "nel", "non", "che", "degli", "pelo", "pela", "não", "uma",
}

_LATIN = re.compile(r"[A-Za-z\u00c0-\u024f]+(?:['\u2019][A-Za-z\u00c0-\u024f]+)?")
_FILLER_WHAT = re.compile(r"^\s*on the record(?:\s+for|\s*\()", re.I)
_FILLER_ANALYSIS = re.compile(
    r"the reports describe (?:a government action|the use of force|a natural hazard|"
    r"cases of disease|a system disruption|a space-weather measurement|"
    r"a market or banking event|the event|\u201c|“)",
    re.I,
)
_WHY_RANKED = re.compile(r"is why this is ranked\b", re.I)
_HISTORY_BOILER = re.compile(
    r"scanner history|not enough history|prior rank in our send ledger|"
    r"similar past events \(|cluster first seen|report volume in our log|"
    r"volume alone does not set the danger",
    re.I,
)
_SECTIONS = ("near", "main", "politics", "notable", "updates", "follow", "developing", "watchlist")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return s.replace("\u2019", "'").replace("\u2018", "'")


def headline(item) -> str:
    if not isinstance(item, dict):
        return str(item or "")
    for k in ("display_title", "headline", "title"):
        v = item.get(k)
        if v:
            return str(v)
    # Do not fall back to {}. An empty dict is still a dict, so that used to
    # recurse forever (x_post calls require_allowed({text, purpose}) with no title).
    sub = item.get("candidate") or item.get("youtube")
    if isinstance(sub, dict) and sub is not item:
        return headline(sub)
    return str(item.get("text") or item.get("body") or "")


def cluster_ids(item) -> set[str]:
    out = set()
    if not isinstance(item, dict):
        return out
    for k in ("cluster_id", "key", "id"):
        v = item.get(k)
        if v and isinstance(v, (str, int)):
            out.add(str(v))
    sub = item.get("candidate")
    if isinstance(sub, dict) and sub is not item:
        out |= cluster_ids(sub)
    return out


def _story_text(item) -> str:
    if not isinstance(item, dict):
        return _fold(str(item or ""))
    parts = [headline(item)]
    for k in ("brief", "what", "text", "body", "description", "location", "where"):
        v = item.get(k)
        if v:
            parts.append(str(v))
    return _fold(" ".join(parts))


def us_involved(item) -> bool:
    t = _story_text(item)
    loc = ""
    if isinstance(item, dict):
        loc = str(item.get("location") or item.get("where") or "").strip()
    if _US.search(t) or _US.search(loc):
        return True
    return bool(_US_WEAK.search(t)) and not loc


def _threat_text(text: str) -> str:
    # Do not treat the French idiom "coup de pouce" as a coup d'etat.
    return re.sub(r"coup\s+de\s+pouce", " ", text, flags=re.I)


def is_hard_blocked(item) -> str | None:
    """Matt, Nov 10: never cover the French SMIC / minimum-wage story again."""
    ids = cluster_ids(item)
    if ids & BLOCKED_CLUSTER_IDS:
        return "hard-blocked story (French SMIC / minimum wage, cluster d4c11e75bf8722e0)"
    t = _story_text(item)
    if _SMIC_HEAD.search(t):
        return "hard-blocked story (French SMIC / minimum wage headline match)"
    return None


def is_english_headline(title: str) -> bool:
    """True when the displayed headline reads as English (accented proper names are fine)."""
    title = _fold(title or "")
    title = re.sub(r"https?://\S+", " ", title)
    # Non-Latin scripts: if a large share of letters is not Latin, it is not English.
    letters = [ch for ch in title if ch.isalpha()]
    if letters:
        latin = sum(1 for ch in letters if ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("\u00c0" <= ch <= "\u024f"))
        if latin / len(letters) < 0.7:
            return False
    words = [w.lower() for w in _LATIN.findall(title)]
    # Strip French elisions to the leading particle: l'intersyndicale -> l
    particles = []
    bare = []
    for w in words:
        if "'" in w:
            left, right = w.split("'", 1)
            if left in {"l", "d", "n", "s", "qu", "j", "c", "m", "t"}:
                particles.append(left)
                bare.append(right)
                continue
        bare.append(w)
    en = sum(1 for w in bare if w in _EN_FUNC)
    fo = sum(1 for w in bare if w in _FOREIGN_FUNC) + len(particles)
    if fo >= 2 and fo > en:
        return False
    # Distinctive French function-word pair (le/la/les/des/du/au + another).
    if fo >= 3 and en == 0 and len(bare) >= 4:
        return False
    return True


def non_english_reason(item) -> str | None:
    h = headline(item).strip()
    if not h:
        return None
    if is_english_headline(h):
        return None
    return "non-English headline (translate to plain English or drop; original not shown untranslated)"


def is_foreign_domestic_nonthreat(item) -> str | None:
    """Foreign labor, union, wage, or similar domestic politics with no US/civilization threat."""
    if us_involved(item):
        return None
    t = _threat_text(_story_text(item))
    if _THREAT.search(t):
        return None
    cat = ""
    if isinstance(item, dict):
        cat = str(item.get("category") or "").lower()
    if _LABOR_DOMESTIC.search(_story_text(item)):
        return "foreign domestic labor/wage/union politics (not a US or civilization threat)"
    # Similar domestic political rows: no threat keywords, political category, no US hook.
    if cat == "political":
        return "foreign domestic politics (not a US or civilization threat)"
    return None


def selection_block_reason(item) -> str | None:
    """Why a story must not be picked for the brief or a social post. None = allowed (other gates still apply)."""
    if not isinstance(item, dict):
        return None
    # Prep how-tos are out of scope for these news gates.
    if item.get("kind") == "prep" or item.get("purpose") == "prep":
        return None
    return is_hard_blocked(item) or non_english_reason(item) or is_foreign_domestic_nonthreat(item)


def _token_set(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _fold(s).lower()))


def is_template_filler(what: str = "", analysis: str = "", title: str = "", from_note: bool = False) -> bool:
    """True when the writeup only restates the headline or rank, with no real facts."""
    what = (what or "").strip()
    analysis = (analysis or "").strip()
    # Strip a leading "Analysis: " label if the renderer left it in.
    analysis_body = re.sub(r"^\s*analysis:\s*", "", analysis, flags=re.I)
    looks_template = bool(
        _FILLER_WHAT.search(what)
        or _FILLER_ANALYSIS.search(analysis_body)
        or _WHY_RANKED.search(what)
        or _WHY_RANKED.search(analysis_body)
    )
    if from_note and not looks_template and fact_bearing(what, analysis_body, title):
        return False
    if not looks_template:
        # High overlap with the headline and no extra facts is also filler.
        if what and title and not fact_bearing(what, analysis_body, title):
            tw, th = _token_set(what), _token_set(title)
            if th and tw and len(tw & th) / max(1, min(len(tw), len(th))) >= 0.7:
                return True
        return False
    return not fact_bearing(what, analysis_body, title)


def fact_bearing(what: str, analysis: str, title: str = "") -> bool:
    """True when the text adds facts beyond the headline and rank/history boilerplate."""
    blob = _fold(f"{what or ''} {analysis or ''}")
    blob = re.sub(_HISTORY_BOILER, " ", blob)
    blob = re.sub(r"\bon the record(?:\s+for|\s*\()[^:]{0,160}:", " ", blob, flags=re.I)
    blob = re.sub(_FILLER_ANALYSIS, " ", blob)
    blob = re.sub(r"\brank\s+\d{1,2}\s*/\s*10\b", " ", blob, flags=re.I)
    blob = re.sub(r"\b\d{1,2}/10\b", " ", blob)
    blob = re.sub('[%s]([^%s]{0,240})[%s]' % ('\"\u201c\u201d\u2018\u2019', '\"\u201c\u201d\u2018\u2019', '\"\u201c\u201d\u2018\u2019'), ' ', blob)
    blob = re.sub(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b", " ", blob, flags=re.I)
    blob = re.sub(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)?\s*(?:ET|EST|EDT|UTC|Z)?\b", " ", blob, flags=re.I)
    blob = re.sub(r"\b(?:24h|7d|30d)\b", " ", blob, flags=re.I)
    residual = blob
    for tok in _token_set(title):
        residual = re.sub(r"\b" + re.escape(tok) + r"\b", " ", residual, flags=re.I)
    residual = re.sub(r"[\u2026.]+", " ", residual)
    residual = re.sub(r"\s+", " ", residual).strip()
    if re.search(r"\bM\s*\d(?:\.\d)?\b", residual):
        return True
    if re.search(r"\b\d[\d,]*\s+(?:dead|deaths|killed|injured|wounded|cases|patients|people|civilians|soldiers)\b", residual, re.I):
        return True
    if re.search(r"\b(?:indicted|charged|arrested|summoned|shot down|intercepted|declared|evacuated|imposed sanctions)\b", residual, re.I):
        return True
    if re.search(r"\b(?:deaths|cases|rank) stated in the reports (?:rose|fell)\b", residual, re.I):
        return True
    stop = {
        "the", "reports", "describe", "a", "an", "in", "of", "for", "and", "or", "on",
        "record", "government", "action", "use", "force", "natural", "hazard", "event",
        "confidence", "low", "medium", "high", "cluster", "first", "seen", "source",
        "families", "family", "independent", "confirmation", "lists", "official",
        "to", "from", "at", "by", "with", "as", "is", "are", "was", "were", "it",
        "this", "that", "le", "la", "les", "des", "du", "au", "aux", "un", "une",
        "et", "pas", "que", "qui",
    }
    words = [w for w in re.findall(r"[A-Za-z0-9]+", residual) if w.lower() not in stop]
    return len(words) >= 8

def _displayed_writeup(item):
    if not isinstance(item, dict):
        return "", "", "", False
    a = item.get("analyst") or {}
    what = a.get("what") or a.get("what_happened") or item.get("what") or ""
    analysis = a.get("analysis") or ""
    title = item.get("display_title") or item.get("title") or item.get("headline") or ""
    from_note = bool(item.get("from_note") or a.get("from_note"))
    return what, analysis, title, from_note


def headline_has_facts(title: str) -> bool:
    """A headline that already states a concrete figure or official action is fact-bearing."""
    t = title or ""
    if re.search(r"\bM\s*\d(?:\.\d)?\b", t):
        return True
    if re.search(r"\b\d[\d,]*\s+(?:dead|deaths|killed|injured|wounded|cases|patients|people|civilians)\b", t, re.I):
        return True
    if re.search(r"\b(?:indicted|charged|arrested|summoned|shot down|intercepted|evacuated|imposed sanctions)\b", t, re.I):
        return True
    return False


def scrub_filler(item) -> None:
    """Remove template what/analysis/why so a kept item cannot show filler copy."""
    if not isinstance(item, dict):
        return
    a = item.get("analyst") or {}
    title = item.get("display_title") or item.get("title") or item.get("headline") or ""
    if is_template_filler(a.get("what") or a.get("what_short") or "", a.get("analysis") or a.get("analysis_short") or "", title, from_note=False):
        salvage = (item.get("what") or "").strip()
        if salvage and fact_bearing(salvage, "", title):
            a["what"] = salvage
        else:
            a["what"] = ""
        a["analysis"] = ""
        a["what_short"] = ""
        a["analysis_short"] = ""
        a["outlook"] = a.get("outlook") if fact_bearing("", a.get("outlook") or "", title) else ""
        item["analyst"] = a
    if _WHY_RANKED.search(item.get("why") or "") or _WHY_RANKED.search((item.get("analyst") or {}).get("takeaway") or ""):
        item["why"] = ""
        if isinstance(item.get("analyst"), dict):
            item["analyst"]["takeaway"] = ""


def item_drop_reason(item) -> str | None:
    """Selection blocks always drop. Template filler is stripped so it cannot appear; the item
    stays when it otherwise qualified, unless the writeup is a fake analyst note or a
    'Today in History' style non-current item with no real facts."""
    why = selection_block_reason(item)
    if why:
        return why
    if not isinstance(item, dict):
        return None
    what, analysis, title, from_note = _displayed_writeup(item)
    if not is_template_filler(what, analysis, title, from_note=from_note):
        return None
    # A notes file that itself copied the template should not ship.
    if from_note:
        return "template-filler analysis (restates headline or rank, no real facts)"
    if re.search(r"^today in history\b|^on this day\b|\b\d+(?:st|nd|rd|th)\s+anniversary\b|wreath ceremony honors", title or "", re.I):
        return "historical commemoration, not a current threat"
    salvage = (item.get("what") or "").strip()
    if fact_bearing(salvage, "", title) or headline_has_facts(title) or title.strip():
        scrub_filler(item)
        return None
    return "template-filler analysis (restates headline or rank, no real facts)"


def prune_issue(issue) -> list:
    """Drop blocked, non-English, non-threat foreign-domestic, and filler items from a built issue.

    Returns a list of (section, cluster_id, title, reason) for the dry-run log.
    """
    dropped = []
    if not isinstance(issue, dict):
        return dropped
    for sec in _SECTIONS:
        kept = []
        for it in issue.get(sec) or []:
            why = item_drop_reason(it)
            if why:
                dropped.append((sec, str(it.get("cluster_id") or ""), headline(it)[:160], why))
            else:
                kept.append(it)
        issue[sec] = kept
    drop_ids = {cid for _, cid, _, _ in dropped if cid}
    an = issue.get("analysis")
    if isinstance(an, dict) and an.get("items"):
        an["items"] = [x for x in an["items"] if str(x.get("cluster_id") or "") not in drop_ids]
    has = any(issue.get(sec) for sec in _SECTIONS if sec != "watchlist")
    issue["quiet"] = not has
    # A quiet issue can still go out (standing rule); empty is reserved for a total miss.
    return dropped
