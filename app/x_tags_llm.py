"""Story-specific hashtags from the xAI API, cached per story id (Nov 25 2026, Matt pt1873u).

Never runs inside a request: x_share.hashtags() calls lookup(), which returns cached tags at once or queues ONE
background generation and returns None so the caller uses the rule-based extractor.

Cost (Matt, Nov 25): recurring spend stays near zero.
  - Only rank 5+ stories are sent to the API; everything else is rule-based only.
  - Model defaults to grok-4.20-0309-non-reasoning (cheapest non-reasoning).
  - Hard daily cap $0.10 (ET day). Spend and the tag cache live in xtags.db (Render-owned, survives deploys).
  - One API call per story ever: a row is written after the attempt (ok, invalid, or error). A skip for the
    daily cap is not an attempt, so the story can be tried the next day.

Every LLM tag set is validated against the story text (no invented names), at least 2 specific tags or the
result is discarded (rules used instead). #War / #Conflict count as generic unless the story is armed conflict.
XAI_API_KEY is read from the environment only (never logged or printed).

Env: XAI_API_KEY, BN_XTAGS=0 kill switch, BN_XTAGS_MODEL, BN_XTAGS_API, BN_XTAGS_DAILY_USD (default 0.10),
     BN_XTAGS_PRICE_IN/_OUT (default 1.25 / 2.50 per million), BN_XTAGS_DB (default <app>/xtags.db).
"""
from __future__ import annotations
import json, os, re, sqlite3, sys, threading, time, urllib.request, queue
from datetime import datetime
from zoneinfo import ZoneInfo

_CACHE = {}          # cid -> (status, [tags] or [])
_PENDING = set()
_Q = queue.Queue(maxsize=400)
_LOCK = threading.Lock()
_STARTED = False
HERE = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
GENERIC = {"#news", "#worldnews", "#breaking", "#breakingnews"}
SOFT_GENERIC = {"#war", "#conflict"}
ALLOWED_SECTOR = {"biotech", "stocks", "markets", "cybersecurity", "cyberattack", "war", "outbreak", "weather", "economy", "energy", "earthquake",
                  "wildfire", "flood", "tornado", "hurricane", "ransomware", "databreach", "cve", "politics", "election", "space", "science", "health", "crime",
                  "airstrike", "dronestrike", "missilestrike", "ukrainewar", "gaza", "israel", "russia", "ebola", "bankruptcy", "merger", "ipo",
                  "sanctions", "nucleartests", "nucleartestveterans"}
_ARMED_RX = re.compile(
    r"\b(missile strikes?|missile attacks?|airstrikes?|air strikes?|artillery|shelling|invasion|"
    r"drone (?:attack|strike)s?|aerial attacks?|struck in)\b",
    re.I,
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS tags(
  cid TEXT PRIMARY KEY,
  status TEXT,
  tags TEXT,
  model TEXT,
  tokens_in INTEGER DEFAULT 0,
  tokens_out INTEGER DEFAULT 0,
  usd REAL DEFAULT 0,
  rank INTEGER,
  called_at TEXT
);
CREATE TABLE IF NOT EXISTS spend(
  day TEXT PRIMARY KEY,
  usd REAL DEFAULT 0,
  tokens_in INTEGER DEFAULT 0,
  tokens_out INTEGER DEFAULT 0,
  calls INTEGER DEFAULT 0
);
"""


def _enabled():
    if os.environ.get("BN_XTAGS", "1") == "0":
        return False
    return bool((os.environ.get("XAI_API_KEY") or "").strip())


def db_path():
    return os.environ.get("BN_XTAGS_DB") or os.path.join(HERE, "xtags.db")


def et_day(d=None):
    return (d or datetime.now(ET)).astimezone(ET).date().isoformat()


def _cfg():
    def f(k, d):
        try:
            return float(os.environ.get(k) or d)
        except (TypeError, ValueError):
            return d
    return {
        "model": (os.environ.get("BN_XTAGS_MODEL") or "grok-4.20-0309-non-reasoning").strip(),
        "api": (os.environ.get("BN_XTAGS_API") or os.environ.get("BN_WRITER_API") or "https://api.x.ai/v1").rstrip("/"),
        "daily_usd": f("BN_XTAGS_DAILY_USD", 0.10),
        "price_in": f("BN_XTAGS_PRICE_IN", 1.25),
        "price_out": f("BN_XTAGS_PRICE_OUT", 2.50),
    }


def _db():
    p = db_path()
    c = sqlite3.connect(p, timeout=15)
    c.executescript(SCHEMA)
    return c


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _armed(title, brief, loc):
    return bool(_ARMED_RX.search(f"{title or ''} {brief or ''} {loc or ''}"))


def _generics(title, brief, loc):
    g = set(GENERIC)
    if not _armed(title, brief, loc):
        g |= SOFT_GENERIC
    return g


def _grounded(tag, text_norm, rule_n, generics):
    n = tag[1:].lower()
    if tag.lower() in generics:
        return True
    if n in text_norm or n in ALLOWED_SECTOR or n in rule_n:
        return True
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", tag[1:])
    if len(parts) >= 2 and all(_norm(p) in text_norm for p in parts if len(p) > 1):
        return True
    return False


def validate(tags, title, brief, loc, rule=None):
    """Keep only tags grounded in the story. Require 3–5 tags with at least 2 specific (non-generic) ones."""
    text = _norm(f"{title} {brief} {loc}")
    rule_n = {_norm(t) for t in (rule or [])}
    generics = _generics(title, brief, loc)
    out, n_gen = [], 0
    for raw in tags or []:
        t = "#" + re.sub(r"[^A-Za-z0-9]", "", str(raw))
        if len(t) < 3 or len(t) > 31 or t in out:
            continue
        if t.lower() in generics:
            n_gen += 1
            if n_gen > 1:
                continue
        elif not _grounded(t, text, rule_n, generics):
            continue
        out.append(t)
    out = out[:5]
    specific = [t for t in out if t.lower() not in generics]
    if len(out) < 3 or len(specific) < 2:
        return None
    return out


PROMPT = ("You write hashtags for one news item on a threat-monitoring site. Return ONLY JSON: {\"tags\":[\"#CamelCase\", ...]} with 3 to 5 hashtags.\n"
          "Rules: name the SPECIFIC things in the story, most specific first: people (full name, no job title — #PeteHegseth not #WarPeteHegseth or #SecretaryPeteHegseth; "
          "resolve a surname in the title from the body), organizations, companies, hardware or systems (#NASAMS, #F16), and places (use the location field; city then country). "
          "Then a specific topic noun phrase when there is one (#NuclearTestVeterans). AT MOST ONE sector tag, and only when it fits. "
          "#War and #Conflict are for armed conflict only (a strike, invasion, or attack that happened) — not an arms package, aid, inquiry, or nuclear test veterans' records. "
          "Generic tags (#News #WorldNews #Breaking #BreakingNews) are a LAST RESORT and at most one. At least two tags must be specific. "
          "Never invent a name that is not in the text. No spaces or punctuation inside a tag.")


def _call(title, brief, loc):
    """Returns (tags, tokens_in, tokens_out). Never logs the key or the body."""
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    c = _cfg()
    body = {"model": c["model"], "temperature": 0, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Title: {title}\nLocation field: {loc or '-'}\nSummary: {(brief or '')[:900]}"}]}
    req = urllib.request.Request(c["api"] + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "blackout-network-xtags/1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    txt = d["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    tags = json.loads(m.group(0)).get("tags") or []
    u = d.get("usage") or {}
    tin = int(u.get("prompt_tokens") or 0)
    tout = int(u.get("completion_tokens") or 0)
    return tags, tin, tout


def _cost(tin, tout):
    c = _cfg()
    return round(tin * c["price_in"] / 1e6 + tout * c["price_out"] / 1e6, 6)


def _load():
    try:
        db = _db()
        for cid, status, tags in db.execute("SELECT cid, status, tags FROM tags"):
            try:
                _CACHE[cid] = (status, json.loads(tags) if tags else [])
            except Exception:
                _CACHE[cid] = (status, [])
        db.close()
    except Exception:
        pass


def _spent_today():
    db = _db()
    try:
        r = db.execute("SELECT usd, calls FROM spend WHERE day=?", (et_day(),)).fetchone()
        return (float(r[0]), int(r[1])) if r else (0.0, 0)
    finally:
        db.close()


def _add_spend(tin, tout, usd):
    db = _db()
    try:
        db.execute(
            "INSERT INTO spend(day, usd, tokens_in, tokens_out, calls) VALUES(?,?,?,?,1) "
            "ON CONFLICT(day) DO UPDATE SET usd=usd+excluded.usd, tokens_in=tokens_in+excluded.tokens_in, "
            "tokens_out=tokens_out+excluded.tokens_out, calls=calls+1",
            (et_day(), usd, tin, tout),
        )
        db.commit()
    finally:
        db.close()


def _store(cid, status, tags, tin, tout, usd, rank):
    tags = tags or []
    db = _db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO tags(cid, status, tags, model, tokens_in, tokens_out, usd, rank, called_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, status, json.dumps(tags), _cfg()["model"], tin, tout, usd, rank or 0,
             datetime.now(ET).isoformat(timespec="seconds")),
        )
        db.commit()
    finally:
        db.close()
    with _LOCK:
        _CACHE[cid] = (status, list(tags))


def already_called(cid):
    if cid in _CACHE:
        return True
    try:
        db = _db()
        row = db.execute("SELECT 1 FROM tags WHERE cid=?", (cid,)).fetchone()
        db.close()
        return bool(row)
    except Exception:
        return False


def _worker():
    while True:
        cid, title, brief, loc, rule, rank = _Q.get()
        try:
            if already_called(cid):
                continue
            c = _cfg()
            spent, _calls = _spent_today()
            if spent >= c["daily_usd"]:
                print("x_tags_llm: daily cap reached, skipping", cid, file=sys.stderr)
                continue   # not an attempt — retry tomorrow
            raw, tin, tout = _call(title, brief, loc)
            usd = _cost(tin, tout)
            _add_spend(tin, tout, usd)
            tags = validate(raw, title, brief, loc, rule)
            _store(cid, "ok" if tags else "invalid", tags or [], tin, tout, usd, rank)
            if tags:
                print("x_tags_llm: cached", cid, " ".join(tags), file=sys.stderr)
            else:
                print("x_tags_llm: invalid (need 2 specific tags), using rules", cid, file=sys.stderr)
        except Exception as e:   # never logs the key or the request
            try:
                _store(cid, "error", [], 0, 0, 0.0, rank)
            except Exception:
                pass
            print("x_tags_llm: generation failed:", type(e).__name__, file=sys.stderr)
        finally:
            _PENDING.discard(cid)


def _start():
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    _load()
    threading.Thread(target=_worker, name="xtags-0", daemon=True).start()


def lookup(cid, title, brief, loc, rule=None, rank=None):
    """Cached validated LLM tags for this story, else None (and a background generation may be queued).

    Rank < 5 is rule-based only. A story already in xtags.db is never called again.
    """
    if not cid or not re.fullmatch(r"[0-9a-f]{16}", str(cid)):
        return None
    _start()
    hit = _CACHE.get(cid)
    if hit:
        if hit[0] == "ok" and hit[1]:
            got = validate(hit[1], title, brief, loc, rule)
            if got:
                return list(got)
        return None
    if not _enabled():
        return None
    try:
        rnk = int(rank) if rank is not None and rank != "" else 0
    except (TypeError, ValueError):
        rnk = 0
    if rnk < 5:
        return None
    if cid not in _PENDING:
        try:
            _PENDING.add(cid)
            _Q.put_nowait((cid, title, brief, loc, rule, rnk))
        except Exception:
            _PENDING.discard(cid)
    return None
