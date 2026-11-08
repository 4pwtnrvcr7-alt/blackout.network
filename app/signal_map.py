"""Global signal map. Public homepage card plus /map.

Draws the Control panel v2 map: Leaflet, the bundled Natural Earth world.geojson, and the same
.signal dots (panel/app.js renderMap, panel/style.css). The panel's OpenFreeMap / MapLibre tile
layer is not used, so there is no tile server and no API key.

Dots come only from /api/state clusters the Wire already returns (watchlist 0 and 1) and only
when that row already has coordinates. Nothing here geocodes, scores, or writes.

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
<p class="bn-sig-note" id="bn_sig_note">Only records with coordinates</p></div>
<div class="bn-sig-side">{LEGEND}<a class="bn-sig-open" href="/map">Open the map</a></div></div>
<div id="bn_sig_map" class="bn-sig-map" role="group" aria-label="World map of Wire and Watchlist stories that already have coordinates. Open the map for filters."></div>
</article></div></section>
{HOME_BOOT}'''

def _pick(qs, key, allowed, default):
    v = (qs.get(key) or [default])[0]
    return v if v in allowed else default

def page(qs):
    rank = _pick(qs, "rank", ("", "0", "4", "7"), "")
    win = _pick(qs, "window", ("24", "72", "168"), "168")
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
<p class="bn-sig-note" id="bn_sig_note">Only records with coordinates</p></div>
{LEGEND}
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

def handle_get(path, qs):
    if path in ("/map", "/map/"):
        return 200, page(qs or {}), "text/html"
    if path.startswith("/api/signal/"):
        name = path[len("/api/signal/"):]
        if name not in FILES: return 404, {"error": "not found"}
        with open(os.path.join(STATIC, name), "rb") as fh:
            return 200, fh.read(), FILES[name]
    return 404, {"error": "not found"}
