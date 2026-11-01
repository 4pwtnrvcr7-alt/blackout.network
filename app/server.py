#!/usr/bin/env python3
"""blackout.network dashboard + scheduler (stdlib HTTP server)."""
import json, os, re, time, threading, secrets, hmac, sqlite3, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
import scanner
import push
import jets
import display_links

BASE = scanner.BASE
CONFIG = f"{BASE}/config.json"
NOTIFY = f"{BASE}/notify_settings.json"
PASSFILE = f"{BASE}/ADMIN_PASSCODE.txt"
PORT = int(os.environ.get("BLACKOUT_PORT", "8787"))
ALLOWED = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300, 360]   # scan interval choices, 5 min to 6 h (t225)
REFRESH_COOLDOWN = 120   # manual scans: at most one per 2 minutes (t225)
wake = threading.Event()
jet_wake = threading.Event()
jet_state = {"running": False, "last": None}
state = {"last_scan": None, "last_result": None, "next_scan": None, "last_manual": 0, "scanning": False}
fails = {}   # ip -> [timestamps] of bad passcodes

def load_json(p, default):
    try:
        with open(p) as f: return {**default, **json.load(f)}
    except Exception: return dict(default)
def save_json(p, d, mode=0o644):
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, indent=1)
    os.chmod(tmp, mode); os.replace(tmp, p)
def cfg(): return load_json(CONFIG, {"interval_minutes": 60, "push_min_rank": 7, "push_min_sources": 2})
NOTIFY_DEFAULT = {"phone": "", "channels": {"sms": False, "email": True, "app": True}, "updated": None}
def notify(): 
    d = load_json(NOTIFY, NOTIFY_DEFAULT); d["channels"] = {**NOTIFY_DEFAULT["channels"], **(d.get("channels") or {})}; return d
def passcode():
    if not os.path.exists(PASSFILE):
        fd = os.open(PASSFILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f: f.write(secrets.token_urlsafe(12) + "\n")
    os.chmod(PASSFILE, 0o600)
    return open(PASSFILE).read().strip()
def mask(phone): return f"***-***-{phone[-4:]}" if phone and len(phone) == 10 else ""
def norm_phone(s):
    d = re.sub(r"[\s().\-]", "", s or "")
    if d.startswith("+1"): d = d[2:]
    elif d.startswith("1") and len(d) == 11: d = d[1:]
    if not re.fullmatch(r"[2-9]\d{2}[2-9]\d{6}", d): return None
    return d
def public_settings():
    n = notify()
    return {"phone_masked": mask(n.get("phone")), "phone_saved": bool(n.get("phone")), "channels": n["channels"], "updated": n.get("updated"),
            "delivery_status": {"app": "active: delivered as a message in the Grok Bot chat by the hourly check",
                                "email": "not yet deliverable: no email sending mechanism configured",
                                "sms": "not yet deliverable: no SMS gateway configured"}}

def run_scan(trigger):
    state["scanning"] = True
    try:
        r = scanner.scan(trigger)
        if r.get("status") != "busy":
            state["last_scan"] = time.time(); state["last_result"] = r
            try: r["push"] = push.push_new()          # push hook runs after every completed scan
            except Exception as ex: r["push"] = {"status": "error", "error": str(ex)[:200]}
        return r
    finally:
        state["scanning"] = False

def scheduler():
    # first scan at startup if stale
    c = scanner.db(); last = c.execute("SELECT finished FROM scans ORDER BY id DESC LIMIT 1").fetchone(); c.close()
    if last:
        state["last_scan"] = scanner.parse_t(last[0]).timestamp()
    while True:
        iv = cfg()["interval_minutes"] * 60
        due = (state["last_scan"] or 0) + iv
        state["next_scan"] = due
        if time.time() >= due:
            try: run_scan("scheduled")
            except Exception: traceback.print_exc()
            continue
        wake.wait(timeout=min(60, max(1, due - time.time())))   # re-check config at least every 60s
        wake.clear()

def jet_loop():
    """Jet sampler: every min(jet_sample_minutes [default 5], interval_minutes). Writes only jets.db; never touches threat scoring."""
    while True:
        c = cfg(); st = jets.settings(c)
        jet_state["running"] = True
        try: jet_state["last"] = jets.run_pass(c)
        except Exception: traceback.print_exc()
        finally: jet_state["running"] = False
        jet_wake.wait(timeout=st["sample_minutes"] * 60); jet_wake.clear()

def q(sql, args=()):
    c = scanner.db()
    try: return [dict(r) for r in c.execute(sql, args)]
    finally: c.close()

def clusters_out(rows):
    for r in rows:
        r["families"] = json.loads(r["families"] or "[]"); r["links"] = json.loads(r["links"] or "[]")
    return rows

def api_state():
    cut = scanner.iso(scanner.now() - timedelta(days=7))
    main = clusters_out(q("SELECT * FROM clusters WHERE watchlist=0 AND COALESCE(event_time, first_seen)>=? ORDER BY score DESC, event_time DESC LIMIT 150", (cut,)))
    watch = clusters_out(q("SELECT * FROM clusters WHERE watchlist=1 AND COALESCE(event_time, first_seen)>=? ORDER BY score DESC, event_time DESC LIMIT 150", (cut,)))
    nwatch = q("SELECT COUNT(*) n FROM clusters WHERE watchlist=1")[0]["n"]
    vol = q("""SELECT substr(COALESCE(event_time, first_seen),1,10) d, category, COUNT(*) n FROM clusters
               WHERE COALESCE(event_time, first_seen)>=? GROUP BY d, category ORDER BY d""", (cut,))
    trend = q("""SELECT substr(COALESCE(event_time, first_seen),1,10) d, MAX(score) mx, ROUND(AVG(score),1) avg,
               SUM(score>=?) high FROM clusters WHERE COALESCE(event_time, first_seen)>=? AND watchlist=0 GROUP BY d ORDER BY d""", (scanner.HIGH, cut))
    geo = q("SELECT lat, lon, score, title, category, watchlist FROM clusters WHERE lat IS NOT NULL AND COALESCE(event_time, first_seen)>=?", (cut,))
    health = q("SELECT * FROM source_health ORDER BY ok DESC, name")
    scans = q("SELECT * FROM scans ORDER BY id DESC LIMIT 10")
    pub = ""
    try: pub = open(f"{BASE}/PUBLIC_URL.txt").read().strip()
    except Exception: pass
    return {"generated": scanner.iso(scanner.now()), "high_threshold": scanner.HIGH, "main": main, "watchlist": watch, "watchlist_count": nwatch,
            "volume": vol, "trend": trend, "geo": geo, "sources": health, "scans": scans,
            "interval_minutes": cfg()["interval_minutes"], "allowed_intervals": ALLOWED,
            "next_scan": scanner.iso(datetime.fromtimestamp(state["next_scan"], timezone.utc)) if state["next_scan"] else None,
            "scanning": state["scanning"], "settings": public_settings(), "public_url": pub}

# ---- add-on modules (Story Arcs, ...): separate files listed in addons.py, hot-reloaded on change ----
import importlib
_addon_mods = {}
_addon_lock = threading.Lock()
def _addon_mod(name):
    mt = os.path.getmtime(f"{BASE}/{name}.py")
    with _addon_lock:
        m = _addon_mods.get(name)
        if m is None or m[0] != mt:
            mod = importlib.reload(m[1]) if m else importlib.import_module(name)
            _addon_mods[name] = (mt, mod)
        return _addon_mods[name][1]
def addon_for(path):
    try: routes = _addon_mod("addons").ROUTES
    except Exception: traceback.print_exc(); return None
    for pre, name in routes.items():
        if path == pre or path.startswith(pre + "/"): return _addon_mod(name)
    return None

# "Report a problem" widget (reports.py): added to every HTML page that doesn't already load it (dashboard.html loads it itself).
_RW = b'<link rel="stylesheet" href="/api/report/app.css"><script src="/api/report/app.js" defer></script>'
# PWA / home-screen support + site title (pwa.py, static/pwa/): every full HTML page served through send() gets the manifest, icons,
# iOS/Android web-app meta tags and the install guide in its <head>, and the public title "Know first. Be ready." (2026-10-31).
SITE_TITLE = b"Know first. Be ready."
# Light/dark theme (t323): set data-theme on <html> before first paint (saved choice, else the OS setting) + preload the self-hosted fonts.
THEME_HEAD = (b'<script>(function(){var d=document.documentElement,t;try{t=localStorage.getItem("bn_theme")}catch(e){}'
              b'if(t!=="light"&&t!=="dark")t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";'
              b'd.setAttribute("data-theme",t);d.style.colorScheme=t;var m=document.querySelector(\'meta[name="theme-color"]\');if(m)m.content=t=="light"?"#f6f7f9":"#0b0d10"})()</script>'
              b'<link rel="icon" type="image/svg+xml" href="/img/favicon.svg">'
              b'<link rel="preload" href="/fonts/montserrat-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>'
              b'<link rel="preload" href="/fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>')
_BRANDED = b"BLACKOUT.NETWORK"
PWA_HEAD = (b'<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">'
            b'<link rel="icon" type="image/png" sizes="32x32" href="/icons/icon-32.png"><link rel="icon" type="image/png" sizes="16x16" href="/icons/icon-16.png">'
            b'<meta name="theme-color" content="#0b0d10"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
            b'<meta name="apple-mobile-web-app-title" content="BLACKOUT"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
            b'<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="mask-icon" href="/img/safari-pinned-tab.svg" color="#0B0D10">'   # BN master tile icon set (t333)
            b'<meta name="msapplication-TileColor" content="#0B0D10"><meta name="msapplication-TileImage" content="/icons/icon-mstile-150.png">'
            b'<link rel="stylesheet" href="/install-guide.css"><script src="/install-guide.js" defer></script>')
ALERTS_HEAD = b'<link rel="stylesheet" href="/alerts.css"><script src="/alerts.js" defer></script>'   # Alerts bell + panel (webpush.py, t341)
_OLD_TAGLINES = [b"The world's threats, scored and sourced, before cable news catches up.", b"The world&#x27;s threats, scored and sourced, before cable news catches up.",
                 b"The world&#39;s threats, scored and sourced, before cable news catches up."]
_DASH_FALLBACK = (b'<header class="bn-top" id="bn_topbar"><div class="bn-tbar"><a class="bn-logo" href="/">BLACKOUT.<b>NETWORK</b></a></div>'
                  b'<div class="bn-pop" id="bn_settings" hidden><div class="ctl"><span id="status">loading\xe2\x80\xa6</span><button class="pri" id="refresh">Manual refresh</button>'
                  b'<label>Scans every <select id="interval"></select></label><span id="msg"></span></div></div></header>')
def dashboard_page():
    """dashboard.html with the shared top bar + sidebar (sitenav.py, t320/t321) in place of <!--BN_TOP-->."""
    b = open(f"{BASE}/dashboard.html", "rb").read()
    try:
        import sitenav
        top = sitenav.dashboard_top().encode("utf-8")
    except Exception:
        traceback.print_exc(); top = _DASH_FALLBACK
    return b.replace(b"<!--BN_TOP-->", top, 1)

def pwa_head(b):
    try:
        h = b[:4000].lower().find(b"<head>")
        if h >= 0 and b"<html" in b[:4000].lower() and b"bn_theme" not in b[:30000]:   # light/dark theme before first paint (t323)
            b = b[:h + 6] + THEME_HEAD + b[h + 6:]
        al = b[:120000].lower(); j = al.find(b"</head>")   # Alerts bell + Web Push (webpush.py, t341)
        if j >= 0 and b"<html" in al[:4000] and b"/alerts.js" not in al[:j]: b = b[:j] + ALERTS_HEAD + b[j:]
        lo = b[:20000].lower(); i = lo.find(b"</head>")
        if i < 0 or b"<html" not in lo: return b          # fragments (cards, iframes, JSON) are left alone
        if b"/manifest.webmanifest" not in lo[:i]: b = b[:i] + PWA_HEAD + b[i:]
        # per-page titles such as "How we score | BLACKOUT.NETWORK" (sitenav.py, t302) are kept; any other title becomes the site title
        b = re.sub(rb"<title>([^<]*)</title>", lambda m: m.group(0) if _BRANDED in m.group(1) else b"<title>" + SITE_TITLE + b"</title>", b, count=1)
        b = re.sub(rb'(<meta (?:property="og:title"|name="twitter:title") content=")([^"]*)(")', lambda m: m.group(0) if _BRANDED in m.group(2) else m.group(1) + SITE_TITLE + m.group(3), b)
        b = re.sub(rb'(<meta name="viewport" content="width=device-width,\s*initial-scale=1)(")', rb"\g<1>,viewport-fit=cover\g<2>", b, count=1)
        for t in _OLD_TAGLINES: b = b.replace(t, SITE_TITLE)
        return b
    except Exception: return b

# t338/t343: Render's free tier drops some of a page's ~40 parallel requests (502/503). (1) every same-origin JS/CSS URL in a page gets
# ?v=<build> so Cloudflare and browsers can cache it for a year (Cache-Control immutable below) and the origin rarely sees asset requests;
# (2) BN_RETRY_HEAD retries a failed script/stylesheet (twice, with backoff) and same-origin GET fetches that come back 502/503/504.
_ASSET_RE = re.compile(rb'((?:src|href)=["\']?)(/?(?:api/[a-z_]+/[\w.-]+|sitenav|theme|install-guide|alerts|linkguard|bn-eggs)\.(?:js|css)|/?api/[a-z_]+/[\w.-]+\.(?:js|css))(["\'\s>])')
_ASSET_V = {"t": 0, "v": b"0"}
def asset_version():
    now = time.time()
    if now - _ASSET_V["t"] > 20:
        h = 0
        try:
            for d in [BASE, f"{BASE}/static"] + [e.path for e in os.scandir(BASE) if e.is_dir() and e.name.endswith("_static")]:
                for e in os.scandir(d):
                    if e.name.endswith((".js", ".css", ".html")): h = (h * 31 + int(e.stat().st_mtime) + len(e.name)) % 0xFFFFFFFFFF
        except Exception: pass
        _ASSET_V.update(t=now, v=format(h, "x").encode())
    return _ASSET_V["v"]
def version_assets(b):
    try:
        v = asset_version(); lo = b[:6000].lower(); h = lo.find(b"<head>")
        if h >= 0 and b"<html" in lo and b"bnRetry" not in b[:40000]: b = b[:h + 6] + BN_RETRY_HEAD + b[h + 6:]
        j = b.rfind(b"</body>")   # dead-link guard + easter eggs (bn_extras.py) on every full page
        if j > 0 and b"<html" in lo and b"/linkguard.js" not in b: b = b[:j] + b'<script src="/linkguard.js" defer></script><script src="/bn-eggs.js" defer></script>' + b[j:]
        return _ASSET_RE.sub(lambda m: m.group(1) + m.group(2) + b"?v=" + v + m.group(3), b)
    except Exception: return b
BN_RETRY_HEAD = (b'<script>/*bnRetry*/(function(){if(window.__bnRetry)return;window.__bnRetry=1;var o=location.origin;'
  b'addEventListener("error",function(e){var t=e.target;if(!t||t===window||!t.tagName)return;var tag=t.tagName,u=tag=="SCRIPT"?t.src:tag=="LINK"&&t.rel=="stylesheet"?t.href:"";'
  b'if(!u||u.indexOf(o)!==0)return;var n=+(t.getAttribute("data-bn-retry")||0);if(n>=2)return;setTimeout(function(){var c=document.createElement(tag);'
  b'if(tag=="SCRIPT"){c.src=u+(u.indexOf("?")<0?"?":"&")+"r="+(n+1);c.async=false}else{c.rel="stylesheet";c.href=u+(u.indexOf("?")<0?"?":"&")+"r="+(n+1)}'
  b'c.setAttribute("data-bn-retry",n+1);(t.parentNode||document.head).insertBefore(c,t.nextSibling)},700*(n+1)*(n+1))},true);'
  b'var F=window.fetch;if(!F)return;window.fetch=function(i,init){var m=((init&&init.method)||(i&&i.method)||"GET").toUpperCase(),u=typeof i=="string"?i:(i&&i.url)||"";'
  b'var same=u.indexOf("://")<0||u.indexOf(o)===0;if(m!="GET"||!same||/\\/api\\/stream/.test(u))return F.apply(this,arguments);var a=arguments,s=this,k=0;'
  b'return new Promise(function(res,rej){(function go(){F.apply(s,a).then(function(r){if((r.status==502||r.status==503||r.status==504)&&k<3){k++;setTimeout(go,500*k*k)}else res(r)},'
  b'function(err){if(k<2&&!(init&&init.signal&&init.signal.aborted)){k++;setTimeout(go,600*k)}else rej(err)})})()})}})()</script>')

def report_widget(b):
    try:
        i = b.rfind(b"</body>")
        if i < 0 or b"/api/report/app.js" in b or b"data-bn-noreport" in b or b"http-equiv=refresh" in b[:600]: return b
        return b[:i] + _RW + b[i:]
    except Exception: return b

class H(BaseHTTPRequestHandler):
    server_version = "Blackout/1.0"
    def log_message(self, fmt, *a): pass
    def ip(self): return self.headers.get("CF-Connecting-IP") or self.client_address[0]
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (json.dumps(body, default=str) if ctype == "application/json" else body).encode()
        if ctype == "application/json" and b"://" in b:   # t347: show people the human page, not the raw API/RSS endpoint (display only)
            try: b = display_links.rewrite_json(b.decode("utf-8")).encode("utf-8")
            except Exception: pass
        if ctype == "text/html": b = version_assets(report_widget(pwa_head(b)))
        self.send_response(code); self.send_header("Content-Type", ctype if ctype.startswith("image/") else ctype + "; charset=utf-8")
        versioned = "v=" in (self.path.split("?", 1)[1] if "?" in self.path else "") and code == 200 and ctype in ("application/javascript", "text/css")
        self.send_header("Cache-Control", "public, max-age=2592000, immutable" if ctype.startswith("font/") else "public, max-age=31536000, immutable" if versioned else "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = min(int(self.headers.get("Content-Length") or 0), 2_000_000 if self.path.startswith("/api/reports/") else 16000 if self.path.startswith("/api/report") else 10000)
        self._raw = self.rfile.read(n)   # kept for add-ons that accept form posts (newsletter: no-JS forms, RFC 8058 one-click unsubscribe)
        try: return json.loads(self._raw or b"{}")
        except Exception: return {}
    def authed(self, d):
        ip = self.ip(); t = time.time()
        fails[ip] = [x for x in fails.get(ip, []) if t - x < 600]
        if len(fails[ip]) >= 5: return "locked"
        given = str(d.get("passcode") or self.headers.get("X-Admin-Passcode") or "")
        if given and hmac.compare_digest(given.encode(), passcode().encode()): return "ok"
        fails[ip].append(t); return "bad"

    TAB_PATHS = set("wire noise thread broadcasts streams radio network grid ai solar heatmap midterms spacex figures preppers tips weather trends "
                    "politics gunlaws finance jets medical resources bushcraft intel ranked games government maps".split())
    def not_found_page(self, path):
        """t347: a dashboard tab name typed as a path (/maps) -> 302 to /#maps; any other unknown non-API path -> the HTML 404 page.
        API / internal paths keep their JSON 404. Returns True if a response was sent."""
        if path.startswith(("/api/", "/internal/")): return False
        seg = path.strip("/").lower()
        if seg == "elon": seg = "figures"   # t353: the old Elon Musk tab is now Key Figures
        if seg in self.TAB_PATHS:
            self.send_response(302); self.send_header("Location", "/#" + seg); self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); return True
        try:
            import bn_extras; self.send(404, bn_extras.page_404(path), "text/html"); return True
        except Exception: return False

    def do_GET(self):
        u = urlparse(self.path); qs = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, dashboard_page(), "text/html")
            if u.path == "/api/state": return self.send(200, api_state())
            if u.path == "/api/health":
                return self.send(200, {"ok": True, "scanning": state["scanning"], "last_scan": state["last_scan"], "interval_minutes": cfg()["interval_minutes"]})
            if u.path == "/api/settings": return self.send(200, public_settings())
            if u.path == "/api/config": return self.send(200, {"interval_minutes": cfg()["interval_minutes"], "allowed": ALLOWED})
            if u.path == "/api/jets": return self.send(200, {**jets.api_state(cfg()), "sampler": jet_state})
            if u.path in ("/api/jet_spikes/new", "/api/jet_spikes"):
                since = (qs.get("since") or [None])[0]
                sd = scanner.parse_t(since) if since else scanner.now() - timedelta(hours=1 if u.path.endswith("new") else 24 * 30)
                if not sd: return self.send(400, {"error": "since must be ISO-8601, e.g. 2026-10-29T04:00:00Z"})
                items = jets.new_spikes(sd)
                return self.send(200, {"since": scanner.iso(sd), "now": scanner.iso(scanner.now()), "count": len(items), "items": items,
                                       "note": "Informational only. Jet spikes never change threat ranks/scores."})
            if u.path == "/api/new_high":
                since = (qs.get("since") or [None])[0]
                mn = int((qs.get("min") or [scanner.HIGH])[0])
                mode = (qs.get("mode") or ["alert"])[0]
                sd = scanner.parse_t(since) if since else scanner.now() - timedelta(hours=1)
                if not sd: return self.send(400, {"error": "since must be ISO-8601, e.g. 2026-10-29T04:00:00Z"})
                if mode == "alert":   # push hook: rank >= push_min_rank AND confirmed by >= push_min_sources independent source families
                    cf = cfg(); pr = int(cf.get("push_min_rank", 7)); ps = int(cf.get("push_min_sources", 2))
                    rows = clusters_out(q("""SELECT * FROM clusters WHERE watchlist=0 AND high_at>=? AND rank>=? AND eff_families>=?
                                             ORDER BY rank DESC, score DESC""", (scanner.iso(sd), pr, ps)))
                else:                 # mode=all: every main-feed item with score>=min or rank>=7
                    rows = clusters_out(q("SELECT * FROM clusters WHERE watchlist=0 AND high_at>=? AND (score>=? OR rank>=7) ORDER BY rank DESC, score DESC",
                                          (scanner.iso(sd), mn)))
                return self.send(200, {"since": scanner.iso(sd), "min_score": mn, "mode": mode,
                                       "push_rule": {"push_min_rank": int(cfg().get("push_min_rank", 7)), "push_min_sources": int(cfg().get("push_min_sources", 2))} if mode == "alert" else None, "count": len(rows), "now": scanner.iso(scanner.now()),
                                       "items": [{k: r[k] for k in ("cluster_id", "score", "confidence", "category", "title", "location", "lat", "lon",
                                                                     "event_time", "high_at", "families", "links", "brief", "rank", "rising", "eff_families")} for r in rows]})
            m = addon_for(u.path)
            if m and hasattr(m, "handle_stream"): return m.handle_stream(u.path, qs, self)   # long-lived add-on responses (SSE /api/stream)
            if m:
                r = m.handle_get(u.path, qs)
                if not (r and r[0] == 404 and self.not_found_page(u.path)): return self.send(*r)
                return
            if self.not_found_page(u.path): return
            return self.send(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError): return
        except Exception as ex:
            traceback.print_exc(); return self.send(500, {"error": str(ex)})

    def do_POST(self):
        u = urlparse(self.path); d = self.body()
        try:
            if u.path == "/api/refresh":
                left = REFRESH_COOLDOWN - (time.time() - state["last_manual"])
                if left > 0: return self.send(429, {"status": "rate_limited", "retry_after_s": int(left) + 1})
                if state["scanning"]: return self.send(409, {"status": "busy"})
                state["last_manual"] = time.time()
                r = run_scan("manual")
                wake.set()
                return self.send(200, r)
            if u.path == "/api/interval":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                try: m = int(d.get("minutes"))
                except Exception: m = None
                if m not in ALLOWED: return self.send(400, {"error": f"minutes must be one of {ALLOWED}"})
                c = cfg(); c["interval_minutes"] = m; save_json(CONFIG, c); wake.set()
                return self.send(200, {"status": "ok", "interval_minutes": m})
            if u.path == "/api/jets/settings":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                c = cfg()
                if "k" in d:
                    try: k = round(float(d["k"]), 2)
                    except Exception: k = None
                    if k is None or not (jets.K_MIN <= k <= jets.K_MAX): return self.send(400, {"error": f"k must be between {jets.K_MIN} and {jets.K_MAX}"})
                    c["jet_spike_k"] = k
                if "enabled" in d: c["jet_spike_alerts_enabled"] = bool(d["enabled"])
                save_json(CONFIG, c)
                return self.send(200, {"status": "ok", "jet_spike_k": c.get("jet_spike_k", 2.0), "jet_spike_alerts_enabled": c.get("jet_spike_alerts_enabled", True)})
            if u.path == "/api/settings":
                a = self.authed(d)
                if a != "ok": return self.send(429 if a == "locked" else 403, {"error": "too many attempts, wait 10 min" if a == "locked" else "admin passcode required"})
                n = notify()
                if "phone" in d and str(d["phone"]).strip() != "":
                    p = norm_phone(str(d["phone"]))
                    if not p: return self.send(400, {"error": "Phone must be a valid US 10-digit number, e.g. (555) 555-0100"})
                    n["phone"] = p
                if d.get("clear_phone"): n["phone"] = ""
                ch = d.get("channels") or {}
                for k in ("sms", "email", "app"):
                    if k in ch: n["channels"][k] = bool(ch[k])
                if n["channels"]["sms"] and not n["phone"]:
                    return self.send(400, {"error": "Save a valid phone number before enabling SMS"})
                n["updated"] = scanner.iso(scanner.now())
                save_json(NOTIFY, n, 0o600)
                return self.send(200, {"status": "saved", **public_settings()})
            m = addon_for(u.path)
            if m and hasattr(m, "handle_post"):
                import inspect
                sig = inspect.signature(m.handle_post).parameters
                if "headers" in sig:   # newsletter: same-origin check, query-string token, raw form body
                    return self.send(*m.handle_post(u.path, d if isinstance(d, dict) else {}, ip=self.ip(), qs=parse_qs(u.query),
                                                    headers={k.lower(): v for k, v in self.headers.items()}, raw=getattr(self, "_raw", b"")))
                if "ip" in sig: return self.send(*m.handle_post(u.path, d, ip=self.ip()))   # in-memory rate limiting only
                return self.send(*m.handle_post(u.path, d))
            return self.send(404, {"error": "not found"})
        except Exception as ex:
            traceback.print_exc(); return self.send(500, {"error": str(ex)})

if __name__ == "__main__":
    passcode()
    if not os.path.exists(CONFIG): save_json(CONFIG, {"interval_minutes": 60})
    if not os.path.exists(NOTIFY): save_json(NOTIFY, NOTIFY_DEFAULT, 0o600)
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=jet_loop, daemon=True).start()
    try: import newsletter; newsletter.ensure_worker(force=True)   # newsletter scheduler: separate light process (newsletter_worker.py)
    except Exception: traceback.print_exc()
    print(f"Blackout dashboard on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
