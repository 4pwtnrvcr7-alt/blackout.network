#!/usr/bin/env python3
"""Story Arcs for Blackout Network (read-only view layer).

Groups scanner clusters into story threads ("arcs") and finds connections between arcs.
- Reads blackout.db READ-ONLY (file:...?mode=ro). Never writes scanner tables, never changes scores.
- Only persistence: arcs_settings.json (the selected time window).
Connection detection: each cluster title (+location) becomes a TF-IDF keyword vector (stopwords removed,
light stemming, place names/demonyms normalised and up-weighted). Clusters are processed in time order and
joined to the existing arc whose keyword centroid is most similar (cosine >= threshold, sharing distinctive
terms or a place + a term, within a time gap), otherwise they start a new arc; near-duplicate arcs are then
merged. Arc-to-arc "connections" are shared places/terms between arc centroids below the merge threshold.
"""
import json, math, os, re, sqlite3, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "blackout.db")
SETTINGS = os.path.join(BASE, "arcs_settings.json")
WINDOWS = {"6h": 6, "24h": 24, "3d": 72, "7d": 168, "30d": 720}
WINDOW_LABELS = {"6h": "6 hours", "24h": "24 hours", "3d": "3 days", "7d": "7 days", "30d": "30 days"}
DEFAULT_WINDOW = "24h"
JOIN_T = 0.30          # item -> arc centroid cosine to join an arc
MERGE_T2 = 0.22        # ...or this when they share 3+ distinctive core terms
MERGE_T = 0.42         # arc <-> arc centroid cosine to merge two arcs
ANCHOR_IDF = 5.8      # rare place names (e.g. Hormuz, Ras Tanura) anchor a story on their own
ANCHOR_T = 0.17
MIN_SHARED = 9.0      # min idf-weight of shared distinctive terms (~2 rare terms)
MAX_GAP_H = 72         # an item can't join an arc whose latest update is older than this
TEXT_CHARS = 260       # only the lead of long posts is used for matching (digests mention many stories)
MAX_ARCS = 150
MAX_UPDATES = 40

STOP = set("""a an the and or but if then than that this these those there their they them he she his her its it's it is are was were be been being
to of in on at by for from with without into onto over under about after before during between against among through amid via per as
not no nor so too very can could would should will shall may might must do does did done has have had having just also still even
says said say saying told tells report reports reported reportedly according claim claims claimed amid new latest update updates
breaking live news developing urgent alert alerts watch video videos footage photo photos thread read more via source sources channel
today tonight yesterday tomorrow now hours hour minutes minute day days week weeks month months year years ago time times
one two three four five six seven eight nine ten first second third last next many much more most some any all each every other another
who what when where why how which while whom whose here out off up down near around across back away again only own same such
mr mrs ms dr gov govt official officials people person us we our you your i me my him
http https www com org net html amp rt via x twitter telegram t.me
les des une pour dans sur avec par est sont aux qui que pas plus ses ces cette leur nous vous ils elle
der die das und den dem des ein eine einer mit von auf ist sind für nicht sich auch bei nach wie
los las del una por con para que sus como más pero
warning warnings watch watches issued until nws edt est mst pdt pst cdt mdt akdt akst hst utc gmt ist statement advisory advisories
january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday
notification population affected higher category speed speeds green orange level
""".split())

PLACES = {  # canonical place tokens (countries, regions, cities, waterways) -> used as entities
 "iran","israel","gaza","lebanon","syria","iraq","yemen","saudi","oman","qatar","uae","dubai","kuwait","bahrain","jordan","egypt","turkey",
 "hormuz","musandam","khasab","aden","riyadh","tehran","jerusalem","beirut","damascus","baghdad","sanaa","tanura","abqaiq","rabigh","red","gulf",
 "ukraine","russia","kyiv","kharkiv","odesa","dnipro","zaporizhzhia","lviv","moscow","crimea","belgorod","kursk","kaliningrad","donetsk","kherson",
 "poland","warsaw","germany","berlin","france","paris","spain","madrid","italy","rome","britain","london","ireland","netherlands","belgium",
 "hungary","romania","serbia","greece","sweden","finland","norway","denmark","baltic","estonia","latvia","lithuania","moldova","georgia","armenia","azerbaijan",
 "china","beijing","taiwan","japan","tokyo","korea","pyongyang","seoul","india","pakistan","afghanistan","bangladesh","myanmar","thailand","vietnam",
 "philippines","indonesia","malaysia","australia","zealand","bhutan","nepal","sri","lanka",
 "nigeria","kenya","ethiopia","tigray","sudan","somalia","congo","drc","uganda","tanzania","rwanda","mali","niger","chad","burkina","mozambique",
 "botswana","zambia","zimbabwe","malawi","madagascar","morocco","algeria","libya","tunisia","sahara","cameroon","ghana",
 "mexico","canada","brazil","argentina","chile","peru","colombia","venezuela","cuba","haiti","guyana","ecuador","bolivia",
 "florida","volusia","brevard","orlando","arizona","maricopa","coconino","navajo","vegas","nevada","texas","california","alaska","skagway",
 "keys","washington","york","chicago","hawaii","puerto","rico","caribbean","atlantic","pacific","europe","africa","asia","america","arctic","antarctica"}
ALIAS = {"kiev":"kyiv","iranian":"iran","iranians":"iran","irgc":"iran","israeli":"israel","israelis":"israel","idf":"israel","polish":"poland","polska":"poland",
 "pologne":"poland","polen":"poland","ukrainian":"ukraine","ukrainians":"ukraine","ukraina":"ukraine","russian":"russia","russians":"russia","rf":"russia",
 "saudis":"saudi","arabia":"saudi","yemeni":"yemen","houthis":"houthi","ansar":"houthi","chinese":"china","japanese":"japan","korean":"korea",
 "indian":"india","pakistani":"pakistan","nigerian":"nigeria","kenyan":"kenya","ethiopian":"ethiopia","sudanese":"sudan","congolese":"congo",
 "mexican":"mexico","canadian":"canada","brazilian":"brazil","venezuelan":"venezuela","cuban":"cuba","german":"germany","french":"france",
 "spanish":"spain","italian":"italy","british":"britain","uk":"britain","turkish":"turkey","türkiye":"turkey","syrian":"syria","iraqi":"iraq",
 "lebanese":"lebanon","egyptian":"egypt","emirates":"uae","taiwanese":"taiwan","filipino":"philippines","australian":"australia","european":"europe",
 "tankers":"tanker","missiles":"missile","drones":"drone","strikes":"strike","struck":"strike","striking":"strike","attacks":"attack","attacked":"attack",
 "attacking":"attack","explosions":"explosion","exploded":"explosion","blasts":"blast","killed":"kill","kills":"kill","killing":"kill","dead":"death",
 "deaths":"death","died":"death","tornadoes":"tornado","floods":"flood","flooding":"flood","flooded":"flood","storms":"storm","earthquakes":"earthquake",
 "quake":"earthquake","outbreaks":"outbreak","cases":"case","refineries":"refinery","mines":"mine","mined":"mine","outage":"blackout","outages":"blackout",
 "tusk":"tusk","coup":"coup","tribunal":"tribunal","constitutional":"constitutional","eboli":"ebola","wildfires":"wildfire","fires":"fire"}

ERE = re.compile(r"https?://\S+|www\.\S+|@\w+")
WRE = re.compile(r"[^\W\d_][\w'’\-]*[^\W_]|[^\W\d_]{2}", re.UNICODE)

def now(): return datetime.now(timezone.utc)
def iso(d): return d.strftime("%Y-%m-%dT%H:%M:%SZ")
def parse_t(s):
    if not s: return None
    try: return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        try: return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception: return None
def to_rank(score): return int((score or 0) / 10 + 0.5)

def et(d):
    """Format a UTC datetime in America/New_York with 'ET'."""
    try:
        from zoneinfo import ZoneInfo
        x = d.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        x = d - timedelta(hours=4)
    return x.strftime("%a %b %-d, %-I:%M %p") + " ET"

def clean_title(t, n=150):
    t = ERE.sub("", t or "")
    t = "".join(ch for ch in t if unicodedata.category(ch)[0] in "LNPZ" or ch in "$%&+'’\"()")
    t = re.sub(r"^\s*(?:[-–—:|•·➖]+\s*)*", "", t)
    t = re.sub(r"(?i)^\s*((breaking|developing|urgent|just in|live|alert)\s*(news)?\s*[:\-–—!|]*\s*)+", "", t)
    t = re.sub(r"(?i)^\s*source:\s*on x\s*", "", t)
    t = re.sub(r"[-–—➖]{2,}", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—:|•")
    return (t[:n - 1].rstrip() + "…") if len(t) > n else (t or "(untitled)")

def tokens(text):
    text = ERE.sub(" ", (text or "")[:TEXT_CHARS]).replace("#", " ").lower()
    out = []
    for w in WRE.findall(text):
        w = w.strip("'’-").replace("’", "'")
        if w.endswith("'s"): w = w[:-2]
        w = ALIAS.get(w, w)
        if len(w) < 3 and w not in ("uk", "us", "eu"): continue
        if w in STOP: continue
        if w not in PLACES and len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")): w = ALIAS.get(w[:-1], w[:-1])
        if w in STOP or len(w) < 3: continue
        out.append(w)
    return set(out)

def load_settings():
    try:
        with open(SETTINGS) as f: w = json.load(f).get("window")
        return w if w in WINDOWS else DEFAULT_WINDOW
    except Exception: return DEFAULT_WINDOW
def save_settings(w):
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w") as f: json.dump({"window": w, "updated": iso(now())}, f)
    os.chmod(tmp, 0o644); os.replace(tmp, SETTINGS)

def ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5); c.row_factory = sqlite3.Row; return c

def item_time(r):
    fs = parse_t(r["first_seen"]); ev = parse_t(r["event_time"])
    if ev and fs and fs - timedelta(days=3) <= ev <= fs + timedelta(minutes=30): return ev
    return fs or ev

class Vec:
    __slots__ = ("w", "n2")
    def __init__(self): self.w = defaultdict(float); self.n2 = 0.0
    def add(self, v):
        d = sum(self.w.get(k, 0.0) * x for k, x in v.items())
        self.n2 += 2 * d + sum(x * x for x in v.values())
        for k, x in v.items(): self.w[k] += x
    def cos(self, v, vn):
        if self.n2 <= 0 or vn <= 0: return 0.0
        return sum(self.w.get(k, 0.0) * x for k, x in v.items()) / math.sqrt(self.n2 * vn)
    def top(self, n=12): return [k for k, _ in sorted(self.w.items(), key=lambda kv: -kv[1])[:n]]

_cache = {}
_tok = {}
def tok_cached(text):
    t = _tok.get(text)
    if t is None:
        if len(_tok) > 50000: _tok.clear()
        t = _tok[text] = frozenset(tokens(text))
    return t
def compute(window):
    hours = WINDOWS[window]
    t0 = time.time()
    c = ro()
    try:
        cut = now() - timedelta(hours=hours)
        # pull a little earlier than the window so time can be judged on event_time/first_seen
        rows = c.execute("""SELECT cluster_id,title,category,location,event_time,first_seen,updated,score,rank,confidence,n_items,n_families,
                            families,links,watchlist FROM clusters WHERE first_seen>=? OR COALESCE(event_time,first_seen)>=?""",
                         (iso(cut - timedelta(hours=1)), iso(cut))).fetchall()
        rows = sorted(rows, key=lambda r: r["first_seen"] or "", reverse=True)[:MAX_ITEMS]
        docs_total = c.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
        corpus = c.execute("SELECT title, location FROM clusters ORDER BY first_seen DESC LIMIT 6000").fetchall()
    finally:
        c.close()
    df = Counter()
    for t, loc in corpus: df.update(tok_cached((t or "") + " " + (loc or "")))
    N = max(1, len(corpus))
    IDF = {w: math.log((N + 1) / (n + 1)) + 0.5 for w, n in df.items()}
    dflt = math.log(N + 1) + 0.5
    idf = lambda w: IDF.get(w, dflt)
    common = math.log((N + 1) / (0.06 * N + 1)) + 0.5     # tokens in >6% of docs are not "distinctive"

    items = []
    for r in rows:
        t = item_time(r)
        if not t or t < cut: continue
        toks = tok_cached((r["title"] or "") + " " + (r["location"] or ""))
        if not toks: continue
        v = {}
        for w in toks: v[w] = idf(w) * (1.35 if w in PLACES else 1.0)
        fams = json.loads(r["families"] or "[]"); links = json.loads(r["links"] or "[]")
        items.append({"id": r["cluster_id"], "t": t, "title": r["title"] or "", "category": r["category"], "location": r["location"],
                      "score": r["score"] or 0, "db_rank": r["rank"], "confidence": r["confidence"], "watchlist": r["watchlist"],
                      "families": fams, "links": links, "n_items": r["n_items"], "toks": toks, "v": v,
                      "vn": sum(x * x for x in v.values()), "first_seen": r["first_seen"]})
    items.sort(key=lambda x: x["t"])

    arcs = []; inv = defaultdict(set)
    for it in items:
        dist = {w for w in it["toks"] if idf(w) >= common}
        cands = set()
        for w in dist:
            st = inv.get(w)
            if st:
                stale = [ai for ai in st if (it["t"] - arcs[ai]["last"]).total_seconds() > MAX_GAP_H * 3600]
                for ai in stale: st.discard(ai)
                cands |= st
        best, bs = None, 0.0
        for ai in cands:
            a = arcs[ai]
            if a is None or (it["t"] - a["last"]).total_seconds() > MAX_GAP_H * 3600: continue
            shared = dist & a["toks"]
            if not shared: continue
            S = sum(it["v"][w] for w in shared)
            anchor = any(w in PLACES and idf(w) >= ANCHOR_IDF for w in shared)
            if S < MIN_SHARED and not (anchor and it["category"] == a["category"]): continue
            if not anchor and not (shared - PLACES): continue      # a shared country name alone is not a story link
            core = a.get("core")
            if core is None or a.get("core_n") != len(a["items"]):
                core = a["core"] = set(a["vec"].top(25)); a["core_n"] = len(a["items"])
            iw = sum(it["v"].values()) or 1
            cont = sum(x for k, x in it["v"].items() if k in core and idf(k) >= common) / iw
            s = max(a["vec"].cos(it["v"], it["vn"]), 0.85 * cont) + (0.03 if it["category"] == a["category"] else 0)
            need = JOIN_T if S >= MIN_SHARED else ANCHOR_T
            if anchor and S >= MIN_SHARED: need = ANCHOR_T
            if s >= need and s - need > bs: best, bs = ai, s - need
        if best is not None:
            a = arcs[best]
        else:
            a = {"vec": Vec(), "items": [], "toks": set(), "last": it["t"], "first": it["t"], "category": it["category"]}
            arcs.append(a); best = len(arcs) - 1
        a["items"].append(it); a["vec"].add(it["v"]); a["toks"] |= it["toks"]; a["last"] = max(a["last"], it["t"])
        for w in dist: inv[w].add(best)

    # merge near-duplicate arcs (order effects / fragments)
    live = [a for a in arcs if a]
    merged = True; rounds = 0
    while merged and rounds < 3:
        merged = False; rounds += 1
        tops = [set(a["vec"].top(14)) for a in live]
        idx = defaultdict(list)
        for i, tp in enumerate(tops):
            for w in tp:
                if idf(w) >= common: idx[w].append(i)
        dead = set()
        for i, a in enumerate(live):
            if i in dead: continue
            cand = set()
            for w in tops[i]: cand.update(j for j in idx.get(w, []) if j > i and j not in dead)
            for j in cand:
                b = live[j]
                lo = max(a["first"], b["first"])
                hi = min(a["last"], b["last"])
                if (lo - hi).total_seconds() > MAX_GAP_H * 3600: continue
                sh = {w for w in (tops[i] & tops[j]) if idf(w) >= common}
                if len(sh) < 2 and not any(w in PLACES and idf(w) >= ANCHOR_IDF for w in sh): continue
                small, big = (a, b) if a["vec"].n2 < b["vec"].n2 else (b, a)
                core = set(big["vec"].top(20)); sw = sum(small["vec"].w.values()) or 1
                cont = sum(x for k, x in small["vec"].w.items() if k in core and idf(k) >= common) / sw
                s = max(cosv(a["vec"], b["vec"]), 0.85 * cont)
                if s >= MERGE_T or (s >= MERGE_T2 and len(sh) >= 3):
                    for it in b["items"]: a["vec"].add(it["v"])
                    a["items"] += b["items"]; a["toks"] |= b["toks"]; a["last"] = max(a["last"], b["last"]); a["first"] = min(a["first"], b["first"]); dead.add(j); merged = True
        live = [a for k, a in enumerate(live) if k not in dead]

    out = []
    for a in live:
        its = sorted(a["items"], key=lambda x: x["t"])
        ranks = [to_rank(x["score"]) for x in its]
        peak = max(ranks)
        if peak <= 2 and (len(its) < 2 or (len(its) < 3 and len({f for x in its for f in x["families"]}) < 2)): continue
        fams = []
        for x in its:
            for f in x["families"]:
                if f not in fams: fams.append(f)
        # title: highest severity, then most source families, then latest
        head = max(its, key=lambda x: (x["score"], len(x["families"]), x["t"]))
        top_terms = [w for w in a["vec"].top(14) if idf(w) >= common * 0.8][:8]
        ups = []; seen_f = set(); seen_t = set(); prev_r = None
        for x, rk in zip(its, ranks):
            ch = []
            if prev_r is None: ch.append("first report")
            else:
                nf = [f for f in x["families"] if f not in seen_f]
                if nf: ch.append("new source: " + ", ".join(nf[:3]))
                if rk > prev_r: ch.append(f"severity up {prev_r}→{rk}")
                elif rk < prev_r: ch.append(f"severity down {prev_r}→{rk}")
                nt = sorted((w for w in x["toks"] - seen_t if idf(w) >= common), key=lambda w: -idf(w))[:4]
                if nt: ch.append("new detail: " + ", ".join(nt))
                if len(ch) == 0: ch.append("repeat coverage")
            seen_f.update(x["families"]); seen_t |= x["toks"]; prev_r = rk
            ups.append({"cluster_id": x["id"], "time": iso(x["t"]), "time_et": et(x["t"]), "title": clean_title(x["title"], 200),
                        "category": x["category"], "rank": rk, "score": x["score"], "db_rank": x["db_rank"], "confidence": x["confidence"],
                        "watchlist": bool(x["watchlist"]), "unconfirmed": bool(x["watchlist"]) or len(x["families"]) < 2,
                        "families": x["families"], "links": [l for l in x["links"] if isinstance(l, dict) and l.get("url")][:4],
                        "changed": "; ".join(ch)})
        cats = Counter(x["category"] for x in its)
        start, last = its[0]["t"], its[-1]["t"]
        out.append({"id": "arc_" + its[0]["id"][:10], "title": clean_title(head["title"]), "category": cats.most_common(1)[0][0],
                    "categories": dict(cats), "start": iso(start), "start_et": et(start), "latest": iso(last), "latest_et": et(last),
                    "severity": peak, "severity_basis": "peak rank in window (0-10 = score/10 rounded)",
                    "peak_score": max(x["score"] for x in its), "latest_rank": ranks[-1], "latest_score": its[-1]["score"],
                    "n_updates": len(its), "n_sources": len(fams), "sources": fams[:20], "terms": top_terms,
                    "places": [w for w in a["vec"].top(20) if w in PLACES][:5], "confirmed": len(fams) >= 2,
                    "updates": ups[-MAX_UPDATES:], "updates_truncated": max(0, len(ups) - MAX_UPDATES),
                    "_vec": a["vec"]})
    out.sort(key=lambda a: (a["latest"], a["severity"]), reverse=True)
    total = len(out)
    out = out[:MAX_ARCS]
    # connections between displayed arcs: shared places/distinctive terms, below merge threshold
    byid = {a["id"]: a for a in out}
    for a in out: a["connections"] = []
    for i, a in enumerate(out):
        ta = set(a["_vec"].top(15))
        for b in out[i + 1:]:
            tb = set(b["_vec"].top(15)); sh = ta & tb
            places = sorted(w for w in sh if w in PLACES)
            terms = sorted((w for w in sh if w not in PLACES and idf(w) >= common), key=lambda w: -idf(w))
            if not ((places and terms) or len(terms) >= 2 or len(places) >= 2): continue
            s = cosv(a["_vec"], b["_vec"])
            if s < 0.08: continue
            shared = (places + terms)[:5]
            a["connections"].append({"arc": b["id"], "title": b["title"][:70], "shared": shared, "strength": round(s, 2)})
            b["connections"].append({"arc": a["id"], "title": a["title"][:70], "shared": shared, "strength": round(s, 2)})
    for a in out:
        a["connections"] = sorted(a["connections"], key=lambda x: -x["strength"])[:5]
        del a["_vec"]
    res = {"window": window, "window_label": WINDOW_LABELS[window], "hours": hours, "generated": iso(now()), "generated_et": et(now()),
           "clusters_in_window": len(items), "arcs_total": total, "arcs_returned": len(out),
           "multi_update_arcs": sum(1 for a in out if a["n_updates"] > 1), "compute_ms": int((time.time() - t0) * 1000),
           "severity_note": "Severity is the peak rank in the window on the 0-10 chat scale (score/10 rounded); raw scores kept. Read-only view: scores are not changed.",
           "windows": list(WINDOWS), "window_labels": WINDOW_LABELS, "arcs": out}
    return res

import threading
_lock = threading.Lock(); _busy = set()
CACHE_S = 240
MAX_ITEMS = 8000   # most recent clusters considered (keeps 30d responses fast as data grows)
def get(window):
    """Cached arcs: fresh for CACHE_S; after that, serve the cached copy and recompute in the background."""
    ent = _cache.get(window)
    if ent and time.time() - ent[0] < CACHE_S: return ent[1]
    if ent:
        with _lock:
            if window in _busy: return ent[1]
            _busy.add(window)
        def bg():
            try: _cache[window] = (time.time(), compute(window))
            except Exception: pass
            finally: _busy.discard(window)
        threading.Thread(target=bg, daemon=True).start()
        return ent[1]
    res = compute(window); _cache[window] = (time.time(), res); return res

def cosv(a, b):
    if a.n2 <= 0 or b.n2 <= 0: return 0.0
    if len(a.w) > len(b.w): a, b = b, a
    return sum(x * b.w.get(k, 0.0) for k, x in a.w.items()) / math.sqrt(a.n2 * b.n2)

# ---- HTTP glue (called from server.py) ----
def handle_get(path, qs):
    if path == "/api/arcs_window": return 200, {"window": load_settings(), "allowed": list(WINDOWS), "labels": WINDOW_LABELS}
    if path == "/api/arcs":
        w = (qs.get("window") or [None])[0] or load_settings()
        if w not in WINDOWS: return 400, {"error": f"window must be one of {list(WINDOWS)}"}
        return 200, get(w)
    return 404, {"error": "not found"}

def handle_post(path, d):
    if path == "/api/arcs_window":
        w = str((d or {}).get("window") or "")
        if w not in WINDOWS: return 400, {"error": f"window must be one of {list(WINDOWS)}"}
        save_settings(w); return 200, {"status": "ok", "window": w, "label": WINDOW_LABELS[w]}
    return 404, {"error": "not found"}

if __name__ == "__main__":
    import sys
    r = compute(sys.argv[1] if len(sys.argv) > 1 else "24h")
    print(json.dumps({k: v for k, v in r.items() if k != "arcs"}, indent=1))
    kws = sys.argv[3:] 
    for a in r["arcs"][:int(sys.argv[2]) if len(sys.argv) > 2 else 40]:
        if kws and not any(k.lower() in (" ".join(u["title"] for u in a["updates"])).lower() for k in kws): continue
        print(f'[{a["severity"]}] u={a["n_updates"]} s={a["n_sources"]} {a["latest_et"]} | {a["title"][:90]} | {",".join(a["terms"][:6])} | conn={[(c["arc"][-4:],c["shared"]) for c in a["connections"][:3]]}')
        if kws:
            for u in a["updates"]: print("      ", u["time_et"][4:], u["rank"], u["changed"][:60], "|", u["title"][:80])
