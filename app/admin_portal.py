"""Read-only admin portal at /admin (Matt, Nov 21 2026).

Password is stored only as a salted PBKDF2 hash (never plaintext). Session cookie is HttpOnly,
Secure, SameSite=Lax, 30 days. Failed logins are rate-limited per IP. The page is noindex and
is not in the sitemap or the public menu. Status is assembled server-side from existing
internals (public_status, story_writer.status, newsletter admin_stats / cfg). No action
buttons. Never prints or returns secrets.
"""
import hashlib, hmac, html, json, os, re, sqlite3, time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

# Salted PBKDF2-HMAC-SHA256 of the portal password. Not the site admin passcode.
PASS_HASH = "pbkdf2_sha256$260000$e980a87da81c2736a7168c9b57fa8bbc$70d09bdcabe53c49a3427bb1d65042efe1ac887b903d86c5286784ba1b5c6bf2"
COOKIE = "bn_portal"
TTL = 30 * 24 * 3600
FAIL_WINDOW = 15 * 60
FAIL_MAX = 10
STALE_S = 20 * 60
_SESSION_KEY = hashlib.sha256(b"bn-admin-portal-v1|" + PASS_HASH.encode()).digest()
_FAILS = {}
_SECRET_NAME = re.compile(r"(api_?key|secret|token|password|passcode|passwd|authorization|private_key)$", re.I)
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

def _ip(h):
    if hasattr(h, "ip"):
        try: return h.ip()
        except Exception: pass
    return (h.headers.get("CF-Connecting-IP") or (h.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            or (h.client_address[0] if getattr(h, "client_address", None) else "0"))

def check_password(pw):
    if not isinstance(pw, str) or not pw: return False
    try:
        algo, iters, salt_hex, dk_hex = PASS_HASH.split("$")
        if algo != "pbkdf2_sha256": return False
        n = int(iters)
        got = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), n)
        return hmac.compare_digest(got, bytes.fromhex(dk_hex))
    except Exception:
        return False

def _sign(exp):
    msg = f"v1.{int(exp)}".encode()
    return hmac.new(_SESSION_KEY, msg, hashlib.sha256).hexdigest()

def make_session(now=None):
    exp = int((now or time.time()) + TTL)
    return f"v1.{exp}.{_sign(exp)}"

def session_ok(h, now=None):
    raw = (h.headers.get("Cookie") or "")
    try: c = SimpleCookie(raw)
    except Exception: return False
    if COOKIE not in c: return False
    val = c[COOKIE].value or ""
    parts = val.split(".")
    if len(parts) != 3 or parts[0] != "v1": return False
    try: exp = int(parts[1])
    except Exception: return False
    if exp < int(now or time.time()): return False
    return hmac.compare_digest(parts[2], _sign(exp))

def _cookie(value, clear=False):
    if clear:
        return f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
    return f"{COOKIE}={value}; Path=/; Max-Age={TTL}; HttpOnly; Secure; SameSite=Lax"

def _fails(ip, now=None):
    t = now or time.time()
    _FAILS[ip] = [x for x in _FAILS.get(ip, []) if t - x < FAIL_WINDOW]
    return _FAILS[ip]

def locked(ip, now=None):
    return len(_fails(ip, now)) >= FAIL_MAX

def record_fail(ip, now=None):
    _fails(ip, now).append(now or time.time())

def _headers(extra=None):
    h = {"X-Robots-Tag": "noindex, nofollow", "X-Frame-Options": "DENY", "Cache-Control": "no-store"}
    if extra: h.update(extra)
    return h

def _password_from(h, data):
    if isinstance(data, dict):
        for k in ("password", "pass", "pw"):
            if data.get(k) is not None and str(data.get(k)) != "": return str(data[k])
    raw = getattr(h, "_raw", b"") or b""
    try:
        q = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
        for k in ("password", "pass", "pw"):
            if q.get(k): return q[k][0]
    except Exception:
        pass
    return ""

def _scrub(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_NAME.search(str(k)) and isinstance(v, str) and len(v) > 0:
                continue
            out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    return obj

def _scan_row():
    base = os.environ.get("BN_BASE") or os.path.dirname(os.path.abspath(__file__))
    db = os.path.join(base, "blackout.db")
    if not os.path.exists(db): return None
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            r = c.execute("SELECT finished, fetched, new_items, ok_sources, failed_sources, trigger "
                          "FROM scans WHERE finished IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            return dict(r) if r else None
        finally:
            c.close()
    except Exception:
        return None

def _wire_activity():
    base = os.environ.get("BN_BASE") or os.path.dirname(os.path.abspath(__file__))
    db = os.path.join(base, "blackout.db")
    empty = {"h1": {"total": 0, "r0_4": 0, "r5_6": 0, "r7plus": 0},
             "h24": {"total": 0, "r0_4": 0, "r5_6": 0, "r7plus": 0}, "newest": []}
    if not os.path.exists(db): return empty
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cut1 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
        cut24 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400))
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            def band(cut):
                rows = c.execute("SELECT COALESCE(rank,0) r, COUNT(*) n FROM clusters "
                                 "WHERE watchlist=0 AND COALESCE(event_time, first_seen)>=? "
                                 "GROUP BY 1", (cut,)).fetchall()
                out = {"total": 0, "r0_4": 0, "r5_6": 0, "r7plus": 0}
                for r in rows:
                    n = int(r["n"]); rk = int(r["r"]); out["total"] += n
                    if rk >= 7: out["r7plus"] += n
                    elif rk >= 5: out["r5_6"] += n
                    else: out["r0_4"] += n
                return out
            newest = [dict(r) for r in c.execute(
                "SELECT cluster_id, title, rank, COALESCE(event_time, first_seen) t "
                "FROM clusters WHERE watchlist=0 ORDER BY COALESCE(event_time, first_seen) DESC LIMIT 8")]
            return {"h1": band(cut1), "h24": band(cut24), "newest": newest, "now": now}
        finally:
            c.close()
    except Exception as ex:
        return {**empty, "error": type(ex).__name__}

def _newsletter():
    try:
        import newsletter as NL
        import render_app as R
        st = NL.admin_stats()
        return {
            "sender": st.get("sender"),
            "live_sending_approved": bool((st.get("settings") or {}).get("live_sending_approved")),
            "render_scheduler": bool(NL.cfg().get("render_scheduler")),
            "restored": bool(getattr(R, "SYNC", {}).get("restored")),
            "held": dict(getattr(NL, "HELD", {}) or {}),
            "next_slots": st.get("next_slots"),
            "runs": (st.get("runs") or [])[:6],
            "mail": (st.get("mail") or [])[:8],
            "counts": st.get("counts"),
            "now_et": st.get("now_et"),
        }
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {str(ex)[:200]}"}

def _writer():
    try:
        import story_writer
        return story_writer.status()
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {str(ex)[:200]}"}

def snapshot():
    try:
        import render_app as R
        pub = R.public_status()
    except Exception as ex:
        pub = {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:200]}"}
    scan = _scan_row()
    age = pub.get("last_scan_age_s")
    stale = (age is None) or (age > STALE_S)
    deploy = (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("RENDER_GIT_COMMIT_SHA") or "")[:12] or None
    out = {
        "ok": True,
        "scanner": {
            "badge": "STALE" if stale else "OK",
            "stale": stale,
            "last_scan": pub.get("last_scan"),
            "last_scan_age_s": age,
            "last_sync": pub.get("last_sync"),
            "last_sync_age_s": pub.get("last_sync_age_s"),
            "sync_healthy": pub.get("sync_healthy"),
            "scan": scan,
        },
        "realtime": pub.get("realtime") or {},
        "wire": _wire_activity(),
        "writer": _writer(),
        "newsletter": _newsletter(),
        "server": {
            "boot_id": pub.get("boot_id"),
            "booted": pub.get("booted"),
            "uptime_s": None,
            "memory": pub.get("memory"),
            "deploy_commit": deploy,
            "has_data": pub.get("has_data"),
            "node": pub.get("node"),
        },
        "now": pub.get("now") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    booted = pub.get("booted")
    if booted:
        try:
            import calendar
            from email.utils import parsedate_to_datetime
            # booted is ISO Z
            t = time.strptime(booted, "%Y-%m-%dT%H:%M:%SZ")
            out["server"]["uptime_s"] = int(time.time() - calendar.timegm(t))
        except Exception:
            pass
    return _scrub(out)

def _fmt_age(s):
    if s is None: return "never"
    try: s = int(s)
    except Exception: return "—"
    if s < 60: return f"{s}s ago"
    if s < 3600: return f"{s // 60} min ago"
    if s < 86400: return f"{s // 3600}h { (s % 3600)//60 }m ago"
    return f"{s // 86400}d ago"

def _fmt_et(iso):
    if not iso: return "—"
    try:
        t = time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        # UTC -> ET (EST/EDT: use fixed offset is wrong; use zoneinfo if available)
        try:
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo
            dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
            return dt.strftime("%b %-d, %-I:%M %p ET") if os.name != "nt" else dt.strftime("%b %d, %I:%M %p ET")
        except Exception:
            return iso
    except Exception:
        return E(iso)

HEAD = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#05060a">
<title>Admin · BLACKOUT.NETWORK</title>
<style>
:root{--bg:#05060a;--pn:#12161b;--tx:#e6e9ee;--mu:#8a94a3;--bd:#232a33;--bd2:#2f3742;--sf:#161b21;--red:#c8102e}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--tx)}a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #fff;outline-offset:2px}
.wrap{max-width:820px;margin:0 auto;padding:20px 16px 48px}
.wm{font-weight:700;letter-spacing:.02em;font-size:15px;margin:0}
.sub{color:var(--mu);font-size:13px;margin:4px 0 18px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin:0 0 16px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button,.btn{appearance:none;background:transparent;color:var(--tx);border:1px solid var(--bd2);border-radius:9px;padding:10px 14px;font:700 14px/1 system-ui;cursor:pointer}
.card{background:var(--pn);border:1px solid var(--bd);border-radius:12px;padding:14px 16px;margin:0 0 14px}
.card h2{font-size:15px;letter-spacing:.04em;text-transform:uppercase;color:var(--mu);font-weight:700;margin:0 0 10px}
.kv{display:grid;grid-template-columns:minmax(8rem,34%) 1fr;gap:6px 12px;font-size:15px}
.kv span{color:var(--mu)}
.badge{display:inline-block;font-size:12px;font-weight:800;letter-spacing:.06em;border:1px solid var(--bd2);border-radius:6px;padding:3px 8px}
.badge.bad{border-color:var(--red);color:#fff;background:var(--red)}
.list{list-style:none;margin:10px 0 0;padding:0}
.list li{border-top:1px solid var(--bd);padding:8px 0;overflow-wrap:anywhere}
.rk7{color:#fff}
.rk7 .n{background:var(--red);border-radius:4px;padding:1px 6px;font-weight:800;font-size:12px;margin-right:6px}
.err{color:#fff;border-left:3px solid var(--red);padding-left:8px}
form{display:flex;flex-direction:column;gap:10px;max-width:360px}
label{font-size:13px;color:var(--mu)}
input[type=password]{background:var(--sf);color:var(--tx);border:1px solid var(--bd2);border-radius:9px;padding:12px 12px;font-size:16px}
.note{color:var(--mu);font-size:13px;margin-top:10px}
@media(max-width:420px){.kv{grid-template-columns:1fr} .kv span{font-size:12px}}
</style>
</head>
<body>
"""

def login_html(err=None, locked_out=False):
    msg = ""
    if locked_out:
        msg = "<p class='err'>Too many attempts. Wait 15 minutes and try again.</p>"
    elif err:
        msg = "<p class='err'>Wrong password.</p>"
    return (HEAD + f"""
<div class="wrap">
  <p class="wm">blackout.network</p>
  <p class="sub">Admin · research only</p>
  {msg}
  <form method="post" action="/admin/login" autocomplete="current-password">
    <label for="password">Password</label>
    <input id="password" name="password" type="password" required autofocus>
    <button type="submit">Log in</button>
  </form>
</div>
</body></html>""")

def _kv(rows):
    bits = []
    for k, v in rows:
        bits.append(f"<span>{E(k)}</span><div>{v if isinstance(v, str) and v.startswith('<') else E(v)}</div>")
    return "<div class='kv'>" + "".join(bits) + "</div>"

def page_html(data):
    sc = data.get("scanner") or {}
    rt = data.get("realtime") or {}
    wr = data.get("writer") or {}
    nl = data.get("newsletter") or {}
    sv = data.get("server") or {}
    wire = data.get("wire") or {}
    badge = sc.get("badge") or "STALE"
    bcls = "badge bad" if sc.get("stale") else "badge"
    scan = sc.get("scan") or {}
    sender = (nl.get("sender") or {})
    last_run = (nl.get("runs") or [None])[0]
    last_run_s = "—"
    if last_run:
        last_run_s = E(f"{last_run.get('slot_key') or ''} · {last_run.get('status') or ''} · {last_run.get('slot_time_et') or last_run.get('slot_time') or ''}")
        if last_run.get("note"): last_run_s += E(" · " + str(last_run.get("note"))[:160])
    next_slots = nl.get("next_slots") or []
    next_s = "—"
    if next_slots:
        x = next_slots[0]
        if isinstance(x, dict):
            next_s = E(" · ".join(str(x.get(k) or "") for k in ("slot", "at_et", "when", "time", "iso") if x.get(k)) or str(x))
        else:
            next_s = E(x)
    qn = len(wr.get("queue") or [])
    spend = wr.get("spend_today") or {}
    spend_s = "—"
    if isinstance(spend, dict):
        used = spend.get("usd") or spend.get("spent") or spend.get("total")
        cap = wr.get("daily_cap_usd")
        spend_s = f"{used} / {cap}" if used is not None else (f"cap {cap}" if cap is not None else "—")
    elif spend:
        spend_s = str(spend)
    written = wr.get("briefs") or {}
    written_s = written.get("written") if isinstance(written, dict) else written
    newest = ""
    for it in (wire.get("newest") or []):
        rk = int(it.get("rank") or 0)
        cls = "rk7" if rk >= 7 else ""
        newest += f"<li class='{cls}'><span class='n'>{E(rk)}</span>{E(it.get('title') or 'Untitled')} <span style='color:var(--mu);font-size:13px'>{E(_fmt_et(it.get('t')))}</span></li>"
    h1, h24 = wire.get("h1") or {}, wire.get("h24") or {}
    werr = wr.get("last_error") or wr.get("error") or wr.get("paused")
    nerr = nl.get("error")
    up = sv.get("uptime_s")
    up_s = "—"
    if isinstance(up, int):
        up_s = f"{up//3600}h {(up%3600)//60}m" if up >= 3600 else f"{up//60}m {up%60}s"
    rt_err = rt.get("errors")
    live = sender.get("mode") or "—"
    live_ok = bool(nl.get("live_sending_approved")) and live not in ("preview", "—", "")
    html_out = HEAD + f"""
<div class="wrap">
  <div class="bar">
    <div>
      <p class="wm">blackout.network</p>
      <p class="sub">Admin · research only · updates every 30 seconds</p>
    </div>
    <div class="row">
      <span class="{bcls}">{E(badge)}</span>
      <form method="get" action="/admin" style="margin:0"><button type="submit">Refresh</button></form>
      <form method="post" action="/admin/logout" style="margin:0"><button type="submit">Log out</button></form>
    </div>
  </div>

  <section class="card">
    <h2>Mac scanner</h2>
    {_kv([
        ("Last scan", _fmt_et(sc.get("last_scan")) + " (" + _fmt_age(sc.get("last_scan_age_s")) + ")"),
        ("Fetched / new", f"{scan.get('fetched', '—')} / {scan.get('new_items', '—')}" if scan else "—"),
        ("Sources ok / failed", f"{scan.get('ok_sources', '—')} / {scan.get('failed_sources', '—')}" if scan else "—"),
        ("Last sync", _fmt_et(sc.get("last_sync")) + " (" + _fmt_age(sc.get("last_sync_age_s")) + ")"),
        ("Sync healthy", "yes" if sc.get("sync_healthy") else "no"),
        ("Realtime Mac", "connected" if rt.get("mac_connected") else "offline"),
        ("Last push", _fmt_et(rt.get("last_push")) + " (" + _fmt_age(rt.get("last_push_age_s")) + ")"),
        ("Push errors", rt_err if rt_err not in (None, 0, "0") else "none"),
    ])}
  </section>

  <section class="card">
    <h2>Wire</h2>
    {_kv([
        ("Last 1 hour", f"{h1.get('total',0)} total · rank 0–4: {h1.get('r0_4',0)} · 5–6: {h1.get('r5_6',0)} · 7+: {h1.get('r7plus',0)}"),
        ("Last 24 hours", f"{h24.get('total',0)} total · rank 0–4: {h24.get('r0_4',0)} · 5–6: {h24.get('r5_6',0)} · 7+: {h24.get('r7plus',0)}"),
    ])}
    <ul class="list">{newest or "<li>No items</li>"}</ul>
  </section>

  <section class="card">
    <h2>Instant writer</h2>
    {_kv([
        ("Thread", "alive" if wr.get("thread_alive") else "not running"),
        ("API key", "set" if wr.get("api_key_set") else "missing"),
        ("Queue", qn),
        ("Written", written_s if written_s is not None else "—"),
        ("Spend today", spend_s),
        ("Last error", (werr or "none")),
    ])}
    {f"<p class='err'>{E(werr)}</p>" if werr and werr != "none" else ""}
  </section>

  <section class="card">
    <h2>Newsletter</h2>
    {_kv([
        ("Sender", f"{sender.get('requested') or '—'} · mode {live}"),
        ("Live sending", "on" if nl.get("live_sending_approved") else "off"),
        ("Scheduler", "on" if nl.get("render_scheduler") else "off"),
        ("Next send", next_s),
        ("Last send", last_run_s),
        ("Subscribers", (nl.get("counts") or {}).get("active", "—")),
    ])}
    {f"<p class='err'>{E(nerr)}</p>" if nerr else ""}
  </section>

  <section class="card">
    <h2>Server</h2>
    {_kv([
        ("Uptime", up_s),
        ("Memory", (f"{(sv.get('memory') or {}).get('rss_mb', '—')} MB RSS · peak {(sv.get('memory') or {}).get('peak_rss_mb', '—')} MB" if sv.get("memory") else "—")),
        ("Deploy", sv.get("deploy_commit") or "—"),
        ("Boot", sv.get("boot_id") or "—"),
    ])}
  </section>
  <p class="note">Read only. No sending, posting, or config changes from this page.</p>
</div>
<meta http-equiv="refresh" content="30">
</body></html>"""
    return html_out

def handle(h):
    method = (h.command or "GET").upper()
    path = h.path.split("?", 1)[0]
    if path.rstrip("/") == "/admin":
        path = "/admin"
    if method == "POST" and not getattr(h, "_raw", None) and path in ("/admin/login", "/admin", "/admin/logout"):
        try: h.body()
        except Exception: pass
    data = {}
    raw = getattr(h, "_raw", b"") or b""
    if raw:
        try: data = json.loads(raw)
        except Exception: data = {}

    if method == "POST" and path in ("/admin/login", "/admin"):
        ip = _ip(h)
        if locked(ip):
            return h.send(429, login_html(locked_out=True), "text/html", _headers())
        pw = _password_from(h, data)
        if check_password(pw):
            loc = {"Location": "/admin", "Set-Cookie": _cookie(make_session())}
            return h.send(302, b"", "text/html", _headers(loc))
        record_fail(ip)
        return h.send(401, login_html(err=True), "text/html", _headers())

    if method == "POST" and path == "/admin/logout":
        loc = {"Location": "/admin", "Set-Cookie": _cookie("", clear=True)}
        return h.send(302, b"", "text/html", _headers(loc))

    if method == "GET" and path in ("/admin", "/admin/login"):
        if path == "/admin" and session_ok(h):
            return h.send(200, page_html(snapshot()), "text/html", _headers())
        return h.send(200, login_html(), "text/html", _headers())

    if method == "GET" and path == "/api/admin/status":
        if not session_ok(h):
            return h.send(401, {"error": "login required"}, "application/json", _headers())
        return h.send(200, snapshot(), "application/json", _headers())

    if path.startswith("/admin") or path.startswith("/api/admin"):
        return h.send(404, {"error": "not found"}, "application/json", _headers())
    return h.send(404, {"error": "not found"})
