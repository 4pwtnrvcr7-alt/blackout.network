"""Alerts (standards-based Web Push, t341). Public side only: the service worker, the Alerts panel and the subscribe API.
GET  /sw.js                    service worker (root scope): shows pushed alerts, opens the story on tap. No fetch handler, no caching.
GET  /alerts.js, /alerts.css   the bell button + Alerts panel (also window.BN.enableAlerts() for the add-to-home-screen pop-up)
GET  /alerts/badge.png, /alerts/icon.png   notification badge (monochrome BN) and icon (BN tile)
GET  /api/alerts/config        VAPID PUBLIC key, levels, categories, whether public sending is switched on
POST /api/alerts/subscribe     {sub:{endpoint,keys:{p256dh,auth}}, level:"major"|"all", cats:[...], test:bool} (upsert = change prefs)
POST /api/alerts/unsubscribe   {endpoint}
POST /api/alerts/resubscribe   {old_endpoint, sub}  (service worker, after the browser rotates a subscription)
Subscriptions live in webpush.db, a Render-owned DB: the box mirrors it every minute over the signed sync channel and restores it
after a Render restart (render_rules.RENDER_OWNED). The box, never this node, holds the VAPID private key and sends the pushes
(webpush_notifier.py). Stored per subscriber: the push endpoint + its two public encryption keys, level, categories, browser family,
created/updated times. No IP address, no cookie, no name or email."""
import os, re, json, time, sqlite3, hashlib, threading
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "static", "alerts")
DB = os.path.join(BASE, "webpush.db")
CFG = os.path.join(BASE, "webpush_config.json")     # pushed by the box (render_rules.SYNC_JSON); holds no secrets
DEAD = os.path.join(BASE, "webpush_dead.json")      # pushed by the box: {sub_id: iso} for subscriptions the push service says have ended
LEVELS = {"major": 7, "all": 5}
CATS = [("war/conflict", "War & conflict"), ("natural disaster", "Natural disasters"), ("political", "Politics & government"),
        ("disease", "Disease & outbreaks"), ("cyber", "Cyber"), ("financial", "Financial"), ("space weather", "Space weather"),
        ("ufo/uap", "UFO / UAP"), ("spiritual/religious", "Religious"), ("other", "Other")]
CAT_KEYS = {k for k, _ in CATS}
PUSH_HOSTS = ("fcm.googleapis.com", "android.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com",
              "web.push.apple.com", ".push.apple.com", ".notify.windows.com", "push.api.chromium.org")   # browser push services only
B64U = re.compile(r"^[A-Za-z0-9_\-]+={0,2}$")
FILES = {"/sw.js": ("sw.js", "application/javascript"), "/alerts.js": ("alerts.js", "application/javascript"),
         "/alerts.css": ("alerts.css", "text/css"), "/alerts/badge.png": ("badge.png", "image/png"), "/alerts/icon.png": ("icon.png", "image/png")}
SITE_ORIGINS = ("https://blackout.network", "https://www.blackout.network")
_lock = threading.Lock(); _hits = {}

def _read(name):
    with open(os.path.join(D, name), "rb") as fh: return fh.read()

def cfg():
    try: c = json.load(open(CFG))
    except Exception: c = {}
    return c

def _db():
    c = sqlite3.connect(DB, timeout=20)
    c.execute("""CREATE TABLE IF NOT EXISTS subs(id TEXT PRIMARY KEY, endpoint TEXT UNIQUE NOT NULL, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
                 level TEXT NOT NULL DEFAULT 'major', cats TEXT NOT NULL DEFAULT '[]', test INTEGER NOT NULL DEFAULT 0, browser TEXT,
                 created TEXT NOT NULL, updated TEXT NOT NULL)""")
    return c

_purged = {"mt": None}
def _purge(c):
    """Delete subscriptions the box reported as ended (HTTP 404/410 from the push service), unless re-subscribed since."""
    try: mt = os.path.getmtime(DEAD)
    except OSError: return
    if _purged["mt"] == mt: return
    try: dead = json.load(open(DEAD))
    except Exception: return
    with c:
        for sid, at in (dead.items() if isinstance(dead, dict) else []):
            c.execute("DELETE FROM subs WHERE id=? AND updated<=?", (str(sid)[:40], str(at)[:25]))
    _purged["mt"] = mt

def sub_id(endpoint): return hashlib.sha256(endpoint.encode()).hexdigest()[:20]
def _iso(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _ok_endpoint(ep):
    if not isinstance(ep, str) or len(ep) > 1024 or not ep.startswith("https://"): return False
    h = (urlparse(ep).hostname or "").lower()
    return any(h == p or (p.startswith(".") and h.endswith(p)) for p in PUSH_HOSTS)

def _ok_key(k, lo, hi): return isinstance(k, str) and lo <= len(k) <= hi and bool(B64U.match(k))

def _limited(ip, n=30, win=600):
    t = time.time()
    with _lock:
        if len(_hits) > 5000: _hits.clear()
        q = [x for x in _hits.get(ip or "?", []) if t - x < win]; q.append(t); _hits[ip or "?"] = q
        return len(q) > n

def _same_origin(headers):
    o = (headers or {}).get("origin") or ""
    if not o: return True          # some browsers omit Origin on same-origin fetch; the endpoint allowlist still applies
    h = (urlparse(o).hostname or "").lower()
    return o in SITE_ORIGINS or h in ("localhost", "127.0.0.1") or h.endswith(".onrender.com")

def _browser(ua):
    ua = ua or ""
    os_ = "ios" if re.search(r"iPhone|iPad|iPod", ua) else "android" if "Android" in ua else "desktop"
    b = ("samsung" if "SamsungBrowser" in ua else "edge" if "Edg" in ua else "firefox" if re.search("Firefox|FxiOS", ua) else
         "chrome" if re.search("Chrome|CriOS", ua) else "safari" if "Safari" in ua else "other")
    return f"{b}/{os_}"

def _prefs(d):
    level = d.get("level") if d.get("level") in LEVELS else "major"
    cats = d.get("cats") if isinstance(d.get("cats"), list) else []
    cats = sorted({c for c in cats if c in CAT_KEYS})
    if len(cats) == len(CAT_KEYS): cats = []        # [] = every category
    return level, cats

def _parse_sub(s):
    if not isinstance(s, dict): return None
    ep = s.get("endpoint"); k = s.get("keys") or {}
    if not _ok_endpoint(ep) or not _ok_key(k.get("p256dh"), 80, 100) or not _ok_key(k.get("auth"), 16, 32): return None
    return ep, k["p256dh"], k["auth"]

def public_config():
    c = cfg()
    try: pub = _read("vapid_public.txt").decode().strip()
    except Exception: pub = ""
    return {"vapid_public_key": pub, "live": bool(c.get("webpush_live_sending")), "max_per_hour": int(c.get("max_per_hour", 6)),
            "levels": [{"key": "major", "label": "Major alerts only", "min_rank": 7, "default": True},
                       {"key": "all", "label": "All ranked alerts", "min_rank": 5}],
            "categories": [{"key": k, "label": l} for k, l in CATS]}

def handle_get(path, qs):
    if path in FILES:
        name, ct = FILES[path]
        try: return 200, _read(name), ct
        except FileNotFoundError: return 404, {"error": "not found"}
    if path == "/api/alerts/config":
        if os.path.exists(DB):
            try:
                c = _db()
                try: _purge(c)
                finally: c.close()
            except Exception: pass
        return 200, public_config()
    return 404, {"error": "not found"}

def handle_post(path, d, ip=None, qs=None, headers=None, raw=b""):
    if not _same_origin(headers): return 403, {"error": "cross-site request refused"}
    if _limited(ip): return 429, {"error": "Too many requests. Please wait a few minutes."}
    d = d if isinstance(d, dict) else {}
    if path == "/api/alerts/subscribe":
        p = _parse_sub(d.get("sub"))
        if not p: return 400, {"error": "This browser sent a push subscription we can't use."}
        ep, k1, k2 = p; level, cats = _prefs(d)
        test = 1 if (d.get("test") is True or (qs or {}).get("test") == ["1"]) else 0
        sid = sub_id(ep); now = _iso(); br = _browser((headers or {}).get("user-agent"))
        c = _db()
        try:
            _purge(c)
            with c:
                old = c.execute("SELECT test FROM subs WHERE id=?", (sid,)).fetchone()
                if old:
                    c.execute("UPDATE subs SET p256dh=?,auth=?,level=?,cats=?,test=?,browser=?,updated=? WHERE id=?",
                              (k1, k2, level, json.dumps(cats), max(test, old[0]), br, now, sid))
                else:
                    if c.execute("SELECT COUNT(*) FROM subs").fetchone()[0] >= 200000: return 503, {"error": "Alerts are full right now."}
                    c.execute("INSERT INTO subs(id,endpoint,p256dh,auth,level,cats,test,browser,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (sid, ep, k1, k2, level, json.dumps(cats), test, br, now, now))
        finally: c.close()
        return 200, {"ok": True, "id": sid, "level": level, "cats": cats, "live": public_config()["live"], "test": bool(test)}
    if path == "/api/alerts/unsubscribe":
        ep = d.get("endpoint")
        if not _ok_endpoint(ep): return 400, {"error": "unknown subscription"}
        c = _db()
        try:
            with c: n = c.execute("DELETE FROM subs WHERE id=?", (sub_id(ep),)).rowcount
        finally: c.close()
        return 200, {"ok": True, "removed": n}
    if path == "/api/alerts/resubscribe":
        p = _parse_sub(d.get("sub")); old = d.get("old_endpoint")
        if not p or not _ok_endpoint(old): return 400, {"error": "bad request"}
        ep, k1, k2 = p; now = _iso()
        c = _db()
        try:
            with c:
                r = c.execute("SELECT level,cats,test,created FROM subs WHERE id=?", (sub_id(old),)).fetchone()
                if not r: return 404, {"error": "unknown subscription"}
                c.execute("DELETE FROM subs WHERE id=?", (sub_id(old),))
                c.execute("INSERT OR REPLACE INTO subs(id,endpoint,p256dh,auth,level,cats,test,browser,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (sub_id(ep), ep, k1, k2, r[0], r[1], r[2], _browser((headers or {}).get("user-agent")), r[3], now))
        finally: c.close()
        return 200, {"ok": True}
    return 404, {"error": "not found"}
