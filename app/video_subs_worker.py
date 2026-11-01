#!/usr/bin/env python3
"""Video subtitles worker (runs under /workspace/.whisperenv at nice 19, ONE job at a time, exits when idle).
Per video, cheapest first: yt-dlp metadata (no video download) -> live/login/length checks -> language detection
(caption track 'xx-orig' > Whisper audio language-ID > metadata/title script) -> English subtitles:
 (a) platform English captions (human, then YouTube's own machine translation), (b) original-language captions translated
 cue-by-cue with the on-box Argos engine (shared with the site language picker), (c) audio-only download (<=20 min) + faster-whisper
 'small' on CPU: task=transcribe for the original text, task=translate for English. Writes only video_subs.db and video_subs/ temp files."""
import json, os, re, shutil, subprocess, sys, tempfile, time, traceback, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_subs_common as V
YTDLP = "/workspace/.whisperenv/bin/yt-dlp"; ARGOS_PY = "/workspace/.translateenv/bin/python"
YT_CAPTURE_ENABLED = os.environ.get("BN_YT_CAPTURE", "0") == "1"   # Nov 1 2026 audit: YouTube capture via yt-dlp/scraping OFF by default (Google API audit)
TMP = os.path.join(V.BASE, "video_subs"); JOB_BUDGET_S = 15 * 60; IDLE_EXIT_S = 180
_model = None
PLAT = {}
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(V.WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=2)
    return _model
class Stop(Exception):
    def __init__(self, code, detail=""): super().__init__(code); self.code = code; self.detail = detail
def classify(err, plat=None):
    e = (err or "").lower()
    if plat == "x" and ("no video formats" in e or "guest token" in e or "authorization" in e or "unable to" in e): return "login_required"   # X serves media only to logged-in sessions
    if "429" in e or "too many requests" in e: return "rate_limited"
    if "private video" in e or "this video is private" in e: return "private"
    if "not available in your country" in e or "geo restrict" in e or "geo-restrict" in e: return "geo_blocked"
    if "confirm you" in e and "bot" in e: return "download_blocked"
    if any(k in e for k in ("sign in", "log in", "login", "logged-in", "authentication", "cookies", "nsfw", "age-restricted", "confirm your age")): return "login_required"
    if any(k in e for k in ("no video could be found", "no video formats", "unsupported url", "there's no video", "no media", "does not contain")): return "not_a_video"
    if any(k in e for k in ("video unavailable", "has been removed", "does not exist", "http error 404", "not found", "deleted")): return "unavailable"
    if "timed out" in e or "timeout" in e: return "timeout"
    return "download_blocked"
def ytdlp(args, timeout=90):
    if not YT_CAPTURE_ENABLED and any(("youtube.com" in a or "youtu.be" in a) for a in args): raise Stop("unavailable", "YouTube capture disabled (API compliance)")
    r = subprocess.run(["nice", "-n", "19", YTDLP, "--no-warnings", "--no-playlist", "--socket-timeout", "20", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr
def probe(url):
    try: rc, out, err = ytdlp(["-J", "--skip-download", url], 90)
    except subprocess.TimeoutExpired: raise Stop("timeout", "metadata probe timed out")
    if rc != 0 or not out.strip(): raise Stop(classify(err, PLAT.get("p")), err.strip().splitlines()[-1][:300] if err.strip() else "yt-dlp failed")
    d = json.loads(out)
    if not d: raise Stop("not_a_video", "post has no video")   # yt-dlp prints null for text/photo-only Telegram posts
    if d.get("_type") == "playlist":
        ents = [e for e in (d.get("entries") or []) if e]
        if not ents: raise Stop("not_a_video", "post has no video")
        d = ents[0]
    return d
SCRIPTS = [(r"[\u0900-\u097F]", "hi"), (r"[\u0600-\u06FF]", "ar"), (r"[\u0590-\u05FF]", "he"), (r"[\u0400-\u04FF]", "ru"), (r"[\u3040-\u30FF]", "ja"),
           (r"[\uAC00-\uD7AF]", "ko"), (r"[\u4E00-\u9FFF]", "zh"), (r"[\u0E00-\u0E7F]", "th"), (r"[\u0980-\u09FF]", "bn"), (r"[\u0B80-\u0BFF]", "ta"), (r"[\u0370-\u03FF]", "el")]
def script_hint(text):
    for rx, code in SCRIPTS:
        if len(re.findall(rx, text or "")) >= 4: return code
    return None
# ---------- caption helpers ----------
def parse_json3(path):
    d = json.load(open(path, encoding="utf-8")); cues = []
    for e in d.get("events", []):
        if not e.get("segs") or e.get("aAppend"): continue
        t = "".join(s.get("utf8", "") for s in e["segs"]).replace("\n", " ").strip()
        if not t: continue
        a = e.get("tStartMs", 0) / 1000; b = a + e.get("dDurationMs", 2000) / 1000
        cues.append([round(a, 2), round(b, 2), re.sub(r"\s+", " ", t)])
    for i in range(len(cues) - 1): cues[i][1] = round(min(cues[i][1], cues[i + 1][0]) if cues[i + 1][0] > cues[i][0] else cues[i][1], 2)
    return cues
def merge(cues, max_s=10.0, max_words=28):
    """Rolling ASR captions -> readable sentence-ish cues (better context for MT)."""
    out = []
    for a, b, t in cues:
        if out and (b - out[-1][0] <= max_s) and len(out[-1][2].split()) + len(t.split()) <= max_words and a - out[-1][1] < 1.5 and not re.search(r"[.!?।۔。！？]$", out[-1][2]):
            out[-1][1] = b; out[-1][2] += " " + t
        else: out.append([a, b, t])
    return out
def fetch_subs(url, lang, auto, tmp):
    for f in os.listdir(tmp):
        if f.endswith(".json3"): os.remove(os.path.join(tmp, f))
    args = ["--skip-download", "--sub-format", "json3", "--sub-langs", lang, "-o", os.path.join(tmp, "s.%(ext)s"), url]
    args.insert(0, "--write-auto-subs" if auto else "--write-subs")
    rc, out, err = ytdlp(args, 120)
    fs = [f for f in os.listdir(tmp) if f.endswith(".json3")]
    if not fs:
        if "429" in err: raise Stop("rate_limited", "caption download rate-limited")
        return None
    return parse_json3(os.path.join(tmp, fs[0]))
# ---------- on-box text MT (Argos, same engine/env as the site language picker) ----------
ARGOS_SRC = r'''
import json, sys
import argostranslate.translate as T
d = json.load(sys.stdin); langs = {l.code: l for l in T.get_installed_languages()}
src = langs.get(d["src"]); en = langs.get("en")
tr = src.get_translation(en) if src and en else None
if tr is None: print(json.dumps({"ok": False, "installed": sorted(langs)})); sys.exit()
print(json.dumps({"ok": True, "out": [tr.translate(t) if t.strip() else t for t in d["texts"]]}))
'''
def argos_code(code): return {"iw": "he", "zh-Hans": "zh", "zh-Hant": "zt", "nb": "nb", "no": "nb", "fil": "tl", "pt-BR": "pt"}.get(code, code.split("-")[0])
def mt_to_en(texts, src):
    if not os.path.exists(ARGOS_PY) or not texts: return None
    try:
        env = {**os.environ, "OMP_NUM_THREADS": "2", "CT2_INTER_THREADS": "1"}
        r = subprocess.run(["nice", "-n", "19", ARGOS_PY, "-c", ARGOS_SRC], input=json.dumps({"src": argos_code(src), "texts": texts}), capture_output=True, text=True, timeout=JOB_BUDGET_S, env=env)
        d = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        return d.get("out") if d.get("ok") else None
    except Exception: traceback.print_exc(); return None
# ---------- Whisper path ----------
def audio(url, tmp, info):
    for f in os.listdir(tmp): os.remove(os.path.join(tmp, f))
    try: rc, out, err = ytdlp(["-f", "bestaudio/best[height<=480]/best", "--max-filesize", "400M", "-o", os.path.join(tmp, "a.%(ext)s"), url], 300)
    except subprocess.TimeoutExpired: raise Stop("timeout", "audio download timed out")
    fs = [f for f in os.listdir(tmp) if f.startswith("a.") and not f.endswith(".part")]
    if rc != 0 or not fs:
        if "max-filesize" in err or "larger than max" in err.lower(): raise Stop("too_large", "file over 400 MB")
        raise Stop(classify(err, PLAT.get("p")), (err.strip().splitlines() or ["download failed"])[-1][:300])
    wav = os.path.join(tmp, "a.wav")
    p = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", os.path.join(tmp, fs[0]), "-t", str(V.AUDIO_CAP_S + 1), "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not os.path.exists(wav) or os.path.getsize(wav) < 16000:
        raise Stop("no_audio", "no decodable audio stream")
    import numpy as np
    with wave.open(wav, "rb") as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if len(a) / 16000 > V.AUDIO_CAP_S: raise Stop("too_long", f"audio {len(a)/16000:.0f}s")
    if float(np.abs(a).max() if len(a) else 0) < 0.003: raise Stop("no_audio", "audio track is silent")
    return a
def whisper(a, deadline, lang_hint=None):
    m = model(); out = {}
    for task in ("transcribe", "translate"):
        segs, info = m.transcribe(a, beam_size=1, vad_filter=True, task=task, language=out.get("lang") or None, condition_on_previous_text=False)
        cues = []
        for s in segs:
            if time.time() > deadline: raise Stop("timeout", "transcription exceeded the per-job budget")
            if s.text.strip(): cues.append([round(s.start, 2), round(s.end, 2), s.text.strip()])
        if task == "transcribe":
            out.update(lang=info.language, prob=round(info.language_probability, 3), dur=info.duration, orig=cues)
            if not cues: raise Stop("no_speech", "voice activity detection found no speech")
            if info.language == "en" and info.language_probability >= 0.6: out["en"] = cues; break
        else: out["en"] = cues
    return out
# ---------- job ----------
def save(key, **kv):
    kv["updated"] = V.iso(); c = V.db()
    c.execute(f"UPDATE jobs SET {','.join(k + '=?' for k in kv)} WHERE key=?", (*[json.dumps(v) if isinstance(v, (list, dict)) else v for v in kv.values()], key)); c.commit(); c.close()
def process(j):
    key, url, plat = j["key"], j["url"], j["platform"]; t0 = time.time(); deadline = t0 + JOB_BUDGET_S
    tmp = tempfile.mkdtemp(prefix="vs_", dir=TMP); PLAT["p"] = plat
    try:
        save(key, status="processing", started=V.iso(), attempts=(j["attempts"] or 0) + 1, eta_s=60)
        info = probe(url)
        title = info.get("title") or info.get("description") or ""; dur = info.get("duration"); ls = info.get("live_status")
        media = info.get("url") if plat in ("telegram", "direct") else None
        if not media and plat in ("telegram", "direct"):
            fm = [f for f in (info.get("formats") or []) if f.get("url") and f.get("vcodec") != "none" and str(f.get("ext")) in ("mp4", "webm")]
            media = fm[-1]["url"] if fm else None
        save(key, title=title[:300], duration=dur, is_live=1 if info.get("is_live") else 0, media_url=media, media_at=V.iso() if media else None)
        if info.get("is_live") or ls in ("is_live", "post_live"): raise Stop("live_stream", f"live_status={ls}")
        if ls == "is_upcoming": raise Stop("upcoming")
        fmts = info.get("formats") or [info]
        has_audio = any(f.get("acodec") not in ("none",) for f in fmts)
        subs = info.get("subtitles") or {}; auto = info.get("automatic_captions") or {}
        orig = next((k[:-5] for k in auto if k.endswith("-orig")), None)
        meta_lang = (info.get("language") or "").split("-")[0] or None
        hint = script_hint(title)
        manual = [k for k in subs if k != "live_chat"]
        src = orig or (manual[0] if len(manual) == 1 else None); lm = "caption track" if src else None
        save(key, eta_s=round(25 + min(dur or 300, V.AUDIO_CAP_S) * 0.35))
        # (a)/(b) caption paths
        if src and src.split("-")[0] == "en":
            save(key, status="english", src_lang="en", lang_method=lm, method="Original captions are English", finished=V.iso(), proc_s=round(time.time() - t0, 1)); return
        if src:
            en_manual = next((k for k in manual if k.split("-")[0] == "en"), None)
            o = fetch_subs(url, f"{src}-orig" if orig else src, bool(orig), tmp) or []
            o = merge(o) if orig else o
            en = None; method = None
            if en_manual: en = fetch_subs(url, en_manual, False, tmp); method = "uploader's English captions"
            if not en and "en" in auto:
                try: en = fetch_subs(url, "en", True, tmp); en = merge(en) if en else en; method = "YouTube auto-translated captions"
                except Stop: en = None
            if not en and o:
                lim = [c for c in o if c[0] < V.MT_CAP_S]
                tr = mt_to_en([c[2] for c in lim], src)
                if tr:
                    en = [[c[0], c[1], t] for c, t in zip(lim, tr)]; method = "Argos on-box, from original captions"
                    partial = "first 60 min" if len(lim) < len(o) else None
                    save(key, partial=partial)
            if en:
                save(key, status="done", src_lang=src, lang_method=lm, method=method, model="Argos Translate" if "Argos" in method else "platform", detail=None,
                     cues_en=en[:6000], cues_orig=o[:6000], finished=V.iso(), proc_s=round(time.time() - t0, 1)); return
        # (c) Whisper on audio
        if not has_audio and not src: raise Stop("no_audio", "no audio formats and no captions")
        if dur and dur > V.AUDIO_CAP_S: raise Stop("too_long", f"{dur:.0f}s and no translatable captions")
        if not dur and info.get("is_live") is None and plat == "x" and not fmts: raise Stop("not_a_video")
        a = audio(url, tmp, info); ta = time.time()
        save(key, eta_s=round(len(a) / 16000 * 0.35))
        w = whisper(a, deadline)
        st = "english" if w["lang"] == "en" and "en" in w and w["en"] is w["orig"] else "done"
        save(key, status=st, src_lang=w["lang"], lang_prob=w["prob"], lang_method="Whisper audio language ID", method="Whisper speech-to-English, on-box" if st == "done" else "Whisper detected English speech",
             model=f"faster-whisper {V.WHISPER_MODEL} (int8, CPU)", cues_en=w["en"], cues_orig=w["orig"], audio_s=round(len(a) / 16000, 1),
             finished=V.iso(), proc_s=round(time.time() - t0, 1), detail=f"whisper {time.time()-ta:.0f}s for {len(a)/16000:.0f}s audio; title-script hint={hint}; metadata language={meta_lang}")
    except Stop as s:
        if s.code in ("rate_limited", "timeout") and (j["attempts"] or 0) < 2:
            save(key, status="queued", reason=s.code, detail=s.detail, retry_after=V.iso(time.time() + 1800), priority=6)
        else: save(key, status="unsupported", reason=s.code, detail=s.detail[:300], finished=V.iso(), proc_s=round(time.time() - t0, 1))
        log(key, "->", s.code, s.detail[:120])
    except Exception as ex:
        traceback.print_exc(); save(key, status="unsupported", reason="generic", detail=f"{type(ex).__name__}: {str(ex)[:250]}", finished=V.iso())
    finally: shutil.rmtree(tmp, ignore_errors=True)
def main():
    import fcntl
    os.makedirs(TMP, exist_ok=True)
    lk = open(os.path.join(V.BASE, "logs", "video_subs_worker.lock"), "w")
    try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: return
    try: os.nice(19 - os.nice(0))
    except Exception: pass
    c = V.db(); c.execute("UPDATE jobs SET status='queued' WHERE status='processing'"); c.commit(); c.close()   # recover after a crash
    idle = time.time()
    while time.time() - idle < IDLE_EXIT_S:
        c = V.db()
        j = c.execute("SELECT * FROM jobs WHERE status='queued' AND (retry_after IS NULL OR retry_after<=?) ORDER BY priority, created LIMIT 1", (V.iso(),)).fetchone(); c.close()
        if not j: time.sleep(5); continue
        log("job", j["key"], j["url"]); process(dict(j)); idle = time.time()
    log("idle, exiting")
if __name__ == "__main__": main()
