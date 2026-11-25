"""Story-specific hashtags from the xAI (Grok) API, cached per story id (Nov 25 2026, Matt pt1873u).

Never runs inside a request: x_share.hashtags() calls lookup(), which returns the cached tags at once or queues ONE background
generation (bounded worker pool, per-hour cap, hard HTTP timeout) and returns None so the caller uses the rule-based entity extractor.
Every LLM tag is validated against the story text and the site dictionaries (no hallucinated company or place), at most one generic
filler tag, 3-5 tags. XAI_API_KEY is read from the environment only (never logged or printed).
Env: XAI_API_KEY (required), BN_XTAGS=0 kill switch, BN_XTAGS_MODEL (default = story writer model), BN_XTAGS_API, BN_XTAGS_PER_HOUR (default 240).
"""
from __future__ import annotations
import json, os, re, sys, threading, time, urllib.request, queue

_CACHE = {}          # cid -> (key, [tags])
_PENDING = set()
_Q = queue.Queue(maxsize=400)
_LOCK = threading.Lock()
_STAMPS = []
_STARTED = False
HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.environ.get("BN_XTAGS_CACHE") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "bn-xtags-cache.json")
GENERIC = {"#news", "#worldnews", "#breaking", "#breakingnews"}
ALLOWED_SECTOR = {"biotech", "stocks", "markets", "cybersecurity", "cyberattack", "war", "outbreak", "weather", "economy", "energy", "earthquake",
                  "wildfire", "flood", "tornado", "hurricane", "ransomware", "databreach", "cve", "politics", "election", "space", "science", "health", "crime",
                  "airstrike", "dronestrike", "missilestrike", "ukrainewar", "gaza", "israel", "russia", "ebola", "outbreak", "bankruptcy", "merger", "ipo"}


def _enabled():
    if os.environ.get("BN_XTAGS", "1") == "0":
        return False
    return bool((os.environ.get("XAI_API_KEY") or "").strip())


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _key(title, brief, loc):
    import hashlib
    return hashlib.sha1(f"{title}|{(brief or '')[:400]}|{loc}".encode("utf-8", "replace")).hexdigest()[:12]


def _load():
    try:
        with open(FILE, encoding="utf-8") as f:
            d = json.load(f)
        for k, v in d.items():
            _CACHE.setdefault(k, (v[0], v[1]))
    except Exception:
        pass


def _save():
    try:
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({k: [v[0], v[1]] for k, v in _CACHE.items()}, f)
        os.replace(tmp, FILE)
    except Exception:
        pass


def validate(tags, title, brief, loc, rule=None):
    """Keep only tags that name things present in the story text (or an allowed topic/sector word). Returns 3-5 tags or None."""
    text = _norm(f"{title} {brief} {loc}")
    rule_n = {_norm(t) for t in (rule or [])}
    out, generics = [], 0
    for raw in tags or []:
        t = "#" + re.sub(r"[^A-Za-z0-9]", "", str(raw))
        if len(t) < 3 or len(t) > 31 or t in out:
            continue
        n = t[1:].lower()
        if t.lower() in GENERIC:
            generics += 1
            if generics > 1:
                continue
        elif n not in text and n not in ALLOWED_SECTOR and n not in rule_n:
            continue   # not in the story and not a known topic word: could be invented
        out.append(t)
    out = out[:5]
    if len(out) < 3:
        return None
    return out


PROMPT = ("You write hashtags for one news item on a threat-monitoring site. Return ONLY JSON: {\"tags\":[\"#CamelCase\", ...]} with 3 to 5 hashtags.\n"
          "Rules: name the SPECIFIC things in the story, most specific first: the company (e.g. #TherivaBiologics), its stock ticker only if the text states it "
          "or you are certain (e.g. #TOVX), the exchange or market (#NYSEAmerican, #Nasdaq), people, organizations and agencies (#CDC, #WHO, #FAA), "
          "places (city, then country; use a company's HQ only if the story says it), diseases, weapons, hazards. Then AT MOST ONE broad sector tag "
          "(#Biotech, #Stocks, #Markets, #Cybersecurity, #War, #Outbreak, #Weather). Generic tags (#News #WorldNews #Breaking #BreakingNews) are a LAST "
          "RESORT and at most one. Never invent a name that is not in the text. No spaces or punctuation inside a tag. Do not tag a country that is only a "
          "side mention (e.g. do not use #UkraineWar for a story that merely mentions Ukraine).")


def _call(title, brief, loc):
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    api = (os.environ.get("BN_XTAGS_API") or os.environ.get("BN_WRITER_API") or "https://api.x.ai/v1").rstrip("/")
    model = os.environ.get("BN_XTAGS_MODEL") or os.environ.get("BN_WRITER_MODEL") or "grok-4.3"
    body = {"model": model, "temperature": 0, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Title: {title}\nLocation field: {loc or '-'}\nSummary: {(brief or '')[:900]}"}]}
    req = urllib.request.Request(api + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "blackout-network-xtags/1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    txt = d["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)).get("tags") or []


def _worker():
    while True:
        cid, title, brief, loc, rule = _Q.get()
        try:
            now = time.time()
            cap = int(os.environ.get("BN_XTAGS_PER_HOUR") or 240)
            _STAMPS[:] = [s for s in _STAMPS if now - s < 3600]
            if len(_STAMPS) >= cap:
                continue
            _STAMPS.append(now)
            tags = validate(_call(title, brief, loc), title, brief, loc, rule)
            if tags:
                with _LOCK:
                    _CACHE[cid] = (_key(title, brief, loc), tags)
                    _save()
                print("x_tags_llm: cached", cid, " ".join(tags), file=sys.stderr)
        except Exception as e:   # never logs the key or the request
            print("x_tags_llm: generation failed:", type(e).__name__, file=sys.stderr)
        finally:
            _PENDING.discard(cid)


def _start():
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    _load()
    for i in range(2):
        threading.Thread(target=_worker, name=f"xtags-{i}", daemon=True).start()


def lookup(cid, title, brief, loc, rule=None):
    """Cached validated LLM tags for this story, else None (and a background generation is queued)."""
    if not cid or not _enabled() or not re.fullmatch(r"[0-9a-f]{16}", cid):
        return None
    _start()
    k = _key(title, brief, loc)
    hit = _CACHE.get(cid)
    if hit and hit[0] == k:
        return list(hit[1])
    if cid not in _PENDING:
        try:
            _PENDING.add(cid)
            _Q.put_nowait((cid, title, brief, loc, rule))
        except Exception:
            _PENDING.discard(cid)
    return list(hit[1]) if hit else None
