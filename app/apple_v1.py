"""BLACKOUT.NETWORK apple_style_v1, Phase 2 (Nov 3 2026): minimal site chrome + new homepage.

Kill switch: on by default; BN_APPLE=0 turns it off, and the site renders exactly as before
(no CSS/JS injection, no wordmark swap, no homepage section, /api/apple/* -> 404).
Serves /bn-apple.css, /bn-apple.js and /api/apple/home (a slim same-origin summary of /api/state, /api/solar_seismic,
/api/grid and /api/sources/catalog, built in-process so the homepage never downloads the full payloads).
Nothing here is invented: every number comes from those endpoints, with its own timestamp."""
import os, sys, json, time, html, threading

BASE = os.path.dirname(os.path.abspath(__file__))
ENABLED = lambda: os.environ.get("BN_APPLE", "1") != "0"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
_cache = {"t": 0, "v": None}; _lock = threading.Lock()

def _body(r):
    if not r or r[0] != 200: return None
    b = r[1]
    if isinstance(b, (bytes, bytearray)): b = json.loads(b.decode("utf-8"))
    elif isinstance(b, str): b = json.loads(b)
    return b if isinstance(b, dict) else None

def _slim(x):
    return {k: x.get(k) for k in ("cluster_id", "title", "category", "location", "lat", "lon", "rank", "n_families", "updated", "first_seen")}

def home_data():
    with _lock:
        if _cache["v"] and time.time() - _cache["t"] < 60: return _cache["v"]
    srv = sys.modules.get("server"); out = {"generated": None, "main": [], "counts": {}, "kp": None, "quake": None, "grid": None, "sources": None}
    try:
        st = srv.api_state(); out["generated"] = st.get("generated")
        main = st.get("main") or []
        for x in main: out["counts"][x.get("category") or "other"] = out["counts"].get(x.get("category") or "other", 0) + 1
        out["main"] = [_slim(x) for x in sorted(main, key=lambda x: (-(x.get("rank") or 0), -(x.get("n_families") or 0)))[:40]]
        out["wire_total"] = len(main)
    except Exception: pass
    try:
        ss = _body(srv._addon_mod("solar_seismic").handle_get("/api/solar_seismic", {}))
        kp = (ss.get("now") or {}).get("kp") or {}
        if kp.get("value") is not None: out["kp"] = {k: kp.get(k) for k in ("value", "t", "t_et", "max24")}
        q = (ss.get("quakes_notable") or [None])[0]
        if q: out["quake"] = {k: q.get(k) for k in ("mag", "place", "t", "t_et")}
    except Exception: pass
    try:
        g = _body(srv._addon_mod("gridwatch").handle_get("/api/grid", {})); s = g.get("summary") or {}
        ranks = [int(k) for k, v in (s.get("by_rank") or {}).items() if k.isdigit() and v]
        out["grid"] = {"total": s.get("total"), "top": max(ranks) if ranks else None, "by_kind": s.get("by_kind"), "generated": g.get("generated")}
    except Exception: pass
    try:
        c = _body(srv._addon_mod("sources").handle_get("/api/sources/catalog", {"per": ["1"]}))
        out["sources"] = c.get("total")
    except Exception: pass
    with _lock: _cache.update(t=time.time(), v=out)
    return out

def head_tag():
    """Early, render-blocking switch: '/' with no hash (or #home) shows the new homepage; any tab hash shows the dashboard."""
    # bna-home: the new homepage (dashboard path "/" with no tab hash). bna-pg: the page groups restyled so far
    # (The Wire, Threats tabs, /crime, /network, /wire/<id> event pages); every other page keeps its current look.
    return (b'<script>(function(){var d=document.documentElement,p=location.pathname;function f(){var h=location.hash.replace(/^#/,""),home=p=="/"&&(!h||h=="home");'
            b'd.classList.toggle("bna-home",home);d.classList.toggle("bna-pg",!home&&(p=="/"?/^(wire|weather|solar|grid|network|ai|streams|noise|heatmap|trends|broadcasts|radio|preppers|medical|resources|tips|bushcraft)$/.test(h):/^\\/crime\\/?$|^\\/network(\\/[a-z0-9-]+)?\\/?$|^\\/wire\\/[0-9a-f]{16}\\/?$/.test(p)))}'
            b'f();addEventListener("hashchange",f)})()</script>'
            b'<link rel="stylesheet" href="/bn-apple.css">')

def home_html(sn):
    """Server-rendered homepage shell (static text + real links). Live numbers fill in from /api/apple/home."""
    try:
        import sitenav_ui as UI; groups = UI.menu3_sections(sn)
    except Exception: groups = []
    cols = ""
    for g in groups:
        sid, label, items = g[0], g[1], g[-1]
        lis = "".join((f'<li><a href="{E(h)}">{E(l)}</a></li>' if h else f'<li class="bna-soon">{E(l)} <em>Soon</em></li>') for _k, l, h in items)
        cols += f'<div><h2>{E(label)}</h2><ul>{lis}</ul></div>'
    return f'''<div id="bna_home" class="bna" aria-label="Home">
<section class="bna-hero bna-wrap"><h1 class="bna-lede">The fastest way to know what&rsquo;s happening.</h1>
<p class="bna-links"><a class="bna-lnk" href="/sources"><b data-bna="sources">&ndash;</b> sources in the feed</a><a class="bna-lnk" href="/scoring">How we score</a></p></section>
<section class="bna-sec" aria-labelledby="bna_h_latest"><div class="bna-wrap bna-sech"><h2 id="bna_h_latest">The latest. <span>Ranked as it happens.</span></h2>
<div class="bna-arrows"><button type="button" class="bna-arw" data-dir="-1" aria-label="Scroll back" aria-controls="bna_row_latest">&lsaquo;</button><button type="button" class="bna-arw" data-dir="1" aria-label="Scroll forward" aria-controls="bna_row_latest">&rsaquo;</button></div></div>
<div class="bna-row" id="bna_row_latest" tabindex="0" aria-label="Top of the Wire"><p class="bna-empty">Loading the Wire&hellip;</p></div>
<p class="bna-wrap bna-more"><a class="bna-lnk" href="/#wire">Open The Wire</a></p></section>
<section class="bna-sec" aria-labelledby="bna_h_now"><div class="bna-wrap bna-sech"><h2 id="bna_h_now">Threats right now. <span>Live readouts.</span></h2></div>
<div class="bna-wrap bna-grid3" id="bna_now">
<a class="bna-card bna-rd" href="/#solar"><p class="bna-k">Kp index</p><p class="bna-big" data-bna="kp">&ndash;</p><p class="bna-d" data-bna="kpd"></p><p class="bna-src" data-bna="kps"></p></a>
<a class="bna-card bna-rd" href="/#solar"><p class="bna-k">Latest notable quake</p><p class="bna-big" data-bna="qm">&ndash;</p><p class="bna-d" data-bna="qp"></p><p class="bna-src" data-bna="qs"></p></a>
<a class="bna-card bna-rd" href="/#grid"><p class="bna-k">U.S. energy grid</p><p class="bna-big" data-bna="gt">&ndash;</p><p class="bna-d" data-bna="gd"></p><p class="bna-src" data-bna="gs"></p></a></div></section>
<section class="bna-sec bna-wrap"><div class="bna-brief"><div><h2>The Free brief. <span>The day, ranked.</span></h2><p>The highest-ranked events of the day, in one email.</p></div>
<a class="bna-btn" href="/newsletter">Get the Free brief</a></div><p class="bna-asof" data-bna="asof"></p></section>
<footer class="bna-foot"><div class="bna-wrap"><nav class="bna-cols" aria-label="Site">{cols}</nav>
<div class="bna-bot"><p class="bna-fol">Follow <a href="{E(sn.YT_URL)}" target="_blank" rel="noopener me">YouTube</a><a href="{E(sn.X_URL)}" target="_blank" rel="noopener me">X</a></p>
<p class="bna-legal"><a href="/scoring">How we score</a><a href="/privacy">Privacy</a><a href="/tos">Terms</a><a href="/stats">Stats</a><a href="/report-status">Report status</a></p></div>
<p class="bna-copy">BLACKOUT.NETWORK. Signal over noise.&trade;</p></div></footer></div>'''

def _static(name, ctype):
    with open(os.path.join(BASE, "static", name), "rb") as f: return 200, f.read(), ctype

def handle_get(path, qs):
    if not ENABLED(): return 404, {"error": "not found"}
    if path == "/bn-apple.css": return _static("bn-apple.css", "text/css")
    if path == "/bn-apple.js": return _static("bn-apple.js", "application/javascript")
    if path == "/api/apple/home": return 200, home_data()
    return 404, {"error": "not found"}
