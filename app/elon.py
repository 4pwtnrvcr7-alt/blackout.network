"""Elon Musk add-on (tab "👤 Elon Musk", MONITOR group, deep link #elon). Read-only and informational: never touches scanner.py,
scoring, push.py, jets.py, config.json or blackout.db (scanner alerts are only read, mode=ro). Free, no-key public sources:
  Google News RSS (headlines about Musk, last 2 days; sorted into company/topic buckets by keywords), cached 15 min.
  Forbes Real-Time Billionaires JSON (rank and estimated net worth), cached 30 min; one value per day is archived in elon.db.
  Yahoo Finance (TSLA quote, shared with the Finance tab's 3-min cache in finance.py).
  Polymarket Gamma API (open markets tagged elon-musk, read-only prices), cached 15 min.
  adsb.lol / adsb.fi public ADS-B API (the three Musk-linked Gulfstreams already on aviation_watchlist.json), cached 5 min.
  X (Twitter) posts: no free keyless API, so the tab links to x.com/elonmusk (link only).
Observed data only; where/why a jet flies and who is aboard is never inferred here."""
import json, os, re, sqlite3, time, urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import importlib, bn_feeds as B
if getattr(B, "_mt", None) != os.path.getmtime(B.__file__): B = importlib.reload(B); B._mt = os.path.getmtime(B.__file__)   # pick up helper edits on hot reload

BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "elon.db")
STATIC = os.path.join(BASE, "elon_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
ET = ZoneInfo("America/New_York")
RX = r"\b(elon|musk|tesla|xai|neuralink|boring company|doge)\b"
JETS = [("a835af", "N628TS", "Gulfstream G650ER N628TS (Falcon Landing LLC)"), ("a2ae0a", "N272BG", "Gulfstream N272BG (Falcon Landing LLC)"),
        ("a64304", "N502SX", "Gulfstream N502SX (Falcon Landing LLC)")]
BUCKETS = [("Tesla", r"\b(tesla|cybertruck|robotaxi|optimus|fsd|model [3sxy]|gigafactory|tsla)\b"),
           ("SpaceX & Starlink", r"\b(spacex|starlink|starship|falcon|starshield|mars)\b"),
           ("xAI & Grok", r"\b(xai|x\.ai|grok|colossus)\b"),
           ("X (Twitter)", r"\b(twitter|x corp|on x\b|x platform|x's|tweet)"),
           ("Neuralink & Boring", r"\b(neuralink|boring company|hyperloop)\b"),
           ("Politics & government", r"\b(trump|doge|white house|election|midterm|congress|senate|government|party|policy|regulat\w*|lawsuit|court|sec\b|tariff)"),
           ("Money & pay", r"\b(net worth|pay package|compensation|billion|trillion|shares|stock|ipo|valuation|wealth)\b")]
LINKS = [("@elonmusk on X (link only — no free API)", "https://x.com/elonmusk"), ("Forbes real-time profile", "https://www.forbes.com/profile/elon-musk/"),
         ("Tesla investor relations", "https://ir.tesla.com/"), ("SpaceX updates", "https://www.spacex.com/updates/"), ("xAI news", "https://x.ai/news"),
         ("Neuralink blog", "https://neuralink.com/blog/"), ("Bloomberg Billionaires Index", "https://www.bloomberg.com/billionaires/")]

def _db():
    c = sqlite3.connect(DB, timeout=15); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS networth(day TEXT PRIMARY KEY, usd_b REAL, rank INTEGER, fetched TEXT)"); return c

def news(force=False):
    def f():
        items = [dict(x, via="Google News") for x in B.gnews('"Elon Musk" when:2d', 60)]
        items.sort(key=lambda x: x.get("time") or "", reverse=True); items = B.dedupe(items)[:50]
        for x in items:
            t = (x["title"] or "").lower(); x["topics"] = [n for n, rx in BUCKETS if re.search(rx, t)] or ["Other"]
        return {"fetched": B.iso(), "items": items}
    return B.cached(DB, "news", 900, f, force)

def networth(force=False):
    def f():
        j = B.getjson("https://www.forbes.com/forbesapi/person/rtb/0/position/true.json?" + urllib.parse.urlencode({"fields": "rank,uri,personName,finalWorth", "limit": 10}))
        lst = (j.get("personList") or {}).get("personsLists") or []
        me = next((p for p in lst if p.get("uri") == "elon-musk"), None)
        if not me: raise RuntimeError("Musk not in Forbes top 10 response")
        top = [{"rank": p.get("rank"), "name": p.get("personName"), "usd_b": round((p.get("finalWorth") or 0) / 1000, 1)} for p in lst[:5]]
        return {"fetched": B.iso(), "usd_b": round(me["finalWorth"] / 1000, 1), "rank": me.get("rank"), "top": top, "src": "https://www.forbes.com/real-time-billionaires/"}
    v = B.cached(DB, "networth", 1800, f, force)
    if v and not v.get("stale") and not os.environ.get("BN_WEB_ONLY"):
        try: c = _db(); c.execute("INSERT OR REPLACE INTO networth VALUES(?,?,?,?)", (datetime.now(ET).strftime("%Y-%m-%d"), v["usd_b"], v["rank"], v["fetched"])); c.commit(); c.close()
        except Exception: pass
    try: c = _db(); hist = [dict(r) for r in c.execute("SELECT day, usd_b, rank FROM networth ORDER BY day DESC LIMIT 120")]; c.close()
    except Exception: hist = []
    return (dict(v, history=hist[::-1]) if v else None)

def markets(force=False):
    def f():
        j = B.getjson("https://gamma-api.polymarket.com/events?" + urllib.parse.urlencode({"tag_slug": "elon-musk", "closed": "false", "limit": 40, "order": "volume24hr", "ascending": "false"}))
        out = []
        for e in [e for e in j if not re.search(r"assassinat|\bdie\b|\bdies\b|death|killed|shot\b", e.get("title") or "", re.I)][:12]:
            mk = []
            for m in e.get("markets") or []:
                if m.get("closed"): continue
                try: p = float(json.loads(m.get("outcomePrices") or "[]")[0])
                except Exception: continue
                mk.append({"q": m.get("groupItemTitle") or m.get("question"), "yes": p})
            mk.sort(key=lambda x: -x["yes"])
            out.append({"title": e.get("title"), "url": "https://polymarket.com/event/" + (e.get("slug") or ""), "vol24": e.get("volume24hr"), "end": e.get("endDate"), "top": mk[:3]})
        return {"fetched": B.iso(), "items": out, "src": "https://polymarket.com/"}
    return B.cached(DB, "markets", 900, f, force)

def jets(force=False):
    def f():
        hexes = ",".join(h for h, _, _ in JETS); last = None
        for url in (f"https://api.adsb.lol/v2/icao/{hexes}", f"https://opendata.adsb.fi/api/v2/icao/{hexes}"):
            try: j = B.getjson(url, 20); src = urllib.parse.urlsplit(url).netloc; break
            except Exception as ex: last = ex
        else: raise last
        seen = {a.get("hex"): a for a in j.get("ac") or []}; out = []
        for h, reg, lab in JETS:
            a = seen.get(h)
            out.append({"hex": h, "reg": reg, "label": lab, "airborne": bool(a and a.get("alt_baro") not in (None, "ground")), "seen": bool(a),
                        "alt": a.get("alt_baro") if a else None, "gs": a.get("gs") if a else None, "lat": a.get("lat") if a else None, "lon": a.get("lon") if a else None,
                        "track": a.get("track") if a else None, "callsign": (a.get("flight") or "").strip() if a else None,
                        "map": "https://globe.adsb.lol/?icao=" + h})
        return {"fetched": B.iso(), "src": src, "items": out}
    return B.cached(DB, "jets", 300, f, force)

def tsla():
    try:
        import finance
        q = (finance.quotes() or {}).get("q") or {}; x = dict(q.get("TSLA") or {}); x.pop("period", None)
        return dict(x, sym="TSLA", label="Tesla") if x else None
    except Exception: return None

_force = {"t": 0}
def summary(force=False):
    return 200, {"updated": B.iso(), "networth": networth(force), "tsla": tsla(), "news": news(force), "markets": markets(), "jets": jets(force),
                 "alerts": B.scanner_mentions(RX, days=14, limit=25), "links": LINKS, "buckets": [b[0] for b in BUCKETS] + ["Other"], "errors": B.errors(DB),
                 "note": "Headlines are shown verbatim from their publishers (via Google News) and sorted into topics by keywords only — no opinions are added. Net worth is Forbes' real-time estimate. Jet positions are observed ADS-B data; who is aboard is never known. Informational only — this tab does not feed The Wire's scoring."}

def handle_get(path, qs):
    n = path[len("/api/elon/"):] if path.startswith("/api/elon/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/elon":
        force = (qs.get("force") or [""])[0] == "1" and time.time() - _force["t"] > 120
        if force: _force["t"] = time.time()
        return summary(force)
    return 404, {"error": "not found"}
