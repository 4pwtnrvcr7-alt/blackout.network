#!/usr/bin/env python3
"""Continuous Live Streams watcher (runs under /workspace/.whisperenv). For each slot: resolve the live HLS URL with yt-dlp,
capture 30 s audio chunks with ffmpeg, transcribe on CPU with faster-whisper, keyword-match against keywords.json and score
each segment with the scanner-mirroring rules in streams_common. Concurrency auto-tunes to keep TOTAL box CPU under ~50%;
streams rotate every ROTATE_S so all live channels get coverage. Writes only streams.db (reads blackout.db read-only)."""
import json, os, random, sqlite3, subprocess, sys, tempfile, threading, time, traceback
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streams_common as SC
from faster_whisper import WhisperModel
BASE = SC.BASE; YTDLP = "/workspace/.whisperenv/bin/yt-dlp"; CHUNK_S = 30; ROTATE_S = 600; MAX_SLOTS = 6; CPU_HI = 50.0; CPU_LO = 33.0
MODEL = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=2, num_workers=MAX_SLOTS)
LOCK = threading.Lock(); S = {"slots": 1, "watching": {}, "last_watched": {}, "cpu": 0.0, "cpu_hist": [], "chunks": 0, "rtf": []}
def iso(d=None): return (d or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
def setstate(**kv):
    c = SC.db()
    for k, v in kv.items(): c.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (k, v if isinstance(v, str) else json.dumps(v)))
    c.commit(); c.close()
def cpu_sample():
    def rd():
        p = list(map(int, open("/proc/stat").readline().split()[1:])); idle = p[3] + p[4]; return sum(p), idle
    a = rd(); time.sleep(5); b = rd(); return 100.0 * (1 - (b[1] - a[1]) / max(1, b[0] - a[0]))
def tuner():
    while True:
        try:
            cpu = cpu_sample(); S["cpu_hist"] = (S["cpu_hist"] + [round(cpu, 1)])[-24:]; avg = sum(S["cpu_hist"][-6:]) / len(S["cpu_hist"][-6:]); S["cpu"] = avg
            nlive = len(live_list())
            if avg > CPU_HI and S["slots"] > 1: S["slots"] -= 1
            elif avg < CPU_LO and S["slots"] < min(MAX_SLOTS, nlive) and len(S["cpu_hist"]) >= 6: S["slots"] += 1; S["cpu_hist"] = S["cpu_hist"][-2:]
            S["slots"] = max(1, min(S["slots"], max(1, nlive)))
            rtf = sum(S["rtf"][-20:]) / max(1, len(S["rtf"][-20:]))
            setstate(slots=str(S["slots"]), cpu_pct=f"{avg:.1f}", cpu_hist=S["cpu_hist"], watching=list(S["watching"].values()), chunks=str(S["chunks"]),
                     rtf=f"{rtf:.2f}", cpu_target=f"<{CPU_HI:.0f}% total box CPU", updated=iso(), max_slots=str(MAX_SLOTS), chunk_seconds=str(CHUNK_S), rotate_seconds=str(ROTATE_S))
        except Exception: traceback.print_exc()
        time.sleep(25)
def live_list():
    c = SC.db(ro=True)
    try: return [dict(r) for r in c.execute("SELECT channel_id, video_id, title FROM live WHERE live=1")]
    finally: c.close()
def pick():
    with LOCK:
        busy = set(S["watching"].values()); cands = [x for x in live_list() if x["channel_id"] not in busy]
        if not cands: return None
        # global scope: rotate fairly across all live channels (least-recently watched first), no Central Florida priority
        cands.sort(key=lambda x: (S["last_watched"].get(x["channel_id"], 0), random.random()))
        return cands[0]
def confirm(c, cid, text, t0):
    """2+ independent sources: another channel saying overlapping threat terms within 60 min, or a matching blackout.db cluster in the last 6 h."""
    tk = SC.toks(text); conf = []; linked = None
    if len(tk) < 4: return conf, linked
    since = iso(datetime.now(timezone.utc) - timedelta(minutes=60))
    seen = set()
    for r in c.execute("SELECT channel_id, text FROM segments WHERE t_start>=? AND channel_id!=? AND matches!='[]'", (since, cid)):
        if r["channel_id"] in seen: continue
        ot = SC.toks(r["text"]); sh = tk & ot
        if len(sh) >= 3 and SC.jacc(tk, ot) >= 0.08: conf.append({"type": "stream", "name": SC.CH.get(r["channel_id"], {}).get("name", r["channel_id"]), "shared": sorted(sh)[:6]}); seen.add(r["channel_id"])
    try:
        b = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=20); b.row_factory = sqlite3.Row
        cut = iso(datetime.now(timezone.utc) - timedelta(hours=6))
        best = None
        for r in b.execute("SELECT cluster_id,title,score,rank,eff_families,watchlist FROM clusters WHERE first_seen>=? AND watchlist=0", (cut,)):
            ot = SC.toks(r["title"]); sh = tk & ot
            if len(sh) >= 3 or (len(ot) <= 6 and len(sh) >= 2 and len(sh) / max(1, len(ot)) >= .5):
                if not best or r["rank"] > best["rank"]: best = dict(r); best["shared"] = sorted(sh)[:6]
        b.close()
        if best: conf.append({"type": "wire", "name": "The Wire: " + best["title"][:90], "shared": best["shared"], "cluster_id": best["cluster_id"]}); linked = best
    except Exception: pass
    return conf, linked
def store(cid, vid, t0, t1, text):
    ms = SC.match(text); c = SC.db()
    try:
        conf, linked = confirm(c, cid, text, t0) if (ms or SC.RX and __import__("re").search(SC.RX["THREAT_RX"], text.lower())) else ([], None)
        score, rank, cf, nf = SC.score_segment(text, len(conf))
        high = 0
        if linked and linked["rank"] >= 7 and linked["eff_families"] >= 2: high = 1; rank = max(rank, linked["rank"]); score = max(score, linked["score"])
        wl = 1 if cf == "Low" else 0
        c.execute("INSERT INTO segments(channel_id,video_id,t_start,t_end,text,matches,cats,score,rank,confidence,confirmed_by,watchlist,high,scored_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, vid, t0, t1, text, json.dumps(ms), json.dumps(sorted({m["cat"] for m in ms})), score, rank, cf, json.dumps(conf), wl, high, iso()))
        c.execute("DELETE FROM segments WHERE t_start < ?", (iso(datetime.now(timezone.utc) - timedelta(days=7)),)); c.commit()
    finally: c.close()
def rerank():
    c = SC.db()
    try:
        r = c.execute("SELECT v FROM state WHERE k='rerank_requested'").fetchone(); d = c.execute("SELECT v FROM state WHERE k='rerank_done'").fetchone()
        if not r or (d and d[0] >= r[0]): return
        since = iso(datetime.now(timezone.utc) - timedelta(hours=1))
        for s in c.execute("SELECT * FROM segments WHERE t_start>=?", (since,)).fetchall():
            conf, linked = confirm(c, s["channel_id"], s["text"], s["t_start"]); score, rank, cf, nf = SC.score_segment(s["text"], len(conf)); high = 0
            if linked and linked["rank"] >= 7 and linked["eff_families"] >= 2: high = 1; rank = max(rank, linked["rank"]); score = max(score, linked["score"])
            c.execute("UPDATE segments SET score=?,rank=?,confidence=?,confirmed_by=?,watchlist=?,high=?,scored_at=? WHERE id=?", (score, rank, cf, json.dumps(conf), 1 if cf == "Low" else 0, high, iso(), s["id"]))
        c.execute("INSERT OR REPLACE INTO state VALUES('rerank_done', ?)", (iso(),)); c.commit()
    finally: c.close()
def load_wav(path):
    import wave, numpy as np
    with wave.open(path, "rb") as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return a.astype(np.float32) / 32768.0
def slot(n):
    tmp = tempfile.mkdtemp(prefix=f"bnstream{n}_")
    while True:
        try:
            if n >= S["slots"]: S["watching"].pop(n, None); time.sleep(10); continue
            x = pick()
            if not x: time.sleep(20); continue
            cid, vid = x["channel_id"], x["video_id"]
            with LOCK: S["watching"][n] = cid; S["last_watched"][cid] = time.time()
            r = subprocess.run([YTDLP, "-g", "-f", "91/92/93/94/bestaudio/best", "--no-warnings", "--no-playlist", f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=60)
            url = (r.stdout.strip().splitlines() or [""])[0]
            if not url: time.sleep(30); continue
            t_end = time.time() + ROTATE_S
            while time.time() < t_end and n < S["slots"]:
                wav = os.path.join(tmp, "a.wav"); t0 = iso()
                p = subprocess.run(["nice", "-n", "15", "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", url, "-t", str(CHUNK_S), "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True, timeout=CHUNK_S + 60)
                if p.returncode != 0 or not os.path.exists(wav): break
                ts = time.time(); segs, info = MODEL.transcribe(load_wav(wav), beam_size=1, vad_filter=True, language="en")
                text = " ".join(s.text.strip() for s in segs).strip(); S["rtf"].append((time.time() - ts) / CHUNK_S); S["chunks"] += 1
                if text: store(cid, vid, t0, iso(), text)
                os.remove(wav)
            with LOCK: S["watching"].pop(n, None)
        except Exception:
            traceback.print_exc(); S["watching"].pop(n, None); time.sleep(20)
if __name__ == "__main__":
    import fcntl
    _lk = open(os.path.join(BASE, "logs", "streams_worker.lock"), "w")
    try: fcntl.flock(_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: sys.exit(0)   # another instance is already running
    open(os.path.join(BASE, "logs", "streams_worker.pid"), "w").write(str(os.getpid()))
    os.nice(10)
    threading.Thread(target=tuner, daemon=True).start()
    for i in range(MAX_SLOTS): threading.Thread(target=slot, args=(i,), daemon=True).start()
    while True:
        try: rerank()
        except Exception: traceback.print_exc()
        time.sleep(20)
