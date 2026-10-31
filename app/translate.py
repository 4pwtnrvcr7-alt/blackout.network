"""Translate add-on: display-only machine translation for the dashboard (language picker, Show original, RTL).
Routes: GET  /api/translate/app.js | app.css   (client script + styles, from translate_static/)
        GET  /api/translate/langs              (installed target languages with native names)
        GET  /api/translate/stats              (cache + engine stats)
        POST /api/translate {to, texts:[...]}  (batched; answers from translate_cache.db, misses go to the sidecar)
Engine: offline Argos Translate / CTranslate2 sidecar on 127.0.0.1:8788 (translate_service.py, run_translate.sh). No third party.
Translations live ONLY in translate_cache.db. blackout.db is read only via file:blackout.db?mode=ro (cache warm-up of
current alert titles/briefs for languages visitors actually picked). Never touches scanner.py, scoring, push.py, jets.py, config.json."""
import hashlib, json, os, re, sqlite3, sys, threading, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "translate_static")
CACHE = os.path.join(BASE, "translate_cache.db")
ALERTS_DB = os.path.join(BASE, "blackout.db")
SIDECAR = os.environ.get("BN_TRANSLATE_URL", "http://127.0.0.1:8788")
FILES = {"app.js": "application/javascript", "app.css": "text/css"}
MAX_TEXTS, MAX_CHARS = 200, 2000
MISS_BUDGET = (12000, 300)         # per IP: at most 12000 uncached strings per 5 min (MT is CPU-heavy once public)
NATIVE = {"en": "English", "ar": "العربية", "az": "Azərbaycanca", "bg": "Български", "bn": "বাংলা", "ca": "Català", "cs": "Čeština",
    "da": "Dansk", "de": "Deutsch", "el": "Ελληνικά", "eo": "Esperanto", "es": "Español", "et": "Eesti", "eu": "Euskara", "fa": "فارسی",
    "fi": "Suomi", "fr": "Français", "ga": "Gaeilge", "gl": "Galego", "he": "עברית", "hi": "हिन्दी", "hu": "Magyar", "id": "Bahasa Indonesia",
    "it": "Italiano", "ja": "日本語", "ko": "한국어", "ky": "Кыргызча", "lt": "Lietuvių", "lv": "Latviešu", "ms": "Bahasa Melayu",
    "nb": "Norsk bokmål", "nl": "Nederlands", "pb": "Português (Brasil)", "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
    "sk": "Slovenčina", "sl": "Slovenščina", "sq": "Shqip", "sv": "Svenska", "sw": "Kiswahili", "th": "ไทย", "tl": "Tagalog", "tr": "Türkçe",
    "uk": "Українська", "ur": "اردو", "vi": "Tiếng Việt", "zh": "中文（简体）", "zt": "中文（繁體）"}
ENGLISH = {"ar": "Arabic", "az": "Azerbaijani", "bg": "Bulgarian", "bn": "Bengali", "ca": "Catalan", "cs": "Czech", "da": "Danish", "de": "German",
    "el": "Greek", "eo": "Esperanto", "es": "Spanish", "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish", "fr": "French",
    "ga": "Irish", "gl": "Galician", "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "ky": "Kyrgyz", "lt": "Lithuanian", "lv": "Latvian", "ms": "Malay", "nb": "Norwegian Bokmål", "nl": "Dutch",
    "pb": "Portuguese (Brazil)", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak", "sl": "Slovenian",
    "sq": "Albanian", "sv": "Swedish", "sw": "Swahili", "th": "Thai", "tl": "Tagalog", "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu",
    "vi": "Vietnamese", "zh": "Chinese (Simplified)", "zt": "Chinese (Traditional)"}
RTL = {"ar", "fa", "he", "ur"}

_S = getattr(sys, "_bn_translate_state", None)
if _S is None:
    _S = sys._bn_translate_state = {"lock": threading.Lock(), "langs": None, "langs_t": 0, "ips": {}, "warm": None, "warm_stamp": None,
                                    "hits": 0, "misses": 0, "mt_ms": 0, "mt_batches": 0, "errors": 0}

def _cache():
    c = sqlite3.connect(CACHE, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS tr (lang TEXT, h TEXT, src TEXT, out TEXT, created REAL, PRIMARY KEY(lang, h))")
    c.execute("CREATE TABLE IF NOT EXISTS usage (lang TEXT PRIMARY KEY, last REAL, requests INTEGER)")
    return c

def _h(s): return hashlib.sha1(s.encode()).hexdigest()

def langs():
    if _S["langs"] is None or time.time() - _S["langs_t"] > 300:
        try:
            with urllib.request.urlopen(SIDECAR + "/langs", timeout=5) as r: _S["langs"] = json.load(r)["langs"]
        except Exception:
            if _S["langs"] is None: return []
        _S["langs_t"] = time.time()
    return _S["langs"]

def _mt(to, texts):
    out = []
    for i in range(0, len(texts), 400):
        chunk = texts[i:i + 400]
        req = urllib.request.Request(SIDECAR + "/translate", data=json.dumps({"to": to, "texts": chunk}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r: j = json.load(r)
        _S["mt_ms"] += j.get("ms", 0); _S["mt_batches"] += 1
        out += j["out"]
    return out

GLOSSARY_FILE = os.path.join(BASE, "translate_glossary.json")
def glossary():
    try:
        mt = os.path.getmtime(GLOSSARY_FILE)
        if _S.get("gl_mt") != mt:
            g = json.load(open(GLOSSARY_FILE, encoding="utf-8")); L = g["_langs"]
            _S["gl"] = {l: {k.casefold(): v[i] for k, v in g.items() if not k.startswith("_")} for i, l in enumerate(L)}; _S["gl_mt"] = mt
    except Exception: _S.setdefault("gl", {})
    return _S.get("gl", {})
_AFFIX = re.compile(r"^([\W_]*?)(\w.*?)([^\w.!?)\"\u201d'%]*)$", re.S)
def translate(to, texts, ip=None, warm=False):
    """Emoji/punctuation affixes are kept as-is; the core is looked up in the hand-checked glossary, then the cache, then MT."""
    parts = []
    for t in texts:
        m = _AFFIX.match(t)
        parts.append(m.groups() if m else ("", t, ""))
    gl = glossary().get(to, {})
    todo = [core for _, core, _ in parts if core.casefold() not in gl]
    got = dict(zip(todo, _translate_cached(to, todo, ip, warm))) if todo else {}
    return [pre + (gl.get(core.casefold()) or got.get(core, core)) + suf for pre, core, suf in parts]

def _translate_cached(to, texts, ip=None, warm=False):
    """Returns translations in order. Cache first; misses batched to the sidecar and stored in translate_cache.db only."""
    c = _cache()
    try:
        res, miss = {}, []
        uniq = list(dict.fromkeys(texts))
        for i in range(0, len(uniq), 400):
            part = uniq[i:i + 400]; hs = {_h(t): t for t in part}
            for h, o in c.execute(f"SELECT h, out FROM tr WHERE lang=? AND h IN ({','.join('?' * len(hs))})", (to, *hs)):
                res[hs[h]] = o
        miss = [t for t in uniq if t not in res]
        if not warm:
            _S["hits"] += len(uniq) - len(miss); _S["misses"] += len(miss)
            c.execute("INSERT INTO usage VALUES(?,?,1) ON CONFLICT(lang) DO UPDATE SET last=excluded.last, requests=requests+1", (to, time.time()))
        if miss and ip is not None:
            now = time.time(); b = [x for x in _S["ips"].get(ip, []) if now - x[0] < MISS_BUDGET[1]]
            if sum(n for _, n in b) + len(miss) > MISS_BUDGET[0]:
                _S["ips"][ip] = b; c.commit()
                raise OverflowError("rate")
            b.append((now, len(miss))); _S["ips"][ip] = b
        c.commit()
        if miss:
            with _S["lock"]:    # one MT batch + cache write at a time (sidecar is single-queue anyway)
                hs = {_h(t): t for t in miss}
                for h, o in c.execute(f"SELECT h, out FROM tr WHERE lang=? AND h IN ({','.join('?' * len(hs))})", (to, *hs)): res[hs[h]] = o
                miss = [t for t in miss if t not in res]      # another request may have filled them while we waited
                if miss:
                    out = _mt(to, miss)
                    c.executemany("INSERT OR REPLACE INTO tr VALUES(?,?,?,?,?)", [(to, _h(s), s, o, time.time()) for s, o in zip(miss, out)])
                    c.commit(); res.update(zip(miss, out))
        return [res[t] for t in texts]
    finally:
        c.close()

# --- same segmentation as app.js, so warmed alert text hits the cache the browser asks for ---
PROTECT = re.compile(r"(https?://\S+|\bblackout\.network\b|\s·\s|\s\|\s)", re.I)
def segments(s):
    out = []
    for part in PROTECT.split(s or ""):
        if not part or PROTECT.fullmatch(part): continue
        t = part.strip()
        if re.search(r"[^\W\d_]{2,}", t): out.append(t)
    return out

def _warm_loop():
    """Every 2 min: if the alert feed changed, pre-translate current Wire/Watchlist titles+briefs into languages picked in the last 7 days."""
    while True:
        time.sleep(120)
        try:
            a = sqlite3.connect(f"file:{ALERTS_DB}?mode=ro", uri=True, timeout=10)
            try:
                stamp = a.execute("SELECT MAX(updated) FROM clusters").fetchone()[0]
                if stamp == _S["warm_stamp"]: continue
                rows = a.execute("""SELECT title, brief FROM clusters WHERE COALESCE(event_time, first_seen) >= datetime('now','-7 days')
                                    ORDER BY score DESC, event_time DESC LIMIT 400""").fetchall()
            finally: a.close()
            c = _cache()
            try: used = [r[0] for r in c.execute("SELECT lang FROM usage WHERE last > ? ORDER BY last DESC LIMIT 6", (time.time() - 7 * 86400,))]
            finally: c.close()
            texts = list(dict.fromkeys(seg for t, b in rows for x in (t, b) for seg in segments(x) if len(seg) <= MAX_CHARS))
            t0 = time.time()
            for lang in used:
                if lang in langs():
                    for i in range(0, len(texts), 40):      # small chunks so visitors' requests interleave with the warm-up
                        translate(lang, texts[i:i + 40], warm=True); time.sleep(0.05)
            _S["warm_stamp"] = stamp; _S["warm"] = {"at": time.time(), "langs": used, "texts": len(texts), "secs": round(time.time() - t0, 1)}
        except Exception as ex:
            _S["errors"] += 1; _S["warm"] = {"error": str(ex)[:200], "at": time.time()}

if not getattr(sys, "_bn_translate_warm", None):
    sys._bn_translate_warm = threading.Thread(target=_warm_loop, daemon=True); sys._bn_translate_warm.start()

def stats():
    c = _cache()
    try:
        per = {l: n for l, n in c.execute("SELECT lang, COUNT(*) FROM tr GROUP BY lang")}
        usage = {l: {"last": t, "requests": n} for l, t, n in c.execute("SELECT * FROM usage")}
    finally: c.close()
    size = sum(os.path.getsize(CACHE + x) for x in ("", "-wal") if os.path.exists(CACHE + x))
    return {"engine": "Argos Translate (offline, CTranslate2 on CPU)", "languages": len(langs()), "cached_strings": sum(per.values()),
            "cached_by_lang": per, "cache_bytes": size, "hits": _S["hits"], "misses": _S["misses"], "mt_batches": _S["mt_batches"],
            "mt_ms_total": _S["mt_ms"], "errors": _S["errors"], "last_error": _S.get("last_error"), "warm": _S["warm"], "usage": usage}

def handle_get(path, qs):
    name = path.rsplit("/", 1)[-1]
    if name in FILES:
        with open(os.path.join(STATIC, name), "rb") as f: return 200, f.read(), FILES[name]
    if path == "/api/translate/langs":
        ls = langs()
        return 200, {"default": "en", "engine": "offline" if ls else "unavailable", "rtl": sorted(RTL),
                     "langs": [{"code": "en", "native": "English", "english": "English"}] +
                              sorted(({"code": l, "native": NATIVE.get(l, l), "english": ENGLISH.get(l, l)} for l in ls), key=lambda x: x["english"])}
    if path == "/api/translate/stats": return 200, stats()
    return 404, {"error": "not found"}

def handle_post(path, data, ip=None):
    if path != "/api/translate": return 404, {"error": "not found"}
    to = str(data.get("to", "")); texts = data.get("texts")
    if to not in langs(): return 400, {"error": "unsupported language"}
    if not isinstance(texts, list) or not texts or len(texts) > MAX_TEXTS: return 400, {"error": f"texts must be a list of 1-{MAX_TEXTS} strings"}
    texts = [str(t)[:MAX_CHARS] for t in texts]
    t0 = time.time()
    try: out = translate(to, texts, ip=ip)
    except OverflowError: out = None
    except Exception as ex:
        _S["errors"] += 1; _S["last_error"] = f"{time.strftime('%H:%M:%S')} {type(ex).__name__}: {str(ex)[:160]}"; return 503, {"error": "translation engine unavailable", "detail": str(ex)[:120]}
    if out is None: return 429, {"error": "translation rate limit, try again in a few minutes"}
    return 200, {"to": to, "out": out, "ms": int((time.time() - t0) * 1000), "note": "Machine-translated. Original English is authoritative."}
