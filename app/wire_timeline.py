"""Wire timeline (preview, Nov 18 2026, Matt 1:23 AM ET): one chronological research timeline of everything collected.

GET /wire                      the live Wire timeline (indexable). BN_WIRE_TIMELINE=0 lets story.py restore the previous listing.
GET /wire-next                 301 to /wire (old preview URL). Redirects even when the flag is off.
GET /api/wire_tl               items, newest first. before=<cursor> (older) or after=<cursor> (newer), limit 1..200,
                               q=<keywords> (all words, title/place), bg=1 adds background signals.
GET /api/wire_tl/meta          totals, earliest/latest, per-category and per-region counts, per-month histogram.
GET /api/wire_tl/app.js|app.css

Data: blackout.db clusters (live scanner) + trends_history.db stories (archive backfill), both opened read-only
(file:...?mode=ro), the same sources /api/wire_history merges. Display-only grouping (category colours, regions) is
computed here and never written back. Never touches scanner.py, scoring, push.py, jets.py, aviation_watch.py or config.json.
"""
import html, json, os, re, sqlite3, threading, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db"); HDB = os.path.join(BASE, "trends_history.db")
STATIC = os.path.join(BASE, "wire_timeline_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
MAXL = 200
_CUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z(\|[A-Za-z0-9_.:\-]{1,80})?$")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def on(): return os.environ.get("BN_WIRE_TIMELINE", "1") != "0"

def _ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c
def _hdb():
    if not os.path.exists(HDB): return None
    try:
        h = _ro(HDB); h.execute("SELECT 1 FROM stories LIMIT 1"); return h
    except sqlite3.Error: return None
def _j(s, d):
    try: return json.loads(s or "") if s else d
    except Exception: return d

# ------------------------------------------------------------------ display categories (colour keys)
CATS = [  # key, label, colour (muted; red is reserved for rank 7+, no yellow)
    ("conflict", "War & conflict", "#B98466"),
    ("disease", "Disease", "#6FA88C"),
    ("quake", "Quakes & volcanoes", "#9A86C4"),
    ("weather", "Weather & fire", "#5E95C8"),
    ("hazard", "Other hazards", "#8C99A6"),
    ("space", "Space weather", "#C58FB6"),
    ("cyber", "Cyber", "#4EAAA6"),
    ("markets", "Markets", "#86A96A"),
    ("politics", "Politics", "#8D93DA"),
    ("uap", "UFO / UAP", "#A7B4C4"),
    ("faith", "Religion", "#AC94A4"),
    ("other", "Other", "#73787F"),
]
_QK = re.compile(r"\b(earthquakes?|quakes?|tsunami|seismic|aftershock|volcan\w*|eruption|ash (?:plume|advisory)|magnitude)\b|^M\s?\d(?:\.\d)?\b", re.I)
_WX = re.compile(r"\b(cyclone|hurricane|typhoon|tropical (?:storm|depression)|storm|floods?|flooding|flash flood|rain\w*|tornado\w*|wild ?fires?|forest ?fires?|bush ?fires?|fire weather|red flag|drought|heat ?wave|excessive heat|heat (?:advisory|warning)|snow\w*|blizzard|ice storm|winter (?:storm|weather)|freez\w+|frost|wind|gale|monsoon|landslides?|mudslides?|avalanche|dust storm|fog|weather|cold wave)\b", re.I)
_DZ = re.compile(r"\b(outbreak|cholera|ebola|marburg|mpox|measles|dengue|malaria|influenza|avian flu|h5n1|bird flu|covid|virus|polio|yellow fever|epidemic|pandemic|meningitis|anthrax|plague|diphtheria|nipah|mers|lassa|hepatitis)\b", re.I)
_RW = re.compile(r"^[^:]{2,60}:\s*(.+?)\s+-\s+[A-Z][a-z]{2} \d{4}$")   # ReliefWeb "Country: Floods - Aug 2026"

def cat_key(category, title, archive):
    c = (category or "").lower(); t = title or ""
    m = _RW.match(t) if archive else None
    if m:   # archive ReliefWeb items carry a coarse stored category; their own type label is better for display
        ty = m.group(1)
        if _QK.search(ty): return "quake"
        if _DZ.search(ty) or re.search(r"epidemic|outbreak", ty, re.I): return "disease"
        if _WX.search(ty): return "weather"
        if re.search(r"conflict|violence|displacement|refugee|unrest|crisis", ty, re.I): return "conflict"
        return "hazard"
    if c == "natural disaster":
        if _QK.search(t): return "quake"
        if _WX.search(t): return "weather"
        return "hazard"
    return {"war/conflict": "conflict", "disease": "disease", "space weather": "space", "cyber": "cyber", "financial": "markets",
            "political": "politics", "ufo/uap": "uap", "spiritual/religious": "faith"}.get(c, "other")

# ------------------------------------------------------------------ regions (display only)
REGIONS = [("na", "North America"), ("la", "Latin America"), ("eu", "Europe"), ("me", "Middle East"), ("af", "Africa"),
           ("as", "Asia"), ("oc", "Oceania"), ("sea", "Oceans & poles"), ("gl", "Global")]
_RC = {
 "na": "united states|u\\.s\\.|usa|america|canada|alaska|hawaii|mexico|greenland|bermuda|puerto rico|guam|" +
       "alabama|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|" +
       "massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|" +
       "ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|" +
       "british columbia|alberta|ontario|quebec|manitoba|saskatchewan|nova scotia|yukon|nunavut|washington, d\\.?c|pentagon|white house|congress|fema|nws",
 "la": "guatemala|honduras|el salvador|nicaragua|costa rica|panama|cuba|haiti|dominican|jamaica|bahamas|barbados|trinidad|caribbean|antilles|martinique|guadeloupe|" +
       "colombia|venezuela|ecuador|peru|bolivia|chile|argentina|brazil|paraguay|uruguay|guyana|suriname|french guiana|latin america|south america|central america",
 "eu": "europe|european|united kingdom|\\buk\\b|britain|england|scotland|wales|ireland|france|germany|spain|portugal|italy|greece|netherlands|belgium|luxembourg|" +
       "switzerland|austria|denmark|norway|sweden|finland|iceland|poland|czech|slovakia|hungary|romania|bulgaria|serbia|croatia|bosnia|slovenia|albania|kosovo|" +
       "montenegro|macedonia|moldova|ukraine|belarus|russia|russian|lithuania|latvia|estonia|cyprus|malta|balkan|kyiv|moscow|crimea|nato",
 "me": "israel|gaza|west bank|palestin|lebanon|syria|iraq|iran|jordan|saudi|yemen|oman|qatar|bahrain|kuwait|emirates|uae|dubai|turkey|t\\u00fcrkiye|turkiye|" +
       "hormuz|red sea|houthi|hezbollah|hamas|tehran|middle east|persian gulf",
 "af": "africa|nigeria|niger|chad|sudan|south sudan|ethiopia|eritrea|somalia|kenya|uganda|tanzania|rwanda|burundi|congo|drc|angola|zambia|zimbabwe|malawi|mozambique|" +
       "madagascar|botswana|namibia|lesotho|eswatini|swaziland|egypt|libya|tunisia|algeria|morocco|mauritania|mali|burkina|senegal|gambia|guinea|sierra leone|liberia|" +
       "ivory coast|c\\u00f4te d|cote d|ghana|togo|benin|cameroon|gabon|central african|djibouti|sahel|comoros|mauritius|reunion|cabo verde|cape verde",
 "as": "china|chinese|japan|korea|taiwan|hong kong|mongolia|india|pakistan|afghanistan|bangladesh|nepal|bhutan|sri lanka|maldives|myanmar|burma|thailand|laos|" +
       "cambodia|vietnam|malaysia|singapore|indonesia|philippines|brunei|timor|kazakhstan|kyrgyzstan|tajikistan|turkmenistan|uzbekistan|azerbaijan|armenia|" +
       "georgia \\(country\\)|kuril|ryukyu|izu islands|honshu|hokkaido|kyushu|sumatra|java|sulawesi|mindanao|luzon|borneo|beijing|asia",
 "oc": "papua new guinea|australia|new zealand|papua|fiji|tonga|samoa|vanuatu|solomon|kermadec|new caledonia|micronesia|marshall islands|kiribati|tuvalu|nauru|palau|" +
       "tasmania|queensland|victoria|new south wales|oceania|pacific islands",
 "sea": "ridge|rise|ocean|sea\\b|atlantic|pacific|indian ocean|arctic|antarctic|south sandwich|south georgia|drake passage|scotia|offshore|tristan da cunha|bouvet|" +
        "macquarie|easter island|galapagos",
 "gl": "global|worldwide|earth\\)|software|internet|international",
}
_RCX = [(k, re.compile(r"(?:%s)" % v, re.I)) for k, v in _RC.items()]

def _reg_ll(lat, lon):
    try: la = float(lat); lo = float(lon)
    except (TypeError, ValueError): return None
    if la < -60 or la > 75: return "sea" if la < -60 else ("na" if -170 < lo < -10 else "eu")
    if -170 <= lo <= -50 and la >= 15: return "na"
    if -120 <= lo <= -30 and la < 15: return "la"
    if -25 <= lo <= 45 and 35 <= la <= 72: return "eu"
    if 25 <= lo <= 63 and 12 <= la < 42: return "me"
    if -20 <= lo <= 52 and -36 <= la < 37: return "af"
    if 60 <= lo <= 150 and -11 <= la <= 75: return "as"
    if 110 <= lo <= 180 and -50 <= la < -11 or lo >= 150 and la < 0: return "oc"
    return "sea"

def _best(txt, skip=()):
    """Region whose pattern matches the longest stretch of txt (so "Papua New Guinea" beats "Guinea")."""
    best, bl = None, 0
    for k, rx in _RCX:
        if k in skip: continue
        for m in rx.finditer(txt):
            if len(m.group(0)) > bl: best, bl = k, len(m.group(0))
    return best

def region_key(loc, title, lat=None, lon=None):
    txt = f"{loc or ''}"
    k = _best(txt, ("sea",)) if txt else None   # the stored place text first: it names the country/area the scanner resolved
    if k: return k
    r = _reg_ll(lat, lon)
    if r: return r
    k = _best(txt) if txt else None
    if k: return k
    return _best(title or "", ("sea", "gl")) or "gl"

# ------------------------------------------------------------------ text
_EMO = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")
def _clean(s): return re.sub(r"\s{2,}", " ", _EMO.sub("", str(s or ""))).strip()

def headline(t):
    try:
        import theme; h = theme._headline(t or "")
    except Exception: h = _clean(t)
    h = (h or _clean(t)).strip()
    if len(h) > 110:
        m = re.match(r"^(.{30,110}?[.!?])\s", h)
        h = m.group(1).rstrip(".") if m else h[:110].rsplit(" ", 1)[0].rstrip(",;:-— ") + "…"
    return h

def _brief(b):
    b = b or ""; out = {}
    for k in ("WHAT", "WHERE", "WHEN", "CONFIDENCE", "VERIFY"):
        m = re.search(k + r":\s*(.+?)(?=\s+(?:WHAT|WHERE|WHEN|CONFIDENCE|VERIFY):|$)", b, re.S)
        if m: out[k.lower()] = m.group(1).strip()
    if not out and b.strip(): out["what"] = b.strip()
    return out

def _sent(s, n):
    s = re.sub(r"\[[^\]]*\]", "", _clean(s)).strip()
    if len(s) <= n: return s
    m = re.match(r"^(.{40,%d}?[.!?])(\s|$)" % n, s)
    return m.group(1) if m else s[:n].rsplit(" ", 1)[0].rstrip(",;:-— ") + "…"

_N = lambda x: set(re.sub(r"[^a-z0-9]+", " ", (x or "").lower()).split())

def _links(js):
    out = []
    for x in _j(js, []):
        u = (x or {}).get("url") or ""
        if re.match(r"^https?://", u): out.append({"s": _clean(x.get("source"))[:60], "u": u[:500]})
        if len(out) >= 5: break
    return out

def _item(r, archive):
    title = _clean(r["title"]); h = headline(title)
    loc = _clean(r["location"])[:90] if r["location"] else ""
    links = _links(r["links"])
    fams = _j(r["families"], [])[:6]
    srcs = [s for s in (_j(r["sources"], []) if archive else []) if isinstance(s, str)][:4] or [l["s"] for l in links if l["s"]][:4]
    srcs = list(dict.fromkeys(srcs))
    bp = _brief(r["brief"]) if not archive else {}
    what = _sent(bp.get("what") or "", 420)
    # one-line summary that adds something beyond the headline
    s = ""
    if what and len(_N(what) - _N(h)) >= 4: s = _sent(what, 150)
    if not s:
        bits = [loc] if loc and len(_N(loc) - _N(h)) >= 1 else []
        if srcs: bits.append("via " + ", ".join(srcs[:2]) + (f" +{len(srcs) - 2}" if len(srcs) > 2 else ""))
        s = " · ".join(bits)
    d = what if what and what != s else ""
    if not d and title != h: d = _sent(title, 420)
    rk = r["rank"]
    try: rk = int(rk) if rk is not None else None
    except (TypeError, ValueError): rk = None
    t = r["t"]
    return {"id": r["id"], "t": t, "h": h, "s": s, "d": d, "k": cat_key(r["category"], title, archive),
            "g": region_key(loc, title, r["lat"], r["lon"]), "r": rk, "c": r["confidence"] or "", "loc": loc,
            "n": int(r["n_items"] or 0), "f": len(fams), "src": srcs, "l": links, "a": 1 if archive else 0,
            "w": r["watchlist"] or 0, "et": r["event_time"] if not archive else None,
            "do": 1 if archive and (t or "").endswith("T00:00:00Z") else 0}   # archive items dated by day only (no time given)

_LIVE_COLS = ("cluster_id id, first_seen t, event_time, title, category, location, lat, lon, score, rank, confidence, watchlist, "
              "n_items, families, links, brief, NULL sources")
_ARCH_COLS = ("id, t, NULL event_time, title, category, location, lat, lon, score, rank, confidence, watchlist, n_items, families, links, "
              "NULL brief, sources")

def _qwhere(words, cols):
    w, a = "", []
    for x in words:
        w += " AND (" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in cols) + ")"
        a += ["%" + x.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"] * len(cols)
    return w, a

def page(before=None, after=None, limit=100, q="", bg=False):
    limit = max(1, min(MAXL, int(limit)))
    words = [w for w in re.split(r"\s+", (q or "").strip()) if w][:6]
    lists = (0, 1, 2) if bg else (0, 1)
    newer = bool(after)
    cur = after if newer else before
    if cur:
        ct, _, cid = cur.partition("|"); cid = cid or ("" if newer else "~")
    else:
        ct, cid = ("0000-01-01T00:00:00Z", "") if newer else ("9999-12-31T23:59:59Z", "~")
    op, order = (">", "ASC") if newer else ("<", "DESC")
    rows = []
    c = _ro(DB)
    try:
        qw, qa = _qwhere(words, ("title", "location"))
        sql = (f"SELECT {_LIVE_COLS} FROM clusters WHERE (first_seen{op}? OR (first_seen=? AND cluster_id{op}?)) "
               f"AND watchlist IN ({','.join('?' * len(lists))}){qw} ORDER BY first_seen {order}, cluster_id {order} LIMIT ?")
        rows += [(r, False) for r in c.execute(sql, [ct, ct, cid, *lists, *qa, limit + 1])]
    finally: c.close()
    h = _hdb()
    if h is not None:
        try:
            qw, qa = _qwhere(words, ("title", "location"))
            sql = (f"SELECT {_ARCH_COLS} FROM stories WHERE (t{op}? OR (t=? AND id{op}?)) "
                   f"AND watchlist IN ({','.join('?' * len(lists))}){qw} ORDER BY t {order}, id {order} LIMIT ?")
            rows += [(r, True) for r in h.execute(sql, [ct, ct, cid, *lists, *qa, limit + 1])]
        finally: h.close()
    rows.sort(key=lambda x: (x[0]["t"] or "", x[0]["id"]), reverse=not newer)
    more = len(rows) > limit
    rows = rows[:limit]
    items = [_item(r, a) for r, a in rows]
    if newer: items.reverse()   # always newest first in the payload
    edge = (items[0] if newer else items[-1]) if items else None
    nxt = f"{edge['t']}|{edge['id']}" if edge and more else None
    return {"items": items, "next": nxt, "end": nxt is None, "dir": "newer" if newer else "older", "limit": limit}

def count(q="", bg=False):
    words = [w for w in re.split(r"\s+", (q or "").strip()) if w][:6]
    lists = (0, 1, 2) if bg else (0, 1)
    n = 0; lo = hi = None
    c = _ro(DB)
    try:
        qw, qa = _qwhere(words, ("title", "location"))
        r = c.execute(f"SELECT COUNT(*), MIN(first_seen), MAX(first_seen) FROM clusters WHERE watchlist IN ({','.join('?' * len(lists))}){qw}", [*lists, *qa]).fetchone()
        n += r[0] or 0; lo, hi = r[1], r[2]
    finally: c.close()
    h = _hdb()
    if h is not None:
        try:
            qw, qa = _qwhere(words, ("title", "location"))
            r = h.execute(f"SELECT COUNT(*), MIN(t), MAX(t) FROM stories WHERE watchlist IN ({','.join('?' * len(lists))}){qw}", [*lists, *qa]).fetchone()
            n += r[0] or 0
            lo = min([x for x in (lo, r[1]) if x] or [None]) if (lo or r[1]) else None
            hi = max([x for x in (hi, r[2]) if x] or [None]) if (hi or r[2]) else None
        finally: h.close()
    return {"count": n, "earliest": lo, "latest": hi}

_M = {"t": 0, "key": None, "data": None}; _LK = threading.Lock()
def _stamp():
    out = []
    for p in (DB, HDB):
        try: out.append(os.path.getmtime(p))
        except OSError: out.append(0)
    return tuple(out)

def meta():
    st = _stamp()
    with _LK:
        if _M["data"] and time.time() - _M["t"] < 600: return _M["data"]   # 10-minute TTL (the DB changes every scan)
    cats = {k: 0 for k, _, _ in CATS}; regs = {k: 0 for k, _ in REGIONS}; months = {}
    n = 0; lo = hi = None; arch = live = 0
    def take(rows, archive):
        nonlocal n, lo, hi
        for r in rows:
            n += 1; t = r["t"] or ""
            if t:
                lo = t if lo is None or t < lo else lo; hi = t if hi is None or t > hi else hi
                months[t[:7]] = months.get(t[:7], 0) + 1
            cats[cat_key(r["category"], _clean(r["title"]), archive)] += 1
            regs[region_key(r["location"], r["title"], r["lat"], r["lon"])] += 1
    c = _ro(DB)
    try:
        rows = c.execute("SELECT first_seen t, title, category, location, lat, lon FROM clusters WHERE watchlist IN (0,1)").fetchall()
        live = len(rows); take(rows, False)
        bgn = c.execute("SELECT COUNT(*) FROM clusters WHERE watchlist=2").fetchone()[0]
    finally: c.close()
    h = _hdb()
    if h is not None:
        try:
            rows = h.execute("SELECT t, title, category, location, lat, lon FROM stories WHERE watchlist IN (0,1)").fetchall()
            arch = len(rows); take(rows, True)
        finally: h.close()
    out = {"total": n, "live": live, "archive": arch, "background": bgn, "earliest": lo, "latest": hi,
           "categories": [{"k": k, "label": l, "color": col, "n": cats[k]} for k, l, col in CATS],
           "regions": [{"k": k, "label": l, "n": regs[k]} for k, l in REGIONS],
           "months": sorted(months.items()), "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with _LK: _M.update(t=time.time(), key=st, data=out)
    return out

_BG = {"on": False}
def meta_cached():
    """Last meta (possibly stale) without blocking the page; refreshes in a short-lived thread when older than 10 minutes."""
    d = _M["data"]
    if (d is None or time.time() - _M["t"] >= 600) and not _BG["on"]:
        _BG["on"] = True
        def run():
            try: meta()
            except Exception: pass
            finally: _BG["on"] = False
        threading.Thread(target=run, daemon=True).start()
    return d or {}

# ------------------------------------------------------------------ page
_FILE = {}
def _file(name):
    p = os.path.join(STATIC, name)
    try: mt = os.path.getmtime(p)
    except OSError: return None
    hit = _FILE.get(name)
    if hit and hit[0] == mt: return hit[1]
    data = open(p, "rb").read(); _FILE[name] = (mt, data); return data

def _ver(name):
    # suffix busts a Cloudflare immutable cache if a previous probe used this mtime as ?v=
    try: return str(int(os.path.getmtime(os.path.join(STATIC, name)))) + "b"
    except OSError: return "0"

def page_html():
    try:
        import wire_v2; menu = wire_v2.menu_html(); w2 = wire_v2.ST
    except Exception:
        menu = ""; w2 = "/wire2/static"
    m = meta_cached()
    cfg = {"cats": [{"k": k, "label": l, "color": col} for k, l, col in CATS], "regions": [{"k": k, "label": l} for k, l in REGIONS]}
    tot = m.get("total") or 0
    since = ""
    if m.get("earliest"):
        try: since = datetime.fromisoformat(m["earliest"].replace("Z", "+00:00")).strftime("%b %-d, %Y")
        except Exception: since = ""
    line = f"{tot:,} signals since {since}. Newest at the top." if tot and since else "Every signal we have collected, newest at the top."
    v_css, v_js = _ver("app.css"), _ver("app.js")
    title = "The Wire: live threat feed | BLACKOUT.NETWORK"
    desc = "Every signal BLACKOUT.NETWORK has collected, in one timeline."
    try:
        import og
        ogmeta = og.tags(title=title, desc=desc, url="https://blackout.network/wire", key="wire", og_type="website")
    except Exception:
        ogmeta = ""
    return f'''<!doctype html><html lang="en" data-bnt-home data-bn-w2 data-bn-tl><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="https://blackout.network/wire">
{ogmeta}<meta name="theme-color" content="#000">
<!-- w2: own design system; server.pwa_head skips the shared theme layer when it sees /bnt/theme.css here -->
<link rel="stylesheet" href="{w2}/wire2.css?v=6"><link rel="stylesheet" href="/api/wire_tl/app.css?v={v_css}">
<link rel="preload" as="image" href="/bnt/media/wthero-m.jpg?v=1" media="(max-width:700px)"><link rel="preload" as="image" href="/bnt/media/wtvid-d.jpg?v=1" media="(min-width:701px)"></head>
<body class="w2 tl"><header class="w2-bar" id="w2_bar"><a class="w2-wm" href="/?intro=1" aria-label="BLACKOUT.NETWORK intro">blackout.network</a>
<button type="button" class="w2-mbtn" id="w2_open" aria-label="Open menu" aria-controls="w2_menu" aria-expanded="false"><span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span><span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span></button></header>
{menu}
<div class="tl-bg" aria-hidden="true"><picture><source media="(max-width:700px)" srcset="/bnt/media/wthero-m.jpg?v=1"><img src="/bnt/media/wtvid-d.jpg?v=1" alt="" decoding="async" fetchpriority="high"></picture>
<video class="tl-vid" muted loop playsinline preload="none" disablepictureinpicture tabindex="-1" data-webm="/bnt/media/wtvid-d.webm?v=1" data-mp4="/bnt/media/wtvid-d.mp4?v=1"></video><i class="tl-veil"></i></div>
<main id="tl_main">
<section class="tl-hero" aria-label="The Wire"><div class="tl-hc"><p class="w2-eb">The Wire &middot; Timeline</p><h1 class="w2-ht">Every signal</h1>
<p class="w2-hl" id="tl_line">{E(line)}</p><a class="w2-btn" href="#tl_start" id="tl_enter">Enter the timeline <span aria-hidden="true">&darr;</span></a></div>
<a class="tl-cue" href="#tl_start" aria-label="Scroll to the timeline"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></a></section>
<div id="tl_start"></div>
<div class="tl-ctl" id="tl_ctl">
 <div class="tl-row1">
  <label class="tl-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="1.4"/></svg>
   <input id="tl_q" type="search" inputmode="search" enterkeyhint="search" autocomplete="off" spellcheck="false" placeholder="Search every signal" aria-label="Search every signal"><button type="button" id="tl_qx" class="tl-qx" aria-label="Clear search" hidden>&times;</button></label>
  <button type="button" class="tl-b" id="tl_when" aria-expanded="false" aria-controls="tl_jump"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 10h16M9 3.5v4M15 3.5v4" stroke="currentColor" stroke-width="1.4"/></svg><span>Date</span></button>
  <button type="button" class="tl-b tl-cond" id="tl_cond" aria-pressed="false" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v6m0 0-3-3m3 3 3-3M12 21v-6m0 0-3 3m3-3 3 3M4 12h16" fill="none" stroke="currentColor" stroke-width="1.4"/></svg><span class="tl-cl">Condense</span></button>
  <button type="button" class="tl-b" id="tl_ref" aria-label="Refresh"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="miter"/></svg><span>Refresh</span></button>
 </div>
 <div class="tl-row2"><div class="tl-chips" id="tl_chips" role="group" aria-label="Filter by type and region"></div></div>
 <div class="tl-jump" id="tl_jump" hidden><div class="tl-jq" id="tl_jq"></div><label class="tl-jd"><span>Go to date</span><input type="date" id="tl_date"></label></div>
 <div class="tl-stat"><button type="button" class="tl-now" id="tl_now" aria-label="Current date; tap to jump"></button><span id="tl_stat" aria-live="polite"></span><span id="tl_upd" class="tl-upd" hidden></span><button type="button" class="tl-clear" id="tl_clear" hidden>Clear</button></div>
</div>
<section class="tl-wrap" aria-label="Timeline"><div class="tl-list" id="tl_list" role="list"></div><div class="tl-foot" id="tl_foot"></div></section>
<button type="button" class="tl-newp" id="tl_new" hidden></button>
<button type="button" class="tl-top" id="tl_top" hidden aria-label="Back to the latest"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><span>Latest</span></button>
</main>
<footer class="w2-foot"><p class="w2-tag">Global threat monitoring</p><p class="w2-legal">Independent early-warning signals. Not an official alert service. <a href="/scoring">How we score</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p></footer>
<script>window.BN_TL={json.dumps(cfg)};</script>
<script src="{w2}/wire2.js?v=3" defer></script><script src="/api/wire_tl/app.js?v={v_js}" defer></script></body></html>'''

def handle_get(path, qs):
    if path in ("/wire-next", "/wire-next/"):
        return 301, b"", "text/html", {"Location": "/wire"}
    if not on(): return 404, {"error": "not found"}
    g = lambda k, d=None: ((qs.get(k) or [d])[0] or d)
    if path in ("/wire", "/wire/"):
        return 200, page_html(), "text/html"
    if path.startswith("/api/wire_tl/"):
        n = path[len("/api/wire_tl/"):]
        if n in FILES:
            b = _file(n)
            return (200, b, FILES[n]) if b is not None else (404, {"error": "not found"})
        if n == "meta":
            try: return 200, meta()
            except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
        if n == "count":
            q = (g("q", "") or "")[:80]
            try: return 200, count(q, g("bg") == "1")
            except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
        return 404, {"error": "not found"}
    if path == "/api/wire_tl":
        before, after = g("before"), g("after")
        for x in (before, after):
            if x and not _CUR.match(x): return 400, {"error": "cursor must be an ISO UTC time like 2025-06-01T00:00:00Z, optionally |<id>"}
        if before and after: return 400, {"error": "use before or after, not both"}
        try: lim = int(g("limit", "100"))
        except ValueError: return 400, {"error": "limit must be a number"}
        if not 1 <= lim <= MAXL: return 400, {"error": f"limit must be 1..{MAXL}"}
        q = (g("q", "") or "")[:80]
        try: return 200, page(before, after, lim, q, g("bg") == "1")
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
    return 404, {"error": "not found"}
