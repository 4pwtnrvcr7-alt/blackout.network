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

# ---- Active Threat Monitoring (homepage chart cards). Slim, same-origin, cached 2 min; every number from stored or same-origin data. ----
_dcache = {"t": 0, "v": None}
def _iso(t):
    from datetime import datetime, timezone
    try: return datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return None
def _r(c, f):
    try: return f()
    except Exception: return None
def dash_data():
    with _lock:
        if _dcache["v"] and time.time() - _dcache["t"] < 120: return _dcache["v"]
    import sqlite3
    srv = sys.modules.get("server"); now = time.time(); out = {"now": now}
    ss = _r(None, lambda: _body(srv._addon_mod("solar_seismic").handle_get("/api/solar_seismic", {}))) or {}
    nw = ss.get("now") or {}; bins = ss.get("bins") or []
    def kp_card():
        kp = nw.get("kp") or {}
        if kp.get("value") is None: return None
        ser = [[_iso(b.get("bin_start")), b.get("kp")] for b in bins[-24:] if b.get("kp") is not None]
        return {"value": kp.get("value"), "g": kp.get("g"), "max24": kp.get("max24"), "t": kp.get("t"), "series": ser,
                "fc": [x.get("G") for x in ((nw.get("scales") or {}).get("forecast") or [])][:3]}
    out["kp"] = _r(None, kp_card)
    def quake_card():
        q = nw.get("quake") or {}; lst = ss.get("map") or []
        day = [x for x in lst if (_iso(x.get("t")) or 0) >= now - 86400 and x.get("mag") is not None]
        cls = [0, 0, 0, 0, 0, 0]   # <4, 4-4.9, 5-5.9, 6-6.9, 7-7.9, 8+
        for x in day: cls[min(5, max(0, int(float(x["mag"])) - 3))] += 1
        big = max(day, key=lambda x: x["mag"]) if day else None
        lt = q.get("latest") or {}
        pick = big or lt
        return {"n24": len(day), "classes": cls, "big": {k: pick.get(k) for k in ("mag", "place", "t", "tsunami", "url")} if pick else None,
                "week_n": q.get("count"), "src_t": max((x.get("t") for x in lst), default=None)}
    out["quake"] = _r(None, quake_card)
    def flare_card():
        x = nw.get("xray") or {}; fl = nw.get("flare") or {}
        ser = [[_iso(b.get("bin_start")), b.get("xray_max")] for b in bins[-24:] if b.get("xray_max")]
        return {"cls": x.get("class"), "flux": x.get("flux"), "t_et": x.get("t_et"), "count": fl.get("count"),
                "biggest": {k: (fl.get("biggest") or {}).get(k) for k in ("class", "t")}, "r": ((nw.get("scales") or {}).get("now") or {}).get("R"), "series": ser}
    out["flare"] = _r(None, flare_card)
    def wind_card():
        w = nw.get("wind") or {}; ser = [[_iso(p.get("t")), p.get("proton_speed")] for p in (ss.get("wind24") or [])[::3] if p.get("proton_speed")]
        return {"speed": w.get("speed"), "bz": w.get("bz"), "t_et": w.get("t_et"), "series": ser}
    out["wind"] = _r(None, wind_card)
    def grid_card():
        gs = _body(srv._addon_mod("gridstatus").handle_get("/api/gridstatus", {})) or {}
        secs = [v for v in (gs.get("sections") or {}).values() if isinstance(v, dict)]
        live = [v for v in secs if v.get("status") not in ("nodata_ok", None)]
        cnt = {}
        for v in live: cnt[v["status"]] = cnt.get(v["status"], 0) + 1
        odin = sum(int(((v.get("odin") or {}).get("outages")) or 0) for v in secs)
        utils = sum(int(((v.get("odin") or {}).get("reporting_outages")) or 0) for v in secs)
        nws = {"extreme": sum(int(((v.get("nws") or {}).get("extreme")) or 0) for v in secs),
               "warnings": sum(int(((v.get("nws") or {}).get("warnings")) or 0) for v in secs),
               "power": sum(int(((v.get("nws") or {}).get("power_alerts")) or 0) for v in secs)}
        hist = (_body(srv._addon_mod("gridstatus").handle_get("/api/gridstatus/history", {})) or {}).get("history") or []
        per = {}
        for h in hist:
            t = _iso(h.get("ts"))
            if t is None or t < now - 48 * 3600 or h.get("status") == "nodata_ok": continue
            p = per.setdefault(t, [0, 0]); p[0] += h.get("status") == "watch"; p[1] += h.get("status") not in ("online", "watch")
        flagged = [{"name": v.get("name"), "status": v.get("status"), "why": (v.get("reasons") or [""])[0]} for v in live if v.get("status") != "online"]
        return {"regions": len(live), "status": cnt, "outages": odin, "utilities": utils, "series": [[t] + per[t] for t in sorted(per)], "flagged": flagged[:6],
                "nws": nws, "t": (gs.get("freshness") or {}).get("sections", {}).get("ts") or gs.get("generated"),
                "nws_t": ((gs.get("freshness") or {}).get("nws") or {}).get("ts"),
                "storms": [{"title": w.get("title"), "rank": w.get("rank"), "location": w.get("location")} for w in (gs.get("weather") or [])[:3]]}
    out["grid"] = _r(None, grid_card)
    def net_card():
        ns = srv._addon_mod("netstatus"); a = ns.alerts()
        c = sqlite3.connect(f"file:{ns.NDB}?mode=ro", uri=True, timeout=5)
        try:
            cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 86400))
            rows = c.execute("SELECT ts, COUNT(DISTINCT src), SUM(level>=2) FROM checks WHERE ts>=? AND kind!='isp' GROUP BY ts ORDER BY ts", (cut,)).fetchall()
        finally: c.close()
        ser = [[_iso(r[0]), r[2] or 0] for r in rows]
        if len(ser) > 96: k = len(ser) / 96.0; ser = [max(ser[int(i * k):int((i + 1) * k)], key=lambda p: p[1]) for i in range(96)]
        return {"count": a.get("count"), "alerts": [{"src": x.get("src"), "status": x.get("status")} for x in (a.get("alerts") or [])[:4]],
                "checked": rows[-1][1] if rows else None, "t": a.get("polled"), "series": ser}
    out["net"] = _r(None, net_card)
    def wire_card():
        c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=5)
        try:
            cut = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 8 * 86400))
            rows = c.execute("""SELECT date(first_seen, '-5 hours') d, SUM(rank>=7) hi, SUM(rank BETWEEN 4 AND 6) mid, SUM(rank<4) lo
                                FROM clusters WHERE watchlist=0 AND first_seen>=? GROUP BY d ORDER BY d""", (cut,)).fetchall()
        finally: c.close()
        days = [[r[0], r[1] or 0, r[2] or 0, r[3] or 0] for r in rows][-7:]   # ET calendar days (EST offset), today last
        return {"days": days, "total": sum(d[1] + d[2] + d[3] for d in days), "hi": sum(d[1] for d in days)}
    out["wire"] = _r(None, wire_card)
    with _lock: _dcache.update(t=time.time(), v=out)
    return out

def head_tag():
    """Early, render-blocking switch: '/' with no hash (or #home) shows the new homepage; any tab hash shows the dashboard."""
    # bna-home: the new homepage (dashboard path "/" with no tab hash). bna-pg: the page groups restyled so far
    # (The Wire, Threats tabs, /crime, /network, /wire/<id> event pages); every other page keeps its current look.
    return (b'<script>(function(){var d=document.documentElement,p=location.pathname;function f(){var h=location.hash.replace(/^#/,""),home=p=="/"&&(!h||h=="home");'
            b'd.classList.toggle("bna-home",home);d.classList.toggle("bna-pg",!home)}'
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
<h1 class="bna-vh">BLACKOUT.NETWORK</h1>
<section class="bna-sec" aria-labelledby="bna_h_latest"><div class="bna-wrap bna-sech"><h2 id="bna_h_latest">The latest. <span>Ranked as it happens.</span></h2>
<div class="bna-arrows"><button type="button" class="bna-arw" data-dir="-1" aria-label="Scroll back" aria-controls="bna_row_latest">&lsaquo;</button><button type="button" class="bna-arw" data-dir="1" aria-label="Scroll forward" aria-controls="bna_row_latest">&rsaquo;</button></div></div>
<div class="bna-row" id="bna_row_latest" tabindex="0" aria-label="Top of the Wire"><p class="bna-empty">Loading the Wire&hellip;</p></div>
<p class="bna-wrap bna-more"><a class="bna-lnk" href="/#wire">Open The Wire</a></p></section>
<section class="bna-sec" id="bna_dash" aria-labelledby="bna_h_now"><div class="bna-wrap bna-sech"><h2 id="bna_h_now">Active Threat Monitoring</h2></div>
<div class="bna-wrap bna-mgrid" id="bna_now"><article class="bna-card bna-mc" data-mc="kp"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_kp"><span class="bna-k">Geomagnetic storms</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_kp" hidden><div data-f="x"></div><a class="bna-lnk" href="/#solar">See full page</a></div></article><article class="bna-card bna-mc" data-mc="quake"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_quake"><span class="bna-k">Earthquakes</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_quake" hidden><div data-f="x"></div><a class="bna-lnk" href="/#solar">See full page</a></div></article><article class="bna-card bna-mc" data-mc="flare"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_flare"><span class="bna-k">Solar flares</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_flare" hidden><div data-f="x"></div><a class="bna-lnk" href="/#solar">See full page</a></div></article><article class="bna-card bna-mc" data-mc="wind"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_wind"><span class="bna-k">Solar wind</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_wind" hidden><div data-f="x"></div><a class="bna-lnk" href="/#solar">See full page</a></div></article><article class="bna-card bna-mc" data-mc="grid"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_grid"><span class="bna-k">U.S. power grid</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_grid" hidden><div data-f="x"></div><a class="bna-lnk" href="/#grid">See full page</a></div></article><article class="bna-card bna-mc" data-mc="wx"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_wx"><span class="bna-k">Weather threats to power</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_wx" hidden><div data-f="x"></div><a class="bna-lnk" href="/#grid">See full page</a></div></article><article class="bna-card bna-mc" data-mc="net"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_net"><span class="bna-k">Internet and cloud</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_net" hidden><div data-f="x"></div><a class="bna-lnk" href="/#network">See full page</a></div></article><article class="bna-card bna-mc" data-mc="wire"><button type="button" class="bna-mh" aria-expanded="false" aria-controls="bna_mx_wire"><span class="bna-k">The Wire this week</span><span class="bna-mv" data-f="v">&ndash;</span><span class="bna-ms" data-f="s">Loading&hellip;</span><span class="bna-ch" data-f="c" aria-hidden="true"></span><span class="bna-mf"><span class="bna-src" data-f="t"></span><span class="bna-chev" aria-hidden="true"></span></span></button><div class="bna-mx" id="bna_mx_wire" hidden><div data-f="x"></div><a class="bna-lnk" href="/#wire">See full page</a></div></article></div></section>
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
    if path == "/api/apple/dash": return 200, dash_data()
    return 404, {"error": "not found"}
