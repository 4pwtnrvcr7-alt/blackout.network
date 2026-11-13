#!/usr/bin/env python3
"""People layer for BLACKOUT.NETWORK (t1351u, Nov 13 2026). Box-side only; called from story_reports/build.py.

What it does, every story_reports cycle:
  1. Finds public figures named in the current stories (titles, scanner briefs, report headlines, desk notes):
       - a curated seed list (same names and patterns as the Key Figures tab, figures.py) matched by pattern, and
       - new names: capitalised "First Last" pairs that show up in the stories, resolved on Wikidata (human, with an English
         Wikipedia article, and a public role: an office held, a party, or a public-life occupation). Unknown pairs are cached
         as "not a person" for 30 days so they cost nothing next cycle.
  2. Builds a profile per person from free, keyless sources and keeps every fact tied to its source:
       - Wikidata (CC0): born, birthplace, party, offices held with dates, education, employers, spouse/parents, ideology.
       - English Wikipedia (CC BY-SA 4.0): lead summary and short excerpts of the article's own sections (early life, career,
         political positions, controversies, public image), each linked to its section. Nothing is paraphrased or invented.
       - Wikimedia Commons: the Wikidata portrait plus up to 6 freely licensed photos from the article (PD / CC0 / CC BY /
         CC BY-SA only; author, license and file page kept for the credit line). The site serves them same-origin.
  3. Links stories to people (current board + the history it has seen before, kept in people/registry.json).
  4. Finds a credited lead photo for stories that have none: the main person's Commons portrait, else a Commons photo of the
     story's place (labelled as a file photo, not from the event).

Wikimedia API etiquette: one request at a time, a descriptive User-Agent with contact address, gzip, maxlag on Wikidata (20 s by default for these read-only calls; we wait and retry, then stop for the cycle),
back off on 429/503/maxlag, every response cached on disk (search 30 days, entities and articles 7 days), and a hard
per-cycle request and time budget. Kill switch: BN_PEOPLE=0 in the environment, or the file desk/people_off.
Never touches blackout.db, scanner.py, scoring, push.py, jets.py or config.json. Never prints a secret (there are none here).
"""
import hashlib, html, io, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error, gzip
from datetime import datetime, timezone, timedelta

UTC = timezone.utc
PV = 7   # profile format/version: a profile built by an older version is rebuilt
UA = "BLACKOUT.NETWORK-people/1.0 (https://blackout.network/people; hello@blackout.network) python-urllib"
HERE = os.path.dirname(os.path.abspath(__file__))
PDIR = os.path.join(HERE, "people")
CACHE = os.path.join(PDIR, "cache")
REG = os.path.join(PDIR, "registry.json")
KILL = os.path.join(HERE, "desk", "people_off")
LIC_OK = re.compile(r"public domain|^pd\b|^pd-|cc0|cc[ -]by|^attribution", re.I)
LIC_BAD = re.compile(r"\bnc\b|\bnd\b|non-?commercial|no ?deriv|non-?free|fair use|all rights reserved", re.I)
BANNED = re.compile(r"\b(?:un)?verified\b|\bverif(?:y|ies|ying)\b|\bfirst to\b|\bbefore the news\b|\bbreaking\b", re.I)

MAXLAG = int(os.environ.get("BN_PEOPLE_MAXLAG", "20"))   # read-only calls; Wikidata folds query-service lag (often 10 s+) into maxlag

def log(*a): print("people:", *a, file=sys.stderr, flush=True)
def now(): return time.time()

# ------------------------------------------------------------------ seed (same people and patterns as figures.py, the Key Figures tab)
SEED = [
 ("trump", "Q22686", r"\bTrump\b(?!\s+(?:Tower|Media|National|Doral))"), ("mkhamenei", "Q2919350", r"\bMojtaba\s+Khamenei\b|\bKhamenei\b"),
 ("araghchi", "Q7459020", r"\bAraghchi\b"), ("rezaei", "Q545979", r"\bMohsen\s+Rezaei\b|\bRezaei\b"), ("rubio", "Q324546", r"\bRubio\b"),
 ("bessent", "Q7435987", r"\bBessent\b"), ("netanyahu", "Q43723", r"\bNetanyahu\b"), ("zelensky", "Q3874799", r"\bZelensk(?:y|yy|iy|ii)\b"),
 ("putin", "Q7747", r"\bPutin\b"), ("carney", "Q192533", r"\bMark\s+Carney\b|\bCarney\b"), ("nikitin", "Q19910481", r"\bGleb\s+Nikitin\b"),
 ("tedros", "Q16196017", r"\bTedros\b"), ("musk", "Q317521", r"\bElon\s+Musk\b|\bMusk(?:'s)?\b"), ("vance", "Q28935729", r"\bJ\.?\s?D\.?\s+Vance\b|\bVance\b"),
 ("hegseth", "Q7172014", r"\bHegseth\b"), ("patel", "Q104639732", r"\bKash\s+Patel\b|\bFBI Director Patel\b"), ("hobbs", "Q16226012", r"\bKatie\s+Hobbs\b|\bGov(?:ernor|\.)?\s+Hobbs\b"),
 ("kimju", "Q56226", r"\bKim\s+Jong[\s-]?Un\b"), ("xi", "Q15031", r"\bXi\s+Jinping\b|\bPresident\s+Xi\b|\bXi's\b"), ("pezeshkian", "Q5933752", r"\bPezeshkian\b"),
 ("tusk", "Q946", r"\bDonald\s+Tusk\b|\bTusk\b"), ("nawrocki", "Q17704749", r"\bNawrocki\b"), ("erdogan", "Q39259", r"\bErdo[gğ]an\b"),
 ("modi", "Q1058", r"\bNarendra\s+Modi\b|\bModi\b"), ("macron", "Q3052772", r"\bMacron\b"), ("merz", "Q566257", r"\bFriedrich\s+Merz\b|\bMerz\b"),
 ("lula", "Q37181", r"\bLula\b"), ("mbs", "Q6892571", r"\bMohammed\s+bin\s+Salman\b|\bMBS\b"), ("lavrov", "Q58217", r"\bLavrov\b"),
 ("sheinbaum", "Q5771800", r"\bSheinbaum\b"), ("lukashenko", "Q2866", r"\bLukashenk[oa]\b"), ("thompson", "Q109379578", r"\bTrina\s+(?:L\.\s+)?Thompson\b"),
]
# Public-role filter for names found automatically (Wikidata P106 occupation ids)
ROLE_OCC = {"Q82955", "Q43845", "Q131524", "Q193391", "Q189290", "Q47064", "Q212238", "Q16533", "Q484876", "Q116", "Q1423891", "Q30461",
            "Q372436", "Q1097498", "Q15627169", "Q12097", "Q4991371", "Q1930187", "Q2285706", "Q83307", "Q806798",
            "Q48352", "Q3242115"}
ROLE_DESC = re.compile(r"politician|minister|president|prime minister|chancellor|official|executive|ceo|chief|business|entrepreneur|investor|"
                       r"general|admiral|commander|military|leader|senator|governor|secretary|ambassador|diplomat|judge|justice|attorney|"
                       r"militant|spokes|founder|chairman|chairwoman|king|queen|prince|princess|monarch|emir|sultan|pope|cleric|ayatollah|"
                       r"director of|director-general|mayor|congress|representative|member of|parliament|activist|journalist|commentator|spy chief|negotiator|envoy", re.I)
STOP1 = set("""the a an and of in on at for to by with from as is are was be new old north south east west central united us u.s. breaking live
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august september october november december
white house supreme court air force navy army marine coast guard national state federal department ministry police fire red cross prime
former deputy acting chief senior general president vice minister secretary governor senator rep sen gov dr mr mrs ms sir lord st saint
world global breaking update watch video photos exclusive report reports analysis opinion latest news today tonight morning evening
iran israel ukraine russia china gaza hamas hezbollah houthi houthis israeli iranian russian chinese ukrainian american british french german""".split())

# ------------------------------------------------------------------ Wikimedia client: serial, cached, budgeted, polite
class WM:
    def __init__(self, budget=400, seconds=240, gap=0.12, offline=False):
        self.left, self.until, self.gap, self.off = budget, now() + seconds, gap, offline
        self.last, self.stopped, self.sent, self.hits = 0.0, "", 0, 0
        os.makedirs(CACHE, exist_ok=True)

    def _path(self, key): return os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest()[:24] + ".json")

    def can(self): return not self.off and not self.stopped and self.left > 0 and now() < self.until

    def get(self, base, params, ttl=7 * 86400):
        q = dict(params, format="json")
        if "wikidata.org" in base: q["maxlag"] = MAXLAG
        url = base + "?" + urllib.parse.urlencode(sorted(q.items()))
        return self.url(url, ttl)

    def url(self, url, ttl=7 * 86400):
        p = self._path(url); old = None
        try:
            with open(p, encoding="utf-8") as f: old = json.load(f)
            if now() - old["t"] < ttl: self.hits += 1; return old["v"]
        except Exception: pass
        if not self.can(): return old["v"] if old else None
        wait = self.gap - (now() - self.last)
        if wait > 0: time.sleep(wait)
        self.left -= 1; self.sent += 1; self.last = now()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read(30_000_000)
                if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
            v = json.loads(raw)
            if isinstance(v, dict) and (v.get("error") or {}).get("code") == "maxlag":
                self.lagged = getattr(self, "lagged", 0) + 1
                if self.lagged > 3:
                    self.stopped = "maxlag"; log("Wikidata maxlag, backing off for this cycle"); return old["v"] if old else None
                time.sleep(5 * self.lagged); return self.url(url, ttl)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                self.stopped = f"HTTP {e.code}"; log(f"Wikimedia {e.code}, backing off for this cycle")
                return old["v"] if old else None
            v = {"_http": e.code}
        except Exception as ex:
            return old["v"] if old else None
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump({"t": now(), "v": v}, f, ensure_ascii=False)
        os.replace(tmp, p)
        return v

    def raw(self, url, limit=4_000_000):
        """Image bytes (not cached here; callers keep their own files)."""
        if not self.can(): return None
        wait = self.gap - (now() - self.last)
        if wait > 0: time.sleep(wait)
        self.left -= 1; self.sent += 1; self.last = now()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
            with urllib.request.urlopen(req, timeout=25) as r: return r.read(limit)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503): self.stopped = f"HTTP {e.code}"
            return None
        except Exception: return None

WD = "https://www.wikidata.org/w/api.php"; WP = "https://en.wikipedia.org/w/api.php"; CM = "https://commons.wikimedia.org/w/api.php"

def entities(wm, ids, props="labels|descriptions|claims|sitelinks", ttl=7 * 86400):
    out = {}
    ids = [i for i in dict.fromkeys(ids) if re.fullmatch(r"Q\d+", i or "")]
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        v = wm.get(WD, {"action": "wbgetentities", "ids": "|".join(chunk), "props": props, "languages": "en", "sitefilter": "enwiki"}, ttl) or {}
        out.update((v.get("entities") or {}))
    return out

def label(e): return ((e or {}).get("labels") or {}).get("en", {}).get("value", "")
def desc(e): return ((e or {}).get("descriptions") or {}).get("en", {}).get("value", "")
def enwiki(e): return (((e or {}).get("sitelinks") or {}).get("enwiki") or {}).get("title", "")

def claims(e, P):
    out = []
    for c in ((e or {}).get("claims") or {}).get(P, []):
        if c.get("rank") == "deprecated": continue
        dv = (c.get("mainsnak") or {}).get("datavalue") or {}
        v = dv.get("value")
        if isinstance(v, dict) and "id" in v: v = v["id"]
        elif isinstance(v, dict) and "time" in v: v = (v["time"], v.get("precision", 11))
        elif isinstance(v, dict) and "text" in v: v = v["text"]
        q = {}
        for qp, qs in (c.get("qualifiers") or {}).items():
            for s in qs:
                d = (s.get("datavalue") or {}).get("value")
                if isinstance(d, dict) and "time" in d: q[qp] = (d["time"], d.get("precision", 11))
                elif isinstance(d, dict) and "id" in d: q.setdefault(qp, d["id"])
        if v is not None: out.append({"v": v, "q": q, "rank": c.get("rank")})
    pref = [x for x in out if x["rank"] == "preferred"]
    return pref + [x for x in out if x["rank"] != "preferred"]

MONTHS = "January February March April May June July August September October November December".split()
def wdate(t):
    """('+1946-06-14T00:00:00Z', 11) -> ('1946-06-14', 'June 14, 1946')."""
    if not t: return "", ""
    s, p = t
    m = re.match(r"([+-])(\d{1,4})-(\d\d)-(\d\d)", s or "")
    if not m: return "", ""
    y, mo, d = int(m.group(2)), int(m.group(3)), int(m.group(4))
    if m.group(1) == "-": return "", ""
    if p >= 11 and mo and d: return f"{y:04d}-{mo:02d}-{d:02d}", f"{MONTHS[mo - 1]} {d}, {y}"
    if p == 10 and mo: return f"{y:04d}-{mo:02d}", f"{MONTHS[mo - 1]} {y}"
    return f"{y:04d}", str(y)

# ------------------------------------------------------------------ Wikipedia article: sections and sentences
_ABBR = re.compile(r"\b(U\.S|U\.K|U\.N|D\.C|Jr|Sr|Dr|Mr|Mrs|Ms|St|Gen|Lt|Col|Maj|Sgt|Capt|Adm|Gov|Sen|Rep|No|Inc|Ltd|Co|Corp|vs|Ph\.D|E\.U|a\.m|p\.m|[A-Z])\.")
def sentences(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    if not t: return []
    t = _ABBR.sub(lambda m: m.group(1).replace(".", "\u2024") + "\u2024", t)
    out = [s.replace("\u2024", ".").strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(0-9])", t)]
    return [s for s in out if len(s) > 25 and not BANNED.search(s)]

def excerpt(t, n=3, cap=700):
    out = ""
    for s in sentences(t)[:n]:
        if out and len(out) + len(s) > cap: break
        out = (out + " " + s).strip()
    return out[:cap + 200]

def parse_sections(text):
    """[(level, heading, body_text_including_subsections, own_text)] from an explaintext extract (exsectionformat=wiki)."""
    parts = re.split(r"\n(={2,5})\s*(.+?)\s*\1\n", "\n" + (text or ""))
    lead = parts[0].strip(); secs = []
    for i in range(1, len(parts) - 2, 3):
        secs.append([len(parts[i]), parts[i + 1].strip(), parts[i + 2].strip()])
    out = []
    for i, (lv, h, own) in enumerate(secs):
        body = [own]
        for lv2, h2, own2 in secs[i + 1:]:
            if lv2 <= lv: break
            body.append(own2)
        out.append((lv, h, "\n".join(b for b in body if b), own))
    return lead, out

def anchor(title, heading=""):
    u = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    return u + ("#" + urllib.parse.quote(heading.replace(" ", "_")) if heading else "")

SEC = {
 "early": re.compile(r"^(early (life|years)|childhood|background|early life and (education|career|family))", re.I),
 "education": re.compile(r"education", re.I),
 "family": re.compile(r"^(personal life|family|marriage|personal|family and personal life|private life)", re.I),
 "career": re.compile(r"career|business|military service|professional|working life|early career", re.I),
 "ideology": re.compile(r"political (positions|views|ideology|stances?)|^ideolog|^views$|^positions|policy positions|political beliefs|^platform|^political philosophy", re.I),
 "controv": re.compile(r"controvers|scandal|legal (issues|affairs|troubles|cases)|allegation|investigation|indictment|lawsuit|criminal|misconduct|accusation|"
                       r"sanction|impeachment|corruption|criticism|conflicts? of interest|fraud|trial|conviction|arrest warrant|war crimes", re.I),
 "image": re.compile(r"public (image|profile|perception|opinion)|reception|legacy|assessment|approval|reputation|popularity|criticism and praise|evaluation", re.I),
 "actions": re.compile(r"presiden(cy|t of)|first term|second term|tenure|in office|^as |administration|premiership|leadership|chancellorship|secretary of|"
                       r"minister of|director of|foreign policy|domestic policy|economic policy|governorship|chairman|chief executive|government", re.I),
}
_PRO_OLD = re.compile(r"\b(praised|praise|supporters|admirers|credited|lauded|applauded|commended|popular among|popularity|hailed|endorsed|defended)\b", re.I)
_CON_OLD = re.compile(r"\b(critics|criticized|criticised|criticism|condemned|denounced|accused|opponents|backlash|controversial|condemnation|protest(?:ed|s)?)\b", re.I)
GOAL = re.compile(r"\b(pledged|promised|vowed|goal|aims? to|seeks? to|campaigned on|agenda|platform|called for|advocat(?:es|ed)|supports|favou?rs|opposes|proposed)\b", re.I)

def pick(secs, key, n=3, cap=700, used=None):
    for lv, h, body, own in secs:
        if SEC[key].search(h) and body.strip() and (used is None or h not in used):
            ex = excerpt(body, n, cap)
            if ex:
                if used is not None: used.add(h)
                return {"text": ex, "section": h}
    return None

# ------------------------------------------------------------------ profile
def commons_info(wm, files, width=960):
    """{file: info} for free-licensed Commons files (PD / CC0 / CC BY / CC BY-SA), with author, license, file page, thumb url."""
    out = {}
    files = [f for f in dict.fromkeys(files) if f]
    for k in range(0, len(files), 8):
        chunk = files[k:k + 8]
        v = wm.get(CM, {"action": "query", "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": width,
                        "titles": "|".join("File:" + f for f in chunk)}) or {}
        for pg in ((v.get("query") or {}).get("pages") or {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii: continue
            md = ii.get("extmetadata") or {}
            g = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", (md.get(x) or {}).get("value", "") or ""))).strip()
            lic = g("LicenseShortName"); artist = re.sub(r"^(?:Autor|Author|Auteur|Photo)\s*:\s*", "", g("Artist"), flags=re.I)
            if not lic or not LIC_OK.search(lic) or LIC_BAD.search(lic): continue
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"): continue
            if not artist and not re.search(r"public domain|^pd|cc0", lic, re.I): continue      # CC licenses need a named author for the credit
            th = ii.get("thumburl") or ii.get("url") or ""
            if urllib.parse.urlsplit(th).hostname not in ("upload.wikimedia.org", "thumb.wikimedia.org"): continue
            fn = pg.get("title", "").removeprefix("File:")
            out[fn] = {"file": fn, "src": th, "w": ii.get("thumbwidth") or ii.get("width"), "h": ii.get("thumbheight") or ii.get("height"),
                       "license": lic, "license_url": g("LicenseUrl") or None, "author": (artist or "Unknown author")[:140],
                       "credit_line": g("Credit")[:160], "desc": excerpt(g("ImageDescription"), 1, 220) or g("ObjectName")[:200],
                       "date": g("DateTimeOriginal")[:10] or g("DateTime")[:10], "source": ii.get("descriptionurl") or ("https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(fn.replace(" ", "_")))}
    return out

BAD_FILE = re.compile(r"logo|flag|seal|signature|coat[_ ]of[_ ]arms|emblem|map|locator|icon|chart|graph|diagram|results|electoral|\.svg$|banner|"
                      r"election|ballot|poll|composite|collage|montage|cartoon|caricature|tweet|screenshot|stamp|coin|banknote|insignia|badge", re.I)

def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[\u0300-\u036f]", "", __import__("unicodedata").normalize("NFKD", name.lower()))).strip("-")
    return s[:60] or "person"

def build_profile(wm, qid, seed_key=""):
    ent = entities(wm, [qid]).get(qid)
    if not ent or ent.get("missing") is not None: return None
    name = label(ent); title = enwiki(ent)
    if not name or not title: return None
    P = lambda p: claims(ent, p)
    born_iso, born = wdate((P("P569") or [{}])[0].get("v") if P("P569") else None)
    died_iso, died = wdate(P("P570")[0]["v"]) if P("P570") else ("", "")
    if died_iso and died_iso[:4] < "2010": return None
    refs = set()
    for p in ("P19", "P27", "P102", "P39", "P69", "P108", "P106", "P26", "P22", "P25", "P1038", "P241", "P410", "P1142", "P140", "P20", "P463", "P166"):
        for c in P(p):
            if isinstance(c["v"], str) and re.fullmatch(r"Q\d+", c["v"]): refs.add(c["v"])
            for qv in c["q"].values():
                if isinstance(qv, str) and re.fullmatch(r"Q\d+", qv): refs.add(qv)
    R = entities(wm, sorted(refs), props="labels|descriptions")
    L = lambda q: label(R.get(q)) or ""
    # birthplace country and party ideology need the claims of a few linked items
    deep = [c["v"] for c in P("P19")[:1]] + [c["v"] for c in P("P102")[:3]]
    D = entities(wm, deep, props="labels|claims") if deep else {}
    bp = P("P19")[0]["v"] if P("P19") else ""
    bp_country = ""
    if bp and D.get(bp):
        cq = (claims(D[bp], "P17") or [{}])[0].get("v")
        if cq:
            bp_country = label(entities(wm, [cq], props="labels").get(cq))
    born_in = ", ".join(x for x in (L(bp), bp_country) if x and x != L(bp) or x == L(bp))
    if bp_country and bp_country == L(bp): born_in = L(bp)
    def span(c):
        a = wdate(c["q"].get("P580"))[1]; b = wdate(c["q"].get("P582"))[1]
        return a, b
    positions = []
    for c in P("P39"):
        if not L(c["v"]): continue
        a, b = span(c); sa = wdate(c["q"].get("P580"))[0]
        positions.append({"title": L(c["v"]) + (f" ({L(c['q']['P642'])})" if c["q"].get("P642") and L(c["q"]["P642"]) else ""), "from": a, "to": b, "sort": sa, "current": bool(a and not b)})
    positions.sort(key=lambda x: x["sort"] or "0", reverse=True)
    parties = []
    for c in P("P102"):
        a, b = span(c); parties.append({"name": L(c["v"]), "from": a, "to": b, "sort": wdate(c["q"].get("P580"))[0]})
    parties = [p for p in parties if p["name"]]
    parties.sort(key=lambda x: x["sort"] or "0", reverse=True)
    ideol = [L(c["v"]) for c in P("P1142") if L(c["v"])]
    for pq in [c["v"] for c in P("P102")[:1]]:
        for c in claims(D.get(pq), "P1142")[:4]:
            ideol.append(c["v"])
    idq = [x for x in ideol if re.fullmatch(r"Q\d+", x)]
    if idq:
        IL = entities(wm, idq, props="labels")
        ideol = [label(IL.get(x)) if re.fullmatch(r"Q\d+", x) else x for x in ideol]
    ideol = [x for x in dict.fromkeys(ideol) if x][:6]
    edu = []
    for c in P("P69"):
        if L(c["v"]): edu.append({"name": L(c["v"]), "to": wdate(c["q"].get("P582"))[1], "sort": wdate(c["q"].get("P582"))[0] or wdate(c["q"].get("P580"))[0]})
    edu.sort(key=lambda x: x["sort"] or "9")
    jobs = []
    for c in P("P108"):
        if L(c["v"]):
            a, b = span(c); jobs.append({"name": L(c["v"]), "from": a, "to": b, "sort": wdate(c["q"].get("P580"))[0]})
    jobs.sort(key=lambda x: x["sort"] or "0", reverse=True)
    occ = [L(c["v"]) for c in P("P106") if L(c["v"])][:8]
    fam = {"spouses": [], "parents": [], "relatives": [], "children": 0}
    for c in P("P26"):
        if L(c["v"]): a, b = span(c); fam["spouses"].append({"name": L(c["v"]), "from": a, "to": b})
    for p in ("P22", "P25"):
        for c in P(p):
            if L(c["v"]): fam["parents"].append(L(c["v"]))
    for c in P("P1038")[:6]:
        if L(c["v"]): fam["relatives"].append(L(c["v"]))
    n_kids = P("P1971")
    fam["children"] = int(float(n_kids[0]["v"]["amount"])) if n_kids and isinstance(n_kids[0]["v"], dict) and "amount" in n_kids[0]["v"] else len(P("P40"))
    branch = [L(c["v"]) for c in P("P241") if L(c["v"])][:3]
    rank_mil = [L(c["v"]) for c in P("P410") if L(c["v"])][:2]
    citizenship = [L(c["v"]) for c in P("P27") if L(c["v"])][:3]
    religion = [L(c["v"]) for c in P("P140") if L(c["v"])][:2]
    website = (P("P856") or [{}])[0].get("v", "") if P("P856") else ""
    # ---- Wikipedia article
    v = wm.get(WP, {"action": "query", "prop": "extracts|info", "explaintext": 1, "exsectionformat": "wiki", "redirects": 1, "titles": title, "formatversion": 2, "inprop": "url"}) or {}
    pg = ((v.get("query") or {}).get("pages") or [{}])[0]
    text = pg.get("extract") or ""; title = pg.get("title") or title
    lead, secs = parse_sections(text)
    secs = [s for s in secs if not re.match(r"^(see also|references|notes|further reading|external links|bibliography|works cited|sources|explanatory notes|citations|footnotes|filmography|electoral history|awards and honou?rs|selected works|publications)$", s[1], re.I)]
    used = set()
    sec = {k: pick(secs, k, 3 if k != "controv" else 2, 700, used) for k in ("early", "education", "family", "career", "ideology", "image")}
    controv = []
    for lv, h, body, own in secs:
        if SEC["controv"].search(h) and h not in used:
            ex = excerpt(body, 2, 480)
            if ex: controv.append({"text": ex, "section": h}); used.add(h)
        if len(controv) >= 6: break
    actions = []
    for lv, h, body, own in secs:
        if SEC["actions"].search(h) and h not in used and len(actions) < 6:
            ex = excerpt(own or body, 2, 420)
            if ex: actions.append({"text": ex, "section": h}); used.add(h)
    # supporters' and critics' views: sentences from the article that report praise or criticism, each linked to its section
    pro, con, goals = [], [], []
    sur = re.escape(name.split()[-1]); who = rf"(?:{sur}|him|her)"
    VIEW = r"(?:\s+\w+){0,3}\s+(?:say|says|said|argue|argues|argued|credit|credits|credited|praise|praised|view|viewed|see|saw|consider|considered|describe|described|hail|hailed|contend|contended|call|called|regard|regarded)\b"
    PROX = re.compile(rf"\b(?:supporters|admirers|proponents|defenders)\b{VIEW}|\b(?:praised|lauded|applauded|commended|hailed|credited)\s+(?:\w+\s+)?{who}\b|"
                      rf"\b{sur}\b[^.]{{0,40}}\b(?:was|has been|were)\s+(?:widely\s+)?(?:praised|lauded|credited|commended|hailed)", re.I)
    CONX = re.compile(rf"\b(?:critics|detractors|opponents)\b{VIEW}|\b(?:criticized|criticised|condemned|denounced|faulted|rebuked)\s+(?:\w+\s+)?{who}\b|\baccused\s+{who}\s+of\b|"
                      rf"\b{sur}\b[^.]{{0,40}}\b(?:was|has been|were)\s+(?:widely\s+|heavily\s+|sharply\s+)?(?:criticized|criticised|condemned|censured)", re.I)
    SUBJ = re.compile(rf"^(?:(?:In|On|By|During|After)\b[^,]{{0,40}},\s*)?(?:{sur}|He|She)\s+(?:\w+\s+){{0,2}}(?:criticized|criticised|condemned|denounced|accused|praised|defended|endorsed|called|attacked)\b")
    pri = sorted(secs, key=lambda s: 0 if SEC["image"].search(s[1]) else (1 if SEC["controv"].search(s[1]) else 2))
    for lv, h, body, own in pri:
        for s in sentences(own):
            if len(s) < 60 or len(s) > 360: continue
            if SUBJ.search(s): continue
            p_, c_ = bool(PROX.search(s)), bool(CONX.search(s))
            if p_ and not c_ and len(pro) < 4 and s not in [x["text"] for x in pro]: pro.append({"text": s, "section": h})
            elif c_ and not p_ and len(con) < 4 and s not in [x["text"] for x in con]: con.append({"text": s, "section": h})
            gm = GOAL.search(s)
            s2 = re.sub(r"^(?:In|During|After|Before|On|By|As|Since|Despite|While|When|Following)\b[^,]{0,90},\s*", "", s)
            if gm and re.match(rf"(?:{sur}|He|She)\b(?!['’]s)", s2) and not re.search(rf"\b{sur}['’]s\b", s[gm.start():]) \
                    and len(goals) < 4 and (SEC["ideology"].search(h) or SEC["actions"].search(h)): goals.append({"text": s, "section": h})
    summ = excerpt(lead, 3, 650)
    # ---- photos: Wikidata portrait + free photos from the article
    p18 = [c["v"] for c in P("P18")[:2] if isinstance(c["v"], str)]
    ml = wm.url("https://en.wikipedia.org/api/rest_v1/page/media-list/" + urllib.parse.quote(title.replace(" ", "_"), safe="")) or {}
    art = []
    for it in (ml.get("items") or []):
        t = (it.get("title") or "").removeprefix("File:")
        if it.get("type") == "image" and t and not BAD_FILE.search(t) and re.search(r"\.(jpe?g|webp)$", t, re.I): art.append(t)
    info = commons_info(wm, p18 + art[:24], 960)
    portrait = next((info[f] for f in [x.replace("_", " ") for x in p18] if f in info), None)
    gal = [info[f] for f in [x.replace("_", " ") for x in art] if f in info and (not portrait or info[f]["file"] != portrait["file"])][:6]
    if portrait:
        pi = commons_info(wm, [portrait["file"]], 480).get(portrait["file"])
        if pi: portrait = dict(portrait, avatar_src=pi["src"])
    HEAD = re.compile(r"^(?:\d+(?:st|nd|rd|th)\s+)?(?:President|Vice President|Prime Minister|Deputy Prime Minister|Chancellor|Supreme Leader|King|Queen|Emir|Crown Prince|"
                      r"Secretary|Minister|Governor|Senator|United States senator|United States representative|Mayor|Attorney General|Director|Director-General|Chief|Speaker|"
                      r"Leader|Chair|Chairman|Commander|Ambassador|Secretary-General|Member of the|Special Envoy|White House|National Security Advisor|Foreign|Defence|Defense)", re.I)
    cur = [p for p in positions if p["current"] and HEAD.search(p["title"]) and not re.match(r"^(member of|chairperson$)", p["title"], re.I)]
    dsc = re.sub(r"^\d+\.?\s*°?\s*", "", re.sub(r"\s*\((?:born |\d{4}).*?\)\s*$", "", desc(ent)).strip())
    role = (cur[0]["title"] if cur else "") or dsc
    if role: role = role[:1].upper() + role[1:]
    tl = []
    if born: tl.append({"date": born_iso, "label": born, "text": f"Born{' in ' + born_in if born_in else ''}", "src": "wikidata"})
    for e_ in edu:
        if e_["to"]: tl.append({"date": e_["sort"], "label": e_["to"], "text": f"Completes studies at {e_['name']}", "src": "wikidata"})
    for p in parties:
        if p["from"]: tl.append({"date": p["sort"], "label": p["from"], "text": f"Joins the {p['name']}" if not p['name'].lower().startswith("the ") else f"Joins {p['name']}", "src": "wikidata"})
    for p in positions:
        if p["from"]: tl.append({"date": p["sort"], "label": p["from"], "text": f"Becomes {p['title']}" + (f" (until {p['to']})" if p["to"] else ""), "src": "wikidata"})
    for j in jobs:
        if j["from"]: tl.append({"date": j["sort"], "label": j["from"], "text": f"Starts at {j['name']}", "src": "wikidata"})
    if died: tl.append({"date": died_iso, "label": died, "text": "Dies", "src": "wikidata"})
    tl = sorted({(x["date"], x["text"]): x for x in tl if x["date"]}.values(), key=lambda x: x["date"])[:40]
    return {"pv": PV, "qid": qid, "slug": slugify(name), "seed": seed_key, "name": name, "description": desc(ent), "role": role, "wiki_title": title,
            "wiki_url": anchor(title), "wikidata_url": f"https://www.wikidata.org/wiki/{qid}", "website": website if isinstance(website, str) and website.startswith("http") else "",
            "born": born, "born_iso": born_iso, "born_in": born_in, "died": died, "citizenship": citizenship, "religion": religion,
            "party": parties[0]["name"] if parties else "", "parties": [{k: p[k] for k in ("name", "from", "to")} for p in parties[:6]],
            "ideology": ideol, "occupations": occ, "positions": [{k: p[k] for k in ("title", "from", "to", "current")} for p in positions[:14]],
            "education": [{k: e_[k] for k in ("name", "to")} for e_ in edu[:6]], "employers": [{k: j[k] for k in ("name", "from", "to")} for j in jobs[:8]],
            "military": {"branch": branch, "rank": rank_mil}, "family": fam, "summary": summ,
            "sections": {k: v for k, v in sec.items() if v}, "controversies": controv, "actions": actions,
            "views": {"supporters": pro, "critics": con}, "goals": goals, "timeline": tl,
            "portrait": portrait, "gallery": gal, "built_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "sources": [{"label": f"Wikipedia: {title} (CC BY-SA 4.0)", "url": anchor(title)}, {"label": f"Wikidata: {qid} (CC0)", "url": f"https://www.wikidata.org/wiki/{qid}"}]
                       + ([{"label": "Official website", "url": website}] if isinstance(website, str) and website.startswith("http") else [])}

# ------------------------------------------------------------------ detection
_NAME = re.compile(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?|[A-Z]\.(?:\s?[A-Z]\.)?)\s+((?:[A-Z][a-z]+\s+)?(?:(?:al|el|bin|ben|van|von|de|da|di|du|la|le)\s+)?(?:Mc|Mac|O')?[A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b")

def candidates(texts):
    cnt = {}
    for t in texts:
        seen = set()
        for m in _NAME.finditer(t or ""):
            a, b = m.group(1), m.group(2)
            if a.lower().rstrip(".") in STOP1 or b.split()[-1].lower() in STOP1 or b.split()[0].lower() in STOP1: continue
            nm = f"{a} {b}"
            if nm in seen: continue
            seen.add(nm); cnt[nm] = cnt.get(nm, 0) + 1
    return cnt

def _public(e):
    if "Q5" not in [c["v"] for c in claims(e, "P31")] or not enwiki(e): return False
    died = claims(e, "P570")
    if died and (wdate(died[0]["v"])[0][:4] or "0") < "2010": return False
    born = claims(e, "P569")
    if born and wdate(born[0]["v"])[0][:4] and wdate(born[0]["v"])[0][:4] < "1900": return False
    occ = {c["v"] for c in claims(e, "P106")}
    return bool(claims(e, "P39") or claims(e, "P102") or occ & ROLE_OCC or ROLE_DESC.search(desc(e)))

TOPICS = None   # set by run(): {name_lower: {qid, label, file}} for names that are places, organisations or things with a Commons image

def resolve_batch(wm, names, neg):
    """{name: (qid, label)} for candidate names that are exact English Wikipedia titles (after redirects) of a living or recent
    public figure. 50 names per Wikipedia call and 10 entities per Wikidata call; misses are cached in neg for 30 days."""
    out = {}
    names = [n for n in names if not (n.lower() in neg and now() - neg[n.lower()] < 30 * 86400)]
    for k in range(0, len(names), 50):
        if not wm.can(): break
        chunk = names[k:k + 50]
        v = wm.get(WP, {"action": "query", "titles": "|".join(chunk), "redirects": 1, "prop": "pageprops", "ppprop": "wikibase_item|disambiguation", "formatversion": 2}, ttl=30 * 86400)
        if v is None: break
        q = v.get("query") or {}
        m = {n: n for n in chunk}
        for x in q.get("normalized") or []:
            for n in chunk:
                if m[n] == x.get("from"): m[n] = x.get("to")
        for x in q.get("redirects") or []:
            for n in chunk:
                if m[n] == x.get("from"): m[n] = x.get("to")
        byt = {p.get("title"): p for p in q.get("pages") or []}
        qids = {}
        for n in chunk:
            p = byt.get(m[n]) or {}
            pp = p.get("pageprops") or {}
            if p.get("missing") or "disambiguation" in pp or not pp.get("wikibase_item"): neg[n.lower()] = now(); continue
            qids[n] = pp["wikibase_item"]
        for j in range(0, len(qids), 10):
            part = list(qids.items())[j:j + 10]
            E = entities(wm, [qq for _, qq in part], props="claims|sitelinks|descriptions|labels", ttl=30 * 86400)
            for n, qq in part:
                e = E.get(qq) or {}
                lab = label(e) or m[n]
                toks = lambda s: set(re.findall(r"[a-z]+", __import__("unicodedata").normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()))
                ok_name = n.split()[-1].lower() in toks(lab) and (n.split()[0].lower().rstrip(".") in toks(lab) or len(toks(n) & toks(lab)) >= 2)
                if e and ok_name and _public(e): out[n] = (qq, lab)
                elif e:
                    neg[n.lower()] = now()
                    f18 = [c["v"] for c in claims(e, "P18")[:1] if isinstance(c["v"], str)]
                    if f18 and "Q5" not in [c["v"] for c in claims(e, "P31")] and TOPICS is not None:
                        TOPICS[n.lower()] = {"qid": qq, "label": lab, "file": f18[0], "t": now()}
    return out

def load_reg():
    try:
        with open(REG, encoding="utf-8") as f: r = json.load(f)
    except Exception: r = {}
    r.setdefault("people", {}); r.setdefault("neg", {}); r.setdefault("profiles", {})
    return r

def save_reg(r):
    os.makedirs(PDIR, exist_ok=True)
    tmp = REG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(r, f, ensure_ascii=False)
    os.replace(tmp, REG)

COMMON_SURNAMES = set("""miller johnson smith brown jones williams davis wilson taylor anderson thomas moore martin jackson white harris clark lewis young
walker hall allen king wright scott green baker adams nelson hill campbell mitchell roberts carter phillips evans turner parker collins edwards stewart
morris murphy cook rogers morgan cooper peterson bailey reed kelly howard cox ward richardson wood watson brooks bennett gray grey james hughes price
sanders myers long ross foster powell russell sullivan bell coleman butler henderson barnes fisher stone hunt black rose blanche khan ali kim lee wang
zhang chen singh kumar garcia martinez rodriguez lopez gonzalez hernandez perez sanchez castro golan cruz ramirez torres flores rivera gomez diaz
reyes morales ortiz gutierrez chavez ramos ruiz alvarez mendoza vasquez castillo jimenez moreno romero herrera medina aguilar""".split())

def person_rx(p):
    if p.get("rx"): return re.compile(p["rx"])
    nm = p["name"]; parts = [x for x in re.split(r"\s+", nm) if x]
    alts = [re.escape(nm)]
    if len(parts) >= 3: alts.append(re.escape(parts[0]) + r"\s+" + re.escape(parts[-1]))
    if p.get("surname_ok") and parts: alts.append(re.escape(parts[-1]))
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b")

# ------------------------------------------------------------------ place photo (lead fallback)
def place_photo(wm, loc, neg):
    loc = re.sub(r"\s+", " ", (loc or "")).strip()
    if not loc or len(loc) > 80: return None
    tries = [loc] + ([loc.split(",")[0].strip()] if "," in loc else [])
    for q in tries:
        k = "place:" + q.lower()
        if k in neg and now() - neg[k] < 30 * 86400: continue
        v = wm.get(WD, {"action": "wbsearchentities", "search": q, "language": "en", "type": "item", "limit": 3}, ttl=30 * 86400)
        if v is None: return None
        for h in (v.get("search") or [])[:3]:
            e = entities(wm, [h["id"]], props="claims|labels|descriptions").get(h["id"]) or {}
            if not claims(e, "P625"): continue         # a place has coordinates
            f = [c["v"] for c in claims(e, "P18")[:1]]
            if not f: continue
            info = commons_info(wm, f, 1200).get(f[0].replace("_", " "))
            if info:
                return {"src": info["src"], "w": info["w"], "h": info["h"], "kind": "place", "alt": f"File photo: {label(e)}",
                        "caption": f"File photo of {label(e)}" + (f" ({info['date'][:4]})" if info.get("date", "")[:4].isdigit() else "") + ". Not taken at this event.",
                        "credit": f"{info['author']} / Wikimedia Commons", "license": info["license"], "link": info["source"]}
        neg[k] = now()
    return None

# Countries and regions named in headlines (name -> search term for its Wikidata item); demonyms map to the country.
COUNTRIES = {k.lower(): v for k, v in [(x, x) for x in (
 "Afghanistan Albania Algeria Angola Argentina Armenia Australia Austria Azerbaijan Bahrain Bangladesh Belarus Belgium Bolivia Bosnia Brazil "
 "Bulgaria Burkina Faso Cambodia Cameroon Canada Chile China Colombia Congo Croatia Cuba Cyprus Czechia Denmark Djibouti Ecuador Egypt "
 "Eritrea Estonia Ethiopia Fiji Finland France Gabon Germany Ghana Greece Greenland Guatemala Guinea Haiti Honduras Hungary Iceland India "
 "Indonesia Iran Iraq Ireland Israel Italy Jamaica Japan Jordan Kazakhstan Kenya Kosovo Kuwait Kyrgyzstan Laos Latvia Lebanon Libya Lithuania "
 "Madagascar Malawi Malaysia Mali Malta Mauritania Mexico Moldova Mongolia Montenegro Morocco Mozambique Myanmar Namibia Nepal Netherlands "
 "Nicaragua Niger Nigeria Norway Oman Pakistan Panama Paraguay Peru Philippines Poland Portugal Qatar Romania Russia Rwanda Senegal Serbia "
 "Singapore Slovakia Slovenia Somalia Spain Sudan Sweden Switzerland Syria Taiwan Tajikistan Tanzania Thailand Tunisia Turkey Turkmenistan "
 "Uganda Ukraine Uruguay Uzbekistan Venezuela Vietnam Yemen Zambia Zimbabwe Gaza Crimea Kashmir Tibet Xinjiang Donbas Chechnya Kurdistan").split()]
 + [("Burkina Faso", "Burkina Faso"), ("DR Congo", "Democratic Republic of the Congo"), ("Democratic Republic of the Congo", "Democratic Republic of the Congo"),
    ("North Korea", "North Korea"), ("South Korea", "South Korea"), ("South Africa", "South Africa"), ("South Sudan", "South Sudan"), ("Saudi Arabia", "Saudi Arabia"),
    ("United Kingdom", "United Kingdom"), ("Britain", "United Kingdom"), ("New Zealand", "New Zealand"), ("Sri Lanka", "Sri Lanka"), ("Puerto Rico", "Puerto Rico"),
    ("West Bank", "West Bank"), ("Gaza Strip", "Gaza Strip"), ("Strait of Hormuz", "Strait of Hormuz"), ("Red Sea", "Red Sea"), ("Taiwan Strait", "Taiwan Strait"),
    ("Ukrainian", "Ukraine"), ("Russian", "Russia"), ("Iranian", "Iran"), ("Israeli", "Israel"), ("Chinese", "China"), ("Japanese", "Japan"), ("Indian", "India"),
    ("Pakistani", "Pakistan"), ("Syrian", "Syria"), ("Lebanese", "Lebanon"), ("Iraqi", "Iraq"), ("Yemeni", "Yemen"), ("Turkish", "Turkey"), ("Venezuelan", "Venezuela"),
    ("Mexican", "Mexico"), ("Canadian", "Canada"), ("Brazilian", "Brazil"), ("Polish", "Poland"), ("German", "Germany"), ("French", "France"), ("British", "United Kingdom"),
    ("Palestinian", "State of Palestine"), ("Kenyan", "Kenya"), ("Nigerian", "Nigeria"), ("Sudanese", "Sudan"), ("Ethiopian", "Ethiopia"), ("Somali", "Somalia"),
    ("Cuban", "Cuba"), ("Haitian", "Haiti"), ("Taiwanese", "Taiwan"), ("Korean", "South Korea"), ("Filipino", "Philippines"), ("Indonesian", "Indonesia")]}
_CRX = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in COUNTRIES), key=len, reverse=True)) + r")\b", re.I)

def country_in(*texts):
    for t in texts:
        m = _CRX.search(t or "")
        if m: return COUNTRIES[m.group(1).lower()]
    return ""

# ------------------------------------------------------------------ main entry
def run(corpus, budget=350, seconds=200, max_new=30, max_profiles=12, offline=False, seed_only=False):
    """corpus: [{"cid","title","text","when","rank","loc","has_image"}]. Returns the 'people' block for story_reports.json."""
    if os.environ.get("BN_PEOPLE", "1") == "0" or os.path.exists(KILL):
        log("off (BN_PEOPLE=0 or desk/people_off)"); return None
    global TOPICS
    t0 = now(); wm = WM(budget, seconds, offline=offline); reg = load_reg(); P = reg["people"]
    TOPICS = reg.setdefault("topics", {})
    for key, qid, rx in SEED:
        if qid and qid not in P: P[qid] = {"qid": qid, "seed": key, "rx": rx, "name": "", "first_seen": datetime.now(UTC).isoformat()[:19]}
        elif qid: P[qid]["rx"] = rx; P[qid]["seed"] = key
    texts = [c["text"] for c in corpus]
    # 1) new names, most frequent first, capped per cycle
    known = {(p.get("name") or "").lower() for p in P.values()}
    cand = sorted(((n, k) for n, k in candidates(texts).items() if n.lower() not in known), key=lambda x: -x[1])
    added = 0
    if not seed_only:
        todo = [n for n, k in cand if not (n.lower() in reg["neg"] and now() - reg["neg"][n.lower()] < 30 * 86400)][:max_new]
        for nm, (qid, lab) in resolve_batch(wm, todo, reg["neg"]).items():
            added += 1
            if qid not in P:
                P[qid] = {"qid": qid, "name": lab, "first_seen": datetime.now(UTC).isoformat()[:19]}
                log(f"new person: {lab} ({qid}) from '{nm}'")
    # 2) match every story; surname-only matching for seeds (curated) and people seen by full name in 2+ stories, unless shared
    surn = {}
    for q, p in P.items():
        if p.get("name"): surn.setdefault(p["name"].split()[-1], []).append(q)
    rxs = {}
    for q, p in P.items():
        if not p.get("name") and not p.get("rx"): continue
        sp = (p.get("name") or "").split()
        p["surname_ok"] = bool(not p.get("rx") and sp and len(sp[-1]) >= 5 and len(surn.get(sp[-1], [])) == 1 and p.get("full_hits", 0) >= 2 and sp[-1].lower() not in STOP1 and sp[-1].lower() not in COMMON_SURNAMES)
        rxs[q] = person_rx(p)
    story_people, counts = {}, {}
    for c in corpus:
        hits = []
        for q, rx in rxs.items():
            n = len(rx.findall(c["text"]))
            if n: hits.append((q, n + (3 if rx.search(c["title"] or "") else 0)))
        if hits:
            hits.sort(key=lambda x: -x[1])
            story_people[c["cid"]] = [q for q, _ in hits[:6]]
            for q, _ in hits:
                counts[q] = counts.get(q, 0) + 1
                st = P[q].setdefault("stories", {})
                st[c["cid"]] = {"t": c.get("when") or "", "title": (c.get("title") or "")[:200], "rank": c.get("rank") or 0}
                if len(st) > 300:
                    for old in sorted(st, key=lambda x: st[x]["t"])[:len(st) - 300]: st.pop(old, None)
    for q, p in P.items():
        if p.get("name"):
            full = re.compile(r"\b" + re.escape(p["name"]) + r"\b")
            p["full_hits"] = max(p.get("full_hits", 0), sum(1 for t in texts if full.search(t)))
        p["mentions_now"] = counts.get(q, 0)
    # 3) profiles: refresh weekly; most mentioned first, a few per cycle
    order = sorted((q for q in P if counts.get(q) or P[q].get("seed")), key=lambda q: (-counts.get(q, 0), q))
    built = 0
    for q in order:
        prof = reg["profiles"].get(q)
        fresh = prof and prof.get("pv") == PV and now() - datetime.fromisoformat(prof["built_at"]).timestamp() < 7 * 86400
        if fresh or built >= max_profiles or not wm.can(): continue
        try:
            pr = build_profile(wm, q, P[q].get("seed", ""))
        except Exception as ex:
            log(f"profile {q} failed: {ex}"); pr = None
        if pr:
            reg["profiles"][q] = pr; P[q]["name"] = pr["name"]; built += 1
    # slugs unique
    slugs = {}
    for q in sorted(reg["profiles"], key=lambda x: (-counts.get(x, 0), x)):
        s = reg["profiles"][q]["slug"]
        if s in slugs and slugs[s] != q: s = f"{s}-{q.lower()}"; reg["profiles"][q]["slug"] = s
        slugs[s] = q
    # 4) lead photo for stories with no image: main person's portrait, else a place photo
    lead = {}
    for c in corpus:
        if c.get("has_image"): continue
        def at(q):
            m = rxs[q].search(c.get("title") or "") if q in rxs else None
            return m.start() if m else 10 ** 6
        q = next((q for q in sorted(story_people.get(c["cid"], []), key=at) if (reg["profiles"].get(q) or {}).get("portrait")), None)
        if q:
            pr = reg["profiles"][q]; po = pr["portrait"]
            yr = po.get("date", "")[:4]
            lead[c["cid"]] = {"src": po["src"], "w": po["w"], "h": po["h"], "kind": "person", "person": pr["slug"], "alt": pr["name"],
                              "caption": f"{pr['name']}" + (f", {yr}" if yr.isdigit() else "") + ". File photo; not taken at this event.",
                              "credit": f"{po['author']} / Wikimedia Commons", "license": po["license"], "link": po["source"]}
    for c in corpus:
        if c.get("has_image") or c["cid"] in lead or not c.get("loc") or not wm.can(): continue
        k = "plc:" + c["loc"].lower()
        hit = reg.setdefault("places", {}).get(k)
        if hit is None or (not hit and now() - reg.get("places_t", {}).get(k, 0) > 7 * 86400):
            hit = place_photo(wm, c["loc"], reg["neg"]) or {}
            reg["places"][k] = hit; reg.setdefault("places_t", {})[k] = now()
        if hit: lead[c["cid"]] = hit
    # 4b) still nothing: a Commons photo of a place, organisation or thing named in the headline (resolved above), file-photo caption
    tnames = sorted(((k, v) for k, v in TOPICS.items() if v.get("file")), key=lambda kv: -len(kv[0]))
    for c in corpus:
        if c.get("has_image") or c["cid"] in lead: continue
        tl = (c.get("title") or "").lower()
        hit = next((v for k, v in tnames if re.search(r"\b" + re.escape(k) + r"\b", tl)), None)
        if not hit: continue
        if "img" not in hit:
            if not wm.can(): continue
            info = commons_info(wm, [hit["file"]], 1200).get(hit["file"].replace("_", " "))
            hit["img"] = {"src": info["src"], "w": info["w"], "h": info["h"], "kind": "place", "alt": f"File photo: {hit['label']}",
                          "caption": f"File photo: {hit['label']}" + (f" ({info['date'][:4]})" if info.get("date", "")[:4].isdigit() else "") + ". Not taken at this event.",
                          "credit": f"{info['author']} / Wikimedia Commons", "license": info["license"], "link": info["source"]} if info else {}
        if hit.get("img"): lead[c["cid"]] = hit["img"]
    # 4c) still nothing: the country or region named in the headline or location
    for c in corpus:
        if c.get("has_image") or c["cid"] in lead or not wm.can() and not reg.get("places"): continue
        co = country_in(c.get("title") or "", c.get("loc") or "")
        if not co: continue
        k = "plc:" + co.lower()
        hit = reg.setdefault("places", {}).get(k)
        if hit is None and wm.can():
            hit = place_photo(wm, co, reg["neg"]) or {}
            reg["places"][k] = hit; reg.setdefault("places_t", {})[k] = now()
        if hit: lead[c["cid"]] = hit
    # 5) output block
    out_people = {}
    keep = [q for q in reg["profiles"] if counts.get(q) or P.get(q, {}).get("stories")]
    keep = sorted(keep, key=lambda q: (-counts.get(q, 0), -len(P.get(q, {}).get("stories", {})), q))[:150]
    for q in keep:
        pr = dict(reg["profiles"][q])
        st = P.get(q, {}).get("stories", {})
        pr["stories"] = sorted(({"cid": k, **v} for k, v in st.items()), key=lambda x: x["t"], reverse=True)[:200]
        pr["mentions_now"] = counts.get(q, 0)
        if q in rxs: pr["rx"] = rxs[q].pattern
        for k in ("seed", "built_at"): pr.pop(k, None)
        out_people[pr["slug"]] = pr
    sp = {cid: [reg["profiles"][q]["slug"] for q in qs if q in reg["profiles"]] for cid, qs in story_people.items()}
    sp = {k: v for k, v in sp.items() if v}
    save_reg(reg)
    log(f"{len(out_people)} profiles ({built} built now), {len(sp)} stories with people, {len(lead)} lead photos; "
        f"{wm.sent} Wikimedia requests, {wm.hits} cache hits, {now() - t0:.0f}s" + (f", stopped: {wm.stopped}" if wm.stopped else ""))
    places = {}
    for k, v in (reg.get("places") or {}).items():
        nm = k.removeprefix("plc:")
        if v and v.get("src") and (nm in {x.lower() for x in COUNTRIES.values()} or nm in COUNTRIES): places[nm] = v
    return {"v": 1, "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(), "profiles": out_people, "story_people": sp, "places": places,
            "country_alias": {k: v.lower() for k, v in COUNTRIES.items() if v.lower() in places},
            "lead": lead, "top": [reg["profiles"][q]["slug"] for q in sorted(keep, key=lambda q: -counts.get(q, 0)) if counts.get(q)][:60]}

def wire_page_bits(body):
    """(headline, location, report headlines) from one of our own cached /wire/<id> pages ('' when unknown)."""
    if not body: return "", "", []
    h = re.search(r'<h1 class="t">(.*?)</h1>', body, re.S)
    m = re.search(r'<p class="meta">(.*?)</p>', body, re.S)
    loc = ""
    if m:
        last = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).split(" · ")[-1].strip()
        if not re.match(r"^(Updated|First seen|Confirmed|Watchlist|Background)", last): loc = last[:80]
    i = body.find('<ul class="tl">')
    rep = [html.unescape(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r'<a href="https?://[^"]+" target="_blank" rel="noopener">(.*?)</a>', body[i:] if i >= 0 else "")][:40]
    return html.unescape(re.sub(r"<[^>]+>", "", h.group(1))).strip() if h else "", loc, rep

def corpus_from(st, items, home, notes, alias, images, shares, pages=None):
    """One entry per story we can render: board stories (title, scanner brief, report headlines, location) + homepage-linked
    stories (headline) + desk notes (headline, what happened, analysis)."""
    C = {}
    def add(cid, title="", text="", when="", rank=0, loc=""):
        if not re.fullmatch(r"[0-9a-f]{16}", cid or ""): return
        c = C.setdefault(cid, {"cid": cid, "title": "", "text": "", "when": "", "rank": 0, "loc": ""})
        if title and not c["title"]: c["title"] = title
        c["text"] += " \n " + (title or "") + " \n " + (text or "")
        c["when"] = max(c["when"], when or ""); c["rank"] = max(c["rank"], int(rank or 0)); c["loc"] = c["loc"] or (loc or "")
    for s in (st.get("main") or []) + (st.get("watchlist") or []):
        cid = s.get("cluster_id")
        what = re.search(r"WHAT:\s*(.*?)\s*(?:WHERE:|WHEN:|CONFIDENCE:|VERIFY:|$)", s.get("brief") or "", re.S)
        add(cid, s.get("title") or "", (what.group(1) if what else "")[:1500], s.get("updated") or s.get("first_seen") or "", s.get("rank"), s.get("location") or "")
        for it in (items.get(cid) or [])[:30]: add(cid, "", it.get("title") or "")
    for cid, h in (home or {}).items(): add(cid, h.get("title") or "", "", "", h.get("rank") or 0)
    for cid, body in (pages or {}).items():
        t, loc, rep = wire_page_bits(body)
        if t or rep: add(cid, t, " \n ".join(rep), "", 0, loc)
    for cid, n in (notes or {}).items():
        add(cid, "", " ".join(str(n.get(k) or "") for k in ("headline", "what_happened", "why_it_matters", "analysis")), n.get("generated_at") or "")
    for a, b in (alias or {}).items():
        if a in C and b in notes: C[a]["text"] += " " + " ".join(str(notes[b].get(k) or "") for k in ("headline", "what_happened"))
    for cid, c in C.items():
        c["has_image"] = bool((images or {}).get(cid)) or bool((shares or {}).get(cid))
        c["text"] = c["text"][:12000]
    return list(C.values())

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build / refresh the people layer standalone (writes people/registry.json; prints a summary).")
    ap.add_argument("--state", required=True); ap.add_argument("--items", required=True); ap.add_argument("--reports", required=True)
    ap.add_argument("--budget", type=int, default=2500); ap.add_argument("--seconds", type=int, default=1500)
    ap.add_argument("--max-new", type=int, default=60); ap.add_argument("--max-profiles", type=int, default=40)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    st = json.load(open(a.state)); items = json.load(open(a.items)).get("items") or {}; sr = json.load(open(a.reports))
    home = {k: {"rank": v, "title": ""} for k, v in (sr.get("home") or {}).items()}
    corp = corpus_from(st, items, home, sr.get("notes") or {}, sr.get("alias") or {}, sr.get("images"), sr.get("shares"))
    res = run(corp, a.budget, a.seconds, a.max_new, a.max_profiles)
    if a.out and res:
        with open(a.out, "w") as f: json.dump(res, f, ensure_ascii=False, indent=1)
    if res:
        for s in res["top"][:40]:
            p = res["profiles"][s]; print(f"{p['mentions_now']:4d}  {p['name']:<32} {p['role'][:60]}")
