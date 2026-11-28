"""Pulse intro (Nov 28 2026): "/" opens on one live instrument instead of stacked video panels.

Four rings, inside out, plus one scope, all drawn from numbers the site already serves (read-only, nothing stored here):
  Wire    one hairline per story, brightness = rank           theme.summary()           (same numbers as /api/live/summary)
  Quakes  last 24 h, angle = hours ago, radius = magnitude    solar_seismic "map"       (USGS M2.5+, same as /api/solar_seismic)
  Grid    one segment per region, length = share of demand    gridpage data regions     (EIA-930, same as /api/gridpage/data)
  Space   last 72 h of Kp, bars                               solar_seismic "bins"/"now" (NOAA SWPC)
  Scope   US demand for the last hours + quake spikes         gridpage region series + solar_seismic "map"
Centre readout: threat level = average rank of the stories ranked 7 and up (summary level / level_n).

/api/pulse/live is a compact, 45 s stale-while-revalidate roll-up of those three reads. Each section is built on its own thread:
one slow or failed source hides only its own ring (no placeholder number is ever drawn), and a section older than 10 minutes is
dropped rather than shown. The page itself keeps the previous menu, follow band, footer and the free-brief signup (theme.py).
Kill switch: Render env BN_INTRO_PULSE=0 serves the previous intro (theme._home_page_raw) unchanged.
No scanner, scoring or write path is touched; everything here is read-only."""
import hashlib, html, json, os, re, threading, time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "pulse_static")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
FILES = {"pulse.css": "text/css; charset=utf-8", "pulse.js": "application/javascript; charset=utf-8"}
MAX_AGE = 600   # a section older than this is hidden, not shown

def on(): return os.environ.get("BN_INTRO_PULSE", "1").strip() != "0"

def _v(n):
    try:
        with open(os.path.join(STATIC, n), "rb") as f: return hashlib.sha1(f.read()).hexdigest()[:10]
    except Exception: return "0"

# ---------------------------------------------------------------- page
ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'
PILLS = (("wire", "Wire", "stories"), ("quake", "Quakes", "M2.5+ · 24 h"), ("grid", "Grid", "GW demand"), ("space", "Space", "Kp index"))

def _section(href, cta):
    pills = "".join(
        f'<button type="button" class="pl-pill" data-k="{k}" aria-pressed="false" aria-controls="pl_cap" disabled>'
        f'<span class="pl-pk">{E(lab)}</span><b class="pl-pv" data-v="{k}">&ndash;</b><small class="pl-ps" data-s="{k}">{E(sub)}</small></button>' for k, lab, sub in PILLS)
    return f'''<section class="pl" id="s1" aria-label="Live threat instrument">
<div class="pl-top"><p class="pl-eb">United States</p><p class="pl-live" id="pl_live"><i></i><span>Live</span></p></div>
<div class="pl-main">
 <div class="pl-dial" id="pl_dial"><canvas id="pl_cv" aria-hidden="true"></canvas>
  <div class="pl-ctr" id="pl_ctr" aria-live="polite">
   <div class="pl-cs on" data-for="def"><p class="pl-cl">Threat level</p><p class="pl-cn" data-n="def">&ndash;</p><p class="pl-cu"><i id="pl_dot"></i></p></div>
   <div class="pl-cs" data-for="wire"><p class="pl-cl">Wire</p><p class="pl-cn" data-n="wire">&ndash;</p><p class="pl-cu" data-u="wire">stories</p></div>
   <div class="pl-cs" data-for="quake"><p class="pl-cl">Quakes · 24 h</p><p class="pl-cn" data-n="quake">&ndash;</p><p class="pl-cu" data-u="quake">M2.5+</p></div>
   <div class="pl-cs" data-for="grid"><p class="pl-cl">US demand</p><p class="pl-cn" data-n="grid">&ndash;</p><p class="pl-cu" data-u="grid">GW</p></div>
   <div class="pl-cs" data-for="space"><p class="pl-cl">Kp index</p><p class="pl-cn" data-n="space">&ndash;</p><p class="pl-cu" data-u="space">NOAA SWPC</p></div>
  </div></div>
 <div class="pl-side">
  <div class="pl-pills" role="group" aria-label="Rings">{pills}</div>
  <div class="pl-cap" id="pl_cap" aria-live="polite">
   <p class="on" data-for="def"><span data-c="def1">Threat level is the average rank of the stories ranked 7 and up.</span><span>Rings, inside out: Wire (one line per story) &middot; Quakes &middot; Grid &middot; Space.</span></p>
   <p data-for="wire"><span data-c="wire1"></span><span>The brightest lines are the stories ranked 7 and up.</span></p>
   <p data-for="quake"><span data-c="quake1"></span><span>Angle is hours ago (top is now). Distance from the center is magnitude. USGS.</span></p>
   <p data-for="grid"><span data-c="grid1"></span><span>Segment length is share of demand. EIA-930. Alaska and Hawaii report no demand feed.</span></p>
   <p data-for="space"><span data-c="space1"></span><span>Bars are the last 72 hours. NOAA Space Weather Prediction Center.</span></p>
  </div>
  <div class="pl-scope" id="pl_scope"><div class="pl-sh"><span>US grid demand</span><span>Quakes M2.5+</span></div><canvas id="pl_sv" aria-hidden="true"></canvas>
   <div class="pl-st"><span id="pl_t0"></span><span id="pl_t1"></span></div></div>
  <div class="pl-foot"><a class="pl-btn" href="{E(href)}">{E(cta)}{ARROW}</a><p class="pl-src">EIA &middot; USGS &middot; NOAA &middot; NWS</p></div>
 </div>
</div>
<noscript><p class="pl-ns">Live numbers need JavaScript. The full feed is at <a href="{E(href)}">{E(cta)}</a>.</p></noscript>
</section>'''

def transform(h):
    """Take the previous intro's full HTML (head, header, menu, scripts, footer, brief signup) and swap its seven video sections for the
    instrument. Everything outside <main> stays exactly as the previous intro built it, so the menu and footer cannot drift."""
    m_main = re.search(r'<main id="flow"[^>]*>.*?</main>', h, re.S)
    s6 = re.search(r'<section class="h-sec"[^>]*id="s6"[^>]*>.*?</section>', h, re.S)
    foot = re.search(r'<footer class="h-foot".*?</footer>', h, re.S)
    if not (m_main and s6 and foot): raise ValueError("previous intro markup changed")
    m_cta = re.search(r'<a class="bnt-btn[^"]*" href="(/[a-z]*)">(Open The Wire|Enter the dashboard)</a>', h)
    href, cta = (m_cta.group(1), m_cta.group(2)) if m_cta else ("/wire", "Open The Wire")
    brief = re.sub(r'<p class="h-credit">[^<]*</p>', "", s6.group(0))
    brief = brief.replace(' data-clip="email"', "").replace('class="h-sec"', 'class="h-sec pl-brief"', 1)
    main = f'<main id="flow">\n{_section(href, cta)}\n{brief}\n{foot.group(0)}\n</main>'
    h = h[:m_main.start()] + main + h[m_main.end():]
    h = re.sub(r'<link rel="preload" as="image" href="/bnt/media/hero-[dm]\.jpg[^>]*>', "", h)
    h = re.sub(r'<ol class="h-pager"[^>]*></ol>\n?', "", h)
    h = h.replace('<body class="bnt-home"', '<body class="bnt-home pl-body"', 1).replace('<html lang="en" data-bnt-home', '<html lang="en" data-bnt-home data-pl', 1)
    h = re.sub(r'(<link rel="stylesheet" href="[^"]*home\.css[^"]*">)', r'\1<link rel="stylesheet" href="/api/pulse/pulse.css?v=' + _v("pulse.css") + '">', h, 1)
    h, n = re.subn(r'<script src="[^"]*home\.js[^"]*" defer></script>', '<script src="/api/pulse/pulse.js?v=' + _v("pulse.js") + '" defer></script>', h)
    if n != 1 or "pulse.css" not in h: raise ValueError("previous intro scripts changed")
    return h

# ---------------------------------------------------------------- live data (read-only, 45 s stale-while-revalidate)
UPSTREAM = os.environ.get("BN_PULSE_UPSTREAM", "").rstrip("/")   # preview harness only: read the same public endpoints from a live site

def _upstream(path):
    import urllib.request
    err = None
    for _ in range(3):
        try:
            rq = urllib.request.Request(UPSTREAM + path, headers={"User-Agent": "Mozilla/5.0 (BN pulse preview)", "Accept": "application/json"})
            with urllib.request.urlopen(rq, timeout=45) as r: return json.loads(r.read().decode("utf-8"))
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

def _epoch(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()

def _b_wire():
    if UPSTREAM: S = _upstream("/api/live/summary")
    else:
        import theme
        S = theme.summary()
    ranks = {str(k): int(v) for k, v in (S.get("ranks") or {}).items()}
    if not S.get("wire") or not ranks: raise RuntimeError("no wire")
    return {"level": S.get("level"), "level_n": int(S.get("level_n") or 0), "level_hi": bool(S.get("level_hi")), "n": int(S["wire"]), "ranks": ranks,
            "scan_et": S.get("last_scan_et") or "", "scan": S.get("last_scan") or ""}

def _b_grid():
    G = _call("gridpage", "/api/gridpage/data")
    regs = [r for r in (G.get("regions") or []) if r.get("demand_mw")]
    if not regs: raise RuntimeError("no regions")
    tot, cnt = {}, {}
    for r in regs:
        for p in (r.get("series") or []):
            if len(p) >= 2 and p[1]:
                tot[p[0]] = tot.get(p[0], 0) + p[1]; cnt[p[0]] = cnt.get(p[0], 0) + 1
    full = max(cnt.values()) if cnt else 0
    series = [[_epoch(t), v] for t, v in sorted(tot.items()) if cnt[t] == full]   # only hours where every region reported
    sw = G.get("swpc") or {}
    return {"regions": [{"id": r["id"], "status": r.get("status") or "online", "mw": r["demand_mw"]} for r in regs],
            "series": series, "g": int(sw.get("g") or 0)}

def _b_space():
    S = _call("solar_seismic", "/api/solar_seismic")
    now = time.time()
    bins = [b for b in (S.get("bins") or []) if not b.get("partial") and b.get("kp") is not None]
    kp = [round(float(b["kp"]), 2) for b in bins[-24:]]
    kv = ((S.get("now") or {}).get("kp") or {})
    q = []
    for x in (S.get("map") or []):
        try:
            t = _epoch(x["t"])
            if now - 40 * 3600 <= t <= now + 60: q.append([int(t), round(float(x["mag"]), 1)])
        except Exception: pass
    out = {"quakes": sorted(q)}
    if kp and kv.get("value") is not None:
        out["space"] = {"kp": kp, "now": round(float(kv["value"]), 2), "g": int(kv.get("g") or 0)}
    if not out["quakes"] and "space" not in out: raise RuntimeError("no space data")
    return out

BUILDERS = (("wire", _b_wire), ("grid", _b_grid), ("space", _b_space))
_C = {"t": 0, "v": None, "busy": False, "good": {}}
_L = threading.Lock()

def _build():
    out, errs = {}, {}
    def one(k, fn):
        try: out[k] = fn()
        except Exception as ex: out[k] = None; errs[k] = type(ex).__name__
    ts = [threading.Thread(target=one, args=(k, fn), daemon=True) for k, fn in BUILDERS]
    for t in ts:
        t.start()
        if UPSTREAM: t.join(120)   # preview harness: one upstream request at a time
    for t in ts: t.join(45)
    now = time.time()
    with _L: prev = _C["v"] or {}; good = _C["good"]
    res = {"wire": out.get("wire"), "grid": out.get("grid"), "space": None, "quakes": None}
    sp = out.get("space")
    if sp: res["space"] = sp.get("space"); res["quakes"] = sp.get("quakes")
    for k in ("wire", "grid", "space", "quakes"):
        src = "space" if k in ("space", "quakes") else k
        if res.get(k) is not None and not (src in errs): good[k] = now
        elif prev.get(k) is not None and now - good.get(k, 0) < MAX_AGE: res[k] = prev[k]    # a blip keeps the last good section (max 10 min old)
        else: res[k] = None
    if errs: res["errors"] = errs
    res["ts"] = int(now); res["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res["asof"] = {k: int(good.get(k, 0)) for k in ("wire", "grid", "space", "quakes") if good.get(k)}
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
        if v is not None and age > 45 and not busy:
            _C["busy"] = True; threading.Thread(target=_refresh, daemon=True).start()
    if v is None:
        _refresh()
        with _L: v = _C["v"]
    return v

# ---------------------------------------------------------------- routes (/api/pulse/*)
def handle_get(path, qs):
    if path == "/api/pulse/live":
        try: return 200, live()
        except Exception as ex: return 503, {"error": "pulse data unavailable", "detail": type(ex).__name__}
    n = path[len("/api/pulse/"):] if path.startswith("/api/pulse/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as f: return 200, f.read(), FILES[n]
    return 404, {"error": "not found"}
