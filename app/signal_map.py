"""Global signal map. Public homepage card plus /map.

Draws the Control panel v2 map: Leaflet, the bundled Natural Earth world.geojson, and the same
.signal dots (panel/app.js renderMap, panel/style.css). The panel's OpenFreeMap / MapLibre tile
layer is not used, so there is no tile server and no API key.

Dots are Wire and Watchlist stories (watchlist 0 and 1). A stored coordinate is used when
the row has one. Otherwise a place is inferred offline from the headline and location text
(signal_place.py, the bundled gazetteer). Nothing here calls a geocoder, scores, or writes.

Vendored in signal_map_static/: Leaflet 1.9.4 (BSD-2-Clause) and Natural Earth 110m admin-0
(public domain), copied from the panel package, and Natural Earth 110m admin-1 US state lines
(us_states.geojson, public domain, properties trimmed to the name). MapLibre is not shipped.
"""
import os, re
import html as _html
import threading as _th

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "signal_map_static")
FILES = {
    "app.js": "application/javascript",
    "app.css": "text/css",
    "leaflet.js": "application/javascript",
    "leaflet.css": "text/css",
    "world.geojson": "application/json",
    "us_states.geojson": "application/json",
    # Nov 17 2026 full-screen heat map (MapLibre GL JS 5.24.1, BSD-3-Clause, vendored; OpenFreeMap vector tiles)
    "maplibre-gl.js": "application/javascript",
    "maplibre-gl.css": "text/css",
    "maplibre-LICENSE.txt": "text/plain",
    "map2.js": "application/javascript",
    "map2.css": "text/css",
    "map2_loader.js": "application/javascript",   # Nov 20 2026 "Signal acquisition" loader (pt1675u)
}
E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)
LEGEND = ('<p class="bn-sig-leg"><i class="lo"></i>Low<i class="md"></i>Elevated<i class="hi"></i>High</p>'
          '<p class="bn-sig-sr">Low is rank 0 to 3, elevated is rank 4 to 6, and high is rank 7 to 10. Red is only rank 7 and above.</p>')

def _display_cat(title, category):
    try:
        import story_display as SD
        return SD.display_category(title, category)
    except Exception:
        return category or ""


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

_SEED = {"t": 0.0, "v": None}
_SEED_LOCK = _th.Lock()

def _seed_path():
    """Persisted verified seed so a fresh worker can inline dots before the full points rebuild finishes."""
    d = os.environ.get("BN_STATE_DIR") or os.path.join(BASE, "data")
    try: os.makedirs(d, exist_ok=True)
    except Exception: d = "/tmp"
    return os.path.join(d, "signal_seed.json")

def _slice_seed(body):
    """Top 30 US + 15 world from an already-verified points payload. Never re-geocodes."""
    import time as _t
    from datetime import datetime as _dt, timezone as _tz
    if not body: return []
    cut = _t.time() - 7 * 86400
    def ts(p):
        try: return _dt.strptime(str(p.get("event_time") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_tz.utc).timestamp()
        except Exception: return 0
    pts = [p for p in body.get("points") or [] if p.get("lat") is not None and ts(p) >= cut]
    pts.sort(key=lambda p: (-(p.get("rank") or 0), -ts(p)))
    us = [p for p in pts if _in_us(p)][:SEED_US]; world = [p for p in pts if not _in_us(p)][:SEED_WORLD]
    keep = ("cluster_id", "title", "rank", "category", "event_time", "lat", "lon", "exact", "place", "precision", "approximate", "cc", "watchlist")
    return [dict({k: p.get(k) for k in keep}, links=(p.get("links") or [])[:1]) for p in us + world]

def _publish_seed(pts):
    """Memory + disk. Disk lets the next cold worker serve dots without waiting on PIP over every Wire row."""
    import json as _json, time as _t
    pts = list(pts or [])
    _SEED.update(t=_t.time(), v=pts)
    try:
        p = _seed_path(); tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            _json.dump({"t": _SEED["t"], "points": pts}, fh, separators=(",", ":"))
        os.replace(tmp, p)
    except Exception:
        pass
    return pts

def _load_seed_disk():
    import json as _json
    try:
        with open(_seed_path(), encoding="utf-8") as fh:
            data = _json.load(fh)
        pts = data.get("points") if isinstance(data, dict) else None
        if isinstance(pts, list) and pts:
            _SEED.update(t=float(data.get("t") or 0), v=pts)
            return pts
    except Exception:
        pass
    return None

def seed_points():
    """Top dots for the first paint: the 30 highest-ranked US dots (the starting view) and the 15 highest-ranked elsewhere,
    last 7 days, newest first within a rank. Small (about 10 KB); the rest arrive from /api/signal/points.

    Seed is precomputed when the verified points cache rebuilds (and persisted to disk). The homepage never waits on
    point-in-polygon / gazetteer over the full Wire — that work stays on the background rebuild."""
    import time as _t
    pts = _SEED["v"]
    if pts is None:
        pts = _load_seed_disk()
    # Stale or missing full payload: refresh in the background; still serve the last seed immediately.
    body = _points_cached(wait=0)
    if body is None or (_t.time() - _POINTS["t"] >= 30):
        _kick()
    if pts is not None:
        return pts
    # Absolute cold (new worker, empty disk): build a small verified seed once, then let the full rebuild catch up.
    with _SEED_LOCK:
        if _SEED["v"] is not None:
            return _SEED["v"]
        body = _points_cached(wait=0)
        if body:
            return _publish_seed(_slice_seed(body))
        try:
            fast = _build_points(limit=150)  # same verify path, capped rows
            return _SEED["v"] or _slice_seed(fast)
        except Exception:
            _kick()
            return []

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
    col = lambda r: "#FF4D4F" if r >= 7 else "#C9CDD3" if r >= 4 else "#6B7076"   # Push G: rank option A
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
<meta property="og:url" content="https://blackout.network/map"><meta property="og:type" content="website"><meta property="og:image" content="https://blackout.network/og/map.png?v=5"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{E(title)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://blackout.network/og/map.png?v=5"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}">
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/bn-refresh.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/leaflet.css"><link rel="stylesheet" href="/api/signal/app.css">
<script src="/sitenav.js" defer></script><script src="/bn-refresh.js" defer></script>
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
<noscript><p class="bn-sig-note">The map needs JavaScript. <a href="/wire">The Wire</a> lists the same stories.</p></noscript>
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

def _build_points(limit=None):
    """Rebuild verified points. limit=N builds only the top N by rank (cold seed path); None = full Wire window."""
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
            q = """SELECT cluster_id, title, category, location, lat, lon, event_time, first_seen, updated,
                          rank, links, watchlist, brief FROM clusters
                   WHERE watchlist IN (0, 1) AND COALESCE(event_time, first_seen)>=?
                   ORDER BY rank DESC, COALESCE(event_time, first_seen) DESC"""
            if limit:
                rows = [dict(r) for r in c.execute(q + " LIMIT ?", (cut, int(limit)))]
            else:
                rows = [dict(r) for r in c.execute(q, (cut,))]
        finally:
            c.close()
    import geo, map_pins

    # Same headline+state resolver as the Wire map (v12, pt1761u), including sibling counties.
    ha_places = {}
    try:
        import heat_all as HA
        items = [{"id": r.get("cluster_id"), "title": r.get("title") or "", "loc": r.get("location") or "",
                  "lat": r.get("lat"), "lon": r.get("lon"), "a": 0, "category": r.get("category") or "",
                  "brief": r.get("brief") or "", "links": r.get("links") or "[]"} for r in rows]
        grew = HA._geo_rows(it["id"] for it in items if it["id"])
        places = HA._stored_places(items, grew)   # stored once (story_places.db), never re-geocoded per request
        ha_places = {it["id"]: p for it, p in zip(items, places)}
    except Exception:
        ha_places = {}

    # Pass 1: resolve each story. Country-only and other unverified pins stay off the map (pt1762u).
    drafted, stored, inferred, unmapped, unverified = [], 0, 0, 0, 0
    for r in rows:
        if int(r.get("watchlist") or 0) not in (0, 1): continue
        try: links = json.loads(r.get("links") or "[]")
        except Exception: links = []
        if not isinstance(links, list): links = []
        story = signal_place.story_text(r.get("title"), r.get("location"), r.get("brief"))
        named = signal_place.named_countries(story)
        prefer = named[0] if len(named) == 1 else None
        hit = signal_place.infer(story, prefer_cc=prefer)
        coord = _stored_coord(r.get("lat"), r.get("lon"))
        hp = ha_places.get(r.get("cluster_id"))
        if hp and hp.get("prec") in map_pins.SPECIFIC and hp.get("lat") is not None and hp.get("lon") is not None:
            hit = {"lat": hp["lat"], "lon": hp["lon"], "place": hp.get("place") or "",
                   "precision": hp.get("prec") or "city", "cc": hp.get("cc") or "", "approximate": False}
            # A stored cluster coordinate that contradicts the headline place is ignored.
            if coord and geo.hav(coord[0], coord[1], hp["lat"], hp["lon"]) > 50:
                coord = None
        specific = hit and hit.get("precision") in ("city", "facility", "state", "region")
        # Stored coord must sit inside the story's country when we know one.
        expected_cc = (hit or {}).get("cc") or prefer
        if coord and expected_cc and not signal_place.in_country(coord[0], coord[1], expected_cc):
            coord = None
        # A named city or base beats a stored country centroid far away.
        if coord and specific and geo.hav(coord[0], coord[1], hit["lat"], hit["lon"]) > 200:
            coord = None
        exact, place, precision, approximate, cc = True, "", "point", False, ""
        lat = lon = None
        if coord:
            lat, lon = coord
            # Final PIP gate on stored coords too.
            if expected_cc and not signal_place.in_country(lat, lon, expected_cc):
                unverified += 1
                continue
            stored += 1
            if hit:
                place, cc = hit.get("place") or "", hit.get("cc") or expected_cc or ""
                if not specific:
                    precision = hit.get("precision") or "point"
                    approximate = bool(hit.get("approximate")) or precision in ("country", "region")
                    exact = not approximate
            elif expected_cc:
                cc = expected_cc
        elif hit:
            lat, lon = hit["lat"], hit["lon"]
            precision = hit.get("precision") or ""
            place = hit.get("place") or ""
            cc = hit.get("cc") or expected_cc or ""
            approximate = bool(hit.get("approximate")) or precision in ("country", "region")
            exact = not approximate
            # PIP gate: never plot a point outside the story's country.
            if cc and not signal_place.in_country(lat, lon, cc):
                unverified += 1
                continue
            inferred += 1
        else:
            # Could name a country but not a safe pin → unverified; else unmapped.
            if named:
                unverified += 1
            else:
                unmapped += 1
            continue
        entry = {
            "cluster_id": r.get("cluster_id"), "title": r.get("title") or "", "rank": int(r.get("rank") or 0),
            "category": _display_cat(r.get("title") or "", r.get("category") or ""), "event_time": r.get("event_time") or r.get("first_seen") or r.get("updated") or "",
            "lat": lat, "lon": lon, "exact": exact, "place": place, "precision": precision,
            "approximate": approximate, "cc": cc, "watchlist": int(r.get("watchlist") or 0),
            "links": [{"url": (l or {}).get("url"), "source": (l or {}).get("source")} for l in links[:5] if isinstance(l, dict)],
        }
        # Nov 23 2026 (pt1762u): only a specific, named location is a pin. Country centroids,
        # scattered stand-in cities, low-confidence / ambiguous matches, water, and headline
        # contradictions stay in the lists, not on the map. A city pin whose city is not in the
        # headline is dropped, or moved to a county or state the headline names.
        pin = map_pins.resolve_pin(title=entry["title"], place=entry["place"], precision=entry["precision"],
                                   lat=entry["lat"], lon=entry["lon"], cc=entry["cc"])
        if not pin:
            unverified += 1
            continue
        entry["lat"], entry["lon"] = pin["lat"], pin["lon"]
        if pin.get("place") is not None:
            entry["place"] = pin["place"]
        if pin.get("precision"):
            entry["precision"] = pin["precision"]
        if pin.get("cc"):
            entry["cc"] = pin["cc"]
        drafted.append(entry)
    points = drafted
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"points": points, "stored": stored, "inferred": inferred, "shown": len(points),
            "unmapped": unmapped, "unverified": unverified, "generated": generated}
    # A capped seed build must not overwrite the full points cache (homepage API needs every pin).
    if not limit:
        _POINTS.update(t=now, v=body)
    _publish_seed(_slice_seed(body if not limit else {"points": points}))
    if limit:
        _kick()  # finish the full verified set in the background
    return body

# ---------- Nov 17 2026: full-screen heat map (/map) ----------
# One MapLibre renderer: OpenFreeMap vector base + the heat as a native heatmap layer + rank dots, so heat and map move as one.
# Kill switch: BN_NEW_MAP=0 (or ?classic=1) serves the Leaflet page above unchanged.
def new_map_on():
    return os.environ.get("BN_NEW_MAP", "1") != "0"

_VER = {}
def _v(name):
    """Content hash for ?v= (immutable caching), refreshed when the file changes."""
    import hashlib
    path = os.path.join(STATIC, name)
    try: mt = os.path.getmtime(path)
    except OSError: return "0"
    hit = _VER.get(name)
    if hit and hit[0] == mt: return hit[1]
    with open(path, "rb") as fh: h = hashlib.sha1(fh.read()).hexdigest()[:10]
    _VER[name] = (mt, h)
    return h

def page2(qs):
    rank = _pick(qs, "rank", ("", "0", "4", "7"), "")
    win = _pick(qs, "window", ("24", "72", "168"), "168")
    view = _pick(qs, "view", ("us", "world", "conflicts"), "world")
    topic = (qs.get("topic") or [""])[0][:80]
    if topic and not re.fullmatch(r"[A-Za-z0-9 /&+\-]{1,80}", topic): topic = ""
    try:
        import sitenav, sitenav_ui
        top = sitenav.header_html("")
        theme = sitenav_ui.THEME_SCRIPT
        ref_btn = sitenav_ui.refresh_fill_btn("bnm_ref")
    except Exception:
        top = '<header class="bn-top"><div class="bn-tbar"><a class="bn-logo" href="/"><span class="bnt-wm">blackout.network</span></a></div></header>'
        theme = ""
        ref_btn = ""
    title = "Heat map | BLACKOUT.NETWORK"
    desc = "Full-screen live heat map of ranked alerts from the last 7 days: conflicts, weather and quakes, outbreaks, outages and unrest."
    import json as _json
    cfg = _json.dumps({"rank": rank, "window": win, "view": view, "topic": topic}).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="en" class="bnm-root"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{theme}
<script>document.documentElement.classList.add("bnm-js")</script>
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="https://blackout.network/map">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="https://blackout.network/map"><meta property="og:type" content="website"><meta property="og:image" content="https://blackout.network/og/map.png?v=5"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{E(title)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="https://blackout.network/og/map.png?v=5"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}">
<meta name="theme-color" content="#05060a">
<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin>
<link rel="stylesheet" href="/sitenav.css"><link rel="stylesheet" href="/bn-refresh.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/api/signal/maplibre-gl.css?v={_v("maplibre-gl.css")}"><link rel="stylesheet" href="/api/signal/map2.css?v={_v("map2.css")}">
<script src="/sitenav.js" defer></script><script src="/bn-refresh.js" defer></script>
</head><body class="bnm bn-has-ref" data-bn-map2="1">
<a class="skip" href="#bnm_map">Skip to the map</a>
<div class="bnm-head" id="bnm_head">{top}</div>
<button type="button" class="bnm-x" id="bnm_x" aria-label="Close the map and go back" title="Close map"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
<a class="bnm-mb bn-burger" id="bnm_mb" href="#bn-menu" role="button" aria-label="Open menu" aria-controls="bn-menu" aria-expanded="false" aria-haspopup="dialog" title="Menu"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg><span>Menu</span></a>
<script>/* Nov 17: the header slides (transform), which would clip the fixed full-screen menu; the menu lives on <body> */(function(){{var m=document.getElementById("bn-menu");if(m&&m.parentNode!==document.body)document.body.appendChild(m)}})()</script>
<div class="bnm-edge" id="bnm_edge" aria-hidden="true"></div>
<main id="bnm_main">
<h1 class="bnm-vh">Heat map</h1>
<div id="bnm_map" class="bnm-map" role="region" aria-label="Heat map of ranked alerts. Drag to pan, pinch or scroll to zoom, tap a dot for the headline."></div>
<div class="bnl" id="bnm_ld"><canvas aria-hidden="true"></canvas><div class="bnl-hud">
<p class="bnl-k" aria-hidden="true"><span>Signal acquisition</span><span id="bnl_brg">BRG 000&deg;</span></p>
<ol aria-hidden="true"><li data-s="link"><b>01</b><span>Wire feed</span><em>connecting</em></li><li data-s="exact"><b>02</b><span>Exact places</span><em>waiting</em></li><li data-s="approx"><b>03</b><span>Approximate</span><em>waiting</em></li><li data-s="region"><b>04</b><span>Region only</span><em>waiting</em></li><li data-s="global"><b>05</b><span>No location</span><em>waiting</em></li><li data-s="base"><b>06</b><span>Basemap</span><em>loading</em></li></ol>
<div class="bnl-bar" aria-hidden="true"><i></i></div><p class="bnl-msg" id="bnl_msg" role="status" hidden></p></div></div>
<div class="bnm-top"><div class="bnm-chip" id="bnm_chip"><i></i><span id="bnm_count" aria-live="polite">Loading alerts…</span></div><span class="bnm-rt" id="bnm_rt" hidden aria-live="polite"></span><span class="bnm-upw" id="bnm_up"></span>{ref_btn}</div>
<div class="bnm-ctl" id="bnm_ctl">
<button type="button" class="bnm-b" id="bnm_zin" aria-label="Zoom in"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v12M6 12h12"/></svg></button>
<button type="button" class="bnm-b" id="bnm_zout" aria-label="Zoom out"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg></button>
</div>
<button type="button" class="bnm-gbtn" id="bnm_gbtn" hidden aria-controls="bnm_card" title="Wire alerts that name no place"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.9 5.2 3.9 8.5s-1.3 6.1-3.9 8.5M12 3.5C9.4 5.9 8.1 8.7 8.1 12s1.3 6.1 3.9 8.5"/></svg><span>No location</span><b id="bnm_gn">0</b></button>
<button type="button" class="bnm-fbtn" id="bnm_fbtn" aria-expanded="false" aria-controls="bnm_panel"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M7 12h10M10 17h4"/></svg><span>Filters</span><b id="bnm_fn" hidden></b></button>
<section class="bnm-panel" id="bnm_panel" hidden aria-label="Map filters and legend">
<div class="bnm-grab" aria-hidden="true"></div>
<div class="bnm-ph"><p class="bnm-eb">Heat map</p><button type="button" class="bnm-pclose" id="bnm_pclose" aria-label="Close filters"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
<div class="bnm-row"><span class="bnm-l">View</span><div class="bnm-seg" data-k="view" role="group" aria-label="View">
<button type="button" data-v="world">World <em data-n="world"></em></button><button type="button" data-v="us">U.S. <em data-n="us"></em></button><button type="button" data-v="conflicts">Conflicts <em data-n="conflicts"></em></button></div></div>
<div class="bnm-row"><span class="bnm-l">Rank</span><div class="bnm-seg" data-k="rank" role="group" aria-label="Rank">
<button type="button" data-v="">All</button><button type="button" data-v="7">High 7–10</button><button type="button" data-v="4">Elevated 4–6</button><button type="button" data-v="0">Calm 0–3</button></div></div>
<div class="bnm-row"><span class="bnm-l">Window</span><div class="bnm-seg" data-k="window" role="group" aria-label="Time window">
<button type="button" data-v="24">24 hours</button><button type="button" data-v="72">3 days</button><button type="button" data-v="168">7 days</button></div></div>
<div class="bnm-row"><label class="bnm-l" for="bnm_topic">Topic</label><select id="bnm_topic"><option value="">All topics</option></select></div>
<div class="bnm-row bnm-lyr"><span class="bnm-l">Layers</span><label><input type="checkbox" id="bnm_lh" checked> Heat</label><label><input type="checkbox" id="bnm_ld" checked> Alert dots</label></div>
<div class="bnm-leg"><div class="bnm-ramp" aria-hidden="true"></div><div class="bnm-rl"><span>Fewer, lower-ranked</span><span>More, higher-ranked</span></div>
<div class="bnm-key"><span class="c">Calm 0–3</span><span class="e">Elevated 4–6</span><span class="h">High 7–10</span></div>
<p class="bnm-note" id="bnm_note">Heat weighs each placed alert by its rank. Solid dots are exact places, hollow rings are approximate (usually a country centre), labeled rings are region only. Tap any of them for the headline, rank and sources.</p>
<p class="bnm-note" id="bnm_cov"></p></div>
<div class="bnm-links"><a href="/wire">The Wire</a><a href="/scoring">How we score</a><button type="button" id="bnm_report">Report a problem</button></div>
<p class="bnm-attr">Map data &copy; <a href="https://www.openstreetmap.org/copyright" rel="noopener" target="_blank">OpenStreetMap</a> contributors · <a href="https://openfreemap.org" rel="noopener" target="_blank">OpenFreeMap</a> · <a href="https://openmaptiles.org/" rel="noopener" target="_blank">OpenMapTiles</a></p>
</section>
<aside class="bnm-card" id="bnm_card" hidden aria-live="polite"></aside>
<noscript><p class="bnm-nojs">The map needs JavaScript. <a href="/wire">The Wire</a> lists the same stories.</p></noscript>
</main>
<script>window.BNM_CFG={cfg};</script>
<script src="/api/signal/map2_loader.js?v={_v("map2_loader.js")}" defer></script><script src="/api/signal/maplibre-gl.js?v={_v("maplibre-gl.js")}" defer></script><script src="/api/rt/client.js?v={_rt_v()}" defer></script><script src="/api/signal/map2.js?v={_v("map2.js")}" defer></script>
</body></html>'''

def _rt_v():
    try: return str(int(os.path.getmtime(os.path.join(os.path.dirname(os.path.abspath(__file__)), "realtime_static", "client.js")))) + "r"
    except OSError: return "0"

_HEAT = {"t": 0.0, "v": None}
_HLOCK = _th.Lock()
_HBUILD = _th.Lock()     # single flight: one heat build at a time

def _drop_unplaced(body):
    """Nov 23 2026 (Matt pt1781u): a story with no map position is not sent to the map at all (no tray, no chip).
    coverage keeps the server-side counts for the location guard; the map never shows them."""
    if not body or not body.get("rows"): return body
    cols = body.get("cols") or []
    try: i_lat, i_lon = cols.index("lat"), cols.index("lon")
    except ValueError: return body
    body = dict(body)
    body["rows"] = [r for r in body["rows"] if r[i_lat] is not None and r[i_lon] is not None]
    return body

def heat_payload(force=False):
    """Stale-while-revalidate: a cached body is returned at once and a stale one is rebuilt in the background (one build at a time).
    Only the very first request after boot waits for a build. force=True (Refresh / ?fresh=1) marks the slot stale,
    bumps the generation, and waits for a new build so a tap is never served a 60 s-old copy."""
    import time
    if force:
        with _HLOCK:
            _HEAT["t"] = 0
            _HEAT["g"] = _HEAT.get("g", 0) + 1
        _heat_rebuild()
        with _HLOCK:
            if _HEAT["v"] is not None:
                return _HEAT["v"]
    with _HLOCK:
        v, fresh = _HEAT["v"], time.time() - _HEAT["t"] < 60
    if v is not None:
        if not fresh and not _HBUILD.locked():
            _th.Thread(target=_heat_rebuild, name="heat_rebuild", daemon=True).start()
        return v
    _heat_rebuild()
    with _HLOCK:
        return _HEAT["v"]

def _heat_rebuild():
    if not _HBUILD.acquire(blocking=False):
        _HBUILD.acquire(); _HBUILD.release(); return      # someone else is building: wait for it
    try:
        body = _heat_build()
        with _HLOCK:
            _HEAT["v"] = body
    finally:
        _HBUILD.release()

def _heat_build():
    """Slim, read-only rows for the heat map: every Wire item of the last 7 days with its best position (heat_all.build); if that fails,
    the Heat Map tab's located alerts (heatmap.data, 7 days, geo.db), else /map's points.
    Cached 60 s in one slot. Never writes, never geocodes, never scores."""
    import time, sys
    with _HLOCK:
        g0 = _HEAT.get("g", 0)   # Nov 21 2026: realtime.bust() bumps "g"; a build that started before a bust must not cache its older rows
    body = None
    # Nov 20 2026 (Matt pt1672u): every Wire item, placed at its best honest precision (heat_all.py). BN_MAP_ALL=0 restores the located-only feed.
    try:
        import heat_all
        if heat_all.on(): body = heat_all.build()
        if body is not None:
            import map_pins
            body = map_pins.filter_heat_body(body)
    except Exception as ex:
        print("signal_map heat: every-Wire-item feed failed, using located-only:", ex, flush=True); body = None
    if body is not None:
        body = _drop_unplaced(body)
        with _HLOCK:
            _HEAT["t"] = time.time() if _HEAT.get("g", 0) == g0 else 0.0     # a bust during the build: serve it, rebuild next request
        return body
    try:
        hm = sys.modules.get("heatmap")
        if hm is None:
            import heatmap as hm
        d = hm.data()
        rows = []
        for x in d.get("items") or []:
            try: lat, lon = round(float(x["lat"]), 4), round(float(x["lon"]), 4)
            except Exception: continue
            ln = (x.get("links") or [{}])[0] or {}
            rows.append([x.get("id"), lat, lon, int(x.get("rank") or 0), x.get("cat") or "", x.get("t") or "",
                         (x.get("title") or "")[:220], x.get("place") or x.get("cn") or "", x.get("prec") or "", int(x.get("watch") or 0),
                         ln.get("s") or "", ln.get("u") or "", x.get("cc") or "", int(x.get("fam") or 0)])
        cov = d.get("coverage") or {}
        body = {"generated": d.get("generated"), "source": "heatmap", "window_days": d.get("window_days") or 7,
                "coverage": {"located": cov.get("located"), "total": cov.get("total"), "pct": cov.get("pct")}, "rows": rows}
    except Exception as ex:
        print("signal_map heat: falling back to points:", ex, flush=True)
    if body is None:
        p = points_payload() or {}
        rows = []
        for x in p.get("points") or []:
            ln = (x.get("links") or [{}])[0] or {}
            rows.append([x.get("cluster_id"), x.get("lat"), x.get("lon"), int(x.get("rank") or 0), x.get("category") or "", x.get("event_time") or "",
                         (x.get("title") or "")[:220], x.get("place") or "", x.get("precision") or "", int(x.get("watchlist") or 0),
                         ln.get("source") or "", ln.get("url") or "", x.get("cc") or "", 0])
        body = {"generated": p.get("generated"), "source": "points", "window_days": 7,
                "coverage": {"located": len(rows), "total": len(rows) + int(p.get("unmapped") or 0), "pct": None}, "rows": rows}
    body["cols"] = ["id", "lat", "lon", "rank", "cat", "t", "title", "place", "prec", "watch", "src", "url", "cc", "fam"]
    import map_pins
    body = _drop_unplaced(map_pins.filter_heat_body(body))
    with _HLOCK:
        _HEAT["t"] = time.time() if _HEAT.get("g", 0) == g0 else 0.0
    return body

def handle_get(path, qs):
    if path in ("/map", "/map/"):
        if new_map_on() and (qs or {}).get("classic", [""])[0] != "1":
            return 200, page2(qs or {}), "text/html"
        return 200, page(qs or {}), "text/html"
    if path == "/api/signal/heat":
        force = str((qs or {}).get("fresh", [""])[0]).lower() in ("1", "true", "yes")
        return 200, heat_payload(force=force)
    if path == "/api/signal/points":
        return 200, points_payload()
    if path == "/api/signal/places-status":
        import story_places
        return 200, story_places.status()
    if path in ("/api/signal/location-guard", "/api/location-guard"):
        import location_guard
        return 200, location_guard.latest_report()
    if path.startswith("/api/signal/"):
        name = path[len("/api/signal/"):]
        if name not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, name), "rb") as fh:
            return 200, fh.read(), FILES[name]
    return 404, {"error": "not found"}

try:
    import location_guard as _location_guard
    _location_guard.start_hourly()
except Exception as _lg_ex:
    print("location_guard start:", _lg_ex, flush=True)
