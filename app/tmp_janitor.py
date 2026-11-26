"""Keep the Render instance's /tmp under its 2 GB eviction limit (Nov 25 2026).

Render evicted the public node four times on Nov 25 (2:34, 6:30, 8:00, 9:02 PM ET) with "Size of temporary storage
volume /tmp exceeded the limit of 2GB"; each eviction dropped the Wire data until the box re-synced. One daemon thread
(bn-tmp-janitor) measures /tmp every SWEEP_S seconds, logs the biggest top-level entries every LOG_S seconds, deletes
stale sync/handoff archives and orphaned *.tmp files, and when /tmp is over SOFT_MB trims rebuildable caches
(card/OG/photo/weather/crime caches) oldest first down to TARGET_MB. It never deletes databases, WAL/SHM files,
secrets or the sync manifest."""
import os, re, time, threading

ROOT = os.environ.get("BN_TMP_ROOT", "/tmp")
STATE = os.environ.get("BN_STATE_DIR", "/tmp/bn_state")
SOFT_MB = int(os.environ.get("BN_TMP_SOFT_MB", "1200"))
TARGET_MB = int(os.environ.get("BN_TMP_TARGET_MB", "800"))
SWEEP_S = int(os.environ.get("BN_TMP_SWEEP_S", "60"))
LOG_S = int(os.environ.get("BN_TMP_LOG_S", "600"))
ARCHIVE_AGE_S = 420          # a push/handoff/export archive older than this is never still in use (box push timeout 300 s)
TMP_AGE_S = 1800
# Rebuildable caches only (each module re-creates its directory and re-fetches on a miss).
CACHE_DIRS = ("bn-og-cache", "bn_card_photo", "bn-story-photos", "bn_wxcache", "bn_crime_news", "bn_backfill_cache",
              "bn_starlink", "bn_launch", "gov_img")
CACHE_PREFIXES = ("nlpreview_", "bnbrand_", "bndec_", "vs_", "bnstream", "bn_bf_")
KEEP_SUFFIXES = (".db", ".db-wal", ".db-shm", "-wal", "-shm", "-journal")
STATS = {"sweeps": 0, "deleted": 0, "freed_mb": 0.0, "last_mb": None, "top": [], "err": ""}
_T = {"thread": None, "logged": 0.0}

def _keep(path):
    p = path.replace("\\", "/")
    if p.endswith(KEEP_SUFFIXES) or "/secrets" in p or p.endswith("manifest.json"):
        return True
    return False

def _walk(top):
    """(size_bytes, [(mtime, size, path)]) for regular files under top; never follows symlinks."""
    total, files = 0, []
    try:
        st = os.lstat(top)
    except OSError:
        return 0, files
    if not os.path.isdir(top) or os.path.islink(top):
        return st.st_size, [(st.st_mtime, st.st_size, top)]
    for dp, dns, fns in os.walk(top, followlinks=False):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                s = os.lstat(fp)
            except OSError:
                continue
            total += s.st_size; files.append((s.st_mtime, s.st_size, fp))
    return total, files

def _rm(fp, size):
    try:
        os.unlink(fp); STATS["deleted"] += 1; STATS["freed_mb"] += size / 1048576.0; return size
    except OSError:
        return 0

_SNAP_RE = re.compile(r"^tmp[a-z0-9_]{6,12}\.db$")

def _is_cache(name):
    return name in CACHE_DIRS or name.startswith(CACHE_PREFIXES)

def sweep(now=None):
    """One pass. Returns the /tmp size in MB after the pass."""
    now = now or time.time()
    try:
        entries = sorted(os.listdir(ROOT))
    except OSError:
        return None
    sizes, total, cache_files = {}, 0, []
    for name in entries:
        top = os.path.join(ROOT, name)
        sz, files = _walk(top)
        for mt, s, fp in files:
            base = os.path.basename(fp)
            age = now - mt
            stale_archive = fp.endswith((".tgz", ".tar.gz")) and age > ARCHIVE_AGE_S and (fp.startswith(STATE) or os.path.dirname(fp) == ROOT)
            stale_tmp = base.endswith(".tmp") and age > TMP_AGE_S
            # handoff_db.snapshot_sqlite temp copies (mkstemp "tmpXXXXXXXX.db") left by a failed snapshot; never report_queue.db etc.
            stale_snap = (os.path.dirname(fp) == STATE.rstrip("/") and _SNAP_RE.match(base) is not None and age > ARCHIVE_AGE_S)
            if stale_snap:
                sz -= _rm(fp, s); continue
            if (stale_archive or stale_tmp) and not _keep(fp):
                sz -= _rm(fp, s); continue
            if _is_cache(name) and not _keep(fp):
                cache_files.append((mt, s, fp))
        sizes[name] = sz; total += sz
    mb = total / 1048576.0
    if mb > SOFT_MB and cache_files:
        cache_files.sort()                       # oldest first
        for mt, s, fp in cache_files:
            if total / 1048576.0 <= TARGET_MB:
                break
            got = _rm(fp, s); total -= got
            top = os.path.relpath(fp, ROOT).split(os.sep)[0]; sizes[top] = sizes.get(top, 0) - got
        mb = total / 1048576.0
    STATS["sweeps"] += 1; STATS["last_mb"] = round(mb, 1)
    STATS["top"] = [(k, round(v / 1048576.0, 1)) for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:8]]
    try:   # what is inside the state dir (sync archives, queues): the biggest 5 files
        st = os.path.basename(STATE.rstrip("/"))
        _, sf = _walk(STATE)
        STATS["state_top"] = [(os.path.relpath(fp, STATE), round(sz / 1048576.0, 1), int(now - mt))
                              for mt, sz, fp in sorted(sf, key=lambda x: -x[1])[:5] if os.path.exists(fp)]
    except Exception:
        STATS["state_top"] = []
    return mb

def _tmp_sweep():
    while True:
        try:
            mb = sweep()
            if mb is not None and (time.time() - _T["logged"] >= LOG_S or mb > SOFT_MB):
                _T["logged"] = time.time()
                fs = ""
                try:   # used space on the /tmp filesystem; far above the file total means deleted-but-open files
                    import shutil
                    if os.path.ismount(ROOT): fs = f"; fs used {shutil.disk_usage(ROOT).used / 1048576.0:.0f} MB"
                except Exception:
                    pass
                print(f"tmp_janitor: /tmp {mb:.0f} MB{fs}; top {STATS['top']}; deleted {STATS['deleted']} files "
                      f"({STATS['freed_mb']:.0f} MB) since boot; state {STATS.get('state_top')}", flush=True)
        except Exception as ex:   # never let the janitor take the node down
            STATS["err"] = str(ex)[:200]
        time.sleep(SWEEP_S)

def start():
    t = _T["thread"]
    if t and t.is_alive():
        return t
    t = threading.Thread(target=_tmp_sweep, name="bn-tmp-janitor", daemon=True)
    t.start(); _T["thread"] = t
    return t
