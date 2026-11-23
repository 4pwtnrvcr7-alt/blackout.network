"""Undersea cables for the /network map (pt1785u, Stage 2).

Geometry: netmap_static/cables.json, built by tools/build_cables.py from OpenStreetMap (ODbL) and NOAA Office for Coastal
Management (U.S. waters, public domain). TeleGeography's free map data is CC BY-NC-SA (non-commercial), so it is not used.

Status is INFERRED, never official: no cable operator publishes a live status feed. We combine
  - news headlines that name a cable or a chokepoint together with damage words (Google News RSS, 2 queries / 30 min),
  - IODA internet outage signals (Georgia Tech) in the countries around each chokepoint, from the map's own data build.
Risk score per chokepoint (0-100, our model, shown with its parts): chokepoint base 20 + documented cuts in the last
36 months (15 each, max 30) + conflict/security headlines in the last 7 days (5 each, max 25) + cable-damage news in the
last 14 days (25).
"""
import json, os, re, time, urllib.parse
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import email.utils

BASE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(BASE, "netmap_static", "cables.json")
NEWS_DAYS, CONFLICT_DAYS, HIST_MONTHS = 14, 7, 36

# Chokepoints (approximate outlines, drawn by us). Cut history: documented incidents with a public source.
ZONES = [
    dict(id="redsea", name="Red Sea and Bab el-Mandeb", cc=["YE", "DJ", "ER", "SA", "EG", "SD"],
         poly=[[32.55, 29.95], [32.7, 28.5], [33.6, 27.0], [34.3, 25.8], [35.2, 24.0], [35.8, 22.8], [36.9, 21.5], [37.3, 19.5], [38.5, 18.0], [39.6, 16.0], [40.8, 14.8], [42.5, 13.0], [43.2, 11.9], [43.7, 12.3], [43.4, 12.9], [42.8, 14.5], [42.6, 15.5], [41.8, 17.0], [40.6, 19.0], [39.2, 21.4], [38.4, 23.5], [37.2, 25.0], [36.0, 26.8], [35.0, 28.0], [33.6, 28.0], [32.8, 29.6]],
         q='"Red Sea" (Houthi OR missile OR drone OR attack OR warship OR navy)', kw=r"red sea|bab[- ]el[- ]mandeb|jeddah|yemen|djibouti|houthi",
         cuts=[dict(d="2024-02-24", t="Seacom, AAE-1 and EIG cut in the southern Red Sea; the leading explanation is the dragging anchor of the Rubymar after a Houthi missile strike",
                    src="Kentik", url="https://www.kentik.com/blog/what-caused-the-red-sea-submarine-cable-cuts/"),
               dict(d="2025-09-06", t="SMW4 and IMEWE cut near Jeddah; Microsoft Azure reported higher latency on Middle East routes",
                    src="Reuters", url="https://www.reuters.com/world/middle-east/red-sea-cable-cuts-disrupt-internet-across-asia-middle-east-2025-09-07/")],
         note="About 15 cables pass through Bab el-Mandeb (International Cable Protection Committee, via AP).",
         note_url="https://apnews.com/article/red-sea-undersea-cables-cut-internet-disruption-0b08fc5f02daf72710e0010c11ea21ae"),
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
DAMAGE = re.compile(r"\b(cut|cuts|severed|damag\w*|fault\w*|outage|break|broken|rupture\w*|disrupt\w*)\b", re.I)
CABLE = re.compile(r"\b(undersea|subsea|submarine|sea|seabed|fib(?:re|er)[- ]optic|internet|telecom\w*|data|communications?)\s+cables?\b|\bcables?\s+(?:cut|damage)", re.I)
CONFLICT = re.compile(r"\b(attack\w*|strik\w*|missile\w*|drone\w*|sabotage\w*|seiz\w*|fired|hit|hits|clash\w*|incursion\w*|warship\w*|drills?|blockade\w*|shadow fleet|detain\w*|boarded)\b", re.I)
_LAST = {}
NOT_CABLE = re.compile(r"\b(power cable|electricity cable|gas pipeline|pipeline)\b", re.I)

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
    try: res["cable"] = _rss(CABLE_Q, NEWS_DAYS); ok += 1
    except Exception: pass
    for z in ZONES:
        try: res["conflict"][z["id"]] = _LAST[z["id"]] = [it for it in _rss(z["q"], CONFLICT_DAYS) if CONFLICT.search(it["t"])]; ok += 1
        except Exception: res["conflict"][z["id"]] = _LAST.get(z["id"])   # keep the last good list rather than dropping the score
    if not ok: raise RuntimeError("news search unavailable")
    res["ok"] = ok == 1 + len(ZONES); res["at"] = _iso(_now())
    return res

_NAMES = None
def cable_names():
    global _NAMES
    if _NAMES is None:
        try:
            fs = json.load(open(GEO)).get("features") or []
            nm = {f["properties"]["n"] for f in fs if f["geometry"]["type"] == "LineString" and f["properties"].get("n")}
            _NAMES = sorted({re.sub(r"\s*(cable system|submarine cable system|cable|system|seg(?:ment)?\.?\s*[\w.]+)\s*$", "", n, flags=re.I).strip() for n in nm} - {""}, key=len, reverse=True)
        except Exception: _NAMES = []
    return _NAMES

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

def status(nw, outages=None):
    """Zones with inferred status + risk score, and cable names that recent damage news mentions."""
    n0 = _now(); cable_news = [it for it in (nw or {}).get("cable") or [] if DAMAGE.search(it["t"]) and CABLE.search(it["t"]) and not NOT_CABLE.search(it["t"])]
    cable_news = _dedupe(sorted(cable_news, key=lambda x: x.get("at") or "", reverse=True))
    ioda = {c["cc"]: c for c in ((outages or {}).get("countries") or []) if c.get("cur")}
    names = cable_names(); hit_names = {}
    for it in cable_news:
        if _age_h(it.get("at")) > NEWS_DAYS * 24: continue
        for nm in names:
            if len(nm) >= 4 and re.search(r"(?<![\w-])" + re.escape(nm) + r"(?![\w-])", it["t"], re.I):
                hit_names.setdefault(nm, it)
    zones = []
    for z in ZONES:
        zn = [it for it in cable_news if re.search(z["kw"], it["t"], re.I) and _age_h(it.get("at")) <= NEWS_DAYS * 24]
        cf_raw = ((nw or {}).get("conflict") or {}).get(z["id"])
        cf = _dedupe([it for it in (cf_raw or []) if _age_h(it.get("at")) <= CONFLICT_DAYS * 24])
        hist = [c for c in z["cuts"] if datetime.fromisoformat(c["d"]).replace(tzinfo=timezone.utc) >= n0 - timedelta(days=HIST_MONTHS * 30.4)]
        parts = [("Chokepoint", 20), (f"Documented cuts, last {HIST_MONTHS} months ({len(hist)})", min(30, 15 * len(hist))),
                 (f"Conflict and security headlines, last {CONFLICT_DAYS} days ({len(cf)})" if cf_raw is not None else "Conflict headlines (search unavailable)", min(25, 5 * len(cf))),
                 (f"Cable damage in the news, last {NEWS_DAYS} days", 25 if zn else 0)]
        score = min(100, sum(p[1] for p in parts))
        io = [dict(cc=c, name=ioda[c]["name"], url=ioda[c].get("ioda")) for c in z["cc"] if c in ioda]
        if zn and io: st, lv = "Likely damage (inferred)", 2
        elif zn: st, lv = "Possible damage (inferred)", 1
        else: st, lv = "No damage reported (inferred)", 0
        zones.append(dict(id=z["id"], name=z["name"], poly=z["poly"], score=score, parts=parts, status=st, lv=lv, ioda=io,
                          news=zn[:5], conflict=cf[:5], cuts=sorted(z["cuts"], key=lambda c: c["d"], reverse=True), note=z.get("note"), note_url=z.get("note_url")))
    return dict(generated=_iso(n0), zones=zones, news_ok=(nw or {}).get("ok"), news_at=(nw or {}).get("at"),
                damaged={k: dict(t=v["t"], url=v["url"], src=v["src"], at=v["at"]) for k, v in hit_names.items()},
                news=cable_news[:8],
                basis="Inferred from news headlines and IODA internet outage signals. No cable operator publishes a live status feed.",
                model="Risk score (our model): chokepoint 20 + documented cuts 15 each (max 30) + conflict headlines 5 each (max 25) + cable damage news 25.")

def api(swr, outages_fn):
    nw = swr("cables:news", 1800, news, wait=True)
    try: out = outages_fn()
    except Exception: out = None
    return status(nw, out)
