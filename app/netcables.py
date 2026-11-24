"""Undersea cables for the /grid map (pt1785u, pt1812u).

Geometry: netmap_static/cables.json, built by tools/build_cables.py from OpenStreetMap (ODbL) and NOAA Office for Coastal
Management (U.S. waters, public domain). TeleGeography's free map data is CC BY-NC-SA (non-commercial), so it is not used.

Each drawn cable is coloured by inferred status, never official (operators publish no live feed):
  green  — working: no fault reports
  yellow — service interruption / degraded, damage under investigation, or the route crosses a zone with recent cable-damage news
  red    — out of service: a public report that the cable itself was cut, severed, or taken out of service
Sources: Google News RSS (one cable-damage query an hour, last-good fallback) plus documented recent cuts we already record.
"""
import json, os, re, time, urllib.parse
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import email.utils

BASE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(BASE, "netmap_static", "cables.json")
NEWS_DAYS, CONFLICT_DAYS, HIST_MONTHS = 14, 7, 36

# Risk-area outlines, used only to mark cables that cross a zone with recent damage news. Not drawn on the map.
ZONES = [
    dict(id="redsea", name="Red Sea and Bab el-Mandeb", cc=["YE", "DJ", "ER", "SA", "EG", "SD"],
         poly=[[32.55, 29.95], [32.7, 28.5], [33.6, 27.0], [34.3, 25.8], [35.2, 24.0], [35.8, 22.8], [36.9, 21.5], [37.3, 19.5], [38.5, 18.0], [39.6, 16.0], [40.8, 14.8], [42.5, 13.0], [43.2, 11.9], [43.7, 12.3], [43.4, 12.9], [42.8, 14.5], [42.6, 15.5], [41.8, 17.0], [40.6, 19.0], [39.2, 21.4], [38.4, 23.5], [37.2, 25.0], [36.0, 26.8], [35.0, 28.0], [33.6, 28.0], [32.8, 29.6]],
         q='"Red Sea" (Houthi OR missile OR drone OR attack OR warship OR navy)', kw=r"red sea|bab[- ]el[- ]mandeb|jeddah|yemen|djibouti|houthi",
         cuts=[dict(d="2024-02-24", t="Seacom, AAE-1 and EIG cut in the southern Red Sea; the leading explanation is the dragging anchor of the Rubymar after a Houthi missile strike",
                    src="Kentik", url="https://www.kentik.com/blog/what-caused-the-red-sea-submarine-cable-cuts/"),
               dict(d="2025-09-06", t="SMW4 and IMEWE cut near Jeddah; Microsoft Azure reported higher latency on Middle East routes",
                    src="Reuters", url="https://www.reuters.com/world/middle-east/red-sea-cable-cuts-disrupt-internet-across-asia-middle-east-2025-09-07/")]),
    dict(id="baltic", name="Baltic Sea and Gulf of Finland", cc=["FI", "EE", "LV", "LT", "SE", "DE", "PL", "DK"],
         poly=[[10.2, 54.2], [12.5, 54.0], [14.3, 53.9], [18.5, 54.5], [21.0, 55.2], [21.0, 56.9], [23.5, 57.4], [24.3, 59.3], [28.0, 59.5], [30.2, 59.9], [28.0, 60.5], [25.0, 60.3], [22.5, 60.0], [19.5, 60.3], [18.8, 59.4], [17.0, 57.5], [16.2, 56.2], [14.3, 55.4], [12.8, 55.5], [10.8, 55.2]],
         q='"Baltic Sea" (sabotage OR navy OR "shadow fleet" OR anchor OR warship OR investigation)', kw=r"baltic|gulf of finland|gotland|estlink|c-lion|finland|estonia|latvia|lithuania",
         cuts=[dict(d="2024-11-17", t="BCS East-West Interlink (Sweden-Lithuania) and C-Lion1 (Finland-Germany) severed within a day; investigators focused on the Yi Peng 3",
                    src="Reuters", url="https://www.reuters.com/business/media-telecom/telecoms-cable-linking-finland-germany-likely-severed-owner-says-2024-11-18/"),
               dict(d="2024-12-25", t="Eagle S anchor dragged across the Gulf of Finland, damaging the Estlink 2 power cable and four telecom cables",
                    src="Finnish Police", url="https://poliisi.fi/en/-/criminal-investigation-by-the-nbi-into-cable-damage-in-the-gulf-of-finland-concluded")]),
    dict(id="taiwan", name="Taiwan Strait", cc=["TW"],
         poly=[[117.6, 23.3], [118.6, 24.6], [119.4, 26.0], [120.1, 26.7], [121.0, 26.6], [121.9, 25.4], [121.2, 24.9], [120.6, 24.1], [120.2, 22.9], [120.4, 21.9], [119.4, 21.9], [118.0, 22.6]],
         q='"Taiwan Strait" (PLA OR military OR drills OR "coast guard" OR warship)', kw=r"taiwan|matsu|penghu|kinmen",
         cuts=[dict(d="2025-01-03", t="Trans-Pacific Express cable damaged off northern Taiwan; Taiwan named the Shunxin-39",
                    src="Reuters", url="https://www.reuters.com/world/asia-pacific/china-linked-shipowner-denies-taiwan-accusation-damaging-undersea-cable-2025-01-08/"),
               dict(d="2025-02-25", t="Taiwan-Penghu No. 3 cable cut; the captain of the Hong Tai 58 was later jailed",
                    src="Reuters", url="https://www.reuters.com/business/media-telecom/taiwan-jails-chinese-ship-captain-damaging-undersea-cables-2025-06-12/"),
               dict(d="2023-02-08", t="Both Matsu-Taiwan cables (TMSC-2 and TMSC-3) cut within a week; Matsu relied on microwave backup for weeks",
                    src="Taipei Times", url="https://www.taipeitimes.com/News/taiwan/archives/2023/02/10/2003794094")]),
]

CABLE_Q = '("undersea cable" OR "subsea cable" OR "submarine cable") (cut OR damaged OR severed OR fault OR outage OR repair)'
DAMAGE = re.compile(r"\b(cut|cuts|severed|damag\w*|fault\w*|outage|break|broken|rupture\w*|disrupt\w*|repair\w*|degrad\w*|intermittent)\b", re.I)
CABLE = re.compile(r"\b(undersea|subsea|submarine|sea|seabed|fib(?:re|er)[- ]optic|internet|telecom\w*|data|communications?)\s+cables?\b|\bcables?\s+(?:cut|damage)|sea[\s\-]*me[\s\-]*we|\bsmw[\s\-]?\d", re.I)
CONFLICT = re.compile(r"\b(attack\w*|strik\w*|missile\w*|drone\w*|sabotage\w*|seiz\w*|fired|hit|hits|clash\w*|incursion\w*|warship\w*|drills?|blockade\w*|shadow fleet|detain\w*|boarded)\b", re.I)
CUT = re.compile(r"\b(severed|out of service|ruptured)\b|\b(?:(?:the|an|a|its)\s+)?(?:undersea|subsea|submarine)?\s*cables?\s+(?:is|are|was|were|have been|has been)?\s*cut\b|\bcut(?:s)?\s+(?:in|on|to|of)\s+(?:the\s+)?(?:undersea|subsea|submarine)?\s*cables?\b|\bcables?\s+cut\b", re.I)
NOT_CABLE = re.compile(r"\b(power cable|electricity cable|gas pipeline|pipeline)\b", re.I)
_LAST = {}
_GEO, _INDEX = None, None

def _now(): return datetime.now(timezone.utc)
def _iso(d): return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None

def _rss(q, days):
    import netwatch as NW
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f"{q} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(NW._get(u, timeout=12)); out = []
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip(); src = (it.findtext("source") or "").strip()
        if src and t.endswith(" - " + src): t = t[: -len(src) - 3]
        try: pd = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except Exception: pd = None
        if pd and pd.tzinfo is None: pd = pd.replace(tzinfo=timezone.utc)
        out.append(dict(t=t[:220], src=src[:60], url=(it.findtext("link") or "")[:600], at=_iso(pd) if pd else None))
    return out

def news():
    """Raises if every query failed, so the cache keeps the last good copy instead of saying 'no news'."""
    res = dict(cable=None, conflict={}); ok = 0
    for t in (0, 3):
        try: time.sleep(t); res["cable"] = _LAST["cable"] = _rss(CABLE_Q, NEWS_DAYS); ok += 1; break
        except Exception: res["cable"] = _LAST.get("cable")
    for z in ZONES:   # kept so a failed hour can still use last-good conflict lists if we need them later
        time.sleep(2)
        try: res["conflict"][z["id"]] = _LAST[z["id"]] = [it for it in _rss(z["q"], CONFLICT_DAYS) if CONFLICT.search(it["t"])]; ok += 1
        except Exception: res["conflict"][z["id"]] = _LAST.get(z["id"])
    if not ok and not _LAST: raise RuntimeError("news search unavailable")
    res["ok"] = ok == 1 + len(ZONES); res["at"] = _iso(_now())
    return res

def _norm(s):
    s = re.sub(r"\s*seg(?:ment)?\.?\s*[\w.]+", " ", (s or ""), flags=re.I)
    s = re.sub(r"\s*\(([^)]*)\)\s*", r" \1 ", s)
    s = re.sub(r"\s*(cable system|submarine cable system|submarine cable|system)\s*", " ", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def _base(n):
    n = re.sub(r"\s*seg(?:ment)?\.?\s*[\w.]+", "", (n or ""), flags=re.I).strip()
    return n or (n or "").strip()

def _aliases(n):
    out, n0 = set(), (n or "").strip()
    if not n0: return out
    out.add(_norm(n0)); out.add(_norm(_base(n0)))
    m = re.search(r"sea[\s\-]*me[\s\-]*we[\s\-]*(\d+)", n0, re.I) or re.search(r"\bsmw[\s\-]*(\d+)\b", n0, re.I)
    if m: out.add("smw" + m.group(1)); out.add("seamewe" + m.group(1))
    m = re.search(r"c[\s\-]*lion[\s\-]*(\d+)", n0, re.I)
    if m: out.add("clion" + m.group(1))
    return {a for a in out if len(a) >= 4}

def _geo():
    global _GEO
    if _GEO is None:
        try:
            with open(GEO) as fh: _GEO = json.load(fh)
        except Exception: _GEO = {"features": [], "names": []}
    return _GEO

_NAMES = None
def cable_names():
    global _NAMES
    if _NAMES is None:
        gj = _geo(); fs = gj.get("features") or []
        nm = set(gj.get("names") or []) or {f["properties"]["n"] for f in fs if (f.get("properties") or {}).get("n")}
        nm |= {_base(n) for n in list(nm)}
        nm |= {f["properties"]["n"] for f in fs if f.get("geometry", {}).get("type") == "LineString" and (f.get("properties") or {}).get("n")}
        _NAMES = sorted({n.strip() for n in nm if n and n.strip()}, key=lambda x: (-len(x), x))
    return _NAMES

def _index():
    """Map alias tokens (smw3, seamewe3, …) to a preferred display name in our dataset."""
    global _INDEX
    if _INDEX is None:
        pref = {}
        def better(a, b):
            asg, bsg = bool(re.search(r"seg", a, re.I)), bool(re.search(r"seg", b, re.I))
            if asg != bsg: return not asg
            return len(a) <= len(b)
        for n in cable_names():
            for a in _aliases(n):
                if a not in pref or better(n, pref[a]): pref[a] = _base(n) or n
        _INDEX = pref
    return _INDEX

def _age_h(at):
    try: return (_now() - datetime.fromisoformat(str(at).replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception: return 1e9

def _dedupe(items):
    seen, out = set(), []
    for it in items:
        k = re.sub(r"\W+", " ", it["t"].lower())[:70]
        if k in seen: continue
        seen.add(k); out.append(it)
    return out

def _level(title):
    """2 = out of service, 1 = interruption / investigation, None = not a cable-fault report."""
    t = title or ""
    if NOT_CABLE.search(t) or not (DAMAGE.search(t) and CABLE.search(t)): return None
    return 2 if CUT.search(t) else 1

def _mentions(title):
    """Display names from our dataset that this headline names (including SMW5-style aliases)."""
    t, hit, idx = title or "", set(), _index()
    for nm in cable_names():
        if len(nm) >= 4 and re.search(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", t, re.I):
            hit.add(_base(nm) or nm)
    extra = []
    for m in re.finditer(r"sea[\s\-]*me[\s\-]*we[\s\-]*(\d+)|\bsmw[\s\-]*(\d+)\b", t, re.I):
        num = m.group(1) or m.group(2)
        extra += ["smw" + num, "seamewe" + num]
    for m in re.finditer(r"c[\s\-]*lion[\s\-]*(\d+)", t, re.I):
        extra.append("clion" + m.group(1))
    for a in extra:
        if a in idx: hit.add(idx[a])
    return sorted(hit, key=len, reverse=True)


def _in_poly(lon, lat, poly):
    inside, n, j = False, len(poly), len(poly) - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def _line_in_zone(coords, poly):
    if not coords or not poly: return False
    step = max(1, len(coords) // 80)
    return any(_in_poly(p[0], p[1], poly) for p in coords[::step])

def _variants(name):
    """Every dataset spelling of the same cable (SEA-ME-WE 3 vs SEA-ME-WE3, segments stripped)."""
    if not name: return set()
    al = _aliases(name)
    out = {_base(name) or name}
    for n in cable_names():
        if _aliases(n) & al:
            out.add(_base(n) or n)
    return out

def _put(cables, name, lv, status, reason, src=None, url=None, at=None):
    rec = dict(lv=lv, status=status, reason=reason)
    if src: rec["src"] = src
    if url: rec["url"] = url
    if at: rec["at"] = at
    for nm in _variants(name) or ({name} if name else set()):
        cur = cables.get(nm)
        if cur and cur["lv"] > lv: continue
        if cur and cur["lv"] == lv and len(cur.get("reason") or "") >= len(reason or ""): continue
        cables[nm] = dict(rec)

def status(nw, outages=None):
    """Per-cable inferred status. outages is accepted for compatibility and is not used to colour cables."""
    n0 = _now()
    cable_news = [it for it in (nw or {}).get("cable") or [] if DAMAGE.search(it["t"]) and CABLE.search(it["t"]) and not NOT_CABLE.search(it["t"])]
    cable_news = _dedupe(sorted(cable_news, key=lambda x: x.get("at") or "", reverse=True))
    cables = {}
    for it in cable_news:
        if _age_h(it.get("at")) > NEWS_DAYS * 24: continue
        lv = _level(it["t"])
        if not lv: continue
        st = "Out of service" if lv == 2 else "Service interruption"
        for nm in _mentions(it["t"]):
            _put(cables, nm, lv, st, it["t"], it.get("src"), it.get("url"), it.get("at"))
    # Documented cuts we already record, only if the cut itself is still within the news window (repaired historic cuts stay green).
    for z in ZONES:
        for c in z["cuts"]:
            try: age_d = (n0 - datetime.fromisoformat(c["d"]).replace(tzinfo=timezone.utc)).days
            except Exception: continue
            if age_d > NEWS_DAYS: continue
            for nm in _mentions(c["t"]):
                _put(cables, nm, 2, "Out of service", c["t"], c.get("src"), c.get("url"), c["d"] + "T12:00:00Z")
    # Unnamed damage in a risk area: cables whose route crosses that area are in jeopardy (yellow), not assumed cut.
    fs = [f for f in (_geo().get("features") or []) if f.get("geometry", {}).get("type") == "LineString"]
    for z in ZONES:
        zn = [it for it in cable_news if re.search(z["kw"], it["t"], re.I) and _age_h(it.get("at")) <= NEWS_DAYS * 24]
        if not zn: continue
        src_it = zn[0]
        for f in fs:
            p = f.get("properties") or {}; nm = _base(p.get("n") or "") or (p.get("n") or "")
            if not nm or nm in cables: continue
            if _line_in_zone(f.get("geometry", {}).get("coordinates") or [], z["poly"]):
                _put(cables, nm, 1, "In jeopardy",
                     f"Cable damage reported in the {z['name']}; this route crosses the area.",
                     src_it.get("src"), src_it.get("url"), src_it.get("at"))
    uniq, seen = [], set()
    for f in fs:
        raw = (f.get("properties") or {}).get("n") or ""
        n = _base(raw) or raw
        key = _norm(n) if n else "id:" + str((f.get("properties") or {}).get("id") or id(f))
        if key in seen: continue
        seen.add(key); uniq.append(n)
    def _st_for(n):
        if not n: return None
        st, nn = None, _norm(n)
        for k, v in cables.items():
            kn = _norm(k)
            if n == k or (nn and kn and (nn == kn or nn.startswith(kn) or kn.startswith(nn))):
                if not st or v["lv"] > st["lv"]: st = v
        return st
    red = sum(1 for n in uniq if (_st_for(n) or {}).get("lv", 0) >= 2)
    yel = sum(1 for n in uniq if (_st_for(n) or {}).get("lv") == 1)
    working = len(uniq) - red - yel
    return dict(generated=_iso(n0), news_ok=(nw or {}).get("ok"), news_at=(nw or {}).get("at"),
                cables=cables, news=cable_news[:8],
                counts=dict(out=red, degraded=yel, working=working, drawn=len(fs), unique=len(uniq)),
                basis="Status is inferred from public fault and repair reports. Cable operators do not publish a live feed. Cables with no fault reports are shown as working.")

def api(swr, outages_fn):
    nw = swr("cables:news", 3600, news, wait=True)
    try: outages_fn()
    except Exception: pass
    return status(nw, None)
