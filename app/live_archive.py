"""Live Archive add-on: a timestamped log of what was live on the dashboard (no audio/video is recorded here).
Every 5 min it reads (read-only) streams.db (YouTube channels on air), broadcasts.db (live audio/feed sources up/down),
netstatus.db (each monitored service's latest status) and the Radio tab's stream status, and keeps one row per
"session": first seen, last seen, ended. Writes only live_archive.db (90-day retention). The panel is injected into the
Live Streams, Live Broadcasts, Network Status and Radio tabs by live_archive_static/app.js.
Never touches scanner.py, scoring, push.py, jets.py, config.json or blackout.db."""
import builtins, json, os, re, sqlite3, threading, time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "live_archive.db")
STATIC = os.path.join(BASE, "live_archive_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
POLL_S = 300; KEEP_DAYS = 90; ET = ZoneInfo("America/New_York")
SECTIONS = {"streams": "Live Streams", "bcast": "Live Broadcasts", "net": "Network Status", "radio": "Radio", "finance": "Finance (daily closes, written by finance.py)"}
S = getattr(builtins, "_bn_live_archive", None)
if S is None: S = builtins._bn_live_archive = {"started": False, "last": None, "err": None}

def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def ro(name): c = sqlite3.connect(f"file:{os.path.join(BASE, name)}?mode=ro", uri=True, timeout=10); c.row_factory = sqlite3.Row; return c
def rw():
    c = sqlite3.connect(DB, timeout=15); c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT, key TEXT, title TEXT, channel TEXT,
                 url TEXT, status TEXT, first_seen TEXT, last_seen TEXT, ended INTEGER DEFAULT 0)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_la ON sessions(section, last_seen)"); c.execute("CREATE INDEX IF NOT EXISTS ix_lk ON sessions(section, key, ended)")
    return c

def snap_streams():
    import streams_common as SC
    c = ro("streams.db")
    try: rows = c.execute("SELECT channel_id, video_id, title FROM live WHERE live=1").fetchall()
    finally: c.close()
    return [{"key": "yt:" + r["video_id"], "title": r["title"] or "", "channel": (SC.CH.get(r["channel_id"]) or {}).get("name", r["channel_id"]),
             "url": f"https://www.youtube.com/watch?v={r['video_id']}", "status": "live"} for r in rows]

def snap_bcast():
    c = ro("broadcasts.db")
    try: rows = c.execute("SELECT name, kind, url, ok, error FROM health").fetchall()
    finally: c.close()
    return [{"key": f"bc:{r['name']}:{'up' if r['ok'] else 'down'}", "title": r["name"], "channel": r["kind"], "url": r["url"],
             "status": "up" if r["ok"] else ("down: " + (r["error"] or "")[:120])} for r in rows]

NUM = re.compile(r"\b\d+ ms\b")
def snap_net():
    c = ro("netstatus.db")
    try: rows = c.execute("SELECT c.* FROM checks c JOIN (SELECT src, MAX(ts) m FROM checks GROUP BY src) x ON c.src=x.src AND c.ts=x.m").fetchall()
    finally: c.close()
    return [{"key": f"ns:{r['src']}:{r['level']}", "title": r["src"], "channel": r["grp"], "url": r["url"],
             "status": f"level {r['level']}: " + NUM.sub("", r["status"] or "").replace(" in ", " ").strip()} for r in rows]

def snap_radio():
    import radio_common as RC
    try: st = json.load(open(os.path.join(BASE, "logs", "radio_check.json")))["status"]   # written by radio.py's 5-min stream check
    except Exception: st = {}
    rs = RC.read_status().get("streams", {}); out = []
    for s in RC.DIRECT:
        v = st.get(s["id"])
        if v is None: continue
        out.append({"key": f"rd:{s['id']}:{'up' if v.get('ok') else 'down'}", "title": s["name"], "channel": s["group"], "url": s["url"],
                    "status": "on air" if v.get("ok") else "offline: " + str(v.get("err", ""))[:100]})
    for r in RC.RELAYS:
        w = rs.get(r["id"]) or {}
        if w.get("running") and w.get("tuned"):
            t = w["tuned"]; out.append({"key": f"rd:{r['id']}:{t['khz']}:{t['mode']}", "title": t["label"], "channel": "KiwiSDR relay · " + ((w.get("receiver") or {}).get("host") or ""),
                                        "url": RC.twente(t["khz"], t["mode"]), "status": f"relaying {t['khz']} kHz {t['mode'].upper()}"})
    return out

SNAP = {"streams": snap_streams, "bcast": snap_bcast, "net": snap_net, "radio": snap_radio}

def poll():
    now = iso(); c = rw()
    try:
        for sec, fn in SNAP.items():
            try: cur = {x["key"]: x for x in fn()}
            except Exception as ex: print(f"live_archive {sec}:", ex, flush=True); continue
            open_ = {r["key"]: r for r in c.execute("SELECT id, key FROM sessions WHERE section=? AND ended=0", (sec,))}
            for k, x in cur.items():
                if k in open_: c.execute("UPDATE sessions SET last_seen=?, title=?, status=? WHERE id=?", (now, x["title"], x["status"], open_[k]["id"]))
                else: c.execute("INSERT INTO sessions(section,key,title,channel,url,status,first_seen,last_seen,ended) VALUES(?,?,?,?,?,?,?,?,0)",
                                (sec, k, x["title"], x["channel"], x["url"], x["status"], now, now))
            for k, r in open_.items():
                if k not in cur: c.execute("UPDATE sessions SET ended=1 WHERE id=?", (r["id"],))
        c.execute("DELETE FROM sessions WHERE last_seen<?", (iso(datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)),))
        c.commit(); S["last"] = now; S["err"] = None
    finally: c.close()

def _loop():
    time.sleep(20)
    try: backfill_net()
    except Exception as ex: print("live_archive backfill:", ex, flush=True)
    while True:
        try: poll()
        except Exception as ex: S["err"] = str(ex)[:200]; print("live_archive:", ex, flush=True)
        time.sleep(POLL_S)
if not S["started"] and os.environ.get("BN_LIVE_ARCHIVE_POLLER") == "1" and not os.environ.get("BN_WEB_ONLY"):   # radio_archive.py runs the poller
    S["started"] = True; threading.Thread(target=_loop, daemon=True, name="live-archive").start()

def query(qs):
    g = lambda k, d="": ((qs.get(k) or [d])[0] or d).strip()
    sec = g("section"); day = g("date"); q = g("q").lower()[:80]
    if sec and sec not in SECTIONS: return 400, {"error": "section must be one of " + ", ".join(SECTIONS)}
    try: d0 = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ET) if day else datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError: return 400, {"error": "date must be YYYY-MM-DD"}
    a, b = iso(d0.astimezone(timezone.utc)), iso((d0 + timedelta(days=1)).astimezone(timezone.utc))
    if not os.path.exists(DB): return 200, {"date": d0.strftime("%Y-%m-%d"), "items": [], "days": [], "note": "no archive yet"}
    c = ro("live_archive.db")
    try:
        sql = "SELECT * FROM sessions WHERE first_seen<? AND last_seen>=?"; args = [b, a]
        if sec: sql += " AND section=?"; args.append(sec)
        if q: sql += " AND (lower(title) LIKE ? OR lower(channel) LIKE ? OR lower(status) LIKE ?)"; args += [f"%{q}%"] * 3
        items = [dict(r) for r in c.execute(sql + " ORDER BY first_seen DESC LIMIT 500", args)]
        days = [r[0] for r in c.execute("SELECT DISTINCT substr(first_seen,1,10) FROM sessions" + (" WHERE section=?" if sec else "") + " ORDER BY 1 DESC LIMIT 120", [sec] if sec else [])]
        first = c.execute("SELECT MIN(first_seen) FROM sessions").fetchone()[0]
    finally: c.close()
    return 200, {"date": d0.strftime("%Y-%m-%d"), "section": sec or None, "q": q, "items": items, "days_utc": days, "since": first,
                 "poll_s": POLL_S, "keep_days": KEEP_DAYS, "last_poll": S["last"], "sections": SECTIONS}

def handle_get(path, qs):
    n = path[len("/api/live_archive/"):] if path.startswith("/api/live_archive/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/live_archive": return query(qs)
    return 404, {"error": "not found"}

def backfill_net():
    """One-time replay of netstatus.db history (it keeps its own check log) so the archive starts when monitoring started."""
    c = rw()
    try:
        if c.execute("SELECT COUNT(*) FROM sessions WHERE section='net'").fetchone()[0]: return 0
        n = ro("netstatus.db")
        try: rows = n.execute("SELECT * FROM checks ORDER BY ts").fetchall()
        finally: n.close()
        open_ = {}; added = 0
        for r in rows:
            src = r["src"]; key = f"ns:{src}:{r['level']}"; st = f"level {r['level']}: " + NUM.sub("", r["status"] or "").replace(" in ", " ").strip()
            cur = open_.get(src)
            if cur and cur[0] == key: c.execute("UPDATE sessions SET last_seen=?, status=? WHERE id=?", (r["ts"], st, cur[1])); continue
            if cur: c.execute("UPDATE sessions SET ended=1 WHERE id=?", (cur[1],))
            i = c.execute("INSERT INTO sessions(section,key,title,channel,url,status,first_seen,last_seen,ended) VALUES('net',?,?,?,?,?,?,?,0)",
                          (key, src, r["grp"], r["url"], st, r["ts"], r["ts"])).lastrowid
            open_[src] = (key, i); added += 1
        c.commit(); return added
    finally: c.close()
