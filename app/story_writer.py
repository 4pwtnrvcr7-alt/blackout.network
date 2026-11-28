"""Instant story write-ups for rank 5+ Wire stories via the xAI API (Nov 21 2026, Matt 2:12 PM ET).

Runs on the Render web node as ONE background thread (never inside a request). Every few seconds it reads blackout.db
read-only (file:...?mode=ro) and queues each main-feed cluster with rank >= BN_WRITER_MIN_RANK that has no write-up yet
(new arrivals first, then a backfill of the last BN_WRITER_BACKFILL_H hours). For each job it fetches the cluster's own
source URLs (timeouts, size caps, public hosts only), sends the extracted text to the model with a strict grounding prompt,
validates the JSON against the desk brief v2 + Story v3 schema, checks the text (word rules, numbers and quotes must appear
in the sources, cited links must be ones we fetched), retries once, and stores the brief in story_writer.db.

Precedence (never overwrite the desk): a Story v3 brief file, a pushed desk brief / analyst note (story_reports.json notes or
alias) always win. The writer skips those clusters and story_v3.note_for() only falls back to a writer brief when neither
exists. Near-duplicates of a covered story alias to its brief instead of a new API call.

No images are generated: the page keeps the existing licensed / place-matched Wire images.

One write-up per story: no automatic rewrites when new sources arrive. Desk / Story v3 briefs always win.
New rank 5+ items stay off the Wire until the paid article is stored (a free template is still written in the
background). Existing visible items keep their template until the paid article is swapped in.

Env (all optional except the key):
  XAI_API_KEY               required; the writer stays idle without it (never logged or printed)
  BN_WRITER=0               kill switch
  BN_WRITER_MODEL           default grok-4.20-0309-non-reasoning
  BN_WRITER_API             default https://api.x.ai/v1
  BN_WRITER_MIN_RANK        default 5
  BN_WRITER_MAX_PER_HOUR    default 30 API write-ups per rolling hour
  BN_WRITER_DAILY_USD       default 0.25 (ET day, current model only); the writer pauses when the day's spend reaches it
  BN_WRITER_PRICE_IN/_OUT   USD per million tokens (default 1.25 / 2.50)
  BN_WRITER_BACKFILL_H      default 48
  BN_WRITER_POLL_S          default 10
  BN_WRITER_REWRITE=1       opt-in rewrites (off by default)
  BN_WRITER_REFRESH_MIN     only used if rewrites are on; default 0
  BN_WRITER_DB              default <app>/story_writer.db (a Render-owned DB: handed to the next instance on every deploy)
"""
from __future__ import annotations
import base64, hashlib, html, ipaddress, json, os, re, socket, sqlite3, sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    ET = timezone(timedelta(hours=-5))
UTC = timezone.utc
HERE = os.path.dirname(os.path.abspath(__file__))
DB_REL = "story_writer.db"

def _env(k, d): return (os.environ.get(k) or "").strip() or d
def _f(k, d):
    try: return float(_env(k, str(d)))
    except Exception: return float(d)
def cfg():
    return {"model": _env("BN_WRITER_MODEL", "grok-4.20-0309-non-reasoning"), "api": _env("BN_WRITER_API", "https://api.x.ai/v1").rstrip("/"),
            "min_rank": int(_f("BN_WRITER_MIN_RANK", 5)), "max_per_hour": int(_f("BN_WRITER_MAX_PER_HOUR", 30)),
            "daily_usd": _f("BN_WRITER_DAILY_USD", 0.25), "price_in": _f("BN_WRITER_PRICE_IN", 1.25), "price_out": _f("BN_WRITER_PRICE_OUT", 2.50),
            "backfill_h": _f("BN_WRITER_BACKFILL_H", 48), "poll_s": max(1.0, _f("BN_WRITER_POLL_S", 2)),
            "refresh_min": _f("BN_WRITER_REFRESH_MIN", 0), "db": _env("BN_WRITER_DB", os.path.join(HERE, DB_REL)),
            "blackout_db": _env("BN_WRITER_SOURCE_DB", os.path.join(HERE, "blackout.db")),
            "template_backfill_h": _f("BN_TEMPLATE_BACKFILL_H", 48)}
def key_set(): return bool((os.environ.get("XAI_API_KEY") or "").strip())
def enabled(): return _env("BN_WRITER", "1") != "0" and key_set()
def templates_on(): return _env("BN_TEMPLATES", "1") != "0"
def gate_wanted(): return templates_on() and _env("BN_PUBLISH_GATE", "1") != "0"
def api_enabled(): return enabled()
def rewrite_allowed(): return _env("BN_WRITER_REWRITE", "0") == "1"

def now(): return datetime.now(UTC)
def iso(d=None): return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")
def parse_t(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC)
    except Exception: return None
def et_day(d=None): return (d or now()).astimezone(ET).date().isoformat()
def log(*a): print("story_writer:", *a, flush=True)

# ---------------------------------------------------------------- store (story_writer.db)
_LK = threading.RLock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs(cid TEXT PRIMARY KEY, note TEXT, written_at TEXT, model TEXT, src_urls TEXT, alias_of TEXT,
  tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, usd REAL DEFAULT 0, rank INTEGER, title TEXT);
CREATE TABLE IF NOT EXISTS seen(cid TEXT PRIMARY KEY, first_seen TEXT, rank INTEGER, backfill INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT, reason TEXT, status TEXT, enq_at TEXT, arrived_at TEXT,
  started TEXT, finished TEXT, err TEXT, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, usd REAL DEFAULT 0,
  latency_s REAL, calls INTEGER DEFAULT 0, rank INTEGER, title TEXT);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS ix_jobs_cid ON jobs(cid);
CREATE TABLE IF NOT EXISTS spend(day TEXT PRIMARY KEY, usd REAL DEFAULT 0, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, calls INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ready(cid TEXT PRIMARY KEY, kind TEXT, tags TEXT, card_ok INTEGER DEFAULT 0, ready_at TEXT, title TEXT, rank INTEGER);
CREATE TABLE IF NOT EXISTS legacy(cid TEXT PRIMARY KEY, at TEXT);
CREATE TABLE IF NOT EXISTS held(cid TEXT PRIMARY KEY, since TEXT, last_try TEXT, tries INTEGER DEFAULT 0, alerted INTEGER DEFAULT 0, err TEXT, title TEXT, rank INTEGER);
CREATE TABLE IF NOT EXISTS story_photos(cid TEXT PRIMARY KEY, src TEXT, credit TEXT, license TEXT, caption TEXT, kind TEXT, label TEXT, link TEXT, jpg BLOB, none INTEGER DEFAULT 0, stored_at TEXT);
CREATE TABLE IF NOT EXISTS story_cards(cid TEXT PRIMARY KEY, png BLOB, v TEXT, src TEXT, built_at TEXT);
CREATE TABLE IF NOT EXISTS spend_model(day TEXT, model TEXT, usd REAL DEFAULT 0, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0, calls INTEGER DEFAULT 0, PRIMARY KEY(day, model));
CREATE TABLE IF NOT EXISTS needs_paid(cid TEXT PRIMARY KEY, since TEXT, rank INTEGER, title TEXT);
"""
def db():
    k = sqlite3.connect(cfg()["db"], timeout=20)
    k.row_factory = sqlite3.Row
    k.executescript(SCHEMA)
    cols = {r[1] for r in k.execute("PRAGMA table_info(jobs)")}
    if "model" not in cols:
        k.execute("ALTER TABLE jobs ADD COLUMN model TEXT")
    k.commit()
    return k

_NC = {"t": 0.0, "v": {}}
def notes(max_age=5.0):
    """{cid: note dict} of writer briefs (cached a few seconds; request threads call this)."""
    if time.time() - _NC["t"] < max_age: return _NC["v"]
    out = {}
    try:
        p = cfg()["db"]
        if not os.path.exists(p):
            return _NC["v"]                      # mid-handoff: keep the last good cache, do not store empty
        k = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
        try:
            rows = k.execute("SELECT cid, note, alias_of FROM briefs").fetchall()
        finally: k.close()
        for c, n, a in rows:
            if a: out[c] = ("alias", a); continue
            try: out[c] = json.loads(n) if n else None
            except Exception: pass
    except Exception:
        traceback.print_exc()
        return _NC["v"]                          # 7:15 PM ET 27 Nov 2026: a failed read cached {} and looked like no write-ups
    _NC.update(t=time.time(), v=out)
    return out
def note_for(cid):
    """Writer brief for a cluster, or None. Callers must check desk content first (story_v3.note_for does)."""
    if not cid: return None
    allv = notes(); n = allv.get(cid)
    if isinstance(n, tuple):   # near-duplicate: the covered story's desk brief, else its writer brief
        tgt = n[1]
        notes_, alias, v3 = _desk_maps()
        d = v3.get(tgt) or notes_.get(tgt) or notes_.get(alias.get(tgt) or "")
        if isinstance(d, dict): return d
        n = allv.get(tgt)
    return n if isinstance(n, dict) else None

# ---------------------------------------------------------------- desk coverage (the routine's briefs win)
def _desk_maps():
    notes_, alias = {}, {}
    try:
        import story_report as SR
        R = SR.reports() or {}
        notes_ = R.get("notes") or {}; alias = R.get("alias") or {}
    except Exception: pass
    v3 = {}
    try:
        import story_v3 as V3
        v3 = V3._load_v3() or {}
    except Exception: pass
    return notes_, alias, v3
def desk_covered(cid, maps=None):
    notes_, alias, v3 = maps or _desk_maps()
    return bool(cid in v3 or cid in notes_ or (alias.get(cid) and alias.get(cid) in notes_))

_STOP = set("the a an of in on at to for and or with by from is are was were has have be this that as near over after into its it new says said "
            "update updates live report reports more than us u s".split())
def _toks(t): return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(w) > 2 and w not in _STOP}
def near_dup(a, b):
    """Two cluster rows describe the same event: same category, close in time, headline tokens mostly shared."""
    if (a.get("category") or "") != (b.get("category") or ""): return False
    ta, tb = _toks(a.get("title")), _toks(b.get("title"))
    if len(ta) < 3 or len(tb) < 3: return False
    j = len(ta & tb) / max(1, len(ta | tb))
    t1, t2 = parse_t(a.get("first_seen")), parse_t(b.get("first_seen"))
    u1, u2 = parse_t(a.get("updated")), parse_t(b.get("updated"))
    close = bool((t1 and t2 and abs((t1 - t2).total_seconds()) < 72 * 3600) or (u1 and u2 and abs((u1 - u2).total_seconds()) < 24 * 3600))
    return close and j >= 0.6

# ---------------------------------------------------------------- source DB (read-only)
def _src():
    p = cfg()["blackout_db"]
    if not os.path.exists(p): return None
    k = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    k.row_factory = sqlite3.Row
    return k
def candidates(hours):
    k = _src()
    if k is None: return []
    try:
        cut = iso(now() - timedelta(hours=hours))
        rows = [dict(r) for r in k.execute(
            "SELECT * FROM clusters WHERE watchlist=0 AND COALESCE(rank,0)>=? AND COALESCE(updated, first_seen)>=? ORDER BY rank DESC, updated DESC LIMIT 400",
            (cfg()["min_rank"], cut))]
    finally: k.close()
    try:
        import story_display as SD
        rows = [SD.apply(r) for r in rows]
        rows = [r for r in rows if SD.visible(r)]
    except Exception: pass
    return rows
def cluster(cid):
    k = _src()
    if k is None: return None, []
    try:
        r = k.execute("SELECT * FROM clusters WHERE cluster_id=?", (cid,)).fetchone()
        al = [dict(x) for x in k.execute("SELECT source, family, title, source_url, event_time, first_seen, official, location FROM alerts "
                                         "WHERE cluster_id=? ORDER BY official DESC, first_seen DESC LIMIT 80", (cid,))]
    finally: k.close()
    r = dict(r) if r else None
    if r:
        try:
            import story_display as SD; r = SD.apply(r)
        except Exception: pass
    return r, al
def source_urls(r, al):
    urls = []
    for a in al:
        u = (a.get("source_url") or "").strip()
        if u.startswith(("http://", "https://")) and u not in urls: urls.append(u)
    try: links = json.loads(r.get("links") or "[]") if isinstance(r.get("links"), str) else (r.get("links") or [])
    except Exception: links = []
    for l in links:
        u = str((l or {}).get("url") or "").strip()
        if u.startswith(("http://", "https://")) and u not in urls: urls.append(u)
    return urls

# ---------------------------------------------------------------- fetching (public hosts only, capped)
MAX_BYTES = 1_500_000; FETCH_TIMEOUT = 9; PER_SOURCE_CHARS = 9000; TOTAL_CHARS = 48000; MAX_SOURCES = 8
UA = "Mozilla/5.0 (compatible; BLACKOUT.NETWORK story writer; +https://blackout.network/about)"
_ALLOW_NETS = []
for _n in (os.environ.get("BN_WRITER_FETCH_ALLOW_CIDR") or "").split(","):
    try:
        if _n.strip(): _ALLOW_NETS.append(ipaddress.ip_network(_n.strip()))
    except ValueError: pass
def _public_host(u):
    try:
        p = urllib.parse.urlsplit(u)
        if p.scheme not in ("http", "https") or not p.hostname: return False
        for fam, _, _, _, sa in socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(sa[0])
            if any(ip in n for n in _ALLOW_NETS): continue   # local testing behind an egress proxy only (unset on Render)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified: return False
        return True
    except Exception: return False
class _NoPrivateRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public_host(newurl): return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)
_OPENER = urllib.request.build_opener(_NoPrivateRedirect())

class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside", "button", "select", "iframe", "template"}
    KEEP = {"p", "h1", "h2", "h3", "li", "td", "blockquote", "pre", "dd", "dt", "figcaption"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.skip = 0; self.cur = None; self.parts = []; self.meta = {}; self.title = ""; self._in_title = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP: self.skip += 1
        elif tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k in ("og:title", "og:description", "description", "article:published_time", "og:site_name") and a.get("content"): self.meta[k] = a["content"]
        elif tag == "title": self._in_title = True
        elif tag in self.KEEP and not self.skip: self.cur = []
        elif tag == "br" and self.cur is not None: self.cur.append(" ")
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip: self.skip -= 1
        elif tag == "title": self._in_title = False
        elif tag in self.KEEP and self.cur is not None:
            t = " ".join("".join(self.cur).split())
            if len(t) >= 25: self.parts.append(t)
            self.cur = None
    def handle_data(self, d):
        if self._in_title: self.title += d
        if self.skip: return
        if self.cur is not None: self.cur.append(d)

def _json_text(o, out, depth=0):
    if depth > 8 or len(out) > 400: return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and k.lower() in ("headline", "description", "instruction", "title", "place", "areadesc", "event", "severity",
                                                    "certainty", "urgency", "sendername", "onset", "expires", "effective", "time", "summary", "text", "name", "status"):
                if v.strip(): out.append(f"{k}: {' '.join(v.split())}")
            elif isinstance(v, (int, float)) and k.lower() in ("mag", "magnitude", "depth", "felt", "tsunami", "alert", "cdi", "mmi", "sig"):
                out.append(f"{k}: {v}")
            else: _json_text(v, out, depth + 1)
    elif isinstance(o, list):
        for v in o[:60]: _json_text(v, out, depth + 1)

def _rewrite(u):
    """Machine-readable twins of pages that are JavaScript-only for a plain fetch."""
    m = re.match(r"https?://earthquake\.usgs\.gov/earthquakes/eventpage/([a-z0-9]+)", u)
    if m: return f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/{m.group(1)}.geojson"
    return u

# Google News RSS/article links do not redirect to the publisher (the id no longer
# embeds the URL). Resolve via the splash signature + Fbv4je batchexecute call, then
# fetch the publisher (or its AMP twin if the canonical page is blocked).
_GNEWS_HOST = "news.google."
_GNEWS_COOKIE = "CONSENT=YES+cb; SOCS=CAI"   # skips the EU consent interstitial; not a secret
_GNEWS_UA = "Mozilla/5.0"
_GNEWS_CACHE = {}            # article id -> {"pub", "amp", "err"}
_GNEWS_AMP = {}              # publisher url -> amp url
_GNEWS_LK = threading.Lock()
_GNEWS_GATE = threading.Semaphore(2)   # Google rate-limits the resolve path

def _is_google_news(u):
    host = (urllib.parse.urlsplit(u or "").hostname or "").lower()
    return _GNEWS_HOST in host

def _gnews_id(u):
    parts = urllib.parse.urlsplit(u or "").path.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] in ("articles", "read") and parts[-1]:
        return parts[-1]
    return ""

def _gnews_embedded_url(u):
    """Fast path for older article ids that still carry an http URL in the base64 payload."""
    gid = _gnews_id(u)
    if not gid:
        return ""
    try:
        raw = base64.urlsafe_b64decode(gid + "=" * ((4 - len(gid) % 4) % 4))
    except Exception:
        return ""
    for b in re.findall(rb"https?://[^\x00-\x1f\x7f-\xff]{12,500}", raw):
        try:
            s = b.decode("ascii")
        except Exception:
            continue
        if s.startswith(("http://", "https://")) and _GNEWS_HOST not in (urllib.parse.urlsplit(s).hostname or ""):
            return s
    return ""

def _parse_garturlres(raw):
    raw = (raw or "").lstrip("\ufeff").lstrip()
    if raw.startswith(")]}'"):
        raw = raw.split("\n", 1)[-1]
    data = json.loads(raw)
    rows = data if isinstance(data, list) else [data]
    for row in rows:
        if not (isinstance(row, list) and len(row) >= 3 and row[1] == "Fbv4je"):
            continue
        payload = row[2]
        if not payload:
            return "", "", "google news wrapper"
        parsed = json.loads(payload) if isinstance(payload, str) else payload
        if not (isinstance(parsed, list) and len(parsed) > 1 and parsed[0] == "garturlres"):
            return "", "", "google news wrapper"
        pub = str(parsed[1] or "").strip()
        amp = str(parsed[3] or "").strip() if len(parsed) > 3 else ""
        if pub.startswith(("http://", "https://")) and not _is_google_news(pub):
            return pub, (amp if amp.startswith(("http://", "https://")) else ""), ""
        return "", "", "google news wrapper"
    return "", "", "google news wrapper"

def resolve_google_news(u):
    """Return (publisher_url, amp_url, err). Cache by article id. Never raises."""
    if not _is_google_news(u):
        return (u or ""), "", ""
    embedded = _gnews_embedded_url(u)
    if embedded:
        return embedded, "", ""
    gid = _gnews_id(u)
    if not gid:
        return "", "", "google news wrapper"
    with _GNEWS_LK:
        hit = _GNEWS_CACHE.get(gid)
    if hit is not None:
        return hit.get("pub") or "", hit.get("amp") or "", hit.get("err") or ""
    err = "google news wrapper"
    pub = amp = ""
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
        hl = (q.get("hl") or ["en-US"])[0]
        gl = (q.get("gl") or ["US"])[0]
        ceid = (q.get("ceid") or ["US:en"])[0]
        splash = f"https://news.google.com/rss/articles/{gid}?hl={urllib.parse.quote(hl)}&gl={urllib.parse.quote(gl)}&ceid={urllib.parse.quote(ceid)}"
        req = urllib.request.Request(splash, headers={"User-Agent": _GNEWS_UA, "Cookie": _GNEWS_COOKIE, "Accept": "text/html"})
        with _GNEWS_GATE:
            with _OPENER.open(req, timeout=FETCH_TIMEOUT) as r:
                final = r.geturl()
                html_body = r.read(MAX_BYTES).decode("utf-8", "replace")
            if not _is_google_news(final) and (final or "").startswith(("http://", "https://")):
                pub, amp, err = final, "", ""
            else:
                sg = re.search(r'data-n-a-sg="([^"]+)"', html_body)
                ts = re.search(r'data-n-a-ts="([^"]+)"', html_body)
                aid = re.search(r'data-n-a-id="([^"]+)"', html_body)
                if not sg or not ts:
                    err = "google news wrapper"
                else:
                    use_id = (aid.group(1) if aid else gid)
                    inner = (
                        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
                        'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
                        f'"{use_id}",{ts.group(1)},"{sg.group(1)}"]'
                    )
                    body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode()
                    preq = urllib.request.Request(
                        "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
                        data=body,
                        headers={"User-Agent": _GNEWS_UA, "Cookie": _GNEWS_COOKIE,
                                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                    )
                    raw = _OPENER.open(preq, timeout=FETCH_TIMEOUT).read(200_000).decode("utf-8", "replace")
                    pub, amp, err = _parse_garturlres(raw)
    except urllib.error.HTTPError as e:
        err = f"google news HTTP {e.code}"
        pub = amp = ""
    except Exception as e:
        err = f"google news {type(e).__name__}"
        pub = amp = ""
    with _GNEWS_LK:
        _GNEWS_CACHE[gid] = {"pub": pub, "amp": amp, "err": err}
        if pub and amp:
            _GNEWS_AMP[pub] = amp
        # cap the cache so a long-running node cannot grow without bound
        if len(_GNEWS_CACHE) > 4000:
            for k in list(_GNEWS_CACHE)[:2000]:
                _GNEWS_CACHE.pop(k, None)
    return pub, amp, err

def _fetch_http(u):
    """Fetch a non-wrapper URL and extract text. {url, final, ok, text, label, err}. Never raises."""
    out = {"url": u, "final": u, "ok": False, "text": "", "label": "", "err": ""}
    try:
        fu = _rewrite(u)
        if not _public_host(fu):
            out["err"] = "host not allowed"; return out
        req = urllib.request.Request(fu, headers={"User-Agent": UA, "Accept": "text/html,application/json,application/geo+json,application/xml;q=0.8,*/*;q=0.5",
                                                  "Accept-Language": "en-US,en;q=0.8"})
        with _OPENER.open(req, timeout=FETCH_TIMEOUT) as r:
            ct = (r.headers.get("Content-Type") or "").lower(); out["final"] = r.geturl()
            raw = r.read(MAX_BYTES + 1)[:MAX_BYTES]
        cs = re.search(r"charset=([\w-]+)", ct); body = raw.decode(cs.group(1) if cs else "utf-8", "replace")
        host = urllib.parse.urlsplit(out["final"]).hostname or ""
        if "json" in ct or body.lstrip()[:1] in ("{", "["):
            try:
                parts = []; _json_text(json.loads(body), parts); text = "\n".join(dict.fromkeys(parts))
            except Exception:
                text = ""
            label = host
        elif "html" in ct or "<html" in body[:2000].lower():
            p = _Text(); p.feed(body); p.close()
            lead = [p.meta.get("og:title") or "", p.meta.get("og:description") or p.meta.get("description") or ""]
            text = "\n".join(x for x in lead + p.parts if x)
            label = " ".join((p.meta.get("og:site_name") or "").split()) or host
            if p.meta.get("article:published_time"): text = f"Published: {p.meta['article:published_time']}\n" + text
        elif "xml" in ct or "text/plain" in ct:
            text = " ".join(re.sub(r"<[^>]+>", " ", body).split()); label = host
        else:
            out["err"] = f"unsupported type {ct[:40]}"; return out
        text = html.unescape(text)
        if _GNEWS_HOST in host:
            out["err"] = "google news wrapper"; return out
        if len(text) < 200:
            out["err"] = "too little text"; out["text"] = text[:PER_SOURCE_CHARS]; return out
        out.update(ok=True, text=text[:PER_SOURCE_CHARS], label=label[:80])
    except urllib.error.HTTPError as e:
        out["err"] = f"HTTP {e.code}"
    except Exception as e:
        out["err"] = type(e).__name__
    return out

def fetch(u):
    """{url, final, ok, text, label, err}. Resolves Google News wrappers first. Never raises."""
    if _is_google_news(u):
        pub, amp, err = resolve_google_news(u)
        if not pub:
            return {"url": u, "final": u, "ok": False, "text": "", "label": "", "err": err or "google news wrapper"}
        out = _fetch_http(pub)
        out["url"] = pub
        if out["ok"]:
            return out
        if amp and amp != pub and amp != out.get("final"):
            alt = _fetch_http(amp)
            if alt["ok"]:
                alt["url"] = pub or amp
                return alt
            # keep the more specific error if both failed
            if not out.get("err"):
                out["err"] = alt.get("err") or err or "google news wrapper"
        if not out.get("err"):
            out["err"] = err or "google news wrapper"
        return out
    out = _fetch_http(u)
    if (not out["ok"]) and (out.get("err") or "").startswith("HTTP 403"):
        with _GNEWS_LK:
            amp = _GNEWS_AMP.get(u) or _GNEWS_AMP.get(out.get("final") or "")
        if amp and amp != u:
            alt = _fetch_http(amp)
            if alt["ok"]:
                alt["url"] = u
                return alt
    return out

def fetch_all(urls):
    """Fetch cluster source URLs. Non-Google-News links first; wrappers are resolved and
    other corroborating sources are still tried when one URL is unreadable."""
    seen, direct, gnews = set(), [], []
    for u in urls or []:
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        (gnews if _is_google_news(u) else direct).append(u)
    # Resolve wrappers with tight concurrency before the main fetch so a burst of
    # Google News links does not 429, and so we can prefer already-direct publishers.
    resolved = []
    if gnews:
        def _res(u):
            pub, amp, err = resolve_google_news(u)
            return u, pub, amp, err
        with ThreadPoolExecutor(max_workers=2) as ex:
            for u, pub, amp, err in ex.map(_res, gnews):
                if pub and pub not in seen:
                    seen.add(pub)
                    resolved.append(pub)
                elif not pub:
                    # keep a stub so the deferred error lists the wrapper reason
                    resolved.append(u)
    to_fetch = (direct + [u for u in resolved if not _is_google_news(u)])[:MAX_SOURCES * 2]
    # If every direct URL failed and we still have unresolved wrappers, include a few
    # so fetch() records their errors (already resolved failures stay in `tried`).
    if not to_fetch:
        to_fetch = gnews[:MAX_SOURCES * 2]
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(fetch, to_fetch))
    # If all direct fetches failed, try remaining resolved publishers we trimmed off.
    if not any(f["ok"] for f in res):
        extra = [u for u in resolved if not _is_google_news(u) and u not in to_fetch][:MAX_SOURCES]
        if extra:
            with ThreadPoolExecutor(max_workers=6) as ex:
                res.extend(ex.map(fetch, extra))
    good, total = [], 0
    for f in res:
        if not f["ok"]:
            continue
        if total >= TOTAL_CHARS or len(good) >= MAX_SOURCES:
            break
        f["text"] = f["text"][:max(800, TOTAL_CHARS - total)]
        total += len(f["text"])
        good.append(f)
    return good, res

# ---------------------------------------------------------------- prompt
SYSTEM = """You write story pages for BLACKOUT.NETWORK, a global threat-monitoring news site. You are given the scanner's record of one story and the extracted text of its source pages, labelled S1, S2 and so on.

Hard rules, no exceptions:
1. Use ONLY facts found in the provided source texts or the scanner record. Never add facts from memory or general knowledge. No invented numbers, dates, names, places, quotes or casualty figures. Every number you write must appear in a source.
2. Attribute claims ("USGS said...", "according to Reuters..."). A claim that appears in only one source is labelled as coming from that source and not independently confirmed. Quote only exact words that appear in a source, in double quotes.
3. Place: the story happens where the scanner record's "place" says unless the sources clearly say otherwise. Never move a story to another country or state.
4. Neutral, calm, plain English for an average reader. Political items strictly neutral. Never use: verified, first (as a boast), before the news, BREAKING, exclusive, shocking, terrifying, panic, hype or scare words. No "today in history" or anniversary framing. No emojis. Never mention a site owner. No internal notes. No scoring jargon in prose (no "severity", "score", "rank 7/10", "item(s)", "source family"); in rank_why say in plain words why it ranks where it does.
5. If the sources are thin, say so honestly ("so far we have only the USGS notice") instead of padding. If you cannot source background history, leave story.sections.background as an empty string.
6. Risk to an ordinary reader is never above the story's band: rank 0-3 Low, 4-6 Medium, 7-10 High. Use Low for over-ranked items (sports, entertainment, expired warnings) and say why.
7. what_to_do starts with "No action is needed." when that is true for an ordinary reader in the United States.
8. sources and story.sources may list ONLY URLs from the provided S-list, 2-6 of them when available, most authoritative first. Prefer official agencies and news outlets; cite a social media post only when nothing better covers that fact.
9. Never write the S-labels (S1, S2), "scanner record" or other internal labels in any text field. Ignore source material about a different event; do not mention unrelated posts. If every source is a social media post, say which account posted it and that no news outlet or official source has confirmed it yet.
10. US style: write numbers with commas (11,613), dates like "Nov. 21", times in ET when the record gives them.

Return ONE JSON object, no markdown, exactly these keys:
{"headline": "<one plain sentence with the key fact, under 110 characters>",
 "why_it_matters": "<one sentence bottom line>",
 "what_happened": "<2-3 sentences: who, what, where, when, with attribution>",
 "analysis": "<2-3 sentences on what this means, from the sources>",
 "rank_why": "<one sentence on why the story ranks where it does and whether we agree>",
 "risk": "Low|Medium|High", "risk_why": "<one line>",
 "if_true": "<signposts if the reporting holds>", "if_false": "<what it looks like if overblown or wrong>",
 "what_to_do": "<1-2 practical sentences>",
 "confidence": "High|Medium|Low", "confidence_why": "<which sources, and what is not confirmed>",
 "sources": ["<url from the S-list>", "..."],
 "story": {"headline": "<page H1, one sentence, under 140 characters>", "dek": "<one or two short sentences that add to the headline>",
   "sections": {"happened": "<chronological narrative with dates, names, places and attribution; several short paragraphs separated by blank lines>",
                "background": "<history and context ONLY from the sources, or empty string>",
                "analysis": "<why it matters, who is affected, whether it is spreading or confirmed, whether the rank fits, in plain words>",
                "watch": "<signposts to watch next and practical guidance>"},
   "sources": [{"url": "<url from the S-list>", "label": "<outlet or agency, short title, date if known>"}]}}
Aim for 450-900 words across the four story sections. Shorter is fine when the sources are thin."""

def _et(s):
    d = parse_t(s)
    return d.astimezone(ET).strftime("%b %-d, %Y %-I:%M %p ET") if d else ""

def place_of(r):
    loc = r.get("location") or ""
    try:
        import geo
        return geo.place_label(r.get("title") or "", loc) or (loc if loc.count(";") < 2 else "")
    except Exception:
        return loc if loc.count(";") < 2 else ""

def build_prompt(r, al, srcs):
    heads = []
    for a in al[:25]:
        t = " ".join((a.get("title") or "").split())
        if t: heads.append(f"- {a.get('source') or a.get('family') or 'source'}{' (official)' if a.get('official') else ''}, {_et(a.get('event_time') or a.get('first_seen'))}: {t[:240]}")
    rec = {"title": r.get("title"), "category": r.get("category"), "place": place_of(r), "rank": int(r.get("rank") or 0),
           "first_seen": _et(r.get("first_seen")), "event_time": _et(r.get("event_time")), "updated": _et(r.get("updated")),
           "independent_sources": int(r.get("eff_families") or r.get("n_families") or 0), "reports_logged": int(r.get("n_items") or 0)}
    s = ["SCANNER RECORD:", json.dumps(rec, ensure_ascii=False), "", "HEADLINES FROM THE SOURCES WE TRACK (source data, not our words):", *heads, ""]
    for i, f in enumerate(srcs, 1):
        s += [f"[S{i}] URL: {f['url']}", f"[S{i}] Outlet: {f['label']}", f"[S{i}] TEXT:", f["text"], ""]
    s.append("Write the JSON now.")
    return "\n".join(s), rec

# ---------------------------------------------------------------- validation + text QA
V2 = ("headline", "why_it_matters", "what_happened", "analysis", "rank_why", "risk", "risk_why", "if_true", "if_false", "what_to_do", "confidence", "confidence_why")
BANNED = re.compile(r"\b(verified|unverified|breaking|before the news|exclusive|shocking|terrifying|horrifying|panic|bombshell|apocalyptic|"
                    r"today in history|anniversary|source famil(?:y|ies)|severity|item\(s\)|rank \d+\s*/\s*10|\d+\s*/\s*10|scanner scor|"
                    r"\(?S\d{1,2}\)?(?=[\s,.;:)]|$)|scanner record|as an ai|language model|i cannot|matt johnston|meshtastic|lora|lorem ipsum)\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
def _band(rank): return "Low" if rank <= 3 else ("Medium" if rank <= 6 else "High")
_ORDER = {"Low": 0, "Medium": 1, "High": 2}
def _norm(s): return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower().replace(",", "")))
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
def _nums_in(text):
    return {n.replace(",", "") for n in _NUM.findall(text or "")}
_GROUPED = re.compile(r"(?<![\d.])\d{1,3}(?:[ \u00a0\u202f\u2009]\d{3})+(?![\d])")
def _corpus_nums(corpus):
    corpus = (corpus or "") + " " + " ".join(g.replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace("\u2009", "") for g in _GROUPED.findall(corpus or ""))
    s = _nums_in(corpus)
    out = set(s)
    for n in s:   # 7.20 == 7.2, 030 == 30
        try:
            v = float(n); out.add(("%g" % v)); out.add(str(int(v)) if v == int(v) else n)
        except Exception: pass
    return out

def validate(o, rank, fetched_urls, corpus):
    """(clean note dict, [problems]). Problems mean reject (the caller retries once with them)."""
    probs = []
    if not isinstance(o, dict): return None, ["output is not a JSON object"]
    note = {}
    for k in V2:
        v = o.get(k)
        if not isinstance(v, str) or not v.strip(): probs.append(f"missing {k}")
        else: note[k] = " ".join(v.split()) if k not in ("what_happened", "analysis") else v.strip()
    if probs: return None, probs
    if note["risk"] not in _ORDER: probs.append("risk must be Low, Medium or High")
    if note["confidence"] not in _ORDER: probs.append("confidence must be High, Medium or Low")
    band = _band(rank)
    if note.get("risk") in _ORDER and _ORDER[note["risk"]] > _ORDER[band]: note["risk"] = band   # the page caps it too
    st = o.get("story") if isinstance(o.get("story"), dict) else {}
    secs = st.get("sections") if isinstance(st.get("sections"), dict) else {}
    story = {"headline": " ".join(str(st.get("headline") or note["headline"]).split())[:180],
             "dek": " ".join(str(st.get("dek") or "").split()),
             "sections": {k: str(secs.get(k) or "").strip() for k in ("happened", "background", "analysis", "watch")}}
    for k in ("happened", "analysis", "watch"):
        if len(story["sections"][k].split()) < (40 if k == "happened" else 20): probs.append(f"story.sections.{k} too short")
    if not story["dek"]: probs.append("missing story.dek")
    fset = set(fetched_urls)
    srcs = [u for u in (o.get("sources") or []) if isinstance(u, str) and u in fset]
    bad = [u for u in (o.get("sources") or []) if isinstance(u, str) and u not in fset]
    if bad: probs.append(f"sources not in the S-list: {bad[:3]}")
    ss = []
    for s in (st.get("sources") or []):
        if isinstance(s, dict) and s.get("url") in fset and s["url"] not in [x["url"] for x in ss]:
            ss.append({"url": s["url"], "label": " ".join(str(s.get("label") or "").split())[:140] or urllib.parse.urlsplit(s["url"]).hostname})
    if not srcs: srcs = [s["url"] for s in ss]
    if not srcs: probs.append("no sources from the S-list")
    if not ss: ss = [{"url": u, "label": urllib.parse.urlsplit(u).hostname} for u in srcs]
    note["sources"] = srcs[:6]; story["sources"] = ss[:6]
    prose = "\n".join([note[k] for k in V2 if k not in ("risk", "confidence")] + [story["headline"], story["dek"]] + list(story["sections"].values()))
    for m in BANNED.finditer(prose): probs.append(f"banned wording: {m.group(0)!r}")
    if EMOJI.search(prose): probs.append("emoji in text")
    cn = _corpus_nums(corpus)
    def _ok(n):
        try: return n in cn or ("%g" % float(n)) in cn
        except Exception: return n in cn
    miss = sorted({n for n in _nums_in(prose) if not _ok(n)})
    if miss: probs.append(f"numbers not found in any source: {miss[:12]}")
    nc = _norm(corpus)
    for q in re.findall(r"[\"“]([^\"”]{12,400})[\"”]", prose):
        if len(q.split()) >= 4 and _norm(q) not in nc: probs.append(f"quote not found in sources: {q[:80]!r}")
    words = len(" ".join(story["sections"].values()).split())
    if words > 1600: probs.append(f"story too long ({words} words)")
    note["story"] = story
    return note, list(dict.fromkeys(probs))

# ---------------------------------------------------------------- API
class APIError(Exception): pass
def call_api(messages, max_tokens=6000):
    """(content str, usage dict). Raises APIError. The key is read from the environment and never logged."""
    c = cfg(); key = (os.environ.get("XAI_API_KEY") or "").strip()
    if not key: raise APIError("no API key")
    body = json.dumps({"model": c["model"], "messages": messages, "temperature": 0.2, "max_tokens": max_tokens,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(c["api"] + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "blackout-story-writer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r: d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise APIError(f"HTTP {e.code}: {e.read(300).decode('utf-8', 'replace')[:200]}")
    except Exception as e:
        raise APIError(type(e).__name__)
    try: content = d["choices"][0]["message"]["content"]
    except Exception: raise APIError("no content in response")
    u = d.get("usage") or {}
    tin = int(u.get("prompt_tokens") or 0); comp = int(u.get("completion_tokens") or 0)
    reas = int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
    tot = int(u.get("total_tokens") or 0)
    tout = max(comp, tot - tin) if tot else comp + reas   # reasoning tokens bill as output
    return content, {"in": tin, "out": tout, "reasoning": reas}
def _cost(usage):
    c = cfg(); tin = usage["in"]; tout = usage["out"]
    return tin, tout, round(tin * c["price_in"] / 1e6 + tout * c["price_out"] / 1e6, 6)
def _parse_json(s):
    s = (s or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try: return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: return None
    return None

# ---------------------------------------------------------------- spend / rate limits
def spent_all_today(k=None):
    """All-model spend for the ET day (includes the retired grok-4.3 writer). Not used for the cap."""
    own = k is None; k = k or db()
    try:
        r = k.execute("SELECT usd, tokens_in, tokens_out, calls FROM spend WHERE day=?", (et_day(),)).fetchone()
        return dict(r) if r else {"usd": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0}
    finally:
        if own: k.close()
def spent_today(k=None):
    """Spend under the current model only. The $0.25 cap does not include earlier models' spend the same day."""
    own = k is None; k = k or db()
    try:
        r = k.execute("SELECT usd, tokens_in, tokens_out, calls FROM spend_model WHERE day=? AND model=?",
                      (et_day(), cfg()["model"])).fetchone()
        return dict(r) if r else {"usd": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0}
    finally:
        if own: k.close()
def _bump_spend(k, tin, tout, usd, calls=1):
    k.execute("INSERT INTO spend(day, usd, tokens_in, tokens_out, calls) VALUES(?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET "
              "usd=usd+excluded.usd, tokens_in=tokens_in+excluded.tokens_in, tokens_out=tokens_out+excluded.tokens_out, calls=calls+excluded.calls",
              (et_day(), usd, tin, tout, calls))
    k.execute("INSERT INTO spend_model(day, model, usd, tokens_in, tokens_out, calls) VALUES(?,?,?,?,?,?) ON CONFLICT(day, model) DO UPDATE SET "
              "usd=usd+excluded.usd, tokens_in=tokens_in+excluded.tokens_in, tokens_out=tokens_out+excluded.tokens_out, calls=calls+excluded.calls",
              (et_day(), cfg()["model"], usd, tin, tout, calls))

def _add_spend(k, tin, tout, usd):
    _bump_spend(k, tin, tout, usd, 1)
def written_last_hour(k):
    return k.execute("SELECT COUNT(*) FROM jobs WHERE status='done' AND calls>0 AND finished>=? AND COALESCE(model,'')=?",
                     (iso(now() - timedelta(hours=1)), cfg()["model"])).fetchone()[0]
def blocked_reason(k):
    c = cfg(); sp = spent_today(k)
    if ledger_untrusted() and float(sp["usd"] or 0) <= 0:
        return "spend ledger missing after deploy; paid writer closed until seed"
    if sp["usd"] >= c["daily_usd"]: return f"daily cap reached (${sp['usd']:.4f} of ${c['daily_usd']:.2f})"
    if written_last_hour(k) >= c["max_per_hour"]: return f"hourly limit reached ({c['max_per_hour']}/h)"
    return None

# ---------------------------------------------------------------- spend ledger seed / fall-closed
_UNTRUSTED_NAME = "story_writer.ledger_untrusted"

def _untrusted_path():
    d = os.path.dirname(cfg()["db"]) or "."
    return os.path.join(d, _UNTRUSTED_NAME)

def mark_ledger_untrusted(reason=""):
    """After a failed deploy handoff the writer DB (and today's spend row) may be gone.

    Paid calls stay blocked for the rest of the ET day until a signed seed raises the ledger,
    so a reset-to-zero ledger cannot start a second day of spend under the same cap.
    """
    payload = {"day": et_day(), "reason": str(reason or "")[:200], "at": iso()}
    pth = _untrusted_path(); tmp = pth + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, pth)

def clear_ledger_untrusted():
    try:
        os.unlink(_untrusted_path())
    except FileNotFoundError:
        pass

def ledger_untrusted():
    try:
        with open(_untrusted_path()) as f:
            d = json.load(f)
    except Exception:
        return False
    return d.get("day") == et_day()

def seed_spend(body):
    """Raise today's spend ledger to the given floors. Never decreases counts or the cap.

    body: {floor_usd (required), tokens_in?, tokens_out?, calls?, day_et?, clear_untrusted?}
    day_et must be today's ET date when provided. floor_usd is capped at $50 to catch typos.
    """
    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    day = str(body.get("day_et") or et_day())
    if day != et_day():
        raise ValueError(f"day_et must be today ({et_day()})")
    if "floor_usd" not in body and "usd" not in body:
        raise ValueError("floor_usd is required")
    try:
        floor_usd = float(body["floor_usd"] if "floor_usd" in body else body.get("usd"))
    except (TypeError, ValueError):
        raise ValueError("floor_usd must be a number")
    if not (0 <= floor_usd <= 50):
        raise ValueError("floor_usd out of range")

    def floor_int(key, lo=0, hi=50_000_000):
        if key not in body:
            return None
        try:
            v = int(body[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be an integer")
        if v < lo or v > hi:
            raise ValueError(f"{key} out of range")
        return v

    floor_in = floor_int("tokens_in")
    floor_out = floor_int("tokens_out")
    floor_calls = floor_int("calls", hi=100000)
    with _LK:
        k = db()
        try:
            cur = spent_today(k)
            d_usd = max(0.0, floor_usd - float(cur["usd"] or 0))
            d_in = max(0, floor_in - int(cur["tokens_in"] or 0)) if floor_in is not None else 0
            d_out = max(0, floor_out - int(cur["tokens_out"] or 0)) if floor_out is not None else 0
            d_calls = max(0, floor_calls - int(cur["calls"] or 0)) if floor_calls is not None else 0
            if d_usd or d_in or d_out or d_calls:
                _bump_spend(k, d_in, d_out, d_usd, d_calls)
                k.commit()
            now = spent_today(k)
            if body.get("clear_untrusted") or float(now["usd"] or 0) > 0:
                clear_ledger_untrusted()
            out = {"ok": True, "added_usd": round(d_usd, 6), "added_calls": d_calls,
                   "spend_today": now, "ledger_untrusted": ledger_untrusted()}
            out["spend_today"]["day_et"] = et_day()
            return out
        finally:
            k.close()

# ---------------------------------------------------------------- queue
STATE = {"thread": None, "started": None, "last_scan": None, "last_error": None, "scans": 0, "paused": None, "initial_done": False, "boot_backfill": 0}
def _invalidate(cid):
    _NC["t"] = 0.0
    for mod, keyf in (("wire_v2", lambda k: k == cid), ("story", lambda k: isinstance(k, tuple) and k and k[0] == cid)):
        m = sys.modules.get(mod)
        try:
            C = getattr(m, "_C", None)
            if isinstance(C, dict):
                for kk in [x for x in list(C) if keyf(x)]: C.pop(kk, None)
        except Exception: pass
    # Re-run repaired tags/headlines through the publish gate on the next validator pass.
    try:
        import wire_timeline as WT
        WT._VR.pop(cid, None)
        WT._VT.pop(cid, None)
        WT._XC.pop(cid, None)
        if isinstance(getattr(WT, "_PC", None), dict) and isinstance(WT._PC.get("t"), dict):
            WT._PC["t"]["k"] = 0.0
    except Exception:
        pass

def enqueue(k, cid, reason, arrived_at, rank, title):
    if k.execute("SELECT 1 FROM jobs WHERE cid=? AND status IN ('queued','running','deferred')", (cid,)).fetchone(): return False
    k.execute("INSERT INTO jobs(cid, reason, status, enq_at, arrived_at, rank, title) VALUES(?,?,?,?,?,?,?)",
              (cid, reason, "queued", iso(), arrived_at, rank, (title or "")[:200]))
    return True

def _dedupe_open_jobs(k):
    """Keep one open paid job per story. Duplicate deferred/queued upgrades were starving package_pending."""
    rows = k.execute(
        "SELECT id, cid, status FROM jobs WHERE status IN ('queued','running','deferred') "
        "ORDER BY cid, CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END, id"
    ).fetchall()
    seen = set()
    for r in rows:
        cid = r["cid"]
        if cid in seen:
            if r["status"] != "running":
                k.execute("UPDATE jobs SET status='skipped', err='duplicate job' WHERE id=? AND status IN ('queued','deferred')", (r["id"],))
        else:
            seen.add(cid)

def _is_template_brief(h):
    m = (h or {}).get("model") or ""
    return m == "template" or m.startswith("template")

def scan():
    """Queue new rank 5+ clusters and one-time upgrades of template-only briefs. No automatic rewrites."""
    c = cfg(); maps = _desk_maps(); notes_, alias, v3 = maps
    rows = candidates(max(c["backfill_h"], 2) + 0.0)
    first = not STATE["initial_done"]
    with _LK:
        k = db()
        try:
            if not rewrite_allowed():
                k.execute("UPDATE jobs SET status='skipped', err='rewrites disabled' WHERE status IN ('queued','deferred') AND reason LIKE 'refresh%'")
            have = {r["cid"]: dict(r) for r in k.execute("SELECT cid, written_at, src_urls, alias_of, model FROM briefs")}
            seen = {r["cid"]: dict(r) for r in k.execute("SELECT cid, first_seen, backfill FROM seen")}
            covered_rows = [r for r in rows if desk_covered(r["cluster_id"], maps)]
            _dedupe_open_jobs(k)
            queued = {x[0] for x in k.execute("SELECT cid FROM jobs WHERE status IN ('queued','running')")}
            deferred = {x[0] for x in k.execute("SELECT cid FROM jobs WHERE status='deferred'")}
            claimed = [r for r in rows if (r["cluster_id"] in have and not have[r["cluster_id"]].get("alias_of") and not _is_template_brief(have[r["cluster_id"]])) or r["cluster_id"] in queued]
            for r in rows:
                cid = r["cluster_id"]; rank = int(r.get("rank") or 0)
                if cid not in seen:
                    k.execute("INSERT OR IGNORE INTO seen(cid, first_seen, rank, backfill) VALUES(?,?,?,?)", (cid, iso(), rank, 1 if first else 0))
                    seen[cid] = {"first_seen": iso(), "backfill": 1 if first else 0}
                if desk_covered(cid, maps): continue
                if cid in have:
                    h = have[cid]
                    if h.get("alias_of"): continue
                    if _is_template_brief(h) and rank >= c["min_rank"] and cid not in queued and cid not in deferred:
                        if enqueue(k, cid, "upgrade", seen[cid]["first_seen"], rank, r.get("title")):
                            queued.add(cid); claimed.append(r)
                        continue
                    if rewrite_allowed() and c["refresh_min"] > 0:
                        wt = parse_t(h.get("written_at"))
                        if wt and (now() - wt).total_seconds() >= c["refresh_min"] * 60 and (parse_t(r.get("updated")) or wt) > wt:
                            _, al = cluster(cid)
                            newsrc = set(source_urls(r, al)) - set(json.loads(h.get("src_urls") or "[]"))
                            if len(newsrc) >= 2: enqueue(k, cid, "refresh: new sources", seen[cid]["first_seen"], rank, r.get("title"))
                    continue
                if cid in queued: continue
                dup = next((x for x in covered_rows if x["cluster_id"] != cid and near_dup(r, x)), None)
                if dup is None:
                    dup_w = next((x for x in claimed if x["cluster_id"] != cid and near_dup(r, x)), None)
                else: dup_w = None
                if dup is not None or dup_w is not None:
                    tgt = (dup or dup_w)["cluster_id"]
                    k.execute("INSERT OR REPLACE INTO briefs(cid, note, written_at, model, src_urls, alias_of, rank, title) VALUES(?,?,?,?,?,?,?,?)",
                              (cid, None, iso(), "alias:desk" if dup is not None else "alias", "[]", tgt, rank, r.get("title")))
                    k.execute("UPDATE jobs SET status='skipped', err=? WHERE cid=? AND status IN ('queued','deferred')", (f"near-duplicate of {tgt}", cid))
                    _invalidate(cid); continue
                if cid in deferred: claimed.append(r); continue
                if enqueue(k, cid, "backfill" if seen[cid].get("backfill") else "new", seen[cid]["first_seen"], rank, r.get("title")):
                    claimed.append(r); queued.add(cid)
            k.commit()
        finally: k.close()
    STATE["initial_done"] = True; STATE["last_scan"] = iso(); STATE["scans"] += 1

def next_job(k):
    r = k.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY CASE reason WHEN 'new' THEN 0 WHEN 'upgrade' THEN 1 WHEN 'refresh: new sources' THEN 3 ELSE 2 END, rank DESC, id LIMIT 1").fetchone()
    return dict(r) if r else None

def write_one(job, api=None):
    """Fetch, write, validate, store. Returns the final job status."""
    api = api or call_api
    cid = job["cid"]; t0 = time.time()
    with _LK:
        k = db(); k.execute("UPDATE jobs SET status='running', started=? WHERE id=?", (iso(), job["id"])); k.commit(); k.close()
    status, err, tin_t, tout_t, usd_t, calls = "failed", "", 0, 0, 0.0, 0
    try:
        r, al = cluster(cid)
        if not r: raise RuntimeError("cluster gone")
        if desk_covered(cid): status = "skipped"; err = "desk brief arrived"; raise StopIteration
        if has_paid_article(cid): status = "skipped"; err = "already has a paid write-up"; raise StopIteration
        with _LK:
            k = db(); al_row = k.execute("SELECT alias_of FROM briefs WHERE cid=?", (cid,)).fetchone(); k.close()
        if al_row and al_row[0]: status = "skipped"; err = f"near-duplicate of {al_row[0]}"; raise StopIteration
        urls = source_urls(r, al)
        srcs, tried = fetch_all(urls)
        if not srcs:
            status = "deferred"; err = "no readable source text yet (" + ", ".join(sorted({f['err'] for f in tried if f['err']}))[:120] + ")"; raise StopIteration
        prompt, rec = build_prompt(r, al, srcs)
        corpus = prompt
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        note, probs = None, ["not run"]
        for attempt in range(2):
            with _LK:
                k = db(); why = blocked_reason(k); k.close()
            if why: status = "deferred"; err = why; raise StopIteration
            content, usage = api(msgs)
            calls += 1; tin, tout, usd = _cost(usage); tin_t += tin; tout_t += tout; usd_t += usd
            with _LK:
                k = db(); _add_spend(k, tin, tout, usd); k.commit(); k.close()
            o = _parse_json(content)
            note, probs = validate(o, int(r.get("rank") or 0), [f["url"] for f in srcs], corpus) if o is not None else (None, ["response was not valid JSON"])
            if note and not probs: break
            msgs = msgs + [{"role": "assistant", "content": content or ""},
                           {"role": "user", "content": "Your JSON failed these checks; fix every one and return the full corrected JSON only:\n- " + "\n- ".join((probs or [])[:20])}]
        if not note or probs:
            err = "; ".join((probs or ["invalid"])[:6])[:400]; raise StopIteration
        w = iso()
        note.update({"written_at": w, "generated_at": w, "edition": "BLACKOUT.NETWORK desk brief", "desk": True, "file": "story_writer",
                     "writer": {"model": cfg()["model"], "sources_read": len(srcs)}})
        note["story"]["written_at"] = w
        with _LK:
            k = db()
            if desk_covered(cid): status = "skipped"; err = "desk brief arrived during write"
            else:
                k.execute("INSERT OR REPLACE INTO briefs(cid, note, written_at, model, src_urls, alias_of, tokens_in, tokens_out, usd, rank, title) VALUES(?,?,?,?,?,NULL,?,?,?,?,?)",
                          (cid, json.dumps(note, ensure_ascii=False), w, cfg()["model"], json.dumps(urls), tin_t, tout_t, usd_t, int(r.get("rank") or 0), r.get("title")))
                status = "done"
            k.commit(); k.close()
        _invalidate(cid)
        if status == "done":
            _clear_needs_paid(cid)
            try:
                package_one(cid, row=r, al=al, build_card_now=False)
            except Exception:
                traceback.print_exc()
    except StopIteration: pass
    except APIError as e: status = "deferred"; err = f"API: {e}"
    except Exception as e: err = f"{type(e).__name__}: {str(e)[:200]}"; traceback.print_exc()
    fin = iso(); lat = None
    a = parse_t(job.get("arrived_at"))
    if status == "done" and a: lat = round((now() - a).total_seconds(), 1)
    with _LK:
        k = db()
        k.execute("UPDATE jobs SET status=?, finished=?, err=?, tokens_in=?, tokens_out=?, usd=?, latency_s=?, calls=?, model=? WHERE id=?",
                  (status, fin, err, tin_t, tout_t, usd_t, lat, calls, cfg()["model"] if calls else None, job["id"]))
        k.commit(); k.close()
    log(f"{cid} {job['reason']} -> {status} in {time.time() - t0:.1f}s tokens {tin_t}/{tout_t} ${usd_t:.4f}" + (f" ({err[:160]})" if err else ""))
    return status

_DEFER = {}
def _requeue_deferred(k):
    """Deferred jobs (no source text yet, cap, API error) go back in the queue after a back-off."""
    skip_refresh = not rewrite_allowed()
    for r in k.execute("SELECT id, cid, finished, err, reason FROM jobs WHERE status='deferred'").fetchall():
        if skip_refresh and (r["reason"] or "").startswith("refresh"):
            k.execute("UPDATE jobs SET status='skipped', err='rewrites disabled' WHERE id=?", (r["id"],))
            continue
        f = parse_t(r["finished"]); wait = 900 if "cap" in (r["err"] or "") or "limit" in (r["err"] or "") else 300
        n = _DEFER.get(r["cid"], 0)
        if f and (now() - f).total_seconds() >= wait * (1 + min(n, 6)):
            if n >= 8: k.execute("UPDATE jobs SET status='failed' WHERE id=?", (r["id"],)); continue
            _DEFER[r["cid"]] = n + 1
            k.execute("UPDATE jobs SET status='queued' WHERE id=?", (r["id"],))

def _writer_worker(ready, paused):
    """The one background thread. (Its name must not contain the words the web node's thread guard blocks.)"""
    STATE["started"] = iso(); waited = 0
    while not ready() and waited < 1800: time.sleep(5); waited += 5
    with _LK:
        k = db(); k.execute("UPDATE jobs SET status='queued' WHERE status='running'"); k.commit(); k.close()
    last_mt = None
    while True:
        try:
            if paused(): STATE["paused"] = "deploy handoff"; time.sleep(5); continue
            if not templates_on() and not api_enabled():
                STATE["paused"] = "no API key" if not key_set() else "BN_WRITER=0"; time.sleep(30); continue
            STATE["paused"] = None if api_enabled() else "BN_WRITER=0, templates on"
            if not STATE.get("gate_booted") and templates_on():
                boot_gate()
            # New arrivals get a free template on every pass, before any paid job.
            # After a deploy the paid queue can run for many minutes; write_one then
            # `continue` used to skip package_pending and leave new Wire stories unpublished.
            if templates_on():
                counts = package_pending(max_backfill=0)
                log(f"free templates: {counts.get('new', 0)} packaged")
                nfix = repair_packaged(max_n=40)
                if nfix:
                    log(f"free repair: {nfix} retagged or reheaded")
            if api_enabled():
                mt = []
                for sfx in ("", "-wal"):   # realtime deltas (realtime.py) may commit to the WAL without touching the main file
                    try: mt.append(os.path.getmtime(cfg()["blackout_db"] + sfx))
                    except OSError: mt.append(None)
                if mt != last_mt or time.time() - (parse_t(STATE["last_scan"]) or now()).timestamp() > 120 or not STATE["initial_done"]:
                    scan(); last_mt = mt
                with _LK:
                    k = db()
                    _dedupe_open_jobs(k)
                    blocked = blocked_reason(k)
                    # When the daily cap (or hourly limit) is hit, do not requeue or drain
                    # cap-deferred upgrades: write_one would bounce in ~0.3s and `continue`
                    # would skip package_pending, leaving new Wire stories without tags/cards.
                    if not blocked:
                        _requeue_deferred(k)
                    k.commit()
                    job = None if blocked else next_job(k)
                    k.close()
                if job:
                    write_one(job)
                    continue  # drain the paid queue before the slow template/card pass
            if templates_on():
                package_pending()
                nfix = repair_packaged(max_n=40)
                if nfix:
                    log(f"free repair: {nfix} retagged or reheaded")
                check_held_alerts()
            if not api_enabled():
                time.sleep(cfg()["poll_s"]); continue
        except Exception as e:
            STATE["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"; traceback.print_exc()
        time.sleep(cfg()["poll_s"])

# ---------------------------------------------------------------- template write-ups + publish gate (Nov 25 2026, PR 1)
# Every live Wire item gets a free write-up built only from scanner data (no API). Tags are the rule-based
# x_share extractor (never the paid x_tags_llm path). Cards are built through share_card.story_png / warm.
# The public gate stays off until boot_gate() snapshots current cluster ids (they stay visible) and then
# turns on: any cluster first seen after that snapshot is held until its write-up, tags and card are stored.

def gate_on():
    return bool(STATE.get("gate_on")) and gate_wanted()

def _item_for_tags(r):
    return {"cluster_id": r.get("cluster_id") or r.get("id"), "title": r.get("title") or "", "headline": r.get("title") or "",
            "brief": r.get("brief") or "", "location": r.get("location") or "", "category": r.get("category") or "",
            "rank": r.get("rank") or 0, "watchlist": r.get("watchlist") or 0, "hidden": r.get("hidden") or 0}

_TAG_BANNED = {"news", "worldnews", "breaking", "breakingnews", "blackoutnetwork", "blackout",
               "alerts", "update", "updates", "live"}

def _tag_text(r, al=None):
    """Title, place, brief, and source titles — the free tagger's only inputs."""
    parts = [r.get("title") or "", r.get("headline") or "", r.get("location") or "", r.get("brief") or ""]
    for a in al or []:
        parts.append((a or {}).get("title") or "")
    try:
        raw = json.loads(r.get("links") or "[]") if isinstance(r.get("links"), str) else (r.get("links") or [])
        for l in raw:
            if isinstance(l, dict):
                parts.append(l.get("title") or "")
    except Exception:
        pass
    return " ".join(x for x in parts if x)

def source_headline(r, al=None):
    """A 4+ word headline from the cluster title, a source title, or the brief lead. Never invents wording."""
    import wire_check as WC
    cands = []
    def add(s):
        s = _plain(s or "", 220)
        if s and s not in cands:
            cands.append(s)
    add(r.get("title") or "")
    for a in al or []:
        add((a or {}).get("title") or "")
    try:
        raw = json.loads(r.get("links") or "[]") if isinstance(r.get("links"), str) else (r.get("links") or [])
        for l in raw:
            if isinstance(l, dict):
                add(l.get("title") or "")
    except Exception:
        pass
    bf = brief_fields(r.get("brief") or "")
    add(bf.get("what") or "")
    loc = _plain(r.get("location") or "", 80)
    good = [c for c in cands if not WC.thin_headline(c)]
    picked = None
    title = _plain(r.get("title") or "", 220)
    if title and not WC.thin_headline(title):
        picked = title
    elif good:
        picked = good[0]
    elif title and loc and not WC.thin_headline(f"{title} in {loc}"):
        picked = f"{title} in {loc}"
    elif (bf.get("what") or "") and loc:
        w = _plain(bf.get("what") or "", 180).rstrip(".")
        picked = f"{w} in {loc}"
        if WC.thin_headline(picked):
            picked = None
    if not picked:
        return title
    if len(picked) <= 110:
        return WC.headline(picked)[0]
    return WC.headline(picked[:109].rsplit(" ", 1)[0] + "…")[0]

def rule_tags(r, al=None):
    """Rule-based hashtags only. Does not call x_share.hashtags() (that queues the paid tag model).

    Always runs the result through wire_check.tags so the stored set is 3-5 tags that already
    pass the publish gate (short popular words, places, diseases, known entities). Never
    #News or #BlackoutNetwork.
    """
    import x_share
    import wire_check as WC
    item = _item_for_tags(r)
    raw = []
    try:
        raw = list(x_share._entity_first(item) or [])
    except Exception:
        traceback.print_exc(); raw = []
    raw = ["#" + str(t).lstrip("#") for t in raw
           if str(t).lstrip("#").lower() not in _TAG_BANNED]
    title = (r.get("title") or r.get("headline") or "")
    blob = _tag_text(r, al)
    k = WC.category(r.get("category") or item.get("category") or "", title, blob)
    try:
        lt = list(x_share.location_tags(item) or [])
    except Exception:
        lt = []
    out = WC.tags(raw, k, title, lt, text=blob)
    return out[:5]

def build_card(cid):
    """Render and cache the share card. Returns True when bytes were produced.
    A new story waits briefly for a high-priority photo lookup so the photo card can exist before publish;
    if the lookup does not finish, the designed map card is used (never the earth fallback)."""
    try:
        import share_card
        import story_photo
        if story_photo.card_has_photo(cid):
            return True
        if hasattr(share_card, "story_png_publish"):
            b = share_card.story_png_publish(cid)
        else:
            b = share_card.story_png(cid)
        return bool(b)
    except Exception:
        traceback.print_exc()
        return False

def brief_fields(brief):
    out = {}
    for key in ("WHAT", "WHERE", "WHEN", "CONFIDENCE"):
        m = re.search(rf"{key}:\s*(.*?)(?=(?:WHAT|WHERE|WHEN|CONFIDENCE):|$)", brief or "", re.S | re.I)
        if m:
            out[key.lower()] = " ".join(m.group(1).split()).strip()
    return out

def _plain(s, n=0):
    s = " ".join((s or "").split())
    s = re.sub(r"\s*\[[^\[\]]{2,200}\]", "", s).strip()
    return s[:n] if n else s

def _source_links(r, al):
    links = []
    try:
        raw = json.loads(r.get("links") or "[]") if isinstance(r.get("links"), str) else (r.get("links") or [])
    except Exception:
        raw = []
    for l in raw:
        if not isinstance(l, dict):
            continue
        u = str(l.get("url") or "").strip(); s = str(l.get("source") or l.get("s") or "Source").strip()
        if u.startswith(("http://", "https://")) and u not in {x["url"] for x in links}:
            links.append({"url": u, "label": s})
    for a in al or []:
        u = (a.get("source_url") or "").strip(); s = (a.get("source") or a.get("family") or "Source").strip()
        if u.startswith(("http://", "https://")) and u not in {x["url"] for x in links}:
            links.append({"url": u, "label": s})
    return links[:8]

def _related(r, limit=5):
    k = _src()
    if k is None: return []
    cid = r.get("cluster_id"); cat = r.get("category") or ""; loc = (r.get("location") or "").strip()
    out = []
    try:
        q = "SELECT cluster_id, title, location, rank, first_seen FROM clusters WHERE watchlist IN (0,1) AND cluster_id!=?"
        args = [cid]
        if cat:
            q += " AND category=?"; args.append(cat)
        q += " ORDER BY updated DESC LIMIT 40"
        for row in k.execute(q, args):
            d = dict(row)
            if loc and (d.get("location") or "") and loc.split(",")[0].lower() not in (d.get("location") or "").lower():
                if not (_toks(r.get("title")) & _toks(d.get("title"))):
                    continue
            out.append(d)
            if len(out) >= limit: break
    except Exception:
        pass
    finally:
        k.close()
    return out

def build_template(r, al):
    """Neutral wire write-up from scanner data only. No invented facts, quotes or numbers."""
    title = _plain(r.get("title") or "Story", 140)
    bf = brief_fields(r.get("brief") or "")
    what = _plain(bf.get("what") or "", 500)
    raw_where = (bf.get("where") or r.get("location") or "").strip()
    where = _plain(place_of({"title": r.get("title") or title, "location": raw_where}) or raw_where or place_of(r) or "", 200)
    when = _plain(bf.get("when") or "", 200)
    conf = _plain(bf.get("confidence") or r.get("confidence") or "", 80)
    loc = where or (r.get("location") or "").strip()
    rank = int(r.get("rank") or 0)
    lab = _band(rank)
    links = _source_links(r, al)
    officials = [a for a in (al or []) if a.get("official")]
    fams = []
    try:
        fams = json.loads(r.get("families") or "[]") if isinstance(r.get("families"), str) else (r.get("families") or [])
        if isinstance(fams, str): fams = [f for f in fams.split(",") if f]
    except Exception:
        fams = []
    n_fam = int(r.get("eff_families") or r.get("n_families") or len(fams) or 0)
    n_items = int(r.get("n_items") or len(al or []) or 0)
    first = _et(r.get("first_seen")); ev = _et(r.get("event_time")); upd = _et(r.get("updated"))
    # headlines from the sources we track (their words, attributed)
    heads = []
    seen = set()
    for a in (al or [])[:25]:
        ht = _plain(a.get("title") or "", 220)
        if not ht: continue
        k = _norm(ht)
        if k in seen: continue
        seen.add(k)
        src = _plain(a.get("source") or a.get("family") or "One source", 80)
        off = " (official)" if a.get("official") else ""
        tm = _et(a.get("event_time") or a.get("first_seen"))
        heads.append((src + off, tm, ht))

    headline = source_headline(r, al) or (title if len(title) <= 110 else (title[:109].rsplit(" ", 1)[0] + "…"))
    where_bit = f" in {loc}" if loc else ""
    when_bit = f", {when or ev or first}" if (when or ev or first) else ""
    lead = what or title
    if lead and not lead.endswith("."): lead += "."
    attrib = ""
    if n_fam:
        attrib = f" {n_fam} independent source{'s' if n_fam != 1 else ''} in our record {'are' if n_fam != 1 else 'is'} reporting this"
        if officials:
            names = []
            for a in officials[:3]:
                s = _plain(a.get("source") or "", 40)
                if s and s not in names: names.append(s)
            if names:
                attrib += ", including " + ", ".join(names)
        attrib += "."
    elif links:
        attrib = f" The reports we have come from {links[0]['label']}."
    else:
        attrib = " So far we have the scanner record only; a news outlet or official source has not been logged yet."

    what_happened = f"{lead}{(' The record places this' + where_bit + when_bit + '.') if (loc or when_bit) else ''}{attrib}"
    what_happened = " ".join(what_happened.split())

    know, dont = [], []
    if what: know.append(lead)
    if loc: know.append(f"The location in the record is {loc}.")
    if officials: know.append("At least one official source is among the reports we have logged.")
    if n_fam >= 2: know.append(f"{n_fam} independent sources are in the record.")
    elif n_fam == 1: dont.append("This has been reported by a single independent source so far and is not independently confirmed in our record.")
    else: dont.append("We do not yet have a second independent source.")
    if not officials: dont.append("No official source has been logged for this story yet.")
    if conf: know.append(f"The record marks confidence as {conf}.")
    dont.append("Later reports may add or revise details that are not in the record yet.")

    # timeline paragraphs
    paras = [what_happened]
    if heads:
        lines = []
        for src, tm, ht in heads[:8]:
            q = ht if ht.endswith((".", "?", "!", "…")) else ht + "."
            when_s = f" at {tm}" if tm else ""
            lines.append(f"{src} reported{when_s}: \"{q}\"")
        paras.append(" ".join(lines))
    if know:
        paras.append("What we know from the record: " + " ".join(know))
    if dont:
        paras.append("What we do not know yet: " + " ".join(dont))
    rel = _related(r)
    if rel:
        bits = []
        for d in rel:
            bits.append(_plain(d.get("title") or "", 90) + (f" ({_plain(d.get('location') or '', 40)})" if d.get("location") else ""))
        paras.append("Related stories we are also tracking: " + "; ".join(bits) + ".")
    if links:
        paras.append("Sources: " + "; ".join(f"{l['label']} ({l['url']})" for l in links) + ".")
    else:
        paras.append("We have not yet logged a source URL for this story.")

    body = "\n\n".join(paras)
    dek = (what[:180] if what and _norm(what) != _norm(title) else (f"A {lab.lower()}-risk story{where_bit}, from the reports we track." + (f" Logged {first}." if first else "")))
    dek = _plain(dek, 240)
    why = dek
    analysis = (" ".join(know[:2]) + " " + " ".join(dont[:2])).strip() or "We are working only from the reports logged for this story."
    rank_why = f"This is in the {lab.lower()} band on our 0–10 scale, based on the reach and confirmation of the reports we have."
    if n_fam < 2:
        rank_why += " It is waiting on a second independent source."
    risk_why = "Rank band for this story, from the reports we have; not a forecast."
    if_true = "If the reporting holds, later official or on-the-ground accounts should match the core facts above."
    if_false = "If the reporting is overstated or wrong, later official accounts or corrections will not match these early reports."
    what_to_do = "No action is needed." if rank <= 4 else ("Monitor official local guidance if you are in the affected area." if loc else "Monitor official guidance as more reports arrive.")
    confidence = "High" if (n_fam >= 3 and officials) else ("Medium" if n_fam >= 2 or officials else "Low")
    confidence_why = (("Official sources in the record include " + ", ".join(_plain(a.get("source") or "", 40) for a in officials[:3]) + ".") if officials
                      else "The reports we have are not from an official source yet.")
    if n_fam < 2:
        confidence_why += " This is not independently confirmed in our record."
    src_urls = [l["url"] for l in links]
    w = iso()
    note = {
        "headline": headline, "why_it_matters": why, "what_happened": what_happened, "analysis": _plain(analysis, 600),
        "rank_why": rank_why, "risk": lab, "risk_why": risk_why, "if_true": if_true, "if_false": if_false,
        "what_to_do": what_to_do, "confidence": confidence, "confidence_why": confidence_why,
        "sources": src_urls, "story": {
            "headline": title, "dek": dek,
            "sections": {"happened": body, "background": "", "analysis": _plain(analysis, 800),
                         "watch": what_to_do + " " + if_true},
            "sources": links, "written_at": w,
        },
        "written_at": w, "generated_at": w, "edition": "BLACKOUT.NETWORK write-up", "desk": True,
        "file": "story_writer_template", "writer": {"model": "template", "sources_read": 0},
        "place": loc,
    }
    return note

_NP_C = {"t": 0.0, "v": set()}
def _needs_paid_set():
    if time.time() - _NP_C["t"] < 3:
        return _NP_C["v"]
    with _LK:
        k = db()
        try:
            v = {r[0] for r in k.execute("SELECT cid FROM needs_paid")}
        finally:
            k.close()
    _NP_C.update(t=time.time(), v=v)
    return v

def _is_needs_paid(cid):
    return bool(cid) and cid in _needs_paid_set()

def _mark_needs_paid(cid, rank=0, title=""):
    with _LK:
        k = db()
        try:
            k.execute("INSERT OR REPLACE INTO needs_paid(cid, since, rank, title) VALUES(?,?,?,?)",
                      (cid, iso(), int(rank or 0), (title or "")[:200]))
            k.commit()
        finally:
            k.close()
    _NP_C["t"] = 0.0

def _clear_needs_paid(cid):
    with _LK:
        k = db()
        try:
            k.execute("DELETE FROM needs_paid WHERE cid=?", (cid,)); k.commit()
        finally:
            k.close()
    _NP_C["t"] = 0.0

def _legacy_set():
    with _LK:
        k = db()
        try:
            return {r[0] for r in k.execute("SELECT cid FROM legacy")}
        finally:
            k.close()

def _ready_row(cid):
    with _LK:
        k = db()
        try:
            r = k.execute("SELECT cid, kind, tags, card_ok FROM ready WHERE cid=?", (cid,)).fetchone()
            return dict(r) if r else None
        finally:
            k.close()

def ready_tags(cid):
    """Baked-in Share-to-X hashtags for this story, or []. Never raises."""
    if not cid:
        return []
    try:
        row = _ready_row(cid)
    except Exception:
        return []
    if not row:
        return []
    raw = row.get("tags")
    if not raw or raw in ("[]", "null"):
        return []
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    if not isinstance(v, list):
        return []
    return ["#" + str(t).lstrip("#") for t in v if t]

def has_paid_article(cid):
    """True when a desk brief or a paid API article (not a free template) is stored."""
    if not cid: return False
    if desk_covered(cid): return True
    n = note_for(cid)
    if not isinstance(n, dict): return False
    if n.get("file") == "story_writer_template": return False
    if (n.get("writer") or {}).get("model") == "template": return False
    return True

def has_writeup(cid):
    """True when a desk brief or a stored writer/template write-up exists (cards may still be building)."""
    if not cid: return False
    if desk_covered(cid): return True
    return note_for(cid) is not None

def is_packaged(cid):
    """True when a write-up is stored. Tags are recorded when we have them; a card may trail."""
    if not cid: return False
    if has_writeup(cid):
        row = _ready_row(cid)
        if row and (row.get("tags") or "").strip() not in ("", "[]", "null"):
            return True
        if desk_covered(cid):
            return True
        return True  # write-up is enough to render a full page; tags/card may follow
    return False

def allow(cid, archive=False):
    """Whether a story may appear on a public listing or API. Never raises.
    Once the gate is on, items need a stored write-up. New rank 5+ items (needs_paid)
    stay off the Wire until the paid article is stored. Items that later rise to 5+
    keep their template until the paid article is swapped in. Clusters snapshotted at
    boot_gate stay visible even if their tip template has not been rebuilt yet this
    boot (templates catch up in the worker). Archive is unchanged."""
    try:
        if archive or not cid:
            return True
        if not gate_on():
            return True
        if _is_needs_paid(cid) and not has_paid_article(cid):
            return False
        if has_writeup(cid) or is_packaged(cid) or has_paid_article(cid):
            return _card_ready(cid)
        if cid in _legacy_set_cached():
            return True
        return False
    except Exception:
        traceback.print_exc()
        return not gate_on()


def _card_ready(cid):
    """Nov 25 2026 (X cards): a story is not public until its share card is baked, so the first crawler fetch (X fetches
    the link seconds after the post) never hits a cold build. Queues the bake and holds the story for a few seconds;
    fails open if the card store is unavailable."""
    if os.environ.get("BN_CARD_GATE", "1") == "0":
        return True
    try:
        import wire_check as WC
        if not WC.story_cards_on():
            return True
    except Exception:
        if os.environ.get("BN_STORY_CARDS", "0") != "1":
            return True
    try:
        import share_card
        if share_card.card_baked(cid):
            return True
        share_card.bake_card(cid)
        # Fail open after queueing: holding every story with no stored card emptied the Wire and, with
        # one bake thread per story plus a photo fetch, OOM-killed the 2Gi box after #242 (10:40:19 AM ET).
        # The single bake worker still stores the map card; the poster can wait on card_baked if needed.
        return True
    except Exception:
        return True

_LEGACY_C = {"t": 0.0, "v": set()}
def _legacy_set_cached():
    if time.time() - _LEGACY_C["t"] < 5:
        return _LEGACY_C["v"]
    v = _legacy_set()
    _LEGACY_C.update(t=time.time(), v=v)
    return v

def filter_rows(rows, key="cluster_id", archive_key=None):
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            cid = r.get(key) or r.get("id") or r.get("cluster_id")
            arch = bool(r.get(archive_key)) if archive_key else False
        else:
            try:
                cid = r[key] if key in r.keys() else (r["id"] if "id" in r.keys() else None)
            except Exception:
                cid = None
            arch = False
            if archive_key:
                try: arch = bool(r[archive_key])
                except Exception: arch = False
        if allow(cid, archive=arch):
            out.append(r)
    return out

def live_clusters(hours=None, limit=4000):
    k = _src()
    if k is None: return []
    try:
        if hours:
            cut = iso(now() - timedelta(hours=hours))
            rows = [dict(r) for r in k.execute(
                "SELECT * FROM clusters WHERE watchlist IN (0,1) AND COALESCE(updated, first_seen)>=? ORDER BY COALESCE(updated, first_seen) DESC, cluster_id DESC LIMIT ?",
                (cut, limit))]
        else:
            rows = [dict(r) for r in k.execute(
                "SELECT * FROM clusters WHERE watchlist IN (0,1) ORDER BY COALESCE(updated, first_seen) DESC, cluster_id DESC LIMIT ?", (limit,))]
    except Exception:
        rows = []
    finally:
        k.close()
    try:
        import story_display as SD
        rows = [SD.apply(r) for r in rows]
        rows = [r for r in rows if SD.visible(r)]
    except Exception:
        pass
    return rows

def boot_gate():
    """Snapshot live cluster ids as legacy, then turn the publish gate on immediately.

    Tip templates are not built here. They continue in the worker via package_pending so a
    deploy-time tip pass (up to 800 package_one calls) cannot starve the paid writer. Cards
    also trail in the worker. Existing live items stay visible because they were grandfathered.
    New arrivals after this snapshot stay held until their write-up, tags and card are stored.
    """
    if STATE.get("gate_booted"):
        return
    rows = live_clusters(hours=None, limit=8000)
    at = iso()
    with _LK:
        k = db()
        try:
            for r in rows:
                k.execute("INSERT OR IGNORE INTO legacy(cid, at) VALUES(?,?)", (r["cluster_id"], at))
            k.commit()
        finally:
            k.close()
    _LEGACY_C.update(t=0, v=set())
    STATE["gate_booted"] = True
    if gate_wanted():
        STATE["gate_on"] = True
    log(f"publish gate on after grandfathering {len(rows)} live clusters; tip templates continue in the worker")

def _mark_held(cid, err, title="", rank=0):
    with _LK:
        k = db()
        try:
            r = k.execute("SELECT since, tries FROM held WHERE cid=?", (cid,)).fetchone()
            if r:
                k.execute("UPDATE held SET last_try=?, tries=?, err=?, title=?, rank=? WHERE cid=?",
                          (iso(), int(r["tries"] or 0) + 1, (err or "")[:400], title, rank, cid))
            else:
                k.execute("INSERT INTO held(cid, since, last_try, tries, alerted, err, title, rank) VALUES(?,?,?,?,0,?,?,?)",
                          (cid, iso(), iso(), 1, (err or "")[:400], title, rank))
            k.commit()
        finally:
            k.close()

def _clear_held(cid):
    with _LK:
        k = db()
        try:
            k.execute("DELETE FROM held WHERE cid=?", (cid,)); k.commit()
        finally:
            k.close()

def _backoff_ok(cid):
    with _LK:
        k = db()
        try:
            r = k.execute("SELECT last_try, tries FROM held WHERE cid=?", (cid,)).fetchone()
        finally:
            k.close()
    if not r: return True
    last = parse_t(r["last_try"]); n = int(r["tries"] or 0)
    if not last: return True
    wait = min(300, 5 * (2 ** min(n, 6)))
    return (now() - last).total_seconds() >= wait

def package_one(cid, row=None, al=None, build_card_now=False):
    """Build (or reuse) a write-up and store rule-based tags. Cards trail unless build_card_now is True.
    Returns True when the write-up is stored and the item may appear on the Wire."""
    if not cid: return False
    if has_writeup(cid) and is_packaged(cid):
        if has_paid_article(cid):
            _clear_needs_paid(cid)
        _repair_packaged(cid, row=row, al=al)
        _clear_held(cid); return True
    if not _backoff_ok(cid):
        return False
    try:
        if row is None or al is None:
            r, al2 = cluster(cid)
            row = row or r; al = al if al is not None else al2
        if not row:
            _mark_held(cid, "cluster gone"); return False
        kind = "template"
        if desk_covered(cid):
            kind = "desk"
        else:
            existing = note_for(cid)
            if existing and existing.get("file") != "story_writer_template":
                kind = "writer"
            elif existing and existing.get("file") == "story_writer_template":
                kind = "template"
            else:
                note = build_template(row, al or [])
                with _LK:
                    k = db()
                    try:
                        k.execute("INSERT OR REPLACE INTO briefs(cid, note, written_at, model, src_urls, alias_of, tokens_in, tokens_out, usd, rank, title) VALUES(?,?,?,?,?,NULL,0,0,0,?,?)",
                                  (cid, json.dumps(note, ensure_ascii=False), note["written_at"], "template",
                                   json.dumps(note.get("sources") or []), int(row.get("rank") or 0), row.get("title")))
                        k.commit()
                    finally:
                        k.close()
                _invalidate(cid)
                kind = "template"
        try:
            tags = rule_tags(row, al=al)
        except Exception:
            traceback.print_exc(); tags = []
        if not tags:
            _mark_held(cid, "no tags", row.get("title"), int(row.get("rank") or 0)); return False
        was_ready = _ready_row(cid) is not None
        if kind in ("desk", "writer") or has_paid_article(cid):
            _clear_needs_paid(cid)
        elif (kind == "template" and int(row.get("rank") or 0) >= cfg()["min_rank"]
              and cid not in _legacy_set_cached() and not was_ready):
            _mark_needs_paid(cid, int(row.get("rank") or 0), row.get("title"))
        card_ok = 0
        if build_card_now:
            try:
                card_ok = 1 if build_card(cid) else 0
            except Exception:
                traceback.print_exc(); card_ok = 0
            if not card_ok:
                tries = 0
                try:
                    with _LK:
                        k = db()
                        try:
                            r = k.execute("SELECT tries FROM held WHERE cid=?", (cid,)).fetchone()
                            tries = int((r["tries"] if r else 0) or 0)
                        finally:
                            k.close()
                except Exception:
                    tries = 0
                _mark_held(cid, "card not ready", row.get("title"), int(row.get("rank") or 0))
                if tries < 1:   # first failure: hold and retry. Second failure: publish anyway (map card / warm will follow).
                    return False
                log(f"card failed twice for {cid}, publishing without a stored card (map fallback; never the earth fallback)")
        with _LK:
            k = db()
            try:
                k.execute("INSERT OR REPLACE INTO ready(cid, kind, tags, card_ok, ready_at, title, rank) VALUES(?,?,?,?,?,?,?)",
                          (cid, kind, json.dumps(tags), card_ok, iso(), row.get("title"), int(row.get("rank") or 0)))
                k.commit()
            finally:
                k.close()
        _clear_held(cid)
        _invalidate(cid)
        return True
    except Exception as e:
        _mark_held(cid, f"{type(e).__name__}: {str(e)[:200]}", (row or {}).get("title"), int((row or {}).get("rank") or 0))
        traceback.print_exc()
        return False

def _repair_packaged(cid, row=None, al=None):
    """Refresh stored tags / a thin template headline so a held row can pass the existing gate.

    Does not loosen tag_ok or thin_headline. Only rewrites a template note's headline, and
    only replaces ready.tags when the stored set does not already yield 3 validated tags.
    """
    import wire_check as WC
    if not cid:
        return False
    if row is None or al is None:
        try:
            r, al2 = cluster(cid)
        except Exception:
            r, al2 = None, []
        row = row or r
        al = al if al is not None else al2
    if not row:
        return False
    changed = False
    title = source_headline(row, al) or (row.get("title") or "")
    k = WC.category(row.get("category") or "", row.get("title") or title, _tag_text(row, al))
    new_tags = []
    try:
        new_tags = rule_tags(row, al=al)
    except Exception:
        traceback.print_exc()
    old = _ready_row(cid)
    old_tags = []
    if old:
        try:
            old_tags = json.loads(old.get("tags") or "[]") if isinstance(old.get("tags"), str) else (old.get("tags") or [])
        except Exception:
            old_tags = []
    valid_old = WC.tags(old_tags, k, title, text=_tag_text(row, al))
    if len(valid_old) < 3 and len(new_tags) >= 3:
        with _LK:
            dbk = db()
            try:
                if old:
                    dbk.execute("UPDATE ready SET tags=? WHERE cid=?", (json.dumps(new_tags), cid))
                else:
                    dbk.execute("INSERT OR REPLACE INTO ready(cid, kind, tags, card_ok, ready_at, title, rank) VALUES(?,?,?,?,?,?,?)",
                                (cid, "template", json.dumps(new_tags), 0, iso(), row.get("title"), int(row.get("rank") or 0)))
                dbk.commit()
            finally:
                dbk.close()
        changed = True
    n = note_for(cid)
    if isinstance(n, dict) and n.get("file") == "story_writer_template":
        h = n.get("headline") or ""
        if WC.thin_headline(h) or WC.thin_headline(row.get("title") or ""):
            new_h = title
            if new_h and not WC.thin_headline(new_h) and new_h != h:
                n["headline"] = new_h
                if isinstance(n.get("story"), dict):
                    n["story"]["headline"] = new_h
                with _LK:
                    dbk = db()
                    try:
                        dbk.execute("UPDATE briefs SET note=? WHERE cid=?", (json.dumps(n, ensure_ascii=False), cid))
                        dbk.commit()
                    finally:
                        dbk.close()
                changed = True
    if changed:
        _invalidate(cid)
    return changed

def repair_packaged(max_n=40):
    """Re-tag and re-head already packaged live items that would still fail the gate. Free only."""
    if not templates_on():
        return 0
    n = 0
    for r in live_clusters(hours=cfg()["template_backfill_h"], limit=800):
        if n >= max_n:
            break
        cid = r.get("cluster_id")
        if not cid or not has_writeup(cid):
            continue
        if _repair_packaged(cid, row=r, al=None):
            n += 1
    return n

def package_pending(max_new=80, max_backfill=200):
    """Package newly arrived items first, then the visible tip (last activity), templates only. Returns counts."""
    if not templates_on():
        return {"new": 0, "backfill": 0}
    rows = live_clusters(hours=cfg()["template_backfill_h"], limit=4000)
    legacy = _legacy_set_cached()
    packaged = 0
    backfilled = 0
    for r in rows:
        cid = r["cluster_id"]
        if has_writeup(cid):
            if not is_packaged(cid):
                package_one(cid, row=r, build_card_now=False)
            continue
        is_new = cid not in legacy
        if is_new and packaged >= max_new:
            continue
        if not is_new and backfilled >= max_backfill:
            continue
        if not _backoff_ok(cid):
            continue
        ok = package_one(cid, row=r, build_card_now=False)
        if is_new:
            packaged += 1
        else:
            backfilled += 1
        if packaged >= max_new and backfilled >= max_backfill:
            break
    # A few trailing card builds, never blocking new write-ups
    warm_cards(n=5)
    return {"new": packaged, "backfill": backfilled}

def warm_cards(n=5):
    """Build share cards for packaged write-ups that do not have one yet. Failures are not held."""
    try:
        import wire_check as WC
        if not WC.story_cards_on():
            return
    except Exception:
        if os.environ.get("BN_STORY_CARDS", "0") != "1":
            return
    with _LK:
        k = db()
        try:
            rows = [r[0] for r in k.execute("SELECT cid FROM ready WHERE COALESCE(card_ok,0)=0 ORDER BY ready_at DESC LIMIT ?", (n,))]
        finally:
            k.close()
    for cid in rows:
        try:
            ok = bool(build_card(cid))
        except Exception:
            ok = False
        if ok:
            with _LK:
                k = db()
                try:
                    k.execute("UPDATE ready SET card_ok=1 WHERE cid=?", (cid,)); k.commit()
                finally:
                    k.close()

def check_held_alerts():
    """Log and flag any new item held more than 15 minutes."""
    cut = iso(now() - timedelta(minutes=15))
    with _LK:
        k = db()
        try:
            rows = list(k.execute("SELECT cid, since, tries, err, title, rank FROM held WHERE alerted=0 AND since<=? AND cid NOT IN (SELECT cid FROM legacy)", (cut,)))
            for r in rows:
                log(f"HELD 15m {r['cid']} rank={r['rank']} tries={r['tries']} {(r['title'] or '')[:80]} ({r['err'] or ''})")
                k.execute("UPDATE held SET alerted=1 WHERE cid=?", (r["cid"],))
            if rows:
                k.commit()
                STATE["held_alerts"] = int(STATE.get("held_alerts") or 0) + len(rows)
        finally:
            k.close()

def held_status():
    with _LK:
        k = db()
        try:
            rows = [dict(r) for r in k.execute("SELECT cid, since, last_try, tries, alerted, err, title, rank FROM held ORDER BY since")]
            n_ready = k.execute("SELECT COUNT(*) FROM ready WHERE card_ok=1").fetchone()[0]
            n_legacy = k.execute("SELECT COUNT(*) FROM legacy").fetchone()[0]
            n_tmpl = k.execute("SELECT COUNT(*) FROM briefs WHERE model='template'").fetchone()[0]
            return {"held": rows, "ready": n_ready, "legacy": n_legacy, "templates_written": n_tmpl,
                    "alerts": int(STATE.get("held_alerts") or 0)}
        finally:
            k.close()



def start(ready=lambda: True, paused=lambda: False):
    """Start the background thread. Templates and the publish gate run even when BN_WRITER=0 (the paid writer is off)."""
    if STATE["thread"] is not None: return False
    if _env("BN_TEMPLATES", "1") == "0" and _env("BN_WRITER", "1") == "0": return False
    t = threading.Thread(target=_writer_worker, args=(ready, paused), name="story-writer", daemon=True)
    t.start(); STATE["thread"] = t
    return True

# ---------------------------------------------------------------- admin status (read-only)
def status(n=20):
    c = cfg(); out = {"enabled": enabled(), "api_key_set": key_set(), "model": c["model"], "min_rank": c["min_rank"],
                      "daily_cap_usd": c["daily_usd"], "max_per_hour": c["max_per_hour"], "backfill_hours": c["backfill_h"],
                      "price_per_million": {"input": c["price_in"], "output": c["price_out"]},
                      "thread_alive": bool(STATE["thread"] and STATE["thread"].is_alive()),
                      **{k: STATE[k] for k in ("started", "last_scan", "last_error", "scans", "paused")}}
    try:
        with _LK:
            k = db()
            try:
                out["spend_today"] = spent_today(k); out["spend_today"]["day_et"] = et_day()
                out["ledger_untrusted"] = ledger_untrusted()
                out["spend_today_all_models"] = spent_all_today(k); out["spend_today_all_models"]["day_et"] = et_day()
                out["rewrites"] = rewrite_allowed()
                try: out["needs_paid"] = k.execute("SELECT COUNT(*) FROM needs_paid").fetchone()[0]
                except Exception: out["needs_paid"] = 0
                out["queue"] = [dict(r) for r in k.execute("SELECT id, cid, reason, status, enq_at, arrived_at, rank, title, err FROM jobs WHERE status IN ('queued','running','deferred') ORDER BY id")]
                out["recent"] = [dict(r) for r in k.execute("SELECT id, cid, reason, status, arrived_at, finished, latency_s, tokens_in, tokens_out, usd, calls, rank, title, err FROM jobs WHERE status NOT IN ('queued','running') ORDER BY id DESC LIMIT ?", (n,))]
                out["written_last_hour"] = written_last_hour(k)
                out["briefs"] = {"written": k.execute("SELECT COUNT(*) FROM briefs WHERE alias_of IS NULL AND model NOT LIKE 'alias%'").fetchone()[0],
                                 "aliases": k.execute("SELECT COUNT(*) FROM briefs WHERE alias_of IS NOT NULL OR model LIKE 'alias%'").fetchone()[0]}
                lat = [r[0] for r in k.execute("SELECT latency_s FROM jobs WHERE status='done' AND reason='new' AND latency_s IS NOT NULL ORDER BY id DESC LIMIT 50")]
                out["latency_new_s"] = {"n": len(lat), "median": sorted(lat)[len(lat) // 2] if lat else None, "max": max(lat) if lat else None}
            finally: k.close()
        out["gate_on"] = gate_on(); out["templates_on"] = templates_on(); out["api_enabled"] = api_enabled()
        try: out.update(held_status())
        except Exception: pass
    except Exception as e: out["db_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out
