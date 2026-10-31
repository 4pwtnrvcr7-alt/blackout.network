"""Video subtitles (English auto-translation of linked foreign-language videos): shared pieces for the dashboard add-on
(video_subs.py, stdlib) and the worker (video_subs_worker.py, /workspace/.whisperenv). Writes only video_subs.db.
Reads blackout.db / streams.db read-only. Never touches scanner.py, scoring, push.py, jets.py or config.json."""
import json, os, re, sqlite3, time
from urllib.parse import urlparse, parse_qs
BASE = os.path.dirname(os.path.abspath(__file__)); VDB = os.path.join(BASE, "video_subs.db")
AUDIO_CAP_S = 20 * 60          # Whisper path: VOD audio up to 20 minutes
CAPTION_CAP_S = 3 * 3600       # caption path: platform English tracks up to 3 h
MT_CAP_S = 60 * 60             # caption path with on-box text MT: first 60 min translated (marked partial)
WHISPER_MODEL = "small"        # multilingual; 'base' is ~3x faster but noticeably worse at translation
RTL = {"ar", "fa", "he", "ur", "ps", "yi", "iw", "sd", "ug", "dv"}
LANGS = {"af":"Afrikaans","am":"Amharic","ar":"Arabic","az":"Azerbaijani","be":"Belarusian","bg":"Bulgarian","bn":"Bengali","bs":"Bosnian","ca":"Catalan",
 "cs":"Czech","cy":"Welsh","da":"Danish","de":"German","el":"Greek","en":"English","es":"Spanish","et":"Estonian","eu":"Basque","fa":"Persian","fi":"Finnish",
 "fil":"Filipino","tl":"Tagalog","fr":"French","ga":"Irish","gl":"Galician","gu":"Gujarati","ha":"Hausa","he":"Hebrew","iw":"Hebrew","hi":"Hindi","hr":"Croatian",
 "hu":"Hungarian","hy":"Armenian","id":"Indonesian","is":"Icelandic","it":"Italian","ja":"Japanese","jw":"Javanese","ka":"Georgian","kk":"Kazakh","km":"Khmer",
 "kn":"Kannada","ko":"Korean","ky":"Kyrgyz","lo":"Lao","lt":"Lithuanian","lv":"Latvian","mk":"Macedonian","ml":"Malayalam","mn":"Mongolian","mr":"Marathi",
 "ms":"Malay","my":"Burmese","ne":"Nepali","nl":"Dutch","no":"Norwegian","nb":"Norwegian","pa":"Punjabi","pl":"Polish","ps":"Pashto","pt":"Portuguese",
 "ro":"Romanian","ru":"Russian","si":"Sinhala","sk":"Slovak","sl":"Slovenian","so":"Somali","sq":"Albanian","sr":"Serbian","sv":"Swedish","sw":"Swahili",
 "ta":"Tamil","te":"Telugu","tg":"Tajik","th":"Thai","tk":"Turkmen","tr":"Turkish","uk":"Ukrainian","ur":"Urdu","uz":"Uzbek","vi":"Vietnamese","yi":"Yiddish",
 "yo":"Yoruba","zh":"Chinese","zh-Hans":"Chinese (Simplified)","zh-Hant":"Chinese (Traditional)","yue":"Cantonese","haw":"Hawaiian","la":"Latin","mt":"Maltese",
 "sn":"Shona","ln":"Lingala","sd":"Sindhi","ug":"Uyghur","ba":"Bashkir","tt":"Tatar","be-BY":"Belarusian","pt-BR":"Portuguese (Brazil)"}
def lang_name(code):
    if not code: return "an unknown language"
    return LANGS.get(code) or LANGS.get(code.split("-")[0]) or code
# Every internal outcome code -> plain-language reason shown under the video ("Translation is not supported" + why + watch link).
REASONS = {
 "live_stream": "Live streams require constant processing, so they can't be translated here. Recorded videos can.",
 "upcoming": "This stream hasn't started yet, so there is nothing to translate.",
 "login_required": "This clip requires a login to download, and blackout.network doesn't sign in to other platforms.",
 "private": "This video is private or has been removed by the uploader.",
 "unavailable": "This video is no longer available on the original platform.",
 "geo_blocked": "This video isn't available in the region our server is in.",
 "download_blocked": "The platform blocked the download, so the audio couldn't be processed.",
 "rate_limited": "The platform is temporarily limiting requests. We'll retry automatically later.",
 "no_audio": "No audio or captions were found.",
 "no_speech": "No speech was detected in the audio (it may be music, ambient sound or silent footage).",
 "too_long": "This video is longer than the 20-minute limit and has no captions we could translate.",
 "not_a_video": "This link doesn't point to a video.",
 "host_not_allowed": "Videos from this site aren't supported for translation.",
 "unsupported_language": "This language isn't supported by the on-box translator.",
 "timeout": "Processing took too long and was stopped to protect the server.",
 "queue_full": "The translation queue is full right now. Try again in a few minutes.",
 "too_large": "The video file is too large to process on this server.",
 "generic": "Translation couldn't be completed for this video.",
}
RETRYABLE = {"rate_limited", "timeout", "queue_full", "generic", "download_blocked"}
NOTICE_TITLE = "Translation is not supported"
def reason_text(code): return REASONS.get(code or "generic", REASONS["generic"])
PLATFORM_LABEL = {"youtube": "YouTube", "telegram": "Telegram", "x": "X", "rumble": "Rumble", "direct": "the original site"}
def iso(t=None): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))

def normalize(url):
    """Allow-list validation. Returns (platform, key, canonical_url) or (None, reason_code, None). No arbitrary-URL fetches."""
    url = (url or "").strip()
    if len(url) > 600 or not re.match(r"^https?://", url, re.I): return None, "host_not_allowed", None
    try: u = urlparse(url)
    except Exception: return None, "host_not_allowed", None
    h = (u.hostname or "").lower(); h = h[4:] if h.startswith("www.") else h; h = h[2:] if h.startswith("m.") else h
    p = u.path or "/"
    if h in ("youtube.com", "youtube-nocookie.com", "music.youtube.com", "youtu.be"):
        vid = None
        if h == "youtu.be": vid = p.strip("/").split("/")[0]
        elif p == "/watch": vid = (parse_qs(u.query).get("v") or [""])[0]
        else:
            m = re.match(r"^/(?:shorts|live|embed|v)/([\w-]{11})", p); vid = m.group(1) if m else None
        if not vid or not re.fullmatch(r"[\w-]{11}", vid): return None, "not_a_video", None
        return "youtube", "yt:" + vid, f"https://www.youtube.com/watch?v={vid}"
    if h in ("t.me", "telegram.me"):
        m = re.match(r"^/(?:s/)?([A-Za-z0-9_]{4,64})/(\d{1,12})/?$", p)
        if not m: return None, "not_a_video", None
        return "telegram", f"tg:{m.group(1).lower()}/{m.group(2)}", f"https://t.me/{m.group(1)}/{m.group(2)}"
    if h in ("x.com", "twitter.com", "mobile.twitter.com"):
        m = re.match(r"^/([A-Za-z0-9_]{1,15}|i/web)/status/(\d{5,25})", p)
        if not m: return None, "not_a_video", None
        return "x", "x:" + m.group(2), f"https://x.com/{m.group(1)}/status/{m.group(2)}"
    if h == "rumble.com":
        m = re.match(r"^/(v[0-9a-z]{4,12})(?:-[\w-]*)?\.html$", p, re.I) or re.match(r"^/embed/(v[0-9a-z]{4,12})/?$", p, re.I)
        if not m: return None, "not_a_video", None
        return "rumble", "rumble:" + m.group(1).lower(), url.split("#")[0] if "/embed/" not in p else f"https://rumble.com/embed/{m.group(1)}/"
    if re.search(r"\.(mp4|webm|m4v|mov)$", p, re.I) and _in_alert_links(url):   # direct files only when an alert source linked them
        return "direct", "direct:" + re.sub(r"[^\w.:/-]", "_", url)[:300], url
    return None, "host_not_allowed", None
def _in_alert_links(url):
    try:
        b = sqlite3.connect(f"file:{BASE}/blackout.db?mode=ro", uri=True, timeout=10)
        try: return b.execute("SELECT 1 FROM clusters WHERE instr(links, ?) > 0 LIMIT 1", (json.dumps(url)[1:-1],)).fetchone() is not None
        finally: b.close()
    except Exception: return False

SCHEMA = """CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, url TEXT, platform TEXT, status TEXT, reason TEXT, detail TEXT,
 src_lang TEXT, lang_method TEXT, lang_prob REAL, method TEXT, model TEXT, duration REAL, is_live INTEGER, title TEXT, media_url TEXT, media_at TEXT,
 cues_en TEXT, cues_orig TEXT, partial TEXT, priority INTEGER DEFAULT 5, attempts INTEGER DEFAULT 0, source TEXT,
 created TEXT, updated TEXT, started TEXT, finished TEXT, proc_s REAL, audio_s REAL, retry_after TEXT, eta_s REAL);
CREATE INDEX IF NOT EXISTS jobs_q ON jobs(status, priority, created);"""
def db(ro=False):
    if ro:
        if not os.path.exists(VDB): db().close()
        c = sqlite3.connect(f"file:{VDB}?mode=ro", uri=True, timeout=20)
    else:
        c = sqlite3.connect(VDB, timeout=30); c.executescript(SCHEMA)
        try: c.execute("PRAGMA journal_mode=WAL")
        except Exception: pass
    c.row_factory = sqlite3.Row; return c
def vtt(cues):
    def ts(s): s = max(0.0, float(s)); return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"
    return "WEBVTT\n\n" + "\n\n".join(f"{i+1}\n{ts(a)} --> {ts(max(b, a + .5))}\n{t}" for i, (a, b, t) in enumerate(cues or [])) + "\n"
