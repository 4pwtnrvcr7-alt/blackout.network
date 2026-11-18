"""Client-side performance pass (Matt, 9:13 PM ET, Nov 17 2026).

Trim /live HTML, lazy-load tab assets (including Leaflet from unpkg), defer
non-critical scripts, add lazy images. BN_PERF=0 restores the pre-pass HTML
rewrites (apple snapshot inlining is also gated in apple_v1._snap_js).
"""
import os, re, hashlib
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))

# Path (no query) -> group name. Paths are matched after stripping a leading "/".
# Groups may list deps so Leaflet/Chart load before the tab that needs them.
PATH_GROUP = {
    # Leaflet / heat / markercluster (unpkg + local copies)
    "unpkg.com/leaflet@1.9.4/dist/leaflet.css": "leaflet",
    "unpkg.com/leaflet@1.9.4/dist/leaflet.js": "leaflet",
    "unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css": "leaflet",
    "unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css": "leaflet",
    "unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js": "leaflet",
    "unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js": "leaflet",
    "api/heatmap/MarkerCluster.css": "leaflet",
    "api/heatmap/MarkerCluster.Default.css": "leaflet",
    "api/heatmap/leaflet-heat.js": "leaflet",
    "api/heatmap/leaflet.markercluster.js": "leaflet",
    "cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js": "chart",
    # Tabs
    "api/solar_seismic/app.css": "solar",
    "api/solar_seismic/live.css": "solar",
    "api/solar_seismic/app.js": "solar",
    "api/solar_seismic/live.js": "solar",
    "api/solar_quake/app.css": "solar",
    "api/solar_quake/app.js": "solar",
    "api/heatmap/app.css": "heatmap",
    "api/heatmap/app.js": "heatmap",
    "api/politics/app.css": "politics",
    "api/politics/app.js": "politics",
    "api/weather/app.css": "weather",
    "api/weather/app.js": "weather",
    "api/games/app.css": "games",
    "api/games/app.js": "games",
    "api/trends/app.css": "trends",
    "api/trends/app.js": "trends",
    "api/wire_history/app.css": "wire",
    "api/wire_history/app.js": "wire",
    "api/noise/app.css": "noise",
    "api/noise/app.js": "noise",
    "api/newsletter/app.css": "newsletter",
    "api/newsletter/app.js": "newsletter",
    "api/sources/app.css": "sources",
    "api/sources/app.js": "sources",
    "api/geo/geo.css": "maps",
    "api/geo/geo.js": "maps",
    "api/radio/app.css": "radio",
    "api/radio/app.js": "radio",
    "api/live_archive/app.css": "broadcasts",
    "api/live_archive/app.js": "broadcasts",
    "api/spacex/app.css": "spacex",
    "api/spacex/app.js": "spacex",
    "api/figures/app.css": "figures",
    "api/figures/app.js": "figures",
    "api/finance/app.css": "finance",
    "api/finance/app.js": "finance",
    "api/intel/app.css": "intel",
    "api/intel/app.js": "intel",
    "api/preppers/app.css": "preppers",
    "api/preppers/app.js": "preppers",
    "api/ai/app.css": "ai",
    "api/ai/app.js": "ai",
    "api/gridstatus/app.css": "grid",
    "api/gridstatus/app.js": "grid",
    "api/government/app.css": "government",
    "api/government/app.js": "government",
    "api/gunlaws/app.css": "gunlaws",
    "api/gunlaws/app.js": "gunlaws",
    "api/midterms/app.css": "midterms",
    "api/midterms/app.js": "midterms",
    "api/translate/app.css": "translate",
    "api/translate/app.js": "translate",
    "vsubs/vsubs.css": "vsubs",
    "vsubs/vsubs.js": "vsubs",
    "api/search/app.js": "search",
    "api/report/app.css": "report",
    "api/report/app.js": "report",
    "api/mesh/grid-panel.js": "grid",
    "api/network/accordion.js": "network",
}

GROUP_DEPS = {
    "heatmap": ["leaflet"],
    "weather": ["leaflet"],
    "maps": ["leaflet"],
    "wire": ["leaflet", "chart"],
    "solar": ["chart"],
    "finance": ["chart"],
    "trends": ["chart"],
    "midterms": ["chart"],
    "gunlaws": ["chart"],
    "grid": ["chart"],
}

# Hash / data-tab names that should load a different group key.
ALIAS = {
    "threat": "wire",
    "solar_seismic": "solar",
    "solar-seismic": "solar",
    "heat-map": "heatmap",
    "heat_map": "heatmap",
    "bcast": "broadcasts",
    "broadcast": "broadcasts",
    "net": "network",
    "gov": "government",
    "res": "preppers",
    "resources": "preppers",
    "bush": "preppers",
    "bushcraft": "preppers",
    "med": "preppers",
    "medical": "preppers",
    "ranked": "wire",
    "jets": "spacex",
    "thread": "wire",
    "streams": "broadcasts",
}

# Loaded during idle time so search/translate still work without a tab visit.
IDLE = ["search", "translate", "vsubs", "report"]

_LINK_RE = re.compile(
    rb'<link\s[^>]*rel=["\']stylesheet["\'][^>]*>',
    re.I,
)
_SCRIPT_RE = re.compile(
    rb'<script\s[^>]*src=["\'][^"\']+["\'][^>]*></script>',
    re.I,
)
_HREF_RE = re.compile(rb'\bhref=["\']([^"\']+)["\']', re.I)
_SRC_RE = re.compile(rb'\bsrc=["\']([^"\']+)["\']', re.I)

# Fallback plugin document.write in dashboard.html is unused once Leaflet is lazy.
_DW_RE = re.compile(
    rb'<script>if\(typeof L!="undefined"&&!L\.heatLayer\)document\.write\(.*?\)</script>',
    re.S,
)



def _filev(name):
    try:
        with open(os.path.join(BASE, "static", name), "rb") as fh:
            raw = fh.read()
        return hashlib.sha1(raw).hexdigest()[:10].encode()
    except Exception:
        return b"1"

def enabled():
    return os.environ.get("BN_PERF", "1").strip() != "0"


def _norm_path(url: str) -> str:
    u = url.split("?")[0].split("#")[0]
    if u.startswith("https://"):
        u = u[len("https://"):]
    elif u.startswith("http://"):
        u = u[len("http://"):]
    if u.startswith("/"):
        u = u[1:]
    return u


def _group_for(url: str):
    return PATH_GROUP.get(_norm_path(url))


def _is_dashboard(b: bytes) -> bool:
    return b"<main id=\"tab-threat\"" in b or b'id="bntl"' in b


def _lazy_images(b: bytes) -> bytes:
    def repl(m):
        tag = m.group(0)
        if b"loading=" in tag.lower() or b"fetchpriority=\"high\"" in tag.lower() or b"fetchpriority='high'" in tag.lower():
            return tag
        # insert loading="lazy" before the closing >
        if tag.endswith(b"/>"):
            return tag[:-2] + b' loading="lazy"/>'
        if tag.endswith(b">"):
            return tag[:-1] + b' loading="lazy">'
        return tag
    return re.sub(rb"<img\b[^>]*>", repl, b, flags=re.I)


def _ensure_video_preload(b: bytes) -> bytes:
    def repl(m):
        tag = m.group(0)
        if b"preload=" in tag.lower():
            return tag
        if tag.endswith(b">"):
            return tag[:-1] + b' preload="metadata">'
        return tag
    return re.sub(rb"<video\b[^>]*>", repl, b, flags=re.I)


def _strip_and_collect(b: bytes):
    """Remove lazy-group stylesheet/script tags; return (html, groups dict)."""
    groups = {}  # name -> {"css": [urls], "js": [urls]}

    def add(url, kind):
        url = url.decode("utf-8", "replace") if isinstance(url, (bytes, bytearray)) else url
        g = _group_for(url)
        if not g:
            return False
        rec = groups.setdefault(g, {"css": [], "js": []})
        if url not in rec[kind]:
            rec[kind].append(url)
        return True

    def drop_link(m):
        href = _HREF_RE.search(m.group(0))
        if href and add(href.group(1), "css"):
            return b""
        return m.group(0)

    def drop_script(m):
        src = _SRC_RE.search(m.group(0))
        if src and add(src.group(1), "js"):
            return b""
        return m.group(0)

    b = _LINK_RE.sub(drop_link, b)
    b = _SCRIPT_RE.sub(drop_script, b)
    # tidy leftover blank lines from removed tags
    b = re.sub(rb"\n[ \t]*\n[ \t]*\n", b"\n\n", b)
    return b, groups


def _config_script(groups: dict) -> bytes:
    import json
    cfg = {}
    for name, rec in groups.items():
        item = {"css": rec.get("css") or [], "js": rec.get("js") or []}
        if name in GROUP_DEPS:
            item["deps"] = GROUP_DEPS[name]
        cfg[name] = item
    # always publish deps + alias + idle, even if a dep group had no tags
    cfg["__alias"] = ALIAS
    cfg["__idle"] = [n for n in IDLE if n in groups or True]
    js = "window.BN_LAZY_GROUPS=" + json.dumps(cfg, separators=(",", ":")) + ";"
    return (b"<script>" + js.encode("utf-8") + b"</script>"
            b'<script src="/bn-lazy.js?v=' + _filev('bn-lazy.js') + b'" defer></script>')


def rewrite(b: bytes) -> bytes:
    if not enabled() or not b or b"<html" not in b[:4000].lower():
        return b
    try:
        if _is_dashboard(b):
            b = _DW_RE.sub(b"", b)
            b, groups = _strip_and_collect(b)
            if groups:
                inj = _config_script(groups)
                k = b.rfind(b"</body>")
                if k > 0:
                    b = b[:k] + inj + b[k:]
                else:
                    b += inj
        b = _lazy_images(b)
        b = _ensure_video_preload(b)
    except Exception:
        return b
    return b


def handle_get(path, qs):
    if path == "/bn-lazy.js":
        p = os.path.join(BASE, "static", "bn-lazy.js")
        with open(p, "rb") as f:
            return 200, f.read(), "application/javascript"
    if path == "/cohesion.js":
        p = os.path.join(BASE, "static", "cohesion.js")
        with open(p, "rb") as f:
            return 200, f.read(), "application/javascript"
    if path == "/bn-ga.js":
        # late import: server defines GA_JS
        import server
        return 200, server.GA_JS.encode("utf-8"), "application/javascript"
    return 404, {"error": "not found"}
