"""SpaceX-style intro on "/" (Matt, Nov 28 2026 3:49 AM ET brief):
  "The intro needs to reflect the current menu offerings graphically. Simple. Sleek. https://www.spacex.com/ style. Big video.
   Big beautiful images. Link to menu items. ... Zero fluff or clutter. Mobile too. They are also pulling realtime flight data.
   Maybe we could do something similar with like the high ranking stuff we put in the newsletter ... Or outages for the grid."

One full-screen panel per current menu item (read from the live menu, sitenav_ui.menu3_sections + menu5 when present), each with a
big licensed video or photograph (see CREDITS rows below; all graded grey), an uppercase headline, one line of copy, a hairline pill
button to the section, and one strip of real live numbers, like the SpaceX launch strip. Native scroll with CSS scroll-snap.

Live strips come from /api/intro/live: a compact, read-only, 60 s stale-while-revalidate roll-up of numbers the site already serves:
  wire     top-ranked Wire stories of the last 24 h          wire_timeline /api/wire_tl?time=1 (same window the Wire page uses; "24h" is not a valid time value there)
  map      stories pinned in the last 24 h, by region         same read
  weather  NWS alerts in effect now, by state               api.weather.gov/alerts/active/count (public, no key)
  grid     outages on the Wire (24 h / 7 d), U.S. customers   netmap /api/netmap/data (outages.layers, summary.power_customers)
  markets  S&P 500, Dow, Nasdaq                               markets /api/markets/data
  brief    the next brief's top 3 and its send time           newsletter.build_issue + newsletter_v2.top_stories (same as /newsletter/sample)
A section that fails or is older than 10 minutes is hidden; no number is ever invented or stored here.

Kill switch: Render env BN_INTRO_SX=0 serves the previous intro (theme._home_page_raw) unchanged. Any error in transform() also falls back.
No scanner, scoring, water, loader or status-colour code is touched."""
import hashlib, html, json, os, re, threading, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "intro_sx_static")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FILES = {"intro.css": "text/css; charset=utf-8", "intro.js": "application/javascript; charset=utf-8"}
MAX_AGE = 600

def on(): return os.environ.get("BN_INTRO_SX", "1").strip() != "0"

def _v(n):
    try:
        with open(os.path.join(STATIC, n), "rb") as f: return hashlib.sha1(f.read()).hexdigest()[:10]
    except Exception: return "0"

# ---------------------------------------------------------------- panels
# key: (menu label match, eyebrow, headline, lede, button label, media: (desktop still, mobile still, mp4, webm), credit row)
PANELS = {
 "/wire": ("wire", "The Wire", "Global threat monitoring", "Every signal from official agencies, sensors and wires, ranked 0 to 10 the moment it lands.", "Open The Wire",
           ("crvid-d.jpg", "crhero-m.jpg", "crvid-d.mp4", "crvid-d.webm"),
           ("The Wire panel video and still", "\"Time Lapse 4K Midnight City\" (view from Blackpool Tower at night) by netLike, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Time_Lapse_4K_Midnight_City.webm); graded grey", "CC BY 3.0")),
 "/map": ("map", "Heat Map", "Where it is happening", "Every story with a place, pinned live. Country and region pins when that is all that is known.", "Open the Heat Map",
          ("sxheat-d.jpg", "sxheat-m.jpg", None, None),
          ("Heat Map panel photo", "\"FEMA - 33313 - Firefighters at the Poomacha fire in California\" by Andrea Booher, FEMA, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:FEMA_-_33313_-_Firefighters_at_the_Poomacha_fire_in_California.jpg); graded grey, cropped", "Public domain")),
 "/weather": ("weather", "Weather", "Storms, live", "Warnings, radar and storm paths on one map, for anywhere you search.", "Open Weather",
              ("hero-d.jpg", "hero-m.jpg", "hero-d.mp4", None),
              ("Weather panel video and still", "NASA, International Space Station imagery of Hurricane Erin, 2025; graded grey", "Public domain (NASA media guidelines)")),
 "/grid": ("grid", "The Grid", "Power and internet, now", "Outages on the grid, the internet, cloud, cables and water, as they happen.", "Open The Grid",
           ("sxgrid-d.jpg", "sxgrid-m.jpg", None, None),
           ("The Grid panel photo", "\"H-frame suspension pylon Wisconsin US 2017\" by Tony Webster, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:H-frame_suspension_pylon_Wisconsin_US_2017.jpg); graded grey and cropped; this adaptation is shared under the same licence", "CC BY-SA 2.0")),
 "/comms": ("comms", "Comms", "When the network goes dark", "Staying in touch when the usual ways fail.", "See Comms",
            ("tvvid-d.jpg", "tvhero-m.jpg", "tvvid-d.mp4", "tvvid-d.webm"),
            ("Comms panel video and still", "NASA JSC, \"4K Earth Views Extended Cut for Earth Day 2021\" (jsc2021m000138), ISS solar array over Earth; graded grey", "Public domain")),
 "/markets": ("markets", "Markets", "Money under stress", "Index moves, bank stress and the money stories behind them.", "Open Markets",
              ("mkvid-d.jpg", "mkhero-m.jpg", "mkvid-d.mp4", "mkvid-d.webm"),
              ("Markets panel video and still", "\"Aerial views of Downtown Manhattan, New York City, USA at night ...\" by the Dronalist, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Aerial_views_of_Downtown_Manhattan,_New_York_City,_USA_at_night_including_Battery_Park,_Freedom_Tower,_Wall_Street,_The_Oculus,_West_Side_Highway_and_Hudson_River.webm); graded grey", "CC BY 3.0")),
 "/newsletter": ("brief", "Newsletter", "The brief", "The stories that matter, ranked and sourced. 7 AM and 7 PM ET. Free.", "Get the brief",
                 ("sxbrief-d.jpg", "sxbrief-m.jpg", None, None),
                 ("Newsletter panel photo", "\"US Capitol Building at night Jan 2006\" by Diliff, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:US_Capitol_Building_at_night_Jan_2006.jpg); graded grey, cropped", "Public domain")),
}
ORDER = ("/wire", "/map", "/weather", "/grid", "/comms", "/markets", "/newsletter")
ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'

def menu_items(h=None):
    """(href, label) in menu order. The live menu is the source: the links inside the page's own menu (<aside id="h_menu">),
    then sitenav_ui.menu3_sections. Only items with a panel are shown; nothing outside the menu is added."""
    found = []
    if h:
        m = re.search(r'<aside class="h-menu[^"]*" id="h_menu".*?</aside>', h, re.S)
        if m:
            for href, lab in re.findall(r'<a[^>]*href="(/[a-z]+)"[^>]*>([^<]+)</a>', m.group(0)):
                if href in PANELS and href not in [f for f, _ in found]: found.append((href, html.unescape(lab).strip()))
    if not found:
        try:
            import sitenav, sitenav_ui
            for _, _, _, rows in sitenav_ui.menu3_sections(sitenav):
                for _, lab, href in rows:
                    if href in PANELS and href not in [f for f, _ in found]: found.append((href, lab))
        except Exception: pass
    if not found: found = [(k, PANELS[k][1]) for k in ORDER]
    rank = {k: i for i, k in enumerate(ORDER)}
    return sorted(found, key=lambda x: rank.get(x[0], 99))

def credit_rows(items=None):
    return [PANELS[k][6] for k, _ in (items or [(k, "") for k in ORDER]) if k in PANELS]

def _panel(i, href, label, mv):
    key, _eb, head, lede, cta, media, _cr = PANELS[href]
    d, m, mp4, webm = media
    first = i == 0
    img = (f'<picture><source media="(max-width:700px)" srcset="/bnt/media/{m}?v={mv}">'
           f'<img src="/bnt/media/{d}?v={mv}" alt="" decoding="async"{" fetchpriority=\"high\"" if first else " loading=\"lazy\""}></picture>')
    vid = (f'<video muted loop playsinline preload="none" disablepictureinpicture tabindex="-1" aria-hidden="true"'
           + (f' data-webm="/bnt/media/{webm}?v={mv}"' if webm else "") + f' data-mp4="/bnt/media/{mp4}?v={mv}"></video>') if mp4 else ""
    tag = "h1" if first else "h2"
    return (f'<section class="sx{" sx-in" if first else ""}" id="s{i + 1}" data-k="{key}" aria-labelledby="sx_h{i + 1}">'
            f'<div class="sx-bg" aria-hidden="true">{img}{vid}</div>'
            f'<div class="sx-c">'
            f'<p class="sx-eb"><span class="sx-n">{i + 1:02d}</span><span>{E(label)}</span><span class="sx-live" data-live="{key}" hidden><i></i><b>Live</b></span></p>'
            f'<{tag} class="sx-h" id="sx_h{i + 1}">{E(head)}</{tag}>'
            f'<p class="sx-l">{E(lede)}</p>'
            f'<div class="sx-d" data-d="{key}" aria-live="polite" hidden></div>'
            f'<a class="sx-btn" href="{E(href)}">{E(cta)}{ARROW}</a>'
            f'</div></section>')

def panels_html(items, mv):
    rail = "".join(f'<li><a href="#s{i + 1}" aria-label="{E(lab)}"><span>{E(lab)}</span></a></li>' for i, (_, lab) in enumerate(items))
    return "\n".join(_panel(i, href, lab, mv) for i, (href, lab) in enumerate(items)), f'<nav class="sx-rail" aria-label="Sections"><ol>{rail}</ol></nav>'

def transform(h):
    """Take the previous intro's full HTML (head, header, menu, scripts, footer) and swap its video sections for one
    panel per menu item. Everything outside <main> stays exactly as the previous intro built it.
    Matt 9:06 AM ET Nov 28: do not keep the bottom Stay connected / email signup section on "/".
    The 07 Newsletter / The brief panel already links to /newsletter. Section s6 stays in the raw
    previous-intro markup so the fallback (BN_INTRO_SX=0) and the structural check stay intact."""
    m_main = re.search(r'<main id="flow"[^>]*>.*?</main>', h, re.S)
    s6 = re.search(r'<section class="h-sec"[^>]*id="s6"[^>]*>.*?</section>', h, re.S)
    foot = re.search(r'<footer class="h-foot".*?</footer>', h, re.S)
    if not (m_main and s6 and foot): raise ValueError("previous intro markup changed")
    mv = (re.search(r'window\.BNT_MEDIA_V="([^"]*)"', h) or [None, "1"])[1]
    items = menu_items(h)
    if len(items) < 2: raise ValueError("menu not readable")
    panels, rail = panels_html(items, mv)
    main = f'<main id="flow">\n{panels}\n{foot.group(0)}\n</main>\n{rail}'
    h = h[:m_main.start()] + main + h[m_main.end():]
    d0, m0 = PANELS[items[0][0]][5][0], PANELS[items[0][0]][5][1]
    h = re.sub(r'<link rel="preload" as="image" href="/bnt/media/hero-d\.jpg[^>]*>', f'<link rel="preload" as="image" href="/bnt/media/{d0}?v={mv}" media="(min-width:701px)">', h, 1)
    h = re.sub(r'<link rel="preload" as="image" href="/bnt/media/hero-m\.jpg[^>]*>', f'<link rel="preload" as="image" href="/bnt/media/{m0}?v={mv}" media="(max-width:700px)">', h, 1)
    h = re.sub(r'<ol class="h-pager"[^>]*></ol>\n?', "", h)
    h = h.replace('href="#s6"', 'href="/newsletter"')
    h = h.replace('<body class="bnt-home"', '<body class="bnt-home sx-body"', 1).replace('<html lang="en" data-bnt-home', '<html lang="en" data-bnt-home data-sx', 1)
    h = re.sub(r'(<link rel="stylesheet" href="[^"]*home\.css[^"]*">)', r'\1<link rel="stylesheet" href="/api/intro/intro.css?v=' + _v("intro.css") + '">', h, 1)
    h, n = re.subn(r'<script src="[^"]*home\.js[^"]*" defer></script>', '<script src="/api/intro/intro.js?v=' + _v("intro.js") + '" defer></script>', h)
    if n != 1 or "intro.css" not in h: raise ValueError("previous intro scripts changed")
    return h

# ---------------------------------------------------------------- live data (read-only, 60 s stale-while-revalidate)
UPSTREAM = os.environ.get("BN_INTRO_UPSTREAM", "").rstrip("/")   # preview harness only: read the same public endpoints from a live site

def _upstream(path, raw=False):
    import urllib.request
    err = None
    for _ in range(3):
        try:
            rq = urllib.request.Request(UPSTREAM + path, headers={"User-Agent": "Mozilla/5.0 (BN intro preview)", "Accept": "*/*"})
            with urllib.request.urlopen(rq, timeout=60) as r:
                b = r.read().decode("utf-8")
                return b if raw else json.loads(b)
        except Exception as ex: err = ex
    raise err

def _mod(name):
    import sys
    s = sys.modules.get("server")
    if s is not None and hasattr(s, "_addon_mod"):
        try: return s._addon_mod(name)
        except Exception: pass
    return __import__(name)

def _call(mod, path, qs=None):
    if UPSTREAM:
        q = "&".join(f"{k}={v[0]}" for k, v in (qs or {}).items())
        return _upstream(path + ("?" + q if q else ""))
    r = _mod(mod).handle_get(path, qs or {})
    code, body = r[0], r[1]
    if code != 200: raise RuntimeError(f"{path} -> {code}")
    if isinstance(body, (bytes, bytearray)): body = body.decode("utf-8")
    if isinstance(body, str): body = json.loads(body)
    return body

_CUR = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ(\|[0-9a-f]{1,40})?$")

def _epoch(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()

REGIONS = {"na": "North America", "eu": "Europe", "as": "Asia", "me": "Middle East", "af": "Africa", "la": "Latin America",
           "oc": "Oceania", "sea": "Southeast Asia", "gl": "Global"}

def _clean(t, n=110):
    t = re.sub(r"https?://\S*", "", str(t or ""))
    t = re.sub(r"\s+", " ", t).strip(" -\u2013\u2014|:")
    t = re.sub(r"^\d{1,2}/\s*", "", t)
    t = re.sub(r"\s*[-\u2013\u2014|]\s*(MeteoAlarm|Reuters|AP|BBC News)$", "", t)
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "\u2026"

def _readable(t):
    """A headline a reader can scan: not a hashtag string, not a bare link, long enough to say something."""
    t = str(t or "")
    return t.count("#") < 2 and len(_clean(t)) >= 28 and not re.search(r"\bwww\.\S+$", t.strip())

def _row(x):
    return {"id": x.get("id"), "h": _clean(x.get("h") or x.get("d")), "r": int(x.get("r") or 0), "t": x.get("t"), "loc": _clean(x.get("loc") or "", 40)}

def _b_feed():
    """One Wire read (last 24 h) shared by the Wire and Heat Map strips.

    The Wire page's 24-hour chip sends time=1 (a number of days). time=24h is not a valid
    window and the API treats it as unfiltered, which is also how the empty-first-page
    glitch produced counts in the tens instead of the hundreds. Page until the API says
    we are done, so the totals are the same set the Wire would show for that window.
    """
    now, it, seen, more = time.time(), [], set(), False
    qs = {"time": ["1"], "limit": ["200"]}      # 1 day: same parameter the /wire "24 hours" chip sends
    for page in range(20):
        d = _call("wire_timeline", "/api/wire_tl", qs)
        rows = [x for x in (d.get("items") or []) if x.get("t") and x.get("id") not in seen]
        seen.update(x.get("id") for x in rows)
        it += [x for x in rows if now - _epoch(x["t"]) <= 86400 + 300]
        nx = d.get("next")
        if d.get("end") or not nx or not _CUR.match(str(nx)) or now - _epoch(str(nx).split("|")[0]) > 86400 + 300:
            more = False
            break
        if page == 19:
            more = True
            break
        qs = {"time": ["1"], "limit": ["200"], "before": [str(nx)]}
    if not it: raise RuntimeError("no wire items")
    ok = [x for x in it if _readable(x.get("h") or x.get("d"))]
    top = sorted(ok, key=lambda x: (-int(x.get("r") or 0), -_epoch(x["t"])))
    wire = {"n": len(it), "more": more, "hi": sum(1 for x in it if int(x.get("r") or 0) >= 7), "top": [_row(x) for x in top[:3]]}
    pins = [x for x in it if x.get("lat") is not None and x.get("lon") is not None]
    regs = {}
    for x in pins: regs[x.get("g") or "gl"] = regs.get(x.get("g") or "gl", 0) + 1
    rl = sorted(((REGIONS.get(k, k.upper()), v) for k, v in regs.items() if k != "gl"), key=lambda r: -r[1])
    mp = {"n": len(pins), "more": more, "regions": len(rl), "by": [{"name": a, "n": b} for a, b in rl[:4]]}
    return {"wire": wire, "map": mp}

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
          "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
          "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
          "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
          "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
          "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
          "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington, D.C.", "PR": "Puerto Rico"}

def _b_weather():
    """National Weather Service: alerts in effect right now (api.weather.gov/alerts/active/count, public, no key)."""
    import urllib.request
    rq = urllib.request.Request("https://api.weather.gov/alerts/active/count", headers={"User-Agent": "BLACKOUT.NETWORK (hello@blackout.network)", "Accept": "application/geo+json"})
    with urllib.request.urlopen(rq, timeout=20) as r: d = json.loads(r.read().decode("utf-8"))
    if d.get("total") is None: raise RuntimeError("no NWS count")
    ar = sorted(((STATES[k], int(v)) for k, v in (d.get("areas") or {}).items() if k in STATES), key=lambda x: -x[1])
    return {"total": int(d["total"]), "land": int(d.get("land") or 0), "states": sum(1 for _, v in ar if v), "top": [{"name": a, "n": b} for a, b in ar[:3]]}

def _b_grid():
    G = _call("netmap", "/api/netmap/data")
    o = G.get("outages") or {}
    L = o.get("layers") or {}
    if not L: raise RuntimeError("no outage layers")
    n24 = sum(int((v or {}).get("n24") or 0) for v in L.values())
    n7 = sum(int((v or {}).get("n7") or 0) for v in L.values())
    c24 = int((G.get("summary") or {}).get("countries_24h") or 0)
    us = next((v.get("us") for v in L.values() if (v or {}).get("us") and v.get("us") != "U.S.: none major"), "U.S.: none major")
    pc = (G.get("summary") or {}).get("power_customers")
    sts = sorted(((G.get("power") or {}).get("states") or []), key=lambda s: -int(s.get("outages") or 0))
    top = {"name": sts[0].get("name"), "n": int(sts[0].get("outages") or 0)} if sts and sts[0].get("outages") else None
    return {"n24": n24, "n7": n7, "countries": c24, "us": us, "customers": int(pc) if pc is not None else None, "top_state": top}

def _b_markets():
    M = _call("markets", "/api/markets/data")
    us = ((M.get("markets") or {}).get("us") or [])
    rows = [{"label": r.get("label"), "price": r.get("price"), "chg": r.get("chg_pct")} for r in us if r.get("price") is not None][:3]
    if not rows: raise RuntimeError("no markets")
    return {"rows": rows}

def _b_brief_upstream():
    hb = _upstream("/newsletter/sample", raw=True)
    t = html.unescape(re.sub(r"<style.*?</style>|<script.*?</script>", "", hb, flags=re.S))
    rows = []
    txt = re.sub(r"<[^>]+>", "|", t); txt = re.sub(r"\s*\|[\s|]*", "|", txt)
    for m in re.finditer(r"RANK (\d+) \u00b7 [A-Z ]+\|(?:\u00b7\|([A-Z][A-Z ,.'\-]{2,})\|)?([^|]{20,220})\|", txt):
        rows.append({"r": int(m.group(1)), "loc": (m.group(2) or "").title().strip(), "h": _clean(m.group(3))})
    ids = re.findall(r'/wire/([0-9a-f]{16})', hb)
    seen = []
    for i in ids:
        if i not in seen: seen.append(i)
    for r, i in zip(rows, seen): r["id"] = i
    m = re.search(r"(MORNING|EVENING) BRIEF", txt)
    return rows[:3], (m.group(1).lower() if m else None)

def _b_brief():
    if UPSTREAM:
        top, slot = _b_brief_upstream()
        nxt = None
    else:
        N = _mod("newsletter")
        import newsletter_v2
        c = N.cfg(); at = N.now()
        k = N.db(); last = k.execute("SELECT MAX(slot_time) FROM slot_runs WHERE status LIKE 'done%'").fetchone()[0]; k.close()
        nx = N.next_slots(at, 1, c)[0]
        from datetime import timedelta
        since = max(N.parse_t(last) or at - timedelta(hours=12), at - timedelta(hours=float(c["max_window_hours"])))
        issue = N.build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=at, since=since, slot=nx["slot"], c=c)
        top = [{"id": it.get("cluster_id"), "h": _clean(it.get("title")), "r": int(it.get("rank") or 0), "loc": _clean(it.get("location") or "", 40)}
               for it in newsletter_v2.top_stories(issue, 3)]
        slot = nx.get("slot"); nxt = nx.get("time")
    slots = {"morning": "07:00", "evening": "19:00"}
    try:
        if not UPSTREAM: slots = dict(_mod("newsletter").cfg().get("slots") or slots)
    except Exception: pass
    return {"top": top, "slot": slot, "next": nxt, "slots": slots}

BUILDERS = (("feed", _b_feed), ("weather", _b_weather), ("grid", _b_grid), ("markets", _b_markets), ("brief", _b_brief))
KEYS = ("wire", "map", "weather", "grid", "markets", "brief")
_C = {"t": 0, "v": None, "busy": False, "good": {}}
_L = threading.Lock()

def _build():
    out, errs = {}, {}
    def one(k, fn):
        try: out[k] = fn()
        except Exception as ex: out[k] = None; errs[k] = type(ex).__name__
    ts = [threading.Thread(target=one, args=(k, fn), daemon=True) for k, fn in BUILDERS]
    for t in ts: t.start()
    for t in ts: t.join(50)
    now = time.time()
    with _L: prev = _C["v"] or {}; good = _C["good"]
    f = out.get("feed") or {}
    res = {"wire": f.get("wire"), "map": f.get("map"), "weather": out.get("weather"), "grid": out.get("grid"), "markets": out.get("markets"), "brief": out.get("brief")}
    for k in KEYS:
        if res.get(k) is not None: good[k] = now
        elif prev.get(k) is not None and now - good.get(k, 0) < MAX_AGE: res[k] = prev[k]
        else: res[k] = None
    if errs: res["errors"] = errs
    res["ts"] = int(now); res["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return res

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

def handle_get(path, qs):
    if path == "/api/intro/live":
        try: return 200, live()
        except Exception as ex: return 503, {"error": "intro data unavailable", "detail": type(ex).__name__}
    n = path[len("/api/intro/"):] if path.startswith("/api/intro/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as f: return 200, f.read(), FILES[n]
    return 404, {"error": "not found"}
