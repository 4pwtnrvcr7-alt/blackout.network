"""Privacy-safe traffic counters for the public node (Render). Aggregates only, kept in memory and in BN_STATE_DIR:
per UTC day -> page views, unique visitors (count of a keyed daily-rotating hash; the hashes themselves never leave this
process), requests per dashboard data module ("top tabs" proxy), and responses by status class (error rates).
No IPs, user agents, paths with query strings or per-visitor rows are kept or sent. The box pulls snapshot() over the signed
reports sync (/api/reports/pull) and stores it in reports.db (usage table). Counting starts when this node boots, so a
restart begins a new segment (unique-visitor counts of segments are summed by the box: an upper bound)."""
import os, re, json, time, hmac, hashlib, secrets, threading

STATE = os.environ.get("BN_STATE_DIR", "/tmp/bn_state")
FILE = os.path.join(STATE, "usage_stats.json")
BOOT = secrets.token_hex(6)
_lock = threading.Lock()
_days = {}          # day -> {"page_views", "requests", "status": {"2xx":..}, "modules": {..}, "pages": {..}, "_v": set()}
_last_save = [0.0]
SKIP = ("/internal/", "/healthz", "/api/reports/pull", "/api/reports/ack", "/api/reports/status", "/api/status", "/api/sync_status")
PAGES = {"/": "dashboard", "/index.html": "dashboard", "/scoring": "scoring", "/about/scoring": "scoring", "/newsletter": "newsletter",
         "/sources": "sources", "/report-status": "report_status", "/guides": "guides", "/maps": "maps", "/vsubs": "video_subs",
         "/stats": "stats", "/midterms": "midterms", "/privacy": "privacy", "/tos": "tos", "/alerts": "alerts"}
EXACT = {"/social": "social"}   # t385: /social/thumb/* are images, not page views
STORY_RE = re.compile(r"^/(wire|story)/([A-Za-z0-9_\-]{1,64})/?$")   # t385: per-story page views (top stories on /stats)
MAX_KEYS = 400
_SALTS = {}   # t385: day -> random key; only today's key exists, so visitor hashes cannot be linked across days
BOT_RE = re.compile(r"(?i)bot|crawl|spider|slurp|curl|wget|python-|go-http|headless|monitor|uptime|render|blackout-render-sync")

def _load():
    try:
        d = json.load(open(FILE))
        if d.get("boot") == BOOT:
            for k, v in d.get("days", {}).items(): _days[k] = {**v, "_v": set()}
    except Exception: pass

def _salt(day):
    k = _SALTS.get(day)
    if k is None:
        _SALTS.clear(); k = _SALTS[day] = secrets.token_bytes(32)   # new day: the old key is dropped and old hash sets are emptied
        for dd, v in _days.items():
            if dd != day: v["_v"] = set()
    return k

def _page(p):
    m = STORY_RE.match(p)
    if m: return f"{m.group(1)}:{m.group(2)}"
    if p in EXACT: return EXACT[p]
    return PAGES.get(p) or next((v for k, v in PAGES.items() if k != "/" and p.startswith(k + "/")), None)

def record(path, code, method="GET", ip="", ua="", ref="", headers=None):
    p = (path or "").split("?", 1)[0]
    if any(p.startswith(s) for s in SKIP): return
    if headers is not None and (str(headers.get("DNT", "")).strip() == "1" or str(headers.get("Sec-GPC", "")).strip() == "1"):
        return   # t385: Do Not Track / Global Privacy Control -> not counted at all
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _lock:
        d = _days.setdefault(day, {"page_views": 0, "requests": 0, "bot_requests": 0, "status": {}, "modules": {}, "pages": {}, "uniques": 0, "_v": set()})
        cls = f"{int(code) // 100}xx"; d["status"][cls] = d["status"].get(cls, 0) + 1; d["requests"] += 1
        if not ua or BOT_RE.search(ua): d["bot_requests"] += 1; return
        page = _page(p)
        if method == "GET" and page and int(code) < 400:
            if ":" in page and page not in d["pages"] and len(d["pages"]) >= MAX_KEYS: page = page.split(":", 1)[0] + ":_other"
            d["page_views"] += 1; d["pages"][page] = d["pages"].get(page, 0) + 1
            cc = str((headers.get("CF-IPCountry") if headers is not None else "") or "").strip().upper()
            if re.fullmatch(r"[A-Z]{2}", cc) and cc not in ("XX", "T1"):   # country code only when the CDN supplies it; never looked up from the IP
                d.setdefault("countries", {}); d["countries"][cc] = d["countries"].get(cc, 0) + 1
            v = hmac.new(_salt(day), f"{day}|{ip}".encode(), hashlib.sha256).digest()[:8]
            if v not in d["_v"]: d["_v"].add(v); d["uniques"] += 1
        if method == "GET" and page and int(code) < 400:   # growth (Nov 1): aggregate campaign + referrer-site counts only (no per-visitor rows)
            u = re.search(r"[?&]utm_source=([A-Za-z0-9_.-]{1,24})", path or "")
            if u: d.setdefault("utm", {}); k = u.group(1).lower(); d["utm"][k] = d["utm"].get(k, 0) + 1
            rh = re.match(r"^https?://([^/:?#]{1,80})", ref or "")
            if rh:
                h = rh.group(1).lower().removeprefix("www.")
                if not h.endswith("blackout.network"):
                    d.setdefault("referrers", {}); rf = d["referrers"]
                    if h in rf or len(rf) < 60: rf[h] = rf.get(h, 0) + 1
        m = re.match(r"^/api/([a-z_]+)", p)
        if m and m.group(1) not in ("report", "reports"): d["modules"][m.group(1)] = d["modules"].get(m.group(1), 0) + 1
        for k in sorted(_days)[:-14]: _days.pop(k, None)
    if time.time() - _last_save[0] > 60: save()

def snapshot():
    with _lock:
        return {"boot": BOOT, "since": _since, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "days": {k: {kk: vv for kk, vv in v.items() if kk != "_v"} for k, v in _days.items()}}
def save():
    _last_save[0] = time.time()
    try:
        os.makedirs(STATE, mode=0o700, exist_ok=True); tmp = FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(snapshot(), f)
        os.replace(tmp, FILE)
    except Exception: pass

_since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
_load()
