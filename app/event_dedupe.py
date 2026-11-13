"""One event = one card (Matt, Nov 13 2026). Shared same-event matching for the newsletter (newsletter.py, newsletter_qa.py) and,
later, the homepage, carousel and feeds. Pure functions over plain dicts; no I/O, no network.

An item is a dict with any of: cluster_id, story_id, title, where, when (datetime or ISO string), rank, category, people (slugs).
Two items are the same event when (first match wins, the reason is returned):
  1. same cluster_id or same story_id (story_reports alias / canonical id)
  2. same place + same event type (car bomb, earthquake, outbreak, ...) within 48 h
  3. same named outbreak/hazard (Ebola, H5N1, a named storm) and no conflicting place, within 48 h
  4. shared named people + shared place, or 2+ shared named people, with some headline overlap
  5. near-identical headlines (word overlap >= 0.6)
"""
import re
from datetime import datetime, timezone

WINDOW_H = 48

# Event types read from the headline. Broad news categories (political, war) are NOT event types on purpose:
# "Washington" + "political" would merge unrelated stories.
EVENT_TYPES = (
    ("bombing", r"car[- ]?bomb|bomb(?:s|ing|ed|er)?\b|blast|explosion|explosive|ied\b"),
    ("shooting", r"shoot(?:ing|er|s)?\b|gunm[ae]n|gunfire|shot dead|opened fire"),
    ("stabbing", r"stab(?:bing|bed|s)?\b|knife attack"),
    ("quake", r"earthquake|quake|magnitude \d|tremor|aftershock"),
    ("tsunami", r"tsunami"),
    ("eruption", r"volcan|eruption|erupts"),
    ("storm", r"hurricane|typhoon|cyclone|tornado|tropical storm"),
    ("flood", r"flood|flash flood|landslide|mudslide"),
    ("wildfire", r"wildfire|bushfire|forest fire"),
    ("fire", r"\bfire\b|blaze|on fire|ablaze"),
    ("outbreak", r"outbreak|epidemic|cases\b|infect|vaccin|ebola|marburg|cholera|measles|mpox|h5n1|bird flu|avian flu|dengue|polio"),
    ("cyber", r"ransomware|cyber ?attack|hack(?:ed|ers?)?\b|data breach|ddos"),
    ("crash", r"plane crash|crash(?:es|ed)?\b|derail|collision|capsiz"),
    ("strike", r"missile|airstrike|air strike|drone (?:strike|attack)|drones? (?:hit|struck|set)|shelling|rocket"),
    ("killing", r"assassinat|killed in (?:an? )?attack|murder"),
    ("hostage", r"hostage|kidnap|abduct"),
)
NAMED_HAZARDS = (r"ebola", r"marburg", r"cholera", r"measles", r"mpox", r"h5n1|bird flu|avian (?:flu|influenza)", r"dengue", r"polio",
                 r"(?:hurricane|typhoon|cyclone|storm) [A-Z][a-z]+")
_STOP = set("a an the of in on at to for from by with and or but as is are was were be been it its this that these those after before over "
            "near says said say new more than into about up out off amid against what who how why when where".split())
_NOPLACE = re.compile(r"not (?:specified|reported|recorded)|unknown|^none$|^n/?a$|^global$|^worldwide$", re.I)


def _t(x):
    if isinstance(x, datetime): return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if not x: return None
    try: return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception: return None


def words(title):
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if w not in _STOP and len(w) > 2}


def overlap(a, b):
    A, B = words(a), words(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def event_types(title):
    t = (title or "").lower()
    return {name for name, rx in EVENT_TYPES if re.search(rx, t)}


def hazards(title):
    out = set()
    for rx in NAMED_HAZARDS:
        m = re.search(rx, title or "", 0 if "[A-Z]" in rx else re.I)
        if m: out.add(m.group(0).lower())
    return out


def places(it, gazetteer=None):
    """Lower-case place names for an item: its location (each comma part) plus place names found in the headline.
    gazetteer: optional callable(title) -> list of place names (the newsletter passes its own headline place finder)."""
    out = set()
    loc = str(it.get("where") or it.get("location") or "").strip()
    if loc and not _NOPLACE.search(loc):
        parts = [p.strip().lower() for p in loc.split(",") if p.strip()]
        if parts: out.add(parts[0])   # the most specific part only: "Moscow, Russia" must not match every Russia story
    title = it.get("title") or ""
    if gazetteer:
        try: out |= {str(p).split(",")[0].strip().lower() for p in (gazetteer(title) or []) if p}
        except Exception: pass
    for p in list(out):
        if p and not re.search(r"\b" + re.escape(p) + r"\b", title.lower()) and p not in parts_of(loc):
            out.discard(p)
    return {p for p in out if len(p) > 2}


def parts_of(loc):
    return {p.strip().lower() for p in str(loc or "").split(",") if p.strip()}


def _named_in(p, it):
    txt = " ".join(str(it.get(k) or "") for k in ("title", "where", "location")).lower()
    return bool(re.search(r"\b" + re.escape(p) + r"(?!['\w])", txt))


def shared_places(pa, pb, a, b):
    """Places both items name: the same resolved place, or one item's place written in the other's headline/location
    (a gazetteer can miss "The Moscow bombing victim ..." while the other card resolved Moscow)."""
    return (pa & pb) | {p for p in pa if _named_in(p, b)} | {p for p in pb if _named_in(p, a)}


def _within(a, b, hours=WINDOW_H):
    ta, tb = _t(a.get("when")), _t(b.get("when"))
    if not ta or not tb: return True   # one issue / one feed window is already <= 48 h
    return abs((ta - tb).total_seconds()) <= hours * 3600


def same_event(a, b, gazetteer=None):
    """Reason string when a and b describe the same event, else None."""
    if a is b: return None
    ca, cb = a.get("cluster_id"), b.get("cluster_id")
    if ca and cb and ca == cb: return "same cluster id"
    sa, sb = a.get("story_id") or ca, b.get("story_id") or cb
    if sa and sb and sa == sb: return "same story id"
    ta, tb = a.get("title") or "", b.get("title") or ""
    if not ta or not tb: return None
    if not _within(a, b): return None
    pa, pb = places(a, gazetteer), places(b, gazetteer)
    shared_place = shared_places(pa, pb, a, b)
    ev = event_types(ta) & event_types(tb)
    if shared_place and ev: return f"same place ({sorted(shared_place)[0]}) and event type ({sorted(ev)[0]})"
    hz = hazards(ta) & hazards(tb)
    if hz and (shared_place or not pa or not pb): return f"same named hazard ({sorted(hz)[0]})"
    ppl = set(a.get("people") or []) & set(b.get("people") or [])
    ov = overlap(ta, tb)
    if ppl and shared_place and (ev or ov >= 0.15): return f"shared people ({', '.join(sorted(ppl))}) and place ({sorted(shared_place)[0]})"
    if len(ppl) >= 2 and ov >= 0.2: return f"shared people ({', '.join(sorted(ppl))})"
    if ov >= 0.6: return "near-identical headlines"
    return None


def merge(items, gazetteer=None, priority=None):
    """Fold same-event items into the strongest one. items: ordered list (earlier = preferred on equal rank).
    priority: optional key(item) -> sortable, lower first (default: higher rank, then list order).
    Returns (kept, folded) where folded = [(kept_item, dropped_item, reason)]. Items are not copied or mutated."""
    order = {id(it): i for i, it in enumerate(items)}
    key = priority or (lambda it: (-int(it.get("rank") or 0), order[id(it)]))
    kept, folded = [], []
    for it in sorted(items, key=key):
        hit = None
        for k in kept:
            r = same_event(k, it, gazetteer)
            if r: hit = (k, r); break
        if hit: folded.append((hit[0], it, hit[1]))
        else: kept.append(it)
    keep_ids = {id(k) for k in kept}
    return [it for it in items if id(it) in keep_ids], folded


def duplicates(items, gazetteer=None):
    """Every same-event pair in a list: [(a, b, reason)]. Used by QA gates."""
    out = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            r = same_event(a, b, gazetteer)
            if r: out.append((a, b, r))
    return out
