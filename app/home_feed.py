"""Homepage feed: one card per real event, plus "Follow this story" links (display/API layer only).

Why the homepage showed duplicates (Nov 8): the scanner opens a new cluster whenever a later report doesn't match an
existing cluster closely enough, so one event can live in several clusters ("Paraguay Bank Failure", "Paraguay: President
under investigation for bank failure", "Ousted Paraguayan president placed under house arrest..."), several agencies report
the same quake (JMA + EMSC + a news story), NWS re-issues the same warning for the same county, and the Nov 7 cutover
catch-up re-ingested a backlog with the same first_seen. /api/state lists clusters, and the homepage row only grouped quakes.

This module collapses those clusters into events here, at display time. It never changes the scanner, its scores or the DB
(read-only, file:...?mode=ro), and it never invents anything: every card is a real cluster, shown with its own rank.

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
        out.append(rep)
    out.sort(key=lambda x: (-(int(x.get("rank") or 0)), -(int(x.get("n_families") or 0)), -(_ts(x.get("updated")) or 0)))
    return out

def events(items, now=None, limit=40):
    """Clean titles (drop unusable ones), collapse duplicates, rank by usefulness. Titles in the result are display-clean."""
    keep = []
    for x in items:
        t = clean_title(x.get("title"))
        if t: keep.append(dict(x, title=t))
    return group(keep, now)[:limit]

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
_QK = re.compile(r"\b(?:earthquakes?|quake|seismic|magnitude)\b|\bM\s*[4-9]\.\d", re.I)
_QIMPACT = re.compile(r"\b(?:significant|major|severe|widespread) (?:damage|destruction)\b|\b(?:[1-9]\d* (?:dead|deaths|killed|injured)|fatalities|casualties reported|tsunami (?:warning|threat))\b", re.I)
_QNEG = re.compile(r"\b(?:no|without|zero|not any)\b.{0,35}(?:damage|casualties|fatalities|tsunami|deaths|killed|injured)", re.I)
_QUS = re.compile(r"\b(?:Los Angeles|San Francisco|San Diego|Seattle|Portland, Oregon|Anchorage|Honolulu|Salt Lake City|San Juan, Puerto Rico)\b", re.I)
def topic_ok(title):
    """False for routine weather / NWS products and for quakes below M7 without real damage, a tsunami threat, or M5.5+ in a populated US area."""
    t = str(title or "")
    if _WX.search(t) or nws(t): return False
    if _QK.search(t):
        m = re.search(r"\b(?:M\s*|magnitude\s*)(\d(?:\.\d)?)", t, re.I); mag = float(m.group(1)) if m else 0
        return mag >= 7 or bool(_QIMPACT.search(t) and not _QNEG.search(t)) or (mag >= 5.5 and bool(_QUS.search(t)))
    return True

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
