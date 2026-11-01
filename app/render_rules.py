"""Shared rules for the Render deployment (used by render_package.py, render_sync.py and render_app.py).
Decides which files are (a) baked into the public image, (b) pushed from the box to Render as live data,
(c) owned by Render (written by the public: votes, newsletter signups) and mirrored back to the box.
Generic on purpose: new add-on modules (*.py), *_static/ dirs and *.db files are picked up automatically.
Secrets never qualify: anything matching SECRET_PATTERNS is refused by every rule here."""
import fnmatch, os, re

BASE = "/workspace/blackout"

# Never packaged, never synced (checked first, wins over everything).
SECRET_PATTERNS = ["ADMIN_PASSCODE*", "notify_settings.json*", "push.env*", "*.env", "*.env.*", ".env*", "*secret*", "*credential*",
                   "*.pem", "*.key", "id_rsa*", "PUBLIC_URL.txt", "render_sync.env*", "cloudflared", "run_tunnel.sh", "*.pid",
                   "private_*"]   # owner-private location data (private_location.json, private_maps_index.json): box-local only

def _private_files():
    """Files listed in the box-only private maps index (the owner's home-area maps) are treated like secrets: never packaged or synced."""
    try:
        import json
        return {"static/maps/" + m["file"] for m in json.load(open(os.path.join(BASE, "static", "maps", "private_maps_index.json")))["maps"]}
    except Exception: return set()
_PRIV = _private_files()
# Never packaged (bulky, box-only, or backups).
EXCLUDE_PATTERNS = ["*_backup*", "*.pre_*", "*_pre_*", "*_v1_backup*", "__pycache__", "*.pyc", "logs", "reports", "newsletter_outbox",
                    "render_mirror", "snapshots", "video_subs", "*.db-wal", "*.db-shm", "*.db-journal", "*.tmp", "*.part", ".git",
                    "archive", "*.m3u8", "*.ts", "*.aac", "*.mp4", "*.mkv", "*.webm", "*.wav", "*.mp3", "*.m4a", "tests/tmp*", ".bn_sync*"]
MAX_IMAGE_FILE = 20 * 1024 * 1024        # files above this stay box-only (e.g. 50 MB USGS topo PDFs)

# Written by the public on Render. Render is the source of truth while it runs; the box mirrors them to render_mirror/
# and restores them after a Render restart (free-tier disk is wiped on spin-down/redeploy).
RENDER_OWNED = [x for x in os.environ.get("BN_RENDER_OWNED", "votes.db,newsletter.db,source_submissions.db,webpush.db").split(",") if x]

# Box -> Render live data. Top-level *.db (snapshotted read-only), selected JSON state and generated media dirs.
SYNC_DIRS = ["snapshots", "static/vsubs", "video_subs", "static/social"]   # static/social: story thumbnails (t303)
SYNC_JSON = ["page_data.json", "config.json", "keywords.json", "arcs_settings.json", "tips.json", "newsletter_config.json",
             "translate_glossary.json", "translate_langs.json", "sources*.json", "youtube*.json",
             "social_*.json", "webpush_config.json", "webpush_dead.json"]   # social_stories/social_youtube/social_x_posts.json (t303)
# Code/static that hot-reloads on Render (add-ons re-import on mtime change; dashboard.html is read per request).
CODE_GLOBS = ["*.py", "*.html", "*.css", "*.js", "*_static/*", "games_static/*", "static/theme.css", "static/img/*", "static/pwa/*", "static/guides/*",
              "heatmap_data/*.json", "newsletter_disposable.txt"]
SNAPSHOT_MAX_AGE_DAYS = float(os.environ.get("BN_SYNC_SNAPSHOT_DAYS", "7"))

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*(/[A-Za-z0-9_][A-Za-z0-9_.\-]*)*$")

def _match(rel, pats):
    parts = rel.split("/")
    for p in pats:
        if fnmatch.fnmatch(rel, p) or any(fnmatch.fnmatch(x, p) for x in parts): return True
    return False

def is_secret(rel): return _match(rel, SECRET_PATTERNS) or rel in _PRIV

def safe_rel(rel):
    return bool(rel) and NAME_RE.match(rel) is not None and ".." not in rel.split("/") and not rel.startswith("/")

def image_include(rel, size):
    """Files baked into the Docker image / git repo."""
    if not safe_rel(rel) or is_secret(rel) or _match(rel, EXCLUDE_PATTERNS): return False
    if size > MAX_IMAGE_FILE: return False
    if rel.endswith(".db"): return rel == "resources_pois.db"      # static OSM index; live DBs arrive by sync
    if rel.startswith("tests/"): return rel.endswith(".py")
    return True

def is_db(rel): return "/" not in rel and rel.endswith(".db") and not _match(rel, EXCLUDE_PATTERNS) and not is_secret(rel)

def sync_kind(rel):
    """'db' | 'owned' | 'data' | 'code' | None -- what a path is allowed to be in a box->Render push."""
    if not safe_rel(rel) or is_secret(rel): return None
    if rel in RENDER_OWNED: return "owned"
    if is_db(rel): return "db"
    if _match(rel, ["*_backup*", "*.pre_*", "*_pre_*", "__pycache__", "*.pyc", "*.tmp", "*.db-wal", "*.db-shm"]): return None
    if "/" not in rel and any(fnmatch.fnmatch(rel, p) for p in SYNC_JSON): return "data"
    if any(rel.startswith(d + "/") and rel.count("/") == d.count("/") + 1 for d in SYNC_DIRS): return "data"
    if "/" not in rel and rel.endswith(".py"): return "code"
    if any(fnmatch.fnmatch(rel, p) for p in CODE_GLOBS) and rel.count("/") <= 2: return "code"
    return None

# ---------------------------------------------------------------- visitor problem reports (2026-10-31, reports.py)
# Box-only parts (the report store with every visitor's captured context, the admin/agent view, CLI, sync, stats, impact reports,
# usage log) are treated like secrets: never packaged, never pushed, never accepted by Render. The public node only runs reports.py,
# usage_stats.py and reports_static/ from the scrubbed GitHub repo; its queue lives in BN_STATE_DIR, outside BASE.
REPORTS_BOX_ONLY = ["reports.db*", "reports_admin*", "reports_box*", "reports_cli*", "reports_sync*", "reports_stats*", "reports_config*",
                    "reports_impact", "reports_queue*", "report_queue*", "e2e_reports*", "usage_log*"]
SECRET_PATTERNS += [p for p in REPORTS_BOX_ONLY if p not in SECRET_PATTERNS]
if "NO_PUSH" in globals(): NO_PUSH |= {"reports.db"}
