"""Global signal map. Public homepage card plus /map.

Draws the Control panel v2 map: Leaflet, the bundled Natural Earth world.geojson, and the same
.signal dots (panel/app.js renderMap, panel/style.css). The panel's OpenFreeMap / MapLibre tile
layer is not used, so there is no tile server and no API key. Dots are colored by category.

Dots are Wire and Watchlist stories (watchlist 0 and 1). A stored coordinate is used when
the row has one. Otherwise a place is inferred offline from the headline and location text
(signal_place.py, the bundled gazetteer). Nothing here calls a geocoder, scores, or writes.

Vendored in signal_map_static/: Leaflet 1.9.4 (BSD-2-Clause) and Natural Earth 110m admin-0
(public domain), copied from the panel package. MapLibre is not shipped.
"""
import os, re
import html as _html

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "signal_map_static")
FILES = {
    "app.js": "application/javascript",
    "app.css": "text/css",
    "leaflet.js": "application/javascript",
    "leaflet.css": "text/css",
    "world.geojson": "application/json",
}
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
# Mapped buckets for the chip row. Colors live in signal_map_static/app.js so the dots and the chips share one palette.
CATS = (("health", "Health"), ("weather", "Weather"), ("conflict", "Conflict"), ("quake", "Quake"),
        ("solar", "Solar"), ("grid", "Grid"), ("cyber", "Cyber"), ("nuclear", "Nuclear"),
        ("politics", "Politics"), ("other", "Other"))
SR = ('<p class="bn-sig-sr">Dots are colored by category. Rank stays in the story popup. '
      'An approximate place is a solid dot. Category choices are saved on this device.</p>')

def cats_html():
    btns = ['<button type="button" data-cat="all" aria-pressed="true">All</button>',
            '<button type="button" data-cat="none" aria-pressed="false">None</button>']
    for cid, label in CATS:
        btns.append(f'<button type="button" data-cat="{cid}" aria-pressed="true"><i aria-hidden="true"></i>{label}</button>')
    return '<div class="bn-sig-cats" role="group" aria-label="Categories">' + "".join(btns) + "</div>"

def search_html():
    return ('<div class="bn-sig-find"><form class="bn-sig-search" role="search" action="#">'
            '<label class="bn-sig-sr" for="bn_sig_q">Search stories</label>'
            '<input id="bn_sig_q" type="search" placeholder="Search stories" autocomplete="off" spellcheck="false" '
            'enterkeyhint="search" aria-autocomplete="list" aria-controls="bn_sig_results" aria-expanded="false">'
            '<button type="button" class="bn-sig-clear" hidden aria-label="Clear search">\u00d7</button></form>'
            '<div id="bn_sig_results" class="bn-sig-results" role="listbox" hidden></div></div>')

def views_html(active="us"):
    def btn(name, label):
        on = "true" if name == active else "false"
        return f'<button type="button" data-view="{name}" aria-pressed="{on}">{label} <b data-n="{name}">0</b></button>'
    return ('<div class="bn-sig-views" role="group" aria-label="Map view">'
            + btn("us", "US") + btn("world", "World") + btn("conflicts", "Conflicts")
            + '</div><p class="bn-sig-counts" aria-live="polite"></p>')

# Homepage shell. The map library, stylesheet and world file load only when the card nears the viewport.
HOME_BOOT = """<script>(function(){var el=document.getElementById("bn_sig");if(!el)return;
function css(h){var l=document.createElement("link");l.rel="stylesheet";l.href=h;document.head.appendChild(l)}
function js(src,fn){var s=document.createElement("script");s.src=src;s.onload=fn;s.onerror=fn;document.head.appendChild(s)}
function load(){if(el.getAttribute("data-on"))return;el.setAttribute("data-on","1");
css("/api/signal/app.css");if(!(window.L&&L.map))css("/api/signal/leaflet.css");
function boot(){js("/api/signal/app.js",function(){if(window.BNSignal)BNSignal.mount(el);
else{var n=document.getElementById("bn_sig_note");if(n)n.textContent="The map could not load.";}})}
if(window.L&&L.map)boot();else js("/api/signal/leaflet.js",boot)}
function go(){if(window.requestIdleCallback)requestIdleCallback(load,{timeout:1200});else setTimeout(load,250)}
if(!("IntersectionObserver" in window)){go();return}
var io=new IntersectionObserver(function(es){if(es.some(function(e){return e.isIntersecting})){io.disconnect();go()}},{rootMargin:"160px"});
io.observe(el)})();</script>"""

def home_section():
    """Homepage card. Clicking the map (not a dot) opens /map. The script does not fetch until the card is near view."""
    return f'''<section class="bna-sec" aria-labelledby="bn_sig_h"><div class="bna-wrap">
<article class="bn-sig" id="bn_sig" data-embed="1">
<div class="bn-sig-cardhead"><div><h2 id="bn_sig_h">Global signal map</h2>
<p class="bn-sig-note" id="bn_sig_note">Wire and Watchlist</p></div>
<div class="bn-sig-side"><a class="bn-sig-open" href="/map">Open the map</a></div></div>
{search_html()}
{cats_html()}
{SR}
<div class="bn-sig-tools">{views_html()}</div>
<div id="bn_sig_map" class="bn-sig-map" role="group" aria-label="World map of Wire and Watchlist stories. US is the starting view."></div>
</article></div></section>
{HOME_BOOT}'''

def _pick(qs, key, allowed, default):
    v = (qs.get(key) or [default])[0]
    return v if v in allowed else default

def page(qs):
    rank = _pick(qs, "rank", ("", "0", "4", "7"), "")
    win = _pick(qs, "window", ("24", "72", "168"), "168")
    view = _pick(qs, "view", ("us", "world", "conflicts"), "us")
    topic = (qs.get("topic") or [""])[0][:80]
    if topic and not re.fullmatch(r"[A-Za-z0-9 /&+\-]{1,80}", topic): topic = ""
    topic_opt = f'<option value="{E(topic)}" selected>{E(topic)}</option>' if topic else ""
    def sel(value, cur): return " selected" if value == cur else ""
    try:
        import sitenav, sitenav_ui
        top = sitenav.header_html("")
        theme = sitenav_ui.THEME_SCRIPT
    except Exception:
        top = '<header class="bn-hd"><a href="/">BLACKOUT.NETWORK</a></header>'
        theme = ""
    title = "Global signal map | BLACKOUT.NETWORK"
    desc = "Wire and Watchlist stories that already have coordinates, on the same world map as the control panel."
    return f'''<!doctype html><html lang="en" class="bn-map-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{theme}
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="https://blackout.network/map">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="https://blackout.network/map"><meta property="og:type" content="website">
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/leaflet.css"><link rel="stylesheet" href="/api/signal/app.css">
</head><body>
<a class="bn-sig-skip" href="#bn_sig_map">Skip to the map</a>
{top}
<div id="bn_map_page" class="bn-map-page" data-embed="0">
<div class="bn-sig-bar"><div class="bn-sig-titles"><h1 id="bn_sig_h">Global signal map</h1>
<p class="bn-sig-note" id="bn_sig_note">Wire and Watchlist</p></div>
{search_html()}
{cats_html()}
{SR}
<div class="bn-sig-tools">{views_html(view)}</div>
<label>Topic <select id="bn_sig_topic" aria-label="Topic"><option value="">All topics</option>{topic_opt}</select></label>
<label>Rank <select id="bn_sig_rank" aria-label="Rank">
<option value=""{sel("", rank)}>All ranks</option>
<option value="7"{sel("7", rank)}>High 7–10</option>
<option value="4"{sel("4", rank)}>Elevated 4–6</option>
<option value="0"{sel("0", rank)}>Low 0–3</option>
</select></label>
<label>Window <select id="bn_sig_win" aria-label="Time window">
<option value="24"{sel("24", win)}>24 hours</option>
<option value="72"{sel("72", win)}>3 days</option>
<option value="168"{sel("168", win)}>7 days</option>
</select></label>
</div>
<div id="bn_sig_map" class="bn-sig-map" role="group" aria-label="World map. Hover or tap a dot for the headline, rank and time."></div>
<noscript><p class="bn-sig-note">The map needs JavaScript. <a href="/#wire">The Wire</a> lists the same stories.</p></noscript>
</div>
<script src="/api/signal/leaflet.js"></script><script src="/api/signal/app.js"></script>
<script>if(window.BNSignal)BNSignal.mount(document.getElementById("bn_map_page"));</script>
</body></html>'''

def _stored_coord(lat, lon):
    if lat is None or lon is None or lat == "" or lon == "": return None
    try: lat, lon = float(lat), float(lon)
    except (TypeError, ValueError): return None
    if lat != lat or lon != lon: return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): return None
    return round(lat, 4), round(lon, 4)

_POINTS = {"t": 0.0, "v": None}

def points_payload():
    """Read-only. Same Wire and Watchlist rows the public feed shows, plus offline inferred dots."""
    import json, sqlite3, time
    from datetime import datetime, timezone, timedelta
    now = time.time()
    if _POINTS["v"] is not None and now - _POINTS["t"] < 30: return _POINTS["v"]
    import signal_place
    path = os.path.join(BASE, "blackout.db")
    rows = []
    if os.path.isfile(path):
        cut = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=8)
        c.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in c.execute(
                """SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated,
                          rank, links, watchlist, brief FROM clusters
                   WHERE watchlist IN (0, 1) AND COALESCE(event_time, first_seen)>=?""", (cut,))]
        finally:
            c.close()
    import geo
    points, stored, inferred, unmapped = [], 0, 0, 0
    for r in rows:
        if int(r.get("watchlist") or 0) not in (0, 1): continue
        try: links = json.loads(r.get("links") or "[]")
        except Exception: links = []
        if not isinstance(links, list): links = []
        coord = _stored_coord(r.get("lat"), r.get("lon"))
        hit = signal_place.infer(signal_place.story_text(r.get("title"), r.get("location"), r.get("brief")))
        specific = hit and hit.get("precision") in ("city", "facility", "state", "region")
        # A named city or base beats a stored country centroid. A real nearby coordinate stays.
        if coord and specific and geo.hav(coord[0], coord[1], hit["lat"], hit["lon"]) > 200:
            coord = None
        exact, place, precision, approximate, cc = True, "", "point", False, ""
        if coord and not (specific and coord is None):
            lat, lon = coord
            stored += 1
            if hit and not specific:
                place, cc = hit.get("place") or "", hit.get("cc") or ""
        elif hit:
            lat, lon = hit["lat"], hit["lon"]
            precision = hit.get("precision") or ""
            place = hit.get("place") or ""
            cc = hit.get("cc") or ""
            approximate = bool(hit.get("approximate")) or precision in ("country", "region")
            exact = not approximate
            inferred += 1
        else:
            unmapped += 1
            continue
        points.append({
            "cluster_id": r.get("cluster_id"), "title": r.get("title") or "", "rank": int(r.get("rank") or 0),
            "category": r.get("category") or "", "event_time": r.get("event_time") or r.get("first_seen") or r.get("updated") or "",
            "lat": lat, "lon": lon, "exact": exact, "place": place, "precision": precision,
            "approximate": approximate, "cc": cc, "watchlist": int(r.get("watchlist") or 0),
            "links": [{"url": (l or {}).get("url"), "source": (l or {}).get("source")} for l in links[:5] if isinstance(l, dict)],
        })
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"points": points, "stored": stored, "inferred": inferred, "shown": len(points),
            "unmapped": unmapped, "generated": generated}
    _POINTS.update(t=now, v=body)
    return body

def handle_get(path, qs):
    if path in ("/map", "/map/"):
        return 200, page(qs or {}), "text/html"
    if path == "/api/signal/points":
        return 200, points_payload()
    if path.startswith("/api/signal/"):
        name = path[len("/api/signal/"):]
        if name not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, name), "rb") as fh:
            return 200, fh.read(), FILES[name]
    return 404, {"error": "not found"}
