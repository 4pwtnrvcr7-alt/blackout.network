#!/usr/bin/env python3
"""blackout.network public web node for Render (free web service).

Runs ONLY the read-mostly web front end (server.py handler + add-ons). Everything heavy stays on the box:
no scanner/jet/newsletter scheduler, no Whisper/ffmpeg/yt-dlp/Argos subprocesses, no background harvest loops.
Data arrives from the box via authenticated pushes to /internal/sync/* (see render_sync.py).

Env vars (set in the Render dashboard; never baked into the image):
  BN_SYNC_SECRET     required: shared HMAC secret, same value the scanner node signs its pushes with
  PORT               set by Render (default 10000)
  BN_ADMIN_PASSCODE  optional: admin passcode; otherwise the box pushes it over the sync channel; otherwise a random one (admin unusable)
  NEWSLETTER_SECRET  optional: otherwise pushed by the box (keeps confirm/unsubscribe links valid on both sides)
  BN_PUBLIC_POST_ALLOW optional: extra comma-separated POST path prefixes the public may call
Newsletter live sending stays locked here: NEWSLETTER_SENDER is forced to preview and no worker runs."""
import os, sys, io, json, time, hmac, hashlib, tarfile, tempfile, threading, subprocess, sqlite3, secrets, traceback, gzip, shutil

BASE = "/workspace/blackout"
os.chdir(BASE); sys.path.insert(0, BASE)
STATE = os.environ.get("BN_STATE_DIR", "/tmp/bn_state")
os.makedirs(STATE, mode=0o700, exist_ok=True)
SECRET_DIR = os.path.join(STATE, "secrets"); os.makedirs(SECRET_DIR, mode=0o700, exist_ok=True)
for k, v in {"NEWSLETTER_NO_WORKER": "1", "BN_NO_STREAMWATCH": "1", "BN_NO_SNAPSHOTS": "1", "BN_WEB_ONLY": "1",
             "NEWSLETTER_ENV": os.path.join(SECRET_DIR, "newsletter.env"), "BN_TRANSLATE_URL": "http://127.0.0.1:9"}.items():
    os.environ[k] = v
os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
import render_rules as R

SYNC_SECRET = os.environ.get("BN_SYNC_SECRET", "")
MAX_PUSH = int(os.environ.get("BN_SYNC_MAX_MB", "96")) * 1024 * 1024
BOOT_ID = secrets.token_hex(8)
BOOTED = time.time()
MANIFEST_F = os.path.join(STATE, "manifest.json")
SYNC = {"last_push": None, "pushes": 0, "files": 0, "bytes": 0, "restored": False, "last_error": None}
_mlock = threading.Lock()

# ---------- web-only guards: block background loops and subprocesses started by add-ons ----------
BLOCK_THREAD_NAMES = {"bn-search-index", "politics_hist", "politics_markets", "netstatus", "heatmap_geocoder", "solar_seismic_logger",
                      "video-subs-bg", "streams-live", "bcast-text", "bcast-audio"}
BLOCK_TARGETS = {"_loop", "loop", "_warm_loop", "_indexer", "_text_loop", "_audio_loop", "harvest", "scheduler", "jet_loop", "_harvest"}
ALLOW_TARGETS = {"_watch", "bg", "process_request_thread", "_render_bg"}
BLOCKED = []
_orig_start = threading.Thread.start
def _guarded_start(self):
    t = getattr(self, "_target", None); tn = getattr(t, "__name__", "") or ""
    if tn not in ALLOW_TARGETS and (self.name in BLOCK_THREAD_NAMES or tn in BLOCK_TARGETS or any(w in tn.lower() for w in ("loop", "harvest", "indexer"))):
        BLOCKED.append(f"thread:{self.name}:{tn}"); return None
    return _orig_start(self)
threading.Thread.start = _guarded_start

class _FakePopen:
    pid = 0; returncode = 0; stdout = stderr = stdin = None
    def __init__(self, args, *a, **k): BLOCKED.append("popen:" + str(args if isinstance(args, str) else " ".join(map(str, args)))[:120])
    def poll(self): return 0
    def wait(self, *a, **k): return 0
    def communicate(self, *a, **k): return ("", "")
    def kill(self): pass
    terminate = kill
    def __enter__(self): return self
    def __exit__(self, *a): return False
def _fake_run(args, *a, **k):
    BLOCKED.append("run:" + str(args if isinstance(args, str) else " ".join(map(str, args)))[:120])
    out = "" if k.get("text") or k.get("universal_newlines") or k.get("encoding") else b""
    return subprocess.CompletedProcess(args, 127, out, out)
subprocess.Popen = _FakePopen; subprocess.run = _fake_run
subprocess.check_output = lambda *a, **k: (_ for _ in ()).throw(subprocess.CalledProcessError(127, a[0] if a else ""))

# ---------- secrets pushed by the box (or env), stored only under /tmp with 0600 ----------
def _write_secret(path, text):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: f.write(text)
    os.replace(tmp, path); os.chmod(path, 0o600)
def apply_secrets(d):
    if d.get("admin_passcode") and not os.environ.get("BN_ADMIN_PASSCODE"):
        _write_secret(os.path.join(BASE, "ADMIN_PASSCODE.txt"), str(d["admin_passcode"]).strip() + "\n")
    ns = os.environ.get("NEWSLETTER_SECRET") or d.get("newsletter_secret")
    if ns:   # sender + provider keys come only from Render env vars (never synced, never logged); default stays preview
        lines = [f"NEWSLETTER_SECRET={ns}", "NEWSLETTER_SENDER=" + (os.environ.get("NEWSLETTER_SENDER") or "preview").strip()]
        lines += [f"{k}={os.environ[k].strip()}" for k in MAIL_ENV_KEYS if os.environ.get(k)]
        _write_secret(os.environ["NEWSLETTER_ENV"], "\n".join(lines) + "\n")
MAIL_ENV_KEYS = ("RESEND_API_KEY", "BREVO_API_KEY", "SENDGRID_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_SECURITY")
if os.environ.get("BN_ADMIN_PASSCODE"): _write_secret(os.path.join(BASE, "ADMIN_PASSCODE.txt"), os.environ["BN_ADMIN_PASSCODE"].strip() + "\n")
if os.environ.get("NEWSLETTER_SECRET"): apply_secrets({})

# ---------- newsletter scheduler (t373): 07:00 / 19:00 America/New_York via newsletter.run_due() ----------
# Runs only when newsletter_config.json (pushed by the box) has render_scheduler=true. run_due is idempotent per slot
# (slot_runs + UNIQUE(subscriber, slot)); an flock keeps a second process/instance on this disk from running it at the same time.
def _nl_lookup(NL, em):
    if not em: return None
    k = NL.db()
    try: r = k.execute("SELECT status, created, confirmed_at FROM subscribers WHERE email=?", (str(em).strip().lower(),)).fetchone()
    finally: k.close()
    return dict(r) if r else "not found"
def _nl_tick():
    import fcntl
    while True:
        time.sleep(45)
        try:
            if not SYNC.get("restored") and SYNC_SECRET: continue          # wait until newsletter.db is restored from the mirror
            import newsletter as NL
            if not NL.cfg().get("render_scheduler"): continue
            with open(os.path.join(STATE, "newsletter_sched.lock"), "w") as lk:
                try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError: continue
                for key, st in NL.run_due(): print(f"newsletter slot {key}: {st}", flush=True)
        except Exception: traceback.print_exc()
threading.Thread(target=_nl_tick, name="nl-sched", daemon=True).start()

import server  # noqa: E402  (imports scanner/push/jets modules only; their loops are never started here)

# ---------- manifest of what the box has pushed ----------
def _load_manifest():
    try: return json.load(open(MANIFEST_F))
    except Exception: return {}
MAN = _load_manifest()
def _save_manifest():
    tmp = MANIFEST_F + ".tmp"
    with open(tmp, "w") as f: json.dump(MAN, f)
    os.replace(tmp, MANIFEST_F)
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def _db_snapshot(src_rel):
    """Consistent copy of a Render-owned sqlite DB (backup API), returned as a temp file path."""
    src = os.path.join(BASE, src_rel)
    fd, tmp = tempfile.mkstemp(dir=STATE, suffix=".db"); os.close(fd)
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=20); d = sqlite3.connect(tmp)
    try: s.backup(d); d.execute("PRAGMA journal_mode=DELETE"); d.commit()
    finally: d.close(); s.close()
    return tmp

def has_data(): return os.path.exists(os.path.join(BASE, "blackout.db"))

# ---------- auth ----------
def verify(h, method, path, body_sha):
    if len(SYNC_SECRET) < 32: return False, "sync disabled: BN_SYNC_SECRET not set (needs 32+ chars)"
    ts = h.headers.get("X-BN-Ts") or ""; sig = h.headers.get("X-BN-Sig") or ""
    try: skew = abs(time.time() - float(ts))
    except Exception: return False, "bad timestamp"
    if skew > 300: return False, "timestamp skew"
    want = hmac.new(SYNC_SECRET.encode(), f"{ts}\n{method}\n{path}\n{body_sha}".encode(), hashlib.sha256).hexdigest()
    return (True, "") if hmac.compare_digest(want, sig) else (False, "bad signature")

def _install(rel, tmp_path, kind):
    dest = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if kind in ("db", "owned"):
        try:
            c = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True); ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"; c.close()
        except Exception: ok = False
        if not ok: os.unlink(tmp_path); raise ValueError(f"{rel}: failed sqlite quick_check")
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, dest)
    if kind in ("db", "owned"):
        for suf in ("-wal", "-shm"):
            try: os.unlink(dest + suf)       # stale WAL/SHM from the previous file must never be applied to the new one
            except FileNotFoundError: pass

def handle_push(h):
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > MAX_PUSH: return 413, {"error": f"push must be 1..{MAX_PUSH} bytes"}
    fd, tmp = tempfile.mkstemp(dir=STATE, suffix=".tgz"); hsh = hashlib.sha256(); left = n
    with os.fdopen(fd, "wb") as f:
        while left > 0:
            b = h.rfile.read(min(left, 1 << 20))
            if not b: break
            f.write(b); hsh.update(b); left -= len(b)
    try:
        if left: return 400, {"error": "short body"}
        ok, why = verify(h, "POST", "/internal/sync/push", hsh.hexdigest())
        if not ok: return 403, {"error": why}
        done, refused = [], []
        with tarfile.open(tmp, "r:gz") as tf:
            meta = {}
            for m in tf:
                if m.name == "__meta__.json" and m.isfile():
                    meta = json.load(tf.extractfile(m)); continue
                kind = R.sync_kind(m.name)
                if not m.isfile() or kind is None or (kind == "owned" and m.name not in (meta.get("restore") or [])):
                    refused.append(m.name); continue
                src = tf.extractfile(m)
                dfd, dtmp = tempfile.mkstemp(dir=os.path.dirname(os.path.join(BASE, m.name)) if os.path.isdir(os.path.dirname(os.path.join(BASE, m.name))) else BASE, prefix=".bnsync_")
                with os.fdopen(dfd, "wb") as out: shutil.copyfileobj(src, out)
                _install(m.name, dtmp, kind)
                with _mlock: MAN[m.name] = (meta.get("hashes") or {}).get(m.name) or _sha(os.path.join(BASE, m.name))
                done.append(m.name); SYNC["bytes"] += m.size
        if meta.get("secrets"): apply_secrets(meta["secrets"])
        if meta.get("restore_done"): SYNC["restored"] = True
        with _mlock: _save_manifest()
        SYNC.update(last_push=time.time(), pushes=SYNC["pushes"] + 1, files=SYNC["files"] + len(done))
        _refresh_state()
        return 200, {"status": "ok", "installed": len(done), "refused": refused[:50], "boot_id": BOOT_ID}
    except Exception as ex:
        SYNC["last_error"] = str(ex)[:300]; traceback.print_exc(); return 500, {"error": str(ex)[:300]}
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def manifest():
    owned = {}
    for rel in R.RENDER_OWNED:
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            try: tmp = _db_snapshot(rel); owned[rel] = _sha(tmp); os.unlink(tmp)
            except Exception as ex: owned[rel] = "error:" + str(ex)[:80]
    with _mlock:   # t338: only files that are really on disk (a restart can keep /tmp/bn_state but lose the pushed data -> "Syncing" forever)
        for rel in [r for r in MAN if not os.path.exists(os.path.join(BASE, r))]: MAN.pop(rel, None)
        files = dict(MAN)
    return {"boot_id": BOOT_ID, "booted": BOOTED, "files": files, "owned": owned, "restored": SYNC["restored"],
            "has_data": has_data(), "sync": SYNC, "blocked_background": len(BLOCKED)}

# ---------- memory (t353): Render free plan = 512 MB; report RSS publicly (no secrets) and hand freed heap back to the OS ----------
def _mem():
    d = {}
    try:
        for l in open("/proc/self/status"):
            k, _, v = l.partition(":")
            if k in ("VmRSS", "VmHWM", "Threads"): d[k] = int(v.split()[0])
    except Exception: pass
    return {"rss_mb": round(d.get("VmRSS", 0) / 1024, 1), "peak_rss_mb": round(d.get("VmHWM", 0) / 1024, 1), "threads": d.get("Threads")}
try:
    import ctypes; _libc = ctypes.CDLL("libc.so.6"); _trim = lambda: _libc.malloc_trim(0)
except Exception: _trim = lambda: None

def _iso(t): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)) if t else None
def public_status():
    """Public, secret-free freshness report: when the box last pushed data and when the scanner last finished."""
    lp = SYNC["last_push"]; ls = server.state.get("last_scan")
    age = round(time.time() - lp) if lp else None
    return {"ok": True, "node": "render-public", "has_data": has_data(), "boot_id": BOOT_ID, "booted": _iso(BOOTED),
            "last_sync": _iso(lp), "last_sync_age_s": age, "sync_healthy": bool(lp) and age < 900,
            "pushes_since_boot": SYNC["pushes"], "files_installed_since_boot": SYNC["files"], "owned_restored": SYNC["restored"],
            "last_scan": _iso(ls), "last_scan_age_s": round(time.time() - ls) if ls else None, "now": _iso(time.time()),
            "memory": {**_mem(), "limit_mb": 512, "malloc_arena_max": os.environ.get("MALLOC_ARENA_MAX")}}

# ---------- keep "last scan / next scan" meaningful from synced data ----------
def _refresh_state():
    try:
        if not has_data(): return
        c = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=10)
        try: r = c.execute("SELECT finished FROM scans WHERE finished IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
        finally: c.close()
        if r and r[0]:
            t = server.scanner.parse_t(r[0]).timestamp()
            server.state["last_scan"] = t; server.state["next_scan"] = t + server.cfg()["interval_minutes"] * 60
    except Exception: traceback.print_exc()

# ---------- translation: no Argos on Render -> serve cached translations; language list pushed by the box ----------
_orig_addon_mod = server._addon_mod
def _addon_mod(name):
    m = _orig_addon_mod(name)
    if name == "translate" and not getattr(m, "_bn_render_patched", False):
        def langs():
            try: return json.load(open(os.path.join(BASE, "translate_langs.json")))["langs"]
            except Exception: return []
        m.langs = langs; m._bn_render_patched = True
    return m
server._addon_mod = _addon_mod

POST_ALLOW = ["/api/vote", "/api/newsletter", "/newsletter", "/api/translate", "/api/search", "/api/sources", "/sources",
              "/api/report", "/api/reports", "/api/alerts"] + \
             [x for x in os.environ.get("BN_PUBLIC_POST_ALLOW", "").split(",") if x]
OWNED_WRITERS = ["/api/vote", "/api/newsletter", "/newsletter", "/api/alerts"]
BOX_ONLY = {"/api/refresh": "Scans run on the blackout.network scanner node; this page updates automatically every few minutes.",
            "/api/interval": "Scan settings are managed on the scanner node.", "/api/jets/settings": "Jet settings are managed on the scanner node.",
            "/api/settings": "Alert settings are managed on the scanner node."}
WARMING = b"""<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=20><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Know first. Be ready.</title>
<meta name=description content="BLACKOUT.NETWORK is a free early-warning threat monitor: outbreaks, quakes, space weather, cyber attacks and conflict, ranked 0-10 and linked to sources."><link rel=canonical href="https://blackout.network/"><meta property="og:type" content="website"><meta property="og:site_name" content="BLACKOUT.NETWORK"><meta property="og:title" content="BLACKOUT.NETWORK | Know first. Be ready."><meta property="og:url" content="https://blackout.network/"><meta property="og:description" content="Free early-warning threat monitor: global threats ranked 0-10 and linked to sources."><meta property="og:image" content="https://blackout.network/icons/icon-og-1200x630.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="@BlkoutNtw"><link rel=stylesheet href=/theme.css><link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"><link rel="icon" type="image/png" sizes="32x32" href="/icons/icon-32.png"><link rel="icon" type="image/png" sizes="16x16" href="/icons/icon-16.png"><meta name="theme-color" content="#0b0d10"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Blackout"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><link rel="stylesheet" href="/install-guide.css"><script src="/install-guide.js" defer></script></head><body style="font-family:system-ui;background:#0b0f14;color:#d7dde5;display:grid;place-items:center;height:100vh">
<div style="text-align:center"><h1>blackout.network</h1><p>Know first. Be ready.</p>
<p>Syncing the latest data&hellip; this page refreshes automatically.</p></div></body></html>"""

class RH(server.H):
    server_version = "Blackout/1.0"
    def send_response(self, code, message=None):
        try:   # privacy-safe aggregate traffic counters (usage_stats.py); pulled by the box over the signed reports sync
            import usage_stats; usage_stats.record(self.path, code, self.command, self.ip(), self.headers.get("User-Agent", ""), self.headers.get("Referer", ""), self.headers)
        except Exception: pass
        return super().send_response(code, message)
    def ip(self):
        return self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or self.client_address[0]
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz": return self.send(200, {"ok": True, "has_data": has_data(), "boot_id": BOOT_ID})
        if path in ("/api/status", "/api/sync_status"): return self.send(200, public_status())
        if path == "/internal/sync/manifest":
            ok, why = verify(self, "GET", path, hashlib.sha256(b"").hexdigest())
            return self.send(200, manifest()) if ok else self.send(403, {"error": why})
        if path == "/internal/sync/pull":
            ok, why = verify(self, "GET", self.path, hashlib.sha256(b"").hexdigest())
            if not ok: return self.send(403, {"error": why})
            from urllib.parse import urlparse, parse_qs
            rel = (parse_qs(urlparse(self.path).query).get("file") or [""])[0]
            if rel not in R.RENDER_OWNED or not os.path.exists(os.path.join(BASE, rel)): return self.send(404, {"error": "not found"})
            tmp = _db_snapshot(rel)
            try: data = gzip.compress(open(tmp, "rb").read(), 6)
            finally: os.unlink(tmp)
            return self.send(200, data, "application/gzip")
        if not has_data():
            if path in ("/", "/index.html"): return self.send(503, WARMING, "text/html")
            if path.startswith("/api/") and not path.startswith(("/api/report/", "/api/reports/")):   # problem reports work without synced data
                return self.send(503, {"error": "warming up: waiting for the first data sync"})
        return super().do_GET()
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/internal/sync/push": return self.send(*handle_push(self))
        if path in ("/internal/newsletter/test", "/internal/newsletter/status"):   # t373: box-signed (BN_SYNC_SECRET HMAC) newsletter ops
            self.body(); raw = getattr(self, "_raw", b"") or b""
            ok, why = verify(self, "POST", path, hashlib.sha256(raw).hexdigest())
            if not ok: return self.send(403, {"error": why})
            import newsletter as NL
            try: d = json.loads(raw or b"{}")
            except Exception: d = {}
            if path.endswith("/status"):
                st = NL.admin_stats()
                return self.send(200, {"counts": st["counts"], "sender": st["sender"], "next_slots": st["next_slots"], "runs": st["runs"][:6],
                                       "mail": st["mail"][:8], "render_scheduler": bool(NL.cfg().get("render_scheduler")), "restored": SYNC["restored"],
                                       "lookup": _nl_lookup(NL, d.get("email"))})
            return self.send(*NL.admin_action({"action": "test_send", "email": d.get("email"), "location": d.get("location")}))
        if path in BOX_ONLY:
            self.body(); return self.send(503 if path == "/api/refresh" else 403, {"status": "unavailable", "error": BOX_ONLY[path]})
        if not any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in POST_ALLOW):
            self.body(); return self.send(403, {"error": "read-only public node"})
        if any(path == p or path.startswith(p + "/") for p in OWNED_WRITERS) and SYNC_SECRET and not SYNC["restored"] and time.time() - BOOTED < 900:
            self.body(); return self.send(503, {"error": "The site just restarted and is syncing. Please try again in a minute."})
        return super().do_POST()

def _render_bg():
    while True:
        _refresh_state()
        try: _trim()
        except Exception: pass
        time.sleep(60)

if __name__ == "__main__":
    server.passcode()      # creates a random one if none was provided (admin then unusable until the box pushes the real one)
    port = int(os.environ.get("PORT", "10000"))
    if not SYNC_SECRET: print("WARNING: BN_SYNC_SECRET not set; the box cannot push data", flush=True)
    t = threading.Thread(target=_render_bg, daemon=True); t.start()
    print(f"blackout.network public node on 0.0.0.0:{port} (boot {BOOT_ID}); background jobs blocked so far: {len(BLOCKED)}", flush=True)
    server.ThreadingHTTPServer.daemon_threads = True
    server.ThreadingHTTPServer.request_queue_size = 256   # t338: the default listen backlog (5) overflowed on page loads (~40 parallel requests) -> Render 502s
    server.ThreadingHTTPServer(("0.0.0.0", port), RH).serve_forever()
