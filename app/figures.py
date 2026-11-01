"""Key Figures add-on (tab "👥 Key Figures", Reference group, deep link #figures; #elon redirects here). t353.
Neutral reference cards for people named in the stories BLACKOUT.NETWORK is tracking: name, current role, country, one factual
line on why they are in the news, how many recent alerts mention them, the latest related headlines and a profile link.
Never labels a person a threat; shows no ranks, scores or severity for people and no aircraft tracking.
Read-only: blackout.db is opened only as file:blackout.db?mode=ro; never touches scanner.py, scoring, push.py, jets.py or config.json.
Who appears: a curated base list (people in today's reports, roles as of Nov 1 2026) plus anyone from POOL who is named in a
rank 4+ alert on The Wire in the last 7 days. Headlines: matching scanner alerts first (link to /wire/<id>, which the
page turns into a jump to the item on The Wire), topped up from Google News (verbatim headlines) when fewer than 3 alerts match.
Memory: one bounded DB pass (<=1500 short rows, truncated text), results cached 10 min; Google News per person cached 1 h (figures.db)."""
import os, re, sqlite3, threading, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import importlib, bn_feeds as B
if getattr(B, "_mt", None) != os.path.getmtime(B.__file__): B = importlib.reload(B); B._mt = os.path.getmtime(B.__file__)

BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "figures.db")
BDB = "file:" + os.path.join(BASE, "blackout.db") + "?mode=ro"
STATIC = os.path.join(BASE, "figures_static"); FILES = {"app.js": "application/javascript", "app.css": "text/css"}
WIKI = "https://en.wikipedia.org/wiki/"
DAYS, MIN_RANK, MAX_ROWS, MAX_HEADLINES = 7, 4, 1500, 5
AS_OF = "2026-11-01"

# key, name, role, country, why (neutral, factual, sourced in today's reports), regex, profile links [(label, url)]
BASE_LIST = [
 ("trump", "Donald Trump", "President of the United States", "United States",
  "Commenting on the US–Iran talks in Doha and on possible further US action after the Nov 3 midterms.",
  r"\bTrump\b(?!\s+(?:Tower|Media|National|Doral))", [("Wikipedia", WIKI + "Donald_Trump"), ("White House", "https://www.whitehouse.gov/")]),
 ("mkhamenei", "Mojtaba Khamenei", "Supreme Leader of Iran", "Iran",
  "State media say he ordered Iran's forces to answer any renewed attack \"without geographic limits\".",
  r"\bKhamenei\b", [("Wikipedia", WIKI + "Mojtaba_Khamenei")]),
 ("araghchi", "Abbas Araghchi", "Foreign Minister of Iran", "Iran",
  "Iran's top diplomat while Iranian envoys hold Qatar-mediated talks with the US in Doha.",
  r"\bAraghchi\b", [("Wikipedia", WIKI + "Abbas_Araghchi")]),
 ("rezaei", "Mohsen Rezaei", "Secretary of Iran's Supreme National Security Council", "Iran",
  "Told state TV on Oct 31 that Iran set seven conditions before talks or reopening the Strait of Hormuz.",
  r"\bRezaei\b", [("Wikipedia", WIKI + "Mohsen_Rezaei")]),
 ("rubio", "Marco Rubio", "U.S. Secretary of State", "United States",
  "Spoke on Iran and shipping after the G20 foreign ministers' meeting in Atlanta, which ended without a joint communiqué.",
  r"\bRubio\b", [("Wikipedia", WIKI + "Marco_Rubio"), ("State Department", "https://www.state.gov/")]),
 ("bessent", "Scott Bessent", "U.S. Secretary of the Treasury", "United States",
  "Speaking on sanctions on Iran and on the economy; scheduled for TV interviews on Nov 1.",
  r"\bBessent\b", [("Wikipedia", WIKI + "Scott_Bessent"), ("U.S. Treasury", "https://home.treasury.gov/")]),
 ("netanyahu", "Benjamin Netanyahu", "Prime Minister of Israel", "Israel",
  "Named in coverage of US–Israel coordination on Iran.",
  r"\bNetanyahu\b", [("Wikipedia", WIKI + "Benjamin_Netanyahu")]),
 ("zelensky", "Volodymyr Zelensky", "President of Ukraine", "Ukraine",
  "Reported large power outages after overnight Russian strikes; Trump said he would invite him to the G20 summit in Miami.",
  r"\bZelensk(?:y|yy|iy|ii)\b", [("Wikipedia", WIKI + "Volodymyr_Zelenskyy")]),
 ("putin", "Vladimir Putin", "President of Russia", "Russia",
  "Invited to the Dec 14–15 G20 summit in Miami while Russia–Ukraine strikes continue.",
  r"\bPutin\b", [("Wikipedia", WIKI + "Vladimir_Putin")]),
 ("carney", "Mark Carney", "Prime Minister of Canada", "Canada",
  "Said Canada is prepared to wait out an unfavourable US trade deal while deepening ties with the EU.",
  r"\bCarney\b", [("Wikipedia", WIKI + "Mark_Carney"), ("Prime Minister of Canada", "https://www.pm.gc.ca/en")]),
 ("thompson", "Trina L. Thompson", "U.S. District Judge, Northern District of California", "United States",
  "Issued a temporary restraining order, in force to Nov 16, on DOJ and DHS contacts with election officials over lists of alleged noncitizens.",
  r"\b(?:Trina\s+(?:L\.\s+)?Thompson|Judge\s+Thompson)\b", [("Wikipedia", WIKI + "Trina_Thompson")]),
 ("nikitin", "Gleb Nikitin", "Governor of Nizhny Novgorod Oblast", "Russia",
  "Reported \"significant damage\" at an industrial site in Kstovo after an overnight drone attack, with no casualties.",
  r"\bNikitin\b", [("Wikipedia", WIKI + "Gleb_Nikitin")]),
 ("tedros", "Tedros Adhanom Ghebreyesus", "Director-General, World Health Organization", "International",
  "Heads the WHO as it responds to the Ebola (Bundibugyo) outbreak in DR Congo, Kenya and Nigeria.",
  r"\bTedros\b", [("Wikipedia", WIKI + "Tedros_Adhanom_Ghebreyesus"), ("WHO", "https://www.who.int/director-general")]),
 ("musk", "Elon Musk", "CEO of Tesla and SpaceX; head of xAI and owner of X", "United States",
  "Business and technology figure; in the news for his companies (Tesla, SpaceX, xAI, X).",
  r"\bElon\s+Musk\b|\bMusk's\b|\bMusk\b", [("Wikipedia", WIKI + "Elon_Musk"),
   ("SpaceX updates", "https://www.spacex.com/updates/"), ("xAI news", "https://x.ai/news")]),
]
# Shown only when named in a rank 4+ alert in the last DAYS days. Roles as of AS_OF.
POOL = [
 ("vance", "JD Vance", "Vice President of the United States", "United States", r"\bVance\b", [("Wikipedia", WIKI + "JD_Vance")]),
 ("hegseth", "Pete Hegseth", "U.S. Secretary of Defense", "United States", r"\bHegseth\b", [("Wikipedia", WIKI + "Pete_Hegseth")]),
 ("patel", "Kash Patel", "Director of the FBI", "United States", r"\bKash\s+Patel\b|\bFBI Director Patel\b", [("Wikipedia", WIKI + "Kash_Patel")]),
 ("hobbs", "Katie Hobbs", "Governor of Arizona", "United States", r"\bHobbs\b", [("Wikipedia", WIKI + "Katie_Hobbs")]),
 ("kimju", "Kim Jong Un", "Supreme Leader of North Korea", "North Korea", r"\bKim\s+Jong[\s-]?Un\b", [("Wikipedia", WIKI + "Kim_Jong_Un")]),
 ("xi", "Xi Jinping", "President of China", "China", r"\bXi\s+Jinping\b|\bPresident\s+Xi\b", [("Wikipedia", WIKI + "Xi_Jinping")]),
 ("pezeshkian", "Masoud Pezeshkian", "President of Iran", "Iran", r"\bPezeshkian\b", [("Wikipedia", WIKI + "Masoud_Pezeshkian")]),
 ("tusk", "Donald Tusk", "Prime Minister of Poland", "Poland", r"\bTusk\b", [("Wikipedia", WIKI + "Donald_Tusk")]),
 ("nawrocki", "Karol Nawrocki", "President of Poland", "Poland", r"\bNawrocki\b", [("Wikipedia", WIKI + "Karol_Nawrocki")]),
 ("erdogan", "Recep Tayyip Erdoğan", "President of Turkey", "Turkey", r"\bErdo[gğ]an\b", [("Wikipedia", WIKI + "Recep_Tayyip_Erdo%C4%9Fan")]),
 ("modi", "Narendra Modi", "Prime Minister of India", "India", r"\bModi\b", [("Wikipedia", WIKI + "Narendra_Modi")]),
 ("macron", "Emmanuel Macron", "President of France", "France", r"\bMacron\b", [("Wikipedia", WIKI + "Emmanuel_Macron")]),
 ("merz", "Friedrich Merz", "Chancellor of Germany", "Germany", r"\bMerz\b", [("Wikipedia", WIKI + "Friedrich_Merz")]),
 ("lula", "Luiz Inácio Lula da Silva", "President of Brazil", "Brazil", r"\bLula\b", [("Wikipedia", WIKI + "Luiz_In%C3%A1cio_Lula_da_Silva")]),
 ("mbs", "Mohammed bin Salman", "Crown Prince and Prime Minister of Saudi Arabia", "Saudi Arabia", r"\bbin\s+Salman\b|\bMBS\b", [("Wikipedia", WIKI + "Mohammed_bin_Salman")]),
 ("lavrov", "Sergey Lavrov", "Foreign Minister of Russia", "Russia", r"\bLavrov\b", [("Wikipedia", WIKI + "Sergey_Lavrov")]),
 ("sheinbaum", "Claudia Sheinbaum", "President of Mexico", "Mexico", r"\bSheinbaum\b", [("Wikipedia", WIKI + "Claudia_Sheinbaum")]),
 ("lukashenko", "Alexander Lukashenko", "President of Belarus", "Belarus", r"\bLukashenko\b", [("Wikipedia", WIKI + "Alexander_Lukashenko")]),
]
CATS = {"conflict": "conflict", "war": "conflict", "political": "politics", "disease": "health", "natural": "natural hazards", "cyber": "cyber",
        "financial": "finance", "space": "space weather"}
INITIALS = {"kimju": "KJU", "tedros": "TAG", "mbs": "MBS", "xi": "XJ"}
URL1 = re.compile(r'"url"\s*:\s*"(https?://[^"]+)"|"(https?://[^"]+)"')
_lock = threading.Lock(); _C = {"t": 0, "v": None}

def _alerts():
    """One bounded read-only pass over recent rank 4+ clusters on The Wire (watchlist=0; unconfirmed Watchlist items are left out) -> {key: [alerts newest first]}."""
    people = [(p[0], re.compile(p[5], re.I)) for p in BASE_LIST] + [(p[0], re.compile(p[4], re.I)) for p in POOL]
    cut = B.iso(datetime.now(timezone.utc) - timedelta(days=DAYS)); hits = {k: [] for k, _ in people}; counts = {k: 0 for k, _ in people}; cats = {k: {} for k, _ in people}
    try:
        c = sqlite3.connect(BDB, uri=True, timeout=10)
        cur = c.execute("SELECT cluster_id, title, substr(COALESCE(brief,''),1,600), substr(COALESCE(links,''),1,700), category, COALESCE(updated, first_seen), "
                        "COALESCE(event_time, first_seen), watchlist FROM clusters WHERE watchlist=0 AND rank>=? AND COALESCE(updated, first_seen)>=? "
                        "ORDER BY COALESCE(updated, first_seen) DESC LIMIT ?", (MIN_RANK, cut, MAX_ROWS))
        for cid, title, brief, links, cat, upd, ev, wl in cur:
            text = (title or "") + " " + (brief or "")
            for k, rx in people:
                if not rx.search(text): continue
                counts[k] += 1
                cc = (cat or "").lower(); lab = next((v for kk, v in CATS.items() if kk in cc), None)
                if lab: cats[k][lab] = cats[k].get(lab, 0) + 1
                if len(hits[k]) < MAX_HEADLINES:
                    m = URL1.search(links or ""); src = (m.group(1) or m.group(2)) if m else None
                    hits[k].append({"cid": cid, "title": (title or "")[:240], "time": ev or upd, "updated": upd, "url": src,
                                    "source": urllib.parse.urlsplit(src).netloc.replace("www.", "") if src else None,
                                    "list": "Watchlist" if wl == 1 else "The Wire", "via": "scanner"})
        c.close(); err = None
    except Exception as ex: err = f"{type(ex).__name__}: {str(ex)[:120]}"
    return hits, counts, cats, err

def _gnews(name):
    def f():
        items = B.dedupe(B.gnews(f'"{name}" when:3d', 12))
        items.sort(key=lambda x: x.get("time") or "", reverse=True)
        return {"items": [{"title": x["title"][:240], "url": x["url"], "source": x.get("source"), "time": x.get("time"), "via": "Google News"} for x in items[:MAX_HEADLINES]]}
    v = B.cached(DB, "gn:" + name, 3600, f)
    return (v or {}).get("items") or []

def build():
    hits, counts, cats, err = _alerts()
    out = []
    for key, name, role, country, why, _rx, links in BASE_LIST:
        out.append({"key": key, "name": name, "role": role, "country": country, "why": why, "links": links, "curated": True})
    for key, name, role, country, _rx, links in POOL:
        if counts.get(key):
            top = sorted(cats[key].items(), key=lambda kv: -kv[1])[:2]
            why = "Named in recent alerts on The Wire" + (" about " + " and ".join(k for k, _ in top) if top else "") + "."
            out.append({"key": key, "name": name, "role": role, "country": country, "why": why, "links": links, "curated": False})
    need = [p for p in out if len(hits.get(p["key"]) or []) < 3]
    with ThreadPoolExecutor(max_workers=4) as ex:
        gn = dict(zip([p["key"] for p in need], ex.map(lambda p: _gnews(p["name"]), need)))
    for p in out:
        h = list(hits.get(p["key"]) or [])
        if len(h) < 3:
            seen = {re.sub(r"\W+", " ", x["title"].lower())[:60] for x in h}
            for x in gn.get(p["key"]) or []:
                k = re.sub(r"\W+", " ", x["title"].lower())[:60]
                if k in seen: continue
                seen.add(k); h.append(x)
                if len(h) >= MAX_HEADLINES: break
        p["headlines"] = h[:MAX_HEADLINES]; p["alerts"] = counts.get(p["key"], 0)
        p["latest"] = max([x.get("updated") or x.get("time") or "" for x in h] or [""])
        p["initials"] = INITIALS.get(p["key"]) or (p["name"].split()[0][0] + p["name"].split()[-1][0]).upper()
    # newest related mention first (alphabetical tie-break); not a ranking of people
    out.sort(key=lambda p: p["name"]); out.sort(key=lambda p: (p["alerts"] > 0, p["latest"]), reverse=True)
    return {"updated": B.iso(), "as_of": AS_OF, "days": DAYS, "people": out, "db_error": err,
            "note": ("People named in the stories BLACKOUT.NETWORK is following, listed by their most recent mention. This is a neutral reference: "
                     "being listed says nothing about a person beyond their public role and the news they appear in. Headlines are shown verbatim from "
                     f"the scanner's sources and Google News. Alert counts cover rank 4+ items on The Wire in the last {DAYS} days. "
                     f"Roles as of Nov 1, 2026; follow the profile links for the latest.")}

def summary():
    if _C["v"] and time.time() - _C["t"] < 600: return _C["v"]
    with _lock:
        if _C["v"] and time.time() - _C["t"] < 600: return _C["v"]
        v = build(); _C["v"] = v; _C["t"] = time.time(); return v

def handle_get(path, qs):
    n = path[len("/api/figures/"):] if path.startswith("/api/figures/") else ""
    if n in FILES:
        with open(os.path.join(STATIC, n), "rb") as fh: return 200, fh.read(), FILES[n]
    if path == "/api/figures":
        try: return 200, summary()
        except Exception as ex: return 503, {"error": f"{type(ex).__name__}: {str(ex)[:160]}"}
    return 404, {"error": "not found"}
