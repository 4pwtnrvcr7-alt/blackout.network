"""Live Streams add-on: curated YouTube news channels, keyless live detection (public /streams pages, every 10 min, 2 at a time),
continuous-watch worker (streams_worker.py under /workspace/.whisperenv) and the tab's API. Writes only streams.db.
Never writes blackout.db, never touches scoring, scanner.py or push.py."""
import builtins, json, os, re, subprocess, threading, time, urllib.request, concurrent.futures as cf
from collections import Counter
from datetime import datetime, timezone, timedelta
import streams_common as SC
BASE = SC.BASE; PIDF = os.path.join(BASE, "logs", "streams_worker.pid"); CHECK_MIN = 10
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36", "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"}
ST = getattr(builtins, "_bn_streams", None)
if ST is None: ST = builtins._bn_streams = {"started": False, "wake": threading.Event(), "last_check": 0, "last_refresh": 0}
def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def check_channel(cid):
    """Keyless: the public /channel/<id>/live page canonicalises to the current live video when one is on air."""
    req = urllib.request.Request(f"https://www.youtube.com/channel/{cid}/live", headers=UA)
    h = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', h)
    if not m or '"isLive":true' not in h or '"isUpcoming":true' in h or "LIVE_STREAM_OFFLINE" in h: return []
    t = re.search(r'"videoDetails":\{"videoId":"[\w-]{11}","title":"((?:[^"\\]|\\.)*)"', h); v = re.search(r'"concurrentViewers":"(\d+)"', h)
    import html as _h
    return [(m.group(1), json.loads('"' + t.group(1) + '"') if t else "", int(v.group(1)) if v else None)]
def check_all():
    now = iso(); c = SC.db()
    def one(cid):
        try: return cid, check_channel(cid), None
        except Exception as ex: return cid, None, f"{type(ex).__name__}: {str(ex)[:120]}"
    with cf.ThreadPoolExecutor(2) as ex: res = list(ex.map(one, CHS()))
    for cid, lives, err in res:
        c.execute("INSERT OR REPLACE INTO checks VALUES(?,?,?,?,?)", (cid, now, 0 if err else 1, err, len(lives or [])))
        if err: continue
        c.execute("UPDATE live SET live=0 WHERE channel_id=?", (cid,))
        for vid, title, viewers in lives: c.execute("INSERT OR REPLACE INTO live VALUES(?,?,?,?,?,1)", (cid, vid, title, viewers, now))
    c.commit(); c.close(); ST["last_check"] = time.time()
def CHS(): return list(SC.CH)
def _loop():
    while True:
        try: check_all()
        except Exception as ex: print("streams check:", ex, flush=True)
        ST["wake"].wait(CHECK_MIN * 60); ST["wake"].clear()
def _worker_alive():
    try:
        pid = int(open(PIDF).read().strip()); return "streams_worker" in open(f"/proc/{pid}/cmdline").read()
    except Exception: return False
def ensure_worker():
    if _worker_alive() or os.environ.get("BN_NO_STREAMWATCH"): return
    log = open(os.path.join(BASE, "logs", "streams_worker.log"), "a")
    subprocess.Popen(["/workspace/.whisperenv/bin/python", os.path.join(BASE, "streams_worker.py")], cwd=BASE, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
if not ST["started"]:
    ST["started"] = True; threading.Thread(target=_loop, daemon=True, name="streams-live").start()
ensure_worker()
SENT = re.compile(r"(?<=[.!?])\s+")
def summarize(segs):
    """Extractive summary: the 2 sentences from the last 30 min that carry the most keyword / threat signal and the channel's most frequent terms."""
    if not segs: return ""
    sents = [s.strip() for g in segs for s in SENT.split(g["text"] or "") if 40 <= len(s.strip()) <= 260]
    if not sents: return ""
    tf = Counter(w for s in sents for w in SC.toks(s)); top = {w for w, _ in tf.most_common(12)}
    def sc(s): return 3 * len(SC.match(s)) + 2 * len(re.findall(SC.RX["THREAT_RX"], s.lower())) + len(SC.toks(s) & top) / 2
    best = sorted(range(len(sents)), key=lambda i: -sc(sents[i]))[:2]
    return " … ".join(sents[i] for i in sorted(best))
def api(qs):
    hours = min(24, max(1, int((qs.get("hours") or ["3"])[0] or 3))); kw = (qs.get("kw") or [""])[0].lower().strip(); region = (qs.get("region") or [""])[0]
    live_only = (qs.get("live_only") or ["1"])[0] == "1"; since = iso(datetime.now(timezone.utc) - timedelta(hours=hours))
    c = SC.db(ro=True)
    try:
        live = [dict(r) for r in c.execute("SELECT * FROM live WHERE live=1")]; checks = {r["channel_id"]: dict(r) for r in c.execute("SELECT * FROM checks")}
        segs = [dict(r) for r in c.execute("SELECT * FROM segments WHERE t_start>=? ORDER BY t_start DESC LIMIT 3000", (since,))]
        state = {r["k"]: r["v"] for r in c.execute("SELECT * FROM state")}
    finally: c.close()
    for s in segs:
        s["matches"] = json.loads(s["matches"] or "[]"); s["cats"] = json.loads(s["cats"] or "[]"); s["confirmed_by"] = json.loads(s["confirmed_by"] or "[]")
    counts = Counter(m["w"] for s in segs for m in s["matches"])
    lv = {}; [lv.setdefault(x["channel_id"], []).append(x) for x in live]
    out = []
    for cid, ch in SC.CH.items():
        if region and ch["region"] != region: continue
        vids = lv.get(cid, [])
        if live_only and not vids: continue
        mine = [s for s in segs if s["channel_id"] == cid]
        cut = iso(datetime.now(timezone.utc) - timedelta(minutes=30))
        shown = [s for s in mine if not kw or any(m["w"] == kw for m in s["matches"])]
        if kw and not shown: continue
        out.append({**ch, "live": vids, "check": checks.get(cid), "summary": summarize([s for s in mine if s["t_start"] >= cut][:20]),
                    "max_score": max([s["score"] for s in mine] or [0]), "segments": shown[:40], "n_segments": len(mine),
                    "watching": cid in json.loads(state.get("watching", "[]"))})
    out.sort(key=lambda x: (-bool(x["live"]), -x["max_score"], x["name"]))   # global scope: live first, then score; no regional priority (Florida channels stay listed)
    watch = sorted([s for s in segs if s["watchlist"] and s["score"] > 0], key=lambda s: -s["score"])[:30]
    for s in watch: s["channel"] = SC.CH.get(s["channel_id"], {}).get("name", "")
    return 200, {"channels": out, "keywords": SC.keywords(), "keyword_counts": counts, "regions": sorted({c[2] for c in SC.CHANNELS}), "stream_watchlist": watch,
                 "worker": {"running": _worker_alive(), **{k: (json.loads(v) if k in ("watching", "cpu_hist") else v) for k, v in state.items()}},
                 "last_live_check": iso(datetime.fromtimestamp(ST["last_check"], timezone.utc)) if ST["last_check"] else None, "check_minutes": CHECK_MIN,
                 "n_live": len(lv), "n_channels": len(SC.CH)}
def handle_get(path, qs):
    ensure_worker()
    if path == "/api/streams": return api(qs)
    return 404, {"error": "not found"}
def handle_post(path, d):
    if path == "/api/streams/refresh":
        left = 30 - (time.time() - ST["last_refresh"])
        if left > 0: return 429, {"status": "rate_limited", "retry_after_s": int(left) + 1}
        ST["last_refresh"] = time.time(); check_all()
        c = SC.db(); c.execute("INSERT OR REPLACE INTO state VALUES('rerank_requested', ?)", (iso(),)); c.commit(); c.close()
        return 200, {"status": "ok", "checked": len(SC.CH), "note": "live status re-checked now; the watcher re-ranks the last hour of segments within a minute"}
    return 404, {"error": "not found"}
