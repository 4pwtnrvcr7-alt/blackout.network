"""Server-side factual-text location enrichment (v11, Matt pt1718u).
Reads the same published desk/API brief as /wire/<id>. Offline, no network or DB writes.
No guesses from institution headquarters, source outlet names, advice or analysis.
geo.db can continue syncing from the Mac; a stale missing location cannot hide a
place named in a published write-up. Cache keys include the actual prose, so a
new/changed write-up takes effect without a restart or another Mac install.
"""
import hashlib, json, re, threading
import geo
_CACHE = {}
NO_COUNTRY_CATS = {'cyber', 'space weather'}   # 'Canada's cyber centre also warned': an issuer, not where it happened
CUE_RC = {'not_found', 'no_place', 'pending', 'none', 'archive', 'geocoder_error'}
SPAN_RC = {'not_found', 'no_place', 'non_geo', 'pending', 'none', 'archive', 'geocoder_error'}
_LOCK = threading.RLock()

def note_for(cid):
    try:
        import story_v3 as V
        n = V.note_for(cid)
        if isinstance(n, dict): return n
    except Exception: pass
    # story_report.render resolves aliases too (v3's legacy helper doesn't).
    try:
        import story_report as S
        d = S.reports(); n = (d.get('notes') or {})
        v = n.get(cid) or n.get((d.get('alias') or {}).get(cid, ''))
        if isinstance(v, dict): return v
    except Exception: pass
    return {}

def factual_text(cid):
    """(lede text, more factual prose): the same "What happened" the story page prints (Story v3 sections.happened, else the
    brief's what_happened). Never background (earlier events elsewhere), analysis, advice or the page's generated "N sources are
    reporting" fallback."""
    n = note_for(cid) or {}
    story = n.get('story') if isinstance(n.get('story'), dict) else {}
    secs = story.get('sections') if isinstance(story.get('sections'), dict) else {}
    w = secs.get('happened') or n.get('what_happened') or ''
    body = ''
    if not isinstance(w, str): w = ''
    if not isinstance(body, str): body = ''
    if _TEMPLATE.match(w.strip()): w = ''
    return w, body

_TEMPLATE = re.compile(r"^(?:\d+ independent sources? (?:is|are) reporting this|This page was created by our scanner)")

def enrich(item, old=None, members=(), lede_only=False):
    """geo.db-shaped row or old. Never override source point/county/state/city pins.
    A specific city in a write-up can refine a country-only pin, in that country.
    """
    if old and old.get('located') and old.get('precision') not in ('country',): return old
    cid = item.get('id') or item.get('cluster_id')
    w, body = factual_text(cid)
    title = item.get('title') or ''
    summary = item.get('brief') or item.get('summary') or ''
    loc = item.get('loc') or item.get('location') or ''
    # Published write-up ledes (desk, Story v3 or the instant writer): gazetteer on the lede, then places the later sentences mark
    # with "in / near / at". Titles and the scanner summary were already read by the Mac's geocoder (with member titles and
    # Nominatim); re-reading them here would undo its v10 decisions, so they only feed the small-town table, and only when the
    # Mac found nothing.
    texts = geo.lead_sentences(w) + geo.lead_sentences(body)
    span_texts = []
    if not (old and old.get('located')) and ((old or {}).get('reason_code') or 'none') in SPAN_RC:
        span_texts = [title, geo.brief_where(summary)]
    # no write-up and the Mac found no place at all: a place the headline or summary marks with "in / near / at" (cue only)
    cue_tail = []
    if not texts and span_texts and ((old or {}).get('reason_code') or 'none') in CUE_RC:
        cue_tail = [t for t in span_texts if t]
    if not texts and not span_texts: return old
    if not members:
        links = item.get('links') or []
        try: links = json.loads(links) if isinstance(links, str) else links
        except Exception: links = []
        members = [{'source': x.get('source') or x.get('s'), 'source_url': x.get('url') or x.get('u')} for x in links if isinstance(x,dict)]
    key = hashlib.sha256(json.dumps([cid, lede_only, title, texts, span_texts, cue_tail, members, (old or {}).get('country'), (old or {}).get('admin1_code')], sort_keys=True, default=str).encode()).hexdigest()
    with _LOCK:
        if key in _CACHE: return _CACHE[key] or old
    r = geo.locate_texts({'cluster_id': cid, 'title': title}, texts or cue_tail, members, cue_only=not texts,
                          method='gazetteer', what="the story's published write-up" if texts else "the headline (offline town table)", span_texts=span_texts, refine=bool(lede_only or (old and old.get('located'))))
    rc0 = (old or {}).get('reason_code') or 'none'
    if not r and not texts and title and not (old and old.get('located')) and rc0 in SPAN_RC and (item.get('category') or '').lower() not in NO_COUNTRY_CATS:
        # no write-up: the headline under today's rules on the server ("A Krasnoyarsk apartment ...", "Canary Islands state of emergency"),
        # so a rules fix reaches the map without waiting for the Mac's geocoder. Only when the Mac found no place (never ambiguous/multi-place).
        r = geo.locate_texts({'cluster_id': cid, 'title': title}, [title], members, method='gazetteer', what="the headline (server re-read, v11 rules)")
    if not r and texts and not lede_only and not (old and old.get('located')) and (item.get('category') or '').lower() not in NO_COUNTRY_CATS:
        # the write-up names exactly one country and nothing finer ("a call from Ghana's Catholic bishops"): that country, approximate
        ccs = set()
        for t in texts: ccs |= {c for c in geo._named_countries(t) if c and len(c) == 2}
        if len(ccs) == 1:
            G = geo.gaz(); cc = next(iter(ccs)); lab = (G.countries.get(cc) or {}).get('label')
            if lab:
                r = {'id': cid, 'lat': lab[0], 'lon': lab[1], 'place': G.countries[cc].get('name', cc), 'country': cc, 'country_name': G.countries[cc].get('name', cc),
                     'admin1': None, 'admin1_code': None, 'city': None, 'precision': 'country', 'method': 'gazetteer',
                     'method_detail': "the story's published write-up (only country named)", 'confidence': 'medium', 'located': 1,
                     'reason_code': None, 'reason_unlocated': None, 'candidates': None, 'evidence': 'write-up names only ' + cc}
    if not r and cue_tail:
        r = _us_state_abbrev(cid, title)
    if r and old and old.get('located'):
        # refine only: same country, same state when the Mac had one, and finer than what it had
        if r.get('country') != old.get('country') or r.get('precision') == 'country' or (old.get('admin1_code') and r.get('admin1_code') != old.get('admin1_code')): r = None
    if r: r['geocoded_at'] = geo.iso(geo.now())
    with _LOCK:
        if len(_CACHE)>20000: _CACHE.clear()
        _CACHE[key] = r
    return r or old

# AP-style state abbreviations that lead a headline ("Ill. Judge Wary Of Sanctions ...", Law360) or a direction + postal code
# ("flooding in North GA"). State level, never a town.
AP_STATES = {"Ala": "AL", "Ariz": "AZ", "Ark": "AR", "Calif": "CA", "Colo": "CO", "Conn": "CT", "Del": "DE", "Fla": "FL", "Ga": "GA", "Ill": "IL",
             "Ind": "IN", "Kan": "KS", "Ky": "KY", "La": "LA", "Md": "MD", "Mass": "MA", "Mich": "MI", "Minn": "MN", "Miss": "MS", "Mo": "MO",
             "Mont": "MT", "Neb": "NE", "Nev": "NV", "N.H": "NH", "N.J": "NJ", "N.M": "NM", "N.Y": "NY", "N.C": "NC", "N.D": "ND", "Okla": "OK",
             "Ore": "OR", "Pa": "PA", "R.I": "RI", "S.C": "SC", "S.D": "SD", "Tenn": "TN", "Tex": "TX", "Vt": "VT", "Va": "VA", "Wash": "WA",
             "W.Va": "WV", "Wis": "WI", "Wyo": "WY"}
_AP = re.compile(r"^(" + "|".join(re.escape(k) for k in sorted(AP_STATES, key=len, reverse=True)) + r")\. (?:[A-Z][a-z]+)")
_DIRPOST = re.compile(r"\b(?:North|South|East|West|Central|Northeast|Northwest|Southeast|Southwest|Northern|Southern|Eastern|Western) ([A-Z]{2})\b")
def _us_state_abbrev(cid, title):
    t = (title or "").strip()
    m = _AP.match(t); st = AP_STATES.get(m.group(1)) if m else None
    if not st:
        m = _DIRPOST.search(t); st = m.group(1) if m and m.group(1) in geo.US_POSTAL else None
    if not st: return None
    G = geo.gaz(); a1 = geo.US_POSTAL.get(st); a = G.admin1.get(a1) or {}; lab = a.get("label")
    if not lab: return None
    return {"id": cid, "lat": lab[0], "lon": lab[1], "place": f"{a.get('name', st)}, United States", "country": "US", "country_name": "United States",
            "admin1": a.get("name"), "admin1_code": a1, "city": None, "precision": "state", "method": "gazetteer",
            "method_detail": "headline state abbreviation", "confidence": "medium", "located": 1, "reason_code": None, "reason_unlocated": None,
            "candidates": None, "evidence": f"matched \"{m.group(0)}\""}
