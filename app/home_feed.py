"""Homepage feed: one card per real event, plus "Follow this story" links (display/API layer only).

Why the homepage showed duplicates (Nov 8): the scanner opens a new cluster whenever a later report doesn't match an
existing cluster closely enough, so one event can live in several clusters ("Paraguay Bank Failure", "Paraguay: President
under investigation for bank failure", "Ousted Paraguayan president placed under house arrest..."), several agencies report
the same quake (JMA + EMSC + a news story), NWS re-issues the same warning for the same county, and the Nov 7 cutover
catch-up re-ingested a backlog with the same first_seen. /api/state lists clusters, and the homepage row only grouped quakes.

This module collapses those clusters into events here, at display time (SITE-DEDUPE-1). Other angles of the same event
become one "Also:" line on the kept card (event_dedupe, same matcher as the newsletter). It never changes the scanner, its
scores or the DB (read-only, file:...?mode=ro), and it never invents anything: every card is a real cluster, shown with its own rank.

Social links: the box posts each story to X and YouTube, verifies the links (HTTP 200 via oEmbed, deleted posts skipped) and
pushes social_links.json over the signed sync channel (render_sync, pattern social_*.json). A link is rendered only when the
file marks it ok and it matches the strict URL patterns below. tools/home_linkcheck.py re-checks them after each slot and hides
any broken one."""
import os, re, json, math, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
F_LINKS = os.path.join(BASE, "social_links.json")
HTTPS = "^https:" + "//"   # split so the link gate doesn't read the patterns below as URLs
X_RE = re.compile(HTTPS + r"(x|twitter)\.com/BlkoutNtw/status/\d{5,25}$", re.I)
YT_RE = re.compile(HTTPS + r"(www\.)?youtube\.com/(shorts/|watch\?v=)[A-Za-z0-9_\-]{11}$")
CID_RE = re.compile(r"^[0-9a-f]{16}$")
# Social posting slots, America/New_York (Matt, Nov 8): the homepage pins the stories posted in these slots.
SLOTS_ET = ["08:00", "11:00", "14:00", "16:00", "20:00", "22:00"]
PIN_HOURS = 24          # a posted story stays pinned at the front of the row this long
PIN_MAX = 3
# Latest-row freshness (Matt, Nov 8): keep the homepage in step with the 6x-daily social schedule.
LATEST_FRESH_H = 48     # prefer events updated within this window
LATEST_WIDEN_H = 72     # if fewer than 6 qualify, widen to this; never older
LATEST_STALE_H = 24     # an item older than this cannot outrank a fresher item of equal or rank-1 lower
LATEST_MIN = 6

def _ts(iso):
    try: return datetime.strptime(str(iso)[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return None

# ------------------------------------------------------------------ titles
_EMOJI = re.compile("[\u2190-\u21FF\u2300-\u23FF\u2460-\u27BF\u2900-\u2BFF\uFE0F\u200d\U0001F000-\U0001FAFF]")
_BAD = re.compile(r"(\bf\W?u?c?k|\bf\*ck|\bshit|\bdamn|\[live\]|\blive:|\bwatch:|blueanon|\bmaga\b|^\W*(rt|breaking)\b)", re.I)
_URLISH = re.compile(r"^(https?:|www\.|[a-z0-9\-]+\.(com|net|org|io|co|tv|news|be|ly|gov)\b/)", re.I)

def clean_title(t):
    """Display headline or None when the item is not a usable headline (URL-only, emoji post, profanity, shouting, too short)."""
    t = str(t or "").strip()
    first = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
    if not first or _URLISH.match(first): return None
    first = re.sub(r"\s+", " ", first)
    first = re.sub(r"^[^A-Za-z0-9\"'(]+", "", first)          # leading flags, emoji, bolts and dashes
    if _BAD.search(first) or _EMOJI.search(first): return None
    if len(first) < 20: return None
    letters = sum(ch.isalpha() for ch in first)
    if letters and sum(ch.isupper() for ch in first) > 0.6 * letters: return None
    first = re.sub(r"\s+\|\s+[A-Z][\w .&'-]{1,40}$", "", first).strip()
    try:
        import site_page as SP; first = SP.clean_title(first)
    except Exception: pass
    return first[:180]

# ------------------------------------------------------------------ stale NWS products
_MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
_TZ = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7, "AKST": -9, "AKDT": -8, "HST": -10, "CHST": 10, "SST": -11}
_NWS = re.compile(r"^(?P<prod>[A-Za-z /]+?(Warning|Watch|Advisory|Statement|Emergency))\s+issued\s+(?P<iss>[A-Za-z]+ \d{1,2} at \d{1,2}:\d{2}[AP]M [A-Z]{2,4})"
                  r"(\s+until\s+(?P<until>[A-Za-z]+ \d{1,2} at \d{1,2}:\d{2}[AP]M [A-Z]{2,4}))?\s+by\s+NWS", re.I)

def _nws_time(s, ref):
    m = re.match(r"([A-Za-z]+) (\d{1,2}) at (\d{1,2}):(\d{2})([AP]M) ([A-Z]{2,4})", s or "")
    if not m or m.group(1).lower() not in _MON: return None
    mon, day, hh, mm, ap, tz = _MON[m.group(1).lower()], int(m.group(2)), int(m.group(3)) % 12, int(m.group(4)), m.group(5).upper(), m.group(6).upper()
    hh += 12 if ap == "PM" else 0
    y = datetime.fromtimestamp(ref, timezone.utc).year
    try: t = datetime(y, mon, day, hh, mm, tzinfo=timezone.utc).timestamp() - _TZ.get(tz, -5) * 3600
    except ValueError: return None
    if t - ref > 200 * 86400: t = datetime(y - 1, mon, day, hh, mm, tzinfo=timezone.utc).timestamp() - _TZ.get(tz, -5) * 3600
    return t

def nws(title):
    m = _NWS.match(str(title or "").strip())
    return m.groupdict() if m else None

def stale(x, now):
    """True for NWS warnings that have already expired (or were issued 48+ h ago with no end time): not useful on the homepage."""
    p = nws(x.get("title"))
    if not p: return False
    if p.get("until"):
        u = _nws_time(p["until"], now)
        return u is not None and u < now
    i = _nws_time(p["iss"], now)
    return i is not None and now - i > 48 * 3600

# ------------------------------------------------------------------ event grouping
_STOP = set("""a an and the of to in on at for by from with as is are was were be been being it its this that these those after amid over
under into about than then near more most new news says said say report reports reported update updates live breaking video watch
via per vs who what when where why how will would could can may might has have had not no yes all any some other others out up down
off just also first last latest today tonight yesterday week day days hours hour year years amp his her their they them he she we our
us u.s you your i""".split())
_ALIAS = {"kanto": "japan", "honshu": "japan", "tokyo": "japan", "ibaraki": "japan", "hokkaido": "japan", "kyushu": "japan", "japanese": "japan",
          "kyiv": "ukrain", "kiev": "ukrain", "ukrainian": "ukrain", "russian": "russia", "iranian": "iran", "israeli": "israel",
          "paraguayan": "paragua", "venezuelan": "venezue", "belizean": "belize", "chinese": "china", "american": "america"}
_QUAKE = re.compile(r"\b(earthquake|quake|seismic)\b|^(m ?\d|[A-Z]{2,7}: m ?\d)", re.I)
_MAG = re.compile(r"\b(?:m|magnitude|mag\.?)\s*-?\s*(\d(?:\.\d)?)\b", re.I)

def _stem(w):
    if w in _ALIAS: return _ALIAS[w]
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf) and not w.endswith("ss"): w = w[: -len(suf)]; break
    if len(w) > 7 and w.endswith("an"): w = w[:-2]
    return _ALIAS.get(w, w[:7])

def tokens(t):
    t = re.sub(r"[’']s\b", "", str(t or "").lower())
    out = set()
    for w in re.findall(r"[a-z][a-z\-]+|\d+(?:\.\d+)?", t):
        if w in _STOP or len(w) < 3 and not w[0].isdigit(): continue
        for p in w.split("-"):
            if p and p not in _STOP and (len(p) >= 3 or p[0].isdigit()): out.add(_stem(p))
    return out

def _hav(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))

def _when(x): return _ts(x.get("event_time")) or _ts(x.get("first_seen")) or _ts(x.get("updated")) or 0

def _quake_same(a, b):
    ma, mb = _MAG.search(a["title"] or ""), _MAG.search(b["title"] or "")
    if not ma or not mb: return False
    dm = abs(float(ma.group(1)) - float(mb.group(1)))
    if a.get("lat") is not None and b.get("lat") is not None:      # two agency reports: same magnitude, place and time
        if dm > 0.25 or abs(_when(a) - _when(b)) > 3 * 3600: return False
        try: return _hav(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"])) <= 250
        except Exception: return False
    # a news story about a quake (no coordinates): same magnitude and a shared place name within 48 h
    if dm > 0.05 or abs(_when(a) - _when(b)) > 48 * 3600: return False
    ta = tokens((a.get("title") or "") + " " + (a.get("location") or "")); tb = tokens((b.get("title") or "") + " " + (b.get("location") or ""))
    return bool((ta & tb) - _QGENERIC - {ma.group(1)})
_QGENERIC = {_stem(w) for w in ("earthquake", "quake", "quakes", "magnitude", "coast", "east", "eastern", "west", "western", "north", "northern", "south",
             "southern", "central", "region", "near", "strike", "strikes", "intensity", "seismic", "max", "jma", "emsc", "geofon", "ingv", "usgs", "csn",
             "island", "islands", "sea", "ridge", "depth", "off", "km", "prefecture")}

def _nws_key(x):
    p = nws(x.get("title"))
    return (p["prod"].lower(), (x.get("location") or "").lower()) if p else None

def group(items, now=None):
    """items: cluster dicts (title, category, location, lat, lon, rank, n_families, updated, first_seen, cluster_id).
    Returns events (list of dicts): the strongest cluster of each event, plus `cluster_ids` (all members) and `grouped` (count)."""
    now = now or time.time()
    xs = [x for x in items if x and not stale(x, now)]
    n = len(xs); parent = list(range(n))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j):
        a, b = find(i), find(j)
        if a != b: parent[b] = a
    toks = [tokens(x.get("title")) for x in xs]
    caps = [tokens(" ".join(re.findall(r"\b[A-Z][A-Za-z\-]+", x.get("title") or ""))) for x in xs]   # capitalised words: names and places
    df = {}
    for ts in toks:
        for w in ts: df[w] = df.get(w, 0) + 1
    big = max(n, 100)      # corpus floor: weights stay stable when only a few stories are listed
    idf = {w: math.log((big + 1) / (c + 1)) + 1 for w, c in df.items()}
    rare = max(2, min(4, int(0.03 * n)))
    quake = [bool(_QUAKE.search(x.get("title") or "")) for x in xs]
    nk = [_nws_key(x) for x in xs]
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j): continue
            if quake[i] or quake[j]:
                if quake[i] and quake[j] and _quake_same(xs[i], xs[j]): union(i, j)
                continue
            if nk[i] or nk[j]:
                if nk[i] and nk[i] == nk[j] and abs(_when(xs[i]) - _when(xs[j])) <= 72 * 3600: union(i, j)
                continue
            sh = toks[i] & toks[j]
            if len(sh) < 2 or not any(df[w] <= rare and (w in caps[i] or w in caps[j]) for w in sh): continue
            if abs(_when(xs[i]) - _when(xs[j])) > 96 * 3600: continue
            s = sum(idf[w] for w in sh) / max(1e-9, min(sum(idf[w] for w in toks[i]), sum(idf[w] for w in toks[j])))
            if s >= 0.5: union(i, j)
    groups = {}
    for i in range(n): groups.setdefault(find(i), []).append(xs[i])
    out = []
    for mem in groups.values():
        mem.sort(key=lambda x: (-(int(x.get("rank") or 0)), -(int(x.get("n_families") or 0)), -(_ts(x.get("updated")) or 0)))
        rep = dict(mem[0])
        rep["cluster_ids"] = [m.get("cluster_id") for m in mem if m.get("cluster_id")]
        rep["grouped"] = len(mem)
        ups = [u for u in (_ts(m.get("updated")) for m in mem) if u]
        if ups: rep["updated"] = max(m.get("updated") for m in mem if _ts(m.get("updated")) == max(ups))
        also = list(rep.get("also") or [])
        seen = {a.get("text") for a in also}
        for m in mem[1:]:
            line = (m.get("title") or "").rstrip(" .")
            if line and line != (rep.get("title") or "") and line not in seen:
                also.append({"text": line, "cluster_id": m.get("cluster_id"), "reason": "grouped same event"})
                seen.add(line)
        if also: rep["also"] = also
        for m in mem[1:]:
            _merge_source_fields(rep, m)
        out.append(rep)
    out.sort(key=lambda x: (-(int(x.get("rank") or 0)), -(int(x.get("n_families") or 0)), -(_ts(x.get("updated")) or 0)))
    return out

def events(items, now=None, limit=40):
    """Clean titles (drop unusable ones), collapse duplicates, rank by usefulness. Titles in the result are display-clean."""
    keep = []
    for x in items:
        t = clean_title(x.get("title"))
        if t: keep.append(dict(x, title=t))
    return fold_angles(group(keep, now))[:limit]


# ------------------------------------------------------------------ one event = one card (SITE-DEDUPE-1): reuse event_dedupe, display only
def _gazetteer(title):
    """Every place a headline clearly names (countries, plus the best resolved place). Never opens the DB."""
    out = []
    try:
        import signal_place as SP
        text = SP.story_text(title or "", "", "")
        out.extend(SP.named_countries(text) or [])
        inf = SP.infer(text)
        if inf:
            if inf.get("cc"): out.append(inf["cc"])
            if inf.get("place"): out.append(inf["place"])
    except Exception:
        pass
    try:
        import story_display as SD
        loc = SD.place_from_headline(title or "")
        if loc: out.append(loc)
    except Exception:
        pass
    seen, uniq = set(), []
    for p_ in out:
        k = str(p_).strip()
        if k and k.lower() not in seen:
            seen.add(k.lower()); uniq.append(k)
    return uniq


def also_line(item):
    """One short 'Also:' sentence for angles merged into this card; empty when none."""
    a = [x["text"] for x in (item.get("also") or []) if isinstance(x, dict) and x.get("text")]
    return ("Also: " + "; ".join(a[:2]) + ".") if a else ""


def _probe(it):
    cid = it.get("cluster_id") or ""
    if not cid and isinstance(it.get("url"), str) and "/wire/" in it["url"]:
        cid = it["url"].rsplit("/", 1)[-1]
    return {"cluster_id": cid or None, "story_id": it.get("story_id") or cid or None,
            "title": it.get("title") or it.get("display_title") or "",
            "where": it.get("location") or it.get("where") or it.get("loc") or "",
            "when": it.get("event_time") or it.get("when") or it.get("updated") or it.get("first_seen") or it.get("t"),
            "rank": it.get("rank"), "people": it.get("people") or []}


def _add_also(kept, dropped, reason):
    """Fold dropped's title into kept's also list and merge cluster_ids. Mutates kept."""
    line = (dropped.get("title") or "").rstrip(" .")
    if line and line != (kept.get("title") or ""):
        kept.setdefault("also", [])
        if line not in [a.get("text") for a in kept["also"]]:
            kept["also"].append({"text": line, "cluster_id": dropped.get("cluster_id"), "reason": reason})
    ids = list(kept.get("cluster_ids") or ([kept.get("cluster_id")] if kept.get("cluster_id") else []))
    for cid in (dropped.get("cluster_ids") or ([dropped.get("cluster_id")] if dropped.get("cluster_id") else [])):
        if cid and cid not in ids:
            ids.append(cid)
    if ids:
        kept["cluster_ids"] = ids
        kept["grouped"] = max(int(kept.get("grouped") or 1), len(ids))
    _merge_source_fields(kept, dropped)


def _family_set(it):
    """Distinct source-family names on a cluster dict (list or JSON string). Empty if none are present."""
    fam = (it or {}).get("families")
    if isinstance(fam, str):
        try: fam = json.loads(fam)
        except Exception: fam = None
    if isinstance(fam, (list, tuple, set)):
        return {str(x).strip() for x in fam if str(x).strip()}
    return set()


def _merge_source_fields(kept, other):
    """Display-only: union distinct source families onto kept. If neither item lists families, add the counts."""
    if not kept or not other: return
    names = _family_set(kept) | _family_set(other)
    if names:
        kept["families"] = sorted(names)
        kept["n_families"] = len(names)
    elif not _family_set(kept):
        kept["n_families"] = int(kept.get("n_families") or 0) + int(other.get("n_families") or 0)


def source_meta(item):
    """('N sources', 'M stories merged'|None) for a card. The stories label is set only when more than one angle was folded in."""
    n = int((item or {}).get("n_families") or 0)
    src = f"{n} source" + ("" if n == 1 else "s")
    g = int((item or {}).get("grouped") or 0) or (1 + len((item or {}).get("also") or []))
    extra = f"{g} stories merged" if g > 1 else None
    return src, extra


def fold_angles(items, gazetteer=None):
    """Merge same-event cards (event_dedupe) and attach Also: lines. Display only; does not mutate scanner data.
    Items are not copied: Also: is added on the kept dicts, dropped dicts are omitted from the returned list."""
    import event_dedupe as ED
    items = list(items or [])
    if len(items) < 2:
        return items
    gz = gazetteer if gazetteer is not None else _gazetteer
    probes = [_probe(it) for it in items]
    back = {id(p): it for p, it in zip(probes, items)}
    kept, folded = ED.merge(probes, gz)
    for kp, dp, why in folded:
        _add_also(back[id(kp)], back[id(dp)], why)
    keep = {id(back[id(k)]) for k in kept}
    return [it for it in items if id(it) in keep]


def apply_source_label(item):
    """Stamp a display `src` string (combined count, plus 'N stories merged' when angles were folded)."""
    if not item: return item
    src, extra = source_meta(item)
    item["src"] = (src + " · " + extra) if extra else src
    return item


def fold_story_list(stories, gazetteer=None):
    """Same-event fold for homepage feed day lists and 'latest' lines (title + url or cluster_id)."""
    return [apply_source_label(it) for it in fold_angles(list(stories or []), gazetteer)]

# ------------------------------------------------------------------ social links (box -> Render, social_links.json)
_LC = {"m": None, "v": {}}
def links():
    """{cluster_id: {"x": url|None, "yt": url|None, "posted_at": iso, "story": "/wire/<id>"}} with only verified, not-hidden links."""
    try: m = os.path.getmtime(F_LINKS)
    except OSError: _LC.update(m=None, v={}); return {}
    if _LC["m"] == m: return _LC["v"]
    try:
        with open(F_LINKS, encoding="utf-8") as f: d = json.load(f)
    except Exception: d = {}
    out = {}
    for cid, s in ((d or {}).get("stories") or {}).items():
        if not CID_RE.match(str(cid)) or not isinstance(s, dict): continue
        if s.get("policy_ok") is not True: continue          # box topic policy (fails closed when missing)
        hid = set(s.get("hidden") or [])
        x = s.get("x_url") if s.get("x_ok") and "x" not in hid and X_RE.match(str(s.get("x_url") or "")) else None
        yt = s.get("yt_url") if s.get("yt_ok") and "yt" not in hid and YT_RE.match(str(s.get("yt_url") or "")) else None
        if not x and not yt: continue
        out[cid] = {"x": x, "yt": yt, "posted_at": s.get("posted_at"), "story": None if "site" in hid else f"/wire/{cid}"}
    _LC.update(m=m, v=out)
    return out

# Mirror of the social topic policy for the two rules Matt called out (box: /workspace/launch/social/weather_policy.py).
# The box sets policy_ok per story; this second check uses the event's current title so a quake or weather story is never
# linked or pinned even if an older social_links.json lacks the flag.
_WX = re.compile(r"\b(?:weather|storms?|hurricanes?|typhoons?|cyclones?|tornado(?:es|s)?|flood(?:ing|s| warning)?|heat advisory|heat ?wave|winter storm|"
                 r"forecast(?:s|ing)?|NWS|rain(?:fall)?|snow(?:fall)?|blizzard|deep freeze|cold snap|freeze warning|wind advisory|thunderstorm|drought|"
                 r"(?:wind|freeze|frost|flood|winter|gale|spray|surf|fire weather|heat|storm) (?:warning|watch|advisory))\b", re.I)
_FLOOD = re.compile(r"\bflood(?:ing|s)?\b", re.I)
_FLOOD_IMPACT = re.compile(r"\b(?:deaths?|dead|killed|fatalit\w*|evacuat\w*|"
                           r"state of emergency|emergency declaration|declared (?:a )?state of emergency|"
                           r"federal (?:disaster|emergency)|national (?:disaster|emergency)|disaster declaration)\b", re.I)
_QK = re.compile(r"\b(?:earthquakes?|quake|seismic|magnitude)\b|\bM\s*[4-9]\.\d", re.I)
_QIMPACT = re.compile(r"\b(?:significant|major|severe|widespread) (?:damage|destruction)\b|\b(?:[1-9]\d* (?:dead|deaths|killed|injured)|fatalities|casualties reported|tsunami (?:warning|threat))\b", re.I)
_QNEG = re.compile(r"\b(?:no|without|zero|not any)\b.{0,35}(?:damage|casualties|fatalities|tsunami|deaths|killed|injured)", re.I)
_QUS = re.compile(r"\b(?:Los Angeles|San Francisco|San Diego|Seattle|Portland, Oregon|Anchorage|Honolulu|Salt Lake City|San Juan, Puerto Rico)\b", re.I)
# Evergreen SEO / health-reference explainers: keep off the latest row unless an active outbreak with 2+ sources.
_EXPLAINER = re.compile(r"(?::\s*Causes?,\s*(?:symptoms?,\s*)?(?:warning signs|signs and what|treatment)|"
                        r"\bCauses?,\s*(?:warning )?signs\b|"
                        r"\bWhat is\b|\bHow to\b|"
                        r"\b(?:\d+|Top)\s+(?:ways|tips|things|reasons|signs|causes)\b|"
                        r"\blisticles?\b|\bsymptoms and treatment\b|\bwarning signs and what you can do\b)", re.I)
_OUTBREAK = re.compile(r"\b(?:outbreak|epidemic|pandemic|cluster of|ebola|marburg|h5n1|h9n2|avian|bird flu|measles|cholera|mpox|polio)\b", re.I)

def topic_ok(title, summary=""):
    """False for routine weather / NWS products and for quakes below M7 without real damage, a tsunami threat, or M5.5+ in a populated US area.
    Floods are allowed only with deaths, evacuations, or a federal/state emergency declaration in the title/summary."""
    title = str(title or ""); blob = (title + " " + str(summary or "")).strip()
    if nws(title): return False
    if _FLOOD.search(blob) and _FLOOD_IMPACT.search(blob): return True
    if _WX.search(blob): return False
    if _QK.search(blob):
        m = re.search(r"\b(?:M\s*|magnitude\s*)(\d(?:\.\d)?)", blob, re.I); mag = float(m.group(1)) if m else 0
        return mag >= 7 or bool(_QIMPACT.search(blob) and not _QNEG.search(blob)) or (mag >= 5.5 and bool(_QUS.search(blob)))
    return True

def explainer_junk(item):
    """True for evergreen explainer / health-reference / SEO titles, unless an active outbreak with 2+ sources."""
    t = str((item or {}).get("title") or "")
    if not _EXPLAINER.search(t): return False
    if int((item or {}).get("n_families") or 0) >= 2 and _OUTBREAK.search(t): return False
    return True

# ------------------------------------------------------------------ top-row junk + repeat filter (Matt, Nov 13: "stop posting duplicate stories in the top")
# Display only: never changes scanner.py scoring, the DB or any cluster. Off with BN_HOME_ROW_FILTER=0.
ROW_BLOCK = {"ff9e5add02c443c4"}   # Snyder "Trump's Next Coup Attempt" (Project Syndicate opinion column via a blog repost): scanner false positive
_ROW_URL = re.compile(r"https?:|\bwww\.|\b[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.(?:com|net|org|io|co|tv|news|be|ly|gov|info|me|us|uk|de|ru|ua|blog)/", re.I)
_ROW_LIVE = re.compile(r"\bLIVE\s*\]|\[\s*LIVE\b|\bLIVE\s*:|\bLIVE\s*$|\blive ?stream(?:ing)?\b|\blive (?:updates|coverage|blog)\b|\bwatch live\b|\bspeech live\b", re.I)
_ROW_LIVE_CAPS = re.compile(r"\bLIVE\b")    # all-caps LIVE anywhere is a broadcast/stream title ("Trump Speech LIVE")
_ROW_OPINION = re.compile(r"\bProject Syndicate\b|^\s*opinion\b|\|\s*opinion\b|\bop-?ed\b|\bcolumn(?:ist)?\s*:|\bcommentary\s*:|\beditorial\s*:|\bguest essay\b", re.I)
_ROW_HISTORY = re.compile(r"\btoday in history\b|\bthis day in history\b|\bon this day\b|\byears ago today\b", re.I)
# Same-theme keys: the top row shows one card per outbreak / attack type, so several reports of one thread (Ebola totals, plots,
# car bombings) do not fill it. The Wire still lists every cluster.
_THEMES = (("outbreak:ebola", r"\bebola\b"), ("outbreak:marburg", r"\bmarburg\b"), ("outbreak:cholera", r"\bcholera\b"),
           ("outbreak:mpox", r"\bmpox\b"), ("outbreak:measles", r"\bmeasles\b"), ("outbreak:h5n1", r"\b(?:h5n1|bird flu|avian (?:flu|influenza))\b"),
           ("outbreak:polio", r"\bpolio\b"), ("outbreak:dengue", r"\bdengue\b"),
           ("attack:assassination", r"\bassassinat\w*|\bplot(?:ted|ting)? to (?:kill|murder)\b|\bmurder plot\b|\bkill(?:ing)? plot\b"),
           ("attack:car-bomb", r"\bcar (?:bomb\w*|explo\w+|blast)|\bcar (?:was |has )?(?:blown up|exploded)\b|\bvehicle[- ]borne\b"),
           ("coup", r"\bcoup(?: attempt| d'?\u00e9tat| plot)?\b"))
_THEMES = tuple((k, re.compile(r, re.I)) for k, r in _THEMES)

def row_filter_on():
    return os.environ.get("BN_HOME_ROW_FILTER", "1") != "0"

def row_junk(item):
    """True for titles that are not headlines for the top row: URLs / domain paths, livestream titles, opinion columns,
    history features, and the explicit ROW_BLOCK list."""
    if not row_filter_on(): return False
    item = item or {}
    ids = set(item.get("cluster_ids") or []) | {item.get("cluster_id")}
    if ids & ROW_BLOCK: return True
    t = str(item.get("title") or "")
    return bool(_ROW_URL.search(t) or _ROW_LIVE.search(t) or _ROW_LIVE_CAPS.search(t) or _ROW_OPINION.search(t) or _ROW_HISTORY.search(t))

def themes(title):
    t = str(title or "")
    return {k for k, r in _THEMES if r.search(t)}

def _norm(t):
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", str(t or "").lower())).strip()[:80]

def same_story(a, b):
    """Near-identical or same-event titles: same normalised title, or 60%+ of the smaller title's content words shared."""
    if _norm(a.get("title")) and _norm(a.get("title")) == _norm(b.get("title")): return True
    ta, tb = tokens(a.get("title")), tokens(b.get("title"))
    if len(ta) < 3 or len(tb) < 3: return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.6

def dedupe_row(evs, skip_ids=(), skip_items=()):
    """Top-row display filter, order kept: drops junk, cards whose cluster is already shown (or is in skip_ids, e.g. the featured
    desk card), near-identical titles, and a second card on the same theme (one Ebola card, one assassination card ...)."""
    if not row_filter_on(): return list(evs or [])
    seen_ids, seen_th, kept = set(i for i in skip_ids if i), set(), []
    # skip_items (Nov 13): the pinned card 1 and green card 2 are placed by the page, never by this list, so a scanner card that is
    # the same story (near-identical title or same theme) is dropped too. They are never returned.
    ghost = [x for x in (skip_items or ()) if isinstance(x, dict) and x.get("title")]
    for g in ghost:
        if g.get("cluster_id"): seen_ids.add(g["cluster_id"])
        seen_th |= themes(g.get("title"))
    for e in evs or []:
        if not e or row_junk(e): continue
        ids = set(e.get("cluster_ids") or []) | ({e.get("cluster_id")} if e.get("cluster_id") else set())
        if ids & seen_ids: continue
        th = themes(e.get("title"))
        if th & seen_th: continue
        if any(same_story(e, k) for k in kept) or any(same_story(e, g) for g in ghost): continue
        kept.append(e); seen_ids |= ids; seen_th |= th
    return kept

def row_ok(item):
    """Latest-row gate: topic policy (same rules as pins) plus explainer / entertainment junk filter."""
    if not item: return False
    if row_junk(item): return False
    summ = " ".join(str(item.get(k) or "") for k in ("summary", "location", "category"))
    if not topic_ok(item.get("title"), summ): return False
    if explainer_junk(item): return False
    try:
        import story_display as SD
        if SD.is_entertainment_junk(item.get("title") or ""): return False
        item["category"] = SD.display_category(item.get("title") or "", item.get("category"))
        if not (item.get("location") or "").strip():
            loc = SD.place_from_headline(item.get("title") or "")
            if loc: item["location"] = loc
    except Exception:
        pass
    return True

def _updated(x):
    return _ts((x or {}).get("updated")) or _ts((x or {}).get("first_seen")) or 0

def _cmp_latest(a, b, now):
    """Rank desc, then recency; a >24h-old item cannot outrank a fresher item of equal or rank-1 lower."""
    ra, rb = int(a.get("rank") or 0), int(b.get("rank") or 0)
    ua, ub = _updated(a), _updated(b)
    stale_a, stale_b = (now - ua) > LATEST_STALE_H * 3600, (now - ub) > LATEST_STALE_H * 3600
    if stale_a != stale_b:
        # Stale can lead only when its rank is at least 2 higher than the fresher card.
        if stale_a:  # a stale, b fresh
            return -1 if ra >= rb + 2 else 1
        return 1 if rb >= ra + 2 else -1  # b stale, a fresh
    if ra != rb: return -1 if ra > rb else 1
    if ua != ub: return -1 if ua > ub else 1
    return 0

def latest(items, now=None, limit=40):
    """Homepage 'The latest' row: deduped events, topic+junk filtered, 48h freshness (widen to 72h if <6), recency-biased sort."""
    from functools import cmp_to_key
    now = now or time.time()
    ev = [e for e in events(items, now=now, limit=max(limit * 4, 80)) if row_ok(e)]
    def pick(h):   # sort first so the strongest card of a repeated thread is the one kept
        p = [e for e in ev if _updated(e) >= now - h * 3600]
        p.sort(key=cmp_to_key(lambda a, b: _cmp_latest(a, b, now)))
        return dedupe_row(p)
    pool = pick(LATEST_FRESH_H)
    if len(pool) < LATEST_MIN: pool = pick(LATEST_WIDEN_H)
    return pool[:limit]

def links_mtime():
    try: return os.path.getmtime(F_LINKS)
    except OSError: return None

def attach(evs, now=None):
    """Adds `social` to events whose member clusters were posted, and flags the ones posted in the last PIN_HOURS as `posted`."""
    now = now or time.time(); L = links()
    for e in evs:
        best = None
        for cid in e.get("cluster_ids") or [e.get("cluster_id")]:
            s = L.get(cid)
            if s and (best is None or (_ts(s.get("posted_at")) or 0) > (_ts(best.get("posted_at")) or 0)): best = dict(s, cluster_id=cid)
        if best and topic_ok(e.get("title")):
            e["social"] = {"x": best["x"], "yt": best["yt"], "posted_at": best.get("posted_at"), "story": best.get("story")}
            t = _ts(best.get("posted_at"))
            e["posted"] = bool(t and now - t <= PIN_HOURS * 3600)
    return evs

def posted_missing(evs, now=None):
    """Cluster ids posted in the last PIN_HOURS that are not in evs (the caller loads them read-only from the DB)."""
    now = now or time.time(); have = {c for e in evs for c in (e.get("cluster_ids") or [])}
    return [cid for cid, s in links().items() if cid not in have and (_ts(s.get("posted_at")) or 0) >= now - PIN_HOURS * 3600]
