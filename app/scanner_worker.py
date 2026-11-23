"""Always-on Render scanner worker (Nov 23 2026).

Runs the same scanner, geocoder and realtime push client the Mac uses, against
databases on a persistent disk. New rows are delivered to the public node through
POST /internal/rt/push (the Mac's live path). The site upserts by primary key, so
the same item from the Mac backup and this worker cannot create a duplicate row.

This process does not run a full /internal/sync/push of blackout.db. That endpoint
replaces the whole file, and two writers would race (last writer wins). Seed is a
pull of the site's current DBs via GET /internal/sync/export?part=bulk so the
12-hour cluster window is preserved. Until a seed succeeds, this worker will
scan locally but will not push, so it cannot mint a parallel set of cluster ids.

Never prints, logs or writes secret values. X reads stay off (X_READS_OFF=1).
Does not change scanner scoring, push.py, jets.py, config.json or aviation_watch.py.
"""
from __future__ import annotations

import gzip, hashlib, hmac, io, json, os, signal, sqlite3, sys, tarfile, tempfile, threading, time, traceback
import urllib.error, urllib.request

# --------------------------------------------------------------------------- config
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("BN_WORKER_DATA", "/data")
INTERVAL_MIN = int(os.environ.get("BN_WORKER_INTERVAL_MINUTES", "9"))
RENDER_URL = (os.environ.get("BN_RENDER_URL") or "https://blackout.network").rstrip("/")
STATUS_PATH = os.path.join(DATA, "worker_status.json")
SEED_MARK = os.path.join(DATA, ".seeded")
ALLOWED_SEED = frozenset({"blackout.db", "geo.db"})
VERSION = "render-worker/1"
WINDOW_DAYS = 7
LIMITS = {"clusters": 800, "alerts": 2000, "scans": 50, "geo": 2000}
STOP = threading.Event()


def _secret():
    return os.environ.get("BN_SYNC_SECRET") or ""


def secret_ok():
    return len(_secret()) >= 32


def env_report():
    """Names only: which required settings are present. Never includes values."""
    return {
        "BN_SYNC_SECRET": "set" if secret_ok() else "missing",
        "BN_RENDER_URL": "set" if (os.environ.get("BN_RENDER_URL") or "").startswith("http") else "default",
        "BN_RENDER_URL_host": urllib.request.urlparse(RENDER_URL).netloc,
        "X_READS_OFF": os.environ.get("X_READS_OFF", ""),
        "interval_minutes": INTERVAL_MIN,
        "data": DATA,
    }


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] worker: {msg}", flush=True)


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))


def rss_mb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    return None


def peak_rss_mb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- privileges + disk layout
def drop_privs():
    """If started as root (so we can chown the mounted disk), switch to bn."""
    if os.geteuid() != 0:
        return
    try:
        import pwd
        u = pwd.getpwnam("bn")
    except KeyError:
        return
    os.makedirs(DATA, exist_ok=True)
    for root, dirs, files in os.walk(DATA):
        try:
            os.chown(root, u.pw_uid, u.pw_gid)
        except OSError:
            pass
        for n in dirs + files:
            try:
                os.chown(os.path.join(root, n), u.pw_uid, u.pw_gid)
            except OSError:
                pass
    os.setgid(u.pw_gid)
    os.setuid(u.pw_uid)
    os.umask(0o077)


def link_dbs():
    """Point the scanner and geocoder (which write next to this file) at the disk."""
    os.makedirs(DATA, exist_ok=True)
    for name in ("blackout.db", "geo.db"):
        dest = os.path.join(BASE, name)
        src = os.path.join(DATA, name)
        if os.path.islink(dest) or not os.path.exists(dest):
            if os.path.lexists(dest) and not os.path.exists(dest):
                os.unlink(dest)
            if not os.path.islink(dest):
                os.symlink(src, dest)
        elif os.path.isfile(dest) and os.path.abspath(dest) != os.path.abspath(src):
            # An image file should never shadow the disk; move it aside once.
            bak = dest + ".image"
            if not os.path.exists(bak):
                os.rename(dest, bak)
            os.symlink(src, dest)


# --------------------------------------------------------------------------- HMAC client (same scheme as the Mac's render_sync / rt_push)
class Client:
    def __init__(self, url, secret):
        if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("BN_RENDER_URL must be https://")
        self.url, self.secret = url.rstrip("/"), secret

    def sign(self, method, path, body=b""):
        ts = str(int(time.time()))
        body_sha = hashlib.sha256(body or b"").hexdigest()
        sig = hmac.new(self.secret.encode(), f"{ts}\n{method}\n{path}\n{body_sha}".encode(), hashlib.sha256).hexdigest()
        return {"X-BN-Ts": ts, "X-BN-Sig": sig}

    def req(self, method, path, body=b"", timeout=120, ctype="application/gzip"):
        headers = {"User-Agent": "blackout-scanner-worker/1.0", "Accept": "application/json, application/gzip, */*"}
        headers.update(self.sign(method, path, body))
        if body:
            headers["Content-Type"] = ctype
            headers["Content-Length"] = str(len(body))
        req = urllib.request.Request(self.url + path, data=body or None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read()


def client():
    if not secret_ok():
        return None
    return Client(RENDER_URL, _secret())


# --------------------------------------------------------------------------- seed (pull only)
def _safe_member(name):
    rel = name.replace("\\", "/").lstrip("/")
    if rel != os.path.basename(rel) or rel.startswith(".") or ".." in rel:
        return None
    if rel not in ALLOWED_SEED:
        return None
    return rel


def extract_seed_tar(raw, dest_dir):
    """Install blackout.db and geo.db from a site export tarball. Ignores any secrets in meta.

    Returns the list of files written. Raises ValueError on a bad archive.
    """
    os.makedirs(dest_dir, exist_ok=True)
    written = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf:
            if m.name == "__meta__.json":
                continue  # may mention secrets; we do not read or apply them
            rel = _safe_member(m.name)
            if not rel or not m.isfile():
                continue
            src = tf.extractfile(m)
            if src is None:
                continue
            tmp_fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".seed_")
            try:
                with os.fdopen(tmp_fd, "wb") as out:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
                try:
                    c = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
                    try:
                        ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                    finally:
                        c.close()
                except sqlite3.Error as ex:
                    os.unlink(tmp)
                    raise ValueError(f"{rel}: not a usable sqlite database ({type(ex).__name__})") from ex
                if not ok:
                    os.unlink(tmp)
                    raise ValueError(f"{rel}: failed sqlite quick_check")
                os.chmod(tmp, 0o600)
                os.replace(tmp, os.path.join(dest_dir, rel))
                written.append(rel)
            except Exception:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                raise
    return written


def seed_from_site(cl):
    """Pull the live node's blackout.db + geo.db so the 12-hour cluster window is not reset."""
    if os.path.exists(os.path.join(DATA, "blackout.db")) and os.path.exists(SEED_MARK):
        return {"status": "already", "files": ["blackout.db"]}
    path = "/internal/sync/export?part=bulk"
    code, body = cl.req("GET", path, timeout=300)
    if code != 200:
        err = ""
        try:
            err = json.loads(body).get("error", "")[:200]
        except Exception:
            err = f"HTTP {code}"
        raise RuntimeError(f"seed export HTTP {code}: {err}")
    written = extract_seed_tar(body, DATA)
    if "blackout.db" not in written:
        raise RuntimeError("seed export had no blackout.db")
    open(SEED_MARK, "w").write(iso() + "\n")
    os.chmod(SEED_MARK, 0o600)
    return {"status": "seeded", "files": written}


# --------------------------------------------------------------------------- realtime delta (same queries as the Mac's rt_push.py)
def _ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def delta(wm):
    wm = wm or {}
    d = {"v": VERSION}
    cut = iso(time.time() - WINDOW_DAYS * 86400)
    db, gdb = os.path.join(DATA, "blackout.db"), os.path.join(DATA, "geo.db")

    def cur(k):
        x = wm.get(k)
        return (x[0] or "", x[1] or "") if isinstance(x, list) and len(x) == 2 else (cut, "")

    if os.path.exists(db):
        c = _ro(db)
        try:
            t, i = cur("clusters")
            t = max(t, cut)
            d["clusters"] = [dict(r) for r in c.execute(
                "SELECT * FROM clusters WHERE (COALESCE(updated, first_seen) > ? OR (COALESCE(updated, first_seen) = ? AND cluster_id > ?)) "
                "ORDER BY COALESCE(updated, first_seen), cluster_id LIMIT ?",
                (t, t, i, LIMITS["clusters"]))]
            t, i = cur("alerts")
            t = max(t, cut)
            d["alerts"] = [dict(r) for r in c.execute(
                "SELECT * FROM alerts WHERE (first_seen > ? OR (first_seen = ? AND id > ?)) ORDER BY first_seen, id LIMIT ?",
                (t, t, i, LIMITS["alerts"]))]
            sc = wm.get("scans") if isinstance(wm.get("scans"), int) else None
            if sc is not None:
                d["scans"] = [dict(r) for r in c.execute("SELECT * FROM scans WHERE id > ? ORDER BY id LIMIT ?", (sc, LIMITS["scans"]))]
            else:
                d["scans"] = [dict(r) for r in c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1")]
        finally:
            c.close()
    if os.path.exists(gdb):
        try:
            g = _ro(gdb)
            try:
                t, i = cur("geo")
                d["geo"] = [dict(r) for r in g.execute(
                    "SELECT * FROM geo WHERE (geocoded_at > ? OR (geocoded_at = ? AND id > ?)) ORDER BY geocoded_at, id LIMIT ?",
                    (t, t, i, LIMITS["geo"]))]
            finally:
                g.close()
        except sqlite3.Error:
            d["geo"] = []
    return d


def _n(d):
    return sum(len(d.get(k) or []) for k in LIMITS)


def push_once(cl, d):
    body = gzip.compress(json.dumps(d, separators=(",", ":"), default=str).encode(), 6)
    code, resp = cl.req("POST", "/internal/rt/push", body, timeout=60, ctype="application/gzip")
    try:
        j = json.loads(resp or b"{}")
    except Exception:
        j = {}
    return code, j, len(body)


def push_new(cl, state, why="scan"):
    sent = 0
    for _ in range(12):
        if state.get("wm") is None:
            code, j, _ = push_once(cl, {"v": VERSION})
            if code != 200:
                raise RuntimeError(f"rt/push HTTP {code}: {str(j.get('error') or '')[:120]}")
            state["wm"] = j.get("wm") or {}
        d = delta(state["wm"])
        n = _n(d)
        if not n:
            break
        code, j, size = push_once(cl, d)
        if code != 200:
            raise RuntimeError(f"rt/push HTTP {code}: {str(j.get('error') or '')[:120]}")
        state["wm"] = j.get("wm") or state["wm"]
        sent += n
        log(f"{why}: sent {n} rows ({len(d.get('clusters') or [])} clusters, "
            f"{len(d.get('alerts') or [])} alerts, {len(d.get('geo') or [])} places, "
            f"{len(d.get('scans') or [])} scans; {size // 1024} KB) -> site new={j.get('new', 0)}")
        if n < 50:
            break
    return sent


# --------------------------------------------------------------------------- status (secret-free; feed-health reads last_scan from the site after rt/push)
def last_scan_finished():
    p = os.path.join(DATA, "blackout.db")
    if not os.path.exists(p):
        return None
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
        try:
            r = c.execute("SELECT finished FROM scans WHERE finished IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            return r[0] if r else None
        finally:
            c.close()
    except sqlite3.Error:
        return None


def write_status(**extra):
    info = {
        "ok": True,
        "node": "render-scanner-worker",
        "version": VERSION,
        "last_scan": last_scan_finished(),
        "rss_mb": rss_mb(),
        "peak_rss_mb": peak_rss_mb(),
        "interval_minutes": INTERVAL_MIN,
        "seeded": os.path.exists(SEED_MARK),
        "at": iso(),
    }
    info.update(extra)
    tmp = STATUS_PATH + ".tmp"
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(info, f, indent=1)
        os.replace(tmp, STATUS_PATH)
    except OSError as ex:
        log(f"status write failed: {type(ex).__name__}")
    return info


# --------------------------------------------------------------------------- one cycle
def run_scan():
    """Import and run the existing scanner.scan(). Does not edit scanner.py."""
    if BASE not in sys.path:
        sys.path.insert(0, BASE)
    import scanner
    return scanner.scan("scheduled")


def run_geocode():
    if BASE not in sys.path:
        sys.path.insert(0, BASE)
    import geo
    return geo.run(trigger="worker", max_seconds=120)


def failed_sources(result):
    """Names of sources that raised during the last scan, if the scanner reported them."""
    if not isinstance(result, dict):
        return []
    # scan() returns counts only; source_health is in the DB.
    p = os.path.join(DATA, "blackout.db")
    if not os.path.exists(p):
        return []
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
        try:
            rows = c.execute(
                "SELECT name, error FROM source_health WHERE ok = 0 AND error IS NOT NULL ORDER BY name"
            ).fetchall()
            return [{"name": n, "error": (e or "")[:160]} for n, e in rows]
        finally:
            c.close()
    except sqlite3.Error:
        return []


def cycle(cl, state):
    t0 = time.time()
    if not state.get("seeded"):
        seed = seed_from_site(cl)
        link_dbs()
        state["seeded"] = True
        log(f"seed {seed['status']}: {', '.join(seed['files'])}")
    link_dbs()
    scan = run_scan()
    log(f"scan {scan.get('status')}: fetched={scan.get('fetched')} new={scan.get('new')} "
        f"ok_sources={scan.get('ok_sources')} failed_sources={scan.get('failed_sources')} rss={rss_mb()} MB")
    if STOP.is_set():
        return scan
    try:
        g = run_geocode()
        log(f"geocode: scanned={g.get('scanned')} geocoded={g.get('geocoded')} located={g.get('located')} "
            f"nominatim={g.get('nominatim_calls')} s={g.get('seconds')}")
    except Exception as ex:
        log(f"geocode error: {type(ex).__name__}: {str(ex)[:160]}")
        g = {"error": type(ex).__name__}
    sent = 0
    if state.get("seeded"):
        sent = push_new(cl, state, why="scan")
    failed = failed_sources(scan)
    if failed:
        log(f"source failures this pass: {len(failed)} (names only in status)")
    write_status(scan=scan.get("status"), fetched=scan.get("fetched"), new=scan.get("new"),
                 ok_sources=scan.get("ok_sources"), failed_source_count=scan.get("failed_sources"),
                 failed_source_names=[x["name"] for x in failed],
                 pushed_rows=sent, geocode_error=g.get("error"), seconds=round(time.time() - t0, 1))
    return scan


# --------------------------------------------------------------------------- main loop
def _stop(signum, _frame):
    log(f"got signal {signum}; will exit after the current step")
    STOP.set()


def prepare_env():
    os.environ["X_READS_OFF"] = "1"
    os.environ.setdefault("BN_NO_STREAMWATCH", "1")
    os.environ.setdefault("BN_NO_SNAPSHOTS", "1")
    os.environ.setdefault("NEWSLETTER_NO_WORKER", "1")
    # Do not inherit or request X API keys; if a platform copy set them, drop them here.
    for k in list(os.environ):
        if k.startswith("X_API") or k.startswith("X_ACCESS") or k == "X_BEARER_TOKEN":
            os.environ.pop(k, None)


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    prepare_env()
    os.makedirs(DATA, exist_ok=True)
    drop_privs()
    link_dbs()
    log("starting " + json.dumps(env_report()))
    if not secret_ok():
        write_status(error="BN_SYNC_SECRET missing or too short")
        log("BN_SYNC_SECRET is missing or shorter than 32 characters. "
            "Set it on this worker in the Render dashboard (copy from the web service; do not paste it into chat). Exiting.")
        return 2
    cl = client()
    state = {"wm": None, "seeded": os.path.exists(SEED_MARK) and os.path.exists(os.path.join(DATA, "blackout.db"))}
    # Try to seed before the first scan so clustering uses the live 12-hour window.
    if not state["seeded"]:
        for attempt in range(8):
            if STOP.is_set():
                return 0
            try:
                seed = seed_from_site(cl)
                link_dbs()
                state["seeded"] = True
                log(f"seed {seed['status']}: {', '.join(seed['files'])}")
                break
            except Exception as ex:
                log(f"seed attempt {attempt + 1} failed: {type(ex).__name__}: {str(ex)[:200]}")
                STOP.wait(min(60, 5 * (attempt + 1)))
        if not state["seeded"]:
            write_status(error="seed failed; not pushing until the live DBs can be pulled")
            log("could not seed from the site; will retry each cycle and will not push until it succeeds")
    while not STOP.is_set():
        t0 = time.time()
        try:
            if not state["seeded"]:
                seed = seed_from_site(cl)
                link_dbs()
                state["seeded"] = True
                log(f"seed {seed['status']}: {', '.join(seed['files'])}")
            cycle(cl, state)
        except Exception as ex:
            traceback.print_exc()
            log(f"cycle error: {type(ex).__name__}: {str(ex)[:200]}")
            write_status(error=f"{type(ex).__name__}: {str(ex)[:200]}")
        wait = max(5, INTERVAL_MIN * 60 - (time.time() - t0))
        log(f"sleeping {int(wait)} s (interval {INTERVAL_MIN} min); rss={rss_mb()} MB peak={peak_rss_mb()} MB")
        STOP.wait(wait)
    log("exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
