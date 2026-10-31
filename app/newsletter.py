"""blackout.network newsletter add-on (hot-reloaded by server.py via addons.py).

Pages:  GET /newsletter (signup) · /newsletter/confirm?token= · /newsletter/unsubscribe?token= · /newsletter/manage?token=
        /newsletter/admin (admin passcode) · /newsletter/sample (live sample issue)
API:    GET  /api/newsletter/meta · /api/newsletter/app.js|app.css|admin.js
        POST /api/newsletter/subscribe · /api/newsletter/manage · /api/newsletter/resubscribe · /api/newsletter/unsubscribe
        POST /newsletter/unsubscribe?token=  (RFC 8058 one-click, used by mail clients)
        POST /api/newsletter/admin/login · /api/newsletter/admin  (session token from login)
Data:   reads blackout.db ONLY via file:blackout.db?mode=ro; writes only newsletter.db, newsletter_outbox/, logs/newsletter.log,
        newsletter_config.json (admin settings) and the secrets file /workspace/.credentials/newsletter.env (created once, chmod 600).
Never changes scanner.py, scoring, push.py, jets.py or config.json. Sending is 'preview' (outbox files, no network) unless a provider
is configured in newsletter.env AND newsletter_config.json has live_sending_approved=true AND a mailing address is set.
"""
import os, re, json, time, hmac, html, base64, hashlib, secrets, sqlite3, threading, subprocess, csv, io, smtplib, ssl, traceback
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email import policy as _email_policy
from email.utils import formataddr, format_datetime, make_msgid
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
P = {  # every path is overridable by env var for tests (NEWSLETTER_DB, NEWSLETTER_SRC_DB, ...)
    "cfg": os.environ.get("NEWSLETTER_CONFIG", os.path.join(BASE, "newsletter_config.json")),
    "db": os.environ.get("NEWSLETTER_DB", os.path.join(BASE, "newsletter.db")),
    "src": os.environ.get("NEWSLETTER_SRC_DB", os.path.join(BASE, "blackout.db")),
    "bo_cfg": os.environ.get("NEWSLETTER_BO_CONFIG", os.path.join(BASE, "config.json")),
    "outbox": os.environ.get("NEWSLETTER_OUTBOX", os.path.join(BASE, "newsletter_outbox")),
    "env": os.environ.get("NEWSLETTER_ENV", "/workspace/.credentials/newsletter.env"),
    "pass": os.environ.get("NEWSLETTER_PASSFILE", os.path.join(BASE, "ADMIN_PASSCODE.txt")),
    "log": os.environ.get("NEWSLETTER_LOG", os.path.join(BASE, "logs", "newsletter.log")),
    "static": os.path.join(BASE, "newsletter_static"),
    "disposable": os.path.join(BASE, "newsletter_disposable.txt"),
    "worker": os.path.join(BASE, "newsletter_worker.py"),
    "pid": os.path.join(BASE, "logs", "newsletter_worker.pid"),
}
BRAND = "blackout.network"
TAGLINE = "The world's threats, scored and sourced, before cable news catches up."
DISCLAIMER = ("Research only. blackout.network is not an official warning service. Items are machine-collected and scored; "
              "always verify with official sources before acting.")
PRIVACY = "Email only used for this newsletter; unsubscribe anytime."
CATEGORIES = ["war/conflict", "political", "natural disaster", "disease", "cyber", "space weather", "financial", "ufo/uap", "spiritual/religious", "other"]
FREQS = {"twice": "Twice daily (morning + evening)", "morning": "Once daily: morning", "evening": "Once daily: evening"}
SLOTS = ("morning", "evening")
SENDER_MODES = ("preview", "smtp", "resend", "brevo", "sendgrid")
DEFAULTS = {
    "base_url": "https://blackout.network",
    "from_name": "blackout.network",
    "from_email": "newsletter@blackout.network",
    "reply_to": "",
    "mailing_address": "",
    "slots": {"morning": "07:00", "evening": "19:00"},
    "global_frequency": "per_subscriber",
    "paused": False,
    "catchup_hours": 2,
    "dedupe_hours": 12,
    "max_window_hours": 24,
    "main_min_rank": None,
    "main_min_sources": None,
    "notable_min_rank": 5,
    "min_main_items": 3,
    "max_main_items": 10,
    "max_notable_items": 3,
    "max_watchlist": 5,
    "confirm_ttl_hours": 48,
    "link_ttl_days": 400,
    "rate_limit": {"ip_per_hour": 5, "email_per_day": 3},
    "mx_check": False,
    "live_sending_approved": False,
    "outbox_retention_days": 30,
    "retry_backoff_minutes": [2, 10, 30],
    "editorial_ttl_hours": 24,
}
E = lambda s: html.escape("" if s is None else str(s), quote=True)
_LOCK = threading.RLock()

# ------------------------------------------------------------------ config, secrets, logging
def cfg():
    d = json.loads(json.dumps(DEFAULTS))
    try:
        with open(P["cfg"]) as f: user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict): d[k].update(v)
            else: d[k] = v
    except FileNotFoundError:
        save_cfg(d)
    except Exception: pass
    return d

def save_cfg(d):
    tmp = P["cfg"] + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, indent=1)
    os.chmod(tmp, 0o644); os.replace(tmp, P["cfg"])

def bo_cfg():
    try:
        with open(P["bo_cfg"]) as f: return json.load(f)
    except Exception: return {}

def main_rule(c=None):
    c = c or cfg(); b = bo_cfg()
    r = c.get("main_min_rank") if c.get("main_min_rank") is not None else b.get("push_min_rank", 7)
    s = c.get("main_min_sources") if c.get("main_min_sources") is not None else b.get("push_min_sources", 2)
    return int(r), int(s)

ENV_TEMPLATE = """# blackout.network newsletter secrets (chmod 600). Never commit or share this file.
# NEWSLETTER_SECRET signs confirm/unsubscribe/manage/admin tokens. Changing it invalidates every link already emailed.
NEWSLETTER_SECRET={secret}
# Sender mode: preview (default: writes newsletter_outbox/, sends nothing) | smtp | resend | brevo | sendgrid
# Live modes ALSO need "live_sending_approved": true and "mailing_address" in newsletter_config.json.
NEWSLETTER_SENDER=preview
# --- smtp ---
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASS=
# SMTP_SECURITY is one of: starttls | ssl | none
# SMTP_SECURITY=starttls
# --- resend ---
# RESEND_API_KEY=
# --- brevo ---
# BREVO_API_KEY=
# --- sendgrid ---
# SENDGRID_API_KEY=
"""

def env():
    path = P["env"]
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f: f.write(ENV_TEMPLATE.format(secret=secrets.token_hex(32)))
        except FileExistsError: pass
    try:
        if (os.stat(path).st_mode & 0o777) != 0o600: os.chmod(path, 0o600)
    except Exception: pass
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1); out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def secret():
    s = env().get("NEWSLETTER_SECRET", "")
    if len(s) < 32: raise RuntimeError("NEWSLETTER_SECRET missing/short in newsletter.env")
    return s.encode()

def log(msg, kind="info"):
    line = f"[{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}] {kind}: {msg}"
    try:
        os.makedirs(os.path.dirname(P["log"]), exist_ok=True)
        with open(P["log"], "a") as f: f.write(line + "\n")
    except Exception: pass
    try:
        c = db(); c.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (iso(now()), kind, str(msg)[:1000])); c.commit(); c.close()
    except Exception: pass

# ------------------------------------------------------------------ time helpers
def now(): return datetime.now(UTC)
def iso(d): return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None
def parse_t(s):
    if not s: return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except Exception: return None
def fmt_et(d, with_date=True):
    if not d: return "time not reported"
    l = d.astimezone(ET)
    t = l.strftime("%-I:%M %p ") + l.tzname()
    return (l.strftime("%b %-d, %Y ") + t) if with_date else t
def fmt_z(d): return d.astimezone(UTC).strftime("%H%MZ %d %b").upper() if d else ""
def when_str(d): return f"{fmt_et(d)} ({fmt_z(d)})" if d else "time not reported"
def range_str(a, b):
    same = a.astimezone(ET).date() == b.astimezone(ET).date()
    return f"Data range: {fmt_et(a)} – {fmt_et(b, not same)}"

# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
  frequency TEXT NOT NULL DEFAULT 'twice', interests TEXT NOT NULL DEFAULT '["all"]', created TEXT, confirmed_at TEXT, unsubscribed_at TEXT,
  updated TEXT, last_sent_at TEXT, confirm_sent_at TEXT, signup_source TEXT, consent_ip_hash TEXT, unsub_reason TEXT);
CREATE TABLE IF NOT EXISTS slot_runs(slot_key TEXT PRIMARY KEY, slot_time TEXT, status TEXT, started TEXT, finished TEXT,
  n_targets INTEGER DEFAULT 0, n_sent INTEGER DEFAULT 0, n_failed INTEGER DEFAULT 0, n_skipped INTEGER DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS sends(id INTEGER PRIMARY KEY AUTOINCREMENT, subscriber_id INTEGER, slot_key TEXT, status TEXT, attempts INTEGER DEFAULT 0,
  next_retry TEXT, created TEXT, sent_at TEXT, mode TEXT, outbox_file TEXT, subject TEXT, n_main INTEGER DEFAULT 0, n_notable INTEGER DEFAULT 0,
  n_watch INTEGER DEFAULT 0, quiet INTEGER DEFAULT 0, error TEXT, UNIQUE(subscriber_id, slot_key));
CREATE TABLE IF NOT EXISTS sent_items(send_id INTEGER, subscriber_id INTEGER, cluster_id TEXT, title_norm TEXT, section TEXT, sent_at TEXT);
CREATE INDEX IF NOT EXISTS si_sub ON sent_items(subscriber_id, sent_at);
CREATE TABLE IF NOT EXISTS mail_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, subscriber_id INTEGER, mode TEXT, status TEXT,
  outbox_file TEXT, subject TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS attempts(kind TEXT, k TEXT, ts REAL);
CREATE INDEX IF NOT EXISTS att_k ON attempts(kind, k, ts);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS editorial(cluster_id TEXT PRIMARY KEY, added TEXT, note TEXT);
"""
_INIT = {}
def db():
    c = sqlite3.connect(P["db"], timeout=15); c.row_factory = sqlite3.Row
    if _INIT.get(P["db"]) is None:
        c.execute("PRAGMA journal_mode=WAL"); c.executescript(SCHEMA); c.commit(); _INIT[P["db"]] = True
    return c

def src():
    c = sqlite3.connect(f"file:{P['src']}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row
    return c

def h(s, n=16): return hashlib.sha256((s or "").encode()).hexdigest()[:n]

# ------------------------------------------------------------------ signed tokens (HMAC-SHA256, expiry, purpose-bound)
def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def _unb64(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
def make_token(purpose, sid=0, ttl=3600, t=None, **extra):
    payload = {"p": purpose, "s": sid, "e": int((t or time.time()) + ttl), **extra}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret(), f"{purpose}.{body}".encode(), hashlib.sha256).digest()[:20])
    return f"{body}.{sig}"
def read_token(tok, purpose, t=None):
    """-> (status, payload); status is ok | expired | invalid. Signature is checked before anything in the payload is trusted."""
    try:
        body, sig = str(tok or "").strip().split(".", 1)
        want = _b64(hmac.new(secret(), f"{purpose}.{body}".encode(), hashlib.sha256).digest()[:20])
        if not hmac.compare_digest(want, sig): return "invalid", None
        p = json.loads(_unb64(body))
        if p.get("p") != purpose: return "invalid", None
        if int(p.get("e", 0)) < (t or time.time()): return "expired", p
        return "ok", p
    except Exception: return "invalid", None

def sub_token(purpose, row, ttl=None, t=None):
    c = cfg()
    ttl = ttl or (c["confirm_ttl_hours"] * 3600 if purpose == "confirm" else c["link_ttl_days"] * 86400)
    return make_token(purpose, int(row["id"]), ttl, t=t, x=h(row["email"], 12))
def token_sub(tok, purpose, t=None):
    """-> (status, row|None). A token for an erased or re-created address resolves to 'gone'."""
    st, p = read_token(tok, purpose, t)
    if st == "invalid": return "invalid", None
    c = db(); r = c.execute("SELECT * FROM subscribers WHERE id=?", (int(p.get("s", 0)),)).fetchone(); c.close()
    if st == "expired": return "expired", r if (r and h(r["email"], 12) == p.get("x")) else None
    if not r or h(r["email"], 12) != p.get("x"): return "gone", None
    return "ok", r

def links_for(row, c=None):
    base = (c or cfg())["base_url"].rstrip("/")
    return {"unsubscribe": f"{base}/newsletter/unsubscribe?token={sub_token('unsub', row)}",
            "manage": f"{base}/newsletter/manage?token={sub_token('manage', row)}",
            "confirm": f"{base}/newsletter/confirm?token={sub_token('confirm', row)}",
            "scoring": f"{base}/scoring", "site": f"{base}/#wire", "signup": f"{base}/newsletter"}

# ------------------------------------------------------------------ validation + rate limits
EMAIL_RE = re.compile(r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9])$")
_DISP = {"t": 0, "s": set()}
def disposable():
    try:
        mt = os.path.getmtime(P["disposable"])
        if mt != _DISP["t"]:
            _DISP["s"] = {l.strip().lower() for l in open(P["disposable"]) if l.strip() and not l.startswith("#")}; _DISP["t"] = mt
    except Exception: pass
    return _DISP["s"]
def mx_ok(domain):
    """Optional MX lookup. Needs dnspython and working DNS; the box's DNS is synthetic, so this is off by default and any failure is 'skipped'."""
    if not cfg().get("mx_check"): return "skipped"
    try:
        import dns.resolver  # type: ignore
        ans = dns.resolver.resolve(domain, "MX", lifetime=3)
        return "ok" if len(ans) else "none"
    except ImportError: return "skipped"
    except Exception as ex:
        return "none" if type(ex).__name__ in ("NXDOMAIN", "NoAnswer") else "skipped"
def validate_email(raw):
    """-> (normalized_email, None) or (None, friendly error). Normalizes case and IDN domains."""
    s = (raw or "").strip() if isinstance(raw, str) else ""
    if not s: return None, "Enter your email address."
    if len(s) > 254: return None, "That email address is too long."
    if "@" not in s: return None, "That doesn't look like an email address (missing @)."
    local, _, dom = s.rpartition("@")
    try: dom = dom.encode("idna").decode("ascii")
    except Exception: return None, "That email domain isn't valid."
    s = f"{local}@{dom}".lower(); local = local.lower()
    if not local or len(local) > 64: return None, "The part before @ must be 1–64 characters."
    if not EMAIL_RE.match(s): return None, "That doesn't look like a valid email address."
    d = s.split("@")[1]
    if any(d == x or d.endswith("." + x) for x in disposable()): return None, "Disposable email addresses can't subscribe. Please use a permanent address."
    if mx_ok(d) == "none": return None, "That email domain can't receive mail (no MX record)."
    return s, None

def hits(c, kind, k, window_s):
    return c.execute("SELECT COUNT(*) FROM attempts WHERE kind=? AND k=? AND ts>=?", (kind, k, time.time() - window_s)).fetchone()[0]
def hit(c, kind, k):
    c.execute("INSERT INTO attempts(kind,k,ts) VALUES(?,?,?)", (kind, k, time.time()))
    c.execute("DELETE FROM attempts WHERE ts<?", (time.time() - 3 * 86400,))

# ------------------------------------------------------------------ CSRF (stateless signed token + same-origin check)
def csrf_token(): return make_token("csrf", 0, 4 * 3600, n=secrets.token_hex(4))
def allowed_origins():
    b = cfg()["base_url"].rstrip("/")
    o = {"http://127.0.0.1:8787", "http://localhost:8787", b}
    if b.startswith("https://") and not b.startswith("https://www."): o.add(b.replace("https://", "https://www.", 1))
    try:
        pu = open(os.path.join(BASE, "PUBLIC_URL.txt")).read().strip().rstrip("/")
        if pu: o.add(pu)
    except Exception: pass
    return o
def origin_ok(headers):
    headers = headers or {}
    o = headers.get("origin")
    if o: return o.rstrip("/") in allowed_origins()
    r = headers.get("referer")
    if r:
        pr = urllib.parse.urlparse(r); return f"{pr.scheme}://{pr.netloc}" in allowed_origins()
    return True   # non-browser client: no ambient credentials to abuse; the signed CSRF token is still required
def csrf_ok(d, headers):
    st, p = read_token(d.get("csrf"), "csrf")
    return st == "ok" and origin_ok(headers)

# ------------------------------------------------------------------ content selection
STOP = set("a an the of in on at to for and or by with from is are was were be after as amid over into its it this that new says said".split())
def norm_title(t):
    t = re.sub(r"https?://\S+", " ", (t or "").lower())
    w = [x for x in re.findall(r"[^\W_]+", t) if x not in STOP and len(x) > 1]
    return " ".join(w[:24])
def similar(a, b, th=0.6):
    A, B = set(a.split()), set(b.split())
    if not A or not B: return False
    return len(A & B) / len(A | B) >= th

def _links(r):
    out, seen = [], set()
    try: L = json.loads(r["links"] or "[]")
    except Exception: L = []
    for x in L:
        u = (x or {}).get("url") or ""
        if not re.match(r"^https?://[^\s<>\"']+$", u) or u in seen: continue
        seen.add(u); out.append({"source": (x.get("source") or urllib.parse.urlparse(u).netloc)[:60], "url": u})
    return out[:4]
def _what(r):
    m = re.search(r"WHAT:\s*(.*?)\s*WHERE:", r["brief"] or "", re.S)
    s = (m.group(1) if m else r["title"]) or r["title"] or ""
    s = re.sub(r"\s+", " ", s).strip(); s = re.sub(r"\s+\.", ".", s)
    s = s if len(s) <= 420 else s[:417].rsplit(" ", 1)[0] + "…"
    return s if s.endswith((".", "!", "?", "…", "]")) else s + "."
def _fams(r):
    try: return [f for f in json.loads(r["families"] or "[]") if f]
    except Exception: return []

def item_of(r, section, official=0, editorial=False):
    fams = _fams(r); eff = int(r["eff_families"] or 0)
    t = parse_t(r["event_time"]) or parse_t(r["first_seen"])
    if t and t > now() + timedelta(minutes=10): t = parse_t(r["first_seen"])   # forecast times: report when first seen
    if editorial:
        conf = "UNCONFIRMED: single source, included under the editorial exception for a potential national- or civilizational-scale event"
    elif eff >= 2:
        conf = f"Confirmed by {eff} independent source families ({', '.join(fams[:5])})" if fams else f"Confirmed by {eff} independent sources"
    else:
        conf = f"Single {'official ' if official else ''}source ({', '.join(fams[:2]) or 'one outlet'})" + ("" if official else ", not independently confirmed")
    return {"cluster_id": r["cluster_id"], "section": section, "title": re.sub(r"\s+", " ", r["title"] or "").strip(), "what": _what(r),
            "where": (r["location"] or "").strip() or None, "lat": r["lat"], "lon": r["lon"], "when": t, "category": r["category"] or "other",
            "rank": int(r["rank"] or 0), "score": int(r["score"] or 0), "eff": eff, "families": fams, "confidence": conf,
            "unconfirmed": editorial or eff < 2, "official": bool(official), "editorial": editorial, "links": _links(r),
            "title_norm": norm_title(r["title"]), "first_seen": parse_t(r["first_seen"])}

def build_issue(sub, at=None, since=None, slot="morning", conn=None, c=None):
    """Select content for one subscriber. sub: dict with id (None for previews), frequency, interests, last_sent_at.
    Window: since the subscriber's last send, capped at max_window_hours (24 h). Returns main / notable / watchlist / quiet / empty."""
    c = c or cfg(); at = at or now()
    win = timedelta(hours=float(c["max_window_hours"]))
    last = parse_t(sub.get("last_sent_at")) if sub else None
    start = since or (max(last, at - win) if last else at - win)
    rmin, smin = main_rule(c)
    try: ints = set(json.loads(sub.get("interests") or '["all"]')) if sub else {"all"}
    except Exception: ints = {"all"}
    allcats = "all" in ints or not ints
    # dedupe memory: clusters + normalized titles this subscriber got in the last dedupe_hours (+30 min grace so a 12 h-apart slot still counts)
    sent_ids, sent_titles = set(), []
    if sub and sub.get("id"):
        k = db(); cut = iso(at - timedelta(hours=float(c["dedupe_hours"]), minutes=30))
        for x in k.execute("SELECT cluster_id, title_norm FROM sent_items WHERE subscriber_id=? AND sent_at>=?", (sub["id"], cut)):
            sent_ids.add(x["cluster_id"]); sent_titles.append(x["title_norm"] or "")
        k.close()
    s0, s1 = iso(start), iso(at)
    ed_ids = []
    try:
        k = db(); ed_ids = [x[0] for x in k.execute("SELECT cluster_id FROM editorial WHERE added>=?", (iso(at - timedelta(hours=float(c["editorial_ttl_hours"]))),))]; k.close()
    except Exception: pass
    own = conn is None; S = conn or src()
    try:
        rows = S.execute("""SELECT * FROM clusters WHERE watchlist=0 AND rank>=? AND
              ((first_seen>=? AND first_seen<=?) OR (high_at>=? AND high_at<=?)) ORDER BY rank DESC, score DESC, eff_families DESC LIMIT 400""",
              (int(c["notable_min_rank"]), s0, s1, s0, s1)).fetchall()
        wrows = S.execute("""SELECT * FROM clusters WHERE watchlist=1 AND first_seen>=? AND first_seen<=?
              ORDER BY rank DESC, score DESC, mentions_3h DESC, first_seen DESC LIMIT 300""", (s0, s1)).fetchall()
        erows = S.execute(f"SELECT * FROM clusters WHERE cluster_id IN ({','.join('?' * len(ed_ids))})", ed_ids).fetchall() if ed_ids else []
        ids = [r["cluster_id"] for r in rows] + [r["cluster_id"] for r in erows]
        offi = {}
        if ids:
            for x in S.execute(f"SELECT cluster_id, MAX(official) o FROM alerts WHERE cluster_id IN ({','.join('?' * len(ids))}) GROUP BY cluster_id", ids):
                offi[x["cluster_id"]] = x["o"] or 0
    finally:
        if own: S.close()
    picked_titles = []
    def take(r):
        if r["cluster_id"] in sent_ids: return False
        if not allcats and (r["category"] or "other") not in ints: return False
        tn = norm_title(r["title"])
        if any(similar(tn, x) for x in sent_titles + picked_titles): return False
        picked_titles.append(tn); return True
    main, notable, watch = [], [], []
    for r in erows:
        if len(main) < int(c["max_main_items"]) and take(r): main.append(item_of(r, "main", offi.get(r["cluster_id"], 0), editorial=True))
    for r in rows:
        if int(r["rank"] or 0) >= rmin and int(r["eff_families"] or 0) >= smin and len(main) < int(c["max_main_items"]) and take(r):
            main.append(item_of(r, "main", offi.get(r["cluster_id"], 0)))
    if len(main) < int(c["min_main_items"]):
        room = min(int(c["max_notable_items"]), int(c["min_main_items"]) - len(main)); used = {m["cluster_id"] for m in main}
        for r in rows:
            if len(notable) >= room: break
            rk, ef = int(r["rank"] or 0), int(r["eff_families"] or 0)
            if r["cluster_id"] in used: continue
            ok = (ef >= 2) or (rk >= rmin and offi.get(r["cluster_id"]))   # confirmed rank 5-6, or a rank-7+ item from one official source
            if ok and take(r): notable.append(item_of(r, "notable", offi.get(r["cluster_id"], 0)))
    for r in wrows:
        if len(watch) >= int(c["max_watchlist"]): break
        if take(r): watch.append(item_of(r, "watchlist"))
    quiet = not main and not notable
    return {"main": main, "notable": notable, "watchlist": watch, "quiet": quiet, "start": start, "end": at, "slot": slot,
            "empty": not (main or notable or watch), "rule": {"rank": rmin, "sources": smin}}

# ------------------------------------------------------------------ rendering (HTML email: tables + inline CSS; plain-text alternative)
RANK_COLORS = ["#3a4250", "#4b5563", "#2f7d4f", "#52c41a", "#a0d911", "#fadb14", "#faad14", "#fa8c16", "#ff4d4f", "#cf1322", "#8b0000"]
def rank_color(r): return RANK_COLORS[max(0, min(10, int(r or 0)))]
def slot_label(slot): return {"morning": "Morning", "evening": "Evening"}.get(slot, "Special")
def _cut(s, n): return s if len(s) <= n else s[:n - 3].rsplit(" ", 1)[0] + "…"

def subject_for(issue):
    d = issue["end"].astimezone(ET).strftime("%b %-d"); lab = slot_label(issue["slot"])
    if issue["main"]:
        top = issue["main"][0]; more = len(issue["main"]) - 1
        return f"{BRAND} {lab} Brief, {d}: R{top['rank']} {_cut(top['title'], 70)}" + (f" (+{more} more)" if more else "")
    if issue["notable"]: return f"{BRAND} {lab} Brief, {d}: no rank-{issue['rule']['rank']}+ confirmed threats; {len(issue['notable'])} notable"
    return f"{BRAND} {lab} Brief, {d}: quiet period"

def _item_html(it):
    rc = rank_color(it["rank"]); btx = "#0b0d10" if 3 <= it["rank"] <= 7 else "#ffffff"
    conf_col = "#faad14" if it["unconfirmed"] else "#52c41a"
    unc = ('<span style="display:inline-block;border:1px solid #faad14;color:#faad14;border-radius:4px;font-size:11px;font-weight:700;'
           'padding:1px 6px;margin-left:6px;letter-spacing:.4px">UNCONFIRMED</span>') if it["editorial"] else ""
    where = E(it["where"]) if it["where"] else "Location not reported"
    if it["lat"] is not None and it["lon"] is not None and it["where"]: where += f" (approx. {it['lat']:.2f}, {it['lon']:.2f})"
    links = " · ".join(f'<a href="{E(l["url"])}" style="color:#4aa3ff;text-decoration:underline">{E(l["source"])}</a>' for l in it["links"]) or "no source link recorded"
    return (f'<tr><td style="padding:14px 16px;border-top:1px solid #252b33">'
            f'<div style="margin:0 0 6px 0"><span style="display:inline-block;background:{rc};color:{btx};border-radius:4px;font-size:12px;font-weight:700;padding:2px 7px">'
            f'RANK {it["rank"]}/10</span> <span style="color:#8b95a3;font-size:12px">score {it["score"]}/100 · {E(it["category"])}</span>{unc}</div>'
            f'<div style="font-size:16px;line-height:1.35;font-weight:700;color:#e6e9ee;margin:0 0 6px 0">{E(_cut(it["title"], 200))}</div>'
            f'<p style="margin:0;font-size:14px;line-height:1.55;color:#c9d1d9"><b style="color:#e6e9ee">What happened:</b> {E(it["what"])} '
            f'<b style="color:#e6e9ee">Where:</b> {where}. <b style="color:#e6e9ee">When:</b> {E(when_str(it["when"]))}. '
            f'<b style="color:#e6e9ee">Confidence:</b> <span style="color:{conf_col}">{E(it["confidence"])}</span>; rank {it["rank"]}/10, score {it["score"]}/100. '
            f'<b style="color:#e6e9ee">Verify:</b> {links}</p></td></tr>')

def render(issue, links, c=None):
    """-> (subject, html, text). links: dict with unsubscribe, manage, scoring, site."""
    c = c or cfg(); subj = subject_for(issue)
    rr = issue["rule"]; rng = range_str(issue["start"], issue["end"])
    addr = (c.get("mailing_address") or "").strip()
    addr_html = E(addr) if addr else ('<span style="color:#faad14">[Mailing address not set. CAN-SPAM requires a physical postal address before live sending: '
                                      'set "mailing_address" in newsletter_config.json.]</span>')
    pre = (f"{len(issue['main'])} confirmed rank-{rr['rank']}+ item(s)" if issue["main"] else f"No rank-{rr['rank']}+ confirmed threats in this window") + \
          (f" · {len(issue['watchlist'])} on the watchlist" if issue["watchlist"] else "")
    H = []; a = H.append
    a('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="color-scheme" content="dark light"><meta name="supported-color-schemes" content="dark light">'
      f'<title>{E(subj)}</title></head><body style="margin:0;padding:0;background:#0b0d10">'
      f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#0b0d10">{E(pre)}</div>'
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0b0d10"><tr><td align="center" style="padding:16px 8px">'
      '<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;background:#14181d;border:1px solid #252b33;'
      'border-radius:10px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#e6e9ee">')
    a(f'<tr><td style="padding:18px 16px 12px 16px;border-bottom:1px solid #252b33">'
      f'<div style="font-size:20px;letter-spacing:.5px;font-weight:800;color:#e6e9ee">BLACKOUT.<span style="color:#ff4d4f">NETWORK</span></div>'
      f'<div style="font-size:13px;color:#8b95a3;margin-top:4px">{E(TAGLINE)}</div>'
      f'<div style="font-size:15px;font-weight:700;color:#e6e9ee;margin-top:12px">{slot_label(issue["slot"])} Brief · {E(issue["end"].astimezone(ET).strftime("%A, %B %-d, %Y"))}</div>'
      f'<div style="font-size:12px;color:#8b95a3;margin-top:3px">{E(rng)}</div></td></tr>')
    def section(title, sub_, items, col="#e6e9ee"):
        a(f'<tr><td style="padding:16px 16px 4px 16px"><div style="font-size:13px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:{col}">{E(title)}</div>'
          f'<div style="font-size:12px;color:#8b95a3;margin-top:2px">{E(sub_)}</div></td></tr>')
        for it in items: a(_item_html(it))
    if issue["main"]:
        section("Main feed", f"Rank {rr['rank']}+ confirmed by {rr['sources']}+ independent sources (plus any item marked UNCONFIRMED under the editorial exception).", issue["main"])
    else:
        a(f'<tr><td style="padding:16px"><div style="border:1px solid #2f3742;background:#181d23;border-radius:8px;padding:12px 14px;font-size:14px;color:#c9d1d9">'
          f'<b style="color:#e6e9ee">Quiet period:</b> No rank-{rr["rank"]}+ confirmed threats in this window.</div></td></tr>')
    if issue["notable"]:
        section("Also notable", f"Below the main-feed bar: confirmed rank 5–6 items, or a rank-{rr['rank']}+ item from a single official source.", issue["notable"])
    if issue["watchlist"]:
        a('<tr><td style="padding:16px 16px 4px 16px"><div style="font-size:13px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#faad14">Watchlist: unconfirmed</div>'
          '<div style="font-size:12px;color:#8b95a3;margin-top:2px">Low-confidence, single-source reports. Not verified. Shown so you can watch for confirmation.</div></td></tr>')
        for it in issue["watchlist"]:
            l = it["links"][0] if it["links"] else None
            a(f'<tr><td style="padding:8px 16px;border-top:1px solid #252b33;font-size:13px;line-height:1.5;color:#c9d1d9">'
              f'<span style="color:#faad14;font-weight:700">UNCONFIRMED</span> · {E(_cut(it["title"], 180))} '
              f'<span style="color:#8b95a3">({E(it["category"])}, {E(fmt_et(it["first_seen"]))})</span>'
              + (f' · <a href="{E(l["url"])}" style="color:#4aa3ff">{E(l["source"])}</a>' if l else "") + '</td></tr>')
    a(f'<tr><td style="padding:16px;border-top:1px solid #252b33;font-size:12px;line-height:1.6;color:#8b95a3">'
      f'<p style="margin:0 0 8px 0">{E(DISCLAIMER)} <a href="{E(links["scoring"])}" style="color:#4aa3ff">How we score</a> · '
      f'<a href="{E(links["site"])}" style="color:#4aa3ff">Open the live dashboard</a></p>'
      f'<p style="margin:0 0 8px 0">You get this because you confirmed a subscription to the {BRAND} newsletter. '
      f'<a href="{E(links["manage"])}" style="color:#4aa3ff">Manage preferences</a> · '
      f'<a href="{E(links["unsubscribe"])}" style="color:#4aa3ff">Unsubscribe</a> (one click, no login).</p>'
      f'<p style="margin:0">{BRAND} · {addr_html}</p></td></tr></table></td></tr></table></body></html>')
    T = [f"BLACKOUT.NETWORK — {slot_label(issue['slot'])} Brief", TAGLINE, rng, ""]
    def tsec(title, items):
        T.extend([title.upper(), "=" * len(title)])
        for i, it in enumerate(items, 1):
            T.append(f"{i}. [RANK {it['rank']}/10 · score {it['score']}/100 · {it['category']}]{' UNCONFIRMED' if it['editorial'] else ''} {_cut(it['title'], 200)}")
            T.append(f"   What happened: {it['what']} Where: {it['where'] or 'Location not reported'}. When: {when_str(it['when'])}. Confidence: {it['confidence']}.")
            for l in it["links"]: T.append(f"   Verify ({l['source']}): {l['url']}")
            T.append("")
    if issue["main"]: tsec("Main feed", issue["main"])
    else: T += [f"QUIET PERIOD: No rank-{rr['rank']}+ confirmed threats in this window.", ""]
    if issue["notable"]: tsec("Also notable", issue["notable"])
    if issue["watchlist"]:
        T += ["WATCHLIST: UNCONFIRMED (single-source, not verified)", "=" * 30]
        for it in issue["watchlist"]:
            T.append(f"- UNCONFIRMED · {_cut(it['title'], 180)} ({it['category']}, {fmt_et(it['first_seen'])})" + (f" {it['links'][0]['url']}" if it["links"] else ""))
        T.append("")
    T += ["--", DISCLAIMER, f"How we score: {links['scoring']}", f"Dashboard: {links['site']}",
          f"Manage preferences: {links['manage']}", f"Unsubscribe (one click): {links['unsubscribe']}",
          f"{BRAND} · {addr or '[Mailing address not set: required by CAN-SPAM before live sending]'}"]
    return subj, "".join(H), "\n".join(T)

def render_simple(title, paras, button=None, c=None, extra_links=None):
    """Transactional email (confirm / already-subscribed). paras: plain strings. button: (label, url). extra_links: [(label, url)]."""
    c = c or cfg(); addr = (c.get("mailing_address") or "").strip()
    btn = (f'<p style="margin:18px 0"><a href="{E(button[1])}" style="display:inline-block;background:#4aa3ff;color:#0b0d10;font-weight:700;'
           f'text-decoration:none;border-radius:6px;padding:10px 18px">{E(button[0])}</a></p>'
           f'<p style="font-size:12px;color:#8b95a3;word-break:break-all">Or paste this link into your browser: {E(button[1])}</p>') if button else ""
    xl = "".join(f'<p style="font-size:12px;margin:0 0 6px 0"><a href="{E(u)}" style="color:#4aa3ff">{E(l)}</a></p>' for l, u in (extra_links or []))
    foot = (f'<p style="font-size:12px;color:#8b95a3;margin-top:18px">{E(DISCLAIMER)}<br>{BRAND} · '
            + (E(addr) if addr else '[Mailing address not set: required by CAN-SPAM before live sending]') + "</p>")
    body = "".join(f'<p style="font-size:14px;line-height:1.55;color:#c9d1d9;margin:0 0 10px 0">{E(p)}</p>' for p in paras)
    html_ = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="color-scheme" content="dark light"><title>' + E(title) + '</title></head>'
             '<body style="margin:0;background:#0b0d10"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0d10"><tr><td align="center" style="padding:16px 8px">'
             '<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;background:#14181d;border:1px solid #252b33;border-radius:10px;'
             'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"><tr><td style="padding:20px">'
             '<div style="font-size:18px;font-weight:800;color:#e6e9ee">BLACKOUT.<span style="color:#ff4d4f">NETWORK</span></div>'
             f'<div style="font-size:12px;color:#8b95a3;margin:4px 0 14px 0">{E(TAGLINE)}</div><h1 style="font-size:17px;color:#e6e9ee;margin:0 0 10px 0">{E(title)}</h1>'
             + body + btn + xl + foot + '</td></tr></table></td></tr></table></body></html>')
    text = "\n\n".join([f"BLACKOUT.NETWORK — {title}", *paras] + ([f"{button[0]}: {button[1]}"] if button else [])
                       + [f"{l}: {u}" for l, u in (extra_links or [])] + ["--", DISCLAIMER, f"{BRAND} · {addr or '[Mailing address not set]'}"])
    return html_, text

# ------------------------------------------------------------------ MIME + pluggable senders
_POLICY = _email_policy.default.clone(max_line_length=998)
def build_mime(to, subject, html_, text, unsub_url=None, kind="issue", c=None):
    c = c or cfg(); m = EmailMessage(policy=_POLICY)   # 998-char lines: keeps List-Unsubscribe a plain <URL> (no RFC 2047 encoding)
    m["From"] = formataddr((c["from_name"], c["from_email"])); m["To"] = to; m["Subject"] = subject
    m["Date"] = format_datetime(now()); m["Message-ID"] = make_msgid(domain=(c["from_email"].split("@")[-1] or "blackout.network"))
    if c.get("reply_to"): m["Reply-To"] = c["reply_to"]
    if unsub_url:
        m["List-Unsubscribe"] = f"<{unsub_url}>"
        m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    m["List-Id"] = f"{BRAND} newsletter <newsletter.blackout.network>"
    m["X-Blackout-Kind"] = kind
    if kind != "issue": m["Auto-Submitted"] = "auto-generated"
    m.set_content(text); m.add_alternative(html_, subtype="html")
    return m

RESERVED = re.compile(r"(@|\.)(example\.(com|net|org)|test|invalid|localhost|example)$")
def sender_status():
    """Effective mode + why. Never returns secret values, only whether each required key is present."""
    e = env(); c = cfg(); want = (e.get("NEWSLETTER_SENDER") or "preview").strip().lower()
    if want not in SENDER_MODES: return {"requested": want, "mode": "preview", "reason": f"unknown sender '{want}': using preview"}
    need = {"smtp": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"], "resend": ["RESEND_API_KEY"], "brevo": ["BREVO_API_KEY"], "sendgrid": ["SENDGRID_API_KEY"]}.get(want, [])
    missing = [k for k in need if not e.get(k)]
    st = {"requested": want, "keys_present": {k: bool(e.get(k)) for k in need}, "live_sending_approved": bool(c.get("live_sending_approved")),
          "mailing_address_set": bool((c.get("mailing_address") or "").strip()), "from": c["from_email"]}
    if want == "preview": return {**st, "mode": "preview", "reason": "preview mode: emails are written to newsletter_outbox/ and nothing is sent"}
    if missing: return {**st, "mode": "preview", "reason": f"{want} selected but {', '.join(missing)} not set: using preview"}
    if not c.get("live_sending_approved"): return {**st, "mode": "preview", "reason": f"{want} configured but live_sending_approved is false: using preview"}
    if not st["mailing_address_set"]: return {**st, "mode": "preview", "reason": f"{want} configured but mailing_address is empty (CAN-SPAM): using preview"}
    return {**st, "mode": want, "reason": f"live: sending through {want}"}

def _outbox_write(msg, kind, sid):
    os.makedirs(P["outbox"], exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{kind}_{h(str(sid) + str(msg['To']), 8)}_{secrets.token_hex(2)}"
    with open(os.path.join(P["outbox"], stem + ".html"), "w") as f: f.write(msg.get_body(preferencelist=("html",)).get_content())
    with open(os.path.join(P["outbox"], stem + ".eml"), "wb") as f: f.write(bytes(msg))
    return stem + ".html"

def _http_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=20) as r: return r.status, r.read(2000).decode("utf-8", "replace")

def deliver(msg, kind="issue", sid=None, force_preview=False):
    """Send one message with the effective sender. Returns (ok, mode, outbox_file|None, error|None)."""
    mode = "preview" if force_preview else sender_status()["mode"]
    to = str(msg["To"])
    if mode != "preview" and RESERVED.search(to.lower()): mode = "preview"   # never hand a reserved/test domain to a real provider
    if mode == "preview":
        return True, "preview", _outbox_write(msg, kind, sid), None
    e = env(); c = cfg()
    html_ = msg.get_body(preferencelist=("html",)).get_content(); text = msg.get_body(preferencelist=("plain",)).get_content()
    hdrs = {k: str(msg[k]) for k in ("List-Unsubscribe", "List-Unsubscribe-Post") if msg[k]}
    try:
        if mode == "smtp":
            host, port = e["SMTP_HOST"], int(e.get("SMTP_PORT") or 587); sec = (e.get("SMTP_SECURITY") or "starttls").lower()
            S = smtplib.SMTP_SSL(host, port, timeout=30, context=ssl.create_default_context()) if sec == "ssl" else smtplib.SMTP(host, port, timeout=30)
            with S:
                if sec == "starttls": S.starttls(context=ssl.create_default_context())
                S.login(e["SMTP_USER"], e["SMTP_PASS"]); S.send_message(msg)
        elif mode == "resend":
            p = {"from": str(msg["From"]), "to": [to], "subject": str(msg["Subject"]), "html": html_, "text": text, "headers": hdrs}
            if c.get("reply_to"): p["reply_to"] = c["reply_to"]
            code, body = _http_json("https://api.resend.com/emails", p, {"Authorization": "Bearer " + e["RESEND_API_KEY"]})
            if code >= 300: raise RuntimeError(f"resend HTTP {code}: {body[:200]}")
        elif mode == "brevo":
            p = {"sender": {"name": c["from_name"], "email": c["from_email"]}, "to": [{"email": to}], "subject": str(msg["Subject"]),
                 "htmlContent": html_, "textContent": text, "headers": hdrs}
            if c.get("reply_to"): p["replyTo"] = {"email": c["reply_to"]}
            code, body = _http_json("https://api.brevo.com/v3/smtp/email", p, {"api-key": e["BREVO_API_KEY"]})
            if code >= 300: raise RuntimeError(f"brevo HTTP {code}: {body[:200]}")
        elif mode == "sendgrid":
            p = {"personalizations": [{"to": [{"email": to}]}], "from": {"email": c["from_email"], "name": c["from_name"]}, "subject": str(msg["Subject"]),
                 "content": [{"type": "text/plain", "value": text}, {"type": "text/html", "value": html_}], "headers": hdrs}
            if c.get("reply_to"): p["reply_to"] = {"email": c["reply_to"]}
            code, body = _http_json("https://api.sendgrid.com/v3/mail/send", p, {"Authorization": "Bearer " + e["SENDGRID_API_KEY"]})
            if code >= 300: raise RuntimeError(f"sendgrid HTTP {code}: {body[:200]}")
        return True, mode, None, None
    except Exception as ex:
        err = str(ex)
        for v in e.values():
            if v and len(v) >= 8: err = err.replace(v, "***")
        return False, mode, None, err[:300]

def send_transactional(row, kind):
    """kind: confirm | already. Logged to mail_log. Returns ok."""
    c = cfg(); L = links_for(row, c)
    if kind == "confirm":
        title = "Confirm your blackout.network newsletter subscription"
        paras = [f"Someone (hopefully you) asked to subscribe {row['email']} to the {BRAND} newsletter: {FREQS.get(row['frequency'], 'twice daily').lower()} briefs of the highest-severity, source-verified threats.",
                 f"Click the button to confirm. The link expires in {c['confirm_ttl_hours']} hours. If you didn't ask for this, ignore this email and nothing will be sent."]
        hb, tx = render_simple(title, paras, ("Confirm subscription", L["confirm"]), c=c); unsub = None
    else:
        title = "You're already subscribed to blackout.network"
        paras = [f"Someone asked to subscribe {row['email']}, which is already an active subscriber. Nothing was changed.",
                 "To change how often you get the brief or which categories you see, use Manage preferences. To stop, use the unsubscribe link."]
        hb, tx = render_simple(title, paras, ("Manage preferences", L["manage"]), c=c, extra_links=[("Unsubscribe", L["unsubscribe"])]); unsub = L["unsubscribe"]
    msg = build_mime(row["email"], title, hb, tx, unsub, kind=kind, c=c)
    ok, mode, f, err = deliver(msg, kind, row["id"])
    k = db(); k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file,subject,error) VALUES(?,?,?,?,?,?,?,?)",
                        (iso(now()), kind, row["id"], mode, "sent" if ok else "failed", f, title, err)); k.commit(); k.close()
    log(f"{kind} email for subscriber #{row['id']} via {mode}: {'ok' if ok else err}" + (f" -> newsletter_outbox/{f}" if f else ""), "mail")
    return ok

# ------------------------------------------------------------------ subscribe / confirm / unsubscribe / manage
GENERIC_OK = ("Almost done. If this address can be subscribed, a confirmation link is on its way. "
              "Open it within {ttl} hours to start receiving the brief. Check spam if you don't see it.")
def _clean_ints(ints):
    if isinstance(ints, str): ints = ["all"] if ints == "all" else [x for x in re.split(r"[,]+", ints) if x.strip()]
    ints = [x for x in (ints or []) if x == "all" or x in CATEGORIES] or ["all"]
    return ["all"] if ("all" in ints or set(ints) >= set(CATEGORIES)) else sorted(set(ints), key=CATEGORIES.index)

def subscribe(d, ip="", headers=None):
    """-> (code, {ok, message}). Same response whether the address is new, pending, active or unsubscribed (no enumeration)."""
    c = cfg(); rl = c["rate_limit"]
    if not csrf_ok(d, headers): return 403, {"ok": False, "message": "This form expired or came from another site. Reload the page and try again."}
    ipk = h("ip:" + (ip or "?")); generic = {"ok": True, "message": GENERIC_OK.format(ttl=c["confirm_ttl_hours"])}
    k = db()
    try:
        if hits(k, "sub_ip", ipk, 3600) >= int(rl["ip_per_hour"]):
            return 429, {"ok": False, "message": "Too many signup attempts from your network. Please try again in an hour."}
        hit(k, "sub_ip", ipk); k.commit()
        if str(d.get("website") or "").strip():          # honeypot: bots fill hidden fields; pretend success, store nothing
            log("honeypot tripped (signup ignored)", "abuse"); return 200, generic
        email, err = validate_email(d.get("email"))
        if err: return 400, {"ok": False, "message": err, "field": "email"}
        freq = d.get("frequency") or "twice"
        if freq not in FREQS: return 400, {"ok": False, "message": "Choose a frequency.", "field": "frequency"}
        ints = _clean_ints(d.get("interests") or ["all"])
        ek = h("em:" + email)
        if hits(k, "sub_email", ek, 86400) >= int(rl["email_per_day"]):
            return 429, {"ok": False, "message": "This address has had several signup attempts today. Please try again tomorrow, or use the link already sent."}
        hit(k, "sub_email", ek)
        t = iso(now()); r = k.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone()
        if r is None:
            k.execute("""INSERT INTO subscribers(email,status,frequency,interests,created,updated,signup_source,consent_ip_hash,confirm_sent_at)
                         VALUES(?,?,?,?,?,?,?,?,?)""", (email, "pending", freq, json.dumps(ints), t, t, str(d.get("source") or "form")[:20], ipk, t))
            kind = "confirm"
        elif r["status"] == "active":
            kind = "already"   # don't let a third party change an active subscriber's settings; tell the owner instead
        else:                  # pending or unsubscribed: (re)start double opt-in with the new choices
            k.execute("UPDATE subscribers SET status='pending', frequency=?, interests=?, updated=?, consent_ip_hash=?, confirm_sent_at=? WHERE id=?",
                      (freq, json.dumps(ints), t, ipk, t, r["id"]))
            kind = "confirm"
        k.commit(); row = k.execute("SELECT * FROM subscribers WHERE email=?", (email,)).fetchone()
    finally: k.close()
    send_transactional(row, kind)
    return 200, generic

def confirm(tok):
    """-> (ok|already|expired|invalid, row)."""
    st, r = token_sub(tok, "confirm")
    if st == "invalid" or st == "gone": return "invalid", None
    if st == "expired":
        return ("already", r) if (r is not None and r["status"] == "active") else ("expired", None)
    if r["status"] == "active": return "already", r
    if r["status"] != "pending": return "invalid", None     # unsubscribed since this link was sent: needs a fresh signup
    k = db(); t = iso(now())
    k.execute("UPDATE subscribers SET status='active', confirmed_at=?, unsubscribed_at=NULL, updated=? WHERE id=?", (t, t, r["id"])); k.commit()
    r = k.execute("SELECT * FROM subscribers WHERE id=?", (r["id"],)).fetchone(); k.close()
    log(f"subscriber #{r['id']} confirmed", "sub"); return "ok", r

def unsubscribe(tok, how="link"):
    """Idempotent. Signed tokens for erased addresses also report success (nothing is left to send to). Expired-but-genuine tokens still work."""
    st, r = token_sub(tok, "unsub")
    if st == "invalid": return "invalid", None
    if r is None: return "ok", None
    if r["status"] == "unsubscribed": return "ok", r
    k = db(); t = iso(now())
    k.execute("UPDATE subscribers SET status='unsubscribed', unsubscribed_at=?, updated=?, unsub_reason=? WHERE id=?", (t, t, how, r["id"])); k.commit()
    r = k.execute("SELECT * FROM subscribers WHERE id=?", (r["id"],)).fetchone(); k.close()
    log(f"subscriber #{r['id']} unsubscribed ({how})", "sub"); return "ok", r

def resubscribe(tok):
    """Undo from the unsubscribe page: allowed for 7 days, only for an address that had confirmed before."""
    st, r = token_sub(tok, "unsub")
    if st != "ok" or r is None or not r["confirmed_at"]: return False
    if r["status"] == "active": return True
    u = parse_t(r["unsubscribed_at"])
    if r["status"] != "unsubscribed" or not u or now() - u > timedelta(days=7): return False
    k = db(); t = iso(now()); k.execute("UPDATE subscribers SET status='active', unsubscribed_at=NULL, updated=? WHERE id=?", (t, r["id"])); k.commit(); k.close()
    log(f"subscriber #{r['id']} resubscribed (undo)", "sub"); return True

def manage(tok, d):
    st, r = token_sub(tok, "manage")
    if st != "ok" or r is None: return 400, {"ok": False, "message": "This link is invalid or expired. Use the link in your latest email."}
    if r["status"] != "active": return 400, {"ok": False, "message": "This address isn't subscribed right now. Sign up again to restart the brief."}
    freq = d.get("frequency") or r["frequency"]
    if freq not in FREQS: return 400, {"ok": False, "message": "Choose a frequency."}
    ints = _clean_ints(d.get("interests") or ["all"])
    k = db(); k.execute("UPDATE subscribers SET frequency=?, interests=?, updated=? WHERE id=?", (freq, json.dumps(ints), iso(now()), r["id"])); k.commit(); k.close()
    log(f"subscriber #{r['id']} changed preferences", "sub")
    return 200, {"ok": True, "message": f"Saved: {FREQS[freq].lower()}, {'all categories' if ints == ['all'] else ', '.join(ints)}."}

# ------------------------------------------------------------------ schedule (slots, idempotency, catch-up, retry)
def slot_time(day, name, c=None):
    c = c or cfg(); hh, mm = map(int, c["slots"][name].split(":"))
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=ET).astimezone(UTC)
def slot_key(day, name): return f"{day.isoformat()}@{name}"
def eligible(freq, slot, c=None):
    c = c or cfg(); g = c.get("global_frequency", "per_subscriber")
    if c.get("paused"): return False
    if g == "twice": return True
    if g == "once": return slot == ("evening" if freq == "evening" else "morning")
    return freq == "twice" or freq == slot
def next_slots(at=None, n=4, c=None):
    c = c or cfg(); at = at or now(); out = []
    d0 = at.astimezone(ET).date()
    for dd in range(0, 3):
        day = d0 + timedelta(days=dd)
        for s in SLOTS:
            t = slot_time(day, s, c)
            if t > at: out.append({"key": slot_key(day, s), "slot": s, "time": iso(t), "time_et": fmt_et(t)})
    return sorted(out, key=lambda x: x["time"])[:n]

def _send_one(k, srow, sub, key, slot, at, c):
    """Build + deliver one issue. Caller holds the 'sending' claim on srow."""
    issue = build_issue(dict(sub), at=at, slot=slot, c=c)
    if issue["empty"]:   # never send an empty email
        k.execute("UPDATE sends SET status='skipped_empty', sent_at=? WHERE id=?", (iso(now()), srow["id"])); k.commit(); return "skipped"
    L = links_for(sub, c); subj, hb, tx = render(issue, L, c)
    msg = build_mime(sub["email"], subj, hb, tx, L["unsubscribe"], "issue", c)
    ok, mode, f, err = deliver(msg, "issue", sub["id"])
    t = iso(now())
    if ok:
        k.execute("""UPDATE sends SET status='sent', sent_at=?, mode=?, outbox_file=?, subject=?, n_main=?, n_notable=?, n_watch=?, quiet=?, error=NULL,
                     attempts=attempts+1 WHERE id=?""", (t, mode, f, subj, len(issue["main"]), len(issue["notable"]), len(issue["watchlist"]), int(issue["quiet"]), srow["id"]))
        for sec in ("main", "notable", "watchlist"):
            for it in issue[sec]:
                k.execute("INSERT INTO sent_items(send_id,subscriber_id,cluster_id,title_norm,section,sent_at) VALUES(?,?,?,?,?,?)",
                          (srow["id"], sub["id"], it["cluster_id"], it["title_norm"], sec, iso(at)))
        k.execute("UPDATE subscribers SET last_sent_at=? WHERE id=?", (iso(at), sub["id"]))
        k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file,subject) VALUES(?,?,?,?,?,?,?)", (t, "issue", sub["id"], mode, "sent", f, subj))
        k.commit(); return "sent"
    att = (srow["attempts"] or 0) + 1; back = c["retry_backoff_minutes"]; final = att > len(back)
    nr = None if final else iso(now() + timedelta(minutes=back[att - 1]))
    k.execute("UPDATE sends SET status=?, attempts=?, next_retry=?, error=?, mode=? WHERE id=?", ("gave_up" if final else "failed", att, nr, err, mode, srow["id"]))
    k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,subject,error) VALUES(?,?,?,?,?,?,?)", (t, "issue", sub["id"], mode, "failed", subj, err))
    k.commit(); log(f"issue {key} to subscriber #{sub['id']} failed (attempt {att}): {err}", "error"); return "failed"

def run_slot(key, slot, at, c):
    k = db()
    try:
        for s in k.execute("SELECT * FROM subscribers WHERE status='active' AND confirmed_at<=?", (iso(at),)).fetchall():
            if eligible(s["frequency"], slot, c):
                k.execute("INSERT OR IGNORE INTO sends(subscriber_id,slot_key,status,created) VALUES(?,?,?,?)", (s["id"], key, "queued", iso(now())))
        k.commit()
        # a send claimed but never finished (worker killed mid-send) is never retried, so a restart can't cause a duplicate
        k.execute("UPDATE sends SET status='uncertain', error='worker stopped mid-send; not retried to avoid a duplicate' WHERE slot_key=? AND status='sending' AND next_retry<?",
                  (key, iso(now() - timedelta(minutes=15))))
        k.commit()
        due = k.execute("SELECT * FROM sends WHERE slot_key=? AND (status='queued' OR (status='failed' AND next_retry<=?))", (key, iso(now()))).fetchall()
        for srow in due:
            cur = k.execute("UPDATE sends SET status='sending', next_retry=? WHERE id=? AND status IN ('queued','failed')", (iso(now()), srow["id"])); k.commit()
            if cur.rowcount != 1: continue
            sub = k.execute("SELECT * FROM subscribers WHERE id=?", (srow["subscriber_id"],)).fetchone()
            if not sub or sub["status"] != "active":
                k.execute("UPDATE sends SET status='skipped_inactive' WHERE id=?", (srow["id"],)); k.commit(); continue
            try: _send_one(k, k.execute("SELECT * FROM sends WHERE id=?", (srow["id"],)).fetchone(), sub, key, slot, at, c)
            except Exception as ex:
                traceback.print_exc()
                k.execute("UPDATE sends SET status='failed', attempts=attempts+1, next_retry=?, error=? WHERE id=?",
                          (iso(now() + timedelta(minutes=c["retry_backoff_minutes"][0])), str(ex)[:300], srow["id"])); k.commit()
        agg = {r["status"]: r["n"] for r in k.execute("SELECT status, COUNT(*) n FROM sends WHERE slot_key=? GROUP BY status", (key,))}
        pending = agg.get("queued", 0) + agg.get("failed", 0) + agg.get("sending", 0)
        status = "running" if pending else ("done_with_errors" if (agg.get("gave_up") or agg.get("uncertain")) else "done")
        k.execute("UPDATE slot_runs SET status=?, n_targets=?, n_sent=?, n_failed=?, n_skipped=?, finished=? WHERE slot_key=?",
                  (status, sum(agg.values()), agg.get("sent", 0), agg.get("gave_up", 0) + agg.get("failed", 0) + agg.get("uncertain", 0),
                   agg.get("skipped_empty", 0) + agg.get("skipped_inactive", 0), None if pending else iso(now()), key))
        k.commit(); return status, agg
    finally: k.close()

def run_due(at=None):
    """Called every ~30 s by newsletter_worker.py. Idempotent per slot: the slot_runs row is written before anything is sent and each
    (subscriber, slot) pair is UNIQUE in sends, so restarts never double-send. Catch-up: a slot missed while the box was down is sent
    once if we're within catchup_hours (2 h) of it, otherwise recorded as skipped. Failed sends retry with backoff (2, 10, 30 min)."""
    c = cfg(); at = at or now(); res = []
    with _LOCK:
        d0 = at.astimezone(ET).date()
        k = db(); fresh = k.execute("SELECT COUNT(*) FROM slot_runs").fetchone()[0] == 0; k.close()
        for day in (d0 - timedelta(days=1), d0):
            for s in SLOTS:
                t = slot_time(day, s, c); key = slot_key(day, s)
                if t > at: continue
                k = db(); r = k.execute("SELECT * FROM slot_runs WHERE slot_key=?", (key,)).fetchone()
                late = (at - t) > timedelta(hours=float(c["catchup_hours"]))
                if r is None:
                    if c.get("paused"): status, note = "paused", "pause-all was on at slot time"
                    elif late and fresh: status, note = "skipped", "before the newsletter was installed"
                    elif late: status, note = "skipped", f"missed (worker or box down at slot time); more than {c['catchup_hours']} h late, so not sent"
                    else: status, note = "running", ("catch-up send" if (at - t) > timedelta(minutes=5) else "on time")
                    try: k.execute("INSERT INTO slot_runs(slot_key,slot_time,status,started,note) VALUES(?,?,?,?,?)", (key, iso(t), status, iso(at), note)); k.commit()
                    except sqlite3.IntegrityError: k.close(); continue
                    k.close(); log(f"slot {key} ({fmt_et(t)}): {status}: {note}", "slot")
                    if status != "running": res.append((key, status)); continue
                elif r["status"] != "running": k.close(); continue
                else:
                    if (at - t) > timedelta(hours=float(c["catchup_hours"]) + 1):   # stop retrying well after the window
                        k.execute("UPDATE sends SET status='gave_up', error=COALESCE(error,'')||' (retry window closed)' WHERE slot_key=? AND status IN ('queued','failed')", (key,))
                        k.commit()
                    k.close()
                st, agg = run_slot(key, s, at if r is None else max(parse_t(r["started"]) or at, t), c)
                res.append((key, st))
    return res

def cleanup_outbox(days=None):
    days = days if days is not None else int(cfg()["outbox_retention_days"])
    cut = time.time() - days * 86400; n = 0
    for f in (os.listdir(P["outbox"]) if os.path.isdir(P["outbox"]) else []):
        if f.startswith("sample_issue"): continue
        p = os.path.join(P["outbox"], f)
        if os.path.isfile(p) and os.path.getmtime(p) < cut: os.remove(p); n += 1
    k = db(); k.execute("DELETE FROM sent_items WHERE sent_at<?", (iso(now() - timedelta(days=7)),)); k.commit(); k.close()
    return n

# ------------------------------------------------------------------ background worker (separate light process, launched like streams_worker)
_W = {"checked": 0}
def worker_alive():
    try:
        pid = int(open(P["pid"]).read().strip())
        return "newsletter_worker" in open(f"/proc/{pid}/cmdline").read()
    except Exception: return False
def ensure_worker(force=False):
    if os.environ.get("NEWSLETTER_NO_WORKER"): return False
    if not force and time.time() - _W["checked"] < 60: return None
    _W["checked"] = time.time()
    if worker_alive(): return True
    os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
    lg = open(os.path.join(BASE, "logs", "newsletter_worker.log"), "a")
    subprocess.Popen(["nice", "-n", "10", "python3", P["worker"]], cwd=BASE, stdout=lg, stderr=lg, stdin=subprocess.DEVNULL, start_new_session=True)
    return True

# ------------------------------------------------------------------ admin
def admin_login(d, ip):
    k = db(); ipk = h("adm:" + (ip or "?"))
    try:
        if hits(k, "admin_fail", ipk, 600) >= 5: return 429, {"ok": False, "message": "Too many attempts. Wait 10 minutes."}
        try: real = open(P["pass"]).read().strip()
        except Exception: return 503, {"ok": False, "message": "Admin passcode file (ADMIN_PASSCODE.txt) is missing."}
        given = str(d.get("passcode") or "")
        if given and real and hmac.compare_digest(given.encode(), real.encode()):
            log("admin unlocked", "admin")
            return 200, {"ok": True, "session": make_token("admin", 0, 8 * 3600, ph=h(real, 12))}
        hit(k, "admin_fail", ipk); k.commit()
        return 403, {"ok": False, "message": "Wrong passcode."}
    finally: k.close()
def admin_ok(d):
    st, p = read_token(d.get("session"), "admin")
    if st != "ok": return False
    try: return p.get("ph") == h(open(P["pass"]).read().strip(), 12)   # changing the passcode ends every admin session
    except Exception: return False

def mask_email(e):
    l, _, d = (e or "").partition("@")
    return (l[:2] + "•" * max(1, min(6, len(l) - 2))) + "@" + d

def preview_issue(at=None, c=None):
    """The next issue as a 'twice daily, all categories' subscriber with no send history would get it."""
    c = c or cfg(); at = at or now()
    k = db(); last = k.execute("SELECT MAX(slot_time) FROM slot_runs WHERE status LIKE 'done%'").fetchone()[0]; k.close()
    nxt = next_slots(at, 1, c)[0]
    since = max(parse_t(last) or at - timedelta(hours=12), at - timedelta(hours=float(c["max_window_hours"])))
    issue = build_issue({"id": None, "frequency": "twice", "interests": '["all"]'}, at=at, since=since, slot=nxt["slot"], c=c)
    base = c["base_url"].rstrip("/")
    L = {"unsubscribe": f"{base}/newsletter", "manage": f"{base}/newsletter", "scoring": f"{base}/scoring", "site": f"{base}/#wire"}
    subj, hb, tx = render(issue, L, c)
    return issue, subj, hb, tx, nxt

def admin_stats():
    c = cfg(); k = db()
    try:
        cnt = {r["status"]: r["n"] for r in k.execute("SELECT status, COUNT(*) n FROM subscribers GROUP BY status")}
        freq = {r["frequency"]: r["n"] for r in k.execute("SELECT frequency, COUNT(*) n FROM subscribers WHERE status='active' GROUP BY frequency")}
        d0 = (now() - timedelta(days=13)).astimezone(ET).date(); growth = []
        for i in range(14):
            dd = d0 + timedelta(days=i); a0 = datetime(dd.year, dd.month, dd.day, tzinfo=ET); a, b = iso(a0), iso(a0 + timedelta(days=1))
            growth.append({"day": dd.isoformat(),
                           "signups": k.execute("SELECT COUNT(*) FROM subscribers WHERE created>=? AND created<?", (a, b)).fetchone()[0],
                           "confirmed": k.execute("SELECT COUNT(*) FROM subscribers WHERE confirmed_at>=? AND confirmed_at<?", (a, b)).fetchone()[0],
                           "unsubscribed": k.execute("SELECT COUNT(*) FROM subscribers WHERE unsubscribed_at>=? AND unsubscribed_at<?", (a, b)).fetchone()[0]})
        runs = [dict(r) for r in k.execute("SELECT * FROM slot_runs ORDER BY slot_time DESC LIMIT 20")]
        for r in runs:
            x = k.execute("SELECT COALESCE(SUM(n_main),0) m, COALESCE(SUM(n_notable),0) n, COALESCE(SUM(n_watch),0) w, COALESCE(SUM(quiet),0) q FROM sends WHERE slot_key=? AND status='sent'", (r["slot_key"],)).fetchone()
            r.update({"items_main": x["m"], "items_notable": x["n"], "items_watch": x["w"], "quiet": x["q"], "slot_time_et": fmt_et(parse_t(r["slot_time"]))})
        mails = [dict(r) for r in k.execute("SELECT ts,kind,mode,status,outbox_file,subject,error FROM mail_log ORDER BY id DESC LIMIT 15")]
        for m in mails: m["ts_et"] = fmt_et(parse_t(m["ts"]))
        recent = [{"id": r["id"], "email": mask_email(r["email"]), "status": r["status"], "frequency": r["frequency"],
                   "interests": json.loads(r["interests"] or '["all"]'), "created_et": fmt_et(parse_t(r["created"]))}
                  for r in k.execute("SELECT * FROM subscribers ORDER BY id DESC LIMIT 25")]
        ev = [dict(r) for r in k.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT 20")]
        for e in ev: e["ts_et"] = fmt_et(parse_t(e["ts"]))
        ed = [dict(r) for r in k.execute("SELECT * FROM editorial ORDER BY added DESC")]
    finally: k.close()
    outbox = len([f for f in os.listdir(P["outbox"]) if f.endswith(".eml")]) if os.path.isdir(P["outbox"]) else 0
    rmin, smin = main_rule(c)
    return {"counts": {"active": cnt.get("active", 0), "pending": cnt.get("pending", 0), "unsubscribed": cnt.get("unsubscribed", 0)},
            "active_by_frequency": freq, "growth": growth, "runs": runs, "mail": mails, "recent": recent, "events": ev, "editorial": ed,
            "next_slots": next_slots(n=4, c=c), "sender": sender_status(), "worker_running": worker_alive(), "outbox_eml": outbox,
            "settings": {x: c[x] for x in ("global_frequency", "paused", "slots", "max_watchlist", "min_main_items", "dedupe_hours", "catchup_hours",
                                           "base_url", "from_email", "from_name", "mailing_address", "live_sending_approved")},
            "rule": {"main_min_rank": rmin, "main_min_sources": smin}, "now_et": fmt_et(now())}

def admin_action(d):
    a = d.get("action")
    if a == "stats": return 200, admin_stats()
    if a == "preview":
        issue, subj, hb, tx, nxt = preview_issue()
        return 200, {"subject": subj, "html": hb, "text": tx, "next": nxt, "counts": {x: len(issue[x]) for x in ("main", "notable", "watchlist")},
                     "range": range_str(issue["start"], issue["end"])}
    if a == "test_outbox":
        issue, subj, hb, tx, nxt = preview_issue()
        msg = build_mime("preview@outbox.invalid", "[TEST] " + subj, hb, tx, cfg()["base_url"].rstrip("/") + "/newsletter", "test")
        ok, mode, f, err = deliver(msg, "test", 0, force_preview=True)
        k = db(); k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file,subject) VALUES(?,?,?,?,?,?,?)", (iso(now()), "test", None, mode, "sent", f, "[TEST] " + subj)); k.commit(); k.close()
        log(f"admin test issue written to newsletter_outbox/{f}", "admin")
        return 200, {"ok": True, "file": f, "message": f"Written to newsletter_outbox/{f} (plus .eml). Nothing was sent."}
    if a == "settings":
        c = cfg(); s = d.get("settings") or {}
        if "global_frequency" in s:
            if s["global_frequency"] not in ("per_subscriber", "once", "twice"): return 400, {"error": "global_frequency must be per_subscriber, once or twice"}
            c["global_frequency"] = s["global_frequency"]
        if "paused" in s: c["paused"] = bool(s["paused"])
        if "slots" in s:
            new = dict(c["slots"])
            for nm in SLOTS:
                v = (s["slots"] or {}).get(nm)
                if v is None: continue
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v)): return 400, {"error": f"{nm} time must be HH:MM (24 h, Eastern)"}
                new[nm] = v
            if new["morning"] >= new["evening"]: return 400, {"error": "the morning time must be earlier than the evening time"}
            c["slots"] = new
        for nm, lo, hi in (("max_watchlist", 0, 10), ("min_main_items", 0, 10)):
            if nm in s:
                try: v = int(s[nm])
                except Exception: return 400, {"error": f"{nm} must be a number"}
                if not lo <= v <= hi: return 400, {"error": f"{nm} must be {lo}–{hi}"}
                c[nm] = v
        save_cfg(c); log(f"admin changed settings: {json.dumps(s)[:300]}", "admin")
        return 200, {"ok": True, "settings": admin_stats()["settings"], "next_slots": next_slots(c=c)}
    if a == "export":
        k = db(); rows = k.execute("SELECT email, frequency, interests, created, confirmed_at FROM subscribers WHERE status='active' ORDER BY id").fetchall(); k.close()
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(["email", "frequency", "interests", "created_utc", "confirmed_utc"])
        for r in rows:
            w.writerow([("'" + r["email"]) if r["email"][:1] in "=+-@" else r["email"], r["frequency"], ",".join(json.loads(r["interests"] or '["all"]')), r["created"], r["confirmed_at"]])
        log(f"admin exported {len(rows)} active subscribers (CSV)", "admin")
        return 200, {"filename": f"blackout_newsletter_active_{now().astimezone(ET).strftime('%Y%m%d')}.csv", "csv": buf.getvalue(), "count": len(rows)}
    if a == "erase":
        k = db()
        try:
            if d.get("id"): r = k.execute("SELECT * FROM subscribers WHERE id=?", (int(d["id"]),)).fetchone()
            else:
                em, _ = validate_email(d.get("email")); em = em or str(d.get("email") or "").strip().lower()
                r = k.execute("SELECT * FROM subscribers WHERE email=?", (em,)).fetchone()
            if not r: return 404, {"ok": False, "message": "No subscriber with that address or id."}
            k.execute("DELETE FROM sent_items WHERE subscriber_id=?", (r["id"],)); k.execute("DELETE FROM sends WHERE subscriber_id=?", (r["id"],))
            k.execute("UPDATE mail_log SET subscriber_id=NULL WHERE subscriber_id=?", (r["id"],))
            k.execute("DELETE FROM attempts WHERE k=?", (h("em:" + r["email"]),))
            k.execute("DELETE FROM subscribers WHERE id=?", (r["id"],)); k.commit()
        finally: k.close()
        removed = 0   # outbox copies addressed to them (preview mode) are erased too
        if os.path.isdir(P["outbox"]):
            for f in os.listdir(P["outbox"]):
                if f.endswith(".eml"):
                    p = os.path.join(P["outbox"], f)
                    try:
                        with open(p, "rb") as fh: head = fh.read(4000).decode("utf-8", "replace")
                        if re.search(r"^To: " + re.escape(r["email"]) + r"\s*$", head, re.M | re.I):
                            os.remove(p); removed += 1
                            hp = p[:-4] + ".html"
                            if os.path.exists(hp): os.remove(hp)
                    except Exception: pass
        log(f"admin erased subscriber #{r['id']} (row, send history and {removed} outbox file(s) deleted)", "admin")
        return 200, {"ok": True, "message": f"Erased subscriber #{r['id']}: their row, send history and {removed} outbox copies are gone."}
    if a == "candidates":
        S = src()
        try:
            rows = S.execute("""SELECT cluster_id,title,category,rank,score,first_seen FROM clusters WHERE watchlist=1 AND first_seen>=?
                                ORDER BY score DESC, rank DESC LIMIT 25""", (iso(now() - timedelta(hours=24)),)).fetchall()
        finally: S.close()
        return 200, {"items": [dict(r) for r in rows]}
    if a in ("editorial_add", "editorial_remove"):
        cid = str(d.get("cluster_id") or "")
        if not re.fullmatch(r"[0-9a-f]{8,40}", cid): return 400, {"error": "cluster_id required"}
        k = db()
        if a == "editorial_add": k.execute("INSERT OR REPLACE INTO editorial(cluster_id,added,note) VALUES(?,?,?)", (cid, iso(now()), str(d.get("note") or "")[:200]))
        else: k.execute("DELETE FROM editorial WHERE cluster_id=?", (cid,))
        k.commit(); k.close(); log(f"admin {a} {cid}", "admin")
        return 200, {"ok": True}
    return 400, {"error": "unknown action"}

# ------------------------------------------------------------------ HTML pages
def page(title, body, robots="noindex"):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="{robots}"><title>{E(title)} · {BRAND}</title>'
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any"><link rel="stylesheet" href="/api/newsletter/app.css">'
            '<link rel="stylesheet" href="/api/translate/app.css"></head><body class="nl-page"><a class="skip" href="#main">Skip to content</a>'
            f'<header><h1>BLACKOUT.<b>NETWORK</b> · {E(title)}<small>{E(TAGLINE)}</small></h1>'
            '<nav class="nl-nav" aria-label="Site"><a href="/#wire">← Dashboard</a><a href="/scoring">How we score</a><a href="/newsletter" class="on">✉ Newsletter</a></nav></header>'
            f'<div class="nl-wrap" id="main" role="main">{body}</div>'
            f'<footer>Research-only data · {BRAND} · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · <a href="/newsletter">Newsletter</a></footer>'
            '<script src="/api/translate/app.js"></script><script src="/api/search/app.js"></script></body></html>')

def form_html(mode="page"):
    """Server-rendered signup form (works without JavaScript; app.js enhances it in place)."""
    c = cfg(); sl = c["slots"]; uid = "nlp" if mode == "page" else "nlc"
    cats = "".join(f'<label class="nl-chk"><input type="checkbox" name="interests" value="{E(x)}" checked> {E(x)}</label>' for x in CATEGORIES)
    return (f'<form method="post" action="/api/newsletter/subscribe" class="nl-form" data-nl-form novalidate>'
            f'<input type="hidden" name="csrf" value="{E(csrf_token())}"><input type="hidden" name="source" value="{E(mode)}">'
            f'<label for="{uid}_email">Email address</label>'
            f'<div class="nl-row"><input id="{uid}_email" type="email" name="email" required maxlength="254" autocomplete="email" inputmode="email" placeholder="you@example.org" aria-describedby="{uid}_msg">'
            '<button class="pri" type="submit">Subscribe</button></div>'
            f'<fieldset class="nl-freq"><legend>How often</legend>'
            + "".join(f'<label class="nl-radio"><input type="radio" name="frequency" value="{k}"{" checked" if k == "twice" else ""}> {E(v)}'
                      f'<span class="nl-sm"> ({E(sl["morning"] + " & " + sl["evening"] if k == "twice" else sl[k])} ET)</span></label>' for k, v in FREQS.items())
            + '</fieldset>'
            f'<details class="nl-cats-d"><summary>Categories: all (optional: pick only some)</summary><div class="nl-cats">{cats}</div></details>'
            '<div class="nl-hp" aria-hidden="true"><label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
            f'<p class="nl-msg" id="{uid}_msg" role="status" aria-live="polite"></p>'
            f'<p class="nl-sm nl-priv">🔒 {E(PRIVACY)} Double opt-in: nothing is sent until you confirm. {E(DISCLAIMER)}</p></form>')

def signup_page():
    rmin, smin = main_rule()
    body = ('<section class="nl-card"><h2>✉ The blackout.network brief, in your inbox</h2>'
            '<p class="nl-lede">Once or twice a day: the highest-severity threats that cleared the main-feed bar, each as a one-paragraph brief '
            '(what happened, where, when, how well it\'s confirmed, and the raw source link so you can verify it yourself), plus a short watchlist '
            'of unconfirmed single-source reports. Nothing is repeated within 12 hours. Quiet windows get a short "nothing qualified" note, never filler.</p>'
            '<div id="nl_app" data-mode="page">' + form_html("page") + '</div>'
            '<p class="nl-sm"><a href="/newsletter/sample" target="_blank" rel="noopener">See a sample issue built from live data →</a></p></section>'
            '<section class="nl-card nl-faq"><h3>How it works</h3><ul>'
            '<li><b>Double opt-in.</b> You get a confirmation email first. Nothing else is sent until you click it.</li>'
            f'<li><b>What makes the main feed.</b> Rank {rmin}+ items confirmed by {smin}+ independent sources (the same bar as instant alerts). '
            'If fewer than 3 qualify, up to 3 "Also notable" items (confirmed rank 5–6, or a high rank from one official source) are added and labeled. '
            'See <a href="/scoring">How we score</a>.</li>'
            '<li><b>Watchlist.</b> Up to 5 low-confidence, single-source reports, each clearly labeled UNCONFIRMED.</li>'
            '<li><b>Times.</b> Morning and evening briefs go out at the times shown on the form, Eastern Time.</li>'
            '<li><b>Leaving.</b> Every email has a one-click unsubscribe link and a manage-preferences link. No account or login.</li>'
            f'<li><b>Privacy.</b> {E(PRIVACY)} Your address is never sold, shared or shown publicly.</li></ul></section>'
            '<script src="/api/newsletter/app.js"></script>')
    return page("Newsletter", body, robots="index")

def result_page(title, msg, ok=True, extra=""):
    return page(title, f'<section class="nl-card nl-result {"ok" if ok else "warn"}"><h2>{"✓" if ok else "ⓘ"} {E(title)}</h2><p>{E(msg)}</p>{extra}'
                '<p class="nl-sm"><a href="/#wire">Go to the dashboard</a> · <a href="/newsletter">Newsletter home</a></p></section>')

def prefs_form(tok, r):
    try: ints = json.loads(r["interests"] or '["all"]')
    except Exception: ints = ["all"]
    allc = "all" in ints
    return (f'<form class="nl-form" id="nl_manage" method="post" action="/api/newsletter/manage"><input type="hidden" name="token" value="{E(tok)}">'
            '<fieldset class="nl-freq"><legend>How often</legend>' + "".join(
                f'<label class="nl-radio"><input type="radio" name="frequency" value="{k}"{" checked" if r["frequency"] == k else ""}> {E(v)}</label>' for k, v in FREQS.items()) + '</fieldset>'
            '<fieldset><legend>Categories</legend><div class="nl-cats">' +
            "".join(f'<label class="nl-chk"><input type="checkbox" name="interests" value="{E(x)}"{" checked" if allc or x in ints else ""}> {E(x)}</label>' for x in CATEGORIES) +
            '</div><p class="nl-sm">Leave all ticked (or none) to get every category.</p></fieldset><button class="pri" type="submit">Save preferences</button> '
            '<p class="nl-msg" role="status" aria-live="polite"></p></form>')

def handle_get(path, qs):
    if "/admin" in path: return 404, {"error": "not found"}   # admin is not part of the public node
    ensure_worker()
    q1 = lambda k: (qs.get(k) or [""])[0]
    if path.startswith("/api/newsletter/"):
        name = path[len("/api/newsletter/"):]
        if name in ("app.js", "app.css"):
            with open(os.path.join(P["static"], name), "rb") as f: return 200, f.read(), ("application/javascript" if name.endswith(".js") else "text/css")
        if name == "meta":
            c = cfg()
            return 200, {"csrf": csrf_token(), "frequencies": FREQS, "categories": CATEGORIES, "slots": c["slots"], "privacy": PRIVACY,
                         "disclaimer": DISCLAIMER, "rule": dict(zip(("rank", "sources"), main_rule(c))), "confirm_ttl_hours": c["confirm_ttl_hours"]}
        if name == "form": return 200, form_html((qs.get("mode") or ["card"])[0] if (qs.get("mode") or ["card"])[0] in ("card", "page") else "card"), "text/html"
        return 404, {"error": "not found"}
    if path == "/api/newsletter": return 200, {"ok": True, "pages": ["/newsletter", "/newsletter/sample"]}
    if path == "/newsletter": return 200, signup_page(), "text/html"
    if path == "/newsletter/sample":
        issue, subj, hb, tx, nxt = preview_issue()
        bar = (f'<div style="background:#181d23;color:#8b95a3;font:12px system-ui,sans-serif;padding:8px;text-align:center;border-bottom:1px solid #252b33">Sample issue, built live from '
               f'the current data window. Subject line: <b style="color:#e6e9ee">{E(subj)}</b> · <a style="color:#4aa3ff" href="/newsletter">Subscribe</a> · '
               f'<a style="color:#4aa3ff" href="/#wire">Dashboard</a></div>')
        return 200, hb.replace('<body style="margin:0;padding:0;background:#0b0d10">', '<body style="margin:0;padding:0;background:#0b0d10">' + bar, 1), "text/html"
    if path == "/newsletter/confirm":
        st, r = confirm(q1("token"))
        if st == "ok":
            return 200, result_page("Subscription confirmed", f"You're in. {r['email']} will get the {FREQS[r['frequency']].lower()} brief from the next scheduled send. "
                                    "Every email has a one-click unsubscribe link.", True,
                                    f'<p><a class="nl-btn" href="/newsletter/manage?token={E(sub_token("manage", r))}">Manage preferences</a></p>'), "text/html"
        if st == "already": return 200, result_page("Already confirmed", "This subscription was already confirmed. Nothing changed.", True), "text/html"
        if st == "expired":
            return 410, result_page("Confirmation link expired", f"Confirmation links expire after {cfg()['confirm_ttl_hours']} hours. Sign up again to get a new one.", False,
                                    '<p><a class="nl-btn" href="/newsletter">Sign up again</a></p>'), "text/html"
        return 400, result_page("Link not valid", "This confirmation link is invalid, was altered, or the address was unsubscribed since it was sent. Sign up again for a fresh link.", False,
                                '<p><a class="nl-btn" href="/newsletter">Go to signup</a></p>'), "text/html"
    if path == "/newsletter/unsubscribe":
        tok = q1("token"); st, r = unsubscribe(tok, "link")
        if st == "ok":
            undo = (f'<form class="nl-undo" method="post" action="/api/newsletter/resubscribe"><input type="hidden" name="token" value="{E(tok)}">'
                    '<button type="submit" class="nl-btn-ghost">Unsubscribed by mistake? Resubscribe</button></form>') if (r is not None and r["confirmed_at"]) else ""
            return 200, result_page("You're unsubscribed", "You won't get any more newsletter emails at this address. No login needed, and opening this link again changes nothing.", True, undo), "text/html"
        return 400, result_page("Link not valid", "This unsubscribe link is invalid or was altered. Use the unsubscribe link from your most recent email.", False), "text/html"
    if path == "/newsletter/manage":
        tok = q1("token"); st, r = token_sub(tok, "manage")
        if st != "ok" or r is None:
            return 400, result_page("Link not valid", "This preferences link is invalid, expired, or the subscription was erased. Use the link in your latest email.", False), "text/html"
        if r["status"] != "active":
            return 200, result_page("Not currently subscribed", "This address isn't receiving the newsletter. Sign up again to restart it.", False,
                                    '<p><a class="nl-btn" href="/newsletter">Sign up</a></p>'), "text/html"
        body = (f'<section class="nl-card"><h2>Manage your newsletter</h2><p>Subscribed: <b>{E(mask_email(r["email"]))}</b>. Changes apply from the next send.</p>'
                + prefs_form(tok, r) + f'<p class="nl-sm"><a href="/newsletter/unsubscribe?token={E(sub_token("unsub", r))}">Unsubscribe instead</a></p></section>'
                '<script src="/api/newsletter/app.js"></script>')
        return 200, page("Manage newsletter", body), "text/html"
    if path == "/newsletter/admin":
        body = ('<section class="nl-card" id="nla_login"><h2>Newsletter admin</h2><p>Enter the dashboard admin passcode (the same one that changes the scan interval).</p>'
                '<form id="nla_form" class="nl-form" autocomplete="off"><label for="nla_pass">Admin passcode</label><div class="nl-row"><input type="password" id="nla_pass" autocomplete="current-password" required>'
                '<button class="pri" type="submit">Unlock</button></div><p class="nl-msg" role="status" aria-live="polite"></p></form></section>'
                '<div id="nla_app" hidden></div><script src="/api/newsletter/admin.js"></script>')
        return 200, page("Newsletter admin", body), "text/html"
    return 404, {"error": "not found"}

def _form(raw):
    try:
        f = urllib.parse.parse_qs((raw or b"").decode("utf-8", "replace"), keep_blank_values=True)
        return {k: (v if k == "interests" else v[0]) for k, v in f.items()}
    except Exception: return {}

def handle_post(path, d, ip=None, qs=None, headers=None, raw=None):
    if "/admin" in path: return 404, {"error": "not found"}   # admin is not part of the public node
    ensure_worker()
    qs = qs or {}; headers = {k.lower(): v for k, v in (headers or {}).items()}
    html_mode = False
    if not d and raw:   # classic form post (no JavaScript) or RFC 8058 one-click body
        d = _form(raw); html_mode = "x-www-form-urlencoded" in (headers.get("content-type") or "")
    if path in ("/newsletter/unsubscribe", "/api/newsletter/unsubscribe"):
        tok = (qs.get("token") or [""])[0] or d.get("token")
        st, r = unsubscribe(tok, "one-click" if path == "/newsletter/unsubscribe" else "page")
        if path == "/newsletter/unsubscribe": return (200, "Unsubscribed.", "text/plain") if st == "ok" else (400, "Invalid unsubscribe link.", "text/plain")
        return (200, {"ok": True}) if st == "ok" else (400, {"ok": False, "message": "Invalid link."})
    if path == "/api/newsletter/subscribe":
        code, body = subscribe(d, ip or "", headers)
        if html_mode:
            return code, result_page("Check your inbox" if body.get("ok") else "Couldn't subscribe", body["message"], bool(body.get("ok")),
                                     "" if body.get("ok") else '<p><a class="nl-btn" href="/newsletter">Try again</a></p>'), "text/html"
        return code, body
    if not origin_ok(headers): return 403, {"ok": False, "message": "Cross-site request blocked."}
    if path == "/api/newsletter/resubscribe":
        ok = resubscribe(d.get("token"))
        if html_mode:
            return (200, result_page("Resubscribed", "Welcome back. You'll get the brief again from the next send.", True), "text/html") if ok else \
                   (400, result_page("Couldn't resubscribe", "The 7-day undo window has passed or the link is invalid. Sign up again instead.", False,
                                     '<p><a class="nl-btn" href="/newsletter">Sign up</a></p>'), "text/html")
        return (200, {"ok": True}) if ok else (400, {"ok": False})
    if path == "/api/newsletter/manage":
        code, body = manage(d.get("token"), d)
        if html_mode: return code, result_page("Preferences saved" if body.get("ok") else "Couldn't save", body["message"], bool(body.get("ok"))), "text/html"
        return code, body
    if path == "/api/newsletter/admin/login": return admin_login(d, ip or "")
    if path == "/api/newsletter/admin":
        if not admin_ok(d): return 401, {"error": "Admin session expired. Unlock again."}
        return admin_action(d)
    return 404, {"error": "not found"}
