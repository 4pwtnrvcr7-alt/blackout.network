"""Stored story places (Nov 23 2026, Matt pt1781u: "this is so simple").

Two jobs, both writing only story_places.db (Render-owned, handed to the next instance on every deploy):
  1. A memo of the map position heat_all already computes for each story, keyed by story id + a signature of the inputs
     (title, location field, source coordinates, geo.db row). A story is geocoded once; /api/signal/heat never re-geocodes it.
  2. New stories at ingest: one background thread reads blackout.db read-only, sends new stories' headline + location field +
     brief (10 per call) to the xAI API, and stores the most specific real place and its coordinates. The stored place is what the
     map shows for that story. "none" means the story names no place; it is left off the map.
Never touches scanner scoring, Wire ingest, blackout.db (read-only) or geo.db. The API key is read from the environment and never logged.

Env: BN_PLACES=0 kill switch (memo stays, LLM thread off) · BN_PLACES_MODEL (default grok-4.20-0309-non-reasoning)
     BN_PLACES_DAILY_USD (default 1.00) · BN_PLACES_BACKLOG_H (default 2: stories first seen up to this long before boot are read too)
"""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, threading, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB_REL = "story_places.db"
def _env(k, d): return (os.environ.get(k) or "").strip() or d
def db_path(): return _env("BN_PLACES_DB", os.path.join(HERE, DB_REL))
def log(*a): print("story_places:", *a, flush=True)

_LK = threading.RLock()
_CONN = {}
SCHEMA = """
CREATE TABLE IF NOT EXISTS memo(id TEXT PRIMARY KEY, sig TEXT, place TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS llm(id TEXT PRIMARY KEY, sig TEXT, level TEXT, place TEXT, cc TEXT, lat REAL, lon REAL, model TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS spend(day TEXT PRIMARY KEY, usd REAL DEFAULT 0, calls INTEGER DEFAULT 0, stories INTEGER DEFAULT 0);
"""
def _db():
    p = db_path()
    c = _CONN.get(p)
    if c is None:
        c = sqlite3.connect(p, timeout=15, check_same_thread=False); c.executescript(SCHEMA); _CONN[p] = c
    return c

def _iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------- memo of computed positions
_MEMO = {}          # id -> (sig, place dict)
_LLM = {}           # id -> place dict (tier global when the model found no place)
_LOADED = [False]

def _load():
    if _LOADED[0]: return
    with _LK:
        if _LOADED[0]: return
        try:
            c = _db()
            for i, s, p in c.execute("SELECT id, sig, place FROM memo"):
                try: _MEMO[i] = (s, json.loads(p))
                except Exception: pass
            for r in c.execute("SELECT id, level, place, cc, lat, lon FROM llm"):
                _LLM[r[0]] = _llm_place(*r[1:])
        except sqlite3.Error as ex:
            log("load failed:", ex)
        _LOADED[0] = True

def sig_of(item, g):
    g = g or {}
    return hashlib.sha1(json.dumps([item.get("title"), item.get("loc"), item.get("lat"), item.get("lon"), bool(item.get("brief")),
                                    g.get("located"), g.get("lat"), g.get("lon"), g.get("precision"), g.get("place"), g.get("reason_code")],
                                   default=str).encode()).hexdigest()[:16]

def memo_get(sid, sig):
    _load()
    m = _MEMO.get(sid)
    return m[1] if m and m[0] == sig else None

def memo_put_many(entries):
    """entries: [(id, sig, place dict)]. One transaction."""
    if not entries: return
    _load()
    with _LK:
        for i, s, p in entries: _MEMO[i] = (s, p)
        try:
            c = _db(); now = _iso()
            c.executemany("INSERT OR REPLACE INTO memo(id, sig, place, at) VALUES(?,?,?,?)", [(i, s, json.dumps(p), now) for i, s, p in entries])
            c.commit()
        except sqlite3.Error as ex:
            log("memo save failed:", ex)

def prune(keep_days=9):
    try:
        with _LK:
            c = _db(); cut = _iso(datetime.now(timezone.utc) - timedelta(days=keep_days))
            c.execute("DELETE FROM memo WHERE at < ?", (cut,)); c.commit()
    except sqlite3.Error:
        pass

# ---------------------------------------------------------------- LLM places for new stories
LEVELS = {"point": "point", "facility": "point", "city": "city", "town": "city", "neighborhood": "city", "county": "county",
          "state": "state", "province": "state", "region": "state", "country": "country"}

def _llm_place(level, place, cc, lat, lon):
    if level == "none" or lat is None or lon is None:
        return {"lat": None, "lon": None, "prec": "global", "tier": "global", "place": "", "cc": "", "rid": "", "how": "no place named (AI read)"}
    prec = LEVELS.get(level, "city")
    return {"lat": round(float(lat), 4), "lon": round(float(lon), 4), "prec": prec, "tier": "approx" if prec == "country" else "exact",
            "place": place or "", "cc": (cc or "").upper(), "rid": "", "how": "story place (AI read)"}

def llm_get(sid):
    _load()
    return _LLM.get(sid)

PROMPT = """You place news alerts on a map. For each story, read the headline, location field and brief, and return the single most
specific REAL place where the event itself happens (not where a statement was made about it, not a reporter's home city, not an
embassy's country). Prefer a city or town; else county; else state/province; else country. Use "none" ONLY when the story names
no place at all (e.g. a software bug, a market move, a celebrity remark). For a quake or storm at sea, give the named nearest place.
Never guess a city or county the text does not name: if only a state or country is named, answer at that level.
Return JSON: {"results":[{"id":"...","level":"city|county|state|country|none","place":"City, State/Province, Country",
"cc":"ISO 3166-1 alpha-2","lat":number,"lon":number}]}. lat/lon are the coordinates of that place (centre of the city, county,
state or country). One result per input id, same ids."""

def _clean(s, n): return re.sub(r"\s+", " ", (s or "")).strip()[:n]

def read_places(stories, api_key, model, api="https://api.x.ai/v1", timeout=90):
    """stories: [{id,title,loc,brief}] -> ({id: (level, place, cc, lat, lon)}, usage dict)."""
    msg = [{"role": "system", "content": PROMPT},
           {"role": "user", "content": json.dumps([{"id": s["id"], "headline": _clean(s.get("title"), 300), "location_field": _clean(s.get("loc"), 200),
                                                     "brief": _clean(s.get("brief"), 900)} for s in stories], ensure_ascii=False)}]
    body = json.dumps({"model": model, "messages": msg, "temperature": 0, "max_tokens": 200 * len(stories) + 200,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(api.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json", "User-Agent": "blackout-story-places/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r: d = json.loads(r.read())
    content = d["choices"][0]["message"]["content"]
    out = {}
    for x in (json.loads(content).get("results") or []):
        try:
            sid = str(x.get("id")); level = (x.get("level") or "none").lower().strip()
            if level == "none":
                out[sid] = ("none", "", "", None, None); continue
            lat, lon = float(x["lat"]), float(x["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0): continue
            out[sid] = (level, _clean(x.get("place"), 120), _clean(x.get("cc"), 2).upper(), lat, lon)
        except Exception:
            continue
    return out, d.get("usage") or {}

def _plausible(res):
    """The model's coordinates must sit in the country it names (offline polygons). Otherwise the story keeps the old position."""
    level, place, cc, lat, lon = res
    if level == "none": return True
    try:
        import geo
        pcc, _ = geo.gaz().pip(lat, lon)
        if pcc and cc and pcc.upper() != cc.upper(): return False
    except Exception:
        pass
    return True

def store_llm(results, sigs, model):
    now = _iso()
    with _LK:
        c = _db()
        for sid, res in results.items():
            if not _plausible(res):
                log("dropped implausible coordinates for", sid, res[1], res[2]); res = None
            if res is None:
                c.execute("INSERT OR REPLACE INTO llm(id, sig, level, place, cc, lat, lon, model, at) VALUES(?,?,?,?,?,?,?,?,?)",
                          (sid, sigs.get(sid, ""), "rejected", "", "", None, None, model, now))
                continue
            level, place, cc, lat, lon = res
            c.execute("INSERT OR REPLACE INTO llm(id, sig, level, place, cc, lat, lon, model, at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (sid, sigs.get(sid, ""), level, place, cc, lat, lon, model, now))
            _LLM[sid] = _llm_place(level, place, cc, lat, lon)
        c.commit()

ST = {"state": "off", "done": 0, "calls": 0, "errors": 0, "last_error": None, "last_run": None, "since": None}

def _spent_today():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r = _db().execute("SELECT usd FROM spend WHERE day=?", (day,)).fetchone()
    return day, float(r[0]) if r else 0.0

def _add_spend(day, usd, n):
    with _LK:
        c = _db()
        c.execute("INSERT INTO spend(day, usd, calls, stories) VALUES(?,?,1,?) ON CONFLICT(day) DO UPDATE SET usd=usd+excluded.usd, calls=calls+1, stories=stories+excluded.stories", (day, usd, n))
        c.commit()

def _pending(since, limit=200):
    p = os.path.join(HERE, "blackout.db")
    if not os.path.exists(p): return []
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=15); c.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in c.execute("SELECT cluster_id id, title, location loc, brief FROM clusters WHERE watchlist IN (0,1) AND first_seen >= ? "
                                            "ORDER BY first_seen DESC LIMIT 2000", (since,))]
    finally: c.close()
    have = set(r[0] for r in _db().execute("SELECT id FROM llm"))
    return [r for r in rows if r["id"] not in have][:limit]

def run_once(batch=10):
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    if not key: ST["state"] = "idle (no API key)"; return 0
    model = _env("BN_PLACES_MODEL", "grok-4.20-0309-non-reasoning")
    budget = float(_env("BN_PLACES_DAILY_USD", "1.0"))
    todo = _pending(ST["since"])
    n = 0
    for k in range(0, len(todo), batch):
        day, spent = _spent_today()
        if spent >= budget: ST["state"] = "paused (daily budget)"; break
        chunk = todo[k:k + batch]
        try:
            res, usage = read_places(chunk, key, model)
            usd = (usage.get("prompt_tokens", 0) * 1.25 + usage.get("completion_tokens", 0) * 2.5) / 1e6
            _add_spend(day, usd, len(chunk)); ST["calls"] += 1
            store_llm(res, {}, model); n += len(res); ST["done"] += len(res)
        except Exception as ex:
            ST["errors"] += 1; ST["last_error"] = str(ex)[:160]; log("read failed:", str(ex)[:160]); break
    ST["last_run"] = _iso()
    return n

def start(ready=lambda: True, paused=lambda: False):
    if _env("BN_PLACES", "1") == "0": ST["state"] = "off"; return
    hours = float(_env("BN_PLACES_BACKLOG_H", "2"))
    ST["since"] = _iso(datetime.now(timezone.utc) - timedelta(hours=hours)); ST["state"] = "running"
    def _places_run():     # name must not contain 'loop' (render_app blocks threads whose target is named *loop*)
        warmed = False
        while True:
            if not warmed and ready():
                try:      # build the map feed once in the background so the first visitor does not wait for it
                    import signal_map; signal_map.heat_payload(); warmed = True
                except Exception as ex:
                    log("warm failed:", str(ex)[:160]); warmed = True
            try:
                if ready() and not paused():
                    if run_once(): 
                        try:
                            import realtime; realtime.bust()
                        except Exception: pass
            except Exception as ex:
                ST["errors"] += 1; ST["last_error"] = str(ex)[:160]
            time.sleep(30)
    threading.Thread(target=_places_run, name="story_places", daemon=True).start()

def status():
    _load()
    try:
        day, spent = _spent_today()
        n = _db().execute("SELECT level, COUNT(*) FROM llm GROUP BY level").fetchall()
    except sqlite3.Error:
        day, spent, n = None, None, []
    return {**ST, "memo": len(_MEMO), "llm": dict(n), "spent_today_usd": round(spent or 0, 4), "day": day}
