"""Wire timeline (preview, Nov 18 2026, Matt 1:23 AM ET): one chronological research timeline of everything collected.

GET /wire                      the live Wire timeline (indexable). BN_WIRE_TIMELINE=0 lets story.py restore the previous listing.
GET /wire-next                 301 to /wire (old preview URL). Redirects even when the flag is off.
GET /api/wire_tl               items, newest first by last activity (COALESCE(updated, first_seen)). before=<cursor>
                               (older) or after=<cursor> (newer), limit 1..200, q=<keywords> (all words, title/place),
                               bg=1 adds background signals, lat/lon/r=miles limits to a radius,
                               sev=lo|mid|hi (ranks 0-3 / 4-6 / 7-10), cats= and regs= (comma keys),
                               time=today|<days> (event_time or first_seen, America/New_York for today).
                               The server keeps reading until it fills `limit` matches or the true end;
                               end is true only when no older/newer matching row remains.
GET /api/wire_tl/xu?id=         Post-on-X URL (3-5 entity tags) for one live row the warm thread has not reached yet.
GET /api/wire_tl/meta          totals, earliest/latest, per-category and per-region counts, per-month histogram.
GET /api/wire_tl/geo?q=        keyless ZIP/place geocode (US Census ZCTA table + offline gazetteer).
GET /api/wire_tl/crime?q=      local crime headlines for a US place when BN_CRIME_NEWS is on (cached).
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
    ("politics", "Political", "#8D93DA"),
    ("scandal", "Scandals", "#A8907A"),
    ("unrest", "Civil unrest", "#9A7A8C"),
    ("crime", "Crime", "#8A8E9A"),
    ("deaths", "Obituaries", "#7A8490"),
    ("people", "People", "#8B8FA3"),
    ("disease", "Health alerts", "#6FA88C"),
    ("quake", "Quakes & volcanoes", "#9A86C4"),
    ("weather", "Weather & fire", "#5E95C8"),
    ("wreck", "Wrecks & crashes", "#7E8A96"),
    ("infra", "Infrastructure", "#6E8B8A"),
    ("hazard", "Other hazards", "#8C99A6"),
    ("space", "Space weather", "#C58FB6"),
    ("cyber", "Cyber", "#4EAAA6"),
    ("markets", "Finance", "#86A96A"),
    ("uap", "UFO / UAP", "#A7B4C4"),
    ("faith", "Religion", "#AC94A4"),
    ("other", "Other", "#73787F"),
]
_QK = re.compile(r"\b(earthquakes?|quakes?|tsunami|seismic|aftershock|volcan\w*|eruption|ash (?:plume|advisory)|magnitude)\b|^M\s?\d(?:\.\d)?\b", re.I)
_AG = re.compile(r"\b(USGS|GEOFON|EMSC|INGV|CSN|PTWC|JMA|BMKG)\b:\s*M\s?\d", re.I)
_WX = re.compile(r"\b(cyclone|hurricane|typhoon|tropical (?:storm|depression)|storm|floods?|flooding|flash flood|rain\w*|tornado\w*|wild ?fires?|forest ?fires?|bush ?fires?|fire weather|red flag|drought|heat ?wave|excessive heat|heat (?:advisory|warning)|snow\w*|blizzard|ice storm|winter (?:storm|weather)|freez\w+|frost|wind|gale|monsoon|landslides?|mudslides?|avalanche|dust storm|fog|weather|cold wave)\b", re.I)
_DZ = re.compile(r"\b(outbreak|cholera|ebola|marburg|mpox|measles|dengue|malaria|influenza|avian flu|h5n1|bird flu|covid|virus|polio|yellow fever|epidemic|pandemic|meningitis|anthrax|plague|diphtheria|nipah|mers|lassa|hepatitis)\b", re.I)
_WRECK = re.compile(r"\b(plane crash|air crash|airliner crash|crashed|mid-air|derail\w*|train crash|shipwreck|capsized|sank|sinking|multi-vehicle|pile-?up|traffic fatality|fatal crash|helicopter crash|vessel sunk|maritime accident|ferry (?:sink|capsiz)|road crash|car crash|bus crash|truck crash)\b", re.I)
_INFRA = re.compile(r"\b(power outage|blackout|grid (?:fail|collapse|down)|substation|water main|boil[- ]water|pipeline (?:rupture|leak|explosion)|bridge collapse|dam (?:fail|breach|burst)|internet outage|fiber cut|gas leak|sewage (?:spill|overflow)|runway closed|port closed|rail (?:outage|suspended)|transformer fire)\b", re.I)
_OBIT = re.compile(r"\b(obituar\w*|dies at \d+|has died|dead at \d+|passed away)\b", re.I)
_CRIME = re.compile(r"\b(homicide|murder(?:ed)?|manslaughter|mass shooting|shooting|shot dead|stabbed|stabbing|robbery|burglary|carjack\w*|kidnapp\w*|arrested|serial (?:killer|rapist)|gang (?:violence|shooting)|sexual assault)\b", re.I)
_SCANDAL = re.compile(r"\b(scandal|corruption|embezzl\w*|bribery|kickback|impeach\w*|ethics (?:probe|investigation)|cover-?up|campaign finance|resigned amid)\b", re.I)
_UNREST = re.compile(r"\b(civil unrest|riot\w*|protest\w*|demonstrat\w*|looting|curfew|martial law|clashes with police|tear gas|anti-government)\b", re.I)
_PEOPLE = re.compile(r"\b(assassina\w*|assassination attempt)\b", re.I)
_RW = re.compile(r"^[^:]{2,60}:\s*(.+?)\s+-\s+[A-Z][a-z]{2} \d{4}$")   # ReliefWeb "Country: Floods - Aug 2026"
_STORED = {"war/conflict": "conflict", "disease": "disease", "space weather": "space", "cyber": "cyber",
           "financial": "markets", "political": "politics", "ufo/uap": "uap", "spiritual/religious": "faith",
           "crime": "crime", "people": "people"}

def cat_key(category, title, archive):
    """Display category. Title rules run first so a stored war/conflict tag on a quake (or similar mislabel) is corrected."""
    c = (category or "").lower(); t = title or ""
    m = _RW.match(t) if archive else None
    if m:   # archive ReliefWeb items carry a coarse stored category; their own type label is better for display
        ty = m.group(1)
        if _QK.search(ty): return "quake"
        if _DZ.search(ty) or re.search(r"epidemic|outbreak", ty, re.I): return "disease"
        if _WX.search(ty): return "weather"
        if re.search(r"conflict|violence|displacement|refugee|unrest|crisis", ty, re.I): return "conflict"
        return "hazard"
    if c == "people":   # scanner [people] layer (sources_layers.py): keep it under People; its death notices go to Obituaries
        return "deaths" if (_OBIT.search(t) or t.startswith("Death: ")) else "people"
    # Title-first: fix known quake-as-conflict (and similar) mislabels regardless of stored category.
    if _QK.search(t) or _AG.search(t): return "quake"
    if _DZ.search(t): return "disease"
    if _WRECK.search(t): return "wreck"
    if _INFRA.search(t): return "infra"
    if c == "natural disaster":
        if _WX.search(t): return "weather"
        return "hazard"
    if _OBIT.search(t): return "deaths"
    if c != "war/conflict":
        if _UNREST.search(t): return "unrest"
        if _CRIME.search(t): return "crime"
        if _PEOPLE.search(t): return "people"
    if _SCANDAL.search(t): return "scandal"
    if _WX.search(t) and c not in ("war/conflict", "political"): return "weather"
    return _STORED.get(c, "other")

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

# ------------------------------------------------------------------ speed layer (Nov 25 2026, Matt: Wire list under 1 s)
# The request path never opens a story_writer connection, takes SW._LK, or computes hashtags. One daemon thread
# ("bn-wire-warm") reads story_writer's tables with ONE read-only connection every few seconds (briefs, needs_paid,
# ready.tags), keeps the public gate and the per-row Post-on-X URL in memory, and rebuilds the pages people ask for.
# #243 did that work per row under the global lock and the list hung on "database is locked".
_TL = threading.local()
_SNAP = {}; _SNAP_LK = threading.Lock(); _SNAP_TTL = 4.0
_XC = {}; _XC_MAX = 4000; _XC_TTL = 900.0      # cid -> (sig, xu, built_at); rows with fewer than 3 tags are cached too
_PC = {"t": {}, "v": {}}; _PC_TTL = 3.0; _PC_LK = threading.Lock()
_PA = {}                                         # page key -> (args, last_requested)
_PC_STALE = 20.0                                 # a cached page may be served this long while the warmer rebuilds it
_WARM = {"thread": None, "rows_at": 0.0, "cursor": 0, "baked": {}, "err": ""}
_WARM_LK = threading.Lock()

def _sw():
    try:
        import story_writer as SW
        return SW
    except Exception:
        return None

def _warm_alive():
    t = _WARM["thread"]
    return bool(t and t.is_alive())

_BRIEF_SQL = ("SELECT cid, alias_of, "
              "CASE WHEN json_valid(note) AND json_type(note)='object' THEN 1 ELSE 0 END, "
              "CASE WHEN json_valid(note) AND json_type(note)='object' THEN json_extract(note,'$.file') END, "
              "CASE WHEN json_valid(note) AND json_type(note)='object' THEN json_extract(note,'$.writer.model') END FROM briefs")

def _snap_load():
    """One read-only connection, three SELECTs. Raises on a busy database; the caller keeps the previous snapshot."""
    SW = _sw()
    if SW is None:
        return None
    p = SW.cfg()["db"]
    brief, np, ready = {}, set(), {}
    if os.path.exists(p):
        k = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=4)
        try:
            for cid, alias, isd, f, m in k.execute(_BRIEF_SQL):
                brief[cid] = (alias, isd, f, m)
            for q, sink in (("SELECT cid FROM needs_paid", "np"), ("SELECT cid, tags FROM ready", "ready")):
                try:
                    rows = k.execute(q).fetchall()
                except sqlite3.OperationalError as ex:
                    if "no such table" in str(ex):
                        continue
                    raise
                if sink == "np":
                    np = {r[0] for r in rows}
                else:
                    ready = {r[0]: r[1] for r in rows}
        finally:
            k.close()
    return {"t": time.time(), "gate_on": bool(SW.gate_on()), "np": np, "brief": brief, "ready": ready, "maps": SW._desk_maps()}

def _snap_refresh(block):
    if not _SNAP_LK.acquire(blocking=block):
        return _SNAP.get("s")
    try:
        try:
            s = _snap_load()
        except Exception as ex:
            s = None
            _SNAP["err"] = str(ex)[:120]
        if s is not None:
            _SNAP["s"] = s
        return _SNAP.get("s")
    finally:
        _SNAP_LK.release()

def _snap():
    s = _SNAP.get("s")
    if s is not None:
        age = time.time() - s["t"]
        if age < _SNAP_TTL or (_warm_alive() and age < 60):
            return s
    return _snap_refresh(block=s is None)

def _is_template(f, m):
    return f == "story_writer_template" or m == "template"

def _gate_ok(cid):
    """story_writer.allow(cid, archive=False) evaluated against the in-memory snapshot (tests compare the two)."""
    s = _snap()
    if s is None:
        SW = _sw()
        try:
            return bool(SW.allow(cid, archive=False)) if SW else True
        except Exception:
            return True
    if not s["gate_on"]:
        return True
    notes_, alias, v3 = s["maps"]
    desk = bool(cid in v3 or cid in notes_ or (alias.get(cid) and alias.get(cid) in notes_))
    b = s["brief"].get(cid)
    note = None                                   # (is_template,) of the note story_writer.note_for would return
    if b is not None:
        a, isd, f, m = b
        if a:
            d = v3.get(a) or notes_.get(a) or notes_.get(alias.get(a) or "")
            if isinstance(d, dict):
                note = (_is_template(d.get("file"), (d.get("writer") or {}).get("model")),)
            else:
                b2 = s["brief"].get(a)
                if b2 and not b2[0] and b2[1]:
                    note = (_is_template(b2[2], b2[3]),)
        elif isd:
            note = (_is_template(f, m),)
    paid = desk or (note is not None and not note[0])
    if cid in s["np"] and not paid:
        return False
    return bool(desk or note is not None)

def _public_row(r, archive):
    """Live clusters are held until story_writer has a write-up, tags and card. Archive items stay visible."""
    if archive:
        return True
    try:
        return _gate_ok(r["id"] if "id" in r.keys() else r["cluster_id"])
    except Exception:
        return True

def _stored_tags(cid):
    raw = ((_SNAP.get("s") or {}).get("ready") or {}).get(cid)
    if not raw or raw in ("[]", "null"):
        return []
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return [("#" + str(t).lstrip("#")) for t in v if t] if isinstance(v, list) else []
    except Exception:
        return []

def _xu_build(r, rk, h, title, loc, links, what, dek, hid):
    import x_share
    item = {"cluster_id": r["id"], "title": title, "headline": h, "location": loc,
            "category": r["category"] or "", "brief": r["brief"] or "", "rank": rk,
            "watchlist": r["watchlist"] or 0, "hidden": hid, "links": links, "d": what or dek}
    stored = [t for t in _stored_tags(r["id"]) if not x_share._is_filler(t)]
    if len(stored) >= 3 and not hid:
        return x_share.intent_url(x_share.with_body(item), tags=stored[:5])
    return x_share.intent_url(x_share.with_body(item))

def _xu_for(r, rk, h, title, loc, links, what, dek, hid, compute):
    cid = r["id"]
    sig = hash((title, rk, loc, (r["brief"] or "")[:400], bool(hid)))
    e = _XC.get(cid)
    if e is not None and e[0] == sig:
        return e[1]
    if not compute:
        return ""
    xu = _xu_build(r, rk, h, title, loc, links, what, dek, hid)
    if len(_XC) >= _XC_MAX:
        for k in sorted(_XC, key=lambda k: _XC[k][2])[:_XC_MAX // 4]:
            _XC.pop(k, None)
    _XC[cid] = (sig, xu, time.time())
    return xu

def _item(r, archive, warm_budget=None, compute=None):
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
    dek = what if what and what != s else ""
    if not dek and title != h: dek = _sent(title, 420)
    rk = r["rank"]
    try: rk = int(rk) if rk is not None else None
    except (TypeError, ValueError): rk = None
    t = r["t"]
    def _ll(v):
        try:
            return float(v) if v is not None and v != "" else None
        except (TypeError, ValueError):
            return None
    fs = r["fs"] if "fs" in r.keys() else None
    d = {"id": r["id"], "t": t, "h": h, "s": s, "d": dek, "k": cat_key(r["category"], title, archive),
            "g": region_key(loc, title, r["lat"], r["lon"]), "r": rk, "c": r["confidence"] or "", "loc": loc,
            "n": int(r["n_items"] or 0), "f": len(fams), "src": srcs, "l": links, "a": 1 if archive else 0,
            "w": r["watchlist"] or 0, "et": r["event_time"] if not archive else None,
            "do": 1 if archive and (t or "").endswith("T00:00:00Z") else 0,  # archive items dated by day only (no time given)
            "lat": _ll(r["lat"]), "lon": _ll(r["lon"]), "fs": fs}
    if archive:
        d["xu"] = ""          # the timeline shows no Post on X for archive rows
        return d
    try:
        hid = False
        try:
            hid = bool(r["hidden"])
        except Exception:
            hid = False
        if (rk or 0) >= 5 and warm_budget is not None and warm_budget[0] > 0:
            try:
                import share_card; share_card.warm(str(r["id"]))
                warm_budget[0] -= 1
            except Exception:
                pass
        go = _warming() if compute is None else compute
        d["xu"] = _xu_for(r, rk, h, title, loc, links, what, dek, hid, go)
    except Exception:
        d["xu"] = ""
    return d

# t = last activity so newly collected signals on an existing cluster rise to the tip.
_LIVE_COLS = ("cluster_id id, COALESCE(updated, first_seen) t, first_seen fs, event_time, title, category, location, lat, lon, score, rank, confidence, watchlist, "
              "n_items, families, links, brief, NULL sources")
_ARCH_COLS = ("id, t, t fs, NULL event_time, title, category, location, lat, lon, score, rank, confidence, watchlist, n_items, families, links, "
              "NULL brief, sources")
_TCOL = "COALESCE(updated, first_seen)"

def _qwhere(words, cols):
    w, a = "", []
    for x in words:
        w += " AND (" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in cols) + ")"
        a += ["%" + x.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"] * len(cols)
    return w, a

def _miles(a, b, c, d):
    import math
    p = math.pi / 180
    x = 0.5 - math.cos((c - a) * p) / 2 + math.cos(a * p) * math.cos(c * p) * (1 - math.cos((d - b) * p)) / 2
    return 3958.8 * 2 * math.asin(math.sqrt(max(0, x)))

def _geo_clause(lat, lon, r_mi):
    """Bounding-box SQL plus args. Tight enough that a follow-up haversine drops almost nothing."""
    if lat is None or lon is None or not r_mi:
        return "", []
    import math
    dlat = float(r_mi) / 69.0
    dlon = float(r_mi) / (69.0 * max(0.2, abs(math.cos(math.radians(float(lat))))))
    return (" AND lat IS NOT NULL AND lon IS NOT NULL AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            [float(lat) - dlat, float(lat) + dlat, float(lon) - dlon, float(lon) + dlon])

def _near(r, lat, lon, r_mi):
    if lat is None or lon is None or not r_mi: return True
    try:
        return _miles(float(lat), float(lon), float(r["lat"]), float(r["lon"])) <= float(r_mi) + 0.05
    except (TypeError, ValueError):
        return False

_SEV = {"lo": (0, 3), "mid": (4, 6), "hi": (7, 10)}
_CAT_KEYS = {c[0] for c in CATS}
_REG_KEYS = {"na", "la", "eu", "me", "af", "as", "oc", "sea", "gl"}

def _sev_clause(sev):
    rng = _SEV.get((sev or "").strip().lower())
    if not rng:
        return "", []
    return " AND rank IS NOT NULL AND rank BETWEEN ? AND ?", [rng[0], rng[1]]

def _keys(s, allowed):
    if not s:
        return None
    out = [x.strip() for x in str(s).split(",") if x.strip() in allowed]
    return set(out) or None

def _time_cut(time_win):
    """Inclusive ISO UTC lower bound for event_time/first_seen, or None if unfiltered."""
    w = (time_win or "").strip().lower()
    if not w:
        return None
    now = datetime.now(timezone.utc)
    if w == "today":
        try:
            from zoneinfo import ZoneInfo
            et = now.astimezone(ZoneInfo("America/New_York"))
            start = et.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        except Exception:
            start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return start.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        days = float(w)
    except ValueError:
        return None
    if not (0 < days <= 3650):
        return None
    from datetime import timedelta
    return (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

def _time_clause(time_win, live):
    cut = _time_cut(time_win)
    if not cut:
        return "", []
    if live:
        return " AND COALESCE(event_time, first_seen) >= ?", [cut]
    return " AND t >= ?", [cut]

def _facet_ok(r, archive, cats, regs):
    if not cats and not regs:
        return True
    title = _clean(r["title"])
    loc = _clean(r["location"])[:90] if r["location"] else ""
    if cats and cat_key(r["category"], title, archive) not in cats:
        return False
    if regs and region_key(loc, title, r["lat"], r["lon"]) not in regs:
        return False
    return True

def _fetch_window(ct, cid, fetch_n, newer, words, lists, lat, lon, r_mi, sev, time_win):
    """One over-fetch from live + archive, already sorted in page direction."""
    op, order = (">", "ASC") if newer else ("<", "DESC")
    geo, ga = _geo_clause(lat, lon, r_mi)
    sv, sa = _sev_clause(sev)
    rows = []
    c = _ro(DB)
    try:
        qw, qa = _qwhere(words, ("title", "location"))
        tw, ta = _time_clause(time_win, True)
        sql = (f"SELECT {_LIVE_COLS} FROM clusters WHERE ({_TCOL}{op}? OR ({_TCOL}=? AND cluster_id{op}?)) "
               f"AND watchlist IN ({','.join('?' * len(lists))}){qw}{geo}{sv}{tw} "
               f"ORDER BY {_TCOL} {order}, cluster_id {order} LIMIT ?")
        rows += [(r, False) for r in c.execute(sql, [ct, ct, cid, *lists, *qa, *ga, *sa, *ta, fetch_n])]
    finally:
        c.close()
    h = _hdb()
    if h is not None:
        try:
            qw, qa = _qwhere(words, ("title", "location"))
            tw, ta = _time_clause(time_win, False)
            sql = (f"SELECT {_ARCH_COLS} FROM stories WHERE (t{op}? OR (t=? AND id{op}?)) "
                   f"AND watchlist IN ({','.join('?' * len(lists))}){qw}{geo}{sv}{tw} "
                   f"ORDER BY t {order}, id {order} LIMIT ?")
            rows += [(r, True) for r in h.execute(sql, [ct, ct, cid, *lists, *qa, *ga, *sa, *ta, fetch_n])]
        finally:
            h.close()
    if geo:
        rows = [(r, a) for r, a in rows if _near(r, lat, lon, r_mi)]
    rows.sort(key=lambda x: (x[0]["t"] or "", x[0]["id"]), reverse=not newer)
    return rows

def _page_build(before=None, after=None, limit=100, q="", bg=False, lat=None, lon=None, r_mi=None,
                sev=None, cats=None, regs=None, time_win=None):
    """Page matching public rows. Loops past held/non-matching rows so `end` is the true end."""
    limit = max(1, min(MAXL, int(limit)))
    words = [w for w in re.split(r"\s+", (q or "").strip()) if w][:6]
    lists = (0, 1, 2) if bg else (0, 1)
    newer = bool(after)
    cur = after if newer else before
    if cur:
        ct, _, cid = cur.partition("|"); cid = cid or ("" if newer else "~")
    else:
        ct, cid = ("0000-01-01T00:00:00Z", "") if newer else ("9999-12-31T23:59:59Z", "~")
    cats = _keys(cats, _CAT_KEYS)
    regs = _keys(regs, _REG_KEYS)
    sev = (sev or "").strip().lower()
    if sev not in _SEV:
        sev = None
    # Rank is SQL-side; cats/regs/geo/public are post-filters, so over-fetch and continue.
    post = bool(cats or regs or (lat is not None))
    fetch_n = min(MAXL, max((limit + 1) * (8 if post else 4), 80))
    acc, seen = [], set()
    for _ in range(24):
        batch = _fetch_window(ct, cid, fetch_n, newer, words, lists, lat, lon, r_mi, sev, time_win)
        if not batch:
            break
        edge = batch[-1][0]
        ct, cid = edge["t"] or "", edge["id"]
        for r, a in batch:
            rid = r["id"]
            if rid in seen:
                continue
            if not _public_row(r, a) or not _facet_ok(r, a, cats, regs):
                continue
            seen.add(rid)
            acc.append((r, a))
        if len(acc) >= limit + 1:
            break
        if len(batch) < fetch_n:
            break
    more = len(acc) > limit
    rows = acc[:limit]
    # Do not warm share cards on the list path: photo work was stalling each page 5–7s.
    items = [_item(r, a, warm_budget=[0]) for r, a in rows]
    if newer:
        items.reverse()
    edge = (items[0] if newer else items[-1]) if items else None
    nxt = f"{edge['t']}|{edge['id']}" if edge and more else None
    return {"items": items, "next": nxt, "end": nxt is None, "dir": "newer" if newer else "older", "limit": limit}

def _reset_caches():
    """Forget cached pages, row tags and the gate snapshot (tests; also handy after a manual DB change)."""
    with _PC_LK:
        _PC["v"].clear(); _PC["t"].clear()
    _PA.clear(); _XC.clear(); _SNAP.clear()

def _warming():
    return bool(getattr(_TL, "warm", False))

def _pkey(before, after, limit, q, bg, lat, lon, r_mi, sev, cats, regs, time_win):
    return (before, after, int(limit) if limit is not None else 100, q or "", bool(bg),
            lat, lon, r_mi, sev or "", cats or "", regs or "", time_win or "")

def _pstore(key, out):
    with _PC_LK:
        _PC["v"][key] = out
        _PC["t"][key] = time.time()
        if len(_PC["v"]) > 64:
            for k in sorted(_PC["t"], key=_PC["t"].get)[:32]:
                _PC["v"].pop(k, None); _PC["t"].pop(k, None); _PA.pop(k, None)

def page(before=None, after=None, limit=100, q="", bg=False, lat=None, lon=None, r_mi=None,
         sev=None, cats=None, regs=None, time_win=None):
    """Page matching public rows. Cached 3 s; a stale copy (up to 20 s) is served while the warm thread rebuilds
    it, so a request rarely builds. Row tags and the public gate come from memory (see the speed layer above)."""
    args = (before, after, limit, q, bg, lat, lon, r_mi, sev, cats, regs, time_win)
    key = _pkey(*args)
    now = time.time()
    hit = _PC["v"].get(key)
    age = now - _PC["t"].get(key, 0)
    if len(_PA) > 96:
        _PA.clear()
    _PA[key] = (args, now)
    if hit is not None:
        if age < _PC_TTL:
            return hit
        if age < _PC_STALE and _warm_alive():
            return hit
    start_warm()
    out = _page_build(*args)
    _pstore(key, out)
    return out

# ---- the one warm thread (name has no "loop": render_app's thread guard counts those)
_STD = [dict(limit=100), dict(limit=100, sev="hi"), dict(limit=100, sev="mid"), dict(limit=100, sev="lo"),
        dict(limit=200, sev="hi"), dict(limit=200, sev="mid"), dict(limit=200, sev="lo"), dict(limit=200)]

def start_warm():
    if os.environ.get("BN_WIRE_WARM", "1") == "0" or _warm_alive():
        return
    with _WARM_LK:
        if _warm_alive():
            return
        t = threading.Thread(target=_warm_main, name="bn-wire-warm", daemon=True)
        _WARM["thread"] = t
        t.start()

def _warm_main():
    _TL.warm = True
    while True:
        try:
            _warm_cycle()
        except Exception as ex:
            _WARM["err"] = f"{type(ex).__name__}: {ex}"[:160]
        time.sleep(1.0)

def _warm_cycle():
    now = time.time()
    s = _SNAP.get("s")
    if s is None or now - s["t"] >= _SNAP_TTL:
        _snap_refresh(block=True)
    # 1. rebuild pages that were asked for in the last 3 minutes and are older than ~2 s (standard ones always)
    for a in _STD:
        args = (None, None, a.get("limit", 100), "", False, None, None, None, a.get("sev"), None, None, None)
        _PA.setdefault(_pkey(*args), (args, now - 120))
    for key, (args, last) in list(_PA.items()):
        if now - last > 180 or now - _PC["t"].get(key, 0) < 2.0:
            continue
        try:
            _pstore(key, _page_build(*args))
        except sqlite3.Error as ex:
            _WARM["err"] = "page: " + str(ex)[:120]
        time.sleep(0.01)
    # 2. fill the per-row tag cache a slice at a time (newest public live rows, then every rank 7+ row)
    _warm_rows(25)

def _warm_rows(n):
    c = _ro(DB)
    try:
        newest = list(c.execute(f"SELECT {_LIVE_COLS} FROM clusters WHERE watchlist IN (0,1) ORDER BY {_TCOL} DESC, cluster_id DESC LIMIT 700"))
        hi = list(c.execute(f"SELECT {_LIVE_COLS} FROM clusters WHERE watchlist IN (0,1) AND rank>=7 ORDER BY {_TCOL} DESC LIMIT 400"))
    finally:
        c.close()
    seen, rows = set(), []
    for r in newest + hi:
        if r["id"] not in seen:
            seen.add(r["id"]); rows.append(r)
    done = 0
    now = time.time()
    for r in rows:
        if done >= n:
            break
        e = _XC.get(r["id"])
        if e is not None and now - e[2] < _XC_TTL:
            continue
        if not _public_row(r, False):
            continue
        try:
            _item(r, False, compute=True)            # fills _XC (rows with fewer than 3 tags too)
            if e is not None:
                pass
        except Exception:
            pass
        done += 1
        time.sleep(0.01)
    _warm_bake(rows[:150])

def _warm_bake(rows):
    """Queue card bakes the way story_writer.allow() used to on every list call, once per story per 10 minutes."""
    now = time.time()
    try:
        import share_card
    except Exception:
        return
    for r in rows:
        cid = r["id"]
        if now - _WARM["baked"].get(cid, 0) < 600 or not _public_row(r, False):
            continue
        _WARM["baked"][cid] = now
        try:
            if not share_card.card_baked(cid):
                share_card.bake_card(cid)
        except Exception:
            pass
    if len(_WARM["baked"]) > 2000:
        _WARM["baked"].clear()

def xu_for_id(cid):
    """Post-on-X URL for one live row (the timeline asks when a row was not pre-warmed). Computed once, then cached."""
    if not re.match(r"^[A-Za-z0-9_.:\-]{1,80}$", cid or ""):
        return ""
    c = _ro(DB)
    try:
        rows = list(c.execute(f"SELECT {_LIVE_COLS} FROM clusters WHERE watchlist IN (0,1) AND cluster_id=?", (cid,)))
    finally:
        c.close()
    if not rows or not _public_row(rows[0], False):
        return ""
    return _item(rows[0], False, compute=True).get("xu", "")

def items_for(ids):
    """Wire items (same shape as /api/wire_tl) for these live cluster ids, newest first. Used by the realtime stream (realtime.py)."""
    ids = [i for i in dict.fromkeys(ids or []) if i][:500]
    if not ids: return []
    c = _ro(DB)
    try: rows = list(c.execute(f"SELECT {_LIVE_COLS} FROM clusters WHERE watchlist IN (0,1) AND cluster_id IN ({','.join('?' * len(ids))})", ids))
    finally: c.close()
    rows.sort(key=lambda r: (r["t"] or "", r["id"]), reverse=True)
    rows = [r for r in rows if _public_row(r, False)]
    _wb = [20]
    return [_item(r, False, warm_budget=_wb) for r in rows]

def bust_meta():
    """Forget the cached meta (totals) so the next read rebuilds it (realtime.py calls this at most every 2 minutes)."""
    with _LK: _M["t"] = 0

def count(q="", bg=False):
    words = [w for w in re.split(r"\s+", (q or "").strip()) if w][:6]
    lists = (0, 1, 2) if bg else (0, 1)
    n = 0; lo = hi = None
    c = _ro(DB)
    try:
        qw, qa = _qwhere(words, ("title", "location"))
        r = c.execute(f"SELECT COUNT(*), MIN(first_seen), MAX({_TCOL}) FROM clusters WHERE watchlist IN ({','.join('?' * len(lists))}){qw}", [*lists, *qa]).fetchone()
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

def _rt_ver():
    try: return str(int(os.path.getmtime(os.path.join(BASE, "realtime_static", "client.js")))) + "r"
    except OSError: return "0"

def page_html():
    start_warm()
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
<link rel="stylesheet" href="{w2}/wire2.css?v=7"><link rel="stylesheet" href="/api/wire_tl/app.css?v={v_css}">
<link rel="preload" as="image" href="/bnt/media/wthero-m.jpg?v=1" media="(max-width:700px)"><link rel="preload" as="image" href="/bnt/media/wtvid-d.jpg?v=1" media="(min-width:701px)"></head>
<body class="w2 tl"><header class="w2-bar" id="w2_bar"><a class="w2-wm" href="/?intro=1" aria-label="BLACKOUT.NETWORK intro">blackout.network</a>
<button type="button" class="w2-mbtn" id="w2_open" aria-label="Open menu" aria-controls="w2_menu" aria-expanded="false"><span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span><span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span></button></header>
{menu}
<div class="tl-bg" aria-hidden="true"><picture><source media="(max-width:700px)" srcset="/bnt/media/wthero-m.jpg?v=1"><img src="/bnt/media/wtvid-d.jpg?v=1" alt="" decoding="async" fetchpriority="high"></picture>
<video class="tl-vid" muted loop playsinline preload="none" disablepictureinpicture tabindex="-1" data-webm="/bnt/media/wtvid-d.webm?v=1" data-mp4="/bnt/media/wtvid-d.mp4?v=1"></video><i class="tl-veil"></i></div>
<main id="tl_main">
<section class="tl-hero" aria-label="The Wire"><div class="tl-hc"><p class="w2-eb">The Wire &middot; Timeline</p><h1 class="w2-ht">Every signal</h1>
<p class="w2-hl" id="tl_line">{E(line)}</p><p class="tl-stale" id="tl_stale" hidden aria-live="polite"></p><a class="w2-btn" href="#tl_start" id="tl_enter">Enter the timeline <span aria-hidden="true">&darr;</span></a></div>
<a class="tl-cue" href="#tl_start" aria-label="Scroll to the timeline"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.4"/></svg></a></section>
<div id="tl_start"></div>
<div class="tl-ctl" id="tl_ctl">
 <div class="tl-row1">
  <label class="tl-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="1.4"/></svg>
   <input id="tl_q" type="search" inputmode="search" enterkeyhint="search" autocomplete="off" spellcheck="false" placeholder="Search every signal" aria-label="Search every signal"><button type="button" id="tl_qx" class="tl-qx" aria-label="Clear search" hidden>&times;</button></label>
  <button type="button" class="tl-b" id="tl_filt" aria-expanded="false" aria-controls="tl_sheet" aria-label="Filters"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6 7.5V19l-4 2v-8.5L4 5z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="miter"/></svg><span>Filters</span><b class="tl-fbadge" id="tl_fbadge" hidden></b></button>
  <button type="button" class="tl-b" id="tl_when" aria-expanded="false" aria-controls="tl_jump"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 10h16M9 3.5v4M15 3.5v4" stroke="currentColor" stroke-width="1.4"/></svg><span>Date</span></button>
  <button type="button" class="tl-b tl-cond" id="tl_cond" aria-pressed="false" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v6m0 0-3-3m3 3 3-3M12 21v-6m0 0-3 3m3-3 3 3M4 12h16" fill="none" stroke="currentColor" stroke-width="1.4"/></svg><span class="tl-cl">Condense</span></button>
  <button type="button" class="tl-b" id="tl_ref" aria-label="Refresh"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="miter"/></svg><span>Refresh</span></button>
 </div>
 <div class="tl-sheet" id="tl_sheet" hidden>
  <div class="tl-sheet-h"><span>Filters</span><button type="button" class="tl-clear" id="tl_fclear">Clear all</button></div>
  <div class="tl-fg"><span class="tl-cg">Type</span><div class="tl-chips wrap" id="tl_chips_c" role="group" aria-label="Type"></div></div>
  <div class="tl-fg"><span class="tl-cg">Region</span><div class="tl-chips wrap" id="tl_chips_r" role="group" aria-label="Region"></div></div>
  <div class="tl-fg" role="group" aria-label="Location"><span class="tl-cg">Location</span>
   <form class="tl-loc" id="tl_locf"><input id="tl_loc" type="text" inputmode="search" enterkeyhint="search" autocomplete="off" spellcheck="false" maxlength="80" placeholder="ZIP or place" aria-label="ZIP or place"><button type="submit" class="tl-b" id="tl_locgo">Set</button></form>
   <div class="tl-chips wrap" id="tl_rad" role="group" aria-label="Radius"><button type="button" class="tl-chip" data-r="10">10 mi</button><button type="button" class="tl-chip" data-r="25">25 mi</button><button type="button" class="tl-chip" data-r="50">50 mi</button><button type="button" class="tl-chip" data-r="100">100 mi</button></div>
   <p class="tl-loclab" id="tl_loclab" hidden></p>
  </div>
  <div class="tl-fg"><span class="tl-cg">Time</span><div class="tl-chips wrap" id="tl_time" role="group" aria-label="Time"><button type="button" class="tl-chip" data-t="">All</button><button type="button" class="tl-chip" data-t="today">Today</button><button type="button" class="tl-chip" data-t="1">24 hours</button><button type="button" class="tl-chip" data-t="7">7 days</button><button type="button" class="tl-chip" data-t="30">30 days</button></div></div>
  <div class="tl-fg"><span class="tl-cg">Severity</span><div class="tl-chips wrap" id="tl_sev" role="group" aria-label="Severity"><button type="button" class="tl-chip" data-s="">Any</button><button type="button" class="tl-chip" data-s="lo">0–3</button><button type="button" class="tl-chip" data-s="mid">4–6</button><button type="button" class="tl-chip" data-s="hi">7–10</button></div></div>
 </div>
 <div class="tl-jump" id="tl_jump" hidden><div class="tl-jq" id="tl_jq"></div><label class="tl-jd"><span>Go to date</span><input type="date" id="tl_date"></label></div>
 <div class="tl-stat"><button type="button" class="tl-now" id="tl_now" aria-label="Current date; tap to jump"></button><span id="tl_stat" aria-live="polite"></span><span id="tl_upd" class="tl-upd" hidden></span><button type="button" class="tl-clear" id="tl_clear" hidden>Clear</button></div>
</div>
<section class="tl-wrap" aria-label="Timeline"><div class="tl-list" id="tl_list" role="list"></div><div class="tl-foot" id="tl_foot"></div></section>
<button type="button" class="tl-newp" id="tl_new" hidden></button>
<button type="button" class="tl-top" id="tl_top" hidden aria-label="Back to the latest"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><span>Latest</span></button>
</main>
<footer class="w2-foot"><p class="w2-tag">Global threat monitoring</p><p class="w2-legal">Independent early-warning signals. Not an official alert service. <a href="/scoring">How we score</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a></p></footer>
<script>window.BN_TL={json.dumps(cfg)};</script>
<script src="{w2}/wire2.js?v=3" defer></script><script src="/api/rt/client.js?v={_rt_ver()}" defer></script><script src="/api/wire_tl/app.js?v={v_js}" defer></script></body></html>'''

# ------------------------------------------------------------------ location (keyless) + local crime
_ZIP = None
def _zip_table():
    global _ZIP
    if _ZIP is None:
        try:
            with open(os.path.join(BASE, "newsletter_zip.json"), encoding="utf-8") as fh:
                _ZIP = json.load(fh)
        except Exception:
            _ZIP = {}
    return _ZIP

def geocode_q(q):
    """US ZIP (full-precision Census ZCTA centroid) or a place name via the offline gazetteer. No API key."""
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:80]
    if not q:
        return {"ok": False, "message": "Enter a US ZIP code or a place name."}
    m = re.fullmatch(r"(\d{5})(?:-\d{4})?", q)
    if m:
        z = _zip_table().get(m.group(1))
        if z:
            lab = (z[2] or "").strip() or ("ZIP " + m.group(1))
            return {"ok": True, "place": {"label": lab, "lat": float(z[0]), "lon": float(z[1]), "cc": "US", "kind": "zip", "zip": m.group(1)}}
    try:
        from newsletter import geocode_place
        p = geocode_place(q)
    except Exception:
        p = None
    if not p:
        return {"ok": False, "message": "We couldn't find that place. Try a US ZIP or a city like Sanford, FL."}
    return {"ok": True, "place": p}

def local_crime(q):
    """Cached local crime headlines for a US ZIP or city. Empty (not an error) when the flag is off or the place is outside the US."""
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:80]
    if not q:
        return {"ok": False, "items": [], "message": "Enter a US ZIP or city."}
    try:
        import crime, crime_news
        if not crime_news.on():
            return {"ok": True, "items": [], "off": True}
        p = crime.resolve(q)
        a = crime_news.area_for(p) if p else None
        if not a:
            return {"ok": True, "items": [], "place": p}
        d = crime_news.reports(a, allow_fetch=True)
        items = []
        for i, r in enumerate(d.get("items") or []):
            when = r.get("date") or ""
            try:
                from datetime import datetime as _dt
                t = _dt.fromisoformat(when).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                t = when
            items.append({"id": "cr-%s-%s" % (i, (r.get("url") or "")[-16:]), "t": t, "h": r.get("title") or "",
                          "s": r.get("place") or r.get("source") or "", "d": "", "k": "crime", "g": "na", "r": None,
                          "c": "", "loc": r.get("place") or "", "n": 1, "f": 0, "src": [r.get("source") or ""],
                          "l": [{"u": r.get("url"), "s": r.get("source") or ""}], "a": 0, "w": 0, "et": None, "do": 0,
                          "lat": None, "lon": None, "fs": t, "crime": 1, "official": bool(r.get("official"))})
        return {"ok": True, "items": items, "fetched": d.get("fetched"), "place": p}
    except Exception as ex:
        return {"ok": False, "items": [], "error": str(ex)[:160]}


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
        if n == "xu":
            try: return 200, {"xu": xu_for_id((g("id", "") or "")[:80])}
            except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
        if n == "geo":
            return 200, geocode_q((g("q", "") or "")[:80])
        if n == "crime":
            return 200, local_crime((g("q", "") or "")[:80])
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
        lat = lon = rmi = None
        try:
            if g("lat"): lat = float(g("lat"))
            if g("lon"): lon = float(g("lon"))
            if g("r"): rmi = float(g("r"))
        except (TypeError, ValueError):
            return 400, {"error": "lat, lon and r must be numbers"}
        if (lat is None) != (lon is None):
            return 400, {"error": "lat and lon are required together"}
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return 400, {"error": "lat/lon out of range"}
        if lat is not None and rmi is None: rmi = 25
        if rmi is not None and not (1 <= rmi <= 500):
            return 400, {"error": "r must be 1..500 miles"}
        sev = (g("sev", "") or "")[:8]
        cats = (g("cats", "") or "")[:200]
        regs = (g("regs", "") or "")[:200]
        time_win = (g("time", "") or "")[:16]
        try: return 200, page(before, after, lim, q, g("bg") == "1", lat, lon, rmi, sev, cats, regs, time_win)
        except sqlite3.Error as ex: return 503, {"error": "database busy: " + str(ex)[:160]}
    return 404, {"error": "not found"}
