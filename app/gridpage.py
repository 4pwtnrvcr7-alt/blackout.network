"""/grid: The Grid, full-screen U.S. power grid page (Matt pt1737u, Nov 21 2026).
Replaces the menu link to the old /live#grid dashboard tab. Read-only: it re-serves what gridstatus.py (gridstatus.db, synced copy)
and gridwatch.py (/api/grid) already publish. It never collects, scores or geocodes anything, and never touches scanner.py, scoring,
push.py, jets.py, aviation_watch.py, config.json, the newsletter or geo code.
Routes: /grid (page), /api/gridpage/data (one compact JSON for the map + sections), /api/gridpage/<static file>."""
import os, json, time, threading, html as _html

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "gridpage_static")
FILES = {"grid.js": "application/javascript", "grid.css": "text/css"}
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)

# Label points for the grid-operator sections (sections.geojson polygons are irregular; these sit inside each one).
SEC_PT = {"CAISO": (-119.6, 37.0), "ERCOT": (-98.9, 31.3), "ISO-NE": (-71.9, 43.7), "NYISO": (-75.2, 42.9), "PJM": (-78.6, 39.9),
          "MISO": (-90.6, 41.0), "SPP": (-99.3, 37.6), "SE": (-84.4, 32.9), "WEST": (-113.6, 41.6), "AK": (-150.0, 63.6), "HI": (-157.4, 20.8)}
# Approximate geographic centres of the states (for state-level outage dots; ODIN reports by utility, mapped to states by gridstatus.py).
ST_PT = {"AL": (-86.8, 32.8), "AK": (-152.0, 64.2), "AZ": (-111.7, 34.3), "AR": (-92.4, 34.9), "CA": (-119.4, 36.8), "CO": (-105.5, 39.0),
         "CT": (-72.7, 41.6), "DE": (-75.5, 39.0), "DC": (-77.03, 38.9), "FL": (-81.7, 28.1), "GA": (-83.4, 32.7), "HI": (-155.6, 19.7),
         "ID": (-114.6, 44.4), "IL": (-89.2, 40.0), "IN": (-86.3, 39.9), "IA": (-93.5, 42.1), "KS": (-98.4, 38.5), "KY": (-85.3, 37.5),
         "LA": (-92.0, 31.0), "ME": (-69.2, 45.4), "MD": (-76.8, 39.0), "MA": (-71.8, 42.3), "MI": (-84.7, 43.6), "MN": (-94.3, 46.3),
         "MS": (-89.7, 32.7), "MO": (-92.5, 38.4), "MT": (-109.6, 47.0), "NE": (-99.8, 41.5), "NV": (-116.6, 39.3), "NH": (-71.6, 43.7),
         "NJ": (-74.6, 40.1), "NM": (-106.1, 34.4), "NY": (-75.5, 42.9), "NC": (-79.4, 35.6), "ND": (-100.5, 47.5), "OH": (-82.8, 40.3),
         "OK": (-97.5, 35.6), "OR": (-120.6, 43.9), "PA": (-77.8, 40.9), "RI": (-71.5, 41.7), "SC": (-80.9, 33.9), "SD": (-100.2, 44.4),
         "TN": (-86.4, 35.9), "TX": (-99.3, 31.5), "UT": (-111.7, 39.3), "VT": (-72.7, 44.0), "VA": (-78.8, 37.5), "WA": (-120.5, 47.4),
         "WV": (-80.6, 38.6), "WI": (-89.9, 44.6), "WY": (-107.6, 43.0), "PR": (-66.5, 18.2)}

_C = {"t": 0.0, "v": None}
_L = threading.Lock()

def _v(name):
    try: return str(int(os.path.getmtime(os.path.join(STATIC, name))))
    except OSError: return "0"

def data():
    """One compact payload for /grid, cached 60 s. Everything comes from gridstatus.db (read-only) as gridstatus.py stored it."""
    with _L:
        if _C["v"] is not None and time.time() - _C["t"] < 60: return _C["v"]
    import gridstatus as G
    code, s = G.summary({})
    body = {"generated": s.get("generated"), "freshness": s.get("freshness") or {}, "swpc": s.get("swpc"), "sources": s.get("sources") or [],
            "last_cycle": s.get("last_cycle"), "regions": [], "states": [], "weather": [], "shelters": [], "ok": bool(s.get("sections"))}
    for k, sec in (s.get("sections") or {}).items():
        p = SEC_PT.get(k)
        r = {x: sec.get(x) for x in ("id", "name", "states", "site", "status", "reasons", "demand_mw", "forecast_mw", "yesterday_mw",
                                     "vs_forecast_pct", "vs_yesterday_pct", "eia_hour", "eia_age_h", "odin", "nws", "scanner", "no_eia")}
        r["series"] = [[t, d] for t, d, *_ in (sec.get("series") or [])][-36:]
        if p: r["lon"], r["lat"] = p
        body["regions"].append(r)
    obs = nws = sh = None
    try:
        c = G.gdb(ro=True)
        try:
            obs, _ = G.sget(c, "odin_by_state", {}); nws, _ = G.sget(c, "nws", []); sh, _ = G.sget(c, "shelters", [])
        finally: c.close()
    except Exception:
        pass
    nws_by = {}
    for a in nws or []:
        if not a.get("power"): continue
        for st in a.get("states") or []:
            nws_by.setdefault(st, []).append({"event": a.get("event"), "severity": a.get("severity"), "headline": a.get("headline"), "url": a.get("url"), "expires": a.get("expires")})
    for st, us in (obs or {}).items():
        if st not in ST_PT: continue
        n = sum(int(u.get("outages") or 0) for u in us)
        top = [{"name": u.get("name"), "outages": u.get("outages"), "web": u.get("web")} for u in us if u.get("outages")][:5]
        body["states"].append({"st": st, "name": G.STATES.get(st, st), "section": G.STATE_SEC.get(st), "outages": n, "utilities": len(us),
                               "reporting": sum(1 for u in us if u.get("outages")), "top": top, "nws": nws_by.get(st, [])[:6],
                               "received": max((u.get("received") or "" for u in us), default="") or None,
                               "lon": ST_PT[st][0], "lat": ST_PT[st][1]})
    for w in s.get("weather") or []:
        body["weather"].append({k: w.get(k) for k in ("cluster_id", "title", "location", "lat", "lon", "rank", "first_seen", "updated", "unconfirmed",
                                                       "us", "section", "own_impacts", "resources")}
                               | {"links": (w.get("links") or [])[:3], "power": [i for c in (w.get("checks") or []) if c.get("key") == "power" for i in (c.get("items") or [])][:4]})
    for x in sh or []:
        if x.get("lat") is None: continue
        body["shelters"].append({k: x.get(k) for k in ("name", "city", "state", "status", "population", "capacity", "lat", "lon")})
    with _L: _C.update(t=time.time(), v=body)
    return body

LOADER = ('<div class="gx-ld" id="gx_ld" role="status" aria-label="Loading the grid">'
  '<svg class="gx-ldsvg" viewBox="0 0 320 200" aria-hidden="true" focusable="false">'
  '<g class="gx-lines">'
  '<path id="gxl1" d="M10 40 C 70 40, 90 70, 130 70 L 160 70"/><path id="gxl2" d="M10 160 C 70 160, 90 130, 130 130 L 160 130"/>'
  '<path id="gxl3" d="M10 100 L 160 100"/>'
  '<path d="M160 70 L 220 70 L 280 70 M160 100 L 220 100 L 280 100 M160 130 L 220 130 L 280 130 M160 70 L 160 130 M220 70 L 220 130 M280 70 L 280 130"/>'
  '</g>'
  '<g class="gx-flow"><path d="M10 40 C 70 40, 90 70, 130 70 L 160 70"/><path d="M10 160 C 70 160, 90 130, 130 130 L 160 130"/><path d="M10 100 L 160 100"/></g>'
  '<g class="gx-tow"><path d="M10 26 v28 M4 34 h12 M6 30 l4 -4 l4 4"/><path d="M10 86 v28 M4 94 h12 M6 90 l4 -4 l4 4"/><path d="M10 146 v28 M4 154 h12 M6 150 l4 -4 l4 4"/></g>'
  '<g class="gx-nodes">' + "".join(f'<circle cx="{x}" cy="{y}" r="5" style="--d:{i * 0.09:.2f}s"/>' for i, (x, y) in enumerate(
      [(160, 70), (160, 100), (160, 130), (220, 70), (220, 100), (220, 130), (280, 70), (280, 100), (280, 130)])) + '</g>'
  '</svg>'
  '<p class="gx-ldk"><span>Energizing the grid</span><b id="gx_ldn">00%</b></p>'
  '<ol class="gx-lds" aria-hidden="true"><li data-s="map">Map</li><li data-s="data">Operators</li><li data-s="pts">Outages</li></ol>'
  '<p class="gx-ldmsg" id="gx_ldmsg" hidden></p></div>')

def page(qs=None):
    try:
        import sitenav, sitenav_ui
        top = sitenav.header_html("grid"); theme = sitenav_ui.THEME_SCRIPT
    except Exception:
        top = '<header class="bn-top"><div class="bn-tbar"><a class="bn-logo" href="/"><span class="bnt-wm">blackout.network</span></a></div></header>'; theme = ""
    try:
        import signal_map
        mlv = signal_map._v("maplibre-gl.js"); mlc = signal_map._v("maplibre-gl.css")
    except Exception:
        mlv = mlc = "0"
    title = "The Grid: power grid status | BLACKOUT.NETWORK"
    desc = "Full-screen map of the power grid: U.S. and international grid operators colored by status, outages by state, worldwide blackout alerts, weather threats, demand and space weather."
    sec = lambda sid, h, sub: (f'<details class="gx-sec" id="{sid}"><summary><span><b>{E(h)}</b><small>{E(sub)}</small></span><i aria-hidden="true"></i></summary>'
                               f'<div class="gx-body" data-sec="{sid}"><p class="gx-empty">Loading…</p></div></details>')
    return f'''<!doctype html><html lang="en" class="gx-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{theme}
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="https://blackout.network/grid">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="https://blackout.network/grid"><meta property="og:type" content="website"><meta property="og:image" content="https://blackout.network/img/share-logo-1200.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="1200"><meta name="twitter:card" content="summary"><meta name="twitter:image" content="https://blackout.network/img/share-logo-1200.png">
<meta name="theme-color" content="#05060a">
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={mlc}"><link rel="stylesheet" href="/api/gridpage/grid.css?v={_v("grid.css")}">
<script src="/sitenav.js" defer></script>
</head><body class="gx">
<a class="skip" href="#gx_more">Skip to grid details</a>
<div class="gx-head">{top}</div>
<script>(function(){{var m=document.getElementById("bn-menu");if(m&&m.parentNode!==document.body)document.body.appendChild(m)}})()</script>
<main id="gx_main" data-bnt-skip>
<h1 class="gx-vh">The Grid: U.S. power grid status</h1>
<div id="gx_map" class="gx-map" role="region" aria-label="Map of the U.S. power grid. Drag to pan, pinch or scroll to zoom, hover or tap a point for details."></div>
{LOADER}
<div class="gx-top"><div class="gx-chip" id="gx_chip"><i></i><span id="gx_sum" aria-live="polite">Loading grid status…</span></div></div>
<div class="gx-reg" id="gx_reg" role="group" aria-label="Region"><button type="button" data-r="us" aria-pressed="true">U.S.</button><button type="button" data-r="eu" aria-pressed="false">Europe</button><button type="button" data-r="apac" aria-pressed="false">Asia-Pacific</button><button type="button" data-r="world" aria-pressed="false">World</button></div>
<div class="gx-ctl"><button type="button" class="gx-b" id="gx_zin" aria-label="Zoom in"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v12M6 12h12"/></svg></button>
<button type="button" class="gx-b" id="gx_zout" aria-label="Zoom out"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg></button>
<button type="button" class="gx-b" id="gx_home" aria-label="Show the whole U.S."><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button></div>
<div class="gx-leg" id="gx_leg" aria-label="Legend">
<p class="gx-k">Status</p>
<ul><li><i class="s-ok"></i>Operational</li><li><i class="s-strain"></i>Strained</li><li><i class="s-out"></i>Outage</li><li><i class="s-na"></i>No data</li></ul>
<p class="gx-k">Points</p>
<ul class="gx-shapes"><li><i class="sh-ring"></i>Grid operator</li><li><i class="sh-dot"></i>State outages</li><li><i class="sh-dia"></i>Weather or grid alert</li></ul></div>
<button type="button" class="gx-more-btn" id="gx_more_btn" aria-controls="gx_more" aria-expanded="false"><span>More about the grid</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg></button>
<aside class="gx-card" id="gx_card" hidden aria-live="polite"></aside>
<section class="gx-more" id="gx_more" aria-label="More about the grid" hidden>
<div class="gx-grab" aria-hidden="true"></div>
<div class="gx-mh"><div><p class="gx-k">The Grid</p><h2>More about the grid</h2></div><button type="button" class="gx-x" id="gx_more_x" aria-label="Close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
<div class="gx-scroll" id="gx_scroll">
<div class="gx-kpis" id="gx_kpis"></div>
{sec("gx-regions", "Grid operators", "Status, demand and the last 36 hours for each operator region")}
{sec("gx-world", "Worldwide", "Operators outside the U.S., internet outages, and grid or blackout alerts on the Wire")}
{sec("gx-outages", "Outages by state", "Utility outage counts reported to DOE / ORNL ODIN")}
{sec("gx-weather", "Weather threats to power", "Ranked weather alerts with grid and infrastructure checks")}
{sec("gx-threats", "Grid threats", "Physical, cyber and reliability threats to U.S. power")}
{sec("gx-space", "Space weather", "NOAA geomagnetic storm scale and 3-day outlook")}
{sec("gx-local", "Your state", "Utilities, outage maps, alerts and open shelters")}
{sec("gx-sources", "Sources and data age", "Where every number on this page comes from")}
</div></section>
<noscript><p class="gx-nojs">The Grid map needs JavaScript. <a href="/api/gridstatus">Raw grid status (JSON)</a></p></noscript>
</main>
<script src="/api/signal/maplibre-gl.js?v={mlv}" defer></script><script src="/api/gridpage/grid.js?v={_v("grid.js")}" defer></script>
</body></html>'''

def handle_get(path, qs):
    if path in ("/grid", "/grid/"):
        return 200, page(qs or {}), "text/html"
    if path == "/api/gridpage/data":
        try: return 200, data()
        except Exception as ex: return 503, {"error": "grid data unavailable", "detail": type(ex).__name__}
    if path == "/api/gridpage/world":
        try: return 200, world()
        except Exception as ex: return 503, {"error": "world grid data unavailable", "detail": type(ex).__name__}
    if path.startswith("/api/gridpage/"):
        n = path[len("/api/gridpage/"):]
        if n not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    return 404, {"error": "not found"}

# ---------------------------------------------------------------- worldwide (Matt pt1739u, Nov 21 2026 7:36 PM ET)
# Keyless public feeds only, fetched on this node and cached (TTL below); one refresh at a time, never per request.
# Operators without a usable free feed are listed as "no live data" (grey) with the reason; nothing is estimated.
import re as _re, urllib.request as _ur
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
_UA = "Mozilla/5.0 (compatible; blackout.network grid page; +https://blackout.network/grid)"
WORLD_TTL = 300          # live operator feeds: 5 min
_W = {"t": 0.0, "v": None}
_WL = threading.Lock()

def _get(url, timeout=8, limit=3_000_000):
    with _ur.urlopen(_ur.Request(url, headers={"User-Agent": _UA, "Accept": "application/json,text/xml,*/*"}), timeout=timeout) as r:
        return r.read(limit)

def _iso(d): return d.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _age_h(ts):
    try: return (_dt.now(_tz.utc) - _dt.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception: return None

def _gb():
    d = json.loads(_get("https://data.elexon.co.uk/bmrs/api/v1/demand/outturn/summary?resolution=minute"))
    last = d[-1] if d else None
    out = {"demand_mw": round(last["demand"]) if last else None, "data_time": last and last.get("startTime")}
    day = [x for x in d if _age_h(x.get("startTime") or "") is not None and 23.5 <= _age_h(x["startTime"]) <= 24.5]
    if last and day: y = day[len(day) // 2]["demand"]; out["vs_yesterday_pct"] = round((last["demand"] - y) / y * 100, 1) if y else None
    out["series"] = [[x["startTime"], round(x["demand"])] for x in d[-36 * 12::12]] if d else []
    try:
        ci = json.loads(_get("https://api.carbonintensity.org.uk/intensity"))["data"][0]["intensity"]
        out["carbon_g_kwh"] = ci.get("actual") or ci.get("forecast"); out["carbon_index"] = ci.get("index")
    except Exception: pass
    return out

def _ieso():
    t = _get("https://reports-public.ieso.ca/public/RealtimeTotals/PUB_RealtimeTotals.xml").decode("utf-8", "replace")
    dd = _re.search(r"<DeliveryDate>([^<]+)", t).group(1); hr = int(_re.search(r"<DeliveryHour>(\d+)", t).group(1))
    ivs = _re.findall(r"<Interval>(\d+)</Interval>(.*?)</IntervalEnergy>", t, _re.S)
    val = None; iv = None
    for n, body in ivs:
        m = _re.search(r"ONTARIO DEMAND</MarketQuantity>\s*<EnergyMW>([\d.]+)", body)
        if m: val, iv = float(m.group(1)), int(n)
    if val is None: return {"demand_mw": None}
    # IESO times are Eastern Standard Time all year; hour ending HR, 5-minute interval IV
    end = _dt.fromisoformat(dd).replace(tzinfo=_tz(_td(hours=-5))) + _td(hours=hr - 1, minutes=5 * (iv or 1))
    return {"demand_mw": round(val), "data_time": _iso(end)}

def _hq():
    j = json.loads(_get("https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/demande-electricite-quebec/records"
                        "?where=valeurs_demandetotal%20is%20not%20null&order_by=date%20desc&limit=1"))
    r = (j.get("results") or [{}])[0]
    return {"demand_mw": round(r["valeurs_demandetotal"]) if r.get("valeurs_demandetotal") else None, "data_time": _iso(_dt.fromisoformat(r["date"])) if r.get("date") else None}

# id, name, region, lon, lat, bbox (W,S,E,N) for nearby Wire grid alerts, official site, fetcher or None, reason when None, source label
INTL = [
 ("GB", "Great Britain (NESO / Elexon)", "europe", -1.6, 53.0, (-8.7, 49.8, 1.9, 60.9), "https://www.neso.energy/", _gb, None, "Elexon BMRS demand outturn + NESO Carbon Intensity API"),
 ("IESO", "Ontario (IESO)", "americas", -84.5, 49.5, (-95.2, 41.6, -74.3, 56.9), "https://www.ieso.ca/power-data", _ieso, None, "IESO Realtime Totals report"),
 ("HQ", "Québec (Hydro-Québec)", "americas", -71.8, 50.5, (-79.8, 45.0, -57.1, 62.6), "https://www.hydroquebec.com/documents-data/open-data/", _hq, None, "Hydro-Québec open data, total demand"),
 ("ENTSOE", "Continental Europe (ENTSO-E)", "europe", 10.0, 50.0, (-10.0, 36.0, 32.0, 71.0), "https://transparency.entsoe.eu/", None, "ENTSO-E's transparency API needs a security token, and none is configured", None),
 ("AESO", "Alberta (AESO)", "americas", -114.5, 53.9, (-120.0, 49.0, -110.0, 60.0), "https://www.aeso.ca/grid/", None, "AESO's data API needs a registered key", None),
 ("AEMO", "Australia NEM (AEMO)", "apac", 146.5, -33.5, (129.0, -44.0, 154.0, -10.0), "https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem", None, "AEMO's public data endpoint returned server errors when checked", None),
 ("GRIDINDIA", "India (Grid-India)", "apac", 78.9, 22.0, (68.0, 6.0, 97.5, 35.5), "https://grid-india.in/", None, "Grid-India publishes no keyless machine-readable live feed", None),
]

def _wire_grid():
    """Worldwide Wire items about power grids or blackouts, with the Wire's own geo (signal_map.heat_payload, read-only)."""
    try:
        import signal_map, gridstatus as G, gridwatch as GW
        p = signal_map.heat_payload(); c = p.get("cols") or []
        ix = {k: i for i, k in enumerate(c)}
    except Exception:
        return []
    out = []
    for r in p.get("rows") or []:
        g = lambda k: r[ix[k]] if k in ix and ix[k] < len(r) else None
        t = (g("title") or "")
        if g("lat") is None or g("lon") is None or g("tier") == "global": continue
        if not (G.GRID_RX.search(t) or GW.GRID.search(t)): continue
        if g("cc") == "US":   # U.S. items must pass the grid desk's own classifier (drops e.g. foreign threats that merely name U.S. power plants)
            try:
                if not G.classify_grid(t, "", g("cat"), g("lat"), g("lon"))[0]: continue
            except Exception: continue
        out.append({"id": g("id"), "title": t.split("\n")[0][:220], "rank": int(g("rank") or 0), "lat": g("lat"), "lon": g("lon"), "place": g("place"),
                    "cc": g("cc"), "prec": g("prec"), "t": g("t"), "src": g("src"), "url": g("url")})
    out.sort(key=lambda x: -x["rank"])
    return out[:300]

def _in(b, lon, lat): return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]

def world():
    with _WL:
        if _W["v"] is not None and time.time() - _W["t"] < WORLD_TTL: return _W["v"]
        res = {}
        def run(k, fn):
            try: res[k] = fn()
            except Exception as ex: res[k] = {"error": type(ex).__name__}
        th = [threading.Thread(target=run, args=(o[0], o[7]), daemon=True) for o in INTL if o[7]]
        for x in th: x.start()
        for x in th: x.join(12)
        wire = _wire_grid()
        internet = []
        try:
            import netwire
            b = netwire.load()
            if b:
                internet = b.get("internet") or []
        except Exception:
            internet = []
        ops = []
        for oid, name, reg, lon, lat, bb, site, fn, why, src in INTL:
            near = [w for w in wire if _in(bb, w["lon"], w["lat"]) and (_age_h(w["t"] or "") or 99) <= 12]
            o = {"id": oid, "name": name, "region": reg, "lon": lon, "lat": lat, "site": site, "source": src,
                 "alerts_12h": len(near), "max_rank": max((w["rank"] for w in near), default=None)}
            if not fn:
                o.update(status="nodata", reason=why)
            else:
                d = res.get(oid) or {"error": "timeout"}
                o.update({k: v for k, v in d.items() if k != "error"})
                age = _age_h(d.get("data_time") or "") if d.get("data_time") else None
                o["age_h"] = round(age, 1) if age is not None else None
                if d.get("error") or d.get("demand_mw") is None: o.update(status="nodata", reason="The live feed did not answer just now")
                elif age is None or age > 6: o.update(status="nodata", reason=f"Latest published data is {age / 24:.0f} days old" if age and age > 48 else "Latest published data is more than 6 hours old")
                elif any(w["rank"] >= 5 for w in near): o.update(status="watch", reason="Wire grid alert ranked 5+ in this area in the last 12 h")
                else: o.update(status="online", reason=None)
            ops.append(o)
        # Nov 24 2026 (Matt): operators without live data are pulled from the page (map points and the Worldwide list), not shown empty.
        pulled = [{"id": o["id"], "name": o["name"], "reason": o.get("reason")} for o in ops if o.get("status") == "nodata"]
        ops = [o for o in ops if o.get("status") != "nodata"]
        v = {"generated": _iso(_dt.now(_tz.utc)), "operators": ops, "pulled": pulled, "wire": wire, "internet": internet, "ttl_s": WORLD_TTL}
        _W.update(t=time.time(), v=v)
        return v
