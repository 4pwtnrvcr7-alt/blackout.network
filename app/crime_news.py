"""Local crime REPORTS layer (Matt, Nov 17 2026): real, recent incident items for one area, not just statistics.

For a resolved crime.py place (ZIP, city or county) this pulls the last ~7 days of public items from:
  1. official police / sheriff release pages listed in REGISTRY (per county FIPS), parsed from their own HTML or RSS;
  2. local outlets' own RSS feeds listed in REGISTRY (kept only when the item names a place in the area);
  3. Google News RSS searches scoped to the city / county + state + crime terms (kept only when the headline names a
     place in the area and, for registry areas, only from the area's known local outlets and agencies).
Each item is headline + date + place + source + link. Nothing is invented or rewritten: the headline is the outlet's
own headline (outlet suffix removed). No images, so no mugshots. Items are deduped and cached per area
(memory + small JSON file, 30 min fresh, served stale up to 24 h when a source fails). Any failure returns [] and the
page / newsletter fall back to statistics only. Rollback: Render env BN_CRIME_NEWS=0.
"""
import concurrent.futures as CF, html, json, os, re, tempfile, threading, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

FLAG = "BN_CRIME_NEWS"
def on(): return os.environ.get(FLAG, "").strip() != "0"

ETZ = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (compatible; BLACKOUT.NETWORK crime reports; +https://blackout.network/crime)"
DAYS_NEWS, DAYS_OFFICIAL, DAYS_BACKFILL, MIN_RECENT = 7, 30, 30, 4   # older items (marked "earlier") only fill a thin week
FRESH_S, STALE_S = 1800, 86400
TIMEOUT_S, DEADLINE_S = 5, 7
CACHE_DIR = os.path.join(tempfile.gettempdir(), "bn_crime_news")

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
          "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
          "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
          "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
          "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
          "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}

# Per-county registry (FIPS). agencies: official release pages; feeds: outlet RSS; outlets: domains trusted as local for the area.
_ORL_OUTLETS = ["orlandosentinel.com", "wftv.com", "wesh.com", "clickorlando.com", "fox35orlando.com", "mynews13.com", "wmfe.org",
                "seminolesheriff.org", "sanfordfl.gov", "ocso.com", "orlando.gov", "flhsmv.gov", "fdle.state.fl.us"]
_ORL_FEEDS = [("WKMG News 6 ClickOrlando", "https://www.clickorlando.com/arc/outboundfeeds/rss/category/news/local/?outputType=xml"),
              ("WFTV Channel 9", "https://www.wftv.com/arc/outboundfeeds/rss/category/news/local/?outputType=xml"),
              ("FOX 35 Orlando", "https://www.fox35orlando.com/rss.xml")]
_ORL_SITES = ["wesh.com", "orlandosentinel.com", "clickorlando.com", "wftv.com", "fox35orlando.com", "mynews13.com"]   # outlets without an open RSS feed are read via Google News site: search
REGISTRY = {
    "12117": {"county": "Seminole County", "st": "FL",   # Sanford, Lake Mary, Longwood, Oviedo, Winter Springs, Altamonte Springs, Casselberry
              "places": ["Sanford", "Lake Mary", "Longwood", "Oviedo", "Winter Springs", "Altamonte Springs", "Casselberry", "Geneva", "Chuluota",
                         "Seminole County", "Seminole deputies", "Seminole sheriff"],
              "agencies": [{"name": "Seminole County Sheriff's Office", "url": "https://www.seminolesheriff.org/", "parser": "scso"},
                           {"name": "Sanford Police Department", "gnews": "\"Sanford police\" Florida"}],
              "feeds": _ORL_FEEDS, "outlets": _ORL_OUTLETS, "sites": _ORL_SITES},
    "12095": {"county": "Orange County", "st": "FL", "places": ["Orlando", "Orange County", "Apopka", "Winter Park", "Ocoee", "Winter Garden", "Maitland", "Pine Hills", "Parramore"],
              "agencies": [], "feeds": _ORL_FEEDS, "outlets": _ORL_OUTLETS, "sites": _ORL_SITES},
}

CRIME_RX = re.compile(r"\b(police|polic[ei]a|deput(y|ies)|sheriff'?s?|trooper|FHP|arrest(s|ed)?|charged|charges|indicted|accused|suspects?|shoot(ing|ings|er)?|shot|"
                      r"stabb(ed|ing)|murder(ed|s)?|homicide|killed|kill(ing)?|manslaughter|robber(y|ies)|robbed|burglar(y|ies|ized)?|theft|stole[n]?|carjack(ing|ed)?|"
                      r"assault(ed)?|battery|kidnapp(ing|ed)|abduct(ed|ion)|traffick(ing|ed)|fraud|scam|DUI|hit-and-run|hit and run|gunfire|gunman|"
                      r"armed|weapon|firearm|drugs?|fentanyl|cocaine|meth|narcotics|sex(ual)? (offender|abuse|battery|assault)|child (porn|abuse)|"
                      r"missing|amber alert|manhunt|standoff|lockdown|vandal(ism|ized)|arson|investigation|investigating|detectives?|crime)\b", re.I)
NOT_CRIME_RX = re.compile(r"\b(weather|forecast|flood(ing)?|rain|hurricane|storm|football|basketball|baseball|game|stadium|recipe|restaurant|inspection|"
                          r"concert|festival|parade|holiday|veterans|ribbon|retir(es|ing|ement)|hiring|recruit|election|budget|commission|comptroller)\b", re.I)
INCIDENT_RX = re.compile(r"\b(arrest(s|ed)?|charged|charges|indicted|accused|suspects?|shoot(ing|ings|er)?|shot|stabb(ed|ing)|murder(ed|s)?|homicide|killed|"
                         r"manslaughter|robber(y|ies)|robbed|burglar(y|ies|ized)?|theft|stole[n]?|carjack(ing|ed)?|assault(ed)?|battery|kidnapp(ing|ed)|abduct(ed|ion)|"
                         r"traffick(ing|ed)|fraud|DUI|hit-and-run|hit and run|gunfire|gunman|standoff|manhunt|missing|amber alert|arson|vandal(ism|ized)|"
                         r"sentenced|convicted|pleads? guilty|deadly|dead|death investigation|crash)\b", re.I)
SKIP_RX = re.compile(r"\bmug ?shots?\b|\bbooking photos?\b|\bjail log\b", re.I)

_mem = {}; _lock = threading.Lock()

def _get(url, timeout=TIMEOUT_S):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_500_000).decode("utf-8", "replace")

def _dom(u):
    try: return urllib.parse.urlsplit(u).netloc.lower().removeprefix("www.")
    except Exception: return ""

def _clean(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", str(t or ""))); return re.sub(r"\s+", " ", t).strip()

def _ts(s):
    try:
        d = parsedate_to_datetime(s); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception: return None

def _rss(text):
    out = []
    try: root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError: return out
    for it in root.iter("item"):
        s = it.find("source")
        out.append({"title": _clean(it.findtext("title")), "url": (it.findtext("link") or "").strip(), "when": _ts(it.findtext("pubDate") or ""),
                    "desc": _clean(it.findtext("description"))[:400], "src_name": _clean(s.text) if s is not None else "",
                    "src_url": (s.get("url") if s is not None else "") or ""})
    return out

def _gnews(q, days=DAYS_NEWS):
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + f" when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    rows = _rss(_get(u))
    for r in rows:   # Google appends " - Outlet" to the outlet's headline; keep the outlet's own words only
        if r["src_name"] and r["title"].endswith(" - " + r["src_name"]): r["title"] = r["title"][: -len(r["src_name"]) - 3].strip()
        r["via"] = "Google News"
    return rows

def _scso(url):
    """Seminole County Sheriff's Office front page: <h4>headline</h4> Month D, YYYY - summary ... <a href=...mediareports/...>."""
    s = _get(url); out = []
    for m in re.finditer(r"<h4>(.*?)</h4>\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-\u2013\u2014].*?<a href=\"([^\"]*mediareports/[^\"]+)\"", s, re.S):
        try: d = datetime.strptime(m.group(2), "%B %d, %Y").replace(hour=12, tzinfo=ETZ)
        except ValueError: continue
        out.append({"title": _clean(m.group(1)), "url": urllib.parse.urljoin(url, html.unescape(m.group(3))), "when": d, "desc": "",
                    "src_name": "Seminole County Sheriff's Office", "src_url": url, "official": True})
    return out
PARSERS = {"scso": _scso}

def area_for(place, county_name=None, agency_cities=()):
    """place: crime.resolve() dict. -> {key, label, city, county, st, places[], registry} or None (US local places only)."""
    if not place or place.get("cc") != "US" or place.get("kind") not in ("zip", "city", "county"): return None
    st = (place.get("st") or "").upper()[:2]; fips = place.get("fips") or ""
    reg = REGISTRY.get(fips) or {}
    city = place.get("city") or ""
    if not city and place.get("kind") == "zip":
        lab = place.get("label") or ""; city = lab.split(",")[0].strip() if "," in lab and not lab.upper().startswith("ZIP") else ""
    county = reg.get("county") or county_name or ""
    places = list(dict.fromkeys([x for x in ([city] + list(reg.get("places") or []) + [county] + list(agency_cities)) if x and len(x) >= 4]))[:16]
    if not places: return None
    key = re.sub(r"[^a-z0-9]+", "-", f"{fips or 'x'}-{city or county}-{st}".lower()).strip("-")
    return {"key": key, "label": place.get("label") or city or county, "city": city, "county": county, "st": st, "fips": fips,
            "places": places, "registry": bool(reg), "reg": reg}

def _place_hit(text, places):
    for p in places:
        if re.search(r"(?<![A-Za-z])" + re.escape(p) + r"(?![A-Za-z])", text, re.I): return p
    return None

def _other_state(title, st):
    for ab, nm in STATES.items():
        if ab == st: continue
        if re.search(r"(?<![A-Za-z])" + re.escape(nm) + r"(?![A-Za-z])", title): return True
    return False

def _norm(t): return set(w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2)

def _collect(a):
    jobs = []; reg = a["reg"]; stn = STATES.get(a["st"], a["st"])
    for ag in reg.get("agencies") or []:
        if ag.get("parser") in PARSERS: jobs.append(("official", ag["name"], lambda ag=ag: PARSERS[ag["parser"]](ag["url"])))
        if ag.get("gnews"): jobs.append(("news", ag["name"], lambda ag=ag: _gnews(ag["gnews"])))
    for nm, u in reg.get("feeds") or []:
        jobs.append(("feed", nm, lambda u=u, nm=nm: [dict(r, src_name=nm, src_url=u, via="") for r in _rss(_get(u))]))
    terms = "(police OR deputies OR sheriff OR arrested OR charged OR shooting OR stabbing OR robbery OR burglary OR homicide OR murder)"
    pl = [x for x in a["places"] if " " not in x or x.endswith("County") or x in ("Lake Mary", "Winter Springs", "Altamonte Springs")][:8]
    ors = " OR ".join(f'"{x}"' for x in pl)
    if reg.get("sites") and ors:
        sites = " OR ".join("site:" + d for d in reg["sites"])
        jobs.append(("news", "Google News", lambda: _gnews(f"({sites}) ({ors}) {terms}")))
        jobs.append(("news", "Google News", lambda: _gnews(f"({sites}) ({ors}) {terms}", DAYS_BACKFILL)))
    elif len(pl) > 1: jobs.append(("news", "Google News", lambda: _gnews(f"({ors}) {stn} {terms}")))
    if a["city"]: jobs.append(("news", "Google News", lambda: _gnews(f'"{a["city"]}" {stn} {terms}', DAYS_BACKFILL)))
    if a["county"]: jobs.append(("news", "Google News", lambda: _gnews(f'"{a["county"]}" {stn} {terms}', DAYS_BACKFILL)))
    rows, errs, t0 = [], [], time.time()
    with CF.ThreadPoolExecutor(max_workers=6) as ex:
        fut = {ex.submit(fn): (kind, nm) for kind, nm, fn in jobs}
        try:
            for f in CF.as_completed(fut, timeout=DEADLINE_S):
                kind, nm = fut[f]
                try: rows += [dict(r, _kind=kind) for r in f.result()]
                except Exception as e: errs.append(f"{nm}: {type(e).__name__}")
        except CF.TimeoutError:
            errs.append("deadline")
    now = datetime.now(timezone.utc); out, seen_u, seen_t = [], set(), []
    allow = set(reg.get("outlets") or [])
    for r in sorted(rows, key=lambda r: (not r.get("official"), -(r["when"].timestamp() if r.get("when") else 0))):
        t = r.get("title") or ""; w = r.get("when")
        if not t or not w or not r.get("url"): continue
        age = (now - w).total_seconds() / 86400
        if age < -0.5 or age > (DAYS_OFFICIAL if r.get("official") else DAYS_BACKFILL): continue
        if SKIP_RX.search(t) or not CRIME_RX.search(t) or (not r.get("official") and not INCIDENT_RX.search(t)) or (NOT_CRIME_RX.search(t) and not re.search(r"\b(arrest|charged|shooting|shot|killed|deputies|police)\b", t, re.I)): continue
        dom = _dom(r.get("src_url") or r["url"])
        if a["registry"] and not r.get("official") and dom not in allow: continue   # registry areas: known local outlets only
        hit = _place_hit(t, a["places"]) or (r.get("_kind") == "feed" and _place_hit(r.get("desc") or "", a["places"]))
        if r.get("official"): hit = hit or (a["county"] or a["city"])
        if not hit or _other_state(t, a["st"]): continue
        u = r["url"]; nt = _norm(t)
        if u in seen_u or any(len(nt & s) / max(1, len(nt | s)) > 0.55 for s in seen_t): continue
        seen_u.add(u); seen_t.append(nt)
        out.append({"title": t[:200], "url": u, "date": w.astimezone(ETZ).isoformat(timespec="minutes"), "place": hit,
                    "source": r.get("src_name") or dom, "domain": dom, "official": bool(r.get("official")), "earlier": age > DAYS_NEWS})
    out.sort(key=lambda x: x["date"], reverse=True)
    recent = [x for x in out if not x["earlier"]][:12]
    older = [x for x in out if x["earlier"]][:max(0, MIN_RECENT - len(recent)) + 2] if len(recent) < MIN_RECENT else []
    return recent + older, errs, round(time.time() - t0, 2)

def _cache_path(key): return os.path.join(CACHE_DIR, key[:80] + ".json")

def reports(a, allow_fetch=True):
    """-> {"items": [...], "fetched": iso, "stale": bool, "errors": [...]} for area a (area_for()). Never raises."""
    if not a or not on(): return {"items": [], "fetched": None, "stale": False, "errors": ["off" if a else "no area"]}
    k = a["key"]; now = time.time()
    with _lock: c = _mem.get(k)
    if not c:
        try:
            with open(_cache_path(k)) as fh: c = json.load(fh)
        except Exception: c = None
    if c and now - c.get("t", 0) < FRESH_S: return dict(c["d"], stale=False)
    if not allow_fetch: return dict(c["d"], stale=True) if c and now - c.get("t", 0) < STALE_S else {"items": [], "fetched": None, "stale": False, "errors": ["not cached"]}
    try:
        items, errs, secs = _collect(a)
        d = {"items": items, "fetched": datetime.now(ETZ).isoformat(timespec="minutes"), "errors": errs, "secs": secs}
        if items or not c:
            c = {"t": now, "d": d}
            with _lock: _mem[k] = c
            try:
                os.makedirs(CACHE_DIR, exist_ok=True); tmp = _cache_path(k) + ".tmp"
                with open(tmp, "w") as fh: json.dump(c, fh)
                os.replace(tmp, _cache_path(k))
            except Exception: pass
            return dict(d, stale=False)
        return dict(c["d"], stale=True, errors=errs)   # every source failed or came back empty: keep the last good list
    except Exception as e:
        if c and now - c.get("t", 0) < STALE_S: return dict(c["d"], stale=True)
        return {"items": [], "fetched": None, "stale": False, "errors": [type(e).__name__]}

def fmt_date(iso):
    try: d = datetime.fromisoformat(iso).astimezone(ETZ)
    except Exception: return ""
    return d.strftime("%a %b %-d")
