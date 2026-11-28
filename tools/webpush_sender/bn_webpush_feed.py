#!/usr/bin/env python3
"""Web Push sender feed (Nov 24 2026, repaired Nov 27). Box only. Keeps two LOCAL files fresh so
webpush_notifier.py can send from a box whose own blackout.db is stale (the live Wire and the live
subscription DB are owned by Render now):
  1. render_subs.db     the Render-owned webpush.db, pulled over the signed GET /internal/sync/pull (read-only, hash-checked)
  2. live_clusters.db   a `clusters` table built from the PUBLIC https://blackout.network/api/alerts/feed
                        (falls back to /api/state if the slim feed is not live yet)
Never touches /workspace/blackout, blackout.db, render_mirror, scanner or push.py. Never prints keys, endpoints or secrets.
Usage: bn_webpush_feed.py once | loop"""
import os, sys, json, time, gzip, sqlite3, urllib.request, urllib.error
sys.path.insert(0, "/workspace/blackout")
D = "/workspace/webpush_box"
SUBS = os.path.join(D, "render_subs.db"); CL = os.path.join(D, "live_clusters.db"); HB = os.path.join(D, "feed_heartbeat.json")
LOG = os.path.join(D, "feed.log"); SITE = "https://blackout.network"
# Slim /api/alerts/feed first (small, usually fast). /api/state is a large page and often times out at 40s.
FEEDS = (("/api/alerts/feed", 25), ("/api/state", 90))

def log(m):
    with open(LOG, "a") as f: f.write(time.strftime("[%Y-%m-%dT%H:%M:%SZ] ", time.gmtime()) + m + "\n")
def jl(p, d):
    try: return json.load(open(p))
    except Exception: return d

def pull_subs(st):
    import render_sync as S                                      # read-only use of the signed client; nothing is pushed
    env = S.load_env(); cl = S.Client(env["BN_RENDER_URL"], env["BN_SYNC_SECRET"])
    code, body = cl.req("GET", "/internal/sync/manifest")
    if code != 200: raise RuntimeError(f"manifest HTTP {code}")
    h = (json.loads(body).get("owned") or {}).get("webpush.db")
    if not h or str(h).startswith("error"): raise RuntimeError("manifest has no webpush.db hash")
    if os.path.exists(SUBS) and st.get("subs_hash") == h: return False
    code, body = cl.req("GET", "/internal/sync/pull?file=webpush.db")
    if code != 200: raise RuntimeError(f"pull HTTP {code}")
    tmp = SUBS + ".tmp"
    with open(tmp, "wb") as f: f.write(gzip.decompress(body))
    c = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    try:
        ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"; n = c.execute("SELECT COUNT(*) FROM subs").fetchone()[0]
    finally: c.close()
    if not ok: os.unlink(tmp); raise RuntimeError("pulled webpush.db failed quick_check")
    os.chmod(tmp, 0o600); os.replace(tmp, SUBS); st["subs_hash"] = h; st["subs_n"] = n
    return True

def _fetch_json(path, timeout):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": "BLACKOUT.NETWORK webpush feed", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status != 200:
            raise RuntimeError(f"{path} HTTP {r.status}")
        return json.loads(r.read()), path

def _load_clusters():
    last = None
    for path, timeout in FEEDS:
        tries = 2 if path.endswith("/feed") else 2
        for i in range(tries):
            try:
                d, used = _fetch_json(path, timeout)
                rows = [x for x in (d.get("main") or []) if x.get("cluster_id") and not x.get("hidden") and not x.get("watchlist")
                        and x.get("published", True)]   # skip held/unready items; they reappear here once published
                if len(rows) < 20:
                    last = RuntimeError(f"{used} main has only {len(rows)} rows; keeping the previous file")
                    break
                return rows, used
            except Exception as ex:
                last = ex
                if i + 1 < tries:
                    time.sleep(1.5 * (i + 1))
        # 404 on the slim feed: not shipped yet, try /api/state
        if path.endswith("/feed") and isinstance(last, urllib.error.HTTPError) and last.code == 404:
            continue
        if path.endswith("/feed"):
            continue
    raise last if last else RuntimeError("cluster feed failed")

def pull_clusters(st):
    rows, used = _load_clusters()
    tmp = CL + ".tmp"
    if os.path.exists(tmp): os.unlink(tmp)
    c = sqlite3.connect(tmp)
    try:
        c.execute("""CREATE TABLE clusters(cluster_id TEXT PRIMARY KEY, title TEXT, category TEXT, location TEXT, rank INTEGER, score REAL,
                     eff_families INTEGER, high_at TEXT, updated TEXT, first_seen TEXT, watchlist INTEGER DEFAULT 0, published INTEGER DEFAULT 1)""")
        c.executemany("INSERT OR REPLACE INTO clusters VALUES(?,?,?,?,?,?,?,?,?,?,0,?)",
                      [(x["cluster_id"], x.get("title"), x.get("category"), x.get("location"), int(x.get("rank") or 0), x.get("score"),
                        int(x.get("eff_families") or 0), x.get("high_at"), x.get("updated"), x.get("first_seen"),
                        1 if x.get("published", True) else 0) for x in rows])
        c.commit()
    finally: c.close()
    os.chmod(tmp, 0o600); os.replace(tmp, CL); st["clusters_n"] = len(rows); st["clusters_src"] = used

def once():
    os.makedirs(D, mode=0o700, exist_ok=True)
    st = jl(HB, {}); res = {}
    for name, fn in (("subs", pull_subs), ("clusters", pull_clusters)):
        try:
            res[name] = fn(st); st[name + "_ok"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); st.pop(name + "_err", None)
        except Exception as ex:
            st[name + "_err"] = f"{type(ex).__name__}: {str(ex)[:120]}"; log(f"{name}: {st[name + '_err']}"); res[name] = "error"
    json.dump(st, open(HB + ".tmp", "w")); os.replace(HB + ".tmp", HB)
    return res

if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["once"])[0]
    if cmd == "once": print(json.dumps(once()))
    else:
        log("feed loop started")
        while True:
            try: once()
            except Exception as ex: log(f"cycle error: {ex!r}")
            time.sleep(30)
