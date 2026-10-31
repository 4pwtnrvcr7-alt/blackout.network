"""SpaceX add-on (tab "🚀 SpaceX", MONITOR group, deep link #spacex). Read-only and informational: never touches scanner.py, scoring,
push.py, jets.py, config.json or blackout.db (scanner alerts are only read, mode=ro). Free, no-key public sources:
  The Space Devs Launch Library 2 (ll.thespacedevs.com, free tier 15 req/h): upcoming + recent SpaceX launches, Starship flights, year count.
      Cached 30-120 min, so this tab makes ~4 LL2 calls per hour at most.
  Spaceflight News API v4 (api.spaceflightnewsapi.net): SpaceX/Starlink/Starship articles, cached 20 min.
  Google News RSS: SpaceX headlines (last 2 days), cached 20 min.
  CelesTrak GP data (celestrak.org): count of Starlink satellites with current orbital elements, cached 12 h.
Cache and last-good payloads live in spacex.db."""
import json, os, re, time, urllib.parse
from datetime import datetime, timezone, timedelta
import importlib, bn_feeds as B
if getattr(B, "_mt", None) != os.path.getmtime(B.__file__): B = importlib.reload(B); B._mt = os.path.getmtime(B.__file__)   # pick up helper edits on hot reload

BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "spacex.db")
STATIC = os.path.join(BASE, "spacex_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
LL = "https://ll.thespacedevs.com/2.2.0/launch"
RX = r"\b(spacex|starlink|starship|starshield|falcon ?9|falcon heavy|dragon capsule|crew dragon|starbase|boca chica)\b"
LINKS = [("SpaceX launches (official)", "https://www.spacex.com/launches/"), ("@SpaceX on X (live webcasts)", "https://x.com/SpaceX"),
         ("SpaceX on YouTube", "https://www.youtube.com/@SpaceX"), ("Starlink status / outages", "https://www.starlink.com/support/status"),
         ("FAA commercial space operations", "https://www.faa.gov/space/stakeholder_engagement/spacex_starship"),
         ("Next Spaceflight schedule", "https://nextspaceflight.com/launches/?search=SpaceX"), ("Launch Library 2 (data source)", "https://thespacedevs.com/llapi")]

def _launch(x):
    r = (x.get("rocket") or {}).get("configuration") or {}; m = x.get("mission") or {}; p = x.get("pad") or {}; st = x.get("status") or {}
    return {"id": x.get("id"), "name": x.get("name"), "net": x.get("net"), "win_start": x.get("window_start"), "win_end": x.get("window_end"),
            "precision": ((x.get("net_precision") or {}).get("name")), "status": st.get("abbrev"), "status_long": st.get("name"), "status_desc": st.get("description"),
            "prob": x.get("probability"), "weather": x.get("weather_concerns"), "hold": x.get("holdreason"), "fail": x.get("failreason"),
            "rocket": r.get("full_name") or r.get("name"), "mission": m.get("name"), "mission_type": m.get("type"), "orbit": (m.get("orbit") or {}).get("abbrev"),
            "desc": (m.get("description") or "")[:400], "pad": p.get("name"), "site": (p.get("location") or {}).get("name"),
            "lat": p.get("latitude"), "lon": p.get("longitude"), "map": p.get("map_url"), "webcast_live": x.get("webcast_live"), "image": x.get("image"),
            "url": "https://ll.thespacedevs.com/2.2.0/launch/" + (x.get("id") or "") + "/", "slug": x.get("slug"),
            "year_n": x.get("agency_launch_attempt_count_year"), "total_n": x.get("agency_launch_attempt_count")}

def upcoming(force=False):
    def f():
        j = B.getjson(f"{LL}/upcoming/?" + urllib.parse.urlencode({"lsp__name": "SpaceX", "limit": 14, "mode": "normal", "hide_recent_previous": "true"}))
        return {"fetched": B.iso(), "count": j.get("count"), "items": [_launch(x) for x in j.get("results") or []]}
    return B.cached(DB, "upcoming", 1800, f, force)

def previous(force=False):
    def f():
        y0 = f"{datetime.now(timezone.utc).year}-01-01T00:00:00Z"
        j = B.getjson(f"{LL}/previous/?" + urllib.parse.urlencode({"lsp__name": "SpaceX", "limit": 12, "mode": "normal", "net__gte": y0}))
        return {"fetched": B.iso(), "year_count": j.get("count"), "year": y0[:4], "items": [_launch(x) for x in j.get("results") or []]}
    return B.cached(DB, "previous", 3600, f, force)

def starship(force=False):
    def f():
        up = B.getjson(f"{LL}/upcoming/?" + urllib.parse.urlencode({"lsp__name": "SpaceX", "search": "Starship", "limit": 3, "mode": "normal"}))
        pr = B.getjson(f"{LL}/previous/?" + urllib.parse.urlencode({"lsp__name": "SpaceX", "search": "Starship", "limit": 5, "mode": "normal"}))
        return {"fetched": B.iso(), "upcoming": [_launch(x) for x in up.get("results") or []], "previous": [_launch(x) for x in pr.get("results") or []], "total_flights": pr.get("count")}
    return B.cached(DB, "starship", 7200, f, force)

def starlink(force=False):
    def f():
        t = B.http("https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv", timeout=40, accept="text/csv").decode("utf-8", "replace").splitlines()
        rows = [l for l in t[1:] if l.startswith("STARLINK")]
        if len(rows) < 1000: raise RuntimeError(f"CelesTrak returned only {len(rows)} rows")
        y = datetime.now(timezone.utc).year; this_year = sum(1 for l in rows if (l.split(",")[1] or "").startswith(str(y)))
        return {"fetched": B.iso(), "tracked": len(rows), "launched_this_year": this_year, "year": y, "src": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv"}
    return B.cached(DB, "starlink", 12 * 3600, f, force)

def news(force=False):
    def f():
        a = B.getjson("https://api.spaceflightnewsapi.net/v4/articles/?" + urllib.parse.urlencode({"search": "SpaceX", "limit": 15, "ordering": "-published_at"}))
        items = [{"title": x.get("title"), "url": x.get("url"), "source": x.get("news_site"), "time": x.get("published_at"), "summary": (x.get("summary") or "")[:280], "via": "Spaceflight News API"}
                 for x in a.get("results") or []]
        try: items += [dict(x, via="Google News") for x in B.gnews("SpaceX OR Starlink OR Starship when:2d", 30)]
        except Exception: pass
        items.sort(key=lambda x: x.get("time") or "", reverse=True)
        return {"fetched": B.iso(), "items": B.dedupe(items)[:40]}
    return B.cached(DB, "news", 1200, f, force)

_force = {"t": 0}
def summary(force=False):
    up = upcoming(force); pv = previous(); ss = starship(); sl = starlink(); nw = news(force)
    nxt = None
    for x in (up or {}).get("items") or []:
        if x.get("status") not in ("Success", "Failure", "Partial Failure"): nxt = x; break
    return 200, {"updated": B.iso(), "next": nxt, "upcoming": up, "previous": pv, "starship": ss, "starlink": sl, "news": nw,
                 "alerts": B.scanner_mentions(RX, days=14, limit=25), "links": LINKS, "errors": B.errors(DB),
                 "note": "Launch times are NET (no earlier than) and change often; times shown in ET. Data: The Space Devs Launch Library 2, Spaceflight News API, Google News, CelesTrak. Informational only — this tab does not feed The Wire's scoring."}

def handle_get(path, qs):
    n = path[len("/api/spacex/"):] if path.startswith("/api/spacex/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/spacex":
        force = (qs.get("force") or [""])[0] == "1" and time.time() - _force["t"] > 120
        if force: _force["t"] = time.time()
        return summary(force)
    return 404, {"error": "not found"}
