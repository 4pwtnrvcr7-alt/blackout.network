"""Resend webhook receiver: POST /api/email-events -> newsletter.db table email_events (Render node; the box mirrors newsletter.db).

Off unless env RESEND_WEBHOOK_SECRET (the endpoint's "whsec_..." signing secret from Resend) is set: then 404, nothing stored.
Every request must carry a valid Svix signature (svix-id, svix-timestamp within 5 min, svix-signature v1 = base64 HMAC-SHA256 of
"id.timestamp.body" keyed with the base64-decoded secret). Idempotent: svix-id is the primary key, so Resend's retries are no-ops.

Stored per event, and nothing else (Compliance 2026-11-01): Resend email id, event type, event time, clicked link WITHOUT query string
or fragment (our links can carry personal tokens), and the subscriber id looked up from our own send log. No address, IP, user agent,
subject or headers. Bounded: rows older than 365 days are deleted, the table is capped at BN_EMAIL_EVENTS_MAX rows (oldest first), and
a subscriber's rows are deleted when they unsubscribe (purge_subscriber, called from newsletter.unsubscribe)."""
import base64, hashlib, hmac, json, os, sqlite3, time
from datetime import datetime, timezone

TYPES = {"email.delivered": "delivered", "email.opened": "opened", "email.clicked": "clicked", "email.bounced": "bounced",
         "email.complained": "complained", "email.failed": "failed", "email.suppressed": "suppressed"}
MAX_BODY = 64 * 1024
TOLERANCE_S = 300
RETAIN_DAYS = 365
MAX_ROWS = int(os.environ.get("BN_EMAIL_EVENTS_MAX", "200000"))
SCHEMA = """CREATE TABLE IF NOT EXISTS email_events(svix_id TEXT PRIMARY KEY, resend_id TEXT, type TEXT NOT NULL, ts TEXT NOT NULL,
  link TEXT, subscriber_id INTEGER, received TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ee_sub ON email_events(subscriber_id, type, ts);
CREATE INDEX IF NOT EXISTS ee_rid ON email_events(resend_id);
CREATE INDEX IF NOT EXISTS ee_ts ON email_events(received);"""
_N = {"n": 0}

def secret(): return os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
def enabled(): return bool(secret())

def _key(sec):
    s = sec[6:] if sec.startswith("whsec_") else sec
    try: return base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
    except Exception: return s.encode()

def sign(sec, msg_id, ts, body):
    """v1 signature (also used by the tests)."""
    return base64.b64encode(hmac.new(_key(sec), f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()

def verify(headers, body, sec=None, now=None):
    """-> (ok, reason). headers: any mapping with .get (case-insensitive lookups done here)."""
    sec = sec if sec is not None else secret()
    if not sec: return False, "disabled"
    g = lambda k: (headers.get(k) or headers.get(k.title()) or headers.get(k.upper()) or "").strip()
    mid, ts, sig = g("svix-id"), g("svix-timestamp"), g("svix-signature")
    if not (mid and ts and sig) or len(mid) > 200: return False, "missing signature headers"
    try: t = int(ts)
    except ValueError: return False, "bad timestamp"
    if abs((now or time.time()) - t) > TOLERANCE_S: return False, "timestamp outside tolerance"
    want = sign(sec, mid, ts, body)
    for part in sig.split():
        v, _, s = part.partition(",")
        if v == "v1" and hmac.compare_digest(s, want): return True, "ok"
    return False, "bad signature"

def _iso(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception: return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _link(v):
    v = str(v or "").split("#", 1)[0].split("?", 1)[0]
    return v[:300] if v.startswith(("https://", "http://")) else None

def init(k): k.executescript(SCHEMA)

def _subscriber(k, rid):
    if not rid: return None
    for t in ("sends", "mail_log"):
        try:
            r = k.execute(f"SELECT subscriber_id FROM {t} WHERE outbox_file=? AND subscriber_id IS NOT NULL LIMIT 1", ("resend:" + rid,)).fetchone()
            if r and r[0]: return int(r[0])
        except sqlite3.Error: pass
    return None

def prune(k, now=None):
    cut = datetime.fromtimestamp((now or time.time()) - RETAIN_DAYS * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    k.execute("DELETE FROM email_events WHERE received < ?", (cut,))
    n = k.execute("SELECT COUNT(*) FROM email_events").fetchone()[0]
    if n > MAX_ROWS:
        k.execute("DELETE FROM email_events WHERE rowid IN (SELECT rowid FROM email_events ORDER BY received, rowid LIMIT ?)", (n - MAX_ROWS,))

def purge_subscriber(k, sid):
    """Delete a subscriber's per-recipient events (on unsubscribe or a deletion request). Caller commits. Safe if the table doesn't exist."""
    if k.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='email_events'").fetchone():
        k.execute("DELETE FROM email_events WHERE subscriber_id=?", (sid,))

def store(k, msg_id, payload, now=None):
    """-> 'stored' | 'duplicate' | 'ignored'. Caller commits."""
    typ = TYPES.get(str(payload.get("type") or ""))
    if not typ: return "ignored"
    d = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rid = str(d.get("email_id") or "")[:80] or None
    link = _link((d.get("click") or {}).get("link")) if typ == "clicked" else None
    ts = _iso((d.get("click") or {}).get("timestamp") or payload.get("created_at") or d.get("created_at"))
    rec = datetime.fromtimestamp(now or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = k.execute("INSERT OR IGNORE INTO email_events(svix_id,resend_id,type,ts,link,subscriber_id,received) VALUES(?,?,?,?,?,?,?)",
                    (msg_id, rid, typ, ts, link, _subscriber(k, rid), rec))
    if cur.rowcount != 1: return "duplicate"
    _N["n"] += 1
    if _N["n"] % 200 == 1: prune(k, now)
    return "stored"

def handle(headers, body, db_path, now=None):
    """-> (http_code, json). 2xx tells Resend to stop retrying; 401/400 are not retried usefully, 5xx are."""
    if not enabled(): return 404, {"error": "not found"}
    if body is None or len(body) > MAX_BODY: return 413, {"error": "too large"}
    ok, why = verify(headers, body, now=now)
    if not ok: return 401, {"error": why}
    try: payload = json.loads(body.decode("utf-8"))
    except Exception: return 400, {"error": "bad json"}
    if not isinstance(payload, dict): return 400, {"error": "bad json"}
    g = lambda kk: (headers.get(kk) or headers.get(kk.title()) or "").strip()
    k = sqlite3.connect(db_path, timeout=15)
    try:
        init(k); st = store(k, g("svix-id"), payload, now); k.commit()
    except sqlite3.Error as ex:
        return 503, {"error": "storage busy", "detail": str(ex)[:80]}
    finally: k.close()
    return 200, {"ok": True, "result": st}
