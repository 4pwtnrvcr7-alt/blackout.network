"""Intro v2 (Matt, Nov 27 2026 10:49 PM ET, pt2029u): "/" rebuilt in the spacex.com language.

One full-viewport panel per current menu item (menu5.items(), so deactivated pages drop out on their own), each with a big
licensed video (phones get a 540x960 cut, reduced motion / Save-Data get the poster still) and one link to that page.
Live overlays come from one small read-only endpoint, /api/intro/live, built from the same data the pages already serve:
  hero strip   theme.summary() (last scan, Wire count, rank 7+ count) + netlaunch (next orbital launch, T- countdown)
  The Wire     theme.summary()["top"]: rank 7+ first, 2+ independent source families, by rank then score (the newsletter pool)
  Heat Map     theme.summary() bands + mapped points
  Weather      wxmap alerts (NWS active alerts, api.weather.gov)
  The Grid     gridpage data (DOE/ORNL ODIN outages by state, EIA-930 region status, NOAA SWPC G-scale)
  Markets      markets data (Yahoo Finance delayed quotes)
  Newsletter   fixed send schedule (7 AM and 7 PM ET)
Matt 10:50 PM: silky scroll, no sticking. Native scrolling only (no snap, no scroll-jacking); only the panel on screen plays;
a full-screen loader (Grid-loader family, real progress, percent only) holds the page until media and data are in.
Kill switch: Render env BN_INTRO_V2=0 serves the previous intro (theme._home_page_raw) unchanged.
No scanner, scoring or write paths are touched; everything here is read-only."""
import hashlib, html, json, os, re, threading, time
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "intro_static")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FILES = {"intro.css": "text/css; charset=utf-8", "intro.js": "application/javascript; charset=utf-8"}

def on(): return os.environ.get("BN_INTRO_V2", "1").strip() != "0"

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = timezone(timedelta(hours=-5))

def _v(n):
    try:
        with open(os.path.join(STATIC, n), "rb") as f: return hashlib.sha1(f.read()).hexdigest()[:10]
    except Exception: return "0"

# ---------------------------------------------------------------- panels
# menu5 key -> (panel id, media key, eyebrow, title, CTA label). Media: theme_static/media/<key>-d|m.mp4|jpg (see CREDITS rows below).
PANELS = {
    "intro":      ("top",     "hero",   "Live",          "Global threat monitoring", "Explore"),
    "threat":     ("wire",    "ixwire", "Top stories",   "The Wire",                 "Open The Wire"),
    "heatmap":    ("heat",    "ixheat", "Worldwide",     "Heat Map",                 "Open the Heat Map"),
    "weather":    ("weather", "noise",  "United States", "Weather",                  "Open Weather"),
    "net":        ("grid",    "ixgrid", "Power and networks", "The Grid",            "Open The Grid"),
    "finance":    ("markets", "ixmkt",  "Delayed quotes", "Markets",                 "Open Markets"),
    "newsletter": ("brief",   "email",  "7 AM and 7 PM ET", "The Brief",             "Get the free brief"),
}
CREDITS = [
    ("Intro panel video", "NASA, International Space Station imagery of Hurricane Erin, 2025", "Public domain (NASA media guidelines)"),
    ("The Wire panel video", 'NASA, "Earth Views from the ISS - No Music" (NHQ_2020_1221), 2020; graded grey, 10-second loop', "Public domain"),
    ("Heat Map panel video", "NASA Goddard, \"Lights of Human Activity Shine in NASA's Image of Earth at Night\" (2017), Suomi NPP VIIRS city lights", "Public domain"),
    ("Weather panel video", "NASA, International Space Station imagery of Hurricane Dorian, 2019", "Public domain"),
    ("The Grid panel video", '"Time Lapse 4K Midnight City" by netLike, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Time_Lapse_4K_Midnight_City.webm); graded grey, cropped', "CC BY 3.0"),
    ("Markets panel video", '"Aerial views of Downtown Manhattan, New York City, USA at night ..." by the Dronalist, via Wikimedia Commons; graded grey, cropped', "CC BY 3.0"),
    ("The Brief panel video", "NASA, International Space Station, Earth from orbit, 2019", "Public domain"),
]

def _panels():
    try:
        import menu5
        rows = menu5.items()
    except Exception:
        rows = [("intro", "Intro", "/"), ("threat", "The Wire", "/wire"), ("newsletter", "Newsletter", "/newsletter")]
    out = []
    for k, label, href in rows:
        if k not in PANELS: continue   # a newer menu item without media yet: it stays in the menu, no panel until it has licensed media
        pid, mk, eb, title, cta = PANELS[k]
        out.append(dict(key=k, id=pid, media=mk, eyebrow=eb, title=title, cta=cta, href=("#wire" if k == "intro" else href.split("?")[0])))
    if not out or out[0]["key"] != "intro":
        pid, mk, eb, title, cta = PANELS["intro"]
        out.insert(0, dict(key="intro", id=pid, media=mk, eyebrow=eb, title=title, cta=cta, href="#wire"))
    return out

def _theme():
    import theme
    return theme

ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'

def _overlay(pid):
    """Server-rendered empty slots; intro.js fills them from /api/intro/live (no placeholder numbers are ever shown)."""
    if pid == "top":
        return ('<dl class="ix-strip" id="ix_strip" aria-live="off">'
                '<div><dt>Last scan</dt><dd data-f="scan"></dd></div><div><dt>On the Wire</dt><dd data-f="wire"></dd></div>'
                '<div><dt>Rank 7+</dt><dd data-f="high"></dd></div>'
                '<div class="ix-ln"><dt>Next launch</dt><dd><span data-f="tminus"></span><small data-f="launch"></small></dd></div></dl>')
    if pid == "wire": return '<ol class="ix-list" data-f="top" aria-label="Top stories right now"></ol>'
    if pid == "heat": return '<div class="ix-nums" data-f="bands"></div>'
    if pid == "weather": return '<div class="ix-nums" data-f="wxn"></div><ul class="ix-rows" data-f="wx"></ul>'
    if pid == "grid": return '<div class="ix-nums" data-f="gridn"></div><ul class="ix-rows" data-f="grid"></ul>'
    if pid == "markets": return '<div class="ix-tick" data-f="mk"></div>'
    if pid == "brief": return '<div class="ix-nums" data-f="brief"></div>'
    return ""

def _follow():
    """Matt 5:28 PM Nov 17: the follow band sits on the page black, above the footer (same block as the previous intro)."""
    try:
        import growth
        return growth.follow_html()
    except Exception:
        return ""

def page():
    T = _theme()
    _, mv = T.versions()
    ps = _panels()
    secs = []
    for i, p in enumerate(ps):
        mk = p["media"]; first = i == 0
        head = (f'<h1 class="ix-h">{E(p["title"])}</h1>' if first else f'<h2 class="ix-h">{E(p["title"])}</h2>')
        secs.append(
            f'<section class="ix-p{" ix-hero" if first else ""}" id="{E(p["id"])}" data-m="{E(mk)}" aria-label="{E(p["title"])}">'
            f'<div class="ix-bg" aria-hidden="true"><picture><source media="(max-width:900px),(orientation:portrait)" srcset="/bnt/media/{mk}-m.jpg?v={mv}">'
            f'<img src="/bnt/media/{mk}-d.jpg?v={mv}" alt="" decoding="async"{" fetchpriority=\"high\"" if first else " loading=\"lazy\""}></picture>'
            f'<video muted loop playsinline preload="none" disablepictureinpicture tabindex="-1"></video></div>'
            f'<div class="ix-c"><p class="ix-k">{E(p["eyebrow"])}</p>{head}{"" if first else _overlay(p["id"])}'
            f'<a class="ix-cta" href="{E(p["href"])}">{E(p["cta"])}{ARROW}</a></div>{_overlay(p["id"]) if first else ""}</section>')
    wm = '<span class="bnt-wm">blackout.network</span>'
    lv = "/wire" if T._live_off() else "/live"
    m5 = ""
    try:
        import menu5
        if menu5.on(): m5 = menu5.html_block(None, intro_href="#top")
    except Exception:
        import traceback; traceback.print_exc()
    menu_body = m5 or "".join(f'<a class="h-mlive" href="{E(p["href"])}">{E(p["title"])}</a>' for p in ps)
    foot = "".join(f'<a href="{h}">{x}</a>' for h, x in (("/privacy", "Privacy"), ("/tos", "Terms"), ("/sources", "Sources"), ("/scoring", "How we score"), ("/credits#intro", "Image credits")) if not T._off(h))
    media = json.dumps([p["media"] for p in ps])
    hx = '<span class="bn-hx" aria-hidden="true"><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span><span class="bn-hx-bar"></span></span>'
    m4btn = '<span class="bn-bl"><span class="bn-bl-a">Menu</span><span class="bn-bl-b">Close</span></span>'
    cells = "".join(f'<i class="ix-ldc" data-r="{9 - r}"><b></b></i>' for r in range(10) for c in range(10))
    D = T.DESC
    return f'''<!doctype html><html lang="en" data-bnt-home class="ix-loading"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<script>{T.HEAD_JS}</script>
<title>Global threat monitoring | BLACKOUT.NETWORK</title>
<meta name="description" content="{E(D)}"><meta name="theme-color" content="#000000">
<link rel="canonical" href="https://blackout.network/">
<meta property="og:type" content="website"><meta property="og:site_name" content="BLACKOUT.NETWORK"><meta property="og:title" content="Global threat monitoring | BLACKOUT.NETWORK">
<meta property="og:description" content="{E(D)}"><meta property="og:url" content="https://blackout.network/">
<meta property="og:image" content="https://blackout.network/og/home.png?v=5"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Global threat monitoring | BLACKOUT.NETWORK">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://blackout.network/og/home.png?v=5"><meta name="twitter:site" content="@BlkoutNtw">
<meta name="twitter:title" content="Global threat monitoring | BLACKOUT.NETWORK"><meta name="twitter:description" content="{E(D)}">
<link rel="preload" href="/fonts/montserrat-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" as="image" href="/bnt/media/hero-d.jpg?v={mv}" media="(min-width:901px) and (orientation:landscape)"><link rel="preload" as="image" href="/bnt/media/hero-m.jpg?v={mv}" media="(max-width:900px),(orientation:portrait)">
<link rel="stylesheet" href="{T.url("theme.css")}"><link rel="stylesheet" href="{T.url("home.css")}"><link rel="stylesheet" href="/api/intro/intro.css?v={_v("intro.css")}">
<script>window.BNT_MEDIA_V="{mv}";window.BN_IX_MEDIA={media}</script>
</head><body class="bnt-home ix-body" data-bn-noreport>
<div class="ix-ld" id="ix_ld" role="progressbar" aria-label="Loading" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="ix-ldb" aria-hidden="true">{cells}</div><p class="ix-ldn"><b id="ix_ldn">0</b><small>%</small></p></div>
<header class="h-nav ix-nav" id="h_nav">
 <a class="h-wm" href="{lv}" aria-label="BLACKOUT.NETWORK {'The Wire' if lv == '/wire' else 'live dashboard'}">{wm}</a>
 <div class="h-right"><button class="h-burger" type="button" data-h-menu aria-label="Open menu" aria-controls="h_menu" aria-expanded="false">{hx}{m4btn}</button></div>
</header>
<main id="flow" class="ix-flow">
{"".join(secs)}
</main>
{_follow()}<footer class="h-foot" id="ix_foot"><nav aria-label="Legal">{foot}</nav><p>BLACKOUT.NETWORK &middot; Independent signals, not an official alert service.</p></footer>
<div class="h-scrim" id="h_scrim"></div>
<aside class="h-menu h-menu4" id="h_menu" aria-hidden="true" aria-label="Site menu">
 <button class="h-x" type="button" aria-label="Close menu">&times;</button>
 <a class="h-wm" href="{lv}" style="display:block;margin:0 0 18px;font-size:18px">{wm}</a>
 {menu_body}
</aside>
<script src="{T.url("theme.js")}"></script><script src="/api/intro/intro.js?v={_v("intro.js")}" defer></script>
</body></html>'''

# ---------------------------------------------------------------- live data (read-only, 60 s stale-while-revalidate)
UPSTREAM = os.environ.get("BN_INTRO_UPSTREAM", "").rstrip("/")   # preview harness only: read the same public endpoints from a live site

def _upstream(path):
    import urllib.request
    err = None
    for _ in range(3):
        try:
            rq = urllib.request.Request(UPSTREAM + path, headers={"User-Agent": "Mozilla/5.0 (BN intro preview)", "Accept": "application/json"})
            with urllib.request.urlopen(rq, timeout=20) as r: return json.loads(r.read().decode("utf-8"))
        except Exception as ex: err = ex
    raise err

def _mod(name):
    import sys
    s = sys.modules.get("server")
    if s is not None and hasattr(s, "_addon_mod"):
        try: return s._addon_mod(name)
        except Exception: pass
    return __import__(name)

def _call(mod, path):
    if UPSTREAM: return _upstream(path)
    r = _mod(mod).handle_get(path, {})
    code, body = r[0], r[1]
    if code != 200: raise RuntimeError(f"{path} -> {code}")
    if isinstance(body, (bytes, bytearray)): body = body.decode("utf-8")
    if isinstance(body, str): body = json.loads(body)
    return body

def _summary():
    if UPSTREAM: return _upstream("/api/live/summary")
    return _theme().summary()

def _clean_title(t):
    t = re.sub(r"^\s*\[[A-Z ]{2,12}\]\s*", "", str(t or ""))
    return t.strip()

def _iso_et(s, fmt="%-I:%M %p ET"):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(ET).strftime(fmt)
    except Exception: return ""

SEV = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1}

def _story_headline(cid, title):
    """Same headline the story page leads with: desk / writer note headline when one exists, else the cleaned scanner title."""
    cid = str(cid or "")
    if UPSTREAM and cid:
        try:
            import urllib.request
            rq = urllib.request.Request(UPSTREAM + "/wire/" + cid, headers={"User-Agent": "Mozilla/5.0 (BN intro preview)"})
            with urllib.request.urlopen(rq, timeout=20) as r: h = r.read().decode("utf-8", "replace")
            m = re.search(r'<h1 class="t">(.*?)</h1>', h, re.S)
            if m: return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        except Exception: pass
    elif cid:
        try:
            note = _mod("story_v3").note_for(cid) or {}
            st = note.get("story") if isinstance(note.get("story"), dict) else {}
            h = (st.get("headline") or note.get("headline") or "").strip()
            if h: return h
        except Exception: pass
    try: return _theme()._headline(_clean_title(title))
    except Exception: return _clean_title(title)

def _b_top():
    S = _summary()
    top = []
    for x in (S.get("top") or [])[:3]:
        if not x.get("url") or not x.get("title"): continue
        cid = str(x["url"]).rsplit("/", 1)[-1]
        top.append({"t": _story_headline(cid, x.get("full") or x.get("title")), "r": int(x.get("rank") or 0), "loc": x.get("loc") or "", "u": x["url"], "n": int(x.get("sources") or 0)})
    b = S.get("bands") or {}
    return {"scan": S.get("last_scan_et") or "", "scan_iso": S.get("last_scan") or "", "wire": int(S.get("wire") or 0),
            "high": int(b.get("high") or 0), "elev": int(b.get("elevated") or 0), "calm": int(b.get("calm") or 0),
            "mapped": len(S.get("geo") or []), "top": top}

def _b_launch():
    L = _call("netmap", "/api/netmap/launches")
    now = datetime.now(timezone.utc)
    up = []
    for x in L.get("launches") or []:
        try: t = datetime.fromisoformat(str(x.get("net")).replace("Z", "+00:00"))
        except Exception: continue
        if t <= now - timedelta(minutes=2) or str(x.get("status") or "") in ("Success", "Failure", "Partial Failure"): continue
        up.append((t, x))
    if not up: return None
    t, x = min(up, key=lambda a: a[0])
    return {"net": t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "name": (x.get("vehicle") or x.get("name") or "")[:40],
            "prov": (x.get("provider") or "")[:60], "status": x.get("status") or "", "prec": x.get("net_precision") or ""}

def _b_wx():
    W = _call("wxmap", "/api/wxmap/alerts")
    feats = [f.get("properties") or {} for f in W.get("features") or []]
    feats.sort(key=lambda p: (-SEV.get(p.get("severity"), 0), 0 if not p.get("watch") else 1))
    rows = []
    for p in feats[:3]:
        area = str(p.get("area") or "").split(";")[0].strip()
        rows.append({"e": p.get("event") or "", "a": area[:48], "s": p.get("severity") or ""})
    counts = sorted((W.get("counts") or {}).items(), key=lambda a: -a[1])[:3]
    return {"n": len(feats), "rows": rows, "counts": counts}

def _b_grid():
    G = _call("gridpage", "/api/gridpage/data")
    st = sorted(G.get("states") or [], key=lambda s: -int(s.get("outages") or 0))
    tot = sum(int(s.get("outages") or 0) for s in st)
    regs = G.get("regions") or []
    bad = sum(1 for r in regs if r.get("status") in ("degraded", "stressed", "emergency", "alert"))
    watch = sum(1 for r in regs if r.get("status") == "watch")
    sw = G.get("swpc") or {}
    return {"out": tot, "states": [{"n": s.get("name") or s.get("st"), "o": int(s.get("outages") or 0)} for s in st[:3] if int(s.get("outages") or 0) > 0],
            "regions": len(regs), "bad": bad, "watch": watch, "g": int(sw.get("g") or 0),
            "asof": _iso_et(((G.get("freshness") or {}).get("odin") or {}).get("ts"))}

def _b_mk():
    M = _call("markets", "/api/markets/data").get("markets") or {}
    want = [("us", "^GSPC", "S&P 500"), ("us", "^DJI", "Dow"), ("us", "^IXIC", "Nasdaq"), ("crypto", "BTC-USD", "Bitcoin"), ("metals", "GC=F", "Gold")]
    out = []
    for g, sym, lab in want:
        rows = M.get(g) or []
        x = next((r for r in rows if r.get("sym") == sym), None)
        if x is None: x = next((r for r in rows if str(r.get("label", "")).lower().startswith(lab.lower())), None)
        if x and x.get("price") is not None:
            out.append({"l": lab, "p": float(x["price"]), "c": round(float(x.get("chg_pct") or 0), 2)})
    return {"q": out, "asof": _iso_et(M.get("updated")), "stale": bool(M.get("stale"))}

def _b_brief():
    now = datetime.now(ET)
    for add in range(0, 2):
        for h in (7, 19):
            t = (now + timedelta(days=add)).replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now: return {"next": t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "label": t.strftime("%-I %p ET").replace(" AM", " AM").replace(" PM", " PM")}
    return None

BUILDERS = (("wire", _b_top), ("launch", _b_launch), ("wx", _b_wx), ("grid", _b_grid), ("mk", _b_mk), ("brief", _b_brief))
_C = {"t": 0, "v": None, "busy": False}
_L = threading.Lock()

def _build():
    """Each overlay is built on its own thread; one slow or failed source only hides its own overlay (nothing fake is shown)."""
    out, errs = {}, {}
    def one(k, fn):
        try: out[k] = fn()
        except Exception as ex: out[k] = None; errs[k] = type(ex).__name__
    ts = [threading.Thread(target=one, args=(k, fn), daemon=True) for k, fn in BUILDERS]
    for t in ts:
        t.start()
        if UPSTREAM: t.join(70)   # preview harness: one upstream request at a time
    for t in ts: t.join(45)
    now = time.time()
    with _L: prev = _C["v"] or {}; good = _C.setdefault("good", {})
    for k, _ in BUILDERS:
        if out.get(k) is not None: good[k] = now
        elif prev.get(k) is not None and now - good.get(k, 0) < 600: out[k] = prev[k]   # a blip keeps the last good overlay (max 10 min old)
        out.setdefault(k, None)
    if errs: out["errors"] = errs
    out["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out

def _refresh():
    try:
        v = _build()
        with _L: _C.update(t=time.time(), v=v)
    finally:
        with _L: _C["busy"] = False

def live():
    with _L:
        v, age, busy = _C["v"], time.time() - _C["t"], _C["busy"]
        if v is not None and age > 60 and not busy:
            _C["busy"] = True; threading.Thread(target=_refresh, daemon=True).start()
    if v is None:
        _refresh()
        with _L: v = _C["v"]
    return v

# ---------------------------------------------------------------- routes (/api/intro/*)
def handle_get(path, qs):
    if path == "/api/intro/live":
        try: return 200, live()
        except Exception as ex: return 503, {"error": "intro data unavailable", "detail": type(ex).__name__}
    n = path[len("/api/intro/"):] if path.startswith("/api/intro/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as f: return 200, f.read(), FILES[n]
    return 404, {"error": "not found"}
