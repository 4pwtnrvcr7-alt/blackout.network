#!/usr/bin/env python3
"""BLACKOUT.NETWORK Wire post-publish QA (Matt, Nov 25 2026 11:18-11:20 PM ET).

Independent of the site's pre-publish validator (app/wire_check.py): its own rules, its own code path.
Python 3 standard library only. Read-only HTTP against the live site, no paid APIs, no LLM.

Loop (launchd KeepAlive daemon com.blackout.wireqa): every ~10 s
  1. GET /api/wire_tl?limit=40 (served from the site's 3 s page cache; If-None-Match / If-Modified-Since sent when the site gives them)
  2. for each live item not seen before: GET /wire/<id> (Full Story page) and its og:image (first bytes + size only)
     and, when the sync key is on this Mac, one signed POST /internal/wire/qa for the card's photo facts
  3. checks: photo card (not text fallback, map or satellite), category vs text, photo vs category, location vs text,
     tag rules, real write-up, headline not cut on a dangling word, Full Story resolves
  4. a failing item is held through the signed /internal/wire/qa hold list (same HMAC key the sync uses). With no key on this
     Mac, nothing is held: the failure is logged and FLAG_qa_unheld.txt is written.
  5. held items are re-checked every 5 min and released when they pass. Errors and 429 back off 10 s -> 5 min.
Logs: ~/blackout_mac/wire_qa/logs/YYYYMMDD.jsonl (one line per checked item) and wire_qa.log. Never prints keys.
Run once:  python3 wire_qa.py --once [--no-hold]
"""
import hashlib, hmac, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

SITE = os.environ.get("BN_QA_SITE", "https://blackout.network").rstrip("/")
HOME = os.path.abspath(os.environ.get("BN_QA_HOME") or os.path.join(os.path.expanduser("~"), "blackout_mac", "wire_qa"))
LOGS = os.path.join(HOME, "logs")
STATE = os.path.join(HOME, "state.json")
FLAG = os.path.join(HOME, "FLAG_qa_unheld.txt")
OFF = os.path.join(HOME, "OFF")                      # touch this file to pause the loop
SLEEP_S = float(os.environ.get("BN_QA_SLEEP_S", "10"))
PASS_BUDGET_S = 18.0                                 # one pass stays under 20 s; leftovers wait for the next pass
UA = "bn-wire-qa/1 (+mac)"
PHOTO_MIN = 60000                                    # photo cards are 60 KB+; the text fallback is ~24-58 KB
RULES_OFF = {x.strip() for x in os.environ.get("BN_QA_RULES_OFF", "").split(",") if x.strip()}   # e.g. thin-writeup
SYSTEMIC = 0.6                                       # >60% of >=8 new items failing one rule = a QA problem: flag, don't hold

def now_et():
    return time.strftime("%Y-%m-%d %H:%M:%S %Z")

def log(msg):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, "wire_qa.log"), "a") as f:
        f.write(f"[{now_et()}] {msg}\n")

def jl(rec):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, time.strftime("%Y%m%d") + ".jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ------------------------------------------------------------------ signing key (never printed, never stored here)
def _key():
    k = os.environ.get("BN_SYNC_SECRET", "")
    if len(k) >= 32:
        return k
    root = os.path.dirname(HOME)
    for p in (os.environ.get("BN_RENDER_SYNC_ENV", ""), os.path.join(root, ".env"), os.path.join(root, "app", ".env")):
        try:
            for line in open(p):
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if line.startswith("BN_SYNC_SECRET="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if len(v) >= 32:
                        return v
        except OSError:
            pass
    return ""

# ------------------------------------------------------------------ HTTP
class Busy(Exception):
    pass

def get(path, head=None, limit=None, timeout=12):
    url = path if path.startswith("http") else SITE + path
    r = urllib.request.Request(url, headers=dict({"User-Agent": UA}, **(head or {})))
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            body = resp.read(limit) if limit else resp.read()
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            raise Busy(str(e.code))
        return e.code, dict(e.headers or {}), b""

def signed(path, payload, key):
    raw = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = hmac.new(key.encode(), f"{ts}\nPOST\n{path}\n{hashlib.sha256(raw).hexdigest()}".encode(), hashlib.sha256).hexdigest()
    r = urllib.request.Request(SITE + path, data=raw, method="POST",
                               headers={"X-BN-Ts": ts, "X-BN-Sig": sig, "User-Agent": UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Busy("429")
        return e.code, {}
    except Exception as ex:
        return 0, {"error": type(ex).__name__}

# ------------------------------------------------------------------ rules (independent of app/wire_check.py)
CAT = {
    "conflict": r"war|strike|missile|drone|troops|military|army|attack|airstrike|shell(?:ing)?|rocket|raid|invasion|militant|insurgent|ceasefire|frontline|forces|hostage|bomb|explosion|navy|naval|idf|hamas|hezbollah|houthi|isis|isil",
    "politics": r"election|vote|president|minister|parliament|congress|senate|government|policy|bill|law|court|coup|party|campaign|sanction|diplomat|summit|treaty|cabinet|governor|mayor|white house|trump|biden|rubio",
    "scandal": r"scandal|corruption|bribe|fraud|embezzl|indict|probe|investigation|resign|leak|misconduct",
    "unrest": r"protest|riot|demonstrat|unrest|strike|march|clash|rally|curfew|tear gas",
    "crime": r"murder|kill|shoot|shot|stab|arrest|police|crime|homicide|robbery|kidnap|gang|charged|suspect|sentenced|court|trafficking|indict",
    "deaths": r"dies|died|dead|death|obituar|passed away|funeral",
    "people": r"\b[A-Z][a-z]+ [A-Z][a-z]+",
    "disease": r"outbreak|virus|disease|case|infection|epidemic|pandemic|cholera|measles|mpox|ebola|flu|influenza|dengue|meningitis|health|vaccine|who\b|cdc",
    "quake": r"earthquake|quake|magnitude|seismic|tsunami|volcan|eruption|ash|\bM ?\d",
    "weather": r"storm|hurricane|typhoon|cyclone|tornado|flood|rain|snow|blizzard|wind|heat|wildfire|fire|weather|nor'?easter|ice|freeze|drought|warning|advisory|ground stop|faa",
    "wreck": r"crash|collision|derail|wreck|capsiz|sank|sink|accident|plane|train|bus|tanker|vessel|ship|aircraft|runway|fire|explosion|blast",
    "infra": r"outage|power|grid|blackout|internet|cable|water|pipeline|dam|bridge|network|electric|telecom|ioda|cloudflare|aws|down",
    "hazard": r"spill|leak|chemical|toxic|radiation|explosion|blast|evacuat|hazard|gas|fire|smoke|contamina",
    "space": r"solar|geomagnetic|flare|cme|aurora|space|satellite|kp|noaa swpc|asteroid|meteor|reentry|launch",
    "cyber": r"cyber|hack|breach|ransomware|malware|vulnerab|cve|exploit|phishing|ddos|patch|security|password|data leak|zero-day",
    "markets": r"market|stock|shares|bank|dollar|bitcoin|crypto|price|economy|economic|inflation|rate|fed\b|treasury|bond|trade|tariff|oil|gold|index|investor|financial|fund|debt",
    "uap": r"ufo|uap|unidentified|aerial phenomen|alien",
    "faith": r"church|pope|vatican|religio|mosque|temple|bishop|faith|christian|muslim|jewish|catholic",
    "other": r".",
}
STRONG = {   # unmistakable signs of another category (used only to confirm a mismatch)
    "weather": r"hurricane|typhoon|tornado|blizzard|nor'?easter|winter storm|coastal storm|flood(?:ing|s)?\b|wildfire|heat wave",
    "quake": r"earthquake|magnitude \d|\bM ?\d\.\d|tsunami|eruption|volcanic ash",
    "disease": r"outbreak|epidemic|cholera|measles|mpox|ebola|meningitis",
    "cyber": r"ransomware|cve-\d|vulnerabilit|data breach|hackers?\b|malware",
    "space": r"geomagnetic|solar flare|\bcme\b|aurora",
    "conflict": r"airstrike|missile strike|drone strike|shelling|troops|ceasefire|idf|hamas|hezbollah|houthi",
    "wreck": r"plane crash|derail|capsiz|collision|crashed",
    "sports": r"\b(nfl|nba|mlb|nhl|fifa|uefa|ligue|premier league|champions league|pitcher|quarterback|touchdown|grand prix|f1 teams|world cup|playoffs?)\b",
}
PHOTO_BAD_ALL = r"satellite|avhrr|modis|goes-\d|from space|\bmap\b|locator|relief|topograph|blue marble|earth from"
PHOTO_BY_CAT = {   # photo words that do not belong on a category
    "conflict": r"hurricane|storm|flood|tornado|earthquake|volcan|kremlin|st\.? basil|clock tower|cathedral|skyline",
    "crime": r"hurricane|storm|flood|tornado|earthquake|volcan|kremlin|st\.? basil|skyline",
    "wreck": r"hurricane|storm|earthquake|volcan|kremlin|st\.? basil",
    "politics": r"hurricane|storm damage|flood|tornado|earthquake|volcan|wreck",
    "cyber": r"hurricane|storm|flood|tornado|earthquake|volcan",
    "markets": r"hurricane|storm|flood|tornado|earthquake|volcan",
    "weather": r"earthquake|volcan|tank|soldier|missile",
    "quake": r"hurricane|storm|tornado|soldier|missile",
}
STOP = set("""a an the and or of to in on at for with by from as into over after amid about than that its his her their our is are
was were be been has have had but nor via this these those which who what when where why how later maybe logged nov dec jan
says said new latest breaking update live report watch read video audio more just also only""".split())
BADTAGS = {"news", "blackoutnetwork", "breaking", "update", "maybe", "later", "which", "whathappened", "loggednov", "live", "video"}
AGENCY = re.compile(r"^\s*(?:[A-Z]{4}\s+)?(?:VAAC|WAAF|SCEZ|RPHI|MHCC|RJTD|KNES|EGRR|LFPW|SABM|ADRM|YMMC|NZKL|CWAO|PAWU|FMEE|VABB)\b")
BOILER = re.compile(r"(The record places this[^.]*\.|\d+ independent sources? in our record[^.]*\.|The record marks confidence[^.]*\.|"
                    r"This has been reported by a single[^.]*\.|from the reports we track\.|Logged [A-Z][a-z]{2} \d+[^.]*\.)")

def page_text(raw):
    s = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))

def writeup_words(text, headline):
    a = text.find("01 What happened")
    if a < 0:
        return 0
    b = text.find("03 ", a + 20)
    body = BOILER.sub(" ", text[a + 16: b if b > a else a + 3000])
    body = body.replace("02 Why it matters", " ").replace(headline, " ")
    return len(re.findall(r"[A-Za-z]{3,}", body))

def check(it, key, facts):
    cid = it["id"]; h = it.get("h") or ""; k = it.get("k") or "other"; loc = it.get("loc") or ""
    fails, notes = [], []
    # Full Story resolves
    code, hd, raw = get(f"/wire/{cid}", timeout=15)
    if code != 200:
        return ["full-story-" + str(code)], notes, {}
    text = page_text(raw.decode("utf-8", "ignore"))
    blob = (h + " " + text[text.find("01 What happened"):][:3000]).lower() if "01 What happened" in text else h.lower()
    # write-up
    w = writeup_words(text, h)
    if w < 25:
        fails.append(f"thin-writeup:{w}w")
    # og card
    m = re.search(r'property="og:image" content="([^"]+)"', raw.decode("utf-8", "ignore")) or re.search(r'og:image" content="([^"]+)"', raw.decode("utf-8", "ignore"))
    size = 0
    if not m:
        fails.append("og-missing")
    else:
        c2, hd2, b2 = get(html.unescape(m.group(1)), limit=16, timeout=15)
        size = int(hd2.get("Content-Length") or 0)
        if c2 != 200 or not b2.startswith(b"\x89PNG"):
            fails.append(f"og-bad:{c2}")
        elif size and size < PHOTO_MIN:
            fails.append(f"og-text-fallback:{size}")
    f = facts.get(cid) or {}
    pdesc = " ".join(str(f.get(x) or "") for x in ("photo_src", "caption", "label", "card_src")).lower()
    if f:
        if re.search(PHOTO_BAD_ALL, pdesc):
            fails.append("photo-map-or-satellite")
        bad = PHOTO_BY_CAT.get(k)
        if bad and re.search(bad, pdesc) and not re.search(bad, blob):
            fails.append("photo-misfit:" + re.search(bad, pdesc).group(0))
    elif key:
        notes.append("photo-facts-unavailable")
    # category vs text
    own = re.search(r"\b(?:" + CAT.get(k, ".") + r")", blob, re.I)
    if k == "other":
        own = True
    strong = [c for c, rx in STRONG.items() if c != k and re.search(rx, blob, re.I)]
    if "sports" in strong and k not in ("other", "people"):
        fails.append(f"category:{k}->sports")
    elif not own and [c for c in strong if c != "sports"]:
        fails.append(f"category:{k}->{[c for c in strong if c != 'sports'][0]}")
    # location
    if loc:
        if AGENCY.search(loc):
            fails.append("location-agency-code")
        else:
            words = [x for x in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", loc) if x.lower() not in STOP]
            if words and not any(x.lower() in blob or x.lower() in text.lower() for x in words):
                fails.append("location-not-in-text:" + loc[:40])
    # tags
    q = urllib.parse.parse_qs(urllib.parse.urlparse(it.get("xu") or "").query).get("text", [""])[0]
    tags = re.findall(r"#(\w+)", q)
    if not 3 <= len(tags) <= 5:
        fails.append(f"tags-count:{len(tags)}")
    for t in tags:
        parts = [p.lower() for p in re.findall(r"[A-Z]{2,}(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", t)]
        if (t.lower() in BADTAGS or not t[0].isupper() or len(t) > 22 or (parts and all(p in STOP for p in parts))
                or (len(parts) >= 2 and parts[-1] in STOP)):
            fails.append("tag:" + t)
    # dangling headline
    last = re.sub(r"[\u2026.]+$", "", h.strip()).split()[-1:] or [""]
    if last[0].lower().strip(",;:-") in STOP - {"live", "video", "update"} and last[0][:1].islower():
        fails.append("headline-dangling:" + last[0])
    fails = [x for x in fails if x.split(":")[0] not in RULES_OFF]
    return fails, notes, {"og_bytes": size, "writeup_words": w}

# ------------------------------------------------------------------ state
def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"seen": {}, "held": {}, "etag": "", "lm": "", "last_sync": 0}

def save(st):
    if len(st["seen"]) > 6000:
        for k in sorted(st["seen"], key=st["seen"].get)[:3000]:
            st["seen"].pop(k, None)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE)

def flag(lines):
    with open(FLAG, "a") as f:
        for ln in lines:
            f.write(f"[{now_et()}] {ln}\n")

def push_holds(st, key, release=()):
    if not key:
        return False
    cut = time.time() - 48 * 3600
    holds = {c: v["why"] for c, v in st["held"].items() if v["at"] >= cut}
    code, j = signed("/internal/wire/qa", {"holds": holds, "replace": True, "release": list(release)}, key)
    if code == 200:
        st["last_sync"] = time.time()
        return True
    log(f"hold push failed: HTTP {code}")
    return False

def facts_for(ids, key):
    if not key or not ids:
        return {}
    code, j = signed("/internal/wire/qa", {"info": ids}, key)
    return (j or {}).get("info") or {} if code == 200 else {}

def one_pass(st, key, hold=True):
    t0 = time.time()
    hdr = {}
    if st.get("etag"): hdr["If-None-Match"] = st["etag"]
    if st.get("lm"): hdr["If-Modified-Since"] = st["lm"]
    code, hd, body = get("/api/wire_tl?limit=40", head=hdr)
    if code == 304:
        items = []
    elif code != 200:
        raise Busy(f"wire_tl {code}")
    else:
        st["etag"] = hd.get("ETag") or ""; st["lm"] = hd.get("Last-Modified") or ""
        items = [x for x in json.loads(body).get("items", []) if not x.get("a")]
    new = [x for x in items if x["id"] not in st["seen"] and x["id"] not in st["held"]]
    facts = facts_for([x["id"] for x in new], key)
    results = []
    for it in new:
        if time.time() - t0 > PASS_BUDGET_S:
            break
        try:
            fails, notes, meta = check(it, key, facts)
        except Busy:
            raise
        except Exception as ex:
            fails, notes, meta = [], [f"check-error:{type(ex).__name__}"], {}
        results.append((it, fails, notes, meta))
        st["seen"][it["id"]] = time.time()
    # systemic guard: one rule failing most of a batch is treated as a QA problem, not 6 bad stories
    rule_n = {}
    for _, fails, _, _ in results:
        for r in {f.split(":")[0] for f in fails}:
            rule_n[r] = rule_n.get(r, 0) + 1
    systemic = {r for r, n in rule_n.items() if len(results) >= 8 and n > SYSTEMIC * len(results)}
    to_hold, unheld = {}, []
    for it, fails, notes, meta in results:
        real = [f for f in fails if f.split(":")[0] not in systemic]
        act = "pass" if not fails else ("hold" if real and hold and key else "flag")
        if real and hold and key:
            to_hold[it["id"]] = ",".join(real)[:200]
        elif fails:
            unheld.append(f"{it['id']} {','.join(fails)[:160]} | {it.get('h','')[:80]}")
        jl({"at": now_et(), "id": it["id"], "k": it.get("k"), "h": it.get("h", "")[:140], "fs": it.get("fs"),
            "result": act, "fails": fails, "notes": notes, "systemic": sorted(systemic & {f.split(':')[0] for f in fails}), **meta,
            "url": f"{SITE}/wire/{it['id']}"})
    if to_hold:
        for c, why in to_hold.items():
            it = next(x for x, *_ in results if x["id"] == c)
            st["held"][c] = {"why": why, "at": time.time(), "checked": time.time(),
                             "it": {k: it.get(k) for k in ("id", "h", "k", "loc", "xu", "fs")}}
        if not push_holds(st, key):
            unheld += [f"{c} {w} (hold push failed)" for c, w in to_hold.items()]
    if unheld:
        flag(unheld)
    # re-check holds every 5 min (at most 5 per pass), release the ones that pass now
    rel = []
    for c, v in list(st["held"].items()):
        if time.time() - t0 > PASS_BUDGET_S or len(rel) >= 5:
            break
        if time.time() - v["at"] > 48 * 3600:
            st["held"].pop(c); continue
        if time.time() - v.get("checked", 0) < 300:
            continue
        v["checked"] = time.time()
        try:
            it = dict(v.get("it") or {})
            if not it.get("h"):
                continue                     # no stored fields: keep the hold
            fails, _, _ = check(it, key, facts_for([c], key))
            if not fails:
                rel.append(c); st["held"].pop(c)
                jl({"at": now_et(), "id": c, "result": "released"})
        except Busy:
            raise
        except Exception:
            pass
    if rel or (key and st["held"] and time.time() - st.get("last_sync", 0) > 300):
        push_holds(st, key, release=rel)    # re-send the whole list every 5 min: a site restart loses holds for <= 5 min
    return results, systemic

def main():
    os.makedirs(LOGS, exist_ok=True)
    once = "--once" in sys.argv; hold = "--no-hold" not in sys.argv
    key = _key()
    log(f"start: site {SITE}, holds {'on' if (key and hold) else 'OFF (no sync key on this Mac or --no-hold): failures are flagged'}")
    back = 0.0
    while True:
        if os.path.exists(OFF) and not once:
            time.sleep(30); continue
        st = load()
        try:
            res, systemic = one_pass(st, key, hold)
            save(st)
            if res:
                n = len(res); ok = sum(1 for r in res if not r[1])
                log(f"pass: {n} new, {ok} passed, {n-ok} failed" + (f", systemic (not held): {sorted(systemic)}" if systemic else ""))
            back = 0.0
        except Busy as ex:
            save(st); back = min(300.0, max(10.0, back * 2)); log(f"site busy ({ex}): backing off {back:.0f} s")
        except Exception as ex:
            save(st); back = min(300.0, max(10.0, back * 2)); log(f"error {type(ex).__name__}: {str(ex)[:120]}; backing off {back:.0f} s")
        if once:
            return
        time.sleep(SLEEP_S + back)

if __name__ == "__main__":
    main()
