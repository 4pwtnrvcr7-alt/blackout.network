"""Global signal map. Public homepage card plus /map.

Draws the Control panel v2 map: Leaflet, the bundled Natural Earth world.geojson, and the same
.signal dots (panel/app.js renderMap, panel/style.css). The panel's OpenFreeMap / MapLibre tile
layer is not used, so there is no tile server and no API key.

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
LEGEND = ('<p class="bn-sig-leg"><i class="lo"></i>Low<i class="md"></i>Elevated<i class="hi"></i>High</p>'
          '<p class="bn-sig-sr">Low is rank 0 to 3, elevated is rank 4 to 6, and high is rank 7 to 10. Red is only rank 7 and above.</p>')

def views_html(active="us", counts=None):
    counts = counts or {}
    def btn(name, label):
        on = "true" if name == active else "false"
        return f'<button type="button" data-view="{name}" aria-pressed="{on}">{label} <b data-n="{name}">{int(counts.get(name) or 0)}</b></button>'
    return ('<div class="bn-sig-views" role="group" aria-label="Map view">'
            + btn("us", "US") + btn("world", "World") + btn("conflicts", "Conflicts")
            + '</div><p class="bn-sig-counts" aria-live="polite"></p>')

# Homepage shell. The page ships a first batch of dots (inline JSON + a static SVG preview drawn server-side, so dots show on first
# paint). The map library starts loading as soon as the page is idle (no longer only when the card nears the viewport); the card
# coming into view starts it at once. The rest of the dots then load in the background.
HOME_BOOT = """<script>(function(){var el=document.getElementById("bn_sig");if(!el)return;
var pre=el.querySelector(".bn-sig-pre");if(pre){var vb=pre.viewBox&&pre.viewBox.baseVal;function sz(){var r=pre.getBoundingClientRect();if(!vb||!r.width)return;
var k=Math.min((r.width)/vb.width,(r.height)/vb.height)||1;pre.querySelectorAll("circle").forEach(function(c){c.setAttribute("r",(6/k).toFixed(3))});
pre.querySelectorAll("path").forEach(function(p){p.style.strokeWidth=(.6/k).toFixed(3)})}sz();addEventListener("resize",sz)}
function css(h){var l=document.createElement("link");l.rel="stylesheet";l.href=h;document.head.appendChild(l)}
function js(src,fn){var s=document.createElement("script");s.src=src;s.onload=fn;s.onerror=fn;document.head.appendChild(s)}
function load(){if(el.getAttribute("data-on"))return;el.setAttribute("data-on","1");
css("/api/signal/app.css");if(!(window.L&&L.map))css("/api/signal/leaflet.css");
function boot(){js("/api/signal/app.js",function(){if(window.BNSignal&&window.L&&L.map)return BNSignal.mount(el);fail()})}
if(window.L&&L.map)boot();else js("/api/signal/leaflet.js",boot)}
var tries=0;function fail(){var n=document.getElementById("bn_sig_note");if(tries++<2){el.removeAttribute("data-on");setTimeout(load,4000*tries);return}
if(n)n.textContent=el.querySelector(".bn-sig-pre circle")?"Top stories shown. Open the map for every dot.":"The map could not load."}
if(window.requestIdleCallback)requestIdleCallback(load,{timeout:1500});else setTimeout(load,300);
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){if(es.some(function(e){return e.isIntersecting})){io.disconnect();load()}},{rootMargin:"600px"});io.observe(el)}})();</script>"""

def home_section():
    """Homepage card. Clicking the map (not a dot) opens /map. First dots are inline (seed JSON + SVG preview); the rest load after."""
    seed, svg, counts, note = "", "", {}, "Wire and Watchlist"
    try:
        pts = seed_points()
        if pts:
            # the view buttons show the preview set's counts until the live map has loaded every dot
            counts = {"us": sum(1 for p in pts if _in_us(p)), "world": len(pts),
                      "conflicts": sum(1 for p in pts if str(p.get("category") or "").lower() == "war/conflict")}
            note = "Loading live map\u2026"
            import json as _json
            seed = '<script type="application/json" id="bn_sig_seed">' + _json.dumps(pts, separators=(",", ":")).replace("</", "<\\/") + "</script>"
            svg = preview_svg(pts)
    except Exception:
        seed, svg, counts, note = "", "", {}, "Wire and Watchlist"
    return f'''<section class="bna-sec" aria-labelledby="bn_sig_h"><div class="bna-wrap">
<article class="bn-sig" id="bn_sig" data-embed="1">
<div class="bn-sig-cardhead"><div><h2 id="bn_sig_h">Global signal map</h2>
<p class="bn-sig-note" id="bn_sig_note" data-done="Wire and Watchlist" aria-live="polite">{note}</p></div>
<div class="bn-sig-side">{LEGEND}<a class="bn-sig-open" href="/map">Open the map</a></div></div>
<div class="bn-sig-tools">{views_html(counts=counts)}</div>
<div id="bn_sig_map" class="bn-sig-map" role="group" aria-label="World map of Wire and Watchlist stories. US is the starting view." style="background:#0b1220;position:relative;overflow:hidden">{svg}</div>
{seed}</article></div></section>
{HOME_BOOT}'''

# ---------------------------------------------------------------- first batch of dots (homepage speed, Nov 8)
SEED_US, SEED_WORLD = 30, 15
US_VIEW = (24.5, -125.0, 49.5, -66.5)          # the same LOWER48 bounds app.js fits on load (padding 12 px)

def _in_us(p):
    if str(p.get("cc") or "").upper() == "US": return True
    lat, lon = float(p["lat"]), float(p["lon"])
    return (24.5 <= lat <= 49.5 and -125 <= lon <= -66.5) or (51 <= lat <= 72 and -170 <= lon <= -129) or (18.5 <= lat <= 22.5 and -161 <= lon <= -154) or (17.5 <= lat <= 18.6 and -67.5 <= lon <= -65)

def seed_points():
    """Top dots for the first paint: the 30 highest-ranked US dots (the starting view) and the 15 highest-ranked elsewhere,
    last 7 days, newest first within a rank. Small (about 10 KB); the rest arrive from /api/signal/points."""
    import time as _t
    body = _points_cached(wait=1.5)
    if not body: return []
    from datetime import datetime as _dt, timezone as _tz
    cut = _t.time() - 7 * 86400
    def ts(p):
        try: return _dt.strptime(str(p.get("event_time") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_tz.utc).timestamp()
        except Exception: return 0
    pts = [p for p in body.get("points") or [] if p.get("lat") is not None and ts(p) >= cut]
    pts.sort(key=lambda p: (-(p.get("rank") or 0), -ts(p)))
    us = [p for p in pts if _in_us(p)][:SEED_US]; world = [p for p in pts if not _in_us(p)][:SEED_WORLD]
    keep = ("cluster_id", "title", "rank", "category", "event_time", "lat", "lon", "exact", "place", "precision", "approximate", "cc", "watchlist")
    return [dict({k: p.get(k) for k in keep}, links=(p.get("links") or [])[:1]) for p in us + world]

def _merc(lat, lon):
    import math
    s = math.sin(max(-85.0, min(85.0, lat)) * math.pi / 180)
    return (lon + 180) / 360 * 360, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * 360

_OUTLINE = {"v": None}
def _outline():
    """World outline paths clipped to the US starting view, projected like Leaflet (Web Mercator). Built once."""
    if _OUTLINE["v"] is None:
        import json as _json
        x0, y0 = _merc(US_VIEW[2] + 12, US_VIEW[1] - 20); x1, y1 = _merc(US_VIEW[0] - 12, US_VIEW[3] + 20)
        with open(os.path.join(STATIC, "world.geojson"), encoding="utf-8") as fh: feats = _json.load(fh)["features"]
        out = []
        for f in feats:
            g = f.get("geometry") or {}; polys = g.get("coordinates") or []
            if g.get("type") == "Polygon": polys = [polys]
            for poly in polys:
                for ring in poly[:1]:
                    pts = [_merc(la, lo) for lo, la in ring]
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
                    out.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + "Z")
        _OUTLINE["v"] = "".join(out)
    return _OUTLINE["v"]

def preview_svg(pts):
    """Static first-paint map: the US view with the seed dots, drawn exactly where Leaflet will put them. app.js removes it
    once the live map has drawn its first dots. Decorative (the live map carries the accessible labels)."""
    x0, y0 = _merc(US_VIEW[2], US_VIEW[1]); x1, y1 = _merc(US_VIEW[0], US_VIEW[3])
    col = lambda r: "#FF4D4F" if r >= 7 else "#F5A524" if r >= 4 else "#55b7ff"
    dots = []
    for p in pts:
        if not _in_us(p): continue
        x, y = _merc(float(p["lat"]), float(p["lon"]))
        if not (x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1): continue
        ap = p.get("exact") is False or p.get("approximate") or p.get("precision") == "country"
        dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.6" fill="{col(int(p.get("rank") or 0))}"' + (' fill-opacity=".72" stroke="#0b1220" stroke-width=".08"' if ap else "") + "/>")
    return (f'<svg class="bn-sig-pre" aria-hidden="true" focusable="false" viewBox="{x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f}" preserveAspectRatio="xMidYMid meet" '
            'style="position:absolute;left:12px;top:12px;width:calc(100% - 24px);height:calc(100% - 24px);overflow:visible;pointer-events:none">'
            f'<path d="{_outline()}" fill="#192538" fill-opacity=".7" stroke="#364158" stroke-width=".05"/>{"".join(dots)}</svg>')

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
{LEGEND}
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
import threading as _th
_PLOCK = _th.Lock(); _PREB = {"t": None}

def _points_rebuild():
    if not _PLOCK.acquire(blocking=False): return
    try: _build_points()
    except Exception: pass
    finally: _PLOCK.release()

def _kick():
    t = _PREB["t"]
    if t is not None and t.is_alive(): return t
    t = _th.Thread(target=_points_rebuild, name="bn-sig-points", daemon=True); _PREB["t"] = t; t.start()
    return t

def _points_cached(wait=0.0):
    """Last points payload without blocking a page: stale copies are served while one background build refreshes them."""
    import time
    v = _POINTS["v"]
    if v is not None:
        if time.time() - _POINTS["t"] >= 30: _kick()
        return v
    t = _kick()
    if wait and t is not None: t.join(wait)
    return _POINTS["v"]

def points_payload():
    """Read-only. Same Wire and Watchlist rows the public feed shows, plus offline inferred dots.
    Fresh for 30 s; after that the last copy is returned at once while one background build refreshes it (was: every
    request after 30 s rebuilt it inline, about 1 s on Render)."""
    v = _points_cached()
    if v is not None: return v
    with _PLOCK:
        if _POINTS["v"] is not None: return _POINTS["v"]
        return _build_points()

def _build_points():
    import json, sqlite3, time
    from datetime import datetime, timezone, timedelta
    now = time.time()
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
