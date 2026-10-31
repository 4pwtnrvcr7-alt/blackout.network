"""Video subtitles add-on: /api/video_subs (status + English/original cues for one allow-listed video URL), /api/video_subs/vtt
(WebVTT for <track>), /api/video_subs/stats, and /vsubs/<file> (client script/style). Heavy work runs in video_subs_worker.py
(separate process, nice 19, one job at a time). Background queue pre-processes videos linked from rank 6+ alerts.
Writes only video_subs.db. blackout.db and streams.db are read with mode=ro. Display-only: never changes alerts or scores."""
import builtins, json, os, re, sqlite3, subprocess, threading, time
from datetime import datetime, timezone, timedelta
import video_subs_common as V
BASE = V.BASE; WPY = "/workspace/.whisperenv/bin/python"; STATIC = os.path.join(BASE, "static", "vsubs")
ST = getattr(builtins, "_bn_vsubs", None)
if ST is None: ST = builtins._bn_vsubs = {"started": False, "recent": [], "last_bg": 0, "media_refresh": {}}
ST.setdefault("procs", [])
def reap(): ST["procs"] = [p for p in ST["procs"] if p.poll() is None]   # no zombie workers left behind
MAX_QUEUE = 150; USER_PER_10MIN = 40; BG_MIN_RANK = 6; BG_HOURS = 48
def spawn():
    try:
        import fcntl
        lk = open(os.path.join(BASE, "logs", "video_subs_worker.lock"), "a")
        try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(lk, fcntl.LOCK_UN); lk.close()
        except OSError: lk.close(); return   # already running
        log = open(os.path.join(BASE, "logs", "video_subs_worker.log"), "a")
        reap(); ST["procs"].append(subprocess.Popen(["nice", "-n", "19", WPY, os.path.join(BASE, "video_subs_worker.py")], cwd=BASE, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True))
    except Exception as ex: print("video_subs spawn:", ex, flush=True)
def live_ids():
    try:
        c = sqlite3.connect(f"file:{BASE}/streams.db?mode=ro", uri=True, timeout=5)
        try: return {r[0] for r in c.execute("SELECT video_id FROM live WHERE live=1")}
        finally: c.close()
    except Exception: return set()
def enqueue(plat, key, url, priority, source):
    c = V.db()
    try:
        r = c.execute("SELECT status FROM jobs WHERE key=?", (key,)).fetchone()
        if r: 
            if priority == 0: c.execute("UPDATE jobs SET priority=0 WHERE key=? AND status='queued'", (key,)); c.commit()
            return r["status"]
        if c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','processing')").fetchone()[0] >= MAX_QUEUE: return "queue_full"
        if plat == "youtube" and key[3:] in live_ids():   # cheapest check: our own Live Streams list already knows it is on air
            c.execute("INSERT INTO jobs(key,url,platform,status,reason,detail,is_live,priority,source,created,updated,finished) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (key, url, plat, "unsupported", "live_stream", "listed live in streams.db", 1, priority, source, V.iso(), V.iso(), V.iso()))
            c.commit(); return "unsupported"
        c.execute("INSERT INTO jobs(key,url,platform,status,priority,source,created,updated) VALUES(?,?,?,?,?,?,?,?)", (key, url, plat, "queued", priority, source, V.iso(), V.iso()))
        c.commit(); return "queued"
    finally: c.close()
def bg_scan():
    """Queue videos linked from rank 6+ alerts (last 48 h) at low priority."""
    try:
        b = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20)
        cut = (datetime.now(timezone.utc) - timedelta(hours=BG_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = b.execute("SELECT rank, links FROM clusters WHERE rank>=? AND COALESCE(event_time, first_seen)>=? ORDER BY rank DESC", (BG_MIN_RANK, cut)).fetchall(); b.close()
        n = 0
        for rank, links in rows:
            for l in json.loads(links or "[]"):
                plat, key, url = V.normalize(l.get("url") if isinstance(l, dict) else l)
                if plat and plat != "x":        # X needs a login for most media; only on demand
                    if enqueue(plat, key, url, 5 if rank < 8 else 3, f"alert rank {rank}") == "queued": n += 1
                if n >= 40: break
        if n: spawn()
    except Exception as ex: print("video_subs bg:", ex, flush=True)
def _loop():
    time.sleep(90)
    while True:
        bg_scan(); time.sleep(15 * 60)
if not ST["started"]:
    ST["started"] = True; threading.Thread(target=_loop, daemon=True, name="video-subs-bg").start()
def refresh_media(r):
    """Telegram CDN links expire: re-resolve at most every 30 min per video (metadata only)."""
    key = r["key"]
    if r["platform"] not in ("telegram",) or not r["media_url"]: return r["media_url"]
    try: age = time.time() - datetime.strptime(r["media_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception: age = 1e9
    if age < 1800 or time.time() - ST["media_refresh"].get(key, 0) < 600: return r["media_url"]
    ST["media_refresh"][key] = time.time()
    try:
        p = subprocess.run(["nice", "-n", "10", "/workspace/.whisperenv/bin/yt-dlp", "--no-warnings", "-g", "-f", "best", r["url"]], capture_output=True, text=True, timeout=40)
        u = (p.stdout.strip().splitlines() or [""])[0]
        if u.startswith("https://"):
            c = V.db(); c.execute("UPDATE jobs SET media_url=?, media_at=? WHERE key=?", (u, V.iso(), key)); c.commit(); c.close(); return u
    except Exception: pass
    return r["media_url"]
def out(r, plat, url, extra=None):
    o = {"platform": plat, "watch_url": url, "watch_label": f"Watch on {V.PLATFORM_LABEL.get(plat, 'the original site')} ↗", "notice_title": V.NOTICE_TITLE}
    if extra: o.update(extra)
    if not r: return o
    st = r["status"]; o.update(status=st, key=r["key"], title=r["title"], duration=r["duration"], src_lang=r["src_lang"], src_lang_name=V.lang_name(r["src_lang"]),
                            rtl=(r["src_lang"] or "").split("-")[0] in V.RTL, method=r["method"], model=r["model"], lang_method=r["lang_method"], lang_prob=r["lang_prob"],
                            partial=r["partial"], updated=r["updated"], finished=r["finished"], proc_s=r["proc_s"])
    if st in ("queued", "processing"):
        c = V.db(ro=True)
        try: pos = c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','processing') AND (priority<? OR (priority=? AND created<?))", (r["priority"], r["priority"], r["created"])).fetchone()[0]
        finally: c.close()
        o.update(queue_pos=pos, eta_s=r["eta_s"], retrying=r["reason"] if st == "queued" and r["reason"] else None)
    if st == "unsupported": o.update(reason=r["reason"] or "generic", reason_text=V.reason_text(r["reason"]), detail=r["detail"])
    if st == "done":
        o.update(label=f"Translated from {V.lang_name(r['src_lang'])} · machine translation ({r['method']})", cues_en=json.loads(r["cues_en"] or "[]"), cues_orig=json.loads(r["cues_orig"] or "[]"))
        if plat in ("telegram", "direct"): o["media_url"] = refresh_media(r)
    if st == "english": o.update(label="This video is already in English. No translation needed.")
    return o
def api(qs):
    url = (qs.get("url") or [""])[0]; plat, key, canon = V.normalize(url)
    if not plat: return 200, {"status": "unsupported", "reason": key, "reason_text": V.reason_text(key), "notice_title": V.NOTICE_TITLE, "watch_url": url if re.match(r"^https?://", url) else None, "watch_label": "Open original link ↗"}
    c = V.db(ro=True)
    try: r = c.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
    finally: c.close()
    if r and r["status"] == "unsupported" and r["reason"] in V.RETRYABLE and (qs.get("retry") or ["0"])[0] == "1":
        c = V.db(); c.execute("UPDATE jobs SET status='queued', priority=0, retry_after=NULL WHERE key=?", (key,)); c.commit(); c.close(); r = None; spawn()
        c = V.db(ro=True); r = c.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone(); c.close()
    if not r and (qs.get("peek") or ["0"])[0] != "1":
        now = time.time(); ST["recent"] = [t for t in ST["recent"] if now - t < 600]
        if len(ST["recent"]) >= USER_PER_10MIN: return 200, out(None, plat, canon, {"status": "unsupported", "reason": "queue_full", "reason_text": V.reason_text("queue_full")})
        ST["recent"].append(now)
        s = enqueue(plat, key, canon, 0, "viewer")
        if s == "queue_full": return 200, out(None, plat, canon, {"status": "unsupported", "reason": "queue_full", "reason_text": V.reason_text("queue_full")})
        spawn()
        c = V.db(ro=True); r = c.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone(); c.close()
    elif r and r["status"] == "queued": spawn()
    if not r: return 200, out(None, plat, canon, {"status": "none"})
    return 200, out(r, plat, canon)
def stats():
    c = V.db(ro=True)
    try:
        by = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")}
        rs = {r[0]: r[1] for r in c.execute("SELECT reason, COUNT(*) FROM jobs WHERE status='unsupported' GROUP BY reason")}
        langs = {r[0]: r[1] for r in c.execute("SELECT src_lang, COUNT(*) FROM jobs WHERE status='done' GROUP BY src_lang")}
        sp = c.execute("SELECT SUM(audio_s), SUM(proc_s) FROM jobs WHERE status IN ('done','english') AND audio_s>0").fetchone()
    finally: c.close()
    return 200, {"by_status": by, "unsupported_reasons": rs, "languages_done": langs, "reasons": V.REASONS, "notice_title": V.NOTICE_TITLE,
                 "whisper_audio_s": sp[0], "whisper_proc_s": sp[1], "speed_x_realtime": round(sp[0] / sp[1], 2) if sp[0] and sp[1] else None,
                 "caps": {"audio_minutes": V.AUDIO_CAP_S // 60, "caption_hours": V.CAPTION_CAP_S // 3600, "mt_minutes": V.MT_CAP_S // 60}, "model": V.WHISPER_MODEL}
def handle_get(path, qs):
    reap()
    if path == "/api/video_subs": return api(qs)
    if path == "/api/video_subs/stats": return stats()
    if path == "/api/video_subs/vtt":
        plat, key, canon = V.normalize((qs.get("url") or [""])[0]); track = (qs.get("track") or ["en"])[0]
        if not plat: return 404, "WEBVTT\n\n", "text/vtt"
        c = V.db(ro=True); r = c.execute("SELECT cues_en, cues_orig FROM jobs WHERE key=? AND status='done'", (key,)).fetchone(); c.close()
        if not r: return 404, "WEBVTT\n\n", "text/vtt"
        return 200, V.vtt(json.loads(r["cues_orig" if track == "orig" else "cues_en"] or "[]")), "text/vtt"
    if path.startswith("/vsubs/"):
        name = path[len("/vsubs/"):]
        if name in ("vsubs.js", "vsubs.css"):
            with open(os.path.join(STATIC, name), "rb") as f: return 200, f.read(), "application/javascript" if name.endswith(".js") else "text/css"
    return 404, {"error": "not found"}
