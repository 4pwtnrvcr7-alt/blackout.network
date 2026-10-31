#!/usr/bin/env python3
"""Live Broadcasts add-on for blackout.network.

Separate collector (own daemon threads, own broadcasts.db). It is NOT part of scanner.py and never feeds scoring.
- Text: RSS feeds polled every TEXT_POLL_MIN with HTTP timeouts.
- Audio: short ffmpeg captures of public live news streams, transcribed locally on CPU with faster-whisper
  (separate venv /workspace/.whisperenv, run as a niced subprocess with a hard timeout).
- Keywords: keywords.json (editable via POST /api/broadcast_keywords); matching happens at read time so edits
  apply to new and existing clips.
"""
import hashlib, html, json, os, re, sqlite3, subprocess, sys, tempfile, threading, time, traceback
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "broadcasts.db")
KW = os.path.join(BASE, "keywords.json")
WHISPER_PY = "/workspace/.whisperenv/bin/python"
WHISPER_MODEL = "base.en"
TEXT_POLL_MIN = 7
AUDIO_EVERY_MIN = 15
AUDIO_SECONDS = 60
RETAIN_DAYS = 8
UA = "Mozilla/5.0 (X11; Linux x86_64) BlackoutNetwork/1.0 (private local monitor)"

GN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
TEXT_SOURCES = [
    {"name": "AP (via Google News search: site:apnews.com)", "short": "AP", "url": GN.format(q="site:apnews.com+when:1d"),
     "note": "AP has no official public RSS; this is a Google News search restricted to apnews.com. Links go through news.google.com."},
    {"name": "Reuters (via Google News search: site:reuters.com)", "short": "Reuters", "url": GN.format(q="site:reuters.com+when:1d"),
     "note": "Reuters retired its public RSS; this is a Google News search restricted to reuters.com. Links go through news.google.com."},
    {"name": "WESH 2 — top stories (RSS)", "short": "WESH 2", "url": "https://www.wesh.com/topstories-rss", "note": "Official station RSS."},
    {"name": "WESH 2 — local news (RSS)", "short": "WESH 2 local", "url": "https://www.wesh.com/local-news-rss", "note": "Official station RSS."},
    {"name": "Spectrum News 13 — Orlando news (RSS)", "short": "Spectrum 13", "url": "https://mynews13.com/services/contentfeed.fl%7Corlando%7Cnews.landing.rss", "note": "Official mynews13.com content feed."},
    {"name": "ClickOrlando / WKMG News 6 (RSS)", "short": "WKMG 6", "url": "https://www.clickorlando.com/arc/outboundfeeds/rss/category/news/?outputType=xml", "note": "Official station RSS (Arc outbound feed)."},
]
AUDIO_SOURCES = [
    {"name": "NPR live news stream (audio)", "short": "NPR live", "url": "https://npr-ice.streamguys1.com/live.mp3",
     "page": "https://www.npr.org/", "note": f"{AUDIO_SECONDS}s captured every {AUDIO_EVERY_MIN} min, transcribed locally (faster-whisper {WHISPER_MODEL}, CPU)."},
    {"name": "BBC World Service live stream (audio)", "short": "BBC WS live", "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service",
     "page": "https://www.bbc.co.uk/sounds/play/live:bbc_world_service", "note": f"{AUDIO_SECONDS}s captured every {AUDIO_EVERY_MIN} min, transcribed locally (faster-whisper {WHISPER_MODEL}, CPU)."},
]

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def et(d):
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("America/New_York")).strftime("%a %b %-d, %-I:%M %p") + " ET"
    except Exception: return iso(d)

def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS clips(id TEXT PRIMARY KEY, source TEXT, kind TEXT, title TEXT, text TEXT, link TEXT,
                 published TEXT, fetched TEXT, extra TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_clips_pub ON clips(published)")
    c.execute("""CREATE TABLE IF NOT EXISTS health(name TEXT PRIMARY KEY, kind TEXT, url TEXT, ok INTEGER, items INTEGER, new_items INTEGER,
                 last_checked TEXT, last_ok TEXT, error TEXT, note TEXT)""")
    return c

def set_health(name, kind, url, ok, items=0, new=0, error=None, note=None):
    c = db()
    try:
        prev = c.execute("SELECT last_ok FROM health WHERE name=?", (name,)).fetchone()
        t = iso(now())
        c.execute("INSERT OR REPLACE INTO health VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (name, kind, url, 1 if ok else 0, items, new, t, t if ok else (prev[0] if prev else None), (error or "")[:300] or None, note))
        c.commit()
    finally: c.close()

def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or ""); s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read(3_000_000)

def parse_date(s):
    if not s: return None
    try: return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception: pass
    try: return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception: return None

def poll_text():
    for src in TEXT_SOURCES:
        try:
            root = ET.fromstring(fetch(src["url"]))
            items = root.findall(".//item")
            c = db(); new = 0
            try:
                for it in items[:100]:
                    title = strip_html(it.findtext("title") or "")
                    link = (it.findtext("link") or "").strip()
                    desc = strip_html(it.findtext("description") or "")
                    if desc.startswith(title): desc = desc[len(title):].strip()
                    if src["url"].startswith("https://news.google.com"): desc = ""   # Google News descriptions just repeat the title
                    pub = parse_date(it.findtext("pubDate")) or now()
                    if not title or not link: continue
                    cid = hashlib.sha1((src["short"] + "|" + link).encode()).hexdigest()[:16]
                    cur = c.execute("INSERT OR IGNORE INTO clips VALUES(?,?,?,?,?,?,?,?,?)",
                                    (cid, src["short"], "text", title[:300], desc[:700], link, iso(pub), iso(now()), json.dumps({"feed": src["name"]})))
                    new += cur.rowcount
                c.commit()
            finally: c.close()
            set_health(src["name"], "text", src["url"], len(items) > 0, len(items), new, None if items else "feed returned 0 items", src["note"])
        except Exception as ex:
            set_health(src["name"], "text", src["url"], False, 0, 0, f"{type(ex).__name__}: {ex}", src["note"])

def audio_status():
    if not os.path.exists(WHISPER_PY): return False, f"off: {WHISPER_PY} not installed"
    if not any(os.access(os.path.join(p, "ffmpeg"), os.X_OK) for p in os.environ.get("PATH", "/usr/bin").split(":")): return False, "off: ffmpeg not found"
    return True, f"on: {AUDIO_SECONDS}s every {AUDIO_EVERY_MIN} min per stream, faster-whisper {WHISPER_MODEL} on CPU (2 threads, nice 15)"

def capture_audio():
    ok, why = audio_status()
    for src in AUDIO_SOURCES:
        if not ok: set_health(src["name"], "audio", src["url"], False, 0, 0, "audio transcription " + why, src["note"]); continue
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "clip.wav"); t0 = now()
            try:
                subprocess.run(["nice", "-n", "15", "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-t", str(AUDIO_SECONDS), "-i", src["url"],
                                "-ac", "1", "-ar", "16000", wav], timeout=AUDIO_SECONDS + 45, check=True, capture_output=True)
                p = subprocess.run(["nice", "-n", "15", WHISPER_PY, os.path.join(BASE, "transcribe.py"), wav, WHISPER_MODEL],
                                   timeout=300, check=True, capture_output=True, text=True)
                txt = json.loads(p.stdout.strip().splitlines()[-1])["text"]
                if not txt: raise RuntimeError("no speech detected in clip")
                link = f'{src["url"]}#captured={iso(t0)}'
                cid = hashlib.sha1((src["short"] + iso(t0)).encode()).hexdigest()[:16]
                c = db()
                try:
                    c.execute("INSERT OR IGNORE INTO clips VALUES(?,?,?,?,?,?,?,?,?)",
                              (cid, src["short"], "audio", f'{src["short"]} transcript · {et(t0)}', txt[:4000], link, iso(t0), iso(now()),
                               json.dumps({"stream": src["name"], "page": src["page"], "seconds": AUDIO_SECONDS})))
                    c.commit(); n = c.execute("SELECT COUNT(*) FROM clips WHERE source=?", (src["short"],)).fetchone()[0]
                finally: c.close()
                set_health(src["name"], "audio", src["url"], True, n, 1, None, src["note"])
            except Exception as ex:
                err = ex.stderr.decode(errors="ignore")[-200:] if isinstance(getattr(ex, "stderr", None), bytes) else (getattr(ex, "stderr", "") or "")[-200:]
                set_health(src["name"], "audio", src["url"], False, 0, 0, f"{type(ex).__name__}: {ex} {err}".strip(), src["note"])

def prune():
    c = db()
    try: c.execute("DELETE FROM clips WHERE published<?", (iso(now() - timedelta(days=RETAIN_DAYS)),)); c.commit()
    finally: c.close()

# ---- background threads (started once per server process; each loop re-imports the module so code edits apply) ----
def _mod():
    import importlib; return sys.modules.get("broadcasts") or importlib.import_module("broadcasts")
def _text_loop():
    while True:
        try: _mod().poll_text(); _mod().prune()
        except Exception: traceback.print_exc()
        time.sleep(TEXT_POLL_MIN * 60)
def _audio_loop():
    time.sleep(20)
    while True:
        try: _mod().capture_audio()
        except Exception: traceback.print_exc()
        time.sleep(AUDIO_EVERY_MIN * 60)
def start():
    if getattr(sys, "_bn_broadcasts_started", False): return
    sys._bn_broadcasts_started = True
    threading.Thread(target=_text_loop, daemon=True, name="bcast-text").start()
    threading.Thread(target=_audio_loop, daemon=True, name="bcast-audio").start()

# ---- keywords ----
WORD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 '\-]{0,38}[A-Za-z0-9]$|^[A-Za-z0-9]{2}$")
def load_kw():
    with open(KW) as f: return json.load(f)
def save_kw(d):
    tmp = KW + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, indent=1)
    os.chmod(tmp, 0o644); os.replace(tmp, KW)
def kw_regex(word): return re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(p) for p in word.split()) + r"(?![A-Za-z0-9])", re.I)
def matches(text, kw):
    out = []
    for cat in kw["categories"]:
        for w in cat["words"]:
            if kw_regex(w).search(text): out.append({"word": w, "cat": cat["id"]})
    return out

HOURS = {"1h": 1, "6h": 6, "24h": 24, "3d": 72, "7d": 168}
def api(qs):
    win = (qs.get("window") or ["24h"])[0]
    if win not in HOURS: return 400, {"error": f"window must be one of {list(HOURS)}"}
    src = (qs.get("source") or [""])[0]; kwf = (qs.get("kw") or [""])[0].lower()
    kw = load_kw()
    c = db()
    try:
        rows = c.execute("SELECT * FROM clips WHERE published>=? ORDER BY published DESC LIMIT 2000", (iso(now() - timedelta(hours=HOURS[win])),)).fetchall()
        health = [dict(r) for r in c.execute("SELECT * FROM health ORDER BY kind DESC, name")]
        srcs = [r[0] for r in c.execute("SELECT DISTINCT source FROM clips ORDER BY source")]
    finally: c.close()
    clips = []; counts = {}
    for r in rows:
        if src and r["source"] != src: continue
        m = matches(r["title"] + " " + (r["text"] or ""), kw)
        for x in m: counts[x["word"].lower()] = counts.get(x["word"].lower(), 0) + 1
        if kwf and not any(x["word"].lower() == kwf for x in m): continue
        pub = datetime.strptime(r["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        clips.append({"id": r["id"], "source": r["source"], "kind": r["kind"], "title": r["title"], "text": r["text"], "link": r["link"],
                      "published": r["published"], "published_et": et(pub), "matches": m, "extra": json.loads(r["extra"] or "{}")})
    for h in health:
        for k in ("last_checked", "last_ok"):
            h[k + "_et"] = et(datetime.strptime(h[k], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)) if h.get(k) else None
    ok, why = audio_status()
    return 200, {"generated_et": et(now()), "window": win, "windows": list(HOURS), "source": src, "kw": kwf, "total": len(clips),
                 "clips": clips[:300], "truncated": max(0, len(clips) - 300), "sources": srcs, "health": health, "keywords": kw,
                 "keyword_counts": counts, "audio_transcription": why, "text_poll_minutes": TEXT_POLL_MIN,
                 "note": "Informational only: Live Broadcasts never change threat scores or ranks."}

def handle_get(path, qs):
    start()
    if path == "/api/broadcasts": return api(qs)
    if path == "/api/broadcast_keywords": return 200, load_kw()
    return 404, {"error": "not found"}

def handle_post(path, d):
    start()
    if path != "/api/broadcast_keywords": return 404, {"error": "not found"}
    d = d or {}; act = d.get("action"); cat = str(d.get("category") or ""); w = re.sub(r"\s+", " ", str(d.get("word") or "")).strip()
    kw = load_kw(); cats = {c["id"]: c for c in kw["categories"]}
    if act not in ("add", "remove"): return 400, {"error": "action must be 'add' or 'remove'"}
    if cat not in cats: return 400, {"error": f"category must be one of {list(cats)}"}
    if not WORD_RE.match(w): return 400, {"error": "keyword must be 2-40 characters: letters, digits, spaces, hyphens or apostrophes"}
    words = cats[cat]["words"]; low = [x.lower() for x in words]
    if act == "add":
        for c2 in kw["categories"]:
            if w.lower() in [x.lower() for x in c2["words"]]: return 400, {"error": f"'{w}' is already in {c2['label']}"}
        if len(words) >= 60: return 400, {"error": "max 60 keywords per category"}
        words.append(w)
    else:
        if w.lower() not in low: return 400, {"error": f"'{w}' is not in {cats[cat]['label']}"}
        del words[low.index(w.lower())]
    save_kw(kw); return 200, {"status": "ok", "action": act, "category": cat, "word": w, "keywords": kw}
