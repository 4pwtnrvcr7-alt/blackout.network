"""Visitor problem reports, public side (runs on the box AND on the Render public node).

Visitors flag a broken page, wrong data, a dead source link, a visual glitch, etc. with the "Report a problem" button
(reports_static/app.js, injected on every dashboard page). Privacy rules enforced here, server-side:
  * page URLs keep scheme://host/path only (query strings and fragments that could carry tokens are dropped; the
    dashboard tab hash is kept only if it is a plain tab name), no cookies, no headers except the User-Agent the visitor saw
    in the preview, no form contents, no localStorage;
  * the visitor IP is never stored: only a salted, daily-rotating HMAC (16 hex) used for rate limiting;
  * honeypot + minimum fill time + per-IP-hash and global rate limits + size limits + validation; all text is stored as plain
    text and escaped on output (textContent / html.escape);
  * write-only from the public side: there is NO listing or search endpoint. One report's status can be looked up only by its
    unguessable reference ID (BN-XXXX-XXXX, 40 random bits, Crockford base32), lookups are rate-limited per IP hash, and
    missing or malformed IDs get the same generic "not found".

Box node (this file on 127.0.0.1:8787): submissions go straight into reports.db (reports_box.py, box-only).
Render node (BN_WEB_ONLY=1): submissions go into a small local SQLite queue (report_queue.db under BN_STATE_DIR, /tmp on
Render). The box pulls and acknowledges them every sync cycle (~60 s, render_sync.py -> reports_sync.py) and pushes back only
the public view of each report (status, timeline, queue position, REVIEWED+APPROVED public replies). Render's free-tier disk
is ephemeral: a report submitted in the seconds before a restart, and not yet pulled, can be lost (loss window <= one sync
cycle); statuses are re-pushed automatically after a restart.

Routes (addons.py): /api/report/* , /api/reports/* , /report-status , /report-status/<id>
  POST /api/report                         submit (public)
  GET  /api/report/config                  categories, limits, build, privacy note (public)
  GET  /api/report/<id>/status             one report's public view (public, rate-limited, generic 404)
  GET  /api/reports/stats                  aggregate, non-identifying queue stats (public)
  GET  /api/report/app.js|app.css|status.js|status.css   widget + status page assets
  GET  /report-status[/<id>]               public status page (noindex)
  GET  /api/reports/pull                   HMAC-signed with BN_SYNC_SECRET (Render only): unacknowledged reports + usage counts
  POST /api/reports/ack                    HMAC-signed: {"ids": [...]} -> private context deleted from the Render queue
  POST /api/reports/status                 HMAC-signed: public views + stats pushed down from the box"""
import os, re, json, time, hmac, hashlib, secrets, sqlite3, threading, unicodedata, html
from urllib.parse import urlsplit

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "reports_static")
WEB_ONLY = os.environ.get("BN_WEB_ONLY") == "1"
NODE = "render" if WEB_ONLY else "box"
QUEUE_DB = os.environ.get("BN_REPORT_QUEUE") or os.path.join(os.environ.get("BN_STATE_DIR", "/tmp/bn_state"), "report_queue.db")
VERSION = "reports-1.0"
BUILD = (os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or ("render" if WEB_ONLY else "box")
FILES = {"app.js": "application/javascript", "app.css": "text/css", "status.js": "application/javascript", "status.css": "text/css"}

CATEGORIES = [("broken_page", "Broken page or feature"), ("wrong_data", "Wrong or outdated data"),
              ("dead_link", "Missing or dead source link"), ("visual", "Visual glitch"), ("performance", "Slow or unresponsive"),
              ("accessibility", "Accessibility problem"), ("suggestion", "Suggestion"), ("other", "Something else")]
CAT = dict(CATEGORIES)
STATUS_INFO = {
    "received": ("Received", "Your report reached the public site and is on its way to the review queue (usually within a minute or two)."),
    "open": ("Open", "We have your report. It is waiting in the review queue."),
    "in_progress": ("In progress", "Someone is working on it now."),
    "resolved": ("Resolved", "We fixed it or answered it. Thank you for flagging it."),
    "wont_fix": ("Won't fix", "We reviewed it and decided not to change anything. If we wrote a response, it is shown below."),
    "duplicate": ("Duplicate", "Someone already reported the same problem. Follow the original report for updates."),
}
LIMITS = {"description": 2000, "title": 300, "item_id": 120, "url": 500, "ua": 400, "js_errors": 10, "js_error_len": 300}
SUBMIT_RATE = [(5, 600), (20, 86400)]          # per IP hash
SUBMIT_GLOBAL = (300, 3600)                    # whole node
LOOKUP_RATE = (30, 600)                        # per IP hash, any lookup
MISS_RATE = (10, 600)                          # per IP hash, not-found lookups (enumeration guard)
MIN_FILL_MS = 1500                             # faster than this = bot (silently dropped, like the honeypot)
ALPH = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"     # Crockford base32 (no I L O U)
ID_RE = re.compile(r"^BN-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")
PRIVACY = ("We send only what is listed in the preview: your category and description, the page address without any query "
           "string, the dashboard tab, the time, your browser's user agent, window size, language and time zone, the site build, the "
           "last scan time on screen and up to 10 recent script error messages from this page. No cookies, passwords, form contents, "
           "account data or IP address are stored; the server keeps only a daily-rotating anonymous hash to stop spam. "
           "Your reference ID is the only way to look up a report, so keep it if you want to follow up.")

_SALT = secrets.token_bytes(32)                # per-process; combined with the UTC date -> daily-rotating, irreversible IP hash
def ip_hash(ip):
    return hmac.new(_SALT, f"{time.strftime('%Y-%m-%d', time.gmtime())}|{ip or '?'}".encode(), hashlib.sha256).hexdigest()[:16]

def new_id():
    r = secrets.randbits(40); s = "".join(ALPH[(r >> (5 * i)) & 31] for i in range(8))
    return f"BN-{s[:4]}-{s[4:]}"
def norm_id(s):
    s = re.sub(r"[\s_]", "", str(s or "")).upper().replace("O", "0").replace("I", "1").replace("L", "1")
    if re.fullmatch(r"BN[0-9A-Z]{8}", s): s = f"BN-{s[2:6]}-{s[6:]}"
    return s if ID_RE.match(s) else None

# ---------------------------------------------------------------- rate limiting (in memory, per process)
_rl = {}; _rl_lock = threading.Lock()
def _hit(key, n, window, record=True):
    t = time.time()
    with _rl_lock:
        q = [x for x in _rl.get(key, []) if t - x < window]
        if len(q) >= n: _rl[key] = q; return int(window - (t - q[0])) + 1
        if record: q.append(t)
        _rl[key] = q
        if len(_rl) > 50000:
            for k in list(_rl)[:10000]: _rl.pop(k, None)
    return 0

# ---------------------------------------------------------------- sanitising
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_TOKENISH = re.compile(r"[A-Za-z0-9_\-]{32,}")
def clean_text(s, n, multiline=False):
    s = unicodedata.normalize("NFC", str(s or ""))
    s = _CTRL.sub("", s.replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline: s = s.replace("\n", " ")
    s = re.sub(r"\n{4,}", "\n\n\n", s).strip()
    return s[:n]
def clean_url(u, n=500):
    """scheme://host[:port]/path only: no userinfo, query or fragment (they can carry tokens)."""
    try:
        p = urlsplit(str(u or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname: return ""
        host = p.hostname + (f":{p.port}" if p.port else "")
        return f"{p.scheme}://{host}{p.path or '/'}"[:n]
    except Exception: return ""
def clean_source_url(u, n=500):
    """Source link of an alert card (public article URL from our own data): keep the query (many feeds need it) but no
    fragment/userinfo, and drop it entirely if it looks like it carries a credential."""
    try:
        p = urlsplit(str(u or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname: return ""
        if re.search(r"(?i)(token|key|secret|session|passw|auth|sig)=", p.query or ""): q = ""
        else: q = ("?" + p.query) if p.query else ""
        host = p.hostname + (f":{p.port}" if p.port else "")
        return f"{p.scheme}://{host}{p.path or '/'}{q}"[:n]
    except Exception: return ""
def clean_hash(h):
    h = str(h or "").lstrip("#")
    h = re.split(r"[?&=]", h, 1)[0]
    h = re.sub(r"[^A-Za-z0-9_\-/.]", "", h)[:60]
    return ("#" + h) if h and not _TOKENISH.search(h) else ""
def clean_err(e):
    if not isinstance(e, dict): e = {"msg": str(e)}
    msg = clean_text(e.get("msg"), LIMITS["js_error_len"])
    msg = re.sub(r"https?://[^\s)'\"]+", lambda m: clean_url(m.group(0)) or "[url]", msg)
    msg = _TOKENISH.sub("[redacted]", msg)
    out = {"msg": msg, "src": clean_url(e.get("src")), "line": int(e["line"]) if str(e.get("line", "")).isdigit() else None,
           "kind": e.get("kind") if e.get("kind") in ("error", "unhandledrejection", "resource") else "error"}
    t = str(e.get("t") or "")
    if re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", t): out["t"] = t[:30]
    return out
def _num(v, lo, hi):
    try: v = float(v)
    except Exception: return None
    return v if lo <= v <= hi else None

def validate(d):
    """-> (error | None, record). record = what gets stored (all plain text, sanitised)."""
    if not isinstance(d, dict): return "invalid request", None
    cat = str(d.get("category") or "")
    if cat not in CAT: return "Please choose a category.", None
    desc = clean_text(d.get("description"), LIMITS["description"] + 1, multiline=True)
    if len(desc) > LIMITS["description"]: return f"Description is limited to {LIMITS['description']} characters.", None
    it = d.get("item") if isinstance(d.get("item"), dict) else {}
    item = {"id": clean_text(it.get("id"), LIMITS["item_id"]), "title": clean_text(it.get("title"), LIMITS["title"]),
            "source_url": clean_source_url(it.get("source_url") or it.get("url")),
            "kind": it.get("kind") if it.get("kind") in ("wire", "watchlist", "timeline", "card") else ("card" if it else "")}
    item = {k: v for k, v in item.items() if v}
    if item.get("id") and not re.fullmatch(r"[A-Za-z0-9_.:\-]{1,120}", item["id"]): item.pop("id")
    c = d.get("context") if isinstance(d.get("context"), dict) else {}
    vw = c.get("viewport") if isinstance(c.get("viewport"), dict) else {}
    ctx = {"url": clean_url(c.get("url")), "hash": clean_hash(c.get("hash")),
           "tab": re.sub(r"[^a-z0-9_\-]", "", str(c.get("tab") or "").lower())[:40],
           "client_time": str(c.get("client_time") or "")[:30] if re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", str(c.get("client_time") or "")) else "",
           "user_agent": clean_text(c.get("user_agent"), LIMITS["ua"]),
           "viewport": {"w": _num(vw.get("w"), 0, 20000), "h": _num(vw.get("h"), 0, 20000), "dpr": _num(vw.get("dpr"), 0, 10)},
           "language": re.sub(r"[^A-Za-z0-9\-,]", "", str(c.get("language") or ""))[:35],
           "timezone": re.sub(r"[^A-Za-z0-9_+\-/]", "", str(c.get("timezone") or ""))[:64],
           "build": re.sub(r"[^A-Za-z0-9_.\-]", "", str(c.get("build") or ""))[:40],
           "last_scan_shown": clean_text(c.get("last_scan_shown"), 80),
           "online": c.get("online") if isinstance(c.get("online"), bool) else None,
           "js_errors": [clean_err(e) for e in (c.get("js_errors") or [])[:LIMITS["js_errors"]]] if isinstance(c.get("js_errors"), list) else []}
    if not ctx["url"]: return "Missing page address.", None
    if not desc and not item and cat in ("suggestion", "other"): return "Please add a short description.", None
    return None, {"category": cat, "description": desc, "item": item, "context": ctx}

def public_view(rec):
    """The only parts of a report the status page ever shows: the visitor's own category, description, page and item title."""
    ctx = rec.get("context") or {}
    return {"category": rec["category"], "category_label": CAT.get(rec["category"], rec["category"]),
            "description": rec.get("description") or "", "page": (ctx.get("url") or "") + (ctx.get("hash") or ""),
            "item_title": (rec.get("item") or {}).get("title", "")}

# ---------------------------------------------------------------- Render queue (also usable on the box for tests)
_qlock = threading.Lock()
def qdb():
    os.makedirs(os.path.dirname(QUEUE_DB), mode=0o700, exist_ok=True)
    c = sqlite3.connect(QUEUE_DB, timeout=20); c.row_factory = sqlite3.Row
    c.executescript("""PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS queue(id TEXT PRIMARY KEY, created_at TEXT, record_json TEXT, public_json TEXT, ip_hash TEXT, acked_at TEXT);
      CREATE TABLE IF NOT EXISTS status(id TEXT PRIMARY KEY, json TEXT, updated_at TEXT);
      CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);""")
    try: os.chmod(QUEUE_DB, 0o600)
    except Exception: pass
    return c
def _meta(c, k, v=None):
    if v is None:
        r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone(); return r[0] if r else None
    c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))
def iso(t=None): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t or time.time()))

def _box():
    import importlib, reports_box
    mt = os.path.getmtime(reports_box.__file__)
    if getattr(reports_box, "_bn_mt", None) not in (None, mt): reports_box = importlib.reload(reports_box)
    reports_box._bn_mt = mt
    return reports_box

def submit(d, ip):
    if not isinstance(d, dict): return 400, {"ok": False, "error": "invalid request"}
    ih = ip_hash(ip)
    # honeypot / too-fast fill: pretend success (fake ID, nothing stored) so bots learn nothing
    try: fill = int(d.get("elapsed_ms") or 0)
    except Exception: fill = 0
    if str(d.get("website") or "").strip() or 0 < fill < MIN_FILL_MS or fill <= 0:
        return 200, {"ok": True, "id": new_id(), "status": "received", "status_url": "/report-status"}
    for n, w in SUBMIT_RATE:
        left = _hit(("sub", ih, w), n, w, record=False)
        if left: return 429, {"ok": False, "error": f"Too many reports from this connection. Please try again in {max(1, left // 60)} min.", "retry_after_s": left}
    if _hit(("subg",), *SUBMIT_GLOBAL, record=False): return 429, {"ok": False, "error": "We're receiving a lot of reports right now. Please try again shortly.", "retry_after_s": 300}
    err, rec = validate(d)
    if err: return 400, {"ok": False, "error": err}
    for n, w in SUBMIT_RATE: _hit(("sub", ih, w), n, w)
    _hit(("subg",), *SUBMIT_GLOBAL)
    now = iso()
    rec["server"] = {"received_at": now, "node": NODE, "server_build": BUILD, "widget_version": VERSION}
    if WEB_ONLY:
        with _qlock:
            c = qdb()
            try:
                for _ in range(5):
                    rid = new_id()
                    try:
                        c.execute("INSERT INTO queue(id, created_at, record_json, public_json, ip_hash) VALUES(?,?,?,?,?)",
                                  (rid, now, json.dumps(rec), json.dumps(public_view(rec)), ih)); c.commit(); break
                    except sqlite3.IntegrityError: continue
            finally: c.close()
        st = "received"
    else:
        rid = _box().add(rec, source="box", ip_hash=ih); st = "open"
    return 200, {"ok": True, "id": rid, "status": st, "status_label": STATUS_INFO[st][0], "status_url": f"/report-status/{rid}"}

def lookup(raw_id, ip):
    ih = ip_hash(ip)
    left = _hit(("lk", ih), *LOOKUP_RATE) or _hit(("miss", ih), *MISS_RATE, record=False)
    if left: return 429, {"ok": False, "error": f"Too many lookups from this connection. Please wait {max(1, left // 60)} min and try again.", "retry_after_s": left}
    rid = norm_id(raw_id); rep = None
    if rid:
        if WEB_ONLY:
            c = qdb()
            try:
                r = c.execute("SELECT json FROM status WHERE id=?", (rid,)).fetchone()
                if r: rep = json.loads(r[0])
                else:
                    q = c.execute("SELECT created_at, public_json FROM queue WHERE id=?", (rid,)).fetchone()
                    if q:
                        info = STATUS_INFO["received"]
                        rep = {"id": rid, **json.loads(q["public_json"]), "status": "received", "status_label": info[0], "status_explanation": info[1],
                               "submitted_at": q["created_at"], "updated_at": q["created_at"], "queue_position": None, "duplicate_of": None,
                               "responses": [], "timeline": [{"t": q["created_at"], "status": "received", "label": "Report received"}]}
            finally: c.close()
        else:
            rep = _box().public_record(rid)
    if not rep:
        _hit(("miss", ih), *MISS_RATE)
        if WEB_ONLY and time.time() - _BOOT < 900 and not _status_synced():   # same answer for every ID while statuses are being restored
            return 503, {"ok": False, "error": "The site restarted moments ago and is re-syncing report statuses. Please try again in a minute.", "retry_after_s": 60}
        return 404, {"ok": False, "error": "No report matches that reference ID. Check it and try again (IDs look like BN-7K2M-Q9XD)."}
    return 200, {"ok": True, "report": rep}

_BOOT = time.time()
def _status_synced():
    c = qdb()
    try: return bool(_meta(c, "status_hash"))
    finally: c.close()

def stats():
    if WEB_ONLY:
        c = qdb()
        try: s = _meta(c, "stats"); pend = c.execute("SELECT COUNT(*) FROM queue WHERE acked_at IS NULL").fetchone()[0]
        finally: c.close()
        s = json.loads(s) if s else {"counts": {}, "total": 0, "median_resolve_hours": None, "updated": None}
        s["awaiting_pickup"] = pend
        return s
    return _box().public_stats()

# ---------------------------------------------------------------- box <-> Render (HMAC-signed with BN_SYNC_SECRET; same scheme as /internal/sync)
def verify(headers, method, path, body):
    sec = os.environ.get("BN_SYNC_SECRET", "")
    if len(sec) < 32: return False
    ts = headers.get("x-bn-ts") or ""; sig = headers.get("x-bn-sig") or ""
    try:
        if abs(time.time() - float(ts)) > 300: return False
    except Exception: return False
    want = hmac.new(sec.encode(), f"{ts}\n{method}\n{path}\n{hashlib.sha256(body or b'').hexdigest()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, sig)

def pull(limit=200):
    c = qdb()
    try:
        rows = c.execute("SELECT id, created_at, record_json, ip_hash FROM queue WHERE acked_at IS NULL ORDER BY created_at LIMIT ?", (limit,)).fetchall()
        out = {"node": NODE, "build": BUILD, "status_hash": _meta(c, "status_hash"),
               "reports": [{"id": r["id"], "created_at": r["created_at"], "ip_hash": r["ip_hash"], "record": json.loads(r["record_json"])} for r in rows]}
    finally: c.close()
    try:
        import usage_stats; out["usage"] = usage_stats.snapshot()
    except Exception: out["usage"] = None
    return out
def ack(d):
    ids = [i for i in (d.get("ids") or []) if isinstance(i, str) and ID_RE.match(i)][:1000]
    with _qlock:
        c = qdb()
        try:
            n = 0
            for i in ids: n += c.execute("UPDATE queue SET record_json=NULL, ip_hash=NULL, acked_at=? WHERE id=? AND acked_at IS NULL", (iso(), i)).rowcount
            # acknowledged stubs (public view only) are dropped once the box has pushed a status for them, or after 30 days
            c.execute("DELETE FROM queue WHERE acked_at IS NOT NULL AND (id IN (SELECT id FROM status) OR acked_at < ?)", (iso(time.time() - 30 * 86400),))
            c.commit()
        finally: c.close()
    return {"ok": True, "acked": n}
def put_status(d):
    sts = d.get("statuses")
    if not isinstance(sts, dict): return 400, {"ok": False, "error": "statuses must be an object"}
    with _qlock:
        c = qdb()
        try:
            c.execute("DELETE FROM status"); now = iso()
            for rid, v in sts.items():
                if ID_RE.match(rid) and isinstance(v, dict): c.execute("INSERT INTO status VALUES(?,?,?)", (rid, json.dumps(v), now))
            _meta(c, "status_hash", str(d.get("hash") or "")[:80]); _meta(c, "stats", json.dumps(d.get("stats") or {})); _meta(c, "status_pushed", now)
            c.execute("DELETE FROM queue WHERE acked_at IS NOT NULL AND id IN (SELECT id FROM status)")
            c.commit()
        finally: c.close()
    return 200, {"ok": True, "stored": len(sts)}

# ---------------------------------------------------------------- HTTP
def _send(h, code, body, ctype="application/json", robots=False):
    b = body if isinstance(body, bytes) else (json.dumps(body, default=str) if ctype == "application/json" else body).encode()
    h.send_response(code); h.send_header("Content-Type", ctype + "; charset=utf-8"); h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff"); h.send_header("Referrer-Policy", "no-referrer")
    if robots: h.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
    h.send_header("Content-Length", str(len(b))); h.end_headers(); h.wfile.write(b)

def config():
    return {"ok": True, "categories": [{"id": k, "label": v} for k, v in CATEGORIES], "limits": {"description": LIMITS["description"]},
            "build": BUILD, "version": VERSION, "node": NODE, "privacy": PRIVACY, "status_page": "/report-status",
            "statuses": {k: {"label": a, "explanation": b} for k, (a, b) in STATUS_INFO.items()}}

def status_page(rid=""):
    rid = html.escape(norm_id(rid) or "", quote=True)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer">
<title>Report status · blackout.network</title><link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/api/report/status.css"></head>
<body data-report-id="{rid}"><header class="rs-hd"><a href="/" class="rs-brand">blackout<b>.network</b></a><nav><a href="/">← Back to the dashboard</a></nav></header>
<main class="rs-main" id="main">
<h1>Check a problem report</h1>
<p class="rs-lead">Enter the reference ID you got after sending a report (it looks like <code>BN-7K2M-Q9XD</code>). You'll see only that report: what you sent, where it is in the queue, its status and our reply.</p>
<section class="rs-stats" id="rs_stats" aria-label="Review queue overview" hidden></section>
<form id="rs_form" class="rs-form" autocomplete="off"><label for="rs_id">Reference ID</label>
<div class="rs-row"><input id="rs_id" name="id" inputmode="text" autocapitalize="characters" spellcheck="false" maxlength="20" placeholder="BN-XXXX-XXXX" value="{rid}" required aria-describedby="rs_hint">
<button type="submit">Check status</button></div><div id="rs_hint" class="rs-hint">Letters and numbers only; dashes are optional.</div></form>
<div id="rs_out" aria-live="polite"></div>
<section class="rs-mine" id="rs_mine" hidden><h2>Reports saved on this device</h2><ul id="rs_mine_list"></ul>
<p class="rs-hint">Saved only in this browser (just the IDs). <button type="button" id="rs_forget" class="rs-link">Forget all saved IDs</button></p></section>
<noscript><p class="rs-err">This page needs JavaScript to look up a report.</p></noscript>
<p class="rs-foot">Found a new problem? Use the <b>Report a problem</b> button on any page. Report IDs are private: anyone with the ID can see that report's description and status, so share it only with people you trust.</p>
</main><script src="/api/report/status.js"></script></body></html>"""

def handle_stream(path, qs, h):
    """All GETs for this module (needs the request handler for the IP hash and extra headers)."""
    if path.startswith("/report-status"):
        rest = path[len("/report-status"):].strip("/")
        if "/" in rest: return _send(h, 404, status_page(), "text/html", robots=True)
        return _send(h, 200, status_page(rest), "text/html", robots=True)
    if path.startswith("/api/report/"):
        n = path[len("/api/report/"):]
        if n in FILES:
            with open(os.path.join(STATIC, n), "rb") as f: return _send(h, 200, f.read(), FILES[n])
        if n == "config": return _send(h, 200, config())
        m = re.fullmatch(r"([^/]{1,40})/status", n)
        if m: return _send(h, *lookup(m.group(1), h.ip()), robots=True)
        return _send(h, 404, {"ok": False, "error": "not found"})
    if path == "/api/report": return _send(h, 405, {"ok": False, "error": "POST a report here; see /api/report/config"})
    if path == "/api/reports/stats": return _send(h, 200, {"ok": True, **stats()})
    if path == "/api/reports/pull":
        if not WEB_ONLY or not verify({k.lower(): v for k, v in h.headers.items()}, "GET", h.path, b""): return _send(h, 403, {"ok": False, "error": "forbidden"})
        try: lim = max(1, min(500, int((qs.get("limit") or ["200"])[0])))
        except Exception: lim = 200
        return _send(h, 200, pull(lim))
    return _send(h, 404, {"ok": False, "error": "not found"})

def handle_post(path, d, ip=None, qs=None, headers=None, raw=b""):
    headers = headers or {}
    if path == "/api/report":
        ct = (headers.get("content-type") or "").split(";")[0].strip().lower()
        if ct != "application/json": return 415, {"ok": False, "error": "send JSON (Content-Type: application/json)"}
        if len(raw or b"") > 12000: return 413, {"ok": False, "error": "report too large"}
        return submit(d, ip)
    if path in ("/api/reports/ack", "/api/reports/status"):
        if not WEB_ONLY or not verify(headers, "POST", path, raw): return 403, {"ok": False, "error": "forbidden"}
        if path == "/api/reports/ack": return 200, ack(d if isinstance(d, dict) else {})
        return put_status(d if isinstance(d, dict) else {})
    return 404, {"ok": False, "error": "not found"}

def handle_get(path, qs):   # fallback for callers without a request handler (never used by server.py, which prefers handle_stream)
    if path == "/api/report/config": return 200, config()
    if path == "/api/reports/stats": return 200, {"ok": True, **stats()}
    return 404, {"ok": False, "error": "not found"}
