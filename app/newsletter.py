"""blackout.network newsletter add-on (hot-reloaded by server.py via addons.py).

Pages:  GET /newsletter (signup) · /newsletter/confirm?token= · /newsletter/unsubscribe?token= · /newsletter/manage?token=
        /newsletter/sources?token= (personalized source suggestions; same signed "manage" token as the categories page)
        /newsletter/admin (admin passcode) · /newsletter/sample (live sample issue)
API:    GET  /api/newsletter/meta · /api/newsletter/app.js|app.css|admin.js
        POST /api/newsletter/subscribe · /api/newsletter/manage · /api/newsletter/add_category · /api/newsletter/resubscribe · /api/newsletter/unsubscribe
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
import sitenav   # shared header, tab bar and SEO tags (t301/t302)

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
    "sources_db": os.environ.get("NEWSLETTER_SOURCES_DB", os.path.join(BASE, "sources.db")),            # Sources catalog (read-only here)
    "dir_db": os.environ.get("NEWSLETTER_DIR_DB", os.path.join(BASE, "sources_dir", "directory.db")),  # global directory (read-only here)
}
BRAND = "BLACKOUT.NETWORK"   # brand is always written in capitals in every email and page (t300)
TAGLINE = "Ask better questions."   # global tagline (t326u): small supporting line under the masthead domain and in the footer
DISCLAIMER = ("Research only. BLACKOUT.NETWORK is not an official warning service. Items are machine-collected and scored; "
              "always verify with official sources before acting.")
PRIVACY = "Email only used for this newsletter; unsubscribe anytime."
CATEGORIES = ["war/conflict", "political", "natural disaster", "disease", "cyber", "space weather", "financial", "ufo/uap", "spiritual/religious", "other"]
FREQS = {"twice": "Twice daily (morning + evening)", "morning": "Once daily: morning", "evening": "Once daily: evening"}
SLOTS = ("morning", "evening")
SENDER_MODES = ("preview", "smtp", "resend", "brevo", "sendgrid")
DEFAULTS = {
    "base_url": "https://blackout.network",
    "from_name": "BLACKOUT.NETWORK",
    "from_email": "hello@blackout.network",
    "reply_to": "",
    "mailing_address": "PO Box 1228, Lake Mary, FL 32746",
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
    "transactional_sending_approved": False,   # confirm/already emails only; issues still need live_sending_approved
    "outbox_retention_days": 30,
    "retry_backoff_minutes": [2, 10, 30],
    "editorial_ttl_hours": 24,
    "dedupe_days": 14,              # a story already sent is never repeated for this long, except as an UPDATE when it develops
    "max_update_items": 5,          # per section (Stories you follow / Developing stories)
    "follow_max": 50,               # active follows per subscriber
    "audience_db": "",              # override for the subscriber list used by live sending (default: render_mirror/newsletter.db when live)
    "breaking": {"enabled": True, "fresh_hours": 6, "min_gap_hours": 2, "max_per_day": 3, "max_items": 3, "quiet_start": 22, "quiet_end": 7, "quiet_min_rank": 9},
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
CREATE TABLE IF NOT EXISTS follows(subscriber_id INTEGER NOT NULL, cluster_id TEXT NOT NULL, title TEXT, created TEXT, active INTEGER NOT NULL DEFAULT 1,
  unfollowed_at TEXT, PRIMARY KEY(subscriber_id, cluster_id));
CREATE INDEX IF NOT EXISTS fo_c ON follows(cluster_id, active);
CREATE TABLE IF NOT EXISTS breaking_seen(cluster_id TEXT PRIMARY KEY, ts TEXT, rank INTEGER, rule TEXT, status TEXT, run_id INTEGER);
CREATE TABLE IF NOT EXISTS breaking_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, cluster_ids TEXT, status TEXT, mode TEXT,
  n_targets INTEGER DEFAULT 0, n_sent INTEGER DEFAULT 0, note TEXT);
"""
MIGRATE = [("sent_items", "rank", "INTEGER"), ("sent_items", "n_items", "INTEGER"), ("sent_items", "eff", "INTEGER"), ("sent_items", "fams", "TEXT"),
           ("sent_items", "kind", "TEXT"), ("subscribers", "breaking", "INTEGER NOT NULL DEFAULT 1")]
_INIT = {}
def db():
    c = sqlite3.connect(P["db"], timeout=15); c.row_factory = sqlite3.Row
    if _INIT.get(P["db"]) is None:
        c.execute("PRAGMA journal_mode=WAL"); c.executescript(SCHEMA)
        for t, col, decl in MIGRATE:   # additive, idempotent column migrations (t303)
            if col not in {x[1] for x in c.execute(f"PRAGMA table_info({t})")}:
                try: c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {decl}")
                except sqlite3.OperationalError: pass
        c.commit(); _INIT[P["db"]] = True
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
    base = (c or cfg())["base_url"].rstrip("/"); mt = sub_token('manage', row)
    return {"unsubscribe": f"{base}/newsletter/unsubscribe?token={sub_token('unsub', row)}",
            "manage": f"{base}/newsletter/manage?token={mt}",
            "breaking_off": f"{base}/newsletter/breaking_off?token={mt}",
            "categories": f"{base}/newsletter/manage?token={mt}",   # "Manage my subscription categories" button
            "sources": f"{base}/newsletter/sources?token={mt}",     # "Find new sources" button
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

TIERS = {0: ("Noise", "local trivia"), 1: ("Background", "very local"), 2: ("Minor", "local"), 3: ("Minor regional", "one-region"),
         4: ("Regional", "one region or state"), 5: ("Significant", "regional or national"), 6: ("Serious", "national"),
         7: ("Major", "national or multi-country"), 8: ("Severe", "multi-country or continental"), 9: ("Critical", "global"),
         10: ("Catastrophic", "global")}   # labels + scope from /scoring (scoring.py)
CAT_WHY = {
    "war/conflict": "Armed conflict can escalate fast and ripple into energy prices, shipping lanes, flights and travel advisories.",
    "political": "Emergency declarations, coups and unrest can quickly shift aid, security, travel safety and markets.",
    "natural disaster": "Expect knock-on effects in the affected area: power and water outages, blocked roads, displacement and supply gaps.",
    "disease": "Outbreaks can cross borders before official guidance catches up; watch for health-agency advisories and travel notices.",
    "cyber": "Attacks on widely used systems can knock out services you depend on; check vendor advisories and patch.",
    "space weather": "Strong geomagnetic activity can degrade GPS, HF radio and satellites, and at the extreme it stresses power grids.",
    "financial": "Market shocks can spread to savings, credit, prices and supply chains.",
    "ufo/uap": "Unexplained aerial reports sometimes lead to airspace closures or military responses.",
    "spiritual/religious": "Religious flashpoints can spark unrest, security alerts and travel restrictions.",
    "other": "Could affect safety, services or travel in the affected area.",
}
def tier(rank): return TIERS.get(max(0, min(10, int(rank or 0))), ("", ""))
def why_it_matters(r, official=False):
    """Deterministic 'why it matters' line built only from the item's own data: rank tier + scope (/scoring), the category's typical
    knock-on effects, an official-source flag, a population figure quoted by the source, and spread speed. Nothing is invented."""
    rk = int(r["rank"] or 0); name, scope = tier(rk)
    out = [f"Rated {name} ({rk}/10), {scope} scale."]
    out.append(CAT_WHY.get(r["category"] or "other", CAT_WHY["other"]))
    m = re.search(r"([\d]+(?:\.\d+)?) million", f"{r['title'] or ''} {r['brief'] or ''}")
    if m:
        try: out.append(f"The source estimates about {float(m.group(1)):g} million people affected.")
        except ValueError: pass
    if official: out.append("An official agency is on record.")
    try: m3 = int(r["mentions_3h"] or 0); rising = int(r["rising"] or 0)
    except (KeyError, IndexError, TypeError, ValueError): m3, rising = 0, 0
    if rising and m3 >= 2: out.append(f"Spreading: {m3} reports in the last 3 hours.")
    return " ".join(out)

def wire_url(cid, since=None, c=None, anchor=""):
    """Permalink of one Wire story on the site (story.py). since= highlights what's new; readers reach the original sources from there."""
    base = (c or cfg())["base_url"].rstrip("/")
    q = ("?" + urllib.parse.urlencode({"since": iso(since)})) if since else ""
    return f"{base}/wire/{cid}{q}{anchor}"

def _row_get(r, k, d=None):
    try: return r[k]
    except (KeyError, IndexError): return d

_LEAD = re.compile(r"^[^\w(\"'“‘\[]+")
_HYPE = re.compile(r"^(?:#?(?-i:BREAKING(?: NEWS)?|JUST IN)\b\s*[:!\-–—|]*\s*|(?:BREAKING(?: NEWS)?|JUST IN|URGENT|ALERT|FLASH|DEVELOPING)\s*[:!\-–—|]+\s*)+", re.I)
def clean_title(t):
    """Readable headline: drop leading flag/emoji runs and dash bullets, trailing @handles, squeeze spaces. Wording is never changed."""
    t = re.sub(r"\s+", " ", t or "").strip()
    t = _LEAD.sub("", t); t = _HYPE.sub("", t); t = _LEAD.sub("", t); t = re.sub(r"(\s+@[A-Za-z0-9_.]{2,30})+\.?$", "", t).strip()
    return t or re.sub(r"\s+", " ", t or "").strip()

def item_of(r, section, official=0, editorial=False):
    fams = _fams(r); eff = int(r["eff_families"] or 0)
    t = parse_t(r["event_time"]) or parse_t(r["first_seen"])
    if t and t > now() + timedelta(minutes=10): t = parse_t(r["first_seen"])   # forecast times: report when first seen
    if editorial:
        conf = "UNCONFIRMED: single source, included under the editorial exception for a potential national- or civilizational-scale event"
    elif eff >= 2:
        conf = f"Confirmed by {eff} independent source families ({', '.join(fams[:5])}{', …' if len(fams) > 5 else ''})" if fams else f"Confirmed by {eff} independent sources"
    else:
        conf = f"Single {'official ' if official else ''}source ({', '.join(fams[:2]) or 'one outlet'})" + ("" if official else ", not independently confirmed")
    return {"cluster_id": r["cluster_id"], "section": section, "title": clean_title(r["title"]), "what": clean_title(_what(r)),
            "where": (r["location"] or "").strip() or None, "lat": r["lat"], "lon": r["lon"], "when": t, "category": r["category"] or "other",
            "rank": int(r["rank"] or 0), "score": int(r["score"] or 0), "eff": eff, "families": fams, "confidence": conf,
            "unconfirmed": editorial or eff < 2, "official": bool(official), "editorial": editorial, "links": _links(r),
            "title_norm": norm_title(r["title"]), "first_seen": parse_t(r["first_seen"]), "n_items": int(_row_get(r, "n_items", 0) or 0),
            "why": why_it_matters(r, official), "tier": tier(r["rank"])[0], "update": None, "breaking": False, "followed": False}

# ---- developing stories: what is new in a cluster since a subscriber last got it
def developments(S, cid, since):
    """-> (new alerts since `since`, new independent families not seen before `since`) for one cluster, from blackout.db alerts."""
    rows = S.execute("SELECT source,family,title,first_seen,official,source_url FROM alerts WHERE cluster_id=? ORDER BY first_seen", (cid,)).fetchall()
    old, new = set(), []
    for x in rows:
        t = parse_t(x["first_seen"])
        if t is not None and since is not None and t > since: new.append(x)
        else: old.add(x["family"])
    nf = sorted({x["family"] for x in new if x["family"] and x["family"] not in old})
    return new, nf

def _update_of(r, h0, new, new_fams, followed, since, c=None):
    """UPDATE block for a story the subscriber already got (or follows), or None if nothing qualifies as new.
    Not followed: the rank went up or at least one NEW independent source family reported it.
    Followed: any new report or any rank change."""
    rk = int(r["rank"] or 0); was = h0.get("rank") if h0 else None
    up = was is not None and rk > int(was); down = was is not None and rk < int(was)
    if not (up or new_fams or (followed and (new or down))): return None
    reps = []
    for x in sorted(new, key=lambda y: y["first_seen"] or "", reverse=True)[:4]:
        reps.append({"source": re.sub(r"^(Google News|Bluesky|RSS):\s*", "", str(x["source"] or x["family"] or ""))[:60],
                     "title": _cut(re.sub(r"\s+", " ", x["title"] or "").strip(), 160), "when": parse_t(x["first_seen"]), "official": bool(x["official"])})
    return {"since": since, "rank_from": was, "rank_to": rk, "up": up, "down": down, "n_new": len(new), "new_fams": new_fams, "reports": reps,
            "timeline": wire_url(r["cluster_id"], since, c, "#timeline")}

def _history(sid, at, c):
    """cluster_id -> what this subscriber was last sent about it (time, rank), over the last dedupe_days. Also the normalized titles."""
    out, titles = {}, []
    if not sid: return out, titles
    k = db(); cut = iso(at - timedelta(days=float(c.get("dedupe_days") or 14)))
    try:
        for x in k.execute("SELECT * FROM sent_items WHERE subscriber_id=? AND sent_at>=? ORDER BY sent_at", (sid, cut)):
            out[x["cluster_id"]] = {"sent_at": parse_t(x["sent_at"]), "rank": x["rank"], "kind": x["kind"], "section": x["section"]}
            titles.append(x["title_norm"] or "")
    finally: k.close()
    return out, titles

def _breaking_ids():
    try:
        k = db(); ids = {x[0] for x in k.execute("SELECT cluster_id FROM breaking_seen")}; k.close(); return ids
    except Exception: return set()

def build_issue(sub, at=None, since=None, slot="morning", conn=None, c=None):
    """Select content for one subscriber. sub: dict with id (None for previews), frequency, interests, last_sent_at, follows (cluster ids).
    Window: since the subscriber's last send, capped at max_window_hours (24 h).
    Dedupe: a story this subscriber already got (any edition or breaking alert in the last dedupe_days, or a near-duplicate title) is never
    repeated. It comes back only as an UPDATE when it is developing (rank up, or a new independent source; for followed stories any new report
    or rank change), showing only what is new since they last got it.
    Returns follow / main / updates / notable / watchlist / bluf / quiet / empty."""
    c = c or cfg(); at = at or now()
    win = timedelta(hours=float(c["max_window_hours"]))
    last = parse_t(sub.get("last_sent_at")) if sub else None
    start = since or (max(last, at - win) if last else at - win)
    rmin, smin = main_rule(c)
    try: ints = set(json.loads(sub.get("interests") or '["all"]')) if sub else {"all"}
    except Exception: ints = {"all"}
    allcats = "all" in ints or not ints
    follows = set((sub or {}).get("follows") or [])
    hist, sent_titles = _history(sub.get("id") if sub else None, at, c)
    s0, s1 = iso(start), iso(at)
    ed_ids = []
    try:
        k = db(); ed_ids = [x[0] for x in k.execute("SELECT cluster_id FROM editorial WHERE added>=?", (iso(at - timedelta(hours=float(c["editorial_ttl_hours"]))),))]; k.close()
    except Exception: pass
    own = conn is None; S = conn or src(); dev = {}
    try:
        rows = S.execute("""SELECT * FROM clusters WHERE watchlist=0 AND rank>=? AND
              ((first_seen>=? AND first_seen<=?) OR (high_at>=? AND high_at<=?)) ORDER BY rank DESC, score DESC, eff_families DESC LIMIT 400""",
              (int(c["notable_min_rank"]), s0, s1, s0, s1)).fetchall()
        wrows = S.execute("""SELECT * FROM clusters WHERE watchlist=1 AND first_seen>=? AND first_seen<=?
              ORDER BY rank DESC, score DESC, mentions_3h DESC, first_seen DESC LIMIT 300""", (s0, s1)).fetchall()
        erows = S.execute(f"SELECT * FROM clusters WHERE cluster_id IN ({','.join('?' * len(ed_ids))})", ed_ids).fetchall() if ed_ids else []
        track = sorted(set(hist) | follows)
        trows = S.execute(f"SELECT * FROM clusters WHERE cluster_id IN ({','.join('?' * len(track))})", track).fetchall() if track else []
        ids = list({r["cluster_id"] for r in list(rows) + list(erows) + list(trows)})
        offi = {}
        if ids:
            for x in S.execute(f"SELECT cluster_id, MAX(official) o FROM alerts WHERE cluster_id IN ({','.join('?' * len(ids))}) GROUP BY cluster_id", ids):
                offi[x["cluster_id"]] = x["o"] or 0
        for r in trows:
            h0 = hist.get(r["cluster_id"])
            dev[r["cluster_id"]] = developments(S, r["cluster_id"], h0["sent_at"] if h0 else start)
    finally:
        if own: S.close()
    brk = _breaking_ids()
    follow_u, updates = [], []
    for r in trows:
        cid = r["cluster_id"]; followed = cid in follows; h0 = hist.get(cid)
        if not followed:
            if not h0 or r["watchlist"] or int(r["rank"] or 0) < int(c["notable_min_rank"]): continue
            if not allcats and (r["category"] or "other") not in ints: continue
        new, nf = dev.get(cid, ([], []))
        u = _update_of(r, h0, new, nf, followed, h0["sent_at"] if h0 else start, c)
        if not u: continue
        it = item_of(r, "follow" if followed else "update", offi.get(cid, 0)); it["update"] = u; it["followed"] = followed
        (follow_u if followed else updates).append(it)
    keyf = lambda x: (-(x["rank"]), -(x["update"]["n_new"] if x["update"] else 0))
    follow_u = sorted(follow_u, key=keyf)[:int(c.get("max_update_items") or 5)]
    updates = sorted(updates, key=keyf)[:int(c.get("max_update_items") or 5)]
    picked_titles = [x["title_norm"] for x in follow_u + updates]; used = {x["cluster_id"] for x in follow_u + updates}
    def take(r):
        if r["cluster_id"] in hist or r["cluster_id"] in used: return False
        if not allcats and (r["category"] or "other") not in ints and r["cluster_id"] not in follows: return False
        tn = norm_title(r["title"])
        if any(similar(tn, x) for x in sent_titles + picked_titles): return False
        picked_titles.append(tn); used.add(r["cluster_id"]); return True
    main, notable, watch = [], [], []
    for r in erows:
        if len(main) < int(c["max_main_items"]) and take(r): main.append(item_of(r, "main", offi.get(r["cluster_id"], 0), editorial=True))
    for r in rows:
        if int(r["rank"] or 0) >= rmin and int(r["eff_families"] or 0) >= smin and len(main) < int(c["max_main_items"]) and take(r):
            main.append(item_of(r, "main", offi.get(r["cluster_id"], 0)))
    if len(main) < int(c["min_main_items"]):
        room = min(int(c["max_notable_items"]), int(c["min_main_items"]) - len(main))
        for r in rows:
            if len(notable) >= room: break
            rk, ef = int(r["rank"] or 0), int(r["eff_families"] or 0)
            if r["cluster_id"] in used: continue
            ok = (ef >= 2) or (rk >= rmin and offi.get(r["cluster_id"]))   # confirmed rank 5-6, or a rank-7+ item from one official source
            if ok and take(r): notable.append(item_of(r, "notable", offi.get(r["cluster_id"], 0)))
    for r in wrows:
        if len(watch) >= int(c["max_watchlist"]): break
        if take(r): watch.append(item_of(r, "watchlist"))
    politics = [x for x in main + notable if x["category"] == "political"]
    main = [x for x in main if x["category"] != "political"]; notable = [x for x in notable if x["category"] != "political"]
    for r in rows:   # more confirmed political items (rank 5+, 2+ independent sources) for the Politics & Government section
        if len(politics) >= int(c.get("max_politics_items") or 4): break
        if (r["category"] or "") == "political" and int(r["eff_families"] or 0) >= 2 and take(r): politics.append(item_of(r, "politics", offi.get(r["cluster_id"], 0)))
    for it in politics: it["section"] = "politics"
    for it in follow_u + main + updates + notable + politics:
        it["breaking"] = it["cluster_id"] in brk; it["followed"] = it["cluster_id"] in follows
    quiet = not main and not notable and not updates and not follow_u and not politics
    issue = {"main": main, "notable": notable, "watchlist": watch, "updates": updates, "follow": follow_u, "politics": politics, "quiet": quiet, "start": start,
             "end": at, "slot": slot, "empty": not (main or notable or watch or updates or follow_u or politics), "rule": {"rank": rmin, "sources": smin}}
    issue["videos"] = videos_for(issue, c)
    issue["empty"] = issue["empty"] and not issue["videos"]
    if quiet and not any(int(i.get("rank") or 0) >= 4 for i in watch):   # quiet period: only send if something rank 4+ exists
        issue["empty"] = True
    issue["bluf"] = bluf(issue)
    return issue

def _short(t, n=90): return _cut(re.sub(r"^[^\w(\"'“]+", "", t or "").strip() or (t or ""), n)
def bluf(issue):
    """Bottom line up front: one or two sentences, built from the selected items only."""
    m, u, f, n = issue["main"], issue.get("updates", []), issue.get("follow", []), issue["notable"]
    rr = issue["rule"]; hrs = max(1, round((issue["end"] - issue["start"]).total_seconds() / 3600))
    parts = []
    if m:
        top = m[0]
        parts.append(f"{len(m)} confirmed rank-{rr['rank']}+ threat{'s' if len(m) != 1 else ''} in the last {hrs} h. "
                     f"Top: {_short(top['title'])} (rank {top['rank']}, {top['category']}).")
        if len(m) > 1: parts.append("Also: " + "; ".join(f"{_short(x['title'], 60)} (R{x['rank']})" for x in m[1:3]) + ".")
    else:
        parts.append(f"No new rank-{rr['rank']}+ confirmed threats in the last {hrs} h.")
        if n: parts.append(f"Most significant: {_short(n[0]['title'])} (rank {n[0]['rank']}).")
    dv = f + u
    if dv:
        ups = [x for x in dv if x["update"]["up"]]
        parts.append(f"{len(dv)} developing stor{'ies' if len(dv) != 1 else 'y'} updated" + (f", {len(ups)} raised in rank" if ups else "") + ".")
    if issue.get("videos"): parts.append(f"{len(issue['videos'])} new video report{'s' if len(issue['videos']) != 1 else ''} below.")
    return " ".join(parts)

# ------------------------------------------------------------------ rendering (HTML email: tables + inline CSS; plain-text alternative)
# Brand: Signal (t324/t326u). Spec: /workspace/brand_concepts/A/README.md. Dark is the default (inline styles); a light variant is applied by the
# @media (prefers-color-scheme: light) block in <head> where the client supports it (Apple Mail, iOS Mail, Outlook for Mac). Clients that strip
# <style> (Gmail, Outlook.com) get the dark design. The logo is a hosted PNG (email clients do not load web fonts reliably); every text style has a
# web-safe fallback stack. All text is left-aligned. Masthead = BN tile + small domain + tagline (t333u).
PAL = {"bg": "#0B0D10", "surf": "#14181D", "surf2": "#1B2027", "line": "#252B33", "tx": "#E6E9EE", "mu": "#8B95A3", "ac": "#FF4D4F", "ink": "#0B0D10",
       "sev": ("#2BB673", "#F5A524", "#FF4D4F"), "empty": "#252B33", "body": "#C9CED6"}
PAL_LIGHT = {"bg": "#F6F7F9", "surf": "#FFFFFF", "surf2": "#EEF0F3", "line": "#DDE1E6", "tx": "#0B0D10", "mu": "#5B6573", "ac": "#D92D30", "ink": "#FFFFFF",
             "sev": ("#16884B", "#C77700", "#D92D30"), "empty": "#DDE1E6", "body": "#2A313B"}
FH = "Montserrat,'Helvetica Neue',Helvetica,Arial,sans-serif"                   # headlines, kickers, numerals
FB = "Inter,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Helvetica,Arial,sans-serif"   # body
LOGO_ALT = "BN"
def logo_url(theme="dark", c=None):
    """Hosted master logo (t333u): the BN square tile with the green/amber/red meter underneath, solid background. Served by social.py /social/thumb/."""
    return f'{(c or cfg())["base_url"].rstrip("/")}/social/thumb/brand_tile_{theme}_168.png'
def _logo_html(c, size=48):
    """Masthead: BN tile + the domain in a small, quiet size beside it, with the tagline under the domain. Left-aligned."""
    dk = (f'<img class="bn-dk" src="{E(logo_url("dark", c))}" width="{size}" height="{size}" alt="{LOGO_ALT}" '
          f'style="display:block;width:{size}px;height:{size}px;border:0;outline:none;text-decoration:none;color:{PAL["tx"]};font:900 16px {FH}">')
    lt = (f'<!--[if !mso]><!--><img class="bn-lt" src="{E(logo_url("light", c))}" width="{size}" height="{size}" alt="{LOGO_ALT}" '
          f'style="display:none;width:{size}px;height:{size}px;max-height:0;overflow:hidden;mso-hide:all;border:0;outline:none"><!--<![endif]-->')
    fs = 13 if size >= 44 else 11
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td width="{size}" valign="middle" style="width:{size}px;padding:0">{dk}{lt}</td>'
            f'<td valign="middle" style="padding:0 0 0 12px;text-align:left">'
            f'<div class="bnt" style="font:700 {fs}px/1.3 {FH};letter-spacing:1.4px;color:{PAL["tx"]}">BLACKOUT.<span class="bnr" style="color:{PAL["ac"]}">NETWORK</span></div>'
            f'<div class="bnm" style="font:400 {fs - 1}px/1.4 {FB};color:{PAL["mu"]};margin-top:1px">{E(TAGLINE)}</div></td></tr></table>')
_LIGHT_CSS = ("@media (prefers-color-scheme: light){"
    f".bnb{{background:{PAL_LIGHT['bg']}!important}}.bns{{background:{PAL_LIGHT['surf']}!important}}.bns2{{background:{PAL_LIGHT['surf2']}!important}}"
    f".bnl{{border-color:{PAL_LIGHT['line']}!important}}.bnt{{color:{PAL_LIGHT['tx']}!important}}.bnm{{color:{PAL_LIGHT['mu']}!important}}"
    f".bnx{{color:{PAL_LIGHT['body']}!important}}.bnr{{color:{PAL_LIGHT['ac']}!important}}.bnrl{{border-left-color:{PAL_LIGHT['ac']}!important}}"
    f".bnp{{background:{PAL_LIGHT['tx']}!important;color:{PAL_LIGHT['ink']}!important;border-color:{PAL_LIGHT['tx']}!important}}"
    f".bng{{background:{PAL_LIGHT['surf']}!important;color:{PAL_LIGHT['tx']}!important;border-color:{PAL_LIGHT['line']}!important}}"
    f".sg{{background:{PAL_LIGHT['sev'][0]}!important}}.sa{{background:{PAL_LIGHT['sev'][1]}!important}}.sr{{background:{PAL_LIGHT['sev'][2]}!important}}"
    f".se{{background:{PAL_LIGHT['empty']}!important}}.tg{{color:{PAL_LIGHT['sev'][0]}!important}}.ta{{color:{PAL_LIGHT['sev'][1]}!important}}"
    f".tr{{color:{PAL_LIGHT['sev'][2]}!important}}.bga{{border-color:{PAL_LIGHT['sev'][1]}!important}}"
    ".bn-dk{display:none!important;max-height:0!important;overflow:hidden!important}.bn-lt{display:block!important;max-height:none!important}}"
    "a[x-apple-data-detectors]{color:inherit!important;text-decoration:none!important}")
def _head(title):
    return ('<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="x-apple-disable-message-reformatting"><meta name="color-scheme" content="dark light"><meta name="supported-color-schemes" content="dark light">'
            f'<title>{E(title)}</title><style>:root{{color-scheme:dark light;supported-color-schemes:dark light}}{_LIGHT_CSS}</style></head>')

def sev_band(r):
    r = max(0, min(10, int(r or 0)))
    return 0 if r <= 3 else (1 if r <= 6 else 2)
RANK_COLORS = [PAL["sev"][sev_band(i)] for i in range(11)]          # kept for callers: severity colour of a rank (green 0–3 / amber 4–6 / red 7–10)
_SEVCLS = ("sg", "sa", "sr"); _SEVTXT = ("tg", "ta", "tr")
def rank_color(r): return RANK_COLORS[max(0, min(10, int(r or 0)))]
def slot_label(slot): return {"morning": "Morning", "evening": "Evening", "breaking": "Breaking"}.get(slot, "Special")
def _cut(s, n): return s if len(s) <= n else s[:n - 3].rsplit(" ", 1)[0] + "…"

def meter_html(rank, big=False, rank_from=None):
    """Signal Rank Meter: 10 segments filled to the rank (segment colour by its own band), always followed by the numeral (e.g. 7/10)."""
    rk = max(0, min(10, int(rank or 0))); w, hgt, fs = (9, 16, 24) if big else (7, 12, 17)
    cells = "".join(
        f'<td class="{_SEVCLS[sev_band(i)] if i <= rk else "se"}" width="{w}" height="{hgt}" style="width:{w}px;height:{hgt}px;padding:0;font-size:0;line-height:0;'
        f'border-radius:2px;background:{PAL["sev"][sev_band(i)] if i <= rk else PAL["empty"]}">&nbsp;</td><td width="2" style="width:2px;padding:0;font-size:0;line-height:0">&nbsp;</td>'
        for i in range(1, 11))
    chg = ""
    if rank_from is not None and rank_from != rk:
        chg = f'<span class="bnm" style="font:700 12px {FH};color:{PAL["mu"]};letter-spacing:.3px">&nbsp;{"▲" if rk > rank_from else "▼"} from {int(rank_from)}</span>'
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:separate"><tr>' + cells +
            f'<td style="padding:0 0 0 8px;white-space:nowrap;vertical-align:middle"><span class="bnt" style="font:800 {fs}px/1 {FH};color:{PAL["tx"]}">{rk}</span>'
            f'<span class="bnm" style="font:700 {round(fs * .62)}px/1 {FH};color:{PAL["mu"]}">/10</span>{chg}</td></tr></table>')

def subject_for(issue):
    d = issue["end"].astimezone(ET).strftime("%b %-d"); lab = slot_label(issue["slot"])
    pre = f"{BRAND} {lab} Brief, {d}: "
    if issue["main"]:
        top = issue["main"][0]; more = len(issue["main"]) - 1 + len(issue.get("updates", [])) + len(issue.get("follow", []))
        return pre + f"R{top['rank']} {_cut(_short(top['title'], 200), 70)}" + (f" (+{more} more)" if more else "")
    dv = issue.get("follow", []) + issue.get("updates", [])
    if dv: return pre + f"UPDATE R{dv[0]['rank']} {_cut(_short(dv[0]['title'], 200), 64)}" + (f" (+{len(dv) - 1} more)" if len(dv) > 1 else "")
    if issue["notable"]: return pre + f"no rank-{issue['rule']['rank']}+ confirmed threats; {len(issue['notable'])} notable"
    return pre + "quiet period"

def follow_links(row, cid, c=None):
    """One-click, no-login Follow / Unfollow links for one story (signed, purpose-bound, bound to the address). Previews without a
    subscriber point at the story page's follow section instead."""
    c = c or cfg(); base = c["base_url"].rstrip("/")
    if not row or not _row_get(row, "id"): return {"follow": f"{base}/wire/{cid}#follow", "unfollow": None}
    ttl = int(c["link_ttl_days"]) * 86400; x = h(row["email"], 12)
    return {"follow": f"{base}/newsletter/follow?token={make_token('follow', int(row['id']), ttl, x=x, c=cid)}",
            "unfollow": f"{base}/newsletter/unfollow?token={make_token('unfollow', int(row['id']), ttl, x=x, c=cid)}"}

# Status chips (BREAKING / UPDATE / UNCONFIRMED) and the kicker line under the meter.
def _chip(txt, kind):
    if kind == "red": return f'<span class="tr" style="font:800 11px/1.4 {FH};letter-spacing:1px;color:{PAL["sev"][2]}">{E(txt)}</span>'
    return f'<span class="ta" style="font:800 11px/1.4 {FH};letter-spacing:1px;color:{PAL["sev"][1]}">{E(txt)}</span>'
def _badge(txt, bg, fg="#ffffff", bd=None):   # legacy helper kept for compatibility (not used by the Signal layout)
    return f'<span style="display:inline-block;border-radius:4px;font:800 11px/1.4 {FH};letter-spacing:.5px;padding:2px 7px;margin:0 4px 4px 0;background:{bg};color:{fg};border:1px solid {bd or bg}">{E(txt)}</span>'
def _kicker(it):
    sep = f'<span class="bnm" style="color:{PAL["mu"]}"> · </span>'
    parts = [f'<span class="{_SEVTXT[sev_band(it["rank"])]}" style="color:{rank_color(it["rank"])}">{E((it.get("tier") or "").upper())}</span>'] if it.get("tier") else []
    parts.append(f'<span class="bnm" style="color:{PAL["mu"]}">{E((it.get("category") or "other").upper())}</span>')
    if it.get("breaking"): parts.append(_chip("BREAKING", "red"))
    if it.get("update"): parts.append(_chip("UPDATE", "amber"))
    if it.get("editorial") or it.get("section") == "watchlist": parts.append(_chip("UNCONFIRMED", "amber"))
    return f'<div style="font:800 11px/1.5 {FH};letter-spacing:1px;margin:8px 0 4px 0">{sep.join(parts)}</div>'
def _rank_badge(it):
    u = it.get("update") or {}
    return meter_html(it["rank"], rank_from=u.get("rank_from"))

_L = f"color:{PAL['tx']};text-decoration:underline"
_BTN = (f"display:inline-block;background:{PAL['tx']};color:{PAL['ink']};font:700 14px/1.3 {FH};text-decoration:none;"
        f"border-radius:6px;padding:10px 16px;margin:10px 8px 0 0;border:1px solid {PAL['tx']}")
_BTN2 = (f"display:inline-block;background:{PAL['bg']};color:{PAL['tx']};font:700 14px/1.3 {FH};text-decoration:none;"
         f"border-radius:6px;padding:10px 16px;margin:10px 8px 0 0;border:1px solid {PAL['line']}")
def _btn(label, url, primary=True):
    return f'<a href="{E(url)}" class="{"bnp" if primary else "bng"}" style="{_BTN if primary else _BTN2}">{label}</a>'

def _where(it):
    w = it["where"] or "Location not reported"
    if it["lat"] is not None and it["lon"] is not None and it["where"]:
        try: w += f" (approx. {float(it['lat']):.2f}, {float(it['lon']):.2f})"
        except (TypeError, ValueError): pass
    return w

def _follow_html(it, links, c):
    fl = follow_links(links.get("_row"), it["cluster_id"], c)
    if it.get("followed") and fl["unfollow"]:
        return (f'<span class="tg" style="display:inline-block;margin:10px 8px 0 0;font:700 13px {FH};color:{PAL["sev"][0]}">✓ Following</span> '
                f'<a href="{E(fl["unfollow"])}" class="bnm" style="font:400 13px {FB};color:{PAL["mu"]}">Unfollow</a>')
    return _btn("☆ Follow this story", fl["follow"], primary=False)

_P = f'class="bnx" style="margin:0 0 8px 0;font:400 15px/1.55 {FB};color:{PAL["body"]}"'
def _lbl(t): return f'<b class="bnt" style="font:800 11px {FH};letter-spacing:1px;color:{PAL["tx"]}">{t}</b>'
_ROWTD = f'class="bnl" style="padding:20px;border-top:1px solid {PAL["line"]}"'

_NLF = {"t": 0, "d": {}}
def _nl_figures():
    if time.time() - _NLF["t"] > 600:
        try: _NLF["d"] = json.load(open(os.path.join(BASE, "static", "img", "nl_figures.json")))
        except Exception: _NLF["d"] = {}
        _NLF["t"] = time.time()
    return _NLF["d"]
def _visuals_html(it, url, c):
    """t373: per-item visuals (absolute blackout.network URLs, alt text): locator map, headshots of named people, video thumbnail."""
    base = c["base_url"].rstrip("/"); cid = it["cluster_id"]; out = []
    if os.path.exists(os.path.join(BASE, "static", "img", f"nl_{cid}.jpg")):
        loc = it.get("where") or "the event location"
        out.append(f'<a href="{E(url)}"><img src="{base}/img/nl_{E(cid)}.jpg" width="600" alt="Map showing {E(loc)}" '
                   f'style="display:block;width:100%;max-width:600px;height:auto;border:0;border-radius:6px;margin:0 0 10px 0"></a>')
    text = f"{it.get('title') or ''} {it.get('brief') or ''}"
    faces = [(k, v) for k, v in _nl_figures().items() if v["name"].split()[-1] in text][:4]
    if faces:
        out.append('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 10px 0"><tr>' + "".join(
            f'<td style="padding:0 10px 0 0;vertical-align:top;text-align:center;font:400 11px/1.3 {FB};color:{PAL["mu"]}">'
            f'<a href="{base}/#figures"><img src="{base}/img/nlf_{E(k)}.jpg" width="56" height="56" alt="{E(v["name"])}" style="display:block;width:56px;height:56px;border-radius:28px;border:0;margin:0 auto 4px auto"></a>{E(v["name"].split()[-1])}</td>'
            for k, v in faces) + '</tr></table>')
    vid = next((s_ for s_ in load_stories() if cid in (s_.get("cluster_ids") or []) and s_.get("youtube_id")), None)
    if vid:
        yt = f'https://www.youtube.com/shorts/{vid["youtube_id"]}'
        out.append(f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 10px 0"><tr><td style="padding:0 10px 0 0">'
                   f'<a href="{E(yt)}"><img src="https://i.ytimg.com/vi/{E(vid["youtube_id"])}/mqdefault.jpg" width="160" alt="Watch the video: {E(it.get("title") or "")}" style="display:block;width:160px;height:auto;border:0;border-radius:6px"></a></td>'
                   f'<td style="font:700 14px/1.4 {FH}"><a href="{E(yt)}" class="bnt" style="{_L}">▶ Watch the video</a></td></tr></table>')
    return "".join(out)

def _item_html(it, links, c):
    url = wire_url(it["cluster_id"], c=c); u = it.get("update")
    conf_cls, conf_col = ("ta", PAL["sev"][1]) if it["unconfirmed"] else ("tg", PAL["sev"][0])
    H = [f'<tr><td {_ROWTD}>{_rank_badge(it)}{_kicker(it)}'
         f'<div style="margin:2px 0 10px 0"><a href="{E(url)}" class="bnt" style="font:800 19px/1.3 {FH};color:{PAL["tx"]};text-decoration:none">{E(_cut(it["title"], 200))}</a></div>']
    H.append(_visuals_html(it, url, c))
    if u:
        bits = []
        if u["rank_from"] is not None and u["rank_from"] != u["rank_to"]:
            bits.append(f"Rank {'raised' if u['up'] else 'lowered'} {u['rank_from']} → {u['rank_to']}.")
        if u["n_new"]:
            bits.append(f"{u['n_new']} new report{'s' if u['n_new'] != 1 else ''}" + (f", {len(u['new_fams'])} from new independent source{'s' if len(u['new_fams']) != 1 else ''} ({', '.join(u['new_fams'][:4])})" if u["new_fams"] else "") + ".")
        H.append(f'<p {_P}><b class="ta" style="font:800 11px {FH};letter-spacing:1px;color:{PAL["sev"][1]}">WHAT\'S NEW</b> '
                 f'<span class="bnm" style="color:{PAL["mu"]}">since {E(fmt_et(u["since"]))}:</span> {E(" ".join(bits) or "Updated.")}</p>')
        if u["reports"]:
            H.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 8px 0">' + "".join(
                f'<tr><td class="bnx bga" style="padding:3px 0 3px 10px;border-left:2px solid {PAL["sev"][1]};font:400 14px/1.45 {FB};color:{PAL["body"]}">'
                f'<span class="bnm" style="color:{PAL["mu"]}">{E(fmt_et(x["when"], with_date=False))} · {E(x["source"])}{" · official" if x["official"] else ""}:</span> {E(x["title"])}</td></tr>'
                for x in u["reports"]) + '</table>')
        H.append(f'<p {_P}>{_lbl("WHY IT MATTERS")} {E(it["why"])}</p>'
                 f'<p {_P}>{_lbl("CONFIDENCE")} <span class="{conf_cls}" style="color:{conf_col}">{E(it["confidence"])}</span>.</p>'
                 f'<div>{_btn("Story timeline →", u["timeline"])}{_follow_html(it, links, c)}</div></td></tr>')
        return "".join(H)
    H.append(f'<p {_P}>{_lbl("BRIEF")} {E(it["what"])}</p>'
             f'<p {_P}>{_lbl("WHERE")} {E(_where(it))} · {_lbl("WHEN")} {E(when_str(it["when"]))}</p>'
             f'<p {_P}>{_lbl("WHY IT MATTERS")} {E(it["why"])}</p>'
             f'<p {_P}>{_lbl("CONFIDENCE")} <span class="{conf_cls}" style="color:{conf_col}">{E(it["confidence"])}</span>. '
             f'<span class="bnm" style="color:{PAL["mu"]};font-size:13px">{it["n_items"] or 1} report{"s" if (it["n_items"] or 1) != 1 else ""}, score {it["score"]}/100, first seen {E(fmt_et(it["first_seen"]))}.</span></p>'
             f'<div>{_btn("Full story &amp; sources →", url)}{_follow_html(it, links, c)}</div></td></tr>')
    return "".join(H)

# Issue footer: distinct buttons. Inline styles only (email clients strip <style>).
BTN_PRIMARY = _BTN
BTN_SECONDARY = _BTN2
def footer_buttons_html(links):
    cat = links.get("categories") or links.get("manage"); srcs = links.get("sources") or links.get("site")
    return (f'<tr><td class="bnl" style="padding:16px 20px 4px 20px;border-top:1px solid {PAL["line"]}">'
            f'{_btn("Manage my subscription categories", cat)}{_btn("Find new sources", srcs, primary=False)}</td></tr>'
            f'<tr><td align="left" style="padding:14px 20px 22px 20px;text-align:left;font:400 12px/1.5 {FB}">'
            f'<a href="{E(links["unsubscribe"])}" class="bnm" style="color:{PAL["mu"]};text-decoration:underline">Unsubscribe</a>'
            f'<span class="bnm" style="color:{PAL["mu"]}"> (one click, no login)</span>'
            + (f' · <a href="{E(links["breaking_off"])}" class="bnm" style="color:{PAL["mu"]};text-decoration:underline">Stop breaking alerts (keep briefs)</a>' if links.get("breaking_off") else "")
            + '</td></tr>')
def footer_buttons_text(links):
    return [f"Manage my subscription categories: {links.get('categories') or links.get('manage')}",
            f"Find new sources: {links.get('sources') or links.get('site')}", "",
            f"Unsubscribe (one click): {links['unsubscribe']}"] + ([f"Stop breaking alerts, keep briefs: {links['breaking_off']}"] if links.get("breaking_off") else [])

def _addr(c):
    a = (c.get("mailing_address") or "").strip()
    return a, (E(a) if a else (f'<span class="ta" style="color:{PAL["sev"][1]}">Postal address: [PENDING] (CAN-SPAM requires a physical postal address in every issue; '
                                'live issue sending stays locked until it is set)</span>'))

def _sevbar():
    """Thin green / amber / red strip across the top of every email (the meter's three bands)."""
    return ('<tr><td style="padding:0;font-size:0;line-height:0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td class="sg" width="30%" height="4" style="height:4px;background:{PAL["sev"][0]};font-size:0;line-height:0">&nbsp;</td>'
            f'<td class="sa" width="30%" height="4" style="height:4px;background:{PAL["sev"][1]};font-size:0;line-height:0">&nbsp;</td>'
            f'<td class="sr" width="40%" height="4" style="height:4px;background:{PAL["sev"][2]};font-size:0;line-height:0">&nbsp;</td></tr></table></td></tr>')

def _shell(title, pre, head_html, body_rows, links, c, why_line):
    """Common email frame: single column, 100% wide up to 640 px (phones get full width), table layout + inline CSS, left-aligned text."""
    addr, addr_html = _addr(c); mu = PAL["mu"]
    return (_head(title) + f'<body class="bnb" style="margin:0;padding:0;background:{PAL["bg"]};-webkit-text-size-adjust:100%">'
            f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAL["bg"]}">{E(pre)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>'
            f'<table role="presentation" class="bnb" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAL["bg"]}"><tr><td align="center" style="padding:0">'
            f'<table role="presentation" class="bnb" width="640" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;background:{PAL["bg"]};'
            f'font-family:{FB};color:{PAL["tx"]};text-align:left">'
            + _sevbar() + head_html + "".join(body_rows) +
            f'<tr><td class="bnl" style="padding:22px 20px 8px 20px;border-top:1px solid {PAL["line"]};text-align:left">{_logo_html(c, 32)}</td></tr>'
            f'<tr><td class="bnm" style="padding:8px 20px 4px 20px;font:400 12px/1.6 {FB};color:{mu};text-align:left">'
            f'<p style="margin:0 0 8px 0">{E(DISCLAIMER)} Every story links to its page on {BRAND}, where you can open each original source. '
            f'<a href="{E(links["scoring"])}" class="bnt" style="{_L}">How we score</a> · <a href="{E(links["site"])}" class="bnt" style="{_L}">Open the live dashboard</a></p>'
            f'<p style="margin:0 0 8px 0">{E(why_line)}</p>'
            f'<p style="margin:0 0 8px 0">Visit <a href="https://blackout.network" class="bnt" style="{_L}">blackout.network</a> (no .com) to see the whole picture. '
            f'Follow: <a href="https://www.youtube.com/@blkoutntw" class="bnt" style="{_L}">YouTube @blkoutntw</a> · <a href="https://x.com/BlkoutNtw" class="bnt" style="{_L}">X @BlkoutNtw</a></p>'
            f'<p style="margin:0">{BRAND} · {addr_html}</p></td></tr>'
            + footer_buttons_html(links) + '</table></td></tr></table></body></html>')

def _head_html(kicker, kcol, line2, rng):
    kcls = "bnr" if kcol.lower() in ("#ff4d4f", PAL["ac"].lower()) else "bnt"
    return (f'<tr><td style="padding:22px 20px 6px 20px;text-align:left">{_logo_html(None, 48)}</td></tr>'
            f'<tr><td class="bnl" style="padding:14px 20px 16px 20px;border-bottom:1px solid {PAL["line"]};text-align:left">'
            f'<div class="{kcls}" style="font:800 12px/1.4 {FH};letter-spacing:1.6px;color:{kcol}">{E(kicker)}</div>'
            f'<div class="bnt" style="font:800 22px/1.25 {FH};color:{PAL["tx"]};margin-top:4px">{E(line2)}</div>'
            f'<div class="bnm" style="font:400 13px/1.5 {FB};color:{PAL["mu"]};margin-top:4px">{E(rng)}</div></td></tr>')

_SECCOL = {"#e6e9ee": ("bnt", PAL["tx"]), "green": ("tg", PAL["sev"][0]), "amber": ("ta", PAL["sev"][1]), "red": ("tr", PAL["sev"][2])}
def _sec_html(title, sub_, col="#e6e9ee"):
    cls, colv = _SECCOL.get(col, ("bnt", PAL["tx"]))
    return (f'<tr><td style="padding:26px 20px 6px 20px;text-align:left"><div class="{cls}" style="font:800 13px/1.3 {FH};letter-spacing:1.6px;text-transform:uppercase;color:{colv}">{E(title)}</div>'
            f'<div class="bnm" style="font:400 13px/1.5 {FB};color:{PAL["mu"]};margin-top:3px">{E(sub_)}</div></td></tr>')

def _bluf_html(txt, label="BLUF"):
    return (f'<tr><td style="padding:18px 20px 4px 20px"><div class="bns2 bnrl bnt" style="border-left:3px solid {PAL["ac"]};background:{PAL["surf2"]};border-radius:6px;'
            f'padding:12px 14px;font:400 15px/1.55 {FB};color:{PAL["tx"]}"><b class="bnr" style="font:800 12px {FH};letter-spacing:1.4px;color:{PAL["ac"]}">{label}</b> {E(txt)}</div></td></tr>')

def window_str(a, b):
    hrs = (b - a).total_seconds() / 3600
    return f"Data window: {fmt_et(a)} – {fmt_et(b, a.astimezone(ET).date() != b.astimezone(ET).date())} ({hrs:.0f} h)"

def _text_item(it, n):
    u = it.get("update"); T = []
    tags = [f"RANK {it['rank']}/10 {it['tier'].upper()}", it["category"]] + (["BREAKING"] if it.get("breaking") else []) + (["UPDATE"] if u else []) + \
           (["UNCONFIRMED"] if it["editorial"] or it["section"] == "watchlist" else [])
    T.append(f"{n}. [{' · '.join(tags)}] {_cut(it['title'], 200)}")
    if u:
        bits = []
        if u["rank_from"] is not None and u["rank_from"] != u["rank_to"]: bits.append(f"Rank {u['rank_from']} -> {u['rank_to']}.")
        if u["n_new"]: bits.append(f"{u['n_new']} new report(s)" + (f", new independent sources: {', '.join(u['new_fams'][:4])}" if u["new_fams"] else "") + ".")
        T.append(f"   WHAT'S NEW since {fmt_et(u['since'])}: {' '.join(bits) or 'Updated.'}")
        for x in u["reports"]: T.append(f"   - {fmt_et(x['when'], with_date=False)} · {x['source']}: {x['title']}")
    else:
        T.append(f"   BRIEF: {it['what']}")
        T.append(f"   WHERE: {_where(it)} · WHEN: {when_str(it['when'])}")
    T.append(f"   WHY IT MATTERS: {it['why']}")
    T.append(f"   CONFIDENCE: {it['confidence']}.")
    return T

def render(issue, links, c=None):
    """-> (subject, html, text). links: dict with unsubscribe, manage, scoring, site (+ _row: the subscriber row, for Follow links)."""
    c = c or cfg(); subj = subject_for(issue); rr = issue["rule"]
    rng = window_str(issue["start"], issue["end"]); addr, _ = _addr(c)
    lab = slot_label(issue["slot"]); day = issue["end"].astimezone(ET).strftime("%A, %B %-d, %Y")
    if issue.get("label"): day = issue["label"]
    B = []; a = B.append
    a(_bluf_html(issue["bluf"]))
    if issue.get("follow"):
        a(_sec_html("Stories you follow", "Updates on stories you chose to follow: only what is new since your last brief.", "green"))
        for it in issue["follow"]: a(_item_html(it, links, c))
    if issue["main"]:
        a(_sec_html("Top threats", f"New since your last brief. Rank {rr['rank']}+ and confirmed by {rr['sources']}+ independent sources, highest first."))
        for it in issue["main"]: a(_item_html(it, links, c))
    else:
        a(f'<tr><td style="padding:16px 20px"><div class="bns2 bnx" style="background:{PAL["surf2"]};border-radius:6px;padding:12px 14px;font:400 15px/1.55 {FB};color:{PAL["body"]}">'
          f'<b class="bnt" style="color:{PAL["tx"]}">Quiet period:</b> No new rank-{rr["rank"]}+ confirmed threats in this window.</div></td></tr>')
    if issue.get("politics"):
        a(_sec_html("Politics & Government", "Government actions, emergency declarations, sanctions and political crises, confirmed by 2+ independent sources."))
        for it in issue["politics"]: a(_item_html(it, links, c))
    vids = issue.get("videos") or []
    if vids:
        a(_sec_html("Watch: new on BLACKOUT.NETWORK", "Our latest video reports. Each one has a full written report with every source on its BLACKOUT.NETWORK page."))
        for s_ in vids: a(_video_html(s_, c, issue["slot"]))
    if issue.get("updates"):
        a(_sec_html("Developing stories", "Stories from earlier briefs with new independent sources or a higher rank. Only what changed is shown.", "amber"))
        for it in issue["updates"]: a(_item_html(it, links, c))
    if issue["notable"]:
        a(_sec_html("Also notable", f"Below the top-threats bar: confirmed rank 5–6 items, or a rank-{rr['rank']}+ item from a single official source."))
        for it in issue["notable"]: a(_item_html(it, links, c))
    if issue["watchlist"]:
        a(_sec_html("Watchlist: unconfirmed", "Low-confidence, single-source reports. Not verified. Shown so you can watch for confirmation.", "amber"))
        for it in issue["watchlist"]:
            rk = int(it.get("rank") or 0)
            a(f'<tr><td class="bnl" style="padding:12px 20px;border-top:1px solid {PAL["line"]};font:400 14px/1.5 {FB}">'
              f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
              f'<td width="34" valign="top" class="{_SEVTXT[sev_band(rk)]}" style="width:34px;font:800 20px/1.1 {FH};color:{rank_color(rk)}">{rk}</td>'
              f'<td valign="top"><a href="{E(wire_url(it["cluster_id"], c=c))}" class="bnt" style="font:700 15px/1.35 {FH};color:{PAL["tx"]};text-decoration:none">{E(_cut(it["title"], 180))}</a>'
              f'<div style="font:800 11px/1.6 {FH};letter-spacing:1px;margin-top:3px">{_chip("UNCONFIRMED", "amber")}'
              f'<span class="bnm" style="color:{PAL["mu"]}"> · {E((it["category"] or "").upper())} · {E(fmt_et(it["first_seen"]).upper())}</span></div></td></tr></table></td></tr>')
    pre = issue["bluf"]
    why = f"You get this because you confirmed a subscription to the {BRAND} newsletter. Change how often it arrives, or turn off breaking alerts, under Manage."
    html_ = _shell(subj, pre, _head_html(f"{lab.upper()} BRIEF", PAL["ac"], day, rng), B, links, c, why)
    T = [f"{BRAND} — {lab} Brief", TAGLINE, day, rng, "", f"BLUF: {issue['bluf']}", ""]
    def tsec(title, items):
        T.extend([title.upper(), "=" * len(title)])
        for i, it in enumerate(items, 1):
            T.extend(_text_item(it, i))
            T.append(f"   {'Story timeline' if it.get('update') else 'Full story & sources'}: {(it['update'] or {}).get('timeline') or wire_url(it['cluster_id'], c=c)}")
            fl = follow_links(links.get("_row"), it["cluster_id"], c)
            T.append(f"   Unfollow: {fl['unfollow']}" if it.get("followed") and fl["unfollow"] else f"   Follow this story: {fl['follow']}")
            T.append("")
    if issue.get("follow"): tsec("Stories you follow", issue["follow"])
    if issue["main"]: tsec("Top threats", issue["main"])
    else: T += [f"QUIET PERIOD: No new rank-{rr['rank']}+ confirmed threats in this window.", ""]
    if issue.get("politics"): tsec("Politics & Government", issue["politics"])
    if vids:
        T.extend(["WATCH: NEW ON BLACKOUT.NETWORK", "=" * 30])
        for s_ in vids: T.extend(_video_text(s_, c, issue["slot"]))
    if issue.get("updates"): tsec("Developing stories", issue["updates"])
    if issue["notable"]: tsec("Also notable", issue["notable"])
    if issue["watchlist"]:
        T += ["WATCHLIST: UNCONFIRMED (single-source, not verified)", "=" * 30]
        for it in issue["watchlist"]:
            T.append(f"- UNCONFIRMED · {_cut(it['title'], 180)} ({it['category']}, {fmt_et(it['first_seen'])}) {wire_url(it['cluster_id'], c=c)}")
        T.append("")
    T += ["See the whole picture: https://blackout.network (no .com)", "YouTube: https://www.youtube.com/@blkoutntw · X: https://x.com/BlkoutNtw", ""]
    T += ["--", DISCLAIMER, f"How we score: {links['scoring']}", f"Dashboard: {links['site']}", why,
          f"{BRAND} · {TAGLINE}", f"{addr or 'Postal address: [PENDING] (required by CAN-SPAM before live sending)'}", ""]
    T += footer_buttons_text(links)
    return subj, html_, "\n".join(T)


# ------------------------------------------------------------------ breaking / emergency alerts
# Trigger (documented in NEWSLETTER.md, "Breaking alerts"). A main-Wire story (not watchlist) that first appeared, or reached its high
# rank, in the last breaking.fresh_hours (6 h) qualifies when ANY rule holds:
#   B1  rank 9-10 (Critical / Catastrophic: nuclear use, WHO PHEIC or pandemic, G5 storm) with an official source or 2+ independent families
#   B2  rank 8 (Severe) with 3+ independent source families AND (an official source OR a major-event pattern below)
#   B3  rank 7+ with 2+ independent source families AND a war-outbreak / novel-pathogen / nuclear pattern (WAR_PATHOGEN_RX)
# Rate limits: at most one alert email every min_gap_hours (3 h) and max_per_day (3) per rolling 24 h; up to max_items (3) stories per
# email. A story alerts once; it can alert again only if it later escalates into rank 9+. Stories held back by the rate limit are not
# re-sent as a separate alert: they lead the next scheduled brief, tagged BREAKING.
WAR_PATHOGEN_RX = re.compile(
    r"declar\w* (of )?war|war (has )?(breaks?|broke|broken) out|outbreak of war|full[- ]scale (war|invasion|offensive|attack)|invasion of|invades?\b|invaded\b|"
    r"troops (cross|crossed|enter|entered|pour)|ground (offensive|invasion)|nuclear (strike|attack|detonation|war|exchange|test)|"
    r"novel (virus|pathogen|coronavirus|influenza|flu|strain|disease)|new (virus|pathogen|strain|variant) (detected|identified|discovered|emerges?)|"
    r"unknown (disease|illness|pathogen|virus)|mystery (illness|disease|virus)|human[- ]to[- ]human|pandemic|\bPHEIC\b|"
    r"public health emergency of international concern", re.I)
MAJOR_RX = re.compile(WAR_PATHOGEN_RX.pattern + r"|ballistic missiles?|missile (strike|attack)s?|air ?strikes? (on|against|hit)|"
                      r"tsunami warning|martial law|\bcoup\b|assassinat|state of war|mass casualt|\bM ?[89]\.\d|magnitude [89]", re.I)
def breaking_rule(r, official):
    rk, ef = int(r["rank"] or 0), int(r["eff_families"] or 0)
    text = f"{r['title'] or ''} {r['brief'] or ''}"
    if ef < 2: return None                 # t373: never single-source / unconfirmed
    if rk >= 9: return "B1"
    if rk >= 7: return "B2"
    return None
BREAKING_RULES = {"B1": "rank 9-10 confirmed by 2+ independent sources",
                  "B2": "rank 7+ confirmed by 2+ independent sources",
                  "T1": "one of our posts is trending (engagement well above our recent baseline)"}

def load_trending():
    """social_trending.json (written by the box engagement check, pushed via sync): [{id, title, url, platform, metric, value, baseline, at}]."""
    try: return json.load(open(os.path.join(BASE, "social_trending.json"))).get("items") or []
    except Exception: return []

def breaking_candidates(at=None, c=None, S=None):
    """-> [(row, rule, official)] fresh stories meeting the trigger, strongest first."""
    c = c or cfg(); at = at or now(); b = c.get("breaking") or {}
    cut = iso(at - timedelta(hours=float(b.get("fresh_hours", 6)))); s1 = iso(at)
    own = S is None; S = S or src()
    try:
        rows = S.execute("""SELECT * FROM clusters WHERE watchlist=0 AND rank>=7 AND ((first_seen>=? AND first_seen<=?) OR (high_at>=? AND high_at<=?))
                            ORDER BY rank DESC, eff_families DESC, score DESC LIMIT 100""", (cut, s1, cut, s1)).fetchall()
        offi = {}
        if rows:
            ids = [r["cluster_id"] for r in rows]
            for x in S.execute(f"SELECT cluster_id, MAX(official) o FROM alerts WHERE cluster_id IN ({','.join('?' * len(ids))}) GROUP BY cluster_id", ids):
                offi[x["cluster_id"]] = x["o"] or 0
    finally:
        if own: S.close()
    out = []
    for r in rows:
        rule = breaking_rule(r, offi.get(r["cluster_id"], 0))
        if rule: out.append((r, rule, offi.get(r["cluster_id"], 0)))
    return out

def _trend_row(t):
    return (f'<tr><td class="bnl" style="padding:16px 20px;border-top:1px solid {PAL["line"]};font:400 15px/1.55 {FB};color:{PAL["tx"]}">'
            f'<p style="margin:0 0 6px 0;font:800 12px/1.4 {FH};letter-spacing:.08em;color:{PAL["ac"]}">TRENDING ON {BRAND}</p>'
            f'<p style="margin:0 0 10px 0;font:700 18px/1.3 {FH}">{E(t.get("title") or "")}</p>'
            f'<p class="bnm" style="margin:0 0 12px 0;color:{PAL["mu"]};font-size:13px">{E(t.get("platform") or "")}: {E(t.get("value"))} {E(t.get("metric") or "views")}, about {E(t.get("ratio") or "")}× our recent average.</p>'
            f'{_btn("Watch it →", t["url"])}</td></tr>')
def render_trending(t, links, at, c=None):
    c = c or cfg(); addr, _ = _addr(c)
    subj = f"Trending on {BRAND}: {_cut(t.get('title') or '', 90)}"
    pre = f"One of our posts is taking off: {_cut(t.get('title') or '', 120)}"
    why = f"You get breaking alerts because you subscribed to the {BRAND} newsletter. Turn them off with the link below or under Manage."
    html_ = _shell(subj, pre, _head_html("TRENDING", PAL["ac"], fmt_et(at), f"As of {fmt_et(at)}"), [_bluf_html(pre), _trend_row(t)], links, c, why)
    text = "\n".join([subj, "", pre, f"Watch: {t['url']}", "", "See the whole picture: https://blackout.network (no .com)", "--",
                      f"{BRAND} · {addr}", *footer_buttons_text(links)])
    return subj, html_, text

def render_breaking(items, links, at, c=None, trend=None):
    """items: item_of() dicts with 'rule'. -> (subject, html, text)."""
    if not items and trend: return render_trending(trend, links, at, c)
    c = c or cfg(); top = items[0]; addr, _ = _addr(c)
    subj = f"BREAKING · {BRAND}: R{top['rank']} {_cut(_short(top['title'], 200), 80)}" + (f" (+{len(items) - 1} more)" if len(items) > 1 else "")
    pre = f"{top['tier']} ({top['rank']}/10): {_short(top['title'], 140)}. {top['confidence']}."
    B = [_bluf_html(pre)]
    for it in items: B.append(_item_html(it, links, c))
    ids = {it["cluster_id"] for it in items}
    vids = [s_ for s_ in load_stories() if ids & set(s_.get("cluster_ids") or []) and (parse_t(s_.get("publish_at")) or at) <= at][:2]
    for s_ in vids: B.append(_video_html(s_, c, "breaking"))
    rules = "; ".join(sorted({f"{it['rule']}: {BREAKING_RULES[it['rule']]}" for it in items if it.get("rule")}))
    B.append(f'<tr><td class="bnl bnm" style="padding:14px 20px;border-top:1px solid {PAL["line"]};font:400 13px/1.55 {FB};color:{PAL["mu"]}">'
             f'<b class="bnt" style="color:{PAL["tx"]}">Why you got this:</b> it met the {BRAND} breaking-alert bar ({E(rules)}). Breaking alerts are rare: at most one every '
             f'{(c.get("breaking") or {}).get("min_gap_hours", 3)} hours and {(c.get("breaking") or {}).get("max_per_day", 3)} a day. Your regular briefs continue as usual.</td></tr>')
    why = f"You get breaking alerts because you subscribed to the {BRAND} newsletter. Turn them off under Manage, or unsubscribe below."
    html_ = _shell(subj, pre, _head_html("BREAKING ALERT", PAL["ac"], fmt_et(at), f"Data as of {fmt_et(at)} ({fmt_z(at)})"), B, links, c, why)
    T = [f"{BRAND} — BREAKING ALERT", TAGLINE, fmt_et(at), "", f"BLUF: {pre}", ""]
    for i, it in enumerate(items, 1):
        T.extend(_text_item(it, i)); T.append(f"   Full story & sources: {wire_url(it['cluster_id'], c=c)}")
        T.append(f"   Follow this story: {follow_links(links.get('_row'), it['cluster_id'], c)['follow']}"); T.append("")
    T += [f"Why you got this: it met the breaking-alert bar ({rules}).", "--", DISCLAIMER, why,
          f"{BRAND} · {TAGLINE}", f"{addr or 'Postal address: [PENDING] (required by CAN-SPAM before live sending)'}", ""] + footer_buttons_text(links)
    return subj, html_, "\n".join(T)

# ------------------------------------------------------------------ launch / video stories (social_stories.json, built by tools/build_social_stories.py)
def load_stories():
    """Published-or-scheduled video stories. The site story page (/story/<slug>) is the hub; YouTube and X are supplemental."""
    try:
        with open(os.environ.get("NEWSLETTER_STORIES", os.path.join(BASE, "social_stories.json"))) as f: return json.load(f).get("stories", [])
    except Exception: return []
def story_url(slug, c=None, utm=None):
    base = (c or cfg())["base_url"].rstrip("/")
    return f"{base}/story/{slug}" + (f"?utm_source=newsletter&utm_medium=email&utm_campaign={urllib.parse.quote(utm)}" if utm else "")
def videos_for(issue, c=None, include_upcoming=False):
    """Video stories that went public inside this issue's window (or, for previews, the upcoming launch lineup)."""
    out = []
    for s in load_stories():
        t = parse_t(s.get("publish_at"))
        if not t: continue
        if (issue["start"] < t <= issue["end"]) or (include_upcoming and t > issue["end"]): out.append(s)
    return sorted(out, key=lambda s: (s.get("order", 99), s.get("publish_at") or ""))[:int((c or cfg()).get("max_videos") or 4)]
def _video_html(s, c, camp):
    base = c["base_url"].rstrip("/"); site = story_url(s["slug"], c, camp)
    img = f'{base}/social/thumb/{urllib.parse.quote(s["thumb"])}' if s.get("thumb") else None
    alt = s.get("thumb_alt") or f'Thumbnail: {s["title"]}'
    yt = f'https://www.youtube.com/watch?v={s["youtube_id"]}' if s.get("youtube_id") else (s.get("youtube_url") or "https://www.youtube.com/@blkoutntw")
    btns = (_btn(f"Read &amp; watch on {BRAND}", site) + _btn("▶ Watch on YouTube", yt, primary=False)
            + _btn("Watch on X", s.get("x_url") or "https://x.com/BLKOUTNTW", primary=False))
    pic = (f'<a href="{E(site)}" style="text-decoration:none"><img src="{E(img)}" width="600" alt="{E(alt)}" '
           f'style="display:block;width:100%;max-width:600px;height:auto;border:0;border-radius:8px;background:{PAL["surf"]};color:{PAL["body"]};font:400 13px {FB}"></a>') if img else ""
    meter = meter_html(s["rank"]) if isinstance(s.get("rank"), int) else ""
    kind = (s.get("kind") or s.get("category") or "video report").upper()
    return (f'<tr><td {_ROWTD}>{pic}<div style="height:12px;line-height:12px;font-size:0">&nbsp;</div>{meter}'
            f'<div class="bnm" style="font:800 11px/1.5 {FH};letter-spacing:1px;color:{PAL["mu"]};margin:6px 0 4px 0">{E(kind)}{" · " + E(s["duration_label"]) if s.get("duration_label") else ""}</div>'
            f'<div style="margin:0 0 8px 0"><a href="{E(site)}" class="bnt" style="font:800 19px/1.3 {FH};color:{PAL["tx"]};text-decoration:none">{E(s["title"])}</a></div>'
            f'<p {_P}>{E(s.get("dek") or "")}</p>'
            f'<div>{btns}</div></td></tr>')
def _video_text(s, c, camp):
    T = [f"- {s['title']}", f"  {s.get('dek') or ''}", f"  Read & watch on {BRAND}: {story_url(s['slug'], c, camp)}"]
    T.append(f"  Watch on YouTube: " + (f"https://www.youtube.com/watch?v={s['youtube_id']}" if s.get("youtube_id") else (s.get("youtube_url") or "https://www.youtube.com/@blkoutntw")))
    T.append(f"  Watch on X: {s.get('x_url') or 'https://x.com/BLKOUTNTW'}")
    return T + [""]
def render_simple(title, paras, button=None, c=None, extra_links=None):
    """Transactional email (confirm / already-subscribed). paras: plain strings. button: (label, url). extra_links: [(label, url)]."""
    c = c or cfg(); addr = (c.get("mailing_address") or "").strip()
    btn = (f'<p style="margin:18px 0 0 0">{_btn(E(button[0]), button[1])}</p>'
           f'<p class="bnm" style="font:400 12px/1.5 {FB};color:{PAL["mu"]};word-break:break-all;margin:14px 0 0 0">Or paste this link into your browser: {E(button[1])}</p>') if button else ""
    xl = "".join(f'<p style="font:400 13px/1.5 {FB};margin:0 0 6px 0"><a href="{E(u)}" class="bnt" style="{_L}">{E(l)}</a></p>' for l, u in (extra_links or []))
    foot = (f'<tr><td class="bnl" style="padding:22px 20px 8px 20px;border-top:1px solid {PAL["line"]}">{_logo_html(c, 32)}</td></tr>'
            f'<tr><td class="bnm" style="padding:8px 20px 22px 20px;font:400 12px/1.6 {FB};color:{PAL["mu"]};text-align:left">{E(DISCLAIMER)}<br>{BRAND} · '
            + (E(addr) if addr else 'https://BLACKOUT.NETWORK') + "</td></tr>")
    body = "".join(f'<p {_P}>{E(p)}</p>' for p in paras)
    html_ = (_head(title) + f'<body class="bnb" style="margin:0;padding:0;background:{PAL["bg"]};-webkit-text-size-adjust:100%">'
             f'<table role="presentation" class="bnb" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAL["bg"]}"><tr><td align="center" style="padding:0">'
             f'<table role="presentation" class="bnb" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{PAL["bg"]};font-family:{FB};text-align:left">'
             + _sevbar() + f'<tr><td style="padding:22px 20px 6px 20px">{_logo_html(c, 48)}</td></tr>'
             f'<tr><td class="bnl" style="padding:14px 20px 22px 20px;border-top:1px solid {PAL["line"]};text-align:left">'
             f'<h1 class="bnt" style="font:800 22px/1.25 {FH};color:{PAL["tx"]};margin:0 0 12px 0">{E(title)}</h1>'
             + body + btn + xl + '</td></tr>' + foot + '</table></td></tr></table></body></html>')
    text = "\n\n".join([f"{BRAND} — {title}", TAGLINE, *paras] + ([f"{button[0]}: {button[1]}"] if button else [])
                       + [f"{l}: {u}" for l, u in (extra_links or [])] + ["--", DISCLAIMER, f"{BRAND} · {TAGLINE} · {addr or 'https://BLACKOUT.NETWORK'}"])
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
TRANSACTIONAL_KINDS = ("confirm", "already", "test_live")   # test_live: admin one-off test issue to a confirmed subscriber
def sender_status(kind="issue"):
    """Effective mode + why. Never returns secret values, only whether each required key is present.
    Transactional mail (confirm / already-subscribed) may go live with transactional_sending_approved alone; issues stay gated by
    live_sending_approved + mailing_address."""
    tx = kind in TRANSACTIONAL_KINDS
    e = env(); c = cfg(); want = (e.get("NEWSLETTER_SENDER") or "preview").strip().lower()
    if want not in SENDER_MODES: return {"requested": want, "mode": "preview", "reason": f"unknown sender '{want}': using preview"}
    need = {"smtp": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"], "resend": ["RESEND_API_KEY"], "brevo": ["BREVO_API_KEY"], "sendgrid": ["SENDGRID_API_KEY"]}.get(want, [])
    missing = [k for k in need if not e.get(k)]
    st = {"requested": want, "keys_present": {k: bool(e.get(k)) for k in need}, "live_sending_approved": bool(c.get("live_sending_approved")),
          "mailing_address_set": bool((c.get("mailing_address") or "").strip()), "from": c["from_email"]}
    if want == "preview": return {**st, "mode": "preview", "reason": "preview mode: emails are written to newsletter_outbox/ and nothing is sent"}
    if missing: return {**st, "mode": "preview", "reason": f"{want} selected but {', '.join(missing)} not set: using preview"}
    if tx and (c.get("transactional_sending_approved") or c.get("live_sending_approved")):
        return {**st, "mode": want, "reason": f"live (transactional only): sending {kind} email through {want}"}
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
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "blackout.network-newsletter/1.0 (+https://blackout.network)", **headers})
    with urllib.request.urlopen(req, timeout=20) as r: return r.status, r.read(2000).decode("utf-8", "replace")

def deliver(msg, kind="issue", sid=None, force_preview=False):
    """Send one message with the effective sender. Returns (ok, mode, outbox_file|None, error|None)."""
    mode = "preview" if force_preview else sender_status(kind)["mode"]
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
            try: return True, mode, "resend:" + str(json.loads(body).get("id") or ""), None
            except Exception: pass
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
        title = f"Confirm your {BRAND} newsletter subscription"
        paras = [f"Someone (hopefully you) asked to subscribe {row['email']} to the {BRAND} newsletter: {FREQS.get(row['frequency'], 'twice daily').lower()} briefs of the highest-severity, source-verified threats.",
                 f"Click the button to confirm. The link expires in {c['confirm_ttl_hours']} hours. If you didn't ask for this, ignore this email and nothing will be sent."]
        hb, tx = render_simple(title, paras, ("Confirm subscription", L["confirm"]), c=c); unsub = None
    else:
        title = f"You're already subscribed to {BRAND}"
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
    brk = _row_get(r, "breaking", 1)
    if "breaking_present" in d or "breaking" in d:   # checkbox (absent = off) when the form says it rendered one
        brk = 1 if str(d.get("breaking") or "") in ("1", "on", "true", "True", "yes") else 0
    k = db(); k.execute("UPDATE subscribers SET frequency=?, interests=?, breaking=?, updated=? WHERE id=?", (freq, json.dumps(ints), int(brk if brk is not None else 1), iso(now()), r["id"])); k.commit(); k.close()
    log(f"subscriber #{r['id']} changed preferences", "sub")
    return 200, {"ok": True, "message": f"Saved: {FREQS[freq].lower()}, {'all categories' if ints == ['all'] else ', '.join(ints)}, breaking alerts {'on' if brk else 'off'}."}

def add_category(tok, cat):
    """'Add this category' on the Find new sources page. Same signed manage token; frequency is left alone."""
    st, r = token_sub(tok, "manage")
    if st != "ok" or r is None: return 400, {"ok": False, "message": "This link is invalid or expired. Use the link in your latest email."}
    if r["status"] != "active": return 400, {"ok": False, "message": "This address isn't subscribed right now. Sign up again to restart the brief."}
    if cat not in CATEGORIES: return 400, {"ok": False, "message": "Unknown category."}
    try: cur = json.loads(r["interests"] or '["all"]')
    except Exception: cur = ["all"]
    if "all" in cur or cat in cur: return 200, {"ok": True, "message": f"You already get {cat}.", "interests": _clean_ints(cur)}
    ints = _clean_ints(cur + [cat])
    k = db(); k.execute("UPDATE subscribers SET interests=?, updated=? WHERE id=?", (json.dumps(ints), iso(now()), r["id"])); k.commit(); k.close()
    log(f"subscriber #{r['id']} added category {cat}", "sub")
    return 200, {"ok": True, "message": f"Added {cat}. It applies from the next send.", "interests": ints}

# ------------------------------------------------------------------ personalized source suggestions (real Sources catalog + global directory only)
# Newsletter category -> global-directory categories (the published registries behind /sources). Empty: no matching directory section.
DIR_MAP = {"war/conflict": ["News & media", "Government & public agencies"], "political": ["Government & public agencies", "Local government"],
           "natural disaster": ["Emergency management", "Seismic, volcanic & geophysical", "Weather, radar & ocean", "Hydrology & flood gauges"],
           "disease": ["Health & medical institutions"], "cyber": ["Security & cyber", "Internet outage sensors"], "space weather": ["Satellites & space"],
           "financial": [], "ufo/uap": [], "spiritual/religious": [], "other": ["Police & law enforcement", "Scanner & public-safety audio"]}
_URL_OK = re.compile(r"^https?://[^\s<>\"']+$")
def _ro(path):
    if not os.path.exists(path): return None
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5); c.row_factory = sqlite3.Row; return c
def catalog_picks(cat, n=5, skip=()):
    """Top-rated sources in the Sources catalog that mainly report on this category (rating 7+/10, its top category or 30%+ of its items, live link)."""
    c = None
    try:
        c = _ro(P["sources_db"])
        if c is None: return []
        jp = '$."' + cat.replace('"', "") + '"'
        rows = c.execute("""SELECT key,name,type,link,rating,n_items,origin FROM sources WHERE link LIKE 'http%' AND rating>=7
                            AND COALESCE(status,'') NOT LIKE 'disabled%' AND COALESCE(json_extract(categories, ?),0)>0
                            AND (top_category=? OR 1.0 * json_extract(categories, ?) / MAX(n_items, 1) >= 0.3)
                            ORDER BY rating DESC, json_extract(categories, ?) DESC, n_items DESC LIMIT ?""", (jp, cat, jp, jp, n + len(skip) + 5)).fetchall()
    except Exception: return []
    finally:
        if c: c.close()
    out = []
    for r in rows:
        if r["key"] in skip or not _URL_OK.match(r["link"] or ""): continue
        out.append({"key": r["key"], "name": r["name"], "type": r["type"], "url": r["link"], "rating": r["rating"], "n": r["n_items"] or 0})
        if len(out) >= n: break
    return out
def directory_picks(dcat, n=3, day=None):
    """A few entries from the global directory for one directory category: link-checked entries first, then a daily rotation."""
    c = None
    try:
        c = _ro(P["dir_db"])
        if c is None: return []
        day = day if day is not None else int(time.time() // 86400)
        rows = c.execute("""SELECT name,url,kind,cc,reg FROM d WHERE cat=? AND url LIKE 'http%'
                            ORDER BY checked IS NULL, (id * 7919 + ?) % 100003 LIMIT ?""", (dcat, day, n)).fetchall()
        return [dict(r) for r in rows if _URL_OK.match(r["url"] or "")]
    except Exception: return []
    finally:
        if c: c.close()
def suggestions(row):
    """-> {'mine': [(cat, [catalog picks], [(dircat, [dir picks])])], 'more': [(cat, [catalog picks])], 'all': bool, 'have': [cats]}"""
    try: ints = json.loads(row["interests"] or '["all"]')
    except Exception: ints = ["all"]
    allc = "all" in ints or not ints
    have = list(CATEGORIES) if allc else [x for x in CATEGORIES if x in ints]
    per = 4 if allc else 6; seen = set(); mine = []
    for cat in have:
        picks = catalog_picks(cat, per, seen); seen.update(p["key"] for p in picks)
        dirs = [(d, directory_picks(d, 2 if allc else 3)) for d in DIR_MAP.get(cat, [])[:2]]
        dirs = [(d, x) for d, x in dirs if x]
        if picks or dirs: mine.append((cat, picks, dirs))
    more = []
    if not allc:
        for cat in CATEGORIES:
            if cat in have: continue
            more.append((cat, catalog_picks(cat, 3, seen)))
    return {"mine": mine, "more": more, "all": allc, "have": have}

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

def audience_path(c=None):
    """Where the real subscriber list lives. Signups, confirmations, unsubscribes and Follow clicks happen on the public node (Render owns
    newsletter.db there); the box mirrors it to render_mirror/newsletter.db every sync cycle. Live issue sending on the box reads that
    mirror (read-only). While issue sending is locked (preview), the box's own newsletter.db is used, so no outbox spam for real people."""
    c = c or cfg()
    p = (c.get("audience_db") or "").strip() or os.environ.get("NEWSLETTER_AUDIENCE_DB", "")
    if p: return p
    m = os.path.join(BASE, "render_mirror", "newsletter.db")
    if not os.environ.get("BN_WEB_ONLY") and os.path.exists(m) and sender_status("issue")["mode"] != "preview": return m
    return P["db"]

def audience(c=None):
    """{id: active subscriber dict + 'follows' (active followed cluster ids) + 'last_sent_at' from this node's send ledger}."""
    p = audience_path(c); local = os.path.abspath(p) == os.path.abspath(P["db"])
    if local: k = db()
    else: k = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=15); k.row_factory = sqlite3.Row
    try:
        subs = {r["id"]: dict(r) for r in k.execute("SELECT * FROM subscribers WHERE status='active'")}
        try:
            for f in k.execute("SELECT subscriber_id, cluster_id FROM follows WHERE active=1"):
                if f[0] in subs: subs[f[0]].setdefault("follows", []).append(f[1])
        except sqlite3.OperationalError: pass     # a mirror taken before the follows table existed
    finally: k.close()
    L = db()
    try:
        for s in subs.values():
            s.setdefault("follows", []); s["breaking"] = 1 if s.get("breaking") is None else int(s["breaking"])
            r = L.execute("""SELECT MAX(r.slot_time) FROM sends s JOIN slot_runs r ON r.slot_key=s.slot_key
                             WHERE s.subscriber_id=? AND s.status='sent'""", (s["id"],)).fetchone()[0]
            s["last_sent_at"] = max([x for x in (s.get("last_sent_at"), r) if x] or [None], key=lambda x: x or "")
    finally: L.close()
    return subs

def record_sent(k, send_id, sid, issue_or_items, at, kind=None):
    """Remember what went to this subscriber (cluster, rank, title) so later editions only repeat it as an UPDATE."""
    secs = issue_or_items if isinstance(issue_or_items, list) else [it for s in ("follow", "main", "updates", "politics", "notable", "watchlist") for it in issue_or_items.get(s, [])]
    for it in secs:
        k.execute("INSERT INTO sent_items(send_id,subscriber_id,cluster_id,title_norm,section,sent_at,rank,n_items,eff,fams,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (send_id, sid, it["cluster_id"], it["title_norm"], it["section"], iso(at), it["rank"], it.get("n_items"), it["eff"],
                   json.dumps(it["families"][:20]), kind or ("update" if it.get("update") else "new")))

def _send_one(k, srow, sub, key, slot, at, c):
    """Build + deliver one issue. Caller holds the 'sending' claim on srow."""
    issue = build_issue(dict(sub), at=at, slot=slot, c=c)
    if issue["empty"]:   # never send an empty email
        k.execute("UPDATE sends SET status='skipped_empty', sent_at=? WHERE id=?", (iso(now()), srow["id"])); k.commit(); return "skipped"
    L = links_for(sub, c); L["_row"] = sub; subj, hb, tx = render(issue, L, c)
    msg = build_mime(sub["email"], subj, hb, tx, L["unsubscribe"], "issue", c)
    ok, mode, f, err = deliver(msg, "issue", sub["id"])
    t = iso(now())
    if ok:
        k.execute("""UPDATE sends SET status='sent', sent_at=?, mode=?, outbox_file=?, subject=?, n_main=?, n_notable=?, n_watch=?, quiet=?, error=NULL,
                     attempts=attempts+1 WHERE id=?""", (t, mode, f, subj, len(issue["main"]) + len(issue["updates"]) + len(issue["follow"]) + len(issue["politics"]), len(issue["notable"]),
                                                       len(issue["watchlist"]), int(issue["quiet"]), srow["id"]))
        record_sent(k, srow["id"], sub["id"], issue, at)
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
        aud = audience(c)
        for s in aud.values():
            if (s.get("confirmed_at") or "9") <= iso(at) and eligible(s["frequency"], slot, c):
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
            sub = aud.get(srow["subscriber_id"])
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

def run_breaking(at=None, c=None, dry_run=False):
    """Check the breaking-alert trigger and send (or, while issue sending is locked, record + write one outbox preview). Rate-limited.
    -> list of (key, status). dry_run=True evaluates only: nothing is written."""
    c = c or cfg(); at = at or now(); b = c.get("breaking") or {}
    if not b.get("enabled", True) or c.get("paused"): return []
    cands = breaking_candidates(at, c)
    k = db()
    try:
        seen = {r["cluster_id"]: r for r in k.execute("SELECT * FROM breaking_seen")}
        briefed = {x[0] for x in k.execute("SELECT DISTINCT cluster_id FROM sent_items WHERE sent_at>=?", (iso(at - timedelta(days=float(c.get("dedupe_days") or 14))),))}
        fresh = [(r, rule, o) for r, rule, o in cands if r["cluster_id"] not in briefed and (r["cluster_id"] not in seen
                 or (int(r["rank"] or 0) >= 9 and int(seen[r["cluster_id"]]["rank"] or 0) < 9))]   # escalation into rank 9+ may alert again
        hr = at.astimezone(ET).hour
        if hr >= int(b.get("quiet_start", 22)) or hr < int(b.get("quiet_end", 7)):   # overnight: only rank 9+
            fresh = [x for x in fresh if int(x[0]["rank"] or 0) >= int(b.get("quiet_min_rank", 9))]
        trend = None
        if not fresh and not (hr >= int(b.get("quiet_start", 22)) or hr < int(b.get("quiet_end", 7))):
            for t_ in load_trending():
                tid = "trend:" + str(t_.get("id") or "")
                if tid != "trend:" and tid not in seen and t_.get("url") and (parse_t(t_.get("at")) or at) > at - timedelta(hours=12): trend = t_; break
        if not fresh and not trend: return []
        if dry_run: return [(f"breaking:dry:{r['cluster_id']}", rule) for r, rule, o in fresh]
        runs = [parse_t(x[0]) for x in k.execute("SELECT ts FROM breaking_runs WHERE status IN ('sent','locked','running','done') AND ts>=?",
                                                 (iso(at - timedelta(hours=24)),))]
        lastr = max([x for x in runs if x] or [None], key=lambda x: x or datetime.min.replace(tzinfo=UTC))
        limited = (lastr and at - lastr < timedelta(hours=float(b.get("min_gap_hours", 3)))) or len(runs) >= int(b.get("max_per_day", 3))
        if limited:
            for r, rule, o in fresh:
                k.execute("INSERT OR REPLACE INTO breaking_seen(cluster_id,ts,rank,rule,status,run_id) VALUES(?,?,?,?,?,NULL)",
                          (r["cluster_id"], iso(at), int(r["rank"] or 0), rule, "held"))
            k.commit(); log(f"breaking: {len(fresh)} qualifying stor(ies) held by the rate limit; they lead the next brief", "breaking")
            return [("breaking:held", len(fresh))]
        take = fresh[:int(b.get("max_items", 3))]
        items = []
        if trend:
            k.execute("INSERT OR REPLACE INTO breaking_seen(cluster_id,ts,rank,rule,status,run_id) VALUES(?,?,?,?,?,NULL)", ("trend:" + str(trend["id"]), iso(at), 0, "T1", "pending")); k.commit()
        for r, rule, o in take:
            it = item_of(r, "main", o); it["rule"] = rule; it["breaking"] = True; items.append(it)
        mode = sender_status("issue")["mode"]
        status = "locked" if mode == "preview" else "running"
        note = "issue sending is locked (preview): one outbox preview written, no email sent" if status == "locked" else ""
        cur = k.execute("INSERT INTO breaking_runs(ts,cluster_ids,status,mode,note) VALUES(?,?,?,?,?)", (iso(at), json.dumps([i["cluster_id"] for i in items] or ["trend:" + str(trend["id"])]), status, mode, note))
        run_id = cur.lastrowid
        for it in items:
            k.execute("INSERT OR REPLACE INTO breaking_seen(cluster_id,ts,rank,rule,status,run_id) VALUES(?,?,?,?,?,?)", (it["cluster_id"], iso(at), it["rank"], it["rule"], status, run_id))
        k.commit()
    finally: k.close()
    base = c["base_url"].rstrip("/")
    if status == "locked":
        L = {"unsubscribe": f"{base}/newsletter", "manage": f"{base}/newsletter", "categories": f"{base}/newsletter", "sources": f"{base}/sources",
             "scoring": f"{base}/scoring", "site": f"{base}/#wire", "_row": None}
        subj, hb, tx = render_breaking(items, L, at, c, trend)
        f = _outbox_write(build_mime("preview@blackout.invalid", subj, hb, tx, None, "breaking", c), "breaking_preview", run_id)
        log(f"breaking run #{run_id} ({', '.join(i['cluster_id'] + ' ' + i['rule'] for i in items)}): LOCKED, preview -> newsletter_outbox/{f}", "breaking")
        return [(f"breaking:{run_id}", "locked")]
    key = f"breaking:{run_id}"; n_sent = n_t = 0
    k = db()
    try:
        aud = audience(c)
        for s in aud.values():
            if not s.get("breaking", 1): continue
            try: ints = set(json.loads(s.get("interests") or '["all"]'))
            except Exception: ints = {"all"}
            mine = [i for i in items if "all" in ints or not ints or i["category"] in ints or i["cluster_id"] in (s.get("follows") or [])]
            if not mine and not (trend and not items): continue
            cur = k.execute("INSERT OR IGNORE INTO sends(subscriber_id,slot_key,status,created) VALUES(?,?,?,?)", (s["id"], key, "sending", iso(now()))); k.commit()
            if cur.rowcount != 1: continue
            n_t += 1; srow_id = k.execute("SELECT id FROM sends WHERE subscriber_id=? AND slot_key=?", (s["id"], key)).fetchone()[0]
            for i in mine: i["followed"] = i["cluster_id"] in (s.get("follows") or [])
            L = links_for(s, c); L["_row"] = s
            subj, hb, tx = render_breaking(mine, L, at, c, trend if not items else None)
            ok, mode, f, err = deliver(build_mime(s["email"], subj, hb, tx, L["unsubscribe"], "issue", c), "issue", s["id"])
            k.execute("UPDATE sends SET status=?, sent_at=?, mode=?, outbox_file=?, subject=?, n_main=?, error=?, attempts=1 WHERE id=?",
                      ("sent" if ok else "gave_up", iso(now()), mode, f, subj, len(mine), err, srow_id))
            if ok: record_sent(k, srow_id, s["id"], mine, at, "breaking"); n_sent += 1
            k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file,subject,error) VALUES(?,?,?,?,?,?,?,?)",
                      (iso(now()), "breaking", s["id"], mode, "sent" if ok else "failed", f, subj, err))
            k.commit()
        k.execute("UPDATE breaking_runs SET status='done', n_targets=?, n_sent=? WHERE id=?", (n_t, n_sent, run_id)); k.commit()
    finally: k.close()
    log(f"breaking run #{run_id}: sent {n_sent}/{n_t}", "breaking")
    return [(key, "done")]

def run_due(at=None):
    """Called every ~30 s by newsletter_worker.py. Idempotent per slot: the slot_runs row is written before anything is sent and each
    (subscriber, slot) pair is UNIQUE in sends, so restarts never double-send. Catch-up: a slot missed while the box was down is sent
    once if we're within catchup_hours (2 h) of it, otherwise recorded as skipped. Failed sends retry with backoff (2, 10, 30 min).
    Then checks the breaking-alert trigger (run_breaking)."""
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
        try: res += run_breaking(at, c)
        except Exception as ex: traceback.print_exc(); log(f"breaking check failed: {ex}", "error")
    return res

def cleanup_outbox(days=None):
    days = days if days is not None else int(cfg()["outbox_retention_days"])
    cut = time.time() - days * 86400; n = 0
    for f in (os.listdir(P["outbox"]) if os.path.isdir(P["outbox"]) else []):
        if f.startswith("sample_issue"): continue
        p = os.path.join(P["outbox"], f)
        if os.path.isfile(p) and os.path.getmtime(p) < cut: os.remove(p); n += 1
    keep = float(cfg().get("dedupe_days") or 14) + 1
    k = db(); k.execute("DELETE FROM sent_items WHERE sent_at<?", (iso(now() - timedelta(days=keep)),)); k.commit(); k.close()
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
    L = {"unsubscribe": f"{base}/newsletter", "manage": f"{base}/newsletter", "categories": f"{base}/newsletter", "sources": f"{base}/sources",
         "scoring": f"{base}/scoring", "site": f"{base}/#wire", "_row": None}
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
            "next_slots": next_slots(n=4, c=c), "sender": sender_status(), "sender_transactional": sender_status("confirm"), "worker_running": worker_alive(), "outbox_eml": outbox,
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
    if a == "test_send":   # one real issue to ONE confirmed subscriber (not recorded as sent, so it never affects dedupe)
        em = str(d.get("email") or "").strip().lower(); c = cfg()
        k = db(); r = k.execute("SELECT * FROM subscribers WHERE email=? AND status='active' AND confirmed_at IS NOT NULL", (em,)).fetchone(); k.close()
        if not r: return 404, {"ok": False, "message": "No confirmed, active subscriber with that address."}
        sub = dict(r); at = now(); nxt = next_slots(at, 1, c)[0]
        issue = build_issue(sub, at=at, since=at - timedelta(hours=12), slot=nxt["slot"], c=c)
        L = links_for(sub, c); L["_row"] = sub; subj, hb, tx = render(issue, L, c)
        ok, mode, f, err = deliver(build_mime(sub["email"], "[TEST] " + subj, hb, tx, L["unsubscribe"], "issue", c), "test_live", sub["id"])
        k = db(); k.execute("INSERT INTO mail_log(ts,kind,subscriber_id,mode,status,outbox_file,subject,error) VALUES(?,?,?,?,?,?,?,?)",
                            (iso(now()), "test_live", sub["id"], mode, "sent" if ok else "failed", f, "[TEST] " + subj, err)); k.commit(); k.close()
        return 200, {"ok": ok, "mode": mode, "id": f, "error": err, "subject": "[TEST] " + subj, "sent_at_et": fmt_et(now()), "html": hb}
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
            k.execute("DELETE FROM follows WHERE subscriber_id=?", (r["id"],))
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

# ------------------------------------------------------------------ Follow this story (one click, signed token, no login)
def _story_title(cid):
    try:
        S = src(); r = S.execute("SELECT title FROM clusters WHERE cluster_id=?", (cid,)).fetchone(); S.close()
        return re.sub(r"\s+", " ", r[0]).strip() if r and r[0] else None
    except Exception: return None

def follow(tok, on=True):
    """-> (ok|invalid|inactive|limit, row, cluster_id, title). Idempotent. The token names one subscriber + one story cluster."""
    purpose = "follow" if on else "unfollow"
    st, p = read_token(tok, purpose)
    if st == "invalid" or not p: return "invalid", None, None, None
    cid = str(p.get("c") or "")
    if not re.match(r"^[0-9a-f]{8,40}$", cid): return "invalid", None, None, None
    k = db()
    try:
        r = k.execute("SELECT * FROM subscribers WHERE id=?", (int(p.get("s", 0)),)).fetchone()
        if not r or h(r["email"], 12) != p.get("x"): return "invalid", None, cid, None
        if on and r["status"] != "active": return "inactive", r, cid, None
        title = _story_title(cid); t = iso(now())
        if on:
            n = k.execute("SELECT COUNT(*) FROM follows WHERE subscriber_id=? AND active=1", (r["id"],)).fetchone()[0]
            cur = k.execute("SELECT active FROM follows WHERE subscriber_id=? AND cluster_id=?", (r["id"], cid)).fetchone()
            if not (cur and cur[0]) and n >= int(cfg().get("follow_max") or 50): return "limit", r, cid, title
            k.execute("""INSERT INTO follows(subscriber_id,cluster_id,title,created,active) VALUES(?,?,?,?,1)
                         ON CONFLICT(subscriber_id,cluster_id) DO UPDATE SET active=1, unfollowed_at=NULL, title=COALESCE(excluded.title, follows.title)""",
                      (r["id"], cid, title, t))
        else:
            k.execute("UPDATE follows SET active=0, unfollowed_at=? WHERE subscriber_id=? AND cluster_id=?", (t, r["id"], cid))
            if not title:
                x = k.execute("SELECT title FROM follows WHERE subscriber_id=? AND cluster_id=?", (r["id"], cid)).fetchone(); title = x[0] if x else None
        k.commit()
    finally: k.close()
    log(f"subscriber #{r['id']} {'followed' if on else 'unfollowed'} story {cid}", "follow")
    return "ok", r, cid, title

def follows_of(sid):
    k = db()
    try: return [dict(x) for x in k.execute("SELECT cluster_id, title, created FROM follows WHERE subscriber_id=? AND active=1 ORDER BY created DESC", (sid,))]
    finally: k.close()

# ------------------------------------------------------------------ HTML pages
def page(title, body, robots="noindex"):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="{robots}">' + sitenav.head_html("newsletter") +
            '<link rel="stylesheet" href="/theme.css"><link rel="icon" href="/favicon.ico" sizes="any"><link rel="stylesheet" href="/api/newsletter/app.css">'
            '<link rel="stylesheet" href="/api/translate/app.css"></head><body class="nl-page"><a class="skip" href="#main">Skip to content</a>'
            + sitenav.site_top("newsletter") +
            f'<div class="nl-wrap" id="main" role="main">{body}</div>'
            f'<footer>Research-only data · {BRAND} · <a href="/#wire">Dashboard</a> · <a href="/scoring">How we score</a> · <a href="/newsletter">Newsletter</a> · <a href="/privacy">Privacy</a> · <a href="/tos">Terms</a><br>{BRAND} · PO Box 1228, Lake Mary, FL 32746</footer>'
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
    body = ('<section class="nl-card"><h2>✉ The BLACKOUT.NETWORK brief, in your inbox</h2>'
            '<p class="nl-lede">Once or twice a day: the highest-severity threats that cleared the main-feed bar, each as a one-paragraph brief '
            '(what happened, where, when, how well it\'s confirmed, and the raw source link so you can verify it yourself), plus a short watchlist '
            'of unconfirmed single-source reports. Every story opens with a bottom line up front and links to its own page on BLACKOUT.NETWORK, '
            'where you can open every original source. A story you already got is never repeated: when it develops, you get only what is new, '
            'marked UPDATE. Tap <b>Follow this story</b> on any item to get its updates. Quiet windows get a short "nothing qualified" note, never filler.</p>'
            '<div id="nl_app" data-mode="page">' + form_html("page") + '</div>'
            '<p class="nl-sm"><a href="/newsletter/sample" target="_blank" rel="noopener">See a sample issue built from live data →</a></p></section>'
            '<section class="nl-card nl-faq"><h3>How it works</h3><ul>'
            '<li><b>Double opt-in.</b> You get a confirmation email first. Nothing else is sent until you click it.</li>'
            f'<li><b>What makes the main feed.</b> Rank {rmin}+ items confirmed by {smin}+ independent sources (the same bar as instant alerts). '
            'If fewer than 3 qualify, up to 3 "Also notable" items (confirmed rank 5–6, or a high rank from one official source) are added and labeled. '
            'See <a href="/scoring">How we score</a>.</li>'
            '<li><b>Watchlist.</b> Up to 5 low-confidence, single-source reports, each clearly labeled UNCONFIRMED.</li>'
            '<li><b>Breaking alerts.</b> Rare emergency emails for truly major events only, such as the outbreak of a war, a novel pathogen or a rank 9–10 event, '
            'at most one every 3 hours. You can turn them off on the manage page.</li>'
            '<li><b>Follow this story.</b> One click in any email, no login. Updates on that story then lead your next brief until you unfollow.</li>'
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
            '</div><p class="nl-sm">Leave all ticked (or none) to get every category.</p></fieldset>'
            '<fieldset><legend>Breaking alerts</legend><input type="hidden" name="breaking_present" value="1">'
            f'<label class="nl-chk"><input type="checkbox" name="breaking" value="1"{" checked" if _row_get(r, "breaking", 1) else ""}> Send me rare breaking alerts for truly major events (at most one every 3 hours)</label></fieldset>'
            '<button class="pri" type="submit">Save preferences</button> '
            '<p class="nl-msg" role="status" aria-live="polite"></p></form>')

def _src_li(p):
    meta = " · ".join(x for x in (E(p["type"]), f'rated {int(p["rating"])}/10' if p.get("rating") is not None else "",
                                   f'{p["n"]:,} items seen' if p.get("n") else "") if x)
    return (f'<li><a href="{E(p["url"])}" target="_blank" rel="noopener nofollow">{E(p["name"])}</a> '
            f'<span class="nl-sm">{meta}</span></li>')
def _dir_li(p):
    meta = " · ".join(E(x) for x in (p.get("kind"), p.get("cc"), ("from " + p["reg"]) if p.get("reg") else "") if x)
    return f'<li><a href="{E(p["url"])}" target="_blank" rel="noopener nofollow">{E(p["name"])}</a> <span class="nl-sm">{meta}</span></li>'
def sources_body(tok, r):
    S = suggestions(r); mt = E(tok)
    head = ('<section class="nl-card"><h2>Find new sources</h2>'
            f'<p>Picked for <b>{E(mask_email(r["email"]))}</b> from the categories you get: <b>{"all categories" if S["all"] else E(", ".join(S["have"]))}</b>. '
            'Every suggestion links to the real source. They come from the BLACKOUT.NETWORK <a href="/sources">Sources catalog</a> (rated 7/10 or higher) '
            'and its global directory of published registries.</p>'
            f'<p><a class="nl-btn" href="/newsletter/manage?token={mt}">Manage my subscription categories</a></p></section>')
    out = [head]
    if not S["mine"]:
        out.append('<section class="nl-card"><p>Source suggestions are still loading. Try again in a few minutes, or <a href="/sources">browse all sources</a>.</p></section>')
    for cat, picks, dirs in S["mine"]:
        blk = [f'<section class="nl-card nl-src"><h3>Because you get {E(cat)}</h3>']
        if picks: blk.append('<p class="nl-sm">Top-rated sources in the catalog for this category:</p><ul class="nl-srclist">' + "".join(_src_li(p) for p in picks) + '</ul>')
        for d, xs in dirs:
            blk.append(f'<p class="nl-sm">From the directory: {E(d)}</p><ul class="nl-srclist">' + "".join(_dir_li(p) for p in xs) + '</ul>')
        blk.append('</section>'); out.append("".join(blk))
    if S["more"]:
        out.append('<section class="nl-card"><h2>Categories you don\'t get yet</h2><p class="nl-sm">Add one to start getting it in your brief. Each shows a few of the sources behind it.</p>')
        for cat, picks in S["more"]:
            out.append(f'<div class="nl-more"><form class="nl-addcat" method="post" action="/api/newsletter/add_category" data-nl-addcat>'
                       f'<input type="hidden" name="token" value="{mt}"><input type="hidden" name="category" value="{E(cat)}">'
                       f'<b>{E(cat)}</b> <button class="pri nl-btn" type="submit">Add this category</button> <span class="nl-msg" role="status" aria-live="polite"></span></form>'
                       + (('<ul class="nl-srclist">' + "".join(_src_li(p) for p in picks) + '</ul>') if picks else '<p class="nl-sm">No catalog sources rated 7+ for this category yet.</p>')
                       + '</div>')
        out.append('</section>')
    out.append('<p class="nl-sm"><a href="/sources">Browse all sources</a> · <a href="/sources#sources">Search the global directory</a></p>'
               '<script src="/api/newsletter/app.js"></script>')
    return "".join(out)

def _follows_card(r):
    fs = follows_of(r["id"])
    if not fs: return ('<section class="nl-card"><h3>Stories you follow</h3><p class="nl-sm">None yet. Tap <b>Follow this story</b> under any item in a brief '
                       'to get its updates.</p></section>')
    li = "".join(f'<li><a href="/wire/{E(f["cluster_id"])}">{E(_cut(f["title"] or f["cluster_id"], 140))}</a> · '
                 f'<a class="nl-sm" href="{E(follow_links(r, f["cluster_id"])["unfollow"])}">Unfollow</a></li>' for f in fs)
    return f'<section class="nl-card"><h3>Stories you follow ({len(fs)})</h3><ul class="nl-srclist">{li}</ul></section>'

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
        bar = (f'<div style="background:{PAL["surf2"]};color:{PAL["mu"]};font:400 12px/1.5 {FB};padding:8px 20px;text-align:left;border-bottom:1px solid {PAL["line"]}">Sample issue, built live from '
               f'the current data window. Subject line: <b style="color:{PAL["tx"]}">{E(subj)}</b> · <a style="{_L}" href="/newsletter">Subscribe</a> · '
               f'<a style="{_L}" href="/#wire">Dashboard</a></div>')
        return 200, re.sub(r'(<body [^>]*>)', lambda m: m.group(1) + bar, hb, count=1), "text/html"
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
    if path in ("/newsletter/follow", "/newsletter/unfollow"):
        on = path.endswith("/follow"); tok = q1("token"); st, r, cid, title = follow(tok, on)
        story = f'/wire/{E(cid)}' if cid else "/#wire"; tl = E(title or "this story")
        if st == "ok" and on:
            fl = follow_links(r, cid)
            return 200, result_page("You're following this story", f"Following: {title or 'this story'}. Updates (new independent sources, rank changes) will lead your "
                                    "next brief until you unfollow. No login needed.", True,
                                    f'<p><a class="nl-btn" href="{story}">Open the story</a> <a href="{E(fl["unfollow"])}">Unfollow</a></p>'), "text/html"
        if st == "ok":
            fl = follow_links(r, cid)
            return 200, result_page("Unfollowed", f"You won't get separate updates on: {title or 'this story'}. Your regular brief continues.", True,
                                    f'<p><a class="nl-btn" href="{story}">Open the story</a> <a href="{E(fl["follow"])}">Follow again</a></p>'), "text/html"
        if st == "inactive":
            return 200, result_page("Not currently subscribed", "This address isn't receiving the newsletter, so there is nothing to follow with. Sign up again first.", False,
                                    '<p><a class="nl-btn" href="/newsletter">Sign up</a></p>'), "text/html"
        if st == "limit":
            return 200, result_page("Too many followed stories", f"You already follow {cfg().get('follow_max', 50)} stories. Unfollow some on your manage page first.", False), "text/html"
        return 400, result_page("Link not valid", "This follow link is invalid or was altered. Use the link in your latest email.", False,
                                f'<p><a class="nl-btn" href="{story}">Open the story</a></p>'), "text/html"
    if path == "/newsletter/breaking_off":
        tok = q1("token"); st, r = token_sub(tok, "manage")
        if st != "ok" or r is None:
            return 400, result_page("Link not valid", "This link is invalid or expired. Use the link in your latest email.", False), "text/html"
        k = db(); k.execute("UPDATE subscribers SET breaking=0, updated=? WHERE id=?", (iso(now()), r["id"])); k.commit(); k.close()
        log(f"subscriber #{r['id']} turned breaking alerts off (footer link)", "sub")
        return 200, result_page("Breaking alerts off", "Done. You'll still get your Morning and Evening Briefs. Turn breaking alerts back on any time under Manage.", True,
                                f'<p><a class="nl-btn" href="/newsletter/manage?token={E(tok)}">Manage preferences</a></p>'), "text/html"
    if path == "/newsletter/manage":
        tok = q1("token"); st, r = token_sub(tok, "manage")
        if st != "ok" or r is None:
            return 400, result_page("Link not valid", "This preferences link is invalid, expired, or the subscription was erased. Use the link in your latest email.", False), "text/html"
        if r["status"] != "active":
            return 200, result_page("Not currently subscribed", "This address isn't receiving the newsletter. Sign up again to restart it.", False,
                                    '<p><a class="nl-btn" href="/newsletter">Sign up</a></p>'), "text/html"
        body = (f'<section class="nl-card" id="categories"><h2>Manage my subscription categories</h2><p>Subscribed: <b>{E(mask_email(r["email"]))}</b>. '
                'Tick the threat categories you want in your brief and choose how often it arrives. Changes apply from the next send.</p>'
                + prefs_form(tok, r) + '</section>'
                f'<section class="nl-card"><h3>Find new sources</h3><p>See top-rated sources and registries for the categories you follow, plus categories you could add.</p>'
                f'<p><a class="nl-btn" href="/newsletter/sources?token={E(tok)}">Find new sources</a></p>'
                f'<p class="nl-sm"><a href="/newsletter/unsubscribe?token={E(sub_token("unsub", r))}">Unsubscribe instead</a></p></section>'
                + _follows_card(r) + '<script src="/api/newsletter/app.js"></script>')
        return 200, page("Subscription categories", body), "text/html"
    if path == "/newsletter/sources":
        tok = q1("token"); st, r = token_sub(tok, "manage")
        if st != "ok" or r is None:
            return 400, result_page("Link not valid", "This link is invalid, expired, or the subscription was erased. Use the Find new sources button in your latest email.", False,
                                    '<p><a class="nl-btn" href="/sources">Browse all sources</a></p>'), "text/html"
        if r["status"] != "active":
            return 200, result_page("Not currently subscribed", "This address isn't receiving the newsletter. Sign up again to restart it.", False,
                                    '<p><a class="nl-btn" href="/newsletter">Sign up</a></p>'), "text/html"
        return 200, page("Find new sources", sources_body(tok, r)), "text/html"
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
    if path == "/api/newsletter/add_category":
        tok = d.get("token"); code, body = add_category(tok, str(d.get("category") or ""))
        if html_mode:
            back = f'<p><a class="nl-btn" href="/newsletter/sources?token={E(tok or "")}">Back to Find new sources</a></p>'
            return code, result_page("Category added" if body.get("ok") else "Couldn't add", body["message"], bool(body.get("ok")), back), "text/html"
        return code, body
    if path == "/api/newsletter/admin/login": return admin_login(d, ip or "")
    if path == "/api/newsletter/admin":
        if not admin_ok(d): return 401, {"error": "Admin session expired. Unlock again."}
        return admin_action(d)
    return 404, {"error": "not found"}
