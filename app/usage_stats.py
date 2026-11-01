"""Privacy-safe traffic counters for the public node (Render). Aggregates only, kept in memory and in BN_STATE_DIR:
per UTC day -> page views, unique visitors (count of a keyed daily-rotating hash; the hashes themselves never leave this
process), requests per dashboard data module ("top tabs" proxy), and responses by status class (error rates).
No IPs, user agents, paths with query strings or per-visitor rows are kept or sent. The box pulls snapshot() over the signed
reports sync (/api/reports/pull) and stores it in reports.db (usage table). Counting starts when this node boots, so a
restart begins a new segment (unique-visitor counts of segments are summed by the box: an upper bound).

Visitor counter fix (analytics, 2026-11-01):
- Page views: only GETs whose Accept header asks for text/html (browsers), status < 400, known pages. /vsubs is not a page.
- Unique visitors: counted only from the JS beacon (POST /api/hit, see beacon()), so page-only checkers (curl, link checkers,
  scanners, previews) never become "visitors". Hash = HMAC(daily random key, day|IP|User-Agent), first 8 bytes, memory only.
- Internal traffic (our own bots, the owner, the team) is dropped before anything else and only counted in internal_requests:
  header X-BN-Internal equal to env BN_INTERNAL_TOKEN (check skipped when the env var is unset), a User-Agent containing
  BlackoutNetwork-Internal, the staff cookie bn_internal=1 (set by /?internal=1, cleared by /?internal=0), or that query itself.
- Do Not Track / Global Privacy Control: not counted at all (unchanged).
- export_state()/import_state(): today's key + visitor-hash set for the zero-downtime deploy handoff (render_app.py), so a
  visitor seen by the old instance is not counted again by the new one. Counters are NOT copied (the box sums segments)."""
import os, re, json, time, hmac, hashlib, secrets, threading

STATE = os.environ.get("BN_STATE_DIR", "/tmp/bn_state")
FILE = os.path.join(STATE, "usage_stats.json")
BOOT = secrets.token_hex(6)
_lock = threading.Lock()
_days = {}          # day -> {"page_views", "requests", "status": {"2xx":..}, "modules": {..}, "pages": {..}, "_v": set()}
_last_save = [0.0]
SKIP = ("/internal/", "/healthz", "/api/reports/pull", "/api/reports/ack", "/api/reports/status", "/api/status", "/api/sync_status",
        "/api/hit", "/api/email-events")   # /api/hit is accounted for by beacon()
PAGES = {"/": "dashboard", "/index.html": "dashboard", "/scoring": "scoring", "/about/scoring": "scoring", "/newsletter": "newsletter",
         "/sources": "sources", "/report-status": "report_status", "/guides": "guides", "/maps": "maps",
         "/stats": "stats", "/midterms": "midterms", "/privacy": "privacy", "/tos": "tos", "/alerts": "alerts"}
EXACT = {"/social": "social"}   # t385: /social/thumb/* are images, not page views
STORY_RE = re.compile(r"^/(wire|story)/([A-Za-z0-9_\-]{1,64})/?$")   # t385: per-story page views (top stories on /stats)
MAX_KEYS = 400
_SALTS = {}   # t385: day -> random key; only today's key exists, so visitor hashes cannot be linked across days
BOT_RE = re.compile(r"(?i)bot|crawl|spider|slurp|curl|wget|python-|go-http|headless|monitor|uptime|render|blackout-render-sync"
                    r"|facebookexternalhit|meta-external|ChatGPT-User|OAI-Search|Perplexity|Google-InspectionTool|Google-Extended|GoogleOther"
                    r"|Google-Read-Aloud|FeedFetcher|Lighthouse|PageSpeed|PTST|GTmetrix|Pingdom|StatusCake|Site24x7|Checkly|HetrixTools"
                    r"|axios|node-fetch|undici|okhttp|Java/|aiohttp|httpx|Scrapy|HeadlessChrome|PhantomJS|Puppeteer|Playwright|Selenium|webdriver"
                    r"|libwww|lwp-|Apache-HttpClient|reqwest|Dart/|Deno/|Bun/|http_request|HTTPie|PostmanRuntime|Insomnia|Wappalyzer"
                    r"|preview|Embedly|Iframely|WhatsApp|SkypeUriPreview|Slack-ImgProxy|Mastodon|Bluesky|Cardyb"
                    r"|Bytespider|ClaudeBot|Claude-User|anthropic-ai|cohere-ai|Amazonbot|Applebot|Diffbot|Timpibot|ImagesiftBot|scan|fetch|archive")
INTERNAL_UA = "BlackoutNetwork-Internal"
INTERNAL_ENV = "BN_INTERNAL_TOKEN"       # Render env var (and box env); unset -> header check skipped
INTERNAL_COOKIE = "bn_internal"
INTERNAL_COOKIE_MAX_AGE = 365 * 86400
_INT_Q = re.compile(r"(?:^|&)internal=([01])(?:&|$)")
_INT_C = re.compile(r"(?:^|;)\s*bn_internal=1(?:;|$)")
# Beacon rate limit (per visitor hash, and overall): a visitor counts once per day anyway; this only bounds abuse/CPU.
HIT_PER_MIN = 30
HIT_GLOBAL_PER_MIN = 3000
_rl = {}                  # visitor hash -> [window_start, n]   (memory only, pruned every minute)
_rl_g = [0.0, 0]

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

def _h(headers, k):
    try: return str((headers.get(k) if headers is not None else "") or "")
    except Exception: return ""

def internal_query(path):
    """'1' / '0' when the URL carries ?internal=1 / ?internal=0 (staff link), else None."""
    q = (path or "").split("?", 1)[1] if "?" in (path or "") else ""
    m = _INT_Q.search(q.split("#", 1)[0])
    return m.group(1) if m else None

def internal_cookie_header(path):
    """Set-Cookie value for the staff link, or None. First-party, 1 year; readable by our GA4 snippet (traffic_type=internal)."""
    v = internal_query(path)
    if v == "1": return f"{INTERNAL_COOKIE}=1; Max-Age={INTERNAL_COOKIE_MAX_AGE}; Path=/; Secure; SameSite=Lax"
    if v == "0": return f"{INTERNAL_COOKIE}=; Max-Age=0; Path=/; Secure; SameSite=Lax"
    return None

def internal_reason(path="", ua="", headers=None):
    """Why a request is our own traffic ('header', 'ua', 'cookie', 'link'), or '' for public traffic."""
    tok = os.environ.get(INTERNAL_ENV, "").strip()
    if tok:
        got = _h(headers, "X-BN-Internal").strip()
        if got and hmac.compare_digest(got.encode(), tok.encode()): return "header"
    if INTERNAL_UA.lower() in (ua or "").lower(): return "ua"
    if internal_query(path) is not None: return "link"
    if _INT_C.search(_h(headers, "Cookie")): return "cookie"
    return ""

def _day(day):
    return _days.setdefault(day, {"page_views": 0, "requests": 0, "bot_requests": 0, "internal_requests": 0, "status": {}, "modules": {},
                                  "pages": {}, "uniques": 0, "_v": set()})

def _privacy_off(headers):
    return headers is not None and (_h(headers, "DNT").strip() == "1" or _h(headers, "Sec-GPC").strip() == "1")

def _wants_html(headers):
    return "text/html" in _h(headers, "Accept").lower()

def record(path, code, method="GET", ip="", ua="", ref="", headers=None):
    p = (path or "").split("?", 1)[0]
    if any(p.startswith(s) for s in SKIP): return
    day = time.strftime("%Y-%m-%d", time.gmtime())
    why = internal_reason(path, ua, headers)
    if why:   # our own tools, the owner, the team: dropped, only counted here
        with _lock:
            d = _day(day); d["internal_requests"] = d.get("internal_requests", 0) + 1
            ib = d.setdefault("internal_by", {}); ib[why] = ib.get(why, 0) + 1
        return
    if _privacy_off(headers):
        return   # t385: Do Not Track / Global Privacy Control -> not counted at all
    with _lock:
        d = _day(day)
        cls = f"{int(code) // 100}xx"; d["status"][cls] = d["status"].get(cls, 0) + 1; d["requests"] += 1
        if not ua or BOT_RE.search(ua): d["bot_requests"] += 1; return
        page = _page(p)
        is_view = method == "GET" and page and int(code) < 400 and _wants_html(headers)
        if is_view:
            if ":" in page and page not in d["pages"] and len(d["pages"]) >= MAX_KEYS: page = page.split(":", 1)[0] + ":_other"
            d["page_views"] += 1; d["pages"][page] = d["pages"].get(page, 0) + 1
            cc = _h(headers, "CF-IPCountry").strip().upper()
            if re.fullmatch(r"[A-Z]{2}", cc) and cc not in ("XX", "T1"):   # country code only when the CDN supplies it; never looked up from the IP
                d.setdefault("countries", {}); d["countries"][cc] = d["countries"].get(cc, 0) + 1
            # growth (Nov 1): aggregate campaign + referrer-site counts only (no per-visitor rows)
            u = re.search(r"[?&]utm_source=([A-Za-z0-9_.-]{1,24})", path or "")
            if u: d.setdefault("utm", {}); k = u.group(1).lower(); d["utm"][k] = d["utm"].get(k, 0) + 1
            rh = re.match(r"^https?://([^/:?#]{1,80})", ref or "")
            if rh:
                h = rh.group(1).lower().removeprefix("www.")
                if not h.endswith("blackout.network"):
                    d.setdefault("referrers", {}); rf = d["referrers"]
                    if h in rf or len(rf) < 60: rf[h] = rf.get(h, 0) + 1
        elif method == "GET" and page and int(code) < 400:
            d["nonhtml_page_gets"] = d.get("nonhtml_page_gets", 0) + 1   # checkers/fetchers that don't ask for HTML
        m = re.match(r"^/api/([a-z_]+)", p)
        if m and m.group(1) not in ("report", "reports"): d["modules"][m.group(1)] = d["modules"].get(m.group(1), 0) + 1
        for k in sorted(_days)[:-14]: _days.pop(k, None)
    if time.time() - _last_save[0] > 60: save()

def _vhash(day, ip, ua):
    return hmac.new(_salt(day), f"{day}|{ip}|{ua}".encode(), hashlib.sha256).digest()[:8]

def beacon(ip="", ua="", headers=None, raw=b""):
    """POST /api/hit from the page's script. Counts a unique visitor once per day per (IP, User-Agent) hash.
    Returns a short status string (for tests/logs; never includes the IP or the hash)."""
    day = time.strftime("%Y-%m-%d", time.gmtime())
    why = internal_reason("", ua, headers)
    if why:
        with _lock:
            d = _day(day); d["internal_requests"] = d.get("internal_requests", 0) + 1
            ib = d.setdefault("internal_by", {}); ib[why] = ib.get(why, 0) + 1
        return "internal"
    if _privacy_off(headers): return "dnt"
    sfs = _h(headers, "Sec-Fetch-Site").strip().lower()
    if sfs and sfs not in ("same-origin", "none"): return "cross_site"
    if not ua or BOT_RE.search(ua):
        with _lock: d = _day(day); d["bot_requests"] += 1
        return "bot"
    try:
        b = json.loads((raw or b"{}")[:512] or b"{}")
        pg = str(b.get("p") or "") if isinstance(b, dict) else ""
    except Exception: pg = ""
    if not pg.startswith("/") or len(pg) > 300: return "bad"
    now = time.time()
    with _lock:
        if now - _rl_g[0] >= 60: _rl_g[0], _rl_g[1] = now, 0; _rl.clear()
        _rl_g[1] += 1
        d = _day(day)
        if _rl_g[1] > HIT_GLOBAL_PER_MIN: d["beacon_limited"] = d.get("beacon_limited", 0) + 1; return "limited"
        v = _vhash(day, ip, ua)
        w = _rl.get(v)
        if w is None: w = _rl[v] = [now, 0]
        w[1] += 1
        if w[1] > HIT_PER_MIN: d["beacon_limited"] = d.get("beacon_limited", 0) + 1; return "limited"
        d["beacons"] = d.get("beacons", 0) + 1
        if v in d["_v"]: return "seen"
        d["_v"].add(v); d["uniques"] += 1
    if time.time() - _last_save[0] > 60: save()
    return "new"

def export_state():
    """For the deploy handoff only (signed, instance to instance): today's key and visitor-hash set. Never public."""
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _lock:
        k = _SALTS.get(day); d = _days.get(day)
        if k is None or not d: return None
        return {"v": 1, "day": day, "key": k.hex(), "hashes": [h.hex() for h in d["_v"]][:200000]}

def import_state(st):
    """New instance side: adopt the old instance's key + hashes for today, so returning visitors are not double counted.
    Counters stay at 0 (this instance is a new segment; the box sums segments)."""
    try:
        if not st or st.get("v") != 1: return 0
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if st.get("day") != day: return 0
        key = bytes.fromhex(st["key"]); hs = {bytes.fromhex(h) for h in st.get("hashes", []) if len(h) == 16}
        if len(key) != 32: return 0
        with _lock:
            cur = _SALTS.get(day); d = _day(day)
            if cur is not None and cur != key: d["_v"] = set()   # hashes made with our own key are useless with the new key
            _SALTS.clear(); _SALTS[day] = key; d["_v"] |= hs
        return len(hs)
    except Exception: return 0

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
